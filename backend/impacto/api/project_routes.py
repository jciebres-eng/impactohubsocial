"""Projetos financiáveis (OSC): necessidade → orçamento → fracionamento em marcos → publicação.
Feed da empresa: projetos publicados ranqueados com explicação; favoritos, descarte com motivo e comparação."""
from __future__ import annotations

from ..db.pq import Json
from ..http import ApiError, Ctx, not_found, page, route
from ..services import geo, matching, risk
from ..services.audit import ledger
from ..services.entitlements import check_limit
from . import schemas as S

T = ("projects",)
COLS = ("p.id::text AS id, p.org_id::text AS org_id, p.title, p.summary, p.problem, p.objectives, p.methodology, p.causes, p.ods,"
        " p.esg_tags, p.territory, p.beneficiaries_count, p.beneficiaries_description, p.budget_total_cents, p.status, p.visibility,"
        " p.urgency, p.starts_on, p.ends_on, p.indicators, p.ai_assisted, p.published_at, p.created_at, p.updated_at")
ACTIVE = ("draft", "published", "funding", "funded", "in_execution")
# Janela de pontuação do feed: quantos candidatos recebem a avaliação explicável completa em uma consulta.
# É um limite DECLARADO na resposta, não um detalhe escondido — ver PERFORMANCE_REPORT.md.
SCORING_WINDOW = 200


def _get_own(c, ctx, pid: str) -> dict:
    p = c.one(f"SELECT {COLS} FROM projects p WHERE p.id = $1 AND p.org_id = $2", pid, ctx.org_id)
    if not p:
        raise not_found("Projeto")
    return p


def funding_summary(c, pid: str) -> dict:
    """Agregados (sem detalhar outros financiadores). Só chamado após o projeto ter sido lido sob RLS."""
    return c.one("SELECT * FROM project_funding($1)", pid)


