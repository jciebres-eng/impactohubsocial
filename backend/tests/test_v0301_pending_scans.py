"""v0.30.1 — um arquivo ilegível no storage não pode parar o reescaneamento dos demais.

Em produção (2026-10-09) quatro documentos criados antes de o bucket existir ficaram em
`pending_scan` sem objeto no R2. O primeiro 404 derrubava `pending_scans` inteiro e nenhum outro
documento era escaneado. A rotina agora pula o ilegível (que continua em quarentena) e segue.
"""
from __future__ import annotations

import contextlib
import unittest

from impacto import jobs


class _Conn:
    def __init__(self, docs, updates):
        self._docs, self._updates = docs, updates

    def query(self, sql, *args):
        return list(self._docs)

    def run(self, sql, *args):
        self._updates.append(args)


class _Pool:
    def __init__(self, docs, updates):
        self._conn = _Conn(docs, updates)

    @contextlib.contextmanager
    def tx(self, ctx, readonly=False):
        yield self._conn


class _Storage:
    def __init__(self, missing):
        self.missing, self.deleted = set(missing), []

    def get(self, key):
        if key in self.missing:
            raise RuntimeError("HTTP Error 404: Not Found")
        return b"conteudo"

    def delete(self, key):
        self.deleted.append(key)


class _Antivirus:
    name = "clamd"

    def scan(self, data):
        return "clean", ""


class _App:
    def __init__(self, docs, missing):
        self.updates: list = []
        self.pool = _Pool(docs, self.updates)
        self.storage = _Storage(missing)
        self.antivirus = _Antivirus()


class PendingScansTests(unittest.TestCase):
    def test_missing_object_does_not_stop_the_queue(self):
        docs = [{"id": "a", "storage_key": "k-a"}, {"id": "b", "storage_key": "k-ausente"},
                {"id": "c", "storage_key": "k-c"}]
        app = _App(docs, missing={"k-ausente"})
        res = jobs.pending_scans(app)
        self.assertEqual(res["scanned"], 2)
        self.assertEqual(res["unreadable"], 1)
        self.assertEqual(res["unreadable_ids"], ["b"])
        # o ilegível NÃO é marcado: continua em quarentena
        self.assertEqual([u[0] for u in app.updates], ["a", "c"])

    def test_without_antivirus_is_skipped(self):
        app = _App([], missing=set())
        app.antivirus.name = "none"
        self.assertIn("skipped", jobs.pending_scans(app))


if __name__ == "__main__":
    unittest.main()
