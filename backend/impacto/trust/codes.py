"""Código público de verificação.

Formato: ``IMP-XXXX-XXXX-XXXX``. Alfabeto sem caracteres ambíguos (sem I, O, U) para ditar por telefone e ler de papel.
Aleatório (`secrets`), nunca sequencial: um código não permite descobrir outro.
"""
from __future__ import annotations

import secrets

ALPHABET = "0123456789ABCDEFGHJKLMNPQRSTVWXYZ"   # 33 caracteres; casa com o CHECK de verifiable_records.code
GROUPS = 3
GROUP_LEN = 4


def new_code() -> str:
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(GROUP_LEN)) for _ in range(GROUPS)]
    return "IMP-" + "-".join(groups)


def normalize(raw: str) -> str:
    """Aceita o que a pessoa digita (minúsculas, sem hífen, com espaços) e devolve o formato canônico."""
    cleaned = "".join(ch for ch in (raw or "").upper() if ch in ALPHABET or ch == "I" or ch == "O")
    cleaned = cleaned.replace("I", "1").replace("O", "0")       # confusão clássica em leitura de papel
    if cleaned.startswith("1MP"):
        cleaned = cleaned[3:]
    elif cleaned.startswith("IMP"):
        cleaned = cleaned[3:]
    if len(cleaned) != GROUPS * GROUP_LEN:
        return ""
    return "IMP-" + "-".join(cleaned[i:i + GROUP_LEN] for i in range(0, len(cleaned), GROUP_LEN))
