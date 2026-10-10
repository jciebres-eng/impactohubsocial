"""v0.35.0 — correções da auditoria de segurança e integridade financeira (docs/security/AUDITORIA_SEGURANCA_FASE1.md).

Cada classe cita o ID do controle da matriz da auditoria. Os testes foram escritos para FALHAR no código da v0.34.0
(a falha de cada um está descrita na auditoria) e passar depois da correção. Todos usam PostgreSQL e HTTP reais e dados
sintéticos.
"""
from __future__ import annotations

import json
import unittest
import uuid

from tests import test_v0270_economy as ECOT
from tests.support import Client, db_system, grant_premium, new_account, reauth, server, set_role

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
    st["state"].settings.donation_webhook_secret = SECRET
    cls.osc = new_account("osc", compliance="approved")
    cls.reviewer = make_staff("compliance")
    reauth(cls.reviewer)
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
        from tests.support import make_staff, reauth
        de_dentro = make_staff("compliance")
        reauth(de_dentro)
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


# ================================================================================================ lote C
class StaffWriteRoutesNeedFreshIdentityTests(unittest.TestCase):
    """AUTH-05 — antes: 68 rotas de escrita da administração sem permissão nomeada (mudar status de usuário, confirmar
    recebimento, decidir identidade…) não exigiam reautenticação; e compliance.write (verificar beneficiário, decidir caso
    de risco) também não."""

    def test_an_administrator_without_fresh_reauth_cannot_change_a_user_status(self):
        from tests.support import PASSWORD, fresh_totp, make_admin_without_reauth
        server()
        adm = make_admin_without_reauth()
        alvo = new_account("osc")
        r = adm.post(f"/v1/admin/users/{alvo.user['id']}/status", {"status": "disabled", "reason": "Teste de reautenticação"})
        self.assertEqual((r.status, r.json["code"]), (401, "step_up_required"), "escrita administrativa sem identidade confirmada")
        self.assertEqual(adm.post("/v1/auth/reauth", {"password": PASSWORD, "mfa_code": fresh_totp(adm.mfa_secret)}).status, 200)
        r = adm.post(f"/v1/admin/users/{alvo.user['id']}/status", {"status": "disabled", "reason": "Teste de reautenticação"})
        self.assertEqual(r.status, 200, r)

    def test_compliance_write_needs_fresh_identity(self):
        from tests.support import make_staff, reauth
        server()
        rev = make_staff("compliance")
        osc = new_account("osc")
        corpo = {"status": "verified", "note": "Cadastro conferido no teste.", "account_holder_matches": True}
        r = rev.post(f"/v1/admin/beneficiaries/{osc.org_id}/verification", corpo)
        self.assertEqual((r.status, r.json["code"]), (401, "step_up_required"))
        reauth(rev)
        self.assertEqual(rev.post(f"/v1/admin/beneficiaries/{osc.org_id}/verification", corpo).status, 200)


class StaffSecondFactorTests(unittest.TestCase):
    """AUTH-03/AUTH-04 — antes: quem tivesse a senha de um administrador sem MFA ativava o PRÓPRIO aplicativo e entrava;
    a equipe sem `is_platform_admin` podia desligar o MFA e a sessão seguia 'verificada'."""

    def test_staff_needs_the_email_code_to_enable_the_second_factor(self):
        from tests.support import fresh_totp, last_mfa_setup_code
        server()
        c = new_account("osc")
        with db_system() as d:
            d.run("UPDATE users SET is_platform_admin = true WHERE id = $1", c.user["id"])
        setup = c.post("/v1/auth/mfa/setup").json
        self.assertTrue(setup["email_code_required"])
        r = c.post("/v1/auth/mfa/enable", {"code": fresh_totp(setup["secret"])})
        self.assertEqual((r.status, r.json["code"]), (400, "invalid_email_code"), "só a senha bastava para cadastrar o TOTP do admin")
        r = c.post("/v1/auth/mfa/enable", {"code": fresh_totp(setup["secret"]), "email_code": "000000"})
        self.assertEqual(r.json["code"], "invalid_email_code")
        r = c.post("/v1/auth/mfa/enable", {"code": fresh_totp(setup["secret"]), "email_code": last_mfa_setup_code(c.email)})
        self.assertEqual(r.status, 200, r)

    def test_a_regular_person_does_not_need_the_email_code(self):
        from tests.support import fresh_totp
        server()
        c = new_account("osc")
        setup = c.post("/v1/auth/mfa/setup").json
        self.assertFalse(setup["email_code_required"])
        self.assertEqual(c.post("/v1/auth/mfa/enable", {"code": fresh_totp(setup["secret"])}).status, 200)

    def test_staff_cannot_disable_and_disabling_ends_other_sessions(self):
        from tests.support import PASSWORD, enable_mfa, fresh_totp, make_staff
        server()
        staff = make_staff("support")
        r = staff.post("/v1/auth/mfa/disable", {"password": PASSWORD, "code": fresh_totp(staff.mfa_secret)})
        self.assertEqual((r.status, r.json["code"]), (403, "mfa_required_for_admin"), "equipe desligava o MFA")
        pessoa = new_account("osc")
        segredo = enable_mfa(pessoa)
        outra = Client()
        r = outra.post("/v1/auth/login", {"email": pessoa.email, "password": PASSWORD})
        r = outra.post("/v1/auth/mfa/verify", {"mfa_token": r.json["mfa_token"], "code": fresh_totp(segredo)})
        self.assertEqual(r.status, 200, r)
        outra._absorb(r.json)
        self.assertEqual(outra.get("/v1/me").status, 200)
        self.assertEqual(pessoa.post("/v1/auth/mfa/disable", {"password": PASSWORD, "code": fresh_totp(segredo)}).status, 200)
        self.assertEqual(outra.get("/v1/me").status, 401, "desligar o MFA não encerrou a outra sessão")
        with db_system() as d:
            self.assertFalse(d.scalar("SELECT bool_or(mfa_verified) FROM sessions WHERE user_id = $1 AND revoked_at IS NULL", pessoa.user["id"]))


