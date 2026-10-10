"""v0.34.0 — ecossistema financeiro: gratuito até gerar valor, obrigações, recurso público, estados, conciliação (ADR-377 a ADR-383).

Cobre os cenários do pacote (PARTE XIV) que a v0.33.0 não cobria: pendente ≠ liquidado, estorno parcial, liquidação,
receita devida ≠ recebida, fatura paga parcialmente, cobrança vencida, compromisso ≠ dinheiro, recurso externo, tarifa
divergente, divergência razão × provedor, mudança de tarifa com operações antigas, valor fora dos limites, concorrência de
eventos, acesso de outra organização, e a regra ADR-381 (nada de prestação de contas consulta o estado comercial).
"""
import hashlib
import hmac
import json
import re
import threading
import unittest
import uuid

from tests.support import ROOT, Client, db_system, make_admin, make_staff, new_account, reauth, server, verify_beneficiary

SECRET = "segredo-webhook-de-teste-nao-e-segredo-real"


def _signed(client: Client, body: dict):
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.request("POST", "/v1/webhooks/donations/sandbox", raw=raw, ctype="application/json", headers={"X-Impacto-Signature": sig})


_ORIGINAL_CARD: dict[str, str] = {}


def _set_rule_active(key: str, active: bool) -> None:
    """Só o teste liga uma regra — e desliga no finally — passando pelo MESMO portão do banco que a produção passaria:
    carta legal VERDE nova (as cartas são append-only: a de ontem explica a decisão de ontem), regra validada, e o portão
    recusa por desenho qualquer regra do motor `success_fee` (ADR-022)."""
    with db_system() as c:
        if active:
            _ORIGINAL_CARD[key] = c.scalar("SELECT legal_card_id::text FROM monetization_rules WHERE key = $1", key)
            green = c.scalar(
                "INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature, contractual_relation,"
                " required_document, required_terms, cancellation_policy, refund_policy, tax_notes, invoice_notes, regulatory_notes, legal_basis, source_name,"
                " source_url, verified_on, open_questions, needs_lawyer, note)"
                " SELECT rule_key, 'green', 'high', payer, beneficiary, billing_event, revenue_nature, contractual_relation, required_document, required_terms,"
                " cancellation_policy, refund_policy, tax_notes, invoice_notes, regulatory_notes, legal_basis, source_name, source_url, current_date, NULL, false,"
                " 'CARTA DE TESTE: simula a revisão jurídica concluída; existe só no banco de teste' FROM monetization_legal_cards WHERE id = $1::uuid RETURNING id::text",
                _ORIGINAL_CARD[key])
            c.run("UPDATE monetization_rules SET legal_card_id = $2::uuid, legal_status = 'validated', active = true WHERE key = $1", key, green)
        else:
            c.run("UPDATE monetization_rules SET active = false, legal_status = 'review_required', legal_card_id = $2::uuid WHERE key = $1", key, _ORIGINAL_CARD[key])


def _publish(osc: Client, reviewer: Client, campaign_id: str) -> None:
    assert osc.post(f"/v1/campaigns/{campaign_id}/submit").status == 200
    assert reviewer.post(f"/v1/admin/donation-campaigns/{campaign_id}/review", {"approve": True, "note": "Revisão de teste: finalidade clara."}).status == 200
    verify_beneficiary(osc.org_id, reviewer)   # v0.35.0: decisão + confirmação por outra pessoa (KYC-03)
    assert osc.post(f"/v1/campaigns/{campaign_id}/publish").status == 200


def _campaign(osc: Client, reviewer: Client, **extra) -> tuple[str, str]:
    slug = "eco-" + uuid.uuid4().hex[:8]
    r = osc.post("/v1/campaigns", {"slug": slug, "title": "Campanha do ecossistema", "kind": "organization",
                                   "summary": "Arrecadação para testar a camada financeira sem custódia.",
                                   "target_cents": 1_000_000, "purpose": "Testes.", "contingency_policy": "Sem a meta, segue.",
                                   "refund_policy": "Estorno pelo provedor.", **extra})
    assert r.status == 201, r
    _publish(osc, reviewer, r.json["id"])
    return r.json["id"], slug


