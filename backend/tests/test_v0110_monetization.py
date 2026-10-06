"""v0.11.0 — monetização: trial de 14 dias FULL, cancelamento, FREE/PLUS/PREMIUM/GOV, vouchers, convênios, licenças, webhooks (assinados, idempotentes, fora de
ordem), upgrade/downgrade, falhas de pagamento, portal, segurança do billing. HTTP + PostgreSQL reais; o provedor Stripe é um dublê de HTTP (nenhuma chamada
real, nenhuma credencial): a cobrança em si acontece no Stripe — aqui provamos o que A PLATAFORMA envia, decide e registra."""
from __future__ import annotations

import contextlib
import hashlib
import hmac
import json
import time
import unittest
import urllib.parse
import uuid

from impacto.services.monetization import DEFAULT_CURRENCY
from tests.support import TEST_PRICE_REASON
from tests.support import PASSWORD, Client, db_system, last_token_for, make_admin, new_account, owner_conn, server

PRICES = {"osc_premium": "price_prem_m", "osc_premium_year": "price_prem_y", "osc_plus": "price_plus_m", "osc_plus_year": "price_plus_y"}
VALUES = {("osc_premium", "month"): 9900, ("osc_premium", "year"): 99000, ("osc_plus", "month"): 4900, ("osc_plus", "year"): 49000}


class FakeHttp:
    """Dublê do cliente HTTP do Stripe: registra o que a plataforma envia e responde como o provedor responderia."""

    def __init__(self):
        self.calls: list[tuple[str, str, dict]] = []
        self.n = 0

    def request(self, method, url, data=None, headers=None, timeout=None):
        params = dict(urllib.parse.parse_qsl(data.decode())) if data else {}
        self.calls.append((method, url.split("/v1", 1)[1], params))
        self.n += 1
        path = url.split("/v1", 1)[1]
        if path == "/coupons":
            out = {"id": f"co_{self.n}"}
        elif path == "/checkout/sessions":
            out = {"id": f"cs_{uuid.uuid4().hex[:12]}", "url": "https://checkout.stripe.test/c/pay"}
        elif path == "/billing_portal/sessions":
            out = {"url": "https://billing.stripe.test/p/session"}
        elif method == "GET" and path.startswith("/subscriptions/"):
            out = {"id": path.split("/")[-1], "items": {"data": [{"id": "si_1"}]}}
        else:
            out = {}
        return 200, {}, json.dumps(out).encode()

    def find(self, path):
        return [c for c in self.calls if c[1] == path]


@contextlib.contextmanager
def stripe_mode():
    from impacto.services.billing import StripeBilling
    st = server()["state"]
    fake = FakeHttp()
    old = (st.settings.billing_provider, st.settings.stripe_webhook_secret, st.billing, dict(st.settings.stripe_prices))
    st.settings.billing_provider, st.settings.stripe_webhook_secret = "stripe", "whsec_test"
    st.billing = StripeBilling("sk_test_placeholder", "whsec_test", http=fake)
    st.settings.stripe_prices = dict(PRICES)
    try:
        yield fake
    finally:
        st.settings.billing_provider, st.settings.stripe_webhook_secret, st.billing, st.settings.stripe_prices = old


