"""v0.18.0 — busca incremental com procedência, e o componente que não sobrescreve em silêncio.

Duas regras sob teste:

1. **Toda sugestão diz de onde veio.** `origin` e `origin_label` em cada linha, com fonte e data
   quando existem. Sugestão sem origem é sugestão que a pessoa não pode avaliar.
2. **Sugestão de histórico é da PRÓPRIA organização.** `my_suppliers` e `my_projects` não devolvem
   nada de outra organização — autocomplete é uma das formas mais silenciosas de vazar dado.

A terceira regra vive na interface (`web/src/ui/suggest.tsx`) e é verificada aqui por leitura do
arquivo: o componente pede confirmação antes de substituir texto digitado.
"""
from __future__ import annotations

import pathlib
import unittest

from tests.support import new_account, owner_conn

COMPONENT = (pathlib.Path(__file__).resolve().parents[2] / "web" / "src" / "ui" / "suggest.tsx")


class LookupBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")


# ================================================================================================ catálogo
class CatalogTests(LookupBase):
    def test_the_catalog_declares_the_contract_and_the_origins(self):
        r = self.osc.get("/v1/lookups")
        self.assertEqual(r.status, 200, r)
        self.assertGreaterEqual(len(r.json["items"]), 10)
        self.assertIn("origem", r.json["contract"])
        self.assertIn("NUNCA", r.json["never_overwrites"])
        for item in r.json["items"]:
            self.assertTrue(item["origins"], item["key"])
            for o in item["origins"]:
                self.assertTrue(o["label"])

    def test_an_unknown_lookup_is_refused(self):
        r = self.osc.get("/v1/lookups/usuarios?q=a")
        self.assertEqual(r.json["code"], "unknown_lookup", r)


# ================================================================================================ procedência
class ProvenanceTests(LookupBase):
    def test_every_suggestion_of_every_lookup_declares_its_origin(self):
        chaves = [i["key"] for i in self.osc.get("/v1/lookups").json["items"]]
        vistos = 0
        for key in chaves:
            r = self.osc.get(f"/v1/lookups/{key}?q=a&limit=5")
            self.assertEqual(r.status, 200, f"{key}: {r}")
            for item in r.json["items"]:
                vistos += 1
                self.assertTrue(item["origin"], f"{key} sem origin")
                self.assertTrue(item["origin_label"], f"{key} sem origin_label")
                self.assertIn("verified", item)
        self.assertGreater(vistos, 10, "a varredura precisa ver sugestões de verdade")

    def test_the_seeded_territories_are_platform_knowledge_not_official_load(self):
        """A honestidade mais específica desta rodada: 27 UFs digitadas por mim não são IBGE."""
        itens = self.osc.get("/v1/lookups/territories?q=mato").json["items"]
        self.assertTrue(itens)
        for i in itens:
            self.assertEqual(i["origin"], "platform_knowledge")
            self.assertFalse(i["verified"])
            self.assertIn("conferir", i["origin_label"])

    def test_an_officially_loaded_territory_is_marked_as_such(self):
        oc = owner_conn()
        oc.run("INSERT INTO territories(code, kind, name, parent_code, uf, ibge_code, source_name,"
               " source_url, source_date, from_official_load)"
               " VALUES ('BR-MT-5103403','municipality','Cuiabá Carga','BR-MT','MT','5103403',"
               " 'IBGE — Divisão territorial brasileira', 'https://www.ibge.gov.br',"
               " current_date, true) ON CONFLICT (code) DO UPDATE SET from_official_load = true,"
               " name = 'Cuiabá Carga', source_name = 'IBGE — Divisão territorial brasileira'")
        item = next(i for i in self.osc.get("/v1/lookups/territories?q=Cuiab").json["items"]
                    if i["value"] == "BR-MT-5103403")
        self.assertEqual(item["origin"], "official_load")
        self.assertTrue(item["verified"])
        self.assertIn("IBGE", item["source_name"])

    def test_editorial_lists_say_they_are_editorial(self):
        for key in ("equity_barriers", "materiality_topics", "determinants", "seal_rules"):
            itens = self.osc.get(f"/v1/lookups/{key}?limit=3").json["items"]
            self.assertTrue(itens, key)
            for i in itens:
                self.assertEqual(i["origin"], "platform_editorial", key)

    def test_the_ods_targets_lookup_is_empty_until_the_official_load(self):
        """Honesto por ausência: as 169 metas oficiais não entraram, então a busca não devolve nada."""
        self.assertEqual(self.osc.get("/v1/lookups/ods_targets?q=4").json["items"], [])
        self.assertTrue(self.osc.get("/v1/lookups/ods?q=4").json["items"])


