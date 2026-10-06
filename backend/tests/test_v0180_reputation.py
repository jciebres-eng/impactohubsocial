"""v0.18.0 — reputação explicável: em dimensões, sem nota única, sem decisão automática.

A frase dos documentos desta rodada que estes testes protegem:

    "NUNCA transformar o score em uma caixa-preta que determina automaticamente acesso a
     financiamento, contratação, benefícios, oportunidades ou exposição pública."

Então o que é testado aqui não é só o cálculo. É a ausência da nota única, a ausência do valor
quando falta base, a ausência de qualquer sinal comercial no módulo, o perfil sem nota do órgão
público, a inexistência de perfil público para pessoa física, e a contestação que APARECE.
"""
from __future__ import annotations

import ast
import pathlib
import unittest

from tests.support import app_tx, grant_premium, make_admin, new_account, owner_conn, server

MODULE = pathlib.Path(__file__).resolve().parents[1] / "impacto" / "impact" / "reputation.py"
LONG = ("Texto de contestação com extensão suficiente para o CHECK do banco nesta coluna, "
        "descrevendo o que está sendo contestado.")


class ReputationBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        cls.admin, _ = make_admin()


# ================================================================================================ catálogo
class CatalogTests(ReputationBase):
    def test_every_dimension_declares_what_it_does_not_measure(self):
        r = self.osc.get("/v1/reputation/dimensions")
        self.assertEqual(r.status, 200, r)
        self.assertGreaterEqual(len(r.json["items"]), 6)
        for d in r.json["items"]:
            self.assertGreaterEqual(len(d["what_it_does_not_measure"]), 20, d["code"])
            self.assertGreaterEqual(len(d["why_it_is_fair"]), 20, d["code"])
            self.assertGreaterEqual(len(d["signals_note"]), 20, d["code"])

    def test_the_catalog_says_there_is_no_single_score_and_why(self):
        j = self.osc.get("/v1/reputation/dimensions").json
        self.assertIn("ranking", j["no_single_score"])
        self.assertIn("decisão humana", j["no_automatic_decision"])

    def test_the_catalog_lists_the_signals_excluded_on_purpose(self):
        excl = " ".join(self.osc.get("/v1/reputation/dimensions").json["excluded_signals"]).lower()
        for term in ("plano", "assinatura", "pagamento", "autodeclara", "modelo de linguagem"):
            self.assertIn(term, excl)


