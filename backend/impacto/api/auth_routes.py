"""Rotas de autenticação, conta, sessões e equipe."""
from __future__ import annotations

from ..http import ApiError, Ctx, route
from ..network import notify as NT
from ..services import auth
from . import schemas as S

T = ("auth",)


@route("POST", "/v1/auth/register", auth="none", body=S.RegisterIn, status=202, rate=("register", 10, 3600), tags=T,
       summary="Cadastra usuário (e organização opcional). Resposta não revela se o e-mail já existe.")
def register(ctx: Ctx, body: S.RegisterIn):
    return auth.register(ctx, body)


@route("POST", "/v1/auth/login", auth="none", body=S.LoginIn, raw=True, rate=("login_ip", 30, 900), tags=T,
       summary="Login por e-mail/senha. Web recebe cookies httpOnly; mobile envia X-Auth-Mode: token.")
def login(ctx: Ctx, body: S.LoginIn):
    return auth.login(ctx, body)


@route("POST", "/v1/auth/mfa/verify", auth="none", body=S.MfaLoginIn, raw=True, rate=("mfa_ip", 30, 900), tags=T,
       summary="Conclui login com TOTP ou código de recuperação")
def mfa_verify(ctx: Ctx, body: S.MfaLoginIn):
    if not body.code and not body.recovery_code:
        raise ApiError(422, "validation_error", "Informe o código do autenticador ou um código de recuperação")
    return auth.mfa_login(ctx, body)


@route("POST", "/v1/auth/refresh", auth="none", body=S.RefreshIn, raw=True, rate=("refresh_ip", 120, 900), tags=T,
       summary="Rotaciona o refresh token (reuso revoga toda a família de sessões)")
def refresh(ctx: Ctx, body: S.RefreshIn):
    return auth.refresh(ctx, body)


@route("POST", "/v1/auth/logout", auth="user", raw=True, tags=T, summary="Encerra a sessão atual")
def logout(ctx: Ctx):
    return auth.logout(ctx)


@route("POST", "/v1/auth/logout-all", auth="user", raw=True, tags=T, summary="Encerra todas as sessões do usuário")
def logout_all(ctx: Ctx):
    return auth.logout(ctx, everywhere=True)


@route("POST", "/v1/auth/verify-email", auth="none", body=S.TokenIn, rate=("verify_ip", 30, 900), tags=T)
def verify_email(ctx: Ctx, body: S.TokenIn):
    return auth.verify_email(ctx, body.token)


@route("POST", "/v1/auth/resend-verification", auth="user", rate=("resend_ip", 5, 3600), tags=T)
def resend(ctx: Ctx):
    return auth.resend_verification(ctx)


@route("POST", "/v1/auth/forgot-password", auth="none", body=S.EmailIn, status=202, rate=("forgot_ip", 5, 3600), tags=T)
def forgot(ctx: Ctx, body: S.EmailIn):
    return auth.forgot_password(ctx, body.email)


@route("POST", "/v1/auth/reset-password", auth="none", body=S.ResetIn, rate=("reset_ip", 10, 3600), tags=T)
def reset(ctx: Ctx, body: S.ResetIn):
    return auth.reset_password(ctx, body.token, body.password)


@route("POST", "/v1/auth/change-password", auth="user", body=S.ChangePasswordIn, rate=("changepw_ip", 10, 3600), tags=T)
def change_password(ctx: Ctx, body: S.ChangePasswordIn):
    return auth.change_password(ctx, body.current_password, body.new_password)


@route("POST", "/v1/auth/mfa/setup", auth="user", tags=T, summary="Gera segredo TOTP (pendente até confirmar)")
def mfa_setup(ctx: Ctx):
    return auth.mfa_setup(ctx)


@route("POST", "/v1/auth/mfa/enable", auth="user", body=S.CodeIn, tags=T, summary="Confirma TOTP e devolve códigos de recuperação")
def mfa_enable(ctx: Ctx, body: S.CodeIn):
    return auth.mfa_enable(ctx, body.code)


