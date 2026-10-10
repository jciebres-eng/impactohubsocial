"""v0.28.0 — AI Usage & Cost Control, créditos, PIX, patrocínio e integridade financeira (ADR-347 a ADR-349).

O que se prova, contra HTTP e PostgreSQL reais (motor local; nenhum provedor externo):
  A. autorização e isolamento: tipo errado, papel insuficiente, créditos de outra organização, operação planejada → 501;
  B. créditos: cota de boas-vindas uma vez por organização E por pessoa; prévia mostra custo e fonte; execução cobra SÓ em
     sucesso; reserva impede gasto duplo em concorrência; idempotência devolve a mesma execução; saldo não negativo;
     saldo não é manipulável pelo frontend;
  C. pedidos e PIX: modo piloto sem pagamento; aprovação de piloto vira concessão PROMOCIONAL (nunca compra); pedido real
     só com regra ativa e provedor real; webhook sem segredo → 503; assinatura inválida → gravado sem efeito; repetido →
     sem crédito duplo; conciliação manual exige referência; cobrança simulada nunca credita compra;
  D. patrocínio: compromete créditos do patrocinador; beneficiário elegível é custeado; esgotado NÃO migra para cobrança
     pessoal; prestação de contas agregada só ao patrocinador; encerrar devolve o não usado;
  E. integridade: nenhum débito sem execução bem-sucedida; nenhum crédito sem confirmação; nenhum lançamento duplicado;
     cada execução cobrada tem registro; o razão é append-only e o portão SQL recusa lançamento fora da regra.
"""
from __future__ import annotations

import json
import os
import threading
import unittest
import uuid

from impacto.integrations.events import sign
from tests.support import Client, db_system, grant_premium, make_admin, make_staff, new_account

WELCOME = 60   # welcome.v1 (migração 0068): uma vez por organização e por pessoa
MONTHLY = 10   # monthly.light.v1: OSC e profissional, por mês civil
W = WELCOME + MONTHLY   # saldo promocional de uma OSC recém-criada


def _projeto(c: Client, title="Projeto A", territory="BR-MT-5103403", causes=("educacao",), items=(("Material pedagógico", 1, 50000),)) -> str:
    import datetime as dt
    r = c.post("/v1/projects", {
        "title": title, "summary": "Reforço escolar com leitura orientada para crianças do bairro.",
        "problem": "Crianças sem contraturno e sem acesso a livros adequados à idade.",
        "objectives": "Oferecer reforço de leitura orientada a trinta crianças três vezes por semana.",
        "methodology": "Oficinas de leitura com mediadores voluntários e acervo itinerante.",
        "territory": territory, "causes": list(causes), "ods": [4], "beneficiaries_description": "crianças de 7 a 10 anos da rede pública",
        "beneficiaries_count": 30, "budget_total_cents": 200_000,
        "starts_on": (dt.date.today() - dt.timedelta(days=10)).isoformat(), "ends_on": (dt.date.today() + dt.timedelta(days=90)).isoformat()})
    assert r.status == 201, r.json
    pid = r.json["id"]
    for d, q, uc in items:
        assert c.post(f"/v1/projects/{pid}/budget-items", {"description": d, "quantity": q, "unit_cost_cents": uc}).status == 201
    return pid


def _grant(org_id: str, credits: int, bucket="purchased", reason="purchase", key=None):
    with db_system() as d:
        d.run("INSERT INTO ai_credit_ledger(org_id, delta, reason, bucket, idempotency_key, note) VALUES ($1,$2,$3,$4,$5,'teste')",
              org_id, credits, reason, bucket, key or f"test:{uuid.uuid4()}")


def _balance(org_id: str, bucket: str) -> int:
    with db_system() as d:
        return int(d.scalar("SELECT ai_credit_balance_bucket($1,$2)", org_id, bucket))


