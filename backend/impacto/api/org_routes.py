"""Organização ativa: perfil, perfil de investimento (empresa), perfil profissional (prestador), credenciais,
perfil fiscal, diretório de profissionais parceiros, notificações e denúncias."""
from __future__ import annotations

from ..http import ApiError, Ctx, not_found, page, route
from . import schemas as S

T = ("organizations",)
PUBLIC_ORG_COLS = ("id::text AS id, kind, legal_name, trade_name, cnpj, description, website, city, uf, ibge_code, territories,"
                   " causes, ods, certifications, founded_on, compliance_status, created_at")


@route("GET", "/v1/org", min_role="viewer", tags=T, summary="Perfil completo da organização ativa")
def get_org(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        org = c.one("SELECT id::text AS id, kind, legal_name, trade_name, cnpj, legal_nature, founded_on, description, website,"
                    " contact_email::text AS contact_email, phone, city, uf, ibge_code, territories, causes, ods, esg_focus,"
                    " certifications, team_size, annual_revenue_cents, status, compliance_status, compliance_risk, created_at,"
                    " legal_nature_code, institutional_profile, institutional_status"
                    " FROM organizations WHERE id = $1", ctx.org_id)
        fp = c.one("SELECT * FROM funder_profiles WHERE org_id = $1", ctx.org_id) if org["kind"] in ("company", "individual") else None
        pp = c.one("SELECT * FROM provider_profiles WHERE org_id = $1", ctx.org_id) if org["kind"] == "provider" else None
    return {"organization": org, "funder_profile": fp, "provider_profile": pp}


@route("PATCH", "/v1/org", body=S.OrgProfileIn, min_role="admin", tags=T, summary="Atualiza o perfil da organização")
def patch_org(ctx: Ctx, body: S.OrgProfileIn):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise ApiError(422, "empty", "Nada para atualizar")
    certs = data.pop("certifications", None)
    sets, vals = [], [ctx.org_id]
    for k, v in data.items():
        vals.append(v)
        cast = {"territories": "::text[]", "causes": "::text[]", "esg_focus": "::text[]", "certifications": "::text[]",
                "ods": "::smallint[]", "founded_on": "::date", "team_size": "::int", "annual_revenue_cents": "::bigint"}.get(k, "")
        sets.append(f"{k} = ${len(vals)}{cast}")
    with ctx.tx() as c:
        if sets:
            c.run(f"UPDATE organizations SET {', '.join(sets)} WHERE id = $1", *vals)
        if certs is not None:
            # Campo legado: agora cada código vira uma QUALIFICAÇÃO DECLARADA (não comprovada) na camada institucional; o array é só espelho.
            from ..services import institutional as inst
            from .institutional_routes import _sync_certifications
            known = inst.catalog(c, "qualification_type").get("qualification_type", {})
            bad = [x for x in certs if x not in known]
            if bad:
                raise ApiError(422, "validation_error", "Qualificações fora do catálogo: " + ", ".join(bad), {"valid": sorted(known)})
            for code in certs:
                c.run("INSERT INTO organization_qualifications(org_id, qualification_type, declared_by) SELECT $1, $2, $3 WHERE NOT EXISTS"
                      " (SELECT 1 FROM organization_qualifications WHERE org_id = $1 AND qualification_type = $2 AND verification_status NOT IN ('rejected','revoked'))",
                      ctx.org_id, code, ctx.user_id)
            _sync_certifications(c, ctx.org_id)
        ctx.audit(c, "org.profile_updated", "organization", ctx.org_id, {"fields": sorted(data) + (["certifications"] if certs is not None else [])})
    return get_org(ctx)


@route("PUT", "/v1/org/funder-profile", body=S.FunderProfileIn, kinds=("company", "individual"), min_role="manager", tags=T,
       summary="Perfil de investimento: causas, ODS, ESG, território, ticket, restrições e documentos exigidos")
def put_funder_profile(ctx: Ctx, body: S.FunderProfileIn):
    d = body.model_dump()
    if d["ticket_min_cents"] is not None and d["ticket_max_cents"] is not None and d["ticket_min_cents"] > d["ticket_max_cents"]:
        raise ApiError(422, "validation_error", "Ticket mínimo maior que o máximo")
    with ctx.tx() as c:
        c.run("INSERT INTO funder_profiles(org_id, causes, ods, esg_focus, territories, excluded_causes, excluded_territories,"
              " ticket_min_cents, ticket_max_cents, annual_budget_cents, required_document_types, min_org_age_months, accepts_fractioning, policies, public_name,"
              " accepted_legal_natures, required_qualifications, min_maturity, funding_modalities)"
              " VALUES ($1,$2::text[],$3::smallint[],$4::text[],$5::text[],$6::text[],$7::text[],$8::bigint,$9::bigint,$10::bigint,$11::text[],$12::int,$13::bool,$14,$15::bool,$16::text[],$17::text[],$18::smallint,$19::text[])"
              " ON CONFLICT (org_id) DO UPDATE SET causes=EXCLUDED.causes, ods=EXCLUDED.ods, esg_focus=EXCLUDED.esg_focus,"
              " territories=EXCLUDED.territories, excluded_causes=EXCLUDED.excluded_causes, excluded_territories=EXCLUDED.excluded_territories,"
              " ticket_min_cents=EXCLUDED.ticket_min_cents, ticket_max_cents=EXCLUDED.ticket_max_cents, annual_budget_cents=EXCLUDED.annual_budget_cents,"
              " required_document_types=EXCLUDED.required_document_types, min_org_age_months=EXCLUDED.min_org_age_months,"
              " accepts_fractioning=EXCLUDED.accepts_fractioning, policies=EXCLUDED.policies, public_name=EXCLUDED.public_name,"
              " accepted_legal_natures=EXCLUDED.accepted_legal_natures, required_qualifications=EXCLUDED.required_qualifications,"
              " min_maturity=EXCLUDED.min_maturity, funding_modalities=EXCLUDED.funding_modalities",
              ctx.org_id, d["causes"], d["ods"], d["esg_focus"], d["territories"], d["excluded_causes"], d["excluded_territories"],
              d["ticket_min_cents"], d["ticket_max_cents"], d["annual_budget_cents"], d["required_document_types"],
              d["min_org_age_months"], d["accepts_fractioning"], d["policies"], d["public_name"],
              d["accepted_legal_natures"], d["required_qualifications"], d["min_maturity"], d["funding_modalities"])
        ctx.audit(c, "org.funder_profile_updated", "organization", ctx.org_id)
        return c.one("SELECT * FROM funder_profiles WHERE org_id = $1", ctx.org_id)


@route("PUT", "/v1/org/provider-profile", body=S.ProviderProfileIn, kinds=("provider",), min_role="manager", tags=T)
def put_provider_profile(ctx: Ctx, body: S.ProviderProfileIn):
    d = body.model_dump()
    with ctx.tx() as c:
        c.run("INSERT INTO provider_profiles(org_id, services, categories, remote, territories, languages, accessibility, price_info, accepting_requests)"
              " VALUES ($1,$2::text[],$3::text[],$4::bool,$5::text[],$6::text[],$7,$8,$9::bool) ON CONFLICT (org_id) DO UPDATE SET"
              " services=EXCLUDED.services, categories=EXCLUDED.categories, remote=EXCLUDED.remote, territories=EXCLUDED.territories,"
              " languages=EXCLUDED.languages, accessibility=EXCLUDED.accessibility, price_info=EXCLUDED.price_info,"
              " accepting_requests=EXCLUDED.accepting_requests",
              ctx.org_id, d["services"], d["categories"], d["remote"], d["territories"], d["languages"], d["accessibility"],
              d["price_info"], d["accepting_requests"])
        ctx.audit(c, "org.provider_profile_updated", "organization", ctx.org_id)
        return c.one("SELECT * FROM provider_profiles WHERE org_id = $1", ctx.org_id)


@route("GET", "/v1/org/credentials", kinds=("provider",), min_role="viewer", tags=T)
def list_credentials(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, user_id::text AS user_id, council, number, uf, holder_name, valid_until,"
                                 " verification_status, verification_note, verified_at, document_id::text AS document_id, created_at"
                                 " FROM professional_credentials WHERE org_id = $1 ORDER BY created_at DESC", ctx.org_id)}


