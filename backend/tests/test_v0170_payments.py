"""v0.17.0 — arquitetura de pagamento da plataforma.

A regra que estes testes protegem vem textualmente dos documentos desta rodada: "Nunca apresentar
pagamento fake como pagamento real." A proteção não é um aviso na tela — é `is_simulated`, derivada do
provedor por gatilho, e `platform_revenue()`, que nunca soma simulado com real.

Nenhum teste aqui afirma que a cobrança está integrada. Não há provedor configurado nesta instalação,
e vários destes testes verificam justamente isso.
"""
from __future__ import annotations

import datetime as dt
import unittest

from tests.support import app_tx, db_system, make_admin, new_account, owner_conn


def _d(days: int = 0) -> str:
    return (dt.date.today() + dt.timedelta(days=days)).isoformat()


class PayBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.org = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        cls.admin, _ = make_admin()

    def charge(self, **extra) -> dict:
        body = {"kind": "one_off", "method": "card", "amount_cents": 9900, "currency": "BRL", **extra}
        r = self.org.post("/v1/payments/charges", body)
        self.assertEqual(r.status, 201, r)
        return r.json


# ================================================================================================ a trava
class SimulationHonestyTests(PayBase):
    def test_no_provider_is_configured_and_the_api_says_so(self):
        r = self.org.get("/v1/payments/status")
        self.assertEqual(r.status, 200, r)
        self.assertFalse(r.json["configured"])
        self.assertEqual(r.json["banner"], "PRODUCTION PAYMENT NOT CONFIGURED")
        self.assertEqual(r.json["methods_available_now"], [],
                         "sem provedor, nenhum meio está disponível de verdade")
        self.assertIn("simulada", r.json["note"].lower())

    def test_every_charge_is_born_simulated_and_carries_the_warning(self):
        c = self.charge()
        self.assertTrue(c["is_simulated"])
        self.assertIn("PRODUCTION PAYMENT NOT CONFIGURED", c["warning"])
        self.assertEqual(c["state"], "created")

    def test_the_warning_appears_on_every_line_not_only_in_the_summary(self):
        """Linha de extrato que não diz que é simulada é linha que alguém vai somar."""
        self.charge()
        lst = self.org.get("/v1/payments/charges").json
        self.assertTrue(lst["items"])
        for item in lst["items"]:
            if item["is_simulated"]:
                self.assertIn("simulada", item["warning"].lower(), item)

    def test_nobody_can_mark_a_simulated_charge_as_real(self):
        """A recusa é melhor que a sobrescrita: quem tentou tem de receber o erro, não o silêncio."""
        c = self.charge()
        with app_tx(self.org) as conn, self.assertRaises(Exception) as e:
            conn.run("UPDATE platform_charges SET is_simulated = false WHERE id = $1", c["id"])
        self.assertIn("derivada do provedor", str(e.exception).lower())
        # Nem pelo papel dono, que não passa por RLS nenhuma.
        oc = owner_conn()
        try:
            with self.assertRaises(Exception):
                oc.run("UPDATE platform_charges SET is_simulated = false WHERE id = $1", c["id"])
        finally:
            oc.close()
        self.assertTrue(self.org.get(f"/v1/payments/charges/{c['id']}").json["is_simulated"])

    def test_simulated_money_never_enters_real_revenue(self):
        c = self.charge(amount_cents=50_000)
        for s in ("checkout_started", "pending", "paid"):
            self.assertEqual(self.org.post(f"/v1/payments/charges/{c['id']}/transition",
                                           {"to_state": s}).status, 200)
        rev = self.admin.get("/v1/admin/payments/revenue").json
        brl = next((i for i in rev["items"] if i["currency"] == "BRL"), None)
        self.assertIsNotNone(brl, rev)
        self.assertEqual(brl["real_paid_cents"], 0, "não há provedor real: a receita real é zero")
        self.assertGreater(brl["simulated_cents"], 0, "e o simulado aparece, em coluna própria")
        self.assertIn("nunca entra no real", rev["note"].lower())


