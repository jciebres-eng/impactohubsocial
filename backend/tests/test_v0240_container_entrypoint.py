"""O entrypoint do contêiner, executado de verdade — sem Docker, que este ambiente não tem.

`backend/start_container.sh` é o que roda quando a imagem sobe. Aqui ele roda como processo, contra
um banco LIMPO criado pelo usuário administrativo (como num PostgreSQL gerenciado: as migrações
correm como administrador e a aplicação conecta como `impacto_app`). O que se prova:

  - as 63 migrações aplicam num banco cujo dono não é `impacto_owner`;
  - o servidor sobe e `/readyz` responde 200 com banco ok;
  - a aplicação está conectada como `impacto_app`, não como administrador;
  - `IMPACTO_SEED_DEMO=true` com `IMPACTO_ENV=development` semeia, e a conta de demonstração entra;
  - `IMPACTO_APP_PASSWORD` ausente derruba o script antes de qualquer coisa.

O que NÃO se prova: a construção da imagem (precisa de daemon Docker) e o comportamento com pgcrypto
em `extensions` (precisa de banco gerenciado). Os dois estão nomeados em docs/PUBLICACAO.md.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
import unittest
import urllib.error
import urllib.request

from tests.support import ADMIN_URL, APP_PW, ROOT, _psql

SCRIPT = ROOT / "backend" / "start_container.sh"


def _psql_em(db: str, sql: str) -> str:
    """psql apontado para o banco do cenário (URL + `-d` não convivem no psql)."""
    url = ADMIN_URL.rsplit("/", 1)[0] + "/" + db
    return subprocess.run(["psql", url, "-v", "ON_ERROR_STOP=1", "-q", "-tA", "-c", sql],
                          check=True, capture_output=True, text=True).stdout


class TheContainerEntrypointBringsTheProductUpOnACleanDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = f"impacto_entry_{os.getpid()}"
        # A senha do processo (support.APP_PW), nunca uma nova: o papel é da instância, e trocar a
        # senha dele derrubava, no CI, todo teste que rodasse depois deste.
        cls.app_pw = APP_PW
        _psql("-c", f'DROP DATABASE IF EXISTS "{cls.db}" WITH (FORCE)')
        _psql("-c", f'CREATE DATABASE "{cls.db}"')
        # O papel é da instância (cluster), não do banco: o harness já o criou com outra senha, e o
        # bootstrap do script nunca altera senha de papel existente — por desenho. A senha é alinhada
        # aqui, como o operador faria uma vez no banco gerenciado.
        _psql("-c", f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='impacto_app') THEN"
                    f" CREATE ROLE impacto_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT; END IF; END $$;"
                    f" ALTER ROLE impacto_app PASSWORD '{cls.app_pw}';")
        admin = ADMIN_URL.rsplit("/", 1)[0] + "/" + cls.db
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            cls.port = s.getsockname()[1]
        cls.env = {
            **{k: v for k, v in os.environ.items() if not k.startswith("IMPACTO_")},
            "DATABASE_URL": admin, "IMPACTO_APP_PASSWORD": cls.app_pw, "IMPACTO_BOOTSTRAP_EXTERNAL": "true",
            "IMPACTO_ENV": "development", "IMPACTO_SEED_DEMO": "true", "DEMO_PASSWORD": "Senha-Entry-Forte-2026",
            "PORT": str(cls.port), "WEB_CONCURRENCY": "1",
            "SECRET_KEY": "entry-secret-key-" + "x" * 32, "VOUCHER_HMAC_KEY": "entry-voucher-" + "y" * 32,
            "STORAGE_LOCAL_DIR": str(ROOT / "backend" / ".tmp_entry_storage"), "PUBLIC_BASE_URL": f"http://127.0.0.1:{cls.port}",
            "COOKIE_SECURE": "false", "BILLING_PROVIDER": "sandbox", "AI_PROVIDER": "local", "MAIL_PROVIDER": "console",
            "LOG_LEVEL": "ERROR", "PASSWORD_SCRYPT_N": "16384", "RATE_LIMIT_MULTIPLIER": "1000", "ALLOW_UNSCANNED_DOWNLOADS": "true",
        }
        cls.proc = subprocess.Popen(["sh", str(SCRIPT)], cwd=ROOT / "backend", env=cls.env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.saida = ""
        pronto = False
        for _ in range(240):
            if cls.proc.poll() is not None:
                break
            try:
                with urllib.request.urlopen(cls.base + "/readyz", timeout=2) as r:
                    if r.status == 200:
                        pronto = True
                        break
            except (urllib.error.URLError, ConnectionError, OSError):
                time.sleep(0.5)
        if not pronto:
            cls.proc.kill()
            cls.saida = cls.proc.communicate(timeout=10)[0]
            raise AssertionError("o entrypoint não deixou o servidor pronto:\n" + cls.saida[-3000:])

    @classmethod
    def tearDownClass(cls):
        if cls.proc.poll() is None:
            cls.proc.terminate()
            try:
                cls.saida = cls.proc.communicate(timeout=15)[0]
            except subprocess.TimeoutExpired:
                cls.proc.kill()
        _psql("-c", f'DROP DATABASE IF EXISTS "{cls.db}" WITH (FORCE)')

    def _json(self, method, path, body=None, token=None):
        req = urllib.request.Request(self.base + path, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Content-Type": "application/json", "X-Auth-Mode": "token",
                                              **({"Authorization": "Bearer " + token} if token else {})})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_ready_and_the_new_public_config_route(self):
        s, d = self._json("GET", "/readyz")
        self.assertEqual((s, d.get("database")), (200, "ok"), d)
        s, d = self._json("GET", "/v1/meta/config")
        # Rota crua de `app.py`, não do registro `@route` — por isso o cruzamento da v0.23.1 não a via.
        self.assertEqual(s, 200)
        self.assertIs(d.get("sso_enabled"), False, d)
        self.assertEqual(d.get("env"), "development")
        self.assertNotIn("oidc", json.dumps(d).lower(), "nenhum identificador de cliente sai por aqui")

    def test_the_application_runs_as_impacto_app_not_as_the_administrator(self):
        quem = _psql_em(self.db, "SELECT DISTINCT usename FROM pg_stat_activity WHERE datname = current_database()"
                                 " AND application_name <> 'psql' AND usename IS NOT NULL")
        usuarios = {u for u in quem.split() if u}
        self.assertIn("impacto_app", usuarios, usuarios)
        # A conexão administrativa serviu só às migrações e já foi encerrada: o servidor em pé não a usa.
        self.assertNotIn("postgres", usuarios, f"o servidor ainda conecta como administrador: {usuarios}")

    def test_the_demo_seed_ran_and_the_demo_account_logs_in(self):
        from impacto.seed_dev import DEMO_EMAILS
        s, d = self._json("POST", "/v1/auth/login", {"email": DEMO_EMAILS["osc"], "password": self.env["DEMO_PASSWORD"]})
        self.assertEqual(s, 200, d)
        self.assertIn("access_token", d)
        s, me = self._json("GET", "/v1/me", token=d["access_token"])
        self.assertEqual(s, 200)
        self.assertEqual(me["active_org"]["kind"], "osc")

    def test_all_migrations_applied_on_a_database_not_owned_by_impacto_owner(self):
        n = _psql_em(self.db, "SELECT count(*) FROM schema_migrations").strip()
        self.assertEqual(int(n), len(list((ROOT / "backend" / "migrations").glob("[0-9]*_*.sql"))))
        dono = _psql_em(self.db, "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = current_database()").strip()
        self.assertNotEqual(dono, "impacto_owner", "o cenário é o de banco gerenciado: o dono não é impacto_owner")

    def test_missing_app_password_stops_the_script_before_anything(self):
        env = {k: v for k, v in self.env.items() if k != "IMPACTO_APP_PASSWORD"}
        r = subprocess.run(["sh", str(SCRIPT)], cwd=ROOT / "backend", env=env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("IMPACTO_APP_PASSWORD", r.stderr + r.stdout)


class TheImageKeepsProductionGuardsTests(unittest.TestCase):
    """O Dockerfile recebido de fora fixava development, seed e um domínio de terceiro na IMAGEM."""

    def setUp(self):
        # Só as diretivas: o comentário que explica a recusa cita o que foi recusado, e isso não é
        # configuração. A primeira versão deste teste acusou o próprio comentário.
        self.docker = "\n".join(l for l in (ROOT / "Dockerfile").read_text(encoding="utf-8").splitlines()
                                if not l.lstrip().startswith("#"))

    def test_the_image_is_production_and_names_no_third_party_host(self):
        self.assertIn("IMPACTO_ENV=production", self.docker)
        for proibido in ("IMPACTO_ENV=development", "IMPACTO_SEED_DEMO=true", "manus", "PUBLIC_BASE_URL=https://"):
            self.assertNotIn(proibido, self.docker, proibido)

    def test_the_image_runs_the_entrypoint_it_copies(self):
        self.assertIn('CMD ["sh", "/app/start_container.sh"]', self.docker)
        self.assertIn("COPY backend/start_container.sh /app/start_container.sh", self.docker)
        self.assertTrue(os.access(SCRIPT, os.X_OK), "start_container.sh precisa ser executável")
        self.assertEqual(subprocess.run(["sh", "-n", str(SCRIPT)], capture_output=True).returncode, 0, "sintaxe sh")

    def test_the_entrypoint_never_derives_the_app_password_from_the_admin_url(self):
        script = SCRIPT.read_text(encoding="utf-8")
        self.assertIn(': "${IMPACTO_APP_PASSWORD:?', script)
        boot = (ROOT / "backend" / "impacto" / "db" / "bootstrap_external.py").read_text(encoding="utf-8")
        self.assertNotIn("parsed.password", boot)
        self.assertIn("len(senha) < 16", boot)
