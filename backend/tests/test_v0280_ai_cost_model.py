"""v0.28.0 — o modelo de custo da IA é DERIVADO de hipóteses declaradas e confere com o catálogo no banco.

  1. `AI_COST_MODEL.md` é exatamente o que o gerador produz (número editado à mão reprova);
  2. os créditos por operação e as cotas do arquivo de hipóteses são os do catálogo `ai_operations` / `ai_quota_policies`
     — o banco manda, a simulação segue;
  3. a aritmética fecha e o documento separa MEDIDO de [PREMISSA], diz que a receita real é zero e nomeia as operações
     deficitárias com provedor externo em vez de afirmar que não existem;
  4. a medição do piloto existe, é do motor local e declara o que NÃO mede.
"""
from __future__ import annotations

import importlib.util
import json
import unittest

from tests.support import ROOT, db_system

CFG = json.loads((ROOT / "config" / "ai_economics.json").read_text(encoding="utf-8"))


def _gen(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class AiCostModelTests(unittest.TestCase):

    def test_the_document_is_exactly_what_the_generator_produces(self):
        dest = ROOT / "AI_COST_MODEL.md"
        antes = dest.read_text(encoding="utf-8")
        _gen("make_ai_cost_model").main()
        self.assertEqual(antes, dest.read_text(encoding="utf-8"), "AI_COST_MODEL.md divergiu do gerador: rode scripts/make_ai_cost_model.py")

    def test_credits_and_quotas_in_the_hypotheses_match_the_catalog_in_the_database(self):
        with db_system() as c:
            ops = {r["code"]: r for r in c.query("SELECT code, credits_base, credits_per_unit FROM ai_operations WHERE status IN ('active','hypothesis')")}
            welcome = c.scalar("SELECT credits FROM ai_quota_policies WHERE key = 'welcome.v1'")
            monthly = c.scalar("SELECT credits FROM ai_quota_policies WHERE key = 'monthly.light.v1'")
            packs = {r["code"]: r["price_cents"] for r in c.query("SELECT code, price_cents FROM ai_credit_packs WHERE status IN ('active','hypothesis')")}
        for code, op in CFG["operations"].items():
            self.assertIn(code, ops, f"{code} não está no catálogo vigente")
            esperado = ops[code]["credits_base"] + (ops[code]["credits_per_unit"] * 3 if code == "similarity.set" else 0)   # conjunto modelado com 3 projetos
            self.assertEqual(op["credits"], esperado, code)
        self.assertEqual((CFG["welcome_quota_credits"], CFG["monthly_light_quota_credits"]), (welcome, monthly))
        self.assertEqual(CFG["pack_prices_cents"], packs)
        self.assertFalse(CFG["external_provider_configured"], "o arquivo diz que não há provedor externo — e não há")

    def test_arithmetic_and_honesty_markers(self):
        mod = _gen("make_ai_cost_model")
        ue = mod.unit_economics(CFG, external=True)
        for r in ue:
            self.assertEqual(r["price_cents"], r["credits"] * CFG["credit_price_cents_hypothesis"])
            self.assertAlmostEqual(r["margin"], r["price_cents"] - r["cost"]["total"] - r["pix_fee"] - r["tax"], places=6)
        local = {r["code"]: r for r in mod.unit_economics(CFG, external=False)}
        self.assertTrue(all(r["margin"] > 0 for r in local.values()), "no motor local toda operação cobre o custo variável")
        txt = (ROOT / "AI_COST_MODEL.md").read_text(encoding="utf-8")
        for frase in ("[PREMISSA]", "MEDIDO", "Receita real de IA desta instalação: R$ 0,00", "tabela de preço do provedor está vazia", "## 7. As doze perguntas"):
            self.assertIn(frase, txt, frase)
        deficit = [r["code"] for r in ue if r["margin"] < 0]
        if deficit:
            self.assertIn("DEFICITÁRIAS", txt)
            for code in deficit:
                self.assertIn(f"`{code}`", txt.split("DEFICITÁRIAS", 1)[1][:600])
        for sc in CFG["scenarios"].values():
            rows = mod.simulate(CFG, sc)
            self.assertEqual(len(rows), CFG["horizon_months"])
            for r in rows:
                self.assertAlmostEqual(r["ops"], r["free_ops"] + r["paid_ops"] + r["sponsored_ops"] + (r["ops"] - r["free_ops"] - r["paid_ops"] - r["sponsored_ops"]), places=6)
                self.assertGreaterEqual(r["free_cost"], 0)
                self.assertLessEqual(r["free_cost"], r["cost"] + 1e-9)

    def test_the_pilot_measurement_is_local_and_says_what_it_does_not_measure(self):
        ev = json.loads((ROOT / "docs" / "evidence" / "ai_pilot_v0280.json").read_text(encoding="utf-8"))
        self.assertEqual(ev["engine_version"], "similarity@1.0")
        self.assertGreater(ev["originality_200_ms"]["p50"], 0)
        self.assertLess(ev["originality_200_ms"]["max"], 5000, "200 candidatos em menos de 5 s na máquina do piloto")
        self.assertTrue(any("provedor externo" in x for x in ev["what_is_not_measured"]))
