"""Motor de auditoria: os campos que faltavam, a árvore de causa e as tentativas de burlá-la.

O QUE JÁ EXISTIA

`audit_events` é append-only desde a v0.2.0, com cadeia de hash por organização calculada no banco,
redação de campo sensível e 319 chamadas no código. O prompt desta rodada pede um "motor de
auditoria" como se não houvesse nenhum. O que faltava são campos e relações, não a tabela:

    actor_type · before_state · after_state · correlation_id · parent_event_id · session_id
    user_agent · severity · status · source · resource_name

E faltava a consulta que o prompt nomeia: sair de "quem mexeu neste documento?" para "mostre-me a
cadeia de acontecimentos que levou este documento até este estado".

O TESTE MAIS IMPORTANTE DESTE ARQUIVO

`TheChainStaysValidAcrossTheSchemaChangeTests`. Acrescentar coluna ao material do hash invalidaria
o hash de TODA linha existente, e a verificação passaria a acusar manipulação onde não houve — o
que é pior que não verificar. O material é versionado, e o teste prova que linha antiga e linha
nova verificam ao mesmo tempo.
"""
from __future__ import annotations

import unittest

from tests.support import (Client, app_tx, db_system, make_staff, new_account, owner_conn,
                           reauth)


class TheStandardFieldsExistAndAreFilledWithoutTouchingCallersTests(unittest.TestCase):
    """319 chamadores não foram alterados. Quem preenche é `Ctx.audit()`, o ponto de passagem."""

    def test_a_normal_user_action_is_recorded_with_actor_type_user(self):
        c = new_account("osc", compliance="approved")
        c.post("/v1/org/invitations", {"email": "convidada@teste.org", "role": "member"})
        with db_system() as conn:
            e = conn.one("SELECT actor_type, severity, status, source, session_id, user_agent,"
                         "       correlation_id, request_id, chain_version"
                         "  FROM audit_events WHERE org_id = $1 AND action = 'member.invited'"
                         " ORDER BY id DESC LIMIT 1", c.org_id)
        self.assertIsNotNone(e, "a ação não gerou evento de auditoria")
        self.assertEqual("user", e["actor_type"])
        self.assertEqual("info", e["severity"])
        self.assertEqual("success", e["status"])
        self.assertEqual("api", e["source"])
        self.assertIsNotNone(e["session_id"], "o evento não registrou a sessão")
        self.assertIsNotNone(e["user_agent"], "o evento não registrou o agente")
        self.assertEqual(e["request_id"], e["correlation_id"],
                         "sem cabeçalho de correlação, rastro e requisição coincidem")
        self.assertEqual(2, e["chain_version"], "linha nova tem de nascer na versão 2 da cadeia")

    def test_a_staff_action_is_recorded_with_actor_type_admin(self):
        """Distinguir pessoa de administrador é a primeira pergunta depois de "quem"."""
        c = make_staff("audit")
        reauth(c)
        r = c.post("/v1/admin/audit/export", {"limit": 1})
        self.assertEqual(200, r.status, r.json)
        with db_system() as conn:
            tipo = conn.scalar("SELECT actor_type FROM audit_events WHERE id = $1",
                               r.json["export_event_id"])
        self.assertEqual("admin", tipo, "evento de membro da equipe não saiu como admin")

    def test_a_direct_record_call_with_an_actor_is_not_marked_as_system(self):
        """O padrão fixo `"system"` marcava como SISTEMA ação que uma pessoa acabara de fazer."""
        c = new_account("osc", compliance="approved")
        with db_system() as conn:
            tipo = conn.scalar("SELECT actor_type FROM audit_events"
                               " WHERE action = 'user.registered' AND org_id = $1"
                               " ORDER BY id DESC LIMIT 1", c.org_id)
        self.assertEqual("user", tipo)

    def test_the_correlation_header_ties_several_requests_into_one_trail(self):
        """Uma operação do produto costuma ser várias requisições. O rastro é o que as amarra."""
        c = new_account("osc", compliance="approved")
        rastro = "rastro-de-teste-0001"
        for destinatario in ("a@teste.org", "b@teste.org"):
            c.post("/v1/org/invitations", {"email": destinatario, "role": "member"},
                   headers={"x-correlation-id": rastro})
        with db_system() as conn:
            n = conn.scalar("SELECT count(*) FROM audit_events WHERE correlation_id = $1", rastro)
        self.assertEqual(2, n, "as duas requisições não entraram no mesmo rastro")

    def test_a_malformed_correlation_header_is_cleaned_not_trusted(self):
        """Cabeçalho é entrada do cliente. Guardar o que vier nele é guardar o que o cliente quiser."""
        c = new_account("osc", compliance="approved")
        c.post("/v1/org/invitations", {"email": "c@teste.org", "role": "member"},
               headers={"x-correlation-id": "'; DROP TABLE audit_events; --" + "x" * 200})
        with db_system() as conn:
            valor = conn.scalar("SELECT correlation_id FROM audit_events"
                                " WHERE org_id = $1 ORDER BY id DESC LIMIT 1", c.org_id)
        self.assertLessEqual(len(valor or ""), 64)
        self.assertNotIn(";", valor or "")
        self.assertNotIn(" ", valor or "")

    def test_severity_is_derived_in_one_place_not_asked_of_every_caller(self):
        from impacto.services.audit import severity_of
        self.assertEqual("critical", severity_of("auth.refresh_reuse_detected"))
        self.assertEqual("critical", severity_of("security.kill_switch_engaged"))
        self.assertEqual("warning", severity_of("auth.login_failed"))
        self.assertEqual("warning", severity_of("project.created", status="denied"))
        self.assertEqual("info", severity_of("project.created"))

    def test_a_security_event_is_recorded_with_higher_severity(self):
        c = new_account("osc", compliance="approved")
        Client().post("/v1/auth/login", {"email": c.email, "password": "senha-errada-de-proposito"})
        with db_system() as conn:
            e = conn.one("SELECT severity, actor_type FROM audit_events"
                         " WHERE action = 'auth.login_failed' ORDER BY id DESC LIMIT 1")
        self.assertEqual("warning", e["severity"])

    def test_every_action_prefix_in_the_codebase_has_a_category(self):
        """Filtro de categoria que joga a maioria dos eventos em "outros" não é um filtro.

        A primeira versão derivava a categoria de um CASE no código e cobria as nove categorias do
        prompt. Este teste mostrou que a base tem 86 prefixos de ação e 68 caíam em OTHER. A
        taxonomia virou tabela (`audit_action_categories`), e o que este teste protege é a
        COBERTURA: um domínio novo no código sem categoria reprova, em vez de cair em OTHER sem
        ninguém notar.
        """
        import re
        from pathlib import Path
        pasta = Path(__file__).parent.parent / "impacto"
        codigo = "\n".join(f.read_text(encoding="utf-8") for f in pasta.rglob("*.py"))
        acoes = set(re.findall(r'audit\(c[^,]*,\s*"([a-z_]+\.[a-z0-9_.]+)"', codigo))
        acoes |= set(re.findall(r'action="([a-z_]+\.[a-z0-9_.]+)"', codigo))
        self.assertGreater(len(acoes), 100, "a varredura não encontrou as ações")
        prefixos = sorted({a.split(".")[0] for a in acoes})
        with db_system() as conn:
            catalogados = {r["prefix"] for r in
                           conn.query("SELECT prefix FROM audit_action_categories")}
        faltando = [p for p in prefixos if p not in catalogados]
        self.assertEqual([], faltando,
                         f"prefixo de ação sem categoria (cairia em OTHER): {faltando}")

    def test_the_category_of_a_known_action_is_the_expected_one(self):
        """Contraprova da cobertura: uma tabela com tudo em OTHER passaria no teste acima."""
        esperado = {"auth.login": "AUTH", "member.invited": "USERS", "org.created": "ORGS",
                    "document.uploaded": "DOCUMENTS", "indicator.value_reported": "PROJECTS",
                    "application.transition": "WORKFLOWS", "expense.registered": "FINANCE",
                    "ai.classified": "AI", "audit.log_exported": "SECURITY",
                    "integration.export.generated": "INTEGRATIONS"}
        with db_system() as conn:
            for acao, categoria in esperado.items():
                with self.subTest(acao=acao):
                    self.assertEqual(categoria, conn.scalar("SELECT audit_category($1)", acao))

    def test_an_unknown_domain_still_falls_into_other_instead_of_failing(self):
        """A função não pode levantar para ação desconhecida: ela roda dentro da leitura da trilha."""
        with db_system() as conn:
            self.assertEqual("OTHER", conn.scalar("SELECT audit_category('dominio_novo.coisa')"))


