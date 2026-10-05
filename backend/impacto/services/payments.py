"""Pagamentos como REGISTROS conferidos (ADR-022: a plataforma não custodia nem processa dinheiro).

Máquina de estados (também imposta por trigger no banco):
  created → awaiting_confirmation → confirmed → partially_refunded → refunded ;  qualquer ponto confirmado/aguardando → disputed
Quem pode fazer o quê: o financiador declara e cancela; a OSC confirma/recusa o recebimento; ambos podem abrir disputa;
estorno: qualquer parte solicita, a OUTRA decide; conclusão do estorno é registrada pela OSC (quem devolve).
Reconciliação: linhas de extrato importadas (CSV) são pareadas com pagamentos confirmáveis por valor + data + referência.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, timedelta

from ..db.pq import Connection
from ..http import ApiError
from .audit import ledger

FUNDER_MOVES = {("created", "awaiting_confirmation"), ("created", "cancelled"), ("awaiting_confirmation", "cancelled")}
OSC_MOVES = {("awaiting_confirmation", "confirmed"), ("awaiting_confirmation", "failed")}
BOTH_MOVES = {("awaiting_confirmation", "disputed"), ("confirmed", "disputed")}
ACTIVE = ("created", "awaiting_confirmation", "confirmed", "partially_refunded", "disputed")


def allocated_cents(c: Connection, commitment_id: str) -> int:
    return int(c.scalar("SELECT coalesce(sum(amount_cents - refunded_cents), 0) FROM payment_records WHERE commitment_id = $1"
                        " AND state NOT IN ('failed','cancelled','refunded')", commitment_id))


def _event(c: Connection, pid: str, frm: str | None, to: str, ctx, note: str | None) -> None:
    c.run("INSERT INTO payment_events(payment_id, from_state, to_state, actor_org_id, actor_user_id, note) VALUES ($1,$2,$3,$4,$5,$6)",
          pid, frm, to, ctx.org_id, ctx.user_id, note)


def create(c: Connection, ctx, commitment_id: str, amount_cents: int, method: str, external_ref: str | None, model_id: str | None) -> str:
    cm = c.one("SELECT id::text AS id, project_id::text AS project_id, osc_org_id::text AS osc_org_id, funder_org_id::text AS funder_org_id,"
               " amount_cents, status FROM commitments WHERE id = $1 FOR UPDATE", commitment_id)
    if not cm or cm["funder_org_id"] != ctx.org_id:
        raise ApiError(404, "not_found", "Aporte não encontrado")
    if cm["status"] == "cancelled":
        raise ApiError(409, "commitment_cancelled", "Aporte cancelado")
    if allocated_cents(c, cm["id"]) + amount_cents > cm["amount_cents"]:
        raise ApiError(409, "exceeds_commitment", "A soma dos pagamentos ultrapassaria o valor do aporte")
    if model_id and not c.one("SELECT 1 FROM contribution_models WHERE id = $1 AND project_id = $2 AND status = 'approved'", model_id, cm["project_id"]):
        raise ApiError(409, "contribution_model_not_approved", "Modelo de contribuição inexistente ou sem aprovação jurídica")
    pid = c.scalar("INSERT INTO payment_records(commitment_id, project_id, funder_org_id, osc_org_id, contribution_model_id, amount_cents, method,"
                   " external_ref, created_by) VALUES ($1,$2,$3,$4,$5,$6::bigint,$7,$8,$9) RETURNING id::text",
                   cm["id"], cm["project_id"], cm["funder_org_id"], cm["osc_org_id"], model_id, amount_cents, method, external_ref, ctx.user_id)
    _event(c, pid, None, "created", ctx, None)
    return pid


def move(c: Connection, ctx, payment_id: str, to: str, note: str | None) -> dict:
    p = c.one("SELECT id::text AS id, state, commitment_id::text AS commitment_id, project_id::text AS project_id, funder_org_id::text AS funder_org_id,"
              " osc_org_id::text AS osc_org_id, amount_cents FROM payment_records WHERE id = $1 FOR UPDATE", payment_id)
    if not p or ctx.org_id not in (p["funder_org_id"], p["osc_org_id"]):
        raise ApiError(404, "not_found", "Pagamento não encontrado")
    pair = (p["state"], to)
    is_funder, is_osc = ctx.org_id == p["funder_org_id"], ctx.org_id == p["osc_org_id"]
    allowed = (is_funder and pair in FUNDER_MOVES) or (is_osc and pair in OSC_MOVES) or pair in BOTH_MOVES
    if not allowed:
        raise ApiError(409, "invalid_transition", f"Transição não permitida para a sua organização: {p['state']} → {to}")
    if to in ("failed", "disputed") and not note:
        raise ApiError(422, "note_required", "Informe o motivo")
    c.run("UPDATE payment_records SET state = $2 WHERE id = $1", p["id"], to)
    _event(c, p["id"], p["state"], to, ctx, note)
    if to == "awaiting_confirmation":
        c.run("UPDATE commitments SET status = 'disbursed', disbursed_at = coalesce(disbursed_at, now()) WHERE id = $1 AND status = 'pledged'", p["commitment_id"])
        ledger(c, project_id=p["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="disbursement_reported", amount_cents=p["amount_cents"],
               ref_type="payment", ref_id=p["id"])
    elif to == "confirmed":
        ledger(c, project_id=p["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="disbursement_confirmed", amount_cents=p["amount_cents"],
               ref_type="payment", ref_id=p["id"])
        confirmed = int(c.scalar("SELECT coalesce(sum(amount_cents - refunded_cents), 0) FROM payment_records WHERE commitment_id = $1"
                                 " AND state IN ('confirmed','partially_refunded')", p["commitment_id"]))
        total = int(c.scalar("SELECT amount_cents FROM commitments WHERE id = $1", p["commitment_id"]))
        if confirmed >= total:
            c.run("UPDATE commitments SET status = 'confirmed', confirmed_at = now() WHERE id = $1 AND status IN ('pledged','disbursed')", p["commitment_id"])
    elif to == "disputed":
        ledger(c, project_id=p["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="payment_disputed", amount_cents=p["amount_cents"],
               ref_type="payment", ref_id=p["id"], payload={"note": note})
    other = p["osc_org_id"] if is_funder else p["funder_org_id"]
    c.scalar("SELECT app_notify($1, NULL, 'payment', $2, $3, $4)", other, "Pagamento atualizado", f"Novo estado: {to}", f"/projetos/{p['project_id']}")
    return {"id": p["id"], "state": to}


def request_refund(c: Connection, ctx, payment_id: str, amount_cents: int, reason: str) -> str:
    p = c.one("SELECT id::text AS id, state, amount_cents, refunded_cents, funder_org_id::text AS funder_org_id, osc_org_id::text AS osc_org_id"
              " FROM payment_records WHERE id = $1 FOR UPDATE", payment_id)
    if not p or ctx.org_id not in (p["funder_org_id"], p["osc_org_id"]):
        raise ApiError(404, "not_found", "Pagamento não encontrado")
    if p["state"] not in ("confirmed", "partially_refunded", "disputed"):
        raise ApiError(409, "not_refundable", "Só é possível estornar pagamento confirmado")
    pending = int(c.scalar("SELECT coalesce(sum(amount_cents),0) FROM refunds WHERE payment_id = $1 AND status IN ('requested','approved')", p["id"]))
    if amount_cents + pending > p["amount_cents"] - p["refunded_cents"]:
        raise ApiError(409, "exceeds_refundable", "Valor acima do saldo estornável")
    rid = c.scalar("INSERT INTO refunds(payment_id, amount_cents, reason, requested_by_org) VALUES ($1,$2::bigint,$3,$4) RETURNING id::text",
                   p["id"], amount_cents, reason, ctx.org_id)
    other = p["osc_org_id"] if ctx.org_id == p["funder_org_id"] else p["funder_org_id"]
    c.scalar("SELECT app_notify($1, NULL, 'payment', 'Pedido de estorno', $2, '/aportes')", other, reason[:200])
    return rid


def decide_refund(c: Connection, ctx, refund_id: str, decision: str) -> dict:
    r = c.one("SELECT r.id::text AS id, r.payment_id::text AS payment_id, r.amount_cents, r.status, r.requested_by_org::text AS requested_by_org"
              " FROM refunds r WHERE r.id = $1 FOR UPDATE", refund_id)
    if not r:
        raise ApiError(404, "not_found", "Estorno não encontrado")
    p = c.one("SELECT id::text AS id, project_id::text AS project_id, state, amount_cents, refunded_cents, funder_org_id::text AS funder_org_id,"
              " osc_org_id::text AS osc_org_id FROM payment_records WHERE id = $1 FOR UPDATE", r["payment_id"])
    if not p or ctx.org_id not in (p["funder_org_id"], p["osc_org_id"]):
        raise ApiError(404, "not_found", "Estorno não encontrado")
    if r["requested_by_org"] == ctx.org_id and decision in ("approved", "rejected"):
        raise ApiError(403, "self_decision", "A outra parte deve decidir o estorno")
    valid = {("requested", "approved"), ("requested", "rejected"), ("approved", "completed")}
    if (r["status"], decision) not in valid:
        raise ApiError(409, "invalid_transition", f"{r['status']} → {decision} não permitido")
    if decision == "completed" and ctx.org_id != p["osc_org_id"]:
        raise ApiError(403, "forbidden", "A conclusão do estorno é registrada pela OSC (quem devolve)")
    c.run("UPDATE refunds SET status = $2, decided_by_org = $3, decided_by = $4, decided_at = now() WHERE id = $1", r["id"], decision, ctx.org_id, ctx.user_id)
    if decision == "completed":
        done = p["refunded_cents"] + r["amount_cents"]
        new_state = "refunded" if done >= p["amount_cents"] else "partially_refunded"
        c.run("UPDATE payment_records SET refunded_cents = $2::bigint WHERE id = $1", p["id"], done)
        if new_state != p["state"]:
            c.run("UPDATE payment_records SET state = $2 WHERE id = $1", p["id"], new_state)
            _event(c, p["id"], p["state"], new_state, ctx, f"estorno de {r['amount_cents']} centavos")
        ledger(c, project_id=p["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="refund_completed", amount_cents=r["amount_cents"],
               ref_type="payment", ref_id=p["id"])
    return {"id": r["id"], "status": decision}


# ------------------------------------------------------------------------------------------------ reconciliação
_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y")


def _parse_amount(s: str) -> int:
    s = s.strip().replace("R$", "").replace(" ", "")
    neg = s.startswith("-") or (s.startswith("(") and s.endswith(")"))
    s = s.strip("-()")
    if "," in s:                       # formato BR: 1.234,56
        s = s.replace(".", "").replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", s):
        raise ValueError(f"valor inválido: {s!r}")
    cents = round(float(s) * 100)
    return -cents if neg else cents


def _parse_date(s: str) -> date:
    for f in _DATE_FORMATS:
        try:
            return datetime.strptime(s.strip(), f).date()
        except ValueError:
            continue
    raise ValueError(f"data inválida: {s!r}")


def parse_statement(text: str) -> list[dict]:
    """CSV com cabeçalho: data, valor, descricao (opcional), referencia (opcional). Aceita ';' ou ','."""
    sample = text[:2000]
    delim = ";" if sample.count(";") >= sample.count(",") else ","
    rows = list(csv.DictReader(io.StringIO(text), delimiter=delim))
    if not rows:
        raise ValueError("extrato vazio")
    norm = [{(k or "").strip().lower(): (v or "") for k, v in r.items()} for r in rows]
    need = {"data", "valor"}
    if not need <= set(norm[0]):
        raise ValueError("cabeçalho esperado: data;valor;descricao;referencia")
    if len(norm) > 5000:
        raise ValueError("máximo de 5000 linhas por importação")
    out = []
    for i, r in enumerate(norm, 2):
        try:
            out.append({"booked_on": _parse_date(r["data"]), "amount_cents": _parse_amount(r["valor"]),
                        "description": r.get("descricao", "")[:300] or None, "reference": (r.get("referencia") or "")[:200] or None})
        except ValueError as e:
            raise ValueError(f"linha {i}: {e}") from e
    return out


def reconcile(c: Connection, org_id: str) -> dict:
    """Pareia linhas de crédito não pareadas com pagamentos da OSC (confirmados ou aguardando) — valor exato e janela de ±5 dias;
    referência igual vira 'matched'; sem referência/diferente, 'manual' (precisa de olho humano). Pagamento confirmado sem linha → mismatch."""
    pays = c.query("SELECT id::text AS id, amount_cents, external_ref, created_at::date AS d FROM payment_records WHERE osc_org_id = $1"
                   " AND state IN ('awaiting_confirmation','confirmed') AND reconciliation_status IN ('unreconciled','mismatch')", org_id)
    lines = c.query("SELECT id::text AS id, booked_on, amount_cents, reference FROM statement_lines WHERE org_id = $1 AND matched_payment_id IS NULL"
                    " AND amount_cents > 0 ORDER BY booked_on", org_id)
    used: set[str] = set()
    matched = manual = 0
    for p in pays:
        cand = [l for l in lines if l["id"] not in used and l["amount_cents"] == p["amount_cents"]
                and abs((l["booked_on"] - p["d"]).days) <= 5 + 0]
        exact = [l for l in cand if p["external_ref"] and l["reference"] and l["reference"].strip().lower() == p["external_ref"].strip().lower()]
        pick = exact[0] if exact else (cand[0] if len(cand) == 1 else None)
        if pick:
            used.add(pick["id"])
            status = "matched" if exact else "manual"
            c.run("UPDATE statement_lines SET matched_payment_id = $2 WHERE id = $1", pick["id"], p["id"])
            c.run("UPDATE payment_records SET reconciliation_status = $2 WHERE id = $1", p["id"], status)
            matched += status == "matched"
            manual += status == "manual"
    c.run("UPDATE payment_records SET reconciliation_status = 'mismatch' WHERE osc_org_id = $1 AND state = 'confirmed' AND reconciliation_status = 'unreconciled'"
          " AND created_at < now() - interval '7 days'", org_id)
    return {"matched": matched, "needs_manual_review": manual,
            "unmatched_lines": int(c.scalar("SELECT count(*) FROM statement_lines WHERE org_id = $1 AND matched_payment_id IS NULL AND amount_cents > 0", org_id)),
            "mismatched_payments": int(c.scalar("SELECT count(*) FROM payment_records WHERE osc_org_id = $1 AND reconciliation_status = 'mismatch'", org_id))}
