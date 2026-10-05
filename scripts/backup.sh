#!/usr/bin/env bash
# Backup lógico (pg_dump formato custom) + SHA-256. Use com PostgreSQL gerenciado como camada ADICIONAL ao PITR do provedor.
# Uso: BACKUP_DATABASE_URL=postgresql://impacto_owner:...@host/impacto scripts/backup.sh /caminho/backups
set -euo pipefail
: "${BACKUP_DATABASE_URL:?defina BACKUP_DATABASE_URL}"
DEST="${1:-./backups}"; mkdir -p "$DEST"
F="$DEST/impacto-$(date -u +%Y%m%dT%H%M%SZ).dump"
pg_dump --format=custom --no-owner --no-privileges "$BACKUP_DATABASE_URL" -f "$F"
sha256sum "$F" > "$F.sha256"
echo "backup: $F"
# Arquivos (storage local): faça snapshot do volume ou use versionamento do bucket S3.
