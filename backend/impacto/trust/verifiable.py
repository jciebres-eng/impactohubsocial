"""Verificação pública por terceiro.

Princípio de projeto: **a página pública NÃO lê tabela privada.** O que será mostrado é curado no momento em que o
registro público é criado e fica em ``verifiable_records.public_fields``. Assim, mudar uma tabela do domínio nunca
passa a vazar dado novo na página pública por engano, e o que é público fica auditável em um lugar só.

O que um terceiro consegue responder com o código:
1. este documento é genuíno (existe registro e pertence a esta organização);
2. **qual versão** foi assinada (hash do conteúdo + número da versão);
3. a integridade permanece (hash declarado × hash recalculado do arquivo guardado);
4. quem assinou, em que papel e quando;
5. o registro está válido, substituído, expirado ou **revogado** (com motivo e data).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..db.pq import Connection, Json
from . import codes, custody, timestamps

SUBJECTS = ("document", "draft", "signature", "agreement", "credential")
PRIVACY_NOTE = ("Esta página mostra apenas o necessário para conferir a autenticidade. Nomes de pessoas aparecem somente "
                "quando a assinatura é profissional (o registro no conselho é público e consta do próprio documento). "
                "Nenhum conteúdo do documento, endereço, contato ou dado pessoal de beneficiários é exibido.")


def _custody_type(subject_type: str) -> str:
    return subject_type if subject_type in ("document", "draft", "agreement", "credential") else "document"


def _unique_code(conn: Connection) -> str:
    for _ in range(8):
        code = codes.new_code()
        if not conn.scalar("SELECT 1 FROM verifiable_records WHERE code = $1", code):
            return code
    raise RuntimeError("não foi possível gerar um código de verificação único")


def signer_display(sig: dict) -> str:
    """Nome só para assinatura PROFISSIONAL com credencial verificada — é o que consta do documento assinado.
    Nos outros papéis, mostra a organização e o papel, nunca o nome da pessoa."""
    if sig.get("role") == "professional" and sig.get("verification_status") == "verified" and sig.get("council"):
        uf = f"/{sig['council_uf']}" if sig.get("council_uf") else ""
        return f"{sig.get('full_name') or 'Profissional'} — {sig['council']} {sig['number']}{uf}"
    labels = {"legal_representative": "Representante legal", "funder": "Financiador", "professional": "Profissional",
              "witness": "Testemunha", "contractor": "Contratante", "provider": "Prestador"}
    return f"{labels.get(sig.get('role'), 'Parte')} — {sig.get('legal_name') or 'organização'}"


def build_public_fields(conn: Connection, *, subject_type: str, subject_id: str, org_id: str,
                        extra: dict[str, Any] | None = None) -> dict[str, Any]:
    org = conn.one("SELECT legal_name, trade_name, city, uf, kind FROM organizations WHERE id = $1", org_id) or {}
    sigs = conn.query(
        "SELECT s.role, s.signed_at, s.method, user_display_name(s.signer_user_id) AS full_name, o.legal_name,"
        " pc.council, pc.number, pc.uf AS council_uf, pc.verification_status,"
        " (SELECT 1 FROM signature_revocations r WHERE r.signature_id = s.id) AS revoked"
        " FROM signatures s JOIN organizations o ON o.id = s.signer_org_id"
        " LEFT JOIN professional_credentials pc ON pc.id = s.credential_id"
        " WHERE s.subject_type = $1 AND s.subject_id = $2 ORDER BY s.signed_at",
        subject_type if subject_type in ("document", "draft") else "document", subject_id)
    return {
        "organization": {"name": org.get("trade_name") or org.get("legal_name"), "city": org.get("city"),
                         "uf": org.get("uf"), "kind": org.get("kind")},
        "signers": [{"role": s["role"], "signed_at": s["signed_at"], "method": s["method"],
                     "display": signer_display(s), "revoked": bool(s.get("revoked"))} for s in sigs],
        **(extra or {}),
    }


def create(conn: Connection, *, org_id: str, subject_type: str, subject_id: str, title: str, content_sha256: str,
           subject_version: int = 1, public_fields: dict[str, Any] | None = None, created_by: str | None = None,
           expires_at: str | None = None, secret_key: str | None = None) -> dict:
    if subject_type not in SUBJECTS:
        raise ValueError(f"objeto não verificável: {subject_type}")
    code = _unique_code(conn)
    row = conn.one(
        "INSERT INTO verifiable_records(code, subject_type, subject_id, org_id, title, content_sha256, subject_version,"
        " public_fields, created_by, expires_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10::timestamptz)"
        " RETURNING id::text AS id, code, issued_at, status",
        code, subject_type, subject_id, org_id, title, content_sha256, subject_version,
        Json(public_fields or {}), created_by, expires_at)
    # trust_events aceita document/draft/agreement/credential/identity; um registro de 'signature' é custodiado como documento
    custody_type = subject_type if subject_type in ("document", "draft", "agreement", "credential") else "document"
    custody.record(conn, subject_type=custody_type, subject_id=subject_id, org_id=org_id, event_type="created",
                   actor_user_id=created_by, content_sha256=content_sha256,
                   payload={"verification_code": code, "record_id": row["id"]})
    stamp = None
    if secret_key:
        stamp = timestamps.stamp_internal(conn, record_id=row["id"], hashed_value=content_sha256, secret_key=secret_key,
                                          subject_type=custody_type, subject_id=subject_id, org_id=org_id)
    return {**row, "timestamp": stamp}


def revoke(conn: Connection, *, record_id: str, org_id: str, reason: str, by: str) -> dict:
    r = conn.one("SELECT id::text AS id, subject_type, subject_id::text AS subject_id, status, code"
                 " FROM verifiable_records WHERE id = $1 AND org_id = $2", record_id, org_id)
    if not r:
        return {"found": False}
    if r["status"] == "revoked":
        return {"found": True, "already": True, "code": r["code"]}
    conn.run("UPDATE verifiable_records SET status = 'revoked', revoked_at = now(), revocation_reason = $2, revoked_by = $3"
             " WHERE id = $1", record_id, reason, by)
    custody.record(conn, subject_type=_custody_type(r["subject_type"]), subject_id=r["subject_id"], org_id=org_id, event_type="revoked",
                   actor_user_id=by, payload={"reason": reason, "verification_code": r["code"]})
    return {"found": True, "already": False, "code": r["code"], "status": "revoked"}


def supersede(conn: Connection, *, old_record_id: str, new_record_id: str, org_id: str, by: str | None = None) -> bool:
    r = conn.one("SELECT subject_type, subject_id::text AS subject_id, code FROM verifiable_records"
                 " WHERE id = $1 AND org_id = $2 AND status = 'active'", old_record_id, org_id)
    if not r:
        return False
    conn.run("UPDATE verifiable_records SET status = 'superseded', superseded_by = $2 WHERE id = $1",
             old_record_id, new_record_id)
    custody.record(conn, subject_type=_custody_type(r["subject_type"]), subject_id=r["subject_id"], org_id=org_id,
                   event_type="superseded", actor_user_id=by, payload={"superseded_by": new_record_id})
    return True


def public_lookup(conn: Connection, raw_code: str, *, storage=None, record_access: bool = True) -> dict:
    """Consulta pública. Roda em contexto de sistema (a página é aberta sem login) e devolve SOMENTE campos curados."""
    code = codes.normalize(raw_code)
    if not code:
        return {"found": False, "reason": "malformed"}
    r = conn.one(
        "SELECT id::text AS id, code, subject_type, subject_id::text AS subject_id, org_id::text AS org_id, title,"
        " content_sha256, subject_version, status, public_fields, issued_at, expires_at, revoked_at, revocation_reason,"
        " superseded_by::text AS superseded_by FROM verifiable_records WHERE code = $1", code)
    if not r:
        return {"found": False, "reason": "unknown_code"}

    status = r["status"]
    if status == "active" and r["expires_at"] and r["expires_at"] < datetime.now(UTC):
        status = "expired"

    # integridade: o arquivo guardado continua batendo com o hash registrado?
    integrity: dict[str, Any] = {"checked": False}
    current_version = r["subject_version"]
    if r["subject_type"] == "document":
        d = conn.one("SELECT sha256, version, deleted_at FROM documents WHERE id = $1", r["subject_id"])
        if not d:
            integrity = {"checked": True, "intact": False, "detail": "documento não está mais disponível na plataforma"}
        else:
            current_version = d["version"]
            same = d["sha256"] == r["content_sha256"]
            integrity = {"checked": True, "intact": same,
                         "detail": None if same else "o conteúdo atual do documento é diferente do que foi registrado"}
            if same and storage is not None:
                try:
                    from .integrity import sha256_bytes
                    key = conn.scalar("SELECT storage_key FROM documents WHERE id = $1", r["subject_id"])
                    integrity["storage_verified"] = sha256_bytes(storage.get(key)) == r["content_sha256"]
                except (OSError, ValueError):
                    integrity["storage_verified"] = None
    elif r["subject_type"] == "draft":
        cur = conn.scalar("SELECT content_sha256 FROM drafts WHERE id = $1", r["subject_id"])
        integrity = {"checked": True, "intact": cur == r["content_sha256"],
                     "detail": None if cur == r["content_sha256"] else "o conteúdo atual é diferente do que foi assinado"}

    stamps = conn.query("SELECT kind, authority, stamped_at FROM trust_timestamps WHERE record_id = $1 ORDER BY stamped_at",
                        r["id"])
    chain = conn.one("SELECT entries, valid FROM trust_verify($1, $2)", _custody_type(r["subject_type"]), r["subject_id"]) or {}

    if record_access:
        conn.run("UPDATE verifiable_records SET access_count = access_count + 1, last_accessed_at = now() WHERE id = $1", r["id"])
        custody.record(conn, subject_type=_custody_type(r["subject_type"]), subject_id=r["subject_id"], org_id=r["org_id"],
                       event_type="verified_public", payload={"verification_code": code})

    public = r["public_fields"] or {}
    return {
        "found": True,
        "code": code,
        "status": status,
        "genuine": status in ("active", "superseded"),
        "title": r["title"],
        "subject_type": r["subject_type"],
        "signed_version": r["subject_version"],
        "current_version": current_version,
        "version_is_current": current_version == r["subject_version"],
        "content_sha256": r["content_sha256"],
        "issued_at": r["issued_at"],
        "expires_at": r["expires_at"],
        "revoked_at": r["revoked_at"],
        "revocation_reason": r["revocation_reason"],
        "integrity": integrity,
        "organization": public.get("organization"),
        "signers": public.get("signers", []),
        "timestamps": stamps,
        "custody_chain": {"entries": chain.get("entries"), "valid": chain.get("valid")},
        "privacy_note": PRIVACY_NOTE,
    }
