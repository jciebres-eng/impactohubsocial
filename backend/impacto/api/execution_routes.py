"""Execução e prestação de contas: despesas comprovadas, evidências por etapa (com revisão do financiador),
devolutivas/relatórios, Impact Ledger verificável e painel de rastreio do recurso investido."""
from __future__ import annotations

import csv
import io

from starlette.responses import Response

from ..http import ApiError, Ctx, not_found, page, route
from ..services.audit import ledger
from ..services.validators import cnpj_valid, only_digits
from . import schemas as S

T = ("execution",)


def _project_owned(c, ctx, pid):
    p = c.one("SELECT id::text AS id, status FROM projects WHERE id = $1 AND org_id = $2", pid, ctx.org_id)
    if not p:
        raise not_found("Projeto")
    return p


def _doc_ok(c, ctx, doc_id):
    if doc_id and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", doc_id, ctx.org_id):
        raise not_found("Documento")


@route("GET", "/v1/projects/{project_id}/expenses", query=S.Pagination, min_role="viewer", tags=T,
       summary="Despesas do projeto (OSC dona e financiadores com aporte)")
def list_expenses(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT e.id::text AS id, e.description, e.supplier_name, e.supplier_cnpj, e.amount_cents, e.paid_on, e.status,"
                       " e.review_note, e.milestone_id::text AS milestone_id, e.budget_item_id::text AS budget_item_id,"
                       " e.document_id::text AS document_id, e.created_at, b.description AS budget_item"
                       " FROM expenses e LEFT JOIN budget_items b ON b.id = e.budget_item_id WHERE e.project_id = $1"
                       " ORDER BY e.paid_on DESC LIMIT $2 OFFSET $3", ctx.path["project_id"], q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/projects/{project_id}/expenses", body=S.ExpenseIn, kinds=("osc",), min_role="member", status=201, tags=T,
       summary="Registra despesa com comprovante (nota fiscal/recibo) vinculada a marco e item de orçamento")
