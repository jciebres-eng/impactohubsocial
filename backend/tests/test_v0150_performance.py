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

from tests.support import Client, grant_premium, new_account, owner_conn, server

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

        # ------------------------------------------------------------------ v0.16.0: volume na REDE
        #
        # POR QUE ISTO É NECESSÁRIO: o teste de plano de execução usa EXPLAIN, e o planejador escolhe varredura
        # sequencial quando a tabela é pequena — corretamente. Sem volume nas tabelas da rede, "esta consulta usa
        # índice?" não tem resposta significativa: o plano diria Seq Scan mesmo com o índice no lugar. Volume aqui
        # é o que torna a verificação honesta.
        c.run("WITH projs AS (SELECT id, org_id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM projects"
              "               WHERE title LIKE 'Projeto volume %'),"
              "     orgs AS (SELECT id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM organizations"
              "              WHERE legal_name LIKE 'Volume Org %')"
              " INSERT INTO relationships(kind, source_org_id, target_project_id, org_id, visibility, status)"
              " SELECT CASE WHEN g % 3 = 0 THEN 'favorite' WHEN g % 3 = 1 THEN 'watchlist' ELSE 'support' END,"
              # A relação parte de ORGANIZAÇÕES DIFERENTES, como no mundo real. Concentrar tudo numa só
              # organização tornava `org_id` não seletivo, e o planejador escolhia varredura sequencial —
              # corretamente. O teste de índice só diz algo quando o dado tem a forma do dado de verdade.
              "        o.id, p.id, o.id, 'private', 'active'"
              " FROM generate_series(1, $1) g JOIN projs p ON p.n = g % $2"
              # o índice da organização é módulo ORGS (há menos organizações que projetos): usar PROJECTS aqui
              # fazia o JOIN não casar e o INSERT inserir quase nada, em silêncio
              " JOIN orgs o ON o.n = (g * 7) % $3"
              " WHERE o.id <> p.org_id ON CONFLICT DO NOTHING", PROJECTS, PROJECTS, ORGS)
        c.run("ANALYZE relationships")
        c.run("WITH orgs AS (SELECT id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM organizations"
              "              WHERE legal_name LIKE 'Volume Org %'),"
              "     projs AS (SELECT id, org_id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM projects"
              "               WHERE title LIKE 'Projeto volume %')"
              " INSERT INTO proposals(kind, sender_org_id, receiver_org_id, project_id, title, purpose, status,"
              " sent_at) SELECT 'investment', $3, p.org_id, p.id, 'Proposta volume ' || g,"
              " 'Proposito da proposta de volume para medir consulta', 'sent', now()"
              " FROM generate_series(1, $1) g JOIN projs p ON p.n = g % $2 WHERE p.org_id <> $3", PROJECTS,
              PROJECTS, own_org)
        c.run("WITH projs AS (SELECT id, org_id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM projects"
              "               WHERE title LIKE 'Projeto volume %')"
              " INSERT INTO marketplace_listings(org_id, subject_type, project_id, seeking, headline,"
              " publication_state, published_at) SELECT p.org_id, 'project', p.id, '{investment}',"
              " 'Anuncio de volume numero ' || g || ' para medir a consulta publica', 'published', now()"
              " FROM generate_series(1, $1) g JOIN projs p ON p.n = g % $2"
              " ON CONFLICT DO NOTHING", PROJECTS, PROJECTS)
        c.run("INSERT INTO notifications(org_id, user_id, kind, title, priority)"
              " SELECT $2, $3, 'network.notice', 'Aviso de volume ' || g, 'normal'"
              " FROM generate_series(1, $1) g", DOCUMENTS, own_org, own_user)
        c.run("WITH projs AS (SELECT id, org_id, row_number() OVER (ORDER BY created_at) - 1 AS n FROM projects"
              "               WHERE title LIKE 'Projeto volume %')"
              " INSERT INTO domain_events(event, org_id, project_id, subject_type, subject_id, payload)"
              " SELECT 'Relationship.created', p.org_id, p.id, 'project', p.id, '{}'::jsonb"
              " FROM generate_series(1, $1) g JOIN projs p ON p.n = g % $2", DOCUMENTS, PROJECTS)

        # ------------------------------------------------------------------ v0.17.0: camada econômica
        # Programas de DONOS diferentes, por volume e por honestidade do plano: concentrar tudo numa
        # organização tornaria `owner_org_id` não seletivo e o planejador escolheria varredura
        # sequencial — corretamente. Foi a lição que `relationships` ensinou acima.
        c.run("WITH orgs AS (SELECT id, row_number() OVER (ORDER BY created_at) - 1 AS n"
              "              FROM organizations WHERE legal_name LIKE 'Volume Org %')"
              " INSERT INTO programs(owner_org_id, title, summary, objective, visibility,"
              " published_at, status)"
              " SELECT o.id, 'Programa volume ' || g,"
              "        'Resumo do programa de volume numero ' || g || ' para medir consulta.',"
              "        'Objetivo declarado do programa de volume numero ' || g || '.',"
              "        CASE WHEN g % 3 = 0 THEN 'public' ELSE 'network' END, NULL, 'draft'"
              " FROM generate_series(1, $1) g JOIN orgs o ON o.n = (g * 3) % $2", PROJECTS, ORGS)
        # Programa NASCE em rascunho — o gatilho recusa qualquer outra situação inicial, inclusive para
        # o papel dono. Então o volume publica pela transição, como o produto faz, e é a transição que
        # deriva `published_at`. Inserir já publicado seria mais rápido e mediria um dado que o
        # produto nunca produz.
        c.run("UPDATE programs SET status = 'open' WHERE title LIKE 'Programa volume %'"
              " AND visibility = 'public'")
        c.run("WITH progs AS (SELECT id, owner_org_id, row_number() OVER (ORDER BY created_at) - 1 AS n"
              "               FROM programs WHERE title LIKE 'Programa volume %'),"
              "     projs AS (SELECT id, org_id, row_number() OVER (ORDER BY created_at) - 1 AS n"
              "               FROM projects WHERE title LIKE 'Projeto volume %')"
              " INSERT INTO program_projects(program_id, project_id, org_id, role, added_by)"
              " SELECT pr.id, pj.id, pr.owner_org_id,"
              "        CASE WHEN g % 4 = 0 THEN 'funded' WHEN g % 4 = 1 THEN 'selected'"
              "             WHEN g % 4 = 2 THEN 'monitored' ELSE 'candidate' END, NULL"
              " FROM generate_series(1, $1) g"
              " JOIN progs pr ON pr.n = g % $2 JOIN projs pj ON pj.n = (g * 5) % $3"
              " ON CONFLICT DO NOTHING", PROJECTS, PROJECTS, PROJECTS)
        # Eventos de valor pela porta do produto seriam lentos de criar em volume; aqui o que se mede é
        # a CONSULTA, então as linhas entram em lote. `estimate_status` fica 'no_baseline' porque é o
        # estado verdadeiro: a tabela de linhas de base nasce vazia.
        c.run("WITH orgs AS (SELECT id, row_number() OVER (ORDER BY created_at) - 1 AS n"
              "              FROM organizations WHERE legal_name LIKE 'Volume Org %')"
              " INSERT INTO value_events(event_type, org_id, subject_type, units, estimate_status,"
              " engine_version) SELECT 'readiness.evaluated', o.id, 'organization', 1, 'no_baseline',"
              " 'volume@1.0' FROM generate_series(1, $1) g JOIN orgs o ON o.n = g % $2",
              MATCH_RUNS, ORGS)
        c.run("WITH orgs AS (SELECT id, row_number() OVER (ORDER BY created_at) - 1 AS n"
              "              FROM organizations WHERE legal_name LIKE 'Volume Org %')"
              " INSERT INTO platform_charges(org_id, kind, method, amount_cents, currency, provider)"
              " SELECT o.id, 'one_off', 'card', 1000 + g, 'BRL', 'sandbox'"
              " FROM generate_series(1, $1) g JOIN orgs o ON o.n = g % $2", PROJECTS, ORGS)
        c.run("ANALYZE programs")
        c.run("ANALYZE program_projects")
        c.run("ANALYZE value_events")
        c.run("ANALYZE platform_charges")

    # ---------------------------------------------------------------------------------------- consultas quentes
    def test_volume_was_really_created(self):
        n = {t: self.own.scalar(f"SELECT count(*) FROM {t}") for t in
             ("organizations", "projects", "solutions", "documents", "match_runs",
              "relationships", "proposals", "marketplace_listings", "notifications", "domain_events")}
        n.update({t: self.own.scalar(f"SELECT count(*) FROM {t}") for t in
                  ("programs", "program_projects", "value_events", "platform_charges")})
        for t in ("relationships", "proposals", "marketplace_listings", "notifications",
                  "domain_events", "programs", "program_projects", "value_events",
                  "platform_charges"):
            self.assertGreater(n[t], 100, f"sem volume em {t} o plano de execução não diz nada: {n}")
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

    # ---------------------------------------------------------------------------------------- v0.16.0: a rede
    def test_workspace_stays_within_budget(self):
        """O workspace é a tela de ABERTURA de todas as personas, e chama vários motores de uma vez.

        Se esta medição estourar, a primeira impressão do produto é uma tela lenta. O orçamento vale para a
        resposta inteira — persona, capacidades, contadores, próximas ações e todas as seções.
        """
        r = timed("workspace_osc", lambda: self.osc.get("/v1/workspace"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["workspace_osc"], BUDGET_MS, TIMINGS)
        r2 = timed("workspace_investidor", lambda: self.company.get("/v1/workspace"))
        self.assertEqual(r2.status, 200, r2)
        self.assertLess(TIMINGS["workspace_investidor"], BUDGET_MS, TIMINGS)

    def test_public_marketplace_feed_stays_within_budget(self):
        """O feed público é a porta de entrada de quem ainda não tem conta: é a página mais exposta do produto."""
        anon = Client()
        r = timed("marketplace_publico", lambda: anon.get("/v1/marketplace/feed?limit=20"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["marketplace_publico"], BUDGET_MS, TIMINGS)

    def test_proposal_inbox_and_relationships_stay_within_budget(self):
        r = timed("propostas", lambda: self.osc.get("/v1/proposals?box=all&limit=25"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["propostas"], BUDGET_MS, TIMINGS)
        r2 = timed("relacoes", lambda: self.osc.get("/v1/network/relationships?limit=25"))
        self.assertEqual(r2.status, 200, r2)
        self.assertLess(TIMINGS["relacoes"], BUDGET_MS, TIMINGS)

    def test_network_graph_depth_two_stays_within_budget(self):
        """Profundidade 2 é o caso que justificaria um banco de grafos — a medição é o que decide isso."""
        r = timed("grafo_2", lambda: self.osc.get("/v1/network/graph?depth=2&limit=100"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["grafo_2"], BUDGET_MS, TIMINGS)

    def test_readiness_purposes_stays_within_budget(self):
        r = timed("prontidao_finalidades", lambda: self.osc.get("/v1/readiness/purposes"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["prontidao_finalidades"], BUDGET_MS, TIMINGS)

    # ------------------------------------------------------------------------------ v0.17.0: econômica
    def test_public_program_feed_stays_within_budget(self):
        r = timed("feed_programas", lambda: Client().get("/v1/programs/feed?limit=25"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["feed_programas"], BUDGET_MS, TIMINGS)

    def test_value_summary_stays_within_budget(self):
        r = timed("resumo_valor", lambda: self.osc.get("/v1/value/summary"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["resumo_valor"], BUDGET_MS, TIMINGS)

    def test_charge_list_stays_within_budget(self):
        r = timed("cobrancas", lambda: self.osc.get("/v1/payments/charges?limit=25"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["cobrancas"], BUDGET_MS, TIMINGS)

    def test_legal_registry_stays_within_budget(self):
        r = timed("registro_legal", lambda: Client().get("/v1/legal/registry"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["registro_legal"], BUDGET_MS, TIMINGS)

    def test_the_sql_functions_of_the_economic_layer_stay_within_budget(self):
        """Mede as FUNÇÕES, não as rotas: é nelas que mora a conta, e é nelas que a regressão aparece.

        `platform_revenue()` varre todas as cobranças e `legal_overview()` conta todos os aceites —
        duas consultas que crescem com o uso e que ninguém olharia até ficarem lentas.
        """
        prog = self.own.scalar("SELECT id::text FROM programs WHERE title LIKE 'Programa volume %'"
                               " LIMIT 1")
        for label, sql, arg in (
                ("fn_programa_financeiro", "SELECT * FROM program_financials($1)", prog),
                ("fn_cadeia_resultado", "SELECT * FROM result_chain($1)", prog),
                ("fn_receita_plataforma", "SELECT * FROM platform_revenue()", None),
                ("fn_panorama_legal", "SELECT * FROM legal_overview()", None),
                ("fn_lacuna_territorial", "SELECT * FROM territorial_gap(NULL)", None)):
            if arg is None:
                timed(label, lambda sql=sql: self.own.query(sql))
            else:
                timed(label, lambda sql=sql, arg=arg: self.own.query(sql, arg))
            self.assertLess(TIMINGS[label], BUDGET_MS, f"{label}: {TIMINGS[label]:.0f}ms")

    # ---------------------------------------------------------------------------------------- planos de execução
    def _plan(self, sql: str, *args) -> str:
        rows = self.own.query("EXPLAIN (ANALYZE false, COSTS false) " + sql, *args)
        return "\n".join(r["QUERY PLAN"] for r in rows)

    def test_hot_queries_use_an_index(self):
        org = self.own.scalar("SELECT org_id::text FROM projects WHERE title LIKE 'Projeto volume %' LIMIT 1")
        pid = self.own.scalar("SELECT id::text FROM projects WHERE title LIKE 'Projeto volume %' LIMIT 1")
        rel_org = self.own.scalar("SELECT org_id::text FROM relationships WHERE kind = 'favorite' LIMIT 1")
        prog = self.own.scalar("SELECT id::text FROM programs WHERE title LIKE 'Programa volume %' LIMIT 1")
        prog_org = self.own.scalar("SELECT owner_org_id::text FROM programs"
                                   " WHERE title LIKE 'Programa volume %' LIMIT 1")
        val_org = self.own.scalar("SELECT org_id::text FROM value_events"
                                  " WHERE engine_version = 'volume@1.0' LIMIT 1")
        chg_org = self.own.scalar("SELECT org_id::text FROM platform_charges"
                                  " WHERE provider = 'sandbox' LIMIT 1")
        # Tabela pequena ganha varredura sequencial porque o planejador está CERTO: ler 150 linhas
        # inteiras é mais barato que navegar índice. Então o teste só conclui algo onde há volume, e
        # diz quais verificações ficaram inconclusivas em vez de fingir que passaram.
        MIN_ROWS = 500
        checks = {
            "documentos por projeto": ("SELECT id FROM documents WHERE project_id = $1 AND deleted_at IS NULL", pid),
            "projetos da organização": ("SELECT id FROM projects WHERE org_id = $1 ORDER BY updated_at DESC LIMIT 25", org),
            "trilha do projeto": ("SELECT seq FROM ledger_entries WHERE project_id = $1 ORDER BY seq DESC LIMIT 50", pid),
            "avaliações da organização": ("SELECT id FROM match_runs WHERE viewer_org_id = $1"
                                          " ORDER BY created_at DESC LIMIT 25", self.osc.org_id),
            # v0.16.0 — os acessos quentes da rede
            "relações da organização": ("SELECT id FROM relationships WHERE org_id = $1 AND kind = 'favorite'"
                                        " AND status = 'active' LIMIT 25", rel_org),
            "propostas recebidas": ("SELECT id FROM proposals WHERE receiver_org_id = $1 AND status = 'sent'"
                                    " ORDER BY created_at DESC LIMIT 25", self.osc.org_id),
            "anúncios publicados": ("SELECT id FROM marketplace_listings WHERE publication_state = 'published'"
                                    " ORDER BY published_at DESC LIMIT 25", None),
            "avisos não lidos": ("SELECT id FROM notifications WHERE user_id = $1 AND read_at IS NULL"
                                 " ORDER BY created_at DESC LIMIT 25", self.osc.user["id"]),
            "fatos do projeto": ("SELECT id FROM domain_events WHERE project_id = $1 ORDER BY id DESC LIMIT 25",
                                 pid),
            # v0.17.0 — os acessos quentes da camada econômica
            "programas da organização": ("SELECT id FROM programs WHERE owner_org_id = $1 LIMIT 25",
                                         prog_org),
            "feed público de programas": ("SELECT id FROM programs WHERE visibility = 'public'"
                                          " ORDER BY published_at DESC LIMIT 25", None),
            "carteira do programa": ("SELECT project_id FROM program_projects WHERE program_id = $1"
                                     " LIMIT 50", prog),
            "eventos de valor da organização": ("SELECT id FROM value_events WHERE org_id = $1"
                                                " ORDER BY created_at DESC LIMIT 25", val_org),
            "cobranças da organização": ("SELECT id FROM platform_charges WHERE org_id = $1"
                                         " ORDER BY created_at DESC LIMIT 25", chg_org),
            "cobranças a vencer": ("SELECT id FROM platform_charges WHERE state = 'pending'"
                                   " AND expires_at < now() LIMIT 50", None),
            "aceites do titular": ("SELECT id FROM legal_acceptances WHERE user_id = $1"
                                   " ORDER BY accepted_at DESC LIMIT 25", self.osc.user["id"]),
        }
        seq_scans, inconclusive = [], []
        for label, (sql, arg) in checks.items():
            table = sql.split(" FROM ")[1].split()[0]
            if self.own.scalar(f"SELECT count(*) FROM {table}") < MIN_ROWS:   # noqa: S608
                inconclusive.append(f"{label} ({table} com menos de {MIN_ROWS} linhas)")
                continue
            plan = self._plan(sql, arg) if arg is not None else self._plan(sql)
            if "Seq Scan" in plan:
                seq_scans.append(f"{label}:\n{plan}")
        if inconclusive:
            print("\n[desempenho] inconclusivo nesta escala: " + "; ".join(inconclusive))
        self.assertEqual(seq_scans, [], "consulta quente sem índice:\n" + "\n\n".join(seq_scans))
        self.assertGreaterEqual(len(checks) - len(inconclusive), 6,
                                "escala baixa demais: quase nada foi conferido de verdade")

    @classmethod
    def tearDownClass(cls):
        scale = "cheia" if FULL else "reduzida"
        print(f"\n[desempenho · escala {scale}] volume criado em {cls.build_s:.1f}s · "
              + " · ".join(f"{k}={v:.0f}ms" for k, v in sorted(TIMINGS.items())))
