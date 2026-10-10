"""v0.35.0 — correções da auditoria de segurança e integridade financeira (docs/security/AUDITORIA_SEGURANCA_FASE1.md).

Cada classe cita o ID do controle da matriz da auditoria. Os testes foram escritos para FALHAR no código da v0.34.0
(a falha de cada um está descrita na auditoria) e passar depois da correção. Todos usam PostgreSQL e HTTP reais e dados
sintéticos.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import Client, db_system, grant_premium, new_account, server, set_role

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def _project(osc: Client) -> str:
    r = osc.post("/v1/projects", {"title": "Projeto da diligência", "summary": "Resumo do projeto de teste",
                                  "territory": "BR-MT-5105259", "causes": ["educacao"], "beneficiaries_count": 10,
                                  "budget_total_cents": 500000})
    assert r.status == 201, r
    assert osc.post(f"/v1/projects/{r.json['id']}/publish").status == 200
    return r.json["id"]


def _upload(osc: Client, doc_type: str, title: str, **fields) -> str:
    r = osc.upload("/v1/documents", f"{doc_type}.pdf", PDF, {"doc_type": doc_type, "title": title, **fields})
    assert r.status == 201, r
    return r.json["id"]


def _diligence(osc: Client, funder: Client, pid: str) -> str:
    app = funder.post("/v1/applications/interest", {"project_id": pid})
    assert app.status in (200, 201), app
    aid = app.json["id"]
    assert osc.post(f"/v1/applications/{aid}/transition", {"to_status": "due_diligence"}).status == 200
    return aid


class DiligenceSeesOnlyInstitutionalDocumentsTests(unittest.TestCase):
    """FILE-07 — antes: financiador em diligência lia e via listado todo documento da OSC sem projeto (inclusive a
    exportação de dados e documentos de identidade) e continuava lendo depois de encerrada a candidatura."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc")
        grant_premium(cls.osc)
        cls.pid = _project(cls.osc)
        cls.estatuto = _upload(cls.osc, "estatuto_social", "Estatuto social")
        cls.interno = _upload(cls.osc, "outro", "Documento interno privado")
        cls.compartilhado = _upload(cls.osc, "outro", "Carta compartilhada com as partes", visibility="parties")
        cls.do_projeto = _upload(cls.osc, "cnd_federal", "CND do projeto", project_id=cls.pid)
        cls.dirigente = _upload(cls.osc, "documento_dirigente", "Documento pessoal da presidente")
        # documento anexado a uma verificação de identidade — mesmo com tipo institucional, nunca pela diligência
        ver = cls.osc.post("/v1/trust/identity/verifications", {"level": "document"})
        assert ver.status == 201, ver
        cls.identidade = _upload(cls.osc, "comprovante_endereco", "Comprovante de endereço da pessoa")
        att = cls.osc.post(f"/v1/trust/identity/verifications/{ver.json['id']}/documents",
                           {"document_id": cls.identidade, "kind": "proof_of_address"})
        assert att.status == 201, att
        exp = cls.osc.post("/v1/integrations/exports", {"dataset": "projects", "format": "csv"})
        assert exp.status == 201, exp
        cls.exportacao = exp.json["document_id"]
        cls.funder = new_account("company")
        cls.aid = _diligence(cls.osc, cls.funder, cls.pid)

    def _status(self, doc: str, quem: Client | None = None) -> int:
        return (quem or self.funder).post(f"/v1/documents/{doc}/download-url").status

    def test_institutional_project_and_explicitly_shared_documents_stay_available(self):
        for doc in (self.estatuto, self.do_projeto, self.compartilhado):
            self.assertEqual(self._status(doc), 200, doc)

    def test_private_export_personal_and_identity_documents_are_refused(self):
        for nome, doc in (("interno", self.interno), ("exportação de dados", self.exportacao),
                          ("documento de dirigente", self.dirigente), ("documento de identidade", self.identidade)):
            self.assertEqual(self._status(doc), 404, nome)
        listados = {d["id"] for d in self.funder.get(f"/v1/applications/{self.aid}").json.get("documents", [])}
        self.assertIn(self.estatuto, listados)
        for doc in (self.interno, self.exportacao, self.dirigente, self.identidade):
            self.assertNotIn(doc, listados, "a tela da candidatura listava o documento privado")

    def test_the_owner_still_sees_everything(self):
        for doc in (self.estatuto, self.interno, self.exportacao, self.dirigente, self.identidade):
            self.assertEqual(self._status(doc, self.osc), 200)

    def test_access_ends_when_the_application_closes(self):
        outro = new_account("company")
        aid = _diligence(self.osc, outro, self.pid)
        self.assertEqual(self._status(self.estatuto, outro), 200)
        with db_system() as c:      # o ciclo inteiro, pela máquina de estados do banco (não há atalho para 'closed')
            for estado in ("approved", "committed", "in_execution", "reporting", "closed"):
                c.run("UPDATE applications SET status = $2 WHERE id = $1", aid, estado)
        self.assertEqual(self._status(self.estatuto, outro), 404, "candidatura encerrada ainda abria os documentos")


