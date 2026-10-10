"""Camada HTTP: registro de rotas tipadas, autenticação/autorização por rota, CSRF, erros RFC 7807 e OpenAPI.

Cada rota declara explicitamente:
* ``auth``: none | user | org | admin
* ``kinds``: tipos de organização permitidos (osc, company, provider, government, platform)
* ``min_role``: papel mínimo na organização (viewer < member < analyst < manager < admin < owner)
* ``body``/``query``: modelos pydantic (validação estrita; campos extras rejeitados)
* ``feature``: chave de entitlement exigida (verificada pelo EntitlementService)
Handlers são síncronos e rodam em threadpool (o driver libpq libera o GIL durante I/O).
"""
from __future__ import annotations

import json
import logging
import re as _re
import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from collections.abc import Callable

from pydantic import BaseModel, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import Response

from .db import pq
from .db.pool import DbContext, Pool
from .observability import METRICS, error_fingerprint, log, new_trace, request_id_var, spans_var, summarize_spans, trace_id_var
from .security.tokens import csrf_for_session, sha256_hex

logger = logging.getLogger("impacto.http")

_UUID = _re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
ROLE_ORDER = ["viewer", "member", "analyst", "manager", "admin", "owner"]
# Texto interno do PostgreSQL (nomes de tabela/coluna/constraint). Mensagens AUTORADAS pelos gatilhos do projeto
# também chegam como check_violation (RAISE ... ERRCODE 23514) e continuam visíveis: só o texto interno é generalizado.
_PG_INTERNAL = _re.compile(r"violates (check|foreign key|not-null|exclusion|unique) constraint|null value in column|new row for relation|insert or update on table|duplicate key value", _re.I)
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: Any = None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


#: substantivos terminados em -a que são masculinos (o resto do -a, -ção, -dade, -gem é feminino)
_MASCULINOS_EM_A = {"programa", "sistema", "esquema", "tema", "problema", "mapa", "dia", "prompt", "plano"}


def _encontrado(what: str) -> str:
    """Concordância de "não encontrado" com o nome do recurso (v0.25.0).

    A mensagem saía "Conversa não encontrado", "Proposta não encontrado" — e, quando o chamador já
    passava a frase pronta, "Alegação não encontrada não encontrado". O robô de telas da v0.25.0 viu
    as duas coisas na interface.
    """
    if "não " in what:
        return what
    primeira = what.split()[0].split("/")[0].lower() if what.strip() else ""
    feminino = primeira not in _MASCULINOS_EM_A and primeira.endswith(("a", "ção", "são", "dade", "gem", "ie"))
    return f"{what} não encontrad{'a' if feminino else 'o'}"


def not_found(what: str = "Recurso") -> ApiError:
    return ApiError(404, "not_found", _encontrado(what))


def forbidden(msg: str = "Permissão insuficiente", code: str = "forbidden") -> ApiError:
    return ApiError(403, code, msg)


def unprocessable(msg: str, details: Any = None, code: str = "unprocessable") -> ApiError:
    return ApiError(422, code, msg, details)


def require_fresh_identity(ctx: Any) -> None:
    """Identidade confirmada (senha + segundo fator, se ativo) há menos de 15 minutos — o mesmo critério das permissões de
    `STEP_UP_PERMISSIONS`. A tela recebe `step_up_required`, pede a confirmação e repete a chamada (web/src/api.ts)."""
    from .core import access as ACCESS
    if not ACCESS.of(ctx)._reauth_fresh():
        raise ApiError(401, "step_up_required", "Confirme sua identidade para esta operação",
                       {"allowed": False, "reason": "permission_denied", "source": "step_up", "step_up_required": True})


def _default(o):
    if isinstance(o, (datetime, date)):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    if isinstance(o, (uuid.UUID, bytes)):
        return str(o)
    if isinstance(o, BaseModel):
        return o.model_dump()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    raise TypeError(f"não serializável: {type(o).__name__}")


def json_response(data: Any, status: int = 200, headers: dict | None = None) -> Response:
    body = b"" if status == 204 else json.dumps(data, ensure_ascii=False, default=_default).encode()
    h = {"Cache-Control": "no-store"}
    if headers:
        h.update(headers)
    return Response(body, status_code=status, media_type=None if status == 204 else "application/json", headers=h)


