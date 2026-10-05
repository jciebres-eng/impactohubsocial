"""Adaptação sugerida de uma solução para outro território/orçamento. SEMPRE 'necessita validação' — heurística explicável, não estimativa
atuarial. Sem dados suficientes devolve a frase padrão em vez de inventar números."""
from __future__ import annotations

ENGINE_VERSION = "adaptation@1.0.0"
STATUS = "ADAPTAÇÃO SUGERIDA — NECESSITA VALIDAÇÃO"
INSUFFICIENT = "Dados insuficientes para estimativa confiável."
REGION = {**{u: "N" for u in "AC AP AM PA RO RR TO".split()}, **{u: "NE" for u in "AL BA CE MA PB PE PI RN SE".split()},
          **{u: "CO" for u in "DF GO MT MS".split()}, **{u: "SE" for u in "ES MG RJ SP".split()}, **{u: "S" for u in "PR RS SC".split()}}


def adapt(sol: dict, rp: dict | None, target: dict) -> dict:
    """target: {uf, city, population_size?, budget_cents?, months?, infra?: [..], partners?: [..], notes?}."""
    rp = rp or {}
    if not sol.get("allow_adaptation"):
        return {"status": "blocked", "engine_version": ENGINE_VERSION, "reason": "O autor não autorizou adaptação desta solução (licença/condições de uso).",
                "required_action": "Solicitar autorização ao autor."}
    changes, risks, steps, conditions = [], [], [], []
    src_uf, tgt_uf = sol.get("uf"), target.get("uf")
    known = 0
    if src_uf and tgt_uf:
        known += 1
        if src_uf == tgt_uf:
            conditions.append("Mesma UF de origem: menor necessidade de adaptação cultural/regulatória.")
        elif REGION.get(src_uf) == REGION.get(tgt_uf):
            changes.append("Revisar parceiros locais e calendário (mesma região, UF diferente).")
        else:
            changes.append("Revisar linguagem, parceiros e contexto cultural (região diferente).")
            risks.append("Contexto territorial distinto do de origem; resultados anteriores podem não se repetir.")
    ter = rp.get("territorial_dependency")
    if ter == "high" and src_uf != tgt_uf:
        risks.append("Autor declara forte dependência do território de origem.")
    # orçamento
    src_b, tgt_b = sol.get("budget_cents"), target.get("budget_cents")
    budget = None
    if src_b and tgt_b:
        known += 1
        ratio = tgt_b / src_b
        budget = {"original_cents": src_b, "available_cents": tgt_b, "ratio": round(ratio, 2)}
        if ratio >= 1:
            conditions.append("Orçamento disponível cobre o orçamento de referência.")
        elif ratio >= 0.5:
            changes.append(f"Reduzir escopo (~{round((1 - ratio) * 100)}% menos recursos): menos beneficiários ou menor frequência.")
            risks.append("Orçamento abaixo do de referência: dimensionar escopo antes de assumir resultados semelhantes.")
        else:
            changes.append("Orçamento muito abaixo do de referência: considerar piloto reduzido e fases.")
            risks.append("Orçamento inferior a 50% do de referência — replicação integral improvável.")
    # prazo
    src_m = (sol.get("schedule") or {}).get("months") if isinstance(sol.get("schedule"), dict) else None
    tgt_m = target.get("months")
    if src_m and tgt_m:
        known += 1
        if tgt_m < src_m:
            changes.append(f"Prazo menor que o de referência ({tgt_m} × {src_m} meses): priorizar etapas essenciais.")
            risks.append("Prazo curto pode comprometer a maturação dos resultados.")
    # infraestrutura / parceiros
    if rp.get("infra_dependency") in ("medium", "high"):
        have = set(target.get("infra") or [])
        if target.get("infra") is None:
            steps.append("Levantar a infraestrutura necessária (a solução depende dela) antes de iniciar.")
        elif not have:
            risks.append("Sem infraestrutura informada para uma solução que depende dela.")
        known += target.get("infra") is not None
    if rp.get("specialists_needed") in ("some", "many"):
        if not target.get("partners"):
            steps.append("Identificar especialistas/parceiros locais (a solução exige apoio técnico).")
        else:
            conditions.append("Parceiros locais informados.")
            known += 1
    for a in rp.get("adaptable") or []:
        conditions.append(f"Autor indica que pode ser adaptado: {a}.")
    if rp.get("documented") is False:
        risks.append("Metodologia não documentada: depende de contato direto com o autor.")
    steps += ["Validar a adaptação com a equipe local e, se possível, com o autor original.",
              "Executar piloto e medir indicadores antes de ampliar."]
    if sol.get("attribution_required"):
        conditions.append("Atribuição ao autor original é obrigatória.")
    if known < 2:
        return {"status": "insufficient_data", "label": STATUS, "message": INSUFFICIENT, "engine_version": ENGINE_VERSION,
                "needed": ["território (UF)", "orçamento disponível", "prazo"], "steps": steps[-2:], "conditions": conditions}
    return {"status": "suggested_needs_validation", "label": STATUS, "engine_version": ENGINE_VERSION, "recommended_changes": changes, "risks": risks,
            "conditions": conditions, "steps": steps, "budget": budget, "inputs_known": known,
            "disclaimer": "Heurística explicável baseada em dados cadastrados; não prevê resultados. Exige validação humana."}