# ================================================================================================ máquina
class StateMachineTests(PayBase):
    def test_a_charge_is_born_in_created_even_through_direct_sql(self):
        with app_tx(self.org) as conn, self.assertRaises(Exception) as e:
            conn.run("INSERT INTO platform_charges(org_id,kind,method,amount_cents,currency,provider,"
                     " state) VALUES ($1,'one_off','card',100,'BRL','sandbox','paid')", self.org.org_id)
        self.assertIn("created", str(e.exception).lower())

    def test_a_transition_outside_the_graph_is_refused_and_says_where_it_can_go(self):
        c = self.charge()
        r = self.org.post(f"/v1/payments/charges/{c['id']}/transition", {"to_state": "settled"})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "invalid_transition")
        self.assertIn("checkout_started", r.json["details"]["possiveis"])

    def test_payment_dates_are_derived_not_written(self):
        c = self.charge()
        for s in ("checkout_started", "pending", "paid"):
            self.org.post(f"/v1/payments/charges/{c['id']}/transition", {"to_state": s})
        got = self.org.get(f"/v1/payments/charges/{c['id']}").json
        self.assertIsNotNone(got["paid_at"])
        with app_tx(self.org) as conn, self.assertRaises(Exception) as e:
            conn.run("UPDATE platform_charges SET paid_at = now() - interval '1 year' WHERE id = $1",
                     c["id"])
        self.assertIn("derivad", str(e.exception).lower())

    def test_the_trail_is_written_by_the_trigger_and_is_append_only(self):
        c = self.charge()
        self.org.post(f"/v1/payments/charges/{c['id']}/transition", {"to_state": "checkout_started"})
        got = self.org.get(f"/v1/payments/charges/{c['id']}").json
        states = [(e["from_state"], e["to_state"]) for e in got["events"]]
        self.assertEqual(states[0], (None, "created"), "a criação tem de estar na trilha")
        self.assertIn(("created", "checkout_started"), states)
        with app_tx(self.org) as conn, self.assertRaises(Exception):
            conn.run("UPDATE charge_events SET to_state = 'paid' WHERE charge_id = $1", c["id"])

    def test_a_partial_refund_needs_a_value_between_zero_and_the_total(self):
        c = self.charge(amount_cents=10_000)
        for s in ("checkout_started", "pending", "paid"):
            self.org.post(f"/v1/payments/charges/{c['id']}/transition", {"to_state": s})
        for bad in (0, 10_000, 20_000):
            r = self.org.post(f"/v1/payments/charges/{c['id']}/transition",
                              {"to_state": "partially_refunded", "refunded_cents": bad})
            self.assertEqual(r.status, 422, f"devolução parcial de {bad} deveria ser recusada")
        ok = self.org.post(f"/v1/payments/charges/{c['id']}/transition",
                           {"to_state": "partially_refunded", "refunded_cents": 3_000})
        self.assertEqual(ok.status, 200, ok)
        self.assertEqual(ok.json["refunded_cents"], 3_000)

    def test_a_full_refund_sets_the_refunded_value_to_the_whole_amount(self):
        c = self.charge(amount_cents=7_700)
        for s in ("checkout_started", "pending", "paid", "refunded"):
            self.assertEqual(self.org.post(f"/v1/payments/charges/{c['id']}/transition",
                                           {"to_state": s}).status, 200, s)
        self.assertEqual(self.org.get(f"/v1/payments/charges/{c['id']}").json["refunded_cents"], 7_700)


