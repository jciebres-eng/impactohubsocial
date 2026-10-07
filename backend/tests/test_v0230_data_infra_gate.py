"""Gate 6 do pacote de execução: dados e infraestrutura.

O ITEM QUE NÃO TINHA TESTE, E É O QUE MAIS IMPORTA

`/readyz` tinha um teste: o do caminho felizu, que confere `status == "ready"`. O ramo que decide se
a plataforma sobrevive a um incidente é o OUTRO — o 503. Uma sonda de prontidão que nunca devolve 503
é pior que nenhuma: o orquestrador acha que a instância está boa, manda tráfego, e cada requisição
morre no banco. Então aqui se exercita o 503 nos dois motivos que o produto declara (banco fora,
migração pendente) e se confere a separação entre prontidão e vivacidade.

A distinção não é formalidade. `/healthz` responder 200 com o banco fora é CORRETO: reiniciar o
processo não ressuscita o banco, e um orquestrador que mata o processo por isso só troca uma
instância ruim por outra, mais devagar. Prontidão tira do balanceador; vivacidade reinicia. Confundir
as duas transforma uma queda de banco numa tempestade de reinícios.

O QUE É CONFERIDO AQUI E O QUE É CONFERIDO FORA

Migração do zero, semente, backup, restauração em banco limpo e integridade pós-restauração foram
EXECUTADOS nesta rodada contra PostgreSQL 16.15 real, e o registro está em
`docs/execution/DATA_INFRA_GATE.md` com os números. Não se repetem aqui porque criar banco, dumpar e
restaurar dentro da suíte a tornaria lenta e frágil; o que mora aqui é o que precisa rodar em CADA
execução para não regredir.
"""
from __future__ import annotations

import hashlib
import unittest
from pathlib import Path
from unittest import mock

from tests.support import Client, ROOT, db_system, server


class ReadinessFailsWhenADependencyIsMissingTests(unittest.TestCase):
    """Os dois motivos de 503 que o produto declara, exercitados."""

    @classmethod
    def setUpClass(cls):
        server()

    def test_ready_is_ready_when_everything_is_in_place(self):
        r = Client().get("/readyz")
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(r.json["status"], "ready")
        # A prontidão nomeia cada dependência: quem lê o 503 precisa saber O QUE falta.
        for dependencia in ("database", "storage", "antivirus", "ai", "billing", "mail"):
            self.assertIn(dependencia, r.json, f"prontidão não declara {dependencia}")

    def test_a_pending_migration_makes_readiness_fail_with_503(self):
        """Subir código que espera uma coluna que a migração ainda não criou é o caminho curto para
        corrupção. A prontidão compara o que o CÓDIGO espera com o que o BANCO tem."""
        from impacto.db import migrate
        reais = migrate._files()
        falsa = Path(str(reais[-1].parent / "9999_migracao_que_o_banco_nao_tem.sql"))
        with mock.patch.object(migrate, "_files", return_value=[*reais, falsa]):
            r = Client().get("/readyz")
        self.assertEqual(r.status, 503, r.body)
        self.assertEqual(r.json["status"], "unavailable")
        self.assertIn("9999_migracao_que_o_banco_nao_tem", str(r.json["pending_migrations"]))

    def test_a_dead_database_makes_readiness_fail_with_503_and_says_so(self):
        from impacto.db import migrate
        with mock.patch.object(migrate, "_files", side_effect=OSError("banco inalcançável")):
            r = Client().get("/readyz")
        self.assertEqual(r.status, 503, r.body)
        self.assertEqual(r.json["database"], "down")

    def test_liveness_stays_up_while_readiness_is_down(self):
        """Reiniciar o processo não ressuscita o banco. Vivacidade e prontidão respondem perguntas
        diferentes, e `/healthz` não pode depender do banco — senão uma queda de banco vira
        tempestade de reinícios."""
        from impacto.db import migrate
        with mock.patch.object(migrate, "_files", side_effect=OSError("banco inalcançável")):
            self.assertEqual(Client().get("/readyz").status, 503)
            vivo = Client().get("/healthz")
        self.assertEqual(vivo.status, 200, vivo.body)
        self.assertEqual(vivo.json["status"], "ok")

    def test_liveness_does_not_touch_the_database_at_all(self):
        """A conferência estrutural, porque a de comportamento passa por acidente se o banco está no ar."""
        fonte = (ROOT / "backend" / "impacto" / "app.py").read_text(encoding="utf-8")
        corpo = fonte[fonte.index("async def healthz"):fonte.index("def _ready()")]
        for proibido in ("pool", "tx(", "query(", "state.db"):
            self.assertNotIn(proibido, corpo, f"healthz toca o banco ({proibido}): deixa de ser vivacidade")


