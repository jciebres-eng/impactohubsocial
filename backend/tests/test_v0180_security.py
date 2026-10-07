"""v0.18.0 — segurança, isolamento, LGPD, viés e gaming das tabelas novas (FASE 10).

Este arquivo não testa funcionalidade. Testa que a camada de impacto contextualizado obedece às
mesmas regras do resto do sistema, e mais duas coisas que só esta rodada pede:

* **viés**: a plataforma não pode penalizar projeto pequeno, território remoto nem organização nova;
* **gaming**: nenhum atalho barato pode melhorar reputação, selo ou integridade de alegação.

Tabela nova sem RLS, sem política ou que vaza entre organizações é o defeito que não aparece em
nenhum teste de produto — e é o pior deles.
"""
from __future__ import annotations

import unittest

from tests.support import app_tx, db_system, grant_premium, make_admin, new_account, owner_conn

#: Toda tabela criada nas migrações 0025–0031.
NEW_TABLES = [
    # 0025 equidade
    "equity_barrier_catalog", "project_barriers", "equity_denominators", "equity_contexts",
    "equity_assessments",
    # 0026 território
    "territories", "determinant_indicator_defs", "territory_indicators",
    # 0027 referenciais e materialidade
    "impact_frameworks", "framework_mappings", "materiality_topics", "materiality_assessments",
    "materiality_entries",
    # 0028 alegações
    "claim_rules", "claims", "claim_checks", "claim_review_requests", "claim_reviews",
    # 0029 reputação
    "reputation_dimensions", "reputation_snapshots", "reputation_disputes",
    "reputation_dispute_resolutions",
    # 0030 selos
    "seal_rules", "seal_definitions", "seal_criteria", "seal_awards", "seal_revocations",
    "seal_evaluations",
    # 0031 responsabilidade
    "responsibility_roles", "responsibility_decision_kinds", "responsibility_assignments",
    "responsibility_decisions",
]

#: Tabelas cuja leitura é ABERTA de propósito, com o motivo. Toda outra tabela nova precisa de
#: política que recorte por organização — e o teste de vazamento confere isso.
OPEN_ON_PURPOSE = {
    "equity_barrier_catalog": "catálogo editorial: quem é classificado lê o critério",
    "territories": "território é bem comum",
    "determinant_indicator_defs": "definição de indicador de determinante é bem comum",
    "territory_indicators": "indicador territorial é bem comum",
    "impact_frameworks": "registro de referenciais, com o que a plataforma NÃO mapeia",
    "materiality_topics": "catálogo editorial",
    "claim_rules": "quem é marcado tem direito de ler a regra e o léxico",
    "reputation_dimensions": "quem é avaliado tem direito de ler o critério",
    "reputation_snapshots": "reputação que ninguém pode ler não serve para nada",
    "reputation_disputes": "contestação invisível não é direito, é formulário",
    "reputation_dispute_resolutions": "a resposta à contestação é pública como a contestação",
    "seal_rules": "critério de selo é público",
    "seal_definitions": "inclui rascunho: ninguém é surpreendido por critério novo",
    "seal_criteria": "idem",
    "seal_awards": "concessão pública é o ponto do selo",
    "seal_revocations": "revogação precisa ser tão visível quanto a concessão",
    "responsibility_roles": "catálogo editorial",
    "responsibility_decision_kinds": "catálogo editorial",
    "framework_mappings": "mapeamento declarado é informação de relatório",
}

#: Em que o app NÃO TEM SEQUER a permissão de INSERT — a escrita passa por função SECURITY DEFINER
#: ou por migração.
APP_CANNOT_INSERT = {
    "reputation_snapshots": "só app_record_reputation(), que recusa valor sem observação",
    "seal_awards": "só app_award_seal(), que reavalia o critério no banco",
    "seal_evaluations": "a avaliação é gravada pela função de concessão",
    "equity_barrier_catalog": "catálogo editorial, entra por migração",
    "claim_rules": "regra determinística entra por migração",
    "reputation_dimensions": "dimensão entra por migração",
    "seal_rules": "critério de selo exige migração",
    "materiality_topics": "catálogo editorial, entra por migração",
    "impact_frameworks": "registro entra por migração",
    "responsibility_roles": "catálogo editorial, entra por migração",
    "responsibility_decision_kinds": "catálogo editorial, entra por migração",
}