def problem(status: int, code: str, message: str, details: Any = None, error_id: str | None = None) -> Response:
    body = {"type": f"https://impacto.app/errors/{code}", "title": message, "status": status, "code": code,
            "request_id": request_id_var.get()}
    if details is not None:
        body["details"] = details
    if error_id:
        body["error_id"] = error_id
    return Response(json.dumps(body, ensure_ascii=False, default=_default).encode(), status_code=status,
                    media_type="application/problem+json", headers={"Cache-Control": "no-store"})


@dataclass
class Principal:
    user_id: str
    email: str
    full_name: str
    session_id: str
    is_platform_admin: bool
    mfa_enabled: bool
    mfa_verified: bool
    email_verified: bool
    org_id: str | None
    org_kind: str | None
    org_name: str | None
    role: str | None
    via: str  # bearer | cookie
    staff_roles: tuple[str, ...] = ()   # editor | reviewer | support (papéis internos concedidos pela administração)

    def has_role(self, minimum: str) -> bool:
        return self.role is not None and ROLE_ORDER.index(self.role) >= ROLE_ORDER.index(minimum)


@dataclass
class Ctx:
    request: Request
    app: Any  # AppState
    principal: Principal | None = None
    admin_mode: bool = False
    path: dict = field(default_factory=dict)
    request_id: str = "-"

    @property
    def settings(self):
        return self.app.settings

    @property
    def pool(self) -> Pool:
        return self.app.pool

    @property
    def ip(self) -> str:
        """IP do cliente para limite de tentativas e trilha.

        v0.35.0 (auditoria, AUTH-02): antes vinha do PRIMEIRO valor do X-Forwarded-For — o único que quem faz o pedido
        escreve; trocando o cabeçalho a cada tentativa, os limites por IP de login, cadastro, recuperação e IA eram
        contornados. Agora: o cabeçalho que a borda sobrescreve (se configurado) ou o N-ésimo valor a partir da DIREITA
        (N = TRUSTED_PROXY_HOPS, os proxies confiáveis que acrescentam ao cabeçalho)."""
        s = self.app.settings
        if s.trust_proxy_headers:
            if s.client_ip_header:
                v = (self.request.headers.get(s.client_ip_header) or "").strip()
                if v:
                    return v[:64]
            fwd = [x.strip() for x in (self.request.headers.get("x-forwarded-for") or "").split(",") if x.strip()]
            if fwd:
                return fwd[max(0, len(fwd) - s.trusted_proxy_hops)][:64]
        return (self.request.client.host if self.request.client else "unknown")[:64]

    @property
    def user_agent(self) -> str:
        return (self.request.headers.get("user-agent") or "")[:300]

    @property
    def user_id(self) -> str:
        assert self.principal
        return self.principal.user_id

    @property
    def org_id(self) -> str:
        if not self.principal or not self.principal.org_id:
            raise ApiError(409, "no_active_org", "Selecione uma organização ativa")
        return self.principal.org_id

    def db_context(self) -> DbContext:
        p = self.principal
        if not p:
            return DbContext.anonymous()
        return DbContext(user_id=p.user_id, org_id=p.org_id, org_kind=p.org_kind, platform_admin=self.admin_mode)

    def tx(self, readonly: bool = False, isolation: str | None = None):
        return self.pool.tx(self.db_context(), readonly=readonly, isolation=isolation)

    def system_tx(self, isolation: str | None = None):
        """Contexto de sistema (ignora tenant). Uso restrito e verificado por teste (tests/test_architecture.py)."""
        p = self.principal
        return self.pool.tx(DbContext(user_id=p.user_id if p else None, org_id=p.org_id if p else None,
                                      org_kind=p.org_kind if p else None, system=True), isolation=isolation)

    def require_role(self, minimum: str) -> None:
        if self.admin_mode:
            return
        if not self.principal or not self.principal.has_role(minimum):
            raise forbidden(f"Requer papel '{minimum}' ou superior na organização")

    @property
    def correlation_id(self) -> str:
        """Identificador do RASTRO, não da requisição.

        `request_id` identifica uma requisição. Uma operação do produto costuma ser várias: enviar
        documento, classificar, aprovar, gerar recibo. O cliente que quiser amarrar as quatro manda
        `x-correlation-id`; quem não manda recebe o próprio `request_id`, e aí rastro e requisição
        coincidem — que é o caso simples, não um caso perdido.
        """
        bruto = self.request.headers.get("x-correlation-id") or ""
        limpo = "".join(ch for ch in bruto if ch.isalnum() or ch in "-_")[:64]
        return limpo or self.request_id

    def audit(self, conn: pq.Connection, action: str, object_type: str | None = None, object_id: Any = None,
              payload: dict | None = None, org_id: str | None = None, *,
              actor_type: str | None = None, resource_name: str | None = None,
              severity: str | None = None, status: str = "success", source: str = "api",
              parent_event_id: int | None = None,
              before: dict | None = None, after: dict | None = None) -> int:
        """Ponto de estrangulamento da auditoria: 319 chamadores passam por aqui.

        É por isso que os campos acrescentados na v0.23.0 — `actor_type`, `session_id`,
        `user_agent`, `correlation_id`, `severity` — são preenchidos AQUI e não em cada chamada.
        Pedir a cada chamador que preenchesse `actor_type` garantiria que algum esquecesse, e um
        evento sem tipo de ator numa investigação vale menos que nenhum, porque engana.
        """
        from .services.audit import actor_type_of, record
        p = self.principal
        return record(
            conn,
            org_id=org_id if org_id is not None else (p.org_id if p else None),
            actor=p.user_id if p else None, action=action, object_type=object_type,
            object_id=object_id, payload=payload or {}, ip=self.ip, request_id=self.request_id,
            actor_type=actor_type or actor_type_of(p),
            session_id=getattr(p, "session_id", None) if p else None,
            user_agent=self.user_agent, correlation_id=self.correlation_id,
            parent_event_id=parent_event_id, resource_name=resource_name,
            severity=severity, status=status, source=source, before=before, after=after)


