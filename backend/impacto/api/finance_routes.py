"""Modelos de contribuição (com portão jurídico), registros de pagamento (estados, estorno, disputa) e reconciliação de extrato.

ADR-022: a plataforma NÃO processa nem custodia dinheiro. Estes registros são declarados pelas partes e conferidos
(OSC confirma recebimento; extrato importado é pareado). Modelos de contribuição só valem após aprovação jurídica da administração."""
from __future__ import annotations

import hashlib

from ..http import ApiError, Ctx, not_found, page, route
from ..services import payments
from . import schemas as S

T = ("funding",)
CM_COLS = ("id::text AS id, project_id::text AS project_id, kind, title, description, legal_structure, refundable, refund_policy, min_contribution_cents,"
           " quota_value_cents, quotas_total, status, legal_note, approved_at, created_at")


# ------------------------------------------------------------------------------------------------ modelos de contribuição
@route("GET", "/v1/projects/{project_id}/contribution-models", min_role="viewer", tags=T,
       summary="Modelos de contribuição do projeto (a OSC vê todos; os demais, só os aprovados juridicamente)")
def list_models(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {CM_COLS} FROM contribution_models WHERE project_id = $1 ORDER BY created_at DESC", ctx.path["project_id"])
    return {"items": rows}


@route("POST", "/v1/projects/{project_id}/contribution-models", body=S.ContributionModelIn, kinds=("osc",), min_role="manager", status=201, tags=T,
       summary="Propõe um modelo (doação, patrocínio, cotas, lei de incentivo, investimento de impacto). Nasce em rascunho")
def create_model(ctx: Ctx, body: S.ContributionModelIn):
    if body.refundable and not body.refund_policy:
        raise ApiError(422, "refund_policy_required", "Modelo reembolsável exige a política de devolução")
    if body.kind == "quota" and not (body.quota_value_cents and body.quotas_total):
        raise ApiError(422, "quota_fields_required", "Cotas exigem valor da cota e quantidade")
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", ctx.path["project_id"], ctx.org_id):
            raise not_found("Projeto")
        mid = c.scalar("INSERT INTO contribution_models(org_id, project_id, kind, title, description, legal_structure, refundable, refund_policy,"
                       " min_contribution_cents, quota_value_cents, quotas_total, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::bigint,$10::bigint,$11::int,$12)"
                       " RETURNING id::text", ctx.org_id, ctx.path["project_id"], body.kind, body.title, body.description, body.legal_structure,
                       body.refundable, body.refund_policy, body.min_contribution_cents, body.quota_value_cents, body.quotas_total, ctx.user_id)
        ctx.audit(c, "contribution_model.created", "contribution_model", mid, {"kind": body.kind})
    return {"id": mid, "status": "draft"}


@route("POST", "/v1/contribution-models/{model_id}/submit", kinds=("osc",), min_role="manager", tags=T, summary="Envia o modelo à revisão jurídica da administração")
def submit_model(ctx: Ctx):
    with ctx.tx() as c:
        m = c.one("SELECT id::text AS id, status FROM contribution_models WHERE id = $1 AND org_id = $2", ctx.path["model_id"], ctx.org_id)
        if not m:
            raise not_found("Modelo")
        if m["status"] != "draft":
            raise ApiError(409, "invalid_transition", "Só rascunhos podem ser enviados")
        c.run("UPDATE contribution_models SET status = 'legal_review' WHERE id = $1", m["id"])
        ctx.audit(c, "contribution_model.submitted", "contribution_model", m["id"])
    return {"id": m["id"], "status": "legal_review"}


@route("POST", "/v1/contribution-models/{model_id}/retire", kinds=("osc",), min_role="manager", tags=T)
def retire_model(ctx: Ctx):
    with ctx.tx() as c:
        if not c.run("UPDATE contribution_models SET status = 'retired' WHERE id = $1 AND org_id = $2 AND status <> 'retired'", ctx.path["model_id"], ctx.org_id):
            raise not_found("Modelo")
        ctx.audit(c, "contribution_model.retired", "contribution_model", ctx.path["model_id"])
    return {"status": "retired"}


@route("GET", "/v1/admin/contribution-models", auth="admin", tags=("admin",), summary="Fila de revisão jurídica de modelos de contribuição")
def admin_list_models(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT m.id::text AS id, m.kind, m.title, m.legal_structure, m.refundable, m.refund_policy, m.status, m.created_at, o.legal_name AS org_name"
                       " FROM contribution_models m JOIN organizations o ON o.id = m.org_id WHERE m.status = 'legal_review' ORDER BY m.created_at")
    return {"items": rows}


@route("POST", "/v1/admin/contribution-models/{model_id}/decide", auth="admin", body=S.LegalDecisionIn, tags=("admin",),
       summary="Decisão jurídica: aprova (vira utilizável em pagamentos) ou devolve ao rascunho, com parecer registrado")
def admin_decide_model(ctx: Ctx, body: S.LegalDecisionIn):
    with ctx.tx() as c:
        m = c.one("SELECT id::text AS id, status, org_id::text AS org_id FROM contribution_models WHERE id = $1", ctx.path["model_id"])
        if not m or m["status"] != "legal_review":
            raise ApiError(409, "not_in_review", "Modelo não está em revisão jurídica")
        if body.approve:
            c.run("UPDATE contribution_models SET status = 'approved', legal_reviewer = $2, legal_note = $3, approved_at = now() WHERE id = $1", m["id"], ctx.user_id, body.note)
        else:
            c.run("UPDATE contribution_models SET status = 'draft', legal_reviewer = $2, legal_note = $3 WHERE id = $1", m["id"], ctx.user_id, body.note)
        c.scalar("SELECT app_notify($1, NULL, 'funding', 'Modelo de contribuição analisado', $2, '/aportes')", m["org_id"],
                 ("Aprovado. " if body.approve else "Devolvido: ") + body.note[:300])
        ctx.audit(c, "contribution_model.legal_decision", "contribution_model", m["id"], {"approved": body.approve}, org_id=m["org_id"])
    return {"id": m["id"], "status": "approved" if body.approve else "draft"}


# ------------------------------------------------------------------------------------------------ pagamentos
PAY_COLS = ("p.id::text AS id, p.commitment_id::text AS commitment_id, p.project_id::text AS project_id, p.amount_cents, p.refunded_cents, p.state,"
            " p.method, p.external_ref, p.reconciliation_status, p.contribution_model_id::text AS contribution_model_id, p.created_at, p.updated_at")


@route("POST", "/v1/commitments/{commitment_id}/payments", body=S.PaymentIn, kinds=("company", "government", "individual"), min_role="manager", status=201, tags=T,
       summary="Registra um pagamento (parcela) do aporte — declarado pelo financiador; a plataforma não movimenta dinheiro")
def create_payment(ctx: Ctx, body: S.PaymentIn):
    with ctx.tx() as c:
        pid = payments.create(c, ctx, ctx.path["commitment_id"], body.amount_cents, body.method, body.external_ref, body.contribution_model_id)
        ctx.audit(c, "payment.created", "payment", pid, {"amount_cents": body.amount_cents, "method": body.method})
    return {"id": pid, "state": "created"}


@route("GET", "/v1/payments", query=S.Pagination, min_role="viewer", tags=T, summary="Pagamentos da organização (como financiador ou OSC)")
def list_payments(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {PAY_COLS}, pr.title AS project_title FROM payment_records p JOIN projects pr ON pr.id = p.project_id"
                       " WHERE p.funder_org_id = $1 OR p.osc_org_id = $1 ORDER BY p.created_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/payments/{payment_id}", min_role="viewer", tags=T, summary="Pagamento com linha do tempo de estados e estornos")
def get_payment(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        p = c.one(f"SELECT {PAY_COLS} FROM payment_records p WHERE p.id = $1 AND (p.funder_org_id = $2 OR p.osc_org_id = $2)", ctx.path["payment_id"], ctx.org_id)
        if not p:
            raise not_found("Pagamento")
        p["events"] = c.query("SELECT from_state, to_state, note, at, org_display(actor_org_id) AS actor FROM payment_events WHERE payment_id = $1 ORDER BY at", p["id"])
        p["refunds"] = c.query("SELECT id::text AS id, amount_cents, reason, status, created_at, decided_at, requested_by_org::text AS requested_by_org FROM refunds"
                               " WHERE payment_id = $1 ORDER BY created_at", p["id"])
    return p


@route("POST", "/v1/payments/{payment_id}/transition", body=S.PaymentMoveIn, min_role="manager", tags=T,
       summary="Muda o estado (financiador: declara/cancela; OSC: confirma/recusa; ambos: abrem disputa). O banco recusa transições inválidas")
def move_payment(ctx: Ctx, body: S.PaymentMoveIn):
    with ctx.tx() as c:
        out = payments.move(c, ctx, ctx.path["payment_id"], body.to, body.note)
        ctx.audit(c, "payment.transition", "payment", ctx.path["payment_id"], {"to": body.to})
    return out


@route("POST", "/v1/payments/{payment_id}/refunds", body=S.RefundIn, min_role="manager", status=201, tags=T, summary="Solicita estorno total ou parcial (a outra parte decide)")
def request_refund(ctx: Ctx, body: S.RefundIn):
    with ctx.tx() as c:
        rid = payments.request_refund(c, ctx, ctx.path["payment_id"], body.amount_cents, body.reason)
        ctx.audit(c, "refund.requested", "refund", rid, {"amount_cents": body.amount_cents})
    return {"id": rid, "status": "requested"}


@route("POST", "/v1/refunds/{refund_id}/decide", body=S.RefundDecisionIn, min_role="manager", tags=T,
       summary="Aprova/rejeita (a parte que NÃO pediu) ou conclui (OSC registra a devolução)")
def decide_refund(ctx: Ctx, body: S.RefundDecisionIn):
    with ctx.tx() as c:
        out = payments.decide_refund(c, ctx, ctx.path["refund_id"], body.decision)
        ctx.audit(c, "refund.decided", "refund", ctx.path["refund_id"], {"decision": body.decision})
    return out


# ------------------------------------------------------------------------------------------------ extrato e reconciliação (OSC)
@route("POST", "/v1/statements", body=S.StatementIn, kinds=("osc",), min_role="manager", status=201, tags=T,
       summary="Importa extrato CSV (data;valor;descricao;referencia) para conferir recebimentos. Reimportar o mesmo arquivo é recusado")
def import_statement(ctx: Ctx, body: S.StatementIn):
    try:
        rows = payments.parse_statement(body.csv)
    except ValueError as e:
        raise ApiError(422, "invalid_statement", str(e)) from e
    digest = hashlib.sha256(body.csv.encode()).hexdigest()
    with ctx.tx() as c:
        if c.one("SELECT 1 FROM statement_imports WHERE org_id = $1 AND sha256 = $2", ctx.org_id, digest):
            raise ApiError(409, "already_imported", "Este extrato já foi importado")
        iid = c.scalar("INSERT INTO statement_imports(org_id, filename, sha256, row_count, created_by) VALUES ($1,$2,$3,$4,$5) RETURNING id::text",
                       ctx.org_id, body.filename, digest, len(rows), ctx.user_id)
        for r in rows:
            c.run("INSERT INTO statement_lines(import_id, org_id, booked_on, amount_cents, description, reference) VALUES ($1,$2,$3::date,$4::bigint,$5,$6)",
                  iid, ctx.org_id, r["booked_on"], r["amount_cents"], r["description"], r["reference"])
        result = payments.reconcile(c, ctx.org_id)
        ctx.audit(c, "statement.imported", "statement_import", iid, {"rows": len(rows)})
    return {"id": iid, "rows": len(rows), "reconciliation": result}


@route("POST", "/v1/statements/reconcile", kinds=("osc",), min_role="manager", tags=T, summary="Reexecuta o pareamento extrato × pagamentos")
def reconcile(ctx: Ctx):
    with ctx.tx() as c:
        return payments.reconcile(c, ctx.org_id)


@route("GET", "/v1/statements/lines", kinds=("osc",), query=S.Pagination, min_role="viewer", tags=T)
def statement_lines(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, booked_on, amount_cents, description, reference, matched_payment_id::text AS matched_payment_id FROM statement_lines"
                       " WHERE org_id = $1 ORDER BY booked_on DESC, id LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
        summary = c.one("SELECT count(*) AS lines, count(*) FILTER (WHERE matched_payment_id IS NOT NULL) AS matched FROM statement_lines WHERE org_id = $1", ctx.org_id)
    return {**page(rows, q.limit, q.offset), "summary": summary}


@route("POST", "/v1/payments/{payment_id}/reconcile-manual", body=S.ManualMatchIn, kinds=("osc",), min_role="manager", tags=T,
       summary="Pareamento manual de uma linha do extrato com um pagamento (registrado em auditoria)")
def reconcile_manual(ctx: Ctx, body: S.ManualMatchIn):
    with ctx.tx() as c:
        p = c.one("SELECT id::text AS id FROM payment_records WHERE id = $1 AND osc_org_id = $2", ctx.path["payment_id"], ctx.org_id)
        ln = c.one("SELECT id::text AS id FROM statement_lines WHERE id = $1 AND org_id = $2 AND matched_payment_id IS NULL", body.line_id, ctx.org_id)
        if not p or not ln:
            raise not_found("Pagamento ou linha")
        c.run("UPDATE statement_lines SET matched_payment_id = $2 WHERE id = $1", ln["id"], p["id"])
        c.run("UPDATE payment_records SET reconciliation_status = 'manual' WHERE id = $1", p["id"])
        ctx.audit(c, "payment.reconciled_manually", "payment", p["id"], {"line_id": ln["id"]})
    return {"id": p["id"], "reconciliation_status": "manual"}
