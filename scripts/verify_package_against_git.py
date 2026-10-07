#!/usr/bin/env python3
"""Prova que o conteúdo do pacote É a árvore de um commit Git — arquivo por arquivo.

A LACUNA QUE ESTE SCRIPT FECHA

O adendo de auditoria de 07/10/2026 registrou, com razão: *"O arquivo de projeto recebido não contém
`.git`; os commits e a tag citados nos relatórios permanecem declarações dos documentos anexados, não
verificações do histórico Git."*

Estava certo. Um ZIP que afirma vir do commit X não prova nada sobre X: o manifesto interno confere o
ZIP contra ele mesmo, o que detecta corrupção e não detecta divergência entre o que foi empacotado e
o que foi versionado.

Este script compara o conteúdo do pacote com os OBJETOS do Git, pelo sha1 que o próprio Git calcula
(`git hash-object`), e não pelo sha256 do manifesto. São duas cadeias independentes: se o pacote
tiver um arquivo que nunca foi commitado, ou um arquivo cujo conteúdo difere do commitado, aparece
aqui — ainda que o manifesto interno esteja perfeitamente consistente consigo mesmo.

COMO UM AUDITOR USA ISTO SEM CONFIAR EM NÓS

    git clone https://github.com/jciebres-eng/impactohubsocial
    cd impactohubsocial && git checkout <commit>
    unzip IMPACTO_v0.23.0_AUDIT_COMPLETION.zip -d /tmp/pkg
    python3 scripts/verify_package_against_git.py /tmp/pkg/plataforma-impacto-v0.23.0

Ou, sem rede, a partir do `impacto-v0.23.0.bundle` que acompanha o pacote de auditoria:

    git clone impacto-v0.23.0.bundle repo && cd repo

Uso: verify_package_against_git.py <diretório extraído> [commit]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Arquivos que o empacotador GERA no momento do empacotamento e que, por construção, não podem
#: coincidir com o objeto Git do commit — o manifesto é escrito depois que o conteúdo está fechado.
#: Cada exceção tem motivo escrito; uma exceção sem motivo é um buraco que ninguém lembra de ter aberto.
GERADOS_NO_EMPACOTAMENTO: dict[str, str] = {
    "RELEASE_MANIFEST.sha256": "lista de hashes do próprio pacote: escrita durante o empacotamento",
    "RELEASE_MANIFEST.csv": "idem, em formato tabular",
}


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} falhou:\n{r.stderr[-800:]}")
    return r.stdout


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    pacote = Path(sys.argv[1]).resolve()
    commit = sys.argv[2] if len(sys.argv) > 2 else "HEAD"
    if not pacote.is_dir():
        raise SystemExit(f"não é diretório: {pacote}")

    # Objetos do commit: caminho → sha1 do blob, direto do Git.
    do_git: dict[str, str] = {}
    for linha in _git("ls-tree", "-r", commit).splitlines():
        meta, caminho = linha.split("\t", 1)
        _modo, tipo, sha = meta.split()
        if tipo == "blob":
            do_git[caminho] = sha

    no_pacote = sorted(p for p in pacote.rglob("*") if p.is_file())
    divergentes: list[str] = []
    ausentes_no_git: list[str] = []
    conferidos = 0

    for f in no_pacote:
        rel = f.relative_to(pacote).as_posix()
        if rel in GERADOS_NO_EMPACOTAMENTO:
            continue
        esperado = do_git.get(rel)
        if esperado is None:
            ausentes_no_git.append(rel)
            continue
        atual = subprocess.run(["git", "hash-object", str(f)], cwd=ROOT,
                               capture_output=True, text=True).stdout.strip()
        if atual != esperado:
            divergentes.append(f"{rel}\n      git={esperado}\n      zip={atual}")
        else:
            conferidos += 1

    so_no_git = sorted(set(do_git) - {f.relative_to(pacote).as_posix() for f in no_pacote})

    print(f"commit conferido: {_git('rev-parse', commit).strip()}")
    print(f"árvore:           {_git('rev-parse', commit + '^{tree}').strip()}")
    print(f"arquivos no pacote: {len(no_pacote)} · conferidos contra o Git: {conferidos}")
    print(f"exceções declaradas (geradas no empacotamento): {len(GERADOS_NO_EMPACOTAMENTO)}")
    print(f"versionados e FORA do pacote: {len(so_no_git)} "
          "(exclusões do empacotador: evidência histórica, auto-referência)")

    problema = False
    if divergentes:
        problema = True
        print(f"\nDIVERGENTES ({len(divergentes)}) — conteúdo do pacote difere do commitado:")
        for d in divergentes[:20]:
            print(f"  - {d}")
    if ausentes_no_git:
        problema = True
        print(f"\nNO PACOTE E NÃO VERSIONADOS ({len(ausentes_no_git)}):")
        for a in ausentes_no_git[:20]:
            print(f"  - {a}")

    if problema:
        return 1
    print("\nOK: todo arquivo do pacote é o objeto Git do commit, byte a byte.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