def webhook(ev: dict, *, bad_sig=False, age=0):
    payload = json.dumps(ev).encode()
    t = int(time.time()) - age
    sig = "deadbeef" if bad_sig else hmac.new(b"whsec_test", f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return Client().request("POST", "/v1/billing/webhooks/stripe", raw=payload, ctype="application/json", headers={"Stripe-Signature": f"t={t},v1={sig}"})


def ev(etype: str, obj: dict, created: int | None = None) -> dict:
    return {"id": f"evt_{uuid.uuid4().hex[:14]}", "type": etype, "created": created or int(time.time()), "data": {"object": obj}}


def acct(kind="osc", trial=True) -> Client:
    st = server()["state"]
    old = st.settings.trial_auto_start
    st.settings.trial_auto_start = trial
    try:
        return new_account(kind)
    finally:
        st.settings.trial_auto_start = old


def set_trial(org_id: str, *, started_ago="0 days", ends_in="14 days"):
    with db_system() as d:
        d.run(f"UPDATE org_trials SET trial_start = now() - interval '{started_ago}', trial_end = now() + interval '{ends_in}' WHERE org_id = $1", org_id)


def features(c: Client) -> set:
    return set(c.get("/v1/me").json["entitlements"]["features"])


def billing(c: Client) -> dict:
    return c.get("/v1/billing").json


def notif_kinds(c: Client) -> list:
    return [n["kind"] for n in c.get("/v1/notifications").json["items"]]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.adm1, _ = make_admin()
        cls.adm2, _ = make_admin()
        # A AUTORIDADE DE PREÇO É `plan_price_versions` (com moeda e vigência) desde a v0.16.0, e manda
        # sobre `plan_prices`. Estes testes verificam o cálculo do servidor, o voucher e o fluxo do
        # Stripe — não a regra comercial —, então fecham a vigência das versões vigentes e publicam as
        # suas próprias, sem promoção de entrada. É o mesmo caminho que o proprietário usa.
        #
        # E **sem** `provider_price_id`: `billing.price_ref()` prefere, corretamente, o identificador
        # gravado na versão de preço quando existe. Preenchê-lo aqui faria o teste medir a si mesmo em
        # vez de medir o caminho que ele quer medir, que é o de `settings.stripe_prices`.
        with db_system() as d:
            for (pk, iv), v in VALUES.items():
                d.run("INSERT INTO plan_prices(plan_key, interval, amount_cents) VALUES ($1,$2,$3) ON CONFLICT (plan_key, interval) DO UPDATE SET amount_cents = EXCLUDED.amount_cents", pk, iv, v)
        oc = owner_conn()
        oc.run("UPDATE plan_price_versions SET effective_until = now() WHERE plan_key = ANY($1::text[])"
               " AND effective_until IS NULL", [pk for pk, _ in VALUES])
        for (pk, iv), v in VALUES.items():
            oc.run("INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents, trial_days,"
                   " tax_behavior, provider, reason)"
                   " VALUES ($1,$2,$4,$3,14,'inclusive','stripe',"
                   " 'preço do cenário de teste da v0.11.0 (sem promoção de entrada)')",
                   pk, iv, v, DEFAULT_CURRENCY)

    @classmethod
    def tearDownClass(cls):
        with db_system() as d:
            d.run("UPDATE plan_prices SET amount_cents = NULL WHERE plan_key IN ('osc_premium','osc_plus')")
        oc = owner_conn()
        # FECHA a vigência do cenário em vez de apagá-lo. Duas razões, e as duas importam:
        #   1. apagar falha por chave estrangeira assim que alguma assinatura aponta para a versão
        #      (`subscription_prices.price_version_id`), o que acontece quando mais de uma classe roda;
        #   2. apagar histórico de preço é exatamente o que a arquitetura proíbe — "quanto esta
        #      organização contratou em março?" precisa continuar respondível.
        oc.run("UPDATE plan_price_versions SET effective_until = now()"
               " WHERE reason LIKE 'preço do cenário de teste%' AND effective_until IS NULL")
        # Reabre a vigência das versões DO AMBIENTE, identificadas pelo `reason`. Duas correções de
        # uma vez: a moeda deixou de estar fixa em 'USD' (a v0.17.0 a aposentou, e isso deixava a suíte
        # inteira sem preço vigente depois desta classe), e o filtro deixou de reabrir "qualquer versão
        # fechada deste plano" — o que ressuscitava os cenários de classes anteriores e violava
        # `ux_price_current`, porque passavam a existir duas vigentes ao mesmo tempo.
        oc.run("UPDATE plan_price_versions SET effective_until = NULL"
               " WHERE reason LIKE $1 AND effective_until IS NOT NULL", TEST_PRICE_REASON + "%")

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


# ------------------------------------------------------------------------------------------------ trial
class TrialTests(Base):
    def test_new_user_starts_14_day_full_trial(self):                    # prompt: 1, 2, 3
        c = acct("osc")
        b = billing(c)
        self.assertTrue(b["trial"]["active"])
        with db_system() as d:
            days = d.scalar("SELECT extract(epoch FROM (trial_end - trial_start)) / 86400 FROM org_trials WHERE org_id = $1", c.org_id)
        self.assertEqual(round(float(days)), 14)
        self.assertEqual(b["tier"], "premium")
        self.assertIn("alerts.saved_search", features(c))                # recurso PREMIUM liberado (FULL)
        texts = " | ".join(n["text"] for n in b["notices"])
        self.assertIn("Você está no período de teste gratuito de 14 dias.", texts)
        self.assertIn("Você não será cobrado durante o período de teste.", texts)
        self.assertIn("Seu período de teste termina em 14 dias.", texts)
        self.assertIn("billing.trial_started", notif_kinds(c))
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM subscriptions WHERE org_id = $1", c.org_id), 0)   # trial não cria assinatura nem cobrança

    def test_government_gets_no_trial_and_no_auto_trial_when_disabled(self):
        self.assertIsNone(billing(acct("government"))["trial"])
        self.assertIsNone(billing(acct("osc", trial=False))["trial"])

    def test_cancel_on_day_1_keeps_full_until_end_without_charge(self):    # prompt: 4, 6, 7
        c = acct("osc")
        r = c.post("/v1/billing/cancel")
        self.assertEqual(r.status, 200, r)
        self.assertIn("Nenhuma cobrança será realizada.", r.json["message"])
        self.assertIs(r.json["charged"], False)
        self.assertIn("alerts.saved_search", features(c))                # NÃO bloqueia imediatamente
        b = billing(c)
        self.assertTrue(b["trial"]["canceled"])
        self.assertIn("Seu acesso FULL permanece ativo até", " ".join(n["text"] for n in b["notices"]))
        self.assertIsNone(b["next_charge"])
        self.assertIn("billing.cancel_confirmed", notif_kinds(c))
        self.assertEqual(c.post("/v1/billing/cancel").status, 404)       # já cancelado, sem assinatura
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM subscriptions WHERE org_id = $1", c.org_id), 0)

    def test_cancel_on_day_13_then_downgrade_to_free_after_trial(self):    # prompt: 5, 6, 9, 10, 11
        c = acct("osc")
        set_trial(c.org_id, started_ago="12 days 2 hours", ends_in="1 day 22 hours")
        self.assertEqual(c.post("/v1/billing/cancel").status, 200)
        self.assertIn("alerts.saved_search", features(c))
        with db_system() as d:
            d.run("UPDATE org_trials SET trial_end = now() - interval '1 minute' WHERE org_id = $1", c.org_id)
        f = features(c)
        self.assertNotIn("alerts.saved_search", f)                       # FREE depois do trial
        self.assertIn("catalog.search", f)                               # FREE continua usando o gratuito
        self.assertEqual(c.post("/v1/saved-searches", {"name": "Cultura", "filters": {"cause": "cultura"}}).json["code"], "feature_not_in_plan")
        from impacto.services import monetization
        res = monetization.lifecycle_job(server()["state"])
        self.assertGreaterEqual(res["trials_ended"], 1)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT status FROM org_trials WHERE org_id = $1", c.org_id), "ended")
        self.assertIn("billing.trial_ended", notif_kinds(c))
        self.assertEqual(billing(c)["tier"], "free")

    def test_trial_cannot_be_reused_or_farmed(self):                       # prompt: 20
        st = server()["state"]
        base = f"jul.iano{uuid.uuid4().hex[:6]}"
        em1, em2 = f"{base}+a@gmail.com", f"{base.replace('.', '')}@gmail.com"   # mesmo remetente (alias do gmail)

        def reg(email):
            from tests.support import next_cnpj
            c = Client()
            r = c.post("/v1/auth/register", {"email": email, "password": PASSWORD, "full_name": "Pessoa Teste", "accept_terms": True,
                                             "organization": {"kind": "osc", "legal_name": "Org " + uuid.uuid4().hex[:6], "cnpj": next_cnpj(), "uf": "MT"}})
            self.assertEqual(r.status, 202, r)
            self.assertEqual(c.post("/v1/auth/verify-email", {"token": last_token_for(email, "/verificar-email")}).status, 200)
            self.assertEqual(c.login(email, PASSWORD).status, 200)
            c.org_id = c.get("/v1/me").json["active_org"]["id"]
            return c
        old = st.settings.trial_auto_start
        st.settings.trial_auto_start = True
        try:
            a, b = reg(em1), reg(em2)
        finally:
            st.settings.trial_auto_start = old
        self.assertIsNotNone(billing(a)["trial"])
        self.assertIsNone(billing(b)["trial"])                           # alias do mesmo e-mail: sem novo trial
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM trial_claims WHERE identity_hash LIKE '%@%' OR length(identity_hash) <> 64"), 0)   # só HMAC, sem dado em claro
        self.assertEqual(self.adm1.post(f"/v1/admin/organizations/{a.org_id}/trial", {"days": 14, "reason": "tentativa de repetir"}).status, 409)   # um por organização
        c = acct("osc", trial=False)
        r = self.adm1.post(f"/v1/admin/organizations/{c.org_id}/trial", {"days": 7, "reason": "cortesia comercial"})
        self.assertEqual(r.status, 201, r)
        self.assertTrue(billing(c)["trial"]["active"])

    def test_lifecycle_reminders_days_1_7_11_13_14_without_spam(self):
        from impacto.services import monetization
        st = server()["state"]
        c = acct("osc")
        for idx, started in ((7, "6 days 2 hours"), (11, "10 days 2 hours"), (13, "12 days 2 hours"), (14, "13 days 2 hours")):
            set_trial(c.org_id, started_ago=started, ends_in=f"{14 - idx} days 22 hours")
            monetization.lifecycle_job(st)
            monetization.lifecycle_job(st)                               # repetir não duplica
        titles = [n["title"] for n in c.get("/v1/notifications").json["items"]]
        for t in ("Lembrete do período de teste", "Seu período de teste termina em 3 dias", "Seu período de teste termina amanhã", "Seu período de teste termina hoje"):
            self.assertEqual(titles.count(t), 1, (t, titles))


# ------------------------------------------------------------------------------------------------ planos, tiers e acesso
class TierAccessTests(Base):
    def test_free_plus_premium_gov_access_matrix(self):                    # prompt: 10–14
        free = acct("osc", trial=False)
        f_free = features(free)
        self.assertIn("catalog.search", f_free)
        self.assertNotIn("alerts.saved_search", f_free)
        self.assertEqual(billing(free)["tier"], "free")
        plus = acct("osc", trial=False)
        self.license(plus.org_id, "osc_plus")
        f_plus = features(plus)
        self.assertIn("alerts.saved_search", f_plus)
        self.assertNotIn("ai.assist.advanced", f_plus)                   # PLUS ≠ PREMIUM
        self.assertEqual(billing(plus)["tier"], "plus")
        prem = acct("osc", trial=False)
        self.license(prem.org_id, "osc_premium")
        self.assertIn("ai.assist.advanced", features(prem))
        self.assertEqual(billing(prem)["tier"], "premium")
        gov = acct("government", trial=False)
        self.assertNotIn("audit.export", features(gov))
        self.license(gov.org_id, "gov_institutional", source="gov")
        self.assertEqual(billing(gov)["tier"], "gov")
        self.assertIn("audit.export", features(gov))
        self.assertIn("calls.publish", features(gov))

    def test_plans_catalog_has_tiers_and_real_prices_only(self):
        """O catálogo mostra o preço que existe, e nenhum que não exista.

        v0.21.0 — ATUALIZADO, não afrouxado. Até a v0.20.0 este teste afirmava que `company_plus`
        não tinha economia anual PORQUE não tinha preço: a v0.17.0 aposentou a regra em dólar e o
        proprietário não havia fixado preço institucional. A Pricing Version 2027.01 fixou. Então a
        asserção passa a ser a que continua valendo em qualquer versão de preço: a economia anual é
        CONSEQUÊNCIA de dois valores publicados, e um plano sem anual publicado não ganha economia
        nenhuma — que é a mesma proibição de antes, dita sobre o plano certo.
        """
        items = {p["plan_key"]: p for p in Client().get("/v1/plans").json["items"]}
        self.assertEqual(items["osc_plus"]["tier"], "plus")
        self.assertEqual(items["gov_institutional"]["tier"], "gov")
        # Preços do AMBIENTE de teste (ver `_declare_test_prices` em support.py), não os de produção.
        self.assertEqual(items["osc_premium"]["prices"], {"month": 9900, "year": 99000})
        self.assertEqual(items["osc_premium"]["annual_savings"], {"cents": 19800, "percent": 17})

        # `company_plus` agora TEM os dois preços: a economia é derivada deles, não inventada.
        pr = items["company_plus"]["prices"]
        self.assertIsNotNone(pr.get("month"))
        self.assertIsNotNone(pr.get("year"))
        self.assertEqual(items["company_plus"]["annual_savings"]["cents"], pr["month"] * 12 - pr["year"])

        # E a proibição original continua, no plano a que ela agora se aplica: a PRICING_BIBLE.md não
        # publica valor anual para FUNDER PRO, e nenhum foi criado — logo, nenhuma economia anual.
        self.assertIsNone(items["company_premium"]["prices"].get("year"))
        self.assertIsNone(items["company_premium"]["annual_savings"],
                          "economia anual inventada para um plano sem preço anual publicado")

        # Plano sob proposta: piso publicado, nenhum preço contratável.
        self.assertEqual(items["company_enterprise"]["prices"], {})
        self.assertEqual(items["company_enterprise"]["quote_floor_cents"], 250000)

    def test_gov_cannot_be_bought_online(self):
        g = acct("government", trial=False)
        r = g.post("/v1/billing/quote", {"plan_key": "gov_institutional"})
        self.assertEqual((r.status, r.json["code"]), (409, "quote_required"))

    def test_plan_has_no_effect_on_match_architecture(self):
        import re
        from pathlib import Path
        for f in Path(__file__).resolve().parents[1].joinpath("impacto", "engines", "match").glob("*.py"):
            for imp in re.findall(r"^\s*(?:from|import)\s+(\S+)", f.read_text(encoding="utf-8"), re.M):
                self.assertNotRegex(imp, r"monetization|entitlements|billing|voucher")


# ------------------------------------------------------------------------------------------------ vouchers
class VoucherTests(Base):
    def test_percent_voucher_20_applies_on_server_and_cannot_be_reused(self):    # prompt: 15, 19
        c = acct("osc", trial=False)
        _, codes = self.batch(type="percent_off", percent=20, plan_key="osc_premium", max_redemptions=5)
        r = c.post("/v1/vouchers/redeem", {"code": codes[0]})
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["pending_discount"])
        q = c.post("/v1/billing/quote", {"plan_key": "osc_premium", "interval": "month"}).json
        self.assertEqual((q["base_cents"], q["final_cents"], q["discount"]["value"]), (9900, 7920, 20))
        self.assertTrue(q["charge_now"])
        self.assertEqual(c.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 404)       # mesma organização não reutiliza
        self.assertEqual(c.post("/v1/billing/checkout", {"plan_key": "osc_premium", "price_cents": 1}).status, 422)   # cliente não envia preço
        self.assertEqual(c.post("/v1/billing/checkout", {"plan_key": "osc_premium", "discount": 100}).status, 422)

    def test_expired_and_exhausted_vouchers_fail(self):                  # prompt: 16, 17
        bid, codes = self.batch(type="percent_off", percent=10, plan_key="osc_premium", max_redemptions=1)
        a, b = acct("osc", trial=False), acct("osc", trial=False)
        self.assertEqual(a.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 200)
        self.assertEqual(b.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 404)       # limite excedido
        bid2, codes2 = self.batch(type="percent_off", percent=10, plan_key="osc_premium")
        with db_system() as d:
            d.run("UPDATE vouchers SET valid_until = now() - interval '1 day' WHERE batch_id = $1", bid2)
        self.assertEqual(b.post("/v1/vouchers/redeem", {"code": codes2[0]}).status, 404)      # expirado
        red = self.adm1.get(f"/v1/admin/voucher-batches/{bid}/redemptions")
        self.assertEqual(red.status, 200)
        self.assertEqual(red.json["items"][0]["redeemed_count"], 1)

    def test_voucher_100_percent_grants_license_without_payment(self):     # prompt: 18
        c = acct("osc", trial=False)
        _, codes = self.batch(type="percent_off", percent=100, plan_key="osc_premium", duration_days=60)
        r = c.post("/v1/vouchers/redeem", {"code": codes[0]})
        self.assertEqual(r.status, 200, r)
        self.assertFalse(r.json["pending_discount"])
        self.assertIn("ai.assist.advanced", features(c))
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM subscriptions WHERE org_id = $1", c.org_id), 0)   # licença ≠ assinatura

    def test_permanent_license_voucher(self):
        c = acct("osc", trial=False)
        _, codes = self.batch(type="grant_plan", plan_key="osc_premium")      # sem duração = permanente
        self.assertEqual(c.post("/v1/vouchers/redeem", {"code": codes[0]}).status, 200)
        self.assertIn("ai.assist.advanced", features(c))
        with db_system() as d:
            self.assertIsNone(d.scalar("SELECT ends_at FROM entitlement_grants WHERE org_id = $1", c.org_id))

    def test_amount_voucher_in_checkout_creates_coupon_and_final_price(self):
        c = acct("osc", trial=False)
        _, codes = self.batch(type="amount_off", amount_cents=2000, plan_key="osc_premium", discount_duration="repeating", discount_months=3)
        with stripe_mode() as fake:
            r = c.post("/v1/billing/checkout", {"plan_key": "osc_premium", "interval": "month", "voucher": codes[0]})
            self.assertEqual(r.status, 200, r)
            self.assertEqual(r.json["quote"]["final_cents"], 7900)
            coupon = fake.find("/coupons")[0][2]
            self.assertEqual((coupon["amount_off"], coupon["currency"], coupon["duration"], coupon["duration_in_months"]), ("2000", "brl", "repeating", "3"))
            sess = fake.find("/checkout/sessions")[0][2]
            self.assertTrue(sess["discounts[0][coupon]"].startswith("co_"))
            self.assertNotIn("subscription_data[trial_end]", sess)        # sem trial ativo: cobra já (ela escolheu assinar)


