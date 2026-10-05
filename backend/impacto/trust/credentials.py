"""Credencial profissional: catálogo de conselhos e fluxo de verificação.

O que é verificado aqui: a pessoa apresentou documento do conselho e **alguém da equipe conferiu**. O histórico é
append-only (``credential_verifications``) e a promoção do estado é privilegiada (gatilho ``guard_columns`` de 0002).

O que NÃO é verificado: não há consulta on-line a conselho (CFP, CRM, CRC, OAB… não expõem API pública contratada).
Portanto `verified` significa **"documento conferido pela equipe"**, nunca "confirmado junto ao conselho".
"""
from __future__ import annotations

from ..db.pq import Connection
from . import custody

VERIFIED_MEANING = ("'Verificada' significa que a equipe da plataforma conferiu o documento apresentado. "
                    "A plataforma não consulta o conselho profissional on-line.")
ACTIONS = ("submitted", "document_attached", "verified", "rejected", "expired", "revoked", "reopened")


def councils(conn: Connection) -> list[dict]:
    return conn.query("SELECT code, name, profession, uf_required, number_pattern, official_site, lookup_note,"
                      " source_name, source_date FROM professional_councils WHERE active ORDER BY code")


def log(conn: Connection, *, credential_id: str, org_id: str, action: str, actor_user_id: str | None = None,
        method: str = "human_review", document_id: str | None = None, note: str | None = None) -> dict:
    if action not in ACTIONS:
        raise ValueError(f"ação de credencial desconhecida: {action}")
    return conn.one("INSERT INTO credential_verifications(credential_id, org_id, action, actor_user_id, method,"
                    " document_id, note) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id, at",
                    credential_id, org_id, action, actor_user_id, method, document_id, note)


def history(conn: Connection, credential_id: str) -> list[dict]:
    return conn.query("SELECT id, action, method, note, at, actor_user_id::text AS actor_user_id,"
                      " user_display_name(actor_user_id) AS actor_name, document_id::text AS document_id"
                      " FROM credential_verifications WHERE credential_id = $1 ORDER BY id", credential_id)


def attach_document(conn: Connection, *, credential_id: str, org_id: str, document_id: str, actor_user_id: str) -> dict:
    from ..http import ApiError
    cred = conn.one("SELECT id::text AS id, verification_status FROM professional_credentials WHERE id = $1 AND org_id = $2",
                    credential_id, org_id)
    if not cred:
        raise ApiError(404, "not_found", "Credencial não encontrada")
    if cred["verification_status"] == "verified":
        raise ApiError(409, "already_verified", "Credencial já verificada")
    from ..services.documents import usable_statuses
    doc = conn.one("SELECT status FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", document_id, org_id)
    if not doc:
        raise ApiError(404, "not_found", "Documento não encontrado")
    if doc["status"] not in usable_statuses():
        raise ApiError(409, "document_not_usable", "O documento está aguardando verificação antivírus ou foi recusado")
    conn.run("UPDATE professional_credentials SET document_id = $2 WHERE id = $1", credential_id, document_id)
    log(conn, credential_id=credential_id, org_id=org_id, action="document_attached", actor_user_id=actor_user_id,
        document_id=document_id, note="Documento do conselho anexado para conferência")
    return {"id": credential_id, "verification_status": "document_submitted"}


def mark_submitted(conn: Connection, credential_id: str) -> None:
    """Contexto PRIVILEGIADO. `verification_status` é guardada desde a migração 0002 — a organização anexa o documento,
    mas não declara o próprio estado. Isto só move self_declared/rejected/expired → document_submitted."""
    conn.run("UPDATE professional_credentials SET verification_status = 'document_submitted'"
             " WHERE id = $1 AND verification_status IN ('self_declared','rejected','expired')", credential_id)


def decide(conn: Connection, *, credential_id: str, approve: bool, decided_by: str, note: str,
           valid_until: str | None = None) -> dict:
    """Decisão da equipe (contexto privilegiado). Aprovar também eleva a identidade da pessoa ao nível 'professional'."""
    cred = conn.one("SELECT id::text AS id, org_id::text AS org_id, user_id::text AS user_id, council, number,"
                    " verification_status FROM professional_credentials WHERE id = $1", credential_id)
    if not cred:
        return {"found": False}
    status = "verified" if approve else "rejected"
    conn.run("UPDATE professional_credentials SET verification_status = $2, verified_by = $3, verified_at = now(),"
             " verification_note = $4, valid_until = coalesce($5::date, valid_until) WHERE id = $1",
             credential_id, status, decided_by, note, valid_until)
    log(conn, credential_id=credential_id, org_id=cred["org_id"], action=status, actor_user_id=decided_by,
        method="council_document", note=note)
    custody.record(conn, subject_type="credential", subject_id=credential_id, org_id=cred["org_id"],
                   event_type="credential_decided", actor_user_id=decided_by,
                   payload={"status": status, "council": cred["council"]})
    if approve:
        conn.run("INSERT INTO identity_verifications(user_id, level, method, status, decided_by, decided_at, decision_note)"
                 " VALUES ($1,'professional','council_document','verified',$2, now(), $3)"
                 " ON CONFLICT (user_id, level) DO UPDATE SET status = 'verified', decided_by = $2, decided_at = now(),"
                 " decision_note = $3", cred["user_id"], decided_by, f"Credencial {cred['council']} {cred['number']} conferida")
    return {"found": True, "verification_status": status, "meaning": VERIFIED_MEANING}


def revoke(conn: Connection, *, credential_id: str, reason: str, revoked_by: str) -> dict:
    cred = conn.one("SELECT id::text AS id, org_id::text AS org_id FROM professional_credentials WHERE id = $1", credential_id)
    if not cred:
        return {"found": False}
    conn.run("UPDATE professional_credentials SET verification_status = 'rejected', revoked_at = now(),"
             " revocation_reason = $2 WHERE id = $1", credential_id, reason)
    log(conn, credential_id=credential_id, org_id=cred["org_id"], action="revoked", actor_user_id=revoked_by, note=reason)
    custody.record(conn, subject_type="credential", subject_id=credential_id, org_id=cred["org_id"],
                   event_type="credential_decided", actor_user_id=revoked_by, payload={"status": "revoked", "reason": reason})
    return {"found": True, "verification_status": "rejected", "revoked": True}


def queue(conn: Connection, limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.query(
        "SELECT c.id::text AS id, c.council, c.council_code, c.number, c.uf, c.holder_name, c.verification_status,"
        " c.valid_until, c.created_at, c.org_id::text AS org_id, o.legal_name, c.document_id::text AS document_id"
        " FROM professional_credentials c JOIN organizations o ON o.id = c.org_id"
        " WHERE c.verification_status = 'document_submitted' ORDER BY c.created_at LIMIT $1 OFFSET $2", limit, offset)
