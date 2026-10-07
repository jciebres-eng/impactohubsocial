#!/usr/bin/env python3
"""Inventário verificável da árvore `node_modules` que produziu o build. NÃO é um lockfile.

POR QUE NÃO É UM LOCKFILE, E POR QUE ISSO IMPORTA

A ressalva 8 do adendo de auditoria de 07/10/2026 registra: *"Ausência de `package-lock.json` segue
como lacuna de reprodutibilidade web."* Está correta, e continua em aberto.

Tentou-se gerar o lockfile offline, a partir do cache do npm:

    npm install --package-lock-only --offline
    → npm error code ENOTCACHED
      request to https://registry.npmjs.org/@capacitor%2fandroid failed:
      cache mode is 'only-if-cached' but no cached response is available.

Um `package-lock.json` legítimo precisa da árvore de dependências resolvida, da URL de origem e do
`integrity` de CADA pacote declarado — inclusive `@types/react`, `@types/react-dom` e os cinco
`@capacitor/*`, que nunca foram baixados neste ambiente porque o registry responde 403. Montar um
arquivo com esse nome contendo só os seis pacotes presentes seria pior que não ter: `npm ci` o
trataria como a árvore completa e instalaria menos do que o projeto declara.

Então este arquivo é outra coisa, com outro nome, e diz o que é: o **inventário do que está
instalado**, com a versão exata e o sha256 do conteúdo de cada pacote. Serve para responder uma
pergunta específica e verificável — *o build entregue foi produzido a partir de quais bytes?* — sem
fingir que resolve a reprodutibilidade.

O que ele cobre: `react`, `react-dom`, `scheduler`, `esbuild`, `typescript` e o binário de plataforma
do esbuild. É o conjunto que o `build.mjs` usa de fato. O que falta é de tipagem (`@types/*`, que só
afetam o typecheck) e de empacotamento móvel (`@capacitor/*`, fora do escopo desta rodada).

Uso: web_installed_tree.py [saída.json]
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NM = ROOT / "web" / "node_modules"


def _sha256_do_diretorio(d: Path) -> tuple[str, int, int]:
    """sha256 sobre (caminho relativo, conteúdo) de cada arquivo, em ordem. Determinístico."""
    h = hashlib.sha256()
    arquivos = sorted(p for p in d.rglob("*") if p.is_file() and not p.is_symlink())
    total = 0
    for p in arquivos:
        rel = p.relative_to(d).as_posix().encode()
        dados = p.read_bytes()
        total += len(dados)
        h.update(len(rel).to_bytes(4, "big")); h.update(rel)
        h.update(len(dados).to_bytes(8, "big")); h.update(dados)
    return h.hexdigest(), len(arquivos), total


def _pacotes() -> list[Path]:
    saida = []
    for p in sorted(NM.iterdir()):
        if p.name.startswith(".") or not p.is_dir():
            continue
        if p.name.startswith("@"):
            saida += sorted(x for x in p.iterdir() if x.is_dir())
        else:
            saida.append(p)
    return saida


def main() -> int:
    if not NM.is_dir():
        raise SystemExit("web/node_modules não existe: nada a inventariar")
    declarado = json.loads((ROOT / "web" / "package.json").read_text(encoding="utf-8"))
    esperados = {**declarado.get("dependencies", {}), **declarado.get("devDependencies", {})}

    itens = []
    for d in _pacotes():
        pj = d / "package.json"
        if not pj.exists():
            continue
        meta = json.loads(pj.read_text(encoding="utf-8"))
        sha, n, bytes_ = _sha256_do_diretorio(d)
        itens.append({
            "name": meta.get("name", d.name),
            "version": meta.get("version"),
            "declared_range": esperados.get(meta.get("name", d.name)),
            "files": n, "bytes": bytes_, "sha256_tree": sha,
        })

    instalados = {i["name"] for i in itens}
    ausentes = sorted(n for n in esperados if n not in instalados)

    saida = {
        "o_que_este_arquivo_e": "inventário verificável da árvore node_modules que produziu o build",
        "o_que_este_arquivo_nao_e": "um package-lock.json; ver D-SUP1 em docs/execution/BLOCKERS.md",
        "declarados_em_package_json": len(esperados),
        "instalados": len(itens),
        "declarados_e_ausentes": ausentes,
        "motivo_das_ausencias": ("o registry npm responde 403 neste ambiente; @types/* afetam apenas "
                                 "o typecheck (contornado por tsconfig.offline.json) e @capacitor/* "
                                 "são de empacotamento móvel, fora do escopo desta rodada"),
        "pacotes": sorted(itens, key=lambda i: i["name"]),
    }
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "web" / "INSTALLED_TREE.json"
    destino.write_text(json.dumps(saida, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{destino.name}: {len(itens)} pacotes instalados de {len(esperados)} declarados")
    for i in saida["pacotes"]:
        print(f"  {i['name']:28s} {str(i['version']):10s} {i['sha256_tree'][:16]}… "
              f"({i['files']} arquivos)")
    if ausentes:
        print(f"\n  declarados e AUSENTES ({len(ausentes)}): {', '.join(ausentes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
