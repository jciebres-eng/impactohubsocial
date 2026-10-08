"""v0.25.0 — a matriz de cobertura é GERADA das evidências e não pode divergir delas.

Roda antes (ordem alfabética) dos testes que regravam as evidências; confere a matriz versionada
contra as evidências versionadas. Se divergir: `python3 scripts/make_coverage_matrix.py`.
"""
from __future__ import annotations

import subprocess
import sys
import unittest

from tests.support import ROOT


class TheCoverageMatrixMatchesTheEvidenceTests(unittest.TestCase):
    def test_the_committed_matrix_is_what_the_evidence_produces(self):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_coverage_matrix.py"), "--check"],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_the_matrix_quotes_zero_failures(self):
        texto = (ROOT / "docs" / "execution" / "COVERAGE_MATRIX.md").read_text(encoding="utf-8")
        self.assertIn("0 falha(s). Fonte: `docs/evidence/jornadas_v0250", texto)
        for linha in texto.splitlines():
            if linha.startswith("| ") and "Perfil" not in linha and "---" not in linha and linha.count("|") == 13:
                self.assertEqual(linha.split("|")[10].strip(), "0", f"perfil com estado de falha: {linha}")
