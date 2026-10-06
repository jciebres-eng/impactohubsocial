"""v0.18.0 — responsabilidade: quem responde por quê, em que escopo, em que período.

A ideia que estes testes protegem é a separação: **responsabilidade não é assinatura.** Assinatura
amarra uma pessoa a um CONTEÚDO (sha256); designação amarra uma pessoa a um ESCOPO num PERÍODO. Uma
decisão pode existir sem assinatura, e uma assinatura pode existir sem decisão.

E protegem três travas que o banco aplica: designação não é reescrita, decisão fora do período é
recusada, e quatro-olhos declarado em dado (`requires_two`) não depende de a rota lembrar.
"""
from __future__ import annotations

import unittest
from datetime import date, timedelta

from tests.support import app_tx, grant_premium, new_account, owner_conn

BASIS = "Designação registrada em ata da diretoria de 12 de março, item 4 da pauta."
LONG = "Declaração de decisão com extensão suficiente para o CHECK do banco nesta coluna."


class RespBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        # cada teste cria o próprio projeto (ordem alfabética compartilharia estado), e o plano
        # gratuito limita projetos ativos a 10
        grant_premium(cls.osc)

    def _project(self, client=None) -> str:
        c = client or self.osc
        r = c.post("/v1/projects", {
            "title": "Projeto com responsabilidade designada",
            "summary": "Projeto criado para exercitar a designação de responsabilidade da v0.18.0.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 60, "budget_total_cents": 1_500_000})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def _assign(self, subject: str, role: str = "project_coordinator", *, scope: str = "project",
                client=None, external: str | None = None, starts_on=None):
        c = client or self.osc
        body = {"scope": scope, "subject_id": subject, "role_code": role,
                "mandate_basis": BASIS}
        if external:
            body["external_name"] = external
            body["external_note"] = "Consultora contratada para o período do projeto."
        else:
            body["user_id"] = c.user["id"]
        if starts_on:
            body["starts_on"] = starts_on
        return c.post("/v1/responsibility/assignments", body)


# ================================================================================================ catálogo
class CatalogTests(RespBase):
    def test_every_role_says_what_it_does_not_answer_for(self):
        r = self.osc.get("/v1/responsibility/roles")
        self.assertEqual(r.status, 200, r)
        self.assertGreaterEqual(len(r.json["items"]), 8)
        for item in r.json["items"]:
            self.assertGreaterEqual(len(item["does_not_answer_for"]), 20, item["code"])
            self.assertTrue(item["scopes"], item["code"])

    def test_the_catalog_says_designating_creates_no_legal_power(self):
        j = self.osc.get("/v1/responsibility/roles").json
        self.assertIn("NÃO cria poder de representação", j["note"])
        self.assertIn("NÃO é assinatura", j["separation"])

    def test_the_decision_kinds_declare_which_ones_need_four_eyes(self):
        kinds = {k["code"]: k for k in
                 self.osc.get("/v1/responsibility/roles").json["decision_kinds"]}
        self.assertTrue(kinds["authorization_to_publish"]["requires_two"])
        self.assertTrue(kinds["acceptance_of_risk"]["requires_two"])
        self.assertFalse(kinds["technical_opinion"]["requires_two"])


# ================================================================================================ designação
class AssignmentTests(RespBase):
    def test_a_role_has_one_current_holder_per_scope(self):
        pid = self._project()
        self.assertEqual(self._assign(pid).status, 201)
        again = self._assign(pid, external="Maria Consultora")
        self.assertEqual(again.status, 409, again)
        self.assertEqual(again.json["code"], "role_already_held")

    def test_a_role_outside_its_scopes_is_refused_by_the_database(self):
        pid = self._project()
        r = self._assign(pid, "legal_representative")
        self.assertEqual(r.status, 422, r)
        self.assertIn("não se aplica ao escopo", r.json["title"])

    def test_the_person_is_either_a_member_or_an_external_name_never_both(self):
        pid = self._project()
        r = self.osc.post("/v1/responsibility/assignments", {
            "scope": "project", "subject_id": pid, "role_code": "technical_lead",
            "mandate_basis": BASIS, "user_id": self.osc.user["id"],
            "external_name": "Maria Consultora"})
        self.assertEqual(r.json["code"], "person_required", r)

    def test_a_person_from_another_organization_cannot_be_designated_as_a_member(self):
        pid = self._project()
        r = self.osc.post("/v1/responsibility/assignments", {
            "scope": "project", "subject_id": pid, "role_code": "technical_lead",
            "mandate_basis": BASIS, "user_id": self.other.user["id"]})
        self.assertEqual(r.json["code"], "not_a_member", r)

    def test_an_external_person_is_registered_by_name_without_a_document_number(self):
        pid = self._project()
        r = self._assign(pid, "technical_lead", external="Joana Avaliadora Externa")
        self.assertEqual(r.status, 201, r)
        atual = self.osc.get(f"/v1/responsibility/current?scope=project&subject_id={pid}").json
        quem = next(i for i in atual["items"] if i["role_code"] == "technical_lead")
        self.assertEqual(quem["who"], "Joana Avaliadora Externa")
        self.assertEqual(quem["kind"], "external_person")
        with app_tx(self.osc, readonly=True) as c:
            cols = [x["column_name"] for x in c.query(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_name = 'responsibility_assignments'")]
        for proibido in ("cpf", "document_number", "rg", "tax_id"):
            self.assertNotIn(proibido, cols)

    def test_designating_someone_elses_project_is_refused(self):
        pid = self._project()
        r = self.other.post("/v1/responsibility/assignments", {
            "scope": "project", "subject_id": pid, "role_code": "technical_lead",
            "mandate_basis": BASIS, "external_name": "Alguém de fora"})
        self.assertEqual(r.status, 404, r)

    def test_an_assignment_is_never_rewritten(self):
        pid = self._project()
        aid = self._assign(pid).json["id"]
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception) as ctx:
                c.run("UPDATE responsibility_assignments SET user_id = NULL,"
                      " external_name = 'Outra pessoa' WHERE id = $1", aid)
        self.assertIn("não é reescrita", str(ctx.exception))

    def test_ending_requires_a_reason_and_keeps_the_period_readable(self):
        pid = self._project()
        aid = self._assign(pid).json["id"]
        r = self.osc.post(f"/v1/responsibility/assignments/{aid}/end", {
            "reason": "Encerrada por fim do contrato da coordenadora, conforme ata de abril."})
        self.assertEqual(r.status, 200, r)
        hist = self.osc.get(f"/v1/responsibility/history?scope=project&subject_id={pid}").json
        linha = next(i for i in hist["items"] if i["id"] == aid)
        self.assertTrue(linha["ended_on"])
        self.assertIn("fim do contrato", linha["ended_reason"])
        # e o papel volta a aparecer como SEM responsável
        atual = self.osc.get(f"/v1/responsibility/current?scope=project&subject_id={pid}").json
        self.assertIn("project_coordinator", [x["code"] for x in atual["without_responsible"]])

    def test_an_ended_assignment_does_not_change_its_end_date(self):
        pid = self._project()
        aid = self._assign(pid).json["id"]
        self.osc.post(f"/v1/responsibility/assignments/{aid}/end",
                      {"reason": "Encerrada para o teste de imutabilidade do encerramento."})
        oc = owner_conn()
        with self.assertRaises(Exception) as ctx:
            oc.run("UPDATE responsibility_assignments SET ended_on = current_date + 30"
                   " WHERE id = $1", aid)
        self.assertIn("já encerrada", str(ctx.exception))

    def test_after_ending_the_role_can_be_assigned_to_someone_else(self):
        pid = self._project()
        aid = self._assign(pid).json["id"]
        self.osc.post(f"/v1/responsibility/assignments/{aid}/end",
                      {"reason": "Encerrada para designar outra pessoa, conforme ata."})
        r = self._assign(pid, external="Nova Coordenadora")
        self.assertEqual(r.status, 201, r)

    def test_roles_without_a_responsible_are_shown_as_information(self):
        pid = self._project()
        atual = self.osc.get(f"/v1/responsibility/current?scope=project&subject_id={pid}").json
        self.assertEqual(atual["items"], [])
        self.assertTrue(atual["without_responsible"])
        self.assertIn("ausência de responsável é informação", atual["note"])


# ================================================================================================ decisão
class DecisionTests(RespBase):
    def _ready(self, role: str = "project_coordinator"):
        pid = self._project()
        aid = self._assign(pid, role).json["id"]
        return pid, aid

    def test_a_decision_is_recorded_with_role_person_and_date(self):
        pid, aid = self._ready()
        r = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": aid, "kind": "approval",
            "statement": "Aprovo o plano de trabalho revisado na reunião de equipe desta semana."})
        self.assertEqual(r.status, 201, r)
        self.assertFalse(r.json["signed"])
        lista = self.osc.get(
            f"/v1/responsibility/decisions?scope=project&subject_id={pid}").json["items"]
        self.assertEqual(lista[0]["role_code"], "project_coordinator")
        self.assertTrue(lista[0]["who"])
        self.assertFalse(lista[0]["signed"])

    def test_a_decision_outside_the_assignment_period_is_refused(self):
        pid = self._project()
        amanha = (date.today() + timedelta(days=5)).isoformat()
        aid = self._assign(pid, starts_on=amanha).json["id"]
        r = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": aid, "kind": "approval", "statement": LONG,
            "taken_on": date.today().isoformat()})
        self.assertEqual(r.status, 422, r)
        self.assertIn("fora do período", r.json["title"])

    def test_a_decision_that_requires_four_eyes_is_refused_alone(self):
        pid, aid = self._ready()
        r = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": aid, "kind": "authorization_to_publish", "statement": LONG})
        self.assertEqual(r.status, 422, r)
        self.assertIn("quatro-olhos", r.json["title"])

    def test_four_eyes_refuses_the_same_person_in_both_roles(self):
        pid = self._project()
        a1 = self._assign(pid, "project_coordinator").json["id"]
        a2 = self._assign(pid, "technical_lead").json["id"]  # mesma pessoa, outro papel
        r = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": a1, "kind": "acceptance_of_risk", "statement": LONG,
            "second_assignment_id": a2, "second_statement": LONG})
        self.assertEqual(r.status, 422, r)
        self.assertIn("PESSOAS diferentes", r.json["title"])

    def test_four_eyes_accepts_two_different_people(self):
        pid = self._project()
        a1 = self._assign(pid, "project_coordinator").json["id"]
        a2 = self._assign(pid, "technical_lead", external="Joana Avaliadora").json["id"]
        r = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": a1, "kind": "authorization_to_publish",
            "statement": "Autorizo a publicação do relatório anual na página pública da "
                         "organização.",
            "second_assignment_id": a2,
            "second_statement": "Confirmo a autorização: os números do relatório correspondem às "
                                "medições validadas."})
        self.assertEqual(r.status, 201, r)
        item = self.osc.get(
            f"/v1/responsibility/decisions?scope=project&subject_id={pid}").json["items"][0]
        self.assertEqual(item["second_who"], "Joana Avaliadora")
        self.assertTrue(item["requires_two"])

    def test_a_decision_about_a_document_points_at_a_version(self):
        pid, aid = self._ready()
        oc = owner_conn()
        doc = oc.scalar(
            "INSERT INTO documents(org_id, doc_type, title, filename, mime_type, size_bytes,"
            " sha256, storage_key, status, version) VALUES ($1,'relatorio','Relatório anual',"
            " 'rel.pdf','application/pdf',2048, repeat('b',64), 'k/' || gen_random_uuid()::text,"
            " 'clean', 3) RETURNING id", self.osc.org_id)
        ok = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": aid, "kind": "approval", "statement": LONG,
            "document_id": doc, "document_version": 3})
        self.assertEqual(ok.status, 201, ok)
        errada = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": aid, "kind": "technical_opinion", "statement": LONG,
            "document_id": doc, "document_version": 2})
        self.assertEqual(errada.status, 422, errada)
        self.assertIn("é sobre uma VERSÃO", errada.json["title"])

    def test_a_document_of_another_organization_cannot_be_decided_upon(self):
        pid, aid = self._ready()
        oc = owner_conn()
        alheio = oc.scalar(
            "INSERT INTO documents(org_id, doc_type, title, filename, mime_type, size_bytes,"
            " sha256, storage_key, status) VALUES ($1,'relatorio','Relatório de outra org',"
            " 'rel.pdf','application/pdf',2048, repeat('c',64), 'k/' || gen_random_uuid()::text,"
            " 'clean') RETURNING id", self.other.org_id)
        r = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": aid, "kind": "approval", "statement": LONG, "document_id": alheio})
        self.assertEqual(r.status, 422, r)
        self.assertIn("não é da organização", r.json["title"])

    def test_the_decision_trail_is_append_only(self):
        pid, aid = self._ready()
        self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": aid, "kind": "approval", "statement": LONG})
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception):
                c.run("UPDATE responsibility_decisions SET statement = 'outro' WHERE"
                      " assignment_id = $1", aid)

    def test_a_decision_exists_without_a_signature_and_says_so(self):
        """A separação, verificada: decisão sem assinatura é registro válido de responsabilidade."""
        pid, aid = self._ready()
        r = self.osc.post("/v1/responsibility/decisions", {
            "assignment_id": aid, "kind": "technical_opinion", "statement": LONG})
        self.assertEqual(r.status, 201, r)
        self.assertFalse(r.json["signed"])
        self.assertIn("NÃO é assinatura", r.json["separation"])


# ================================================================================================ isolamento
class IsolationTests(RespBase):
    def test_another_organization_does_not_read_the_assignment_history(self):
        pid = self._project()
        self._assign(pid)
        self.assertEqual(self.other.get(
            f"/v1/responsibility/history?scope=project&subject_id={pid}").json["items"], [])

    def test_mine_lists_only_my_own_assignments(self):
        pid = self._project()
        aid = self._assign(pid).json["id"]
        meus = self.osc.get("/v1/responsibility/mine").json["items"]
        self.assertIn(aid, [m["id"] for m in meus])
        self.assertEqual([m for m in self.other.get("/v1/responsibility/mine").json["items"]
                          if m["id"] == aid], [])
