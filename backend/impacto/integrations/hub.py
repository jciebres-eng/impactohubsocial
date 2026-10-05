"""Orquestrador do Integration Hub: resolve o adapter, monta o contexto (credencial decifrada só em memória),
executa saúde/pull/push com transporte resiliente, grava IDs externos, atualiza disjuntor e audita.

Executa SEMPRE em contexto de sistema restrito à conexão/organização em questão (as tabelas do hub têm RLS, e a
credencial só é legível pela função privilegiada). O núcleo de negócio não é tocado daqui — só a camada de integração.
"""
from __future__ import annotations

import logging
import secrets as _secrets
from datetime import UTC, datetime

from ..db.pq import Json
from ..observability import log
from ..services.audit import record as audit_record
from . import hubjobs, links
from . import secrets as sec
from .adapters import ADAPTERS
from .contracts import AdapterContext, IntegrationError
from .transport import ResilientCaller

logger = logging.getLogger("impacto.integrations.hub")


def adapter_for(provider_key: str):
    cls = ADAPTERS.get(provider_key)
    if not cls:
        raise IntegrationError("no_adapter", f"Provedor sem adapter executável nesta versão: {provider_key}", kind="permanent")
    return cls()


def load_connection(c, connection_id: str) -> dict:
    row = c.one("SELECT id::text AS id, org_id::text AS org_id, provider_key, name, environment, status, endpoint, external_system_id,"
                " config, health_state, failure_streak, circuit_open_until FROM integration_connections WHERE id = $1", connection_id)
    if not row:
        raise IntegrationError("connection_not_found", "Conexão não encontrada", kind="permanent", status=404)
    return row


def build_context(app, c, conn: dict, *, correlation_id: str | None = None, http=None, sleep=None) -> AdapterContext:
    secret, username, kind = sec.load(c, app.cipher, connection_id=conn["id"], provider=getattr(app, "secret_provider", None))
    conn = dict(conn, _credential_kind=kind)
    mappings = c.query("SELECT entity, direction, source_path, target_field, transform, enum_map, required, default_value"
                       " FROM integration_mappings WHERE connection_id = $1", conn["id"])
    cid = correlation_id or _secrets.token_hex(8)
    kwargs = {"correlation_id": cid}
    if http is not None:
        kwargs["http"] = http
    if sleep is not None:
        kwargs["sleep"] = sleep
    caller = ResilientCaller(conn, **kwargs)
    return AdapterContext(connection=conn, secret=secret, username=username, mappings=mappings, transport=caller,
                          correlation_id=cid, config=conn.get("config") or {})


def health_check(app, c, connection_id: str, *, actor: str | None = None, http=None) -> dict:
    """Nunca destrutivo. Grava o estado na conexão e audita."""
    conn = load_connection(c, connection_id)
    adapter = adapter_for(conn["provider_key"])
    ctx = build_context(app, c, conn, http=http, sleep=lambda _s: None)
    if conn.get("status") == "revoked":
        state, detail = "unconfigured", "conexão revogada"
    elif ctx.transport.circuit_open():
        state, detail = "unavailable", "disjuntor aberto após falhas consecutivas"
    else:
        try:
            state, detail = adapter.health_check(ctx)
        except IntegrationError as exc:
            state, detail = ("degraded" if exc.temporary else "unavailable"), str(exc)
        except Exception as exc:  # noqa: BLE001 - adapter nunca derruba o núcleo
            state, detail = "unknown", f"{type(exc).__name__}"
    c.run("UPDATE integration_connections SET health_state = $2, health_detail = $3, last_health_at = now(), updated_at = now() WHERE id = $1",
          connection_id, state, (detail or "")[:500] or None)
    audit_record(c, org_id=conn["org_id"], actor=actor, action="integration.health_check", object_type="integration_connection",
                 object_id=connection_id, payload={"state": state, "correlation_id": ctx.correlation_id}, ip=None, request_id=ctx.correlation_id)
    return {"connection_id": connection_id, "health_state": state, "detail": (detail or "")[:500], "checked_at": datetime.now(UTC).isoformat(),
            "correlation_id": ctx.correlation_id}


