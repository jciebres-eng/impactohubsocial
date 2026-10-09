"""v0.32.0 — desativar as contas de demonstração de um banco de produção sem tocar no que é real.

Decisão do responsável (09/10/2026): as 15 contas `@demo.impacto.local` que estão no banco de produção
são DESATIVADAS. `scripts/demo_accounts.py` faz o que a tela de administração faz, e este teste prova:
  - listar não escreve;
  - desativar: toda conta de demonstração fica `disabled`, a sessão aberta dela deixa de valer NA HORA,
    o login é recusado, as organizações só de demonstração ficam `suspended`, cada mudança vai para a
    trilha de auditoria;
  - a conta real (inclusive a de administração, que divide a organização da plataforma com o
    administrador de demonstração) e a organização da plataforma não são tocadas;
  - reativar desfaz;
  - sem a frase de confirmação, o script recusa.
"""
import importlib.util
import os
import subprocess
import sys
import unittest

from tests.support import OWNER_DSN, PASSWORD, ROOT, Client, make_admin, server

SCRIPT = ROOT / "scripts" / "demo_accounts.py"


def _mod():
    spec = importlib.util.spec_from_file_location("demo_accounts", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)  # type: ignore[union-attr]
    return m


class DemoAccountsInProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        st = server()
        cls.base, cls.state = st["base"], st["state"]
        os.environ["DEMO_PASSWORD"] = PASSWORD
        from impacto import seed_dev
        r = seed_dev.seed(cls.state)
        assert r["status"] in ("seeded", "already_seeded"), r
        cls.demo_emails = sorted(seed_dev.DEMO_EMAILS.values())
        cls.m = _mod()
        from impacto.db.pq import Connection
        cls.Connection = Connection
        # Uma conta REAL de administração (fora do domínio de demonstração).
        cls.admin, _ = make_admin()

    def _c(self):
        return self.Connection(OWNER_DSN)

    def _login(self, email: str):
        c = Client(self.base)
        return c.post("/v1/auth/login", {"email": email, "password": PASSWORD})

    def test_disable_is_complete_reversible_and_never_touches_real_accounts(self):
        c = self._c()
        try:
            antes = self.m.listar(c)
            # O seed atual cria as 15 personas + "coletivo"; a produção foi semeada por uma versão anterior (15).
            # A verdade é o banco: tudo o que está no domínio de demonstração.
            n = len(antes["contas_demo"])
            self.assertGreaterEqual(n, len(self.demo_emails))
            self.assertTrue(all(u["status"] == "active" for u in antes["contas_demo"]))
            self.assertGreater(antes["contas_reais"], 0)
            orgs = antes["orgs_so_demo"]
            self.assertTrue(orgs, "o seed cria organizações só de demonstração")
            self.assertFalse([o for o in orgs if o["kind"] == "platform"], "a organização da plataforma nunca entra")
            plat_antes = c.scalar("SELECT status FROM organizations WHERE kind = 'platform' LIMIT 1")
            audit_antes = c.scalar("SELECT count(*) FROM audit_events WHERE action IN ('admin.user_status','admin.org_status')")
        finally:
            c.close()

        # Uma sessão de demonstração aberta ANTES da desativação.
        osc = Client(self.base)
        r = osc.post("/v1/auth/login", {"email": "osc@demo.impacto.local", "password": PASSWORD})
        self.assertEqual(r.status, 200, r.body)
        self.assertEqual(osc.get("/v1/me").status, 200)

        c = self._c()
        try:
            c.execute_script("BEGIN;")
            feito = self.m.desativar(c)
            c.execute_script("COMMIT;")
            self.assertEqual(feito["contas_desativadas"], n)
            self.assertEqual(feito["orgs_suspensas"], len(orgs))
            publicados = sum(v for v in antes["conteudo_publico_das_orgs_demo"].values())
            self.assertGreaterEqual(publicados, 1, "o seed publica conteúdo; sem isso o teste passaria no vazio")
            self.assertEqual(feito["conteudo_tirado_do_ar"], publicados)
            depois = self.m.listar(c)
            self.assertTrue(all(u["status"] == "disabled" for u in depois["contas_demo"]))
            self.assertEqual(depois["sessoes_abertas_demo"], 0)
            self.assertTrue(all(o["status"] == "suspended" for o in depois["orgs_so_demo"]))
            self.assertEqual(sum(depois["conteudo_publico_das_orgs_demo"].values()), 0, "nenhum conteúdo fictício fica público")
            self.assertEqual(c.scalar("SELECT status FROM organizations WHERE kind = 'platform' LIMIT 1"), plat_antes)
            self.assertEqual(c.scalar("SELECT count(*) FROM users WHERE email::text NOT LIKE '%@demo.impacto.local' AND status <> 'active'"
                                      " AND id IN (SELECT user_id FROM memberships m JOIN organizations o ON o.id = m.org_id WHERE o.kind = 'platform')"), 0)
            self.assertEqual(c.scalar("SELECT count(*) FROM audit_events WHERE action IN ('admin.user_status','admin.org_status')"),
                             audit_antes + n + len(orgs))
            # repetir é inofensivo: nada mais a desativar
            c.execute_script("BEGIN;")
            de_novo = self.m.desativar(c)
            c.execute_script("COMMIT;")
            self.assertEqual(de_novo, {"contas_desativadas": 0, "orgs_suspensas": 0, "conteudo_tirado_do_ar": 0})
        finally:
            c.close()

        self.assertEqual(osc.get("/v1/me").status, 401, "a sessão aberta deixa de valer na hora")
        self.assertNotEqual(self._login("admin@demo.impacto.local").status, 200, "o administrador de demonstração não entra")
        self.assertEqual(self.admin.get("/v1/me").status, 200, "a conta real de administração continua funcionando")

        c = self._c()
        try:
            c.execute_script("BEGIN;")
            volta = self.m.reativar(c)
            c.execute_script("COMMIT;")
            self.assertEqual(volta["contas_reativadas"], n)
            self.assertEqual(volta["conteudo_devolvido"], publicados)
            fim = self.m.listar(c)
            self.assertTrue(all(u["status"] == "active" for u in fim["contas_demo"]))
            self.assertTrue(all(o["status"] == "active" for o in fim["orgs_so_demo"]))
            self.assertEqual(sum(fim["conteudo_publico_das_orgs_demo"].values()), publicados, "reativar devolve o conteúdo")
        finally:
            c.close()
        self.assertEqual(self._login("osc@demo.impacto.local").status, 200, "reativar devolve o acesso")

    def test_listing_is_read_only_and_writes_need_the_exact_phrase(self):
        env = {**os.environ, "DATABASE_URL": "postgresql:///" + OWNER_DSN.split("dbname=")[1].split()[0]}
        # A URL acima não carrega usuário/senha; o libpq recebe o resto pelo ambiente.
        host = OWNER_DSN.split("host=")[1].split()[0]
        port = OWNER_DSN.split("port=")[1].split()[0]
        env.update(PGHOST=host, PGPORT=port, PGUSER="impacto_owner", PGPASSWORD=OWNER_DSN.split("password=")[1].split()[0])
        for modo, frase in (("desativar", ""), ("desativar", "desativar"), ("reativar", "DESATIVAR CONTAS DEMO")):
            r = subprocess.run([sys.executable, str(SCRIPT), modo], env={**env, "CONFIRMACAO": frase}, capture_output=True, text=True)
            self.assertEqual(r.returncode, 3, f"{modo} sem a frase certa tem de recusar: {r.stderr}")
        r = subprocess.run([sys.executable, str(SCRIPT), "listar"], env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("contas_demo", r.stdout)
        self.assertNotIn(PASSWORD, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
