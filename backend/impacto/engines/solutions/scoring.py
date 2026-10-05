"""Pontuações explicáveis da biblioteca de soluções. Todas são determinísticas, usam apenas dados cadastrados e devolvem
``None`` (nunca um número inventado) quando não há dados suficientes. Pesos em config/solution_weights.json (HIPÓTESE a calibrar)."""
from __future__ import annotations

import json
import math
from pathlib import Path

W = json.loads((Path(__file__).resolve().parents[4] / "config" / "solution_weights.json").read_text(encoding="utf-8"))
SCORE_VERSIONS = {"maturity": "maturity@1.0", "replicability": "replicability@1.0", "evidence": "evidence@1.0", "relevance": "solution-relevance@1.0"}

STAGE_LABEL = {"idea": "IDEIA / NÃO VALIDADA", "proposal": "PROPOSTA", "developing": "EM DESENVOLVIMENTO", "running": "EM EXECUÇÃO",
               "completed": "REALIZADO", "archived": "ARQUIVADO"}
TRUST_LABEL = {"verified": "VERIFICADO", "evidenced": "EVIDENCIADO", "documented": "DOCUMENTADO", "self_declared": "AUTODECLARADO",
               "in_review": "EM REVISÃO", "unverified": "NÃO VERIFICADO"}
KIND_LABEL = {"project": "Projeto", "idea": "Ideia", "methodology": "Metodologia", "social_tech": "Tecnologia social", "academic": "Projeto acadêmico"}


# ------------------------------------------------------------------------------------------------ rótulo de verdade (§66)
def truth_labels(s: dict, replications_confirmed: int = 0, validated_results: int = 0) -> dict:
    """Ideia ≠ case; autodeclarado ≠ comprovado; replicado só com confirmação do autor; validado só com resultado validado + verificação."""
    stage, trust, kind = s["stage"], s["trust_level"], s["kind"]
    primary = STAGE_LABEL.get(stage, stage)
    flags = []
    if kind == "idea" or stage == "idea":
        primary = STAGE_LABEL["idea"]
        flags.append("não apresentar como projeto comprovado")
    proven = stage in ("running", "completed") and trust in ("evidenced", "verified")
    if proven:
        primary = "COMPROVADO" if stage == "completed" else "EM EXECUÇÃO (COMPROVADO)"
    if replications_confirmed > 0 and stage == "completed":
        primary = "REPLICADO"
    if trust == "verified" and validated_results > 0 and stage in ("running", "completed"):
        flags.append("VALIDADO")
    if stage in ("running", "completed") and not proven:
        flags.append("sem comprovação independente")
    return {"primary": primary, "trust": TRUST_LABEL.get(trust, trust), "kind": KIND_LABEL.get(kind, kind), "proven": proven, "flags": flags,
            "display_type": display_type(s)}


def display_type(s: dict) -> str:
    """Classificação de §5 para exibição: case realizado, em execução, pronto para financiamento, ideia, metodologia, tecnologia social, acadêmico."""
    if s["kind"] == "idea":
        return "idea"
    if s["kind"] in ("methodology", "social_tech", "academic"):
        return s["kind"]
    if s["stage"] == "completed":
        return "case"
    if s["stage"] == "running":
        return "running"
    if s.get("seeking_funding") and s["stage"] in ("proposal", "developing"):
        return "ready_to_fund"
    return "project"


# ------------------------------------------------------------------------------------------------ maturidade (completude estrutural)
def maturity(s: dict, ctx: dict) -> dict:
    """Completude estrutural do cadastro (não mede qualidade nem eficácia). ctx: results, evidence, people, replication_profile (contagens/bools)."""
    w = W["maturity"]
    has = {
        "problem": bool((s.get("problem") or "").strip()), "objectives": bool((s.get("objectives") or "").strip()),
        "approach": bool((s.get("approach") or "").strip()), "population": bool(s.get("population")),
        "territory": bool(s.get("uf")), "budget": s.get("budget_cents") is not None, "schedule": bool(s.get("schedule")),
        "goals": bool(s.get("goals")), "ods": bool(s.get("ods")), "esg": bool(s.get("esg")),
        "license": s.get("license") not in (None, "all_rights_reserved") or bool(s.get("usage_conditions")),
        "results": ctx.get("results", 0) > 0, "evidence": ctx.get("evidence", 0) > 0, "people": ctx.get("people", 0) > 0,
        "replication_profile": bool(ctx.get("replication_profile")),
    }
    total = sum(w.values())
    got = sum(w[k] for k, v in has.items() if v)
    labels = {"problem": "problema", "objectives": "objetivos", "approach": "solução/metodologia", "population": "população", "territory": "território", "budget": "orçamento",
              "schedule": "cronograma", "goals": "metas", "ods": "ODS", "esg": "ESG", "license": "licença/condições de uso", "results": "resultados/indicadores",
              "evidence": "evidências", "people": "autoria/equipe", "replication_profile": "perfil de replicação"}
    return {"score": round(100 * got / total), "version": SCORE_VERSIONS["maturity"], "basis": "completude do cadastro (não mede qualidade)",
            "missing": [labels[k] for k, v in has.items() if not v], "present": [labels[k] for k, v in has.items() if v]}