class BeforeAndAfterSayFromWhatToWhatTests(unittest.TestCase):
    """A trilha registrava que algo mudou. Não de QUE para QUE."""

    def test_the_columns_accept_state_and_redact_secrets_in_them(self):
        c = new_account("osc", compliance="approved")
        from impacto.services.audit import record
        with db_system() as conn:
            record(conn, org_id=c.org_id, actor=None, action="teste.mudanca",
                   object_type="teste", object_id="1",
                   before={"status": "draft", "api_key": "NAO_PODE_APARECER"},
                   after={"status": "published", "api_key": "TAMBEM_NAO"})
            e = conn.one("SELECT before_state::text AS antes, after_state::text AS depois"
                         "  FROM audit_events WHERE action = 'teste.mudanca'"
                         " ORDER BY id DESC LIMIT 1")
        self.assertIn("draft", e["antes"])
        self.assertIn("published", e["depois"])
        self.assertNotIn("NAO_PODE_APARECER", e["antes"],
                         "a redação não alcançou before_state: é a mesma tabela imutável")
        self.assertNotIn("TAMBEM_NAO", e["depois"])

    def test_the_before_and_after_are_protected_by_the_hash_chain(self):
        """Campo novo que não entra no material do hash é campo que pode ser reescrito em silêncio."""
        c = new_account("osc", compliance="approved")
        from impacto.services.audit import record
        with db_system() as conn:
            record(conn, org_id=c.org_id, actor=None, action="teste.protegido",
                   object_type="teste", object_id="2",
                   before={"valor": 1}, after={"valor": 2})
        conn = owner_conn()
        try:
            conn.run("ALTER TABLE audit_events DISABLE TRIGGER trg_append_only")
            conn.run("UPDATE audit_events SET after_state = '{\"valor\": 999}'::jsonb"
                     " WHERE action = 'teste.protegido' AND org_id = $1", c.org_id)
            conn.run("ALTER TABLE audit_events ENABLE TRIGGER trg_append_only")
            v = conn.one("SELECT valid, first_broken_seq FROM audit_verify($1)", c.org_id)
        finally:
            conn.close()
        self.assertFalse(v["valid"],
                         "alterar after_state não quebrou a cadeia: o campo não está protegido")


