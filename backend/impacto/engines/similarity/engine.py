"""Motor de originalidade, similaridade, complementaridade e integridade do financiamento (v0.28.0, ADR-350).

DETERMINÍSTICO E LOCAL. Nenhum texto sai da instalação: o motor fala de projetos de TERCEIROS (faixa de
risco 3 da política de IA), e mandar isso a um provedor externo exigiria base legal que a plataforma não
tem. A comparação é por dimensão, cada uma com score próprio, fatores, qualidade do dado e limitação:

    texto · escopo · público · território · tempo · orçamento · financiamento · indicadores

e as LEITURAS são separadas e nunca somadas num percentual único:

    SIMILARIDADE TEXTUAL ≠ SIMILARIDADE DE ESCOPO ≠ SOBREPOSIÇÃO TERRITORIAL ≠ DUPLICIDADE FINANCEIRA
    ≠ PLÁGIO ≠ FRAUDE.

O motor devolve INDÍCIOS com confiança e a necessidade de revisão humana; nunca conclui plágio, fraude ou
duplicidade. Nada aqui bloqueia financiamento, altera reputação, match ou ranking (teste de arquitetura).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from datetime import date

ENGINE_VERSION = "similarity@1.0"

STOPWORDS = set("""a o as os um uma uns umas de do da dos das em no na nos nas por para com sem sob sobre entre e ou que
se ao aos à às pelo pela pelos pelas este esta estes estas esse essa esses essas isso isto aquele aquela ser estar ter
haver como mais menos muito muitos muita muitas pouco poucos também já não sim seu sua seus suas nosso nossa nossos
nossas deste desta destes destas desse dessa nesse nessa neste nesta num numa dum duma até após antes depois quando
onde porque pois assim então cada todo toda todos todas outro outra outros outras mesmo mesma projeto projetos ação
ações atividade atividades realizar realização promover promoção através junto meio forma formas meta metas objetivo
objetivos público pessoas pessoa comunidade comunidades área áreas local locais município municípios região regiões
ano anos mês meses dia dias the of and""".split())

DIMENSIONS = ("text", "scope", "audience", "territory", "time", "budget", "funding", "indicators")
DIMENSION_LABEL = {
    "text": "Texto (título, resumo, problema)", "scope": "Escopo (objetivos, metodologia, causas, ODS)",
    "audience": "Público-alvo", "territory": "Território", "time": "Período", "budget": "Orçamento e itens de despesa",
    "funding": "Fontes de financiamento", "indicators": "Indicadores",
}


# ------------------------------------------------------------------------------------------------ texto
def normalize(text: str | None) -> str:
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9\s]", " ", t)


def tokens(text: str | None) -> list[str]:
    out = []
    for w in normalize(text).split():
        if len(w) < 3 or w in STOPWORDS or w.isdigit():
            continue
        # redução leve de plural/gênero: "escolas" ≈ "escola", "jovens" ≈ "jovem"
        if w.endswith("ns") and len(w) > 4:
            w = w[:-2] + "m"
        elif w.endswith("s") and len(w) > 4:
            w = w[:-1]
        out.append(w)
    return out


def shingles(text: str | None, n: int = 5) -> set[str]:
    ws = normalize(text).split()
    return {" ".join(ws[i:i + n]) for i in range(0, max(0, len(ws) - n + 1))}


def jaccard(a: set, b: set) -> float | None:
    """Nulo quando um dos lados não tem dado: ausência de informação não é dissimilaridade."""
    if not a or not b:
        return None
    return len(a & b) / len(a | b)


def cosine(a: list[str], b: list[str]) -> float | None:
    if not a or not b:
        return None
    fa: dict[str, int] = {}
    fb: dict[str, int] = {}
    for w in a:
        fa[w] = fa.get(w, 0) + 1
    for w in b:
        fb[w] = fb.get(w, 0) + 1
    dot = sum(fa[w] * fb.get(w, 0) for w in fa)
    na = math.sqrt(sum(v * v for v in fa.values()))
    nb = math.sqrt(sum(v * v for v in fb.values()))
    return dot / (na * nb) if na and nb else None


def r2(x: float | None) -> float | None:
    return None if x is None else round(float(x), 3)


# ------------------------------------------------------------------------------------------------ perfil do projeto
PROFILE_SQL = """
SELECT p.id::text AS id, p.org_id::text AS org_id, p.title, p.summary, p.problem, p.objectives, p.methodology,
       p.causes, p.ods, p.territory, p.beneficiaries_description, p.beneficiaries_count, p.starts_on, p.ends_on,
       p.budget_total_cents, p.indicators, p.status, p.visibility, p.updated_at, p.lat, p.lng,
       o.uf, o.city, o.legal_name AS org_name
  FROM projects p JOIN organizations o ON o.id = p.org_id WHERE p.id = $1
