"""v0.29.0 — camada de conhecimento: base v0.26.0 reconciliada, proveniência com direitos de uso, retirada, assistente que se abstém e fila editorial.

O que se prova (HTTP + PostgreSQL reais; nada é mock):
  A. a base `knowledge-base/` está no repositório, íntegra (12 relatórios, 58 controles, manifesto coerente) e a RECONCILIAÇÃO com o código
     cita só testes que existem (conferido por AST) — nenhum controle é "implementado" sem teste;
  B. fontes: classe O/A/V/H/D, direitos por operação ('unknown' bloqueia), quatro olhos na verificação, retirada terminal — tudo pelo banco;
  C. citações: trecho só com direito explícito, hash conferido pelo banco, só em versão rascunho; o leitor vê classe e avisos;
  D. retirada de conteúdo: motivo obrigatório, só reviewer, some da busca/assistente/sitemap, não volta;
  E. assistente: DEMO, vencido e terceiros NÃO fundamentam resposta (aparecem como excluídos, com motivo); cita exatamente a fonte usada;
     origem educacional é rotulada como educacional; pergunta ambígua devolve opções;
  F. fila editorial: lacuna de busca (sem texto livre), 'não ajudou', relato de erro e vencidos viram itens com dedupe; concluir exige resolução;
  G. arquitetura: busca e motores não leem reputação nem planos (sem pay-to-rank, sem reputação única no ranking).
"""
from __future__ import annotations

import ast
import csv
import hashlib
import json
import re
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from tests.support import ROOT, Client, db_system, new_account, server
from tests.test_v0120_knowledge import article_body, publish_article, staff, uniq

KB = ROOT / "knowledge-base"


# ================================================================================================= A. base reconciliada
class KnowledgeBaseIsInTheRepositoryTests(unittest.TestCase):

    def test_the_v0260_base_is_versioned_and_whole(self):
        for f in ("MASTER-KNOWLEDGE-BASE.md", "KNOWLEDGE-MANIFEST.json", "LEGAL-APPLICABILITY-MATRIX.csv", "CHANGELOG.md", "CLAUDE-HANDOFF.md", "CONTROL-RECONCILIATION.json"):
            self.assertTrue((KB / f).exists(), f)
        reports = sorted(p.name for p in (KB / "research").glob("*.md"))
        self.assertEqual(len(reports), 12, reports)
        man = json.loads((KB / "KNOWLEDGE-MANIFEST.json").read_text(encoding="utf-8"))
        for entry in man["files"]:
            self.assertTrue((ROOT / entry["path"]).exists(), entry["path"])
        for p in man["source_reports"]:
            self.assertTrue((ROOT / p).exists(), p)
        self.assertEqual(len(man["domains"]), 12)
        self.assertEqual(set(man["taxonomy"]), {"O", "A", "V", "H", "D"})

    def test_the_matrix_has_58_controls_with_the_declared_columns(self):
        rows = list(csv.DictReader((KB / "LEGAL-APPLICABILITY-MATRIX.csv").open(encoding="utf-8")))
        self.assertEqual(len(rows), 58)
        self.assertEqual(list(rows[0].keys()), ["id", "module", "obligation", "classification", "source", "control", "test", "responsible", "review", "status"])
        self.assertTrue(all(r["classification"] in ("O", "A", "V", "H", "D") for r in rows))

    def test_the_reconciliation_cites_only_tests_that_exist_and_never_calls_untested_things_implemented(self):
        rec = json.loads((KB / "CONTROL-RECONCILIATION.json").read_text(encoding="utf-8"))
        ids = {r["id"] for r in csv.DictReader((KB / "LEGAL-APPLICABILITY-MATRIX.csv").open(encoding="utf-8"))}
        self.assertEqual(set(rec["controls"]), ids, "a reconciliação cobre exatamente os 58 controles da matriz")
        cache: dict[Path, ast.Module] = {}
        for cid, ctl in rec["controls"].items():
            self.assertIn(ctl["state"], ("IMPLEMENTED_TESTED", "PARTIAL", "NOT_IMPLEMENTED", "BLOCKED_EXTERNAL"), cid)
            if ctl["state"] == "IMPLEMENTED_TESTED":
                self.assertTrue(ctl["tests"], f"{cid}: implementado sem teste não existe")
            for ref in ctl["tests"]:
                parts = ref.split("::")
                path = ROOT / "backend" / parts[0]
                self.assertTrue(path.exists(), f"{cid}: {ref} — arquivo ausente")
                tree = cache.setdefault(path, ast.parse(path.read_text(encoding="utf-8")))
                if len(parts) == 3:
                    cls = next((x for x in tree.body if isinstance(x, ast.ClassDef) and x.name == parts[1]), None)
                    self.assertIsNotNone(cls, f"{cid}: {ref} — classe ausente")
                    self.assertTrue(any(isinstance(f, ast.FunctionDef) and f.name == parts[2] for f in cls.body), f"{cid}: {ref} — função ausente")
                else:
                    self.assertTrue(any(isinstance(f, ast.FunctionDef) and f.name == parts[1] for f in tree.body), f"{cid}: {ref} — função ausente")

    def test_no_document_of_the_base_claims_compliance_certification_or_homologation(self):
        forbidden = re.compile(r"\b(100% conforme|certificad[oa] pela ANPD|homologado pelo PNCP|LGPD compliant|totalmente conforme)\b", re.I)
        for p in [KB / "MASTER-KNOWLEDGE-BASE.md", KB / "CHANGELOG.md", KB / "CLAUDE-HANDOFF.md"]:
            txt = p.read_text(encoding="utf-8")
            for m in forbidden.finditer(txt):
                ctx = txt[max(0, m.start() - 700): m.end() + 40].replace("\n", " ")
                self.assertRegex(ctx, r"(não|nunca|proib|bloquear|sem evidência|Claims proibidos)", f"{p.name}: claim sem negação por perto: …{ctx}…")


