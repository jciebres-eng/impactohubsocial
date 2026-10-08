#!/usr/bin/env python3
"""Leva os rótulos do glossário oficial para o catálogo de tradução e gera GLOSSARY.md.

    python3 scripts/sync_glossary.py           # escreve config/i18n.json e GLOSSARY.md
    python3 scripts/sync_glossary.py --check    # não escreve; sai 1 se estiver fora de sincronia

POR QUE DOIS ARQUIVOS. ``config/glossary.json`` é a origem do vocabulário (rótulo nos três idiomas +
definição em pt-BR + onde o termo aparece na API). ``config/i18n.json`` é o catálogo que a migração
sincroniza para a tabela ``translations`` e que ``GET /v1/public/translations`` serve. Um é documentação
executável para quem desenha; o outro é dado de referência da aplicação. Este script mantém os dois
coerentes para que ninguém edite um e esqueça o outro — e ``--check`` é o que o teste roda.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOSSARY = ROOT / "config" / "glossary.json"
I18N = ROOT / "config" / "i18n.json"
MARKDOWN = ROOT / "GLOSSARY.md"
TYPESCRIPT = ROOT / "web" / "src" / "glossary.ts"

#: Namespaces de i18n que vêm do glossário. O que não estiver aqui é do núcleo e não se mexe.
PREFIX = "g_"


def namespaces(doc: dict) -> dict[str, dict[str, dict[str, str]]]:
    """``{locale: {namespace: {chave: rótulo}}}`` a partir do glossário."""
    out: dict[str, dict[str, dict[str, str]]] = {loc: {} for loc in doc["locales"]}
    for name, domain in doc["domains"].items():
        ns = f"{PREFIX}{name}"
        if len(ns) > 40:
            raise SystemExit(f"namespace longo demais para a tabela translations: {ns}")
        for loc in doc["locales"]:
            out[loc][ns] = {key: term["label"][loc] for key, term in domain["terms"].items()}
    return out


def merged(doc: dict, i18n: dict) -> dict:
    new = json.loads(json.dumps(i18n))
    want = namespaces(doc)
    for loc, spaces in want.items():
        if loc not in new["locales"]:
            raise SystemExit(f"idioma {loc} do glossário não existe em config/i18n.json")
        # Remove namespaces de glossário que saíram e reescreve os que ficaram: o glossário manda.
        for existing in [k for k in new["locales"][loc] if k.startswith(PREFIX)]:
            if existing not in spaces:
                del new["locales"][loc][existing]
        new["locales"][loc].update(spaces)
    new["glossary_version"] = doc["version"]
    new["note"] = (new["note"].split(" Os namespaces ")[0]
                   + f" Os namespaces {PREFIX}* vêm de config/glossary.json e são escritos por "
                     "scripts/sync_glossary.py — não edite à mão.")
    return new


def markdown(doc: dict) -> str:
    # Sem data de geração: arquivo gerado tem de ser função só da fonte. A versão anterior escrevia
    # `date.today()` aqui, e o `--check` passava a acusar "fora de sincronia" a cada virada de dia —
    # no CI, que roda em UTC, isso aconteceu à noite no Brasil (v0.24.1). A versão do glossário, no
    # título, é o que identifica o conteúdo.
    out = [f"# Glossário oficial — Impacto Trust v{doc['version']}", "",
           "> Gerado por `scripts/sync_glossary.py` a partir de `config/glossary.json`. Não edite à mão.", "",
           doc["note"], "",
           f"Idioma de origem: **{doc['source_locale']}** · Idiomas: {', '.join(doc['locales'])}", "",
           "## Como ler", "",
           "| Coluna | O que é |", "| --- | --- |",
           "| chave | o valor que a API devolve e o banco guarda |",
           "| pt-BR / en / es | o rótulo que a interface mostra. Não invente sinônimo em tela |",
           "| definição | para quem desenha e para quem escreve ajuda. Não é texto de tela |", ""]
    n = 0
    for name, domain in doc["domains"].items():
        out += [f"## {domain['title']}", "",
                f"`{name}` · aparece em: {domain['appears_in']}", ""]
        if domain.get("note"):
            out += [f"> {domain['note']}", ""]
        out += ["| chave | pt-BR | en | es | definição |", "| --- | --- | --- | --- | --- |"]
        for key, term in domain["terms"].items():
            lab = term["label"]
            alias = f" (também: {', '.join(term['aliases'])})" if term.get("aliases") else ""
            out.append(f"| `{key}`{alias} | {lab['pt-BR']} | {lab['en']} | {lab['es']} | {term['definition']} |")
            n += 1
        out.append("")
    out += ["## Termos que vivem no banco", "",
            doc["tiers"]["catalog"], "",
            "| tabela | rótulo | explicação |", "| --- | --- | --- |"]
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "glossary_mod", ROOT / "backend" / "impacto" / "core" / "glossary.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for table, s in mod.CATALOGS.items():
        out.append(f"| `{table}` | `{s['label']}` | `{s['explains']}` |")
    out += ["", f"Total: **{n} termos** em {len(doc['domains'])} domínios, "
                f"{n * len(doc['locales'])} rótulos, mais {len(mod.CATALOGS)} catálogos no banco.", ""]
    return "\n".join(out)


def typescript(doc: dict) -> str:
    """Gera web/src/glossary.ts: a interface CONSOME o vocabulário, não o copia.

    Antes da v0.19.0 existia uma terceira cópia dos mesmos rótulos dentro de uma página (um
    `BAND_LABEL` em TypeScript). Três cópias da mesma palavra concordavam por sorte. Agora o arquivo
    é gerado, o teste confere a sincronia, e quem desenha tem um único import para o rótulo de chip.
    """
    # Apelidos entram no dicionário gerado: a camada que consome não pode errar o rótulo porque um
    # módulo diz `insufficient` e outro diz `insufficient_data` para a mesma banda.
    pt: dict[str, dict[str, str]] = {}
    for name, d in doc["domains"].items():
        mapa: dict[str, str] = {}
        for k, term in d["terms"].items():
            mapa[k] = term["label"]["pt-BR"]
            for alias in term.get("aliases") or ():
                mapa[alias] = term["label"]["pt-BR"]
        pt[name] = mapa
    linhas = ["// GERADO por scripts/sync_glossary.py a partir de config/glossary.json — não edite à mão.",
              "// Rótulos em pt-BR (idioma de origem). Para en/es, use GET /v1/public/glossary?locale=...",
              "// ou GET /v1/public/translations (namespaces g_*), que já caem para pt-BR quando falta chave.",
              "",
              f"export const GLOSSARY_VERSION = {json.dumps(doc['version'])};", ""]
    for name in sorted(pt):
        const = name.upper()
        linhas.append(f"export const {const}: Record<string, string> = {{")
        for k, v in pt[name].items():
            linhas.append(f"  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)},")
        linhas += ["};", ""]
    linhas += [
        "/** Rótulo oficial de um termo. Sem rótulo, devolve a própria chave — nunca inventa sinônimo. */",
        "export function term(domain: Record<string, string>, key: string | null | undefined): string {",
        "  if (!key) return \"não informado\";",
        "  return domain[key] ?? key;",
        "}",
        "",
    ]
    return "\n".join(linhas)


def main() -> int:
    check = "--check" in sys.argv
    doc = json.loads(GLOSSARY.read_text(encoding="utf-8"))
    i18n = json.loads(I18N.read_text(encoding="utf-8"))
    new, md, ts = merged(doc, i18n), markdown(doc), typescript(doc)
    cur_md = MARKDOWN.read_text(encoding="utf-8") if MARKDOWN.exists() else ""
    cur_ts = TYPESCRIPT.read_text(encoding="utf-8") if TYPESCRIPT.exists() else ""
    if check:
        bad = []
        if new != i18n:
            bad.append("config/i18n.json está fora de sincronia com config/glossary.json")
        if md != cur_md:
            bad.append("GLOSSARY.md está fora de sincronia com config/glossary.json")
        if ts != cur_ts:
            bad.append("web/src/glossary.ts está fora de sincronia com config/glossary.json")
        for line in bad:
            print(f"FORA DE SINCRONIA: {line}")
        if bad:
            print("rode: python3 scripts/sync_glossary.py")
            return 1
        print("glossário em sincronia com i18n e GLOSSARY.md")
        return 0
    I18N.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MARKDOWN.write_text(md, encoding="utf-8")
    TYPESCRIPT.write_text(ts, encoding="utf-8")
    total = sum(len(d["terms"]) for d in doc["domains"].values())
    print(f"config/i18n.json: {len(doc['domains'])} namespaces {PREFIX}*, {total * len(doc['locales'])} rótulos")
    print(f"GLOSSARY.md: {total} termos em {len(doc['domains'])} domínios")
    print(f"web/src/glossary.ts: {len(doc['domains'])} dicionários em pt-BR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
