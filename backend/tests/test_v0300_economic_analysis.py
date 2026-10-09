"""Invariantes do motor de análise econômica de 120 meses (scripts/analysis/economic_model_120m.py).

A análise é PROPOSTA, não produto: estes testes só garantem que o modelo respeita as regras econômicas
vigentes (GMV ≠ receita, autoria ≠ receita, taxa só após ativação e quitação, modelo ATUAL sem contratos
institucionais) e que o JSON publicado foi gerado pelo motor com os parâmetros do repositório.
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENGINE = ROOT / "scripts" / "analysis" / "economic_model_120m.py"
OUT = ROOT / "docs" / "analysis" / "economia_v0300"


def _load():
    spec = importlib.util.spec_from_file_location("economic_model_120m", ENGINE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class EconomicModelInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = _load()
        cls.econ = json.loads((ROOT / "config" / "economic_model.json").read_text(encoding="utf-8"))

    def test_facts_match_repository_config(self):
        self.assertEqual(self.m.FACTS["service_bps"][3], self.econ["platform_service_bps"])
        self.assertEqual(self.m.FACTS["authorship_bps"][3], self.econ["proponent_participation_bps"])
        self.assertEqual(self.m.FACTS["service_bps"][3], 350)
        self.assertEqual(self.m.FACTS["authorship_bps"][3], 150)

    def test_gmv_and_authorship_are_never_revenue(self):
        for sc in ("conservador", "base", "agressivo"):
            for hybrid in (False, True):
                for r in self.m.simulate(sc, hybrid):
                    self.assertEqual(r["revenue"], r["fee_recognized"] + r["mrr"] + r["setup_recognized"] + r["services"])
                    # a autoria (1,5 %) existe como coluna própria e não entra em nenhuma linha de receita
                    self.assertGreaterEqual(r["authorship_cents"], 0)
                    self.assertLessEqual(r["fee_recognized"], r["gmv_settled"] * 350 / 10_000 + 1)

    def test_no_fee_before_activation_and_only_after_settlement(self):
        rows = self.m.simulate("base", False)
        act = self.m.p("base", "fee_activation_month")
        lag = int(self.m.p("base", "months_to_settle"))
        for r in rows:
            if r["month"] < act + lag:
                self.assertEqual(r["fee_recognized"], 0, f"taxa reconhecida antes da ativação+quitação no mês {r['month']}")
        self.assertGreater(sum(r["fee_recognized"] for r in rows), 0)
        never = self.m.simulate("base", False, {"fee_activation_month": 10_000})
        self.assertEqual(sum(r["fee_recognized"] for r in never), 0)

    def test_current_design_has_no_institutional_contracts(self):
        for sc in ("conservador", "base", "agressivo"):
            for r in self.m.simulate(sc, False):
                self.assertEqual(r["inst_contracts"], 0.0)
                self.assertEqual(r["mrr"], 0)
                self.assertEqual(r["setup_recognized"], 0)

    def test_published_json_matches_engine(self):
        data = json.loads((OUT / "resultados_120m.json").read_text(encoding="utf-8"))
        for sc in ("conservador", "base", "agressivo"):
            for design, hybrid in (("atual", False), ("hibrido", True)):
                rows = self.m.simulate(sc, hybrid)
                ms = self.m.milestones(rows)
                for mark in ("6", "12", "24", "48", "120"):
                    self.assertEqual(data[sc][design]["milestones"][mark]["revenue_ttm"], ms[int(mark)]["revenue_ttm"], (sc, design, mark))
                self.assertEqual(data[sc][design]["breakeven_month"], self.m.breakeven_month(rows))

    def test_valuation_never_multiplies_gmv(self):
        rows = self.m.simulate("agressivo", True)
        ms = self.m.milestones(rows)
        v = self.m.valuation("agressivo", ms)
        for mark, d in v.items():
            self.assertLess(d["ev"], ms[int(mark)]["gmv_originated_ttm"] * 1.0 + ms[int(mark)]["arr"] * 10 + ms[int(mark)]["services_ttm"] * 3)
            self.assertLessEqual(d["founder_equity"], d["ev"])


if __name__ == "__main__":
    unittest.main()