@dataclass
class RouteSpec:
    method: str
    path: str
    handler: Callable
    auth: str = "org"
    kinds: tuple[str, ...] | None = None
    min_role: str | None = None
    body: type[BaseModel] | None = None
    query: type[BaseModel] | None = None
    feature: str | None = None
    summary: str = ""
    tags: tuple[str, ...] = ()
    status: int = 200
    raw: bool = False            # handler devolve Response pronta
    multipart: bool = False      # upload de arquivo (handler recebe form já lido)
    allow_unverified: bool = False
    rate: tuple[str, int, int] | None = None  # (bucket, limite, janela_segundos) por IP
    raw_body: bool = False       # handler recebe bytes do corpo (ex.: webhooks com assinatura)
    staff: tuple[str, ...] = ()  # auth="admin": além de administradores, aceita estes papéis internos (sempre com MFA)
    # v0.22.0 — PERMISSÃO INTERNA exigida (ex.: "finance.read"). Vem de `staff_roles` via a matriz
    # `staff_permissions`. Quando declarada, `is_platform_admin` sozinho NÃO basta: é preciso ter a
    # permissão. A migração 0046 concedeu `super_admin` a todo administrador existente, então
    # ninguém perdeu acesso — mas a próxima pessoa contratada pode receber `support` sem receber,
    # de brinde, a receita da empresa.
    permission: str | None = None


ROUTES: list[RouteSpec] = []


def route(method: str, path: str, **opts):
    def deco(fn):
        ROUTES.append(RouteSpec(method=method.upper(), path=path, handler=fn, **opts))
        return fn
    return deco


# ------------------------------------------------------------------------------------------------
# Autenticação
# ------------------------------------------------------------------------------------------------
def cookie_names(secure: bool) -> dict:
    return {"access": "__Host-impacto_at" if secure else "impacto_at",
            "refresh": "__Secure-impacto_rt" if secure else "impacto_rt",
            "csrf": "__Host-impacto_csrf" if secure else "impacto_csrf"}


def _extract_token(request: Request, secure: bool) -> tuple[str | None, str | None]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip() or None, "bearer"
    tok = request.cookies.get(cookie_names(secure)["access"])
    return (tok, "cookie") if tok else (None, None)


