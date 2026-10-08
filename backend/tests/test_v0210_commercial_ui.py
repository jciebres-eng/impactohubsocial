"""A interface comercial: lê o estado do backend e nunca refaz a conta dele.

A CLASSE DE DEFEITO QUE ESTE ARQUIVO IMPEDE

Quando duas camadas calculam a mesma coisa, elas divergem — e divergem na fronteira, que é
justamente quando a pessoa está olhando. A tela que mostra "faltam 3 dias" enquanto a cobrança
acha que faltam 2 não é um bug de arredondamento: é um cliente cobrado num dia em que a plataforma
dizia que ele não seria.

Então a regra é: `FREE_PERIOD_END`, dias restantes, estado comercial e valores vêm prontos do
servidor. O frontend formata; não decide.
"""
from __future__ import annotations

import re
import unittest

from tests.support import ROOT, new_account

WEB = ROOT / "web" / "src"


def _fontes(*padroes):
    for padrao in padroes:
        yield from WEB.rglob(padrao)


class TheFrontendDoesNotComputeCommercialDatesTests(unittest.TestCase):

    def test_no_screen_does_date_arithmetic_on_the_free_period(self):
        """Nenhuma tela soma, subtrai ou divide datas para descobrir quanto falta.

        A varredura procura as formas usuais: subtração de `getTime()`, divisão por 86400000 e
        `setMonth`/`setDate` perto de qualquer coisa chamada `free`/`period`/`trial`.
        """
        suspeitos = []
        for f in _fontes("*.tsx", "*.ts"):
            for n, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                if not re.search(r"free|period|trial|gratuit", linha, re.I):
                    continue
                if re.search(r"getTime\(\)\s*-|86400000|864e5|setMonth|setDate|addMonths", linha):
                    suspeitos.append(f"{f.relative_to(WEB)}:{n} · {linha.strip()[:80]}")
        self.assertEqual(suspeitos, [],
                         "a tela voltou a calcular prazo de gratuidade:\n  " + "\n  ".join(suspeitos))

    def test_the_banner_reads_the_days_remaining_from_the_server(self):
        fonte = (WEB / "pages" / "commercial.tsx").read_text(encoding="utf-8")
        self.assertIn("days_remaining", fonte)
        self.assertIn("free_period_end", fonte)
        self.assertIn("/v1/commercial/state", fonte)

    def test_the_commercial_timezone_is_named_where_dates_are_formatted(self):
        # Formatar sem fuso usa o do navegador, e aí 31/12 às 23h em São Paulo vira 01/01 para quem
        # está em Lisboa — a data da fronteira comercial apareceria errada exatamente nela.
        fonte = (WEB / "pages" / "commercial.tsx").read_text(encoding="utf-8")
        self.assertIn("America/Sao_Paulo", fonte)


class PublicPricingPageTests(unittest.TestCase):

    def test_there_is_a_public_pricing_route(self):
        app = (WEB / "app.tsx").read_text(encoding="utf-8")
        publicas = app[app.index("const PUBLIC"):app.index("const NAV")]
        self.assertIn('"/planos"', publicas,
                      "a página de preços não é pública: quem ainda não tem conta não a alcança")

    def test_the_pricing_page_reads_the_catalog_and_hardcodes_no_value(self):
        fonte = (WEB / "pages" / "commercial.tsx").read_text(encoding="utf-8")
        self.assertIn("/v1/plans", fonte)
        for valor in ("299", "799", "1490", "2500", "3500", "49,00", "R$ 49"):
            self.assertNotIn(valor, fonte, f"preço {valor} escrito na tela")

    def test_the_page_says_what_money_does_not_buy(self):
        fonte = (WEB / "pages" / "commercial.tsx").read_text(encoding="utf-8")
        for termo in ("Reputação", "selo", "evidência", "match"):
            self.assertIn(termo, fonte,
                          f"a página de preços não diz que {termo} não está à venda")

    def test_proposal_plans_show_the_floor_instead_of_a_blank(self):
        fonte = (WEB / "pages" / "commercial.tsx").read_text(encoding="utf-8")
        self.assertIn("quote_floor_cents", fonte)
        self.assertIn("sob proposta", fonte)


