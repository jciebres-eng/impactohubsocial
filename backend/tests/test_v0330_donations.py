"""v0.33.0 — doações, campanhas, QR, webhook do provedor (sandbox), razão e prestação de contas (ADR-372 a ADR-376).

O que estes testes PROVAM, contra HTTP e PostgreSQL reais:
  * a campanha só vai ao ar depois de revisão de QUATRO OLHOS (quem criou não revisa) e com beneficiário VERIFICADO
    — e o banco recusa o atalho (PATCH legado 'published' → 409);
  * o QR público aponta para a URL canônica HTTPS da campanha, nunca para um payload Pix; regenerar muda a versão;
  * doar cria a cobrança no provedor SANDBOX e devolve o preço total e as parcelas; NADA fica pago pela tela;
  * só o evento ASSINADO do provedor confirma; assinatura adulterada não produz efeito; o mesmo evento reentregue
    não credita duas vezes; evento com valor diferente põe a doação em revisão em vez de confirmar;
  * cada confirmação vira lançamentos em partidas dobradas que FECHAM; estorno é lançamento novo (reversão), nunca
    edição; os totais da campanha são a soma — não existe coluna de saldo;
  * a taxa da plataforma é CALCULADA (1 %, hipótese congelada) mas DEVIDA = 0 enquanto a regra estiver inativa;
    a reserva do beneficiário nunca entra como receita da plataforma;
  * anonimato público: nome não aparece na página pública nem na lista pública; contato nunca sai;
  * outra organização não vê a prestação de contas (404); comprovante existe e não se chama recibo dedutível;
  * flags de cobrança real recusam subir sem adaptador (config.validate).
"""
import hashlib
import hmac
import json
import os
import unittest
import unittest.mock
import uuid
from dataclasses import replace

from tests.support import Client, db_system, make_admin, make_staff, new_account, server

SECRET = "segredo-webhook-de-teste-nao-e-segredo-real"


def _signed(client: Client, path: str, body: dict) -> object:
    raw = json.dumps(body).encode()
    sig = hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.request("POST", path, raw=raw, ctype="application/json", headers={"X-Impacto-Signature": sig})


class DonationsEndToEndTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        cls.state.settings.payment_webhook_secret = SECRET
        cls.state.settings.public_base_url = "https://impacto.teste"
        cls.osc = new_account("osc", compliance="approved")
        cls.outra = new_account("osc", compliance="approved")
        cls.reviewer = make_staff("compliance")
        cls.admin, _ = make_admin()
        pr = cls.osc.post("/v1/projects", {"title": "Horta comunitária do bairro", "summary": "Projeto para a campanha de doações.",
                                           "causes": ["educacao"], "territory": "BR-MT", "ods": [2], "beneficiaries_count": 40,
                                           "budget_total_cents": 2_000_000})
        assert pr.status == 201, pr
        cls.project = pr.json["id"]
        cls.slug = "horta-" + uuid.uuid4().hex[:8]
        r = cls.osc.post("/v1/campaigns", {"project_id": cls.project, "slug": cls.slug, "title": "Horta comunitária do bairro",
                                           "summary": "Arrecadação para sementes, ferramentas e oficinas com as famílias.",
                                           "target_cents": 500_000, "purpose": "Sementes, ferramentas e oficinas.",
                                           "contingency_policy": "Se a meta não for atingida, o valor vai para as oficinas.",
                                           "refund_policy": "Estorno pelo provedor até a confirmação do uso.", "show_backers": True})
        assert r.status == 201, r
        cls.campaign = r.json["id"]

    # ---------------------------------------------------------------- publicação
    def test_01_publishing_requires_four_eyes_and_verified_beneficiary(self):
        r = self.osc.patch(f"/v1/campaigns/{self.campaign}", {"status": "published"})
        self.assertEqual(r.status, 409, "o atalho legado não publica mais")
        self.assertEqual(self.osc.post(f"/v1/campaigns/{self.campaign}/publish").status, 422, "sem aprovação não publica")
        self.assertEqual(self.osc.post(f"/v1/campaigns/{self.campaign}/submit").status, 200)
        # quem criou não revisa: a criadora não tem o papel; e o revisor que é o criador seria recusado no serviço
        r = self.reviewer.post(f"/v1/admin/donation-campaigns/{self.campaign}/review", {"approve": True, "note": "Finalidade, contingência e reembolso claros."})
        self.assertEqual(r.status, 200, r.body)
        r = self.osc.post(f"/v1/campaigns/{self.campaign}/publish")
        self.assertEqual(r.status, 422, "aprovada mas beneficiário NÃO verificado: não vai ao ar")
        self.assertEqual(r.json["code"], "beneficiary_not_verified")
        r = self.reviewer.post(f"/v1/admin/beneficiaries/{self.osc.org_id}/verification",
                               {"status": "verified", "note": "Documentos conferidos no sandbox de teste.", "account_holder_matches": True})
        self.assertEqual(r.status, 200, r.body)
        # v0.35.0 (auditoria, KYC-03): uma pessoa só não basta — a verificação vale depois da confirmação de outra
        r2 = self.osc.post(f"/v1/campaigns/{self.campaign}/publish")
        self.assertEqual((r2.status, r2.json["code"]), (422, "beneficiary_not_verified"), "verificação sem segunda pessoa publicou")
        self.assertEqual(self.reviewer.post(f"/v1/admin/beneficiaries/{self.osc.org_id}/verification/{r.json['id']}/confirm").status, 403,
                         "quem verificou confirmou a si mesmo")
        self.assertEqual(make_staff("compliance").post(f"/v1/admin/beneficiaries/{self.osc.org_id}/verification/{r.json['id']}/confirm").status, 200)
        r = self.osc.post(f"/v1/campaigns/{self.campaign}/publish")
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(r.json["url"], f"https://impacto.teste/campanha/{self.slug}?v=1")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM campaigns WHERE id = $1", self.campaign), "published")

    def test_02_public_page_and_qr_point_to_the_canonical_url(self):
        anon = Client()
        r = anon.get(f"/v1/public/donation-campaigns/{self.slug}")
        self.assertEqual(r.status, 200, r.body)
        self.assertTrue(r.json["beneficiary"]["verified"])
        self.assertEqual(r.json["totals"]["gross_confirmed_cents"], 0)
        self.assertFalse(r.json["costs_disclosure"]["platform_fee_active"])
        self.assertEqual(r.json["costs_disclosure"]["platform_fee_bps"], 100)
        self.assertEqual(r.json["payment_mode"], "sandbox")
        self.assertIn("não recebe, não guarda e não repassa", " ".join(r.json["what_this_is_not"]))
        q = anon.get(f"/v1/public/donation-campaigns/{self.slug}/qr.svg")
        self.assertEqual(q.status, 200)
        self.assertIn(b"<svg", q.body)
        self.assertEqual(q.headers.get("x-impacto-qr-target"), f"https://impacto.teste/campanha/{self.slug}?v=1")
        self.assertNotIn(b"PIX", q.body, "o QR nunca carrega payload Pix")
        r = self.osc.post(f"/v1/campaigns/{self.campaign}/rotate-qr")
        self.assertEqual(r.json["qr_version"], 2)
        q = anon.get(f"/v1/public/donation-campaigns/{self.slug}/qr.svg")
        self.assertTrue(q.headers.get("x-impacto-qr-target", "").endswith("?v=2"))

    # ---------------------------------------------------------------- doação, webhook, razão
    def test_03_donation_is_confirmed_only_by_a_signed_provider_event_and_never_twice(self):
        anon = Client()
        r = anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate",
                      {"amount_cents": 10_000, "method": "pix", "donor_display": "Maria", "donor_email": "maria@teste.org", "idempotency_key": "k-" + uuid.uuid4().hex[:8]})
        self.assertEqual(r.status, 201, r.body)
        d = r.json
        self.assertEqual(d["status"], "awaiting_payment")
        self.assertTrue(d["is_simulated"])
        self.assertEqual(d["total_to_pay_cents"], 10_000)
        self.assertEqual(d["breakdown"]["platform_fee_cents"], 100, "1 % calculado (hipótese congelada)")
        self.assertEqual(d["platform_fee_due_cents"], 0, "regra inativa: nada é devido")
        self.assertEqual(d["breakdown"]["beneficiary_fund_cents"], 0, "a campanha não declarou reserva")
        self.assertIn("NAO-PAGAVEL", d["pix_payload"])
        # clique duplo com a mesma chave devolve a mesma doação
        key = "k-dup-" + uuid.uuid4().hex[:6]
        a = anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 700, "method": "pix", "idempotency_key": key}).json
        b = anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 700, "method": "pix", "idempotency_key": key}).json
        self.assertEqual(a["id"], b["id"], "clique duplo com a mesma chave devolve a mesma doação")
        with db_system() as c:
            charge = c.scalar("SELECT provider_charge_id FROM donations WHERE id = $1", d["id"])
            self.assertIsNone(c.scalar("SELECT 1 FROM donation_ledger_entries WHERE donation_id = $1", d["id"]), "nada no razão antes da confirmação")
            enc = c.scalar("SELECT donor_contact_enc FROM donations WHERE id = $1", d["id"])
            self.assertNotIn("maria@teste.org", enc or "", "contato cifrado")
        # assinatura adulterada: evento gravado como rejeitado, sem efeito
        bad = anon.request("POST", "/v1/webhooks/donations/sandbox", raw=json.dumps({"event_id": "evt-bad-1", "type": "payment.confirmed", "charge_id": charge, "amount_cents": 10_000}).encode(),
                           ctype="application/json", headers={"X-Impacto-Signature": "0" * 64})
        self.assertEqual(bad.status, 202)
        self.assertEqual(bad.json["status"], "rejected_signature")
        self.assertEqual(anon.get(f"/v1/public/donations/{d['id']}").json["status"], "awaiting_payment")
        # evento assinado confirma — uma vez
        ev = {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.confirmed", "charge_id": charge, "amount_cents": 10_000, "currency": "BRL",
              "payer": {"cpf": "000.000.000-00", "email": "maria@teste.org"}}
        ok = _signed(anon, "/v1/webhooks/donations/sandbox", ev)
        self.assertEqual(ok.status, 200, ok.body)
        self.assertEqual(ok.json["effect"], "confirmed")
        dup = _signed(anon, "/v1/webhooks/donations/sandbox", ev)
        self.assertEqual(dup.json["status"], "duplicate")
        st = anon.get(f"/v1/public/donations/{d['id']}").json
        self.assertEqual(st["status"], "confirmed")
        self.assertIsNotNone(st["receipt"])
        with db_system() as c:
            rows = c.query("SELECT account, side, amount_cents FROM donation_ledger_entries WHERE donation_id = $1 ORDER BY id", d["id"])
            self.assertEqual(sum(r["amount_cents"] for r in rows if r["side"] == "D"), sum(r["amount_cents"] for r in rows if r["side"] == "C"), "partidas fecham")
            self.assertEqual({r["account"] for r in rows}, {"donor_payment", "beneficiary_receivable", "platform_fee_accrued"})
            self.assertEqual(c.scalar("SELECT count(*) FROM donation_ledger_entries WHERE donation_id = $1 AND account = 'donor_payment'", d["id"]), 1, "nunca creditada duas vezes")
            red = c.scalar("SELECT payload_redacted::text FROM payment_provider_events WHERE event_id = $1", ev["event_id"])
            self.assertNotIn("maria@teste.org", red)
            self.assertNotIn("000.000.000-00", red)
        pub = anon.get(f"/v1/public/donation-campaigns/{self.slug}").json
        self.assertEqual(pub["totals"]["gross_confirmed_cents"], 10_000)
        self.assertEqual(pub["totals"]["platform_fee_accrued_cents"], 100)
        self.assertEqual(pub["totals"]["beneficiary_net_estimated_cents"], 9_900)
        self.assertEqual(pub["backers"][0]["name"], "Maria")
        rec = anon.get(f"/v1/public/donations/{d['id']}/receipt").json
        self.assertTrue(rec["number"].startswith("IMP-DOA-"))
        self.assertIn("NÃO é recibo para dedução fiscal", rec["what_this_is"])
        type(self).donation = d["id"]
        type(self).charge = charge

    def test_04_amount_mismatch_goes_to_review_not_to_confirmed(self):
        anon = Client()
        d = anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 5_000, "method": "pix"}).json
        with db_system() as c:
            charge = c.scalar("SELECT provider_charge_id FROM donations WHERE id = $1", d["id"])
        r = _signed(anon, "/v1/webhooks/donations/sandbox", {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.confirmed", "charge_id": charge, "amount_cents": 4_999})
        self.assertEqual(r.json["effect"], "under_review")
        self.assertEqual(anon.get(f"/v1/public/donations/{d['id']}").json["status"], "under_review")
        cases = self.reviewer.get("/v1/admin/donation-risk-cases").json["items"]
        case = next(x for x in cases if x["donation_id"] == d["id"])
        self.assertIn("amount_mismatch", case["reason_codes"])
        r = self.reviewer.post(f"/v1/admin/donation-risk-cases/{case['id']}/decide", {"action": "reject", "note": "Valor divergente; o doador será orientado a refazer."})
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(anon.get(f"/v1/public/donations/{d['id']}").json["status"], "cancelled")

    def test_05_anonymous_donor_never_appears_publicly_and_other_org_sees_nothing(self):
        anon = Client()
        d = anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 2_500, "method": "pix", "donor_display": "José Secreto", "public_anonymous": True}).json
        with db_system() as c:
            charge = c.scalar("SELECT provider_charge_id FROM donations WHERE id = $1", d["id"])
        _signed(anon, "/v1/webhooks/donations/sandbox", {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.confirmed", "charge_id": charge, "amount_cents": 2_500})
        pub = anon.get(f"/v1/public/donation-campaigns/{self.slug}").json
        names = [b["name"] for b in pub["backers"]]
        self.assertIn("Apoiador anônimo", names)
        self.assertNotIn("José Secreto", json.dumps(pub, ensure_ascii=False))
        self.assertIsNone(anon.get(f"/v1/public/donations/{d['id']}").json["donor_display"])
        self.assertEqual(self.outra.get(f"/v1/campaigns/{self.campaign}/accountability").status, 404)
        acc = self.osc.get(f"/v1/campaigns/{self.campaign}/accountability").json
        self.assertIsNone(next(x for x in acc["donations"] if x["id"] == d["id"])["donor_display"], "nem para a beneficiária, se anônimo")
        self.assertNotIn("donor_contact", json.dumps(acc))

    def test_06_refund_is_a_new_reversing_entry_and_voids_the_receipt(self):
        anon = Client()
        before = anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        r = _signed(anon, "/v1/webhooks/donations/sandbox", {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.refunded", "charge_id": self.charge})
        self.assertEqual(r.json["effect"], "refunded", r.body)
        self.assertEqual(anon.get(f"/v1/public/donations/{self.donation}").json["status"], "refunded")
        after = anon.get(f"/v1/public/donation-campaigns/{self.slug}").json["totals"]
        self.assertEqual(after["gross_confirmed_cents"], before["gross_confirmed_cents"], "o bruto confirmado não é editado")
        self.assertEqual(after["reversed_cents"], before["reversed_cents"] + 10_000)
        self.assertEqual(after["net_after_reversals_cents"], before["net_after_reversals_cents"] - 10_000)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM donation_ledger_entries WHERE donation_id = $1 AND reversal_of IS NOT NULL", self.donation), 3)
            self.assertEqual(c.scalar("SELECT status FROM donation_receipts WHERE donation_id = $1", self.donation), "voided")
            with self.assertRaises(Exception):
                c.run("DELETE FROM donation_ledger_entries WHERE donation_id = $1", self.donation)
        again = _signed(anon, "/v1/webhooks/donations/sandbox", {"event_id": "evt-" + uuid.uuid4().hex[:8], "type": "payment.refunded", "charge_id": self.charge})
        self.assertEqual(again.json["effect"], "already_reversed", "segundo estorno não reverte de novo")

    def test_07_ledger_and_reconciliation_for_staff(self):
        led = self.admin.get(f"/v1/admin/donation-ledger/{self.campaign}").json
        self.assertGreater(len(led["entries"]), 3)
        self.assertIn("não é dinheiro guardado pela plataforma", led["totals"]["label"])
        r = self.admin.post(f"/v1/admin/donation-campaigns/{self.campaign}/reconcile")
        self.assertEqual(r.status, 200, r.body)
        self.assertGreaterEqual(r.json["reconciled"], 1)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM donations WHERE campaign_id = $1 AND status = 'confirmed'", self.campaign), 0)

    def test_08_expenses_and_updates_feed_accountability(self):
        r = self.osc.post(f"/v1/campaigns/{self.campaign}/expenses", {"description": "Sementes", "budget_line": "insumos", "amount_cents": 1_200, "spent_on": "2026-10-09"})
        self.assertEqual(r.status, 201, r.body)
        self.assertEqual(r.json["evidence_status"], "declared")
        r = self.osc.post(f"/v1/campaigns/{self.campaign}/updates", {"title": "Primeira oficina", "body": "Vinte famílias participaram da oficina de plantio."})
        self.assertEqual(r.status, 201, r.body)
        acc = self.osc.get(f"/v1/campaigns/{self.campaign}/accountability").json
        self.assertEqual(acc["expenses_declared_cents"], 1_200)
        self.assertEqual(acc["expenses_validated_cents"], 0)
        pub = Client().get(f"/v1/public/donation-campaigns/{self.slug}").json
        self.assertEqual(pub["updates"][0]["title"], "Primeira oficina")
        self.assertEqual(pub["expenses"][0]["evidence_status"], "declared")

    def test_09_live_payment_flags_refuse_to_boot_without_an_adapter(self):
        from impacto import config as C
        with unittest.mock.patch.dict(os.environ, {"IMPACTO_ENV": "development", "DATABASE_URL": "postgresql://u@h/d", "STORAGE_PROVIDER": "local"}):
            s = C.load_settings()
        for flag in ("live_payment_provider_enabled", "split_enabled", "recurring_donations_enabled", "risk_hold_enabled"):
            with self.assertRaises(C.ConfigError, msg=flag):
                C.validate(replace(s, **{flag: True}))

    def test_11_admin_can_take_a_published_campaign_off_the_air_and_back_with_a_reason(self):
        anon = Client()
        r = self.reviewer.post(f"/v1/admin/donation-campaigns/{self.campaign}/suspend", {"note": "curto"})
        self.assertEqual(r.status, 422, "suspender sem justificativa não passa")
        r = self.reviewer.post(f"/v1/admin/donation-campaigns/{self.campaign}/suspend", {"note": "denúncia recebida; apurando a titularidade"})
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(r.json["status"], "under_review")
        self.assertEqual(anon.get(f"/v1/public/donation-campaigns/{self.slug}").status, 404, "em análise a página pública some")
        r = self.osc.post(f"/v1/campaigns/{self.campaign}/publish")
        self.assertEqual(r.status, 422, "a organização não devolve ao ar sozinha")
        r = self.reviewer.post(f"/v1/admin/donation-campaigns/{self.campaign}/suspend", {"note": "apuração encerrada sem achado", "reinstate": True})
        self.assertEqual(r.json["status"], "published")
        self.assertEqual(anon.get(f"/v1/public/donation-campaigns/{self.slug}").status, 200)

    def test_10_no_custody_no_balance_column_and_rules_inactive(self):
        with db_system() as c:
            cols = {r["column_name"] for r in c.query("SELECT column_name FROM information_schema.columns WHERE table_name IN ('campaigns','donations','organizations')")}
            self.assertFalse({"balance", "balance_cents", "wallet_balance", "saldo"} & cols)
            self.assertEqual(c.scalar("SELECT count(*) FROM monetization_rules WHERE active"), 0)
            self.assertEqual(c.scalar("SELECT legal_status FROM monetization_rules WHERE key = 'donation.platform_fee'"), "review_required")
            self.assertEqual(c.scalar("SELECT status FROM monetization_legal_cards WHERE rule_key = 'donation.beneficiary_fund'"), "yellow")
            with self.assertRaises(Exception, msg="is_simulated é derivada"):
                c.run("UPDATE donations SET is_simulated = false WHERE id = $1", self.donation)


if __name__ == "__main__":
    unittest.main()
