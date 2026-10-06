"""v0.20.0 — o registro completo dos motores e a tabela de seis colunas.

POR QUE ESTA TABELA EXISTE

O diferencial desta plataforma não está numa tela: está na cadeia necessidade → match →
oportunidade → execução → serviço → evidência → prestação de contas → resultado → impacto →
reputação → inteligência. Uma cadeia vale o seu elo mais fraco, e um elo fraco é exatamente o que
uma tabela escrita à mão esconde — porque quem escreve é quem construiu.

Por isso nenhuma das seis colunas é declarada: todas são derivadas do código, do roteador, da suíte
e do esquema. Estes testes travam as duas coisas que fazem a tabela valer alguma coisa:

1. o registro é COMPLETO — módulo que decide algo e tem versão própria não pode ficar de fora;
2. a tabela não pode ser melhorada por escrita, só por implementação.

O QUE A AUDITORIA DESTA RODADA ENCONTROU: doze motores existiam e não estavam declarados, entre eles
a camada de impacto INTEIRA (afirmações, equidade, reputação, selos). Um registro incompleto é pior
que registro nenhum, porque dá a impressão de inventário.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from impacto.engines import coverage
from impacto.engines.registry import ENGINES, KINDS, resolve

PKG = pathlib.Path(__file__).resolve().parents[1] / "impacto"
COLUNAS = ("implemented", "integrated", "tested", "e2e", "security", "observability")


class RegistryIsCompleteTests(unittest.TestCase):
    def test_every_module_with_its_own_engine_version_is_declared(self):
        """O critério é objetivo: ter `ENGINE_VERSION` é declarar-se motor. Então entre no registro."""
        declarados = {e.module for e in ENGINES}
        faltando = []
        for f in PKG.rglob("*.py"):
            if re.search(r"^ENGINE_VERSION\s*=", f.read_text(encoding="utf-8"), re.M):
                modulo = "impacto." + str(f.relative_to(PKG)).removesuffix(".py").replace("/", ".")
                if modulo not in declarados:
                    faltando.append(modulo)
        self.assertEqual(sorted(faltando), [],
                         "módulo com ENGINE_VERSION fora de engines/registry.py: o inventário "
                         "ficaria incompleto sem ninguém perceber")

    def test_the_impact_layer_is_in_the_registry(self):
        """A camada que sustenta a promessa da plataforma estava inteira fora do inventário."""
        declarados = {e.module for e in ENGINES}
        for modulo in ("impacto.impact.claims", "impacto.impact.equity",
                       "impacto.impact.reputation", "impacto.impact.seals"):
            self.assertIn(modulo, declarados)

    def test_every_declared_engine_resolves_and_has_a_valid_kind(self):
        for e in ENGINES:
            self.assertTrue(callable(resolve(e)), f"{e.key}: entrypoint não é chamável")
            self.assertIn(e.kind, KINDS, e.key)

    def test_every_declared_version_matches_the_module_constant(self):
        import importlib
        for e in ENGINES:
            if not e.version:
                continue
            mod = importlib.import_module(e.module)
            real = getattr(mod, e.version_attr, None)
            if real is not None:
                self.assertEqual(real, e.version,
                                 f"{e.key}: versão declarada diverge da constante do módulo")

    def test_no_engine_declares_a_route_that_does_not_exist(self):
        linhas = {r["key"]: r for r in coverage.table()["engines"]}
        mortas = {k: v["declared_routes_missing"] for k, v in linhas.items()
                  if v.get("declared_routes_missing")}
        self.assertEqual(mortas, {},
                         "rota declarada que não existe no roteador é declaração falsa")

    def test_every_engine_says_what_it_never_decides(self):
        """`never` é o campo que impede o registro de virar folheto."""
        for e in ENGINES:
            self.assertGreaterEqual(len(e.never), 30,
                                    f"{e.key}: o que o motor NÃO decide precisa estar escrito")


class CoverageTableIsComputedTests(unittest.TestCase):
    """A tabela não pode ser melhorada escrevendo — só implementando."""

    @classmethod
    def setUpClass(cls):
        cls.t = coverage.table()

    def test_the_table_covers_every_declared_engine(self):
        self.assertEqual(self.t["total"], len(ENGINES))
        self.assertEqual({r["key"] for r in self.t["engines"]}, {e.key for e in ENGINES})

    def test_no_column_is_a_declared_field_of_the_engine(self):
        """Se uma coluna viesse do próprio registro, bastaria escrever `tested=True`."""
        campos = set(ENGINES[0].__dataclass_fields__)
        for coluna in COLUNAS:
            self.assertNotIn(coluna, campos,
                             f"a coluna {coluna} não pode ser declarada pelo motor que ela avalia")

    def test_every_engine_is_implemented_and_integrated(self):
        """Motor que não importa, ou que não está ligado a nada, é dívida — não é motor."""
        for r in self.t["engines"]:
            self.assertTrue(r["implemented"], f"{r['key']}: {r.get('implemented_error')}")
            self.assertTrue(r["integrated"],
                            f"{r['key']}: nem rota viva, nem tarefa, nem chamado por outro motor")

    def test_every_engine_is_exercised_by_the_suite(self):
        for r in self.t["engines"]:
            self.assertTrue(r["tested"], f"{r['key']} não é exercitado por nenhuma suíte")

    def test_no_engine_exposes_an_undeclared_public_route(self):
        for r in self.t["engines"]:
            self.assertNotEqual(r["security"], False,
                                f"{r['key']} expõe rota pública não declarada: "
                                f"{r.get('undeclared_public')}")

    def test_a_gap_is_reported_as_a_gap_and_not_hidden(self):
        """A prova de que a tabela sabe dizer NÃO: oito motores só calculam e não deixam rastro."""
        sem_rastro = [r["key"] for r in self.t["engines"] if r["observability"] is False]
        self.assertTrue(sem_rastro,
                        "uma tabela em que tudo é 'sim' não está medindo coisa alguma")
        self.assertEqual(self.t["summary"]["observability"]["nao"], len(sem_rastro))

    def test_an_engine_without_routes_is_na_not_failed(self):
        for r in self.t["engines"]:
            if not r["routes"]:
                self.assertIsNone(r["e2e"], f"{r['key']}: sem rota, E2E é n/a")
                self.assertIsNone(r["security"], f"{r['key']}: sem rota, segurança é n/a")

    def test_the_markdown_carries_the_definition_of_each_column(self):
        md = coverage.markdown()
        for coluna in COLUNAS:
            self.assertIn(coluna, md)
        self.assertIn("Nenhuma coluna é escrita à mão", md)
        self.assertIn("Não é falha", md)


class ChainIsCoveredTests(unittest.TestCase):
    """A cadeia que é o diferencial da plataforma tem motor declarado em cada elo."""

    def test_each_link_of_the_chain_has_at_least_one_engine(self):
        chaves = {e.key for e in ENGINES}
        elos = {
            "necessidade → match": {"match", "professional_match", "solution_match"},
            "oportunidade → execução": {"lifecycle", "diagnostic"},
            "evidência": {"evidence", "claim_integrity"},
            "prestação de contas": {"impact_report", "report_center"},
            "resultado → impacto": {"equity_context", "result_chain"},
            "reputação": {"reputation", "seals"},
            "inteligência": {"recommendation", "value_ledger"},
            "confiança": {"report_integrity", "risk_signals", "enforcement_ladder"},
        }
        for elo, esperados in elos.items():
            self.assertTrue(esperados & chaves, f"nenhum motor declarado para o elo: {elo}")


class CoverageDocumentIsCurrentTests(unittest.TestCase):
    """O documento gerado não pode envelhecer em silêncio — é o mesmo princípio do glossário."""

    def test_engine_coverage_md_matches_the_live_computation(self):
        doc = (pathlib.Path(__file__).resolve().parents[2] / "ENGINE_COVERAGE.md")
        self.assertTrue(doc.exists(), "rode: (cd backend && python3 ../scripts/make_engine_coverage.py)")
        self.assertEqual(
            doc.read_text(encoding="utf-8").strip(), coverage.markdown().strip(),
            "ENGINE_COVERAGE.md está desatualizado: regenere com "
            "`(cd backend && python3 ../scripts/make_engine_coverage.py)`")