def add_expense(ctx: Ctx, body: S.ExpenseIn):
    cnpj = only_digits(body.supplier_cnpj) if body.supplier_cnpj else None
    if cnpj and not cnpj_valid(cnpj):
        raise ApiError(422, "validation_error", "CNPJ do fornecedor inválido")
    with ctx.tx() as c:
        p = _project_owned(c, ctx, ctx.path["project_id"])
        _doc_ok(c, ctx, body.document_id)
        for col, val in (("milestones", body.milestone_id), ("budget_items", body.budget_item_id)):
            if val and not c.one(f"SELECT 1 FROM {col} WHERE id = $1 AND project_id = $2", val, p["id"]):
                raise not_found("Marco/item")
        if body.commitment_id and not c.one("SELECT 1 FROM commitments WHERE id = $1 AND project_id = $2", body.commitment_id, p["id"]):
            raise not_found("Aporte")
        if body.procurement_request_id and not c.one("SELECT 1 FROM procurement_requests WHERE id = $1 AND project_id = $2 AND org_id = $3"
                                                     " AND status IN ('decided','exception_approved')", body.procurement_request_id, p["id"], ctx.org_id):
            raise ApiError(409, "procurement_not_decided", "O pedido de compra vinculado não existe ou ainda não foi decidido/aprovado")
        eid = c.scalar("INSERT INTO expenses(project_id, org_id, milestone_id, commitment_id, budget_item_id, description, supplier_name,"
                       " supplier_cnpj, amount_cents, paid_on, document_id, created_by, procurement_request_id) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::bigint,$10::date,$11,$12,$13)"
                       " RETURNING id::text", p["id"], ctx.org_id, body.milestone_id, body.commitment_id, body.budget_item_id,
                       body.description, body.supplier_name, cnpj, body.amount_cents, body.paid_on, body.document_id, ctx.user_id, body.procurement_request_id)
        ledger(c, project_id=p["id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="expense_recorded", amount_cents=body.amount_cents,
               ref_type="expense", ref_id=eid, payload={"description": body.description, "has_receipt": bool(body.document_id)})
        ctx.audit(c, "execution.expense_recorded", "expense", eid, {"amount_cents": body.amount_cents})
    return {"id": eid}


@route("POST", "/v1/expenses/{expense_id}/review", body=S.ReviewDecisionIn, kinds=("company", "government", "individual"), min_role="analyst", tags=T,
       summary="Financiador valida ou questiona a despesa (a OSC não revisa a si mesma — garantido também no banco)")
def review_expense(ctx: Ctx, body: S.ReviewDecisionIn):
    if body.status not in ("validated", "questioned"):
        raise ApiError(422, "validation_error", "Use validated ou questioned")
    with ctx.tx() as c:
        e = c.one("SELECT id::text AS id, project_id::text AS project_id, org_id::text AS org_id FROM expenses WHERE id = $1", ctx.path["expense_id"])
        if not e or not c.scalar("SELECT app_project_investor($1)", e["project_id"]):
            raise not_found("Despesa")
        c.run("UPDATE expenses SET status = $2, review_note = $3 WHERE id = $1", e["id"], body.status, body.note)
        c.scalar("SELECT app_notify($1, NULL, 'execution', $2, $3, $4)", e["org_id"], "Despesa revisada",
                 f"Status: {body.status}. {body.note or ''}", f"/projetos/{e['project_id']}")
        ctx.audit(c, "execution.expense_reviewed", "expense", e["id"], {"status": body.status})
    return {"id": e["id"], "status": body.status}


@route("GET", "/v1/projects/{project_id}/evidences", query=S.Pagination, min_role="viewer", tags=T)
def list_evidences(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT e.id::text AS id, e.kind, e.title, e.description, e.occurred_on, e.status, e.indicator_name,"
                       " e.indicator_value::float AS indicator_value, e.review_note, e.reviewed_at, e.milestone_id::text AS milestone_id,"
                       " e.document_id::text AS document_id, m.title AS milestone_title, e.created_at"
                       " FROM evidences e LEFT JOIN milestones m ON m.id = e.milestone_id WHERE e.project_id = $1"
                       " ORDER BY e.created_at DESC LIMIT $2 OFFSET $3", ctx.path["project_id"], q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/projects/{project_id}/evidences", body=S.EvidenceIn, kinds=("osc",), min_role="member", status=201, tags=T,
       summary="Posta evidência de uma etapa (foto, lista de presença, relatório, resultado de indicador)")
def add_evidence(ctx: Ctx, body: S.EvidenceIn):
    with ctx.tx() as c:
        p = _project_owned(c, ctx, ctx.path["project_id"])
        _doc_ok(c, ctx, body.document_id)
        if body.milestone_id and not c.one("SELECT 1 FROM milestones WHERE id = $1 AND project_id = $2", body.milestone_id, p["id"]):
            raise not_found("Marco")
        evid = c.scalar("INSERT INTO evidences(project_id, org_id, milestone_id, application_id, kind, title, description, occurred_on,"
                        " document_id, indicator_name, indicator_value, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::date,$9,$10,$11::numeric,$12)"
                        " RETURNING id::text", p["id"], ctx.org_id, body.milestone_id, body.application_id, body.kind, body.title,
                        body.description, body.occurred_on, body.document_id, body.indicator_name, body.indicator_value, ctx.user_id)
        if body.milestone_id:
            c.run("UPDATE milestones SET status = 'evidence_submitted' WHERE id = $1 AND status IN ('funded','in_progress','open')", body.milestone_id)
        ledger(c, project_id=p["id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="evidence_submitted", ref_type="evidence", ref_id=evid,
               payload={"kind": body.kind, "title": body.title, "indicator": body.indicator_name, "value": body.indicator_value})
        for f in c.query("SELECT DISTINCT funder_org_id::text AS id FROM commitments WHERE project_id = $1 AND status <> 'cancelled'", p["id"]):
            c.scalar("SELECT app_notify($1, NULL, 'evidence', $2, $3, $4)", f["id"], "Nova evidência para revisão", body.title, f"/projetos/{p['id']}")
        ctx.audit(c, "execution.evidence_submitted", "evidence", evid)
    return {"id": evid}


@route("POST", "/v1/evidences/{evidence_id}/review", body=S.ReviewDecisionIn, kinds=("company", "government", "individual"), min_role="analyst", tags=T)
def review_evidence(ctx: Ctx, body: S.ReviewDecisionIn):
    if body.status not in ("accepted", "rejected", "needs_info"):
        raise ApiError(422, "validation_error", "Use accepted, rejected ou needs_info")
    with ctx.tx() as c:
        e = c.one("SELECT id::text AS id, project_id::text AS project_id, org_id::text AS org_id, milestone_id::text AS milestone_id"
                  " FROM evidences WHERE id = $1", ctx.path["evidence_id"])
        if not e or not c.scalar("SELECT app_project_investor($1)", e["project_id"]):
            raise not_found("Evidência")
        c.run("UPDATE evidences SET status = $2, review_note = $3, reviewed_by = $4, reviewed_by_org = $5, reviewed_at = now() WHERE id = $1",
              e["id"], body.status, body.note, ctx.user_id, ctx.org_id)
        ledger(c, project_id=e["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="evidence_reviewed", ref_type="evidence",
               ref_id=e["id"], payload={"status": body.status})
        c.scalar("SELECT app_notify($1, NULL, 'evidence', $2, $3, $4)", e["org_id"], "Evidência revisada",
                 f"Status: {body.status}. {body.note or ''}", f"/projetos/{e['project_id']}")
        ctx.audit(c, "execution.evidence_reviewed", "evidence", e["id"], {"status": body.status})
    if body.status == "accepted" and e["milestone_id"]:
        with ctx.system_tx() as c:
            c.run("UPDATE milestones SET status = 'accepted' WHERE id = $1 AND status = 'evidence_submitted'", e["milestone_id"])
    return {"id": e["id"], "status": body.status}


@route("GET", "/v1/projects/{project_id}/feedbacks", min_role="viewer", tags=T, summary="Devolutivas e relatórios")
def list_feedbacks(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT f.id::text AS id, f.kind, f.body, f.rating, f.created_at, f.document_id::text AS document_id,"
                                 " o.legal_name AS author_org FROM feedbacks f JOIN organizations o ON o.id = f.author_org_id"
                                 " WHERE f.project_id = $1 ORDER BY f.created_at DESC", ctx.path["project_id"])}


@route("POST", "/v1/projects/{project_id}/feedbacks", body=S.FeedbackIn, min_role="member", status=201, tags=T,
       summary="OSC envia relatório parcial/final; financiador envia devolutiva")
def add_feedback(ctx: Ctx, body: S.FeedbackIn):
    pid = ctx.path["project_id"]
    with ctx.tx() as c:
        owner = c.scalar("SELECT app_project_owner($1)", pid)
        investor = c.scalar("SELECT app_project_investor($1)", pid)
        if not (owner or investor):
            raise not_found("Projeto")
        if owner and body.kind == "funder_feedback" or investor and not owner and body.kind != "funder_feedback":
            raise ApiError(422, "validation_error", "Tipo de registro incompatível com o seu papel no projeto")
        _doc_ok(c, ctx, body.document_id)
        fid = c.scalar("INSERT INTO feedbacks(project_id, application_id, author_org_id, author_user_id, kind, body, rating, document_id)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7::smallint,$8) RETURNING id::text", pid, body.application_id, ctx.org_id, ctx.user_id,
                       body.kind, body.body, body.rating, body.document_id)
        ledger(c, project_id=pid, org_id=ctx.org_id, actor=ctx.user_id,
               entry_type="feedback_given" if body.kind == "funder_feedback" else "report_submitted", ref_type="feedback", ref_id=fid,
               payload={"kind": body.kind})
        ctx.audit(c, "execution.feedback", "feedback", fid, {"kind": body.kind})
    return {"id": fid}


@route("GET", "/v1/projects/{project_id}/ledger", min_role="viewer", tags=("ledger",),
       summary="Impact Ledger do projeto (append-only, encadeado por hash) com verificação de integridade")
def get_ledger(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT l.seq, l.entry_type, l.amount_cents, l.ref_type, l.ref_id::text AS ref_id, l.payload, l.prev_hash, l.entry_hash,"
                       " l.at, org_display(l.org_id) AS org_name FROM ledger_entries l JOIN organizations o ON o.id = l.org_id"
                       " WHERE l.project_id = $1 ORDER BY l.seq", ctx.path["project_id"])
        if not rows and not c.one("SELECT 1 FROM projects WHERE id = $1", ctx.path["project_id"]):
            raise not_found("Projeto")
        v = c.one("SELECT * FROM ledger_verify($1)", ctx.path["project_id"])
    return {"entries": rows, "verification": v}


# ------------------------------------------------------------------------------------------------ rastreio do investimento
@route("GET", "/v1/portfolio", kinds=("company", "government", "individual"), min_role="viewer", tags=("portfolio",),
       summary="Carteira do financiador: recurso comprometido → desembolsado → gasto comprovado → evidências e resultados")
def portfolio(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query(
            "SELECT p.id::text AS project_id, p.title, p.status, p.territory, p.causes, o.legal_name AS osc_name,"
            " sum(cm.amount_cents) FILTER (WHERE cm.status <> 'cancelled') AS committed_cents,"
            " sum(cm.amount_cents) FILTER (WHERE cm.status IN ('disbursed','confirmed')) AS disbursed_cents,"
            " sum(cm.amount_cents) FILTER (WHERE cm.status = 'confirmed') AS confirmed_cents,"
            " (SELECT coalesce(sum(e.amount_cents),0) FROM expenses e WHERE e.project_id = p.id) AS spent_cents,"
            " (SELECT coalesce(sum(e.amount_cents),0) FROM expenses e WHERE e.project_id = p.id AND e.status = 'validated') AS validated_spent_cents,"
            " (SELECT count(*) FROM evidences ev WHERE ev.project_id = p.id AND ev.status = 'accepted') AS accepted_evidences,"
            " (SELECT count(*) FROM evidences ev WHERE ev.project_id = p.id AND ev.status = 'submitted') AS pending_evidences,"
            " p.beneficiaries_count"
            " FROM commitments cm JOIN projects p ON p.id = cm.project_id JOIN organizations o ON o.id = p.org_id"
            " WHERE cm.funder_org_id = $1 GROUP BY p.id, o.legal_name ORDER BY max(cm.created_at) DESC", ctx.org_id)
    totals = {k: sum(int(r[k] or 0) for r in rows) for k in ("committed_cents", "disbursed_cents", "confirmed_cents", "spent_cents",
                                                              "validated_spent_cents", "accepted_evidences", "pending_evidences")}
    totals["beneficiaries"] = sum(int(r["beneficiaries_count"] or 0) for r in rows)
    totals["projects"] = len(rows)
    return {"items": rows, "totals": totals}


@route("GET", "/v1/projects/{project_id}/report", min_role="viewer", tags=("portfolio",),
       summary="Relatório consolidado do projeto (dados para gráficos: orçamento × captado × gasto, evidências, indicadores)")
def project_report(ctx: Ctx):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        p = c.one("SELECT id::text AS id, title, status, territory, causes, ods, beneficiaries_count, budget_total_cents, indicators,"
                  " starts_on, ends_on FROM projects WHERE id = $1", pid)
        if not p:
            raise not_found("Projeto")
        funding = c.one("SELECT * FROM project_funding($1)", pid)
        by_milestone = c.query("SELECT m.seq, m.title, m.amount_cents, m.funded_cents, m.status,"
                               " (SELECT coalesce(sum(e.amount_cents),0) FROM expenses e WHERE e.milestone_id = m.id) AS spent_cents,"
                               " (SELECT count(*) FROM evidences ev WHERE ev.milestone_id = m.id AND ev.status = 'accepted') AS accepted_evidences"
                               " FROM milestones m WHERE m.project_id = $1 ORDER BY m.seq", pid)
        by_category = c.query("SELECT b.category, sum(b.total_cents) AS budget_cents,"
                              " coalesce(sum((SELECT sum(e.amount_cents) FROM expenses e WHERE e.budget_item_id = b.id)),0) AS spent_cents"
                              " FROM budget_items b WHERE b.project_id = $1 GROUP BY b.category ORDER BY b.category", pid)
        indicators = c.query("SELECT indicator_name AS name, sum(indicator_value)::float AS achieved, count(*) AS records FROM evidences"
                             " WHERE project_id = $1 AND indicator_name IS NOT NULL AND status = 'accepted' GROUP BY indicator_name", pid)
        timeline = c.query("SELECT date_trunc('month', at)::date AS month, entry_type, count(*) AS n, sum(amount_cents) AS amount_cents"
                           " FROM ledger_entries WHERE project_id = $1 GROUP BY 1, 2 ORDER BY 1", pid)
    targets = {i.get("name"): i for i in (p["indicators"] or [])}
    for ind in indicators:
        t = targets.get(ind["name"]) or {}
        ind["target"] = t.get("target")
        ind["unit"] = t.get("unit")
    return {"project": p, "funding": funding, "milestones": by_milestone, "budget_by_category": by_category,
            "indicators": indicators, "ledger_timeline": timeline}


@route("GET", "/v1/projects/{project_id}/expenses.csv", min_role="viewer", raw=True, tags=("portfolio",),
       summary="Exporta despesas em CSV (prestação de contas)")
def expenses_csv(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT paid_on, description, supplier_name, supplier_cnpj, amount_cents, status FROM expenses WHERE project_id = $1"
                       " ORDER BY paid_on", ctx.path["project_id"])
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["data_pagamento", "descricao", "fornecedor", "cnpj_fornecedor", "valor_reais", "status"])
    def safe(v):  # proteção contra CSV/formula injection
        v = "" if v is None else str(v)
        return "'" + v if v[:1] in ("=", "+", "-", "@", "\t", "\r") else v
    for r in rows:
        w.writerow([r["paid_on"], safe(r["description"]), safe(r["supplier_name"]), r["supplier_cnpj"] or "",
                    f"{r['amount_cents'] / 100:.2f}".replace(".", ","), r["status"]])
    return Response(buf.getvalue().encode("utf-8-sig"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="despesas.csv"', "Cache-Control": "no-store"})
