#!/usr/bin/env python3
"""Gera o manifesto da versão: arquivo, sha256, tamanho e CATEGORIA.

Usa o mesmo `collect()` do empacotador, para que o manifesto e o ZIP descrevam exatamente o mesmo conjunto.

Uso: python3 scripts/make_version_manifest.py [saída.json]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_release import ROOT, collect, sha256

# (prefixo ou sufixo, categoria). A primeira regra que casa vence.
RULES: list[tuple[str, str]] = [
    ("backend/migrations/", "banco: migração"),
    ("backend/impacto/core/", "núcleo do produto"),
    ("backend/impacto/engines/", "motor"),
    ("backend/impacto/api/", "api: rotas e esquemas"),
    ("backend/impacto/services/", "serviço de domínio"),
    ("backend/impacto/integrations/", "integração"),
    ("backend/impacto/trust/", "confiança e assinatura"),
    ("backend/impacto/security/", "segurança"),
    ("backend/impacto/db/", "banco: acesso"),
    ("backend/tests/", "teste"),
    ("backend/", "backend"),
    ("web/src/", "frontend: código"),
    ("web/public/", "frontend: estático"),
    ("web/dist/", "frontend: build"),
    ("web/", "frontend"),
    ("config/", "configuração versionada"),
    ("scripts/", "operação"),
    ("infra/", "infraestrutura"),
    ("docs/evidence/", "evidência de execução"),
    ("docs/legal/", "documento legal"),
    ("docs/", "documentação técnica"),
    ("history/", "histórico de versão anterior"),
    ("mobile/", "mobile"),
]
DOC_ROOT = "documentação da raiz"


def category(rel: str) -> str:
    for prefix, cat in RULES:
        if rel.startswith(prefix):
            return cat
    if rel.endswith(".md"):
        return DOC_ROOT
    if rel in ("VERSION", ".env.example", "Makefile"):
        return "raiz do projeto"
    if rel.endswith("_MANIFEST.json"):
        return "manifesto de versão anterior"
    if rel.startswith(".github/"):
        return "integração contínua"
    if rel in ("Dockerfile", ".dockerignore", ".gitignore"):
        return "empacotamento e repositório"
    return "outro"


def main(out_path: str) -> int:
    version = (ROOT / "VERSION").read_text().strip()
    out_rel = Path(out_path).resolve().relative_to(ROOT).as_posix() if Path(out_path).resolve().is_relative_to(ROOT) else None
    entries = []
    for p in collect():
        rel = p.relative_to(ROOT).as_posix()
        # o próprio manifesto não pode conter o próprio hash; ele VAI no ZIP, mas não se lista
        if rel == out_rel:
            continue
        st = p.stat()
        entries.append({"file": rel, "sha256": sha256(p), "size_bytes": st.st_size,
                        "category": category(rel)})
    entries.sort(key=lambda e: e["file"])
    by_cat: dict[str, dict] = {}
    for e in entries:
        c = by_cat.setdefault(e["category"], {"files": 0, "size_bytes": 0})
        c["files"] += 1
        c["size_bytes"] += e["size_bytes"]
    doc = {
        "version": version,
        "note": ("Lista os arquivos do pacote da versão. O próprio manifesto não aparece aqui (não pode conter o "
                 "próprio hash), mas vai dentro do ZIP. O conjunto é o MESMO de RELEASE_MANIFEST.sha256, gerado "
                 "pelo mesmo collect() de scripts/make_release.py."),
        "generated_at": dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat(),
        "files_total": len(entries),
        "size_bytes_total": sum(e["size_bytes"] for e in entries),
        "by_category": dict(sorted(by_cat.items())),
        "files": entries,
    }
    Path(out_path).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{out_path}: {len(entries)} arquivos, {len(by_cat)} categorias, "
          f"{doc['size_bytes_total'] / 1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "V0.15.0_FINAL_MANIFEST.json"))
