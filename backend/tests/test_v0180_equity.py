"""v0.18.0 — contexto de equidade, denominador com fonte e a comparação que se recusa.

A afirmação que estes testes protegem é a tese desta rodada: **impacto não é quantidade.** E a trava
que a sustenta é desconfortável de propósito — sem denominador declarado com fonte, não existe número
normalizado. "Atendemos 12% da população elegível" só pode ser dito por quem declarou qual população,
de que fonte e de que data.
"""
from __future__ import annotations

import unittest

from tests.support import app_tx, db_system, make_admin, new_account, owner_conn

LONG = "Texto declarado com extensão suficiente para passar pelo CHECK do banco nesta coluna."


class EquityBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        cls.admin, _ = make_admin()
        cls.project = cls._project(cls.osc, "BR-AC-1200013")

    @classmethod
    def _project(cls, client, territory: str, beneficiaries: int = 120) -> str:
        r = client.post("/v1/projects", {
            "title": f"Projeto de equidade {territory}",
            "summary": "Projeto criado para exercitar o contexto de equidade da v0.18.0.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": territory, "causes": ["educacao"],
            "beneficiaries_count": beneficiaries,
            "budget_total_cents": 8_000_000})
        assert r.status == 201, r
        return r.json["id"]


# ================================================================================================ catálogo
class CatalogTests(EquityBase):
    def test_the_barrier_catalog_declares_itself_as_editorial(self):
        r = self.osc.get("/v1/equity/catalog")
        self.assertEqual(r.status, 200, r)
        self.assertGreaterEqual(len(r.json["items"]), 10)
        self.assertIn("editorial", r.json["note"].lower())
        self.assertIn("nunca da pessoa", r.json["note"].lower())
        for item in r.json["items"]:
            self.assertIn("não é classificação oficial", item["source_note"])

    def test_every_normalization_method_declares_its_denominator(self):
        methods = self.osc.get("/v1/equity/catalog").json["methods"]
        self.assertGreaterEqual(len(methods), 6)
        for m in methods:
            self.assertTrue(m["denominator"], m)
            self.assertTrue(m["label"], m)


