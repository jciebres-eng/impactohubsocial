"""Desempenho com volume sintético. Mede, não adivinha.

Escala padrão (rápida, roda em toda execução da suíte): 120 organizações, 600 projetos, 600 soluções,
3.000 documentos, 1.200 avaliações de match. Escala cheia do alvo (1.000 organizações, 10.000 projetos,
10.000 soluções, 100.000 documentos, 100.000 avaliações) com ``PERF_FULL=1`` — os números publicados em PERFORMANCE_REPORT.md foram
obtidos nessa escala, nesta máquina, e estão registrados lá com o hardware.

O teste não serve para "passar": serve para que uma regressão de desempenho apareça como falha, e para que uma
consulta sem índice apareça como varredura sequencial no EXPLAIN.
"""
from __future__ import annotations

import os
import time
import unittest

from tests.support import grant_premium, new_account, owner_conn, server

# O volume sintético vive no MESMO banco de teste do processo. Rodar junto com a suíte funcional mudaria o resultado
# de testes que dependem de ranking e de listagem (foi o que aconteceu: ordenação de soluções e página de documentos).
# Por isso o teste de volume é um PASSO PRÓPRIO: `PERF=1 python3 -m unittest tests.test_v0150_performance`.
ENABLED = os.getenv("PERF") == "1" or os.getenv("PERF_FULL") == "1"
FULL = os.getenv("PERF_FULL") == "1"
ORGS = 1000 if FULL else 120
PROJECTS = 10_000 if FULL else 600
SOLUTIONS = 10_000 if FULL else 600
DOCUMENTS = 100_000 if FULL else 3_000
MATCH_RUNS = 100_000 if FULL else 1_200
# Limite por requisição. Generoso de propósito: o objetivo é pegar regressão de ordem de grandeza, não milissegundo.
BUDGET_MS = 2_500.0
TIMINGS: dict[str, float] = {}


def timed(label: str, fn):
    t0 = time.perf_counter()
    out = fn()
    TIMINGS[label] = (time.perf_counter() - t0) * 1000
    return out


