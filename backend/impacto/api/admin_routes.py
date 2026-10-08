"""Administração da plataforma (exige is_platform_admin + MFA verificado na sessão). Todas as ações são auditadas."""
from __future__ import annotations

import secrets
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import Field

from ..db.pq import Json
from ..http import ApiError, Ctx, not_found, page, route
from ..services import compliance
from . import schemas as S
from .billing_routes import ALPHABET, code_hash

T = ("admin",)


def A(method, path, **kw):
    return route(method, path, auth="admin", tags=T, **kw)


@A("GET", "/v1/admin/overview", summary="Métricas operacionais da plataforma")
def overview(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {
            "organizations": c.query("SELECT kind, compliance_status, count(*) AS n FROM organizations GROUP BY 1, 2 ORDER BY 1, 2"),
            "users": c.one("SELECT count(*) AS total, count(*) FILTER (WHERE status = 'active') AS active,"
                           " count(*) FILTER (WHERE last_login_at > now() - interval '30 days') AS active_30d,"
                           " count(*) FILTER (WHERE mfa_enabled_at IS NOT NULL) AS with_mfa FROM users"),
            "calls": c.query("SELECT source_type, status, count(*) AS n FROM calls GROUP BY 1, 2"),
            "projects": c.query("SELECT status, count(*) AS n FROM projects GROUP BY 1"),
            "applications": c.query("SELECT origin, status, count(*) AS n FROM applications GROUP BY 1, 2"),
            "funding": c.one("SELECT coalesce(sum(amount_cents) FILTER (WHERE status <> 'cancelled'),0) AS committed_cents,"
                             " coalesce(sum(amount_cents) FILTER (WHERE status = 'confirmed'),0) AS confirmed_cents FROM commitments"),
            "queues": {"compliance_open": c.scalar("SELECT count(*) FROM compliance_reviews WHERE status = 'open'"),
                       "reports_open": c.scalar("SELECT count(*) FROM reports WHERE status IN"
                                                " ('reported','under_review','information_requested')"),
                       "credentials_pending": c.scalar("SELECT count(*) FROM professional_credentials WHERE verification_status IN ('self_declared','document_submitted')"),
                       "fiscal_pending": c.scalar("SELECT count(*) FROM fiscal_rules WHERE status = 'pending_review'"),
                       "documents_pending_scan": c.scalar("SELECT count(*) FROM documents WHERE status = 'pending_scan' AND deleted_at IS NULL")},
            "grants": c.query("SELECT plan_key, source, count(*) AS n FROM entitlement_grants WHERE revoked_at IS NULL AND (ends_at IS NULL OR ends_at > now()) GROUP BY 1, 2"),
            "contracts": c.query("SELECT consent_status, count(*) AS n FROM offer_acceptances WHERE revoked_at IS NULL GROUP BY 1"),
            "ai_usage_30d": c.query("SELECT feature, provider, count(*) AS n FROM ai_usage WHERE created_at > now() - interval '30 days' GROUP BY 1, 2"),
        }


class OrgQ(S.Pagination):
    q: str | None = None
    kind: str | None = None
    compliance: str | None = None


@A("GET", "/v1/admin/organizations", permission="admin.organizations.read", query=OrgQ)
def orgs(ctx: Ctx, q: OrgQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, kind, legal_name, cnpj, uf, status, compliance_status, compliance_risk, created_at,"
                       " (SELECT count(*) FROM memberships m WHERE m.org_id = o.id) AS members FROM organizations o"
                       " WHERE ($1::text IS NULL OR legal_name ILIKE '%' || $1 || '%' OR cnpj = $1) AND ($2::text IS NULL OR kind = $2)"
                       " AND ($3::text IS NULL OR compliance_status = $3) ORDER BY created_at DESC LIMIT $4 OFFSET $5",
                       q.q, q.kind, q.compliance, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


class OrgStatusIn(S.In):
    status: Literal["active", "suspended", "closed"]
    reason: Annotated[str, Field(min_length=3, max_length=1000)]


@A("POST", "/v1/admin/organizations/{org_id}/status", body=OrgStatusIn)
def org_status(ctx: Ctx, body: OrgStatusIn):
    with ctx.tx() as c:
        if not c.run("UPDATE organizations SET status = $2 WHERE id = $1", ctx.path["org_id"], body.status):
            raise not_found("Organização")
        ctx.audit(c, "admin.org_status", "organization", ctx.path["org_id"], {"status": body.status, "reason": body.reason}, org_id=ctx.path["org_id"])
    return {"status": body.status}


@A("POST", "/v1/admin/organizations/{org_id}/compliance-checks", summary="Executa verificações automáticas de compliance")
def run_checks(ctx: Ctx):
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM organizations WHERE id = $1", ctx.path["org_id"]):
            raise not_found("Organização")
        return compliance.run_checks(c, ctx.path["org_id"], ctx.user_id)


@A("GET", "/v1/admin/compliance-reviews", permission="compliance.read", query=S.Pagination)
def compliance_queue(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT r.id::text AS id, r.status, r.risk_level, r.created_at, o.id::text AS org_id, o.legal_name, o.kind, o.cnpj,"
                       " (SELECT json_agg(json_build_object('type', x.check_type, 'status', x.status, 'details', x.details))"
                       "   FROM (SELECT DISTINCT ON (check_type) * FROM compliance_checks k WHERE k.org_id = o.id ORDER BY check_type, checked_at DESC) x) AS checks"
                       " FROM compliance_reviews r JOIN organizations o ON o.id = r.org_id WHERE r.status = 'open' ORDER BY r.created_at"
                       " LIMIT $1 OFFSET $2", q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


class DecideIn(S.In):
    decision: Literal["approved", "rejected", "info_requested"]
    note: Annotated[str | None, Field(max_length=4000)] = None


@A("POST", "/v1/admin/compliance-reviews/{review_id}/decide", body=DecideIn)
def compliance_decide(ctx: Ctx, body: DecideIn):
    return compliance.decide(ctx, ctx.path["review_id"], body.decision, body.note)


class UserQ(S.Pagination):
    q: str | None = None


@A("GET", "/v1/admin/users", permission="admin.users.read", query=UserQ)
def users(ctx: Ctx, q: UserQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, email::text AS email, full_name, status, is_platform_admin, email_verified_at IS NOT NULL AS verified,"
                       " mfa_enabled_at IS NOT NULL AS mfa, last_login_at, created_at FROM users"
                       " WHERE ($1::text IS NULL OR email ILIKE '%' || $1 || '%' OR full_name ILIKE '%' || $1 || '%')"
                       " ORDER BY created_at DESC LIMIT $2 OFFSET $3", q.q, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


class UserStatusIn(S.In):
    status: Literal["active", "disabled"]
    reason: Annotated[str, Field(min_length=3, max_length=1000)]


@A("POST", "/v1/admin/users/{user_id}/status", body=UserStatusIn, summary="Ativa/desativa usuário (revoga sessões ao desativar)")
def user_status(ctx: Ctx, body: UserStatusIn):
    if ctx.path["user_id"] == ctx.user_id:
        raise ApiError(409, "self_action", "Não é possível alterar o próprio status")
    with ctx.tx() as c:
        if not c.run("UPDATE users SET status = $2 WHERE id = $1 AND status <> 'deleted'", ctx.path["user_id"], body.status):
            raise not_found("Usuário")
        if body.status == "disabled":
            c.run("UPDATE sessions SET revoked_at = now(), revoke_reason = 'admin_disabled' WHERE user_id = $1 AND revoked_at IS NULL", ctx.path["user_id"])
        ctx.audit(c, "admin.user_status", "user", ctx.path["user_id"], {"status": body.status, "reason": body.reason}, org_id=None)
    return {"status": body.status}


class CredQ(S.Pagination):
    status: str | None = None


@A("GET", "/v1/admin/credentials", query=CredQ)
def credentials(ctx: Ctx, q: CredQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT pc.id::text AS id, pc.council, pc.number, pc.uf, pc.holder_name, pc.valid_until, pc.verification_status,"
                       " pc.document_id::text AS document_id, o.legal_name, u.email::text AS email FROM professional_credentials pc"
                       " JOIN organizations o ON o.id = pc.org_id JOIN users u ON u.id = pc.user_id"
                       " WHERE ($1::text IS NULL OR pc.verification_status = $1) ORDER BY pc.created_at LIMIT $2 OFFSET $3",
                       q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


class CredDecisionIn(S.In):
    status: Literal["verified", "rejected", "expired"]
    note: Annotated[str, Field(min_length=3, max_length=1000)]


@A("POST", "/v1/admin/credentials/{credential_id}/verify", body=CredDecisionIn,
   summary="Verifica credencial profissional (registre a fonte consultada, ex.: cadastro público do conselho, e a data)")
def verify_credential(ctx: Ctx, body: CredDecisionIn):
    with ctx.tx() as c:
        n = c.run("UPDATE professional_credentials SET verification_status = $2, verification_note = $3, verified_by = $4, verified_at = now()"
                  " WHERE id = $1", ctx.path["credential_id"], body.status, body.note, ctx.user_id)
        if not n:
            raise not_found("Credencial")
        ctx.audit(c, "admin.credential_verified", "credential", ctx.path["credential_id"], {"status": body.status}, org_id=None)
    return {"status": body.status}


# ------------------------------------------------------------------------------------------------ curadoria de editais
@A("POST", "/v1/admin/calls", body=S.CallIn, status=201, summary="Cadastra edital/fundo externo curado (com URL da fonte oficial)")
def curated_call(ctx: Ctx, body: S.CallIn):
    if not body.url:
        raise ApiError(422, "source_required", "Editais curados exigem a URL da fonte oficial")
    if not body.funder_name:
        raise ApiError(422, "validation_error", "Informe o financiador/órgão")
    d = body.model_dump()
    with ctx.tx() as c:
        cid = c.scalar(
            "INSERT INTO calls(source_type, sphere, instrument, funder_name, title, summary, description, url, causes, ods, territories,"
            " eligible_org_types, budget_total_cents, ticket_min_cents, ticket_max_cents, counterpart_pct, min_org_age_months,"
            " required_document_types, required_certifications, requirements, steps_template, opens_at, closes_at, status,"
            " managed_on_platform, last_verified_at, verified_by, created_by, funding_modality, accepted_legal_natures, min_maturity)"
            " VALUES ('curated',$1,$2,$3,$4,$5,$6,$7,$8::text[],$9::smallint[],$10::text[],$11::text[],$12::bigint,$13::bigint,$14::bigint,"
            " $15::numeric,$16::int,$17::text[],$18::text[],$19::jsonb,$20::jsonb,$21::timestamptz,$22::timestamptz,$23,false, now(), $24, $24, $25, $26::text[], $27::smallint)"
            " RETURNING id::text",
            d["sphere"], d["instrument"], d["funder_name"], d["title"], d["summary"], d["description"], d["url"], d["causes"], d["ods"],
            d["territories"], d["eligible_org_types"], d["budget_total_cents"], d["ticket_min_cents"], d["ticket_max_cents"], d["counterpart_pct"],
            d["min_org_age_months"], d["required_document_types"], d["required_certifications"], Json(d["requirements"]),
            Json(d["steps_template"]), d["opens_at"], d["closes_at"], d["status"], ctx.user_id, d["funding_modality"], d["accepted_legal_natures"], d["min_maturity"])
        ctx.audit(c, "admin.call_curated", "call", cid, {"sphere": d["sphere"], "url": d["url"]}, org_id=None)
    return {"id": cid}


@A("POST", "/v1/admin/calls/{call_id}/verify", summary="Registra conferência do edital na fonte oficial (data/responsável)")
def verify_call(ctx: Ctx):
    with ctx.tx() as c:
        if not c.run("UPDATE calls SET last_verified_at = now(), verified_by = $2 WHERE id = $1", ctx.path["call_id"], ctx.user_id):
            raise not_found("Edital")
        ctx.audit(c, "admin.call_verified", "call", ctx.path["call_id"], org_id=None)
    return {"verified": True}


class CallStatusIn(S.In):
    status: Literal["draft", "open", "closed", "archived", "suspended"]


@A("POST", "/v1/admin/calls/{call_id}/status", body=CallStatusIn)
def call_status(ctx: Ctx, body: CallStatusIn):
    with ctx.tx() as c:
        if not c.run("UPDATE calls SET status = $2 WHERE id = $1", ctx.path["call_id"], body.status):
            raise not_found("Edital")
        ctx.audit(c, "admin.call_status", "call", ctx.path["call_id"], {"status": body.status}, org_id=None)
    return {"status": body.status}


class SourceIn(S.In):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    kind: Literal["json_feed", "csv_feed", "rss"]
    url: Annotated[str, Field(pattern=r"^https://", max_length=500)]
    sphere: Literal["private", "federal", "state", "municipal", "local", "international"]
    terms_note: Annotated[str, Field(min_length=10, max_length=2000)]
    mapping: dict = Field(default_factory=dict)
    active: bool = False


@A("GET", "/v1/admin/call-sources")
def list_sources(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, name, kind, url, sphere, active, terms_note, last_run_at, last_status, last_error"
                                 " FROM call_sources ORDER BY name")}


@A("POST", "/v1/admin/call-sources", body=SourceIn, status=201,
   summary="Cadastra fonte de importação (exige registro da verificação de termos de uso/licença da fonte)")
def add_source(ctx: Ctx, body: SourceIn):
    with ctx.tx() as c:
        sid = c.scalar("INSERT INTO call_sources(name, kind, url, sphere, terms_note, mapping, active) VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::bool)"
                       " RETURNING id::text", body.name, body.kind, body.url, body.sphere, body.terms_note, Json(body.mapping), body.active)
        ctx.audit(c, "admin.call_source_created", "call_source", sid, {"url": body.url}, org_id=None)
    return {"id": sid}


@A("POST", "/v1/admin/call-sources/{source_id}/run", summary="Importa agora (feed configurado)")
def run_source(ctx: Ctx):
    from ..jobs import import_source
    with ctx.tx(readonly=True) as c:
        s = c.one("SELECT * FROM call_sources WHERE id = $1", ctx.path["source_id"])
    if not s:
        raise not_found("Fonte")
    out = import_source(ctx.app, s)
    with ctx.tx() as c:
        ctx.audit(c, "call_source.run", "call_source", ctx.path["source_id"],
                  {"imported": out.get("imported"), "source": s.get("name")}, org_id=None)
    return out


# ------------------------------------------------------------------------------------------------ regras fiscais
class FiscalRuleIn(S.In):
    code: Annotated[str, Field(pattern=r"^[A-Z0-9-]{3,60}$")]
    version: Annotated[str, Field(min_length=1, max_length=40)]
    name: Annotated[str, Field(min_length=3, max_length=200)]
    mechanism: Annotated[str, Field(min_length=2, max_length=60)]
    jurisdiction: Literal["federal", "state", "municipal"]
    uf: S.UF | None = None
    taxpayer_types: list[Literal["pj", "pf"]] = Field(default_factory=lambda: ["pj"])
    taxpayer_regimes: list[Literal["lucro_real", "lucro_presumido", "simples", "isenta"]] = Field(default_factory=list)
    tax_base: Annotated[str, Field(min_length=2, max_length=60)]
    limit_pct: Annotated[float | None, Field(ge=0, le=100)] = None
    combined_limit_group: str | None = None
    limit_note: Annotated[str | None, Field(max_length=2000)] = None
    causes: list[S.Slug] = Field(default_factory=list)
    requirements: list[dict] = Field(default_factory=list)
    project_requirements: list[dict] = Field(default_factory=list)
    effective_from: date | None = None
    effective_to: date | None = None
    source_citation: Annotated[str, Field(min_length=5, max_length=500)]
    source_url: Annotated[str, Field(pattern=r"^https://", max_length=500)]
    source_consulted_on: date
    notes: Annotated[str | None, Field(max_length=4000)] = None


@A("GET", "/v1/admin/fiscal-rules", permission="fiscal.read")
def list_rules(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, code, version, name, status, jurisdiction, limit_pct::float AS limit_pct, source_citation,"
                                 " source_url, source_consulted_on, effective_from, effective_to, approved_by_1::text AS approved_by_1,"
                                 " approved_by_2::text AS approved_by_2, approved_at, notes, limit_note FROM fiscal_rules ORDER BY code, version")}


@A("POST", "/v1/admin/fiscal-rules", body=FiscalRuleIn, status=201, summary="Cadastra regra (nasce rascunho; exige fonte oficial e data de consulta)")
def create_rule(ctx: Ctx, body: FiscalRuleIn):
    d = body.model_dump()
    with ctx.tx() as c:
        rid = c.scalar("INSERT INTO fiscal_rules(code, version, name, mechanism, jurisdiction, uf, taxpayer_types, taxpayer_regimes, tax_base, limit_pct,"
                       " combined_limit_group, limit_note, causes, requirements, project_requirements, effective_from, effective_to, source_citation,"
                       " source_url, source_consulted_on, notes, status, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7::text[],$8::text[],$9,$10::numeric,$11,$12,"
                       " $13::text[],$14::jsonb,$15::jsonb,$16::date,$17::date,$18,$19,$20::date,$21,'draft',$22) RETURNING id::text",
                       d["code"], d["version"], d["name"], d["mechanism"], d["jurisdiction"], d["uf"], d["taxpayer_types"], d["taxpayer_regimes"],
                       d["tax_base"], d["limit_pct"], d["combined_limit_group"], d["limit_note"], d["causes"], Json(d["requirements"]),
                       Json(d["project_requirements"]), d["effective_from"], d["effective_to"], d["source_citation"], d["source_url"],
                       d["source_consulted_on"], d["notes"], ctx.user_id)
        ctx.audit(c, "fiscal.rule_created", "fiscal_rule", rid, {"code": d["code"], "version": d["version"]}, org_id=None)
    return {"id": rid, "status": "draft"}


class RuleActionIn(S.In):
    action: Literal["submit", "approve", "retire", "return_to_draft"]
    source_consulted_on: date | None = None
    note: Annotated[str | None, Field(max_length=2000)] = None


@A("POST", "/v1/admin/fiscal-rules/{rule_id}/action", body=RuleActionIn,
   summary="Fluxo: draft → pending_review → approved (dois aprovadores distintos) → retired")
def rule_action(ctx: Ctx, body: RuleActionIn):
    with ctx.tx() as c:
        r = c.one("SELECT id::text AS id, status, approved_by_1::text AS a1, source_url, source_consulted_on FROM fiscal_rules WHERE id = $1 FOR UPDATE",
                  ctx.path["rule_id"])
        if not r:
            raise not_found("Regra")
        if body.action == "submit":
            if r["status"] != "draft":
                raise ApiError(409, "invalid_transition", "Somente rascunhos são enviados à revisão")
            if not r["source_url"] or not (r["source_consulted_on"] or body.source_consulted_on):
                raise ApiError(422, "source_required", "Informe a URL oficial e a data de consulta da fonte")
            c.run("UPDATE fiscal_rules SET status = 'pending_review', source_consulted_on = coalesce($2::date, source_consulted_on) WHERE id = $1",
                  r["id"], body.source_consulted_on)
        elif body.action == "approve":
            if r["status"] != "pending_review":
                raise ApiError(409, "invalid_transition", "Regra precisa estar em revisão")
            if r["a1"] is None:
                c.run("UPDATE fiscal_rules SET approved_by_1 = $2 WHERE id = $1", r["id"], ctx.user_id)
            elif r["a1"] == ctx.user_id:
                raise ApiError(409, "second_approver_required", "A segunda aprovação deve ser feita por outro revisor")
            else:
                c.run("UPDATE fiscal_rules SET approved_by_2 = $2, status = 'approved', approved_at = now() WHERE id = $1", r["id"], ctx.user_id)
        elif body.action == "retire":
            c.run("UPDATE fiscal_rules SET status = 'retired' WHERE id = $1", r["id"])
        elif body.action == "return_to_draft":
            if r["status"] != "pending_review":
                raise ApiError(409, "invalid_transition", "Somente regras em revisão retornam ao rascunho")
            c.run("UPDATE fiscal_rules SET status = 'draft', approved_by_1 = NULL WHERE id = $1", r["id"])
        ctx.audit(c, f"fiscal.rule_{body.action}", "fiscal_rule", r["id"], {"note": body.note}, org_id=None)
        return c.one("SELECT status, approved_by_1::text AS approved_by_1, approved_by_2::text AS approved_by_2 FROM fiscal_rules WHERE id = $1", r["id"])


# ------------------------------------------------------------------------------------------------ vouchers
class BatchIn(S.In):
    campaign: Annotated[str, Field(min_length=2, max_length=120)]
    # v0.27.0 (ADR-341): vouchers de desconto (percent_off/amount_off) foram aposentados — não há assinatura para
    # descontar. O schema recusa o tipo; linhas históricas continuam no banco e não são resgatáveis.
    type: Literal["grant_plan", "grant_feature", "free_period"]
    plan_key: S.Slug | None = None
    feature_key: Annotated[str | None, Field(max_length=60)] = None
    duration_days: Annotated[int | None, Field(ge=1, le=3650)] = None        # licença: None = permanente (grant_plan/grant_feature)
    organization_id: S.Uuid | None = None                                    # voucher restrito a uma organização/convênio
    quantity: Annotated[int, Field(ge=1, le=500)]
    max_redemptions: Annotated[int, Field(ge=1, le=10000)] = 1
    scope_roles: list[Literal["osc", "company", "provider", "government"]] = Field(default_factory=list)
    scope_cnpj: Annotated[str | None, Field(pattern=r"^[0-9]{14}$")] = None
    valid_until: datetime | None = None


@A("POST", "/v1/admin/voucher-batches", permission="billing.write", body=BatchIn, status=201,
   summary="Gera lote de vouchers (códigos exibidos UMA vez; armazenados só como HMAC). Ativação exige segundo administrador.")
def create_batch(ctx: Ctx, body: BatchIn):
    if body.type in ("grant_plan", "free_period") and not body.plan_key:
        raise ApiError(422, "validation_error", "Informe plan_key")
    if body.type == "free_period" and not body.duration_days:
        raise ApiError(422, "validation_error", "free_period exige duration_days (para licença permanente use grant_plan sem duração)")
    if body.type == "grant_feature" and not body.feature_key:
        raise ApiError(422, "validation_error", "Informe feature_key")
    codes = []
    with ctx.tx() as c:
        if body.plan_key and not c.one("SELECT 1 FROM plans WHERE plan_key = $1", body.plan_key):
            raise not_found("Plano")
        bid = c.scalar("INSERT INTO voucher_batches(campaign, created_by) VALUES ($1,$2) RETURNING id::text", body.campaign, ctx.user_id)
        for _ in range(body.quantity):
            raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
            code = f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"
            codes.append(code)
            c.run("INSERT INTO vouchers(batch_id, code_hash, code_hint, type, plan_key, feature_key, scope_roles, scope_cnpj, duration_days,"
                  " max_redemptions, valid_until, value, organization_id, created_by)"
                  " VALUES ($1,$2,$3,$4,$5,$6,$7::text[],$8,$9::int,$10::int,$11::timestamptz,'{}'::jsonb,$12,$13)",
                  bid, code_hash(ctx.settings.voucher_hmac_key, code), raw[-4:], body.type, body.plan_key, body.feature_key, body.scope_roles,
                  body.scope_cnpj, body.duration_days, body.max_redemptions, body.valid_until,
                  body.organization_id, ctx.user_id)
        ctx.audit(c, "voucher.batch_created", "voucher_batch", bid, {"campaign": body.campaign, "quantity": body.quantity, "type": body.type}, org_id=None)
    return {"batch_id": bid, "status": "pending_approval", "codes": codes,
            "warning": "Guarde os códigos agora: eles não poderão ser exibidos novamente."}


@A("GET", "/v1/admin/voucher-batches", permission="billing.read")
def list_batches(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT b.id::text AS id, b.campaign, b.status, b.created_at, b.approved_at, u.email::text AS created_by,"
                                 " (SELECT count(*) FROM vouchers v WHERE v.batch_id = b.id) AS codes,"
                                 " (SELECT coalesce(sum(redeemed_count),0) FROM vouchers v WHERE v.batch_id = b.id) AS redemptions"
                                 " FROM voucher_batches b JOIN users u ON u.id = b.created_by ORDER BY b.created_at DESC")}


class BatchActionIn(S.In):
    action: Literal["approve", "revoke"]


@A("POST", "/v1/admin/voucher-batches/{batch_id}/action", permission="billing.write",
   body=BatchActionIn)
def batch_action(ctx: Ctx, body: BatchActionIn):
    with ctx.tx() as c:
        b = c.one("SELECT id::text AS id, status, created_by::text AS created_by FROM voucher_batches WHERE id = $1 FOR UPDATE", ctx.path["batch_id"])
        if not b:
            raise not_found("Lote")
        if body.action == "approve":
            if b["status"] != "pending_approval":
                raise ApiError(409, "invalid_transition", "Lote não está pendente")
            if b["created_by"] == ctx.user_id:
                raise ApiError(409, "second_approver_required", "A aprovação deve ser feita por outro administrador")
            c.run("UPDATE voucher_batches SET status = 'active', approved_by = $2, approved_at = now() WHERE id = $1", b["id"], ctx.user_id)
        else:
            c.run("UPDATE voucher_batches SET status = 'revoked' WHERE id = $1", b["id"])
            c.run("UPDATE vouchers SET status = 'revoked' WHERE batch_id = $1 AND status = 'active'", b["id"])
        ctx.audit(c, f"voucher.batch_{body.action}", "voucher_batch", b["id"], org_id=None)
    return {"id": b["id"], "action": body.action}


# ------------------------------------------------------------------------------------------------ licenças sob contrato
class LicenseIn(S.In):
    plan_key: S.Slug
    months: Annotated[int, Field(ge=1, le=60)]
    reference: Annotated[str, Field(min_length=3, max_length=200)]


@A("POST", "/v1/admin/organizations/{org_id}/license", permission="billing.write", body=LicenseIn,
   summary="Concede licença de pacote sob contrato (Enterprise/Governo) com referência e prazo — não é assinatura (ADR-341)")
def manual_license(ctx: Ctx, body: LicenseIn):
    """v0.27.0: substitui `manual-subscription`. Um contrato institucional concede o pacote por prazo determinado;
    quando o prazo acaba, o acesso ao pacote cessa e nenhum dado é apagado. Não renova sozinho."""
    with ctx.tx() as c:
        org = c.one("SELECT kind FROM organizations WHERE id = $1", ctx.path["org_id"])
        plan = c.one("SELECT role FROM plans WHERE plan_key = $1", body.plan_key)
        if not org or not plan or plan["role"] != org["kind"]:
            raise ApiError(422, "validation_error", "Pacote incompatível com a organização")
        gid = c.scalar("INSERT INTO entitlement_grants(org_id, plan_key, source, reason, ends_at, created_by)"
                       " VALUES ($1,$2,'license',$3, now() + make_interval(months => $4::int), $5) RETURNING id::text",
                       ctx.path["org_id"], body.plan_key, f"Licença sob contrato {body.reference}", body.months, ctx.user_id)
        ctx.audit(c, "billing.license_granted", "grant", gid, {"plan": body.plan_key, "reference": body.reference, "months": body.months}, org_id=ctx.path["org_id"])
    return {"id": gid, "ends_in_months": body.months}


class InvoiceIn(S.In):
    org_id: S.Uuid
    amount_cents: S.Cents
    description: Annotated[str, Field(min_length=3, max_length=300)]
    due_on: date


@A("POST", "/v1/admin/invoices", permission="billing.write", body=InvoiceIn, status=201, summary="Emite cobrança manual (registro interno; NF-e é emitida no sistema fiscal da empresa)")
def manual_invoice(ctx: Ctx, body: InvoiceIn):
    with ctx.tx() as c:
        iid = c.scalar("INSERT INTO invoices(org_id, provider, description, amount_cents, status, due_on) VALUES ($1,'manual',$2,$3::bigint,'open',$4::date)"
                       " RETURNING id::text", body.org_id, body.description, body.amount_cents, body.due_on)
        ctx.audit(c, "billing.manual_invoice", "invoice", iid, {"amount_cents": body.amount_cents}, org_id=body.org_id)
    return {"id": iid}


class PaidIn(S.In):
    payment_reference: Annotated[str, Field(min_length=3, max_length=200)]


@A("POST", "/v1/admin/invoices/{invoice_id}/paid", permission="billing.write", body=PaidIn)
def invoice_paid(ctx: Ctx, body: PaidIn):
    with ctx.tx() as c:
        if not c.run("UPDATE invoices SET status = 'paid', paid_at = now(), payment_reference = $2 WHERE id = $1 AND provider = 'manual' AND status = 'open'",
                     ctx.path["invoice_id"], body.payment_reference):
            raise not_found("Fatura em aberto")
        ctx.audit(c, "billing.invoice_paid", "invoice", ctx.path["invoice_id"], {"reference": body.payment_reference}, org_id=None)
    return {"status": "paid"}


class GrantIn(S.In):
    plan_key: S.Slug | None = None
    feature_key: Annotated[str | None, Field(max_length=60)] = None
    days: Annotated[int | None, Field(ge=1, le=3650)] = None              # None = licença permanente
    source: Literal["admin", "license", "partner", "convention", "gov", "promotion"] = "admin"
    reason: Annotated[str, Field(min_length=3, max_length=500)]


@A("POST", "/v1/admin/organizations/{org_id}/grants", permission="billing.write", body=GrantIn, status=201)
def grant(ctx: Ctx, body: GrantIn):
    if not (body.plan_key or body.feature_key):
        raise ApiError(422, "validation_error", "Informe plan_key ou feature_key")
    with ctx.tx() as c:
        gid = c.scalar("INSERT INTO entitlement_grants(org_id, plan_key, feature_key, source, reason, ends_at, created_by)"
                       " VALUES ($1,$2,$3,$4,$5, CASE WHEN $6::int IS NULL THEN NULL ELSE now() + make_interval(days => $6::int) END, $7) RETURNING id::text",
                       ctx.path["org_id"], body.plan_key, body.feature_key, body.source, body.reason, body.days, ctx.user_id)
        ctx.audit(c, "billing.admin_grant", "grant", gid, {"plan": body.plan_key, "feature": body.feature_key, "source": body.source, "days": body.days, "reason": body.reason},
                  org_id=ctx.path["org_id"])
    return {"id": gid}


# ------------------------------------------------------------------------------------------------ denúncias, auditoria, flags, jobs
class ReportQ(S.Pagination):
    #: A situação inicial passou a se chamar `reported` na v0.20.0 (`open` misturava "ninguém olhou"
    #: com "está em aberto"). Esta rota continua existindo para leitura bruta com o denunciante à
    #: vista; a fila de apuração, que é a tela de trabalho, está em `/v1/admin/reports/queue`.
    status: str | None = "reported"


@A("GET", "/v1/admin/reports", query=ReportQ)
def reports(ctx: Ctx, q: ReportQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT r.id::text AS id, r.target_type, r.target_id::text AS target_id, r.reason, r.details, r.status, r.resolution,"
                       " r.created_at, u.email::text AS reporter FROM reports r JOIN users u ON u.id = r.reporter_user_id"
                       " WHERE ($1::text IS NULL OR r.status = $1) ORDER BY r.created_at LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


# A rota `POST /v1/admin/reports/{id}` com os estados `triaged|actioned|dismissed` foi RETIRADA na
# v0.20.0. Ela misturava andamento com conclusão ("actioned" não dizia se a denúncia procedia) e não
# tinha como registrar improcedência nem ouvir quem foi denunciado. A apuração agora corre por
# `api/report_routes.py`: review -> request-response -> conclude (com fundamentação) ou dismiss.


class AuditQ(S.Pagination):
    """Filtros da trilha. Cada um corresponde a uma pergunta de investigação, não a uma coluna.

    Até a v0.22.0 havia dois: organização e prefixo de ação. Quem investiga pergunta outras coisas —
    "o que ESTA pessoa fez", "o que aconteceu com ESTE documento", "o que foi RECUSADO", "o que é
    grave" — e nenhuma dessas tinha filtro, então a resposta era paginar milhares de linhas.
    """
    org_id: S.Uuid | None = None
    action: str | None = None
    actor_user_id: S.Uuid | None = None
    actor_type: Literal["user", "admin", "system", "ai", "automation", "integration"] | None = None
    object_type: str | None = None
    object_id: str | None = None
    correlation_id: str | None = None
    severity: Literal["info", "notice", "warning", "critical"] | None = None
    status: Literal["success", "denied", "failed"] | None = None
    source: Literal["api", "job", "cli", "webhook", "migration", "test"] | None = None
    category: str | None = None
    since: datetime | None = None
    until: datetime | None = None


_AUDIT_COLS = (
    "id, org_id::text AS org_id, actor_user_id::text AS actor, actor_type, action,"
    " audit_category(action) AS category, object_type, object_id, resource_name,"
    " ip, request_id, correlation_id, parent_event_id, session_id::text AS session_id,"
    " user_agent, severity, status, source, payload, before_state, after_state,"
    " seq, event_hash, chain_version, at")

_AUDIT_WHERE = (
    " WHERE ($1::uuid IS NULL OR org_id = $1::uuid)"
    "   AND ($2::text IS NULL OR action LIKE $2 || '%')"
    "   AND ($3::uuid IS NULL OR actor_user_id = $3::uuid)"
    "   AND ($4::text IS NULL OR actor_type = $4)"
    "   AND ($5::text IS NULL OR object_type = $5)"
    "   AND ($6::text IS NULL OR object_id = $6)"
    "   AND ($7::text IS NULL OR correlation_id = $7)"
    "   AND ($8::text IS NULL OR severity = $8)"
    "   AND ($9::text IS NULL OR status = $9)"
    "   AND ($10::text IS NULL OR source = $10)"
    "   AND ($11::text IS NULL OR audit_category(action) = $11)"
    "   AND ($12::timestamptz IS NULL OR at >= $12)"
    "   AND ($13::timestamptz IS NULL OR at <= $13)")


def _audit_args(q: AuditQ) -> list:
    return [q.org_id, q.action, q.actor_user_id, q.actor_type, q.object_type, q.object_id,
            q.correlation_id, q.severity, q.status, q.source,
            q.category.upper() if q.category else None, q.since, q.until]


@A("GET", "/v1/admin/audit", permission="security.audit.read", query=AuditQ)
def audit_search(ctx: Ctx, q: AuditQ):
    from ..core.access import log_privileged
    log_privileged(ctx, "security.audit.read")
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {_AUDIT_COLS} FROM audit_events{_AUDIT_WHERE}"
                       " ORDER BY id DESC LIMIT $14 OFFSET $15",
                       *_audit_args(q), q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


class TimelineQ(S.In):
    object_type: str
    object_id: str
    limit: int = Field(default=200, ge=1, le=1000)


@A("GET", "/v1/admin/audit/timeline", permission="security.audit.read", query=TimelineQ,
   summary="Linha do tempo de UMA entidade: tudo o que aconteceu com este documento, projeto ou organização")
def audit_timeline(ctx: Ctx, q: TimelineQ):
    """A consulta que o produto não conseguia fazer sem varrer a tabela que mais cresce no banco.

    `ix_audit_object` existe desde a migração 0056 exatamente para esta rota.
    """
    from ..core.access import log_privileged
    log_privileged(ctx, "security.audit.read")
    with ctx.tx(readonly=True) as c:
        linhas = c.query(f"SELECT {_AUDIT_COLS} FROM audit_events"
                         " WHERE object_type = $1 AND object_id = $2"
                         " ORDER BY id LIMIT $3", q.object_type, q.object_id, q.limit)
    return {"object_type": q.object_type, "object_id": q.object_id,
            "events": linhas, "count": len(linhas),
            "truncated": len(linhas) == q.limit,
            "note": None if len(linhas) < q.limit else
            f"A linha do tempo foi cortada em {q.limit} eventos. Use os filtros de "
            f"`/v1/admin/audit` para percorrer o resto — a trilha é append-only, nada se perdeu."}


class TrailQ(S.In):
    correlation_id: str


@A("GET", "/v1/admin/audit/trail", permission="security.audit.read", query=TrailQ,
   summary="Árvore de causa de um rastro: que acontecimento levou a qual, por parent_event_id")
def audit_trail(ctx: Ctx, q: TrailQ):
    """Sai de "quem mexeu neste documento?" para "mostre-me a cadeia que o levou até este estado".

    A diferença entre esta rota e a linha do tempo é a ÁRVORE: a linha do tempo ordena por tempo e
    não diz o que causou o quê. `parent_event_id` diz, e `depth` é o que a interface indenta.
    """
    from ..core.access import log_privileged
    log_privileged(ctx, "security.audit.read")
    with ctx.tx(readonly=True) as c:
        arvore = c.query("SELECT * FROM audit_trail_of($1)", q.correlation_id)
        # CONFERÊNCIA DE COMPLETUDE, não um segundo resultado.
        #
        # A primeira versão devolvia um campo `unlinked` com "eventos do rastro fora da árvore". Ele
        # é provavelmente vazio SEMPRE, e por construção: `audit_trail_of()` traz como raiz todo
        # evento sem pai, e `aa_trg_audit_parent` recusa pai de outra correlação — então todo evento
        # do rastro é raiz ou descendente de uma. Um campo que não pode ter conteúdo não informa
        # nada e sugere que informa, que é pior.
        #
        # O que vale conferir é o contrário: se a árvore tem MENOS eventos que o rastro, alguma
        # dessas duas garantias deixou de valer, e aí a árvore está mentindo por omissão.
        total = c.scalar("SELECT count(*) FROM audit_events WHERE correlation_id = $1",
                         q.correlation_id)
    faltando = total - len(arvore)
    return {"correlation_id": q.correlation_id, "tree": arvore,
            "events_in_trail": total, "events_in_tree": len(arvore),
            "complete": faltando == 0,
            "note": None if faltando == 0 else
            f"ATENÇÃO: {faltando} evento(s) deste rastro não aparecem na árvore de causa. Isso só "
            f"acontece se a relação de pai apontar para fora da correlação, o que o banco recusa — "
            f"então é indício de alteração direta no banco."}


@A("POST", "/v1/admin/audit/export", permission="security.audit.export", body=AuditQ,
   summary="Exporta a trilha filtrada — e registra a própria exportação na trilha")
def audit_export(ctx: Ctx, body: AuditQ):
    """Exportar trilha de auditoria é um evento auditável. Quem exporta leva a própria linha.

    Levar a trilha para fora é a operação que mais interessa a quem quer apagar rastro depois, e era
    a única leitura privilegiada que não deixava registro NA PRÓPRIA TRILHA — só em
    `privileged_access_log`. Agora deixa as duas, e a exportação devolve o id do evento que ela
    gerou, para que quem recebe o arquivo possa conferir a origem.
    """
    with ctx.tx(readonly=True) as c:
        linhas = c.query(f"SELECT {_AUDIT_COLS} FROM audit_events{_AUDIT_WHERE}"
                         " ORDER BY id LIMIT $14", *_audit_args(body), min(body.limit, 10_000))
    # `ctx.tx()` e não contexto de sistema: a política de INSERT de `audit_events` aceita
    # `app_priv()`, que é o que uma sessão de administração tem. Usar contexto de sistema aqui
    # alargaria a lista de módulos que podem ignorar a RLS para ganhar nada.
    with ctx.tx() as c:
        evento = ctx.audit(c, "audit.log_exported", "audit_events", None,
                           {"rows": len(linhas), "filters": body.model_dump(mode="json",
                                                                            exclude_none=True)},
                           severity="warning")
    return {"export_event_id": evento, "rows": len(linhas), "events": linhas,
            "limit_applied": min(body.limit, 10_000),
            "note": "Esta exportação foi registrada na trilha como `audit.log_exported`, com o "
                    "número de linhas e os filtros usados."}


class VerifyQ(S.In):
    org_id: S.Uuid | None = None


@A("GET", "/v1/admin/audit/verify", query=VerifyQ, summary="Verifica a cadeia de hashes da trilha de auditoria")
def audit_verify(ctx: Ctx, q: VerifyQ):
    with ctx.tx(readonly=True) as c:
        return c.one("SELECT * FROM audit_verify($1::uuid)", q.org_id)


@A("GET", "/v1/admin/flags", permission="maintenance.read")
def flags(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT key, enabled, description, updated_at FROM feature_flags ORDER BY key")}


class FlagIn(S.In):
    enabled: bool


@A("PUT", "/v1/admin/flags/{key}", permission="maintenance.execute", body=FlagIn)
def set_flag(ctx: Ctx, body: FlagIn):
    with ctx.tx() as c:
        if not c.run("UPDATE feature_flags SET enabled = $2::bool, updated_by = $3, updated_at = now() WHERE key = $1", ctx.path["key"], body.enabled, ctx.user_id):
            raise not_found("Flag")
        ctx.audit(c, "admin.flag_changed", "flag", ctx.path["key"], {"enabled": body.enabled}, org_id=None)
    return {"key": ctx.path["key"], "enabled": body.enabled}


@A("GET", "/v1/admin/jobs", permission="maintenance.read")
def jobs(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT job, status, detail AS details, started_at, finished_at, duration_ms, error"
                                 " FROM ops_job_runs ORDER BY id DESC LIMIT 100"),
                "billing_events": c.query("SELECT provider, event_id, type, status, error, received_at FROM billing_events ORDER BY id DESC LIMIT 50")}