# ================================================================================================ a trava
class DenominatorLockTests(EquityBase):
    def test_without_a_denominator_every_method_is_unavailable_with_a_reason(self):
        """A trava central: a resposta é "indisponível", nunca uma estimativa.

        Projeto PRÓPRIO de propósito: os testes de uma classe rodam em ordem alfabética e compartilham
        o que a classe criou, então "sem denominador" rodava depois de "com denominador" e media o
        contrário do que diz o nome.
        """
        novo = self._project(self.osc, "BR-MT-5105150")
        r = self.osc.get(f"/v1/projects/{novo}/equity/normalization")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["available"], [])
        self.assertGreaterEqual(len(r.json["unavailable"]), 6)
        for method, data in r.json["methods"].items():
            self.assertFalse(data["available"], method)
            self.assertIn("declarado com fonte", data["reason"])

    def test_a_denominator_without_a_source_is_refused_by_the_api(self):
        r = self.osc.post("/v1/equity/denominators", {
            "project_id": self.project, "kind": "eligible_population", "value": 500,
            "unit": "pessoas", "reference_date": "2025-01-01", "source_date": "2026-10-06",
            "method_note": "Método declarado com extensão suficiente."})
        self.assertEqual(r.status, 422, r)
        self.assertIn("source_name", str(r.json["details"]))

    def test_a_denominator_without_a_source_is_refused_by_the_database_too(self):
        with app_tx(self.osc) as conn, self.assertRaises(Exception) as e:
            conn.run("INSERT INTO equity_denominators(scope, project_id, org_id, kind, value, unit,"
                     " reference_date, source_date, method_note)"
                     " VALUES ('project',$1,$2,'eligible_population',500,'pessoas','2025-01-01',"
                     " '2026-10-06','Método com extensão suficiente para o CHECK.')",
                     self.project, self.osc.org_id)
        self.assertIn("source_name", str(e.exception))

    def test_with_a_denominator_the_method_becomes_available_and_carries_its_source(self):
        r = self.osc.post("/v1/equity/denominators", {
            "project_id": self.project, "kind": "eligible_population", "value": 480,
            "unit": "pessoas", "reference_date": "2025-01-01",
            "source_name": "Censo escolar municipal 2024", "source_date": "2026-10-06",
            "method_note": "Matrículas da rede municipal na faixa etária do projeto."})
        self.assertEqual(r.status, 201, r)
        norm = self.osc.get(f"/v1/projects/{self.project}/equity/normalization").json
        self.assertIn("per_eligible_population", norm["available"])
        m = norm["methods"]["per_eligible_population"]
        self.assertEqual(m["denominator_value"], 480.0)
        self.assertEqual(m["source_name"], "Censo escolar municipal 2024")
        self.assertEqual(m["basis"], "declared",
                         "sem medição validada, o numerador é declarado e a resposta diz isso")
        self.assertAlmostEqual(m["value"], 120 / 480 * 1000, places=2)

    def test_a_new_version_closes_the_previous_one_and_the_old_number_survives(self):
        self.osc.post("/v1/equity/denominators", {
            "project_id": self.project, "kind": "households", "value": 100, "unit": "domicílios",
            "reference_date": "2024-01-01", "source_name": "Fonte A", "source_date": "2026-10-06",
            "method_note": "Primeira versão declarada para o teste de versionamento."})
        self.osc.post("/v1/equity/denominators", {
            "project_id": self.project, "kind": "households", "value": 110, "unit": "domicílios",
            "reference_date": "2025-01-01", "source_name": "Fonte B", "source_date": "2026-10-06",
            "method_note": "Segunda versão, que deve fechar a vigência da primeira."})
        todos = self.osc.get(f"/v1/equity/denominators?project_id={self.project}"
                             "&include_closed=true").json["items"]
        casa = [d for d in todos if d["kind"] == "households"]
        self.assertEqual(len(casa), 2, "o número antigo não desaparece")
        vigentes = [d for d in casa if d["effective_until"] is None]
        self.assertEqual(len(vigentes), 1)
        self.assertEqual(float(vigentes[0]["value"]), 110.0)

    def test_the_denominator_value_is_immutable(self):
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("UPDATE equity_denominators SET value = 1 WHERE kind = 'households'"
                       " AND effective_until IS NULL")
            self.assertIn("imutável", str(e.exception))
        finally:
            oc.close()

    def test_a_territory_denominator_is_a_common_good_and_only_the_admin_publishes_it(self):
        r = self.osc.post("/v1/equity/denominators", {
            "scope": "project", "project_id": self.project, "kind": "reference_population",
            "value": 1000, "unit": "pessoas", "reference_date": "2025-01-01",
            "source_name": "Declaração da própria organização", "source_date": "2026-10-06",
            "method_note": "A organização pode declarar o denominador do PRÓPRIO projeto."})
        self.assertEqual(r.status, 201, r)
        with app_tx(self.osc) as conn, self.assertRaises(Exception):
            conn.run("INSERT INTO equity_denominators(scope, territory, kind, value, unit,"
                     " reference_date, source_name, source_date, method_note)"
                     " VALUES ('territory','BR-AC-1200013','reference_population',9999,'pessoas',"
                     " '2025-01-01','Tentativa da organização','2026-10-06',"
                     " 'A organização não publica denominador de território.')")
        ok = self.admin.post("/v1/admin/equity/denominators", {
            "territory": "BR-AC-1200013", "kind": "area_km2", "value": 3215.0, "unit": "km²",
            "reference_date": "2024-01-01", "source_name": "Área declarada pelo teste",
            "source_date": "2026-10-06", "method_note": "Valor de teste para a área do município."})
        self.assertEqual(ok.status, 201, ok)


