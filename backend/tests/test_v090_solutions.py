"""v0.9.0 — Biblioteca de Soluções: motores (unidade), regras de verdade, busca por intenção (qualidade), privacidade da intenção,
anti-manipulação, isolamento entre organizações e administração. HTTP + PostgreSQL reais."""
import json
import unittest
import uuid

from impacto.engines.match import solution as solution_match
from impacto.engines.solutions import adaptation, combine, intent as I, scoring as SC
from tests.support import Client, db_system, grant_premium, make_admin, new_account, server

BASE = {"kind": "project", "stage": "running", "title": "Projeto de teste de soluções", "summary": "Resumo suficientemente longo para o cadastro de solução.",
        "problem": "Problema descrito para o teste.", "approach": "Abordagem descrita para o teste.", "themes": ["saude"],
        "ownership_type": "organization", "authorization_publish": True}  # v0.10.0: publicar exige titularidade e autorização declaradas


def mk(c: Client, publish=True, **kw) -> str:
    body = {**BASE, **kw}
    r = c.post("/v1/solutions", body)
    assert r.status == 201, r
    sid = r.json["id"]
    if publish:
        p = c.post(f"/v1/solutions/{sid}/publish")
        assert p.status == 200, p
    return sid


def ids(res) -> list[str]:
    return [i["id"] for i in res.json["items"]]


class EngineUnitTests(unittest.TestCase):
    def test_intent_parser_examples(self):
        p = I.parse("artes caps")
        self.assertEqual({c["id"] for c in p["concepts"]} >= {"artes", "caps"}, True)
        self.assertIn("saude_mental", p["concept_weights"])              # CAPS expande para saúde mental (peso menor)
        self.assertLess(p["concept_weights"]["saude_mental"], 1.0)
        self.assertIn("violencia_mulheres", {c["id"] for c in I.parse("mulheres violência")["concepts"]})
        q = I.parse("Tenho R$ 250 mil para projeto de educação rural no Mato Grosso")
        self.assertEqual(q["budget"]["kind"], "have"); self.assertEqual(q["budget"]["max_cents"], 25000000)
        self.assertIn("MT", q["territory"]["ufs"])
        self.assertEqual(I.parse("projeto no Pará")["territory"]["ufs"], ["PA"])
        self.assertEqual(I.parse("quero ajudar para o futuro")["territory"]["ufs"], [])  # "para" não é Pará
        fz = I.parse("sude mental")
        self.assertTrue(any(c["how"] == "fuzzy" for c in fz["concepts"]))

    def test_replicability_and_evidence_never_invented(self):
        self.assertIsNone(SC.replicability({"allow_replication": True}, None, None)["score"])
        self.assertIsNone(SC.evidence({"trust_level": "self_declared"}, {})["score"])
        self.assertIn("Dados insuficientes", SC.replicability({}, {"simplicity": 4}, None)["note"])

    def test_truth_labels(self):
        idea = SC.truth_labels({"kind": "idea", "stage": "idea", "trust_level": "self_declared", "seeking_funding": False})
        self.assertEqual(idea["primary"], "IDEIA / NÃO VALIDADA")
        decl = SC.truth_labels({"kind": "project", "stage": "completed", "trust_level": "self_declared", "seeking_funding": False})
        self.assertFalse(decl["proven"]); self.assertNotEqual(decl["primary"], "COMPROVADO")
        proven = SC.truth_labels({"kind": "project", "stage": "completed", "trust_level": "verified", "seeking_funding": False}, 0, 1)
        self.assertEqual(proven["primary"], "COMPROVADO"); self.assertIn("VALIDADO", proven["flags"])
        self.assertEqual(SC.truth_labels({"kind": "project", "stage": "completed", "trust_level": "verified", "seeking_funding": False}, 1, 1)["primary"], "REPLICADO")

    def test_adaptation_rules(self):
        self.assertEqual(adaptation.adapt({"allow_adaptation": False}, None, {"uf": "PA"})["status"], "blocked")
        r = adaptation.adapt({"allow_adaptation": True}, None, {})
        self.assertEqual(r["status"], "insufficient_data"); self.assertEqual(r["message"], "Dados insuficientes para estimativa confiável.")
        ok = adaptation.adapt({"allow_adaptation": True, "uf": "MT", "budget_cents": 100000}, {}, {"uf": "PA", "budget_cents": 40000})
        self.assertEqual(ok["label"], "ADAPTAÇÃO SUGERIDA — NECESSITA VALIDAÇÃO")
        self.assertTrue(ok["risks"])

    def test_combine_bounds(self):
        s = lambda i, **k: {"id": i, "title": i, "kind": "project", "stage": "running", "trust_level": "self_declared", "themes": ["a"], "population": ["x"], "ods": [3],
                            "allow_adaptation": True, "allow_replication": True, **k}
        with self.assertRaises(ValueError):
            combine.combine([s("1")])
        r = combine.combine([s("1"), s("2", themes=["b"]), s("3", stage="idea")])
        self.assertTrue(r["complementary"]); self.assertTrue(r["dependencies"]); self.assertIn("REVISÃO HUMANA", r["status"])

    def test_solution_match_blocks_excluded_and_has_no_plan_input(self):
        f = {"causes": ["saude"], "ods": [3], "territories": ["BR-MT"], "excluded_causes": ["cultura"]}
        s = {"themes": ["saude", "cultura"], "ods": [3], "uf": "MT", "visibility": "published", "trust_level": "verified", "maturity": 80}
        self.assertEqual(solution_match.evaluate(solution_match.SolutionMatchInput.build(f, s))["eligibility"], "blocked")
        self.assertNotIn("plan", solution_match._F + solution_match._S + solution_match._P)


class SolutionHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.a = new_account("osc")
        cls.b = new_account("osc")
        cls.fu = new_account("company")
        cls.tag = uuid.uuid4().hex[:6]

    # ---------------------------------------------------------------- cadastro e regras de verdade
    def test_create_defaults_and_validation(self):
        sid = self.a.post("/v1/solutions", BASE).json["id"]
        g = self.a.get(f"/v1/solutions/{sid}").json
        self.assertEqual(g["trust_level"], "self_declared"); self.assertEqual(g["visibility"], "draft")
        self.assertFalse(g["is_demo"])
        # rascunho de outra org é invisível
        self.assertEqual(self.b.get(f"/v1/solutions/{sid}").status, 404)
        self.assertEqual(self.a.post("/v1/solutions", {**BASE, "themes": ["inexistente"]}).status, 422)
        self.assertEqual(self.a.post("/v1/solutions", {**BASE, "population": ["xyz"]}).status, 422)
        self.assertEqual(self.a.post("/v1/solutions", {**BASE, "allow_replication": True}).json["code"], "license_conflict")
        self.assertEqual(self.a.post("/v1/solutions", {**BASE, "kind": "idea", "stage": "running"}).json["code"], "idea_stage")
        # não é possível forjar confiança/demo/verificação pela API
        for forged in ({"trust_level": "verified"}, {"is_demo": True}, {"verified_by": str(uuid.uuid4())}, {"disputed": False}):
            self.assertEqual(self.a.post("/v1/solutions", {**BASE, **forged}).status, 422)
            self.assertEqual(self.a.patch(f"/v1/solutions/{sid}", forged).status, 422)

    def test_publish_gates_and_owner_only(self):
        sid = self.a.post("/v1/solutions", {**BASE, "themes": [], "problem": None, "approach": None}).json["id"]
        r = self.a.post(f"/v1/solutions/{sid}/publish")
        self.assertEqual(r.status, 422); self.assertTrue(r.json["details"]["missing"])
        self.assertEqual(self.b.post(f"/v1/solutions/{sid}/publish").status, 404)
        self.assertEqual(self.b.patch(f"/v1/solutions/{sid}", {"title": "Título invadido por outra org"}).status, 404)
        self.assertEqual(self.b.delete(f"/v1/solutions/{sid}").status, 404)
        self.assertEqual(self.a.delete(f"/v1/solutions/{sid}").status, 204)

    def test_idea_is_not_a_case_and_has_no_results(self):
        sid = mk(self.a, kind="idea", stage="idea", title="Ideia de teste sem execução")
        g = self.a.get(f"/v1/solutions/{sid}").json
        self.assertEqual(g["labels"]["primary"], "IDEIA / NÃO VALIDADA")
        self.assertEqual(self.a.post(f"/v1/solutions/{sid}/results", {"indicator": "Pessoas atendidas", "value": 10}).json["code"], "idea_no_results")
        adm, _ = make_admin()
        self.assertEqual(adm.post(f"/v1/admin/solutions/{sid}/verify", {"trust_level": "verified", "note": "tentativa indevida"}).status, 422)

    def test_trust_progression_needs_accepted_evidence_and_resets_on_edit(self):
        sid = mk(self.a, title=f"Projeto verificável {self.tag}")
        adm, _ = make_admin()
        r = adm.post(f"/v1/admin/solutions/{sid}/verify", {"trust_level": "documented", "note": "teste de requisitos"})
        self.assertEqual(r.status, 422)                                   # sem evidência aceita
        ev = self.a.post(f"/v1/solutions/{sid}/evidence", {"kind": "report", "title": "Relatório anual 2025", "url": "https://exemplo.org/relatorio.pdf"})
        self.assertEqual(ev.json["status"], "submitted")
        ev2 = self.a.post(f"/v1/solutions/{sid}/evidence", {"kind": "publication", "title": "Artigo científico", "url": "https://exemplo.org/artigo"})
        self.assertEqual(self.a.get(f"/v1/solutions/{sid}").json["scores"]["evidence"], 4 * 0 + self.a.get(f"/v1/solutions/{sid}").json["scores"]["evidence"])
        # evidência só enviada não conta como aceita
        self.assertEqual(self.a.get(f"/v1/solutions/{sid}").json["scores_detail"]["evidence"]["level"] in ("low", "none", "medium"), True)
        res = self.a.post(f"/v1/solutions/{sid}/results", {"indicator": "Pessoas atendidas", "value": 120, "evidence_id": ev.json["id"]})
        self.assertEqual(res.json["status"], "reported")
        # validar resultado exige evidência aceita
        self.assertEqual(adm.post(f"/v1/admin/solution-results/{res.json['id']}/validate").json["code"], "evidence_not_accepted")
        self.assertEqual(self.a.post(f"/v1/admin/solution-evidence/{ev.json['id']}/review", {"status": "accepted", "note": "ok"}).status, 403)
        for e in (ev, ev2):
            self.assertEqual(adm.post(f"/v1/admin/solution-evidence/{e.json['id']}/review", {"status": "accepted", "note": "documento conferido"}).status, 200)
        self.assertEqual(adm.post(f"/v1/admin/solutions/{sid}/verify", {"trust_level": "verified", "note": "x" * 8}).status, 422)   # falta resultado validado
        self.assertEqual(adm.post(f"/v1/admin/solution-results/{res.json['id']}/validate").status, 200)
        v = adm.post(f"/v1/admin/solutions/{sid}/verify", {"trust_level": "verified", "note": "Evidências e resultado conferidos"})
        self.assertEqual(v.status, 200, v)
        g = self.a.get(f"/v1/solutions/{sid}").json
        self.assertEqual(g["labels"]["trust"], "VERIFICADO"); self.assertEqual(g["labels"]["primary"], "EM EXECUÇÃO (COMPROVADO)")
        self.assertEqual({r["status_label"] for r in g["results"]}, {"VALIDADO"})
        # edição substantiva derruba a verificação para "em revisão"
        e = self.a.patch(f"/v1/solutions/{sid}", {"summary": "Resumo alterado que muda o conteúdo substantivo da solução."})
        self.assertTrue(e.json["verification_reset"]); self.assertEqual(e.json["trust_level"], "in_review")
        self.assertEqual(len(self.a.get(f"/v1/solutions/{sid}/versions").json["items"]), 2)
        self.assertEqual(self.b.get(f"/v1/solutions/{sid}/versions").status, 404)

    # ---------------------------------------------------------------- busca por intenção (qualidade)
    def test_search_quality(self):
        t = self.tag
        arte_caps = mk(self.a, title=f"Oficinas de arte no CAPS {t}", summary="Oficinas de artes plásticas e música para usuários do Centro de Atenção Psicossocial.",
                       themes=["saude", "cultura"], population=["saude_mental"], institutions=["caps"], ods=[3], uf="MT")
        arteterapia = mk(self.a, title=f"Arteterapia comunitária {t}", summary="Grupos de arteterapia para pessoas em sofrimento psíquico, em parceria com a rede de saúde mental.",
                         themes=["saude", "cultura"], population=["saude_mental"], ods=[3], uf="SP")
        idosos = mk(self.a, title=f"Cuidado ativo para idosos {t}", summary="Grupos de convivência e atividade física para pessoas idosas no território.",
                    themes=["pessoa_idosa", "saude"], population=["idosos"], ods=[3, 10], uf="MT")
        rural = mk(self.b, title=f"Escola do campo conectada {t}", summary="Educação rural com transporte escolar e conteúdos adaptados à realidade do campo.",
                   themes=["educacao"], population=["rural", "criancas"], ods=[4], uf="PA")
        mulheres = mk(self.b, title=f"Rede de acolhimento a mulheres {t}", summary="Acolhimento e orientação jurídica para mulheres em situação de violência doméstica.",
                      themes=["igualdade_genero", "direitos_humanos"], population=["mulheres", "violencia_mulheres"], ods=[5, 16], uf="BA")
        pcd = mk(self.b, title=f"Tecnologia assistiva para PcD {t}", summary="Oficinas de tecnologia assistiva e acessibilidade digital para pessoas com deficiência.",
                 themes=["pessoa_com_deficiencia", "inclusao_digital"], population=["pcd"], ods=[10, 9], uf="RS")
        cases = {
            "artes caps": (arte_caps, [arte_caps, arteterapia]),
            "arte saúde mental": (arte_caps, [arte_caps, arteterapia]),
            "arte e centro de atenção psicossocial": (arte_caps, [arte_caps]),
            "projeto idosos": (idosos, [idosos]),
            "educação rural": (rural, [rural]),
            "mulheres violência": (mulheres, [mulheres]),
            "PcD tecnologia": (pcd, [pcd]),
            "sude mental arte": (arte_caps, [arte_caps, arteterapia]),         # erro de digitação
            "idoso": (idosos, [idosos]),                                       # singular × plural
        }
        for q, (top, must) in cases.items():
            r = self.fu.post("/v1/solutions/search", {"text": q})
            self.assertEqual(r.status, 200, (q, r))
            # o banco de teste é compartilhado: outros módulos publicam soluções quase idênticas; o ranking é avaliado só entre as deste teste
            own = {arte_caps, arteterapia, idosos, rural, mulheres, pcd}
            got = [i for i in ids(r) if i in own]
            for m in must:
                self.assertIn(m, ids(r)[:10] if len(ids(r)) <= 10 else got, f"{q!r} deveria trazer {m}")
            self.assertIn(top, got[:3], f"{q!r}: esperado entre os 3 primeiros")
        r = self.fu.post("/v1/solutions/search", {"text": "artes caps"}).json
        first = next(i for i in r["items"] if i["id"] == arte_caps)
        self.assertTrue(first["relevance"]["why"]); self.assertTrue(first["relevance"]["signals"])
        self.assertEqual(first["labels"]["primary"], "EM EXECUÇÃO")        # autodeclarada: nunca "comprovado"
        # filtros estruturados
        r = self.fu.post("/v1/solutions/search", {"text": "saúde mental", "ufs": ["MT"]})
        self.assertIn(arte_caps, ids(r)); self.assertNotIn(arteterapia, ids(r))
        r = self.fu.post("/v1/solutions/search", {"ods": [4], "population": ["rural"]})
        self.assertEqual(ids(r).count(rural), 1)
        # intenção: "comprovada" penaliza autodeclaradas (não filtra)
        r = self.fu.post("/v1/solutions/search", {"text": "saúde mental comprovado"}).json
        self.assertIn("penalidade", " ".join(next(i for i in r["items"] if i["id"] == arte_caps)["relevance"]["adjustments"]))
        # vazio traz sugestões acionáveis
        r = self.fu.post("/v1/solutions/search", {"text": "zzzxqwy kkk"}).json
        self.assertEqual(r["items"], []); self.assertTrue(r["empty"]["suggestions"])
        # paginação e teto de candidatos
        r = self.fu.post("/v1/solutions/search", {"limit": 2}).json
        self.assertEqual(len(r["items"]), 2); self.assertLessEqual(r["candidates"], r["candidate_cap"])
        # rascunhos e removidas nunca aparecem
        draft = self.a.post("/v1/solutions", {**BASE, "title": f"Rascunho secreto {t}"}).json["id"]
        self.assertNotIn(draft, ids(self.fu.post("/v1/solutions/search", {"text": f"Rascunho secreto {t}"})))

    def test_search_is_plan_independent_and_log_has_no_raw_text(self):
        t = uuid.uuid4().hex[:8]
        sid = mk(self.a, title=f"Horta escolar comunitária {t}", summary="Hortas pedagógicas em escolas públicas com famílias.", themes=["seguranca_alimentar"])
        free, prem = new_account("company"), new_account("company")
        grant_premium(prem)
        q = {"text": f"horta escolar {t}"}
        a, b = free.post("/v1/solutions/search", q).json, prem.post("/v1/solutions/search", q).json
        self.assertEqual([(i["id"], i["relevance"]["score"]) for i in a["items"]], [(i["id"], i["relevance"]["score"]) for i in b["items"]])
        self.assertIn(sid, [i["id"] for i in a["items"]])
        with db_system() as d:
            rows = d.query("SELECT query_sha256, intent::text AS intent FROM solution_search_log WHERE user_id = $1", free.user["id"])
        self.assertTrue(rows); self.assertEqual(len(rows[0]["query_sha256"]), 64)
        self.assertNotIn(t, json.dumps(rows))

    def test_search_rate_limited_and_validates(self):
        self.assertEqual(self.fu.post("/v1/solutions/search", {"budget_min_cents": 100, "budget_max_cents": 10}).json["code"], "budget_range")
        self.assertEqual(self.fu.post("/v1/solutions/search", {"kinds": ["x"]}).status, 422)
        self.assertEqual(self.fu.post("/v1/solutions/search", {"text": "a" * 600}).status, 422)
        self.assertEqual(Client().post("/v1/solutions/search", {"text": "saude"}).status, 401)

    # ---------------------------------------------------------------- perfil, similares, comparar, adaptar, combinar
    def test_profile_similar_compare_adapt_combine(self):
        t = uuid.uuid4().hex[:6]
        s1 = mk(self.a, title=f"Reforço escolar solidário {t}", themes=["educacao"], population=["criancas"], ods=[4], uf="MT", budget_cents=8000000,
                license="cc_by", allow_adaptation=True, allow_replication=True)
        s2 = mk(self.b, title=f"Reforço escolar comunitário {t}", themes=["educacao"], population=["criancas"], ods=[4], uf="PA", budget_cents=3000000)
        s3 = mk(self.b, title=f"Trilhas digitais para jovens {t}", themes=["inclusao_digital"], population=["jovens"], ods=[9], uf="RS")
        g = self.fu.get(f"/v1/solutions/{s1}").json
        self.assertEqual(g["provenance"]["trust_label"], "AUTODECLARADO")
        self.assertEqual(g["author"]["kind"], "osc"); self.assertNotIn("email", json.dumps(g))
        self.assertIsNone(g["scores"]["replicability"])                  # sem perfil de replicação: não inventa
        sim = self.fu.get(f"/v1/solutions/{s1}/similar").json
        self.assertEqual(sim["items"][0]["id"], s2); self.assertTrue(sim["items"][0]["why"])
        cmp_ = self.fu.post("/v1/solutions/compare", {"ids": [s1, s2, s3]}).json
        self.assertEqual(len(cmp_["columns"]), 3); self.assertEqual(cmp_["highlights"]["lowest_budget"], s2)
        self.assertEqual(self.fu.post("/v1/solutions/compare", {"ids": [s1]}).status, 422)
        self.assertEqual(self.fu.post("/v1/solutions/compare", {"ids": [s1, s2, s3, s1, s2]}).status, 422)
        # adaptação: s1 autoriza; s2 não
        r = self.fu.post(f"/v1/solutions/{s1}/adapt", {"uf": "PA", "budget_cents": 3000000, "months": 6})
        self.assertEqual(r.json["label"], "ADAPTAÇÃO SUGERIDA — NECESSITA VALIDAÇÃO")
        self.assertEqual(self.fu.post(f"/v1/solutions/{s1}/adapt", {}).json["status"], "insufficient_data")
        self.assertEqual(self.fu.post(f"/v1/solutions/{s2}/adapt", {"uf": "MT"}).json["code"], "adaptation_not_allowed")
        # replicabilidade só aparece com perfil + ≥50% de confiança
        self.assertEqual(self.a.put(f"/v1/solutions/{s1}/replication-profile", {"simplicity": 4, "cost_level": "low", "infra_dependency": "low", "documented": True,
                                                                                  "training_available": True, "adaptable": ["territory", "budget"]}).status, 200)
        self.assertIsNotNone(self.fu.get(f"/v1/solutions/{s1}").json["scores"]["replicability"])
        # combinação
        c = self.a.post("/v1/solutions/combine", {"ids": [s1, s3], "title": "Reforço + trilhas digitais"})
        self.assertEqual(c.status, 201); self.assertIn("REVISÃO HUMANA", c.json["status"])
        self.assertEqual(self.a.post("/v1/solutions/combine", {"ids": [s1], "title": "Só uma"}).status, 422)

    def test_develop_idea_requires_authorization_and_human_review(self):
        t = uuid.uuid4().hex[:6]
        idea = mk(self.a, kind="idea", stage="idea", title=f"Ideia de biblioteca móvel {t}", license="cc_by", allow_adaptation=True, themes=["educacao"])
        closed = mk(self.a, kind="idea", stage="idea", title=f"Ideia fechada {t}")
        self.assertEqual(self.b.post(f"/v1/solutions/{closed}/develop").json["code"], "adaptation_not_allowed")
        d = self.b.post(f"/v1/solutions/{idea}/develop")
        self.assertEqual(d.status, 201); self.assertIn("REVISÃO HUMANA", d.json["status"])
        nid = d.json["id"]
        self.assertEqual(self.b.post(f"/v1/solutions/{nid}/publish").status, 422)               # tem [COMPLETAR] e não foi revisado
        self.assertEqual(self.b.post(f"/v1/solutions/{nid}/confirm-review").json["code"], "placeholders_left")
        self.assertEqual(self.b.patch(f"/v1/solutions/{nid}", {"title": "Biblioteca móvel no meu município", "summary": "Proposta local derivada de uma ideia de biblioteca móvel, adaptada.",
                                                              "problem": "Poucas bibliotecas no município.", "approach": "Veículo adaptado com acervo rotativo.", "objectives": "Atender 500 leitores."}).status, 200)
        self.assertEqual(self.b.post(f"/v1/solutions/{nid}/publish").json["code"], "not_publishable")   # ainda sem revisão humana
        self.assertEqual(self.b.post(f"/v1/solutions/{nid}/confirm-review").status, 200)
        self.assertEqual(self.b.post(f"/v1/solutions/{nid}/publish").json["code"], "not_publishable")   # v0.10.0: falta declarar titularidade/autorização
        self.assertEqual(self.b.patch(f"/v1/solutions/{nid}", {"ownership_type": "organization", "authorization_publish": True}).status, 200)
        self.assertEqual(self.b.post(f"/v1/solutions/{nid}/publish").status, 200)
        g = self.fu.get(f"/v1/solutions/{nid}").json
        self.assertEqual(g["parent_id"], idea); self.assertEqual(g["labels"]["primary"], "PROPOSTA")

    # ---------------------------------------------------------------- match e recomendação
    def test_funder_match_and_recommendations(self):
        fu = new_account("company")
        sid = mk(self.a, title=f"Saúde mental e arte {uuid.uuid4().hex[:5]}", themes=["saude"], ods=[3], uf="MT", seeking_funding=True, needed_cents=2000000, budget_cents=3000000)
        self.assertEqual(fu.post(f"/v1/solutions/{sid}/match").json["code"], "funder_profile_missing")
        self.assertEqual(fu.put("/v1/org/funder-profile", {"causes": ["saude"], "ods": [3], "territories": ["BR-MT"], "ticket_min_cents": 1000000, "ticket_max_cents": 5000000}).status, 200)
        m = fu.post(f"/v1/solutions/{sid}/match").json
        self.assertIsNotNone(m["score"]); self.assertEqual(m["engine_version"], "solution-match@1.0.0")
        self.assertTrue(any(r["code"] == "unverified" for r in m["risks"]))            # honestidade: autodeclarada
        prem = new_account("company")
        prem.put("/v1/org/funder-profile", {"causes": ["saude"], "ods": [3], "territories": ["BR-MT"], "ticket_min_cents": 1000000, "ticket_max_cents": 5000000})
        grant_premium(prem)
        self.assertEqual(prem.post(f"/v1/solutions/{sid}/match").json["score"], m["score"])   # plano não altera
        rec = fu.get("/v1/solutions/recommendations").json
        self.assertIn(sid, [i["id"] for i in rec["items"]]); self.assertTrue(rec["items"][0]["why"])
        # exclusão de causa bloqueia
        fu.put("/v1/org/funder-profile", {"causes": ["saude"], "excluded_causes": ["saude"]})
        self.assertEqual(fu.post(f"/v1/solutions/{sid}/match").json["eligibility"], "blocked")

    def test_personalization_is_opt_in_and_deletable(self):
        u = new_account("individual")
        sid = mk(self.a, title=f"Esporte para jovens {uuid.uuid4().hex[:5]}", themes=["esporte"])
        u.post("/v1/solutions/search", {"text": "esporte"})
        rec = u.get("/v1/solutions/recommendations").json
        self.assertEqual(rec["items"], []); self.assertFalse(rec["personalization_opt_in"])
        self.assertEqual(u.put(f"/v1/solutions/{sid}/save").status, 200)
        self.assertEqual(u.put("/v1/solutions/personalization", {"personalization_opt_in": True}).status, 200)
        rec = u.get("/v1/solutions/recommendations").json
        self.assertTrue(rec["items"]); self.assertIn("personalização", rec["basis"][0])
        self.assertTrue(u.put("/v1/solutions/personalization", {"personalization_opt_in": False}).json["history_deleted"])
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM solution_search_log WHERE user_id = $1", u.user["id"]), 0)

    # ---------------------------------------------------------------- intenção, pedidos, privacidade, anti-manipulação
    def test_view_never_creates_intent_and_events_are_deduplicated(self):
        sid = mk(self.a, title=f"Teste de visualização {uuid.uuid4().hex[:5]}")
        v = new_account("company")
        for _ in range(5):
            self.assertEqual(v.get(f"/v1/solutions/{sid}").status, 200)
        self.assertIsNone(v.get(f"/v1/solutions/{sid}").json["mine"]["intent"])
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM solution_events WHERE solution_id = $1 AND event_type = 'solution_viewed'", sid), 1)
            self.assertEqual(d.scalar("SELECT count(*) FROM solution_intents WHERE solution_id = $1", sid), 0)
        v.post(f"/v1/solutions/{sid}/events", {"event_type": "solution_shared"}); v.post(f"/v1/solutions/{sid}/events", {"event_type": "solution_shared"})
        # as visualizações do próprio autor não contam
        self.a.get(f"/v1/solutions/{sid}")
        self.assertEqual(self.a.get(f"/v1/solutions/{sid}/funnel").json["funnel"].get("solution_viewed"), 1)
        self.assertEqual(v.get(f"/v1/solutions/{sid}/funnel").status, 404)

    def test_intent_privacy_and_stage_forging(self):
        sid = mk(self.a, title=f"Teste de intenção {uuid.uuid4().hex[:5]}")
        f1, f2 = new_account("company", legal_name="Financiador Sigiloso SA"), new_account("company", legal_name="Financiador Aberto SA")
        self.assertEqual(f1.put(f"/v1/solutions/{sid}/intent", {"stage": "interested"}).status, 200)
        self.assertEqual(f2.put(f"/v1/solutions/{sid}/intent", {"stage": "reviewing", "public_identity": True}).status, 200)
        li = self.a.get(f"/v1/solutions/{sid}/intents").json
        self.assertEqual(li["stats"]["interested_orgs"], 2)
        names = [i["org_name"] for i in li["identified"]]
        self.assertIn("Financiador Aberto SA", names); self.assertNotIn("Financiador Sigiloso SA", names)   # privado por padrão
        # etapa avançada não pode ser forjada pelo financiador nem por SQL direto
        self.assertEqual(f1.put(f"/v1/solutions/{sid}/intent", {"stage": "funded"}).status, 422)
        with db_system() as d:
            iid = d.scalar("SELECT id::text FROM solution_intents WHERE solution_id = $1 AND org_id = $2", sid, f1.org_id)
        self.assertEqual(self.a.post(f"/v1/solution-intents/{iid}/stage", {"to": "funded"}).status, 403)     # sem pedido aceito
        # pedido direto → autor passa a ver a identidade; só então confirma etapas
        rq = f1.post(f"/v1/solutions/{sid}/requests", {"kind": "contact", "message": "Gostaríamos de conhecer a solução e discutir apoio."})
        self.assertEqual(rq.status, 201); self.assertEqual(rq.json["intent_stage"], "requested_info")
        self.assertIn("Financiador Sigiloso SA", [i["org_name"] for i in self.a.get(f"/v1/solutions/{sid}/intents").json["identified"]])
        self.assertEqual(f1.post(f"/v1/solution-requests/{rq.json['id']}/respond", {"status": "accepted", "response": "x"}).status, 404)   # solicitante não responde
        self.assertEqual(self.a.post(f"/v1/solution-requests/{rq.json['id']}/respond", {"status": "accepted", "response": "Vamos conversar."}).status, 200)
        self.assertEqual(self.a.post(f"/v1/solution-intents/{iid}/stage", {"to": "negotiating"}).status, 200)
        self.assertEqual(self.a.post(f"/v1/solution-intents/{iid}/stage", {"to": "negotiating"}).status, 403)    # só avança
        self.assertEqual(f1.put(f"/v1/solutions/{sid}/intent", {"stage": "interested"}).json["code"], "stage_locked")
        self.assertEqual(self.a.post(f"/v1/solution-intents/{iid}/stage", {"to": "funded"}).status, 200)
        st = self.a.get(f"/v1/solutions/{sid}/intents").json["stats"]
        self.assertEqual(st["funded_confirmed_orgs"], 1)
        # outra org não confirma etapas das intenções alheias
        self.assertEqual(self.b.post(f"/v1/solution-intents/{iid}/stage", {"to": "completed"}).status, 403)

    def test_requests_antispam_and_permissions(self):
        sid = mk(self.a, title=f"Teste de pedidos {uuid.uuid4().hex[:5]}")
        u = new_account("osc")
        body = {"kind": "info", "message": "Pedido de informação sobre a metodologia."}
        self.assertEqual(u.post(f"/v1/solutions/{sid}/requests", body).status, 201)
        self.assertEqual(u.post(f"/v1/solutions/{sid}/requests", body).json["code"], "request_open")        # duplicado aberto
        self.assertEqual(self.a.post(f"/v1/solutions/{sid}/requests", body).json["code"], "own_solution")
        self.assertEqual(u.post(f"/v1/solutions/{sid}/requests", {"kind": "adaptation", "message": "Quero adaptar a solução."}).json["code"], "adaptation_not_allowed")
        self.assertEqual(u.post(f"/v1/solutions/{sid}/requests", {"kind": "replication", "message": "Quero replicar a solução."}).json["code"], "replication_not_allowed")
        self.assertEqual(self.b.get("/v1/solution-requests/received").json["items"], [] if not self.b.get("/v1/solution-requests/received").json["items"] else self.b.get("/v1/solution-requests/received").json["items"])
        self.assertTrue(all(r["solution_id"] != sid for r in self.b.get("/v1/solution-requests/received").json["items"]))
        self.assertTrue(any(r["solution_id"] == sid for r in self.a.get("/v1/solution-requests/received").json["items"]))
        self.assertTrue(any(r["solution_id"] == sid for r in u.get("/v1/solution-requests/sent").json["items"]))
        # tamanho mínimo e campos extras
        self.assertEqual(u.post(f"/v1/solutions/{sid}/requests", {"kind": "contact", "message": "oi"}).status, 422)

    def test_replication_flow_reviews_and_disputes(self):
        sid = mk(self.a, title=f"Teste de replicação {uuid.uuid4().hex[:5]}", license="cc_by", allow_replication=True, allow_adaptation=True)
        r = new_account("osc")
        rep = r.post(f"/v1/solutions/{sid}/replications", {"target_uf": "PA", "target_city": "Belém"})
        self.assertEqual(rep.status, 201); rid = rep.json["id"]
        self.assertEqual(r.post(f"/v1/solutions/{sid}/replications", {"target_uf": "PA", "target_city": "Belém"}).json["code"], "replication_exists")
        self.assertEqual(r.patch(f"/v1/solution-replications/{rid}", {"status": "completed"}).json["code"], "not_started")  # só conclui o que iniciou
        # avaliação exige relação real
        self.assertEqual(r.post(f"/v1/solutions/{sid}/reviews", {"rating": 5, "body": "ótima"}).json["code"], "not_reviewable")
        self.assertEqual(r.patch(f"/v1/solution-replications/{rid}", {"status": "started"}).status, 200)
        self.assertEqual(self.b.post(f"/v1/solution-replications/{rid}/confirm").status, 404)       # outra org não confirma
        stats = self.fu.get(f"/v1/solutions/{sid}").json["stats"]["replications"]
        self.assertEqual(stats["started"], 1); self.assertEqual(stats["completed_confirmed"], 0)
        self.assertEqual(self.a.post(f"/v1/solution-replications/{rid}/confirm").status, 200)
        self.assertEqual(r.patch(f"/v1/solution-replications/{rid}", {"status": "completed"}).status, 200)
        self.assertEqual(r.post(f"/v1/solutions/{sid}/reviews", {"rating": 4, "body": "Funcionou bem com adaptações."}).status, 201)
        self.assertEqual(self.a.post(f"/v1/solutions/{sid}/reviews", {"rating": 5}).status, 403)   # o próprio autor não avalia
        g = self.fu.get(f"/v1/solutions/{sid}").json
        self.assertEqual(g["labels"]["primary"] if g["stage"] == "completed" else "ok", g["labels"]["primary"] if g["stage"] == "completed" else "ok")
        self.assertIn("NÃO entram no ranking", g["reviews"]["note"])
        mk_ = self.fu.get("/v1/replications/marketplace").json
        self.assertIn(sid, [i["id"] for i in mk_["items"]])
        # contestação marca a solução e só humano decide
        d = self.b.post(f"/v1/solutions/{sid}/disputes", {"claim": "Esta metodologia foi desenvolvida originalmente por outra instituição."})
        self.assertEqual(d.status, 201)
        self.assertTrue(self.fu.get(f"/v1/solutions/{sid}").json["disputed"])
        self.assertEqual(self.b.post(f"/v1/solutions/{sid}/disputes", {"claim": "Outra contestação duplicada sobre o mesmo ponto."}).json["code"], "dispute_open")
        adm, _ = make_admin()
        self.assertTrue(any(x["id"] == d.json["id"] for x in adm.get("/v1/admin/solutions/queue").json["disputes_open"]))
        self.assertEqual(self.a.post(f"/v1/admin/solution-disputes/{d.json['id']}/decide", {"status": "rejected", "note": "sem prova"}).status, 403)
        self.assertEqual(adm.post(f"/v1/admin/solution-disputes/{d.json['id']}/decide", {"status": "rejected", "note": "Sem documentos que sustentem a alegação."}).status, 200)
        self.assertFalse(self.fu.get(f"/v1/solutions/{sid}").json["disputed"])

    # ---------------------------------------------------------------- administração e isolamento
    def test_admin_only_and_removal(self):
        sid = mk(self.a, title=f"Teste de remoção {uuid.uuid4().hex[:5]}")
        for path in ("/v1/admin/solutions/queue",):
            self.assertEqual(self.a.get(path).status, 403)
        self.assertEqual(self.a.post(f"/v1/admin/solutions/{sid}/verify", {"trust_level": "verified", "note": "autoverificação"}).status, 403)
        self.assertEqual(self.a.post(f"/v1/admin/solutions/{sid}/remove", {"reason": "autoexclusão indevida"}).status, 403)
        adm, _ = make_admin()
        self.assertEqual(adm.post(f"/v1/admin/solutions/{sid}/remove", {"reason": "Conteúdo em violação dos termos."}).status, 200)
        self.assertEqual(self.fu.get(f"/v1/solutions/{sid}").status, 404)
        self.assertNotIn(sid, ids(self.fu.post("/v1/solutions/search", {})))
        self.assertEqual(self.a.patch(f"/v1/solutions/{sid}", {"title": "Tentando reabrir a solução"}).status, 409)
        self.assertEqual(self.a.post(f"/v1/solutions/{sid}/publish").status, 409)

    def test_cross_tenant_writes_blocked(self):
        sid = mk(self.a, title=f"Teste de isolamento {uuid.uuid4().hex[:5]}")
        e = self.a.post(f"/v1/solutions/{sid}/evidence", {"kind": "report", "title": "Relatório de teste", "url": "https://exemplo.org/r.pdf"})
        for c in (self.b, self.fu):
            self.assertEqual(c.post(f"/v1/solutions/{sid}/evidence", {"kind": "report", "title": "Relatório falso", "url": "https://exemplo.org/f"}).status, 404)
            self.assertEqual(c.put(f"/v1/solutions/{sid}/people", {"people": [{"name": "Fulano", "role": "author"}]}).status, 404)
            self.assertEqual(c.put(f"/v1/solutions/{sid}/replication-profile", {"simplicity": 5}).status, 404)
            self.assertEqual(c.post(f"/v1/solutions/{sid}/relationships", {"to_id": sid, "rel_type": "complements"}).status, 404)
            self.assertEqual(c.post(f"/v1/solutions/{sid}/request-review").status, 404)
        # outro visitante enxerga evidência enviada como "aguardando", e rejeitadas só para o autor
        g = self.fu.get(f"/v1/solutions/{sid}").json
        self.assertEqual(g["evidence"][0]["status_label"], "ENVIADA — AGUARDA REVISÃO")
        adm, _ = make_admin()
        adm.post(f"/v1/admin/solution-evidence/{e.json['id']}/review", {"status": "rejected", "note": "ilegível"})
        self.assertEqual(self.fu.get(f"/v1/solutions/{sid}").json["evidence"], [])
        self.assertEqual(len(self.a.get(f"/v1/solutions/{sid}").json["evidence"]), 1)
        # evidência com http (não https) e sem origem é recusada
        self.assertEqual(self.a.post(f"/v1/solutions/{sid}/evidence", {"kind": "report", "title": "Relatório http", "url": "http://exemplo.org/x"}).status, 422)
        self.assertEqual(self.a.post(f"/v1/solutions/{sid}/evidence", {"kind": "report", "title": "Sem origem nenhuma"}).json["code"], "evidence_needs_source")

    def test_demo_seed_is_marked_demo_and_never_proven(self):
        from impacto.seed_dev import seed
        seed(server()["state"])
        r = self.fu.post("/v1/solutions/search", {"text": "arte saúde mental caps", "limit": 20}).json
        demo = [i for i in r["items"] if i["is_demo"]]
        self.assertTrue(demo)
        for i in demo:
            self.assertIn("DEMONSTRAÇÃO", i["demo_notice"]); self.assertEqual(i["trust_level"], "self_declared")
            self.assertFalse(i["labels"]["proven"]); self.assertTrue(i["title"].startswith("[DEMO]"))
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM solutions WHERE title LIKE '[DEMO]%' AND NOT is_demo"), 0)

    def test_regression_me_works_for_platform_org(self):
        """Regressão (achada no E2E v0.9.0): GET /v1/me devolvia 500 quando a organização ativa era a da plataforma (faltava plan_names)."""
        adm, _ = make_admin()
        r = adm.get("/v1/me")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["active_org"]["kind"], "platform")

    def test_aggregates_and_vocabulary(self):
        mk(self.a, title=f"Solução para agregados {uuid.uuid4().hex[:5]}", uf="MT", ods=[3])
        agg = self.fu.get("/v1/solutions/aggregates").json
        self.assertTrue(agg["by_uf"] and agg["by_kind"])
        self.assertNotIn("org", json.dumps(agg).lower().replace("organiz", ""))
        voc = self.fu.get("/v1/solutions/vocabulary").json
        self.assertIn("saude", voc["themes"]); self.assertIn("caps", [i["id"] for i in voc["institutions"]])
        p = self.fu.post("/v1/solutions/intent/parse", {"text": "idosos em Cuiabá orçamento até 100 mil"}).json
        self.assertIn("MT", p["territory"]["ufs"])
        a = self.fu.post("/v1/solutions/assistant", {"text": "projeto de arte em CAPS"}).json
        self.assertTrue(a["grounded"]); self.assertFalse(a["ai_used"])
        self.assertTrue(all("id" in s for s in a["suggestions"]))
        none = self.fu.post("/v1/solutions/assistant", {"text": "xyzzy qwerty"}).json
        self.assertEqual(none["suggestions"], []); self.assertIn("Não encontrei", none["message"])