@route("POST", "/v1/auth/mfa/disable", auth="user", body=S.MfaDisableIn, tags=T)
def mfa_disable(ctx: Ctx, body: S.MfaDisableIn):
    return auth.mfa_disable(ctx, body.password, body.code)


@route("GET", "/v1/auth/sessions", auth="user", tags=T, summary="Sessões ativas do usuário")
def sessions(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, ip, user_agent, created_at, last_seen_at, mfa_verified FROM sessions"
                       " WHERE user_id = $1 AND revoked_at IS NULL AND refresh_expires_at > now() ORDER BY last_seen_at DESC",
                       ctx.user_id)
    for r in rows:
        r["current"] = r["id"] == ctx.principal.session_id
    return {"items": rows}


@route("DELETE", "/v1/auth/sessions/{session_id}", auth="user", tags=T, summary="Revoga uma sessão")
def revoke_session(ctx: Ctx):
    with ctx.tx() as c:
        n = c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'user_revoked' WHERE id = $1 AND user_id = $2"
                  " AND revoked_at IS NULL", ctx.path["session_id"], ctx.user_id)
        if not n:
            raise ApiError(404, "not_found", "Sessão não encontrada")
        ctx.audit(c, "auth.session_revoked", "session", ctx.path["session_id"])
    return None


@route("GET", "/v1/me", auth="user", tags=T, summary="Usuário, organizações, direitos do plano e token CSRF")
def me(ctx: Ctx):
    return auth.me(ctx)


@route("POST", "/v1/me/switch-org", auth="user", body=S.SwitchOrgIn, tags=T)
def switch_org(ctx: Ctx, body: S.SwitchOrgIn):
    return auth.switch_org(ctx, body.org_id)


@route("POST", "/v1/orgs", auth="user", body=S.OrgIn, status=201, tags=("organizations",), summary="Cria organização adicional")
def create_org(ctx: Ctx, body: S.OrgIn):
    return auth.create_org(ctx, body)


@route("POST", "/v1/org/invitations", body=S.InviteIn, status=201, min_role="admin", tags=("team",))
def invite(ctx: Ctx, body: S.InviteIn):
    return auth.invite(ctx, body.email, body.role)


@route("GET", "/v1/org/invitations", min_role="admin", tags=("team",))
def list_invites(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, email::text AS email, role, expires_at, accepted_at, revoked_at, created_at"
                                 " FROM invitations WHERE org_id = $1 ORDER BY created_at DESC LIMIT 200", ctx.org_id)}


@route("DELETE", "/v1/org/invitations/{invitation_id}", min_role="admin", tags=("team",))
def revoke_invite(ctx: Ctx):
    with ctx.tx() as c:
        n = c.run("UPDATE invitations SET revoked_at = now() WHERE id = $1 AND org_id = $2 AND accepted_at IS NULL",
                  ctx.path["invitation_id"], ctx.org_id)
        if not n:
            raise ApiError(404, "not_found", "Convite não encontrado")
        ctx.audit(c, "member.invite_revoked", "invitation", ctx.path["invitation_id"])
    return None


@route("POST", "/v1/auth/accept-invite", auth="user", body=S.TokenIn, tags=("team",))
def accept_invite(ctx: Ctx, body: S.TokenIn):
    return auth.accept_invite(ctx, body.token)


@route("GET", "/v1/org/members", min_role="viewer", tags=("team",))
def members(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT u.id::text AS user_id, u.full_name, u.email::text AS email, m.role, m.created_at,"
                                 " u.mfa_enabled_at IS NOT NULL AS mfa_enabled FROM memberships m JOIN users u ON u.id = m.user_id"
                                 " WHERE m.org_id = $1 ORDER BY m.created_at", ctx.org_id)}


