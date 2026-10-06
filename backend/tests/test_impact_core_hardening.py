import unittest

from impacto.engines.match.context import contextual_impact
from impacto.engines.match.engine import MatchInput, evaluate
from impacto.impact.longitudinal import summarize_measurements


class ContextualImpactTests(unittest.TestCase):
    def test_unknown_is_not_zero_and_large_population_does_not_dominate_context(self):
        unknown = contextual_impact({"beneficiaries_count": 5000}, has_indicators=False)
        self.assertIsNone(unknown["score"])
        self.assertEqual(unknown["coverage"], 0.0)

        urban = contextual_impact({"impact_context": {
            "need_level": .25, "barrier_burden": .1, "infrastructure_gap": .05,
            "additionality_score": .3, "sustainability_score": .8,
            "outcome_evidence_score": .8, "denominator_quality": .9}}, has_indicators=True)
        remote = contextual_impact({"impact_context": {
            "need_level": .95, "barrier_burden": .95, "infrastructure_gap": .95,
            "additionality_score": .8, "sustainability_score": .6,
            "outcome_evidence_score": .7, "denominator_quality": .6}}, has_indicators=True)
        self.assertGreater(remote["score"], urban["score"])

    def test_match_exposes_context_signal_and_unknown(self):
        base = {"org": {"kind": "osc", "compliance_status": "approved"},
                "funder": {"causes": ["education"]}, "project": {
                    "visibility": "published", "causes": ["education"], "territory": "BR-MT",
                    "budget_total_cents": 100000, "beneficiaries_count": 5000,
                    "impact_context": {"need_level": .9, "barrier_burden": .8, "infrastructure_gap": .8,
                                       "additionality_score": .8, "outcome_evidence_score": .6}}}
        result = evaluate(MatchInput.build("funder_project", **base))
        signal = next(s for s in result["signals"] if s["key"] == "impact")
        self.assertIsNotNone(signal["value"])
        self.assertIn("Contexto agregado", signal["detail"])


class LongitudinalTests(unittest.TestCase):
    def test_series_separates_reported_and_validated_and_does_not_claim_causality(self):
        out = summarize_measurements([
            {"id": "2", "measured_on": "2026-02-01", "value": 12, "status": "validated", "evidence_id": "e2"},
            {"id": "1", "measured_on": "2026-01-01", "value": 10, "status": "reported", "evidence_id": None},
            {"id": "3", "measured_on": "2026-03-01", "value": 15, "status": "validated", "evidence_id": "e3"},
        ])
        self.assertEqual(out["validated_periods"], 2)
        self.assertEqual(out["reported_periods"], 1)
        self.assertEqual(out["validated_delta"], 3.0)
        self.assertIn("não prova causalidade", out["interpretation"])


if __name__ == "__main__":
    unittest.main()