class TheMigrationsAreForwardOnlyAndFingerprintedTests(unittest.TestCase):
    """Migração aplicada que muda de conteúdo é a falha silenciosa mais cara que existe."""

    @classmethod
    def setUpClass(cls):
        server()

    def test_every_applied_migration_matches_the_file_sha256(self):
        from impacto.db import migrate
        arquivos = {f.stem: f for f in migrate._files()}
        with db_system() as c:
            aplicadas = c.query("SELECT version, checksum FROM schema_migrations ORDER BY version")
        self.assertTrue(aplicadas, "nenhuma migração registrada")
        for linha in aplicadas:
            with self.subTest(linha["version"]):
                f = arquivos.get(linha["version"])
                self.assertIsNotNone(f, f"{linha['version']} está no banco e não existe em disco")
                atual = hashlib.sha256(f.read_bytes()).hexdigest()
                self.assertEqual(linha["checksum"], atual,
                                 f"{linha['version']} mudou de conteúdo DEPOIS de aplicada")

    def test_the_versions_are_sequential_with_no_hole_and_no_duplicate(self):
        from impacto.db import migrate
        numeros = sorted(int(f.stem.split("_")[0]) for f in migrate._files())
        self.assertEqual(len(numeros), len(set(numeros)), "número de migração duplicado")
        self.assertEqual(numeros, list(range(numeros[0], numeros[0] + len(numeros))),
                         f"buraco na sequência de migrações: {numeros}")

    #: Remoções DECLARADAS, cada uma com o motivo e a prova de que o dado foi preservado antes.
    #: A lista é a trava: uma remoção NOVA reprova até que alguém a inscreva aqui deliberadamente,
    #: o que obriga a pensar em migração de dado em vez de descobrir a perda em produção.
    REMOCOES_DECLARADAS: dict[str, str] = {
        "0013_v0150_core_product.sql:DROP TABLE sdg_goals":
            "consolidação de duas tabelas de ODS numa: as linhas 15-16 da mesma migração copiam "
            "code/name_en/color_hex de sdg_goals para ods_goals ANTES da remoção, e o gatilho de "
            "validação de impact_tags é recriado apontando para ods_goals. Nenhum dado se perde.",
    }

    def test_no_migration_drops_a_table_or_column_without_a_declared_reason(self):
        """Avanço-somente não é só a ordem dos arquivos: é não destruir dado em silêncio.

        Uma remoção legítima existe (consolidar duas tabelas numa). O que não pode existir é a
        remoção que ninguém declarou — e a primeira versão deste teste reprovou a declarada porque
        o motivo estava num comentário na MESMA linha do comando, depois do ponto e vírgula.
        """
        from impacto.db import migrate
        achados = []
        for f in migrate._files():
            for linha in f.read_text(encoding="utf-8").splitlines():
                antes_do_comentario = linha.split("--")[0]
                alto = antes_do_comentario.upper()
                destrutiva = (("DROP TABLE" in alto and "IF EXISTS" not in alto)
                              or "DROP COLUMN" in alto)
                if not destrutiva:
                    continue
                comando = " ".join(antes_do_comentario.replace(";", " ").split())
                chave = f"{f.name}:{comando}"
                if chave not in self.REMOCOES_DECLARADAS:
                    achados.append(chave)
        self.assertEqual(achados, [],
                         f"remoção destrutiva não declarada em REMOCOES_DECLARADAS: {achados}")

    def test_every_declared_removal_still_exists_and_carries_its_reason(self):
        """A lista de exceções não pode envelhecer: uma entrada que não corresponde a nenhuma
        migração real é ruído que faz a próxima pessoa confiar numa trava que não trava nada."""
        from impacto.db import migrate
        por_nome = {f.name: f.read_text(encoding="utf-8") for f in migrate._files()}
        for chave, motivo in self.REMOCOES_DECLARADAS.items():
            arquivo, comando = chave.split(":", 1)
            with self.subTest(chave):
                self.assertIn(arquivo, por_nome, f"{arquivo} não existe mais")
                self.assertIn(comando, por_nome[arquivo], f"{comando} não está mais em {arquivo}")
                self.assertGreater(len(motivo), 80, "motivo curto demais para ser auditável")


