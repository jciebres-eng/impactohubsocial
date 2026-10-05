"""Mensagens de ENTRADA (webhook de sistema externo): assinatura verificada e deduplicação obrigatória.

Mesmo princípio já provado no webhook do Stripe: a unicidade é garantida pelo BANCO (UNIQUE por conexão + id do evento
externo), então a mesma mensagem entregue 1, 2 ou 10 vezes — inclusive em paralelo — é processada uma única vez.
"""
from __future__ import annotations

import hashlib
import logging

from ..observability import log
from .contracts import IntegrationError

logger = logging.getLogger("impacto.integrations.inbound")
MAX_BODY = 2 * 1024 * 1024


def record(c, *, connection_id: str, external_event_id: str, event_type: str | None, body: bytes) -> dict:
    """Registra a chegada. Devolve `duplicate=True` quando já havia sido recebida (nada é reprocessado)."""
    if len(body) > MAX_BODY:
        raise IntegrationError("payload_too_large", "Corpo da mensagem acima do limite", kind="permanent")
    digest = hashlib.sha256(body).hexdigest()
    row = c.one("INSERT INTO integration_inbound(connection_id, external_event_id, event_type, payload_sha256)"
                " VALUES ($1,$2,$3,$4) ON CONFLICT (connection_id, external_event_id) DO NOTHING"
                " RETURNING id::text AS id", connection_id, external_event_id[:200], (event_type or None), digest)
    if not row:
        prev = c.one("SELECT id::text AS id, payload_sha256, status FROM integration_inbound"
                     " WHERE connection_id = $1 AND external_event_id = $2", connection_id, external_event_id[:200])
        same = bool(prev and prev["payload_sha256"] == digest)
        log(logger, logging.INFO, "inbound_duplicate", connection_id=connection_id, same_payload=same)
        return {"id": prev["id"] if prev else None, "duplicate": True, "same_payload": same, "status": prev["status"] if prev else None}
    return {"id": row["id"], "duplicate": False, "same_payload": True, "status": "received"}


def finish(c, inbound_id: str, *, status: str, detail: str | None = None, job_id: str | None = None) -> None:
    c.run("UPDATE integration_inbound SET status = $2, detail = $3, job_id = $4, processed_at = now() WHERE id = $1",
          inbound_id, status, (detail or None), job_id)
