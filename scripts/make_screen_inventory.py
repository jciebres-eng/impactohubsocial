#!/usr/bin/env python3
"""Inventário das telas da aplicação web, extraído de `web/src/app.tsx`.

POR QUE EXTRAÍDO, E NÃO ESCRITO À MÃO

Um inventário escrito à mão descreve o que alguém lembra que existe. Este descreve o que o roteador
REALMENTE serve: cada linha vem de uma das três tabelas de rota, e a coluna de menu vem de `NAV`,
que é o que decide o que o usuário consegue alcançar clicando.

AS TRÊS TABELAS, NA ORDEM EM QUE O ROTEADOR TENTA CASAR (`app.tsx`, função de roteamento)

  1. `PUBLIC` — abre sem login, na moldura pública.
  2. `HELP`   — Central de Conhecimento; terceiro elemento `true` significa "exige login".
  3. `ROUTES` — aplicação autenticada; terceiro elemento é a lista de tipos de organização.

A primeira versão deste extrator lia só `ROUTES` e devolvia 179 telas — e o teste que a acompanhava
conferia a contagem CONTRA O PRÓPRIO BLOCO `ROUTES`, então passava com o inventário incompleto. As 35
telas de `HELP` e as 9 de `PUBLIC` ficavam de fora sem que nada reclamasse. Um instrumento que se
confere contra o próprio recorte não confere nada; agora a conferência é contra as três tabelas.

O cruzamento com os menus é a informação que mais interessa a quem vai desenhar ou testar: uma tela
que existe no roteador e não aparece em menu nenhum só é alcançável por link direto. Isso pode ser
correto (detalhe de um item, formulário de edição) ou pode ser tela órfã — e a diferença só aparece
quando alguém olha a lista.

Uso: make_screen_inventory.py [saída.json]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "web" / "src" / "app.tsx"

_COMPONENTE = re.compile(r"<([A-Z][\w.]*)")
_MENU_LINHA = re.compile(r'^\s*(\w+):\s*\[(.+)\],?\s*$', re.MULTILINE)
_MENU_ITEM = re.compile(r'\["(/[^"]*)",\s*"([^"]*)"\]')
_IMPORT = re.compile(r'^import \* as (\w+) from "\./(\S+)";', re.MULTILINE)
_PRIMEIRA_STRING = re.compile(r'^\s*"(/[^"]*)"\s*,')

#: Nome que o produto usa para cada tipo de organização (o mesmo `KIND_LABEL` do `app.tsx`).
TIPOS = {"osc": "OSC", "company": "Empresa", "individual": "Apoiador",
         "provider": "Profissional", "government": "Governo", "platform": "Administração"}

#: Tabela → (ordem em que o roteador tenta casar, como se entra).
TABELAS = {"PUBLIC": (1, "sem login"), "HELP": (2, "Central de Conhecimento"),
           "ROUTES": (3, "dentro da aplicação")}


def _bloco(texto: str, nome: str) -> str:
    r"""Devolve o `[ … ]` do lado direito de `const <nome>… = [ … ]`, com os colchetes.

    O `[` que interessa é o da ATRIBUIÇÃO, e achá-lo já falhou duas vezes de maneiras diferentes:
    procurar o primeiro `[` depois de `const` pegava o `[` do tipo (`R[]`) e procurar o primeiro `=`
    pegava o `=` de `=>` dentro da anotação `[string, () => ReactNode][]`, caindo no `[]` vazio logo
    adiante. Nos dois casos o resultado era um bloco vazio — zero tela, sem erro nenhum. Daí casar o
    `=\s*\[` inteiro: `=>` não casa, porque exige `[` depois do `=`.
    """
    m = re.search(r"const " + re.escape(nome) + r"\b.*?=\s*\[", texto, re.DOTALL)
    if not m:
        raise SystemExit(f"não achei a atribuição de {nome}")
    nivel, j = 0, m.end() - 1
    for k in range(j, len(texto)):
        if texto[k] == "[":
            nivel += 1
        elif texto[k] == "]":
            nivel -= 1
            if nivel == 0:
                return texto[j:k + 1]
    raise SystemExit(f"não achei o fim do bloco {nome}")


def _entradas(bloco: str) -> list[str]:
    """Separa as entradas de primeiro nível do bloco, contando colchetes.

    Substituiu uma expressão regular que já perdeu tela duas vezes: uma por ancorar no fim da linha
    (`app.tsx` tem linhas com duas rotas) e outra por exigir que o terceiro elemento fosse uma lista,
    o que deixava passar as entradas de `HELP`, cujo terceiro elemento é `true`. Contar colchetes não
    tem esse tipo de ponto cego.
    """
    fora, nivel, inicio = [], 0, None
    for k, ch in enumerate(bloco[1:-1], start=1):
        if ch == "[":
            if nivel == 0:
                inicio = k
            nivel += 1
        elif ch == "]":
            nivel -= 1
            if nivel == 0 and inicio is not None:
                fora.append(bloco[inicio + 1:k])
                inicio = None
    return fora


def _casa(padrao: str, caminho: str) -> bool:
    """Mesma regra do `match()` de `web/src/router.tsx`: nº de segmentos igual, `:x` casa um."""
    p = [s for s in padrao.split("/") if s]
    a = [s for s in caminho.split("/") if s]
    if len(p) != len(a):
        return False
    return all(seg.startswith(":") or seg == a[i] for i, seg in enumerate(p))


def main() -> int:
    texto = APP.read_text(encoding="utf-8")
    arquivo_de = {alias: f"web/src/{caminho}.tsx" for alias, caminho in _IMPORT.findall(texto)}
    menus_src = texto[texto.index("const NAV"):texto.index("const KIND_LABEL")]

    # menus: tipo → {caminho: rótulo}
    menus: dict[str, dict[str, str]] = {}
    for tipo, corpo in _MENU_LINHA.findall(menus_src):
        if tipo in TIPOS:
            menus[tipo] = dict(_MENU_ITEM.findall(corpo))
    rotulo_de: dict[str, str] = {}
    for m in menus.values():
        rotulo_de.update(m)

    telas, declaradas = [], {}
    for tabela, (ordem, entrada) in TABELAS.items():
        brutas = _entradas(_bloco(texto, tabela))
        declaradas[tabela] = [m.group(1) for m in map(_PRIMEIRA_STRING.match, brutas) if m]
        for bruta in brutas:
            m = _PRIMEIRA_STRING.match(bruta)
            if not m:
                continue
            caminho, resto = m.group(1), bruta[m.end():]
            comp = _COMPONENTE.search(resto)
            componente = comp.group(1) if comp else "(desconhecido)"
            tipos = re.findall(r'"(\w+)"', resto[resto.rindex(",") + 1:]) if resto.count(",") else []
            tipos = [t for t in tipos if t in TIPOS]
            exige_login = tabela == "ROUTES" or (tabela == "HELP" and resto.rstrip().endswith("true"))
            em_menu = sorted(t for t, mm in menus.items() if caminho in mm)
            telas.append({
                "rota": caminho,
                "tabela": tabela,
                "ordem_de_casamento": ordem,
                "entrada": entrada,
                "exige_login": exige_login,
                "componente": componente,
                "arquivo": arquivo_de.get(componente.split(".")[0], ""),
                "parametro": ":" in caminho,
                "tipos_declarados": tipos,
                "alcanca": [TIPOS[t] for t in tipos] if tipos else ["todos os tipos"],
                "em_menu_de": [TIPOS[t] for t in em_menu],
                "rotulo": rotulo_de.get(caminho, ""),
                "alcance": ("menu" if em_menu else
                            ("parâmetro" if ":" in caminho else "link direto")),
            })

    # Sombreamento: tela que nunca é alcançada porque um padrão de tabela anterior casa primeiro.
    sombreadas = []
    for i, t in enumerate(telas):
        amostra = re.sub(r":[^/]+", "x", t["rota"])
        for antes in telas[:i]:
            if antes["ordem_de_casamento"] < t["ordem_de_casamento"] and _casa(antes["rota"], amostra):
                sombreadas.append({"rota": t["rota"], "sombreada_por": antes["rota"],
                                   "tabela": antes["tabela"]})
                break

    telas.sort(key=lambda t: (t["ordem_de_casamento"], t["rota"]))
    saida = {
        "o_que_e": ("inventário das telas servidas por web/src/app.tsx, extraído das três tabelas de"
                    " rota (PUBLIC, HELP, ROUTES) na ordem em que o roteador tenta casar"),
        "o_que_nao_e": ("não é a aplicação rodando: é a lista do que o roteador serve. Nenhuma linha"
                        " aqui prova que a tela funciona contra um banco com dados."),
        "telas": len(telas),
        "por_tabela": {k: sum(1 for t in telas if t["tabela"] == k) for k in TABELAS},
        "sem_login": sum(1 for t in telas if not t["exige_login"]),
        "com_parametro": sum(1 for t in telas if t["parametro"]),
        "em_algum_menu": sum(1 for t in telas if t["em_menu_de"]),
        "so_por_link_direto": sum(1 for t in telas if t["alcance"] == "link direto"),
        "sombreadas": sombreadas,
        "menus_por_tipo": {TIPOS[t]: len(m) for t, m in sorted(menus.items())},
        "arquivos": sorted({t["arquivo"] for t in telas if t["arquivo"]}),
        "lista": telas,
    }
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "execution" / "screen_inventory.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(saida, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"{destino.name}: {len(telas)} telas")
    for k, v in saida["por_tabela"].items():
        print(f"  {k:<8} {v:3}  ({TABELAS[k][1]}, {len(declaradas[k])} declaradas no bloco)")
    print(f"  sem login                  {saida['sem_login']}")
    print(f"  com parâmetro de rota      {saida['com_parametro']}")
    print(f"  presentes em algum menu    {saida['em_algum_menu']}")
    print(f"  só por link direto         {saida['so_por_link_direto']}")
    print(f"  sombreadas                 {len(sombreadas)}")
    print(f"  arquivos de página         {len(saida['arquivos'])}")
    print("  menus por tipo:", ", ".join(f"{k} {v}" for k, v in saida["menus_por_tipo"].items()))
    for t, decl in declaradas.items():
        extraidas = [x["rota"] for x in telas if x["tabela"] == t]
        perdidas = [r for r in decl if r not in extraidas]
        if perdidas:
            print(f"  PERDIDAS em {t}: {perdidas}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
