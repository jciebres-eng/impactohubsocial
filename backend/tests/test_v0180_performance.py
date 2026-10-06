"""v0.18.0 — desempenho das consultas novas, com volume sintético (FASE 10).

As consultas desta rodada têm um traço em comum e um risco próprio: várias são `CROSS JOIN LATERAL`
sobre função (`claim_status`, `seal_status`, `dispute_status`, `responsible_now`), e função chamada
por linha é a forma mais fácil de escrever algo que funciona com dez linhas e para com dez mil.

Este arquivo mede isso. Roda em passo próprio (`PERF=1`) porque gera volume no mesmo banco de teste
e mudaria o resultado de testes funcionais que dependem de listagem.
"""
from __future__ import annotations

import os
import time
import unittest

from tests.support import db_system, grant_premium, new_account, owner_conn, server

ENABLED = os.getenv("PERF") == "1" or os.getenv("PERF_FULL") == "1"
FULL = os.getenv("PERF_FULL") == "1"
CLAIMS = 8_000 if FULL else 1_200
AWARDS = 2_000 if FULL else 200
ASSIGNMENTS = 4_000 if FULL else 400
#: Generoso de propósito: o alvo é pegar regressão de ordem de grandeza, não milissegundo.
BUDGET_MS = 2_500.0
#: Abaixo disso o planejador acerta ao varrer a tabela, e exigir índice ensina a ignorar o teste.
MIN_ROWS = 1_000
TIMINGS: dict[str, float] = {}


def timed(label: str, fn):
    t0 = time.perf_counter()
    out = fn()
    TIMINGS[label] = (time.perf_counter() - t0) * 1000
    return out


