"""v0.27.0 — a simulação de 24 meses é DERIVADA de hipóteses declaradas, confere com o catálogo e diz que não prevê.

Três coisas são provadas:
  1. o documento no repositório é exatamente o que o gerador produz (um número editado à mão reprova);
  2. os percentuais do arquivo de hipóteses são os do catálogo `economic_rules` da versão vigente — o banco manda;
  3. a aritmética fecha: 3.500 + 1.500 = 5.000 por 100.000, o GMV necessário para R$ 1 milhão a 3,5% é
     R$ 28.571.428,57, e nenhum cenário fatura assinatura (não existe).
"""
from __future__ import annotations

import importlib.util
import json
import unittest

from tests.support import ROOT, db_system

CFG = json.loads((ROOT / "config" / "economic_model.json").read_text(encoding="utf-8"))


def _gen():
    spec = importlib.util.spec_from_file_location("make_24_month_model", ROOT / "scripts" / "make_24_month_model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class FinancialModelTests(unittest.TestCase):

    def test_the_document_is_exactly_what_the_generator_produces(self):
        mod = _gen()
        antes = (ROOT / "24_MONTH_FINANCIAL_MODEL.md").read_text(encoding="utf-8")
        mod.main()
        depois = (ROOT / "24_MONTH_FINANCIAL_MODEL.md").read_text(encoding="utf-8")
        self.assertEqual(antes, depois, "24_MONTH_FINANCIAL_MODEL.md divergiu do gerador: rode scripts/make_24_month_model.py")

    def test_the_percentages_mirror_the_catalog_in_force(self):
        from impacto.services.monetization import pricing_version_name
        self.assertEqual(CFG["pricing_version"], pricing_version_name())
        with db_system() as c:
            bps = {r["key"]: r["bps"] for r in c.query("SELECT key, bps FROM economic_rules WHERE pricing_version = $1", CFG["pricing_version"])}
        self.assertEqual(bps["funding.platform_service"], CFG["platform_service_bps"])
        self.assertEqual(bps["funding.proponent_participation"], CFG["proponent_participation_bps"])

    def test_the_arithmetic_closes(self):
        self.assertEqual(CFG["platform_service_bps"] + CFG["proponent_participation_bps"], 500)
        self.assertEqual(100_000_00 * CFG["platform_service_bps"] // 10_000, 3_500_00)
        self.assertEqual(100_000_00 * CFG["proponent_participation_bps"] // 10_000, 1_500_00)
        gmv_1m = 100_000_000 * 10_000 / CFG["platform_service_bps"]
        self.assertAlmostEqual(gmv_1m, 2_857_142_857.14, places=1)
        mod = _gen()
        for sc in CFG["scenarios"].values():
            rows = mod.simulate(CFG, sc)
            self.assertEqual(len(rows), CFG["horizon_months"])
            self.assertEqual(rows[-1]["clients"], CFG["new_funding_clients_per_month"] * CFG["horizon_months"])
            for r in rows:
                self.assertEqual(r["platform_registered_cents"], round(r["gmv_cents"] * CFG["platform_service_bps"] / 10_000))
                self.assertLessEqual(r["platform_paid_cents"], max(x["platform_registered_cents"] for x in rows))
            # a camada paga nunca supera a registrada acumulada — não se quita o que não foi ativado
            self.assertLessEqual(sum(r["platform_paid_cents"] for r in rows), sum(r["platform_registered_cents"] for r in rows))

    def test_the_document_says_it_is_hypothesis_and_has_no_subscription(self):
        txt = (ROOT / "24_MONTH_FINANCIAL_MODEL.md").read_text(encoding="utf-8")
        for frase in ("RECEITA REAL DESTA INSTALAÇÃO: R$ 0,00", "HIPÓTESES DECLARADAS", "Não existe assinatura", "[PREMISSA]",
                      "GMV ≠ receita", "R$ 28.571.428,57"):
            self.assertIn(frase, txt, frase)
        self.assertNotIn("MRR(m)", txt)
        self.assertNotIn("preco_do_plano", txt)