class AuthorizationAndIsolationTests(unittest.TestCase):

    def test_an_operation_not_for_the_kind_is_refused_before_any_cost(self):
        gov = new_account("government")
        r = gov.post("/v1/ai/preview", {"operation_code": "assist.structure_need"})   # só OSC
        self.assertEqual(r.status, 403, r.json)
        self.assertEqual(r.json["code"], "ai_operation_not_for_kind")

    def test_a_planned_operation_answers_501_and_is_in_the_catalog(self):
        osc = new_account("company")
        r = osc.post("/v1/ai/preview", {"operation_code": "similarity.batch"})
        self.assertEqual(r.status, 501, r.json)
        cat = osc.get("/v1/ai/operations").json["items"]
        self.assertIn("planned", {o["status"] for o in cat if o["code"] == "similarity.batch"})

    def test_a_viewer_cannot_run_a_member_operation(self):
        from tests.support import set_role
        osc = new_account("osc")
        set_role(osc.user["id"], osc.org_id, "viewer")
        r = osc.post("/v1/ai/preview", {"operation_code": "assist.structure_need"})
        self.assertEqual(r.status, 403, r.json)

    def test_an_organization_never_sees_another_organizations_credits_or_executions(self):
        a, b = new_account("osc"), new_account("osc")
        _grant(a.org_id, 500)
        self.assertEqual(b.get("/v1/ai/center").json["balances"]["purchased"]["balance"], 0)
        a.get("/v1/ai/center")   # concede a cota de boas-vindas de A
        self.assertEqual([x for x in b.get("/v1/ai/executions").json["items"]], [])
        with db_system() as d:
            ex = d.scalar("SELECT id::text FROM ai_executions WHERE org_id = $1 LIMIT 1", a.org_id)
        if ex:
            self.assertEqual(b.get(f"/v1/ai/executions/{ex}").status, 404)

    def test_the_frontend_cannot_set_price_or_balance(self):
        osc = new_account("osc")
        r = osc.post("/v1/ai/preview", {"operation_code": "similarity.single", "credits_required": 0, "funding_source": "free"})
        # campos desconhecidos são rejeitados pelo esquema (422), não ignorados em silêncio
        self.assertEqual(r.status, 422, r.json)


