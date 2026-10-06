"""Oferta comercial e aceite: ACESSO GRATUITO não é AUTORIZAÇÃO DE COBRANÇA.

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

from tests.support import db_system, new_account


def scalar(sql, *a):
    with db_system() as c:
        return c.scalar(sql, *a)


def _oferta(cli, **kw) -> dict:
    corpo = {"plan_key": "osc_premium", "interval": "month", "billing_frequency": "recurring",
             "payment_method": "card"}
    corpo.update(kw)
    r = cli.post("/v1/commercial/offers", corpo)
    assert r.status == 201, r.body
    return r.json


class OfferComesFromTheCatalogTests(unittest.TestCase):

    def test_a_caller_supplied_price_is_rejected_outright(self):
        # O schema não ignora o campo em silêncio: recusa o pedido inteiro. Ignorar seria aceitar a
        # requisição e devolver outro valor, deixando quem integra achando que mandou um preço
        # válido — o tipo de ambiguidade que vira disputa de fatura.
        cli = new_account("osc")
        r = cli.post("/v1/commercial/offers",
                     {"plan_key": "osc_premium", "interval": "month",
                      "billing_frequency": "recurring", "payment_method": "card",
                      "amount_cents": 1})
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["details"][0]["field"], "amount_cents")
        self.assertEqual(scalar("SELECT count(*) FROM commercial_offers WHERE org_id = $1",
                                cli.org_id), 0)

    def test_the_amount_comes_from_the_catalog(self):
        cli = new_account("osc")
        oferta = _oferta(cli)
        catalogo = scalar("SELECT amount_cents FROM plan_price_versions WHERE plan_key = 'osc_premium'"
                          " AND interval = 'month' AND effective_until IS NULL")
        self.assertEqual(oferta["amount_cents"], catalogo)

    def test_a_plan_without_a_published_price_is_refused_instead_of_invented(self):
        cli = new_account("company")
        r = cli.post("/v1/commercial/offers",
                     {"plan_key": "company_enterprise", "interval": "month",
                      "billing_frequency": "recurring", "payment_method": "card"})
        self.assertEqual(r.status, 409, r.body)
        self.assertEqual(r.json["code"], "price_not_defined")

    def test_the_offer_records_the_pricing_version_in_force(self):
        from impacto.services import free_period as FP
        cli = new_account("osc")
        self.assertEqual(_oferta(cli)["pricing_version"], FP.pricing_version())


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
        self.assertIn("primeira fatura", estado["on_expiry"])

    def test_the_acceptance_records_the_fourteen_fields_a_dispute_needs(self):
        cli = new_account("osc")
        of = _oferta(cli, payment_method="card", billing_frequency="recurring")
        cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        with db_system() as c:
            row = c.one("SELECT * FROM offer_acceptances WHERE org_id = $1", cli.org_id)
        for campo in ("offer_id", "pricing_version", "plan_key", "price_version_id",
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
                      " VALUES ($1,'subscription','card','stripe',79900,'BRL',false)",
                      cli.org_id)
        self.assertIn("sem autorização", str(e.exception))

    def test_a_charge_with_a_live_authorization_is_allowed(self):
        cli = new_account("osc")
        of = _oferta(cli)
        cli.post(f"/v1/commercial/offers/{of['id']}/accept", {"consent_status": "authorized"})
        with db_system() as c:
            c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                  " currency, is_simulated)"
                  " VALUES ($1,'subscription','card','stripe',79900,'BRL',false)", cli.org_id)
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
                      " VALUES ($1,'subscription','card','stripe',79900,'BRL',false)",
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
                      " VALUES ($1,'subscription','card','stripe',79900,'BRL',true)", cli.org_id)
        self.assertIn("sem autorização", str(e.exception))
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges WHERE org_id = $1",
                                cli.org_id), 0)

    def test_a_simulated_charge_is_exempt_because_it_debits_nobody(self):
        cli = new_account("osc")
        with db_system() as c:
            c.run("INSERT INTO platform_charges(org_id, kind, method, provider, amount_cents,"
                  " currency, is_simulated)"
                  " VALUES ($1,'subscription','card','sandbox',79900,'BRL',true)", cli.org_id)
        self.assertEqual(scalar("SELECT count(*) FROM platform_charges WHERE org_id = $1",
                                cli.org_id), 1)


class PaymentTermsTests(unittest.TestCase):
    """Parcelamento não é recorrência, e boleto parcelado é só para CNPJ."""

    def test_boleto_installments_require_a_cnpj(self):
        # `provider` é cadastrado sem CNPJ pelo arranjo de teste: é a pessoa física.
        pf = new_account("provider")
        r = pf.post("/v1/commercial/offers",
                    {"plan_key": "provider_premium", "interval": "month",
                     "billing_frequency": "installment", "payment_method": "boleto",
                     "installments": 6})
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "boleto_installments_require_cnpj")
        self.assertIn("pessoa jurídica", r.json["title"])

    def test_boleto_installments_are_accepted_for_a_cnpj(self):
        pj = new_account("osc")          # cadastrado com CNPJ
        r = pj.post("/v1/commercial/offers",
                    {"plan_key": "osc_premium", "interval": "month",
                     "billing_frequency": "installment", "payment_method": "boleto",
                     "installments": 6})
        self.assertEqual(r.status, 201, r.body)
        self.assertEqual(r.json["installments"], 6)
        self.assertEqual(r.json["billing_frequency"], "installment")

    def test_card_installments_do_not_require_a_cnpj(self):
        pf = new_account("provider")
        r = pf.post("/v1/commercial/offers",
                    {"plan_key": "provider_premium", "interval": "month",
                     "billing_frequency": "installment", "payment_method": "card",
                     "installments": 6})
        self.assertEqual(r.status, 201, r.body)

    def test_installments_are_not_recurrence(self):
        cli = new_account("osc")
        # Recorrência não aceita número de parcelas: são conceitos diferentes, e deixar os dois
        # juntos é o que faz alguém achar que comprou em 12x e descobrir que assinou 12 meses.
        r = cli.post("/v1/commercial/offers",
                     {"plan_key": "osc_premium", "interval": "month",
                      "billing_frequency": "recurring", "payment_method": "card",
                      "installments": 12})
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "installments_not_applicable")

    def test_installment_without_a_number_of_installments_is_refused(self):
        cli = new_account("osc")
        r = cli.post("/v1/commercial/offers",
                     {"plan_key": "osc_premium", "interval": "month",
                      "billing_frequency": "installment", "payment_method": "card"})
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "installments_required")

    def test_boleto_is_not_offered_as_recurring_because_it_has_no_direct_debit(self):
        cli = new_account("osc")
        r = cli.post("/v1/commercial/offers",
                     {"plan_key": "osc_premium", "interval": "month",
                      "billing_frequency": "recurring", "payment_method": "boleto"})
        self.assertEqual(r.status, 422, r.body)
        self.assertEqual(r.json["code"], "boleto_not_recurring")

    def test_boleto_installments_stop_at_twelve(self):
        pj = new_account("osc")
        r = pj.post("/v1/commercial/offers",
                    {"plan_key": "osc_premium", "interval": "month",
                     "billing_frequency": "installment", "payment_method": "boleto",
                     "installments": 24})
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
