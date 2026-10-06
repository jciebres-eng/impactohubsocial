"""v0.20.0 — a prova do aceite passa a existir (ETAPA 1).

O DEFEITO. A tela de cadastro mostrava "Li e aceito os Termos de uso e a Política de privacidade",
com links para o texto — e o texto saía com o cabeçalho `X-Legal-Status: draft`, porque as onze
minutas nunca foram aprovadas. O backend conferia um booleano e gravava `consents` com uma string de
versão vinda do arquivo de configuração. A prova que serve a um questionamento jurídico — documento,
versão e HASH do texto, em `legal_acceptances` — nunca era escrita pelo cadastro.

Ou seja: publicando assim, cada pessoa aceitaria uma minuta e não sobraria prova de QUAL texto foi
aceito. A infraestrutura da prova existia inteira (tabela append-only, gatilho que recusa aceite de
minuta, sobrevivência à exclusão de conta sem o IP, saída na portabilidade LGPD). Faltava ligar o fio.

A CORREÇÃO TEM DUAS PARTES, e as duas são testadas aqui:
1. o cadastro registra o aceite de todo documento VIGENTE que exige aceite;
2. em staging/produção, o cadastro é RECUSADO enquanto houver documento que exige aceite e não foi
   aprovado — a trava vira regra do produto, em vez de um esquecimento silencioso.
"""
from __future__ import annotations

import unittest
import uuid

from tests.support import PASSWORD, Client, db_system, new_account, next_cnpj, server


def _aprovar_um_documento(doc_key: str | None = None) -> dict:
    """Aprova uma minuta pelo caminho real do serviço (que exige quem revisou e sob qual referência)."""
    from impacto.services import legal as LEGAL
    with db_system() as c:
        doc = c.one("SELECT id::text AS id, doc_key FROM legal_documents"
                    " WHERE status IN ('draft','in_legal_review')"
                    "   AND ($1::text IS NULL OR doc_key = $1) ORDER BY doc_key LIMIT 1", doc_key)
        assert doc, "não há minuta para aprovar no cenário"
        return LEGAL.approve(c, doc_id=doc["id"], reviewed_by="Revisão jurídica do cenário de teste",
                             review_reference="Parecer interno do cenário de aceite no cadastro")


class SignupRecordsProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()
        # Dos onze documentos, apenas `terms_of_use` e `privacy_policy` exigem aceite. Aprovar o
        # alfabeticamente primeiro (`b2b`, público `company`) não produziria aceite nenhum para uma
        # OSC — e o teste passaria a medir a ausência em vez do mecanismo.
        cls.doc = _aprovar_um_documento("terms_of_use")

    def _registrar(self) -> str:
        c = Client()
        em = f"aceite-{uuid.uuid4().hex[:10]}@teste.org"
        r = c.post("/v1/auth/register", {
            "email": em, "password": PASSWORD, "full_name": "Pessoa do aceite", "accept_terms": True,
            "organization": {"kind": "osc", "legal_name": f"OSC Aceite {uuid.uuid4().hex[:6]}",
                             "cnpj": next_cnpj(), "uf": "MT"}})
        self.assertEqual(r.status, 202, r.body)
        return em

    def test_o_cadastro_grava_a_prova_com_o_hash_do_texto(self):
        em = self._registrar()
        with db_system() as c:
            uid = c.scalar("SELECT id::text FROM users WHERE email = $1", em)
            linhas = c.query("SELECT doc_key, version, body_sha256, source FROM legal_acceptances"
                             " WHERE user_id = $1", uid)
        self.assertTrue(linhas, "o cadastro não registrou aceite nenhum do documento vigente")
        por_chave = {r["doc_key"]: r for r in linhas}
        self.assertIn(self.doc["doc_key"], por_chave, "o documento aprovado não foi aceito no cadastro")
        prova = por_chave[self.doc["doc_key"]]
        self.assertEqual(len(prova["body_sha256"]), 64, "a prova não carrega o hash do texto aceito")
        self.assertEqual(prova["source"], "signup",
                         "a origem do aceite não distingue o cadastro das demais telas")

    def test_a_prova_aponta_para_a_versao_aprovada_e_nao_para_uma_string_de_configuracao(self):
        em = self._registrar()
        with db_system() as c:
            uid = c.scalar("SELECT id::text FROM users WHERE email = $1", em)
            prova = c.one("SELECT a.version, a.body_sha256, d.status,"
                          " d.body_sha256 AS doc_sha FROM legal_acceptances a"
                          " JOIN legal_documents d ON d.id = a.document_id"
                          " WHERE a.user_id = $1 AND a.doc_key = $2", uid, self.doc["doc_key"])
        self.assertEqual(prova["status"], "approved", "aceite registrado sobre documento não aprovado")
        self.assertEqual(prova["body_sha256"], prova["doc_sha"],
                         "o hash guardado no aceite não é o hash do texto do documento")

    def test_a_trilha_de_auditoria_registra_o_que_foi_aceito(self):
        em = self._registrar()
        with db_system() as c:
            uid = c.scalar("SELECT id::text FROM users WHERE email = $1", em)
            ev = c.one("SELECT payload FROM audit_events WHERE actor_user_id = $1"
                       " AND action = 'user.registered' ORDER BY id DESC LIMIT 1", uid)
        self.assertIsNotNone(ev)
        self.assertIn(self.doc["doc_key"], ev["payload"].get("legal_acceptances") or [],
                      "a auditoria do cadastro não diz qual documento foi aceito")

    def test_o_aceite_do_cadastro_nao_duplica_quando_a_pessoa_aceita_de_novo_na_tela(self):
        em = self._registrar()
        with db_system() as c:
            uid = c.scalar("SELECT id::text FROM users WHERE email = $1", em)
            antes = c.scalar("SELECT count(*) FROM legal_acceptances WHERE user_id = $1", uid)
            from impacto.services import legal as LEGAL
            LEGAL.accept(c, user_id=uid, org_id=None, key=self.doc["doc_key"], source="web")
            depois = c.scalar("SELECT count(*) FROM legal_acceptances WHERE user_id = $1", uid)
        self.assertEqual(antes, depois, "aceitar de novo criou uma segunda prova para o mesmo documento")