def run_job(app, c, job: dict, *, http=None, sleep=None) -> dict:
    """Executa UM job já reivindicado (claim). Resultado, erro classificado, disjuntor e auditoria ficam registrados."""
    conn = load_connection(c, job["connection_id"]) if job.get("connection_id") else None
    outcome = {"job_id": job["id"], "status": "failed"}
    try:
        if conn is None:
            raise IntegrationError("no_connection", "Job sem conexão", kind="permanent")
        if conn["status"] != "active":
            raise IntegrationError("connection_inactive", f"Conexão em estado '{conn['status']}'", kind="permanent")
        adapter = adapter_for(conn["provider_key"])
        ctx = build_context(app, c, conn, correlation_id=job["correlation_id"], http=http, sleep=sleep)
        req = job.get("request") or {}
        if job["operation"] == "health_check":
            state, detail = adapter.health_check(ctx)
            result = {"health_state": state, "detail": detail}
            ok = state == "healthy"
        elif job["operation"] == "pull":
            since = datetime.fromisoformat(req["since"]) if req.get("since") else None
            res = adapter.pull(ctx, job["entity"], since=since, limit=int(req.get("limit", 200)))
            linked = conflicts = 0
            for rec in res.records:
                if rec.external_id and rec.fields.get("internal_id"):
                    out = links.link(c, org_id=conn["org_id"], connection_id=conn["id"], entity=rec.entity, internal_id=str(rec.fields["internal_id"]),
                                     external_id=rec.external_id, external_version=rec.external_version)
                    linked += out["status"] == "linked"
                    conflicts += out["status"] == "conflict"
            result = {**res.stats, "linked": linked, "conflicts": conflicts, "detail": res.detail,
                      "records_preview": [{"entity": r.entity, "external_id": r.external_id, "fields": list(r.fields)[:12]} for r in res.records[:5]]}
            ok = res.ok and res.stats.get("invalid", 0) == 0
        elif job["operation"] == "push":
            from .contracts import CanonicalRecord
            recs = [CanonicalRecord(entity=job["entity"], fields=r.get("fields", {}), external_id=r.get("external_id")) for r in req.get("records", [])]
            res = adapter.push(ctx, job["entity"], recs)
            for internal_id, ext in res.external_ids.items():
                links.link(c, org_id=conn["org_id"], connection_id=conn["id"], entity=job["entity"], internal_id=internal_id, external_id=ext)
            result = {**res.stats, "linked": len(res.external_ids)}
            ok = res.ok
        else:
            raise IntegrationError("unknown_operation", f"Operação desconhecida: {job['operation']}", kind="permanent")
        hubjobs.succeed(c, job["id"], result, partial=not ok)
        hubjobs.register_outcome(c, connection_id=conn["id"], ok=True)
        outcome.update({"status": "partial" if not ok else "succeeded", "result": result})
    except IntegrationError as exc:
        status = hubjobs.fail(c, job["id"], exc, attempts=job["attempts"], max_attempts=job["max_attempts"])
        if conn:
            hubjobs.register_outcome(c, connection_id=conn["id"], ok=False, temporary=exc.temporary, detail=f"{exc.code}: {exc}"[:300])
        outcome.update({"status": status, "error_code": exc.code, "error_kind": exc.kind})
        if status == "failed":
            from .events import emit
            try:
                emit(c, org_id=job["org_id"], event_type="INTEGRATION.JOB.FAILED", entity_id=job["id"],
                     payload={"operation": job["operation"], "entity": job.get("entity"), "error_code": exc.code})
            except Exception:  # noqa: BLE001
                log(logger, logging.WARNING, "integration_event_emit_failed", job_id=job["id"])
    except Exception as exc:  # noqa: BLE001 - defeito no adapter: registra como permanente, nunca derruba o trabalhador
        err = IntegrationError("adapter_error", f"Falha interna do adapter: {type(exc).__name__}", kind="permanent")
        hubjobs.fail(c, job["id"], err, attempts=job["attempts"], max_attempts=job["max_attempts"])
        log(logger, logging.ERROR, "integration_adapter_error", job_id=job["id"], error_type=type(exc).__name__)
        outcome.update({"status": "failed", "error_code": "adapter_error"})
    audit_record(c, org_id=job["org_id"], actor=None, action=f"integration.job.{outcome['status']}", object_type="integration_job",
                 object_id=job["id"], payload={k: v for k, v in outcome.items() if k != "result"} | {"operation": job["operation"], "entity": job.get("entity"),
                 "connection_id": job.get("connection_id"), "attempt": job["attempts"]}, ip=None, request_id=job["correlation_id"])
    return outcome


def process_due(app, c, *, limit: int = 20, http=None, sleep=None) -> dict:
    """Trabalhador: executa os jobs devidos. Cada job é reivindicado com FOR UPDATE SKIP LOCKED (sem execução dupla)."""
    done = {"succeeded": 0, "partial": 0, "failed": 0, "retrying": 0, "skipped": 0}
    for job in hubjobs.due(c, limit=limit):
        claimed = hubjobs.claim(c, job["id"])
        if not claimed:
            done["skipped"] += 1
            continue
        job = dict(job, attempts=claimed["attempts"])
        out = run_job(app, c, job, http=http, sleep=sleep)
        done[out["status"]] = done.get(out["status"], 0) + 1
    return done