class CommercialActsNeedTheOwnerTests(unittest.TestCase):
    """AUTHZ-02 — antes: aceitar oferta com autorização de cobrança, revogar a autorização e mudar o teto de gasto
    aceitavam qualquer membro da organização, até quem só tinha leitura."""

    def test_a_viewer_cannot_authorize_billing_revoke_or_change_the_spend_limit(self):
        from tests.test_v0210_offer import _oferta
        server()
        cli = new_account("osc")
        oferta = _oferta(cli)
        set_role(cli.user["id"], cli.org_id, "viewer")
        try:
            for metodo, rota, corpo in (
                    ("post", f"/v1/commercial/offers/{oferta['id']}/accept", {"consent_status": "authorized"}),
                    ("post", "/v1/commercial/consent/revoke", {"reason": "Teste de papel insuficiente"}),
                    ("put", "/v1/commercial/spend-limit", {"limit_cents": 10000, "action": "notify"})):
                r = getattr(cli, metodo)(rota, corpo)
                self.assertEqual((r.status, r.json["code"]), (403, "insufficient_role"), rota)
        finally:
            set_role(cli.user["id"], cli.org_id, "owner")
        r = cli.post(f"/v1/commercial/offers/{oferta['id']}/accept", {"consent_status": "authorized"})
        self.assertEqual(r.status, 200, r)

    def test_every_organization_write_route_declares_a_minimum_role(self):
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        sem_papel = sorted(f"{r.method} {r.path}" for r in ROUTES
                           if r.auth == "org" and r.method in ("POST", "PUT", "PATCH", "DELETE") and not r.min_role)
        self.assertEqual(sem_papel, [], "rota de escrita da organização sem papel mínimo: qualquer membro (até leitura) passa")


