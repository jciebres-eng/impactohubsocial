"""Compras: benchmark de cotações (estatística descritiva) e verificação da política da OSC.

Linguagem: o benchmark sinaliza "preço possivelmente fora do padrão das cotações" — nunca "fraude". A decisão é humana.
"""
from __future__ import annotations

import statistics

from ..db.pq import Connection


def benchmark(amounts: list[int], outlier_pct: float) -> dict:
    """Mediana como referência (robusta a extremos). Outlier = desvio relativo à mediana acima do limite da política."""
    n = len(amounts)
    if n == 0:
        return {"count": 0, "quotes": []}
    med = statistics.median(amounts)
    out = {"count": n, "mean_cents": round(statistics.fmean(amounts)), "median_cents": round(med), "min_cents": min(amounts),
           "max_cents": max(amounts), "stdev_cents": round(statistics.pstdev(amounts)) if n > 1 else 0, "outlier_pct_limit": outlier_pct}
    out["spread_pct"] = round(100 * (max(amounts) - min(amounts)) / med, 1) if med else None
    out["comparable"] = n >= 3        # com menos de 3 cotações, mediana/outlier não são estatisticamente informativos
    return out


def flag_quotes(quotes: list[dict], outlier_pct: float) -> list[dict]:
    amounts = [q["amount_cents"] for q in quotes]
    med = statistics.median(amounts) if amounts else 0
    res = []
    for q in quotes:
        dev = round(100 * (q["amount_cents"] - med) / med, 1) if med else None
        flag = None
        if len(amounts) >= 3 and dev is not None and abs(dev) > outlier_pct:
            flag = "possivelmente acima do padrão das cotações" if dev > 0 else "possivelmente abaixo do padrão das cotações (verificar escopo/qualidade)"
        res.append({**q, "deviation_pct": dev, "flag": flag})
    return res


def policy_for(c: Connection, org_id: str) -> dict:
    p = c.one("SELECT min_quotes, quote_threshold_cents, outlier_pct::float AS outlier_pct, exception_needs_approval FROM procurement_policies WHERE org_id = $1", org_id)
    return p or {"min_quotes": 3, "quote_threshold_cents": 0, "outlier_pct": 30.0, "exception_needs_approval": True, "default": True}


def requirement(policy: dict, estimated_cents: int) -> int:
    """Quantidade mínima de cotações exigida para este valor (0 = política não exige)."""
    return policy["min_quotes"] if estimated_cents >= policy["quote_threshold_cents"] else 0


def report(c: Connection, request_id: str) -> dict:
    req = c.one("SELECT r.*, r.id::text AS id, r.project_id::text AS project_id, r.org_id::text AS org_id, r.selected_quotation_id::text AS selected_quotation_id"
                " FROM procurement_requests r WHERE r.id = $1", request_id)
    if not req:
        return {}
    pol = policy_for(c, req["org_id"])
    quotes = c.query("SELECT id::text AS id, supplier_name, supplier_cnpj, amount_cents, valid_until, notes, document_id::text AS document_id"
                     " FROM quotations WHERE request_id = $1 ORDER BY amount_cents, supplier_name", request_id)
    need = requirement(pol, req["estimated_cents"])
    flagged = flag_quotes(quotes, pol["outlier_pct"])
    return {"request": req, "policy": pol, "required_quotes": need, "quotes": flagged,
            "benchmark": benchmark([q["amount_cents"] for q in quotes], pol["outlier_pct"]),
            "meets_policy": len(quotes) >= need,
            "selected_is_lowest": bool(req["selected_quotation_id"]) and quotes and req["selected_quotation_id"] == quotes[0]["id"]}
