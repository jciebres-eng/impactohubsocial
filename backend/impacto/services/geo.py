"""Localização pública configurável (§42). Coordenadas exatas ficam privadas; o que é exposto depende da precisão escolhida.

exact → 5 casas (~1 m) · approximate → 1 casa (~11 km, com deslocamento determinístico) · neighborhood → 2 casas (~1 km)
municipality/region → sem coordenadas (apenas território textual). Não há mapa-base externo (CSP self-only): a interface
desenha pontos em projeção equiretangular simples.
"""
from __future__ import annotations

import hashlib

PRECISIONS = ("exact", "approximate", "neighborhood", "municipality", "region")
_DECIMALS = {"exact": 5, "approximate": 1, "neighborhood": 2}


def _jitter(key: str, span: float) -> tuple[float, float]:
    h = hashlib.sha256(key.encode()).digest()
    return ((h[0] / 255 - 0.5) * span, (h[1] / 255 - 0.5) * span)


def public_point(project_id: str, lat, lng, precision: str) -> dict | None:
    if lat is None or lng is None or precision not in _DECIMALS:
        return None
    lat, lng = float(lat), float(lng)
    if precision == "approximate":      # deslocamento estável (não varia a cada leitura) antes de arredondar
        dy, dx = _jitter(project_id, 0.08)
        lat, lng = lat + dy, lng + dx
    d = _DECIMALS[precision]
    return {"lat": round(lat, d), "lng": round(lng, d), "precision": precision}


def uf_of(territory: str) -> str | None:
    parts = (territory or "").split("-")
    return parts[1] if len(parts) >= 2 and parts[0] == "BR" else (parts[0] if len(parts[0]) == 2 and len(parts) == 1 and parts[0] != "BR" else None)
