"""v0.10.0 — Camada institucional do Terceiro Setor: natureza jurídica × qualificações × situação × elegibilidade, documentos com estado,
regras versionadas com fluxo de aprovação, match com bloqueios explicados, PI/confidencialidade e busca institucional. HTTP + PostgreSQL reais."""
from __future__ import annotations

import unittest
import uuid
from datetime import date, timedelta

from tests.support import Client, db_system, grant_premium, make_admin, new_account, server

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
TODAY = date.today()


def iso(d: date) -> str:
    return d.isoformat()


def publish_catalog_or_rule(admin_a: Client, admin_b: Client, kind: str, rid: str, consulted: bool = False):
    """Fluxo completo com DUAS pessoas: A cria (já feito), A envia, B aprova, B publica."""
    base = f"/v1/admin/institutional/{kind}/{rid}/action"
    assert admin_a.post(base, {"action": "submit"}).status == 200
    r = admin_b.post(base, {"action": "approve"})
    assert r.status == 200, r
    body = {"action": "publish"}
    if consulted:
        body["source_consulted_on"] = iso(TODAY)
    r = admin_b.post(base, body)
    assert r.status == 200, r
    return r.json


def verify_qualification(admin: Client, qid: str, *, note="Conferido no registro oficial") -> None:
    r = admin.post(f"/v1/admin/institutional/qualifications/{qid}/decide", {"decision": "verify", "note": note})
    assert r.status == 200, r


def add_qual(c: Client, qtype: str, **kw) -> str:
    body = {"qualification_type": qtype, "issuing_authority": "Ministério da Justiça", "certificate_number": f"N-{uuid.uuid4().hex[:6]}",
            "verification_url": "https://example.gov.br/consulta", **kw}
    r = c.post("/v1/institutional/qualifications", body)
    assert r.status == 201, r
    return r.json["id"]


def new_call(gov: Client, **kw) -> str:
    body = {"title": f"Edital institucional {uuid.uuid4().hex[:5]}", "sphere": "state", "status": "open", "causes": ["educacao"],
            "closes_at": iso(TODAY + timedelta(days=40)) + "T12:00:00Z", **kw}
    r = gov.post("/v1/calls", body)
    assert r.status == 201, r
    return r.json["id"]


class InstitutionalBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.admin1, _ = make_admin()
        cls.admin2, _ = make_admin()


# ===================================================================================== modelo: natureza × qualificação × perfil
class ModelTests(InstitutionalBase):
    def test_catalogs_separate_nature_qualification_profile_and_status(self):
        osc = new_account("osc")
        cat = osc.get("/v1/institutional/catalogs").json
        for k in ("legal_nature", "qualification_type", "institutional_profile", "institutional_status", "funding_modality"):
            self.assertIn(k, cat["catalogs"] if "catalogs" in cat else cat, k)
        c = cat["catalogs"] if "catalogs" in cat else cat
        natures = {i["code"] for i in c["legal_nature"]}
        quals = {i["code"] for i in c["qualification_type"]}
        self.assertTrue({"association", "foundation"} <= natures)
        self.assertTrue({"oscip", "os", "cebas"} <= quals)
        self.assertFalse(natures & quals - {"other"}, "natureza jurídica e qualificação não podem se misturar")
        # OSCIP/OS/CEBAS são qualificações, nunca naturezas
        self.assertNotIn("oscip", natures)

    def test_profile_association_and_foundation_with_cultural_profile(self):
        a = new_account("osc")
        r = a.put("/v1/institutional/profile", {"legal_nature_code": "association", "institutional_profile": "cultural", "mission": "Fomentar cultura"})
        self.assertEqual(r.status, 200, r)
        p = a.get("/v1/institutional/profile").json["organization"]
        self.assertEqual(p["legal_nature_code"], "association")
        self.assertEqual(p["institutional_profile"], "cultural")
        f = new_account("osc")
        self.assertEqual(f.put("/v1/institutional/profile", {"legal_nature_code": "foundation", "institutional_profile": "health"}).status, 200)

    def test_profile_rejects_unknown_codes_and_incompatible_kind(self):
        a = new_account("osc")
        self.assertEqual(a.put("/v1/institutional/profile", {"legal_nature_code": "inventada"}).status, 422)
        self.assertEqual(a.put("/v1/institutional/profile", {"institutional_profile": "inventado"}).status, 422)
        co = new_account("company")
        r = co.put("/v1/institutional/profile", {"legal_nature_code": "association"})
        self.assertEqual(r.status, 422)
        self.assertEqual(r.json["code"], "legal_nature_kind_mismatch")

    def test_profile_requires_admin_role_and_viewer_can_read(self):
        a = new_account("osc")
        self.assertEqual(a.get("/v1/institutional/profile").status, 200)
        anon = Client()
        self.assertEqual(anon.get("/v1/institutional/profile").status, 401)

    def test_collective_registers_without_cnpj_and_never_becomes_regular(self):
        c = Client()
        em = f"coletivo-{uuid.uuid4().hex[:8]}@teste.org"
        r = c.post("/v1/auth/register", {"email": em, "password": "Senha-Teste-Forte-2026", "full_name": "Coletivo Teste", "accept_terms": True,
                                         "organization": {"kind": "osc", "legal_name": "Coletivo Sem CNPJ", "uf": "MT", "legal_nature_code": "collective"}})
        self.assertEqual(r.status, 202, r)
        # natureza que exige CNPJ continua exigindo
        r2 = Client().post("/v1/auth/register", {"email": f"a-{uuid.uuid4().hex[:8]}@teste.org", "password": "Senha-Teste-Forte-2026", "full_name": "X Y", "accept_terms": True,
                                                 "organization": {"kind": "osc", "legal_name": "Associação sem CNPJ", "uf": "MT", "legal_nature_code": "association"}})
        self.assertEqual(r2.status, 422)
        with db_system() as d:
            row = d.one("SELECT institutional_status, cnpj FROM organizations WHERE legal_name = 'Coletivo Sem CNPJ' ORDER BY created_at DESC LIMIT 1")
        self.assertEqual(row["institutional_status"], "in_structuring")
        self.assertIsNone(row["cnpj"])


