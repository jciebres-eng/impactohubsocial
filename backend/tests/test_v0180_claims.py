"""v0.18.0 — integridade de alegação: a frase do relatório confrontada com o que o banco sabe.

O que estes testes protegem é uma ideia só: **a situação da alegação não é escrevível.** Não existe
coluna de situação em `claims`; `claim_status()` deriva da última rodada de verificação. É a diferença
entre um produto onde alguém pode marcar a alegação como comprovada e um onde ninguém pode.

E protegem a contrapartida: o verificador NÃO acusa fraude. Devolve `attention` ou `serious`,
e `serious` exige revisão humana de OUTRA organização — revisão que qualifica a marca sem apagá-la.

NOTA DE ORDEM: os métodos de uma classe rodam em ordem ALFABÉTICA e compartilham o que a classe
criou. Cada teste que depende do estado do sujeito cria o seu próprio projeto.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from tests.support import app_tx, db_system, grant_premium, new_account, owner_conn

NOTE20 = "Nota de revisão com extensão suficiente para o CHECK do banco nesta coluna."


class ClaimBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        # Cada teste de regra precisa de um sujeito com fatos próprios (a ordem alfabética dos
        # métodos compartilharia o estado), e o plano gratuito limita projetos ativos a 10.
        grant_premium(cls.osc)

    def _project(self, title: str = "Projeto de alegação") -> str:
        r = self.osc.post("/v1/projects", {
            "title": f"{title} {date.today().isoformat()}",
            "summary": "Projeto criado para exercitar a integridade de alegação da v0.18.0.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5103403", "causes": ["educacao"],
            "beneficiaries_count": 200, "budget_total_cents": 5_000_000})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def _declare(self, project: str, statement: str, kind: str = "result", **kw):
        return self.osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": project, "claim_kind": kind,
            "statement": statement, **kw})

    def _indicator(self, project: str) -> str:
        cat = self.osc.get("/v1/indicators/catalog?ods=4").json["items"]
        ind = next(i for i in cat if i["code"] == "trained_people")
        r = self.osc.post(f"/v1/projects/{project}/indicators", {
            "indicator_id": ind["id"], "baseline": 0,
            "baseline_source": "Lista de presença do primeiro encontro", "target": 100,
            "method": "Lista de presença"})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def _validated_value(self, project: str, pi: str, value: float, *, evidence: bool = True):
        """Insere valor VALIDADO pelo caminho do dono do banco.

        O caminho real exige financiador com aporte no projeto (separação de funções, v0.8.0). Aqui o
        que está sob teste é o verificador de alegação, não o fluxo de validação — e o CHECK de
        `validated_by_org <> org_id` continua valendo, então a validação é atribuída à OUTRA org.
        """
        ev = None
        oc = owner_conn()
        if evidence:
            ev = self.osc.post(f"/v1/projects/{project}/evidences", {
                "kind": "attendance", "title": "Lista de presença da turma"}).json["id"]
            oc.run("UPDATE evidences SET status = 'accepted' WHERE id = $1", ev)
        oc.run(
                "INSERT INTO indicator_values(project_indicator_id, project_id, org_id, value,"
            " measured_on, evidence_id, status, validated_by, validated_by_org)"
            " SELECT $1, $2, $3, $4, current_date, $5, 'validated',"
            "        (SELECT id FROM users LIMIT 1), $6",
            pi, project, self.osc.org_id, value, ev, self.other.org_id)
        return ev


# ================================================================================================ catálogo
class RuleCatalogTests(ClaimBase):
    def test_every_rule_is_deterministic_and_says_why_it_matters(self):
        r = self.osc.get("/v1/claims/rules")
        self.assertEqual(r.status, 200, r)
        self.assertGreaterEqual(len(r.json["items"]), 11)
        for item in r.json["items"]:
            self.assertTrue(item["deterministic"], item["code"])
            self.assertGreaterEqual(len(item["why_it_matters"]), 20, item["code"])
            self.assertIn(item["severity"], ("info", "attention", "serious"))

    def test_the_lexicons_are_public_because_whoever_is_flagged_may_contest(self):
        lex = self.osc.get("/v1/claims/rules").json["lexicons"]
        for key in ("absolute", "certification", "causality", "comparative"):
            self.assertGreaterEqual(len(lex[key]), 8, key)
        self.assertIn("neutro", lex["absolute"])
        self.assertIn("certificado", lex["certification"])

    def test_no_rule_in_the_database_may_be_probabilistic(self):
        oc = owner_conn()
        with self.assertRaises(Exception):
            oc.run("UPDATE claim_rules SET deterministic = false WHERE code = 'no_basis_at_all'")

    def test_the_catalog_declares_that_no_rule_calls_a_language_model(self):
        note = self.osc.get("/v1/claims/rules").json["note"].lower()
        self.assertIn("modelo de linguagem", note)
        self.assertIn("reproduz", note)


# ================================================================================================ declaração
class DeclarationTests(ClaimBase):
    def test_a_fresh_claim_is_unchecked_not_substantiated(self):
        p = self._project()
        r = self._declare(p, "Atendemos duzentas pessoas em oficinas de leitura no semestre.")
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["status"], "unchecked")
        got = self.osc.get(f"/v1/claims/{r.json['id']}")
        self.assertEqual(got.json["status"], "unchecked")
        self.assertEqual(got.json["checks"], [])

    def test_a_claim_about_someone_elses_subject_is_refused(self):
        """404 e não 403: dizer "existe, mas não é seu" já é informação sobre o que não se pode ver."""
        p = self._project()
        r = self.other.post("/v1/claims", {
            "subject_type": "project", "subject_id": p, "claim_kind": "result",
            "statement": "Alegação sobre projeto que não é da minha organização."})
        self.assertEqual(r.status, 404, r)
        self.assertNotIn("não encontrado não encontrado", r.json["title"])

    def test_an_unknown_subject_is_404_not_a_claim_about_nothing(self):
        r = self.osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": "00000000-0000-0000-0000-000000000000",
            "claim_kind": "result", "statement": "Alegação sobre sujeito inexistente."})
        self.assertEqual(r.status, 404, r)

    def test_there_is_no_status_column_to_write_to(self):
        """A trava central desta fase, verificada no esquema e não no texto do relatório."""
        with db_system() as d:
            cols = [r["column_name"] for r in d.query(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'claims'")]
        self.assertNotIn("status", cols)
        self.assertNotIn("verified", cols)
        self.assertNotIn("substantiated", cols)

    def test_the_statement_is_frozen_after_the_first_check(self):
        p = self._project()
        cid = self._declare(p, "Reduzimos a evasão escolar na comunidade atendida.").json["id"]
        self.osc.post(f"/v1/claims/{cid}/check", {})
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception) as ctx:
                c.run("UPDATE claims SET statement = $2 WHERE id = $1", cid,
                      "Texto trocado depois de verificado para herdar a verificação anterior.")
        self.assertIn("não troca de texto", str(ctx.exception))

    def test_withdrawal_keeps_the_check_history_readable(self):
        p = self._project()
        cid = self._declare(p, "Alegação que será retirada depois de verificada.").json["id"]
        self.osc.post(f"/v1/claims/{cid}/check", {})
        r = self.osc.post(f"/v1/claims/{cid}/withdraw", {
            "reason": "Retirada porque o número do texto não corresponde ao medido."})
        self.assertEqual(r.status, 200, r)
        got = self.osc.get(f"/v1/claims/{cid}").json
        self.assertEqual(got["status"], "withdrawn")
        self.assertGreaterEqual(len(got["checks"]), 11)

    def test_a_withdrawn_claim_is_not_checked_again(self):
        p = self._project()
        cid = self._declare(p, "Alegação retirada não volta para a fila de verificação.").json["id"]
        self.osc.post(f"/v1/claims/{cid}/withdraw", {"reason": "Retirada por decisão da equipe."})
        r = self.osc.post(f"/v1/claims/{cid}/check", {})
        self.assertEqual(r.json["code"], "withdrawn", r)


# ================================================================================================ regras
class RuleBehaviourTests(ClaimBase):
    def _check(self, project: str, statement: str, kind: str = "result", **kw) -> dict:
        cid = self._declare(project, statement, kind, **kw).json["id"]
        r = self.osc.post(f"/v1/claims/{cid}/check", {})
        self.assertEqual(r.status, 201, r)
        return r.json

    def _rule(self, out: dict, code: str) -> dict:
        return next(c for c in out["checks"] if c["rule_code"] == code)

    def test_a_subject_with_no_basis_at_all_is_serious_not_merely_weak(self):
        out = self._check(self._project(), "Transformamos a realidade educacional do município.")
        self.assertFalse(self._rule(out, "no_basis_at_all")["passed"])
        self.assertEqual(self._rule(out, "no_basis_at_all")["severity"], "serious")
        self.assertEqual(out["status"], "flagged")

    def test_absolute_language_without_a_validated_measurement_is_flagged(self):
        out = self._check(self._project(), "O projeto é neutro em carbono e o resultado é "
                                           "comprovado em toda a área de atuação.")
        hit = self._rule(out, "absolute_language")
        self.assertFalse(hit["passed"])
        self.assertIn("neutro", hit["detail"])
        self.assertEqual(hit["severity"], "serious")

    def test_claiming_certification_is_flagged_because_the_platform_certifies_nothing(self):
        out = self._check(self._project(), "Nosso programa é certificado e homologado pelo órgão "
                                           "competente do estado.", kind="certification")
        hit = self._rule(out, "certification_language")
        self.assertFalse(hit["passed"])
        self.assertEqual(hit["severity"], "serious")
        self.assertIn("não certifica", hit["detail"])

    def test_plain_language_does_not_trigger_the_lexicon_rules(self):
        out = self._check(self._project(), "Realizamos oficinas semanais de leitura com turmas da "
                                           "escola municipal ao longo do semestre.")
        for code in ("absolute_language", "certification_language", "causality_from_weak_link",
                     "comparative_without_denominator"):
            self.assertTrue(self._rule(out, code)["passed"], code)

    def test_an_ods_marked_without_an_indicator_is_a_point_of_attention(self):
        p = self._project()
        r = self.osc.put(f"/v1/projects/{p}/ods-targets", {
            "items": [{"ods": 4, "rationale": "Educação de qualidade na escola municipal."}]})
        self.assertEqual(r.status, 200, r)
        out = self._check(p, "Contribuímos para o objetivo de desenvolvimento sustentável quatro.",
                          kind="ods_contribution")
        hit = self._rule(out, "ods_without_indicator")
        self.assertFalse(hit["passed"])
        self.assertEqual(hit["severity"], "attention")

    def test_an_indicator_without_measurement_is_caught_and_clears_once_measured(self):
        p = self._project()
        pi = self._indicator(p)
        antes = self._check(p, "Acompanhamos o indicador de pessoas formadas no período.")
        self.assertFalse(self._rule(antes, "indicator_without_measurement")["passed"])
        self._validated_value(p, pi, 40)
        depois = self._check(p, "Acompanhamos o indicador de pessoas formadas no período dois.")
        self.assertTrue(self._rule(depois, "indicator_without_measurement")["passed"])

    def test_a_validated_measurement_without_evidence_is_a_point_of_attention(self):
        p = self._project()
        pi = self._indicator(p)
        self._validated_value(p, pi, 40, evidence=False)
        out = self._check(p, "Registramos a medição do indicador no período de execução.")
        hit = self._rule(out, "measurement_without_evidence")
        self.assertFalse(hit["passed"])
        self.assertIn("sem evidência", hit["detail"])

    def test_absolute_language_passes_when_there_is_a_measurement_with_evidence(self):
        """A regra não pune a palavra: pune a palavra SEM base. Essa distinção é o produto."""
        p = self._project()
        pi = self._indicator(p)
        self._validated_value(p, pi, 40)
        out = self._check(p, "O resultado é comprovado pela medição validada com evidência "
                             "anexada no cofre do projeto.")
        self.assertTrue(self._rule(out, "absolute_language")["passed"])

    def test_a_number_in_the_text_without_a_matching_measurement_is_flagged(self):
        p = self._project()
        pi = self._indicator(p)
        self._validated_value(p, pi, 40)
        out = self._check(p, "Formamos 1.200 pessoas em oficinas de leitura durante o semestre.")
        hit = self._rule(out, "number_not_in_measurements")
        self.assertFalse(hit["passed"])
        self.assertIn("1200", hit["detail"].replace(".0", ""))

    def test_a_number_that_matches_a_validated_value_passes(self):
        p = self._project()
        pi = self._indicator(p)
        self._validated_value(p, pi, 40)
        out = self._check(p, "Formamos 40 pessoas em oficinas de leitura durante o semestre.")
        self.assertTrue(self._rule(out, "number_not_in_measurements")["passed"])

    def test_causality_on_a_hypothesis_link_is_flagged_as_serious(self):
        p = self._project()
        n1 = self.osc.post(f"/v1/projects/{p}/graph/nodes", {
            "kind": "activity", "label": "Oficinas semanais"}).json["id"]
        n2 = self.osc.post(f"/v1/projects/{p}/graph/nodes", {
            "kind": "outcome", "label": "Alunos leem melhor"}).json["id"]
        e = self.osc.post(f"/v1/projects/{p}/graph/edges", {
            "from_node": n1, "to_node": n2, "link_type": "hypothesis"})
        self.assertEqual(e.status, 201, e)
        out = self._check(p, "As oficinas geraram melhoria na leitura das turmas atendidas.")
        hit = self._rule(out, "causality_from_weak_link")
        self.assertFalse(hit["passed"])
        self.assertEqual(hit["severity"], "serious")
        self.assertIn("hypothesis", hit["detail"])

    def test_a_comparison_without_a_sourced_denominator_is_a_point_of_attention(self):
        out = self._check(self._project(), "Somos a maior iniciativa de leitura do município e "
                                           "lidera o atendimento na região.", kind="comparative")
        hit = self._rule(out, "comparative_without_denominator")
        self.assertFalse(hit["passed"])
        self.assertIn("denominador", hit["detail"])

    def test_a_financial_claim_with_an_expense_without_receipt_is_serious(self):
        p = self._project()
        owner_conn().run(
            "INSERT INTO expenses(project_id, org_id, description, amount_cents, paid_on)"
            " VALUES ($1, $2, 'Compra de livros', 120000, current_date)", p, self.osc.org_id)
        out = self._check(p, "Aplicamos integralmente os recursos recebidos no período.",
                          kind="financial")
        hit = self._rule(out, "financial_claim_without_receipt")
        self.assertFalse(hit["passed"])
        self.assertEqual(hit["severity"], "serious")

    def test_a_period_before_the_execution_window_is_caught(self):
        p = self._project()
        owner_conn().run(
            "UPDATE projects SET starts_on = $2, ends_on = $3 WHERE id = $1", p,
            date.today() - timedelta(days=30), date.today() + timedelta(days=30))
        out = self._check(p, "Resultado alcançado no período declarado abaixo.",
                          period_start=(date.today() - timedelta(days=400)).isoformat(),
                          period_end=date.today().isoformat())
        self.assertFalse(self._rule(out, "period_outside_execution")["passed"])

    def test_the_check_publishes_the_facts_it_used_so_the_result_can_be_contested(self):
        p = self._project()
        out = self._check(p, "Alegação qualquer para inspecionar os fatos usados na verificação.")
        facts = out["facts_used"]
        for key in ("indicators", "values_validated", "values_with_evidence",
                    "accepted_evidences", "result_chain_links", "denominators_available"):
            self.assertIn(key, facts)
        self.assertTrue(out["engine_version"].startswith("claim-integrity@"))

    def test_the_same_text_on_the_same_facts_gives_the_same_verdict(self):
        """Determinismo não é promessa de documentação: é o que este teste mede."""
        p = self._project()
        texto = "Garantimos a erradicação do analfabetismo nas turmas atendidas."
        a = self._check(p, texto + " Primeira declaração.")
        b = self._check(p, texto + " Segunda declaração.")
        chave = lambda o: sorted((c["rule_code"], c["passed"]) for c in o["checks"])  # noqa: E731
        self.assertEqual(chave(a), chave(b))
        self.assertEqual(a["status"], b["status"])


# ================================================================================================ rodadas
class CheckRoundTests(ClaimBase):
    def test_a_new_round_never_erases_the_previous_one(self):
        p = self._project()
        cid = self._declare(p, "Alegação verificada mais de uma vez ao longo do tempo.").json["id"]
        r1 = self.osc.post(f"/v1/claims/{cid}/check", {}).json
        r2 = self.osc.post(f"/v1/claims/{cid}/check", {}).json
        self.assertEqual((r1["check_round"], r2["check_round"]), (1, 2))
        got = self.osc.get(f"/v1/claims/{cid}").json
        self.assertEqual({c["check_round"] for c in got["checks"]}, {1, 2})
        self.assertEqual(got["check_round"], 2)

    def test_the_check_trail_is_append_only_even_for_the_app_role(self):
        p = self._project()
        cid = self._declare(p, "Alegação cuja trilha de verificação não pode ser editada.").json["id"]
        self.osc.post(f"/v1/claims/{cid}/check", {})
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception):
                c.run("UPDATE claim_checks SET passed = true WHERE claim_id = $1", cid)
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception):
                c.run("DELETE FROM claim_checks WHERE claim_id = $1", cid)

    def test_improvement_shows_up_as_a_better_status_in_a_later_round(self):
        p = self._project()
        pi = self._indicator(p)
        cid = self._declare(p, "Formamos pessoas em oficinas de leitura, conforme medição.").json["id"]
        antes = self.osc.post(f"/v1/claims/{cid}/check", {}).json
        self.assertIn(antes["status"], ("flagged", "attention"))
        self._validated_value(p, pi, 40)
        depois = self.osc.post(f"/v1/claims/{cid}/check", {}).json
        self.assertLess(depois["serious"] + depois["attention"], antes["serious"] + antes["attention"])


# ================================================================================================ revisão
class HumanReviewTests(ClaimBase):
    """A revisão é por CONVITE.

    Antes de existir o convite, qualquer organização podia revisar qualquer alegação marcada — e
    como revisar exige LER a alegação e a verificação, isso equivalia a tornar pública toda alegação
    marcada, além de abrir um canal para pressionar concorrente. O convite nomeado resolve as duas
    coisas: é ele que abre a leitura, e ele vale para UMA rodada.
    """

    def _flagged(self, *, invite: bool = True) -> str:
        p = self._project()
        cid = self._declare(p, "O resultado é comprovado e garantido em toda a área.").json["id"]
        out = self.osc.post(f"/v1/claims/{cid}/check", {}).json
        self.assertEqual(out["status"], "flagged")
        if invite:
            r = self.osc.post(f"/v1/claims/{cid}/review-requests", {
                "reviewer_org_id": self.other.org_id,
                "note": "Convite para revisar a linguagem desta alegação."})
            self.assertEqual(r.status, 201, r)
        return cid

    def test_the_declaring_organization_cannot_review_its_own_claim(self):
        cid = self._flagged()
        r = self.osc.post(f"/v1/claims/{cid}/review", {"decision": "accepted", "note": NOTE20})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "not_invited")

    def test_the_declaring_organization_cannot_invite_itself(self):
        cid = self._flagged(invite=False)
        r = self.osc.post(f"/v1/claims/{cid}/review-requests", {
            "reviewer_org_id": self.osc.org_id})
        self.assertEqual(r.status, 422, r)
        self.assertIn("própria organização", r.json["title"])

    def test_without_an_invitation_there_is_no_review_and_nothing_to_read(self):
        cid = self._flagged(invite=False)
        self.assertEqual(self.other.get(f"/v1/claims/{cid}").status, 404)
        r = self.other.post(f"/v1/claims/{cid}/review", {"decision": "accepted", "note": NOTE20})
        self.assertEqual(r.json["code"], "not_invited", r)

    def test_the_invitation_is_what_opens_the_claim_and_its_checks(self):
        cid = self._flagged()
        got = self.other.get(f"/v1/claims/{cid}")
        self.assertEqual(got.status, 200, got)
        self.assertGreaterEqual(len(got.json["checks"]), 11)
        fila = self.other.get("/v1/claims/review-requests").json["items"]
        self.assertTrue(any(i["claim_id"] == cid and i["pending"] for i in fila))

    def test_accepting_in_review_qualifies_the_flag_but_never_erases_it(self):
        cid = self._flagged()
        r = self.other.post(f"/v1/claims/{cid}/review", {
            "decision": "accepted", "note": "Revisado: a linguagem absoluta se justifica pelo "
                                            "laudo externo apresentado fora da plataforma."})
        self.assertEqual(r.status, 201, r)
        self.assertEqual(r.json["status"], "flagged_accepted_by_review")
        self.assertGreater(r.json["serious"], 0)

    def test_a_rejecting_review_is_the_status_that_shows(self):
        cid = self._flagged()
        r = self.other.post(f"/v1/claims/{cid}/review", {"decision": "rejected", "note": NOTE20})
        self.assertEqual(r.json["status"], "rejected_by_review")

    def test_an_invitation_only_exists_after_a_check(self):
        p = self._project()
        cid = self._declare(p, "Alegação ainda não verificada não pode ser revisada.").json["id"]
        r = self.osc.post(f"/v1/claims/{cid}/review-requests", {
            "reviewer_org_id": self.other.org_id})
        self.assertEqual(r.json["code"], "not_checked", r)

    def test_a_review_does_not_carry_over_to_the_next_round(self):
        """Mesma lição da assinatura: revisão é de uma RODADA, como assinatura é de uma VERSÃO."""
        cid = self._flagged()
        self.other.post(f"/v1/claims/{cid}/review", {"decision": "accepted", "note": NOTE20})
        self.assertEqual(self.osc.get(f"/v1/claims/{cid}").json["status"],
                         "flagged_accepted_by_review")
        self.osc.post(f"/v1/claims/{cid}/check", {})
        self.assertEqual(self.osc.get(f"/v1/claims/{cid}").json["status"], "flagged")
        r = self.other.post(f"/v1/claims/{cid}/review", {"decision": "accepted", "note": NOTE20})
        self.assertEqual(r.status, 422, r)

    def test_the_review_trail_is_append_only(self):
        cid = self._flagged()
        self.other.post(f"/v1/claims/{cid}/review", {"decision": "accepted", "note": NOTE20})
        with app_tx(self.other) as c:
            with self.assertRaises(Exception):
                c.run("UPDATE claim_reviews SET decision = 'rejected' WHERE claim_id = $1", cid)


# ================================================================================================ isolamento
class IsolationTests(ClaimBase):
    def test_a_stranger_organization_does_not_see_the_claim(self):
        p = self._project()
        cid = self._declare(p, "Alegação que outra organização não deve enxergar.").json["id"]
        stranger = new_account("company", compliance="approved")
        self.assertEqual(stranger.get(f"/v1/claims/{cid}").status, 404)
        self.assertEqual([c["id"] for c in stranger.get("/v1/claims").json["items"]], [])

    def test_a_stranger_cannot_run_a_check_to_learn_the_facts(self):
        p = self._project()
        cid = self._declare(p, "Alegação cuja verificação é privativa de quem a declarou.").json["id"]
        stranger = new_account("company", compliance="approved")
        self.assertEqual(stranger.post(f"/v1/claims/{cid}/check", {}).status, 404)

    def test_listing_mine_is_scoped_to_my_organization(self):
        p = self._project()
        self._declare(p, "Alegação da minha organização que aparece na minha lista.")
        mine = self.osc.get("/v1/claims").json["items"]
        self.assertTrue(mine)
        self.assertEqual(self.other.get("/v1/claims").json["items"], [])
