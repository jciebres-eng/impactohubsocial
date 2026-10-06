"""v0.18.0 — selos: definição versionada, critério avaliado em SQL, selo nunca comprável.

O teste central deste arquivo é `test_no_path_can_award_a_seal_without_the_criteria`: ele tenta
conceder selo por SQL direto, no papel da aplicação, e falha — porque a aplicação não tem INSERT em
`seal_awards` e a única porta (`app_award_seal()`) reavalia os critérios no banco antes de inserir.

Se algum dia alguém adicionar uma rota de concessão "manual", é este teste que vai reprovar.
"""
from __future__ import annotations

import ast
import pathlib
import unittest
from datetime import date, timedelta

from tests.support import app_tx, db_system, make_admin, new_account, owner_conn

MODULE = pathlib.Path(__file__).resolve().parents[1] / "impacto" / "impact" / "seals.py"
MIGRATION = (pathlib.Path(__file__).resolve().parents[1] / "migrations"
             / "0030_v0180_seals.sql")
ATTESTS = ("Atesta que a organização tem compliance aprovado e documentação básica validada pela "
           "administração da plataforma.")
NOT_ATTESTS = ("NÃO atesta qualidade de projeto, impacto social, elegibilidade em edital nem "
               "aprovação de órgão público.")


class SealBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin, _ = make_admin()
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")

    def _definition(self, *, code: str | None = None, scope: str = "organization",
                    criteria: list[dict] | None = None, publish: bool = True) -> str:
        code = code or f"selo_{date.today().strftime('%d%m')}_{id(self) % 10000}"
        r = self.admin.post("/v1/admin/seals/definitions", {
            "code": code, "scope": scope, "title": "Selo de teste da rodada",
            "what_it_attests": ATTESTS, "what_it_does_not_attest": NOT_ATTESTS,
            "validity_days": 365,
            "criteria": criteria or [{"rule_code": "compliance_approved"}]})
        self.assertEqual(r.status, 201, r)
        did = r.json["id"]
        self.assertEqual(r.json["status"], "draft")
        if publish:
            self.assertEqual(self.admin.post(
                f"/v1/admin/seals/definitions/{did}/publish", {}).status, 200)
        return did


# ================================================================================================ a trava
class ForgeryTests(SealBase):
    def test_no_path_can_award_a_seal_without_the_criteria(self):
        """A trava central: a aplicação não tem INSERT em seal_awards."""
        did = self._definition()
        with app_tx(self.osc) as c:
            with self.assertRaises(Exception):
                c.run("INSERT INTO seal_awards(definition_id, scope, subject_id, org_id, evidence,"
                      " expires_on, engine_version) VALUES ($1,'organization',$2,$2,"
                      " '[{\"rule_code\":\"compliance_approved\",\"met\":true}]'::jsonb,"
                      " current_date + 365, 'mao')", did, self.osc.org_id)

    def test_the_award_function_refuses_when_a_criterion_is_not_met(self):
        did = self._definition(criteria=[{"rule_code": "measurements_with_evidence",
                                          "params": {"min_count": 3}}])
        r = self.admin.post("/v1/admin/seals/awards",
                            {"definition_id": did, "subject_id": self.osc.org_id})
        self.assertEqual(r.status, 422, r)
        self.assertEqual(r.json["code"], "criteria_not_met")
        self.assertIn("measurements_with_evidence", r.json["title"])
        self.assertIn("measurements_with_evidence", r.json["details"]["unmet"])

    def test_even_the_database_owner_goes_through_the_evaluation(self):
        """Nem o dono do banco concede sem critério: a função devolve NULL e não grava concessão.

        Devolver NULL em vez de levantar exceção é deliberado — exceção desfaria a transação e
        levaria embora o registro da avaliação que explica a recusa.
        """
        did = self._definition(criteria=[{"rule_code": "substantiated_claims"}])
        oc = owner_conn()
        self.assertIsNone(oc.scalar("SELECT app_award_seal($1, $2, 'mao')", did, self.osc.org_id))
        self.assertEqual(oc.scalar("SELECT count(*) FROM seal_awards WHERE definition_id = $1",
                                   did), 0)
        self.assertFalse(oc.scalar("SELECT all_met FROM seal_evaluations WHERE definition_id = $1"
                                   " ORDER BY created_at DESC LIMIT 1", did))

    def test_a_draft_definition_awards_nothing(self):
        did = self._definition(publish=False)
        r = self.admin.post("/v1/admin/seals/awards",
                            {"definition_id": did, "subject_id": self.osc.org_id})
        self.assertEqual(r.status, 422, r)
        self.assertIn("PUBLICADA", r.json["title"])
        self.assertEqual(r.json["code"], "seal_not_awardable")

    def test_the_module_and_the_migration_have_no_commercial_signal(self):
        """Selo não é comprável: a varredura é no código, não na promessa."""
        proibidos = ("plan_key", "entitlement", "subscription", "invoice", "billable",
                     "platform_charges", "price_")
        tree = ast.parse(MODULE.read_text(encoding="utf-8"))
        achados = [n.id if isinstance(n, ast.Name) else n.attr
                   for n in ast.walk(tree) if isinstance(n, ast.Name | ast.Attribute)
                   and any(t in (n.id if isinstance(n, ast.Name) else n.attr).lower()
                           for t in proibidos)]
        self.assertEqual(achados, [], f"sinal comercial no motor de selos: {achados}")
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        for termo in proibidos:
            self.assertNotIn(termo, sql, f"sinal comercial na migração de selos: {termo}")

    def test_no_criterion_reads_reputation(self):
        """Encadear selo em nota transformaria a nota naquilo que a FASE 6 recusou ser.

        A varredura é por LEITURA da tabela, não pela palavra: a migração cita
        `reputation_snapshots` num comentário que diz justamente que não a lê.
        """
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        for linha in sql.splitlines():
            if linha.lstrip().startswith("--"):
                continue
            for padrao in ("from reputation", "join reputation", "into reputation",
                           "update reputation", "exists (select 1 from reputation"):
                self.assertNotIn(padrao, linha, f"o selo passou a ler reputação: {linha.strip()}")


