#!/bin/sh
# Banco NOVO com o mesmo desenho do Supabase (v0.25.0), executado uma vez na criação do volume:
#   - o administrador do projeto NÃO é superusuário: só LOGIN + CREATEROLE (como `postgres` no Supabase);
#   - o pgcrypto mora no esquema `extensions`, criado por quem tem privilégio (como `supabase_admin`);
#   - o administrador recebe USAGE em `extensions` COM GRANT OPTION, para repassar ao impacto_app.
# O superusuário da imagem só existe aqui dentro, para este passo; a aplicação nunca o usa.
set -eu
: "${IMPACTO_ADMIN_PASSWORD:?defina IMPACTO_ADMIN_PASSWORD}"
psql -v ON_ERROR_STOP=1 -U postgres -v senha="$IMPACTO_ADMIN_PASSWORD" <<'SQL'
CREATE ROLE impacto_admin LOGIN CREATEROLE NOSUPERUSER NOCREATEDB NOBYPASSRLS PASSWORD :'senha';
CREATE DATABASE impacto OWNER impacto_admin;
\c impacto
CREATE SCHEMA extensions;
CREATE EXTENSION pgcrypto WITH SCHEMA extensions;
GRANT USAGE ON SCHEMA extensions TO impacto_admin WITH GRANT OPTION;
SQL