@unittest.skipUnless(ENABLED, "teste de volume roda em passo próprio (PERF=1 ou PERF_FULL=1)")
class ImpactVolumeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        grant_premium(cls.osc)
        cls.project = cls.osc.post("/v1/projects", {
            "title": "Projeto do teste de volume da v0.18.0",
            "summary": "Projeto único; o volume é de alegações, selos e designações sobre ele.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 100, "budget_total_cents": 3_000_000}).json["id"]
        oc = owner_conn()
        # Alegações com uma rodada de verificação cada: é o que faz `claim_status()` doer.
        oc.run(
            "INSERT INTO claims(org_id, subject_type, subject_id, claim_kind, statement)"
            " SELECT $1, 'project', $2, 'result',"
            "        'Alegação sintética número ' || g || ' para medir desempenho da rodada.'"
            "   FROM generate_series(1, $3) g", cls.osc.org_id, cls.project, CLAIMS)
        oc.run(
            "INSERT INTO claim_checks(claim_id, check_round, rule_code, passed, severity, detail,"
            " engine_version) SELECT c.id, 1, 'no_basis_at_all', (random() < 0.5), 'serious',"
            "        'detalhe sintético para medir desempenho', 'perf@1'"
            "   FROM claims c WHERE c.subject_id = $1", cls.project)
        # Designações de responsabilidade em escopos sintéticos distintos (um papel por escopo).
        oc.run(
            "INSERT INTO responsibility_assignments(org_id, role_code, scope, subject_id,"
            " external_name, mandate_basis) SELECT $1, 'document_owner', 'document',"
            "        gen_random_uuid(), 'Pessoa sintética ' || g,"
            "        'Base de mandato sintética para medir desempenho da consulta.'"
            "   FROM generate_series(1, $2) g", cls.osc.org_id, ASSIGNMENTS)
        # Selos: uma definição publicada e concessões sintéticas pela função real.
        with db_system() as d:
            cls.definition = d.scalar(
                "INSERT INTO seal_definitions(code, version, scope, title, what_it_attests,"
                " what_it_does_not_attest, validity_days, status, published_at)"
                " VALUES ('selo_perf_volume', 1, 'organization', 'Selo de volume',"
                " 'Atesta compliance aprovado, apenas para o teste de volume desta rodada.',"
                " 'Não atesta qualidade, impacto nem elegibilidade em edital.', 365, 'draft', NULL)"
                " RETURNING id")
            d.run("INSERT INTO seal_criteria(definition_id, rule_code, params, position)"
                  " VALUES ($1, 'compliance_approved', '{}'::jsonb, 0)", cls.definition)
            d.run("UPDATE seal_definitions SET status = 'published', published_at = now()"
                  " WHERE id = $1", cls.definition)
        orgs = [new_account("osc", compliance="approved").org_id for _ in range(3)]
        oc.run(
            "INSERT INTO seal_awards(definition_id, scope, subject_id, org_id, evidence,"
            " expires_on, engine_version)"
            " SELECT $1, 'organization', o, o,"
            "        '[{\"rule_code\":\"compliance_approved\",\"met\":true,"
            "           \"detail\":\"sintético\"}]'::jsonb, current_date + 365, 'perf@1'"
            "   FROM unnest($2::uuid[]) o, generate_series(1, $3) g",
            cls.definition, orgs, AWARDS // 3)

    def test_the_claim_listing_stays_fast_with_thousands_of_claims(self):
        r = timed("claims.list", lambda: self.osc.get("/v1/claims?limit=50"))
        self.assertEqual(r.status, 200, r)
        self.assertEqual(len(r.json["items"]), 50)
        self.assertLess(TIMINGS["claims.list"], BUDGET_MS,
                        "a listagem com claim_status() por linha regrediu")

    def test_one_claim_is_read_without_scanning_the_others(self):
        cid = self.osc.get("/v1/claims?limit=1").json["items"][0]["id"]
        r = timed("claims.get", lambda: self.osc.get(f"/v1/claims/{cid}"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["claims.get"], BUDGET_MS)

    def test_the_claim_status_query_uses_the_index(self):
        with db_system() as d:
            n = d.scalar("SELECT count(*) FROM claim_checks")
            if n < MIN_ROWS:
                self.skipTest(f"claim_checks tem {n} linhas; abaixo de {MIN_ROWS} a varredura "
                              "sequencial é o planejador acertando")
            plano = "\n".join(r["QUERY PLAN"] for r in d.query(
                "EXPLAIN SELECT * FROM claim_checks WHERE claim_id = (SELECT id FROM claims"
                " LIMIT 1) ORDER BY check_round DESC"))
        self.assertIn("Index", plano, f"consulta de verificação sem índice:\n{plano}")

    def test_the_reputation_profile_stays_fast(self):
        r = timed("reputation.me", lambda: self.osc.get("/v1/reputation/me"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["reputation.me"], BUDGET_MS,
                        "o perfil de reputação faz uma consulta por sinal; alguma regrediu")

    def test_the_seal_listing_stays_fast_with_thousands_of_awards(self):
        r = timed("seals.list", lambda: self.osc.get("/v1/seals/awards?active_only=true"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["seals.list"], BUDGET_MS,
                        "a listagem com seal_status() por linha regrediu")

    def test_the_seal_evaluation_stays_fast(self):
        r = timed("seals.evaluate", lambda: self.osc.post(
            "/v1/seals/evaluate",
            {"definition_id": self.definition, "subject_id": self.osc.org_id}))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["seals.evaluate"], BUDGET_MS)

    def test_my_responsibility_list_stays_fast(self):
        r = timed("responsibility.mine", lambda: self.osc.get("/v1/responsibility/mine"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["responsibility.mine"], BUDGET_MS)

    def test_the_lookup_answers_fast_enough_to_type_against(self):
        """Autocomplete é medido em percepção: acima de meio segundo a pessoa já digitou outra coisa."""
        r = timed("lookup.territories", lambda: self.osc.get("/v1/lookups/territories?q=ma"))
        self.assertEqual(r.status, 200, r)
        self.assertLess(TIMINGS["lookup.territories"], 800.0,
                        "a busca incremental ficou lenta para o uso que ela tem")

    def test_zzz_report(self):
        print("\n--- v0.18.0: tempos (ms) ---")
        for k, v in sorted(TIMINGS.items(), key=lambda x: -x[1]):
            print(f"  {k:28s} {v:9.1f}")
