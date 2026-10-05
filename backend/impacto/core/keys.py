"""Chaves de cifragem: inventário, versionamento, rotação com recifragem e auditoria.

O que já existia: `FieldCipher` usa `MultiFernet` — a primeira chave cifra, **todas** decifram. Isso faz a rotação
funcionar na leitura, mas não respondia a três perguntas que importam em produção:

1. **quais chaves estão em uso?** → `encryption_keys` guarda a *impressão digital* de cada chave (nunca a chave).
2. **os dados antigos foram recifrados?** → `reencrypt()` relê e regrava com a chave corrente, em lote, e conta.
3. **quem rodou a rotação e o que acontececeu?** → `encryption_rotations` registra total, recifrados, falhas e resultado.

O que NÃO existe aqui: KMS e HSM. Eles dependem de infraestrutura contratada. O que existe é a **abstração**
(`KeyProvider`) com um provedor local baseado em variável de ambiente — honesto e testável. Nenhum HSM é inventado.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Protocol

from ..db.pq import Connection

PURPOSES = ("field", "integration", "signature_seal")
# Colunas cifradas por FieldCipher, por tabela. Rotacionar = reler e regravar cada uma.
ENCRYPTED_COLUMNS: dict[str, tuple[str, str, str]] = {
    # tabela: (coluna cifrada, coluna identificadora, finalidade)
    "users": ("mfa_secret_enc", "id", "field"),
}
# `integration_credentials.secret_cipher` é bytea e NÃO é legível pelo papel da aplicação (GRANT por coluna na 0011):
# a recifragem dessa coluna exige o papel dono do banco e está descrita em KEY_ROTATION.md, não automatizada aqui.


def derived_field_key(secret: str) -> str:
    """A MESMA derivação do FieldCipher quando FIELD_ENCRYPTION_KEY não está configurada."""
    return base64.urlsafe_b64encode(hashlib.sha256(("field:" + secret).encode()).digest()).decode()


class KeyProvider(Protocol):
    """Contrato de provedor de chave. O provedor local lê de variável de ambiente; KMS/HSM entram por aqui."""

    name: str

    def current(self, purpose: str) -> str: ...
    def all_keys(self, purpose: str) -> list[str]: ...


class EnvKeyProvider:
    """Provedor local: as chaves vêm da configuração do processo (FIELD_ENCRYPTION_KEY, SECRET_KEY)."""

    name = "env"

    def __init__(self, settings):
        self.settings = settings

    def _raw(self, purpose: str) -> list[str]:
        if purpose == "field":
            raw = getattr(self.settings, "field_encryption_key", "") or ""
            if not raw and not getattr(self.settings, "is_hardened", False):
                # espelha FieldCipher: sem chave própria, a chave REALMENTE em uso é a derivada do SECRET_KEY.
                # O inventário precisa dizer a verdade sobre qual chave protege o dado hoje.
                return [derived_field_key(getattr(self.settings, "secret_key", "") or "")]
        elif purpose == "integration":
            raw = getattr(self.settings, "integration_secret_key", "") or getattr(self.settings, "secret_key", "")
        else:
            raw = getattr(self.settings, "secret_key", "")
        return [k.strip() for k in str(raw).split(",") if k.strip()]

    def current(self, purpose: str) -> str:
        keys = self._raw(purpose)
        return keys[0] if keys else ""

    def all_keys(self, purpose: str) -> list[str]:
        return self._raw(purpose)


KMS_UNAVAILABLE = ("Gerenciamento de chave em KMS/HSM depende de infraestrutura contratada (AWS KMS, GCP KMS, Azure "
                   "Key Vault ou HSM). Não está implementado: o provedor em uso é o local, baseado na configuração do "
                   "processo. Ativação descrita em KEY_ROTATION.md.")


def fingerprint(key: str) -> str:
    """Identifica a chave sem revelá-la: 16 hex do SHA-256 com rótulo de domínio."""
    return hashlib.sha256(("impacto-key-fingerprint-v1|" + (key or "")).encode()).hexdigest()[:16]


def register(conn: Connection, provider: KeyProvider, *, purpose: str, note: str | None = None) -> dict:
    """Registra as chaves em uso para esta finalidade. A corrente fica `active`; as demais, `decrypt_only`."""
    keys = provider.all_keys(purpose)
    if not keys:
        return {"purpose": purpose, "registered": 0, "reason": "nenhuma chave configurada para esta finalidade"}
    fps = [fingerprint(k) for k in keys]
    existing = {r["fingerprint"]: r for r in conn.query(
        "SELECT id::text AS id, version, fingerprint, state FROM encryption_keys WHERE purpose = $1", purpose)}
    next_version = (conn.scalar("SELECT coalesce(max(version), 0) FROM encryption_keys WHERE purpose = $1", purpose) or 0)
    registered = []
    for i, fp in enumerate(fps):
        state = "active" if i == 0 else "decrypt_only"
        if fp in existing:
            if existing[fp]["state"] != state:
                conn.run("UPDATE encryption_keys SET state = $2, retired_at = CASE WHEN $2 = 'retired' THEN now() END"
                         " WHERE id = $1", existing[fp]["id"], state)
            registered.append({"fingerprint": fp, "version": existing[fp]["version"], "state": state, "new": False})
            continue
        next_version += 1
        conn.run("INSERT INTO encryption_keys(purpose, version, fingerprint, state, note) VALUES ($1,$2,$3,$4,$5)",
                 purpose, next_version, fp, state, note)
        registered.append({"fingerprint": fp, "version": next_version, "state": state, "new": True})
    # chave que saiu da configuração vira 'retired' (continua no inventário para explicar dado antigo)
    for fp, row in existing.items():
        if fp not in fps and row["state"] != "retired":
            conn.run("UPDATE encryption_keys SET state = 'retired', retired_at = now() WHERE id = $1", row["id"])
    return {"purpose": purpose, "provider": provider.name, "registered": registered,
            "active_fingerprint": fps[0], "decrypt_only": len(fps) - 1}


def inventory(conn: Connection) -> dict:
    rows = conn.query("SELECT purpose, version, fingerprint, state, activated_at, retired_at, note"
                      " FROM encryption_keys ORDER BY purpose, version")
    rotations = conn.query("SELECT id, purpose, from_version, to_version, table_name, rows_total, rows_reencrypted,"
                           " rows_failed, status, detail, started_at, finished_at, actor_user_id::text AS actor_user_id"
                           " FROM encryption_rotations ORDER BY id DESC LIMIT 20")
    return {"keys": rows, "rotations": rotations, "kms": KMS_UNAVAILABLE,
            "note": "A impressão digital identifica a chave sem revelá-la. A chave NUNCA é gravada no banco."}


def reencrypt(conn: Connection, cipher, *, table: str, actor_user_id: str | None = None, batch: int = 500) -> dict:
    """Relê e regrava a coluna cifrada com a chave corrente. Idempotente: rodar duas vezes não causa dano.

    Contexto PRIVILEGIADO (as tabelas de chave são só da administração). A contagem e o resultado ficam auditados.
    """
    from ..http import ApiError
    spec = ENCRYPTED_COLUMNS.get(table)
    if not spec:
        raise ApiError(422, "table_not_rotatable",
                       f"Tabela '{table}' não tem coluna cifrada registrada. Disponíveis: {', '.join(ENCRYPTED_COLUMNS)}")
    column, ident, purpose = spec
    active = conn.one("SELECT version, fingerprint FROM encryption_keys WHERE purpose = $1 AND state = 'active'", purpose)
    previous = conn.scalar("SELECT max(version) FROM encryption_keys WHERE purpose = $1 AND state = 'decrypt_only'", purpose)
    total = conn.scalar(f"SELECT count(*) FROM {table} WHERE {column} IS NOT NULL") or 0
    rot_id = conn.scalar("INSERT INTO encryption_rotations(purpose, from_version, to_version, table_name, rows_total,"
                         " status, actor_user_id) VALUES ($1,$2,$3,$4,$5,'running',$6) RETURNING id",
                         purpose, previous, (active or {}).get("version") or 1, table, total, actor_user_id)
    done = failed = 0
    details: list[str] = []
    offset = 0
    while True:
        rows = conn.query(f"SELECT {ident}::text AS k, {column} AS v FROM {table} WHERE {column} IS NOT NULL"
                          f" ORDER BY {ident} LIMIT {batch} OFFSET {offset}")
        if not rows:
            break
        for r in rows:
            try:
                plain = cipher.decrypt(r["v"])
            except ValueError:
                failed += 1
                if len(details) < 5:
                    details.append(f"{table}.{r['k']}: não foi possível decifrar com as chaves configuradas")
                continue
            conn.run(f"UPDATE {table} SET {column} = $2 WHERE {ident} = $1", r["k"], cipher.encrypt(plain))
            done += 1
        offset += batch
    status = "completed" if not failed else ("partial" if done else "failed")
    conn.run("UPDATE encryption_rotations SET rows_reencrypted = $2, rows_failed = $3, status = $4, detail = $5,"
             " finished_at = now() WHERE id = $1", rot_id, done, failed, status, "; ".join(details)[:2000] or None)
    return {"rotation_id": rot_id, "table": table, "purpose": purpose, "rows_total": total,
            "rows_reencrypted": done, "rows_failed": failed, "status": status,
            "active_key": (active or {}).get("fingerprint"), "details": details}
