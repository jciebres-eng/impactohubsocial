#!/usr/bin/env python3
"""Gera MANIFEST.sha256 e o zip do pacote. Uso: python3 scripts/make_release.py"""
import hashlib, os, zipfile, pathlib
root = pathlib.Path(__file__).resolve().parent.parent
ver = (root / "VERSION").read_text().strip()
files = sorted(p for p in root.rglob("*") if p.is_file() and not p.name.endswith(".zip") and p.name != "MANIFEST.sha256")
lines = [f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(root)}" for p in files]
(root / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")
out = root.parent / f"plataforma-impacto_docs_v{ver}.zip"
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in files + [root / "MANIFEST.sha256"]:
        z.write(p, f"plataforma-impacto-v{ver}/{p.relative_to(root)}")
print(out, len(files) + 1, "arquivos")