# ================================================================================================ definição
class DefinitionTests(SealBase):
    def test_the_platform_ships_zero_seal_definitions(self):
        """Critério de selo é decisão de produto; embarcá-lo numa migração seria inventá-lo."""
        with db_system() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM seal_definitions WHERE id IN"
                                      " (SELECT id FROM seal_definitions WHERE created_at <"
                                      "  (SELECT min(created_at) FROM organizations))"), 0)
        note = self.osc.get("/v1/seals/definitions").json["note"]
        self.assertIn("decisão de produto", note)

    def test_every_definition_declares_what_it_does_not_attest(self):
        self._definition()
        for d in self.osc.get("/v1/seals/definitions").json["items"]:
            self.assertGreaterEqual(len(d["what_it_does_not_attest"]), 20, d["code"])
        self.assertIn("NÃO é certificação", self.osc.get("/v1/seals/definitions").json["disclaimer"])

    def test_a_published_definition_is_immutable(self):
        did = self._definition()
        oc = owner_conn()
        with self.assertRaises(Exception) as ctx:
            oc.run("UPDATE seal_definitions SET validity_days = 1000 WHERE id = $1", did)
        self.assertIn("versão", str(ctx.exception).lower())

    def test_a_criterion_of_a_published_definition_cannot_be_changed(self):
        did = self._definition()
        oc = owner_conn()
        with self.assertRaises(Exception):
            oc.run("DELETE FROM seal_criteria WHERE definition_id = $1", did)

    def test_a_definition_without_criteria_is_refused(self):
        r = self.admin.post("/v1/admin/seals/definitions", {
            "code": "selo_sem_critetio", "scope": "organization", "title": "Selo sem critério",
            "what_it_attests": ATTESTS, "what_it_does_not_attest": NOT_ATTESTS,
            "validity_days": 365, "criteria": []})
        self.assertEqual(r.status, 422, r)

    def test_a_criterion_of_another_scope_is_refused(self):
        r = self.admin.post("/v1/admin/seals/definitions", {
            "code": "selo_escopo_errado", "scope": "organization", "title": "Selo com escopo errado",
            "what_it_attests": ATTESTS, "what_it_does_not_attest": NOT_ATTESTS,
            "validity_days": 365, "criteria": [{"rule_code": "project_completed"}]})
        self.assertEqual(r.json["code"], "scope_mismatch", r)

    def test_publishing_a_new_version_retires_the_previous_one(self):
        code = "selo_versionado_teste"
        v1 = self._definition(code=code)
        v2 = self._definition(code=code, criteria=[{"rule_code": "compliance_approved"},
                                                   {"rule_code": "documents_validated",
                                                    "params": {"doc_types": ["cartao_cnpj"]}}])
        itens = {d["id"]: d for d in self.osc.get(
            f"/v1/seals/definitions?code={code}").json["items"]}
        self.assertEqual(itens[v1]["status"], "retired")
        self.assertEqual(itens[v2]["status"], "published")
        self.assertEqual(itens[v2]["version"], itens[v1]["version"] + 1)


