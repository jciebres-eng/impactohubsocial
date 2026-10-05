-- PostgreSQL production baseline. Execute only through reviewed migrations.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS organizations(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, kind text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS programs(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), org_id uuid NOT NULL REFERENCES organizations(id), name text NOT NULL, cause text NOT NULL, territory text NOT NULL, budget_cents bigint NOT NULL CHECK (budget_cents>=0), status text NOT NULL, criteria_version text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
ALTER TABLE programs ENABLE ROW LEVEL SECURITY;
ALTER TABLE programs FORCE ROW LEVEL SECURITY;
CREATE POLICY programs_tenant_isolation ON programs USING (org_id = nullif(current_setting('app.org_id', true),'')::uuid) WITH CHECK (org_id = nullif(current_setting('app.org_id', true),'')::uuid);
REVOKE ALL ON programs FROM PUBLIC;
-- Every request transaction must SET LOCAL app.org_id = '<tenant uuid>' after verified auth.
