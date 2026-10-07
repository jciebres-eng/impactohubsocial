"""Portão de observabilidade da v0.23.0: o evento detectado chega a alguém.

O DEFEITO QUE ESTES TESTES FECHAM

A auditoria independente desta versão encontrou o pior tipo de lacuna de segurança: a que parece
resolvida. A plataforma DETECTA reuso de refresh token — o sinal mais forte de roubo de sessão que
ela sabe produzir —, revoga a família inteira de sessões, grava o evento na trilha imutável e
notifica o titular da conta. E ninguém da operação é avisado. O evento mais grave do sistema
esperava que alguém abrisse uma tela.

O mesmo vale para o backup: `scripts/restore_test.sh` é o ativo de recuperação mais forte do
repositório — confere o sha256, restaura num banco descartável, verifica as cadeias de hash e
recusa um restore que traga estado que não deveria existir. Nada o executava. É literalmente o
defeito que `ops/backup.py` critica na primeira linha: "script que ninguém executa não é backup".

Cada teste aqui é uma catraca: prova que a métrica sai do ponto de estrangulamento, que o alerta lê
uma série que existe de fato, e que o CI roda o que diz rodar.
"""
from __future__ import annotations

import re
import unittest

import yaml

from tests.support import Client, ROOT, make_staff, new_account

ALERTS = ROOT / "infra" / "monitoring" / "alerts.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
FONTES = sorted((ROOT / "backend" / "impacto").rglob("*.py"))
CODIGO = "\n".join(f.read_text(encoding="utf-8") for f in FONTES)


def _metricas() -> dict[str, float]:
    """Lê /metrics e devolve {série: valor}. A série inclui os rótulos, como o Prometheus a vê."""
    corpo = Client().get("/metrics").body.decode("utf-8")
    fora = {}
    for linha in corpo.splitlines():
        if linha.startswith("#") or " " not in linha:
            continue
        serie, _, valor = linha.rpartition(" ")
        try:
            fora[serie] = float(valor)
        except ValueError:
            continue
    return fora


def _valor(nome: str, **rotulos) -> float:
    """Soma as séries de `nome` que casam com os rótulos pedidos."""
    alvo = _metricas()
    total = 0.0
    for serie, v in alvo.items():
        if not serie.startswith(nome + "{") and serie != nome:
            continue
        if all(f'{k}="{val}"' in serie for k, val in rotulos.items()):
            total += v
    return total


class SecurityMetricsReachTheAlertsTests(unittest.TestCase):
    """O contador de segurança sai do ponto de estrangulamento, não de cada chamador."""

    def test_every_security_action_is_produced_by_code(self):
        """Nome em SECURITY_ACTIONS que ninguém emite é o defeito de LOGIN_MAX_ATTEMPTS.

        Configuração que parece ligada e não tem produtor engana quem lê o conjunto e, pior, engana
        quem escreve o alerta: a regra fica verde para sempre porque a série nunca nasce.
        """
        from impacto.services.audit import SECURITY_ACTIONS
        orfas = []
        for acao in sorted(SECURITY_ACTIONS):
            # Produtor direto: a ação aparece como literal. Produtor por f-string: `auth.session_*`
            # nasce de `action=f"auth.{motivo}"`, então o literal presente é o sufixo em `motivo`.
            sufixo = acao.split(".", 1)[1]
            if f'"{acao}"' in CODIGO:
                continue
            if 'action=f"auth.{motivo}"' in CODIGO and f'"{sufixo}"' in CODIGO:
                continue
            orfas.append(acao)
        self.assertEqual([], orfas, f"ações sem produtor no código: {orfas}")

    def test_the_f_string_actions_still_match_the_declared_names(self):
        """`action=f"auth.{motivo}"` é frágil: renomear `motivo` apaga a série sem erro nenhum."""
        self.assertIn('"session_too_old"', CODIGO)
        self.assertIn('"session_idle"', CODIGO)
        self.assertIn('action=f"auth.{motivo}"', CODIGO)

    def test_a_failed_login_moves_the_security_counter(self):
        """Prova de ponta a ponta: o evento de segurança gera série, não só linha na trilha."""
        c = new_account()
        antes = _valor("impacto_security_events_total", action="auth.login_failed")
        r = c.post("/v1/auth/login", {"email": c.email, "password": "senha_errada_de_proposito"})
        self.assertEqual(401, r.status)
        self.assertGreater(_valor("impacto_security_events_total", action="auth.login_failed"), antes,
                           "login falho não incrementou impacto_security_events_total")

    def test_a_denied_privileged_access_moves_its_own_counter(self):
        """A recusa é gravada em `privileged_access_log`, que não passa por `record()`.

        Por isso o contador é emitido no próprio `log_privileged` — para o alerta ler uma série só.
        """
        from impacto.services.audit import DENIED_PRIVILEGED_ACTION
        c = make_staff("support")   # papel de conteúdo: nenhuma permissão financeira
        antes = _valor("impacto_security_events_total", action=DENIED_PRIVILEGED_ACTION)
        r = c.get("/v1/controladoria/summary")
        self.assertEqual(403, r.status, "um papel de conteúdo não deveria alcançar a controladoria")
        self.assertGreater(_valor("impacto_security_events_total", action=DENIED_PRIVILEGED_ACTION), antes,
                           "entrada privilegiada recusada não incrementou o contador")

    def test_every_audit_event_feeds_the_category_counter(self):
        """`impacto_audit_events_total{categoria}` existe para que um evento NOVO já nasça visível."""
        c = new_account()
        c.post("/v1/auth/login", {"email": c.email, "password": "outra_senha_errada"})
        series = [s for s in _metricas() if s.startswith("impacto_audit_events_total{")]
        self.assertTrue(series, "nenhuma série de impacto_audit_events_total foi emitida")
        self.assertTrue(any('categoria="auth"' in s for s in series), series[:5])

    def test_the_counter_is_emitted_at_the_chokepoint_not_at_the_callers(self):
        """319 chamadas de auditoria; uma emissão. Emitir em cada chamador deixaria eventos fora."""
        emissoes = CODIGO.count('METRICS.inc("impacto_security_events_total"')
        self.assertEqual(2, emissoes,
                         "esperado exatamente 2 pontos de emissão (services/audit.py e core/access.py); "
                         f"encontrados {emissoes} — espalhar a emissão reabre o defeito")


