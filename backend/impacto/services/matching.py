"""Montagem das entradas do Match Engine a partir do banco (sob RLS do solicitante) e registro de match_runs.

Não consulta billing/entitlements: o motor nunca recebe plano/voucher (ADR-008).
"""
from __future__ import annotations

from ..db.pq import Connection, Json
from ..engines.match.engine import MatchInput, evaluate
from . import institutional as inst

ORG_COLS = ("id::text AS id, kind, founded_on, territories, causes, ods, certifications, team_size, compliance_status, uf,"
            " ibge_code, legal_nature")
PROJECT_COLS = ("id::text AS id, org_id::text AS org_id, title, causes, ods, esg_tags, territory, beneficiaries_count,"
                " budget_total_cents, status, visibility, urgency, ends_on, indicators")
CALL_COLS = ("id::text AS id, status, opens_at, closes_at, causes, ods, territories, eligible_org_types, ticket_min_cents,"
             " ticket_max_cents, budget_total_cents, required_document_types, required_certifications, min_org_age_months,"
             " counterpart_pct::float AS counterpart_pct, requirements, weights, criteria_version, sphere, owner_org_id::text AS owner_org_id,"
             " title, funding_modality, accepted_legal_natures, min_maturity")


def load_org(c: Connection, org_id: str) -> dict | None:
    org = c.one(f"SELECT {ORG_COLS} FROM organizations WHERE id = $1", org_id)
    if org:
        # Declarar não é provar: o motor só enxerga qualificações VERIFICADAS e vigentes (a coluna legada é apenas espelho de declarações).
        org["certifications"] = [r["qualification_type"] for r in c.query(
            "SELECT DISTINCT qualification_type FROM organization_qualifications WHERE org_id = $1 AND verification_status = 'verified'"
            " AND (expiration_date IS NULL OR expiration_date >= current_date)", org_id)]
    return org


def load_project(c: Connection, project_id: str) -> dict | None:
    p = c.one(f"SELECT {PROJECT_COLS} FROM projects WHERE id = $1", project_id)
    if p:
        p["milestones"] = c.query("SELECT amount_cents, funded_cents, status FROM milestones WHERE project_id = $1 ORDER BY seq", project_id)
        p["funded_cents"] = c.scalar("SELECT committed_cents FROM project_funding($1)", project_id) or 0
    return p


def load_call(c: Connection, call_id: str) -> dict | None:
    return c.one(f"SELECT {CALL_COLS} FROM calls WHERE id = $1", call_id)


def load_documents(c: Connection, org_id: str, project_id: str | None) -> list[dict]:
    """Documentos da OSC. Para o financiador, a RLS só devolve o que ele pode ver; usamos uma função
    SECURITY DEFINER restrita a metadados (tipo/status/validade) para não expor conteúdo."""
    from .documents import usable_statuses
    ok = usable_statuses()
    rows = c.query("SELECT doc_type, status, valid_until FROM org_document_metadata($1, $2)", org_id, project_id)
    # Normaliza para o motor: só conta o que é utilizável no ambiente (ver services/documents.ACCEPT_UNSCANNED).
    return [dict(r, status="clean" if r["status"] in ok else r["status"]) for r in rows]


def load_history(c: Connection, org_id: str) -> dict:
    return c.one("SELECT * FROM org_track_record($1)", org_id) or {}


def funder_behavior(c: Connection, funder_org_id: str) -> dict:
    saved = c.query("SELECT DISTINCT unnest(p.causes) AS c FROM favorites f JOIN projects p ON p.id = f.project_id WHERE f.org_id = $1", funder_org_id)
    dismissed = c.query("SELECT DISTINCT unnest(p.causes) AS c FROM feed_feedback f JOIN projects p ON p.id = f.target_id"
                        " WHERE f.org_id = $1 AND f.target_type = 'project' AND f.action = 'dismiss'", funder_org_id)
    return {"saved_causes": [r["c"] for r in saved], "dismissed_causes": [r["c"] for r in dismissed]}


def has_conflict(c: Connection, funder_org_id: str, osc_org_id: str) -> bool:
    return bool(c.scalar("SELECT EXISTS (SELECT 1 FROM conflict_declarations d JOIN applications a ON a.id = d.application_id"
                         " WHERE d.org_id = $1 AND a.osc_org_id = $2 AND d.has_conflict)", funder_org_id, osc_org_id))


