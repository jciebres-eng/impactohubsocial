-- RASCUNHO v0.1 — NAO EXECUTADO, NAO TESTADO. Subconjunto: tenancy, billing, vouchers, auditoria.
-- Validar em banco descartavel (PostgreSQL) antes de qualquer uso. Moeda em centavos.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE tenant (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), name text NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE organization (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id uuid REFERENCES tenant(id),
  kind text NOT NULL CHECK (kind IN ('funder','osc','provider')),
  legal_name text NOT NULL, tax_id text, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE app_user (id uuid PRIMARY KEY DEFAULT gen_random_uuid(), email text UNIQUE NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE membership (user_id uuid REFERENCES app_user(id), organization_id uuid REFERENCES organization(id),
  role text NOT NULL, PRIMARY KEY (user_id, organization_id));

-- Planos versionados e imutaveis
CREATE TABLE plan_version (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), plan_key text NOT NULL, version text NOT NULL,
  role text NOT NULL CHECK (role IN ('funder','osc','provider')),
  price_cents bigint, currency char(3) DEFAULT 'BRL', definition jsonb NOT NULL,
  UNIQUE (plan_key, version));

CREATE TABLE subscription (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES organization(id),
  plan_version_id uuid NOT NULL REFERENCES plan_version(id),
  status text NOT NULL CHECK (status IN ('trialing','active','past_due','canceled','expired')),
  current_period_end timestamptz, external_ref text, created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE voucher_batch (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), campaign text, created_by uuid NOT NULL REFERENCES app_user(id),
  approved_by uuid REFERENCES app_user(id), created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE voucher (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), batch_id uuid REFERENCES voucher_batch(id),
  code_hash bytea UNIQUE NOT NULL, code_hint text,
  type text NOT NULL CHECK (type IN ('percent_off','amount_off','free_period','grant_plan','grant_feature')),
  value jsonb NOT NULL, scope jsonb NOT NULL DEFAULT '{}',
  max_redemptions int NOT NULL CHECK (max_redemptions > 0), redeemed_count int NOT NULL DEFAULT 0,
  per_org_limit int NOT NULL DEFAULT 1, stackable boolean NOT NULL DEFAULT false,
  valid_from timestamptz, valid_until timestamptz,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_approval','active','paused','revoked','exhausted','expired')),
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (redeemed_count <= max_redemptions));

CREATE TABLE voucher_redemption (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), voucher_id uuid NOT NULL REFERENCES voucher(id),
  organization_id uuid NOT NULL REFERENCES organization(id), redeemed_by uuid NOT NULL REFERENCES app_user(id),
  redeemed_at timestamptz NOT NULL DEFAULT now(), idempotency_key text,
  UNIQUE (voucher_id, organization_id));  -- per_org_limit=1 por padrao; ajustar se per_org_limit>1

CREATE TABLE entitlement_grant (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(), organization_id uuid NOT NULL REFERENCES organization(id),
  feature_key text NOT NULL, limits jsonb, source text NOT NULL CHECK (source IN ('plan','voucher','flag','admin')),
  source_ref uuid, starts_at timestamptz NOT NULL DEFAULT now(), ends_at timestamptz);

-- Auditoria encadeada por hash (append-only)
CREATE TABLE audit_event (
  id bigserial PRIMARY KEY, tenant_id uuid, actor_id uuid, action text NOT NULL,
  object_type text, object_id uuid, payload_hash bytea NOT NULL, prev_hash bytea, event_hash bytea NOT NULL,
  at timestamptz NOT NULL DEFAULT now());
REVOKE UPDATE, DELETE ON audit_event FROM PUBLIC;

-- Exemplo de RLS (aplicar a todas as tabelas com tenant_id)
-- ALTER TABLE organization ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY tenant_isolation ON organization USING (tenant_id = current_setting('app.tenant_id')::uuid);
-- Obs.: provider nao possui coluna de plano/impulsionamento em nenhuma tabela de busca (ADR-007).