class RedactionGoesAllTheWayDownTests(unittest.TestCase):
    """`_clean` só olhava o primeiro nível. A trilha é append-only: o que entra não sai."""

    def test_a_nested_secret_is_redacted(self):
        from impacto.services.audit import _clean
        limpo = _clean({"webhook": {"secret": "s3cr3t", "url": "https://x"}})
        self.assertEqual("[REDACTED]", limpo["webhook"]["secret"])
        self.assertEqual("https://x", limpo["webhook"]["url"])

    def test_a_secret_inside_a_list_of_objects_is_redacted(self):
        from impacto.services.audit import _clean
        limpo = _clean({"conexoes": [{"api_key": "k1"}, {"api_key": "k2"}]})
        self.assertEqual(["[REDACTED]", "[REDACTED]"], [i["api_key"] for i in limpo["conexoes"]])

    def test_the_name_variants_are_caught_not_just_the_exact_words(self):
        """A lista exata pegava `token`; `refresh_token` e `client_secret` passavam inteiros."""
        from impacto.services.audit import _clean
        for chave in ("refresh_token", "access_token", "client_secret", "api_key", "apiKey",
                      "Authorization", "Cookie", "private_key", "senha_atual", "session_token"):
            with self.subTest(chave=chave):
                self.assertEqual("[REDACTED]", _clean({chave: "vazou"})[chave])

    def test_a_pathological_depth_is_truncated_instead_of_recursing_forever(self):
        from impacto.services.audit import _clean
        fundo: dict = {"fim": 1}
        for _ in range(40):
            fundo = {"n": fundo}
        texto = str(_clean(fundo))
        self.assertIn("[TRUNCADO]", texto)

    def test_the_secret_never_reaches_the_immutable_table(self):
        """O teste que importa: ler a linha de volta do banco e não encontrar o segredo."""
        from impacto.services.audit import record
        from tests.support import db_system
        c = new_account()
        with db_system() as conn:
            record(conn, org_id=c.org_id, actor=None, action="teste.redacao_aninhada",
                   object_type="teste", object_id="1",
                   payload={"integracao": {"credential": {"client_secret": "NAO_PODE_APARECER"}}})
            guardado = conn.scalar("SELECT payload::text FROM audit_events"
                                   " WHERE action = 'teste.redacao_aninhada' AND org_id = $1"
                                   " ORDER BY seq DESC LIMIT 1", c.org_id)
        self.assertIsNotNone(guardado)
        self.assertNotIn("NAO_PODE_APARECER", guardado)
        self.assertIn("REDACTED", guardado)


