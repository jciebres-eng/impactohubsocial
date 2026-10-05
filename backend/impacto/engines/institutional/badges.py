"""Badges institucionais com critério, fonte, data de verificação e validade (puro).

Sem selo estático: cada badge é CALCULADO a partir de fatos validados; a data de verificação é a do último ato humano que o sustenta e a validade é o menor
entre (validade dos documentos/qualificações usados) e (verificação + validity_days do catálogo). Toda saída carrega o aviso de que é classificação interna.
"""
from __future__ import annotations

from datetime import date, timedelta

from .common import BADGE_DISCLAIMER, as_date
from .documents import best_state

# critérios implementados (conjunto fechado; o catálogo só parametriza)
ORG_CRITERIA = ("compliance_approved", "document_validated", "qualification_verified", "eligibility_evaluated")
SOLUTION_CRITERIA = ("solution_trust", "solution_impact_proven", "solution_replicable", "solution_seeking_funding")
CRITERIA = ORG_CRITERIA + SOLUTION_CRITERIA


def _basis(ok: bool, verified_at: date | None, expiries: list[date | None], detail: str, extra: dict | None = None) -> dict:
    return {"ok": ok, "verified_at": verified_at, "expiries": [e for e in expiries if e], "detail": detail, **(extra or {})}


def _org_criterion(code: str, params: dict, facts: dict, today: date, ctx: dict) -> dict:
    if code == "compliance_approved":
        ok = facts.get("compliance_status") == "approved"
        return _basis(ok, as_date(facts.get("compliance_reviewed_at")) if ok else None, [], "Compliance aprovado pela administração" if ok else "Compliance não aprovado")
    if code == "document_validated":
        docs = [{"doc_type": d.get("doc_type"), "scan_status": d.get("scan_status"), "validation_status": d.get("validation_status"), "valid_until": d.get("valid_until"),
                 "validated_at": d.get("validated_at")} for d in facts.get("documents") or []]
        got, ver, exp, miss = True, [], [], []
        for t in params.get("doc_types", []):
            st, d = best_state(docs, t, today)
            if st == "validated":
                ver.append(as_date(d.get("validated_at")))
                exp.append(as_date(d.get("valid_until")))
            else:
                got = False
                miss.append(t)
        return _basis(got, max((v for v in ver if v), default=None) if got else None, exp, "Documentos validados: " + ", ".join(params.get("doc_types", [])) if got else "Faltam/pendentes: " + ", ".join(miss))
    if code == "qualification_verified":
        t = params.get("type")
        qs = [q for q in facts.get("qualifications") or [] if q.get("type") == t and q.get("status") == "verified"
              and not (as_date(q.get("expiration_date")) and as_date(q.get("expiration_date")) < today)]
        if not qs:
            return _basis(False, None, [], f"Sem qualificação {str(t).upper()} verificada e vigente")
        q = max(qs, key=lambda x: str(x.get("validation_date") or ""))
        return _basis(True, as_date(q.get("validation_date")), [as_date(q.get("expiration_date"))], f"Qualificação {str(t).upper()} verificada")
    if code == "eligibility_evaluated":
        last = as_date(ctx.get("last_eligibility_evaluation"))
        return _basis(bool(last), last, [], "Há avaliação de elegibilidade registrada" if last else "Nenhuma avaliação de elegibilidade registrada")
    raise ValueError("critério de organização desconhecido")


def _solution_criterion(code: str, params: dict, sol: dict, today: date) -> dict:
    ver = as_date(sol.get("verified_at"))
    if code == "solution_trust":
        ok = sol.get("trust_level") in params.get("levels", ["verified"])
        return _basis(ok, ver if ok else None, [], f"Nível de confiança: {sol.get('trust_level')}")
    if code == "solution_impact_proven":
        ok = sol.get("trust_level") in ("evidenced", "verified") and (sol.get("validated_results") or 0) >= 1 and sol.get("stage") in ("running", "completed") and sol.get("kind") != "idea"
        return _basis(ok, ver if ok else None, [], "Execução com evidência aceita e resultado validado" if ok else "Exige execução, evidência aceita e resultado validado por revisor independente")
    if code == "solution_replicable":
        ok = bool(sol.get("allow_replication")) and sol.get("stage") in ("running", "completed") and (sol.get("replicability_confidence") or 0) >= 50
        return _basis(ok, as_date(sol.get("updated_at")) if ok else None, [], "Replicação autorizada com perfil de replicabilidade suficiente" if ok else "Exige execução, replicação autorizada e perfil de replicabilidade com confiança ≥ 50%")
    if code == "solution_seeking_funding":
        ok = bool(sol.get("seeking_funding")) and sol.get("visibility") == "published"
        return _basis(ok, as_date(sol.get("updated_at")) if ok else None, [], "Captação aberta" if ok else "Sem captação aberta")
    raise ValueError("critério de solução desconhecido")


def compute(defs: list[dict], *, scope: str, facts: dict | None = None, solution: dict | None = None, today: date | None = None, ctx: dict | None = None) -> list[dict]:
    """defs: itens publicados do catálogo 'badge' ({code,label,description,attributes,source_citation,...})."""
    today = today or date.today()
    out = []
    for d in defs:
        a = d.get("attributes") or {}
        if a.get("scope") != scope or a.get("criterion") not in CRITERIA:
            continue
        params = a.get("params") or {}
        b = (_org_criterion(a["criterion"], params, facts or {}, today, ctx or {}) if scope == "organization"
             else _solution_criterion(a["criterion"], params, solution or {}, today))
        valid_until = None
        status = "not_earned"
        if b["ok"]:
            days = int(a.get("validity_days") or 365)
            cands = list(b["expiries"])
            if b["verified_at"]:
                cands.append(b["verified_at"] + timedelta(days=days))
            valid_until = min(cands) if cands else None
            status = "expired" if valid_until and valid_until < today else "earned"
        out.append({
            "code": d["code"], "label": d["label"], "definition": d.get("description"), "criterion": a["criterion"], "criterion_params": params,
            "status": status, "earned": status == "earned", "verified_at": str(b["verified_at"]) if b["verified_at"] else None,
            "valid_until": str(valid_until) if valid_until else None, "source": d.get("source_citation") or "Critério interno da plataforma",
            "detail": b["detail"], "disclaimer": BADGE_DISCLAIMER,
        })
    return out
