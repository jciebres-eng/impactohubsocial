"""Invariantes do produto. São as afirmações que NÃO podem deixar de valer entre versões.

Cada teste aqui corresponde a uma promessa escrita na documentação:

* mesma entrada + mesmas versões ⇒ mesmo resultado (o motor é determinístico e versionado);
* plano, assinatura ou voucher NÃO influenciam match nem diagnóstico;
* bloqueio não é compensado por pontuação: bloqueado nunca sai como elegível;
* declaração não vira evidência verificada;
* evidência velha reduz CONFIANÇA, não pontuação;
* hash de documento gerado não muda; histórico não é reescrito;
* trabalho idempotente rodado duas vezes produz um efeito só.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from impacto.core.evidence import (Evidence, EvidenceSet, Source, band, decay_confidence, freshness)
from impacto.engines.match import engine as ME
from tests.support import db_system, grant_premium, new_account


class EvidenceInvariants(unittest.TestCase):
    """Unidade: o vocabulário de evidência precisa impedir o erro, não só documentá-lo."""

    def test_declared_evidence_cannot_be_marked_verified(self):
        ev = Evidence(key="cnpj", source=Source.DECLARED, value="informado pela organização", verified=True)
        self.assertFalse(ev.verified, "declaração aceitou a marca de verificada")
        for src in (Source.SIGNED_DOCUMENT, Source.VERIFIED_CREDENTIAL, Source.VERIFIED_DOCUMENT):
            self.assertTrue(Evidence(key="k", source=src, value="x").verified, src)
        for src in (Source.DECLARED, Source.ABSENT, Source.INFERRED):
            self.assertFalse(Evidence(key="k", source=src, value="x").verified, src)

    def test_absent_evidence_is_never_present_and_has_no_confidence(self):
        ev = Evidence(key="k", source=Source.ABSENT, value=None)
        self.assertFalse(ev.present)
        self.assertEqual(ev.confidence(), 0.0)

    def test_freshness_decays_and_expiry_is_distinct_from_old(self):
        today = date(2026, 10, 5)
        new, _ = freshness(today, kind="default", at=today)
        old, _ = freshness(today - timedelta(days=720), kind="default", at=today)
        self.assertGreater(new, old)
        expired, why = freshness(today - timedelta(days=10), kind="default", at=today,
                                 expires_at=today - timedelta(days=1))
        self.assertEqual(expired, 0.0)
        self.assertIn("expirado", why.lower())

    def test_stale_evidence_lowers_confidence_not_the_value(self):
        today = date(2026, 10, 5)
        fresh = EvidenceSet()
        fresh.add(Evidence(key="k", source=Source.VERIFIED_DOCUMENT, value="x", observed_at=today))
        stale = EvidenceSet()
        stale.add(Evidence(key="k", source=Source.VERIFIED_DOCUMENT, value="x",
                           observed_at=today - timedelta(days=1500)))
        c_fresh, _ = decay_confidence(80.0, fresh, at=today)
        c_stale, detail = decay_confidence(80.0, stale, at=today)
        self.assertLess(c_stale, c_fresh)
        self.assertIn("confiança", detail.lower())
        # o VALOR da evidência não mudou: só a confiança nele
        self.assertEqual(stale.get("k").value, "x")

    def test_insufficient_data_is_a_band_of_its_own(self):
        self.assertEqual(band(90.0, known=1, total=10).value, "insufficient_data")
        self.assertEqual(band(90.0, known=9, total=10).value, "high")
        self.assertEqual(band(10.0, known=9, total=10).value, "insufficient_data")

    def test_better_source_wins_the_conflict(self):
        s = EvidenceSet()
        s.add(Evidence(key="capacidade", source=Source.DECLARED, value="declarado"))
        s.add(Evidence(key="capacidade", source=Source.SIGNED_DOCUMENT, value="assinado"))
        self.assertEqual(s.get("capacidade").value, "assinado")
        s.add(Evidence(key="capacidade", source=Source.DECLARED, value="tentou voltar"))
        self.assertEqual(s.get("capacidade").value, "assinado", "fonte pior sobrescreveu fonte melhor")


class MatchEngineInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.company = new_account("company", compliance="approved")
        cls.pid = cls.osc.post("/v1/projects", {
            "title": "Projeto para invariantes", "summary": "Resumo do projeto",
            "problem": "Problema com dado local.", "territory": "BR-MT", "causes": ["educacao"],
            "beneficiaries_count": 80, "budget_total_cents": 3_000_000}).json["id"]
        assert cls.osc.post(f"/v1/projects/{cls.pid}/publish").status == 200

    def _match(self, client=None):
        r = (client or self.company).get(f"/v1/projects/{self.pid}")
        self.assertEqual(r.status, 200, r)
        return r.json["match"]

    def test_same_input_and_versions_give_the_same_result(self):
        a, b = self._match(), self._match()
        for key in ("score", "eligibility", "confidence", "coverage", "features", "engine_version",
                    "weights_version", "rules_version", "taxonomy_version", "confidence_band"):
            self.assertEqual(a[key], b[key], f"resultado não determinístico em '{key}'")

    def test_plan_does_not_influence_the_result(self):
        before = self._match()
        grant_premium(self.company)
        after = self._match()
        self.assertEqual(before["score"], after["score"], "o plano mudou a pontuação")
        self.assertEqual(before["eligibility"], after["eligibility"])
        self.assertEqual(before["features"], after["features"])

    def test_every_result_carries_the_four_versions(self):
        m = self._match()
        self.assertEqual(m["engine_version"], ME.ENGINE_VERSION)
        for key in ("weights_version", "rules_version", "taxonomy_version"):
            self.assertTrue(m[key], key)

    def test_score_and_confidence_are_separate_fields(self):
        m = self._match()
        self.assertIn("confidence", m)
        self.assertIn("confidence_band", m)
        self.assertIn("coverage", m)
        # confiança NÃO é a pontuação travestida
        if m["score"] is not None:
            self.assertNotEqual(m["score"], m["confidence"])

    def test_hard_blocker_never_comes_out_eligible_and_has_no_score(self):
        """Bloqueio é regra de ELEGIBILIDADE, não peso: pontuação alta não compensa requisito não atendido."""
        funder = new_account("company", compliance="approved")
        with db_system() as c:
            c.run("INSERT INTO funder_profiles(org_id, excluded_causes) VALUES ($1, '{educacao}')"
                  " ON CONFLICT (org_id) DO UPDATE SET excluded_causes = '{educacao}'", funder.org_id)
        m = self._match(funder)
        self.assertEqual(m["eligibility"], "blocked", m)
        self.assertIsNone(m["score"], "projeto bloqueado recebeu pontuação")
        self.assertTrue(m["blockers"], "bloqueado sem bloqueio explicado")
        self.assertEqual(m["blockers"][0]["code"], "EXCLUDED_CAUSE")
        self.assertEqual(m["recommended_state"], "bloqueada")
        # e o sinal de causa, isolado, continuaria alto: é o bloqueio que manda, não a soma
        self.assertTrue(any(s["key"] == "cause" for s in m["signals"]))

    def test_explanation_always_answers_why_and_what_is_missing(self):
        m = self._match()
        for key in ("why_match", "why_not", "blockers", "risks", "missing_data", "next_action", "disclaimer",
                    "evidence", "evidence_summary", "stale_evidence"):
            self.assertIn(key, m, f"explicação sem '{key}'")
        self.assertTrue(m["disclaimer"])

    def test_signals_carry_weight_value_and_contribution(self):
        for s in self._match()["signals"]:
            self.assertIn("weight", s)
            self.assertIn("value", s)
            self.assertIn("contribution", s)
            if s["value"] is None:
                self.assertIsNone(s["contribution"], f"sinal sem dado contribuiu para a nota: {s['key']}")


class DiagnosticInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.did = cls.osc.post("/v1/diagnoses", {"title": "Diagnóstico das invariantes",
                                                  "need_statement": "Necessidade com dado."}).json["id"]

    def test_same_state_does_not_create_a_new_version(self):
        first = self.osc.post(f"/v1/diagnoses/{self.did}/versions").json
        self.assertTrue(first["created"])
        for _ in range(3):
            again = self.osc.post(f"/v1/diagnoses/{self.did}/versions").json
            self.assertFalse(again["created"], "versão criada sem nada ter mudado")
            self.assertEqual(again["version"], first["version"])

    def test_plan_does_not_influence_readiness(self):
        before = self.osc.get("/v1/readiness").json
        grant_premium(self.osc)
        after = self.osc.get("/v1/readiness").json
        self.assertEqual(before["current_state"]["completeness"], after["current_state"]["completeness"])
        self.assertEqual([g["code"] for g in before["gaps"]], [g["code"] for g in after["gaps"]])

    def test_analysis_never_invents_a_value_where_there_is_no_evidence(self):
        d = self.osc.get("/v1/readiness").json
        known = {k for k, ev in d["evidence"].items() if ev["present"]}
        for u in d["unknown"]:
            self.assertNotIn(u["code"], known)
        for m in d["missing_evidence"]:
            self.assertNotIn(m["key"], known)

    def test_recommendation_is_marked_as_recommendation(self):
        d = self.osc.get("/v1/readiness").json
        self.assertIn("decisão é humana", d["disclaimer"].lower())
        for a in d["recommended_actions"]:
            self.assertEqual(a["origin"], "system_identified")


class IdempotencyInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.pid = cls.osc.post("/v1/projects", {
            "title": "Projeto idempotente", "summary": "Resumo", "problem": "Problema.", "territory": "BR-MT",
            "causes": ["educacao"], "beneficiaries_count": 20, "budget_total_cents": 500_000}).json["id"]

    def test_risk_scan_twice_produces_one_effect(self):
        first = self.osc.post(f"/v1/projects/{self.pid}/risks/scan").json
        n1 = len(self.osc.get(f"/v1/projects/{self.pid}/risks").json["items"])
        second = self.osc.post(f"/v1/projects/{self.pid}/risks/scan").json
        n2 = len(self.osc.get(f"/v1/projects/{self.pid}/risks").json["items"])
        self.assertEqual(n1, n2)
        self.assertTrue(first["identified"])
        self.assertEqual(second["identified"], [])

    def test_repeated_transition_to_the_same_status_is_not_recorded_twice(self):
        self.osc.post(f"/v1/projects/{self.pid}/transitions", {"to_status": "diagnosing"})
        again = self.osc.post(f"/v1/projects/{self.pid}/transitions", {"to_status": "diagnosing"})
        self.assertEqual(again.status, 200, again)
        self.assertFalse(again.json["changed"])
        history = self.osc.get(f"/v1/projects/{self.pid}/lifecycle").json["history"]
        self.assertEqual(len([h for h in history if h["to_status"] == "diagnosing"]), 1)

    def test_generated_document_hash_does_not_change(self):
        tid = next(t["id"] for t in self.osc.get("/v1/document-templates?status=published").json["items"]
                   if t["code"] == "plano_monitoramento_base")
        tpl = self.osc.get(f"/v1/document-templates/{tid}").json
        aid = self.osc.post("/v1/document-assemblies", {"template_id": tid, "title": "Plano idempotente",
                                                        "project_id": self.pid}).json["id"]
        values = {f["key"]: "Conteúdo do campo " + f["label"] for f in tpl["fields"]
                  if f["required"] and not f["derived_from"]}
        self.osc.put(f"/v1/document-assemblies/{aid}", {"values": values})
        g = self.osc.post(f"/v1/document-assemblies/{aid}/generate", {"format": "pdf"}).json
        doc = self.osc.get(f"/v1/documents/{g['document_id']}").json
        self.assertEqual(doc["sha256"], g["sha256"])
        with db_system() as c, self.assertRaises(Exception):
            c.run("UPDATE documents SET sha256 = $2 WHERE id = $1", g["document_id"], "0" * 64)
        self.assertEqual(self.osc.get(f"/v1/documents/{g['document_id']}").json["sha256"], g["sha256"])

    def test_snapshot_of_an_unchanged_project_has_the_same_hash(self):
        a = self.osc.post(f"/v1/projects/{self.pid}/snapshots", {"label": "um"}).json
        b = self.osc.post(f"/v1/projects/{self.pid}/snapshots", {"label": "dois"}).json
        self.assertEqual(a["state_sha256"], b["state_sha256"],
                         "o mesmo estado produziu hashes diferentes — o retrato não é comparável")
