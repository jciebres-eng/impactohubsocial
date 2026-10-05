#!/usr/bin/env bash
set -euo pipefail
DB="${IMPACTO_DB:-./data/impacto.sqlite3}"
OUT="${1:-./backups/impacto-$(date -u +%Y%m%dT%H%M%SZ).sqlite3}"
mkdir -p "$(dirname "$OUT")"
python3 - "$DB" "$OUT" <<'PY'
import sqlite3, sys, pathlib, hashlib
src,dst=sys.argv[1:]
pathlib.Path(dst).parent.mkdir(parents=True,exist_ok=True)
a=sqlite3.connect(src); b=sqlite3.connect(dst)
a.backup(b); b.execute('PRAGMA integrity_check'); b.commit(); b.close(); a.close()
print(f'backup={dst} sha256={hashlib.sha256(pathlib.Path(dst).read_bytes()).hexdigest()}')
PY
