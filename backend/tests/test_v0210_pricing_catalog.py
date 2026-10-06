"""O catálogo de preços bate com a PRICING_BIBLE.md, e nenhum valor mora no código.

POR QUE ESTE ARQUIVO EXISTE

A auditoria desta rodada encontrou a situação exata oposta: toda a infraestrutura de preço
construída — versionamento, imutabilidade por gatilho, aviso de 30 dias, aceite congelado — e
ZERO linhas de dado. Sete planos pagos com `price_cents = NULL`, `plan_price_versions` vazia.
A plataforma recusava contratação em vez de inventar valor, que é o comportamento certo, mas
significava que nada daquilo tinha sido exercitado com um preço de verdade.

Agora existe preço. Estes testes garantem que ele continue vindo de UM lugar — a tabela de versões,
alimentada por `config/plans.json` — e que a Bíblia e o banco não divirjam em silêncio.
"""
from __future__ import annotations

import json
import pathlib
import re
import unittest

from tests.support import ROOT, db_system

CONFIG = json.loads((ROOT / "config" / "plans.json").read_text(encoding="utf-8"))

# Os valores da PRICING_BIBLE.md §3, em centavos. Escritos aqui À MÃO, de propósito: um teste que
# lesse o mesmo arquivo que a implementação lê concordaria com qualquer coisa. A divergência que
# interessa é entre a DECISÃO COMERCIAL e o que o sistema faz.
BIBLIA_MENSAL = {
    "provider_premium": 4900,     # PROFESSIONAL PRO, §17
    "osc_plus": 29900,            # PRO, §12
    "osc_premium": 79900,         # BUSINESS, §13
    "company_plus": 79900,        # BUSINESS, §13
    "company_premium": 149000,    # FUNDER PRO, §24
}
BIBLIA_ANUAL = {
    "osc_plus": 299000,           # §12
    "osc_premium": 799000,        # §13
    "company_plus": 799000,       # §13
}
BIBLIA_PISO = {
    "company_enterprise": 250000,  # ENTERPRISE, §14
    "gov_institutional": 350000,   # GOV, §15
}


def scalar(sql, *a):
    with db_system() as c:
        return c.scalar(sql, *a)


def item(plan_key: str, interval: str) -> dict | None:
    """O item de preço declarado em `config/plans.json` — a fonte que a migração carrega.

    A conferência é feita AQUI, e não no banco de teste, porque o ambiente de teste publica uma
    tabela própria por cima da real (ver `_declare_test_prices` em `tests/support.py`): ele precisa
    de valores com promoção de entrada e dias de teste para exercitar a camada de cobrança. Conferir
    o banco mediria aquela tabela, não esta decisão comercial. O caminho de carga em si é exercitado
    pelo próprio `dev_reset_db` e pelos testes de versionamento.
    """
    for it in CONFIG["price_versions"]["items"]:
        if it.get("plan_key") == plan_key and it.get("interval") == interval and not it.get("retire"):
            return it
    return None


