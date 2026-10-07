#!/usr/bin/env python3
"""Monta o painel navegável de telas a partir do inventário — nenhum dado digitado à mão.

O painel é uma página só, para publicar como artefato na claude.ai: a equipe de design e quem for
testar abre pelo link, filtra por tipo de organização e registra a revisão de cada tela. As revisões
ficam na base do artefato (capacidade `db`), não na página: quem abrir depois vê o que já foi dito.

O QUE O PAINEL É E NÃO É. É o inventário do roteador, navegável. Não é a aplicação rodando: as telas
não são renderizadas, porque renderizá-las sem backend produziria uma imitação do produto — telas
bonitas falhando em toda chamada de API — e isso seria pior que não mostrar nada. A página diz isso
no próprio cabeçalho.

Uso: make_screen_panel.py [saída.html]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INVENTARIO = ROOT / "docs" / "execution" / "screen_inventory.json"
MAPA_BACKEND = ROOT / "docs" / "execution" / "screen_backend_map.json"
TEMPLATE = ROOT / "scripts" / "templates" / "painel_de_telas.html"
MARCA = "/*__DADOS__*/"

#: Mesma ordem do `TIPOS` do extrator; `chaves` serve ao link direto por tipo (`…#osc`).
CHAVES = ["osc", "company", "individual", "provider", "government", "platform"]
TIPOS = ["OSC", "Empresa", "Apoiador", "Profissional", "Governo", "Administração"]
ALCANCE = {"menu": 0, "parâmetro": 1, "link direto": 2}
ESTADO = {"backend presente": 0, "endpoint ausente": 1, "sem chamada direta": 2,
          "chamada dinâmica": 3}


def _slug(rota: str) -> str:
    """Identificador de documento para a rota: só letras, dígitos e `_` (gramática de caminho do db)."""
    s = "".join(c if c.isalnum() else "_" for c in rota).strip("_")
    return s or "raiz"


def main() -> int:
    inv = json.loads(INVENTARIO.read_text(encoding="utf-8"))
    mapa = {t["rota"]: t for t in json.loads(MAPA_BACKEND.read_text(encoding="utf-8"))["lista"]}
    molde = TEMPLATE.read_text(encoding="utf-8")
    if MARCA not in molde:
        raise SystemExit(f"o molde perdeu a marca {MARCA}")

    linhas, slugs = [], {}
    for t in inv["lista"]:
        sl = _slug(t["rota"])
        # Duas rotas com o mesmo slug gravariam revisão uma sobre a outra — silenciosamente.
        if sl in slugs:
            raise SystemExit(f"slug repetido {sl!r}: {slugs[sl]} e {t['rota']}")
        slugs[sl] = t["rota"]
        linhas.append([
            t["rota"], sl, t["componente"], t["arquivo"], t["tabela"],
            1 if t["exige_login"] else 0, 1 if t["parametro"] else 0,
            [TIPOS.index(x) for x in t["alcanca"] if x in TIPOS],
            [TIPOS.index(x) for x in t["em_menu_de"] if x in TIPOS],
            t["rotulo"], ALCANCE[t["alcance"]],
            ESTADO[mapa[t["rota"]]["estado"]], mapa[t["rota"]]["operacoes"],
        ])

    dados = {
        "o_que_e": inv["o_que_e"],
        "tipos": TIPOS,
        "chaves": CHAVES,
        "por_tabela": inv["por_tabela"],
        "arquivos": len(inv["arquivos"]),
        "operacoes_no_backend": json.loads(MAPA_BACKEND.read_text(encoding="utf-8"))
            ["operacoes_no_backend"],
        "orfas_backend": json.loads(MAPA_BACKEND.read_text(encoding="utf-8"))
            ["operacoes_que_nenhuma_tela_chama"],
        "telas": linhas,
    }
    html = molde.replace(MARCA, json.dumps(dados, ensure_ascii=False, separators=(",", ":")))
    destino = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "docs" / "execution" / "painel_de_telas.html"
    destino.write_text(html, encoding="utf-8")
    print(f"{destino.name}: {len(linhas)} telas, {len(html):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
