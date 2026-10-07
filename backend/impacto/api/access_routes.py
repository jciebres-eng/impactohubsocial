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
        # O MENU também. Até a v0.21.0 a barra lateral da administração era uma lista fixa no
        # frontend, igual para toda a equipe: quem atendia chamado via "Cobrança por organização"
        # e "Auditoria" no menu e levava 403 ao clicar. Menu que oferece o que a porta recusa é
        # pior do que menu incompleto — ensina a pessoa a desconfiar da tela.
        "menu": menu_for(ac),
        "step_up_window_seconds": 900,
    }


# [caminho, rótulo, grupo, permissão exigida]. A permissão é a MESMA que a rota exige: é isso que
# faz o menu não poder discordar da porta (conferido em test_v0220_internal_ui.py).
STAFF_MENU: tuple[tuple[str, str, str, str | None], ...] = (
    ("/controladoria", "Painel executivo", "Controladoria", "metrics.read"),
    ("/controladoria/conciliacao", "Conciliação", "Controladoria", "finance.read"),
    ("/aprovacoes", "Aprovações", "Controladoria", "finance.read"),
    ("/financeiro", "Recebíveis e pagáveis", "Financeiro", "finance.read"),
    ("/financeiro/despesas", "Despesas da plataforma", "Financeiro", "finance.read"),
    ("/financeiro/instrucoes", "Instruções de pagamento", "Financeiro", "instruction.read"),
    ("/admin/cobranca", "Cobrança por organização", "Financeiro", "billing.read"),
    # FULL FREE 2026 existia desde a v0.21.0 com rota, serviço, banco e teste — e nenhuma tela.
    # Quem concedia cortesia fazia por chamada de API; quem auditava não tinha onde olhar.
    ("/financeiro/periodos-gratuitos", "Períodos gratuitos", "Financeiro", "free_period.write"),
    ("/contabilidade", "Balancete e competência", "Contabilidade", "accounting.read"),
    ("/contabilidade/plano-de-contas", "Plano de contas", "Contabilidade", "accounting.read"),
    ("/tesouraria", "Caixa e patrimônio", "Tesouraria", "treasury.read"),
    ("/administrativo/orcamento", "Orçamento", "Administrativo", "budget.read"),
    ("/admin/fiscal", "Regras fiscais", "Fiscal", "fiscal.read"),
    ("/operacoes", "Saúde do sistema", "Operações", "health.read"),
    ("/operacoes/alertas", "Central de alertas", "Operações", "health.read"),
    ("/admin/erros", "Erros", "Operações", "maintenance.read"),
    ("/admin/risco", "Sinais de risco", "Operações", "maintenance.read"),
    ("/admin/compliance", "Fila de compliance", "Compliance", "compliance.read"),
    ("/admin/organizacoes", "Organizações", "Compliance", "admin.organizations.read"),
    ("/auditoria", "Acesso privilegiado", "Auditoria", "security.audit.read"),
    ("/admin/auditoria", "Trilha de auditoria", "Auditoria", "security.audit.read"),
    ("/admin/chaves", "Chaves de cifragem", "Segurança", "security.keys.read"),
    ("/admin/usuarios", "Usuários e papéis", "Segurança", "admin.users.read"),
    ("/admin/permissoes", "Matriz de permissões", "Segurança", "admin.users.read"),
    ("/admin/central/suporte", "Fila de suporte", "Suporte", "support.read"),
    ("/admin/central", "Central de Conhecimento", "Conteúdo", "content.read"),
    ("/admin/integracoes", "Integrações", "Operações", "integration.read"),
)


def menu_for(ac: ACCESS.AccessContext) -> list[dict]:
    """O menu INTERNO que esta pessoa pode receber, agrupado, na ordem declarada.

    Devolve vazio para quem não é da equipe: a ausência de menu interno é a resposta correta, e não
    um menu vazio com títulos de grupo.
    """
    if not (ac.is_staff or ac.is_platform_admin):
        return []
    grupos: list[dict] = []
    por_nome: dict[str, dict] = {}
    for caminho, rotulo, grupo, permissao in STAFF_MENU:
        if permissao and not ac.has_permission(permissao):
            continue
        g = por_nome.get(grupo)
        if g is None:
            g = {"group": grupo, "items": []}
            por_nome[grupo] = g
            grupos.append(g)
        g["items"].append({"to": caminho, "label": rotulo, "permission": permissao})
    return grupos


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
