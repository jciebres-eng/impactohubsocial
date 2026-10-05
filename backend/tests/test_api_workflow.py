"""Jornada completa via API real: cadastro → compliance → edital → match → candidatura assistida → triagem →
diligência → aprovação (com conflito de interesse) → aporte → execução → despesas/evidências → prestação de contas →
encerramento → ledger íntegro → relatórios. Também: edital externo e validação/assinatura por profissional."""
import unittest
from datetime import date, timedelta

from tests.support import PASSWORD, Client, db_system, grant_premium, make_admin, new_account, server

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
REQUIRED = ["estatuto_social", "cnd_federal"]


def setup_osc(osc: Client):
    r = osc.patch("/v1/org", {"founded_on": "2016-05-01", "description": "OSC de teste", "causes": ["educacao", "cultura"],
                              "uf": "MT", "ibge_code": "5105259", "ods": [4]})
    assert r.status == 200, r
    future = (date.today() + timedelta(days=200)).isoformat()
    for dt in ["estatuto_social", "ata_eleicao_diretoria", "cartao_cnpj", "cnd_federal", "crf_fgts", "cndt_trabalhista"]:
        r = osc.upload("/v1/documents", f"{dt}.pdf", PDF, {"doc_type": dt, "title": dt, "valid_until": future})
        assert r.status == 201, r


class JourneyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.admin, _ = make_admin()
        cls.osc = new_account("osc")
        grant_premium(cls.osc)
        cls.co = new_account("company")
        grant_premium(cls.co)
        setup_osc(cls.osc)

    def test_full_platform_journey(self):
        osc, co, admin = self.osc, self.co, self.admin
        # Compliance: OSC solicita, admin aprova
        r = osc.post("/v1/compliance/request-review")
        self.assertEqual(r.status, 200, r)
        kinds = {c["check_type"]: c["status"] for c in r.json["checks"]}
        self.assertEqual(kinds["cnpj_format"], "pass")
        self.assertEqual(kinds["documents_basic"], "pass")
        self.assertEqual(kinds["cnpj_registry"], "not_configured")  # honesto: sem provedor externo configurado
        queue = admin.get("/v1/admin/compliance-reviews").json["items"]
        rid = next(q["id"] for q in queue if q["org_id"] == osc.org_id)
        self.assertEqual(admin.post(f"/v1/admin/compliance-reviews/{rid}/decide", {"decision": "approved", "note": "Documentos conferidos"}).status, 200)
        self.assertEqual(osc.get("/v1/compliance").json["compliance_status"], "approved")

        # Empresa: perfil e programa próprio aberto
        self.assertEqual(co.put("/v1/org/funder-profile", {"causes": ["educacao"], "territories": ["BR-MT"], "ticket_min_cents": 100000,
                                                           "ticket_max_cents": 3000000, "required_document_types": REQUIRED}).status, 200)
        call = co.post("/v1/calls", {"title": "Programa Educação MT", "causes": ["educacao"], "territories": ["BR-MT"], "ticket_min_cents": 100000,
                                     "ticket_max_cents": 3000000, "required_document_types": REQUIRED, "min_org_age_months": 24, "status": "open",
                                     "closes_at": (date.today() + timedelta(days=30)).isoformat() + "T23:59:00Z",
                                     "requirements": [{"code": "plano", "label": "Plano de trabalho", "mandatory": True}]})
        self.assertEqual(call.status, 201, call)
        call_id = call.json["id"]

        # OSC: projeto com orçamento fracionado e publicação
        pid = osc.post("/v1/projects", {"title": "Música na Escola", "summary": "Aulas de música", "territory": "BR-MT-5105259",
                                        "causes": ["educacao", "cultura"], "ods": [4], "beneficiaries_count": 40, "urgency": "high",
                                        "indicators": [{"name": "Alunos formados", "unit": "alunos", "baseline": 0, "target": 32}]}).json["id"]
        osc.post(f"/v1/projects/{pid}/budget-items", {"description": "Violões", "quantity": 10, "unit_cost_cents": 50000, "category": "equipment"})
        osc.post(f"/v1/projects/{pid}/budget-items", {"description": "Professor", "quantity": 10, "unit_cost_cents": 100000, "category": "personnel"})
        proj = osc.get(f"/v1/projects/{pid}").json
        self.assertEqual(proj["budget_total_cents"], 1_500_000)
        self.assertEqual(osc.post(f"/v1/projects/{pid}/milestones", {"title": "Instrumentos", "amount_cents": 500000}).status, 201)
        ms2 = osc.post(f"/v1/projects/{pid}/milestones", {"title": "Aulas", "amount_cents": 1000000}).json["id"]
        self.assertEqual(osc.post(f"/v1/projects/{pid}/milestones", {"title": "Extra", "amount_cents": 1}).json["code"], "milestones_exceed_budget")
        self.assertEqual(osc.post(f"/v1/projects/{pid}/publish").status, 200)

        # Match OSC × edital: requisitos e compatibilidade explicados
        d = osc.get(f"/v1/calls/{call_id}?project_id={pid}").json
        m = d["match"]
        self.assertEqual(m["eligibility"], "needs_review")       # requisito customizado exige confirmação manual
        self.assertIsNotNone(m["score"])
        self.assertTrue(all(r["status"] == "met" for r in m["requirements"] if r["code"].startswith("doc:")))
        self.assertIn("next_action", m)
        rec = osc.get("/v1/calls/recommended").json["items"]
        self.assertIn(call_id, [x["id"] for x in rec])

        # Candidatura assistida
        app = osc.post("/v1/applications", {"call_id": call_id, "project_id": pid, "requested_cents": 1_500_000}).json
        self.assertEqual((app["origin"], app["status"]), ("osc_application", "draft"))
        aid = app["id"]
        r = osc.post(f"/v1/applications/{aid}/transition", {"to_status": "submitted"})
        self.assertEqual(r.json["code"], "checklist_incomplete")
        detail = osc.get(f"/v1/applications/{aid}").json
        steps = {s["code"]: s for s in detail["steps"]}
        self.assertEqual(steps["doc_estatuto_social"]["status"], "done")  # concluído automaticamente pelo cofre
        # Rascunho com IA (provedor local) → salvo → assinado pelo representante legal
        dr = osc.post("/v1/ai/draft", {"kind": "project_proposal", "project_id": pid, "call_id": call_id}).json
        self.assertIn("[COMPLETAR", dr["content"])
        self.assertTrue(dr["human_review_required"])
        draft_id = osc.post("/v1/drafts", {"kind": "project_proposal", "title": "Proposta", "content": dr["content"], "application_id": aid,
                                           "project_id": pid, "ai_assisted": True}).json["id"]
        self.assertEqual(osc.patch(f"/v1/applications/{aid}/steps/{steps['signature']['id']}", {"status": "done"}).json["code"], "signature_required")
        self.assertEqual(osc.post("/v1/signatures", {"subject_type": "draft", "subject_id": draft_id, "role": "legal_representative",
                                                      "statement": "Declaro que as informações são verdadeiras.", "password": "errada"}).status, 401)
        self.assertEqual(osc.post("/v1/signatures", {"subject_type": "draft", "subject_id": draft_id, "role": "legal_representative",
                                                      "statement": "Declaro que as informações são verdadeiras.", "password": PASSWORD}).status, 201)
        for code, st in steps.items():
            if st["mandatory"] and st["status"] != "done" and code not in ("submission",):
                r = osc.patch(f"/v1/applications/{aid}/steps/{st['id']}", {"status": "done"})
                self.assertEqual(r.status, 200, (code, r))
        self.assertEqual(osc.post(f"/v1/applications/{aid}/transition", {"to_status": "submitted"}).status, 200)

        # Empresa: triagem com match explicado, diligência, conflito, aprovação
        lst = co.get(f"/v1/calls/{call_id}/applications").json["items"]
        self.assertEqual(lst[0]["id"], aid)
        self.assertIn(lst[0]["match"]["eligibility"], ("eligible", "needs_review"))
        self.assertEqual(osc.post(f"/v1/applications/{aid}/transition", {"to_status": "screening"}).json["code"], "not_your_turn")
        self.assertEqual(co.post(f"/v1/applications/{aid}/transition", {"to_status": "screening"}).status, 200)
        self.assertEqual(co.post(f"/v1/applications/{aid}/transition", {"to_status": "due_diligence"}).status, 200)
        self.assertEqual(co.post(f"/v1/applications/{aid}/transition", {"to_status": "approved"}).json["code"], "conflict_declaration_required")
        co.post(f"/v1/applications/{aid}/conflict", {"has_conflict": True, "description": "Parente na diretoria"})
        self.assertEqual(co.post(f"/v1/applications/{aid}/transition", {"to_status": "approved"}).json["code"], "conflict_of_interest")
        co.post(f"/v1/applications/{aid}/conflict", {"has_conflict": False})
        self.assertEqual(co.post(f"/v1/applications/{aid}/transition", {"to_status": "approved", "note": "Aprovado"}).status, 200)

        # Aporte (sem custódia): compromisso → desembolso informado → confirmação pela OSC
        self.assertEqual(co.post(f"/v1/applications/{aid}/commitments", {"amount_cents": 2_000_000}).status, 422)  # excede orçamento (trigger)
        cm = co.post(f"/v1/applications/{aid}/commitments", {"amount_cents": 1_000_000, "milestone_id": ms2, "reference": "TED-001"})
        self.assertEqual(cm.status, 201, cm)
        cm_id = cm.json["id"]
        self.assertEqual(osc.post(f"/v1/commitments/{cm_id}/status", {"status": "disbursed"}).status, 403)  # OSC não informa desembolso
        self.assertEqual(co.post(f"/v1/commitments/{cm_id}/status", {"status": "disbursed", "reference": "PIX-123"}).status, 200)
        self.assertEqual(co.post(f"/v1/commitments/{cm_id}/status", {"status": "confirmed"}).status, 403)  # só a OSC confirma
        self.assertEqual(osc.post(f"/v1/commitments/{cm_id}/status", {"status": "confirmed"}).status, 200)
        self.assertEqual(osc.get(f"/v1/projects/{pid}").json["milestones"][1]["status"], "funded")

        # Execução: despesas com comprovante e evidências por etapa
        self.assertEqual(osc.post(f"/v1/applications/{aid}/transition", {"to_status": "in_execution"}).status, 200)
        nf = osc.upload("/v1/documents", "nf.pdf", PDF, {"doc_type": "nota_fiscal", "project_id": pid}).json["id"]
        exp = osc.post(f"/v1/projects/{pid}/expenses", {"description": "Pagamento professor", "amount_cents": 100000, "paid_on": date.today().isoformat(),
                                                         "milestone_id": ms2, "document_id": nf, "supplier_name": "Fulano ME"}).json["id"]
        ev = osc.post(f"/v1/projects/{pid}/evidences", {"kind": "attendance", "title": "Lista de presença março", "milestone_id": ms2,
                                                        "indicator_name": "Alunos formados", "indicator_value": 12}).json["id"]
        self.assertEqual(osc.post(f"/v1/evidences/{ev}/review", {"status": "accepted"}).json["code"], "wrong_org_kind")  # OSC não revisa a si mesma
        self.assertEqual(co.post(f"/v1/evidences/{ev}/review", {"status": "accepted", "note": "Ok"}).status, 200)
        self.assertEqual(co.post(f"/v1/expenses/{exp}/review", {"status": "validated"}).status, 200)
        # Empresa rastreia o recurso: comprometido → desembolsado → gasto comprovado → evidências
        port = co.get("/v1/portfolio").json
        self.assertEqual(port["totals"]["committed_cents"], 1_000_000)
        self.assertEqual(port["totals"]["validated_spent_cents"], 100000)
        self.assertEqual(port["totals"]["accepted_evidences"], 1)
        rep = co.get(f"/v1/projects/{pid}/report").json
        self.assertEqual(rep["indicators"][0]["achieved"], 12.0)
        self.assertEqual(rep["indicators"][0]["target"], 32)
        csv = co.get(f"/v1/projects/{pid}/expenses.csv")
        self.assertIn(b"Pagamento professor", csv.body)

        # Prestação de contas e encerramento
        self.assertEqual(osc.post(f"/v1/applications/{aid}/transition", {"to_status": "reporting"}).status, 200)
        self.assertEqual(co.post(f"/v1/applications/{aid}/transition", {"to_status": "closed"}).json["code"], "final_report_required")
        self.assertEqual(osc.post(f"/v1/projects/{pid}/feedbacks", {"kind": "final_report", "body": "Relatório final de execução."}).status, 201)
        self.assertEqual(co.post(f"/v1/projects/{pid}/feedbacks", {"kind": "funder_feedback", "body": "Devolutiva: ótimo trabalho.", "rating": 5}).status, 201)
        self.assertEqual(co.post(f"/v1/applications/{aid}/transition", {"to_status": "closed"}).status, 200)
        self.assertEqual(osc.get(f"/v1/projects/{pid}").json["status"], "completed")

        # Impact Ledger completo e íntegro (visível às duas partes)
        led = co.get(f"/v1/projects/{pid}/ledger").json
        self.assertTrue(led["verification"]["valid"])
        types = [e["entry_type"] for e in led["entries"]]
        for t in ("need_published", "budget_defined", "application_submitted", "application_approved", "funding_committed",
                  "disbursement_reported", "disbursement_confirmed", "expense_recorded", "evidence_submitted", "evidence_reviewed",
                  "report_submitted", "feedback_given", "project_completed", "professional_signature"):
            self.assertIn(t, types, t)
        self.assertEqual(osc.get(f"/v1/projects/{pid}/ledger").json["verification"]["entries"], len(types))
        # Linha do tempo e notificações
        tl = osc.get(f"/v1/applications/{aid}").json["timeline"]
        self.assertEqual([t["to_status"] for t in tl][-3:], ["in_execution", "reporting", "closed"])
        self.assertGreater(osc.get("/v1/notifications").json["items"].__len__(), 0)
        self.assertEqual(admin.get("/v1/admin/audit/verify").json["valid"], True)

    def test_funder_interest_flow_and_feed(self):
        osc, co = new_account("osc"), self.co
        setup_osc(osc)
        pid = osc.post("/v1/projects", {"title": "Horta Comunitária", "summary": "Horta", "territory": "BR-MT-5105259", "causes": ["educacao"],
                                        "beneficiaries_count": 20, "budget_total_cents": 500000}).json["id"]
        osc.post(f"/v1/projects/{pid}/publish")
        feed = co.get("/v1/feed/projects").json
        item = next(i for i in feed["items"] if i["project"]["id"] == pid)
        self.assertIn(item["match"]["eligibility"], ("eligible", "needs_review"))
        self.assertTrue(item["match"]["why_match"])
        self.assertEqual(co.post(f"/v1/feed/projects/{pid}/favorite").status, 200)
        self.assertTrue(co.get(f"/v1/projects/{pid}").json["favorite"])
        cmp = co.get(f"/v1/feed/compare?ids={pid},{pid}").json
        self.assertEqual(len(cmp["items"]), 2)
        aid = co.post("/v1/applications/interest", {"project_id": pid, "note": "Gostamos do projeto"}).json["id"]
        self.assertEqual(osc.get(f"/v1/applications/{aid}").json["status"], "interest")
        self.assertEqual(osc.post(f"/v1/applications/{aid}/transition", {"to_status": "due_diligence"}).status, 200)
        # Descartar com motivo remove do feed do financiador
        p2 = osc.post("/v1/projects", {"title": "Outro projeto", "summary": "x", "territory": "BR-MT", "causes": ["educacao"],
                                       "beneficiaries_count": 5, "budget_total_cents": 200000}).json["id"]
        osc.post(f"/v1/projects/{p2}/publish")
        co.post(f"/v1/feed/projects/{p2}/feedback", {"action": "dismiss", "reason": "Fora do foco"})
        ids = [i["project"]["id"] for i in co.get("/v1/feed/projects?limit=100").json["items"]]
        self.assertNotIn(p2, ids)

    def test_external_call_tracking(self):
        osc, admin = self.osc, self.admin
        r = admin.post("/v1/admin/calls", {"title": "Edital Federal Teste", "funder_name": "Ministério Teste", "sphere": "federal",
                                           "instrument": "edital", "url": "https://www.gov.br/edital-teste", "causes": ["educacao"],
                                           "territories": ["BR"], "status": "open", "managed_on_platform": False})
        self.assertEqual(r.status, 201, r)
        cid = r.json["id"]
        app = osc.post("/v1/applications", {"call_id": cid}).json
        self.assertEqual(app["origin"], "external_tracking")
        det = osc.get(f"/v1/applications/{app['id']}").json
        sub = next(s for s in det["steps"] if s["code"] == "submission")
        self.assertIn("gov.br", sub["description"])
        self.assertIsNone(det["funder_org_id"])
        for s in det["steps"]:
            if s["mandatory"] and s["status"] != "done" and s["kind"] != "signature" and s["code"] != "submission":
                osc.patch(f"/v1/applications/{app['id']}/steps/{s['id']}", {"status": "done"})
        sig = next(s for s in det["steps"] if s["kind"] == "signature")
        dr = osc.post("/v1/drafts", {"kind": "cover_letter", "title": "Carta", "content": "Carta de apresentação.", "application_id": app["id"]}).json["id"]
        osc.post("/v1/signatures", {"subject_type": "draft", "subject_id": dr, "role": "legal_representative",
                                    "statement": "Assino a carta de apresentação.", "password": PASSWORD})
        self.assertEqual(osc.patch(f"/v1/applications/{app['id']}/steps/{sig['id']}", {"status": "done"}).status, 200)
        r = osc.post(f"/v1/applications/{app['id']}/transition", {"to_status": "submitted", "external_protocol": "PROTO-2026-001"})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(osc.post(f"/v1/applications/{app['id']}/transition", {"to_status": "approved", "note": "Resultado publicado"}).status, 200)
        self.assertEqual(osc.get(f"/v1/applications/{app['id']}").json["external_protocol"], "PROTO-2026-001")

    def test_professional_validation_and_signature(self):
        osc, admin = self.osc, self.admin
        pro = new_account("provider")
        pro.put("/v1/org/provider-profile", {"services": ["Prestação de contas"], "categories": ["contador"], "territories": ["BR-MT"]})
        cred = pro.post("/v1/org/credentials", {"council": "CRC", "number": f"MT-{pro.user['id'][:6]}", "uf": "MT", "holder_name": "Contadora Teste"}).json["id"]
        dirs = osc.get("/v1/directory/professionals?category=contador").json["items"]
        self.assertIn(pro.org_id, [d["org_id"] for d in dirs])
        draft = osc.post("/v1/drafts", {"kind": "budget_justification", "title": "Justificativa", "content": "Custos conforme cotações anexas."}).json["id"]
        rid = osc.post("/v1/professional-reviews", {"professional_org_id": pro.org_id, "subject_type": "draft", "subject_id": draft,
                                                    "scope": "Revisar justificativa orçamentária"}).json["id"]
        self.assertEqual(pro.get(f"/v1/professional-reviews/{rid}").json["subject"]["content"], "Custos conforme cotações anexas.")
        self.assertEqual(pro.get(f"/v1/drafts/{draft}").status, 200)            # revisor lê o objeto da revisão
        other = new_account("provider")
        self.assertEqual(other.get(f"/v1/drafts/{draft}").status, 404)          # outro profissional, não
        self.assertEqual(pro.post(f"/v1/professional-reviews/{rid}/respond", {"status": "accepted"}).status, 200)
        r = pro.post(f"/v1/professional-reviews/{rid}/respond", {"status": "approved", "credential_id": cred})
        self.assertEqual(r.json["code"], "credential_not_verified")             # credencial autodeclarada não basta
        self.assertEqual(admin.post(f"/v1/admin/credentials/{cred}/verify", {"status": "verified", "note": "Consulta ao cadastro do CRC-MT em 04/10/2026"}).status, 200)
        self.assertEqual(pro.post(f"/v1/professional-reviews/{rid}/respond", {"status": "approved", "credential_id": cred}).status, 200)
        s = pro.post("/v1/signatures", {"subject_type": "draft", "subject_id": draft, "role": "professional", "review_id": rid,
                                        "statement": "Revisei e valido a justificativa orçamentária.", "password": PASSWORD})
        self.assertEqual(s.status, 201, s)
        v = osc.get(f"/v1/signatures/verify?subject_type=draft&subject_id={draft}").json
        self.assertTrue(v["signatures"][0]["content_unchanged"])
        self.assertTrue(v["signatures"][0]["server_seal_valid"])
        self.assertIn("CRC", v["signatures"][0]["credential"])
        self.assertEqual(osc.patch(f"/v1/drafts/{draft}", {"content": "alterado"}).json["code"], "immutable_version")
        nv = osc.post(f"/v1/drafts/{draft}/new-version")
        self.assertEqual(nv.json["version"], 2)
        pdf = osc.post(f"/v1/drafts/{draft}/export-pdf")
        self.assertEqual(pdf.status, 201)
        url = osc.post(f"/v1/documents/{pdf.json['document_id']}/download-url").json["url"]
        self.assertTrue(osc.get(url).body.startswith(b"%PDF"))


if __name__ == "__main__":
    unittest.main()
