"""v0.27.0 — Camada econômica da operação: regra versionada, participação de autoria, aporte único direcionado
por chave PIX, instruções de repasse não custodiais, ledger econômico e quitação com reconhecimento.

Integridade econômica (FASE 29): R$ 100.000 → 95.000 projeto + 3.500 plataforma + 1.500 autoria; 3.500 + 1.500 = 5.000,
nunca 3.500 + 1.500 + 5.000. Centavos fecham com qualquer valor. GMV ≠ receita. Anti-bypass (FASE 28): percentual
não vem do cliente; proponente sem elegibilidade não recebe linha; transferência repetida é idempotente; quem paga
não confirma; contrato mudado depois do funding vira versão nova com estorno; cancelamento não gera receita.
"""
from __future__ import annotations

import unittest
from datetime import date

from tests.support import PASSWORD, db_system, last_signature_code, make_staff, new_account, server
from tests.test_v0140_trust import upload

OSC_IDEA = {"kind": "idea", "stage": "idea", "title": "Biblioteca itinerante para bairros sem acervo",
            "summary": "Ideia proposta por uma pessoa física: acervo móvel e rodas de leitura semanais em quatro bairros.",
            "problem": "Bairros sem biblioteca pública nem acervo infantil.", "approach": "Veículo adaptado, acervo e mediação de leitura.",
            "themes": ["educacao"], "ownership_type": "author", "authorization_publish": True}


def _d(dias: int) -> str:
    from datetime import timedelta
    return (date.today() + timedelta(days=dias)).isoformat()


class EconomyBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.funder = new_account("company", compliance="approved")
        cls.proponent = new_account("individual", compliance="approved", legal_name="Elisa Proponente")
        cls.staff = make_staff("billing")

    def _project(self, value=10_000_000, title="Projeto financiado v0.27"):
        pr = self.osc.post("/v1/projects", {"title": title, "summary": "Projeto para a camada econômica.", "causes": ["educacao"],
                                            "territory": "BR-MT", "ods": [4], "beneficiaries_count": 40, "budget_total_cents": value})
        self.assertEqual(pr.status, 201, pr)
        return pr.json["id"]

    def _participation(self, project_id, share_bps=10000, accept=True, publish=True):
        sid = self.proponent.post("/v1/solutions", OSC_IDEA)
        self.assertEqual(sid.status, 201, sid)
        pub = self.proponent.post(f"/v1/solutions/{sid.json['id']}/publish")
        self.assertEqual(pub.status, 200, pub)
        p = self.osc.post(f"/v1/projects/{project_id}/participations", {
            "proponent_org_id": self.proponent.org_id, "idea_ref_type": "solution", "idea_ref_id": sid.json["id"],
            "authorship_type": "author", "share_bps": share_bps,
            "contribution": "Propôs a ideia, estruturou o problema e participou da consolidação do projeto."})
        self.assertEqual(p.status, 201, p)
        if accept:
            a = self.proponent.post(f"/v1/participations/{p.json['id']}/accept")
            self.assertEqual(a.status, 200, a)
        if publish:
            self.osc.post(f"/v1/projects/{project_id}/budget-items", {"description": "Item", "quantity": 1, "unit_cost_cents": 100})
            self.assertEqual(self.osc.post(f"/v1/projects/{project_id}/publish").status, 200)
        return p.json["id"]

    def _agreement(self, project_id, value=10_000_000, with_proponent=True, **extra):
        doc = upload(self.osc, name="acordo.txt", body=b"Acordo de financiamento v0.27", doc_type="contrato")
        body = {"kind": "funding", "title": "Financiamento do projeto", "document_id": doc, "project_id": project_id,
                "value_cents": value, "review_days": 5, "calendar_type": "business", **extra}
        r = self.osc.post("/v1/signed-agreements", body)
        self.assertEqual(r.status, 201, r)
        aid = r.json["id"]
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/parties", {"org_id": self.funder.org_id, "role": "funder"}).status, 201)
        if with_proponent:
            self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/parties", {"org_id": self.proponent.org_id, "role": "proponent",
                                                                                     "required": False}).status, 201)
        m = self.osc.post(f"/v1/signed-agreements/{aid}/milestones", {"title": "Entrega única", "due_on": _d(30), "seq": 1, "amount_cents": value})
        self.assertEqual(m.status, 201, m)
        return aid, m.json["id"]

    def _pix(self, client, aid):
        d = client.get(f"/v1/signed-agreements/{aid}").json
        party = next(p for p in d["parties"] if p["org_id"] == client.org_id)
        kind, key = ("cnpj", "12345678000195") if client is self.osc else ("email", f"{client.org_id[:8]}@exemplo.test")
        r = client.put(f"/v1/signed-agreements/{aid}/parties/{party['id']}/pix", {"pix_key": key, "pix_key_type": kind})
        self.assertEqual(r.status, 200, r)
        return r.json

    def _sign(self, aid, *clients):
        for c in clients:
            self.assertEqual(c.post("/v1/signatures/challenge", {"subject_type": "agreement", "subject_id": aid}).status, 201)
            r = c.post(f"/v1/signed-agreements/{aid}/sign", {"statement": "Assino este acordo e me responsabilizo pelo combinado.",
                                                              "password": PASSWORD, "code": last_signature_code(c.email)})
            self.assertEqual(r.status, 200, r)
        return r.json["agreement_status"]

    def _activate(self, value=10_000_000, with_proponent=True, share_bps=10000):
        pid = self._project(value)
        part = self._participation(pid, share_bps=share_bps) if with_proponent else None
        aid, mid = self._agreement(pid, value, with_proponent=with_proponent)
        self._pix(self.osc, aid)
        if with_proponent:
            self._pix(self.proponent, aid)
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        # o proponente é parte OPCIONAL (assina se quiser, antes da vigência); as obrigatórias são executora e financiador
        if with_proponent:
            self._sign(aid, self.proponent)
        self.assertEqual(self._sign(aid, self.osc, self.funder), "active")
        return pid, part, aid, mid


