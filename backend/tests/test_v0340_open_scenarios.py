"""v0.34.0 (E6) — os cenários da PARTE XIV que a primeira rodada deixou parciais ou descobertos.

Tudo roda contra o provedor SANDBOX. Onde o cenário depende de capacidade que o sandbox não tem (falha temporária,
split), o teste injeta a condição só aqui (mock restrito a teste) e o nome do teste diz isso — nenhuma linha de produção
finge que um provedor real existe.

* 2  cartão confirmado · 8 falha temporária do provedor · 14 split bem-sucedido (simulado) · 15 split indisponível
* 17 falha de liquidação · 18 liquidação/transferência parcial · 25 doação recorrente · 33 falha no processamento
* 35 reprocessamento · 38 cancelamento de recorrência (assinatura não existe: ADR-341) · 39 reembolso do que a
  plataforma recebeu, com a fatura protegida contra a própria organização
"""
import hashlib
import hmac
import json
import unittest
import uuid

from tests.support import Client, db_system, make_staff, new_account, reauth, server

SECRET = "segredo-webhook-de-teste-nao-e-segredo-real"
CONSENT = "Autorizo a cobrança mensal deste valor no meu cartão até eu cancelar, o que posso fazer a qualquer momento."
_CARDS: dict[str, str] = {}


