"""Compliance / KYB da organização: verificações automáticas + revisão humana pela administração.

KYC de pessoa física não se aplica ao MVP (sem custódia de recursos). Fontes externas (Receita via provedor de
consulta de CNPJ; listas de sanções CEIS/CNEP do Portal da Transparência) são adapters configuráveis — sem
configuração, a verificação fica registrada como ``not_configured`` (nunca como aprovada).
"""
from __future__ import annotations

import json
import os

from ..adapters.http_client import HttpClient
from ..db.pq import Connection, Json
from ..http import ApiError, Ctx
from .validators import cnpj_valid

BASIC_DOCS = {"osc": ["estatuto_social", "ata_eleicao_diretoria", "cartao_cnpj", "cnd_federal", "crf_fgts", "cndt_trabalhista"],
              "company": ["cartao_cnpj"], "government": ["material_governo"], "provider": [], "individual": []}


def _registry_check(cnpj: str, http: HttpClient | None = None) -> tuple[str, dict, str]:
    url_tpl = os.getenv("CNPJ_LOOKUP_URL", "")
    if not url_tpl:
        return "not_configured", {"message": "Consulta de CNPJ não configurada (CNPJ_LOOKUP_URL)"}, "none"
    try:
        status, _, raw = (http or HttpClient(retries=1)).request("GET", url_tpl.format(cnpj=cnpj), timeout=10)
        if status != 200:
            return "error", {"http_status": status}, url_tpl.split("/")[2]
        data = json.loads(raw)
        situacao = str(data.get("descricao_situacao_cadastral") or data.get("situacao") or "").upper()
        return ("pass" if situacao == "ATIVA" else "fail"), {"situacao_cadastral": situacao or "desconhecida",
                                                             "razao_social": data.get("razao_social") or data.get("nome")}, url_tpl.split("/")[2]
    except Exception as exc:  # noqa: BLE001
        return "error", {"error": type(exc).__name__}, "cnpj_lookup"


def _sanctions_check(cnpj: str, http: HttpClient | None = None) -> tuple[str, dict]:
    key = os.getenv("PORTAL_TRANSPARENCIA_API_KEY", "")
    if not key:
        return "not_configured", {"message": "Consulta CEIS/CNEP não configurada (PORTAL_TRANSPARENCIA_API_KEY)"}
    hits = 0
    try:
        for lst in ("ceis", "cnep"):
            st, _, raw = (http or HttpClient(retries=1)).request(
                "GET", f"https://api.portaldatransparencia.gov.br/api-de-dados/{lst}?cnpjSancionado={cnpj}&pagina=1",
                headers={"chave-api-dados": key, "Accept": "application/json"}, timeout=15)
            if st != 200:
                return "error", {"list": lst, "http_status": st}
            hits += len(json.loads(raw) or [])
    except Exception as exc:  # noqa: BLE001
        return "error", {"error": type(exc).__name__}
    return ("fail" if hits else "pass"), {"sanction_records": hits}


