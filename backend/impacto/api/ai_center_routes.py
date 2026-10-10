"""Central de IA (v0.28.0): catálogo, prévia, execuções, créditos por PIX, patrocínio, similaridade e painel financeiro.

Toda operação cobrada passa por `engines/ai/usage_control` (autoriza → reserva → executa → liquida). O
frontend NUNCA decide preço, saldo ou fonte: pede a prévia, mostra, e confirma.
"""
from __future__ import annotations

import json
from datetime import date
from typing import Annotated, Literal

from pydantic import Field
from starlette.responses import JSONResponse

from ..engines.ai import usage_control as UC
from ..http import ApiError, Ctx, not_found, page, route, unprocessable
from ..services import ai_center as AC
from ..services import similarity as SIM
from .schemas import In, Pagination, Uuid

T = ("ai",)


# ------------------------------------------------------------------------------------------------ esquemas
class PreviewIn(In):
    operation_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{2,60}$")]
    units: Annotated[int, Field(ge=1, le=500)] = 1
    input_chars: Annotated[int, Field(ge=0, le=10_000_000)] = 0
    project_id: Uuid | None = None


class CreditOrderIn(In):
    pack_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{2,40}$")]
    accept_terms: bool


class OrderConfirmIn(In):
    reference: Annotated[str, Field(min_length=6, max_length=120)]
    note: Annotated[str, Field(min_length=5, max_length=300)]


class PilotApproveIn(In):
    note: Annotated[str, Field(min_length=5, max_length=300)]


class SponsorshipIn(In):
    name: Annotated[str, Field(min_length=3, max_length=160)]
    budget_credits: Annotated[int, Field(ge=1, le=1_000_000)]
    starts_on: date | None = None
    ends_on: date
    eligible_kinds: list[Literal["osc", "company", "government", "individual", "provider"]] = ["osc"]
    eligible_org_ids: list[Uuid] = []
    eligible_uf: Annotated[str | None, Field(pattern=r"^[A-Za-z]{2}$")] = None
    operations: list[Annotated[str, Field(pattern=r"^(\*|[a-z][a-z0-9_.]{2,60})$")]] = ["*"]
    per_org_limit: Annotated[int | None, Field(ge=1)] = None
    per_project_limit: Annotated[int | None, Field(ge=1)] = None
    accountability: Annotated[str, Field(min_length=10, max_length=1000)]


class SimilarityIn(In):
    kind: Literal["single", "pair", "set", "complementarity", "expense_overlap"]
    compared_project_ids: list[Uuid] = []
    idempotency_key: Annotated[str | None, Field(min_length=8, max_length=80)] = None


class DisputeIn(In):
    reason: Annotated[str, Field(min_length=20, max_length=4000)]


class DisputeReviewIn(In):
    outcome: Literal["reviewed_upheld", "reviewed_corrected"]
    reviewer_note: Annotated[str, Field(min_length=10, max_length=2000)]


class OperationIn(In):
    code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{2,60}$")]
    name_pt: Annotated[str, Field(min_length=3, max_length=120)]
    description_pt: Annotated[str, Field(min_length=20, max_length=1200)]
    purpose_pt: Annotated[str, Field(min_length=10, max_length=400)]
    category: Literal["A", "B", "C", "D", "E", "F"]
    tier: Annotated[int, Field(ge=0, le=4)]
    allowed_kinds: list[Literal["osc", "company", "government", "individual", "provider"]]
    min_role: Literal["viewer", "member", "manager", "admin", "owner"] = "member"
    data_requirements_pt: Annotated[str, Field(min_length=5, max_length=600)]
    provider_mode: Literal["local", "external_allowed"]
    funding_modes: list[Literal["free", "free_quota", "sponsorship", "credits"]]
    credits_base: Annotated[int, Field(ge=0, le=100_000)]
    credits_per_unit: Annotated[int, Field(ge=0, le=100_000)] = 0
    unit_label_pt: Annotated[str, Field(min_length=2, max_length=40)] = "execução"
    max_units: Annotated[int, Field(ge=1, le=10_000)] = 1
    max_input_chars: Annotated[int, Field(ge=100, le=50_000_000)]
    free_quota_eligible: bool = True
    sponsor_eligible: bool = True
    completion_rule_pt: Annotated[str, Field(min_length=10, max_length=600)]
    delivers_pt: Annotated[str, Field(min_length=10, max_length=600)]
    status: Literal["active", "hypothesis", "planned", "retired"]
    note: Annotated[str, Field(min_length=10, max_length=600)]


