"""v0.18.1 — caminho de atualização v0.17.0 → v0.18.x, checksum e falha no meio (FASE 4).

Criar o banco do zero prova que o esquema é coerente. **Não** prova que quem já está na v0.17.0
consegue subir — e é esse o caso de quem já tem dado. Este arquivo prepara um banco na última
migration da v0.17.0, coloca dado dentro, aplica as oito migrations seguintes e confere:

* o dado anterior continua lá, sem reescrita;
* as estruturas novas chegam COM RLS e política;
* a trava de linha de base sem fonte (0025) não quebra o dado que já existia;
* `--check` fica limpo depois;
* migration já aplicada e ALTERADA é recusada (forward-only);
* migration que falha no meio **não deixa metade aplicada**.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import unittest
import uuid

from tests.support import ADMIN_URL, APP_PW, HOST, OWNER_PW, PORT, ROOT

DB = f"impacto_v0181_upgrade_{os.getpid()}"
OWNER_DSN = f"host={HOST} port={PORT} dbname={DB} user=impacto_owner password={OWNER_PW}"

#: Última migration de cada versão entregue.
V0170 = "0024_v0170_privacy_hardening"
V0180_TABLES = ("equity_contexts", "equity_denominators", "claims", "claim_checks",
                "reputation_snapshots", "seal_awards", "responsibility_assignments",
                "territories", "impact_frameworks", "materiality_assessments")


def psql(*args: str) -> str:
    return subprocess.run(["psql", ADMIN_URL, "-v", "ON_ERROR_STOP=1", "-q", "-tA", *args],
                          check=True, capture_output=True, text=True).stdout


class UpgradeFromV0170Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from impacto.db.migrate import migrate
        from impacto.db.pq import Connection
        psql("-c", f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
        subprocess.run(["psql", ADMIN_URL, "-v", "ON_ERROR_STOP=1", "-q", "-v", f"db={DB}", "-f",
                        str(ROOT / "infra/db/bootstrap.sql")], check=True, capture_output=True,
                       text=True)
        psql("-c", f"ALTER ROLE impacto_owner PASSWORD '{OWNER_PW}';"
                   f" ALTER ROLE impacto_app PASSWORD '{APP_PW}';")
        cls.Connection = Connection
        cls.migrate = staticmethod(migrate)
        # 1. banco na v0.17.0
        cls.migrate(OWNER_DSN, upto=V0170, log=lambda *_: None)
        c = Connection(OWNER_DSN)
        cls.conn = c
        # 2. dado dentro, pelo caminho do dono (é um banco "de produção" simulado)
        cls.org = c.scalar(
            "INSERT INTO organizations(kind, legal_name, cnpj, uf, compliance_status)"
            " VALUES ('osc','OSC que já estava na v0.17.0','11222333000181','MT','approved')"
            " RETURNING id::text")
        cls.user = c.scalar(
            "INSERT INTO users(email, full_name, password_hash, status, email_verified_at)"
            " VALUES ($1,'Pessoa Anterior','x', 'active', now()) RETURNING id::text",
            f"antes-{uuid.uuid4().hex[:8]}@teste.org")
        c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner')",
              cls.user, cls.org)
        cls.project = c.scalar(
            "INSERT INTO projects(org_id, title, summary, problem, objectives, territory, causes,"
            " beneficiaries_count, budget_total_cents, status, created_by)"
            " VALUES ($1,'Projeto anterior à v0.18.0','Resumo do projeto que já existia.',"
            " 'Problema declarado antes da atualização, com extensão suficiente.',"
            " 'Objetivos declarados antes da atualização, com extensão suficiente.',"
            " 'BR-MT-5105259', ARRAY['educacao'], 120, 500000, 'published', $2)"
            " RETURNING id::text", cls.org, cls.user)
        ind = c.scalar("SELECT id::text FROM indicator_catalog WHERE org_id IS NULL LIMIT 1")
        # Indicador COM linha de base e SEM fonte: é o estado que a 0025 passa a recusar em
        # escrita nova. A atualização não pode falhar nem apagar o que já estava.
        cls.indicator = c.scalar(
            "INSERT INTO project_indicators(project_id, org_id, indicator_id, baseline, target)"
            " VALUES ($1,$2,$3,10,100) RETURNING id::text", cls.project, cls.org, ind)

    @classmethod
    def tearDownClass(cls):
        try:
            cls.conn.close()
        except Exception:
            pass
        psql("-c", f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')

    def test_a_the_database_starts_on_v0170(self):
        """Nome com prefixo: os métodos rodam em ordem alfabética e este tem de ser o primeiro."""
        from impacto.db.migrate import status
        st = status(self.conn)
        self.assertIn(V0170, st["applied"])
        self.assertEqual(st["changed"], [])
        self.assertTrue(st["pending"], "não há o que atualizar: o cenário não vale")
        faltando = [t for t in V0180_TABLES
                    if not self.conn.scalar("SELECT to_regclass($1) IS NOT NULL", t)]
        self.assertEqual(sorted(faltando), sorted(V0180_TABLES),
                         "tabela da v0.18.0 já existe num banco que deveria estar na v0.17.0")

    def test_b_the_incremental_migration_applies_cleanly(self):
        aplicadas = self.migrate(OWNER_DSN, log=lambda *_: None)
        self.assertGreaterEqual(len(aplicadas), 8, aplicadas)
        self.assertIn("0032_v0180_fk_index", aplicadas)
        from impacto.db.migrate import status
        st = status(self.conn)
        self.assertEqual((st["pending"], st["changed"]), ([], []))

    def test_c_the_data_that_existed_before_is_intact(self):
        row = self.conn.one("SELECT title, beneficiaries_count, status FROM projects WHERE id = $1",
                            self.project)
        self.assertEqual(row["title"], "Projeto anterior à v0.18.0")
        self.assertEqual(row["beneficiaries_count"], 120)
        self.assertEqual(row["status"], "published")
        self.assertTrue(self.conn.scalar("SELECT count(*) FROM memberships WHERE org_id = $1",
                                         self.org))

    def test_d_the_baseline_without_source_survives_and_becomes_countable(self):
        """A trava nova vale para escrita NOVA; o passivo antigo fica legível numa visão.

        Apagar ou corrigir sozinho a linha de base sem fonte seria pior: a plataforma estaria
        inventando a fonte. A migration deixa o dado como está e a visão
        `project_baselines_without_source` torna a dívida contável.
        """
        ainda = self.conn.one("SELECT baseline::float AS baseline, baseline_source"
                              " FROM project_indicators WHERE id = $1", self.indicator)
        self.assertEqual(ainda["baseline"], 10.0)
        self.assertIsNone(ainda["baseline_source"])
        contado = self.conn.scalar(
            "SELECT count(*) FROM project_baselines_without_source WHERE project_id = $1",
            self.project)
        self.assertEqual(contado, 1, "a dívida antiga não aparece na visão que a conta")
        # e a escrita nova é recusada
        ind2 = self.conn.scalar("SELECT id::text FROM indicator_catalog WHERE org_id IS NULL"
                                "   AND id <> (SELECT indicator_id FROM project_indicators"
                                "              WHERE id = $1) LIMIT 1", self.indicator)
        with self.assertRaises(Exception) as ctx:
            self.conn.run("INSERT INTO project_indicators(project_id, org_id, indicator_id,"
                          " baseline) VALUES ($1,$2,$3,50)", self.project, self.org, ind2)
        self.assertIn("linha de base exige fonte", str(ctx.exception))

    def test_e_every_new_table_arrived_with_rls_and_policy(self):
        sem_rls, sem_politica = [], []
        for t in V0180_TABLES:
            if not self.conn.scalar("SELECT relrowsecurity FROM pg_class WHERE relname = $1"
                                    "   AND relkind = 'r'", t):
                sem_rls.append(t)
            if not self.conn.scalar("SELECT count(*) FROM pg_policies WHERE tablename = $1", t):
                sem_politica.append(t)
        self.assertEqual((sem_rls, sem_politica), ([], []))

    def test_f_the_new_functions_exist_after_the_upgrade(self):
        for fn in ("claim_status", "seal_evaluate", "app_award_seal", "app_record_reputation",
                   "responsible_now", "app_claim_invited", "materiality_matrix",
                   "territory_profile", "dispute_status", "seal_status"):
            self.assertTrue(
                self.conn.scalar("SELECT count(*) FROM pg_proc WHERE proname = $1", fn),
                f"função {fn} não existe depois da atualização")

    def test_g_an_already_applied_migration_that_changed_is_refused(self):
        """Forward-only: alterar migration liberada tem de parar o runner, não passar calado."""
        self.conn.run("UPDATE schema_migrations SET checksum = repeat('0', 64) WHERE version = $1",
                      V0170)
        with self.assertRaises(RuntimeError) as ctx:
            self.migrate(OWNER_DSN, log=lambda *_: None)
        self.assertIn("alteradas", str(ctx.exception))
        # devolve o checksum real para não contaminar os testes seguintes
        import hashlib
        real = hashlib.sha256((ROOT / "backend" / "migrations" / f"{V0170}.sql").read_bytes()).hexdigest()
        self.conn.run("UPDATE schema_migrations SET checksum = $2 WHERE version = $1", V0170, real)
        from impacto.db.migrate import status
        self.assertEqual(status(self.conn)["changed"], [])


class FailedMigrationTests(unittest.TestCase):
    """Migration que falha no meio não pode deixar metade aplicada."""

    def test_a_broken_migration_leaves_nothing_behind(self):
        import impacto.db.migrate as M
        from impacto.db.pq import Connection
        db = f"impacto_v0181_broken_{os.getpid()}"
        psql("-c", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
        subprocess.run(["psql", ADMIN_URL, "-v", "ON_ERROR_STOP=1", "-q", "-v", f"db={db}", "-f",
                        str(ROOT / "infra/db/bootstrap.sql")], check=True, capture_output=True,
                       text=True)
        psql("-c", f"ALTER ROLE impacto_owner PASSWORD '{OWNER_PW}'")   # a do processo: ver support.py
        dsn = f"host={HOST} port={PORT} dbname={db} user=impacto_owner password={OWNER_PW}"
        original = M.MIGRATIONS_DIR
        try:
            with tempfile.TemporaryDirectory() as tmp:
                d = pathlib.Path(tmp)
                (d / "0001_ok.sql").write_text(
                    "CREATE TABLE etapa_um(id int PRIMARY KEY);", encoding="utf-8")
                # metade válida, metade inválida: a primeira instrução criaria tabela
                (d / "0002_quebrada.sql").write_text(
                    "CREATE TABLE etapa_dois(id int PRIMARY KEY);\n"
                    "SELECT coluna_que_nao_existe FROM etapa_um;", encoding="utf-8")
                M.MIGRATIONS_DIR = d
                with self.assertRaises(Exception):
                    M.migrate(dsn, sync_reference=False, log=lambda *_: None)
                c = Connection(dsn)
                try:
                    self.assertTrue(c.scalar("SELECT to_regclass('etapa_um') IS NOT NULL"),
                                    "a migration boa deveria ter ficado")
                    self.assertFalse(c.scalar("SELECT to_regclass('etapa_dois') IS NOT NULL"),
                                     "a migration quebrada deixou metade aplicada")
                    aplicadas = [r["version"] for r in c.query(
                        "SELECT version FROM schema_migrations ORDER BY version")]
                    self.assertEqual(aplicadas, ["0001_ok"],
                                     "o runner registrou uma migration que falhou")
                finally:
                    c.close()
        finally:
            M.MIGRATIONS_DIR = original
            psql("-c", f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)')