# ================================================================================================ meios
class MethodTests(PayBase):
    def test_installments_are_modelled_apart_from_subscription(self):
        """Parcelamento tem número fixo de parcelas e não renova — por isso não é assinatura."""
        c = self.charge(kind="installment_plan", installments=3, amount_cents=30_000)
        self.assertEqual(c["state"], "created")
        r = self.org.put(f"/v1/payments/charges/{c['id']}/installments", {"schedule": [
            {"amount_cents": 10_000, "due_on": _d(30)},
            {"amount_cents": 10_000, "due_on": _d(60)},
            {"amount_cents": 10_000, "due_on": _d(90)}]})
        self.assertEqual(r.status, 200, r)
        got = self.org.get(f"/v1/payments/charges/{c['id']}").json
        self.assertEqual(len(got["installments_schedule"]), 3)
        self.assertEqual(sum(i["amount_cents"] for i in got["installments_schedule"]), 30_000)

    def test_an_installment_schedule_that_does_not_add_up_is_refused(self):
        c = self.charge(kind="installment_plan", installments=2, amount_cents=20_000)
        r = self.org.put(f"/v1/payments/charges/{c['id']}/installments", {"schedule": [
            {"amount_cents": 5_000, "due_on": _d(30)},
            {"amount_cents": 5_000, "due_on": _d(60)}]})
        self.assertIn(r.status, (409, 422), f"a soma não fecha com o total e precisa ser recusada: {r}")

    def test_installments_only_exist_on_card(self):
        r = self.org.post("/v1/payments/charges", {"kind": "installment_plan", "method": "boleto",
                                                   "amount_cents": 10_000, "installments": 2,
                                                   "due_on": _d(30)})
        self.assertEqual(r.status, 422, r)

    def test_boleto_requires_a_due_date_and_pix_an_expiry(self):
        with app_tx(self.org) as conn, self.assertRaises(Exception) as e:
            conn.run("INSERT INTO platform_charges(org_id,kind,method,amount_cents,currency,provider)"
                     " VALUES ($1,'one_off','boleto',1000,'BRL','sandbox')", self.org.org_id)
        self.assertIn("boleto_has_due_date", str(e.exception))
        with app_tx(self.org) as conn, self.assertRaises(Exception) as e:
            conn.run("INSERT INTO platform_charges(org_id,kind,method,amount_cents,currency,provider)"
                     " VALUES ($1,'one_off','pix',1000,'BRL','sandbox')", self.org.org_id)
        self.assertIn("pix_has_expiry", str(e.exception))

    def test_pix_and_boleto_artifacts_are_stored_with_their_deadline(self):
        oc = owner_conn()
        try:
            pix = oc.scalar("INSERT INTO platform_charges(org_id,kind,method,amount_cents,currency,"
                            " provider,expires_at) VALUES ($1,'one_off','pix',5000,'BRL','sandbox',"
                            " now() + interval '30 minutes') RETURNING id::text", self.org.org_id)
            oc.run("INSERT INTO charge_pix(charge_id,payload,expires_at) VALUES ($1,$2,"
                   " now() + interval '30 minutes')", pix, "00020126" + "0" * 60)
            bol = oc.scalar("INSERT INTO platform_charges(org_id,kind,method,amount_cents,currency,"
                            " provider,due_on) VALUES ($1,'one_off','boleto',5000,'BRL','sandbox',"
                            " current_date + 5) RETURNING id::text", self.org.org_id)
            oc.run("INSERT INTO charge_boleto(charge_id,digitable_line,due_on) VALUES ($1,$2,"
                   " current_date + 5)", bol, "34191" + "0" * 42)
        finally:
            oc.close()
        p = self.org.get(f"/v1/payments/charges/{pix}").json
        self.assertIsNotNone(p["pix"], "a instrução do PIX tem de estar legível pela organização")
        self.assertIsNotNone(p["pix"]["expires_at"], "PIX sem prazo não existe")
        b = self.org.get(f"/v1/payments/charges/{bol}").json
        self.assertIsNotNone(b["boleto"])
        self.assertIsNotNone(b["boleto"]["due_on"])

    def test_expired_pix_and_boleto_are_closed_by_the_job(self):
        oc = owner_conn()
        try:
            cid = oc.scalar("INSERT INTO platform_charges(org_id,kind,method,amount_cents,currency,"
                            " provider,expires_at) VALUES ($1,'one_off','pix',5000,'BRL','sandbox',"
                            " now() + interval '1 hour') RETURNING id::text", self.org.org_id)
            oc.run("UPDATE platform_charges SET state='checkout_started' WHERE id=$1", cid)
            oc.run("UPDATE platform_charges SET state='pending' WHERE id=$1", cid)
            oc.run("UPDATE platform_charges SET expires_at = now() - interval '1 minute' WHERE id=$1", cid)
            from impacto.economics import payments as PAY
            out = PAY.expire_due(oc)
            self.assertGreaterEqual(out["expired"], 1)
            self.assertEqual(oc.scalar("SELECT state FROM platform_charges WHERE id=$1", cid), "expired")
        finally:
            oc.close()


