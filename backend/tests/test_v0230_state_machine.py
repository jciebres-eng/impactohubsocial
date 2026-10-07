"""Máquina de estados da candidatura: o grafo passa a valer no banco, não só na rota.

O QUE MUDA

A máquina de estados existe desde a v0.13.0 em `services/workflow.py` (`PLATFORM`/`EXTERNAL`) e é
conferida em `transition()`. Isso protege UMA rota. O prompt desta rodada pede validação no
backend no sentido forte: que nenhum caminho a contorne. `rascunho → encerrada` por um `UPDATE`
direto era possível — de outra rota, de um script de operação, ou de uma rota futura escrita sem
lembrar da regra.

A DUPLICAÇÃO É CONSCIENTE

O grafo está em dois lugares (Python e banco) porque migração não importa Python. O que torna isso
aceitável é `TheGraphInTheDatabaseIsTheGraphInTheCodeTests`: ele reprova se as duas cópias
divergirem em UMA aresta. Sem esse teste, a segunda cópia seria uma segunda regra — que é o defeito
que `core/risk_levels.py` e o menu da v0.22.0 ensinaram a não repetir.
"""
from __future__ import annotations

import unittest

from tests.support import db_system, grant_premium, new_account, owner_conn


def _osc_com_projeto() -> tuple[object, str]:
    """`applications_check` exige `call_id` OU `project_id`: candidatura sem nenhum dos dois não
    existe no esquema, e é por isso que o teste constrói um projeto de verdade."""
    c = new_account("osc", compliance="approved")
    grant_premium(c)
    return c, _novo_projeto(c)


def _novo_projeto(c) -> str:
    """Um projeto POR candidatura. `ux_application_active` é único em
    (edital, projeto, OSC, financiador) para estados ativos, então duas candidaturas em rascunho
    no mesmo projeto colidem — a primeira versão deste teste colidiu exatamente assim."""
    import datetime as dt
    r = c.post("/v1/projects", {
        "title": "Projeto para prova da máquina de estados",
        "summary": "Criado por teste para exercitar as transições de candidatura.",
        "problem": "A comunidade não tem oferta de contraturno.",
        "objectives": "Ofertar reforço a 30 crianças.",
        "territory": "BR-AC-1200013", "causes": ["educacao"],
        "beneficiaries_count": 30, "budget_total_cents": 200_000,
        "starts_on": (dt.date.today() - dt.timedelta(days=20)).isoformat(),
        "ends_on": (dt.date.today() + dt.timedelta(days=100)).isoformat()})
    assert r.status == 201, r
    return r.json["id"]


#: Caminho legítimo até cada estado. Depois desta versão não há atalho: a candidatura nasce em
#: rascunho e CAMINHA. Montar o estado por INSERT direto, como a primeira versão deste teste fazia,
#: é justamente o que o gatilho novo recusa — e o teste descobriu isso sozinho.
_CAMINHOS = {
    "osc_application": {
        "draft": [],
        "submitted": ["submitted"],
        "screening": ["submitted", "screening"],
        "due_diligence": ["submitted", "screening", "due_diligence"],
        "approved": ["submitted", "screening", "due_diligence", "approved"],
        "committed": ["submitted", "screening", "due_diligence", "approved", "committed"],
        "in_execution": ["submitted", "screening", "due_diligence", "approved", "committed",
                         "in_execution"],
        "reporting": ["submitted", "screening", "due_diligence", "approved", "committed",
                      "in_execution", "reporting"],
        "rejected": ["submitted", "rejected"],
        "withdrawn": ["withdrawn"],
        "closed": ["submitted", "screening", "due_diligence", "approved", "committed",
                   "in_execution", "reporting", "closed"],
    },
    "external_tracking": {
        "draft": [],
        "submitted": ["submitted"],
        "approved": ["submitted", "approved"],
        "rejected": ["submitted", "rejected"],
        "in_execution": ["submitted", "approved", "in_execution"],
        "reporting": ["submitted", "approved", "in_execution", "reporting"],
        "closed": ["submitted", "approved", "in_execution", "reporting", "closed"],
    },
}


