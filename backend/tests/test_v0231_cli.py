"""Os comandos operacionais — rodados de verdade, como subprocesso.

POR QUE ESTE ARQUIVO EXISTE

`python -m impacto.cli create-admin` **nunca funcionou num banco limpo**. Falhava com
`inconsistent types deduced for parameter $2`, e a transação inteira era desfeita: sem organização
da plataforma, sem usuário, sem membership. É o PRIMEIRO comando que o operador roda depois de
implantar — sem ele não há administrador, sem administrador não há MFA, não há aprovação das minutas
jurídicas e não há painel.

O defeito sobreviveu a 2.193 testes por uma razão simples: **nenhum teste rodava o CLI.** Em
desenvolvimento usa-se o administrador que vem do `seed-demo`, que entra por outro caminho. Uma
auditoria independente o encontrou executando o produto em configuração de produção.

A lição não é "faltava um teste". É que código que só roda na mão, no dia da implantação, é código
que ninguém testa — e é justamente o que não pode falhar nesse dia.

COMO ESTE ARQUIVO TESTA

Por SUBPROCESSO, com o mesmo comando que o operador digita. Importar a função e chamá-la testaria o
Python; o que precisa funcionar é a linha de comando inteira, com `argparse`, leitura de senha pelo
stdin, carregamento de configuração e pool de banco.
"""
from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
import unittest

from tests.support import APP_DSN, ROOT, Client, db_system, owner_conn, server


#: `legal_documents_summary_check` também tem piso de tamanho.
RESUMO = ("Resumo da minuta de teste usada pelos comandos operacionais de aprovação "
          "jurídica, sem valor legal.")

#: `legal_documents_body_md_check` exige mais de 200 caracteres: minuta curta demais não é minuta.
CORPO = ("# Minuta de teste do CLI\n\nTexto de minuta criado exclusivamente para exercitar os comandos operacionais de aprovação jurídica. Não tem valor legal algum e existe só para que o teste tenha um documento proprio, sem tocar nas minutas reais do produto.")


@contextlib.contextmanager
def _dono():
    """Conexão como DONO do banco. `owner_conn()` é autocommit e não é gerenciador de contexto."""
    c = owner_conn()
    try:
        yield c
    finally:
        c.close()


def _cli(*args: str, senha: str = "Senha-Do-Admin-Forte-2026") -> subprocess.CompletedProcess:
    """Roda o CLI como o operador roda: processo próprio, senha pelo stdin, nunca por argumento."""
    ambiente = {
        **os.environ,
        "DATABASE_URL": APP_DSN,
        "SECRET_KEY": "chave_de_teste_com_mais_de_32_caracteres_aqui",
        "IMPACTO_ENV": "test",
    }
    return subprocess.run([sys.executable, "-m", "impacto.cli", *args],
                          input=senha + "\n", capture_output=True, text=True,
                          cwd=ROOT / "backend", env=ambiente, timeout=180)


class CreateAdminActuallyCreatesAnAdministratorTests(unittest.TestCase):
    """O comando que cria o primeiro administrador. Era o que estava quebrado."""

    EMAIL = "primeiro.admin@teste.local"

    @classmethod
    def setUpClass(cls):
        server()
        cls.r = _cli("create-admin", "--email", cls.EMAIL, "--name", "Primeira Administradora")

    def test_the_command_succeeds(self):
        self.assertEqual(self.r.returncode, 0,
                         f"create-admin falhou:\nstdout: {self.r.stdout}\nstderr: {self.r.stderr[-1500:]}")
        self.assertIn("Administrador criado", self.r.stdout)

    def test_it_creates_every_row_the_administrator_needs(self):
        """A transação é tudo ou nada: se uma linha falta, o comando mentiu ao dizer que criou."""
        with db_system() as c:
            u = c.one("SELECT id::text AS id, is_platform_admin, email_verified_at IS NOT NULL AS verificado"
                      " FROM users WHERE email = $1", self.EMAIL)
            self.assertIsNotNone(u, "o usuário não existe")
            self.assertTrue(u["is_platform_admin"], "criado sem a marca de administrador")
            self.assertTrue(u["verificado"],
                            "e-mail não verificado: o administrador não conseguiria entrar sem receber e-mail, "
                            "e o provedor de e-mail pode ainda nem estar configurado")
            plataforma = c.one("SELECT id::text AS id FROM organizations WHERE kind = 'platform'")
            self.assertIsNotNone(plataforma, "não há organização da plataforma")
            papel = c.scalar("SELECT role FROM memberships WHERE user_id = $1 AND org_id = $2",
                             u["id"], plataforma["id"])
            self.assertEqual(papel, "owner", "o administrador não é dono da organização da plataforma")

    def test_it_leaves_an_audit_trail(self):
        """Era exatamente esta linha que quebrava: `$2` servia um uuid e um text na mesma instrução."""
        with db_system() as c:
            n = c.scalar("SELECT count(*) FROM audit_events WHERE action = 'admin.created'")
        self.assertGreaterEqual(n, 1, "criar administrador não deixou rastro de auditoria")

    def test_running_it_twice_is_safe(self):
        """O operador vai rodar de novo — por engano, ou para promover alguém que já existe.

        v0.35.0 (auditoria, AUTH-04): a segunda execução SEM `--promote-existing` é recusada com instrução clara (antes
        devolvia 0 e promovia a conta mantendo a senha antiga — o caminho de quem pré-cadastra o e-mail do administrador).
        Com a opção, promove trocando a senha. Em nenhum caso duplica o usuário."""
        r = _cli("create-admin", "--email", self.EMAIL, "--name", "Primeira Administradora")
        self.assertEqual(r.returncode, 1, f"segunda execução sem --promote-existing foi aceita: {r.stdout}")
        self.assertIn("--promote-existing", r.stderr)
        r = _cli("create-admin", "--email", self.EMAIL, "--name", "Primeira Administradora", "--promote-existing")
        self.assertEqual(r.returncode, 0, f"promoção explícita falhou: {r.stderr[-800:]}")
        with db_system() as c:
            self.assertEqual(c.scalar("SELECT count(*) FROM users WHERE email = $1", self.EMAIL), 1,
                             "a segunda execução duplicou o usuário")

    def test_the_new_administrator_can_log_in_but_is_stopped_by_mfa(self):
        """Prova a ponta útil: o administrador entra, e a área administrativa exige MFA — que é o
        que o próprio comando promete na mensagem final."""
        c = Client()
        r = c.login(self.EMAIL, "Senha-Do-Admin-Forte-2026")
        self.assertEqual(r.status, 200, r.body)
        adm = c.get("/v1/admin/legal/acceptances")
        self.assertEqual(adm.status, 403, f"a área administrativa não exigiu MFA: {adm.body}")
        self.assertIn("mfa", str(adm.json).lower())


