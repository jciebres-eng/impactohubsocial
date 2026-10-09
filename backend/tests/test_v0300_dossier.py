"""v0.30.0 — dossiê longitudinal do projeto (ADR-361) e mudança metodológica de indicador (ADR-362).

Prova por HTTP e PostgreSQL reais: o dossiê é composição do que está gravado (nenhum número sem origem), 'unknown' permanece,
cada bloco declara origem e atualidade, a OSC dona e o financiador com aporte veem o MESMO dossiê, outra organização e o
anônimo não veem; aceitar evidência/validar indicador não altera repasses; mudar o método de medição exige motivo, fica
registrado (append-only) e a série marca a descontinuidade.
"""
import unittest
from datetime import date

from impacto.db import pq
from tests.support import Client, db_system, new_account, server
from tests.test_v080 import funded_pair


class DossierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.pair = funded_pair()
        cls.osc, cls.fu, cls.pid = cls.pair["osc"], cls.pair["fu"], cls.pair["pid"]

    def test_the_dossier_composes_what_is_recorded_and_declares_gaps_sources_and_freshness(self):
        fresh = funded_pair()   # projeto sem evidência nem indicador: as lacunas têm de aparecer como lacunas
        d = fresh["osc"].get(f"/v1/projects/{fresh['pid']}/dossier").json
        self.assertEqual(d["engine"], "dossier@1.0")
        self.assertTrue(d["viewer_is_owner"])
        for block in ("readiness", "milestones", "evidences", "indicators", "funding", "diligence", "timeline"):
            self.assertIn("source", d[block], block)
            self.assertIn(d[block]["freshness"], ("recent", "stale", "unknown"), block)
        self.assertIn("evidences", d["gaps"])          # nada enviado ainda: lacuna, não zero de impacto
        self.assertIn("indicators", d["gaps"])
        self.assertIn(d["readiness"]["state"], ("ready", "in_progress", "not_started", "unknown"))
        self.assertEqual(d["readiness"]["met"] + d["readiness"]["unmet"] + d["readiness"]["unknown"], d["rules_version"]["readiness_criteria"])
        self.assertTrue(any("não é nota nem ranking" in x for x in d["what_this_is_not"]))
        self.assertEqual(d["funding"]["commitments_cents_by_status"].get("pledged"), 100000)
        self.assertEqual(d["funding"]["transfers"], {"registered": 0, "confirmed": 0})

    def test_funder_and_owner_see_the_same_dossier_and_strangers_see_nothing(self):
        mine = self.osc.get(f"/v1/projects/{self.pid}/dossier").json
        theirs = self.fu.get(f"/v1/projects/{self.pid}/dossier").json
        self.assertFalse(theirs["viewer_is_owner"])
        for k in ("readiness", "milestones", "evidences", "indicators", "funding", "diligence", "gaps"):
            a, b = dict(mine[k]) if isinstance(mine[k], dict) else mine[k], dict(theirs[k]) if isinstance(theirs[k], dict) else theirs[k]
            self.assertEqual(a, b, k)
        self.assertEqual(new_account("company").get(f"/v1/projects/{self.pid}/dossier").status, 404)
        self.assertEqual(Client().get(f"/v1/projects/{self.pid}/dossier").status, 401)

    def test_evidence_and_indicator_states_flow_into_the_dossier_without_moving_money(self):
        ev = self.osc.post(f"/v1/projects/{self.pid}/evidences", {"kind": "report", "title": "Relatório trimestral", "method": "document",
                                                                  "consent_basis": "not_personal"}).json["id"]
        cat = self.osc.get("/v1/indicators/catalog").json["items"]
        ind = next((x for x in cat if x.get("active", True)), cat[0])
        pi = self.osc.post(f"/v1/projects/{self.pid}/indicators", {"indicator_id": ind["id"], "method": "contagem mensal em lista de presença"}).json["id"]
        self.assertEqual(self.osc.post(f"/v1/project-indicators/{pi}/values", {"value": 12, "measured_on": date.today().isoformat(), "evidence_id": ev}).status, 201)
        d = self.osc.get(f"/v1/projects/{self.pid}/dossier").json
        self.assertEqual(d["evidences"]["classification"]["declared"], 1)
        self.assertEqual(d["evidences"]["quality"], {"with_document": 0, "method_known": 1, "consent_known": 1})
        s = next(x for x in d["indicators"]["series"] if x["project_indicator_id"] == pi)
        self.assertEqual((len(s["reported"]), len(s["validated"]), s["comparable"]), (1, 0, True))
        self.assertEqual(d["diligence"]["evidence_pending"], 1)
        self.assertEqual(d["diligence"]["values_awaiting_validation"], 1)
        with db_system() as x:
            before = x.scalar("SELECT count(*) FROM payout_transfers")
        self.assertEqual(self.fu.post(f"/v1/evidences/{ev}/review", {"status": "accepted", "note": "conferido"}).status, 200)
        d2 = self.fu.get(f"/v1/projects/{self.pid}/dossier").json
        self.assertEqual(d2["evidences"]["classification"]["validated"], 1)
        self.assertEqual(d2["evidences"]["freshness"], "recent")
        self.assertEqual(d2["funding"]["transfers"], {"registered": 0, "confirmed": 0})
        with db_system() as x:
            self.assertEqual(x.scalar("SELECT count(*) FROM payout_transfers"), before)

    def test_changing_the_measurement_method_requires_a_reason_is_logged_and_breaks_comparability(self):
        cat = self.osc.get("/v1/indicators/catalog").json["items"]
        pi = self.osc.post(f"/v1/projects/{self.pid}/indicators", {"indicator_id": cat[-1]["id"], "method": "amostra de 30 famílias"}).json["id"]
        self.assertEqual(self.osc.patch(f"/v1/projects/{self.pid}/indicators/{pi}/method", {"method": "censo completo", "reason": "curto"}).status, 422)
        with db_system() as x, self.assertRaises(pq.DatabaseError):
            x.run("UPDATE project_indicators SET method = 'sem motivo' WHERE id = $1", pi)   # o banco exige motivo, não só a API
        r = self.osc.patch(f"/v1/projects/{self.pid}/indicators/{pi}/method", {"method": "censo completo das famílias atendidas",
                                                                               "reason": "A amostra deixou de ser representativa após a expansão."})
        self.assertEqual(r.status, 200, r.json)
        self.assertEqual(len(r.json["changes"]), 1)
        self.assertEqual(r.json["changes"][0]["old_method"], "amostra de 30 famílias")
        self.assertIn("descontinuidade", r.json["notice"])
        s = next(x for x in self.fu.get(f"/v1/projects/{self.pid}/dossier").json["indicators"]["series"] if x["project_indicator_id"] == pi)
        self.assertFalse(s["comparable"])
        self.assertEqual(len(s["method_changes"]), 1)
        with db_system() as x, self.assertRaises(pq.DatabaseError):
            x.run("DELETE FROM indicator_method_changes WHERE project_indicator_id = $1", pi)
        self.assertEqual(new_account("osc").patch(f"/v1/projects/{self.pid}/indicators/{pi}/method", {"method": "outro", "reason": "outra organização"}).status, 404)
