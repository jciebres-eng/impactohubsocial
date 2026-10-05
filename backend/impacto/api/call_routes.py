"""Banco de oportunidades: chamadas, editais, fundos e financiamentos (privados, federais, estaduais, municipais,
locais e internacionais); compatibilidade explicável para OSC; buscas salvas com alertas; materiais de governo."""
from __future__ import annotations

from ..db.pq import Json
from ..http import ApiError, Ctx, not_found, page, route
from ..services import matching
from ..services.entitlements import check_limit
from . import schemas as S

T = ("calls",)
LIST_COLS = ("c.id::text AS id, c.title, c.funder_name, c.summary, c.sphere, c.instrument, c.causes, c.ods, c.territories,"
             " c.ticket_min_cents, c.ticket_max_cents, c.budget_total_cents, c.opens_at, c.closes_at, c.status, c.url,"
             " c.managed_on_platform, c.source_type, c.is_example, c.last_verified_at, c.owner_org_id::text AS owner_org_id")


def _csv(v: str | None) -> list[str] | None:
    if not v:
        return None
    return [x.strip() for x in v.split(",") if x.strip()][:20]


def search_sql(q: S.CallSearchQ, org_id: str | None) -> tuple[str, list]:
    where, vals = ["true"], []

    def add(cond, val):
        vals.append(val)
        where.append(cond.replace("?", f"${len(vals)}"))
    if q.mine:
        add("c.owner_org_id = ?::uuid", org_id)
    elif q.status == "open":
        where.append("c.status = 'open' AND (c.closes_at IS NULL OR c.closes_at >= now())")
    elif q.status == "closed":
        where.append("(c.status = 'closed' OR c.closes_at < now())")
    if q.q:
        add("(c.title ILIKE '%' || ? || '%' OR c.summary ILIKE '%' || ? || '%' OR c.funder_name ILIKE '%' || ? || '%')", q.q)
        where[-1] = where[-1].replace(f"${len(vals)}", f"${len(vals)}")
    if _csv(q.sphere):
        add("c.sphere = ANY(?::text[])", _csv(q.sphere))
    if _csv(q.instrument):
        add("c.instrument = ANY(?::text[])", _csv(q.instrument))
    if _csv(q.cause):
        add("(c.causes && ?::text[] OR cardinality(c.causes) = 0)", _csv(q.cause))
    if q.territory:
        add("(cardinality(c.territories) = 0 OR EXISTS (SELECT 1 FROM unnest(c.territories) t WHERE t = 'INT' OR ? LIKE t || '%'))", q.territory)
    if q.closes_before:
        add("c.closes_at <= (?::date + 1)", q.closes_before)
    if q.min_amount_cents:
        add("(c.ticket_max_cents IS NULL OR c.ticket_max_cents >= ?::bigint)", q.min_amount_cents)
    sql = (f"SELECT {LIST_COLS} FROM calls c WHERE {' AND '.join(where)}"
           f" ORDER BY c.closes_at NULLS LAST, c.created_at DESC LIMIT ${len(vals) + 1} OFFSET ${len(vals) + 2}")
    return sql, vals + [q.limit + 1, q.offset]


@route("GET", "/v1/calls", query=S.CallSearchQ, min_role="viewer", feature=None, tags=T,
       summary="Busca no banco de oportunidades. Para OSC, cada item traz a compatibilidade resumida.")
def list_calls(ctx: Ctx, q: S.CallSearchQ):
    sql, vals = search_sql(q, ctx.principal.org_id)
    with ctx.tx(readonly=True) as c:
        rows = c.query(sql, *vals)
        if ctx.principal.org_kind == "osc":
            org = matching.load_org(c, ctx.org_id)
            docs = matching.load_documents(c, ctx.org_id, None)
            hist = matching.load_history(c, ctx.org_id)
            ictx = matching.inst_context(c, ctx.org_id)
            for r in rows[: q.limit]:
                full = matching.load_call(c, r["id"])
                m = matching.evaluate_osc_call(c, ctx.org_id, full, None, docs=docs, history=hist, org=org, inst_ctx=ictx)
                r["match"] = {k: m[k] for k in ("eligibility", "recommended_state", "score", "confidence")}
                r["match"]["unmet"] = sum(1 for x in m["requirements"] if x["status"] == "unmet")
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/calls/recommended", kinds=("osc",), query=S.Pagination, min_role="viewer", tags=T,
       summary="Editais abertos ranqueados por compatibilidade com a OSC (elegíveis primeiro, depois score)")