class SecondFactorBruteForceAndTrailTests(unittest.TestCase):
    """AUTH-02/AUTH-11/AUTH-09 — antes: a senha certa zerava o contador e cada desafio dava 5 tentativas de TOTP; falhas de
    MFA e de reautenticação não ficavam na trilha; trocar a senha não avisava o titular."""

    def test_wrong_codes_lock_the_account_across_challenges_and_are_audited(self):
        from impacto.services.auth import LOCK_AFTER
        from tests.support import PASSWORD, enable_mfa
        server()
        pessoa = new_account("osc")
        enable_mfa(pessoa)
        atacante = Client()
        erros = 0
        for _ in range(4):                     # desafios novos a cada 2 erros: antes, cada um zerava o jogo
            tok = atacante.post("/v1/auth/login", {"email": pessoa.email, "password": PASSWORD}).json.get("mfa_token")
            if not tok:
                break
            for _ in range(2):
                if atacante.post("/v1/auth/mfa/verify", {"mfa_token": tok, "code": "000000"}).status == 401:
                    erros += 1
        self.assertEqual(erros, LOCK_AFTER)
        r = atacante.post("/v1/auth/login", {"email": pessoa.email, "password": PASSWORD})
        self.assertEqual((r.status, r.json["code"]), (429, "account_locked"), "TOTP adivinhável sem limite por conta")
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM audit_events WHERE action = 'auth.mfa_failed' AND actor_user_id = $1",
                                      pessoa.user["id"]), LOCK_AFTER)

    def test_a_failed_reauth_is_audited(self):
        server()
        c = new_account("osc")
        r = c.post("/v1/auth/reauth", {"password": "senha-errada-de-proposito"})
        self.assertEqual(r.status, 401)
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM audit_events WHERE action = 'auth.step_up_failed' AND actor_user_id = $1",
                                      c.user["id"]), 1)

    def test_changing_the_password_warns_the_owner(self):
        from tests.support import PASSWORD, outbox_messages, subject_of
        server()
        c = new_account("osc")
        self.assertEqual(c.post("/v1/auth/change-password", {"current_password": PASSWORD, "new_password": "Outra-Senha-Forte-2026"}).status, 200)
        assuntos = [subject_of(m) for m in outbox_messages() if m["To"] == c.email]
        self.assertTrue(any("Aviso de segurança" in (s or "") for s in assuntos), "troca de senha sem aviso ao titular")