#: Em que o app TEM permissão de INSERT, mas a POLÍTICA exige contexto privilegiado. É o padrão da
#: v0.17.0 (`APP_NEEDS_PRIV`): a permissão existe porque o caminho administrativo passa pelo mesmo
#: papel de banco, e quem recorta é a política — que é o que o teste confere.
APP_NEEDS_PRIV = {
    "territories": "catálogo territorial entra por importador com fonte declarada",
    "determinant_indicator_defs": "definição de indicador de determinante é editorial",
    "territory_indicators": "indicador territorial entra por importador com fonte",
    "seal_definitions": "definição de selo é ato da plataforma",
    "seal_criteria": "critério de definição é ato da plataforma",
    "seal_revocations": "revogação é ato da plataforma",
    "reputation_dispute_resolutions": "ninguém resolve a própria contestação",
}

#: Trilhas em que nem UPDATE nem DELETE existem para o app.
APPEND_ONLY = ["claim_checks", "claim_reviews", "equity_assessments", "reputation_snapshots",
               "reputation_disputes", "reputation_dispute_resolutions", "seal_awards",
               "seal_revocations", "seal_evaluations", "responsibility_decisions"]


class CatalogTests(unittest.TestCase):
    """Lido do catálogo do PostgreSQL: é o estado real do banco, não o que o código pretende."""

    @classmethod
    def setUpClass(cls):
        with db_system() as c:
            cls.rls = {r["relname"]: r["relrowsecurity"] for r in c.query(
                "SELECT relname, relrowsecurity FROM pg_class WHERE relname = ANY($1)"
                "   AND relkind = 'r'", NEW_TABLES)}
            cls.policies = {r["tablename"]: r["n"] for r in c.query(
                "SELECT tablename, count(*) AS n FROM pg_policies WHERE tablename = ANY($1)"
                " GROUP BY tablename", NEW_TABLES)}
            cls.grants = {}
            for row in c.query(
                    "SELECT table_name, string_agg(DISTINCT privilege_type, ',') AS p"
                    " FROM information_schema.table_privileges"
                    " WHERE table_name = ANY($1) AND grantee = 'impacto_app' GROUP BY table_name",
                    NEW_TABLES):
                cls.grants[row["table_name"]] = set((row["p"] or "").split(","))

    def test_every_declared_table_exists(self):
        self.assertEqual(set(self.rls), set(NEW_TABLES),
                         "tabela declarada nesta lista e ausente do banco (ou o contrário)")

    def test_every_new_table_has_row_level_security(self):
        off = [t for t, on in self.rls.items() if not on]
        self.assertEqual(off, [], f"tabela nova sem RLS: {off}")

    def test_every_new_table_has_at_least_one_policy(self):
        """RLS ligada e sem política nega tudo: parece seguro e quebra o produto em silêncio."""
        missing = [t for t in NEW_TABLES if self.policies.get(t, 0) == 0]
        self.assertEqual(missing, [], f"RLS ligada sem política: {missing}")

    def test_the_tables_the_app_must_not_write_have_no_insert_grant(self):
        for table, why in APP_CANNOT_INSERT.items():
            self.assertNotIn("INSERT", self.grants.get(table, set()),
                             f"{table} recebeu INSERT: {why}")

    def test_the_privileged_tables_are_recortadas_pela_politica_e_nao_pelo_grant(self):
        """Onde o INSERT existe, a política tem de exigir contexto privilegiado.

        Conferir só o grant daria falso conforto: é a política que decide, e é ela que alguém pode
        afrouxar sem perceber.
        """
        with db_system() as c:
            checks = {}
            for r in c.query(
                    "SELECT tablename, string_agg(coalesce(with_check, qual), ' | ') AS c"
                    " FROM pg_policies WHERE tablename = ANY($1) AND cmd IN ('INSERT','ALL')"
                    " GROUP BY tablename", list(APP_NEEDS_PRIV)):
                checks[r["tablename"]] = r["c"] or ""
        for table, why in APP_NEEDS_PRIV.items():
            self.assertIn("app_priv", checks.get(table, ""),
                          f"{table} aceita escrita sem contexto privilegiado: {why}")

    def test_the_append_only_trails_have_neither_update_nor_delete(self):
        for table in APPEND_ONLY:
            privs = self.grants.get(table, set())
            self.assertNotIn("UPDATE", privs, f"{table} virou editável")
            self.assertNotIn("DELETE", privs, f"{table} virou apagável")

    def test_no_new_column_holds_personal_data_without_a_declared_reason(self):
        """Varredura por PALAVRA do nome da coluna; exceções declaradas uma a uma.

        A varredura por substring (primeira versão, na v0.17.0) acusava `subscription_id` por conter
        "ip". Varredura que grita com nome inocente é varredura que alguém desliga.
        """
        allowed = {
            ("claims", "statement"): "o texto da alegação é o objeto do módulo",
            ("responsibility_assignments", "external_name"): "nome da pessoa externa, SEM "
                                                             "documento: é o mínimo para registrar "
                                                             "quem respondeu",
            ("responsibility_assignments", "external_note"): "como a pessoa se relaciona com a "
                                                             "organização, em texto livre",
            ("territories", "name"): "nome de território",
            ("territories", "source_name"): "fonte do dado territorial",
            ("equity_denominators", "source_name"): "fonte do denominador",
            ("territory_indicators", "source_name"): "fonte do indicador territorial",
            ("framework_mappings", "source_name"): "fonte do mapeamento",
            ("framework_mappings", "external_name"): "nome do código no referencial externo",
            ("equity_contexts", "need_source_name"): "fonte da necessidade declarada",
        }
        # "name" ficou FORA da lista: `name_pt`, `source_name` e `role_name` são nomes de coisas,
        # não de pessoas, e incluí-los faria a varredura acusar meia dúzia de colunas inocentes.
        # O nome de PESSOA é tratado no teste seguinte, que o procura explicitamente.
        suspicious = {"cpf", "email", "mail", "phone", "telefone", "password", "senha",
                      "token", "card", "cartao", "cvv", "agent", "secret", "birth",
                      "nascimento", "address", "endereco"}
        with db_system() as c:
            cols = c.query("SELECT table_name, column_name FROM information_schema.columns"
                           " WHERE table_name = ANY($1)", NEW_TABLES)
        found = []
        for row in cols:
            words = set(row["column_name"].split("_"))
            if words & suspicious and (row["table_name"], row["column_name"]) not in allowed:
                found.append(f"{row['table_name']}.{row['column_name']}")
        self.assertEqual(found, [],
                         f"coluna nova com cara de dado pessoal e sem justificativa: {found}")

    def test_no_new_table_stores_a_national_id_number(self):
        """A regra mais simples e a mais importante: CPF não entra nesta camada.

        O casamento é por PALAVRA: `LIKE '%rg%'` acusava `org_id`, que é o oposto de dado pessoal.
        """
        with db_system() as c:
            cols = c.query(
                "SELECT table_name, column_name FROM information_schema.columns"
                " WHERE table_name = ANY($1)"
                "   AND (string_to_array(column_name, '_') && ARRAY['cpf','rg','cnh','pis',"
                "        'titulo','passaporte'] OR column_name IN ('tax_id','document_number',"
                "        'national_id','ssn'))", NEW_TABLES)
        self.assertEqual(cols, [])

    def test_the_only_person_name_column_is_the_declared_external_one(self):
        """Nome de PESSOA nesta camada existe em um lugar só, e sem documento ao lado."""
        with db_system() as c:
            cols = [f"{r['table_name']}.{r['column_name']}" for r in c.query(
                "SELECT table_name, column_name FROM information_schema.columns"
                " WHERE table_name = ANY($1)"
                "   AND (column_name LIKE '%full_name%' OR column_name LIKE '%person%'"
                "        OR column_name LIKE '%holder%' OR column_name = 'external_name')",
                NEW_TABLES)]
        # `framework_mappings.external_name` é o nome do código no referencial externo (GRI 403-9,
        # por exemplo) e `materiality_*` não guarda pessoa: ambos são nomes de COISA. A única coluna
        # de nome de pessoa é a da designação externa, e ela não tem documento ao lado.
        # `materiality_entries.stakeholder_note` casa por conter "stakeholder"/"person"? Não: casa
        # pelo padrão `%person%`... não casa. Casa por `%holder%` dentro de "stakeholder" — nome de
        # GRUPO de interesse, nunca de pessoa, e o CHECK da coluna limita a 2.000 caracteres de
        # texto sobre consulta a público, não sobre indivíduo.
        esperado = {"responsibility_assignments.external_name", "framework_mappings.external_name",
                    "materiality_entries.stakeholder_note"}
        self.assertEqual(set(cols) - esperado, set(), f"nome de pessoa não declarado: {cols}")
        self.assertIn("responsibility_assignments.external_name", cols)


