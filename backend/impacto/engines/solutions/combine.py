"""Combinação de 2–4 soluções: complementaridade, sobreposição, conflitos e dependências. Resultado é SUGESTÃO que exige revisão humana."""
from __future__ import annotations

ENGINE_VERSION = "combine@1.0.0"


def _set(x):
    return set(x or [])


def combine(sols: list[dict]) -> dict:
    n = len(sols)
    if not 2 <= n <= 4:
        raise ValueError("combine requires 2-4 solutions")
    themes = [_set(s.get("themes")) for s in sols]
    pops = [_set(s.get("population")) for s in sols]
    ods = [_set(s.get("ods")) for s in sols]
    allt, allp, allo = set().union(*themes), set().union(*pops), set().union(*ods)
    shared_t = set.intersection(*themes) if themes else set()
    shared_p = set.intersection(*pops) if pops else set()
    complementary, overlaps, conflicts, deps, opps, notes = [], [], [], [], [], []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = sols[i], sols[j]
            jt = len(themes[i] & themes[j]) / max(1, len(themes[i] | themes[j]))
            jp = len(pops[i] & pops[j]) / max(1, len(pops[i] | pops[j]))
            pair = {"a": a["id"], "b": b["id"], "titles": [a["title"], b["title"]]}
            if jt > 0.7 and jp > 0.7 and a["kind"] == b["kind"]:
                overlaps.append({**pair, "reason": "Temas e população quase idênticos: possível duplicidade/sobreposição."})
            elif themes[i] != themes[j] and (pops[i] & pops[j]):
                complementary.append({**pair, "reason": "Mesma população, temas distintos: atuações complementares."})
            elif themes[i] & themes[j] and not (pops[i] & pops[j]) and pops[i] and pops[j]:
                complementary.append({**pair, "reason": "Mesmo tema, populações diferentes: pode ampliar o alcance."})
            if a["kind"] != b["kind"] and {a["kind"], b["kind"]} & {"methodology", "social_tech"}:
                complementary.append({**pair, "reason": "Metodologia/tecnologia + projeto: a metodologia pode instrumentar a execução."})
            if a.get("uf") and b.get("uf") and a["uf"] != b["uf"]:
                notes.append(f"“{a['title']}” ({a['uf']}) e “{b['title']}” ({b['uf']}) atuam em UFs diferentes: definir território de aplicação.")
            if a.get("budget_cents") and b.get("budget_cents") and max(a["budget_cents"], b["budget_cents"]) > 5 * min(a["budget_cents"], b["budget_cents"]):
                conflicts.append({**pair, "reason": "Escalas de orçamento muito distintas (>5×): integração exige redimensionamento."})
            for x, _y in ((a, b), (b, a)):
                if not x.get("allow_adaptation") or not x.get("allow_replication"):
                    conflicts.append({"a": x["id"], "titles": [x["title"]], "reason": "Licença/condições do autor restringem adaptação ou replicação: pedir autorização antes de combinar."})
                    break
    for s in sols:
        if s["stage"] in ("idea", "proposal"):
            deps.append({"id": s["id"], "title": s["title"], "reason": "Ainda não executada: depende de validação antes de compor um piloto."})
        if s["trust_level"] in ("unverified", "self_declared", "in_review"):
            notes.append(f"“{s['title']}” não tem verificação independente.")
    if len(allt) > max(len(t) for t in themes):
        opps.append(f"A combinação cobre {len(allt)} temas e {len(allp)} populações (isolada, cada uma cobre no máximo {max(len(t) for t in themes)} temas).")
    if len(allo) > max((len(o) for o in ods), default=0):
        opps.append(f"Cobre {len(allo)} ODS no conjunto.")
    # dedupe conflitos de licença por id
    seen, uniq = set(), []
    for c in conflicts:
        k = (c.get("a"), c.get("b"), c["reason"])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return {"engine_version": ENGINE_VERSION, "count": n, "complementary": complementary, "overlaps": overlaps, "conflicts": uniq, "dependencies": deps,
            "opportunities": opps, "notes": notes, "shared_themes": sorted(shared_t), "shared_population": sorted(shared_p),
            "union": {"themes": sorted(allt), "population": sorted(allp), "ods": sorted(allo)},
            "status": "SUGESTÃO — NECESSITA REVISÃO HUMANA", "disclaimer": "Combinação sugerida a partir de dados cadastrados; não garante compatibilidade operacional."}
