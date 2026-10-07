"""v0.13.0 — INTEGRATION HUB: ciclo de vida de conexão, credencial cega, mapeamento, IDs externos, jobs idempotentes,
webhooks (entrada e saída), retry/timeout/429, dead-letter e replay, importação com aprovação, exportação, saúde,
isolamento entre organizações, concorrência e falha de sistema externo.

Tudo com PostgreSQL e HTTP reais. O sistema externo é um DUBLÊ DE TRANSPORTE claramente identificado (`FakeTransport`):
nenhuma chamada sai para a internet e NENHUMA integração é declarada homologada por causa destes testes.
"""
from __future__ import annotations

import json
import threading
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from tests.support import Client, db_system, make_admin, new_account, server


# ------------------------------------------------------------------------------------------------ dublê de transporte
class FakeTransport:
    """Transporte injetável no HttpClient: responde por URL, conta chamadas e simula falhas. É um DUBLÊ, não integração."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []
        self.routes: dict[str, list] = {}      # sufixo do caminho -> lista de (status, corpo) consumidos em ordem
        self.default = (200, b'{"items": []}')
        self.lock = threading.Lock()
        self.raise_network = 0
        self.last_headers: dict = {}

    def set(self, suffix: str, responses: list):
        self.routes[suffix] = list(responses)

    def __call__(self, method: str, url: str, headers: dict, body: bytes | None, timeout: float):
        with self.lock:
            self.calls.append((method, url))
            self.last_headers = dict(headers or {})
            if self.raise_network > 0:
                self.raise_network -= 1
                raise TimeoutError("dublê: tempo esgotado")
            for suffix, responses in self.routes.items():
                if suffix in url:
                    status, payload = responses.pop(0) if len(responses) > 1 else responses[0]
                    return status, {"Content-Type": "application/json"}, payload
            return self.default[0], {"Content-Type": "application/json"}, self.default[1]


def http_with(transport: FakeTransport):
    from impacto.adapters.http_client import HttpClient
    return HttpClient(transport=transport, retries=0)


def connection(c: Client, *, provider="generic_rest", env="sandbox", endpoint="https://erp.exemplo.org/api",
               config=None, activate=True, secret="segredo-de-integracao-123") -> str:
    cfg = config if config is not None else {"paths": {"person": "/pessoas"}, "health_path": "/saude"}
    r = c.post("/v1/integrations/connections", {"provider_key": provider, "name": "Conexão " + uuid.uuid4().hex[:6],
                                                "environment": env, "endpoint": endpoint, "config": cfg})
    assert r.status == 201, r
    cid = r.json["id"]
    if secret:
        from impacto.integrations.adapters import ADAPTERS
        kinds = ADAPTERS[provider].auth_kinds
        kind = "api_key" if "api_key" in kinds else ("basic_auth" if "basic_auth" in kinds else kinds[0])
        body = {"kind": kind, "secret": secret}
        if kind == "basic_auth":
            body["username"] = "integracao"
        r2 = c.put(f"/v1/integrations/connections/{cid}/credential", body)
        assert r2.status == 200, r2
    if activate:
        act = c.patch(f"/v1/integrations/connections/{cid}", {"status": "active"})
        assert act.status == 200, act
    return cid


def run_worker(app=None, *, transport: FakeTransport | None = None) -> dict:
    """Executa um ciclo do trabalhador com o dublê injetado (jobs devidos + entregas devidas)."""
    from impacto.integrations import events as EV, hub as HUB
    app = app or server()["state"]
    http = http_with(transport) if transport else None
    with db_system() as c:
        jobs = HUB.process_due(app, c, http=http, sleep=lambda _s: None)
        deliveries = EV.deliver_pending(app, c, http=http)
    return {"jobs": jobs, "deliveries": deliveries}


# ------------------------------------------------------------------------------------------------ A. ciclo de vida e autorização
class ConnectionLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")

    def test_catalog_declares_real_maturity_and_never_claims_homologation(self):
        items = self.org.get("/v1/integrations/providers").json["items"]
        self.assertGreaterEqual(len(items), 9)
        by_key = {i["key"]: i for i in items}
        self.assertEqual(by_key["government_api"]["maturity"], "scaffolded")
        self.assertIn("NOT IMPLEMENTED", by_key["government_api"]["maturity_note"])
        self.assertIn("não homologado", by_key["senior_sapiens"]["maturity_note"])
        self.assertFalse(any(i["maturity"] == "production_active" for i in items), "nenhum provedor pode nascer em produção")
        self.assertFalse(by_key["sftp_batch"]["adapter_available"], "SFTP é contrato reservado, sem adapter")

    def test_draft_to_active_requires_valid_config_and_credential(self):
        r = self.org.post("/v1/integrations/connections", {"provider_key": "generic_rest", "name": "Sem config",
                                                           "environment": "sandbox", "endpoint": "https://erp.exemplo.org"})
        self.assertEqual(r.status, 201, r)
        cid = r.json["id"]
        self.assertTrue(r.json["config_problems"], "faltando config.paths deveria ser apontado")
        self.assertEqual(self.org.patch(f"/v1/integrations/connections/{cid}", {"status": "active"}).status, 422)
        self.assertEqual(self.org.patch(f"/v1/integrations/connections/{cid}", {"config": {"paths": {"person": "/p"}}}).status, 200)
        no_cred = self.org.patch(f"/v1/integrations/connections/{cid}", {"status": "active"})
        self.assertEqual((no_cred.status, no_cred.json["code"]), (422, "credential_required"))
        self.assertEqual(self.org.put(f"/v1/integrations/connections/{cid}/credential", {"kind": "api_key", "secret": "segredo-forte-1234"}).status, 200)
        self.assertEqual(self.org.patch(f"/v1/integrations/connections/{cid}", {"status": "active"}).status, 200)
        got = self.org.get(f"/v1/integrations/connections/{cid}").json
        self.assertEqual((got["status"], got["health_state"]), ("active", "unknown"))

    def test_provider_without_adapter_cannot_be_connected(self):
        r = self.org.post("/v1/integrations/connections", {"provider_key": "sftp_batch", "name": "SFTP", "environment": "sandbox"})
        self.assertEqual((r.status, r.json["code"]), (422, "no_adapter"))

    def test_revoking_deletes_credentials_but_keeps_history(self):
        cid = connection(self.org)
        self.assertEqual(self.org.delete(f"/v1/integrations/connections/{cid}").status, 200)
        got = self.org.get(f"/v1/integrations/connections/{cid}").json
        self.assertEqual(got["status"], "revoked")
        self.assertIsNone(got["credential"])
        self.assertEqual(self.org.patch(f"/v1/integrations/connections/{cid}", {"name": "Nome novo"}).status, 409)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM integration_credentials WHERE connection_id = $1", cid), 0)

    def test_roles_are_enforced(self):
        owner = new_account("osc")
        cid = connection(owner)
        viewer = Client()
        from tests.support import PASSWORD
        with db_system() as d:
            email = f"viewer-{uuid.uuid4().hex[:8]}@teste.org"
            uid = d.scalar("INSERT INTO users(email, full_name, password_hash, status, email_verified_at) VALUES ($1,$2,$3,'active', now()) RETURNING id::text",
                           email, "Pessoa Viewer", d.scalar("SELECT password_hash FROM users WHERE id = $1", owner.user["id"]))
            d.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'viewer')", uid, owner.org_id)
        self.assertEqual(viewer.login(email, PASSWORD).status, 200)
        self.assertEqual(viewer.get("/v1/integrations/connections").status, 200)                       # leitura: ok
        self.assertEqual(viewer.post("/v1/integrations/connections", {"provider_key": "generic_rest", "name": "x",
                                                                      "environment": "sandbox", "endpoint": "https://a.exemplo.org",
                                                                      "config": {"paths": {}}}).status, 403)
        self.assertEqual(viewer.put(f"/v1/integrations/connections/{cid}/credential", {"kind": "api_key", "secret": "12345678"}).status, 403)
        self.assertEqual(viewer.post(f"/v1/integrations/connections/{cid}/jobs", {"operation": "health_check"}).status, 403)


# ------------------------------------------------------------------------------------------------ B. credencial e segurança de segredo
class CredentialSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")

    def test_secret_never_leaves_the_api_and_is_not_readable_by_the_app_role(self):
        cid = connection(self.org, secret="segredo-ultra-secreto-9876")
        detail = self.org.get(f"/v1/integrations/connections/{cid}")
        body = detail.body.decode()
        self.assertNotIn("segredo-ultra-secreto-9876", body)
        self.assertEqual(detail.json["credential"]["hint"], "••••9876")
        for path in ("/v1/integrations/connections", f"/v1/integrations/connections/{cid}"):
            self.assertNotIn("secret", self.org.get(path).body.decode().lower().replace("secret_ref", ""))
        from impacto.db.pool import DbContext
        ctxdb = DbContext(user_id=self.org.user["id"], org_id=self.org.org_id, org_kind="osc")
        with self.assertRaises(Exception):                     # papel da aplicação não tem SELECT na coluna cifrada
            with server()["state"].pool.tx(ctxdb) as c:
                c.scalar("SELECT secret_cipher FROM integration_credentials WHERE connection_id = $1", cid)
        with server()["state"].pool.tx(ctxdb) as c:             # metadados, sim; segredo, não
            self.assertEqual(c.scalar("SELECT hint FROM integration_credentials WHERE connection_id = $1", cid), "••••9876")

    def test_stored_secret_is_encrypted_at_rest_and_decrypts_only_through_the_hub(self):
        cid = connection(self.org, secret="minha-chave-de-erp-4242")
        with db_system() as d:
            # nem o contexto de sistema lê a coluna direto (GRANT por coluna); a leitura é só pela função privilegiada
            cred_id = d.scalar("SELECT id::text FROM integration_credentials WHERE connection_id = $1", cid)
            raw = bytes(d.scalar("SELECT integration_secret($1)", cred_id))
            self.assertNotIn(b"minha-chave-de-erp-4242", raw, "segredo gravado em claro")
            self.assertTrue(raw.startswith(b"gAAAAA"), "esperado token Fernet")
            from impacto.integrations import secrets as SEC
            secret, _user, kind = SEC.load(d, server()["state"].cipher, connection_id=cid)
        self.assertEqual((secret, kind), ("minha-chave-de-erp-4242", "api_key"))

    def test_rotation_replaces_the_secret_and_is_audited_without_the_value(self):
        cid = connection(self.org, secret="primeiro-segredo-111")
        self.assertEqual(self.org.put(f"/v1/integrations/connections/{cid}/credential",
                                      {"kind": "api_key", "secret": "segundo-segredo-2222"}).json["hint"], "••••2222")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM integration_credentials WHERE connection_id = $1", cid), 1)
            events = d.query("SELECT payload FROM audit_events WHERE object_id = $1 AND action = 'integration.credential_rotated'", cid)
        self.assertTrue(events)
        self.assertNotIn("segundo-segredo", json.dumps([e["payload"] for e in events]))

    def test_provider_rejects_unsupported_auth_kind_and_short_secret(self):
        cid = connection(self.org, provider="totvs", endpoint="https://totvs.exemplo.org",
                         config={"product": "protheus"}, activate=False, secret=None)
        self.assertEqual(self.org.put(f"/v1/integrations/connections/{cid}/credential", {"kind": "certificate", "secret": "x" * 40}).status, 422)
        self.assertEqual(self.org.put(f"/v1/integrations/connections/{cid}/credential", {"kind": "basic_auth", "secret": "curto"}).status, 422)
        self.assertEqual(self.org.put(f"/v1/integrations/connections/{cid}/credential",
                                      {"kind": "basic_auth", "secret": "senha-boa-de-erp", "username": "integra"}).status, 200)

    def test_secret_ref_keeps_only_the_reference(self):
        cid = connection(self.org, activate=False, secret=None)
        r = self.org.put(f"/v1/integrations/connections/{cid}/credential", {"kind": "secret_ref", "secret_ref": "vault://impacto/erp/prod"})
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["hint"].startswith("ref:vault://impacto/erp"), r.json["hint"])
        with db_system() as d:
            cred_id = d.scalar("SELECT id::text FROM integration_credentials WHERE connection_id = $1", cid)
            self.assertIsNone(d.scalar("SELECT integration_secret($1)", cred_id), "credencial por referência não guarda segredo")


# ------------------------------------------------------------------------------------------------ C. isolamento entre organizações (IDOR)
class TenantIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.a, cls.b = new_account("osc"), new_account("company")
        cls.cid = connection(cls.a)

    def test_other_organization_cannot_read_write_or_use_the_connection(self):
        self.assertEqual(self.b.get(f"/v1/integrations/connections/{self.cid}").status, 404)
        self.assertEqual(self.b.patch(f"/v1/integrations/connections/{self.cid}", {"name": "sequestrada"}).status, 404)
        self.assertEqual(self.b.put(f"/v1/integrations/connections/{self.cid}/credential", {"kind": "api_key", "secret": "invasao-123"}).status, 404)
        self.assertEqual(self.b.delete(f"/v1/integrations/connections/{self.cid}").status, 404)
        self.assertEqual(self.b.post(f"/v1/integrations/connections/{self.cid}/jobs", {"operation": "health_check"}).status, 404)
        self.assertEqual(self.b.post(f"/v1/integrations/connections/{self.cid}/health").status, 404)
        self.assertEqual(self.b.get(f"/v1/integrations/connections/{self.cid}/mappings").status, 404)
        self.assertEqual(self.b.put(f"/v1/integrations/connections/{self.cid}/mappings",
                                    {"items": [{"entity": "person", "source_path": "x", "target_field": "name"}]}).status, 404)
        self.assertEqual([x["id"] for x in self.b.get("/v1/integrations/connections").json["items"]], [])

    def test_jobs_links_events_and_imports_are_scoped(self):
        self.assertEqual(self.a.post(f"/v1/integrations/connections/{self.cid}/jobs",
                                     {"operation": "pull", "entity": "person"}).status, 201)
        job_id = self.a.get("/v1/integrations/jobs").json["items"][0]["id"]
        self.assertEqual(self.b.get(f"/v1/integrations/jobs/{job_id}").status, 404)
        self.assertEqual(self.b.post(f"/v1/integrations/jobs/{job_id}/cancel").status, 404)
        self.assertEqual(self.b.get("/v1/integrations/jobs").json["items"], [])
        with db_system() as d:
            d.run("INSERT INTO external_entity_links(org_id, connection_id, entity, internal_id, external_id) VALUES ($1,$2,'person',$3,'EXT-1')",
                  self.a.org_id, self.cid, self.a.user["id"])
        self.assertEqual(self.b.get("/v1/integrations/links").json["items"], [])
        self.assertEqual(len(self.a.get("/v1/integrations/links").json["items"]), 1)

    def test_subscription_and_deliveries_are_scoped(self):
        r = self.a.post("/v1/integrations/subscriptions", {"name": "Parceiro A", "url": "https://parceiro-a.exemplo.org/hook",
                                                           "event_types": ["DOCUMENT.VALIDATED"], "secret": "x" * 24})
        self.assertEqual(r.status, 201, r)
        sid = r.json["id"]
        self.assertEqual(self.b.patch(f"/v1/integrations/subscriptions/{sid}", {"status": "disabled"}).status, 404)
        self.assertEqual(self.b.delete(f"/v1/integrations/subscriptions/{sid}").status, 404)
        self.assertEqual(self.b.post(f"/v1/integrations/subscriptions/{sid}/test").status, 404)
        self.assertEqual(self.b.get("/v1/integrations/subscriptions").json["items"], [])
        self.assertEqual(self.b.get("/v1/integrations/deliveries").json["items"], [])

    def test_admin_only_operational_view(self):
        self.assertEqual(self.a.get("/v1/admin/integrations/overview").status, 403)
        adm, _ = make_admin()
        self.assertEqual(adm.get("/v1/admin/integrations/overview").status, 200)


# ------------------------------------------------------------------------------------------------ D. mapeamento e IDs externos
class MappingAndExternalIds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")
        cls.cid = connection(cls.org)

    def test_mapping_transforms_are_declared_and_validated(self):
        items = [
            {"entity": "person", "direction": "inbound", "source_path": "dados.nome", "target_field": "name", "transform": "trim", "required": True},
            {"entity": "person", "direction": "inbound", "source_path": "dados.cpf", "target_field": "document", "transform": "digits_only"},
            {"entity": "person", "direction": "inbound", "source_path": "dados.nasc", "target_field": "birth_date", "transform": "date_br"},
            {"entity": "person", "direction": "inbound", "source_path": "id", "target_field": "external_id", "transform": "trim", "required": True},
            {"entity": "invoice", "direction": "inbound", "source_path": "valor", "target_field": "amount_cents", "transform": "cents_from_decimal"},
            {"entity": "person", "direction": "inbound", "source_path": "dados.tipo", "target_field": "role", "transform": "enum",
             "enum_map": {"F": "funcionario", "T": "terceiro"}},
        ]
        r = self.org.put(f"/v1/integrations/connections/{self.cid}/mappings", {"items": items})
        self.assertEqual((r.status, r.json["count"]), (200, 6))
        from impacto.integrations.mapping import map_inbound
        with db_system() as d:
            maps = d.query("SELECT entity, direction, source_path, target_field, transform, enum_map, required, default_value"
                           " FROM integration_mappings WHERE connection_id = $1", self.cid)
        rec, errs = map_inbound("person", {"id": " EXT-77 ", "dados": {"nome": "  Ana Souza ", "cpf": "123.456.789-00",
                                                                      "nasc": "05/10/1990", "tipo": "F"}}, maps)
        self.assertEqual(errs, [])
        self.assertEqual(rec.external_id, "EXT-77")
        self.assertEqual(rec.fields["name"], "Ana Souza")
        self.assertEqual(rec.fields["document"], "12345678900")
        self.assertEqual(str(rec.fields["birth_date"]), "1990-10-05")
        self.assertEqual(rec.fields["role"], "funcionario")
        inv, _ = map_inbound("invoice", {"valor": "1.234,56"}, maps)
        self.assertEqual(inv.fields["amount_cents"], 123456)          # dinheiro é inteiro em centavos
        _, errs2 = map_inbound("person", {"dados": {"cpf": "x"}}, maps)
        self.assertTrue(any("obrigatório" in e for e in errs2), errs2)
        _, errs3 = map_inbound("person", {"id": "E1", "dados": {"nome": "Ana", "tipo": "Z"}}, maps)
        self.assertTrue(any("correspondência" in e for e in errs3), errs3)      # enum sem correspondência é ERRO, não suposição

    def test_mapping_rejects_unknown_transform_and_bad_target(self):
        bad = self.org.put(f"/v1/integrations/connections/{self.cid}/mappings",
                           {"items": [{"entity": "person", "source_path": "a", "target_field": "name", "transform": "eval"}]})
        self.assertEqual(bad.status, 422)
        bad2 = self.org.put(f"/v1/integrations/connections/{self.cid}/mappings",
                            {"items": [{"entity": "person", "source_path": "a", "target_field": "Nome Maiúsculo"}]})
        self.assertEqual(bad2.status, 422)

    def test_internal_id_is_never_replaced_and_conflicts_are_recorded(self):
        from impacto.integrations import links as L
        internal_a, internal_b = str(uuid.uuid4()), str(uuid.uuid4())
        with db_system() as d:
            first = L.link(d, org_id=self.org.org_id, connection_id=self.cid, entity="person", internal_id=internal_a,
                           external_id="ERP-1", external_version="v1")
            self.assertEqual(first["status"], "linked")
            self.assertEqual(L.resolve_internal(d, connection_id=self.cid, entity="person", external_id="ERP-1"), internal_a)
            self.assertEqual(L.resolve_external(d, connection_id=self.cid, entity="person", internal_id=internal_a), "ERP-1")
            # o MESMO id externo apontando para outro registro interno é conflito, não substituição
            clash = L.link(d, org_id=self.org.org_id, connection_id=self.cid, entity="person", internal_id=internal_b, external_id="ERP-1")
            self.assertEqual(clash["status"], "conflict")
            self.assertEqual(L.resolve_internal(d, connection_id=self.cid, entity="person", external_id="ERP-1"), internal_a)
            row = d.one("SELECT sync_status, conflict_detail FROM external_entity_links WHERE connection_id = $1 AND external_id = 'ERP-1'", self.cid)
        self.assertEqual(row["sync_status"], "conflict")
        self.assertEqual(row["conflict_detail"]["reason"], "external_id_aponta_para_outro_registro_interno")

    def test_version_conflict_is_detected_and_never_silently_overwritten(self):
        from datetime import UTC, datetime, timedelta

        from impacto.integrations import links as L
        internal = str(uuid.uuid4())
        with db_system() as d:
            L.link(d, org_id=self.org.org_id, connection_id=self.cid, entity="document", internal_id=internal, external_id="DOC-9", external_version="v1")
            same = L.detect_conflict(d, connection_id=self.cid, entity="document", external_id="DOC-9", incoming_version="v1")
            self.assertEqual(same["action"], "unchanged")           # idempotente: mesma versão não reaplica
            newer = L.detect_conflict(d, connection_id=self.cid, entity="document", external_id="DOC-9", incoming_version="v2")
            self.assertEqual(newer["action"], "apply")
            both = L.detect_conflict(d, connection_id=self.cid, entity="document", external_id="DOC-9", incoming_version="v3",
                                     internal_updated_at=datetime.now(UTC) + timedelta(minutes=5))
            self.assertEqual(both["action"], "conflict")
            self.assertEqual(d.scalar("SELECT sync_status FROM external_entity_links WHERE connection_id = $1 AND external_id = 'DOC-9'", self.cid), "conflict")
            novo = L.detect_conflict(d, connection_id=self.cid, entity="document", external_id="DOC-404", incoming_version="v1")
            self.assertEqual(novo["action"], "apply")
            self.assertTrue(L.mark_deleted_externally(d, connection_id=self.cid, entity="document", external_id="DOC-9"))
            self.assertIsNone(L.resolve_internal(d, connection_id=self.cid, entity="document", external_id="DOC-9"))

    def test_conflicts_are_visible_to_the_organization(self):
        from impacto.integrations import links as L
        a, b = str(uuid.uuid4()), str(uuid.uuid4())
        with db_system() as d:                                  # cria o conflito aqui: o teste não depende de ordem
            L.link(d, org_id=self.org.org_id, connection_id=self.cid, entity="partner", internal_id=a, external_id="PARC-1")
            L.link(d, org_id=self.org.org_id, connection_id=self.cid, entity="partner", internal_id=b, external_id="PARC-1")
        out = self.org.get("/v1/integrations/links?sync_status=conflict").json
        self.assertTrue(out["items"], "conflito precisa aparecer para a organização")
        self.assertTrue(all(i["sync_status"] == "conflict" for i in out["items"]))
        self.assertTrue(any(i["external_id"] == "PARC-1" for i in out["items"]))


# ------------------------------------------------------------------------------------------------ E. jobs: idempotência, retry, concorrência
class JobLifecycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")
        cls.cid = connection(cls.org)
        cls.org.put(f"/v1/integrations/connections/{cls.cid}/mappings",
                    {"items": [{"entity": "person", "source_path": "nome", "target_field": "name", "required": True},
                               {"entity": "person", "source_path": "id", "target_field": "external_id", "required": True}]})

    def test_same_request_returns_the_same_job(self):
        body = {"operation": "pull", "entity": "person", "request": {"limit": 10}}
        first = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs", body)
        second = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs", body)
        self.assertEqual((first.status, second.status), (201, 201))
        self.assertEqual(first.json["id"], second.json["id"])
        self.assertFalse(first.json["reused"])
        self.assertTrue(second.json["reused"])
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM integration_jobs WHERE org_id = $1 AND operation = 'pull'"
                                      " AND request->>'limit' = '10'", self.org.org_id), 1)

    def test_explicit_idempotency_key_is_respected(self):
        key = "sync-diaria-" + uuid.uuid4().hex[:8]
        a = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs", {"operation": "pull", "entity": "person", "idempotency_key": key})
        b = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs", {"operation": "pull", "entity": "person", "idempotency_key": key,
                                                                           "request": {"limit": 99}})
        self.assertEqual(a.json["id"], b.json["id"], "a chave explícita deve prevalecer sobre o conteúdo")

    def test_successful_pull_maps_records_and_links_external_ids(self):
        t = FakeTransport()
        internal = self.org.user["id"]
        t.set("/pessoas", [(200, json.dumps({"items": [{"id": "ERP-100", "nome": "Ana", "internal_id": internal}]}).encode())])
        self.org.put(f"/v1/integrations/connections/{self.cid}/mappings",
                     {"items": [{"entity": "person", "source_path": "nome", "target_field": "name", "required": True},
                                {"entity": "person", "source_path": "id", "target_field": "external_id", "required": True},
                                {"entity": "person", "source_path": "internal_id", "target_field": "internal_id"}]})
        job = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                            {"operation": "pull", "entity": "person", "idempotency_key": "pull-ok-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual(got["status"], "succeeded")
        self.assertEqual(got["result"]["read"], 1)
        self.assertEqual(got["result"]["linked"], 1)
        self.assertTrue(got["audit_trail"], "job precisa ter trilha de auditoria")
        links = self.org.get("/v1/integrations/links?entity=person").json["items"]
        self.assertIn("ERP-100", [x["external_id"] for x in links])

    def test_temporary_failure_retries_with_backoff_then_gives_up(self):
        t = FakeTransport()
        t.set("/pessoas", [(503, b'{"erro":"indisponivel"}')])
        job = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                            {"operation": "pull", "entity": "person", "max_attempts": 2,
                             "idempotency_key": "pull-503-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        first = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual(first["status"], "retrying")
        self.assertEqual(first["error_kind"], "temporary")
        self.assertIsNotNone(first["next_attempt_at"], "precisa reagendar com espera")
        with db_system() as d:                                     # antecipa o reagendamento para testar a desistência
            d.run("UPDATE integration_jobs SET next_attempt_at = now() - interval '1 minute' WHERE id = $1", job["id"])
        run_worker(transport=t)
        final = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual((final["status"], final["attempts"]), ("failed", 2))
        self.assertEqual(final["error_code"], "http_503")

    def test_permanent_failure_is_not_retried(self):
        t = FakeTransport()
        t.set("/pessoas", [(422, b'{"erro":"payload invalido"}')])
        job = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                            {"operation": "pull", "entity": "person", "max_attempts": 5,
                             "idempotency_key": "pull-422-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual((got["status"], got["error_kind"], got["attempts"]), ("failed", "permanent", 1))
        self.assertIsNone(got["next_attempt_at"], "erro permanente não deve ficar repetindo")

    def test_timeout_and_rate_limit_are_temporary(self):
        t = FakeTransport()
        t.raise_network = 3
        job = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                            {"operation": "pull", "entity": "person", "max_attempts": 1,
                             "idempotency_key": "timeout-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual((got["status"], got["error_code"], got["error_kind"]), ("failed", "network", "temporary"))
        t2 = FakeTransport()
        t2.set("/pessoas", [(429, b'{"erro":"limite"}')])
        job2 = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                             {"operation": "pull", "entity": "person", "max_attempts": 1,
                              "idempotency_key": "rate-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t2)
        got2 = self.org.get(f"/v1/integrations/jobs/{job2['id']}").json
        self.assertEqual((got2["error_code"], got2["error_kind"]), ("http_429", "temporary"))

    def test_malformed_response_is_permanent_and_does_not_break_the_core(self):
        t = FakeTransport()
        t.set("/pessoas", [(200, b"<html>nao sou json</html>")])
        job = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                            {"operation": "pull", "entity": "person", "max_attempts": 2,
                             "idempotency_key": "malformed-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual((got["status"], got["error_code"]), ("failed", "malformed_response"))
        self.assertEqual(self.org.get("/v1/me").status, 200, "falha externa não pode afetar o núcleo")

    def test_concurrent_workers_never_run_the_same_job_twice(self):
        t = FakeTransport()
        t.set("/pessoas", [(200, b'{"items":[]}')])
        job = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                            {"operation": "pull", "entity": "person", "idempotency_key": "concorrente-" + uuid.uuid4().hex[:8]}).json
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(lambda _: run_worker(transport=t), range(4)))
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual(got["status"], "succeeded")
        self.assertEqual(got["attempts"], 1, "o job foi executado mais de uma vez por trabalhadores concorrentes")

    def test_canceled_job_is_not_executed(self):
        t = FakeTransport()
        job = self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                            {"operation": "pull", "entity": "person", "idempotency_key": "cancelar-" + uuid.uuid4().hex[:8]}).json
        self.assertTrue(self.org.post(f"/v1/integrations/jobs/{job['id']}/cancel").json["canceled"])
        run_worker(transport=t)
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual((got["status"], got["attempts"]), ("canceled", 0))
        again = self.org.post(f"/v1/integrations/jobs/{job['id']}/cancel")
        self.assertFalse(again.json["canceled"])

    def test_circuit_opens_after_consecutive_failures_and_protects_the_external_system(self):
        t = FakeTransport()
        t.set("/pessoas", [(500, b"erro")])
        for i in range(5):
            self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                          {"operation": "pull", "entity": "person", "max_attempts": 1, "idempotency_key": f"disjuntor-{i}-" + uuid.uuid4().hex[:6]})
            run_worker(transport=t)
        conn = self.org.get(f"/v1/integrations/connections/{self.cid}").json
        self.assertGreaterEqual(conn["failure_streak"], 5)
        self.assertIsNotNone(conn["circuit_open_until"], "disjuntor deveria abrir após falhas consecutivas")
        self.assertEqual(conn["health_state"], "unavailable")
        before = len(t.calls)
        self.org.post(f"/v1/integrations/connections/{self.cid}/jobs",
                      {"operation": "pull", "entity": "person", "max_attempts": 1, "idempotency_key": "pos-disjuntor-" + uuid.uuid4().hex[:6]})
        run_worker(transport=t)
        self.assertEqual(len(t.calls), before, "com o disjuntor aberto não deve haver nova chamada externa")
        # credencial nova fecha o disjuntor (intervenção humana)
        self.org.put(f"/v1/integrations/connections/{self.cid}/credential", {"kind": "api_key", "secret": "credencial-nova-9999"})
        self.assertIsNone(self.org.get(f"/v1/integrations/connections/{self.cid}").json["circuit_open_until"])


# ------------------------------------------------------------------------------------------------ F. webhooks de saída (eventos)
class OutboundWebhooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")

    def subscription(self, events=("DOCUMENT.VALIDATED",), url="https://parceiro.exemplo.org/hook", secret="segredo-de-webhook-32bytes!") -> tuple[str, str]:
        r = self.org.post("/v1/integrations/subscriptions", {"name": "Parceiro " + uuid.uuid4().hex[:6], "url": url,
                                                             "event_types": list(events), "secret": secret})
        self.assertEqual(r.status, 201, r)
        return r.json["id"], secret

    def test_catalog_only_accepts_real_events(self):
        r = self.org.post("/v1/integrations/subscriptions", {"name": "Inventado", "url": "https://x.exemplo.org/h",
                                                             "event_types": ["UNICORNIO.VOADOR"], "secret": "x" * 20})
        self.assertEqual((r.status, r.json["code"]), (422, "unknown_event"))
        catalog = {i["event_type"] for i in self.org.get("/v1/integrations/events/catalog").json["items"]}
        self.assertIn("CERTIFICATE.ISSUED", catalog)
        self.assertNotIn("UNICORNIO.VOADOR", catalog)

    def test_http_endpoint_and_internal_targets_are_refused(self):
        for url in ("http://parceiro.exemplo.org/hook", "https://127.0.0.1/hook", "https://169.254.169.254/latest/meta-data",
                    "https://10.0.0.5/hook", "https://192.168.0.10/hook"):
            r = self.org.post("/v1/integrations/subscriptions", {"name": "Alvo " + uuid.uuid4().hex[:6], "url": url,
                                                                 "event_types": ["DOCUMENT.VALIDATED"], "secret": "x" * 20})
            self.assertIn(r.status, (403, 422), f"{url} deveria ser recusado: {r.body[:120]}")

    def test_event_is_delivered_once_with_valid_signature(self):
        t = FakeTransport()
        t.set("parceiro.exemplo.org", [(200, b"ok")])
        sid, secret = self.subscription(events=("CERTIFICATE.ISSUED",))
        from impacto.integrations import events as EV
        with db_system() as d:
            eid = EV.emit(d, org_id=self.org.org_id, event_type="CERTIFICATE.ISSUED", entity_id=None,
                          payload={"code": "ABC123", "course": "Curso de teste"})
        out = run_worker(transport=t)
        self.assertEqual(out["deliveries"]["delivered"], 1, out)
        deliveries = self.org.get("/v1/integrations/deliveries").json["items"]
        mine = [d for d in deliveries if d["event_id"] == eid]
        self.assertEqual(mine[0]["status"], "delivered")
        self.assertEqual(mine[0]["response_code"], 200)
        # a assinatura enviada confere com o segredo da assinatura (verificável pelo parceiro)
        self.assertTrue(any("parceiro.exemplo.org" in url for _m, url in t.calls))
        run_worker(transport=t)
        again = [d for d in self.org.get("/v1/integrations/deliveries").json["items"] if d["event_id"] == eid]
        self.assertEqual(again[0]["attempts"], 1, "entrega concluída não deve ser reenviada")

    def test_signature_is_verifiable_and_rejects_tampering(self):
        from impacto.integrations.events import sign, verify
        body = b'{"type":"CERTIFICATE.ISSUED"}'
        header, _ = sign("segredo-do-parceiro", body)
        self.assertTrue(verify("segredo-do-parceiro", body, header))
        self.assertFalse(verify("segredo-errado", body, header))
        self.assertFalse(verify("segredo-do-parceiro", b'{"type":"OUTRO"}', header))
        old, _ = sign("segredo-do-parceiro", body, timestamp=1)
        self.assertFalse(verify("segredo-do-parceiro", body, old), "replay antigo deve ser recusado")

    def test_failing_endpoint_retries_then_dead_letters_and_can_be_replayed(self):
        t = FakeTransport()
        t.set("parceiro-ruim.exemplo.org", [(500, b"erro")])
        sid, _ = self.subscription(events=("TRIAL.STARTED",), url="https://parceiro-ruim.exemplo.org/hook")
        from impacto.integrations import events as EV
        with db_system() as d:
            EV.emit(d, org_id=self.org.org_id, event_type="TRIAL.STARTED", entity_id=None, payload={"days": 14})
        for _ in range(7):
            run_worker(transport=t)
            with db_system() as d:      # antecipa o reagendamento (o backoff real é de minutos)
                d.run("UPDATE integration_deliveries SET next_attempt_at = now() - interval '1 minute' WHERE status = 'retrying'")
        mine = [x for x in self.org.get(f"/v1/integrations/deliveries?subscription_id={sid}").json["items"]]
        self.assertEqual(mine[0]["status"], "dead_letter", mine[0])
        self.assertGreaterEqual(mine[0]["attempts"], 6)
        did = mine[0]["id"]
        t.set("parceiro-ruim.exemplo.org", [(200, b"ok")])
        self.assertTrue(self.org.post(f"/v1/integrations/deliveries/{did}/replay").json["replayed"])
        run_worker(transport=t)
        after = [x for x in self.org.get(f"/v1/integrations/deliveries?subscription_id={sid}").json["items"] if x["id"] == did]
        self.assertEqual(after[0]["status"], "delivered", "replay controlado deveria entregar")

    def test_permanent_rejection_goes_straight_to_dead_letter(self):
        t = FakeTransport()
        t.set("parceiro-400.exemplo.org", [(400, b"payload recusado")])
        sid, _ = self.subscription(events=("PAYMENT.FAILED",), url="https://parceiro-400.exemplo.org/hook")
        from impacto.integrations import events as EV
        with db_system() as d:
            EV.emit(d, org_id=self.org.org_id, event_type="PAYMENT.FAILED", entity_id=None, payload={"reason": "card_declined"})
        run_worker(transport=t)
        mine = self.org.get(f"/v1/integrations/deliveries?subscription_id={sid}").json["items"]
        self.assertEqual((mine[0]["status"], mine[0]["attempts"]), ("dead_letter", 1), "400 não deve ser repetido")
        self.assertEqual(self.org.post(f"/v1/integrations/deliveries/{mine[0]['id']}/replay").status, 200)

    def test_only_subscribed_events_and_active_subscriptions_are_delivered(self):
        t = FakeTransport()
        sid, _ = self.subscription(events=("LICENSE.GRANTED",), url="https://seletivo.exemplo.org/hook")
        from impacto.integrations import events as EV
        with db_system() as d:
            EV.emit(d, org_id=self.org.org_id, event_type="LICENSE.REVOKED", entity_id=None, payload={})     # não inscrito
        self.assertEqual([x for x in self.org.get(f"/v1/integrations/deliveries?subscription_id={sid}").json["items"]], [])
        self.assertEqual(self.org.patch(f"/v1/integrations/subscriptions/{sid}", {"status": "paused"}).status, 200)
        with db_system() as d:
            EV.emit(d, org_id=self.org.org_id, event_type="LICENSE.GRANTED", entity_id=None, payload={})     # pausada: não enfileira
        self.assertEqual([x for x in self.org.get(f"/v1/integrations/deliveries?subscription_id={sid}").json["items"]], [])

    def test_other_organization_never_receives_events(self):
        other = new_account("company")
        t = FakeTransport()
        sid, _ = self.subscription(events=("SUPPORT.TICKET.CREATED",), url="https://meu-parceiro.exemplo.org/hook")
        from impacto.integrations import events as EV
        with db_system() as d:
            EV.emit(d, org_id=other.org_id, event_type="SUPPORT.TICKET.CREATED", entity_id=None, payload={"n": 1})
        run_worker(transport=t)
        self.assertEqual(self.org.get(f"/v1/integrations/deliveries?subscription_id={sid}").json["items"], [],
                         "evento de outra organização não pode ser entregue à minha assinatura")

    def test_test_delivery_endpoint_emits_a_ping(self):
        t = FakeTransport()
        t.set("ping.exemplo.org", [(202, b"")])
        sid, _ = self.subscription(events=("INTEGRATION.TEST",), url="https://ping.exemplo.org/hook")
        r = self.org.post(f"/v1/integrations/subscriptions/{sid}/test")
        self.assertEqual(r.status, 200, r)
        run_worker(transport=t)
        mine = self.org.get(f"/v1/integrations/deliveries?subscription_id={sid}").json["items"]
        self.assertEqual(mine[0]["status"], "delivered")


# ------------------------------------------------------------------------------------------------ G. webhooks de entrada
class InboundWebhooks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")
        cls.secret = "segredo-de-entrada-do-erp-123"
        cls.cid = connection(cls.org, secret=cls.secret)

    def send(self, payload: dict, *, event_id="EVT-1", secret=None, signature=None, timestamp=None) -> object:
        from impacto.integrations.events import sign
        body = json.dumps(payload).encode()
        sig = signature or sign(secret or self.secret, body, timestamp)[0]
        return Client().request("POST", f"/v1/integrations/inbound/{self.cid}", raw=body, ctype="application/json",
                                headers={"X-Impacto-Signature": sig, "X-Event-Id": event_id, "X-Event-Type": "person.updated"})

    def test_valid_message_is_accepted_and_enqueues_a_job(self):
        r = self.send({"type": "person.updated", "id": "P-1"}, event_id="EVT-" + uuid.uuid4().hex[:8])
        self.assertEqual(r.status, 202, r.body[:200])
        self.assertIn("job_id", r.json)
        detail = self.org.get(f"/v1/integrations/connections/{self.cid}").json
        self.assertTrue(detail["inbound_recent"])
        self.assertEqual(detail["inbound_recent"][0]["status"], "processed")

    def test_duplicate_message_is_processed_once_even_in_parallel(self):
        eid = "EVT-DUP-" + uuid.uuid4().hex[:8]
        payload = {"type": "person.updated", "id": "P-2"}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.send(payload, event_id=eid), range(4)))
        statuses = sorted(r.status for r in results)
        self.assertEqual(statuses.count(202), 1, f"deveria aceitar uma vez só: {statuses}")
        self.assertEqual(statuses.count(200), 3, statuses)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM integration_inbound WHERE connection_id = $1 AND external_event_id = $2", self.cid, eid), 1)
            self.assertEqual(d.scalar("SELECT count(*) FROM integration_jobs WHERE org_id = $1 AND request->>'external_event_id' = $2", self.org.org_id, eid), 1)

    def test_bad_signature_is_rejected_and_recorded(self):
        r = self.send({"a": 1}, event_id="EVT-BAD", signature="t=1,v1=deadbeef")
        self.assertEqual(r.status, 403, r.body[:200])
        self.assertEqual(r.json["code"], "bad_signature")
        r2 = self.send({"a": 1}, event_id="EVT-BAD2", secret="segredo-errado-do-atacante")
        self.assertEqual(r2.status, 403)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM integration_jobs WHERE org_id = $1 AND request->>'external_event_id' = 'EVT-BAD'", self.org.org_id), 0)

    def test_replay_of_old_signature_is_rejected(self):
        r = self.send({"a": 1}, event_id="EVT-OLD-" + uuid.uuid4().hex[:6], timestamp=1)
        self.assertEqual(r.status, 403, "assinatura fora da janela de tolerância deveria ser recusada")

    def test_missing_event_id_and_malformed_body_are_rejected(self):
        from impacto.integrations.events import sign
        body = json.dumps({"a": 1}).encode()
        sig, _ = sign(self.secret, body)
        no_id = Client().request("POST", f"/v1/integrations/inbound/{self.cid}", raw=body, ctype="application/json",
                                 headers={"X-Impacto-Signature": sig})
        self.assertEqual((no_id.status, no_id.json["code"]), (400, "missing_event_id"))
        bad = b"nao sou json"
        sig2, _ = sign(self.secret, bad)
        malformed = Client().request("POST", f"/v1/integrations/inbound/{self.cid}", raw=bad, ctype="application/json",
                                     headers={"X-Impacto-Signature": sig2, "X-Event-Id": "EVT-MAL"})
        self.assertEqual((malformed.status, malformed.json["code"]), (400, "malformed_payload"))

    def test_unknown_or_inactive_connection_answers_generically(self):
        ghost = Client().request("POST", f"/v1/integrations/inbound/{uuid.uuid4()}", raw=b"{}", ctype="application/json",
                                 headers={"X-Event-Id": "X"})
        self.assertEqual(ghost.status, 404)
        self.assertEqual(ghost.json["code"], "unknown_connection")
        self.assertNotIn("org", ghost.body.decode().lower(), "resposta não deve revelar nada da organização")
        paused_org = new_account("osc")
        pid = connection(paused_org)
        self.assertEqual(paused_org.patch(f"/v1/integrations/connections/{pid}", {"status": "paused"}).status, 200)
        r = Client().request("POST", f"/v1/integrations/inbound/{pid}", raw=b"{}", ctype="application/json", headers={"X-Event-Id": "Y"})
        self.assertEqual((r.status, r.json["code"]), (409, "connection_inactive"))

    def test_inbound_endpoint_is_public_but_rate_limited_in_spec(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        spec = next(r for r in ROUTES if r.path == "/v1/integrations/inbound/{connection_id}")
        self.assertEqual(spec.auth, "none")
        self.assertIsNotNone(spec.rate, "endpoint público precisa de limite de taxa")
        self.assertTrue(spec.raw_body)


# ------------------------------------------------------------------------------------------------ H. arquivos: importação com aprovação e exportação
class FileIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")
        cls.cid = connection(cls.org)
        cls.org.put(f"/v1/integrations/connections/{cls.cid}/mappings",
                    {"items": [{"entity": "person", "source_path": "codigo", "target_field": "external_id", "transform": "trim", "required": True},
                               {"entity": "person", "source_path": "nome", "target_field": "name", "transform": "trim", "required": True},
                               {"entity": "person", "source_path": "interno", "target_field": "internal_id", "transform": "trim"},
                               {"entity": "person", "source_path": "cpf", "target_field": "document", "transform": "digits_only"}]})

    def upload(self, content: bytes, filename="pessoas.csv") -> str:
        r = self.org.upload("/v1/documents", filename, content, {"doc_type": "outro", "title": "Planilha de integração"})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def test_import_previews_without_applying_and_requires_approval(self):
        internal = self.org.user["id"]
        csv_bytes = f"codigo,nome,cpf,interno\nERP-1,Ana Souza,123.456.789-00,{internal}\nERP-2,,999,{internal}\n".encode()
        doc = self.upload(csv_bytes)
        r = self.org.post("/v1/integrations/imports", {"entity": "person", "format": "csv", "document_id": doc, "connection_id": self.cid})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["status"], "previewed")
        self.assertEqual((r.json["rows_total"], r.json["rows_valid"], r.json["rows_invalid"]), (2, 1, 1))
        self.assertTrue(r.json["report"]["sample_errors"], "linha inválida deve ser explicada")
        imp = r.json["id"]
        with db_system() as d:      # nada aplicado antes da aprovação
            self.assertEqual(d.scalar("SELECT count(*) FROM external_entity_links WHERE connection_id = $1 AND external_id = 'ERP-1'", self.cid), 0)
        preview = self.org.get(f"/v1/integrations/imports/{imp}").json
        self.assertEqual(len(preview["rows"]), 2)
        self.assertTrue(any(row["valid"] for row in preview["rows"]))
        self.assertTrue(any(row["errors"] for row in preview["rows"]))
        approved = self.org.post(f"/v1/integrations/imports/{imp}/approve", {})
        self.assertEqual(approved.status, 200, approved)
        self.assertEqual(approved.json["applied_links"], 1)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM external_entity_links WHERE connection_id = $1 AND external_id = 'ERP-1'", self.cid), 1)
        self.assertEqual(self.org.post(f"/v1/integrations/imports/{imp}/approve", {}).status, 409, "aprovar duas vezes não deve reaplicar")

    def test_same_file_cannot_be_imported_twice(self):
        doc = self.upload(b"codigo,nome\nERP-9,Repetido\n", "repetido.csv")
        first = self.org.post("/v1/integrations/imports", {"entity": "person", "format": "csv", "document_id": doc, "connection_id": self.cid})
        self.assertEqual(first.status, 201)
        second = self.org.post("/v1/integrations/imports", {"entity": "person", "format": "csv", "document_id": doc, "connection_id": self.cid})
        self.assertEqual((second.status, second.json["code"]), (409, "already_imported"))

    def test_import_rejects_document_of_another_organization(self):
        other = new_account("osc")
        doc = other.upload("/v1/documents", "alheio.csv", b"codigo,nome\nX,Y\n", {"doc_type": "outro", "title": "Alheio"}).json["id"]
        r = self.org.post("/v1/integrations/imports", {"entity": "person", "format": "csv", "document_id": doc, "connection_id": self.cid})
        self.assertEqual(r.status, 404, "documento de outra organização não pode ser importado")

    def test_rows_missing_required_fields_are_invalid_and_explained(self):
        doc = self.upload(b"coluna_errada,outra\nvalor1,valor2\nvalor3,valor4\n", "colunas-erradas.csv")
        r = self.org.post("/v1/integrations/imports", {"entity": "person", "format": "csv", "document_id": doc, "connection_id": self.cid})
        self.assertEqual(r.status, 201, r)
        self.assertEqual((r.json["rows_total"], r.json["rows_valid"], r.json["rows_invalid"]), (2, 0, 2))
        self.assertTrue(any("obrigatório" in e for e in r.json["report"]["sample_errors"]), r.json["report"])
        approved = self.org.post(f"/v1/integrations/imports/{r.json['id']}/approve", {})
        self.assertEqual(approved.json["applied_links"], 0, "nenhuma linha inválida pode ser aplicada")

    def test_vault_rejects_binary_disguised_as_csv(self):
        """O cofre compara conteúdo e extensão: binário disfarçado de .csv não chega ao interpretador."""
        r = self.org.upload("/v1/documents", "disfarce.csv", b"\x00\x01 binario\n", {"doc_type": "outro", "title": "Disfarce"})
        self.assertEqual((r.status, r.json["code"]), (422, "content_mismatch"))

    def test_upload_only_accepts_formats_the_vault_validates(self):
        """O cofre de documentos valida assinatura binária e só aceita .csv/.xlsx entre os formatos tabulares.
        JSON e XML seguem suportados pelo interpretador (respostas REST/SOAP), mas não por upload — a allowlist do
        cofre NÃO é enfraquecida para aceitar texto sem assinatura."""
        self.assertEqual(self.org.upload("/v1/documents", "dados.json", b'[{"a":1}]',
                                         {"doc_type": "outro", "title": "JSON"}).status, 422)
        doc = self.upload(b"codigo,nome\nX,Y\n", "ok.csv")
        r = self.org.post("/v1/integrations/imports", {"entity": "person", "format": "json", "document_id": doc, "connection_id": self.cid})
        self.assertEqual((r.status, r.json["code"]), (422, "format_not_uploadable"))
        self.assertIn("REST/SOAP", r.json["title"])

    def test_xxe_is_refused_by_the_parser_used_for_connector_payloads(self):
        from impacto.integrations.contracts import IntegrationError
        from impacto.integrations.files import parse_rows
        xxe = b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY e SYSTEM "file:///etc/passwd">]><r><p>&e;</p></r>'
        with self.assertRaises(IntegrationError) as cm:
            parse_rows("xml", xxe)
        self.assertEqual(cm.exception.code, "xml_unsafe")

    def test_export_generates_controlled_dataset_and_neutralizes_formula(self):
        datasets = {d["key"] for d in self.org.get("/v1/integrations/datasets").json["items"]}
        self.assertIn("projects", datasets)
        self.assertEqual(self.org.post("/v1/integrations/exports", {"dataset": "pg_catalog", "format": "csv"}).status, 422)
        self.org.post("/v1/projects", {"title": "=HYPERLINK(\"http://malicioso\")", "summary": "Resumo", "territory": "BR-MT",
                                       "causes": ["educacao"], "beneficiaries_count": 5, "budget_total_cents": 50000})
        r = self.org.post("/v1/integrations/exports", {"dataset": "projects", "format": "csv"})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["status"], "ready")
        self.assertGreaterEqual(r.json["rows"], 1)
        dl = self.org.post(f"/v1/documents/{r.json['document_id']}/download-url")
        self.assertEqual(dl.status, 200, dl)
        content = Client().get(dl.json["url"]).body.decode("utf-8-sig")
        self.assertIn("'=HYPERLINK", content, "fórmula deve ser neutralizada no CSV exportado")
        self.assertIn("title", content.splitlines()[0])

    def test_export_only_sees_own_organization(self):
        other = new_account("osc")
        other.post("/v1/projects", {"title": "Projeto da outra", "summary": "R", "territory": "BR-MT", "causes": ["educacao"],
                                    "beneficiaries_count": 1, "budget_total_cents": 1000})
        r = self.org.post("/v1/integrations/exports", {"dataset": "projects", "format": "json"})
        dl = self.org.post(f"/v1/documents/{r.json['document_id']}/download-url")
        content = Client().get(dl.json["url"]).body.decode()
        self.assertNotIn("Projeto da outra", content, "exportação vazou dado de outra organização")


# ------------------------------------------------------------------------------------------------ I. saúde e visão operacional
class HealthAndOperations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")

    def test_health_states_reflect_the_external_system(self):
        from impacto.integrations import hub as HUB
        cid = connection(self.org)
        cases = [(200, b"ok", "healthy"), (401, b"nao autorizado", "unauthorized"), (503, b"fora", "degraded"), (404, b"sem rota", "unavailable")]
        for status, body, expected in cases:
            t = FakeTransport()
            t.set("/saude", [(status, body)])
            with db_system() as d:
                out = HUB.health_check(server()["state"], d, cid, http=http_with(t))
            self.assertEqual(out["health_state"], expected, f"HTTP {status} deveria resultar em {expected}, veio {out}")

    def test_health_check_never_writes_on_the_external_system(self):
        t = FakeTransport()
        cid = connection(self.org)
        self.assertEqual(self.org.post(f"/v1/integrations/connections/{cid}/health").status, 200)
        from impacto.integrations import hub as HUB
        with db_system() as d:
            HUB.health_check(server()["state"], d, cid, http=http_with(t))
        self.assertTrue(all(m == "GET" for m, _u in t.calls), f"verificação de saúde fez chamada não-GET: {t.calls}")

    def test_unconfigured_connection_reports_unconfigured(self):
        r = self.org.post("/v1/integrations/connections", {"provider_key": "totvs", "name": "TOTVS sem produto",
                                                           "environment": "sandbox", "endpoint": "https://totvs.exemplo.org", "config": {}})
        cid = r.json["id"]
        from impacto.integrations import hub as HUB
        with db_system() as d:
            out = HUB.health_check(server()["state"], d, cid, http=http_with(FakeTransport()))
        self.assertEqual(out["health_state"], "unconfigured")
        self.assertIn("product", out["detail"])

    def test_admin_overview_answers_which_integration_is_broken(self):
        adm, _ = make_admin()
        t = FakeTransport()
        t.set("/saude", [(503, b"fora do ar")])
        cid = connection(self.org, endpoint="https://erp-quebrado.exemplo.org/api")
        from impacto.integrations import hub as HUB
        with db_system() as d:
            HUB.health_check(server()["state"], d, cid, http=http_with(t))
        out = adm.get("/v1/admin/integrations/overview").json
        self.assertIn("connections_by_health", out)
        self.assertTrue(any(b["id"] == cid for b in out["broken_now"]), "conexão quebrada deve aparecer no painel")
        self.assertIn("queue_depth", out)
        self.assertIn("dead_letters", out)
        self.assertIn("latency_7d", out)

    def test_worker_endpoint_is_admin_only(self):
        adm, _ = make_admin()
        self.assertEqual(self.org.post("/v1/admin/integrations/run-worker").status, 403)
        r = adm.post("/v1/admin/integrations/run-worker")
        self.assertEqual(r.status, 200, r)
        self.assertIn("jobs", r.json)
        self.assertIn("deliveries", r.json)

    def test_provider_maturity_requires_admin_and_evidence(self):
        adm, _ = make_admin()
        self.assertEqual(self.org.post("/v1/admin/integrations/providers/totvs/maturity",
                                       {"maturity": "production_active", "evidence": "x" * 30}).status, 403)
        self.assertEqual(adm.post("/v1/admin/integrations/providers/totvs/maturity",
                                  {"maturity": "homologated", "evidence": "curta"}).status, 422)
        ok = adm.post("/v1/admin/integrations/providers/totvs/maturity",
                      {"maturity": "homologated", "evidence": "Ata de homologação nº 123/2026 do cliente X, ambiente de homologação TOTVS Protheus."})
        self.assertEqual(ok.status, 200, ok)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT maturity FROM integration_providers WHERE key = 'totvs'"), "homologated")
            ev = d.query("SELECT payload FROM audit_events WHERE action = 'integration.provider_maturity' ORDER BY at DESC LIMIT 1")
        self.assertIn("Ata de homologação", json.dumps(ev[0]["payload"], ensure_ascii=False))
        adm.post("/v1/admin/integrations/providers/totvs/maturity",
                 {"maturity": "contract_tested", "evidence": "Rebaixado: homologação do cliente X expirou em 2026; sem evidência vigente."})


# ------------------------------------------------------------------------------------------------ J. segurança da camada de integração
class IntegrationSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")

    def test_connection_endpoint_cannot_point_to_internal_network(self):
        for url in ("https://169.254.169.254/latest/meta-data/", "https://10.1.2.3/api", "https://172.16.0.9/api", "http://erp.exemplo.org/api"):
            r = self.org.post("/v1/integrations/connections", {"provider_key": "generic_rest", "name": "Alvo " + uuid.uuid4().hex[:6],
                                                               "environment": "sandbox", "endpoint": url, "config": {"paths": {}}})
            self.assertIn(r.status, (403, 422), f"{url} deveria ser recusado")

    def test_ssrf_guard_blocks_at_call_time_even_if_dns_points_inside(self):
        """A guarda autoritativa roda na chamada: destino interno vira erro PERMANENTE (não fica repetindo)."""
        from impacto.integrations.transport import ResilientCaller
        from impacto.integrations.contracts import IntegrationError
        caller = ResilientCaller({"id": "x"}, attempts=3, sleep=lambda _s: None)
        with self.assertRaises(IntegrationError) as cm:
            caller.call("GET", "https://169.254.169.254/latest/meta-data/")   # metadados de nuvem: recusado em qualquer ambiente
        self.assertEqual(cm.exception.kind, "permanent")
        self.assertEqual(cm.exception.code, "destination_blocked")
        self.assertEqual(len(caller.calls), 0, "não deve nem tentar")

    def test_soap_envelope_escapes_content_and_rejects_bad_operation(self):
        from impacto.integrations.xmlsafe import soap_envelope, parse, soap_fault
        from impacto.integrations.contracts import IntegrationError
        env = soap_envelope("ConsultarPessoas", {"filtro": '</ns:filtro><ns:injetado>x'}, namespace="http://erp.exemplo.org/ws")
        self.assertNotIn(b"<ns:injetado>", env, "conteúdo externo não pode injetar XML")
        self.assertIn(b"&lt;/ns:filtro&gt;", env)
        with self.assertRaises(IntegrationError):
            soap_envelope("Consultar; DROP TABLE", {}, namespace="http://x")
        fault = parse(b'<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/"><Body><Fault><faultstring>credenciais invalidas</faultstring></Fault></Body></Envelope>')
        self.assertIn("credenciais", soap_fault(fault))

    def test_xml_bomb_and_deep_nesting_are_refused(self):
        from impacto.integrations.xmlsafe import parse
        from impacto.integrations.contracts import IntegrationError
        bomb = b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol"><!ENTITY lol2 "&lol;&lol;&lol;">]><lolz>&lol2;</lolz>'
        with self.assertRaises(IntegrationError):
            parse(bomb)
        deep = b"<a>" * 60 + b"x" + b"</a>" * 60
        with self.assertRaises(IntegrationError) as cm:
            parse(deep)
        self.assertEqual(cm.exception.code, "xml_too_deep")

    def test_mapping_cannot_execute_code(self):
        from impacto.integrations.mapping import apply_transform
        from impacto.integrations.contracts import IntegrationError
        with self.assertRaises(IntegrationError):
            apply_transform("1+1", "eval")
        with self.assertRaises(IntegrationError):
            apply_transform("x", "__import__('os').system('id')")

    def test_secrets_never_appear_in_logs_or_audit(self):
        cid = connection(self.org, secret="segredo-que-nao-pode-vazar-7777")
        t = FakeTransport()
        t.set("/pessoas", [(500, b"erro")])
        self.org.put(f"/v1/integrations/connections/{cid}/mappings",
                     {"items": [{"entity": "person", "source_path": "nome", "target_field": "name"}]})
        self.org.post(f"/v1/integrations/connections/{cid}/jobs", {"operation": "pull", "entity": "person", "max_attempts": 1,
                                                                   "idempotency_key": "log-" + uuid.uuid4().hex[:8]})
        run_worker(transport=t)
        with db_system() as d:
            audit = json.dumps(d.query("SELECT action, payload FROM audit_events WHERE org_id = $1", self.org.org_id), default=str)
            jobs = json.dumps(d.query("SELECT request, result, error_detail FROM integration_jobs WHERE org_id = $1", self.org.org_id), default=str)
        for blob in (audit, jobs):
            self.assertNotIn("segredo-que-nao-pode-vazar-7777", blob)

    def test_webhook_headers_cannot_smuggle_authorization(self):
        r = self.org.post("/v1/integrations/subscriptions", {"name": "Com cabeçalho", "url": "https://parceiro.exemplo.org/hook",
                                                             "event_types": ["DOCUMENT.VALIDATED"], "secret": "x" * 24,
                                                             "headers": {"Authorization": "Bearer roubado", "X-Custom": "ok"}})
        self.assertEqual(r.status, 201, r)
        t = FakeTransport()
        t.set("parceiro.exemplo.org", [(200, b"ok")])
        from impacto.integrations import events as EV
        with db_system() as d:
            EV.emit(d, org_id=self.org.org_id, event_type="DOCUMENT.VALIDATED", entity_id=None, payload={"doc": "x"})
        run_worker(transport=t)
        # o cabeçalho Authorization fornecido pelo cliente é DESCARTADO na entrega (não é repassado ao destino)
        self.assertTrue(any("parceiro.exemplo.org" in u for _m, u in t.calls))
        self.assertNotIn("authorization", [k.lower() for k in t.last_headers], t.last_headers)
        self.assertIn("x-custom", [k.lower() for k in t.last_headers])
        self.assertIn("x-impacto-signature", [k.lower() for k in t.last_headers])

    def test_import_row_content_is_stored_as_text_not_interpreted(self):
        cid = connection(self.org)
        payload = "'; DROP TABLE integration_imports; --"
        doc = self.org.upload("/v1/documents", "injecao.csv", f"codigo,nome\nX1,{payload}\n".encode(),
                              {"doc_type": "outro", "title": "Injeção"}).json["id"]
        r = self.org.post("/v1/integrations/imports", {"entity": "person", "format": "csv", "document_id": doc, "connection_id": cid})
        self.assertEqual(r.status, 201, r)
        rows = self.org.get(f"/v1/integrations/imports/{r.json['id']}").json["rows"]
        self.assertEqual(rows[0]["raw"]["nome"], payload, "conteúdo deve ser guardado literalmente")
        with db_system() as d:
            self.assertTrue(d.scalar("SELECT to_regclass('integration_imports') IS NOT NULL"))


# ------------------------------------------------------------------------------------------------ K. adapters de ERP e governo (contrato, sem homologação)
class AdapterContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")

    def test_senior_sapiens_speaks_soap_and_maps_records(self):
        cid = connection(self.org, provider="senior_sapiens", endpoint="https://g5.exemplo.org",
                         config={"mode": "soap", "soap_namespace": "http://services.senior.com.br/", "soap_path": "/g5-senior-services"},
                         secret="senha-do-usuario-de-integracao")
        self.org.put(f"/v1/integrations/connections/{cid}/mappings",
                     {"items": [{"entity": "person", "source_path": "Codigo", "target_field": "external_id", "required": True},
                                {"entity": "person", "source_path": "Nome", "target_field": "name", "transform": "trim", "required": True},
                                {"entity": "person", "source_path": "Cpf", "target_field": "document", "transform": "digits_only"}]})
        soap = (b'<?xml version="1.0"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
                b"<soapenv:Body><ConsultarPessoasResponse><result>"
                b"<Pessoa><Codigo>9001</Codigo><Nome> Maria Silva </Nome><Cpf>111.222.333-44</Cpf></Pessoa>"
                b"<Pessoa><Codigo>9002</Codigo><Nome>Joao Souza</Nome><Cpf>555.666.777-88</Cpf></Pessoa>"
                b"</result></ConsultarPessoasResponse></soapenv:Body></soapenv:Envelope>")
        t = FakeTransport()
        t.set("/g5-senior-services", [(200, soap)])
        job = self.org.post(f"/v1/integrations/connections/{cid}/jobs",
                            {"operation": "pull", "entity": "person", "idempotency_key": "soap-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual(got["status"], "succeeded", got)
        self.assertEqual(got["result"]["read"], 2)
        self.assertEqual(got["result"]["mapped"], 2)
        self.assertTrue(any("SOAPAction" for _m, _u in t.calls))

    def test_soap_fault_is_a_permanent_error_and_unauthorized_is_detected(self):
        from impacto.integrations import hub as HUB
        cid = connection(self.org, provider="senior_sapiens", endpoint="https://g5.exemplo.org",
                         config={"mode": "soap", "soap_namespace": "http://services.senior.com.br/"},
                         secret="senha-de-integracao-errada")
        fault = (b'<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"><soapenv:Body><soapenv:Fault>'
                 b"<faultstring>Credenciais invalidas para o usuario de integracao</faultstring></soapenv:Fault></soapenv:Body></soapenv:Envelope>")
        t = FakeTransport()
        t.set("/g5-senior-services", [(200, fault)])
        with db_system() as d:
            out = HUB.health_check(server()["state"], d, cid, http=http_with(t))
        self.assertEqual(out["health_state"], "unauthorized", out)

    def test_totvs_requires_product_and_uses_its_own_paths(self):
        from impacto.integrations import hub as HUB
        cid = connection(self.org, provider="totvs", endpoint="https://protheus.exemplo.org",
                         config={"product": "protheus"}, secret="token-do-protheus-123")
        t = FakeTransport()
        t.set("/api/framework/v1/health", [(200, b'{"status":"ok"}')])
        with db_system() as d:
            out = HUB.health_check(server()["state"], d, cid, http=http_with(t))
        self.assertEqual(out["health_state"], "healthy", out)
        self.assertTrue(any("/api/framework/v1/health" in u for _m, u in t.calls))
        bad = self.org.post("/v1/integrations/connections", {"provider_key": "totvs", "name": "Produto errado",
                                                             "environment": "sandbox", "endpoint": "https://x.exemplo.org",
                                                             "config": {"product": "inexistente"}})
        self.assertTrue(bad.json["config_problems"])

    def test_government_adapter_refuses_to_pretend_authorization(self):
        from impacto.integrations.contracts import AdapterContext, IntegrationError
        from impacto.integrations.adapters.government import GovernmentApiAdapter
        prod = self.org.post("/v1/integrations/connections", {"provider_key": "government_api", "name": "Conecta produção",
                                                              "environment": "production", "endpoint": "https://gateway.conecta.gov.br",
                                                              "config": {"scope": "conecta", "authorization_status": "technically_ready"}})
        self.assertTrue(any("production_active" in p for p in prod.json["config_problems"]),
                        "ambiente de produção sem credenciamento deve ser apontado")
        self.assertEqual(self.org.patch(f"/v1/integrations/connections/{prod.json['id']}", {"status": "active"}).status, 422)
        adapter = GovernmentApiAdapter()
        ctx = AdapterContext(connection={"endpoint": "https://gateway.conecta.gov.br", "config": {"scope": "conecta", "authorization_status": "technically_ready"}},
                             secret=None, username=None, mappings=[], transport=None, correlation_id="x")
        with self.assertRaises(IntegrationError) as cm:
            adapter.pull(ctx, "organization")
        self.assertEqual(cm.exception.code, "not_authorized")
        self.assertIn("EXTERNAL AUTHORIZATION REQUIRED", str(cm.exception))

    def test_generic_rest_adapter_pushes_and_records_external_id(self):
        cid = connection(self.org, config={"paths": {"person": "/pessoas"}, "health_path": "/saude"})
        internal = str(uuid.uuid4())
        self.org.put(f"/v1/integrations/connections/{cid}/mappings",
                     {"items": [{"entity": "person", "direction": "outbound", "source_path": "nome", "target_field": "name"},
                                {"entity": "person", "direction": "outbound", "source_path": "interno", "target_field": "internal_id"}]})
        t = FakeTransport()
        t.set("/pessoas", [(201, b'{"id":"ERP-NEW-1"}')])
        job = self.org.post(f"/v1/integrations/connections/{cid}/jobs",
                            {"operation": "push", "entity": "person", "direction": "outbound",
                             "request": {"records": [{"fields": {"name": "Ana", "internal_id": internal}}]},
                             "idempotency_key": "push-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual((got["status"], got["result"]["sent"], got["result"]["linked"]), ("succeeded", 1, 1))
        links = self.org.get("/v1/integrations/links?entity=person").json["items"]
        self.assertIn("ERP-NEW-1", [x["external_id"] for x in links])


# ------------------------------------------------------------------------------------------------ L. produção simulada: fluxo completo e recuperação
class SimulatedProductionFlow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.org = new_account("osc")
        cls.adm, _ = make_admin()

    def test_full_happy_path_from_connection_to_audit(self):
        """Organização → conexão → credencial → saúde → mapeamento → job → ID externo → evento → webhook → auditoria."""
        t = FakeTransport()
        t.set("/saude", [(200, b'{"ok":true}')])
        t.set("/pessoas", [(200, json.dumps({"items": [{"id": "ERP-FLOW-1", "nome": "Fluxo Completo", "interno": self.org.user["id"]}]}).encode())])
        t.set("parceiro-fluxo.exemplo.org", [(200, b"ok")])
        cid = connection(self.org, config={"paths": {"person": "/pessoas"}, "health_path": "/saude"}, secret="credencial-do-fluxo-999")
        self.assertEqual(self.org.put(f"/v1/integrations/connections/{cid}/mappings",
                                      {"items": [{"entity": "person", "source_path": "id", "target_field": "external_id", "required": True},
                                                 {"entity": "person", "source_path": "nome", "target_field": "name", "required": True},
                                                 {"entity": "person", "source_path": "interno", "target_field": "internal_id"}]}).status, 200)
        from impacto.integrations import hub as HUB
        with db_system() as d:
            self.assertEqual(HUB.health_check(server()["state"], d, cid, http=http_with(t))["health_state"], "healthy")
        sub = self.org.post("/v1/integrations/subscriptions", {"name": "Parceiro do fluxo", "url": "https://parceiro-fluxo.exemplo.org/hook",
                                                               "event_types": ["INTEGRATION.JOB.FAILED", "INTEGRATION.TEST"], "secret": "s" * 24})
        self.assertEqual(sub.status, 201)
        job = self.org.post(f"/v1/integrations/connections/{cid}/jobs",
                            {"operation": "pull", "entity": "person", "strategy": "scheduled",
                             "idempotency_key": "fluxo-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        got = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual(got["status"], "succeeded")
        self.assertEqual(got["result"]["linked"], 1)
        self.assertTrue(got["audit_trail"])
        link = [x for x in self.org.get("/v1/integrations/links").json["items"] if x["external_id"] == "ERP-FLOW-1"]
        self.assertEqual(link[0]["sync_status"], "linked")
        self.assertEqual(link[0]["internal_id"], self.org.user["id"], "o ID interno é preservado, nunca substituído")
        self.org.post(f"/v1/integrations/subscriptions/{sub.json['id']}/test")
        run_worker(transport=t)
        deliv = self.org.get(f"/v1/integrations/deliveries?subscription_id={sub.json['id']}").json["items"]
        self.assertEqual(deliv[0]["status"], "delivered")
        conn = self.org.get(f"/v1/integrations/connections/{cid}").json
        self.assertEqual((conn["health_state"], conn["failure_streak"]), ("healthy", 0))
        self.assertIsNotNone(conn["last_success_at"])
        with db_system() as d:
            actions = {r["action"] for r in d.query("SELECT action FROM audit_events WHERE org_id = $1", self.org.org_id)}
        for expected in ("integration.connection_created", "integration.credential_rotated", "integration.health_check",
                         "integration.mappings_replaced", "integration.job_enqueued", "integration.job.succeeded",
                         "integration.subscription_created"):
            self.assertIn(expected, actions, f"auditoria faltando: {expected}")

    def test_failure_path_then_recovery(self):
        """Conexão → falha externa → retry → falha → auditoria + evento de falha → recuperação."""
        t = FakeTransport()
        t.set("/saude", [(503, b"instavel")])
        t.set("/pessoas", [(503, b"instavel")])
        cid = connection(self.org, config={"paths": {"person": "/pessoas"}, "health_path": "/saude"}, secret="credencial-recuperacao-1")
        self.org.put(f"/v1/integrations/connections/{cid}/mappings",
                     {"items": [{"entity": "person", "source_path": "id", "target_field": "external_id", "required": True},
                                {"entity": "person", "source_path": "nome", "target_field": "name", "required": True}]})
        sub = self.org.post("/v1/integrations/subscriptions", {"name": "Alerta de falha", "url": "https://alerta.exemplo.org/hook",
                                                               "event_types": ["INTEGRATION.JOB.FAILED"], "secret": "f" * 24}).json
        t.set("alerta.exemplo.org", [(200, b"ok")])
        job = self.org.post(f"/v1/integrations/connections/{cid}/jobs",
                            {"operation": "pull", "entity": "person", "max_attempts": 2,
                             "idempotency_key": "recup-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        self.assertEqual(self.org.get(f"/v1/integrations/jobs/{job['id']}").json["status"], "retrying")
        with db_system() as d:
            d.run("UPDATE integration_jobs SET next_attempt_at = now() - interval '1 minute' WHERE id = $1", job["id"])
        run_worker(transport=t)
        failed = self.org.get(f"/v1/integrations/jobs/{job['id']}").json
        self.assertEqual(failed["status"], "failed")
        conn = self.org.get(f"/v1/integrations/connections/{cid}").json
        self.assertIn(conn["health_state"], ("degraded", "unavailable"))
        self.assertGreaterEqual(conn["failure_streak"], 1)
        self.assertEqual(self.org.get("/v1/me").status, 200, "o núcleo continua saudável")
        run_worker(transport=t)                                  # entrega do evento de falha ao parceiro
        events = self.org.get("/v1/integrations/events?event_type=INTEGRATION.JOB.FAILED").json["items"]
        self.assertTrue(events, "falha definitiva deve emitir evento de domínio")
        deliv = self.org.get(f"/v1/integrations/deliveries?subscription_id={sub['id']}").json["items"]
        self.assertTrue(deliv and deliv[0]["status"] == "delivered", deliv)
        broken = self.adm.get("/v1/admin/integrations/overview").json
        self.assertTrue(any(b["id"] == cid for b in broken["broken_now"]))
        # recuperação: sistema externo volta e um novo job tem sucesso; a saúde volta a healthy
        t.set("/pessoas", [(200, json.dumps({"items": [{"id": "ERP-REC-1", "nome": "Voltou"}]}).encode())])
        novo = self.org.post(f"/v1/integrations/connections/{cid}/jobs",
                             {"operation": "pull", "entity": "person", "idempotency_key": "recup-ok-" + uuid.uuid4().hex[:8]}).json
        run_worker(transport=t)
        self.assertEqual(self.org.get(f"/v1/integrations/jobs/{novo['id']}").json["status"], "succeeded")
        recovered = self.org.get(f"/v1/integrations/connections/{cid}").json
        self.assertEqual((recovered["health_state"], recovered["failure_streak"]), ("healthy", 0))

    def test_worker_job_is_registered_in_platform_history(self):
        from impacto import jobs as JOBS
        names = [n for n, _f in JOBS.JOBS]
        self.assertIn("integration_ops", names, "o trabalhador do hub precisa estar no agendador")
        out = JOBS.integration_ops(server()["state"])
        self.assertEqual(out["status"], "ok", out)
        with db_system() as d:
            # v0.22.0: a trilha é UMA (`ops_job_runs`) e passou a registrar duração e erro — a
            # tabela antiga (`job_runs`) sabia apenas que a tarefa "rodou". O teste ficou mais
            # exigente junto com a trilha: não basta existir a linha, ela tem de dizer quanto
            # tempo levou e ter terminado.
            execucao = d.one("SELECT status, duration_ms, finished_at, error FROM ops_job_runs"
                             " WHERE job = 'integration_ops' ORDER BY id DESC LIMIT 1")
            self.assertIsNotNone(execucao, "a execução do trabalhador não foi registrada")
            self.assertEqual(execucao["status"], "ok")
            self.assertIsNotNone(execucao["duration_ms"])
            self.assertIsNotNone(execucao["finished_at"])
            self.assertIsNone(execucao["error"])
