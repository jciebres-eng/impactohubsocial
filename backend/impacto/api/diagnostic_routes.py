"""Diagnóstico longitudinal: versões imutáveis, o que mudou entre elas e as ações que as lacunas geram.

A saída separa sempre três coisas que costumam ser misturadas: FATO (a evidência que a plataforma tem, com fonte e
data), INFERÊNCIA (a lacuna que uma REGRA aponta) e RECOMENDAÇÃO (a ação sugerida). Onde não há evidência, a resposta
é "desconhecido" — nunca um palpite apresentado como achado.
"""
from __future__ import annotations

from ..core import diagnostic as DX
from ..core.evidence import BAND_LABEL, SOURCE_TRUST
from ..http import ApiError, Ctx, not_found, page, route
from . import core_schemas as C
from . import schemas as S

T = ("diagnosis",)


def _own_diagnosis(c, ctx: Ctx, did: str) -> dict:
    d = c.one("SELECT id::text AS id, org_id::text AS org_id, project_id::text AS project_id, title"
              " FROM diagnoses WHERE id = $1 AND org_id = $2", did, ctx.org_id)
    if not d:
        raise not_found("Diagnóstico")
    return d


@route("GET", "/v1/readiness", query=C.AnalysisQ, kinds=("osc",), min_role="viewer", tags=T,
       summary="Leitura de prontidão da organização agora (não grava nada)")
def readiness(ctx: Ctx, q: C.AnalysisQ):
    with ctx.tx(readonly=True) as c:
        if q.project_id and not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", q.project_id, ctx.org_id):
            raise not_found("Projeto")
        return DX.analyse(c, org_id=ctx.org_id, project_id=q.project_id)


@route("GET", "/v1/diagnoses/{diagnosis_id}/analysis", kinds=("osc",), min_role="viewer", tags=T,
       summary="Análise do diagnóstico no estado atual (prévia, antes de congelar uma versão)")
def analysis(ctx: Ctx):
    did = ctx.path["diagnosis_id"]
    with ctx.tx(readonly=True) as c:
        d = c.one("SELECT id::text AS id, org_id::text AS org_id, project_id::text AS project_id, title,"
                  " need_statement, affected_group, root_causes, objective, goals, action_plan, risks, data_sources,"
                  " updated_at FROM diagnoses WHERE id = $1 AND org_id = $2", did, ctx.org_id)
        if not d:
            raise not_found("Diagnóstico")
        out = DX.analyse(c, org_id=ctx.org_id, project_id=d["project_id"], diagnosis=d)
    out["preview"] = True
    return out


@route("POST", "/v1/diagnoses/{diagnosis_id}/versions", kinds=("osc",), min_role="member", status=201, tags=T,
       summary="Congela uma versão do diagnóstico (a anterior nunca é alterada)")
def publish_version(ctx: Ctx):
    did = ctx.path["diagnosis_id"]
    with ctx.tx() as c:
        _own_diagnosis(c, ctx, did)
        out = DX.publish_version(c, diagnosis_id=did, org_id=ctx.org_id, created_by=ctx.user_id)
        if out.get("created"):
            ctx.audit(c, "diagnosis.version_published", "diagnosis", did,
                      {"version": out["version"], "completeness": out["completeness"]})
    return out


@route("GET", "/v1/diagnoses/{diagnosis_id}/versions", kinds=("osc",), min_role="viewer", tags=T)
def list_versions(ctx: Ctx):
    did = ctx.path["diagnosis_id"]
    with ctx.tx(readonly=True) as c:
        _own_diagnosis(c, ctx, did)
        rows = DX.versions(c, did)
    return {"items": rows, "engine_version": DX.ENGINE_VERSION,
            "note": "Cada versão guarda o retrato completo e o resumo do que mudou. Versão publicada não é editada."}


@route("GET", "/v1/diagnoses/{diagnosis_id}/versions/compare", query=C.VersionCompareQ, kinds=("osc",),
       min_role="viewer", tags=T, summary="O que mudou entre duas versões (lacunas fechadas, novas forças, confiança)")
def compare_versions(ctx: Ctx, q: C.VersionCompareQ):
    did = ctx.path["diagnosis_id"]
    with ctx.tx(readonly=True) as c:
        _own_diagnosis(c, ctx, did)
        out = DX.compare_versions(c, did, q.a, q.b)
    if not out.get("found"):
        raise not_found("Versão do diagnóstico")
    return out


@route("GET", "/v1/diagnoses/{diagnosis_id}/versions/{version}", kinds=("osc",), min_role="viewer", tags=T,
       summary="Retrato completo de uma versão")
def get_version(ctx: Ctx):
    did = ctx.path["diagnosis_id"]
    try:
        v = int(ctx.path["version"])
    except ValueError:
        raise ApiError(422, "validation_error", "Versão inválida") from None
    with ctx.tx(readonly=True) as c:
        _own_diagnosis(c, ctx, did)
        row = c.one("SELECT id::text AS id, version, payload, payload_sha256, changes, completeness, confidence,"
                    " engine_version, created_at, created_by::text AS created_by,"
                    " user_display_name(created_by) AS created_by_name FROM diagnosis_versions"
                    " WHERE diagnosis_id = $1 AND version = $2", did, v)
    if not row:
        raise not_found("Versão do diagnóstico")
    return row


