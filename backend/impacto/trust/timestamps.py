"""Carimbo de tempo.

* ``internal``: selo HMAC-SHA256 do servidor sobre ``(hash do conteúdo, instante)``. Prova **interna**, verificável por
  quem tem a chave do servidor. NÃO é carimbo de Autoridade de Carimbo de Tempo e não substitui um.
* ``rfc3161``: carimbo de ACT. O protocolo está descrito e a coluna do token existe, mas **não há emissão**: depende de
  ACT contratada (DEPENDÊNCIA EXTERNA). A função abaixo recusa explicitamente em vez de simular.
"""
from __future__ import annotations

from datetime import UTC, datetime

from ..db.pq import Connection
from ..security.tokens import hmac_hex
from . import custody

RFC3161_UNAVAILABLE = ("Carimbo de tempo RFC 3161 exige Autoridade de Carimbo de Tempo (ACT) contratada. "
                       "Não está disponível nesta instalação — o carimbo interno da plataforma é o que foi aplicado.")


def seal_material(hashed_value: str, stamped_at: str) -> str:
    return f"impacto-timestamp-v1|{hashed_value}|{stamped_at}"


def stamp_internal(conn: Connection, *, record_id: str, hashed_value: str, secret_key: str,
                   subject_type: str | None = None, subject_id: str | None = None, org_id: str | None = None) -> dict:
    at = datetime.now(UTC).replace(microsecond=0).isoformat()
    seal = hmac_hex(secret_key, seal_material(hashed_value, at))
    row = conn.one("INSERT INTO trust_timestamps(record_id, kind, hashed_value, seal, authority, stamped_at)"
                   " VALUES ($1,'internal',$2,$3,$4,$5::timestamptz) RETURNING id::text AS id, stamped_at",
                   record_id, hashed_value, seal, "IMPACTO (carimbo interno)", at)
    if subject_type and subject_id:
        custody.record(conn, subject_type=subject_type, subject_id=subject_id, org_id=org_id, event_type="timestamped",
                       content_sha256=hashed_value, payload={"kind": "internal", "timestamp_id": row["id"]})
    return {"id": row["id"], "kind": "internal", "stamped_at": row["stamped_at"], "authority": "IMPACTO (carimbo interno)",
            "note": "Carimbo interno da plataforma (selo HMAC do servidor). Não é carimbo de ACT."}


def verify_internal(hashed_value: str, stamped_at: str, seal: str, secret_key: str) -> bool:
    import hmac as _h
    return _h.compare_digest(seal, hmac_hex(secret_key, seal_material(hashed_value, stamped_at)))


def stamp_rfc3161(*_args, **_kwargs):
    from ..http import ApiError
    raise ApiError(501, "tsa_not_configured", RFC3161_UNAVAILABLE)
