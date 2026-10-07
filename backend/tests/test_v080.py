"""v0.8.0 — jornadas reais via HTTP + PostgreSQL real para os módulos novos:
financiador PF, ODS/indicadores/grafo/diagnóstico, compras, contribuição e pagamentos, risco, rede/profissionais, mapa, relatórios,
rastreamento. Cada módulo inclui testes NEGATIVOS e de isolamento entre organizações (cross-tenant)."""
import json
import unittest
from datetime import date

from impacto.db import pq
from tests.support import Client, db_system, grant_premium, make_admin, new_account, server


def published_project(osc: Client, title="Projeto de teste", cause="educacao", territory="BR-MT", budget_items=((1, 100000),)) -> str:
    pid = osc.post("/v1/projects", {"title": title, "summary": "Resumo do projeto", "territory": territory, "causes": [cause], "ods": [4],
                                    "beneficiaries_count": 30}).json["id"]
    for q, c in budget_items:
        assert osc.post(f"/v1/projects/{pid}/budget-items", {"description": "Item", "quantity": q, "unit_cost_cents": c}).status == 201
    assert osc.post(f"/v1/projects/{pid}/publish").status == 200
    return pid


def funded_pair(funder_kind="company", amount=100000, budget_items=((1, 100000),)) -> dict:
    """OSC + financiador com projeto publicado, candidatura aprovada (inserida pelo banco) e aporte registrado pela API."""
    osc, fu = new_account("osc"), new_account(funder_kind)
    grant_premium(osc)
    pid = published_project(osc, budget_items=budget_items)
    with db_system() as d:
        # v0.23.0 — a candidatura nasce em rascunho e CAMINHA. `trg_application_status_graph`
        # recusa nascer aprovada, porque isso pularia o processo inteiro sem deixar uma única
        # transição registrada. O atalho que existia aqui era exatamente o estado impossível que
        # a máquina de estados no banco passou a impedir, então o arranjo percorre o grafo.
        aid = d.scalar("INSERT INTO applications(project_id, osc_org_id, funder_org_id, origin, status)"
                       " VALUES ($1,$2,$3,'funder_interest','draft') RETURNING id::text",
                       pid, osc.org_id, fu.org_id)
        for passo in ("submitted", "screening", "due_diligence", "approved"):
            d.run("UPDATE applications SET status = $2 WHERE id = $1", aid, passo)
    r = fu.post(f"/v1/applications/{aid}/commitments", {"amount_cents": amount})
    assert r.status == 201, r
    return {"osc": osc, "fu": fu, "pid": pid, "aid": aid, "cid": r.json["id"]}


class IndividualFunderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_individual_registers_without_cnpj_and_funds_with_masked_name(self):
        pf = new_account("individual", legal_name="Maria da Silva Doadora")
        me = pf.get("/v1/me").json
        self.assertEqual(me["active_org"]["kind"], "individual")
        self.assertEqual(pf.put("/v1/org/funder-profile", {"causes": ["educacao"], "territories": ["BR-MT"]}).status, 200)
        osc = new_account("osc")
        pid = published_project(osc)
        self.assertEqual(pf.get("/v1/feed/projects").status, 200)
        r = pf.post("/v1/applications/interest", {"project_id": pid})
        self.assertEqual(r.status, 201, r)
        # a OSC vê o nome mascarado (privacidade por padrão)
        apps = osc.get("/v1/applications").json["items"]
        self.assertEqual(apps[0]["funder_org_name"], "Apoiador pessoa física")
        self.assertNotIn("Maria", json.dumps(apps))
        # opt-in explícito revela o nome
        self.assertEqual(pf.put("/v1/org/funder-profile", {"causes": ["educacao"], "public_name": True}).status, 200)
        self.assertEqual(osc.get("/v1/applications").json["items"][0]["funder_org_name"], "Maria da Silva Doadora")

    def test_individual_cannot_do_company_or_osc_things(self):
        pf = new_account("individual")
        self.assertEqual(pf.post("/v1/calls", {"title": "Edital X", "causes": ["educacao"], "status": "draft"}).json["code"], "wrong_org_kind")
        self.assertEqual(pf.get("/v1/fiscal/estimates").status, 403)
        self.assertEqual(pf.post("/v1/projects", {"title": "Abc", "territory": "BR-MT"}).status, 403)
        # cadastro de PF não aceita lista de CNPJ obrigatória, mas osc/company continuam exigindo
        c = Client()
        r = c.post("/v1/auth/register", {"email": "x@teste.org", "password": "Senha-Teste-Forte-2026", "full_name": "X Y", "accept_terms": True,
                                          "organization": {"kind": "company", "legal_name": "Sem CNPJ Ltda"}})
        self.assertEqual(r.status, 422)


class ImpactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.p = funded_pair()
        cls.osc, cls.fu, cls.pid = cls.p["osc"], cls.p["fu"], cls.p["pid"]
        cls.other_osc = new_account("osc")

    def test_ods_catalog_and_honest_targets(self):
        goals = self.osc.get("/v1/ods").json
        self.assertEqual(len(goals["items"]), 17)
        self.assertTrue(all(g["targets_loaded"] == 0 for g in goals["items"]))   # metas oficiais NÃO são embutidas
        self.assertEqual(self.osc.get("/v1/ods/18/targets").status, 404)
        self.assertEqual(self.osc.get("/v1/ods/abc/targets").status, 404)
        r = self.osc.put(f"/v1/projects/{self.pid}/ods-targets", {"items": [{"ods": 4, "target_code": "4.1"}]})
        self.assertEqual(r.json["code"], "unknown_target")
        r = self.osc.put(f"/v1/projects/{self.pid}/ods-targets", {"items": [{"ods": 4, "rationale": "Educação de qualidade"}, {"ods": 10}]})
        self.assertEqual(r.status, 200)
        imp = self.osc.get(f"/v1/projects/{self.pid}/impact").json
        self.assertEqual({a["ods"] for a in imp["ods_alignment"]}, {4, 10})
        self.assertEqual({a["ods"]: a["alignment_level"] for a in imp["ods_alignment"]}[10], "declared")       # sem indicador → apenas declarado
        self.assertTrue(all(a["alignment_level"] in ("declared", "supported_by_evidence") for a in imp["ods_alignment"]))

    def test_indicator_reported_vs_validated_flow(self):
        cat = self.osc.get("/v1/indicators/catalog?ods=4").json["items"]
        ind = next(i for i in cat if i["code"] == "trained_people")
        self.assertEqual(ind["origin"], "platform")
        pi = self.osc.post(f"/v1/projects/{self.pid}/indicators", {"indicator_id": ind["id"], "baseline": 0, "baseline_source": "Lista de presença do primeiro encontro", "target": 40, "method": "Lista de presença"}).json["id"]
        self.assertEqual(self.osc.post(f"/v1/projects/{self.pid}/indicators", {"indicator_id": ind["id"]}).status, 409)
        ev = self.osc.post(f"/v1/projects/{self.pid}/evidences", {"kind": "attendance", "title": "Lista de presença turma A"}).json["id"]
        v = self.osc.post(f"/v1/project-indicators/{pi}/values", {"value": 20, "measured_on": date.today().isoformat(), "evidence_id": ev})
        self.assertEqual(v.status, 201, v)
        vid = v.json["id"]
        # a OSC não valida o próprio valor (rota exclusiva de financiador)
        self.assertEqual(self.osc.post(f"/v1/indicator-values/{vid}/review", {"status": "validated"}).status, 403)
        # outra OSC não enxerga nem valida
        self.assertEqual(self.other_osc.post(f"/v1/indicator-values/{vid}/review", {"status": "validated"}).status, 403)
        stranger = new_account("company")
        self.assertEqual(stranger.post(f"/v1/indicator-values/{vid}/review", {"status": "validated"}).status, 404)   # sem aporte no projeto
        imp = self.osc.get(f"/v1/projects/{self.pid}/impact").json
        row = next(i for i in imp["indicators"] if i["id"] == pi)
        self.assertEqual((row["latest_reported"], row["latest_validated"], row["progress_reported_pct"], row["progress_validated_pct"]), (20.0, None, 50.0, None))
        # valor sem evidência não pode ser validado
        v2 = self.osc.post(f"/v1/project-indicators/{pi}/values", {"value": 25, "measured_on": date.today().isoformat()}).json["id"]
        r = self.fu.post(f"/v1/indicator-values/{v2}/review", {"status": "validated"})
        self.assertEqual(r.json["code"], "evidence_required")
        self.assertEqual(self.fu.post(f"/v1/indicator-values/{vid}/review", {"status": "validated", "note": "conferido"}).status, 200)
        imp = self.osc.get(f"/v1/projects/{self.pid}/impact").json
        row = next(i for i in imp["indicators"] if i["id"] == pi)
        self.assertEqual(row["latest_validated"], 20.0)
        self.assertEqual(row["progress_validated_pct"], 50.0)
        # validado não pode ser removido
        self.assertEqual(self.osc.delete(f"/v1/projects/{self.pid}/indicators/{pi}").json["code"], "has_validated_values")
        # no banco: "validado" por quem reportou é recusado (CHECK de separação de funções)
        with db_system() as d:
            with self.assertRaises(pq.CheckViolation):
                d.run("UPDATE indicator_values SET status = 'validated', validated_by = created_by, validated_by_org = org_id WHERE id = $1", v2)

    def test_graph_link_types_and_external_validation(self):
        n1 = self.osc.post(f"/v1/projects/{self.pid}/graph/nodes", {"kind": "activity", "label": "Aulas semanais"}).json["id"]
        n2 = self.osc.post(f"/v1/projects/{self.pid}/graph/nodes", {"kind": "outcome", "label": "Alunos leem melhor"}).json["id"]
        base = f"/v1/projects/{self.pid}/graph/edges"
        self.assertEqual(self.osc.post(base, {"from_node": n1, "to_node": n2, "link_type": "observed_evidence"}).json["code"], "evidence_required")
        self.assertEqual(self.osc.post(base, {"from_node": n1, "to_node": n2, "link_type": "validated_causality"}).json["code"], "use_validation")
        self.assertEqual(self.osc.post(base, {"from_node": n1, "to_node": n1}).status, 422)   # laço no mesmo nó (CHECK)
        eid = self.osc.post(base, {"from_node": n1, "to_node": n2}).json["id"]
        g = self.osc.get(f"/v1/projects/{self.pid}/graph").json
        self.assertEqual(next(e for e in g["edges"] if e["id"] == eid)["link_type"], "hypothesis")   # padrão é hipótese, nunca causa
        self.assertIn("validated_causality", g["legend"])
        ev = self.osc.post(f"/v1/projects/{self.pid}/evidences", {"kind": "report", "title": "Avaliação externa"}).json["id"]
        # evidência não aceita ainda → financiador não consegue validar causalidade
        r = self.fu.post(f"/v1/graph-edges/{eid}/validate", {"evidence_id": ev, "note": "Avaliação pareada conferida pelo comitê"})
        self.assertEqual(r.json["code"], "evidence_not_accepted")
        self.assertEqual(self.fu.post(f"/v1/evidences/{ev}/review", {"status": "accepted"}).status, 200)
        self.assertEqual(self.osc.post(f"/v1/graph-edges/{eid}/validate", {"evidence_id": ev, "note": "Tentativa da própria OSC"}).status, 403)
        self.assertEqual(self.fu.post(f"/v1/graph-edges/{eid}/validate", {"evidence_id": ev, "note": "Avaliação pareada conferida pelo comitê"}).status, 200)
        self.assertEqual(self.osc.delete(f"{base}/{eid}").json["code"], "validated")        # OSC não apaga validação externa
        with db_system() as d:                                                             # o banco exige revisor externo + evidência
            with self.assertRaises(pq.CheckViolation):
                d.run("UPDATE impact_edges SET link_type = 'validated_causality', reviewed_by_org = org_id WHERE id = $1 AND link_type <> 'validated_causality'", eid)
                d.run("INSERT INTO impact_edges(project_id, org_id, from_node, to_node, link_type) SELECT project_id, org_id, from_node, to_node, 'validated_causality' FROM impact_edges WHERE id = $1", eid)

    def test_cross_tenant_isolation(self):
        # projeto publicado é visível; dados de execução (valores, grafo) de terceiros não editáveis
        self.assertEqual(self.other_osc.put(f"/v1/projects/{self.pid}/ods-targets", {"items": [{"ods": 1}]}).status, 404)
        self.assertEqual(self.other_osc.post(f"/v1/projects/{self.pid}/graph/nodes", {"kind": "need", "label": "Invasor"}).status, 404)
        self.assertEqual(self.other_osc.post(f"/v1/projects/{self.pid}/indicators", {"indicator_id": "00000000-0000-0000-0000-000000000000"}).status, 404)
        priv = self.osc.post("/v1/projects", {"title": "Privado", "territory": "BR-MT"}).json["id"]    # rascunho (não publicado)
        self.assertEqual(self.other_osc.get(f"/v1/projects/{priv}/impact").status, 404)
        self.assertEqual(self.other_osc.get(f"/v1/projects/{priv}/graph").status, 404)
        # RLS direta: outra organização não lê valores de indicador do projeto
        from impacto.db.pool import DbContext
        st = server()["state"]
        with st.pool.tx(DbContext(user_id=self.other_osc.user["id"], org_id=self.other_osc.org_id, org_kind="osc")) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM indicator_values"), 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM impact_edges"), 0)

    def test_diagnosis_to_project_flow(self):
        d = self.osc.post("/v1/diagnoses", {"title": "Diagnóstico leitura", "project_id": self.pid, "need_statement": "Baixa proficiência em leitura"}).json["id"]
        r = self.osc.post(f"/v1/diagnoses/{d}/apply")
        self.assertEqual(r.json["code"], "incomplete_diagnosis")
        self.assertIn("Causas", r.json["details"]["missing"])
        full = {"title": "Diagnóstico leitura", "project_id": self.pid, "need_statement": "Baixa proficiência em leitura entre 8-10 anos",
                "root_causes": [{"text": "Falta de acervo", "source": "levantamento da escola", "evidence_level": "observado"}],
                "objective": "Elevar a proficiência", "goals": [{"text": "Formar 40 alunos", "indicator_code": "sessions_held", "target": 40}],
                "action_plan": [{"action": "Oficinas semanais", "owner": "Coordenação"}]}
        up = self.osc.put(f"/v1/diagnoses/{d}", full)
        self.assertEqual(up.json["missing"], [])
        ap = self.osc.post(f"/v1/diagnoses/{d}/apply")
        self.assertEqual(ap.status, 200, ap)
        proj = self.osc.get(f"/v1/projects/{self.pid}").json
        self.assertIn("Baixa proficiência", proj["problem"])
        g = self.osc.get(f"/v1/projects/{self.pid}/graph").json
        self.assertTrue(g["nodes"])
        # isolamento
        self.assertEqual(self.other_osc.get(f"/v1/diagnoses/{d}").status, 404)
        self.assertEqual(self.other_osc.put(f"/v1/diagnoses/{d}", full).status, 404)
        self.assertEqual(self.fu.get("/v1/diagnoses").status, 403)

    def test_determinants_k_anonymity_and_honest_note(self):
        gov = new_account("government")
        r = gov.get("/v1/determinants?territory=BR").json
        self.assertTrue(all(x["suppressed"] or x["projects"] >= 3 for x in r["domains"]))
        self.assertIn("NÃO são estatísticas populacionais", r["note"])
        self.assertEqual(self.osc.get("/v1/determinants").status, 403)


class ProcurementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc")
        cls.pid = published_project(cls.osc)
        cls.other = new_account("osc")
        with db_system() as d:   # segundo usuário administrador na mesma OSC
            cls.second = new_account("osc")
            d.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'admin')", cls.second.user["id"], cls.osc.org_id)
        assert cls.second.post("/v1/me/switch-org", {"org_id": cls.osc.org_id}).status == 200

    def req(self, amount=100000):
        return self.osc.post(f"/v1/projects/{self.pid}/procurement", {"description": "Compra de violões", "estimated_cents": amount}).json["id"]

    def quote(self, rid, name, amount):
        r = self.osc.post(f"/v1/procurement/{rid}/quotes", {"supplier_name": name, "amount_cents": amount})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def test_default_policy_requires_three_quotes_and_exception_needs_other_approver(self):
        self.assertEqual(self.osc.get("/v1/procurement/policy").json["min_quotes"], 3)
        rid = self.req()
        q1 = self.quote(rid, "Loja A", 100000)
        self.quote(rid, "Loja B", 110000)
        self.assertEqual(self.osc.post(f"/v1/procurement/{rid}/quotes", {"supplier_name": "loja a", "amount_cents": 5}).json["code"], "duplicate_supplier")
        r = self.osc.post(f"/v1/procurement/{rid}/decide", {"quotation_id": q1})
        self.assertEqual(r.json["code"], "exception_required")
        self.assertEqual(r.json["details"], {"required": 3, "have": 2})
        r = self.osc.post(f"/v1/procurement/{rid}/decide", {"quotation_id": q1, "exception_reason": "Só dois fornecedores na cidade"})
        self.assertEqual(r.json["status"], "exception_pending")
        self.assertEqual(self.osc.post(f"/v1/procurement/{rid}/approve-exception").json["code"], "self_approval")
        self.assertEqual(self.second.post(f"/v1/procurement/{rid}/approve-exception").status, 200)
        self.assertEqual(self.osc.get(f"/v1/procurement/{rid}").json["request"]["status"], "exception_approved")
        # despesa só pode referenciar pedido decidido/aprovado
        r = self.osc.post(f"/v1/projects/{self.pid}/expenses", {"description": "Violões", "amount_cents": 100000, "paid_on": date.today().isoformat(), "procurement_request_id": rid})
        self.assertEqual(r.status, 201, r)

    def test_benchmark_flags_outlier_and_requires_justification(self):
        rid = self.req(100000)
        a = self.quote(rid, "Loja A", 100000)
        self.quote(rid, "Loja B", 105000)
        c_id = self.quote(rid, "Loja C", 200000)
        rep = self.osc.get(f"/v1/procurement/{rid}").json
        self.assertTrue(rep["meets_policy"])
        b = rep["benchmark"]
        self.assertEqual((b["count"], b["median_cents"], b["min_cents"], b["max_cents"]), (3, 105000, 100000, 200000))
        flagged = [q for q in rep["quotes"] if q["flag"]]
        self.assertEqual(len(flagged), 1)
        self.assertNotIn("fraude", json.dumps(rep).lower())              # linguagem: sinaliza padrão, não acusa
        self.assertIn("possivelmente acima", flagged[0]["flag"])
        self.assertEqual(self.osc.post(f"/v1/procurement/{rid}/decide", {"quotation_id": c_id}).json["code"], "reason_required")
        self.assertEqual(self.osc.post(f"/v1/procurement/{rid}/decide", {"quotation_id": a}).json["status"], "decided")
        self.assertEqual(self.osc.post(f"/v1/procurement/{rid}/quotes", {"supplier_name": "Tardia", "amount_cents": 1}).json["code"], "closed")

    def test_configurable_policy_and_expense_guard(self):
        pol = self.other.put("/v1/procurement/policy", {"min_quotes": 1, "quote_threshold_cents": 50000, "outlier_pct": 20})
        self.assertEqual(pol.status, 200)
        self.assertEqual(self.other.get("/v1/procurement/policy").json["min_quotes"], 1)
        self.assertEqual(self.osc.get("/v1/procurement/policy").json["min_quotes"], 3)       # política é por organização
        rid = self.req()
        self.assertEqual(self.osc.post(f"/v1/projects/{self.pid}/expenses", {"description": "Xx", "amount_cents": 100, "paid_on": date.today().isoformat(),
                                                                              "procurement_request_id": rid}).json["code"], "procurement_not_decided")
        self.assertEqual(self.osc.put("/v1/procurement/policy", {"min_quotes": 0}).status, 422)

    def test_cross_tenant(self):
        rid = self.req()
        self.assertEqual(self.other.get(f"/v1/procurement/{rid}").status, 404)
        self.assertEqual(self.other.post(f"/v1/procurement/{rid}/quotes", {"supplier_name": "Intruso", "amount_cents": 10}).status, 404)
        self.assertEqual(self.other.post(f"/v1/projects/{self.pid}/procurement", {"description": "abc", "estimated_cents": 5}).status, 404)
        fu = new_account("company")
        self.assertEqual(fu.get(f"/v1/projects/{self.pid}/procurement").json["items"], [])    # sem aporte → RLS oculta


class PaymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.admin, _ = make_admin()

    def test_state_machine_roles_and_commitment_sync(self):
        p = funded_pair(amount=100000)
        osc, fu, cid = p["osc"], p["fu"], p["cid"]
        pay = fu.post(f"/v1/commitments/{cid}/payments", {"amount_cents": 60000, "method": "pix", "external_ref": "E2E-1"})
        self.assertEqual(pay.status, 201, pay)
        pid1 = pay.json["id"]
        self.assertEqual(fu.post(f"/v1/commitments/{cid}/payments", {"amount_cents": 50000}).json["code"], "exceeds_commitment")
        self.assertEqual(osc.post(f"/v1/commitments/{cid}/payments", {"amount_cents": 1000}).status, 403)       # OSC não declara pagamento
        T = lambda c, pid, to, note=None: c.post(f"/v1/payments/{pid}/transition", {"to": to, "note": note})
        self.assertEqual(T(osc, pid1, "confirmed").json["code"], "invalid_transition")                              # nada declarado ainda
        self.assertEqual(T(fu, pid1, "awaiting_confirmation").status, 200)
        self.assertEqual(T(fu, pid1, "confirmed").json["code"], "invalid_transition")                               # financiador não confirma o próprio envio
        self.assertEqual(T(osc, pid1, "failed").json["code"], "note_required")
        self.assertEqual(T(osc, pid1, "confirmed").status, 200)
        self.assertEqual(T(fu, pid1, "created").status, 422)                                                         # estado fora do conjunto aceito
        self.assertEqual(T(osc, pid1, "awaiting_confirmation").json["code"], "invalid_transition")
        ev = fu.get(f"/v1/payments/{pid1}").json
        self.assertEqual([e["to_state"] for e in ev["events"]], ["created", "awaiting_confirmation", "confirmed"])
        pay2 = fu.post(f"/v1/commitments/{cid}/payments", {"amount_cents": 40000}).json["id"]
        T(fu, pay2, "awaiting_confirmation"); T(osc, pay2, "confirmed")
        status = osc.get(f"/v1/applications/{p['aid']}").json["commitments"][0]["status"]
        self.assertEqual(status, "confirmed")                                  # soma confirmada = valor do aporte
        led = osc.get(f"/v1/projects/{p['pid']}/ledger").json
        self.assertTrue(led["verification"]["valid"])
        # DB: máquina de estados e imutabilidade valem mesmo fora da API
        with db_system() as d:
            with self.assertRaises(pq.CheckViolation):
                d.run("UPDATE payment_records SET state = 'created' WHERE id = $1", pid1)
        with db_system() as d:
            with self.assertRaises(pq.CheckViolation):
                d.run("UPDATE payment_records SET amount_cents = amount_cents + 1 WHERE id = $1", pid1)
        with db_system() as d:
            with self.assertRaises(Exception):
                d.run("DELETE FROM payment_events WHERE payment_id = $1", pid1)

    def test_refund_flow_two_party_control(self):
        p = funded_pair(amount=50000)
        osc, fu = p["osc"], p["fu"]
        pid = fu.post(f"/v1/commitments/{p['cid']}/payments", {"amount_cents": 50000}).json["id"]
        for c, to in ((fu, "awaiting_confirmation"), (osc, "confirmed")):
            c.post(f"/v1/payments/{pid}/transition", {"to": to})
        self.assertEqual(fu.post(f"/v1/payments/{pid}/refunds", {"amount_cents": 60000, "reason": "Erro de valor"}).json["code"], "exceeds_refundable")
        rid = fu.post(f"/v1/payments/{pid}/refunds", {"amount_cents": 20000, "reason": "Valor lançado a maior"}).json["id"]
        self.assertEqual(fu.post(f"/v1/refunds/{rid}/decide", {"decision": "approved"}).json["code"], "self_decision")
        self.assertEqual(osc.post(f"/v1/refunds/{rid}/decide", {"decision": "completed"}).json["code"], "invalid_transition")
        self.assertEqual(osc.post(f"/v1/refunds/{rid}/decide", {"decision": "approved"}).status, 200)
        self.assertEqual(fu.post(f"/v1/refunds/{rid}/decide", {"decision": "completed"}).status, 403)                # só a OSC conclui
        self.assertEqual(osc.post(f"/v1/refunds/{rid}/decide", {"decision": "completed"}).status, 200)
        d = fu.get(f"/v1/payments/{pid}").json
        self.assertEqual((d["state"], d["refunded_cents"]), ("partially_refunded", 20000))
        rid2 = osc.post(f"/v1/payments/{pid}/refunds", {"amount_cents": 30000, "reason": "Devolução do saldo"}).json["id"]
        fu.post(f"/v1/refunds/{rid2}/decide", {"decision": "approved"})
        osc.post(f"/v1/refunds/{rid2}/decide", {"decision": "completed"})
        self.assertEqual(fu.get(f"/v1/payments/{pid}").json["state"], "refunded")
        self.assertEqual(fu.post(f"/v1/payments/{pid}/refunds", {"amount_cents": 1, "reason": "Já estornado"}).json["code"], "not_refundable")

    def test_dispute_and_cross_tenant(self):
        p = funded_pair(amount=30000)
        osc, fu = p["osc"], p["fu"]
        pid = fu.post(f"/v1/commitments/{p['cid']}/payments", {"amount_cents": 30000}).json["id"]
        fu.post(f"/v1/payments/{pid}/transition", {"to": "awaiting_confirmation"})
        self.assertEqual(osc.post(f"/v1/payments/{pid}/transition", {"to": "disputed"}).json["code"], "note_required")
        self.assertEqual(osc.post(f"/v1/payments/{pid}/transition", {"to": "disputed", "note": "Valor não identificado"}).status, 200)
        led = [e["entry_type"] for e in osc.get(f"/v1/projects/{p['pid']}/ledger").json["entries"]]
        self.assertIn("payment_disputed", led)
        stranger, stranger_osc = new_account("company"), new_account("osc")
        for s in (stranger, stranger_osc):
            self.assertEqual(s.get(f"/v1/payments/{pid}").status, 404)
            self.assertEqual(s.post(f"/v1/payments/{pid}/transition", {"to": "cancelled"}).status, 404)
            self.assertEqual(s.post(f"/v1/payments/{pid}/refunds", {"amount_cents": 1, "reason": "intruso"}).status, 404)
            self.assertEqual(s.get("/v1/payments").json["items"], [])
        self.assertEqual(stranger.post(f"/v1/commitments/{p['cid']}/payments", {"amount_cents": 100}).status, 404)

    def test_contribution_model_legal_gate(self):
        p = funded_pair(amount=40000)
        osc, fu, pid = p["osc"], p["fu"], p["pid"]
        self.assertEqual(osc.post(f"/v1/projects/{pid}/contribution-models", {"kind": "quota", "title": "Cotas"}).json["code"], "quota_fields_required")
        self.assertEqual(osc.post(f"/v1/projects/{pid}/contribution-models", {"kind": "donation", "title": "Doação", "refundable": True}).json["code"], "refund_policy_required")
        mid = osc.post(f"/v1/projects/{pid}/contribution-models", {"kind": "quota", "title": "Cotas de R$ 100", "quota_value_cents": 10000, "quotas_total": 4,
                                                                    "legal_structure": "A definir com assessoria jurídica"}).json["id"]
        # modelo não aprovado não pode ser usado em pagamento
        self.assertEqual(fu.post(f"/v1/commitments/{p['cid']}/payments", {"amount_cents": 10000, "contribution_model_id": mid}).json["code"], "contribution_model_not_approved")
        self.assertEqual(fu.get(f"/v1/projects/{pid}/contribution-models").json["items"], [])      # financiador só vê aprovados
        self.assertEqual(osc.post(f"/v1/contribution-models/{mid}/submit").status, 200)
        # a OSC não consegue se autoaprovar: rota é administrativa e o banco recusa a coluna
        self.assertEqual(osc.post(f"/v1/admin/contribution-models/{mid}/decide", {"approve": True, "note": "autoaprovação indevida"}).status, 403)
        from impacto.db.pool import DbContext
        with server()["state"].pool.tx(DbContext(user_id=osc.user["id"], org_id=osc.org_id, org_kind="osc")) as c:
            with self.assertRaises(pq.InsufficientPrivilege):
                c.run("UPDATE contribution_models SET status = 'approved', legal_reviewer = $2, legal_note = 'x', approved_at = now() WHERE id = $1", mid, osc.user["id"])
        self.assertEqual(self.admin.post(f"/v1/admin/contribution-models/{mid}/decide", {"approve": True, "note": "Estrutura revisada pelo jurídico"}).status, 200)
        self.assertEqual(len(fu.get(f"/v1/projects/{pid}/contribution-models").json["items"]), 1)
        r = fu.post(f"/v1/commitments/{p['cid']}/payments", {"amount_cents": 10000, "contribution_model_id": mid})
        self.assertEqual(r.status, 201, r)
        with server()["state"].pool.tx(DbContext(user_id=osc.user["id"], org_id=osc.org_id, org_kind="osc")) as c:
            with self.assertRaises(pq.InsufficientPrivilege):                                        # termos aprovados são imutáveis
                c.run("UPDATE contribution_models SET refundable = true, refund_policy = 'qualquer' WHERE id = $1", mid)

    def test_statement_import_and_reconciliation(self):
        p = funded_pair(amount=75000)
        osc, fu = p["osc"], p["fu"]
        pid = fu.post(f"/v1/commitments/{p['cid']}/payments", {"amount_cents": 75000, "external_ref": "PIX-ABC"}).json["id"]
        fu.post(f"/v1/payments/{pid}/transition", {"to": "awaiting_confirmation"})
        csv_text = f"data;valor;descricao;referencia\n{date.today().strftime('%d/%m/%Y')};750,00;PIX RECEBIDO;PIX-ABC\n{date.today().isoformat()};12,34;TARIFA;\n"
        r = osc.post("/v1/statements", {"filename": "extrato.csv", "csv": csv_text})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["reconciliation"]["matched"], 1)
        self.assertEqual(osc.get(f"/v1/payments/{pid}").json["reconciliation_status"], "matched")
        self.assertEqual(osc.post("/v1/statements", {"filename": "extrato.csv", "csv": csv_text}).json["code"], "already_imported")
        self.assertEqual(osc.post("/v1/statements", {"filename": "x.csv", "csv": "foo;bar\n1;2\n3;4"}).json["code"], "invalid_statement")
        self.assertEqual(osc.post("/v1/statements", {"filename": "y.csv", "csv": "data;valor\nontem;abc\n"}).json["code"], "invalid_statement")
        self.assertEqual(fu.post("/v1/statements", {"filename": "z.csv", "csv": csv_text + "\n"}).status, 403)          # só OSC
        lines = osc.get("/v1/statements/lines").json
        self.assertEqual(lines["summary"]["matched"], 1)
        self.assertEqual(new_account("osc").get("/v1/statements/lines").json["items"], [])                          # isolamento


class RiskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.admin, _ = make_admin()

    def test_signals_are_review_items_never_accusations(self):
        p = funded_pair(amount=100000)
        osc, fu, pid = p["osc"], p["fu"], p["pid"]
        same = {"description": "Compra de material", "amount_cents": 25000, "paid_on": date.today().isoformat(), "supplier_name": "Papelaria X", "supplier_cnpj": "11222333000181"}
        # CNPJ de teste precisa ser válido: gera dígitos corretos
        from impacto.services.validators import cnpj_with_check_digits
        same["supplier_cnpj"] = cnpj_with_check_digits("112223330001")
        for _ in range(2):
            self.assertEqual(osc.post(f"/v1/projects/{pid}/expenses", same).status, 201)
        with db_system() as d:    # mesma pessoa vinculada à OSC e ao financiador
            d.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'viewer') ON CONFLICT DO NOTHING", osc.user["id"], fu.org_id)
        out = self.admin.post("/v1/admin/risk/scan", {"org_id": osc.org_id}).json
        self.assertGreaterEqual(out["total_new"], 2)
        sig = [s for s in self.admin.get("/v1/admin/risk/signals?limit=100").json["items"] if s["org_id"] == osc.org_id]
        types = {s["signal_type"] for s in sig}
        self.assertTrue({"duplicate_expense", "related_accounts"} <= types)
        self.assertNotIn("fraude", json.dumps(sig).lower())
        again = self.admin.post("/v1/admin/risk/scan", {"org_id": osc.org_id}).json
        self.assertEqual(again["total_new"], 0)                                                   # idempotente (dedupe_key)
        lvl = next(a for a in self.admin.get("/v1/admin/risk/assessments").json["items"] if a["org_id"] == osc.org_id)
        self.assertEqual(lvl["level"], "manual_review")
        # revisão humana exige justificativa
        s0 = sig[0]
        self.assertEqual(self.admin.post(f"/v1/admin/risk/signals/{s0['id']}/review", {"status": "dismissed", "note": "x"}).status, 422)
        self.assertEqual(self.admin.post(f"/v1/admin/risk/signals/{s0['id']}/review", {"status": "dismissed", "note": "Conselheiro declarado, sem conflito"}).status, 200)
        # sinais são invisíveis para a própria OSC e terceiros (RLS + rota admin)
        for c in (osc, fu):
            self.assertEqual(c.get("/v1/admin/risk/signals").status, 403)
        from impacto.db.pool import DbContext
        with server()["state"].pool.tx(DbContext(user_id=osc.user["id"], org_id=osc.org_id, org_kind="osc")) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM risk_signals"), 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM risk_assessments"), 0)

    def test_block_requires_human_decision_and_restricts_operations(self):
        osc = new_account("osc")
        pid = osc.post("/v1/projects", {"title": "Projeto bloqueável", "summary": "Resumo", "territory": "BR-MT", "causes": ["educacao"], "beneficiaries_count": 5}).json["id"]
        osc.post(f"/v1/projects/{pid}/budget-items", {"description": "Item", "quantity": 1, "unit_cost_cents": 1000})
        self.assertEqual(osc.post(f"/v1/admin/risk/orgs/{osc.org_id}/block", {"note": "tentativa indevida pela própria OSC"}).status, 403)
        self.assertEqual(self.admin.post(f"/v1/admin/risk/orgs/{osc.org_id}/block", {"note": "Revisão documental em andamento"}).status, 200)
        r = osc.post(f"/v1/projects/{pid}/publish")
        self.assertEqual((r.status, r.json["code"]), (423, "org_blocked"))
        # o scan automático nunca remove um bloqueio humano
        self.admin.post("/v1/admin/risk/scan", {"org_id": osc.org_id})
        lvl = next(a for a in self.admin.get("/v1/admin/risk/assessments").json["items"] if a["org_id"] == osc.org_id)
        self.assertEqual(lvl["level"], "blocked")
        with db_system() as d:     # CHECK: bloqueio sem decisor humano é impossível
            with self.assertRaises(pq.CheckViolation):
                d.run("UPDATE risk_assessments SET decided_by = NULL WHERE org_id = $1", osc.org_id)
        self.assertEqual(self.admin.post(f"/v1/admin/risk/orgs/{osc.org_id}/unblock", {"note": "Revisão concluída sem achados"}).status, 200)
        self.assertEqual(osc.post(f"/v1/projects/{pid}/publish").status, 200)


class NetworkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.admin, _ = make_admin()

    def test_messaging_requires_relationship_blocks_and_privacy(self):
        p = funded_pair()
        osc, fu = p["osc"], p["fu"]
        stranger = new_account("company")
        self.assertEqual(stranger.post(f"/v1/messages/{osc.org_id}", {"body": "Olá"}).json["code"], "no_relationship")
        r = fu.post(f"/v1/messages/{osc.org_id}", {"body": "Podemos conversar sobre o projeto?"})
        self.assertEqual(r.status, 201, r)
        cv = r.json["conversation_id"]
        convs = osc.get("/v1/messages/conversations").json["items"]
        self.assertEqual(convs[0]["unread"], 1)
        msgs = osc.get(f"/v1/messages/conversations/{cv}").json["items"]
        self.assertEqual(msgs[0]["body"], "Podemos conversar sobre o projeto?")
        self.assertEqual(osc.get("/v1/messages/conversations").json["items"][0]["unread"], 0)
        self.assertEqual(stranger.get(f"/v1/messages/conversations/{cv}").status, 404)               # terceiros não leem
        self.assertEqual(osc.post(f"/v1/messages/{osc.org_id}", {"body": "eu mesmo"}).status, 422)
        self.assertEqual(osc.post(f"/v1/messages/{fu.org_id}", {"body": ""}).status, 422)
        # bloqueio bilateral
        self.assertEqual(osc.post(f"/v1/network/block/{fu.org_id}").status, 200)
        self.assertEqual(fu.post(f"/v1/messages/{osc.org_id}", {"body": "Ainda aí?"}).json["code"], "blocked")
        self.assertEqual(osc.post(f"/v1/messages/{fu.org_id}", {"body": "Eu bloqueei"}).json["code"], "blocked")
        self.assertEqual(osc.delete(f"/v1/network/block/{fu.org_id}").status, 200)
        # moderação: o admin só lê mensagem denunciada e apenas oculta o conteúdo
        mid = fu.post(f"/v1/messages/{osc.org_id}", {"body": "conteúdo a moderar"}).json["id"]
        self.assertEqual(self.admin.get(f"/v1/admin/messages/{mid}").json["code"], "not_reported")
        self.assertEqual(osc.post("/v1/reports", {"target_type": "message", "target_id": mid, "reason": "inappropriate"}).status, 201)
        self.assertEqual(self.admin.get(f"/v1/admin/messages/{mid}").json["body"], "conteúdo a moderar")
        self.assertEqual(self.admin.post(f"/v1/admin/messages/{mid}/remove", {"reason": "Violação das regras"}).status, 200)
        shown = [m for m in osc.get(f"/v1/messages/conversations/{cv}").json["items"] if m["id"] == mid][0]
        self.assertTrue(shown["removed"] and shown["body"] is None)
        # RLS: ninguém altera o corpo de uma mensagem nem finge ser remetente
        from impacto.db.pool import DbContext
        with server()["state"].pool.tx(DbContext(user_id=fu.user["id"], org_id=fu.org_id, org_kind="company")) as c:
            with self.assertRaises(pq.InsufficientPrivilege):
                c.run("UPDATE messages SET body = 'adulterada' WHERE id = $1", mid)

    def test_mutual_follow_enables_messages(self):
        a, b = new_account("company"), new_account("osc")
        self.assertEqual(a.post(f"/v1/messages/{b.org_id}", {"body": "oi"}).json["code"], "no_relationship")
        a.post(f"/v1/network/follow/{b.org_id}")
        self.assertEqual(a.post(f"/v1/messages/{b.org_id}", {"body": "oi"}).status, 403)             # seguimento unilateral não basta
        b.post(f"/v1/network/follow/{a.org_id}")
        self.assertEqual(a.post(f"/v1/messages/{b.org_id}", {"body": "oi"}).status, 201)
        self.assertEqual(a.post(f"/v1/network/follow/{a.org_id}").status, 422)
        self.assertEqual(a.get("/v1/network").json["following"][0]["id"], b.org_id)

    def test_badges_have_no_ranking(self):
        osc = new_account("osc")
        items = osc.get("/v1/badges").json
        self.assertTrue(items["items"])
        blob = json.dumps(items).lower()
        for banned in ("points", "pontos", "leaderboard", "score", "position", "posição"):
            self.assertNotIn(banned, blob)
        self.assertFalse(any(i["earned"] for i in items["items"] if i["code"] == "profile_complete"))

    def test_professional_needs_offers_and_match_invariance(self):
        osc = new_account("osc")
        pid = published_project(osc)
        need = osc.post(f"/v1/projects/{pid}/needs", {"category": "contador", "title": "Prestação de contas trimestral"})
        self.assertEqual(need.status, 201, need)
        nid = need.json["id"]
        self.assertEqual(osc.post(f"/v1/projects/{pid}/needs", {"category": "mago", "title": "Inválida"}).json["code"], "unknown_category")
        prof = new_account("provider")
        self.assertEqual(prof.put("/v1/org/provider-profile", {"categories": ["contador"], "remote": True, "services": ["Contabilidade"]}).status, 200)
        self.assertEqual(prof.post("/v1/org/credentials", {"council": "CRC", "number": "123456", "uf": "MT", "holder_name": "Contador Teste"}).status, 201)
        o1 = prof.get("/v1/professional/opportunities").json["items"]
        m = next(x for x in o1 if x["id"] == nid)["match"]
        self.assertEqual(m["eligibility"], "needs_review")                               # credencial só autodeclarada
        self.assertTrue(any(r["code"] == "credential_required" for r in m["requirements"]))
        with db_system() as d:
            d.run("UPDATE professional_credentials SET verification_status = 'verified' WHERE org_id = $1", prof.org_id)
        m2 = next(x for x in prof.get("/v1/professional/opportunities").json["items"] if x["id"] == nid)["match"]
        self.assertEqual(m2["eligibility"], "eligible")
        # plano pago NÃO altera o resultado
        grant_premium(prof)
        m3 = next(x for x in prof.get("/v1/professional/opportunities").json["items"] if x["id"] == nid)["match"]
        for k in ("eligibility", "score", "confidence", "recommended_state"):
            self.assertEqual(m2[k], m3[k])
        # fora da área: oportunidades de outras categorias nem aparecem
        lawyer = new_account("provider")
        lawyer.put("/v1/org/provider-profile", {"categories": ["advogado"], "remote": True})
        self.assertNotIn(nid, [x["id"] for x in lawyer.get("/v1/professional/opportunities").json["items"]])
        # oferta
        self.assertEqual(osc.post(f"/v1/needs/{nid}/offers", {"message": "x"}).status, 403)       # OSC não oferece
        oid = prof.post(f"/v1/needs/{nid}/offers", {"message": "Posso ajudar"}).json["id"]
        self.assertEqual(prof.post(f"/v1/needs/{nid}/offers", {}).json["code"], "already_offered")
        offers = osc.get(f"/v1/needs/{nid}/offers").json["items"]
        self.assertEqual(offers[0]["match"]["eligibility"], "eligible")
        self.assertEqual(new_account("osc").get(f"/v1/needs/{nid}/offers").status, 404)           # outra OSC não vê
        self.assertEqual(prof.post(f"/v1/offers/{oid}/decide", {"decision": "accepted"}).status, 403)
        self.assertEqual(osc.post(f"/v1/offers/{oid}/decide", {"decision": "accepted"}).status, 200)
        # oferta cria relação: agora podem conversar
        self.assertEqual(prof.post(f"/v1/messages/{osc.org_id}", {"body": "Vamos alinhar escopo"}).status, 201)
        sug = osc.get(f"/v1/needs/{nid}/professionals").json["items"]
        self.assertTrue(all(s["match"]["eligibility"] != "blocked" for s in sug))


class GeoAndReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_location_precision_protects_exact_coordinates(self):
        osc = new_account("osc")
        pid = published_project(osc)
        fu = new_account("company")
        self.assertEqual(osc.put(f"/v1/projects/{pid}/location", {"precision": "exact"}).json["code"], "coordinates_required")
        self.assertEqual(osc.put(f"/v1/projects/{pid}/location", {"precision": "approximate", "lat": 95, "lng": 0}).status, 422)
        r = osc.put(f"/v1/projects/{pid}/location", {"precision": "approximate", "lat": -15.601234, "lng": -56.097654})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["public"]["precision"], "approximate")
        pt = next(p for p in fu.get("/v1/map/projects").json["points"] if p["id"] == pid)
        self.assertEqual(round(pt["lat"], 1), pt["lat"])                       # 1 casa decimal (~11 km)
        raw = fu.get(f"/v1/projects/{pid}").text if hasattr(fu.get(f"/v1/projects/{pid}"), "text") else fu.get(f"/v1/projects/{pid}").body.decode()
        self.assertNotIn("-15.601234", raw)
        self.assertNotIn("-56.097654", raw)
        self.assertNotIn("location_private", fu.get(f"/v1/projects/{pid}").json)
        self.assertEqual(osc.get(f"/v1/projects/{pid}").json["location_private"], {"lat": -15.60123, "lng": -56.09765})
        self.assertEqual(osc.put(f"/v1/projects/{pid}/location", {"precision": "municipality", "lat": -15.601234, "lng": -56.097654}).json["public"], None)
        self.assertNotIn(pid, [p["id"] for p in fu.get("/v1/map/projects").json["points"]])      # município: sem ponto
        by_uf = {x["uf"]: x["projects"] for x in fu.get("/v1/map/projects").json["by_uf"]}
        self.assertGreaterEqual(by_uf.get("MT", 0), 1)
        self.assertEqual(new_account("osc").put(f"/v1/projects/{pid}/location", {"precision": "region"}).status, 404)

    def test_reports_scope_language_and_csv_safety(self):
        p = funded_pair(amount=100000)
        osc, fu, pid = p["osc"], p["fu"], p["pid"]
        osc.post(f"/v1/projects/{pid}/expenses", {"description": "=HYPERLINK(\"http://x\")", "amount_cents": 5000, "paid_on": date.today().isoformat()})
        types = {t["type"] for t in osc.get("/v1/report-center").json["items"]}
        self.assertEqual(types, {"executive", "technical", "financial", "evidence", "ods", "esg", "audit", "board"})
        prov = new_account("provider")
        self.assertEqual({t["type"] for t in prov.get("/v1/report-center").json["items"]}, {"audit"})
        self.assertEqual(prov.get("/v1/report-center/financial").status, 404)
        ex = osc.get(f"/v1/report-center/executive?project_id={pid}").json
        self.assertEqual(ex["scope"]["projects"], 1)
        self.assertIn("não é rating ESG", ex["wording"])
        self.assertTrue(any(s["kind"] == "kv" for s in ex["sections"]))
        fx = fu.get("/v1/report-center/financial").json                        # financiador: só projetos com aporte
        self.assertTrue(all(isinstance(s["title"], str) for s in fx["sections"]))
        csv = osc.get(f"/v1/report-center/financial?project_id={pid}&format=csv")
        self.assertEqual(csv.status, 200)
        self.assertIn("text/csv", csv.headers["Content-Type"])
        body = csv.body.decode()
        self.assertIn("'=HYPERLINK", body)                                     # neutraliza injeção de fórmula
        self.assertNotIn(";=HYPERLINK", body)
        audit = osc.get("/v1/report-center/audit").json
        valid = [s for s in audit["sections"] if s["title"].startswith("Trilha")][0]["items"]
        self.assertEqual(valid[1]["value"], "sim")
        # escopo: não gera relatório de projeto alheio
        self.assertEqual(new_account("osc").get(f"/v1/report-center/executive?project_id={pid}").status, 404)
        self.assertEqual(new_account("company").get(f"/v1/report-center/executive?project_id={pid}").status, 404)
        self.assertEqual(osc.get("/v1/report-center/executive?format=xml").status, 422)
        self.assertEqual(osc.get("/v1/report-center/inexistente").status, 404)

    def test_esg_and_ods_reports_use_reported_wording(self):
        p = funded_pair()
        osc = p["osc"]
        cat = osc.get("/v1/indicators/catalog?esg=E").json["items"]
        pi = osc.post(f"/v1/projects/{p['pid']}/indicators", {"indicator_id": cat[0]["id"], "target": 100}).json["id"]
        osc.post(f"/v1/project-indicators/{pi}/values", {"value": 10, "measured_on": date.today().isoformat()})
        esg = osc.get("/v1/report-center/esg").json
        tbl = esg["sections"][0]
        self.assertEqual(tbl["columns"], ["Dimensão", "Indicadores", "Com valor reportado", "Com valor validado"])
        row = next(r for r in tbl["rows"] if r[0] == "E")
        self.assertEqual(row[1:], [1, 1, 0])                                   # reportado, nenhum validado
        ods = osc.get("/v1/report-center/ods").json
        self.assertTrue(any("Como ler" == s["title"] for s in ods["sections"]))


class ObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.admin, _ = make_admin()

    def test_traceparent_propagation(self):
        c = Client()
        tid = "4bf92f3577b34da6a3ce929d0e0e4736"
        c = new_account("osc")
        r = c.get("/v1/ods", headers={"traceparent": f"00-{tid}-00f067aa0ba902b7-01"})
        self.assertTrue(r.headers["traceparent"].startswith(f"00-{tid}-"))
        r = c.get("/v1/ods", headers={"traceparent": "lixo"})
        parts = r.headers["traceparent"].split("-")
        self.assertEqual((parts[0], len(parts[1]), len(parts[2])), ("00", 32, 16))
        self.assertNotEqual(parts[1], tid)
        r = c.get("/v1/ods", headers={"traceparent": "00-" + "0" * 32 + "-00f067aa0ba902b7-01"})
        self.assertNotEqual(r.headers["traceparent"].split("-")[1], "0" * 32)       # trace_id zerado é inválido (W3C)

    def test_error_aggregation_without_pii(self):
        from impacto import http as h
        st = server()["state"]
        spec = next(s for s in h.ROUTES if s.path == "/v1/dashboard")
        def boom(email):
            raise RuntimeError(f"falha para {email} cpf 12345678901 token abcdefghijklmnopqrstuvwxyz0123")
        for _ in range(2):
            try:
                boom("pessoa@exemplo.com")
            except RuntimeError as e:
                h._record_error(st, spec, "req-test", e)
        items = self.admin.get("/v1/admin/errors?limit=100").json["items"]
        row = next(i for i in items if i["exception_type"] == "RuntimeError" and i["route"] == "/v1/dashboard")
        self.assertGreaterEqual(row["occurrences"], 2)
        for secret in ("pessoa@exemplo.com", "12345678901", "abcdefghijklmnopqrstuvwxyz0123"):
            self.assertNotIn(secret, row["message"])
        self.assertEqual(new_account("osc").get("/v1/admin/errors").status, 403)
        self.assertEqual(self.admin.post(f"/v1/admin/errors/{row['id']}/resolve").status, 200)


class UnitTests(unittest.TestCase):
    def test_professional_engine_blocks_and_ignores_billing_inputs(self):
        from impacto.engines.match.professional import ProfessionalInput, evaluate
        prof = {"categories": ["advogado"], "remote": True, "languages": ["pt-BR"], "accepting_requests": True,
                "credentials": [{"council": "OAB", "status": "verified", "valid_until": None}], "completed_reviews": 5, "open_reviews": 0, "open_reviews_limit": 10}
        need = {"category": "contador", "remote_ok": True, "status": "open", "territory": "BR-MT"}
        r = evaluate(ProfessionalInput.build(prof, need))
        self.assertEqual(r["eligibility"], "blocked")
        self.assertEqual(r["recommended_state"], "bloqueada")
        need["category"] = "advogado"
        base = evaluate(ProfessionalInput.build(prof, need))
        polluted = evaluate(ProfessionalInput.build({**prof, "plan": "provider_premium", "subscription": "active", "voucher": "X"}, {**need, "plan_boost": 10}))
        for k in ("eligibility", "score", "confidence", "recommended_state", "features"):
            self.assertEqual(base[k], polluted[k])                              # campos de cobrança são descartados pela lista branca
        expired = evaluate(ProfessionalInput.build({**prof, "credentials": [{"council": "OAB", "status": "verified", "valid_until": date(2000, 1, 1)}]}, need))
        self.assertEqual(expired["eligibility"], "needs_review")
        closed = evaluate(ProfessionalInput.build(prof, {**need, "status": "filled"}))
        self.assertEqual(closed["eligibility"], "blocked")
        sparse = evaluate(ProfessionalInput.build({}, need))
        self.assertIsNone(sparse["score"])                                      # sem dados suficientes → sem nota

    def test_procurement_stats(self):
        from impacto.services.procurement import benchmark, flag_quotes
        self.assertEqual(benchmark([], 30), {"count": 0, "quotes": []})
        b = benchmark([100, 100, 400], 30)
        self.assertEqual((b["median_cents"], b["min_cents"], b["max_cents"]), (100, 100, 400))
        two = flag_quotes([{"amount_cents": 100}, {"amount_cents": 1000}], 30)
        self.assertTrue(all(q["flag"] is None for q in two))                    # < 3 cotações: sem sinalização estatística
        low = flag_quotes([{"amount_cents": 100}, {"amount_cents": 1000}, {"amount_cents": 1000}], 30)
        self.assertIn("abaixo", low[0]["flag"])

    def test_geo_precision_rules(self):
        from impacto.services.geo import public_point
        self.assertIsNone(public_point("x", -15.5, -56.1, "municipality"))
        self.assertIsNone(public_point("x", -15.5, -56.1, "region"))
        self.assertIsNone(public_point("x", None, None, "exact"))
        self.assertEqual(public_point("x", -15.123456, -56.654321, "exact")["lat"], -15.12346)
        n = public_point("x", -15.123456, -56.654321, "neighborhood")
        self.assertEqual((n["lat"], n["lng"]), (-15.12, -56.65))
        a1, a2 = public_point("p1", -15.12, -56.65, "approximate"), public_point("p1", -15.12, -56.65, "approximate")
        self.assertEqual(a1, a2)                                                # deslocamento determinístico (não vaza por repetição)

    def test_statement_parser(self):
        from impacto.services.payments import parse_statement
        rows = parse_statement("Data;Valor;Descricao\n05/10/2026;1.234,56;PIX\n2026-10-06;-10;Tarifa\n")
        self.assertEqual((rows[0]["amount_cents"], rows[1]["amount_cents"]), (123456, -1000))
        with self.assertRaises(ValueError):
            parse_statement("data;valor\n32/13/2026;10\n")
        with self.assertRaises(ValueError):
            parse_statement("data;valor\n")
        with self.assertRaises(ValueError):
            parse_statement("coluna;outra\n1;2\n")

    def test_error_fingerprint_is_stable_and_scrubbed(self):
        from impacto.observability import error_fingerprint
        def f(e): raise ValueError(e)
        out = []
        for _ in range(2):
            try:
                f("erro com a@b.com e 98765432100")
            except ValueError as e:
                out.append(error_fingerprint("/x", e))
        self.assertEqual(out[0], out[1])
        self.assertNotIn("a@b.com", out[0][1])
        self.assertNotIn("98765432100", out[0][1])

    def test_csv_injection_neutralized(self):
        from impacto.services.reports import _safe
        self.assertEqual(_safe("=1+1"), "'=1+1")
        self.assertEqual(_safe("@SUM(A1)"), "'@SUM(A1)")
        self.assertEqual(_safe("-5"), "-5")             # número negativo legítimo é preservado
        self.assertEqual(_safe(None), "")


if __name__ == "__main__":
    unittest.main()
