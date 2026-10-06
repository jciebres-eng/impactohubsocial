"""Contextualização determinística do sinal de impacto no match.

Este módulo não cria uma nota de equidade. Ele apenas transforma contexto agregado,
explicitamente fornecido e não sensível em um sinal explicável para apoio à decisão.
Ausência de contexto é ``None`` (UNKNOWN), nunca zero.
"""
from __future__ import annotations

from typing import Any


CONTEXT_KEYS = (
    "need_level",
    "barrier_burden",
    "infrastructure_gap",
    "additionality_score",
    "sustainability_score",
    "outcome_evidence_score",
    "impact_evidence_score",
    "denominator_quality",
)


def _bounded(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, value))


def contextual_impact(project: dict, *, has_indicators: bool) -> dict:
    """Retorna score, cobertura e explicação sem transformar população em impacto.

    O resultado é deliberadamente ``None`` se nenhum contexto foi informado. Quando há
    contexto parcial, calcula-se apenas sobre os componentes presentes e informa-se a
    cobertura; a aplicação pode exigir revisão humana conforme sua política.
    """
    raw = project.get("impact_context") or {}
    values = {key: _bounded(raw.get(key)) for key in CONTEXT_KEYS}
    known = {key: value for key, value in values.items() if value is not None}
    if not known:
        return {
            "score": None,
            "coverage": 0.0,
            "known": [],
            "unknown": list(CONTEXT_KEYS),
            "detail": "Contexto de necessidade, barreiras e evidência não informado; impacto UNKNOWN.",
        }

    # Contexto e adicionalidade aumentam a prioridade quando há evidência; não são
    # multiplicados como uma falsa fórmula de impacto. A régua é auditável e versionada.
    need = values["need_level"]
    barriers = values["barrier_burden"]
    infra_gap = values["infrastructure_gap"]
    additionality = values["additionality_score"]
    sustainability = values["sustainability_score"]
    outcome = values["outcome_evidence_score"]
    impact = values["impact_evidence_score"]
    denominator = values["denominator_quality"]
    parts = [
        (need, 0.22),
        (barriers, 0.18),
        (infra_gap, 0.14),
        (additionality, 0.14),
        (sustainability, 0.10),
        (outcome, 0.10),
        (impact, 0.07),
        (denominator, 0.05),
    ]
    present = [(value, weight) for value, weight in parts if value is not None]
    score = sum(value * weight for value, weight in present) / sum(weight for _, weight in present)
    if has_indicators and outcome is None and impact is None:
        detail_suffix = "; indicadores existem, mas sua evidência de resultado ainda é UNKNOWN"
    else:
        detail_suffix = ""
    return {
        "score": round(score, 4),
        "coverage": round(sum(weight for _, weight in present) / sum(weight for _, weight in parts), 4),
        "known": sorted(known),
        "unknown": [key for key in CONTEXT_KEYS if key not in known],
        "detail": (f"Contexto agregado: necessidade {need if need is not None else 'UNKNOWN'}, "
                    f"barreiras {barriers if barriers is not None else 'UNKNOWN'}, "
                    f"lacuna de infraestrutura {infra_gap if infra_gap is not None else 'UNKNOWN'}"
                    f"{detail_suffix}"),
    }