class TheLegalGateHasAWayOutThatIsNotPsqlTests(unittest.TestCase):
    """Em produção o cadastro responde 503 até as minutas serem aprovadas. Era preciso `psql`.

    `POST /v1/admin/legal/documents/{doc_id}/approve` exige o `doc_id`, e `legal_overview()` — que
    alimenta a única rota de panorama — devolve doc_key, título, versão e situação, mas **não o id**.
    Nenhuma rota, tela ou documento o expunha. O operador só saía do 503 abrindo o banco na mão, no
    dia da publicação, que é quando ninguém quer improvisar com SQL.

    `legal-list` e `legal-approve` fecham isso SEM afrouxar nada: chamam a mesma
    `services.legal.approve`, que exige revisor nomeado e referência da revisão, e o CHECK do banco
    exige também.
    """

    @classmethod
    def setUpClass(cls):
        server()

    def test_listing_shows_the_id_and_says_what_is_blocking(self):
        r = _cli("legal-list")
        self.assertEqual(r.returncode, 0, r.stderr[-800:])
        self.assertIn("terms_of_use", r.stdout)
        self.assertIn("privacy_policy", r.stdout)
        # O id tem de aparecer: é a razão de o comando existir.
        self.assertRegex(r.stdout, r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                         "a listagem não mostra o id, que é o que falta para aprovar")

    def test_approving_requires_a_named_reviewer(self):
        """Não é atalho para aprovar sem revisão. Sem revisor, o comando nem roda."""
        r = _cli("legal-approve", "--doc-key", "terms_of_use")
        self.assertNotEqual(r.returncode, 0, "aprovou sem revisor nomeado")
        self.assertIn("reviewed-by", (r.stderr + r.stdout))

    def test_an_unknown_document_fails_with_a_useful_message(self):
        r = _cli("legal-approve", "--doc-key", "documento_que_nao_existe",
                 "--reviewed-by", "Fulana, OAB/MT 1234", "--review-reference", "Parecer 1/2026")
        self.assertEqual(r.returncode, 2)
        self.assertIn("legal-list", r.stderr, "a mensagem não diz como descobrir as chaves válidas")

    def test_approving_a_draft_works_and_leaves_a_trail(self):
        """Usa uma minuta PRÓPRIA, porque o estado das reais é compartilhado — e irreversível.

        A primeira versão forçava `terms_of_use` e `privacy_policy` de volta a rascunho para testar
        a transição. O banco recusou:

            CheckViolation: situação de documento legal não volta: approved -> draft

        O produto está certo, e a trava é boa: documento jurídico aprovado não se desaprova por
        UPDATE. Quem precisa mudar publica versão nova. Então o teste para de brigar com a trava e
        cria a própria minuta, que não bloqueia nada (`requires_acceptance = false`) e não atrapalha
        teste nenhum.
        """
        chave = "minuta_de_teste_do_cli"
        # Pelo papel DONO: `impacto_app` não tem INSERT em `legal_documents`, e está certo — minuta
        # jurídica entra pelo migrador, não pela aplicação. O arranjo do teste respeita isso.
        with _dono() as c:
            c.run("INSERT INTO legal_documents(doc_key, version, title, summary, source_path,"
                  " body_md, body_sha256, audience, requires_acceptance, status, software_version)"
                  " VALUES ($1,1,'Minuta de teste do CLI',$3,'docs/legal/teste.md',"
                  " $2,'0'::text,'all',false,'draft','0.23.0')"
                  " ON CONFLICT DO NOTHING", chave, CORPO, RESUMO)
            self.addCleanup(lambda: self._remover(chave))

        listagem = _cli("legal-list")
        self.assertEqual(listagem.returncode, 0, listagem.stderr[-500:])
        self.assertIn(chave, listagem.stdout, "a minuta criada não aparece na listagem")

        r = _cli("legal-approve", "--doc-key", chave,
                 "--reviewed-by", "Fulana de Tal, OAB/MT 1234",
                 "--review-reference", "Parecer 12/2026")
        self.assertEqual(r.returncode, 0, f"aprovação falhou: {r.stderr[-800:]}")
        self.assertIn("Aprovado", r.stdout)

        with db_system() as c:
            d = c.one("SELECT status, reviewed_by, review_reference, effective_from"
                      " FROM legal_documents WHERE doc_key = $1", chave)
        self.assertEqual(d["status"], "approved")
        self.assertIn("OAB", d["reviewed_by"], "não registrou quem assumiu a revisão")
        self.assertTrue(d["review_reference"], "não registrou a referência da revisão")
        self.assertIsNotNone(d["effective_from"], "aprovou sem data de vigência")

        with db_system() as c:
            ev = c.query("SELECT payload FROM audit_events WHERE action = 'legal.approved'"
                         " ORDER BY at DESC LIMIT 1")
        self.assertTrue(ev, "a aprovação pelo CLI não deixou rastro de auditoria")
        self.assertIn("Fulana", json.dumps(ev[0]["payload"], ensure_ascii=False))

    def test_approving_something_already_approved_is_refused_with_a_clear_message(self):
        """O operador vai rodar duas vezes. A recusa precisa dizer por quê, não só falhar."""
        chave = "minuta_de_teste_ja_aprovada"
        with _dono() as c:
            c.run("INSERT INTO legal_documents(doc_key, version, title, summary, source_path,"
                  " body_md, body_sha256, audience, requires_acceptance, status, reviewed_by,"
                  " review_reference, reviewed_at, effective_from, software_version)"
                  " VALUES ($1,1,'Minuta já aprovada',$3,'docs/legal/t2.md',$2,'0'::text,"
                  " 'all',false,'approved','Alguém','Ref',now(),current_date,'0.23.0')"
                  " ON CONFLICT DO NOTHING", chave, CORPO, RESUMO)
            self.addCleanup(lambda: self._remover(chave))
        r = _cli("legal-approve", "--doc-key", chave, "--reviewed-by", "Outra Pessoa",
                 "--review-reference", "Parecer 2/2026")
        self.assertEqual(r.returncode, 2)
        self.assertIn("minuta", r.stderr.lower(),
                      f"a mensagem não explica por que recusou: {r.stderr}")

    def test_the_listing_agrees_with_the_database_about_what_is_blocking(self):
        """A listagem é o que o operador lê para decidir. Ela não pode divergir do banco."""
        r = _cli("legal-list")
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        with db_system() as c:
            bloqueando = {x["doc_key"] for x in c.query(
                "SELECT doc_key FROM legal_overview() WHERE blocks_product")}
        if bloqueando:
            self.assertIn("BLOQUEANDO O PRODUTO", r.stdout,
                          f"o banco diz que {bloqueando} bloqueia e a listagem não avisa")
            for k in bloqueando:
                self.assertIn(k, r.stdout)
        else:
            self.assertIn("Nenhum documento bloqueando", r.stdout,
                          "nada bloqueia no banco e a listagem diz o contrário")

    @staticmethod
    def _remover(doc_key: str):
        with _dono() as c:
            c.run("DELETE FROM legal_documents WHERE doc_key = $1", doc_key)


class GenSecretsProducesKeysTheProductAcceptsTests(unittest.TestCase):
    """Chave gerada que a aplicação recusa é pior que nenhuma: o operador descobre no boot."""

    def test_the_generated_keys_are_accepted_by_the_code_that_uses_them(self):
        r = _cli("gen-secrets")
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        valores = dict(l.split("=", 1) for l in r.stdout.strip().splitlines() if "=" in l)
        for nome in ("SECRET_KEY", "VOUCHER_HMAC_KEY", "FIELD_ENCRYPTION_KEY", "METRICS_TOKEN"):
            with self.subTest(nome):
                self.assertIn(nome, valores)
                self.assertGreaterEqual(len(valores[nome]), 32,
                                        f"{nome} tem menos de 32 caracteres e a validação de "
                                        "produção vai recusar")
        # A chave de cifra de campo é Fernet: tem de cifrar e decifrar de verdade.
        from impacto.security.crypto import FieldCipher
        cifra = FieldCipher(valores["FIELD_ENCRYPTION_KEY"])
        self.assertEqual(cifra.decrypt(cifra.encrypt("segredo")), "segredo")