class TheChainStaysValidAcrossTheSchemaChangeTests(unittest.TestCase):
    """O teste que autoriza a mudança de esquema numa tabela encadeada por hash.

    Material versionado: a versão 1 é literalmente a fórmula anterior, a 2 acrescenta os campos
    novos. Calcular o material novo sobre linhas antigas seria reescrever a história para que ela
    feche — e a verificação deixaria de significar alguma coisa.
    """

    def test_an_old_row_and_a_new_row_verify_together(self):
        """Simula a situação real: linhas gravadas ANTES da migração 0056 e linhas gravadas depois.

        A primeira versão deste teste reescrevia o hash de uma linha no meio da cadeia, o que quebra
        o `prev_hash` da seguinte — e o teste acusava a implementação por um defeito do arranjo. O
        jeito certo é desligar o gatilho que força a versão 2 e deixar a cadeia ser construída na
        ordem, como aconteceu de verdade.
        """
        from impacto.services.audit import record
        c = new_account("osc", compliance="approved")
        conn = owner_conn()
        try:
            conn.run("ALTER TABLE audit_events DISABLE TRIGGER ab_trg_audit_chain_version")
        finally:
            conn.close()
        try:
            with db_system() as conn:
                for i in ("um", "dois"):
                    conn.run("INSERT INTO audit_events(org_id, action, chain_version)"
                             " VALUES ($1, $2, 1)", c.org_id, f"teste.antiga_{i}")
        finally:
            conn = owner_conn()
            try:
                conn.run("ALTER TABLE audit_events ENABLE TRIGGER ab_trg_audit_chain_version")
            finally:
                conn.close()
        with db_system() as conn:
            record(conn, org_id=c.org_id, actor=None, action="teste.nova", object_type="t",
                   object_id="1", before={"a": 1}, after={"a": 2})
            v = conn.one("SELECT entries, valid, first_broken_seq FROM audit_verify($1)", c.org_id)
            versoes = {r["chain_version"] for r in
                       conn.query("SELECT DISTINCT chain_version FROM audit_events"
                                  " WHERE org_id = $1", c.org_id)}
        self.assertEqual({1, 2}, versoes, "o arranjo não produziu as duas versões de material")
        self.assertTrue(v["valid"],
                        f"a cadeia mista não verifica (quebra em {v['first_broken_seq']}): "
                        "material versionado é exatamente o que evita isso")
        self.assertGreaterEqual(v["entries"], 3)

    def test_the_version_one_formula_was_not_touched(self):
        """Se a fórmula da versão 1 mudar, todo hash gravado antes da migração 0056 deixa de fechar."""
        with db_system() as c:
            fonte = c.scalar("SELECT prosrc FROM pg_proc WHERE proname = 'audit_material'")
        # A fórmula antiga, campo por campo, na ordem exata.
        for campo in ("e.prev_hash", "e.seq::text", "coalesce(e.org_id::text,'')",
                      "coalesce(e.actor_user_id::text,'')", "e.action",
                      "coalesce(e.object_type,'')", "coalesce(e.object_id,'')",
                      "e.payload::text", "ts_canonical(e.at)"):
            with self.subTest(campo=campo):
                self.assertIn(campo, fonte)
        self.assertIn("chain_version <= 1", fonte, "o material deixou de ser versionado")

    def test_a_new_row_cannot_be_born_in_version_one(self):
        """Nascer na versão 1 deixaria os campos novos fora da proteção do hash."""
        c = new_account("osc", compliance="approved")
        with db_system() as conn:
            conn.run("INSERT INTO audit_events(org_id, action, chain_version)"
                     " VALUES ($1,'teste.versao',1)", c.org_id)
            v = conn.scalar("SELECT chain_version FROM audit_events WHERE action = 'teste.versao'"
                            " AND org_id = $1 ORDER BY id DESC LIMIT 1", c.org_id)
        self.assertEqual(2, v, "o gatilho não forçou a versão 2 na linha nova")


