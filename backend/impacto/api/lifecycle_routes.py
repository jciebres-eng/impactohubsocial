"""Ideia → projeto, máquina de situações, linha de tempo, retratos comparáveis e registro de riscos.

Três decisões que valem explicação:

* A ideia NUNCA é apagada ao virar projeto. Ela fica, com ``promoted_project_id``, e o projeto guarda
  ``origin_idea_id``: a origem de um projeto é parte da história dele.
* A linha de tempo não é uma segunda tabela de histórico. É a trilha ``ledger_entries``, encadeada por hash desde a
  migration 0002 e verificável por ``ledger_verify``. Histórico que pode ser reescrito não é histórico.
* O risco apontado por regra entra como ``system_identified`` e nunca se mistura com o risco que a equipe declarou.
"""
from __future__ import annotations

from ..core import lifecycle as LC
from ..http import ApiError, Ctx, not_found, page, route
from ..services.audit import ledger
from ..services.entitlements import check_limit
from . import core_schemas as C
from . import schemas as S

T = ("lifecycle",)
TI = ("ideas",)
IDEA_COLS = ("id::text AS id, title, problem, hypothesis, audience, territory, solution_idea, expected_impact, stage,"
             " causes, ods, promoted_project_id::text AS promoted_project_id, promoted_at,"
             " owner_user_id::text AS owner_user_id, created_at, updated_at")
ACTIVE_PROJECT = ("draft", "diagnosing", "structuring", "ready", "published", "funding", "funded", "submitted",
                  "in_execution", "monitoring")


def _own_project(c, ctx: Ctx, pid: str) -> dict:
    """Projeto da própria organização. Sob RLS: outra organização recebe 404, nunca 403 com dado vazando."""
    p = c.one("SELECT id::text AS id, org_id::text AS org_id, title, status FROM projects WHERE id = $1 AND org_id = $2",
              pid, ctx.org_id)
    if not p:
        raise not_found("Projeto")
    return p


def _own_idea(c, ctx: Ctx, iid: str) -> dict:
    i = c.one(f"SELECT {IDEA_COLS} FROM ideas WHERE id = $1 AND org_id = $2", iid, ctx.org_id)
    if not i:
        raise not_found("Ideia")
    return i


# ------------------------------------------------------------------------------------------------ ideias
@route("GET", "/v1/ideas", query=S.Pagination, min_role="viewer", tags=TI, summary="Ideias da organização")
def list_ideas(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {IDEA_COLS} FROM ideas WHERE org_id = $1 ORDER BY updated_at DESC LIMIT $2 OFFSET $3",
                       ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/ideas", body=C.IdeaIn, min_role="member", status=201, tags=TI,
       summary="Registra uma ideia (ainda não é projeto, e não consome cota de projeto)")
def create_idea(ctx: Ctx, body: C.IdeaIn):
    d = body.model_dump()
    with ctx.tx() as c:
        iid = c.scalar("INSERT INTO ideas(org_id, title, problem, hypothesis, audience, territory, solution_idea,"
                       " expected_impact, stage, causes, ods, owner_user_id, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::text[],$11::smallint[],$12,$12) RETURNING id::text",
                       ctx.org_id, d["title"], d["problem"], d["hypothesis"], d["audience"], d["territory"],
                       d["solution_idea"], d["expected_impact"], d["stage"], d["causes"], d["ods"], ctx.user_id)
        ctx.audit(c, "idea.created", "idea", iid, {"stage": d["stage"]})
    return {"id": iid}


