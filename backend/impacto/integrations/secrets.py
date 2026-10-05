"""Credenciais de integração: cifradas em repouso, nunca devolvidas pela API, nunca em log.

REUTILIZA `security/crypto.FieldCipher` (Fernet com rotação de chave, já usado nos segredos de MFA). A coluna cifrada
não tem SELECT para o papel da aplicação: a leitura passa pela função SECURITY DEFINER `integration_secret()`.
Para quem usa gerenciador externo, `SecretProvider` permite guardar só a REFERÊNCIA (kind='secret_ref').
"""
from __future__ import annotations

from typing import Protocol

from ..http import ApiError


class SecretProvider(Protocol):
    """Interface para gerenciador de segredos externo (Vault, Secrets Manager...). Não há implementação embutida."""

    def resolve(self, ref: str) -> str:
        ...


def hint(secret: str) -> str:
    """Dica exibível: nunca o segredo. Mostra só os 4 últimos caracteres."""
    s = (secret or "").strip()
    return ("•" * 4 + s[-4:]) if len(s) >= 8 else "•" * 6


def store(c, cipher, *, connection_id: str, kind: str, secret: str | None, secret_ref: str | None,
          username: str | None, scopes: list[str], expires_at, user_id: str | None) -> dict:
    """Grava (ou substitui) a credencial da conexão. O segredo em claro nunca é persistido nem registrado."""
    if kind == "secret_ref":
        if not secret_ref:
            raise ApiError(422, "secret_ref_required", "Informe a referência do segredo no gerenciador externo")
        cipher_text = None
        shown = f"ref:{secret_ref[:24]}"
    else:
        if not secret or len(secret) < 8:
            raise ApiError(422, "secret_too_short", "Segredo ausente ou muito curto (mínimo de 8 caracteres)")
        cipher_text = cipher.encrypt(secret).encode()
        shown = hint(secret)
    c.run("DELETE FROM integration_credentials WHERE connection_id = $1 AND kind = $2", connection_id, kind)
    c.run("INSERT INTO integration_credentials(connection_id, kind, secret_cipher, secret_ref, hint, username, scopes, expires_at, created_by,"
          " rotated_at) VALUES ($1,$2,$3,$4,$5,$6,$7::text[],$8,$9, now())",
          connection_id, kind, cipher_text, secret_ref, shown, username, scopes or [], expires_at, user_id)
    return {"kind": kind, "hint": shown}


def load(c, cipher, *, connection_id: str, provider: SecretProvider | None = None) -> tuple[str | None, str | None, str | None]:
    """Devolve (segredo em claro na memória, usuário, tipo) da credencial da conexão — ou (None, None, None)."""
    row = c.one("SELECT id::text AS id, kind, secret_ref, username FROM integration_credentials WHERE connection_id = $1"
                " ORDER BY created_at DESC LIMIT 1", connection_id)
    if not row:
        return None, None, None
    if row["kind"] == "secret_ref":
        if provider is None:
            return None, row["username"], row["kind"]
        return provider.resolve(row["secret_ref"]), row["username"], row["kind"]
    blob = c.scalar("SELECT integration_secret($1)", row["id"])     # SELECT direto na coluna é negado por GRANT
    if blob is None:
        return None, row["username"], row["kind"]
    raw = bytes(blob) if not isinstance(blob, (bytes, bytearray)) else blob
    return cipher.decrypt(raw.decode()), row["username"], row["kind"]


def auth_headers(kind: str | None, secret: str | None, username: str | None) -> dict:
    """Cabeçalhos de autenticação por tipo de credencial. Sem credencial, devolve vazio (o adapter decide o que fazer)."""
    import base64
    if not secret or not kind:
        return {}
    if kind == "api_key":
        return {"X-API-Key": secret}
    if kind in ("bearer_token", "oauth2_client_credentials", "oauth2_refresh"):
        return {"Authorization": f"Bearer {secret}"}
    if kind == "basic_auth":
        token = base64.b64encode(f"{username or ''}:{secret}".encode()).decode()
        return {"Authorization": f"Basic {token}"}
    return {}