# ================================================================================================ a ausência de nota
class NoSingleScoreTests(ReputationBase):
    def test_the_profile_has_no_aggregate_field_at_all(self):
        j = self.osc.get("/v1/reputation/me").json
        for forbidden in ("score", "overall", "rank", "rating", "stars", "total_score", "grade"):
            self.assertNotIn(forbidden, j, f"apareceu agregado: {forbidden}")
        self.assertIn("dimensions", j)

    def test_no_column_in_the_database_stores_an_aggregate_score(self):
        with app_tx(self.osc, readonly=True) as c:
            cols = [r["column_name"] for r in c.query(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name IN ('reputation_snapshots','reputation_dimensions')")]
        for forbidden in ("score", "overall", "rank", "rating"):
            self.assertNotIn(forbidden, cols)

    def test_a_brand_new_organization_has_no_value_not_a_bad_one(self):
        """O ponto mais importante do desenho: ausência de histórico não é nota baixa."""
        nova = new_account("osc")
        j = nova.get("/v1/reputation/me").json
        for d in j["dimensions"]:
            self.assertIsNone(d["value"], d["dimension"])
            self.assertEqual(d["band"], "insufficient", d["dimension"])
            # a dimensão de contagem explica a ausência pelo denominador que não existe; as outras,
            # pela base insuficiente — e nenhuma das duas razões é "nota baixa"
            esperado = "denominador" if d["count_only"] else "SEM"
            self.assertIn(esperado, d["reason_without_value"], d["dimension"])

    def test_the_counting_dimension_never_produces_a_value(self):
        j = self.osc.get("/v1/reputation/me").json
        contrib = next(d for d in j["dimensions"] if d["dimension"] == "contribution_to_others")
        self.assertTrue(contrib["count_only"])
        self.assertIsNone(contrib["value"])
        self.assertIn("denominador", contrib["reason_without_value"])


# ================================================================================================ sem pagar para subir
class NoPayToRankTests(ReputationBase):
    def test_the_module_never_mentions_plan_payment_or_entitlement(self):
        """Varredura no código, não promessa em documento (mesma lição da ADR-042)."""
        src = MODULE.read_text(encoding="utf-8")
        tree = ast.parse(src)
        proibidos = ("entitlement", "plan_key", "subscription", "platform_charges", "invoice",
                     "billable", "price", "premium")
        achados = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                low = node.value.lower()
                # a docstring pode citar a proibição; o que não pode é consulta ou identificador
                if any(t in low for t in proibidos) and ("select" in low or "from " in low):
                    achados.append(node.value[:80])
            if isinstance(node, ast.Name | ast.Attribute):
                nome = (node.id if isinstance(node, ast.Name) else node.attr).lower()
                if any(t in nome for t in proibidos):
                    achados.append(nome)
        self.assertEqual(achados, [], f"sinal comercial no motor de reputação: {achados}")

    def test_premium_does_not_change_a_single_dimension(self):
        antes = self.other.get("/v1/reputation/me").json["dimensions"]
        grant_premium(self.other)
        depois = self.other.get("/v1/reputation/me").json["dimensions"]
        chave = lambda ds: [(d["dimension"], d["value"], d["confidence"], d["band"]) for d in ds]  # noqa: E731
        self.assertEqual(chave(antes), chave(depois))


# ================================================================================================ quem recebe o quê
class AudienceTests(ReputationBase):
    def test_a_public_body_gets_a_governance_profile_without_scores(self):
        gov = new_account("government", compliance="approved")
        j = gov.get("/v1/reputation/me").json
        self.assertEqual(j["profile_type"], "governance_and_transparency")
        self.assertIn("política pública", j["note"])
        for d in j["dimensions"]:
            self.assertIsNone(d["value"], d["dimension"])
            self.assertIn("Órgão público", d["reason_without_value"])

    def test_a_natural_person_has_no_public_reputation_profile(self):
        pessoa = new_account("individual")
        r = self.osc.get(f"/v1/organizations/{pessoa.org_id}/reputation")
        self.assertEqual(r.status, 403, r)
        self.assertEqual(r.json["code"], "no_public_profile_for_person")

    def test_a_natural_person_can_see_their_own_profile_marked_private(self):
        pessoa = new_account("individual")
        j = pessoa.get("/v1/reputation/me").json
        self.assertTrue(j["private"])
        self.assertIn("não tem reputação pública", j["note"])

    def test_an_authenticated_organization_can_read_another_organizations_profile(self):
        r = self.other.get(f"/v1/organizations/{self.osc.org_id}/reputation")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["profile_type"], "organization_dimensions")


# ================================================================================================ explicabilidade
class ExplainabilityTests(ReputationBase):
    def test_every_dimension_shows_how_it_was_computed_and_what_went_in(self):
        for d in self.osc.get("/v1/reputation/me").json["dimensions"]:
            self.assertGreaterEqual(len(d["how"]), 20, d["dimension"])
            self.assertIsInstance(d["inputs"], dict)
            self.assertIn("observations", d)
            self.assertIn("verified_observations", d)
            self.assertIn("self_declared_observations", d)
            self.assertIn("min_observations", d)

    def test_the_engine_version_travels_with_the_answer(self):
        self.assertTrue(self.osc.get("/v1/reputation/me").json["engine_version"]
                        .startswith("reputation-dimensions@"))

    def test_verified_never_exceeds_observations(self):
        for d in self.osc.get("/v1/reputation/me").json["dimensions"]:
            self.assertLessEqual(d["verified_observations"], d["observations"], d["dimension"])

    def test_a_value_only_appears_once_the_minimum_of_observations_is_reached(self):
        osc = new_account("osc", compliance="approved")
        d0 = next(d for d in osc.get("/v1/reputation/me").json["dimensions"]
                  if d["dimension"] == "institutional_formality")
        self.assertIsNone(d0["value"])
        # compliance aprovado é 1 observação; a dimensão exige 2
        self.assertGreaterEqual(d0["min_observations"], 2)


# ================================================================================================ linha do tempo
class TimelineTests(ReputationBase):
    def test_a_snapshot_is_recorded_per_dimension_and_is_append_only(self):
        r = self.osc.post("/v1/reputation/snapshots", {})
        self.assertEqual(r.status, 201, r)
        self.assertGreaterEqual(r.json["recorded"], 6)
        tl = self.osc.get(f"/v1/organizations/{self.osc.org_id}/reputation/timeline")
        self.assertEqual(tl.status, 200, tl)
        self.assertGreaterEqual(len(tl.json["items"]), 6)
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception):
                c.run("UPDATE reputation_snapshots SET value = 100 WHERE org_id = $1",
                      self.osc.org_id)

    def test_the_application_cannot_insert_a_snapshot_directly(self):
        """A escrita passa por app_record_reputation(): não há caminho que invente valor."""
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception):
                c.run("INSERT INTO reputation_snapshots(org_id, dimension, value, confidence,"
                      " band, observations, verified_observations, engine_version)"
                      " VALUES ($1,'claim_integrity',100,100,'high',10,10,'mao')", self.osc.org_id)

    def test_a_value_without_an_observation_to_support_it_is_refused(self):
        oc = owner_conn()
        with self.assertRaises(Exception) as ctx:
            oc.run("SELECT app_record_reputation($1,'claim_integrity',95,90,'high',0,0,0,"
                   "'{}'::jsonb,'x')", self.osc.org_id)
        self.assertIn("sem observação", str(ctx.exception))

    def test_an_insufficient_band_can_never_carry_a_value(self):
        oc = owner_conn()
        with self.assertRaises(Exception):
            oc.run("SELECT app_record_reputation($1,'claim_integrity',80,10,'insufficient',5,5,0,"
                   "'{}'::jsonb,'x')", self.osc.org_id)