def connection_summary(c, conn_id: str) -> dict:
    """Visão operacional de UMA conexão: estado, última sincronização, falhas, jobs recentes, pendências de entrega."""
    conn = load_connection(c, conn_id)
    conn["credential"] = c.one("SELECT kind, hint, username, scopes, expires_at, rotated_at FROM integration_credentials WHERE connection_id = $1"
                               " ORDER BY created_at DESC LIMIT 1", conn_id)           # NUNCA o segredo
    conn["recent_jobs"] = c.query("SELECT id::text AS id, operation, entity, direction, status, attempts, error_code, error_kind, started_at, finished_at,"
                                  " correlation_id FROM integration_jobs WHERE connection_id = $1 ORDER BY created_at DESC LIMIT 10", conn_id)
    conn["links"] = c.query("SELECT sync_status, count(*) AS n FROM external_entity_links WHERE connection_id = $1 GROUP BY 1", conn_id)
    conn["inbound_recent"] = c.query("SELECT external_event_id, event_type, status, received_at FROM integration_inbound WHERE connection_id = $1"
                                     " ORDER BY received_at DESC LIMIT 10", conn_id)
    conn["mappings_count"] = c.scalar("SELECT count(*) FROM integration_mappings WHERE connection_id = $1", conn_id)
    return conn


def operations_overview(c) -> dict:
    """Painel da administração: 'qual integração está quebrada agora?'"""
    return {
        "connections_by_health": c.query("SELECT health_state, count(*) AS n FROM integration_connections WHERE status = 'active' GROUP BY 1 ORDER BY 1"),
        "broken_now": c.query("SELECT c.id::text AS id, o.legal_name AS organization, c.provider_key, c.name, c.environment, c.health_state, c.health_detail,"
                              " c.failure_streak, c.circuit_open_until, c.last_success_at FROM integration_connections c JOIN organizations o ON o.id = c.org_id"
                              " WHERE c.status = 'active' AND c.health_state IN ('unavailable','unauthorized','degraded') ORDER BY c.failure_streak DESC LIMIT 50"),
        "jobs_last_24h": c.query("SELECT status, count(*) AS n FROM integration_jobs WHERE created_at > now() - interval '24 hours' GROUP BY 1"),
        "jobs_failed_recent": c.query("SELECT j.id::text AS id, j.operation, j.entity, j.error_code, j.error_kind, j.attempts, j.finished_at, c.provider_key, c.name"
                                      " FROM integration_jobs j LEFT JOIN integration_connections c ON c.id = j.connection_id"
                                      " WHERE j.status = 'failed' AND j.finished_at > now() - interval '7 days' ORDER BY j.finished_at DESC LIMIT 30"),
        "deliveries": c.query("SELECT status, count(*) AS n FROM integration_deliveries GROUP BY 1"),
        "dead_letters": c.query("SELECT d.id::text AS id, s.name AS subscription, e.event_type, d.attempts, d.response_code, d.error_detail, d.created_at"
                                " FROM integration_deliveries d JOIN integration_subscriptions s ON s.id = d.subscription_id JOIN integration_events e ON e.id = d.event_id"
                                " WHERE d.status = 'dead_letter' ORDER BY d.created_at DESC LIMIT 30"),
        "queue_depth": {"jobs_due": c.scalar("SELECT count(*) FROM integration_jobs WHERE status IN ('pending','retrying') AND (next_attempt_at IS NULL OR next_attempt_at <= now())"),
                        "deliveries_due": c.scalar("SELECT count(*) FROM integration_deliveries WHERE status IN ('pending','retrying') AND next_attempt_at <= now()")},
        "imports_pending_approval": c.scalar("SELECT count(*) FROM integration_imports WHERE status = 'previewed'"),
        "generated_at": datetime.now(UTC).isoformat(),
    }


def latency_stats(c, *, days: int = 7) -> list[dict]:
    return c.query("SELECT c.provider_key, count(*) AS jobs, round(avg(extract(epoch FROM j.finished_at - j.started_at))::numeric, 2) AS avg_seconds,"
                   " count(*) FILTER (WHERE j.status = 'failed') AS failed, round(avg(j.attempts)::numeric, 2) AS avg_attempts"
                   " FROM integration_jobs j JOIN integration_connections c ON c.id = j.connection_id"
                   " WHERE j.finished_at > now() - make_interval(days => $1) GROUP BY 1 ORDER BY 1", days)


def _json(v) -> str:
    return Json(v)