# ================================================================================================= B/C/D. fontes, citações, retirada
class SourcesCitationsAndRetractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv, cls.sup = staff("editor"), staff("reviewer"), staff("support")
        cls.anon = Client()
        cls.user = new_account("osc")

    def _source(self, **kw) -> dict:
        body = {"key": uniq("fonte.teste"), "title": "Fonte de teste para proveniência", "publisher": "Teste", "url": "https://example.org/x",
                "source_type": "guidance", "klass": "A", "jurisdiction": "BR", "consulted_on": "2026-10-09",
                "rights": {"index": "allowed", "excerpt": "allowed", "store": "allowed"}, "review_due": "2026-12-01"}
        body.update(kw)
        r = self.ed.post("/v1/admin/content/sources", body)
        self.assertEqual(r.status, 201, r)
        return {**body, **r.json}

    def test_seeded_primary_sources_are_public_classified_and_unverified(self):
        r = self.anon.get("/v1/help/sources").json
        keys = {s["key"]: s for s in r["items"]}
        self.assertIn("br.lei.13709-2018", keys)
        lgpd = keys["br.lei.13709-2018"]
        self.assertEqual(lgpd["klass"], "O")
        self.assertEqual(lgpd["verification"], "unverified", "ninguém conferiu vigência: nasce não verificada")
        self.assertEqual(lgpd["rights"]["train"], "unknown")
        self.assertNotIn("train", lgpd["usable_for"])
        self.assertIn("excerpt", lgpd["usable_for"])
        self.assertIn("classificação editorial", r["notice"])
        self.assertEqual(keys["impacto.kb.master-0.26.0"]["klass"], "H")

    def test_unknown_right_blocks_the_excerpt_at_the_database(self):
        src = self._source(rights={"index": "allowed"})           # excerpt ausente → unknown
        art = self.ed.post("/v1/admin/content/articles", article_body(uniq("cit"))).json
        r = self.ed.post("/v1/admin/content/citations", {"object_type": "article_version", "object_id": art["version_id"], "source": src["key"],
                                                         "locator": "§ 2", "excerpt": "um trecho"})
        self.assertEqual(r.status, 403, r)
        self.assertEqual(r.json["code"], "excerpt_not_allowed")
        # sem trecho (só localizador) pode
        ok = self.ed.post("/v1/admin/content/citations", {"object_type": "article_version", "object_id": art["version_id"], "source": src["key"], "locator": "§ 2"})
        self.assertEqual(ok.status, 201, ok)
        self.assertFalse(ok.json["has_excerpt"])
        # e o banco recusa mesmo que a aplicação tente passar por cima
        with db_system() as d:
            with self.assertRaises(Exception):
                d.run("INSERT INTO kb_citations(object_type, object_id, source_id, excerpt, excerpt_sha256) VALUES ('article_version', $1, $2, 'x', $3)",
                      art["version_id"], src["id"], hashlib.sha256(b"x").hexdigest())

    def test_the_database_checks_the_excerpt_hash_and_only_drafts_accept_citations(self):
        src = self._source()
        art = self.ed.post("/v1/admin/content/articles", article_body(uniq("cit"))).json
        with db_system() as d:
            with self.assertRaises(Exception):   # hash errado
                d.run("INSERT INTO kb_citations(object_type, object_id, source_id, excerpt, excerpt_sha256) VALUES ('article_version', $1, $2, 'trecho', $3)",
                      art["version_id"], src["id"], "0" * 64)
        pub = publish_article(self.ed, self.rv)
        r = self.ed.post("/v1/admin/content/citations", {"object_type": "article_version", "object_id": pub["version_id"], "source": src["key"], "excerpt": "t"})
        self.assertIn(r.status, (409, 422, 500), "versão publicada é imutável: citação recusada")   # CHECK do gatilho

    def test_the_reader_sees_the_citation_with_class_and_notices(self):
        src = self._source(klass="H", title="Hipótese interna de produto X")
        slug = uniq("guia")
        art = self.ed.post("/v1/admin/content/articles", article_body(slug)).json
        self.assertEqual(self.ed.post("/v1/admin/content/citations", {"object_type": "article_version", "object_id": art["version_id"], "source": src["key"],
                                                                      "locator": "§ 3.1", "excerpt": "Trecho citado com direito registrado.", "claim": "Afirmação sustentada"}).status, 201)
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/article-versions/{art['version_id']}/transition", {"to": to}).status, 200)
        a = self.anon.get(f"/v1/help/articles/{slug}").json
        self.assertEqual(len(a["citations"]), 1)
        c = a["citations"][0]
        self.assertEqual(c["klass"], "H")
        self.assertEqual(c["klass_label"], "Hipótese de produto")
        self.assertIn("não é norma: hipótese de produto", c["notices"])
        self.assertIn("fonte ainda não conferida por outra pessoa", c["notices"])
        self.assertEqual(c["excerpt_sha256"], hashlib.sha256(b"Trecho citado com direito registrado.").hexdigest())
        pub = self.anon.get(f"/v1/help/sources/{src['key']}").json
        self.assertEqual(pub["cited_by"][0]["object_id"], art["version_id"])

    def test_whoever_registers_a_source_cannot_verify_it(self):
        src = self._source()
        ed_as_reviewer = staff("editor", "reviewer")
        s2 = ed_as_reviewer.post("/v1/admin/content/sources", {**{k: v for k, v in src.items() if k not in ("id", "key")}, "key": uniq("fonte.dup")}).json
        self.assertEqual(ed_as_reviewer.post(f"/v1/admin/content/sources/{s2['key']}/verify", {"verification": "verified"}).status, 403)
        with db_system() as d:
            with self.assertRaises(Exception):     # pelo banco também
                d.run("UPDATE kb_sources SET verification = 'verified', verified_by = created_by, verified_at = now() WHERE id = $1", s2["id"])
        ok = self.rv.post(f"/v1/admin/content/sources/{src['key']}/verify", {"verification": "verified", "note": "conferido no Planalto"})
        self.assertEqual(ok.status, 200, ok)
        self.assertEqual(self.anon.get(f"/v1/help/sources/{src['key']}").json["verification"], "verified")
        self.assertEqual(self.ed.post(f"/v1/admin/content/sources/{src['key']}/verify", {"verification": "verified"}).status, 403, "editor não verifica")

    def test_a_retracted_source_is_terminal_and_opens_follow_up_work(self):
        src = self._source()
        art = self.ed.post("/v1/admin/content/articles", article_body(uniq("cit"))).json
        self.ed.post("/v1/admin/content/citations", {"object_type": "article_version", "object_id": art["version_id"], "source": src["key"], "locator": "p. 1"})
        self.assertEqual(self.rv.post(f"/v1/admin/content/sources/{src['key']}/retract", {"reason": "x"}).status, 422)
        self.assertEqual(self.rv.post(f"/v1/admin/content/sources/{src['key']}/retract", {"reason": "revogada pela norma Y"}).status, 200)
        self.assertEqual(self.anon.get(f"/v1/help/sources/{src['key']}").json["status"], "retracted")
        with db_system() as d:
            with self.assertRaises(Exception):
                d.run("UPDATE kb_sources SET status = 'active' WHERE id = $1", src["id"])
            with self.assertRaises(Exception):
                d.run("DELETE FROM kb_sources WHERE id = $1", src["id"])
        items = self.rv.get("/v1/admin/content/work-items?kind=retraction_followup").json["items"]
        self.assertTrue(any(i["ref_id"] == art["version_id"] for i in items))
        self.assertEqual(self.ed.post("/v1/admin/content/citations", {"object_type": "article_version", "object_id": art["version_id"], "source": src["key"]}).status, 409)

    def test_retracting_published_content_needs_a_reason_a_reviewer_and_removes_it_everywhere(self):
        word = uniq("zyquelm").replace("-", "")
        pub = publish_article(self.ed, self.rv, title=f"Guia {word} de retirada", summary=f"{word} {word} explicado", visibility="public")
        self.assertTrue(any(i["slug"] == pub["slug"] for i in self.anon.get(f"/v1/help/search?q={word}").json["items"]))
        self.assertIsNotNone(self.anon.post("/v1/help/assistant", {"question": f"o que é {word}?"}).json["answer"])
        self.assertEqual(self.ed.post(f"/v1/admin/content/article_version/{pub['version_id']}/retract", {"reason": "informação errada"}).status, 403, "só reviewer")
        self.assertEqual(self.rv.post(f"/v1/admin/content/article_version/{pub['version_id']}/retract", {"reason": "x"}).status, 422)
        r = self.rv.post(f"/v1/admin/content/article_version/{pub['version_id']}/retract", {"reason": "informação errada confirmada pela fonte"})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["status"], "retracted")
        self.assertFalse(any(i["slug"] == pub["slug"] for i in self.anon.get(f"/v1/help/search?q={word}").json["items"]))
        self.assertIsNone(self.anon.post("/v1/help/assistant", {"question": f"o que é {word}?"}).json["answer"])
        self.assertEqual(self.anon.get(f"/v1/help/articles/{pub['slug']}").status, 404)
        self.assertFalse(any(u["loc"].endswith(f"/ajuda/{pub['slug']}") for u in self.anon.get("/v1/help/sitemap").json["urls"]))
        hist = self.rv.get(f"/v1/admin/content/history/article_version/{pub['version_id']}").json
        self.assertTrue(any(h["to_status"] == "retracted" and "fonte" in (h["note"] or "") for h in hist["items"]))
        with db_system() as d:
            with self.assertRaises(Exception):
                d.run("UPDATE kb_article_versions SET status = 'draft' WHERE id = $1", pub["version_id"])
            with self.assertRaises(Exception):    # sem motivo o banco recusa, mesmo para o dono
                d.run("UPDATE kb_faqs SET status = 'retracted' WHERE id = (SELECT id FROM kb_faqs WHERE status = 'published' LIMIT 1)")