# ================================================================================================ contestação
class DisputeTests(ReputationBase):
    def _open(self, client=None, dimension: str = "claim_integrity"):
        c = client or self.osc
        r = c.post("/v1/reputation/disputes", {
            "dimension": dimension, "what_is_contested": LONG,
            "expected_correction": "Esperamos que a dimensão deixe de contar a alegação retirada."})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def test_an_open_dispute_appears_on_the_profile_next_to_the_dimension(self):
        cliente = new_account("osc", compliance="approved")
        self._open(cliente, "delivery_record")
        j = cliente.get("/v1/reputation/me").json
        self.assertEqual(j["open_disputes"], 1)
        alvo = next(d for d in j["dimensions"] if d["dimension"] == "delivery_record")
        self.assertEqual(len(alvo["contested"]), 1)
        self.assertEqual(alvo["contested"][0]["status"], "open")

    def test_an_unknown_dimension_cannot_be_contested(self):
        r = self.osc.post("/v1/reputation/disputes", {
            "dimension": "nota_geral", "what_is_contested": LONG,
            "expected_correction": "Queremos contestar uma dimensão que não existe."})
        self.assertEqual(r.json["code"], "unknown_dimension", r)

    def test_an_organization_cannot_resolve_its_own_dispute(self):
        did = self._open()
        r = self.osc.post(f"/v1/admin/reputation/disputes/{did}/resolution", {
            "outcome": "corrected", "rationale": LONG, "what_changed": "Mudamos o cálculo."})
        self.assertIn(r.status, (403, 404), r)

    def test_claiming_a_correction_requires_saying_what_changed(self):
        did = self._open()
        r = self.admin.post(f"/v1/admin/reputation/disputes/{did}/resolution", {
            "outcome": "corrected", "rationale": LONG})
        self.assertEqual(r.json["code"], "what_changed_required", r)

    def test_a_correction_creates_a_new_point_instead_of_rewriting_the_old_one(self):
        cliente = new_account("osc", compliance="approved")
        cliente.post("/v1/reputation/snapshots", {})
        antes = len(cliente.get(
            f"/v1/organizations/{cliente.org_id}/reputation/timeline").json["items"])
        did = self._open(cliente)
        r = self.admin.post(f"/v1/admin/reputation/disputes/{did}/resolution", {
            "outcome": "corrected", "rationale": LONG,
            "what_changed": "A dimensão passou a desconsiderar alegação retirada."})
        self.assertEqual(r.status, 201, r)
        self.assertIn("ponto novo", r.json["note"])
        depois = len(cliente.get(
            f"/v1/organizations/{cliente.org_id}/reputation/timeline").json["items"])
        self.assertGreater(depois, antes)

    def test_a_resolution_happens_once_and_is_append_only(self):
        did = self._open()
        self.assertEqual(self.admin.post(f"/v1/admin/reputation/disputes/{did}/resolution", {
            "outcome": "no_change", "rationale": LONG}).status, 201)
        again = self.admin.post(f"/v1/admin/reputation/disputes/{did}/resolution", {
            "outcome": "corrected", "rationale": LONG, "what_changed": "Segunda tentativa."})
        self.assertEqual(again.json["code"], "already_resolved", again)
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception):
                c.run("UPDATE reputation_disputes SET what_is_contested = 'outro' WHERE id = $1",
                      did)

    def test_the_resolution_is_readable_by_whoever_contested(self):
        cliente = new_account("osc", compliance="approved")
        did = self._open(cliente, "evidence_discipline")
        self.admin.post(f"/v1/admin/reputation/disputes/{did}/resolution", {
            "outcome": "no_change", "rationale": "Mantido: a medição citada não foi validada por "
                                                 "organização diferente, como a regra exige."})
        item = next(d for d in cliente.get("/v1/reputation/disputes").json["items"]
                    if d["id"] == did)
        self.assertEqual(item["status"], "resolved")
        self.assertIn("não foi validada", item["rationale"])


