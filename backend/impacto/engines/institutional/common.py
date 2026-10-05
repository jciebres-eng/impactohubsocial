"""Vocabulário e utilitários compartilhados pela camada institucional (puro)."""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

CFG = Path(__file__).resolve().parents[4] / "config" / "institutional_maturity.json"

DISCLAIMER_LEGAL = ("Avaliação de apoio baseada em dados informados, documentos enviados e regras publicadas na plataforma. Não substitui advogado, contador, "
                    "especialista tributário nem a análise da autoridade ou do financiador. Requisitos legais devem ser confirmados na fonte e com profissional habilitado.")
BADGE_DISCLAIMER = "Classificação interna da plataforma — não é certificação governamental, não garante elegibilidade nem aprovação em editais."

STATE_LABELS = {"eligible": "ELEGÍVEL", "probably_eligible": "PROVAVELMENTE ELEGÍVEL", "pending": "ELEGIBILIDADE PENDENTE",
                "not_eligible": "NÃO ELEGÍVEL", "needs_professional_validation": "REQUER VALIDAÇÃO PROFISSIONAL"}
STATUS_LABELS = {"met": "Requisito atendido", "unmet": "Requisito não atendido", "unknown": "Não foi possível confirmar",
                 "pending_validation": "Informado — aguardando validação", "expired": "Expirado"}
DOC_STATE_LABELS = {"absent": "AUSENTE", "expired": "EXPIRADO", "pending_validation": "PENDENTE DE VALIDAÇÃO",
                    "validated": "VALIDADO", "rejected": "REJEITADO"}
# gravidade para combinar resultados (maior = pior)
SEVERITY = {"met": 0, "pending_validation": 1, "unknown": 2, "expired": 3, "unmet": 4}


@lru_cache(maxsize=1)
def config() -> dict:
    return json.loads(CFG.read_text(encoding="utf-8"))


def as_date(v) -> date | None:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def br(d: date | None) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"


def months_between(a: date, b: date) -> int:
    return (b.year - a.year) * 12 + (b.month - a.month) - (1 if b.day < a.day else 0)


def label_of(catalog: dict[str, dict] | None, code: str) -> str:
    """Rótulo de um código de catálogo (dict code -> item); cai para o próprio código quando o catálogo não conhece."""
    return ((catalog or {}).get(code) or {}).get("label") or code
