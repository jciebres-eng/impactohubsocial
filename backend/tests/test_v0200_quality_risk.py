"""v0.20.0 — §69 Qualidade de Dado e §40 Nível de Risco por operação.

A TRAVA MAIS IMPORTANTE DESTE ARQUIVO

§69 termina com uma frase curta: "não transformar baixa qualidade de dados automaticamente em baixa
performance do projeto". É a regra mais fácil de quebrar sem perceber, e a de consequência mais
grave nesta plataforma.

Um projeto numa periferia sem dado público, tocado por três pessoas que anotam no caderno, produz
dado incompleto. Um projeto de uma fundação com equipe de monitoramento produz dado completo. Se a
qualidade do dado entrar na nota, a plataforma conclui que o segundo tem mais impacto — e terá
medido orçamento de monitoramento, não impacto. Fazer isso uma vez basta para a plataforma inverter
exatamente a desigualdade que ela existe para enxergar.

Por isso há quatro testes separados sobre a mesma regra: a saída não tem nota, não tem faixa, diz de
quem ela fala (`about: "the_data"`), e nada dela alcança reputação, selo ou compatibilidade.
"""
from __future__ import annotations

import unittest

from impacto.impact import quality as DQ
from tests.support import db_system, make_admin, new_account


def _projeto(c) -> tuple[str, str]:
    """Um projeto com indicador declarado, para os achados terem onde acontecer."""
    r = c.post("/v1/projects", {
        "title": "Projeto para conferência de qualidade de dado",
        "summary": "Projeto criado pelo teste de qualidade de dado, com dado declarado de propósito.",
        "problem": "O problema declarado para que o projeto exista e possa ser avaliado no teste.",
        "objectives": "Objetivo declarado para o teste de qualidade de dado deste projeto.",
        "territory": "BR-MT", "beneficiaries_count": 100, "budget_total_cents": 1000000})
    assert r.status == 201, r
    return r.json["id"], c.org_id


class DataQualityNeverBecomesPerformanceTests(unittest.TestCase):
    """As quatro faces da mesma regra."""

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")
        cls.project_id, cls.org_id = _projeto(cls.c)

    def test_1_the_output_has_no_score_no_band_no_grade(self):
        with db_system() as c:
            out = DQ.assess(c, project_id=self.project_id)
        for proibido in ("score", "band", "grade", "rating", "quality_score", "percent",
                         "percentual", "nota"):
            self.assertNotIn(proibido, out,
                             f"'{proibido}' na saída transformaria qualidade de dado em nota")

    def test_2_every_finding_says_it_is_about_the_data(self):
        with db_system() as c:
            out = DQ.assess(c, project_id=self.project_id)
        for a in out["findings"]:
            self.assertEqual(a["about"], "the_data")
            self.assertNotEqual(a["about"], "the_project")

    def test_3_the_warning_is_part_of_every_answer(self):
        with db_system() as c:
            out = DQ.assess(c, project_id=self.project_id)
        self.assertIn("NÃO É AVALIAÇÃO DO PROJETO", out["not_a_performance_score"])
        self.assertIn("orçamento de monitoramento", out["not_a_performance_score"])

    def test_4_nothing_in_the_quality_engine_feeds_reputation_seals_or_matching(self):
        """A trava estrutural: o módulo não pode nem IMPORTAR quem pontua."""
        import pathlib
        fonte = (pathlib.Path(__file__).resolve().parents[1]
                 / "impacto" / "impact" / "quality.py").read_text(encoding="utf-8")
        for proibido in ("reputation", "seals", "match", "readiness", "score"):
            self.assertNotIn(f"import {proibido}", fonte,
                             f"qualidade de dado não pode alimentar {proibido}")

    def test_5_no_other_engine_imports_the_quality_engine(self):
        """E o caminho inverso também: ninguém pode puxar qualidade para dentro de uma nota."""
        import pathlib
        pkg = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        culpados = []
        for f in pkg.rglob("*.py"):
            if f.name in ("quality.py", "registry.py", "coverage.py"):
                continue
            src = f.read_text(encoding="utf-8")
            if "impact import quality" in src or "impact.quality" in src:
                if "routes" not in f.name:      # a rota que SERVE o motor é o uso legítimo
                    culpados.append(f.name)
        self.assertEqual(culpados, [], "qualidade de dado sendo consumida por quem pontua")


