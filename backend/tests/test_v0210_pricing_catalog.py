"""O catálogo é de PACOTES DE CAPACIDADES, nenhum valor mora no código, e o pagamento nunca compra posição.

HISTÓRICO. Na v0.21.0 este arquivo conferia a tabela de mensalidades (Pricing Version 2027.01) contra a
PRICING_BIBLE.md. Na v0.27.0 o proprietário RETIROU a assinatura do modelo econômico (ADR-341): não há
mensalidade a conferir, e os testes que a conferiam foram removidos — não afrouxados. O que fica:
(1) nenhum valor de preço escrito em código; (2) o que o pagamento nunca compra; (3) as regras
transacionais continuam desligadas e recusadas pelo banco; (4) a regra de assinatura está RECUSADA no
catálogo com carta vermelha; (5) os documentos de reconciliação existem e apontam para testes reais.
"""
from __future__ import annotations

import json
import pathlib
import re
import unittest

from tests.support import ROOT, db_system

CONFIG = json.loads((ROOT / "config" / "plans.json").read_text(encoding="utf-8"))

# Pisos de proposta de CONTRATO publicados (não mensalidade): ENTERPRISE e GOV, em centavos.
PISO_CONTRATO = {
    "company_enterprise": 250000,
    "gov_institutional": 350000,
}


def scalar(sql, *a):
    with db_system() as c:
        return c.scalar(sql, *a)


