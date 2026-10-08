"""CAMADA ECONÔMICA DA OPERAÇÃO (v0.27.0) — regra versionada, participação de autoria, instruções de
repasse não custodiais, ledger econômico e reconhecimento por quitação.

A tese: a plataforma não vende assinatura. A remuneração nasce de EVENTO ECONÔMICO contratual — o
acordo de financiamento em vigor — e o financiador faz UM aporte direcionado a cada destinatário
pela chave PIX informada no contrato. Aqui:

  * `rule_for()`          — percentual do catálogo versionado (economic_rules), congelado no acordo;
  * participações         — autoria/desenvolvimento da ideia com estados e aceite PELO PROPONENTE;
  * `instruct_payouts()`  — uma instrução por linha da matriz (projeto, plataforma, proponente);
  * transferências        — quem paga registra (quando quiser); quem RECEBE confirma; conciliação é
                            passo separado; nada vira "pago" por existir registro;
  * `economic_event()`    — ledger append-only e idempotente: quem → pagou → quem → quanto → por quê;
  * `settle_if_complete()`— operação quitada = todas as entregas aceitas E todos os repasses devidos
                            confirmados; só então nascem reconhecimentos (nunca por pagar a plataforma).

Nada aqui move dinheiro (ADR-284).
"""
from __future__ import annotations

import json
from typing import Any

from ..db.pq import Connection, Json
from ..http import ApiError

PLATFORM_RULE = "funding.platform_service"
PROPONENT_RULE = "funding.proponent_participation"
PIX_TYPES = ("cpf", "cnpj", "email", "phone", "evp")


# ------------------------------------------------------------------ regras versionadas
def rule_for(conn: Connection, key: str, pricing_version: str) -> dict | None:
    return conn.one("SELECT key, pricing_version, bps, payer_role, recipient_kind, monetization_rule_key, label_pt, what_it_pays_for"
                    " FROM economic_rules WHERE key = $1 AND pricing_version = $2"
                    " AND (effective_until IS NULL OR effective_until > current_date)", key, pricing_version)


def economic_terms_for_funding(conn: Connection) -> dict:
    """Os termos que um acordo de FINANCIAMENTO recebe ao nascer: vêm do catálogo, nunca do cliente."""
    from ..services.monetization import pricing_version_name
    pv = pricing_version_name()
    plat = rule_for(conn, PLATFORM_RULE, pv)
    prop = rule_for(conn, PROPONENT_RULE, pv)
    if not plat:
        raise ApiError(409, "economic_rule_missing", f"Não há regra econômica {PLATFORM_RULE} para a versão de preços {pv}")
    return {"pricing_version": pv, "platform_fee_bps": plat["bps"], "fee_payer_role": plat["payer_role"], "fee_mode": "deducted",
            "proponent_participation_bps": prop["bps"] if prop else 0}


def mask_pix(key: str | None, kind: str | None) -> str | None:
    if not key:
        return None
    if kind in ("cpf", "cnpj", "phone"):
        return key[:3] + "•" * max(0, len(key) - 5) + key[-2:]
    if kind == "email":
        user, _, dom = key.partition("@")
        return (user[:2] + "•••@" + dom) if dom else "•••"
    return key[:8] + "•••"


# ------------------------------------------------------------------ chave PIX da parte
def set_party_pix(conn: Connection, *, agreement_id: str, party_id: str, org_id: str, user_id: str,
                  pix_key: str, pix_key_type: str) -> dict:
    """Só a própria parte informa a própria chave. O formato é conferido pelo banco (CHECK pix_key_shape)."""
    if pix_key_type not in PIX_TYPES:
        raise ApiError(422, "pix_type_invalid", "Tipo de chave PIX inválido", {"possiveis": list(PIX_TYPES)})
    key = pix_key.strip()
    if pix_key_type in ("cpf", "cnpj"):
        key = "".join(ch for ch in key if ch.isdigit())
    if pix_key_type == "phone" and not key.startswith("+"):
        key = "+55" + "".join(ch for ch in key if ch.isdigit())
    if pix_key_type == "email":
        key = key.lower()
    p = conn.one("SELECT id::text AS id, org_id::text AS org_id FROM signed_agreement_parties WHERE id = $1 AND agreement_id = $2",
                 party_id, agreement_id)
    if not p:
        raise ApiError(404, "not_found", "Parte não encontrada")
    if p["org_id"] != org_id:
        raise ApiError(403, "not_your_party", "Cada parte informa a própria chave PIX")
    conn.run("UPDATE signed_agreement_parties SET pix_key = $2, pix_key_type = $3, pix_key_set_by = $4, pix_key_set_at = now() WHERE id = $1",
             party_id, key, pix_key_type, user_id)
    return {"party_id": party_id, "pix_key_masked": mask_pix(key, pix_key_type), "pix_key_type": pix_key_type}


