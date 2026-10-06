"""Billing (sandbox), vouchers (dupla aprovação, concorrência), invariância do match a plano, alertas de editais,
regras fiscais com dupla aprovação, LGPD, governo, administração, IA, jobs e contrato OpenAPI."""
import threading
import unittest
from datetime import date, timedelta

from tests.support import PASSWORD, Client, db_system, grant_premium, make_admin, new_account, server

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class BillingAndVoucherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.adm1, _ = make_admin()
        cls.adm2, _ = make_admin()

    def test_public_plan_catalog(self):
        r = Client().get("/v1/plans").json
        keys = {p["plan_key"] for p in r["items"]}
        self.assertTrue({"osc_basic", "osc_premium", "company_premium", "government_basic"} <= keys)
        self.assertEqual(r["billing_provider"], "sandbox")

    def test_sandbox_checkout_unlocks_paid_features(self):
        osc = new_account("osc")
        r = osc.post("/v1/saved-searches", {"name": "Editais de cultura", "filters": {"cause": "cultura"}})
        self.assertEqual((r.status, r.json["code"]), (402, "feature_not_in_plan"))
        self.assertEqual(osc.post("/v1/billing/checkout", {"plan_key": "company_premium"}).status, 404)  # plano de outro papel
        # A v0.17.0 APOSENTOU a regra comercial em dólar da v0.16.0 e não fixa preço institucional em
        # `config/plans.json`. Quem declara o preço exercitado aqui é o AMBIENTE DE TESTE
        # (`support.TEST_PRICES`), então o teste lê o valor de lá em vez de fixá-lo — fixar aqui seria
        # repetir em teste exatamente o que o produto deixou de fazer.
        # O que continua valendo é que nada é fictício: no provedor de teste a resposta diz, em letras,
        # que nenhuma cobrança real aconteceu.
        r = osc.post("/v1/billing/checkout", {"plan_key": "osc_premium"})
        self.assertEqual(r.status, 200, r)
        self.assertIn("SANDBOX", r.json["warning"])
        self.assertIn("alerts.saved_search", osc.get("/v1/me").json["entitlements"]["features"])
        # e o preço que ela aceitou ficou congelado, com a moeda e a promoção de entrada da regra vigente
        acc = osc.get("/v1/billing/price-history").json["accepted"]
        self.assertEqual(len(acc), 1)
        from tests.support import TEST_PRICES
        cents, intro = next((c, i) for p, iv, c, i, _, _ in TEST_PRICES
                            if p == "osc_premium" and iv == "month")
        self.assertEqual((acc[0]["currency"], acc[0]["amount_cents"], acc[0]["intro_amount_cents"]),
                         ("BRL", cents, intro))

    def test_paid_plan_with_price_via_sandbox(self):
        with db_system() as d:
            d.run("UPDATE plans SET price_cents = 9900 WHERE plan_key = 'osc_premium'")
        try:
            osc = new_account("osc")
            r = osc.post("/v1/billing/checkout", {"plan_key": "osc_premium"})
            self.assertEqual(r.status, 200, r)
            self.assertIn("SANDBOX", r.json["warning"])
            self.assertIn("alerts.saved_search", osc.get("/v1/me").json["entitlements"]["features"])
            self.assertEqual(osc.post("/v1/saved-searches", {"name": "Cultura", "filters": {"cause": "cultura"}}).status, 201)
            self.assertEqual(osc.post("/v1/billing/cancel").status, 200)
            # v0.11.0: cancelar NÃO corta o acesso já pago — vale até o fim do período; só então volta ao FREE
            self.assertIn("alerts.saved_search", osc.get("/v1/me").json["entitlements"]["features"])
            with db_system() as d:
                d.run("UPDATE subscriptions SET current_period_end = now() - interval '8 days' WHERE org_id = $1", osc.org_id)
            self.assertNotIn("alerts.saved_search", osc.get("/v1/me").json["entitlements"]["features"])
            # rebaixamento não apaga dados
            self.assertEqual(len(osc.get("/v1/saved-searches").json["items"]), 1)
        finally:
            with db_system() as d:
                d.run("UPDATE plans SET price_cents = NULL WHERE plan_key = 'osc_premium'")

    def test_voucher_dual_approval_and_single_use(self):
        r = self.adm1.post("/v1/admin/voucher-batches", {"campaign": "Piloto MT", "type": "grant_plan", "plan_key": "osc_premium",
                                                          "duration_days": 90, "quantity": 2, "scope_roles": ["osc"]})
        self.assertEqual(r.status, 201, r)
        bid, codes = r.json["batch_id"], r.json["codes"]
        osc = new_account("osc")
        self.assertEqual(osc.post("/v1/vouchers/redeem", {"code": codes[0]}).json["code"], "voucher_unavailable")  # lote não aprovado
        self.assertEqual(self.adm1.post(f"/v1/admin/voucher-batches/{bid}/action", {"action": "approve"}).json["code"], "second_approver_required")
        self.assertEqual(self.adm2.post(f"/v1/admin/voucher-batches/{bid}/action", {"action": "approve"}).status, 200)
        self.assertEqual(osc.post("/v1/vouchers/redeem", {"code": codes[0].lower().replace("-", "")}).status, 200)
        self.assertIn("osc_premium", osc.get("/v1/me").json["entitlements"]["plans"])
        self.assertEqual(osc.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 404)  # reuso
        co = new_account("company")
        self.assertEqual(co.post("/v1/vouchers/redeem", {"code": codes[1]}).status, 404)  # fora do escopo de papel
        self.assertEqual(osc.post("/v1/vouchers/redeem", {"code": "AAAA-BBBB-CCCC"}).json["code"], "voucher_unavailable")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM vouchers WHERE code_hash = $1", codes[1]), 0)  # nunca em texto puro

    def test_voucher_concurrency_last_use(self):
        r = self.adm1.post("/v1/admin/voucher-batches", {"campaign": "Concorrência", "type": "grant_feature", "feature_key": "alerts.saved_search",
                                                          "duration_days": 30, "quantity": 1, "max_redemptions": 1})
        bid, code = r.json["batch_id"], r.json["codes"][0]
        self.adm2.post(f"/v1/admin/voucher-batches/{bid}/action", {"action": "approve"})
        orgs = [new_account("osc") for _ in range(5)]
        results = []
        ts = [threading.Thread(target=lambda c=c: results.append(c.post("/v1/vouchers/redeem", {"code": code}).status)) for c in orgs]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(sorted(results).count(200), 1, results)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT redeemed_count FROM vouchers WHERE batch_id = $1", bid), 1)

    def test_stripe_webhook_signature_and_idempotency(self):
        import hashlib
        import hmac
        import json
        import time
        st = server()["state"]
        old = (st.settings.billing_provider, st.settings.stripe_webhook_secret)
        st.settings.billing_provider, st.settings.stripe_webhook_secret = "stripe", "whsec_test"
        try:
            osc = new_account("osc")
            with db_system() as d:
                d.run("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_checkout_id) VALUES ($1,'osc_premium','incomplete','stripe','cs_test_1')",
                      osc.org_id)
            ev = {"id": "evt_1", "type": "checkout.session.completed", "data": {"object": {"id": "cs_test_1", "customer": "cus_1",
                  "subscription": "sub_1", "metadata": {"org_id": osc.org_id, "plan_key": "osc_premium"}}}}
            payload = json.dumps(ev).encode()
            t = int(time.time())
            sig = hmac.new(b"whsec_test", f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
            self.assertEqual(Client().request("POST", "/v1/billing/webhooks/stripe", raw=payload, ctype="application/json",
                                              headers={"Stripe-Signature": f"t={t},v1=deadbeef"}).status, 400)
            self.assertEqual(Client().request("POST", "/v1/billing/webhooks/stripe", raw=payload, ctype="application/json",
                                              headers={"Stripe-Signature": f"t={t - 3600},v1={sig}"}).status, 400)  # replay antigo
            ok = Client().request("POST", "/v1/billing/webhooks/stripe", raw=payload, ctype="application/json", headers={"Stripe-Signature": f"t={t},v1={sig}"})
            self.assertEqual((ok.status, ok.json["status"]), (200, "processed"))
            dup = Client().request("POST", "/v1/billing/webhooks/stripe", raw=payload, ctype="application/json", headers={"Stripe-Signature": f"t={t},v1={sig}"})
            self.assertEqual(dup.json["status"], "duplicate_ignored")
            self.assertIn("osc_premium", osc.get("/v1/me").json["entitlements"]["plans"])
            # pagamento falho → past_due
            ev2 = {"id": "evt_2", "type": "invoice.payment_failed", "data": {"object": {"id": "in_1", "subscription": "sub_1", "amount_due": 9900, "currency": "brl"}}}
            p2 = json.dumps(ev2).encode()
            s2 = hmac.new(b"whsec_test", f"{t}.".encode() + p2, hashlib.sha256).hexdigest()
            Client().request("POST", "/v1/billing/webhooks/stripe", raw=p2, ctype="application/json", headers={"Stripe-Signature": f"t={t},v1={s2}"})
            self.assertEqual(osc.get("/v1/billing").json["invoices"][0]["status"], "open")
        finally:
            st.settings.billing_provider, st.settings.stripe_webhook_secret = old


class MatchInvarianceTests(unittest.TestCase):
    """ADR-008: plano/voucher nunca alteram elegibilidade, score ou ordenação."""

    def test_feed_identical_with_and_without_premium(self):
        server()
        osc = new_account("osc")
        osc.patch("/v1/org", {"founded_on": "2015-01-01", "causes": ["educacao"], "uf": "MT"})
        pid = osc.post("/v1/projects", {"title": "Invariância", "summary": "x", "territory": "BR-MT", "causes": ["educacao"], "beneficiaries_count": 10,
                                        "budget_total_cents": 300000}).json["id"]
        osc.post(f"/v1/projects/{pid}/publish")
        co = new_account("company")
        co.put("/v1/org/funder-profile", {"causes": ["educacao"], "territories": ["BR-MT"]})

        def snapshot():
            m = co.get(f"/v1/projects/{pid}").json["match"]
            feed = [i["project"]["id"] for i in co.get("/v1/feed/projects?limit=100").json["items"]]
            return m["score"], m["eligibility"], m["confidence"], feed.index(pid)
        before = snapshot()
        grant_premium(osc)
        grant_premium(co, "company_enterprise")
        self.assertEqual(snapshot(), before)


class AlertsTests(unittest.TestCase):
    def test_saved_search_tracks_new_calls_and_notifies(self):
        server()
        osc = new_account("osc")
        grant_premium(osc)
        osc.patch("/v1/org", {"founded_on": "2015-01-01", "causes": ["meio_ambiente"], "uf": "MT"})
        sid = osc.post("/v1/saved-searches", {"name": "Ambiental MT", "filters": {"cause": "meio_ambiente", "territory": "BR-MT"}}).json["id"]
        gov = new_account("government", compliance="approved")
        r = gov.post("/v1/calls", {"title": "Edital Municipal Ambiental", "sphere": "municipal", "causes": ["meio_ambiente"], "territories": ["BR-MT"],
                                   "status": "open", "closes_at": (date.today() + timedelta(days=20)).isoformat() + "T12:00:00Z"})
        self.assertEqual(r.status, 201, r)
        self.assertGreaterEqual(osc.post(f"/v1/saved-searches/{sid}/run").json["new_matches"], 1)
        self.assertEqual(osc.post(f"/v1/saved-searches/{sid}/run").json["new_matches"], 0)  # não notifica duas vezes
        notes = osc.get("/v1/notifications").json["items"]
        self.assertTrue(any(n["kind"] == "alert" for n in notes))

    def test_government_must_be_verified_to_publish(self):
        gov = new_account("government")
        r = gov.post("/v1/calls", {"title": "Edital não verificado", "sphere": "state", "status": "open"})
        self.assertEqual(r.json["code"], "government_not_verified")
        self.assertEqual(gov.post("/v1/calls", {"title": "Rascunho de edital", "sphere": "state", "status": "draft"}).status, 201)


class FiscalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.adm1, _ = make_admin()
        cls.adm2, _ = make_admin()

    def test_candidate_rules_are_never_used_until_dual_approval(self):
        co = new_account("company")
        grant_premium(co)
        co.put("/v1/org/tax-profile", {"regime": "lucro_real", "estimated_ir_due_cents": 10_000_000, "fiscal_year": 2026})
        res = co.get("/v1/fiscal/estimates").json
        codes = {i["rule"]["code"] for i in res["items"]}
        self.assertNotIn("BR-FED-FIA", codes)  # candidata em rascunho
        rid = self.adm1.post("/v1/admin/fiscal-rules", {
            "code": "TEST-FED-FIA", "version": "2026.1", "name": "Regra de teste", "mechanism": "deducao_ir", "jurisdiction": "federal",
            "taxpayer_regimes": ["lucro_real"], "tax_base": "ir_devido", "limit_pct": 1.0, "causes": ["criancas_adolescentes"],
            "source_citation": "Lei de teste, art. 1º", "source_url": "https://www.planalto.gov.br/teste", "source_consulted_on": "2026-10-04"}).json["id"]
        self.adm1.post(f"/v1/admin/fiscal-rules/{rid}/action", {"action": "submit"})
        self.assertEqual(self.adm1.post(f"/v1/admin/fiscal-rules/{rid}/action", {"action": "approve"}).json["status"], "pending_review")
        self.assertEqual(self.adm1.post(f"/v1/admin/fiscal-rules/{rid}/action", {"action": "approve"}).json["code"], "second_approver_required")
        self.assertEqual(self.adm2.post(f"/v1/admin/fiscal-rules/{rid}/action", {"action": "approve"}).json["status"], "approved")
        res = co.get("/v1/fiscal/estimates").json
        item = next(i for i in res["items"] if i["rule"]["code"] == "TEST-FED-FIA")
        self.assertEqual(item["estimate"]["max_deductible_cents"], 100_000)
        self.assertEqual(item["estimate"]["label"], "ESTIMATIVA")
        self.assertTrue(item["professional_validation"]["required"])
        self.assertIn("Não constitui aconselhamento", res["disclaimer"])
        self.adm1.post(f"/v1/admin/fiscal-rules/{rid}/action", {"action": "retire"})
        self.assertNotIn("TEST-FED-FIA", {i["rule"]["code"] for i in co.get("/v1/fiscal/estimates").json["items"]})


class PrivacyAndAdminTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.adm, _ = make_admin()

    def test_export_and_delete_account(self):
        c = new_account("osc")
        r = c.get("/v1/privacy/export")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json["user"]["email"], c.email)
        self.assertIn("attachment", r.headers["Content-Disposition"])
        self.assertEqual(c.post("/v1/privacy/delete-account", {"password": "errada", "confirm": True}).status, 401)
        self.assertEqual(c.post("/v1/privacy/delete-account", {"password": PASSWORD, "confirm": True}).status, 200)
        self.assertEqual(Client().login(c.email, PASSWORD).status, 401)
        with db_system() as d:
            u = d.one("SELECT email::text AS email, full_name, status, password_hash FROM users WHERE id = $1", c.user["id"])
        self.assertTrue(u["email"].endswith("@anonimizado.invalid"))
        self.assertEqual((u["status"], u["password_hash"]), ("deleted", None))

    def test_admin_disable_user_revokes_sessions(self):
        c = new_account("osc")
        self.assertEqual(self.adm.post(f"/v1/admin/users/{c.user['id']}/status", {"status": "disabled", "reason": "Fraude"}).status, 200)
        self.assertEqual(c.get("/v1/me").status, 401)
        self.assertEqual(self.adm.post(f"/v1/admin/users/{self.adm.user['id']}/status", {"status": "disabled", "reason": "x"}).status, 422)

    def test_reports_flow(self):
        c = new_account("osc")
        target = new_account("osc")
        rid = c.post("/v1/reports", {"target_type": "organization", "target_id": target.org_id, "reason": "fraud", "details": "Suspeita"}).json["id"]
        items = self.adm.get("/v1/admin/reports").json["items"]
        self.assertIn(rid, [i["id"] for i in items])
        self.assertEqual(self.adm.post(f"/v1/admin/reports/{rid}", {"status": "dismissed", "resolution": "Sem evidências"}).status, 200)

    def test_admin_overview_and_audit_chain(self):
        ov = self.adm.get("/v1/admin/overview").json
        self.assertIn("queues", ov)
        self.assertTrue(self.adm.get("/v1/admin/audit/verify").json["valid"])

    def test_legal_texts_served(self):
        r = Client().get("/v1/legal/privacidade")
        self.assertEqual(r.status, 200)
        self.assertIn(b"LGPD", r.body)


