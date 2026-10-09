"""v0.29.0 — a busca da Central tem conjunto de avaliação versionado, baseline MEDIDO e não regride em silêncio.

Mede, por HTTP real contra o servidor de teste com o conteúdo semeado PUBLICADO (quatro olhos respeitado: autor ≠ revisor):
precision@5, recall@5, MRR, nDCG@5, hit@1, taxa de consulta sem resultado, abstenção correta nas consultas sem resposta, latência p50/p95.
Grava `docs/evidence/search_eval_v0290.json` e compara com os pisos de `config/search_eval.json`. Também prova que o assistente se
abstém nas consultas sem resposta. O conjunto é pequeno e sintético — o arquivo de evidência diz isso.
"""
from __future__ import annotations

import json
import time
import unittest
from urllib.parse import quote

from impacto.engines.knowledge import evaluation as EV
from tests.support import ROOT, Client, db_system, new_account, server

CFG = json.loads((ROOT / "config" / "search_eval.json").read_text(encoding="utf-8"))
EVIDENCE = ROOT / "docs" / "evidence" / "search_eval_v0290.json"


def ensure_seed_published() -> None:
    """Publica o conteúdo inicial (demo, educacional) com autor e revisor distintos; idempotente por slug."""
    from impacto.services import kb_seed
    author, reviewer = new_account("osc"), new_account("osc")
    with db_system() as d:
        kb_seed.import_seed(d, author_id=author.user["id"], reviewer_id=reviewer.user["id"], publish=True)
        # se uma rodada anterior semeou em rascunho (test_v0120), publica a versão 1 dos artigos da semente que ainda estão em rascunho
        d.run("UPDATE kb_article_versions v SET status = 'published', approved_by = $1, approved_at = now(), published_at = now()"
              " FROM kb_articles a WHERE a.id = v.article_id AND v.version = 1 AND v.status = 'draft' AND a.demo AND a.live_version_id IS NULL"
              " AND v.author_id <> $1::uuid AND a.slug = ANY($2::text[])", reviewer.user["id"], [x[0] for x in kb_seed.ARTICLES])
        d.run("UPDATE kb_faqs SET status = 'published', approved_by = $1, approved_at = now(), published_at = now(), last_reviewed_at = now()"
              " WHERE status = 'draft' AND demo AND author_id <> $1::uuid AND question = ANY($2::text[])", reviewer.user["id"], [x[0] for x in kb_seed.FAQS])
        d.run("UPDATE kb_resources SET status = 'published', approved_by = $1, approved_at = now(), published_at = now(), last_reviewed_at = now()"
              " WHERE status = 'draft' AND demo AND author_id <> $1::uuid AND slug = ANY($2::text[])", reviewer.user["id"], [x[0] for x in kb_seed.RESOURCES])


def restore_seed_to_draft() -> None:
    """Devolve a semente ao estado de rascunho (publicada → arquivada → rascunho, transições permitidas) para não alterar o que outros
    módulos esperam do banco compartilhado da suíte (test_v0120: a semente importada nunca está viva)."""
    from impacto.services import kb_seed
    with db_system() as d:
        slugs = [x[0] for x in kb_seed.ARTICLES]
        for st in ("archived", "draft"):
            d.run("UPDATE kb_article_versions v SET status = $1 FROM kb_articles a WHERE a.id = v.article_id AND a.demo AND a.slug = ANY($2::text[]) AND v.status <> 'retracted'", st, slugs)
            d.run("UPDATE kb_faqs SET status = $1 WHERE demo AND question = ANY($2::text[]) AND status <> 'retracted'", st, [x[0] for x in kb_seed.FAQS])
            d.run("UPDATE kb_resources SET status = $1 WHERE demo AND slug = ANY($2::text[]) AND status <> 'retracted'", st, [x[0] for x in kb_seed.RESOURCES])
        d.run("UPDATE kb_articles SET live_version_id = NULL, search_doc = NULL WHERE demo AND slug = ANY($1::text[])", slugs)


def judged_corpus() -> set[str]:
    """As chaves do corpus ROTULADO (a semente): slugs de artigos e recursos e `faq:<pergunta>`."""
    from impacto.services import kb_seed
    return {x[0] for x in kb_seed.ARTICLES} | {x[0] for x in kb_seed.RESOURCES} | {"faq:" + x[0] for x in kb_seed.FAQS}


def run_eval(client: Client, k: int) -> list[dict]:
    """Pede 4k resultados e pontua só os do corpus rotulado. Na suíte completa, outros módulos publicam artigos de teste
    ("Prestação de contas passo a passo E2E", slugs aleatórios…) no mesmo banco; eles não têm rótulo e, mantidos no ranking,
    fariam a medição depender da ORDEM dos testes (achado da 1ª regressão v0.29.0: P@5 0,1875 contra piso 0,19). Como a
    pontuação da busca é por documento (FTS/trigram/tesauro não olham os vizinhos), remover os não rotulados equivale a medir
    sobre a semente sozinha. A evidência registra quantos foram removidos."""
    corpus = judged_corpus()
    out = []
    for q in CFG["queries"]:
        t0 = time.perf_counter()
        r = client.get(f"/v1/help/search?q={quote(q['q'])}&limit={4 * k}")
        ms = (time.perf_counter() - t0) * 1000
        assert r.status == 200, (q, r)
        all_keys = [EV.item_key(i) for i in r.json["items"]]
        ranked = [x for x in all_keys if x in corpus]
        out.append({"query": q["q"], "kind": q["kind"], "relevant": q["relevant"], "acceptable": q.get("acceptable", []), "ranked": ranked[:k],
                    "unjudged_removed": len(all_keys) - len(ranked), "latency_ms": round(ms, 1), "abstained": not r.json["items"]})
    return out


class SearchEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        ensure_seed_published()
        cls.anon = Client()
        cls.osc = new_account("osc")                       # perfil medido: OSC autenticada (vê conteúdo 'authenticated' e do seu público)
        cls.k = int(CFG["k"])
        cls.results = run_eval(cls.osc, cls.k)
        cls.metrics = EV.summarize(cls.results, k=cls.k)
        cls.anon_results = run_eval(cls.anon, cls.k)       # anônimo: só conteúdo público — mede que o restrito NÃO vaza
        cls.anon_metrics = EV.summarize(cls.anon_results, k=cls.k)
        # evidência: o que foi medido, com que corpus e que limites
        with db_system() as d:
            corpus = {"articles_published": d.scalar("SELECT count(*) FROM kb_articles WHERE live_version_id IS NOT NULL"),
                      "faqs_published": d.scalar("SELECT count(*) FROM kb_faqs WHERE status = 'published'"),
                      "resources_published": d.scalar("SELECT count(*) FROM kb_resources WHERE status = 'published'")}
        from impacto.engines.knowledge import search as KS
        EVIDENCE.write_text(json.dumps({
            "engine": KS.ENGINE_VERSION, "weights": KS.WEIGHTS, "min_score": KS.MIN_SCORE, "answer_min": KS.ANSWER_MIN,
            "eval_set": CFG["version"], "queries": len(CFG["queries"]), "corpus": corpus, "profile": "osc autenticada", "metrics": cls.metrics,
            "anonymous_metrics": cls.anon_metrics,
            "unjudged_removed_total": sum(r["unjudged_removed"] for r in cls.results),
            "scoring_note": "só itens do corpus rotulado (semente) entram no ranking pontuado; conteúdo criado por outros testes no mesmo banco é removido antes de pontuar",
            "per_query": [{"q": r["query"], "kind": r["kind"], "top": r["ranked"][:3], "hit": bool(r["ranked"][:1] and r["ranked"][0] in set(r["relevant"])) if r["relevant"] else None,
                           "found_any_relevant": any(x in set(r["relevant"]) for x in r["ranked"]) if r["relevant"] else None, "abstained": r["abstained"]} for r in cls.results],
            "what_this_is_not": ["desempenho em base real (o corpus é a semente demo/educacional publicada só para a medição)",
                                 "julgamento por mais de uma pessoa (rótulos feitos à mão por quem escreveu o conjunto)",
                                 "medida de embeddings ou de modelo (não existem; a busca é determinística)"],
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        restore_seed_to_draft()

    def test_the_metrics_do_not_fall_below_the_recorded_baseline(self):
        f, m = CFG["floors"], self.metrics
        self.assertGreaterEqual(m["precision_at_5"], f["precision_at_5"], m)
        self.assertGreaterEqual(m["recall_at_5"], f["recall_at_5"], m)
        self.assertGreaterEqual(m["mrr"], f["mrr"], m)
        self.assertGreaterEqual(m["ndcg_at_5"], f["ndcg_at_5"], m)
        self.assertGreaterEqual(m["hit_at_1"], f["hit_at_1"], m)
        self.assertLessEqual(m["zero_result_rate"], f["zero_result_rate_max"], m)
        self.assertGreaterEqual(m["correct_abstention_rate"], f["correct_abstention_rate"], m)
        self.assertLessEqual(m["latency_ms"]["p95"], f["latency_p95_ms_max"], m["latency_ms"])

    def test_restricted_content_never_appears_to_an_anonymous_visitor(self):
        restricted = {"como-fazer-cotacoes", "como-cadastrar-projeto", "entender-conformidade", "checklist-prestacao-contas", "modelo-plano-trabalho"}
        for r in self.anon_results:
            self.assertFalse(restricted & set(r["ranked"]), (r["query"], r["ranked"]))
        self.assertLess(self.anon_metrics.get("recall_at_5", 0), self.metrics["recall_at_5"], "o anônimo vê menos porque o restrito fica de fora")

    def test_unanswerable_queries_make_the_assistant_abstain(self):
        for q in [x for x in CFG["queries"] if x["kind"] == "unanswerable"]:
            r = self.anon.post("/v1/help/assistant", {"question": q["q"]}).json
            self.assertIsNone(r["answer"], q["q"])
            self.assertFalse(r["ai_used"])

    def test_the_evidence_file_declares_corpus_metrics_and_limits(self):
        ev = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(ev["queries"], len(CFG["queries"]))
        self.assertIn("precision_at_5", ev["metrics"])
        self.assertTrue(any("base real" in x for x in ev["what_this_is_not"]))
        self.assertGreater(ev["corpus"]["articles_published"], 10)
