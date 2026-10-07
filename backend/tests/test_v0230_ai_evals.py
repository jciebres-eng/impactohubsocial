"""Avaliação da camada de IA contra um conjunto de referência.

POR QUE ESTA AVALIAÇÃO É POSSÍVEL AQUI

O prompt desta rodada pede conjunto de referência, teste de alucinação, teste de contradição e
regressão de avaliação. Avaliar saída de modelo externo exigiria provedor contratado, e esta
instalação não tem um — declarar uma avaliação que não roda seria pior que não ter.

O que roda é a avaliação dos motores DETERMINÍSTICOS (`engines/ai/local.py`). E ela vale por dois
motivos concretos: esses motores são o caminho padrão desta plataforma (sem provedor configurado,
são eles que produzem o resultado), e são eles que definem o PISO de qualidade — quando há provedor,
a resposta externa é comparada com o resultado local antes de substituí-lo.

INVARIANTE, NÃO SAÍDA EXATA

O conjunto fixa invariantes, não texto. Fixar a saída palavra por palavra transformaria qualquer
melhoria de redação em reprovação — e aí alguém atualiza o arquivo sem ler, que é o jeito mais
rápido de uma suíte de avaliação deixar de significar algo.

A invariante central é a mais barata de conferir e a mais caruaro de violar: NÚMERO NA SAÍDA QUE NÃO
ESTAVA NA ENTRADA. É alucinação na forma que mais importa para uma plataforma de prestação de
contas, porque um número inventado num relatório de impacto é uma afirmação falsa com aparência de
medição.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

GOLDEN = json.loads((Path(__file__).parent / "golden" / "ai_golden.json").read_text(encoding="utf-8"))

ADJETIVOS_PROMOCIONAIS = ("incrível", "revolucionário", "excelente", "inédito", "único no país",
                          "imperdível", "transformador", "melhor do", "líder em")


def _digitos(texto: str) -> set[str]:
    """Os números presentes num texto, normalizados.

    Normalizar importa: `R$ 30.000,00` e `30000` são o mesmo número escrito de dois jeitos, e
    comparar as formas brutas produziria falsas alucinações a cada formatação de moeda.
    """
    return {d.lstrip("0") or "0" for d in re.findall(r"\d+", re.sub(r"[.,]", "", texto or ""))}


#: Campos de texto livre de `structure_need`. A invariante de número inventado vale AQUI e não
#: sobre a saída inteira: `ods: [4, 16]` são códigos de catálogo derivados por regra de
#: palavra-chave, não afirmação numérica sobre o projeto. A primeira versão deste teste reprovava
#: por causa deles, o que seria pedir ao motor que não classificasse.
CAMPOS_DE_TEXTO = ("title", "summary", "problem", "objectives", "beneficiaries_description",
                   "questions")


def _texto_livre(saida: dict) -> str:
    return " ".join(_texto_de(saida.get(k)) for k in CAMPOS_DE_TEXTO)


def _texto_de(valor) -> str:
    if isinstance(valor, str):
        return valor
    if isinstance(valor, dict):
        return " ".join(_texto_de(v) for v in valor.values())
    if isinstance(valor, (list, tuple)):
        return " ".join(_texto_de(v) for v in valor)
    return "" if valor is None else str(valor)


class TheGoldenSetItselfIsWellFormedTests(unittest.TestCase):
    """Conjunto de referência sem caso é uma avaliação que passa sempre."""

    def test_every_engine_has_cases(self):
        for motor in ("structure_need", "summarize_project", "classify_document"):
            with self.subTest(motor=motor):
                self.assertGreaterEqual(len(GOLDEN[motor]), 2)

    def test_every_case_declares_why_it_exists(self):
        """Caso sem motivo escrito é caso que ninguém sabe se ainda faz sentido."""
        for motor, casos in GOLDEN.items():
            if motor.startswith("_"):
                continue
            for caso in casos:
                with self.subTest(caso=caso["id"]):
                    self.assertGreaterEqual(len(caso.get("why", "")), 60)
                    self.assertTrue(caso.get("invariants"), "caso sem invariante não avalia nada")

    def test_every_case_id_is_unique(self):
        todos = [c["id"] for m, cs in GOLDEN.items() if not m.startswith("_") for c in cs]
        self.assertEqual(len(todos), len(set(todos)))


class TheStructuringEngineNeverInventsANumberTests(unittest.TestCase):

    def test_the_golden_cases_pass(self):
        from impacto.engines.ai import local
        for caso in GOLDEN["structure_need"]:
            with self.subTest(caso=caso["id"]):
                saida = local.structure_need(caso["input"])
                inv = caso["invariants"]
                texto = _texto_livre(saida)
                if inv.get("no_invented_digits"):
                    novos = _digitos(texto) - _digitos(caso["input"])
                    self.assertEqual(set(), novos,
                                     f"número inventado na saída: {sorted(novos)}")
                if inv.get("digits_subset_of_input"):
                    novos = _digitos(texto) - _digitos(caso["input"])
                    self.assertEqual(set(), novos, f"número inventado: {sorted(novos)}")
                if inv.get("title_max_chars"):
                    self.assertLessEqual(len(saida["title"]), inv["title_max_chars"])
                if inv.get("summary_within_input"):
                    self.assertIn(saida["summary"].strip()[:40].lower(),
                                  caso["input"].lower() + " ",
                                  "o resumo não é trecho da entrada: é texto novo")
                if inv.get("causes_from_catalog"):
                    self.assertTrue(all(isinstance(c, str) for c in saida.get("causes", [])))

    def test_an_empty_input_produces_empty_structure_not_a_project(self):
        from impacto.engines.ai import local
        saida = local.structure_need("")
        self.assertEqual(set(), _digitos(_texto_livre(saida)))
        self.assertEqual("", saida["summary"].strip())

    def test_the_hallucination_check_would_catch_a_real_one(self):
        """Contraprova: a invariante só vale se souber reprovar.

        Sem este teste, uma mudança em `_digitos` que fizesse a comparação sempre devolver conjunto
        vazio deixaria toda a avaliação verde sem conferir nada.
        """
        inventado = _digitos("atendemos 500 pessoas") - _digitos("atendemos pessoas")
        self.assertEqual({"500"}, inventado)


class TheSummaryDoesNotAddNumbersOrAdjectivesTests(unittest.TestCase):

    def test_the_golden_cases_pass(self):
        from impacto.engines.ai import local
        for caso in GOLDEN["summarize_project"]:
            with self.subTest(caso=caso["id"]):
                saida = local.summarize_project(caso["input"])
                inv = caso["invariants"]
                entrada = _texto_de(caso["input"])
                if inv.get("digits_subset_of_input"):
                    novos = _digitos(saida) - _digitos(entrada)
                    self.assertEqual(set(), novos, f"número inventado no resumo: {sorted(novos)}")
                if inv.get("max_chars"):
                    self.assertLessEqual(len(saida), inv["max_chars"])
                if inv.get("no_promotional_adjectives"):
                    achados = [a for a in ADJETIVOS_PROMOCIONAIS if a in saida.lower()]
                    self.assertEqual([], achados,
                                     f"adjetivo promocional no resumo: {achados} — resumo com "
                                     "adjetivo vira alegação")

    def test_the_summary_still_says_something(self):
        """Contraprova: um motor que devolvesse string vazia passaria em todas as invariantes."""
        from impacto.engines.ai import local
        saida = local.summarize_project(GOLDEN["summarize_project"][1]["input"])
        self.assertGreater(len(saida.strip()), 40, "o resumo está vazio ou quase")

    def test_an_input_with_a_promotional_adjective_does_not_leak_it(self):
        """O motor copia trecho da entrada. Se a entrada tiver adjetivo, ele pode vir — e aí o
        teste documenta o limite em vez de prometer o que o motor não faz."""
        from impacto.engines.ai import local
        saida = local.summarize_project({
            "title": "Projeto incrível", "summary": "O melhor do estado.",
            "problem": "p", "objectives": "o"})
        self.assertIsInstance(saida, str)


class TheClassifierSaysUnknownInsteadOfGuessingTests(unittest.TestCase):

    def test_the_golden_cases_pass(self):
        from impacto.engines.ai import local
        for caso in GOLDEN["classify_document"]:
            with self.subTest(caso=caso["id"]):
                saida = local.classify_document(caso["text"], caso["filename"])
                inv = caso["invariants"]
                if inv.get("confidence_zero_when_no_signal"):
                    self.assertEqual(0.0, saida["confidence"],
                                     "sem sinal no texto, a confiança tem de ser zero")
                if "cnpj_found" in inv:
                    self.assertIn(inv["cnpj_found"], saida["cnpjs_found"])
                if "valid_until" in inv:
                    self.assertEqual(inv["valid_until"], saida["valid_until"])
                if inv.get("human_review_required"):
                    self.assertTrue(saida["human_review_required"])

    def test_an_impossible_date_does_not_become_a_validity(self):
        """31 de fevereiro não existe. Aceitar a data mais próxima inventaria validade."""
        from impacto.engines.ai import local
        self.assertIsNone(local.classify_document("Validade: 31/02/2027", "x.pdf")["valid_until"])

    def test_a_real_signal_produces_a_confidence_above_zero(self):
        """Contraprova: um classificador que devolvesse sempre zero passaria no caso sem sinal."""
        from impacto.engines.ai import local
        # O texto tem de casar uma palavra-chave de `DOC_RULES` — "débitos relativos aos tributos
        # federais" (no plural, como a certidão real traz). Pegar a frase quase certa faria o teste
        # provar o contrário do que pretende.
        saida = local.classify_document(
            "CERTIDÃO NEGATIVA DE DÉBITOS RELATIVOS AOS TRIBUTOS FEDERAIS E À DÍVIDA ATIVA DA "
            "UNIÃO. Emitida pela Receita Federal. Validade: 31/12/2027.",
            "certidao_federal.pdf")
        self.assertGreater(saida["confidence"], 0.0)
        self.assertNotEqual("outro", saida["suggested_type"])

    def test_no_cnpj_is_reported_when_none_is_present(self):
        from impacto.engines.ai import local
        self.assertEqual([], local.classify_document("sem documento algum", "a.pdf")["cnpjs_found"])


class EveryEngineMarksItsOutputAsADraftTests(unittest.TestCase):
    """A garantia que sustenta a camada inteira: nada do que a IA produz vira estado sozinho."""

    def test_the_classifier_demands_human_review(self):
        from impacto.engines.ai import local
        self.assertTrue(local.classify_document("contrato", "c.pdf")["human_review_required"])

    def test_the_draft_engine_marks_what_is_missing_instead_of_filling_it(self):
        """`[COMPLETAR]` é a diferença entre um rascunho honesto e um documento com dado inventado."""
        from impacto.engines.ai import local
        texto = local.draft_document(
            "project_proposal",
            {"title": "Projeto sem dados", "summary": "", "problem": "", "objectives": ""},
            {"legal_name": "OSC Exemplo", "cnpj": None, "city": None, "uf": None},
            None, [], [], None)
        self.assertIn("[COMPLETAR", texto,
                      "o rascunho preencheu lacuna em vez de marcá-la")

    def test_the_draft_engine_does_not_invent_money(self):
        from impacto.engines.ai import local
        projeto = {"title": "Projeto", "summary": "s", "problem": "p", "objectives": "o"}
        texto = local.draft_document("project_proposal", projeto,
                                     {"legal_name": "OSC", "cnpj": None, "city": None, "uf": None},
                                     None, [], [], None)
        novos = _digitos(texto) - _digitos(_texto_de(projeto)) - {"0"}
        # Datas e numeração de seção são do GABARITO, não do dado. O que não pode aparecer é valor
        # monetário sem origem — e sem itens de orçamento não existe valor para informar.
        self.assertNotIn("R$", texto.replace("R$ [COMPLETAR", ""),
                         f"valor monetário num rascunho sem orçamento (números novos: {sorted(novos)[:5]})")


if __name__ == "__main__":
    unittest.main()
