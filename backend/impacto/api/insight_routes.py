"""Painéis (OSC, empresa, governo, prestador), dados agregados para governo, estimativas fiscais e compliance."""
from __future__ import annotations

from ..http import ApiError, Ctx, not_found, route
from ..engines.fiscal.engine import evaluate as fiscal_evaluate
from ..services import compliance
from . import schemas as S


@route("GET", "/v1/dashboard", min_role="viewer", tags=("dashboard",), summary="Indicadores da organização ativa (dados reais do banco)")
def dashboard(ctx: Ctx):
    k = ctx.principal.org_kind
    with ctx.tx(readonly=True) as c:
        out: dict = {"kind": k}
        if k == "osc":
            out["projects"] = c.one("SELECT count(*) AS total, count(*) FILTER (WHERE visibility = 'published') AS published,"
                                    " count(*) FILTER (WHERE status = 'in_execution') AS in_execution, coalesce(sum(budget_total_cents),0) AS needed_cents"
                                    " FROM projects WHERE org_id = $1", ctx.org_id)
            out["funding"] = c.one("SELECT coalesce(sum(amount_cents) FILTER (WHERE status <> 'cancelled'),0) AS committed_cents,"
                                   " coalesce(sum(amount_cents) FILTER (WHERE status = 'confirmed'),0) AS received_cents FROM commitments WHERE osc_org_id = $1", ctx.org_id)
            out["applications"] = c.query("SELECT status, count(*) AS n FROM applications WHERE osc_org_id = $1 GROUP BY status", ctx.org_id)
            out["documents"] = c.one("SELECT count(*) FILTER (WHERE valid_until < current_date) AS expired,"
                                     " count(*) FILTER (WHERE valid_until BETWEEN current_date AND current_date + 30) AS expiring,"
                                     " count(*) FILTER (WHERE status = 'pending_scan') AS pending_scan, count(*) AS total"
                                     " FROM documents WHERE org_id = $1 AND deleted_at IS NULL", ctx.org_id)
            out["evidences"] = c.query("SELECT status, count(*) AS n FROM evidences WHERE org_id = $1 GROUP BY status", ctx.org_id)
            out["open_calls"] = c.scalar("SELECT count(*) FROM calls WHERE status = 'open' AND (closes_at IS NULL OR closes_at >= now())")
            out["deadlines"] = c.query("SELECT a.id::text AS application_id, c.title, c.closes_at FROM applications a JOIN calls c ON c.id = a.call_id"
                                       " WHERE a.osc_org_id = $1 AND a.status = 'draft' AND c.closes_at >= now() ORDER BY c.closes_at LIMIT 5", ctx.org_id)
        elif k in ("company", "government", "individual"):
            out["calls"] = c.query("SELECT status, count(*) AS n FROM calls WHERE owner_org_id = $1 GROUP BY status", ctx.org_id)
            out["pipeline"] = c.query("SELECT status, count(*) AS n FROM applications WHERE funder_org_id = $1 GROUP BY status", ctx.org_id)
            out["portfolio"] = c.one("SELECT coalesce(sum(amount_cents) FILTER (WHERE status <> 'cancelled'),0) AS committed_cents,"
                                     " coalesce(sum(amount_cents) FILTER (WHERE status IN ('disbursed','confirmed')),0) AS disbursed_cents,"
                                     " count(DISTINCT project_id) AS projects FROM commitments WHERE funder_org_id = $1", ctx.org_id)
            out["by_cause"] = c.query("SELECT cause, sum(amount) AS committed_cents FROM (SELECT unnest(p.causes) AS cause, cm.amount_cents AS amount"
                                      " FROM commitments cm JOIN projects p ON p.id = cm.project_id WHERE cm.funder_org_id = $1 AND cm.status <> 'cancelled') x"
                                      " GROUP BY cause ORDER BY 2 DESC", ctx.org_id)
            out["by_ods"] = c.query("SELECT ods, sum(amount) AS committed_cents FROM (SELECT unnest(p.ods) AS ods, cm.amount_cents AS amount"
                                    " FROM commitments cm JOIN projects p ON p.id = cm.project_id WHERE cm.funder_org_id = $1 AND cm.status <> 'cancelled') x"
                                    " GROUP BY ods ORDER BY ods", ctx.org_id)
            out["by_territory"] = c.query("SELECT split_part(p.territory, '-', 2) AS uf, sum(cm.amount_cents) AS committed_cents FROM commitments cm"
                                          " JOIN projects p ON p.id = cm.project_id WHERE cm.funder_org_id = $1 AND cm.status <> 'cancelled' GROUP BY 1 ORDER BY 2 DESC",
                                          ctx.org_id)
            out["pending_reviews"] = c.scalar("SELECT count(*) FROM evidences e WHERE e.status = 'submitted' AND app_project_investor(e.project_id)")
        elif k == "provider":
            out["reviews"] = c.query("SELECT status, count(*) AS n FROM professional_reviews WHERE professional_org_id = $1 GROUP BY status", ctx.org_id)
            out["credentials"] = c.query("SELECT verification_status, count(*) AS n FROM professional_credentials WHERE org_id = $1 GROUP BY 1", ctx.org_id)
    return out