# ------------------------------------------------------------------ participação de autoria
def propose_participation(conn: Connection, *, project_id: str, org_id: str, actor_user_id: str, proponent_org_id: str,
                          proponent_user_id: str | None, idea_ref_type: str, idea_ref_id: str, authorship_type: str,
                          share_bps: int, contribution: str) -> dict:
    """A executora (dona do projeto) PROPÕE; o proponente aceita. Sem aceite não há elegibilidade."""
    if proponent_org_id == org_id:
        raise ApiError(422, "proponent_is_executor", "A participação de autoria é de outra organização ou pessoa, não da executora")
    if not conn.scalar("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", project_id, org_id):
        raise ApiError(404, "not_found", "Projeto não encontrado")
    if idea_ref_type == "solution":
        ok = conn.scalar("SELECT 1 FROM solutions WHERE id = $1", idea_ref_id)
    else:
        ok = conn.scalar("SELECT 1 FROM ideas WHERE id = $1", idea_ref_id)
    if not ok:
        raise ApiError(422, "idea_not_found", "A ideia referida não existe ou não é visível")
    if not conn.scalar("SELECT 1 FROM organizations WHERE id = $1 AND kind IN ('individual','osc','provider','company')", proponent_org_id):
        raise ApiError(422, "proponent_invalid", "Proponente precisa ser organização ou pessoa cadastrada")
    pid = conn.scalar(
        "INSERT INTO proponent_participations(project_id, org_id, proponent_org_id, proponent_user_id, idea_ref_type, idea_ref_id,"
        " authorship_type, share_bps, contribution, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id::text",
        project_id, org_id, proponent_org_id, proponent_user_id, idea_ref_type, idea_ref_id, authorship_type, share_bps,
        contribution, actor_user_id)
    from ..services.audit import ledger
    ledger(conn, project_id=project_id, org_id=org_id, actor=actor_user_id, entry_type="participation_proposed",
           ref_type="participation", ref_id=pid, payload={"proponent_org_id": proponent_org_id, "share_bps": share_bps,
                                                          "authorship_type": authorship_type})
    return {"id": pid, "status": "proposed"}


def participation(conn: Connection, participation_id: str) -> dict:
    p = conn.one("SELECT p.id::text AS id, p.project_id::text AS project_id, p.org_id::text AS org_id,"
                 " p.proponent_org_id::text AS proponent_org_id, p.proponent_user_id::text AS proponent_user_id, p.idea_ref_type,"
                 " p.idea_ref_id::text AS idea_ref_id, p.authorship_type, p.share_bps, p.contribution, p.status, p.accepted_at,"
                 " p.consolidated_at, p.validated_at, p.cancelled_reason, p.agreement_id::text AS agreement_id, p.created_at,"
                 " pr.title AS project_title, o.legal_name AS proponent_name, ex.legal_name AS executor_name,"
                 " coalesce(pr.visibility = 'published', false) AS project_published"
                 # LEFT JOIN de propósito: antes da publicação o projeto é invisível ao proponente (RLS), e a participação
                 # precisa continuar visível a ele — é ele quem aceita.
                 " FROM proponent_participations p LEFT JOIN projects pr ON pr.id = p.project_id"
                 " JOIN organizations o ON o.id = p.proponent_org_id JOIN organizations ex ON ex.id = p.org_id WHERE p.id = $1",
                 participation_id)
    if not p:
        raise ApiError(404, "not_found", "Participação não encontrada")
    return p


def accept_participation(conn: Connection, *, participation_id: str, org_id: str, user_id: str) -> dict:
    p = participation(conn, participation_id)
    if p["proponent_org_id"] != org_id:
        raise ApiError(403, "not_the_proponent", "Só o proponente aceita a própria participação")
    if p["status"] not in ("proposed", "under_review"):
        raise ApiError(409, "not_acceptable", f"Participação em '{p['status']}' não está aguardando aceite")
    conn.run("UPDATE proponent_participations SET status = 'accepted', accepted_by = $2 WHERE id = $1", participation_id, user_id)
    # projeto já publicado → consolidada no mesmo ato
    status = "accepted"
    if p["project_published"]:
        conn.run("UPDATE proponent_participations SET status = 'consolidated' WHERE id = $1", participation_id)
        status = "consolidated"
    # O razão do projeto é da executora: o lançamento é feito pela rota em contexto de sistema, com o ator real.
    return {"id": participation_id, "status": status, "project_id": p["project_id"], "org_id": p["org_id"]}


def consolidate_for_project(conn: Connection, *, project_id: str, actor_user_id: str | None) -> int:
    """Chamado quando o projeto é PUBLICADO: aceitas viram consolidadas."""
    rows = conn.query("SELECT id::text AS id, org_id::text AS org_id FROM proponent_participations"
                      " WHERE project_id = $1 AND status = 'accepted'", project_id)
    from ..services.audit import ledger
    for r in rows:
        conn.run("UPDATE proponent_participations SET status = 'consolidated' WHERE id = $1", r["id"])
        ledger(conn, project_id=project_id, org_id=r["org_id"], actor=actor_user_id, entry_type="participation_consolidated",
               ref_type="participation", ref_id=r["id"], payload={})
    return len(rows)


def cancel_participation(conn: Connection, *, participation_id: str, org_id: str, user_id: str, reason: str) -> dict:
    p = participation(conn, participation_id)
    if org_id not in (p["org_id"], p["proponent_org_id"]):
        raise ApiError(403, "forbidden", "Só a executora ou o proponente cancelam a participação")
    if p["status"] in ("paid", "cancelled"):
        raise ApiError(409, "not_cancellable", f"Participação '{p['status']}' não se cancela")
    conn.run("UPDATE proponent_participations SET status = 'cancelled', cancelled_reason = $2 WHERE id = $1", participation_id, reason)
    return {"id": participation_id, "status": "cancelled"}