class QuotaAndCreditsTests(unittest.TestCase):

    def test_welcome_quota_is_granted_once_per_org_and_once_per_person(self):
        osc = new_account("osc")
        c1 = osc.get("/v1/ai/center").json
        self.assertEqual(c1["balances"]["promotional"]["balance"], W)
        self.assertEqual([g["policy"] for g in c1["quotas_granted_now"]], ["welcome.v1", "monthly.light.v1"])
        c2 = osc.get("/v1/ai/center").json
        self.assertEqual(c2["balances"]["promotional"]["balance"], W, "a cota não se repete na segunda leitura")
        self.assertEqual(c2["quotas_granted_now"], [])
        # a MESMA pessoa cria outra organização: não ganha de novo (anti-abuso)
        r = osc.post("/v1/orgs", {"kind": "osc", "legal_name": "Segunda OSC da mesma pessoa", "cnpj": __import__("tests.support", fromlist=["next_cnpj"]).next_cnpj()})
        if r.status == 201:
            self.assertEqual(osc.post("/v1/me/switch-org", {"org_id": r.json["id"]}).status, 200)
            c3r = osc.get("/v1/ai/center")
            self.assertEqual(c3r.status, 200, c3r.json)
            c3 = c3r.json
            self.assertEqual(c3["balances"]["promotional"]["balance"], MONTHLY, "segunda organização da mesma pessoa não recebe boas-vindas (só a mensal leve)")

    def test_preview_shows_cost_funding_and_balance_before_anything_runs(self):
        osc = new_account("osc")
        pid = _projeto(osc)
        r = osc.post("/v1/ai/preview", {"operation_code": "similarity.single", "project_id": pid, "input_chars": 500})
        self.assertEqual(r.status, 200, r.json)
        self.assertTrue(r.json["allowed"])
        self.assertEqual(r.json["credits_required"], 49)
        self.assertEqual(r.json["funding_source"], "promotional")
        self.assertTrue(r.json["operation"]["price_is_hypothesis"])
        self.assertIn("delivers", r.json["operation"])
        self.assertEqual(r.json["cost_status"], "local_no_cost")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM ai_executions WHERE org_id = $1", osc.org_id), 0, "prévia não cria execução")

    def test_a_successful_operation_charges_exactly_the_reserved_credits_and_is_recorded(self):
        osc = new_account("osc")
        pid = _projeto(osc)
        r = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single"})
        self.assertEqual(r.status, 200, r.json)
        ex = r.json["execution"]
        self.assertEqual(ex["state"], "reconciled")
        self.assertEqual(ex["charged_credits"], 49)
        self.assertEqual(ex["funding_source"], "promotional")
        self.assertEqual(_balance(osc.org_id, "promotional"), W - 49)
        with db_system() as d:
            row = d.one("SELECT reason, bucket, execution_id::text AS execution_id, delta FROM ai_credit_ledger WHERE org_id = $1 AND reason = 'consumption'", osc.org_id)
            self.assertEqual((row["bucket"], row["execution_id"], row["delta"]), ("promotional", ex["id"], -49))
            ev = [e["to_state"] for e in d.query("SELECT to_state FROM ai_execution_events WHERE execution_id = $1 ORDER BY id", ex["id"])]
        self.assertEqual(ev, ["authorized", "reserved", "running", "succeeded", "reconciled"])

    def test_without_funding_nothing_runs_and_the_answer_lists_options(self):
        osc = new_account("osc")
        pid = _projeto(osc)
        osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single"})            # 49 dos 70 da cota
        r = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "pair", "compared_project_ids": [_projeto(osc, title="Projeto B")]})
        self.assertEqual(r.status, 402, r.json)
        self.assertEqual(r.json["code"], "ai_funding_required")
        self.assertEqual({o["kind"] for o in r.json["details"]["options"]}, {"buy_credits", "request_sponsorship", "save_draft"})
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM ai_executions WHERE org_id = $1 AND operation_code = 'similarity.pair'", osc.org_id), 0)
            self.assertEqual(d.scalar("SELECT count(*) FROM similarity_analyses WHERE org_id = $1 AND kind = 'pair'", osc.org_id), 0)

    def test_purchased_credits_are_used_after_the_quota_and_the_same_inputs_are_not_charged_twice(self):
        osc = new_account("osc")
        pid = _projeto(osc)
        _grant(osc.org_id, 200)
        r1 = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single"})
        self.assertEqual(r1.json["execution"]["funding_source"], "promotional")
        r2 = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single"})
        self.assertTrue(r2.json["cached"])
        self.assertEqual(r2.json["execution"]["funding_source"], "cached")
        self.assertEqual(r2.json["execution"]["charged_credits"], 0)
        self.assertEqual(_balance(osc.org_id, "purchased"), 200)
        # muda o projeto → entrada nova → cobra (agora do comprado, porque a cota não cobre 49)
        osc.patch(f"/v1/projects/{pid}", {"summary": "Resumo alterado para invalidar o cache."})
        r3 = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single"})
        self.assertFalse(r3.json["cached"])
        self.assertEqual(r3.json["execution"]["funding_source"], "purchased")
        self.assertEqual(_balance(osc.org_id, "purchased"), 151)

    def test_the_same_idempotency_key_returns_the_same_execution_without_a_second_charge(self):
        osc = new_account("osc")
        pid = _projeto(osc)
        key = "idem-" + uuid.uuid4().hex[:12]
        r1 = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single", "idempotency_key": key})
        r2 = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single", "idempotency_key": key})
        self.assertEqual(r1.json["execution"]["id"], r2.json["execution"]["id"])
        self.assertEqual(_balance(osc.org_id, "promotional"), W - 49)

    def test_concurrent_executions_never_spend_more_than_the_balance(self):
        """Saldo 70 (cotas) + 0 comprado; oito análises de 49 em paralelo: no máximo UMA cobra."""
        osc = new_account("osc")
        osc.get("/v1/ai/center")
        pids = [_projeto(osc, title=f"Projeto concorrente {i}") for i in range(8)]
        results = []

        def go(pid):
            results.append(osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single"}).status)

        ts = [threading.Thread(target=go, args=(p,)) for p in pids]
        [t.start() for t in ts]
        [t.join() for t in ts]
        self.assertEqual(results.count(200), 1, results)
        self.assertEqual(results.count(402), 7, results)
        self.assertGreaterEqual(_balance(osc.org_id, "promotional"), 0)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM ai_credit_ledger WHERE org_id = $1 AND reason = 'consumption'", osc.org_id), 1)

    def test_a_failed_execution_charges_nothing(self):
        osc = new_account("osc")
        pid = _projeto(osc, items=())
        other = new_account("company")
        grant_premium(other)
        # sobreposição de despesa exige itens de orçamento: falha de validação ANTES de cobrar
        _grant(osc.org_id, 500)
        r = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "expense_overlap", "compared_project_ids": [_projeto(osc, title="Projeto B sem itens", items=())]})
        self.assertIn(r.status, (403, 422), r.json)
        self.assertEqual(_balance(osc.org_id, "purchased"), 500)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM ai_executions WHERE org_id = $1 AND charged_credits > 0", osc.org_id), 0)

    def test_the_ledger_gate_refuses_a_grant_outside_the_policy_from_an_org_context(self):
        from tests.support import app_tx
        osc = new_account("osc")
        with app_tx(osc) as c, self.assertRaises(Exception) as cm:
            c.scalar("SELECT ai_credit_post($1, 1000, 'grant', 'promotional', 'ai_quota_policy', '1', 'x', 'forjado', NULL, NULL)", osc.org_id)
        self.assertIn("fora da política", str(cm.exception))
        with app_tx(osc) as c, self.assertRaises(Exception) as cm2:
            c.scalar("SELECT ai_credit_post($1, 1000, 'purchase', 'purchased', 'ai_credit_order', 'x', 'y', 'forjado', NULL, NULL)", osc.org_id)
        self.assertIn("privilégio", str(cm2.exception))
        self.assertEqual(_balance(osc.org_id, "purchased"), 0)

    def test_the_existing_assistance_routes_now_go_through_the_usage_layer(self):
        osc = new_account("osc", compliance="approved")
        grant_premium(osc)
        pid = _projeto(osc)
        r = osc.post("/v1/ai/summarize-project", {"project_id": pid})
        self.assertEqual(r.status, 200, r.json)
        # a fonte é a cota — ou um patrocínio aberto a toda OSC criado por outro teste/jornada; ambos passam pela camada
        self.assertIn(r.json["execution"]["funding_source"], ("promotional", "sponsorship"))
        self.assertEqual(r.json["execution"]["charged_credits"], 1)
        self.assertEqual(r.json["execution"]["state"], "reconciled")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT credits_charged FROM ai_usage WHERE org_id = $1 ORDER BY id DESC LIMIT 1", osc.org_id), 1)