def _candidatura(osc, projeto: str, funder, status: str = "draft",
                 origem: str = "osc_application") -> str:
    projeto = _novo_projeto(osc)   # ver `_novo_projeto`: um por candidatura
    # `applications_check1`: em edital externo não há financiador na plataforma — quem acompanha o
    # próprio processo não tem contraparte aqui. Passar um financiador seria inventar a relação.
    financiador = None if origem == "external_tracking" else funder.org_id
    with db_system() as c:
        aid = c.scalar(
            "INSERT INTO applications(osc_org_id, funder_org_id, origin, status, project_id)"
            " VALUES ($1,$2,$3,'draft',$4) RETURNING id::text",
            osc.org_id, financiador, origem, projeto)
        for passo in _CAMINHOS[origem][status]:
            c.run("UPDATE applications SET status = $2 WHERE id = $1", aid, passo)
        return aid


class TheGraphInTheDatabaseIsTheGraphInTheCodeTests(unittest.TestCase):
    """Duas cópias, uma verdade. Este teste é o que autoriza a duplicação.

    A única diferença permitida está declarada: `approved → committed` não passa pela rota genérica
    de transição (quem a executa é a rota de registro de aporte), então ela existe no banco e não
    em `PLATFORM`. A exceção fica aqui, nomeada, e não cresce em silêncio.
    """

    EXTRA_NO_BANCO = {("approved", "committed", "funder")}

    def _do_banco(self, origem: str) -> set[tuple[str, str, str]]:
        with db_system() as c:
            return {(r["from_status"], r["to_status"], r["side"])
                    for r in c.query("SELECT from_status, to_status, side"
                                     "  FROM application_status_graph WHERE origin = $1", origem)}

    @staticmethod
    def _do_codigo(tabela: dict) -> set[tuple[str, str, str]]:
        return {(de, para, lado) for de, destinos in tabela.items()
                for para, lado in destinos.items()}

    def test_the_platform_graph_matches_edge_by_edge(self):
        from impacto.services.workflow import PLATFORM
        codigo = self._do_codigo(PLATFORM)
        for origem in ("osc_application", "funder_interest"):
            with self.subTest(origem=origem):
                banco = self._do_banco(origem)
                self.assertEqual(codigo | self.EXTRA_NO_BANCO, banco,
                                 "o grafo do banco divergiu do grafo do código; "
                                 f"só no banco: {banco - codigo - self.EXTRA_NO_BANCO}; "
                                 f"só no código: {codigo - banco}")

    def test_the_external_graph_matches_edge_by_edge(self):
        from impacto.services.workflow import EXTERNAL
        self.assertEqual(self._do_codigo(EXTERNAL), self._do_banco("external_tracking"))

    def test_the_declared_exception_carries_its_reason_in_the_database(self):
        """Exceção sem motivo escrito volta a ser divergência com outro nome."""
        with db_system() as c:
            nota = c.scalar("SELECT note FROM application_status_graph"
                            " WHERE origin = 'osc_application' AND from_status = 'approved'"
                            "   AND to_status = 'committed'")
        self.assertIsNotNone(nota)
        self.assertIn("commitments", nota)

    def test_the_exception_list_cannot_grow_quietly(self):
        self.assertEqual(1, len(self.EXTRA_NO_BANCO),
                         "cada aresta que existe só no banco precisa de decisão consciente")

    def test_terminal_states_have_no_exit_and_initial_states_have_one(self):
        """Estado terminal com saída não é terminal; estado inicial sem saída prende a candidatura."""
        with db_system() as c:
            alcancaveis = {r["to_status"] for r in
                           c.query("SELECT DISTINCT to_status FROM application_status_graph")}
            saem = {r["from_status"] for r in
                    c.query("SELECT DISTINCT from_status FROM application_status_graph")}
        for estado in ("rejected", "withdrawn", "closed"):
            with self.subTest(terminal=estado):
                self.assertIn(estado, alcancaveis, "estado terminal inalcançável")
                self.assertNotIn(estado, saem, "estado terminal com saída: não é terminal")
        for estado in ("draft", "interest"):
            with self.subTest(inicial=estado):
                self.assertIn(estado, saem, "estado inicial sem saída: a candidatura ficaria presa")


