#!/usr/bin/env python3
"""Gera ENGINE_COVERAGE.md a partir do código. Nenhuma coluna é escrita à mão.

Rodar depois de qualquer mudança em motores, rotas ou testes:

    (cd backend && python3 ../scripts/make_engine_coverage.py)

Há teste que compara este arquivo com o cálculo corrente: documento desatualizado reprova a suíte,
pelo mesmo motivo que um glossário desatualizado reprova.
"""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from impacto.engines import coverage  # noqa: E402

DEST = ROOT / "ENGINE_COVERAGE.md"


def main() -> int:
    DEST.write_text(coverage.markdown() + "\n", encoding="utf-8")
    t = coverage.table()
    print(f"{DEST.name}: {t['total']} motores")
    for col, c in t["summary"].items():
        print(f"  {col:15s} {c['sim']} sim · {c['nao']} não"
              + (f" · {c['na']} n/a" if c["na"] else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
