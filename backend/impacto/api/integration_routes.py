"""Integration Hub — API. Rotas por organização (RLS), entrada pública assinada e visão operacional da administração.

Segurança: segredo nunca é devolvido (só a dica); endpoint é validado pela guarda de SSRF antes de gravar; entrada
externa é deduplicada pelo banco; jobs rodam no trabalhador (nunca uma sincronização longa dentro da requisição).
"""
from __future__ import annotations

import hashlib
import json

from starlette.responses import JSONResponse

from ..db.pq import Json
from ..http import ApiError, Ctx, not_found, page, route
from ..integrations import events as EV
from ..integrations import files as F
from ..integrations import hub as HUB
from ..integrations import hubjobs as J
from ..integrations import inbound as IN
from ..integrations import links as L
from ..integrations import secrets as SEC
from ..integrations.adapters import ADAPTERS
from ..integrations.adapters.bi import DATASETS
from ..integrations.contracts import IntegrationError
from ..integrations.transport import assert_allowed_endpoint
from . import integration_schemas as I

T = ("integrations",)
WRITE = "manager"      # criar/alterar conexões, mapeamentos, assinaturas, importações
OWNER = "owner"        # credenciais e aprovação de importação


def _conn_or_404(c, conn_id: str) -> dict:
    row = c.one("SELECT id::text AS id, org_id::text AS org_id, provider_key, name, environment, status, endpoint, external_system_id, config,"
                " health_state, health_detail, last_health_at, last_success_at, failure_streak, circuit_open_until, created_at, updated_at"
                " FROM integration_connections WHERE id = $1", conn_id)
    if not row:
        raise not_found("Conexão")
    return row


def _problem(exc: IntegrationError) -> ApiError:
    return ApiError(exc.status if exc.status in (400, 403, 404, 409, 422) else 422, exc.code, str(exc))


