"""Oito jornadas de ponta a ponta pela API real. Cada jornada é um caminho que uma pessoa percorre de verdade.

Não há atalho de banco para "chegar no estado": cada passo é a chamada que a interface fará. Quando um passo depende
de terceiro não contratado, a jornada registra a RECUSA explícita como resultado esperado — é isso que a plataforma
entrega hoje, e dizer outra coisa seria mentir.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import (PASSWORD, Client, db_system, grant_premium, last_signature_code, last_token_for,
                           new_account)


def _project_body(title: str, **extra) -> dict:
    return {"title": title, "summary": "Resumo do projeto da jornada",
            "problem": "Problema descrito com dado do território.",
            "objectives": "Ampliar o acesso a atividade socioeducativa.",
            "methodology": "Oficinas semanais com registro de presença.",
            "territory": "BR-MT", "causes": ["educacao"], "beneficiaries_count": 120,
            "beneficiaries_description": "Famílias atendidas pelo CRAS", "budget_total_cents": 5_000_000, **extra}


class Journey(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        grant_premium(cls.osc)

    def colleague(self) -> Client:
        em = f"revisor-{uuid.uuid4().hex[:8]}@teste.org"
        self.assertEqual(self.osc.post("/v1/org/invitations", {"email": em, "role": "manager"}).status, 201)
        peer = Client()
        peer.post("/v1/auth/register", {"email": em, "password": PASSWORD, "full_name": "Revisora",
                                        "accept_terms": True})
        peer.login(em, PASSWORD)
        self.assertEqual(peer.post("/v1/auth/accept-invite", {"token": last_token_for(em, "/convite")}).status, 200)
        return peer

    def template(self, code: str) -> dict:
        t = next(t for t in self.osc.get("/v1/document-templates?status=published").json["items"]
                 if t["code"] == code)
        return self.osc.get(f"/v1/document-templates/{t['id']}").json

    def fill(self, aid: str, tpl: dict, client: Client | None = None) -> None:
        """Preenche o que a equipe digita e anexa a evidência de cada campo que exige comprovação."""
        client = client or self.osc
        values = {f["key"]: f"Conteúdo informado para {f['label']}" for f in tpl["fields"]
                  if f["required"] and not f["derived_from"]}
        if values:
            self.assertEqual(client.put(f"/v1/document-assemblies/{aid}", {"values": values}).status, 200)
        evidence = {}
        for f in tpl["fields"]:
            if not (f["requires_evidence"] and f["required"]):
                continue
            up = client.upload("/v1/documents", filename=f"{f['key']}.txt",
                               content=f"Comprovação de {f['label']}".encode(),
                               fields={"doc_type": "outro", "title": f"Evidência — {f['label']}"[:200]})
            self.assertEqual(up.status, 201, up)
            evidence[f["key"]] = up.json["id"]
        if evidence:
            self.assertEqual(client.put(f"/v1/document-assemblies/{aid}", {"evidence": evidence}).status, 200)


class J1IdeaToVerifiedDocument(Journey):
    """1. Ideia → diagnóstico → projeto → documento montado → assinado → verificado publicamente."""

    def test_journey(self):
        idea = self.osc.post("/v1/ideas", {"title": "Reforço escolar no contraturno",
                                           "problem": "Defasagem de aprendizagem no 5º ano.",
                                           "hypothesis": "Acompanhamento diário recupera leitura.",
                                           "audience": "90 estudantes da rede municipal",
                                           "territory": "BR-MT", "ods": [4], "stage": "shaping"})
        self.assertEqual(idea.status, 201, idea)
        iid = idea.json["id"]

        promoted = self.osc.post(f"/v1/ideas/{iid}/promote", {"title": "Reforço escolar no contraturno",
                                                              "summary": "Acompanhamento diário de leitura"})
        self.assertEqual(promoted.status, 201, promoted)
        pid = promoted.json["id"]
        self.assertEqual(self.osc.get(f"/v1/ideas/{iid}").json["promoted_project_id"], pid)

        diag = self.osc.post("/v1/diagnoses", {"title": "Diagnóstico do reforço escolar", "project_id": pid,
                                               "need_statement": "Defasagem medida pela avaliação municipal.",
                                               "objective": "Recuperar leitura no 5º ano."})
        self.assertEqual(diag.status, 201, diag)
        did = diag.json["id"]
        v1 = self.osc.post(f"/v1/diagnoses/{did}/versions")
        self.assertEqual(v1.status, 201, v1)
        self.assertTrue(self.osc.get(f"/v1/diagnoses/{did}/actions").json["items"])

        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "diagnosing"}).status, 200)
        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "structuring"}).status, 200)

        # o projeto que nasceu de uma ideia ainda não tem objetivo, metodologia nem prazo: a equipe completa agora,
        # e o modelo técnico puxa esses valores do PROJETO (campo derivado), sem redigitação
        self.assertEqual(self.osc.patch(f"/v1/projects/{pid}", {
            "objectives": "Recuperar a fluência de leitura de 90 estudantes do 5º ano.",
            "methodology": "Dois encontros semanais no contraturno, com avaliação bimestral.",
            "beneficiaries_count": 90, "budget_total_cents": 4_000_000,
            "starts_on": "2027-02-01", "ends_on": "2027-12-15"}).status, 200)

        tpl = self.template("projeto_tecnico_base")
        asm = self.osc.post("/v1/document-assemblies", {"template_id": tpl["id"], "title": "Projeto técnico — reforço",
                                                        "project_id": pid, "diagnosis_id": did})
        self.assertEqual(asm.status, 201, asm)
        aid = asm.json["id"]
        blocked = self.osc.post(f"/v1/document-assemblies/{aid}/generate", {"format": "pdf"})
        self.assertEqual(blocked.status, 409, "documento incompleto não pode ser gerado")

        self.fill(aid, tpl)
        state = self.osc.get(f"/v1/document-assemblies/{aid}").json["evaluation"]
        self.assertTrue(state["can_generate"], state)

        gen = self.osc.post(f"/v1/document-assemblies/{aid}/generate", {"format": "pdf"})
        self.assertEqual(gen.status, 200, gen)
        doc = gen.json["document_id"]

        peer = self.colleague()
        ok = peer.post(f"/v1/document-assemblies/{aid}/review", {"approve": True,
                                                                 "note": "Revisado: metas e orçamento conferidos."})
        self.assertEqual(ok.status, 200, ok)

        self.osc.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc})
        code = last_signature_code(self.osc.email)
        sig = self.osc.post("/v1/signatures", {"subject_type": "document", "subject_id": doc,
                                               "role": "legal_representative",
                                               "statement": "Assino o projeto técnico apresentado.",
                                               "password": PASSWORD, "code": code})
        self.assertEqual(sig.status, 201, sig)
        rec = self.osc.post("/v1/verifiable-records", {"subject_type": "document", "subject_id": doc})
        self.assertEqual(rec.status, 201, rec)

        anon = Client()
        pub = anon.get(f"/v1/public/verify/{rec.json['code']}")
        self.assertEqual(pub.status, 200, pub)
        self.assertNotIn("storage_key", pub.body.decode())
        self.assertNotIn(self.osc.email, pub.body.decode())
        kinds = [e["entry_type"] for e in self.osc.get(f"/v1/projects/{pid}/timeline").json["items"]]
        for expected in ("idea_promoted", "project_created", "status_changed", "diagnosis_created",
                         "document_generated", "document_approved"):
            self.assertIn(expected, kinds, f"a jornada não deixou rastro de '{expected}'")
        self.assertTrue(self.osc.get(f"/v1/projects/{pid}/timeline/integrity").json["valid"])


class J2ProjectToFunding(Journey):
    """2. Projeto publicado → financiador avalia → candidatura → aprovação → execução acompanhada."""

    def test_journey(self):
        pid = self.osc.post("/v1/projects", _project_body("Projeto para captação")).json["id"]
        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/milestones",
                                       {"title": "Etapa 1", "amount_cents": 2_500_000,
                                        "description": "Oficinas do primeiro semestre"}).status, 201)
        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/publish").status, 200)

        company = new_account("company", compliance="approved")
        grant_premium(company)
        view = company.get(f"/v1/projects/{pid}")
        self.assertEqual(view.status, 200, view)
        m = view.json["match"]
        self.assertIn(m["eligibility"], ("eligible", "needs_review", "blocked"))
        self.assertTrue(m["disclaimer"])
        fb = company.post(f"/v1/match-runs/{m['match_run_id']}/feedback",
                          {"feedback": "contacted", "reason": "Vamos conversar com a organização."})
        self.assertEqual(fb.status, 201, fb)

        feed = company.get("/v1/feed/projects?limit=25")
        self.assertEqual(feed.status, 200, feed)
        self.assertIn("scoring_window", feed.json)

        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "funding"}).status, 200)
        lc = self.osc.get(f"/v1/projects/{pid}/lifecycle").json
        self.assertEqual(lc["status"], "funding")
        self.assertEqual(lc["phase"], "open")
        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "in_execution"}).status, 200)
        self.assertEqual(self.osc.get(f"/v1/projects/{pid}/lifecycle").json["phase"], "execution")


class J3EmptyOrganizationFillsEvidence(Journey):
    """3. Organização sem dado → tudo desconhecido → preenche evidência → completude sobe e a versão registra."""

    def test_journey(self):
        osc = new_account("osc", compliance="approved")
        grant_premium(osc)
        before = osc.get("/v1/readiness").json
        self.assertTrue(before["unknown"], "organização vazia deveria ter pontos desconhecidos")
        self.assertTrue(before["gaps"])

        # o diagnóstico nasce LIGADO ao projeto: é o projeto que carrega orçamento, cronograma e marcos
        pid = osc.post("/v1/projects", {"title": "Projeto da organização nova",
                                        "summary": "Resumo inicial", "problem": "Problema a descrever melhor.",
                                        "territory": "BR-MT"}).json["id"]
        did = osc.post("/v1/diagnoses", {"title": "Primeiro diagnóstico", "project_id": pid,
                                         "need_statement": "Necessidade declarada pela equipe."}).json["id"]
        v1 = osc.post(f"/v1/diagnoses/{did}/versions").json
        self.assertTrue(v1["created"])
        gaps_v1 = {g["code"] for g in osc.get(f"/v1/diagnoses/{did}/analysis").json["gaps"]}
        self.assertIn("no_milestones", gaps_v1)

        # a equipe fecha lacunas: orçamento, cronograma, marco e estatuto no cofre
        self.assertEqual(osc.patch(f"/v1/projects/{pid}", {
            "objectives": "Atender 90 famílias com acompanhamento mensal.",
            "methodology": "Visitas domiciliares quinzenais com registro.",
            "beneficiaries_count": 90, "beneficiaries_description": "Famílias indicadas pelo CRAS",
            "budget_total_cents": 3_000_000, "starts_on": "2027-03-01", "ends_on": "2027-12-20"}).status, 200)
        self.assertEqual(osc.post(f"/v1/projects/{pid}/milestones",
                                  {"title": "Etapa inicial", "amount_cents": 1_000_000}).status, 201)
        up = osc.upload("/v1/documents", filename="estatuto.txt", content=b"Estatuto social",
                        fields={"doc_type": "estatuto_social", "title": "Estatuto"})
        self.assertEqual(up.status, 201, up)

        v2 = osc.post(f"/v1/diagnoses/{did}/versions").json
        self.assertTrue(v2["created"], "a versão nova não registrou a evidência acrescentada")
        self.assertGreater(v2["completeness"], v1["completeness"])
        closed = set(v2["changes"]["closed_gaps"])
        self.assertTrue(closed, v2["changes"])
        for code in ("no_milestones", "no_budget", "no_schedule", "no_objective", "no_methodology", "missing_statute"):
            self.assertIn(code, closed, f"a lacuna '{code}' continuou aberta depois de ser resolvida")
        # e a versão 1 continua dizendo o que valia naquele dia
        self.assertEqual(osc.get(f"/v1/diagnoses/{did}/versions/1").json["completeness"], v1["completeness"])
        after = osc.get("/v1/readiness").json
        self.assertLess(len(after["unknown"]), len(before["unknown"]))


class J4AssemblyReviewAndSignature(Journey):
    """4. Montagem bloqueada → completa → gerada → quatro olhos → assinatura com as duas camadas."""

    def test_journey(self):
        pid = self.osc.post("/v1/projects", _project_body("Projeto do plano de trabalho",
                                                          starts_on="2027-01-15", ends_on="2027-12-20")).json["id"]
        tpl = self.template("plano_trabalho_mrosc")
        self.assertIn("art. 22", tpl["source_note"])
        aid = self.osc.post("/v1/document-assemblies", {"template_id": tpl["id"], "title": "Plano de trabalho",
                                                        "project_id": pid}).json["id"]
        first = self.osc.get(f"/v1/document-assemblies/{aid}").json
        self.assertEqual(first["status"], "blocked")
        self.assertTrue(first["evaluation"]["missing"])

        self.fill(aid, tpl)
        gen = self.osc.post(f"/v1/document-assemblies/{aid}/generate", {"format": "docx"})
        self.assertEqual(gen.status, 200, gen)

        mine = self.osc.post(f"/v1/document-assemblies/{aid}/review", {"approve": True, "note": "Aprovo o meu."})
        self.assertEqual(mine.status, 409)
        peer = self.colleague()
        self.assertEqual(peer.post(f"/v1/document-assemblies/{aid}/review",
                                   {"approve": False, "note": "Falta detalhar o cronograma de desembolso."}).status, 200)
        self.assertEqual(self.osc.get(f"/v1/document-assemblies/{aid}").json["status"], "rejected")
        # recusada volta a ser editável, e a edição a devolve para 'em preenchimento'
        self.assertEqual(self.osc.put(f"/v1/document-assemblies/{aid}",
                                      {"title": "Plano de trabalho (revisado)"}).status, 200)
        gen2 = self.osc.post(f"/v1/document-assemblies/{aid}/generate", {"format": "docx"})
        self.assertEqual(gen2.status, 200, gen2)
        self.assertEqual(peer.post(f"/v1/document-assemblies/{aid}/review",
                                   {"approve": True, "note": "Cronograma corrigido. Aprovado."}).status, 200)

        doc = gen2.json["document_id"]
        # assinatura exige as DUAS camadas: senha e código de uso único preso ao conteúdo
        sem_codigo = self.osc.post("/v1/signatures", {"subject_type": "document", "subject_id": doc,
                                                      "role": "legal_representative", "statement": "Assino.",
                                                      "password": PASSWORD, "code": "000000"})
        self.assertIn(sem_codigo.status, (401, 403, 409, 422), sem_codigo)
        self.osc.post("/v1/signatures/challenge", {"subject_type": "document", "subject_id": doc})
        code = last_signature_code(self.osc.email)
        ok = self.osc.post("/v1/signatures", {"subject_type": "document", "subject_id": doc,
                                              "role": "legal_representative",
                                              "statement": "Assino o plano de trabalho revisado.",
                                              "password": PASSWORD, "code": code})
        self.assertEqual(ok.status, 201, ok)
        prov = {p["key"]: p for p in self.osc.get("/v1/signature-providers").json["items"]}
        self.assertEqual(prov["platform_advanced"]["legal_level"], "advanced")
        self.assertEqual(prov["icp_brasil"]["state"], "unavailable")


class J5LongitudinalTracking(Journey):
    """5. Acompanhamento no tempo: retratos comparáveis, linha de tempo íntegra e indicadores por nível."""

    def test_journey(self):
        pid = self.osc.post("/v1/projects", _project_body("Projeto acompanhado no tempo")).json["id"]
        a = self.osc.post(f"/v1/projects/{pid}/snapshots", {"label": "linha de base"}).json
        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/milestones",
                                       {"title": "Etapa 1", "amount_cents": 1_500_000}).status, 201)
        cat = self.osc.get("/v1/indicators/catalog?limit=5").json["items"]
        if cat:
            ind = self.osc.post(f"/v1/projects/{pid}/indicators",
                                {"indicator_id": cat[0]["id"], "baseline": 10, "target": 40})
            self.assertIn(ind.status, (200, 201), ind)
        b = self.osc.post(f"/v1/projects/{pid}/snapshots", {"label": "após estruturação"}).json
        self.assertNotEqual(a["state_sha256"], b["state_sha256"])
        cmp = self.osc.get(f"/v1/projects/{pid}/snapshots/compare?a={a['id']}&b={b['id']}")
        self.assertEqual(cmp.status, 200, cmp)
        self.assertTrue(cmp.json["changed"] or cmp.json["added"], cmp.json)
        state = self.osc.get(f"/v1/projects/{pid}/state").json["state"]
        self.assertIn("funding", state)
        self.assertIn("counts", state)
        self.assertTrue(self.osc.get(f"/v1/projects/{pid}/timeline/integrity").json["valid"])


class J6RiskLifecycle(Journey):
    """6. Risco: regra aponta → equipe mitiga → condição desaparece → encerramento registrado com motivo."""

    def test_journey(self):
        pid = self.osc.post("/v1/projects", _project_body("Projeto com gestão de risco")).json["id"]
        scan = self.osc.post(f"/v1/projects/{pid}/risks/scan").json
        self.assertTrue(scan["identified"])
        found = self.osc.get(f"/v1/projects/{pid}/risks").json["items"]
        self.assertTrue(all(r["origin"] == "system_identified" for r in found))

        declared = self.osc.post(f"/v1/projects/{pid}/risks",
                                 {"category": "partnership", "title": "Dependência de um único parceiro",
                                  "probability": "medium", "impact": "high",
                                  "mitigation": "Buscar segundo parceiro executor até o fim do trimestre."})
        self.assertEqual(declared.status, 201, declared)
        self.assertEqual(declared.json["severity"], "high")   # média × alto pela matriz publicada
        rid = declared.json["id"]
        self.assertEqual(self.osc.put(f"/v1/projects/{pid}/risks/{rid}",
                                      {"status": "mitigating", "probability": "low"}).status, 200)
        sem_motivo = self.osc.put(f"/v1/projects/{pid}/risks/{rid}", {"status": "resolved"})
        self.assertEqual(sem_motivo.status, 422)
        self.assertEqual(self.osc.put(f"/v1/projects/{pid}/risks/{rid}",
                                      {"status": "resolved",
                                       "resolution_note": "Segundo parceiro formalizado."}).status, 200)
        kinds = [e["entry_type"] for e in self.osc.get(f"/v1/projects/{pid}/timeline").json["items"]]
        self.assertIn("risk_created", kinds)
        self.assertIn("risk_resolved", kinds)


class J7FeedbackLoopWithoutAutomaticTraining(Journey):
    """7. Retorno humano sobre recomendação → base de calibração para a administração, sem treino automático."""

    def test_journey(self):
        pid = self.osc.post("/v1/projects", _project_body("Projeto do ciclo de retorno")).json["id"]
        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/publish").status, 200)
        company = new_account("company", compliance="approved")
        run = company.get(f"/v1/projects/{pid}").json["match"]
        before = run["score"], run["confidence"]
        self.assertEqual(company.post(f"/v1/match-runs/{run['match_run_id']}/feedback",
                                      {"feedback": "rejected", "reason": "Fora do foco deste ano."}).status, 201)
        after = company.get(f"/v1/projects/{pid}").json["match"]
        self.assertEqual((after["score"], after["confidence"]), before,
                         "o retorno humano mexeu no resultado do motor — não deveria")
        from tests.support import make_admin
        admin, _ = make_admin()
        ds = admin.get("/v1/admin/match/calibration")
        self.assertEqual(ds.status, 200, ds)
        self.assertIn("Nenhum treino automático", ds.json["note"])
        self.assertTrue(any(r["feedback"] == "rejected" for r in ds.json["rows"]))


class J8TwoTenantsNeverMeet(Journey):
    """8. A mesma jornada em duas organizações: nenhuma enxerga qualquer passo da outra."""

    def test_journey(self):
        a = new_account("osc", compliance="approved")
        b = new_account("osc", compliance="approved")
        grant_premium(a)
        grant_premium(b)
        ids = {}
        for who, client in (("a", a), ("b", b)):
            idea = client.post("/v1/ideas", {"title": f"Ideia da organização {who}"}).json["id"]
            pid = client.post(f"/v1/ideas/{idea}/promote", {}).json["id"]
            did = client.post("/v1/diagnoses", {"title": f"Diagnóstico {who}", "project_id": pid}).json["id"]
            client.post(f"/v1/diagnoses/{did}/versions")
            snap = client.post(f"/v1/projects/{pid}/snapshots", {"label": "base"}).json["id"]
            client.post(f"/v1/projects/{pid}/risks/scan")
            ids[who] = {"idea": idea, "project": pid, "diagnosis": did, "snapshot": snap}

        for path in (f"/v1/ideas/{ids['b']['idea']}", f"/v1/projects/{ids['b']['project']}/lifecycle",
                     f"/v1/projects/{ids['b']['project']}/timeline", f"/v1/projects/{ids['b']['project']}/risks",
                     f"/v1/diagnoses/{ids['b']['diagnosis']}/versions"):
            self.assertIn(a.get(path).status, (403, 404), path)
        self.assertEqual(len(a.get("/v1/ideas").json["items"]), 1)
        self.assertEqual(a.get("/v1/ideas").json["items"][0]["title"], "Ideia da organização a")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM ideas WHERE org_id IN ($1, $2)", a.org_id, b.org_id), 2)