@unittest.skipUnless(ENABLED, "teste de volume roda em passo próprio (PERF=1 ou PERF_FULL=1)")
class VolumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.company = new_account("company", compliance="approved")
        grant_premium(cls.osc)
        grant_premium(cls.company)
        cls.own = owner_conn()
        t0 = time.perf_counter()
        cls._build_volume(cls.own, cls.osc.org_id, cls.osc.user["id"])
        cls.build_s = time.perf_counter() - t0
        cls.own.run("ANALYZE")

    @staticmethod
    def _build_volume(c, own_org: str, own_user: str) -> None:
        """Volume por SQL em lote, no papel DONO. Nada aqui tenta imitar dado real: são linhas para medir consulta."""
        c.run("INSERT INTO organizations(kind, legal_name, compliance_status, uf)"
              " SELECT 'osc', 'Volume Org ' || g, 'approved', 'MT' FROM generate_series(1, $1) g", ORGS)
        c.run("WITH orgs AS (SELECT id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM organizations"
              "              WHERE legal_name LIKE 'Volume Org %')"
              " INSERT INTO projects(org_id, title, summary, problem, territory, causes, ods, beneficiaries_count,"
              " budget_total_cents, status, visibility, published_at)"
              " SELECT o.id, 'Projeto volume ' || g, 'Resumo do projeto de volume', 'Problema de volume', 'BR-MT',"
              " '{educacao}', '{4}', 50 + (g % 500), 100000 * (1 + g % 50), 'published', 'published', now()"
              " FROM generate_series(1, $1) g JOIN orgs o ON o.n = g % $2", PROJECTS, ORGS)
        # Não existe cadastro nominal de beneficiário na plataforma (por desenho de LGPD: o projeto guarda a
        # contagem agregada). O volume "de registros por organização" usa SOLUÇÕES, que é a tabela grande de conteúdo.
        c.run("WITH orgs AS (SELECT id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM organizations"
              "              WHERE legal_name LIKE 'Volume Org %')"
              " INSERT INTO solutions(org_id, created_by, kind, stage, title, summary, themes, ods, uf,"
              " beneficiaries_count, visibility, published_at)"
              " SELECT o.id, $3, 'methodology', 'running', 'Solução volume ' || g, 'Resumo da solução de volume',"
              " '{educacao}', '{4}', 'MT', 40 + (g % 300), 'published', now()"
              " FROM generate_series(1, $1) g JOIN orgs o ON o.n = g % $2", SOLUTIONS, ORGS, own_user)
        c.run("WITH projs AS (SELECT id, org_id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM projects"
              "               WHERE title LIKE 'Projeto volume %')"
              " INSERT INTO documents(org_id, project_id, doc_type, title, filename, mime_type, size_bytes, sha256,"
              " storage_key, status, origin) SELECT p.org_id, p.id, 'relatorio', 'Documento volume ' || g,"
              " 'doc.pdf', 'application/pdf', 2048, md5(g::text) || md5((g + 7)::text), 'volume/' || g, 'clean',"
              " 'upload' FROM generate_series(1, $1) g JOIN projs p ON p.n = g % $2", DOCUMENTS, PROJECTS)
        c.run("WITH projs AS (SELECT id, org_id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM projects"
              "               WHERE title LIKE 'Projeto volume %')"
              " INSERT INTO match_runs(viewer_org_id, direction, project_id, engine_version, weights_version,"
              " rules_version, taxonomy_version, eligibility, score, confidence, result, features, evidence)"
              " SELECT $3, 'funder_project', p.id, 'match-engine@1.2.0', 'weights@1.0', 'match-rules@1.1',"
              " 'taxonomy@1.0', 'eligible', (g % 100), (g % 100), '{}'::jsonb, '{}'::jsonb, '{}'::jsonb"
              " FROM generate_series(1, $1) g JOIN projs p ON p.n = g % $2", MATCH_RUNS, PROJECTS, own_org)
        c.run("WITH projs AS (SELECT id, org_id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM projects"
              "               WHERE title LIKE 'Projeto volume %')"
              " INSERT INTO ledger_entries(project_id, org_id, entry_type, ref_type, ref_id, payload)"
              " SELECT p.id, p.org_id, 'project_created', 'project', p.id, '{}'::jsonb FROM projs p")

    # ---------------------------------------------------------------------------------------- consultas quentes
    def test_volume_was_really_created(self):
        n = {t: self.own.scalar(f"SELECT count(*) FROM {t}") for t in
             ("organizations", "projects", "solutions", "documents", "match_runs")}
        self.assertGreaterEqual(n["projects"], PROJECTS)
        self.assertGreaterEqual(n["solutions"], SOLUTIONS)
        self.assertGreaterEqual(n["documents"], DOCUMENTS)
        self.assertGreaterEqual(n["match_runs"], MATCH_RUNS)

    def test_funder_feed_stays_within_budget(self):
        r = timed("feed_financiador", lambda: self.company.get("/v1/feed/projects?limit=25"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["feed_financiador"], BUDGET_MS, TIMINGS)

    def test_document_list_stays_within_budget(self):
        r = timed("documentos", lambda: self.osc.get("/v1/documents?limit=25"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["documentos"], BUDGET_MS, TIMINGS)

    def test_readiness_stays_within_budget(self):
        r = timed("prontidao", lambda: self.osc.get("/v1/readiness"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["prontidao"], BUDGET_MS, TIMINGS)

    def test_project_timeline_stays_within_budget(self):
        pid = self.own.scalar("SELECT id::text FROM projects WHERE org_id = $1 LIMIT 1", self.osc.org_id) or \
            self.osc.post("/v1/projects", {"title": "Projeto de medição", "summary": "Resumo",
                                           "problem": "Problema.", "territory": "BR-MT", "causes": ["educacao"],
                                           "beneficiaries_count": 10, "budget_total_cents": 100_000}).json["id"]
        r = timed("linha_do_tempo", lambda: self.osc.get(f"/v1/projects/{pid}/timeline?limit=50"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["linha_do_tempo"], BUDGET_MS, TIMINGS)

    def test_list_does_not_grow_linearly_with_the_page_size(self):
        """Detector de N+1: se a página de 100 custar muito mais que a de 5, há consulta por linha."""
        small = timed("projetos_5", lambda: self.company.get("/v1/feed/projects?limit=5"))
        big = timed("projetos_100", lambda: self.company.get("/v1/feed/projects?limit=100"))
        self.assertEqual((small.status, big.status), (200, 200))
        ratio = TIMINGS["projetos_100"] / max(TIMINGS["projetos_5"], 1.0)
        self.assertLess(ratio, 8.0, f"página 20× maior custou {ratio:.1f}× — indício de consulta por linha: {TIMINGS}")

    # ---------------------------------------------------------------------------------------- planos de execução
    def _plan(self, sql: str, *args) -> str:
        rows = self.own.query("EXPLAIN (ANALYZE false, COSTS false) " + sql, *args)
        return "\n".join(r["QUERY PLAN"] for r in rows)

    def test_hot_queries_use_an_index(self):
        org = self.own.scalar("SELECT org_id::text FROM projects WHERE title LIKE 'Projeto volume %' LIMIT 1")
        pid = self.own.scalar("SELECT id::text FROM projects WHERE title LIKE 'Projeto volume %' LIMIT 1")
        checks = {
            "documentos por projeto": ("SELECT id FROM documents WHERE project_id = $1 AND deleted_at IS NULL", pid),
            "projetos da organização": ("SELECT id FROM projects WHERE org_id = $1 ORDER BY updated_at DESC LIMIT 25", org),
            "trilha do projeto": ("SELECT seq FROM ledger_entries WHERE project_id = $1 ORDER BY seq DESC LIMIT 50", pid),
            "avaliações da organização": ("SELECT id FROM match_runs WHERE viewer_org_id = $1"
                                          " ORDER BY created_at DESC LIMIT 25", self.osc.org_id),
        }
        seq_scans = []
        for label, (sql, arg) in checks.items():
            plan = self._plan(sql, arg)
            if "Seq Scan" in plan:
                seq_scans.append(f"{label}:\n{plan}")
        self.assertEqual(seq_scans, [], "consulta quente sem índice:\n" + "\n\n".join(seq_scans))

    @classmethod
    def tearDownClass(cls):
        scale = "cheia" if FULL else "reduzida"
        print(f"\n[desempenho · escala {scale}] volume criado em {cls.build_s:.1f}s · "
              + " · ".join(f"{k}={v:.0f}ms" for k, v in sorted(TIMINGS.items())))
