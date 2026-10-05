#!/usr/bin/env bash
# Servidor de desenvolvimento. Requer DATABASE_URL (papel impacto_app) — ver scripts/dev_reset_db.sh
set -euo pipefail
cd "$(dirname "$0")"
exec python3 -m uvicorn "impacto.main:app" --host "${HOST:-127.0.0.1}" --port "${PORT:-8080}" --proxy-headers --no-server-header
