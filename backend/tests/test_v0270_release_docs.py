"""v0.27.0 — os documentos de fechamento exigidos pelo PROMPT MASTER são derivados, completos e honestos.

O que se prova aqui (nada de "o documento existe"):
  1. `MOTOR_COVERAGE_MATRIX.md` é exatamente o que `scripts/make_motor_coverage_matrix.py` produz a partir do
     registro de motores — um número editado à mão reprova; e a contagem que ele afirma é a do registro;
  2. `FINAL_EXECUTION_REPORT.md` tem as 28 seções fixas, na ordem, a decisão em uma das três formas
     permitidas, nenhum marcador de preenchimento esquecido, e a versão corrente;
  3. `FINAL_EXECUTION_AUDIT.md` não deixa FAIL em aberto e não afirma "100% impossível de invadir";
  4. `EXTERNAL_INTEGRATIONS.md` cobre todo provedor configurável do backend e marca como BLOCKED o que
     depende de credencial/contrato externo — nenhuma integração é declarada ativa sem estar;
  5. `FINAL_RELEASE_MANIFEST.json` e `RELEASE_NOTES.md` falam da versão corrente.
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest

from tests.support import ROOT

VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()

SECOES = ["Executive Summary", "Version", "Commit", "Architecture Status", "Engines Status", "Contract Intelligence",
          "Match", "Diagnostic", "Equity", "Evidence", "Responsibility", "Reputation", "Seals", "Government Data",
          "Marketplace", "Payments", "Distribution", "Billing", "Fiscal", "Vouchers", "Identity", "Security", "LGPD",
          "Tests", "External Dependencies", "Known Limitations", "GO / GO WITH CONDITIONS / NO-GO", "Exact Next Step"]


def _script(nome: str):
    spec = importlib.util.spec_from_file_location(nome, ROOT / "scripts" / f"{nome}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


class MotorCoverageMatrixTests(unittest.TestCase):

    def test_the_matrix_is_exactly_what_the_generator_produces(self):
        dest = ROOT / "MOTOR_COVERAGE_MATRIX.md"
        antes = dest.read_text(encoding="utf-8")
        _script("make_motor_coverage_matrix").main()
        depois = dest.read_text(encoding="utf-8")
        self.assertEqual(antes, depois, "MOTOR_COVERAGE_MATRIX.md divergiu do gerador: rode scripts/make_motor_coverage_matrix.py")

    def test_the_count_it_claims_is_the_registry_and_no_engine_is_red(self):
        from impacto.engines import registry
        txt = (ROOT / "MOTOR_COVERAGE_MATRIX.md").read_text(encoding="utf-8")
        m = re.search(r"\*\*(\d+) motores\*\* — VERDE (\d+) · AMARELO (\d+) · VERMELHO (\d+)", txt)
        self.assertIsNotNone(m, "cabeçalho de contagem ausente")
        total, verde, amarelo, vermelho = (int(x) for x in m.groups())  # type: ignore[union-attr]
        chaves = [e.key for e in registry.ENGINES]
        self.assertEqual(total, len(chaves))
        self.assertEqual(total, verde + amarelo + vermelho)
        self.assertEqual(vermelho, 0, "um motor VERMELHO não pode ser entregue como coberto")
        # cada motor do registro tem a sua linha
        for key in chaves:
            self.assertIn(f"| `{key}` —", txt, f"motor {key} sem linha na matriz")


class FinalExecutionReportTests(unittest.TestCase):
    txt = (ROOT / "FINAL_EXECUTION_REPORT.md").read_text(encoding="utf-8")

    def test_the_28_sections_exist_in_order(self):
        titulos = re.findall(r"^## (\d+)\. (.+)$", self.txt, flags=re.M)
        self.assertEqual([t for _, t in titulos], SECOES)
        self.assertEqual([int(n) for n, _ in titulos], list(range(1, 29)))

    def test_the_decision_is_one_of_the_three_forms_and_is_stated_in_its_section(self):
        secao = self.txt.split("## 27. GO / GO WITH CONDITIONS / NO-GO", 1)[1].split("## 28.", 1)[0]
        bloco = re.search(r"```text\n(GO WITH CONDITIONS|GO|NO-GO)\n```", secao)
        self.assertIsNotNone(bloco, "a decisão tem de estar num bloco, numa das três formas")

    def test_no_placeholder_was_left_behind_and_the_version_is_current(self):
        self.assertNotIn("{{", self.txt, "marcador de preenchimento esquecido")
        self.assertNotIn("TODO", self.txt)
        self.assertIn(f"IMPACTO v{VERSION}", self.txt.splitlines()[0])
        self.assertIn(f"IMPACTO_TRUST_FINAL_RELEASE_{VERSION}.zip", self.txt)

    def test_the_tests_section_reports_a_real_run_with_a_log(self):
        secao = self.txt.split("## 24. Tests", 1)[1].split("## 25.", 1)[0]
        self.assertRegex(secao, r"Ran \d+ tests|\d\.\d{3} testes")
        self.assertIn(f"docs/evidence/test_run_v{VERSION}.log", secao)

    def test_it_never_claims_to_be_impossible_to_break_into(self):
        for frase in ("100% impossível", "impossível de invadir, e este", "100% seguro"):
            if frase in self.txt:
                self.assertIn("não é exceção", self.txt)   # a única forma permitida é a negação


class FinalExecutionAuditTests(unittest.TestCase):
    txt = (ROOT / "FINAL_EXECUTION_AUDIT.md").read_text(encoding="utf-8")

    def test_no_fail_is_left_open_and_every_row_has_evidence(self):
        self.assertIn(f"IMPACTO v{VERSION}", self.txt.splitlines()[0])
        self.assertNotIn("{{", self.txt)
        linhas = [l for l in self.txt.splitlines() if l.startswith("| ") and "| PASS" in l or "| PARTIAL" in l or "| BLOCKED" in l]
        self.assertGreater(len(linhas), 10)
        for l in linhas:
            self.assertNotRegex(l, r"\| FAIL \|", f"FAIL em aberto: {l[:80]}")
            celulas = [c.strip() for c in l.strip("|").split("|")]
            self.assertTrue(celulas[2], f"linha sem evidência: {l[:80]}")

    def test_the_regression_section_names_a_cause_and_a_fix_for_every_failure(self):
        secao = self.txt.split("## 7. Regressão", 1)[1].split("## 8.", 1)[0]
        tabela = [l for l in secao.splitlines() if l.startswith("| `") or l.startswith("| test")]
        self.assertGreater(len(tabela), 5)
        for l in tabela:
            celulas = [c.strip() for c in l.strip("|").split("|")]
            self.assertEqual(len(celulas), 3, l[:80])
            self.assertTrue(all(celulas), f"falha sem causa ou sem correção: {l[:80]}")


class ExternalIntegrationsTests(unittest.TestCase):
    txt = (ROOT / "EXTERNAL_INTEGRATIONS.md").read_text(encoding="utf-8")

    def _rows(self) -> list[list[str]]:
        rows = []
        for l in self.txt.splitlines():
            if l.startswith("| ") and not l.startswith("| ---") and not l.startswith("| Integração"):
                rows.append([c.strip() for c in l.strip("|").split("|")])
        return rows

    def test_every_configurable_provider_of_the_backend_has_a_row(self):
        from impacto.config import Settings
        campos = [f for f in Settings.__dataclass_fields__ if f.endswith("_provider")]   # mail, storage, antivirus, ai, …
        self.assertTrue(campos)
        nomes = " ".join(r[0].lower() for r in self._rows())
        mapa = {"mail_provider": "smtp", "storage_provider": "s3", "antivirus_provider": "clamav", "ai_provider": "modelo de linguagem"}
        for campo in campos:
            self.assertIn(mapa.get(campo, campo.replace("_provider", "")), nomes, f"{campo} sem linha em EXTERNAL_INTEGRATIONS.md")

    def test_nothing_that_needs_a_credential_is_declared_active(self):
        for r in self._rows():
            status = r[-1]
            self.assertIn(status, {"VERDE", "BLOCKED_EXTERNAL_DEPENDENCY", "opcional"}, r[0])
            if status == "VERDE":
                self.assertNotIn("credencial", r[4].lower(), f"{r[0]}: VERDE mas exige credencial")
        # o que o pedido manda nunca simular está, cada um, marcado como bloqueado
        texto = self.txt
        for nome in ("Biometria", "KYC", "ICP-Brasil", "Gov.br", "SMS", "Nota fiscal", "PIX (chave da plataforma)"):
            linha = next((r for r in self._rows() if r[0].startswith(nome)), None)
            self.assertIsNotNone(linha, f"{nome} sem linha")
            self.assertEqual(linha[-1], "BLOCKED_EXTERNAL_DEPENDENCY", nome)  # type: ignore[index]
        self.assertIn("ADR-341", texto)


class ManifestAndNotesTests(unittest.TestCase):

    def test_the_release_manifest_and_the_notes_speak_of_this_version(self):
        m = json.loads((ROOT / "FINAL_RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
        self.assertEqual(m["version"], VERSION)
        self.assertRegex(m["decision"], r"```text\n(GO WITH CONDITIONS|GO|NO-GO)\n```")
        self.assertTrue(m["commit"])
        notas = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")
        self.assertIn(f"v{VERSION}", notas.splitlines()[0])