@route("GET", "/v1/ideas/{idea_id}", min_role="viewer", tags=TI)
def get_idea(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return _own_idea(c, ctx, ctx.path["idea_id"])


@route("PUT", "/v1/ideas/{idea_id}", body=C.IdeaIn, min_role="member", tags=TI)
def update_idea(ctx: Ctx, body: C.IdeaIn):
    d = body.model_dump()
    iid = ctx.path["idea_id"]
    with ctx.tx() as c:
        cur = _own_idea(c, ctx, iid)
        if cur["stage"] == "promoted":
            raise ApiError(409, "already_promoted", "Esta ideia já virou projeto. Edite o projeto, não a ideia.")
        c.run("UPDATE ideas SET title = $2, problem = $3, hypothesis = $4, audience = $5, territory = $6,"
              " solution_idea = $7, expected_impact = $8, stage = $9, causes = $10::text[], ods = $11::smallint[]"
              " WHERE id = $1", iid, d["title"], d["problem"], d["hypothesis"], d["audience"], d["territory"],
              d["solution_idea"], d["expected_impact"], d["stage"], d["causes"], d["ods"])
        ctx.audit(c, "idea.updated", "idea", iid, {"stage": d["stage"]})
    return {"id": iid}


@route("POST", "/v1/ideas/{idea_id}/promote", body=C.PromoteIn, kinds=("osc",), min_role="member", status=201, tags=TI,
       summary="Transforma a ideia em projeto sem apagar a ideia (o projeto guarda a origem)")
def promote_idea(ctx: Ctx, body: C.PromoteIn):
    iid = ctx.path["idea_id"]
    # Contexto privilegiado: `promoted_project_id`/`promoted_at` são colunas guardadas (a organização não as escreve
    # à mão). Todo acesso continua filtrado por org_id explícito — o contexto de sistema não dispensa o filtro.
    with ctx.system_tx() as c:
        idea = c.one(f"SELECT {IDEA_COLS} FROM ideas WHERE id = $1 AND org_id = $2", iid, ctx.org_id)
        if not idea:
            raise not_found("Ideia")
        if idea["stage"] == "promoted":
            raise ApiError(409, "already_promoted", "Esta ideia já virou projeto",
                           {"project_id": idea["promoted_project_id"]})
        n = c.scalar("SELECT count(*) FROM projects WHERE org_id = $1 AND status = ANY($2::text[])",
                     ctx.org_id, list(ACTIVE_PROJECT))
        check_limit(c, ctx, "active_projects", n)
        # `projects.territory` é NOT NULL: herda da ideia e, na falta, usa a UF da organização.
        territory = idea["territory"] or c.scalar(
            "SELECT CASE WHEN uf IS NULL THEN 'BR' ELSE 'BR-' || uf END FROM organizations WHERE id = $1",
            ctx.org_id) or "BR"
        title = (body.title or idea["title"])[:200]
        summary = body.summary or (idea["expected_impact"] or idea["solution_idea"] or idea["title"])
        pid = c.scalar("INSERT INTO projects(org_id, title, summary, problem, objectives, causes, ods, territory,"
                       " beneficiaries_description, status, origin_idea_id, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6::text[],$7::smallint[],$8,$9,'draft',$10,$11) RETURNING id::text",
                       ctx.org_id, title, summary[:2000], idea["problem"], idea["solution_idea"], idea["causes"],
                       idea["ods"], territory, idea["audience"], iid, ctx.user_id)
        c.run("UPDATE ideas SET stage = 'promoted', promoted_project_id = $2, promoted_at = now() WHERE id = $1",
              iid, pid)
        ledger(c, project_id=pid, org_id=ctx.org_id, actor=ctx.user_id, entry_type="idea_promoted", ref_type="idea",
               ref_id=iid, payload={"idea_title": idea["title"], "stage_before": idea["stage"]})
        ledger(c, project_id=pid, org_id=ctx.org_id, actor=ctx.user_id, entry_type="project_created",
               ref_type="project", ref_id=pid, payload={"origin": "idea"})
        ctx.audit(c, "idea.promoted", "project", pid, {"idea_id": iid})
    return {"id": pid, "idea_id": iid,
            "note": "A ideia continua registrada e aponta para o projeto criado."}


# ------------------------------------------------------------------------------------------------ situações
@route("GET", "/v1/project-status-graph", min_role="viewer", tags=T,
       summary="Máquina de situações do projeto (é DADO no banco, não código: um gatilho recusa o que não está aqui)")
def status_graph(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT from_status, to_status, requires_reason, note FROM project_status_graph"
                       " ORDER BY from_status, to_status")
    return {"transitions": rows, "labels": LC.LABELS,
            "phases": {"building": list(LC.BUILDING), "open": list(LC.OPEN), "execution": list(LC.EXECUTION),
                       "closed": list(LC.CLOSED)},
            "note": "Projeto arquivado só reabre por exceção, e a reabertura exige motivo registrado."}


@route("GET", "/v1/projects/{project_id}/lifecycle", min_role="viewer", tags=T,
       summary="Situação atual, para onde pode ir e o que já aconteceu")
def get_lifecycle(ctx: Ctx):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        p = _own_project(c, ctx, pid)
        return {"project_id": pid, "status": p["status"], "label": LC.LABELS.get(p["status"], p["status"]),
                "phase": LC.phase(p["status"]),
                "allowed": LC.allowed_from(c, p["status"]), "history": LC.transitions(c, pid)}


@route("POST", "/v1/projects/{project_id}/transitions", body=C.TransitionIn, min_role="member", tags=T,
       summary="Muda a situação do projeto (recusa explícita quando a máquina não permite)")
def create_transition(ctx: Ctx, body: C.TransitionIn):
    pid = ctx.path["project_id"]
    with ctx.tx() as c:
        _own_project(c, ctx, pid)
        if body.evidence_document_id and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2",
                                                   body.evidence_document_id, ctx.org_id):
            raise not_found("Documento de evidência")
        out = LC.transition(c, project_id=pid, org_id=ctx.org_id, to_status=body.to_status, actor_user_id=ctx.user_id,
                            reason=body.reason, evidence_document_id=body.evidence_document_id)
        if out.get("changed"):
            ctx.audit(c, "project.status_changed", "project", pid, {"from": out["from"], "to": out["status"]})
    return out