class RowLevelSecurityCoversEveryTableTests(unittest.TestCase):
    """Os números que o release afirma, conferidos contra o banco e não contra a documentação."""

    @classmethod
    def setUpClass(cls):
        server()

    #: `schema_migrations` é a única tabela sem RLS, e o motivo é escrito: ela é lida pelo
    #: `/readyz` e pelo migrador antes de existir qualquer sessão de organização.
    SEM_RLS = {"schema_migrations"}

    def test_every_table_but_the_declared_exception_has_rls_enabled(self):
        with db_system() as c:
            sem = {r["tablename"] for r in c.query(
                "SELECT t.tablename FROM pg_tables t JOIN pg_class c ON c.relname = t.tablename"
                " WHERE t.schemaname = 'public' AND NOT c.relrowsecurity")}
        self.assertEqual(sem, self.SEM_RLS, f"tabelas sem RLS fora da exceção declarada: {sem - self.SEM_RLS}")

    def test_every_table_with_rls_actually_has_a_policy(self):
        """RLS ligada sem política NEGA tudo — e um `GRANT` largo pareceria funcionar até alguém ler."""
        with db_system() as c:
            orfas = {r["tablename"] for r in c.query(
                "SELECT t.tablename FROM pg_tables t JOIN pg_class c ON c.relname = t.tablename"
                " LEFT JOIN pg_policies p ON p.tablename = t.tablename AND p.schemaname = 'public'"
                " WHERE t.schemaname = 'public' AND c.relrowsecurity AND p.policyname IS NULL")}
        self.assertEqual(orfas, {"chain_heads"},
                         "tabela com RLS e sem política fora da exceção conhecida (chain_heads)")

    def test_force_row_level_security_is_nowhere(self):
        """`FORCE ROW LEVEL SECURITY` aplica a política ao DONO da tabela — que é quem roda `pg_dump`.

        Ligar isso transforma o backup num dump vazio que parece ter funcionado. É a armadilha mais
        cara deste esquema e está escrita em ADR: nenhuma tabela pode tê-la.
        """
        with db_system() as c:
            forcadas = {r["relname"] for r in c.query(
                "SELECT c.relname FROM pg_class c JOIN pg_tables t ON t.tablename = c.relname"
                " WHERE t.schemaname = 'public' AND c.relforcerowsecurity")}
        self.assertEqual(forcadas, set(),
                         f"FORCE RLS ligada em {forcadas}: o backup do dono sairia vazio")

    def test_the_append_only_tables_refuse_update_and_delete(self):
        with db_system() as c:
            protegidas = c.scalar(
                "SELECT count(DISTINCT c.relname) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
                " JOIN pg_proc p ON p.oid = t.tgfoid WHERE p.proname = 'forbid_mutation'")
            sem_truncate = c.scalar(
                "SELECT count(DISTINCT c.relname) FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
                " JOIN pg_proc p ON p.oid = t.tgfoid WHERE p.proname = 'forbid_truncate'")
        self.assertGreaterEqual(protegidas, 40, f"só {protegidas} tabelas append-only")
        # `forbid_mutation` é gatilho de LINHA e não vê TRUNCATE: sem o par, apagar a trilha de
        # auditoria inteira continuaria possível com um comando.
        self.assertGreaterEqual(sem_truncate, 6, f"só {sem_truncate} tabelas protegidas contra TRUNCATE")


class TheHashChainsVerifyAfterEveryWriteTests(unittest.TestCase):
    """As quatro cadeias de hash do produto, verificadas pela função do próprio banco."""

    @classmethod
    def setUpClass(cls):
        server()

    def test_the_audit_chain_verifies_for_every_organization_that_has_events(self):
        with db_system() as c:
            quebradas = c.query(
                "SELECT o.org_id::text AS org_id FROM (SELECT DISTINCT org_id FROM audit_events) o"
                " CROSS JOIN LATERAL audit_verify(o.org_id) v WHERE NOT v.valid")
        self.assertEqual(quebradas, [], f"cadeia de auditoria quebrada: {quebradas}")

    def test_the_ledger_chain_verifies_for_every_project(self):
        with db_system() as c:
            quebradas = c.query("SELECT p.id::text AS id FROM projects p"
                                " CROSS JOIN LATERAL ledger_verify(p.id) v WHERE NOT v.valid")
        self.assertEqual(quebradas, [], f"cadeia do ledger quebrada: {quebradas}")

    def test_all_four_chains_have_a_verify_function_and_a_head(self):
        with db_system() as c:
            funcoes = {r["proname"] for r in c.query(
                "SELECT proname FROM pg_proc WHERE proname IN"
                " ('audit_verify','ledger_verify','value_verify','trust_verify')")}
        self.assertEqual(funcoes, {"audit_verify", "ledger_verify", "value_verify", "trust_verify"},
                         f"faltam funções de verificação: {funcoes}")
