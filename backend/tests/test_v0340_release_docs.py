"""v0.34.0 — o que a versão afirma sobre o ecossistema financeiro está no repositório e bate com o banco.

* A política `free_until_value` existe no banco como versão 1 (hipótese) e o documento cita os mesmos parâmetros.
* As regras de doação/aporte estão INATIVAS; a taxa de serviço está no motor `enterprise`; fundo e reserva no `success_fee`.
* Os documentos pedidos pelo pacote existem e não prometem o que o código não faz.
* ADR-377..383 estão em DECISIONS.md; CHANGELOG e VERSION falam da 0.34.0.
"""
import json
import re
import unittest

from tests.support import ROOT, db_system, server

FIN = ROOT / "docs" / "finance"
REQUIRED = ("FINANCIAL_ARCHITECTURE.md", "FREE_UNTIL_VALUE_POLICY.md", "LEDGER_AND_FINANCIAL_STATES.md", "MONETIZATION_MATRIX.md",
            "RISK_MATRIX.md", "LEGAL_FISCAL_MATRIX.md", "DONATIONS_API.md", "TEST_SCENARIO_COVERAGE.md", "MODULE_INVENTORY.md",
            "PUBLICATION_ROLLBACK_CHECKLIST.md", "modelo_24m/MODELO_24M_v0340.md", "diagramas/arquitetura_financeira.svg",
            "diagramas/fluxo_pagamento_conciliacao.svg", "modelo_24m/IMPACTO_MODELO_24M_v0340.xlsx")


class PolicyAndRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_policy_v1_is_a_hypothesis_and_the_doc_quotes_its_parameters(self):
        with db_system() as c:
            row = c.one("SELECT version, legal_status, content FROM monetization_policy_versions WHERE key = 'free_until_value' ORDER BY version DESC LIMIT 1")
        self.assertEqual((row["version"], row["legal_status"]), (1, "hypothesis"))
        content = row["content"] if isinstance(row["content"], dict) else json.loads(row["content"])
        doc = (FIN / "FREE_UNTIL_VALUE_POLICY.md").read_text(encoding="utf-8")
        self.assertIn("R$ 20.000,00", doc)
        self.assertEqual(content["allowance_settled_cents_12m"], 2_000_000)
        self.assertIn(f"`notice_days` (v1: {content['notice_days']})", doc)
        self.assertEqual(content["public_funding_default"], "exempt")
        for k in ("accountability", "exports", "public_page", "evidence", "reports"):
            self.assertIn(k, content["never_blocks"])

    def test_rules_are_inactive_and_in_the_right_engines(self):
        with db_system() as c:
            rows = {r["key"]: r for r in c.query("SELECT key, active, revenue_engine FROM monetization_rules WHERE key LIKE 'donation.%'")}
        # E6 (ADR-384): + contribuição voluntária do doador, também inativa e no motor faturável (não é destinação do beneficiário)
        self.assertEqual(set(rows), {"donation.platform_fee", "donation.beneficiary_fund", "donation.institutional_fee", "donation.institutional_reserve",
                                     "donation.platform_contribution"})
        self.assertEqual(rows["donation.platform_contribution"]["revenue_engine"], "enterprise")
        self.assertFalse(any(r["active"] for r in rows.values()))
        self.assertEqual(rows["donation.platform_fee"]["revenue_engine"], "enterprise")
        self.assertEqual(rows["donation.institutional_fee"]["revenue_engine"], "enterprise")
        self.assertEqual(rows["donation.beneficiary_fund"]["revenue_engine"], "success_fee", "destinação do beneficiário: motor inativável")
        self.assertEqual(rows["donation.institutional_reserve"]["revenue_engine"], "success_fee")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM monetization_rules WHERE active"), 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND column_name ~ 'balance'"), 0)