class TheCausalTreeAnswersWhatLedToWhatTests(unittest.TestCase):

    def _rastro(self, org: str) -> tuple[str, int, int]:
        from impacto.services.audit import record
        rastro = "arvore-de-teste-" + org[:8]
        with db_system() as conn:
            raiz = record(conn, org_id=org, actor=None, action="document.uploaded",
                          object_type="document", object_id="d1", correlation_id=rastro,
                          resource_name="contrato.pdf")
            filho = record(conn, org_id=org, actor=None, action="document.classified",
                           object_type="document", object_id="d1", correlation_id=rastro,
                           parent_event_id=raiz, actor_type="ai")
            record(conn, org_id=org, actor=None, action="document.approved",
                   object_type="document", object_id="d1", correlation_id=rastro,
                   parent_event_id=filho)
        return rastro, raiz, filho

    def test_the_tree_is_returned_with_depth(self):
        c = make_staff("audit")
        org = new_account("osc", compliance="approved").org_id
        rastro, raiz, filho = self._rastro(org)
        r = c.get(f"/v1/admin/audit/trail?correlation_id={rastro}")
        self.assertEqual(200, r.status, r.json)
        arvore = r.json["tree"]
        self.assertEqual(3, len(arvore), f"a árvore não tem os três eventos: {arvore}")
        self.assertEqual([0, 1, 2], [n["depth"] for n in arvore],
                         "a profundidade é o que a interface indenta")
        self.assertEqual("ai", arvore[1]["actor_type"],
                         "o passo de classificação é da IA e tem de dizer isso")

    def test_an_event_without_a_declared_cause_is_a_root_of_the_tree_not_an_orphan(self):
        """A árvore tem de conter TODO evento do rastro — raiz ou descendente, nunca de fora.

        A primeira versão desta rota devolvia um campo `unlinked` para "eventos fora da árvore".
        Ele é vazio por construção: `audit_trail_of()` traz como raiz todo evento sem pai, e o banco
        recusa pai de outra correlação. Campo que não pode ter conteúdo sugere que informa e não
        informa. O que vale conferir é a COMPLETUDE, e é o que este teste faz.
        """
        from impacto.services.audit import record
        c = make_staff("audit")
        org = new_account("osc", compliance="approved").org_id
        rastro, _, _ = self._rastro(org)
        with db_system() as conn:
            record(conn, org_id=org, actor=None, action="document.downloaded",
                   object_type="document", object_id="d1", correlation_id=rastro)
        r = c.get(f"/v1/admin/audit/trail?correlation_id={rastro}")
        self.assertTrue(r.json["complete"], r.json["note"])
        self.assertEqual(r.json["events_in_trail"], r.json["events_in_tree"])
        acoes = [n["action"] for n in r.json["tree"]]
        self.assertIn("document.downloaded", acoes,
                      "evento sem causa declarada desapareceu da árvore")
        self.assertEqual(0, next(n["depth"] for n in r.json["tree"]
                                 if n["action"] == "document.downloaded"),
                         "evento sem pai é raiz, profundidade zero")

    def test_an_incomplete_tree_says_so_loudly(self):
        """Contraprova: a conferência de completude só vale se souber reprovar."""
        c = make_staff("audit")
        org = new_account("osc", compliance="approved").org_id
        rastro, raiz, _ = self._rastro(org)
        conn = owner_conn()
        try:
            # Aponta um filho para fora da correlação — o que o gatilho recusa, e é por isso que
            # a simulação precisa desligá-lo. É exatamente o cenário "alteração direta no banco".
            conn.run("ALTER TABLE audit_events DISABLE TRIGGER trg_append_only")
            conn.run("UPDATE audit_events SET correlation_id = 'outro-rastro'"
                     " WHERE id = $1", raiz)
            conn.run("ALTER TABLE audit_events ENABLE TRIGGER trg_append_only")
            r = c.get(f"/v1/admin/audit/trail?correlation_id={rastro}")
            self.assertFalse(r.json["complete"])
            self.assertIn("alteração direta no banco", r.json["note"])
        finally:
            conn.close()

    def test_a_parent_from_another_organization_is_refused(self):
        """A árvore de causa não cruza inquilino: se cruzasse, ela mentiria sobre quem fez o quê."""
        from impacto.services.audit import record
        a = new_account("osc", compliance="approved")
        b = new_account("osc", compliance="approved")
        with db_system() as conn:
            pai = record(conn, org_id=a.org_id, actor=None, action="teste.pai",
                         correlation_id="rastro-a")
            conn.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                record(conn, org_id=b.org_id, actor=None, action="teste.filho",
                       correlation_id="rastro-a", parent_event_id=pai)
            conn.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("outra organização", str(erro.exception))

    def test_a_parent_from_another_trail_is_refused(self):
        from impacto.services.audit import record
        a = new_account("osc", compliance="approved")
        with db_system() as conn:
            pai = record(conn, org_id=a.org_id, actor=None, action="teste.pai_outro",
                         correlation_id="rastro-x")
            conn.run("SAVEPOINT s")
            with self.assertRaises(Exception) as erro:
                record(conn, org_id=a.org_id, actor=None, action="teste.filho_outro",
                       correlation_id="rastro-y", parent_event_id=pai)
            conn.run("ROLLBACK TO SAVEPOINT s")
            self.assertIn("outra correlação", str(erro.exception))

    def test_the_timeline_of_one_entity_is_returned_in_order(self):
        c = make_staff("audit")
        org = new_account("osc", compliance="approved").org_id
        self._rastro(org)
        r = c.get("/v1/admin/audit/timeline?object_type=document&object_id=d1")
        self.assertEqual(200, r.status, r.json)
        acoes = [e["action"] for e in r.json["events"]]
        self.assertEqual(["document.uploaded", "document.classified", "document.approved"],
                         acoes[:3])
        self.assertEqual("contrato.pdf", r.json["events"][0]["resource_name"],
                         "o nome do recurso é o que a pessoa lê; o id sobrevive ao objeto apagado")

    def test_a_truncated_timeline_says_so_instead_of_pretending_to_be_complete(self):
        from impacto.services.audit import record
        c = make_staff("audit")
        org = new_account("osc", compliance="approved").org_id
        with db_system() as conn:
            for i in range(4):
                record(conn, org_id=org, actor=None, action=f"teste.corte_{_NOMES[i]}",
                       object_type="documento_longo", object_id="z1")
        r = c.get("/v1/admin/audit/timeline?object_type=documento_longo&object_id=z1&limit=2")
        self.assertTrue(r.json["truncated"])
        self.assertIn("nada se perdeu", r.json["note"])