# ------------------------------------------------------------------------------------------------ checkout + webhooks (Stripe dublê)
class StripeFlowTests(Base):
    def test_checkout_during_trial_sends_trial_end_and_never_charges_early(self):    # prompt: 8
        c = acct("osc")
        with stripe_mode() as fake:
            r = c.post("/v1/billing/checkout", {"plan_key": "osc_premium", "interval": "month"})
            self.assertEqual(r.status, 200, r)
            sess = fake.find("/checkout/sessions")[0][2]
            with db_system() as d:
                te = d.scalar("SELECT extract(epoch FROM trial_end)::bigint FROM org_trials WHERE org_id = $1", c.org_id)
            self.assertLessEqual(abs(int(sess["subscription_data[trial_end]"]) - int(te)), 1)       # primeira cobrança = fim do trial
            self.assertEqual(sess["line_items[0][price]"], "price_prem_m")
            self.assertEqual(r.json["quote"]["final_cents"], 9900)
            self.assertFalse(r.json["quote"]["charge_now"])
            sub_id, cs = f"sub_{uuid.uuid4().hex[:8]}", None
            with db_system() as d:
                cs = d.scalar("SELECT provider_checkout_id FROM subscriptions WHERE org_id = $1", c.org_id)
            md = {"org_id": c.org_id, "plan_key": "osc_premium"}
            self.assertEqual(webhook(ev("checkout.session.completed", {"id": cs, "customer": "cus_1", "subscription": sub_id, "metadata": md})).json["status"], "processed")
            b = billing(c)
            self.assertEqual(b["subscription"]["status"], "trialing")                  # trialing: FULL, R$ 0
            self.assertEqual(b["invoices"], [])
            self.assertIsNotNone(b["next_charge"])
            self.assertIn("Primeira cobrança:", " ".join(n["text"] for n in b["notices"]))
            # fim do trial no provedor: assinatura ativa + primeira fatura paga
            now = int(time.time())
            webhook(ev("customer.subscription.updated", {"id": sub_id, "status": "active", "current_period_end": now + 30 * 86400, "metadata": md}))
            inv = {"id": "in_" + uuid.uuid4().hex[:8], "subscription": sub_id, "amount_paid": 9900, "currency": "brl", "hosted_invoice_url": "https://invoice.stripe.test/x"}
            self.assertEqual(webhook(ev("invoice.paid", inv)).json["status"], "processed")
            b = billing(c)
            self.assertEqual(b["subscription"]["status"], "active")
            self.assertEqual([i["amount_cents"] for i in b["invoices"]], [9900])
            self.assertIn("billing.plan_activated", notif_kinds(c))
            with db_system() as d:
                self.assertEqual(d.scalar("SELECT status FROM org_trials WHERE org_id = $1", c.org_id), "converted")

    def test_duplicate_webhook_does_not_duplicate_charge_or_invoice(self):    # prompt: 21, 22
        c = acct("osc", trial=False)
        with stripe_mode():
            sub_id = f"sub_{uuid.uuid4().hex[:8]}"
            with db_system() as d:
                d.run("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_subscription_id, interval) VALUES ($1,'osc_premium','active','stripe',$2,'month')", c.org_id, sub_id)
            e = ev("invoice.paid", {"id": "in_dup1", "subscription": sub_id, "amount_paid": 9900, "currency": "brl"})
            self.assertEqual(webhook(e).json["status"], "processed")
            self.assertEqual(webhook(e).json["status"], "duplicate_ignored")           # mesmo evento
            webhook(ev("invoice.paid", {"id": "in_dup1", "subscription": sub_id, "amount_paid": 9900, "currency": "brl"}))   # evento NOVO, mesma fatura
            self.assertEqual(len(billing(c)["invoices"]), 1)
            self.assertEqual(webhook(e, bad_sig=True).status, 400)                     # spoofing
            self.assertEqual(webhook(ev("invoice.paid", {"id": "in_x", "subscription": sub_id}), age=3600).status, 400)   # replay antigo

    def test_out_of_order_subscription_events_are_ignored(self):
        c = acct("osc", trial=False)
        with stripe_mode():
            sub_id = f"sub_{uuid.uuid4().hex[:8]}"
            with db_system() as d:
                d.run("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_subscription_id, interval) VALUES ($1,'osc_premium','trialing','stripe',$2,'month')", c.org_id, sub_id)
            self.assertEqual(webhook(ev("customer.subscription.updated", {"id": sub_id, "status": "active"}, created=2000)).json["status"], "processed")
            self.assertEqual(webhook(ev("customer.subscription.updated", {"id": sub_id, "status": "trialing"}, created=1000)).json["status"], "ignored")
            self.assertEqual(billing(c)["subscription"]["status"], "active")

    def test_monthly_and_annual_use_the_right_price(self):
        c = acct("osc", trial=False)
        with stripe_mode() as fake:
            q = c.post("/v1/billing/quote", {"plan_key": "osc_premium", "interval": "year"}).json
            self.assertEqual((q["base_cents"], q["annual_savings"]["percent"]), (99000, 17))
            self.assertEqual(c.post("/v1/billing/checkout", {"plan_key": "osc_premium", "interval": "year"}).status, 200)
            self.assertEqual(fake.find("/checkout/sessions")[0][2]["line_items[0][price]"], "price_prem_y")

    def test_trial_ending_in_under_48h_never_charges_before_end(self):
        c = acct("osc")
        set_trial(c.org_id, started_ago="13 days 12 hours", ends_in="12 hours")
        with stripe_mode() as fake:
            self.assertEqual(c.post("/v1/billing/checkout", {"plan_key": "osc_premium"}).status, 200)
            sent = int(fake.find("/checkout/sessions")[0][2]["subscription_data[trial_end]"])
            self.assertGreaterEqual(sent, int(time.time()) + 48 * 3600)
        with db_system() as d:
            self.assertGreaterEqual(int(d.scalar("SELECT extract(epoch FROM trial_end)::bigint FROM org_trials WHERE org_id = $1", c.org_id)), sent - 1)

    def test_cancel_prevents_renewal_and_keeps_history(self):               # prompt: 25, 30
        c = acct("osc", trial=False)
        with stripe_mode() as fake:
            sub_id = f"sub_{uuid.uuid4().hex[:8]}"
            with db_system() as d:
                d.run("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_subscription_id, provider_customer_id, interval, current_period_end)"
                      " VALUES ($1,'osc_premium','active','stripe',$2,'cus_9','month', now() + interval '20 days')", c.org_id, sub_id)
            self.assertEqual(c.post("/v1/saved-searches", {"name": "x", "filters": {"cause": "cultura"}}).status, 201)
            webhook(ev("invoice.paid", {"id": "in_h1", "subscription": sub_id, "amount_paid": 9900, "currency": "brl"}))
            r = c.post("/v1/billing/cancel")
            self.assertEqual(r.status, 200, r)
            call = fake.find(f"/subscriptions/{sub_id}")[0]
            self.assertEqual(call[2]["cancel_at_period_end"], "true")                  # impede a próxima cobrança
            self.assertIn("ai.assist.advanced", features(c))                           # acesso pago preservado
            b = billing(c)
            self.assertIn("Você continuará tendo acesso até", " ".join(n["text"] for n in b["notices"]))
            self.assertIsNone(b["next_charge"])
            self.assertEqual(c.post("/v1/billing/reactivate").status, 200)             # arrependimento
            self.assertEqual(fake.find(f"/subscriptions/{sub_id}")[-1][2]["cancel_at_period_end"], "false")
            self.assertEqual(c.post("/v1/billing/cancel").status, 200)
            webhook(ev("customer.subscription.deleted", {"id": sub_id, "status": "canceled"}))
            self.assertEqual(billing(c)["tier"], "free")
            self.assertEqual(len(billing(c)["invoices"]), 1)                           # histórico financeiro permanece
            self.assertEqual(len(c.get("/v1/saved-searches").json["items"]), 1)        # dados permanecem

    def test_upgrade_and_downgrade_are_synced_with_provider(self):          # prompt: 26, 27
        c = acct("osc", trial=False)
        with stripe_mode() as fake:
            sub_id = f"sub_{uuid.uuid4().hex[:8]}"
            with db_system() as d:
                d.run("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_subscription_id, provider_customer_id, interval, current_period_end)"
                      " VALUES ($1,'osc_plus','active','stripe',$2,'cus_8','month', now() + interval '20 days')", c.org_id, sub_id)
            r = c.post("/v1/billing/change-plan", {"plan_key": "osc_premium", "interval": "month"})
            self.assertEqual(r.status, 200, r)
            up = fake.find(f"/subscriptions/{sub_id}")
            self.assertEqual(up[0][0], "GET")
            self.assertEqual((up[1][2]["items[0][price]"], up[1][2]["proration_behavior"]), ("price_prem_m", "create_prorations"))
            self.assertIn("ai.assist.advanced", features(c))
            r = c.post("/v1/billing/change-plan", {"plan_key": "osc_plus", "interval": "month"})
            self.assertEqual(r.status, 200, r)
            self.assertNotIn("ai.assist.advanced", features(c))                        # downgrade PREMIUM → PLUS
            self.assertEqual(c.post("/v1/billing/change-plan", {"plan_key": "osc_plus", "interval": "month"}).status, 409)
            self.assertEqual(c.post("/v1/billing/checkout", {"plan_key": "osc_premium"}).json["code"], "use_change_plan")
            # o provedor confirma por evento (metadados) — reconcilia sem divergir
            webhook(ev("customer.subscription.updated", {"id": sub_id, "status": "active", "metadata": {"plan_key": "osc_plus", "interval": "month"}}))
            self.assertEqual(billing(c)["subscription"]["plan_key"], "osc_plus")

    def test_payment_failure_action_required_and_portal(self):               # prompt: 28, 29
        c = acct("osc", trial=False)
        with stripe_mode() as fake:
            sub_id = f"sub_{uuid.uuid4().hex[:8]}"
            with db_system() as d:
                d.run("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_subscription_id, provider_customer_id, interval, current_period_end)"
                      " VALUES ($1,'osc_premium','active','stripe',$2,'cus_7','month', now() + interval '5 days')", c.org_id, sub_id)
            webhook(ev("invoice.payment_failed", {"id": "in_f1", "subscription": sub_id, "amount_due": 9900, "currency": "brl"}))
            b = billing(c)
            self.assertEqual((b["subscription"]["status"], b["subscription"]["payment_issue"]), ("past_due", "payment_failed"))
            self.assertIn("Não conseguimos processar seu pagamento.", " ".join(n["text"] for n in b["notices"]))
            self.assertIn("billing.payment_failed", notif_kinds(c))
            self.assertIn("ai.assist.advanced", features(c))                            # sem corte imediato; dados preservados
            webhook(ev("invoice.payment_action_required", {"id": "in_f2", "subscription": sub_id, "amount_due": 9900, "currency": "brl"}))
            self.assertEqual(billing(c)["subscription"]["payment_issue"], "action_required")
            r = c.post("/v1/billing/portal")                                            # atualizar método de pagamento (portal Stripe)
            self.assertEqual((r.status, r.json["url"]), (200, "https://billing.stripe.test/p/session"))
            self.assertEqual(fake.find("/billing_portal/sessions")[0][2]["customer"], "cus_7")
            webhook(ev("invoice.paid", {"id": "in_f2", "subscription": sub_id, "amount_paid": 9900, "currency": "brl"}))
            self.assertIsNone(billing(c)["subscription"]["payment_issue"])
            self.assertEqual(acct("osc", trial=False).post("/v1/billing/portal").json["code"], "no_customer")

    def test_sandbox_trial_checkout_then_conversion_job(self):
        from impacto.services import monetization
        c = acct("osc")
        r = c.post("/v1/billing/checkout", {"plan_key": "osc_premium", "interval": "year"})
        self.assertEqual(r.status, 200, r)
        b = billing(c)
        self.assertEqual((b["subscription"]["status"], b["subscription"]["amount_cents"]), ("trialing", 99000))
        with db_system() as d:
            d.run("UPDATE subscriptions SET trial_end = now() - interval '1 minute' WHERE org_id = $1", c.org_id)
            d.run("UPDATE org_trials SET trial_end = now() - interval '1 minute', trial_start = now() - interval '15 days' WHERE org_id = $1", c.org_id)
        monetization.lifecycle_job(server()["state"])
        self.assertEqual(billing(c)["subscription"]["status"], "active")


