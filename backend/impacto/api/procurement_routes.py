"""Compras da OSC: política configurável de cotações, fornecedores, pedidos, cotações, benchmark e exceções com aprovação.

O benchmark sinaliza "preço possivelmente fora do padrão das cotações" — nunca acusa fraude. A decisão e a exceção são humanas
e ficam registradas (separação de funções: quem aprova a exceção não é quem decidiu — também no banco)."""
from __future__ import annotations

from ..http import ApiError, Ctx, not_found, page, route
from ..services import procurement
from ..services.audit import ledger
from ..services.validators import cnpj_valid, only_digits
from . import schemas as S

T = ("procurement",)


def _req(c, ctx, rid: str, *, lock: bool = False) -> dict:
    r = c.one("SELECT id::text AS id, project_id::text AS project_id, status, estimated_cents, decided_by::text AS decided_by FROM procurement_requests"
              " WHERE id = $1 AND org_id = $2" + (" FOR UPDATE" if lock else ""), rid, ctx.org_id)
    if not r:
        raise not_found("Pedido de compra")
    return r


@route("GET", "/v1/procurement/policy", kinds=("osc",), min_role="viewer", tags=T, summary="Política de cotações da organização (padrão: 3 cotações)")
def get_policy(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return procurement.policy_for(c, ctx.org_id)


@route("PUT", "/v1/procurement/policy", body=S.ProcurementPolicyIn, kinds=("osc",), min_role="admin", tags=T,
       summary="Configura nº mínimo de cotações, valor a partir do qual exige, limite de desvio e aprovação de exceções")
def put_policy(ctx: Ctx, body: S.ProcurementPolicyIn):
    with ctx.tx() as c:
        c.run("INSERT INTO procurement_policies(org_id, min_quotes, quote_threshold_cents, outlier_pct, exception_needs_approval)"
              " VALUES ($1,$2,$3::bigint,$4::numeric,$5) ON CONFLICT (org_id) DO UPDATE SET min_quotes = EXCLUDED.min_quotes,"
              " quote_threshold_cents = EXCLUDED.quote_threshold_cents, outlier_pct = EXCLUDED.outlier_pct,"
              " exception_needs_approval = EXCLUDED.exception_needs_approval, updated_at = now()",
              ctx.org_id, body.min_quotes, body.quote_threshold_cents, body.outlier_pct, body.exception_needs_approval)
        ctx.audit(c, "procurement.policy_updated", "organization", ctx.org_id, body.model_dump())
        return procurement.policy_for(c, ctx.org_id)


@route("GET", "/v1/suppliers", kinds=("osc",), query=S.Pagination, min_role="viewer", tags=T)
def list_suppliers(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, name, cnpj, category FROM suppliers WHERE org_id = $1 ORDER BY lower(name) LIMIT $2 OFFSET $3",
                       ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/suppliers", body=S.SupplierIn, kinds=("osc",), min_role="member", status=201, tags=T)
def create_supplier(ctx: Ctx, body: S.SupplierIn):
    cnpj = only_digits(body.cnpj) if body.cnpj else None
    if cnpj and not cnpj_valid(cnpj):
        raise ApiError(422, "validation_error", "CNPJ inválido")
    with ctx.tx() as c:
        if cnpj and c.one("SELECT 1 FROM suppliers WHERE org_id = $1 AND cnpj = $2", ctx.org_id, cnpj):
            raise ApiError(409, "supplier_exists", "Fornecedor já cadastrado")
        sid = c.scalar("INSERT INTO suppliers(org_id, name, cnpj, category) VALUES ($1,$2,$3,$4) RETURNING id::text", ctx.org_id, body.name, cnpj, body.category)
    return {"id": sid}


@route("GET", "/v1/projects/{project_id}/procurement", min_role="viewer", query=S.Pagination, tags=T, summary="Pedidos de compra do projeto (OSC dona ou financiador)")
def list_requests(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT r.id::text AS id, r.description, r.estimated_cents, r.status, r.created_at, (SELECT count(*) FROM quotations x WHERE x.request_id = r.id) AS quotes"
                       " FROM procurement_requests r WHERE r.project_id = $1 ORDER BY r.created_at DESC LIMIT $2 OFFSET $3", ctx.path["project_id"], q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/projects/{project_id}/procurement", body=S.ProcurementRequestIn, kinds=("osc",), min_role="member", status=201, tags=T)
def create_request(ctx: Ctx, body: S.ProcurementRequestIn):
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", ctx.path["project_id"], ctx.org_id):
            raise not_found("Projeto")
        if body.budget_item_id and not c.one("SELECT 1 FROM budget_items WHERE id = $1 AND project_id = $2", body.budget_item_id, ctx.path["project_id"]):
            raise not_found("Item de orçamento")
        rid = c.scalar("INSERT INTO procurement_requests(org_id, project_id, budget_item_id, description, estimated_cents, created_by)"
                       " VALUES ($1,$2,$3,$4,$5::bigint,$6) RETURNING id::text", ctx.org_id, ctx.path["project_id"], body.budget_item_id,
                       body.description, body.estimated_cents, ctx.user_id)
        pol = procurement.policy_for(c, ctx.org_id)
        ctx.audit(c, "procurement.requested", "procurement_request", rid)
    return {"id": rid, "required_quotes": procurement.requirement(pol, body.estimated_cents)}


@route("GET", "/v1/procurement/{request_id}", min_role="viewer", tags=T, summary="Pedido com cotações, benchmark (média, mediana, mín., máx., desvio) e conformidade com a política")
def get_request(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rep = procurement.report(c, ctx.path["request_id"])
        if not rep:
            raise not_found("Pedido de compra")
    return rep


@route("POST", "/v1/procurement/{request_id}/quotes", body=S.QuotationIn, kinds=("osc",), min_role="member", status=201, tags=T)
def add_quote(ctx: Ctx, body: S.QuotationIn):
    cnpj = only_digits(body.supplier_cnpj) if body.supplier_cnpj else None
    if cnpj and not cnpj_valid(cnpj):
        raise ApiError(422, "validation_error", "CNPJ do fornecedor inválido")
    with ctx.tx() as c:
        r = _req(c, ctx, ctx.path["request_id"], lock=True)
        if r["status"] not in ("open", "exception_pending"):
            raise ApiError(409, "closed", "Pedido já decidido")
        if body.document_id and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", body.document_id, ctx.org_id):
            raise not_found("Documento")
        key_dup = c.one("SELECT 1 FROM quotations WHERE request_id = $1 AND coalesce(supplier_cnpj, lower(supplier_name)) = $2", r["id"], cnpj or body.supplier_name.lower())
        if key_dup:
            raise ApiError(409, "duplicate_supplier", "Já existe cotação deste fornecedor neste pedido")
        sup = c.one("SELECT id::text AS id FROM suppliers WHERE org_id = $1 AND cnpj = $2", ctx.org_id, cnpj) if cnpj else None
        qid = c.scalar("INSERT INTO quotations(request_id, org_id, supplier_id, supplier_name, supplier_cnpj, amount_cents, valid_until, document_id, notes, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6::bigint,$7::date,$8,$9,$10) RETURNING id::text", r["id"], ctx.org_id, sup["id"] if sup else None,
                       body.supplier_name, cnpj, body.amount_cents, body.valid_until, body.document_id, body.notes, ctx.user_id)
        ctx.audit(c, "procurement.quote_added", "quotation", qid)
    return {"id": qid}


@route("DELETE", "/v1/procurement/{request_id}/quotes/{quote_id}", kinds=("osc",), min_role="member", tags=T)
def delete_quote(ctx: Ctx):
    with ctx.tx() as c:
        r = _req(c, ctx, ctx.path["request_id"], lock=True)
        if r["status"] not in ("open", "exception_pending"):
            raise ApiError(409, "closed", "Pedido já decidido")
        if not c.run("DELETE FROM quotations WHERE id = $1 AND request_id = $2", ctx.path["quote_id"], r["id"]):
            raise not_found("Cotação")
    return {"deleted": True}


@route("POST", "/v1/procurement/{request_id}/decide", body=S.ProcurementDecisionIn, kinds=("osc",), min_role="manager", tags=T,
       summary="Decide a compra: com cotações suficientes escolhe uma (justifica se não for a menor); sem elas, registra exceção (com aprovação)")
def decide(ctx: Ctx, body: S.ProcurementDecisionIn):
    with ctx.tx() as c:
        r = _req(c, ctx, ctx.path["request_id"], lock=True)
        if r["status"] not in ("open", "exception_pending"):
            raise ApiError(409, "closed", "Pedido já decidido")
        rep = procurement.report(c, r["id"])
        pol = rep["policy"]
        chosen = None
        if body.quotation_id:
            chosen = next((q for q in rep["quotes"] if q["id"] == body.quotation_id), None)
            if not chosen:
                raise not_found("Cotação")
        if rep["meets_policy"]:
            if not chosen:
                raise ApiError(422, "quotation_required", "Escolha uma das cotações")
            if rep["quotes"] and chosen["id"] != rep["quotes"][0]["id"] and not body.reason:
                raise ApiError(422, "reason_required", "Justifique a escolha de uma cotação que não é a de menor valor")
            if chosen["flag"] and not body.reason:
                raise ApiError(422, "reason_required", "A cotação escolhida está possivelmente fora do padrão; registre a justificativa")
            status = "decided"
        else:
            if not body.exception_reason:
                raise ApiError(422, "exception_required", f"A política exige {rep['required_quotes']} cotação(ões); informe o motivo da exceção",
                               {"required": rep["required_quotes"], "have": len(rep["quotes"])})
            status = "exception_pending" if pol["exception_needs_approval"] else "exception_approved"
        c.run("UPDATE procurement_requests SET status = $2, selected_quotation_id = $3, decision_reason = $4, exception_reason = $5, decided_by = $6,"
              " approved_by = CASE WHEN $2 = 'exception_approved' THEN NULL ELSE approved_by END WHERE id = $1",
              r["id"], status, chosen["id"] if chosen else None, body.reason, body.exception_reason, ctx.user_id)
        if status != "exception_pending":
            ledger(c, project_id=r["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="procurement_decided", ref_type="procurement_request",
                   ref_id=r["id"], amount_cents=chosen["amount_cents"] if chosen else None,
                   payload={"quotes": len(rep["quotes"]), "exception": not rep["meets_policy"]})
        ctx.audit(c, "procurement.decided", "procurement_request", r["id"], {"status": status})
    return {"id": r["id"], "status": status}


@route("POST", "/v1/procurement/{request_id}/approve-exception", kinds=("osc",), min_role="admin", tags=T,
       summary="Aprova a exceção à política (usuário diferente de quem decidiu)")
def approve_exception(ctx: Ctx):
    with ctx.tx() as c:
        r = _req(c, ctx, ctx.path["request_id"], lock=True)
        if r["status"] != "exception_pending":
            raise ApiError(409, "not_pending", "Não há exceção pendente")
        if r["decided_by"] == ctx.user_id:
            raise ApiError(403, "self_approval", "Quem decidiu não pode aprovar a própria exceção")
        c.run("UPDATE procurement_requests SET status = 'exception_approved', approved_by = $2, approved_at = now() WHERE id = $1", r["id"], ctx.user_id)
        ledger(c, project_id=r["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="procurement_decided", ref_type="procurement_request",
               ref_id=r["id"], payload={"exception": True, "approved": True})
        ctx.audit(c, "procurement.exception_approved", "procurement_request", r["id"])
    return {"id": r["id"], "status": "exception_approved"}
