"""Autenticação: cadastro, login, MFA (TOTP + códigos de recuperação), sessões com refresh rotativo e detecção de
reuso, verificação de e-mail, recuperação de senha, convites e troca de organização ativa.

Todas as operações anteriores à identificação do usuário rodam em ``system_tx`` (contexto de sistema auditável).
Respostas não revelam se um e-mail existe (anti-enumeração).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, UTC

from ..db.pq import Connection
from ..http import ApiError, Ctx, cookie_names, json_response, unprocessable
from ..observability import log
from ..security import passwords, totp
from ..security.tokens import csrf_for_session, new_token, sha256_hex
from .validators import cnpj_valid, only_digits

logger = logging.getLogger("impacto.auth")
LOCK_AFTER = 8
LOCK_MINUTES = 15


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------------------------------------
# Sessões
# ------------------------------------------------------------------------------------------------
def issue_session(c: Connection, ctx: Ctx, user_id: str, org_id: str | None, mfa_verified: bool,
                  family_id: str | None = None) -> dict:
    s = ctx.settings
    access, refresh = new_token(), new_token(48)
    sid = str(uuid.uuid4())
    c.run("INSERT INTO sessions(id, user_id, org_id, family_id, access_hash, access_expires_at, refresh_hash, refresh_expires_at,"
          " mfa_verified, ip, user_agent) VALUES ($1,$2,$3,$4,$5, now() + make_interval(secs => $6), $7,"
          " now() + make_interval(secs => $8), $9, $10, $11)",
          sid, user_id, org_id, family_id or str(uuid.uuid4()), sha256_hex(access), s.access_token_ttl,
          sha256_hex(refresh), s.refresh_token_ttl, mfa_verified, ctx.ip, ctx.user_agent)
    return {"session_id": sid, "access_token": access, "refresh_token": refresh, "expires_in": s.access_token_ttl,
            "csrf_token": csrf_for_session(s.secret_key, sid)}


def session_response(ctx: Ctx, tokens: dict, extra: dict | None = None, status: int = 200):
    """Web: cookies httpOnly + token CSRF. Mobile/API (header X-Auth-Mode: token): tokens no corpo."""
    mode = ctx.request.headers.get("x-auth-mode", "cookie").lower()
    body = {"expires_in": tokens["expires_in"], "csrf_token": tokens["csrf_token"], **(extra or {})}
    if mode == "token":
        body.update({"access_token": tokens["access_token"], "refresh_token": tokens["refresh_token"], "token_type": "Bearer"})
        return json_response(body, status)
    resp = json_response(body, status)
    set_session_cookies(ctx, resp, tokens)
    return resp


def set_session_cookies(ctx: Ctx, resp, tokens: dict) -> None:
    s = ctx.settings
    names = cookie_names(s.cookie_secure)
    resp.set_cookie(names["access"], tokens["access_token"], max_age=s.access_token_ttl, path="/", secure=s.cookie_secure,
                    httponly=True, samesite="lax")
    resp.set_cookie(names["refresh"], tokens["refresh_token"], max_age=s.refresh_token_ttl, path="/v1/auth",
                    secure=s.cookie_secure, httponly=True, samesite="strict")
    resp.set_cookie(names["csrf"], tokens["csrf_token"], max_age=s.refresh_token_ttl, path="/", secure=s.cookie_secure,
                    httponly=False, samesite="lax")


def clear_session_cookies(ctx: Ctx, resp) -> None:
    names = cookie_names(ctx.settings.cookie_secure)
    resp.delete_cookie(names["access"], path="/", secure=ctx.settings.cookie_secure, httponly=True, samesite="lax")
    resp.delete_cookie(names["refresh"], path="/v1/auth", secure=ctx.settings.cookie_secure, httponly=True, samesite="strict")
    resp.delete_cookie(names["csrf"], path="/", secure=ctx.settings.cookie_secure, samesite="lax")


def default_org(c: Connection, user_id: str, preferred: str | None = None) -> str | None:
    if preferred:
        r = c.one("SELECT m.org_id::text AS id FROM memberships m JOIN organizations o ON o.id = m.org_id"
                  " WHERE m.user_id = $1 AND m.org_id = $2 AND o.status = 'active'", user_id, preferred)
        if r:
            return r["id"]
    r = c.one("SELECT m.org_id::text AS id FROM memberships m JOIN organizations o ON o.id = m.org_id"
              " WHERE m.user_id = $1 AND o.status = 'active' ORDER BY m.created_at LIMIT 1", user_id)
    return r["id"] if r else None


# ------------------------------------------------------------------------------------------------
# Tokens de uso único (verificação de e-mail, reset de senha, desafio MFA)
# ------------------------------------------------------------------------------------------------
def create_auth_token(c: Connection, user_id: str, purpose: str, ttl_minutes: int) -> str:
    tok = new_token()
    c.run("UPDATE auth_tokens SET used_at = now() WHERE user_id = $1 AND purpose = $2 AND used_at IS NULL", user_id, purpose)
    c.run("INSERT INTO auth_tokens(user_id, purpose, token_hash, expires_at) VALUES ($1,$2,$3, now() + make_interval(mins => $4))",
          user_id, purpose, sha256_hex(tok), ttl_minutes)
    return tok


def consume_auth_token(c: Connection, token: str, purpose: str, *, max_attempts: int = 1) -> dict | None:
    row = c.one("SELECT id, user_id::text AS user_id, attempts FROM auth_tokens WHERE token_hash = $1 AND purpose = $2"
                " AND used_at IS NULL AND expires_at > now() FOR UPDATE", sha256_hex(token or ""), purpose)
    if not row:
        return None
    if max_attempts == 1:
        c.run("UPDATE auth_tokens SET used_at = now() WHERE id = $1", row["id"])
    return row


# ------------------------------------------------------------------------------------------------
# Casos de uso
# ------------------------------------------------------------------------------------------------
def register(ctx: Ctx, body) -> dict:
    email = body.email.lower()
    problems = passwords.password_problems(body.password, email)
    if problems:
        raise unprocessable("Senha fraca", [{"field": "password", "message": p} for p in problems])
    if not body.accept_terms:
        raise unprocessable("É necessário aceitar os Termos de Uso e a Política de Privacidade")
    # PORTÃO JURÍDICO. Documento que exige aceite e não foi aprovado não pode ser aceito: o gatilho do
    # banco recusa o registro, e seguir mesmo assim significaria coletar concordância com um texto que
    # ninguém revisou, sem deixar prova. Em desenvolvimento e teste o cadastro continua, porque a
    # plataforma precisa ser desenvolvível antes de o jurídico existir — e a resposta DIZ que seguiu
    # assim, em vez de fingir que houve aceite.
    from . import legal as LEGAL
    with ctx.system_tx() as c_legal:
        pendentes = LEGAL.blockers(c_legal)
    if pendentes and ctx.settings.is_hardened:
        raise ApiError(503, "legal_documents_not_published",
                       "O cadastro está suspenso até que os documentos legais sejam aprovados por "
                       "revisão jurídica. Nenhum aceite pode ser coletado sobre minuta.",
                       {"documents": [d["doc_key"] for d in pendentes]})
    org = body.organization
    cnpj = only_digits(org.cnpj) if org and org.cnpj else None
    nature_code = getattr(org, "legal_nature_code", None) if org else None
    if org:
        no_cnpj_ok = False
        if nature_code:
            # Natureza do catálogo governado: coletivos/iniciativas em estruturação podem se cadastrar sem CNPJ (nunca recebem o estado "regular").
            with ctx.system_tx() as c0:
                item = c0.one("SELECT attributes FROM inst_catalog_items WHERE catalog = 'legal_nature' AND code = $1 AND status = 'published'", nature_code)
            if not item:
                raise unprocessable("Natureza jurídica fora do catálogo", [{"field": "organization.legal_nature_code", "message": "código desconhecido"}])
            attrs = item["attributes"] or {}
            if org.kind not in attrs.get("allowed_kinds", []):
                raise unprocessable("Natureza jurídica incompatível com o tipo de organização", [{"field": "organization.legal_nature_code", "message": "não se aplica a este tipo"}])
            no_cnpj_ok = attrs.get("requires_cnpj", True) is False
        if org.kind in ("osc", "company", "government") and not cnpj and not no_cnpj_ok:
            raise unprocessable("CNPJ é obrigatório para este tipo de organização", [{"field": "organization.cnpj", "message": "obrigatório"}])
        if cnpj and not cnpj_valid(cnpj):
            raise unprocessable("CNPJ inválido", [{"field": "organization.cnpj", "message": "dígitos verificadores inválidos"}])
    pw_hash = passwords.hash_password(body.password)
    with ctx.system_tx() as c:
        existing = c.one("SELECT id::text AS id, email_verified_at FROM users WHERE email = $1", email)
        if existing:
            # Anti-enumeração: mesma resposta; avisamos o titular por e-mail.
            log(logger, logging.INFO, "register_existing_email")
            mail = ("Alguém tentou criar uma conta com este e-mail na Plataforma Impacto. Se foi você, use 'Esqueci minha senha'."
                    " Se não foi, ignore esta mensagem.")
            _send_after(ctx, email, "Tentativa de cadastro com seu e-mail", mail)
            return {"status": "pending_verification", "message": "Se os dados forem válidos, enviaremos um e-mail de confirmação."}
        if cnpj and c.one("SELECT 1 FROM organizations WHERE cnpj = $1", cnpj):
            raise ApiError(409, "cnpj_in_use", "Já existe organização com este CNPJ. Peça um convite ao responsável.")
        uid = c.scalar("INSERT INTO users(email, full_name, password_hash) VALUES ($1,$2,$3) RETURNING id::text",
                       email, body.full_name, pw_hash)
        for kind, ver in (("terms", ctx.settings.terms_version), ("privacy", ctx.settings.privacy_version)):
            c.run("INSERT INTO consents(user_id, kind, version, ip) VALUES ($1,$2,$3,$4)", uid, kind, ver, ctx.ip)
        org_id = None
        if org:
            org_id = c.scalar("INSERT INTO organizations(kind, legal_name, trade_name, cnpj, uf, city, legal_nature_code, institutional_status)"
                              " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id::text", org.kind, org.legal_name, org.trade_name, cnpj, org.uf, org.city,
                              nature_code, "in_structuring" if org.kind in ("osc", "company", "government") and not cnpj else "registered")
            c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner')", uid, org_id)
            if org.kind in ("company", "individual"):
                c.run("INSERT INTO funder_profiles(org_id) VALUES ($1)", org_id)
            if org.kind == "provider":
                c.run("INSERT INTO provider_profiles(org_id) VALUES ($1)", org_id)
            from . import monetization
            monetization.start_trial(c, ctx.settings, org_id=org_id, org_kind=org.kind, email=email, cnpj=cnpj, user_id=uid, source="signup")
        # PROVA DO ACEITE. `consents` guarda a string de versão do arquivo de configuração; a prova
        # que serve a um questionamento jurídico é outra: documento, versão e HASH do texto, em
        # `legal_acceptances`. Até a v0.20.0 o cadastro não escrevia lá — a caixa "Li e aceito" era
        # conferida como booleano e nada ficava registrado.
        from . import legal as LEGAL
        aceitos = LEGAL.accept_on_signup(c, user_id=uid, org_id=org_id,
                                         audience=org.kind if org else None,
                                         ip=ctx.ip, user_agent=ctx.user_agent)
        tok = create_auth_token(c, uid, "verify_email", 60 * 48)
        from .audit import record
        record(c, org_id=org_id, actor=uid, action="user.registered", object_type="user", object_id=uid,
               payload={"org_kind": org.kind if org else None,
                        "legal_acceptances": [a["doc_key"] for a in aceitos]},
               ip=ctx.ip, request_id=ctx.request_id)
    link = f"{ctx.settings.public_base_url}/verificar-email?token={tok}"
    _send_after(ctx, email, "Confirme seu e-mail — Plataforma Impacto",
                f"Olá, {body.full_name}!\n\nConfirme seu e-mail para ativar todas as funções:\n{link}\n\nO link expira em 48 horas.")
    return {"status": "pending_verification", "message": "Se os dados forem válidos, enviaremos um e-mail de confirmação."}


def _send_after(ctx: Ctx, to: str, subject: str, text: str) -> None:
    try:
        ctx.app.mailer.send(to, subject, text)
    except Exception as exc:  # e-mail não pode derrubar o fluxo; fica registrado para reprocessamento
        log(logger, logging.ERROR, "mail_failed", error_type=type(exc).__name__)


def login(ctx: Ctx, body):
    email = body.email.lower()
    error: ApiError | None = None
    result = None
    with ctx.system_tx() as c:
        c.execute("SELECT pg_advisory_xact_lock(hashtext($1))", ("login:" + email,))
        u = c.one("SELECT id::text AS id, password_hash, status, mfa_enabled_at, failed_login_count, locked_until"
                  " FROM users WHERE email = $1", email)
        if u and u["locked_until"] and u["locked_until"] > _now():
            passwords.verify_password(body.password, None)
            error = ApiError(429, "account_locked", "Conta temporariamente bloqueada por excesso de tentativas. Tente mais tarde.")
        elif not passwords.verify_password(body.password, u["password_hash"] if u else None) or not u or u["status"] != "active":
            if u:
                n = u["failed_login_count"] + 1
                c.run("UPDATE users SET failed_login_count = $2::int, locked_until = CASE WHEN $2::int >= $3::int THEN now() + make_interval(mins => $4::int)"
                      " ELSE locked_until END WHERE id = $1", u["id"], n, LOCK_AFTER, LOCK_MINUTES)
                from .audit import record
                record(c, org_id=None, actor=u["id"], action="auth.login_failed", object_type="user", object_id=u["id"],
                       payload={"attempt": n}, ip=ctx.ip, request_id=ctx.request_id)
            # resposta idêntica para usuário inexistente, desativado e senha errada
            error = ApiError(401, "invalid_credentials", "E-mail ou senha inválidos")
        else:
            c.run("UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE id = $1", u["id"])
            if passwords.needs_rehash(u["password_hash"]):
                c.run("UPDATE users SET password_hash = $2 WHERE id = $1", u["id"], passwords.hash_password(body.password))
            if u["mfa_enabled_at"]:
                tok = create_auth_token(c, u["id"], "mfa_challenge", 5)
                result = json_response({"mfa_required": True, "mfa_token": tok})
            else:
                org_id = default_org(c, u["id"], body.org_id)
                c.run("UPDATE users SET last_login_at = now() WHERE id = $1", u["id"])
                tokens = issue_session(c, ctx, u["id"], org_id, mfa_verified=False)
                from .audit import record
                record(c, org_id=org_id, actor=u["id"], action="auth.login", object_type="session", object_id=tokens["session_id"],
                       payload={"mfa": False}, ip=ctx.ip, request_id=ctx.request_id)
                result = session_response(ctx, tokens, {"mfa_required": False})
    if error:
        raise error
    return result


def mfa_login(ctx: Ctx, body):
    error: ApiError | None = None
    with ctx.system_tx() as c:
        row = c.one("SELECT t.id, t.user_id::text AS user_id, t.attempts, u.mfa_secret_enc, u.mfa_recovery_hashes, u.status"
                    " FROM auth_tokens t JOIN users u ON u.id = t.user_id WHERE t.token_hash = $1 AND t.purpose = 'mfa_challenge'"
                    " AND t.used_at IS NULL AND t.expires_at > now() FOR UPDATE OF t", sha256_hex(body.mfa_token))
        if not row or row["status"] != "active":
            raise ApiError(401, "invalid_mfa_token", "Desafio MFA inválido ou expirado. Faça login novamente.")
        if row["attempts"] >= 5:
            c.run("UPDATE auth_tokens SET used_at = now() WHERE id = $1", row["id"])
            error = ApiError(429, "too_many_attempts", "Muitas tentativas. Faça login novamente.")
        ok = False
        if error:
            pass
        elif body.code:
            secret = ctx.app.cipher.decrypt(row["mfa_secret_enc"])
            ok = totp.verify(secret, body.code) is not None
        elif body.recovery_code:
            h = sha256_hex(body.recovery_code.strip().upper())
            if h in (row["mfa_recovery_hashes"] or []):
                ok = True
                c.run("UPDATE users SET mfa_recovery_hashes = array_remove(mfa_recovery_hashes, $2) WHERE id = $1", row["user_id"], h)
        if not ok and not error:
            c.run("UPDATE auth_tokens SET attempts = attempts + 1 WHERE id = $1", row["id"])
            error = ApiError(401, "invalid_mfa_code", "Código inválido")
        if error:
            tokens = None
        else:
            c.run("UPDATE auth_tokens SET used_at = now() WHERE id = $1", row["id"])
            org_id = default_org(c, row["user_id"], None)
            c.run("UPDATE users SET last_login_at = now() WHERE id = $1", row["user_id"])
            tokens = issue_session(c, ctx, row["user_id"], org_id, mfa_verified=True)
            from .audit import record
            record(c, org_id=org_id, actor=row["user_id"], action="auth.login", object_type="session", object_id=tokens["session_id"],
                   payload={"mfa": True, "recovery_code": bool(body.recovery_code)}, ip=ctx.ip, request_id=ctx.request_id)
    if error:
        raise error
    return session_response(ctx, tokens, {"mfa_required": False})


def refresh(ctx: Ctx, body):
    error: ApiError | None = None
    tokens = None
    names = cookie_names(ctx.settings.cookie_secure)
    rt = (body.refresh_token if body and body.refresh_token else None) or ctx.request.cookies.get(names["refresh"])
    if not rt:
        raise ApiError(401, "no_refresh_token", "Sessão expirada")
    with ctx.system_tx() as c:
        s = c.one("SELECT id::text AS id, user_id::text AS user_id, org_id::text AS org_id, family_id::text AS family_id,"
                  " rotated_at, revoked_at, refresh_expires_at, mfa_verified FROM sessions WHERE refresh_hash = $1 FOR UPDATE",
                  sha256_hex(rt))
        if not s or s["refresh_expires_at"] < _now():
            raise ApiError(401, "invalid_refresh_token", "Sessão expirada")
        if s["rotated_at"] or s["revoked_at"]:
            # Reuso de refresh token já rotacionado ⇒ possível roubo: revoga toda a família.
            c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'refresh_reuse' WHERE family_id = $1 AND revoked_at IS NULL",
                  s["family_id"])
            from .audit import record
            record(c, org_id=s["org_id"], actor=s["user_id"], action="auth.refresh_reuse_detected", object_type="session",
                   object_id=s["id"], payload={}, ip=ctx.ip, request_id=ctx.request_id)
            log(logger, logging.WARNING, "refresh_reuse_detected", user_id=s["user_id"])
            error = ApiError(401, "refresh_reuse", "Sessão invalidada por segurança. Faça login novamente.")
        else:
            u = c.one("SELECT status FROM users WHERE id = $1", s["user_id"])
            if not u or u["status"] != "active":
                error = ApiError(401, "invalid_refresh_token", "Sessão expirada")
            else:
                c.run("UPDATE sessions SET rotated_at = now(), revoked_at = now(), revoke_reason = 'rotated' WHERE id = $1", s["id"])
                tokens = issue_session(c, ctx, s["user_id"], s["org_id"], s["mfa_verified"], family_id=s["family_id"])
    if error:
        raise error
    return session_response(ctx, tokens)


def logout(ctx: Ctx, everywhere: bool = False):
    p = ctx.principal
    with ctx.system_tx() as c:
        if everywhere:
            c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'logout_all' WHERE user_id = $1 AND revoked_at IS NULL", p.user_id)
        else:
            c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'logout' WHERE id = $1", p.session_id)
        from .audit import record
        record(c, org_id=p.org_id, actor=p.user_id, action="auth.logout", object_type="session", object_id=p.session_id,
               payload={"everywhere": everywhere}, ip=ctx.ip, request_id=ctx.request_id)
    resp = json_response(None, 204)
    clear_session_cookies(ctx, resp)
    return resp


def verify_email(ctx: Ctx, token: str) -> dict:
    with ctx.system_tx() as c:
        row = consume_auth_token(c, token, "verify_email")
        if not row:
            raise ApiError(400, "invalid_token", "Link inválido ou expirado")
        c.run("UPDATE users SET email_verified_at = coalesce(email_verified_at, now()) WHERE id = $1", row["user_id"])
        from .audit import record
        record(c, org_id=None, actor=row["user_id"], action="user.email_verified", object_type="user", object_id=row["user_id"],
               payload={}, ip=ctx.ip, request_id=ctx.request_id)
    return {"verified": True}


def resend_verification(ctx: Ctx) -> dict:
    p = ctx.principal
    if p.email_verified:
        return {"status": "already_verified"}
    with ctx.system_tx() as c:
        tok = create_auth_token(c, p.user_id, "verify_email", 60 * 48)
    _send_after(ctx, p.email, "Confirme seu e-mail — Plataforma Impacto",
                f"Confirme seu e-mail:\n{ctx.settings.public_base_url}/verificar-email?token={tok}")
    return {"status": "sent"}


def forgot_password(ctx: Ctx, email: str) -> dict:
    email = email.lower()
    with ctx.system_tx() as c:
        u = c.one("SELECT id::text AS id, status FROM users WHERE email = $1", email)
        tok = create_auth_token(c, u["id"], "reset_password", 30) if u and u["status"] == "active" else None
    if tok:
        _send_after(ctx, email, "Redefinição de senha — Plataforma Impacto",
                    f"Para criar uma nova senha, acesse (válido por 30 minutos):\n{ctx.settings.public_base_url}/redefinir-senha?token={tok}\n\n"
                    "Se você não solicitou, ignore este e-mail.")
    return {"status": "ok", "message": "Se o e-mail estiver cadastrado, enviaremos instruções."}


def reset_password(ctx: Ctx, token: str, new_password: str) -> dict:
    with ctx.system_tx() as c:
        row = consume_auth_token(c, token, "reset_password")
        if not row:
            raise ApiError(400, "invalid_token", "Link inválido ou expirado")
        email = c.scalar("SELECT email::text FROM users WHERE id = $1", row["user_id"])
        problems = passwords.password_problems(new_password, email)
        if problems:
            raise unprocessable("Senha fraca", [{"field": "password", "message": p} for p in problems])
        c.run("UPDATE users SET password_hash = $2, failed_login_count = 0, locked_until = NULL WHERE id = $1",
              row["user_id"], passwords.hash_password(new_password))
        c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'password_reset' WHERE user_id = $1 AND revoked_at IS NULL",
              row["user_id"])
        from .audit import record
        record(c, org_id=None, actor=row["user_id"], action="auth.password_reset", object_type="user", object_id=row["user_id"],
               payload={}, ip=ctx.ip, request_id=ctx.request_id)
    return {"status": "ok"}


def change_password(ctx: Ctx, current: str, new: str) -> dict:
    p = ctx.principal
    with ctx.system_tx() as c:
        h = c.scalar("SELECT password_hash FROM users WHERE id = $1", p.user_id)
        if not passwords.verify_password(current, h):
            raise ApiError(401, "invalid_credentials", "Senha atual incorreta")
        problems = passwords.password_problems(new, p.email)
        if problems:
            raise unprocessable("Senha fraca", [{"field": "new_password", "message": x} for x in problems])
        c.run("UPDATE users SET password_hash = $2 WHERE id = $1", p.user_id, passwords.hash_password(new))
        c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'password_changed' WHERE user_id = $1 AND id <> $2"
              " AND revoked_at IS NULL", p.user_id, p.session_id)
        from .audit import record
        record(c, org_id=p.org_id, actor=p.user_id, action="auth.password_changed", object_type="user", object_id=p.user_id,
               payload={}, ip=ctx.ip, request_id=ctx.request_id)
    return {"status": "ok"}


def mfa_setup(ctx: Ctx) -> dict:
    p = ctx.principal
    if p.mfa_enabled:
        raise ApiError(409, "mfa_already_enabled", "MFA já está ativo")
    secret = totp.new_secret()
    with ctx.system_tx() as c:
        c.run("UPDATE users SET mfa_secret_enc = $2 WHERE id = $1", p.user_id, ctx.app.cipher.encrypt(secret))
    return {"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, p.email)}


def mfa_enable(ctx: Ctx, code: str) -> dict:
    p = ctx.principal
    with ctx.system_tx() as c:
        enc = c.scalar("SELECT mfa_secret_enc FROM users WHERE id = $1 AND mfa_enabled_at IS NULL", p.user_id)
        if not enc:
            raise ApiError(409, "mfa_not_pending", "Inicie a configuração do MFA primeiro")
        if totp.verify(ctx.app.cipher.decrypt(enc), code) is None:
            raise ApiError(400, "invalid_mfa_code", "Código inválido")
        codes = totp.recovery_codes()
        c.run("UPDATE users SET mfa_enabled_at = now(), mfa_recovery_hashes = $2::text[] WHERE id = $1",
              p.user_id, [sha256_hex(x) for x in codes])
        c.run("UPDATE sessions SET mfa_verified = true WHERE id = $1", p.session_id)
        from .audit import record
        record(c, org_id=p.org_id, actor=p.user_id, action="auth.mfa_enabled", object_type="user", object_id=p.user_id,
               payload={}, ip=ctx.ip, request_id=ctx.request_id)
    return {"enabled": True, "recovery_codes": codes, "message": "Guarde os códigos de recuperação em local seguro. Eles não serão exibidos novamente."}


def mfa_disable(ctx: Ctx, password: str, code: str) -> dict:
    p = ctx.principal
    with ctx.system_tx() as c:
        u = c.one("SELECT password_hash, mfa_secret_enc, is_platform_admin FROM users WHERE id = $1", p.user_id)
        if u["is_platform_admin"] and ctx.settings.require_mfa_for_admins:
            raise forbidden_admin_mfa()
        if not passwords.verify_password(password, u["password_hash"]) or not u["mfa_secret_enc"] \
                or totp.verify(ctx.app.cipher.decrypt(u["mfa_secret_enc"]), code) is None:
            raise ApiError(401, "invalid_credentials", "Senha ou código inválidos")
        c.run("UPDATE users SET mfa_enabled_at = NULL, mfa_secret_enc = NULL, mfa_recovery_hashes = '{}' WHERE id = $1", p.user_id)
        from .audit import record
        record(c, org_id=p.org_id, actor=p.user_id, action="auth.mfa_disabled", object_type="user", object_id=p.user_id,
               payload={}, ip=ctx.ip, request_id=ctx.request_id)
    return {"enabled": False}


def forbidden_admin_mfa() -> ApiError:
    return ApiError(403, "mfa_required_for_admin", "Administradores não podem desativar o MFA")


def switch_org(ctx: Ctx, org_id: str) -> dict:
    p = ctx.principal
    with ctx.system_tx() as c:
        ok = default_org(c, p.user_id, org_id)
        if ok != org_id:
            raise ApiError(404, "not_found", "Organização não encontrada")
        c.run("UPDATE sessions SET org_id = $2 WHERE id = $1", p.session_id, org_id)
    return {"org_id": org_id}


def me(ctx: Ctx) -> dict:
    p = ctx.principal
    from .entitlements import effective
    with ctx.tx(readonly=True) as c:
        orgs = c.query("SELECT o.id::text AS id, o.kind, o.legal_name, o.trade_name, o.compliance_status, m.role"
                       " FROM memberships m JOIN organizations o ON o.id = m.org_id WHERE m.user_id = $1 AND o.status = 'active'"
                       " ORDER BY o.legal_name", p.user_id)
        ent = effective(c, p.org_id, p.org_kind) if p.org_id else None
        unread = c.scalar("SELECT count(*) FROM notifications WHERE read_at IS NULL") if p.org_id else 0
    return {"user": {"id": p.user_id, "email": p.email, "full_name": p.full_name, "email_verified": p.email_verified,
                     "mfa_enabled": p.mfa_enabled, "mfa_verified": p.mfa_verified, "is_platform_admin": p.is_platform_admin,
                     "staff_roles": list(p.staff_roles)},
            "active_org": next((o for o in orgs if o["id"] == p.org_id), None), "organizations": orgs,
            "entitlements": ent and {k: ent[k] for k in ("plans", "plan_names", "features", "limits")},
            "subscription": ent and ent["subscription"], "unread_notifications": unread,
            "csrf_token": csrf_for_session(ctx.settings.secret_key, p.session_id) if p.via == "cookie" else None}


def create_org(ctx: Ctx, body) -> dict:
    p = ctx.principal
    cnpj = only_digits(body.cnpj) if body.cnpj else None
    if body.kind in ("osc", "company", "government") and not cnpj:
        raise unprocessable("CNPJ é obrigatório para este tipo de organização")
    if cnpj and not cnpj_valid(cnpj):
        raise unprocessable("CNPJ inválido")
    with ctx.system_tx() as c:
        n = c.scalar("SELECT count(*) FROM memberships WHERE user_id = $1 AND role = 'owner'", p.user_id)
        if n >= 5 and not p.is_platform_admin:
            raise unprocessable("Limite de 5 organizações próprias por usuário")
        if cnpj and c.one("SELECT 1 FROM organizations WHERE cnpj = $1", cnpj):
            raise ApiError(409, "cnpj_in_use", "Já existe organização com este CNPJ. Peça um convite ao responsável.")
        oid = c.scalar("INSERT INTO organizations(kind, legal_name, trade_name, cnpj, uf, city) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id::text",
                       body.kind, body.legal_name, body.trade_name, cnpj, body.uf, body.city)
        c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,'owner')", p.user_id, oid)
        if body.kind in ("company", "individual"):
            c.run("INSERT INTO funder_profiles(org_id) VALUES ($1)", oid)
        if body.kind == "provider":
            c.run("INSERT INTO provider_profiles(org_id) VALUES ($1)", oid)
        c.run("UPDATE sessions SET org_id = $2 WHERE id = $1", p.session_id, oid)
        from .audit import record
        record(c, org_id=oid, actor=p.user_id, action="org.created", object_type="organization", object_id=oid,
               payload={"kind": body.kind}, ip=ctx.ip, request_id=ctx.request_id)
    return {"id": oid}


# ------------------------------------------------------------------------------------------------
# Convites e equipe
# ------------------------------------------------------------------------------------------------
def invite(ctx: Ctx, email: str, role: str) -> dict:
    from .entitlements import check_limit
    email = email.lower()
    if role == "admin":
        ctx.require_role("owner")
    with ctx.tx() as c:
        seats = c.scalar("SELECT count(*) FROM memberships WHERE org_id = $1", ctx.org_id) + \
            c.scalar("SELECT count(*) FROM invitations WHERE org_id = $1 AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > now()", ctx.org_id)
        check_limit(c, ctx, "seats", seats)
        tok = new_token()
        iid = c.scalar("INSERT INTO invitations(org_id, email, role, token_hash, invited_by, expires_at)"
                       " VALUES ($1,$2,$3,$4,$5, now() + interval '7 days') RETURNING id::text",
                       ctx.org_id, email, role, sha256_hex(tok), ctx.user_id)
        ctx.audit(c, "member.invited", "invitation", iid, {"role": role})
    _send_after(ctx, email, f"Convite para {ctx.principal.org_name} — Plataforma Impacto",
                f"{ctx.principal.full_name} convidou você para participar de {ctx.principal.org_name} como {role}.\n"
                f"Aceite em: {ctx.settings.public_base_url}/convite?token={tok}\n(Válido por 7 dias.)")
    return {"id": iid, "status": "sent"}


def accept_invite(ctx: Ctx, token: str) -> dict:
    p = ctx.principal
    with ctx.system_tx() as c:
        inv = c.one("SELECT id::text AS id, org_id::text AS org_id, email::text AS email, role FROM invitations WHERE token_hash = $1"
                    " AND accepted_at IS NULL AND revoked_at IS NULL AND expires_at > now() FOR UPDATE", sha256_hex(token))
        if not inv:
            raise ApiError(400, "invalid_token", "Convite inválido ou expirado")
        if inv["email"].lower() != p.email.lower():
            raise ApiError(403, "invite_email_mismatch", "Este convite foi enviado para outro e-mail")
        c.run("INSERT INTO memberships(user_id, org_id, role) VALUES ($1,$2,$3) ON CONFLICT (user_id, org_id) DO NOTHING",
              p.user_id, inv["org_id"], inv["role"])
        c.run("UPDATE invitations SET accepted_at = now() WHERE id = $1", inv["id"])
        c.run("UPDATE sessions SET org_id = $2 WHERE id = $1", p.session_id, inv["org_id"])
        if not p.email_verified:
            # aceitar convite enviado ao e-mail comprova a posse do endereço
            c.run("UPDATE users SET email_verified_at = now() WHERE id = $1", p.user_id)
        from .audit import record
        record(c, org_id=inv["org_id"], actor=p.user_id, action="member.joined", object_type="invitation", object_id=inv["id"],
               payload={"role": inv["role"]}, ip=ctx.ip, request_id=ctx.request_id)
    return {"org_id": inv["org_id"]}
