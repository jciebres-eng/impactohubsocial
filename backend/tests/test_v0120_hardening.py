"""v0.12.x — endurecimento final (baseline técnica): varredura de autorização em TODAS as operações da API,
IDOR de escrita, condições de corrida reais (threads), higiene de erros, limites de entrada, invariantes de dinheiro e datas.
Nada aqui depende de serviço externo: PostgreSQL e servidor HTTP reais. Estes testes tentam QUEBRAR o sistema."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from tests.support import Client, db_system, make_admin, new_account, server
from tests.test_v0110_monetization import stripe_mode
from tests.test_v0120_knowledge import staff, uniq

PLACEHOLDER = {"token": "x" * 44, "code": "ABCDEFGHJKMN", "doc": "termos", "priority": "normal",
               "obj_type": "article", "object_type": "article_version", "role": "editor", "slug": "x", "key": "x"}


def url_for(path: str) -> str:
    """Rota declarada → URL concreta (valores são irrelevantes: a negativa deve vir ANTES do handler)."""
    return re.sub(r"\{([a-z_]+)\}", lambda m: PLACEHOLDER.get(m.group(1), str(uuid.uuid4())), path)


def all_routes() -> list:
    from impacto import api
    from impacto.http import ROUTES
    api.load_all()
    return list(ROUTES)


# ------------------------------------------------------------------------------------------------ varredura de autorização
class RouteAuthorizationSweep(unittest.TestCase):
    """Cobertura de autorização sobre TODAS as operações registradas (não por amostragem)."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.routes = all_routes()
        cls.anon = Client()
        cls.user = new_account("osc")

    def test_catalog_is_not_empty_and_matches_openapi(self):
        self.assertGreater(len(self.routes), 400, "catálogo de rotas suspeito")
        spec = self.anon.get("/v1/openapi.json")
        self.assertEqual(spec.status, 200)
        ops = sum(1 for p, item in spec.json["paths"].items() for m in item if m in ("get", "post", "put", "patch", "delete"))
        self.assertEqual(ops, len(self.routes), "OpenAPI e registro de rotas divergem")

    def test_every_non_public_route_rejects_anonymous(self):
        bad = []
        for r in self.routes:
            if r.auth == "none":
                continue
            resp = self.anon.request(r.method, url_for(r.path))
            if resp.status != 401:
                bad.append(f"{r.method} {r.path} -> {resp.status} {resp.body[:120]!r}")
        self.assertEqual(bad, [], "rotas que não exigiram autenticação (ou vazaram antes de autorizar):\n" + "\n".join(bad))

    def test_every_admin_route_rejects_ordinary_user(self):
        bad = []
        for r in self.routes:
            if r.auth != "admin":
                continue
            resp = self.user.request(r.method, url_for(r.path))
            if resp.status != 403 or (resp.json or {}).get("code") not in ("admin_only", "mfa_required", "role_required"):
                bad.append(f"{r.method} {r.path} -> {resp.status} {resp.body[:120]!r}")
        self.assertEqual(bad, [], "rotas administrativas acessíveis a usuária comum:\n" + "\n".join(bad))

    def test_admin_routes_require_mfa_even_for_platform_admin(self):
        adm, _ = make_admin(mfa=False)
        blocked = 0
        for r in self.routes:
            if r.auth != "admin":
                continue
            resp = adm.request(r.method, url_for(r.path))
            self.assertEqual(resp.status, 403, f"{r.method} {r.path} -> {resp.status}")
            self.assertEqual((resp.json or {}).get("code"), "mfa_required", f"{r.method} {r.path}")
            blocked += 1
        self.assertGreater(blocked, 100)

    def test_no_route_answers_with_server_error_to_anonymous(self):
        """Nenhuma rota deve estourar 5xx por entrada anônima/placeholder (estado impossível vira erro tratado)."""
        bad = []
        for r in self.routes:
            resp = self.anon.request(r.method, url_for(r.path))
            if resp.status >= 500:
                bad.append(f"{r.method} {r.path} -> {resp.status} {resp.body[:160]!r}")
        self.assertEqual(bad, [], "erro de servidor em rota anônima:\n" + "\n".join(bad))


