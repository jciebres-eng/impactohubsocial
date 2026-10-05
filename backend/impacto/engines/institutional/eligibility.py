"""INSTITUTIONAL ELIGIBILITY ENGINE (institutional-eligibility@1.0.0) — "esta organização pode concorrer a esta oportunidade?"
e "o que falta para ela se tornar elegível?". Puro e determinístico.

Nunca devolve só SIM/NÃO. Cinco estados:
  ELEGÍVEL · PROVAVELMENTE ELEGÍVEL · ELEGIBILIDADE PENDENTE · NÃO ELEGÍVEL · REQUER VALIDAÇÃO PROFISSIONAL.
Ausência de requisitos/regras NUNCA produz "elegível": produz PENDENTE ("Não foi possível confirmar").
Regra de origem legal (needs_professional_validation) nunca é tratada como certeza jurídica: mesmo com tudo comprovado, o estado é
REQUER VALIDAÇÃO PROFISSIONAL.
"""
from __future__ import annotations

from datetime import date

from .common import (DISCLAIMER_LEGAL, SEVERITY, STATE_LABELS, STATUS_LABELS, as_date, br, config, months_between)
from .documents import best_state
from . import maturity as _maturity

ENGINE_VERSION = "institutional-eligibility@1.0.0"

# Conjunto FECHADO de tipos de requisito (a API valida; o motor recusa o que não conhece)
REQUIREMENT_TYPES: dict[str, dict] = {
    "legal_nature_in": {"required": ("values",), "optional": ()},
    "qualification_any": {"required": ("values",), "optional": ()},
    "qualification_all": {"required": ("values",), "optional": ()},
    "maturity_min": {"required": ("level",), "optional": ()},
    "org_status_in": {"required": ("values",), "optional": ()},
    "document_valid": {"required": ("doc_types",), "optional": ("require_validated",)},
    "org_age_min": {"required": ("months",), "optional": ()},
    "cnpj_required": {"required": (), "optional": ()},
    "compliance_approved": {"required": (), "optional": ()},
}


def validate_requirement(req: dict) -> dict:
    """Valida e normaliza um requisito. Levanta ValueError com mensagem em português."""
    if not isinstance(req, dict) or req.get("type") not in REQUIREMENT_TYPES:
        raise ValueError(f"tipo de requisito inválido; aceitos: {', '.join(sorted(REQUIREMENT_TYPES))}")
    spec = REQUIREMENT_TYPES[req["type"]]
    extra = set(req) - {"type", *spec["required"], *spec["optional"]}
    if extra:
        raise ValueError(f"parâmetros não reconhecidos: {', '.join(sorted(extra))}")
    out = {"type": req["type"]}
    for k in spec["required"]:
        if k not in req:
            raise ValueError(f"parâmetro obrigatório ausente: {k}")
    for k in ("values", "doc_types"):
        if k in req:
            v = req[k]
            if not isinstance(v, list) or not v or len(v) > 30 or not all(isinstance(x, str) and 2 <= len(x) <= 60 for x in v):
                raise ValueError(f"{k}: lista de 1 a 30 códigos")
            out[k] = v
    if "level" in req:
        if not isinstance(req["level"], int) or isinstance(req["level"], bool) or not 0 <= req["level"] <= 6:
            raise ValueError("level: inteiro de 0 a 6")
        out["level"] = req["level"]
    if "months" in req:
        if not isinstance(req["months"], int) or isinstance(req["months"], bool) or not 1 <= req["months"] <= 1200:
            raise ValueError("months: inteiro de 1 a 1200")
        out["months"] = req["months"]
    if "require_validated" in req:
        if not isinstance(req["require_validated"], bool):
            raise ValueError("require_validated: booleano")
        out["require_validated"] = req["require_validated"]
    return out


def _worst(results: list[tuple[str, str]]) -> tuple[str, str]:
    return max(results, key=lambda r: SEVERITY[r[0]])


def _best(results: list[tuple[str, str]]) -> tuple[str, str]:
    return min(results, key=lambda r: SEVERITY[r[0]])


def _qualification(facts: dict, qtype: str, today: date, warn_days: int) -> tuple[str, str, dict]:
    quals = [q for q in facts.get("qualifications") or [] if q.get("type") == qtype]
    if not quals:
        return "unmet", f"Qualificação {qtype.upper()} não registrada", {"how": "Registre a qualificação e anexe o comprovante"}
    rank = {"verified": 0, "under_review": 1, "document_submitted": 1, "declared": 2}
    quals.sort(key=lambda q: rank.get(q.get("status"), 3))
    q = quals[0]
    exp = as_date(q.get("expiration_date"))
    extra = {"qualification_id": q.get("id"), "expiration_date": str(exp) if exp else None}
    if q.get("status") == "verified":
        if exp and exp < today:
            return "expired", f"Qualificação {qtype.upper()} verificada, mas expirada em {br(exp)}", {**extra, "how": "Renove e atualize o comprovante"}
        if exp and (exp - today).days <= warn_days:
            extra["warning"] = f"vence em {(exp - today).days} dia(s)"
        return "met", f"Qualificação {qtype.upper()} verificada" + (f" (válida até {br(exp)})" if exp else ""), extra
    if q.get("status") in ("under_review", "document_submitted"):
        return "pending_validation", f"Qualificação {qtype.upper()} informada com comprovante, aguardando validação", {**extra, "how": "Aguarde a análise da administração"}
    return "unknown", f"Qualificação {qtype.upper()} apenas declarada, sem comprovante", {**extra, "how": "Anexe o comprovante (certificado, ato ou protocolo)"}