class SignupGateTests(unittest.TestCase):
    """O portão: em staging/produção não se coleta aceite de minuta."""

    def test_em_ambiente_endurecido_o_cadastro_e_recusado_enquanto_houver_minuta(self):
        from dataclasses import replace

        from impacto.services import auth as AUTH
        st = server()
        from impacto.services import legal as LEGAL
        with db_system() as c:
            pendentes = LEGAL.blockers(c)
        self.assertTrue(pendentes, "o cenário precisa de pelo menos uma minuta que exige aceite")

        class _CtxEndurecido:
            """O mesmo caminho do produto, com as configurações de produção."""

            def __init__(self, app):
                self.app = app
                self.settings = replace(app.settings, env="production")
                self.ip, self.request_id, self.user_agent = "127.0.0.1", "teste", "teste"

            def system_tx(self, **_kw):
                from impacto.db.pool import DbContext
                return self.app.pool.tx(DbContext(system=True))

        class _Org:
            kind, legal_name, trade_name, cnpj, uf, city = "osc", "OSC do portão", None, None, "MT", None
            legal_nature_code = None

        class _Body:
            email = f"portao-{uuid.uuid4().hex[:8]}@teste.org"
            password = PASSWORD
            full_name = "Pessoa do portão"
            accept_terms = True
            organization = _Org()

        ctx = _CtxEndurecido(st["state"])
        with self.assertRaises(Exception) as erro:
            AUTH.register(ctx, _Body())
        texto = f"{getattr(erro.exception, 'code', '')} {erro.exception}"
        self.assertIn("legal_documents_not_published", texto)

    def test_em_desenvolvimento_o_cadastro_segue_e_a_plataforma_diz_o_motivo(self):
        """Desenvolver antes de o jurídico aprovar é legítimo; esconder isso não é."""
        cli = new_account("osc")
        self.assertTrue(cli.org_id)
        r = Client().get("/v1/legal/registry")
        self.assertEqual(r.status, 200, r.body)
        self.assertTrue(r.json["blocking_product"],
                        "o registro legal não declara mais nenhuma pendência — confira o cenário")
        self.assertIn("pendência jurídica", r.json["note"])

    def test_a_tela_de_cadastro_mostra_a_situacao_dos_documentos(self):
        from tests.support import ROOT
        tela = (ROOT / "web" / "src" / "pages" / "public.tsx").read_text(encoding="utf-8")
        self.assertIn("LegalStatus", tela, "a tela de cadastro não consulta a situação dos documentos")
        self.assertIn("/v1/legal/registry", tela)
        self.assertIn("blocking_product", tela)