# ------------------------------------------------------------------------------------------------ IDOR de leitura E de escrita
class CrossTenantIdor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.a, cls.b = new_account("osc"), new_account("osc")
        cls.sup = staff("support")
        r = cls.a.post("/v1/support/tickets", {"category": "question", "subject": "Chamado da organização A", "message": "Mensagem privada da A."})
        assert r.status == 201, r
        cls.ticket = r.json["id"]

    def test_other_tenant_cannot_read_write_or_rate_ticket(self):
        self.assertEqual(self.b.get(f"/v1/support/tickets/{self.ticket}").status, 404)
        self.assertEqual(self.b.post(f"/v1/support/tickets/{self.ticket}/messages", {"body": "injetando mensagem"}).status, 404)
        self.assertEqual(self.b.post(f"/v1/support/tickets/{self.ticket}/rate", {"score": 1}).status, 404)
        self.assertEqual(self.b.post(f"/v1/support/tickets/{self.ticket}/close").status, 404)
        msgs = self.a.get(f"/v1/support/tickets/{self.ticket}").json["messages"]
        self.assertEqual([m["body"] for m in msgs], ["Mensagem privada da A."], "escrita cruzada vazou para o chamado")

    def test_trial_and_demo_requests_are_scoped_to_the_organization(self):
        r = self.a.post("/v1/help/trial-requests", {"users_count": 3, "purpose": "Avaliar o módulo de captação com a equipe.", "responsible": "Resp A"})
        self.assertEqual(r.status, 201, r)
        self.assertEqual([x["id"] for x in self.b.get("/v1/help/trial-requests").json["items"]], [])
        self.assertIn(r.json["id"], [x["id"] for x in self.a.get("/v1/help/trial-requests").json["items"]])

    def test_checklist_progress_and_feedback_are_per_user(self):
        scope = f"article:{uniq('scope')}"
        self.assertEqual(self.a.put("/v1/help/checklists", {"scope": scope, "checked": [0, 2]}).status, 200)
        self.assertEqual(self.a.get(f"/v1/help/checklists?scope={scope}").json["checked"], [0, 2])
        self.assertEqual(self.b.get(f"/v1/help/checklists?scope={scope}").json["checked"], [])

    def test_uuid_of_another_tenant_never_returns_data_on_core_objects(self):
        pid = self.a.post("/v1/projects", {"title": "Projeto privado A", "summary": "Resumo", "territory": "BR-MT",
                                           "causes": ["educacao"], "beneficiaries_count": 10, "budget_total_cents": 100000}).json["id"]
        for path in (f"/v1/projects/{pid}", f"/v1/projects/{pid}/impact", f"/v1/projects/{pid}/budget"):
            self.assertIn(self.b.get(path).status, (403, 404), path)
        self.assertIn(self.b.patch(f"/v1/projects/{pid}", {"title": "Sequestrado"}).status, (403, 404))
        self.assertEqual(self.a.get(f"/v1/projects/{pid}").json["title"], "Projeto privado A")


