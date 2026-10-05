#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"; mkdir -p "$ROOT/data"; PYTHONPATH="$ROOT" python3 "$ROOT/src/impacto/app.py"