# ===================================================================================== qualificações
class QualificationTests(InstitutionalBase):
    def test_declared_is_not_verified_and_org_cannot_self_verify(self):
        a = new_account("osc")
        qid = add_qual(a, "oscip")
        lst = a.get("/v1/institutional/qualifications").json["items"]
        q = next(x for x in lst if x["id"] == qid)
        self.assertEqual(q["verification_status"], "declared")
        # a organização não tem rota para verificar e a rota administrativa a rejeita
        self.assertIn(a.post(f"/v1/admin/institutional/qualifications/{qid}/decide", {"decision": "verify", "note": "eu mesma"}).status, (401, 403))
        # nem por PATCH
        r = a.patch(f"/v1/institutional/qualifications/{qid}", {"notes": "ok"})
        self.assertEqual(r.status, 200)
        self.assertEqual(next(x for x in a.get("/v1/institutional/qualifications").json["items"] if x["id"] == qid)["verification_status"], "declared")

    def test_forged_status_fields_are_rejected(self):
        a = new_account("osc")
        r = a.post("/v1/institutional/qualifications", {"qualification_type": "oscip", "verification_status": "verified"})
        self.assertEqual(r.status, 422)

    def test_sql_direct_cannot_self_verify(self):
        from impacto.db.pool import DbContext
        from impacto.db.pq import DatabaseError
        a = new_account("osc")
        qid = add_qual(a, "oscip")
        with self.assertRaises(DatabaseError):
            with server()["state"].pool.tx(DbContext(user_id=a.user["id"], org_id=a.org_id, org_kind="osc")) as c:
                c.run("UPDATE organization_qualifications SET verification_status = 'verified' WHERE id = $1", qid)

    def test_multiple_qualifications_and_admin_verification_rules(self):
        a = new_account("osc")
        q1, q2, q3 = add_qual(a, "osc"), add_qual(a, "oscip"), add_qual(a, "cebas")
        self.assertEqual(len(a.get("/v1/institutional/qualifications").json["items"]), 3)
        base = "/v1/admin/institutional/qualifications/{}/decide"
        # sem nota
        r = self.admin1.post(base.format(q1), {"decision": "verify"})
        self.assertEqual(r.status, 422)
        self.assertEqual(r.json["code"], "verification_requirements")
        # sem autoridade e sem comprovante
        bare = a.post("/v1/institutional/qualifications", {"qualification_type": "os"}).json["id"]
        r = self.admin1.post(base.format(bare), {"decision": "verify", "note": "tentativa"})
        self.assertEqual(r.status, 422)
        self.assertIn("autoridade concedente", " ".join(r.json["details"]["missing"]))
        verify_qualification(self.admin1, q1)
        verify_qualification(self.admin1, q2)
        got = {x["qualification_type"]: x["verification_status"] for x in a.get("/v1/institutional/qualifications").json["items"]}
        self.assertEqual(got["osc"], "verified"); self.assertEqual(got["oscip"], "verified"); self.assertEqual(got["cebas"], "declared")
        # histórico append-only registra a verificação
        ev = a.get(f"/v1/institutional/qualifications/{q1}/events").json["items"]
        self.assertTrue(any(e["event"] == "verified" or e.get("to_status") == "verified" for e in ev), ev)

    def test_expired_qualification_cannot_be_verified_and_expired_not_counted(self):
        a = new_account("osc")
        qid = add_qual(a, "cebas", expiration_date=iso(TODAY - timedelta(days=5)))
        r = self.admin1.post(f"/v1/admin/institutional/qualifications/{qid}/decide", {"decision": "verify", "note": "x"})
        self.assertEqual(r.status, 422)
        self.assertIn("expirada", " ".join(r.json["details"]["missing"]))

    def test_revoke_and_reject_require_note_and_revoke_only_verified(self):
        a = new_account("osc")
        q = add_qual(a, "oscip")
        base = f"/v1/admin/institutional/qualifications/{q}/decide"
        self.assertEqual(self.admin1.post(base, {"decision": "reject"}).status, 422)
        self.assertEqual(self.admin1.post(base, {"decision": "revoke", "note": "n"}).status, 409)
        verify_qualification(self.admin1, q)
        self.assertEqual(self.admin1.post(base, {"decision": "revoke", "note": "Registro cancelado"}).status, 200)
        st = next(x for x in a.get("/v1/institutional/qualifications").json["items"] if x["id"] == q)
        self.assertEqual(st["verification_status"], "revoked")

    def test_legacy_certifications_array_becomes_declared_qualification_only(self):
        a = new_account("osc")
        r = a.patch("/v1/org", {"certifications": ["cebas"]})
        self.assertEqual(r.status, 200, r)
        items = a.get("/v1/institutional/qualifications").json["items"]
        self.assertEqual([i["verification_status"] for i in items if i["qualification_type"] == "cebas"], ["declared"])
        self.assertEqual(a.patch("/v1/org", {"certifications": ["inventada"]}).status, 422)

    def test_tenant_isolation_declared_qualifications_not_visible_to_others(self):
        a, b = new_account("osc"), new_account("osc")
        qid = add_qual(a, "oscip")
        self.assertEqual(b.patch(f"/v1/institutional/qualifications/{qid}", {"notes": "invasão"}).status, 404)
        self.assertIn(b.delete(f"/v1/institutional/qualifications/{qid}").status, (404, 409))
        self.assertNotIn(qid, [x["id"] for x in b.get("/v1/institutional/qualifications").json["items"]])
        from impacto.db.pool import DbContext
        with server()["state"].pool.tx(DbContext(user_id=b.user["id"], org_id=b.org_id, org_kind="osc")) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM organization_qualifications WHERE id = $1", qid), 0)

    def test_verified_qualification_is_public_declared_is_not(self):
        a, v = new_account("osc"), new_account("company")
        q = add_qual(a, "oscip")
        pub = v.get(f"/v1/institutional/orgs/{a.org_id}").json
        self.assertEqual(pub["verified_qualifications"], [])
        verify_qualification(self.admin1, q)
        pub = v.get(f"/v1/institutional/orgs/{a.org_id}").json
        self.assertEqual([x["type"] for x in pub["verified_qualifications"]], ["oscip"])

    def test_verified_with_validated_document_instead_of_url(self):
        a = new_account("osc")
        d = a.upload("/v1/documents", "oscip.pdf", PDF, {"doc_type": "certidao_oscip", "title": "Título OSCIP"})
        self.assertEqual(d.status, 201, d)
        q = a.post("/v1/institutional/qualifications", {"qualification_type": "oscip", "issuing_authority": "MJSP", "protocol": "P-1", "document_id": d.json["id"]}).json["id"]
        r = self.admin1.post(f"/v1/admin/institutional/qualifications/{q}/decide", {"decision": "verify", "note": "doc"})
        self.assertEqual(r.status, 422, "documento ainda não validado e sem URL")