# ================================================================================================ isolamento
class IsolationTests(LookupBase):
    def test_supplier_history_never_crosses_organizations(self):
        pid = self.osc.post("/v1/projects", {
            "title": "Projeto com fornecedor no histórico",
            "summary": "Projeto criado para exercitar a sugestão de fornecedor na v0.18.0.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 30, "budget_total_cents": 900_000}).json["id"]
        owner_conn().run(
            "INSERT INTO expenses(project_id, org_id, description, supplier_name, amount_cents,"
            " paid_on) VALUES ($1,$2,'Livros','Livraria Sertão Vivo',50000,current_date)",
            pid, self.osc.org_id)
        meus = self.osc.get("/v1/lookups/my_suppliers?q=Sert").json["items"]
        self.assertTrue(meus)
        self.assertEqual(meus[0]["origin"], "your_organization")
        self.assertEqual(self.other.get("/v1/lookups/my_suppliers?q=Sert").json["items"], [])

    def test_project_suggestions_never_cross_organizations(self):
        titulo = "Projeto visível apenas para quem o criou"
        self.osc.post("/v1/projects", {
            "title": titulo,
            "summary": "Projeto criado para exercitar o isolamento da sugestão de projeto.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 30, "budget_total_cents": 900_000})
        self.assertTrue(self.osc.get("/v1/lookups/my_projects?q=apenas").json["items"])
        self.assertEqual(self.other.get("/v1/lookups/my_projects?q=apenas").json["items"], [])

    def test_an_indicator_created_by_one_organization_is_not_suggested_to_another(self):
        r = self.osc.post("/v1/indicators/catalog", {
            "code": f"ind_proprio_{self.osc.org_id[:8]}", "name": "Indicador próprio da OSC",
            "unit": "pessoas", "definition": "Indicador criado pela organização para este teste."})
        self.assertEqual(r.status, 201, r)
        # a consulta vai percent-encoded: o cliente de teste não escapa a URL por conta própria
        meus = self.osc.get("/v1/lookups/indicators?q=pr%C3%B3prio").json["items"]
        self.assertTrue(meus)
        self.assertEqual(meus[0]["origin"], "your_organization")
        self.assertEqual(self.other.get("/v1/lookups/indicators?q=pr%C3%B3prio").json["items"], [])


# ================================================================================================ robustez
class RobustnessTests(LookupBase):
    def test_a_percent_sign_is_text_and_not_a_wildcard(self):
        """Sem escapar, quem digita "%" recebe o catálogo inteiro como se fosse sugestão."""
        self.assertEqual(self.osc.get("/v1/lookups/territories?q=%25").json["items"], [])
        self.assertEqual(self.osc.get("/v1/lookups/territories?q=_").json["items"], [])

    def test_the_limit_is_respected_and_bounded(self):
        self.assertLessEqual(len(self.osc.get("/v1/lookups/ods?limit=3").json["items"]), 3)
        self.assertEqual(self.osc.get("/v1/lookups/ods?limit=900").status, 422)

    def test_the_search_is_accent_and_case_tolerant(self):
        self.assertTrue(self.osc.get("/v1/lookups/territories?q=MATO").json["items"])
        self.assertTrue(self.osc.get("/v1/lookups/territories?q=mato").json["items"])


# ================================================================================================ o componente
class ComponentTests(unittest.TestCase):
    """O que a interface promete, lido do arquivo — para a promessa não ficar só no documento."""

    def test_the_component_asks_before_replacing_typed_text(self):
        src = COMPONENT.read_text(encoding="utf-8")
        self.assertIn("Manter o que escrevi", src)
        self.assertIn("Usar a sugestão", src)
        self.assertIn("Voltar ao que eu havia escrito", src)

    def test_the_component_shows_the_origin_of_every_suggestion(self):
        src = COMPONENT.read_text(encoding="utf-8")
        self.assertIn("OriginTag", src)
        self.assertIn("origin_label", src)
        self.assertIn("source_name", src)

    def test_the_component_reports_provenance_back_to_the_form(self):
        src = COMPONENT.read_text(encoding="utf-8")
        self.assertIn("SuggestProvenance", src)
        self.assertIn('filled_by: "typed"', src)
        self.assertIn('filled_by: "suggestion"', src)
        self.assertIn("replaced_text", src)

    def test_the_progressive_form_never_hides_filled_work(self):
        src = COMPONENT.read_text(encoding="utf-8")
        self.assertIn("Abrir agora mesmo assim", src)
        self.assertIn("perda de trabalho", src)
