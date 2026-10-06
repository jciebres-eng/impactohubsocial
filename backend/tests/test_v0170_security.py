"""v0.17.0 — revisão de segurança, isolamento e LGPD das tabelas novas (FASES 11 e 12).

Este arquivo não testa funcionalidade: testa que a camada econômica nova obedece às mesmas regras que
o resto do sistema. Tabela nova sem RLS, sem política ou que vaza entre organizações é o defeito que
não aparece em nenhum teste de produto — e é o pior deles.
"""
from __future__ import annotations

import datetime as dt
import unittest

from tests.support import app_tx, db_system, make_admin, new_account, owner_conn

#: Toda tabela criada nas migrações 0018–0024.
NEW_TABLES = [
    "programs", "program_status_graph", "program_calls", "program_projects", "program_indicators",
    "program_needs", "value_event_types", "value_baselines", "value_events", "ai_price_table",
    "monetization_legal_cards", "monetization_rules", "billable_events", "charge_state_graph",
    "payment_instruments", "platform_charges", "charge_events", "charge_installments",
    "charge_pix", "charge_boleto", "legal_documents", "legal_acceptances",
]

#: Tabela → como achar NESTA tabela as linhas da organização A. O teste de vazamento pergunta por
#: ESSAS linhas a partir da organização B, e não "a tabela está vazia": a primeira versão deste teste
#: exigia contagem zero e falhou na suíte completa, porque outra suíte publica programa com
#: visibilidade de rede — que a política expõe a qualquer autenticado DE PROPÓSITO. Teste que confunde
#: "não é meu" com "não existe" acusa vazamento onde há regra.
ORG_SCOPED = {
    "programs": "owner_org_id = $1",
    "program_calls": "program_id = $1",
    "program_projects": "program_id = $1",
    "program_indicators": "program_id = $1",
    "program_needs": "program_id = $1",
    "value_events": "org_id = $1",
    "billable_events": "org_id = $1",
    "payment_instruments": "org_id = $1",
    "platform_charges": "org_id = $1",
    "charge_events": "charge_id = $1",
    "charge_installments": "charge_id = $1",
}

#: O subconjunto que o cenário desta suíte realmente popula. As demais são povoadas por outras
#: suítes (edital e projeto exigem organizações de outros tipos), e é justamente aí que o teste de
#: vazamento fica interessante: há linhas de terceiros no banco e a organização nova lê zero.
SEEDED_HERE = ["programs", "program_indicators", "value_events", "payment_instruments",
               "platform_charges", "charge_events", "charge_installments"]

#: Tabelas em que o app NÃO pode escrever direto. Cada uma tem um porquê:
#: value_events e charge_events são trilha escrita por gatilho; as demais são decisão da plataforma.
APP_CANNOT_INSERT = {
    "value_events": "trilha de valor: só `app_record_value()` escreve",
    "charge_events": "trilha de cobrança: só o gatilho escreve",
}
APP_NEEDS_PRIV = {
    "value_baselines": "linha de base exige fonte, data e método declarados pela plataforma",
    "ai_price_table": "preço de IA é decisão da plataforma",
    "monetization_rules": "regra de receita passa pelo portão legal",
    "monetization_legal_cards": "cartão legal é parecer, não configuração",
    "legal_documents": "documento legal é publicado por migração, não pelo produto",
}