class IsolationTests(unittest.TestCase):
    """Uma organização cria de tudo; a outra não vê nada — exceto o que é aberto de propósito."""

    @classmethod
    def setUpClass(cls):
        cls.a = new_account("osc", compliance="approved")
        cls.b = new_account("osc", compliance="approved")
        cls.admin, _ = make_admin()
        grant_premium(cls.a)
        p = cls.a.post("/v1/projects", {
            "title": "Projeto do teste de isolamento da v0.18.0",
            "summary": "Projeto criado para povoar as tabelas novas e provar o isolamento.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 80, "budget_total_cents": 2_000_000})
        assert p.status == 201, p
        cls.project = p.json["id"]
        cls.a.put(f"/v1/projects/{cls.project}/equity/context", {
            "need_statement": "A comunidade atendida não tem oferta pública de reforço escolar no "
                              "contraturno, conforme levantamento da secretaria.",
            "additionality": "Nenhuma outra organização atua no contraturno desta comunidade."})
        cls.a.post("/v1/equity/denominators", {
            "project_id": cls.project, "kind": "eligible_population", "value": 200,
            "unit": "pessoas", "reference_date": "2025-01-01",
            "source_name": "Censo escolar municipal 2024", "source_date": "2025-03-01",
            "method_note": "Matriculados na faixa atendida, conforme censo escolar municipal."})
        c = cls.a.post("/v1/claims", {
            "subject_type": "project", "subject_id": cls.project, "claim_kind": "result",
            "statement": "Atendemos oitenta pessoas em oficinas de leitura no semestre."})
        assert c.status == 201, c
        cls.claim = c.json["id"]
        cls.a.post(f"/v1/claims/{cls.claim}/check", {})
        cls.a.post("/v1/reputation/snapshots", {})
        cls.a.post("/v1/responsibility/assignments", {
            "scope": "project", "subject_id": cls.project, "role_code": "project_coordinator",
            "mandate_basis": "Designação registrada em ata da diretoria, item 4.",
            "user_id": cls.a.user["id"]})

    def test_the_scenario_actually_wrote_rows(self):
        """Isolamento que passa porque não há dado é isolamento que não foi testado."""
        vazias = []
        with app_tx(self.a, readonly=True) as conn:
            for table in ("equity_contexts", "equity_denominators", "claims", "claim_checks",
                          "reputation_snapshots", "responsibility_assignments"):
                if conn.scalar(f"SELECT count(*) FROM {table}") == 0:   # noqa: S608
                    vazias.append(table)
        self.assertEqual(vazias, [], f"o cenário não escreveu nada em {vazias}")

    def test_the_other_organization_reads_none_of_my_org_scoped_rows(self):
        """Cada tabela leva só o parâmetro que o WHERE dela usa: o driver recusa sobra."""
        escopo = [
            ("equity_contexts", "project_id = $1", "project"),
            ("equity_denominators", "project_id = $1", "project"),
            ("equity_assessments", "project_id = $1", "project"),
            ("project_barriers", "project_id = $1", "project"),
            ("claims", "subject_id = $1", "project"),
            ("claim_checks", "claim_id = $1", "claim"),
            ("responsibility_assignments", "subject_id = $1", "project"),
            ("materiality_assessments", "org_id = $1", "org"),
            ("seal_evaluations", "org_id = $1", "org"),
        ]
        valor = {"project": self.project, "claim": self.claim, "org": self.a.org_id}
        vazou = []
        with app_tx(self.b, readonly=True) as conn:
            for table, where, qual in escopo:
                n = conn.scalar(f"SELECT count(*) FROM {table} WHERE {where}",   # noqa: S608
                                valor[qual])
                if n:
                    vazou.append(f"{table} ({n})")
        self.assertEqual(vazou, [], f"vazamento entre organizações: {vazou}")

    def test_the_claim_of_another_organization_is_not_even_found(self):
        self.assertEqual(self.b.get(f"/v1/claims/{self.claim}").status, 404)
        self.assertEqual(self.b.get(
            f"/v1/responsibility/history?scope=project&subject_id={self.project}"
        ).json["items"], [])

    def test_what_is_open_is_open_on_purpose_and_declared(self):
        """Toda tabela de leitura aberta tem motivo escrito nesta lista — é o inventário."""
        with db_system() as c:
            abertas = {r["tablename"] for r in c.query(
                "SELECT DISTINCT tablename FROM pg_policies WHERE tablename = ANY($1)"
                "   AND cmd = 'SELECT' AND qual = 'true'", NEW_TABLES)}
        sem_motivo = sorted(abertas - set(OPEN_ON_PURPOSE))
        self.assertEqual(sem_motivo, [],
                         f"leitura aberta sem motivo declarado neste arquivo: {sem_motivo}")


class GamingTests(unittest.TestCase):
    """Atalhos baratos que não podem melhorar nada."""

    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        cls.other = new_account("osc", compliance="approved")
        cls.admin, _ = make_admin()
        grant_premium(cls.osc)

    def _project(self, title="Projeto de gaming") -> str:
        r = self.osc.post("/v1/projects", {
            "title": title,
            "summary": "Projeto criado para exercitar os testes de gaming da v0.18.0.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 50, "budget_total_cents": 1_000_000})
        self.assertEqual(r.status, 201, r)
        return r.json["id"]

    def test_declaring_many_unchecked_claims_does_not_improve_claim_integrity(self):
        osc = new_account("osc", compliance="approved")
        pid = osc.post("/v1/projects", {
            "title": "Projeto com muitas alegações sem verificação",
            "summary": "Projeto criado para provar que alegação não verificada não conta.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": "BR-MT-5105259", "causes": ["educacao"],
            "beneficiaries_count": 50, "budget_total_cents": 1_000_000}).json["id"]
        for i in range(5):
            osc.post("/v1/claims", {
                "subject_type": "project", "subject_id": pid, "claim_kind": "result",
                "statement": f"Alegação número {i} declarada e nunca verificada por ninguém."})
        d = next(x for x in osc.get("/v1/reputation/me").json["dimensions"]
                 if x["dimension"] == "claim_integrity")
        self.assertEqual(d["observations"], 0, "alegação não verificada não é observação")
        self.assertIsNone(d["value"])

    def test_withdrawing_a_flagged_claim_does_not_clean_the_record(self):
        """Retirar a alegação marcada não melhora a dimensão: sai do numerador E do denominador."""
        pid = self._project("Projeto com alegação marcada e retirada")
        cid = self.osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": pid, "claim_kind": "result",
            "statement": "O resultado é comprovado e garantido em toda a área atendida."}).json["id"]
        out = self.osc.post(f"/v1/claims/{cid}/check", {}).json
        self.assertEqual(out["status"], "flagged")
        antes = next(x for x in self.osc.get("/v1/reputation/me").json["dimensions"]
                     if x["dimension"] == "claim_integrity")
        self.osc.post(f"/v1/claims/{cid}/withdraw", {
            "reason": "Retirada depois de ser marcada pelo verificador determinístico."})
        depois = next(x for x in self.osc.get("/v1/reputation/me").json["dimensions"]
                      if x["dimension"] == "claim_integrity")
        self.assertLessEqual(depois["observations"], antes["observations"])
        if depois["value"] is not None and antes["value"] is not None:
            self.assertLessEqual(depois["value"], 100.0)
        # e o histórico da alegação retirada continua legível
        self.assertEqual(self.osc.get(f"/v1/claims/{cid}").json["status"], "withdrawn")

    def test_an_organization_cannot_validate_its_own_measurement(self):
        """Trava de v0.8.0 reafirmada aqui porque a reputação depende dela."""
        oc = owner_conn()
        pid = self._project("Projeto com autovalidação tentada")
        cat = self.osc.get("/v1/indicators/catalog?ods=4").json["items"]
        ind = next(i for i in cat if i["code"] == "trained_people")
        pi = self.osc.post(f"/v1/projects/{pid}/indicators", {
            "indicator_id": ind["id"], "baseline": 0,
            "baseline_source": "Lista de presença do primeiro encontro", "target": 50}).json["id"]
        with self.assertRaises(Exception):
            oc.run("INSERT INTO indicator_values(project_indicator_id, project_id, org_id, value,"
                   " measured_on, status, validated_by, validated_by_org)"
                   " VALUES ($1,$2,$3,10,current_date,'validated',"
                   " (SELECT id FROM users LIMIT 1), $3)", pi, pid, self.osc.org_id)

    def test_a_reviewer_cannot_review_a_claim_without_being_invited(self):
        pid = self._project("Projeto com revisão não convidada")
        cid = self.osc.post("/v1/claims", {
            "subject_type": "project", "subject_id": pid, "claim_kind": "result",
            "statement": "O resultado é comprovado e garantido, para testar revisão sem convite."
        }).json["id"]
        self.osc.post(f"/v1/claims/{cid}/check", {})
        r = self.other.post(f"/v1/claims/{cid}/review", {
            "decision": "accepted",
            "note": "Revisão não solicitada, que o banco precisa recusar nesta rodada."})
        self.assertEqual(r.json["code"], "not_invited", r)

    def test_a_seal_cannot_be_awarded_by_the_organization_itself(self):
        d = self.admin.post("/v1/admin/seals/definitions", {
            "code": "selo_gaming_teste", "scope": "organization", "title": "Selo do teste de gaming",
            "what_it_attests": "Atesta compliance aprovado, apenas para este teste de gaming.",
            "what_it_does_not_attest": "Não atesta qualidade, impacto nem elegibilidade em edital.",
            "validity_days": 90, "criteria": [{"rule_code": "compliance_approved"}]}).json["id"]
        self.admin.post(f"/v1/admin/seals/definitions/{d}/publish", {})
        r = self.osc.post("/v1/admin/seals/awards",
                          {"definition_id": d, "subject_id": self.osc.org_id})
        self.assertIn(r.status, (403, 404), r)

    def test_a_denominator_cannot_be_declared_without_source_and_method(self):
        pid = self._project("Projeto com denominador sem fonte")
        r = self.osc.post("/v1/equity/denominators", {
            "project_id": pid, "kind": "eligible_population", "value": 1, "unit": "pessoas",
            "reference_date": "2025-01-01", "source_date": "2026-01-01",
            "method_note": "Método declarado com extensão suficiente para o CHECK."})
        self.assertEqual(r.status, 422, r)

    def test_a_tiny_denominator_does_not_manufacture_a_hundred_percent_verdict(self):
        """Denominador de 1 pessoa dá 100%, e é por isso que `compare()` nunca dá veredito."""
        pid = self._project("Projeto com denominador mínimo")
        self.osc.post("/v1/equity/denominators", {
            "project_id": pid, "kind": "eligible_population", "value": 1, "unit": "pessoas",
            "reference_date": "2025-01-01", "source_name": "Declaração da própria organização",
            "source_date": "2026-01-01",
            "method_note": "Denominador mínimo declarado para exercitar o teste de gaming."})
        norm = self.osc.get(f"/v1/projects/{pid}/equity/normalization").json
        self.assertTrue(norm["available"])
        outro = self._project("Projeto para comparar com o denominador mínimo")
        cmp_ = self.osc.post("/v1/equity/compare", {"project_ids": [pid, outro]})
        self.assertEqual(cmp_.status, 200, cmp_)
        self.assertIsNone(cmp_.json["verdict"])
        self.assertFalse(cmp_.json["comparable"])


class BiasTests(unittest.TestCase):
    """A tese da rodada, testada: impacto não é quantidade, e ausência de base não é nota baixa."""

    @classmethod
    def setUpClass(cls):
        cls.osc = new_account("osc", compliance="approved")
        grant_premium(cls.osc)

    def _project(self, title: str, territory: str, beneficiaries: int) -> str:
        return self.osc.post("/v1/projects", {
            "title": title,
            "summary": "Projeto criado para o teste de viés da v0.18.0, com território próprio.",
            "problem": "O problema declarado pelo projeto, com extensão suficiente para o CHECK.",
            "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
            "territory": territory, "causes": ["educacao"],
            "beneficiaries_count": beneficiaries, "budget_total_cents": 1_000_000}).json["id"]

    def test_a_small_remote_project_is_never_ranked_below_a_large_urban_one(self):
        pequeno = self._project("Projeto em comunidade remota", "BR-AC-1200013", 50)
        grande = self._project("Projeto em centro urbano", "BR-SP-3550308", 5000)
        for pid, pop in ((pequeno, 60), (grande, 400000)):
            self.osc.post("/v1/equity/denominators", {
                "project_id": pid, "kind": "eligible_population", "value": pop,
                "unit": "pessoas", "reference_date": "2025-01-01",
                "source_name": "Estimativa declarada para o teste de viés",
                "source_date": "2026-01-01",
                "method_note": "Denominador declarado com fonte, data e método, como a regra exige."})
        r = self.osc.post("/v1/equity/compare", {"project_ids": [pequeno, grande]})
        self.assertEqual(r.status, 200, r)
        self.assertIsNone(r.json["verdict"], "comparação não devolve veredito, nunca")
        self.assertFalse(r.json["comparable"])
        self.assertTrue(r.json["reasons"])

    def test_reputation_is_proportional_and_not_a_proxy_for_size(self):
        """Três medições de três pontuam MAIS que trinta de sessenta: é proporção, não volume."""
        pequena = new_account("osc", compliance="approved")
        grande = new_account("osc", compliance="approved")
        oc = owner_conn()
        for client, com_evidencia, total in ((pequena, 3, 3), (grande, 30, 60)):
            pid = client.post("/v1/projects", {
                "title": f"Projeto de proporção {total}",
                "summary": "Projeto criado para provar que a reputação é proporção, não volume.",
                "problem": "O problema declarado pelo projeto, com extensão suficiente.",
                "objectives": "Os objetivos declarados pelo projeto, com extensão suficiente.",
                "territory": "BR-MT-5105259", "causes": ["educacao"],
                "beneficiaries_count": 10, "budget_total_cents": 500_000}).json["id"]
            cat = client.get("/v1/indicators/catalog?ods=4").json["items"]
            ind = next(i for i in cat if i["code"] == "trained_people")
            pi = client.post(f"/v1/projects/{pid}/indicators", {
                "indicator_id": ind["id"], "baseline": 0,
                "baseline_source": "Lista de presença do primeiro encontro",
                "target": 100}).json["id"]
            ev = client.post(f"/v1/projects/{pid}/evidences", {
                "kind": "attendance", "title": "Lista de presença"}).json["id"]
            oc.run("UPDATE evidences SET status = 'accepted' WHERE id = $1", ev)
            for i in range(total):
                # v0.23.0 — medição validada EXIGE evidência (`indicator_validated_needs_evidence`).
                # As que não têm evidência entram como REPORTADAS, que é o estado que elas podem
                # ocupar de verdade. A dimensão continua exercitada: `evidence_discipline` é
                # "medições validadas COM evidência sobre medições REPORTADAS", então o
                # denominador conta as duas e a proporção segue diferente entre as organizações.
                tem_evidencia = i < com_evidencia
                oc.run(
                    "INSERT INTO indicator_values(project_indicator_id, project_id, org_id, value,"
                    " measured_on, evidence_id, status, validated_by, validated_by_org)"
                    " SELECT $1,$2,$3,$4,current_date,$5,$7,"
                    "        CASE WHEN $7 = 'validated' THEN (SELECT id FROM users LIMIT 1) END,"
                    "        CASE WHEN $7 = 'validated' THEN $6::uuid END",
                    pi, pid, client.org_id, 10 + i, (ev if tem_evidencia else None),
                    self.osc.org_id, "validated" if tem_evidencia else "reported")
        p = next(d for d in pequena.get("/v1/reputation/me").json["dimensions"]
                 if d["dimension"] == "evidence_discipline")
        g = next(d for d in grande.get("/v1/reputation/me").json["dimensions"]
                 if d["dimension"] == "evidence_discipline")
        self.assertIsNotNone(p["value"])
        self.assertIsNotNone(g["value"])
        self.assertGreater(p["value"], g["value"],
                           "disciplina de evidência virou proxy de tamanho")

    def test_a_territory_without_measured_indicators_is_shown_and_not_hidden(self):
        perfil = self.osc.get("/v1/territories/BR-AC").json
        self.assertTrue(perfil["indicators"])
        nao_medidos = [i for i in perfil["indicators"] if not i["measured"]]
        self.assertTrue(nao_medidos, "território sem dado precisa aparecer como sem dado")
        for i in nao_medidos:
            self.assertIn("measured", i)
            self.assertIsNone(i.get("value"))

    def test_a_new_organization_is_not_penalised_in_any_dimension(self):
        nova = new_account("osc")
        for d in nova.get("/v1/reputation/me").json["dimensions"]:
            self.assertIsNone(d["value"], d["dimension"])
            self.assertEqual(d["band"], "insufficient", d["dimension"])