class CreditOrdersAndPixTests(unittest.TestCase):

    def test_in_pilot_mode_an_order_has_no_payment_and_can_become_a_promotional_grant_only(self):
        osc = new_account("osc")
        packs = osc.get("/v1/ai/credit-packs").json
        self.assertEqual(packs["sale"]["mode"], "pilot")
        self.assertIn("ai.credits_prepaid", packs["sale"]["why_pilot"])
        r = osc.post("/v1/ai/credit-orders", {"pack_code": "pack.100", "accept_terms": True})
        self.assertEqual(r.status, 201, r.json)
        self.assertEqual((r.json["mode"], r.json["state"]), ("pilot", "created"))
        self.assertIsNone(r.json["charge_id"])
        self.assertEqual(r.json["pix"]["status"], "NÃO CONFIGURADA")
        adm, _ = make_admin()
        # conciliação manual (pagamento) é recusada para pedido piloto
        self.assertEqual(adm.post(f"/v1/admin/ai/credit-orders/{r.json['id']}/confirm", {"reference": "E2E-123456", "note": "teste"}).status, 422)
        ok = adm.post(f"/v1/admin/ai/credit-orders/{r.json['id']}/approve-pilot", {"note": "piloto de medição"})
        self.assertEqual(ok.status, 200, ok.json)
        self.assertEqual((ok.json["state"], ok.json["confirmed_via"]), ("credited", "pilot_grant"))
        self.assertEqual(_balance(osc.org_id, "purchased"), 0, "piloto nunca vira compra")
        self.assertEqual(_balance(osc.org_id, "promotional"), 100)
        # aprovar de novo não duplica
        self.assertEqual(adm.post(f"/v1/admin/ai/credit-orders/{r.json['id']}/approve-pilot", {"note": "de novo"}).status, 422)
        self.assertEqual(_balance(osc.org_id, "promotional"), 100)

    def test_terms_must_be_accepted_and_only_one_open_order_per_org(self):
        osc = new_account("osc")
        self.assertEqual(osc.post("/v1/ai/credit-orders", {"pack_code": "pack.100", "accept_terms": False}).status, 422)
        self.assertEqual(osc.post("/v1/ai/credit-orders", {"pack_code": "pack.100", "accept_terms": True}).status, 201)
        self.assertEqual(osc.post("/v1/ai/credit-orders", {"pack_code": "pack.500", "accept_terms": True}).status, 409)

    def test_webhook_without_secret_is_refused_and_nothing_is_credited(self):
        self.assertFalse(os.environ.get("PAYMENT_WEBHOOK_SECRET"))
        r = Client().post("/v1/webhooks/payments/pix", {"event_id": "e1", "type": "charge.paid"})
        self.assertEqual(r.status, 404, r.json)
        self.assertEqual(r.json["code"], "webhook_not_configured")

    def test_a_real_order_is_refused_by_the_database_without_an_active_rule(self):
        """Mesmo que o código tentasse abrir cobrança real, o gatilho recusa: sem regra ativa não há venda."""
        osc = new_account("osc")
        with db_system() as d:
            oid = d.scalar("INSERT INTO ai_credit_orders(org_id, pack_id, credits, amount_cents, mode) SELECT $1, id, credits, price_cents, 'real'"
                           " FROM ai_credit_packs WHERE code = 'pack.100' RETURNING id::text", osc.org_id)
            with self.assertRaises(Exception) as cm:
                d.run("INSERT INTO platform_charges(org_id, kind, method, amount_cents, currency, provider, idempotency_key, expires_at)"
                      " VALUES ($1,'ai_credits','pix',1000,'BRL','stripe',$2, now() + interval '2 days')", osc.org_id, f"ai_credit_order:{oid}")
            self.assertIn("sem autorização vigente", str(cm.exception))

    def test_a_real_order_can_only_be_credited_with_a_reference_and_never_from_a_simulated_charge(self):
        osc = new_account("osc")
        with db_system() as d:
            oid = d.scalar("INSERT INTO ai_credit_orders(org_id, pack_id, credits, amount_cents, mode, state) SELECT $1, id, credits, price_cents, 'real', 'awaiting_payment'"
                           " FROM ai_credit_packs WHERE code = 'pack.100' RETURNING id::text", osc.org_id)
        # creditar sem referência nem lançamento: o gatilho do pedido recusa
        with self.assertRaises(Exception) as cm, db_system() as d:
            d.run("UPDATE ai_credit_orders SET state = 'paid' WHERE id = $1", oid)
            d.run("UPDATE ai_credit_orders SET state = 'credited', confirmed_via = 'manual_reconciliation', paid_reference = 'X' WHERE id = $1", oid)
        self.assertIn("lançamento no razão", str(cm.exception))
        with db_system() as d:
            # cobrança SIMULADA associada: a conciliação manual recusa creditar compra
            ch = d.scalar("INSERT INTO platform_charges(org_id, kind, method, amount_cents, currency, provider, expires_at) VALUES ($1,'ai_credits','pix',1000,'BRL','manual', now() + interval '2 days') RETURNING id::text", osc.org_id)
            d.run("UPDATE ai_credit_orders SET charge_id = $2 WHERE id = $1", oid, ch)
        adm, _ = make_admin()
        r = adm.post(f"/v1/admin/ai/credit-orders/{oid}/confirm", {"reference": "EXTRATO-000001", "note": "tentativa"})
        self.assertEqual(r.status, 409, r.json)
        self.assertEqual(r.json["code"], "simulated_charge")
        self.assertEqual(_balance(osc.org_id, "purchased"), 0)