@route("PATCH", "/v1/org/members/{user_id}", body=S.RoleIn, min_role="admin", tags=("team",))
def change_role(ctx: Ctx, body: S.RoleIn):
    target = ctx.path["user_id"]
    with ctx.tx() as c:
        cur = c.one("SELECT role FROM memberships WHERE org_id = $1 AND user_id = $2", ctx.org_id, target)
        if not cur:
            raise ApiError(404, "not_found", "Membro não encontrado")
        if cur["role"] == "owner" or (body.role == "admin" and ctx.principal.role != "owner"):
            raise ApiError(403, "forbidden", "Somente o proprietário altera administradores; o papel de proprietário não pode ser alterado aqui")
        c.run("UPDATE memberships SET role = $3 WHERE org_id = $1 AND user_id = $2", ctx.org_id, target, body.role)
        ctx.audit(c, "member.role_changed", "user", target, {"from": cur["role"], "to": body.role})
    return {"user_id": target, "role": body.role}


@route("DELETE", "/v1/org/members/{user_id}", min_role="admin", tags=("team",))
def remove_member(ctx: Ctx):
    target = ctx.path["user_id"]
    with ctx.tx() as c:
        cur = c.one("SELECT role FROM memberships WHERE org_id = $1 AND user_id = $2", ctx.org_id, target)
        if not cur:
            raise ApiError(404, "not_found", "Membro não encontrado")
        if cur["role"] == "owner":
            raise ApiError(409, "last_owner", "Não é possível remover o proprietário")
        c.run("DELETE FROM memberships WHERE org_id = $1 AND user_id = $2", ctx.org_id, target)
        ctx.audit(c, "member.removed", "user", target, {"role": cur["role"]})
        # v0.20.0 — `Team.member_added` e `Team.member_removed` estavam declarados e nunca eram
        # gravados. A ironia é precisa: a equipe é derivada de `memberships`, e o módulo de
        # notificação existe para avisar a equipe — mas entrar e sair dela não era um fato.
        NT.org_event(
            c, event="Team.member_removed", org_id=ctx.org_id,
            title="Pessoa retirada da organização",
            body=f"Perfil anterior: {cur['role']}.", link="/organizacao/equipe",
            actor_user_id=ctx.user_id, priority="high", min_role="admin",
            ref_type="user", ref_id=target, action_label="Ver equipe",
            payload={"role": cur["role"]})
    with ctx.system_tx() as c:
        c.run("UPDATE sessions SET org_id = NULL WHERE user_id = $1 AND org_id = $2", target, ctx.org_id)
    return None


# ------------------------------------------------------------------------------------------------ SSO OIDC
class OidcStartQ(S.In):
    redirect: str = "/"


@route("GET", "/v1/auth/oidc/start", auth="none", query=OidcStartQ, raw=True, rate=("oidc_ip", 60, 900), tags=T,
       summary="Inicia login corporativo (OIDC Authorization Code + PKCE)")
def oidc_start(ctx: Ctx, q: OidcStartQ):
    from starlette.responses import RedirectResponse
    from ..services import oidc
    return RedirectResponse(oidc.start(ctx, q.redirect), status_code=302)


class OidcCallbackQ(S.In):
    code: str
    state: str
    session_state: str | None = None
    iss: str | None = None


@route("GET", "/v1/auth/oidc/callback", auth="none", query=OidcCallbackQ, raw=True, rate=("oidc_ip", 60, 900), tags=T,
       summary="Retorno do provedor de identidade: valida id_token (JWKS, iss, aud, nonce) e cria a sessão")
def oidc_callback(ctx: Ctx, q: OidcCallbackQ):
    from starlette.responses import RedirectResponse
    from ..services import oidc
    ident, redirect_to = oidc.callback(ctx, q.code, q.state)
    tokens = oidc.login_or_provision(ctx, ident)
    resp = RedirectResponse(redirect_to, status_code=302)
    auth.set_session_cookies(ctx, resp, tokens)
    return resp