class GovernmentAndAiTests(unittest.TestCase):
    def test_gov_stats_k_anonymity(self):
        server()
        gov = new_account("government", compliance="approved")
        for i in range(3):
            o = new_account("osc")
            p = o.post("/v1/projects", {"title": f"Projeto Gov {i}", "summary": "x", "territory": "BR-RO-1100205", "causes": ["saude"],
                                        "beneficiaries_count": 10, "budget_total_cents": 100000}).json["id"]
            o.post(f"/v1/projects/{p}/publish")
        lone = new_account("osc")
        p = lone.post("/v1/projects", {"title": "Único", "summary": "x", "territory": "BR-RO-1100205", "causes": ["habitacao"],
                                       "beneficiaries_count": 5, "budget_total_cents": 100000}).json["id"]
        lone.post(f"/v1/projects/{p}/publish")
        r = gov.get("/v1/gov/territory-stats?territory=BR-RO").json
        causes = {g["cause"] for g in r["groups"]}
        self.assertIn("saude", causes)
        self.assertNotIn("habitacao", causes)  # grupo < 3 suprimido
        osc = new_account("osc")
        self.assertEqual(osc.get("/v1/gov/territory-stats").status, 403)
        m = gov.post("/v1/materials", {"title": "Guia de prestação de contas", "category": "guide", "status": "published", "url": "https://www.gov.br/guia"})
        self.assertEqual(m.status, 201)
        self.assertIn(m.json["id"], [x["id"] for x in osc.get("/v1/materials").json["items"]])

    def test_ai_structure_need_and_quota(self):
        osc = new_account("osc")
        r = osc.post("/v1/ai/structure-need", {"text": "Precisamos de 10 violões de R$ 500 cada para aulas de música para 40 crianças do bairro."})
        self.assertEqual(r.status, 200, r)
        d = r.json
        self.assertEqual(d["budget_items"][0]["quantity"], 10)
        self.assertEqual(d["budget_total_cents"], 500_000)
        self.assertEqual(d["beneficiaries_count"], 40)
        self.assertIn("cultura", d["causes"])
        self.assertTrue(d["human_review_required"])
        with db_system() as db:
            db.run("INSERT INTO ai_usage(org_id, feature, provider, status) SELECT $1, 'x', 'local', 'ok' FROM generate_series(1, 30)", osc.org_id)
        r = osc.post("/v1/ai/structure-need", {"text": "Mais uma necessidade com texto suficiente."})
        self.assertEqual((r.status, r.json["code"]), (402, "ai_quota_exceeded"))
        with db_system() as db:
            row = db.one("SELECT input_sha256, input_chars FROM ai_usage WHERE org_id = $1 AND feature = 'structure_need'", osc.org_id)
        self.assertEqual(len(row["input_sha256"]), 64)  # só hash — conteúdo não é armazenado