# ------------------------------------------------------------------------------------------------ ações
ACTION_COLS = ("id::text AS id, gap_code, title, detail, evidence_hint, priority, origin, status,"
               " owner_user_id::text AS owner_user_id, user_display_name(owner_user_id) AS owner_name, due_on,"
               " document_id::text AS document_id, done_at, dismissed_reason, created_at, updated_at")


@route("GET", "/v1/diagnoses/{diagnosis_id}/actions", query=S.Pagination, kinds=("osc",), min_role="viewer", tags=T)
def list_actions(ctx: Ctx, q: S.Pagination):
    did = ctx.path["diagnosis_id"]
    with ctx.tx(readonly=True) as c:
        _own_diagnosis(c, ctx, did)
        rows = c.query(f"SELECT {ACTION_COLS} FROM diagnosis_actions WHERE diagnosis_id = $1"
                       " ORDER BY CASE priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'medium' THEN 2"
                       " ELSE 3 END, created_at LIMIT $2 OFFSET $3", did, q.limit + 1, q.offset)
    out = page(rows, q.limit, q.offset)
    out["origins"] = {"declared": "criada pela equipe",
                      "system_identified": "criada a partir de uma lacuna apontada por regra"}
    return out


@route("POST", "/v1/diagnoses/{diagnosis_id}/actions", body=C.ActionIn, kinds=("osc",), min_role="member", status=201,
       tags=T, summary="Ação declarada pela equipe (a ação de lacuna nasce com a versão do diagnóstico)")
def create_action(ctx: Ctx, body: C.ActionIn):
    did, d = ctx.path["diagnosis_id"], body.model_dump()
    with ctx.tx() as c:
        dg = _own_diagnosis(c, ctx, did)
        aid = c.scalar("INSERT INTO diagnosis_actions(diagnosis_id, org_id, project_id, title, detail, priority,"
                       " origin, owner_user_id, due_on) VALUES ($1,$2,$3,$4,$5,$6,'declared',$7,$8::date)"
                       " RETURNING id::text", did, ctx.org_id, dg["project_id"], d["title"], d["detail"],
                       d["priority"], d["owner_user_id"], d["due_on"])
        ctx.audit(c, "diagnosis.action_created", "diagnosis_action", aid, {"priority": d["priority"]})
    return {"id": aid}


@route("PUT", "/v1/diagnoses/{diagnosis_id}/actions/{action_id}", body=C.ActionUpdateIn, kinds=("osc",),
       min_role="member", tags=T, summary="Atualiza a ação (encerrar por descarte exige motivo)")
def update_action(ctx: Ctx, body: C.ActionUpdateIn):
    did, aid = ctx.path["diagnosis_id"], ctx.path["action_id"]
    d = {k: v for k, v in body.model_dump().items() if v is not None}
    if not d:
        raise ApiError(422, "validation_error", "Nada para atualizar")
    with ctx.tx() as c:
        dg = _own_diagnosis(c, ctx, did)
        cur = c.one("SELECT id::text AS id, status, gap_code FROM diagnosis_actions WHERE id = $1 AND diagnosis_id = $2",
                    aid, did)
        if not cur:
            raise not_found("Ação")
        status = d.get("status", cur["status"])
        if status == "dismissed" and not (d.get("dismissed_reason") or "").strip():
            raise ApiError(422, "reason_required", "Descartar uma ação exige registrar o motivo.")
        if d.get("document_id") and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2",
                                              d["document_id"], ctx.org_id):
            raise not_found("Documento")
        c.run("UPDATE diagnosis_actions SET status = $3, owner_user_id = coalesce($4, owner_user_id),"
              " due_on = coalesce($5::date, due_on), document_id = coalesce($6, document_id),"
              " dismissed_reason = coalesce($7, dismissed_reason),"
              " done_at = CASE WHEN $3 = 'done' THEN coalesce(done_at, now()) END"
              " WHERE id = $1 AND diagnosis_id = $2", aid, did, status, d.get("owner_user_id"), d.get("due_on"),
              d.get("document_id"), d.get("dismissed_reason"))
        if status == "done" and cur["status"] != "done" and dg["project_id"]:
            from ..services.audit import ledger
            ledger(c, project_id=dg["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="action_completed",
                   ref_type="diagnosis_action", ref_id=aid, payload={"gap_code": cur["gap_code"]})
        ctx.audit(c, "diagnosis.action_updated", "diagnosis_action", aid, {"status": status})
    return {"id": aid, "status": status}


@route("GET", "/v1/diagnostic-engine", min_role="viewer", tags=T,
       summary="O que o motor de diagnóstico avalia, com que peso e como trata ausência de dado")
def engine_reference(ctx: Ctx):
    return {
        "engine_version": DX.ENGINE_VERSION,
        "dimensions": [{"dimension": d, "label": label, "weight": w} for d, label, w in DX.DIMENSIONS],
        "gaps": [{"code": code, "dimension": dim, "title": title, "severity": sev, "evidence_hint": hint}
                 for code, dim, title, sev, hint, _ in DX.GAPS],
        "evidence_sources": [{"source": k.value, "trust": v} for k, v in SOURCE_TRUST.items()],
        "confidence_bands": [{"band": k.value, "label": v} for k, v in BAND_LABEL.items()],
        "output_kinds": {"FACT": "evidência registrada, com fonte e data",
                         "INFERENCE": "lacuna ou risco apontado por regra",
                         "RECOMMENDATION": "ação sugerida — a decisão é humana",
                         "UNKNOWN": "não há dado na plataforma para avaliar"},
        "note": "Nenhuma saída do motor é verdade absoluta. Ausência de evidência aparece como desconhecido.",
    }