# ===================================================================================== documentos
class DocumentStateTests(InstitutionalBase):
    def test_states_absent_pending_validated_rejected_expired(self):
        a = new_account("osc")
        docs = a.get("/v1/institutional/documents").json
        self.assertTrue(docs["missing_base"], "sem documentos: todos os básicos ausentes")
        self.assertTrue(all(i["state"] == "absent" for i in docs["items"] if i["base"]))
        base = docs["base_documents"][0]
        up = a.upload("/v1/documents", "d.pdf", PDF, {"doc_type": base, "title": "Doc", "valid_until": iso(TODAY + timedelta(days=200))})
        self.assertEqual(up.status, 201, up)
        did = up.json["id"]
        st = next(i for i in a.get("/v1/institutional/documents").json["items"] if i["doc_type"] == base)
        self.assertEqual(st["state"], "pending_validation")
        self.assertEqual(st["state_label"], "PENDENTE DE VALIDAÇÃO")
        # a organização não valida o próprio documento
        self.assertIn(a.post(f"/v1/admin/institutional/documents/{did}/validate", {"decision": "validate"}).status, (401, 403))
        # fila administrativa só traz arquivos já aprovados no antivírus; força o estado do scan no teste
        with db_system() as d:
            d.run("UPDATE documents SET status = 'clean' WHERE id = $1", did)
        # a fila é filtrável por organização (a fila geral cresce com o uso e paginar não é o assunto deste teste)
        q = self.admin1.get(f"/v1/admin/institutional/documents?org_id={a.org_id}").json["items"]
        self.assertIn(did, [x["id"] for x in q])
        self.assertEqual(self.admin1.post(f"/v1/admin/institutional/documents/{did}/validate", {"decision": "reject"}).status, 422)  # exige motivo
        self.assertEqual(self.admin1.post(f"/v1/admin/institutional/documents/{did}/validate", {"decision": "validate"}).status, 200)
        st = next(i for i in a.get("/v1/institutional/documents").json["items"] if i["doc_type"] == base)
        self.assertEqual(st["state_label"], "VALIDADO")
        # expira
        with db_system() as d:
            d.run("UPDATE documents SET valid_until = $2 WHERE id = $1", did, TODAY - timedelta(days=1))
        st = next(i for i in a.get("/v1/institutional/documents").json["items"] if i["doc_type"] == base)
        self.assertEqual(st["state_label"], "EXPIRADO")
        # rejeitado
        up2 = a.upload("/v1/documents", "e.pdf", PDF, {"doc_type": docs["base_documents"][1], "title": "Outro"})
        d2 = up2.json["id"]
        with db_system() as d:
            d.run("UPDATE documents SET status = 'clean' WHERE id = $1", d2)
        self.assertEqual(self.admin1.post(f"/v1/admin/institutional/documents/{d2}/validate", {"decision": "reject", "note": "Ilegível"}).status, 200)
        st = next(i for i in a.get("/v1/institutional/documents").json["items"] if i["doc_type"] == docs["base_documents"][1])
        self.assertEqual(st["state_label"], "REJEITADO")

    def test_expired_document_cannot_be_validated(self):
        a = new_account("osc")
        up = a.upload("/v1/documents", "v.pdf", PDF, {"doc_type": "certidao_negativa_federal", "title": "CND", "valid_until": iso(TODAY + timedelta(days=5))})
        did = up.json["id"]
        with db_system() as d:
            d.run("UPDATE documents SET status = 'clean', valid_until = $2 WHERE id = $1", did, TODAY - timedelta(days=2))
        r = self.admin1.post(f"/v1/admin/institutional/documents/{did}/validate", {"decision": "validate"})
        self.assertEqual(r.status, 409)

    def test_sql_direct_cannot_self_validate_document(self):
        from impacto.db.pool import DbContext
        from impacto.db.pq import DatabaseError
        a = new_account("osc")
        did = a.upload("/v1/documents", "v.pdf", PDF, {"doc_type": "estatuto_social", "title": "Estatuto"}).json["id"]
        with self.assertRaises(DatabaseError):
            with server()["state"].pool.tx(DbContext(user_id=a.user["id"], org_id=a.org_id, org_kind="osc")) as c:
                c.run("UPDATE documents SET validation_status = 'validated' WHERE id = $1", did)