# ================================================================================================ cartão
class InstrumentTests(PayBase):
    def test_the_platform_stores_no_card_number(self):
        """`last4` com mais de quatro dígitos é recusado. É o campo em que alguém grava o número todo."""
        with app_tx(self.org) as conn, self.assertRaises(Exception):
            conn.run("INSERT INTO payment_instruments(org_id,kind,provider,provider_token,last4)"
                     " VALUES ($1,'card','sandbox','tok_teste','4111111111111111')", self.org.org_id)
        with app_tx(self.org) as conn, self.assertRaises(Exception) as e:
            conn.run("INSERT INTO payment_instruments(org_id,kind,provider,provider_token,"
                     " holder_label) VALUES ($1,'card','sandbox','tok_outro','4111111111111111')",
                     self.org.org_id)
        self.assertIn("dígitos", str(e.exception).lower())

    def test_there_is_no_column_for_card_data(self):
        with db_system() as c:
            cols = {r["column_name"] for r in c.query(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'payment_instruments'")}
        for forbidden_col in ("pan", "card_number", "number", "cvv", "cvc", "security_code"):
            self.assertNotIn(forbidden_col, cols,
                             f"payment_instruments não pode ter coluna {forbidden_col}")

    def test_the_platform_admin_cannot_read_a_client_card_token(self):
        """Não há por que um administrador ver o token de cartão de um cliente."""
        with app_tx(self.org) as conn:
            conn.run("INSERT INTO payment_instruments(org_id,kind,provider,provider_token,last4)"
                     " VALUES ($1,'card','sandbox','tok_do_cliente','4242')", self.org.org_id)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM payment_instruments"
                                      " WHERE provider_token = 'tok_do_cliente'"), 0,
                             "o contexto de sistema não deve alcançar o token do cliente")


# ================================================================================================ webhook
class WebhookTests(PayBase):
    def test_a_replayed_event_is_counted_and_produces_no_effect(self):
        from impacto.economics import payments as PAY
        oc = owner_conn()
        try:
            first = PAY.record_webhook(oc, provider="sandbox", event_id="evt_unico_do_teste",
                                       event_type="charge.paid", payload={"a": 1},
                                       signature_verified=True)
            self.assertFalse(first["duplicate"])
            self.assertTrue(first["applied"])
            again = PAY.record_webhook(oc, provider="sandbox", event_id="evt_unico_do_teste",
                                       event_type="charge.paid", payload={"a": 1},
                                       signature_verified=True)
            self.assertTrue(again["duplicate"])
            self.assertFalse(again["applied"], "reentrega não pode produzir efeito")
            self.assertEqual(oc.scalar("SELECT duplicate_count FROM billing_events"
                                       " WHERE event_id = 'evt_unico_do_teste'"), 1)
        finally:
            oc.close()

    def test_an_event_without_a_valid_signature_is_stored_but_not_applied(self):
        """O frontend nunca é fonte de verdade sobre pagamento: quem confirma é o webhook assinado."""
        from impacto.economics import payments as PAY
        oc = owner_conn()
        try:
            out = PAY.record_webhook(oc, provider="sandbox", event_id="evt_sem_assinatura",
                                     event_type="charge.paid", payload={}, signature_verified=False)
            self.assertFalse(out["applied"])
            self.assertIn("assinatura", out["note"].lower())
            row = oc.one("SELECT status, signature_verified FROM billing_events"
                         " WHERE event_id = 'evt_sem_assinatura'")
            self.assertFalse(row["signature_verified"])
            self.assertEqual(row["status"], "rejected_signature")
        finally:
            oc.close()

    def test_reconciliation_surfaces_stuck_charges_and_unverified_events(self):
        r = self.admin.get("/v1/admin/payments/reconciliation")
        self.assertEqual(r.status, 200, r)
        for key in ("events", "stuck_charges", "unverified_events", "note"):
            self.assertIn(key, r.json)
        self.assertIn("forjar", r.json["note"].lower())


