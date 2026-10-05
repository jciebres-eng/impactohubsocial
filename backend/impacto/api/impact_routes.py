"""Impacto: ODS normalizado, catálogo de indicadores, indicadores do projeto e valores (reportado × validado), Impact Graph com
tipos de ligação distintos, camada agregada de determinantes sociais e diagnóstico estruturado da OSC.

Linguagem: "indicadores reportados" e "evidência de alinhamento aos ODS" — nunca "impacto comprovado" sem validação externa.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..db.pq import Json
from ..http import ApiError, Ctx, not_found, page, route
from ..services.audit import ledger
from . import schemas as S

T = ("impact",)
_DET = json.loads((Path(__file__).resolve().parents[3] / "config" / "determinants.json").read_text(encoding="utf-8"))
LINK_LEGEND = {
    "observed_evidence": "Evidência observada (há evidência anexada)",
    "correlation": "Correlação (dados que variam juntos; não prova causa)",
    "hypothesis": "Hipótese (teoria de mudança, ainda não testada)",
    "association": "Associação (relação plausível documentada)",
    "inference": "Inferência (conclusão a partir de dados indiretos)",
    "validated_causality": "Causalidade validada (revisão externa + evidência)",
}


def _owned_project(c, ctx, pid: str) -> dict:
    p = c.one("SELECT id::text AS id, status FROM projects WHERE id = $1 AND org_id = $2", pid, ctx.org_id)
    if not p:
        raise not_found("Projeto")
    return p


def _visible_project(c, pid: str) -> dict:
    p = c.one("SELECT id::text AS id, org_id::text AS org_id, title FROM projects WHERE id = $1", pid)
    if not p:
        raise not_found("Projeto")
    return p


# ------------------------------------------------------------------------------------------------ ODS e catálogo
@route("GET", "/v1/ods", min_role="viewer", tags=T, summary="17 ODS e quantidade de metas oficiais carregadas (metas/indicadores oficiais entram por importação)")
def list_ods(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        goals = c.query("SELECT g.number, g.name, (SELECT count(*) FROM ods_targets t WHERE t.ods = g.number) AS targets_loaded FROM ods_goals g ORDER BY g.number")
    return {"items": goals, "note": "A plataforma não embute o texto das metas oficiais; use a importação administrativa a partir da fonte oficial."}


@route("GET", "/v1/ods/{number}/targets", min_role="viewer", tags=T)
def ods_targets(ctx: Ctx):
    if not ctx.path["number"].isdigit() or not 1 <= int(ctx.path["number"]) <= 17:
        raise not_found("ODS")
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT code, description, source FROM ods_targets WHERE ods = $1::smallint ORDER BY code", ctx.path["number"])}


class CatalogQ(S.Pagination):
    ods: S.Ods | None = None
    esg: str | None = None


@route("GET", "/v1/indicators/catalog", query=CatalogQ, min_role="viewer", tags=T, summary="Catálogo de indicadores (plataforma, oficiais e definidos pela organização)")
def indicator_catalog(ctx: Ctx, q: CatalogQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, code, name, unit, definition, esg_dimension, ods, ods_target, origin FROM indicator_catalog WHERE active"
                       " AND ($1::smallint IS NULL OR ods = $1) AND ($2::text IS NULL OR esg_dimension = $2) ORDER BY origin, name LIMIT $3 OFFSET $4",
                       q.ods, q.esg, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/indicators/catalog", body=S.IndicatorCatalogIn, min_role="manager", status=201, tags=T,
       summary="Cria indicador próprio da organização (origem 'org_defined'; não é indicador oficial)")
def create_indicator(ctx: Ctx, body: S.IndicatorCatalogIn):
    with ctx.tx() as c:
        if c.one("SELECT 1 FROM indicator_catalog WHERE code = $1", body.code):
            raise ApiError(409, "code_in_use", "Código já existe")
        iid = c.scalar("INSERT INTO indicator_catalog(code, name, unit, definition, esg_dimension, ods, ods_target, origin, org_id)"
                       " VALUES ($1,$2,$3,$4,$5,$6::smallint,$7,'org_defined',$8) RETURNING id::text",
                       body.code, body.name, body.unit, body.definition, body.esg_dimension, body.ods, body.ods_target, ctx.org_id)
        ctx.audit(c, "indicator.created", "indicator", iid)
    return {"id": iid}


# ------------------------------------------------------------------------------------------------ projeto: ODS e indicadores
@route("PUT", "/v1/projects/{project_id}/ods-targets", body=S.OdsTargetsIn, kinds=("osc",), min_role="member", tags=T,
       summary="Define o alinhamento do projeto a ODS/metas (declarado; sobe de nível com evidência validada e revisão profissional)")
def put_ods_targets(ctx: Ctx, body: S.OdsTargetsIn):
    with ctx.tx() as c:
        p = _owned_project(c, ctx, ctx.path["project_id"])
        for it in body.items:
            if it.target_code and not c.one("SELECT 1 FROM ods_targets WHERE code = $1 AND ods = $2::smallint", it.target_code, it.ods):
                raise ApiError(422, "unknown_target", f"Meta {it.target_code} não carregada para o ODS {it.ods}")
        c.run("DELETE FROM project_ods_targets WHERE project_id = $1", p["id"])
        for it in body.items:
            c.run("INSERT INTO project_ods_targets(project_id, org_id, ods, target_code, rationale) VALUES ($1,$2,$3::smallint,$4,$5)"
                  " ON CONFLICT DO NOTHING", p["id"], ctx.org_id, it.ods, it.target_code, it.rationale)
        c.run("UPDATE projects SET ods = $2::smallint[] WHERE id = $1", p["id"], sorted({i.ods for i in body.items}))
        ctx.audit(c, "project.ods_updated", "project", p["id"], {"count": len(body.items)})
    return {"count": len(body.items)}


@route("POST", "/v1/projects/{project_id}/indicators", body=S.ProjectIndicatorIn, kinds=("osc",), min_role="member", status=201, tags=T)
def add_project_indicator(ctx: Ctx, body: S.ProjectIndicatorIn):
    with ctx.tx() as c:
        p = _owned_project(c, ctx, ctx.path["project_id"])
        if not c.one("SELECT 1 FROM indicator_catalog WHERE id = $1 AND active", body.indicator_id):
            raise not_found("Indicador")
        if c.one("SELECT 1 FROM project_indicators WHERE project_id = $1 AND indicator_id = $2", p["id"], body.indicator_id):
            raise ApiError(409, "already_added", "Indicador já vinculado ao projeto")
        piid = c.scalar("INSERT INTO project_indicators(project_id, org_id, indicator_id, baseline, target, target_date, method)"
                        " VALUES ($1,$2,$3,$4::numeric,$5::numeric,$6::date,$7) RETURNING id::text", p["id"], ctx.org_id, body.indicator_id,
                        body.baseline, body.target, body.target_date, body.method)
        ctx.audit(c, "project.indicator_added", "project_indicator", piid)
    return {"id": piid}


@route("DELETE", "/v1/projects/{project_id}/indicators/{pi_id}", kinds=("osc",), min_role="member", tags=T)
def remove_project_indicator(ctx: Ctx):
    with ctx.tx() as c:
        p = _owned_project(c, ctx, ctx.path["project_id"])
        if c.scalar("SELECT count(*) FROM indicator_values WHERE project_indicator_id = $1 AND status = 'validated'", ctx.path["pi_id"]):
            raise ApiError(409, "has_validated_values", "Indicador com valores validados não pode ser removido")
        n = c.run("DELETE FROM project_indicators WHERE id = $1 AND project_id = $2", ctx.path["pi_id"], p["id"])
        if not n:
            raise not_found("Indicador do projeto")
    return {"deleted": True}


@route("POST", "/v1/project-indicators/{pi_id}/values", body=S.IndicatorValueIn, kinds=("osc",), min_role="member", status=201, tags=T,
       summary="Reporta valor medido (status 'reported'; só vira 'validated' por quem não reportou)")
def report_value(ctx: Ctx, body: S.IndicatorValueIn):
    with ctx.tx() as c:
        pi = c.one("SELECT id::text AS id, project_id::text AS project_id FROM project_indicators WHERE id = $1 AND org_id = $2", ctx.path["pi_id"], ctx.org_id)
        if not pi:
            raise not_found("Indicador do projeto")
        if body.evidence_id and not c.one("SELECT 1 FROM evidences WHERE id = $1 AND project_id = $2", body.evidence_id, pi["project_id"]):
            raise not_found("Evidência")
        vid = c.scalar("INSERT INTO indicator_values(project_indicator_id, project_id, org_id, value, measured_on, evidence_id, note, created_by)"
                       " VALUES ($1,$2,$3,$4::numeric,$5::date,$6,$7,$8) RETURNING id::text", pi["id"], pi["project_id"], ctx.org_id, body.value,
                       body.measured_on, body.evidence_id, body.note, ctx.user_id)
        ledger(c, project_id=pi["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="result_reported", ref_type="indicator_value", ref_id=vid,
               payload={"value": body.value, "measured_on": str(body.measured_on), "has_evidence": bool(body.evidence_id)})
        ctx.audit(c, "indicator.value_reported", "indicator_value", vid)
    return {"id": vid, "status": "reported"}


@route("POST", "/v1/indicator-values/{value_id}/review", body=S.IndicatorValueReviewIn, kinds=("company", "government", "individual"), min_role="analyst", tags=T,
       summary="Financiador do projeto valida ou rejeita um valor reportado (a OSC não valida o próprio valor — garantido no banco)")
def review_value(ctx: Ctx, body: S.IndicatorValueReviewIn):
    with ctx.tx() as c:
        v = c.one("SELECT id::text AS id, project_id::text AS project_id, org_id::text AS org_id, evidence_id FROM indicator_values WHERE id = $1", ctx.path["value_id"])
        if not v or not c.scalar("SELECT app_project_investor($1)", v["project_id"]):
            raise not_found("Valor")
        if body.status == "validated" and not v["evidence_id"]:
            raise ApiError(422, "evidence_required", "Só é possível validar valor que tenha evidência anexada")
        c.run("UPDATE indicator_values SET status = $2, validated_by = $3, validated_by_org = $4, note = coalesce($5, note) WHERE id = $1",
              v["id"], body.status, ctx.user_id, ctx.org_id, body.note)
        if body.status == "validated":
            ledger(c, project_id=v["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="indicator_validated", ref_type="indicator_value", ref_id=v["id"])
        c.scalar("SELECT app_notify($1, NULL, 'impact', 'Indicador revisado', $2, $3)", v["org_id"], f"Status: {body.status}", f"/projetos/{v['project_id']}")
        ctx.audit(c, "indicator.value_reviewed", "indicator_value", v["id"], {"status": body.status})
    return {"id": v["id"], "status": body.status}


def _impact_payload(c, pid: str) -> dict:
    ods = c.query("SELECT t.ods, g.name, t.target_code, t.rationale,"
                  " CASE WHEN EXISTS (SELECT 1 FROM professional_reviews r WHERE r.subject_type = 'project' AND r.subject_id = t.project_id"
                  "        AND r.status IN ('approved','signed')) THEN 'professionally_reviewed'"
                  "      WHEN EXISTS (SELECT 1 FROM indicator_values v JOIN project_indicators pi ON pi.id = v.project_indicator_id"
                  "        JOIN indicator_catalog ic ON ic.id = pi.indicator_id WHERE v.project_id = t.project_id AND v.status = 'validated' AND ic.ods = t.ods)"
                  "        THEN 'supported_by_evidence' ELSE 'declared' END AS alignment_level"
                  " FROM project_ods_targets t JOIN ods_goals g ON g.number = t.ods WHERE t.project_id = $1 ORDER BY t.ods, t.target_code", pid)
    inds = c.query("SELECT pi.id::text AS id, ic.code, ic.name, ic.unit, ic.esg_dimension, ic.ods, ic.origin, pi.baseline::float AS baseline,"
                   " pi.target::float AS target, pi.target_date, pi.method FROM project_indicators pi JOIN indicator_catalog ic ON ic.id = pi.indicator_id"
                   " WHERE pi.project_id = $1 ORDER BY ic.name", pid)
    for i in inds:
        vals = c.query("SELECT id::text AS id, value::float AS value, measured_on, status, evidence_id::text AS evidence_id, note FROM indicator_values"
                       " WHERE project_indicator_id = $1 ORDER BY measured_on DESC, created_at DESC LIMIT 24", i["id"])
        i["values"] = vals
        rep = next((v for v in vals if v["status"] != "rejected"), None)
        val = next((v for v in vals if v["status"] == "validated"), None)
        i["latest_reported"] = rep["value"] if rep else None
        i["latest_validated"] = val["value"] if val else None
        span = (i["target"] - i["baseline"]) if i["target"] is not None and i["baseline"] is not None else None
        i["progress_reported_pct"] = (round(100 * (rep["value"] - i["baseline"]) / span, 1) if span and rep else None)
        i["progress_validated_pct"] = (round(100 * (val["value"] - i["baseline"]) / span, 1) if span and val else None)
    return {"ods_alignment": ods, "indicators": inds,
            "wording": "Valores 'reportados' são informados pela OSC; 'validados' foram conferidos por outra organização com evidência anexada."}


@route("GET", "/v1/projects/{project_id}/impact", min_role="viewer", tags=T, summary="ODS, indicadores (reportado × validado) e progresso do projeto")
def project_impact(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        p = _visible_project(c, ctx.path["project_id"])
        out = _impact_payload(c, p["id"])
    return {"project_id": p["id"], "title": p["title"], **out}


# ------------------------------------------------------------------------------------------------ Impact Graph
@route("GET", "/v1/projects/{project_id}/graph", min_role="viewer", tags=T, summary="Impact Graph: nós, ligações e a legenda dos tipos de evidência")
def get_graph(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        p = _visible_project(c, ctx.path["project_id"])
        nodes = c.query("SELECT id::text AS id, kind, label, description FROM impact_nodes WHERE project_id = $1 ORDER BY created_at", p["id"])
        edges = c.query("SELECT id::text AS id, from_node::text AS from_node, to_node::text AS to_node, link_type, evidence_id::text AS evidence_id, note,"
                        " reviewed_by_org IS NOT NULL AS externally_reviewed FROM impact_edges WHERE project_id = $1 ORDER BY created_at", p["id"])
    by_type: dict[str, int] = {}
    for e in edges:
        by_type[e["link_type"]] = by_type.get(e["link_type"], 0) + 1
    return {"nodes": nodes, "edges": edges, "legend": LINK_LEGEND, "edges_by_type": by_type,
            "note": "Só 'causalidade validada' afirma relação causal, e exige evidência + revisão externa. Os demais tipos NÃO devem ser lidos como prova de causa."}


@route("POST", "/v1/projects/{project_id}/graph/nodes", body=S.NodeIn, kinds=("osc",), min_role="member", status=201, tags=T)
def add_node(ctx: Ctx, body: S.NodeIn):
    with ctx.tx() as c:
        p = _owned_project(c, ctx, ctx.path["project_id"])
        if c.scalar("SELECT count(*) FROM impact_nodes WHERE project_id = $1", p["id"]) >= 200:
            raise ApiError(409, "limit", "Limite de 200 nós por projeto")
        nid = c.scalar("INSERT INTO impact_nodes(project_id, org_id, kind, label, description) VALUES ($1,$2,$3,$4,$5) RETURNING id::text",
                       p["id"], ctx.org_id, body.kind, body.label, body.description)
    return {"id": nid}


@route("DELETE", "/v1/projects/{project_id}/graph/nodes/{node_id}", kinds=("osc",), min_role="member", tags=T)
def delete_node(ctx: Ctx):
    with ctx.tx() as c:
        p = _owned_project(c, ctx, ctx.path["project_id"])
        if c.one("SELECT 1 FROM impact_edges WHERE (from_node = $1 OR to_node = $1) AND link_type = 'validated_causality'", ctx.path["node_id"]):
            raise ApiError(409, "has_validated_edge", "Nó participa de uma ligação com causalidade validada")
        if not c.run("DELETE FROM impact_nodes WHERE id = $1 AND project_id = $2", ctx.path["node_id"], p["id"]):
            raise not_found("Nó")
    return {"deleted": True}


@route("POST", "/v1/projects/{project_id}/graph/edges", body=S.EdgeIn, kinds=("osc",), min_role="member", status=201, tags=T,
       summary="Cria ligação. 'observed_evidence' exige evidência; 'validated_causality' só por revisão externa (rota própria)")
def add_edge(ctx: Ctx, body: S.EdgeIn):
    if body.link_type == "validated_causality":
        raise ApiError(422, "use_validation", "Causalidade validada é atribuída por revisão externa (POST /v1/graph-edges/{id}/validate)")
    if body.link_type == "observed_evidence" and not body.evidence_id:
        raise ApiError(422, "evidence_required", "Evidência observada exige uma evidência anexada")
    with ctx.tx() as c:
        p = _owned_project(c, ctx, ctx.path["project_id"])
        for nid in (body.from_node, body.to_node):
            if not c.one("SELECT 1 FROM impact_nodes WHERE id = $1 AND project_id = $2", nid, p["id"]):
                raise not_found("Nó")
        if body.evidence_id and not c.one("SELECT 1 FROM evidences WHERE id = $1 AND project_id = $2", body.evidence_id, p["id"]):
            raise not_found("Evidência")
        eid = c.scalar("INSERT INTO impact_edges(project_id, org_id, from_node, to_node, link_type, evidence_id, note, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id::text", p["id"], ctx.org_id, body.from_node, body.to_node, body.link_type,
                       body.evidence_id, body.note, ctx.user_id)
    return {"id": eid}


@route("DELETE", "/v1/projects/{project_id}/graph/edges/{edge_id}", kinds=("osc",), min_role="member", tags=T)
def delete_edge(ctx: Ctx):
    with ctx.tx() as c:
        p = _owned_project(c, ctx, ctx.path["project_id"])
        e = c.one("SELECT link_type FROM impact_edges WHERE id = $1 AND project_id = $2", ctx.path["edge_id"], p["id"])
        if not e:
            raise not_found("Ligação")
        if e["link_type"] == "validated_causality":
            raise ApiError(409, "validated", "Ligação validada externamente não pode ser removida pela OSC")
        c.run("DELETE FROM impact_edges WHERE id = $1", ctx.path["edge_id"])
    return {"deleted": True}


@route("POST", "/v1/graph-edges/{edge_id}/validate", body=S.EdgeValidateIn, kinds=("company", "government", "individual"), min_role="manager", tags=T,
       summary="Revisão externa (financiador do projeto) que promove a ligação a 'causalidade validada', com evidência e justificativa")
def validate_edge(ctx: Ctx, body: S.EdgeValidateIn):
    with ctx.tx() as c:
        e = c.one("SELECT id::text AS id, project_id::text AS project_id FROM impact_edges WHERE id = $1", ctx.path["edge_id"])
        if not e or not c.scalar("SELECT app_project_investor($1)", e["project_id"]):
            raise not_found("Ligação")
        if not c.one("SELECT 1 FROM evidences WHERE id = $1 AND project_id = $2 AND status = 'accepted'", body.evidence_id, e["project_id"]):
            raise ApiError(422, "evidence_not_accepted", "A evidência precisa existir no projeto e estar aceita")
        c.run("UPDATE impact_edges SET link_type = 'validated_causality', evidence_id = $2, note = $3, reviewed_by = $4, reviewed_by_org = $5 WHERE id = $1",
              e["id"], body.evidence_id, body.note, ctx.user_id, ctx.org_id)
        ctx.audit(c, "graph.edge_validated", "impact_edge", e["id"])
    return {"id": e["id"], "link_type": "validated_causality"}


# ------------------------------------------------------------------------------------------------ determinantes sociais (agregado)
class DetQ(S.In):
    territory: S.Territory = "BR"


@route("GET", "/v1/determinants", kinds=("government", "company", "individual", "platform"), query=DetQ, min_role="viewer", tags=T,
       summary="Camada agregada: projetos por domínio de determinante social e território (k-anonimato; sem ranking de grupos vulneráveis)")
def determinants(ctx: Ctx, q: DetQ):
    k = _DET["min_group"]
    out = []
    with ctx.tx(readonly=True) as c:
        for key, d in _DET["domains"].items():
            row = c.one("SELECT count(*) AS projects, coalesce(sum(budget_total_cents),0) AS budget_cents FROM projects p"
                        " WHERE p.visibility = 'published' AND p.causes && $1::text[] AND p.territory LIKE $2 || '%'", d["causes"], q.territory)
            n = int(row["projects"])
            out.append({"domain": key, "label": d["label"], "projects": n if n >= k else None, "budget_cents": int(row["budget_cents"]) if n >= k else None,
                        "suppressed": n < k})
    return {"territory": q.territory, "min_group": k, "domains": out,
            "note": ("Contagens vêm só de projetos publicados na plataforma — NÃO são estatísticas populacionais nem indicam necessidade relativa. "
                     "Grupos com menos de %d projetos são suprimidos. Não há dados externos (IBGE/Censo) carregados nesta versão." % k),
            "taxonomy_note": _DET["_note"]}


# ------------------------------------------------------------------------------------------------ diagnóstico
DIAG_COLS = ("id::text AS id, project_id::text AS project_id, title, need_statement, affected_group, root_causes, objective, goals, action_plan,"
             " risks, data_sources, status, applied_at, created_at, updated_at")


def _diag_missing(d: dict) -> list[str]:
    miss = []
    if not (d["need_statement"] or "").strip():
        miss.append("Necessidade")
    if not d["root_causes"]:
        miss.append("Causas")
    if not (d["objective"] or "").strip():
        miss.append("Objetivo")
    if not d["goals"]:
        miss.append("Metas")
    if not d["action_plan"]:
        miss.append("Plano de ação")
    return miss


@route("GET", "/v1/diagnoses", kinds=("osc",), query=S.Pagination, min_role="viewer", tags=("diagnosis",))
def list_diagnoses(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {DIAG_COLS} FROM diagnoses WHERE org_id = $1 ORDER BY updated_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/diagnoses", body=S.DiagnosisIn, kinds=("osc",), min_role="member", status=201, tags=("diagnosis",),
       summary="Cria diagnóstico estruturado: necessidade → causas → objetivo → metas → plano de ação (sem dados pessoais de beneficiários)")
def create_diagnosis(ctx: Ctx, body: S.DiagnosisIn):
    with ctx.tx() as c:
        if body.project_id and not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", body.project_id, ctx.org_id):
            raise not_found("Projeto")
        did = c.scalar("INSERT INTO diagnoses(org_id, project_id, title, need_statement, affected_group, root_causes, objective, goals, action_plan, risks,"
                       " data_sources, created_by) VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11::jsonb,$12) RETURNING id::text",
                       ctx.org_id, body.project_id, body.title, body.need_statement, body.affected_group, Json(body.root_causes), body.objective,
                       Json(body.goals), Json(body.action_plan), Json(body.risks), Json(body.data_sources), ctx.user_id)
        ctx.audit(c, "diagnosis.created", "diagnosis", did)
    return {"id": did}


@route("GET", "/v1/diagnoses/{diagnosis_id}", kinds=("osc",), min_role="viewer", tags=("diagnosis",))
def get_diagnosis(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        d = c.one(f"SELECT {DIAG_COLS} FROM diagnoses WHERE id = $1 AND org_id = $2", ctx.path["diagnosis_id"], ctx.org_id)
        if not d:
            raise not_found("Diagnóstico")
    d["missing"] = _diag_missing(d)
    return d


@route("PUT", "/v1/diagnoses/{diagnosis_id}", body=S.DiagnosisIn, kinds=("osc",), min_role="member", tags=("diagnosis",))
def update_diagnosis(ctx: Ctx, body: S.DiagnosisIn):
    with ctx.tx() as c:
        if body.project_id and not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", body.project_id, ctx.org_id):
            raise not_found("Projeto")
        n = c.run("UPDATE diagnoses SET project_id = $3, title = $4, need_statement = $5, affected_group = $6, root_causes = $7::jsonb, objective = $8,"
                  " goals = $9::jsonb, action_plan = $10::jsonb, risks = $11::jsonb, data_sources = $12::jsonb, updated_at = now(),"
                  " status = CASE WHEN status = 'applied' THEN 'draft' ELSE status END WHERE id = $1 AND org_id = $2",
                  ctx.path["diagnosis_id"], ctx.org_id, body.project_id, body.title, body.need_statement, body.affected_group, Json(body.root_causes),
                  body.objective, Json(body.goals), Json(body.action_plan), Json(body.risks), Json(body.data_sources))
        if not n:
            raise not_found("Diagnóstico")
        d = c.one(f"SELECT {DIAG_COLS} FROM diagnoses WHERE id = $1", ctx.path["diagnosis_id"])
        if not _diag_missing(d) and d["status"] == "draft":
            c.run("UPDATE diagnoses SET status = 'complete' WHERE id = $1", d["id"])
    return {"id": d["id"], "missing": _diag_missing(d)}


@route("POST", "/v1/diagnoses/{diagnosis_id}/apply", kinds=("osc",), min_role="member", tags=("diagnosis",),
       summary="Aplica o diagnóstico completo ao projeto: problema, objetivos, metas como indicadores do projeto e nós iniciais do Impact Graph")
def apply_diagnosis(ctx: Ctx):
    with ctx.tx() as c:
        d = c.one(f"SELECT {DIAG_COLS} FROM diagnoses WHERE id = $1 AND org_id = $2", ctx.path["diagnosis_id"], ctx.org_id)
        if not d:
            raise not_found("Diagnóstico")
        if not d["project_id"]:
            raise ApiError(422, "project_required", "Vincule o diagnóstico a um projeto antes de aplicar")
        miss = _diag_missing(d)
        if miss:
            raise ApiError(422, "incomplete_diagnosis", "Complete antes de aplicar: " + ", ".join(miss), {"missing": miss})
        pid = d["project_id"]
        c.run("UPDATE projects SET problem = left($2, 8000), objectives = left($3, 8000) WHERE id = $1", pid, d["need_statement"], d["objective"])
        linked = 0
        for g in d["goals"]:
            code = (g or {}).get("indicator_code")
            ic = c.one("SELECT id::text AS id FROM indicator_catalog WHERE code = $1 AND active", code) if code else None
            if ic and not c.one("SELECT 1 FROM project_indicators WHERE project_id = $1 AND indicator_id = $2", pid, ic["id"]):
                tgt = g.get("target")
                c.run("INSERT INTO project_indicators(project_id, org_id, indicator_id, target, method) VALUES ($1,$2,$3,$4::numeric,$5)",
                      pid, ctx.org_id, ic["id"], tgt if isinstance(tgt, (int, float)) else None, "Definido no diagnóstico")
                linked += 1
        if not c.one("SELECT 1 FROM impact_nodes WHERE project_id = $1", pid):
            n_need = c.scalar("INSERT INTO impact_nodes(project_id, org_id, kind, label) VALUES ($1,$2,'need',left($3,200)) RETURNING id::text", pid, ctx.org_id, d["need_statement"])
            n_out = c.scalar("INSERT INTO impact_nodes(project_id, org_id, kind, label) VALUES ($1,$2,'outcome',left($3,200)) RETURNING id::text", pid, ctx.org_id, d["objective"])
            c.run("INSERT INTO impact_edges(project_id, org_id, from_node, to_node, link_type, note, created_by) VALUES ($1,$2,$3,$4,'hypothesis',$5,$6)",
                  pid, ctx.org_id, n_need, n_out, "Teoria de mudança inicial do diagnóstico", ctx.user_id)
        c.run("UPDATE diagnoses SET status = 'applied', applied_at = now() WHERE id = $1", d["id"])
        ctx.audit(c, "diagnosis.applied", "diagnosis", d["id"], {"project_id": pid, "indicators_linked": linked})
    return {"id": d["id"], "status": "applied", "indicators_linked": linked}
