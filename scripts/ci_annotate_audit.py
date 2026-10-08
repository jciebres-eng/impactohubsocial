#!/usr/bin/env python3
"""Resultado das auditorias de vulnerabilidade (pip-audit e npm audit) como anotações do Actions.

O passo de auditoria do CI nunca tinha rodado (a suíte antes dele morria no gitleaks); quando
rodou, falhou com só "exit code 1". Cada vulnerabilidade vira anotação com pacote, versão instalada,
identificador e versão que corrige — o necessário para decidir, sem abrir o log bruto.

Relatório ausente ou vazio é dito como tal: ferramenta que não rodou não é "sem vulnerabilidades".

Uso: ci_annotate_audit.py <pip-audit.json> <npm-audit.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _escapa(t: str) -> str:
    return t.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def _carrega(caminho: str):
    p = Path(caminho)
    if not p.exists() or not p.read_text(encoding="utf-8", errors="replace").strip():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return None


def pip(caminho: str) -> list[str] | None:
    d = _carrega(caminho)
    if d is None:
        print("::error title=pip-audit::relatório ausente ou ilegível — a ferramenta não rodou até o fim "
              "(isso NÃO é 'sem vulnerabilidades')")
        return None
    achados = []
    for dep in d.get("dependencies", []):
        for v in dep.get("vulns", []):
            fix = ", ".join(v.get("fix_versions") or []) or "sem versão corrigida publicada"
            achados.append(f"{dep['name']} {dep.get('version')} · {v.get('id')} "
                           f"({', '.join(v.get('aliases') or [])}) · corrige em: {fix}")
    pulados = [f"{dep['name']}: {dep.get('skip_reason')}" for dep in d.get("dependencies", []) if dep.get("skip_reason")]
    return achados + [f"NÃO AUDITADO {p}" for p in pulados]


def npm(caminho: str) -> list[str] | None:
    d = _carrega(caminho)
    if d is None:
        print("::error title=npm audit::relatório ausente ou ilegível — a ferramenta não rodou até o fim "
              "(isso NÃO é 'sem vulnerabilidades')")
        return None
    achados = []
    for nome, v in (d.get("vulnerabilities") or {}).items():
        via = [x.get("title") or x.get("url") for x in v.get("via", []) if isinstance(x, dict)]
        fix = v.get("fixAvailable")
        fix_txt = (f"{fix.get('name')} {fix.get('version')}" if isinstance(fix, dict)
                   else ("sim" if fix else "não"))
        achados.append(f"{nome} [{v.get('severity')}] {v.get('range', '')} · {'; '.join(via)[:200]} · correção: {fix_txt}")
    return achados


def main() -> int:
    pa = pip(sys.argv[1]) if len(sys.argv) > 1 else None
    na = npm(sys.argv[2]) if len(sys.argv) > 2 else None
    for titulo, lista in (("pip-audit (backend)", pa), ("npm audit --omit=dev (web)", na)):
        if lista is None:
            continue   # já anotado como "não rodou" — nunca vira "nenhuma vulnerabilidade"
        corpo = "\n".join(lista) if lista else "nenhuma vulnerabilidade relatada"
        nivel = "error" if lista else "notice"
        print(f"::{nivel} title={titulo}: {len(lista)} item(ns)::{_escapa(corpo[:6000])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
