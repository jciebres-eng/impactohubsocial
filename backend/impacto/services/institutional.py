"""Camada institucional: carrega fatos/catálogos/regras do banco (sob RLS) e chama os motores puros.

Nada aqui lê plano/assinatura. Toda avaliação carrega versão do motor, regras usadas (código+versão+fonte) e data.
"""
from __future__ import annotations

import json
from datetime import date

from ..db.pq import Connection, Json
from ..engines.institutional import badges as badge_engine
from ..engines.institutional import eligibility as elig
from ..engines.institutional import maturity as mat
from ..engines.institutional.common import config
from .documents import usable_statuses

CATALOGS = ("legal_nature", "qualification_type", "institutional_profile", "institutional_status", "funding_modality", "badge")


# ------------------------------------------------------------------------------------------------ catálogos
def catalog(c: Connection, name: str | None = None) -> dict[str, dict[str, dict]]:
    """Itens PUBLICADOS por catálogo: {catalog: {code: item}}."""
    q = ("SELECT catalog, code, version, label, description, attributes, source_citation, source_url, source_date, confidence,"
         " needs_professional_validation FROM inst_catalog_items WHERE status = 'published'")
    rows = c.query(q + (" AND catalog = $1" if name else "") + " ORDER BY catalog, label", *([name] if name else []))
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        r["attributes"] = _json(r["attributes"])
        out.setdefault(r["catalog"], {})[r["code"]] = r
    return out


