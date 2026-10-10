"""v0.35.0 — o que a versão afirma sobre as correções de segurança está no repositório, e é verificável.

* VERSION, CHANGELOG, DECISIONS (ADR-385..392) e o snapshot da 0.34.0 em `history/`.
* `docs/security/`: auditoria da fase 1, relatório da fase 2, checklist de publicação, runbooks e evidências — e o relatório
  não promete o que nenhum sistema garante, não traz segredo e só cita commits que existem.
* O checklist de publicação fala de TODA variável nova que a configuração passou a ler nesta versão.
"""
import re
import subprocess
import unittest

from tests.support import ROOT

SEC = ROOT / "docs" / "security"
NOVAS_VARIAVEIS = ("TRUST_PROXY_HEADERS", "TRUSTED_PROXY_HOPS", "CLIENT_IP_HEADER", "DONATION_WEBHOOK_SECRET", "PAYMENT_SANDBOX_ENABLED")


class SecurityDocsTests(unittest.TestCase):
    def test_version_changelog_decisions_and_snapshot(self):
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.35.0")
        ch = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(ch, r"(?m)^## \[0\.35\.0\]")
        self.assertIn("ADR-385", ch)
        dec = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        for n in range(385, 393):
            self.assertRegex(dec, rf"(?m)^\| {n} \|", f"ADR-{n} ausente")
        self.assertEqual((ROOT / "history" / "v0.34.0" / "VERSION").read_text(encoding="utf-8").strip(), "0.34.0")

    def test_the_security_documents_exist_and_are_honest(self):
        nomes = ("AUDITORIA_SEGURANCA_FASE1.md", "RELATORIO_CORRECOES_FASE2.md", "PUBLICATION_CHECKLIST_v0350.md",
                 "runbooks/README.md", "evidencias/README.md")
        for n in nomes:
            self.assertTrue((SEC / n).is_file(), n)
        texto = "\n".join((SEC / n).read_text(encoding="utf-8") for n in nomes)
        texto += "\n".join(p.read_text(encoding="utf-8") for p in (SEC / "runbooks").glob("RB-*.md"))
        # a frase só pode aparecer NEGADA ("Nada de afirmar '100% seguro'"); nunca como afirmação
        for linha in texto.splitlines():
            if re.search(r"(?i)imposs[ií]vel de invadir|blindagem total|100 ?% segur", linha):
                self.assertRegex(linha, r"(?i)\b(não|nada de|nunca|nenhum)\b", f"afirmação proibida: {linha[:120]}")
        self.assertNotRegex(texto, r"(?i)(senha|password|secret|token|passphrase)\s*[:=]\s*['\"]?[A-Za-z0-9+/_-]{16,}")
        rel = (SEC / "RELATORIO_CORRECOES_FASE2.md").read_text(encoding="utf-8")
        self.assertIn("**não** é certificação", rel, "o relatório tem de dizer o que ele NÃO é")
        for trecho in ("NÃO VERIFICÁVEL", "decisão do responsável", "Docker Hub", "AMARELO"):
            self.assertIn(trecho, rel, trecho)

    def test_every_commit_the_report_cites_exists(self):
        rel = (SEC / "RELATORIO_CORRECOES_FASE2.md").read_text(encoding="utf-8") + (SEC / "evidencias" / "README.md").read_text(encoding="utf-8")
        citados = set(re.findall(r"`([0-9a-f]{7})`", rel))
        self.assertGreaterEqual(len(citados), 9)
        for c in citados:
            r = subprocess.run(["git", "cat-file", "-e", f"{c}^{{commit}}"], cwd=ROOT, capture_output=True)
            self.assertEqual(r.returncode, 0, f"o relatório cita o commit {c}, que não existe")

    def test_there_is_fail_before_evidence_for_every_lot(self):
        ev = SEC / "evidencias"
        for lote in "ABCDEFGHI":
            arquivos = list(ev.glob(f"lote{lote}_antes_*.txt"))
            self.assertEqual(len(arquivos), 1, f"lote {lote} sem evidência do código anterior")
            self.assertRegex(arquivos[0].read_text(encoding="utf-8"), r"FAILED|ERROR", f"lote {lote}: a evidência não mostra falha")

    def test_the_publication_checklist_covers_every_new_variable_the_config_reads(self):
        cfg = (ROOT / "backend" / "impacto" / "config.py").read_text(encoding="utf-8")
        chk = (SEC / "PUBLICATION_CHECKLIST_v0350.md").read_text(encoding="utf-8")
        for v in NOVAS_VARIAVEIS:
            self.assertIn(f'"{v}"', cfg, f"{v} não é lida pela configuração")
            self.assertIn(f"`{v}`", chk, f"{v} fora do checklist de publicação")
        self.assertIn("pleasing-trust", chk)
        self.assertIn("ensaio-restauracao", chk)
