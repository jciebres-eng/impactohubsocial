"""v0.20.0 — procedência de dado de governo e o conceito de dado DESATUALIZADO.

O QUE ESTES TESTES PROTEGEM

A plataforma inteira é um argumento sobre evidência. Dado de terceiro — IBGE, DATASUS, INEP, ONU —
é o único lugar onde ela repete número que não produziu, e até a v0.19.0 ela repetia sem saber dizer
sob qual licença o número veio, de qual arquivo, publicado quando, nem se já envelheceu.

O teste central deste arquivo é `undeclared`. Quando ninguém declarou em quantos meses um conjunto de
dados envelhece, a resposta honesta é "não declarado" — jamais "atual". Tratar silêncio como
atualidade é a forma mais discreta de um produto de evidência mentir, e é a forma mais fácil de
alguém escrever por acidente (`COALESCE(estado, 'current')` é uma linha).
"""
from __future__ import annotations

import pathlib
import subprocess
import unittest
from datetime import date, timedelta

from tests.support import ROOT, db_system, make_admin, new_account, owner_conn

SCRIPT = ROOT / "scripts" / "import_ods_targets.py"


def _dataset(admin, **over) -> dict:
    corpo = {
        "key": "ibge.censo", "version": "2022-rev1", "publisher": "IBGE",
        "dataset": "Censo Demográfico 2022", "url": "https://www.ibge.gov.br/censo2022",
        "published_at": "2023-06-28", "retrieved_at": "2026-10-06",
        "geographic_scope": "country", "license": "não declarada pela fonte",
        "file_name": "censo2022.csv", "file_sha256": "a" * 64, "rows_loaded": 5570,
        "stale_after_months": 120,
    }
    corpo.update(over)
    r = admin.post("/v1/admin/datasets", corpo)
    assert r.status == 201, r
    return r.json


class FreshnessTests(unittest.TestCase):
    """As quatro respostas de `data_freshness`, e a que não pode nunca sair errada."""

    def test_a_dataset_without_a_declared_term_is_never_reported_as_current(self):
        with db_system() as c:
            estado, _, nota = c.one(
                "SELECT state, months_old, note FROM data_freshness($1, NULL)",
                date.today().isoformat()).values()
        self.assertEqual(estado, "undeclared",
                         "silêncio sobre o prazo NÃO é atualidade: o dado pode ser de ontem e a "
                         "resposta continua sendo 'não declarado'")
        self.assertNotEqual(estado, "current")
        self.assertIn("não inventa o prazo", nota)

    def test_a_date_past_the_declared_term_is_stale(self):
        antiga = (date.today() - timedelta(days=365 * 12)).isoformat()
        with db_system() as c:
            row = c.one("SELECT state, months_old, note FROM data_freshness($1, 120)", antiga)
        self.assertEqual(row["state"], "stale")
        self.assertGreaterEqual(row["months_old"], 140)
        self.assertIn("passou do prazo declarado", row["note"])

    def test_a_date_inside_the_declared_term_is_current(self):
        recente = (date.today() - timedelta(days=200)).isoformat()
        with db_system() as c:
            row = c.one("SELECT state, months_old, note FROM data_freshness($1, 120)", recente)
        self.assertEqual(row["state"], "current")
        self.assertIn("dentro do prazo declarado", row["note"])

    def test_without_a_reference_date_the_answer_is_unknown_not_current(self):
        with db_system() as c:
            row = c.one("SELECT state, months_old, note FROM data_freshness(NULL, 12)")
        self.assertEqual(row["state"], "unknown")
        self.assertIsNone(row["months_old"])
        self.assertIn("não dá para dizer", row["note"])

    def test_the_four_states_are_the_only_ones_the_function_can_return(self):
        """Fecha o vocabulário: um quinto estado inventado em outra rodada quebra aqui."""
        sql = (ROOT / "backend" / "migrations"
               / "0040_v0200_external_provenance.sql").read_text(encoding="utf-8")
        corpo = sql.split("CREATE FUNCTION data_freshness")[1].split("$$")[1]
        for estado in ("'unknown'", "'undeclared'", "'stale'", "'current'"):
            self.assertIn(estado, corpo)


class DatasetRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin, _ = make_admin()
        cls.user = new_account("osc")

    def test_1_the_registry_starts_empty_and_says_so(self):
        r = self.user.get("/v1/datasets")
        self.assertEqual(r.status, 200, r)
        self.assertIn("Vazio significa", r.json["note"])
        self.assertIn("nunca 'atual'", r.json["freshness_rule"])

    def test_2_a_dataset_records_the_nine_provenance_fields(self):
        criado = _dataset(self.admin, version="2022-rev-campos")
        linha = next(d for d in self.user.get("/v1/datasets").json["items"]
                     if d["id"] == criado["id"])
        for campo in ("publisher", "dataset", "url", "published_at", "retrieved_at",
                      "geographic_scope", "license", "file_sha256", "stale_after_months"):
            self.assertIsNotNone(linha[campo], f"{campo} não foi registrado")
        self.assertNotEqual(linha["published_at"], linha["retrieved_at"],
                            "a data em que a FONTE publicou é diferente da data da consulta")

    def test_3_the_license_is_mandatory(self):
        r = self.admin.post("/v1/admin/datasets", {
            "key": "sem.licenca", "version": "1", "publisher": "Órgão", "dataset": "Conjunto",
            "retrieved_at": "2026-10-06", "geographic_scope": "country"})
        self.assertEqual(r.status, 422, "dado de terceiro sem licença é decisão por omissão")

    def test_4_provenance_is_immutable_once_recorded(self):
        criado = _dataset(self.admin, version="2022-rev-imutavel")
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("UPDATE external_datasets SET publisher = 'Outro órgão' WHERE id = $1",
                       criado["id"])
            self.assertIn("imutável", str(e.exception))
        finally:
            oc.close()

    def test_5_an_ordinary_user_cannot_register_provenance(self):
        r = self.user.post("/v1/admin/datasets", {
            "key": "tentativa", "version": "1", "publisher": "Qualquer", "dataset": "Qualquer",
            "retrieved_at": "2026-10-06", "geographic_scope": "country", "license": "CC0"})
        self.assertIn(r.status, (401, 403), r)


class TerritoryProfileFreshnessTests(unittest.TestCase):
    """O perfil do território passa a dizer que um número envelheceu — e quando não sabe."""

    @classmethod
    def setUpClass(cls):
        cls.admin, _ = make_admin()
        cls.user = new_account("osc")
        cls.velho = _dataset(cls.admin, key="ibge.antigo", version="2010",
                             stale_after_months=60, published_at="2011-01-01")

    def test_1_an_indicator_linked_to_an_old_dataset_is_reported_as_stale(self):
        r = self.admin.post("/v1/admin/territory-indicators", {
            "territory": "BR-AC", "code": "taxa_analfabetismo", "value": 11.2,
            "reference_date": "2010-12-31", "source_name": "IBGE — Censo 2010",
            "source_date": "2026-10-06", "dataset_id": self.velho["id"]})
        self.assertEqual(r.status, 201, r)
        perfil = self.user.get("/v1/territories/BR-AC").json
        linha = next(i for i in perfil["indicators"] if i["code"] == "taxa_analfabetismo")
        self.assertEqual(linha["freshness"], "stale")
        self.assertEqual(linha["provenance"]["publisher"], "IBGE")
        self.assertEqual(linha["provenance"]["license"], "não declarada pela fonte")
        self.assertGreater(linha["months_old"], 60)
        self.assertIn("taxa_analfabetismo", perfil["freshness"]["stale"])

    def test_2_an_indicator_with_no_dataset_is_undeclared_never_current(self):
        r = self.admin.post("/v1/admin/territory-indicators", {
            "territory": "BR-AP", "code": "taxa_analfabetismo", "value": 6.0,
            "reference_date": "2026-01-31", "source_name": "Declarado à mão no teste",
            "source_date": "2026-10-06"})
        self.assertEqual(r.status, 201, r)
        perfil = self.user.get("/v1/territories/BR-AP").json
        linha = next(i for i in perfil["indicators"] if i["code"] == "taxa_analfabetismo")
        self.assertEqual(linha["freshness"], "undeclared",
                         "número recente SEM prazo declarado não pode virar 'current'")
        self.assertIsNone(linha["provenance"])
        self.assertIn("taxa_analfabetismo", perfil["freshness"]["undeclared"])
        self.assertNotIn("taxa_analfabetismo", perfil["freshness"]["stale"])

    def test_3_an_indicator_never_measured_carries_no_invented_freshness(self):
        perfil = self.user.get("/v1/territories/BR-RR").json
        nao_medido = next(i for i in perfil["indicators"] if not i["measured"])
        self.assertEqual(nao_medido["freshness"], "unknown")
        self.assertIsNone(nao_medido["provenance"])
        self.assertEqual(nao_medido["freshness_note"],
                         "indicador não medido para este território")

    def test_4_the_profile_explains_what_undeclared_means(self):
        nota = self.user.get("/v1/territories/BR-AC").json["freshness"]["note"]
        self.assertIn("ninguém declarou prazo", nota)
        self.assertIn("em vez de chamar o dado de atual", nota)

    def test_5_an_indicator_cannot_point_at_a_dataset_that_does_not_exist(self):
        r = self.admin.post("/v1/admin/territory-indicators", {
            "territory": "BR-BA", "code": "taxa_analfabetismo", "value": 1.0,
            "reference_date": "2024-12-31", "source_name": "Fonte", "source_date": "2026-10-06",
            "dataset_id": "00000000-0000-0000-0000-000000000000"})
        self.assertEqual(r.status, 404, r)


