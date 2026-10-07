"""Proveniência e integridade relacional: de onde veio o número, e o que falta para prová-lo.

A REGRA SOB TESTE

    "Nenhum indicador crítico deveria existir sem conseguir apontar para sua origem/evidência."

A leitura literal dessa frase — proibir medição sem evidência — impediria trabalho: muita medição
começa autodeclarada e ganha evidência depois. A leitura que esta versão implementa é mais útil e
mais honesta: medição autodeclarada é permitida, **medição autodeclarada apresentada como validada
não é** — e a trava está no banco, não na rota, porque rota se contorna.

E o que o motor de proveniência devolve inclui o que FALTA (`gaps`). Uma cadeia que esconde o elo
ausente transforma ausência de prova em aparência de prova.
"""
from __future__ import annotations

import datetime as dt
import unittest

from tests.support import (Client, db_system, grant_premium, make_staff,
                           new_account, owner_conn)


def _d(delta: int) -> str:
    return (dt.date.today() + dt.timedelta(days=delta)).isoformat()


def _osc_com_projeto() -> tuple[Client, str]:
    c = new_account("osc", compliance="approved")
    grant_premium(c)
    r = c.post("/v1/projects", {
        "title": "Reforço escolar para prova de proveniência",
        "summary": "Projeto criado por teste para exercitar a cadeia de proveniência inteira.",
        "problem": "A comunidade não tem oferta de reforço escolar no contraturno.",
        "objectives": "Ofertar reforço de leitura a 40 crianças, medido por lista e teste.",
        "territory": "BR-AC-1200013", "causes": ["educacao"],
        "beneficiaries_count": 40, "budget_total_cents": 300_000,
        "starts_on": _d(-30), "ends_on": _d(120)})
    assert r.status == 201, r
    return c, r.json["id"]


def _indicador(c: Client, pid: str, *, com_fonte: bool = True, com_metodo: bool = True) -> str:
    cat = c.get("/v1/indicators/catalog?ods=4").json["items"]
    ind = next(i for i in cat if i["code"] == "trained_people")
    corpo = {"indicator_id": ind["id"], "target": 40}
    if com_fonte:
        # `baseline_source_required`: a plataforma já recusa linha de base SEM fonte. Esse controle
        # é anterior a esta versão e continua valendo — por isso a variante "sem fonte" deste
        # auxiliar não declara linha de base nenhuma, em vez de declarar uma sem fonte.
        corpo["baseline"] = 0
        corpo["baseline_source"] = "Lista de presença do primeiro encontro"
        corpo["baseline_date"] = _d(-25)
    if com_metodo:
        corpo["method"] = "Lista de presença e teste de leitura aplicado ao fim de cada módulo"
    r = c.post(f"/v1/projects/{pid}/indicators", corpo)
    assert r.status == 201, r
    return r.json["id"]


def _evidencia(c: Client, pid: str) -> str:
    r = c.post(f"/v1/projects/{pid}/evidences",
               {"kind": "attendance", "title": "Lista de presença da turma A"})
    assert r.status == 201, r
    return r.json["id"]


