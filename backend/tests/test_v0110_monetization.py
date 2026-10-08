"""v0.11.0 → v0.27.0 — concessões de acesso: pacotes FREE/PLUS/PREMIUM/GOV, vouchers de concessão, convênios,
licenças e segurança da camada de acesso. HTTP + PostgreSQL reais.

HISTÓRICO (ADR-340/341): até a v0.26.0 este módulo provava trial de 14 dias, checkout/webhooks do Stripe,
upgrade/downgrade, portal e cotação com desconto. O proprietário retirou a ASSINATURA do modelo econômico
na v0.27.0; esses testes foram REMOVIDOS porque a funcionalidade deixou de existir — não afrouxados. O que
fica aqui é o que continua sendo verdade: pacotes concedem capacidades, vouchers e convênios concedem
pacotes, a organização nunca escreve o próprio direito, e nada disso altera match ou ranking.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import Client, db_system, make_admin, new_account, server


def acct(kind="osc") -> Client:
    return new_account(kind)


def features(c: Client) -> set:
    return set(c.get("/v1/me").json["entitlements"]["features"])


def billing(c: Client) -> dict:
    return c.get("/v1/billing").json


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.adm1, _ = make_admin()
        cls.adm2, _ = make_admin()

    def license(self, org_id: str, plan_key: str, days=30, source="license"):
        r = self.adm1.post(f"/v1/admin/organizations/{org_id}/grants", {"plan_key": plan_key, "days": days, "source": source, "reason": "teste de licença"})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def batch(self, **kw) -> tuple[str, list[str]]:
        body = {"campaign": "Teste " + uuid.uuid4().hex[:5], "quantity": 1, **kw}
        r = self.adm1.post("/v1/admin/voucher-batches", body)
        self.assertEqual(r.status, 201, r)
        self.assertEqual(self.adm2.post(f"/v1/admin/voucher-batches/{r.json['batch_id']}/action", {"action": "approve"}).status, 200)
        return r.json["batch_id"], r.json["codes"]


# ------------------------------------------------------------------------------------------------ pacotes
class TierAccessTests(Base):
    def test_free_plus_premium_gov_access_matrix(self):
        free = acct("osc")
        f_free = features(free)
        self.assertIn("catalog.search", f_free)
        self.assertNotIn("alerts.saved_search", f_free)
        self.assertEqual(billing(free)["tier"], "free")
        plus = acct("osc")
        self.license(plus.org_id, "osc_plus")
        f_plus = features(plus)
        self.assertIn("alerts.saved_search", f_plus)
        self.assertNotIn("ai.assist.advanced", f_plus)                   # PLUS ≠ PREMIUM
        self.assertEqual(billing(plus)["tier"], "plus")
        prem = acct("osc")
        self.license(prem.org_id, "osc_premium")
        self.assertIn("ai.assist.advanced", features(prem))
        self.assertEqual(billing(prem)["tier"], "premium")
        gov = acct("government")
        self.assertNotIn("audit.export", features(gov))
        self.license(gov.org_id, "gov_institutional", source="gov")
        self.assertEqual(billing(gov)["tier"], "gov")
        self.assertIn("audit.export", features(gov))
        self.assertIn("calls.publish", features(gov))

    def test_plans_catalog_has_tiers_and_no_price(self):
        """v0.27.0: o catálogo publica pacotes e vias de acesso — e NENHUM preço recorrente."""
        out = Client().get("/v1/plans").json
        items = {p["plan_key"]: p for p in out["items"]}
        self.assertEqual(items["osc_plus"]["tier"], "plus")
        self.assertEqual(items["gov_institutional"]["tier"], "gov")
        for p in out["items"]:
            self.assertNotIn("prices", p)
            self.assertNotIn("price_quotes", p)
            self.assertNotIn("annual_savings", p)
            self.assertNotIn("price_cents", p)
            self.assertNotIn("interval", p)
        self.assertIsNone(out["subscription"])
        self.assertIn("não cobra assinatura", out["pricing_note"])
        self.assertEqual({a["key"] for a in out["access_paths"]}, {"core", "operation", "contract", "grant"})
        # Pacote sob proposta: piso de CONTRATO publicado (não mensalidade).
        self.assertEqual(items["company_enterprise"]["quote_floor_cents"], 250000)
        self.assertEqual(items["company_enterprise"]["obtained_by"], "contract_or_grant")
        self.assertEqual(items["osc_basic"]["obtained_by"], "core")

    def test_there_is_no_checkout_quote_or_subscription_route(self):
        c = acct("osc")
        for path in ("/v1/billing/checkout", "/v1/billing/quote", "/v1/billing/cancel", "/v1/billing/reactivate",
                     "/v1/billing/change-plan", "/v1/billing/portal", "/v1/billing/webhooks/stripe"):
            self.assertIn(c.post(path, {"plan_key": "osc_premium"}).status, (404, 405), path)
        self.assertEqual(Client().get("/v1/plans/price?plan_key=osc_premium").status, 404)
        b = billing(c)
        self.assertIsNone(b["subscription"])
        self.assertIsNone(b["trial"])
        self.assertIsNone(b["next_charge"])
        self.assertEqual(b["access"]["state"], "FREE_GRANT")      # campanha 2026 concedida no cadastro
        self.assertIn("não cobra assinatura", b["no_subscription"])

    def test_plan_has_no_effect_on_match_architecture(self):
        import re
        from pathlib import Path
        for f in Path(__file__).resolve().parents[1].joinpath("impacto", "engines", "match").glob("*.py"):
            for imp in re.findall(r"^\s*(?:from|import)\s+(\S+)", f.read_text(encoding="utf-8"), re.M):
                self.assertNotRegex(imp, r"monetization|entitlements|billing|voucher")


# ------------------------------------------------------------------------------------------------ vouchers
class VoucherTests(Base):
    def test_discount_vouchers_are_retired(self):
        """v0.27.0: não há assinatura para descontar. A administração não cria mais voucher de desconto; um
        voucher de desconto HISTÓRICO (inserido direto no banco) responde a mesma resposta genérica de um
        código inválido — não concede nada."""
        from impacto.api.billing_routes import code_hash
        c = acct("osc")
        r = self.adm1.post("/v1/admin/voucher-batches", {"campaign": "Desconto " + uuid.uuid4().hex[:4], "quantity": 1,
                                                          "type": "percent_off", "percent": 20, "plan_key": "osc_premium"})
        self.assertEqual(r.status, 422, r)
        code = "LEGA-CY" + uuid.uuid4().hex[:6].upper()
        with db_system() as d:
            bid = d.scalar("INSERT INTO voucher_batches(campaign, created_by, status) VALUES ('legado', $1, 'active') RETURNING id::text", self.adm1.user["id"])
            d.run("INSERT INTO vouchers(batch_id, code_hash, code_hint, type, plan_key, max_redemptions, value, created_by)"
                  " VALUES ($1,$2,'LEGA','percent_off','osc_premium',5,'{\"percent\": 20}'::jsonb,$3)",
                  bid, code_hash(server()["state"].settings.voucher_hmac_key, code), self.adm1.user["id"])
        r = c.post("/v1/vouchers/redeem", {"code": code})
        self.assertEqual(r.status, 404, r)
        self.assertNotIn("ai.assist.advanced", features(c))
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM voucher_redemptions WHERE org_id = $1", c.org_id), 0)

    def test_expired_and_exhausted_vouchers_fail(self):
        bid, codes = self.batch(type="grant_plan", plan_key="osc_premium", max_redemptions=1, duration_days=10)
        a, b = acct("osc"), acct("osc")
        self.assertEqual(a.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 200)
        self.assertEqual(b.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 404)       # limite excedido
        bid2, codes2 = self.batch(type="grant_plan", plan_key="osc_premium")
        with db_system() as d:
            d.run("UPDATE vouchers SET valid_until = now() - interval '1 day' WHERE batch_id = $1", bid2)
        self.assertEqual(b.post("/v1/vouchers/redeem", {"code": codes2[0]}).status, 404)      # expirado
        red = self.adm1.get(f"/v1/admin/voucher-batches/{bid}/redemptions")
        self.assertEqual(red.status, 200)
        self.assertEqual(red.json["items"][0]["redeemed_count"], 1)

    def test_voucher_grants_license_without_payment_and_cannot_be_reused(self):
        c = acct("osc")
        _, codes = self.batch(type="grant_plan", plan_key="osc_premium", duration_days=60, max_redemptions=5)
        r = c.post("/v1/vouchers/redeem", {"code": codes[0]})
        self.assertEqual(r.status, 200, r)
        self.assertFalse(r.json["pending_discount"])
        self.assertIn("ai.assist.advanced", features(c))
        self.assertEqual(c.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 404)       # mesma organização não reutiliza
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT status FROM voucher_redemptions WHERE org_id = $1", c.org_id), "applied")
            self.assertIsNotNone(d.scalar("SELECT ends_at FROM entitlement_grants WHERE org_id = $1 AND source = 'voucher'", c.org_id))

    def test_permanent_license_voucher(self):
        c = acct("osc")
        _, codes = self.batch(type="grant_plan", plan_key="osc_premium")      # sem duração = permanente
        self.assertEqual(c.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 200)
        self.assertIn("ai.assist.advanced", features(c))
        with db_system() as d:
            self.assertIsNone(d.scalar("SELECT ends_at FROM entitlement_grants WHERE org_id = $1 AND source = 'voucher'", c.org_id))


# ------------------------------------------------------------------------------------------------ convênios
class AgreementTests(Base):
    def mk_agreement(self, **kw):
        body = {"name": "Convênio Teste " + uuid.uuid4().hex[:4], "kind": "convention", "seats": 1, "plan_key": "osc_premium", **kw}
        r = self.adm1.post("/v1/admin/agreements", body)
        self.assertEqual(r.status, 201, r)
        return r.json["id"], r.json["code"]

    def activate(self, aid):
        self.assertEqual(self.adm1.post(f"/v1/admin/agreements/{aid}/action", {"action": "activate"}).json["code"], "second_approver_required")
        self.assertEqual(self.adm2.post(f"/v1/admin/agreements/{aid}/action", {"action": "activate"}).status, 200)

    def test_agreement_license_seats_domain_and_revoke(self):
        aid, code = self.mk_agreement(email_domains=["teste.org"], grant_days=90)
        a, b = acct("osc"), acct("osc")
        self.assertEqual(a.post("/v1/agreements/join", {"code": code}).status, 404)       # ainda rascunho: resposta genérica
        self.activate(aid)
        r = a.post("/v1/agreements/join", {"code": code})
        self.assertEqual(r.status, 200, r)
        self.assertIn("ai.assist.advanced", features(a))
        self.assertEqual(b.post("/v1/agreements/join", {"code": code}).json["code"], "agreement_full")    # 1 vaga
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT source FROM entitlement_grants WHERE agreement_id = $1", aid), "convention")
        self.assertEqual(self.adm1.post(f"/v1/admin/agreements/{aid}/members/{a.org_id}/revoke", {"reason": "desligamento"}).status, 200)
        self.assertNotIn("ai.assist.advanced", features(a))
        self.assertEqual(b.post("/v1/agreements/join", {"code": code}).status, 200)       # vaga liberada

    def test_domain_alone_is_not_enough_and_wrong_domain_is_generic(self):
        aid, code = self.mk_agreement(email_domains=["outra-empresa.com.br"])
        self.activate(aid)
        a = acct("osc")
        self.assertEqual(a.post("/v1/agreements/join", {"code": code}).status, 404)       # domínio do usuário não confere
        self.assertEqual(a.post("/v1/agreements/join", {"code": "AAAA-BBBB-CCCC"}).status, 404)   # sem código válido, nada

    def test_discount_agreement_is_retired(self):
        """v0.27.0: convênio só concede pacote; desconto percentual foi aposentado com a assinatura."""
        r = self.adm1.post("/v1/admin/agreements", {"name": "Convênio desconto", "kind": "convention", "seats": 10, "discount_percent": 20})
        self.assertEqual(r.status, 422, r)
        r = self.adm1.post("/v1/admin/agreements", {"name": "Convênio desconto", "kind": "convention", "seats": 10, "plan_key": "osc_premium", "discount_percent": 20})
        self.assertEqual((r.status, r.json["code"]), (422, "discount_retired"))

    def test_gov_agreement_grants_institutional_tier(self):
        aid, code = self.mk_agreement(kind="gov", plan_key="gov_institutional", seats=100, name="Órgão público de teste")
        self.activate(aid)
        g = acct("government")
        self.assertEqual(g.post("/v1/agreements/join", {"code": code}).status, 200)
        self.assertEqual(billing(g)["tier"], "gov")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT source FROM entitlement_grants WHERE org_id = $1", g.org_id), "gov")
        osc = acct("osc")
        self.assertEqual(osc.post("/v1/agreements/join", {"code": code}).status, 404)     # pacote de outro tipo de organização

    def test_license_revocation_requires_reason_and_keeps_history(self):
        c = acct("osc")
        gid = self.license(c.org_id, "osc_premium", days=None, source="partner")
        self.assertEqual(self.adm1.post(f"/v1/admin/grants/{gid}/revoke", {"reason": "x"}).status, 422)
        self.assertEqual(self.adm1.post(f"/v1/admin/grants/{gid}/revoke", {"reason": "fim da parceria"}).status, 200)
        self.assertNotIn("ai.assist.advanced", features(c))
        view = self.adm1.get(f"/v1/admin/billing/organizations/{c.org_id}").json
        self.assertEqual(view["grants"][0]["revoke_reason"], "fim da parceria")
        self.assertNotIn("subscriptions", view)
        self.assertNotIn("trial", view)

    def test_contract_license_replaces_manual_subscription(self):
        """v0.27.0: `manual-subscription` virou `license` — concessão com prazo, sem renovação."""
        c = acct("company")
        self.assertIn(self.adm1.post(f"/v1/admin/organizations/{c.org_id}/manual-subscription",
                                     {"plan_key": "company_enterprise", "months": 12, "reference": "CT-1"}).status, (404, 405))
        r = self.adm1.post(f"/v1/admin/organizations/{c.org_id}/license", {"plan_key": "company_enterprise", "months": 12, "reference": "CT-2026-001"})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(billing(c)["tier"], "premium")
        with db_system() as d:
            g = d.one("SELECT source, ends_at > now() + interval '11 months' AS prazo FROM entitlement_grants WHERE id = $1", r.json["id"])
        self.assertEqual((g["source"], g["prazo"]), ("license", True))
        self.assertEqual(self.adm1.post(f"/v1/admin/organizations/{c.org_id}/license",
                                        {"plan_key": "osc_premium", "months": 12, "reference": "CT-x"}).status, 422)   # pacote de outro tipo


# ------------------------------------------------------------------------------------------------ segurança da camada de acesso
class BillingSecurityTests(Base):
    def test_user_cannot_change_plan_or_rights(self):
        c = acct("osc")
        self.assertEqual(c.patch("/v1/org", {"plan_key": "osc_premium"}).status, 422)
        self.assertEqual(c.post("/v1/admin/organizations/" + c.org_id + "/grants", {"plan_key": "osc_premium", "days": 9, "reason": "eu mesma"}).status, 403)
        self.assertEqual(c.post("/v1/admin/commercial/offers", {"org_id": c.org_id, "plan_key": "osc_premium", "amount_cents": 1,
                                                                "amount_reason": "tentativa"}).status, 403)
        self.assertIn(c.put("/v1/admin/plans/osc_premium/price", {"interval": "month", "amount_cents": 1, "reason": "tentativa"}).status, (404, 405))
        self.assertNotIn("ai.assist.advanced", features(c))
        # banco: papel da aplicação com contexto da própria organização não escreve licença nem concessão
        from impacto.db.pool import DbContext
        st = server()["state"]
        for sql in ("INSERT INTO entitlement_grants(org_id, plan_key, source) VALUES ($1,'osc_premium','admin')",
                    "INSERT INTO free_periods(org_id, source, reason, pricing_version, months) VALUES ($1,'PROMOTION','eu mesma','x',3)"):
            with self.assertRaises(Exception):
                with st.pool.tx(DbContext(user_id=c.user["id"], org_id=c.org_id, org_kind="osc")) as d:
                    d.run(sql, c.org_id)
        self.assertNotIn("ai.assist.advanced", features(c))

    def test_cannot_see_or_touch_other_org_billing(self):
        a, b = acct("osc"), acct("osc")
        from impacto.db.pool import DbContext
        st = server()["state"]
        with st.pool.tx(DbContext(user_id=b.user["id"], org_id=b.org_id, org_kind="osc"), readonly=True) as d:
            for t in ("invoices", "entitlement_grants", "billing_notices", "agreement_members", "free_periods", "commercial_offers", "offer_acceptances"):
                self.assertEqual(d.scalar(f"SELECT count(*) FROM {t} WHERE org_id = $1", a.org_id), 0, t)
            self.assertEqual(d.scalar("SELECT count(*) FROM agreements"), 0)           # código/HMAC de convênio nunca visível a organizações
        self.assertEqual(b.get(f"/v1/admin/billing/organizations/{a.org_id}").status, 403)
        self.assertEqual(b.post("/v1/agreements/join", {"code": "XXXX-YYYY-ZZZZ"}).status, 404)

    def test_billing_requires_a_session(self):
        c = acct("osc")
        self.assertEqual(Client().get("/v1/billing").status, 401)
        self.assertEqual(c.get("/v1/billing").status, 200)

    def test_every_billing_route_declares_authorization(self):
        from impacto.http import ROUTES
        import impacto.api
        impacto.api.load_all()
        for r in ROUTES:
            if "/billing" in r.path or "/agreements" in r.path:
                self.assertTrue(r.auth != "none" or r.path == "/v1/plans", r.path)

    def test_no_card_data_columns_in_schema(self):
        with db_system() as d:
            cols = {r["column_name"] for r in d.query("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public'")}
        for bad in ("card_number", "cvv", "cvc", "pan", "card_exp"):
            self.assertNotIn(bad, cols)


if __name__ == "__main__":
    unittest.main()