# ------------------------------------------------------------------------------------------------ linha de tempo
@route("GET", "/v1/projects/{project_id}/timeline", query=S.Pagination, min_role="viewer", tags=T,
       summary="Linha de tempo imutável (trilha encadeada por hash)")
def get_timeline(ctx: Ctx, q: S.Pagination):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        _own_project(c, ctx, pid)
        rows = LC.timeline(c, pid, limit=q.limit + 1, offset=q.offset)
    out = page(rows, q.limit, q.offset)
    out["note"] = "Cada entrada guarda o hash da anterior. Nada é editado nem removido — correção entra como novo fato."
    return out


@route("GET", "/v1/projects/{project_id}/timeline/integrity", min_role="viewer", tags=T,
       summary="Confere o encadeamento da linha de tempo")
def timeline_integrity(ctx: Ctx):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        _own_project(c, ctx, pid)
        return LC.timeline_integrity(c, pid)


# ------------------------------------------------------------------------------------------------ retratos
@route("GET", "/v1/projects/{project_id}/snapshots", query=S.Pagination, min_role="viewer", tags=T)
def list_snapshots(ctx: Ctx, q: S.Pagination):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        _own_project(c, ctx, pid)
        rows = c.query("SELECT id::text AS id, label, reason, state_sha256, ledger_seq, taken_at,"
                       " taken_by::text AS taken_by, user_display_name(taken_by) AS taken_by_name"
                       " FROM project_snapshots WHERE project_id = $1 ORDER BY taken_at DESC LIMIT $2 OFFSET $3",
                       pid, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/projects/{project_id}/snapshots", body=C.SnapshotIn, min_role="member", status=201, tags=T,
       summary="Guarda um retrato comparável do projeto neste instante")
def create_snapshot(ctx: Ctx, body: C.SnapshotIn):
    pid = ctx.path["project_id"]
    with ctx.tx() as c:
        _own_project(c, ctx, pid)
        out = LC.take_snapshot(c, project_id=pid, org_id=ctx.org_id, label=body.label, reason=body.reason,
                               taken_by=ctx.user_id)
        ctx.audit(c, "project.snapshot", "project", pid, {"snapshot_id": out["id"], "label": body.label})
    return out