class CatalogIsCapabilityBundlesTests(unittest.TestCase):

    def test_no_plan_declares_a_price_or_an_interval(self):
        for plano, p in CONFIG["plans"].items():
            for chave in ("price_cents", "interval", "prices"):
                self.assertNotIn(chave, p, f"{plano} voltou a declarar {chave}: não existe assinatura (ADR-341)")

    def test_the_config_has_no_price_versions_nor_trial(self):
        for chave in ("price_versions", "trial"):
            self.assertNotIn(chave, CONFIG, f"`{chave}` voltou ao config/plans.json")

    def test_proposal_plans_keep_a_published_contract_floor(self):
        for plano, piso in PISO_CONTRATO.items():
            self.assertEqual(CONFIG["plans"][plano].get("quote_floor_cents"), piso)
            self.assertEqual(CONFIG["plans"][plano].get("obtained_by"), "contract_or_grant")

    def test_free_plans_are_the_core_and_say_so(self):
        for plano, p in CONFIG["plans"].items():
            if p.get("tier") == "free":
                self.assertEqual(p.get("obtained_by"), "core", plano)

    def test_the_pricing_version_is_declared_once_and_superseded_2027_01(self):
        self.assertEqual(CONFIG["pricing_version"], "2027.02")
        from impacto.services import free_period as FP
        from impacto.services.monetization import pricing_version_name
        self.assertEqual(FP.pricing_version(), "2027.02")
        self.assertEqual(pricing_version_name(), "2027.02")

    def test_the_database_has_no_subscription_structures(self):
        with db_system() as c:
            tabelas = {r["table_name"] for r in c.query(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
            colunas = {(r["table_name"], r["column_name"]) for r in c.query(
                "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'")}
            funcoes = {r["proname"] for r in c.query(
                "SELECT p.proname FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public'")}
        for t in ("subscriptions", "subscription_prices", "price_change_notices", "org_trials", "trial_claims",
                  "trial_requests", "plan_prices", "plan_price_versions"):
            self.assertNotIn(t, tabelas, f"tabela de assinatura ainda existe: {t}")
        for col in (("plans", "price_cents"), ("plans", "interval"), ("invoices", "subscription_id"),
                    ("platform_charges", "subscription_id"), ("free_periods", "subscription_id"),
                    ("commercial_offers", "price_version_id"), ("commercial_offers", "interval"),
                    ("offer_acceptances", "price_version_id"), ("voucher_redemptions", "consumed_by_subscription")):
            self.assertNotIn(col, colunas, f"coluna de assinatura ainda existe: {col}")
        for fn in ("price_current", "price_apply_guard", "price_notice_guard"):
            self.assertNotIn(fn, funcoes, f"função de assinatura ainda existe: {fn}")

    def test_the_subscription_rule_is_refused_with_a_red_card(self):
        with db_system() as c:
            r = c.one("SELECT r.legal_status, r.active, r.trigger_kind, r.pricing_mode, k.status AS card"
                      " FROM monetization_rules r LEFT JOIN monetization_legal_cards k ON k.id = r.legal_card_id"
                      " WHERE r.key = 'saas.institutional.funder'")
        self.assertEqual((r["legal_status"], r["active"], r["card"]), ("refused", False, "red"))
        self.assertNotEqual(r["trigger_kind"], "subscription")
        self.assertNotEqual(r["pricing_mode"], "subscription")


class PriceLivesInOnePlaceTests(unittest.TestCase):

    def test_no_price_figure_is_written_in_product_code(self):
        """Nenhum dos valores da antiga tabela, nem os pisos de contrato, aparece como literal em código."""
        numeros = {"29900", "79900", "149000", "250000", "350000", "4900", "299000", "799000"}
        alvos: list[tuple[str, str]] = []
        for raiz, padroes in ((ROOT / "backend" / "impacto", ("*.py",)),
                              (ROOT / "web" / "src", ("*.tsx", "*.ts"))):
            for padrao in padroes:
                for f in raiz.rglob(padrao):
                    for n, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                        for tok in re.findall(r"\b\d{3,7}\b", linha):
                            if tok in numeros:
                                alvos.append((f"{f.relative_to(ROOT)}:{n}", linha.strip()[:90]))
        self.assertEqual(alvos, [],
                         "preço escrito no código — o catálogo deixou de ser a fonte única:\n"
                         + "\n".join(f"  {o} · {t}" for o, t in alvos))

    def test_the_economic_percentages_are_not_written_in_code(self):
        """3,5% e 1,5% vivem em `economic_rules` (0066) e são congelados no acordo — nunca em código."""
        achados = []
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            txt = f.read_text(encoding="utf-8")
            for n, linha in enumerate(txt.splitlines(), 1):
                if re.search(r"(take_rate|success_fee|transaction_fee|platform_fee_bps|participation_bps)\s*[=:]\s*0?\.?\d", linha):
                    achados.append(f"{f.relative_to(ROOT)}:{n}")
        self.assertEqual(achados, [], "percentual econômico escrito em código: " + ", ".join(achados))

    def test_the_benchmark_never_feeds_the_platform_price(self):
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            txt = f.read_text(encoding="utf-8")
            if "price_benchmark" in txt:
                self.assertNotIn("economic_rules", txt, f"{f.name} lê o benchmark e escreve no catálogo econômico")


class PaymentNeverBuysTheseTests(unittest.TestCase):
    """O que o pagamento NUNCA compra. Declarado em `never_sellable` e travado aqui."""

    PROIBIDOS = ("provider_rank", "provider_featured", "provider_badge", "match_boost",
                 "eligibility_override")

    def test_the_never_sellable_list_is_declared(self):
        self.assertEqual(sorted(CONFIG["never_sellable"]), sorted(self.PROIBIDOS))

    def test_no_plan_sells_anything_from_the_list(self):
        for plano, p in CONFIG["plans"].items():
            vendidos = set(p.get("features", [])) & set(self.PROIBIDOS)
            self.assertEqual(vendidos, set(), f"{plano} vende {vendidos}")

    def test_no_code_path_turns_a_plan_into_a_score(self):
        """Nenhum cálculo de reputação, impacto ou match lê concessão, contrato ou cobrança."""
        comerciais = ("entitlement_grants", "platform_charges", "invoices", "economic_events",
                      "offer_acceptances", "commercial_offers", "free_periods", "allocation_payouts")
        pontuacao = []
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            rel = str(f.relative_to(ROOT / "backend" / "impacto"))
            if not any(x in rel for x in ("reputation", "impact", "match", "seal", "claim",
                                          "equity", "eligib")):
                continue
            txt = f.read_text(encoding="utf-8")
            for tabela in comerciais:
                if re.search(rf"\b(FROM|JOIN)\s+{tabela}\b", txt):
                    pontuacao.append(f"{rel} consulta {tabela}")
        self.assertEqual(pontuacao, [],
                         "um módulo de reputação/impacto/match passou a ler estado comercial:\n  "
                         + "\n  ".join(pontuacao))

    def test_entitlements_never_grant_a_never_sellable_feature(self):
        from impacto.services import entitlements as E
        declaradas = set()
        for p in CONFIG["plans"].values():
            declaradas |= set(p.get("features", []))
        self.assertEqual(declaradas & set(self.PROIBIDOS), set())
        fonte = (ROOT / "backend" / "impacto" / "services" / "entitlements.py").read_text(encoding="utf-8")
        self.assertIn("platform", fonte.lower())
        self.assertNotIn("subscriptions", fonte)
        self.assertNotIn("org_trials", fonte)
        self.assertIs(E.has_access, E.has_access)   # o módulo carrega


class TransactionalRulesStayOffTests(unittest.TestCase):
    """Take rate, success fee e transaction fee: declarados, desligados, e por quê."""

    def test_no_monetization_rule_is_active(self):
        ativas = [r["key"] for r in _regras() if r["active"]]
        self.assertEqual(ativas, [], f"regra ativada sem carta verde: {ativas}")

    def test_the_blocked_rules_are_refused_by_the_database_not_merely_unset(self):
        for chave in ("marketplace.take_rate", "success_fee.funding"):
            with self.assertRaises(Exception) as e:
                with db_system() as c:
                    c.run("UPDATE monetization_rules SET active = true WHERE key = $1", chave)
            self.assertIn("ADR-022", str(e.exception),
                          f"{chave} pôde ser ativada: a recusa é arquitetural, não configuração")

    def test_the_reconciliation_document_explains_the_conflict_with_the_bible(self):
        doc = (ROOT / "PRICING_RECONCILIATION.md").read_text(encoding="utf-8")
        self.assertIn("ADR-178", doc)
        self.assertIn("12.865", doc, "falta a base legal da recusa (Lei 12.865/2013)")
        bib = (ROOT / "PRICING_BIBLE.md").read_text(encoding="utf-8")
        for termo in ("service", "contract", "transaction"):
            self.assertIn(termo, bib,
                          f"a Bíblia perdeu a condição '{termo}' que ela mesma impõe ao take rate")
        self.assertIn("não custodia", bib)


def _regras():
    with db_system() as c:
        return [dict(r) for r in c.query("SELECT key, active FROM monetization_rules")]


class BibleAndReconciliationExistTests(unittest.TestCase):

    def test_the_bible_is_in_the_repository_and_says_subscription_is_over(self):
        p = ROOT / "PRICING_BIBLE.md"
        self.assertTrue(p.exists(), "PRICING_BIBLE.md não está no repositório")
        txt = p.read_text(encoding="utf-8")
        self.assertIn("ADR-341", txt, "a Bíblia não registra a retirada da assinatura")
        self.assertIn("2027.02", txt)
        for secao in ("FULL FREE 2026", "ACESSO GRATUITO", "AUTORIZAÇÃO DE COBRANÇA",
                      "O QUE AINDA NÃO ESTÁ DECIDIDO"):
            self.assertIn(secao, txt, f"a Bíblia não tem a seção {secao}")

    def test_the_reconciliation_matrix_has_the_required_columns(self):
        txt = (ROOT / "PRICING_RECONCILIATION.md").read_text(encoding="utf-8")
        for coluna in ("REGRA COMERCIAL", "LOCALIZAÇÃO NO CÓDIGO", "STATUS", "GAP",
                       "IMPLEMENTAÇÃO NECESSÁRIA", "TESTE"):
            self.assertIn(coluna, txt, f"a matriz não tem a coluna {coluna}")
        self.assertIn("O QUE NÃO SERÁ FEITO NESTA RODADA", txt)

    def test_every_matrix_row_names_a_test_file_that_exists(self):
        txt = (ROOT / "PRICING_RECONCILIATION.md").read_text(encoding="utf-8")
        citados = set(re.findall(r"`?(test_v0\d{3}_[a-z_]+)`?", txt))
        faltando = [t for t in citados
                    if not (pathlib.Path(__file__).parent / f"{t}.py").exists()]
        self.assertEqual(faltando, [],
                         "a matriz promete testes que não existem: " + ", ".join(sorted(faltando)))
