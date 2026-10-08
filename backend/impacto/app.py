"""Fábrica da aplicação ASGI (Starlette) — API /v1, SPA/PWA estática, health, métricas e OpenAPI."""
from __future__ import annotations

import contextlib
import hmac
import json
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from . import config as config_mod
from .adapters import antivirus, mail, storage
from .db.pool import DbContext, Pool
from .http import ROUTES, make_endpoint, problem
from .observability import METRICS, log, setup_logging
from .security.crypto import FieldCipher

logger = logging.getLogger("impacto.app")


class AppState:
    def __init__(self, settings: config_mod.Settings, pool: Pool | None = None):
        self.settings = settings
        self.pool = pool or Pool(_dsn(settings.database_url), max_size=settings.database_pool_size)
        self.cipher = FieldCipher(settings.field_encryption_key, fallback_secret=settings.secret_key if not settings.is_hardened else "")
        if settings.mail_provider == "smtp":
            self.mailer = mail.SmtpMailer(settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_password, settings.smtp_from)
        else:
            self.mailer = mail.ConsoleMailer(Path(settings.storage_local_dir).parent / "outbox", settings.smtp_from)
        if settings.storage_provider == "s3":
            self.storage = storage.S3Storage(settings.s3_endpoint, settings.s3_region, settings.s3_bucket,
                                             settings.s3_access_key_id, settings.s3_secret_access_key)
        else:
            self.storage = storage.LocalStorage(settings.storage_local_dir)
        self.antivirus = (antivirus.ClamdAntivirus(settings.clamd_host, settings.clamd_port)
                          if settings.antivirus_provider == "clamd" else antivirus.NoAntivirus())
        from .services import documents as _docs
        _docs.ACCEPT_UNSCANNED = settings.allow_unscanned_downloads
        from .engines.ai.gateway import AiGateway
        self.ai = AiGateway(settings)
        # v0.27.0 (ADR-341): não há provedor de assinatura. O que existe é o estado do provedor de
        # cobrança própria (economics/payments.status), lido onde é preciso.
        # Toda tentativa de envio passa a deixar registro em email_events. Fica aqui, e não nos oito
        # pontos que enviam e-mail, para que nenhum deles possa esquecer.
        self.mailer.on_event = self._record_email_event

    def _record_email_event(self, event: dict) -> None:
        """Grava a tentativa de envio. Guarda o DOMÍNIO do destinatário, nunca o endereço."""
        from .db.pool import DbContext
        with self.pool.tx(DbContext(system=True)) as c:
            c.run("INSERT INTO email_events(message_id, kind, to_domain, status, provider,"
                  " retry_count, duration_ms, error) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
                  event.get("message_id"), event["kind"], event["to_domain"], event["status"],
                  event["provider"], event.get("retry_count", 0), event.get("duration_ms"),
                  event.get("error"))


def db_role_problems(pool) -> list[str]:
    """Verifica se o papel de conexão da aplicação respeita RLS (não superusuário, sem BYPASSRLS, não dono das tabelas)."""
    from .db.pool import DbContext
    with pool.tx(DbContext(system=True)) as c:
        r = c.one("SELECT r.rolsuper, r.rolbypassrls, EXISTS(SELECT 1 FROM pg_tables WHERE schemaname = 'public' AND tableowner = current_user)"
                  " AS owns FROM pg_roles r WHERE r.rolname = current_user")
    problems = []
    if r["rolsuper"]:
        problems.append("DATABASE_URL usa superusuário (RLS seria ignorada)")
    if r["rolbypassrls"]:
        problems.append("DATABASE_URL usa papel com BYPASSRLS")
    if r["owns"]:
        problems.append("DATABASE_URL usa o papel dono das tabelas (use impacto_app; migrações com impacto_owner)")
    return problems


