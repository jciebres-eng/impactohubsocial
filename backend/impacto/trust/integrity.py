"""Integridade documental: o arquivo guardado continua sendo o que foi registrado?

Reconta o SHA-256 do objeto no armazenamento e compara com ``documents.sha256`` (gravado no upload e protegido por
``guard_columns``: o papel da aplicação não altera o hash). O resultado entra na cadeia de custódia — inclusive quando falha.
"""
from __future__ import annotations

import hashlib

from ..db.pq import Connection
from . import custody


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_document(conn: Connection, storage, document_id: str, *, actor_user_id: str | None = None) -> dict:
    d = conn.one("SELECT id::text AS id, org_id::text AS org_id, sha256, storage_key, filename, size_bytes, version,"
                 " status, created_at FROM documents WHERE id = $1 AND deleted_at IS NULL", document_id)
    if not d:
        return {"found": False}
    try:
        data = storage.get(d["storage_key"])
    except (OSError, ValueError) as exc:
        custody.record(conn, subject_type="document", subject_id=d["id"], org_id=d["org_id"], event_type="integrity_failed",
                       actor_user_id=actor_user_id, content_sha256=d["sha256"], payload={"reason": "unreadable"})
        return {"found": True, "readable": False, "intact": False, "detail": f"objeto ilegível no armazenamento ({type(exc).__name__})"}
    actual = sha256_bytes(data)
    intact = actual == d["sha256"]
    custody.record(conn, subject_type="document", subject_id=d["id"], org_id=d["org_id"],
                   event_type="integrity_ok" if intact else "integrity_failed", actor_user_id=actor_user_id,
                   content_sha256=actual, payload={"expected": d["sha256"], "size_bytes": len(data)})
    return {"found": True, "readable": True, "intact": intact, "expected_sha256": d["sha256"], "actual_sha256": actual,
            "size_bytes": len(data), "declared_size_bytes": d["size_bytes"], "version": d["version"], "filename": d["filename"]}
