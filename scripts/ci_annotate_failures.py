#!/usr/bin/env python3
"""Transforma as falhas da suíte em ANOTAÇÕES do GitHub Actions.

Por que existe: o log bruto de uma execução do Actions fica num armazenamento externo
(blob da Azure). Quem não está no navegador do GitHub — um ambiente de desenvolvimento atrás de
proxy, por exemplo — só vê "Process completed with exit code 1". Anotações saem pela API do GitHub
(`check-runs/{id}/annotations`), então este script põe ali o nome de cada teste que falhou e as
últimas linhas do traceback. Até a v0.24.0 o CI falhava em todo push e ninguém sabia em quê.

Uso: ci_annotate_failures.py <log da suíte, saída de `unittest -v`>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

LIMITE_DETALHADAS = 9          # o GitHub guarda 10 anotações de erro por passo; 1 vai para o resumo
LINHAS_DO_TRACEBACK = 14


def _escapa(texto: str) -> str:
    return texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    if len(sys.argv) < 2 or not Path(sys.argv[1]).exists():
        print("::error title=Resumo da suíte::log da suíte não encontrado — os testes nem chegaram a rodar?")
        return 0
    linhas = [l for l in Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace").splitlines()
              if not l.startswith("{")]   # o log estruturado da aplicação (JSON) não é do unittest
    texto = "\n".join(linhas)
    blocos = re.split(r"\n={50,}\n", texto)
    falhas = []
    for b in blocos[1:]:
        cab = b.splitlines()[0] if b else ""
        m = re.match(r"(FAIL|ERROR): (\S+) \(([^)]+)\)", cab)
        if not m:
            continue
        corpo = b.split("\n" + "-" * 70, 1)[-1].strip().split("\n" + "=" * 70)[0]
        cauda = [l for l in corpo.splitlines() if l.strip()][-LINHAS_DO_TRACEBACK:]
        falhas.append((m.group(1), m.group(3), "\n".join(cauda)))
    resumo = [l for l in linhas if re.match(r"^(Ran \d+ tests|FAILED|OK)", l)]
    nomes = "\n".join(f"{t} {n}" for t, n, _ in falhas) or "(nenhum bloco FAIL/ERROR encontrado no log)"
    print(f"::error title=Resumo da suíte::{_escapa(' | '.join(resumo) + chr(10) + nomes)}")
    for tipo, nome, cauda in falhas[:LIMITE_DETALHADAS]:
        print(f"::error title={tipo} {nome.split('.')[-1][:120]}::{_escapa(nome + chr(10) + cauda)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
