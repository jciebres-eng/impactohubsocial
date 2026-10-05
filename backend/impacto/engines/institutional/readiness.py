"""Prontidão para captação de uma solução/projeto. Critérios objetivos sobre dados cadastrados; sem dado → 'desconhecido' (nunca vira zero
nem número inventado). A nota só é exibida com confiança suficiente. Não é parecer, nem garantia de financiamento."""
from __future__ import annotations

MIN_CONFIDENCE = 0.6


def compute(sol: dict, feats: dict, proponent: dict | None) -> dict:
    p = proponent or {}
    crit: list[dict] = []

    def add(code: str, label: str, status: str, detail: str):
        crit.append({"code": code, "label": label, "status": status, "detail": detail})

    add("need", "Valor necessário informado", "met" if sol.get("needed_cents") is not None else "unmet",
        "Informado" if sol.get("needed_cents") is not None else "Informe o valor necessário")
    add("budget", "Orçamento estimado", "met" if sol.get("budget_cents") is not None else "unmet",
        "Informado" if sol.get("budget_cents") is not None else "Informe o orçamento")
    plan = bool(sol.get("goals")) or bool(sol.get("schedule"))
    add("plan", "Metas ou cronograma", "met" if plan else "unmet", "Metas/cronograma cadastrados" if plan else "Cadastre metas ou cronograma")
    res = (feats or {}).get("results", 0)
    add("results", "Resultados registrados", "met" if res else "unmet", f"{res} resultado(s) registrado(s)")
    ev = (feats or {}).get("accepted_items", 0)
    add("evidence", "Evidência aceita", "met" if ev else "unmet", f"{ev} item(ns) de evidência aceito(s)")
    own = sol.get("ownership_type") not in (None, "unknown") and bool(sol.get("authorization_publish"))
    add("ip", "Titularidade e autorização declaradas", "met" if own else "unmet", "Declaradas" if own else "Declare titularidade e autorização")
    add("modalities", "Modalidades de financiamento indicadas", "met" if sol.get("compatible_modalities") else "unmet",
        "Indicadas" if sol.get("compatible_modalities") else "Indique as modalidades compatíveis")
    if p:
        st = p.get("institutional_status")
        ok = st in ("regular", "partially_regular")
        add("proponent_status", "Proponente com situação institucional regular/parcialmente regular", "met" if ok else "unmet",
            f"Situação: {st}" if st else "Situação não definida")
        qn = len(p.get("verified_qualifications") or [])
        add("proponent_qualification", "Proponente com qualificação verificada", "met" if qn else "unmet", f"{qn} qualificação(ões) verificada(s)")
    else:
        add("proponent_status", "Proponente com situação institucional regular/parcialmente regular", "unknown", "Sem dados institucionais")
        add("proponent_qualification", "Proponente com qualificação verificada", "unknown", "Sem dados institucionais")
    known = [c for c in crit if c["status"] != "unknown"]
    conf = round(len(known) / len(crit), 2)
    met = sum(c["status"] == "met" for c in known)
    score = round(100 * met / len(known)) if known and conf >= MIN_CONFIDENCE else None
    ready = bool(sol.get("seeking_funding")) and score is not None and score >= 70 and all(
        c["status"] == "met" for c in crit if c["code"] in ("need", "ip"))
    return {"score": score, "confidence": conf, "ready": ready, "criteria": crit,
            "note": "Indicador de apoio calculado de dados cadastrados; não garante financiamento e não substitui a análise do financiador."}