def load_principal(ctx: Ctx) -> Principal | None:
    token, via = _extract_token(ctx.request, ctx.settings.cookie_secure)
    if not token or len(token) > 200:
        return None
    with ctx.pool.tx(DbContext(system=True)) as c:
        row = c.one(
            "SELECT s.id::text AS session_id, s.user_id::text AS user_id, s.org_id::text AS org_id, s.mfa_verified,"
            " s.last_seen_at, s.family_started_at, s.family_id::text AS family_id,"
            " u.email::text AS email, u.full_name, u.status, u.is_platform_admin,"
            " u.email_verified_at IS NOT NULL AS email_verified, u.mfa_enabled_at IS NOT NULL AS mfa_enabled,"
            " coalesce((SELECT array_agg(sr.role) FROM staff_roles sr WHERE sr.user_id = u.id), '{}') AS staff_roles,"
            " o.kind AS org_kind, o.legal_name AS org_name, o.status AS org_status, m.role"
            " FROM sessions s JOIN users u ON u.id = s.user_id"
            " LEFT JOIN memberships m ON m.user_id = s.user_id AND m.org_id = s.org_id"
            " LEFT JOIN organizations o ON o.id = s.org_id"
            " WHERE s.access_hash = $1 AND s.revoked_at IS NULL AND s.access_expires_at > now()",
            sha256_hex(token))
        if not row or row["status"] != "active":
            return None
        # IDADE MÁXIMA e INATIVIDADE também no caminho do token de acesso, não só na renovação.
        # Conferir apenas na renovação deixaria uma sessão vencida valendo até 15 minutos a mais —
        # e, pior, uma sessão esquecida continuaria respondendo enquanto alguém a usasse a cada 14
        # minutos. A linha já está carregada, então a conferência não custa consulta nova.
        agora = time.time()
        idade = agora - row["family_started_at"].timestamp()
        inativa = agora - row["last_seen_at"].timestamp()
        motivo = ("session_too_old" if idade > ctx.settings.session_absolute_ttl
                  else "session_idle" if inativa > ctx.settings.session_idle_ttl else None)
        if motivo:
            c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = $2"
                  " WHERE family_id = $1 AND revoked_at IS NULL", row["family_id"], motivo)
            # Deixa trilha também aqui. A revogação acontece UMA vez (depois dela a consulta não
            # encontra mais a sessão), então não há custo recorrente — e uma sessão que morre sem
            # registro é uma pessoa desconectada sem explicação e um incidente sem evidência.
            from .services.audit import record
            record(c, org_id=row["org_id"], actor=row["user_id"], action=f"auth.{motivo}",
                   object_type="session", object_id=row["session_id"],
                   payload={"family_age_seconds": int(idade), "idle_seconds": int(inativa),
                            "detected_on": "access_token"},
                   ip=ctx.ip, request_id=ctx.request_id)
            return None
        if (agora - row["last_seen_at"].timestamp()) > 60:
            c.run("UPDATE sessions SET last_seen_at = now() WHERE id = $1", row["session_id"])
    has_org = row["org_id"] and row["role"] and row["org_status"] == "active"
    return Principal(
        user_id=row["user_id"], email=row["email"], full_name=row["full_name"], session_id=row["session_id"],
        is_platform_admin=row["is_platform_admin"], mfa_enabled=row["mfa_enabled"], mfa_verified=row["mfa_verified"],
        email_verified=row["email_verified"], org_id=row["org_id"] if has_org else None,
        org_kind=row["org_kind"] if has_org else None, org_name=row["org_name"] if has_org else None,
        role=row["role"] if has_org else None, via=via or "bearer", staff_roles=tuple(row["staff_roles"] or ()))


def _check_origin(ctx: Ctx) -> None:
    origin = ctx.request.headers.get("origin")
    if not origin:
        return
    allowed = {ctx.settings.public_base_url.rstrip("/")} | {o.rstrip("/") for o in ctx.settings.cors_origins}
    if origin.rstrip("/") not in allowed:
        raise forbidden("Origem não permitida", "bad_origin")


def _check_csrf(ctx: Ctx) -> None:
    p = ctx.principal
    if not p or p.via != "cookie" or ctx.request.method not in UNSAFE:
        return
    sent = ctx.request.headers.get("x-csrf-token", "")
    expected = csrf_for_session(ctx.settings.secret_key, p.session_id)
    import hmac
    if not sent or not hmac.compare_digest(sent, expected):
        raise forbidden("Token CSRF ausente ou inválido", "csrf")


