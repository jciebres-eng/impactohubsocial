"""Contrato comercial (proposta e aceite): ACESSO GRATUITO não é AUTORIZAÇÃO DE COBRANÇA.

v0.27.0 (ADR-341): a oferta é a proposta de um CONTRATO avulso ou parcelado, montada pela administração
com alçada financeira (valor + motivo, auditado). `recurring` não existe mais; a organização que paga
não cria a própria oferta. Os testes de "o valor vem do catálogo de mensalidades" foram substituídos por
"o valor vem de quem tem alçada, nunca do cliente".

O QUE ESTES TESTES PROTEGEM

A auditoria desta rodada procurou, no repositório inteiro, qualquer distinção entre "aceitei usar
de graça" e "autorizo cobrar meu cartão". Não havia nenhuma. Enquanto for um aceite só, o fim de um
período gratuito vira cobrança por omissão — a cobrança surpresa, que nasce de modelagem e não de
má-fé.

Aqui são dois atos, e o teste central é `test_a_charge_without_authorization_is_refused_by_the_database`:
a garantia precisa valer contra TODO caminho de escrita, inclusive os que ainda não existem. Por
isso ela mora num gatilho, e por isso o teste a exercita pelo banco e não pela rota.
"""
from __future__ import annotations

import unittest

from tests.support import db_system, make_admin, new_account, server

_ADM = {}


def _adm():
    if "c" not in _ADM:
        server()
        _ADM["c"], _ = make_admin()
    return _ADM["c"]


def scalar(sql, *a):
    with db_system() as c:
        return c.scalar(sql, *a)


def _proposta(cli, **kw):
    """A administração propõe o contrato para a organização `cli` (valor + motivo); devolve a resposta crua."""
    corpo = {"org_id": cli.org_id, "plan_key": "osc_premium", "amount_cents": 120000,
             "amount_reason": "Implantação assistida — proposta comercial de teste",
             "billing_frequency": "one_time", "payment_method": "pix"}
    corpo.update(kw)
    return _adm().post("/v1/admin/commercial/offers", corpo)


def _oferta(cli, **kw) -> dict:
    r = _proposta(cli, **kw)
    assert r.status == 201, r.body
    return r.json


class OfferComesFromWhoHasAuthorityTests(unittest.TestCase):

    def test_the_paying_organization_cannot_write_its_own_offer(self):
        cli = new_account("osc")
        r = cli.post("/v1/commercial/offers", {"plan_key": "osc_premium", "billing_frequency": "one_time",
                                               "payment_method": "pix", "amount_cents": 1, "amount_reason": "eu mesma"})
        self.assertIn(r.status, (404, 405), r.body)      # a rota de criação não existe para a organização
        r = cli.post("/v1/admin/commercial/offers", {"org_id": cli.org_id, "plan_key": "osc_premium", "amount_cents": 1,
                                                     "amount_reason": "eu mesma", "billing_frequency": "one_time", "payment_method": "pix"})
        self.assertEqual(r.status, 403, r.body)
        self.assertEqual(scalar("SELECT count(*) FROM commercial_offers WHERE org_id = $1", cli.org_id), 0)

    def test_the_amount_needs_a_reason_and_is_audited(self):
        cli = new_account("osc")
        r = _proposta(cli, amount_reason="x")
        self.assertEqual(r.status, 422, r.body)
        of = _oferta(cli, amount_cents=250000)
        self.assertEqual(of["amount_cents"], 250000)
        self.assertEqual(scalar("SELECT amount_reason FROM commercial_offers WHERE id = $1", of["id"]),
                         "Implantação assistida — proposta comercial de teste")
        self.assertEqual(scalar("SELECT count(*) FROM audit_events WHERE action = 'commercial.offer_created' AND object_id::text = $1", of["id"]), 1)

    def test_recurring_is_not_a_billing_frequency_anymore(self):
        cli = new_account("osc")
        r = _proposta(cli, billing_frequency="recurring")
        self.assertEqual(r.status, 422, r.body)
        with self.assertRaises(Exception):
            with db_system() as c:
                c.run("INSERT INTO commercial_offers(org_id, pricing_version, plan_key, currency, amount_cents, billing_frequency, payment_method)"
                      " VALUES ($1,'t','osc_premium','BRL',1000,'recurring','card')", cli.org_id)

    def test_the_offer_records_the_pricing_version_in_force(self):
        from impacto.services import free_period as FP
        cli = new_account("osc")
        self.assertEqual(_oferta(cli)["pricing_version"], FP.pricing_version())

    def test_accepting_with_authorization_grants_the_bundle_and_revoking_removes_it(self):
        cli = new_account("osc")
        of = _oferta(cli, plan_key="osc_premium")
        self.assertNotIn("ai.assist.advanced", cli.get("/v1/me").json["entitlements"]["features"])
        cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        self.assertIn("ai.assist.advanced", cli.get("/v1/me").json["entitlements"]["features"])
        self.assertEqual(cli.get("/v1/billing").json["access"]["state"], "CONTRACTED")
        cli.post("/v1/commercial/consent/revoke", {"reason": "encerrando o contrato"})
        self.assertNotIn("ai.assist.advanced", cli.get("/v1/me").json["entitlements"]["features"])
        self.assertEqual(scalar("SELECT source FROM entitlement_grants WHERE org_id = $1 AND revoked_at IS NOT NULL", cli.org_id), "contract")


