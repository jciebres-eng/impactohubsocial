"""v0.16.0 — cobrança v2: preço versionado, moeda, preço de entrada, imposto e as travas contra mudança silenciosa.

A regra comercial desta rodada (ditada pelo proprietário do produto):
  14 dias de teste com o produto completo → US$ 1,99/mês nos 3 primeiros meses pagos → US$ 19,99/mês,
  ou o anual equivalente a US$ 14,99/mês (US$ 179,88 à vista).

Nenhum teste aqui afirma que a cobrança está integrada. O provedor não está configurado nesta instalação, e é
exatamente isso que um dos testes verifica: a plataforma RECUSA cobrar sem identificador de preço no provedor, em vez
de tentar e falhar de forma obscura.
"""
from __future__ import annotations

import unittest

from tests.support import Client, db_system, new_account, owner_conn


class PricingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.anon = Client()

    # ------------------------------------------------------------------ a regra comercial
    def test_commercial_rule_comes_from_the_database(self):
        r = self.anon.get("/v1/plans/price?plan_key=osc_premium&interval=month")
        self.assertEqual(r.status, 200, r)
        d = r.json
        self.assertEqual(d["currency"], "USD")
        self.assertEqual(d["amount_cents"], 1999, "preço regular: US$ 19,99/mês")
        self.assertEqual(d["intro"]["amount_cents"], 199, "entrada: US$ 1,99")
        self.assertEqual(d["intro"]["periods"], 3, "por 3 meses pagos")
        self.assertEqual(d["intro"]["then_amount_cents"], 1999)
        self.assertEqual(d["trial_days"], 14)
        self.assertIn("1.99", d["intro"]["summary"])
        self.assertIn("19.99", d["intro"]["summary"], "o preço DEPOIS tem de estar na mesma frase")

    def test_annual_shows_both_the_monthly_equivalent_and_the_total(self):
        """Mostrar só "US$ 14,99/mês" e cobrar US$ 179,88 de uma vez é o padrão escuro clássico."""
        r = self.anon.get("/v1/plans/price?plan_key=osc_premium&interval=year")
        self.assertEqual(r.status, 200, r)
        d = r.json
        self.assertEqual(d["amount_cents"], 17988, "total anual: US$ 179,88")
        self.assertEqual(d["monthly_equivalent_cents"], 1499, "equivalente mensal: US$ 14,99")
        self.assertIn("179.88", d["total_note"], "o TOTAL aparece junto do equivalente mensal")
        self.assertEqual(d["monthly_equivalent_cents"] * 12, d["amount_cents"],
                         "o equivalente mensal tem de fechar com o total; número de marketing não serve")

    def test_tax_behaviour_is_declared_before_payment(self):
        for interval in ("month", "year"):
            d = self.anon.get(f"/v1/plans/price?plan_key=osc_premium&interval={interval}").json
            self.assertIn(d["tax_behavior"], ("inclusive", "exclusive", "unspecified"))
            self.assertTrue(d["tax_note"], interval)

    def test_price_is_not_in_the_code(self):
        """O valor vem do banco: mudar a tabela muda a resposta, sem tocar em código."""
        oc = owner_conn()
        oc.run("UPDATE plan_price_versions SET effective_until = now() - interval '1 second'"
               " WHERE plan_key = 'provider_premium' AND interval = 'month' AND effective_until IS NULL")
        r = self.anon.get("/v1/plans/price?plan_key=provider_premium&interval=month")
        self.assertEqual(r.status, 404, "sem versão vigente, a plataforma diz que não há preço publicado")
        self.assertEqual(r.json["code"], "price_not_defined")

    def test_catalog_carries_the_quotes_for_both_intervals(self):
        plans = self.anon.get("/v1/plans").json
        prem = next(p for p in plans["items"] if p["plan_key"] == "osc_premium")
        self.assertEqual(set(prem["price_quotes"].keys()), {"month", "year"})
        self.assertEqual(prem["currency"], "USD")
        self.assertIn("Imposto", plans["pricing_note"])

    # ------------------------------------------------------------------ travas
    def test_checkout_refuses_when_the_real_provider_has_no_published_price(self):
        """Com provedor REAL e sem preço publicado nele, a plataforma recusa — e diz o motivo verdadeiro.

        A recusa é condicionada ao provedor de propósito: o provedor de teste (sandbox) não publica preço nenhum,
        então exigir identificador nele quebraria o fluxo de desenvolvimento e de demonstração. Quem precisa do
        identificador é quem cobra de verdade. Este teste usa o provedor real com cliente HTTP dublê e NENHUM preço
        configurado, que é a situação desta instalação hoje.
        """
        from tests.test_v0110_monetization import FakeHttp
        from impacto.services.billing import StripeBilling
        from tests.support import server
        st = server()["state"]
        old = (st.settings.billing_provider, st.billing, dict(st.settings.stripe_prices))
        st.settings.billing_provider = "stripe"
        st.billing = StripeBilling("sk_test_placeholder", "whsec_test", http=FakeHttp())
        st.settings.stripe_prices = {}
        try:
            r = self.osc.post("/v1/billing/checkout", {"plan_key": "osc_premium", "interval": "month"})
        finally:
            st.settings.billing_provider, st.billing, st.settings.stripe_prices = old
        self.assertEqual(r.status, 503, r)
        self.assertEqual(r.json["code"], "provider_price_missing")
        self.assertIn("provedor de pagamento", r.json["title"])

    def test_sandbox_does_not_require_a_published_price(self):
        """E no provedor de teste a contratação funciona, dizendo em letras que nada foi cobrado."""
        org = new_account("osc", compliance="approved")
        r = org.post("/v1/billing/checkout", {"plan_key": "osc_premium", "interval": "month"})
        self.assertEqual(r.status, 200, r)
        self.assertIn("SANDBOX", r.json["warning"])
        self.assertEqual(r.json["quote"]["first_price_source"], "intro",
                         "a primeira fatura sai pelo preço de entrada")
        self.assertEqual(r.json["quote"]["first_cents"], 199)
        self.assertEqual(r.json["quote"]["base_cents"], 1999, "e o preço regular continua declarado")

    def test_a_price_version_is_never_rewritten(self):
        oc = owner_conn()
        vid = oc.scalar("SELECT id::text FROM plan_price_versions WHERE plan_key = 'osc_premium'"
                        " AND interval = 'month' AND effective_until IS NULL")
        # Duas trancas, porque é dinheiro. Primeira: a coluna de valor está fora do GRANT, então nem a
        # administração a alcança pelo caminho da aplicação.
        with db_system() as c, self.assertRaises(Exception) as e:
            c.run("UPDATE plan_price_versions SET amount_cents = 100 WHERE id = $1", vid)
        self.assertIn("permission denied", str(e.exception).lower())
        # Segunda tranca: o gatilho. Hoje ele é inalcançável pelo caminho da aplicação — justamente porque a
        # coluna está fora do GRANT, o PostgreSQL recusa antes de chegar ao gatilho. Ele existe para o dia em que
        # alguém ampliar o GRANT numa migração futura, e por isso o teste confere que ele CONTINUA ligado: a
        # garantia "versão de preço não se reescreve" não pode depender de uma única tranca.
        oc2 = owner_conn()
        trg = oc2.one("SELECT t.tgname, p.proname FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid"
                      " WHERE t.tgrelid = 'plan_price_versions'::regclass AND NOT t.tgisinternal"
                      "   AND p.proname = 'price_version_immutable'")
        self.assertIsNotNone(trg, "o gatilho de imutabilidade do preço foi removido")
        granted = {r["column_name"] for r in oc2.query(
            "SELECT column_name FROM information_schema.column_privileges WHERE table_name ="
            " 'plan_price_versions' AND grantee = 'impacto_app' AND privilege_type = 'UPDATE'")}
        self.assertFalse(granted & {"amount_cents", "intro_amount_cents", "intro_periods", "currency",
                                    "plan_key", "interval", "effective_from"},
                         "coluna de valor não pode entrar no GRANT de UPDATE da aplicação")
        # Fechar a vigência, por outro lado, é permitido: é exatamente assim que se troca de preço.
        with db_system() as c:
            c.run("UPDATE plan_price_versions SET provider_price_id = 'price_exemplo_do_teste' WHERE id = $1", vid)
            c.run("UPDATE plan_price_versions SET provider_price_id = NULL WHERE id = $1", vid)

    def test_intro_price_cannot_exceed_the_regular_price(self):
        oc = owner_conn()
        with self.assertRaises(Exception) as e:
            oc.run("INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents,"
                   " intro_amount_cents, intro_periods, tax_behavior, reason)"
                   " VALUES ('osc_plus','month','USD',1000,2000,3,'exclusive','teste de promoção impossível')")
        self.assertIn("intro_is_cheaper", str(e.exception))

    def test_intro_needs_both_price_and_duration(self):
        oc = owner_conn()
        with self.assertRaises(Exception) as e:
            oc.run("INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents,"
                   " intro_amount_cents, tax_behavior, reason)"
                   " VALUES ('osc_plus','year','USD',5000,1000,'exclusive','promoção sem prazo definido')")
        self.assertIn("intro_pair", str(e.exception),
                      "promoção sem prazo é padrão escuro: o banco recusa")

    def test_price_increase_requires_a_notice_with_thirty_days(self):
        """"Nunca mudar preço silenciosamente" é uma trava do banco, não uma frase na documentação."""
        org = new_account("osc", compliance="approved")
        oc = owner_conn()
        v_low = oc.scalar(
            "INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents, tax_behavior, reason)"
            " VALUES ('osc_premium','month','BRL',1000,'inclusive','preço inicial do teste') RETURNING id::text")
        # Trocar de preço é fechar a vigência da versão atual e criar a nova. O índice `ux_price_current` garante
        # que não existam duas vigentes ao mesmo tempo — dois preços válidos simultâneos seriam indefensáveis.
        oc.run("UPDATE plan_price_versions SET effective_until = now() + interval '1 day' WHERE id = $1", v_low)
        v_high = oc.scalar(
            "INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents, tax_behavior, reason,"
            " effective_from) VALUES ('osc_premium','month','BRL',5000,'inclusive','reajuste do teste',"
            " now() + interval '1 day') RETURNING id::text")
        oc.run("INSERT INTO subscription_prices(org_id, price_version_id, plan_key, interval, currency,"
               " amount_cents, tax_behavior) VALUES ($1,$2,'osc_premium','month','BRL',1000,'inclusive')",
               org.org_id, v_low)
        # aviso na véspera é recusado: avisar com um dia é tecnicamente avisar e na prática não é
        with self.assertRaises(Exception) as e:
            oc.run("INSERT INTO price_change_notices(org_id, to_price_version_id, to_amount_cents, currency,"
                   " effective_at, channel, reason) VALUES ($1,$2,5000,'BRL', now() + interval '1 day','both',"
                   " 'aviso de véspera')", org.org_id, v_high)
        self.assertIn("30 dias", str(e.exception))
        # e aplicar o aumento sem aviso nenhum também é recusado
        with self.assertRaises(Exception) as e:
            oc.run("INSERT INTO subscription_prices(org_id, price_version_id, plan_key, interval, currency,"
                   " amount_cents, tax_behavior) VALUES ($1,$2,'osc_premium','month','BRL',5000,'inclusive')",
                   org.org_id, v_high)
        self.assertIn("aviso prévio", str(e.exception))

    def test_a_price_reduction_needs_no_notice(self):
        """A carência protege quem paga, não a plataforma: baixar preço não precisa de 30 dias."""
        org = new_account("osc", compliance="approved")
        oc = owner_conn()
        v_high = oc.scalar(
            "INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents, tax_behavior, reason)"
            " VALUES ('osc_premium','year','BRL',50000,'inclusive','preço alto do teste') RETURNING id::text")
        oc.run("UPDATE plan_price_versions SET effective_until = now() + interval '1 second' WHERE id = $1",
               v_high)
        v_low = oc.scalar(
            "INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents, tax_behavior, reason,"
            " effective_from) VALUES ('osc_premium','year','BRL',10000,'inclusive','redução do teste',"
            " now() + interval '1 second') RETURNING id::text")
        oc.run("INSERT INTO subscription_prices(org_id, price_version_id, plan_key, interval, currency,"
               " amount_cents, tax_behavior) VALUES ($1,$2,'osc_premium','year','BRL',50000,'inclusive')",
               org.org_id, v_high)
        oc.run("UPDATE subscription_prices SET ends_at = now() WHERE org_id = $1 AND ends_at IS NULL", org.org_id)
        oc.run("INSERT INTO subscription_prices(org_id, price_version_id, plan_key, interval, currency,"
               " amount_cents, tax_behavior) VALUES ($1,$2,'osc_premium','year','BRL',10000,'inclusive')",
               org.org_id, v_low)
        hist = org.get("/v1/billing/price-history")
        self.assertEqual(hist.status, 200, hist)
        self.assertEqual(len(hist.json["accepted"]), 2)
        self.assertEqual(hist.json["accepted"][0]["amount_cents"], 10000)

    def test_only_one_current_version_per_plan_interval_currency(self):
        oc = owner_conn()
        with self.assertRaises(Exception) as e:
            oc.run("INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents, tax_behavior,"
                   " reason) VALUES ('company_premium','month','USD',2999,'exclusive','segunda versão vigente')")
        self.assertIn("ux_price_current", str(e.exception),
                      "duas versões vigentes significariam dois preços válidos ao mesmo tempo")

    def test_organization_sees_its_own_price_history_and_acknowledges_notices(self):
        org = new_account("osc", compliance="approved")
        oc = owner_conn()
        v = oc.scalar("SELECT id::text FROM plan_price_versions WHERE plan_key = 'osc_premium'"
                      " AND interval = 'month' AND currency = 'USD' AND effective_until IS NULL")
        nid = oc.scalar("INSERT INTO price_change_notices(org_id, to_price_version_id, to_amount_cents, currency,"
                        " effective_at, channel, reason) VALUES ($1,$2,1999,'USD', now() + interval '31 days',"
                        " 'both','reajuste anual de contrato') RETURNING id::text", org.org_id, v)
        h = org.get("/v1/billing/price-history").json
        self.assertEqual([n["id"] for n in h["notices"]], [nid])
        self.assertIsNone(h["notices"][0]["acknowledged_at"])
        ack = org.post(f"/v1/billing/price-notices/{nid}/ack", {})
        self.assertEqual(ack.status, 200, ack)
        self.assertIsNotNone(org.get("/v1/billing/price-history").json["notices"][0]["acknowledged_at"])
        # e o aviso de outra organização não é dela para confirmar
        other = new_account("osc", compliance="approved")
        self.assertEqual(other.post(f"/v1/billing/price-notices/{nid}/ack", {}).status, 404)

    def test_webhook_replay_does_not_double_count_intro_periods(self):
        """Webhook reprocessado não pode consumir dois meses de promoção."""
        org = new_account("osc", compliance="approved")
        oc = owner_conn()
        v = oc.scalar("SELECT id::text FROM plan_price_versions WHERE plan_key = 'osc_premium'"
                      " AND interval = 'month' AND currency = 'USD' AND effective_until IS NULL")
        oc.run("INSERT INTO subscription_prices(org_id, price_version_id, plan_key, interval, currency,"
               " amount_cents, intro_amount_cents, intro_periods, tax_behavior)"
               " VALUES ($1,$2,'osc_premium','month','USD',1999,199,3,'exclusive')", org.org_id, v)
        for _ in range(5):
            oc.run("UPDATE subscription_prices SET intro_periods_used = least(intro_periods_used + 1,"
                   " intro_periods) WHERE org_id = $1 AND ends_at IS NULL AND intro_periods IS NOT NULL"
                   " AND intro_periods_used < intro_periods", org.org_id)
        used = oc.scalar("SELECT intro_periods_used FROM subscription_prices WHERE org_id = $1"
                         " AND ends_at IS NULL", org.org_id)
        self.assertEqual(used, 3, "o CHECK da tabela limita ao número contratado")


if __name__ == "__main__":
    unittest.main()