# ================================================================================================ contexto
class ContextTests(EquityBase):
    def setUp(self):
        self.p = self._project(self.osc, "BR-MT-5105150")

    def test_additionality_above_declared_requires_the_counterfactual(self):
        r = self.osc.put(f"/v1/projects/{self.p}/equity/context", {
            "need_statement": LONG, "additionality": LONG,
            "additionality_standing": "documented"})
        self.assertEqual(r.status, 422, r)
        ok = self.osc.put(f"/v1/projects/{self.p}/equity/context", {
            "need_statement": LONG, "additionality": LONG, "counterfactual": LONG,
            "additionality_standing": "documented"})
        self.assertEqual(ok.status, 200, ok)
        self.assertEqual(ok.json["additionality_standing"], "documented")

    def test_evidenced_additionality_requires_evidence(self):
        r = self.osc.put(f"/v1/projects/{self.p}/equity/context", {
            "need_statement": LONG, "additionality": LONG, "counterfactual": LONG,
            "additionality_standing": "evidenced"})
        self.assertEqual(r.status, 422, r)

    def test_another_organization_cannot_declare_my_context(self):
        r = self.other.put(f"/v1/projects/{self.p}/equity/context", {
            "need_statement": LONG, "additionality": LONG})
        self.assertIn(r.status, (403, 404), r)


# ================================================================================================ barreiras
class BarrierTests(EquityBase):
    def setUp(self):
        self.p = self._project(self.osc, "BR-MT-5105150")

    def test_a_declared_barrier_is_accepted_and_labelled(self):
        r = self.osc.post(f"/v1/projects/{self.p}/equity/barriers", {
            "barrier_code": "lingua", "note": "A comunidade atendida usa língua indígena própria."})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["standing"], "declared")
        self.assertIn("declarada", r.json["standing_label"])

    def test_an_evidenced_barrier_without_evidence_is_refused(self):
        r = self.osc.post(f"/v1/projects/{self.p}/equity/barriers", {
            "barrier_code": "conectividade", "standing": "evidenced",
            "note": "Conexão insuficiente para a atividade pretendida."})
        self.assertEqual(r.status, 422, r)

    def test_a_documented_barrier_needs_a_source_with_a_date_or_a_document(self):
        r = self.osc.post(f"/v1/projects/{self.p}/equity/barriers", {
            "barrier_code": "transporte_ausente", "standing": "documented",
            "note": "Não há linha regular até a comunidade."})
        self.assertEqual(r.status, 422, r)
        ok = self.osc.post(f"/v1/projects/{self.p}/equity/barriers", {
            "barrier_code": "transporte_ausente", "standing": "documented",
            "note": "Não há linha regular até a comunidade.",
            "source_name": "Plano municipal de mobilidade 2024", "source_date": "2026-01-15"})
        self.assertEqual(ok.status, 201, ok)
        self.assertEqual(ok.json["standing"], "documented")

    def test_an_unknown_barrier_code_is_refused(self):
        r = self.osc.post(f"/v1/projects/{self.p}/equity/barriers", {
            "barrier_code": "barreira_inventada", "note": "Código que não existe no catálogo."})
        self.assertIn(r.status, (409, 422), r)


# ================================================================================================ retrato
class AssessmentTests(EquityBase):
    def setUp(self):
        self.p = self._project(self.osc, "BR-MT-5105150")
        self.osc.put(f"/v1/projects/{self.p}/equity/context",
                     {"need_statement": LONG, "additionality": LONG})
        self.osc.post(f"/v1/projects/{self.p}/equity/barriers",
                      {"barrier_code": "distancia_servico", "note": "Deslocamento de 40 km."})

    def test_the_assessment_has_no_score_and_says_why(self):
        r = self.osc.post(f"/v1/projects/{self.p}/equity/assessments", {})
        self.assertEqual(r.status, 201, r)
        self.assertIsNone(r.json["score"], "não existe nota de equidade, de propósito")
        self.assertIn("multiplicar fatores estimados", r.json["note"])
        self.assertEqual(r.json["barriers"][0]["barrier_code"], "distancia_servico")
        self.assertIn(r.json["confidence_band"],
                      ("high", "medium", "low", "insufficient_data"))

    def test_the_assessment_is_append_only(self):
        r = self.osc.post(f"/v1/projects/{self.p}/equity/assessments", {})
        oc = owner_conn()
        try:
            with self.assertRaises(Exception):
                oc.run("UPDATE equity_assessments SET barriers_total = 99 WHERE id = $1",
                       r.json["id"])
        finally:
            oc.close()

    def test_the_history_keeps_every_snapshot(self):
        self.osc.post(f"/v1/projects/{self.p}/equity/assessments", {})
        self.osc.post(f"/v1/projects/{self.p}/equity/assessments", {})
        h = self.osc.get(f"/v1/projects/{self.p}/equity/assessments").json["items"]
        self.assertGreaterEqual(len(h), 2)

    def test_confidence_rises_when_the_barrier_is_documented(self):
        antes = self.osc.post(f"/v1/projects/{self.p}/equity/assessments", {}).json["confidence"]
        self.osc.post(f"/v1/projects/{self.p}/equity/barriers", {
            "barrier_code": "distancia_servico", "standing": "documented",
            "note": "Deslocamento de 40 km até o equipamento mais próximo.",
            "source_name": "Levantamento da secretaria municipal", "source_date": "2026-02-01"})
        depois = self.osc.post(f"/v1/projects/{self.p}/equity/assessments", {}).json["confidence"]
        self.assertGreater(depois, antes,
                           "documentar a barreira tem de aumentar a confiança, não a nota")


