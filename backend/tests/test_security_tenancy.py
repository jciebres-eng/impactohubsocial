"""Isolamento multi-tenant (BOLA/IDOR) pela API e pela RLS do banco, privilégios, uploads maliciosos,
injeção e adulteração do ledger. Todos os testes usam PostgreSQL e HTTP reais."""
import subprocess
import unittest
import zipfile
import io

from tests.support import ADMIN_URL, DB_NAME, Client, db_system, grant_premium, make_admin, new_account, server

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def project_body(**kw):
    b = {"title": "Projeto Teste", "summary": "Resumo do projeto", "territory": "BR-MT-5105259", "causes": ["educacao"],
         "beneficiaries_count": 30, "budget_total_cents": 1_000_000}
    b.update(kw)
    return b


class TenancyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.a = new_account("osc")
        cls.b = new_account("osc")
        cls.co = new_account("company")
        cls.co2 = new_account("company")
        cls.pid = cls.a.post("/v1/projects", project_body()).json["id"]
        grant_premium(cls.a)
        r = cls.a.upload("/v1/documents", "estatuto.pdf", PDF, {"doc_type": "estatuto_social", "title": "Estatuto"})
        assert r.status == 201, r
        cls.doc = r.json["id"]
        cls.draft = cls.a.post("/v1/drafts", {"kind": "project_proposal", "title": "Proposta", "content": "Texto confidencial"}).json["id"]

    def test_other_osc_cannot_read_or_write_project(self):
        self.assertEqual(self.b.get(f"/v1/projects/{self.pid}").status, 404)
        self.assertEqual(self.b.patch(f"/v1/projects/{self.pid}", {"title": "Invadido"}).status, 404)
        self.assertEqual(self.b.post(f"/v1/projects/{self.pid}/budget-items", {"description": "x", "quantity": 1, "unit_cost_cents": 1}).status, 404)
        self.assertEqual(self.b.post(f"/v1/projects/{self.pid}/evidences", {"kind": "photo", "title": "Falsa"}).status, 404)
        self.assertEqual(self.b.delete(f"/v1/projects/{self.pid}").status, 404)
        self.assertNotIn(self.pid, [p["id"] for p in self.b.get("/v1/projects").json["items"]])

    def test_other_tenants_cannot_access_documents_and_drafts(self):
        # self.co pode entrar em diligência com a OSC em outro teste (acesso legítimo a documentos institucionais);
        # aqui usamos apenas organizações SEM relação com a OSC dona.
        for c in (self.b, self.co2):
            self.assertEqual(c.get(f"/v1/documents/{self.doc}").status, 404)
            self.assertEqual(c.post(f"/v1/documents/{self.doc}/download-url").status, 404)
            self.assertEqual(c.get(f"/v1/drafts/{self.draft}").status, 404)
            self.assertEqual(c.patch(f"/v1/drafts/{self.draft}", {"content": "x"}).status, 404)
            self.assertNotIn(self.doc, [d["id"] for d in c.get("/v1/documents").json["items"]])

    def test_company_sees_only_published_and_docs_only_after_due_diligence(self):
        self.assertEqual(self.co.get(f"/v1/projects/{self.pid}").status, 404)
        pid = self.a.post("/v1/projects", project_body(title="Publicável")).json["id"]
        self.assertEqual(self.a.post(f"/v1/projects/{pid}/publish").status, 200)
        r = self.co.get(f"/v1/projects/{pid}")
        self.assertEqual(r.status, 200)
        self.assertIn("match", r.json)
        doc = self.a.upload("/v1/documents", "cnd.pdf", PDF, {"doc_type": "cnd_federal", "title": "CND", "project_id": pid}).json["id"]
        self.assertEqual(self.co.post(f"/v1/documents/{doc}/download-url").status, 404)
        app = self.co.post("/v1/applications/interest", {"project_id": pid}).json["id"]
        self.assertEqual(self.co2.get(f"/v1/applications/{app}").status, 404)
        self.assertEqual(self.b.get(f"/v1/applications/{app}").status, 404)
        # empresa não pode aceitar pela OSC
        self.assertEqual(self.co.post(f"/v1/applications/{app}/transition", {"to_status": "due_diligence"}).json["code"], "not_your_turn")
        self.assertEqual(self.a.post(f"/v1/applications/{app}/transition", {"to_status": "due_diligence"}).status, 200)
        r = self.co.post(f"/v1/documents/{doc}/download-url")
        self.assertEqual(r.status, 200, r)
        file = self.co.get(r.json["url"])
        self.assertEqual(file.body, PDF)
        self.assertIn("attachment", file.headers["Content-Disposition"])
        self.assertEqual(self.co2.post(f"/v1/documents/{doc}/download-url").status, 404)

    def test_download_token_is_short_lived_and_tamper_proof(self):
        url = self.a.post(f"/v1/documents/{self.doc}/download-url").json["url"]
        tampered = url[:-3] + ("aaa" if not url.endswith("aaa") else "bbb")
        self.assertEqual(Client().get(tampered).status, 403)
        self.assertIn(Client().get("/v1/files/..%2F..%2Fetc%2Fpasswd").status, (403, 404))

    def test_regular_user_cannot_access_admin(self):
        for path in ("/v1/admin/overview", "/v1/admin/users", "/v1/admin/fiscal-rules", "/v1/admin/audit"):
            r = self.a.get(path)
            self.assertEqual((r.status, r.json["code"]), (403, "admin_only"), path)
        self.assertEqual(self.a.post("/v1/admin/voucher-batches", {"campaign": "x", "type": "grant_plan", "plan_key": "osc_premium",
                                                                   "duration_days": 30, "quantity": 1}).status, 403)

    def test_admin_without_mfa_is_blocked(self):
        adm, _ = make_admin(mfa=False)
        r = adm.get("/v1/admin/overview")
        self.assertEqual((r.status, r.json["code"]), (403, "mfa_required"))
        adm2, _ = make_admin(mfa=True)
        self.assertEqual(adm2.get("/v1/admin/overview").status, 200)

    def test_role_and_kind_enforcement(self):
        self.assertEqual(self.co.post("/v1/projects", project_body()).json["code"], "wrong_org_kind")
        self.assertEqual(self.a.post("/v1/calls", {"title": "Edital falso"}).json["code"], "wrong_org_kind")
        self.assertEqual(self.a.get("/v1/feed/projects").json["code"], "wrong_org_kind")

    def test_injection_payloads_are_stored_literally(self):
        evil = "'; DROP TABLE projects; -- <script>alert(1)</script>"
        fresh = new_account("osc")
        pid = fresh.post("/v1/projects", project_body(title=evil[:190])).json["id"]
        r = fresh.get(f"/v1/projects/{pid}")
        self.assertEqual(r.json["title"], evil[:190])
        self.assertEqual(r.headers["Content-Type"], "application/json")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(self.a.get("/v1/projects").status, 200)

    def test_object_ids_are_validated(self):
        self.assertEqual(self.a.get("/v1/projects/nao-e-uuid").status, 404)
        self.assertEqual(self.a.get("/v1/projects/1%27%20OR%20%271%27=%271").status, 404)
        r = self.a.get("/v1/projects/00000000-0000-0000-0000-000000000000")
        self.assertEqual(r.status, 404)


class UploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.c = new_account("osc")

    def test_valid_pdf_hash_and_suggestion(self):
        import hashlib
        r = self.c.upload("/v1/documents", "cnd.pdf", PDF, {"doc_type": "cnd_federal", "title": "CND", "valid_until": "2030-01-01"})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["sha256"], hashlib.sha256(PDF).hexdigest())
        self.assertEqual(r.json["mime_type"], "application/pdf")

    def test_executable_disguised_as_pdf(self):
        r = self.c.upload("/v1/documents", "nota.pdf", b"MZ\x90\x00\x03" + b"\x00" * 200, {"doc_type": "nota_fiscal"})
        self.assertEqual((r.status, r.json["code"]), (422, "content_mismatch"))

    def test_disallowed_extension(self):
        r = self.c.upload("/v1/documents", "virus.exe", b"MZ" + b"\x00" * 50, {"doc_type": "outro"})
        self.assertEqual((r.status, r.json["code"]), (422, "file_type_not_allowed"))
        r = self.c.upload("/v1/documents", "pagina.html", b"<script>alert(1)</script>", {"doc_type": "outro"})
        self.assertEqual(r.status, 422)

    def test_pdf_with_javascript_rejected(self):
        evil = b"%PDF-1.4\n1 0 obj<< /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>endobj\n%%EOF"
        r = self.c.upload("/v1/documents", "evil.pdf", evil, {"doc_type": "outro"})
        self.assertEqual((r.status, r.json["code"]), (422, "active_content"))

    def test_docx_with_macro_rejected(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
            z.writestr("word/document.xml", "<w/>")
            z.writestr("word/vbaProject.bin", b"\x00" * 10)
        r = self.c.upload("/v1/documents", "macro.docx", buf.getvalue(), {"doc_type": "outro"})
        self.assertEqual((r.status, r.json["code"]), (422, "active_content"))

    def test_oversize_rejected(self):
        st = server()["state"].settings
        big = b"%PDF-1.4\n" + b"0" * (st.max_upload_bytes + 10)
        r = self.c.upload("/v1/documents", "grande.pdf", big, {"doc_type": "outro"})
        self.assertEqual(r.status, 413)

    def test_filename_traversal_is_neutralized(self):
        r = self.c.upload("/v1/documents", "../../../etc/passwd.txt", b"conteudo inofensivo", {"doc_type": "outro"})
        self.assertEqual(r.status, 201, r)
        d = self.c.get(f"/v1/documents/{r.json['id']}").json
        self.assertEqual(d["filename"], "passwd.txt")


class DatabaseRlsTests(unittest.TestCase):
    """Defesa em profundidade: mesmo uma query SEM filtro de tenant não vaza dados entre organizações."""

    @classmethod
    def setUpClass(cls):
        st = server()["state"]
        cls.pool = st.pool
        cls.a = new_account("osc")
        cls.b = new_account("osc")
        cls.pa = cls.a.post("/v1/projects", project_body(title="Projeto A")).json["id"]
        cls.pb = cls.b.post("/v1/projects", project_body(title="Projeto B")).json["id"]

    def ctx(self, client, kind="osc"):
        from impacto.db.pool import DbContext
        return self.pool.tx(DbContext(user_id=client.user["id"], org_id=client.org_id, org_kind=kind))

    def test_unfiltered_select_returns_only_own_rows(self):
        with self.ctx(self.a) as c:
            ids = {r["id"] for r in c.query("SELECT id::text AS id FROM projects")}
        self.assertIn(self.pa, ids)
        self.assertNotIn(self.pb, ids)

    def test_unfiltered_update_cannot_touch_other_tenant(self):
        with self.ctx(self.a) as c:
            c.run("UPDATE projects SET summary = 'alterado por A'")
        with db_system() as c:
            self.assertNotEqual(c.scalar("SELECT summary FROM projects WHERE id = $1", self.pb), "alterado por A")

    def test_insert_for_other_tenant_denied(self):
        from impacto.db.pq import InsufficientPrivilege
        with self.assertRaises(InsufficientPrivilege):
            with self.ctx(self.a) as c:
                c.run("INSERT INTO projects(org_id, title, territory) VALUES ($1, 'Forjado', 'BR')", self.b.org_id)

    def test_anonymous_context_sees_nothing(self):
        from impacto.db.pool import DbContext
        with self.pool.tx(DbContext()) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM organizations"), 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM users"), 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM documents"), 0)

    def test_privileged_columns_guarded(self):
        from impacto.db.pq import InsufficientPrivilege
        with self.assertRaises(InsufficientPrivilege):
            with self.ctx(self.a) as c:
                c.run("UPDATE users SET is_platform_admin = true WHERE id = $1", self.a.user["id"])
        with self.assertRaises(InsufficientPrivilege):
            with self.ctx(self.a) as c:
                c.run("UPDATE organizations SET compliance_status = 'approved' WHERE id = $1", self.a.org_id)

    def test_append_only_and_hidden_tables(self):
        from impacto.db.pq import DatabaseError
        with self.assertRaises(DatabaseError):
            with self.ctx(self.a) as c:
                c.run("UPDATE audit_events SET action = 'forjado.x'")
        with self.assertRaises(DatabaseError):
            with self.ctx(self.a) as c:
                c.run("DELETE FROM audit_events")
        with self.assertRaises(DatabaseError):
            with self.ctx(self.a) as c:
                c.query("SELECT * FROM chain_heads")

    def test_app_role_has_no_bypass(self):
        with self.pool.connection() as c:
            r = c.one("SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
            self.assertEqual((r["rolsuper"], r["rolbypassrls"]), (False, False))
            self.assertEqual(c.scalar("SELECT current_user"), "impacto_app")

    def test_ledger_tampering_is_detected(self):
        self.a.post(f"/v1/projects/{self.pa}/publish")
        with self.ctx(self.a) as c:
            ok = c.one("SELECT * FROM ledger_verify($1)", self.pa)
        self.assertTrue(ok["valid"])
        self.assertGreaterEqual(ok["entries"], 2)
        # Ataque com privilégio de DBA: desliga o trigger e altera o payload
        sql = (f"ALTER TABLE ledger_entries DISABLE TRIGGER trg_append_only;"
               f"UPDATE ledger_entries SET amount_cents = 1 WHERE project_id = '{self.pa}' AND seq = 1;"
               f"ALTER TABLE ledger_entries ENABLE TRIGGER trg_append_only;")
        subprocess.run(["psql", ADMIN_URL.rsplit("/", 1)[0] + "/" + DB_NAME, "-v", "ON_ERROR_STOP=1", "-q", "-c", sql], check=True, capture_output=True)
        with self.ctx(self.a) as c:
            bad = c.one("SELECT * FROM ledger_verify($1)", self.pa)
        self.assertFalse(bad["valid"])
        self.assertEqual(bad["first_broken_seq"], 1)

    def test_app_db_role_cannot_bypass_rls(self):
        from impacto.app import db_role_problems
        from impacto.db.pool import Pool
        from tests.support import OWNER_DSN
        self.assertEqual(db_role_problems(server()["state"].pool), [])   # impacto_app: OK
        owner = Pool(OWNER_DSN, max_size=1)
        try:
            self.assertTrue(any("dono" in p for p in db_role_problems(owner)))   # papel dono detectado
        finally:
            owner.close()


if __name__ == "__main__":
    unittest.main()
