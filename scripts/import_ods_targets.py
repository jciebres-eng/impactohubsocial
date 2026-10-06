#!/usr/bin/env python3
"""Carrega as metas dos ODS a partir de um arquivo oficial, com procedência obrigatória.

POR QUE ESTE ARQUIVO EXISTE AGORA, E NÃO ANTES

`IMPACT_FRAMEWORK_AUDIT.md` afirmava, desde a v0.18.0, que aquela rodada "entrega o importador
`scripts/import_ods_targets.py`". O arquivo NÃO existia no repositório, e nenhum código inseria em
`ods_targets` — a tabela estava vazia e sem nenhum caminho para deixar de estar. A auditoria da
v0.20.0 encontrou a divergência entre o documento e o código. Entre corrigir o documento e entregar o
que ele prometia, entregar é o certo: a tabela existe, a rota que a serve existe, e a lacuna era só
o carregador.

O QUE ESTE SCRIPT RECUSA FAZER

* rodar sem procedência: publicador, conjunto, licença e data da consulta são obrigatórios;
* gravar pela metade: ou o arquivo inteiro entra, ou nada entra;
* inventar o texto da meta: cada linha vem do arquivo, e o arquivo vem de quem publica os ODS.

A plataforma NÃO distribui os logos nem os emblemas oficiais da ONU (ver SDG_ESG_TAXONOMY.md); o que
entra aqui é o código da meta e o texto dela, com a fonte declarada.

USO

    DB="postgresql://impacto_owner:...@host/impacto" python3 scripts/import_ods_targets.py \\
        --file metas-ods.csv \\
        --publisher "Organização das Nações Unidas" \\
        --dataset "Indicadores Globais dos ODS — Agenda 2030" \\
        --version "2024-rev1" \\
        --license "Creative Commons BY 3.0 IGO" \\
        --source-url https://unstats.un.org/sdgs/indicators/indicators-list/ \\
        --retrieved-on 2026-10-06 \\
        [--published-on 2024-03-01] [--stale-after-months 60] [--dry-run]

O arquivo precisa ter as colunas `codigo` e `descricao` (nomes configuráveis).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from impacto.db.pq import Connection  # noqa: E402

CODE_RE = re.compile(r"^[0-9]{1,2}\.[0-9a-z]{1,2}$")


def ler(caminho: Path, col_codigo: str, col_descricao: str, encoding: str) -> list[tuple[str, str]]:
    linhas: list[tuple[str, str]] = []
    problemas: list[str] = []
    with caminho.open(encoding=encoding, newline="") as fh:
        leitor = csv.DictReader(fh)
        faltando = {col_codigo, col_descricao} - set(leitor.fieldnames or [])
        if faltando:
            raise SystemExit(f"colunas ausentes no arquivo: {', '.join(sorted(faltando))}; "
                             f"o arquivo tem {leitor.fieldnames}")
        for n, linha in enumerate(leitor, start=2):
            codigo = (linha.get(col_codigo) or "").strip()
            descricao = (linha.get(col_descricao) or "").strip()
            if not codigo and not descricao:
                continue
            if not CODE_RE.match(codigo):
                problemas.append(f"linha {n}: código de meta inválido: {codigo!r}")
                continue
            ods = int(codigo.split(".")[0])
            if not 1 <= ods <= 17:
                problemas.append(f"linha {n}: ODS fora de 1..17: {codigo!r}")
                continue
            if not 10 <= len(descricao) <= 1000:
                problemas.append(f"linha {n}: descrição com {len(descricao)} caracteres (10..1000)")
                continue
            linhas.append((codigo, descricao))
    if problemas:
        for p in problemas[:20]:
            print(f"  {p}", file=sys.stderr)
        raise SystemExit(f"{len(problemas)} linha(s) inválida(s). NADA foi gravado.")
    if not linhas:
        raise SystemExit("o arquivo não tem nenhuma meta válida. NADA foi gravado.")
    return linhas


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file", required=True)
    ap.add_argument("--publisher", required=True, help="Órgão que publica (ex.: ONU)")
    ap.add_argument("--dataset", required=True, help="Nome do conjunto de dados")
    ap.add_argument("--version", required=True, help="Versão da fonte (ex.: 2024-rev1)")
    ap.add_argument("--license", required=True,
                    help="Licença sob a qual o dado foi obtido. Se a fonte não declara, escreva "
                         "'não declarada pela fonte' — que é um fato, e não domínio público.")
    ap.add_argument("--source-url", required=True)
    ap.add_argument("--retrieved-on", required=True, help="Data da CONSULTA (AAAA-MM-DD)")
    ap.add_argument("--published-on", help="Data em que a FONTE publicou (AAAA-MM-DD)")
    ap.add_argument("--license-url")
    ap.add_argument("--stale-after-months", type=int,
                    help="Em quantos meses este conjunto deve ser tratado como desatualizado. "
                         "Sem isto, a plataforma responde 'não declarado' — nunca 'atual'.")
    ap.add_argument("--code-column", default="codigo")
    ap.add_argument("--description-column", default="descricao")
    ap.add_argument("--encoding", default="utf-8-sig")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    caminho = Path(args.file)
    if not caminho.exists():
        raise SystemExit(f"arquivo não encontrado: {caminho}")
    metas = ler(caminho, args.code_column, args.description_column, args.encoding)
    sha = hashlib.sha256(caminho.read_bytes()).hexdigest()
    print(f"{len(metas)} meta(s) lida(s) · sha256 do arquivo {sha[:16]}…")
    if args.dry_run:
        print("--dry-run: nada foi gravado.")
        return 0

    # A exigência de credencial vem DEPOIS da conferência do arquivo, de propósito: conferir a carga
    # é justamente o que se faz antes de ter acesso de escrita ao banco de produção.
    dsn = os.environ.get("DB") or os.environ.get("ADMIN_DATABASE_URL")
    if not dsn:
        raise SystemExit("defina DB com um papel capaz de escrever em ods_targets (impacto_owner)")
    conn = Connection(dsn)
    faltam = conn.scalar("SELECT 17 - count(*) FROM ods_goals")
    if faltam:
        raise SystemExit("ods_goals não está completa (17 objetivos): rode as migrações antes")
    conn.run("BEGIN")
    try:
        dataset_id = conn.scalar(
            "INSERT INTO external_datasets(key, version, publisher, dataset, url, published_at,"
            " retrieved_at, geographic_scope, license, license_url, file_name, file_sha256,"
            " rows_loaded, stale_after_months)"
            " VALUES ('ods_targets',$1,$2,$3,$4,$5,$6,'international',$7,$8,$9,$10,$11,$12)"
            " RETURNING id::text",
            args.version, args.publisher, args.dataset, args.source_url, args.published_on,
            args.retrieved_on, args.license, args.license_url, caminho.name, sha,
            len(metas), args.stale_after_months)
        for codigo, descricao in metas:
            ods = int(codigo.split(".")[0])
            conn.run("INSERT INTO ods_targets(code, ods, description, source, dataset_id, loaded_at)"
                     " VALUES ($1,$2,$3,$4,$5, now())"
                     " ON CONFLICT (code) DO UPDATE SET description = EXCLUDED.description,"
                     " source = EXCLUDED.source, dataset_id = EXCLUDED.dataset_id,"
                     " loaded_at = now()",
                     codigo, ods, descricao,
                     f"{args.publisher} — {args.dataset} ({args.version})", dataset_id)
        conn.run("COMMIT")
    except Exception:
        conn.run("ROLLBACK")
        raise
    print(f"carga concluída: {len(metas)} meta(s) · conjunto de dados {dataset_id}")
    print("A plataforma NÃO distribui logos nem emblemas oficiais da ONU (ver SDG_ESG_TAXONOMY.md).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