# ------------------------------------------------------------------------------------------------ concorrência real (threads)
class Concurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")

    def publish_event(self, capacity: int) -> dict:
        slug = uniq("corrida")
        r = self.ed.post("/v1/admin/content/events", {"slug": slug, "kind": "webinar", "title": "Evento de corrida", "description": "Teste de concorrência.",
                                                      "starts_at": (datetime.now(UTC) + timedelta(days=3)).isoformat(), "duration_min": 30,
                                                      "capacity": capacity, "demo": True})
        self.assertEqual(r.status, 201, r)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/events/{r.json['id']}/transition", {"to": to}).status, 200)
        return {"id": r.json["id"], "slug": slug}

    def test_event_capacity_is_never_exceeded_under_concurrent_registration(self):
        e = self.publish_event(capacity=2)
        accounts = [new_account("osc") for _ in range(5)]
        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(lambda c: c.post(f"/v1/help/events/{e['id']}/register"), accounts))
        self.assertTrue(all(r.status == 200 for r in results), [r.status for r in results])
        states = sorted(r.json["status"] for r in results)
        with db_system() as d:
            registered = d.scalar("SELECT count(*) FROM hub_event_registrations WHERE event_id = $1 AND status = 'registered'", e["id"])
            waitlist = d.scalar("SELECT count(*) FROM hub_event_registrations WHERE event_id = $1 AND status = 'waitlist'", e["id"])
        self.assertEqual(registered, 2, f"capacidade estourada por corrida: {states}")
        self.assertEqual(waitlist, 3, states)

    def test_concurrent_certificate_issue_creates_a_single_certificate(self):
        slug = uniq("curso")
        body = {"slug": slug, "title": "Curso de corrida", "pass_score": 70, "hours": 1.0, "cert_enabled": True, "demo": True, "visibility": "public",
                "modules": [{"title": "M1", "lessons": [{"title": "Aula única", "kind": "text", "body": "Texto."}]}]}
        r = self.ed.post("/v1/admin/content/courses", body)
        self.assertEqual(r.status, 201, r)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/courses/{r.json['id']}/transition", {"to": to}).status, 200)
        u = new_account("osc")
        self.assertEqual(u.post(f"/v1/help/courses/{slug}/enroll").status, 200)
        lesson = u.get(f"/v1/help/courses/{slug}").json["modules"][0]["lessons"][0]["id"]
        self.assertEqual(u.post(f"/v1/help/lessons/{lesson}/complete", {}).status, 200)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: u.post(f"/v1/help/courses/{slug}/certificate"), range(4)))
        self.assertTrue(all(r.status in (200, 201, 409) for r in results), [r.status for r in results])
        codes = {r.json["code"] for r in results if r.status in (200, 201) and r.json.get("code")}
        with db_system() as d:
            n = d.scalar("SELECT count(*) FROM course_certificates WHERE user_id = $1", u.user["id"])
        self.assertEqual(n, 1, f"certificado duplicado por corrida (códigos: {codes})")
        self.assertEqual(len(codes), 1, codes)

    def test_concurrent_voucher_redemption_respects_the_single_use_limit(self):
        adm1, s1 = make_admin()
        adm2, s2 = make_admin()
        b = adm1.post("/v1/admin/voucher-batches", {"campaign": "Corrida " + uuid.uuid4().hex[:5], "quantity": 1,
                                                    "type": "percent_off", "percent": 10, "plan_key": "osc_premium", "max_redemptions": 1})
        self.assertEqual(b.status, 201, b)
        self.assertEqual(adm2.post(f"/v1/admin/voucher-batches/{b.json['batch_id']}/action", {"action": "approve"}).status, 200)
        code = b.json["codes"][0]
        orgs = [new_account("osc") for _ in range(4)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda c: c.post("/v1/vouchers/redeem", {"code": code}), orgs))
        ok = [r for r in results if r.status == 200]
        self.assertEqual(len(ok), 1, f"voucher de uso único resgatado {len(ok)}x: {[r.status for r in results]}")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM voucher_redemptions r JOIN vouchers v ON v.id = r.voucher_id WHERE v.batch_id = $1", b.json["batch_id"]), 1)
            self.assertEqual(d.scalar("SELECT redeemed_count FROM vouchers WHERE batch_id = $1", b.json["batch_id"]), 1)

    def test_duplicate_webhook_delivered_concurrently_is_processed_once(self):
        """Idempotência sob concorrência: o mesmo event.id entregue 4x em paralelo grava UMA linha (garantia do banco)."""
        event = {"id": f"evt_{uuid.uuid4().hex[:14]}", "type": "customer.subscription.updated", "created": int(time.time()),
                 "data": {"object": {"id": f"sub_{uuid.uuid4().hex[:10]}", "status": "active", "customer": f"cus_{uuid.uuid4().hex[:8]}"}}}
        payload = json.dumps(event).encode()

        def deliver(_):
            t = int(time.time())
            sig = hmac.new(b"whsec_test", f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
            return Client().request("POST", "/v1/billing/webhooks/stripe", raw=payload, ctype="application/json",
                                    headers={"Stripe-Signature": f"t={t},v1={sig}"})

        with stripe_mode():
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(deliver, range(4)))
        self.assertTrue(all(r.status == 200 for r in results), [(r.status, r.body[:80]) for r in results])
        outcomes = sorted((r.json or {}).get("status", "?") for r in results)
        self.assertEqual(outcomes.count("duplicate_ignored"), 3, outcomes)
        with db_system() as d:
            stored = d.scalar("SELECT count(*) FROM billing_events WHERE event_id = $1", event["id"])
            processed = d.scalar("SELECT count(*) FROM billing_events WHERE event_id = $1 AND processed_at IS NOT NULL", event["id"])
        self.assertEqual(stored, 1, "webhook duplicado concorrente gravou o evento mais de uma vez")
        self.assertEqual(processed, 1)

    def test_webhook_without_valid_signature_is_never_recorded(self):
        event = {"id": f"evt_{uuid.uuid4().hex[:14]}", "type": "customer.subscription.updated", "created": int(time.time()),
                 "data": {"object": {"id": f"sub_{uuid.uuid4().hex[:10]}", "status": "active"}}}
        payload = json.dumps(event).encode()
        with stripe_mode():
            r = Client().request("POST", "/v1/billing/webhooks/stripe", raw=payload, ctype="application/json",
                                 headers={"Stripe-Signature": "t=1,v1=deadbeef"})
        self.assertIn(r.status, (400, 403), r)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM billing_events WHERE event_id = $1", event["id"]), 0)

    def test_concurrent_trial_decision_is_applied_once(self):
        org = new_account("osc")
        req = org.post("/v1/help/trial-requests", {"users_count": 2, "purpose": "Avaliar com a equipe de projetos.", "responsible": "Resp"})
        self.assertEqual(req.status, 201, req)
        adm, _ = make_admin()
        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(lambda _: adm.post(f"/v1/admin/hub/trial-requests/{req.json['id']}/decide",
                                                       {"approve": True, "reason": "aprovado para piloto"}), range(3)))
        ok = [r for r in results if r.status == 200]
        self.assertEqual(len(ok), 1, f"decisão aplicada {len(ok)}x: {[r.status for r in results]}")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM org_trials WHERE org_id = $1", org.org_id), 1)