def _eval_requirement(req: dict, facts: dict, docs: list[dict], maturity: dict | None, today: date) -> tuple[str, str, dict]:
    """Retorna (status, detalhe, extras)."""
    t = req["type"]
    warn = config()["qualification_warning_days"]
    if t == "legal_nature_in":
        code = facts.get("legal_nature_code")
        if not code:
            return "unknown", "Natureza jurídica não informada", {"how": "Informe a natureza jurídica no perfil institucional"}
        if code not in req["values"]:
            return "unmet", f"Natureza jurídica declarada ({code}) não consta entre as aceitas: {', '.join(req['values'])}", \
                {"how": "Verifique se a forma jurídica da organização é aceita por esta oportunidade"}
        proof = [best_state(docs, d, today)[0] for d in ("estatuto_social", "cartao_cnpj")]
        if "validated" in proof:
            return "met", f"Natureza jurídica ({code}) declarada e comprovada por documento validado", {}
        return "pending_validation", f"Natureza jurídica ({code}) declarada; falta documento comprobatório validado (estatuto ou cartão CNPJ)", \
            {"how": "Envie estatuto/cartão CNPJ e aguarde a validação", "document_needed": ["estatuto_social", "cartao_cnpj"]}
    if t in ("qualification_any", "qualification_all"):
        parts = [_qualification(facts, q, today, warn) for q in req["values"]]
        pick = (_best if t == "qualification_any" else _worst)([(p[0], p[1]) for p in parts])
        chosen = next(p for p in parts if (p[0], p[1]) == pick)
        extra = dict(chosen[2])
        if t == "qualification_any" and len(parts) > 1:
            return pick[0], ("Pelo menos uma de: " + ", ".join(x.upper() for x in req["values"]) + ". " + pick[1]), extra
        return pick[0], pick[1], extra
    if t == "maturity_min":
        lvl = (maturity or {}).get("level")
        if lvl is None:
            return "unknown", "Maturidade institucional não calculada", {}
        if lvl >= req["level"]:
            return "met", f"Maturidade nível {lvl} (mínimo {req['level']})", {}
        nxt = ((maturity or {}).get("next") or {})
        return "unmet", f"Maturidade nível {lvl}; o requisito é nível {req['level']}", {"how": ("Cumpra: " + "; ".join(r["label"] for r in nxt.get("requirements", []) if not r["met"])) if nxt.get("requirements") else "Avance no caminho de formalização"}
    if t == "org_status_in":
        st = facts.get("institutional_status")
        if st in req["values"]:
            return "met", f"Situação institucional: {st}", {}
        if st in ("under_review", "registered", "in_structuring"):
            return "unknown", f"Situação institucional ainda não revisada ({st})", {"how": "Conclua a documentação e solicite a revisão da situação institucional"}
        return "unmet", f"Situação institucional ({st}) não consta entre as exigidas: {', '.join(req['values'])}", {"how": "Regularize as pendências com a administração"}
    if t == "document_valid":
        need_val = req.get("require_validated", True)
        parts = []
        for dt in req["doc_types"]:
            st, d = best_state(docs, dt, today)
            if st == "validated" or (st == "pending_validation" and not need_val):
                parts.append(("met", f"{dt}: {('DOCUMENTO VALIDADO' if st == 'validated' else 'enviado e sem vírus')}", {"doc": dt, "state": st}))
            elif st == "pending_validation":
                parts.append(("pending_validation", f"{dt}: DOCUMENTO PENDENTE DE VALIDAÇÃO", {"doc": dt, "state": st, "how": "Aguarde a validação do documento"}))
            elif st == "expired":
                parts.append(("expired", f"{dt}: DOCUMENTO EXPIRADO em {br(as_date(d.get('valid_until')))}", {"doc": dt, "state": st, "how": "Envie versão atualizada"}))
            elif st == "rejected":
                parts.append(("unmet", f"{dt}: DOCUMENTO REJEITADO", {"doc": dt, "state": st, "how": "Corrija e reenvie o documento"}))
            else:
                parts.append(("unmet", f"{dt}: DOCUMENTO AUSENTE", {"doc": dt, "state": st, "how": "Envie o documento no cofre"}))
        worst = _worst([(p[0], p[1]) for p in parts])
        needed = [p[2]["doc"] for p in parts if p[0] != "met"]
        return worst[0], "; ".join(p[1] for p in parts), {"document_needed": needed, "how": next((p[2].get("how") for p in parts if p[0] == worst[0]), None)}
    if t == "org_age_min":
        f = as_date(facts.get("founded_on"))
        if not f:
            return "unknown", "Data de fundação não informada", {"how": "Informe a data de fundação (conforme cartão CNPJ)"}
        age = months_between(f, today)
        return ("met" if age >= req["months"] else "unmet"), f"Organização com {age} meses (mínimo {req['months']})", {}
    if t == "cnpj_required":
        return ("met", "CNPJ informado", {}) if facts.get("cnpj_present") else ("unmet", "Sem CNPJ", {"how": "Formalize a organização e informe o CNPJ"})
    if t == "compliance_approved":
        cs = facts.get("compliance_status")
        if cs == "approved":
            return "met", "Compliance aprovado pela administração", {}
        if cs in ("rejected", "suspended"):
            return "unmet", f"Compliance {cs}", {"how": "Fale com a administração da plataforma"}
        return "unknown", "Compliance ainda não concluído", {"how": "Envie os documentos e solicite a análise de compliance"}
    raise ValueError("tipo de requisito não implementado")