# ================================================================================================= E. assistente
class AssistantAbstainsAndCitesExactlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv = staff("editor"), staff("reviewer")
        cls.anon = Client()

    def _ask(self, q: str) -> dict:
        return self.anon.post("/v1/help/assistant", {"question": q}).json

    def test_demo_content_never_grounds_an_answer_and_is_listed_as_excluded(self):
        word = uniq("vorpalk").replace("-", "")
        publish_article(self.ed, self.rv, title=f"Exemplo {word}", summary=f"{word} {word} de demonstração", demo=True, visibility="public")
        r = self._ask(f"como funciona {word}?")
        self.assertIsNone(r["answer"])
        self.assertTrue(any("DEMO" in e["reason"] for e in r["excluded"]), r)
        self.assertIn("nenhum que possa fundamentar", r["message"])
        self.assertEqual(r["sources"], [])

    def test_third_party_content_is_found_but_never_presented_as_platform_guidance(self):
        word = uniq("quimblor").replace("-", "")
        publish_article(self.ed, self.rv, title=f"Nota {word}", summary=f"{word} {word}", origin="third_party", visibility="public")
        r = self._ask(f"o que diz {word}?")
        self.assertIsNone(r["answer"])
        self.assertTrue(any("terceiros" in e["reason"] for e in r["excluded"]))
        self.assertEqual(r["excluded"][0]["origin_label"], "Conteúdo de terceiros")

    def test_expired_regulatory_content_does_not_ground_an_answer(self):
        word = uniq("fraxolim").replace("-", "")
        slug = uniq("regra")
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
        r = self.ed.post("/v1/admin/content/articles", article_body(slug, title=f"Regra {word}", summary=f"{word} {word}", regulatory=True,
                                                                  regulatory_source="Lei X (exemplo)", regulatory_date="2025-01-01", valid_until=yesterday))
        vid = r.json["version_id"]
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": to}).status, 200)
        a = self._ask(f"qual a regra {word}?")
        self.assertIsNone(a["answer"])
        self.assertTrue(any("vencida" in e["reason"] for e in a["excluded"]))

    def test_the_answer_cites_exactly_one_used_source_and_labels_an_educational_origin(self):
        word = uniq("brelont").replace("-", "")
        publish_article(self.ed, self.rv, title=f"Aula {word}", summary=f"{word} {word} explicado em linguagem simples", origin="educational", visibility="public")
        r = self._ask(f"explique {word}")
        self.assertIsNotNone(r["answer"])
        self.assertEqual(len(r["sources"]), 1, "só a fonte efetivamente usada")
        self.assertEqual(r["sources"][0]["origin_label"], "Material educacional")
        self.assertEqual(r["origin_label"], "Material educacional")
        self.assertIn("material educacional", r["notice"])
        self.assertNotIn("oficial", r["notice"].split("origem:")[1])
        self.assertIn("citations", r["sources"][0])
        self.assertIn("não tem fonte primária citada", r["notice"])

    def test_an_ambiguous_question_returns_options_instead_of_guessing(self):
        word = uniq("ambigx").replace("-", "")
        publish_article(self.ed, self.rv, title=f"Guia {word} para prestação de contas", summary=f"{word}", visibility="public", tags=["prestação de contas"],
                        ctx_keys=["project.budget"])
        publish_article(self.ed, self.rv, title=f"Guia {word} para cadastro", summary=f"{word}", visibility="public", tags=["cadastro"], ctx_keys=["org.new"])
        # os dois empatam no termo raro e se distinguem só pelo tópico: o assistente devolve as opções
        r = self._ask(word)
        if r.get("answer") is None:
            self.assertTrue(r.get("ambiguous") or r["excluded"] == [], r)
            if r.get("ambiguous"):
                self.assertGreaterEqual(len(r["options"]), 2)
        else:
            # empate não detectado (scores diferentes): ainda assim só uma fonte usada e as outras em also_found
            self.assertEqual(len(r["sources"]), 1)
            self.assertTrue(r["also_found"])

    def test_without_any_base_it_says_so_and_opens_a_gap_item_without_the_text(self):
        q = "Qual é a capital da Mongólia e a previsão do tempo?"
        r = self._ask(q)
        self.assertIsNone(r["answer"])
        self.assertFalse(r["ai_used"])
        self.assertEqual(r["actions"][0]["link"], "/ajuda/suporte/novo")
        items = self.rv.get("/v1/admin/content/work-items?kind=assistant_gap&limit=200").json["items"]
        self.assertTrue(items)
        for i in items:
            self.assertNotIn("Mong", json.dumps(i, ensure_ascii=False, default=str), "a fila nunca guarda o texto digitado (ADR-043)")