# ------------------------------------------------------------------------------------------------ evidência
def evidence(s: dict, ctx: dict) -> dict:
    """Score de evidência 0–100 ou None (sem nenhum dado). ctx: accepted_items, kinds_accepted, submitted_items, validated_results, reported_results,
    project_accepted_evidences (do projeto vinculado)."""
    w = W["evidence"]
    acc, kinds = ctx.get("accepted_items", 0), ctx.get("kinds_accepted", 0)
    vres, pacc = ctx.get("validated_results", 0), ctx.get("project_accepted_evidences", 0)
    trust = s.get("trust_level")
    has_any = acc or ctx.get("submitted_items", 0) or ctx.get("reported_results", 0) or vres or pacc or trust in ("documented", "evidenced", "verified")
    if not has_any:
        return {"score": None, "version": SCORE_VERSIONS["evidence"], "level": "none", "reasons": ["Nenhuma evidência, resultado ou verificação cadastrados."],
                "note": "Sem dados: o score não é calculado."}
    pts = (w["accepted_items"] * min(acc, 5) / 5 + w["kind_diversity"] * min(kinds, 3) / 3 + w["validated_results"] * min(vres, 3) / 3
           + w["trust"] * {"verified": 1.0, "evidenced": 0.6, "documented": 0.3}.get(trust, 0.0) + w["linked_project"] * min(pacc, 5) / 5)
    score = round(100 * pts / sum(w.values()))
    level = "high" if score >= 70 else "medium" if score >= 40 else "low"
    reasons = []
    if acc:
        reasons.append(f"{acc} evidência(s) aceita(s) pela revisão")
    if ctx.get("submitted_items", 0) - acc > 0:
        reasons.append(f"{ctx['submitted_items'] - acc} evidência(s) enviada(s) ainda sem aceite")
    if vres:
        reasons.append(f"{vres} resultado(s) validado(s)")
    if ctx.get("reported_results", 0) - vres > 0:
        reasons.append(f"{ctx['reported_results'] - vres} resultado(s) apenas reportado(s) pelo autor")
    if pacc:
        reasons.append(f"{pacc} evidência(s) aceita(s) no projeto vinculado")
    if trust in ("documented", "evidenced", "verified"):
        reasons.append(f"verificação: {TRUST_LABEL[trust].lower()}")
    return {"score": score, "version": SCORE_VERSIONS["evidence"], "level": level, "reasons": reasons}


# ------------------------------------------------------------------------------------------------ replicabilidade
_LEVEL = {"low": 1.0, "medium": 0.6, "high": 0.2}


