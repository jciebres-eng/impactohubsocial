"""v0.20.0 §94 — as seis telas que faltavam, e a regra que as mantém honestas.

§94 é explícito: **não confundir API IMPLEMENTED com PRODUCT COMPLETE.** Reputação, selos,
afirmações, equidade, ODS e responsabilidade tinham API, serviço, banco, eventos, permissões,
testes e documentação — e nenhuma tela. Uma pessoa não conseguia usar nada disso.

Esta é UI MÍNIMA FUNCIONAL no sentido exato do documento: existe para que o fluxo possa ser
validado de ponta a ponta por uma pessoa, não para ser bonita. O refinamento visual é do Designer,
sobre um contrato técnico congelado.

O QUE ESTES TESTES TRAVAM

1. As seis rotas existem na interface e apontam para páginas que existem.
2. Toda rota da API que a tela chama existe no roteador — tela que chama rota inexistente é a
   mesma mentira de rota que aponta para tela inexistente, só mais difícil de perceber.
3. A interface NÃO INVENTA RÓTULO: os estados vêm de `glossary.ts`, gerado de
   `config/glossary.json`. "Pendente", "em análise" e "aguardando" para o mesmo estado é como um
   produto de evidência começa a parecer três produtos.
4. A tela de reputação diz, por escrito, que não existe nota única nem ranking — porque é a
   pergunta que todo mundo faz ao ver a palavra "reputação".
"""
from __future__ import annotations

import re
import unittest

from tests.support import ROOT

PAGINA = ROOT / "web" / "src" / "pages" / "impactlayer.tsx"
APP = ROOT / "web" / "src" / "app.tsx"

ROTAS_DE_TELA = ("/reputacao", "/selos", "/afirmacoes", "/responsabilidade",
                 "/projetos/:id/equidade", "/projetos/:id/ods")


class ScreensExistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pagina = PAGINA.read_text(encoding="utf-8")
        cls.app = APP.read_text(encoding="utf-8")

    def test_the_six_screens_are_routed(self):
        rotas = set(re.findall(r'^\s*\["(/[^"]*)"', self.app, re.M))
        for r in ROTAS_DE_TELA:
            self.assertIn(r, rotas, f"a tela {r} não está roteada")

    def test_each_route_points_at_a_component_that_exists(self):
        exportados = set(re.findall(r"export function (\w+)", self.pagina))
        for nome in ("Reputation", "Seals", "Claims", "Equity", "OdsTargets", "Responsibility"):
            self.assertIn(nome, exportados, f"componente {nome} não existe")
            self.assertIn(f"IL.{nome}", self.app, f"{nome} não está ligado a nenhuma rota")

    def test_the_screens_appear_in_at_least_one_profile_menu(self):
        for r in ("/reputacao", "/selos"):
            self.assertIn(f'["{r}"', self.app)
            # aparecer no menu é diferente de existir no roteador: sem menu, ninguém acha
            self.assertRegex(self.app, rf'\["{re.escape(r)}", "[^"]+"\]',
                             f"{r} não tem rótulo de menu em nenhum perfil")


class ScreensCallRealRoutesTests(unittest.TestCase):
    """Tela que chama rota inexistente é página em branco com cara de defeito do usuário."""

    @staticmethod
    def _normalizar(caminho: str) -> str:
        """`/v1/projects/${id}/equity` e `/v1/projects/{project_id}/equity` viram a mesma forma."""
        sem_query = caminho.split("?")[0].rstrip("/")
        return re.sub(r"\$\{[^}]+\}|\{[a-z_]+\}", "{}", sem_query)

    @classmethod
    def _declaradas(cls) -> set[str]:
        from impacto import api
        from impacto.http import ROUTES
        api.load_all()
        return {cls._normalizar(r.path) for r in ROUTES}

    def test_every_api_path_used_by_the_screens_exists(self):
        pagina = PAGINA.read_text(encoding="utf-8")
        usados = {self._normalizar(b) for b in re.findall(r'["`](/v1/[^"`]*)["`]', pagina)}
        self.assertTrue(usados, "a varredura não encontrou nenhuma chamada: o teste seria vazio")
        faltando = sorted(usados - self._declaradas())
        self.assertEqual(faltando, [],
                         f"a interface chama rota que não existe no roteador: {faltando}")

    def test_the_check_would_catch_an_invented_route(self):
        """Prova de que o teste acima não passa por vacuidade."""
        self.assertNotIn(self._normalizar("/v1/rota/que/nao/existe"), self._declaradas())
        self.assertEqual(self._normalizar("/v1/projects/${id}/equity"),
                         self._normalizar("/v1/projects/{project_id}/equity"))


class ScreensDoNotInventVocabularyTests(unittest.TestCase):
    """O rótulo da tela sai do glossário oficial, não da cabeça de quem escreveu a tela."""

    @classmethod
    def setUpClass(cls):
        cls.pagina = PAGINA.read_text(encoding="utf-8")

    def test_the_screens_import_the_generated_glossary(self):
        self.assertIn('from "../glossary"', self.pagina)
        for dominio in ("CLAIM_STATUS", "SEAL_STATUS", "REPUTATION_BAND", "EQUITY_STANDING",
                        "EQUITY_METHOD", "EQUITY_DENOMINATOR", "CLAIM_KIND"):
            self.assertIn(dominio, self.pagina,
                          f"{dominio} não é usado: a tela estaria inventando o rótulo")

    def test_the_glossary_module_is_generated_not_handwritten(self):
        g = (ROOT / "web" / "src" / "glossary.ts").read_text(encoding="utf-8")
        self.assertIn("GERADO por scripts/sync_glossary.py", g)
        self.assertIn("não edite à mão", g)


class ScreensSayWhatTheyAreNotTests(unittest.TestCase):
    """Cada tela carrega a recusa que a define — é o que impede o produto de virar outra coisa."""

    @classmethod
    def setUpClass(cls):
        cls.pagina = PAGINA.read_text(encoding="utf-8")

    def test_reputation_says_there_is_no_single_score_and_no_ranking(self):
        self.assertIn("Não existe nota única nem posição em ranking", self.pagina)

    def test_reputation_says_an_open_report_does_not_count(self):
        self.assertIn("Denúncia aberta NÃO entra aqui", self.pagina)
        self.assertIn("infração apurada", self.pagina)

    def test_seals_show_what_they_do_not_attest_with_the_same_weight(self):
        self.assertIn("what_it_does_not_attest", self.pagina)
        self.assertIn("O que NÃO atesta", self.pagina)

    def test_the_ods_screen_refuses_to_transcribe_official_targets_from_memory(self):
        self.assertIn("import_ods_targets.py", self.pagina)
        self.assertIn("não transcreve o texto oficial de memória", self.pagina)

    def test_responsibility_explains_why_an_empty_list_matters(self):
        self.assertIn("não tem sujeito", self.pagina)

    def test_equity_states_that_comparing_without_a_denominator_is_meaningless(self):
        self.assertIn("Comparar sem denominador comum", self.pagina)


class FirstRunNoLongerCallsThemUndesignedTests:
    """Ver tests/test_v0190_firstrun.py: a declaração `to_be_designed` foi atualizada lá."""
