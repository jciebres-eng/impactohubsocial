"""v0.17.0 — registro versionado de documento legal e aceite com prova.

A afirmação que estes testes protegem é a mais fácil de falsificar em qualquer produto: "o usuário
aceitou os termos". Sem documento, versão e hash do texto, essa frase não é prova de nada.

E a trava mais importante aqui é desconfortável de propósito: **nenhuma das onze minutas foi revisada
por advogado(a), então nenhuma pode ser aceita**. O produto não coleta aceite de rascunho.
"""
from __future__ import annotations

import hashlib
import pathlib
import unittest

from tests.support import Client, db_system, make_admin, new_account, owner_conn

REPO = pathlib.Path(__file__).resolve().parents[2]

#: As onze chaves que a rodada pede: Termos, Assinatura, Marketplace, Intermediação, Pagamento,
#: Cancelamento, Reembolso, B2B, B2G — mais privacidade e cookies, que já existiam.
KEYS = {"terms_of_use", "privacy_policy", "cookies", "subscription", "marketplace",
        "intermediation", "payment", "cancellation", "refund", "b2b", "b2g"}


class RegistryTests(unittest.TestCase):
    def test_the_eleven_documents_are_registered(self):
        r = Client().get("/v1/legal/registry")
        self.assertEqual(r.status, 200, r)
        self.assertEqual({i["doc_key"] for i in r.json["items"]}, KEYS)

    def test_none_of_them_is_approved_and_the_api_says_so_in_numbers(self):
        """Se um dia este teste falhar, é porque alguém aprovou uma minuta — e isso tem de doer."""
        body = Client().get("/v1/legal/registry").json
        self.assertEqual(body["approved"], 0)
        self.assertEqual(body["drafts"], len(KEYS))
        self.assertFalse(body["can_collect_acceptance"])
        for item in body["items"]:
            self.assertEqual(item["status"], "draft", item["doc_key"])
            self.assertIn("MINUTA", item["status_label"])

    def test_the_documents_requiring_acceptance_are_listed_as_blocking(self):
        body = Client().get("/v1/legal/registry").json
        self.assertEqual(set(body["blocking_product"]), {"terms_of_use", "privacy_policy"},
                         "exige aceite e não está aprovado = bloqueia")

    def test_every_draft_carries_the_english_marker_demanded_by_the_round(self):
        for key in KEYS:
            doc = Client().get(f"/v1/legal/documents/{key}").json
            self.assertIn("DRAFT FOR LEGAL REVIEW", doc["body_md"],
                          f"{key} tem de se identificar como minuta no próprio texto")

    def test_the_stored_text_is_byte_for_byte_the_repository_text(self):
        """Contrato digitado duas vezes diverge um dia, e ninguém descobre qual foi aceito."""
        with db_system() as c:
            rows = c.query("SELECT doc_key, source_path, body_sha256 FROM legal_documents")
        self.assertEqual(len(rows), len(KEYS))
        for row in rows:
            path = REPO / row["source_path"]
            self.assertTrue(path.exists(), f"{row['source_path']} não existe no repositório")
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(row["body_sha256"], sha,
                             f"{row['doc_key']}: o banco e o arquivo divergiram")

    def test_the_generator_is_in_sync_with_the_documents(self):
        import subprocess
        out = subprocess.run(["python3", "scripts/gen_legal_registry.py", "--check"], cwd=REPO,
                             capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)

    def test_the_text_route_says_in_the_header_that_it_is_a_draft(self):
        r = Client().get("/v1/legal/termos")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.headers.get("x-legal-status"), "draft")
        self.assertEqual(r.headers.get("x-legal-version"), "1")
        self.assertEqual(len(r.headers.get("x-legal-sha256", "")), 64)

    def test_an_unknown_document_is_a_404_not_an_empty_page(self):
        self.assertEqual(Client().get("/v1/legal/documents/inexistente").status, 404)


class AcceptanceRefusalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def test_nobody_can_accept_a_draft_through_the_api(self):
        r = self.c.post("/v1/legal/acceptances", {"doc_key": "terms_of_use"})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "document_not_effective")
        self.assertIn("MINUTA", r.json["title"])

    def test_nobody_can_accept_a_draft_through_direct_sql_either(self):
        oc = owner_conn()
        try:
            doc = oc.scalar("SELECT id::text FROM legal_documents WHERE doc_key = 'b2g'")
            with self.assertRaises(Exception) as e:
                oc.run("INSERT INTO legal_acceptances(document_id, user_id) VALUES ($1,$2)",
                       doc, self.c.user["id"])
            self.assertIn("DRAFT FOR LEGAL REVIEW", str(e.exception))
        finally:
            oc.close()

    def test_pending_is_empty_and_explains_that_this_is_not_the_same_as_accepted(self):
        body = self.c.get("/v1/legal/pending").json
        self.assertEqual(body["items"], [])
        self.assertIn("não significa que o usuário já aceitou", body["note"].lower())

    def test_approval_without_a_reviewer_is_refused_by_the_database(self):
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("UPDATE legal_documents SET status = 'approved' WHERE doc_key = 'refund'")
            self.assertIn("approved_needs_review", str(e.exception))
        finally:
            oc.close()

    def test_effective_date_cannot_precede_approval(self):
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("UPDATE legal_documents SET effective_from = current_date"
                       " WHERE doc_key = 'refund'")
            self.assertIn("effective_needs_approved", str(e.exception))
        finally:
            oc.close()