def eligible_participations(conn: Connection, project_id: str) -> list[dict]:
    """Elegíveis a entrar na matriz: aceitas/consolidadas/elegíveis/acumuladas — nunca propostas ou canceladas."""
    return conn.query("SELECT id::text AS id, proponent_org_id::text AS proponent_org_id, share_bps, status, authorship_type"
                      " FROM proponent_participations WHERE project_id = $1"
                      " AND status IN ('consolidated','eligible','accrued','payable') ORDER BY created_at", project_id)


def mine(conn: Connection, org_id: str) -> list[dict]:
    return conn.query("SELECT p.id::text AS id, p.project_id::text AS project_id, pr.title AS project_title, p.org_id::text AS org_id,"
                      " ex.legal_name AS executor_name, p.proponent_org_id::text AS proponent_org_id, o.legal_name AS proponent_name,"
                      " p.authorship_type, p.share_bps, p.status, p.contribution, p.accepted_at, p.consolidated_at, p.created_at,"
                      " p.agreement_id::text AS agreement_id"
                      " FROM proponent_participations p LEFT JOIN projects pr ON pr.id = p.project_id"
                      " JOIN organizations o ON o.id = p.proponent_org_id JOIN organizations ex ON ex.id = p.org_id"
                      " WHERE p.org_id = $1 OR p.proponent_org_id = $1 ORDER BY p.created_at DESC", org_id)


# ------------------------------------------------------------------ ledger econômico
def economic_event(conn: Connection, *, kind: str, idempotency_key: str, amount_cents: int, org_id: str | None,
                   agreement_id: str | None = None, allocation_id: str | None = None, payout_id: str | None = None,
                   rule_key: str | None = None, pricing_version: str | None = None, bps: int | None = None,
                   base_cents: int | None = None, payer_org_id: str | None = None, recipient_org_id: str | None = None,
                   actor_user_id: str | None = None, payload: dict | None = None, reverses_seq: int | None = None) -> int | None:
    """Append-only e idempotente: a mesma chave nunca gera segundo evento (devolve None quando já existe)."""
    return conn.scalar(
        "INSERT INTO economic_events(kind, org_id, agreement_id, allocation_id, payout_id, rule_key, pricing_version, bps, base_cents,"
        " amount_cents, payer_org_id, recipient_org_id, reverses_seq, idempotency_key, payload, actor_user_id)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb,$16)"
        " ON CONFLICT (idempotency_key) DO NOTHING RETURNING seq",
        kind, org_id, agreement_id, allocation_id, payout_id, rule_key, pricing_version, bps, base_cents, int(amount_cents),
        payer_org_id, recipient_org_id, reverses_seq, idempotency_key, Json(payload or {}), actor_user_id)


# ------------------------------------------------------------------ instruções de repasse
def instruct_payouts(conn: Connection, *, agreement: dict, allocation_id: str, alloc: dict, parties: list[dict],
                     actor_user_id: str | None, platform_charge_id: str | None) -> list[dict]:
    """Uma instrução por linha. Contexto privilegiado (ativação). Idempotente pela UNIQUE da tabela."""
    from ..config import load_settings
    settings = load_settings()
    payer = alloc.get("fee_payer_org_id") or next((p["org_id"] for p in parties if p["role"] == "funder"), None)
    if not payer:
        return []
    out = []
    pix_by_org = {p["org_id"]: (p.get("pix_key"), p.get("pix_key_type")) for p in parties}
    for line in alloc["lines"]:
        if int(line["cents"]) <= 0:
            continue
        kind = line["kind"]
        recipient = line.get("to_org_id")
        if kind == "platform_fee":
            label = "Plataforma Impacto — infraestrutura e inteligência"
            pix, pix_t = getattr(settings, "platform_pix_key", None) or None, getattr(settings, "platform_pix_key_type", None) or None
            state = "instruction_created" if line.get("chargeable") else "awaiting_rule"
        else:
            label = conn.scalar("SELECT legal_name FROM organizations WHERE id = $1", recipient) or "Destinatário"
            pix, pix_t = pix_by_org.get(recipient, (None, None))
            state = "instruction_created"
        pid = conn.scalar(
            "INSERT INTO allocation_payouts(allocation_id, agreement_id, org_id, line_kind, payer_org_id, recipient_org_id, recipient_label,"
            " amount_cents, pix_key_snapshot, pix_key_type, state, platform_charge_id)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)"
            " ON CONFLICT (allocation_id, line_kind, recipient_org_id) DO NOTHING RETURNING id::text",
            allocation_id, agreement["id"], agreement["org_id"], kind, payer, recipient, label, int(line["cents"]), pix, pix_t, state,
            platform_charge_id if kind == "platform_fee" else None)
        if not pid:
            continue
        ek = {"project": "project_funds_instructed", "platform_fee": "platform_service_registered",
              "proponent": "proponent_participation_accrued", "third_party": "project_funds_instructed"}[kind]
        economic_event(conn, kind=ek, idempotency_key=f"{ek}:{allocation_id}:{kind}:{recipient or 'platform'}",
                       amount_cents=int(line["cents"]), org_id=agreement["org_id"], agreement_id=agreement["id"],
                       allocation_id=allocation_id, payout_id=pid, rule_key=line.get("rule_key"), pricing_version=alloc["pricing_version"],
                       bps=line.get("bps"), base_cents=alloc["gross_cents"], payer_org_id=payer, recipient_org_id=recipient,
                       actor_user_id=actor_user_id, payload={"basis": line.get("basis"), "chargeable": line.get("chargeable")})
        if kind == "platform_fee" and line.get("chargeable"):
            economic_event(conn, kind="platform_service_due", idempotency_key=f"platform_service_due:{allocation_id}",
                           amount_cents=int(line["cents"]), org_id=agreement["org_id"], agreement_id=agreement["id"],
                           allocation_id=allocation_id, payout_id=pid, rule_key=line.get("rule_key"), pricing_version=alloc["pricing_version"],
                           bps=line.get("bps"), base_cents=alloc["gross_cents"], payer_org_id=payer, recipient_org_id=None,
                           actor_user_id=actor_user_id, payload={"platform_charge_id": platform_charge_id})
        if kind == "proponent" and recipient:
            # consolidada → elegível (acordo em vigor com a parte) → acumulada (linha na matriz): dois passos, pelo grafo
            conn.run("UPDATE proponent_participations SET status = 'eligible', agreement_id = $2 WHERE proponent_org_id = $1"
                     " AND project_id = $3 AND status = 'consolidated'", recipient, agreement["id"], agreement["project_id"])
            conn.run("UPDATE proponent_participations SET status = 'accrued', agreement_id = $2 WHERE proponent_org_id = $1"
                     " AND project_id = $3 AND status = 'eligible'", recipient, agreement["id"], agreement["project_id"])
        if agreement.get("project_id"):
            from ..services.audit import ledger
            ledger(conn, project_id=agreement["project_id"], org_id=agreement["org_id"], actor=actor_user_id, entry_type="payout_instructed",
                   amount_cents=int(line["cents"]), ref_type="payout", ref_id=pid,
                   payload={"line": kind, "recipient_org_id": recipient, "state": state, "pix_informed": bool(pix)})
        out.append({"id": pid, "line_kind": kind, "state": state, "amount_cents": int(line["cents"])})
    return out


