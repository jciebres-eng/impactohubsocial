"""Estado documental: AUSENTE · EXPIRADO · PENDENTE DE VALIDAÇÃO · VALIDADO · REJEITADO (puro)."""
from __future__ import annotations

from datetime import date

from .common import as_date

USABLE_SCAN = {"clean"}          # o chamador normaliza o status do antivírus para 'clean' conforme o ambiente (services/documents.usable_statuses)


def doc_state(doc: dict, today: date) -> str:
    """Estado de UM documento. Antivírus ≠ validação humana: arquivo limpo mas não validado é 'pending_validation'."""
    if doc.get("validation_status") == "rejected" or doc.get("scan_status") in ("infected", "rejected"):
        return "rejected"
    vu = as_date(doc.get("valid_until"))
    if vu and vu < today:
        return "expired"
    if doc.get("scan_status") not in USABLE_SCAN:
        return "pending_validation"     # ainda não passou pelo antivírus: não pode contar como válido
    return "validated" if doc.get("validation_status") == "validated" else "pending_validation"


def best_state(docs: list[dict], doc_type: str, today: date) -> tuple[str, dict | None]:
    """Melhor estado entre as versões do tipo (validado > pendente > expirado > rejeitado > ausente)."""
    order = {"validated": 0, "pending_validation": 1, "expired": 2, "rejected": 3}
    cand = [(order[doc_state(d, today)], doc_state(d, today), d) for d in docs if d.get("doc_type") == doc_type]
    if not cand:
        return "absent", None
    cand.sort(key=lambda x: x[0])
    return cand[0][1], cand[0][2]