class WebhookWithSecretTests(unittest.TestCase):
    """Liga PAYMENT_WEBHOOK_SECRET no servidor de teste (o mesmo processo) para provar assinatura, reentrega e crédito único."""

    def setUp(self):
        from tests.support import server
        self.secret = "segredo-de-webhook-de-teste-" + uuid.uuid4().hex[:8]
        self.settings = server()["state"].settings
        self._old = self.settings.payment_webhook_secret
        self.settings.payment_webhook_secret = self.secret

    def tearDown(self):
        self.settings.payment_webhook_secret = self._old

    def _post(self, body: dict, sig: str | None = None):
        raw = json.dumps(body).encode()
        # v0.35.0 (auditoria, PAY-01): assinatura com carimbo de tempo (t=…,v1=…), janela de 300 s
        s = sig if sig is not None else sign(self.secret, raw)[0]
        return Client().request("POST", "/v1/webhooks/payments/pix", raw=raw, headers={"x-impacto-signature": s, "content-type": "application/json"})

    def test_signature_duplicates_and_single_credit(self):
        from tests.support import owner_conn
        osc = new_account("osc")
        own = owner_conn()
        # cobrança REAL exige regra ativa; cartas são append-only, então registra-se uma carta de TESTE verde e volta-se ao fim
        original = own.one("SELECT legal_card_id::text AS legal_card_id, legal_status FROM monetization_rules WHERE key = 'ai.credits_prepaid'")
        card = own.scalar(
            "INSERT INTO monetization_legal_cards(rule_key, payer, beneficiary, billing_event, revenue_nature, contractual_relation,"
            " legal_basis, source_name, source_url, verified_on, certainty, needs_lawyer, needs_accountant, status, note)"
            " VALUES ('ai.credits_prepaid', 'Organização compradora', 'Plataforma Impacto', 'pagamento confirmado de pedido de créditos',"
            " 'prestação de serviço de software sob demanda', 'termos de crédito aceitos no pedido',"
            " 'Base de TESTE registrada só para exercitar o portão; não é parecer.', 'Registro interno de teste', 'https://exemplo.test/base',"
            " current_date, 'high', false, false, 'green', 'carta de teste — ambiente de teste') RETURNING id::text")
        # preço por crédito de TESTE (10 centavos) só para passar pelo portão "sem preço não cobra"; volta a nulo ao fim
        own.run("UPDATE monetization_rules SET legal_status = 'validated', legal_card_id = $1, active = true, amount_cents = 10 WHERE key = 'ai.credits_prepaid'", card)
        with db_system() as d:
            oid = d.scalar("INSERT INTO ai_credit_orders(org_id, pack_id, credits, amount_cents, mode, state) SELECT $1, id, credits, price_cents, 'real', 'awaiting_payment'"
                           " FROM ai_credit_packs WHERE code = 'pack.100' RETURNING id::text", osc.org_id)
            ch = d.scalar("INSERT INTO platform_charges(org_id, kind, method, amount_cents, currency, provider, idempotency_key, expires_at)"
                          " VALUES ($1,'ai_credits','pix',1000,'BRL','stripe',$2, now() + interval '2 days') RETURNING id::text", osc.org_id, f"ai_credit_order:{oid}")
            d.run("UPDATE platform_charges SET state='checkout_started' WHERE id=$1", ch)
            d.run("UPDATE platform_charges SET state='pending' WHERE id=$1", ch)
            d.run("UPDATE ai_credit_orders SET charge_id = $2 WHERE id = $1", oid, ch)
        try:
            bad = self._post({"event_id": "evt-bad", "type": "charge.paid", "charge_id": ch, "amount_cents": 1000}, sig="deadbeef")
            self.assertEqual(bad.status, 202, bad.json)
            self.assertEqual(bad.json["status"], "rejected_signature")
            self.assertEqual(_balance(osc.org_id, "purchased"), 0, "assinatura inválida não credita")
            wrong_amount = self._post({"event_id": "evt-amt", "type": "charge.paid", "charge_id": ch, "amount_cents": 999})
            self.assertFalse(wrong_amount.json["credited"])
            ok = self._post({"event_id": "evt-ok", "type": "charge.paid", "charge_id": ch, "amount_cents": 1000})
            self.assertEqual(ok.status, 200, ok.json)
            self.assertTrue(ok.json["credited"])
            self.assertEqual(_balance(osc.org_id, "purchased"), 100)
            again = self._post({"event_id": "evt-ok", "type": "charge.paid", "charge_id": ch, "amount_cents": 1000})
            self.assertEqual(again.json["status"], "duplicate")
            self.assertEqual(_balance(osc.org_id, "purchased"), 100, "reentrega não duplica crédito")
            with db_system() as d:
                self.assertEqual(d.scalar("SELECT state FROM ai_credit_orders WHERE id = $1", oid), "credited")
                self.assertEqual(d.scalar("SELECT state FROM platform_charges WHERE id = $1", ch), "paid")
                self.assertEqual(d.scalar("SELECT duplicate_count FROM billing_events WHERE provider='pix' AND event_id='evt-ok'"), 1)
                # v0.35.0 (auditoria, PAY-01): o evento SEM assinatura válida fica guardado sob identificador próprio (`unverified:`),
                # nunca sob o `event_id` que alega — senão ocuparia o lugar do evento verdadeiro. Procura-se pelo id alegado no corpo.
                self.assertEqual(d.scalar("SELECT status FROM billing_events WHERE provider='pix' AND payload->>'event_id' = 'evt-bad'"
                                          " AND NOT signature_verified"), "rejected_signature")
                self.assertIsNone(d.scalar("SELECT 1 FROM billing_events WHERE provider='pix' AND event_id='evt-bad'"))
        finally:
            own.run("UPDATE monetization_rules SET active = false, legal_status = $1, legal_card_id = $2::uuid, amount_cents = NULL WHERE key = 'ai.credits_prepaid'",
                    original["legal_status"], original["legal_card_id"])
            own.close()