# ================================================================================================ comparação
class ComparisonTests(EquityBase):
    """O teste que os documentos desta rodada pedem, e a resposta que eu defendo."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.grande = cls._project(cls.osc, "BR-MT-5105150", beneficiaries=5000)
        cls.pequeno = cls._project(cls.osc, "BR-AC-1200013", beneficiaries=120)
        for pid in (cls.grande, cls.pequeno):
            cls.osc.put(f"/v1/projects/{pid}/equity/context",
                        {"need_statement": LONG, "additionality": LONG})
        cls.osc.post(f"/v1/projects/{cls.pequeno}/equity/barriers", {
            "barrier_code": "distancia_servico", "note": "Deslocamento de 180 km até a cidade."})
        cls.osc.post(f"/v1/projects/{cls.pequeno}/equity/barriers", {
            "barrier_code": "lingua", "note": "A comunidade usa língua indígena própria."})

    def test_without_denominators_the_comparison_refuses_itself(self):
        a = self._project(self.osc, "BR-MT-5105150", beneficiaries=5000)
        b = self._project(self.osc, "BR-AC-1200013", beneficiaries=120)
        r = self.osc.post("/v1/equity/compare", {"project_ids": [a, b]})
        self.assertEqual(r.status, 200, r)
        self.assertFalse(r.json["comparable"])
        self.assertTrue(r.json["reasons"])
        self.assertIn("denominador", " ".join(r.json["reasons"]))
        self.assertIsNone(r.json["verdict"])

    def test_it_never_declares_a_winner_even_when_comparable(self):
        for pid, pop in ((self.grande, 200_000), (self.pequeno, 600)):
            self.osc.post("/v1/equity/denominators", {
                "project_id": pid, "kind": "reference_population", "value": pop,
                "unit": "pessoas", "reference_date": "2025-01-01",
                "source_name": "População declarada pelo teste", "source_date": "2026-10-06",
                "method_note": "Denominador declarado para exercitar a comparação."})
        r = self.osc.post("/v1/equity/compare", {"project_ids": [self.grande, self.pequeno]})
        self.assertEqual(r.status, 200, r)
        self.assertIsNone(r.json["verdict"], "a plataforma não elege o projeto de mais impacto")
        self.assertIn("NÃO declara qual projeto tem mais impacto", r.json["note"])
        self.assertIn("50 pessoas atendidas num território remoto", r.json["note"])

    def test_the_small_project_is_not_buried_by_the_absolute_number(self):
        """5.000 em 200.000 é 25 por mil. 120 em 600 é 200 por mil. A escala absoluta engana."""
        r = self.osc.post("/v1/equity/compare", {"project_ids": [self.grande, self.pequeno]})
        por_mil = {e["project_id"]: e["value"]
                   for e in r.json["comparison"].get("per_reference_population", [])}
        if not por_mil:
            self.skipTest("denominadores ainda não disponíveis para os dois lados")
        self.assertGreater(por_mil[self.pequeno], por_mil[self.grande])

    def test_it_still_warns_that_only_declared_numbers_were_compared(self):
        r = self.osc.post("/v1/equity/compare", {"project_ids": [self.grande, self.pequeno]})
        self.assertIn("apenas número DECLARADO", " ".join(r.json["reasons"]))
        self.assertFalse(r.json["comparable"],
                         "comparar declaração com declaração não é comparar resultado")

    def test_comparing_needs_two_projects(self):
        r = self.osc.post("/v1/equity/compare", {"project_ids": [self.grande]})
        self.assertEqual(r.status, 422, r)

    def test_it_warns_when_the_two_denominators_come_from_different_sources(self):
        a = self._project(self.osc, "BR-MT-5105150", beneficiaries=300)
        b = self._project(self.osc, "BR-MT-5105150", beneficiaries=300)
        for pid, fonte in ((a, "Censo demográfico 2022"), (b, "Estimativa própria 2025")):
            self.osc.post("/v1/equity/denominators", {
                "project_id": pid, "kind": "households", "value": 1000, "unit": "domicílios",
                "reference_date": "2024-01-01", "source_name": fonte, "source_date": "2026-10-06",
                "method_note": "Fontes diferentes de propósito, para exercitar o aviso."})
        r = self.osc.post("/v1/equity/compare", {"project_ids": [a, b]})
        self.assertIn("per_household", r.json["different_sources"])
        self.assertIn("FONTES DIFERENTES", r.json["note"])


# ================================================================================================ 0017 corrigida
class BaselineSourceTests(EquityBase):
    def test_a_project_baseline_now_requires_a_source_like_the_program_one(self):
        """Inconsistência da v0.17.0: `program_indicators` exigia fonte, `project_indicators` não."""
        p = self._project(self.osc, "BR-MT-5105150")
        with db_system() as c:
            ind = c.scalar("SELECT id::text FROM indicator_catalog WHERE org_id IS NULL LIMIT 1")
        if not ind:
            self.skipTest("catálogo de indicadores vazio neste ambiente")
        with app_tx(self.osc) as conn, self.assertRaises(Exception) as e:
            conn.run("INSERT INTO project_indicators(project_id, org_id, indicator_id, baseline)"
                     " VALUES ($1,$2,$3,42)", p, self.osc.org_id, ind)
        self.assertIn("fonte", str(e.exception).lower())
        with app_tx(self.osc) as conn:
            conn.run("INSERT INTO project_indicators(project_id, org_id, indicator_id, baseline,"
                     " baseline_source) VALUES ($1,$2,$3,42,'Censo Escolar INEP 2024')",
                     p, self.osc.org_id, ind)

    def test_the_grandfathered_rows_are_countable_not_silent(self):
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM project_baselines_without_source")
        self.assertIsInstance(n, int,
                             "a view existe para que a dívida seja contável em vez de silenciosa")


if __name__ == "__main__":
    unittest.main()


class BaselineRouteTests(EquityBase):
    """A rota também cobra a fonte, e com mensagem útil — não só o gatilho do banco.

    Trava que só existe no banco chega ao usuário como "integrity_error". A rota recusa antes, com
    `baseline_source_required` e a frase que explica por quê.
    """

    def test_the_route_refuses_a_baseline_without_a_source(self):
        p = self._project(self.osc, "BR-MT-5105150")
        cat = self.osc.get("/v1/indicators/catalog").json["items"]
        if not cat:
            self.skipTest("catálogo de indicadores vazio neste ambiente")
        r = self.osc.post(f"/v1/projects/{p}/indicators",
                          {"indicator_id": cat[0]["id"], "baseline": 10, "target": 40})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "baseline_source_required")
        ok = self.osc.post(f"/v1/projects/{p}/indicators",
                           {"indicator_id": cat[0]["id"], "baseline": 10,
                            "baseline_source": "Levantamento inicial da organização, março de 2026",
                            "baseline_date": "2026-03-01", "target": 40})
        self.assertEqual(ok.status, 201, ok)

    def test_a_target_without_a_baseline_is_still_allowed(self):
        """Meta sem linha de base é legítima: nem todo indicador parte de número conhecido."""
        p = self._project(self.osc, "BR-MT-5105150")
        cat = self.osc.get("/v1/indicators/catalog").json["items"]
        if not cat:
            self.skipTest("catálogo de indicadores vazio neste ambiente")
        r = self.osc.post(f"/v1/projects/{p}/indicators",
                          {"indicator_id": cat[0]["id"], "target": 40})
        self.assertEqual(r.status, 201, r)