def payouts(conn: Connection, agreement_id: str, *, viewer_org_id: str | None) -> list[dict]:
    rows = conn.query("SELECT p.id::text AS id, p.allocation_id::text AS allocation_id, p.line_kind, p.payer_org_id::text AS payer_org_id,"
                      " p.recipient_org_id::text AS recipient_org_id, p.recipient_label, p.amount_cents, p.paid_cents, p.confirmed_cents,"
                      " p.state, p.pix_key_snapshot, p.pix_key_type, p.due_on, p.confirmed_at, p.reconciled_at, p.reconciliation_note,"
                      " p.platform_charge_id::text AS platform_charge_id, p.created_at, p.updated_at"
                      " FROM allocation_payouts p WHERE p.agreement_id = $1 ORDER BY CASE p.line_kind WHEN 'project' THEN 0"
                      " WHEN 'proponent' THEN 1 WHEN 'platform_fee' THEN 2 ELSE 3 END", agreement_id)
    for r in rows:
        full = viewer_org_id is not None and viewer_org_id in (r["payer_org_id"], r["recipient_org_id"])
        r["pix_key"] = r.pop("pix_key_snapshot") if full else None
        r["pix_key_masked"] = mask_pix(r["pix_key"] or None, r["pix_key_type"]) if r["pix_key"] else \
            (mask_pix(conn.scalar("SELECT pix_key_snapshot FROM allocation_payouts WHERE id = $1", r["id"]), r["pix_key_type"]))
        r["pix_informed"] = r["pix_key_masked"] is not None
        r["transfers"] = conn.query("SELECT id::text AS id, amount_cents, reference, paid_on, method, status, registered_by_org::text AS registered_by_org,"
                                    " confirmed_by_org::text AS confirmed_by_org, confirmed_at, rejection_reason, evidence_document_id::text AS evidence_document_id,"
                                    " created_at FROM payout_transfers WHERE payout_id = $1 ORDER BY created_at", r["id"])
        r["remaining_cents"] = max(0, int(r["amount_cents"]) - int(r["confirmed_cents"]))
    return rows


def _payout(conn: Connection, payout_id: str) -> dict:
    p = conn.one("SELECT p.id::text AS id, p.agreement_id::text AS agreement_id, p.allocation_id::text AS allocation_id, p.org_id::text AS org_id,"
                 " p.line_kind, p.payer_org_id::text AS payer_org_id, p.recipient_org_id::text AS recipient_org_id, p.amount_cents,"
                 " p.paid_cents, p.confirmed_cents, p.state, p.platform_charge_id::text AS platform_charge_id, a.project_id::text AS project_id"
                 " FROM allocation_payouts p JOIN signed_agreements a ON a.id = p.agreement_id WHERE p.id = $1", payout_id)
    if not p:
        raise ApiError(404, "not_found", "Instrução de repasse não encontrada")
    return p


