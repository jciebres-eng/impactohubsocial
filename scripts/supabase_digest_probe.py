#!/usr/bin/env python3
"""Sonda: as cadeias de hash funcionam neste banco? Grava, confere e DESFAZ.

Num PostgreSQL gerenciado o pgcrypto mora em `extensions`. A sonda abre uma transação, força o
search_path da SESSÃO para `public, pg_temp` — para que só o search_path fixado em cada função
(migração 0063) possa achar `digest()` —, grava um evento de auditoria, lê o hash que o gatilho
SECURITY DEFINER `chain_audit` calculou, roda a verificação `audit_verify` (função comum) sobre a
cadeia, e termina em ROLLBACK. Nada persiste.

Lê DATABASE_URL (administrativa). Sai 0 se as duas funções acharam `digest()`; 1 caso contrário.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from impacto.db.pq import Connection, DatabaseError


def sonda(url: str) -> tuple[bool, str]:
    c = Connection(url)
    try:
        c.execute_script("BEGIN;")
        try:
            c.execute_script("SET LOCAL search_path TO public, pg_temp;")
            h = c.scalar("INSERT INTO audit_events(action) VALUES ('ci.sonda_digest') RETURNING event_hash")
            v = c.one("SELECT entries, valid FROM audit_verify(NULL)")
            ok = bool(h) and len(h) == 64 and v["valid"] is True
            return ok, f"chain_audit calculou hash de {len(h or '')} caracteres; audit_verify: {v['entries']} evento(s), válida={v['valid']}"
        except DatabaseError as exc:
            return False, "falhou: " + str(exc).splitlines()[0][:200]
        finally:
            c.execute_script("ROLLBACK;")
    finally:
        c.close()


def main() -> int:
    ok, msg = sonda(os.environ["DATABASE_URL"])
    print(("OK — " if ok else "FALHA — ") + msg + " (transação desfeita: nada gravado)")
    if os.getenv("GITHUB_ACTIONS"):
        print(f"::{'notice' if ok else 'error'} title=Sonda das cadeias de hash::{msg}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