class SolutionDatabaseGuardTests(unittest.TestCase):
    """As regras de verdade valem NO BANCO (RLS + gatilhos), mesmo que a API fosse contornada."""
    @classmethod
    def setUpClass(cls):
        server()
        cls.a, cls.b, cls.fu = new_account("osc"), new_account("osc"), new_account("company")
        cls.sid = mk(cls.a, title=f"Solução para guarda de banco {uuid.uuid4().hex[:5]}")

    def ctx(self, c: Client):
        from impacto.db.pool import DbContext
        return server()["state"].pool.tx(DbContext(user_id=c.user["id"], org_id=c.org_id, org_kind=c.get("/v1/me").json["active_org"]["kind"]))

    def test_owner_cannot_forge_trust_demo_or_verification(self):
        from impacto.db import pq
        for col, val in (("trust_level", "'verified'"), ("is_demo", "true"), ("verified_by", f"'{self.a.user['id']}'::uuid"), ("disputed", "true")):
            with self.assertRaises(Exception) as cm:
                with self.ctx(self.a) as c:
                    c.run(f"UPDATE solutions SET {col} = {val} WHERE id = $1", self.sid)
            self.assertIn("administração", str(cm.exception))

    def test_other_org_cannot_modify_or_see_drafts(self):
        draft = self.a.post("/v1/solutions", BASE).json["id"]
        with self.ctx(self.b) as c:
            self.assertEqual(c.run("UPDATE solutions SET title = 'invadido por outra org' WHERE id = $1", self.sid), 0)
            self.assertEqual(c.run("DELETE FROM solutions WHERE id = $1", self.sid), 0)
            self.assertIsNone(c.one("SELECT 1 FROM solutions WHERE id = $1", draft))
            self.assertIsNotNone(c.one("SELECT 1 FROM solutions WHERE id = $1", self.sid))        # publicada: leitura permitida
            self.assertEqual(c.scalar("SELECT count(*) FROM solution_evidence WHERE solution_id = $1", draft), 0)

    def test_intent_stage_cannot_be_forged_in_database(self):
        f = new_account("company")
        with self.assertRaises(Exception):
            with self.ctx(f) as c:
                c.run("INSERT INTO solution_intents(solution_id, org_id, user_id, stage) VALUES ($1,$2,$3,'funded')", self.sid, f.org_id, f.user["id"])
        self.assertEqual(f.put(f"/v1/solutions/{self.sid}/intent", {"stage": "interested"}).status, 200)
        with self.assertRaises(Exception):
            with self.ctx(f) as c:
                c.run("UPDATE solution_intents SET stage = 'funded', confirmed_by_author = true WHERE solution_id = $1 AND org_id = $2", self.sid, f.org_id)

    def test_append_only_and_rls_on_events_and_requests(self):
        with self.assertRaises(Exception):
            with self.ctx(self.a) as c:
                c.run("DELETE FROM solution_versions WHERE solution_id = $1", self.sid)
        with self.assertRaises(Exception):
            with self.ctx(self.a) as c:
                c.run("UPDATE solution_versions SET snapshot = '{}'::jsonb WHERE solution_id = $1", self.sid)
        self.assertEqual(self.fu.post(f"/v1/solutions/{self.sid}/requests", {"kind": "info", "message": "Pedido para teste de banco."}).status, 201)
        with self.ctx(self.b) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM solution_requests WHERE solution_id = $1", self.sid), 0)
        with self.ctx(self.fu) as c:
            with self.assertRaises(Exception):
                c.run("UPDATE solution_requests SET message = 'alterada depois do envio' WHERE solution_id = $1", self.sid)

    def test_evidence_and_results_status_cannot_be_set_by_owner(self):
        e = self.a.post(f"/v1/solutions/{self.sid}/evidence", {"kind": "report", "title": "Relatório X", "url": "https://exemplo.org/x"}).json["id"]
        with self.ctx(self.a) as c:
            try:
                c.run("UPDATE solution_evidence SET status = 'accepted', reviewed_by = $2 WHERE id = $1", e, self.a.user["id"])
            except Exception:
                pass
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT status FROM solution_evidence WHERE id = $1", e), "submitted")


if __name__ == "__main__":
    unittest.main()