class TheAuditApiIsHardAgainstTheUsualAttacksTests(unittest.TestCase):
    """IDOR, BOLA, escalada de privilégio, cruzamento de inquilino, forja e apagamento."""

    def test_a_client_organization_cannot_reach_the_audit_api_at_all(self):
        c = new_account("osc", compliance="approved")
        for caminho in ("/v1/admin/audit", "/v1/admin/audit/timeline?object_type=a&object_id=b",
                        "/v1/admin/audit/trail?correlation_id=x"):
            with self.subTest(caminho=caminho):
                self.assertIn(c.get(caminho).status, (401, 403))

    def test_a_staff_role_without_the_permission_is_refused(self):
        """Escalada de privilégio: papel de conteúdo não vira auditor por tentar."""
        c = make_staff("support")
        self.assertEqual(403, c.get("/v1/admin/audit").status)
        self.assertEqual(403, c.post("/v1/admin/audit/export", {}).status)

    def test_reading_requires_a_different_permission_than_exporting(self):
        """Ler e LEVAR PARA FORA são operações diferentes, e levar é a que interessa a quem apaga."""
        from impacto.http import ROUTES
        leitura = next(r for r in ROUTES if r.path == "/v1/admin/audit" and r.method == "GET")
        export = next(r for r in ROUTES if r.path == "/v1/admin/audit/export")
        self.assertEqual("security.audit.read", leitura.permission)
        self.assertEqual("security.audit.export", export.permission)

    def test_an_organization_session_cannot_read_the_table_through_rls(self):
        """A rota é uma porta; a RLS é a parede. Testar só a porta deixa a parede sem prova."""
        a = new_account("osc", compliance="approved")
        b = new_account("osc", compliance="approved")
        from impacto.services.audit import record
        with db_system() as conn:
            record(conn, org_id=b.org_id, actor=None, action="teste.vizinho", object_type="t",
                   object_id="1")
        with app_tx(a) as conn:
            alheios = conn.scalar("SELECT count(*) FROM audit_events WHERE org_id = $1", b.org_id)
        self.assertEqual(0, alheios, "uma organização enxergou a trilha de outra")

    def test_an_organization_cannot_forge_an_event_in_its_own_trail(self):
        """Forjar evento é pior que apagar: um apagamento quebra a cadeia, uma forja a estende."""
        c = new_account("osc", compliance="approved")
        with app_tx(c) as conn:
            with self.assertRaises(Exception) as erro:
                conn.run("INSERT INTO audit_events(org_id, action, actor_user_id)"
                         " VALUES ($1,'auth.login',$2)", c.org_id,
                         "00000000-0000-0000-0000-000000000001")
            self.assertTrue(str(erro.exception))

    def test_an_organization_cannot_delete_or_rewrite_its_own_trail(self):
        c = new_account("osc", compliance="approved")
        from impacto.services.audit import record
        with db_system() as conn:
            record(conn, org_id=c.org_id, actor=None, action="teste.imutavel")
        with app_tx(c) as conn:
            for sql in ("DELETE FROM audit_events WHERE org_id = $1",
                        "UPDATE audit_events SET action = 'nada' WHERE org_id = $1"):
                with self.subTest(sql=sql.split()[0]):
                    conn.run("SAVEPOINT s")
                    with self.assertRaises(Exception):
                        conn.run(sql, c.org_id)
                    conn.run("ROLLBACK TO SAVEPOINT s")

    def test_even_the_database_owner_cannot_truncate_the_trail_without_disabling_a_trigger(self):
        """TRUNCATE não dispara gatilho de linha. O gatilho de TRUNCATE é o que fecha essa porta."""
        conn = owner_conn()
        try:
            conn.run("BEGIN")
            with self.assertRaises(Exception) as erro:
                conn.run("TRUNCATE audit_events")
            conn.run("ROLLBACK")
            self.assertTrue(str(erro.exception))
        finally:
            conn.close()

    def test_the_filters_do_not_let_a_crafted_value_change_the_query(self):
        from urllib.parse import quote
        c = make_staff("audit")
        for ruim in ("' OR 1=1 --", "x'; DROP TABLE audit_events; --", "../../etc/passwd"):
            with self.subTest(valor=ruim):
                r = c.get(f"/v1/admin/audit?object_id={quote(ruim, safe='')}")
                self.assertIn(r.status, (200, 422))
                if r.status == 200:
                    self.assertEqual([], r.json["items"],
                                     "o filtro casou algo com um valor que não existe")
        with db_system() as conn:
            self.assertGreater(conn.scalar("SELECT count(*) FROM audit_events"), 0,
                               "a tabela de auditoria desapareceu")

    def test_an_unknown_filter_value_is_refused_by_the_schema_not_by_the_database(self):
        c = make_staff("audit")
        r = c.get("/v1/admin/audit?severity=catastrofico")
        self.assertEqual(422, r.status, "valor fora do conjunto tem de parar no esquema")


