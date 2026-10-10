"""Conciliação financeira com fila de exceções — v0.34.0 (ADR-383).

Confronta três fontes: o que o PROVEDOR diz (snapshot das cobranças que ele conhece, com estado, valor e tarifa), o que o
SISTEMA registrou (doações e eventos verificados) e o RAZÃO (lançamentos). Cada divergência vira uma exceção tipada, com
prioridade, responsável e histórico; reexecutar não duplica (índice único por fato aberto). "Webhook recebido" NÃO é
conciliação: só a doação cujo evento assinado bate com o snapshot do provedor em valor e estado vira `reconciled`.

No sandbox, o snapshot vem do próprio adaptador (`SandboxProvider.snapshot`), que lê os eventos assinados e aplicados —
é o que o sandbox "sabe". Um provedor real implementa `snapshot(campaign)` consultando a API dele.

v0.35.0 (auditoria, PAY-07): a execução registra a FONTE do snapshot. Os eventos do próprio sistema só servem ao SANDBOX;
provedor real sem extrato/API é recusado (409) em vez de "conciliar" contra si mesmo. O extrato manual (lista digitada
por uma pessoa) não concilia sozinho: abre as exceções e fica aguardando a aprovação de OUTRA pessoa (quatro olhos,
conferido pelo banco), que reexecuta com o mesmo extrato (o hash prova que é o mesmo).
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from ..db.pq import Connection
from ..http import ApiError, not_found, unprocessable
from .donations import apply_bps

PRIORITY = {"provider_only": "high", "system_only": "high", "amount_mismatch": "high", "reversal_missing": "high",
            "duplicate_entry": "high", "fee_mismatch": "medium", "fee_miscalculated": "medium", "settlement_partial": "medium",
            "unreconciled_overdue": "low", "settlement_failed": "high", "event_processing_failed": "high"}


def sandbox_snapshot(c: Connection, campaign_id: str) -> list[dict]:
    """O que o sandbox 'sabe': uma linha por cobrança, derivada dos eventos ASSINADOS e aplicados."""
    rows = c.query(
        "SELECT d.provider_charge_id AS charge_id, d.amount_cents + d.cover_costs_cents AS amount_cents, d.provider_fee_cents AS fee_cents,"
        " bool_or(e.event_type IN ('payment.confirmed','PAYMENT_RECEIVED','PAYMENT_CONFIRMED','charge.paid')) AS confirmed,"
        " bool_or(e.event_type IN ('payment.refunded','PAYMENT_REFUNDED','charge.refunded','payment.chargeback','PAYMENT_CHARGEBACK_REQUESTED')) AS reversed,"
        " bool_or(e.event_type IN ('payment.settled','PAYMENT_RECEIVED')) AS settled"
        " FROM donations d JOIN payment_provider_events e ON e.donation_id = d.id AND e.signature_verified AND e.processing_status = 'applied'"
        " WHERE d.campaign_id = $1 GROUP BY d.id", campaign_id)
    return [dict(r) for r in rows]


def _open(c: Connection, *, run_id: str | None, kind: str, campaign_id: str | None, org_id: str | None, donation_id: str | None = None,
          obligation_id: str | None = None, provider: str | None = None, provider_ref: str | None = None,
          expected: int | None = None, observed: int | None = None, detail: str = "") -> bool:
    try:
        c.run("SAVEPOINT recon_open")
        c.run("INSERT INTO reconciliation_exceptions(kind, campaign_id, org_id, donation_id, obligation_id, provider, provider_ref, expected_cents,"
              " observed_cents, priority, detail, run_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)",
              kind, campaign_id, org_id, donation_id, obligation_id, provider, provider_ref, expected, observed, PRIORITY[kind], detail[:2000], run_id)
        c.run("RELEASE SAVEPOINT recon_open")
        return True
    except Exception as exc:  # noqa: BLE001 — a unicidade é o comportamento desejado: fato aberto não duplica
        c.run("ROLLBACK TO SAVEPOINT recon_open")
        if "ux_recon_open_fact" in str(exc):
            return False
        raise


def open_from_event(c: Connection, *, kind: str, campaign_id: str | None, org_id: str | None, donation_id: str | None,
                    provider: str | None, provider_ref: str | None, expected: int | None, observed: int | None, detail: str) -> bool:
    """Exceção aberta por um EVENTO (liquidação parcial/falha, evento que falhou ao aplicar), fora de uma execução de
    conciliação. Usa a mesma unicidade por fato aberto: o mesmo fato não vira duas linhas."""
    return _open(c, run_id=None, kind=kind, campaign_id=campaign_id, org_id=org_id, donation_id=donation_id, provider=provider,
                 provider_ref=provider_ref, expected=expected, observed=observed, detail=detail)


def run_periodic(c: Connection, *, days: int = 7) -> dict:
    """Rotina: concilia toda campanha com doação movimentada nos últimos `days` dias (no sandbox, contra os eventos
    assinados). Uma campanha com erro não impede as outras."""
    # só o sandbox concilia sozinho (contra os eventos assinados); provedor real espera extrato (PAY-07)
    camps = c.query("SELECT DISTINCT campaign_id::text AS id FROM donations WHERE updated_at > now() - make_interval(days => $1)"
                    " AND provider = 'sandbox'", days)
    runs = []
    for row in camps:
        c.run("SAVEPOINT recon_periodic")
        try:
            runs.append(run_for_campaign(c, campaign_id=row["id"], run_by=None))
            c.run("RELEASE SAVEPOINT recon_periodic")
        except Exception:  # noqa: BLE001 — registrado pela rotina; a próxima execução tenta de novo
            c.run("ROLLBACK TO SAVEPOINT recon_periodic")
    return {"campaigns": len(camps), "opened": sum(r["opened"] for r in runs), "reconciled": sum(r["reconciled"] for r in runs)}


def snapshot_digest(snapshot: list[dict]) -> str:
    return hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def run_for_campaign(c: Connection, *, campaign_id: str, provider_snapshot: list[dict] | None = None, run_by: str | None = None,
                     overdue_hours: int = 72, source: str | None = None, mark_reconciled: bool = True, status: str = "done") -> dict:
    camp = c.one("SELECT id::text AS id, beneficiary_org_id::text AS org_id FROM campaigns WHERE id = $1", campaign_id)
    if not camp:
        raise not_found("Campanha")
    provider = c.scalar("SELECT provider FROM donations WHERE campaign_id = $1 ORDER BY created_at LIMIT 1", campaign_id) or "sandbox"
    if provider_snapshot is None:
        if provider != "sandbox":
            raise ApiError(409, "provider_statement_required",
                           "Provedor real: a conciliação exige o extrato ou a consulta à API do provedor — os eventos do próprio "
                           "sistema não provam que o dinheiro chegou")
        snapshot, source = sandbox_snapshot(c, campaign_id), "sandbox_signed_events"
    else:
        snapshot, source = provider_snapshot, (source or "manual_statement")
    digest = snapshot_digest(snapshot) if source != "sandbox_signed_events" else None
    by_ref = {s["charge_id"]: s for s in snapshot}
    run_id = str(uuid.uuid4())
    c.run("INSERT INTO reconciliation_runs(id, scope, provider, run_by, status, snapshot_source, snapshot, snapshot_sha256)"
          " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8)", run_id, f"campaign:{campaign_id}", provider, run_by, status, source,
          json.dumps(snapshot) if source == "manual_statement" else None, digest)
    checked = opened = reconciled = 0
    donations = c.query("SELECT id::text AS id, provider_charge_id, status, amount_cents + cover_costs_cents AS total, provider_fee_cents,"
                        " platform_fee_cents, refunded_cents, created_at FROM donations WHERE campaign_id = $1", campaign_id)
    seen = set()
    for d in donations:
        checked += 1
        ref = d["provider_charge_id"]
        seen.add(ref)
        s = by_ref.get(ref)
        if d["status"] in ("confirmed", "reconciled", "partially_refunded"):
            if not s or not s.get("confirmed"):
                opened += _open(c, run_id=run_id, kind="system_only", campaign_id=campaign_id, org_id=camp["org_id"], donation_id=d["id"],
                                provider=provider, provider_ref=ref, expected=int(d["total"]), observed=None,
                                detail="doação confirmada no sistema sem confirmação no snapshot do provedor")
                continue
            if int(s.get("amount_cents") or 0) != int(d["total"]):
                opened += _open(c, run_id=run_id, kind="amount_mismatch", campaign_id=campaign_id, org_id=camp["org_id"], donation_id=d["id"],
                                provider=provider, provider_ref=ref, expected=int(d["total"]), observed=int(s.get("amount_cents") or 0),
                                detail="valor no provedor diferente do registrado")
                continue
            if s.get("fee_cents") is not None and int(s["fee_cents"]) != int(d["provider_fee_cents"]):
                opened += _open(c, run_id=run_id, kind="fee_mismatch", campaign_id=campaign_id, org_id=camp["org_id"], donation_id=d["id"],
                                provider=provider, provider_ref=ref, expected=int(d["provider_fee_cents"]), observed=int(s["fee_cents"]),
                                detail="tarifa do provedor diferente da tabela congelada")
            if s.get("reversed") and not c.scalar("SELECT 1 FROM donation_ledger_entries WHERE donation_id = $1 AND account IN ('refund','chargeback') LIMIT 1", d["id"]):
                opened += _open(c, run_id=run_id, kind="reversal_missing", campaign_id=campaign_id, org_id=camp["org_id"], donation_id=d["id"],
                                provider=provider, provider_ref=ref, detail="provedor estornou; razão sem reversão")
                continue
            dup = c.scalar("SELECT count(DISTINCT txn_id) FROM donation_ledger_entries WHERE donation_id = $1 AND account = 'donor_payment' AND side = 'C' AND reversal_of IS NULL", d["id"])
            if int(dup or 0) > 1:
                opened += _open(c, run_id=run_id, kind="duplicate_entry", campaign_id=campaign_id, org_id=camp["org_id"], donation_id=d["id"],
                                provider=provider, provider_ref=ref, observed=int(dup), expected=1, detail="mais de uma confirmação lançada no razão")
                continue
            if d["status"] == "confirmed":
                if mark_reconciled:
                    c.run("UPDATE donations SET status = 'reconciled' WHERE id = $1", d["id"])
                reconciled += 1
        elif d["status"] == "awaiting_payment" and d["created_at"] < datetime.now(UTC) - timedelta(hours=overdue_hours):
            opened += _open(c, run_id=run_id, kind="unreconciled_overdue", campaign_id=campaign_id, org_id=camp["org_id"], donation_id=d["id"],
                            provider=provider, provider_ref=ref, detail=f"aguardando pagamento há mais de {overdue_hours} h sem evento")
    for ref, s in by_ref.items():
        if ref not in seen:
            opened += _open(c, run_id=run_id, kind="provider_only", campaign_id=campaign_id, org_id=camp["org_id"], provider=provider, provider_ref=ref,
                            observed=int(s.get("amount_cents") or 0), detail="cobrança existe no provedor e não no sistema")
    # obrigações: valor ≠ regra congelada × base
    for o in c.query("SELECT o.id::text AS id, o.basis_cents, o.amount_cents, v.bps, v.rounding, v.fixed_cents FROM remuneration_obligations o"
                     " JOIN fee_rule_versions v ON v.id = o.rule_version_id WHERE o.campaign_id = $1", campaign_id):
        expected = apply_bps(int(o["basis_cents"]), int(o["bps"]), o["rounding"]) + int(o["fixed_cents"])
        if expected != int(o["amount_cents"]):
            opened += _open(c, run_id=run_id, kind="fee_miscalculated", campaign_id=campaign_id, org_id=camp["org_id"], obligation_id=o["id"],
                            expected=expected, observed=int(o["amount_cents"]), detail="obrigação com valor diferente da regra congelada")
    summary = {"checked": checked, "opened": opened, "reconciled": reconciled if mark_reconciled else 0, "snapshot_size": len(snapshot),
               "snapshot_source": source, "independent_source": source != "sandbox_signed_events",
               **({} if mark_reconciled else {"would_reconcile": reconciled, "awaiting_approval": True})}
    c.run("UPDATE reconciliation_runs SET finished_at = now(), checked = $2, opened = $3, reconciled = $4, summary = $5::jsonb WHERE id = $1",
          run_id, checked, opened, summary["reconciled"], json.dumps(summary))
    return {"run_id": run_id, **summary, "at": datetime.now(UTC).isoformat()}


def propose_manual_run(c: Connection, *, campaign_id: str, snapshot: list[dict], run_by: str) -> dict:
    """Extrato digitado por uma pessoa: abre as exceções, mas NÃO concilia — fica aguardando outra pessoa (PAY-07)."""
    return run_for_campaign(c, campaign_id=campaign_id, provider_snapshot=snapshot, run_by=run_by, source="manual_statement",
                            mark_reconciled=False, status="awaiting_approval")


def approve_manual_run(c: Connection, *, run_id: str, approver: str) -> dict:
    """A segunda pessoa aprova o extrato manual: reexecuta com o MESMO extrato (conferido pelo hash) e então concilia."""
    run = c.one("SELECT id::text AS id, scope, run_by::text AS run_by, status, snapshot, snapshot_sha256 FROM reconciliation_runs"
                " WHERE id = $1 FOR UPDATE", run_id)
    if not run or not str(run["scope"]).startswith("campaign:"):
        raise not_found("Execução de conciliação")
    if run["status"] != "awaiting_approval":
        raise ApiError(409, "not_awaiting_approval", "Esta execução não está aguardando aprovação")
    if run["run_by"] == approver:
        raise ApiError(403, "four_eyes", "Quem enviou o extrato não pode aprová-lo: é preciso outra pessoa da equipe")
    snapshot = run["snapshot"] if isinstance(run["snapshot"], list) else json.loads(run["snapshot"] or "[]")
    if snapshot_digest(snapshot) != run["snapshot_sha256"]:
        raise ApiError(409, "snapshot_tampered", "O extrato guardado não confere com o hash registrado")
    out = run_for_campaign(c, campaign_id=run["scope"].split(":", 1)[1], provider_snapshot=snapshot, run_by=approver,
                           source="manual_statement", mark_reconciled=True)
    c.run("UPDATE reconciliation_runs SET status = 'approved', approved_by = $2, approved_at = now() WHERE id = $1", run_id, approver)
    return out | {"approved_run": run_id}


def list_exceptions(c: Connection, *, status: str | None = None, org_id: str | None = None) -> list[dict]:
    where, args = [], []
    if status:
        args.append(status)
        where.append(f"e.status = ${len(args)}")
    if org_id:
        args.append(org_id)
        where.append(f"e.org_id = ${len(args)}")
    sql = ("SELECT e.id::text AS id, e.kind, e.priority, e.status, e.campaign_id::text AS campaign_id, e.donation_id::text AS donation_id,"
           " e.obligation_id::text AS obligation_id, e.provider, e.provider_ref, e.expected_cents, e.observed_cents, e.assigned_to::text AS assigned_to,"
           " e.detail, e.resolution_note, e.created_at, e.resolved_at, c.title AS campaign_title FROM reconciliation_exceptions e"
           " LEFT JOIN campaigns c ON c.id = e.campaign_id")
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY CASE e.priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, e.created_at LIMIT 500"
    return c.query(sql, *args)


def assign(c: Connection, *, exception_id: str, user_id: str) -> dict:
    if not c.run("UPDATE reconciliation_exceptions SET status = 'assigned', assigned_to = $2 WHERE id = $1 AND status IN ('open','assigned')", exception_id, user_id):
        raise not_found("Exceção")
    return {"status": "assigned"}


def resolve(c: Connection, *, exception_id: str, user_id: str, outcome: str, note: str) -> dict:
    if outcome not in ("resolved", "dismissed"):
        raise unprocessable("desfecho desconhecido", code="outcome")
    if len(note or "") < 10:
        raise unprocessable("resolução exige justificativa", code="reason_required")
    if not c.run("UPDATE reconciliation_exceptions SET status = $2, resolution_note = $3, resolved_by = $4, resolved_at = now() WHERE id = $1 AND status IN ('open','assigned')",
                 exception_id, outcome, note[:2000], user_id):
        raise not_found("Exceção")
    return {"status": outcome}


def history(c: Connection, exception_id: str) -> list[dict]:
    return c.query("SELECT from_status, to_status, actor_id::text AS actor_id, note, created_at FROM reconciliation_exception_events WHERE exception_id = $1 ORDER BY id", exception_id)


__all__ = ["run_for_campaign", "propose_manual_run", "approve_manual_run", "list_exceptions", "assign", "resolve", "history",
           "sandbox_snapshot"]
