"""v0.19.0 — exclusão de conta provada ponta a ponta sobre a camada de impacto (FASE C).

POR QUE ESTE TESTE EXISTE. A v0.18.0 acrescentou mais de trinta tabelas ligadas à organização
(alegação, conferência, revisão, reputação, contestação, selo, avaliação, responsabilidade, decisão,
contexto de equidade, denominador, materialidade, mapeamento de referencial). As cascatas estavam
declaradas nas migrações, e ninguém nunca executou uma exclusão com registro em todas elas. Cascata
que nunca rodou é cascata que você acha que tem.

E, do outro lado, há registro que PRECISA sobreviver: trilha de auditoria, prova de aceite, lançamento
financeiro, evidência que sustenta medição de terceiros. Um teste de exclusão que só confere que tudo
desapareceu é tão errado quanto nenhum teste: ele aprovaria um produto que apaga a própria prova.

Então aqui se prova as duas direções, e a terceira: que a política escrita em config/data_retention.json
é a que o banco implementa de fato.
"""
from __future__ import annotations

import unittest

from tests.support import (PASSWORD, Client, db_system, grant_premium, new_account,
                           owner_conn, server)

#: Tabelas da camada de impacto que precisam ficar sem órfão quando a organização é removida.
CAMADA_IMPACTO = (
    "claims", "claim_checks", "claim_review_requests", "claim_reviews",
    "reputation_snapshots", "reputation_disputes", "reputation_dispute_resolutions",
    "seal_awards", "seal_evaluations", "seal_revocations",
    "equity_contexts", "equity_denominators", "project_barriers", "equity_assessments",
    "materiality_assessments", "materiality_topics", "framework_mappings",
    "responsibility_assignments", "responsibility_decisions",
)


class RetentionPolicyTests(unittest.TestCase):
    """A política declarada tem de ser a que o banco implementa."""

    def test_classe_declarada_bate_com_a_regra_real_da_chave(self):
        from impacto.core import retention
        with db_system() as c:
            resultado = retention.audit(c)
        self.assertEqual(resultado["mismatched"], [],
                         "política diz uma coisa e o banco faz outra: " + str(resultado["mismatched"]))
        self.assertEqual(resultado["undeclared_non_cascade"], [],
                         "vínculo que não é cascata e ninguém classificou — guarda legítima ou bloqueio "
                         "acidental de exclusão, os dois exigem decisão: "
                         + str(resultado["undeclared_non_cascade"]))
        self.assertEqual(resultado["declared_but_absent"], [],
                         "política aponta para coluna que não existe mais")
        self.assertGreater(resultado["links"], 150)

    def test_o_conferidor_realmente_reprova(self):
        """Prova de que a conferência não é decorativa."""
        from impacto.core import retention
        doc = retention.load()
        doc["declared"]["audit_events.org_id"] = {"class": "deletable_with_parent", "reason": "forjado"}
        doc["declared"]["ledger_entries.org_id"] = {"class": "deletable_with_parent", "reason": "forjado"}
        with db_system() as c:
            resultado = retention.audit(c, doc)
        chaves = {m["key"] for m in resultado["mismatched"]}
        self.assertIn("audit_events.org_id", chaves)
        self.assertIn("ledger_entries.org_id", chaves)