# ================================================================================================ job
class JobTests(ReputationBase):
    def test_the_timeline_job_is_registered_and_skips_organizations_without_a_basis(self):
        from impacto import jobs as J
        self.assertIn("reputation_timeline", [n for n, _ in J.JOBS])
        out = J.reputation_timeline(server()["state"])
        self.assertGreater(out["organizations"], 0)
        # organizações sem nenhuma observação não geram ponto: linha do tempo de quem não tem base
        # é ruído com aparência de dado
        self.assertLessEqual(out["recorded"], out["organizations"])


# ================================================================================================ a trava que o banco pegou
class InsufficientConfidenceTests(ReputationBase):
    def test_a_dimension_with_enough_observations_but_low_verification_publishes_no_value(self):
        """Caso real, encontrado pela restrição do banco durante a implementação.

        Havia observações suficientes e verificação por terceiro baixa, e o perfil publicava um
        valor que a própria faixa de confiança dizia não sustentar. `insufficient_has_no_value`
        recusou a gravação, e a recusa estava certa: quem conserta é o cálculo, não a restrição.
        """
        osc = new_account("osc", compliance="approved")
        pid = osc.post("/v1/projects", {
            "title": "Projeto com despesas sem comprovante",
            "summary": "Projeto para exercitar confiança baixa com observações suficientes.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5103403", "causes": ["educacao"],
            "beneficiaries_count": 50, "budget_total_cents": 1_000_000}).json["id"]
        oc = owner_conn()
        for i in range(6):
            oc.run("INSERT INTO expenses(project_id, org_id, description, amount_cents, paid_on)"
                   " VALUES ($1,$2,$3,10000,current_date)", pid, osc.org_id, f"Despesa {i}")
        d = next(x for x in osc.get("/v1/reputation/me").json["dimensions"]
                 if x["dimension"] == "financial_transparency")
        self.assertGreaterEqual(d["observations"], d["min_observations"])
        self.assertEqual(d["band"], "insufficient")
        self.assertIsNone(d["value"])
        self.assertIn("Confiança insuficiente", d["reason_without_value"])
        # e o snapshot grava, porque valor e faixa agora concordam
        self.assertEqual(osc.post("/v1/reputation/snapshots", {}).status, 201)