class PublicBackersNeverShowACivilNameWithoutOptInTests(unittest.TestCase):
    """ID-01 — antes: a página pública da campanha por cotas mostrava o nome civil de apoiador pessoa física (último
    recurso do `coalesce`), sem passar pela regra de opt-in de `org_display()`."""

    def test_an_individual_backer_appears_masked_until_they_opt_in(self):
        from tests.test_v0140_trust import _publish_campaign
        server()
        osc = new_account("osc", compliance="approved")
        pr = osc.post("/v1/projects", {"title": "Projeto com cotas", "summary": "Projeto para financiamento em cotas.",
                                       "causes": ["educacao"], "territory": "MT"})
        pid = pr.json["id"]
        q = osc.post("/v1/funding-quotas", {"project_id": pid, "label": "Cota", "quota_cents": 20000, "total_quotas": 5}).json["id"]
        self.assertEqual(osc.patch(f"/v1/funding-quotas/{q}", {"status": "open"}).status, 200)
        nome_civil = f"Maria Civil {uuid.uuid4().hex[:6]}"
        pessoa = new_account("individual", legal_name=nome_civil)
        p = pessoa.post(f"/v1/funding-quotas/{q}/pledges", {"quantity": 1})
        self.assertEqual(p.status, 201, p)
        with db_system() as c:
            c.run("UPDATE quota_pledges SET status = 'confirmed' WHERE id = $1", p.json["id"])
        slug = f"cotas-{uuid.uuid4().hex[:8]}"
        camp = osc.post("/v1/campaigns", {"project_id": pid, "slug": slug, "title": "Campanha com apoiadores",
                                          "summary": "Campanha com a lista de apoiadores visível.", "show_backers": True,
                                          "purpose": "Atividades.", "contingency_policy": "Sem a meta, vai para as atividades.",
                                          "refund_policy": "Estorno pelo provedor."})
        self.assertEqual(camp.status, 201, camp)
        _publish_campaign(osc, camp.json["id"])
        nomes = [b["name"] for b in Client().get(f"/v1/public/campaigns/{slug}").json["backers"]]
        self.assertNotIn(nome_civil, nomes, "nome civil exposto sem opt-in")
        self.assertIn("Apoiador pessoa física", nomes)
        with db_system() as c:
            c.run("INSERT INTO funder_profiles(org_id, public_name) VALUES ($1, true)"
                  " ON CONFLICT (org_id) DO UPDATE SET public_name = true", pessoa.org_id)
        nomes = [b["name"] for b in Client().get(f"/v1/public/campaigns/{slug}").json["backers"]]
        self.assertIn(nome_civil, nomes, "com opt-in, o nome aparece")


if __name__ == "__main__":
    unittest.main()


# ================================================================================================ lote B
def _fin_setup(cls):
    from tests.support import make_staff, reauth
    from tests.test_v0340_open_scenarios import SECRET, _publish
    st = server()
    st["state"].settings.payment_webhook_secret = SECRET
    cls.osc = new_account("osc", compliance="approved")
    cls.reviewer = make_staff("compliance")
    cls.finance = make_staff("finance")
    cls.ctl1, cls.ctl2 = make_staff("controller"), make_staff("controller")
    for s in (cls.finance, cls.ctl1, cls.ctl2):
        reauth(s)
    cls.anon = Client()
    cls.campaign, cls.slug = _publish(cls.osc, cls.reviewer)


def _donate(anon: Client, slug: str, cents: int, **body) -> dict:
    r = anon.post(f"/v1/public/donation-campaigns/{slug}/donate",
                  {"amount_cents": cents, "method": "pix", "idempotency_key": "k-" + uuid.uuid4().hex[:8], **body})
    assert r.status == 201, r
    return r.json


def _event(anon: Client, kind: str, charge: str, **extra):
    from tests.test_v0340_open_scenarios import _signed
    return _signed(anon, {"event_id": "evt-" + uuid.uuid4().hex[:10], "type": kind, "charge_id": charge, "currency": "BRL", **extra})