def authorize(ctx: Ctx, spec: RouteSpec) -> None:
    if spec.auth == "none":
        return
    p = ctx.principal
    if not p:
        raise ApiError(401, "unauthenticated", "Autenticação necessária")
    _check_csrf(ctx)
    if spec.auth == "admin":
        # A PORTA. Três chaves a abrem, e a terceira é a novidade da v0.22.0: ter a PERMISSÃO que a
        # rota exige. Antes, a permissão era conferida depois da porta — e a porta só aceitava
        # `is_platform_admin` ou um papel listado em `staff=`. Resultado: criar o papel `finance`
        # com `finance.read` não dava acesso a nada, porque nenhuma rota lista `finance` em
        # `staff=`. A permissão É a autorização; `staff=` fica como o caminho das rotas que não
        # declaram permissão (as de conteúdo, da v0.12.0).
        from .core import access as ACCESS
        tem_permissao = bool(spec.permission) and ACCESS.of(ctx).has_permission(spec.permission)
        if not (p.is_platform_admin
                or (spec.staff and set(spec.staff) & set(p.staff_roles))
                or tem_permissao):
            # A MENSAGEM muda conforme quem bate na porta, e isso é decisão de segurança:
            #   · quem JÁ é da equipe recebe o nome da permissão que falta — está dentro da casa, e
            #     saber a quem pedir é melhor do que tentar de novo;
            #   · quem NÃO é da equipe recebe apenas "área restrita" — não se confirma a existência
            #     da rota nem o que ela exige a quem não deveria estar ali.
            # A TENTATIVA recusada entra na trilha de acesso privilegiado. Antes, o registro só
            # acontecia DEPOIS de a conferência passar: alguém da equipe sondando cinquenta rotas
            # financeiras e levando 403 em todas não deixava rastro em lugar nenhum — nem aqui,
            # porque não chegava, nem em `audit_events`, que só registra alteração.
            if p.staff_roles or p.is_platform_admin:
                ACCESS.log_privileged(ctx, spec.permission, denied=True)
            if p.staff_roles and spec.permission:
                raise ApiError(403, "permission_denied",
                               "Seu papel na equipe não inclui esta permissão",
                               {"allowed": False, "reason": "permission_denied",
                                "source": "staff_roles",
                                "required_permission": spec.permission})
            raise forbidden("Área restrita à administração da plataforma", "admin_only")
        if ctx.settings.require_mfa_for_admins and not p.mfa_verified:
            raise forbidden("Administração exige MFA ativo e verificado nesta sessão", "mfa_required")
        if not spec.permission and not spec.staff and ctx.request.method in UNSAFE:
            # v0.35.0 (auditoria, AUTH-05): escrita da administração SEM permissão nomeada (só administrador da plataforma)
            # também exige identidade confirmada há menos de 15 minutos — antes, 68 rotas (mudar status de usuário,
            # confirmar recebimento, decidir identidade, medidas de moderação…) passavam só com a sessão.
            # Rotas editoriais da equipe (`staff=`: base de conhecimento, revisão de conteúdo) ficam como antes.
            require_fresh_identity(ctx)
        if spec.permission:
            # Segunda conferência, ANTES de `admin_mode` ser ligado. Não é redundante com a porta:
            # é aqui que entram o papel somente-leitura e a exigência de reautenticação recente.
            # E a ordem importa — `admin_mode` desliga `require_role`, `require_feature` e
            # `check_limit` e liga `app.platform_admin` na RLS; ligá-lo primeiro daria, por um
            # instante, o privilégio a quem a conferência vai recusar.
            ACCESS.of(ctx).can(permission=spec.permission).raise_if_denied()
        ctx.admin_mode = True
        if p.staff_roles or p.is_platform_admin:
            ACCESS.log_privileged(ctx, spec.permission)
        return
    if spec.auth == "org":
        if not p.org_id:
            raise ApiError(409, "no_active_org", "Selecione ou crie uma organização")
        if spec.kinds and p.org_kind not in spec.kinds:
            raise forbidden("Recurso indisponível para este tipo de organização", "wrong_org_kind")
        if spec.min_role and not p.has_role(spec.min_role):
            raise forbidden(f"Requer papel '{spec.min_role}' ou superior", "insufficient_role")
        if (ctx.request.method in UNSAFE and ctx.settings.require_email_verification and not p.email_verified
                and not spec.allow_unverified):
            raise forbidden("Confirme seu e-mail para realizar esta ação", "email_not_verified")
        if spec.feature:
            from .services.entitlements import require_feature
            require_feature(ctx, spec.feature)