class ClientIpComesFromTheTrustedEndTests(unittest.TestCase):
    """AUTH-02 — antes: o IP dos limites era o PRIMEIRO valor do X-Forwarded-For, escrito por quem faz o pedido."""

    def _ip(self, headers: dict, **cfg) -> str:
        from dataclasses import replace
        from types import SimpleNamespace

        from impacto.http import Ctx
        settings = replace(server()["state"].settings, **cfg)
        req = SimpleNamespace(headers={k.lower(): v for k, v in headers.items()}, client=SimpleNamespace(host="10.0.0.9"))
        ctx = Ctx.__new__(Ctx)
        ctx.app, ctx.request = SimpleNamespace(settings=settings), req
        return ctx.ip

    def test_the_forged_leftmost_value_is_ignored(self):
        h = {"X-Forwarded-For": "6.6.6.6, 200.10.10.10"}
        self.assertEqual(self._ip(h, trust_proxy_headers=True, trusted_proxy_hops=1), "200.10.10.10")
        self.assertEqual(self._ip({"X-Forwarded-For": "6.6.6.6, 200.10.10.10, 172.70.0.1"}, trust_proxy_headers=True, trusted_proxy_hops=2),
                         "200.10.10.10")
        self.assertEqual(self._ip(h, trust_proxy_headers=True, client_ip_header="cf-connecting-ip"), "200.10.10.10",
                         "sem o cabeçalho da borda, volta ao X-Forwarded-For pela direita")
        self.assertEqual(self._ip({**h, "CF-Connecting-IP": "201.1.1.1"}, trust_proxy_headers=True, client_ip_header="cf-connecting-ip"), "201.1.1.1")
        self.assertEqual(self._ip(h, trust_proxy_headers=False), "10.0.0.9")

    def test_the_start_script_no_longer_trusts_every_forwarded_header(self):
        from tests.support import ROOT
        s = (ROOT / "backend" / "start_container.sh").read_text(encoding="utf-8")
        codigo = "\n".join(linha for linha in s.splitlines() if not linha.lstrip().startswith("#"))
        self.assertNotIn("--forwarded-allow-ips='*'", codigo)
        self.assertIn('FWD_IPS="${FORWARDED_ALLOW_IPS:-127.0.0.1}"', s)


class ProductionRefusesStaffWithoutSecondFactorTests(unittest.TestCase):
    def test_require_mfa_for_admins_false_is_refused_in_production(self):
        from tests.test_v0310_storage import _base

        from impacto import config as C
        s = _base(env="production", require_mfa_for_admins=False)
        with self.assertRaises(C.ConfigError) as err:
            C.validate(s)
        self.assertIn("REQUIRE_MFA_FOR_ADMINS", str(err.exception))


class RemunerationFourEyesTests(unittest.TestCase):
    """AUTHZ-06 — antes: a mesma pessoa com finance.approve registrava o recebimento e liquidava/reembolsava/dispensava."""

    def test_who_registered_the_receipt_cannot_settle_it(self):
        from impacto.http import ApiError
        from impacto.services import remuneration as REM
        from tests.support import make_staff
        server()
        osc = new_account("osc")
        a, b = make_staff("controller"), make_staff("controller")
        with db_system() as c:
            oid = c.scalar("INSERT INTO remuneration_obligations(org_id, source_kind, source_id, rule_key, basis_cents, amount_cents, state,"
                           " funding_source) VALUES ($1,'manual',$2,'donation.platform_fee',10000,300,'calculated','private') RETURNING id::text",
                           osc.org_id, str(uuid.uuid4()))
            REM._set(c, oid, "due", actor=None, trigger_code="manual_test")
            REM._set(c, oid, "received", actor=a.user["id"], received_cents=300, received_reference="TESTE-1")
            with self.assertRaises(ApiError) as err:
                REM.mark_settled(c, obligation_id=oid, actor=a.user["id"], note="Conferido com o extrato do banco.")
            self.assertEqual(err.exception.code, "four_eyes")
            self.assertEqual(REM.mark_settled(c, obligation_id=oid, actor=b.user["id"], note="Conferido com o extrato do banco.")["state"], "settled")


class CreateAdminNeverSilentlyPromotesTests(unittest.TestCase):
    """AUTH-04 — antes: create-admin num e-mail já cadastrado promovia a conta MANTENDO a senha de quem a cadastrou."""

    def test_an_existing_account_is_refused_and_explicit_promotion_replaces_the_password(self):
        from tests.support import PASSWORD
        from tests.test_v0231_cli import _cli
        server()
        pre = new_account("osc")          # quem pré-cadastrou o e-mail do futuro administrador
        r = _cli("create-admin", "--email", pre.email, "--name", "Futura Administradora")
        self.assertEqual(r.returncode, 1)
        with db_system() as c:
            self.assertFalse(c.scalar("SELECT is_platform_admin FROM users WHERE id = $1", pre.user["id"]), "promovida em silêncio")
        r = _cli("create-admin", "--email", pre.email, "--name", "Futura Administradora", "--promote-existing", senha="Senha-Nova-Do-Admin-2026")
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        self.assertEqual(Client().post("/v1/auth/login", {"email": pre.email, "password": PASSWORD}).status, 401,
                         "a senha de quem pré-cadastrou continuou valendo")
        self.assertEqual(pre.get("/v1/me").status, 401, "sessão anterior à promoção continuou aberta")


