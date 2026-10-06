"""v0.18.0 — a documentação conferida contra o banco e contra o código (FASE 10).

Documento de arquitetura envelhece calado: alguém muda uma regra, o número no documento continua o
mesmo, e meses depois o relatório mente com cara de fonte. Este arquivo confere cada número
afirmado nos documentos desta rodada contra o estado real.

Três erros reais foram pegos por um arquivo como este na v0.17.0 — e é por isso que ele existe.
"""
from __future__ import annotations

import pathlib
import re
import unittest

from tests.support import db_system

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DOCS = {
    "claims": RAIZ / "CLAIM_INTEGRITY.md",
    "reputation": RAIZ / "REPUTATION_ARCHITECTURE.md",
    "seals": RAIZ / "SEAL_ENGINE.md",
    "forms": RAIZ / "SMART_FORMS.md",
    "responsibility": RAIZ / "RESPONSIBILITY_ENGINE.md",
    "audit": RAIZ / "IMPACT_FRAMEWORK_AUDIT.md",
    "decisions": RAIZ / "DECISIONS.md",
    "changelog": RAIZ / "CHANGELOG.md",
}


class ExistenceTests(unittest.TestCase):
    def test_every_document_of_this_round_exists_and_is_not_a_stub(self):
        for key, path in DOCS.items():
            self.assertTrue(path.exists(), f"{key}: {path.name} não existe")
            self.assertGreater(len(path.read_text(encoding="utf-8")), 2_000, key)


class CountTests(unittest.TestCase):
    """Cada número afirmado em documento, conferido contra o banco."""

    @classmethod
    def setUpClass(cls):
        with db_system() as c:
            cls.n = {
                "claim_rules": c.scalar("SELECT count(*) FROM claim_rules WHERE active"),
                "dimensions": c.scalar("SELECT count(*) FROM reputation_dimensions WHERE active"),
                "seal_rules": c.scalar("SELECT count(*) FROM seal_rules"),
                "roles": c.scalar("SELECT count(*) FROM responsibility_roles WHERE active"),
                "decision_kinds": c.scalar("SELECT count(*) FROM responsibility_decision_kinds"
                                           " WHERE active"),
                "barriers": c.scalar("SELECT count(*) FROM equity_barrier_catalog WHERE active"),
                "topics": c.scalar("SELECT count(*) FROM materiality_topics WHERE active"),
                "frameworks": c.scalar("SELECT count(*) FROM impact_frameworks WHERE active"),
                "determinants": c.scalar("SELECT count(*) FROM determinant_indicator_defs"
                                         " WHERE active"),
                "seal_definitions": c.scalar("SELECT count(*) FROM seal_definitions"
                                             " WHERE status = 'published'"),
                "ods_targets": c.scalar("SELECT count(*) FROM ods_targets"),
            }

    def test_the_eleven_claim_rules_are_eleven_in_the_database(self):
        self.assertEqual(self.n["claim_rules"], 11)
        self.assertIn("11 regras", DOCS["claims"].read_text(encoding="utf-8"))

    def test_the_six_reputation_dimensions_are_six_in_the_database(self):
        self.assertEqual(self.n["dimensions"], 6)
        texto = DOCS["reputation"].read_text(encoding="utf-8")
        self.assertIn("seis dimensões", texto.lower())

    def test_the_twelve_seal_rules_are_twelve_in_the_database(self):
        self.assertEqual(self.n["seal_rules"], 12)
        self.assertIn("doze critérios", DOCS["seals"].read_text(encoding="utf-8").lower())

    def test_the_eight_responsibility_roles_are_eight_in_the_database(self):
        self.assertEqual(self.n["roles"], 8)
        texto = DOCS["responsibility"].read_text(encoding="utf-8")
        self.assertIn("8 papéis", texto)
        self.assertIn("oito papéis", texto.lower())

    def test_the_six_decision_kinds_are_six_in_the_database(self):
        self.assertEqual(self.n["decision_kinds"], 6)
        self.assertIn("6 tipos", DOCS["responsibility"].read_text(encoding="utf-8"))

    def test_the_thirteen_lookups_are_thirteen_in_the_code(self):
        from impacto.impact.lookups import CATALOG
        self.assertEqual(len(CATALOG), 13)
        texto = DOCS["forms"].read_text(encoding="utf-8")
        self.assertIn("treze buscas", texto.lower())
        # e cada chave citada no documento existe de fato no catálogo
        chaves = {k for k, _l, _d, _o in CATALOG}
        for chave in chaves:
            self.assertIn(chave, texto, f"busca {chave} não aparece no documento")

    def test_the_platform_still_ships_zero_published_seal_definitions(self):
        """Se alguém embarcar uma definição numa migração, este teste é o que avisa."""
        with db_system() as c:
            semeadas = c.scalar(
                "SELECT count(*) FROM seal_definitions WHERE code LIKE 'selo\\_%'"
                "   AND code NOT LIKE '%teste%' AND code NOT LIKE '%perf%'"
                "   AND code NOT LIKE '%gaming%' AND code NOT LIKE '%rev%'"
                "   AND code NOT LIKE '%versionado%' AND code NOT LIKE '%projeto%'"
                "   AND code NOT LIKE '%validade%' AND code NOT LIKE '%recusa%'"
                "   AND code NOT LIKE '%escopo%' AND code NOT LIKE '%critetio%'"
                "   AND code NOT LIKE '%recheck%'")
        self.assertEqual(semeadas, 0,
                         "a plataforma passou a embarcar definição de selo; a decisão (ADR-209) "
                         "dizia zero")
        self.assertIn("ZERO definições", DOCS["seals"].read_text(encoding="utf-8"))

    def test_the_sdg_targets_are_still_not_loaded_and_the_docs_say_so(self):
        self.assertEqual(self.n["ods_targets"], 0)
        for key in ("audit", "forms"):
            self.assertIn("169", DOCS[key].read_text(encoding="utf-8"),
                          f"{key} precisa dizer que as 169 metas não entraram")