@route("GET", "/v1/projects/{project_id}/snapshots/compare", query=C.CompareQ, min_role="viewer", tags=T,
       summary="Compara dois retratos campo a campo (o que mudou, entrou e saiu)")
def compare_snapshots(ctx: Ctx, q: C.CompareQ):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        _own_project(c, ctx, pid)
        out = LC.compare_snapshots(c, q.a, q.b)
    if not out.get("found"):
        raise ApiError(404, "not_found", out.get("reason") or "Retrato não encontrado")
    return out


@route("GET", "/v1/projects/{project_id}/state", min_role="viewer", tags=T,
       summary="Estado comparável do projeto agora (mesma estrutura dos retratos)")
def project_state(ctx: Ctx):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        _own_project(c, ctx, pid)
        return {"snapshot_version": LC.SNAPSHOT_VERSION, "state": LC.build_state(c, pid)}


# ------------------------------------------------------------------------------------------------ riscos
RISK_COLS = ("id::text AS id, code, category, title, description, probability, impact, severity, origin, mitigation,"
             " owner_user_id::text AS owner_user_id, user_display_name(owner_user_id) AS owner_name, status,"
             " review_date, resolved_at, resolution_note, created_at, updated_at")


@route("GET", "/v1/projects/{project_id}/risks", query=S.Pagination, min_role="viewer", tags=T)
def list_risks(ctx: Ctx, q: S.Pagination):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        _own_project(c, ctx, pid)
        rows = c.query(f"SELECT {RISK_COLS} FROM project_risks WHERE project_id = $1"
                       " ORDER BY CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2"
                       " ELSE 3 END, created_at DESC LIMIT $2 OFFSET $3", pid, q.limit + 1, q.offset)
    out = page(rows, q.limit, q.offset)
    out["origins"] = {"declared": "declarado pela equipe",
                      "system_identified": "apontado por regra da plataforma (indício, não veredito)"}
    return out


@route("POST", "/v1/projects/{project_id}/risks", body=C.RiskIn, min_role="member", status=201, tags=T)
def create_risk(ctx: Ctx, body: C.RiskIn):
    pid, d = ctx.path["project_id"], body.model_dump()
    with ctx.tx() as c:
        _own_project(c, ctx, pid)
        severity = LC.SEVERITY_MATRIX[(d["probability"], d["impact"])]
        rid = c.scalar("INSERT INTO project_risks(project_id, org_id, category, title, description, probability,"
                       " impact, severity, origin, mitigation, owner_user_id, review_date, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'declared',$9,$10,$11::date,$12) RETURNING id::text",
                       pid, ctx.org_id, d["category"], d["title"], d["description"], d["probability"], d["impact"],
                       severity, d["mitigation"], d["owner_user_id"], d["review_date"], ctx.user_id)
        ledger(c, project_id=pid, org_id=ctx.org_id, actor=ctx.user_id, entry_type="risk_created", ref_type="risk",
               ref_id=rid, payload={"severity": severity, "origin": "declared", "category": d["category"]})
        ctx.audit(c, "project.risk_created", "risk", rid, {"severity": severity})
    return {"id": rid, "severity": severity}


@route("PUT", "/v1/projects/{project_id}/risks/{risk_id}", body=C.RiskUpdateIn, min_role="member", tags=T,
       summary="Atualiza o risco (a origem nunca muda: risco apontado por regra não passa a declarado)")
