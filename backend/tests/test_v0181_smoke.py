"""v0.18.1 — o smoke de publicação, executado como teste (FASE 4).

`scripts/smoke_test.py` é a verificação que roda DEPOIS de publicar, contra a instância que acabou
de subir. Ela só serve se não apodrecer: rota renomeada, cabeçalho perdido ou provedor que deixa de
se declarar precisam quebrar aqui, na suíte, e não no dia da publicação.

Então o teste sobe o servidor real de teste, cria uma conta de verdade e executa o script inteiro.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

from tests.support import PASSWORD, ROOT, new_account, server

SCRIPT = ROOT / "scripts" / "smoke_test.py"


class SmokeScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base = st["base"]
        cls.account = new_account("osc", compliance="approved")
        with tempfile.TemporaryDirectory() as tmp:
            out = pathlib.Path(tmp) / "smoke.json"
            proc = subprocess.run(
                [sys.executable, str(SCRIPT), "--base", cls.base, "--email", cls.account.email,
                 "--password", PASSWORD, "--out", str(out)],
                capture_output=True, text=True, timeout=300)
            cls.proc = proc
            cls.report = json.loads(out.read_text(encoding="utf-8"))

    def test_the_script_runs_and_no_required_check_fails(self):
        self.assertEqual(self.report["summary"]["required_failed"], 0,
                         json.dumps([c for c in self.report["checks"]
                                     if c["status"] == "FAILED"], ensure_ascii=False, indent=2))
        self.assertEqual(self.proc.returncode, 0, self.proc.stdout[-2000:])

    def test_it_proves_the_things_that_matter_on_a_fresh_deploy(self):
        por_chave = {c["key"]: c for c in self.report["checks"]}
        for chave in ("health", "ready", "ready_declares_providers", "meta_config", "openapi",
                      "security_headers", "unauth_is_denied", "login", "session", "db_read",
                      "404_shape", "no_server_banner"):
            self.assertEqual(por_chave[chave]["status"], "PASSED", f"{chave}: {por_chave[chave]}")

    def test_the_readiness_check_declares_which_providers_are_simulated(self):
        """O ponto mais importante do smoke: não deixar provedor simulado passar por real."""
        detalhe = next(c for c in self.report["checks"]
                       if c["key"] == "ready_declares_providers")["detail"]
        self.assertIn("não produtivo", detalhe,
                      "o ambiente de teste usa provedores simulados e o smoke tem de dizer isso")

    def test_a_skipped_check_is_never_counted_as_passed(self):
        pulados = [c for c in self.report["checks"] if c["status"] == "SKIPPED"]
        self.assertTrue(pulados, "o cenário local deveria pular ao menos TLS")
        for c in pulados:
            self.assertTrue(c["detail"], "pulo sem motivo declarado")
        self.assertEqual(self.report["summary"]["passed"] + self.report["summary"]["failed"]
                         + self.report["summary"]["skipped"], self.report["summary"]["total"])

    def test_the_verdict_is_never_go_when_something_was_skipped(self):
        """Smoke que pula verificação e diz GO é o pior resultado possível."""
        if self.report["summary"]["skipped"]:
            self.assertNotEqual(self.report["verdict"], "GO")
            self.assertEqual(self.report["verdict"], "GO WITH CONDITIONS")