class ExportingTheTrailIsItselfAuditedTests(unittest.TestCase):
    """Levar a trilha para fora era a única leitura privilegiada sem registro NA PRÓPRIA TRILHA."""

    def test_the_export_writes_its_own_event(self):
        c = make_staff("audit")
        reauth(c)   # `security.audit.export` está em STEP_UP_PERMISSIONS: levar a trilha para fora
        r = c.post("/v1/admin/audit/export", {"limit": 5})
        self.assertEqual(200, r.status, r.json)
        self.assertIsNotNone(r.json["export_event_id"])
        with db_system() as conn:
            e = conn.one("SELECT action, severity, actor_type, payload FROM audit_events"
                         " WHERE id = $1", r.json["export_event_id"])
        self.assertEqual("audit.log_exported", e["action"])
        self.assertEqual("warning", e["severity"])
        self.assertEqual("admin", e["actor_type"])
        self.assertIn("rows", e["payload"])

    def test_the_export_records_the_filters_that_were_used(self):
        """Saber que alguém exportou não basta: a investigação precisa saber O QUE foi exportado."""
        c = make_staff("audit")
        reauth(c)
        r = c.post("/v1/admin/audit/export", {"limit": 3, "action": "auth", "severity": "warning"})
        with db_system() as conn:
            payload = conn.scalar("SELECT payload FROM audit_events WHERE id = $1",
                                  r.json["export_event_id"])
        self.assertEqual("auth", payload["filters"]["action"])
        self.assertEqual("warning", payload["filters"]["severity"])

    def test_the_export_is_capped_and_says_the_cap(self):
        c = make_staff("audit")
        reauth(c)
        r = c.post("/v1/admin/audit/export", {"limit": 10_000_000})
        self.assertIn(r.status, (200, 422))
        if r.status == 200:
            self.assertLessEqual(r.json["limit_applied"], 10_000)

    def test_the_exported_action_is_a_declared_security_action(self):
        from impacto.services.audit import SECURITY_ACTIONS
        self.assertIn("audit.log_exported", SECURITY_ACTIONS,
                      "exportação de trilha tem de ser visível para o alerta")

    def test_reading_the_trail_also_leaves_a_privileged_access_record(self):
        c = make_staff("audit")
        self.assertEqual(200, c.get("/v1/admin/audit").status)
        with db_system() as conn:
            n = conn.scalar("SELECT count(*) FROM privileged_access_log"
                            " WHERE path = '/v1/admin/audit' AND user_id ="
                            " (SELECT id FROM users WHERE email = $1)", c.email)
        self.assertGreaterEqual(n, 1, "ler a trilha não deixou rastro de entrada privilegiada")