@route("POST", "/v1/org/credentials", body=S.CredentialIn, kinds=("provider",), min_role="member", status=201, tags=T,
       summary="Registra credencial profissional (CRC, OAB...). Nasce 'autodeclarada' até verificação pela administração.")
def add_credential(ctx: Ctx, body: S.CredentialIn):
    with ctx.tx() as c:
        if body.document_id and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2", body.document_id, ctx.org_id):
            raise not_found("Documento")
        cid = c.scalar("INSERT INTO professional_credentials(org_id, user_id, council, number, uf, holder_name, valid_until, document_id,"
                       " verification_status) VALUES ($1,$2,$3,$4,$5,$6,$7::date,$8, $9) RETURNING id::text",
                       ctx.org_id, ctx.user_id, body.council, body.number, body.uf, body.holder_name, body.valid_until,
                       body.document_id, "document_submitted" if body.document_id else "self_declared")
        ctx.audit(c, "credential.created", "credential", cid, {"council": body.council, "uf": body.uf})
    return {"id": cid}


@route("PUT", "/v1/org/tax-profile", body=S.TaxProfileIn, kinds=("company",), min_role="manager", tags=("fiscal",))
def put_tax_profile(ctx: Ctx, body: S.TaxProfileIn):
    with ctx.tx() as c:
        c.run("INSERT INTO company_tax_profiles(org_id, regime, fiscal_year, estimated_ir_due_cents, uf, updated_by)"
              " VALUES ($1,$2,$3::int,$4::bigint,$5,$6) ON CONFLICT (org_id) DO UPDATE SET regime=EXCLUDED.regime,"
              " fiscal_year=EXCLUDED.fiscal_year, estimated_ir_due_cents=EXCLUDED.estimated_ir_due_cents, uf=EXCLUDED.uf,"
              " updated_by=EXCLUDED.updated_by",
              ctx.org_id, body.regime, body.fiscal_year, body.estimated_ir_due_cents, body.uf, ctx.user_id)
        ctx.audit(c, "fiscal.tax_profile_updated", "organization", ctx.org_id, {"regime": body.regime})
        return c.one("SELECT * FROM company_tax_profiles WHERE org_id = $1", ctx.org_id)