# ================================================================================================ avaliação e concessão
class AwardTests(SealBase):
    def test_the_evaluation_route_shows_the_same_verdict_as_the_award(self):
        did = self._definition()
        ev = self.osc.post("/v1/seals/evaluate",
                           {"definition_id": did, "subject_id": self.osc.org_id})
        self.assertEqual(ev.status, 200, ev)
        self.assertTrue(ev.json["all_met"])
        aw = self.admin.post("/v1/admin/seals/awards",
                             {"definition_id": did, "subject_id": self.osc.org_id})
        self.assertEqual(aw.status, 201, aw)
        self.assertEqual(aw.json["status"], "active")

    def test_the_award_keeps_the_evidence_of_every_criterion(self):
        did = self._definition()
        aw = self.admin.post("/v1/admin/seals/awards",
                             {"definition_id": did, "subject_id": self.osc.org_id}).json
        self.assertTrue(aw["evidence"])
        for item in aw["evidence"]:
            self.assertIn("rule_code", item)
            self.assertTrue(item["met"])
            self.assertGreaterEqual(len(item["detail"]), 5)

    def test_the_award_never_outlives_the_document_that_supports_it(self):
        """Validade = menor entre a da definição e as datas que os critérios impõem."""
        osc = new_account("osc", compliance="approved")
        oc = owner_conn()
        amanha = date.today() + timedelta(days=10)
        oc.run("INSERT INTO documents(org_id, doc_type, title, filename, mime_type, size_bytes,"
               " sha256, storage_key, status, validation_status, validated_by, validated_at,"
               " valid_until) VALUES ($1,'cartao_cnpj','Cartão CNPJ','cnpj.pdf',"
               " 'application/pdf',1024, repeat('a',64), 'k/' || gen_random_uuid()::text,"
               " 'clean','validated',(SELECT id FROM users LIMIT 1), now(), $2)",
               osc.org_id, amanha)
        did = self._definition(code="selo_validade_doc",
                               criteria=[{"rule_code": "documents_validated",
                                          "params": {"doc_types": ["cartao_cnpj"]}}])
        aw = self.admin.post("/v1/admin/seals/awards",
                             {"definition_id": did, "subject_id": osc.org_id})
        self.assertEqual(aw.status, 201, aw)
        self.assertEqual(aw.json["expires_on"], amanha.isoformat())

    def test_an_award_is_append_only(self):
        did = self._definition()
        aw = self.admin.post("/v1/admin/seals/awards",
                             {"definition_id": did, "subject_id": self.osc.org_id}).json
        oc = owner_conn()
        with self.assertRaises(Exception):
            oc.run("UPDATE seal_awards SET expires_on = current_date + 3650 WHERE id = $1",
                   aw["id"])

    def test_the_refused_evaluation_is_recorded_for_whoever_was_refused(self):
        osc = new_account("osc")
        did = self._definition(code="selo_recusa_registrada",
                               criteria=[{"rule_code": "compliance_approved"}])
        self.admin.post("/v1/admin/seals/awards",
                        {"definition_id": did, "subject_id": osc.org_id})
        fila = osc.get("/v1/seals/evaluations").json
        self.assertTrue(fila["items"])
        self.assertFalse(fila["items"][0]["all_met"])
        self.assertIn("por que eu não recebi", fila["note"])