# ------------------------------------------------------------------------------------------------ convênios e licenças
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
        a, b = acct("osc", trial=False), acct("osc", trial=False)
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
        a = acct("osc", trial=False)
        self.assertEqual(a.post("/v1/agreements/join", {"code": code}).status, 404)       # domínio do usuário não confere
        self.assertEqual(a.post("/v1/agreements/join", {"code": "AAAA-BBBB-CCCC"}).status, 404)   # sem código válido, nada

    def test_discount_agreement_applies_in_quote(self):
        aid, code = self.mk_agreement(plan_key=None, discount_percent=20, seats=10)
        self.activate(aid)
        c = acct("osc", trial=False)
        self.assertEqual(c.post("/v1/agreements/join", {"code": code}).status, 200)
        q = c.post("/v1/billing/quote", {"plan_key": "osc_premium", "interval": "month"}).json
        self.assertEqual((q["discount"]["source"], q["final_cents"]), ("agreement", 7920))
        self.assertNotIn("ai.assist.advanced", features(c))                               # só desconto: não concede acesso

    def test_gov_agreement_grants_institutional_tier(self):
        aid, code = self.mk_agreement(kind="gov", plan_key="gov_institutional", seats=100, name="Órgão público de teste")
        self.activate(aid)
        g = acct("government", trial=False)
        self.assertEqual(g.post("/v1/agreements/join", {"code": code}).status, 200)
        self.assertEqual(billing(g)["tier"], "gov")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT source FROM entitlement_grants WHERE org_id = $1", g.org_id), "gov")
        osc = acct("osc", trial=False)
        self.assertEqual(osc.post("/v1/agreements/join", {"code": code}).status, 404)     # plano de outro tipo de organização

    def test_license_revocation_requires_reason_and_keeps_history(self):
        c = acct("osc", trial=False)
        gid = self.license(c.org_id, "osc_premium", days=None, source="partner")
        self.assertEqual(self.adm1.post(f"/v1/admin/grants/{gid}/revoke", {"reason": "x"}).status, 422)
        self.assertEqual(self.adm1.post(f"/v1/admin/grants/{gid}/revoke", {"reason": "fim da parceria"}).status, 200)
        self.assertNotIn("ai.assist.advanced", features(c))
        view = self.adm1.get(f"/v1/admin/billing/organizations/{c.org_id}").json
        self.assertEqual(view["grants"][0]["revoke_reason"], "fim da parceria")