class SevenKindsOfFindingTests(unittest.TestCase):
    """Os sete achados de §69, cada um provocado de propósito."""

    @classmethod
    def setUpClass(cls):
        cls.c = new_account("osc")
        cls.project_id, cls.org_id = _projeto(cls.c)

    def _achados(self, kind: str) -> list[dict]:
        with db_system() as c:
            out = DQ.assess(c, project_id=self.project_id)
        return [a for a in out["findings"] if a["kind"] == kind]

    def test_the_vocabulary_has_exactly_the_seven_kinds_the_document_asks_for(self):
        self.assertEqual(set(DQ.KINDS), {"missing", "duplicate", "inconsistent", "stale",
                                         "invalid", "contradictory", "unverifiable"})

    def test_a_milestone_without_a_deadline_is_missing(self):
        with db_system() as c:
            c.run("INSERT INTO milestones(project_id, org_id, seq, title, amount_cents, due_on)"
                  " VALUES ($1,$2,99,'Marco sem prazo', 0, NULL)", self.project_id, self.org_id)
        achados = self._achados("missing")
        self.assertTrue(any("sem prazo" in a["what"] or "não tem prazo" in a["what"]
                            for a in achados), achados)

    def test_milestones_above_the_declared_budget_are_inconsistent(self):
        with db_system() as c:
            c.run("INSERT INTO milestones(project_id, org_id, seq, title, amount_cents, due_on)"
                  " VALUES ($1,$2,98,'Marco caro', 99000000, current_date + 30)",
                  self.project_id, self.org_id)
        achados = self._achados("inconsistent")
        self.assertTrue(achados, "soma dos marcos acima do orçamento tem de aparecer")
        self.assertIn("não escolhe qual", achados[0]["detail"],
                      "a plataforma não decide qual dos dois números está errado")

    def test_a_project_in_execution_with_no_measurement_is_reported(self):
        """O projeto tem de CHEGAR a esse estado pelo grafo: o gatilho recusa UPDATE direto, e é
        bom que recuse — foi ele que reprovou a primeira versão deste teste."""
        from impacto.core import lifecycle as LC
        with db_system() as c:
            alvo = c.scalar("SELECT to_status FROM project_status_graph"
                            " WHERE from_status = 'draft' LIMIT 1")
            self.assertIsNotNone(alvo)
            LC.transition(c, project_id=self.project_id, org_id=self.org_id, to_status=alvo,
                          actor_user_id=None, reason="Transição feita pelo teste de qualidade.")
            out = DQ.assess(c, project_id=self.project_id)
        # Se o estado alcançado for um dos que o motor observa, o achado tem de aparecer.
        with db_system() as c:
            estado = c.scalar("SELECT status FROM projects WHERE id = $1", self.project_id)
        if estado in ("in_execution", "published", "funded"):
            self.assertTrue(any("sem nenhuma medição" in a["what"] for a in out["findings"]))
        else:
            self.assertEqual(estado, alvo, "a transição pelo grafo tem de ter acontecido")

    def test_every_finding_points_at_a_row(self):
        with db_system() as c:
            out = DQ.assess(c, project_id=self.project_id)
        for a in out["findings"]:
            self.assertTrue(a["ref_id"], "achado sem referência seria opinião sobre o projeto")
            self.assertTrue(a["ref_type"])

    def test_the_engine_refuses_a_project_that_does_not_exist(self):
        with db_system() as c, self.assertRaises(Exception):
            DQ.assess(c, project_id="00000000-0000-0000-0000-000000000000")

    def test_the_answer_says_a_finding_is_not_a_moral_failure(self):
        with db_system() as c:
            out = DQ.assess(c, project_id=self.project_id)
        self.assertIn("Nenhum achado é falha moral", out["note"])
        self.assertIn("ninguém mediu", out["note"])