# ------------------------------------------------------------------------------------------------ higiene de erros
class ErrorHygiene(unittest.TestCase):
    LEAKS = ("Traceback", "SELECT ", "INSERT ", 'File "', "psycopg", "libpq", "impacto/services", "secret", "password=")

    @classmethod
    def setUpClass(cls):
        server()
        cls.u = new_account("osc")

    def assert_clean(self, resp, *, path: str):
        text = resp.body.decode("utf-8", "replace")
        for needle in self.LEAKS:
            self.assertNotIn(needle.lower(), text.lower(), f"{path} vazou '{needle}': {text[:200]}")

    def test_malformed_ids_and_bodies_never_leak_internals_and_never_500(self):
        probes = [("GET", "/v1/projects/not-a-uuid", None), ("GET", "/v1/projects/../../etc/passwd", None),
                  ("GET", "/v1/support/tickets/00000000-0000-0000-0000-000000000000", None),
                  ("GET", "/v1/help/articles/" + "a" * 300, None), ("GET", "/v1/help/resources/%00", None),
                  ("POST", "/v1/projects", {"title": None}), ("POST", "/v1/help/feedback", {"target_type": "article", "target_id": "x", "helpful": True}),
                  ("PUT", "/v1/help/checklists", {"scope": "../etc", "checked": [1]}),
                  ("GET", "/v1/documents?limit=99999", None), ("GET", "/v1/documents?limit=-1", None), ("GET", "/v1/documents?offset=-5", None)]
        for method, path, body in probes:
            resp = self.u.request(method, path, body)
            self.assertLess(resp.status, 500, f"{method} {path} -> {resp.status} {resp.body[:200]!r}")
            self.assertGreaterEqual(resp.status, 400, f"{method} {path} aceitou entrada inválida")
            self.assert_clean(resp, path=path)
            if resp.body:
                self.assertIn("request_id", resp.json, path)

    def test_database_schema_details_never_reach_the_client(self):
        """Violação de CHECK no banco não deve expor tabela/constraint; a mensagem autorada pelos gatilhos continua visível."""
        from impacto.http import _PG_INTERNAL
        self.assertTrue(_PG_INTERNAL.search('new row for relation "courses" violates check constraint "courses_check2"'))
        self.assertTrue(_PG_INTERNAL.search('duplicate key value violates unique constraint "users_email_key"'))
        self.assertIsNone(_PG_INTERNAL.search("versão fora de rascunho é imutável: crie uma nova versão"))
        self.assertIsNone(_PG_INTERNAL.search("chamado só pode ser alterado pela equipe de suporte"))
        ed = staff("editor")
        r = ed.post("/v1/admin/content/courses", {"slug": uniq("curso"), "title": "Curso sem carga horária", "cert_enabled": True,
                                                  "modules": [{"title": "M1", "lessons": [{"title": "A1", "kind": "text", "body": "Texto."}]}]})
        self.assertEqual(r.status, 422, r)
        body = r.body.decode()
        self.assertEqual(r.json["code"], "integrity_error")
        for leak in ("violates", "constraint", "relation", "courses_check", "new row"):
            self.assertNotIn(leak, body.lower(), f"esquema vazou na resposta: {body[:200]}")
        self.assertIn("error_id", r.json)

    def test_bad_json_and_media_type_are_rejected_cleanly(self):
        r = self.u.request("POST", "/v1/projects", raw=b"{nao-e-json", ctype="application/json")
        self.assertEqual(r.status, 400, r)
        self.assert_clean(r, path="json inválido")
        r2 = self.u.request("POST", "/v1/projects", raw=b"title=x", ctype="application/x-www-form-urlencoded")
        self.assertEqual(r2.status, 415, r2)

    def test_unknown_fields_are_rejected_so_clients_cannot_smuggle_state(self):
        r = self.u.post("/v1/projects", {"title": "Projeto", "summary": "R", "territory": "BR-MT", "causes": ["educacao"],
                                         "beneficiaries_count": 1, "budget_total_cents": 1000, "status": "published", "org_id": str(uuid.uuid4())})
        self.assertEqual(r.status, 422, r)

    def test_sql_and_xss_payloads_are_treated_as_text_everywhere_in_the_hub(self):
        payload = "'; DROP TABLE kb_articles; -- <img src=x onerror=alert(1)>"
        s = self.u.get(f"/v1/help/search?q={payload.replace(' ', '%20').replace('&', '%26')}")
        self.assertIn(s.status, (200, 422), s)
        t = self.u.post("/v1/support/tickets", {"category": "question", "subject": payload[:120], "message": payload})
        self.assertEqual(t.status, 201, t)
        got = self.u.get(f"/v1/support/tickets/{t.json['id']}").json
        self.assertEqual(got["messages"][0]["body"], payload, "conteúdo foi reinterpretado em vez de armazenado literalmente")
        with db_system() as d:
            self.assertTrue(d.scalar("SELECT to_regclass('kb_articles') IS NOT NULL"))