class ClaimDocTests(unittest.TestCase):
    def test_every_rule_code_in_the_database_appears_in_the_document(self):
        with db_system() as c:
            codes = [r["code"] for r in c.query("SELECT code FROM claim_rules WHERE active")]
        texto = DOCS["claims"].read_text(encoding="utf-8")
        faltando = [code for code in codes if code not in texto]
        self.assertEqual(faltando, [], f"regra sem documentação: {faltando}")

    def test_every_derived_status_in_the_code_appears_in_the_document(self):
        from impacto.impact.claims import STATUS_LABEL
        texto = DOCS["claims"].read_text(encoding="utf-8")
        faltando = [s for s in STATUS_LABEL if s not in texto]
        self.assertEqual(faltando, [], f"situação derivada sem documentação: {faltando}")


class ReputationDocTests(unittest.TestCase):
    def test_every_dimension_in_the_database_appears_in_the_document(self):
        with db_system() as c:
            codes = [r["code"] for r in c.query(
                "SELECT code FROM reputation_dimensions WHERE active")]
        texto = DOCS["reputation"].read_text(encoding="utf-8")
        faltando = [code for code in codes if code not in texto]
        self.assertEqual(faltando, [], f"dimensão sem documentação: {faltando}")

    def test_the_document_declares_the_divergence_from_the_prompts(self):
        texto = DOCS["reputation"].read_text(encoding="utf-8")
        self.assertIn("divergência", texto.lower())
        self.assertIn("ranking", texto)


class SealDocTests(unittest.TestCase):
    def test_every_seal_rule_in_the_database_appears_in_the_document(self):
        with db_system() as c:
            codes = [r["code"] for r in c.query("SELECT code FROM seal_rules")]
        texto = DOCS["seals"].read_text(encoding="utf-8")
        faltando = [code for code in codes if code not in texto]
        self.assertEqual(faltando, [], f"critério de selo sem documentação: {faltando}")

    def test_the_relation_ladder_still_refuses_certified(self):
        """O documento da FASE 4 prometeu que a escada para em `audited`."""
        from impacto.impact.frameworks import RELATIONS
        self.assertNotIn("certified", RELATIONS)
        self.assertEqual(len(RELATIONS), 6)


class DecisionLogTests(unittest.TestCase):
    def test_the_decision_log_has_no_duplicate_numbers(self):
        texto = DOCS["decisions"].read_text(encoding="utf-8")
        nums = re.findall(r"^\| (\d{3}) \|", texto, re.MULTILINE)
        dup = {n for n in nums if nums.count(n) > 1}
        self.assertEqual(dup, set(), f"ADR duplicada: {sorted(dup)}")

    def test_this_round_registered_its_decisions(self):
        texto = DOCS["decisions"].read_text(encoding="utf-8")
        for n in range(191, 221):
            self.assertIn(f"| {n} |", texto, f"ADR-{n} não registrada")

    def test_every_round_decision_cites_a_consequence(self):
        """Linha de ADR sem consequência é opinião com número."""
        texto = DOCS["decisions"].read_text(encoding="utf-8")
        for linha in texto.splitlines():
            m = re.match(r"^\| (19[1-9]|2[01][0-9]|220) \|", linha)
            if not m:
                continue
            colunas = [c.strip() for c in linha.strip("|").split("|")]
            self.assertGreaterEqual(len(colunas), 5, linha[:80])
            self.assertGreater(len(colunas[3]), 20, f"ADR-{m.group(1)} sem consequência")