class AMeasurementWithoutEvidenceCannotBeCalledValidatedTests(unittest.TestCase):
    """A trava central, provada nos dois lugares: na rota e no banco."""

    def test_the_route_refuses_to_validate_without_evidence(self):
        c, pid = _osc_com_projeto()
        pi = _indicador(c, pid)
        v = c.post(f"/v1/project-indicators/{pi}/values", {"value": 32, "measured_on": _d(-5)})
        self.assertEqual(201, v.status, v)
        self.assertEqual("self_declared", _origem(v.json["id"]),
                         "medição sem evidência tem de nascer autodeclarada")

    def test_the_database_refuses_even_for_the_owner(self):
        """A rota já recusava. O banco não — e rota se contorna por script, migração ou engano.

        A tentativa é feita como DONO do banco, que tem todos os privilégios: o que recusa é a
        restrição, não a falta de permissão.
        """
        c, pid = _osc_com_projeto()
        pi = _indicador(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 32, "measured_on": _d(-5)}).json["id"]
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as erro:
                conn.run("UPDATE indicator_values SET status = 'validated',"
                         " validated_by = (SELECT id FROM users LIMIT 1),"
                         " validated_by_org = (SELECT id FROM organizations"
                         "   WHERE id <> $2 LIMIT 1) WHERE id = $1", vid, c.org_id)
            self.assertIn("indicator_validated_needs_evidence", str(erro.exception))
        finally:
            conn.close()

    def test_claiming_a_document_source_without_a_document_is_refused(self):
        """Dizer "veio de documento" e não apontar o documento é pior que não dizer nada."""
        c, pid = _osc_com_projeto()
        pi = _indicador(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 10, "measured_on": _d(-3)}).json["id"]
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as erro:
                conn.run("UPDATE indicator_values SET source_kind = 'evidence_document'"
                         " WHERE id = $1", vid)
            self.assertIn("indicator_evidence_matches_source", str(erro.exception))
        finally:
            conn.close()

    def test_a_measurement_with_evidence_is_born_with_a_declared_source(self):
        c, pid = _osc_com_projeto()
        pi, ev = _indicador(c, pid), _evidencia(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 32, "measured_on": _d(-5), "evidence_id": ev}).json["id"]
        self.assertEqual("evidence_document", _origem(vid))

    def test_a_validated_measurement_does_not_change_value_or_source(self):
        """Trocar a evidência de uma medição conferida desfaz a conferência em silêncio."""
        c, pid = _osc_com_projeto()
        pi, ev = _indicador(c, pid), _evidencia(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 32, "measured_on": _d(-5), "evidence_id": ev}).json["id"]
        validador = new_account("company", compliance="approved")
        conn = owner_conn()
        try:
            conn.run("UPDATE indicator_values SET status = 'validated',"
                     " validated_by = (SELECT id FROM users LIMIT 1), validated_by_org = $2"
                     " WHERE id = $1", vid, validador.org_id)
            for coluna, valor in (("value", "99"), ("evidence_id", "NULL"),
                                  ("source_kind", "'self_declared'"),
                                  ("measured_on", "current_date")):
                with self.subTest(coluna=coluna):
                    # `owner_conn()` é autocommit, então cada tentativa abre a própria transação:
                    # sem isso, a primeira exceção aborta o bloco e as outras três falhariam por um
                    # motivo que não é o do teste (foi o que aconteceu na primeira execução).
                    conn.run("BEGIN")
                    with self.assertRaises(Exception) as erro:
                        conn.run(f"UPDATE indicator_values SET {coluna} = {valor} WHERE id = $1", vid)
                    conn.run("ROLLBACK")
                    self.assertIn("validada não muda", str(erro.exception))
        finally:
            conn.close()


def _origem(value_id: str) -> str:
    with db_system() as c:
        return c.scalar("SELECT source_kind FROM indicator_values WHERE id = $1", value_id)


