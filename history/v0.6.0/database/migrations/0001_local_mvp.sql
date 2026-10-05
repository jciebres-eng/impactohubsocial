-- Referência do modelo mínimo do MVP local. A aplicação cria as tabelas idempotentemente em SQLite.
-- Para produção, converter para PostgreSQL, adicionar tenant isolation/RLS, migrations forward-only e revisão de índices.
CREATE TABLE organizations (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, compliance_status TEXT NOT NULL DEFAULT 'pending', created_at TEXT NOT NULL);
CREATE TABLE users (id TEXT PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, role TEXT NOT NULL, org_id TEXT NOT NULL REFERENCES organizations(id), created_at TEXT NOT NULL);
CREATE TABLE programs (id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), name TEXT NOT NULL, cause TEXT NOT NULL, territory TEXT NOT NULL, budget_cents INTEGER NOT NULL, status TEXT NOT NULL, criteria_version TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE opportunities (id TEXT PRIMARY KEY, org_id TEXT NOT NULL REFERENCES organizations(id), program_id TEXT NOT NULL REFERENCES programs(id), title TEXT NOT NULL, description TEXT NOT NULL, requested_cents INTEGER NOT NULL, territory TEXT NOT NULL, cause TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
