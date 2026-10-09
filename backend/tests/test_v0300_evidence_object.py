"""v0.30.0 — evidência como objeto de primeira classe (ADR-360; migração 0070).

Prova, por HTTP e PostgreSQL reais:
* origem e uso (método, acesso, consentimento, retenção) são declarados e 'unknown' é lacuna visível, nunca "ok";
* rejeitar exige justificativa (API 422 e CHECK no banco); contestar exige motivo; só a executora contesta;
* a contestação vai para quem revisa, que decide com justificativa; a máquina de estados é do banco;
* substituir cria versão nova e deixa a anterior 'superseded' (terminal, legível, com histórico) — nada é apagado;
* histórico próprio append-only (evidence_events); hash do documento exposto com o aviso "integridade ≠ veracidade";
* outra organização não vê (404); aceitar evidência NÃO move dinheiro (payout_transfers intacto).
"""
import unittest

from impacto.db import pq
from tests.support import Client, db_system, new_account, server

from tests.test_v080 import funded_pair

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


class EvidenceObjectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.pair = funded_pair()
        cls.osc, cls.fu, cls.pid = cls.pair["osc"], cls.pair["fu"], cls.pair["pid"]

    def _evidence(self, **extra) -> str:
        body = {"kind": "report", "title": "Relatório de atividade", **extra}
        r = self.osc.post(f"/v1/projects/{self.pid}/evidences", body)
        self.assertEqual(r.status, 201, r.json)
        return r.json["id"]

    def test_origin_and_use_are_declared_and_unknown_is_a_visible_gap(self):
        ev = self._evidence()
        d = self.osc.get(f"/v1/evidences/{ev}").json
        self.assertEqual(d["method"], "unknown")
        self.assertEqual(d["consent_basis"], "unknown")
        self.assertEqual(d["access_level"], "parties")
        self.assertEqual(d["version"], 1)
        self.assertEqual(d["classification"], "declared")
        self.assertEqual(sorted(d["gaps"]), ["consent_basis", "document", "method"])
        self.assertIn("não a veracidade", d["notice"])
        self.assertEqual([h["to_status"] for h in d["history"]], ["submitted"])
        ev2 = self._evidence(method="direct_observation", consent_basis="not_personal", access_level="restricted", retention_class="accountability")
        d2 = self.osc.get(f"/v1/evidences/{ev2}").json
        self.assertEqual(d2["gaps"], ["document"])
        self.assertEqual(d2["retention_class"], "accountability")

    def test_document_hash_is_exposed_and_the_notice_says_what_it_proves(self):
        doc = self.osc.upload("/v1/documents", "foto.pdf", PDF, {"doc_type": "relatorio", "project_id": self.pid}).json
        ev = self._evidence(document_id=doc["id"], method="document")
        d = self.osc.get(f"/v1/evidences/{ev}").json
        self.assertRegex(d["document_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("document", d["gaps"])
        lst = self.osc.get(f"/v1/projects/{self.pid}/evidences").json
        self.assertIn("integridade", lst["notice"])
        self.assertTrue(any(x["id"] == ev and x["document_sha256"] == d["document_sha256"] for x in lst["items"]))

    def test_rejecting_requires_a_written_reason_in_the_api_and_in_the_database(self):
        ev = self._evidence()
        r = self.fu.post(f"/v1/evidences/{ev}/review", {"status": "rejected", "note": "curto"})
        self.assertEqual(r.status, 422, r.json)
        self.assertEqual(r.json["code"], "reason_required")
        with db_system() as d, self.assertRaises(pq.DatabaseError):
            d.run("UPDATE evidences SET status = 'rejected', review_note = NULL WHERE id = $1", ev)
        self.assertEqual(self.fu.post(f"/v1/evidences/{ev}/review", {"status": "rejected", "note": "Lista sem assinaturas nem data."}).status, 200)
        self.assertEqual(self.osc.get(f"/v1/evidences/{ev}").json["status"], "rejected")

    def test_only_the_executing_org_contests_and_only_a_rejected_evidence(self):
        ev = self._evidence()
        self.assertEqual(self.osc.post(f"/v1/evidences/{ev}/contest", {"reason": "Ainda não foi rejeitada, então não cabe"}).json["code"], "evidence_not_rejected")
        self.fu.post(f"/v1/evidences/{ev}/review", {"status": "rejected", "note": "Fotos sem data e sem local identificável."})
        self.assertEqual(self.fu.post(f"/v1/evidences/{ev}/contest", {"reason": "O financiador não contesta a própria revisão"}).status, 403)
        other = new_account("osc")
        self.assertEqual(other.post(f"/v1/evidences/{ev}/contest", {"reason": "Outra organização tentando contestar"}).status, 404)
        self.assertEqual(self.osc.post(f"/v1/evidences/{ev}/contest", {"reason": "curto"}).status, 422)
        r = self.osc.post(f"/v1/evidences/{ev}/contest", {"reason": "As fotos têm metadados EXIF com data e GPS; anexo em nova versão."})
        self.assertEqual(r.status, 200, r.json)
        d = self.osc.get(f"/v1/evidences/{ev}").json
        self.assertEqual(d["status"], "contested")
        self.assertEqual(d["classification"], "contested")
        self.assertIn("EXIF", d["contest_reason"])
        # a máquina de estados é do banco: de 'contested' só se vai a 'under_review' (ou 'superseded'), mesmo com privilégio de sistema
        with db_system() as d3, self.assertRaises(pq.DatabaseError):
            d3.run("UPDATE evidences SET status = 'accepted' WHERE id = $1", ev)
        with db_system() as d4, self.assertRaises(pq.DatabaseError):
            d4.run("UPDATE evidences SET status = 'rejected', review_note = 'salto inválido para o teste' WHERE id = $1", ev)

    def test_a_contest_is_decided_by_the_reviewer_with_a_reason_and_the_history_keeps_every_step(self):
        ev = self._evidence()
        self.fu.post(f"/v1/evidences/{ev}/review", {"status": "rejected", "note": "Relatório sem assinatura do responsável."})
        self.osc.post(f"/v1/evidences/{ev}/contest", {"reason": "A assinatura está na última página, digitalizada."})
        self.assertEqual(self.fu.post(f"/v1/evidences/{ev}/review", {"status": "needs_info"}).json["code"], "contest_needs_decision")
        self.assertEqual(self.fu.post(f"/v1/evidences/{ev}/review", {"status": "accepted", "note": "Conferido: assinatura na página 12."}).status, 200)
        d = self.osc.get(f"/v1/evidences/{ev}").json
        self.assertEqual(d["status"], "accepted")
        self.assertEqual([h["to_status"] for h in d["history"]], ["submitted", "rejected", "contested", "under_review", "accepted"])
        self.assertEqual(d["history"][2]["reason"], "A assinatura está na última página, digitalizada.")
        self.assertEqual(d["history"][-1]["reason"], "Conferido: assinatura na página 12.")
        with db_system() as x, self.assertRaises(pq.DatabaseError):
            x.run("DELETE FROM evidence_events WHERE evidence_id = $1", ev)   # histórico é append-only

    def test_replacing_creates_a_new_version_and_the_old_one_stays_readable_as_superseded(self):
        ev1 = self._evidence(title="Lista de presença (v1)")
        r = self.osc.post(f"/v1/projects/{self.pid}/evidences", {"kind": "attendance", "title": "Lista de presença (v2, com assinaturas)",
                                                                  "supersedes_id": ev1, "method": "document"})
        self.assertEqual(r.status, 201, r.json)
        ev2 = r.json["id"]
        d1, d2 = self.osc.get(f"/v1/evidences/{ev1}").json, self.osc.get(f"/v1/evidences/{ev2}").json
        self.assertEqual((d1["status"], d1["superseded_by"], d1["classification"]), ("superseded", ev2, "superseded"))
        self.assertEqual((d2["version"], d2["supersedes_id"]), (2, ev1))
        self.assertEqual(d2["history"][0]["reason"], "substitui evidência anterior")
        # substituída é terminal: não se revisa nem se substitui de novo
        self.assertEqual(self.fu.post(f"/v1/evidences/{ev1}/review", {"status": "accepted", "note": "tarde demais"}).json["code"], "evidence_superseded")
        self.assertEqual(self.osc.post(f"/v1/projects/{self.pid}/evidences", {"kind": "attendance", "title": "v3 errada", "supersedes_id": ev1}).json["code"],
                         "evidence_already_superseded")
        # conteúdo não se edita depois de enviado (gatilho)
        with db_system() as x, self.assertRaises(pq.DatabaseError):
            x.run("UPDATE evidences SET kind = 'photo' WHERE id = $1", ev2)

    def test_another_org_never_sees_the_evidence_and_accepting_moves_no_money(self):
        ev = self._evidence()
        self.assertEqual(new_account("company").get(f"/v1/evidences/{ev}").status, 404)
        self.assertEqual(Client().get(f"/v1/evidences/{ev}").status, 401)
        with db_system() as d:
            before = d.scalar("SELECT count(*) FROM payout_transfers")
        self.assertEqual(self.fu.post(f"/v1/evidences/{ev}/review", {"status": "accepted", "note": "ok"}).status, 200)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM payout_transfers"), before, "aceitar evidência não registra nem confirma repasse")