def register_transfer(conn: Connection, *, payout_id: str, org_id: str, user_id: str, amount_cents: int, reference: str,
                      paid_on: Any, method: str, evidence_document_id: str | None) -> dict:
    """Quem PAGA registra que transferiu — a qualquer momento. Não confirma nada: confirma quem recebe."""
    p = _payout(conn, payout_id)
    if p["payer_org_id"] != org_id:
        raise ApiError(403, "not_the_payer", "Só quem paga registra a transferência")
    if p["state"] in ("cancelled", "refunded", "awaiting_rule"):
        raise ApiError(409, "payout_not_payable", f"Instrução em '{p['state']}' não recebe transferência"
                       + (": a linha da plataforma só é exigível com a regra comercial ativa" if p["state"] == "awaiting_rule" else ""))
    if amount_cents <= 0:
        raise ApiError(422, "amount_invalid", "Valor precisa ser positivo")
    dup = conn.one("SELECT id::text AS id, amount_cents FROM payout_transfers WHERE payout_id = $1 AND reference = $2", payout_id, reference)
    if dup:
        # idempotência: a mesma referência é a mesma transferência
        return {"id": dup["id"], "duplicate": True, "payout_state": p["state"]}
    if int(p["paid_cents"]) + amount_cents > int(p["amount_cents"]):
        raise ApiError(422, "exceeds_instruction", "A soma das transferências passaria do valor instruído",
                       {"instruido": p["amount_cents"], "registrado": p["paid_cents"], "enviado": amount_cents})
    tid = conn.scalar("INSERT INTO payout_transfers(payout_id, org_id, amount_cents, reference, paid_on, method, evidence_document_id,"
                      " registered_by_org, registered_by) VALUES ($1,$2,$3,$4,$5::date,$6,$7,$8,$9) RETURNING id::text",
                      payout_id, p["org_id"], amount_cents, reference, paid_on, method, evidence_document_id, org_id, user_id)
    conn.run("UPDATE allocation_payouts SET paid_cents = paid_cents + $2, state = CASE WHEN state IN ('instruction_created','failed','disputed')"
             " THEN 'payment_pending' ELSE state END WHERE id = $1", payout_id, amount_cents)
    pend = []
    if p["project_id"]:
        pend.append(dict(project_id=p["project_id"], org_id=p["org_id"], actor=user_id, entry_type="payout_registered",
                         amount_cents=amount_cents, ref_type="payout_transfer", ref_id=tid,
                         payload={"payout_id": payout_id, "line": p["line_kind"], "reference": reference, "actor_org_id": org_id}))
    return {"id": tid, "duplicate": False, "payout_state": "payment_pending", "recipient_org_id": p["recipient_org_id"],
            "agreement_id": p["agreement_id"], "_ledger": pend}


def confirm_transfer(conn: Connection, *, transfer_id: str, org_id: str | None, user_id: str, platform_staff: bool = False) -> dict:
    """Quem RECEBE confirma (a plataforma, para a própria linha). Quem paga nunca confirma o que pagou."""
    t = conn.one("SELECT t.id::text AS id, t.payout_id::text AS payout_id, t.amount_cents, t.status, t.registered_by_org::text AS registered_by_org"
                 " FROM payout_transfers t WHERE t.id = $1", transfer_id)
    if not t:
        raise ApiError(404, "not_found", "Transferência não encontrada")
    p = _payout(conn, t["payout_id"])
    if p["recipient_org_id"] is None:
        if not platform_staff:
            raise ApiError(403, "platform_line", "A linha da plataforma é confirmada pela equipe financeira da plataforma")
        recipient = None
    else:
        if org_id != p["recipient_org_id"]:
            raise ApiError(403, "not_the_recipient", "Só quem recebe confirma o recebimento")
        recipient = org_id
    if t["status"] != "registered":
        return {"id": transfer_id, "status": t["status"], "duplicate": True, "payout_state": p["state"], "agreement_id": p["agreement_id"],
                "payout_id": p["id"], "_ledger": []}
    conf_org = recipient or org_id   # linha da plataforma: a organização da equipe financeira (plataforma)
    if not conf_org:
        raise ApiError(403, "no_org", "Confirmação exige organização identificada")
    conn.run("UPDATE payout_transfers SET status = 'confirmed', confirmed_by = $2, confirmed_by_org = $3 WHERE id = $1",
             transfer_id, user_id, conf_org)
    novo = int(p["confirmed_cents"]) + int(t["amount_cents"])
    conn.run("UPDATE allocation_payouts SET confirmed_cents = $2 WHERE id = $1", t["payout_id"], novo)
    state = p["state"]
    if novo >= int(p["amount_cents"]):
        conn.run("UPDATE allocation_payouts SET state = 'confirmed' WHERE id = $1", t["payout_id"])
        state = "confirmed"
        ek = {"project": "project_funds_confirmed", "platform_fee": "platform_service_paid",
              "proponent": "proponent_participation_paid", "third_party": "project_funds_confirmed"}[p["line_kind"]]
        economic_event(conn, kind=ek, idempotency_key=f"{ek}:{p['id']}", amount_cents=int(p["amount_cents"]), org_id=p["org_id"],
                       agreement_id=p["agreement_id"], allocation_id=p["allocation_id"], payout_id=p["id"],
                       payer_org_id=p["payer_org_id"], recipient_org_id=p["recipient_org_id"], actor_user_id=user_id,
                       payload={"confirmed_by_org": recipient or "platform"})
        if p["line_kind"] == "proponent" and p["recipient_org_id"]:
            conn.run("UPDATE proponent_participations SET status = 'paid' WHERE agreement_id = $1 AND proponent_org_id = $2"
                     " AND status IN ('accrued','payable')", p["agreement_id"], p["recipient_org_id"])
        # A cobrança própria (platform_charges), quando existe, segue o grafo dela pelo caminho de pagamentos da
        # plataforma; o evento econômico acima é a fonte da receita reconhecida. Não se força estado aqui.
        from ..economics import value_ledger as VL
        VL.record(conn, event_type="payout.confirmed", org_id=p["org_id"], units=1, project_id=p["project_id"],
                  subject_type="payout", subject_id=p["id"], metrics={"line": p["line_kind"], "amount_cents": int(p["amount_cents"])})
    pend = []
    if p["project_id"]:
        pend.append(dict(project_id=p["project_id"], org_id=p["org_id"], actor=user_id, entry_type="payout_confirmed",
                         amount_cents=int(t["amount_cents"]), ref_type="payout_transfer", ref_id=transfer_id,
                         payload={"payout_id": p["id"], "line": p["line_kind"], "payout_state": state, "actor_org_id": recipient or "platform"}))
    return {"id": transfer_id, "status": "confirmed", "duplicate": False, "payout_state": state, "agreement_id": p["agreement_id"],
            "payout_id": p["id"], "payer_org_id": p["payer_org_id"], "owner_org_id": p["org_id"], "_ledger": pend}