def _json(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


def require_catalog_code(cat: dict[str, dict[str, dict]], catalog_name: str, code: str | None, field: str):
    """Valida que o código existe e está publicado; levanta ValueError com mensagem em português."""
    if code is not None and code not in cat.get(catalog_name, {}):
        raise ValueError(f"{field}: código '{code}' não consta no catálogo publicado ({catalog_name})")


# ------------------------------------------------------------------------------------------------ fatos
def facts(c: Connection, org_id: str) -> dict:
    f = c.scalar("SELECT org_institutional_facts($1)", org_id)
    f = _json(f)
    ok = set(usable_statuses())
    for d in f.get("documents", []):
        d["scan_status"] = "clean" if d.get("scan_status") in ok else d.get("scan_status")
    return f


def track(c: Connection, org_id: str) -> dict:
    t = c.one("SELECT * FROM org_track_record($1)", org_id) or {}
    vi = c.scalar("SELECT count(*) FROM indicator_values WHERE org_id = $1 AND status = 'validated'", org_id) or 0
    return {"completed_projects": int(t.get("completed_projects") or 0), "evidences_accepted": int(t.get("evidences_accepted") or 0),
            "validated_indicator_values": int(vi)}


# ------------------------------------------------------------------------------------------------ regras → itens
def _rule_item(r: dict) -> dict:
    return {"code": f"rule:{r['code']}", "label": r["name"], "requirement": _json(r["requirement"]), "mandatory": r["mandatory"],
            "how_to_fix": r["how_to_fix"], "needs_professional_validation": r["needs_professional_validation"],
            "source": {"kind": "rule", "rule_code": r["code"], "version": r["version"], "citation": r["source_citation"], "url": r["source_url"],
                       "consulted_on": str(r["source_consulted_on"]) if r["source_consulted_on"] else None, "confidence": r["confidence"], "scope": r["scope_type"]}}


def published_rules(c: Connection, *, modality: str | None = None, call_id: str | None = None, funder_org: str | None = None,
                    today: date | None = None) -> list[dict]:
    today = today or date.today()
    rows = c.query(
        "SELECT * FROM eligibility_rules WHERE status = 'published' AND (effective_from IS NULL OR effective_from <= $1::date) AND (effective_to IS NULL OR effective_to >= $1::date)"
        " AND (scope_type = 'global' OR (scope_type = 'modality' AND scope_ref = $2) OR (scope_type = 'call' AND scope_ref = $3) OR (scope_type = 'funder' AND scope_ref = $4))"
        " ORDER BY code", today, modality, call_id, funder_org)
    return [_rule_item(r) for r in rows]


def _src(kind: str, ref: str) -> dict:
    return {"kind": kind, "citation": f"Requisito informado pelo {'edital' if kind == 'call' else 'financiador'} ({ref})", "confidence": "high", "rule_code": None, "version": None, "url": None, "consulted_on": None}


def call_items(call: dict) -> list[dict]:
    """Requisitos estruturais declarados pelo próprio edital (fonte = edital; não são regra legal da plataforma)."""
    src = _src("call", str(call.get("id")))
    out = []
    if call.get("accepted_legal_natures"):
        out.append({"code": "call:legal_nature", "label": "Natureza jurídica aceita pelo edital", "requirement": {"type": "legal_nature_in", "values": list(call["accepted_legal_natures"])},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    for q in call.get("required_certifications") or []:
        out.append({"code": f"call:qualification:{q}", "label": f"Qualificação exigida: {q.upper()}", "requirement": {"type": "qualification_all", "values": [q]},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    if call.get("required_document_types"):
        out.append({"code": "call:documents", "label": "Documentos exigidos pelo edital (validados)", "requirement": {"type": "document_valid", "doc_types": list(call["required_document_types"])},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    if call.get("min_org_age_months"):
        out.append({"code": "call:org_age", "label": f"Tempo mínimo de existência ({call['min_org_age_months']} meses)", "requirement": {"type": "org_age_min", "months": int(call["min_org_age_months"])},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    if call.get("min_maturity") is not None:
        out.append({"code": "call:maturity", "label": f"Maturidade institucional mínima (nível {call['min_maturity']})", "requirement": {"type": "maturity_min", "level": int(call["min_maturity"])},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    return out


def funder_items(fp: dict, funder_org: str) -> list[dict]:
    src = _src("funder", funder_org)
    out = []
    if fp.get("accepted_legal_natures"):
        out.append({"code": "funder:legal_nature", "label": "Natureza jurídica aceita pelo financiador", "requirement": {"type": "legal_nature_in", "values": list(fp["accepted_legal_natures"])},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    for q in fp.get("required_qualifications") or []:
        out.append({"code": f"funder:qualification:{q}", "label": f"Qualificação exigida pelo financiador: {q.upper()}", "requirement": {"type": "qualification_all", "values": [q]},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    if fp.get("required_document_types"):
        out.append({"code": "funder:documents", "label": "Documentos exigidos pelo financiador (validados)", "requirement": {"type": "document_valid", "doc_types": list(fp["required_document_types"])},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    if fp.get("min_org_age_months"):
        out.append({"code": "funder:org_age", "label": f"Tempo mínimo de existência ({fp['min_org_age_months']} meses)", "requirement": {"type": "org_age_min", "months": int(fp["min_org_age_months"])},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    if fp.get("min_maturity") is not None:
        out.append({"code": "funder:maturity", "label": f"Maturidade institucional mínima (nível {fp['min_maturity']})", "requirement": {"type": "maturity_min", "level": int(fp["min_maturity"])},
                    "mandatory": True, "needs_professional_validation": False, "source": src, "how_to_fix": None})
    return out


# ------------------------------------------------------------------------------------------------ maturidade
def modality_states(c: Connection, f: dict, today: date | None = None) -> dict[str, str]:
    """Estado de elegibilidade do org em cada modalidade publicada que tenha regra publicada (sem regra → não avaliável, fora do nível 5)."""
    today = today or date.today()
    out = {}
    for code in catalog(c, "funding_modality").get("funding_modality", {}):
        items = published_rules(c, modality=code, today=today)
        scoped = [i for i in items if i["source"]["scope"] == "modality"]
        if not scoped:
            continue
        out[code] = elig.evaluate(f, items, today=today, maturity={"level": None})["state"]
    return out


def maturity(c: Connection, org_id: str, f: dict | None = None, today: date | None = None) -> dict:
    f = f or facts(c, org_id)
    today = today or date.today()
    states = modality_states(c, f, today) if f.get("cnpj_present") else {}
    return mat.compute(f, today=today, track=track(c, org_id), modality_states=states)


# ------------------------------------------------------------------------------------------------ elegibilidade
def evaluate_for_call(c: Connection, org_id: str, call: dict, *, f: dict | None = None, m: dict | None = None, today: date | None = None) -> dict:
    f = f or facts(c, org_id)
    m = m or maturity(c, org_id, f, today)
    items = call_items(call) + published_rules(c, modality=call.get("funding_modality"), call_id=str(call.get("id")), funder_org=str(call["owner_org_id"]) if call.get("owner_org_id") else None, today=today)
    res = elig.evaluate(f, items, today=today, maturity=m, subject={"type": "call", "id": str(call.get("id")), "title": call.get("title"), "modality": call.get("funding_modality")})
    res["modality"] = call.get("funding_modality")
    return res


def evaluate_for_modality(c: Connection, org_id: str, code: str, *, f: dict | None = None, m: dict | None = None, today: date | None = None) -> dict:
    f = f or facts(c, org_id)
    m = m or maturity(c, org_id, f, today)
    items = published_rules(c, modality=code, today=today)
    return elig.evaluate(f, items, today=today, maturity=m, subject={"type": "modality", "id": code})


def evaluate_for_funder(c: Connection, org_id: str, funder_org: str, fp: dict, *, f: dict | None = None, m: dict | None = None, today: date | None = None) -> dict:
    f = f or facts(c, org_id)
    m = m or maturity(c, org_id, f, today)
    items = funder_items(fp or {}, funder_org) + published_rules(c, funder_org=funder_org, today=today)
    return elig.evaluate(f, items, today=today, maturity=m, subject={"type": "funder", "id": funder_org})


def persist(c: Connection, org_id: str, viewer_org: str, user_id: str, subject_type: str, subject_ref: str, result: dict) -> str:
    return c.scalar("INSERT INTO eligibility_evaluations(org_id, viewer_org_id, subject_type, subject_ref, state, result, engine_version, rules_digest, created_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8::jsonb,$9) RETURNING id::text", org_id, viewer_org, subject_type, subject_ref[:80], result["state"],
                    Json(result), result["engine_version"], Json(result["rules_digest"]), user_id)


# ------------------------------------------------------------------------------------------------ badges
def org_badges(c: Connection, org_id: str, f: dict | None = None, today: date | None = None) -> list[dict]:
    f = f or facts(c, org_id)
    defs = list(catalog(c, "badge").get("badge", {}).values())
    last = c.scalar("SELECT max(created_at)::date FROM eligibility_evaluations WHERE org_id = $1 AND created_at > now() - interval '30 days'", org_id)
    return badge_engine.compute(defs, scope="organization", facts=f, today=today, ctx={"last_eligibility_evaluation": last})


def solution_badges(c: Connection, sol: dict, today: date | None = None) -> list[dict]:
    defs = list(catalog(c, "badge").get("badge", {}).values())
    return badge_engine.compute(defs, scope="solution", solution=sol, today=today)


# ------------------------------------------------------------------------------------------------ visão geral
def overview(c: Connection, org_id: str, today: date | None = None) -> dict:
    """Pode participar × pode receber × ainda precisa cumprir requisitos."""
    today = today or date.today()
    f = facts(c, org_id)
    cat = catalog(c)
    m = maturity(c, org_id, f, today)
    mods = []
    for code, item in cat.get("funding_modality", {}).items():
        items = published_rules(c, modality=code, today=today)
        scoped = [i for i in items if i["source"]["scope"] == "modality"]
        if not scoped:
            mods.append({"modality": code, "label": item["label"], "state": None, "state_label": "Sem regra publicada — não foi possível confirmar",
                         "missing": [], "evaluable": False})
            continue
        r = elig.evaluate(f, items, today=today, maturity=m)
        mods.append({"modality": code, "label": item["label"], "state": r["state"], "state_label": r["state_label"], "summary": r["summary"],
                     "missing": r["missing_to_become_eligible"], "evaluable": True})
    receivable = [x for x in mods if x["state"] in ("eligible", "probably_eligible", "needs_professional_validation")]
    needs = [{"modality": x["modality"], "label": x["label"], "missing": x["missing"]} for x in mods if x["state"] in ("not_eligible", "pending")]
    status = f.get("institutional_status")
    participates = status not in ("suspended", "archived")
    return {
        "organization": {"legal_nature_code": f.get("legal_nature_code"), "institutional_profile": f.get("institutional_profile"), "institutional_status": status,
                         "cnpj_present": f.get("cnpj_present")},
        "participation": {"label": "Pode participar" if participates else "Participação suspensa", "can_participate": participates,
                          "scope": ["Banco de Ideias e Biblioteca de Soluções", "Rede e oportunidades públicas", "Diagnóstico e caminho de formalização"] + (["Candidaturas a oportunidades (sujeitas à elegibilidade de cada uma)"] if f.get("cnpj_present") else [])},
        "can_receive": {"label": "Pode receber este tipo específico de recurso", "modalities": receivable},
        "needs": {"label": "Ainda precisa cumprir requisitos", "items": needs},
        "modalities": mods, "maturity": m, "badges": [b for b in org_badges(c, org_id, f, today)],
        "disclaimer": elig.DISCLAIMER_LEGAL,
        "config": {"maturity_criteria": config()["status"]},
    }


# ------------------------------------------------------------------------------------------------ fiscal (camadas separadas)
def fiscal_layers(c: Connection, res: dict, call: dict) -> dict:
    """Separa, para oportunidades de incentivo fiscal, as camadas que NUNCA devem ser confundidas (ADR-011): estimativa, regra identificada,
    possível elegibilidade, elegibilidade documental e validação profissional. Nenhuma garante benefício fiscal."""
    rules = c.query("SELECT code, version, name, mechanism, jurisdiction, source_citation, source_url, effective_from, effective_to FROM fiscal_rules"
                    " WHERE status = 'approved' AND (cardinality(causes) = 0 OR causes && $1::text[]) ORDER BY code", call.get("causes") or [])
    doc_reqs = [r for r in res["requirements"] if r["document_needed"] or r["code"].endswith("documents")]
    return {
        "ESTIMATIVA": {"available": False, "note": "A estimativa de dedução depende do regime tributário e do IR devido da empresa financiadora; é calculada apenas no módulo fiscal da empresa, "
                                                  "e somente com regra aprovada. Nunca é economia garantida."},
        "REGRA IDENTIFICADA": {"rules": rules, "note": ("Regras fiscais aprovadas (2 revisores) com fonte e vigência." if rules else
                                                         "Nenhuma regra fiscal aprovada nesta instalação para esta causa: não foi possível identificar regra aplicável.")},
        "POSSÍVEL ELEGIBILIDADE": {"state": res["state"], "state_label": res["state_label"], "note": "Resultado de apoio; não é parecer jurídico nem fiscal."},
        "ELEGIBILIDADE DOCUMENTAL": {"requirements": len(doc_reqs), "met": sum(r["status"] == "met" for r in doc_reqs),
                                     "missing": [r["label"] for r in doc_reqs if r["status"] != "met"]},
        "VALIDAÇÃO PROFISSIONAL": {"required": True, "note": "Obrigatória antes de qualquer decisão fiscal: contador/tributarista habilitado confirma enquadramento, limites e vigência."},
    }


def suggest_status(f: dict, today: date | None = None) -> dict:
    """Sugestão (não decisão) de situação institucional para a administração; a decisão é humana."""
    from ..engines.institutional.documents import best_state
    today = today or date.today()
    base = config()["base_documents"]
    docs = [{"doc_type": d.get("doc_type"), "scan_status": d.get("scan_status"), "validation_status": d.get("validation_status"), "valid_until": d.get("valid_until")} for d in f.get("documents", [])]
    states = {t: best_state(docs, t, today)[0] for t in base}
    if not f.get("cnpj_present"):
        return {"status": "in_structuring", "reason": "Sem CNPJ cadastrado", "documents": states}
    bad = [t for t, s in states.items() if s in ("absent", "expired", "rejected")]
    if f.get("institutional_status") in ("suspended", "archived", "irregular"):
        return {"status": f["institutional_status"], "reason": "Situação definida pela administração (não sugerimos alteração automática)", "documents": states}
    if bad:
        return {"status": "documents_pending", "reason": "Documentos básicos ausentes, expirados ou rejeitados: " + ", ".join(bad), "documents": states}
    if all(s == "validated" for s in states.values()) and f.get("compliance_status") == "approved":
        return {"status": "regular", "reason": "Documentação básica validada e compliance aprovado", "documents": states}
    if any(s == "validated" for s in states.values()):
        return {"status": "partially_regular", "reason": "Parte da documentação básica validada; faltam validações ou compliance", "documents": states}
    return {"status": "registered", "reason": "Documentos enviados aguardando validação", "documents": states}


# ------------------------------------------------------------------------------------------------ proponentes (lote, para cartões)
def proponents(c: Connection, org_ids: list[str]) -> dict[str, dict]:
    """Natureza jurídica, situação institucional e qualificações VERIFICADAS e vigentes de cada organização autora (somente dados públicos)."""
    ids = sorted(set(org_ids))
    if not ids:
        return {}
    out = {r["id"]: {"kind": r["kind"], "legal_nature_code": r["legal_nature_code"], "institutional_profile": r["institutional_profile"],
                     "institutional_status": r["institutional_status"], "verified_qualifications": []}
           for r in c.query("SELECT id::text AS id, kind, legal_nature_code, institutional_profile, institutional_status FROM organizations WHERE id = ANY($1::uuid[])", ids)}
    for r in c.query("SELECT org_id::text AS oid, qualification_type FROM organization_qualifications WHERE org_id = ANY($1::uuid[]) AND verification_status = 'verified'"
                     " AND (expiration_date IS NULL OR expiration_date >= current_date) ORDER BY qualification_type", ids):
        out[r["oid"]]["verified_qualifications"].append(r["qualification_type"])
    return out


# ------------------------------------------------------------------------------------------------ declaração institucional (determinística)
def statement(c: Connection, org_id: str, today: date | None = None) -> dict:
    """Texto-base de apoio para a organização usar em propostas. Só afirma o que está cadastrado e rotula o estado de cada afirmação;
    o que não consta vira 'Não foi possível confirmar.' Nunca inventa qualificação, certificação, benefício fiscal, documento ou regra legal.
    Gerado por regras (sem IA externa) — um rascunho que exige revisão humana."""
    today = today or date.today()
    f = facts(c, org_id)
    if not f:
        return {}
    cat = catalog(c)
    nat = (cat["legal_nature"].get(f.get("legal_nature_code")) or {}).get("label")
    prof = (cat["institutional_profile"].get(f.get("institutional_profile")) or {}).get("label")
    lines: list[dict] = []

    def add(text: str, state: str, source: str):
        lines.append({"text": text, "state": state, "source": source})

    add(f"Natureza jurídica: {nat}." if nat else "Natureza jurídica: Não foi possível confirmar.", "declared" if nat else "unknown", "Perfil institucional (declarado pela organização)")
    if prof:
        add(f"Perfil de atuação: {prof}.", "declared", "Perfil institucional (declarado pela organização)")
    add("CNPJ cadastrado na plataforma." if f.get("cnpj_present") else "CNPJ: Não foi possível confirmar (organização sem CNPJ cadastrado).",
        "declared" if f.get("cnpj_present") else "unknown", "Cadastro")
    quals = f.get("qualifications") or []
    if not quals:
        add("Qualificações e certificações: Não foi possível confirmar (nenhuma registrada).", "unknown", "Qualificações")
    for q in quals:
        label = (cat["qualification_type"].get(q["type"]) or {}).get("label", q["type"].upper())
        exp = as_date_safe(q.get("expiration_date"))
        if q.get("status") == "verified" and (not exp or exp >= today):
            add(f"{label}: verificada pela plataforma" + (f" (vigência até {exp.strftime('%d/%m/%Y')})." if exp else "."), "verified", "Verificação administrativa")
        elif q.get("status") == "verified":
            add(f"{label}: vigência expirada em {exp.strftime('%d/%m/%Y')}; não pode ser afirmada.", "expired", "Verificação administrativa")
        else:
            add(f"{label}: declarada pela organização, ainda sem verificação — não afirmar como obtida.", "declared", "Qualificações")
    docs = f.get("documents") or []
    valid = sorted({d["doc_type"] for d in docs if d.get("validation_status") == "validated" and d.get("scan_status") == "clean"
                    and not (d.get("valid_until") and as_date_safe(d["valid_until"]) and as_date_safe(d["valid_until"]) < today)})
    add("Documentos validados no cofre: " + ", ".join(valid) + "." if valid else "Documentos validados: Não foi possível confirmar (nenhum validado).", "verified" if valid else "unknown", "Cofre de documentos")
    return {"lines": lines, "generated_by": "rules@1.0 (sem IA externa)", "generated_on": str(today),
            "disclaimer": "Rascunho de apoio. Afirmações 'declarada' não são prova; revise antes de usar em proposta. Requer validação profissional para qualquer enquadramento legal ou fiscal."}


def as_date_safe(v):
    from ..engines.institutional.common import as_date
    return as_date(v)