class JobsTests(unittest.TestCase):
    def test_import_json_feed_and_run_once(self):
        import json
        from impacto import jobs
        from impacto.adapters.http_client import HttpClient
        st = server()["state"]
        feed = {"items": [{"id": "x1", "title": "Edital Importado 1", "url": "https://fonte.gov.br/1", "closes_at": "2099-01-01T00:00:00+00:00",
                           "causes": "educacao,cultura"}, {"id": "x2", "title": "ok"}, {"id": "", "title": "sem referência"}]}
        http = HttpClient(transport=lambda m, u, h, b, t: (200, {}, json.dumps(feed).encode()), retries=0)
        with db_system() as d:
            sid = d.scalar("INSERT INTO call_sources(name, kind, url, sphere, active, terms_note) VALUES ('Fonte Teste','json_feed',"
                           " 'https://fonte.gov.br/feed.json','federal', true, 'Termos verificados em teste') RETURNING id::text")
            src = d.one("SELECT * FROM call_sources WHERE id = $1", sid)
        res = jobs.import_source(st, src, http=http)
        self.assertEqual((res["status"], res["created"], res["skipped"]), ("ok", 1, 2))
        res = jobs.import_source(st, src, http=http)
        self.assertEqual((res["created"], res["updated"]), (0, 1))  # idempotente
        with db_system() as d:
            d.run("UPDATE call_sources SET active = false WHERE id = $1", sid)  # sem rede externa no restante
        out = jobs.run_once(st)
        self.assertTrue(all(r["status"] in ("ok", "skipped") for r in out), out)


class ContractTests(unittest.TestCase):
    def test_openapi_and_health(self):
        server()
        spec = Client().get("/v1/openapi.json").json
        self.assertEqual(spec["openapi"], "3.1.0")
        self.assertGreater(len(spec["paths"]), 100)
        self.assertIn("/v1/applications/{application_id}/transition", spec["paths"])
        self.assertEqual(Client().get("/healthz").json["status"], "ok")
        self.assertEqual(Client().get("/readyz").json["status"], "ready")
        self.assertIn(b"impacto_http_requests_total", Client().get("/metrics").body)
        self.assertEqual(Client().get("/v1/rota-inexistente").status, 404)
        tax = Client().get("/v1/meta/taxonomy").json
        self.assertIn("educacao", tax["causes"])


if __name__ == "__main__":
    unittest.main()
