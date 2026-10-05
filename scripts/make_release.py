#!/usr/bin/env python3
"""Gera o release: RELEASE_MANIFEST.sha256 (compatível com `sha256sum -c`), RELEASE_MANIFEST.csv (sha256,arquivo,tamanho,data)
e FINAL_FULL_RELEASE.zip (sem ZIP aninhado, sem segredos, sem node_modules/caches/dados locais).

Uso:
  python3 scripts/make_release.py                 # gera manifesto + zip em ./dist-release/
  python3 scripts/make_release.py --verify DIR    # confere um diretório extraído contra RELEASE_MANIFEST.sha256
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist-release"
EXCLUDE_DIRS = {"node_modules", "__pycache__", ".git", ".venv", "venv", "data", "dist-release", ".pytest_cache", ".ruff_cache",
                ".mypy_cache", "outbox", "android", "ios", "build"}
EXCLUDE_SUFFIX = {".pyc", ".pyo", ".log", ".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".jks", ".keystore", ".zip"}
EXCLUDE_NAMES = {".env", ".DS_Store", "RELEASE_MANIFEST.sha256", "RELEASE_MANIFEST.csv"}
# Exceções: evidência de teste (.log) é parte do release
KEEP_EXACT = {"docs/evidence/test_run_v0.7.0.log", "docs/evidence/test_run_v0.8.0.log", "docs/evidence/test_run_v0.9.0.log", "docs/evidence/test_run_v0.10.0.log", "docs/evidence/test_run_v0.10.1.log", "docs/evidence/test_run_v0.11.0.log", "docs/billing.md", "history/v0.10.1/VERSION", "docs/evidence/test_run_v0.11.0.log", "history/v0.10.0/test_run_v0.10.0.log", "history/v0.10.1/test_run_v0.10.1.log", "history/v0.9.0/test_run_v0.9.0.log", "history/v0.8.0/test_run_v0.8.0.log", "history/v0.7.0/test_run_v0.7.0.log"}
SECRET_PATTERNS = [re.compile(p) for p in (
    r"-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----", r"AKIA[0-9A-Z]{16}", r"sk_live_[0-9a-zA-Z]{16,}", r"xox[baprs]-[0-9A-Za-z-]{10,}",
    r"ghp_[0-9A-Za-z]{30,}", r"sk-ant-[0-9A-Za-z_-]{20,}")]
REQUIRED = ["README.md", "FINAL_RELEASE_AUDIT.md", "RELEASE_NOTES.md", "CHANGELOG.md", "DEPLOYMENT_CHECKLIST.md", "PRODUCTION_READINESS.md",
            "SECURITY_AUDIT.md", "LGPD_AUDIT.md", "THIRD_PARTY_DEPENDENCIES.md", "IP_REGISTER.md", "CLAUDE_HANDOFF_FINAL.md", "ENVIRONMENT_SETUP.md",
            "DECISIONS.md", "VERSIONING.md", ".env.example", "VERSION",
            "SOLUTION_LIBRARY.md", "SOLUTION_SEARCH.md", "SOLUTION_MATCH_ENGINE.md", "REPLICATION_ENGINE.md", "INTENT_ENGINE.md", "AI_SEARCH_ARCHITECTURE.md",
            "SOLUTION_DATA_MODEL.md", "API_DOCUMENTATION.md", "TEST_REPORT.md", "docs/evidence/test_run_v0.9.0.log", "docs/evidence/search_perf_v0.9.0.json",
            "docs/evidence/weights_sensitivity_v0.9.0.json",
            "docs/evidence/test_run_v0.10.0.log", "docs/evidence/test_run_v0.10.1.log", "config/formalization_path.json", "history/v0.10.0/VERSION", "THIRD_SECTOR_MODEL.md", "INSTITUTIONAL_ELIGIBILITY_ENGINE.md", "FISCAL_RULE_ENGINE.md", "MATCH_ENGINE.md",
            "REPOSITORY_PROJECTS.md", "DATABASE_SCHEMA.md", "config/institutional_rules.candidates.json", "history/v0.9.0/VERSION"]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect() -> list[Path]:
    files = []
    for p in sorted(ROOT.rglob("*")):
        if p.is_symlink() or not p.is_file():
            continue
        rel = p.relative_to(ROOT)
        if rel.as_posix() in KEEP_EXACT:
            files.append(p)
            continue
        if set(rel.parts[:-1]) & EXCLUDE_DIRS and not (rel.parts[0] == "web" and rel.parts[1] == "dist"):
            continue
        if p.name in EXCLUDE_NAMES or p.suffix in EXCLUDE_SUFFIX:
            continue
        files.append(p)
    return files


def scan_secrets(files: list[Path]) -> list[str]:
    hits = []
    for p in files:
        if p.stat().st_size > 5_000_000:
            continue
        try:
            text = p.read_text("utf-8", errors="ignore").replace("AKIA" + "IOSFODNN7EXAMPLE", "")   # chave de EXEMPLO pública da documentação AWS (vetor SigV4)
        except OSError:
            continue
        for rx in SECRET_PATTERNS:
            if rx.search(text):
                hits.append(f"{p.relative_to(ROOT)}: {rx.pattern}")
    return hits


def build() -> int:
    version = (ROOT / "VERSION").read_text().strip()
    files = collect()
    missing = [r for r in REQUIRED if not (ROOT / r).exists()]
    if missing:
        print("Arquivos obrigatórios ausentes:", ", ".join(missing), file=sys.stderr)
        return 2
    if not (ROOT / "web/dist/index.html").exists():
        print("web/dist ausente — rode `make web` antes.", file=sys.stderr)
        return 2
    nested = [p for p in ROOT.rglob("*.zip") if "node_modules" not in p.parts and "dist-release" not in p.parts]
    if nested:
        print("ZIP aninhado encontrado (proibido):", nested, file=sys.stderr)
        return 2
    hits = scan_secrets(files)
    if hits:
        print("Possíveis segredos encontrados — release abortado:\n  " + "\n  ".join(hits), file=sys.stderr)
        return 2
    OUT.mkdir(exist_ok=True)
    rows = []
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        st = p.stat()
        rows.append((sha256(p), rel, st.st_size, dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")))
    manifest = "".join(f"{h}  {rel}\n" for h, rel, _, _ in rows)
    (ROOT / "RELEASE_MANIFEST.sha256").write_text(manifest)
    with (ROOT / "RELEASE_MANIFEST.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sha256", "file", "size_bytes", "mtime_utc"])
        w.writerows(rows)
    top = f"plataforma-impacto-v{version}"
    zpath = OUT / "FINAL_FULL_RELEASE.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for p in files + [ROOT / "RELEASE_MANIFEST.sha256", ROOT / "RELEASE_MANIFEST.csv"]:
            z.write(p, f"{top}/{p.relative_to(ROOT).as_posix()}")
    zsha = sha256(zpath)
    (OUT / "FINAL_FULL_RELEASE.zip.sha256").write_text(f"{zsha}  FINAL_FULL_RELEASE.zip\n")
    print(f"{len(files)} arquivos · zip {zpath.stat().st_size / 1e6:.2f} MB · sha256 {zsha}")
    return 0


def verify(d: Path) -> int:
    mf = d / "RELEASE_MANIFEST.sha256"
    if not mf.exists():
        print("RELEASE_MANIFEST.sha256 não encontrado em", d, file=sys.stderr)
        return 2
    bad = 0
    listed = set()
    for line in mf.read_text().splitlines():
        h, rel = line.split("  ", 1)
        listed.add(rel)
        p = d / rel
        if not p.exists():
            print("FALTA ", rel)
            bad += 1
        elif sha256(p) != h:
            print("DIFERE", rel)
            bad += 1
    zips = [p for p in d.rglob("*.zip")]
    if zips:
        print("ZIP aninhado:", zips)
        bad += 1
    print(f"{len(listed)} arquivos verificados · {'OK' if not bad else f'{bad} problema(s)'}")
    return 1 if bad else 0


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "--verify":
        sys.exit(verify(Path(sys.argv[2] if len(sys.argv) > 2 else ".")))
    sys.exit(build())