# ================================================================================================ lote D
class WebhookSignatureHasATimeWindowTests(unittest.TestCase):
    """PAY-01 — antes: a assinatura cobria só o corpo (evento capturado valia para sempre); o mesmo segredo servia aos dois
    webhooks; um evento SEM assinatura ocupava o `event_id` e fazia o verdadeiro chegar como "duplicado"; o sandbox valia em
    produção; havia um segredo de reserva fixo no código."""

    @classmethod
    def setUpClass(cls):
        _fin_setup(cls)

    def _body(self, donation: dict, event_id: str | None = None) -> bytes:
        from tests.test_v0340_open_scenarios import _charge_of
        return json.dumps({"event_id": event_id or "evt-" + uuid.uuid4().hex[:10], "type": "payment.confirmed",
                           "charge_id": _charge_of(donation["id"]), "amount_cents": donation["amount_cents"],
                           "currency": "BRL"}).encode()

    def _post(self, raw: bytes, sig: str):
        return self.anon.request("POST", "/v1/webhooks/donations/sandbox", raw=raw, ctype="application/json",
                                 headers={"X-Impacto-Signature": sig})

    def _status(self, donation_id: str) -> str:
        with db_system() as c:
            return c.scalar("SELECT status FROM donations WHERE id = $1", donation_id)

    def test_a_correctly_signed_but_old_event_has_no_effect(self):
        import time

        from impacto.integrations.events import sign
        from tests.test_v0340_open_scenarios import SECRET
        d = _donate(self.anon, self.slug, 5_000)
        raw = self._body(d)
        old, _ = sign(SECRET, raw, int(time.time()) - 600)        # assinatura certa, dez minutos atrás
        r = self._post(raw, old)
        self.assertEqual((r.status, r.json["status"]), (202, "rejected_signature"), r)
        self.assertNotEqual(self._status(d["id"]), "confirmed", "evento antigo (repetido) confirmou a doação")
        legacy = __import__("hmac").new(SECRET.encode(), raw, "sha256").hexdigest()   # formato antigo: só o corpo
        self.assertEqual(self._post(raw, legacy).json["status"], "rejected_signature")
        fresh, _ = sign(SECRET, raw)
        self.assertEqual(self._post(raw, fresh).status, 200)
        self.assertEqual(self._status(d["id"]), "confirmed")

    def test_an_unsigned_event_cannot_squat_the_event_id(self):
        from impacto.integrations.events import sign
        from tests.test_v0340_open_scenarios import SECRET
        d = _donate(self.anon, self.slug, 6_000)
        raw = self._body(d, event_id="evt-previsivel-" + uuid.uuid4().hex[:6])
        self.assertEqual(self._post(raw, "t=1,v1=" + "0" * 64).status, 202)     # chega primeiro, sem assinatura
        good, _ = sign(SECRET, raw)
        r = self._post(raw, good)
        self.assertEqual(r.status, 200, r)
        self.assertNotEqual(r.json["status"], "duplicate", "o evento verdadeiro foi tratado como repetido do falso")
        self.assertEqual(self._status(d["id"]), "confirmed")

    def test_each_webhook_has_its_own_secret(self):
        from impacto.integrations.events import sign
        from tests.test_v0340_open_scenarios import SECRET
        st = server()["state"].settings
        old_pay, old_don = st.payment_webhook_secret, st.donation_webhook_secret
        try:
            st.payment_webhook_secret = "segredo-do-webhook-de-pagamentos-" + uuid.uuid4().hex
            d = _donate(self.anon, self.slug, 7_000)
            raw = self._body(d)
            other, _ = sign(st.payment_webhook_secret, raw)
            self.assertEqual(self._post(raw, other).json["status"], "rejected_signature", "o segredo de pagamentos valeu nas doações")
            st.donation_webhook_secret = ""
            r = self._post(raw, other)
            self.assertEqual((r.status, r.json["code"]), (404, "webhook_not_configured"))
            st.donation_webhook_secret = st.payment_webhook_secret      # o mesmo segredo nos dois: recusado
            self.assertEqual(self._post(raw, other).status, 404)
            st.donation_webhook_secret = SECRET
            self.assertEqual(self._post(raw, sign(SECRET, raw)[0]).status, 200)
        finally:
            st.payment_webhook_secret, st.donation_webhook_secret = old_pay, old_don

    def test_an_unsigned_billing_event_does_not_squat_either(self):
        from impacto.economics import payments as PAY
        eid = "evt-billing-" + uuid.uuid4().hex[:8]
        with db_system() as c:
            fake = PAY.record_webhook(c, provider="pix", event_id=eid, event_type="charge.paid", payload={"event_id": eid}, signature_verified=False)
            real = PAY.record_webhook(c, provider="pix", event_id=eid, event_type="charge.paid", payload={"event_id": eid}, signature_verified=True)
        self.assertFalse(fake["applied"])
        self.assertFalse(real["duplicate"], "o evento assinado virou 'duplicado' do evento sem assinatura")
        self.assertTrue(real["applied"])

    def test_no_fixed_fallback_secret(self):
        from impacto.integrations.events import sign
        from impacto.services.donations import SandboxProvider
        import hashlib
        import hmac
        raw = b'{"event_id":"x"}'
        for guess in ("sandbox-sem-segredo", ""):
            # formato atual e formato antigo (HMAC só do corpo, que o código anterior aceitava com o segredo de reserva)
            for sig in (sign(guess or "a", raw)[0], hmac.new(guess.encode(), raw, hashlib.sha256).hexdigest()):
                self.assertFalse(SandboxProvider("").verify_signature({"x-impacto-signature": sig}, raw), (guess, sig[:12]))

    def test_the_sandbox_never_runs_in_production(self):
        from tests.test_v0310_storage import _base

        from impacto import config as C
        from impacto.http import ApiError
        from impacto.services import donations as DON
        prod = _base(env="production", payment_sandbox_enabled=True)
        with self.assertRaises(C.ConfigError) as err:
            C.validate(prod)
        self.assertIn("PAYMENT_SANDBOX_ENABLED", str(err.exception))
        self.assertFalse(DON.sandbox_allowed(prod), "produção com a variável ligada ainda simularia pagamento")
        with self.assertRaises(ApiError) as e2:
            DON.provider_for(prod)
        self.assertEqual(e2.exception.code, "provider_unavailable")
        self.assertFalse(DON.sandbox_allowed(_base(env="staging", payment_sandbox_enabled=False)))
        self.assertTrue(DON.sandbox_allowed(_base(env="staging", payment_sandbox_enabled=True)))
        self.assertTrue(DON.sandbox_allowed(_base(env="development")))

    def test_short_secrets_do_not_count_in_hardened_mode(self):
        from tests.test_v0310_storage import _base

        from impacto.services import donations as DON
        self.assertEqual(DON.webhook_secret(_base(env="staging", donation_webhook_secret="curto-demais"), "donation_webhook_secret"), "")
        longo = "x" * 40
        self.assertEqual(DON.webhook_secret(_base(env="staging", donation_webhook_secret=longo), "donation_webhook_secret"), longo)