class AccountDeletionTests(unittest.TestCase):
    """Exclusão de conta com registro em TODAS as áreas da camada de impacto."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.cli = new_account("osc", compliance="approved")
        grant_premium(cls.cli)
        cls.email = cls.cli.email
        cls.user_id = cls.cli.user["id"]
        cls.org_id = cls.cli.org_id
        cls.criados = cls._povoar(cls.cli)

    @classmethod
    def _povoar(cls, cli: Client) -> dict:
        """Cria registro real em cada área da camada nova, pela API, sem atalho de banco."""
        feitos: dict[str, str] = {}
        p = cli.post("/v1/projects", {
            "title": "Projeto com registro em todas as áreas",
            "problem": "Problema declarado com fonte", "objectives": "Objetivo declarado",
            "methodology": "Método declarado", "territory": "MT"})
        assert p.status in (200, 201), p.body
        feitos["project"] = p.json["id"]
        pid = feitos["project"]

        ctx = cli.put(f"/v1/projects/{pid}/equity/context", {
            "need_statement": "Necessidade declarada com fonte citada do censo municipal",
            "additionality": "Nenhum programa atende hoje",
            "need_source_name": "Censo municipal", "need_source_date": "2024-05-01"})
        assert ctx.status == 200, ctx.body
        feitos["equity_context"] = pid

        cat = cli.get("/v1/equity/catalog")
        codigo = (cat.json.get("items") or [{}])[0].get("code")
        if codigo:
            b = cli.post(f"/v1/projects/{pid}/equity/barriers",
                         {"barrier_code": codigo, "standing": "declared",
                          "note": "Barreira observada no território de atuação"})
            assert b.status in (200, 201), b.body
            feitos["barrier"] = codigo

        d = cli.post("/v1/equity/denominators", {
            "scope": "project", "project_id": pid, "kind": "households", "value": 400,
            "unit": "domicílios", "reference_date": "2024-05-01", "source_name": "Censo municipal",
            "source_date": "2024-05-01", "method_note": "Contagem de domicílios no censo municipal"})
        assert d.status in (200, 201), d.body
        feitos["denominator"] = d.json.get("id", "ok")

        cl = cli.post("/v1/claims", {
            "subject_type": "project", "subject_id": pid, "claim_kind": "result",
            "statement": "O projeto instalou filtros em domicílios da comunidade no período declarado."})
        assert cl.status in (200, 201), cl.body
        feitos["claim"] = cl.json["id"]
        cli.post(f"/v1/claims/{feitos['claim']}/check", {})

        diag = cli.post("/v1/diagnoses", {"need_statement": "Necessidade para diagnóstico",
                                          "affected_group": "Comunidade ribeirinha"})
        if diag.status in (200, 201):
            feitos["diagnosis"] = diag.json["id"]

        # Aceite legal: sem documento APROVADO E VIGENTE o gatilho recusa o aceite — e é por isso que
        # hoje não existe nenhum. O cenário aprova uma versão para poder provar a REGRA DE RETENÇÃO
        # (o aceite sobrevive à exclusão sem IP nem agente), que é o que este arquivo testa.
        from impacto.services import legal as LEGAL
        with db_system() as c:
            doc = c.one("SELECT id::text AS id, doc_key FROM legal_documents"
                        " WHERE status IN ('draft','in_legal_review') ORDER BY doc_key LIMIT 1")
            if doc:
                LEGAL.approve(c, doc_id=doc["id"], reviewed_by="Revisão jurídica do cenário de teste",
                              review_reference="Parecer interno do cenário de exclusão")
                feitos["legal_doc_key"] = doc["doc_key"]
        if feitos.get("legal_doc_key"):
            ac = cli.post("/v1/legal/acceptances", {"doc_key": feitos["legal_doc_key"]})
            assert ac.status in (200, 201), ac.body

        papeis = cli.get("/v1/responsibility/roles")
        papel = next((r["code"] for r in (papeis.json.get("roles") or papeis.json.get("items") or [])
                      if "project" in (r.get("scopes") or [])), None)
        if papel:
            a = cli.post("/v1/responsibility/assignments", {
                "scope": "project", "subject_id": pid, "role_code": papel,
                "person_user_id": cli.user["id"], "starts_on": "2026-01-01",
                "mandate_basis": "Designação registrada para o teste de exclusão"})
            if a.status in (200, 201):
                feitos["responsibility"] = a.json["id"]
        return feitos

    def test_as_areas_foram_realmente_povoadas(self):
        """Sem isto, o teste de exclusão poderia passar por não haver nada para excluir."""
        with db_system() as c:
            n_claims = c.scalar("SELECT count(*) FROM claims WHERE org_id = $1", self.org_id)
            n_checks = c.scalar("SELECT count(*) FROM claim_checks ck JOIN claims cl ON cl.id = ck.claim_id"
                                " WHERE cl.org_id = $1", self.org_id)
            n_ctx = c.scalar("SELECT count(*) FROM equity_contexts WHERE org_id = $1", self.org_id)
            n_den = c.scalar("SELECT count(*) FROM equity_denominators WHERE org_id = $1", self.org_id)
        self.assertGreater(n_claims, 0, "nenhuma alegação criada")
        self.assertGreater(n_checks, 0, "a conferência da alegação não gravou")
        self.assertGreater(n_ctx, 0, "contexto de equidade não gravou")
        self.assertGreater(n_den, 0, "denominador não gravou")

    def test_exclusao_de_conta_funciona_com_registro_em_todas_as_areas(self):
        r = self.cli.post("/v1/privacy/delete-account", {"password": PASSWORD, "confirm": True})
        self.assertEqual(r.status, 200, r.body)
        self.assertTrue(r.json["deleted"])
        with db_system() as c:
            u = c.one("SELECT email::text AS email, full_name, password_hash, status, mfa_secret_enc"
                      " FROM users WHERE id = $1", self.user_id)
            self.assertIsNotNone(u, "o registro do titular desapareceu — deveria ser anonimizado, não apagado")
            self.assertEqual(u["status"], "deleted")
            self.assertNotEqual(u["email"], self.email, "e-mail não foi substituído")
            self.assertIn("anonimizado.invalid", u["email"])
            self.assertIsNone(u["password_hash"])
            self.assertIsNone(u["mfa_secret_enc"])
            self.assertEqual(u["full_name"], "Titular removido")
            vivas = c.scalar("SELECT count(*) FROM sessions WHERE user_id = $1 AND revoked_at IS NULL",
                             self.user_id)
            self.assertEqual(vivas, 0, "ficou sessão viva depois da exclusão")
            self.assertEqual(c.scalar("SELECT count(*) FROM auth_tokens WHERE user_id = $1", self.user_id), 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM memberships WHERE user_id = $1", self.user_id), 0)
            pedido = c.one("SELECT kind, status FROM privacy_requests WHERE user_id = $1"
                           " ORDER BY created_at DESC LIMIT 1", self.user_id)
            self.assertEqual((pedido or {}).get("kind"), "deletion")
            self.assertEqual((pedido or {}).get("status"), "completed")

    def test_o_que_tem_de_sobreviver_sobrevive(self):
        """Trilha de auditoria, prova de aceite e organização continuam — sem IP nem agente."""
        self.cli.post("/v1/privacy/delete-account", {"password": PASSWORD, "confirm": True})
        with db_system() as c:
            eventos = c.scalar("SELECT count(*) FROM audit_events WHERE actor_user_id = $1", self.user_id)
            self.assertGreater(eventos, 0, "a trilha de auditoria do titular desapareceu")
            aceites = c.query("SELECT ip, user_agent, body_sha256 FROM legal_acceptances WHERE user_id = $1",
                              self.user_id)
            self.assertTrue(aceites, "a prova de aceite desapareceu — é obrigação legal de guarda")
            for a in aceites:
                self.assertIsNone(a["ip"], "IP do aceite não foi limpo")
                self.assertIsNone(a["user_agent"], "agente de usuário do aceite não foi limpo")
                self.assertTrue(a["body_sha256"], "o aceite perdeu o hash do texto — a prova fica inútil")
            org = c.one("SELECT status, contact_email, phone FROM organizations WHERE id = $1", self.org_id)
            self.assertIsNotNone(org, "a organização foi apagada; a política diz que ela é fechada")
            self.assertEqual(org["status"], "closed")
            self.assertIsNone(org["contact_email"])

    def test_o_email_do_titular_nao_sobra_em_nenhuma_coluna_de_texto(self):
        """Varredura de verdade: o endereço não pode restar em nenhuma tabela, nem de relance.

        É o teste que pega o caso que ninguém imagina — o e-mail copiado para uma coluna de texto
        livre (nota, descrição, payload) por um fluxo que não passou pela anonimização.
        """
        self.cli.post("/v1/privacy/delete-account", {"password": PASSWORD, "confirm": True})
        alvo = self.email
        with db_system() as c:
            colunas = c.query(
                "SELECT table_name, string_agg(quote_ident(column_name), ',') AS cols"
                "  FROM information_schema.columns"
                " WHERE table_schema = 'public' AND data_type IN ('text','character varying','citext')"
                "   AND table_name IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public')"
                " GROUP BY table_name ORDER BY table_name")
            # Uma consulta só, em UNION ALL: erro em uma tabela aborta a transação inteira no
            # PostgreSQL, então varrer em laço com try/except esconderia justamente o que importa.
            partes = [f"SELECT {c._lit(linha['table_name']) if hasattr(c, '_lit') else chr(39) + linha['table_name'] + chr(39)}"
                      f" AS tabela, count(*) AS n FROM {linha['table_name']} WHERE "
                      + " OR ".join(f"{col}::text = $1" for col in linha["cols"].split(","))
                      for linha in colunas]
            self.assertGreater(len(partes), 100, "a varredura olhou poucas tabelas — algo filtrou demais")
            rows = c.query(" UNION ALL ".join(partes), alvo)
        achados = [f"{r['tabela']}: {r['n']} linha(s)" for r in rows if r["n"]]
        self.assertEqual(achados, [], "o e-mail do titular excluído sobrou em: " + "; ".join(achados))


class OrganizationNotRemovableTests(unittest.TestCase):
    """A conclusão desta rodada: a plataforma NÃO remove organização — ela fecha.

    A tentativa de remover uma organização com registro em todas as áreas é recusada duas vezes: pela
    guarda legal da evidência (chave NO ACTION) e, retirada a evidência, pela trilha append-only da
    conferência de alegação (gatilho, que não olha papel — nem o proprietário do banco passa).

    Isso não é defeito: é a arquitetura. O que era defeito era a política escrita afirmar cascata onde
    a remoção é impossível, e ninguém ter tentado. O caminho suportado pelo produto é
    POST /v1/privacy/delete-account: fecha a organização e anonimiza o titular.
    """

    @classmethod
    def setUpClass(cls):
        server()
        cls.cli = new_account("osc", compliance="approved")
        grant_premium(cls.cli)
        cls.org_id = cls.cli.org_id
        cls.povoado = AccountDeletionTests._povoar(cls.cli)
        with db_system() as c:
            c.run("INSERT INTO evidences(project_id, org_id, kind, title, occurred_on, created_by)"
                  " VALUES ($1,$2,'report','Comprovante de instalação','2026-02-01',$3)",
                  cls.povoado["project"], cls.org_id, cls.cli.user["id"])

    def test_1_a_guarda_legal_da_evidencia_recusa_a_remocao(self):
        # owner_conn() NÃO é gerenciador de contexto: devolve a conexão direta do dono do banco.
        dono = owner_conn()
        with self.assertRaises(Exception) as erro:
            dono.run("DELETE FROM organizations WHERE id = $1", self.org_id)
        self.assertIn("evidences", str(erro.exception).lower(),
                      "a remoção passou, ou falhou por outro motivo antes da guarda de evidência")

    def test_2_retirada_a_evidencia_a_trilha_append_only_recusa(self):
        """Numerado de propósito: os testes de uma classe rodam em ORDEM ALFABÉTICA e compartilham
        estado, então a sequência precisa estar no nome, não no acaso."""
        dono = owner_conn()
        for tabela in ("evidences", "expenses", "ledger_entries", "conflict_declarations",
                       "signature_revocations"):
            dono.run(f"DELETE FROM {tabela} WHERE org_id = $1", self.org_id)
        with self.assertRaises(Exception) as erro:
            dono.run("DELETE FROM organizations WHERE id = $1", self.org_id)
        texto = str(erro.exception).lower()
        self.assertIn("append-only", texto,
                      f"esperava recusa de trilha append-only; veio: {erro.exception}")
        with db_system() as c:
            self.assertIsNotNone(c.one("SELECT 1 FROM organizations WHERE id = $1", self.org_id),
                                 "a organização foi removida apesar da trilha append-only")

    def test_3_a_politica_declara_que_organizacao_nao_e_removivel(self):
        from impacto.core import retention
        doc = retention.load()
        self.assertIn("append_only", doc["classes"])
        self.assertIn("NÃO REMOVE ORGANIZAÇÃO", doc["effective_class_note"])
        with db_system() as c:
            classes = {i["key"]: i["class"] for i in retention.links(c)}
        self.assertEqual(classes["reputation_snapshots.org_id"], "append_only")
        self.assertEqual(classes["seal_awards.org_id"], "append_only")
        self.assertEqual(classes["responsibility_assignments.org_id"], "append_only")
        # claim_checks e responsibility_decisions não têm org_id: o vínculo é com a alegação e com a
        # designação. A trilha é append-only do mesmo
        # jeito, e é ela que recusa a remoção em cascata — provado em test_2 acima.
        self.assertNotIn("claim_checks.org_id", classes)


class AcceptanceAnonymizationTests(unittest.TestCase):
    """A correção da v0.19.0 no gatilho da prova de aceite, nas duas direções."""

    @classmethod
    def setUpClass(cls):
        server()
        cls.cli = new_account("osc", compliance="approved")
        # Uma SEGUNDA organização é necessária para provar a recusa de transferência: sem ela, o
        # UPDATE não teria para onde apontar e o teste passaria sem testar nada.
        cls.outra_org = new_account("osc").org_id
        from impacto.services import legal as LEGAL
        with db_system() as c:
            doc = c.one("SELECT id::text AS id, doc_key FROM legal_documents"
                        " WHERE status IN ('draft','in_legal_review') ORDER BY doc_key LIMIT 1")
            if doc:
                LEGAL.approve(c, doc_id=doc["id"], reviewed_by="Revisão jurídica do cenário de teste",
                              review_reference="Parecer interno do cenário de aceite")
                cls.doc_key = doc["doc_key"]
        ac = cls.cli.post("/v1/legal/acceptances", {"doc_key": cls.doc_key})
        assert ac.status in (200, 201), ac.body
        with db_system() as c:
            cls.aceite = c.scalar("SELECT id::text FROM legal_acceptances WHERE user_id = $1",
                                  cls.cli.user["id"])

    def test_desvincular_a_organizacao_e_permitido_mesmo_com_ip_preenchido(self):
        """O caso que a primeira versão da migração 0035 ainda quebrava.

        A regra anterior recusava QUALQUER alteração enquanto houvesse IP na linha, então o SET NULL
        da chave falhava justamente na situação normal: organização removida, titular ativo, IP ainda
        registrado. A condição agora é a que a regra sempre quis dizer — só pode APAGAR.
        """
        dono = owner_conn()
        dono.run("UPDATE legal_acceptances SET org_id = NULL WHERE id = $1", self.aceite)
        with db_system() as c:
            linha = c.one("SELECT org_id, body_sha256, user_id FROM legal_acceptances WHERE id = $1",
                          self.aceite)
        self.assertIsNone(linha["org_id"])
        self.assertTrue(linha["body_sha256"], "a prova perdeu o hash do texto aceito")

    def test_transferir_o_aceite_para_outra_organizacao_e_recusado(self):
        outra = self.outra_org
        self.assertIsNotNone(outra, "sem segunda organização o teste não prova nada")
        dono = owner_conn()
        with self.assertRaises(Exception) as erro:
            dono.run("UPDATE legal_acceptances SET org_id = $2 WHERE id = $1", self.aceite, outra)
        self.assertIn("trocado por outra organização", str(erro.exception))

    def test_trocar_o_ip_continua_recusado(self):
        dono = owner_conn()
        with self.assertRaises(Exception) as erro:
            dono.run("UPDATE legal_acceptances SET ip = '10.0.0.1' WHERE id = $1", self.aceite)
        self.assertIn("só pode ser APAGADO", str(erro.exception))

    def test_a_prova_em_si_continua_intocavel(self):
        dono = owner_conn()
        for coluna, valor in (("body_sha256", "0" * 64), ("version", 99), ("source", "api")):
            with self.assertRaises(Exception, msg=f"{coluna} pôde ser alterado") as erro:
                dono.run(f"UPDATE legal_acceptances SET {coluna} = $2 WHERE id = $1",
                         self.aceite, valor)
            self.assertIn("append-only", str(erro.exception))