class EveryAlertReadsASeriesThatExistsTests(unittest.TestCase):
    """Um alerta que lê série inexistente fica verde para sempre. É pior que não ter alerta."""

    @classmethod
    def setUpClass(cls):
        cls.regras = [r for g in yaml.safe_load(ALERTS.read_text(encoding="utf-8"))["groups"]
                      for r in g["rules"]]
        cls.emitidas = set(re.findall(r'METRICS\.(?:inc|observe|set)\("([a-z_]+)"', CODIGO))

    def test_every_metric_in_an_alert_is_emitted_somewhere(self):
        externas = {"up"}   # série do próprio Prometheus (scrape), não da aplicação
        faltando = []
        for r in self.regras:
            for nome in re.findall(r"\b(impacto_[a-z_]+|up)\b", r["expr"]):
                base = nome[: -len("_bucket")] if nome.endswith("_bucket") else nome
                if base not in self.emitidas and base not in externas:
                    faltando.append((r["alert"], nome))
        self.assertEqual([], faltando, f"alertas lendo série que nada emite: {faltando}")

    def test_every_action_label_in_an_alert_is_a_declared_security_action(self):
        """Rótulo digitado errado no alerta é indistinguível de "nunca aconteceu"."""
        from impacto.services.audit import DENIED_PRIVILEGED_ACTION, SECURITY_ACTIONS
        conhecidas = set(SECURITY_ACTIONS) | {DENIED_PRIVILEGED_ACTION}
        desconhecidas = []
        for r in self.regras:
            for valor in re.findall(r'action=~?"([^"]+)"', r["expr"]):
                for a in valor.split("|"):
                    if a not in conhecidas:
                        desconhecidas.append((r["alert"], a))
        self.assertEqual([], desconhecidas, f"ações desconhecidas em alerta: {desconhecidas}")

    def test_the_strongest_session_theft_signal_has_a_page_level_alert(self):
        """A lacuna nomeada pela auditoria. Sem janela de tolerância: um reuso já é indício."""
        reuso = [r for r in self.regras if "refresh_reuse_detected" in r["expr"]]
        self.assertEqual(1, len(reuso), "nenhum alerta para reuso de refresh token")
        self.assertEqual("page", reuso[0]["labels"]["severity"])
        self.assertEqual("0m", str(reuso[0]["for"]), "tolerar reuso de token por minutos não faz sentido")

    def test_a_job_that_stops_running_is_also_an_alert(self):
        """Tarefa que falha emite falha. Tarefa que PARA não emite nada — silêncio também é defeito."""
        ausencia = [r for r in self.regras if "absent(" in r["expr"]]
        self.assertTrue(ausencia, "nenhum alerta cobre a ausência de série (tarefa que parou de rodar)")

    def test_the_backup_alert_names_a_job_that_the_code_actually_runs(self):
        from impacto.services.audit import SECURITY_ACTIONS  # noqa: F401  (mantém a importação viva)
        nomes = set(re.findall(r'runs\.record\(\s*\w+\s*,\s*"([a-z0-9_]+)"', CODIGO))
        nomes |= set(re.findall(r'record\(\s*\w+\s*,\s*"([a-z0-9_]+)"\)', CODIGO))
        for r in self.regras:
            for job in re.findall(r'job="([a-z0-9_]+)"', r["expr"]):
                if job == "impacto":
                    continue   # rótulo de scrape do Prometheus, não nome de tarefa
                with self.subTest(alerta=r["alert"], job=job):
                    self.assertIn(job, nomes, f"alerta cita tarefa '{job}' que nenhum código abre")

    def test_every_page_level_alert_says_what_to_do(self):
        """Acordar alguém às 3h sem dizer o que olhar é passar o problema adiante."""
        sem_texto = [r["alert"] for r in self.regras
                     if r.get("labels", {}).get("severity") == "page"
                     and not (r.get("annotations") or {}).get("summary")
                     and r["alert"] != "ApiFora"]   # "API fora" é autoexplicativo
        self.assertEqual([], sem_texto, f"alertas de página sem orientação: {sem_texto}")


class TheCiRunsWhatItClaimsToRunTests(unittest.TestCase):
    """Script que ninguém executa não é backup. Varredura que não roda não é varredura."""

    @classmethod
    def setUpClass(cls):
        cls.ci = CI.read_text(encoding="utf-8")

    def test_there_is_a_secret_scan_in_the_pipeline(self):
        """O fail-fast de `config.py` protege o BOOT. Não protege o histórico do git."""
        self.assertIn("gitleaks", self.ci,
                      "nenhuma varredura de segredo no CI: um segredo commitado por engano fica no histórico")
        self.assertIn("fetch-depth: 0", self.ci,
                      "varredura sem histórico completo só olha o último commit")

    def test_the_restore_test_is_actually_executed(self):
        self.assertIn("scripts/restore_test.sh", self.ci,
                      "restore_test.sh é o ativo de recuperação mais forte do repositório e nada o chama")
        self.assertIn("scripts/backup.sh", self.ci, "restaurar sem gerar o dump no mesmo ciclo não prova o ciclo")

    def test_the_restore_test_is_proven_against_a_tampered_dump(self):
        """Conferir o hash de um arquivo que ninguém alterou prova pouco.

        O CI adultera o dump de propósito e exige que a restauração FALHE. Sem isto, a verificação
        de integridade poderia estar desligada e o pipeline seguiria verde.
        """
        self.assertIn("adulterado", self.ci,
                      "o ciclo de restauração não prova que recusa um dump adulterado")

    def test_the_restore_runs_against_the_real_roles(self):
        """Restaurar como superusuário esconde justamente os erros de permissão do restore real."""
        self.assertIn("dev_reset_db.sh", self.ci)
        self.assertIn("impacto_owner", self.ci)

    def test_the_dependency_tree_that_gets_audited_is_the_one_that_gets_built(self):
        """`npm audit` sem lockfile audita uma árvore que pode não ser a de produção."""
        self.assertIn("package-lock.json", self.ci)
        self.assertIn("npm ci", self.ci)


if __name__ == "__main__":
    unittest.main()