# ------------------------------------------------------------------------------------------------ entrega de e-mail (outbox; SMTP real não exercitado)
class MailDelivery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")

    def publish_bulletin(self) -> str:
        slug = uniq("boletim")
        r = self.ed.post("/v1/admin/content/resources", {"slug": slug, "kind": "bulletin", "title": "Boletim de teste de entrega",
                                                         "summary": "Edição de teste.", "visibility": "public", "demo": True,
                                                         "url": "https://exemplo.org/boletim-teste"})
        self.assertEqual(r.status, 201, r)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/resources/{r.json['id']}/transition", {"to": to}).status, 200)
        return slug

    def test_failed_bulletin_send_does_not_consume_the_subscriber_period(self):
        """Falha de SMTP não pode "queimar" o boletim da inscrita: last_sent_at só avança quando o envio sai."""
        from impacto.services import hub
        self.publish_bulletin()
        email = f"boletim-{uuid.uuid4().hex[:8]}@teste.org"
        anon = Client()
        self.assertEqual(anon.post("/v1/help/newsletter", {"email": email, "topics": ["platform"], "consent": True}).status, 200)
        from tests.support import last_token_for
        self.assertEqual(anon.post("/v1/help/newsletter/confirm", {"token": last_token_for(email, "/ajuda/boletim/confirmar")}).status, 200)
        st = server()["state"]

        class BrokenMailer:
            def send(self, *a, **kw):
                raise OSError("SMTP indisponível")

        original = st.mailer
        st.mailer = BrokenMailer()
        try:
            with db_system() as d:
                out = hub.bulletin_dispatch(st, d)
            self.assertGreaterEqual(out["failed"], 1, out)
            with db_system() as d:
                self.assertIsNone(d.scalar("SELECT last_sent_at FROM newsletter_subscriptions WHERE email = $1", email),
                                  "período consumido mesmo sem envio: a inscrita perderia o boletim")
        finally:
            st.mailer = original
        with db_system() as d:
            out2 = hub.bulletin_dispatch(st, d)
            self.assertGreaterEqual(out2["sent"], 1, out2)
            self.assertIsNotNone(d.scalar("SELECT last_sent_at FROM newsletter_subscriptions WHERE email = $1", email))

    def test_transactional_notice_is_retried_until_it_leaves(self):
        """Aviso de cobrança: enquanto o e-mail falha, `emailed_at` continua nulo (reenvio no ciclo seguinte), sem duplicar depois."""
        from impacto.services import hub
        org = new_account("osc")
        with db_system() as d:
            d.scalar("SELECT app_notify($1,$2,'billing.notice',$3,$4,$5)", org.org_id, org.user["id"],
                     "Aviso de cobrança de teste", "Corpo do aviso.", "/conta/plano")
        st = server()["state"]

        class BrokenMailer:
            def send(self, *a, **kw):
                raise OSError("SMTP indisponível")

        original = st.mailer
        st.mailer = BrokenMailer()
        try:
            with db_system() as d:
                out = hub.notification_emails(st, d)
            self.assertGreaterEqual(out["emails_failed"], 1, out)
            with db_system() as d:
                self.assertEqual(d.scalar("SELECT count(*) FROM notifications WHERE user_id = $1 AND kind = 'billing.notice' AND emailed_at IS NULL", org.user["id"]), 1)
            # v0.20.0 — a falha deixou de sumir: ela fica registrada, com erro e com a HORA DA
            # PRÓXIMA TENTATIVA. Antes, o ciclo seguinte tentava na hora, o que em uma queda de
            # SMTP vira marretada no servidor que já está fora do ar.
            with db_system() as d:
                entrega = d.one("SELECT d.status, d.attempts, d.last_error, d.next_retry_at > now()"
                                " AS aguardando FROM notification_deliveries d"
                                " JOIN notifications n ON n.id = d.notification_id"
                                " WHERE n.user_id = $1 AND n.kind = 'billing.notice'", org.user["id"])
            self.assertEqual(entrega["status"], "failed")
            self.assertEqual(entrega["attempts"], 1)
            self.assertIn("SMTP indisponível", entrega["last_error"])
            self.assertTrue(entrega["aguardando"], "a próxima tentativa tem de ser agendada")
            with db_system() as d:
                self.assertEqual(hub.notification_emails(st, d)["emails_sent"], 0,
                                 "dentro da janela de recuo, não se tenta de novo")
        finally:
            st.mailer = original
        # Vencida a janela de recuo, o aviso SAI — e o `emailed_at` só avança agora.
        with db_system() as d:
            d.run("UPDATE notification_deliveries SET next_retry_at = now() - interval '1 minute'"
                  " WHERE status = 'failed'")
            self.assertGreaterEqual(hub.notification_emails(st, d)["emails_sent"], 1)
            self.assertEqual(d.scalar("SELECT count(*) FROM notifications WHERE user_id = $1 AND kind = 'billing.notice' AND emailed_at IS NULL", org.user["id"]), 0)
            self.assertEqual(d.scalar("SELECT status FROM notification_deliveries d"
                                      " JOIN notifications n ON n.id = d.notification_id"
                                      " WHERE n.user_id = $1 AND n.kind = 'billing.notice'",
                                      org.user["id"]), "sent")
        with db_system() as d:
            self.assertEqual(hub.notification_emails(st, d)["emails_sent"], 0, "aviso já enviado foi reenviado")


