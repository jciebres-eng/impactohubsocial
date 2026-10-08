#!/usr/bin/env python3
"""Gera `tokens.css` a partir de `tokens.json` — a fonte única da identidade oficial.

Adaptado de `tools/generate_tokens.py` do pacote IMPACTO_DESIGN_SYSTEM_FULL_CORRETO_v2.3. Só a
biblioteca padrão. Este arquivo gera apenas o adaptador CSS: o produto é uma SPA servida também no
WebView do Capacitor, então os adaptadores Tailwind e React Native do pacote original não têm
consumidor aqui e não são gerados (evita arquivo GERADO sem dono).

UMA CORREÇÃO EM RELAÇÃO AO ORIGINAL, E O MOTIVO. O gerador original emitia `color-scheme: dark`
para o tema `high-contrast`, mas esse tema é de **canvas claro** — a própria documentação do pacote
diz "o alto contraste mantém canvas claro, sem preto/amarelo". `color-scheme: dark` sobre canvas
claro faz os controles nativos do navegador (select, scrollbar, checkbox) renderizarem escuros sobre
fundo branco. Aqui o tema de alto contraste declara `color-scheme: light`.

Uso: python3 web/brand/generate_tokens.py   (um teste exige que tokens.css seja exatamente esta saída)
"""
import json
import re
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def _flat(d, p=""):
    o = {}
    for k, v in d.items():
        q = f"{p}-{k}" if p else k
        if isinstance(v, dict):
            o.update(_flat(v, q))
        else:
            o[q] = v
    return o


def _kebab(s):
    return re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", s).lower()


def gerar(tokens: dict) -> str:
    pf = _flat(tokens["primitive"])
    sem = {n: _flat(v) for n, v in tokens["semantic"]["color"].items()}
    linhas = ["/* GENERATED from tokens.json — do not edit by hand. Regere: python3 web/brand/generate_tokens.py */",
              ":root {"]
    for k, v in pf.items():
        if isinstance(v, list):
            v = ", ".join('"' + x + '"' if " " in x else x for x in v)
        linhas.append(f"  --pi-{_kebab(k)}: {v};")
    for k, v in sem["light"].items():
        linhas.append(f"  --pi-color-{_kebab(k)}: {v};")
    for grupo, valores in tokens["component"].items():
        for k, v in valores.items():
            linhas.append(f"  --pi-component-{_kebab(grupo)}-{_kebab(k)}: {v};")
    linhas += ["  color-scheme: light;", "}", '[data-theme="light"] { color-scheme: light; }',
               '[data-theme="dark"] {']
    for k, v in sem["dark"].items():
        linhas.append(f"  --pi-color-{_kebab(k)}: {v};")
    linhas += ["  color-scheme: dark;", "}", '[data-theme="high-contrast"] {']
    for k, v in sem["highContrast"].items():
        linhas.append(f"  --pi-color-{_kebab(k)}: {v};")
    linhas += ["  color-scheme: light;", "}",
               "@media (prefers-color-scheme: dark) { :root:not([data-theme]) {"]
    for k, v in sem["dark"].items():
        linhas.append(f"  --pi-color-{_kebab(k)}: {v};")
    linhas += ["  color-scheme: dark;", "} }", "@media (prefers-contrast: more) { :root:not([data-theme]) {"]
    for k, v in sem["highContrast"].items():
        linhas.append(f"  --pi-color-{_kebab(k)}: {v};")
    linhas += ["}", "}", ""]
    return "\n".join(linhas)


def main() -> int:
    tokens = json.loads((AQUI / "tokens.json").read_text(encoding="utf-8"))
    (AQUI / "tokens.css").write_text(gerar(tokens), encoding="utf-8")
    print(f"tokens.css gerado de tokens.json ({len(_flat(tokens['primitive']))} primitivos)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