class ImpossibleStatesAreImpossibleNowTests(unittest.TestCase):
    """As tentativas são feitas como DONO do banco: o que recusa é o gatilho, não o privilégio."""

    @classmethod
    def setUpClass(cls):
        cls.osc, cls.projeto = _osc_com_projeto()
        cls.funder = new_account("company", compliance="approved")

    def _candidatura(self, status: str = "draft", origem: str = "osc_application") -> str:
        return _candidatura(self.osc, self.projeto, self.funder, status, origem)

    def test_draft_cannot_jump_straight_to_closed(self):
        """O estado impossível que o prompt nomeia."""
        aid = self._candidatura()
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as erro:
                conn.run("UPDATE applications SET status = 'closed' WHERE id = $1", aid)
            self.assertIn("não permitida", str(erro.exception))
            self.assertIn("draft → closed", str(erro.exception))
        finally:
            conn.close()

    def test_the_error_says_which_transitions_are_allowed(self):
        """Erro que só nega não ajuda: quem está no fluxo precisa saber o próximo passo possível."""
        aid = self._candidatura()
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as erro:
                conn.run("UPDATE applications SET status = 'approved' WHERE id = $1", aid)
            self.assertIn("Permitidas: submitted, withdrawn", str(erro.exception))
        finally:
            conn.close()

    def test_a_terminal_state_has_no_exit(self):
        aid = self._candidatura("rejected")
        conn = owner_conn()
        try:
            for destino in ("draft", "submitted", "approved", "in_execution"):
                with self.subTest(destino=destino):
                    conn.run("BEGIN")
                    with self.assertRaises(Exception) as erro:
                        conn.run("UPDATE applications SET status = $2 WHERE id = $1", aid, destino)
                    conn.run("ROLLBACK")
                    self.assertIn("estado terminal", str(erro.exception))
        finally:
            conn.close()

    def test_an_application_cannot_be_born_approved(self):
        """Nascer aprovada pularia o processo inteiro sem deixar uma única transição registrada."""
        with db_system() as c:
            c.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                c.run("INSERT INTO applications(osc_org_id, funder_org_id, origin, status, project_id)"
                      " VALUES ($1,$2,'osc_application','approved',$3)",
                      self.osc.org_id, self.funder.org_id, self.projeto)
            c.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("nasce em rascunho ou interesse", str(erro.exception))

    def test_a_legitimate_transition_still_works(self):
        """Contraprova: um gatilho que recusasse tudo passaria em todos os testes acima."""
        aid = self._candidatura()
        with db_system() as c:
            for destino in ("submitted", "screening", "due_diligence", "approved", "committed"):
                c.run("UPDATE applications SET status = $2 WHERE id = $1", aid, destino)
            self.assertEqual("committed",
                             c.scalar("SELECT status FROM applications WHERE id = $1", aid))

    def test_the_external_flow_has_its_own_graph(self):
        """Edital externo não passa por triagem da plataforma: a OSC acompanha o próprio processo."""
        aid = self._candidatura("submitted", "external_tracking")
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as erro:
                conn.run("UPDATE applications SET status = 'screening' WHERE id = $1", aid)
            self.assertIn("external_tracking", str(erro.exception))
        finally:
            conn.close()
        with db_system() as c:
            c.run("UPDATE applications SET status = 'approved' WHERE id = $1", aid)
            self.assertEqual("approved",
                             c.scalar("SELECT status FROM applications WHERE id = $1", aid))

    def test_updating_another_column_does_not_trip_the_trigger(self):
        """Gatilho em `UPDATE OF status`: mexer em outra coluna de candidatura terminal tem de passar."""
        aid = self._candidatura("closed")
        with db_system() as c:
            c.run("UPDATE applications SET decision_note = 'anotação posterior' WHERE id = $1", aid)
            self.assertEqual("anotação posterior",
                             c.scalar("SELECT decision_note FROM applications WHERE id = $1", aid))


class TheRouteAndTheDatabaseAgreeTests(unittest.TestCase):
    """Duas travas para a mesma regra: a rota dá a mensagem boa, o banco fecha os outros caminhos."""

    def test_the_route_still_answers_with_409_and_the_allowed_list(self):
        osc, projeto = _osc_com_projeto()
        funder = new_account("company", compliance="approved")
        aid = _candidatura(osc, projeto, funder)
        r = osc.post(f"/v1/applications/{aid}/transition", {"to_status": "closed"})
        self.assertEqual(409, r.status, r.json)
        self.assertEqual("invalid_transition", r.json["code"])
        self.assertEqual(["submitted", "withdrawn"], sorted(r.json["details"]["allowed"]))

    def test_the_database_catches_what_a_route_written_without_the_rule_would_let_through(self):
        """Este é o teste que justifica a migração: simula o caminho que a rota não cobre."""
        osc, projeto = _osc_com_projeto()
        funder = new_account("company", compliance="approved")
        aid = _candidatura(osc, projeto, funder)
        with db_system() as c:
            c.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                # Exatamente o UPDATE que uma rota nova escreveria sem consultar `allowed()`.
                c.run("UPDATE applications SET status = 'in_execution' WHERE id = $1", aid)
            c.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("não permitida", str(erro.exception))


if __name__ == "__main__":
    unittest.main()
