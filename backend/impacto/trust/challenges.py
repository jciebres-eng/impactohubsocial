"""Segunda camada da assinatura: código de uso único entregue fora do formulário.

Camada 1 (já existia): reautenticação por senha no momento de assinar.
Camada 2 (nova): código de 6 dígitos enviado por e-mail, válido por 10 minutos, ligado ao **hash exato** do conteúdo.
Se o conteúdo mudar entre pedir o código e assinar, o código não serve — é por isso que o hash entra no desafio.

SMS: previsto no domínio, **não implementado** (não há provedor de SMS na plataforma). A API recusa com mensagem clara
em vez de fingir que enviou.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from ..db.pq import Connection

TTL_MINUTES = 10
MAX_ATTEMPTS = 5
SMS_UNAVAILABLE = ("Envio por SMS não está implementado nesta instalação (sem provedor de SMS). "
                   "Use o canal de e-mail para receber o código de assinatura.")


def _hash(code: str) -> str:
    return hashlib.sha256(f"impacto-sigchal-v1|{code}".encode()).hexdigest()


def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create(conn: Connection, *, user_id: str, subject_type: str, subject_id: str, subject_sha256: str,
           channel: str = "email", destination_hint: str | None = None) -> tuple[str, dict]:
    """Devolve (código em claro, registro). O código em claro só é usado para o envio — nunca é persistido."""
    from ..http import ApiError
    if channel == "sms":
        raise ApiError(501, "channel_unavailable", SMS_UNAVAILABLE)
    if channel != "email":
        raise ApiError(422, "validation_error", "Canal inválido")
    code = new_code()
    expires = (datetime.now(UTC) + timedelta(minutes=TTL_MINUTES)).isoformat()
    conn.run("DELETE FROM signature_challenges WHERE user_id = $1 AND subject_type = $2 AND subject_id = $3 AND used_at IS NULL",
             user_id, subject_type, subject_id)
    row = conn.one("INSERT INTO signature_challenges(user_id, subject_type, subject_id, subject_sha256, channel,"
                   " destination_hint, code_hash, expires_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::timestamptz)"
                   " RETURNING id::text AS id, expires_at",
                   user_id, subject_type, subject_id, subject_sha256, channel, destination_hint, _hash(code), expires)
    return code, {"id": row["id"], "expires_at": row["expires_at"], "channel": channel,
                  "destination_hint": destination_hint, "ttl_minutes": TTL_MINUTES}


def consume(conn: Connection, *, user_id: str, subject_type: str, subject_id: str, subject_sha256: str, code: str) -> dict:
    """Valida e QUEIMA o código. Roda em contexto de sistema (precisa marcar tentativa mesmo em caso de erro)."""
    row = conn.one("SELECT id::text AS id, code_hash, subject_sha256, expires_at, used_at, attempts"
                   " FROM signature_challenges WHERE user_id = $1 AND subject_type = $2 AND subject_id = $3"
                   " ORDER BY created_at DESC LIMIT 1", user_id, subject_type, subject_id)
    if not row:
        return {"ok": False, "reason": "no_challenge"}
    if row["used_at"]:
        return {"ok": False, "reason": "already_used"}
    if row["attempts"] >= MAX_ATTEMPTS:
        return {"ok": False, "reason": "too_many_attempts"}
    if row["expires_at"] < datetime.now(UTC):
        return {"ok": False, "reason": "expired"}
    conn.run("UPDATE signature_challenges SET attempts = attempts + 1 WHERE id = $1", row["id"])
    if not hmac.compare_digest(row["code_hash"], _hash(code or "")):
        return {"ok": False, "reason": "wrong_code", "attempts_left": MAX_ATTEMPTS - row["attempts"] - 1}
    if row["subject_sha256"] != subject_sha256:
        return {"ok": False, "reason": "content_changed"}
    conn.run("UPDATE signature_challenges SET used_at = now() WHERE id = $1", row["id"])
    return {"ok": True, "challenge_id": row["id"]}


REASONS = {
    "no_challenge": "Peça o código de confirmação antes de assinar.",
    "already_used": "Este código já foi usado. Peça um novo.",
    "too_many_attempts": "Muitas tentativas com código errado. Peça um novo código.",
    "expired": "O código expirou. Peça um novo.",
    "wrong_code": "Código de confirmação incorreto.",
    "content_changed": "O conteúdo mudou depois que o código foi enviado. Peça um novo código e confira o documento.",
}
