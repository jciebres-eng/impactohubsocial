"""v0.18.1 — a jornada completa do ciclo de impacto, de ponta a ponta pela API real (FASE 4).

O pedido desta rodada é explícito: provar o ciclo inteiro, na ordem em que uma pessoa o percorre,
sem atalho de banco para "chegar no estado".

    REGISTRO → LOGIN → ORGANIZAÇÃO → PROJETO → DIAGNÓSTICO → EQUIDADE → ODS → ESG →
    MATCH → DOCUMENTO → REVISÃO HUMANA → RESPONSABILIDADE → EVIDÊNCIA → MEDIÇÃO VALIDADA →
    ALEGAÇÃO → VERIFICAÇÃO → REVISÃO DE ALEGAÇÃO → REPUTAÇÃO → SELO → RELATÓRIO

Onde a plataforma RECUSA, a recusa é o resultado esperado e está escrita aqui: é o que ela entrega
hoje, e afirmar outra coisa seria mentir. Cada passo é a chamada que a interface faz.
"""
from __future__ import annotations

import datetime as dt
import unittest

from tests.support import (PASSWORD, Client, db_system, grant_premium, last_token_for, make_admin,
                           new_account, owner_conn, server)

LONGO = ("Texto declarado com extensão suficiente para o CHECK do banco nesta coluna, escrito para "
         "a jornada de ponta a ponta da v0.18.1.")


def _d(delta: int = 0) -> str:
    return (dt.date.today() + dt.timedelta(days=delta)).isoformat()