def run_checks(c: Connection, org_id: str, actor: str | None) -> dict:
    org = c.one("SELECT id::text AS id, kind, cnpj, founded_on, description, causes, uf FROM organizations WHERE id = $1", org_id)
    results = []

    def add(t, st, details, source):
        c.run("INSERT INTO compliance_checks(org_id, check_type, status, details, source, checked_by) VALUES ($1,$2,$3,$4::jsonb,$5,$6)",
              org_id, t, st, Json(details), source, actor)
        results.append({"check_type": t, "status": st, "details": details, "source": source})

    if org["cnpj"]:
        add("cnpj_format", "pass" if cnpj_valid(org["cnpj"]) else "fail", {"cnpj": org["cnpj"]}, "algoritmo_dv")
        st, det, src = _registry_check(org["cnpj"])
        add("cnpj_registry", st, det, src)
        st, det = _sanctions_check(org["cnpj"])
        add("sanctions_ceis_cnep", st, det, "portal_transparencia")
    elif org["kind"] != "provider":
        add("cnpj_format", "fail", {"message": "CNPJ ausente"}, "cadastro")
    required = BASIC_DOCS.get(org["kind"], [])
    if required:
        from .documents import usable_statuses
        have = {r["doc_type"] for r in c.query("SELECT doc_type FROM documents WHERE org_id = $1 AND deleted_at IS NULL AND status = ANY($2::text[])"
                                               " AND (valid_until IS NULL OR valid_until >= current_date)", org_id, list(usable_statuses()))}
        missing = [d for d in required if d not in have]
        add("documents_basic", "pass" if not missing else "warning", {"missing": missing}, "cofre_documentos")
    exp = c.query("SELECT doc_type, valid_until FROM documents WHERE org_id = $1 AND deleted_at IS NULL AND valid_until"
                  " BETWEEN current_date AND current_date + 30", org_id)
    add("documents_expiring", "warning" if exp else "pass", {"expiring": [{"doc_type": e["doc_type"], "valid_until": str(e["valid_until"])} for e in exp]},
        "cofre_documentos")
    gaps = [k for k in ("founded_on", "description", "uf") if not org[k]] + ([] if org["causes"] else ["causes"])
    add("profile_completeness", "pass" if not gaps else "warning", {"missing_fields": gaps}, "cadastro")
    open_reports = c.scalar("SELECT count(*) FROM reports WHERE target_type = 'organization' AND target_id = $1 AND status IN ('open','triaged')", org_id)
    add("open_reports", "warning" if open_reports else "pass", {"open_reports": open_reports}, "denuncias")
    fails = sum(1 for r in results if r["status"] == "fail")
    warns = sum(1 for r in results if r["status"] in ("warning", "error", "not_configured"))
    risk = "high" if fails else ("medium" if warns >= 2 else "low")
    return {"checks": results, "risk_level": risk}


def request_review(ctx: Ctx) -> dict:
    with ctx.system_tx() as c:
        cur = c.one("SELECT compliance_status FROM organizations WHERE id = $1", ctx.org_id)
        if cur["compliance_status"] == "in_review":
            raise ApiError(409, "already_in_review", "Análise de compliance já em andamento")
        res = run_checks(c, ctx.org_id, ctx.user_id)
        rid = c.scalar("INSERT INTO compliance_reviews(org_id, status, risk_level) VALUES ($1,'open',$2) RETURNING id::text", ctx.org_id, res["risk_level"])
        c.run("UPDATE organizations SET compliance_status = 'in_review', compliance_risk = $2 WHERE id = $1", ctx.org_id, res["risk_level"])
        ctx.audit(c, "compliance.review_requested", "compliance_review", rid, {"risk": res["risk_level"]}, org_id=ctx.org_id)
    return {"review_id": rid, **res}


def decide(ctx: Ctx, review_id: str, decision: str, note: str | None) -> dict:
    if decision not in ("approved", "rejected", "info_requested"):
        raise ApiError(422, "validation_error", "Decisão inválida")
    with ctx.tx() as c:  # admin_mode → app.platform_admin=on
        r = c.one("SELECT id::text AS id, org_id::text AS org_id, status FROM compliance_reviews WHERE id = $1 FOR UPDATE", review_id)
        if not r or r["status"] != "open":
            raise ApiError(404, "not_found", "Análise não encontrada ou já decidida")
        c.run("UPDATE compliance_reviews SET status = $2, decision_note = $3, reviewer_id = $4, decided_at = now() WHERE id = $1",
              review_id, decision, note, ctx.user_id)
        new_status = {"approved": "approved", "rejected": "rejected", "info_requested": "pending"}[decision]
        c.run("UPDATE organizations SET compliance_status = $2, compliance_reviewed_at = now() WHERE id = $1", r["org_id"], new_status)
        c.scalar("SELECT app_notify($1, NULL, 'compliance', $2, $3, '/organizacao/compliance')", r["org_id"],
                 {"approved": "Compliance aprovado", "rejected": "Compliance reprovado", "info_requested": "Compliance: informações adicionais"}[decision],
                 note or "")
        ctx.audit(c, "compliance.decided", "compliance_review", review_id, {"decision": decision, "org": r["org_id"]}, org_id=r["org_id"])
    return {"review_id": review_id, "decision": decision}