def replicability(s: dict, rp: dict | None, evidence_score: int | None) -> dict:
    """Score 0–100 a partir de fatores DECLARADOS pelo autor + documentação + evidência. None se a confiança < mínimo."""
    w = W["replicability"]
    rp = rp or {}
    comps: list[tuple[str, float, float | None, str]] = []  # (chave, peso, valor 0–1|None, texto positivo/negativo)
    def add(key, val, good, bad):
        comps.append((key, w[key], val, good if (val or 0) >= 0.6 else bad))
    simp = rp.get("simplicity")
    add("simplicity", None if simp is None else (simp - 1) / 4, "Metodologia simples de executar", "Execução complexa")
    cost = rp.get("cost_level")
    add("cost", None if cost is None else {"low": 1.0, "moderate": 0.6, "high": 0.2}[cost], "Custo baixo/moderado", "Custo alto")
    inf = rp.get("infra_dependency")
    add("infra", None if inf is None else _LEVEL[inf], "Baixa dependência de infraestrutura", "Depende de infraestrutura específica")
    ter = rp.get("territorial_dependency")
    add("territorial", None if ter is None else _LEVEL[ter], "Baixa dependência territorial", "Forte dependência do território de origem")
    sp = rp.get("specialists_needed")
    add("specialists", None if sp is None else {"none": 1.0, "some": 0.6, "many": 0.2}[sp], "Pouca necessidade de especialistas", "Exige muitos especialistas")
    doc = rp.get("documented")
    add("documented", None if doc is None else (1.0 if doc else 0.0), "Metodologia documentada", "Metodologia sem documentação")
    tr = rp.get("training_available")
    add("training", None if tr is None else (1.0 if tr else 0.0), "Há capacidade de treinamento", "Sem treinamento disponível")
    add("evidence", None if evidence_score is None else evidence_score / 100, "Boa evidência histórica", "Evidência histórica fraca")
    ad = rp.get("adaptable")
    add("adaptability", None if ad is None else min(1.0, len(ad) / 5), "Adaptável em várias dimensões", "Pouca adaptabilidade declarada")
    total = sum(c[1] for c in comps)
    known = [c for c in comps if c[2] is not None]
    kw = sum(c[1] for c in known)
    conf = round(100 * kw / total, 1)
    score = round(100 * sum(c[1] * c[2] for c in known) / kw) if kw and conf >= w["min_confidence"] else None
    missing = [c[0] for c in comps if c[2] is None]
    out = {"score": score, "confidence": conf, "version": SCORE_VERSIONS["replicability"],
           "positives": [c[3] for c in known if c[2] >= 0.6], "negatives": [c[3] for c in known if c[2] < 0.6], "missing": missing,
           "basis": "fatores declarados pelo autor" + (" + evidência cadastrada" if evidence_score is not None else ""),
           "note": None if score is not None else "Dados insuficientes para estimar a replicabilidade."}
    if not s.get("allow_replication"):
        out["restriction"] = "O autor não autorizou replicação (licença/condições de uso)."
    return out


# ------------------------------------------------------------------------------------------------ relevância (busca)
def _budget_fit(sol_cents: int | None, b: dict) -> float | None:
    if sol_cents is None:
        return None
    lo, hi = b.get("min_cents"), b.get("max_cents")
    if b["kind"] == "have":
        # tenho X: o custo/necessidade deve caber; acima do orçamento decai (fator 3x = 0)
        if sol_cents <= hi:
            return 1.0
        return max(0.0, 1 - math.log(sol_cents / hi) / math.log(3))
    if lo is not None and hi is not None:
        if lo <= sol_cents <= hi:
            return 1.0
        edge = lo if sol_cents < lo else hi
        return max(0.0, 1 - abs(math.log(max(sol_cents, 1) / max(edge, 1))) / math.log(3))
    if hi is not None:
        return 1.0 if sol_cents <= hi else max(0.0, 1 - math.log(sol_cents / hi) / math.log(3))
    if lo is not None:
        return 1.0 if sol_cents >= lo else max(0.0, 1 - math.log(lo / max(sol_cents, 1)) / math.log(3))
    return None