# ------------------------------------------------------------------------------------------------ invariantes de dinheiro e tempo
class MoneyAndTime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_discount_is_always_integer_cents_within_bounds(self):
        from impacto.services.monetization import _discount_amount
        for base in (0, 1, 99, 9900, 123457, 10 ** 9):
            for pct in (0, 1, 7, 33, 50, 99, 100, 150):
                d = _discount_amount(base, "percent", pct)
                self.assertIsInstance(d, int)
                self.assertGreaterEqual(d, 0)
                self.assertLessEqual(d, base, f"desconto maior que a base ({base}, {pct}%)")
            self.assertEqual(_discount_amount(base, "amount", base + 1000), base, "desconto fixo não foi limitado à base")
            self.assertEqual(_discount_amount(base, "amount", -50), 0)

    def test_annual_savings_is_never_invented(self):
        from impacto.services.monetization import annual_savings
        self.assertIsNone(annual_savings(None, 10000))
        self.assertIsNone(annual_savings(1000, None))
        self.assertIsNone(annual_savings(1000, 12000), "sem economia real não se anuncia economia")
        self.assertEqual(annual_savings(1000, 10000), {"cents": 2000, "percent": 17})

    def test_reserved_voucher_discount_is_visible_to_the_organization(self):
        """Regressão: `pending_discounts` vinha SEMPRE vazio (JOIN com `vouchers`, invisível à organização por RLS),
        então a página Plano não mostrava o desconto reservado mesmo após aplicar o voucher."""
        adm1, _ = make_admin()
        adm2, _ = make_admin()
        b = adm1.post("/v1/admin/voucher-batches", {"campaign": "Visível " + uuid.uuid4().hex[:5], "quantity": 1,
                                                    "type": "percent_off", "percent": 15, "plan_key": "osc_premium", "max_redemptions": 2})
        self.assertEqual(b.status, 201, b)
        self.assertEqual(adm2.post(f"/v1/admin/voucher-batches/{b.json['batch_id']}/action", {"action": "approve"}).status, 200)
        org = new_account("osc")
        self.assertTrue(org.post("/v1/vouchers/redeem", {"code": b.json["codes"][0]}).json["pending_discount"])
        state = org.get("/v1/billing").json
        self.assertEqual(len(state["pending_discounts"]), 1, "desconto reservado não aparece para a organização")
        d = state["pending_discounts"][0]
        self.assertEqual((d["type"], d["value"]["percent"], d["plan_key"]), ("percent_off", 15, "osc_premium"))
        self.assertNotIn("code", str(state["pending_discounts"]).lower(), "código/hash do voucher não deve sair na resposta")
        other = new_account("osc")
        self.assertEqual(other.get("/v1/billing").json["pending_discounts"], [], "desconto de outra organização vazou")

    def test_quote_refuses_to_sell_a_plan_without_price(self):
        c = new_account("osc")
        r = c.post("/v1/billing/quote", {"plan_key": "osc_premium", "interval": "month"})
        self.assertIn(r.status, (409, 200), r)
        if r.status == 409:
            self.assertEqual(r.json["code"], "price_not_defined")
        else:
            self.assertIsInstance(r.json["final_cents"], int)
            self.assertGreaterEqual(r.json["final_cents"], 0)

    def test_timestamps_are_timezone_aware_iso_8601(self):
        c = new_account("osc")
        t = c.post("/v1/support/tickets", {"category": "question", "subject": "Horário do chamado", "message": "Verificando fuso."})
        got = c.get(f"/v1/support/tickets/{t.json['id']}").json
        for field in ("created_at", "updated_at", "first_response_due", "resolution_due"):
            value = got[field]
            self.assertIsNotNone(value, field)
            self.assertRegex(value, r"(Z|[+-]\d{2}:\d{2})$", f"{field} sem fuso horário: {value}")
            self.assertIsNotNone(datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo, field)
        due = datetime.fromisoformat(got["resolution_due"].replace("Z", "+00:00"))
        self.assertGreater(due, datetime.now(UTC), "prazo de SLA nasceu no passado (erro de fuso)")


if __name__ == "__main__":
    unittest.main()
