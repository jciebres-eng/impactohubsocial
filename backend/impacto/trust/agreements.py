"""Acordos assinados por várias partes (contratação de profissional, parceria, financiamento, cessão de dados).

Regras do domínio:
* o acordo nasce ``draft``; as partes são definidas nessa fase;
* ao publicar vira ``awaiting_signatures`` e o **hash do documento é congelado** (``guard_columns`` impede alterar);
* cada parte assina **com a mesma assinatura em duas camadas** do resto da plataforma (senha + código);
* o acordo só vira ``active`` quando TODAS as partes obrigatórias assinaram — nunca por decisão de uma parte;
* se uma parte recusa, o acordo vai para ``canceled`` com o motivo registrado;
* o acompanhamento longitudinal fica em ``signed_agreement_milestones`` (entregas, relatórios, documentos ao longo do tempo).
"""
from __future__ import annotations

from ..db.pq import Connection
from . import custody

KINDS = ("service", "partnership", "funding", "volunteer", "data_sharing", "other")
ROLES = ("contractor", "provider", "funder", "professional", "witness", "beneficiary_rep")


def detail(conn: Connection, agreement_id: str) -> dict | None:
    a = conn.one(
        "SELECT a.id::text AS id, a.org_id::text AS org_id, a.project_id::text AS project_id, a.kind, a.title, a.summary,"
        " a.document_id::text AS document_id, a.content_sha256, a.status, a.effective_from, a.effective_to, a.value_cents,"
        " a.created_at, a.updated_at, o.legal_name AS owner_name,"
        " (SELECT code FROM verifiable_records r WHERE r.subject_type = 'agreement' AND r.subject_id = a.id"
        "  AND r.status = 'active' ORDER BY r.created_at DESC LIMIT 1) AS verification_code"
        " FROM signed_agreements a JOIN organizations o ON o.id = a.org_id WHERE a.id = $1", agreement_id)
    if not a:
        return None
    a["parties"] = conn.query(
        "SELECT p.id::text AS id, p.org_id::text AS org_id, o.legal_name, p.role, p.required, p.signed_at, p.declined_at,"
        " p.decline_reason, p.signature_id::text AS signature_id, p.user_id::text AS user_id,"
        " user_display_name(p.user_id) AS user_name FROM signed_agreement_parties p"
        " JOIN organizations o ON o.id = p.org_id WHERE p.agreement_id = $1 ORDER BY p.invited_at", agreement_id)
    a["milestones"] = conn.query(
        "SELECT id::text AS id, title, due_on, status, note, document_id::text AS document_id, reported_at,"
        " reported_by::text AS reported_by FROM signed_agreement_milestones WHERE agreement_id = $1 ORDER BY due_on NULLS LAST, created_at",
        agreement_id)
    pending = [p for p in a["parties"] if p["required"] and not p["signed_at"] and not p["declined_at"]]
    a["pending_signatures"] = len(pending)
    a["all_signed"] = not pending and any(p["signed_at"] for p in a["parties"])
    return a


def publish(conn: Connection, *, agreement_id: str, org_id: str, actor_user_id: str) -> dict:
    from ..http import ApiError
    a = conn.one("SELECT id::text AS id, status, content_sha256 FROM signed_agreements WHERE id = $1 AND org_id = $2",
                 agreement_id, org_id)
    if not a:
        raise ApiError(404, "not_found", "Acordo não encontrado")
    if a["status"] != "draft":
        raise ApiError(409, "not_draft", "Somente um acordo em rascunho pode ser enviado para assinatura")
    required = conn.scalar("SELECT count(*) FROM signed_agreement_parties WHERE agreement_id = $1 AND required", agreement_id)
    if (required or 0) < 2:
        raise ApiError(409, "parties_missing", "Um acordo precisa de pelo menos duas partes obrigatórias")
    conn.run("UPDATE signed_agreements SET status = 'awaiting_signatures' WHERE id = $1", agreement_id)
    custody.record(conn, subject_type="agreement", subject_id=agreement_id, org_id=org_id, event_type="created",
                   actor_user_id=actor_user_id, content_sha256=a["content_sha256"],
                   payload={"status": "awaiting_signatures", "required_parties": required})
    return {"id": agreement_id, "status": "awaiting_signatures", "required_parties": required}