# ===================================================================================== regras e fluxo editorial
class RuleWorkflowTests(InstitutionalBase):
    def _rule(self, code: str, **kw):
        body = {"code": code, "name": "Exige OSCIP verificada", "scope_type": "modality", "scope_ref": "incentive_law",
                "requirement": {"type": "qualification_all", "values": ["oscip"]}, "source_citation": "Legislação aplicável — conferir texto vigente",
                "source_url": "https://www.planalto.gov.br/", "confidence": "medium", "needs_professional_validation": True, **kw}
        return self.admin1.post("/v1/admin/institutional/rules", body)

    def test_rule_requires_source_and_known_catalog_values(self):
        code = f"R-{uuid.uuid4().hex[:6].upper()}"
        self.assertEqual(self._rule(code, source_citation="ab").status, 422)
        self.assertEqual(self._rule(code, requirement={"type": "qualification_all", "values": ["inventada"]}).status, 422)
        self.assertEqual(self._rule(code, requirement={"type": "xyz"}).status, 422)
        self.assertEqual(self._rule(code, scope_type="global", scope_ref="x").status, 422)
        self.assertEqual(self._rule(code, scope_type="modality", scope_ref="nao_existe").status, 422)
        self.assertEqual(self._rule(code, requirement={"type": "qualification_all", "values": ["oscip"], "extra": 1}).status, 422)

    def test_four_eyes_creator_cannot_approve_and_unpublished_rules_not_visible(self):
        code = f"R-{uuid.uuid4().hex[:6].upper()}"
        r = self._rule(code)
        self.assertEqual(r.status, 201, r)
        rid = r.json["id"]
        a = new_account("osc")
        self.assertNotIn(code, [x["code"] for x in a.get("/v1/institutional/rules").json["items"]])
        act = f"/v1/admin/institutional/rules/{rid}/action"
        self.assertEqual(self.admin1.post(act, {"action": "approve"}).status, 409)          # ainda é rascunho
        self.assertEqual(self.admin1.post(act, {"action": "submit"}).status, 200)
        self.assertEqual(self.admin1.post(act, {"action": "approve"}).json["code"], "second_reviewer_required")
        self.assertEqual(self.admin2.post(act, {"action": "approve"}).status, 200)
        r2 = self.admin2.post(act, {"action": "publish"})
        self.assertEqual(r2.json["code"], "source_required")                               # sem data de consulta
        self.assertEqual(self.admin2.post(act, {"action": "publish", "source_consulted_on": iso(TODAY)}).status, 200)
        pub = {x["code"]: x for x in a.get("/v1/institutional/rules").json["items"]}
        self.assertIn(code, pub)
        self.assertEqual(pub[code]["version"], 1)
        self.assertTrue(pub[code]["source_citation"])

    def test_new_version_keeps_old_until_published_and_archives_previous(self):
        code = f"R-{uuid.uuid4().hex[:6].upper()}"
        rid = self._rule(code).json["id"]
        publish_catalog_or_rule(self.admin1, self.admin2, "rules", rid, consulted=True)
        v2 = self.admin1.post(f"/v1/admin/institutional/rules/{rid}/new-version", {"code": code, "name": "Exige OSCIP (v2)", "scope_type": "modality", "scope_ref": "incentive_law",
                                                                                    "requirement": {"type": "qualification_all", "values": ["oscip", "cebas"]},
                                                                                    "source_citation": "Atualização da fonte", "needs_professional_validation": True})
        self.assertEqual(v2.status, 201, v2)
        self.assertEqual(v2.json["version"], 2)
        a = new_account("osc")
        pub = {x["code"]: x for x in a.get("/v1/institutional/rules").json["items"]}
        self.assertEqual(pub[code]["version"], 1, "a v1 continua valendo até a v2 ser publicada")
        publish_catalog_or_rule(self.admin1, self.admin2, "rules", v2.json["id"], consulted=True)
        pub = {x["code"]: x for x in a.get("/v1/institutional/rules").json["items"]}
        self.assertEqual(pub[code]["version"], 2)
        allv = [x for x in self.admin1.get("/v1/admin/institutional/rules?limit=100").json["items"] if x["code"] == code]
        self.assertEqual(sorted((x["version"], x["status"]) for x in allv), [(1, "archived"), (2, "published")])

    def test_catalog_badge_cannot_claim_government_certification(self):
        r = self.admin1.post("/v1/admin/institutional/catalog", {"catalog": "badge", "code": "selo_oficial", "label": "Certificado pelo governo", "description": "x",
                                                                 "attributes": {"scope": "organization", "criterion": "org_verified", "validity_days": 365},
                                                                 "source_citation": "Critério interno"})
        self.assertEqual(r.status, 422)
        self.assertEqual(r.json["code"], "misleading_badge")
        r = self.admin1.post("/v1/admin/institutional/catalog", {"catalog": "badge", "code": "sem_criterio", "label": "Algo", "description": "x",
                                                                 "attributes": {"scope": "organization", "criterion": "inventado"}, "source_citation": "Critério interno"})
        self.assertEqual(r.status, 422)

    def test_institutional_status_catalog_is_fixed_and_nonadmins_blocked(self):
        r = self.admin1.post("/v1/admin/institutional/catalog", {"catalog": "institutional_status", "code": "novo", "label": "Novo", "attributes": {}})
        self.assertEqual(r.status, 422)
        a = new_account("osc")
        for p in ("/v1/admin/institutional/rules", "/v1/admin/institutional/catalog", "/v1/admin/institutional/overview"):
            self.assertIn(a.get(p).status, (401, 403))

    def test_admin_requires_mfa_for_institutional_actions(self):
        weak, _ = make_admin(mfa=False)
        r = weak.get("/v1/admin/institutional/overview")
        self.assertIn(r.status, (401, 403))

    def test_org_status_decision_is_human_justified_and_audited(self):
        a = new_account("osc")
        r = self.admin1.post(f"/v1/admin/institutional/organizations/{a.org_id}/status", {"status": "irregular"})
        self.assertEqual(r.status, 422)       # exige justificativa
        r = self.admin1.post(f"/v1/admin/institutional/organizations/{a.org_id}/status", {"status": "irregular", "note": "CNPJ inapto na consulta"})
        self.assertEqual(r.status, 200)
        self.assertEqual(a.get("/v1/institutional/profile").json["organization"]["institutional_status"], "irregular")
        snap = self.admin1.get(f"/v1/admin/institutional/organizations/{a.org_id}").json
        self.assertIn("suggested_status", snap)
        # a organização não altera a própria situação
        self.assertIn(a.post(f"/v1/admin/institutional/organizations/{a.org_id}/status", {"status": "regular", "note": "eu"}).status, (401, 403))
        from impacto.db.pool import DbContext
        from impacto.db.pq import DatabaseError
        with self.assertRaises(DatabaseError):
            with server()["state"].pool.tx(DbContext(user_id=a.user["id"], org_id=a.org_id, org_kind="osc")) as c:
                c.run("UPDATE organizations SET institutional_status = 'regular' WHERE id = $1", a.org_id)


