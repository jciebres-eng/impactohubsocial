"""Intent parser determinístico (intent-parser@1.0.0): consulta livre → atributos estruturados.

Pipeline: normalização → conceitos (tesauro, com correção de erros de digitação) → territórios → orçamento → prazo → status desejados → tipo de intenção.
Nada aqui chama LLM, e não existe refinador por IA: uma versão anterior deste comentário citava
`services/solutions.refine_with_ai`, função que nunca foi escrita. Referência órfã em comentário
vira prova documental falsa quando alguém a lê como implementada — por isso o registro de motores
(`engines/registry.py`) declara os três únicos pontos que chamam modelo, e há teste conferindo.
"""
from __future__ import annotations

import re

from .concepts import detect, expand, load, norm, tokens

PARSER_VERSION = "intent-parser@1.0.0"

_MULT = {"mil": 1_000, "k": 1_000, "milhao": 1_000_000, "milhoes": 1_000_000, "mi": 1_000_000}
_NUM = r"(\d{1,3}(?:\.\d{3})+|\d+(?:[.,]\d+)?)"


def _to_number(s: str) -> float:
    s = s.strip()
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        return float(s.replace(".", ""))
    return float(s.replace(",", "."))


def parse_budget(text: str) -> dict | None:
    """Aceita: 'R$ 250 mil', 'até 50 mil', 'entre 50 e 100 mil', 'tenho 100k', '10-50 mil', '500 mil+'. Retorna centavos."""
    t = norm(text.replace("R$", " ").replace("r$", " ")).replace(" mil", "mil").replace(" milhao", "milhao").replace(" milhoes", "milhoes")
    t = re.sub(r"(\d)\s*k\b", r"\1k", t)

    def val(num: str, mult: str | None) -> int:
        return int(round(_to_number(num) * _MULT.get(mult or "", 1) * 100))
    m = re.search(r"(?:entre|de)\s+" + _NUM + r"\s*(mil|k|milhao|milhoes)?\s*(?:e|a|ate)\s+" + _NUM + r"\s*(mil|k|milhao|milhoes)?", t)
    if m:
        hi_mult = m.group(4) or m.group(2)
        lo_mult = m.group(2) or m.group(4)
        lo, hi = val(m.group(1), lo_mult), val(m.group(3), hi_mult)
        return {"min_cents": min(lo, hi), "max_cents": max(lo, hi), "kind": "range"}
    m = re.search(_NUM + r"\s*(mil|k|milhao|milhoes)?\s*-\s*" + _NUM + r"\s*(mil|k|milhao|milhoes)?", t)
    if m:
        hi_mult = m.group(4) or m.group(2)
        lo, hi = val(m.group(1), m.group(2) or hi_mult), val(m.group(3), hi_mult)
        return {"min_cents": min(lo, hi), "max_cents": max(lo, hi), "kind": "range"}
    m = re.search(r"(?:ate|maximo de|no maximo)\s+" + _NUM + r"\s*(mil|k|milhao|milhoes)?", t)
    if m:
        return {"min_cents": None, "max_cents": val(m.group(1), m.group(2)), "kind": "up_to"}
    m = re.search(_NUM + r"\s*(mil|k|milhao|milhoes)?\s*\+", t)
    if m:
        return {"min_cents": val(m.group(1), m.group(2)), "max_cents": None, "kind": "from"}
    m = re.search(r"(?:tenho|dispon\w+|orcamento de|investir|investimento de|com)\s+(?:de\s+)?" + _NUM + r"\s*(mil|k|milhao|milhoes)", t) \
        or re.search(r"\b" + _NUM + r"\s*(mil|k|milhao|milhoes)\b", t)
    if m:
        v = val(m.group(1), m.group(2))
        return {"min_cents": None, "max_cents": v, "target_cents": v, "kind": "have"}
    return None


def parse_months(text: str) -> int | None:
    t = norm(text)
    m = re.search(r"(\d{1,3})\s*(meses|mes)\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d{1,2})\s*(anos|ano)\b", t)
    if m:
        return int(m.group(1)) * 12
    return None


_PHRASES = {
    "proven": ["ja funcionou", "ja funciona", "comprovado", "comprovada", "com evidencia", "que funciona", "case", "cases", "realizado", "testado"],
    "ready_to_fund": ["pronto para financ", "pronto para financiamento", "captacao", "buscando financiamento", "financiavel", "para financiar", "quero financiar", "investir"],
    "idea": ["ideia", "ideias", "conceito", "ainda nao executad"],
    "replicable": ["replicar", "replicavel", "replicaveis", "replicacao", "reaplicar"],
    "adapt": ["adaptar", "adaptacao", "adaptavel"],
    "methodology": ["metodologia", "metodologias", "tecnologia social", "tecnologias sociais"],
    "academic": ["academico", "pesquisa", "pesquisador", "universidade", "tese"],
    "running": ["em execucao", "em andamento", "funcionando"],
}


def _has(n: str, phrases: list[str]) -> bool:
    return any((" " + p) in (" " + n) for p in phrases)


