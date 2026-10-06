"""Caminho de ATUALIZAÇÃO do banco: v0.12.1 → v0.13.0 → v0.14.0 → v0.15.0, com dado dentro.

Criar o banco do zero prova que o esquema é coerente. Não prova que quem já está em produção consegue subir. Este
teste prepara um banco na v0.12.1, coloca dado real nele, aplica as migrations seguintes e confere que:

* nada do que existia foi perdido nem reescrito (inclusive a trilha encadeada por hash);
* as situações de projeto que o produto já usava continuam funcionando;
* a consolidação dos ODS (que REMOVEU uma tabela duplicada) não deixou referência quebrada;
* as estruturas novas chegaram com RLS.
"""
from __future__ import annotations

import os
import subprocess
import unittest
import uuid

from tests.support import ADMIN_URL, HOST, PORT, ROOT

DB = f"impacto_upgrade_{os.getpid()}"
OWNER_PW = "upgrade_owner_" + uuid.uuid4().hex[:8]
APP_PW = "upgrade_app_" + uuid.uuid4().hex[:8]
OWNER_DSN = f"host={HOST} port={PORT} dbname={DB} user=impacto_owner password={OWNER_PW}"
APP_DSN = f"host={HOST} port={PORT} dbname={DB} user=impacto_app password={APP_PW}"
# última migration de cada versão entregue
V0121 = "0010_v0121_indexes"
V0130 = "0011_v0130_integration_hub"
V0140 = "0012_v0140_trust_layer"


def psql(*args: str) -> str:
    return subprocess.run(["psql", ADMIN_URL, "-v", "ON_ERROR_STOP=1", "-q", "-tA", *args],
                          check=True, capture_output=True, text=True).stdout


class UpgradePathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from impacto.db.migrate import migrate
        from impacto.db.pq import Connection
        psql("-c", f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')
        subprocess.run(["psql", ADMIN_URL, "-v", "ON_ERROR_STOP=1", "-q", "-v", f"db={DB}", "-f",
                        str(ROOT / "infra/db/bootstrap.sql")], check=True, capture_output=True, text=True)
        psql("-c", f"ALTER ROLE impacto_owner PASSWORD '{OWNER_PW}'; ALTER ROLE impacto_app PASSWORD '{APP_PW}';")
        cls.migrate = staticmethod(migrate)
        cls.conn = Connection(OWNER_DSN)
        # --- banco na v0.12.1
        applied = migrate(OWNER_DSN, upto=V0121, sync_reference=False, log=lambda *_: None)
        assert applied[-1] == V0121, applied
        cls.applied_v0121 = applied
        cls._seed()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.conn.close()
        finally:
            if os.getenv("TEST_KEEP_DB") != "1":
                psql("-c", f'DROP DATABASE IF EXISTS "{DB}" WITH (FORCE)')

    @classmethod
    def _seed(cls) -> None:
        """Dado como o de uma organização que já usava a plataforma antes desta versão."""
        c = cls.conn
        cls.org = c.one("INSERT INTO organizations(kind, legal_name, compliance_status, uf)"
                        " VALUES ('osc','OSC que já existia','approved','MT') RETURNING id::text AS id")["id"]
        cls.user = c.one("INSERT INTO users(email, full_name, password_hash, status)"
                         " VALUES ('antiga@teste.org','Usuária antiga','x','active') RETURNING id::text AS id")["id"]
        c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner')", cls.user, cls.org)
        cls.project = c.one("INSERT INTO projects(org_id, title, summary, problem, territory, causes,"
                            " beneficiaries_count, budget_total_cents, status, visibility, published_at, created_by)"
                            " VALUES ($1,'Projeto anterior à atualização','Resumo','Problema','BR-MT','{educacao}',"
                            " 100, 2000000, 'published', 'published', now(), $2) RETURNING id::text AS id",
                            cls.org, cls.user)["id"]
        cls.doc = c.one("INSERT INTO documents(org_id, project_id, doc_type, title, filename, mime_type, size_bytes,"
                        " sha256, storage_key, status, origin, uploaded_by) VALUES ($1,$2,'estatuto_social',"
                        " 'Estatuto antigo','e.pdf','application/pdf',1024,$3,'antigo/1','clean','upload',$4)"
                        " RETURNING id::text AS id", cls.org, cls.project, "a" * 64, cls.user)["id"]
        for kind, amount in (("need_published", 2000000), ("budget_defined", 2000000)):
            c.run("INSERT INTO ledger_entries(project_id, org_id, actor_user_id, entry_type, amount_cents, ref_type,"
                  " ref_id, payload) VALUES ($1,$2,$3,$4,$5,'project',$6,'{}'::jsonb)",
                  cls.project, cls.org, cls.user, kind, amount, cls.project)
        cls.ledger_before = c.query("SELECT seq, entry_type, entry_hash FROM ledger_entries"
                                    " WHERE project_id = $1 ORDER BY seq", cls.project)
        assert cls.ledger_before, "a trilha precisa ter entradas antes da atualização"

    # ------------------------------------------------------------------------------------ o caminho
    def test_01_v0121_has_no_v0150_structures(self):
        for table in ("ideas", "project_transitions", "diagnosis_versions", "document_assemblies",
                      "signature_providers", "encryption_keys",
                      "relationships", "proposals", "marketplace_listings", "impact_updates",
                      "public_profiles", "plan_price_versions"):
            self.assertIsNone(self.conn.one("SELECT 1 FROM pg_tables WHERE tablename = $1", table),
                              f"{table} não deveria existir na v0.12.1")
        self.assertIsNotNone(self.conn.one("SELECT 1 FROM pg_tables WHERE tablename = 'ods_goals'"))

    def test_02_upgrade_step_by_step_succeeds(self):
        steps = [(V0130, "v0.13.0"), (V0140, "v0.14.0"), (None, "v0.15.0 + v0.16.0 (todas as restantes)")]
        for upto, label in steps:
            applied = self.migrate(OWNER_DSN, upto=upto, sync_reference=False, log=lambda *_: None)
            self.assertTrue(applied, f"nenhuma migration aplicada no passo {label}")
        from impacto.db.migrate import status
        st = status(self.conn)
        self.assertEqual(st["pending"], [], "sobrou migration pendente depois da atualização")
        self.assertEqual(st["changed"], [], "migration já aplicada foi alterada")

    def test_03_pre_existing_data_survived_untouched(self):
        p = self.conn.one("SELECT title, status, visibility, budget_total_cents, origin_idea_id FROM projects"
                          " WHERE id = $1", self.project)
        self.assertEqual(p["title"], "Projeto anterior à atualização")
        self.assertEqual(p["status"], "published")
        self.assertIsNone(p["origin_idea_id"], "projeto antigo não tem ideia de origem, e isso é correto")
        d = self.conn.one("SELECT title, sha256, status FROM documents WHERE id = $1", self.doc)
        self.assertEqual(d["sha256"], "a" * 64)
        self.assertEqual(d["status"], "clean")

    def test_04_hash_chained_ledger_is_still_intact(self):
        after = self.conn.query("SELECT seq, entry_type, entry_hash FROM ledger_entries WHERE project_id = $1"
                                " ORDER BY seq", self.project)
        self.assertEqual([(r["seq"], r["entry_type"], r["entry_hash"]) for r in after],
                         [(r["seq"], r["entry_type"], r["entry_hash"]) for r in self.ledger_before],
                         "a atualização mexeu na trilha encadeada")
        v = self.conn.one("SELECT entries, valid, first_broken_seq FROM ledger_verify($1)", self.project)
        self.assertTrue(v["valid"], v)

    def test_05_legacy_project_transitions_still_work(self):
        """O produto já movia projeto de 'published' para 'funded' antes da máquina de estados existir."""
        for frm, to in (("published", "funded"), ("funded", "in_execution"), ("in_execution", "completed")):
            self.assertIsNotNone(
                self.conn.one("SELECT 1 FROM project_status_graph WHERE from_status = $1 AND to_status = $2", frm, to),
                f"a transição legada {frm} → {to} não está no grafo: a atualização quebraria o fluxo existente")
        self.conn.run("UPDATE projects SET status = 'funded' WHERE id = $1", self.project)
        self.assertEqual(self.conn.scalar("SELECT status FROM projects WHERE id = $1", self.project), "funded")

    def test_06_ods_consolidation_left_no_dangling_reference(self):
        self.assertIsNone(self.conn.one("SELECT 1 FROM pg_tables WHERE tablename = 'sdg_goals'"),
                          "sdg_goals (duplicada) deveria ter sido removida")
        cols = {r["column_name"] for r in self.conn.query(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'ods_goals'")}
        self.assertTrue({"code", "name_en", "color_hex", "active"} <= cols, cols)
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM ods_goals WHERE code IS NOT NULL"), 17)
        orphan = self.conn.scalar("SELECT count(*) FROM indicator_catalog ic WHERE ic.ods IS NOT NULL"
                                  " AND NOT EXISTS (SELECT 1 FROM ods_goals g WHERE g.number = ic.ods)")
        self.assertEqual(orphan, 0, "indicator_catalog ficou apontando para ODS que não existe mais")

    def test_07_new_structures_arrived_with_rls(self):
        for table in ("ideas", "project_transitions", "project_snapshots", "project_risks", "diagnosis_versions",
                      "diagnosis_actions", "document_templates", "document_template_fields", "document_assemblies",
                      "match_feedback", "signature_providers", "signature_policies", "encryption_keys",
                      "encryption_rotations", "project_status_graph",
                      # v0.16.0 — a rede de impacto e a cobrança versionada
                      "relationships", "proposals", "proposal_events", "proposal_status_graph",
                      "marketplace_listings", "impact_updates", "personas", "org_personas", "taxonomies",
                      "taxonomy_terms", "public_profiles", "handle_history", "professional_experiences",
                      "enforcement_actions", "territory_needs", "investment_intents", "recommendations",
                      "readiness_snapshots", "domain_events", "network_status_graph",
                      "plan_price_versions", "subscription_prices", "price_change_notices",
                      # v0.17.0 — a camada econômica, legal e de pagamento
                      "programs", "program_status_graph", "program_calls", "program_projects",
                      "program_indicators", "program_needs", "value_event_types", "value_baselines",
                      "value_events", "ai_price_table", "monetization_legal_cards",
                      "monetization_rules", "billable_events", "charge_state_graph",
                      "payment_instruments", "platform_charges", "charge_events",
                      "charge_installments", "charge_pix", "charge_boleto", "legal_documents",
                      "legal_acceptances"):
            row = self.conn.one("SELECT relrowsecurity FROM pg_class WHERE relname = $1 AND relkind = 'r'", table)
            self.assertIsNotNone(row, f"{table} não foi criada")
            self.assertTrue(row["relrowsecurity"], f"{table} sem RLS habilitada")
            self.assertGreater(self.conn.scalar("SELECT count(*) FROM pg_policies WHERE tablename = $1", table) or 0,
                               0, f"{table} sem política")

    def test_08_platform_templates_and_providers_are_seeded(self):
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM document_templates WHERE owner_org_id IS NULL"
                                          " AND status = 'published'"), 3)
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM document_template_fields"), 49)
        states = {r["key"]: r["state"] for r in self.conn.query("SELECT key, state FROM signature_providers")}
        self.assertEqual(states["platform_advanced"], "production")
        self.assertEqual(states["icp_brasil"], "unavailable")
        self.assertEqual(states["govbr"], "unavailable")

    def test_09_app_role_can_use_the_new_tables(self):
        from impacto.db.pq import Connection
        app = Connection(APP_DSN)
        try:
            app.execute_script("BEGIN")
            app.run("SELECT set_config('app.user_id', $1, true), set_config('app.org_id', $2, true),"
                    " set_config('app.org_kind', 'osc', true), set_config('app.platform_admin','off',true),"
                    " set_config('app.system','off',true)", self.user, self.org)
            iid = app.scalar("INSERT INTO ideas(org_id, title, created_by) VALUES ($1,'Ideia pós-atualização',$2)"
                             " RETURNING id::text", self.org, self.user)
            self.assertTrue(iid)
            self.assertEqual(app.scalar("SELECT count(*) FROM ideas"), 1)
            self.assertGreater(app.scalar("SELECT count(*) FROM project_status_graph") or 0, 0)
            self.assertEqual(app.scalar("SELECT count(*) FROM encryption_keys"), 0,
                             "tabela de chaves deveria ser invisível para a organização")
            app.execute_script("ROLLBACK")
        finally:
            app.close()

    def test_09b_the_v0170_layer_arrived_with_its_seeds_and_its_refusals(self):
        """Atualizar precisa trazer as travas, não só as tabelas.

        Uma migração pode criar a estrutura e deixar o conteúdo de fora — e aí o portão legal existe
        sem nenhuma regra para barrar, as minutas não existem para serem recusadas, e tudo "passa".
        """
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM legal_documents"), 11)
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM legal_documents"
                                          " WHERE status = 'approved'"), 0,
                         "nenhuma minuta pode chegar aprovada por atualização")
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM monetization_rules"), 9)
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM monetization_rules WHERE active"), 0,
                         "nenhuma regra de receita pode chegar ativa por atualização")
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM monetization_legal_cards"
                                          " WHERE status = 'green'"), 0)
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM value_event_types"), 11)
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM value_baselines"
                                          " WHERE minutes_per_unit IS NOT NULL"), 0,
                         "nenhuma linha de base pode chegar com número por atualização")
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM ai_price_table"), 0)
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM charge_state_graph"), 27)
        self.assertEqual(self.conn.scalar("SELECT count(*) FROM program_status_graph"), 11)
        # e as travas funcionam no banco ATUALIZADO, não só no criado do zero
        with self.assertRaises(Exception):
            self.conn.run("INSERT INTO legal_acceptances(document_id, user_id)"
                          " SELECT id, $1 FROM legal_documents WHERE doc_key = 'terms_of_use'",
                          self.user)
        with self.assertRaises(Exception):
            self.conn.run("UPDATE legal_documents SET status = 'approved' WHERE doc_key = 'cookies'")

    def test_10_schema_matches_a_database_built_from_scratch(self):
        """Atualizar e criar do zero precisam levar ao MESMO esquema. Divergência aqui é dívida silenciosa."""
        fresh = f"{DB}_fresh"
        psql("-c", f'DROP DATABASE IF EXISTS "{fresh}" WITH (FORCE)')
        subprocess.run(["psql", ADMIN_URL, "-v", "ON_ERROR_STOP=1", "-q", "-v", f"db={fresh}", "-f",
                        str(ROOT / "infra/db/bootstrap.sql")], check=True, capture_output=True, text=True)
        from impacto.db.pq import Connection
        fresh_dsn = f"host={HOST} port={PORT} dbname={fresh} user=impacto_owner password={OWNER_PW}"
        self.migrate(fresh_dsn, sync_reference=False, log=lambda *_: None)
        fc = Connection(fresh_dsn)
        try:
            q = ("SELECT table_name || '.' || column_name || ':' || data_type ||"
                 " coalesce(':' || character_maximum_length::text, '') AS sig"
                 " FROM information_schema.columns WHERE table_schema = 'public' ORDER BY 1")
            self.assertEqual([r["sig"] for r in fc.query(q)], [r["sig"] for r in self.conn.query(q)],
                             "esquema atualizado difere do esquema criado do zero")
            qi = ("SELECT tablename || ':' || indexname AS sig FROM pg_indexes WHERE schemaname = 'public' ORDER BY 1")
            self.assertEqual([r["sig"] for r in fc.query(qi)], [r["sig"] for r in self.conn.query(qi)],
                             "índices divergem entre atualização e criação do zero")
            qp = ("SELECT tablename || ':' || policyname AS sig FROM pg_policies WHERE schemaname = 'public' ORDER BY 1")
            self.assertEqual([r["sig"] for r in fc.query(qp)], [r["sig"] for r in self.conn.query(qp)],
                             "políticas de RLS divergem entre atualização e criação do zero")
            qt = ("SELECT c.relname || ':' || t.tgname AS sig FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid"
                  " JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'public'"
                  " AND NOT t.tgisinternal ORDER BY 1")
            self.assertEqual([r["sig"] for r in fc.query(qt)], [r["sig"] for r in self.conn.query(qt)],
                             "gatilhos divergem entre atualização e criação do zero")
        finally:
            fc.close()
            if os.getenv("TEST_KEEP_DB") != "1":
                psql("-c", f'DROP DATABASE IF EXISTS "{fresh}" WITH (FORCE)')
