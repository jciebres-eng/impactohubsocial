"""Login corporativo via OpenID Connect (Authorization Code + PKCE S256), com validação do id_token por JWKS
(assinatura, iss, aud, exp, nonce) e exigência de e-mail verificado pelo IdP.
Configuração: OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_REDIRECT_URI (ex.: https://app/v1/auth/oidc/callback).
Compatível com Microsoft Entra ID, Google Workspace, Keycloak, Okta, Auth0 e gov.br (sujeito a credenciamento)."""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import urllib.parse

import jwt

from ..adapters.http_client import HttpClient
from ..http import ApiError, Ctx
from ..security.tokens import sha256_hex

_DISCOVERY: dict = {}


def enabled(s) -> bool:
    return bool(s.oidc_issuer and s.oidc_client_id and s.oidc_redirect_uri)


def discovery(s, http: HttpClient | None = None) -> dict:
    cached = _DISCOVERY.get(s.oidc_issuer)
    if cached and cached[0] > time.time():
        return cached[1]
    status, _, raw = (http or HttpClient(retries=1)).request("GET", s.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration", timeout=10)
    if status != 200:
        raise ApiError(502, "oidc_discovery_failed", "Provedor de identidade indisponível")
    data = json.loads(raw)
    if data.get("issuer", "").rstrip("/") != s.oidc_issuer.rstrip("/"):
        raise ApiError(502, "oidc_issuer_mismatch", "Issuer do provedor não confere com a configuração")
    _DISCOVERY[s.oidc_issuer] = (time.time() + 3600, data)
    return data


def start(ctx: Ctx, redirect_to: str) -> str:
    s = ctx.settings
    if not enabled(s):
        raise ApiError(404, "oidc_disabled", "SSO não configurado")
    if not redirect_to.startswith("/") or redirect_to.startswith("//"):
        redirect_to = "/"
    d = discovery(s)
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    with ctx.system_tx() as c:
        c.run("INSERT INTO oidc_states(state_hash, nonce, code_verifier, redirect_to, expires_at) VALUES ($1,$2,$3,$4, now() + interval '10 minutes')",
              sha256_hex(state), nonce, verifier, redirect_to)
    q = {"response_type": "code", "client_id": s.oidc_client_id, "redirect_uri": s.oidc_redirect_uri, "scope": "openid email profile",
         "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256"}
    return d["authorization_endpoint"] + "?" + urllib.parse.urlencode(q)


def callback(ctx: Ctx, code: str, state: str, http: HttpClient | None = None) -> tuple[dict, str]:
    s = ctx.settings
    if not enabled(s):
        raise ApiError(404, "oidc_disabled", "SSO não configurado")
    with ctx.system_tx() as c:
        st = c.one("DELETE FROM oidc_states WHERE state_hash = $1 AND expires_at > now() RETURNING nonce, code_verifier, redirect_to", sha256_hex(state or ""))
    if not st:
        raise ApiError(400, "oidc_invalid_state", "Sessão de login expirada ou inválida")
    d = discovery(s, http)
    body = urllib.parse.urlencode({"grant_type": "authorization_code", "code": code, "redirect_uri": s.oidc_redirect_uri,
                                   "client_id": s.oidc_client_id, "client_secret": s.oidc_client_secret,
                                   "code_verifier": st["code_verifier"]}).encode()
    status, _, raw = (http or HttpClient(retries=1)).request("POST", d["token_endpoint"], data=body, timeout=15,
                                                             headers={"Content-Type": "application/x-www-form-urlencoded"})
    if status != 200:
        raise ApiError(401, "oidc_token_failed", "Falha ao validar o login no provedor de identidade")
    id_token = json.loads(raw).get("id_token")
    if not id_token:
        raise ApiError(401, "oidc_no_id_token", "Provedor não retornou id_token")
    try:
        key = jwt.PyJWKClient(d["jwks_uri"], cache_keys=True).get_signing_key_from_jwt(id_token).key
        claims = jwt.decode(id_token, key, algorithms=["RS256", "ES256", "PS256"], audience=s.oidc_client_id,
                            issuer=d["issuer"], options={"require": ["exp", "iat", "sub", "iss", "aud"]}, leeway=60)
    except jwt.PyJWTError as exc:
        raise ApiError(401, "oidc_invalid_token", f"id_token inválido: {type(exc).__name__}") from exc
    if claims.get("nonce") != st["nonce"]:
        raise ApiError(401, "oidc_nonce_mismatch", "Nonce inválido")
    email = (claims.get("email") or "").lower()
    if not email or claims.get("email_verified") is not True:
        raise ApiError(403, "oidc_email_unverified", "O provedor precisa informar e-mail verificado")
    amr = claims.get("amr") or []
    mfa = any(x in ("mfa", "otp", "hwk", "swk", "fido", "sms") for x in (amr if isinstance(amr, list) else [amr]))
    return {"sub": f"{d['issuer']}|{claims['sub']}", "email": email, "name": claims.get("name") or email.split("@")[0], "mfa": mfa}, st["redirect_to"]


def login_or_provision(ctx: Ctx, ident: dict) -> dict:
    from .auth import default_org, issue_session
    from .audit import record
    with ctx.system_tx() as c:
        u = c.one("SELECT id::text AS id, status, oidc_subject FROM users WHERE oidc_subject = $1", ident["sub"]) or \
            c.one("SELECT id::text AS id, status, oidc_subject FROM users WHERE email = $1", ident["email"])
        if u and u["status"] != "active":
            raise ApiError(403, "account_disabled", "Conta desativada")
        if u and u["oidc_subject"] and u["oidc_subject"] != ident["sub"]:
            raise ApiError(409, "oidc_subject_conflict", "Conta vinculada a outra identidade corporativa")
        if not u:
            uid = c.scalar("INSERT INTO users(email, full_name, oidc_subject, email_verified_at) VALUES ($1,$2,$3, now()) RETURNING id::text",
                           ident["email"], ident["name"][:160], ident["sub"])
            for kind, ver in (("terms", ctx.settings.terms_version), ("privacy", ctx.settings.privacy_version)):
                c.run("INSERT INTO consents(user_id, kind, version, ip) VALUES ($1,$2,$3,$4)", uid, kind, ver, ctx.ip)
        else:
            uid = u["id"]
            c.run("UPDATE users SET oidc_subject = $2, email_verified_at = coalesce(email_verified_at, now()), last_login_at = now() WHERE id = $1",
                  uid, ident["sub"])
        # MFA só é considerado verificado se o IdP declarar (claim amr); caso contrário, a área admin continua exigindo TOTP.
        tokens = issue_session(c, ctx, uid, default_org(c, uid), mfa_verified=bool(ident.get("mfa")))
        record(c, org_id=None, actor=uid, action="auth.login_oidc", object_type="session", object_id=tokens["session_id"],
               payload={"issuer": ctx.settings.oidc_issuer}, ip=ctx.ip, request_id=ctx.request_id)
    return tokens