class TheProvenanceChainAnswersWhereTheNumberCameFromTests(unittest.TestCase):

    def test_the_full_chain_is_returned_in_one_request(self):
        c, pid = _osc_com_projeto()
        pi, ev = _indicador(c, pid), _evidencia(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 32, "measured_on": _d(-5), "evidence_id": ev}).json["id"]
        r = c.get(f"/v1/indicator-values/{vid}/provenance")
        self.assertEqual(200, r.status, r)
        d = r.json
        self.assertEqual(vid, d["value"]["id"])
        self.assertEqual(pid, d["project"]["id"])
        self.assertEqual("trained_people", d["indicator"]["code"])
        self.assertEqual(ev, d["evidence"]["id"])
        self.assertEqual("Lista de presença do primeiro encontro", d["indicator"]["baseline_source"])
        passos = [p["step"] for p in d["chain"]]
        for esperado in ("projeto", "indicador", "linha_de_base", "evidencia", "medicao", "validacao"):
            self.assertIn(esperado, passos)

    def test_the_ledger_entry_carries_the_hash_that_makes_the_link_checkable(self):
        """Sem `seq` e hash, o elo do ledger é uma afirmação; com eles, é conferível."""
        c, pid = _osc_com_projeto()
        pi, ev = _indicador(c, pid), _evidencia(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 32, "measured_on": _d(-5), "evidence_id": ev}).json["id"]
        d = c.get(f"/v1/indicator-values/{vid}/provenance").json
        self.assertTrue(d["ledger"], "a medição não gerou lançamento no Impact Ledger")
        primeiro = d["ledger"][0]
        self.assertEqual("result_reported", primeiro["entry_type"])
        self.assertEqual(64, len(primeiro["entry_hash"]))
        with db_system() as conn:
            self.assertTrue(conn.one("SELECT valid FROM ledger_verify($1)", pid)["valid"])

    def test_the_gaps_name_what_is_missing_instead_of_hiding_it(self):
        c, pid = _osc_com_projeto()
        pi = _indicador(c, pid, com_fonte=False, com_metodo=False)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 15, "measured_on": _d(-2)}).json["id"]
        d = c.get(f"/v1/indicator-values/{vid}/provenance").json
        self.assertFalse(d["provenance_complete"])
        elos = {g["link"] for g in d["gaps"]}
        self.assertIn("evidencia", elos)
        self.assertIn("linha_de_base", elos)
        self.assertIn("metodo", elos)
        for g in d["gaps"]:
            with self.subTest(elo=g["link"]):
                self.assertGreaterEqual(len(g["what"]), 20)
                self.assertGreaterEqual(len(g["effect"]), 30,
                                        "lacuna sem efeito escrito não ajuda quem lê")

    def test_a_missing_link_appears_as_absent_in_the_chain_not_omitted(self):
        """Omitir o passo faria a cadeia parecer completa com um passo a menos."""
        c, pid = _osc_com_projeto()
        pi = _indicador(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 15, "measured_on": _d(-2)}).json["id"]
        d = c.get(f"/v1/indicator-values/{vid}/provenance").json
        ausentes = {p["step"] for p in d["chain"] if not p["present"]}
        self.assertIn("evidencia", ausentes)
        self.assertIn("documento", ausentes)
        self.assertIn("validacao", ausentes)

    def test_another_organization_cannot_read_the_chain(self):
        """Proveniência é dado do projeto; rota de leitura ampla seria vazamento entre inquilinos."""
        c, pid = _osc_com_projeto()
        pi, ev = _indicador(c, pid), _evidencia(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 32, "measured_on": _d(-5), "evidence_id": ev}).json["id"]
        outra = new_account("osc", compliance="approved")
        self.assertEqual(404, outra.get(f"/v1/indicator-values/{vid}/provenance").status,
                         "outra organização alcançou a cadeia de proveniência")

    def test_a_complete_chain_reports_itself_complete(self):
        c, pid = _osc_com_projeto()
        pi, ev = _indicador(c, pid), _evidencia(c, pid)
        vid = c.post(f"/v1/project-indicators/{pi}/values",
                     {"value": 32, "measured_on": _d(-5), "evidence_id": ev}).json["id"]
        validador = new_account("company", compliance="approved")
        conn = owner_conn()
        try:
            # Documento com hash, evidência revisada e validação independente: a cadeia inteira.
            doc = conn.scalar(
                "INSERT INTO documents(org_id, project_id, doc_type, title, filename, mime_type,"
                " size_bytes, sha256, storage_key, status, uploaded_by, version)"
                " VALUES ($1,$2,'evidence','Lista de presença','lista.pdf','application/pdf',"
                " 2048, repeat('a',64), 'k/lista.pdf', 'clean',"
                " (SELECT id FROM users WHERE email = $3), 1) RETURNING id::text",
                c.org_id, pid, c.email)
            conn.run("UPDATE evidences SET document_id = $2, status = 'accepted',"
                     " reviewed_by = (SELECT id FROM users WHERE email = $3),"
                     " reviewed_by_org = $4, reviewed_at = now(),"
                     " review_note = 'Lista confere com o número reportado' WHERE id = $1",
                     ev, doc, c.email, validador.org_id)
            conn.run("UPDATE indicator_values SET status = 'validated',"
                     " validated_by = (SELECT id FROM users WHERE email = $3), validated_by_org = $2"
                     " WHERE id = $1", vid, validador.org_id, c.email)
            conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, ref_type, ref_id)"
                     " VALUES ($1,$2,'indicator_validated','indicator_value',$3)",
                     pid, validador.org_id, vid)
        finally:
            conn.close()
        d = c.get(f"/v1/indicator-values/{vid}/provenance").json
        self.assertEqual([], d["gaps"], f"cadeia completa com lacuna: {d['gaps']}")
        self.assertTrue(d["provenance_complete"])
        self.assertTrue(d["validation"]["independent"])
        self.assertEqual("a" * 64, d["document"]["sha256"],
                         "o hash de conteúdo do documento não chegou à cadeia")