# ------------------------------------------------------------------------------------------------
# Construção do endpoint Starlette
# ------------------------------------------------------------------------------------------------
async def _read_json(request: Request, limit: int) -> Any:
    cl = request.headers.get("content-length")
    if cl and int(cl) > limit:
        raise ApiError(413, "payload_too_large", "Corpo da requisição excede o limite")
    ctype = request.headers.get("content-type", "")
    raw = b""
    async for chunk in request.stream():
        raw += chunk
        if len(raw) > limit:
            raise ApiError(413, "payload_too_large", "Corpo da requisição excede o limite")
    if not raw:
        return {}
    if "application/json" not in ctype:
        raise ApiError(415, "unsupported_media_type", "Use Content-Type: application/json")
    try:
        return json.loads(raw)
    except ValueError as exc:
        raise ApiError(400, "invalid_json", "JSON inválido") from exc


def _validation_details(e: ValidationError) -> list[dict]:
    return [{"field": ".".join(str(x) for x in err["loc"]), "message": err["msg"], "type": err["type"]} for err in e.errors()]


def make_endpoint(spec: RouteSpec, app_state):
    async def _endpoint(request: Request) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        if not all(ch.isalnum() or ch in "-_" for ch in rid) or len(rid) > 64:
            rid = uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        spans_var.set([])
        t0 = time.perf_counter()
        ctx = Ctx(request=request, app=app_state, path=dict(request.path_params), request_id=rid)
        status = 500
        form = None
        try:
            if request.method in UNSAFE:
                _check_origin(ctx)
            payload = None
            if spec.multipart:
                cl = request.headers.get("content-length")
                if cl and int(cl) > app_state.settings.max_upload_bytes + 65536:
                    raise ApiError(413, "payload_too_large", "Arquivo excede o limite")
                form = await request.form(max_files=1, max_fields=20, max_part_size=app_state.settings.max_upload_bytes + 1)
                payload = form
            elif spec.raw_body:
                payload = b""
                async for chunk in request.stream():
                    payload += chunk
                    if len(payload) > app_state.settings.max_body_bytes:
                        raise ApiError(413, "payload_too_large", "Corpo da requisição excede o limite")
            elif spec.body is not None:
                payload = await _read_json(request, app_state.settings.max_body_bytes)
            for k, v in ctx.path.items():
                if k.endswith("_id") and not _UUID.match(v):
                    raise ApiError(404, "not_found", "Recurso não encontrado")

            def run():
                if spec.rate:
                    from .services.ratelimit import hit
                    bucket, limit, window = spec.rate
                    hit(ctx, bucket, ctx.ip, limit, window)
                ctx.principal = load_principal(ctx)
                authorize(ctx, spec)   # autoriza ANTES de validar o corpo (não expõe o schema a quem não tem acesso)
                # Interruptor de emergência, DEPOIS de autorizar: quem não tem acesso recebe
                # 401/403 antes de descobrir que a plataforma está parada. Estado de incidente não
                # é informação pública. A auditoria e as rotas do próprio interruptor são isentas —
                # ver `core/killswitch.EXEMPT_PREFIXES`, cada isenção com motivo escrito.
                from .core.killswitch import enforce as _halt_check
                _halt_check(ctx, spec)
                body_obj = payload
                if spec.body is not None:
                    try:
                        body_obj = spec.body.model_validate(payload)
                    except ValidationError as e:
                        raise ApiError(422, "validation_error", "Dados inválidos", _validation_details(e)) from e
                query = None
                if spec.query is not None:
                    try:
                        query = spec.query.model_validate(dict(request.query_params))
                    except ValidationError as e:
                        raise ApiError(422, "validation_error", "Parâmetros inválidos", _validation_details(e)) from e
                args = [ctx]
                if spec.body is not None or spec.multipart or spec.raw_body:
                    args.append(body_obj)
                if spec.query is not None:
                    args.append(query)
                return spec.handler(*args)

            result = await run_in_threadpool(run)
            if spec.raw:
                resp = result
            else:
                resp = json_response(result, status=spec.status if result is not None else 204)
            status = resp.status_code
            return resp
        except ApiError as e:
            status = e.status
            return problem(e.status, e.code, e.message, e.details)
        except pq.UniqueViolation as e:
            status = 409
            return problem(409, "conflict", "Registro duplicado", {"constraint": e.constraint})
        except (pq.CheckViolation, pq.ForeignKeyViolation, pq.NotNullViolation, pq.RaiseException) as e:
            status = 422
            msg = str(e).split("\n")[0][:300]
            if _PG_INTERNAL.search(msg):     # nome de tabela/coluna/constraint não sai na resposta: fica no log com error_id
                eid = uuid.uuid4().hex[:12]
                log(logger, logging.WARNING, "integrity_error", error_id=eid, route=spec.path, constraint=getattr(e, "constraint", None),
                    error=msg, user_id=ctx.principal.user_id if ctx.principal else None)
                return problem(422, "integrity_error", "Dados inválidos para esta operação", None, error_id=eid)
            return problem(422, "integrity_error", msg)
        except pq.InsufficientPrivilege as e:
            status = 403
            log(logger, logging.WARNING, "rls_denied", route=spec.path, error=str(e)[:300],
                user_id=ctx.principal.user_id if ctx.principal else None)
            return problem(403, "forbidden", "Operação não permitida para esta organização")
        except pq.SerializationFailure:
            status = 409
            return problem(409, "concurrent_update", "Operação concorrente detectada; tente novamente")
        except pq.QueryCanceled:
            status = 503
            return problem(503, "timeout", "Operação excedeu o tempo limite; tente novamente")
        except pq.OperationalError as e:
            status = 503
            log(logger, logging.ERROR, "db_unavailable", error=str(e)[:300])
            return problem(503, "service_unavailable", "Serviço temporariamente indisponível")
        except Exception as e:  # noqa: BLE001
            status = 500
            eid = uuid.uuid4().hex[:12]
            log(logger, logging.ERROR, "unhandled_error", error_id=eid, error_type=type(e).__name__, route=spec.path,
                user_id=ctx.principal.user_id if ctx.principal else None, trace=traceback.format_exc()[-4000:])
            await run_in_threadpool(_record_error, app_state, spec, rid, e)
            return problem(500, "internal_error", "Erro interno. Informe o código ao suporte.", error_id=eid)
        finally:
            if form is not None:
                await form.close()
            dt = time.perf_counter() - t0
            METRICS.inc("impacto_http_requests_total", method=request.method, route=spec.path, status=status)
            METRICS.observe("impacto_http_request_duration_seconds", dt, route=spec.path)
            log(logger, logging.INFO if status < 500 else logging.ERROR, "request", method=request.method, route=spec.path,
                status=status, ms=round(dt * 1000, 1), spans=summarize_spans(spans_var.get()),
                user_id=ctx.principal.user_id if ctx.principal else None,
                org_id=ctx.principal.org_id if ctx.principal else None)
            request_id_var.reset(token)

    async def endpoint(request: Request) -> Response:
        trace, span = new_trace(request.headers.get("traceparent"))
        tok = trace_id_var.set(trace)
        try:
            resp = await _endpoint(request)
            resp.headers["traceparent"] = f"00-{trace}-{span}-01"
            return resp
        finally:
            trace_id_var.reset(tok)
    endpoint.__name__ = spec.handler.__name__
    return endpoint


