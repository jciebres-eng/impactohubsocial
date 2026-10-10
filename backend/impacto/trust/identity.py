"""Identificação da pessoa (níveis de confiança).

Níveis: ``none`` → ``email`` → ``phone`` → ``document`` → ``professional`` → ``biometric``.

O que a plataforma FAZ: pede documento, guarda a referência no cofre, registra conferência humana, deriva o nível.
O que a plataforma NÃO FAZ (declarado, não simulado):
* reconhecimento facial e prova de vida — dependem de provedor contratado; nenhum vetor biométrico é armazenado aqui;
* consulta on-line a base oficial de documento — não há integração contratada;
* nível ``phone`` por SMS — não há provedor de SMS (ver ``challenges.py``).
O nível ``biometric`` só pode ser concedido por um provedor externo ativo no Integration Hub; sem isso, a tentativa é recusada.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json
from . import custody

LEVELS = ("email", "phone", "document", "professional", "biometric")
ORDER = {"none": 0, "email": 1, "phone": 2, "document": 3, "professional": 4, "biometric": 5}
METHODS = ("platform_token", "human_review", "council_document", "external_provider")

BIOMETRIC_UNAVAILABLE = ("Verificação biométrica e prova de vida dependem de provedor externo contratado e ativo. "
                         "Nenhum provedor de identidade está ativo nesta instalação.")
PHONE_UNAVAILABLE = ("Verificação por telefone depende de provedor de SMS, que não está implementado. "
                     "Use a verificação por documento com conferência humana.")


def level_of(conn: Connection, user_id: str) -> str:
    return conn.scalar("SELECT identity_level($1)", user_id) or "none"


def at_least(conn: Connection, user_id: str, minimum: str) -> bool:
    return ORDER.get(level_of(conn, user_id), 0) >= ORDER.get(minimum, 99)


def overview(conn: Connection, user_id: str) -> dict:
    rows = conn.query(
        "SELECT id::text AS id, level, status, method, provider_key, decided_at, decision_note, expires_at, created_at"
        " FROM identity_verifications WHERE user_id = $1 ORDER BY created_at", user_id)
    docs = conn.query(
        "SELECT d.id::text AS id, d.verification_id::text AS verification_id, d.kind, d.status, d.reject_reason,"
        " d.created_at, doc.title, doc.filename FROM identity_documents d JOIN documents doc ON doc.id = d.document_id"
        " WHERE d.user_id = $1 ORDER BY d.created_at", user_id)
    return {
        "level": level_of(conn, user_id),
        "levels": list(LEVELS),
        "verifications": rows,
        "documents": docs,
        "unavailable": {"biometric": BIOMETRIC_UNAVAILABLE, "phone": PHONE_UNAVAILABLE},
        "note": "A plataforma não faz biometria própria e não armazena imagem de face nem número de documento.",
    }


def request(conn: Connection, *, user_id: str, level: str, method: str = "human_review",
            provider_key: str | None = None, evidence: dict[str, Any] | None = None) -> dict:
    from ..http import ApiError
    if level not in LEVELS:
        raise ApiError(422, "validation_error", "Nível de identidade inválido")
    if level == "biometric":
        raise ApiError(501, "provider_not_configured", BIOMETRIC_UNAVAILABLE)
    if level == "phone":
        raise ApiError(501, "provider_not_configured", PHONE_UNAVAILABLE)
    if method not in METHODS:
        raise ApiError(422, "validation_error", "Método de verificação inválido")
    existing = conn.one("SELECT id::text AS id, status FROM identity_verifications WHERE user_id = $1 AND level = $2",
                        user_id, level)
    if existing and existing["status"] in ("pending", "under_review"):
        return {"id": existing["id"], "status": existing["status"], "reused": True}
    if existing and existing["status"] == "verified":
        raise ApiError(409, "already_verified", "Este nível já está verificado")
    if existing:
        conn.run("DELETE FROM identity_verifications WHERE id = $1", existing["id"])
    row = conn.one("INSERT INTO identity_verifications(user_id, level, method, provider_key, evidence)"
                   " VALUES ($1,$2,$3,$4,$5::jsonb) RETURNING id::text AS id, status",
                   user_id, level, method, provider_key, Json(evidence or {}))
    return {**row, "reused": False}


def attach_document(conn: Connection, *, verification_id: str, user_id: str, document_id: str, kind: str) -> dict:
    from ..http import ApiError
    v = conn.one("SELECT id::text AS id, status FROM identity_verifications WHERE id = $1 AND user_id = $2",
                 verification_id, user_id)
    if not v:
        raise ApiError(404, "not_found", "Verificação não encontrada")
    if v["status"] not in ("pending", "under_review"):
        raise ApiError(409, "not_open", "Esta verificação não está aberta para novos documentos")
    from ..services.documents import usable_statuses
    doc = conn.one("SELECT id::text AS id, status FROM documents WHERE id = $1 AND deleted_at IS NULL", document_id)
    if not doc:
        raise ApiError(404, "not_found", "Documento não encontrado")
    # 'pending_scan' é aceitável quando a instalação não tem antivírus configurado (mesma regra do download);
    # 'infected'/'rejected' nunca entram.
    if doc["status"] not in usable_statuses():
        raise ApiError(409, "document_not_usable",
                       "O documento está aguardando verificação antivírus ou foi recusado" if doc["status"] == "pending_scan"
                       else "Este documento foi recusado pela verificação de segurança")
    row = conn.one("INSERT INTO identity_documents(verification_id, user_id, document_id, kind)"
                   " VALUES ($1,$2,$3,$4) ON CONFLICT (verification_id, document_id) DO NOTHING"
                   " RETURNING id::text AS id", verification_id, user_id, document_id, kind)
    if row is None:
        return {"duplicate": True}
    return {"id": row["id"], "duplicate": False}


def mark_under_review(conn: Connection, verification_id: str) -> None:
    """Contexto PRIVILEGIADO. `identity_verifications.status` é coluna guardada (guard_columns, migração 0002/0012):
    nem a própria pessoa muda o estado pelo papel da aplicação. Isto só move pending → under_review."""
    conn.run("UPDATE identity_verifications SET status = 'under_review' WHERE id = $1 AND status = 'pending'",
             verification_id)


def decide(conn: Connection, *, verification_id: str, approve: bool, decided_by: str, note: str,
           expires_at: str | None = None) -> dict:
    """Decisão HUMANA (administração). Roda em contexto privilegiado — ninguém promove a própria identidade."""
    v = conn.one("SELECT id::text AS id, user_id::text AS user_id, level, status FROM identity_verifications WHERE id = $1 FOR UPDATE",
                 verification_id)
    if not v:
        return {"found": False}
    from ..http import ApiError
    # v0.35.0 (auditoria, KYC-01): ninguém decide a própria verificação (também conferido pelo banco), e decisão tomada não
    # é reescrita por outra decisão — mudar depois é suspender/revogar/restabelecer, com motivo (`change_status`).
    if v["user_id"] == decided_by:
        raise ApiError(403, "self_decision", "Ninguém decide a própria verificação de identidade")
    if v["status"] not in ("pending", "under_review"):
        raise ApiError(409, "already_decided", "Esta verificação já foi decidida; para mudar, suspenda ou revogue com motivo",
                       {"status": v["status"]})
    status = "verified" if approve else "rejected"
    conn.run("UPDATE identity_verifications SET status = $2, decided_by = $3, decided_at = now(), decision_note = $4,"
             " expires_at = $5::timestamptz WHERE id = $1", verification_id, status, decided_by, note, expires_at)
    conn.run("UPDATE identity_documents SET status = $2, reviewed_by = $3, reviewed_at = now() WHERE verification_id = $1",
             verification_id, "accepted" if approve else "rejected", decided_by)
    custody.record(conn, subject_type="identity", subject_id=v["user_id"], event_type="identity_decided",
                   actor_user_id=decided_by, payload={"level": v["level"], "status": status})
    return {"found": True, "status": status, "level": v["level"], "user_id": v["user_id"]}


STATUS_CHANGES = {"suspended": ("verified",), "revoked": ("verified", "suspended"), "verified": ("suspended",)}


def change_status(conn: Connection, *, verification_id: str, to: str, decided_by: str, note: str) -> dict:
    """v0.35.0 (auditoria, KYC-01): estados depois da decisão — `suspended` (reversível: dúvida em apuração), `revoked`
    (definitivo: documento falso, pedido da pessoa), e `verified` de novo só a partir de `suspended`. Contexto privilegiado."""
    from ..http import ApiError
    if to not in STATUS_CHANGES:
        raise ApiError(422, "invalid_status", "Estado não permitido", {"possiveis": sorted(STATUS_CHANGES)})
    v = conn.one("SELECT id::text AS id, user_id::text AS user_id, level, status FROM identity_verifications WHERE id = $1 FOR UPDATE",
                 verification_id)
    if not v:
        return {"found": False}
    if v["user_id"] == decided_by:
        raise ApiError(403, "self_decision", "Ninguém muda o estado da própria verificação de identidade")
    if v["status"] not in STATUS_CHANGES[to]:
        raise ApiError(409, "invalid_transition", f"De '{v['status']}' não se vai para '{to}'", {"from": v["status"], "to": to})
    conn.run("UPDATE identity_verifications SET status = $2, decided_by = $3, decided_at = now(), decision_note = $4 WHERE id = $1",
             verification_id, to, decided_by, note)
    custody.record(conn, subject_type="identity", subject_id=v["user_id"], event_type="identity_decided",
                   actor_user_id=decided_by, payload={"level": v["level"], "from": v["status"], "status": to, "change": True})
    return {"found": True, "status": to, "from": v["status"], "level": v["level"], "user_id": v["user_id"]}


def expire_due(conn: Connection) -> int:
    """Verificação com validade vencida passa a `expired` (antes nada gravava esse estado; `identity_level()` já ignorava
    a vencida, mas a tela e a fila continuavam dizendo "verificado"). Contexto privilegiado (rotina diária)."""
    return conn.run("UPDATE identity_verifications SET status = 'expired' WHERE status = 'verified' AND expires_at IS NOT NULL"
                    " AND expires_at <= now()")


def queue(conn: Connection, limit: int = 50, offset: int = 0, *, state: str = "open") -> list[dict]:
    estados = ["pending", "under_review"] if state == "open" else ["verified", "suspended", "rejected", "revoked", "expired"]
    return conn.query(
        "SELECT v.id::text AS id, v.level, v.status, v.method, v.created_at, v.decided_at, v.expires_at, v.user_id::text AS user_id,"
        " user_display_name(v.user_id) AS user_name,"
        " (SELECT count(*) FROM identity_documents d WHERE d.verification_id = v.id) AS documents"
        " FROM identity_verifications v WHERE v.status = ANY($3::text[])"
        " ORDER BY coalesce(v.decided_at, v.created_at) DESC LIMIT $1 OFFSET $2", limit, offset, estados)