class PixKeyIsProtectedTests(ECOT.EconomyBase):
    """PAY-09 — antes: a dona trocava a chave PIX de repasse sem confirmar identidade, sem aviso às outras partes, sem
    carência e mesmo depois de todos assinarem — quem tomasse a conta desviava o próximo repasse em silêncio."""

    def _osc_party(self, aid: str) -> str:
        d = self.osc.get(f"/v1/signed-agreements/{aid}").json
        return next(p["id"] for p in d["parties"] if p["org_id"] == self.osc.org_id)

    def _put(self, aid: str, key: str, kind: str = "cnpj"):
        return self.osc.put(f"/v1/signed-agreements/{aid}/parties/{self._osc_party(aid)}/pix", {"pix_key": key, "pix_key_type": kind})

    def _stale(self, client: Client):
        with db_system() as c:
            c.run("UPDATE sessions SET reauth_at = now() - interval '1 hour' WHERE user_id = $1", client.user["id"])

    def test_setting_the_key_needs_fresh_identity(self):
        aid, _ = self._agreement(self._project(), with_proponent=False)
        self._stale(self.osc)
        r = self._put(aid, "12345678000195")
        self.assertEqual((r.status, r.json["code"]), (401, "step_up_required"), r)
        reauth(self.osc)
        self.assertEqual(self._put(aid, "12345678000195").status, 200)

    def test_the_key_locks_after_the_first_signature_and_every_party_is_told(self):
        from tests.support import outbox_messages, subject_of
        aid, _ = self._agreement(self._project(), with_proponent=False)
        reauth(self.osc)
        self.assertEqual(self._put(aid, "12345678000195").status, 200)
        antes = len(outbox_messages())
        self.assertEqual(self._put(aid, "98765432000110").status, 200, "antes de qualquer assinatura a troca é permitida")
        avisos = [m for m in outbox_messages()[antes:] if "Chave PIX" in subject_of(m)]
        self.assertIn(self.funder.email, {m["To"] for m in avisos}, "a financiadora não soube da troca")
        self.assertIn(self.osc.email, {m["To"] for m in avisos}, "a dona da conta não soube da troca")
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM notifications WHERE org_id = $1 AND title LIKE 'Chave PIX%'", self.funder.org_id)
        self.assertGreaterEqual(n, 1)
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self._sign(aid, self.funder)                       # primeira assinatura
        r = self._put(aid, "11222333000181")
        self.assertEqual((r.status, r.json["code"]), (409, "pix_locked_after_signature"), r)
        with db_system() as c, self.assertRaises(Exception) as err:
            c.run("UPDATE signed_agreement_parties SET pix_key = '11222333000181' WHERE id = $1", self._osc_party(aid))
        self.assertIn("pix_locked_after_signature", str(err.exception) + str(getattr(err.exception, "constraint", "")))

    def test_a_key_first_given_after_a_signature_waits_before_the_payer_sees_it(self):
        aid, _ = self._agreement(self._project(), with_proponent=False)
        self.assertEqual(self.osc.post(f"/v1/signed-agreements/{aid}/publish").status, 200)
        self._sign(aid, self.funder)
        reauth(self.osc)
        r = self._put(aid, "12345678000195")
        self.assertEqual(r.status, 200, r)
        self.assertIsNotNone(r.json["cooling_until"])
        visto = next(p for p in self.funder.get(f"/v1/signed-agreements/{aid}").json["parties"] if p["org_id"] == self.osc.org_id)
        self.assertIsNone(visto["pix_key"], "quem paga viu a chave inteira durante a carência")
        self.assertTrue(visto["pix_key_masked"] and visto["pix_cooling_until"])
        dona = next(p for p in self.osc.get(f"/v1/signed-agreements/{aid}").json["parties"] if p["org_id"] == self.osc.org_id)
        self.assertEqual(dona["pix_key"], "12345678000195")