class FreeAccessIsNotAuthorizationTests(unittest.TestCase):

    def test_accepting_free_access_does_not_authorize_charging(self):
        cli = new_account("osc")
        of = _oferta(cli)
        r = cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "free_access"})
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(r.json["consent_status"], "free_access")
        estado = cli.get("/v1/commercial/state").json
        self.assertFalse(estado["charge_authorized"],
                         "aceitar acesso gratuito autorizou cobrança — é exatamente o defeito")
        self.assertFalse(estado["will_be_charged"])
        self.assertIn("Nenhuma cobrança", estado["on_expiry"])

    def test_authorizing_is_a_separate_explicit_act(self):
        cli = new_account("osc")
        of = _oferta(cli)
        r = cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        self.assertEqual(r.status, 200, r.body)
        estado = cli.get("/v1/commercial/state").json
        self.assertTrue(estado["charge_authorized"])
        self.assertIn("contrato", estado["on_expiry"])
        self.assertEqual(estado["state"], "CONTRACTED")

    def test_the_acceptance_records_the_fourteen_fields_a_dispute_needs(self):
        cli = new_account("osc")
        of = _oferta(cli, payment_method="card", billing_frequency="installment", installments=3)
        cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        with db_system() as c:
            row = c.one("SELECT * FROM offer_acceptances WHERE org_id = $1", cli.org_id)
        for campo in ("offer_id", "pricing_version", "plan_key",
                      "billing_frequency", "payment_method", "terms_version", "privacy_version",
                      "commercial_terms_version", "accepted_at", "accepted_by", "consent_status"):
            self.assertIsNotNone(row[campo], f"o aceite não gravou {campo}")
        # IP e user-agent vêm da requisição; o que o teste garante é que a COLUNA existe e é
        # alimentada pelo caminho real — não que o cliente de teste mande cabeçalho.
        self.assertIn("ip", row)
        self.assertIn("user_agent", row)

    def test_only_one_authorization_is_live_at_a_time(self):
        cli = new_account("osc")
        for _ in range(2):
            of = _oferta(cli)
            cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        vivos = scalar("SELECT count(*) FROM offer_acceptances WHERE org_id = $1"
                       " AND consent_status = 'authorized' AND revoked_at IS NULL", cli.org_id)
        self.assertEqual(vivos, 1, "duas autorizações vivas: a cobrança teria de escolher uma")
        # E a anterior continua registrada, revogada e com motivo — a prova não some.
        total = scalar("SELECT count(*) FROM offer_acceptances WHERE org_id = $1", cli.org_id)
        self.assertEqual(total, 2)

    def test_revoking_keeps_the_proof_and_stops_future_charges(self):
        cli = new_account("osc")
        of = _oferta(cli)
        cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        r = cli.post("/v1/commercial/consent/revoke", {"reason": "não quero mais ser cobrado"})
        self.assertEqual(r.status, 200, r.body)
        self.assertFalse(cli.get("/v1/commercial/state").json["charge_authorized"])
        row = scalar("SELECT revoke_reason FROM offer_acceptances WHERE org_id = $1", cli.org_id)
        self.assertEqual(row, "não quero mais ser cobrado")

    def test_revoking_without_an_authorization_says_so(self):
        cli = new_account("osc")
        r = cli.post("/v1/commercial/consent/revoke", {"reason": "nada a revogar"})
        self.assertEqual(r.status, 409, r.body)
        self.assertEqual(r.json["code"], "no_authorization")

    def test_the_acceptance_is_proof_and_cannot_be_rewritten(self):
        cli = new_account("osc")
        of = _oferta(cli)
        cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "free_access"})
        aid = scalar("SELECT id::text FROM offer_acceptances WHERE org_id = $1", cli.org_id)
        with self.assertRaises(Exception) as e:
            with db_system() as c:
                # A reescrita mais tentadora de todas: transformar um aceite de acesso gratuito em
                # autorização de cobrança depois do fato.
                c.run("UPDATE offer_acceptances SET consent_status = 'authorized' WHERE id = $1", aid)
        self.assertIn("não se altera", str(e.exception))


