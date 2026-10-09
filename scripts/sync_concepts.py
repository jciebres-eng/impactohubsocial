#!/usr/bin/env python3
"""Gera web/src/concepts.ts a partir de config/concepts.json (catálogo central de conceitos da ajuda contextual).

    python3 scripts/sync_concepts.py           # escreve web/src/concepts.ts
    python3 scripts/sync_concepts.py --check   # não escreve; sai 1 se estiver fora de sincronia (o teste roda isto)

POR QUE. Tooltip, popover e página de glossário mostram o MESMO texto: o catálogo é a única origem, o TypeScript é gerado
(a interface consome, não copia) e `GET /v1/public/concepts` serve o mesmo arquivo para quem integra. Ninguém digita a
definição de "match territorial" em três componentes. O arquivo gerado é função só da fonte (sem data), como glossary.ts.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONCEPTS = ROOT / "config" / "concepts.json"
TYPESCRIPT = ROOT / "web" / "src" / "concepts.ts"

ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")
REQUIRED = ("term", "domain", "short", "long", "why", "how_impacto", "limitations", "sources", "related", "applies_to", "status")
STATUSES = ("published", "needs_review", "draft")
SOURCE_KINDS = ("official", "illustrative")
AUDIENCES = ("osc", "company", "government", "provider", "individual")
#: Palavras que nenhuma definição pode usar como promessa (o teste também confere).
FORBIDDEN = re.compile(r"\b(garant\w*|certific\w+ que|100 ?%|aprova[çc][ãa]o garantida|inviol[áa]vel|imposs[íi]vel de invadir)\b", re.IGNORECASE)


def validate(doc: dict) -> list[str]:
    errs: list[str] = []
    terms = doc.get("terms") or {}
    for cid, t in terms.items():
        if not ID_RE.match(cid):
            errs.append(f"{cid}: id inválido")
        for k in REQUIRED:
            if k not in t:
                errs.append(f"{cid}: falta '{k}'")
        if len(t.get("short", "")) > 160:
            errs.append(f"{cid}: short com {len(t['short'])} caracteres (máximo 160)")
        if t.get("domain") not in (doc.get("domains") or {}):
            errs.append(f"{cid}: domínio desconhecido {t.get('domain')!r}")
        if t.get("status") not in STATUSES:
            errs.append(f"{cid}: status inválido")
        for r in t.get("related", []):
            if r not in terms:
                errs.append(f"{cid}: related aponta para id inexistente {r!r}")
        for a in t.get("applies_to", []):
            if a not in AUDIENCES:
                errs.append(f"{cid}: applies_to desconhecido {a!r}")
        if not t.get("sources"):
            errs.append(f"{cid}: sem fonte")
        for s in t.get("sources", []):
            if s.get("kind") not in SOURCE_KINDS or not s.get("label"):
                errs.append(f"{cid}: fonte sem kind/label")
            if s.get("kind") == "official" and not (s.get("source_ref") or s.get("url")):
                errs.append(f"{cid}: fonte 'official' precisa de source_ref (kb_sources) ou url")
            if s.get("path") and not (ROOT / s["path"].lstrip("/")).exists() and not s["path"].startswith("/ajuda/"):
                errs.append(f"{cid}: path inexistente {s['path']!r}")
        for field in ("short", "long", "why", "how_impacto", "limitations"):
            m = FORBIDDEN.search(t.get(field, ""))
            if m and "não" not in t.get(field, "")[max(0, m.start() - 40):m.start()].lower() and "nunca" not in t.get(field, "")[max(0, m.start() - 40):m.start()].lower():
                errs.append(f"{cid}.{field}: promessa proibida {m.group(0)!r}")
    return errs


def typescript(doc: dict) -> str:
    lines = ["// GERADO por scripts/sync_concepts.py a partir de config/concepts.json — não edite à mão.",
             "// Catálogo central de conceitos da ajuda contextual (tooltip = short; popover/glossário = tudo).",
             "// A mesma fonte é servida por GET /v1/public/concepts.", "",
             "export type ConceptSource = { kind: \"official\" | \"illustrative\"; label: string; url?: string; path?: string; source_ref?: string };",
             "export type Concept = {",
             "  id: string; term: string; domain: string; short: string; long: string; why: string; how_impacto: string; limitations: string;",
             "  sources: ConceptSource[]; related: string[]; applies_to: string[]; status: \"published\" | \"needs_review\" | \"draft\";",
             "};", "",
             f"export const CONCEPTS_VERSION = {json.dumps(doc['version'])};",
             f"export const CONCEPT_DOMAINS: Record<string, string> = {json.dumps(doc['domains'], ensure_ascii=False, indent=2)};", "",
             "export const CONCEPTS: Record<string, Concept> = {"]
    for cid in sorted(doc["terms"]):
        t = doc["terms"][cid]
        obj = {"id": cid, **{k: t[k] for k in REQUIRED}}
        lines.append(f"  {json.dumps(cid)}: {json.dumps(obj, ensure_ascii=False)},")
    lines += ["};", "",
              "/** Conceito por id. Sem conceito, devolve null — o componente então não mostra nada (nunca inventa texto). */",
              "export function concept(id: string | null | undefined): Concept | null {",
              "  return id ? CONCEPTS[id] ?? null : null;",
              "}", ""]
    return "\n".join(lines)


def main() -> int:
    doc = json.loads(CONCEPTS.read_text(encoding="utf-8"))
    errs = validate(doc)
    if errs:
        print("\n".join(errs))
        return 1
    ts = typescript(doc)
    if "--check" in sys.argv:
        if not TYPESCRIPT.exists() or TYPESCRIPT.read_text(encoding="utf-8") != ts:
            print("web/src/concepts.ts fora de sincronia com config/concepts.json — rode scripts/sync_concepts.py")
            return 1
        print(f"ok: {len(doc['terms'])} conceitos em sincronia")
        return 0
    TYPESCRIPT.write_text(ts, encoding="utf-8")
    print(f"escrito {TYPESCRIPT.relative_to(ROOT)} ({len(doc['terms'])} conceitos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
