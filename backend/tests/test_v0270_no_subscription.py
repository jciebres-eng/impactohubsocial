"""v0.27.0 — NÃO EXISTE ASSINATURA (ADR-341) e a torre MASTER não inventa saldo.

O que estes testes provam, contra o banco, o roteador, os jobs e a configuração reais:
  1. nenhuma estrutura de assinatura sobrou (tabela, coluna, função, rota, job, chave de configuração);
  2. perder uma concessão nunca apaga dado (invariante `downgrade_never_deletes_data`, apontada por
     `config/plans.json` para este arquivo);
  3. o cadastro não inicia trial e o acesso nasce como concessão (FULL FREE 2026) ou acesso livre;
  4. a torre MASTER separa GMV de receita, diz "DADO FINANCEIRO NÃO CONECTADO" para banco e "NÃO MEDIDO"
     para a razão de captura sem denominador — e exige `finance.read`.
"""
from __future__ import annotations

import json
import unittest

from tests.support import ROOT, Client, db_system, make_admin, make_staff, new_account, server


class NoSubscriptionAnywhereTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_no_subscription_structure_in_the_database(self):
        with db_system() as c:
            tabelas = {r["table_name"] for r in c.query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
            funcoes = {r["proname"] for r in c.query("SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public'")}
            kinds = c.scalar("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'platform_charges_kind_check'")
        for t in ("subscriptions", "subscription_prices", "price_change_notices", "org_trials", "trial_claims", "trial_requests",
                  "plan_prices", "plan_price_versions"):
            self.assertNotIn(t, tabelas, t)
        for f in ("price_current", "price_apply_guard", "price_notice_guard", "price_version_immutable"):
            self.assertNotIn(f, funcoes, f)
        self.assertNotIn("'subscription'", kinds)

    def test_no_subscription_route_job_or_setting(self):
        from impacto import api, jobs
        from impacto.config import Settings
        from impacto.http import ROUTES
        api.load_all()
        caminhos = {r.path for r in ROUTES}
        for p in ("/v1/billing/checkout", "/v1/billing/quote", "/v1/billing/cancel", "/v1/billing/reactivate", "/v1/billing/change-plan",
                  "/v1/billing/portal", "/v1/billing/webhooks/stripe", "/v1/plans/price", "/v1/billing/price-history",
                  "/v1/admin/plans/{plan_key}/price", "/v1/admin/organizations/{org_id}/trial", "/v1/admin/organizations/{org_id}/manual-subscription",
                  "/v1/help/trial-requests", "/v1/admin/hub/trials"):
            self.assertNotIn(p, caminhos, p)
        self.assertNotIn("billing_lifecycle", [n for n, _ in jobs.JOBS])
        for campo in ("billing_provider", "trial_days", "trial_auto_start", "stripe_prices"):
            self.assertNotIn(campo, Settings.__dataclass_fields__, campo)
        cfg = json.loads((ROOT / "config" / "plans.json").read_text(encoding="utf-8"))
        self.assertIn("no_subscription", cfg["invariants"])
        self.assertNotIn("price_versions", cfg)

    def test_the_catalog_publishes_no_recurring_price(self):
        r = Client().get("/v1/plans").json
        self.assertIsNone(r["subscription"])
        for p in r["items"]:
            self.assertFalse({"prices", "price_cents", "interval", "price_quotes"} & set(p), p["plan_key"])

    def test_signup_starts_no_trial_and_access_is_a_grant_or_free(self):
        c = new_account("osc")
        me = c.get("/v1/me").json
        self.assertIsNone(me["subscription"])
        b = c.get("/v1/billing").json
        self.assertIsNone(b["trial"])
        self.assertIn(b["access"]["state"], ("FREE_GRANT", "GRANT_EXPIRING", "FREE_ACCESS"))
        self.assertTrue(all("cobran" not in n["text"].lower() or "nada será cobrado" in n["text"].lower() or "nenhuma cobrança" in n["text"].lower()
                            for n in b["notices"]), b["notices"])

    def test_losing_a_grant_never_deletes_data(self):
        """Invariante `downgrade_never_deletes_data` (config/plans.json aponta para este arquivo)."""
        adm, _ = make_admin()
        c = new_account("osc")
        g = adm.post(f"/v1/admin/organizations/{c.org_id}/grants", {"plan_key": "osc_premium", "days": 30, "source": "license", "reason": "teste"})
        self.assertEqual(g.status, 201, g)
        self.assertEqual(c.post("/v1/saved-searches", {"name": "Cultura", "filters": {"cause": "cultura"}}).status, 201)
        self.assertEqual(adm.post(f"/v1/admin/grants/{g.json['id']}/revoke", {"reason": "fim da licença"}).status, 200)
        self.assertNotIn("alerts.saved_search", c.get("/v1/me").json["entitlements"]["features"])
        self.assertEqual(len(c.get("/v1/saved-searches").json["items"]), 1, "perder a concessão apagou dado")
        self.assertEqual(c.post("/v1/saved-searches", {"name": "Outra", "filters": {"cause": "saude"}}).status, 402)


class MasterTowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.adm, _ = make_admin()

    def test_requires_finance_read(self):
        self.assertEqual(new_account("osc").get("/v1/control-tower/master").status, 403)
        self.assertEqual(make_staff("support").get("/v1/control-tower/master").status, 403)
        self.assertEqual(Client().get("/v1/control-tower/master").status, 401)

    def test_no_invented_balance_and_gmv_is_not_revenue(self):
        r = self.adm.get("/v1/control-tower/master")
        self.assertEqual(r.status, 200, r.body)
        d = r.json
        self.assertEqual(d["bank"]["status"], "DADO FINANCEIRO NÃO CONECTADO")
        self.assertIsNone(d["bank"]["balance_cents"])
        self.assertFalse(d["subscription"]["exists"])
        self.assertIn("NÃO é receita", d["gmv"]["warning"])
        self.assertEqual({"registered", "due", "paid"} - set(d["platform_layer"]), set())
        self.assertIn("economic_events", d["platform_layer"]["registered"]["source"])
        self.assertEqual(d["marketplace"]["revenue_cents"], 0)
        self.assertIsNone(d["marketplace"]["take_rate"]["percent"])
        self.assertEqual(d["usage"]["revenue_cents"], 0)
        self.assertFalse(d["platform_layer"]["rule"]["active"], "a regra comercial não pode estar ativa sem carta verde")
        # Razão de captura: medida só com denominador e numerador; senão, NÃO MEDIDO (nunca zero).
        vc = d["value_capture"]
        if vc["value_capture_ratio"] is None:
            self.assertEqual(vc["value_capture_ratio_status"], "NÃO MEDIDO")
        else:
            self.assertGreater(vc["value_capture_ratio"], 0)
            self.assertEqual(vc["value_capture_ratio_status"], "medido")
        self.assertEqual(d["platform_layer"]["pricing"]["pricing_version"], "2027.02")
        bps = {x["key"]: x["bps"] for x in d["platform_layer"]["pricing"]["rules"]}
        self.assertEqual((bps["funding.platform_service"], bps["funding.proponent_participation"]), (350, 150))

    def test_the_master_tower_is_in_the_staff_menu_with_the_same_permission(self):
        from impacto.api.access_routes import STAFF_MENU
        item = next(m for m in STAFF_MENU if m[0] == "/controladoria/torre")
        self.assertEqual(item[3], "finance.read")
        ctx = self.adm.get("/v1/me/context").json
        self.assertIn("/controladoria/torre", [i["to"] for g in ctx["menu"] for i in g["items"]])


if __name__ == "__main__":
    unittest.main()


class TodayCardsTests(unittest.TestCase):
    """'Para você hoje' (v0.27.0): cartões e contadores derivados de registros reais; nenhum vende plano."""

    @classmethod
    def setUpClass(cls):
        server()

    def test_cards_and_badges_come_from_records_and_sell_nothing(self):
        c = new_account("osc")
        r = c.get("/v1/me/today")
        self.assertEqual(r.status, 200, r.body)
        d = r.json
        self.assertTrue(any(x["kind"] == "onboarding" for x in d["cards"]), d["cards"])
        for card in d["cards"]:
            self.assertTrue(card.get("link"), card)
            self.assertNotIn(card["kind"], ("plan", "subscription", "upgrade", "trial"))
            self.assertNotRegex((card["title"] + " " + (card.get("why") or "")).lower(), r"assinatura|assine|upgrade|plano pago")
        self.assertEqual(d["trajectory"]["total"], 0)
        self.assertNotIn("/notificacoes", d["badges"])
        with db_system() as db:
            db.scalar("SELECT app_notify($1, $2, 'test.card', 'Aviso de teste', 'Corpo.', '/notificacoes')", c.org_id, c.user["id"])
        self.assertEqual(c.get("/v1/me/today").json["badges"].get("/notificacoes"), 1)
        self.assertEqual(Client().get("/v1/me/today").status, 401)

    def test_a_proposed_participation_becomes_a_card_and_a_badge_for_the_proponent(self):
        """Executora propõe participação a quem publicou a ideia; a proponente vê o cartão e o contador em /participacoes."""
        from tests.test_v0270_economy import OSC_IDEA
        executora = new_account("osc", compliance="approved")
        proponente = new_account("individual", compliance="approved")
        sid = proponente.post("/v1/solutions", OSC_IDEA)
        self.assertEqual(sid.status, 201, sid.body)
        self.assertEqual(proponente.post(f"/v1/solutions/{sid.json['id']}/publish").status, 200)
        pr = executora.post("/v1/projects", {"title": "Projeto hoje", "summary": "Projeto para o cartão de participação.", "causes": ["educacao"],
                                             "territory": "BR-MT", "ods": [4], "beneficiaries_count": 10, "budget_total_cents": 1_000_000})
        self.assertEqual(pr.status, 201, pr.body)
        r = executora.post(f"/v1/projects/{pr.json['id']}/participations", {"proponent_org_id": proponente.org_id, "idea_ref_type": "solution", "idea_ref_id": sid.json["id"],
                                                                          "authorship_type": "author", "share_bps": 10000, "contribution": "Concebeu e desenvolveu a ideia que originou o projeto."})
        self.assertEqual(r.status, 201, r.body)
        d = proponente.get("/v1/me/today").json
        self.assertEqual(d["badges"].get("/participacoes"), 1)
        self.assertTrue(any(x["kind"] == "participation" and x["link"] == "/participacoes" for x in d["cards"]))
