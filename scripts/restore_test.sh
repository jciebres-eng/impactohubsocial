#!/usr/bin/env bash
# Teste de restauração em banco DESCARTÁVEL: verifica hash, restaura, confere migrations e a integridade das cadeias de hash.
# Uso: ADMIN_DATABASE_URL=postgresql://postgres@host/postgres scripts/restore_test.sh backups/impacto-....dump
set -euo pipefail
: "${ADMIN_DATABASE_URL:?defina ADMIN_DATABASE_URL}"; F="$1"
sha256sum -c "$F.sha256"
DB="impacto_restore_$(date +%s)"
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 -q -c "CREATE DATABASE $DB OWNER impacto_owner"
TARGET="${ADMIN_DATABASE_URL%/*}/$DB"
pg_restore --no-owner --role=impacto_owner -d "$TARGET" "$F"
psql "$TARGET" -tA -c "SELECT count(*) || ' migrations' FROM schema_migrations"
BROKEN=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT p.id FROM projects p CROSS JOIN LATERAL ledger_verify(p.id) v WHERE NOT v.valid")
AUDIT=$(psql "$TARGET" -v ON_ERROR_STOP=1 -tA -c "SELECT count(*) FROM (SELECT DISTINCT org_id FROM audit_events) o CROSS JOIN LATERAL audit_verify(o.org_id) v WHERE NOT v.valid")
if [ -n "$BROKEN" ] || [ "$AUDIT" != "0" ]; then echo "FALHA: cadeia de hash inconsistente ($BROKEN / audit=$AUDIT)"; exit 1; fi
echo "ledger e auditoria íntegros"
psql "$ADMIN_DATABASE_URL" -q -c "DROP DATABASE $DB WITH (FORCE)"
echo "restore OK"