def reject_transfer(conn: Connection, *, transfer_id: str, org_id: str | None, user_id: str, reason: str, platform_staff: bool = False) -> dict:
    t = conn.one("SELECT t.id::text AS id, t.payout_id::text AS payout_id, t.amount_cents, t.status FROM payout_transfers t WHERE t.id = $1", transfer_id)
    if not t:
        raise ApiError(404, "not_found", "Transferência não encontrada")
    p = _payout(conn, t["payout_id"])
    if p["recipient_org_id"] is None and not platform_staff:
        raise ApiError(403, "platform_line", "A linha da plataforma é tratada pela equipe financeira da plataforma")
    if p["recipient_org_id"] is not None and org_id != p["recipient_org_id"]:
        raise ApiError(403, "not_the_recipient", "Só quem recebe recusa uma transferência registrada")
    if t["status"] != "registered":
        raise ApiError(409, "already_decided", f"Transferência já '{t['status']}'")
    conn.run("UPDATE payout_transfers SET status = 'rejected', rejection_reason = $2 WHERE id = $1", transfer_id, reason)
    conn.run("UPDATE allocation_payouts SET paid_cents = greatest(0, paid_cents - $2), state = 'disputed' WHERE id = $1", t["payout_id"], int(t["amount_cents"]))
    return {"id": transfer_id, "status": "rejected", "payout_state": "disputed"}


def reconcile_payout(conn: Connection, *, payout_id: str, org_id: str | None, user_id: str, note: str, platform_staff: bool = False) -> dict:
    p = _payout(conn, payout_id)
    if p["recipient_org_id"] is None and not platform_staff:
        raise ApiError(403, "platform_line", "A linha da plataforma é conciliada pela equipe financeira da plataforma")
    if p["recipient_org_id"] is not None and org_id != p["recipient_org_id"] and not platform_staff:
        raise ApiError(403, "not_the_recipient", "Quem recebe (ou a equipe financeira) concilia")
    if p["state"] != "confirmed":
        raise ApiError(409, "not_confirmed", "Só repasse confirmado por quem recebe pode ser conciliado")
    conn.run("UPDATE allocation_payouts SET state = 'reconciled', reconciled_by = $2, reconciliation_note = $3 WHERE id = $1", payout_id, user_id, note)
    pend = []
    if p["project_id"]:
        pend.append(dict(project_id=p["project_id"], org_id=p["org_id"], actor=user_id, entry_type="payout_reconciled",
                         amount_cents=int(p["amount_cents"]), ref_type="payout", ref_id=payout_id, payload={"note": note[:200]}))
    return {"id": payout_id, "state": "reconciled", "_ledger": pend}


def cancel_payouts(conn: Connection, *, agreement_id: str, actor_user_id: str | None, reason: str) -> int:
    """Acordo cancelado/substituído: instruções abertas são canceladas e o que foi registrado econômico é estornado."""
    rows = conn.query("SELECT id::text AS id, state, line_kind, amount_cents, org_id::text AS org_id, allocation_id::text AS allocation_id,"
                      " payer_org_id::text AS payer_org_id, recipient_org_id::text AS recipient_org_id"
                      " FROM allocation_payouts WHERE agreement_id = $1 AND state IN ('awaiting_rule','instruction_created','payment_pending','failed','disputed')",
                      agreement_id)
    n = 0
    for r in rows:
        conn.run("UPDATE allocation_payouts SET state = 'cancelled' WHERE id = $1", r["id"])
        orig = conn.one("SELECT seq FROM economic_events WHERE payout_id = $1 AND kind IN ('platform_service_registered','proponent_participation_accrued',"
                        "'project_funds_instructed') ORDER BY seq LIMIT 1", r["id"])
        if orig:
            economic_event(conn, kind="reversal", idempotency_key=f"reversal:{orig['seq']}", amount_cents=-int(r["amount_cents"]),
                           org_id=r["org_id"], agreement_id=agreement_id, allocation_id=r["allocation_id"], payout_id=r["id"],
                           payer_org_id=r["payer_org_id"], recipient_org_id=r["recipient_org_id"], actor_user_id=actor_user_id,
                           payload={"reason": reason}, reverses_seq=orig["seq"])
        n += 1
    conn.run("UPDATE proponent_participations SET status = 'consolidated' WHERE agreement_id = $1 AND status IN ('accrued','eligible')", agreement_id)
    return n


