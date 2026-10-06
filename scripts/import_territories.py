#!/usr/bin/env python3
"""Importa o nível MUNICIPAL do catálogo territorial a partir de arquivo oficial.

POR QUE ESTE SCRIPT EXISTE

A plataforma não embute os 5.570 municípios brasileiros. Transcrever de memória uma lista de 5.570
nomes e códigos produziria erros que ninguém encontraria — e o código do IBGE é usado para cruzar
dado público, então um dígito errado contamina comparação territorial.

Então o catálogo nasce com país, regiões e as 27 unidades federativas (marcadas
`from_official_load = false`, ou seja "a conferir"), e o nível municipal entra por aqui.

O script RECUSA rodar sem a procedência do arquivo: nome da fonte, URL e data de consulta são
obrigatórios. E confere, linha por linha, se os dois primeiros dígitos do código IBGE correspondem à
UF declarada — é uma verificação de integridade real, que pega arquivo trocado ou coluna deslocada.

Uso:
    DB="postgresql://impacto_owner@host/impacto" python3 scripts/import_territories.py \
      --file municipios.csv --code-column codigo_ibge --name-column nome --uf-column uf \
      --source-name "IBGE — Divisão Territorial Brasileira 2024" \
      --source-url https://www.ibge.gov.br/... --source-date 2026-10-06

    # conferir sem gravar
    ... --dry-run
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
    ap.add_argument("--file", required=True, help="CSV com os municípios")
    ap.add_argument("--code-column", default="codigo_ibge")
    ap.add_argument("--name-column", default="nome")
    ap.add_argument("--uf-column", default="uf")
    ap.add_argument("--source-name", required=True, help="Nome da fonte oficial do arquivo")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--source-date", required=True, help="Data da consulta (AAAA-MM-DD)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--encoding", default="utf-8-sig")
    args = ap.parse_args()

    dsn = os.environ.get("DB")
    if not dsn and not args.dry_run:
        print("defina DB com a conexão do papel impacto_owner", file=sys.stderr)
        return 2

    path = pathlib.Path(args.file)
    if not path.exists():
        print(f"arquivo não encontrado: {path}", file=sys.stderr)
        return 2

    from impacto.db.pq import Connection

    uf_codes: dict[str, str] = {}
    conn = None
    if dsn:
        conn = Connection(dsn)
        for row in conn.query("SELECT uf, ibge_code FROM territories WHERE kind = 'state'"):
            uf_codes[row["uf"]] = row["ibge_code"]
    if not uf_codes:
        print("catálogo de UF vazio: aplique a migração 0026 antes de importar", file=sys.stderr)
        return 2

    ok = bad = 0
    problems: list[str] = []
    rows: list[tuple[str, str, str, str]] = []
    with path.open(encoding=args.encoding, newline="") as fh:
        for n, rec in enumerate(csv.DictReader(fh), start=2):
            code = (rec.get(args.code_column) or "").strip()
            name = (rec.get(args.name_column) or "").strip()
            uf = (rec.get(args.uf_column) or "").strip().upper()
            if not (code.isdigit() and len(code) == 7):
                problems.append(f"linha {n}: código IBGE inválido ({code!r})")
                bad += 1
                continue
            if uf not in uf_codes:
                problems.append(f"linha {n}: UF desconhecida ({uf!r})")
                bad += 1
                continue
            # A verificação que vale: os dois primeiros dígitos do código IBGE são o código da UF.
            if code[:2] != uf_codes[uf]:
                problems.append(f"linha {n}: código {code} não pertence a {uf} "
                                f"(esperado começar com {uf_codes[uf]})")
                bad += 1
                continue
            if not (2 <= len(name) <= 160):
                problems.append(f"linha {n}: nome inválido ({name!r})")
                bad += 1
                continue
            rows.append((f"BR-{uf}-{code}", name, uf, code))
            ok += 1

    for p in problems[:30]:
        print("✗", p, file=sys.stderr)
    if len(problems) > 30:
        print(f"... e mais {len(problems) - 30} problemas", file=sys.stderr)
    print(f"{ok} municípios válidos, {bad} recusados")

    if bad:
        print("NADA foi gravado: arquivo com linha inválida não entra pela metade", file=sys.stderr)
        return 1
    if args.dry_run or not conn:
        print("--dry-run: nada gravado")
        return 0

    conn.run("BEGIN")
    try:
        for code, name, uf, ibge in rows:
            conn.run(
                "INSERT INTO territories(code, kind, name, parent_code, uf, ibge_code, source_name,"
                " source_url, source_date, from_official_load)"
                " VALUES ($1,'municipality',$2,$3,$4,$5,$6,$7,$8::date,true)"
                " ON CONFLICT (code) DO UPDATE SET name = excluded.name,"
                " source_name = excluded.source_name, source_url = excluded.source_url,"
                " source_date = excluded.source_date, from_official_load = true",
                code, name, f"BR-{uf}", uf, ibge, args.source_name, args.source_url,
                args.source_date)
        conn.run("COMMIT")
    except Exception:
        conn.run("ROLLBACK")
        raise
    print(f"gravados {len(rows)} municípios com from_official_load = true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