class SponsorshipTests(unittest.TestCase):

    def test_a_sponsor_commits_its_own_credits_and_an_eligible_osc_is_funded_until_the_budget_ends(self):
        funder, osc = new_account("company"), new_account("osc")
        _grant(funder.org_id, 300)
        r = funder.post("/v1/ai/sponsorships", {"name": "Diagnóstico para OSCs de MT", "budget_credits": 120, "ends_on": "2027-12-31",
                                                 "eligible_kinds": ["osc"], "operations": ["similarity.single", "similarity.pair"],
                                                 "accountability": "Relatório agregado mensal de operações custeadas."})
        self.assertEqual(r.status, 201, r.json)
        sid = r.json["id"]
        self.assertEqual(_balance(funder.org_id, "purchased"), 180, "o patrocínio compromete créditos do patrocinador")
        pid = _projeto(osc)
        pv = osc.post("/v1/ai/preview", {"operation_code": "similarity.single", "project_id": pid}).json
        self.assertEqual(pv["funding_source"], "sponsorship")
        self.assertIn("custeada pela iniciativa patrocinadora", pv["message"])
        e1 = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single"}).json["execution"]
        self.assertEqual((e1["funding_source"], e1["charged_credits"]), ("sponsorship", 49))
        self.assertEqual(_balance(osc.org_id, "promotional"), W, "o beneficiário não gastou a própria cota")
        pid2 = _projeto(osc, title="Outro projeto")
        e2 = osc.post(f"/v1/projects/{pid2}/similarity", {"kind": "single"}).json["execution"]
        self.assertEqual(e2["funding_source"], "sponsorship")
        # restam 22 no patrocínio: a próxima NÃO migra em silêncio para a cota pessoal — a prévia diz quem paga
        pid3 = _projeto(osc, title="Terceiro projeto")
        pv3 = osc.post("/v1/ai/preview", {"operation_code": "similarity.single", "project_id": pid3}).json
        self.assertEqual(pv3["funding_source"], "promotional")
        self.assertNotIn("sponsorship", pv3)
        rep = funder.get(f"/v1/ai/sponsorships/{sid}").json
        self.assertEqual((rep["used"], rep["remaining"]), (98, 22))
        self.assertEqual(sum(x["credits"] for x in rep["by_operation"]), 98)
        self.assertNotIn("result", json.dumps(rep), "prestação de contas é agregada: sem conteúdo")
        self.assertEqual(osc.get(f"/v1/ai/sponsorships/{sid}").status, 404, "o beneficiário não lê o relatório do patrocinador")
        close = funder.post(f"/v1/ai/sponsorships/{sid}/close").json
        self.assertEqual(close["status"], "closed")
        self.assertEqual(_balance(funder.org_id, "purchased"), 180 + 22, "o não usado volta ao patrocinador")

    def test_a_sponsorship_above_the_sponsors_balance_is_refused(self):
        funder = new_account("company")
        r = funder.post("/v1/ai/sponsorships", {"name": "Sem lastro", "budget_credits": 5000, "ends_on": "2027-12-31", "accountability": "Relatório agregado."})
        self.assertEqual(r.status, 402, r.json)


