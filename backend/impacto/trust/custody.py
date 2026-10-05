"""Cadeia de custódia por objeto.

Cada fato relevante (criação, nova versão, assinatura, revogação, verificação pública, conferência de integridade) entra
em ``trust_events``. O encadeamento (``seq``, ``prev_hash``, ``event_hash``) é calculado por gatilho SECURITY DEFINER no
banco: a aplicação **não escolhe** o próprio hash, e a tabela é append-only. Quebrar a cadeia exige acesso de dono do banco.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json

EVENTS = ("created", "version_created", "hashed", "signed", "signature_revoked", "timestamped", "verified_public",
          "integrity_ok", "integrity_failed", "revoked", "superseded", "shared", "identity_decided", "credential_decided")


def record(conn: Connection, *, subject_type: str, subject_id: str, event_type: str, org_id: str | None = None,
           actor_user_id: str | None = None, content_sha256: str | None = None, payload: dict[str, Any] | None = None) -> dict:
    if event_type not in EVENTS:
        raise ValueError(f"evento de custódia desconhecido: {event_type}")
    return conn.one(
        "INSERT INTO trust_events(subject_type, subject_id, org_id, event_type, actor_user_id, content_sha256, payload)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb) RETURNING id, seq, event_hash, at",
        subject_type, subject_id, org_id, event_type, actor_user_id, content_sha256, Json(payload or {}))


def chain(conn: Connection, subject_type: str, subject_id: str, limit: int = 200) -> list[dict]:
    return conn.query(
        "SELECT seq, event_type, content_sha256, payload, prev_hash, event_hash, at,"
        " actor_user_id::text AS actor_user_id, user_display_name(actor_user_id) AS actor_name"
        " FROM trust_events WHERE subject_type = $1 AND subject_id = $2 ORDER BY seq LIMIT $3",
        subject_type, subject_id, limit)


def verify(conn: Connection, subject_type: str, subject_id: str) -> dict:
    row = conn.one("SELECT entries, valid, first_broken_seq FROM trust_verify($1, $2)", subject_type, subject_id)
    return {"entries": row["entries"], "valid": row["valid"], "first_broken_seq": row["first_broken_seq"]}
