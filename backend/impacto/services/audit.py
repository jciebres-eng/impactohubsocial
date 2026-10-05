"""Trilha de auditoria (hash encadeado por organização, calculado no banco) e Impact Ledger (por projeto)."""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json

_SENSITIVE = {"password", "token", "secret", "code", "mfa_secret", "cnpj_lookup_raw"}


def _clean(payload: dict) -> dict:
    return {k: ("[REDACTED]" if k in _SENSITIVE else v) for k, v in (payload or {}).items()}


def record(conn: Connection, *, org_id: str | None, actor: str | None, action: str, object_type: str | None = None,
           object_id: Any = None, payload: dict | None = None, ip: str | None = None, request_id: str | None = None) -> None:
    conn.run("INSERT INTO audit_events(org_id, actor_user_id, action, object_type, object_id, ip, request_id, payload)"
             " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)",
             org_id, actor, action, object_type, None if object_id is None else str(object_id), ip, request_id,
             Json(_clean(payload or {})))


def ledger(conn: Connection, *, project_id: str, org_id: str, actor: str | None, entry_type: str,
           amount_cents: int | None = None, ref_type: str | None = None, ref_id: Any = None, payload: dict | None = None) -> dict:
    return conn.one("INSERT INTO ledger_entries(project_id, org_id, actor_user_id, entry_type, amount_cents, ref_type, ref_id, payload)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) RETURNING id, seq, entry_hash",
                    project_id, org_id, actor, entry_type, amount_cents, ref_type, None if ref_id is None else str(ref_id),
                    Json(payload or {}))
