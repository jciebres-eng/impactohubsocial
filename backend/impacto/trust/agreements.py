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


def detail(conn: Connection, agreement_id: str, viewer_org_id: str | None = None) -> dict | None:
    a = conn.one(
        "SELECT a.id::text AS id, a.org_id::text AS org_id, a.project_id::text AS project_id, a.kind, a.title, a.summary,"
        " a.document_id::text AS document_id, a.content_sha256, a.status, a.effective_from, a.effective_to, a.value_cents,"
        " a.version, a.platform_fee_bps, a.fee_payer_role, a.fee_mode, a.review_days, a.calendar_type, a.auto_accept, a.dispute_days,"
        " a.created_at, a.updated_at, o.legal_name AS owner_name,"
        " (SELECT code FROM verifiable_records r WHERE r.subject_type = 'agreement' AND r.subject_id = a.id"
        "  AND r.status = 'active' ORDER BY r.created_at DESC LIMIT 1) AS verification_code"
        " FROM signed_agreements a JOIN organizations o ON o.id = a.org_id WHERE a.id = $1", agreement_id)
    if not a:
        return None
    a["parties"] = conn.query(
        "SELECT p.id::text AS id, p.org_id::text AS org_id, o.legal_name, p.role, p.required, p.signed_at, p.declined_at,"
        " p.pix_key_type, (p.pix_key IS NOT NULL) AS pix_informed, p.pix_key,"
        " p.decline_reason, p.signature_id::text AS signature_id, p.user_id::text AS user_id,"
        " user_display_name(p.user_id) AS user_name FROM signed_agreement_parties p"
        " JOIN organizations o ON o.id = p.org_id WHERE p.agreement_id = $1 ORDER BY p.invited_at", agreement_id)
    # A chave PIX inteira só para a própria parte e para o financiador (quem paga); para os demais, mascarada.
    from .economy import mask_pix
    funder_ids = {p["org_id"] for p in a["parties"] if p["role"] == "funder"}
    for p in a["parties"]:
        full = viewer_org_id is not None and (viewer_org_id == p["org_id"] or viewer_org_id in funder_ids)
        key = p.pop("pix_key", None)
        p["pix_key_masked"] = mask_pix(key, p["pix_key_type"]) if key else None
        p["pix_key"] = key if full else None
    a["milestones"] = conn.query(
        "SELECT id::text AS id, seq, title, due_on, status, note, document_id::text AS document_id, reported_at,"
        " reported_by::text AS reported_by, amount_cents, source, delivered_at, acceptance_due_on, accepted_at,"
        " accepted_by_org::text AS accepted_by_org, rejection_reason"
        " FROM signed_agreement_milestones WHERE agreement_id = $1 ORDER BY seq NULLS LAST, due_on NULLS LAST, created_at",
        agreement_id)
    # v0.26.0 — o contrato como regra operacional: versão, termos, obrigações derivadas e matriz de distribuição
    from . import contract_rules
    a["terms"] = conn.one("SELECT version, supersedes_id::text AS supersedes_id, superseded_by_id::text AS superseded_by_id,"
                          " version_reason, platform_fee_bps, fee_payer_role, fee_mode, review_days, calendar_type, auto_accept,"
                          " dispute_days, activated_at, proponent_participation_bps, economic_rule_version FROM signed_agreements WHERE id = $1", agreement_id)
    a["obligations"] = contract_rules.obligations(conn, agreement_id)
    from . import economy as ECO
    a["payouts"] = ECO.payouts(conn, agreement_id, viewer_org_id=viewer_org_id)
    a["settlement"] = ECO.settlement(conn, agreement_id)
    a["participations"] = conn.query("SELECT p.id::text AS id, p.proponent_org_id::text AS proponent_org_id, o.legal_name AS proponent_name,"
                                     " p.authorship_type, p.share_bps, p.status FROM proponent_participations p"
                                     " JOIN organizations o ON o.id = p.proponent_org_id WHERE p.project_id = $1::uuid ORDER BY p.created_at",
                                     a["project_id"]) if a.get("project_id") else []
    a["allocation"] = contract_rules.allocation(conn, agreement_id)
    a["allocation_preview"] = None if a["allocation"] else contract_rules.compute_allocation(conn, {**a, **a["terms"]}, a["parties"])
    a["versions"] = conn.query("SELECT version, content_sha256, reason, created_at FROM agreement_versions"
                               " WHERE lineage_id = (SELECT coalesce((SELECT lineage_id FROM agreement_versions WHERE agreement_id = $1 LIMIT 1), $1::uuid))"
                               " ORDER BY version", agreement_id)
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
    # v0.20.0: publicar um acordo o colocava em `awaiting_signatures` e NÃO avisava parte nenhuma.
    # O instrumento ficava esperando uma assinatura que ninguém sabia dever. Cada parte obrigatória
    # que ainda não assinou é avisada — menos quem publicou, que acabou de fazer isso.
    from ..network import notify
    for parte in conn.query(
            "SELECT org_id::text AS org_id FROM signed_agreement_parties"
            " WHERE agreement_id = $1 AND required AND signed_at IS NULL AND declined_at IS NULL",
            agreement_id):
        notify.org_event(
            conn, event="Agreement.signature_required", org_id=parte["org_id"],
            title="Assinatura pendente em instrumento",
            body=("O conteúdo foi congelado e está aguardando assinatura. A plataforma oferece "
                  "assinatura AVANÇADA própria; ela não emite nem homologa assinatura qualificada "
                  "(ICP-Brasil ou gov.br)."),
            link=f"/acordos/{agreement_id}", priority="high", min_role="admin",   # v0.26.0: o SPA não tem /instrumentos
            actor_user_id=actor_user_id if parte["org_id"] == org_id else None,
            ref_type="agreement", ref_id=agreement_id, action_label="Revisar e assinar",
            payload={"content_sha256": a["content_sha256"]},
            dedupe_parts=("Agreement.signature_required", agreement_id, parte["org_id"]))
    return {"id": agreement_id, "status": "awaiting_signatures", "required_parties": required}


def party_for(conn: Connection, *, agreement_id: str, org_id: str) -> dict | None:
    return conn.one("SELECT id::text AS id, role, required, signed_at, declined_at FROM signed_agreement_parties"
                    " WHERE agreement_id = $1 AND org_id = $2", agreement_id, org_id)


def mark_signed(conn: Connection, *, party_id: str, signature_id: str) -> None:
    """Contexto PRIVILEGIADO: a marcação de assinatura é coluna guardada — uma parte não marca a outra."""
    conn.run("UPDATE signed_agreement_parties SET signature_id = $2, signed_at = now() WHERE id = $1", party_id, signature_id)


def settle(conn: Connection, *, agreement_id: str, actor_user_id: str | None = None) -> str:
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
        # v0.26.0 — CONTRATO COMO REGRA OPERACIONAL: vigente, o acordo deriva obrigações e a matriz de
        # distribuição na mesma transação (contract_rules.activate). Antes, ficar `active` não produzia nada.
        from . import contract_rules
        contract_rules.activate(conn, agreement_id=agreement_id, actor_user_id=actor_user_id)
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