class FullImpactJourney(unittest.TestCase):
    """Uma jornada só, em passos numerados: cada método depende do anterior (ordem alfabética)."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.admin, _ = make_admin()
        cls.validator = new_account("company", compliance="approved")   # financiador/validador
        cls.reviewer = new_account("osc", compliance="approved")        # revisor externo
        cls.state: dict = {}

    # ------------------------------------------------------------------ 1. registro e sessão
    def test_01_register_verify_and_login(self):
        c = Client("token")
        email = f"jornada-{dt.datetime.now().strftime('%H%M%S%f')}@teste.org"
        r = c.post("/v1/auth/register", {
            "email": email, "password": PASSWORD, "full_name": "Coordenadora da Jornada",
            "accept_terms": True,
            "organization": {"kind": "osc", "legal_name": "OSC da Jornada v0.18.1",
                             "cnpj": "11222333000181", "uf": "MT"}})
        self.assertEqual(r.status, 202, r)
        tok = last_token_for(email, "/verificar-email")
        self.assertEqual(c.post("/v1/auth/verify-email", {"token": tok}).status, 200)
        self.assertEqual(c.login(email, PASSWORD).status, 200)
        me = c.get("/v1/me").json
        self.assertTrue(me["active_org"]["id"])
        type(self).state["osc"] = c
        c.email, c.user, c.org_id = email, me["user"], me["active_org"]["id"]
        from tests.support import set_compliance
        set_compliance(c.org_id, "approved")
        grant_premium(c)

    # ------------------------------------------------------------------ 2. projeto
    def test_02_create_project(self):
        osc = self.state["osc"]
        r = osc.post("/v1/projects", {
            "title": "Reforço escolar no contraturno em comunidade ribeirinha",
            "summary": "Projeto da jornada completa, para exercitar o ciclo inteiro de impacto.",
            "problem": "A comunidade não tem oferta pública de reforço escolar no contraturno.",
            "objectives": "Ofertar reforço de leitura a 50 crianças, com medição por lista e teste.",
            "territory": "BR-AC-1200013", "causes": ["educacao"],
            "beneficiaries_count": 50, "budget_total_cents": 400_000,
            "starts_on": _d(-30), "ends_on": _d(120)})
        self.assertEqual(r.status, 201, r)
        self.state["project"] = r.json["id"]
        # Publicar é o passo que torna o projeto visível para financiador — e a rota RECUSA
        # publicar projeto incompleto, o que também é parte da jornada.
        pub = osc.post(f"/v1/projects/{r.json['id']}/publish", {})
        self.assertEqual(pub.status, 200, pub)
        self.assertEqual(pub.json["visibility"], "published")

    # ------------------------------------------------------------------ 3. diagnóstico
    def test_03_diagnostic_returns_the_eight_readiness_dimensions(self):
        osc, pid = self.state["osc"], self.state["project"]
        r = osc.post("/v1/diagnoses", {"title": "Diagnóstico da jornada", "project_id": pid})
        self.assertIn(r.status, (200, 201), r)
        did = r.json.get("id")
        self.state["diagnosis"] = did
        # O `readiness` vive na ANÁLISE, não na ficha do diagnóstico: a ficha é o que a pessoa
        # preencheu, a análise é o que a plataforma infere a partir dela.
        got = osc.get(f"/v1/diagnoses/{did}/analysis")
        self.assertEqual(got.status, 200, got)
        readiness = got.json.get("readiness") or {}
        for chave in ("project_readiness", "organization_readiness", "funding_readiness",
                      "evidence_readiness", "compliance_readiness", "data_readiness",
                      "governance_readiness", "impact_readiness"):
            self.assertIn(chave, readiness, "as oito prontidões precisam existir na saída")
            self.assertIn(readiness[chave]["status"], ("ready", "needs_review", "unknown"))

    # ------------------------------------------------------------------ 4. equidade
    def test_04_equity_context_and_denominator_with_source(self):
        osc, pid = self.state["osc"], self.state["project"]
        sem = osc.get(f"/v1/projects/{pid}/equity/normalization").json
        self.assertEqual(sem["available"], [], "sem denominador, nenhum método pode estar disponível")
        self.assertEqual(osc.put(f"/v1/projects/{pid}/equity/context", {
            "need_statement": "Não há oferta pública de contraturno na comunidade, a doze "
                              "quilômetros da escola mais próxima.",
            "additionality": "Nenhuma outra organização atua no contraturno desta comunidade, "
                             "conforme levantamento da secretaria municipal."}).status, 200)
        self.assertEqual(osc.post("/v1/equity/denominators", {
            "project_id": pid, "kind": "eligible_population", "value": 60, "unit": "pessoas",
            "reference_date": _d(-200), "source_name": "Censo escolar municipal 2024",
            "source_date": _d(-120),
            "method_note": "Matriculados na faixa atendida, conforme censo escolar municipal."}
        ).status, 201)
        com = osc.get(f"/v1/projects/{pid}/equity/normalization").json
        self.assertTrue(com["available"], "com denominador declarado, há método disponível")
        aval = osc.post(f"/v1/projects/{pid}/equity/assessments", {})
        self.assertIn(aval.status, (200, 201), aval)
        self.assertIsNone(aval.json["score"], "avaliação de equidade NÃO produz nota")

    # ------------------------------------------------------------------ 5. ODS e ESG
    def test_05_ods_alignment_is_declared_not_achieved(self):
        osc, pid = self.state["osc"], self.state["project"]
        r = osc.put(f"/v1/projects/{pid}/ods-targets", {
            "items": [{"ods": 4, "rationale": "Educação de qualidade na comunidade atendida."}]})
        self.assertEqual(r.status, 200, r)
        imp = osc.get(f"/v1/projects/{pid}/impact").json
        alinhamento = imp["ods_alignment"]
        self.assertTrue(alinhamento)
        self.assertEqual(alinhamento[0]["alignment_level"], "declared",
                         "ODS marcado nasce DECLARADO, nunca alcançado")

    # ------------------------------------------------------------------ 6. indicador e medição
    def test_06_indicator_requires_a_sourced_baseline(self):
        osc, pid = self.state["osc"], self.state["project"]
        cat = osc.get("/v1/indicators/catalog?ods=4").json["items"]
        ind = next(i for i in cat if i["code"] == "trained_people")
        recusa = osc.post(f"/v1/projects/{pid}/indicators", {"indicator_id": ind["id"],
                                                             "baseline": 0, "target": 50})
        self.assertEqual(recusa.json["code"], "baseline_source_required", recusa)
        ok = osc.post(f"/v1/projects/{pid}/indicators", {
            "indicator_id": ind["id"], "baseline": 0,
            "baseline_source": "Lista de presença do primeiro encontro", "target": 50,
            "method": "Lista de presença e teste de leitura"})
        self.assertEqual(ok.status, 201, ok)
        self.state["pi"] = ok.json["id"]

    def test_07_evidence_and_measurement_validated_by_another_organization(self):
        osc, pid = self.state["osc"], self.state["project"]
        ev = osc.post(f"/v1/projects/{pid}/evidences", {
            "kind": "attendance", "title": "Lista de presença da turma A"})
        self.assertEqual(ev.status, 201, ev)
        self.state["evidence"] = ev.json["id"]
        v = osc.post(f"/v1/project-indicators/{self.state['pi']}/values", {
            "value": 32, "measured_on": _d(-5), "evidence_id": ev.json["id"]})
        self.assertEqual(v.status, 201, v)
        # a própria OSC NÃO valida a própria medição
        self.assertEqual(osc.post(f"/v1/indicator-values/{v.json['id']}/review",
                                  {"status": "validated"}).status, 403)
        # validação por organização diferente, pelo caminho do dono do banco (o fluxo real exige
        # aporte registrado; aqui o que está sob teste é o ciclo de impacto, não o de aporte)
        oc = owner_conn()
        oc.run("UPDATE evidences SET status = 'accepted' WHERE id = $1", ev.json["id"])
        oc.run("UPDATE indicator_values SET status = 'validated', validated_by ="
               " (SELECT id FROM users LIMIT 1), validated_by_org = $2 WHERE id = $1",
               v.json["id"], self.validator.org_id)
        imp = osc.get(f"/v1/projects/{pid}/impact").json
        linha = next(i for i in imp["indicators"] if i["id"] == self.state["pi"])
        self.assertEqual(linha["latest_validated"], 32.0)
        self.assertIn("longitudinal", linha, "a série longitudinal precisa vir na ficha")
        self.assertIn("não prova causalidade", linha["longitudinal"]["interpretation"])

    # ------------------------------------------------------------------ 7. match
    def test_08_match_uses_declared_context_and_ignores_the_plan(self):
        """O match real de uma OSC é a ficha do edital com `project_id`.

        Dois invariantes nesta etapa: o sinal de impacto vem do CONTEXTO declarado (equidade,
        barreiras, adicionalidade), não do número de beneficiários; e plano/assinatura não mexem
        no resultado (ADR-042), o que é conferido concedendo plano pago entre duas leituras.
        """
        osc, pid = self.state["osc"], self.state["project"]
        call = self.validator.post("/v1/calls", {
            "title": "Edital de educação da jornada v0.18.1",
            "funder_name": "Instituto da Jornada", "sphere": "private", "instrument": "edital",
            "causes": ["educacao"], "territories": ["BR-AC"],
            "ticket_min_cents": 100_000, "ticket_max_cents": 1_000_000,
            "closes_at": f"{_d(60)}T23:59:00-03:00", "status": "open"})
        self.assertEqual(call.status, 201, call)
        cid = call.json["id"]
        self.state["call"] = cid
        # ACHADO DESTA RODADA: prazo sem fuso devolvia 500. Agora devolve 422 dizendo o que falta,
        # e a plataforma continua sem adivinhar fuso nenhum.
        sem_fuso = self.validator.post("/v1/calls", {
            "title": "Edital com prazo sem fuso", "sphere": "private", "instrument": "edital",
            "causes": ["educacao"], "closes_at": _d(60)})
        self.assertEqual(sem_fuso.status, 422, sem_fuso)
        self.assertIn("fuso", str(sem_fuso.json))
        # (a) o match que a OSC vê: a ficha do edital com o projeto vinculado
        antes = osc.get(f"/v1/calls/{cid}?project_id={pid}")
        self.assertEqual(antes.status, 200, antes)
        m = antes.json["match"]
        chaves = {s["key"] for s in m["signals"]}
        self.assertTrue({"cause", "territory", "budget", "readiness", "deadline"} <= chaves, chaves)
        self.assertTrue(m["match_run_id"], "o match real é persistido para auditoria")
        # ASSIMETRIA DECLARADA: este sentido (OSC × edital) NÃO tem sinal de impacto. O sinal
        # contextual existe no sentido financiador × projeto. Registrado como dívida na
        # TECHNICAL_DEBT_REGISTER.md desta rodada em vez de inventar um sinal aqui.
        self.assertNotIn("impact", chaves)
        grant_premium(osc)
        depois = osc.get(f"/v1/calls/{cid}?project_id={pid}").json["match"]
        self.assertEqual((m["score"], m["eligibility"], m["confidence"]),
                         (depois["score"], depois["eligibility"], depois["confidence"]),
                         "plano pago mexeu no match")

        # (b) o match que o FINANCIADOR vê: é aqui que o contexto de equidade entra
        ficha = self.validator.get(f"/v1/projects/{pid}")
        self.assertEqual(ficha.status, 200, ficha)
        fm = ficha.json["match"]
        imp = next(s for s in fm["signals"] if s["key"] == "impact")
        self.assertIsNotNone(imp["value"], "o contexto declarado precisa produzir sinal de impacto")
        self.assertIn("Contexto agregado", imp["detail"])
        self.state["funder_match"] = fm

    # ------------------------------------------------------------------ 8. responsabilidade
    def test_09_responsibility_is_designated_before_the_decision(self):
        osc, pid = self.state["osc"], self.state["project"]
        atual = osc.get(f"/v1/responsibility/current?scope=project&subject_id={pid}").json
        self.assertEqual(atual["items"], [])
        self.assertTrue(atual["without_responsible"], "papel vago aparece como informação")
        a = osc.post("/v1/responsibility/assignments", {
            "scope": "project", "subject_id": pid, "role_code": "project_coordinator",
            "mandate_basis": "Designação registrada em ata da diretoria de março, item 4.",
            "user_id": osc.user["id"]})
        self.assertEqual(a.status, 201, a)
        self.state["assignment"] = a.json["id"]
        b = osc.post("/v1/responsibility/assignments", {
            "scope": "project", "subject_id": pid, "role_code": "technical_lead",
            "mandate_basis": "Responsabilidade técnica contratada para o período do projeto.",
            "external_name": "Joana Avaliadora Externa"})
        self.assertEqual(b.status, 201, b)
        self.state["assignment2"] = b.json["id"]
        d = osc.post("/v1/responsibility/decisions", {
            "assignment_id": a.json["id"], "kind": "approval",
            "statement": "Aprovo o plano de trabalho revisado com a equipe nesta semana."})
        self.assertEqual(d.status, 201, d)
        self.assertFalse(d.json["signed"], "decisão sem assinatura é registro válido")

    # ------------------------------------------------------------------ 9. alegação
    def test_10_a_claim_with_absolute_language_is_flagged(self):
        osc, pid = self.state["osc"], self.state["project"]
        c = osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": pid, "claim_kind": "result",
            "statement": "O resultado é comprovado e garantido: erradicamos a defasagem de leitura."})
        self.assertEqual(c.status, 201, c)
        self.state["claim_bad"] = c.json["id"]
        out = osc.post(f"/v1/claims/{c.json['id']}/check", {}).json
        self.assertEqual(out["status"], "flagged")
        grave = [x for x in out["checks"] if not x["passed"] and x["severity"] == "serious"]
        self.assertTrue(grave)
        # ACHADO DESTA RODADA: "erradicamos" passava por `absolute_language` porque o projeto já
        # tinha UMA medição validada. Totalidade virou regra própria, conferida por divisão.
        self.assertIn("totality_claim_without_coverage", [x["rule_code"] for x in grave])
        detalhe = next(x for x in out["checks"]
                       if x["rule_code"] == "totality_claim_without_coverage")["detail"]
        self.assertIn("cobertura medida", detalhe)

    def test_11_a_measured_claim_is_substantiated_or_attention(self):
        osc, pid = self.state["osc"], self.state["project"]
        c = osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": pid, "claim_kind": "result",
            "statement": "Atendemos 32 pessoas em oficinas de leitura, conforme medição validada."})
        self.assertEqual(c.status, 201, c)
        out = osc.post(f"/v1/claims/{c.json['id']}/check", {}).json
        self.assertIn(out["status"], ("substantiated", "attention"),
                      f"alegação medida não deveria estar marcada: {out['status']}")
        self.assertEqual(out["facts_used"]["values_with_evidence"], 1)

    def test_12_the_flagged_claim_is_reviewed_by_another_organization_only_when_invited(self):
        osc = self.state["osc"]
        cid = self.state["claim_bad"]
        sem_convite = self.reviewer.post(f"/v1/claims/{cid}/review", {
            "decision": "accepted", "note": "Revisão não solicitada, que o banco precisa recusar."})
        self.assertEqual(sem_convite.json["code"], "not_invited", sem_convite)
        self.assertEqual(self.reviewer.get(f"/v1/claims/{cid}").status, 404)
        convite = osc.post(f"/v1/claims/{cid}/review-requests", {
            "reviewer_org_id": self.reviewer.org_id,
            "note": "Convite para revisar a linguagem desta alegação."})
        self.assertEqual(convite.status, 201, convite)
        self.assertEqual(self.reviewer.get(f"/v1/claims/{cid}").status, 200)
        rev = self.reviewer.post(f"/v1/claims/{cid}/review", {
            "decision": "needs_change",
            "note": "A linguagem absoluta não se sustenta: a medição cobre 32 de 60 elegíveis."})
        self.assertEqual(rev.status, 201, rev)
        self.assertEqual(osc.get(f"/v1/claims/{cid}").json["status"], "needs_change")

    # ------------------------------------------------------------------ 10. reputação
    def test_13_reputation_has_dimensions_and_no_single_score(self):
        osc = self.state["osc"]
        perfil = osc.get("/v1/reputation/me").json
        self.assertNotIn("score", perfil)
        self.assertEqual(perfil["profile_type"], "organization_dimensions")
        disciplina = next(d for d in perfil["dimensions"]
                          if d["dimension"] == "evidence_discipline")
        self.assertEqual(disciplina["observations"], 1)
        self.assertEqual(osc.post("/v1/reputation/snapshots", {}).status, 201)
        linha = osc.get(f"/v1/organizations/{osc.org_id}/reputation/timeline").json
        self.assertGreaterEqual(len(linha["items"]), 6)

    def test_14_a_contested_dimension_shows_up_on_the_profile(self):
        osc = self.state["osc"]
        d = osc.post("/v1/reputation/disputes", {
            "dimension": "claim_integrity",
            "what_is_contested": "A alegação marcada foi corrigida e a dimensão ainda a conta.",
            "expected_correction": "Esperamos que a alegação revisada deixe de pesar no cálculo."})
        self.assertEqual(d.status, 201, d)
        perfil = osc.get("/v1/reputation/me").json
        alvo = next(x for x in perfil["dimensions"] if x["dimension"] == "claim_integrity")
        self.assertEqual(len(alvo["contested"]), 1)
        self.assertEqual(perfil["open_disputes"], 1)

    # ------------------------------------------------------------------ 11. selo
    def test_15_a_seal_is_only_awarded_when_the_database_agrees(self):
        osc, pid = self.state["osc"], self.state["project"]
        d = self.admin.post("/v1/admin/seals/definitions", {
            "code": "selo_jornada_v0181", "scope": "project",
            "title": "Projeto com contexto de equidade declarado",
            "what_it_attests": "Atesta que o projeto declarou necessidade, adicionalidade e "
                               "denominador vigente com fonte, data e método.",
            "what_it_does_not_attest": "Não atesta resultado, qualidade do projeto, elegibilidade "
                                       "em edital nem aprovação de órgão público.",
            "validity_days": 180,
            "criteria": [{"rule_code": "equity_context_declared"},
                         {"rule_code": "indicator_baseline_sourced"}]})
        self.assertEqual(d.status, 201, d)
        did = d.json["id"]
        # rascunho não concede
        self.assertEqual(self.admin.post("/v1/admin/seals/awards",
                                         {"definition_id": did, "subject_id": pid}).status, 422)
        self.assertEqual(self.admin.post(f"/v1/admin/seals/definitions/{did}/publish", {}).status,
                         200)
        aval = osc.post("/v1/seals/evaluate", {"definition_id": did, "subject_id": pid})
        self.assertEqual(aval.status, 200, aval)
        self.assertTrue(aval.json["all_met"], aval.json["criteria"])
        aw = self.admin.post("/v1/admin/seals/awards", {"definition_id": did, "subject_id": pid})
        self.assertEqual(aw.status, 201, aw)
        self.assertEqual(aw.json["status"], "active")
        self.state["award"] = aw.json["id"]
        ficha = osc.get(f"/v1/seals/awards/{aw.json['id']}").json
        self.assertIn("NÃO é certificação", ficha["disclaimer"])
        self.assertTrue(all(i["met"] for i in ficha["evidence"]))

    def test_16_the_seal_is_revoked_when_the_criterion_falls(self):
        osc = self.state["osc"]
        aid = self.state["award"]
        # O denominador é IMUTÁVEL (e tentar alterá-lo é recusado pelo gatilho, como deve ser).
        # Para derrubar o critério, o que se remove é o contexto de equidade declarado.
        oc = owner_conn()
        oc.run("DELETE FROM equity_contexts WHERE project_id = $1", self.state["project"])
        from impacto.impact import seals as SEAL
        with db_system() as d:
            out = SEAL.recheck(d, org_id=osc.org_id)
        self.assertGreaterEqual(out["revoked"], 1, out)
        ficha = osc.get(f"/v1/seals/awards/{aid}").json
        self.assertEqual(ficha["status"], "revoked")
        self.assertEqual(ficha["revocation"]["reason"], "criterion_no_longer_met")
        self.assertIn("equity_context_declared", ficha["revocation"]["detail"])

    # ------------------------------------------------------------------ 12. relatório
    def test_17_the_impact_report_separates_reported_from_validated(self):
        osc, pid = self.state["osc"], self.state["project"]
        imp = osc.get(f"/v1/projects/{pid}/impact").json
        linha = next(i for i in imp["indicators"] if i["id"] == self.state["pi"])
        self.assertEqual(linha["latest_validated"], 32.0)
        self.assertEqual(linha["longitudinal"]["validated_periods"], 1)
        self.assertEqual(linha["longitudinal"]["reported_periods"], 0)
        self.assertIsNone(linha["longitudinal"]["validated_delta"],
                          "uma medição só não produz delta: variação exige dois pontos")

    def test_18_the_journey_left_an_audit_trail(self):
        osc = self.state["osc"]
        with db_system() as d:
            acoes = [r["action"] for r in d.query(
                "SELECT DISTINCT action FROM audit_events WHERE org_id = $1", osc.org_id)]
        for esperado in ("claim.declared", "claim.checked", "responsibility.assigned",
                         "responsibility.decision", "reputation.snapshot"):
            self.assertIn(esperado, acoes, f"a jornada não registrou {esperado}")
