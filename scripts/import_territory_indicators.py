#!/usr/bin/env python3
"""Importa indicador territorial (população, taxa, cobertura) a partir de arquivo oficial.

`territory_indicators` nasce VAZIA de propósito: nenhum número do IBGE, do DATASUS, do INEP ou de
qualquer outra fonte foi embutido na migração. O número entra por aqui, e só com procedência.

O script recusa:
  * rodar sem nome de fonte, URL e data de consulta;
  * código de indicador que não está em `determinant_indicator_defs`;
  * território que não está no catálogo (importe os municípios primeiro);
  * arquivo com qualquer linha inválida — não grava pela metade.

Uso:
    DB="postgresql://impacto_owner@host/impacto" python3 scripts/import_territory_indicators.py \
      --file saneamento_2022.csv --indicator saneamento_adequado \
      --territory-column codigo_ibge --value-column percentual --reference-date 2022-12-31 \
      --source-name "IBGE — Censo Demográfico 2022" --source-url https://... \
      --source-date 2026-10-06
"""
from __future__ import annotations

import argparse
import csv
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "backend"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--file", required=True)
    ap.add_argument("--indicator", required=True, help="código em determinant_indicator_defs")
    ap.add_argument("--territory-column", default="codigo_ibge")
    ap.add_argument("--value-column", default="valor")
    ap.add_argument("--reference-date", required=True, help="data a que o número se refere")
    ap.add_argument("--source-name", required=True)
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--source-date", required=True)
    ap.add_argument("--method-note", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--encoding", default="utf-8-sig")
    args = ap.parse_args()

    dsn = os.environ.get("DB")
    if not dsn:
        print("defina DB com a conexão do papel impacto_owner", file=sys.stderr)
        return 2
    path = pathlib.Path(args.file)
    if not path.exists():
        print(f"arquivo não encontrado: {path}", file=sys.stderr)
        return 2

    from impacto.db.pq import Connection
    conn = Connection(dsn)

    spec = conn.one("SELECT code, unit, name_pt FROM determinant_indicator_defs"
                    " WHERE code = $1 AND active", args.indicator)
    if not spec:
        print(f"indicador desconhecido: {args.indicator}. Veja determinant_indicator_defs.",
              file=sys.stderr)
        return 2
    known = {r["code"] for r in conn.query("SELECT code FROM territories WHERE active")}

    rows: list[tuple[str, float]] = []
    problems: list[str] = []
    with path.open(encoding=args.encoding, newline="") as fh:
        for n, rec in enumerate(csv.DictReader(fh), start=2):
            raw = (rec.get(args.territory_column) or "").strip()
            code = raw if raw.startswith(("BR-", "INT")) else None
            if code is None and raw.isdigit() and len(raw) == 7:
                code = next((k for k in known if k.endswith(f"-{raw}")), None)
            if not code or code not in known:
                problems.append(f"linha {n}: território desconhecido ({raw!r}) — importe os "
                                f"municípios antes")
                continue
            try:
                value = float((rec.get(args.value_column) or "").strip().replace(",", "."))
            except ValueError:
                problems.append(f"linha {n}: valor inválido ({rec.get(args.value_column)!r})")
                continue
            rows.append((code, value))

    for p in problems[:30]:
        print("✗", p, file=sys.stderr)
    print(f"{len(rows)} linhas válidas, {len(problems)} recusadas "
          f"(indicador: {spec['name_pt']}, unidade {spec['unit']})")
    if problems:
        print("NADA foi gravado.", file=sys.stderr)
        return 1
    if args.dry_run:
        print("--dry-run: nada gravado")
        return 0

    conn.run("BEGIN")
    try:
        for code, value in rows:
            conn.run(
                "INSERT INTO territory_indicators(territory, code, value, unit, reference_date,"
                " source_name, source_url, source_date, method_note)"
                " VALUES ($1,$2,$3,$4,$5::date,$6,$7,$8::date,$9)",
                code, args.indicator, value, spec["unit"], args.reference_date, args.source_name,
                args.source_url, args.source_date, args.method_note)
        conn.run("COMMIT")
    except Exception:
        conn.run("ROLLBACK")
        raise
    print(f"gravados {len(rows)} valores de {args.indicator}; a versão anterior de cada território "
          f"teve a vigência fechada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