# ===================================================================================== elegibilidade e match
class EligibilityMatchTests(InstitutionalBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.gov = new_account("government", compliance="approved")

    def _modality_rule(self) -> str:
        code = f"EL-{uuid.uuid4().hex[:6].upper()}"
        r = self.admin1.post("/v1/admin/institutional/rules", {
            "code": code, "name": "Exige OSCIP verificada para parceria", "scope_type": "modality", "scope_ref": "partnership_term",
            "requirement": {"type": "qualification_all", "values": ["oscip"]}, "source_citation": "Lei nº 13.019/2014 — conferir texto vigente",
            "source_url": "https://www.planalto.gov.br/", "confidence": "medium", "needs_professional_validation": False})
        self.assertEqual(r.status, 201, r)
        publish_catalog_or_rule(self.admin1, self.admin2, "rules", r.json["id"], consulted=True)
        return code

    def test_call_with_declared_legal_nature_and_maturity_blocks_with_explanation(self):
        call = new_call(self.gov, accepted_legal_natures=["foundation"], funding_modality="grant", min_maturity=2)
        a = new_account("osc", compliance="approved")
        a.put("/v1/institutional/profile", {"legal_nature_code": "association"})
        r = a.post("/v1/institutional/eligibility", {"subject_type": "call", "subject_id": call})
        self.assertEqual(r.status, 200, r)
        res = r.json
        self.assertEqual(res["state"], "not_eligible")
        self.assertTrue(res["state_label"])
        self.assertTrue(any(x["code"] == "call:legal_nature" and x["status"] == "unmet" for x in res["requirements"]))
        self.assertIn("evaluation_id", res)
        self.assertIn("rules_digest", res)
        m = a.get(f"/v1/calls/{call}").json["match"]
        self.assertEqual(m["eligibility"], "blocked")
        msgs = " ".join(b["message"] for b in m["blockers"])
        self.assertIn("Match bloqueado porque o requisito", msgs)
        self.assertIn("não foi comprovado", msgs)

    def test_no_rules_means_pending_never_invented_eligibility(self):
        a = new_account("osc")
        r = a.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "sponsorship"}).json
        self.assertEqual(r["state"], "pending")
        self.assertIn("Não foi possível confirmar", r["summary"])
        self.assertEqual(a.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "inventada"}).status, 422)

    def test_published_rule_flow_ineligible_then_eligible_after_verification(self):
        self._modality_rule()
        a = new_account("osc", compliance="approved")
        res = a.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "partnership_term"}).json
        self.assertEqual(res["state"], "not_eligible")
        self.assertTrue(res["missing_to_become_eligible"])
        self.assertTrue(res["requirements"][0]["source"]["citation"])
        q = add_qual(a, "oscip")
        res = a.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "partnership_term"}).json
        self.assertIn(res["state"], ("pending", "probably_eligible"), "declarada ≠ verificada")
        verify_qualification(self.admin1, q)
        res = a.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "partnership_term"}).json
        self.assertEqual(res["state"], "eligible", res)
        hist = a.get("/v1/institutional/eligibility").json["items"]
        self.assertGreaterEqual(len(hist), 3)
        # vencimento torna o requisito vencido → não elegível
        with db_system() as d:
            d.run("UPDATE organization_qualifications SET expiration_date = $2 WHERE id = $1", q, TODAY - timedelta(days=1))
        res = a.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "partnership_term"}).json
        self.assertEqual(res["state"], "not_eligible")

    def test_professional_validation_state_when_rule_needs_it(self):
        code = f"PV-{uuid.uuid4().hex[:6].upper()}"
        r = self.admin1.post("/v1/admin/institutional/rules", {
            "code": code, "name": "Regra legal com validação profissional", "scope_type": "modality", "scope_ref": "management_contract",
            "requirement": {"type": "qualification_all", "values": ["os"]}, "source_citation": "Lei nº 9.637/1998 — conferir", "needs_professional_validation": True})
        publish_catalog_or_rule(self.admin1, self.admin2, "rules", r.json["id"], consulted=True)
        a = new_account("osc")
        q = add_qual(a, "os")
        verify_qualification(self.admin1, q)
        res = a.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "management_contract"}).json
        self.assertEqual(res["state"], "needs_professional_validation")

    def test_blocked_match_for_unmet_published_rule_attached_to_call_modality(self):
        self._modality_rule()
        call = new_call(self.gov, funding_modality="partnership_term")
        a = new_account("osc", compliance="approved")
        m = a.get(f"/v1/calls/{call}").json["match"]
        self.assertEqual(m["eligibility"], "blocked")
        self.assertTrue(any(b["code"].startswith("INST_") for b in m["blockers"]))
        q = add_qual(a, "oscip")
        verify_qualification(self.admin1, q)
        m = a.get(f"/v1/calls/{call}").json["match"]
        self.assertFalse(any(b["code"].startswith("INST_") for b in m["blockers"]), m["blockers"])

    def test_plan_never_changes_eligibility_or_match(self):
        self._modality_rule()
        a, b = new_account("osc", compliance="approved"), new_account("osc", compliance="approved")
        grant_premium(b)
        call = new_call(self.gov, funding_modality="partnership_term")
        ra = a.post("/v1/institutional/eligibility", {"subject_type": "call", "subject_id": call}).json
        rb = b.post("/v1/institutional/eligibility", {"subject_type": "call", "subject_id": call}).json
        self.assertEqual(ra["state"], rb["state"])
        self.assertEqual([x["status"] for x in ra["requirements"]], [x["status"] for x in rb["requirements"]])

    def test_only_funders_evaluate_other_orgs(self):
        a, b = new_account("osc"), new_account("osc")
        r = a.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "grant", "org_id": b.org_id})
        self.assertEqual(r.status, 403)
        co = new_account("company")
        r = co.post("/v1/institutional/eligibility", {"subject_type": "modality", "subject_id": "grant", "org_id": b.org_id})
        self.assertEqual(r.status, 200, r)

    def test_funder_required_qualification_blocks_project_match(self):
        co = new_account("company", compliance="approved")
        grant_premium(co)
        r = co.put("/v1/org/funder-profile", {"required_qualifications": ["oscip"], "accepted_legal_natures": ["association"], "min_maturity": 1, "causes": ["educacao"]})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["required_qualifications"], ["oscip"])
        osc = new_account("osc", compliance="approved")
        osc.put("/v1/institutional/profile", {"legal_nature_code": "association"})
        pid = osc.post("/v1/projects", {"title": "Projeto educação", "summary": "Projeto de educação para jovens do território.", "causes": ["educacao"], "territory": "BR-MT",
                                        "budget_total_cents": 5000000, "beneficiaries_count": 100}).json["id"]
        osc.post(f"/v1/projects/{pid}/publish")
        m = co.get(f"/v1/projects/{pid}").json["match"]
        self.assertEqual(m["eligibility"], "blocked", m)
        self.assertTrue(any("Match bloqueado porque o requisito" in b["message"] for b in m["blockers"]), m["blockers"])
        verify_qualification(self.admin1, add_qual(osc, "oscip"))
        m = co.get(f"/v1/projects/{pid}").json["match"]
        self.assertFalse(any(b["code"].startswith("INST_FUNDER") and "QUALIFICATION" in b["code"] for b in m["blockers"]), m["blockers"])

    def test_fiscal_layers_are_separated_for_incentive_calls(self):
        call = new_call(self.gov, instrument="incentive_law", funding_modality="incentive_law")
        a = new_account("osc")
        res = a.post("/v1/institutional/eligibility", {"subject_type": "call", "subject_id": call}).json
        layers = res["fiscal"]
        self.assertEqual(list(layers), ["ESTIMATIVA", "REGRA IDENTIFICADA", "POSSÍVEL ELEGIBILIDADE", "ELEGIBILIDADE DOCUMENTAL", "VALIDAÇÃO PROFISSIONAL"])
        self.assertTrue(layers["VALIDAÇÃO PROFISSIONAL"]["required"])
        self.assertFalse(layers["ESTIMATIVA"]["available"])


