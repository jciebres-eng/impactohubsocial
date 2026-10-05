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


def load_projects(c: Connection, project_ids: list[str]) -> dict[str, dict]:
    """Carrega VÁRIOS projetos em 3 consultas, em vez de 3 por projeto.

    Achado da medição com volume: o feed do financiador fazia uma ida ao banco por candidato para marcos e para a
    captação. Com algumas centenas de candidatos isso dominava o tempo da requisição.
    """
    if not project_ids:
        return {}
    rows = c.query(f"SELECT {PROJECT_COLS} FROM projects WHERE id = ANY($1::uuid[])", project_ids)
    out = {r["id"]: r for r in rows}
    for r in out.values():
        r["milestones"] = []
        r["funded_cents"] = 0
    for m in c.query("SELECT project_id::text AS project_id, amount_cents, funded_cents, status FROM milestones"
                     " WHERE project_id = ANY($1::uuid[]) ORDER BY project_id, seq", project_ids):
        target = out.get(m.pop("project_id"))
        if target is not None:
            target["milestones"].append(m)
    for f in c.query("SELECT project_id::text AS project_id, committed_cents FROM project_funding_many($1::uuid[])",
                     project_ids):
        target = out.get(f["project_id"])
        if target is not None:
            target["funded_cents"] = f["committed_cents"] or 0
    return out


class FeedCache:
    """Memória de UMA requisição. Vários projetos candidatos pertencem às mesmas organizações: carregar organização,
    documentos, histórico, conflito e contexto institucional uma vez por organização, não uma vez por projeto.

    Vive dentro de uma transação, que é de um único solicitante — não há como misturar dado de outro inquilino aqui.
    """

    def __init__(self) -> None:
        self.org: dict[str, dict | None] = {}
        self.docs: dict[tuple[str, str | None], list[dict]] = {}
        self.history: dict[str, dict] = {}
        self.conflict: dict[tuple[str, str], bool] = {}
        self.inst: dict[str, dict] = {}

    def get_org(self, c, org_id):
        if org_id not in self.org:
            self.org[org_id] = load_org(c, org_id)
        return self.org[org_id]

    def get_docs(self, c, org_id, project_id):
        key = (org_id, project_id)
        if key not in self.docs:
            self.docs[key] = load_documents(c, org_id, project_id)
        return self.docs[key]

    def get_history(self, c, org_id):
        if org_id not in self.history:
            self.history[org_id] = load_history(c, org_id)
        return self.history[org_id]

    def get_conflict(self, c, funder_org_id, org_id):
        key = (funder_org_id, org_id)
        if key not in self.conflict:
            self.conflict[key] = has_conflict(c, funder_org_id, org_id)
        return self.conflict[key]

    def get_inst(self, c, org_id):
        if org_id not in self.inst:
            self.inst[org_id] = inst_context(c, org_id)
        return self.inst[org_id]


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
                            funder=None, behavior=None, cache: FeedCache | None = None) -> dict:
    cache = cache if cache is not None else FeedCache()
    org = cache.get_org(c, project["org_id"])
    funder = funder if funder is not None else (c.one("SELECT * FROM funder_profiles WHERE org_id = $1", funder_org_id) or {})
    if "milestones" not in project:
        project = load_project(c, project["id"])
    fi = []
    try:
        ctx = cache.get_inst(c, project["org_id"])
        if ctx:
            fi = [{"code": r["code"], "label": r["label"], "status": r["status"], "detail": r.get("detail"), "mandatory": r["mandatory"], "how_to_fix": r.get("how_to_fix")}
                  for r in inst.evaluate_for_funder(c, project["org_id"], funder_org_id, funder, f=ctx["f"], m=ctx["m"])["requirements"]]
            if call:
                fi += institutional_requirements(c, project["org_id"], call, ctx)
    except Exception:  # a camada institucional nunca derruba o match; sem dados institucionais o motor segue sem esses critérios
        fi = []
    mi = MatchInput.build("funder_project", org=org, funder=funder, call=call, project=project, inst=fi,
                          documents=cache.get_docs(c, project["org_id"], project["id"]),
                          history=cache.get_history(c, project["org_id"]),
                          behavior=behavior if behavior is not None else funder_behavior(c, funder_org_id),
                          conflict=cache.get_conflict(c, funder_org_id, project["org_id"]))
    return evaluate(mi)