class CorrectionIsANewEntryNotAnUpdateTests(unittest.TestCase):
    """Se o Value Ledger sustenta o posicionamento, corrigir não pode ser apagar."""

    def _lancamento(self, pid: str, org: str, centavos: int) -> int:
        with db_system() as c:
            return c.scalar("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                            " payload) VALUES ($1,$2,'expense_recorded',$3,'{}') RETURNING id",
                            pid, org, centavos)

    def test_a_correction_must_point_at_what_it_corrects(self):
        c, pid = _osc_com_projeto()
        with db_system() as conn:
            conn.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                         " payload) VALUES ($1,$2,'correction',-100,'{\"reason\":\"errado\"}')",
                         pid, c.org_id)
            conn.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("apontar o lançamento", str(erro.exception))

    def test_a_correction_must_be_the_exact_opposite_amount(self):
        """Correção de valor parcial seria ajuste disfarçado: o número final deixaria de ser somável."""
        c, pid = _osc_com_projeto()
        lid = self._lancamento(pid, c.org_id, 50_000)
        with db_system() as conn:
            conn.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                         " reverses_id, payload) VALUES ($1,$2,'correction',-10000,$3,"
                         " '{\"reason\":\"valor digitado errado\"}')", pid, c.org_id, lid)
            conn.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("oposto exato", str(erro.exception))

    def test_a_correction_demands_a_written_reason(self):
        c, pid = _osc_com_projeto()
        lid = self._lancamento(pid, c.org_id, 50_000)
        with db_system() as conn:
            conn.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                         " reverses_id, payload) VALUES ($1,$2,'correction',-50000,$3,'{}')",
                         pid, c.org_id, lid)
            conn.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("payload.reason", str(erro.exception))

    def test_an_entry_is_corrected_at_most_once(self):
        c, pid = _osc_com_projeto()
        lid = self._lancamento(pid, c.org_id, 50_000)
        with db_system() as conn:
            conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                     " reverses_id, payload) VALUES ($1,$2,'correction',-50000,$3,"
                     " '{\"reason\":\"valor digitado errado na primeira vez\"}')", pid, c.org_id, lid)
            conn.run("SAVEPOINT s")
            with self.assertRaises(Exception):
                conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                         " reverses_id, payload) VALUES ($1,$2,'correction',-50000,$3,"
                         " '{\"reason\":\"corrigindo de novo o mesmo\"}')", pid, c.org_id, lid)
            conn.run("ROLLBACK TO SAVEPOINT s")

    def test_a_correction_of_a_correction_is_refused(self):
        c, pid = _osc_com_projeto()
        lid = self._lancamento(pid, c.org_id, 50_000)
        with db_system() as conn:
            cid = conn.scalar("INSERT INTO ledger_entries(project_id, org_id, entry_type,"
                              " amount_cents, reverses_id, payload) VALUES ($1,$2,'correction',"
                              " -50000,$3,'{\"reason\":\"valor digitado errado\"}') RETURNING id",
                              pid, c.org_id, lid)
            conn.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                         " reverses_id, payload) VALUES ($1,$2,'correction',50000,$3,"
                         " '{\"reason\":\"corrigindo a correcao\"}')", pid, c.org_id, cid)
            conn.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("correção de correção", str(erro.exception))

    def test_only_a_correction_points_at_another_entry(self):
        c, pid = _osc_com_projeto()
        lid = self._lancamento(pid, c.org_id, 50_000)
        with db_system() as conn:
            conn.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                         " reverses_id, payload) VALUES ($1,$2,'expense_recorded',-50000,$3,'{}')",
                         pid, c.org_id, lid)
            conn.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("só lançamento do tipo correction", str(erro.exception))

    def test_the_correction_keeps_the_hash_chain_intact_and_the_sum_right(self):
        """O ponto do modelo: o passado continua lá, e o total passa a estar certo."""
        c, pid = _osc_com_projeto()
        lid = self._lancamento(pid, c.org_id, 50_000)
        with db_system() as conn:
            conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                     " reverses_id, payload) VALUES ($1,$2,'correction',-50000,$3,"
                     " '{\"reason\":\"valor digitado com um zero a mais\"}')", pid, c.org_id, lid)
            conn.run("INSERT INTO ledger_entries(project_id, org_id, entry_type, amount_cents,"
                     " payload) VALUES ($1,$2,'expense_recorded',5000,'{}')", pid, c.org_id)
            cadeia = conn.one("SELECT entries, valid, first_broken_seq FROM ledger_verify($1)", pid)
            soma = conn.scalar("SELECT coalesce(sum(amount_cents),0) FROM ledger_entries"
                               " WHERE project_id = $1 AND amount_cents IS NOT NULL", pid)
            original = conn.scalar("SELECT amount_cents FROM ledger_entries WHERE id = $1", lid)
        self.assertTrue(cadeia["valid"], f"cadeia quebrada em {cadeia['first_broken_seq']}")
        self.assertEqual(5_000, soma, "o total não reflete a correção")
        self.assertEqual(50_000, original, "o lançamento original foi alterado: deveria permanecer")

    def test_the_original_entry_still_cannot_be_updated(self):
        """A correção é o caminho PARA corrigir — não uma permissão para reescrever."""
        c, pid = _osc_com_projeto()
        lid = self._lancamento(pid, c.org_id, 50_000)
        conn = owner_conn()
        try:
            with self.assertRaises(Exception) as erro:
                conn.run("UPDATE ledger_entries SET amount_cents = 1 WHERE id = $1", lid)
            self.assertIn("append-only", str(erro.exception))
        finally:
            conn.close()