# ===================================================================================== maturidade e badges
class MaturityBadgeTests(InstitutionalBase):
    def test_maturity_levels_and_next_steps(self):
        a = new_account("osc")
        m = a.get("/v1/institutional/maturity").json
        self.assertEqual(m["level"], 0)
        self.assertEqual(m["next"]["level"], 1)
        self.assertTrue(all(not r["met"] and r["how_to_fix"] for r in m["next"]["requirements"]))
        self.assertTrue(m["path"])
        # preencher o perfil sobe o nível
        a.put("/v1/institutional/profile", {"legal_nature_code": "association", "institutional_profile": "osc"})
        a.patch("/v1/org", {"description": "Associação que atua com educação", "causes": ["educacao"]})
        self.assertGreaterEqual(a.get("/v1/institutional/maturity").json["level"], 1)
        ov = a.get("/v1/institutional/overview").json
        self.assertEqual(ov["participation"]["label"], "Pode participar")
        self.assertEqual(ov["can_receive"]["label"], "Pode receber este tipo específico de recurso")
        self.assertEqual(ov["needs"]["label"], "Ainda precisa cumprir requisitos")
        # sem regra publicada para a modalidade, o sistema diz que não foi possível confirmar (nunca "apto")
        for mod in ov["modalities"]:
            if not mod["evaluable"]:
                self.assertIn("não foi possível confirmar", mod["state_label"])
                self.assertNotIn(mod["modality"], [x.get("modality") for x in ov["can_receive"]["modalities"]])

    def test_badges_have_criterion_validity_and_never_claim_government_certification(self):
        a = new_account("osc")
        verify_qualification(self.admin1, add_qual(a, "oscip"))
        items = a.get("/v1/institutional/badges").json["items"]
        self.assertTrue(items)
        for b in items:
            self.assertTrue(b.get("criterion") or b.get("how") or b.get("definition"), b)
            self.assertNotIn("certificado pelo governo", str(b).lower())
        earned = [b for b in items if b.get("earned") or b.get("status") == "earned"]
        self.assertTrue(any("oscip" in str(b).lower() for b in earned), earned)


# ===================================================================================== soluções: PI, confidencialidade, busca
BASE = {"kind": "project", "stage": "running", "title": "Oficinas culturais inovadoras", "summary": "Oficinas de arte e música para jovens do território, com resultados.",
        "problem": "Falta de acesso à cultura.", "approach": "Oficinas semanais com artistas locais.", "themes": ["cultura"]}


