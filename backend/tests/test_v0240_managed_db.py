"""Banco gerenciado: onde o `digest()` mora e quem o encontra.

Motivado pela instância publicada por terceiro no Supabase, onde a plataforma não subia porque as
funções de cadeia (SECURITY DEFINER com `search_path = public, pg_temp`) não achavam `digest()` —
lá o pgcrypto vive na schema `extensions`. A migração 0063 fixa `public, extensions, pg_temp` em
TODA função que chama digest(); a conexão inclui `extensions` na sessão só se a schema existir.
"""
from __future__ import annotations

import os
import unittest

from tests.support import APP_DSN, owner_conn, server


class EveryDigestCallerCanFindPgcryptoOnAManagedDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server()

    def test_every_function_that_calls_digest_pins_extensions_in_its_search_path(self):
        """A versão desta migração recebida de fora cobria 5 funções; são 9. Este teste não deixa a
        décima ficar de fora: varre o catálogo, não uma lista escrita à mão."""
        c = owner_conn()
        try:
            rows = c.query(
                "SELECT p.proname, p.proconfig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace"
                " WHERE n.nspname = 'public' AND position('digest(' in p.prosrc) > 0 ORDER BY p.proname")
        finally:
            c.close()
        self.assertGreaterEqual(len(rows), 9, [r["proname"] for r in rows])
        sem = [r["proname"] for r in rows
               if not any(x.startswith("search_path=") and "extensions" in x for x in (r["proconfig"] or []))]
        self.assertEqual(sem, [], f"função chama digest() sem `extensions` no search_path: {sem}")

    def test_the_extensions_schema_exists_and_the_app_role_can_use_it(self):
        from impacto.db.pq import Connection
        c = Connection(APP_DSN)
        try:
            self.assertTrue(c.scalar("SELECT has_schema_privilege('impacto_app', 'extensions', 'USAGE')"))
            self.assertEqual(c.scalar("SHOW search_path"), "public, extensions",
                             "a sessão da aplicação tem de incluir `extensions` quando a schema existe")
        finally:
            c.close()

    def test_the_chains_still_verify_after_the_search_path_change(self):
        """Mexer no search_path de função de cadeia sem conferir a cadeia seria fé, não prova.

        Aqui o pgcrypto está em `public` (migração 0001), então `extensions` fica vazia e este teste
        prova só que nada quebrou. A prova de que funciona com o pgcrypto EM `extensions` só pode ser
        dada contra um banco gerenciado — e está dita assim em docs/PUBLICACAO.md, não fingida aqui.
        """
        c = owner_conn()
        try:
            self.assertEqual(len(c.scalar("SELECT encode(digest('impacto', 'sha256'), 'hex')")), 64)
            org = c.scalar("SELECT org_id::text FROM audit_events WHERE org_id IS NOT NULL LIMIT 1")
            if org:
                self.assertIsNotNone(c.one("SELECT * FROM audit_verify($1::uuid)", org))
                self.assertIsNotNone(c.one("SELECT * FROM value_verify($1::uuid)", org))
            self.assertEqual(c.scalar("SELECT count(*) FROM pg_extension WHERE extname = 'pgcrypto'"), 1,
                             "a migração 0063 não pode instalar um segundo pgcrypto onde já há um")
        finally:
            c.close()