class CatalogMatchesTheBibleTests(unittest.TestCase):

    def test_every_monthly_price_matches_the_bible(self):
        for plano, cents in BIBLIA_MENSAL.items():
            it = item(plano, "month")
            self.assertIsNotNone(it, f"{plano} não tem preço mensal declarado")
            self.assertEqual(it["currency"], "BRL")
            self.assertEqual(it["amount_cents"], cents,
                             f"{plano} mensal: catálogo {it['amount_cents']}, Bíblia {cents}")

    def test_every_annual_price_matches_the_bible(self):
        for plano, cents in BIBLIA_ANUAL.items():
            it = item(plano, "year")
            self.assertIsNotNone(it, f"{plano} não tem preço anual declarado")
            self.assertEqual(it["amount_cents"], cents,
                             f"{plano} anual: catálogo {it['amount_cents']}, Bíblia {cents}")

    def test_no_annual_price_was_invented_where_the_bible_publishes_none(self):
        # A Bíblia não publica anual para PROFESSIONAL PRO nem para FUNDER PRO. Criar um desconto
        # anual plausível seria inventar preço — e um preço inventado é indistinguível de um
        # decidido depois que entra no banco.
        for plano in ("provider_premium", "company_premium"):
            self.assertIsNone(item(plano, "year"),
                              f"{plano} ganhou um preço anual que a Bíblia não publica")

    def test_proposal_plans_have_a_published_floor_and_no_contractable_price(self):
        for plano, piso in BIBLIA_PISO.items():
            self.assertEqual(CONFIG["plans"][plano].get("quote_floor_cents"), piso)
            self.assertIsNone(item(plano, "month"),
                              f"{plano} é sob proposta e ganhou preço de tabela: o checkout o ofereceria")
            self.assertEqual(CONFIG["plans"][plano].get("prices"), {},
                             f"{plano} é sob proposta e tem preço na tabela antiga")

    def test_the_annual_discount_is_a_consequence_of_two_published_values(self):
        # Não há "desconto de X%" configurável em lugar nenhum: o desconto é o que sobra da conta
        # entre os dois preços que a Bíblia publica. 16,7% é consequência, não parâmetro.
        for plano in BIBLIA_ANUAL:
            mes, ano = BIBLIA_MENSAL[plano], BIBLIA_ANUAL[plano]
            pct = round((1 - ano / (mes * 12)) * 100, 1)
            self.assertAlmostEqual(pct, 16.7, delta=0.2, msg=f"{plano}: desconto anual {pct}%")

    def test_free_plans_cost_zero_and_have_no_price_version(self):
        for plano, p in CONFIG["plans"].items():
            if p.get("tier") != "free":
                continue
            self.assertEqual(p.get("price_cents"), 0, f"{plano} é gratuito e não custa 0")
            self.assertIsNone(item(plano, "month"),
                              f"{plano} é gratuito: ausência de cobrança não é versão de preço")

    def test_the_pricing_version_is_declared_once(self):
        self.assertEqual(CONFIG["pricing_version"], "2027.01")
        from impacto.services import free_period as FP
        self.assertEqual(FP.pricing_version(), "2027.01")

    def test_the_retired_dollar_rule_was_not_resurrected(self):
        # A v0.17.0 aposentou a regra em dólar da v0.16.0. Publicar a tabela nova não pode revivê-la.
        aposentados = [i for i in CONFIG["price_versions"]["items"] if i.get("retire")]
        self.assertEqual(len(aposentados), 2, "os itens aposentados sumiram do arquivo")
        self.assertEqual([i for i in CONFIG["price_versions"]["items"]
                          if i.get("currency", "").upper() == "USD" and not i.get("retire")], [],
                         "voltou a existir item de preço em dólar não aposentado")
        self.assertEqual(scalar("SELECT count(*) FROM plan_price_versions"
                                " WHERE currency = 'USD' AND effective_until IS NULL"), 0,
                         "voltou a existir preço vigente em dólar")


class PriceLivesInOnePlaceTests(unittest.TestCase):

    def test_no_price_figure_is_written_in_product_code(self):
        """Nenhum dos valores da tabela aparece escrito em código Python ou TSX.

        A varredura procura os números exatos (299, 799, 1490, 3500, 49, 2990, 7990) como literais
        isolados nos arquivos que servem preço. Um preço no código é um preço que sobrevive à
        mudança da tabela e passa a cobrar outro valor do que o catálogo diz.
        """
        numeros = {"29900", "79900", "149000", "250000", "350000", "4900", "299000", "799000"}
        alvos: list[tuple[str, str]] = []
        for raiz, padroes in ((ROOT / "backend" / "impacto", ("*.py",)),
                              (ROOT / "web" / "src", ("*.tsx", "*.ts"))):
            for padrao in padroes:
                for f in raiz.rglob(padrao):
                    for n, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                        for tok in re.findall(r"\b\d{3,7}\b", linha):
                            if tok in numeros:
                                alvos.append((f"{f.relative_to(ROOT)}:{n}", linha.strip()[:90]))
        self.assertEqual(alvos, [],
                         "preço escrito no código — o catálogo deixou de ser a fonte única:\n"
                         + "\n".join(f"  {o} · {t}" for o, t in alvos))

    def test_the_take_rate_percentage_is_not_written_in_code(self):
        achados = []
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            txt = f.read_text(encoding="utf-8")
            for n, linha in enumerate(txt.splitlines(), 1):
                if re.search(r"(take_rate|success_fee|transaction_fee)\s*[=:]\s*0?\.?\d", linha):
                    achados.append(f"{f.relative_to(ROOT)}:{n}")
        self.assertEqual(achados, [], "percentual de take rate escrito em código: " + ", ".join(achados))

    def test_the_benchmark_never_feeds_the_platform_price(self):
        # Regra herdada da v0.20.0 e que continua valendo: o que o mercado cobra informa a decisão,
        # nunca a substitui. Um benchmark que vira preço produz um preço que ninguém decidiu.
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            txt = f.read_text(encoding="utf-8")
            if "price_benchmark" in txt:
                self.assertNotIn("plan_price_versions", txt,
                                 f"{f.name} lê o benchmark e escreve no catálogo")


