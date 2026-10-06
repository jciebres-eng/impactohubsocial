"""v0.20.0 §47–48 e §89 — benchmark de preço: referência consultada, nunca preço decidido.

A SEPARAÇÃO QUE ESTES TESTES MANTÊM

`config/price_benchmark.json` é o que o MERCADO cobra. `config/plans.json` é o que a Impacto Trust
cobra. Nenhuma linha de código lê o primeiro para preencher o segundo, e é isso que o teste
`test_the_benchmark_never_feeds_the_platform_prices` trava.

Não é formalidade. Um benchmark que vira preço por conveniência produz um preço que NINGUÉM decidiu:
ele apenas apareceu, copiado de empresas com outro produto, outro custo e outro cliente. O documento
desta rodada diz a mesma coisa de outro jeito — "não tratar benchmark como decisão final do
proprietário" — e `PRICE_FINALIZATION_REQUIRED` é a marca que mantém a pendência visível.
"""
from __future__ import annotations

import json
import unittest

from impacto.core import pricing
from tests.support import ROOT, make_admin


class BenchmarkIsRecordedProperlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = pricing.load()

    def test_every_entry_carries_the_seven_fields_the_document_requires(self):
        for e in self.doc["entries"]:
            for campo in pricing.REQUIRED_FIELDS:
                self.assertIn(campo, e, f"{e.get('product')}: falta {campo}")

    def test_every_price_points_at_the_vendors_own_page(self):
        """Agregador de terceiro publica ESTIMATIVA. Estimativa apresentada como preço é o tipo de
        dado que esta plataforma recusa em todo o resto — não vai entrar por aqui."""
        for e in self.doc["entries"]:
            self.assertTrue(e["source"].startswith("https://"), e["product"])
            for agregador in ("capterra", "g2.com", "spendhound", "pricingsaas", "toolradar",
                              "vendorbenchmark", "erpresearch"):
                self.assertNotIn(agregador, e["source"].lower(),
                                 f"{e['product']}: fonte é agregador, não o fornecedor")

    def test_a_vendor_that_does_not_publish_is_recorded_as_such(self):
        """Omitir quem não publica faria o mercado parecer mais transparente do que é."""
        sem = [e for e in self.doc["entries"] if e["price"] is None]
        self.assertTrue(sem, "a pesquisa encontrou fornecedores sem preço público: eles têm de estar aqui")
        for e in sem:
            self.assertIn("not_published_reason", e, f"{e['product']}: falta o motivo")
            self.assertIn("NÃO publica", e["not_published_reason"])

    def test_the_collection_date_is_declared_once_for_the_whole_table(self):
        self.assertRegex(self.doc["collected_on"], r"^\d{4}-\d{2}-\d{2}$")
        for e in self.doc["entries"]:
            self.assertRegex(e["source_date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_no_price_was_converted_between_currencies(self):
        """Converter exigiria escolher taxa e data, e o resultado pareceria mais preciso do que é."""
        moedas = {e["currency"] for e in self.doc["entries"] if e["currency"]}
        self.assertNotIn("BRL", moedas,
                         "nenhum comparável publica em reais; um valor em BRL aqui seria conversão")

    def test_the_findings_say_what_the_research_actually_found(self):
        texto = " ".join(self.doc["findings"])
        self.assertIn("não publica preço", texto)
        self.assertIn("por ASSENTO", texto,
                      "o modelo de cobrança dos comparáveis é diferente, e isso tem de estar dito")


class BenchmarkIsNotPriceTests(unittest.TestCase):
    """A trava central: benchmark não vira preço, nem por descuido."""

    def test_the_benchmark_never_feeds_the_platform_prices(self):
        """Nenhum módulo lê o benchmark E o arquivo de planos. Servir o benchmark numa rota é uso
        legítimo; o que não pode é um mesmo trecho de código ter os dois na mão."""
        import ast
        import pathlib
        pkg = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        culpados = []
        for f in pkg.rglob("*.py"):
            if f.name == "pricing.py":
                continue
            arvore = ast.parse(f.read_text(encoding="utf-8"))
            # Só CÓDIGO conta: citar `config/plans.json` numa explicação é explicar, não ler.
            docstrings = {id(ast.get_docstring(n, clean=False)) for n in ast.walk(arvore)
                          if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                            ast.AsyncFunctionDef))}
            textos = [n.value for n in ast.walk(arvore)
                      if isinstance(n, ast.Constant) and isinstance(n.value, str)
                      and id(n.value) not in docstrings]
            # Os NOMES importados entram junto com os módulos: é `from ..core import pricing` que
            # revela a leitura do benchmark, e o módulo ali se chama `core`, não `pricing`.
            importados = set()
            for a in ast.walk(arvore):
                if isinstance(a, (ast.Import, ast.ImportFrom)):
                    importados |= {al.name.split(".")[-1] for al in a.names}
                    if isinstance(a, ast.ImportFrom) and a.module:
                        importados |= set(a.module.split("."))
            codigo = "\n".join(textos)
            # v0.21.0 — detector PRECISO. Antes bastava a substring "pricing" aparecer em qualquer
            # texto do arquivo. Isso bastava enquanto "pricing" só existia no benchmark; a Pricing
            # Version 2027.01 tornou `pricing_version` um conceito corrente, e a regra passou a
            # acusar módulos que apenas nomeiam a versão de preço. O que o teste quer achar é quem
            # LÊ o benchmark — ou seja, quem cita o arquivo dele ou importa o módulo que o lê.
            le_benchmark = "price_benchmark" in codigo or "pricing" in importados
            le_planos = "plans.json" in codigo
            if le_benchmark and le_planos:
                culpados.append(f.name)
        self.assertEqual(culpados, [],
                         "módulo que lê o benchmark E o arquivo de planos: é por aí que um vira o outro")

    def test_the_paid_plans_still_have_no_price_decided(self):
        planos = json.loads((ROOT / "config" / "plans.json").read_text(encoding="utf-8"))["plans"]
        pagos = {k: v for k, v in planos.items() if v.get("price_cents") is None}
        self.assertTrue(pagos, "os planos pagos seguem sem preço até o proprietário decidir")

    def test_the_finalization_marker_is_on(self):
        self.assertTrue(pricing.load()["PRICE_FINALIZATION_REQUIRED"],
                        "enquanto o preço não for decidido, a marca fica ligada")

    def test_no_plan_price_is_hardcoded_in_the_frontend(self):
        """§48: nunca espalhar PREÇO DE PLANO pelo frontend.

        A regra é sobre preço da plataforma, não sobre qualquer número com cifrão: um texto de
        exemplo que diz "tenho R$ 250 mil para educação" é conteúdo de ajuda, e proibi-lo tornaria
        o teste barulhento até alguém desligá-lo. O que se procura é valor na mesma linha de
        plano, assinatura ou mensalidade.
        """
        import re
        web = ROOT / "web" / "src"
        padrao = re.compile(r"(plano|assinatura|mensalidade|/\s*m[êe]s)", re.I)
        valor = re.compile(r"R\$\s?\d|\b\d+[.,]\d{2}\b")
        suspeitos = []
        for f in web.rglob("*.ts*"):
            for linha in f.read_text(encoding="utf-8").splitlines():
                # Comentário que EXPLICA como o preço é exibido não é preço escrito à mão.
                if linha.lstrip().startswith(("//", "*", "/*")):
                    continue
                if padrao.search(linha) and valor.search(linha):
                    suspeitos.append(f"{f.name}: {linha.strip()[:90]}")
        self.assertEqual(suspeitos, [],
                         "preço de plano escrito à mão na interface: o preço vem da API")


class BenchmarkRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin, _ = make_admin()

    def test_the_route_returns_the_benchmark_with_its_warning(self):
        r = self.admin.get("/v1/admin/price-benchmark")
        self.assertEqual(r.status, 200, r)
        self.assertIn("BENCHMARK, NÃO PREÇO", r.json["warning"])
        self.assertTrue(r.json["PRICE_FINALIZATION_REQUIRED"])
        self.assertGreaterEqual(r.json["published"], 5)
        self.assertGreaterEqual(r.json["not_published"], 1,
                                "quem não publica preço também aparece")
        self.assertIsNotNone(r.json["range_usd"])

    def test_the_route_says_who_decides_and_what_is_blocked_meanwhile(self):
        r = self.admin.get("/v1/admin/price-benchmark")
        d = r.json["decision_required"]
        self.assertIn("proprietário", d["owner"])
        self.assertIn("sob consulta", d["blocked_until_then"])

    def test_an_ordinary_organization_cannot_read_the_benchmark(self):
        from tests.support import new_account
        r = new_account("company").get("/v1/admin/price-benchmark")
        self.assertIn(r.status, (401, 403), r)