class ReconciliationProvesSomethingTests(unittest.TestCase):
    """PAY-07 — antes: a rota antiga marcava toda doação confirmada como conciliada sem comparar nada; sem extrato, o sistema
    conciliava contra os próprios eventos para qualquer provedor; o extrato manual (lista livre) conciliava na hora."""

    @classmethod
    def setUpClass(cls):
        _fin_setup(cls)

    def test_the_old_route_now_compares_and_does_not_reconcile_a_confirmation_without_signed_event(self):
        from tests.test_v0340_open_scenarios import _charge_of
        legit = _donate(self.anon, self.slug, 3_000)
        self.assertEqual(_event(self.anon, "payment.confirmed", _charge_of(legit["id"]), amount_cents=3_000).status, 200)
        forjada = _donate(self.anon, self.slug, 4_000)
        with db_system() as c:      # "confirmada" sem evento assinado (o que um erro ou uma adulteração produziria)
            c.run("UPDATE donations SET status = 'confirmed' WHERE id = $1", forjada["id"])
        r = self.finance.post(f"/v1/admin/donation-campaigns/{self.campaign}/reconcile")
        self.assertEqual(r.status, 200, r)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", legit["id"]), "reconciled")
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", forjada["id"]), "confirmed",
                             "a rota antiga conciliou uma confirmação sem evento assinado")
            self.assertEqual(c.scalar("SELECT kind FROM reconciliation_exceptions WHERE donation_id = $1 AND status = 'open'", forjada["id"]), "system_only")
        self.assertEqual(r.json["snapshot_source"], "sandbox_signed_events")
        self.assertFalse(r.json["independent_source"], "eventos do próprio sistema não são fonte independente")

    def test_a_real_provider_needs_a_statement(self):
        from tests.test_v0340_open_scenarios import _publish
        cid, slug = _publish(self.osc, self.reviewer)
        d = _donate(self.anon, slug, 2_000)
        with db_system() as c:
            c.run("UPDATE donations SET provider = 'asaas' WHERE id = $1", d["id"])
        r = self.finance.post(f"/v1/admin/reconciliation/campaigns/{cid}/run", {})
        self.assertEqual((r.status, r.json["code"]), (409, "provider_statement_required"))

    def test_a_manual_statement_reconciles_only_after_another_person_approves(self):
        from tests.test_v0340_open_scenarios import _charge_of, _publish
        cid, slug = _publish(self.osc, self.reviewer)
        d = _donate(self.anon, slug, 5_000)
        charge = _charge_of(d["id"])
        self.assertEqual(_event(self.anon, "payment.confirmed", charge, amount_cents=5_000).status, 200)
        bad = self.ctl1.post(f"/v1/admin/reconciliation/campaigns/{cid}/run", {"charges": [{"charge_id": charge, "valor": 1}]})
        self.assertEqual(bad.status, 422, "linha de extrato sem esquema foi aceita")
        r = self.ctl1.post(f"/v1/admin/reconciliation/campaigns/{cid}/run",
                           {"charges": [{"charge_id": charge, "amount_cents": 5_000, "confirmed": True}]})
        self.assertEqual(r.status, 200, r)
        self.assertEqual((r.json["reconciled"], r.json["awaiting_approval"]), (0, True))
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", d["id"]), "confirmed")
        same = self.ctl1.post(f"/v1/admin/reconciliation/runs/{r.json['run_id']}/approve")
        self.assertEqual((same.status, same.json["code"]), (403, "four_eyes"))
        ok = self.ctl2.post(f"/v1/admin/reconciliation/runs/{r.json['run_id']}/approve")
        self.assertEqual(ok.status, 200, ok)
        self.assertGreaterEqual(ok.json["reconciled"], 1)
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", d["id"]), "reconciled")
            with self.assertRaises(Exception) as err:
                c.run("UPDATE reconciliation_runs SET approved_by = run_by WHERE id = $1", r.json["run_id"])
            self.assertIn("recon_run_four_eyes", str(err.exception))


