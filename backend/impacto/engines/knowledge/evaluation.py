"""Avaliação da busca da Central (help-search): métricas puras, sem I/O.

O conjunto de consultas vive em `config/search_eval.json` (versionado): cada consulta tem o tipo (exato, sinônimo, sigla, erro de
digitação, pergunta natural, ambígua, sem resposta), os itens RELEVANTES (slug de artigo/recurso ou `faq:<pergunta>`) e, quando houver,
os aceitáveis. Os números calculados aqui vão para `docs/evidence/search_eval_vX.json` — toda mudança de ranking é comparada ao baseline
gravado e nunca pode regredir em silêncio (tests/test_v0290_search_eval.py).
"""
from __future__ import annotations

import math


def item_key(item: dict) -> str:
    """Chave de julgamento: slug para artigo/recurso/curso, `faq:<pergunta>` para FAQ."""
    if item.get("type") == "faq":
        return "faq:" + (item.get("title") or "")
    return item.get("slug") or ""


def precision_at(ranked: list[str], relevant: set[str], k: int) -> float:
    top = ranked[:k]
    return (sum(1 for r in top if r in relevant) / k) if k else 0.0


def recall_at(ranked: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    return sum(1 for r in ranked[:k] if r in relevant) / len(relevant)


def reciprocal_rank(ranked: list[str], relevant: set[str]) -> float:
    for i, r in enumerate(ranked, 1):
        if r in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at(ranked: list[str], relevant: set[str], acceptable: set[str], k: int) -> float:
    """Ganho 2 para relevante, 1 para aceitável, 0 para o resto; nDCG binário/graduado padrão."""
    def gain(key: str) -> int:
        return 2 if key in relevant else (1 if key in acceptable else 0)
    dcg = sum(gain(r) / math.log2(i + 1) for i, r in enumerate(ranked[:k], 1))
    ideal = sorted([2] * len(relevant) + [1] * len(acceptable), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 1) for i, g in enumerate(ideal, 1))
    return dcg / idcg if idcg else 0.0


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
    return s[idx]


def summarize(results: list[dict], k: int = 5) -> dict:
    """`results`: [{query, kind, relevant, acceptable, ranked, latency_ms, abstained}] → métricas agregadas e por tipo."""
    answerable = [r for r in results if r["relevant"]]
    unanswerable = [r for r in results if not r["relevant"]]
    per_kind: dict[str, dict] = {}
    agg = {"queries": len(results), "answerable": len(answerable), "unanswerable": len(unanswerable), "k": k}
    if answerable:
        agg.update({
            f"precision_at_{k}": round(sum(precision_at(r["ranked"], set(r["relevant"]), k) for r in answerable) / len(answerable), 4),
            f"recall_at_{k}": round(sum(recall_at(r["ranked"], set(r["relevant"]), k) for r in answerable) / len(answerable), 4),
            "mrr": round(sum(reciprocal_rank(r["ranked"], set(r["relevant"])) for r in answerable) / len(answerable), 4),
            f"ndcg_at_{k}": round(sum(ndcg_at(r["ranked"], set(r["relevant"]), set(r.get("acceptable") or []), k) for r in answerable) / len(answerable), 4),
            "zero_result_rate": round(sum(1 for r in answerable if not r["ranked"]) / len(answerable), 4),
            "hit_at_1": round(sum(1 for r in answerable if r["ranked"][:1] and r["ranked"][0] in set(r["relevant"])) / len(answerable), 4),
        })
    if unanswerable:
        agg["correct_abstention_rate"] = round(sum(1 for r in unanswerable if r.get("abstained")) / len(unanswerable), 4)
        agg["unanswerable_with_results"] = sum(1 for r in unanswerable if r["ranked"])
    lat = [r["latency_ms"] for r in results if r.get("latency_ms") is not None]
    agg["latency_ms"] = {"p50": round(percentile(lat, 50), 1), "p95": round(percentile(lat, 95), 1), "n": len(lat)}
    for r in results:
        d = per_kind.setdefault(r["kind"], {"n": 0, "hit_at_1": 0, "zero": 0, "mrr": 0.0})
        d["n"] += 1
        if r["relevant"]:
            rel = set(r["relevant"])
            d["hit_at_1"] += 1 if (r["ranked"][:1] and r["ranked"][0] in rel) else 0
            d["zero"] += 1 if not r["ranked"] else 0
            d["mrr"] += reciprocal_rank(r["ranked"], rel)
    for d in per_kind.values():
        d["mrr"] = round(d["mrr"] / d["n"], 4) if d["n"] else 0.0
    agg["by_kind"] = per_kind
    return agg
