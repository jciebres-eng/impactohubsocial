#!/usr/bin/env bash
# Recria um banco de desenvolvimento/teste do zero (NUNCA usar em produção).
# Requer: ADMIN_DATABASE_URL (superusuário local), DB_NAME, OWNER_PASSWORD, APP_PASSWORD.
set -euo pipefail
: "${ADMIN_DATABASE_URL:?defina ADMIN_DATABASE_URL}"; : "${DB_NAME:=impacto_dev}"
: "${OWNER_PASSWORD:=owner_dev_pw}"; : "${APP_PASSWORD:=app_dev_pw}"
case "$DB_NAME" in *prod*) echo "recusado: nome de banco parece produção" >&2; exit 1;; esac
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -q -c "DROP DATABASE IF EXISTS \"$DB_NAME\" WITH (FORCE)"
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -q -v db="$DB_NAME" -f "$ROOT/infra/db/bootstrap.sql"
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -q -c "ALTER ROLE impacto_owner PASSWORD '$OWNER_PASSWORD'; ALTER ROLE impacto_app PASSWORD '$APP_PASSWORD';"
HOSTPART=$(python3 -c "import sys,urllib.parse as u;p=u.urlparse(sys.argv[1]);print(f'host={p.hostname or \"127.0.0.1\"} port={p.port or 5432}')" "$ADMIN_DATABASE_URL")
cd "$ROOT/backend" && MIGRATION_DATABASE_URL="$HOSTPART dbname=$DB_NAME user=impacto_owner password=$OWNER_PASSWORD" python3 -m impacto.db.migrate
echo "DATABASE_URL=\"$HOSTPART dbname=$DB_NAME user=impacto_app password=$APP_PASSWORD\""