#: `audit_events_action_check` exige `^[a-z_]+\.[a-z_.]+$` — sem dígito. Nomear o contador por
#: extenso é mais barato que afrouxar a restrição de formato da ação.
_NOMES = ("zero", "um", "dois", "tres", "quatro", "cinco", "seis", "sete", "oito", "nove")


class ConcurrentWritersDoNotBreakTheChainTests(unittest.TestCase):
    """A cadeia usa `FOR UPDATE` em `chain_heads`. O teste prova que isso basta sob concorrência."""

    def test_sixty_concurrent_events_produce_a_valid_chain_with_no_gaps(self):
        import threading
        c = new_account("osc", compliance="approved")
        from impacto.services.audit import record
        erros: list[str] = []

        def escrever(n: int):
            try:
                with db_system() as conn:
                    for i in range(10):
                        record(conn, org_id=c.org_id, actor=None,
                               action=f"teste.concorrente_{_NOMES[n]}_{_NOMES[i]}")
            except Exception as exc:   # noqa: BLE001
                erros.append(f"{type(exc).__name__}: {exc}")

        fios = [threading.Thread(target=escrever, args=(n,)) for n in range(6)]
        for f in fios:
            f.start()
        for f in fios:
            f.join()
        self.assertEqual([], erros, f"escrita concorrente falhou: {erros[:3]}")
        with db_system() as conn:
            v = conn.one("SELECT entries, valid, first_broken_seq FROM audit_verify($1)", c.org_id)
            buracos = conn.scalar(
                "SELECT count(*) FROM (SELECT seq, lag(seq) OVER (ORDER BY seq) AS anterior"
                "  FROM audit_events WHERE org_id = $1) t"
                " WHERE anterior IS NOT NULL AND seq <> anterior + 1", c.org_id)
        self.assertGreaterEqual(v["entries"], 60)
        self.assertTrue(v["valid"], f"cadeia quebrada em {v['first_broken_seq']}")
        self.assertEqual(0, buracos, "a sequência tem buraco: duas escritas pegaram o mesmo número")


if __name__ == "__main__":
    unittest.main()
