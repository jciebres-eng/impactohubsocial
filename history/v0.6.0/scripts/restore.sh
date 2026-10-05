#!/usr/bin/env bash
set -euo pipefail
SRC="${1:?uso: restore.sh backup.sqlite3 destino.sqlite3}"
DST="${2:?uso: restore.sh backup.sqlite3 destino.sqlite3}"
python3 - "$SRC" "$DST" <<'PY'
import sqlite3, sys, pathlib
src,dst=sys.argv[1:]
if not pathlib.Path(src).exists(): raise SystemExit('backup inexistente')
a=sqlite3.connect(src); b=sqlite3.connect(dst); a.backup(b); result=b.execute('PRAGMA integrity_check').fetchone()[0]; b.close(); a.close()
if result!='ok': raise SystemExit('integrity_check falhou: '+result)
print('restore=ok integrity_check=ok')
PY
