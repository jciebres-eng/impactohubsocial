#!/usr/bin/env python3
"""Achados do gitleaks como anotações do GitHub Actions (o log bruto não é legível de fora).

Lê o relatório JSON do `gitleaks git --redact` — o segredo já vem trocado por REDACTED, então nada
sensível sai daqui: só regra, arquivo, linha e commit.

Uso: ci_annotate_gitleaks.py <relatório.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def _escapa(texto: str) -> str:
    return texto.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main() -> int:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if not caminho or not caminho.exists():
        print("::error title=gitleaks::relatório ausente — o binário nem chegou a varrer (download ou checksum?)")
        return 0
    achados = json.loads(caminho.read_text(encoding="utf-8") or "[]")
    linhas = [f"{a.get('RuleID')}  {a.get('File')}:{a.get('StartLine')}  @{str(a.get('Commit', ''))[:8]}"
              for a in achados]
    print(f"::error title=gitleaks: {len(achados)} achado(s)::{_escapa(chr(10).join(linhas[:60]) or 'nenhum')}")
    for a in achados[:9]:
        print(f"::error file={a.get('File')},line={a.get('StartLine')},title=gitleaks {a.get('RuleID')}::"
              f"{_escapa(str(a.get('Description', '')) + ' — commit ' + str(a.get('Commit', ''))[:12])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