def _signed(client: Client, body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.request("POST", "/v1/webhooks/donations/sandbox", raw=raw, ctype="application/json", headers={"X-Impacto-Signature": sig})


def _rule(key: str, active: bool) -> None:
    """Liga/desliga uma regra passando pelo MESMO portão do banco (carta verde de teste, só no banco de teste)."""
    with db_system() as c:
        if active:
            _CARDS[key] = c.scalar("SELECT legal_card_id::text FROM monetization_rules WHERE key = $1", key)
            green = c.scalar(
                "INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature, contractual_relation,"
                " required_document, required_terms, cancellation_policy, refund_policy, tax_notes, invoice_notes, regulatory_notes, legal_basis, source_name,"
                " source_url, verified_on, open_questions, needs_lawyer, note)"
                " SELECT rule_key, 'green', 'high', payer, beneficiary, billing_event, revenue_nature, contractual_relation, required_document, required_terms,"
                " cancellation_policy, refund_policy, tax_notes, invoice_notes, regulatory_notes, legal_basis, source_name, source_url, current_date, NULL, false,"
                " 'CARTA DE TESTE: simula a revisão jurídica concluída; existe só no banco de teste' FROM monetization_legal_cards WHERE id = $1::uuid RETURNING id::text",
                _CARDS[key])
            c.run("UPDATE monetization_rules SET legal_card_id = $2::uuid, legal_status = 'validated', active = true WHERE key = $1", key, green)
        else:
            c.run("UPDATE monetization_rules SET active = false, legal_status = 'review_required', legal_card_id = $2::uuid WHERE key = $1", key, _CARDS[key])


def _publish(osc: Client, reviewer: Client, **extra) -> tuple[str, str]:
    slug = "e6-" + uuid.uuid4().hex[:8]
    r = osc.post("/v1/campaigns", {"slug": slug, "title": "Campanha dos cenários abertos", "kind": "organization",
                                   "summary": "Arrecadação para fechar os cenários que dependiam do provedor.",
                                   "target_cents": 1_000_000, "purpose": "Testes.", "contingency_policy": "Sem a meta, segue.",
                                   "refund_policy": "Estorno pelo provedor.", **extra})
    assert r.status == 201, r
    cid = r.json["id"]
    assert osc.post(f"/v1/campaigns/{cid}/submit").status == 200
    assert reviewer.post(f"/v1/admin/donation-campaigns/{cid}/review", {"approve": True, "note": "Revisão de teste: finalidade clara."}).status == 200
    reviewer.post(f"/v1/admin/beneficiaries/{osc.org_id}/verification", {"status": "verified", "note": "Cadastro conferido no teste.", "account_holder_matches": True})
    assert osc.post(f"/v1/campaigns/{cid}/publish").status == 200
    return cid, slug


def _charge_of(donation_id: str) -> str:
    with db_system() as c:
        return c.scalar("SELECT provider_charge_id FROM donations WHERE id = $1", donation_id)


def _balanced(donation_id: str) -> bool:
    with db_system() as c:
        rows = c.query("SELECT txn_id, sum(CASE WHEN side = 'D' THEN amount_cents ELSE -amount_cents END) AS diff"
                       " FROM donation_ledger_entries WHERE donation_id = $1 GROUP BY txn_id", donation_id)
    return bool(rows) and all(int(r["diff"]) == 0 for r in rows)


class OpenScenariosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.state = st["state"]
        cls.state.settings.payment_webhook_secret = SECRET
        cls.osc = new_account("osc", compliance="approved")
        cls.donor = new_account("individual")
        cls.reviewer = make_staff("compliance")
        cls.finance = make_staff("finance")
        cls.controller = make_staff("controller")
        reauth(cls.finance)
        reauth(cls.controller)
        cls.anon = Client()
        cls.campaign, cls.slug = _publish(cls.osc, cls.reviewer, allow_recurring=True)

    def _donate(self, cents: int, **body) -> dict:
        r = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate",
                           {"amount_cents": cents, "method": "pix", "idempotency_key": "k-" + uuid.uuid4().hex[:8], **body})
        self.assertEqual(r.status, 201, r.body)
        return r.json

    def _confirm(self, d: dict, **extra) -> dict:
        r = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.confirmed", "charge_id": _charge_of(d["id"]),
                                "amount_cents": d["total_to_pay_cents"], "currency": "BRL", **extra})
        self.assertEqual(r.status, 200, r.body)
        return r.json

    # ------------------------------------------------------------------------------------------------ 2
    def test_02_card_payment_is_confirmed_by_the_same_signed_event(self):
        d = self._donate(4_000, method="card")
        self.assertEqual(d["method"], "card")
        self.assertIsNone(d["pix_payload"], "cartão não gera Pix")
        self.assertTrue(d["checkout_url"].startswith("/doar/checkout-sandbox/"))
        self.assertEqual(self._confirm(d)["effect"], "confirmed")
        got = self.anon.get(f"/v1/public/donations/{d['id']}").json
        self.assertEqual((got["status"], got["method"]), ("confirmed", "card"))
        self.assertIsNotNone(got["receipt"])

    # ------------------------------------------------------------------------------------------------ 8
    def test_08_provider_temporary_failure_records_nothing_and_the_same_key_can_retry(self):
        from impacto.services import donations as DON
        original = DON.SandboxProvider.create_charge
        calls = {"n": 0}

        def flaky(self_, **kw):   # mock RESTRITO A TESTE: o sandbox de verdade não falha
            calls["n"] += 1
            if calls["n"] == 1:
                raise DON.ProviderUnavailable("timeout simulado no teste")
            return original(self_, **kw)

        key = "retry-" + uuid.uuid4().hex[:8]
        DON.SandboxProvider.create_charge = flaky
        try:
            first = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 2_500, "method": "pix", "idempotency_key": key})
            self.assertEqual(first.status, 503, first.body)
            self.assertEqual(first.json["code"], "provider_unavailable")
            with db_system() as c:
                self.assertEqual(c.scalar("SELECT count(*) FROM donations WHERE idempotency_key = $1", key), 0, "nada gravado na falha")
            again = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 2_500, "method": "pix", "idempotency_key": key})
            self.assertEqual(again.status, 201, again.body)
            self.assertEqual(again.json["status"], "awaiting_payment")
        finally:
            DON.SandboxProvider.create_charge = original

    # ------------------------------------------------------------------------------------------------ 33 e 35
    def test_33_35_an_event_that_fails_to_apply_is_kept_failed_and_is_reprocessed(self):
        from impacto.services import donations as DON
        d = self._donate(6_000)
        ev = {"event_id": "evt-fail-" + uuid.uuid4().hex[:8], "type": "payment.confirmed", "charge_id": _charge_of(d["id"]),
              "amount_cents": 6_000, "currency": "BRL"}
        original = DON._post_confirmation

        def boom(*a, **kw):   # mock RESTRITO A TESTE: erro interno no meio da aplicação
            raise RuntimeError("falha interna simulada")

        DON._post_confirmation = boom
        try:
            r = _signed(self.anon, ev)
        finally:
            DON._post_confirmation = original
        self.assertEqual(r.status, 500, r.body)
        self.assertEqual(r.json["status"], "failed")
        with db_system() as c:
            row = c.one("SELECT processing_status FROM payment_provider_events WHERE event_id = $1", ev["event_id"])
            self.assertEqual(row["processing_status"], "failed", "evento aceito nunca se perde")
            self.assertEqual(c.scalar("SELECT count(*) FROM donation_ledger_entries WHERE donation_id = $1", d["id"]), 0, "nada lançado pela metade")
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", d["id"]), "awaiting_payment")
            self.assertEqual(c.scalar("SELECT count(*) FROM reconciliation_exceptions WHERE kind = 'event_processing_failed' AND provider_ref = $1"
                                      " AND status = 'open'", ev["event_id"]), 1, "a falha entra na fila de exceções")
            out = DON.reprocess_pending_events(c, older_than_seconds=0)
            self.assertGreaterEqual(out["reprocessed"], 1)
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", d["id"]), "confirmed")
            self.assertEqual(c.scalar("SELECT processing_status FROM payment_provider_events WHERE event_id = $1", ev["event_id"]), "applied")
            self.assertEqual(c.scalar("SELECT status FROM reconciliation_exceptions WHERE kind = 'event_processing_failed' AND provider_ref = $1",
                                      ev["event_id"]), "resolved")
        # o provedor reenvia o mesmo evento depois: nada acontece de novo
        again = _signed(self.anon, ev)
        self.assertEqual(again.json["status"], "duplicate")
        self.assertTrue(_balanced(d["id"]))
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(DISTINCT txn_id) FROM donation_ledger_entries WHERE donation_id = $1", d["id"]), 1)

    def test_33b_a_redelivery_of_a_failed_event_applies_it(self):
        from impacto.services import donations as DON
        d = self._donate(3_300)
        ev = {"event_id": "evt-redeliver-" + uuid.uuid4().hex[:8], "type": "payment.confirmed", "charge_id": _charge_of(d["id"]),
              "amount_cents": 3_300, "currency": "BRL"}
        original = DON._post_confirmation
        DON._post_confirmation = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("falha simulada"))
        try:
            self.assertEqual(_signed(self.anon, ev).status, 500)
        finally:
            DON._post_confirmation = original
        r = _signed(self.anon, ev)   # at-least-once: o provedor reenvia
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(r.json["effect"], "confirmed")

    # ------------------------------------------------------------------------------------------------ 17 e 18
    def test_17_18_settlement_failure_and_partial_settlement_are_separate_states_with_exceptions(self):
        d = self._donate(10_000)
        self.assertEqual(self._confirm(d)["effect"], "confirmed")
        charge = _charge_of(d["id"])
        fail = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.settlement_failed", "charge_id": charge,
                                   "reason": "conta de destino recusou"})
        self.assertEqual(fail.json["effect"], "settlement_failed")
        with db_system() as c:
            self.assertIsNone(c.scalar("SELECT settled_at FROM donations WHERE id = $1", d["id"]), "falha não é liquidação")
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", d["id"]), "confirmed", "o pagamento continua confirmado")
            self.assertEqual(c.scalar("SELECT count(*) FROM reconciliation_exceptions WHERE kind = 'settlement_failed' AND donation_id = $1", d["id"]), 1)
        before = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        part = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.settled", "charge_id": charge, "settled_cents": 4_000})
        self.assertEqual(part.json["effect"], "settled_partial")
        t = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        self.assertEqual(t["settled_cents"], before["settled_cents"], "parcial não entra como liquidado")
        self.assertEqual(t["settled_partial_cents"] - before["settled_partial_cents"], 4_000)
        with db_system() as c:
            exc = c.one("SELECT expected_cents, observed_cents FROM reconciliation_exceptions WHERE kind = 'settlement_partial' AND donation_id = $1", d["id"])
        self.assertEqual((exc["expected_cents"], exc["observed_cents"]), (10_000, 4_000))
        rest = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.settled", "charge_id": charge, "settled_cents": 6_000})
        self.assertEqual(rest.json["effect"], "settled")
        t = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        self.assertEqual(t["settled_cents"] - before["settled_cents"], 10_000)
        self.assertEqual(t["settled_partial_cents"], before["settled_partial_cents"])

    # ------------------------------------------------------------------------------------------------ 14 e 15
    def test_14_15_donor_contribution_split_simulated_and_without_split_it_is_billed(self):
        from impacto.services import donations as DON
        bad = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate",
                             {"amount_cents": 5_000, "method": "pix", "platform_contribution_cents": 500, "idempotency_key": "c-" + uuid.uuid4().hex[:6]})
        self.assertEqual(bad.status, 422, "regra inativa: o campo não existe para o doador")
        self.assertEqual(bad.json["code"], "contribution_unavailable")
        self.assertFalse(self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["costs_disclosure"]["platform_contribution"]["available"])
        _rule("donation.platform_contribution", True)
        try:
            disc = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["costs_disclosure"]["platform_contribution"]
            self.assertEqual((disc["available"], disc["default_cents"]), (True, 0), "começa em zero, nunca sugerida")
            over = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate",
                                  {"amount_cents": 1_000, "method": "pix", "platform_contribution_cents": 1_500, "idempotency_key": "c-" + uuid.uuid4().hex[:6]})
            self.assertEqual(over.json["code"], "contribution_above_cap", "não pode passar do valor doado")
            # 15 — split indisponível (sandbox não divide): a contribuição vira obrigação DEVIDA da organização, nunca desconto
            before = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]["gross_confirmed_cents"]
            d = self._donate(5_000, platform_contribution_cents=500)
            self.assertEqual(d["total_to_pay_cents"], 5_500, "a contribuição é A MAIS, separada no total")
            self.assertEqual(d["split_platform_cents"], 0)
            self.assertEqual(self._confirm(d)["effect"], "confirmed")
            after = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]["gross_confirmed_cents"]
            self.assertEqual(after - before, 5_000, "a arrecadação da campanha não inclui a contribuição")
            with db_system() as c:
                o = c.one("SELECT state, trigger_code, amount_cents FROM remuneration_obligations WHERE source_id = $1 AND rule_key = 'donation.platform_contribution'", d["id"])
            self.assertEqual((o["state"], o["trigger_code"], o["amount_cents"]), ("due", "donor_opt_in_contribution", 500))
            self.assertTrue(_balanced(d["id"]))
            # fecha o ciclo desta obrigação: dispensa com motivo registrado (segregado, finance.approve)
            with db_system() as c:
                due_id = c.scalar("SELECT id::text FROM remuneration_obligations WHERE source_id = $1 AND rule_key = 'donation.platform_contribution'", d["id"])
            w = self.controller.post(f"/v1/admin/remuneration/{due_id}/waive", {"reason": "Contribuição de teste abaixo do mínimo de fatura: dispensada."})
            self.assertEqual(w.status, 200, w.body)
            self.assertEqual(w.json["state"], "waived")
            # 14 — split SIMULADO: trava ligada só neste teste e um provedor que divide (mock restrito a teste)
            self.state.settings.split_enabled = True
            DON.SandboxProvider.supports_split = True
            try:
                s = self._donate(8_000, platform_contribution_cents=800)
                self.assertEqual(s["split_platform_cents"], 800)
                ev = self._confirm(s, split=[{"receiver": "platform", "amount_cents": 800, "status": "done"}])
                self.assertEqual(ev["effect"], "confirmed")
            finally:
                self.state.settings.split_enabled = False
                DON.SandboxProvider.supports_split = False
            with db_system() as c:
                o = c.one("SELECT state, received_cents, received_reference FROM remuneration_obligations WHERE source_id = $1"
                          " AND rule_key = 'donation.platform_contribution'", s["id"])
            self.assertEqual((o["state"], o["received_cents"]), ("received", 800))
            self.assertTrue(o["received_reference"].startswith("split:"))
            self.assertTrue(_balanced(s["id"]))
            # liquidação ao beneficiário desconta a parte dividida: 8.800 − 800 = 8.000
            r = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.settled", "charge_id": _charge_of(s["id"]), "settled_cents": 8_000})
            self.assertEqual(r.json["effect"], "settled")
            # estorno da doação estorna a contribuição: a obrigação recebida vai para disputa, nunca some
            back = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.refunded", "charge_id": _charge_of(s["id"])})
            self.assertEqual(back.json["effect"], "refunded")
            self.assertTrue(_balanced(s["id"]))
            with db_system() as c:
                self.assertEqual(c.scalar("SELECT state FROM remuneration_obligations WHERE source_id = $1 AND rule_key = 'donation.platform_contribution'", s["id"]), "disputed")
        finally:
            _rule("donation.platform_contribution", False)

    # ------------------------------------------------------------------------------------------------ 25 e 38
    def test_25_38_recurring_authorization_attempts_failures_pause_and_cancellation(self):
        from impacto.services import donations as DON
        off = self.donor.post(f"/v1/public/donation-campaigns/{self.slug}/recurring", {"amount_cents": 3_000, "consent_text": CONSENT})
        self.assertEqual(off.status, 503, "recorrência desligada por padrão")
        self.assertEqual(off.json["code"], "recurring_disabled")
        self.state.settings.recurring_donations_enabled = True   # só neste teste (a configuração recusa ligar em produção)
        try:
            self.assertEqual(self.donor.post(f"/v1/public/donation-campaigns/{self.slug}/recurring",
                                             {"amount_cents": 3_000, "consent_text": "curto"}).status, 422)
            a = self.donor.post(f"/v1/public/donation-campaigns/{self.slug}/recurring", {"amount_cents": 3_000, "consent_text": CONSENT})
            self.assertEqual(a.status, 201, a.body)
            ag = a.json
            self.assertEqual((ag["status"], ag["attempts"], ag["confirmed_n"], ag["received_cents"]), ("active", 0, 0, 0), "autorizar não é pagar")
            with db_system() as c:
                first = DON.run_recurring_cycle(c, settings=self.state.settings, cipher=self.state.cipher)
                self.assertGreaterEqual(first["attempts_created"], 1)
                again = DON.run_recurring_cycle(c, settings=self.state.settings, cipher=self.state.cipher)
                self.assertEqual(c.scalar("SELECT count(*) FROM donations WHERE recurring_agreement_id = $1", ag["id"]), 1, "um ciclo, uma tentativa")
                self.assertIsInstance(again, dict)
                att = c.one("SELECT id::text AS id, status, provider_charge_id FROM donations WHERE recurring_agreement_id = $1", ag["id"])
            self.assertEqual(att["status"], "awaiting_payment", "tentativa não é pagamento")
            r = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.confirmed", "charge_id": att["provider_charge_id"],
                                    "amount_cents": 3_000, "currency": "BRL"})
            self.assertEqual(r.json["effect"], "confirmed")
            view = next(x for x in self.donor.get("/v1/me/donations").json["recurring"] if x["id"] == ag["id"])
            self.assertEqual((view["attempts"], view["confirmed_n"], view["received_cents"]), (1, 1, 3_000))
            # três ciclos seguidos falham (cobrança expira) → pausa; pausado não gera tentativa
            for _ in range(3):
                with db_system() as c:
                    c.run("UPDATE recurring_donation_agreements SET next_charge_on = current_date WHERE id = $1", ag["id"])
                    DON.run_recurring_cycle(c, settings=self.state.settings, cipher=self.state.cipher)
                    pend = c.scalar("SELECT provider_charge_id FROM donations WHERE recurring_agreement_id = $1 AND status = 'awaiting_payment'"
                                    " ORDER BY created_at DESC LIMIT 1", ag["id"])
                self.assertEqual(_signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.expired", "charge_id": pend}).json["effect"], "expired")
            view = next(x for x in self.donor.get("/v1/me/donations").json["recurring"] if x["id"] == ag["id"])
            self.assertEqual((view["status"], view["failed_n"], view["received_cents"]), ("paused", 3, 3_000), "falha não vira dinheiro")
            with db_system() as c:
                c.run("UPDATE recurring_donation_agreements SET next_charge_on = current_date WHERE id = $1", ag["id"])
                n = c.scalar("SELECT count(*) FROM donations WHERE recurring_agreement_id = $1", ag["id"])
                DON.run_recurring_cycle(c, settings=self.state.settings, cipher=self.state.cipher)
                self.assertEqual(c.scalar("SELECT count(*) FROM donations WHERE recurring_agreement_id = $1", ag["id"]), n, "pausado não cobra")
            # 38 — cancelamento pelo doador, sempre possível; cancelado não gera tentativa
            b = self.donor.post(f"/v1/public/donation-campaigns/{self.slug}/recurring", {"amount_cents": 2_000, "consent_text": CONSENT}).json
            self.assertEqual(self.donor.post(f"/v1/me/recurring-donations/{b['id']}/cancel").json["status"], "cancelled")
            with db_system() as c:
                DON.run_recurring_cycle(c, settings=self.state.settings, cipher=self.state.cipher)
                self.assertEqual(c.scalar("SELECT count(*) FROM donations WHERE recurring_agreement_id = $1", b["id"]), 0, "cancelado não cobra")
            other = new_account("individual")
            self.assertEqual(other.post(f"/v1/me/recurring-donations/{ag['id']}/cancel").status, 404, "ninguém cancela o acordo de outra pessoa")
        finally:
            self.state.settings.recurring_donations_enabled = False

    # ------------------------------------------------------------------------------------------------ 39
    def test_39_refund_of_what_the_platform_received_reverses_the_obligation_and_the_org_cannot_touch_the_invoice(self):
        _rule("donation.platform_contribution", True)
        try:
            d = self._donate(6_000, platform_contribution_cents=2_500)
            self._confirm(d)
        finally:
            _rule("donation.platform_contribution", False)
        with db_system() as c:
            oid = c.scalar("SELECT id::text FROM remuneration_obligations WHERE source_id = $1 AND rule_key = 'donation.platform_contribution'", d["id"])
        inv = self.finance.post("/v1/admin/remuneration/invoice", {"obligation_ids": [oid]})
        self.assertEqual(inv.status, 200, inv.body)   # R$ 25,00 ≥ mínimo de fatura da política (R$ 20,00)
        charge = inv.json["platform_charge_id"]
        # a organização não move a fatura da plataforma (não marca paga nem devolvida)
        moved = self.osc.post(f"/v1/payments/charges/{charge}/transition", {"to_state": "checkout_started"})
        self.assertEqual(moved.status, 403, moved.body)
        self.assertEqual(moved.json["code"], "platform_invoice")
        self.assertEqual(self.finance.post(f"/v1/admin/remuneration/{oid}/receipt", {"received_cents": 2_500, "reference": "PIX-E2E-REEMB"}).json["state"], "received")
        body = {"refunded_cents": 2_500, "reference": "DEV-001", "note": "Serviço cancelado: devolução integral ao pagador."}
        self.assertEqual(self.finance.post(f"/v1/admin/remuneration/{oid}/refund", body).status, 403, "reembolso exige finance.approve")
        self.assertEqual(self.osc.post(f"/v1/admin/remuneration/{oid}/refund", body).status, 403)
        part = self.controller.post(f"/v1/admin/remuneration/{oid}/refund", {**body, "refunded_cents": 100})
        self.assertEqual(part.json["code"], "partial_refund", "parcial é ajuste com decisão própria")
        ok = self.controller.post(f"/v1/admin/remuneration/{oid}/refund", body)
        self.assertEqual(ok.status, 200, ok.body)
        self.assertEqual(ok.json["state"], "reversed")
        with db_system() as c:
            hist = c.query("SELECT to_state, note FROM remuneration_obligation_events WHERE obligation_id = $1 ORDER BY id", oid)
        self.assertIn("reversed", [h["to_state"] for h in hist])
        self.assertTrue(any("DEV-001" in (h["note"] or "") for h in hist), "referência do reembolso no histórico")
        # e pelo caminho do provedor (origem de sistema): devolução da cobrança reverte o que estiver ligado a ela
        from impacto.economics import payments as PAY
        with db_system() as c:
            o2 = c.scalar("SELECT id::text FROM remuneration_obligations WHERE platform_charge_id = $1", charge)
            self.assertEqual(o2, oid)
            for s in ("checkout_started", "pending", "paid", "refunded"):
                PAY.transition(c, charge_id=charge, to_state=s, org_id=None)
            self.assertEqual(c.scalar("SELECT state FROM remuneration_obligations WHERE id = $1", oid), "reversed")


if __name__ == "__main__":
    unittest.main()