def _dsn(url: str) -> str:
    """Aceita URL postgresql:// ou conninfo; força UTC e timeout de statement."""
    opts = "options='-c timezone=UTC -c statement_timeout=15000 -c idle_in_transaction_session_timeout=30000'"
    if url.startswith("postgres"):
        sep = "&" if "?" in url else "?"
        return url + sep + "options=-c%20timezone%3DUTC%20-c%20statement_timeout%3D15000%20-c%20idle_in_transaction_session_timeout%3D30000" \
            + "&application_name=impacto-api&connect_timeout=5"
    return f"{url} {opts} application_name=impacto-api connect_timeout=5"


# ------------------------------------------------------------------------------------------------
# Middlewares ASGI puros (sem dependências extras)
# ------------------------------------------------------------------------------------------------
class SecurityHeaders:
    def __init__(self, app: ASGIApp, hardened: bool):
        self.app, self.hardened = app, hardened
        csp = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self';"
               " connect-src 'self'; manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'self';"
               " form-action 'self'; object-src 'none'")
        self.headers = [
            (b"x-content-type-options", b"nosniff"), (b"x-frame-options", b"DENY"),
            (b"referrer-policy", b"strict-origin-when-cross-origin"),
            (b"permissions-policy", b"camera=(self), microphone=(), geolocation=(), payment=()"),
            (b"cross-origin-opener-policy", b"same-origin"), (b"content-security-policy", csp.encode()),
        ]
        if hardened:
            self.headers.append((b"strict-transport-security", b"max-age=63072000; includeSubDomains; preload"))

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                message.setdefault("headers", [])
                for k, v in self.headers:
                    if k not in existing:
                        message["headers"].append((k, v))
            await send(message)
        await self.app(scope, receive, send_wrapper)