class CommercialScreensMatchTheApiTests(unittest.TestCase):
    """Os campos que a tela lê existem mesmo na resposta — a classe de defeito da v0.20.0."""

    def test_the_state_endpoint_returns_every_field_the_banner_uses(self):
        cli = new_account("osc")
        r = cli.get("/v1/commercial/state")
        self.assertEqual(r.status, 200, r.body)
        for campo in ("state", "free_period_end", "days_remaining", "charge_authorized",
                      "will_be_charged", "on_expiry", "periods"):
            self.assertIn(campo, r.json, f"a resposta não traz {campo}, que a faixa lê")

    def test_the_usage_endpoint_returns_every_field_the_table_uses(self):
        cli = new_account("osc")
        r = cli.get("/v1/commercial/usage")
        self.assertEqual(r.status, 200, r.body)
        for campo in ("metrics", "thresholds", "spend_limit", "spent_cents", "overage_policy"):
            self.assertIn(campo, r.json)
        for m in r.json["metrics"]:
            for campo in ("metric", "label", "used", "limit", "percent"):
                self.assertIn(campo, m)

    def test_every_commercial_state_the_backend_can_return_has_a_label(self):
        from impacto.services import free_period as FP
        fonte = (WEB / "pages" / "commercial.tsx").read_text(encoding="utf-8")
        rotulos = set(re.findall(r"^\s{2}([A-Z_]+):", fonte, re.M))
        faltando = set(FP.STATES) - rotulos
        self.assertEqual(faltando, set(),
                         f"estados sem rótulo na tela, apareceriam pelo código: {faltando}")

    def test_the_plans_endpoint_publishes_the_quote_floor(self):
        cli = new_account("company")
        r = cli.get("/v1/plans")
        self.assertEqual(r.status, 200, r.body)
        por_chave = {p["plan_key"]: p for p in r.json["items"]}
        self.assertEqual(por_chave["company_enterprise"]["quote_floor_cents"], 250000)
        self.assertEqual(por_chave["gov_institutional"]["quote_floor_cents"], 350000)
        self.assertIsNone(por_chave["osc_basic"]["quote_floor_cents"],
                          "plano gratuito não tem piso de proposta")
        self.assertEqual(r.json["pricing_version"], "2027.02")
        self.assertIsNone(r.json["subscription"])


class CommercialI18nTests(unittest.TestCase):

    NAMESPACES = ("billing", "pricing", "free_period", "commercial", "invoice", "payment", "usage")
    # v0.27.0 (ADR-341): `subscription`, `checkout` e `cancellation` saíram com a assinatura.
    RETIRED = ("subscription", "checkout", "cancellation")

    def setUp(self):
        import json
        self.i18n = json.loads((ROOT / "config" / "i18n.json").read_text(encoding="utf-8"))

    def test_all_commercial_namespaces_exist(self):
        for loc in ("pt-BR", "en", "es"):
            for ns in self.NAMESPACES:
                self.assertIn(ns, self.i18n["locales"][loc],
                              f"namespace {ns} não existe em {loc}")

    def test_the_retired_namespaces_are_gone_in_every_language(self):
        for loc in ("pt-BR", "en", "es"):
            for ns in self.RETIRED:
                self.assertNotIn(ns, self.i18n["locales"][loc], f"namespace de assinatura {ns} ainda existe em {loc}")

    def test_the_three_languages_have_exactly_the_same_keys(self):
        for ns in self.NAMESPACES:
            base = set(self.i18n["locales"]["pt-BR"][ns])
            for loc in ("en", "es"):
                outras = set(self.i18n["locales"][loc][ns])
                self.assertEqual(base, outras,
                                 f"{ns} diverge entre pt-BR e {loc}: "
                                 f"faltam {base - outras}, sobram {outras - base}")

    # Um valor igual à chave quase sempre é tradução esquecida. Quase: em inglês, a tradução
    # correta de `from` é "from". A exceção fica declarada, com motivo, em vez de o teste ser
    # afrouxado — assim a próxima tradução esquecida ainda falha.
    IGUAIS_DE_PROPOSITO = {("en", "pricing", "from"): "a palavra em inglês é a própria chave"}

    def test_no_translation_is_empty_or_a_copy_of_the_key(self):
        for loc in ("pt-BR", "en", "es"):
            for ns in self.NAMESPACES:
                for chave, valor in self.i18n["locales"][loc][ns].items():
                    self.assertTrue(valor.strip(), f"{loc}.{ns}.{chave} está vazia")
                    if (loc, ns, chave) in self.IGUAIS_DE_PROPOSITO:
                        continue
                    self.assertNotEqual(valor, chave, f"{loc}.{ns}.{chave} é a própria chave")

    def test_the_declared_exceptions_are_still_real(self):
        # Uma lista de exceções que ninguém revisa vira um buraco. Se a tradução deixar de ser igual
        # à chave, a exceção deixa de ser necessária e sai da lista.
        for (loc, ns, chave), motivo in self.IGUAIS_DE_PROPOSITO.items():
            self.assertEqual(self.i18n["locales"][loc][ns][chave], chave,
                             f"{loc}.{ns}.{chave} não é mais igual à chave: remova a exceção "
                             f"({motivo})")

    def test_the_key_that_explains_the_two_acts_exists_in_every_language(self):
        # A frase que o produto inteiro protege precisa existir nos três idiomas: traduzir "aceitar"
        # e "autorizar" pela mesma palavra apagaria a distinção justamente onde ela importa.
        for loc in ("pt-BR", "en", "es"):
            txt = self.i18n["locales"][loc]["commercial"]["authorize_explained"]
            self.assertGreater(len(txt), 40, f"{loc}: a explicação dos dois atos está curta demais")


class CommercialErrorCodesAreExplainedTests(unittest.TestCase):

    def test_the_backend_messages_say_what_to_do_not_just_what_failed(self):
        from impacto.services import offers as OF
        from impacto.http import ApiError
        from tests.support import db_system
        pf = new_account("provider")
        with db_system() as c:
            with self.assertRaises(ApiError) as e:
                OF.validate_payment_terms(c, org_id=pf.org_id, payment_method="boleto",
                                          billing_frequency="installment", installments=3)
        # A mensagem diz a alternativa, e não só a recusa.
        self.assertIn("cartão", e.exception.message)
        self.assertIn("à vista", e.exception.message)
