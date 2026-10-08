"""Banco gerenciado: onde o `digest()` mora e quem o encontra.

Motivado pela instância publicada por terceiro no Supabase, onde a plataforma não subia porque as
funções de cadeia (SECURITY DEFINER com `search_path = public, pg_temp`) não achavam `digest()` —
lá o pgcrypto vive na schema `extensions`. A migração 0063 fixa `public, extensions, pg_temp` em
TODA função que chama digest(); a conexão inclui `extensions` na sessão só se a schema existir.
"""
from __future__ import annotations

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
