"""v0.28.0 — motor de originalidade, similaridade, complementaridade e integridade do financiamento (ADR-350).

Unidade (sem banco): as oito dimensões, as leituras separadas, o conjunto de avaliação com precisão/recall para o
indício de reprodução textual e de sobreposição de despesa, e a gravação da evidência em docs/evidence.
Integração (HTTP + PostgreSQL, RLS real): confidencialidade (projeto de outra organização em rascunho → 404 genérico
e só contagem agregada), isolamento, cache por versão, contestação com revisão humana, explicabilidade, desempenho
em volume, e a prova de que nada disto toca match, reputação ou financiamento.
"""
from __future__ import annotations

import datetime as dt
import json
import time
import unittest

from impacto.engines.similarity import engine as E
from tests.support import ROOT, db_system, grant_premium, make_admin, new_account

EVIDENCE = ROOT / "docs" / "evidence" / "similarity_eval_v0280.json"


def _p(**kw) -> dict:
    base = {"id": kw.get("id", "x"), "title": "Leitura no bairro", "summary": "Reforço de leitura para crianças da rede pública com mediadores voluntários.",
            "problem": "Crianças do bairro não têm contraturno nem acesso a livros adequados à idade.",
            "objectives": "Oferecer reforço de leitura orientada a trinta crianças três vezes por semana durante um ano.",
            "methodology": "Oficinas de leitura mediada com acervo itinerante e acompanhamento pedagógico mensal.",
            "causes": ["educacao"], "ods": [4], "territory": "BR-MT-5103403", "uf": "MT", "city": "Cuiabá",
            "beneficiaries_description": "crianças de 7 a 10 anos da rede pública", "beneficiaries_count": 30,
            "starts_on": dt.date(2026, 3, 1), "ends_on": dt.date(2027, 2, 28), "budget_total_cents": 200_000,
            "budget_items": [{"description": "Acervo de livros", "category": None, "total_cents": 50_000},
                             {"description": "Mediadores (bolsa)", "category": None, "total_cents": 150_000}],
            "calls": [], "funders": [], "indicator_names": ["Crianças com frequência >= 75%"], "lat": None, "lng": None,
            "org_name": "OSC", "visibility": "published"}
    base.update(kw)
    return base


# conjunto de avaliação rotulado: (a, b, reprodução_textual_esperada, duplicidade_despesa_esperada, complementaridade_esperada)
EVAL = [
    ("legítimos semelhantes (mesma causa, mesmo tipo, textos próprios)", _p(id="a1"),
     _p(id="b1", title="Biblioteca viva", summary="Clube de leitura semanal para crianças com oficinas de contação de histórias e empréstimo de livros.",
        problem="Baixo hábito de leitura entre crianças da periferia e pouca oferta cultural no contraturno.",
        objectives="Formar um clube de leitura com vinte crianças e realizar encontros semanais ao longo do ano letivo.",
        methodology="Contação de histórias, rodas de leitura e empréstimo domiciliar com registro de frequência.",
        territory="BR-MT-5107602", city="Rondonópolis", budget_items=[{"description": "Livros infantis", "category": None, "total_cents": 40_000}],
        starts_on=dt.date(2026, 8, 1), ends_on=dt.date(2027, 7, 31)), False, False, True),
    ("cópia textual com pequenas alterações", _p(id="a2"),
     _p(id="b2", title="Leitura no bairro 2", summary="Reforço de leitura para crianças da rede pública com mediadores voluntários da comunidade.",
        objectives="Oferecer reforço de leitura orientada a trinta crianças três vezes por semana durante um ano letivo.",
        methodology="Oficinas de leitura mediada com acervo itinerante e acompanhamento pedagógico mensal da equipe.",
        territory="BR-MT-5103403"), True, True, False),
    ("distintos no mesmo território", _p(id="a3"),
     _p(id="b3", title="Horta comunitária", summary="Produção de alimentos orgânicos em terreno cedido pela associação de moradores.",
        problem="Insegurança alimentar e terrenos ociosos no bairro.", objectives="Implantar uma horta de 400 m2 e distribuir cestas a quarenta famílias.",
        methodology="Mutirões quinzenais, capacitação em agroecologia e distribuição mensal.", causes=["seguranca_alimentar"], ods=[2],
        beneficiaries_description="famílias em situação de insegurança alimentar", budget_items=[{"description": "Sementes e insumos", "category": None, "total_cents": 30_000}],
        indicator_names=["Famílias atendidas"]), False, False, False),
    ("semelhantes em territórios diferentes (mesmo desenho, texto próprio)", _p(id="a4"),
     _p(id="b4", title="Ler para crescer", summary="Apoio à leitura de crianças de escolas públicas com voluntários treinados como mediadores.",
        problem="Alunos do ensino fundamental sem apoio de leitura fora da escola e sem acervo acessível.",
        objectives="Acompanhar trinta crianças em reforço de leitura orientada, três encontros semanais, por um ano.",
        methodology="Encontros de leitura mediada, acervo circulante entre as turmas e acompanhamento pedagógico mensal.",
        territory="BR-PA-1501402", uf="PA", city="Belém", starts_on=dt.date(2026, 3, 1), ends_on=dt.date(2027, 2, 28)), False, False, True),
    ("complementares: mesma causa, abordagem diferente, mesmo território", _p(id="a5"),
     _p(id="b5", title="Formação de mediadores de leitura", summary="Curso para formar jovens mediadores de leitura que atuarão em escolas do bairro.",
        problem="Faltam mediadores formados para as iniciativas de leitura existentes.", objectives="Formar vinte jovens mediadores em quatro meses.",
        methodology="Curso presencial de 60 horas com estágio supervisionado em escolas parceiras.",
        beneficiaries_description="jovens de 16 a 24 anos", budget_items=[{"description": "Formadores", "category": None, "total_cents": 80_000}],
        indicator_names=["Mediadores formados"]), False, False, True),
    ("dados incompletos", _p(id="a6"),
     _p(id="b6", title="Projeto sem detalhes", summary=None, problem=None, objectives=None, methodology=None, territory=None, uf=None,
        beneficiaries_description=None, starts_on=None, ends_on=None, budget_items=[], indicator_names=[]), False, False, False),
]