# ------------------------------------------------------------------ quitação e reconhecimento
def _recognize(conn: Connection, *, org_id: str, kind: str, ref_type: str, ref_id: str, project_id: str | None,
               amount_cents: int | None, evidence: dict) -> bool:
    rid = conn.scalar("INSERT INTO recognitions(org_id, kind, ref_type, ref_id, project_id, amount_cents, evidence)"
                      " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb) ON CONFLICT (org_id, kind, ref_type, ref_id) DO NOTHING RETURNING id::text",
                      org_id, kind, ref_type, ref_id, project_id, amount_cents, Json(evidence))
    if rid and project_id:
        from ..services.audit import ledger
        ledger(conn, project_id=project_id, org_id=org_id, actor=None, entry_type="recognition_granted", amount_cents=amount_cents,
               ref_type="recognition", ref_id=rid, payload={"kind": kind, "ref_type": ref_type, "ref_id": ref_id})
    return bool(rid)


def settlement(conn: Connection, agreement_id: str) -> dict:
    """Estado de quitação derivado das instruções (a matriz é imutável; o estado vive nos repasses)."""
    rows = conn.query("SELECT line_kind, state, amount_cents, confirmed_cents FROM allocation_payouts WHERE agreement_id = $1", agreement_id)
    if not rows:
        return {"status": "not_instructed", "due": [], "pending": [], "confirmed": [], "not_due": []}
    due = [r for r in rows if r["state"] not in ("awaiting_rule", "cancelled")]
    confirmed = [r for r in due if r["state"] in ("confirmed", "reconciled")]
    pending = [r for r in due if r["state"] not in ("confirmed", "reconciled")]
    not_due = [r for r in rows if r["state"] == "awaiting_rule"]
    if due and not pending:
        status = "reconciled" if all(r["state"] == "reconciled" for r in due) else "confirmed"
    elif any(r["state"] == "payment_pending" for r in due):
        status = "payment_pending"
    else:
        status = "instructed"
    ms = conn.one("SELECT count(*) AS total, count(*) FILTER (WHERE status = 'accepted') AS accepted"
                  " FROM signed_agreement_milestones WHERE agreement_id = $1", agreement_id)
    return {"status": status, "due": due, "pending": pending, "confirmed": confirmed, "not_due": not_due,
            "deliveries_accepted": int(ms["accepted"]), "deliveries_total": int(ms["total"]),
            "complete": int(ms["total"]) > 0 and int(ms["accepted"]) == int(ms["total"]),
            "settled": bool(due) and not pending and int(ms["total"]) > 0 and int(ms["accepted"]) == int(ms["total"])}


def after_confirm(conn: Connection, *, payout_id: str, actor_user_id: str | None) -> bool:
    """Contexto PRIVILEGIADO, depois da confirmação: reconhecimento do proponente pago e tentativa de quitação."""
    p = _payout(conn, payout_id)
    if p["state"] in ("confirmed", "reconciled") and p["line_kind"] == "proponent" and p["recipient_org_id"]:
        _recognize(conn, org_id=p["recipient_org_id"], kind="participation_paid", ref_type="payout", ref_id=p["id"],
                   project_id=p["project_id"], amount_cents=int(p["amount_cents"]), evidence={"agreement_id": p["agreement_id"]})
    return settle_if_complete(conn, agreement_id=p["agreement_id"], actor_user_id=actor_user_id)


def settle_if_complete(conn: Connection, *, agreement_id: str, actor_user_id: str | None) -> bool:
    """Operação QUITADA = todas as entregas aceitas E todos os repasses devidos confirmados. Idempotente."""
    st = settlement(conn, agreement_id)
    if not st["settled"]:
        return False
    a = conn.one("SELECT id::text AS id, org_id::text AS org_id, project_id::text AS project_id, status, value_cents,"
                 " (SELECT org_id::text FROM signed_agreement_parties WHERE agreement_id = $1 AND role = 'funder' LIMIT 1) AS funder_org_id"
                 " FROM signed_agreements WHERE id = $1", agreement_id)
    seq = economic_event(conn, kind="operation_settled", idempotency_key=f"operation_settled:{agreement_id}", amount_cents=int(a["value_cents"] or 0),
                         org_id=a["org_id"], agreement_id=agreement_id, actor_user_id=actor_user_id,
                         payload={"deliveries": st["deliveries_total"], "payouts_confirmed": len(st["confirmed"])})
    if seq is None:
        return True   # já quitada antes
    if a["status"] == "active":
        conn.run("UPDATE signed_agreements SET status = 'completed' WHERE id = $1", agreement_id)
    conn.run("UPDATE proponent_participations SET status = 'validated', validated_at = now() WHERE agreement_id = $1 AND status = 'accrued'", agreement_id)
    conn.run("UPDATE proponent_participations SET status = 'payable' WHERE agreement_id = $1 AND status = 'validated'", agreement_id)
    _recognize(conn, org_id=a["org_id"], kind="operation_settled", ref_type="agreement", ref_id=agreement_id, project_id=a["project_id"],
               amount_cents=int(a["value_cents"] or 0), evidence={"deliveries": st["deliveries_total"], "payouts": len(st["confirmed"])})
    if a["funder_org_id"]:
        _recognize(conn, org_id=a["funder_org_id"], kind="funding_settled", ref_type="agreement", ref_id=agreement_id, project_id=a["project_id"],
                   amount_cents=int(a["value_cents"] or 0), evidence={"deliveries": st["deliveries_total"]})
    if a["project_id"]:
        from ..services.audit import ledger
        ledger(conn, project_id=a["project_id"], org_id=a["org_id"], actor=actor_user_id, entry_type="operation_settled",
               amount_cents=int(a["value_cents"] or 0), ref_type="agreement", ref_id=agreement_id,
               payload={"deliveries": st["deliveries_total"], "payouts_confirmed": len(st["confirmed"])})
        from ..economics import value_ledger as VL
        VL.record(conn, event_type="operation.settled", org_id=a["org_id"], units=1, project_id=a["project_id"],
                  subject_type="agreement", subject_id=agreement_id, metrics={"value_cents": int(a["value_cents"] or 0)})
    return True