class DeliverableDocsTests(unittest.TestCase):
    def test_required_docs_exist_and_are_honest(self):
        for name in REQUIRED:
            self.assertTrue((FIN / name).exists(), name)
        texto = "\n".join((FIN / n).read_text(encoding="utf-8") for n in REQUIRED if n.endswith(".md"))
        self.assertNotRegex(texto, r"(?i)(é|está|100 ?%)\s+imposs[ií]vel de invadir")
        self.assertNotRegex(texto, r"(?i)(senha|password|secret|token)\s*[:=]\s*\S{12,}")
        for trecho in ("INATIVA", "custódia", "não é receita", "instrumento", "finance.approve"):
            self.assertIn(trecho, texto, trecho)
        modelo = (FIN / "modelo_24m" / "MODELO_24M_v0340.md").read_text(encoding="utf-8")
        self.assertIn("HIPÓTESES", modelo)
        self.assertIn("não sustenta a operação", modelo)
        cov = (FIN / "TEST_SCENARIO_COVERAGE.md").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"(?m)^\| \d+ \|", cov)), 40, "os 40 cenários do pacote estão na tabela")
        # E6 (v0.34.0): os 40 cenários passaram a ter teste. A guarda antiga ("⛔ aparece em algum lugar") ficaria satisfeita
        # só pela legenda — vazia. A nova é mais forte: toda linha cita um teste que existe no repositório, e toda linha
        # cuja condição depende do provedor real diz que é simulada/sandbox ou explica o limite.
        tests_dir = ROOT / "backend" / "tests"
        for row in re.findall(r"(?m)^\| (\d+) \| [^|]+\| ([^|]+)\| (.+) \|$", cov):
            n, estado, prova = row
            self.assertTrue(estado.strip().startswith("✅"), f"cenário {n} sem teste: {estado}")
            citados = re.findall(r"test_v0\d{3}(?:_[a-z_]+)?", prova)
            if citados and not prova.startswith("job "):
                for nome in {x for x in citados if x.count("_") > 1}:
                    self.assertTrue((tests_dir / f"{nome}.py").exists(), f"cenário {n} cita {nome}.py, que não existe")
        for n in ("14", "25"):
            linha = re.search(rf"(?m)^\| {n} \|.*$", cov).group(0)
            self.assertRegex(linha, r"simulado|sandbox|só no teste", f"cenário {n} depende do provedor real e tem de dizer que é simulado")

    def test_decisions_changelog_version(self):
        txt = (ROOT / "DECISIONS.md").read_text(encoding="utf-8")
        for n in range(377, 385):   # E6: + ADR-384 (contribuição voluntária, split, webhook em duas fases, recorrência)
            self.assertRegex(txt, rf"(?m)^\| {n} \|", f"ADR-{n} ausente")
        self.assertEqual((ROOT / "VERSION").read_text(encoding="utf-8").strip(), "0.34.0")
        ch = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertRegex(ch, r"(?m)^## \[0\.34\.0\]")
        self.assertIn("ADR-377", ch)
        self.assertTrue((ROOT / "history" / "v0.33.0" / "VERSION").exists())

    def test_api_doc_lists_every_donation_route(self):
        src = (ROOT / "backend" / "impacto" / "api" / "donation_routes.py").read_text(encoding="utf-8")
        doc = (FIN / "DONATIONS_API.md").read_text(encoding="utf-8")
        for m in re.finditer(r'@route\("([A-Z]+)", "([^"]+)"', src):
            self.assertIn(f"`{m.group(1)}` | `{m.group(2)}`", doc, f"rota {m.group(1)} {m.group(2)} fora do documento")
        # E6: a tabela é gerada (scripts/make_donations_api_doc.py) — cada linha tem de ser a da própria rota: na versão
        # escrita à mão, as descrições estavam deslocadas uma linha em relação aos caminhos.
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_donations_api_doc", ROOT / "scripts" / "make_donations_api_doc.py")
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        for linha in gen.rows():
            self.assertIn(linha, doc, "linha da tabela diverge da rota — regere com scripts/make_donations_api_doc.py")

    def test_no_blocking_helper_exists_in_remuneration(self):
        rem = (ROOT / "backend" / "impacto" / "services" / "remuneration.py").read_text(encoding="utf-8")
        self.assertNotRegex(rem, r"def (can_access|is_blocked|block_|lock_|deny_)")
        self.assertIn("never_blocks", rem)
