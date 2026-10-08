"""CONTRATO COMO REGRA OPERACIONAL (v0.26.0) — o que acontece DEPOIS de todas as partes assinarem.

Até a v0.25.0 um acordo com todas as assinaturas só mudava de status para `active`. Ninguém derivava
nada dele: marcos sem valor, obrigações reconstruídas à mão, nenhuma matriz de distribuição, nenhuma
versão. Aqui o acordo vigente produz, em contexto privilegiado e numa única transação:

  * OBRIGAÇÕES — para cada marco: quem entrega e até quando; quem aceita e em quanto tempo (política
    de aceite DO ACORDO); quem paga quanto, quando o marco for aceito;
  * MATRIZ DE DISTRIBUIÇÃO — bruto, projeto, taxa da plataforma e terceiros, com a regra comercial e a
    versão de preço que a produziram, hash do acordo, e um retrato imutável (`agreement_allocations`);
  * COBRANÇA DA PLATAFORMA — só quando a regra comercial está ativa (carta legal verde + parecer). Sem
    isso a linha da taxa é registrada como NÃO cobrável, com o motivo escrito. A taxa nunca é descontada
    de dinheiro em trânsito: é instrução separada ao pagador (ADR-284), e a plataforma não custodia.

NÃO está aqui: mover dinheiro. O financiador paga o projeto pelo meio que as partes combinaram
(`commitments` → `payment_records`), e a taxa, quando cobrável, pelo caminho de cobrança da própria
plataforma (`platform_charges`). Os dois caminhos já existiam; este módulo só os liga ao contrato.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from typing import Any

from ..clock import today
from ..db.pq import Connection, Json
from ..http import ApiError

FEE_RULE_KEY = "contract.platform_service_fee"


def _brl(cents: int) -> str:
    inteiro, cent = divmod(int(cents), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{cent:02d}"


def _bps(valor: int, bps: int | None) -> int:
    return (valor * (bps or 0) + 5000) // 10000   # arredondamento comercial em centavos


def business_days(start: date, days: int) -> date:
    d, n = start, 0
    while n < days:
        d += timedelta(days=1)
        if d.weekday() < 5:
            n += 1
    return d


def acceptance_deadline(start: date, review_days: int, calendar_type: str) -> date:
    return business_days(start, review_days) if calendar_type == "business" else start + timedelta(days=review_days)


def _agreement(conn: Connection, agreement_id: str) -> dict:
    a = conn.one("SELECT a.id::text AS id, a.org_id::text AS org_id, a.project_id::text AS project_id, a.kind, a.title,"
                 " a.status, a.version, a.content_sha256, a.document_id::text AS document_id, a.value_cents,"
                 " a.platform_fee_bps, a.fee_payer_role, a.fee_mode, a.review_days, a.calendar_type, a.auto_accept,"
                 " a.dispute_days, a.effective_from, a.effective_to, a.supersedes_id::text AS supersedes_id"
                 " FROM signed_agreements a WHERE a.id = $1", agreement_id)
    if not a:
        raise ApiError(404, "not_found", "Acordo não encontrado")
    return a


def _parties(conn: Connection, agreement_id: str) -> list[dict]:
    return conn.query("SELECT org_id::text AS org_id, role, required, signed_at FROM signed_agreement_parties"
                      " WHERE agreement_id = $1 ORDER BY invited_at", agreement_id)


def _milestones(conn: Connection, agreement_id: str) -> list[dict]:
    return conn.query("SELECT id::text AS id, seq, title, due_on, amount_cents, status, org_id::text AS org_id"
                      " FROM signed_agreement_milestones WHERE agreement_id = $1 ORDER BY seq NULLS LAST, due_on NULLS LAST, created_at",
                      agreement_id)


# ------------------------------------------------------------------ matriz de distribuição
def fee_rule(conn: Connection) -> dict | None:
    return conn.one("SELECT key, active, legal_status, revenue_engine, pricing_mode FROM monetization_rules WHERE key = $1",
                    FEE_RULE_KEY)


def compute_allocation(conn: Connection, a: dict, parties: list[dict]) -> dict:
    """Só CALCULA (ADR-284). Devolve a matriz com cada linha e o motivo da taxa ser ou não cobrável."""
    gross = int(a["value_cents"] or 0)
    bps = a["platform_fee_bps"]
    fee = _bps(gross, bps) if bps else 0
    deducted = a["fee_mode"] == "deducted"
    project = gross - fee if deducted and fee else gross
    rule = fee_rule(conn)
    payer = next((p for p in parties if p["role"] == a["fee_payer_role"]), None) if a["fee_payer_role"] else None
    # Quem recebe o valor: a parte executora; sem uma, a organização dona do acordo (a OSC que executa).
    receiver = next((p for p in parties if p["role"] in ("contractor", "provider", "professional")), None) \
        or {"org_id": a["org_id"], "role": "owner"}
    if not bps:
        chargeable, reason = False, "o acordo não prevê taxa de serviço da plataforma"
    elif payer is None:
        chargeable, reason = False, "o acordo não diz qual parte paga a taxa (fee_payer_role)"
    elif rule is None or not rule["active"]:
        chargeable, reason = False, ("regra comercial contract.platform_service_fee inativa: aguarda parecer jurídico "
                                     "e contábil (carta legal) — a taxa fica registrada e NÃO é cobrada")
    else:
        chargeable, reason = True, "regra comercial ativa com carta legal validada; taxa instruída ao pagador em cobrança própria da plataforma"
    from ..services.monetization import pricing_version_name
    pricing = pricing_version_name()
    lines = [{"kind": "project", "to_org_id": receiver["org_id"], "role": receiver["role"],
              "cents": project, "basis": "valor contratado" + (" menos a taxa (modo deducted)" if deducted and fee else ""),
              "paid_by": "quem financia, diretamente ao executor (commitments → payment_records)"}]
    if bps:
        lines.append({"kind": "platform_fee", "to_org_id": None, "role": "platform", "cents": fee,
                      "basis": f"{bps / 100:.2f}% sobre {_brl(gross)} ({'descontada do valor' if deducted else 'adicional ao valor'})",
                      "paid_by": (payer["role"] if payer else "?") + " → plataforma, em cobrança separada; nunca descontada em trânsito",
                      "chargeable": chargeable, "reason": reason, "rule_key": FEE_RULE_KEY})
    material = "|".join([a["id"], str(a["version"]), a["content_sha256"], a["fee_mode"], str(gross), str(project), str(fee),
                         json.dumps(lines, sort_keys=True, ensure_ascii=False)])
    return {"gross_cents": gross, "project_cents": project, "platform_fee_cents": fee, "third_party_cents": 0,
            "fee_mode": a["fee_mode"], "fee_bps": bps, "fee_payer_org_id": payer["org_id"] if payer else None,
            "fee_rule_key": FEE_RULE_KEY if bps else None, "fee_chargeable": chargeable, "fee_reason": reason,
            "pricing_version": pricing, "lines": lines,
            "allocation_hash": hashlib.sha256(material.encode()).hexdigest(),
            "note": ("A plataforma calcula, instrui e concilia. Não custodia: cada linha é paga por quem paga, pelo meio "
                     "que as partes escolheram. GMV (valor contratado) ≠ receita da plataforma (só a taxa cobrável)."),
            "total_instructed_cents": project + (fee if not deducted else 0) + (fee if deducted else 0)}


def preview(conn: Connection, agreement_id: str) -> dict:
    a = _agreement(conn, agreement_id)
    return compute_allocation(conn, a, _parties(conn, agreement_id))


# ------------------------------------------------------------------ ativação: derivação
def activate(conn: Connection, *, agreement_id: str, actor_user_id: str | None) -> dict:
    """Contexto PRIVILEGIADO (chamado por `settle` quando a última parte assina). Idempotente."""
    a = _agreement(conn, agreement_id)
    if a["status"] != "active":
        raise ApiError(409, "not_active", "Só um acordo vigente deriva obrigações")
    if conn.scalar("SELECT 1 FROM agreement_allocations WHERE agreement_id = $1", agreement_id):
        return {"already": True}
    parties = _parties(conn, agreement_id)
    executor = next((p for p in parties if p["role"] in ("contractor", "provider", "professional")), None)
    funder = next((p for p in parties if p["role"] == "funder"), None)
    # quem entrega: no acordo de financiamento é o contratante (OSC); no de serviço, o prestador
    deliverer = (next((p for p in parties if p["role"] in ("provider", "professional")), None) if a["kind"] == "service"
                 else executor) or executor
    acceptor = funder or next((p for p in parties if p["org_id"] != (deliverer or {}).get("org_id")), None)
    n = 0
    for m in _milestones(conn, agreement_id):
        if deliverer:
            conn.run("INSERT INTO agreement_obligations(agreement_id, milestone_id, obligor_org_id, kind, title, due_on, amount_cents)"
                     " VALUES ($1,$2,$3,'deliver',$4,$5::date,NULL)", agreement_id, m["id"], deliverer["org_id"],
                     f"Entregar: {m['title']}", m["due_on"])
            n += 1
        if acceptor:
            prazo = acceptance_deadline(m["due_on"], a["review_days"], a["calendar_type"]) if m["due_on"] else None
            conn.run("INSERT INTO agreement_obligations(agreement_id, milestone_id, obligor_org_id, kind, title, due_on, amount_cents)"
                     " VALUES ($1,$2,$3,'accept',$4,$5::date,NULL)", agreement_id, m["id"], acceptor["org_id"],
                     f"Analisar e aceitar (ou recusar) em {a['review_days']} dias {'úteis' if a['calendar_type'] == 'business' else 'corridos'}: {m['title']}",
                     prazo)
            n += 1
            if m["amount_cents"]:
                conn.run("INSERT INTO agreement_obligations(agreement_id, milestone_id, obligor_org_id, kind, title, due_on, amount_cents)"
                         " VALUES ($1,$2,$3,'pay',$4,NULL,$5)", agreement_id, m["id"], acceptor["org_id"],
                         f"Pagar {_brl(m['amount_cents'])} após o aceite: {m['title']}", m["amount_cents"])
                n += 1
    alloc = compute_allocation(conn, a, parties)
    # A cobrança própria da plataforma nasce ANTES da alocação (que é imutável e já aponta para ela).
    charge_id = None
    if alloc["fee_chargeable"] and alloc["platform_fee_cents"] > 0 and alloc["fee_payer_org_id"]:
        from ..economics import payments as PC
        ch = PC.create(conn, org_id=alloc["fee_payer_org_id"], actor=actor_user_id, kind="operation", method="manual",
                       amount_cents=alloc["platform_fee_cents"], currency="BRL", provider="manual")
        charge_id = ch["id"]
    alloc_id = conn.scalar(
        "INSERT INTO agreement_allocations(agreement_id, version, content_sha256, gross_cents, project_cents, platform_fee_cents,"
        " third_party_cents, fee_mode, fee_bps, fee_payer_org_id, fee_rule_key, fee_chargeable, fee_reason, pricing_version,"
        " lines, allocation_hash, computed_by, platform_charge_id)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb,$16,$17,$18) RETURNING id::text",
        agreement_id, a["version"], a["content_sha256"], alloc["gross_cents"], alloc["project_cents"], alloc["platform_fee_cents"],
        alloc["third_party_cents"], alloc["fee_mode"], alloc["fee_bps"], alloc["fee_payer_org_id"], alloc["fee_rule_key"],
        alloc["fee_chargeable"], alloc["fee_reason"], alloc["pricing_version"], Json(alloc["lines"]), alloc["allocation_hash"],
        actor_user_id, charge_id)
    conn.run("UPDATE signed_agreements SET activated_at = now() WHERE id = $1 AND activated_at IS NULL", agreement_id)
    if a["project_id"]:
        from ..services.audit import ledger
        ledger(conn, project_id=a["project_id"], org_id=a["org_id"], actor=actor_user_id, entry_type="agreement_activated",
               amount_cents=alloc["gross_cents"], ref_type="agreement", ref_id=agreement_id,
               payload={"version": a["version"], "obligations": n})
        ledger(conn, project_id=a["project_id"], org_id=a["org_id"], actor=actor_user_id, entry_type="allocation_computed",
               amount_cents=alloc["project_cents"], ref_type="allocation", ref_id=alloc_id,
               payload={"gross_cents": alloc["gross_cents"], "platform_fee_cents": alloc["platform_fee_cents"],
                        "fee_chargeable": alloc["fee_chargeable"], "fee_mode": alloc["fee_mode"],
                        "allocation_hash": alloc["allocation_hash"]})
    return {"already": False, "obligations": n, "allocation_id": alloc_id, "platform_charge_id": charge_id, **alloc}


# ------------------------------------------------------------------ nova versão
def new_version(conn: Connection, *, agreement_id: str, org_id: str, actor_user_id: str, document_id: str,
                document_sha256: str, reason: str, changes: dict[str, Any]) -> dict:
    """Cria a versão N+1 em rascunho, com as partes (sem assinatura) e os marcos copiados; a anterior vira
    `superseded`. As assinaturas antigas continuam no histórico — e deixam de valer como aprovação."""
    old = _agreement(conn, agreement_id)
    if old["org_id"] != org_id:
        raise ApiError(403, "forbidden", "Só a organização dona do acordo abre nova versão")
    if old["status"] not in ("awaiting_signatures", "active"):
        raise ApiError(409, "not_versionable", "Rascunho se edita; acordo cancelado, concluído ou substituído não ganha versão nova")
    campos = {k: old[k] for k in ("kind", "title", "summary", "project_id", "effective_from", "effective_to", "value_cents",
                                  "platform_fee_bps", "fee_payer_role", "fee_mode", "review_days", "calendar_type",
                                  "auto_accept", "dispute_days") if k in old}
    campos.update({k: v for k, v in changes.items() if v is not None})
    novo = conn.scalar(
        "INSERT INTO signed_agreements(org_id, project_id, kind, title, summary, document_id, content_sha256, effective_from,"
        " effective_to, value_cents, created_by, version, supersedes_id, version_reason, platform_fee_bps, fee_payer_role,"
        " fee_mode, review_days, calendar_type, auto_accept, dispute_days)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::date,$9::date,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21) RETURNING id::text",
        org_id, campos.get("project_id"), old["kind"], campos["title"], campos.get("summary"), document_id, document_sha256,
        campos.get("effective_from"), campos.get("effective_to"), campos.get("value_cents"), actor_user_id, old["version"] + 1,
        agreement_id, reason, campos.get("platform_fee_bps"), campos.get("fee_payer_role"), campos.get("fee_mode"),
        campos.get("review_days"), campos.get("calendar_type"), campos.get("auto_accept"), campos.get("dispute_days"))
    for p in conn.query("SELECT org_id::text AS org_id, role, required, user_id::text AS user_id FROM signed_agreement_parties"
                        " WHERE agreement_id = $1", agreement_id):
        conn.run("INSERT INTO signed_agreement_parties(agreement_id, org_id, role, required, user_id) VALUES ($1,$2,$3,$4,$5)",
                 novo, p["org_id"], p["role"], p["required"], p["user_id"])
    for m in _milestones(conn, agreement_id):
        conn.run("INSERT INTO signed_agreement_milestones(agreement_id, org_id, title, due_on, seq, amount_cents, source)"
                 " VALUES ($1,$2,$3,$4::date,$5,$6,'manual')", novo, m["org_id"], m["title"], m["due_on"], m["seq"], m["amount_cents"])
    conn.run("UPDATE signed_agreements SET status = 'superseded', superseded_by_id = $2 WHERE id = $1", agreement_id, novo)
    conn.run("UPDATE agreement_obligations SET status = 'waived' WHERE agreement_id = $1 AND status = 'open'", agreement_id)
    return {"id": novo, "version": old["version"] + 1, "supersedes_id": agreement_id, "status": "draft",
            "note": "As assinaturas da versão anterior continuam no histórico, mas não aprovam esta versão: todas as partes assinam de novo."}


def record_version(conn: Connection, *, agreement_id: str, actor_user_id: str | None, reason: str | None = None) -> None:
    """Fotografa os termos ao PUBLICAR (hash + termos + marcos + partes), append-only."""
    a = _agreement(conn, agreement_id)
    lineage = agreement_id
    while True:
        sup = conn.scalar("SELECT supersedes_id::text FROM signed_agreements WHERE id = $1", lineage)
        if not sup:
            break
        lineage = sup
    termos = {k: (a[k].isoformat() if isinstance(a[k], date) else a[k]) for k in
              ("kind", "title", "value_cents", "platform_fee_bps", "fee_payer_role", "fee_mode", "review_days",
               "calendar_type", "auto_accept", "dispute_days", "effective_from", "effective_to")}
    termos["parties"] = _parties(conn, agreement_id)
    termos["milestones"] = [{**m, "due_on": m["due_on"].isoformat() if m["due_on"] else None} for m in _milestones(conn, agreement_id)]
    conn.run("INSERT INTO agreement_versions(agreement_id, lineage_id, version, content_sha256, document_id, terms, reason, created_by)"
             " VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8) ON CONFLICT (lineage_id, version) DO NOTHING",
             agreement_id, lineage, a["version"], a["content_sha256"], a["document_id"],
             Json(json.loads(json.dumps(termos, default=str))), reason, actor_user_id)


# ------------------------------------------------------------------ marcos: entrega e aceite
def report_milestone(conn: Connection, *, agreement_id: str, milestone_id: str, org_id: str, user_id: str,
                     status: str, document_id: str | None, note: str | None) -> dict:
    """Entrega (quem executa) ou aceite/recusa (a outra parte). O gatilho confere o grafo e os quatro olhos."""
    m = conn.one("SELECT id::text AS id, status, reported_by::text AS reported_by, agreement_id::text AS agreement_id"
                 " FROM signed_agreement_milestones WHERE id = $1 AND agreement_id = $2", milestone_id, agreement_id)
    if not m:
        raise ApiError(404, "not_found", "Entrega não encontrada")
    if status in ("accepted", "rejected"):
        if status == "rejected" and not note:
            raise ApiError(422, "reason_required", "Recusar uma entrega exige o motivo")
        conn.run("UPDATE signed_agreement_milestones SET status = $2, note = coalesce($3, note), accepted_by = $4,"
                 " accepted_by_org = $5, rejection_reason = CASE WHEN $2 = 'rejected' THEN $3 ELSE rejection_reason END WHERE id = $1",
                 m["id"], status, note, user_id, org_id)
        conn.run("UPDATE agreement_obligations SET status = 'done', done_at = now() WHERE milestone_id = $1 AND kind = 'accept' AND status = 'open'", m["id"])
        if status == "accepted":
            # a obrigação de pagar fica ABERTA com prazo: nasce agora, vence pela política do acordo
            a = _agreement(conn, agreement_id)
            prazo = acceptance_deadline(today(), a["review_days"], a["calendar_type"])
            conn.run("UPDATE agreement_obligations SET due_on = $2 WHERE milestone_id = $1 AND kind = 'pay' AND status = 'open' AND due_on IS NULL",
                     m["id"], prazo)
    else:
        conn.run("UPDATE signed_agreement_milestones SET status = $2, document_id = coalesce($3, document_id), note = coalesce($4, note),"
                 " reported_by = $5, reported_at = now() WHERE id = $1", m["id"], status, document_id, note, user_id)
        if status == "delivered":
            a = _agreement(conn, agreement_id)
            prazo = acceptance_deadline(today(), a["review_days"], a["calendar_type"])
            conn.run("UPDATE signed_agreement_milestones SET acceptance_due_on = $2 WHERE id = $1", m["id"], prazo)
            conn.run("UPDATE agreement_obligations SET status = 'done', done_at = now() WHERE milestone_id = $1 AND kind = 'deliver' AND status = 'open'", m["id"])
            conn.run("UPDATE agreement_obligations SET due_on = $2 WHERE milestone_id = $1 AND kind = 'accept' AND status = 'open'", m["id"], prazo)
    return {"id": m["id"], "status": status}


def obligations(conn: Connection, agreement_id: str) -> list[dict]:
    return conn.query("SELECT o.id::text AS id, o.milestone_id::text AS milestone_id, o.obligor_org_id::text AS obligor_org_id,"
                      " org.legal_name AS obligor_name, o.kind, o.title, o.due_on, o.amount_cents, o.status, o.done_at, o.derived_from,"
                      " (o.status = 'open' AND o.due_on IS NOT NULL AND o.due_on < current_date) AS overdue"
                      " FROM agreement_obligations o JOIN organizations org ON org.id = o.obligor_org_id"
                      " WHERE o.agreement_id = $1 ORDER BY o.due_on NULLS LAST, o.created_at", agreement_id)


def allocation(conn: Connection, agreement_id: str) -> dict | None:
    return conn.one("SELECT id::text AS id, version, gross_cents, project_cents, platform_fee_cents, third_party_cents, fee_mode,"
                    " fee_bps, fee_payer_org_id::text AS fee_payer_org_id, fee_rule_key, fee_chargeable, fee_reason, pricing_version,"
                    " platform_charge_id::text AS platform_charge_id, lines, allocation_hash, computed_at"
                    " FROM agreement_allocations WHERE agreement_id = $1 ORDER BY computed_at DESC LIMIT 1", agreement_id)


def pending_for(conn: Connection, org_id: str, *, limit: int = 50) -> list[dict]:
    """O que ESPERA DECISÃO desta organização em todos os seus acordos — base da torre de controle."""
    return conn.query("SELECT o.id::text AS id, o.agreement_id::text AS agreement_id, a.title AS agreement_title, o.kind, o.title,"
                      " o.due_on, o.amount_cents, (o.due_on IS NOT NULL AND o.due_on < current_date) AS overdue"
                      " FROM agreement_obligations o JOIN signed_agreements a ON a.id = o.agreement_id"
                      " WHERE o.obligor_org_id = $1 AND o.status = 'open' AND a.status = 'active'"
                      " ORDER BY o.due_on NULLS LAST LIMIT $2", org_id, limit)
