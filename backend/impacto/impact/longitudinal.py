"""Agregações longitudinais sem inferir causalidade a partir de uma medição isolada."""
from __future__ import annotations

from typing import Any


def summarize_measurements(values: list[dict[str, Any]], *, total_known: int | None = None,
                           window: int | None = None) -> dict[str, Any]:
    """Resume a série de medições de UM indicador.

    `total_known` e `window` existem porque a rota lê as medições mais recentes com `LIMIT`: sem
    declarar a janela, `first_measured_on` e os deltas pareceriam ser da vida inteira do projeto
    quando são apenas da janela lida. Série truncada sem aviso é série que mente de boa-fé.
    """
    ordered = sorted((v for v in values if v.get("status") != "rejected"),
                     key=lambda v: (str(v.get("measured_on") or ""), str(v.get("id") or "")))
    reported = [v for v in ordered if v.get("status") == "reported"]
    validated = [v for v in ordered if v.get("status") == "validated"]

    def _series(items: list[dict]) -> list[dict]:
        return [{"id": v.get("id"), "measured_on": v.get("measured_on"), "value": v.get("value"),
                 "evidence_id": v.get("evidence_id"), "status": v.get("status")} for v in items]

    def _delta(items: list[dict]) -> float | None:
        if len(items) < 2 or items[0].get("value") is None or items[-1].get("value") is None:
            return None
        return round(float(items[-1]["value"]) - float(items[0]["value"]), 4)

    truncated = bool(total_known is not None and window is not None and total_known > window)
    return {
        "periods": len(ordered),
        "window": window,
        "total_known": total_known,
        "window_truncated": truncated,
        "reported_periods": len(reported),
        "validated_periods": len(validated),
        "first_measured_on": ordered[0].get("measured_on") if ordered else None,
        "last_measured_on": ordered[-1].get("measured_on") if ordered else None,
        "reported_delta": _delta(reported),
        "validated_delta": _delta(validated),
        "series": {"reported": _series(reported), "validated": _series(validated)},
        "interpretation": ("Série de medições; mudança observada não prova causalidade."
                           + (f" ATENÇÃO: a série mostra as {window} medições mais recentes de "
                              f"{total_known}; o delta é da janela, não da vida do projeto."
                              if truncated else "")),
    }