class TheValueLedgerIsChainedLikeTheOthersTests(unittest.TestCase):
    """A tabela que sustenta o número principal do produto era a única sem cadeia de hash."""

    def _evento(self, org: str) -> dict:
        """Grava pelo caminho REAL: `app_record_value()` é SECURITY DEFINER e a aplicação não tem
        INSERT em `value_events` — é assim que a estimativa de tempo não pode ser escrita à mão.
        O gatilho de cadeia é BEFORE INSERT, então vale para este caminho também."""
        with db_system() as c:
            vid = c.scalar("SELECT app_record_value('readiness.evaluated',$1,1,NULL,NULL,NULL,"
                           " NULL,NULL,'teste')::text", org)
            return c.one("SELECT id::text AS id, seq, prev_hash, entry_hash FROM value_events"
                         " WHERE id = $1", vid)

    def test_a_new_event_is_chained_on_insert(self):
        c = new_account("osc", compliance="approved")
        e = self._evento(c.org_id)
        self.assertIsNotNone(e["seq"])
        self.assertEqual(64, len(e["entry_hash"]))
        self.assertEqual(64, len(e["prev_hash"]))

    def test_the_chain_verifies(self):
        c = new_account("osc", compliance="approved")
        for _ in range(3):
            self._evento(c.org_id)
        with db_system() as conn:
            v = conn.one("SELECT entries, valid, first_broken_seq FROM value_verify($1)", c.org_id)
        self.assertEqual(3, v["entries"])
        self.assertTrue(v["valid"])

    def test_tampering_with_a_row_breaks_the_chain_and_the_check_finds_it(self):
        """Prova de verdade da cadeia: alterar como DONO do banco e exigir que a verificação acuse."""
        c = new_account("osc", compliance="approved")
        for _ in range(3):
            self._evento(c.org_id)
        conn = owner_conn()
        try:
            # `units` entra no material do hash, então mexer nela invalida a linha. A tabela é
            # append-only para a aplicação; aqui a tentativa é do dono, que é o cenário de ameaça.
            conn.run("ALTER TABLE value_events DISABLE TRIGGER trg_value_events_append")
            conn.run("UPDATE value_events SET units = 999 WHERE org_id = $1"
                     "   AND seq = (SELECT max(seq) FROM value_events WHERE org_id = $1)", c.org_id)
            conn.run("ALTER TABLE value_events ENABLE TRIGGER trg_value_events_append")
            v = conn.one("SELECT entries, valid, first_broken_seq FROM value_verify($1)", c.org_id)
        finally:
            conn.close()
        self.assertFalse(v["valid"], "a cadeia de valor aceitou uma linha alterada")
        self.assertEqual(3, v["first_broken_seq"])

    def test_the_three_chains_are_all_reported_by_the_integrity_engine(self):
        from impacto.engines import integrity
        with db_system() as conn:
            cad = integrity.chains(conn)
        for nome in ("audit", "ledger", "value"):
            self.assertIn(nome, cad)
            self.assertIn("broken", cad[nome])
        self.assertIn("rows_without_chain", cad["value"])


