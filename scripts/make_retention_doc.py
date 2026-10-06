#!/usr/bin/env python3
"""Gera DATA_RETENTION.md conferindo a política contra o banco real.

    DATABASE_URL=postgresql://... python3 scripts/make_retention_doc.py

Fica em scripts/, e não dentro de `impacto/`, por decisão arquitetural: o contexto de SISTEMA do
banco é privilegiado, e a suíte tem uma guarda que lista quais módulos da aplicação podem usá-lo
(`test_system_context_only_in_allowed_modules`). Um gerador de documento não tem por que entrar
nessa lista — então ele sai do módulo.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from impacto.core import retention  # noqa: E402
from impacto.db.pool import DbContext, Pool  # noqa: E402


def main() -> int:
    dsn = os.environ.get("DATABASE_URL") or os.environ.get("ADMIN_DATABASE_URL")
    if not dsn:
        print("defina DATABASE_URL para gerar DATA_RETENTION.md", file=sys.stderr)
        return 2
    pool = Pool(dsn, max_size=1)
    with pool.tx(DbContext(system=True)) as conn:
        retention.MARKDOWN.write_text(retention.markdown(conn), encoding="utf-8")
    print(f"{retention.MARKDOWN} escrito")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