class TheChainsWorkWithPgcryptoInExtensionsLikeSupabaseTests(unittest.TestCase):
    """Layout do Supabase reproduzido: pgcrypto instalado em `extensions` ANTES da primeira migração.

    Até aqui a documentação dizia que isto "só se prova contra o banco gerenciado". Não precisava:
    o que o Supabase faz de diferente nesse ponto é ONDE o pgcrypto mora, e isso se reproduz. Prova:
    as 63 migrações aplicam (a 0023 já dispara digest() ao inserir documentos legais), a sonda grava
    um evento de auditoria com o search_path da SESSÃO sem `extensions` e a cadeia calcula e valida
    — e, como contraprova, sem a 0063 cada uma das duas funções falha com o erro exato que
    derrubava a publicação no Supabase.

    O que continua fora: administrador não-superusuário, o pooler Supavisor e as concessões padrão do
    Supabase. Para isso existe o workflow manual `supabase.yml` (modo verificar, só leitura).
    """

    @classmethod
    def setUpClass(cls):
        import subprocess
        import sys
        from tests.support import ADMIN_URL, ROOT, _psql
        cls._psql = _psql
        cls.db = f"impacto_supa_{os.getpid()}"
        cls.url = ADMIN_URL.rsplit("/", 1)[0] + "/" + cls.db
        _psql("-c", f'DROP DATABASE IF EXISTS "{cls.db}" WITH (FORCE)')
        _psql("-c", f'CREATE DATABASE "{cls.db}"')
        subprocess.run(["psql", cls.url, "-qv", "ON_ERROR_STOP=1", "-c",
                        "CREATE SCHEMA extensions; CREATE EXTENSION pgcrypto WITH SCHEMA extensions;"],
                       check=True, capture_output=True)
        r = subprocess.run([sys.executable, "-m", "impacto.db.migrate"], cwd=ROOT / "backend",
                           env={**os.environ, "DATABASE_URL": cls.url}, capture_output=True, text=True, timeout=600)
        cls.migrou = (r.returncode, r.stdout[-800:] + r.stderr[-1500:])
        sys.path.insert(0, str(ROOT / "scripts"))
        import supabase_digest_probe
        cls.sonda = staticmethod(supabase_digest_probe.sonda)

    @classmethod
    def tearDownClass(cls):
        cls._psql("-c", f'DROP DATABASE IF EXISTS "{cls.db}" WITH (FORCE)')

    def _sql(self, sql: str) -> str:
        import subprocess
        return subprocess.run(["psql", self.url, "-qtAv", "ON_ERROR_STOP=1", "-c", sql],
                              check=True, capture_output=True, text=True).stdout.strip()

    def test_all_migrations_apply_with_pgcrypto_in_extensions(self):
        self.assertEqual(self.migrou[0], 0, self.migrou[1])
        self.assertEqual(self._sql("SELECT extnamespace::regnamespace FROM pg_extension WHERE extname='pgcrypto'"),
                         "extensions", "o cenário tem de ser o do Supabase")

    def test_the_hash_chain_computes_and_verifies_and_nothing_persists(self):
        ok, msg = self.sonda(self.url)
        self.assertTrue(ok, msg)
        self.assertEqual(self._sql("SELECT count(*) FROM audit_events WHERE action = 'ci.sonda_digest'"), "0",
                         "a sonda tem de terminar em ROLLBACK")

    def test_without_migration_0063_the_supabase_failure_comes_back(self):
        """Contraprova: sem o search_path da 0063, o erro exato da publicação no Supabase volta."""
        for fn, desfaz, refaz in (
                ("chain_audit", "ALTER FUNCTION chain_audit() SET search_path = public, pg_temp",
                 "ALTER FUNCTION chain_audit() SET search_path = public, extensions, pg_temp"),
                ("audit_verify", "ALTER FUNCTION audit_verify(uuid) RESET search_path",
                 "ALTER FUNCTION audit_verify(uuid) SET search_path = public, extensions, pg_temp")):
            self._sql(desfaz)
            try:
                ok, msg = self.sonda(self.url)
            finally:
                self._sql(refaz)
            self.assertFalse(ok, f"{fn}: a sonda passou sem a 0063 — então a 0063 não é o que a faz funcionar")
            self.assertIn("digest", msg, msg)