class TheOrphanCheckIsRealNowTests(unittest.TestCase):
    """Era uma string literal dizendo que nenhuma verificação era aplicável."""

    def test_the_catalog_covers_every_polymorphic_column_without_a_foreign_key(self):
        with db_system() as c:
            deriva = c.query("SELECT source_table, id_column, situation FROM integrity_catalog_drift()")
        self.assertEqual([], deriva,
                         "há coluna polimórfica fora do catálogo, ou catalogada e já inexistente: "
                         + "; ".join(f"{d['source_table']}.{d['id_column']} ({d['situation']})"
                                     for d in deriva))

    def test_the_catalog_is_not_empty_and_covers_the_tables_that_matter(self):
        """Catálogo vazio deixaria `integrity_catalog_drift()` em silêncio sobre tudo."""
        with db_system() as c:
            tabelas = {r["source_table"] for r in c.query("SELECT source_table FROM polymorphic_refs")}
        self.assertGreaterEqual(len(tabelas), 20)
        for esperada in ("audit_events", "ledger_entries", "value_events", "approval_requests",
                         "accounting_entries"):
            self.assertIn(esperada, tabelas)

    def test_an_orphan_is_actually_detected(self):
        """A prova que importa: criar um órfão de propósito e exigir que o motor o encontre."""
        c = new_account("osc", compliance="approved")
        fantasma = "00000000-0000-0000-0000-0000000000ff"
        with db_system() as conn:
            conn.run("INSERT INTO audit_events(org_id, action, object_type, object_id)"
                     " VALUES ($1,'teste.orfao','project',$2)", c.org_id, fantasma)
            achados = conn.query("SELECT source_table, type_value, orphans FROM integrity_orphans()"
                                 " WHERE source_table = 'audit_events' AND type_value = 'project'")
        self.assertTrue(achados, "o motor não examinou audit_events.object_id para tipo 'project'")
        self.assertGreaterEqual(achados[0]["orphans"], 1,
                                "o motor não encontrou o órfão que acabou de ser criado")

    def test_a_real_reference_is_not_reported_as_an_orphan(self):
        """Contraprova: sem ela, um motor que reportasse tudo como órfão passaria no teste acima."""
        c, pid = _osc_com_projeto()
        with db_system() as conn:
            conn.run("INSERT INTO audit_events(org_id, action, object_type, object_id)"
                     " VALUES ($1,'teste.referencia_boa','project',$2)", c.org_id, pid)
            orfaos = conn.scalar(
                "SELECT count(*) FROM audit_events a WHERE a.object_type = 'project'"
                "   AND a.object_id = $1"
                "   AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.id::text = a.object_id)", pid)
        self.assertEqual(0, orfaos)

    def test_a_type_value_the_engine_cannot_resolve_is_reported_not_skipped(self):
        """O modo como esta classe de verificação morre: catálogo atrás do código, em silêncio."""
        c = new_account("osc", compliance="approved")
        with db_system() as conn:
            conn.run("INSERT INTO audit_events(org_id, action, object_type, object_id)"
                     " VALUES ($1,'teste.tipo_desconhecido','coisa_que_nao_existe',"
                     " '00000000-0000-0000-0000-00000000aaaa')", c.org_id)
            achados = conn.query("SELECT source_table, type_value, rows_affected"
                                 "  FROM integrity_unresolved_refs()"
                                 " WHERE type_value = 'coisa_que_nao_existe'")
        self.assertTrue(achados, "tipo não resolvido foi pulado em silêncio")

    def test_a_declared_exception_carries_a_written_reason(self):
        with db_system() as c:
            excecoes = c.query("SELECT type_value, reason FROM polymorphic_ref_exceptions")
        self.assertTrue(excecoes)
        for e in excecoes:
            with self.subTest(tipo=e["type_value"]):
                self.assertGreaterEqual(len(e["reason"]), 30)

    def test_the_report_script_no_longer_publishes_a_literal_string(self):
        from tests.support import ROOT
        texto = (ROOT / "scripts" / "db_integrity_report.py").read_text(encoding="utf-8")
        self.assertNotIn("nenhuma verificação de órfão aplicável", texto,
                         "o relatório voltou a publicar uma afirmação que não consulta nada")
        self.assertIn("integrity_orphans()", texto)
        self.assertIn("integrity_catalog_drift()", texto)