def _donate_and_confirm(anon: Client, slug: str, cents: int, settle: bool = False, **body) -> tuple[str, str]:
    d = anon.post(f"/v1/public/donation-campaigns/{slug}/donate", {"amount_cents": cents, "method": "pix", "idempotency_key": "k-" + uuid.uuid4().hex[:8], **body}).json
    with db_system() as c:
        charge = c.scalar("SELECT provider_charge_id FROM donations WHERE id = $1", d["id"])
    r = _signed(anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "PAYMENT_RECEIVED" if settle else "payment.confirmed", "charge_id": charge, "amount_cents": cents, "currency": "BRL"})
    assert r.json["effect"] == "confirmed", r.body
    return d["id"], charge


class EcosystemTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls.state.settings.payment_webhook_secret = SECRET
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        cls.company = new_account("company", compliance="approved")
        cls.reviewer = make_staff("compliance")
        reauth(cls.reviewer)   # v0.35.0: compliance.write exige step-up
        cls.finance = make_staff("finance")
        cls.controller = make_staff("controller")
        reauth(cls.finance)     # finance.write e finance.approve exigem confirmação de identidade (step-up)
        reauth(cls.controller)
        cls.admin, _ = make_admin()
        cls.anon = Client()
        cls.campaign, cls.slug = _campaign(cls.osc, cls.reviewer)

    # ---------------------------------------------------------------- estados: pendente ≠ confirmado ≠ liquidado
    def test_01_pending_is_not_raised_and_settled_is_separate_from_confirmed(self):
        pend = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 7_000, "method": "pix", "idempotency_key": "p-" + uuid.uuid4().hex[:6]}).json
        self.assertEqual(pend["status"], "awaiting_payment")
        t = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        self.assertEqual(t["gross_confirmed_cents"], 0, "pendente não é arrecadação")
        self.assertGreaterEqual(t["pending_cents"], 7_000)
        did, charge = _donate_and_confirm(self.anon, self.slug, 10_000)
        t = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        self.assertEqual(t["gross_confirmed_cents"], 10_000)
        self.assertEqual(t["settled_cents"], 0, "confirmado não é liquidado")
        r = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.settled", "charge_id": charge})
        self.assertEqual(r.json["effect"], "settled")
        t = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        self.assertEqual(t["settled_cents"], 10_000)
        again = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.settled", "charge_id": charge})
        self.assertEqual(again.json["effect"], "already_settled")
        with db_system() as c:
            with self.assertRaises(Exception, msg="liquidação não se desfaz"):
                c.run("UPDATE donations SET settled_at = NULL WHERE id = $1", did)
        self.__class__.donation = did
        self.__class__.charge = charge

    # ---------------------------------------------------------------- obrigação: calculada, nunca devida sozinha
    def test_02_calculated_fee_is_an_obligation_that_is_not_due_and_platform_revenue_is_zero(self):
        with db_system() as c:
            o = c.one("SELECT state, amount_cents, basis_cents, funding_source, rule_version_id FROM remuneration_obligations WHERE source_kind = 'donation' AND source_id = $1", self.donation)
        self.assertIsNotNone(o)
        self.assertEqual(o["state"], "calculated")
        self.assertEqual(o["amount_cents"], 100, "1 % de R$ 100,00, pela versão congelada")
        self.assertIsNotNone(o["rule_version_id"])
        view = self.osc.get("/v1/org/remuneration").json
        self.assertEqual(view["totals_by_state"].get("due", 0), 0)
        self.assertGreaterEqual(view["totals_by_state"]["calculated"], 100)
        self.assertIn("never_blocks", view)
        rev = self.finance.get("/v1/admin/remuneration").json["revenue"]
        self.assertEqual(rev["due_cents"], 0)
        self.assertEqual(rev["received_cents"], 0)
        self.assertGreaterEqual(rev["calculated_not_due_cents"], 100)
        # avaliação com a regra INATIVA: nada vira devido, e o motivo é nomeado
        ev = self.finance.post(f"/v1/admin/remuneration/orgs/{self.osc.org_id}/evaluate")
        self.assertEqual(ev.status, 200, ev.body)
        self.assertEqual(ev.json["became_due"], [])
        reasons = {r for k in ev.json["kept"] for r in k["reasons"]}
        self.assertIn("rule_inactive", reasons)
        self.assertIn("notice_pending", reasons)

    # ---------------------------------------------------------------- gatilho auditável: só com as cinco condições
    def test_03_free_until_value_trigger_requires_rule_notice_allowance_and_settlement(self):
        _set_rule_active("donation.platform_fee", True)
        try:
            # franquia de R$ 20.000 liquidados: ainda abaixo → within_allowance
            ev = self.finance.post(f"/v1/admin/remuneration/orgs/{self.osc.org_id}/evaluate").json
            self.assertEqual(ev["became_due"], [])
            reasons = {r for k in ev["kept"] for r in k["reasons"]}
            self.assertIn("within_allowance", reasons)
            self.assertNotIn("rule_inactive", reasons)
            # liquida muito mais que a franquia (uma doação grande, liquidada no mesmo evento PAYMENT_RECEIVED)
            big, _ = _donate_and_confirm(self.anon, self.slug, 3_000_000, settle=True)
            ev = self.finance.post(f"/v1/admin/remuneration/orgs/{self.osc.org_id}/evaluate").json
            self.assertEqual(ev["became_due"], [], "sem aviso prévio nada é devido")
            self.assertIn("notice_pending", {r for k in ev["kept"] for r in k["reasons"]})
            # aviso enviado agora: prazo correndo
            n = self.finance.post(f"/v1/admin/remuneration/orgs/{self.osc.org_id}/notices", {"kind": "charging_starts"})
            self.assertEqual(n.status, 200, n.body)
            ev = self.finance.post(f"/v1/admin/remuneration/orgs/{self.osc.org_id}/evaluate").json
            self.assertEqual(ev["became_due"], [])
            self.assertIn("notice_period_running", {r for k in ev["kept"] for r in k["reasons"]})
            # o aviso foi há 31 dias (só o banco de teste mexe no relógio): agora o gatilho fecha
            with db_system() as c:
                c.run("UPDATE remuneration_notices SET sent_at = now() - interval '31 days' WHERE id = $1", n.json["id"])
            ev = self.finance.post(f"/v1/admin/remuneration/orgs/{self.osc.org_id}/evaluate").json
            self.assertGreater(len(ev["became_due"]), 0, ev)
            self.assertTrue(all(b["trigger"] == "settled_above_allowance_after_notice" for b in ev["became_due"]))
            with db_system() as c:
                o = c.one("SELECT id::text AS id, state, trigger_code, notice_id, due_on FROM remuneration_obligations WHERE source_kind='donation' AND source_id = $1", big)
            self.assertEqual(o["state"], "due")
            self.assertEqual(o["trigger_code"], "settled_above_allowance_after_notice")
            self.assertIsNotNone(o["notice_id"])
            self.__class__.due_obligation = o["id"]
            self.__class__.big_donation = big
        finally:
            _set_rule_active("donation.platform_fee", False)
        # a história fica no histórico append-only
        with db_system() as c:
            ev_rows = c.query("SELECT from_state, to_state FROM remuneration_obligation_events WHERE obligation_id = $1 ORDER BY id", self.due_obligation)
        self.assertEqual([(e["from_state"], e["to_state"]) for e in ev_rows], [(None, "calculated"), ("calculated", "due")])

    # ---------------------------------------------------------------- devida ≠ faturada ≠ recebida ≠ liquidada; parcial; vencida; disputa
    def test_04_due_invoiced_received_settled_are_different_and_partial_receipt_stays_open(self):
        oid = self.due_obligation
        self.assertIsNotNone(oid)
        inv = self.finance.post("/v1/admin/remuneration/invoice", {"obligation_ids": [oid]})
        self.assertEqual(inv.status, 200, inv.body)
        self.assertEqual(inv.json["total_cents"], 30_000, "1 % de R$ 30.000,00")
        with db_system() as c:
            ch = c.one("SELECT kind, method, provider, is_simulated, state, amount_cents FROM platform_charges WHERE id = $1", inv.json["platform_charge_id"])
        self.assertEqual((ch["kind"], ch["method"], ch["provider"], ch["is_simulated"]), ("operation", "manual", "manual", True))
        self.assertEqual(ch["amount_cents"], 30_000)
        rev = self.finance.get("/v1/admin/remuneration").json["revenue"]
        self.assertEqual(rev["received_cents"], 0, "faturado não é recebido")
        self.assertEqual(self.finance.post(f"/v1/admin/remuneration/{oid}/charged").json["state"], "charged")
        part = self.finance.post(f"/v1/admin/remuneration/{oid}/receipt", {"received_cents": 10_000, "reference": "E2E-PARCIAL-1"})
        self.assertEqual(part.status, 200, part.body)
        self.assertTrue(part.json.get("partial"))
        self.assertEqual(part.json["state"], "charged", "pagamento parcial não fecha a obrigação")
        over = self.finance.post(f"/v1/admin/remuneration/{oid}/receipt", {"received_cents": 25_000, "reference": "E2E-DEMAIS"})
        self.assertEqual(over.status, 422, "recebido maior que o devido é ajuste, não recebimento")
        # vencimento: vence só com due_on passado + carência; aqui forçamos o vencimento no banco de teste
        with db_system() as c:
            c.run("UPDATE remuneration_obligations SET due_on = current_date - 60 WHERE id = $1", oid)
        self.assertEqual(self.finance.post("/v1/admin/remuneration/mark-overdue").json["marked"], 1)
        # vencida NÃO bloqueia nada: prestação de contas e página pública seguem
        self.assertEqual(self.osc.get(f"/v1/campaigns/{self.campaign}/accountability").status, 200)
        self.assertEqual(self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").status, 200)
        self.assertEqual(self.osc.post(f"/v1/campaigns/{self.campaign}/updates", {"title": "Seguimos", "body": "Prestação de contas segue mesmo com fatura vencida.", "is_public": True}).status, 201)
        # a organização contesta; o controller decide manter; o restante é recebido; liquidado só com finance.approve
        disp = self.osc.post(f"/v1/org/remuneration/{oid}/dispute", {"reason": "Discordamos do cálculo da base nesta doação."})
        self.assertEqual(disp.status, 200, disp.body)
        self.assertEqual(self.finance.post(f"/v1/admin/remuneration/{oid}/decide", {"outcome": "uphold", "note": "Cálculo conferido contra a versão congelada."}).status, 403, "decidir disputa exige finance.approve")
        dec = self.controller.post(f"/v1/admin/remuneration/{oid}/decide", {"outcome": "uphold", "note": "Cálculo conferido contra a versão congelada."})
        self.assertEqual(dec.status, 200, dec.body)
        rest = self.finance.post(f"/v1/admin/remuneration/{oid}/receipt", {"received_cents": 20_000, "reference": "E2E-RESTO"})
        self.assertEqual(rest.json["state"], "received")
        self.assertEqual(self.finance.post(f"/v1/admin/remuneration/{oid}/settle", {"note": "extrato 10/10"}).status, 403)
        self.assertEqual(self.controller.post(f"/v1/admin/remuneration/{oid}/settle", {"note": "extrato 10/10 conferido"}).json["state"], "settled")
        rev = self.finance.get("/v1/admin/remuneration").json["revenue"]
        self.assertEqual(rev["settled_cents"], 30_000)
        with db_system() as c:
            with self.assertRaises(Exception, msg="valor congelado"):
                c.run("UPDATE remuneration_obligations SET amount_cents = 1 WHERE id = $1", oid)
            with self.assertRaises(Exception, msg="histórico é append-only"):
                c.run("DELETE FROM remuneration_obligation_events WHERE obligation_id = $1", oid)

    # ---------------------------------------------------------------- recurso público: isento por padrão; elegível só com instrumento
    def test_05_public_funding_is_exempt_unless_instrument_and_authorization_are_recorded(self):
        camp, slug = _campaign(self.osc, self.reviewer, funding_source="public", public_instrument_ref="Termo de Fomento 12/2026")
        did, _ = _donate_and_confirm(self.anon, slug, 50_000, settle=True)
        with db_system() as c:
            o = c.one("SELECT id::text AS id, state, funding_source FROM remuneration_obligations WHERE source_kind='donation' AND source_id = $1", did)
        self.assertEqual((o["state"], o["funding_source"]), ("exempt", "public"))
        _set_rule_active("donation.platform_fee", True)
        try:
            ev = self.finance.post(f"/v1/admin/remuneration/orgs/{self.osc.org_id}/evaluate").json
            kept = {k["id"]: k["reasons"] for k in ev["kept"]}
            self.assertIn("public_funding_exempt", kept[o["id"]])
            self.assertEqual(self.finance.post(f"/v1/admin/remuneration/{o['id']}/authorize-public", {"instrument_ref": "Termo de Fomento 12/2026, cláusula 9", "note": "Despesa prevista no plano de trabalho."}).status, 403)
            au = self.controller.post(f"/v1/admin/remuneration/{o['id']}/authorize-public", {"instrument_ref": "Termo de Fomento 12/2026, cláusula 9", "note": "Despesa prevista no plano de trabalho aprovado."})
            self.assertEqual(au.status, 200, au.body)
            self.assertEqual(au.json["state"], "calculated")
            ev = self.finance.post(f"/v1/admin/remuneration/orgs/{self.osc.org_id}/evaluate").json
            kept = {k["id"]: k["reasons"] for k in ev["kept"]}
            self.assertNotIn("public_funding_exempt", kept.get(o["id"], []))
        finally:
            _set_rule_active("donation.platform_fee", False)

    # ---------------------------------------------------------------- estorno parcial, depois total; obrigação revertida
    def test_06_partial_refund_then_full_refund_reverse_the_right_amounts_once(self):
        did, charge = _donate_and_confirm(self.anon, self.slug, 20_000)
        before = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        r = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.partially_refunded", "charge_id": charge, "amount_cents": 5_000})
        self.assertEqual(r.json["effect"], "partially_refunded", r.body)
        after = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        self.assertEqual(after["reversed_cents"], before["reversed_cents"] + 5_000)
        self.assertEqual(after["gross_confirmed_cents"], before["gross_confirmed_cents"], "o bruto não é editado")
        self.assertEqual(after["confirmed_donations"], before["confirmed_donations"], "parcial continua contada")
        st = self.anon.get(f"/v1/public/donations/{did}").json
        self.assertEqual(st["status"], "partially_refunded")
        too_much = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.partially_refunded", "charge_id": charge, "amount_cents": 50_000})
        self.assertEqual(too_much.json["effect"], "under_review", "estorno maior que o pago abre caso, não lança")
        full = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.refunded", "charge_id": charge})
        self.assertEqual(full.json["effect"], "refunded")
        after2 = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        self.assertEqual(after2["reversed_cents"], before["reversed_cents"] + 20_000, "o total reverte só o restante")
        self.assertEqual(after2["confirmed_donations"], before["confirmed_donations"] - 1)
        again = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.refunded", "charge_id": charge})
        self.assertEqual(again.json["effect"], "already_reversed")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT state FROM remuneration_obligations WHERE source_kind='donation' AND source_id = $1", did), "reversed")
            bad = c.query("SELECT txn_id, sum(CASE WHEN side='D' THEN amount_cents ELSE -amount_cents END) AS s FROM donation_ledger_entries WHERE donation_id = $1 GROUP BY txn_id HAVING sum(CASE WHEN side='D' THEN amount_cents ELSE -amount_cents END) <> 0", did)
            self.assertEqual(bad, [], "toda transação do razão fecha em zero")

    # ---------------------------------------------------------------- compromisso e recurso externo nunca são dinheiro recebido
    def test_07_pledges_and_external_resources_never_enter_the_bar(self):
        before = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        with db_system() as c:
            ledger_before = c.scalar("SELECT count(*) FROM donation_ledger_entries WHERE campaign_id = $1", self.campaign)
        pl = self.company.post(f"/v1/public/donation-campaigns/{self.slug}/pledge", {"amount_cents": 500_000, "display": "Empresa Exemplo", "as_organization": True})
        self.assertEqual(pl.status, 201, pl.body)
        ex = self.osc.post(f"/v1/campaigns/{self.campaign}/external-resources", {"kind": "public_transfer", "source_name": "Prefeitura (exemplo)", "funding_source": "public",
                                                                                "instrument_ref": "Termo de Colaboração 3/2026", "amount_cents": 800_000, "received_on": "2026-10-01"})
        self.assertEqual(ex.status, 201, ex.body)
        nok = self.osc.post(f"/v1/campaigns/{self.campaign}/external-resources", {"kind": "public_transfer", "source_name": "Sem instrumento", "funding_source": "public",
                                                                                 "amount_cents": 1_000, "received_on": "2026-10-01"})
        self.assertEqual(nok.status, 422, "recurso público exige instrumento")
        pub = self.anon.get(f"/v1/public/donation-campaigns/{self.slug}").json
        self.assertEqual(pub["totals"]["gross_confirmed_cents"], before["gross_confirmed_cents"], "compromisso e recurso externo não entram na barra")
        self.assertEqual(pub["pledges"]["cents"], 500_000)
        self.assertEqual(pub["totals"]["external_declared_cents"], 800_000)
        self.assertEqual(len(pub["external_resources"]), 1)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM donation_ledger_entries WHERE campaign_id = $1", self.campaign), ledger_before,
                             "compromisso e recurso externo não geram lançamento")
        # cumprir: só com doação confirmada da mesma campanha
        other_d, _ = _donate_and_confirm(self.anon, self.slug, 1_000)
        ff = self.osc.post(f"/v1/campaigns/{self.campaign}/pledges/{pl.json['id']}/fulfill", {"donation_id": other_d})
        self.assertEqual(ff.status, 200, ff.body)
        self.assertEqual(ff.json["status"], "fulfilled")
        funder = self.company.get("/v1/org/contributions").json
        self.assertEqual(funder["totals"]["pledged_cents"], 0)
        self.assertEqual(self.other.get(f"/v1/campaigns/{self.campaign}/accountability").status, 404, "outra organização não vê o painel")

    # ---------------------------------------------------------------- conciliação: exceções tipadas, sem duplicar, com histórico
    def test_08_reconciliation_opens_typed_exceptions_and_does_not_duplicate_them(self):
        camp, slug = _campaign(self.osc, self.reviewer)
        d1, c1 = _donate_and_confirm(self.anon, slug, 10_000)
        d2, c2 = _donate_and_confirm(self.anon, slug, 20_000)
        snapshot = [
            {"charge_id": c1, "amount_cents": 10_000, "fee_cents": 0, "confirmed": True, "reversed": False},
            {"charge_id": c2, "amount_cents": 19_000, "fee_cents": 150, "confirmed": True, "reversed": False},   # valor divergente
            {"charge_id": "PIX-SANDBOX-fantasma", "amount_cents": 5_000, "confirmed": True, "reversed": False},  # só no provedor
        ]
        run = self.finance.post(f"/v1/admin/reconciliation/campaigns/{camp}/run", {"charges": snapshot})
        self.assertEqual(run.status, 200, run.body)
        # v0.35.0 (auditoria, PAY-07): extrato digitado por UMA pessoa não concilia sozinho — abre as exceções e aguarda a
        # aprovação de outra (antes este teste exigia reconciled == 1 já aqui, que era a falha).
        self.assertEqual((run.json["reconciled"], run.json["would_reconcile"], run.json["awaiting_approval"]), (0, 1, True))
        self.assertEqual(run.json["opened"], 2)
        again = self.finance.post(f"/v1/admin/reconciliation/campaigns/{camp}/run", {"charges": snapshot}).json
        self.assertEqual(again["opened"], 0, "reexecutar não duplica exceções abertas")
        self.assertEqual(self.anon.get(f"/v1/public/donations/{d1}").json["status"], "confirmed", "sem aprovação, nada concilia")
        ok = self.controller.post(f"/v1/admin/reconciliation/runs/{run.json['run_id']}/approve")
        self.assertEqual((ok.status, ok.json["reconciled"], ok.json["opened"]), (200, 1, 0), ok.body)
        items = self.finance.get("/v1/admin/reconciliation/exceptions?status=open").json["items"]
        kinds = {i["kind"] for i in items if i["campaign_id"] == camp}
        self.assertEqual(kinds, {"amount_mismatch", "provider_only"})
        mism = next(i for i in items if i["campaign_id"] == camp and i["kind"] == "amount_mismatch")
        self.assertEqual((mism["expected_cents"], mism["observed_cents"]), (20_000, 19_000))
        self.assertEqual(self.anon.get(f"/v1/public/donations/{d1}").json["status"], "reconciled")
        self.assertEqual(self.anon.get(f"/v1/public/donations/{d2}").json["status"], "confirmed", "divergente NÃO vira conciliada")
        self.assertEqual(self.finance.post(f"/v1/admin/reconciliation/exceptions/{mism['id']}/assign").json["status"], "assigned")
        self.assertEqual(self.finance.post(f"/v1/admin/reconciliation/exceptions/{mism['id']}/resolve", {"outcome": "resolved", "note": "curto"}).status, 422)
        self.assertEqual(self.finance.post(f"/v1/admin/reconciliation/exceptions/{mism['id']}/resolve", {"outcome": "resolved", "note": "Provedor confirmou R$ 200,00; snapshot estava desatualizado."}).json["status"], "resolved")
        hist = self.finance.get(f"/v1/admin/reconciliation/exceptions/{mism['id']}/history").json["items"]
        self.assertEqual([h["to_status"] for h in hist], ["open", "assigned", "resolved"])
        # sandbox: o snapshot derivado dos eventos assinados concilia o que bate
        run3 = self.finance.post(f"/v1/admin/reconciliation/campaigns/{camp}/run", {}).json
        self.assertEqual(run3["snapshot_size"], 2)
        self.assertEqual(self.osc.post(f"/v1/admin/reconciliation/campaigns/{camp}/run", {}).status, 403, "organização não concilia")

    # ---------------------------------------------------------------- mudança de tarifa não reescreve operação antiga
    def test_09_a_new_fee_version_does_not_change_old_obligations(self):
        did_old, _ = _donate_and_confirm(self.anon, self.slug, 10_000)
        with db_system() as c:
            old_v = c.scalar("SELECT rule_version_id FROM remuneration_obligations WHERE source_kind='donation' AND source_id = $1", did_old)
            c.run("INSERT INTO fee_rule_versions(rule_key, version, bps, base, note) VALUES ('donation.platform_fee', 99, 250, 'gross', 'teste: versão nova')")
        try:
            did_new, _ = _donate_and_confirm(self.anon, self.slug, 10_000)
            with db_system() as c:
                o_old = c.one("SELECT amount_cents, rule_version_id FROM remuneration_obligations WHERE source_kind='donation' AND source_id = $1", did_old)
                o_new = c.one("SELECT amount_cents, rule_version_id FROM remuneration_obligations WHERE source_kind='donation' AND source_id = $1", did_new)
            self.assertEqual(o_old["amount_cents"], 100)
            self.assertEqual(o_old["rule_version_id"], old_v)
            self.assertEqual(o_new["amount_cents"], 250, "a nova versão vale só para o que vem depois")
            self.assertNotEqual(o_new["rule_version_id"], old_v)
        finally:
            # versões são append-only (forbid_mutation): a de teste é superada por uma versão posterior igual à original
            with db_system() as c:
                c.run("INSERT INTO fee_rule_versions(rule_key, version, bps, base, note) VALUES ('donation.platform_fee', 100, 100, 'gross', 'teste: volta ao 1 %')")

    # ---------------------------------------------------------------- limites, adulteração pelo cliente, concorrência
    def test_10_limits_tamper_and_concurrent_events(self):
        for cents in (0, -5, 50, 100_000_001):
            r = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": cents, "method": "pix"})
            self.assertEqual(r.status, 422, f"valor {cents} fora dos limites")
        # o cliente não escolhe estado, taxa nem valor pago: campo estranho é recusado (422), e a confirmação vem do provedor
        tamper = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 10_000, "method": "pix", "status": "confirmed", "platform_fee_cents": 0})
        self.assertEqual(tamper.status, 422, tamper.body)
        d = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 10_000, "method": "pix"}).json
        self.assertEqual(d["status"], "awaiting_payment")
        self.assertEqual(d["breakdown"]["platform_fee_cents"], 100)
        with db_system() as c:
            charge = c.scalar("SELECT provider_charge_id FROM donations WHERE id = $1", d["id"])
        ev = {"event_id": "evt-conc-" + uuid.uuid4().hex[:6], "type": "payment.confirmed", "charge_id": charge, "amount_cents": 10_000, "currency": "BRL"}
        results = []

        def fire():
            results.append(_signed(Client(), ev).json)
        threads = [threading.Thread(target=fire) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(1 for r in results if r.get("effect") == "confirmed"), 1, results)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(DISTINCT txn_id) FROM donation_ledger_entries WHERE donation_id = $1 AND account = 'donor_payment'", d["id"]), 1)
            self.assertEqual(c.scalar("SELECT count(*) FROM remuneration_obligations WHERE source_kind='donation' AND source_id = $1", d["id"]), 1)
            self.assertEqual(c.scalar("SELECT count(*) FROM payment_provider_events WHERE event_id = $1", ev["event_id"]), 1)

    # ---------------------------------------------------------------- ADR-381: nada de prestação de contas consulta o estado comercial
    def test_11_no_accountability_route_consults_commercial_state(self):
        src = {p.name: p.read_text(encoding="utf-8") for p in [
            ROOT / "backend" / "impacto" / "api" / "donation_routes.py", ROOT / "backend" / "impacto" / "services" / "donations.py",
            ROOT / "backend" / "impacto" / "services" / "reports.py", ROOT / "backend" / "impacto" / "api" / "execution_routes.py"]}
        forbidden = re.compile(r"org_commercial_state|entitlements\.|free_period|remuneration_obligations[^\n]*WHERE[^\n]*state\s*(=|IN)\s*\(?'(overdue|due)", re.I)
        for name, text in src.items():
            if name == "donations.py":
                # a única referência permitida é a leitura informativa na prestação de contas (lista, nunca condição)
                text = text.replace("obligations = c.query(\"SELECT id::text AS id, rule_key, basis_cents, amount_cents, state, funding_source, due_on FROM remuneration_obligations\"", "")
            self.assertIsNone(forbidden.search(text), f"{name} consulta estado comercial para condicionar acesso (ADR-381)")
        rem = (ROOT / "backend" / "impacto" / "services" / "remuneration.py").read_text(encoding="utf-8")
        self.assertNotRegex(rem, r"def (can_access|is_blocked|block_|lock_)")
        with db_system() as c:
            content = c.one("SELECT content FROM monetization_policy_versions WHERE key = 'free_until_value' ORDER BY version DESC LIMIT 1")["content"]
        content = content if isinstance(content, dict) else json.loads(content)
        self.assertIn("accountability", content["never_blocks"])
        self.assertEqual(content["public_funding_default"], "exempt")

    # ---------------------------------------------------------------- chargeback e meta atingida/ultrapassada
    def test_12_chargeback_reverses_once_and_voids_the_receipt(self):
        did, charge = _donate_and_confirm(self.anon, self.slug, 12_000)
        r = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "PAYMENT_CHARGEBACK_REQUESTED", "charge_id": charge})
        self.assertEqual(r.json["effect"], "chargeback", r.body)
        st = self.anon.get(f"/v1/public/donations/{did}").json
        self.assertEqual(st["status"], "chargeback")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM donation_receipts WHERE donation_id = $1", did), "voided")
            self.assertEqual(c.scalar("SELECT count(*) FROM donation_ledger_entries WHERE donation_id = $1 AND account = 'chargeback'", did), 1)
            self.assertEqual(c.scalar("SELECT state FROM remuneration_obligations WHERE source_kind='donation' AND source_id = $1", did), "reversed")
        again = _signed(self.anon, {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.refunded", "charge_id": charge})
        self.assertEqual(again.json["effect"], "already_reversed")

    def test_13_campaign_reaching_and_exceeding_the_target_keeps_accepting_and_shows_remaining(self):
        camp, slug = _campaign(self.osc, self.reviewer, target_cents=20_000)
        _donate_and_confirm(self.anon, slug, 15_000)
        pub = self.anon.get(f"/v1/public/donation-campaigns/{slug}").json
        self.assertEqual(pub["campaign"]["status"], "published")
        _donate_and_confirm(self.anon, slug, 10_000)   # ultrapassa
        pub = self.anon.get(f"/v1/public/donation-campaigns/{slug}").json
        self.assertEqual(pub["campaign"]["status"], "target_reached")
        self.assertEqual(pub["totals"]["net_after_reversals_cents"], 25_000)
        d = self.anon.post(f"/v1/public/donation-campaigns/{slug}/donate", {"amount_cents": 500, "method": "pix"})
        self.assertEqual(d.status, 201, "meta atingida continua aceitando: a contingência declarada diz o que acontece com o excedente")
        self.assertIn("contingency_policy", pub["campaign"])
