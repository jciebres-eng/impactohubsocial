"""Sonda (não entra no repositório): no código ANTERIOR ao lote B (2b44b58), com os helpers DAQUELE commit, mostra o
comportamento que o lote B corrigiu: KYC-03 (recusa posterior não revoga; uma pessoa só verifica), PAY-07 (rota antiga
concilia sem comparar), PAY-08 (doador muda a origem do recurso público para privada)."""
import hashlib, hmac, json, unittest, uuid
from tests.support import Client, db_system, make_staff, new_account, reauth, server
from tests.test_v0340_open_scenarios import SECRET, _charge_of, _publish


class Probe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        st["state"].settings.payment_webhook_secret = SECRET
        cls.osc = new_account("osc", compliance="approved")
        cls.rev = make_staff("compliance"); reauth(cls.rev)
        cls.fin = make_staff("finance"); reauth(cls.fin)
        cls.anon = Client()

    def test_kyc03_rejection_after_verified_does_not_revoke(self):
        cid, slug = _publish(self.osc, self.rev)
        with db_system() as c:
            print("verificado (uma pessoa só):", c.scalar("SELECT beneficiary_verified($1)", self.osc.org_id))
        r = self.rev.post(f"/v1/admin/beneficiaries/{self.osc.org_id}/verification", {"status": "rejected", "note": "Documento falso descoberto depois."})
        print("registrar recusa:", r.status)
        with db_system() as c:
            print("verificado DEPOIS da recusa:", c.scalar("SELECT beneficiary_verified($1)", self.osc.org_id))
            print("campanha:", c.scalar("SELECT status FROM campaigns WHERE id = $1", cid))
        d = self.anon.post(f"/v1/public/donation-campaigns/{slug}/donate", {"amount_cents": 5000, "method": "pix", "idempotency_key": "k-" + uuid.uuid4().hex[:6]})
        print("doação depois da recusa:", d.status)

    def test_pay07_legacy_reconcile_marks_without_comparing(self):
        cid, slug = _publish(self.osc, self.rev)
        d = self.anon.post(f"/v1/public/donation-campaigns/{slug}/donate", {"amount_cents": 5000, "method": "pix", "idempotency_key": "k-" + uuid.uuid4().hex[:6]}).json
        with db_system() as c:   # confirmação gravada direto, SEM evento assinado do provedor
            c.run("UPDATE donations SET status = 'confirmed', confirmed_at = now() WHERE id = $1", d["id"])
        r = self.fin.post(f"/v1/admin/donation-campaigns/{cid}/reconcile")
        print("rota antiga de conciliação:", r.status, json.dumps(r.json, ensure_ascii=False)[:300])
        with db_system() as c:
            print("doação sem evento ficou:", c.scalar("SELECT reconciliation_status FROM donations WHERE id = $1", d["id"]) if c.scalar("SELECT 1 FROM information_schema.columns WHERE table_name='donations' AND column_name='reconciliation_status'") else "(sem coluna)")

    def test_pay08_donor_turns_public_money_private(self):
        cid, slug = _publish(self.osc, self.rev, funding_source="public", public_instrument_ref="Termo de Fomento 7/2026")
        r = self.anon.post(f"/v1/public/donation-campaigns/{slug}/donate", {"amount_cents": 5000, "method": "pix", "funding_source": "private",
                                                                          "idempotency_key": "k-" + uuid.uuid4().hex[:6]})
        print("doação em campanha de recurso público declarada privada:", r.status)
        with db_system() as c:
            print("origem gravada na doação:", c.scalar("SELECT funding_source FROM donations WHERE id = $1", r.json["id"]))