def update_risk(ctx: Ctx, body: C.RiskUpdateIn):
    pid, rid = ctx.path["project_id"], ctx.path["risk_id"]
    d = {k: v for k, v in body.model_dump().items() if v is not None}
    if not d:
        raise ApiError(422, "validation_error", "Nada para atualizar")
    with ctx.tx() as c:
        _own_project(c, ctx, pid)
        cur = c.one("SELECT id::text AS id, probability, impact, status, origin FROM project_risks"
                    " WHERE id = $1 AND project_id = $2", rid, pid)
        if not cur:
            raise not_found("Risco")
        prob = d.get("probability", cur["probability"])
        imp = d.get("impact", cur["impact"])
        status = d.get("status", cur["status"])
        if status in ("resolved", "dismissed") and not (d.get("resolution_note") or "").strip():
            raise ApiError(422, "reason_required", "Encerrar um risco exige registrar o motivo.")
        c.run("UPDATE project_risks SET description = coalesce($3, description), probability = $4, impact = $5,"
              " severity = $6, mitigation = coalesce($7, mitigation), owner_user_id = coalesce($8, owner_user_id),"
              " review_date = coalesce($9::date, review_date), status = $10,"
              " resolution_note = coalesce($11, resolution_note),"
              " resolved_at = CASE WHEN $10 IN ('resolved','dismissed') THEN coalesce(resolved_at, now()) END"
              " WHERE id = $1 AND project_id = $2", rid, pid, d.get("description"), prob, imp,
              LC.SEVERITY_MATRIX[(prob, imp)], d.get("mitigation"), d.get("owner_user_id"), d.get("review_date"),
              status, d.get("resolution_note"))
        if status != cur["status"] and status in ("resolved", "dismissed"):
            ledger(c, project_id=pid, org_id=ctx.org_id, actor=ctx.user_id, entry_type="risk_resolved",
                   ref_type="risk", ref_id=rid, payload={"status": status, "automatic": False})
        ctx.audit(c, "project.risk_updated", "risk", rid, {"status": status})
    return {"id": rid, "severity": LC.SEVERITY_MATRIX[(prob, imp)], "status": status, "origin": cur["origin"]}


@route("POST", "/v1/projects/{project_id}/risks/scan", min_role="member", tags=T,
       summary="Aplica as regras de risco sobre o projeto (indícios, revisados por pessoa)")
def scan_project_risks(ctx: Ctx):
    pid = ctx.path["project_id"]
    with ctx.tx() as c:
        _own_project(c, ctx, pid)
        out = LC.scan_risks(c, project_id=pid, org_id=ctx.org_id, actor_user_id=ctx.user_id)
        ctx.audit(c, "project.risk_scan", "project", pid,
                  {"identified": len(out["identified"]), "auto_resolved": len(out["auto_resolved"])})
    return out


@route("GET", "/v1/risk-rules", min_role="viewer", tags=T, summary="Regras de risco aplicadas (abertas a quem usa)")
def risk_rules(ctx: Ctx):
    return {"version": LC.RISK_RULES_VERSION,
            "rules": [{"code": code, "category": cat, "title": title, "probability": prob, "impact": imp,
                       "severity": LC.SEVERITY_MATRIX[(prob, imp)]}
                      for code, cat, title, prob, imp, _ in LC.RISK_RULES],
            "note": "Regra aponta indício a partir do que a plataforma conhece. A avaliação final é humana."}


# ------------------------------------------------------------------------------------------------ retorno do match
@route("POST", "/v1/match-runs/{match_run_id}/feedback", body=C.MatchFeedbackIn, min_role="member", status=201,
       tags=("match",), summary="Retorno humano sobre uma recomendação (nada é treinado automaticamente)")
def match_feedback(ctx: Ctx, body: C.MatchFeedbackIn):
    from ..services import matching
    with ctx.tx() as c:
        out = matching.record_feedback(c, match_run_id=ctx.path["match_run_id"], org_id=ctx.org_id,
                                       feedback=body.feedback, reason=body.reason, actor_user_id=ctx.user_id)
        ctx.audit(c, "match.feedback", "match_run", ctx.path["match_run_id"], {"feedback": body.feedback})
    return out


@route("GET", "/v1/match-runs/{match_run_id}/feedback", min_role="viewer", tags=("match",))
def get_match_feedback(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        row = c.one("SELECT feedback, reason, at, actor_user_id::text AS actor_user_id,"
                    " user_display_name(actor_user_id) AS actor_name FROM match_feedback"
                    " WHERE match_run_id = $1 AND org_id = $2", ctx.path["match_run_id"], ctx.org_id)
    return row or {"feedback": None}
