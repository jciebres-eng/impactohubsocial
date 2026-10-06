"""v0.17.0 — Value Ledger e custo de IA.

O que estes testes protegem não é um cálculo: é a diferença entre MEDIDO e ESTIMADO. Um produto de
impacto que mostra "72h economizadas" com número que ninguém conferiu perde o direito de ser levado
a sério em todo o resto, e essa é a razão de a linha de referência nascer vazia.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import app_tx, db_system, grant_premium, make_admin, new_account


class ValueBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        grant_premium(cls.osc)
        cls.admin, cls.mfa = make_admin()

    def project(self, **extra) -> str:
        r = self.osc.post("/v1/projects", {
            "title": f"Projeto valor {uuid.uuid4().hex[:6]}",
            "summary": "Resumo suficiente para que o projeto seja avaliado por terceiros nesta rodada.",
            "problem": "Problema descrito com evidência local e fonte declarada no diagnóstico.",
            "objectives": "Objetivo geral e específicos declarados para o período de execução previsto.",
            "methodology": "Oficinas semanais com registro de presença e avaliação ao final de cada módulo.",
            "territory": "BR-MT", "budget_total_cents": 30_000_000, "causes": ["educacao"], "ods": [4],
            "beneficiaries_count": 200, "beneficiaries_description": "Jovens de 14 a 18 anos", **extra})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]


# ================================================================================================ a trava
class ValueHonestyTests(ValueBase):
    def test_baselines_ship_empty_so_nothing_is_estimated_out_of_the_box(self):
        """A trava central: de fábrica, nenhum número de tempo é produzido."""
        r = self.osc.get("/v1/value/types")
        self.assertEqual(r.status, 200, r)
        self.assertTrue(r.json["items"])
        for t in r.json["items"]:
            self.assertFalse(t["has_baseline"],
                             f"{t['key']} vem com linha de referência de fábrica — número que ninguém conferiu")
            self.assertIsNone(t["minutes_per_unit"])
            self.assertIsNone(t["source_name"])

    def test_counts_are_recorded_even_without_a_baseline(self):
        """Sem linha de referência, a CONTAGEM continua sendo registrada — ela é medida."""
        pid = self.project()
        r = self.osc.post("/v1/readiness/snapshots", {"project_id": pid})
        self.assertIn(r.status, (200, 201), r)
        ev = self.osc.get("/v1/value/events?event_type=readiness.evaluated")
        self.assertEqual(ev.status, 200, ev)
        self.assertTrue(ev.json["items"], "o retrato de prontidão tem de registrar valor")
        item = ev.json["items"][0]
        self.assertEqual(item["units"], 6, "seis dimensões avaliadas é contagem, não estimativa")
        self.assertIsNone(item["minutes_saved_estimate"])
        self.assertEqual(item["estimate_status"], "no_baseline")

    def test_a_number_without_a_source_is_refused_by_the_database(self):
        with db_system() as c, self.assertRaises(Exception) as e:
            c.run("INSERT INTO value_baselines(event_type, minutes_per_unit)"
                  " VALUES ('readiness.evaluated', 5.0)")
        self.assertIn("baseline_needs_source", str(e.exception))

    def test_declaring_a_baseline_with_a_source_starts_the_estimate(self):
        r = self.admin.post("/v1/admin/value/baselines", {
            "event_type": "risk.scan_completed", "minutes_per_unit": 3.5,
            "source_name": "Cronometragem interna com 8 analistas, setembro de 2026",
            "source_date": "2026-09-30",
            "method_note": "Tempo medido para conferir manualmente cada uma das 8 regras de risco "
                           "em 20 projetos reais, descartando o maior e o menor tempo."},
           )
        self.assertEqual(r.status, 201, r)
        pid = self.project()
        s = self.osc.post(f"/v1/projects/{pid}/risks/scan", {})
        self.assertIn(s.status, (200, 201), s)
        ev = self.osc.get("/v1/value/events?event_type=risk.scan_completed")
        self.assertTrue(ev.json["items"], ev.json)
        item = ev.json["items"][0]
        self.assertEqual(item["estimate_status"], "estimated")
        self.assertIsNotNone(item["minutes_saved_estimate"])
        self.assertAlmostEqual(float(item["minutes_saved_estimate"]), 3.5 * item["units"], places=2)

    def test_the_current_baseline_cannot_be_rewritten(self):
        """Corrigir a régua exige versão nova: o número de ontem explica a afirmação de ontem."""
        self.admin.post("/v1/admin/value/baselines", {
            "event_type": "document.assembled", "minutes_per_unit": 20.0,
            "source_name": "Medição interna outubro de 2026", "source_date": "2026-10-01",
            "method_note": "Tempo de montagem manual do mesmo documento por três analistas distintos."},
           )
        with db_system() as c, self.assertRaises(Exception) as e:
            c.run("UPDATE value_baselines SET minutes_per_unit = 999 WHERE event_type = 'document.assembled'"
                  " AND effective_until IS NULL")
        self.assertIn("imutável", str(e.exception).lower())
        # E a versão nova fecha a anterior, sem apagá-la.
        with db_system() as c:
            rows = c.query("SELECT minutes_per_unit, effective_until FROM value_baselines"
                           " WHERE event_type = 'document.assembled' ORDER BY effective_from")
        self.assertGreaterEqual(len(rows), 2, "a linha de fábrica tem de continuar no histórico")
        self.assertIsNotNone(rows[0]["effective_until"], "a anterior tem de ter vigência fechada")
        self.assertIsNone(rows[-1]["effective_until"], "só a última fica vigente")

    def test_the_summary_says_how_many_events_have_no_baseline(self):
        """"45 minutos" ao lado de "e 300 eventos sem régua" é honesto; o número sozinho não é."""
        pid = self.project()
        self.osc.post("/v1/readiness/snapshots", {"project_id": pid})
        r = self.osc.get("/v1/value/summary")
        self.assertEqual(r.status, 200, r)
        self.assertIn("events_without_baseline", r.json["totals"])
        self.assertGreater(r.json["totals"]["events"], 0)
        for word in ("medidas", "estimativa"):
            self.assertIn(word, r.json["note"].lower())


# ================================================================================================ não é cobrança
class ValueIsNotBillingTests(ValueBase):
    def test_the_ledger_is_append_only_for_the_application(self):
        pid = self.project()
        self.osc.post("/v1/readiness/snapshots", {"project_id": pid})
        with app_tx(self.osc) as c, self.assertRaises(Exception):
            c.run("UPDATE value_events SET units = 9999 WHERE org_id = $1", self.osc.org_id)
        with app_tx(self.osc) as c, self.assertRaises(Exception):
            c.run("DELETE FROM value_events WHERE org_id = $1", self.osc.org_id)

    def test_the_application_cannot_insert_a_value_event_directly(self):
        """Se pudesse, poderia escrever a estimativa de tempo à mão — que é o que não se quer poder."""
        with app_tx(self.osc) as c, self.assertRaises(Exception) as e:
            c.run("INSERT INTO value_events(event_type, org_id, units, minutes_saved_estimate,"
                  " estimate_status) VALUES ('readiness.evaluated', $1, 1, 99999, 'estimated')",
                  self.osc.org_id)
        self.assertTrue(str(e.exception), "a inserção direta tem de ser recusada")

    def test_another_org_never_sees_my_value_events(self):
        other = new_account("osc", compliance="approved")
        grant_premium(other)
        pid = self.project()
        self.osc.post("/v1/readiness/snapshots", {"project_id": pid})
        mine = self.osc.get("/v1/value/events").json["items"]
        theirs = other.get("/v1/value/events").json["items"]
        self.assertTrue(mine)
        self.assertEqual([x for x in theirs if x["id"] in {y["id"] for y in mine}], [])


# ================================================================================================ custo de IA
class AiCostTests(ValueBase):
    def test_the_price_table_ships_empty_and_cost_is_null_not_zero(self):
        r = self.admin.get("/v1/admin/ai/cost")
        self.assertEqual(r.status, 200, r)
        self.assertIsNone(r.json["totals"]["cost_cents_estimate"],
                          "sem tabela de preço o custo é NULO; zero pareceria custo apurado")
        self.assertIn("nasce vazia", r.json["note"].lower())

    def test_declaring_a_price_prices_future_calls(self):
        r = self.admin.post("/v1/admin/ai/prices", {
            "provider": "local", "model": "local-stub",
            "input_per_mtok_cents": 0.0, "output_per_mtok_cents": 0.0,
            "source_name": "Motor local: não há custo de provedor externo",
            "source_date": "2026-10-01"})
        self.assertEqual(r.status, 201, r)
        # E o preço também é imutável.
        with db_system() as c, self.assertRaises(Exception) as e:
            c.run("UPDATE ai_price_table SET input_per_mtok_cents = 50 WHERE provider = 'local'"
                  " AND effective_until IS NULL")
        self.assertIn("imutável", str(e.exception).lower())

    def test_a_price_without_a_source_is_refused(self):
        with db_system() as c, self.assertRaises(Exception) as e:
            c.run("INSERT INTO ai_price_table(provider, model, input_per_mtok_cents)"
                  " VALUES ('inventado', 'modelo-x', 12.5)")
        self.assertIn("ai_price_needs_source", str(e.exception))

    def test_the_price_table_is_invisible_to_organizations(self):
        """Preço de provedor é custo NOSSO: a organização não tem por que ver."""
        with app_tx(self.osc) as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM ai_price_table"), 0)


# ================================================================================================ invariante
class ValueVocabularyTests(ValueBase):
    def test_the_python_list_matches_the_table(self):
        """Vocabulário duplicado divergiu uma vez (notify.PRIORITIES × CHECK do banco). Não outra."""
        from impacto.economics import value_ledger
        with db_system() as c:
            db = {r["key"] for r in c.query("SELECT key FROM value_event_types")}
        self.assertEqual(set(value_ledger.TYPES), db,
                         "a lista Python e value_event_types têm de ser a mesma")

    def test_every_type_declares_what_a_unit_means(self):
        """Sem isso, `units` seria número sem significado, somável com qualquer outro."""
        for t in self.osc.get("/v1/value/types").json["items"]:
            self.assertGreaterEqual(len(t["what_counts"]), 20, t["key"])
            self.assertGreaterEqual(len(t["unit_label"]), 3, t["key"])

    def test_the_estimate_status_vocabulary_matches_the_database_check(self):
        from impacto.economics import value_ledger
        with db_system() as c:
            defn = c.scalar("SELECT pg_get_constraintdef(oid) FROM pg_constraint"
                            " WHERE conrelid = 'value_events'::regclass AND contype = 'c'"
                            "   AND pg_get_constraintdef(oid) LIKE '%estimate_status%'")
        for v in value_ledger.ESTIMATE_STATUS:
            self.assertIn(v, defn, f"{v} não está no CHECK do banco")


if __name__ == "__main__":
    unittest.main()