class ApprovedDocumentTests(unittest.TestCase):
    """O caminho completo, exercido sobre uma versão aprovada DENTRO do teste.

    Nenhuma minuta do repositório é aprovada aqui: o teste cria um documento próprio, aprova-o com
    revisor nomeado e exercita o aceite. Aprovar uma minuta real num teste seria exatamente a mentira
    que o resto deste arquivo impede.
    """

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")
        cls.admin, _ = make_admin()
        oc = owner_conn()
        try:
            cls.doc_id = oc.scalar(
                "INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,"
                " audience, requires_acceptance, software_version)"
                " VALUES ('test_policy', 1, 'Documento de Teste',"
                " 'Documento criado pelo teste para exercitar o caminho de aprovação e aceite.',"
                " 'docs/legal/_TESTE.md', $1, 'all', true, '0.17.0') RETURNING id::text",
                "# Documento de Teste\n\n" + ("texto suficientemente longo. " * 20))
        finally:
            oc.close()

    @classmethod
    def tearDownClass(cls):
        oc = owner_conn()
        try:
            oc.run("DELETE FROM legal_acceptances WHERE doc_key = 'test_policy'")
            oc.run("DELETE FROM legal_documents WHERE doc_key = 'test_policy'")
        finally:
            oc.close()

    def _approve(self):
        r = self.admin.post(f"/v1/admin/legal/documents/{self.doc_id}/approve",
                            {"reviewed_by": "Advogada de Teste",
                             "review_reference": "parecer fictício do teste"})
        self.assertEqual(r.status, 200, r)
        return r.json

    def test_01_review_then_approval_derives_the_effective_date(self):
        r = self.admin.post(f"/v1/admin/legal/documents/{self.doc_id}/review", {})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["status"], "in_legal_review")
        out = self._approve()
        self.assertEqual(out["status"], "approved")
        self.assertIsNotNone(out["effective_from"])

    def test_02_the_document_then_becomes_pending_for_the_user(self):
        body = self.c.get("/v1/legal/pending").json
        self.assertIn("test_policy", [i["doc_key"] for i in body["items"]])

    def test_03_acceptance_records_version_and_hash_of_the_text(self):
        r = self.c.post("/v1/legal/acceptances", {"doc_key": "test_policy"})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["version"], 1)
        self.assertEqual(len(r.json["body_sha256"]), 64)
        self.assertFalse(r.json["already_accepted"])
        with db_system() as c:
            sha = c.scalar("SELECT body_sha256 FROM legal_documents WHERE id = $1", self.doc_id)
        self.assertEqual(r.json["body_sha256"], sha, "a prova tem de apontar para o texto aceito")

    def test_04_accepting_twice_does_not_duplicate_the_proof(self):
        again = self.c.post("/v1/legal/acceptances", {"doc_key": "test_policy"})
        self.assertEqual(again.status, 201, again)
        self.assertTrue(again.json["already_accepted"])
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM legal_acceptances"
                                      " WHERE doc_key = 'test_policy'"), 1)

    def test_05_it_leaves_pending_once_accepted(self):
        body = self.c.get("/v1/legal/pending").json
        self.assertNotIn("test_policy", [i["doc_key"] for i in body["items"]])

    def test_06_the_proof_is_append_only(self):
        oc = owner_conn()
        try:
            with self.assertRaises(Exception):
                oc.run("UPDATE legal_acceptances SET accepted_at = now() - interval '1 year'"
                       " WHERE doc_key = 'test_policy'")
        finally:
            oc.close()

    def test_07_the_text_of_an_approved_version_is_immutable(self):
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("UPDATE legal_documents SET body_md = body_md || ' remendo' WHERE id = $1",
                       self.doc_id)
            self.assertIn("imutável", str(e.exception))
        finally:
            oc.close()

    def test_08_a_new_version_supersedes_the_previous_approved_one(self):
        oc = owner_conn()
        try:
            new_id = oc.scalar(
                "INSERT INTO legal_documents(doc_key, version, title, summary, source_path, body_md,"
                " audience, requires_acceptance, software_version)"
                " VALUES ('test_policy', 2, 'Documento de Teste',"
                " 'Segunda versão criada pelo teste para provar a superação da anterior.',"
                " 'docs/legal/_TESTE.md', $1, 'all', true, '0.17.0') RETURNING id::text",
                "# Documento de Teste v2\n\n" + ("outro texto longo o bastante. " * 20))
            oc.run("UPDATE legal_documents SET status = 'approved', reviewed_by = 'Advogada de Teste',"
                   " reviewed_at = now(), review_reference = 'parecer 2' WHERE id = $1", new_id)
            self.assertEqual(oc.scalar("SELECT status FROM legal_documents WHERE id = $1",
                                       self.doc_id), "superseded")
            self.assertEqual(oc.scalar("SELECT count(*) FROM legal_documents"
                                       " WHERE doc_key = 'test_policy' AND status = 'approved'"), 1)
        finally:
            oc.close()

    def test_09_the_old_acceptance_still_proves_what_was_accepted(self):
        """É todo o ponto da versão: o aceite de ontem continua apontando para o texto de ontem."""
        body = self.c.get("/v1/legal/acceptances/mine").json
        row = next(i for i in body["items"] if i["doc_key"] == "test_policy")
        self.assertEqual(row["version"], 1)
        with db_system() as c:
            v1 = c.scalar("SELECT body_sha256 FROM legal_documents WHERE id = $1", self.doc_id)
        self.assertEqual(row["body_sha256"], v1)

    def test_10_the_new_version_becomes_pending_again(self):
        body = self.c.get("/v1/legal/pending").json
        item = next((i for i in body["items"] if i["doc_key"] == "test_policy"), None)
        self.assertIsNotNone(item, "versão nova exige aceite novo")
        self.assertEqual(item["version"], 2)

    def test_11_status_never_goes_backwards(self):
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("UPDATE legal_documents SET status = 'draft' WHERE id = $1", self.doc_id)
            self.assertIn("não volta", str(e.exception))
        finally:
            oc.close()

    def test_12_the_admin_sees_the_proof_with_who_and_which_hash(self):
        r = self.admin.get("/v1/admin/legal/acceptances?doc_key=test_policy")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["total"], 1)
        row = r.json["items"][0]
        self.assertEqual(row["email"], self.c.user["email"])
        self.assertEqual(len(row["sha_prefix"]), 16)


class AcceptanceIsolationTests(unittest.TestCase):
    def test_a_user_sees_only_their_own_acceptances(self):
        a, b = new_account("osc"), new_account("osc")
        self.assertEqual(a.get("/v1/legal/acceptances/mine").json["items"], [])
        self.assertEqual(b.get("/v1/legal/acceptances/mine").json["items"], [])

    def test_the_proof_table_is_not_readable_by_another_organization(self):
        c = new_account("osc")
        from tests.support import app_tx
        with app_tx(c) as conn:
            self.assertEqual(conn.scalar("SELECT count(*) FROM legal_acceptances"), 0)


if __name__ == "__main__":
    unittest.main()