# ================================================================================================ revogação
class RevocationTests(SealBase):
    def _awarded(self, org=None) -> str:
        org = org or self.osc
        did = self._definition(code=f"selo_rev_{id(org) % 100000}")
        return self.admin.post("/v1/admin/seals/awards",
                               {"definition_id": did, "subject_id": org.org_id}).json["id"]

    def test_revoking_is_a_new_fact_and_does_not_erase_the_award(self):
        aid = self._awarded()
        r = self.admin.post(f"/v1/admin/seals/awards/{aid}/revoke", {
            "reason": "data_correction",
            "detail": "O documento usado como critério foi substituído por correção de dado."})
        self.assertEqual(r.status, 201, r)
        got = self.osc.get(f"/v1/seals/awards/{aid}").json
        self.assertEqual(got["status"], "revoked")
        self.assertEqual(got["revocation"]["reason"], "data_correction")
        self.assertTrue(got["awarded_at"], "a concessão continua legível depois de revogada")

    def test_a_seal_is_revoked_once(self):
        aid = self._awarded(self.other)
        self.admin.post(f"/v1/admin/seals/awards/{aid}/revoke", {
            "reason": "request_of_holder", "detail": "A organização pediu a retirada do selo."})
        again = self.admin.post(f"/v1/admin/seals/awards/{aid}/revoke", {
            "reason": "misconduct", "detail": "Segunda tentativa de revogar o mesmo selo."})
        self.assertEqual(again.json["code"], "already_revoked", again)

    def test_a_seal_whose_criterion_fell_is_revoked_by_the_recheck(self):
        osc = new_account("osc", compliance="approved")
        did = self._definition(code="selo_recheck_teste")
        aid = self.admin.post("/v1/admin/seals/awards",
                              {"definition_id": did, "subject_id": osc.org_id}).json["id"]
        self.assertEqual(self.osc.get(f"/v1/seals/awards/{aid}").json["status"], "active")
        oc = owner_conn()
        oc.run("UPDATE organizations SET compliance_status = 'suspended' WHERE id = $1", osc.org_id)
        from impacto.impact import seals as SEAL
        with db_system() as d:
            out = SEAL.recheck(d, org_id=osc.org_id)
        self.assertEqual(out["revoked"], 1, out)
        got = self.osc.get(f"/v1/seals/awards/{aid}").json
        self.assertEqual(got["status"], "revoked")
        self.assertEqual(got["revocation"]["reason"], "criterion_no_longer_met")
        self.assertIn("compliance_approved", got["revocation"]["detail"])

    def test_the_revocation_trail_is_append_only(self):
        aid = self._awarded(new_account("osc", compliance="approved"))
        self.admin.post(f"/v1/admin/seals/awards/{aid}/revoke", {
            "reason": "misconduct", "detail": "Revogação para testar a trilha append-only."})
        oc = owner_conn()
        with self.assertRaises(Exception):
            oc.run("UPDATE seal_revocations SET reason = 'data_correction' WHERE award_id = $1",
                   aid)


# ================================================================================================ projeto
class ProjectScopeTests(SealBase):
    def _project(self, client) -> str:
        return client.post("/v1/projects", {
            "title": "Projeto para selo de escopo de projeto",
            "summary": "Projeto criado para exercitar selo de escopo de projeto na v0.18.0.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5103403", "causes": ["educacao"],
            "beneficiaries_count": 90, "budget_total_cents": 2_000_000}).json["id"]

    def test_a_project_seal_requires_the_equity_context_and_the_sourced_denominator(self):
        pid = self._project(self.osc)
        did = self._definition(code="selo_projeto_equidade", scope="project",
                               criteria=[{"rule_code": "equity_context_declared"}])
        r = self.admin.post("/v1/admin/seals/awards",
                            {"definition_id": did, "subject_id": pid})
        self.assertEqual(r.status, 422, r)
        self.assertIn("contexto de equidade", r.json["title"])

        self.osc.put(f"/v1/projects/{pid}/equity/context", {
            "need_statement": "A comunidade não tem oferta de reforço escolar no contraturno, e a "
                              "escola mais próxima fica a doze quilômetros.",
            "additionality": "Nenhuma outra organização atende o contraturno nesta comunidade, "
                             "conforme levantamento da secretaria municipal."})
        self.osc.post("/v1/equity/denominators", {
            "project_id": pid, "kind": "eligible_population", "value": 180, "unit": "pessoas",
            "reference_date": "2025-01-01", "source_name": "Censo escolar municipal 2024",
            "source_date": "2025-03-01",
            "method_note": "Contagem de matriculados na faixa atendida, conforme censo escolar."})
        ok = self.admin.post("/v1/admin/seals/awards",
                             {"definition_id": did, "subject_id": pid})
        self.assertEqual(ok.status, 201, ok)
        self.assertEqual(ok.json["scope"], "project")
