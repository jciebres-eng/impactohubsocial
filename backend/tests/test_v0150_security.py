"""Matriz de isolamento da v0.15.0: USUÁRIA A tentando agir sobre o RECURSO B, em TODAS as rotas de escrita.

Dois níveis:

1. Varredura automática sobre o registro de rotas: toda rota de escrita com identificador no caminho é chamada com
   um identificador que não existe para ninguém. Nenhuma pode responder 2xx. Isso pega rota nova que esquecer de
   conferir a dona do recurso — inclusive rota que alguém acrescentar depois desta versão.
2. Matriz explícita sobre os recursos novos (ideia, transição, retrato, risco, versão de diagnóstico, ação,
   montagem, modelo, retorno de match), com o identificador REAL da outra organização.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import Client, db_system, grant_premium, make_admin, new_account

# métodos que mudam estado
WRITE = ("POST", "PUT", "PATCH", "DELETE")
# respostas aceitáveis quando o recurso não é da organização: nunca 2xx, nunca 500
ALLOWED = {400, 401, 403, 404, 409, 410, 415, 422, 429, 501, 503}
# DELETE idempotente da PRÓPRIA relação: apagar "o que eu marquei" quando nada está marcado responde com sucesso,
# e isso não conta como vazamento — a resposta é idêntica para identificador existente e inexistente (conferido em
# `IdempotentDeleteTests`), e a linha afetada é sempre da organização que chamou.
IDEMPOTENT_SELF_DELETE = {
    "/v1/feed/projects/{project_id}/favorite",
    "/v1/network/follow/{org_id}",
    "/v1/network/block/{org_id}",
    "/v1/solutions/{solution_id}/save",
    "/v1/solutions/{solution_id}/intent",
}
# rotas que, por natureza, não tomam identificador de recurso de outra organização no caminho
SKIP_PATHS = {
    "/v1/auth/accept-invite",          # token próprio, testado em test_api_auth
    "/v1/files/{token}",               # token assinado, testado em test_security_tenancy
    "/v1/public/verify/{code}",        # verificação PÚBLICA: responder é a função dela
}


def _fake_path(path: str) -> str:
    """Troca cada parâmetro do caminho por um valor que não existe para nenhuma organização."""
    out = path
    while "{" in out:
        head, rest = out.split("{", 1)
        name, tail = rest.split("}", 1)
        if "code" in name or "slug" in name or "token" in name or "key" in name:
            value = "nao-existe-" + uuid.uuid4().hex[:8]
        elif name in ("version", "stage_code"):
            value = "9999"
        else:
            value = str(uuid.uuid4())
        out = head + value + tail
    return out


class WriteRouteSweep(unittest.TestCase):
    """Nenhuma rota de escrita devolve 2xx para um recurso que não é da organização."""

    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.company = new_account("company", compliance="approved")
        grant_premium(cls.osc)
        grant_premium(cls.company)
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        cls.routes = [r for r in ROUTES if r.method in WRITE and "{" in r.path and r.path not in SKIP_PATHS
                      and not (r.method == "DELETE" and r.path in IDEMPOTENT_SELF_DELETE)
                      and r.auth in ("org", "user")]

    def test_sweep(self):
        self.assertGreater(len(self.routes), 60, "a varredura precisa cobrir as rotas de escrita com identificador")
        leaks = []
        for r in self.routes:
            client = self.company if (r.kinds and "osc" not in r.kinds) else self.osc
            path = _fake_path(r.path)
            resp = client.request(r.method, path, {} if r.method != "DELETE" else None)
            if 200 <= resp.status < 300 or resp.status >= 500:
                leaks.append(f"{r.method} {r.path} -> {resp.status}")
        self.assertEqual(leaks, [], "rotas que responderam a identificador inexistente:\n" + "\n".join(leaks))

    def test_sweep_covers_the_new_core_routes(self):
        paths = {r.path for r in self.routes}
        for p in ("/v1/ideas/{idea_id}", "/v1/ideas/{idea_id}/promote",
                  "/v1/projects/{project_id}/transitions", "/v1/projects/{project_id}/snapshots",
                  "/v1/projects/{project_id}/risks", "/v1/projects/{project_id}/risks/scan",
                  "/v1/diagnoses/{diagnosis_id}/versions", "/v1/diagnoses/{diagnosis_id}/actions",
                  "/v1/document-assemblies/{assembly_id}", "/v1/document-assemblies/{assembly_id}/generate",
                  "/v1/document-assemblies/{assembly_id}/review",
                  "/v1/document-templates/{template_id}/fields", "/v1/document-templates/{template_id}/publish",
                  "/v1/match-runs/{match_run_id}/feedback"):
            self.assertIn(p, paths, f"rota nova fora da varredura: {p}")


class IdempotentDeleteTests(unittest.TestCase):
    """As exceções da varredura precisam ser indistinguíveis: a resposta não pode dizer se o alvo existe."""

    @classmethod
    def setUpClass(cls):
        cls.a = new_account("osc", compliance="approved")
        cls.b = new_account("osc", compliance="approved")
        cls.co = new_account("company", compliance="approved")

    @staticmethod
    def _shape(resp):
        """Status e código de erro: o identificador de requisição muda a cada chamada, por desenho."""
        body = resp.json if resp.body else None
        return resp.status, (body or {}).get("code")

    def test_unfollow_of_existing_and_nonexisting_org_are_indistinguishable(self):
        self.assertEqual(self._shape(self.a.delete(f"/v1/network/follow/{self.b.org_id}")),
                         self._shape(self.a.delete(f"/v1/network/follow/{uuid.uuid4()}")))

    def test_unfavorite_of_existing_and_nonexisting_project_are_indistinguishable(self):
        pid = self.b.post("/v1/projects", {"title": "Projeto da B para favoritos", "summary": "Resumo",
                                           "problem": "Problema.", "territory": "BR-MT", "causes": ["educacao"],
                                           "beneficiaries_count": 10, "budget_total_cents": 100_000}).json["id"]
        self.assertEqual(self._shape(self.co.delete(f"/v1/feed/projects/{pid}/favorite")),
                         self._shape(self.co.delete(f"/v1/feed/projects/{uuid.uuid4()}/favorite")))


class CrossTenantMatrix(unittest.TestCase):
    """A → recurso de B, com identificadores REAIS. O que B possui, A não lê, não altera e não descobre."""

    @classmethod
    def setUpClass(cls):
        cls.a = new_account("osc", compliance="approved")
        cls.b = new_account("osc", compliance="approved")
        grant_premium(cls.a)
        grant_premium(cls.b)
        cls.b_project = cls.b.post("/v1/projects", {
            "title": "Projeto da organização B", "summary": "Resumo do projeto da B",
            "problem": "Problema da B.", "territory": "BR-MT", "causes": ["educacao"],
            "beneficiaries_count": 50, "budget_total_cents": 2_000_000}).json["id"]
        cls.b_idea = cls.b.post("/v1/ideas", {"title": "Ideia reservada da organização B"}).json["id"]
        cls.b_diag = cls.b.post("/v1/diagnoses", {"title": "Diagnóstico da B",
                                                  "need_statement": "Necessidade da B."}).json["id"]
        cls.b.post(f"/v1/diagnoses/{cls.b_diag}/versions")
        cls.b_action = cls.b.get(f"/v1/diagnoses/{cls.b_diag}/actions").json["items"][0]["id"]
        cls.b_snapshot = cls.b.post(f"/v1/projects/{cls.b_project}/snapshots", {"label": "retrato B"}).json["id"]
        cls.b.post(f"/v1/projects/{cls.b_project}/risks/scan")
        cls.b_risk = cls.b.get(f"/v1/projects/{cls.b_project}/risks").json["items"][0]["id"]
        tid = next(t["id"] for t in cls.b.get("/v1/document-templates?status=published").json["items"]
                   if t["code"] == "plano_monitoramento_base")
        cls.b_assembly = cls.b.post("/v1/document-assemblies", {"template_id": tid, "title": "Montagem da B",
                                                                "project_id": cls.b_project}).json["id"]
        cls.b_template = cls.b.post("/v1/document-templates", {"code": "modelo_da_b", "version": "1.0",
                                                               "title": "Modelo da B", "kind": "report"}).json["id"]

    def _denied(self, resp, what: str):
        self.assertIn(resp.status, (403, 404), f"{what} respondeu {resp.status}: {resp.body[:200]!r}")

    def test_reads_of_other_tenant_resources_are_denied(self):
        for path, what in (
            (f"/v1/ideas/{self.b_idea}", "ideia"),
            (f"/v1/projects/{self.b_project}/lifecycle", "ciclo de vida"),
            (f"/v1/projects/{self.b_project}/timeline", "linha de tempo"),
            (f"/v1/projects/{self.b_project}/timeline/integrity", "integridade"),
            (f"/v1/projects/{self.b_project}/snapshots", "retratos"),
            (f"/v1/projects/{self.b_project}/state", "estado"),
            (f"/v1/projects/{self.b_project}/risks", "riscos"),
            (f"/v1/diagnoses/{self.b_diag}/analysis", "análise"),
            (f"/v1/diagnoses/{self.b_diag}/versions", "versões"),
            (f"/v1/diagnoses/{self.b_diag}/versions/1", "versão"),
            (f"/v1/diagnoses/{self.b_diag}/actions", "ações"),
            (f"/v1/document-assemblies/{self.b_assembly}", "montagem"),
        ):
            self._denied(self.a.get(path), what)

    def test_writes_on_other_tenant_resources_are_denied(self):
        self._denied(self.a.put(f"/v1/ideas/{self.b_idea}", {"title": "Ideia sequestrada"}), "edição de ideia")
        self._denied(self.a.post(f"/v1/ideas/{self.b_idea}/promote", {}), "promoção de ideia")
        self._denied(self.a.post(f"/v1/projects/{self.b_project}/transitions", {"to_status": "cancelled",
                                                                                "reason": "Invasão"}), "transição")
        self._denied(self.a.post(f"/v1/projects/{self.b_project}/snapshots", {"label": "retrato alheio"}), "retrato")
        self._denied(self.a.post(f"/v1/projects/{self.b_project}/risks",
                                 {"category": "legal", "title": "Risco plantado"}), "risco")
        self._denied(self.a.put(f"/v1/projects/{self.b_project}/risks/{self.b_risk}", {"status": "dismissed",
                                                                                       "resolution_note": "x"}), "risco")
        self._denied(self.a.post(f"/v1/projects/{self.b_project}/risks/scan"), "varredura de risco")
        self._denied(self.a.post(f"/v1/diagnoses/{self.b_diag}/versions"), "versão de diagnóstico")
        self._denied(self.a.post(f"/v1/diagnoses/{self.b_diag}/actions", {"title": "Ação plantada"}), "ação")
        self._denied(self.a.put(f"/v1/diagnoses/{self.b_diag}/actions/{self.b_action}", {"status": "done"}), "ação")
        self._denied(self.a.put(f"/v1/document-assemblies/{self.b_assembly}", {"title": "Montagem sequestrada"}),
                     "montagem")
        self._denied(self.a.post(f"/v1/document-assemblies/{self.b_assembly}/generate", {"format": "pdf"}), "geração")
        self._denied(self.a.post(f"/v1/document-assemblies/{self.b_assembly}/review",
                                 {"approve": True, "note": "Aprovo o documento da outra organização"}), "revisão")
        self._denied(self.a.post(f"/v1/document-templates/{self.b_template}/fields",
                                 {"section": "1", "position": 1, "key": "campo", "label": "Campo",
                                  "field_type": "text"}), "campo de modelo")
        self._denied(self.a.post(f"/v1/document-templates/{self.b_template}/publish"), "publicação de modelo")

    def test_snapshot_of_other_tenant_is_not_comparable_through_own_project(self):
        mine = self.a.post("/v1/projects", {"title": "Projeto da A", "summary": "Resumo da A",
                                            "problem": "Problema da A.", "territory": "BR-MT",
                                            "causes": ["educacao"], "beneficiaries_count": 10,
                                            "budget_total_cents": 100_000}).json["id"]
        s = self.a.post(f"/v1/projects/{mine}/snapshots", {"label": "meu"}).json["id"]
        r = self.a.get(f"/v1/projects/{mine}/snapshots/compare?a={s}&b={self.b_snapshot}")
        self.assertEqual(r.status, 404, r)

    def test_assembly_cannot_point_at_another_tenant_project(self):
        tid = next(t["id"] for t in self.a.get("/v1/document-templates?status=published").json["items"]
                   if t["code"] == "plano_monitoramento_base")
        r = self.a.post("/v1/document-assemblies", {"template_id": tid, "title": "Montagem apontando para a B",
                                                    "project_id": self.b_project})
        self.assertEqual(r.status, 404, r)

    def test_assembly_evidence_must_be_a_document_of_the_same_tenant(self):
        doc = self.b.upload("/v1/documents", "estatuto-b.txt", b"Estatuto da B",
                            {"doc_type": "estatuto_social", "title": "Estatuto da B"}).json["id"]
        tid = next(t["id"] for t in self.a.get("/v1/document-templates?status=published").json["items"]
                   if t["code"] == "projeto_tecnico_base")
        aid = self.a.post("/v1/document-assemblies", {"template_id": tid, "title": "Montagem da A"}).json["id"]
        r = self.a.put(f"/v1/document-assemblies/{aid}", {"evidence": {"doc_estatuto": doc}})
        self.assertEqual(r.status, 404, r)

    def test_rls_blocks_the_new_tables_directly_in_sql(self):
        """Mesmo sem a API: o contexto da organização A não vê nem escreve linha da B."""
        from impacto.db.pool import DbContext
        from tests.support import server
        pool = server()["state"].pool
        ctx_a = DbContext(user_id=self.a.user["id"], org_id=self.a.org_id, org_kind="osc")
        for table, ident in (("ideas", self.b_idea), ("project_risks", self.b_risk),
                             ("project_snapshots", self.b_snapshot), ("diagnosis_versions", None),
                             ("diagnosis_actions", self.b_action), ("document_assemblies", self.b_assembly)):
            with pool.tx(ctx_a, readonly=True) as c:
                if ident:
                    self.assertIsNone(c.one(f"SELECT 1 FROM {table} WHERE id = $1", ident),
                                      f"{table}: linha da outra organização visível")
                self.assertEqual(c.scalar(f"SELECT count(*) FROM {table} WHERE org_id = $1", self.b.org_id), 0,
                                 f"{table}: contagem da outra organização visível")
        with pool.tx(ctx_a) as c:
            self.assertEqual(c.run("UPDATE ideas SET title = 'sequestrada' WHERE id = $1", self.b_idea), 0)

    def test_security_definer_helpers_do_not_leak_other_tenant(self):
        """Função SECURITY DEFINER é a porta de fuga clássica da RLS: confere que nenhuma delas entrega dado alheio."""
        from impacto.db.pool import DbContext
        from tests.support import server
        pool = server()["state"].pool
        ctx_a = DbContext(user_id=self.a.user["id"], org_id=self.a.org_id, org_kind="osc")
        with pool.tx(ctx_a, readonly=True) as c:
            funding = c.one("SELECT committed_cents FROM project_funding($1)", self.b_project)
            self.assertEqual(funding["committed_cents"], 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM ledger_entries WHERE project_id = $1", self.b_project), 0)


class AdminSurfaceTests(unittest.TestCase):
    def test_key_and_calibration_routes_require_platform_admin_with_mfa(self):
        user = new_account("osc")
        for method, path, body in (("GET", "/v1/admin/encryption/keys", None),
                                   ("POST", "/v1/admin/encryption/keys", {"purpose": "field"}),
                                   ("POST", "/v1/admin/encryption/reencrypt", {"table": "users"}),
                                   ("GET", "/v1/admin/match/calibration", None),
                                   ("PUT", "/v1/admin/signature-providers/icp_brasil", {"state": "production"})):
            r = user.request(method, path, body)
            self.assertIn(r.status, (401, 403), f"{method} {path} respondeu {r.status}")

    def test_admin_without_mfa_cannot_touch_keys(self):
        admin, _ = make_admin(mfa=False)
        self.assertIn(admin.get("/v1/admin/encryption/keys").status, (401, 403))

    def test_anonymous_cannot_read_core_routes(self):
        anon = Client()
        for path in ("/v1/ideas", "/v1/readiness", "/v1/document-templates", "/v1/signature-providers",
                     "/v1/project-status-graph", "/v1/risk-rules", "/v1/diagnostic-engine"):
            self.assertEqual(anon.get(path).status, 401, path)


class EncryptionIsolationTests(unittest.TestCase):
    def test_key_tables_are_invisible_to_the_organization_context(self):
        org = new_account("osc")
        from impacto.db.pool import DbContext
        from tests.support import server
        pool = server()["state"].pool
        ctx = DbContext(user_id=org.user["id"], org_id=org.org_id, org_kind="osc")
        with pool.tx(ctx, readonly=True) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM encryption_keys"), 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM encryption_rotations"), 0)

    def test_integration_secret_column_is_not_readable_by_the_app_role(self):
        with db_system() as c, self.assertRaises(Exception) as ctx:
            c.scalar("SELECT secret_cipher FROM integration_credentials LIMIT 1")
        self.assertIn("permission denied", str(ctx.exception).lower())