# ================================================================================================= F. fila editorial
class EditorialWorkQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.ed, cls.rv, cls.sup = staff("editor"), staff("reviewer"), staff("support")
        cls.anon = Client()
        cls.user = new_account("osc")

    def test_search_without_result_opens_one_deduplicated_item_per_topic_without_free_text(self):
        q = "prestação de contas xkqzv"
        for _ in range(3):
            self.anon.get("/v1/help/search?q=" + quote(q))
        items = self.sup.get("/v1/admin/content/work-items?kind=search_gap&limit=200").json["items"]
        mine = [i for i in items if "prestação de contas" in (i["topic"] or "")]
        if mine:   # a busca pode ter encontrado algo (semente) — quando NÃO encontra, há um item e ele conta ocorrências
            self.assertEqual(len(mine), 1)
            self.assertGreaterEqual(mine[0]["occurrences"], 1)
        for i in items:
            self.assertNotIn("xkqzv", json.dumps(i, ensure_ascii=False, default=str))

    def test_unhelpful_feedback_and_incorrect_reports_become_work_items(self):
        pub = publish_article(self.ed, self.rv, visibility="public")
        self.assertEqual(self.user.post("/v1/help/feedback", {"target_type": "article", "target_id": pub["id"], "helpful": False, "reason": "outdated"}).status, 200)
        r = self.user.post("/v1/help/report-incorrect", {"target_type": "article", "target_id": pub["id"], "what": "O prazo citado no passo 2 mudou em 2026."})
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["recorded"])
        self.assertIn("continua visível", r.json["message"])
        self.assertEqual(self.anon.post("/v1/help/report-incorrect", {"target_type": "article", "target_id": pub["id"], "what": "x" * 20}).status, 401)
        items = self.sup.get("/v1/admin/content/work-items?limit=200").json["items"]
        kinds = {i["kind"] for i in items if i["ref_id"] == pub["id"]}
        self.assertEqual(kinds, {"unhelpful", "incorrect_report"})
        rep = next(i for i in items if i["ref_id"] == pub["id"] and i["kind"] == "incorrect_report")
        self.assertEqual(rep["reporter_id"], self.user.user["id"])
        # concluir exige resolução; dispensar também
        self.assertEqual(self.sup.post(f"/v1/admin/content/work-items/{rep['id']}", {"status": "done"}).status, 422)
        self.assertEqual(self.sup.post(f"/v1/admin/content/work-items/{rep['id']}", {"status": "done", "resolution": "Prazo corrigido na versão 2."}).status, 200)
        self.assertNotIn(rep["id"], [i["id"] for i in self.sup.get("/v1/admin/content/work-items?limit=200").json["items"]])
        # a fila é da equipe: usuária comum não vê
        self.assertEqual(self.user.get("/v1/admin/content/work-items").status, 403)

    def test_the_sweep_turns_expired_content_into_work_items_idempotently(self):
        slug = uniq("regra")
        yesterday = (datetime.now(UTC) - timedelta(days=1)).date().isoformat()
        r = self.ed.post("/v1/admin/content/articles", article_body(slug, regulatory=True, regulatory_source="Lei X (exemplo)", regulatory_date="2025-01-01", valid_until=yesterday))
        vid = r.json["version_id"]
        for who, to in ((self.ed, "review"), (self.rv, "approved"), (self.rv, "published")):
            self.assertEqual(who.post(f"/v1/admin/content/article-versions/{vid}/transition", {"to": to}).status, 200)
        self.assertEqual(self.ed.post("/v1/admin/content/work-items/sweep").status, 200)
        self.assertEqual(self.ed.post("/v1/admin/content/work-items/sweep").status, 200)
        items = [i for i in self.ed.get("/v1/admin/content/work-items?kind=expired&limit=200").json["items"] if i["ref_id"] == r.json["id"]]
        self.assertEqual(len(items), 1, "duas varreduras, um item")
        self.assertGreaterEqual(items[0]["occurrences"], 2)