class EngineUnitTests(unittest.TestCase):

    def test_every_dimension_is_reported_separately_with_factors_and_data_quality(self):
        r = E.compare(_p(id="a"), _p(id="b", title="Outro"))
        self.assertEqual(set(r["dimensions"]), set(E.DIMENSIONS))
        for d in r["dimensions"].values():
            self.assertIn("score", d)
            self.assertIn("factors", d)
            self.assertIn(d["data_quality"], ("good", "fair", "poor"))
        self.assertTrue(r["human_review_required"])
        self.assertIn("≠ plágio ≠ fraude", r["disclaimer"])
        self.assertNotIn("overall", r, "não existe percentual único")

    def test_textual_reproduction_is_an_indication_never_a_verdict(self):
        a, b = EVAL[1][1], EVAL[1][2]
        r = E.compare(a, b)
        self.assertTrue(r["readings"]["possible_textual_reproduction"])
        self.assertTrue(any(x["action"] == "request_human_review" for x in r["recommendations"]))
        self.assertTrue(any(x["action"] == "contest_or_correct" for x in r["recommendations"]))
        txt = json.dumps(r, ensure_ascii=False).lower()
        self.assertNotIn("plágio confirmado", txt)
        self.assertNotIn("fraude confirmada", txt)

    def test_expense_overlap_needs_shared_items_territory_and_time(self):
        same = E.compare(EVAL[1][1], EVAL[1][2])
        self.assertTrue(same["readings"]["possible_expense_duplication"])
        self.assertIn("Acervo de livros".lower(), [x.lower() for x in same["dimensions"]["budget"]["shared_items"]][0])
        far = E.compare(EVAL[3][1], EVAL[3][2])   # mesmos itens, outro estado
        self.assertFalse(far["readings"]["possible_expense_duplication"])

    def test_incomplete_data_gives_low_confidence_and_names_the_limitations(self):
        r = E.compare(EVAL[5][1], EVAL[5][2])
        self.assertEqual(r["confidence"], "low")
        self.assertGreaterEqual(len(r["limitations"]), 4)
        self.assertTrue(any(x["action"] == "improve_methodology" for x in r["recommendations"]))

    def test_multiple_funding_sources_are_declared_not_accused(self):
        a = _p(id="a", calls=["c1"], funders=["f1", "f2"])
        b = _p(id="b", title="Outro", calls=["c1"], funders=["f2"])
        r = E.compare(a, b)
        self.assertTrue(r["readings"]["same_funding_source"])
        self.assertTrue(any(x["action"] == "declare_sources" for x in r["recommendations"]))

    def test_originality_names_what_is_new_and_complementarity_candidates(self):
        subj = EVAL[4][1]
        res = E.originality(subj, [EVAL[4][2], EVAL[2][2], EVAL[0][2]])
        self.assertEqual(res["candidates_compared"], 3)
        self.assertIn(res["originality_reading"], ("no_close_match", "close_matches_exist", "crowded_space"))
        self.assertTrue(res["complementarity_candidates"])
        self.assertTrue(res["human_review_required"])

    def test_the_evaluation_set_precision_recall_and_evidence_file(self):
        """Métricas do conjunto rotulado (pequeno e declarado): escritas em docs/evidence para o relatório."""
        rows = []
        tp = fp = fn = 0
        tp2 = fp2 = fn2 = 0
        for label, a, b, rep, dup, comp in EVAL:
            r = E.compare(a, b)
            got_rep, got_dup, got_comp = r["readings"]["possible_textual_reproduction"], r["readings"]["possible_expense_duplication"], r["readings"]["complementarity"]
            tp += got_rep and rep
            fp += got_rep and not rep
            fn += (not got_rep) and rep
            tp2 += got_dup and dup
            fp2 += got_dup and not dup
            fn2 += (not got_dup) and dup
            rows.append({"case": label, "expected": {"textual_reproduction": rep, "expense_duplication": dup, "complementarity": comp},
                         "got": {"textual_reproduction": got_rep, "expense_duplication": got_dup, "complementarity": got_comp},
                         "confidence": r["confidence"], "dimensions": {k: v["score"] for k, v in r["dimensions"].items()}})
        prec = tp / (tp + fp) if tp + fp else 1.0
        rec = tp / (tp + fn) if tp + fn else 1.0
        prec2 = tp2 / (tp2 + fp2) if tp2 + fp2 else 1.0
        rec2 = rec2 = tp2 / (tp2 + fn2) if tp2 + fn2 else 1.0
        comp_ok = sum(1 for row in rows if row["expected"]["complementarity"] == row["got"]["complementarity"])
        ev = {"engine_version": E.ENGINE_VERSION, "cases": len(rows),
              "textual_reproduction": {"precision": prec, "recall": rec, "tp": tp, "fp": fp, "fn": fn},
              "expense_duplication": {"precision": prec2, "recall": rec2, "tp": tp2, "fp": fp2, "fn": fn2},
              "complementarity_agreement": f"{comp_ok}/{len(rows)}",
              "note": "Conjunto de avaliação PEQUENO e rotulado à mão (6 pares): mede se os limiares do motor separam os casos "
                      "declarados; não é medida de desempenho em base real, que ainda não existe. Alertas de alto impacto exigem revisão humana.",
              "rows": rows}
        EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE.write_text(json.dumps(ev, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
        self.assertEqual((prec, rec), (1.0, 1.0), ev["textual_reproduction"])
        self.assertEqual((prec2, rec2), (1.0, 1.0), ev["expense_duplication"])
        self.assertGreaterEqual(comp_ok, 5, [r["case"] for r in rows if r["expected"]["complementarity"] != r["got"]["complementarity"]])


def _projeto(c, **kw) -> str:
    body = {"title": "Leitura no bairro", "summary": "Reforço de leitura para crianças da rede pública com mediadores voluntários.",
            "problem": "Crianças do bairro não têm contraturno nem acesso a livros adequados à idade.",
            "objectives": "Oferecer reforço de leitura orientada a trinta crianças três vezes por semana durante um ano.",
            "methodology": "Oficinas de leitura mediada com acervo itinerante e acompanhamento pedagógico mensal.",
            "territory": "BR-MT-5103403", "causes": ["educacao"], "ods": [4], "beneficiaries_description": "crianças de 7 a 10 anos",
            "beneficiaries_count": 30, "budget_total_cents": 200_000,
            "starts_on": (dt.date.today() - dt.timedelta(days=10)).isoformat(), "ends_on": (dt.date.today() + dt.timedelta(days=200)).isoformat()}
    body.update(kw)
    r = c.post("/v1/projects", body)
    assert r.status == 201, r.json
    pid = r.json["id"]
    assert c.post(f"/v1/projects/{pid}/budget-items", {"description": "Acervo de livros", "quantity": 1, "unit_cost_cents": 50_000}).status == 201
    return pid


class IntegrationTests(unittest.TestCase):

    def test_a_draft_of_another_org_is_never_compared_only_counted_with_k_anonymity(self):
        a, b = new_account("osc"), new_account("osc")
        mine = _projeto(a)
        theirs = _projeto(b, title="Rascunho confidencial de outra OSC")   # rascunho: só B enxerga
        r = a.post(f"/v1/projects/{mine}/similarity", {"kind": "pair", "compared_project_ids": [theirs]})
        self.assertEqual(r.status, 404, "projeto invisível → 404 genérico (não revela existência)")
        r = a.post(f"/v1/projects/{mine}/similarity", {"kind": "single"})
        self.assertEqual(r.status, 200, r.json)
        shown = [p["project_id"] for p in r.json["result"]["shown"]]
        self.assertNotIn(theirs, shown)
        self.assertNotIn("Rascunho confidencial", json.dumps(r.json, ensure_ascii=False))
        # com menos de 3 rascunhos alheios na mesma causa/território, a contagem agregada é ZERO (k-anonimato)
        self.assertEqual(r.json["result"]["hidden_overlap_count"], 0)
        for i in range(3):
            _projeto(new_account("osc"), title=f"Rascunho alheio {i}")
        with db_system() as d:
            d.run("INSERT INTO ai_credit_ledger(org_id, delta, reason, bucket, idempotency_key) VALUES ($1, 500, 'purchase', 'purchased', $2)", a.org_id, "t:" + a.org_id)
        a.patch(f"/v1/projects/{mine}", {"summary": "Resumo alterado para forçar nova análise."})
        r2 = a.post(f"/v1/projects/{mine}/similarity", {"kind": "single"})
        self.assertEqual(r2.status, 200, r2.json)
        self.assertGreaterEqual(r2.json["result"]["hidden_overlap_count"], 3)
        self.assertIn("k-anonimato", r2.json["result"]["hidden_overlap_note"])

    def test_published_projects_are_compared_and_the_analysis_is_explainable(self):
        from tests.test_v080 import published_project
        a, b = new_account("osc"), new_account("osc")
        mine = _projeto(a)
        pub = published_project(b, title="Leitura na praça", cause="educacao", territory="BR-MT-5103403")
        r = a.post(f"/v1/projects/{mine}/similarity", {"kind": "pair", "compared_project_ids": [pub]})
        self.assertEqual(r.status, 200, r.json)
        cmp_ = r.json["result"]["comparison"]
        self.assertEqual(set(cmp_["dimensions"]), set(E.DIMENSIONS))
        self.assertTrue(cmp_["dimensions"]["territory"]["factors"])
        self.assertIn(r.json["confidence"], ("low", "medium", "high"))
        self.assertTrue(r.json["human_review_required"])
        self.assertEqual(r.json["execution"]["funding_source"], "promotional")
        got = a.get(f"/v1/similarity/analyses/{r.json['id']}")
        self.assertEqual(got.status, 200)
        self.assertEqual(got.json["execution"]["state"], "reconciled")
        # outra organização não lê a análise
        self.assertEqual(b.get(f"/v1/similarity/analyses/{r.json['id']}").status, 404)

    def test_the_set_analysis_prices_per_project_and_refuses_above_the_limit(self):
        from tests.test_v080 import published_project
        gov = new_account("government")
        with db_system() as d:
            d.run("INSERT INTO ai_credit_ledger(org_id, delta, reason, bucket, idempotency_key) VALUES ($1, 2000, 'purchase', 'purchased', $2)", gov.org_id, "t:" + gov.org_id)
        subj = published_project(new_account("osc"), title="Projeto base", territory="BR-MT")
        others = [published_project(new_account("osc"), title=f"Projeto {i}", territory="BR-MT") for i in range(3)]
        pv = gov.post("/v1/ai/preview", {"operation_code": "similarity.set", "units": 3}).json
        self.assertEqual(pv["credits_required"], 99 + 10 * 3)
        r = gov.post(f"/v1/projects/{subj}/similarity", {"kind": "set", "compared_project_ids": others})
        self.assertEqual(r.status, 200, r.json)
        self.assertEqual(len(r.json["result"]["set"]), 3)
        self.assertEqual(r.json["execution"]["charged_credits"], 129)
        too_many = gov.post(f"/v1/projects/{subj}/similarity", {"kind": "set", "compared_project_ids": others * 7})
        self.assertIn(too_many.status, (422, 200))   # ids repetidos são deduplicados; 21+ distintos seriam recusados
        self.assertEqual(gov.post("/v1/ai/preview", {"operation_code": "similarity.set", "units": 21}).status, 422)

    def test_a_changed_version_invalidates_the_cache_and_a_dispute_goes_to_human_review(self):
        a = new_account("osc")
        mine = _projeto(a)
        r1 = a.post(f"/v1/projects/{mine}/similarity", {"kind": "complementarity"})
        self.assertEqual(r1.status, 200, r1.json)
        r2 = a.post(f"/v1/projects/{mine}/similarity", {"kind": "complementarity"})
        self.assertTrue(r2.json["cached"])
        a.patch(f"/v1/projects/{mine}", {"methodology": "Metodologia revista: tutoria individual."})
        r3 = a.post(f"/v1/projects/{mine}/similarity", {"kind": "complementarity"})
        self.assertFalse(r3.json["cached"])
        d = a.post(f"/v1/similarity/analyses/{r3.json['id']}/dispute", {"reason": "A comparação com o projeto X ignora que o território é outro distrito."})
        self.assertEqual(d.status, 201, d.json)
        self.assertEqual(a.post(f"/v1/similarity/analyses/{r3.json['id']}/dispute", {"reason": "Segunda contestação enquanto a primeira está aberta."}).status, 409)
        adm, _ = make_admin()
        lst = adm.get("/v1/admin/ai/disputes").json["items"]
        self.assertTrue(any(x["id"] == d.json["id"] for x in lst))
        rv = adm.post(f"/v1/admin/ai/disputes/{d.json['id']}/review", {"outcome": "reviewed_corrected", "reviewer_note": "Procede: territórios distintos; análise anotada."})
        self.assertEqual(rv.status, 200, rv.json)
        self.assertEqual(a.get(f"/v1/similarity/analyses/{r3.json['id']}").json["disputes"][0]["status"], "reviewed_corrected")

    def test_volume_fifty_visible_candidates_under_two_seconds(self):
        a = new_account("osc")
        mine = _projeto(a)
        pubs = [new_account("osc") for _ in range(3)]   # 20 projetos ativos por pacote: três organizações publicadoras
        for pub in pubs:
            grant_premium(pub)
        for i in range(50):
            pub = pubs[i % 3]
            r = pub.post("/v1/projects", {"title": f"Leitura {i}", "summary": "Resumo do projeto", "territory": "BR-MT-5103403", "causes": ["educacao"], "ods": [4], "beneficiaries_count": 30})
            self.assertEqual(r.status, 201, (i, r.json))
            self.assertEqual(pub.post(f"/v1/projects/{r.json['id']}/budget-items", {"description": "Item", "quantity": 1, "unit_cost_cents": 1000}).status, 201)
            pr = pub.post(f"/v1/projects/{r.json['id']}/publish")
            self.assertEqual(pr.status, 200, (i, pr.json))
        t0 = time.perf_counter()
        r = a.post(f"/v1/projects/{mine}/similarity", {"kind": "single"})
        dt_ = time.perf_counter() - t0
        self.assertEqual(r.status, 200, r.json)
        self.assertGreaterEqual(r.json["result"]["candidates_compared"], 50)
        self.assertLess(dt_, 2.0, f"{dt_:.2f}s para {r.json['result']['candidates_compared']} candidatos")
        with db_system() as d:
            lat = d.scalar("SELECT latency_ms FROM ai_executions WHERE id = $1", r.json["execution"]["id"])
        self.assertIsNotNone(lat)

    def test_similarity_touches_neither_match_nor_reputation_nor_funding(self):
        """Arquitetura: o motor de match e a reputação não importam similaridade; a análise não escreve nessas tabelas."""
        from pathlib import Path
        pkg = Path(E.__file__).resolve().parents[2]
        for f in list((pkg / "engines" / "match").rglob("*.py")) + list((pkg / "network").rglob("*.py")) + [pkg / "trust" / "economy.py"]:
            self.assertNotIn("similarity", f.read_text(encoding="utf-8"), f"{f} depende do motor de similaridade")
        src = (pkg / "services" / "similarity.py").read_text(encoding="utf-8") + (pkg / "engines" / "similarity" / "engine.py").read_text(encoding="utf-8")
        for tabela in ("reputation", "match_runs", "allocation_payouts", "applications SET", "projects SET"):
            self.assertNotIn(tabela, src)
