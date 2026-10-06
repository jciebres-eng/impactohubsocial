"""v0.18.0 — território como catálogo, e a honestidade sobre o que não se sabe.

Duas colunas carregam a honestidade desta camada, e os testes existem para elas:

* `from_official_load` separa "achamos que é" (país, regiões e as 27 UFs semeadas pela migração) de
  "está no arquivo oficial" (município, que só entra por importação);
* `measured` no perfil: toda definição ativa aparece, medida ou não. Devolver só o que foi medido
  daria a impressão de que o resto não importa — e é o resto que explica a lacuna.
"""
from __future__ import annotations

import pathlib
import subprocess
import unittest

from tests.support import OWNER_DSN, db_system, make_admin, new_account, owner_conn

REPO = pathlib.Path(__file__).resolve().parents[2]


class CatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")
        cls.admin, _ = make_admin()

    def test_the_catalog_ships_with_the_country_the_regions_and_the_27_states(self):
        with db_system() as c:
            n = {r["kind"]: r["total"] for r in c.query(
                "SELECT kind, count(*) AS total FROM territories GROUP BY kind")}
        self.assertEqual(n.get("country"), 1)
        self.assertEqual(n.get("region"), 5)
        self.assertEqual(n.get("state"), 27, "26 estados e o Distrito Federal")

    def test_nothing_seeded_claims_to_come_from_an_official_file(self):
        """A trava de honestidade: o que a migração semeou não finge ser carga oficial."""
        with db_system() as c:
            claiming = c.query("SELECT code FROM territories WHERE from_official_load"
                               " AND kind <> 'municipality'")
        self.assertEqual(claiming, [],
                         "só município importado pode ter from_official_load verdadeiro")
        with db_system() as c:
            for row in c.query("SELECT code, source_name FROM territories WHERE kind = 'state'"):
                self.assertIn("conferir", row["source_name"].lower(), row["code"])

    def test_no_territorial_indicator_was_embedded_in_the_migration(self):
        """`territory_indicators` nasce vazia: nenhum número do IBGE foi transcrito de memória."""
        for sql in (REPO / "backend" / "migrations").glob("*.sql"):
            self.assertNotIn("INSERT INTO territory_indicators", sql.read_text(encoding="utf-8"),
                             f"{sql.name} embute indicador territorial")

    def test_the_status_route_declares_the_incompleteness(self):
        r = self.c.get("/v1/territories/catalog-status")
        self.assertEqual(r.status, 200, r)
        self.assertGreater(r.json["definitions"], 10)
        self.assertIn("importação de arquivo oficial", r.json["note"])
        self.assertIn("5.570 municípios", r.json["note"])

    def test_the_label_falls_back_to_the_code_when_the_catalog_does_not_know(self):
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT territory_label($1)", "BR-MT"), "Mato Grosso")
            self.assertEqual(c.scalar("SELECT territory_label($1)", "BR-XX-9999999"),
                             "BR-XX-9999999", "nunca inventa nome")

    def test_the_chain_resolves_what_it_knows_and_marks_what_it_does_not(self):
        r = self.c.get("/v1/territories/BR-MT")
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["in_catalog"])
        self.assertEqual([c["name"] for c in r.json["chain"]],
                         ["Brasil", "Centro-Oeste", "Mato Grosso"])
        desconhecido = self.c.get("/v1/territories/BR-XX-9999999").json
        self.assertFalse(desconhecido["in_catalog"])
        self.assertIn("NÃO está no catálogo", desconhecido["note"])

    def test_a_municipality_cannot_be_created_without_uf_and_ibge_code(self):
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("INSERT INTO territories(code,kind,name,parent_code,source_name)"
                       " VALUES ('BR-MT-9999999','municipality','Cidade sem UF','BR-MT','teste')")
            self.assertIn("código IBGE de 7 dígitos", str(e.exception))
        finally:
            oc.close()

    def test_the_profile_shows_what_was_not_measured_with_the_same_weight(self):
        r = self.c.get("/v1/territories/BR-MT")
        self.assertEqual(r.status, 200, r)
        self.assertEqual(len(r.json["indicators"]), r.json["definition_count"])
        self.assertGreater(r.json["definition_count"], 10)
        nao_medidos = [i for i in r.json["indicators"] if not i["measured"]]
        self.assertTrue(nao_medidos, "o que não foi medido tem de aparecer")
        self.assertIn("é informação, não ausência de informação", r.json["note"])

    def test_a_context_indicator_is_marked_as_context_not_performance(self):
        defs = self.c.get("/v1/territories/definitions").json
        ctx = [d for d in defs["items"] if d["direction"] == "context"]
        self.assertTrue(ctx, "tem de existir indicador marcado como contexto")
        self.assertIn("tratar contexto como desempenho", defs["note"])
        for d in defs["items"]:
            self.assertIn("editorial", d["source_note"].lower())

    def test_an_indicator_published_by_the_admin_carries_its_source(self):
        r = self.admin.post("/v1/admin/territory-indicators", {
            "territory": "BR-MT", "code": "taxa_analfabetismo", "value": 5.4,
            "reference_date": "2022-12-31", "source_name": "Fonte declarada pelo teste",
            "source_date": "2026-10-06"})
        self.assertEqual(r.status, 201, r)
        perfil = self.c.get("/v1/territories/BR-MT").json
        linha = next(i for i in perfil["indicators"] if i["code"] == "taxa_analfabetismo")
        self.assertTrue(linha["measured"])
        self.assertEqual(linha["source_name"], "Fonte declarada pelo teste")

    def test_a_published_indicator_is_immutable_and_versioned(self):
        self.admin.post("/v1/admin/territory-indicators", {
            "territory": "BR-GO", "code": "taxa_desocupacao", "value": 7.1,
            "reference_date": "2024-12-31", "source_name": "Primeira versão",
            "source_date": "2026-10-06"})
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e:
                oc.run("UPDATE territory_indicators SET value = 1 WHERE territory = 'BR-GO'"
                       " AND effective_until IS NULL")
            self.assertIn("imutável", str(e.exception))
        finally:
            oc.close()
        self.admin.post("/v1/admin/territory-indicators", {
            "territory": "BR-GO", "code": "taxa_desocupacao", "value": 6.8,
            "reference_date": "2025-12-31", "source_name": "Segunda versão",
            "source_date": "2026-10-06"})
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM territory_indicators"
                                      " WHERE territory = 'BR-GO' AND effective_until IS NULL"), 1)
            self.assertEqual(c.scalar("SELECT count(*) FROM territory_indicators"
                                      " WHERE territory = 'BR-GO'"), 2, "a versão antiga fica")

    def test_an_indicator_for_a_territory_outside_the_catalog_is_refused(self):
        r = self.admin.post("/v1/admin/territory-indicators", {
            "territory": "BR-MT-9999999", "code": "taxa_analfabetismo", "value": 1.0,
            "reference_date": "2022-12-31", "source_name": "Fonte", "source_date": "2026-10-06"})
        self.assertEqual(r.status, 404, r)
        self.assertIn("importe-o antes", r.json["title"])


class SearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")

    def test_search_finds_by_name_without_accents(self):
        r = self.c.get("/v1/territories/search?q=goias")
        self.assertEqual(r.status, 200, r)
        self.assertIn("Goiás", [i["name"] for i in r.json["items"]])

    def test_search_finds_by_partial_name(self):
        r = self.c.get("/v1/territories/search?q=rio%20grande")
        nomes = [i["name"] for i in r.json["items"]]
        self.assertIn("Rio Grande do Sul", nomes)
        self.assertIn("Rio Grande do Norte", nomes)

    def test_search_finds_by_code(self):
        r = self.c.get("/v1/territories/search?q=BR-MT")
        self.assertTrue(any(i["code"] == "BR-MT" for i in r.json["items"]))

    def test_search_requires_two_characters(self):
        r = self.c.get("/v1/territories/search?q=a")
        self.assertEqual(r.json["items"], [])
        self.assertIn("dois caracteres", r.json["note"])

    def test_search_can_be_narrowed_by_kind(self):
        r = self.c.get("/v1/territories/search?q=a&kind=state")
        self.assertEqual(r.json["items"], [], "o limite de dois caracteres vale sempre")
        r2 = self.c.get("/v1/territories/search?q=ma&kind=state")
        self.assertTrue(all(i["kind"] == "state" for i in r2.json["items"]))

    def test_the_literal_route_is_not_captured_by_the_parameter(self):
        """`/v1/territories/search` não pode ser lida como `/v1/territories/{code}`.

        Esse defeito já aconteceu neste projeto ("rota literal capturada por parâmetro") e o teste
        existe para que não volte.
        """
        self.assertEqual(self.c.get("/v1/territories/search?q=mato").status, 200)
        self.assertEqual(self.c.get("/v1/territories/catalog-status").status, 200)
        self.assertEqual(self.c.get("/v1/territories/definitions").status, 200)


class ImporterTests(unittest.TestCase):
    """O importador é a porta do dado oficial, e ele recusa arquivo sem procedência."""

    def test_it_refuses_to_run_without_the_source_metadata(self):
        out = subprocess.run(
            ["python3", "scripts/import_territories.py", "--file", "/dev/null"],
            cwd=REPO, capture_output=True, text=True)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("--source-name", out.stderr + out.stdout)

    def test_it_refuses_a_file_whose_ibge_code_does_not_match_the_state(self):
        """A verificação que pega arquivo trocado: os dois primeiros dígitos são o código da UF."""
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write("codigo_ibge,nome,uf\n5105150,Cidade Errada,SP\n")
            path = fh.name
        out = subprocess.run(
            ["python3", "scripts/import_territories.py", "--file", path,
             "--source-name", "Arquivo de teste", "--source-url", "https://exemplo.invalid/x",
             "--source-date", "2026-10-06"],
            cwd=REPO, capture_output=True, text=True,
            env={**__import__("os").environ, "DB": OWNER_DSN})
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("não pertence a SP", out.stderr)
        self.assertIn("NADA foi gravado", out.stderr)


if __name__ == "__main__":
    unittest.main()