class NoChargeWithoutAuthorizationTests(unittest.TestCase):
    """A invariante mora no banco: ela vale contra caminhos de escrita que ainda não existem."""

    def test_a_charge_without_authorization_is_refused_by_the_database(self):
        cli = new_account("osc")
        with self.assertRaises(Exception) as e:
            with db_system() as c:
                c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                      " currency, is_simulated)"
                      " VALUES ($1,'one_off','card','stripe',120000,'BRL',false)",
                      cli.org_id)
        self.assertIn("sem autorização", str(e.exception))

    def test_a_charge_with_a_live_authorization_is_allowed(self):
        cli = new_account("osc")
        of = _oferta(cli)
        cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        with db_system() as c:
            c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                  " currency, is_simulated)"
                  " VALUES ($1,'one_off','card','stripe',120000,'BRL',false)", cli.org_id)
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges WHERE org_id = $1",
                                cli.org_id), 1)

    def test_revoking_blocks_the_next_charge(self):
        cli = new_account("osc")
        of = _oferta(cli)
        cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        cli.post("/v1/commercial/consent/revoke", {"reason": "cancelando a autorização"})
        with self.assertRaises(Exception) as e:
            with db_system() as c:
                c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                      " currency, is_simulated)"
                      " VALUES ($1,'one_off','card','stripe',120000,'BRL',false)",
                      cli.org_id)
        self.assertIn("sem autorização", str(e.exception))

    def test_declaring_a_charge_simulated_does_not_bypass_the_requirement(self):
        """A tentativa mais direta de contornar: informar `is_simulated = true` com provedor real.

        Os gatilhos BEFORE INSERT disparam em ordem alfabética do nome, e o de autorização vem ANTES
        do que deriva `is_simulated` do provedor. Se ele lesse a coluna, nesse instante ela ainda
        conteria o que o chamador mandou — e a cobrança passaria, para ser marcada como real logo
        depois. Ele pergunta ao provedor.
        """
        cli = new_account("osc")
        with self.assertRaises(Exception) as e:
            with db_system() as c:
                c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                      " currency, is_simulated)"
                      " VALUES ($1,'one_off','card','stripe',120000,'BRL',true)", cli.org_id)
        self.assertIn("sem autorização", str(e.exception))
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges WHERE org_id = $1",
                                cli.org_id), 0)

    def test_a_simulated_charge_is_exempt_because_it_debits_nobody(self):
        cli = new_account("osc")
        with db_system() as c:
            c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                  " currency, is_simulated)"
                  " VALUES ($1,'one_off','card','sandbox',120000,'BRL',true)", cli.org_id)
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges WHERE org_id = $1",
                                cli.org_id), 1)


