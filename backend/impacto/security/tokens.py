"""Tokens opacos, hashes e assinaturas HMAC (URLs temporárias, CSRF, assinatura eletrônica)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def sha256_hex(value: str | bytes) -> str:
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def hmac_hex(key: str, message: str) -> str:
    return hmac.new(key.encode(), message.encode(), hashlib.sha256).hexdigest()


def csrf_for_session(secret: str, session_id: str) -> str:
    return hmac_hex(secret, "csrf:" + session_id)


def sign_payload(secret: str, payload: dict, ttl_seconds: int) -> str:
    body = dict(payload, exp=int(time.time()) + ttl_seconds)
    raw = base64.urlsafe_b64encode(json.dumps(body, separators=(",", ":"), sort_keys=True).encode()).decode().rstrip("=")
    return raw + "." + hmac_hex(secret, raw)


def verify_payload(secret: str, token: str) -> dict | None:
    try:
        raw, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, hmac_hex(secret, raw)):
        return None
    try:
        body = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
    except Exception:  # noqa: BLE001 - corpo malformado é token inválido (a assinatura já foi conferida acima)
        return None
    if int(body.get("exp", 0)) < int(time.time()):
        return None
    return body
