#!/usr/bin/env bash
# Executado UMA vez na criação do volume do Postgres (imagem oficial).
set -euo pipefail
psql -v ON_ERROR_STOP=1 -U postgres -v db=impacto -f /bootstrap/bootstrap.sql
psql -v ON_ERROR_STOP=1 -U postgres -c "ALTER ROLE impacto_owner PASSWORD '${IMPACTO_OWNER_PASSWORD}'; ALTER ROLE impacto_app PASSWORD '${IMPACTO_APP_PASSWORD}';"
