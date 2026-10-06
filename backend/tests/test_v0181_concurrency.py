"""v0.18.1 — concorrência real nas entidades da camada de impacto (FASE 4 do endurecimento final).

Por que este arquivo existe: toda trava desta camada foi escrita e testada em UMA transação por vez.
Produção não é assim. Duas pessoas da mesma organização clicando ao mesmo tempo, um job rodando
junto com uma rota, um navegador que repete a requisição — é aí que aparecem rodada duplicada,
dois responsáveis pelo mesmo papel, dois denominadores vigentes e selo concedido duas vezes.

O método é sempre o mesmo: N threads disparam a MESMA operação ao mesmo tempo, e o teste afirma
quantas podiam ter sucesso. Quando o banco recusa, a recusa é o resultado esperado.
"""
from __future__ import annotations

import threading
import unittest

from tests.support import PASSWORD, Client, db_system, grant_premium, make_admin, new_account, owner_conn, server

THREADS = 6


def race(fn, n: int = THREADS) -> list:
    """Executa `fn(i)` em N threads soltas ao mesmo tempo; devolve os resultados na ordem de término."""
    barrier = threading.Barrier(n)
    out: list = []
    lock = threading.Lock()

    def run(i: int) -> None:
        barrier.wait()          # todas largam juntas
        try:
            r = fn(i)
        except Exception as exc:                      # noqa: BLE001 — o erro é o resultado
            r = exc
        with lock:
            out.append(r)

    ts = [threading.Thread(target=run, args=(i,)) for i in range(n)]
    for t in ts:
        t.start()
    for t in ts:
        t.join(timeout=120)
    return out


class ConcurrencyBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        cls.admin, _ = make_admin()
        grant_premium(cls.osc)

    def _project(self, title: str) -> str:
        r = self.osc.post("/v1/projects", {
            "title": title,
            "summary": "Projeto criado para exercitar concorrência real na v0.18.1.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 70, "budget_total_cents": 1_200_000})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def _session(self) -> Client:
        """Sessão independente da MESMA organização — é o caso real de duas abas."""
        c = Client("token")
        self.assertEqual(c.login(self.osc.email, PASSWORD).status, 200)
        return c


# ================================================================================ rodada de verificação
class ClaimCheckRaceTests(ConcurrencyBase):
    def test_six_simultaneous_checks_never_produce_two_rows_for_the_same_round(self):
        """`check_round` é calculado com max()+1: sob corrida, duas rodadas podiam colidir.

        O índice único `(claim_id, check_round, rule_code)` é quem decide. O teste aceita qualquer
        número de sucessos, mas exige que NÃO exista rodada com regra duplicada e que cada rodada
        bem-sucedida esteja completa — meia rodada gravada falsearia a situação derivada.
        """
        pid = self._project("Projeto da corrida de verificação")
        cid = self.osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": pid, "claim_kind": "result",
            "statement": "Alegação verificada por várias sessões ao mesmo tempo."}).json["id"]
        sessions = [self._session() for _ in range(THREADS)]
        res = race(lambda i: sessions[i].post(f"/v1/claims/{cid}/check", {}))
        ok = [r for r in res if getattr(r, "status", None) == 201]
        self.assertGreaterEqual(len(ok), 1, f"nenhuma verificação concluiu: {res}")
        with db_system() as d:
            dup = d.query(
                "SELECT check_round, rule_code, count(*) AS n FROM claim_checks WHERE claim_id = $1"
                " GROUP BY 1, 2 HAVING count(*) > 1", cid)
            self.assertEqual(dup, [], f"rodada com regra duplicada: {dup}")
            tamanhos = [r["n"] for r in d.query(
                "SELECT check_round, count(*) AS n FROM claim_checks WHERE claim_id = $1"
                " GROUP BY 1", cid)]
        self.assertTrue(tamanhos)
        self.assertEqual(set(tamanhos), {12}, f"rodada incompleta gravada: {tamanhos}")

    def test_the_derived_status_stays_coherent_after_the_race(self):
        pid = self._project("Projeto da coerência pós-corrida")
        cid = self.osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": pid, "claim_kind": "result",
            "statement": "Alegação cuja situação precisa ser coerente depois da corrida."}).json["id"]
        sessions = [self._session() for _ in range(THREADS)]
        race(lambda i: sessions[i].post(f"/v1/claims/{cid}/check", {}))
        got = self.osc.get(f"/v1/claims/{cid}").json
        self.assertIn(got["status"], ("flagged", "attention", "substantiated"))
        # a situação vem da ÚLTIMA rodada, e a última rodada tem de existir inteira
        ultima = [c for c in got["checks"] if c["check_round"] == got["check_round"]]
        self.assertEqual(len(ultima), 12, "a última rodada não está completa")


