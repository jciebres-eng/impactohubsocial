"""v0.17.0 — o registro de motores operacionais, visto pela API.

Os testes estruturais (resolução, versão, rota, varredura de chamada ao modelo) estão em
`test_architecture.py`, porque são sobre o código. Aqui é o contrato da rota.
"""
from __future__ import annotations

import unittest

from tests.support import new_account


class EngineRegistryRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def test_the_registry_is_served_with_the_three_natures(self):
        r = self.c.get("/v1/engines")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(set(r.json["by_kind"]), {"deterministic", "grounded_retrieval",
                                                  "llm_assisted"})
        self.assertGreater(r.json["total"], 20)

    def test_the_deterministic_engines_are_the_large_majority(self):
        """'IA como motor operacional' só é verdade se a maior parte do produto não depender dela."""
        by = self.c.get("/v1/engines").json["by_kind"]
        self.assertGreater(by["deterministic"], 3 * by["llm_assisted"])

    def test_only_three_points_call_a_language_model(self):
        body = self.c.get("/v1/engines").json
        self.assertEqual(body["by_kind"]["llm_assisted"], 3)
        self.assertEqual(body["ai_call_sites"], ["impacto/api/ai_routes.py"])

    def test_every_engine_declares_what_it_never_decides(self):
        body = self.c.get("/v1/engines").json
        for group, items in body["groups"].items():
            for e in items:
                self.assertTrue(e["never"].strip(), f"{group}/{e['key']} sem 'o que nunca faz'")
                self.assertTrue(e["produces"].strip(), f"{group}/{e['key']} sem 'o que produz'")

    def test_the_assistants_are_declared_as_retrieval_not_conversation(self):
        body = self.c.get("/v1/engines").json
        search = {e["key"]: e for items in body["groups"].values() for e in items}
        self.assertEqual(search["help_assistant"]["kind"], "grounded_retrieval")
        self.assertEqual(search["solution_assistant"]["kind"], "grounded_retrieval")
        self.assertIn("não é chatbot", search["help_assistant"]["never"].lower())

    def test_the_ai_controls_are_declared_including_pii_redaction(self):
        controls = " ".join(self.c.get("/v1/engines").json["ai_controls"]).lower()
        for expected in ("cota", "redação de dado pessoal", "revisão humana"):
            self.assertIn(expected, controls)

    def test_the_assistants_really_answer_without_a_model(self):
        """Não basta declarar: a resposta do produto tem de dizer `ai_used: false`."""
        r = self.c.post("/v1/help/assistant", {"question": "como cadastro um projeto"})
        self.assertEqual(r.status, 200, r)
        self.assertFalse(r.json["ai_used"])
        self.assertTrue(r.json["grounded"])


if __name__ == "__main__":
    unittest.main()