class EconomicIntegrityTests(EconomyBase):
    def test_100k_becomes_95k_project_3500_platform_1500_proponent_and_the_layer_is_5000(self):
        pid, part, aid, mid = self._activate()
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        al = d["allocation"]
        self.assertEqual((al["gross_cents"], al["project_cents"], al["platform_fee_cents"], al["proponent_cents"]),
                         (10_000_000, 9_500_000, 350_000, 150_000))
        self.assertEqual(al["economic_layer_cents"], 500_000, "3.500 + 1.500 = 5.000 — e NUNCA 3.500 + 1.500 + 5.000")
        self.assertEqual(al["project_cents"] + al["platform_fee_cents"] + al["proponent_cents"], al["gross_cents"], "a soma fecha")
        self.assertEqual(al["fee_bps"], 350)
        self.assertEqual(al["proponent_bps"], 150)
        self.assertEqual(al["fee_mode"], "deducted", "aporte ÚNICO do financiador, direcionado a cada destinatário")
        self.assertEqual(d["terms"]["economic_rule_version"], "2027.02")     # v0.27.0: versão sem assinatura (ADR-341)
        kinds = {line["kind"]: line for line in al["lines"]}
        self.assertEqual(set(kinds), {"project", "platform_fee", "proponent"})
        self.assertEqual(kinds["proponent"]["to_org_id"], self.proponent.org_id)
        self.assertFalse(kinds["platform_fee"]["chargeable"], "regra jurídica desligada: a linha existe, não é exigível")
        # instruções: uma por linha, com a chave informada no contrato; a da plataforma aguarda a regra
        po = self.funder.get(f"/v1/signed-agreements/{aid}/payouts").json
        by = {p["line_kind"]: p for p in po["items"]}
        self.assertEqual(by["project"]["amount_cents"], 9_500_000)
        self.assertEqual(by["project"]["state"], "instruction_created")
        self.assertEqual(by["project"]["pix_key"], "12345678000195", "o financiador (quem paga) vê a chave inteira")
        self.assertEqual(by["proponent"]["amount_cents"], 150_000)
        self.assertEqual(by["platform_fee"]["state"], "awaiting_rule")
        self.assertIsNone(by["platform_fee"]["pix_key"], "chave da plataforma NÃO CONFIGURADA: nada é inventado")
        self.assertEqual(po["settlement"]["status"], "instructed")
        # o proponente vê a própria chave inteira, mas não a da OSC
        pp = self.proponent.get(f"/v1/signed-agreements/{aid}/payouts").json
        pb = {p["line_kind"]: p for p in pp["items"]}
        self.assertIsNotNone(pb["proponent"]["pix_key"])
        self.assertIsNone(pb["project"]["pix_key"])
        self.assertIn("•", pb["project"]["pix_key_masked"])

    def test_cents_close_for_awkward_amounts_and_rounding_goes_to_the_project(self):
        for value in (33_333, 999_999, 1, 12_345_67):
            pid, part, aid, mid = self._activate(value=value)
            al = self.osc.get(f"/v1/signed-agreements/{aid}").json["allocation"]
            self.assertEqual(al["project_cents"] + al["platform_fee_cents"] + al["proponent_cents"], value, value)
            self.assertEqual(al["platform_fee_cents"], (value * 350 + 5000) // 10000)
            self.assertEqual(al["proponent_cents"], (value * 150 + 5000) // 10000)

    def test_without_an_eligible_proponent_there_is_no_participation_line(self):
        pid, part, aid, mid = self._activate(with_proponent=False)
        al = self.osc.get(f"/v1/signed-agreements/{aid}").json["allocation"]
        self.assertEqual((al["project_cents"], al["platform_fee_cents"], al["proponent_cents"]), (9_650_000, 350_000, 0))
        self.assertEqual([line["kind"] for line in al["lines"]], ["project", "platform_fee"])

    def test_a_proponent_who_did_not_accept_gets_nothing_even_as_a_party(self):
        """Cenário C: reivindicar 1,5% sem elegibilidade."""
        pid = self._project()
        self._participation(pid, accept=False)       # proposta, não aceita
        aid, mid = self._agreement(pid, with_proponent=True)
        self._pix(self.osc, aid)
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self.assertEqual(self._sign(aid, self.osc, self.funder), "active")
        al = self.osc.get(f"/v1/signed-agreements/{aid}").json["allocation"]
        self.assertEqual(al["proponent_cents"], 0)
        self.assertEqual([line["kind"] for line in al["lines"]], ["project", "platform_fee"])
        rec = self.osc.get(f"/v1/signed-agreements/{aid}/allocation").json["recorded"]
        self.assertEqual(rec["proponent_cents"], 0)

    def test_multiple_proponents_split_the_participation_and_cents_still_close(self):
        """Cenário M: dois proponentes, 60/40."""
        pid = self._project()
        outro = new_account("individual", compliance="approved", legal_name="Outro Proponente")
        p1 = self._participation(pid, share_bps=6000, publish=False)
        sid = outro.post("/v1/solutions", OSC_IDEA).json["id"]
        self.assertEqual(outro.post(f"/v1/solutions/{sid}/publish").status, 200)
        p2 = self.osc.post(f"/v1/projects/{pid}/participations", {"proponent_org_id": outro.org_id, "idea_ref_type": "solution", "idea_ref_id": sid,
                                                                  "authorship_type": "coauthor", "share_bps": 4000,
                                                                  "contribution": "Coautoria na estruturação da abordagem e do orçamento."})
        self.assertEqual(p2.status, 201, p2)
        self.assertEqual(outro.post(f"/v1/participations/{p2.json['id']}/accept").status, 200)
        # frações acima de 100% são recusadas pelo banco
        terc = self.osc.post(f"/v1/projects/{pid}/participations", {"proponent_org_id": outro.org_id, "idea_ref_type": "solution", "idea_ref_id": sid,
                                                                    "authorship_type": "coauthor", "share_bps": 1,
                                                                    "contribution": "Tentativa de passar de cem por cento das frações."})
        self.assertEqual(terc.status, 422, terc)
        self.osc.post(f"/v1/projects/{pid}/budget-items", {"description": "Item", "quantity": 1, "unit_cost_cents": 100})
        self.assertEqual(self.osc.post(f"/v1/projects/{pid}/publish").status, 200)
        aid, mid = self._agreement(pid, value=10_000_001)
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/parties", {"org_id": outro.org_id, "role": "proponent", "required": False}).status, 201)
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self.assertEqual(self._sign(aid, self.osc, self.funder), "active")
        al = self.osc.get(f"/v1/signed-agreements/{aid}").json["allocation"]
        props = [line for line in al["lines"] if line["kind"] == "proponent"]
        self.assertEqual(len(props), 2)
        self.assertEqual(sum(x["cents"] for x in props), al["proponent_cents"])
        self.assertEqual(al["project_cents"] + al["platform_fee_cents"] + al["proponent_cents"], 10_000_001)
        self.assertEqual(sorted(x["cents"] for x in props), sorted([(150_000 * 6000 + 5000) // 10000, al["proponent_cents"] - (150_000 * 6000 + 5000) // 10000]))

    def test_gmv_is_not_revenue_in_the_economic_ledger(self):
        pid, part, aid, mid = self._activate()
        with db_system() as c:
            rows = c.query("SELECT kind, amount_cents FROM economic_events WHERE agreement_id = $1 ORDER BY seq", aid)
        kinds = {r["kind"]: r["amount_cents"] for r in rows}
        self.assertEqual(kinds.get("project_funds_instructed"), 9_500_000)
        self.assertEqual(kinds.get("platform_service_registered"), 350_000)
        self.assertEqual(kinds.get("proponent_participation_accrued"), 150_000)
        self.assertNotIn("platform_service_due", kinds, "regra desligada: nada é devido à plataforma")
        self.assertNotIn("platform_service_paid", kinds)
        # receita reconhecida da plataforma: zero — e o GMV de 100.000 não aparece em lugar nenhum como receita
        self.assertEqual(sum(r["amount_cents"] for r in rows if r["kind"] == "platform_service_paid"), 0)


class AntiBypassTests(EconomyBase):
    def test_D_the_client_cannot_set_the_fee_on_a_funding_agreement(self):
        pid = self._project()
        doc = upload(self.osc, name="acordo.txt", body=b"Acordo", doc_type="contrato")
        base = {"kind": "funding", "title": "Financiamento", "document_id": doc, "project_id": pid, "value_cents": 100}
        for bad in ({"platform_fee_bps": 0}, {"platform_fee_bps": 300}, {"fee_payer_role": "contractor"}):
            r = self.osc.post("/v1/signed-agreements", {**base, **bad})
            self.assertEqual(r.status, 422, (bad, r))
            self.assertIn("pricing_version", r.json["code"])
        ok = self.osc.post("/v1/signed-agreements", base)
        self.assertEqual(ok.status, 201, ok)
        aid = ok.json["id"]
        self.assertEqual(self.osc.patch(f"/v1/signed-agreements/{aid}", {"platform_fee_bps": 1}).status, 422)
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        self.assertEqual((d["terms"]["platform_fee_bps"], d["terms"]["fee_payer_role"], d["terms"]["fee_mode"]), (350, "funder", "deducted"))
        # a mesma regra, sob o mesmo valor, é a do catálogo
        rules = {r["key"]: r for r in self.osc.get("/v1/economic-rules").json["items"]}
        self.assertEqual(rules["funding.platform_service"]["bps"], 350)
        self.assertEqual(rules["funding.proponent_participation"]["bps"], 150)
        # a regra não é da plataforma em código: o catálogo versionado é imutável para a aplicação
        with db_system() as c, self.assertRaises(Exception):
            c.run("UPDATE economic_rules SET bps = 1 WHERE key = 'funding.platform_service'")

    def test_E_F_transfers_are_idempotent_and_only_the_recipient_confirms(self):
        pid, part, aid, mid = self._activate()
        po = {p["line_kind"]: p for p in self.funder.get(f"/v1/signed-agreements/{aid}/payouts").json["items"]}
        proj = po["project"]["id"]
        # a OSC (quem recebe) não registra transferência; o financiador registra
        self.assertEqual(self.osc.post(f"/v1/payouts/{proj}/transfers", {"amount_cents": 1, "reference": "X1-tentativa", "paid_on": _d(0)}).status, 403)
        t1 = self.funder.post(f"/v1/payouts/{proj}/transfers", {"amount_cents": 4_000_000, "reference": "E2E-0001", "paid_on": _d(0)})
        self.assertEqual(t1.status, 201, t1)
        dup = self.funder.post(f"/v1/payouts/{proj}/transfers", {"amount_cents": 4_000_000, "reference": "E2E-0001", "paid_on": _d(0)})
        self.assertEqual(dup.status, 201)
        self.assertTrue(dup.json["duplicate"], "mesma referência = mesma transferência (cenário E)")
        self.assertEqual(dup.json["id"], t1.json["id"])
        self.assertEqual(self.funder.post(f"/v1/payouts/{proj}/transfers", {"amount_cents": 6_000_001, "reference": "E2E-0002", "paid_on": _d(0)}).status, 422,
                         "a soma não passa do instruído")
        t2 = self.funder.post(f"/v1/payouts/{proj}/transfers", {"amount_cents": 5_500_000, "reference": "E2E-0002", "paid_on": _d(0)})
        self.assertEqual(t2.status, 201, t2)
        st = {p["line_kind"]: p for p in self.funder.get(f"/v1/signed-agreements/{aid}/payouts").json["items"]}["project"]
        self.assertEqual((st["state"], st["paid_cents"], st["confirmed_cents"]), ("payment_pending", 9_500_000, 0),
                         "registrar não é confirmar: nada está confirmado ainda")
        # quem paga NÃO confirma
        self.assertEqual(self.funder.post(f"/v1/payout-transfers/{t1.json['id']}/confirm").status, 403)
        c1 = self.osc.post(f"/v1/payout-transfers/{t1.json['id']}/confirm")
        self.assertEqual(c1.status, 200, c1)
        self.assertEqual(c1.json["payout_state"], "payment_pending", "4.000.000 de 9.500.000 confirmados: ainda pendente")
        again = self.osc.post(f"/v1/payout-transfers/{t1.json['id']}/confirm")
        self.assertTrue(again.json["duplicate"], "confirmar duas vezes não confirma mais (cenário F)")
        c2 = self.osc.post(f"/v1/payout-transfers/{t2.json['id']}/confirm")
        self.assertEqual(c2.status, 200, c2)
        self.assertEqual(c2.json["payout_state"], "confirmed")
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM economic_events WHERE payout_id = $1 AND kind = 'project_funds_confirmed'", proj)
            conf = c.scalar("SELECT confirmed_cents FROM allocation_payouts WHERE id = $1", proj)
        self.assertEqual((n, conf), (1, 9_500_000))

    def test_B_an_operation_is_not_settled_until_every_due_payout_is_confirmed_by_the_recipient(self):
        """Cenário B: a OSC 'recebeu por fora' — sem confirmação registrada não há quitação nem reconhecimento."""
        pid, part, aid, mid = self._activate()
        # entrega aceita, mas nenhum repasse confirmado
        self.assertEqual(self.osc.patch(f"/v1/signed-agreements/{aid}/milestones/{mid}", {"status": "delivered"}).status, 200)
        self.assertEqual(self.funder.patch(f"/v1/signed-agreements/{aid}/milestones/{mid}", {"status": "accepted"}).status, 200)
        st = self.osc.get(f"/v1/signed-agreements/{aid}/payouts").json["settlement"]
        self.assertTrue(st["complete"])
        self.assertFalse(st["settled"])
        self.assertEqual(self.osc.get(f"/v1/signed-agreements/{aid}").json["status"], "active")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM recognitions WHERE ref_id = $1::uuid", aid), 0)

    def test_golden_path_settles_the_operation_and_grants_recognition_only_then(self):
        pid, part, aid, mid = self._activate()
        po = {p["line_kind"]: p for p in self.funder.get(f"/v1/signed-agreements/{aid}/payouts").json["items"]}
        # financiador paga o projeto e o proponente (a plataforma aguarda a regra: não é devida)
        t = self.funder.post(f"/v1/payouts/{po['project']['id']}/transfers", {"amount_cents": 9_500_000, "reference": "PIX-A", "paid_on": _d(0)}).json
        self.assertEqual(self.osc.post(f"/v1/payout-transfers/{t['id']}/confirm").json["payout_state"], "confirmed")
        t2 = self.funder.post(f"/v1/payouts/{po['proponent']['id']}/transfers", {"amount_cents": 150_000, "reference": "PIX-B", "paid_on": _d(0)}).json
        self.assertEqual(self.osc.post(f"/v1/payout-transfers/{t2['id']}/confirm").status, 403, "a OSC não confirma o que é do proponente")
        c2 = self.proponent.post(f"/v1/payout-transfers/{t2['id']}/confirm")
        self.assertEqual(c2.status, 200, c2)
        self.assertEqual(c2.json["payout_state"], "confirmed")
        self.assertFalse(c2.json["operation_settled"], "sem a entrega aceita a operação não está quitada")
        self.assertEqual(self.proponent.get(f"/v1/participations/{part}").json["status"], "paid")
        self.assertEqual(self.osc.patch(f"/v1/signed-agreements/{aid}/milestones/{mid}", {"status": "delivered"}).status, 200)
        self.assertEqual(self.funder.patch(f"/v1/signed-agreements/{aid}/milestones/{mid}", {"status": "accepted"}).status, 200)
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        self.assertEqual(d["status"], "completed")
        self.assertTrue(d["settlement"]["settled"])
        with db_system() as c:
            kinds = sorted(r["kind"] for r in c.query("SELECT kind FROM recognitions WHERE ref_type = 'signed_agreement' AND ref_id = $1::uuid", aid))
            prop = c.scalar("SELECT count(*) FROM recognitions WHERE org_id = $1 AND kind = 'participation_paid'", self.proponent.org_id)
            settled = c.scalar("SELECT count(*) FROM economic_events WHERE agreement_id = $1 AND kind = 'operation_settled'", aid)
        self.assertEqual(kinds, ["funding_settled", "operation_settled"])
        self.assertEqual(prop, 1)
        self.assertEqual(settled, 1)
        # "o que o IMPACTO fez nesta operação" responde por registro
        v = self.funder.get(f"/v1/signed-agreements/{aid}/value").json
        self.assertEqual(len(v["items"]), 6)
        self.assertIn("NÃO MEDIDO", v["value_capture"]["ratio_note"])

    def test_G_changing_the_contract_after_funding_creates_a_new_version_and_reverses_open_instructions(self):
        pid, part, aid, mid = self._activate()
        doc2 = upload(self.osc, name="acordo-v2.txt", body=b"Acordo v2", doc_type="contrato")
        v2 = self.osc.post(f"/v1/signed-agreements/{aid}/new-version", {"document_id": doc2, "reason": "Prazo da entrega prorrogado em 60 dias.",
                                                                        "platform_fee_bps": 0})
        self.assertEqual(v2.status, 201, v2)
        d2 = self.osc.get(f"/v1/signed-agreements/{v2.json['id']}").json
        self.assertEqual(d2["terms"]["platform_fee_bps"], 350, "a regra congelada não muda por versão nova (nem a zero)")
        with db_system() as c:
            states = [r["state"] for r in c.query("SELECT state FROM allocation_payouts WHERE agreement_id = $1", aid)]
            rev = c.scalar("SELECT count(*) FROM economic_events WHERE agreement_id = $1 AND kind = 'reversal'", aid)
            part_status = c.scalar("SELECT status FROM proponent_participations WHERE id = $1", part)
        self.assertEqual(set(states), {"cancelled"})
        self.assertEqual(rev, 3, "cada instrução registrada tem o estorno de valor oposto")
        self.assertEqual(part_status, "consolidated", "a participação volta a consolidada: continua elegível para a versão nova")

    def test_H_O_cancelling_a_funded_operation_reverses_and_produces_no_revenue(self):
        pid, part, aid, mid = self._activate()
        self.assertEqual(self.proponent.post(f"/v1/signed-agreements/{aid}/cancel", {"reason": "tentativa de quem não pode"}).status, 403)
        r = self.funder.post(f"/v1/signed-agreements/{aid}/cancel", {"reason": "Projeto inviabilizado pela escola; cancelamento de comum acordo."})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["payouts_cancelled"], 3)
        with db_system() as c:
            total = c.scalar("SELECT coalesce(sum(amount_cents),0) FROM economic_events WHERE agreement_id = $1 AND kind <> 'operation_settled'", aid)
            paid = c.scalar("SELECT count(*) FROM economic_events WHERE agreement_id = $1 AND kind = 'platform_service_paid'", aid)
        self.assertEqual(total, 0, "registro + estorno = zero: nenhuma receita indevida")
        self.assertEqual(paid, 0)
        # cancelado não recebe transferência
        po = self.funder.get(f"/v1/signed-agreements/{aid}/payouts").json["items"]
        self.assertEqual(self.funder.post(f"/v1/payouts/{po[0]['id']}/transfers", {"amount_cents": 1, "reference": "XYZ", "paid_on": _d(0)}).status, 409)

    def test_I_J_rejected_transfer_puts_the_payout_in_dispute_and_the_platform_line_waits_for_the_rule(self):
        pid, part, aid, mid = self._activate()
        po = {p["line_kind"]: p for p in self.funder.get(f"/v1/signed-agreements/{aid}/payouts").json["items"]}
        t = self.funder.post(f"/v1/payouts/{po['project']['id']}/transfers", {"amount_cents": 9_500_000, "reference": "PIX-ERR", "paid_on": _d(0)}).json
        rj = self.osc.post(f"/v1/payout-transfers/{t['id']}/reject", {"reason": "O valor não chegou na conta informada."})
        self.assertEqual(rj.status, 200, rj)
        self.assertEqual(rj.json["payout_state"], "disputed")
        st = {p["line_kind"]: p for p in self.funder.get(f"/v1/signed-agreements/{aid}/payouts").json["items"]}
        self.assertEqual(st["project"]["paid_cents"], 0)
        # linha da plataforma: não exigível enquanto a regra jurídica estiver desligada
        self.assertEqual(self.funder.post(f"/v1/payouts/{po['platform_fee']['id']}/transfers", {"amount_cents": 1, "reference": "PLAT", "paid_on": _d(0)}).status, 409)

    def test_tenant_isolation_a_stranger_sees_no_payouts_and_cannot_touch_them(self):
        pid, part, aid, mid = self._activate()
        outro = new_account("company", compliance="approved")
        self.assertEqual(outro.get(f"/v1/signed-agreements/{aid}/payouts").status, 404, "nem sabe que o acordo existe")
        po = self.funder.get(f"/v1/signed-agreements/{aid}/payouts").json["items"]
        self.assertIn(outro.post(f"/v1/payouts/{po[0]['id']}/transfers", {"amount_cents": 1, "reference": "XYZ", "paid_on": _d(0)}).status, (403, 404))
        self.assertEqual(outro.get("/v1/participations").json["items"], [])


class PixKeyTests(EconomyBase):
    def test_only_the_party_sets_its_own_key_and_the_format_is_checked_by_the_database(self):
        pid = self._project()
        aid, mid = self._agreement(pid, with_proponent=False)
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        funder_party = next(p for p in d["parties"] if p["org_id"] == self.funder.org_id)
        self.assertEqual(self.osc.put(f"/v1/signed-agreements/{aid}/parties/{funder_party['id']}/pix", {"pix_key": "a@b.co", "pix_key_type": "email"}).status, 403)
        bad = self.funder.put(f"/v1/signed-agreements/{aid}/parties/{funder_party['id']}/pix", {"pix_key": "123", "pix_key_type": "cnpj"})
        self.assertIn(bad.status, (422,), bad)
        ok = self.funder.put(f"/v1/signed-agreements/{aid}/parties/{funder_party['id']}/pix", {"pix_key": "(65) 99999-1234", "pix_key_type": "phone"})
        self.assertEqual(ok.status, 200, ok)
        self.assertTrue(ok.json["pix_key_masked"].startswith("+55"))
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        fp = next(p for p in d["parties"] if p["org_id"] == self.funder.org_id)
        self.assertTrue(fp["pix_informed"])
        self.assertIsNone(fp["pix_key"], "a OSC não vê a chave do financiador (ela não paga a ele)")