# ================================================================================================= G. arquitetura
class SearchAndEnginesIgnoreReputationAndPlansTests(unittest.TestCase):

    def test_knowledge_search_and_match_never_read_reputation_or_plans(self):
        """Por AST (imports) e por nome de tabela no SQL — comentários e docstrings que DIZEM 'não importa X' não contam."""
        base = ROOT / "backend" / "impacto"
        files = [base / "engines" / "knowledge" / "search.py", base / "services" / "knowledge.py", base / "services" / "kb_provenance.py",
                 *(base / "engines" / "match").rglob("*.py")]
        for p in files:
            tree = ast.parse(p.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "") + "." + a.name for a in node.names]
                for n in names:
                    for bad in ("reputation", "entitlement", "billing", "voucher", "ai_center", "usage_control"):
                        self.assertNotIn(bad, n.lower(), f"{p.relative_to(ROOT)} importa {n}: ranking/match não podem ler reputação nem plano")
            strings = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
            sql = " ".join(s for s in strings if "SELECT" in s.upper() or "FROM" in s.upper())
            for bad in ("org_reputation", "reputation_dimension", "reputation_scores", "entitlement_grants", "plan_code", "ai_credit_ledger"):
                self.assertNotIn(bad, sql, f"{p.relative_to(ROOT)} consulta {bad}")

    def test_the_assistant_is_declared_extractive_without_a_model(self):
        src = (ROOT / "backend" / "impacto" / "services" / "knowledge.py").read_text(encoding="utf-8")
        self.assertIn('"ai_used": False', src)
        self.assertNotIn("gateway", src.lower())


