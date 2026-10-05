"""Ciclo de vida dos jobs de integração: idempotência, tentativas classificadas, disjuntor e auditoria.

`PENDING → RUNNING → SUCCEEDED | PARTIAL | FAILED | RETRYING | CANCELED`. A unicidade de `(org_id, idempotency_key)`
é garantida pelo banco: pedir duas vezes a mesma sincronização devolve o MESMO job, não cria um segundo.
"""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
from datetime import UTC, datetime

from ..db.pq import Json
from ..observability import log
from .contracts import IntegrationError
from .transport import ResilientCaller, backoff_delay

logger = logging.getLogger("impacto.integrations.jobs")
TERMINAL = ("succeeded", "failed", "canceled")


def idempotency_key(*parts: object) -> str:
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:48]


def enqueue(c, *, org_id: str, connection_id: str | None, operation: str, entity: str | None, direction: str,
            strategy: str = "manual", request: dict | None = None, user_id: str | None = None,
            key: str | None = None, max_attempts: int = 3) -> dict:
    """Cria o job se ainda não existir. Mesma chave de idempotência → devolve o job existente (`reused=True`)."""
    k = key or idempotency_key(connection_id, operation, entity, direction, json.dumps(request or {}, sort_keys=True, default=str))
    row = c.one("INSERT INTO integration_jobs(org_id, connection_id, operation, entity, direction, strategy, request,"
                " correlation_id, idempotency_key, max_attempts, created_by, next_attempt_at)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11, now())"
                " ON CONFLICT (org_id, idempotency_key) DO NOTHING RETURNING id::text AS id, correlation_id",
                org_id, connection_id, operation, entity, direction, strategy, Json(request or {}),
                secrets.token_hex(8), k, max_attempts, user_id)
    if row:
        return {"id": row["id"], "correlation_id": row["correlation_id"], "reused": False, "status": "pending"}
    prev = c.one("SELECT id::text AS id, correlation_id, status FROM integration_jobs WHERE org_id = $1 AND idempotency_key = $2", org_id, k)
    return {"id": prev["id"], "correlation_id": prev["correlation_id"], "reused": True, "status": prev["status"]}


def claim(c, job_id: str) -> dict | None:
    """Marca o job como em execução (trava a linha): dois trabalhadores não executam o mesmo job."""
    row = c.one("SELECT id::text AS id, status, attempts FROM integration_jobs WHERE id = $1 FOR UPDATE SKIP LOCKED", job_id)
    if not row or row["status"] in TERMINAL or row["status"] == "running":
        return None
    c.run("UPDATE integration_jobs SET status = 'running', attempts = attempts + 1, started_at = coalesce(started_at, now()) WHERE id = $1", job_id)
    return {"id": row["id"], "attempts": row["attempts"] + 1}


def succeed(c, job_id: str, result: dict, *, partial: bool = False) -> None:
    c.run("UPDATE integration_jobs SET status = $2, result = $3::jsonb, finished_at = now(), error_code = NULL,"
          " error_detail = NULL, error_kind = NULL, next_attempt_at = NULL WHERE id = $1",
          job_id, "partial" if partial else "succeeded", Json(result or {}))


def fail(c, job_id: str, exc: IntegrationError, *, attempts: int, max_attempts: int) -> str:
    """Erro temporário reagenda com backoff; permanente ou tentativas esgotadas encerra como `failed`."""
    retry = exc.temporary and attempts < max_attempts
    if retry:
        delay = backoff_delay(attempts, base=15.0, cap=1800.0)
        c.run("UPDATE integration_jobs SET status = 'retrying', error_code = $2, error_detail = $3, error_kind = $4,"
              " next_attempt_at = now() + make_interval(secs => $5) WHERE id = $1", job_id, exc.code, str(exc)[:1000], exc.kind, delay)
        return "retrying"
    c.run("UPDATE integration_jobs SET status = 'failed', error_code = $2, error_detail = $3, error_kind = $4,"
          " finished_at = now(), next_attempt_at = NULL WHERE id = $1", job_id, exc.code, str(exc)[:1000], exc.kind)
    return "failed"


def cancel(c, job_id: str, *, org_id: str) -> dict:
    row = c.one("SELECT status FROM integration_jobs WHERE id = $1 AND org_id = $2", job_id, org_id)
    if not row:
        return {"canceled": False, "reason": "not_found"}
    if row["status"] in TERMINAL:
        return {"canceled": False, "reason": "already_finished", "status": row["status"]}
    c.run("UPDATE integration_jobs SET status = 'canceled', finished_at = now(), next_attempt_at = NULL WHERE id = $1", job_id)
    return {"canceled": True}


def due(c, *, limit: int = 50, now: datetime | None = None) -> list[dict]:
    return c.query("SELECT id::text AS id, org_id::text AS org_id, connection_id::text AS connection_id, operation, entity,"
                   " direction, request, attempts, max_attempts, correlation_id FROM integration_jobs"
                   " WHERE status IN ('pending','retrying') AND (next_attempt_at IS NULL OR next_attempt_at <= $1)"
                   " ORDER BY next_attempt_at NULLS FIRST LIMIT $2", now or datetime.now(UTC), limit)


def register_outcome(c, *, connection_id: str | None, ok: bool, temporary: bool = True, detail: str = "") -> None:
    """Atualiza saúde e disjuntor da conexão conforme o resultado — o núcleo não trava por causa de sistema externo."""
    if not connection_id:
        return
    if ok:
        c.run("UPDATE integration_connections SET failure_streak = 0, circuit_open_until = NULL, last_success_at = now(),"
              " health_state = 'healthy', health_detail = NULL, last_health_at = now(), updated_at = now() WHERE id = $1", connection_id)
        return
    row = c.one("SELECT failure_streak FROM integration_connections WHERE id = $1", connection_id)
    streak, open_until = ResilientCaller.next_circuit_state((row or {}).get("failure_streak", 0), temporary=temporary)
    state = "unavailable" if open_until else "degraded"
    c.run("UPDATE integration_connections SET failure_streak = $2, circuit_open_until = $3, health_state = $4,"
          " health_detail = $5, last_health_at = now(), updated_at = now() WHERE id = $1",
          connection_id, streak, open_until, state, (detail or None))
    if open_until:
        log(logger, logging.WARNING, "integration_circuit_open", connection_id=connection_id, failure_streak=streak)
