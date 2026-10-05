"""Motor de busca da Central de Conhecimento (help-search@1.0.0): puro e determinístico (sem I/O além de carregar o vocabulário).

Busca HÍBRIDA e explicável: texto (FTS pt_unaccent) + similaridade de título (trigramas) + camada SEMÂNTICA por vocabulário de tópicos
(sinônimos/frases de operação da plataforma — `config/help_synonyms.json`; NÃO há embeddings) + perfil (tipo de organização) + contexto
da tela (ctx_key) + categorias. Cada resultado traz os motivos. Plano/assinatura nunca influencia o resultado (ADR-007/042)."""
from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from ..solutions.concepts import norm

ENGINE_VERSION = "help-search@1.0.0"
_CFG = Path(__file__).resolve().parents[4] / "config" / "help_synonyms.json"
# pesos (HIPÓTESE inicial, ajustáveis; não calibrados com uso real)
WEIGHTS = {"fts": 0.40, "title": 0.20, "topic": 0.25, "ctx": 0.10, "audience": 0.05}
KIND_BONUS = {"guide": 0.04, "procedure": 0.04, "start": 0.03, "faq": 0.02}
MIN_SCORE = 0.18          # abaixo disso o resultado não é exibido (evita "achar" qualquer coisa)
ANSWER_MIN = 0.30         # abaixo disso o assistente declara que não encontrou base suficiente


@lru_cache(maxsize=1)
def load() -> dict:
    doc = json.loads(_CFG.read_text(encoding="utf-8"))
    idx: dict[str, list[str]] = {}
    for tid, t in doc["topics"].items():
        for term in t["terms"]:
            idx.setdefault(norm(term), []).append(tid)
    doc["_idx"] = idx
    doc["_stop"] = {norm(w) for w in doc["stopwords"]}
    return doc


def q_hash(text: str) -> str:
    """Hash curto da consulta normalizada (ADR-043: o log guarda hash + tópicos, nunca o texto digitado)."""
    return hashlib.sha256(norm(text).encode()).hexdigest()[:16]


def tokens(text: str) -> list[str]:
    stop = load()["_stop"]
    return [w for w in norm(text).split() if w not in stop and len(w) > 1]


def topics_in(text: str) -> list[str]:
    """Tópicos presentes no texto (frases longas primeiro; ignora sobreposição)."""
    cfg = load()
    n = " " + norm(text) + " "
    found: list[str] = []
    covered: list[tuple[int, int]] = []
    for term in sorted(cfg["_idx"], key=lambda t: (-len(t), t)):
        for m in re.finditer(r"(?<= )" + re.escape(term) + r"(?= )", n):
            s, e = m.span()
            if any(s < ce and e > cs for cs, ce in covered):
                continue
            covered.append((s, e))
            for tid in cfg["_idx"][term]:
                if tid not in found:
                    found.append(tid)
    return found


def parse(query: str) -> dict:
    """Consulta livre → termos, tópicos e consulta tsquery (OU entre termos; frases ligadas por <->)."""
    q = (query or "").strip()[:300]
    toks = tokens(q)
    tps = topics_in(q)
    cfg = load()
    terms: list[str] = list(dict.fromkeys(toks))
    for tid in tps:                       # expansão semântica: só frases do próprio tópico detectado (1 nível)
        for t in cfg["topics"][tid]["terms"][:6]:
            nt = norm(t)
            if nt and nt not in terms and len(nt) >= 3:
                terms.append(nt)
    parts = []
    for t in terms[:30]:
        t = re.sub(r"[^a-z0-9 ]", "", t).strip()
        if len(t) < 2:
            continue
        parts.append("(" + " <-> ".join(t.split()) + ")")
    return {"q": q, "norm": norm(q), "tokens": toks, "topics": tps, "topic_labels": [cfg["topics"][t]["label"] for t in tps],
            "tsquery": " | ".join(parts), "engine": ENGINE_VERSION}


def topic_overlap(item_text: str, tags: list[str], topics: list[str]) -> float:
    """Fração dos tópicos da consulta que aparecem no item (tags ou texto). 0–1."""
    if not topics:
        return 0.0
    cfg = load()
    body = " " + norm(item_text) + " " + " ".join(norm(t) for t in tags) + " "
    hit = 0
    for tid in topics:
        if tid in tags or any(" " + norm(term) + " " in body for term in cfg["topics"][tid]["terms"]):
            hit += 1
    return hit / len(topics)


def score(parsed: dict, *, fts: float, title_sim: float, kind: str, item_text: str, tags: list[str], ctx_keys: list[str],
          ctx_key: str | None, audience: list[str], user_kind: str | None) -> dict:
    topic = topic_overlap(item_text, tags, parsed["topics"])
    f = min(1.0, fts * 3.5)
    ctx = 1.0 if ctx_key and ctx_key in ctx_keys else 0.0
    aud = 1.0 if (user_kind and (not audience or user_kind in audience)) else 0.0
    s = (WEIGHTS["fts"] * f + WEIGHTS["title"] * min(1.0, title_sim) + WEIGHTS["topic"] * topic + WEIGHTS["ctx"] * ctx
         + WEIGHTS["audience"] * aud + KIND_BONUS.get(kind, 0.0))
    why = []
    if f > 0.15:
        why.append("termos da consulta no conteúdo")
    if title_sim >= 0.45:
        why.append("título parecido com a consulta")
    if topic > 0:
        why.append("mesmo assunto: " + ", ".join(load()["topics"][t]["label"] for t in parsed["topics"][:3]))
    if ctx:
        why.append("relacionado à tela em que você está")
    if aud and audience and user_kind in audience:
        why.append("indicado para o seu perfil")
    return {"score": round(min(1.0, s), 3), "why": why, "signals": {"fts": round(f, 3), "title": round(min(1.0, title_sim), 3),
                                                                         "topic": round(topic, 3), "ctx": ctx, "audience": aud}}