def parse_territory(text: str) -> dict:
    cfg = load()
    n = " " + norm(text) + " "
    ufs, regions, city, notes = [], [], None, []
    for name, uf in sorted(cfg["ufs"].items(), key=lambda kv: -len(kv[0])):
        if name == "para" and not re.search(r"Par[áa]\b(?<!para)|estado do par", text):   # "para" (preposição) × Pará (UF): exige a grafia com acento
            continue
        if name == "para" and "Pará" not in text and "estado do pará" not in text.lower():
            continue
        if f" {name} " in n and uf not in ufs:
            ufs.append(uf)
            n = n.replace(f" {name} ", " ")
    for name, uf in cfg["capitals"].items():
        if f" {name} " in n:
            city = name
            if uf not in ufs:
                ufs.append(uf)
            if re.search(r"\b(proxim\w+|perto)\b", n):
                notes.append("Proximidade geográfica não é calculada (sem base de municípios): considerando o estado inteiro.")
    for r, r_ufs in cfg["regions"].items():
        if f" {r} " in n:
            regions.append(r)
            for u in r_ufs:
                if u not in ufs:
                    ufs.append(u)
    for tok in re.findall(r"\b[A-Z]{2}\b", text):
        if tok in cfg["ufs"].values() and tok not in ufs:
            ufs.append(tok)
    return {"ufs": ufs, "regions": regions, "city": city, "notes": notes}


def parse(query: str) -> dict:
    cfg = load()
    q = (query or "").strip()[:500]
    n = norm(q)
    found = detect(q)
    ids = [f["id"] for f in found]
    weights = expand(ids)
    concepts = cfg["concepts"]
    populations = [i for i in weights if concepts[i]["dim"] == "population"]
    institutions = [i for i in weights if concepts[i]["dim"] == "institution"]
    themes_c = [i for i in weights if concepts[i]["dim"] == "theme"]
    modality = [i for i in ids if concepts[i]["dim"] == "modality"]
    cause_keys, ods, esg = [], [], []
    for i in weights:
        for t in concepts[i]["themes"]:
            if t not in cause_keys:
                cause_keys.append(t)
        for o in concepts[i]["ods"]:
            if o not in ods and weights[i] >= 1.0:
                ods.append(o)
        for e in concepts[i]["esg"]:
            if e not in esg:
                esg.append(e)
    for m in re.finditer(r"\bods\s*(\d{1,2})\b", n):
        v = int(m.group(1))
        if 1 <= v <= 17 and v not in ods:
            ods.insert(0, v)
    explicit_ods = [int(m.group(1)) for m in re.finditer(r"\bods\s*(\d{1,2})\b", n) if 1 <= int(m.group(1)) <= 17]
    for w, d in (("ambiental", "E"), ("social", "S"), ("governanca", "G")):
        if re.search(rf"\besg\b.*\b{w}\b|\b{w}\b.*\besg\b", n) and d not in esg:
            esg.append(d)
    terr = parse_territory(q)
    budget = parse_budget(q)
    months = parse_months(q)
    desired = {"proven": _has(n, _PHRASES["proven"]), "ready_to_fund": _has(n, _PHRASES["ready_to_fund"]), "idea": _has(n, _PHRASES["idea"]),
               "replicable": _has(n, _PHRASES["replicable"]), "adapt": _has(n, _PHRASES["adapt"]), "running": _has(n, _PHRASES["running"]),
               "methodology": _has(n, _PHRASES["methodology"]), "academic": _has(n, _PHRASES["academic"])}
    # tipo de intenção principal
    if desired["idea"]:
        intent = "explore_idea"
    elif re.search(r"\b(tenho|dispon\w+)\b.*\b(mil|milhao|milhoes|investir|recursos?)\b", n) or "investir" in n:
        intent = "invest"
    elif desired["replicable"]:
        intent = "replicate"
    elif desired["adapt"]:
        intent = "adapt"
    elif re.search(r"\b(evasao|violencia|problema|dificuldade|falta de)\b", n):
        intent = "solve_problem"
    else:
        intent = "find_solution"
    consumed = set()
    for f in found:
        consumed.update(tokens(f.get("matched", "")))
    text_tokens = tokens(q)
    unmatched = [t for t in text_tokens if t not in consumed and not t.isdigit() and t not in {"mil", "k", "meses", "mes", "ano", "anos", "r"}
                 and t not in {x for names in [norm(k) for k in cfg["ufs"]] for x in names.split()} and t not in {"ods", "esg"}]
    return {
        "parser_version": PARSER_VERSION, "query": q,
        "concepts": found, "concept_weights": weights,
        "population": populations, "institutions": institutions, "theme_concepts": themes_c, "modality": modality,
        "themes": cause_keys, "ods": ods, "explicit_ods": explicit_ods, "esg": esg,
        "territory": {"ufs": terr["ufs"], "regions": terr["regions"], "city": terr["city"]}, "territory_notes": terr["notes"],
        "budget": budget, "months": months, "desired": desired, "intent": intent,
        "text_terms": text_tokens, "unmatched_terms": unmatched,
        "corrections": [{"from": f["matched"], "to": f["corrected_to"]} for f in found if f["how"] == "fuzzy"],
    }