class SolutionIPTests(InstitutionalBase):
    def setUp(self):
        self.a = new_account("osc")
        self.b = new_account("osc")
        self.tag = uuid.uuid4().hex[:6]

    def _mk(self, c: Client, **kw) -> str:
        r = c.post("/v1/solutions", {**BASE, "title": f"Oficinas {self.tag} {uuid.uuid4().hex[:4]}", **kw})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def test_publish_requires_ownership_and_authorization(self):
        sid = self._mk(self.a)
        r = self.a.post(f"/v1/solutions/{sid}/publish")
        self.assertEqual(r.status, 422)
        self.assertEqual(len(r.json["details"]["missing"]), 2)
        self.assertEqual(self.a.patch(f"/v1/solutions/{sid}", {"ownership_type": "organization"}).status, 200)
        self.assertEqual(len(self.a.post(f"/v1/solutions/{sid}/publish").json["details"]["missing"]), 1)
        self.assertEqual(self.a.patch(f"/v1/solutions/{sid}", {"authorization_publish": True, "rights_holder": "Associação X"}).status, 200)
        r = self.a.post(f"/v1/solutions/{sid}/publish")
        self.assertEqual(r.status, 200)
        self.assertIn("notice", r.json)
        g = self.a.get(f"/v1/solutions/{sid}").json
        self.assertEqual(g["ownership_type"], "organization")
        with db_system() as d:
            row = d.one("SELECT ip_declared_at, ip_declared_by::text AS by FROM solutions WHERE id = $1", sid)
        self.assertIsNotNone(row["ip_declared_at"]); self.assertEqual(row["by"], self.a.user["id"])

    def _pub(self, c, **kw) -> str:
        sid = self._mk(c, ownership_type="organization", authorization_publish=True, **kw)
        r = c.post(f"/v1/solutions/{sid}/publish")
        self.assertEqual(r.status, 200, r)
        return sid

    def test_confidential_is_invisible_to_others_but_visible_to_owner(self):
        sid = self._pub(self.a, confidentiality="confidential")
        self.assertEqual(self.b.get(f"/v1/solutions/{sid}").status, 404)
        res = self.b.post("/v1/solutions/search", {"text": f"Oficinas {self.tag}"}).json
        self.assertNotIn(sid, [i["id"] for i in res["items"]])
        self.assertEqual(self.a.get(f"/v1/solutions/{sid}").status, 200)
        from impacto.db.pool import DbContext
        with server()["state"].pool.tx(DbContext(user_id=self.b.user["id"], org_id=self.b.org_id, org_kind="osc")) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM solutions WHERE id = $1", sid), 0)

    def test_shareable_on_request_hides_content_until_author_accepts(self):
        sid = self._pub(self.a, confidentiality="shareable_on_request")
        g = self.b.get(f"/v1/solutions/{sid}").json
        self.assertEqual(g["access"]["level"], "summary_only")
        self.assertIsNone(g["approach"]); self.assertEqual(g["sharing_label"], "Compartilhável mediante autorização")
        rq = self.b.post(f"/v1/solutions/{sid}/requests", {"kind": "info", "message": "Podemos conhecer a metodologia completa?"})
        self.assertEqual(rq.status, 201, rq)
        self.assertEqual(self.b.get(f"/v1/solutions/{sid}").json["access"]["level"], "summary_only")
        inbox = self.a.get("/v1/solution-requests/received").json["items"]
        rid = next(x["id"] for x in inbox if x["id"] == rq.json["id"])
        self.assertEqual(self.a.post(f"/v1/solution-requests/{rid}/respond", {"status": "accepted", "response": "Claro"}).status, 200)
        g = self.b.get(f"/v1/solutions/{sid}").json
        self.assertEqual(g["access"]["level"], "full"); self.assertTrue(g["approach"])
        self.assertTrue(self.a.get(f"/v1/solutions/{sid}").json["is_owner"])

    def test_restricted_use_blocks_replication_adaptation_and_development(self):
        sid = self._pub(self.a, confidentiality="restricted_use", license="cc_by", allow_replication=True, allow_adaptation=True)
        self.assertEqual(self.b.get(f"/v1/solutions/{sid}").status, 200)      # consulta é permitida
        for path, body in ((f"/v1/solutions/{sid}/replications", {"target_uf": "MT", "target_city": "Cuiabá"}), (f"/v1/solutions/{sid}/adapt", {"uf": "MT"}),
                           (f"/v1/solutions/{sid}/develop", None)):
            r = self.b.post(path, body) if body is not None else self.b.post(path)
            self.assertEqual(r.status, 403, (path, r))
            self.assertEqual(r.json["code"], "restricted_use")
        # a mesma solução sem restrição é replicável
        ok = self._pub(self.a, confidentiality="shareable", license="cc_by", allow_replication=True, allow_adaptation=True)
        self.assertEqual(self.b.post(f"/v1/solutions/{ok}/replications", {"target_uf": "MT", "target_city": "Cuiabá"}).status, 201)

    def test_invalid_modalities_rejected_and_valid_ones_used_in_search(self):
        sid = self._mk(self.a, ownership_type="organization", authorization_publish=True, compatible_modalities=["grant"])
        self.assertEqual(self.a.patch(f"/v1/solutions/{sid}", {"compatible_modalities": ["inventada"]}).status, 422)
        self.assertEqual(self.a.post(f"/v1/solutions/{sid}/publish").status, 200)
        res = self.b.post("/v1/solutions/search", {"modalities": ["grant"], "text": f"Oficinas {self.tag}"}).json
        self.assertIn(sid, [i["id"] for i in res["items"]])
        res = self.b.post("/v1/solutions/search", {"modalities": ["prize"], "text": f"Oficinas {self.tag}"}).json
        self.assertNotIn(sid, [i["id"] for i in res["items"]])

    def test_search_by_verified_qualification_and_legal_nature_only(self):
        self.a.put("/v1/institutional/profile", {"legal_nature_code": "association"})
        sid = self._pub(self.a)
        q = add_qual(self.a, "oscip")
        res = self.b.post("/v1/solutions/search", {"qualifications": ["oscip"], "text": f"Oficinas {self.tag}"}).json
        self.assertNotIn(sid, [i["id"] for i in res["items"]], "OSCIP apenas declarada não pode aparecer em filtro por qualificação")
        verify_qualification(self.admin1, q)
        res = self.b.post("/v1/solutions/search", {"qualifications": ["oscip"], "text": f"Oficinas {self.tag}"}).json
        self.assertIn(sid, [i["id"] for i in res["items"]])
        item = next(i for i in res["items"] if i["id"] == sid)
        self.assertIn("oscip", item["proponent"]["verified_qualifications"])
        res = self.b.post("/v1/solutions/search", {"legal_natures": ["association"], "text": f"Oficinas {self.tag}"}).json
        self.assertIn(sid, [i["id"] for i in res["items"]])
        res = self.b.post("/v1/solutions/search", {"legal_natures": ["foundation"], "text": f"Oficinas {self.tag}"}).json
        self.assertNotIn(sid, [i["id"] for i in res["items"]])

    def test_free_text_institutional_intent(self):
        self.a.put("/v1/institutional/profile", {"legal_nature_code": "association"})
        sid = self._pub(self.a, compatible_modalities=["incentive_law"], themes=["cultura"])
        verify_qualification(self.admin1, add_qual(self.a, "oscip"))
        parsed = self.b.post("/v1/solutions/intent/parse", {"text": "OSCIP com projetos culturais"}).json
        self.assertEqual(parsed["institutional"]["qualifications"], ["oscip"])
        res = self.b.post("/v1/solutions/search", {"text": f"OSCIP com oficinas {self.tag}"}).json
        self.assertIn(sid, [i["id"] for i in res["items"]])
        self.assertEqual(res["institutional_filters"]["qualifications"], ["oscip"])
        res = self.b.post("/v1/solutions/search", {"text": f"projetos com incentivo fiscal oficinas {self.tag}"}).json
        self.assertIn(sid, [i["id"] for i in res["items"]])
        # "os" minúsculo não é a sigla OS
        p = self.b.post("/v1/solutions/intent/parse", {"text": "os jovens"}).json
        self.assertEqual(p["institutional"]["qualifications"], [])
        p = self.b.post("/v1/solutions/intent/parse", {"text": "OS saúde"}).json
        self.assertEqual(p["institutional"]["qualifications"], ["os"])

    def test_funding_readiness_is_explained_and_filter_requires_complete_ip_and_need(self):
        sid = self._pub(self.a, seeking_funding=True, needed_cents=5_000_000, budget_cents=8_000_000, compatible_modalities=["grant"])
        g = self.b.get(f"/v1/solutions/{sid}").json
        fr = g["funding_readiness"]
        self.assertIn("criteria", fr); self.assertTrue(fr["criteria"])
        self.assertIn("note", fr)
        res = self.b.post("/v1/solutions/search", {"funding_ready": True, "text": f"Oficinas {self.tag}"}).json
        for i in res["items"]:
            self.assertTrue(i["funding_readiness"]["ready"])
        plain = self._pub(self.a)
        res = self.b.post("/v1/solutions/search", {"funding_ready": True, "text": f"Oficinas {self.tag}"}).json
        self.assertNotIn(plain, [i["id"] for i in res["items"]])

    def test_sharing_labels_exposed_on_cards(self):
        sid = self._pub(self.a, confidentiality="shareable")
        res = self.b.post("/v1/solutions/search", {"text": f"Oficinas {self.tag}"}).json
        item = next(i for i in res["items"] if i["id"] == sid)
        self.assertEqual(item["sharing_label"], "Compartilhável")