class GovQ(S.In):
    territory: S.Territory = "BR"
    min_group: int = 3


@route("GET", "/v1/gov/territory-stats", kinds=("government", "platform"), query=GovQ, min_role="viewer", feature="gov.data", tags=("government",),
       summary="Dados agregados e anonimizados por território e causa (k-anonimato ≥ 3 projetos por grupo)")
def gov_stats(ctx: Ctx, q: GovQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT * FROM gov_territory_stats($1, $2::int)", q.territory, q.min_group)
        calls = c.query("SELECT sphere, instrument, count(*) AS n, coalesce(sum(budget_total_cents),0) AS budget_cents FROM calls"
                        " WHERE status = 'open' GROUP BY 1, 2 ORDER BY 3 DESC")
    return {"territory_prefix": q.territory, "groups": rows, "open_calls_by_sphere": calls,
            "privacy_note": "Grupos com menos de 3 projetos são suprimidos. Nenhum dado pessoal é exibido."}


# ------------------------------------------------------------------------------------------------ fiscal
class FiscalQ(S.In):
    project_id: S.Uuid | None = None


@route("GET", "/v1/fiscal/estimates", kinds=("company",), query=FiscalQ, min_role="analyst", feature="fiscal.estimates", tags=("fiscal",),
       summary="Mecanismos possivelmente aplicáveis (regras aprovadas e vigentes): REGRA × ELEGIBILIDADE PROVÁVEL × ESTIMATIVA × VALIDAÇÃO")
def fiscal_estimates(ctx: Ctx, q: FiscalQ):
    with ctx.tx(readonly=True) as c:
        rules = c.query("SELECT * FROM fiscal_rules WHERE status = 'approved' ORDER BY code, version")
        tp = c.one("SELECT * FROM company_tax_profiles WHERE org_id = $1", ctx.org_id)
        proj = None
        if q.project_id:
            proj = c.one("SELECT causes FROM projects WHERE id = $1", q.project_id)
            if not proj:
                raise not_found("Projeto")
    res = fiscal_evaluate(rules, tp, proj)
    if not rules:
        res["notice"] = "Nenhuma regra fiscal aprovada nesta instalação. Regras candidatas aguardam revisão de dois especialistas."
    return res


@route("GET", "/v1/fiscal/rules", min_role="viewer", tags=("fiscal",), summary="Regras fiscais aprovadas (fonte, versão e vigência)")
def fiscal_rules(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT code, version, name, mechanism, jurisdiction, tax_base, limit_pct::float AS limit_pct, limit_note,"
                                 " source_citation, source_url, effective_from, effective_to, approved_at FROM fiscal_rules WHERE status = 'approved'"
                                 " ORDER BY code")}


# ------------------------------------------------------------------------------------------------ compliance
@route("GET", "/v1/compliance", min_role="viewer", tags=("compliance",), summary="Status de compliance/KYB da organização e verificações")
def get_compliance(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        org = c.one("SELECT compliance_status, compliance_risk, compliance_reviewed_at FROM organizations WHERE id = $1", ctx.org_id)
        checks = c.query("SELECT DISTINCT ON (check_type) check_type, status, details, source, checked_at FROM compliance_checks"
                         " WHERE org_id = $1 ORDER BY check_type, checked_at DESC", ctx.org_id)
        reviews = c.query("SELECT id::text AS id, status, risk_level, decision_note, created_at, decided_at FROM compliance_reviews"
                          " WHERE org_id = $1 ORDER BY created_at DESC LIMIT 10", ctx.org_id)
    return {**org, "checks": checks, "reviews": reviews}


@route("POST", "/v1/compliance/request-review", min_role="admin", tags=("compliance",),
       summary="Executa verificações automáticas e envia para análise humana da administração")
def compliance_request(ctx: Ctx):
    return compliance.request_review(ctx)


@route("GET", "/v1/organizations/{org_id}/compliance", kinds=("company", "government", "individual"), min_role="viewer", tags=("compliance",),
       summary="Resumo de compliance de uma OSC com a qual o financiador tem candidatura (due diligence)")
def counterpart_compliance(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        if not c.scalar("SELECT app_osc_counterparty($1)", ctx.path["org_id"]):
            raise ApiError(404, "not_found", "Sem relação de candidatura com esta organização")
        org = c.one("SELECT legal_name, compliance_status, compliance_risk, compliance_reviewed_at FROM organizations WHERE id = $1", ctx.path["org_id"])
        checks = c.query("SELECT DISTINCT ON (check_type) check_type, status, details, checked_at FROM compliance_checks WHERE org_id = $1"
                         " ORDER BY check_type, checked_at DESC", ctx.path["org_id"])
    return {**org, "checks": checks}