class OdsTargetImporterTests(unittest.TestCase):
    """O importador que a documentação dizia existir desde a v0.18.0 — e não existia."""

    def test_1_the_importer_exists(self):
        self.assertTrue(SCRIPT.exists(),
                        "`IMPACT_FRAMEWORK_AUDIT.md` afirmava entregar este arquivo na v0.18.0")

    def test_2_the_audit_document_no_longer_claims_it_was_delivered_earlier(self):
        texto = (ROOT / "IMPACT_FRAMEWORK_AUDIT.md").read_text(encoding="utf-8")
        self.assertIn("CORREÇÃO (v0.20.0)", texto)
        self.assertIn("O arquivo não existia no repositório", texto)

    def test_3_no_migration_embeds_the_official_ods_target_text(self):
        for sql in (ROOT / "backend" / "migrations").glob("*.sql"):
            self.assertNotIn("INSERT INTO ods_targets", sql.read_text(encoding="utf-8"),
                             f"{sql.name} transcreve meta de ODS de memória")

    def test_4_it_refuses_to_run_without_provenance(self):
        out = subprocess.run(["python3", str(SCRIPT), "--file", "x.csv"],
                             capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        for exigido in ("--publisher", "--dataset", "--license", "--retrieved-on"):
            self.assertIn(exigido, out.stderr)

    def test_5_it_refuses_an_invalid_line_instead_of_loading_half_the_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            arq = pathlib.Path(d) / "metas.csv"
            arq.write_text("codigo,descricao\n1.1,Erradicar a pobreza extrema\n"
                           "99.9,Meta de um ODS que não existe\n", encoding="utf-8")
            out = subprocess.run(
                ["python3", str(SCRIPT), "--file", str(arq), "--publisher", "ONU",
                 "--dataset", "Metas", "--version", "t", "--license", "CC BY 3.0 IGO",
                 "--source-url", "https://unstats.un.org/", "--retrieved-on", "2026-10-06",
                 "--dry-run"],
                capture_output=True, text=True, cwd=str(ROOT))
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("NADA foi gravado", out.stderr)
        self.assertIn("ODS fora de 1..17", out.stderr)

    def test_6_a_valid_file_passes_the_dry_run_without_touching_the_database(self):
        import tempfile
        antes = self._targets()
        with tempfile.TemporaryDirectory() as d:
            arq = pathlib.Path(d) / "metas.csv"
            arq.write_text("codigo,descricao\n1.1,Erradicar a pobreza extrema em todos os lugares\n",
                           encoding="utf-8")
            out = subprocess.run(
                ["python3", str(SCRIPT), "--file", str(arq), "--publisher", "ONU",
                 "--dataset", "Metas", "--version", "t", "--license", "CC BY 3.0 IGO",
                 "--source-url", "https://unstats.un.org/", "--retrieved-on", "2026-10-06",
                 "--dry-run"],
                capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("nada foi gravado", out.stdout)
        self.assertEqual(self._targets(), antes)

    def test_7_the_importer_does_not_distribute_un_emblems(self):
        texto = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("NÃO distribui os logos", texto)

    @staticmethod
    def _targets() -> int:
        with db_system() as c:
            return c.scalar("SELECT count(*) FROM ods_targets")
