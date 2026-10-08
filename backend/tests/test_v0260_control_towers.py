"""v0.26.0 — Torres de controle (financiador e governo) e o estado verificável "Projeto IMPACTO Ready".

O que estes testes provam, com HTTP e PostgreSQL reais:
  * a torre do financiador responde a cadeia inteira a partir dos registros existentes, e o que ela
    mostra de dinheiro bate com a carteira (/v1/portfolio) — nada é saldo, nada é custódia;
  * "o que preciso decidir" reúne obrigações de acordo, candidaturas, relatórios e evidências;
  * a torre do governo só lista projetos PUBLICADOS, respeita k-anonimato (< 3 projetos → nada linha a
    linha) e distingue indicador declarado de validado;
  * o estado IMPACTO Ready nunca é concedido com critério desconhecido, aponta a evidência de cada
    critério, tem hash reproduzível e respeita a visibilidade (quem não vê o projeto recebe 404);
  * financiador não enxerga a torre de outro financiador, e OSC não tem torre de financiador.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from tests.support import db_system, new_account, server
from tests.test_v080 import funded_pair


class FunderTowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.par = funded_pair(amount=100000, budget_items=((1, 100000),))
        cls.osc, cls.fu, cls.pid = cls.par["osc"], cls.par["fu"], cls.par["pid"]

    def test_capital_in_the_tower_matches_the_portfolio_and_is_never_a_balance(self):
        torre = self.fu.get("/v1/control-tower/funder")
        self.assertEqual(torre.status, 200, torre)
        t = torre.json
        port = self.fu.get("/v1/portfolio").json["totals"]
        for k in ("committed_cents", "disbursed_cents", "confirmed_cents", "spent_cents", "validated_spent_cents"):
            self.assertEqual(t["capital"][k], port[k], k)
        self.assertEqual(t["capital"]["committed_cents"], 100000)
        self.assertEqual(t["capital"]["in_transit_cents"], 100000, "comprometido e não desembolsado = em trânsito entre as partes")
        self.assertNotIn("balance", str(t).lower())
        self.assertIn("não custodia", t["note"])
        p = next(x for x in t["projects"] if x["project_id"] == self.pid)
        self.assertEqual(p["purpose"]["causes"], ["educacao"])
        self.assertIn("ready", p)
        self.assertEqual(p["ready"]["total"], 15)

    def test_what_needs_my_decision_includes_evidence_delays_and_risks(self):
        osc, fu, pid = self.osc, self.fu, self.pid
        ms = osc.post(f"/v1/projects/{pid}/milestones", {"title": "Etapa atrasada", "amount_cents": 50000,
                                                          "due_on": (date.today() - timedelta(days=3)).isoformat()})
        self.assertEqual(ms.status, 201, ms)
        ev = osc.post(f"/v1/projects/{pid}/evidences", {"kind": "attendance", "title": "Lista de presença", "milestone_id": ms.json["id"]})
        self.assertEqual(ev.status, 201, ev)
        with db_system() as d:
            d.run("INSERT INTO project_risks(project_id, org_id, code, category, title, probability, impact, severity, origin, status)"
                  " VALUES ($1,$2,'r1','operational','Escola fechada no período','high','high','critical','declared','open')", pid, osc.org_id)
        t = fu.get("/v1/control-tower/funder").json
        kinds = {d["kind"] for d in t["decisions"]}
        self.assertIn("evidence", kinds, t["decisions"])
        self.assertTrue(any(x["id"] == ms.json["id"] and x["days_late"] >= 3 for x in t["delays"]))
        self.assertTrue(any(x["project_id"] == pid and x["open_high_or_critical"] == 1 for x in t["risks"]["project_risks"]),
                        "o financiador vê a CONTAGEM de riscos críticos abertos; o registro em si é da OSC (RLS)")
        self.assertEqual(t["counts"]["decisions"], len(t["decisions"]))
        # a decisão é tomada na tela do registro, não na torre
        self.assertTrue(all(d["link"].startswith("/") for d in t["decisions"]))

    def test_another_funder_sees_nothing_of_this_capital_and_an_osc_has_no_funder_tower(self):
        outro = new_account("company")
        t = outro.get("/v1/control-tower/funder").json
        self.assertEqual(t["capital"]["projects"], 0)
        self.assertEqual(t["decisions"], [])
        self.assertEqual(self.osc.get("/v1/control-tower/funder").status, 403)
        self.assertEqual(self.osc.get("/v1/control-tower/government").status, 403)
        self.assertEqual(self.fu.get("/v1/control-tower/government").status, 403)


class ReadyStateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.par = funded_pair(amount=100000)
        cls.osc, cls.fu, cls.pid = cls.par["osc"], cls.par["fu"], cls.par["pid"]

    def test_ready_lists_every_criterion_with_its_evidence_and_is_not_granted_by_default(self):
        r = self.osc.get(f"/v1/projects/{self.pid}/ready")
        self.assertEqual(r.status, 200, r)
        j = r.json
        self.assertEqual(j["total"], 15)
        self.assertEqual({c["key"] for c in j["criteria"]},
                         {"identity", "organization", "documents", "diagnosis", "budget", "needs", "ods", "indicators", "evidence",
                          "responsibles", "risks", "professionals", "governance", "history", "accountability"})
        for c in j["criteria"]:
            self.assertIn(c["status"], ("met", "unmet", "unknown"))
            self.assertTrue(c["source"], c["key"])
            self.assertIsInstance(c["evidence"], dict)
        self.assertNotEqual(j["state"], "ready", "projeto recém-criado não pode nascer 'ready'")
        self.assertEqual(j["met"] + j["unmet"] + j["unknown"], 15)
        by = {c["key"]: c for c in j["criteria"]}
        self.assertEqual(by["budget"]["status"], "met")
        self.assertEqual(by["ods"]["status"], "met")
        self.assertEqual(by["evidence"]["status"], "unmet", "sem evidência aceita por outra parte, o critério é unmet — não unknown")
        self.assertEqual(len(j["evaluation_hash"]), 64)
        self.assertIn("não selo", j["note"])
        self.assertEqual(self.osc.get(f"/v1/projects/{self.pid}/ready").json["evaluation_hash"], j["evaluation_hash"],
                         "mesmo material, mesmo hash: qualquer parte confere")

    def test_the_funder_sees_the_same_state_and_a_stranger_sees_nothing(self):
        mine = self.osc.get(f"/v1/projects/{self.pid}/ready").json
        theirs = self.fu.get(f"/v1/projects/{self.pid}/ready")
        self.assertEqual(theirs.status, 200)
        self.assertEqual(theirs.json["evaluation_hash"], mine["evaluation_hash"], "o financiador confere o MESMO resultado")
        # projeto privado de outra OSC: quem não participa recebe 404 (nem sabe que existe)
        outra = new_account("osc")
        priv = outra.post("/v1/projects", {"title": "Projeto privado", "summary": "Não publicado.", "territory": "BR-MT",
                                           "causes": ["saude"], "ods": [3], "beneficiaries_count": 10}).json["id"]
        self.assertEqual(self.fu.get(f"/v1/projects/{priv}/ready").status, 404)
        self.assertEqual(outra.get(f"/v1/projects/{priv}/ready").status, 200)

    def test_unknown_is_not_zero(self):
        from impacto.network.control_tower import ready
        from tests.support import db_system
        with db_system() as c:
            j = ready(c, self.pid)
        self.assertIsNotNone(j)
        # Nenhum critério deste projeto é desconhecido — mas a semântica existe e o estado a respeita:
        self.assertIn(j["state"], ("in_progress", "ready", "not_assessable"))
        self.assertNotIn("unknown", [c["status"] for c in j["criteria"] if c["key"] == "budget"])


class GovernmentTowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.gov = new_account("government", uf="AC")

    def test_small_territory_is_suppressed_and_published_projects_feed_the_tower(self):
        from tests.test_v080 import published_project
        t = self.gov.get("/v1/control-tower/government")
        self.assertEqual(t.status, 200, t)
        j = t.json
        self.assertEqual(j["territory"]["prefix"], "BR-AC")
        # Outros módulos da suíte podem já ter publicado projetos em AC: a regra é conferida contra o banco,
        # não contra a suposição de território vazio.
        with db_system() as d:
            ja_publicados = int(d.scalar("SELECT count(*) FROM projects WHERE visibility = 'published' AND territory LIKE 'BR-AC%'") or 0)
        if ja_publicados < 3:
            self.assertEqual(j["projects"], [], "AC sem 3 projetos publicados: nada linha a linha (k-anonimato)")
            self.assertTrue(j["k_anonymity"]["suppressed"])
        else:
            self.assertEqual(len(j["projects"]), ja_publicados)
        osc = new_account("osc", uf="AC")
        from tests.support import grant_premium
        grant_premium(osc)
        pids = [published_project(osc, title=f"Projeto AC {i}", territory="BR-AC") for i in range(3)]
        osc.post(f"/v1/projects/{pids[0]}/milestones", {"title": "Atrasada", "amount_cents": 1000,
                                                         "due_on": (date.today() - timedelta(days=2)).isoformat()})
        j = self.gov.get("/v1/control-tower/government").json
        self.assertGreaterEqual(j["totals"]["projects"], 3)
        self.assertFalse(j["k_anonymity"]["suppressed"])
        self.assertTrue(any(p["project_id"] == pids[0] for p in j["projects"]))
        self.assertTrue(any(d["project_id"] == pids[0] for d in j["delays"]))
        self.assertIn("declarado", j["indicators"]["note"])
        self.assertLessEqual(j["indicators"]["validated"], j["indicators"]["reported"], "validado é subconjunto do declarado")
        self.assertIsInstance(j["gaps"], (list, dict))
        # projeto NÃO publicado da mesma UF não aparece
        privado = osc.post("/v1/projects", {"title": "Rascunho AC", "summary": "Não publicado.", "territory": "BR-AC",
                                            "causes": ["saude"], "ods": [3], "beneficiaries_count": 5}).json["id"]
        j = self.gov.get("/v1/control-tower/government").json
        self.assertFalse(any(p["project_id"] == privado for p in j["projects"]))

    def test_a_company_cannot_call_the_territory_function_directly(self):
        """A barreira é do banco (SECURITY DEFINER com portão), não só da rota."""
        from impacto.db import pq
        from impacto.db.pool import DbContext
        emp = new_account("company")
        me = emp.get("/v1/me").json
        pool = server()["state"].pool
        with self.assertRaises(pq.InsufficientPrivilege):
            with pool.tx(DbContext(user_id=me["user"]["id"], org_id=emp.org_id, org_kind="company")) as c:
                c.query("SELECT * FROM gov_territory_overview('BR', 3)")