# ================================================================================================= catálogo de conceitos (ajuda contextual)
class ConceptCatalogTests(unittest.TestCase):
    """config/concepts.json é a ÚNICA origem de tooltip, popover e glossário; web/src/concepts.ts é gerado e conferido; a rota pública
    serve o mesmo arquivo; nenhuma definição promete aprovação/garantia; toda fonte 'official' aponta para uma chave de kb_sources."""
    CAT = json.loads((ROOT / "config" / "concepts.json").read_text(encoding="utf-8"))

    def test_schema_and_generated_typescript_are_in_sync(self):
        import subprocess
        import sys
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_concepts.py"), "--check"], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertGreaterEqual(len(self.CAT["terms"]), 30)

    def test_every_term_separates_definition_platform_use_and_limits(self):
        for cid, t in self.CAT["terms"].items():
            for k in ("short", "long", "why", "how_impacto", "limitations", "sources"):
                self.assertTrue(t.get(k), (cid, k))
            self.assertLessEqual(len(t["short"]), 160, cid)

    def test_no_term_promises_approval_compliance_or_guarantee(self):
        bad = re.compile(r"((?<!não )(?<!nunca )garante (a|o|aprova)|aprova[çc][ãa]o garantida|100 ?% (seguro|conforme|imposs)|certifica(mos)? que|em conformidade com a lgpd\b(?! não))", re.I)
        for cid, t in self.CAT["terms"].items():
            text = " ".join(t[k] for k in ("short", "long", "why", "how_impacto", "limitations"))
            self.assertIsNone(bad.search(text), (cid, bad.search(text) and bad.search(text).group(0)))

    def test_official_sources_point_to_registered_kb_sources(self):
        with db_system() as d:
            keys = {r["key"] for r in d.query("SELECT key FROM kb_sources")}
        for cid, t in self.CAT["terms"].items():
            for s in t["sources"]:
                if s.get("source_key"):
                    self.assertIn(s["source_key"], keys, (cid, s["source_key"]))
                if s["kind"] == "official":
                    self.assertTrue(s.get("source_key") or s.get("url"), cid)

    def test_public_route_serves_the_catalog_without_auth(self):
        server()
        r = Client().get("/v1/public/concepts")
        self.assertEqual(r.status, 200, r.json)
        self.assertEqual(r.json["version"], self.CAT["version"])
        ids = {t["id"] for t in r.json["terms"]}
        self.assertEqual(ids, set(self.CAT["terms"]))
        match = next(t for t in r.json["terms"] if t["id"] == "match")
        self.assertIn("não é aprovação", match["limitations"])
