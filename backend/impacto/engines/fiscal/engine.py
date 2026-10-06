"""Fiscal Engine (fiscal-engine@1.0.0) — regras versionadas, NUNCA aconselhamento tributário.

Somente regras com status ``approved`` (dupla aprovação por revisores distintos, garantida por CHECK no banco) e
vigentes na data de referência são avaliadas. A saída separa SEMPRE quatro rótulos:

* REGRA — texto/fonte oficial citada, versão e vigência;
* ELEGIBILIDADE PROVÁVEL — provável | improvável | indeterminada, com motivos;
* ESTIMATIVA — teto de dedução estimado (limite % × IR devido informado pela empresa), nunca "economia garantida";
* VALIDAÇÃO PROFISSIONAL — sempre obrigatória antes de qualquer decisão.
Fiscal não entra no score do Match (ADR-011).
"""
from __future__ import annotations

from datetime import date
from ...clock import today as _hoje_utc  # data do produto é UTC; ver impacto/clock.py

ENGINE_VERSION = "fiscal-engine@1.0.0"
DISCLAIMER = ("Informação de apoio baseada em regras cadastradas e revisadas na plataforma. Não constitui aconselhamento "
              "tributário, jurídico ou contábil. A aplicabilidade, os limites e a vigência devem ser confirmados por "
              "profissional habilitado antes de qualquer decisão.")


def _active(rule: dict, ref: date) -> bool:
    if rule.get("status") != "approved":
        return False
    f, t = rule.get("effective_from"), rule.get("effective_to")
    return (f is None or f <= ref) and (t is None or t >= ref)


def evaluate(rules: list[dict], tax_profile: dict | None, project: dict | None, ref: date | None = None) -> dict:
    ref = ref or _hoje_utc()
    tp = tax_profile or {}
    out = []
    for r in rules:
        if not _active(r, ref):
            continue
        reasons, status = [], "provavel"
        regime = tp.get("regime") or "unknown"
        if r.get("taxpayer_regimes"):
            if regime == "unknown":
                status = "indeterminada"
                reasons.append("Regime tributário da empresa não informado")
            elif regime not in r["taxpayer_regimes"]:
                status = "improvavel"
                reasons.append(f"Regra aplicável ao(s) regime(s) {', '.join(r['taxpayer_regimes'])}; empresa informou {regime}")
            else:
                reasons.append(f"Regime informado ({regime}) compatível com a regra")
        if r.get("uf") and tp.get("uf") and r["uf"] != tp["uf"]:
            status = "improvavel"
            reasons.append(f"Regra estadual de {r['uf']}")
        if project is not None and r.get("causes"):
            if not set(project.get("causes") or []) & set(r["causes"]):
                status = "improvavel" if status != "indeterminada" else status
                reasons.append("Causa do projeto não corresponde ao mecanismo")
            else:
                reasons.append("Causa do projeto corresponde ao mecanismo")
        if r.get("project_requirements"):
            if status == "provavel":
                status = "indeterminada"
            reasons.append("Depende de requisitos do projeto não verificáveis automaticamente (ver checklist)")
        estimate = None
        ir = tp.get("estimated_ir_due_cents")
        if r.get("limit_pct") is not None and ir:
            cap = int(round(int(ir) * float(r["limit_pct"]) / 100))
            estimate = {"label": "ESTIMATIVA", "max_deductible_cents": cap, "basis": f"{float(r['limit_pct']):g}% × IR devido informado",
                        "combined_limit_group": r.get("combined_limit_group"),
                        "notes": "Teto estimado de dedução, não economia garantida. Limites combinados com outros incentivos podem reduzir o valor."}
        elif r.get("limit_pct") is None:
            reasons.append("Limite percentual não validado nesta regra — sem estimativa")
        out.append({
            "rule": {"label": "REGRA", "code": r["code"], "version": r["version"], "name": r["name"], "mechanism": r["mechanism"],
                     "jurisdiction": r["jurisdiction"], "source_citation": r["source_citation"], "source_url": r.get("source_url"),
                     "effective_from": r.get("effective_from"), "effective_to": r.get("effective_to"), "limit_note": r.get("limit_note")},
            "eligibility": {"label": "ELEGIBILIDADE PROVÁVEL", "status": status, "reasons": reasons},
            "estimate": estimate,
            "checklist": [dict(x, status="a_verificar") for x in (r.get("requirements") or []) + (r.get("project_requirements") or [])],
            "professional_validation": {"label": "VALIDAÇÃO PROFISSIONAL", "required": True},
        })
    return {"engine_version": ENGINE_VERSION, "reference_date": ref.isoformat(), "items": out, "disclaimer": DISCLAIMER,
            "rules_considered": len(out)}