class AdminFinanceTests(unittest.TestCase):

    def test_the_finance_panel_requires_finance_read_and_says_what_is_not_measured(self):
        self.assertEqual(new_account("osc").get("/v1/admin/ai/finance").status, 403)
        self.assertEqual(make_staff("support").get("/v1/admin/ai/finance").status, 403)
        adm, _ = make_admin()
        r = adm.get("/v1/admin/ai/finance")
        self.assertEqual(r.status, 200, r.json)
        self.assertIsNone(r.json["costs"]["infra_cents"])
        self.assertEqual(r.json["sale"]["mode"], "pilot")
        self.assertIn("NÃO MEDIDO", r.json["contribution_margin"]["status"] + " " + r.json["honesty"][0])

    def test_the_admin_can_publish_a_new_operation_version_and_old_executions_keep_theirs(self):
        osc = new_account("osc")
        pid = _projeto(osc)
        e1 = osc.post(f"/v1/projects/{pid}/similarity", {"kind": "single"}).json["execution"]
        adm, _ = make_admin()
        cat = next(o for o in adm.get("/v1/ai/operations").json["items"] if o["code"] == "similarity.single")
        body = {k: cat[k] for k in ("code", "name_pt", "description_pt", "purpose_pt", "category", "tier", "allowed_kinds", "min_role",
                                    "data_requirements_pt", "provider_mode", "funding_modes", "credits_per_unit", "unit_label_pt", "max_units",
                                    "max_input_chars", "free_quota_eligible", "sponsor_eligible", "completion_rule_pt", "delivers_pt", "status")}
        body |= {"credits_base": 10, "note": "Versão 2: preço de teste reduzido para medir elasticidade no piloto."}
        r = adm.post("/v1/admin/ai/operations", body)
        self.assertEqual(r.status, 201, r.json)
        self.assertEqual(r.json["version"], 2)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT operation_version FROM ai_executions WHERE id = $1", e1["id"]), 1)
            self.assertEqual(d.scalar("SELECT estimated_credits FROM ai_executions WHERE id = $1", e1["id"]), 49)
        pv = new_account("osc").post("/v1/ai/preview", {"operation_code": "similarity.single"}).json
        self.assertEqual((pv["credits_required"], pv["operation"]["version"]), (10, 2))
        # restaura a versão 1 como vigente publicando uma v3 idêntica a ela (o catálogo é append-only)
        body |= {"credits_base": 49, "note": "Versão 3: volta ao preço de teste original após o experimento."}
        self.assertEqual(adm.post("/v1/admin/ai/operations", body).status, 201)