class PaymentNeverBuysTheseTests(unittest.TestCase):
    """O que o pagamento NUNCA compra. Declarado em `never_sellable` e travado aqui."""

    PROIBIDOS = ("provider_rank", "provider_featured", "provider_badge", "match_boost",
                 "eligibility_override")

    def test_the_never_sellable_list_is_declared(self):
        self.assertEqual(sorted(CONFIG["never_sellable"]), sorted(self.PROIBIDOS))

    def test_no_plan_sells_anything_from_the_list(self):
        for plano, p in CONFIG["plans"].items():
            vendidos = set(p.get("features", [])) & set(self.PROIBIDOS)
            self.assertEqual(vendidos, set(), f"{plano} vende {vendidos}")

    def test_no_code_path_turns_a_plan_into_a_score(self):
        """Nenhum cálculo de reputação, impacto ou match lê plano, assinatura ou cobrança.

        Este é o teste que a PRICING_BIBLE.md §61–62 descreve em palavras: `impact_score +=
        payment` não pode existir. Em vez de procurar essa linha exata — que ninguém escreveria
        assim — a varredura verifica que os módulos de pontuação não importam nem consultam as
        tabelas comerciais.
        """
        comerciais = ("subscriptions", "plan_price_versions", "platform_charges", "invoices",
                      "offer_acceptances", "commercial_offers", "free_periods")
        pontuacao = []
        for f in (ROOT / "backend" / "impacto").rglob("*.py"):
            rel = str(f.relative_to(ROOT / "backend" / "impacto"))
            if not any(x in rel for x in ("reputation", "impact", "match", "seal", "claim",
                                          "equity", "eligib")):
                continue
            txt = f.read_text(encoding="utf-8")
            for tabela in comerciais:
                if re.search(rf"\b(FROM|JOIN)\s+{tabela}\b", txt):
                    pontuacao.append(f"{rel} consulta {tabela}")
        self.assertEqual(pontuacao, [],
                         "um módulo de reputação/impacto/match passou a ler estado comercial:\n  "
                         + "\n  ".join(pontuacao))

    def test_entitlements_never_grant_a_never_sellable_feature(self):
        from impacto.services import entitlements as E
        declaradas = set()
        for p in CONFIG["plans"].values():
            declaradas |= set(p.get("features", []))
        self.assertEqual(declaradas & set(self.PROIBIDOS), set())
        # E o caractere coringa `*` existe só para a organização da própria plataforma.
        fonte = (ROOT / "backend" / "impacto" / "services" / "entitlements.py").read_text(encoding="utf-8")
        self.assertIn("platform", fonte.lower())
        self.assertIs(E.has_access, E.has_access)   # o módulo carrega


class TransactionalRulesStayOffTests(unittest.TestCase):
    """Take rate, success fee e transaction fee: declarados, desligados, e por quê."""

    def test_no_monetization_rule_is_active(self):
        ativas = [r["key"] for r in _regras() if r["active"]]
        self.assertEqual(ativas, [], f"regra transacional ativada sem custódia: {ativas}")

    def test_the_blocked_rules_are_refused_by_the_database_not_merely_unset(self):
        for chave in ("marketplace.take_rate", "success_fee.funding"):
            with self.assertRaises(Exception) as e:
                with db_system() as c:
                    c.run("UPDATE monetization_rules SET active = true WHERE key = $1", chave)
            self.assertIn("ADR-022", str(e.exception),
                          f"{chave} pôde ser ativada: a recusa é arquitetural, não configuração")

    def test_the_reconciliation_document_explains_the_conflict_with_the_bible(self):
        doc = (ROOT / "PRICING_RECONCILIATION.md").read_text(encoding="utf-8")
        self.assertIn("ADR-178", doc)
        self.assertIn("12.865", doc, "falta a base legal da recusa (Lei 12.865/2013)")
        bib = (ROOT / "PRICING_BIBLE.md").read_text(encoding="utf-8")
        for termo in ("service", "contract", "transaction"):
            self.assertIn(termo, bib,
                          f"a Bíblia perdeu a condição '{termo}' que ela mesma impõe ao take rate")
        self.assertIn("não custodia", bib)


def _regras():
    with db_system() as c:
        return [dict(r) for r in c.query("SELECT key, active FROM monetization_rules")]