# ================================================================================ responsabilidade
class ResponsibilityRaceTests(ConcurrencyBase):
    def test_six_simultaneous_assignments_leave_exactly_one_current_holder(self):
        """`ux_responsibility_current` é índice único parcial: a corrida tem de deixar UM."""
        pid = self._project("Projeto da corrida de designação")
        sessions = [self._session() for _ in range(THREADS)]
        res = race(lambda i: sessions[i].post("/v1/responsibility/assignments", {
            "scope": "project", "subject_id": pid, "role_code": "project_coordinator",
            "mandate_basis": f"Designação simultânea número {i}, para exercitar a corrida.",
            "external_name": f"Pessoa Simultânea {i}"}))
        criados = [r for r in res if getattr(r, "status", None) == 201]
        conflitos = [r for r in res if getattr(r, "status", None) == 409]
        self.assertEqual(len(criados), 1, f"mais de uma designação corrente: {[getattr(r,'status',r) for r in res]}")
        self.assertEqual(len(conflitos), THREADS - 1)
        with db_system() as d:
            n = d.scalar("SELECT count(*) FROM responsibility_assignments WHERE scope = 'project'"
                         "   AND subject_id = $1 AND role_code = 'project_coordinator'"
                         "   AND ended_on IS NULL", pid)
        self.assertEqual(n, 1)

    def test_simultaneous_endings_close_the_assignment_once(self):
        pid = self._project("Projeto da corrida de encerramento")
        aid = self.osc.post("/v1/responsibility/assignments", {
            "scope": "project", "subject_id": pid, "role_code": "technical_lead",
            "mandate_basis": "Designação criada para exercitar o encerramento concorrente.",
            "external_name": "Pessoa a ser encerrada"}).json["id"]
        sessions = [self._session() for _ in range(THREADS)]
        res = race(lambda i: sessions[i].post(f"/v1/responsibility/assignments/{aid}/end", {
            "reason": f"Encerramento simultâneo número {i}, para exercitar a corrida."}))
        ok = [r for r in res if getattr(r, "status", None) == 200]
        self.assertEqual(len(ok), 1, "o encerramento aconteceu mais de uma vez")


# ================================================================================ denominador e selo
class EquityAndSealRaceTests(ConcurrencyBase):
    def test_simultaneous_denominators_leave_one_current_version(self):
        """`close_previous_denominator()` fecha a versão anterior ANTES de inserir a nova."""
        pid = self._project("Projeto da corrida de denominador")
        sessions = [self._session() for _ in range(THREADS)]
        res = race(lambda i: sessions[i].post("/v1/equity/denominators", {
            "project_id": pid, "kind": "eligible_population", "value": 100 + i,
            "unit": "pessoas", "reference_date": "2025-01-01",
            "source_name": f"Fonte declarada da versão {i}", "source_date": "2026-01-01",
            "method_note": "Método declarado com extensão suficiente para o CHECK do banco."}))
        criados = [r for r in res if getattr(r, "status", None) == 201]
        self.assertGreaterEqual(len(criados), 1, f"nenhum denominador criado: {res}")
        with db_system() as d:
            vigentes = d.scalar(
                "SELECT count(*) FROM equity_denominators WHERE project_id = $1"
                "   AND kind = 'eligible_population' AND effective_until IS NULL", pid)
        self.assertEqual(vigentes, 1, "ficou mais de um denominador vigente para o mesmo tipo")

    def test_simultaneous_seal_awards_do_not_duplicate_the_evaluation_trail(self):
        """Conceder duas vezes é aceitável (a concessão é um fato); mentir sobre o critério não é."""
        d = self.admin.post("/v1/admin/seals/definitions", {
            "code": "selo_corrida_teste", "scope": "organization",
            "title": "Selo da corrida de concessão",
            "what_it_attests": "Atesta compliance aprovado, apenas para o teste de concorrência.",
            "what_it_does_not_attest": "Não atesta qualidade, impacto nem elegibilidade em edital.",
            "validity_days": 90, "criteria": [{"rule_code": "compliance_approved"}]}).json["id"]
        self.admin.post(f"/v1/admin/seals/definitions/{d}/publish", {})
        admins = []
        for _ in range(THREADS):
            c, _email = make_admin()
            admins.append(c)
        res = race(lambda i: admins[i].post("/v1/admin/seals/awards",
                                            {"definition_id": d, "subject_id": self.osc.org_id}))
        ok = [r for r in res if getattr(r, "status", None) == 201]
        self.assertGreaterEqual(len(ok), 1, f"nenhuma concessão: {[getattr(r,'status',r) for r in res]}")
        with db_system() as sysd:
            for row in sysd.query(
                    "SELECT evidence FROM seal_awards WHERE definition_id = $1", d):
                self.assertTrue(row["evidence"], "concessão sem evidência do critério")
                self.assertTrue(all(item["met"] for item in row["evidence"]),
                                "concessão gravada com critério não satisfeito")
            # cada concessão tem a avaliação correspondente registrada
            n_aw = sysd.scalar("SELECT count(*) FROM seal_awards WHERE definition_id = $1", d)
            n_ev = sysd.scalar("SELECT count(*) FROM seal_evaluations WHERE definition_id = $1", d)
        self.assertGreaterEqual(n_ev, n_aw, "houve concessão sem avaliação registrada")