class TheSupabaseToolingIsSafeByConstructionTests(unittest.TestCase):
    """O que vai tocar um banco de outra pessoa tem de ser seguro por construção, não por cuidado."""

    def test_pooler_username_carries_the_project_suffix(self):
        from impacto.db.app_url import app_dsn
        pooler = "postgresql://postgres.abcdefghijkl:exemplo%40fixture@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
        self.assertEqual(app_dsn(pooler, "exemplo/fix@ture"),
                         "postgresql://impacto_app.abcdefghijkl:exemplo%2Ffix%40ture@aws-0-sa-east-1.pooler.supabase.com:5432/postgres")
        direta = "postgresql://postgres:exemplo@db.abc.supabase.co:5432/postgres?sslmode=require"
        self.assertEqual(app_dsn(direta, "exemplo2"), "postgresql://impacto_app:exemplo2@db.abc.supabase.co:5432/postgres?sslmode=require")
        with self.assertRaises(ValueError):
            app_dsn("host=x user=y", "p")

    def test_the_entrypoint_uses_the_pooler_aware_rewrite(self):
        from tests.support import ROOT
        script = (ROOT / "backend" / "start_container.sh").read_text(encoding="utf-8")
        self.assertIn("python3 -m impacto.db.app_url", script)
        self.assertNotIn("'impacto_app:' +", script, "a troca antiga, que não conhecia o pooler, voltou")

    def test_the_diagnostic_only_reads(self):
        """Toda consulta do diagnóstico roda em transação READ ONLY, e o código não tem SQL de escrita."""
        import re
        from tests.support import ROOT
        fonte = (ROOT / "scripts" / "supabase_check.py").read_text(encoding="utf-8")
        self.assertIn('BEGIN TRANSACTION READ ONLY;', fonte)
        self.assertLess(fonte.index("BEGIN TRANSACTION READ ONLY"), fonte.index('SHOW server_version'))
        # Todo comando passado a scalar/one/query/execute_script tem de COMEÇAR com verbo de leitura.
        # (A primeira versão procurava a palavra GRANT em qualquer lugar e acusou
        # `has_schema_privilege(..., 'USAGE WITH GRANT OPTION')`, que é leitura.)
        comandos = re.findall(r'\.(?:scalar|one|query|execute_script|execute)\(\s*\(?\s*f?"([^"]+)"', fonte)
        self.assertGreater(len(comandos), 8, "o extrator de comandos parou de ver o SQL do diagnóstico")
        for sql in comandos:
            self.assertRegex(sql.lstrip(), r"^(SELECT|SHOW|BEGIN TRANSACTION READ ONLY;|ROLLBACK;)",
                             f"comando que não é leitura no diagnóstico: {sql[:80]}")

    def test_the_probe_always_rolls_back(self):
        from tests.support import ROOT
        fonte = (ROOT / "scripts" / "supabase_digest_probe.py").read_text(encoding="utf-8")
        self.assertIn('c.execute_script("ROLLBACK;")', fonte)
        self.assertNotIn("COMMIT", fonte)

    def test_the_workflow_is_manual_confirmed_and_never_echoes_secrets(self):
        import yaml
        from tests.support import ROOT
        bruto = (ROOT / ".github" / "workflows" / "supabase.yml").read_text(encoding="utf-8")
        wf = yaml.safe_load(bruto)
        self.assertEqual(list(wf[True]), ["workflow_dispatch"], "o workflow do Supabase só roda à mão")
        self.assertEqual(wf[True]["workflow_dispatch"]["inputs"]["modo"]["default"], "verificar")
        aplicar = wf["jobs"]["aplicar"]
        self.assertEqual(aplicar["if"], "inputs.modo == 'aplicar'")
        self.assertEqual(aplicar["needs"], "verificar", "aplicar sem diagnóstico antes não")
        primeiro = aplicar["steps"][0]
        self.assertEqual(primeiro["name"], "Confirmação")
        self.assertIn("APLICAR NO SUPABASE", primeiro["run"])
        # input do usuário nunca interpolado direto no shell (injeção): só via env
        for passo in aplicar["steps"] + wf["jobs"]["verificar"]["steps"]:
            self.assertNotIn("${{ inputs.", passo.get("run", ""), f"input interpolado no shell em {passo.get('name')}")
            self.assertNotIn("${{ secrets.", passo.get("run", ""), f"segredo interpolado no shell em {passo.get('name')}")
        self.assertIn("IMPACTO_ENV=staging", bruto)
        self.assertNotIn("IMPACTO_SEED_DEMO", bruto, "aplicar no banco de alguém não semeia demonstração")
        self.assertIn("pooler", bruto)
