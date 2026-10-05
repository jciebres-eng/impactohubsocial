"""Códigos territoriais hierárquicos.

Formato: ``INT`` (qualquer lugar) › ``BR`` (país, ISO-3166 alfa-2) › ``BR-MT`` (UF) › ``BR-MT-5105259`` (município, código IBGE).
Outros países: ``PT``, ``US`` etc. (sem subdivisão nesta versão).
"""
from __future__ import annotations

import re

_RE = re.compile(r"^(INT|[A-Z]{2}(-[A-Z]{2}(-[0-9]{7})?)?)$")


def valid(code: str | None) -> bool:
    return bool(code) and bool(_RE.match(code))


def parts(code: str) -> list[str]:
    return [] if code == "INT" else code.split("-")


def covers(scope: str, target: str) -> bool:
    """``scope`` abrange ``target``? (INT abrange tudo; BR abrange BR-MT; BR-MT abrange BR-MT-5105259)."""
    if not scope or not target:
        return False
    if scope == "INT":
        return True
    s, t = parts(scope), parts(target)
    return len(s) <= len(t) and t[: len(s)] == s


def specificity(scope: str, target: str) -> float:
    """Quão específico é o encaixe: município exato 1.0 · mesma UF 0.75 · mesmo país 0.5 · internacional 0.35 · fora 0."""
    if not covers(scope, target):
        return 0.0
    if scope == "INT":
        return 0.35
    depth = len(parts(scope))
    return {1: 0.5, 2: 0.75, 3: 1.0}.get(depth, 0.5)