class PackIn(In):
    code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.]{2,40}$")]
    name_pt: Annotated[str, Field(min_length=3, max_length=80)]
    credits: Annotated[int, Field(ge=1, le=1_000_000)]
    price_cents: Annotated[int, Field(ge=1, le=100_000_000)]
    validity_days: Annotated[int, Field(ge=1, le=3650)] = 365
    status: Literal["active", "hypothesis", "retired"]
    note: Annotated[str, Field(min_length=20, max_length=600)]


class QuotaPolicyIn(In):
    label_pt: Annotated[str, Field(min_length=3, max_length=120)]
    scope: Literal["welcome", "periodic", "campaign", "kind", "demo", "institutional"]
    applies_to_kinds: list[Literal["osc", "company", "government", "individual", "provider"]]
    credits: Annotated[int, Field(ge=1, le=100_000)]
    period: Literal["once", "month"] = "once"
    validity_days: Annotated[int | None, Field(ge=1, le=3650)] = None
    max_grants_per_org: Annotated[int, Field(ge=1, le=100)] = 1
    one_per_user: bool = True
    valid_until: date | None = None
    active: bool = True
    note: Annotated[str, Field(min_length=20, max_length=600)]


# ------------------------------------------------------------------------------------------------ central e catálogo
@route("GET", "/v1/ai/center", min_role="viewer", tags=T,
       summary="Central de IA: saldo por lote, cotas, operações com preço e elegibilidade, histórico, pedidos, patrocínios, regras")
def center(ctx: Ctx):
    return AC.center(ctx)


@route("GET", "/v1/ai/operations", min_role="viewer", tags=T, summary="Catálogo versionado de operações de IA (vigentes)")
def operations(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT code, version, name_pt, description_pt, purpose_pt, category, tier, allowed_kinds, min_role, provider_mode, data_requirements_pt,"
                       "       funding_modes, credits_base, credits_per_unit, unit_label_pt, max_units, max_input_chars, free_quota_eligible,"
                       "       sponsor_eligible, completion_rule_pt, failure_policy, delivers_pt, status, note"
                       "  FROM ai_operations WHERE status IN ('active','hypothesis','planned') ORDER BY category, code")
    return {"items": rows, "categories": {"A": "Assistência leve", "B": "Assistência contextual", "C": "Análise avançada individual",
                                          "D": "Originalidade e similaridade", "E": "Processamento em lote", "F": "Institucional e API"}}


@route("POST", "/v1/ai/preview", body=PreviewIn, min_role="viewer", rate=("ai_ip", 120, 3600), tags=T,
       summary="Prévia ANTES de executar: o que será feito, créditos, custo estimado, quem paga, saldo, limites — ou por que não dá")
def preview(ctx: Ctx, body: PreviewIn):
    with ctx.tx() as c:
        return UC.preview(c, ctx, body.operation_code, units=body.units, input_chars=body.input_chars, project_id=body.project_id)