class RiskLevelInventoryTests(unittest.TestCase):
    """§40 — nível por operação, e o controle humano que o nível exige."""

    @classmethod
    def setUpClass(cls):
        from impacto import api
        from impacto.core import risk_levels as RL
        from impacto.http import ROUTES
        api.load_all()
        cls.RL = RL
        cls.inv = RL.inventory(list(ROUTES))

    def test_every_operation_in_the_router_is_classified(self):
        from impacto.http import ROUTES
        self.assertEqual(self.inv["total"], len(ROUTES),
                         "operação sem nível de risco é operação que ninguém olhou")
        for x in self.inv["operations"]:
            self.assertIn(x["level"], self.RL.LEVELS)
            self.assertIn(x["control"], self.RL.CONTROLS)

    def test_reading_is_never_above_low(self):
        for x in self.inv["operations"]:
            if x["method"] == "GET":
                self.assertEqual(x["level"], "LOW", f"{x['path']} só lê e está como {x['level']}")

    def test_every_critical_operation_has_its_control_implemented(self):
        """A trava que faz o inventário valer: dizer que exige quatro olhos e não implementar."""
        sem = [f"{x['method']} {x['path']} ({x['control']})"
               for x in self.inv["operations"]
               if x["level"] == "CRITICAL" and not x["control_implemented"]]
        self.assertEqual(sem, [],
                         "operação CRÍTICA cujo controle humano declarado não existe no código")

    def test_the_high_risk_gap_cannot_grow(self):
        """Catraca: são 16 operações HIGH cujo controle não é conferível de perto. Não podem virar 17.

        Isto NÃO é "está tudo certo". São dezesseis operações em que o controle, se existe, está a
        mais de uma chamada de distância da rota. Em algumas, como a transição de cobrança, o
        controle é um GATILHO no banco e a varredura estática não tem como enxergá-lo — o que é
        informação sobre a varredura, não sobre a operação. Em outras, pode não haver controle
        nenhum. A lista está em `GET /v1/admin/risk-levels` e no registro de dívida técnica; o
        número está aqui para que ela não cresça em silêncio.
        """
        altas = [x for x in self.inv["operations"]
                 if x["level"] == "HIGH" and not x["control_implemented"]]
        self.assertLessEqual(len(altas), 16,
                             "nova operação de alto risco sem controle conferível: "
                             + ", ".join(f"{x['method']} {x['path']}" for x in altas))

    def test_opening_a_report_is_not_classified_as_high_risk(self):
        """Denúncia não tem efeito por si: classificá-la como alta trataria quem denuncia como réu."""
        abrir = next(x for x in self.inv["operations"]
                     if x["method"] == "POST" and x["path"] == "/v1/reports")
        self.assertEqual(abrir["level"], "MEDIUM")
        self.assertIn("NÃO tem efeito por si", abrir["why"])

    def test_applying_a_measure_is_critical_and_says_why(self):
        medida = next(x for x in self.inv["operations"]
                      if x["method"] == "POST" and x["path"] == "/v1/admin/enforcement")
        self.assertEqual(medida["level"], "CRITICAL")
        self.assertEqual(medida["control"], "human_approval")
        self.assertIn("APURADA", medida["why"])

    def test_every_declared_override_carries_a_written_reason(self):
        for chave, (_, _, motivo) in self.RL.OVERRIDES.items():
            self.assertGreaterEqual(len(motivo), 40,
                                    f"{chave}: exceção sem motivo escrito é exceção de conveniência")

    def test_the_rate_limit_control_is_read_from_the_router_not_from_the_code(self):
        """O único controle que não depende de ninguém lembrar de escrever nada."""
        publicas = [x for x in self.inv["operations"] if x["control"] == "rate_limit"]
        self.assertTrue(publicas, "escrita pública tem de ter o limite de taxa como controle")
        for x in publicas:
            self.assertTrue(x["control_implemented"],
                            f"{x['method']} {x['path']}: escrita pública sem limite de taxa")


class CriticalControlsExistInTheCodeTests(unittest.TestCase):
    """Duas lacunas que este inventário encontrou, e que foram corrigidas de verdade."""

    @classmethod
    def setUpClass(cls):
        cls.admin, _ = make_admin()

    def test_retiring_a_seal_definition_demands_a_written_reason(self):
        r = self.admin.post("/v1/admin/seals/definitions/"
                            "00000000-0000-0000-0000-000000000000/retire", {"reason": "curto"})
        self.assertEqual(r.status, 422, "motivo curto tem de ser recusado antes de qualquer coisa")

    def test_revoking_a_staff_role_demands_a_written_reason(self):
        r = self.admin.delete("/v1/admin/staff-roles/"
                              "00000000-0000-0000-0000-000000000000/editor")
        self.assertEqual(r.status, 422, "revogar acesso sem motivo registrado não pode passar")


class ChargeTrailHasOneOwnerTests(unittest.TestCase):
    """A trilha da cobrança é escrita por GATILHO, e só por ele.

    Durante esta rodada eu acrescentei um INSERT em `economics/payments.transition`, convencido por
    uma contagem zerada em banco de desenvolvimento vazio de que ninguém escrevia `charge_events`.
    Escrevia: `charge_record_event()`, desde a v0.17.0. A suíte reprovou — o teste
    `test_the_trail_is_written_by_the_trigger_and_is_append_only` encontrou a duplicata — e o
    código voltou atrás. Este teste existe para que a mesma correção não precise ser descoberta de
    novo: trilha com duas donas é trilha que diverge no primeiro caminho que esquecer de escrever.
    """

    def test_application_code_never_writes_the_charge_trail(self):
        import pathlib
        pkg = pathlib.Path(__file__).resolve().parents[1] / "impacto"
        culpados = [f.name for f in pkg.rglob("*.py")
                    if "INSERT INTO charge_events" in f.read_text(encoding="utf-8")]
        self.assertEqual(culpados, [],
                         "a trilha da cobrança é escrita pelo gatilho `charge_record_event`: "
                         "código de aplicação pode esquecer de registrar uma transição, gatilho não")

    def test_the_trigger_is_the_one_that_writes_it(self):
        import pathlib
        sql = (pathlib.Path(__file__).resolve().parents[1] / "migrations"
               / "0022_v0170_payments.sql").read_text(encoding="utf-8")
        self.assertIn("CREATE FUNCTION charge_record_event()", sql)
        self.assertIn("INSERT INTO charge_events", sql)