def relevance(intent: dict, filters: dict, sol: dict, feats: dict) -> dict:
    """Combina sinais em 0–100 com pesos configuráveis. Só entram sinais APLICÁVEIS (pedidos na busca) e COM dados; renormaliza.
    feats: fts (0–1), concept_cov (0–1), trigram (0–1), concepts_in_sol (set), maturity (0–100), replicability (0–100|None), evidence (0–100|None).
    Avaliações, visualizações e plano NÃO entram (anti-manipulação)."""
    w = W["search_relevance"]
    parts = w["text_relevance_parts"]
    sig = []
    q_has_text = bool(intent["text_terms"] or intent["concepts"])
    if q_has_text:
        tr = parts["fts"] * feats["fts"] + parts["concepts"] * feats["concept_cov"] + parts["trigram"] * feats["trigram"]
        sig.append(("text_relevance", w["text_relevance"], min(1.0, tr),
                    f"texto {round(100 * feats['fts'])}% · conceitos {round(100 * feats['concept_cov'])}% · título {round(100 * feats['trigram'])}%"))
    q_ods = set(filters.get("ods") or intent["ods"])
    q_esg = set(filters.get("esg") or intent["esg"])
    if q_ods or q_esg:
        vals = []
        if q_ods:
            vals.append(len(q_ods & set(sol.get("ods") or [])) / len(q_ods))
        if q_esg:
            vals.append(len(q_esg & set(sol.get("esg") or [])) / len(q_esg))
        sig.append(("ods_esg", w["ods_esg"], sum(vals) / len(vals), "ODS/ESG pedidos × declarados"))
    q_pop = set(filters.get("population") or intent["population"])
    if q_pop:
        have = set(sol.get("population") or []) | feats["concepts_in_sol"]
        sig.append(("population", w["population"], len(q_pop & have) / len(q_pop), "população pedida × atendida"))
    terr = filters.get("ufs") or intent["territory"]["ufs"]
    if terr:
        uf = sol.get("uf")
        if not uf:
            sig.append(("territory", w["territory"], None, "território da solução não informado"))
        elif uf in terr:
            sig.append(("territory", w["territory"], 1.0, f"atua em {uf}"))
        else:
            sig.append(("territory", w["territory"], 0.15 if sol.get("allow_replication") else 0.0,
                        f"atua em {uf}; replicável para outros territórios" if sol.get("allow_replication") else f"atua em {uf}"))
    b = filters.get("budget") or intent["budget"]
    if b:
        cost = sol.get("needed_cents") if sol.get("seeking_funding") and sol.get("needed_cents") is not None else sol.get("budget_cents")
        sig.append(("budget", w["budget"], _budget_fit(cost, b), "orçamento da solução × faixa pedida" if cost is not None else "orçamento da solução não informado"))
    sig.append(("maturity", w["maturity"], feats["maturity"] / 100, "completude do cadastro"))
    sig.append(("replicability", w["replicability"], None if feats["replicability"] is None else feats["replicability"] / 100, "replicabilidade declarada"))
    sig.append(("evidence", w["evidence"], None if feats["evidence"] is None else feats["evidence"] / 100, "evidência cadastrada"))
    applicable = sum(x[1] for x in sig)
    known = [x for x in sig if x[2] is not None]
    kw = sum(x[1] for x in known)
    score = round(100 * sum(x[1] * x[2] for x in known) / kw, 1) if kw else None
    adj, adjustments = 0.0, []
    d = intent["desired"]
    stage, kind, trust = sol["stage"], sol["kind"], sol["trust_level"]
    if (d["proven"] or filters.get("proven")) and stage in ("running", "completed"):
        if trust in ("evidenced", "verified"):
            adj += w["business_rules"]["desired_match_bonus"]
            adjustments.append("+bônus: busca por solução comprovada e esta tem evidência verificada")
        else:
            adj -= w["business_rules"]["unproven_when_proof_wanted_penalty"]
            adjustments.append("−penalidade: busca por solução comprovada, mas esta é autodeclarada")
    elif d["proven"] and (kind == "idea" or stage in ("idea", "proposal")):
        adj -= w["business_rules"]["unproven_when_proof_wanted_penalty"]
        adjustments.append("−penalidade: busca por solução que já funcionou; esta ainda não foi executada")
    if d["ready_to_fund"] and sol.get("seeking_funding"):
        adj += w["business_rules"]["desired_match_bonus"]
        adjustments.append("+bônus: busca por projeto pronto para financiamento")
    if d["idea"] and kind == "idea":
        adj += w["business_rules"]["desired_match_bonus"]
        adjustments.append("+bônus: busca por ideias")
    if d["methodology"] and kind in ("methodology", "social_tech"):
        adj += w["business_rules"]["desired_match_bonus"]
        adjustments.append("+bônus: busca por metodologia/tecnologia social")
    if d["academic"] and kind == "academic":
        adj += w["business_rules"]["desired_match_bonus"]
        adjustments.append("+bônus: busca por conteúdo acadêmico")
    if score is not None:
        score = round(max(0.0, min(100.0, score + adj)), 1)
    return {"score": score, "confidence": round(100 * kw / applicable, 1) if applicable else None, "version": SCORE_VERSIONS["relevance"],
            "signals": [{"key": k, "weight": wt, "value": None if v is None else round(v, 3), "detail": d_} for k, wt, v, d_ in sig],
            "adjustments": adjustments}


def explain(sol: dict, rel: dict, intent: dict) -> list[str]:
    """'Por que apareceu para você' em linguagem direta, só com o que foi efetivamente calculado."""
    out = []
    for s in sorted([x for x in rel["signals"] if x["value"] is not None], key=lambda x: -x["weight"] * x["value"]):
        if s["value"] >= 0.6 and s["key"] not in ("maturity",):
            out.append(f"{ {'text_relevance':'Conteúdo relacionado à busca','ods_esg':'ODS/ESG compatíveis','population':'Mesma população','territory':'Território compatível','budget':'Orçamento dentro da faixa','replicability':'Alta replicabilidade declarada','evidence':'Evidência cadastrada'}.get(s['key'], s['key']) } ({s['detail']})")
    for c in intent["concepts"]:
        if c["how"] == "fuzzy":
            out.append(f"Interpretamos “{c['matched']}” como “{c['corrected_to']}”")
    out.extend(a for a in rel["adjustments"])
    return out[:6]