def evaluate(facts: dict, items: list[dict], *, today: date | None = None, maturity: dict | None = None,
             subject: dict | None = None) -> dict:
    """facts: saída de org_institutional_facts (+ 'documents' normalizados com scan_status). items: lista de
    {code,label,requirement,mandatory,how_to_fix,source:{kind,rule_code,version,citation,url,consulted_on,confidence},needs_professional_validation}."""
    today = today or date.today()
    docs = [{"doc_type": d.get("doc_type"), "scan_status": d.get("scan_status"), "validation_status": d.get("validation_status"),
             "valid_until": d.get("valid_until")} for d in facts.get("documents") or []]
    if maturity is None:
        maturity = _maturity.compute(facts, today=today)
    results, rules_digest = [], []
    for it in items:
        status, detail, extra = _eval_requirement(validate_requirement(it["requirement"]), facts, docs, maturity, today)
        src = it.get("source") or {}
        results.append({
            "code": it["code"], "label": it["label"], "status": status, "status_label": STATUS_LABELS[status], "mandatory": bool(it.get("mandatory", True)),
            "detail": detail, "how_to_fix": it.get("how_to_fix") or extra.get("how"), "document_needed": extra.get("document_needed") or [],
            "warning": extra.get("warning"), "source": src, "needs_professional_validation": bool(it.get("needs_professional_validation")),
        })
        if src.get("kind") == "rule":
            rules_digest.append({"code": src.get("rule_code"), "version": src.get("version"), "citation": src.get("citation"),
                                 "url": src.get("url"), "consulted_on": src.get("consulted_on"), "confidence": src.get("confidence")})
    mand = [r for r in results if r["mandatory"]]
    unmet = [r for r in mand if r["status"] in ("unmet", "expired")]
    unknown = [r for r in mand if r["status"] == "unknown"]
    pending = [r for r in mand if r["status"] == "pending_validation"]
    prof = [r for r in mand if r["needs_professional_validation"] and r["status"] in ("met", "pending_validation")]
    if not results:
        state, summary = "pending", "Nenhum requisito institucional foi cadastrado para esta oportunidade. Não foi possível confirmar a elegibilidade."
    elif unmet:
        state = "not_eligible"
        summary = "Não elegível no momento: " + "; ".join(r["label"] for r in unmet[:3]) + ("…" if len(unmet) > 3 else "")
    elif unknown:
        state, summary = "pending", "Elegibilidade pendente: não foi possível confirmar " + "; ".join(r["label"] for r in unknown[:3]) + ("…" if len(unknown) > 3 else "")
    elif prof:
        state, summary = "needs_professional_validation", "Requisitos documentados, mas há regra de origem legal que exige validação profissional antes de qualquer decisão."
    elif pending:
        state, summary = "probably_eligible", "Provavelmente elegível: há informações aguardando validação documental."
    else:
        state, summary = "eligible", "Todos os requisitos obrigatórios cadastrados foram atendidos e comprovados."
    missing = [{"requirement": r["label"], "action": r["how_to_fix"], "documents": r["document_needed"], "status": r["status"]}
               for r in results if r["status"] != "met" and r["mandatory"]]
    can_apply = state in ("eligible", "probably_eligible", "needs_professional_validation")
    return {
        "engine_version": ENGINE_VERSION, "state": state, "state_label": STATE_LABELS[state], "summary": summary,
        "requirements": sorted(results, key=lambda r: (-SEVERITY[r["status"]], r["code"])),
        "counts": {"met": sum(r["status"] == "met" for r in results), "unmet": sum(r["status"] == "unmet" for r in results),
                   "unknown": sum(r["status"] == "unknown" for r in results), "pending_validation": sum(r["status"] == "pending_validation" for r in results),
                   "expired": sum(r["status"] == "expired" for r in results)},
        "missing_to_become_eligible": missing, "can_compete_label": ("Pode concorrer" if can_apply else "Ainda precisa cumprir requisitos"),
        "rules_digest": rules_digest, "maturity": {k: maturity.get(k) for k in ("level", "label")}, "evaluated_on": str(today),
        "disclaimer": DISCLAIMER_LEGAL, "subject": subject or {},
    }