def recommended(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        org = matching.load_org(c, ctx.org_id)
        docs = matching.load_documents(c, ctx.org_id, None)
        hist = matching.load_history(c, ctx.org_id)
        ictx = matching.inst_context(c, ctx.org_id)
        cands = c.query("SELECT id::text AS id FROM calls c WHERE c.status = 'open' AND (c.closes_at IS NULL OR c.closes_at >= now())"
                        " AND (cardinality(c.causes) = 0 OR c.causes && $1::text[] OR cardinality($1::text[]) = 0)"
                        " ORDER BY c.closes_at NULLS LAST LIMIT 300", org["causes"] or [])
        scored = []
        for cand in cands:
            call = matching.load_call(c, cand["id"])
            m = matching.evaluate_osc_call(c, ctx.org_id, call, None, docs=docs, history=hist, org=org, inst_ctx=ictx)
            scored.append((cand["id"], m))
        order = {"eligible": 0, "needs_review": 1, "blocked": 2}
        scored.sort(key=lambda x: (order[x[1]["eligibility"]], -(x[1]["score"] or 0)))
        sel = scored[q.offset: q.offset + q.limit + 1]
        out = []
        for cid, m in sel:
            row = c.one(f"SELECT {LIST_COLS} FROM calls c WHERE c.id = $1", cid)
            row["match"] = {k: m[k] for k in ("eligibility", "recommended_state", "score", "confidence", "next_action")}
            row["match"]["why_match"] = [w["label"] for w in m["why_match"]]
            row["match"]["unmet"] = [r["label"] for r in m["requirements"] if r["status"] == "unmet"]
            out.append(row)
    return page(out, q.limit, q.offset) | {"engine_note": "Ranking não considera plano, voucher ou pagamento."}


class CallDetailQ(S.In):
    project_id: S.Uuid | None = None


@route("GET", "/v1/calls/{call_id}", query=CallDetailQ, min_role="viewer", tags=T,
       summary="Detalhe do edital. Para OSC: requisitos atendidos/pendentes, compatibilidade, riscos e próxima ação.")
def get_call(ctx: Ctx, q: CallDetailQ):
    with ctx.tx() as c:
        call = c.one("SELECT c.*, c.id::text AS id, c.owner_org_id::text AS owner_org_id, c.counterpart_pct::float AS counterpart_pct"
                     " FROM calls c WHERE c.id = $1", ctx.path["call_id"])
        if not call:
            raise not_found("Edital/chamada")
        out = {"call": call}
        if ctx.principal.org_kind == "osc":
            if q.project_id and not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", q.project_id, ctx.org_id):
                raise not_found("Projeto")
            m = matching.evaluate_osc_call(c, ctx.org_id, matching.load_call(c, call["id"]), q.project_id)
            m["match_run_id"] = matching.persist(c, ctx.org_id, ctx.user_id, m, call["id"], q.project_id)
            out["match"] = m
            out["application"] = c.one("SELECT id::text AS id, status, origin FROM applications WHERE call_id = $1 AND osc_org_id = $2"
                                       " AND status NOT IN ('withdrawn','rejected') ORDER BY created_at DESC LIMIT 1", call["id"], ctx.org_id)
        if call["owner_org_id"] == ctx.principal.org_id:
            out["applications_count"] = c.scalar("SELECT count(*) FROM applications WHERE call_id = $1", call["id"])
    return out


def _call_values(body: S.CallIn, ctx: Ctx) -> dict:
    d = body.model_dump()
    d["requirements"] = Json(d["requirements"])
    d["steps_template"] = Json(d["steps_template"])
    d["weights"] = Json(d["weights"]) if d["weights"] else None
    d["funder_name"] = d["funder_name"] or ctx.principal.org_name
    if d["closes_at"] and d["opens_at"] and d["closes_at"] < d["opens_at"]:
        raise ApiError(422, "validation_error", "Encerramento anterior à abertura")
    return d


def _check_institutional_fields(c, d: dict) -> None:
    """Modalidade e naturezas jurídicas do edital devem existir no catálogo publicado (nada inventado pelo cliente)."""
    from ..services import institutional as inst
    cat = inst.catalog(c)
    if d.get("funding_modality") and d["funding_modality"] not in cat.get("funding_modality", {}):
        raise ApiError(422, "validation_error", "Modalidade fora do catálogo publicado", {"valid": sorted(cat.get("funding_modality", {}))})
    bad = [n for n in d.get("accepted_legal_natures") or [] if n not in cat.get("legal_nature", {})]
    if bad:
        raise ApiError(422, "validation_error", "Naturezas jurídicas fora do catálogo: " + ", ".join(bad), {"valid": sorted(cat.get("legal_nature", {}))})
    badq = [q for q in d.get("required_certifications") or [] if q not in cat.get("qualification_type", {})]
    if badq:
        raise ApiError(422, "validation_error", "Qualificações exigidas fora do catálogo: " + ", ".join(badq), {"valid": sorted(cat.get("qualification_type", {}))})


def _gov_must_be_verified(ctx: Ctx, c, status: str) -> None:
    if ctx.principal.org_kind == "government" and status == "open":
        if c.scalar("SELECT compliance_status FROM organizations WHERE id = $1", ctx.org_id) != "approved":
            raise ApiError(403, "government_not_verified", "Órgão público precisa ter o cadastro verificado pela administração antes de publicar editais")


@route("POST", "/v1/calls", body=S.CallIn, kinds=("company", "government"), min_role="manager", status=201, tags=T,
       summary="Cria programa/chamada própria (empresa) ou edital público (governo)")
def create_call(ctx: Ctx, body: S.CallIn):
    d = _call_values(body, ctx)
    with ctx.tx() as c:
        if ctx.principal.org_kind == "company":
            n = c.scalar("SELECT count(*) FROM calls WHERE owner_org_id = $1 AND status IN ('draft','open')", ctx.org_id)
            check_limit(c, ctx, "programs", n)
        _gov_must_be_verified(ctx, c, d["status"])
        _check_institutional_fields(c, d)
        sphere = d["sphere"] if ctx.principal.org_kind == "government" else "private"
        if ctx.principal.org_kind == "government" and sphere == "private":
            raise ApiError(422, "validation_error", "Órgão público deve informar a esfera (federal, estadual, municipal, local)")
        cid = c.scalar(
            "INSERT INTO calls(owner_org_id, source_type, sphere, instrument, funder_name, title, summary, description, url, causes, ods,"
            " territories, eligible_org_types, budget_total_cents, ticket_min_cents, ticket_max_cents, counterpart_pct, min_org_age_months,"
            " required_document_types, required_certifications, requirements, steps_template, opens_at, closes_at, status,"
            " managed_on_platform, weights, created_by, funding_modality, accepted_legal_natures, min_maturity)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::text[],$11::smallint[],$12::text[],$13::text[],$14::bigint,$15::bigint,$16::bigint,"
            " $17::numeric,$18::int,$19::text[],$20::text[],$21::jsonb,$22::jsonb,$23::timestamptz,$24::timestamptz,$25,$26::bool,$27::jsonb,$28,$29,$30::text[],$31::smallint)"
            " RETURNING id::text",
            ctx.org_id, "government" if ctx.principal.org_kind == "government" else "platform", sphere, d["instrument"], d["funder_name"],
            d["title"], d["summary"], d["description"], d["url"], d["causes"], d["ods"], d["territories"], d["eligible_org_types"],
            d["budget_total_cents"], d["ticket_min_cents"], d["ticket_max_cents"], d["counterpart_pct"], d["min_org_age_months"],
            d["required_document_types"], d["required_certifications"], d["requirements"], d["steps_template"], d["opens_at"],
            d["closes_at"], d["status"], d["managed_on_platform"], d["weights"], ctx.user_id, d["funding_modality"], d["accepted_legal_natures"], d["min_maturity"])
        ctx.audit(c, "call.created", "call", cid, {"status": d["status"], "sphere": sphere})
    return {"id": cid}


@route("PUT", "/v1/calls/{call_id}", body=S.CallIn, kinds=("company", "government"), min_role="manager", tags=T)
def update_call(ctx: Ctx, body: S.CallIn):
    d = _call_values(body, ctx)
    with ctx.tx() as c:
        cur = c.one("SELECT status, sphere FROM calls WHERE id = $1 AND owner_org_id = $2", ctx.path["call_id"], ctx.org_id)
        if not cur:
            raise not_found("Edital/chamada")
        _gov_must_be_verified(ctx, c, d["status"])
        _check_institutional_fields(c, d)
        sphere = d["sphere"] if ctx.principal.org_kind == "government" else "private"
        c.run("UPDATE calls SET instrument=$2, funder_name=$3, title=$4, summary=$5, description=$6, url=$7, causes=$8::text[],"
              " ods=$9::smallint[], territories=$10::text[], eligible_org_types=$11::text[], budget_total_cents=$12::bigint,"
              " ticket_min_cents=$13::bigint, ticket_max_cents=$14::bigint, counterpart_pct=$15::numeric, min_org_age_months=$16::int,"
              " required_document_types=$17::text[], required_certifications=$18::text[], requirements=$19::jsonb, steps_template=$20::jsonb,"
              " opens_at=$21::timestamptz, closes_at=$22::timestamptz, status=$23, managed_on_platform=$24::bool, weights=$25::jsonb,"
              " sphere=$26, funding_modality=$27, accepted_legal_natures=$28::text[], min_maturity=$29::smallint,"
              " criteria_version = CASE WHEN status = 'open' THEN 'c' || (coalesce(nullif(regexp_replace(criteria_version,'\\D','','g'),''),'1')::int + 1)::text"
              " ELSE criteria_version END WHERE id = $1",
              ctx.path["call_id"], d["instrument"], d["funder_name"], d["title"], d["summary"], d["description"], d["url"], d["causes"],
              d["ods"], d["territories"], d["eligible_org_types"], d["budget_total_cents"], d["ticket_min_cents"], d["ticket_max_cents"],
              d["counterpart_pct"], d["min_org_age_months"], d["required_document_types"], d["required_certifications"],
              d["requirements"], d["steps_template"], d["opens_at"], d["closes_at"], d["status"], d["managed_on_platform"],
              d["weights"], sphere, d["funding_modality"], d["accepted_legal_natures"], d["min_maturity"])
        ctx.audit(c, "call.updated", "call", ctx.path["call_id"], {"status": d["status"]})
    return {"id": ctx.path["call_id"]}


@route("GET", "/v1/calls/{call_id}/applications", kinds=("company", "government"), min_role="analyst", query=S.Pagination, tags=T,
       summary="Candidaturas recebidas, com compatibilidade explicada (shortlist)")
def call_applications(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        call = c.one("SELECT id::text AS id FROM calls WHERE id = $1 AND owner_org_id = $2", ctx.path["call_id"], ctx.org_id)
        if not call:
            raise not_found("Edital/chamada")
        rows = c.query("SELECT a.id::text AS id, a.status, a.requested_cents, a.submitted_at, a.updated_at, a.project_id::text AS project_id,"
                       " p.title AS project_title, o.legal_name AS osc_name, o.id::text AS osc_org_id, o.compliance_status"
                       " FROM applications a JOIN organizations o ON o.id = a.osc_org_id LEFT JOIN projects p ON p.id = a.project_id"
                       " WHERE a.call_id = $1 ORDER BY a.updated_at DESC LIMIT $2 OFFSET $3", call["id"], q.limit + 1, q.offset)
        full = matching.load_call(c, call["id"])
        for r in rows[: q.limit]:
            if r["project_id"]:
                proj = matching.load_project(c, r["project_id"])
                m = matching.evaluate_funder_project(c, ctx.org_id, proj, full)
                r["match"] = {k: m[k] for k in ("eligibility", "recommended_state", "score", "confidence")}
                r["match"]["blockers"] = [b["message"] for b in m["blockers"]]
    return page(rows, q.limit, q.offset)


# ------------------------------------------------------------------------------------------------ buscas salvas e alertas
@route("GET", "/v1/saved-searches", min_role="viewer", tags=("alerts",))
def list_saved(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, name, filters, notify, frequency, last_run_at, created_at,"
                                 " (SELECT count(*) FROM saved_search_hits h WHERE h.search_id = s.id) AS hits"
                                 " FROM saved_searches s WHERE org_id = $1 ORDER BY created_at DESC", ctx.org_id)}


@route("POST", "/v1/saved-searches", body=S.SavedSearchIn, min_role="member", feature="alerts.saved_search", status=201, tags=("alerts",),
       summary="Rastreio automático: salva filtros e notifica novos editais compatíveis (planos pagos)")
def create_saved(ctx: Ctx, body: S.SavedSearchIn):
    allowed = {"q", "sphere", "instrument", "cause", "territory", "min_amount_cents", "min_score"}
    bad = set(body.filters) - allowed
    if bad:
        raise ApiError(422, "validation_error", f"Filtros não suportados: {', '.join(sorted(bad))}")
    with ctx.tx() as c:
        n = c.scalar("SELECT count(*) FROM saved_searches WHERE org_id = $1", ctx.org_id)
        check_limit(c, ctx, "saved_searches", n)
        sid = c.scalar("INSERT INTO saved_searches(org_id, user_id, name, filters, notify, frequency) VALUES ($1,$2,$3,$4::jsonb,$5::bool,$6)"
                       " RETURNING id::text", ctx.org_id, ctx.user_id, body.name, Json(body.filters), body.notify, body.frequency)
        ctx.audit(c, "alerts.saved_search_created", "saved_search", sid)
    return {"id": sid}


@route("DELETE", "/v1/saved-searches/{search_id}", min_role="member", tags=("alerts",))
def delete_saved(ctx: Ctx):
    with ctx.tx() as c:
        if not c.run("DELETE FROM saved_searches WHERE id = $1 AND org_id = $2", ctx.path["search_id"], ctx.org_id):
            raise not_found("Busca salva")
    return None


@route("POST", "/v1/saved-searches/{search_id}/run", min_role="member", feature="alerts.saved_search", tags=("alerts",),
       summary="Executa agora o rastreio desta busca (normalmente executado pelo worker)")
def run_saved(ctx: Ctx):
    from ..jobs import run_saved_search
    with ctx.tx() as c:
        s = c.one("SELECT * FROM saved_searches WHERE id = $1 AND org_id = $2", ctx.path["search_id"], ctx.org_id)
        if not s:
            raise not_found("Busca salva")
        new = run_saved_search(c, s, notify_email=None)
    return {"new_matches": new}


# ------------------------------------------------------------------------------------------------ materiais (governo)
class MaterialQ(S.Pagination):
    category: str | None = None
    q: str | None = None


@route("GET", "/v1/materials", query=MaterialQ, min_role="viewer", tags=("government",),
       summary="Biblioteca de materiais governamentais e institucionais publicados")
def list_materials(ctx: Ctx, q: MaterialQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT m.id::text AS id, m.title, m.summary, m.category, m.url, m.document_id::text AS document_id, m.territories,"
                       " m.causes, m.status, m.published_at, o.legal_name AS publisher FROM materials m JOIN organizations o ON o.id = m.org_id"
                       " WHERE ($1::text IS NULL OR m.category = $1) AND ($2::text IS NULL OR m.title ILIKE '%' || $2 || '%')"
                       " ORDER BY m.published_at DESC NULLS LAST, m.created_at DESC LIMIT $3 OFFSET $4",
                       q.category, q.q, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/materials", body=S.MaterialIn, kinds=("government", "platform"), min_role="manager", status=201, tags=("government",))
def create_material(ctx: Ctx, body: S.MaterialIn):
    with ctx.tx() as c:
        if body.document_id and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2", body.document_id, ctx.org_id):
            raise not_found("Documento")
        if body.document_id and body.status == "published":
            c.run("UPDATE documents SET visibility = 'public' WHERE id = $1", body.document_id)
        mid = c.scalar("INSERT INTO materials(org_id, title, summary, category, url, document_id, territories, causes, status, published_at, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7::text[],$8::text[],$9, CASE WHEN $9 = 'published' THEN now() END, $10) RETURNING id::text",
                       ctx.org_id, body.title, body.summary, body.category, body.url, body.document_id, body.territories, body.causes,
                       body.status, ctx.user_id)
        ctx.audit(c, "material.created", "material", mid, {"status": body.status})
    return {"id": mid}