class ConfirmationAndLedgerIntegrityTests(unittest.TestCase):
    """PAY-05, PAY-03, PAY-02, PAY-12."""

    @classmethod
    def setUpClass(cls):
        _fin_setup(cls)

    def test_a_confirmation_without_amount_does_not_confirm(self):
        from tests.test_v0340_open_scenarios import _charge_of
        d = _donate(self.anon, self.slug, 2_500)
        r = _event(self.anon, "payment.confirmed", _charge_of(d["id"]))
        self.assertEqual(r.json["effect"], "under_review", "confirmação sem valor pulava a conferência")
        with db_system() as c:
            self.assertIn("amount_missing", c.scalar("SELECT reason_codes FROM donation_risk_cases WHERE donation_id = $1", d["id"]))

    def test_allow_after_review_posts_the_ledger_issues_the_receipt_and_keeps_the_difference_visible(self):
        from tests.test_v0340_open_scenarios import _balanced, _charge_of
        d = _donate(self.anon, self.slug, 6_000)
        self.assertEqual(_event(self.anon, "payment.confirmed", _charge_of(d["id"]), amount_cents=5_900).json["effect"], "under_review")
        with db_system() as c:
            case = c.scalar("SELECT risk_case_id::text FROM donations WHERE id = $1", d["id"])
        r = self.reviewer.post(f"/v1/admin/donation-risk-cases/{case}/decide", {"action": "allow", "note": "Diferença conferida com o provedor."})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["released"], [d["id"]])
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", d["id"]), "confirmed")
            self.assertTrue(c.scalar("SELECT count(*) FROM donation_ledger_entries WHERE donation_id = $1", d["id"]) >= 2,
                            "'permitir' confirmava sem lançar no razão")
            self.assertEqual(c.scalar("SELECT status FROM donation_receipts WHERE donation_id = $1", d["id"]), "issued")
            self.assertEqual(c.scalar("SELECT observed_cents FROM reconciliation_exceptions WHERE donation_id = $1 AND kind = 'amount_mismatch'",
                                      d["id"]), 5_900)
        self.assertTrue(_balanced(d["id"]))

    def test_a_refund_that_arrives_before_the_confirmation_is_applied_after_it(self):
        from tests.test_v0340_open_scenarios import _balanced, _charge_of
        d = _donate(self.anon, self.slug, 3_300)
        charge = _charge_of(d["id"])
        self.assertEqual(_event(self.anon, "payment.refunded", charge).json["effect"], "deferred", "estorno adiantado era ignorado para sempre")
        conf = _event(self.anon, "payment.confirmed", charge, amount_cents=3_300)
        self.assertEqual(conf.json["effect"], "confirmed")    # a resposta ao provedor é mínima; o efeito adiado aparece no estado
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT status FROM donations WHERE id = $1", d["id"]), "refunded")
        self.assertTrue(_balanced(d["id"]))

    def test_the_same_idempotency_key_with_another_amount_is_refused(self):
        key = "k-" + uuid.uuid4().hex[:8]
        a = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 1_500, "method": "pix", "idempotency_key": key})
        self.assertEqual(a.status, 201, a)
        again = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 1_500, "method": "pix", "idempotency_key": key})
        self.assertEqual((again.status, again.json["id"]), (201, a.json["id"]))
        other = self.anon.post(f"/v1/public/donation-campaigns/{self.slug}/donate", {"amount_cents": 9_900, "method": "pix", "idempotency_key": key})
        self.assertEqual((other.status, other.json["code"]), (409, "idempotency_conflict"), "chave repetida devolvia a doação de outro valor")

    def test_a_failing_event_is_not_retried_forever(self):
        from impacto.services import donations as DON
        from tests.test_v0340_open_scenarios import _charge_of
        d = _donate(self.anon, self.slug, 1_200)
        self.assertEqual(_event(self.anon, "payment.confirmed", _charge_of(d["id"]), amount_cents=1_200).status, 200)
        with db_system() as c:
            row = c.scalar("SELECT id FROM payment_provider_events WHERE donation_id = $1 ORDER BY id DESC LIMIT 1", d["id"])
            c.run("UPDATE payment_provider_events SET processing_status = 'failed', apply_attempts = $2 WHERE id = $1", row, DON.MAX_EVENT_ATTEMPTS)
            DON.reprocess_pending_events(c, older_than_seconds=0)
            self.assertEqual(c.scalar("SELECT processing_status FROM payment_provider_events WHERE id = $1", row), "failed",
                             "evento com o limite de tentativas foi reaplicado")
            DON.mark_event_failed(c, row_id=row, error="teste")
            self.assertEqual(c.scalar("SELECT apply_attempts FROM payment_provider_events WHERE id = $1", row), DON.MAX_EVENT_ATTEMPTS + 1)


