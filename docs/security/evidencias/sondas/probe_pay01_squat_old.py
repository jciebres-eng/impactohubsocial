"""Sonda (não entra no repositório): no código ANTERIOR (lote C, 4f8bcf6), com o formato antigo de assinatura (HMAC só do
corpo) e o segredo antigo (payment_webhook_secret), prova (1) repetição de evento antigo e (2) ocupação do event_id."""
import hashlib, hmac, json, unittest, uuid
from tests.support import Client, db_system, server
from tests.test_v0350_security import _fin_setup, _donate
from tests.test_v0340_open_scenarios import SECRET, _charge_of


class Probe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _fin_setup(cls)
        server()["state"].settings.payment_webhook_secret = SECRET

    def _post(self, raw, sig):
        return self.anon.request("POST", "/v1/webhooks/donations/sandbox", raw=raw, ctype="application/json", headers={"X-Impacto-Signature": sig})

    def test_squat(self):
        d = _donate(self.anon, self.slug, 6_000)
        raw = json.dumps({"event_id": "evt-previsivel-" + uuid.uuid4().hex[:6], "type": "payment.confirmed", "charge_id": _charge_of(d["id"]),
                          "amount_cents": 6_000, "currency": "BRL"}).encode()
        print("sem assinatura:", self._post(raw, "0" * 64).json)
        print("assinado:", self._post(raw, hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()).json)
        with db_system() as c:
            print("status da doação:", c.scalar("SELECT status FROM donations WHERE id = $1", d["id"]))

    def test_replay_has_no_time_limit(self):
        d = _donate(self.anon, self.slug, 5_000)
        raw = json.dumps({"event_id": "evt-" + uuid.uuid4().hex[:6], "type": "payment.confirmed", "charge_id": _charge_of(d["id"]),
                          "amount_cents": 5_000, "currency": "BRL"}).encode()
        print("assinatura sem carimbo de tempo (vale para sempre):", self._post(raw, hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()).json)