# ================================================================================================ lote E
class DatabaseCatalogHardeningTests(unittest.TestCase):
    """DB-03/04/05/06/07 — o catálogo do PostgreSQL depois de TODAS as migrações (as futuras também passam por aqui no CI)."""

    @classmethod
    def setUpClass(cls):
        from tests.support import owner_conn
        server()
        cls.own = owner_conn()

    @classmethod
    def tearDownClass(cls):
        cls.own.close()

    NOT_EXTENSION = "NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')"

    def test_every_security_definer_function_pins_the_search_path_with_pg_temp_last(self):
        rows = self.own.query(
            "SELECT p.oid::regprocedure::text AS f,"
            " (SELECT substr(c, 13) FROM unnest(p.proconfig) c WHERE c LIKE 'search_path=%') AS caminho"
            " FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
            f" WHERE n.nspname = 'public' AND p.prosecdef AND {self.NOT_EXTENSION}")
        self.assertGreater(len(rows), 50)
        bad = [r for r in rows if not r["caminho"] or [e.strip() for e in r["caminho"].split(",")][-1] != "pg_temp"
               or "public" not in [e.strip() for e in r["caminho"].split(",")]]
        self.assertEqual(bad, [], "função SECURITY DEFINER sem `search_path` fixo terminando em pg_temp")

    def test_a_temporary_table_cannot_change_what_a_definer_function_reads(self):
        """Antes: `identity_level` fixava só `public`; o esquema temporário era procurado PRIMEIRO, e uma tabela temporária
        criada pela conexão da aplicação fazia a função devolver 'biometric' para qualquer pessoa."""
        from impacto.db.pq import Connection
        from tests.support import APP_DSN
        app = Connection(APP_DSN)
        try:
            app.run("CREATE TEMP TABLE identity_verifications(user_id uuid, level text, status text, expires_at timestamptz)")
            app.run("INSERT INTO identity_verifications VALUES ('00000000-0000-0000-0000-000000000001','biometric','verified',NULL)")
            app.run("GRANT SELECT ON identity_verifications TO PUBLIC")
            self.assertEqual(app.scalar("SELECT identity_level('00000000-0000-0000-0000-000000000001')"), "none")
        finally:
            app.close()

    def test_no_function_of_the_schema_is_executable_by_public(self):
        bad = self.own.query("SELECT p.oid::regprocedure::text AS f FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
                             f" WHERE n.nspname = 'public' AND {self.NOT_EXTENSION}"
                             "   AND has_function_privilege('public', p.oid, 'EXECUTE') ORDER BY 1")
        self.assertEqual(bad, [], "função executável por PUBLIC (no Supabase, pelos papéis da API pública)")
        for f in ("app_org()", "app_priv()", "beneficiary_verified(uuid)", "identity_level(uuid)"):
            self.assertTrue(self.own.scalar("SELECT has_function_privilege('impacto_app', $1::regprocedure, 'EXECUTE')", f), f)

    def test_the_baselines_view_reapplies_row_level_security(self):
        opts = self.own.scalar("SELECT reloptions FROM pg_class WHERE relname = 'project_baselines_without_source'")
        self.assertIn("security_invoker=true", opts or [])

    def test_every_append_only_table_also_refuses_truncate(self):
        bad = self.own.query(
            "SELECT DISTINCT c.relname FROM pg_trigger g JOIN pg_class c ON c.oid = g.tgrelid JOIN pg_proc p ON p.oid = g.tgfoid"
            " WHERE p.proname = 'forbid_mutation' AND NOT g.tgisinternal"
            "   AND NOT EXISTS (SELECT 1 FROM pg_trigger x WHERE x.tgrelid = c.oid AND (x.tgtype & 32) <> 0) ORDER BY 1")
        self.assertEqual(bad, [], "tabela só-inclusão que ainda aceita TRUNCATE")
        with self.assertRaises(Exception) as err:
            self.own.run("TRUNCATE donation_ledger_entries")
        self.assertIn("TRUNCATE", str(err.exception))

    def test_global_grants_stay_minimal(self):
        """DB-06 — inventário global: a aplicação não trunca, não cria gatilho, não referencia, não cria objeto no esquema,
        não é dona de nada; PUBLIC não tem privilégio em tabela nenhuma."""
        extra = self.own.query("SELECT table_name, privilege_type FROM information_schema.role_table_grants"
                               " WHERE grantee = 'impacto_app' AND table_schema = 'public'"
                               "   AND privilege_type IN ('TRUNCATE', 'REFERENCES', 'TRIGGER') ORDER BY 1, 2")
        self.assertEqual(extra, [])
        self.assertEqual(self.own.query("SELECT table_name FROM information_schema.role_table_grants"
                                        " WHERE grantee = 'PUBLIC' AND table_schema = 'public'"), [])
        self.assertFalse(self.own.scalar("SELECT has_schema_privilege('impacto_app', 'public', 'CREATE')"))
        self.assertEqual(self.own.query("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                                        " WHERE n.nspname = 'public' AND pg_get_userbyid(c.relowner) = 'impacto_app'"), [])


# ================================================================================================ lote F
class PdfActiveContentIsFoundByStructureTests(unittest.TestCase):
    """FILE-02 — antes: a conferência procurava o TEXTO literal `/JavaScript` no arquivo; o mesmo nome escrito com escape
    hexadecimal (`/J#61vaScript`) ou guardado num fluxo de objetos comprimido passava."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc")

    def _objstm(self, inner: bytes, typ: bytes = b"/ObjStm", filt: bytes = b"/FlateDecode") -> bytes:
        import zlib
        comp = zlib.compress(inner)
        return (b"%PDF-1.5\n5 0 obj\n<< /Type " + typ + b" /N 1 /First 4 /Filter " + filt + b" /Length "
                + str(len(comp)).encode() + b" >>\nstream\n" + comp + b"\nendstream\nendobj\ntrailer<<>>\n%%EOF\n")

    def _send(self, data: bytes):
        return self.osc.upload("/v1/documents", "relatorio.pdf", data, {"doc_type": "relatorio_atividades", "title": "Relatório"})

    def test_hex_escaped_names_are_decoded(self):
        evil = b"%PDF-1.4\n1 0 obj<< /OpenAction << /S /J#61vaScript /J#53 (app.alert(1)) >> >>endobj\ntrailer<<>>\n%%EOF\n"
        r = self._send(evil)
        self.assertEqual((r.status, r.json.get("code")), (422, "active_content"), r)

    def test_javascript_inside_a_compressed_object_stream_is_found(self):
        inner = b"2 0 << /S /JavaScript /JS (app.alert(1)) >>"
        for typ, filt in ((b"/ObjStm", b"/FlateDecode"), (b"/O#62jStm", b"/Fla#74eDecode")):
            r = self._send(self._objstm(inner, typ, filt))
            self.assertEqual((r.status, r.json.get("code")), (422, "active_content"), (typ, r))

    def test_a_decompression_bomb_is_refused_instead_of_inflated(self):
        from impacto.services.documents import pdf_active_content
        self.assertIsNotNone(pdf_active_content(self._objstm(b"0" * (40 * 1024 * 1024))))

    def test_an_ordinary_pdf_still_goes_in(self):
        import io

        from pypdf import PdfWriter
        w = PdfWriter()
        w.add_blank_page(width=200, height=200)
        w.add_metadata({"/Title": "Relatório JSmith"})
        buf = io.BytesIO()
        w.write(buf)
        self.assertEqual(self._send(buf.getvalue()).status, 201)
        benign = self._objstm(b"2 0 << /Type /Page /Font << /JSmith 3 0 R >> >>")
        self.assertEqual(self._send(benign).status, 201, "nome parecido (JSmith) não é conteúdo ativo")


class AntivirusOutageQuarantinesInsteadOfFailingTests(unittest.TestCase):
    """FILE-03 (parte autorizada) — antes: clamd fora do ar derrubava o envio (500) e a fila de varredura inteira; e não havia
    teste do 409 `pending_scan`. A recusa de subir sem antivírus em produção NÃO foi feita (decisão sua nesta fase)."""

    class _Down:
        name = "clamd"

        def scan(self, data):
            raise ConnectionRefusedError("clamd fora do ar")

    def test_upload_goes_to_quarantine_and_download_waits(self):
        st = server()["state"]
        osc = new_account("osc")
        old_av, old_allow = st.antivirus, st.settings.allow_unscanned_downloads
        st.antivirus, st.settings.allow_unscanned_downloads = self._Down(), False
        try:
            r = osc.upload("/v1/documents", "estatuto.pdf", PDF, {"doc_type": "estatuto_social", "title": "Estatuto"})
            self.assertEqual(r.status, 201, r)
            self.assertEqual(r.json["status"], "pending_scan")
            d = osc.post(f"/v1/documents/{r.json['id']}/download-url")
            self.assertEqual((d.status, d.json.get("code")), (409, "pending_scan"), d)
        finally:
            st.antivirus, st.settings.allow_unscanned_downloads = old_av, old_allow

    def test_the_rescan_queue_survives_an_engine_error(self):
        from tests.test_v0301_pending_scans import _App

        from impacto import jobs
        app = _App([{"id": "a", "storage_key": "k-a"}, {"id": "b", "storage_key": "k-b"}], missing=set())
        app.antivirus = self._Down()
        res = jobs.pending_scans(app)
        self.assertEqual((res["scanned"], res["unreadable"]), (0, 2))
        self.assertEqual(app.updates, [], "nada é marcado como limpo sem ter sido lido pelo antivírus")


class AccountDeletionRemovesPersonalFilesTests(unittest.TestCase):
    """FILE-09 — antes: excluir a conta anonimizava a pessoa e deixava os documentos de identidade guardados para sempre."""

    def test_identity_and_personal_documents_go_institutional_ones_stay(self):
        from tests.support import PASSWORD
        st = server()["state"]
        osc = new_account("osc")
        req = osc.post("/v1/trust/identity/verifications", {"level": "document"})
        self.assertEqual(req.status, 201, req)
        ident = _upload(osc, "identidade", "RG da presidente")
        self.assertEqual(osc.post(f"/v1/trust/identity/verifications/{req.json['id']}/documents",
                                  {"document_id": ident, "kind": "official_id"}).status, 201)
        dirigente = _upload(osc, "documento_dirigente", "CPF da presidente")
        estatuto = _upload(osc, "estatuto_social", "Estatuto")
        with db_system() as c:
            keys = {r["id"]: r["storage_key"] for r in c.query("SELECT id::text AS id, storage_key FROM documents WHERE id = ANY($1::uuid[])",
                                                                 [ident, dirigente, estatuto])}
        r = osc.post("/v1/privacy/delete-account", {"password": PASSWORD, "confirm": True})
        self.assertEqual(r.status, 200, r)
        with db_system() as c:
            apagados = {r["id"] for r in c.query("SELECT id::text AS id FROM documents WHERE id = ANY($1::uuid[]) AND deleted_at IS NOT NULL",
                                                 [ident, dirigente, estatuto])}
        self.assertEqual(apagados, {ident, dirigente})
        for doc in (ident, dirigente):
            with self.assertRaises(Exception, msg="o objeto do arquivo pessoal continuou no armazenamento"):
                st.storage.get(keys[doc])
        self.assertTrue(st.storage.get(keys[estatuto]), "documento institucional da organização não sai com a conta")