class PublicMoneyStaysPublicTests(unittest.TestCase):
    """PAY-08 — antes: o doador declarava 'private' numa campanha de recurso público e o valor dele prevalecia."""

    @classmethod
    def setUpClass(cls):
        _fin_setup(cls)

    def test_a_donor_cannot_turn_public_money_private_nor_add_a_contribution_to_it(self):
        from tests.test_v0340_open_scenarios import _publish, _rule
        cid, slug = _publish(self.osc, self.reviewer, funding_source="public", public_instrument_ref="Termo de Fomento 7/2026")
        d = _donate(self.anon, slug, 4_000, funding_source="private")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT funding_source FROM donations WHERE id = $1", d["id"]), "public")
        _rule("donation.platform_contribution", True)
        try:
            r = self.anon.post(f"/v1/public/donation-campaigns/{slug}/donate",
                               {"amount_cents": 4_000, "method": "pix", "platform_contribution_cents": 500})
            self.assertEqual((r.status, r.json["code"]), (422, "contribution_public_funds"))
        finally:
            _rule("donation.platform_contribution", False)
        # a declaração pode endurecer: doador público numa campanha privada → público
        d2 = _donate(self.anon, self.slug, 4_000, funding_source="public")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT funding_source FROM donations WHERE id = $1", d2["id"]), "public")


class BeneficiaryVerificationIsRevocableAndFourEyesTests(unittest.TestCase):
    """KYC-03 — antes: 'rejected' depois de 'verified' não desfazia a verificação; 'verified' sem titularidade; documentos de
    evidência não conferidos; uma pessoa só; quem verifica podia ser da organização."""

    @classmethod
    def setUpClass(cls):
        _fin_setup(cls)

    def test_verified_needs_the_account_holder_and_own_evidence(self):
        org = self.osc.org_id
        r = self.reviewer.post(f"/v1/admin/beneficiaries/{org}/verification", {"status": "verified", "note": "Sem titularidade conferida."})
        self.assertEqual((r.status, r.json["code"]), (422, "account_holder_required"))
        alheio = new_account("osc")
        doc = _upload(alheio, "estatuto_social", "Estatuto de outra organização")
        r = self.reviewer.post(f"/v1/admin/beneficiaries/{org}/verification",
                               {"status": "under_review", "note": "Evidência de outra organização.", "evidence_document_ids": [doc]})
        self.assertEqual((r.status, r.json["code"]), (422, "evidence_invalid"))

    def test_a_reviewer_from_the_organization_has_a_conflict_of_interest(self):
        from tests.support import make_staff
        de_dentro = make_staff("compliance")
        with db_system() as c:
            c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'member')", de_dentro.user["id"], self.osc.org_id)
        r = de_dentro.post(f"/v1/admin/beneficiaries/{self.osc.org_id}/verification",
                           {"status": "verified", "note": "Verificando a própria organização.", "account_holder_matches": True})
        self.assertEqual((r.status, r.json["code"]), (403, "conflict_of_interest"))

    def test_a_later_rejection_revokes_takes_the_campaign_off_air_and_stops_donations(self):
        from tests.test_v0340_open_scenarios import _publish
        osc = new_account("osc", compliance="approved")
        cid, slug = _publish(osc, self.reviewer)
        _donate(self.anon, slug, 1_000)
        r = self.reviewer.post(f"/v1/admin/beneficiaries/{osc.org_id}/verification",
                               {"status": "rejected", "note": "Titularidade não confirmada pelo provedor."})
        self.assertEqual(r.status, 200, r)
        self.assertEqual(r.json["campaigns_paused"], 1)
        with db_system() as c:
            self.assertFalse(c.scalar("SELECT beneficiary_verified($1::uuid)", osc.org_id), "a recusa não desfez a verificação")
            self.assertEqual(c.scalar("SELECT status FROM campaigns WHERE id = $1", cid), "under_review")
        d = self.anon.post(f"/v1/public/donation-campaigns/{slug}/donate", {"amount_cents": 1_000, "method": "pix"})
        self.assertIn(d.status, (404, 409), "campanha de beneficiário recusado continuou recebendo")

    def test_the_database_refuses_self_confirmation(self):
        with db_system() as c:
            vid = c.scalar("SELECT id::text FROM org_kyb_verifications WHERE org_id = $1 AND status = 'verified' ORDER BY created_at DESC LIMIT 1",
                           self.osc.org_id)
            with self.assertRaises(Exception) as err:
                c.run("UPDATE org_kyb_verifications SET confirmed_by = reviewed_by WHERE id = $1", vid)
        self.assertIn("kyb_four_eyes", str(err.exception))