"""


def load_profile(conn, project_id: str) -> dict | None:
    """Lê o projeto SOB A RLS DO SOLICITANTE: o que ele não enxerga não entra. Nunca use contexto de sistema aqui."""
    p = conn.one(PROFILE_SQL, project_id)
    if not p:
        return None
    p = dict(p)
    p["budget_items"] = [dict(r) for r in conn.query(
        "SELECT description, category, total_cents FROM budget_items WHERE project_id = $1 ORDER BY created_at", project_id)]
    p["calls"] = [str(r["call_id"]) for r in conn.query("SELECT DISTINCT call_id FROM applications WHERE project_id = $1 AND call_id IS NOT NULL", project_id)]
    p["funders"] = sorted({str(r["org_id"]) for r in conn.query(
        "SELECT DISTINCT sp.org_id FROM signed_agreement_parties sp JOIN signed_agreements s ON s.id = sp.agreement_id"
        " WHERE s.project_id = $1 AND sp.role = 'funder'", project_id)}
        | {str(r["funder_org_id"]) for r in conn.query("SELECT DISTINCT funder_org_id FROM applications WHERE project_id = $1 AND funder_org_id IS NOT NULL", project_id)})
    inds = p.get("indicators") or []
    if isinstance(inds, str):
        try:
            inds = json.loads(inds)
        except ValueError:
            inds = []
    p["indicator_names"] = [str(i.get("name", "")) for i in inds if isinstance(i, dict)]
    return p


def profile_hash(p: dict) -> str:
    keys = ("id", "title", "summary", "problem", "objectives", "methodology", "causes", "ods", "territory", "beneficiaries_description",
            "beneficiaries_count", "starts_on", "ends_on", "budget_total_cents", "indicator_names", "budget_items", "calls", "funders", "uf", "city")
    return hashlib.sha256(json.dumps({k: p.get(k) for k in keys}, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


# ------------------------------------------------------------------------------------------------ dimensões
def _dim(score: float | None, factors: list[str], quality: str, limitation: str | None = None) -> dict:
    return {"score": r2(score), "factors": factors, "data_quality": quality, "limitation": limitation}


def dim_text(a: dict, b: dict) -> dict:
    ta = tokens(" ".join(str(a.get(k) or "") for k in ("title", "summary", "problem")))
    tb = tokens(" ".join(str(b.get(k) or "") for k in ("title", "summary", "problem")))
    cos = cosine(ta, tb)
    sa, sb = shingles(" ".join(str(a.get(k) or "") for k in ("summary", "problem", "objectives", "methodology"))), \
        shingles(" ".join(str(b.get(k) or "") for k in ("summary", "problem", "objectives", "methodology")))
    verb = jaccard(sa, sb)
    factors = []
    if cos is not None:
        factors.append(f"vocabulário em comum: cosseno {cos:.2f}" if cos >= 0.3 else f"vocabulário pouco coincidente: cosseno {cos:.2f}")
    if verb:
        factors.append(f"trechos de cinco palavras idênticos: {verb:.0%} dos trechos" + (" — INDÍCIO de reprodução textual; exige revisão humana" if verb >= 0.3 else ""))
    quality = "good" if len(ta) >= 30 and len(tb) >= 30 else ("poor" if min(len(ta), len(tb)) < 8 else "fair")
    out = _dim(cos, factors, quality, "textos curtos: a comparação de vocabulário tem pouca base" if quality == "poor" else None)
    out["verbatim_overlap"] = r2(verb)
    out["possible_textual_reproduction"] = bool(verb is not None and verb >= 0.3)
    return out


def dim_scope(a: dict, b: dict) -> dict:
    ja = jaccard(set(tokens(f"{a.get('objectives') or ''} {a.get('methodology') or ''}")), set(tokens(f"{b.get('objectives') or ''} {b.get('methodology') or ''}")))
    ca, cb = set(a.get("causes") or []), set(b.get("causes") or [])
    oa, ob = set(a.get("ods") or []), set(b.get("ods") or [])
    jc, jo = jaccard(ca, cb), jaccard(oa, ob)
    parts = [x for x in (ja, jc, jo) if x is not None]
    score = (sum(parts) / len(parts)) if parts else None
    factors = []
    if jc is not None:
        factors.append(f"causas em comum: {sorted(ca & cb) or 'nenhuma'}")
    if jo is not None:
        factors.append(f"ODS em comum: {sorted(oa & ob) or 'nenhum'}")
    if ja is not None:
        factors.append(f"objetivos e metodologia: {ja:.0%} de termos em comum")
    quality = "good" if ja is not None and jc is not None else ("poor" if not parts else "fair")
    return _dim(score, factors, quality, "faltam objetivos, metodologia ou causas em um dos projetos" if quality != "good" else None)


def dim_audience(a: dict, b: dict) -> dict:
    j = jaccard(set(tokens(a.get("beneficiaries_description"))), set(tokens(b.get("beneficiaries_description"))))
    factors = []
    if j is not None:
        factors.append(f"descrição do público: {j:.0%} de termos em comum")
    na, nb = a.get("beneficiaries_count"), b.get("beneficiaries_count")
    if na and nb:
        ratio = min(na, nb) / max(na, nb)
        factors.append(f"escala: {na} × {nb} beneficiários (razão {ratio:.2f})")
    return _dim(j, factors, "good" if j is not None else "poor", None if j is not None else "público-alvo não descrito em um dos projetos")


def _km(lat1, lng1, lat2, lng2) -> float:
    r = 6371.0
    p1, p2 = math.radians(float(lat1)), math.radians(float(lat2))
    dp, dl = p2 - p1, math.radians(float(lng2) - float(lng1))
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def dim_territory(a: dict, b: dict) -> dict:
    ta, tb = normalize(a.get("territory")).strip(), normalize(b.get("territory")).strip()
    factors = []
    score = None
    if ta and tb:
        if ta == tb:
            score = 1.0
            factors.append(f"mesmo território declarado: “{a.get('territory')}”")
        else:
            j = jaccard(set(ta.split()), set(tb.split())) or 0.0
            score = 0.6 * j
            factors.append(f"territórios diferentes com {j:.0%} de termos em comum")
    if a.get("lat") is not None and b.get("lat") is not None and a.get("lng") is not None and b.get("lng") is not None:
        km = _km(a["lat"], a["lng"], b["lat"], b["lng"])
        factors.append(f"distância entre os pontos declarados: {km:.0f} km")
        geo = max(0.0, 1 - km / 100)
        score = max(score or 0.0, geo)
    if (a.get("uf") or "") and (a.get("uf") == b.get("uf")):
        factors.append(f"organizações no mesmo estado ({a.get('uf')})")
        score = max(score or 0.0, 0.3)
    elif a.get("uf") and b.get("uf"):
        factors.append(f"organizações em estados diferentes ({a.get('uf')} × {b.get('uf')})")
    quality = "good" if (ta and tb) else ("fair" if (a.get("uf") and b.get("uf")) else "poor")
    return _dim(score, factors, quality, "território não declarado em um dos projetos" if not (ta and tb) else None)


def dim_time(a: dict, b: dict) -> dict:
    s1, e1, s2, e2 = a.get("starts_on"), a.get("ends_on"), b.get("starts_on"), b.get("ends_on")
    if not (s1 and e1 and s2 and e2):
        return _dim(None, [], "poor", "período não informado em um dos projetos")
    s1, e1, s2, e2 = (d if isinstance(d, date) else date.fromisoformat(str(d)) for d in (s1, e1, s2, e2))
    ov = (min(e1, e2) - max(s1, s2)).days
    span = (max(e1, e2) - min(s1, s2)).days or 1
    score = max(0.0, ov) / span
    return _dim(score, [f"sobreposição de {max(0, ov)} dias ({s1}–{e1} × {s2}–{e2})"], "good")


def dim_budget(a: dict, b: dict) -> dict:
    ia = {normalize(i["description"]).strip() for i in a.get("budget_items") or [] if i.get("description")}
    ib = {normalize(i["description"]).strip() for i in b.get("budget_items") or [] if i.get("description")}
    j = jaccard(ia, ib)
    factors = []
    shared = sorted(ia & ib)
    if j is not None:
        factors.append(f"itens de despesa idênticos: {len(shared)} ({', '.join(shared[:4])}{'…' if len(shared) > 4 else ''})" if shared else "nenhum item de despesa idêntico")
    ta, tb = a.get("budget_total_cents") or 0, b.get("budget_total_cents") or 0
    if ta and tb:
        ratio = min(ta, tb) / max(ta, tb)
        factors.append(f"totais: R$ {ta / 100:,.2f} × R$ {tb / 100:,.2f} (razão {ratio:.2f})")
    out = _dim(j, factors, "good" if (ia and ib) else "poor", "um dos projetos não tem itens de orçamento" if not (ia and ib) else None)
    out["shared_items"] = shared[:20]
    return out


def dim_funding(a: dict, b: dict) -> dict:
    ca, cb = set(a.get("calls") or []), set(b.get("calls") or [])
    fa, fb = set(a.get("funders") or []), set(b.get("funders") or [])
    j = jaccard(ca | {"f:" + f for f in fa}, cb | {"f:" + f for f in fb})
    factors = []
    if ca & cb:
        factors.append(f"candidatos ao(s) mesmo(s) edital(is): {len(ca & cb)}")
    if fa & fb:
        factors.append(f"financiador(es) em comum: {len(fa & fb)}")
    if j is not None and not (ca & cb or fa & fb):
        factors.append("sem edital nem financiador em comum")
    return _dim(j, factors, "good" if (ca or fa) and (cb or fb) else "poor",
                "um dos projetos não tem candidatura nem acordo registrado" if not ((ca or fa) and (cb or fb)) else None)


def dim_indicators(a: dict, b: dict) -> dict:
    ia = {" ".join(tokens(n)) for n in a.get("indicator_names") or [] if n}
    ib = {" ".join(tokens(n)) for n in b.get("indicator_names") or [] if n}
    j = jaccard(ia, ib)
    return _dim(j, [f"indicadores com o mesmo nome: {len(ia & ib)}"] if j is not None else [], "good" if (ia and ib) else "poor",
                "um dos projetos não declara indicadores" if not (ia and ib) else None)


def compare(a: dict, b: dict) -> dict:
    """Comparação de UM par, dimensão a dimensão, com as leituras separadas."""
    dims = {"text": dim_text(a, b), "scope": dim_scope(a, b), "audience": dim_audience(a, b), "territory": dim_territory(a, b),
            "time": dim_time(a, b), "budget": dim_budget(a, b), "funding": dim_funding(a, b), "indicators": dim_indicators(a, b)}
    known = [d for d in dims.values() if d["score"] is not None]
    good = sum(1 for d in dims.values() if d["data_quality"] == "good")
    confidence = "high" if good >= 6 else ("medium" if good >= 3 else "low")

    def sc(k):
        return dims[k]["score"] if dims[k]["score"] is not None else 0.0

    readings = {
        "textual_similarity": _level(sc("text")),
        "scope_similarity": _level(sc("scope")),
        "territorial_overlap": _level(sc("territory")),
        "temporal_overlap": _level(sc("time")),
        "possible_textual_reproduction": dims["text"].get("possible_textual_reproduction", False),
        # duplicidade de despesa: INDÍCIO só quando há itens iguais E mesmo território E períodos sobrepostos
        "possible_expense_duplication": bool(dims["budget"].get("shared_items") and sc("territory") >= 0.6 and sc("time") > 0.2),
        "same_funding_source": sc("funding") > 0,
        # complementaridade: mesmo escopo/causa com dado bom, SEM reprodução textual, e território, público ou
        # abordagem (texto) diferentes — colaboração em vez de concorrência
        "complementarity": bool(dims["scope"]["data_quality"] == "good" and sc("scope") >= 0.3
                                and not dims["text"].get("possible_textual_reproduction")
                                and (sc("territory") < 0.4 or sc("text") < 0.5 or sc("audience") < 0.5)),
    }
    recs = recommendations(readings, dims)
    return {"dimensions": dims, "readings": readings, "confidence": confidence,
            "dimensions_with_data": len(known),
            "human_review_required": True,
            "limitations": [d["limitation"] for d in dims.values() if d["limitation"]],
            "recommendations": recs,
            "disclaimer": ("Similaridade textual ≠ similaridade de escopo ≠ sobreposição territorial ≠ duplicidade financeira "
                           "≠ plágio ≠ fraude. Este resultado traz indícios por dimensão e NÃO prova plágio, fraude nem "
                           "duplicidade de financiamento; nenhuma decisão automática deriva dele.")}


def _level(x: float) -> str:
    return "high" if x >= 0.6 else ("medium" if x >= 0.3 else "low")


def recommendations(readings: dict, dims: dict) -> list[dict]:
    out = []
    if readings["possible_textual_reproduction"]:
        out.append({"action": "request_human_review", "label": "Solicitar revisão humana do indício de reprodução textual",
                    "why": "trechos idênticos de cinco palavras acima do limiar; pode ser modelo comum, autoria compartilhada ou cópia"})
        out.append({"action": "contest_or_correct", "label": "Contestar ou corrigir informações", "why": "quem é comparado pode explicar a origem do texto"})
    if readings["textual_similarity"] == "high" or readings["scope_similarity"] == "high":
        out.append({"action": "differentiate", "label": "Diferenciar a proposta", "why": "escopo e texto muito próximos de outro projeto visível"})
        out.append({"action": "show_additionality", "label": "Demonstrar adicionalidade", "why": "o que este projeto entrega que o semelhante não entrega"})
        out.append({"action": "consult_reference", "label": "Consultar o projeto de referência", "why": "aprender com o que já existe é legítimo"})
    if readings["complementarity"]:
        out.append({"action": "propose_partnership", "label": "Propor parceria ou consórcio", "why": "mesma causa com território ou abordagem diferentes"})
        out.append({"action": "share_infrastructure", "label": "Compartilhar infraestrutura ou dividir responsabilidades", "why": "evita duplicação evitável sem penalizar projetos legítimos"})
    if readings["territorial_overlap"] == "high" and readings["scope_similarity"] != "low":
        out.append({"action": "justify_territory", "label": "Justificar diferenças territoriais", "why": "mesmo território e escopo próximo: explicar a divisão de públicos ou atividades"})
    if readings["possible_expense_duplication"]:
        out.append({"action": "investigate_expense_overlap", "label": "Investigar possível sobreposição de despesa", "why": "itens iguais, mesmo território e períodos sobrepostos — indício, não conclusão"})
        out.append({"action": "adjust_budget", "label": "Ajustar orçamento", "why": "se a despesa já é coberta por outra fonte"})
    if readings["same_funding_source"]:
        out.append({"action": "declare_sources", "label": "Declarar as fontes múltiplas de financiamento", "why": "transparência evita que financiamento por fontes múltiplas pareça duplicidade"})
    if dims["scope"]["data_quality"] != "good":
        out.append({"action": "improve_methodology", "label": "Aprimorar objetivos e metodologia", "why": "dados incompletos reduzem a confiança de qualquer comparação"})
    if not out:
        out.append({"action": "none", "label": "Nenhuma ação necessária", "why": "sem similaridade relevante nas dimensões com dado"})
    return out


# ------------------------------------------------------------------------------------------------ originalidade (um contra conjunto)
def originality(subject: dict, candidates: list[dict], max_results: int = 10) -> dict:
    pairs = []
    for c in candidates:
        r = compare(subject, c)
        top = max((d["score"] or 0.0) for d in r["dimensions"].values())
        pairs.append({"project_id": c["id"], "title": c["title"], "org_name": c.get("org_name"), "visibility": c.get("visibility"),
                      "top_dimension_score": r2(top), "comparison": r})
    pairs.sort(key=lambda x: -(x["top_dimension_score"] or 0))
    shown = pairs[:max_results]
    # o que o projeto traz de novo: termos do escopo que nenhum candidato próximo usa
    mine = set(tokens(f"{subject.get('objectives') or ''} {subject.get('methodology') or ''} {subject.get('summary') or ''}"))
    theirs: set[str] = set()
    for p in shown[:5]:
        c = next(x for x in candidates if x["id"] == p["project_id"])
        theirs |= set(tokens(f"{c.get('objectives') or ''} {c.get('methodology') or ''} {c.get('summary') or ''}"))
    novel = sorted(mine - theirs)[:25]
    high = [p for p in shown if (p["top_dimension_score"] or 0) >= 0.6]
    return {"candidates_compared": len(candidates), "shown": shown,
            "novel_terms": novel,
            "originality_reading": ("no_close_match" if not high else ("close_matches_exist" if len(high) <= 2 else "crowded_space")),
            "originality_note": {
                "no_close_match": "Nenhum projeto visível se aproxima em dimensão alguma: o que você traz de novo está nos termos listados.",
                "close_matches_exist": "Existem projetos próximos em pelo menos uma dimensão. Veja as recomendações de cada par.",
                "crowded_space": "Muitos projetos próximos: diferencie a proposta, demonstre adicionalidade ou proponha complementaridade.",
            },
            "complementarity_candidates": [p["project_id"] for p in shown if p["comparison"]["readings"]["complementarity"]][:10],
            "human_review_required": True}