@route("GET", "/v1/projects", kinds=("osc",), query=S.Pagination, min_role="viewer", tags=T, summary="Projetos da OSC")
def list_projects(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {COLS}, (SELECT count(*) FROM applications a WHERE a.project_id = p.id) AS applications"
                       " FROM projects p WHERE p.org_id = $1 ORDER BY p.updated_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
        for r in rows:
            r["funding"] = funding_summary(c, r["id"])
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/projects", body=S.ProjectIn, kinds=("osc",), min_role="member", status=201, tags=T)
def create_project(ctx: Ctx, body: S.ProjectIn):
    d = body.model_dump()
    with ctx.tx() as c:
        n = c.scalar("SELECT count(*) FROM projects WHERE org_id = $1 AND status = ANY($2::text[])", ctx.org_id, list(ACTIVE))
        check_limit(c, ctx, "active_projects", n)
        pid = c.scalar("INSERT INTO projects(org_id, title, summary, problem, objectives, methodology, causes, ods, esg_tags, territory,"
                       " beneficiaries_count, beneficiaries_description, budget_total_cents, urgency, starts_on, ends_on, indicators,"
                       " ai_assisted, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7::text[],$8::smallint[],$9::text[],$10,$11::int,$12,"
                       " coalesce($13::bigint, 0),$14,$15::date,$16::date,$17::jsonb,$18::bool,$19) RETURNING id::text",
                       ctx.org_id, d["title"], d["summary"], d["problem"], d["objectives"], d["methodology"], d["causes"], d["ods"],
                       d["esg_tags"], d["territory"], d["beneficiaries_count"], d["beneficiaries_description"], d["budget_total_cents"],
                       d["urgency"], d["starts_on"], d["ends_on"], Json(d["indicators"]), d["ai_assisted"], ctx.user_id)
        ctx.audit(c, "project.created", "project", pid, {"ai_assisted": d["ai_assisted"]})
    return {"id": pid}


@route("GET", "/v1/projects/{project_id}", min_role="viewer", tags=T,
       summary="Detalhe do projeto (OSC dona, financiadores com relação ou projeto publicado)")
def get_project(ctx: Ctx):
    pid = ctx.path["project_id"]
    with ctx.tx() as c:
        p = c.one(f"SELECT {COLS}, o.legal_name AS org_name, o.compliance_status AS org_compliance FROM projects p"
                  " JOIN organizations o ON o.id = p.org_id WHERE p.id = $1", pid)
        if not p:
            raise not_found("Projeto")
        p["budget_items"] = c.query("SELECT id::text AS id, description, category, quantity::float AS quantity, unit_cost_cents, total_cents"
                                    " FROM budget_items WHERE project_id = $1 ORDER BY created_at", pid)
        p["milestones"] = c.query("SELECT id::text AS id, seq, title, description, amount_cents, funded_cents, due_on, status"
                                  " FROM milestones WHERE project_id = $1 ORDER BY seq", pid)
        p["funding"] = funding_summary(c, pid)
        p["is_owner"] = p["org_id"] == ctx.principal.org_id
        loc = c.one("SELECT lat::float AS lat, lng::float AS lng, location_precision FROM projects WHERE id = $1", pid)
        p["location_public"] = geo.public_point(pid, loc["lat"], loc["lng"], loc["location_precision"])
        p["location_precision"] = loc["location_precision"]
        if p["is_owner"] and loc["lat"] is not None:
            p["location_private"] = {"lat": loc["lat"], "lng": loc["lng"]}
        if ctx.principal.org_kind in ("company", "individual") and not p["is_owner"]:
            m = matching.evaluate_funder_project(c, ctx.org_id, matching.load_project(c, pid))
            m["match_run_id"] = matching.persist(c, ctx.org_id, ctx.user_id, m, None, pid)
            p["match"] = m
            p["favorite"] = bool(c.one("SELECT 1 FROM favorites WHERE org_id = $1 AND project_id = $2", ctx.org_id, pid))
            p["my_application"] = c.one("SELECT id::text AS id, status FROM applications WHERE project_id = $1 AND funder_org_id = $2"
                                        " AND status NOT IN ('withdrawn','rejected') LIMIT 1", pid, ctx.org_id)
    return p


@route("PATCH", "/v1/projects/{project_id}", body=S.ProjectPatch, kinds=("osc",), min_role="member", tags=T)
def patch_project(ctx: Ctx, body: S.ProjectPatch):
    data = body.model_dump(exclude_unset=True)
    casts = {"causes": "::text[]", "ods": "::smallint[]", "esg_tags": "::text[]", "beneficiaries_count": "::int",
             "budget_total_cents": "::bigint", "starts_on": "::date", "ends_on": "::date", "indicators": "::jsonb", "ai_assisted": "::bool"}
    if not data:
        raise ApiError(422, "empty", "Nada para atualizar")
    with ctx.tx() as c:
        p = _get_own(c, ctx, ctx.path["project_id"])
        if p["status"] in ("completed", "cancelled"):
            raise ApiError(409, "project_closed", "Projeto encerrado não pode ser alterado")
        has_items = c.scalar("SELECT count(*) FROM budget_items WHERE project_id = $1", p["id"])
        if "budget_total_cents" in data and has_items:
            raise ApiError(409, "budget_from_items", "Orçamento é calculado pelos itens; edite os itens")
        sets, vals = [], [p["id"]]
        for k, v in data.items():
            vals.append(Json(v) if k == "indicators" else v)
            sets.append(f"{k} = ${len(vals)}{casts.get(k, '')}")
        c.run(f"UPDATE projects SET {', '.join(sets)} WHERE id = $1", *vals)
        ctx.audit(c, "project.updated", "project", p["id"], {"fields": sorted(data)})
    return {"id": p["id"]}


@route("DELETE", "/v1/projects/{project_id}", kinds=("osc",), min_role="admin", tags=T, summary="Exclui projeto em rascunho")
def delete_project(ctx: Ctx):
    with ctx.tx() as c:
        p = _get_own(c, ctx, ctx.path["project_id"])
        if p["status"] != "draft" or c.scalar("SELECT count(*) FROM applications WHERE project_id = $1", p["id"]):
            raise ApiError(409, "not_deletable", "Somente projetos em rascunho e sem candidaturas podem ser excluídos")
        c.run("DELETE FROM projects WHERE id = $1", p["id"])
        ctx.audit(c, "project.deleted", "project", p["id"])
    return None


@route("POST", "/v1/projects/{project_id}/budget-items", body=S.BudgetItemIn, kinds=("osc",), min_role="member", status=201, tags=T)
def add_item(ctx: Ctx, body: S.BudgetItemIn):
    with ctx.tx() as c:
        p = _get_own(c, ctx, ctx.path["project_id"])
        if p["status"] not in ("draft", "published"):
            raise ApiError(409, "budget_locked", "Orçamento bloqueado após início da captação; registre aditivo")
        iid = c.scalar("INSERT INTO budget_items(project_id, org_id, description, category, quantity, unit_cost_cents)"
                       " VALUES ($1,$2,$3,$4,$5::numeric,$6::bigint) RETURNING id::text", p["id"], ctx.org_id, body.description,
                       body.category, body.quantity, body.unit_cost_cents)
        ctx.audit(c, "project.budget_item_added", "project", p["id"], {"item": iid})
    return {"id": iid}


@route("DELETE", "/v1/projects/{project_id}/budget-items/{item_id}", kinds=("osc",), min_role="member", tags=T)
def del_item(ctx: Ctx):
    with ctx.tx() as c:
        p = _get_own(c, ctx, ctx.path["project_id"])
        if p["status"] not in ("draft", "published"):
            raise ApiError(409, "budget_locked", "Orçamento bloqueado após início da captação")
        if not c.run("DELETE FROM budget_items WHERE id = $1 AND project_id = $2", ctx.path["item_id"], p["id"]):
            raise not_found("Item")
    return None


@route("POST", "/v1/projects/{project_id}/milestones", body=S.MilestoneIn, kinds=("osc",), min_role="member", status=201, tags=T,
       summary="Fracionamento: marcos/etapas com valor e prazo (soma ≤ orçamento)")
def add_milestone(ctx: Ctx, body: S.MilestoneIn):
    with ctx.tx() as c:
        p = _get_own(c, ctx, ctx.path["project_id"])
        total = c.scalar("SELECT coalesce(sum(amount_cents),0) FROM milestones WHERE project_id = $1", p["id"])
        budget = c.scalar("SELECT budget_total_cents FROM projects WHERE id = $1", p["id"])
        if total + body.amount_cents > budget:
            raise ApiError(422, "milestones_exceed_budget", f"Soma dos marcos excederia o orçamento ({budget / 100:.2f})")
        seq = c.scalar("SELECT coalesce(max(seq),0) + 1 FROM milestones WHERE project_id = $1", p["id"])
        mid = c.scalar("INSERT INTO milestones(project_id, org_id, seq, title, description, amount_cents, due_on, status)"
                       " VALUES ($1,$2,$3::int,$4,$5,$6::bigint,$7::date, CASE WHEN $8 = 'draft' THEN 'planned' ELSE 'open' END) RETURNING id::text",
                       p["id"], ctx.org_id, seq, body.title, body.description, body.amount_cents, body.due_on, p["status"])
        if p["visibility"] == "published":
            ledger(c, project_id=p["id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="milestone_defined",
                   amount_cents=body.amount_cents, ref_type="milestone", ref_id=mid, payload={"seq": seq, "title": body.title})
        ctx.audit(c, "project.milestone_added", "project", p["id"], {"milestone": mid})
    return {"id": mid, "seq": seq}


@route("DELETE", "/v1/projects/{project_id}/milestones/{milestone_id}", kinds=("osc",), min_role="member", tags=T)
def del_milestone(ctx: Ctx):
    with ctx.tx() as c:
        p = _get_own(c, ctx, ctx.path["project_id"])
        m = c.one("SELECT funded_cents FROM milestones WHERE id = $1 AND project_id = $2", ctx.path["milestone_id"], p["id"])
        if not m:
            raise not_found("Marco")
        if m["funded_cents"] > 0:
            raise ApiError(409, "milestone_funded", "Marco com recursos comprometidos não pode ser removido")
        c.run("DELETE FROM milestones WHERE id = $1", ctx.path["milestone_id"])
    return None


@route("POST", "/v1/projects/{project_id}/publish", kinds=("osc",), min_role="manager", tags=T,
       summary="Publica o projeto no feed de financiadores (exige dados mínimos e e-mail confirmado)")
def publish(ctx: Ctx):
    with ctx.tx() as c:
        risk.ensure_not_blocked(c, ctx.org_id)
        # Medida de moderação em vigor também restringe — até a v0.20.0 não restringia nada.
        from ..network import enforcement as ENF
        ENF.ensure_allowed(c, capability="publish_project", org_id=ctx.org_id)
        p = _get_own(c, ctx, ctx.path["project_id"])
        problems = []
        if not p["summary"]:
            problems.append("Resumo")
        if not p["causes"]:
            problems.append("Causas")
        if not p["budget_total_cents"]:
            problems.append("Orçamento")
        if not p["beneficiaries_count"]:
            problems.append("Número de beneficiários")
        if problems:
            raise ApiError(422, "incomplete_project", "Complete antes de publicar: " + ", ".join(problems), {"missing": problems})
        c.run("UPDATE projects SET visibility = 'published', status = CASE WHEN status = 'draft' THEN 'published' ELSE status END,"
              " published_at = coalesce(published_at, now()) WHERE id = $1", p["id"])
        c.run("UPDATE milestones SET status = 'open' WHERE project_id = $1 AND status = 'planned'", p["id"])
        items = c.query("SELECT description, quantity::float AS quantity, unit_cost_cents FROM budget_items WHERE project_id = $1", p["id"])
        ledger(c, project_id=p["id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="need_published",
               amount_cents=p["budget_total_cents"], ref_type="project", ref_id=p["id"], payload={"title": p["title"]})
        ledger(c, project_id=p["id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="budget_defined",
               amount_cents=p["budget_total_cents"], payload={"items": items})
        ctx.audit(c, "project.published", "project", p["id"])
        # v0.27.0 — participação de autoria aceita vira CONSOLIDADA quando o projeto é publicado
        from ..trust import economy as ECO
        ECO.consolidate_for_project(c, project_id=p["id"], actor_user_id=ctx.user_id)
    return {"id": p["id"], "visibility": "published"}


@route("POST", "/v1/projects/{project_id}/unpublish", kinds=("osc",), min_role="manager", tags=T)
def unpublish(ctx: Ctx):
    with ctx.tx() as c:
        p = _get_own(c, ctx, ctx.path["project_id"])
        if c.scalar("SELECT count(*) FROM commitments WHERE project_id = $1 AND status <> 'cancelled'", p["id"]):
            raise ApiError(409, "has_commitments", "Projeto com aportes comprometidos permanece visível aos financiadores")
        c.run("UPDATE projects SET visibility = 'private', status = CASE WHEN status = 'published' THEN 'draft' ELSE status END WHERE id = $1", p["id"])
        ctx.audit(c, "project.unpublished", "project", p["id"])
    return {"id": p["id"], "visibility": "private"}


# ------------------------------------------------------------------------------------------------ feed da empresa
@route("GET", "/v1/feed/projects", kinds=("company", "individual"), query=S.FeedQ, min_role="viewer", feature="feed.projects", tags=("feed",),
       summary="Projetos publicados ranqueados por compatibilidade (explicável). Plano não altera ordem nem elegibilidade.")
def feed(ctx: Ctx, q: S.FeedQ):
    with ctx.tx(readonly=True) as c:
        funder = c.one("SELECT * FROM funder_profiles WHERE org_id = $1", ctx.org_id) or {}
        call = matching.load_call(c, q.call_id) if q.call_id else None
        if q.call_id and (not call or not c.one("SELECT 1 FROM calls WHERE id = $1 AND owner_org_id = $2", q.call_id, ctx.org_id)):
            raise not_found("Programa")
        behavior = matching.funder_behavior(c, ctx.org_id)
        # ETAPA 1 — BUSCA DE CANDIDATOS. Quando o financiador não pediu para ver os bloqueados, a elegibilidade dura
        # que CABE em SQL (política de causa/território excluídos e compliance reprovado) já tira o candidato aqui:
        # ele seria descartado depois de qualquer forma, e avaliar centenas de projetos que não entram na lista era o
        # custo dominante da requisição (medido em PERFORMANCE_REPORT.md). Com `include_blocked`, nada é pré-filtrado.
        prefilter = "" if q.include_blocked else (
            " AND o.compliance_status NOT IN ('rejected','suspended')"
            " AND NOT (p.causes && coalesce($4::text[], '{}'))"
            " AND NOT EXISTS (SELECT 1 FROM unnest(coalesce($5::text[], '{}')) t"
            "                  WHERE p.territory = t OR p.territory LIKE t || '-%')")
        cands = c.query("SELECT p.id::text AS id FROM projects p JOIN organizations o ON o.id = p.org_id"
                        " WHERE p.visibility = 'published' AND p.status IN ('published','funding')"
                        " AND p.org_id <> $1"
                        " AND ($2::text IS NULL OR $2 = ANY(p.causes)) AND ($3::text IS NULL OR p.territory LIKE $3 || '%')"
                        " AND NOT EXISTS (SELECT 1 FROM feed_feedback f WHERE f.org_id = $1 AND f.target_type = 'project'"
                        "   AND f.target_id = p.id AND f.action = 'dismiss')" + prefilter +
                        # afinidade barata só para ESCOLHER a janela de pontuação; a ordem final é a do motor
                        " ORDER BY (p.causes && coalesce($4::text[], '{}')) DESC,"
                        " cardinality(p.causes) DESC, p.published_at DESC LIMIT $6",
                        ctx.org_id, q.cause, q.territory, funder.get("excluded_causes") or [],
                        funder.get("excluded_territories") or [], SCORING_WINDOW)
        # ETAPA 2 — CARGA EM LOTE dos candidatos (3 consultas, não 3 por candidato) e memória por organização.
        projects = matching.load_projects(c, [cand["id"] for cand in cands])
        cache = matching.FeedCache()
        scored = []
        hidden = 0
        for cand in cands:
            proj = projects.get(cand["id"])
            if proj is None:
                continue
            m = matching.evaluate_funder_project(c, ctx.org_id, proj, call, funder=funder, behavior=behavior,
                                                 cache=cache)
            if m["eligibility"] == "blocked" and not q.include_blocked:
                hidden += 1
                continue
            scored.append((proj, m))
        order = {"eligible": 0, "needs_review": 1, "blocked": 2}
        scored.sort(key=lambda x: (order[x[1]["eligibility"]], -(x[1]["score"] or 0), x[0]["id"]))
        out = []
        favs = {r["project_id"] for r in c.query("SELECT project_id::text AS project_id FROM favorites WHERE org_id = $1", ctx.org_id)}
        window = scored[q.offset: q.offset + q.limit + 1]
        orgs = {r["id"]: r for r in c.query("SELECT id::text AS id, legal_name, city, uf, compliance_status"
                                            " FROM organizations WHERE id = ANY($1::uuid[])",
                                            [p["org_id"] for p, _ in window])}
        for proj, m in window:
            org = {k: v for k, v in (orgs.get(proj["org_id"]) or {}).items() if k != "id"}
            out.append({"project": {k: proj[k] for k in ("id", "title", "causes", "ods", "territory", "beneficiaries_count",
                                                           "budget_total_cents", "funded_cents", "urgency", "status")},
                        "organization": org, "favorite": proj["id"] in favs,
                        "match": {k: m[k] for k in ("eligibility", "recommended_state", "score", "confidence", "why_match", "why_not",
                                                    "risks", "missing_data", "next_action", "blockers")}})
    return page(out, q.limit, q.offset) | {
        "hidden_blocked": hidden, "scoring_window": SCORING_WINDOW, "candidates_scored": len(cands),
        "engine_note": "Ordenação: elegibilidade, depois compatibilidade. Plano/voucher não interferem.",
        "window_note": f"A pontuação explicável é calculada sobre até {SCORING_WINDOW} candidatos por consulta "
                       "(busca de candidatos por afinidade de causa e data). Use causa/território para estreitar."}


@route("POST", "/v1/feed/projects/{project_id}/favorite", kinds=("company", "individual"), min_role="analyst", tags=("feed",))
def favorite(ctx: Ctx):
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM projects WHERE id = $1", ctx.path["project_id"]):
            raise not_found("Projeto")
        c.run("INSERT INTO favorites(org_id, project_id, created_by) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING",
              ctx.org_id, ctx.path["project_id"], ctx.user_id)
    return {"favorite": True}


@route("DELETE", "/v1/feed/projects/{project_id}/favorite", kinds=("company", "individual"), min_role="analyst", tags=("feed",))
def unfavorite(ctx: Ctx):
    with ctx.tx() as c:
        c.run("DELETE FROM favorites WHERE org_id = $1 AND project_id = $2", ctx.org_id, ctx.path["project_id"])
    return {"favorite": False}


@route("POST", "/v1/feed/projects/{project_id}/feedback", body=S.FeedFeedbackIn, kinds=("company", "individual"), min_role="analyst", tags=("feed",),
       summary="Salvar ou descartar com motivo (sinal de preferência para o ranking do próprio financiador)")
def feed_feedback(ctx: Ctx, body: S.FeedFeedbackIn):
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM projects WHERE id = $1", ctx.path["project_id"]):
            raise not_found("Projeto")
        c.run("INSERT INTO feed_feedback(org_id, target_type, target_id, action, reason, created_by) VALUES ($1,'project',$2,$3,$4,$5)"
              " ON CONFLICT (org_id, target_type, target_id) DO UPDATE SET action = EXCLUDED.action, reason = EXCLUDED.reason",
              ctx.org_id, ctx.path["project_id"], body.action, body.reason, ctx.user_id)
    return {"action": body.action}


class CompareQ(S.In):
    ids: str


@route("GET", "/v1/feed/compare", kinds=("company", "individual"), query=CompareQ, min_role="viewer", tags=("feed",),
       summary="Compara até 4 projetos lado a lado com os mesmos critérios")
def compare(ctx: Ctx, q: CompareQ):
    ids = [x for x in q.ids.split(",") if x][:4]
    if len(ids) < 2:
        raise ApiError(422, "validation_error", "Informe de 2 a 4 projetos")
    out = []
    with ctx.tx(readonly=True) as c:
        for pid in ids:
            proj = matching.load_project(c, pid)
            if not proj:
                raise not_found("Projeto")
            m = matching.evaluate_funder_project(c, ctx.org_id, proj)
            org = c.one("SELECT legal_name, compliance_status FROM organizations WHERE id = $1", proj["org_id"])
            out.append({"project": {k: proj[k] for k in ("id", "title", "causes", "territory", "beneficiaries_count", "budget_total_cents",
                                                         "funded_cents", "urgency")}, "organization": org,
                        "match": {k: m[k] for k in ("eligibility", "score", "confidence", "signals", "risks", "missing_data")}})
    return {"items": out}
