"""Contexto de acesso, consulta de permissão e reautenticação.

O frontend não é a autoridade. Estas rotas existem para que ele possa PERGUNTAR à autoridade, em
vez de reimplementar a regra — que é como as duas camadas passam a discordar.
"""
from __future__ import annotations

from ..core import access as ACCESS
from ..db.pool import DbContext
from ..http import ApiError, Ctx, route
from . import schemas as S

T = ("acesso",)


@route("GET", "/v1/me/context", auth="user", tags=T,
       summary="AccessContext: identidade, organização, papéis, plano, período gratuito, permissões")
def me_context(ctx: Ctx):
    """Tudo que decide um acesso, numa resposta só.

    Uma chamada, e não sete: a tela precisa de todo este conjunto para montar menu, painel e
    estados, e sete requisições no primeiro carregamento é o que faz um painel parecer lento.
    """
    ac = ACCESS.of(ctx)
    return {
        "user": {"id": ac.user_id, "email": ac.email,
                 "mfa_enabled": ac.mfa_enabled, "mfa_verified": ac.mfa_verified,
                 "email_verified": ac.email_verified},
        "staff": {"is_platform_admin": ac.is_platform_admin,
                  "roles": list(ac.staff_roles),
                  "permissions": sorted(ac.permissions),
                  "read_only": ac.is_read_only_staff},
        "organization": ({"id": ac.org_id, "kind": ac.org_kind, "name": ac.org_name,
                          "role": ac.role} if ac.org_id else None),
        "commercial": {"plans": list(ac.plans), "subscription_status": ac.subscription_status,
                       "state": ac.commercial_state, "free_period_end": ac.free_period_end,
                       "charge_authorized": ac.charge_authorized},
        "entitlements": {"features": sorted(ac.features), "limits": ac.limits},
        # O painel que a pessoa deve receber é decidido AQUI, no servidor. Deixar o frontend
        # escolher faria a decisão existir em dois lugares, e um deles ficaria para trás.
        "dashboard": dashboard_for(ac),
        "step_up_window_seconds": 900,
    }


def dashboard_for(ac: ACCESS.AccessContext) -> str:
    """Qual painel esta pessoa deve receber ao entrar.

    A ordem é deliberada: papel INTERNO vence tipo de organização. Quem é da controladoria e
    também tem uma organização cliente entra na controladoria — porque é o que essa pessoa está
    fazendo quando entra pelo trabalho.
    """
    perms = ac.permissions
    # Ordem por ESPECIFICIDADE, da mais restrita para a mais ampla. A primeira versão disto usava
    # `"finance.read" in perms and "accounting.read" in perms` para identificar a controladoria, e
    # mandava a contabilidade para lá — porque contabilidade tem as duas leituras. O que distingue
    # a controladoria não é ler mais coisas: é APROVAR.
    # Auditoria vem ANTES do financeiro, embora leia o financeiro. O que define a auditoria não é
    # o que ela lê — ela lê quase tudo — é que ela não altera nada. Mandá-la para o painel
    # financeiro ofereceria botões que a própria permissão dela recusa.
    if ac.is_read_only_staff and "security.audit.read" in perms:
        return "/auditoria"
    if "finance.approve" in perms:
        return "/controladoria"
    if "accounting.close" in perms or "accounting.write" in perms:
        return "/contabilidade"
    if "treasury.write" in perms:
        return "/tesouraria"
    if "finance.read" in perms or "billing.read" in perms:
        return "/financeiro"
    if "maintenance.read" in perms or "health.read" in perms:
        return "/operacoes"
    if "security.audit.read" in perms:
        return "/auditoria"
    if ac.is_platform_admin or ac.staff_roles:
        return "/admin"
    if not ac.org_id:
        return "/organizacao/nova"
    return "/area"


@route("POST", "/v1/access/check", auth="user", body=S.AccessCheckIn, tags=T,
       summary="Posso executar esta ação? Devolve decisão com motivo, nunca só um booleano")
def check(ctx: Ctx, body: S.AccessCheckIn):
    if not (body.permission or body.feature or body.min_role):
        raise ApiError(422, "nothing_to_check",
                       "Informe ao menos uma permissão, recurso ou papel mínimo.")
    ac = ACCESS.of(ctx)
    return ac.can(permission=body.permission, feature=body.feature,
                  min_role=body.min_role).as_dict()


@route("POST", "/v1/auth/reauth", auth="user", body=S.ReauthIn, rate=("reauth", 20, 900), tags=T,
       summary="Confirma a identidade para operações sensíveis (vale por 15 minutos)")
def reauth(ctx: Ctx, body: S.ReauthIn):
    """Carimba a sessão. Substitui as três cópias manuais de verificação de senha.

    Com MFA ativo, o código é obrigatório: aceitar só a senha de quem tem segundo fator seria
    oferecer o fator mais fraco justamente na operação mais perigosa.
    """
    ACCESS.verify_identity(ctx, password=body.password, mfa_code=body.mfa_code)
    with ctx.pool.tx(DbContext(system=True)) as c:
        ctx.audit(c, "auth.reauth", "session", ctx.principal.session_id,
                  {"mfa_used": bool(ctx.principal.mfa_enabled)})
    # O contexto em cache ficou velho: a próxima pergunta precisa ver o carimbo novo.
    ctx._access = None
    return {"confirmed": True, "valid_for_seconds": 900}


@route("GET", "/v1/admin/privileged-access", auth="admin", permission="security.audit.read",
       tags=T, summary="Quem entrou com papel interno, quando, em qual rota e com qual permissão")
def privileged_access(ctx: Ctx):
    """A trilha que responde "quem olhou", e não só "quem mudou"."""
    with ctx.pool.tx(DbContext(system=True), readonly=True) as c:
        itens = [dict(r) for r in c.query(
            "SELECT p.id, p.at, p.roles_used, p.permission, p.method, p.path, p.request_id,"
            " u.email FROM privileged_access_log p LEFT JOIN users u ON u.id = p.user_id"
            " ORDER BY p.id DESC LIMIT 200")]
        resumo = [dict(r) for r in c.query(
            "SELECT permission, count(*) AS acessos, count(DISTINCT user_id) AS pessoas"
            " FROM privileged_access_log WHERE at > now() - interval '30 days'"
            "   AND permission IS NOT NULL GROUP BY permission ORDER BY acessos DESC")]
    return {"items": itens, "last_30_days": resumo}


@route("GET", "/v1/admin/permissions", auth="admin", permission="admin.users.read", tags=T,
       summary="Matriz papel → permissão, como está no banco")
def permission_matrix(ctx: Ctx):
    with ctx.pool.tx(DbContext(system=True), readonly=True) as c:
        linhas = [dict(r) for r in c.query(
            "SELECT role, permission, note FROM staff_permissions ORDER BY role, permission")]
        pessoas = [dict(r) for r in c.query(
            "SELECT u.email, array_agg(r.role ORDER BY r.role) AS roles FROM staff_roles r"
            " JOIN users u ON u.id = r.user_id GROUP BY u.email ORDER BY u.email")]
    matriz: dict[str, list] = {}
    for linha in linhas:
        matriz.setdefault(linha["role"], []).append(
            {"permission": linha["permission"], "note": linha["note"]})
    return {"matrix": matriz, "staff": pessoas,
            "super_admin_note": "super_admin implica todas as permissões e não aparece na matriz: "
                                "uma lista explícita esqueceria a permissão criada no mês seguinte.",
            "declared_on_routes": sorted({r.permission for r in _routes_with_permission()})}


def _routes_with_permission():
    from ..http import ROUTES
    return [r for r in ROUTES if r.permission]
