"""Maturidade institucional 0–6 (puro). Cumulativa: o nível é o maior N tal que 1..N estão atendidos.
Aplica-se ao lado proponente (osc, provider, individual). Limiares em config/institutional_maturity.json (HIPÓTESE inicial)."""
from __future__ import annotations

from datetime import date

from .common import as_date, config
from .documents import best_state
from ...clock import today as _hoje_utc  # data do produto é UTC; ver impacto/clock.py

PATH_TEXT = {
    1: [("Informe a natureza jurídica e a descrição da iniciativa", "Perfil institucional"), ("Defina causa(s) e território de atuação", "Perfil")],
    2: [("Consulte um profissional (advogado/contador) sobre a forma de formalização adequada ao seu objetivo", "Validação profissional"),
        ("Obtenha o CNPJ e registre-o no cadastro", "Formalização")],
    3: [("Envie estatuto/contrato social e cartão CNPJ", "Documentos"), ("Aguarde a validação dos documentos e a revisão de compliance", "Validação"),
        ("Solicite a revisão da situação institucional (meta: Regular)", "Situação institucional")],
    4: [("Registre as qualificações/certificações que possui (OSCIP, OS, CEBAS etc.) com comprovante", "Qualificações"),
        ("Aguarde a verificação pela administração", "Validação")],
    5: [("Verifique as modalidades de financiamento publicadas e cumpra os requisitos de ao menos uma", "Elegibilidade")],
    6: [("Execute e conclua projetos, registre evidências e resultados e peça validação independente", "Histórico de execução")],
}


def compute(facts: dict, *, today: date | None = None, track: dict | None = None, modality_states: dict[str, str] | None = None) -> dict:
    """facts = org_institutional_facts; track = {completed_projects, evidences_accepted, validated_indicator_values};
    modality_states = {código_da_modalidade: state} já avaliado pelo motor de elegibilidade (para o nível 5)."""
    today = today or _hoje_utc()
    cfg = config()
    labels = {int(k): v for k, v in cfg["levels"].items()}
    if not facts.get("kind_is_proponent", facts.get("kind") in ("osc", "provider", "individual")):
        return {"applicable": False, "level": None, "label": None, "achieved": [], "next": None, "path": [],
                "note": "Maturidade institucional se aplica ao lado proponente (OSC, profissional, pesquisador)."}
    docs = [{"doc_type": d.get("doc_type"), "scan_status": d.get("scan_status"), "validation_status": d.get("validation_status"), "valid_until": d.get("valid_until")}
            for d in facts.get("documents") or []]
    base_ok = all(best_state(docs, t, today)[0] == "validated" for t in cfg["base_documents"])
    quals_ok = [q for q in facts.get("qualifications") or []
                if q.get("status") == "verified" and not (as_date(q.get("expiration_date")) and as_date(q.get("expiration_date")) < today)]
    tr = track or {}
    apt = sorted(m for m, s in (modality_states or {}).items() if s in ("eligible", "probably_eligible", "needs_professional_validation"))
    need = cfg["track_record"]

    def req(code, label, met, detail, fix):
        return {"code": code, "label": label, "met": bool(met), "detail": detail, "how_to_fix": None if met else fix}

    levels: dict[int, list[dict]] = {
        1: [req("nature", "Natureza jurídica informada", bool(facts.get("legal_nature_code")), facts.get("legal_nature_code") or "não informada", "Informe a natureza jurídica no perfil"),
            req("profile", "Descrição da iniciativa", facts.get("has_description"), "descrição preenchida" if facts.get("has_description") else "sem descrição", "Descreva a iniciativa"),
            req("cause", "Causa de atuação", bool(facts.get("causes")), ", ".join(facts.get("causes") or []) or "não informada", "Informe ao menos uma causa")],
        2: [req("cnpj", "CNPJ informado (formalizado)", facts.get("cnpj_present"), "CNPJ presente" if facts.get("cnpj_present") else "sem CNPJ", "Formalize e informe o CNPJ (consulte profissional habilitado)")],
        3: [req("base_docs", "Documentação básica validada", base_ok, ", ".join(cfg["base_documents"]), "Envie e aguarde a validação de " + ", ".join(cfg["base_documents"])),
            req("compliance", "Compliance aprovado", facts.get("compliance_status") == "approved", str(facts.get("compliance_status")), "Conclua a análise de compliance"),
            req("status", "Situação institucional regular", facts.get("institutional_status") == "regular", str(facts.get("institutional_status")), "Solicite a revisão da situação institucional")],
        4: [req("qualification", "Ao menos uma qualificação/certificação verificada e vigente", bool(quals_ok), ", ".join(q["type"] for q in quals_ok) or "nenhuma verificada", "Registre e comprove uma qualificação")],
        5: [req("modality", "Apta a ao menos uma modalidade de financiamento/parceria", bool(apt), ", ".join(apt) or "nenhuma modalidade com requisitos cumpridos", "Cumpra os requisitos de uma modalidade publicada")],
        6: [req("completed", "Projetos concluídos na plataforma", (tr.get("completed_projects") or 0) >= need["completed_projects"], f"{tr.get('completed_projects') or 0}/{need['completed_projects']}", "Conclua projetos"),
            req("evidences", "Evidências aceitas", (tr.get("evidences_accepted") or 0) >= need["accepted_evidences"], f"{tr.get('evidences_accepted') or 0}/{need['accepted_evidences']}", "Registre evidências e obtenha aceite"),
            req("indicators", "Resultados validados por outra organização", (tr.get("validated_indicator_values") or 0) >= need["validated_indicator_values"], f"{tr.get('validated_indicator_values') or 0}/{need['validated_indicator_values']}", "Peça validação independente de resultados")],
    }
    level = 0
    for n in range(1, 7):
        if all(r["met"] for r in levels[n]):
            level = n
        else:
            break
    achieved = [{"level": n, "label": labels[n]} for n in range(0, level + 1)]
    nxt = None
    if level < 6:
        n = level + 1
        nxt = {"level": n, "label": labels[n], "requirements": levels[n]}
    return {"applicable": True, "level": level, "label": labels[level], "achieved": achieved, "next": nxt,
            "path": [{"level": n, "label": labels[n], "steps": [{"text": t, "area": a} for t, a in PATH_TEXT[n]], "done": n <= level} for n in range(1, 7)],
            "apt_modalities": apt, "criteria_status": cfg["status"], "version": cfg["version"],
            "note": "Nível calculado a partir de dados e documentos da plataforma; não é certificação nem garantia de elegibilidade."}
