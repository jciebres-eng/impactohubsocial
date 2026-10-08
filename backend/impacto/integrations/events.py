"""Eventos de domínio (padrão outbox) e webhooks de SAÍDA assinados.

O núcleo apenas registra o evento na mesma transação do fato (`emit`). A entrega é feita depois, por job, com
tentativas, backoff, dead-letter e replay controlado. Assinatura HMAC no mesmo formato já usado na entrada do Stripe
(`t=<timestamp>,v1=<hmac>`), para que o parceiro possa verificar e descartar repetição.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from datetime import UTC, datetime

from ..db.pq import Json
from ..observability import log
from .contracts import IntegrationError
from .transport import ResilientCaller, backoff_delay

logger = logging.getLogger("impacto.integrations.events")

# Eventos REAIS do domínio (só o que a plataforma de fato produz hoje).
CATALOG = {
    "ORGANIZATION.CREATED": "organization", "ORGANIZATION.UPDATED": "organization",
    "ORGANIZATION.COMPLIANCE_CHANGED": "organization",
    "USER.CREATED": "person", "USER.ROLE_CHANGED": "person",
    "DOCUMENT.CREATED": "document", "DOCUMENT.VALIDATED": "document", "DOCUMENT.EXPIRING": "document",
    "PROJECT.PUBLISHED": "project", "APPLICATION.SUBMITTED": "application", "APPLICATION.DECIDED": "application",
    "COURSE.COMPLETED": "course", "CERTIFICATE.ISSUED": "certificate", "CERTIFICATE.REVOKED": "certificate",
    "EVENT.REGISTRATION.CREATED": "event", "SUPPORT.TICKET.CREATED": "support_ticket",
    # v0.27.0 (ADR-341): SUBSCRIPTION.* e TRIAL.* saíram do catálogo — não existe assinatura. No lugar,
    # os fatos da camada econômica da operação financiada.
    "OPERATION.ACTIVATED": "signed_agreement", "OPERATION.SETTLED": "signed_agreement",
    "PAYOUT.CONFIRMED": "payout",
    "PAYMENT.CONFIRMED": "payment", "PAYMENT.FAILED": "payment",
    "LICENSE.GRANTED": "license", "LICENSE.REVOKED": "license",
    "INTEGRATION.JOB.FAILED": "integration_job", "INTEGRATION.TEST": "integration_test",
}
MAX_ATTEMPTS = 6


def emit(c, *, org_id: str | None, event_type: str, entity_id: str | None, payload: dict,
         actor_id: str | None = None, version: int = 1) -> str | None:
    """Registra o evento e enfileira a entrega para quem estiver inscrito. Chamado na MESMA transação do fato.

    O payload é montado pelo servidor e deve conter o mínimo necessário (LGPD): identificadores e campos do domínio,
    nunca segredo, token ou dado sensível desnecessário.
    """
    if event_type not in CATALOG:
        raise IntegrationError("unknown_event", f"Evento fora do catálogo: {event_type}", kind="permanent")
    eid = c.scalar("INSERT INTO integration_events(org_id, event_type, entity, entity_id, version, payload, actor_id)"
                   " VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7) RETURNING id::text",
                   org_id, event_type, CATALOG[event_type], entity_id, version, Json(payload or {}), actor_id)
    subs = c.query("SELECT id::text AS id FROM integration_subscriptions WHERE status = 'active' AND org_id = $1"
                   " AND $2 = ANY(event_types)", org_id, event_type) if org_id else []
    for s in subs:
        c.run("INSERT INTO integration_deliveries(subscription_id, event_id, correlation_id) VALUES ($1,$2,$3)"
              " ON CONFLICT (subscription_id, event_id) DO NOTHING", s["id"], eid, secrets.token_hex(8))
    return eid


def sign(secret: str, payload: bytes, timestamp: int | None = None) -> tuple[str, int]:
    ts = timestamp or int(time.time())
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}", ts


def verify(secret: str, payload: bytes, header: str, *, tolerance: int = 300) -> bool:
    """Verificação usada por quem RECEBE (e pelos testes): assinatura válida e dentro da janela de tolerância."""
    parts = dict(p.split("=", 1) for p in (header or "").split(",") if "=" in p)
    try:
        ts = int(parts.get("t", "0"))
    except ValueError:
        return False
    if abs(time.time() - ts) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, parts.get("v1", ""))


def deliver_pending(app, c, *, limit: int = 100, now: datetime | None = None, http=None) -> dict:
    """Entrega as pendências devidas. Erro temporário reagenda com backoff; permanente ou tentativas esgotadas → dead-letter."""
    now = now or datetime.now(UTC)
    rows = c.query("SELECT d.id::text AS id, d.attempts, d.correlation_id, s.id::text AS sub_id, s.url, s.headers,"
                   " e.id::text AS event_id, e.event_type, e.entity, e.entity_id::text AS entity_id, e.payload, e.occurred_at, e.version"
                   " FROM integration_deliveries d JOIN integration_subscriptions s ON s.id = d.subscription_id"
                   " JOIN integration_events e ON e.id = d.event_id"
                   " WHERE d.status IN ('pending','retrying') AND d.next_attempt_at <= $1 AND s.status = 'active'"
                   " ORDER BY d.next_attempt_at LIMIT $2", now, limit)
    sent = failed = dead = 0
    for d in rows:
        body = json.dumps({"id": d["event_id"], "type": d["event_type"], "entity": d["entity"], "entity_id": d["entity_id"],
                           "version": d["version"], "occurred_at": d["occurred_at"].isoformat(), "data": d["payload"]},
                          ensure_ascii=False, default=str).encode()
        blob = c.scalar("SELECT integration_subscription_secret($1)", d["sub_id"])
        if blob is None:
            c.run("UPDATE integration_deliveries SET status = 'skipped', error_detail = 'assinatura sem segredo' WHERE id = $1", d["id"])
            continue
        secret = app.cipher.decrypt((bytes(blob)).decode())
        header, _ = sign(secret, body)
        headers = {k: str(v)[:200] for k, v in (d["headers"] or {}).items() if k.lower() not in ("authorization", "cookie")}
        headers.update({"Content-Type": "application/json", "X-Impacto-Signature": header,
                        "X-Impacto-Event-Id": d["event_id"], "X-Impacto-Event-Type": d["event_type"],
                        "X-Correlation-Id": d["correlation_id"]})
        caller = ResilientCaller({"id": d["sub_id"]}, http=http, correlation_id=d["correlation_id"], attempts=1, timeout=15.0)
        attempts = d["attempts"] + 1
        try:
            status, _, _ = caller.call("POST", d["url"], headers=headers, data=body, expected=(200, 201, 202, 204))
            c.run("UPDATE integration_deliveries SET status = 'delivered', attempts = $2, response_code = $3, delivered_at = now(),"
                  " error_detail = NULL WHERE id = $1", d["id"], attempts, status)
            sent += 1
        except IntegrationError as exc:
            permanent = not exc.temporary
            if permanent or attempts >= MAX_ATTEMPTS:
                c.run("UPDATE integration_deliveries SET status = 'dead_letter', attempts = $2, response_code = $3,"
                      " error_detail = $4 WHERE id = $1", d["id"], attempts, exc.status, f"{exc.code}: {exc}"[:500])
                dead += 1
                log(logger, logging.WARNING, "webhook_dead_letter", delivery_id=d["id"], event_type=d["event_type"],
                    attempts=attempts, code=exc.code)
            else:
                delay = backoff_delay(attempts, base=30.0, cap=3600.0)
                c.run("UPDATE integration_deliveries SET status = 'retrying', attempts = $2, response_code = $3,"
                      " error_detail = $4, next_attempt_at = now() + make_interval(secs => $5) WHERE id = $1",
                      d["id"], attempts, exc.status, f"{exc.code}: {exc}"[:500], delay)
                failed += 1
    return {"delivered": sent, "retrying": failed, "dead_letter": dead, "due": len(rows)}


def replay(c, *, delivery_id: str, org_id: str) -> dict:
    """Replay CONTROLADO: só a própria organização, só entrega em dead-letter, com nova tentativa agendada."""
    row = c.one("SELECT d.id::text AS id, d.status FROM integration_deliveries d JOIN integration_subscriptions s ON s.id = d.subscription_id"
                " WHERE d.id = $1 AND s.org_id = $2", delivery_id, org_id)
    if not row:
        return {"replayed": False, "reason": "not_found"}
    if row["status"] != "dead_letter":
        return {"replayed": False, "reason": "only_dead_letter"}
    c.run("UPDATE integration_deliveries SET status = 'pending', attempts = 0, next_attempt_at = now(), error_detail = NULL WHERE id = $1", delivery_id)
    return {"replayed": True, "id": delivery_id}


def retention(c, *, days: int = 180) -> dict:
    """Entregas antigas já concluídas são apagadas; dead-letter é preservado para investigação."""
    return {"deliveries_deleted": c.run("DELETE FROM integration_deliveries WHERE status = 'delivered'"
                                        " AND delivered_at < now() - make_interval(days => $1)", days)}
