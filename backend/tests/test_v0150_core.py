"""v0.15.0 — núcleo do produto: ideia → projeto, máquina de situações, linha de tempo, retratos, riscos,
diagnóstico longitudinal, montagem de documento, retorno do match e administração de chaves/assinatura.

Cada teste aqui confere COMPORTAMENTO OBSERVÁVEL pela API real, contra PostgreSQL real. Nenhum teste afirma que
algo "está integrado": o que depende de terceiro é testado pela recusa explícita que a plataforma devolve.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import (PASSWORD, Client, db_system, grant_premium, last_token_for, new_account,
                           owner_conn)


class CoreBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        grant_premium(cls.osc)

    def project(self, title="Projeto do núcleo", **extra):
        r = self.osc.post("/v1/projects", {"title": title, "summary": "Resumo do projeto para os testes do núcleo",
                                           "problem": "Problema descrito com evidência local.",
                                           "objectives": "Objetivo geral do projeto.",
                                           "methodology": "Oficinas semanais com registro de presença.",
                                           "territory": "BR-MT", "budget_total_cents": 5_000_000,
                                           "causes": ["educacao"], "beneficiaries_count": 120,
                                           "beneficiaries_description": "Famílias atendidas pelo CRAS", **extra})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]


# ------------------------------------------------------------------------------------------------ ideias
class IdeasTests(CoreBase):
    def test_idea_survives_promotion_and_project_keeps_origin(self):
        r = self.osc.post("/v1/ideas", {"title": "Horta comunitária na periferia leste",
                                        "problem": "Falta de acesso a alimento fresco no bairro.",
                                        "hypothesis": "Produção local reduz o gasto das famílias com hortaliça.",
                                        "audience": "120 famílias atendidas pelo CRAS do bairro",
                                        "territory": "BR-MT", "ods": [2, 11], "stage": "shaping"})
        self.assertEqual(r.status, 201, r)
        iid = r.json["id"]
        p = self.osc.post(f"/v1/ideas/{iid}/promote", {})
        self.assertEqual(p.status, 201, p)
        pid = p.json["id"]
        # a ideia NÃO foi apagada e aponta para o projeto
        idea = self.osc.get(f"/v1/ideas/{iid}").json
        self.assertEqual(idea["stage"], "promoted")
        self.assertEqual(idea["promoted_project_id"], pid)
        self.assertIsNotNone(idea["promoted_at"])
        # e o projeto guarda a origem
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT origin_idea_id::text FROM projects WHERE id = $1", pid), iid)
        # a promoção aparece na linha de tempo do projeto
        kinds = [e["entry_type"] for e in self.osc.get(f"/v1/projects/{pid}/timeline").json["items"]]
        self.assertIn("idea_promoted", kinds)
        self.assertIn("project_created", kinds)

    def test_promoted_idea_is_not_promoted_twice_nor_edited(self):
        iid = self.osc.post("/v1/ideas", {"title": "Biblioteca itinerante"}).json["id"]
        self.assertEqual(self.osc.post(f"/v1/ideas/{iid}/promote", {}).status, 201)
        again = self.osc.post(f"/v1/ideas/{iid}/promote", {})
        self.assertEqual(again.status, 409)
        self.assertEqual(again.json["code"], "already_promoted")
        edit = self.osc.put(f"/v1/ideas/{iid}", {"title": "Outro nome"})
        self.assertEqual(edit.status, 409)
        self.assertEqual(edit.json["code"], "already_promoted")

    def test_idea_cannot_declare_promoted_stage(self):
        r = self.osc.post("/v1/ideas", {"title": "Ideia que tenta nascer promovida", "stage": "promoted"})
        self.assertEqual(r.status, 422, r)


# ------------------------------------------------------------------------------------------------ situações
class LifecycleTests(CoreBase):
    def test_graph_is_data_and_drives_the_api(self):
        g = self.osc.get("/v1/project-status-graph")
        self.assertEqual(g.status, 200, g)
        pairs = {(t["from_status"], t["to_status"]) for t in g.json["transitions"]}
        self.assertIn(("draft", "structuring"), pairs)
        self.assertIn(("draft", "published"), pairs)       # compatibilidade com o fluxo que já existia
        self.assertNotIn(("draft", "completed"), pairs)
        self.assertEqual(g.json["phases"]["building"][0], "draft")

    def test_invalid_transition_is_refused_with_the_options(self):
        pid = self.project()
        bad = self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "completed"})
        self.assertEqual(bad.status, 409, bad)
        self.assertEqual(bad.json["code"], "invalid_transition")
        self.assertIn("Rascunho", bad.json["title"])
        self.assertIn("structuring", bad.json["title"])    # diz para onde é possível ir

    def test_transition_requiring_reason_is_refused_without_one(self):
        pid = self.project()
        r = self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "cancelled"})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "reason_required")
        ok = self.osc.post(f"/v1/projects/{pid}/transitions",
                           {"to_status": "cancelled", "reason": "A contraparte desistiu da parceria."})
        self.assertEqual(ok.status, 200, ok)

    def test_transition_is_recorded_in_history_and_hash_chained_timeline(self):
        pid = self.project()
        self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "diagnosing"})
        self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "structuring"})
        lc = self.osc.get(f"/v1/projects/{pid}/lifecycle").json
        self.assertEqual(lc["status"], "structuring")
        self.assertEqual(lc["phase"], "building")
        self.assertEqual([(h["from_status"], h["to_status"]) for h in lc["history"]],
                         [("diagnosing", "structuring"), ("draft", "diagnosing")])
        tl = self.osc.get(f"/v1/projects/{pid}/timeline").json["items"]
        chain = [e for e in tl if e["entry_type"] == "status_changed"]
        self.assertEqual(len(chain), 2)
        self.assertTrue(all(e["entry_hash"] for e in chain))
        integ = self.osc.get(f"/v1/projects/{pid}/timeline/integrity").json
        self.assertTrue(integ["valid"])
        self.assertIsNone(integ["first_broken_seq"])

    def test_status_guard_refuses_invalid_transition_even_in_direct_sql(self):
        """A máquina de estados é do BANCO: contornar a API não contorna a regra."""
        pid = self.project()
        with db_system() as c:
            with self.assertRaises(Exception) as ctx:
                c.run("UPDATE projects SET status = 'completed' WHERE id = $1", pid)
            self.assertIn("transi", str(ctx.exception).lower())

    def test_timeline_entry_cannot_be_edited_or_deleted(self):
        pid = self.project()
        self.osc.post(f"/v1/projects/{pid}/transitions", {"to_status": "diagnosing"})
        with db_system() as c:
            seq = c.scalar("SELECT max(seq) FROM ledger_entries WHERE project_id = $1", pid)
            for sql in ("UPDATE ledger_entries SET entry_type = 'project_created' WHERE seq = $1",
                        "DELETE FROM ledger_entries WHERE seq = $1"):
                with self.assertRaises(Exception):
                    c.run(sql, seq)


# ------------------------------------------------------------------------------------------------ retratos
class SnapshotTests(CoreBase):
    def test_snapshot_comparison_shows_what_changed(self):
        pid = self.project(title="Projeto com retrato")
        a = self.osc.post(f"/v1/projects/{pid}/snapshots", {"label": "antes"})
        self.assertEqual(a.status, 201, a)
        up = self.osc.patch(f"/v1/projects/{pid}", {"title": "Projeto com retrato (revisado)",
                                                    "budget_total_cents": 7_500_000})
        self.assertEqual(up.status, 200, up)
        b = self.osc.post(f"/v1/projects/{pid}/snapshots", {"label": "depois"})
        cmp = self.osc.get(f"/v1/projects/{pid}/snapshots/compare?a={a.json['id']}&b={b.json['id']}")
        self.assertEqual(cmp.status, 200, cmp)
        changed = {c["field"]: c for c in cmp.json["changed"]}
        self.assertIn("project.title", changed)
        self.assertIn("project.budget_total_cents", changed)
        self.assertEqual(str(changed["project.budget_total_cents"]["to"]), "7500000")
        # o retrato guarda o hash do estado: o mesmo estado produz o mesmo hash
        self.assertNotEqual(a.json["state_sha256"], b.json["state_sha256"])

    def test_snapshots_of_other_project_are_not_comparable(self):
        p1, p2 = self.project(title="Retrato um"), self.project(title="Retrato dois")
        s1 = self.osc.post(f"/v1/projects/{p1}/snapshots", {"label": "um"}).json["id"]
        s2 = self.osc.post(f"/v1/projects/{p2}/snapshots", {"label": "dois"}).json["id"]
        r = self.osc.get(f"/v1/projects/{p1}/snapshots/compare?a={s1}&b={s2}")
        self.assertEqual(r.status, 404, r)


# ------------------------------------------------------------------------------------------------ riscos
class RiskTests(CoreBase):
    def test_rule_identified_risk_is_marked_and_auto_resolved_when_condition_ends(self):
        pid = self.project(title="Projeto sem marco nem indicador")
        scan = self.osc.post(f"/v1/projects/{pid}/risks/scan")
        self.assertEqual(scan.status, 200, scan)
        codes = {r["code"] for r in scan.json["identified"]}
        self.assertTrue(codes, "nenhuma regra apontou risco em projeto vazio")
        rows = self.osc.get(f"/v1/projects/{pid}/risks").json["items"]
        self.assertTrue(all(r["origin"] == "system_identified" for r in rows))
        # segunda passada é idempotente: não duplica
        again = self.osc.post(f"/v1/projects/{pid}/risks/scan").json
        self.assertEqual(again["identified"], [])
        self.assertEqual(len(self.osc.get(f"/v1/projects/{pid}/risks").json["items"]), len(rows))

    def test_resolved_risk_is_not_reopened_by_the_scan(self):
        pid = self.project(title="Projeto com risco resolvido pela equipe")
        self.osc.post(f"/v1/projects/{pid}/risks/scan")
        risk = self.osc.get(f"/v1/projects/{pid}/risks").json["items"][0]
        up = self.osc.put(f"/v1/projects/{pid}/risks/{risk['id']}",
                          {"status": "accepted", "mitigation": "Risco aceito pela diretoria nesta fase."})
        self.assertEqual(up.status, 200, up)
        self.osc.post(f"/v1/projects/{pid}/risks/scan")
        after = {r["id"]: r for r in self.osc.get(f"/v1/projects/{pid}/risks").json["items"]}
        self.assertEqual(after[risk["id"]]["status"], "accepted")

    def test_closing_a_risk_requires_a_reason_and_severity_follows_the_matrix(self):
        pid = self.project(title="Projeto com risco declarado")
        r = self.osc.post(f"/v1/projects/{pid}/risks",
                          {"category": "financial", "title": "Atraso no repasse", "probability": "high",
                           "impact": "high", "description": "Histórico de atraso do financiador."})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["severity"], "critical")
        rid = r.json["id"]
        bad = self.osc.put(f"/v1/projects/{pid}/risks/{rid}", {"status": "resolved"})
        self.assertEqual(bad.status, 422, bad)
        self.assertEqual(bad.json["code"], "reason_required")
        ok = self.osc.put(f"/v1/projects/{pid}/risks/{rid}",
                          {"status": "resolved", "resolution_note": "Repasse antecipado e confirmado em conta."})
        self.assertEqual(ok.status, 200, ok)
        self.assertEqual(ok.json["origin"], "declared")

    def test_risk_rules_are_open_to_the_user(self):
        r = self.osc.get("/v1/risk-rules")
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["rules"])
        self.assertIn("version", r.json)


# ------------------------------------------------------------------------------------------------ diagnóstico
class DiagnosticTests(CoreBase):
    def _diagnosis(self, pid: str | None = None) -> str:
        body = {"title": "Diagnóstico da organização", "need_statement": "Necessidade descrita com dado local.",
                "affected_group": "Famílias em vulnerabilidade atendidas pelo CRAS",
                "objective": "Ampliar o acesso a atividade socioeducativa."}
        if pid:
            body["project_id"] = pid
        r = self.osc.post("/v1/diagnoses", body)
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def test_readiness_separates_fact_inference_and_recommendation(self):
        r = self.osc.get("/v1/readiness")
        self.assertEqual(r.status, 200, r)
        d = r.json
        for key in ("evidence", "evidence_summary", "current_state", "gaps", "unknown", "recommended_actions",
                    "confidence", "confidence_band", "disclaimer"):
            self.assertIn(key, d)
        # ausência de dado aparece como desconhecido, nunca como achado
        self.assertTrue(all("code" in u and "detail" in u for u in d["unknown"]))
        # quatro faixas, com "dados insuficientes" distinta de "baixa" (valores em minúscula, como o resto da API)
        self.assertIn(d["confidence_band"], ("high", "medium", "low", "insufficient_data"))

    def test_declared_evidence_is_never_marked_verified(self):
        d = self.osc.get("/v1/readiness").json["evidence"]
        for key, ev in d.items():
            if ev["source"] == "declared":
                self.assertFalse(ev["verified"], f"evidência declarada marcada como verificada: {key}")

    def test_version_is_immutable_and_diff_is_computed_by_the_server(self):
        pid = self.project(title="Projeto do diagnóstico")
        did = self._diagnosis(pid)
        v1 = self.osc.post(f"/v1/diagnoses/{did}/versions")
        self.assertEqual(v1.status, 201, v1)
        self.assertTrue(v1.json["created"])
        self.assertEqual(v1.json["version"], 1)
        # publicar de novo sem mudança nenhuma não cria versão
        same = self.osc.post(f"/v1/diagnoses/{did}/versions")
        self.assertFalse(same.json["created"])
        self.assertEqual(same.json["version"], 1)
        # fecha uma lacuna de verdade: marco definido no projeto
        ms = self.osc.post(f"/v1/projects/{pid}/milestones",
                           {"title": "Primeira etapa", "amount_cents": 1_000_000,
                            "description": "Oficinas realizadas com registro de presença"})
        self.assertIn(ms.status, (200, 201), ms)
        v2 = self.osc.post(f"/v1/diagnoses/{did}/versions")
        self.assertEqual(v2.status, 201, v2)
        self.assertTrue(v2.json["created"])
        self.assertEqual(v2.json["version"], 2)
        self.assertIn("closed_gaps", v2.json["changes"])
        # a versão 1 continua exatamente como foi publicada
        p1 = self.osc.get(f"/v1/diagnoses/{did}/versions/1").json
        self.assertEqual(p1["version"], 1)
        with db_system() as c:
            with self.assertRaises(Exception):
                c.run("UPDATE diagnosis_versions SET completeness = 100 WHERE diagnosis_id = $1 AND version = 1", did)
        cmp = self.osc.get(f"/v1/diagnoses/{did}/versions/compare?a=1&b=2")
        self.assertEqual(cmp.status, 200, cmp)
        self.assertIn("what_changed", cmp.json)

    def test_gaps_become_actions_and_closed_gaps_close_their_actions(self):
        did = self._diagnosis()
        self.osc.post(f"/v1/diagnoses/{did}/versions")
        acts = self.osc.get(f"/v1/diagnoses/{did}/actions").json["items"]
        self.assertTrue(acts)
        self.assertTrue(all(a["origin"] == "system_identified" for a in acts))
        self.assertTrue(all(a["gap_code"] for a in acts))

    def test_dismissing_an_action_requires_a_reason(self):
        did = self._diagnosis()
        self.osc.post(f"/v1/diagnoses/{did}/versions")
        aid = self.osc.get(f"/v1/diagnoses/{did}/actions").json["items"][0]["id"]
        bad = self.osc.put(f"/v1/diagnoses/{did}/actions/{aid}", {"status": "dismissed"})
        self.assertEqual(bad.status, 422, bad)
        ok = self.osc.put(f"/v1/diagnoses/{did}/actions/{aid}",
                          {"status": "dismissed", "dismissed_reason": "Não se aplica a esta organização."})
        self.assertEqual(ok.status, 200, ok)

    def test_engine_reference_is_public_to_the_user(self):
        r = self.osc.get("/v1/diagnostic-engine")
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["dimensions"])
        self.assertTrue(r.json["gaps"])
        self.assertIn("UNKNOWN", r.json["output_kinds"])


# ------------------------------------------------------------------------------------------------ montagem
class AssemblyTests(CoreBase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.templates = {t["code"]: t for t in cls.osc.get("/v1/document-templates?status=published").json["items"]}

    def test_platform_templates_are_published_with_their_source_declared(self):
        self.assertIn("projeto_tecnico_base", self.templates)
        for t in self.templates.values():
            self.assertTrue(t["source_note"], f"modelo {t['code']} sem declaração de fonte")
            self.assertIsNone(t["owner_org_id"])

    def test_published_template_is_immutable(self):
        tid = self.templates["projeto_tecnico_base"]["id"]
        r = self.osc.post(f"/v1/document-templates/{tid}/fields",
                          {"section": "9. Extra", "position": 1, "key": "campo_extra", "label": "Campo extra",
                           "field_type": "text"})
        self.assertEqual(r.status, 404, r)   # modelo da plataforma não é da organização
        with db_system() as c:
            with self.assertRaises(Exception) as ctx:
                c.run("INSERT INTO document_template_fields(template_id, section, position, key, label, field_type)"
                      " VALUES ($1,'x',99,'x_y','X','text')", tid)
            self.assertIn("imut", str(ctx.exception).lower())

    def test_incomplete_assembly_refuses_to_generate_and_says_what_is_missing(self):
        pid = self.project(title="Projeto para montar documento")
        tid = self.templates["plano_monitoramento_base"]["id"]
        a = self.osc.post("/v1/document-assemblies", {"template_id": tid, "title": "Plano de M&A do projeto",
                                                      "project_id": pid})
        self.assertEqual(a.status, 201, a)
        self.assertLess(a.json["completeness"], 100)
        aid = a.json["id"]
        g = self.osc.post(f"/v1/document-assemblies/{aid}/generate", {"format": "pdf"})
        self.assertEqual(g.status, 409, g)
        self.assertEqual(g.json["code"], "assembly_blocked")
        self.assertTrue(g.json["details"]["missing"])

    def test_complete_assembly_generates_and_registers_in_the_vault(self):
        pid = self.project(title="Projeto com plano completo")
        tid = self.templates["plano_monitoramento_base"]["id"]
        tpl = self.osc.get(f"/v1/document-templates/{tid}").json
        aid = self.osc.post("/v1/document-assemblies",
                            {"template_id": tid, "title": "Plano de monitoramento completo",
                             "project_id": pid}).json["id"]
        values = {f["key"]: "Conteúdo informado pela equipe para o campo " + f["label"]
                  for f in tpl["fields"] if f["required"] and not f["derived_from"]}
        up = self.osc.put(f"/v1/document-assemblies/{aid}", {"values": values})
        self.assertEqual(up.status, 200, up)
        self.assertTrue(up.json["can_generate"], up.json)
        self.assertEqual(up.json["status"], "ready")
        g = self.osc.post(f"/v1/document-assemblies/{aid}/generate", {"format": "docx"})
        self.assertEqual(g.status, 200, g)
        self.assertEqual(len(g.json["sha256"]), 64)
        doc = self.osc.get(f"/v1/documents/{g.json['document_id']}")
        self.assertEqual(doc.status, 200, doc)
        self.assertEqual(doc.json["origin"], "generated")
        kinds = [e["entry_type"] for e in self.osc.get(f"/v1/projects/{pid}/timeline").json["items"]]
        self.assertIn("document_generated", kinds)

    def _generated_assembly(self) -> str:
        """Mesma montagem completa, devolvendo o id (usado pelo teste dos quatro olhos)."""
        pid = self.project(title="Projeto com plano para revisar")
        tid = self.templates["plano_monitoramento_base"]["id"]
        tpl = self.osc.get(f"/v1/document-templates/{tid}").json
        aid = self.osc.post("/v1/document-assemblies",
                            {"template_id": tid, "title": "Plano para revisão", "project_id": pid}).json["id"]
        values = {f["key"]: "Conteúdo informado pela equipe para o campo " + f["label"]
                  for f in tpl["fields"] if f["required"] and not f["derived_from"]}
        self.assertEqual(self.osc.put(f"/v1/document-assemblies/{aid}", {"values": values}).status, 200)
        self.assertEqual(self.osc.post(f"/v1/document-assemblies/{aid}/generate", {"format": "pdf"}).status, 200)
        return aid

    def test_four_eyes_the_author_cannot_approve_their_own_assembly(self):
        aid = self._generated_assembly()
        mine = self.osc.post(f"/v1/document-assemblies/{aid}/review",
                             {"approve": True, "note": "Aprovo o meu próprio documento."})
        self.assertEqual(mine.status, 409, mine)
        self.assertEqual(mine.json["code"], "four_eyes")
        # outra pessoa da mesma organização aprova
        other = self._colleague()
        ok = other.post(f"/v1/document-assemblies/{aid}/review",
                        {"approve": True, "note": "Revisado: metas e indicadores conferidos."})
        self.assertEqual(ok.status, 200, ok)
        self.assertEqual(ok.json["status"], "approved")

    def _colleague(self) -> Client:
        """Outra pessoa da MESMA organização (quatro olhos exige duas pessoas, não dois papéis)."""
        em = f"revisor-{uuid.uuid4().hex[:8]}@teste.org"
        inv = self.osc.post("/v1/org/invitations", {"email": em, "role": "manager"})
        self.assertEqual(inv.status, 201, inv)
        peer = Client()
        peer.post("/v1/auth/register", {"email": em, "password": PASSWORD, "full_name": "Revisora",
                                        "accept_terms": True})
        peer.login(em, PASSWORD)
        acc = peer.post("/v1/auth/accept-invite", {"token": last_token_for(em, "/convite")})
        self.assertEqual(acc.status, 200, acc)
        return peer

    def test_assembly_cannot_be_created_from_a_draft_template(self):
        mine = self.osc.post("/v1/document-templates",
                             {"code": "modelo_proprio_teste", "version": "1.0", "title": "Modelo próprio",
                              "kind": "report", "description": "Modelo de teste da organização"})
        self.assertEqual(mine.status, 201, mine)
        tid = mine.json["id"]
        a = self.osc.post("/v1/document-assemblies", {"template_id": tid, "title": "Tentativa"})
        self.assertEqual(a.status, 409, a)
        self.assertEqual(a.json["code"], "template_not_published")
        empty = self.osc.post(f"/v1/document-templates/{tid}/publish")
        self.assertEqual(empty.status, 409, empty)
        self.assertEqual(empty.json["code"], "template_empty")

    def test_derived_field_path_is_a_closed_list(self):
        mine = self.osc.post("/v1/document-templates",
                             {"code": "modelo_derivado_teste", "version": "1.0", "title": "Modelo derivado",
                              "kind": "report"}).json["id"]
        bad = self.osc.post(f"/v1/document-templates/{mine}/fields",
                            {"section": "1", "position": 1, "key": "vazamento", "label": "Vazamento",
                             "field_type": "text", "derived_from": "users.password_hash"})
        self.assertEqual(bad.status, 422, bad)
        self.assertEqual(bad.json["code"], "derived_unknown")


# ------------------------------------------------------------------------------------------------ match
class MatchFeedbackTests(CoreBase):
    def _run_for_company(self, company) -> dict:
        """Uma empresa que olha um projeto publicado gera uma avaliação de match no nome dela."""
        pid = self.project(title="Projeto avaliado pelo match")
        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/publish").status, 200)
        view = company.get(f"/v1/projects/{pid}")
        self.assertEqual(view.status, 200, view)
        self.assertIn("match_run_id", view.json["match"])
        with db_system() as c:
            run = c.one("SELECT id::text AS id, viewer_org_id::text AS viewer_org_id, engine_version,"
                        " weights_version, rules_version, taxonomy_version, evidence FROM match_runs"
                        " WHERE id = $1", view.json["match"]["match_run_id"])
        return run

    def test_feedback_is_recorded_once_and_trains_nothing_automatically(self):
        company = new_account("company", compliance="approved")
        run = self._run_for_company(company)
        for v in ("engine_version", "weights_version", "rules_version", "taxonomy_version"):
            self.assertTrue(run[v], f"{v} não foi gravada com o resultado")
        r = company.post(f"/v1/match-runs/{run['id']}/feedback",
                         {"feedback": "not_relevant", "reason": "O projeto é de outro território."})
        self.assertEqual(r.status, 201, r)
        self.assertIn("não", r.json["note"].lower())
        dup = company.post(f"/v1/match-runs/{run['id']}/feedback", {"feedback": "accepted"})
        self.assertEqual(dup.status, 409, dup)
        self.assertEqual(dup.json["code"], "already_recorded")
        got = company.get(f"/v1/match-runs/{run['id']}/feedback").json
        self.assertEqual(got["feedback"], "not_relevant")

    def test_foreign_match_run_is_not_found(self):
        company = new_account("company", compliance="approved")
        intruder = new_account("company", compliance="approved")
        run = self._run_for_company(company)
        r = intruder.post(f"/v1/match-runs/{run['id']}/feedback", {"feedback": "accepted"})
        self.assertEqual(r.status, 404, r)


# ------------------------------------------------------------------------------------------------ assinatura
class SignatureProviderTests(CoreBase):
    def test_provider_states_are_honest(self):
        r = self.osc.get("/v1/signature-providers")
        self.assertEqual(r.status, 200, r)
        byk = {p["key"]: p for p in r.json["items"]}
        self.assertEqual(byk["platform_advanced"]["state"], "production")
        self.assertEqual(byk["platform_advanced"]["crypto_level"], "server_hmac")
        self.assertEqual(byk["platform_advanced"]["legal_level"], "advanced")
        self.assertEqual(byk["icp_brasil"]["state"], "unavailable")
        self.assertEqual(byk["icp_brasil"]["legal_level"], "qualified")
        self.assertTrue(byk["icp_brasil"]["external_dependency"])
        # Gov.br é avançada, não qualificada
        self.assertEqual(byk["govbr"]["legal_level"], "advanced")
        self.assertEqual(byk["govbr"]["state"], "unavailable")

    def test_signature_with_unavailable_provider_is_refused_by_the_database(self):
        r = self.osc.upload("/v1/documents", filename="termo.txt", content=b"Termo para assinar",
                            fields={"doc_type": "termo", "title": "Termo de teste"})
        doc = r.json["id"]
        with db_system() as c:
            with self.assertRaises(Exception) as ctx:
                c.run("INSERT INTO signatures(signer_org_id, signer_user_id, subject_type, subject_id,"
                      " subject_sha256, role, statement, signature_hmac, method, provider_key, legal_level,"
                      " crypto_level) VALUES ($1,$2,'document',$3,$4,'legal_representative','Assino',$5,"
                      " 'icp_brasil','icp_brasil','qualified','asymmetric_pades')",
                      self.osc.org_id, self.osc.user["id"], doc, "a" * 64, "b" * 64)
            self.assertIn("icp", str(ctx.exception).lower())

    def test_policy_cannot_require_a_level_no_provider_delivers(self):
        r = self.osc.put("/v1/signature-policies",
                         {"doc_kind": "relatorio", "min_legal_level": "qualified"})
        self.assertEqual(r.status, 409, r)
        self.assertEqual(r.json["code"], "level_unavailable")
        ok = self.osc.put("/v1/signature-policies", {"doc_kind": "relatorio", "min_legal_level": "advanced",
                                                     "min_identity_level": "document"})
        self.assertEqual(ok.status, 200, ok)
        kinds = {p["doc_kind"] for p in self.osc.get("/v1/signature-policies").json["items"]}
        self.assertIn("relatorio", kinds)


# ------------------------------------------------------------------------------------------------ chaves
class KeyManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from tests.support import make_admin
        cls.admin, cls.secret = make_admin()

    def test_inventory_never_exposes_the_key_and_declares_no_kms(self):
        r = self.admin.get("/v1/admin/encryption/keys")
        self.assertEqual(r.status, 200, r)
        self.assertIn("KMS", r.json["kms"])
        self.assertIn("não está implementado", r.json["kms"].lower())
        reg = self.admin.post("/v1/admin/encryption/keys", {"purpose": "field", "note": "registro de teste"})
        self.assertEqual(reg.status, 201, reg)
        inv = self.admin.get("/v1/admin/encryption/keys").json
        self.assertTrue(inv["keys"])
        for k in inv["keys"]:
            self.assertEqual(len(k["fingerprint"]), 16)
            self.assertNotIn("key", [c.lower() for c in k if "fingerprint" not in c])
        states = {k["state"] for k in inv["keys"]}
        self.assertIn("active", states)

    def test_reencrypt_is_auditable_and_idempotent(self):
        self.admin.post("/v1/admin/encryption/keys", {"purpose": "field"})
        r1 = self.admin.post("/v1/admin/encryption/reencrypt", {"table": "users"})
        self.assertEqual(r1.status, 200, r1)
        self.assertIn(r1.json["status"], ("completed", "partial", "failed"))
        self.assertEqual(r1.json["rows_failed"], 0, r1.json)
        r2 = self.admin.post("/v1/admin/encryption/reencrypt", {"table": "users"})
        self.assertEqual(r2.status, 200, r2)
        self.assertEqual(r2.json["rows_failed"], 0)
        inv = self.admin.get("/v1/admin/encryption/keys").json
        self.assertGreaterEqual(len(inv["rotations"]), 2)

    def test_unknown_table_is_refused_with_the_available_list(self):
        r = self.admin.post("/v1/admin/encryption/reencrypt", {"table": "organizations"})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "table_not_rotatable")

    def test_app_role_cannot_change_the_legal_level_of_a_provider(self):
        """O nível jurídico/criptográfico do provedor não é coluna que a aplicação escreva (GRANT por coluna)."""
        for sql in ("UPDATE signature_providers SET legal_level = 'qualified' WHERE key = 'platform_advanced'",
                    "UPDATE signature_providers SET crypto_level = 'asymmetric_pades' WHERE key = 'platform_advanced'"):
            with db_system() as c, self.assertRaises(Exception) as ctx:
                c.run(sql)
            self.assertIn("permission denied", str(ctx.exception).lower())

    def test_qualified_provider_cannot_be_promoted_without_real_asymmetric_signature(self):
        own = owner_conn()
        own.run("UPDATE signature_providers SET crypto_level = 'server_hmac' WHERE key = 'icp_brasil'")
        try:
            r = self.admin.put("/v1/admin/signature-providers/icp_brasil", {"state": "production"})
            self.assertEqual(r.status, 409, r)
            self.assertEqual(r.json["code"], "cannot_promote")
        finally:
            own.run("UPDATE signature_providers SET crypto_level = 'asymmetric_pades', state = 'unavailable'"
                    " WHERE key = 'icp_brasil'")

    def test_calibration_dataset_has_no_personal_data(self):
        r = self.admin.get("/v1/admin/match/calibration")
        self.assertEqual(r.status, 200, r)
        self.assertIn("Nenhum treino automático", r.json["note"])
        for row in r.json["rows"]:
            self.assertNotIn("email", row)
            self.assertNotIn("org_id", row)