# ================================================================================================ isolamento
class PaymentIsolationTests(PayBase):
    def test_another_org_never_sees_or_moves_my_charge(self):
        c = self.charge()
        self.assertEqual(self.other.get(f"/v1/payments/charges/{c['id']}").status, 404)
        self.assertIn(self.other.post(f"/v1/payments/charges/{c['id']}/transition",
                                      {"to_state": "cancelled"}).status, (403, 404))

    def test_the_org_cannot_rewrite_the_amount_or_the_provider(self):
        c = self.charge()
        with app_tx(self.org) as conn, self.assertRaises(Exception) as e:
            conn.run("UPDATE platform_charges SET amount_cents = 1 WHERE id = $1", c["id"])
        self.assertIn("administração", str(e.exception).lower())
        with app_tx(self.org) as conn, self.assertRaises(Exception):
            conn.run("UPDATE platform_charges SET provider = 'stripe' WHERE id = $1", c["id"])


if __name__ == "__main__":
    unittest.main()


# ================================================================================================ job
class PaymentJobTests(unittest.TestCase):
    def test_the_deadline_job_is_registered_in_the_worker(self):
        """Prazo que só vence quando alguém roda o comando à mão não vence."""
        from impacto import jobs as J
        self.assertIn("payment_deadlines", [n for n, _ in J.JOBS])

    def test_the_job_runs_and_reports_what_it_closed(self):
        from tests.support import server
        from impacto import jobs as J
        out = J.payment_deadlines(server()["state"])
        self.assertIn("expired", out)
        self.assertIsInstance(out["expired"], int)


# ================================================================================================ receita
class RevenueShapeTests(PayBase):
    def test_subscription_revenue_is_reported_apart_from_charges(self):
        """Duas tabelas escrevendo o mesmo dinheiro dariam dois números para a mesma pergunta."""
        rev = self.admin.get("/v1/admin/payments/revenue").json
        self.assertIn("subscriptions", rev)
        self.assertIn("items", rev["subscriptions"])
        self.assertIn("separado", rev["subscriptions"]["note"].lower())

    def test_a_paid_invoice_with_a_real_provider_name_is_still_not_real_money(self):
        """A lição mais cara desta fase.

        A primeira versão deste relatório classificava fatura como real pelo NOME do provedor. A
        suíte completa pegou o erro: os cenários da v0.11.0 gravam `provider = 'stripe'` com uma
        chave falsa, e o total consolidado passou a mostrar R$ 396,00 de receita que não existe.
        Coluna dizendo 'stripe' não é prova de chave ao vivo.
        """
        oc = owner_conn()
        try:
            oc.run("INSERT INTO invoices(org_id, provider, amount_cents, currency, status, paid_at)"
                   " VALUES ($1,'stripe',777700,'BRL','paid', now())", self.org.org_id)
        finally:
            oc.close()
        rev = self.admin.get("/v1/admin/payments/revenue").json
        self.assertFalse(rev["provider_configured"])
        self.assertEqual(rev["total_real_paid_cents_by_currency"].get("BRL", 0), 0)
        brl = next(i for i in rev["subscriptions"]["items"] if i["currency"] == "BRL")
        self.assertEqual(brl["real_paid_cents"], 0)
        self.assertGreaterEqual(brl["simulated_cents"], 777700,
                                "a fatura tem de aparecer, do lado simulado")

    def test_the_consolidated_total_contains_only_real_money(self):
        c = self.charge(amount_cents=123_400)
        for s in ("checkout_started", "pending", "paid"):
            self.org.post(f"/v1/payments/charges/{c['id']}/transition", {"to_state": s})
        rev = self.admin.get("/v1/admin/payments/revenue").json
        total = rev["total_real_paid_cents_by_currency"]
        self.assertEqual(total.get("BRL", 0), 0,
                         "sem provedor real, o total consolidado tem de ser zero")
