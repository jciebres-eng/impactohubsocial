"""v0.17.0 — motor de monetização e a nova regra comercial.

O que estes testes protegem é a cadeia `valor → elegibilidade → monetização → VALIDAÇÃO JURÍDICA →
cobrança`, e sobretudo as recusas dela. Um produto que consegue ativar cobrança sem base jurídica
registrada é um produto que vai cobrar sem base jurídica.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import app_tx, db_system, make_admin, new_account, owner_conn


class MonBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.admin, _ = make_admin()

    def project(self, **extra) -> str:
        r = self.osc.post("/v1/projects", {
            "title": f"Projeto monetização {uuid.uuid4().hex[:6]}",
            "summary": "Resumo suficiente para que o projeto seja avaliado por terceiros nesta rodada.",
            "problem": "Problema descrito com evidência local e fonte declarada no diagnóstico.",
            "objectives": "Objetivo geral e específicos declarados para o período de execução previsto.",
            "methodology": "Oficinas semanais com registro de presença e avaliação ao final de cada módulo.",
            "territory": "BR-MT", "budget_total_cents": 30_000_000, "causes": ["educacao"], "ods": [4],
            "beneficiaries_count": 200, "beneficiaries_description": "Jovens de 14 a 18 anos", **extra})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def green_card(self, rule_key: str) -> str:
        """Carta legal verde completa — só possível com base, fonte, data e dispensa de advogado."""
        r = self.admin.post("/v1/admin/monetization/legal-cards", {
            "rule_key": rule_key, "payer": "Organização contratante",
            "beneficiary": "Plataforma Impacto",
            "billing_event": "análise avançada de prontidão concluída",
            "revenue_nature": "prestação de serviço de software",
            "contractual_relation": "contrato de adesão aos Termos de Uso, com aceite versionado",
            "legal_basis": "Base de teste registrada exclusivamente para exercitar o portão de ativação.",
            "source_name": "Registro interno de teste", "source_url": "https://exemplo.test/base",
            "verified_on": "2026-10-01", "certainty": "high", "needs_lawyer": False,
            "needs_accountant": False, "status": "green"})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]


# ================================================================================================ regra nova
class CommercialRuleTests(MonBase):
    def test_the_shipped_product_declares_no_price_at_all(self):
        """A regra em dólar da v0.16.0 foi aposentada e nenhum preço institucional foi fixado.

        A verificação é sobre o que o PRODUTO declara (`config/plans.json`), não sobre o banco de
        teste: o ambiente de teste declara preços próprios para poder exercitar a camada de cobrança,
        e confundir os dois tornaria este teste dependente da ordem de execução.
        """
        import json
        import pathlib
        cfg = json.loads((pathlib.Path(__file__).resolve().parents[2] / "config" / "plans.json")
                         .read_text(encoding="utf-8"))
        items = cfg["price_versions"]["items"]
        self.assertTrue(items, "o bloco de preços não pode desaparecer: a aposentadoria vive nele")
        for it in items:
            self.assertTrue(it.get("retire"),
                            f"{it} declara preço; a v0.17.0 não fixa preço institucional")
        for key, plan in cfg["plans"].items():
            self.assertIn(plan.get("price_cents"), (None, 0),
                          f"{key} tem preço fixado em config/plans.json")

    def test_a_plan_without_a_declared_price_refuses_contracting(self):
        """E sem preço declarado a plataforma recusa — em vez de inventar um valor."""
        # `company_plus` não é declarado pelo ambiente de teste, de propósito.
        r = self.osc.get("/v1/plans/price?plan_key=company_plus&interval=month")
        self.assertEqual(r.status, 404, r)
        self.assertEqual(r.json["code"], "price_not_defined")

    def test_the_retired_usd_rule_stays_in_history_with_its_period_closed(self):
        """Aposentar não é apagar: o preço de ontem explica o contrato de ontem."""
        # Precisa do papel DONO: `plan_price_versions` não tem escrita para o papel da aplicação, o que
        # é parte da trava — preço não é coisa que a aplicação escreva.
        c = owner_conn()
        try:
            c.run("INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents,"
                  " trial_days, tax_behavior, provider, reason) VALUES ('osc_premium','month','USD',"
                  " 1999, 14, 'exclusive', 'stripe', 'regra da v0.16.0, para o teste de aposentadoria')")
            from impacto.db.migrate import sync_reference_data
            sync_reference_data(c, log=lambda *a: None)
            rows = c.query("SELECT amount_cents, effective_until IS NULL AS current"
                           " FROM plan_price_versions WHERE currency = 'USD'")
        finally:
            c.close()
        self.assertTrue(rows, "a versão em dólar tem de continuar no histórico")
        self.assertTrue(all(not r["current"] for r in rows),
                        "nenhuma versão em dólar pode continuar vigente")

    def test_free_entry_covers_what_the_documents_require(self):
        """Cadastro, perfil, projeto, descoberta e rede sem pagar — e não por tempo limitado."""
        fresh = new_account("osc", compliance="approved")   # sem premium, sem voucher
        self.assertEqual(fresh.post("/v1/projects", {
            "title": "Projeto na conta gratuita", "summary": "Resumo suficiente para avaliação externa.",
            "problem": "Problema descrito com evidência local e fonte declarada.",
            "objectives": "Objetivo geral e específicos declarados para o período previsto.",
            "methodology": "Oficinas semanais com registro de presença.",
            "territory": "BR-MT", "budget_total_cents": 1_000_000, "causes": ["educacao"], "ods": [4],
            "beneficiaries_count": 10, "beneficiaries_description": "Jovens"}).status, 201,
            "criar projeto tem de ser gratuito")
        self.assertEqual(fresh.get("/v1/marketplace/feed").status, 200, "descoberta tem de ser gratuita")
        self.assertEqual(fresh.get("/v1/network/relationships").status, 200, "a rede tem de ser gratuita")
        self.assertEqual(fresh.get("/v1/readiness").status, 200, "prontidão básica tem de ser gratuita")
        with db_system() as c:
            lim = c.scalar("SELECT (limits->>'active_projects')::int FROM plans WHERE plan_key = 'osc_basic'")
        self.assertGreaterEqual(lim, 10, "o limite gratuito não pode estrangular o lado da oferta")


# ================================================================================================ o portão
class LegalGateTests(MonBase):
    def test_no_rule_ships_active(self):
        r = self.osc.get("/v1/monetization/rules")
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["items"])
        for rule in r.json["items"]:
            self.assertFalse(rule["active"], f"{rule['key']} não pode vir ativa")
            self.assertEqual(rule["legal_status"], "review_required", rule["key"])

    def test_activation_without_a_green_legal_card_is_refused(self):
        r = self.admin.patch("/v1/admin/monetization/rules/premium.readiness_analysis",
                             {"active": True})
        self.assertIn(r.status, (403, 422), r)
        self.assertIn("carta legal", str(r.json).lower())

    def test_success_fee_and_take_rate_cannot_be_activated_at_all(self):
        """A ADR-022 é barreira estrutural: a plataforma não custodia nem processa aporte."""
        for key in ("success_fee.funding", "marketplace.take_rate"):
            card = self.green_card(key)
            r = self.admin.patch(f"/v1/admin/monetization/rules/{key}",
                                 {"legal_status": "validated", "legal_card_id": card, "active": True})
            self.assertIn(r.status, (403, 422), f"{key} não pode ser ativada: {r.json}")
            self.assertIn("adr-022", str(r.json).lower(), key)

    def test_activation_without_a_price_is_refused(self):
        card = self.green_card("premium.readiness_analysis")
        r = self.admin.patch("/v1/admin/monetization/rules/premium.readiness_analysis",
                             {"legal_status": "validated", "legal_card_id": card, "active": True})
        self.assertIn(r.status, (403, 422), r)
        self.assertIn("preço", str(r.json).lower())

    def test_a_green_card_cannot_be_issued_without_basis_source_and_date(self):
        r = self.admin.post("/v1/admin/monetization/legal-cards", {
            "rule_key": "premium.readiness_analysis", "payer": "OSC", "beneficiary": "Plataforma",
            "billing_event": "análise concluída", "revenue_nature": "prestação de serviço",
            "contractual_relation": "contrato de adesão", "certainty": "high", "status": "green"})
        self.assertIn(r.status, (422, 409), r)

    def test_a_green_card_cannot_have_open_questions(self):
        r = self.admin.post("/v1/admin/monetization/legal-cards", {
            "rule_key": "premium.readiness_analysis", "payer": "OSC", "beneficiary": "Plataforma",
            "billing_event": "análise concluída", "revenue_nature": "prestação de serviço",
            "contractual_relation": "contrato de adesão",
            "legal_basis": "Base qualquer", "source_name": "Fonte qualquer",
            "verified_on": "2026-10-01", "certainty": "high", "needs_lawyer": False,
            "needs_accountant": False, "status": "green",
            "open_questions": "Falta confirmar o tratamento tributário com o contador."})
        self.assertIn(r.status, (422, 409), r)

    def test_the_legal_card_is_append_only(self):
        card = self.green_card("premium.document_preparation")
        with db_system() as c, self.assertRaises(Exception):
            c.run("UPDATE monetization_legal_cards SET status = 'red' WHERE id = $1", card)

    def test_every_rule_declares_the_problem_and_answers_the_substitution_test(self):
        """"Não venda 20 funcionalidades por R$99; venda um problema caro resolvido"."""
        for rule in self.osc.get("/v1/monetization/rules").json["items"]:
            self.assertGreaterEqual(len(rule["problem_solved"]), 20, rule["key"])
            self.assertGreaterEqual(len(rule["substitution_answer"]), 20, rule["key"])


# ================================================================================================ a fila
class PipelineTests(MonBase):
    def test_a_value_event_produces_a_candidate_and_never_a_charge(self):
        pid = self.project()
        self.osc.post("/v1/readiness/snapshots", {"project_id": pid})
        r = self.osc.get("/v1/monetization/pipeline")
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["items"], "a prontidão avaliada tem de produzir candidato")
        for item in r.json["items"]:
            self.assertIn(item["status"], ("candidate", "blocked_legal", "blocked_no_price", "waived"))
            self.assertIsNone(item["amount_cents"], "nada pode ter valor a cobrar nesta versão")
            self.assertGreaterEqual(len(item["reason"]), 5, "o motivo do estado é obrigatório")

    def test_the_reason_says_why_nothing_is_charged(self):
        pid = self.project()
        self.osc.post("/v1/readiness/snapshots", {"project_id": pid})
        item = self.osc.get("/v1/monetization/pipeline").json["items"][0]
        self.assertEqual(item["status"], "blocked_legal")
        self.assertIn("carta legal", item["reason"].lower())

    def test_the_pipeline_is_isolated_between_organizations(self):
        other = new_account("osc", compliance="approved")
        pid = self.project()
        self.osc.post("/v1/readiness/snapshots", {"project_id": pid})
        mine = {i["id"] for i in self.osc.get("/v1/monetization/pipeline").json["items"]}
        theirs = {i["id"] for i in other.get("/v1/monetization/pipeline").json["items"]}
        self.assertTrue(mine)
        self.assertFalse(mine & theirs)

    def test_the_application_cannot_insert_a_billable_event_directly(self):
        with app_tx(self.osc) as c, self.assertRaises(Exception):
            c.run("INSERT INTO billable_events(value_event_id, rule_key, org_id, status, reason,"
                  " amount_cents) VALUES (1,'premium.readiness_analysis',$1,'eligible','forjado',99999)",
                  self.osc.org_id)

    def test_waiving_requires_a_written_reason(self):
        pid = self.project()
        self.osc.post("/v1/readiness/snapshots", {"project_id": pid})
        bid = self.osc.get("/v1/monetization/pipeline").json["items"][0]["id"]
        short = self.admin.post(f"/v1/admin/monetization/pipeline/{bid}/waive", {"reason": "nao"})
        self.assertEqual(short.status, 422, short)
        ok = self.admin.post(f"/v1/admin/monetization/pipeline/{bid}/waive",
                             {"reason": "Cortesia concedida durante o piloto controlado."})
        self.assertEqual(ok.status, 200, ok)
        self.assertEqual(ok.json["status"], "waived")


# ================================================================================================ hierarquia
class HierarchyTests(MonBase):
    def test_the_proponent_premium_is_never_the_core(self):
        items = {r["key"]: r for r in self.osc.get("/v1/monetization/rules").json["items"]}
        core = [r for r in items.values() if r["engine_rank"] <= 3]
        self.assertTrue(core)
        for r in core:
            self.assertIn(r["revenue_engine"], ("saas_institutional", "b2g", "enterprise"))
            self.assertNotEqual(r["payer_kind"], "osc",
                                "o núcleo da receita não pode ter a OSC como pagadora")
        for r in items.values():
            if r["revenue_engine"] == "proponent_premium":
                self.assertGreaterEqual(r["engine_rank"], 7,
                                        "premium do proponente é aquisição, não núcleo")

    def test_institutional_prices_are_declared_as_hypothesis_not_as_price(self):
        for r in self.osc.get("/v1/monetization/rules").json["items"]:
            if r["engine_rank"] <= 3:
                self.assertIsNone(r["amount_cents"], f"{r['key']} não pode ter preço fixado")
                self.assertIsNotNone(r["hypothesis_note"], r["key"])
                self.assertIn("hipótese", r["hypothesis_note"].lower(), r["key"])


if __name__ == "__main__":
    unittest.main()