class CatalogTests(unittest.TestCase):
    """Lido do catálogo do PostgreSQL, não do código: é o estado real do banco."""

    @classmethod
    def setUpClass(cls):
        with db_system() as c:
            cls.rls = {r["relname"]: r["relrowsecurity"] for r in c.query(
                "SELECT relname, relrowsecurity FROM pg_class WHERE relname = ANY($1)", NEW_TABLES)}
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

    def test_every_new_table_exists(self):
        self.assertEqual(set(self.rls), set(NEW_TABLES),
                         "tabela declarada nesta lista e ausente do banco (ou o contrário)")

    def test_every_new_table_has_row_level_security(self):
        off = [t for t, on in self.rls.items() if not on]
        self.assertEqual(off, [], f"tabela nova sem RLS: {off}")

    def test_every_new_table_has_at_least_one_policy(self):
        """RLS ligada e sem política nega tudo — parece seguro e quebra o produto em silêncio."""
        missing = [t for t in NEW_TABLES if self.policies.get(t, 0) == 0]
        self.assertEqual(missing, [], f"RLS ligada sem política: {missing}")

    def test_the_append_only_tables_are_not_writable_by_the_app(self):
        for table, why in APP_CANNOT_INSERT.items():
            self.assertNotIn("INSERT", self.grants.get(table, set()), f"{table}: {why}")

    def test_no_new_table_grants_delete_to_the_app_except_program_parts(self):
        allowed = {"program_calls", "program_projects", "program_indicators", "program_needs",
                   "programs"}
        for table, privs in self.grants.items():
            if "DELETE" in privs:
                self.assertIn(table, allowed, f"{table} concede DELETE ao app sem justificativa")

    def test_no_new_column_holds_personal_data_in_the_clear(self):
        """Varredura por nome de coluna. A exceção é declarada, uma por uma, com o motivo."""
        allowed = {
            ("payment_instruments", "provider_token"): "token do provedor, não o cartão",
            ("legal_acceptances", "ip"): "prova de aceite; apagado na exclusão e pela retenção",
            ("legal_acceptances", "user_agent"): "idem",
            ("payment_instruments", "holder_label"): "rótulo escolhido pela organização; gatilho "
                                                     "recusa sequência longa de dígitos",
            ("monetization_rules", "legal_card_id"): "cartão aqui é PARECER legal, não cartão de "
                                                     "crédito: aponta para monetization_legal_cards",
        }
        # A comparação é por PALAVRA do nome (partido por "_"), não por pedaço de texto: a primeira
        # versão deste teste procurava substring e acusava `subscription_id` (contém "ip"),
        # `legal_card_id` (contém "card") e `description` (contém "ip"). Varredura que grita com
        # nome inocente é varredura que alguém desliga.
        suspicious = {"cpf", "rg", "email", "mail", "phone", "telefone", "password", "senha",
                      "token", "card", "cartao", "cvv", "ip", "agent", "secret", "birth",
                      "nascimento", "address", "endereco"}
        with db_system() as c:
            cols = c.query("SELECT table_name, column_name FROM information_schema.columns"
                           " WHERE table_name = ANY($1)", NEW_TABLES)
        found = []
        for row in cols:
            words = set(row["column_name"].split("_"))
            if words & suspicious and (row["table_name"], row["column_name"]) not in allowed:
                found.append(f"{row['table_name']}.{row['column_name']}")
        self.assertEqual(found, [], f"coluna nova com cara de dado pessoal e sem justificativa: {found}")


class IsolationMatrixTests(unittest.TestCase):
    """Uma organização cria de tudo; a outra não vê nada. Linha por linha, tabela por tabela."""

    @classmethod
    def setUpClass(cls):
        cls.a = new_account("company", compliance="approved")
        cls.b = new_account("company", compliance="approved")
        cls.admin, _ = make_admin()
        # programa com chamada, indicador e necessidade
        p = cls.a.post("/v1/programs", {
            "title": "Programa de isolamento",
            "summary": "Programa criado para o teste de isolamento da camada econômica da v0.17.0.",
            "objective": "Provar que nenhuma linha deste programa aparece para outra organização."})
        assert p.status == 201, p
        cls.program = p.json["id"]
        with db_system() as c:
            ind = c.scalar("SELECT id::text FROM indicator_catalog WHERE org_id IS NULL LIMIT 1")
            need = c.scalar("SELECT id::text FROM territory_needs LIMIT 1")
        if ind:
            assert cls.a.post(f"/v1/programs/{cls.program}/indicators",
                              {"indicator_id": ind, "target_value": 100.0}).status == 201
        cls.has_need = bool(need)
        if need:
            cls.a.post(f"/v1/programs/{cls.program}/needs", {"need_id": need})
        # cobrança com parcelamento
        ch = cls.a.post("/v1/payments/charges", {"kind": "installment_plan", "method": "card",
                                                 "amount_cents": 20_000, "installments": 2})
        assert ch.status == 201, ch
        cls.charge = ch.json["id"]
        due = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        due2 = (dt.date.today() + dt.timedelta(days=60)).isoformat()
        cls.a.put(f"/v1/payments/charges/{cls.charge}/installments",
                  {"schedule": [{"amount_cents": 10_000, "due_on": due},
                                {"amount_cents": 10_000, "due_on": due2}]})
        # instrumento de pagamento
        with app_tx(cls.a) as conn:
            conn.run("INSERT INTO payment_instruments(org_id,kind,provider,provider_token,last4)"
                     " VALUES ($1,'card','sandbox','tok_isolamento_a','4242')", cls.a.org_id)
        # evento de valor (pelo caminho real: um retrato de prontidão)
        cls.a.post("/v1/readiness/snapshots", {})

    def _args(self, where: str) -> tuple:
        """O valor que o WHERE desta tabela pede. Cada consulta leva um só, por isso todos são $1."""
        if "program_id" in where:
            return (self.program,)
        if "charge_id" in where:
            return (self.charge,)
        return (self.a.org_id,)

    def test_the_scenario_actually_wrote_rows(self):
        """Isolamento que passa porque não há dado é isolamento que não foi testado."""
        vazias = []
        with app_tx(self.a, readonly=True) as conn:
            for table in SEEDED_HERE:
                if conn.scalar(f"SELECT count(*) FROM {table}") == 0:   # noqa: S608
                    vazias.append(table)
        self.assertEqual(vazias, [], f"o cenário não escreveu nada em {vazias}")

    def test_the_other_organization_reads_none_of_my_rows(self):
        leaked = []
        with app_tx(self.b, readonly=True) as conn:
            for table, where in ORG_SCOPED.items():
                n = conn.scalar(f"SELECT count(*) FROM {table} WHERE {where}",   # noqa: S608
                                *self._args(where))
                if n:
                    leaked.append(f"{table} ({n})")
        self.assertEqual(leaked, [], f"linha de outra organização visível: {leaked}")

    def test_and_the_owner_does_read_its_own_rows(self):
        """O par do teste acima. Sem ele, um WHERE errado faria o vazamento 'passar'."""
        seen = []
        with app_tx(self.a, readonly=True) as conn:
            for table, where in ORG_SCOPED.items():
                if table not in SEEDED_HERE:
                    continue
                n = conn.scalar(f"SELECT count(*) FROM {table} WHERE {where}",   # noqa: S608
                                *self._args(where))
                if n == 0:
                    seen.append(table)
        self.assertEqual(seen, [], f"o WHERE do teste de isolamento não acha nada em {seen}")

    def test_the_other_organization_cannot_reach_it_by_api_either(self):
        for path in (f"/v1/programs/{self.program}/indicators",
                     f"/v1/payments/charges/{self.charge}"):
            self.assertIn(self.b.get(path).status, (403, 404), path)

    def test_the_other_organization_cannot_write_into_my_program(self):
        r = self.b.post(f"/v1/programs/{self.program}/indicators",
                        {"indicator_id": "00000000-0000-0000-0000-000000000001"})
        self.assertIn(r.status, (403, 404), r)

    def test_a_draft_program_is_invisible_to_everyone_else(self):
        self.assertIn(self.b.get(f"/v1/programs/{self.program}").status, (403, 404))
        from tests.support import Client
        self.assertIn(Client().get(f"/v1/programs/{self.program}").status, (401, 403, 404))

    def test_the_platform_admin_does_not_read_the_card_token(self):
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM payment_instruments"
                                      " WHERE provider_token = 'tok_isolamento_a'"), 0)