class StatementAndCandidatesTests(InstitutionalBase):
    def test_statement_never_invents_qualifications(self):
        a = new_account("osc")
        st = a.get("/v1/institutional/statement").json
        text = " ".join(l["text"] for l in st["lines"])
        self.assertIn("Não foi possível confirmar", text)
        self.assertNotIn("OSCIP", text.upper().replace("NÃO FOI POSSÍVEL", ""))
        self.assertTrue(all(l["state"] in ("unknown", "declared") for l in st["lines"]))
        q = add_qual(a, "oscip")
        text = " ".join(l["text"] for l in a.get("/v1/institutional/statement").json["lines"])
        self.assertIn("declarada pela organização, ainda sem verificação", text)
        self.assertNotIn("verificada pela plataforma", text)
        verify_qualification(self.admin1, q)
        lines = a.get("/v1/institutional/statement").json["lines"]
        self.assertTrue(any(l["state"] == "verified" and "verificada pela plataforma" in l["text"] for l in lines))
        with db_system() as d:
            d.run("UPDATE organization_qualifications SET expiration_date = $2 WHERE id = $1", q, TODAY - timedelta(days=3))
        lines = a.get("/v1/institutional/statement").json["lines"]
        self.assertTrue(any(l["state"] == "expired" for l in lines))
        self.assertFalse(any(l["state"] == "verified" and "OSCIP" in l["text"] for l in lines))

    def test_candidate_rules_import_as_drafts_only_and_idempotent(self):
        r = self.admin1.post("/v1/admin/institutional/rules/import-candidates")
        self.assertEqual(r.status, 201, r)
        again = self.admin1.post("/v1/admin/institutional/rules/import-candidates").json
        self.assertEqual(again["created"], [])
        rules = {x["code"]: x for x in self.admin1.get("/v1/admin/institutional/rules?limit=100").json["items"]}
        for code in ("CAND-CONTRATO-GESTAO-OS", "CAND-PARCERIA-CNPJ"):
            self.assertEqual(rules[code]["status"], "draft")
            self.assertTrue(rules[code]["needs_professional_validation"])
        a = new_account("osc")
        self.assertNotIn("CAND-PARCERIA-CNPJ", [x["code"] for x in a.get("/v1/institutional/rules").json["items"]])
        self.assertIn(a.post("/v1/admin/institutional/rules/import-candidates").status, (401, 403))


class ArchitectureInstitutionalTests(unittest.TestCase):
    def test_institutional_engines_are_pure_and_do_not_touch_billing(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1] / "impacto" / "engines" / "institutional"
        for f in root.glob("*.py"):
            txt = f.read_text(encoding="utf-8")
            for banned in ("billing", "entitlement", "voucher", "from ...db", "import psycopg"):
                self.assertNotIn(banned, txt, f"{f.name} não pode depender de {banned}")


if __name__ == "__main__":
    unittest.main()