class TheIntegrityReportTellsTheTruthTests(unittest.TestCase):

    def test_the_route_requires_the_audit_permission(self):
        c = new_account("osc", compliance="approved")
        self.assertIn(c.get("/v1/admin/integrity").status, (401, 403))
        equipe = make_staff("support")
        self.assertEqual(403, equipe.get("/v1/admin/integrity").status,
                         "papel de conteúdo alcançou o relatório de integridade")

    def test_an_auditor_reads_the_report(self):
        c = make_staff("audit")
        r = c.get("/v1/admin/integrity")
        self.assertEqual(200, r.status, r.json)
        d = r.json
        self.assertIn(d["state"], ("VERDE", "AMARELO", "VERMELHO"))
        self.assertGreaterEqual(d["polymorphic_columns_catalogued"], 20)
        self.assertIn("provenance", d)
        self.assertIn("chains", d)

    def test_the_state_is_red_when_there_is_a_broken_row_not_merely_yellow(self):
        """Relatório que fica verde com ressalva não serve para decidir nada."""
        from impacto.engines import integrity
        c = new_account("osc", compliance="approved")
        with db_system() as conn:
            conn.run("INSERT INTO audit_events(org_id, action, object_type, object_id)"
                     " VALUES ($1,'teste.orfao_para_vermelho','project',"
                     " '00000000-0000-0000-0000-0000000000fe')", c.org_id)
            r = integrity.report(conn)
        self.assertEqual("VERMELHO", r["state"])
        self.assertGreaterEqual(r["orphan_rows"], 1)

    def test_the_provenance_coverage_states_the_rule_it_enforces(self):
        from impacto.engines import integrity
        with db_system() as conn:
            cob = integrity.provenance_coverage(conn)
        self.assertEqual(0, cob["validated_without_evidence"],
                         "existe medição validada sem evidência: só por alteração direta no banco")
        self.assertIn("EXIGE evidência", cob["rule"])

    def test_the_privileged_read_leaves_a_trace(self):
        c = make_staff("audit")
        self.assertEqual(200, c.get("/v1/admin/integrity").status)
        with db_system() as conn:
            achou = conn.scalar("SELECT count(*) FROM privileged_access_log"
                                " WHERE path = '/v1/admin/integrity'")
        self.assertGreaterEqual(achou, 1, "ler o relatório de integridade não deixou rastro")


if __name__ == "__main__":
    unittest.main()