def trajectory(conn: Connection, org_id: str) -> dict:
    """Contadores cumulativos de reconhecimento — o que vai para o perfil público."""
    rows = conn.query("SELECT kind, count(*) AS n, coalesce(sum(amount_cents), 0) AS cents, max(granted_at) AS last_at"
                      " FROM recognitions WHERE org_id = $1 GROUP BY kind", org_id)
    by = {r["kind"]: {"count": int(r["n"]), "amount_cents": int(r["cents"]), "last_at": r["last_at"]} for r in rows}
    return {"recognitions": by, "total": sum(v["count"] for v in by.values()),
            "note": "Reconhecimentos nascem só de entrega aceita, repasse confirmado por quem recebe e operação quitada. "
                    "Nunca de pagamento à plataforma, plano ou voucher."}


def explain_value(conn: Connection, agreement_id: str) -> dict:
    """'O que o IMPACTO fez nesta operação' — por registro, não por slogan."""
    a = conn.one("SELECT id::text AS id, project_id::text AS project_id, version, value_cents, activated_at FROM signed_agreements WHERE id = $1", agreement_id)
    if not a:
        raise ApiError(404, "not_found", "Acordo não encontrado")
    versions = conn.scalar("SELECT count(*) FROM agreement_versions WHERE agreement_id = $1", agreement_id) or 0
    obligations = conn.one("SELECT count(*) AS n, count(*) FILTER (WHERE status = 'done') AS done FROM agreement_obligations WHERE agreement_id = $1", agreement_id)
    ms = conn.one("SELECT count(*) AS n, count(*) FILTER (WHERE status = 'accepted') AS accepted, count(*) FILTER (WHERE status = 'rejected') AS rejected"
                  " FROM signed_agreement_milestones WHERE agreement_id = $1", agreement_id)
    alloc = conn.one("SELECT gross_cents, project_cents, platform_fee_cents, proponent_cents, allocation_hash FROM agreement_allocations"
                     " WHERE agreement_id = $1 ORDER BY computed_at DESC LIMIT 1", agreement_id)
    pay = conn.one("SELECT count(*) AS n, count(*) FILTER (WHERE state IN ('confirmed','reconciled')) AS confirmed,"
                   " count(*) FILTER (WHERE state = 'awaiting_rule') AS not_due FROM allocation_payouts WHERE agreement_id = $1", agreement_id)
    ledger_n = conn.scalar("SELECT count(*) FROM ledger_entries WHERE ref_id::text = $1 OR payload->>'agreement_id' = $1", agreement_id) or 0
    evid = conn.scalar("SELECT count(*) FROM evidences WHERE project_id = $1 AND status = 'accepted'", a["project_id"]) if a["project_id"] else 0
    items = [
        {"what": "Contrato virou regra", "evidence": f"{versions} versão(ões) congelada(s) com hash; {int(obligations['n'])} obrigação(ões) derivada(s), {int(obligations['done'])} cumprida(s)", "source": "agreement_versions, agreement_obligations"},
        {"what": "Entregas aceitas a quatro olhos", "evidence": f"{int(ms['accepted'])} aceita(s) de {int(ms['n'])}; {int(ms['rejected'])} recusada(s) com motivo", "source": "signed_agreement_milestones"},
        {"what": "Distribuição calculada na origem", "evidence": (f"bruto {_brl(alloc['gross_cents'])}: projeto {_brl(alloc['project_cents'])}, plataforma {_brl(alloc['platform_fee_cents'])}, autoria {_brl(alloc['proponent_cents'])}; hash {alloc['allocation_hash'][:12]}…" if alloc else "ainda não (acordo não vigente)"), "source": "agreement_allocations"},
        {"what": "Repasses instruídos e confirmados por quem recebe", "evidence": f"{int(pay['confirmed'])} confirmado(s) de {int(pay['n'])} instruído(s)" + (f"; {int(pay['not_due'])} não exigível(is) (regra desligada)" if int(pay["not_due"]) else ""), "source": "allocation_payouts, payout_transfers"},
        {"what": "Rastro encadeado", "evidence": f"{int(ledger_n)} lançamento(s) no razão do projeto ligados a este acordo", "source": "ledger_entries (ledger_verify)"},
        {"what": "Evidência aceita por outra parte", "evidence": f"{int(evid or 0)} evidência(s) aceita(s) no projeto", "source": "evidences"},
    ]
    return {"agreement_id": agreement_id, "items": items,
            "value_capture": {"operation_cents": int(a["value_cents"] or 0), "platform_layer_cents": int(alloc["platform_fee_cents"]) if alloc else 0,
                              "ratio_note": "Valor econômico criado ainda NÃO MEDIDO: as linhas de base do Value Ledger nascem sem número até alguém declarar com fonte, data e método."},
            "note": "Isto é o que está registrado, não o que a plataforma promete."}


def _brl(cents: int) -> str:
    inteiro, cent = divmod(int(cents or 0), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{cent:02d}"


def dump(obj: Any) -> str:
    return json.dumps(obj, default=str, ensure_ascii=False)
