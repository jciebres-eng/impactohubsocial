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


def _versao(v: str) -> tuple:
    return tuple(int(x) if x.isdigit() else 0 for x in v.replace("-", ".").split(".")[:4])


def resumo_pip(caminho: str) -> list[str]:
    """Uma linha por PACOTE: versão instalada, quantas vulnerabilidades e a menor versão que corrige
    TODAS (o maior `fix_version` entre elas). É a linha que decide a atualização."""
    d = _carrega(caminho) or {}
    linhas = []
    for dep in d.get("dependencies", []):
        vulns = dep.get("vulns") or []
        if not vulns:
            continue
        ids = {v.get("id") for v in vulns}
        fixes = [max((f for f in (v.get("fix_versions") or [])), key=_versao, default=None) for v in vulns]
        sem_fix = sum(1 for f in fixes if f is None)
        alvo = max((f for f in fixes if f), key=_versao, default=None)
        linhas.append(f"{dep['name']} {dep.get('version')}: {len(ids)} vulnerabilidade(s) · corrige TODAS em "
                      f"{alvo or '—'}" + (f" · {sem_fix} sem correção publicada" if sem_fix else ""))
    return linhas


def main() -> int:
    if len(sys.argv) > 1:
        por_pacote = resumo_pip(sys.argv[1])
        if por_pacote:
            print(f"::error title=pip-audit POR PACOTE: {len(por_pacote)} pacote(s)::{_escapa(chr(10).join(por_pacote))}")
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
