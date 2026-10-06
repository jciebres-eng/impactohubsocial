"""v0.18.0 — interoperabilidade de frameworks e materialidade.

As duas afirmações que estes testes protegem são recusas:

1. **`certified` não existe.** A escada vai até `audited`, e o banco recusa a palavra com a razão.
2. **Nenhum mapeamento para referencial de terceiro foi semeado.** Sem a lista oficial de códigos,
   mapear seria inventar — e alguém publicaria relatório citando código inexistente.

E a trava da materialidade: `is_material` é DERIVADA do eixo e do limiar declarado. Não é escrevível,
e é isso que impede ajustar a matriz no fim para dar o resultado desejado.
"""
from __future__ import annotations

import pathlib
import unittest

from tests.support import db_system, new_account, owner_conn

REPO = pathlib.Path(__file__).resolve().parents[2]
LONG = "Razão declarada com extensão suficiente para passar pelo CHECK do banco nesta coluna."


class RegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = new_account("company", compliance="approved")

    def test_the_registry_tells_the_truth_about_each_framework(self):
        r = self.c.get("/v1/frameworks")
        self.assertEqual(r.status, 200, r)
        self.assertGreaterEqual(r.json["by_status"].get("in_use", 0), 4)
        self.assertGreaterEqual(r.json["by_status"].get("registry_only", 0), 6)
        for item in r.json["items"]:
            if item["status"] == "in_use":
                self.assertTrue(item["implemented_by"],
                                f"{item['key']} diz estar em uso e não diz onde")
            if item["status"] == "registry_only":
                self.assertTrue(item["license_note"],
                                f"{item['key']} não explica por que não é mapeado")

    def test_theory_of_change_is_declared_as_already_implemented(self):
        """Já funcionava desde a v0.8.0 com outro nome. Nomear é a entrega; reimplementar seria erro."""
        items = {i["key"]: i for i in self.c.get("/v1/frameworks").json["items"]}
        toc = items["theory_of_change"]
        self.assertEqual(toc["status"], "in_use")
        self.assertIn("impact_nodes", toc["implemented_by"])
        self.assertIn("impact_edges", toc["implemented_by"])

    def test_gri_and_issb_are_registry_only_with_the_reason_written(self):
        items = {i["key"]: i for i in self.c.get("/v1/frameworks").json["items"]}
        for key in ("gri", "issb", "iris_plus", "tcfd", "tnfd", "sroi"):
            self.assertEqual(items[key]["status"], "registry_only", key)
        self.assertIn("código inexistente", items["gri"]["license_note"])

    def test_no_framework_claims_a_verified_reference(self):
        """Versão e URL oficiais precisam ser conferidas por alguém contra a fonte."""
        with db_system() as c:
            claiming = c.query("SELECT key FROM impact_frameworks WHERE reference_verified")
        self.assertEqual(claiming, [])

    def test_no_mapping_to_a_third_party_framework_was_seeded(self):
        for sql in (REPO / "backend" / "migrations").glob("*.sql"):
            self.assertNotIn("INSERT INTO framework_mappings", sql.read_text(encoding="utf-8"),
                             f"{sql.name} semeia mapeamento de framework")

    def test_the_refused_relation_is_declared_in_the_api(self):
        r = self.c.get("/v1/frameworks").json
        refused = {x["key"]: x["reason"] for x in r["refused_relations"]}
        self.assertIn("certified", refused)
        self.assertIn("NÃO é organismo certificador", refused["certified"])
        self.assertNotIn("certified", [x["key"] for x in r["relations"]])


class MappingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = new_account("company", compliance="approved")
        cls.other = new_account("company", compliance="approved")
        with db_system() as db:
            cls.ind = db.scalar("SELECT id::text FROM indicator_catalog WHERE org_id IS NULL"
                                " LIMIT 1")

    def test_certified_is_refused_by_the_api_with_the_reason(self):
        r = self.c.post("/v1/frameworks/mappings", {
            "framework_key": "ods", "indicator_id": self.ind, "relation": "certified",
            "rationale": LONG})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "relation_refused")
        self.assertIn("NÃO é organismo certificador", r.json["title"])

    def test_certified_is_refused_by_the_database_too(self):
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("INSERT INTO framework_mappings(framework_key, indicator_id, relation,"
                       " rationale) VALUES ('ods',$1,'certified',$2)", self.ind, LONG)
            self.assertIn("organismo certificador", str(e.exception))
        finally:
            oc.close()

    def test_an_aligned_mapping_is_accepted(self):
        r = self.c.post("/v1/frameworks/mappings", {
            "framework_key": "ods", "indicator_id": self.ind, "relation": "aligned",
            "rationale": LONG})
        self.assertEqual(r.status, 201, r)
        self.assertIn("sem conferência", r.json["relation_label"])

    def test_reported_requires_a_source(self):
        r = self.c.post("/v1/frameworks/mappings", {
            "framework_key": "esg", "indicator_id": self.ind, "relation": "reported",
            "rationale": LONG})
        self.assertEqual(r.status, 422, r)
        ok = self.c.post("/v1/frameworks/mappings", {
            "framework_key": "esg", "indicator_id": self.ind, "relation": "reported",
            "rationale": LONG, "source_name": "Relatório anual 2026, página 14"})
        self.assertEqual(ok.status, 201, ok)

    def test_verified_requires_a_reviewer_from_another_organization(self):
        r = self.c.post("/v1/frameworks/mappings", {
            "framework_key": "theory_of_change", "indicator_id": self.ind, "relation": "verified",
            "rationale": LONG, "source_name": "Parecer de verificação",
            "reviewer_org_id": self.c.org_id})
        self.assertEqual(r.status, 422, f"quem declara não verifica: {r}")
        ok = self.c.post("/v1/frameworks/mappings", {
            "framework_key": "theory_of_change", "indicator_id": self.ind, "relation": "verified",
            "rationale": LONG, "source_name": "Parecer de verificação",
            "reviewer_org_id": self.other.org_id})
        self.assertEqual(ok.status, 201, ok)
        self.assertIsNotNone(ok.json["reviewed_at"], "a data da revisão é derivada, não digitada")

    def test_verified_against_a_registry_only_framework_is_refused(self):
        r = self.c.post("/v1/frameworks/mappings", {
            "framework_key": "gri", "indicator_id": self.ind, "relation": "verified",
            "rationale": LONG, "source_name": "Parecer", "reviewer_org_id": self.other.org_id})
        self.assertEqual(r.status, 422, r)
        self.assertIn("registry_only", r.json["title"])

    def test_coverage_answers_with_a_number_not_an_impression(self):
        r = self.c.get("/v1/frameworks/gri/coverage")
        self.assertEqual(r.status, 200, r)
        self.assertFalse(r.json["can_report"])
        self.assertIn("NÃO o mapeia", r.json["note"])

    def test_another_organization_cannot_remove_my_mapping(self):
        mine = self.c.post("/v1/frameworks/mappings", {
            "framework_key": "dei_equity", "indicator_id": self.ind, "relation": "mapped",
            "rationale": LONG}).json["id"]
        self.assertEqual(self.other.delete(f"/v1/frameworks/mappings/{mine}").status, 404)


class MaterialityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = new_account("company", compliance="approved")

    def _open(self, **kw) -> str:
        body = {"period_label": "2026", "method_note": LONG + " Método declarado.", **kw}
        r = self.c.post("/v1/materiality", body)
        assert r.status == 201, r
        return r.json["id"]

    def test_the_lens_and_the_threshold_are_declared(self):
        a = self._open(lens="double", threshold=4)
        got = self.c.get(f"/v1/materiality/{a}").json
        self.assertEqual(got["lens"], "double")
        self.assertEqual(got["threshold"], 4)
        self.assertIn("dupla materialidade", got["lens_label"])

    def test_is_material_is_derived_from_the_threshold(self):
        a = self._open(threshold=4)
        r1 = self.c.put(f"/v1/materiality/{a}/topics",
                        {"topic_code": "emissoes", "impact_score": 5, "rationale": LONG})
        self.assertEqual(r1.status, 200, r1)
        self.assertTrue(r1.json["is_material"])
        r2 = self.c.put(f"/v1/materiality/{a}/topics",
                        {"topic_code": "agua", "impact_score": 2, "rationale": LONG})
        self.assertFalse(r2.json["is_material"])

    def test_is_material_cannot_be_written_by_hand(self):
        a = self._open(threshold=5)
        self.c.put(f"/v1/materiality/{a}/topics",
                   {"topic_code": "residuos", "impact_score": 1, "rationale": LONG})
        oc = owner_conn()
        try:
            oc.run("UPDATE materiality_entries SET is_material = true WHERE assessment_id = $1", a)
            # O gatilho rederiva: escrever à mão não sobrevive.
            self.assertFalse(oc.scalar("SELECT is_material FROM materiality_entries"
                                       " WHERE assessment_id = $1", a),
                             "is_material é derivada, e a derivação ganha da escrita manual")
        finally:
            oc.close()

    def test_a_single_lens_refuses_the_other_axis(self):
        a = self._open(lens="impact_only")
        r = self.c.put(f"/v1/materiality/{a}/topics",
                       {"topic_code": "integridade", "financial_score": 5, "rationale": LONG})
        self.assertEqual(r.status, 422, r)
        self.assertIn("impact_only", r.json["title"])

    def test_an_entry_needs_at_least_one_axis(self):
        a = self._open()
        r = self.c.put(f"/v1/materiality/{a}/topics",
                       {"topic_code": "transparencia", "rationale": LONG})
        self.assertEqual(r.status, 422, r)

    def test_publishing_an_almost_empty_matrix_is_refused(self):
        a = self._open()
        self.c.put(f"/v1/materiality/{a}/topics",
                   {"topic_code": "emissoes", "impact_score": 5, "rationale": LONG})
        r = self.c.post(f"/v1/materiality/{a}/publish", {})
        self.assertEqual(r.status, 422, r)
        self.assertIn("três temas", r.json["title"])

    def test_publishing_works_with_three_topics_and_then_locks(self):
        a = self._open()
        for topic, score in (("emissoes", 5), ("agua", 3), ("comunidade", 4)):
            self.c.put(f"/v1/materiality/{a}/topics",
                       {"topic_code": topic, "impact_score": score, "rationale": LONG})
        r = self.c.post(f"/v1/materiality/{a}/publish", {})
        self.assertEqual(r.status, 200, r)
        self.assertIsNotNone(r.json["published_at"])
        depois = self.c.put(f"/v1/materiality/{a}/topics",
                            {"topic_code": "residuos", "impact_score": 5, "rationale": LONG})
        self.assertEqual(depois.status, 422, "publicada não recebe tema novo")

    def test_publishing_supersedes_the_previous_published_one(self):
        primeira = self._open(period_label="2025")
        for topic in ("emissoes", "agua", "comunidade"):
            self.c.put(f"/v1/materiality/{primeira}/topics",
                       {"topic_code": topic, "impact_score": 4, "rationale": LONG})
        self.c.post(f"/v1/materiality/{primeira}/publish", {})
        segunda = self._open(period_label="2027")
        for topic in ("emissoes", "agua", "integridade"):
            self.c.put(f"/v1/materiality/{segunda}/topics",
                       {"topic_code": topic, "impact_score": 4, "rationale": LONG})
        self.assertEqual(self.c.post(f"/v1/materiality/{segunda}/publish", {}).status, 200)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM materiality_assessments WHERE id = $1",
                                      primeira), "superseded")

    def test_the_matrix_shows_which_topics_have_no_evidence(self):
        a = self._open()
        for topic in ("emissoes", "agua", "comunidade"):
            self.c.put(f"/v1/materiality/{a}/topics",
                       {"topic_code": topic, "impact_score": 5, "rationale": LONG})
        got = self.c.get(f"/v1/materiality/{a}").json
        self.assertEqual(got["topics_assessed"], 3)
        self.assertTrue(all(not r["has_evidence"] for r in got["matrix"]))
        self.assertIn("DERIVADA", got["note"])

    def test_the_topic_catalog_declares_itself_editorial(self):
        r = self.c.get("/v1/materiality/topics")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(len(r.json["items"]), 15)
        self.assertIn("editorial", r.json["note"].lower())
        for t in r.json["items"]:
            self.assertIn("editorial", t["source_note"].lower())


if __name__ == "__main__":
    unittest.main()