@route("GET", "/v1/org/tax-profile", kinds=("company",), min_role="analyst", tags=("fiscal",))
def get_tax_profile(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return c.one("SELECT * FROM company_tax_profiles WHERE org_id = $1", ctx.org_id) or {"regime": "unknown"}


class DirectoryQ(S.Pagination):
    category: str | None = None
    territory: S.Territory | None = None
    q: str | None = None


@route("GET", "/v1/directory/professionals", query=DirectoryQ, min_role="viewer", tags=("directory",),
       summary="Diretório de profissionais parceiros. Ordenação objetiva e determinística — NUNCA por plano (invariante).")
def directory(ctx: Ctx, q: DirectoryQ):
    from ..services.directory import search_professionals
    with ctx.tx(readonly=True) as c:
        rows = search_professionals(c, category=q.category, territory=q.territory, text=q.q, limit=q.limit + 1, offset=q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/organizations/{org_id}", min_role="viewer", tags=T, summary="Perfil público de outra organização")
def public_org(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        org = c.one(f"SELECT {PUBLIC_ORG_COLS} FROM organizations WHERE id = $1 AND status = 'active'", ctx.path["org_id"])
        if not org:
            raise not_found("Organização")
        org["credentials"] = c.query("SELECT council, number, uf, holder_name, verification_status, valid_until FROM professional_credentials"
                                     " WHERE org_id = $1 ORDER BY council", org["id"]) if org["kind"] == "provider" else []
        org["provider_profile"] = c.one("SELECT services, categories, remote, territories, languages, accessibility, price_info,"
                                        " accepting_requests FROM provider_profiles WHERE org_id = $1", org["id"]) if org["kind"] == "provider" else None
        org["published_projects"] = c.query("SELECT id::text AS id, title, causes, territory, budget_total_cents, status FROM projects"
                                             " WHERE org_id = $1 AND visibility = 'published' ORDER BY published_at DESC LIMIT 20", org["id"]) \
            if org["kind"] == "osc" else []
    return org


# ------------------------------------------------------------------------------------------------ notificações
class NotifQ(S.Pagination):
    unread: bool = False


@route("GET", "/v1/notifications", query=NotifQ, min_role="viewer", tags=("notifications",))
def notifications(ctx: Ctx, q: NotifQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, kind, title, body, link, read_at, created_at FROM notifications"
                       " WHERE ($1::bool = false OR read_at IS NULL) ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                       q.unread, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/notifications/read-all", min_role="viewer", allow_unverified=True, tags=("notifications",))
def read_all(ctx: Ctx):
    with ctx.tx() as c:
        n = c.run("UPDATE notifications SET read_at = now() WHERE read_at IS NULL")
    return {"updated": n}


@route("POST", "/v1/notifications/{notification_id}/read", min_role="viewer", allow_unverified=True, tags=("notifications",))
def read_one(ctx: Ctx):
    with ctx.tx() as c:
        if not c.run("UPDATE notifications SET read_at = coalesce(read_at, now()) WHERE id = $1", ctx.path["notification_id"]):
            raise not_found("Notificação")
    return None


# ------------------------------------------------------------------------------------------------ denúncias
@route("POST", "/v1/reports", auth="user", body=S.ReportIn, status=201, rate=("report_ip", 20, 3600), tags=("trust",),
       summary="Denuncia organização, projeto, edital, documento ou usuário (triagem humana pela administração)")
def create_report(ctx: Ctx, body: S.ReportIn):
    from ..network import complaints as REP
    with ctx.tx() as c:
        out = REP.open_report(c, reporter_user_id=ctx.user_id, reporter_org_id=ctx.principal.org_id,
                              target_type=body.target_type, target_id=body.target_id,
                              reason=body.reason, details=body.details, category=body.category,
                              evidence_document_id=body.evidence_document_id)
    with ctx.system_tx() as c:
        ctx.audit(c, "report.created", "report", out["id"],
                  {"target_type": body.target_type, "reason": body.reason, "category": body.category},
                  org_id=ctx.principal.org_id)
    return out