def party_for(conn: Connection, *, agreement_id: str, org_id: str) -> dict | None:
    return conn.one("SELECT id::text AS id, role, required, signed_at, declined_at FROM signed_agreement_parties"
                    " WHERE agreement_id = $1 AND org_id = $2", agreement_id, org_id)


def mark_signed(conn: Connection, *, party_id: str, signature_id: str) -> None:
    """Contexto PRIVILEGIADO: a marcação de assinatura é coluna guardada — uma parte não marca a outra."""
    conn.run("UPDATE signed_agreement_parties SET signature_id = $2, signed_at = now() WHERE id = $1", party_id, signature_id)


def settle(conn: Connection, *, agreement_id: str) -> str:
    """Se todas as partes obrigatórias assinaram, o acordo passa a vigente. Contexto privilegiado."""
    pending = conn.scalar("SELECT count(*) FROM signed_agreement_parties WHERE agreement_id = $1 AND required"
                          " AND signed_at IS NULL AND declined_at IS NULL", agreement_id)
    declined = conn.scalar("SELECT count(*) FROM signed_agreement_parties WHERE agreement_id = $1 AND declined_at IS NOT NULL",
                           agreement_id)
    if declined:
        conn.run("UPDATE signed_agreements SET status = 'canceled' WHERE id = $1 AND status = 'awaiting_signatures'", agreement_id)
        return "canceled"
    if pending == 0:
        conn.run("UPDATE signed_agreements SET status = 'active' WHERE id = $1 AND status = 'awaiting_signatures'", agreement_id)
        return "active"
    return "awaiting_signatures"


def decline(conn: Connection, *, agreement_id: str, org_id: str, reason: str, actor_user_id: str) -> dict:
    from ..http import ApiError
    p = party_for(conn, agreement_id=agreement_id, org_id=org_id)
    if not p:
        raise ApiError(403, "not_a_party", "Sua organização não é parte deste acordo")
    if p["signed_at"]:
        raise ApiError(409, "already_signed", "Esta parte já assinou — use revogação da assinatura")
    conn.run("UPDATE signed_agreement_parties SET declined_at = now(), decline_reason = $2 WHERE id = $1", p["id"], reason)
    custody.record(conn, subject_type="agreement", subject_id=agreement_id, org_id=org_id, event_type="shared",
                   actor_user_id=actor_user_id, payload={"event": "declined", "role": p["role"], "reason": reason})
    return {"declined": True, "role": p["role"]}


def mine(conn: Connection, org_id: str, *, limit: int = 50, offset: int = 0) -> list[dict]:
    return conn.query(
        "SELECT a.id::text AS id, a.kind, a.title, a.status, a.effective_from, a.effective_to, a.value_cents, a.created_at,"
        " a.org_id::text AS org_id, o.legal_name AS owner_name,"
        " (SELECT count(*) FROM signed_agreement_parties p WHERE p.agreement_id = a.id AND p.required) AS required_parties,"
        " (SELECT count(*) FROM signed_agreement_parties p WHERE p.agreement_id = a.id AND p.signed_at IS NOT NULL) AS signed_parties,"
        " EXISTS (SELECT 1 FROM signed_agreement_parties p WHERE p.agreement_id = a.id AND p.org_id = $1"
        "         AND p.signed_at IS NULL AND p.declined_at IS NULL AND p.required) AS awaiting_me"
        " FROM signed_agreements a JOIN organizations o ON o.id = a.org_id"
        " WHERE a.org_id = $1 OR EXISTS (SELECT 1 FROM signed_agreement_parties p WHERE p.agreement_id = a.id AND p.org_id = $1)"
        " ORDER BY a.created_at DESC LIMIT $2 OFFSET $3", org_id, limit, offset)
