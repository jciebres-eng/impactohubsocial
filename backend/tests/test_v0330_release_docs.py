"""v0.33.0 — o que a versão afirma sobre doações está no repositório e bate com o código.

* As travas de dinheiro real estão documentadas em `.env.example` como `false` (ADR-375).
* O arquivo `config/donation_risk_rules.json` espelha a versão e os códigos das regras do serviço (ADR-376).
* Os documentos pedidos pelo pacote existem e dizem, em texto, que não há custódia nem provedor real (ADR-372).
* As decisões ADR-372 a ADR-376 estão em `DECISIONS.md`.
* Nenhum documento promete o que o código não faz: "impossível de invadir" não aparece.
"""
import json
import re
import unittest

from tests.support import ROOT

from impacto.services import donations as DON

DOCS = ROOT / "docs" / "donations"
REQUIRED_DOCS = ("BASELINE_REPORT.md", "IMPLEMENTATION_REPORT.md", "SECURITY_REVIEW.md", "LEGAL_AND_PROVIDER_CHECKLIST.md",
                 "RUNBOOK.md", "DONATIONS_PROVIDER_MATRIX.md", "24_MONTH_DONATIONS_NOTE.md")


class FlagsDocumentedTests(unittest.TestCase):
    def test_env_example_keeps_the_live_flags_off(self):
        txt = (ROOT / ".env.example").read_text(encoding="utf-8")
        for flag in ("LIVE_PAYMENT_PROVIDER_ENABLED", "SPLIT_ENABLED", "RECURRING_DONATIONS_ENABLED", "RISK_HOLD_ENABLED"):
            self.assertRegex(txt, rf"(?m)^{flag}=false$", f"{flag} tem de estar documentada como false")
        self.assertRegex(txt, r"(?m)^DONATIONS_ENABLED=true$")


class RiskRulesFileTests(unittest.TestCase):
    def test_json_mirrors_the_service(self):
        d = json.loads((ROOT / "config" / "donation_risk_rules.json").read_text(encoding="utf-8"))
        self.assertEqual(d["version"], DON.RISK_RULES_VERSION)
        codes = {r["code"] for r in d["rules"]}
        src = (ROOT / "backend" / "impacto" / "services" / "donations.py").read_text(encoding="utf-8")
        for code in codes:
            self.assertIn(f'"{code}"', src, f"regra {code} do JSON não existe no serviço")
        # v0.35.0 (auditoria, FRAUD-02/03): o ARQUIVO passou a ser a fonte (antes o código era a fonte e o JSON, espelho —
        # dava para mudar um sem o outro) e ganhou a regra de fracionamento. O que este teste protege continua: arquivo e
        # serviço não divergem — agora porque o serviço LÊ o arquivo, e nenhum limiar ficou escrito no código.
        self.assertEqual(codes, {"large_single_donation", "burst_attempts", "new_campaign_large_inflow", "structuring"})
        self.assertIn("payout_hold", d["actions_not_available"])
        by = {r["code"]: r for r in d["rules"]}
        self.assertEqual({k: v for k, v in DON.RISK_RULES["rules"].items()}, by)
        self.assertEqual(by["large_single_donation"]["threshold_cents"], 10_000_00)
        self.assertEqual(by["burst_attempts"]["threshold_count"], 20)
        self.assertEqual(by["new_campaign_large_inflow"]["threshold_cents"], 2_000_00)
        for literal in ("10_000_00", ">= 20", "2_000_00"):
            self.assertNotIn(literal, src.split("def _risk_screen", 1)[1].split("def open_risk_case", 1)[0], f"limiar escrito no código: {literal}")


class DeliverableDocsTests(unittest.TestCase):
    def test_required_docs_exist_and_are_honest(self):
        for name in REQUIRED_DOCS:
            self.assertTrue((DOCS / name).exists(), name)
        texto = "\n".join((DOCS / n).read_text(encoding="utf-8") for n in REQUIRED_DOCS)
        # a frase proibida é a AFIRMAÇÃO; a revisão de segurança cita-a só para negá-la ("Nada aqui afirma que…")
        self.assertNotRegex(texto, r"(?i)(é|está|100 ?%)\s+imposs[ií]vel de invadir")
        for trecho in ("custódia", "sandbox", "INATIVA", "parecer"):
            self.assertIn(trecho, texto)
        self.assertNotRegex(texto, r"(?i)(senha|password|secret|token)\s*[:=]\s*\S{12,}")
        matriz = (DOCS / "DONATIONS_PROVIDER_MATRIX.md").read_text(encoding="utf-8")
        self.assertIn("docs.asaas.com", matriz)
        self.assertIn("mercadopago.com.br/developers", matriz)
        self.assertIn("2026-10-10", matriz, "a matriz diz quando foi consultada")

    def test_decisions_have_the_five_adrs(self):
        txt = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        for n in range(372, 377):
            self.assertRegex(txt, rf"(?m)^\| {n} \|", f"ADR-{n} ausente")

    def test_changelog_and_version(self):
        # v0.34.0: a versão corrente avança; o que este teste protege é a ENTRADA da 0.33.0 no CHANGELOG e a versão não regredir.
        self.assertGreaterEqual(tuple(int(x) for x in (ROOT / "VERSION").read_text(encoding="utf-8").strip().split(".")), (0, 33, 0))
        ch = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(ch, r"(?m)^## \[0\.33\.0\]")
        self.assertIn("ADR-372", ch)


class LegacyPublishPathTests(unittest.TestCase):
    def test_platform_routes_no_longer_publish_by_patch(self):
        src = (ROOT / "backend" / "impacto" / "api" / "platform_routes.py").read_text(encoding="utf-8")
        self.assertIn("campaign_review_required", src)
        self.assertFalse(re.search(r"published_at\s*=\s*now\(\)\s*WHERE id = \$1", src.split("def campaign_patch", 1)[-1][:3000] if "def campaign_patch" in src else ""),
                         "o PATCH legado não publica mais sozinho")