_CALL_BASE_CODES = {"call:legal_nature", "call:maturity"}


def inst_context(c: Connection, org_id: str) -> dict:
    """Fatos institucionais + maturidade, calculados uma vez por organização (reutilizável em laços sobre vários editais)."""
    f = inst.facts(c, org_id)
    return {"f": f, "m": inst.maturity(c, org_id, f)} if f else {}


def institutional_requirements(c: Connection, org_id: str, call: dict, ctx: dict | None = None) -> list[dict]:
    """Requisitos institucionais que ENTRAM no match: natureza jurídica/maturidade declaradas no edital e regras publicadas (com fonte).
    Qualificações, documentos e tempo de existência já são avaliados pelo motor com os mesmos dados — não duplicamos."""
    if not call:
        return []
    ctx = ctx if ctx is not None else inst_context(c, org_id)
    if not ctx:
        return []
    res = inst.evaluate_for_call(c, org_id, call, f=ctx["f"], m=ctx["m"])
    out = []
    for r in res["requirements"]:
        if r["code"] in _CALL_BASE_CODES or not r["code"].startswith("call:"):
            out.append({"code": r["code"], "label": r["label"], "status": r["status"], "detail": r.get("detail"), "mandatory": r["mandatory"],
                        "how_to_fix": r.get("how_to_fix"), "source_citation": (r.get("source") or {}).get("citation")})
    return out


def evaluate_osc_call(c: Connection, osc_org_id: str, call: dict, project_id: str | None, *, docs=None, history=None, org=None, inst_ctx=None) -> dict:
    org = org or load_org(c, osc_org_id)
    project = load_project(c, project_id) if project_id else None
    docs = docs if docs is not None else load_documents(c, osc_org_id, project_id)
    history = history if history is not None else load_history(c, osc_org_id)
    mi = MatchInput.build("osc_call", org=org, call=call, project=project, documents=docs, history=history,
                          inst=institutional_requirements(c, osc_org_id, call, inst_ctx))
    return evaluate(mi)


def evaluate_funder_project(c: Connection, funder_org_id: str, project: dict, call: dict | None = None, *,
                            funder=None, behavior=None) -> dict:
    org = load_org(c, project["org_id"])
    funder = funder if funder is not None else (c.one("SELECT * FROM funder_profiles WHERE org_id = $1", funder_org_id) or {})
    if "milestones" not in project:
        project = load_project(c, project["id"])
    fi = []
    try:
        ctx = inst_context(c, project["org_id"])
        if ctx:
            fi = [{"code": r["code"], "label": r["label"], "status": r["status"], "detail": r.get("detail"), "mandatory": r["mandatory"], "how_to_fix": r.get("how_to_fix")}
                  for r in inst.evaluate_for_funder(c, project["org_id"], funder_org_id, funder, f=ctx["f"], m=ctx["m"])["requirements"]]
            if call:
                fi += institutional_requirements(c, project["org_id"], call, ctx)
    except Exception:  # a camada institucional nunca derruba o match; sem dados institucionais o motor segue sem esses critérios
        fi = []
    mi = MatchInput.build("funder_project", org=org, funder=funder, call=call, project=project, inst=fi,
                          documents=load_documents(c, project["org_id"], project["id"]), history=load_history(c, project["org_id"]),
                          behavior=behavior if behavior is not None else funder_behavior(c, funder_org_id),
                          conflict=has_conflict(c, funder_org_id, project["org_id"]))
    return evaluate(mi)


def persist(c: Connection, viewer_org: str, user_id: str, result: dict, call_id: str | None, project_id: str | None) -> str:
    return c.scalar("INSERT INTO match_runs(viewer_org_id, direction, call_id, project_id, engine_version, weights_version, eligibility,"
                    " score, confidence, result, features, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::numeric,$9::numeric,$10::jsonb,$11::jsonb,$12)"
                    " RETURNING id::text", viewer_org, result["direction"], call_id, project_id, result["engine_version"],
                    result["weights_version"], result["eligibility"], result["score"], result["confidence"],
                    Json({k: v for k, v in result.items() if k != "features"}), Json(result["features"]), user_id)
