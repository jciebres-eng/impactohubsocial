-- bootstrap.sql — executar UMA vez por um superusuário/DBA (fora do repositório de segredos).
-- Cria os papéis com privilégio mínimo. Defina as senhas via psql: \password impacto_owner / impacto_app
-- Uso: psql "$ADMIN_DATABASE_URL" -v db=impacto -f infra/db/bootstrap.sql
\set ON_ERROR_STOP on
SELECT 'CREATE ROLE impacto_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'impacto_owner') \gexec
SELECT 'CREATE ROLE impacto_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS NOINHERIT'
 WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'impacto_app') \gexec
SELECT format('CREATE DATABASE %I OWNER impacto_owner ENCODING ''UTF8''', :'db')
 WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \gexec
\c :db
-- pgcrypto e citext exigem privilégio para criar; o DBA cria uma vez.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
ALTER SCHEMA public OWNER TO impacto_owner;
REVOKE ALL ON DATABASE :"db" FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE :"db" TO impacto_app;
GRANT CONNECT ON DATABASE :"db" TO impacto_owner;
