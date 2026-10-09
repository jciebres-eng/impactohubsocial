"""v0.30.0 — os documentos do pacote de superprompts dizem a verdade sobre o código.

* MILESTONE_FUNDING_STATES_v0300.md: toda tabela e coluna citada como `tabela.coluna` existe no esquema; os valores de estado citados
  existem nos CHECKs; o que está marcado "não existe" de fato não existe (nenhuma tabela de saldo/escrow).
* SAAS_ECONOMY.md: toda regra citada existe no catálogo; nenhuma está ativa; as recusadas estão marcadas recusadas; não promete preço.
* 24_MONTH_FINANCIAL_MODEL.md: a seção de sensibilidade do take rate existe, a linha do catálogo está em negrito e o percentual do
  catálogo não mudou.
* PROFILE_JOURNEY_MATRIX_v0300.md: é exatamente o que o gerador produz.
* BASELINE_v0300.md: existe e classifica em quatro estados.
"""
import re
import subprocess
import sys
import unittest

from tests.support import ROOT, db_system

DOCS = ROOT / "docs" / "execution"


class MilestoneStatesDocTests(unittest.TestCase):
    txt = (DOCS / "MILESTONE_FUNDING_STATES_v0300.md").read_text(encoding="utf-8")

    def test_every_cited_table_and_column_exists(self):
        refs = set(re.findall(r"`([a-z_]+)\.([a-z_]+)`", self.txt)) - {("application", "transition"), ("billing", "write"), ("killswitch", "py")}   # ação de auditoria, permissão, arquivo
        self.assertGreaterEqual(len(refs), 8)
        with db_system() as c:
            cols = {(r["table_name"], r["column_name"]) for r in c.query(
                "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public'")}
        missing = sorted(f"{t}.{col}" for t, col in refs if (t, col) not in cols)
        self.assertEqual(missing, [], "documento cita coluna que não existe")

    def test_cited_state_values_exist_in_the_checks(self):
        with db_system() as c:
            checks = " ".join(r["def"] for r in c.query("SELECT pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE contype = 'c'"))
        for value in ("instruction_created", "awaiting_rule", "reconciled", "disputed", "under_review", "superseded", "contested", "overdue", "due_diligence"):
            self.assertIn(f"'{value}'", checks, value)

    def test_no_escrow_or_balance_table_exists_as_the_document_states(self):
        self.assertIn("não existe e não existirá", self.txt)
        with db_system() as c:
            names = [r["table_name"] for r in c.query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")]
        self.assertFalse([n for n in names if re.search(r"escrow|wallet|balance|custod", n)], names)


class SaasEconomyDocTests(unittest.TestCase):
    txt = (ROOT / "docs" / "SAAS_ECONOMY.md").read_text(encoding="utf-8")

    def test_every_cited_rule_exists_none_is_active_and_refused_ones_are_marked(self):
        keys = set(re.findall(r"`([a-z]+\.[a-z_.]+)`", self.txt)) - {"allocation_payouts.state", "ai.analysis_completed", "billing.write", "finance.approve"}   # permissões, não regras
        with db_system() as c:
            rules = {r["key"]: r for r in c.query("SELECT key, active, legal_status FROM monetization_rules")}
        self.assertTrue(keys <= set(rules), keys - set(rules))
        self.assertFalse(any(r["active"] for r in rules.values()))
        for k, r in rules.items():
            if r["legal_status"] == "refused":
                self.assertIn(k, self.txt)
                self.assertRegex(self.txt, rf"`{re.escape(k)}`[^\n]*recusad")
        self.assertIn("R$ 0,00", self.txt)
        self.assertIn("[PREMISSA]", self.txt)

    def test_it_does_not_reintroduce_subscription_or_escrow(self):
        for bad in ("mensalidade de R$", "escrow como feature", "assinatura mensal de"):
            self.assertNotIn(bad, self.txt)
        self.assertIn("Não existe assinatura", self.txt)


class FinancialModelTakeRateTests(unittest.TestCase):
    txt = (ROOT / "24_MONTH_FINANCIAL_MODEL.md").read_text(encoding="utf-8")

    def test_the_sensitivity_section_exists_and_the_catalog_rate_is_the_bold_one(self):
        self.assertIn("SENSIBILIDADE DO TAKE RATE", self.txt)
        self.assertIn("| **3,50%** |", self.txt)
        for p in ("2,00%", "3,00%", "4,00%", "5,00%"):
            self.assertIn(f"| {p} |", self.txt)
        self.assertIn("Nenhum deles é preço", self.txt)
        import json
        cfg = json.loads((ROOT / "config" / "economic_model.json").read_text(encoding="utf-8"))
        self.assertEqual(cfg["platform_service_bps"], 350)
        self.assertEqual(cfg["proponent_participation_bps"], 150)


class GeneratedMatricesTests(unittest.TestCase):
    def test_the_profile_journey_matrix_is_what_the_generator_produces(self):
        path = DOCS / "PROFILE_JOURNEY_MATRIX_v0300.md"
        before = path.read_text(encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_profile_journey_matrix.py")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(path.read_text(encoding="utf-8"), before, "regere com scripts/make_profile_journey_matrix.py")
        self.assertIn("Jornadas: **16**", before)

    def test_the_baseline_classifies_in_four_states_and_names_the_conflicts(self):
        txt = (DOCS / "BASELINE_v0300.md").read_text(encoding="utf-8")
        for st in ("PROVADO", "PARCIAL", "SÓ DOCUMENTADO", "AUSENTE"):
            self.assertIn(st, txt)
        for adr in ("ADR-284", "ADR-337", "ADR-341"):
            self.assertIn(adr, txt)