class PrivacyTests(unittest.TestCase):
    """O conflito entre prova append-only e direito de eliminação, resolvido por estreitamento."""

    def setUp(self):
        self.c = new_account("osc")
        # v0.20.0 — A ORDEM AQUI PASSOU A IMPORTAR, e vale dizer por quê.
        #
        # Desde a v0.20.0 o cadastro registra o aceite dos documentos pendentes no próprio
        # `register()`. Então uma conta criada DEPOIS do documento abaixo já nasce tendo aceitado
        # ele — e o INSERT manual de aceite antigo, mais adiante, colidiria com a chave única.
        # `self.pre` é criada ANTES do documento existir, justamente para que o teste possa
        # fabricar um aceite com data antiga. A colisão não era defeito do produto: era o teste
        # supondo um cadastro que não registra nada, o que deixou de ser verdade.
        self.pre = new_account("osc")
        oc = owner_conn()
        try:
            self.doc = oc.scalar(
                "INSERT INTO legal_documents(doc_key, version, title, summary, source_path,"
                " body_md, audience, requires_acceptance, status, reviewed_by, reviewed_at,"
                " review_reference, effective_from, software_version)"
                " VALUES ('test_privacy', 1, 'Documento de Teste de Privacidade',"
                " 'Documento do teste para exercitar a anonimização da prova de aceite.',"
                " 'docs/legal/_TESTE.md', $1, 'all', true, 'approved', 'Advogada de Teste', now(),"
                " 'parecer fictício', current_date, '0.17.0') RETURNING id::text",
                "# Teste de privacidade\n\n" + ("texto longo o bastante para o CHECK. " * 10))
        finally:
            oc.close()
        r = self.c.post("/v1/legal/acceptances", {"doc_key": "test_privacy"})
        self.assertEqual(r.status, 201, r)

    def tearDown(self):
        oc = owner_conn()
        try:
            oc.run("DELETE FROM legal_acceptances WHERE doc_key = 'test_privacy'")
            oc.run("DELETE FROM legal_documents WHERE doc_key = 'test_privacy'")
        finally:
            oc.close()

    def test_the_acceptance_proof_appears_in_the_data_export(self):
        r = self.c.get("/v1/privacy/export")
        self.assertEqual(r.status, 200, r)
        rows = r.json["legal_acceptances"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]["body_sha256"]), 64,
                         "a portabilidade tem de levar o hash: é o que torna a prova verificável")

    def test_only_the_ip_and_the_user_agent_can_be_erased(self):
        with app_tx(self.c) as conn:
            conn.run("UPDATE legal_acceptances SET ip = NULL, user_agent = NULL"
                     " WHERE user_id = $1", self.c.user["id"])
        # Alterar qualquer outra coluna é recusado DUAS vezes: pelo GRANT de coluna (o app só tem
        # UPDATE em `ip` e `user_agent`) e, se alguém ampliasse o GRANT, pelo gatilho. A mensagem que
        # chega é a da primeira trava — permissão — e é por isso que o teste aceita as duas.
        with app_tx(self.c) as conn, self.assertRaises(Exception) as e:
            conn.run("UPDATE legal_acceptances SET version = 99 WHERE user_id = $1",
                     self.c.user["id"])
        msg = str(e.exception).lower()
        self.assertTrue("permission denied" in msg or "append-only" in msg, msg)
        oc = owner_conn()
        try:
            with self.assertRaises(Exception) as e2:
                oc.run("UPDATE legal_acceptances SET version = 99 WHERE doc_key = 'test_privacy'")
            self.assertIn("append-only", str(e2.exception))
        finally:
            oc.close()

    def test_the_ip_cannot_be_swapped_for_another_one(self):
        with app_tx(self.c) as conn, self.assertRaises(Exception) as e:
            conn.run("UPDATE legal_acceptances SET ip = '198.51.100.9' WHERE user_id = $1",
                     self.c.user["id"])
        # A migração 0035 separou as mensagens de IP e de agente de usuário (antes era uma só, no
        # plural) para permitir a anonimização de org_id que a chave estrangeira promete. A RECUSA é
        # a mesma; só o texto ficou específico.
        self.assertIn("APAGADO", str(e.exception),
                      "o app TEM permissão nesta coluna; quem recusa é o gatilho")

    def test_deleting_the_account_erases_the_ip_and_keeps_the_proof(self):
        uid = self.c.user["id"]
        from tests.support import PASSWORD
        r = self.c.post("/v1/privacy/delete-account", {"password": PASSWORD, "confirm": True})
        self.assertEqual(r.status, 200, r)
        with db_system() as c:
            row = c.one("SELECT doc_key, version, body_sha256, ip, user_agent FROM legal_acceptances"
                        " WHERE user_id = $1", uid)
        self.assertIsNotNone(row, "a prova de aceite não pode desaparecer com a conta")
        self.assertIsNone(row["ip"])
        self.assertIsNone(row["user_agent"])
        self.assertEqual(len(row["body_sha256"]), 64)

    def test_retention_empties_old_webhook_payloads_and_old_acceptance_ips(self):
        from impacto import jobs as J
        from tests.support import server
        outro = self.pre
        oc = owner_conn()
        try:
            oc.run("INSERT INTO billing_events(provider, event_id, type, payload)"
                   " VALUES ('sandbox','evt_retencao_teste','charge.paid',$1::jsonb)",
                   '{"email":"pagador@exemplo.org"}')
            oc.run("UPDATE billing_events SET received_at = now() - interval '19 months'"
                   " WHERE event_id = 'evt_retencao_teste'")
            # O aceite não pode ser ENVELHECIDO por UPDATE — o gatilho append-only recusa, e está
            # certo. Então o aceite antigo nasce antigo: `accepted_at` é informado no INSERT.
            oc.run("INSERT INTO legal_acceptances(document_id, user_id, accepted_at, ip, user_agent)"
                   " VALUES ($1,$2, now() - interval '19 months', '203.0.113.9', 'teste/1.0')",
                   self.doc, outro.user["id"])
        finally:
            oc.close()
        out = J.retention(server()["state"])
        self.assertGreaterEqual(out["billing_event_payloads"], 1)
        self.assertGreaterEqual(out["acceptance_ips"], 1, "o IP de aceite vencido tem de sair")
        with db_system() as c:
            row = c.one("SELECT ip, user_agent, body_sha256 FROM legal_acceptances"
                        " WHERE user_id = $1", outro.user["id"])
        self.assertIsNone(row["ip"])
        self.assertIsNone(row["user_agent"])
        self.assertEqual(len(row["body_sha256"]), 64, "e a prova continua lá")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT payload::text FROM billing_events"
                                      " WHERE event_id = 'evt_retencao_teste'"), "{}")
            self.assertEqual(c.scalar("SELECT count(*) FROM billing_events"
                                      " WHERE event_id = 'evt_retencao_teste'"), 1,
                             "o evento fica; só o conteúdo sai")


if __name__ == "__main__":
    unittest.main()