class PaymentTermsTests(unittest.TestCase):
    """Parcelamento não é recorrência, e boleto parcelado é só para CNPJ."""

    def test_boleto_installments_require_a_cnpj(self):
        # `provider` é cadastrado sem CNPJ pelo arranjo de teste: é a pessoa física.
        pf = new_account("provider")
        r = _proposta(pf, plan_key="provider_premium", billing_frequency="installment", payment_method="boleto", installments=6)
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "boleto_installments_require_cnpj")
        self.assertIn("pessoa jurídica", r.json["title"])

    def test_boleto_installments_are_accepted_for_a_cnpj(self):
        pj = new_account("osc")          # cadastrado com CNPJ
        r = _proposta(pj, billing_frequency="installment", payment_method="boleto", installments=6)
        self.assertEqual(r.status, 201, r.body)
        self.assertEqual(r.json["installments"], 6)
        self.assertEqual(r.json["billing_frequency"], "installment")

    def test_card_installments_do_not_require_a_cnpj(self):
        pf = new_account("provider")
        r = _proposta(pf, plan_key="provider_premium", billing_frequency="installment", payment_method="card", installments=6)
        self.assertEqual(r.status, 201, r.body)

    def test_installments_do_not_apply_to_a_one_time_charge(self):
        cli = new_account("osc")
        r = _proposta(cli, billing_frequency="one_time", payment_method="card", installments=12)
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "installments_not_applicable")

    def test_installment_without_a_number_of_installments_is_refused(self):
        cli = new_account("osc")
        r = _proposta(cli, billing_frequency="installment", payment_method="card")
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "installments_required")

    def test_boleto_installments_stop_at_twelve(self):
        pj = new_account("osc")
        r = _proposta(pj, billing_frequency="installment", payment_method="boleto", installments=24)
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "installments_above_limit")

    def test_the_rule_is_enforced_in_the_backend_not_only_in_the_screen(self):
        # A tela é uma sugestão; a API é a porta. Chamando o serviço direto, sem passar por rota
        # nenhuma, a recusa tem de acontecer igual.
        from impacto.http import ApiError
        from impacto.services import offers as OF
        pf = new_account("provider")
        with db_system() as c:
            with self.assertRaises(ApiError) as e:
                OF.validate_payment_terms(c, org_id=pf.org_id, payment_method="boleto",
                                          billing_frequency="installment", installments=3)
        self.assertEqual(e.exception.code, "boleto_installments_require_cnpj")


class OfferLifecycleTests(unittest.TestCase):

    def test_an_offer_is_accepted_only_once(self):
        cli = new_account("osc")
        of = _oferta(cli)
        self.assertEqual(cli.post(f"/v1/commercial/offers/{of['id']}/accept",
                                  {"consent_status": "free_access"}).status, 200)
        r = cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "free_access"})
        self.assertEqual(r.status, 409, r.body)
        self.assertEqual(r.json["code"], "offer_not_open")

    def test_one_organization_cannot_accept_another_organizations_offer(self):
        dona = new_account("osc")
        intrusa = new_account("osc")
        of = _oferta(dona)
        r = intrusa.post(f"/v1/commercial/offers/{of['id']}/accept",
                         {"consent_status": "authorized"})
        self.assertEqual(r.status, 404, r.body)
        self.assertEqual(scalar("SELECT count(*) FROM offer_acceptances WHERE org_id = $1",
                                intrusa.org_id), 0)

    def test_an_organization_does_not_see_another_organizations_offers(self):
        dona = new_account("osc")
        _oferta(dona)
        outra = new_account("osc")
        self.assertEqual(outra.get("/v1/commercial/offers").json["items"], [])
