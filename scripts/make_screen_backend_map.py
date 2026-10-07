#!/usr/bin/env python3
"""Cruza as telas do inventário com as operações que o backend registra.

A PERGUNTA QUE ISTO RESPONDE

O inventário diz que a rota existe e qual componente a serve. Não diz se a tela tem backend. Este
script responde isso do único jeito que não é opinião: lê as chamadas `api.<verbo>("/v1/…")` dentro
do corpo de cada componente exportado e confere cada caminho contra as 888 operações que
`impacto.http.ROUTES` registra depois de `api.load_all()`.

AS TRÊS COISAS QUE O PROMPT MANDA NÃO ESCONDER

  - interface sem backend  → componente que chama caminho que o backend não registra (`faltando`)
  - backend sem interface  → operação registrada que nenhum arquivo de página chama (`orfas_backend`)
  - tela sem chamada       → componente sem nenhuma chamada resolvível (`sem_chamada`)

O LIMITE DESTE MÉTODO, DITO ANTES QUE ALGUÉM CONFIE DEMAIS

1. A atribuição por componente corta o arquivo em `^export function Nome(`. Chamada que mora num
   auxiliar compartilhado conta para o auxiliar, não para a tela que o usa. Por isso `sem_chamada`
   significa "não chama diretamente", não "é estática".
2. Caminho montado em variável (`api.get(url)`) não é resolvível por leitura de texto e entra em
   `dinamicas`, sem ser contado como presente nem como faltando.
3. `backend presente` quer dizer que a operação existe e está registrada. NÃO quer dizer que a tela
   funciona: só a execução contra um banco com dados prova isso.

Uso: make_screen_backend_map.py [saída.json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

INVENTARIO = ROOT / "docs" / "execution" / "screen_inventory.json"
FRONT = ROOT / "web" / "src"

#: Início de `api.get(` e de `useLoad(`; o argumento é lido por `_argumento`, que entende template
#: aninhado. `useLoad(caminho)` é um GET: o corpo do hook em `web/src/ui/kit.tsx` chama `api.get`.
#: Ignorar esse envoltório era o que fazia 569 das 888 operações parecerem sem interface — os GET do
#: produto quase todos passam por ele.
_ABERTURA = re.compile(r"\b(?:api\.(get|post|put|patch|del|delete|upload)|(useLoad))\s*\(\s*")
_EXPORT = re.compile(r"^export function (\w+)", re.MULTILINE)
VERBO = {"get": "GET", "post": "POST", "put": "PUT", "patch": "PATCH", "del": "DELETE",
         "delete": "DELETE", "upload": "POST"}


def _argumento(fonte: str, i: int) -> str | None:
    """Lê a string literal que começa em `i`, inclusive template com `${…}` aninhado.

    A primeira versão era uma expressão regular que parava na primeira crase — e a crase podia estar
    DENTRO da interpolação: `` `/v1/readiness/snapshots${pid ? `?project_id=${pid}` : ""}` `` virava
    o caminho inexistente `/v1/readiness/snapshots${pid `, denunciado como "endpoint ausente". Era o
    extrator, não o produto.
    """
    aspas = fonte[i]
    if aspas not in "`\"'":
        return None
    saida, k = [], i + 1
    while k < len(fonte):
        c = fonte[k]
        if c == "\\":
            k += 2
            continue
        if aspas == "`" and c == "$" and fonte[k:k + 2] == "${":
            prof, k = 1, k + 2
            while k < len(fonte) and prof:
                prof += (fonte[k] == "{") - (fonte[k] == "}")
                k += 1
            saida.append("{}")
            continue
        if c == aspas:
            return "".join(saida)
        if c == "\n":
            return None
        saida.append(c)
        k += 1
    return None


def _normaliza(caminho: str) -> str:
    """`/v1/x/${id}/y?f=1` e `/v1/x/{org_id}/y` viram a mesma coisa: `/v1/x/{}/y`."""
    caminho = re.sub(r"\{[^}]*\}", "{}", caminho)
    return caminho.split("?")[0].rstrip("/") or "/"


def _variantes(caminho: str) -> list[str]:
    """O caminho e, quando um segmento é texto GRUDADO em interpolação, o mesmo sem a interpolação.

    `/v1/readiness/snapshots{}` é o caso: ali o `${…}` montava uma QUERY, não um segmento, e o
    caminho de verdade é `/v1/readiness/snapshots`.
    """
    segs = caminho.split("/")
    fora = [caminho]
    for i, seg in enumerate(segs):
        if "{}" in seg and seg != "{}":
            fora.append("/".join(segs[:i] + [seg.replace("{}", "")] + segs[i + 1:]).rstrip("/"))
    return fora


def _casa(frente: str, atras: str) -> bool:
    """Um `{}` do front casa QUALQUER segmento do backend — inclusive um literal.

    `/v1/help/newsletter/${mode}` com `mode` em {confirm, unsubscribe} é chamada legítima de duas
    operações literais registradas. Exigir `{}` contra `{}` denunciava isso como endpoint ausente.
    """
    a, b = frente.split("/"), atras.split("/")
    return len(a) == len(b) and all(x == y or "{}" in x for x, y in zip(a, b))


def _existe(op: str, backend: set[str]) -> bool:
    verbo, caminho = op.split(" ", 1)
    return any(any(_casa(v, c.split(" ", 1)[1]) for v in _variantes(caminho))
               for c in backend if c.startswith(verbo + " "))


def _ops(corpo: str) -> tuple[list[str], bool]:
    """Operações chamadas no trecho e se há chamada cujo caminho não é literal."""
    achadas, dinamica = set(), False
    for m in _ABERTURA.finditer(corpo):
        arg = _argumento(corpo, m.end())
        if arg is None or not arg.startswith("/v1/"):
            dinamica = True
            continue
        achadas.add(f"{'GET' if m.group(2) else VERBO[m.group(1)]} {_normaliza(arg)}")
    return sorted(achadas), dinamica


def _referencias(fonte: str) -> set[str]:
    """TODO literal `/v1/…` do arquivo, seja qual for a função que o recebe.

    Serve só ao cálculo de "backend sem interface", e de propósito é o denominador mais generoso:
    se o caminho aparece em qualquer lugar do front, a operação não é órfã. Assim um envoltório que
    eu não conheça não vira acusação falsa contra o produto.
    """
    fora, k = set(), 0
    while k < len(fonte):
        if fonte[k] in "`\"'":
            arg = _argumento(fonte, k)
            if arg is not None and arg.startswith("/v1/"):
                fora.add(_normaliza(arg))
            k += 1
            continue
        k += 1
    return fora


def _corpos(fonte: str) -> dict[str, str]:
    """Componente exportado → corpo, cortando em `^export function Nome(`."""
    marcas = [(m.group(1), m.start()) for m in _EXPORT.finditer(fonte)]
    return {nome: fonte[ini:(marcas[i + 1][1] if i + 1 < len(marcas) else len(fonte))]
            for i, (nome, ini) in enumerate(marcas)}


def main() -> int:
    from impacto import api
    api.load_all()
    from impacto.http import ROUTES
    backend = {f"{r.method} {_normaliza(r.path)}" for r in ROUTES}

    inv = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    cache: dict[str, dict[str, str]] = {}
    chamadas_vistas: set[str] = set()
    telas, faltando, sem_chamada, dinamicas = [], {}, [], []

    for t in inv["lista"]:
        arq, comp = t["arquivo"], t["componente"]
        nome = comp.split(".")[-1]
        if arq and arq not in cache:
            caminho = ROOT / arq
            cache[arq] = _corpos(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
        corpo = cache.get(arq, {}).get(nome, "")
        ops, dinamica = _ops(corpo)
        chamadas_vistas |= set(ops)
        ausentes = [o for o in ops if not _existe(o, backend)]
        tem_dinamica = dinamica
        estado = ("endpoint ausente" if ausentes else
                  "backend presente" if ops else
                  "chamada dinâmica" if tem_dinamica else "sem chamada direta")
        telas.append({"rota": t["rota"], "componente": comp, "arquivo": arq,
                      "operacoes": ops, "ausentes": ausentes, "estado": estado})
        if ausentes:
            faltando[t["rota"]] = ausentes
        elif estado == "sem chamada direta":
            sem_chamada.append(t["rota"])
        elif estado == "chamada dinâmica":
            dinamicas.append(t["rota"])

    # Backend sem interface: operação registrada que NENHUM arquivo do front menciona. A varredura é
    # a árvore `web/src` inteira, não só `pages/`: a sessão, o controle de acesso e o kit de UI também
    # chamam a API, e limitar a `pages/` inflava a lista de órfãs com operações que o front usa.
    fontes = sorted(FRONT.rglob("*.ts")) + sorted(FRONT.rglob("*.tsx"))
    mencionados = set()
    for arq in fontes:
        mencionados |= _referencias(arq.read_text(encoding="utf-8"))
    orfas = sorted(op for op in backend
                   if not any(_casa(v, op.split(" ", 1)[1])
                              for ch in mencionados for v in _variantes(ch)))

    saida = {
        "o_que_e": ("cruzamento das telas com as 888 operações registradas por impacto.http.ROUTES;"
                    " as chamadas vêm da leitura do corpo de cada componente exportado"),
        "o_que_nao_prova": ("'backend presente' quer dizer que a operação existe e está registrada."
                            " Não quer dizer que a tela funciona: só execução contra banco com dados"
                            " prova isso."),
        "operacoes_no_backend": len(backend),
        "telas": len(telas),
        "estados": {e: sum(1 for t in telas if t["estado"] == e) for e in
                    ("backend presente", "endpoint ausente", "chamada dinâmica", "sem chamada direta")},
        "interface_sem_backend": faltando,
        "arquivos_do_front_varridos": len(fontes),
        "operacoes_que_nenhuma_tela_chama": len(orfas),
        "orfas_backend": orfas,
        "telas_sem_chamada_direta": sem_chamada,
        "telas_com_chamada_dinamica": dinamicas,
        "lista": telas,
    }
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "execution" / "screen_backend_map.json"
    destino.write_text(json.dumps(saida, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{destino.name}: {len(telas)} telas × {len(backend)} operações")
    for e, n in saida["estados"].items():
        print(f"  {e:<20} {n:3}")
    print(f"  interface sem backend      {len(faltando)} tela(s)")
    print(f"  front varrido              {len(fontes)} arquivos de web/src")
    print(f"  backend sem interface      {len(orfas)} operação(ões) que o front não chama")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