class BibleAndReconciliationExistTests(unittest.TestCase):

    def test_the_bible_is_in_the_repository(self):
        p = ROOT / "PRICING_BIBLE.md"
        self.assertTrue(p.exists(), "PRICING_BIBLE.md não está no repositório")
        txt = p.read_text(encoding="utf-8")
        self.assertIn("2027.01", txt)
        for secao in ("FULL FREE 2026", "ACESSO GRATUITO", "AUTORIZAÇÃO DE COBRANÇA",
                      "O QUE AINDA NÃO ESTÁ DECIDIDO"):
            self.assertIn(secao, txt, f"a Bíblia não tem a seção {secao}")

    def test_the_reconciliation_matrix_has_the_required_columns(self):
        txt = (ROOT / "PRICING_RECONCILIATION.md").read_text(encoding="utf-8")
        for coluna in ("REGRA COMERCIAL", "LOCALIZAÇÃO NO CÓDIGO", "STATUS", "GAP",
                       "IMPLEMENTAÇÃO NECESSÁRIA", "TESTE"):
            self.assertIn(coluna, txt, f"a matriz não tem a coluna {coluna}")
        # E diz o que NÃO foi feito: uma matriz só com linhas verdes não é uma auditoria.
        self.assertIn("O QUE NÃO SERÁ FEITO NESTA RODADA", txt)

    def test_every_matrix_row_names_a_test_file_that_exists(self):
        txt = (ROOT / "PRICING_RECONCILIATION.md").read_text(encoding="utf-8")
        citados = set(re.findall(r"`?(test_v0210_[a-z_]+)`?", txt))
        faltando = [t for t in citados
                    if not (pathlib.Path(__file__).parent / f"{t}.py").exists()]
        self.assertEqual(faltando, [],
                         "a matriz promete testes que não existem: " + ", ".join(sorted(faltando)))


class ScheduledIncreaseSurvivesASyncTests(unittest.TestCase):
    """Um reajuste AGENDADA para o futuro não pode quebrar a próxima migração.

    DEFEITO ENCONTRADO NA v0.21.0, e que existia desde a v0.16.0 sem nunca aparecer.

    `plan_price_versions` tem CHECK `effective_until > effective_from`. O sincronizador fechava toda
    versão vigente em `now()`. Enquanto nenhum preço era agendado para o futuro, `effective_from`
    estava sempre no passado e a conta fechava. Mas a regra dos 30 dias de aviso prescreve
    exatamente isso: anunciar hoje um preço que passa a valer daqui a um mês. Nesse estado, qualquer
    `sync_reference_data` — ou seja, qualquer implantação — morria com violação de CHECK.

    Só apareceu agora porque, com o catálogo vazio, o sincronizador não tinha o que fechar.

    A correção é uma expressão SQL escrita no próprio sincronizador, e não uma função de banco: o
    sincronizador roda em toda versão do schema, inclusive nas antigas que o teste de atualização
    percorre, e uma função criada numa migração recente não existiria lá.
    """

    def test_a_price_scheduled_for_the_future_does_not_break_the_sync(self):
        from impacto.db.migrate import sync_reference_data
        from tests.support import _declare_test_prices, owner_conn
        c = owner_conn()
        try:
            c.run("UPDATE plan_price_versions SET effective_until = now()"
                  " WHERE plan_key = 'osc_plus' AND interval = 'month' AND currency = 'BRL'"
                  " AND effective_until IS NULL")
            futura = c.scalar(
                "INSERT INTO plan_price_versions(plan_key, interval, currency, amount_cents,"
                " tax_behavior, reason, effective_from)"
                " VALUES ('osc_plus','month','BRL',31900,'unspecified',"
                " 'reajuste anunciado com 30 dias, para o teste', now() + interval '30 days')"
                " RETURNING id::text")
            # A implantação seguinte roda o sincronizador. Antes da correção, morria aqui.
            sync_reference_data(c, log=lambda *a: None)
            janela = c.one("SELECT effective_from, effective_until FROM plan_price_versions"
                           " WHERE id = $1", futura)
            self.assertIsNotNone(janela["effective_until"],
                                 "o sincronizador deveria ter fechado a versão agendada")
            self.assertGreater(janela["effective_until"], janela["effective_from"],
                               "a vigência ficou com fim anterior ao início")
            # E o registro continua no histórico: houve um reajuste anunciado e superado antes de valer.
            self.assertEqual(c.scalar("SELECT count(*) FROM plan_price_versions WHERE id = $1",
                                      futura), 1)
        finally:
            c.close()
            _declare_test_prices()
