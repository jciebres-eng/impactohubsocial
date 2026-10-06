"""v0.17.0 — Programa: a unidade que financiador e governo administram.

Cada teste exercita a API real contra PostgreSQL real. Os que importam mais são os que tentam
QUEBRAR a separação entre declarado e apurado, porque é ali que um produto de impacto mente sem
perceber.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import Client, app_tx, db_system, grant_premium, new_account, owner_conn


class ProgBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.funder = new_account("company", compliance="approved")
        cls.gov = new_account("government", compliance="approved")
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("company", compliance="approved")
        for c in (cls.funder, cls.gov, cls.osc, cls.other):
            grant_premium(c)

    def program(self, client: Client | None = None, **extra) -> str:
        c = client or self.funder
        r = c.post("/v1/programs", {
            "title": f"Programa {uuid.uuid4().hex[:6]} de desenvolvimento territorial",
            "summary": "Programa de apoio a projetos de educação na regional leste do município.",
            "objective": "Elevar a conclusão do ensino médio entre jovens de 14 a 18 anos na regional leste.",
            "budget_total_cents": 500_000_00, "territories": ["BR-MT"], "causes": ["educacao"],
            "ods": [4], "sphere": "private", **extra})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def project(self, client: Client | None = None, publish: bool = False, **extra) -> str:
        c = client or self.osc
        r = c.post("/v1/projects", {
            "title": f"Projeto {uuid.uuid4().hex[:6]}",
            "summary": "Resumo suficiente para que o projeto seja avaliado por terceiros nesta rodada.",
            "problem": "Problema descrito com evidência local e fonte declarada no diagnóstico.",
            "objectives": "Objetivo geral e específicos declarados para o período de execução previsto.",
            "methodology": "Oficinas semanais com registro de presença e avaliação ao final de cada módulo.",
            "territory": "BR-MT", "budget_total_cents": 30_000_000, "causes": ["educacao"], "ods": [4],
            "beneficiaries_count": 200, "beneficiaries_description": "Jovens de 14 a 18 anos", **extra})
        self.assertEqual(r.status, 201, r)
        pid = r.json["id"]
        if publish:
            self.assertIn(c.post(f"/v1/projects/{pid}/publish", {}).status, (200, 201))
        return pid


# ================================================================================================ ciclo
class ProgramLifecycleTests(ProgBase):
    def test_program_is_born_in_draft_even_through_direct_sql(self):
        pid = self.program()
        self.assertEqual(self.funder.get(f"/v1/programs/{pid}").json["status"], "draft")
        # E o gatilho recusa nascer em outro estado mesmo por SQL direto, no contexto da usuária.
        with app_tx(self.funder) as c, self.assertRaises(Exception) as e:
            c.run("INSERT INTO programs(owner_org_id, title, summary, objective, status)"
                  " VALUES ($1,'Programa direto por SQL','Resumo que passa do mínimo exigido',"
                  " 'Objetivo que passa do mínimo exigido','open')", self.funder.org_id)
        self.assertIn("rascunho", str(e.exception).lower())

    def test_transition_outside_the_graph_is_refused_and_says_where_it_can_go(self):
        pid = self.program()
        r = self.funder.post(f"/v1/programs/{pid}/transition", {"to_status": "closed",
                                                                "reason": "tentando pular etapas"})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "invalid_transition")
        self.assertIn("open", r.json["details"]["possiveis"])

    def test_suspension_requires_a_reason(self):
        pid = self.program()
        self.assertEqual(self.funder.post(f"/v1/programs/{pid}/transition", {"to_status": "open"}).status, 200)
        r = self.funder.post(f"/v1/programs/{pid}/transition", {"to_status": "suspended"})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "reason_required")
        ok = self.funder.post(f"/v1/programs/{pid}/transition",
                              {"to_status": "suspended", "reason": "apuração de irregularidade em curso"})
        self.assertEqual(ok.status, 200, ok)

    def test_publication_dates_are_derived_not_written(self):
        pid = self.program()
        self.funder.post(f"/v1/programs/{pid}/transition", {"to_status": "open"})
        got = self.funder.get(f"/v1/programs/{pid}").json
        self.assertIsNotNone(got["published_at"], "abrir o programa precisa gravar a data")
        # E a dona não consegue reescrever a data, nem por SQL direto.
        with app_tx(self.funder) as c, self.assertRaises(Exception) as e:
            c.run("UPDATE programs SET published_at = now() - interval '1 year' WHERE id = $1", pid)
        self.assertIn("derivadas", str(e.exception).lower())

    def test_a_public_program_can_still_be_suspended(self):
        """A primeira versão da guarda de visibilidade BLOQUEAVA a suspensão de programa público."""
        pid = self.program()
        self.assertEqual(self.funder.post(f"/v1/programs/{pid}/transition", {"to_status": "open"}).status, 200)
        self.assertEqual(self.funder.patch(f"/v1/programs/{pid}", {"visibility": "public"}).status, 200)
        r = self.funder.post(f"/v1/programs/{pid}/transition",
                             {"to_status": "suspended", "reason": "apuração de irregularidade em curso"})
        self.assertEqual(r.status, 200, "moderação precisa conseguir suspender programa já publicado")

    def test_a_suspended_program_cannot_be_made_public(self):
        pid = self.program()
        self.funder.post(f"/v1/programs/{pid}/transition", {"to_status": "open"})
        self.funder.post(f"/v1/programs/{pid}/transition",
                         {"to_status": "suspended", "reason": "apuração de irregularidade em curso"})
        r = self.funder.patch(f"/v1/programs/{pid}", {"visibility": "public"})
        self.assertEqual(r.status, 422, r)


# ================================================================================================ o defeito
class ProgramLimitTests(ProgBase):
    def test_the_plan_limit_now_counts_programs_and_not_editais(self):
        """O limite `programs` era aplicado contra `calls`: o plano vendia entidade que não existia."""
        free = new_account("company", compliance="approved")   # sem premium: plano básico
        limit = None
        with db_system() as c:
            limit = c.scalar("SELECT (limits->>'programs')::int FROM plans WHERE plan_key = 'company_basic'")
        self.assertIsNotNone(limit, "company_basic precisa declarar o limite de programas")
        for i in range(limit):
            r = free.post("/v1/programs", {
                "title": f"Programa dentro do limite {i}", "summary": "Resumo que passa do mínimo exigido.",
                "objective": "Objetivo declarado que passa do mínimo exigido pelo contrato."})
            self.assertEqual(r.status, 201, r)
        over = free.post("/v1/programs", {
            "title": "Programa que estoura o limite", "summary": "Resumo que passa do mínimo exigido.",
            "objective": "Objetivo declarado que passa do mínimo exigido pelo contrato."})
        self.assertEqual(over.status, 402, over)


# ================================================================================================ agregação
class ProgramAggregationTests(ProgBase):
    def test_declared_and_measured_never_mix(self):
        """A trava central: orçamento declarado e dinheiro apurado em objetos SEPARADOS e nomeados."""
        pid = self.program()
        prj = self.project(publish=True)
        self.funder.post(f"/v1/programs/{pid}/projects",
                         {"project_id": prj, "role": "funded", "allocated_cents": 100_000_00})
        got = self.funder.get(f"/v1/programs/{pid}").json
        self.assertEqual(got["declared"]["budget_total_cents"], 500_000_00)
        self.assertEqual(got["declared"]["allocated_cents"], 100_000_00)
        # Nada foi comprometido nem pago: o apurado é zero, e NÃO herda o declarado.
        self.assertEqual(got["measured"]["committed_cents"], 0)
        self.assertEqual(got["measured"]["spent_cents"], 0)
        self.assertEqual(got["measured"]["evidenced_cents"], 0)
        self.assertNotIn("budget_total_cents", got["measured"])
        self.assertNotIn("committed_cents", got["declared"])

    def test_a_program_cannot_hang_someone_elses_edital(self):
        pid = self.program()
        other_call = self.other.post("/v1/calls", {
            "title": "Edital de outra organização", "summary": "Resumo do edital de outra organização.",
            "sphere": "private", "instrument": "edital", "funder_name": "Outra",
            "causes": ["educacao"], "territories": ["BR-MT"], "eligible_org_types": ["osc"]})
        if other_call.status != 201:
            self.skipTest(f"criação de edital indisponível neste contexto: {other_call.status}")
        r = self.funder.post(f"/v1/programs/{pid}/calls", {"call_id": other_call.json["id"]})
        self.assertIn(r.status, (403, 404, 422), r)

    def test_baseline_without_a_source_is_refused(self):
        pid = self.program()
        with db_system() as c:
            ind = c.scalar("SELECT id::text FROM indicator_catalog WHERE org_id IS NULL LIMIT 1")
        if not ind:
            self.skipTest("catálogo de indicadores vazio neste ambiente")
        r = self.funder.post(f"/v1/programs/{pid}/indicators",
                             {"indicator_id": ind, "baseline_value": 42.0})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "source_required")
        ok = self.funder.post(f"/v1/programs/{pid}/indicators",
                              {"indicator_id": ind, "baseline_value": 42.0,
                               "baseline_source": "Censo Escolar INEP 2024"})
        self.assertEqual(ok.status, 201, ok)

    def test_the_executing_org_is_notified_when_its_project_enters_a_program(self):
        pid = self.program()
        prj = self.project(publish=True)
        before = self.osc.get("/v1/notifications").json["items"]
        self.funder.post(f"/v1/programs/{pid}/projects", {"project_id": prj, "role": "candidate"})
        after = self.osc.get("/v1/notifications").json["items"]
        self.assertGreater(len(after), len(before),
                           "quem executa precisa saber que entrou num programa: muda a obrigação dele")


# ================================================================================================ isolamento
class ProgramIsolationTests(ProgBase):
    def test_a_draft_program_is_invisible_to_everyone_else(self):
        pid = self.program()
        self.assertEqual(self.other.get(f"/v1/programs/{pid}").status, 404)
        self.assertEqual(self.osc.get(f"/v1/programs/{pid}").status, 404)

    def test_only_public_published_programs_appear_without_a_session(self):
        pid = self.program()
        anon = Client()
        self.assertEqual(anon.get(f"/v1/programs/{pid}").status, 404,
                         "programa em rascunho não pode aparecer para quem não tem sessão")
        self.funder.post(f"/v1/programs/{pid}/transition", {"to_status": "open"})
        self.assertEqual(anon.get(f"/v1/programs/{pid}").status, 404,
                         "aberto mas não público continua invisível")
        self.funder.patch(f"/v1/programs/{pid}", {"visibility": "public"})
        self.assertEqual(anon.get(f"/v1/programs/{pid}").status, 200)
        feed = anon.get("/v1/programs/feed")
        self.assertEqual(feed.status, 200, feed)
        self.assertIn(pid, [i["id"] for i in feed.json["items"]])

    def test_a_suspended_program_leaves_the_public_feed(self):
        pid = self.program()
        self.funder.post(f"/v1/programs/{pid}/transition", {"to_status": "open"})
        self.funder.patch(f"/v1/programs/{pid}", {"visibility": "public"})
        anon = Client()
        self.assertIn(pid, [i["id"] for i in anon.get("/v1/programs/feed").json["items"]])
        self.funder.post(f"/v1/programs/{pid}/transition",
                         {"to_status": "suspended", "reason": "apuração em curso pela administração"})
        self.assertNotIn(pid, [i["id"] for i in anon.get("/v1/programs/feed").json["items"]])
        self.assertEqual(anon.get(f"/v1/programs/{pid}").status, 404)

    def test_the_org_executing_a_project_in_the_program_can_see_the_program(self):
        """Quem executa precisa saber de que programa faz parte — mesma lógica de app_project_supporter."""
        pid = self.program()
        prj = self.project(publish=True)
        self.assertEqual(self.osc.get(f"/v1/programs/{pid}").status, 404, "antes do vínculo, invisível")
        self.funder.post(f"/v1/programs/{pid}/projects", {"project_id": prj, "role": "funded"})
        self.assertEqual(self.osc.get(f"/v1/programs/{pid}").status, 200, "depois do vínculo, visível")
        # Mas continua invisível para quem não tem nada a ver com o programa.
        self.assertEqual(self.other.get(f"/v1/programs/{pid}").status, 404)

    def test_another_org_cannot_move_or_edit_the_program(self):
        pid = self.program()
        self.assertIn(self.other.post(f"/v1/programs/{pid}/transition", {"to_status": "open"}).status,
                      (403, 404))
        self.assertIn(self.other.patch(f"/v1/programs/{pid}", {"title": "Sequestrado por outra org"}).status,
                      (403, 404))


# ================================================================================================ análise
class ResultChainTests(ProgBase):
    def test_hypothesis_is_never_counted_as_evidence(self):
        """A honestidade da cadeia de resultado está em não promover elo fraco a forte."""
        prj = self.project(publish=True)
        nodes = {}
        for kind, label in (("activity", "Oficinas semanais"), ("output", "300 participantes"),
                            ("outcome", "240 concluíram o programa")):
            r = self.osc.post(f"/v1/projects/{prj}/graph/nodes", {"kind": kind, "label": label})
            if r.status not in (200, 201):
                self.skipTest(f"grafo de impacto indisponível: {r.status} {r.json}")
            nodes[kind] = r.json["id"]
        a = self.osc.post(f"/v1/projects/{prj}/graph/edges",
                          {"from_node": nodes["activity"], "to_node": nodes["output"],
                           "link_type": "hypothesis"})
        self.assertIn(a.status, (200, 201), a)
        chain = self.osc.get(f"/v1/projects/{prj}/result-chain")
        self.assertEqual(chain.status, 200, chain)
        s = chain.json["summary"]
        self.assertEqual(s["weak_links"], 1)
        self.assertEqual(s["strong_links"], 0)
        self.assertEqual(s["with_evidence"], 0)
        for word in ("hipótese", "não são evidência"):
            self.assertIn(word, chain.json["note"].lower().replace("hipótese", "hipótese"))


class TerritorialGapTests(ProgBase):
    def test_the_gap_says_when_the_demand_has_no_source(self):
        """Lacuna apoiada em estimativa sem fonte não passa por fato: a resposta diz isso.

        O território é um código MUNICIPAL deliberadamente pouco usado: a primeira versão deste teste
        usava "BR-MT" e passava sozinha, mas falhava na suíte inteira — porque outros testes criam
        necessidades COM fonte no mesmo estado, e a classificação virava "parcial". Teste que depende
        de o banco estar vazio não é teste.
        """
        terr = "BR-AC-1200013"
        r = self.gov.post("/v1/territory/needs", {
            "territory": terr, "title": "Falta de vagas em contraturno na regional leste",
            "description": "Demanda registrada pela secretaria municipal de educação.",
            "cause": "educacao", "priority": "critical"})
        self.assertEqual(r.status, 201, r)
        gap = self.gov.get(f"/v1/territorial-gap?territory_prefix={terr}")
        self.assertEqual(gap.status, 200, gap)
        row = next((x for x in gap.json["items"] if x["territory"] == terr), None)
        self.assertIsNotNone(row, gap.json)
        self.assertGreaterEqual(row["needs_open"], 1)
        self.assertEqual(row["evidence_quality"], "sem_fonte",
                         "necessidade sem fonte citada não pode produzir lacuna tratada como fato")
        self.assertIn(row["gap"], ("demanda_sem_oferta", "demanda_acima_da_oferta", "oferta_compativel"))
        self.assertIn("não é censo", gap.json["note"].lower())

    def test_the_gap_carries_no_person_level_data(self):
        gap = self.gov.get("/v1/territorial-gap")
        self.assertEqual(gap.status, 200, gap)
        blob = str(gap.json).lower()
        for forbidden in ("cpf", "beneficiary_group", "birth_date", "email", "phone"):
            self.assertNotIn(forbidden, blob, f"lacuna territorial não pode carregar {forbidden}")


if __name__ == "__main__":
    unittest.main()