@route("GET", "/v1/ai/executions", min_role="viewer", query=Pagination, tags=T, summary="Histórico de execuções de IA da organização")
def executions(ctx: Ctx, q: Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT * FROM ai_executions WHERE org_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page([UC._row(r) for r in rows], q.limit, q.offset)


@route("GET", "/v1/ai/executions/{execution_id}", min_role="viewer", tags=T, summary="Uma execução, com a trilha de estados")
def execution(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        row = c.one("SELECT * FROM ai_executions WHERE id = $1 AND org_id = $2", ctx.path["execution_id"], ctx.org_id)
        if not row:
            raise not_found("Execução de IA")
        ev = c.query("SELECT from_state, to_state, note, created_at FROM ai_execution_events WHERE execution_id = $1 ORDER BY id", row["id"])
    return UC._row(row) | {"events": ev}


@route("POST", "/v1/ai/executions/{execution_id}/cancel", min_role="member", rate=("ai_ip", 120, 3600), tags=T, summary="Cancela uma execução ainda não iniciada (nada é cobrado)")
def cancel_execution(ctx: Ctx):
    with ctx.tx() as c:
        return UC.cancel(c, ctx, ctx.path["execution_id"])


# ------------------------------------------------------------------------------------------------ créditos e pedidos
@route("GET", "/v1/ai/credit-packs", min_role="viewer", tags=T, summary="Pacotes de crédito (status diz se o preço é hipótese ou vigente) e modo de venda")
def credit_packs(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        packs = c.query("SELECT code, version, name_pt, credits, price_cents, currency, validity_days, status, note FROM ai_credit_packs"
                        " WHERE status IN ('active','hypothesis') ORDER BY credits")
        sale = AC._sale_mode(c, ctx.settings)
    return {"items": packs, "sale": sale, "terms": AC.CREDIT_TERMS_V1}


@route("POST", "/v1/ai/credit-orders", body=CreditOrderIn, min_role="admin", status=201, rate=("ai_order_ip", 20, 3600), tags=T,
       summary="Pedido de créditos por PIX (modo real: cobrança própria aguardando confirmação; modo piloto: sem pagamento)")
def create_order(ctx: Ctx, body: CreditOrderIn):
    return AC.create_order(ctx, pack_code=body.pack_code, accept_terms=body.accept_terms)


@route("GET", "/v1/ai/credit-orders", min_role="viewer", query=Pagination, tags=T, summary="Pedidos de crédito da organização")
def orders(ctx: Ctx, q: Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, credits, amount_cents, currency, mode, state, confirmed_via, expires_at, created_at, updated_at"
                       "  FROM ai_credit_orders WHERE org_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/ai/credit-orders/{order_id}", min_role="viewer", tags=T, summary="Um pedido de crédito com a instrução de pagamento (ou o aviso de piloto)")
def order(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return AC.order_detail(c, ctx, ctx.path["order_id"])


@route("POST", "/v1/ai/credit-orders/{order_id}/cancel", min_role="admin", rate=("ai_order_ip", 20, 3600), tags=T, summary="Cancela um pedido não pago")
def cancel_order(ctx: Ctx):
    return AC.cancel_order(ctx, ctx.path["order_id"])


# ------------------------------------------------------------------------------------------------ webhook de pagamento (provedor real)
@route("POST", "/v1/webhooks/payments/{provider}", auth="none", raw=True, raw_body=True, rate=("pay_webhook_ip", 600, 60), tags=("billing",),
       summary="Webhook do provedor de pagamento: assinatura HMAC conferida, evento deduplicado, pedido de crédito creditado uma vez")
def payment_webhook(ctx: Ctx, payload: bytes):
    """Quem confirma pagamento é o provedor, por evento assinado. Sem segredo configurado a rota responde 404
    (como o webhook de integração responde a conexão desconhecida): não existe "aceitar sem conferir". Evento com
    assinatura inválida é gravado para auditoria e NÃO produz efeito."""
    from ..services.donations import verify_timestamped, webhook_secret
    secret = webhook_secret(ctx.settings, "payment_webhook_secret")
    provider = ctx.path["provider"][:40]
    if not secret:
        return JSONResponse({"status": "rejected", "code": "webhook_not_configured",
                             "note": "PAYMENT_WEBHOOK_SECRET ausente ou curto: nenhum evento de pagamento é aceito"}, status_code=404)
    # v0.35.0 (auditoria, PAY-01): assinatura com carimbo de tempo (t=…,v1=…) e janela de 300 s; segredo próprio deste endpoint
    verified = verify_timestamped(secret, payload, ctx.request.headers.get("x-impacto-signature", ""))
    try:
        data = json.loads(payload or b"{}")
    except ValueError:
        return JSONResponse({"status": "rejected", "code": "bad_json"}, status_code=400)
    event_id = str(data.get("event_id") or "")[:120]
    if not event_id:
        return JSONResponse({"status": "rejected", "code": "missing_event_id"}, status_code=400)
    with ctx.system_tx() as c:
        out = AC.apply_payment_webhook(c, provider=provider, event_id=event_id, event_type=str(data.get("type") or "")[:60],
                                       charge_id=(str(data.get("charge_id")) if data.get("charge_id") else None),
                                       amount_cents=data.get("amount_cents"), payload=data, signature_verified=verified)
    code = 200 if verified else 202
    return JSONResponse({"status": "applied" if out.get("credited") else ("duplicate" if out.get("duplicate") else ("rejected_signature" if not verified else "recorded")),
                         "credited": bool(out.get("credited")), "note": out.get("note")}, status_code=code)


# ------------------------------------------------------------------------------------------------ patrocínio
@route("POST", "/v1/ai/sponsorships", body=SponsorshipIn, min_role="admin", kinds=("company", "government", "osc"), status=201, rate=("ai_order_ip", 20, 3600), tags=T,
       summary="Cria um patrocínio de uso de IA: compromete créditos do patrocinador para organizações elegíveis")
def create_sponsorship(ctx: Ctx, body: SponsorshipIn):
    return AC.create_sponsorship(ctx, body)


@route("GET", "/v1/ai/sponsorships/{sponsorship_id}", min_role="viewer", tags=T, summary="Prestação de contas agregada de um patrocínio (só o patrocinador)")
def sponsorship(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return AC.sponsorship_report(c, ctx, ctx.path["sponsorship_id"])


@route("POST", "/v1/ai/sponsorships/{sponsorship_id}/close", min_role="admin", rate=("ai_order_ip", 20, 3600), tags=T, summary="Encerra o patrocínio e devolve o crédito não usado ao patrocinador")
def close_sponsorship(ctx: Ctx):
    return AC.close_sponsorship(ctx, ctx.path["sponsorship_id"])


# ------------------------------------------------------------------------------------------------ similaridade
@route("POST", "/v1/projects/{project_id}/similarity", body=SimilarityIn, min_role="viewer", rate=("ai_ip", 60, 3600), tags=T,
       summary="Originalidade, comparação de dois, conjunto, complementaridade ou sobreposição de despesas — pela camada de uso (prévia, custeio, cobrança só em sucesso)")
def analyze(ctx: Ctx, body: SimilarityIn):
    return SIM.analyze(ctx, kind=body.kind, subject_id=ctx.path["project_id"], compared_ids=body.compared_project_ids,
                       idempotency_key=body.idempotency_key)


@route("GET", "/v1/similarity/analyses", min_role="viewer", query=Pagination, tags=T, summary="Análises de similaridade da organização")
def analyses(ctx: Ctx, q: Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT a.id::text AS id, a.kind, a.subject_project_id::text AS subject_project_id, p.title AS subject_title,"
                       "       cardinality(a.compared_project_ids) AS compared_count, a.confidence, a.hidden_count, a.engine_version, a.created_at,"
                       "       (SELECT count(*) FROM similarity_disputes d WHERE d.analysis_id = a.id AND d.status = 'open') AS open_disputes"
                       "  FROM similarity_analyses a JOIN projects p ON p.id = a.subject_project_id"
                       " WHERE a.org_id = $1 ORDER BY a.created_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/similarity/analyses/{analysis_id}", min_role="viewer", tags=T, summary="Uma análise completa, com execução e contestações")
def analysis(ctx: Ctx):
    return SIM.get(ctx, ctx.path["analysis_id"])


@route("POST", "/v1/similarity/analyses/{analysis_id}/dispute", body=DisputeIn, min_role="member", status=201, rate=("ai_ip", 60, 3600), tags=T,
       summary="Contesta uma análise (vai para revisão humana da administração)")
def dispute(ctx: Ctx, body: DisputeIn):
    return SIM.dispute(ctx, ctx.path["analysis_id"], body.reason)


# ------------------------------------------------------------------------------------------------ administração
@route("GET", "/v1/admin/ai/finance", auth="admin", permission="finance.read", tags=("admin",),
       summary="Painel financeiro da IA: execuções por categoria, custo medido × estimado, créditos vendidos/concedidos/consumidos, obrigações, margem, alertas")
def admin_finance(ctx: Ctx):
    return AC.admin_finance(ctx)


@route("GET", "/v1/admin/ai/credit-orders", auth="admin", permission="billing.read", query=Pagination, tags=("admin",), summary="Pedidos de crédito de todas as organizações")
def admin_orders(ctx: Ctx, q: Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT o.id::text AS id, g.legal_name AS org_name, o.credits, o.amount_cents, o.mode, o.state, o.confirmed_via, o.paid_reference, o.created_at"
                       "  FROM ai_credit_orders o JOIN organizations g ON g.id = o.org_id ORDER BY o.created_at DESC LIMIT $1 OFFSET $2", q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/admin/ai/credit-orders/{order_id}/confirm", auth="admin", permission="billing.write", body=OrderConfirmIn, tags=("admin",),
       summary="Conciliação manual de um pedido REAL: referência do extrato obrigatória; credita compra uma vez")
def admin_confirm(ctx: Ctx, body: OrderConfirmIn):
    return AC.admin_confirm_order(ctx, ctx.path["order_id"], reference=body.reference, note=body.note)


@route("POST", "/v1/admin/ai/credit-orders/{order_id}/approve-pilot", auth="admin", permission="billing.write", body=PilotApproveIn, tags=("admin",),
       summary="Aprova um pedido PILOTO como concessão promocional (sem pagamento; nunca receita)")
def admin_pilot(ctx: Ctx, body: PilotApproveIn):
    return AC.admin_approve_pilot(ctx, ctx.path["order_id"], note=body.note)


@route("POST", "/v1/admin/ai/operations", auth="admin", permission="finance.approve", body=OperationIn, status=201, tags=("admin",),
       summary="Publica uma versão nova de operação do catálogo (a anterior fica; execuções antigas guardam a sua versão)")
def admin_operation(ctx: Ctx, body: OperationIn):
    with ctx.tx() as c:
        prev = c.one("SELECT (ai_operation_current($1)).version AS version", body.code)
        version = (prev["version"] or 0) + 1 if prev else 1
        if version > 1:
            c.run("UPDATE ai_operations SET status = 'retired' WHERE code = $1 AND status <> 'retired'", body.code)
        row = c.one("INSERT INTO ai_operations(code, version, name_pt, description_pt, purpose_pt, category, tier, allowed_kinds, min_role,"
                    " data_requirements_pt, provider_mode, funding_modes, credits_base, credits_per_unit, unit_label_pt, max_units, max_input_chars,"
                    " free_quota_eligible, sponsor_eligible, completion_rule_pt, delivers_pt, status, note, created_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24) RETURNING code, version, status",
                    body.code, version, body.name_pt, body.description_pt, body.purpose_pt, body.category, body.tier, body.allowed_kinds, body.min_role,
                    body.data_requirements_pt, body.provider_mode, body.funding_modes, body.credits_base, body.credits_per_unit, body.unit_label_pt,
                    body.max_units, body.max_input_chars, body.free_quota_eligible, body.sponsor_eligible, body.completion_rule_pt, body.delivers_pt,
                    body.status, body.note, ctx.user_id)
        ctx.audit(c, "ai.operation_published", "ai_operation", f"{body.code}@{version}", {"credits_base": body.credits_base, "status": body.status})
    return dict(row) | {"note": "Versão publicada. Execuções já autorizadas mantêm a versão e o preço com que foram autorizadas."}


@route("POST", "/v1/admin/ai/credit-packs", auth="admin", permission="finance.approve", body=PackIn, status=201, tags=("admin",),
       summary="Publica uma versão nova de pacote de créditos (preço em centavos; status diz se é hipótese)")
def admin_pack(ctx: Ctx, body: PackIn):
    with ctx.tx() as c:
        prev = c.scalar("SELECT max(version) FROM ai_credit_packs WHERE code = $1", body.code)
        if prev:
            c.run("UPDATE ai_credit_packs SET status = 'retired' WHERE code = $1 AND status <> 'retired'", body.code)
        row = c.one("INSERT INTO ai_credit_packs(code, version, name_pt, credits, price_cents, validity_days, status, note, created_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9) RETURNING code, version, status",
                    body.code, (prev or 0) + 1, body.name_pt, body.credits, body.price_cents, body.validity_days, body.status, body.note, ctx.user_id)
        ctx.audit(c, "ai.pack_published", "ai_credit_pack", f"{body.code}@{row['version']}", {"price_cents": body.price_cents, "credits": body.credits, "status": body.status})
    return dict(row)


@route("PUT", "/v1/admin/ai/quota-policies/{key}", auth="admin", permission="finance.approve", body=QuotaPolicyIn, tags=("admin",),
       summary="Cria ou altera uma política de cota gratuita (com trilha de auditoria)")
def admin_quota(ctx: Ctx, body: QuotaPolicyIn):
    key = ctx.path["key"]
    if not key or len(key) > 60:
        raise unprocessable("Chave inválida", code="bad_key")
    with ctx.tx() as c:
        before = c.one("SELECT credits, period, active FROM ai_quota_policies WHERE key = $1", key)
        row = c.one("INSERT INTO ai_quota_policies(key, label_pt, scope, applies_to_kinds, credits, period, validity_days, max_grants_per_org, one_per_user,"
                    " valid_until, active, note, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)"
                    " ON CONFLICT (key) DO UPDATE SET label_pt = EXCLUDED.label_pt, scope = EXCLUDED.scope, applies_to_kinds = EXCLUDED.applies_to_kinds,"
                    " credits = EXCLUDED.credits, period = EXCLUDED.period, validity_days = EXCLUDED.validity_days, max_grants_per_org = EXCLUDED.max_grants_per_org,"
                    " one_per_user = EXCLUDED.one_per_user, valid_until = EXCLUDED.valid_until, active = EXCLUDED.active, note = EXCLUDED.note"
                    " RETURNING key, credits, period, active",
                    key, body.label_pt, body.scope, body.applies_to_kinds, body.credits, body.period, body.validity_days, body.max_grants_per_org,
                    body.one_per_user, body.valid_until, body.active, body.note, ctx.user_id)
        ctx.audit(c, "ai.quota_policy_set", "ai_quota_policy", key, {"credits": body.credits, "active": body.active},
                  before=dict(before) if before else None, after={"credits": body.credits, "period": body.period, "active": body.active})
    return dict(row) | {"note": "Cotas já concedidas não mudam; a política vale para concessões futuras."}


@route("GET", "/v1/admin/ai/disputes", auth="admin", permission="support.read", query=Pagination, tags=("admin",), summary="Contestações de similaridade para revisão humana")
def admin_disputes(ctx: Ctx, q: Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT d.id::text AS id, d.analysis_id::text AS analysis_id, g.legal_name AS org_name, d.status, d.reason, d.reviewer_note, d.created_at, d.reviewed_at"
                       "  FROM similarity_disputes d JOIN organizations g ON g.id = d.org_id ORDER BY (d.status = 'open') DESC, d.created_at DESC LIMIT $1 OFFSET $2",
                       q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/admin/ai/disputes/{dispute_id}/review", auth="admin", permission="support.write", body=DisputeReviewIn, tags=("admin",),
       summary="Revisão humana de uma contestação: mantida ou corrigida, com nota")
def admin_review_dispute(ctx: Ctx, body: DisputeReviewIn):
    with ctx.tx() as c:
        d = c.one("SELECT id, status FROM similarity_disputes WHERE id = $1", ctx.path["dispute_id"])
        if not d:
            raise not_found("Contestação")
        if d["status"] != "open":
            raise ApiError(409, "dispute_closed", "Esta contestação já foi revisada")
        c.run("UPDATE similarity_disputes SET status = $2, reviewer_note = $3, reviewed_by = $4, reviewed_at = now() WHERE id = $1",
              d["id"], body.outcome, body.reviewer_note, ctx.user_id)
        ctx.audit(c, "ai.similarity_dispute_reviewed", "similarity_dispute", d["id"], {"outcome": body.outcome})
    return {"id": str(d["id"]), "status": body.outcome}