# ------------------------------------------------------------------------------------------------ catálogo
@route("GET", "/v1/integrations/providers", min_role="viewer", tags=T, summary="Catálogo de provedores com matriz de capacidades e maturidade REAL")
def providers(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT key, name, category, api_style, auth_kinds, capabilities, maturity, docs_url, notes FROM integration_providers WHERE active ORDER BY category, name")
    for r in rows:
        r["adapter_available"] = r["key"] in ADAPTERS
        r["maturity_note"] = {"scaffolded": "SCAFFOLDED / NOT IMPLEMENTED", "contract_tested": "CONTRACT TEST (dublê identificado) — não homologado",
                              "sandbox": "SANDBOX do provedor", "homologated": "HOMOLOGATED", "production_active": "PRODUCTION ACTIVE"}[r["maturity"]]
    return {"items": rows}


@route("GET", "/v1/integrations/datasets", min_role="viewer", tags=T, summary="Datasets exportáveis (BI) — colunas públicas do domínio, filtradas pela organização")
def datasets(ctx: Ctx):
    return {"items": [{"key": k, "description": v[0]} for k, v in sorted(DATASETS.items())]}


# ------------------------------------------------------------------------------------------------ conexões
@route("GET", "/v1/integrations/connections", min_role="viewer", tags=T)
def connections(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT c.id::text AS id, c.provider_key, p.name AS provider_name, c.name, c.environment, c.status, c.endpoint, c.health_state,"
                       " c.health_detail, c.last_health_at, c.last_success_at, c.failure_streak, c.circuit_open_until, c.created_at,"
                       " (SELECT count(*) FROM integration_credentials k WHERE k.connection_id = c.id) > 0 AS has_credential"
                       " FROM integration_connections c JOIN integration_providers p ON p.key = c.provider_key WHERE c.org_id = $1 ORDER BY c.created_at DESC", ctx.org_id)
    return {"items": rows}


@route("POST", "/v1/integrations/connections", body=I.ConnectionIn, min_role=WRITE, status=201, tags=T,
       summary="Cria conexão em rascunho. Endpoint passa pela guarda de SSRF; ambiente production só com adapter disponível.")
def connection_create(ctx: Ctx, body: I.ConnectionIn):
    if body.provider_key not in ADAPTERS:
        raise ApiError(422, "no_adapter", "Este provedor está no catálogo mas ainda não tem adapter executável (SCAFFOLDED)")
    if body.endpoint:
        try:
            assert_allowed_endpoint(body.endpoint, allow_loopback=not ctx.settings.is_hardened)
        except IntegrationError as exc:
            raise _problem(exc) from None
    problems = ADAPTERS[body.provider_key]().validate_config({"endpoint": body.endpoint, "config": body.config, "environment": body.environment})
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM integration_providers WHERE key = $1 AND active", body.provider_key):
            raise ApiError(422, "provider_unknown", "Provedor desconhecido")
        cid = c.scalar("INSERT INTO integration_connections(org_id, provider_key, name, environment, endpoint, external_system_id, config, created_by, health_state)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8, $9) RETURNING id::text",
                       ctx.org_id, body.provider_key, body.name, body.environment, body.endpoint, body.external_system_id, Json(body.config), ctx.user_id,
                       "unconfigured" if problems else "unknown")
        ctx.audit(c, "integration.connection_created", "integration_connection", cid, {"provider": body.provider_key, "environment": body.environment})
    return {"id": cid, "status": "draft", "config_problems": problems}


@route("GET", "/v1/integrations/connections/{id}", min_role="viewer", tags=T, summary="Conexão com saúde, credencial (só dica), jobs recentes, correspondências e entradas")
def connection_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        _conn_or_404(c, ctx.path["id"])
        return HUB.connection_summary(c, ctx.path["id"])


@route("PATCH", "/v1/integrations/connections/{id}", body=I.ConnectionPatchIn, min_role=WRITE, tags=T,
       summary="Altera nome, endpoint, configuração ou estado. Ativar exige configuração válida e credencial quando o provedor pede.")
def connection_patch(ctx: Ctx, body: I.ConnectionPatchIn):
    if body.endpoint:
        try:
            assert_allowed_endpoint(body.endpoint, allow_loopback=not ctx.settings.is_hardened)
        except IntegrationError as exc:
            raise _problem(exc) from None
    with ctx.tx() as c:
        row = _conn_or_404(c, ctx.path["id"])
        if row["status"] == "revoked":
            raise ApiError(409, "revoked", "Conexão revogada não pode ser alterada")
        new = {"name": body.name or row["name"], "endpoint": body.endpoint if body.endpoint is not None else row["endpoint"],
               "external_system_id": body.external_system_id if body.external_system_id is not None else row["external_system_id"],
               "config": body.config if body.config is not None else row["config"], "status": body.status or row["status"]}
        adapter = ADAPTERS.get(row["provider_key"])
        problems = adapter().validate_config({**row, **new}) if adapter else ["provedor sem adapter"]
        if new["status"] == "active":
            if problems:
                raise ApiError(422, "config_invalid", "Conexão não pode ser ativada: " + "; ".join(problems))
            if adapter and adapter.auth_kinds and not c.one("SELECT 1 FROM integration_credentials WHERE connection_id = $1", row["id"]):
                raise ApiError(422, "credential_required", "Grave a credencial antes de ativar a conexão")
        c.run("UPDATE integration_connections SET name = $2, endpoint = $3, external_system_id = $4, config = $5::jsonb, status = $6,"
              " health_state = CASE WHEN $7 THEN 'unconfigured' ELSE health_state END, updated_at = now() WHERE id = $1",
              row["id"], new["name"], new["endpoint"], new["external_system_id"], Json(new["config"]), new["status"], bool(problems))
        ctx.audit(c, "integration.connection_updated", "integration_connection", row["id"], {"status": new["status"]})
    return {"id": row["id"], "status": new["status"], "config_problems": problems}


@route("DELETE", "/v1/integrations/connections/{id}", min_role=OWNER, tags=T, summary="Revoga a conexão (credenciais apagadas; histórico de jobs preservado)")
def connection_revoke(ctx: Ctx):
    with ctx.tx() as c:
        row = _conn_or_404(c, ctx.path["id"])
        c.run("DELETE FROM integration_credentials WHERE connection_id = $1", row["id"])
        c.run("UPDATE integration_connections SET status = 'revoked', health_state = 'unconfigured', updated_at = now() WHERE id = $1", row["id"])
        ctx.audit(c, "integration.connection_revoked", "integration_connection", row["id"])
    return {"id": row["id"], "status": "revoked"}


# ------------------------------------------------------------------------------------------------ credenciais (escrita cega)
@route("PUT", "/v1/integrations/connections/{id}/credential", body=I.CredentialIn, min_role=OWNER, tags=T,
       summary="Grava/rotaciona a credencial (cifrada). A resposta traz só a dica; o segredo nunca volta pela API nem vai para log.")
def credential_put(ctx: Ctx, body: I.CredentialIn):
    with ctx.tx() as c:
        row = _conn_or_404(c, ctx.path["id"])
        adapter = ADAPTERS.get(row["provider_key"])
        if adapter and adapter.auth_kinds and body.kind not in adapter.auth_kinds:
            raise ApiError(422, "auth_kind_unsupported", f"Este provedor aceita: {', '.join(adapter.auth_kinds)}")
        out = SEC.store(c, ctx.app.cipher, connection_id=row["id"], kind=body.kind, secret=body.secret, secret_ref=body.secret_ref,
                        username=body.username, scopes=body.scopes, expires_at=body.expires_at, user_id=ctx.user_id)
        c.run("UPDATE integration_connections SET health_state = 'unknown', failure_streak = 0, circuit_open_until = NULL, updated_at = now() WHERE id = $1", row["id"])
        ctx.audit(c, "integration.credential_rotated", "integration_connection", row["id"], {"kind": body.kind})   # nunca o segredo
    return out


@route("DELETE", "/v1/integrations/connections/{id}/credential", min_role=OWNER, tags=T)
def credential_delete(ctx: Ctx):
    with ctx.tx() as c:
        row = _conn_or_404(c, ctx.path["id"])
        n = c.run("DELETE FROM integration_credentials WHERE connection_id = $1", row["id"])
        c.run("UPDATE integration_connections SET health_state = 'unconfigured', updated_at = now() WHERE id = $1", row["id"])
        ctx.audit(c, "integration.credential_deleted", "integration_connection", row["id"])
    return {"deleted": int(n or 0)}


# ------------------------------------------------------------------------------------------------ saúde
@route("POST", "/v1/integrations/connections/{id}/health", min_role="viewer", rate=("int_health", 60, 3600), tags=T,
       summary="Verificação de saúde (somente leitura; nunca destrutiva). Uma chamada externa curta.")
def health(ctx: Ctx):
    with ctx.tx() as c:
        _conn_or_404(c, ctx.path["id"])
        return HUB.health_check(ctx.app, c, ctx.path["id"], actor=ctx.user_id)


# ------------------------------------------------------------------------------------------------ mapeamentos
@route("GET", "/v1/integrations/connections/{id}/mappings", min_role="viewer", tags=T)
def mappings_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        _conn_or_404(c, ctx.path["id"])
        return {"items": c.query("SELECT id::text AS id, entity, direction, source_path, target_field, transform, enum_map, required, default_value"
                                 " FROM integration_mappings WHERE connection_id = $1 ORDER BY entity, direction, target_field", ctx.path["id"])}


@route("PUT", "/v1/integrations/connections/{id}/mappings", body=I.MappingsIn, min_role=WRITE, tags=T,
       summary="Substitui o conjunto de mapeamentos da conexão (campo externo → campo canônico, com transformação declarada)")
def mappings_put(ctx: Ctx, body: I.MappingsIn):
    with ctx.tx() as c:
        row = _conn_or_404(c, ctx.path["id"])
        c.run("DELETE FROM integration_mappings WHERE connection_id = $1", row["id"])
        for m in body.items:
            c.run("INSERT INTO integration_mappings(connection_id, entity, direction, source_path, target_field, transform, enum_map, required, default_value)"
                  " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9)", row["id"], m.entity, m.direction, m.source_path, m.target_field, m.transform,
                  Json(m.enum_map), m.required, m.default_value)
        ctx.audit(c, "integration.mappings_replaced", "integration_connection", row["id"], {"count": len(body.items)})
    return {"count": len(body.items)}


# ------------------------------------------------------------------------------------------------ jobs
@route("POST", "/v1/integrations/connections/{id}/jobs", body=I.JobIn, min_role=WRITE, status=201, rate=("int_jobs", 120, 3600), tags=T,
       summary="Enfileira um job (executado pelo trabalhador, nunca dentro da requisição). Mesma chave de idempotência → mesmo job.")
def job_create(ctx: Ctx, body: I.JobIn):
    if body.operation in ("pull", "push") and not body.entity:
        raise ApiError(422, "entity_required", "Informe a entidade")
    with ctx.tx() as c:
        row = _conn_or_404(c, ctx.path["id"])
        if row["status"] != "active":
            raise ApiError(409, "connection_inactive", "Ative a conexão antes de executar jobs")
        out = J.enqueue(c, org_id=ctx.org_id, connection_id=row["id"], operation=body.operation, entity=body.entity, direction=body.direction,
                        strategy=body.strategy, request=body.request, user_id=ctx.user_id, key=body.idempotency_key, max_attempts=body.max_attempts)
        if not out["reused"]:
            ctx.audit(c, "integration.job_enqueued", "integration_job", out["id"], {"operation": body.operation, "entity": body.entity})
    return out


@route("GET", "/v1/integrations/jobs", query=I.JobsQ, min_role="viewer", tags=T)
def jobs_list(ctx: Ctx, q: I.JobsQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, connection_id::text AS connection_id, operation, entity, direction, strategy, status, attempts, max_attempts,"
                       " next_attempt_at, correlation_id, error_code, error_kind, started_at, finished_at, created_at FROM integration_jobs"
                       " WHERE org_id = $1 AND ($2::uuid IS NULL OR connection_id = $2) AND ($3::text IS NULL OR status = $3)"
                       " ORDER BY created_at DESC LIMIT $4 OFFSET $5", ctx.org_id, q.connection_id, q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/integrations/jobs/{id}", min_role="viewer", tags=T)
def job_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        row = c.one("SELECT id::text AS id, connection_id::text AS connection_id, operation, entity, direction, strategy, status, attempts, max_attempts,"
                    " next_attempt_at, correlation_id, idempotency_key, request, result, error_code, error_detail, error_kind, started_at, finished_at, created_at"
                    " FROM integration_jobs WHERE id = $1 AND org_id = $2", ctx.path["id"], ctx.org_id)
        if not row:
            raise not_found("Job")
        row["audit_trail"] = c.query("SELECT action, payload, at FROM audit_events WHERE object_type = 'integration_job' AND object_id = $1 ORDER BY at",
                                     ctx.path["id"])
        return row


@route("POST", "/v1/integrations/jobs/{id}/cancel", min_role=WRITE, tags=T)
def job_cancel(ctx: Ctx):
    with ctx.system_tx() as c:     # progresso de job é escrita privilegiada; o filtro por org_id vem da sessão
        out = J.cancel(c, ctx.path["id"], org_id=ctx.org_id)
        if out.get("canceled"):
            ctx.audit(c, "integration.job_canceled", "integration_job", ctx.path["id"])
    if out.get("reason") == "not_found":
        raise not_found("Job")
    return out


# ------------------------------------------------------------------------------------------------ IDs externos
@route("GET", "/v1/integrations/links", query=I.LinksQ, min_role="viewer", tags=T, summary="Correspondências ID interno ↔ ID externo (conflitos nunca são resolvidos em silêncio)")
def links_list(ctx: Ctx, q: I.LinksQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, connection_id::text AS connection_id, entity, internal_id::text AS internal_id, external_id, external_version,"
                       " last_synced_at, sync_status, conflict_detail, updated_at FROM external_entity_links WHERE org_id = $1"
                       " AND ($2::text IS NULL OR entity = $2) AND ($3::text IS NULL OR sync_status = $3) AND ($4::uuid IS NULL OR connection_id = $4)"
                       " ORDER BY updated_at DESC LIMIT $5 OFFSET $6", ctx.org_id, q.entity, q.sync_status, q.connection_id, q.limit + 1, q.offset)
        out = page(rows, q.limit, q.offset)
        out["overview"] = L.overview(c, org_id=ctx.org_id)["by_status"]
        return out


# ------------------------------------------------------------------------------------------------ eventos e webhooks de saída
@route("GET", "/v1/integrations/events/catalog", min_role="viewer", tags=T, summary="Eventos de domínio que a plataforma realmente emite")
def events_catalog(ctx: Ctx):
    return {"items": [{"event_type": k, "entity": v} for k, v in sorted(EV.CATALOG.items())]}


@route("GET", "/v1/integrations/events", query=I.EventsQ, min_role="viewer", tags=T)
def events_list(ctx: Ctx, q: I.EventsQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, event_type, entity, entity_id::text AS entity_id, version, payload, occurred_at FROM integration_events"
                       " WHERE org_id = $1 AND ($2::text IS NULL OR event_type = $2) ORDER BY occurred_at DESC LIMIT $3 OFFSET $4",
                       ctx.org_id, q.event_type, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/integrations/subscriptions", min_role="viewer", tags=T)
def subs_list(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT s.id::text AS id, s.name, s.url, s.event_types, s.status, s.headers, s.created_at,"
                                 " (SELECT count(*) FROM integration_deliveries d WHERE d.subscription_id = s.id AND d.status = 'dead_letter') AS dead_letters,"
                                 " (SELECT max(delivered_at) FROM integration_deliveries d WHERE d.subscription_id = s.id) AS last_delivered_at"
                                 " FROM integration_subscriptions s WHERE s.org_id = $1 ORDER BY s.created_at DESC", ctx.org_id)}


@route("POST", "/v1/integrations/subscriptions", body=I.SubscriptionIn, min_role=WRITE, status=201, tags=T,
       summary="Webhook de saída: HTTPS, assinatura HMAC (t=…,v1=…), retries com backoff e dead-letter")
def sub_create(ctx: Ctx, body: I.SubscriptionIn):
    unknown = [e for e in body.event_types if e not in EV.CATALOG]
    if unknown:
        raise ApiError(422, "unknown_event", f"Eventos fora do catálogo: {', '.join(unknown)}")
    try:
        assert_allowed_endpoint(body.url)
    except IntegrationError as exc:
        raise _problem(exc) from None
    with ctx.tx() as c:
        sid = c.scalar("INSERT INTO integration_subscriptions(org_id, connection_id, name, url, event_types, secret_cipher, headers, created_by)"
                       " VALUES ($1,$2,$3,$4,$5::text[],$6,$7::jsonb,$8) RETURNING id::text", ctx.org_id, body.connection_id, body.name, body.url,
                       body.event_types, ctx.app.cipher.encrypt(body.secret).encode(), Json(body.headers), ctx.user_id)
        ctx.audit(c, "integration.subscription_created", "integration_subscription", sid, {"events": body.event_types})
    return {"id": sid, "status": "active", "signature": "X-Impacto-Signature: t=<unix>,v1=<hmac_sha256(secret, t + '.' + body)>"}


@route("PATCH", "/v1/integrations/subscriptions/{id}", body=I.SubscriptionPatchIn, min_role=WRITE, tags=T)
def sub_patch(ctx: Ctx, body: I.SubscriptionPatchIn):
    if body.url:
        try:
            assert_allowed_endpoint(body.url)
        except IntegrationError as exc:
            raise _problem(exc) from None
    if body.event_types and any(e not in EV.CATALOG for e in body.event_types):
        raise ApiError(422, "unknown_event", "Evento fora do catálogo")
    with ctx.tx() as c:
        row = c.one("SELECT id::text AS id FROM integration_subscriptions WHERE id = $1 AND org_id = $2", ctx.path["id"], ctx.org_id)
        if not row:
            raise not_found("Assinatura")
        c.run("UPDATE integration_subscriptions SET name = coalesce($2, name), url = coalesce($3, url), event_types = coalesce($4::text[], event_types),"
              " status = coalesce($5, status) WHERE id = $1", row["id"], body.name, body.url, body.event_types, body.status)
        ctx.audit(c, "integration.subscription_updated", "integration_subscription", row["id"])
    return {"id": row["id"]}


@route("DELETE", "/v1/integrations/subscriptions/{id}", min_role=WRITE, tags=T)
def sub_delete(ctx: Ctx):
    with ctx.tx() as c:
        n = c.run("DELETE FROM integration_subscriptions WHERE id = $1 AND org_id = $2", ctx.path["id"], ctx.org_id)
        if not n:
            raise not_found("Assinatura")
        ctx.audit(c, "integration.subscription_deleted", "integration_subscription", ctx.path["id"])
    return {"deleted": True}


@route("POST", "/v1/integrations/subscriptions/{id}/test", min_role=WRITE, rate=("int_subtest", 30, 3600), tags=T,
       summary="Emite um evento INTEGRATION.TEST para esta assinatura (entregue pelo trabalhador)")
def sub_test(ctx: Ctx):
    with ctx.tx() as c:
        row = c.one("SELECT id::text AS id FROM integration_subscriptions WHERE id = $1 AND org_id = $2 AND status = 'active'", ctx.path["id"], ctx.org_id)
        if not row:
            raise not_found("Assinatura ativa")
        eid = EV.emit(c, org_id=ctx.org_id, event_type="INTEGRATION.TEST", entity_id=None,
                      payload={"message": "Teste de entrega do Integration Hub", "subscription_id": row["id"]}, actor_id=ctx.user_id)
    return {"event_id": eid, "note": "A entrega acontece no próximo ciclo do trabalhador; acompanhe em /v1/integrations/deliveries"}


@route("GET", "/v1/integrations/deliveries", query=I.DeliveriesQ, min_role="viewer", tags=T)
def deliveries(ctx: Ctx, q: I.DeliveriesQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT d.id::text AS id, d.subscription_id::text AS subscription_id, d.event_id::text AS event_id, e.event_type, d.status, d.attempts,"
                       " d.next_attempt_at, d.response_code, d.error_detail, d.correlation_id, d.delivered_at, d.created_at"
                       " FROM integration_deliveries d JOIN integration_subscriptions s ON s.id = d.subscription_id JOIN integration_events e ON e.id = d.event_id"
                       " WHERE s.org_id = $1 AND ($2::uuid IS NULL OR d.subscription_id = $2) AND ($3::text IS NULL OR d.status = $3)"
                       " ORDER BY d.created_at DESC LIMIT $4 OFFSET $5", ctx.org_id, q.subscription_id, q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/integrations/deliveries/{id}/replay", min_role=WRITE, tags=T, summary="Replay controlado: só dead-letter da própria organização")
def delivery_replay(ctx: Ctx):
    with ctx.system_tx() as c:     # escrita em entregas é privilegiada; o filtro por org_id vem da sessão (replay() confere)
        out = EV.replay(c, delivery_id=ctx.path["id"], org_id=ctx.org_id)
        if out.get("replayed"):
            ctx.audit(c, "integration.delivery_replayed", "integration_delivery", ctx.path["id"])
    if out.get("reason") == "not_found":
        raise not_found("Entrega")
    if not out.get("replayed"):
        raise ApiError(409, "only_dead_letter", "Só entregas em dead-letter podem ser reenviadas")
    return out


# ------------------------------------------------------------------------------------------------ entrada externa (webhook de sistema externo)
@route("POST", "/v1/integrations/inbound/{connection_id}", auth="none", raw=True, raw_body=True, rate=("int_inbound_ip", 600, 60), tags=T,
       summary="Recebe webhook de sistema externo: assinatura verificada pelo adapter, deduplicada pelo banco, enfileira job. Nunca processa negócio na requisição.")
def inbound(ctx: Ctx, payload: bytes):
    headers = {k.lower(): v for k, v in ctx.request.headers.items()}
    with ctx.system_tx() as c:
        try:
            conn = HUB.load_connection(c, ctx.path["connection_id"])
        except IntegrationError:
            return JSONResponse({"status": "rejected", "code": "unknown_connection"}, status_code=404)   # resposta genérica: sem enumeração
        if conn["status"] != "active":
            return JSONResponse({"status": "rejected", "code": "connection_inactive"}, status_code=409)
        try:
            adapter = HUB.adapter_for(conn["provider_key"])
            actx = HUB.build_context(ctx.app, c, conn)
            ext_id, etype, data = adapter.handle_webhook(actx, headers, payload)
        except IntegrationError as exc:
            c.run("INSERT INTO integration_inbound(connection_id, external_event_id, event_type, payload_sha256, status, detail)"
                  " VALUES ($1,$2,$3,$4,'rejected',$5) ON CONFLICT DO NOTHING", conn["id"], f"rejected:{hashlib.sha256(payload).hexdigest()[:40]}",
                  None, hashlib.sha256(payload).hexdigest(), f"{exc.code}"[:500])
            return JSONResponse({"status": "rejected", "code": exc.code}, status_code=exc.status or 400)
        rec = IN.record(c, connection_id=conn["id"], external_event_id=ext_id, event_type=etype, body=payload)
        if rec["duplicate"]:
            return JSONResponse({"status": "duplicate_ignored", "same_payload": rec["same_payload"]}, status_code=200)
        job = J.enqueue(c, org_id=conn["org_id"], connection_id=conn["id"], operation="pull", entity=_entity_from(etype), direction="inbound",
                        strategy="event_driven", request={"inbound_id": rec["id"], "event_type": etype, "external_event_id": ext_id},
                        key=J.idempotency_key("inbound", conn["id"], ext_id))
        IN.finish(c, rec["id"], status="processed", detail="job enfileirado", job_id=job["id"])
    return JSONResponse({"status": "accepted", "job_id": job["id"]}, status_code=202)


def _entity_from(event_type: str) -> str:
    low = (event_type or "").lower()
    for e in ("person", "organization", "document", "invoice", "payment", "course", "certificate", "event", "partner", "call"):
        if e in low:
            return e
    return "document"


# ------------------------------------------------------------------------------------------------ importação e exportação de arquivos
@route("POST", "/v1/integrations/imports", body=I.ImportIn, min_role=WRITE, status=201, rate=("int_import", 60, 3600), tags=T,
       summary="Importa a partir de um documento JÁ validado pelo cofre: valida → interpreta → mapeia → pré-visualiza (sem aplicar)")
def import_create(ctx: Ctx, body: I.ImportIn):
    with ctx.tx() as c:
        if body.connection_id:
            _conn_or_404(c, body.connection_id)
        return F.create_import(ctx.app, c, org_id=ctx.org_id, user_id=ctx.user_id, entity=body.entity, fmt=body.format,
                               document_id=body.document_id, connection_id=body.connection_id)


@route("GET", "/v1/integrations/imports", min_role="viewer", tags=T)
def imports_list(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, entity, format, filename, status, rows_total, rows_valid, rows_invalid, rows_imported, approved_at, created_at"
                                 " FROM integration_imports WHERE org_id = $1 ORDER BY created_at DESC LIMIT 100", ctx.org_id)}


@route("GET", "/v1/integrations/imports/{id}", min_role="viewer", tags=T, summary="Pré-visualização: linhas interpretadas, mapeadas e erros por linha")
def import_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return F.preview(c, org_id=ctx.org_id, import_id=ctx.path["id"])


@route("POST", "/v1/integrations/imports/{id}/approve", body=I.ApproveImportIn, min_role=OWNER, tags=T,
       summary="Aprova e aplica (só linhas válidas; cria correspondências de ID externo; nunca cria usuários/organizações)")
def import_approve(ctx: Ctx, body: I.ApproveImportIn):
    with ctx.tx() as c:
        return F.approve_and_import(c, org_id=ctx.org_id, user_id=ctx.user_id, import_id=ctx.path["id"], connection_id_override=body.connection_id)


@route("POST", "/v1/integrations/exports", body=I.ExportIn, min_role=WRITE, status=201, rate=("int_export", 30, 3600), tags=T,
       summary="Gera um dataset (CSV/JSON) da própria organização; download pela URL temporária de documentos")
def export_create(ctx: Ctx, body: I.ExportIn):
    with ctx.tx() as c:
        return F.generate_export(ctx.app, c, org_id=ctx.org_id, user_id=ctx.user_id, dataset=body.dataset, fmt=body.format, filters=body.filters)


@route("GET", "/v1/integrations/exports", min_role="viewer", tags=T)
def exports_list(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, dataset, format, status, rows, document_id::text AS document_id, created_at, finished_at"
                                 " FROM integration_exports WHERE org_id = $1 ORDER BY created_at DESC LIMIT 100", ctx.org_id)}


# ------------------------------------------------------------------------------------------------ administração (visão operacional)
@route("GET", "/v1/admin/integrations/overview", auth="admin", tags=T, summary="Qual integração está quebrada agora? Saúde, filas, falhas, dead-letters")
def admin_overview(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        out = HUB.operations_overview(c)
        out["latency_7d"] = HUB.latency_stats(c)
        return out


@route("POST", "/v1/admin/integrations/providers/{key}/maturity", auth="admin", body=I.MaturityIn, tags=T,
       summary="Promove/rebaixa a maturidade de um provedor COM evidência registrada (nunca automático)")
def admin_maturity(ctx: Ctx, body: I.MaturityIn):
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM integration_providers WHERE key = $1", ctx.path["key"]):
            raise not_found("Provedor")
        c.run("UPDATE integration_providers SET maturity = $2, updated_at = now() WHERE key = $1", ctx.path["key"], body.maturity)
        ctx.audit(c, "integration.provider_maturity", "integration_provider", ctx.path["key"], {"maturity": body.maturity, "evidence": body.evidence})
    return {"key": ctx.path["key"], "maturity": body.maturity}


@route("POST", "/v1/admin/integrations/run-worker", auth="admin", tags=T, summary="Executa um ciclo do trabalhador agora (jobs devidos + entregas devidas)")
def admin_run_worker(ctx: Ctx):
    with ctx.system_tx() as c:
        jobs = HUB.process_due(ctx.app, c)
        deliveries = EV.deliver_pending(ctx.app, c)
        ctx.audit(c, "integration.worker_run", "integration_worker", None, {"jobs": jobs, "deliveries": deliveries})
    return {"jobs": jobs, "deliveries": deliveries}


def _dump(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)