# ================================================================================ reputação e transação
class SnapshotRaceTests(ConcurrencyBase):
    def test_simultaneous_reputation_snapshots_never_write_a_value_without_observation(self):
        sessions = [self._session() for _ in range(THREADS)]
        res = race(lambda i: sessions[i].post("/v1/reputation/snapshots", {}))
        ok = [r for r in res if getattr(r, "status", None) == 201]
        self.assertGreaterEqual(len(ok), 1, f"nenhum retrato gravado: {res}")
        with db_system() as d:
            ruim = d.scalar("SELECT count(*) FROM reputation_snapshots WHERE org_id = $1"
                            "   AND value IS NOT NULL AND observations = 0", self.osc.org_id)
            faixa = d.scalar("SELECT count(*) FROM reputation_snapshots WHERE org_id = $1"
                             "   AND band = 'insufficient' AND value IS NOT NULL", self.osc.org_id)
        self.assertEqual((ruim, faixa), (0, 0))

    def test_an_aborted_transaction_leaves_nothing_behind(self):
        """Transação abortada no meio não pode deixar meia alegação no banco."""
        pid = self._project("Projeto da transação abortada")
        antes = None
        with db_system() as d:
            antes = d.scalar("SELECT count(*) FROM claims WHERE subject_id = $1", pid)
        oc = owner_conn()
        oc.run("BEGIN")
        oc.run("INSERT INTO claims(org_id, subject_type, subject_id, claim_kind, statement)"
               " VALUES ($1,'project',$2,'result','Alegação que vai ser descartada no ROLLBACK.')",
               self.osc.org_id, pid)
        oc.run("ROLLBACK")
        with db_system() as d:
            depois = d.scalar("SELECT count(*) FROM claims WHERE subject_id = $1", pid)
        self.assertEqual(antes, depois, "o ROLLBACK deixou linha no banco")

    def test_a_savepoint_keeps_the_work_done_before_a_refused_statement(self):
        """A lição da v0.17.0: capturar erro sem SAVEPOINT aborta a transação inteira."""
        pid = self._project("Projeto do savepoint")
        oc = owner_conn()
        oc.run("BEGIN")
        oc.run("INSERT INTO claims(org_id, subject_type, subject_id, claim_kind, statement)"
               " VALUES ($1,'project',$2,'result','Alegação que PERMANECE depois do savepoint.')",
               self.osc.org_id, pid)
        oc.run("SAVEPOINT s1")
        try:
            oc.run("INSERT INTO claims(org_id, subject_type, subject_id, claim_kind, statement)"
                   " VALUES ($1,'project',$2,'result','curta')", self.osc.org_id, pid)
        except Exception:
            oc.run("ROLLBACK TO SAVEPOINT s1")
        oc.run("COMMIT")
        with db_system() as d:
            n = d.scalar("SELECT count(*) FROM claims WHERE subject_id = $1"
                         "   AND statement LIKE 'Alegação que PERMANECE%'", pid)
        self.assertEqual(n, 1, "o savepoint não preservou o trabalho anterior")