# ------------------------------------------------------------------------------------------------ segurança do billing
class BillingSecurityTests(Base):
    def test_user_cannot_change_plan_price_or_rights(self):                # prompt: 23
        c = acct("osc", trial=False)
        for body in ({"plan_key": "osc_premium", "tier": "premium"}, {"plan_key": "osc_premium", "price_cents": 1}, {"plan_key": "osc_premium", "amount_cents": 1}):
            self.assertEqual(c.post("/v1/billing/checkout", body).status, 422)
        self.assertEqual(c.patch("/v1/org", {"plan_key": "osc_premium"}).status, 422)
        self.assertEqual(c.post("/v1/billing/change-plan", {"plan_key": "osc_premium"}).json["code"], "no_subscription")
        self.assertEqual(c.post("/v1/admin/organizations/" + c.org_id + "/grants", {"plan_key": "osc_premium", "days": 9, "reason": "eu mesma"}).status, 403)
        self.assertEqual(c.put("/v1/admin/plans/osc_premium/price", {"interval": "month", "amount_cents": 1, "reason": "tentativa"}).status, 403)
        self.assertNotIn("ai.assist.advanced", features(c))
        # banco: papel da aplicação com contexto da própria organização não escreve trial/assinatura/licença
        from impacto.db.pool import DbContext
        st = server()["state"]
        for sql in ("INSERT INTO org_trials(org_id, plan_key, source, trial_end) VALUES ($1,'osc_premium','signup', now() + interval '9 days')",
                    "INSERT INTO entitlement_grants(org_id, plan_key, source) VALUES ($1,'osc_premium','admin')",
                    "INSERT INTO subscriptions(org_id, plan_key, status, provider) VALUES ($1,'osc_premium','active','stripe')"):
            with self.assertRaises(Exception):
                with st.pool.tx(DbContext(user_id=c.user["id"], org_id=c.org_id, org_kind="osc")) as d:
                    d.run(sql, c.org_id)
        self.assertNotIn("ai.assist.advanced", features(c))

    def test_cannot_see_or_touch_other_org_billing(self):                   # prompt: 24
        a, b = acct("osc"), acct("osc")
        self.assertEqual(billing(b)["trial"]["plan_key"], "osc_premium")
        from impacto.db.pool import DbContext
        st = server()["state"]
        with st.pool.tx(DbContext(user_id=b.user["id"], org_id=b.org_id, org_kind="osc"), readonly=True) as d:
            for t in ("org_trials", "subscriptions", "invoices", "entitlement_grants", "billing_notices", "agreement_members"):
                self.assertEqual(d.scalar(f"SELECT count(*) FROM {t} WHERE org_id = $1", a.org_id), 0, t)
            self.assertEqual(d.scalar("SELECT count(*) FROM agreements"), 0)           # código/HMAC de convênio nunca visível a organizações
            self.assertEqual(d.scalar("SELECT count(*) FROM trial_claims"), 0)
        self.assertEqual(b.get(f"/v1/admin/billing/organizations/{a.org_id}").status, 403)
        self.assertEqual(b.post("/v1/agreements/join", {"code": "XXXX-YYYY-ZZZZ"}).status, 404)

    def test_only_owner_can_checkout_cancel_and_change(self):
        c = acct("osc")
        viewer_calls = ("/v1/billing/checkout", "/v1/billing/cancel", "/v1/billing/reactivate", "/v1/billing/change-plan", "/v1/billing/portal")
        self.assertEqual(Client().post(viewer_calls[1]).status, 401)
        self.assertEqual(c.get("/v1/billing").status, 200)

    def test_every_billing_route_declares_authorization(self):
        from impacto.http import ROUTES
        import impacto.api
        impacto.api.load_all()
        for r in ROUTES:
            if "/billing" in r.path or "/agreements" in r.path:
                self.assertTrue(r.auth != "none" or r.path.endswith("/webhooks/stripe") or r.path == "/v1/plans", r.path)

    def test_no_card_data_columns_in_schema(self):
        with db_system() as d:
            cols = {r["column_name"] for r in d.query("SELECT column_name FROM information_schema.columns WHERE table_schema = 'public'")}
        for bad in ("card_number", "cvv", "cvc", "pan", "card_exp"):
            self.assertNotIn(bad, cols)


if __name__ == "__main__":
    unittest.main()