class Cors:
    """CORS restrito à lista CORS_ORIGINS (necessário apenas para clientes em outra origem, ex.: app mobile em dev)."""

    def __init__(self, app: ASGIApp, origins: list[str]):
        self.app, self.origins = app, {o.rstrip("/") for o in origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http" or not self.origins:
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers") or [])
        origin = headers.get(b"origin", b"").decode()
        allowed = origin.rstrip("/") in self.origins
        if scope["method"] == "OPTIONS" and allowed:
            resp = Response(status_code=204, headers={
                "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "GET, POST, PUT, PATCH, DELETE",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, X-CSRF-Token, X-Auth-Mode, X-Request-ID",
                "Access-Control-Max-Age": "600", "Vary": "Origin"})
            return await resp(scope, receive, send)

        async def send_wrapper(message):
            if message["type"] == "http.response.start" and allowed:
                message.setdefault("headers", []).extend([
                    (b"access-control-allow-origin", origin.encode()), (b"access-control-allow-credentials", b"true"),
                    (b"vary", b"Origin")])
            await send(message)
        await self.app(scope, receive, send_wrapper)


# ------------------------------------------------------------------------------------------------
# Rotas de infraestrutura
# ------------------------------------------------------------------------------------------------
def _infra_routes(state: AppState) -> list[Route]:
    s = state.settings

    async def healthz(request: Request):
        return JSONResponse({"status": "ok", "version": s.version, "env": s.env})

    def _ready():
        from .db.migrate import _files
        with state.pool.tx(DbContext(system=True), readonly=True) as c:
            applied = {r["version"] for r in c.query("SELECT version FROM schema_migrations")}
        expected = {f.stem for f in _files()}
        return sorted(expected - applied)

    async def readyz(request: Request):
        from starlette.concurrency import run_in_threadpool
        try:
            pending = await run_in_threadpool(_ready)
        except Exception as exc:  # noqa: BLE001
            log(logger, logging.ERROR, "readiness_failed", error_type=type(exc).__name__)
            return JSONResponse({"status": "unavailable", "database": "down"}, status_code=503)
        if pending:
            return JSONResponse({"status": "unavailable", "pending_migrations": pending}, status_code=503)
        return JSONResponse({"status": "ready", "database": "ok", "storage": state.storage.kind,
                             "antivirus": state.antivirus.name, "ai": state.ai.provider_name,
                             "billing": "none-subscription", "payments": "stripe" if s.stripe_secret_key else "simulated",
                             "mail": s.mail_provider})

    async def metrics(request: Request):
        if s.metrics_token:
            sent = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
            if not hmac.compare_digest(sent, s.metrics_token):
                return PlainTextResponse("unauthorized", status_code=401)
        elif s.is_hardened:
            return PlainTextResponse("not found", status_code=404)
        METRICS.set("impacto_db_pool_connections", state.pool._created)
        return PlainTextResponse(METRICS.render(), media_type="text/plain; version=0.0.4")

    async def openapi(request: Request):
        from .openapi import build
        return JSONResponse(build(s.version))

    async def taxonomy(request: Request):
        data = json.loads((config_mod.ROOT / "config" / "taxonomy.json").read_text(encoding="utf-8"))
        return JSONResponse(data, headers={"Cache-Control": "public, max-age=3600"})

    async def public_config(request: Request):
        from .services.oidc import enabled as oidc_enabled
        return JSONResponse({"sso_enabled": oidc_enabled(s), "billing_provider": "none", "subscription": False, "env": s.env,
                             "terms_version": s.terms_version, "privacy_version": s.privacy_version, "version": s.version},
                            headers={"Cache-Control": "public, max-age=300"})

    return [Route("/v1/meta/config", public_config), Route("/healthz", healthz), Route("/readyz", readyz), Route("/metrics", metrics),
            Route("/v1/openapi.json", openapi), Route("/v1/meta/taxonomy", taxonomy)]


def _static_routes(state: AppState) -> list[Route]:
    dist = Path(state.settings.web_dist_dir).resolve()

    async def spa(request: Request):
        path = request.path_params.get("path", "")
        if path.startswith("v1/") or path == "v1":
            return problem(404, "not_found", "Rota de API inexistente")
        candidate = (dist / path).resolve() if path else dist / "index.html"
        if path and dist in candidate.parents and candidate.is_file():
            headers = {"Cache-Control": "public, max-age=31536000, immutable"} if "/assets/" in f"/{path}" else {"Cache-Control": "no-cache"}
            return FileResponse(candidate, headers=headers)
        index = dist / "index.html"
        if not index.exists():
            return PlainTextResponse("Frontend não compilado. Rode: cd web && node build.mjs", status_code=503)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return [Route("/", spa), Route("/{path:path}", spa)]


def create_app(settings: config_mod.Settings | None = None, state: AppState | None = None) -> Starlette:
    settings = settings or config_mod.load_settings()
    setup_logging(settings.log_level, settings.version, settings.env)
    state = state or AppState(settings)
    from . import api  # noqa: F401  (registra rotas)
    api.load_all()
    routes = _infra_routes(state)
    # Mais específica primeiro: segmentos literais antes de parâmetros na mesma posição (ex.: /v1/solutions/search antes de /v1/solutions/{solution_id}).
    def _specificity(spec):
        return [1 if seg.startswith("{") else 0 for seg in spec.path.split("/")]
    for spec in sorted(ROUTES, key=_specificity):
        routes.append(Route(spec.path, make_endpoint(spec, state), methods=[spec.method]))
    routes += _static_routes(state)

    @contextlib.asynccontextmanager
    async def lifespan(app):
        log(logger, logging.INFO, "startup", version=settings.version, env=settings.env, routes=len(ROUTES))
        problems = db_role_problems(state.pool)
        if problems:
            if settings.is_hardened:
                raise config_mod.ConfigError("Banco inseguro: " + "; ".join(problems))
            log(logger, logging.WARNING, "db_role_insecure", problems=problems)
        if settings.seed_demo and settings.env in ("development", "test"):
            from .seed_dev import seed
            seed(state)
        yield
        state.pool.close()

    app = Starlette(routes=routes, lifespan=lifespan, middleware=[
        Middleware(SecurityHeaders, hardened=settings.is_hardened),
        Middleware(Cors, origins=settings.cors_origins),
    ])
    app.state.impacto = state
    return app
