"""Tesauro de conceitos (config/solution_concepts.json): normalização, detecção e expansão. Puro, sem I/O além do carregamento."""
from __future__ import annotations

import json
import re
import unicodedata
from difflib import get_close_matches
from functools import lru_cache
from pathlib import Path

_CFG = Path(__file__).resolve().parents[4] / "config" / "solution_concepts.json"


def norm(text: str | None) -> str:
    """minúsculas, sem acentos, só [a-z0-9 ] — mesma normalização usada em consultas e termos do tesauro."""
    t = unicodedata.normalize("NFKD", (text or "").lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", t)).strip()


@lru_cache(maxsize=1)
def load() -> dict:
    doc = json.loads(_CFG.read_text(encoding="utf-8"))
    term_index: dict[str, list[str]] = {}
    for cid, c in doc["concepts"].items():
        for t in c["terms"]:
            term_index.setdefault(norm(t), []).append(cid)
    doc["_term_index"] = term_index
    doc["_vocab"] = sorted(t for t in term_index if len(t) >= 4 and " " not in t)
    doc["_stop"] = set(doc["stopwords"])
    return doc


def detect(text: str, *, fuzzy: bool = True) -> list[dict]:
    """Conceitos presentes no texto. Longest-match primeiro (frases antes de palavras); fuzzy só em palavras isoladas ≥ 5 letras."""
    cfg = load()
    n = " " + norm(text) + " "
    found: dict[str, dict] = {}
    covered: list[tuple[int, int]] = []
    terms = sorted(cfg["_term_index"], key=lambda t: (-len(t), t))
    for term in terms:
        for m in re.finditer(r"(?<= )" + re.escape(term) + r"(?= )", n):
            s, e = m.span()
            if any(s < ce and e > cs for cs, ce in covered):
                continue
            covered.append((s, e))
            for cid in cfg["_term_index"][term]:
                found.setdefault(cid, {"id": cid, "how": "exact", "matched": term})
    if fuzzy:
        rest = [w for w in n.split() if len(w) >= 4 and w not in cfg["_stop"]]
        for w in rest:
            if w in cfg["_term_index"]:
                continue
            close = get_close_matches(w, cfg["_vocab"], n=1, cutoff=0.85)
            if close:
                for cid in cfg["_term_index"][close[0]]:
                    found.setdefault(cid, {"id": cid, "how": "fuzzy", "matched": w, "corrected_to": close[0]})
    out = []
    for cid, info in found.items():
        c = cfg["concepts"][cid]
        out.append({**info, "label": c["label"], "dim": c["dim"]})
    return sorted(out, key=lambda x: x["id"])


def expand(concept_ids: list[str]) -> dict[str, float]:
    """Conceitos diretos (peso 1.0) + expansões de 1 nível (peso 0.5)."""
    cfg = load()["concepts"]
    out: dict[str, float] = {}
    for cid in concept_ids:
        out[cid] = 1.0
    for cid in concept_ids:
        for e in cfg.get(cid, {}).get("expands", []):
            out.setdefault(e, 0.5)
    return out


def concept_terms(cid: str) -> list[str]:
    return [norm(t) for t in load()["concepts"][cid]["terms"]]


def tokens(text: str) -> list[str]:
    stop = load()["_stop"]
    return [w for w in norm(text).split() if w not in stop and len(w) > 1]