def persist(c: Connection, viewer_org: str, user_id: str, result: dict, call_id: str | None, project_id: str | None) -> str:
    """Grava o resultado com as QUATRO versões (motor, pesos, regras, taxonomia) e a evidência que o sustentou.

    Um resultado antigo nunca muda de significado quando a régua muda: quem leu "82 com confiança alta" em outubro
    continua podendo saber com qual motor, quais pesos, quais regras e qual taxonomia aquilo foi calculado.
    """
    return c.scalar("INSERT INTO match_runs(viewer_org_id, direction, call_id, project_id, engine_version, weights_version,"
                    " rules_version, taxonomy_version, eligibility, score, confidence, result, features, evidence, created_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::numeric,$11::numeric,$12::jsonb,$13::jsonb,$14::jsonb,$15)"
                    " RETURNING id::text", viewer_org, result["direction"], call_id, project_id, result["engine_version"],
                    result["weights_version"], result.get("rules_version"), result.get("taxonomy_version"),
                    result["eligibility"], result["score"], result["confidence"],
                    Json({k: v for k, v in result.items() if k not in ("features", "evidence")}),
                    Json(result["features"]), Json(result.get("evidence") or {}), user_id)


FEEDBACK_KINDS = ("accepted", "rejected", "ignored", "not_relevant", "contacted", "converted", "expired")


def record_feedback(c: Connection, *, match_run_id: str, org_id: str, feedback: str, reason: str | None,
                    actor_user_id: str | None) -> dict:
    """Retorno humano sobre a recomendação. Serve para CALIBRAR depois — nada é treinado automaticamente aqui.

    O dataset fica pronto (run + versões + evidência + retorno + quem + quando + por quê) para uma calibração futura
    feita com revisão humana. A plataforma não ajusta pesos sozinha.
    """
    from ..http import ApiError
    if feedback not in FEEDBACK_KINDS:
        raise ApiError(422, "validation_error", f"Retorno inválido. Use: {', '.join(FEEDBACK_KINDS)}")
    run = c.one("SELECT id::text AS id, viewer_org_id::text AS viewer_org_id, project_id::text AS project_id,"
                " direction FROM match_runs WHERE id = $1", match_run_id)
    if not run or run["viewer_org_id"] != org_id:
        raise ApiError(404, "not_found", "Avaliação de match não encontrada")
    existing = c.scalar("SELECT 1 FROM match_feedback WHERE match_run_id = $1 AND org_id = $2", match_run_id, org_id)
    if existing:
        raise ApiError(409, "already_recorded", "Esta avaliação já recebeu retorno (o histórico não é reescrito)")
    c.run("INSERT INTO match_feedback(match_run_id, org_id, feedback, reason, actor_user_id) VALUES ($1,$2,$3,$4,$5)",
          match_run_id, org_id, feedback, reason, actor_user_id)
    # DELIBERADAMENTE não entra na linha de tempo do projeto. Quem avalia é quem OLHA (em geral o financiador), e a
    # trilha do projeto é lida pela organização dona dele: registrar ali "a empresa X descartou seu projeto" seria
    # expor a decisão de um terceiro no histórico de outro. O retorno fica em `match_feedback` (append-only, com
    # UNIQUE por avaliação) e na trilha de auditoria de quem agiu.
    return {"recorded": True, "match_run_id": match_run_id, "feedback": feedback,
            "note": "Retorno registrado. A plataforma NÃO recalibra pesos automaticamente: o dado fica disponível "
                    "para calibração futura com revisão humana."}


def calibration_dataset(c: Connection, *, limit: int = 1000, offset: int = 0) -> dict:
    """Base para calibração futura (administração). Sem dado pessoal: só identificadores, versões e sinais."""
    rows = c.query("SELECT r.id::text AS match_run_id, r.direction, r.engine_version, r.weights_version,"
                   " r.rules_version, r.taxonomy_version, r.eligibility, r.score, r.confidence, r.features,"
                   " f.feedback, f.at AS feedback_at FROM match_runs r"
                   " JOIN match_feedback f ON f.match_run_id = r.id ORDER BY r.created_at DESC LIMIT $1 OFFSET $2",
                   limit, offset)
    counts = c.query("SELECT feedback, count(*) AS n FROM match_feedback GROUP BY feedback ORDER BY feedback")
    return {"rows": rows, "counts": counts,
            "note": "Dataset para calibração supervisionada futura. Nenhum treino automático acontece na plataforma."}
