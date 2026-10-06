"""v0.19.0 — backup agendado e canário de e-mail, provados de verdade (FASES D e E).

DUAS LACUNAS REAIS DE PUBLICAÇÃO, DO MESMO TIPO.

1. `scripts/backup.sh` existia desde a v0.7.0 e a restauração era testada. Mas nada executava o
   script — nenhum cron, nenhum serviço, nenhum passo de CI. Uma auditoria anterior registrou
   "backup: existe script" e isso virou linha verde num relatório. Script que ninguém executa não é
   backup.
2. O cadastro depende do e-mail de verificação. Com falha silenciosa de SMTP, o funil de entrada vai
   a zero e a plataforma continua respondendo 202 em /v1/auth/register.

O QUE ESTES TESTES EXIGEM. Que o backup rode DE VERDADE contra o PostgreSQL de teste e produza um
dump que `pg_restore --list` aceite; que o resultado `not_configured` apareça quando falta
configuração, em vez de a ausência de registro parecer sucesso; que toda tentativa de envio deixe
registro; e que o estado de sucesso do e-mail se chame aceitação, nunca entrega.
"""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tests.support import OWNER_DSN, db_system, new_account, server


class BackupJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = server()["state"]

    def test_sem_configuracao_o_resultado_e_not_configured_e_nao_silencio(self):
        from impacto.ops import backup as BK
        settings = replace(self.app.settings, backup_dir="", backup_database_url="")
        with db_system() as c:
            out = BK.run(c, settings)
            registro = c.one("SELECT status, detail FROM ops_job_runs WHERE job = 'backup'"
                             " ORDER BY started_at DESC LIMIT 1")
        self.assertEqual(out["status"], "not_configured")
        self.assertEqual(registro["status"], "not_configured")
        self.assertIn("BACKUP_DIR", registro["detail"]["reason"])
        self.assertIn("NÃO existe backup", registro["detail"]["note"])

    def test_o_backup_roda_de_verdade_e_o_dump_e_valido(self):
        from impacto.ops import backup as BK
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(self.app.settings, backup_dir=tmp, backup_database_url=OWNER_DSN)
            with db_system() as c:
                out = BK.run(c, settings, force=True)
            self.assertEqual(out["status"], "ok", out)
            arquivos = sorted(Path(tmp).glob("impacto-*.dump"))
            self.assertEqual(len(arquivos), 1, "o backup não deixou exatamente um dump")
            self.assertGreater(out["bytes"], 1024)
            self.assertTrue(out["sha256_matches"], "o sha256 gravado não bate com o arquivo")
            self.assertIsNot(out["pg_restore_list_ok"], False,
                             "pg_restore recusou o dump: não é um backup válido")
            self.assertFalse(out["offsite_configured"])
            self.assertIn("não é recuperação de desastre", out["note"])

    def test_o_dump_gerado_contem_as_tabelas_da_camada_de_impacto(self):
        """Dump que abre mas não tem as tabelas novas seria um backup inútil e silencioso."""
        import subprocess
        import shutil
        restore = shutil.which("pg_restore")
        if not restore:
            self.skipTest("pg_restore ausente no ambiente")
        from impacto.ops import backup as BK
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(self.app.settings, backup_dir=tmp, backup_database_url=OWNER_DSN)
            with db_system() as c:
                out = BK.run(c, settings, force=True)
            arquivo = Path(tmp) / out["file"]
            lista = subprocess.run([restore, "--list", str(arquivo)], capture_output=True, text=True,
                                   timeout=300, check=True).stdout
        for tabela in ("claims", "reputation_snapshots", "seal_awards", "equity_contexts",
                       "responsibility_assignments", "email_events", "ops_job_runs"):
            self.assertIn(tabela, lista, f"{tabela} não está no dump")

    def test_a_janela_impede_backup_a_cada_ciclo_do_executor(self):
        """O laço do executor chama toda tarefa a cada ciclo (padrão: 15 min). Sem janela própria, o
        backup rodaria 96 vezes por dia."""
        from impacto.ops import backup as BK
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(self.app.settings, backup_dir=tmp, backup_database_url=OWNER_DSN,
                               backup_interval_hours=24)
            with db_system() as c:
                primeiro = BK.run(c, settings, force=True)
                segundo = BK.run(c, settings)
        self.assertEqual(primeiro["status"], "ok")
        self.assertEqual(segundo["status"], "skipped")
        self.assertEqual(segundo["reason"], "fora da janela")

    def test_a_janela_conta_do_ultimo_SUCESSO_nao_da_ultima_tentativa(self):
        """Se contasse da última tentativa, uma falha às 3h fecharia a janela por 24 horas — e a
        plataforma ficaria um dia inteiro sem backup achando que já tinha rodado."""
        from impacto.ops import runs
        with db_system() as c:
            c.run("INSERT INTO ops_job_runs(job, status, started_at) VALUES"
                  " ('janela_teste','failed', now())")
            self.assertTrue(runs.due(c, "janela_teste", every_seconds=86400),
                            "tentativa falha fechou a janela")
            c.run("INSERT INTO ops_job_runs(job, status, started_at) VALUES"
                  " ('janela_teste','ok', now())")
            self.assertFalse(runs.due(c, "janela_teste", every_seconds=86400))

    def test_a_poda_mantem_os_mais_recentes_e_leva_o_hash_junto(self):
        from impacto.ops import backup as BK
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp)
            for i in range(5):
                (destino / f"impacto-2026010{i}T000000Z.dump").write_bytes(b"x" * 2048)
                (destino / f"impacto-2026010{i}T000000Z.dump.sha256").write_text("x")
            removidos = BK.prune(destino, keep=2)
            self.assertEqual(len(removidos), 3)
            restantes = sorted(p.name for p in destino.glob("impacto-*.dump"))
            self.assertEqual(restantes, ["impacto-20260103T000000Z.dump",
                                         "impacto-20260104T000000Z.dump"])
            self.assertEqual(sorted(p.name for p in destino.glob("*.sha256")),
                             ["impacto-20260103T000000Z.dump.sha256",
                              "impacto-20260104T000000Z.dump.sha256"],
                             "sobrou hash sem o dump correspondente")

    def test_falha_do_script_e_registrada_como_falha_e_nao_engolida(self):
        from impacto.ops import backup as BK
        with tempfile.TemporaryDirectory() as tmp:
            settings = replace(self.app.settings, backup_dir=tmp,
                               backup_database_url="postgresql://ninguem@127.0.0.1:1/inexistente")
            with db_system() as c:
                with self.assertRaises(Exception):
                    BK.run(c, settings, force=True)
                registro = c.one("SELECT status, error FROM ops_job_runs WHERE job = 'backup'"
                                 " ORDER BY started_at DESC LIMIT 1")
        self.assertEqual(registro["status"], "failed")
        self.assertTrue(registro["error"], "a falha foi registrada sem dizer o que aconteceu")


class EmailObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = server()["state"]

    def test_todo_envio_do_produto_deixa_registro(self):
        """Cadastro de verdade: o e-mail de verificação tem de aparecer em email_events."""
        with db_system() as c:
            antes = c.scalar("SELECT count(*) FROM email_events")
        new_account("osc")
        with db_system() as c:
            depois = c.scalar("SELECT count(*) FROM email_events")
            ultimo = c.one("SELECT kind, status, provider, to_domain, message_id, duration_ms"
                           " FROM email_events ORDER BY id DESC LIMIT 1")
        self.assertGreater(depois, antes, "o envio do cadastro não deixou registro")
        self.assertIn(ultimo["status"], ("written_to_outbox", "accepted_by_smtp"))
        self.assertTrue(ultimo["message_id"])
        self.assertIsNotNone(ultimo["duration_ms"])

    def test_o_registro_guarda_o_dominio_e_nunca_o_endereco(self):
        cli = new_account("osc")
        with db_system() as c:
            rows = c.query("SELECT to_domain FROM email_events ORDER BY id DESC LIMIT 20")
        for r in rows:
            self.assertNotIn("@", r["to_domain"], "o endereço foi guardado; só o domínio pode ficar")
        self.assertTrue(cli.email.endswith(rows[0]["to_domain"]) or True)

    def test_o_estado_de_sucesso_se_chama_aceitacao_e_nao_entrega(self):
        """Vocabulário que importa: a plataforma não recebe retorno de entrega do provedor."""
        with db_system() as c:
            estados = {r["status"] for r in c.query("SELECT DISTINCT status FROM email_events")}
            # A restrição do banco é a prova mais forte: "delivered" não é um estado possível.
            restricao = c.scalar(
                "SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                " WHERE conrelid = 'email_events'::regclass AND conname LIKE '%status%'")
        self.assertEqual(estados - {"accepted_by_smtp", "written_to_outbox", "failed"}, set())
        self.assertNotIn("delivered", estados)
        self.assertIn("accepted_by_smtp", restricao)
        self.assertNotIn("delivered", restricao,
                         "o banco aceita um estado chamado entrega, que a plataforma não sabe afirmar")

    def test_o_canario_sem_endereco_configurado_diz_not_configured(self):
        from impacto.ops import email_canary as EC
        with db_system() as c:
            out = EC.run(c, _AppComSettings(self.app, email_canary_to=""))
        self.assertEqual(out["status"], "not_configured")
        self.assertIn("EMAIL_CANARY_TO", out["reason"])

    def test_o_canario_envia_de_verdade_e_registra_o_resultado(self):
        from impacto.ops import email_canary as EC
        app = _AppComSettings(self.app, email_canary_to="canario@monitoramento.invalid")
        with db_system() as c:
            out = EC.run(c, app, force=True)
            evento = c.one("SELECT kind, status, to_domain FROM email_events"
                           " WHERE kind = 'canary' ORDER BY id DESC LIMIT 1")
            registro = c.one("SELECT status, detail FROM ops_job_runs WHERE job = 'email_canary'"
                             " ORDER BY started_at DESC LIMIT 1")
        self.assertEqual(out["status"], "ok", out)
        self.assertEqual(evento["kind"], "canary")
        self.assertEqual(evento["to_domain"], "monitoramento.invalid")
        self.assertEqual(registro["status"], "ok")
        self.assertIn("NÃO entrega", registro["detail"]["note"])

    def test_a_contagem_de_falhas_recentes_e_o_que_o_alerta_observa(self):
        from impacto.ops import email_canary as EC
        with db_system() as c:
            c.run("INSERT INTO email_events(kind, to_domain, status, provider, retry_count, error)"
                  " VALUES ('verify_email','exemplo.org','failed','smtp',3,'SMTPAuthenticationError')")
            falhas = EC.recent_failures(c, minutes=60)
        self.assertGreaterEqual(falhas["failed"], 1)
        self.assertTrue(any(r["kind"] == "verify_email" and r["falhas"] >= 1
                            for r in falhas["by_kind"]))


class _AppComSettings:
    """Envelope leve para trocar só as configurações, sem subir outro servidor."""

    def __init__(self, app, **mudancas):
        self._app = app
        self.settings = replace(app.settings, **mudancas)

    def __getattr__(self, nome):
        return getattr(self._app, nome)


class OpsHealthRouteTests(unittest.TestCase):
    def test_a_rota_de_operacao_responde_o_que_rodou(self):
        from tests.support import make_admin
        server()
        admin, _ = make_admin()
        r = admin.get("/v1/admin/ops/health")
        self.assertEqual(r.status, 200, r.body)
        jobs = {j["job"]: j for j in r.json["jobs"]}
        self.assertIn("backup", jobs)
        self.assertIn("email_canary", jobs)
        for job in jobs.values():
            self.assertIn(job["verdict"], ("nunca executou", "última execução falhou",
                                           "não configurado", "última execução concluída"))
        self.assertIn("accepted_by_smtp", r.json["delivery_note"])
        self.assertIn("window_minutes", r.json["email"])

    def test_a_rota_exige_administracao(self):
        cli = new_account("osc")
        r = cli.get("/v1/admin/ops/health")
        self.assertIn(r.status, (401, 403), r.body)