def _record_error(app_state, spec: RouteSpec, rid: str, exc: BaseException) -> None:
    """Agrega o erro por impressão digital (sem PII). Falha aqui nunca derruba a resposta."""
    try:
        fp, msg = error_fingerprint(spec.path, exc)
        with app_state.pool.tx(DbContext(system=True)) as c:
            c.run("INSERT INTO error_events(fingerprint, route, status, exception_type, message, last_request_id, last_trace_id)"
                  " VALUES ($1,$2,500,$3,$4,$5,$6) ON CONFLICT (fingerprint) DO UPDATE SET occurrences = error_events.occurrences + 1,"
                  " last_seen = now(), last_request_id = EXCLUDED.last_request_id, last_trace_id = EXCLUDED.last_trace_id, resolved = false",
                  fp, spec.path, type(exc).__name__, msg, rid, trace_id_var.get() or None)
    except Exception:  # noqa: BLE001, S110 - registrar erro nunca pode causar novo erro
        pass


# ------------------------------------------------------------------------------------------------
# Paginação
# ------------------------------------------------------------------------------------------------
def page(rows: list[dict], limit: int, offset: int) -> dict:
    has_more = len(rows) > limit
    return {"items": rows[:limit], "limit": limit, "offset": offset, "has_more": has_more,
            "next_offset": offset + limit if has_more else None}
