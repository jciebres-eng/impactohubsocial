-- 0001_schema.sql — Esquema base da Plataforma Impacto (PostgreSQL 16+)
-- Executado pelo papel dono (impacto_owner) via scripts/migrate.py. Forward-only.
-- Convenções: dinheiro em centavos (bigint), timestamps em timestamptz (UTC), ids uuid.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- ===========================================================================================
-- Identidade e tenancy
-- ===========================================================================================
CREATE TABLE organizations (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind               text NOT NULL CHECK (kind IN ('osc','company','provider','government','platform')),
  legal_name         text NOT NULL CHECK (length(legal_name) BETWEEN 2 AND 200),
  trade_name         text CHECK (length(trade_name) <= 200),
  cnpj               char(14) UNIQUE CHECK (cnpj ~ '^[0-9]{14}$'),
  legal_nature       text CHECK (length(legal_nature) <= 120),
  founded_on         date,
  description        text CHECK (length(description) <= 5000),
  website            text CHECK (length(website) <= 300),
  contact_email      citext,
  phone              text CHECK (length(phone) <= 40),
  city               text CHECK (length(city) <= 120),
  uf                 char(2) CHECK (uf ~ '^[A-Z]{2}$'),
  ibge_code          char(7) CHECK (ibge_code ~ '^[0-9]{7}$'),
  territories        text[] NOT NULL DEFAULT '{}',
  causes             text[] NOT NULL DEFAULT '{}',
  ods                smallint[] NOT NULL DEFAULT '{}',
  esg_focus          text[] NOT NULL DEFAULT '{}',
  certifications     text[] NOT NULL DEFAULT '{}',   -- ex.: CEBAS, OSCIP, utilidade_publica_municipal
  team_size          integer CHECK (team_size >= 0),
  annual_revenue_cents bigint CHECK (annual_revenue_cents >= 0),
  status             text NOT NULL DEFAULT 'active' CHECK (status IN ('active','suspended','closed')),
  compliance_status  text NOT NULL DEFAULT 'pending' CHECK (compliance_status IN ('pending','in_review','approved','rejected','suspended')),
  compliance_risk    text CHECK (compliance_risk IN ('low','medium','high')),
  compliance_reviewed_at timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_org_kind ON organizations(kind) WHERE status = 'active';
CREATE INDEX ix_org_causes ON organizations USING gin(causes);

CREATE TABLE users (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email              citext NOT NULL UNIQUE CHECK (length(email) <= 254 AND email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$'),
  full_name          text NOT NULL CHECK (length(full_name) BETWEEN 1 AND 160),
  password_hash      text,
  oidc_subject       text UNIQUE,
  email_verified_at  timestamptz,
  status             text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','deleted')),
  is_platform_admin  boolean NOT NULL DEFAULT false,
  mfa_secret_enc     text,
  mfa_enabled_at     timestamptz,
  mfa_recovery_hashes text[] NOT NULL DEFAULT '{}',
  failed_login_count integer NOT NULL DEFAULT 0,
  locked_until       timestamptz,
  last_login_at      timestamptz,
  locale             text NOT NULL DEFAULT 'pt-BR',
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE memberships (
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  role       text NOT NULL CHECK (role IN ('owner','admin','manager','analyst','member','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, org_id)
);
CREATE INDEX ix_membership_org ON memberships(org_id);

CREATE TABLE invitations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email       citext NOT NULL,
  role        text NOT NULL CHECK (role IN ('admin','manager','analyst','member','viewer')),
  token_hash  char(64) NOT NULL UNIQUE,
  invited_by  uuid NOT NULL REFERENCES users(id),
  expires_at  timestamptz NOT NULL,
  accepted_at timestamptz,
  revoked_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_invitation_org ON invitations(org_id);

CREATE TABLE sessions (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id             uuid REFERENCES organizations(id) ON DELETE SET NULL,
  family_id          uuid NOT NULL,
  access_hash        char(64) NOT NULL UNIQUE,
  access_expires_at  timestamptz NOT NULL,
  refresh_hash       char(64) NOT NULL UNIQUE,
  refresh_expires_at timestamptz NOT NULL,
  rotated_at         timestamptz,
  revoked_at         timestamptz,
  revoke_reason      text,
  mfa_verified       boolean NOT NULL DEFAULT false,
  ip                 text,
  user_agent         text,
  created_at         timestamptz NOT NULL DEFAULT now(),
  last_seen_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_session_user ON sessions(user_id) WHERE revoked_at IS NULL;
CREATE INDEX ix_session_family ON sessions(family_id);

CREATE TABLE auth_tokens (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose     text NOT NULL CHECK (purpose IN ('verify_email','reset_password','mfa_challenge')),
  token_hash  char(64) NOT NULL UNIQUE,
  expires_at  timestamptz NOT NULL,
  used_at     timestamptz,
  attempts    integer NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_auth_tokens_user ON auth_tokens(user_id, purpose);

CREATE TABLE rate_events (
  id      bigserial PRIMARY KEY,
  bucket  text NOT NULL,
  key     text NOT NULL,
  at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_rate_events ON rate_events(bucket, key, at);

CREATE TABLE oidc_states (
  state_hash    char(64) PRIMARY KEY,
  nonce         text NOT NULL,
  code_verifier text NOT NULL,
  redirect_to   text NOT NULL DEFAULT '/',
  expires_at    timestamptz NOT NULL
);

CREATE TABLE consents (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('terms','privacy','marketing')),
  version     text NOT NULL,
  granted     boolean NOT NULL DEFAULT true,
  ip          text,
  at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_consents_user ON consents(user_id);

CREATE TABLE privacy_requests (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind         text NOT NULL CHECK (kind IN ('export','deletion','correction')),
  status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open','completed','rejected')),
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- ===========================================================================================
-- Perfis por tipo de organização
-- ===========================================================================================
CREATE TABLE funder_profiles (
  org_id                  uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  causes                  text[] NOT NULL DEFAULT '{}',
  ods                     smallint[] NOT NULL DEFAULT '{}',
  esg_focus               text[] NOT NULL DEFAULT '{}',
  territories             text[] NOT NULL DEFAULT '{}',
  excluded_causes         text[] NOT NULL DEFAULT '{}',
  excluded_territories    text[] NOT NULL DEFAULT '{}',
  ticket_min_cents        bigint CHECK (ticket_min_cents >= 0),
  ticket_max_cents        bigint CHECK (ticket_max_cents >= 0),
  annual_budget_cents     bigint CHECK (annual_budget_cents >= 0),
  required_document_types text[] NOT NULL DEFAULT '{}',
  min_org_age_months      integer CHECK (min_org_age_months >= 0),
  accepts_fractioning     boolean NOT NULL DEFAULT true,
  policies                text CHECK (length(policies) <= 5000),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  CHECK (ticket_min_cents IS NULL OR ticket_max_cents IS NULL OR ticket_min_cents <= ticket_max_cents)
);

CREATE TABLE provider_profiles (
  org_id             uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  services           text[] NOT NULL DEFAULT '{}',
  categories         text[] NOT NULL DEFAULT '{}',  -- contador, advogado, elaborador_projetos, auditor, avaliador_impacto ...
  remote             boolean NOT NULL DEFAULT true,
  territories        text[] NOT NULL DEFAULT '{}',
  languages          text[] NOT NULL DEFAULT '{pt-BR}',
  accessibility      text,
  price_info         text CHECK (length(price_info) <= 500),
  accepting_requests boolean NOT NULL DEFAULT true,
  updated_at         timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE professional_credentials (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  council             text NOT NULL CHECK (council ~ '^[A-Z]{2,8}$'),  -- CRC, OAB, CRA, CREA, CRP, CORECON...
  number              text NOT NULL CHECK (length(number) BETWEEN 1 AND 40),
  uf                  char(2) CHECK (uf ~ '^[A-Z]{2}$'),
  holder_name         text NOT NULL,
  valid_until         date,
  verification_status text NOT NULL DEFAULT 'self_declared'
                      CHECK (verification_status IN ('self_declared','document_submitted','verified','rejected','expired')),
  verification_note   text,
  verified_by         uuid REFERENCES users(id),
  verified_at         timestamptz,
  document_id         uuid,
  created_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (council, uf, number)
);
CREATE INDEX ix_cred_org ON professional_credentials(org_id);

-- ===========================================================================================
-- Catálogo de oportunidades: chamadas, editais, fundos e financiamentos
-- ===========================================================================================
CREATE TABLE call_sources (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name         text NOT NULL,
  kind         text NOT NULL CHECK (kind IN ('json_feed','csv_feed','rss')),
  url          text NOT NULL CHECK (url ~ '^https://'),
  sphere       text NOT NULL CHECK (sphere IN ('private','federal','state','municipal','local','international')),
  active       boolean NOT NULL DEFAULT false,
  terms_note   text,             -- registro da verificação de termos de uso/licença da fonte
  mapping      jsonb NOT NULL DEFAULT '{}',
  last_run_at  timestamptz,
  last_status  text,
  last_error   text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE calls (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  owner_org_id           uuid REFERENCES organizations(id) ON DELETE SET NULL,
  source_type            text NOT NULL CHECK (source_type IN ('platform','curated','government','imported')),
  source_id              uuid REFERENCES call_sources(id) ON DELETE SET NULL,
  source_reference       text,
  sphere                 text NOT NULL CHECK (sphere IN ('private','federal','state','municipal','local','international')),
  instrument             text NOT NULL CHECK (instrument IN ('grant','edital','fund','financing','prize','incentive_law','donation','other')),
  funder_name            text NOT NULL CHECK (length(funder_name) BETWEEN 2 AND 200),
  title                  text NOT NULL CHECK (length(title) BETWEEN 3 AND 300),
  summary                text CHECK (length(summary) <= 2000),
  description            text CHECK (length(description) <= 20000),
  url                    text CHECK (url IS NULL OR url ~ '^https?://'),
  causes                 text[] NOT NULL DEFAULT '{}',
  ods                    smallint[] NOT NULL DEFAULT '{}',
  territories            text[] NOT NULL DEFAULT '{}',
  eligible_org_types     text[] NOT NULL DEFAULT '{osc}',
  budget_total_cents     bigint CHECK (budget_total_cents >= 0),
  ticket_min_cents       bigint CHECK (ticket_min_cents >= 0),
  ticket_max_cents       bigint CHECK (ticket_max_cents >= 0),
  currency               char(3) NOT NULL DEFAULT 'BRL',
  counterpart_pct        numeric(5,2) CHECK (counterpart_pct BETWEEN 0 AND 100),
  min_org_age_months     integer CHECK (min_org_age_months >= 0),
  required_document_types text[] NOT NULL DEFAULT '{}',
  required_certifications text[] NOT NULL DEFAULT '{}',
  requirements           jsonb NOT NULL DEFAULT '[]',
  steps_template         jsonb NOT NULL DEFAULT '[]',
  opens_at               timestamptz,
  closes_at              timestamptz,
  status                 text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','open','closed','archived','suspended')),
  managed_on_platform    boolean NOT NULL DEFAULT false,
  weights                jsonb,
  criteria_version       text NOT NULL DEFAULT 'c1',
  is_example             boolean NOT NULL DEFAULT false,
  last_verified_at       timestamptz,
  verified_by            uuid REFERENCES users(id),
  created_by             uuid REFERENCES users(id),
  created_at             timestamptz NOT NULL DEFAULT now(),
  updated_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (ticket_min_cents IS NULL OR ticket_max_cents IS NULL OR ticket_min_cents <= ticket_max_cents),
  CHECK (opens_at IS NULL OR closes_at IS NULL OR opens_at <= closes_at),
  CHECK (source_type <> 'platform' OR owner_org_id IS NOT NULL),
  UNIQUE (source_id, source_reference)
);
CREATE INDEX ix_calls_status ON calls(status, closes_at);
CREATE INDEX ix_calls_owner ON calls(owner_org_id);
CREATE INDEX ix_calls_causes ON calls USING gin(causes);
CREATE INDEX ix_calls_territories ON calls USING gin(territories);

CREATE TABLE saved_searches (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name        text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  filters     jsonb NOT NULL DEFAULT '{}',
  notify      boolean NOT NULL DEFAULT true,
  frequency   text NOT NULL DEFAULT 'daily' CHECK (frequency IN ('instant','daily','weekly')),
  last_run_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_saved_search_org ON saved_searches(org_id);

CREATE TABLE saved_search_hits (
  search_id  uuid NOT NULL REFERENCES saved_searches(id) ON DELETE CASCADE,
  call_id    uuid NOT NULL REFERENCES calls(id) ON DELETE CASCADE,
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  score      numeric(5,2),
  notified_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (search_id, call_id)
);

CREATE TABLE notifications (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id     uuid REFERENCES users(id) ON DELETE CASCADE,
  kind        text NOT NULL,
  title       text NOT NULL CHECK (length(title) <= 200),
  body        text CHECK (length(body) <= 2000),
  link        text CHECK (link IS NULL OR link ~ '^/'),
  read_at     timestamptz,
  emailed_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_notifications_org ON notifications(org_id, created_at DESC);

CREATE TABLE materials (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  title        text NOT NULL CHECK (length(title) BETWEEN 3 AND 300),
  summary      text CHECK (length(summary) <= 3000),
  category     text NOT NULL CHECK (category IN ('guide','legislation','template','data','manual','training','other')),
  url          text CHECK (url IS NULL OR url ~ '^https?://'),
  document_id  uuid,
  territories  text[] NOT NULL DEFAULT '{}',
  causes       text[] NOT NULL DEFAULT '{}',
  status       text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
  published_at timestamptz,
  created_by   uuid REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- ===========================================================================================
-- Projetos financiáveis (OSC)
-- ===========================================================================================
CREATE TABLE projects (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  title                    text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  summary                  text CHECK (length(summary) <= 2000),
  problem                  text CHECK (length(problem) <= 8000),
  objectives               text CHECK (length(objectives) <= 8000),
  methodology              text CHECK (length(methodology) <= 12000),
  causes                   text[] NOT NULL DEFAULT '{}',
  ods                      smallint[] NOT NULL DEFAULT '{}',
  esg_tags                 text[] NOT NULL DEFAULT '{}',
  territory                text NOT NULL CHECK (territory ~ '^BR(-[A-Z]{2}(-[0-9]{7})?)?$|^[A-Z]{2}$'),
  beneficiaries_count      integer CHECK (beneficiaries_count >= 0),
  beneficiaries_description text CHECK (length(beneficiaries_description) <= 2000),
  budget_total_cents       bigint NOT NULL DEFAULT 0 CHECK (budget_total_cents >= 0),
  status                   text NOT NULL DEFAULT 'draft'
                           CHECK (status IN ('draft','published','funding','funded','in_execution','completed','cancelled')),
  visibility               text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','published')),
  urgency                  text NOT NULL DEFAULT 'medium' CHECK (urgency IN ('low','medium','high')),
  starts_on                date,
  ends_on                  date,
  indicators               jsonb NOT NULL DEFAULT '[]',
  ai_assisted              boolean NOT NULL DEFAULT false,
  published_at             timestamptz,
  created_by               uuid REFERENCES users(id),
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now(),
  CHECK (starts_on IS NULL OR ends_on IS NULL OR starts_on <= ends_on)
);
CREATE INDEX ix_projects_org ON projects(org_id, created_at DESC);
CREATE INDEX ix_projects_published ON projects(visibility, status) WHERE visibility = 'published';
CREATE INDEX ix_projects_causes ON projects USING gin(causes);

CREATE TABLE budget_items (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  description     text NOT NULL CHECK (length(description) BETWEEN 1 AND 300),
  category        text NOT NULL DEFAULT 'material' CHECK (category IN ('material','service','personnel','equipment','infrastructure','travel','administrative','other')),
  quantity        numeric(12,2) NOT NULL CHECK (quantity > 0),
  unit_cost_cents bigint NOT NULL CHECK (unit_cost_cents >= 0),
  total_cents     bigint GENERATED ALWAYS AS (round(quantity * unit_cost_cents)::bigint) STORED,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_budget_items_project ON budget_items(project_id);

CREATE TABLE milestones (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  seq           integer NOT NULL CHECK (seq >= 1),
  title         text NOT NULL CHECK (length(title) BETWEEN 2 AND 200),
  description   text CHECK (length(description) <= 4000),
  amount_cents  bigint NOT NULL CHECK (amount_cents >= 0),
  funded_cents  bigint NOT NULL DEFAULT 0 CHECK (funded_cents >= 0),
  due_on        date,
  status        text NOT NULL DEFAULT 'planned'
                CHECK (status IN ('planned','open','funded','in_progress','evidence_submitted','accepted','rejected')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, seq)
);

-- ===========================================================================================
-- Candidaturas (plataforma, interesse de financiador e acompanhamento de edital externo)
-- ===========================================================================================
CREATE TABLE applications (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  call_id           uuid REFERENCES calls(id) ON DELETE RESTRICT,
  project_id        uuid REFERENCES projects(id) ON DELETE RESTRICT,
  osc_org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  funder_org_id     uuid REFERENCES organizations(id) ON DELETE SET NULL,
  origin            text NOT NULL CHECK (origin IN ('osc_application','funder_interest','external_tracking')),
  status            text NOT NULL CHECK (status IN ('interest','draft','submitted','screening','due_diligence','approved','rejected',
                                                  'withdrawn','committed','in_execution','reporting','closed')),
  requested_cents   bigint CHECK (requested_cents >= 0),
  external_protocol text CHECK (length(external_protocol) <= 120),
  submitted_at      timestamptz,
  decided_at        timestamptz,
  decision_note     text CHECK (length(decision_note) <= 4000),
  created_by        uuid REFERENCES users(id),
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CHECK (call_id IS NOT NULL OR project_id IS NOT NULL),
  CHECK (origin <> 'external_tracking' OR funder_org_id IS NULL)
);
CREATE UNIQUE INDEX ux_application_active ON applications(coalesce(call_id, '00000000-0000-0000-0000-000000000000'::uuid),
       coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid), osc_org_id, coalesce(funder_org_id, '00000000-0000-0000-0000-000000000000'::uuid))
       WHERE status NOT IN ('withdrawn','rejected','closed');
CREATE INDEX ix_app_osc ON applications(osc_org_id, updated_at DESC);
CREATE INDEX ix_app_funder ON applications(funder_org_id, updated_at DESC);
CREATE INDEX ix_app_project ON applications(project_id);

CREATE TABLE application_steps (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id uuid NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  seq            integer NOT NULL,
  code           text NOT NULL,
  title          text NOT NULL CHECK (length(title) <= 200),
  description    text CHECK (length(description) <= 4000),
  kind           text NOT NULL CHECK (kind IN ('requirement','document','writing','review','signature','submission','followup')),
  status         text NOT NULL DEFAULT 'todo' CHECK (status IN ('todo','in_progress','done','blocked','not_applicable')),
  mandatory      boolean NOT NULL DEFAULT true,
  due_on         date,
  document_id    uuid,
  note           text CHECK (length(note) <= 2000),
  completed_at   timestamptz,
  completed_by   uuid REFERENCES users(id),
  UNIQUE (application_id, code)
);

CREATE TABLE application_transitions (
  id             bigserial PRIMARY KEY,
  application_id uuid NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  from_status    text,
  to_status      text NOT NULL,
  actor_user_id  uuid REFERENCES users(id),
  actor_org_id   uuid REFERENCES organizations(id),
  note           text CHECK (length(note) <= 2000),
  at             timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_app_transitions ON application_transitions(application_id, at);

CREATE TABLE conflict_declarations (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id uuid NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
  user_id        uuid NOT NULL REFERENCES users(id),
  org_id         uuid NOT NULL REFERENCES organizations(id),
  has_conflict   boolean NOT NULL,
  description    text CHECK (length(description) <= 2000),
  declared_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (application_id, user_id)
);

CREATE TABLE favorites (
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  created_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, project_id)
);

CREATE TABLE feed_feedback (
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  target_type text NOT NULL CHECK (target_type IN ('project','call')),
  target_id  uuid NOT NULL,
  action     text NOT NULL CHECK (action IN ('dismiss','save')),
  reason     text CHECK (length(reason) <= 300),
  created_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, target_type, target_id)
);

-- ===========================================================================================
-- Recursos: compromissos (sem custódia), despesas, evidências, devolutivas
-- ===========================================================================================
CREATE TABLE commitments (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  application_id uuid NOT NULL REFERENCES applications(id) ON DELETE RESTRICT,
  project_id     uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  milestone_id   uuid REFERENCES milestones(id) ON DELETE RESTRICT,
  funder_org_id  uuid NOT NULL REFERENCES organizations(id),
  osc_org_id     uuid NOT NULL REFERENCES organizations(id),
  amount_cents   bigint NOT NULL CHECK (amount_cents > 0),
  status         text NOT NULL DEFAULT 'pledged' CHECK (status IN ('pledged','disbursed','confirmed','cancelled')),
  reference      text CHECK (length(reference) <= 200),
  disbursed_at   timestamptz,
  confirmed_at   timestamptz,
  created_by     uuid REFERENCES users(id),
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_commitments_project ON commitments(project_id);
CREATE INDEX ix_commitments_funder ON commitments(funder_org_id);

CREATE TABLE expenses (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  org_id         uuid NOT NULL REFERENCES organizations(id),
  milestone_id   uuid REFERENCES milestones(id) ON DELETE SET NULL,
  commitment_id  uuid REFERENCES commitments(id) ON DELETE SET NULL,
  budget_item_id uuid REFERENCES budget_items(id) ON DELETE SET NULL,
  description    text NOT NULL CHECK (length(description) BETWEEN 2 AND 500),
  supplier_name  text CHECK (length(supplier_name) <= 200),
  supplier_cnpj  char(14) CHECK (supplier_cnpj ~ '^[0-9]{14}$'),
  amount_cents   bigint NOT NULL CHECK (amount_cents > 0),
  paid_on        date NOT NULL,
  document_id    uuid,
  status         text NOT NULL DEFAULT 'recorded' CHECK (status IN ('recorded','validated','questioned')),
  review_note    text CHECK (length(review_note) <= 2000),
  created_by     uuid REFERENCES users(id),
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_expenses_project ON expenses(project_id);

CREATE TABLE evidences (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  org_id          uuid NOT NULL REFERENCES organizations(id),
  milestone_id    uuid REFERENCES milestones(id) ON DELETE SET NULL,
  application_id  uuid REFERENCES applications(id) ON DELETE SET NULL,
  kind            text NOT NULL CHECK (kind IN ('photo','video','report','attendance','invoice','result','other')),
  title           text NOT NULL CHECK (length(title) BETWEEN 2 AND 200),
  description     text CHECK (length(description) <= 4000),
  occurred_on     date,
  document_id     uuid,
  indicator_name  text CHECK (length(indicator_name) <= 120),
  indicator_value numeric(14,2),
  status          text NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','accepted','rejected','needs_info')),
  reviewed_by_org uuid REFERENCES organizations(id),
  reviewed_by     uuid REFERENCES users(id),
  reviewed_at     timestamptz,
  review_note     text CHECK (length(review_note) <= 2000),
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_evidences_project ON evidences(project_id, created_at DESC);

CREATE TABLE feedbacks (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  application_id uuid REFERENCES applications(id) ON DELETE SET NULL,
  author_org_id  uuid NOT NULL REFERENCES organizations(id),
  author_user_id uuid REFERENCES users(id),
  kind           text NOT NULL CHECK (kind IN ('funder_feedback','progress_report','final_report')),
  body           text NOT NULL CHECK (length(body) BETWEEN 2 AND 8000),
  rating         smallint CHECK (rating BETWEEN 1 AND 5),
  document_id    uuid,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_feedbacks_project ON feedbacks(project_id, created_at DESC);

-- ===========================================================================================
-- Documentos, validação profissional e assinaturas
-- ===========================================================================================
CREATE TABLE documents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id    uuid REFERENCES projects(id) ON DELETE SET NULL,
  application_id uuid REFERENCES applications(id) ON DELETE SET NULL,
  doc_type      text NOT NULL CHECK (doc_type ~ '^[a-z0-9_]{2,60}$'),
  title         text NOT NULL CHECK (length(title) BETWEEN 1 AND 200),
  filename      text NOT NULL CHECK (length(filename) BETWEEN 1 AND 255),
  mime_type     text NOT NULL,
  size_bytes    bigint NOT NULL CHECK (size_bytes > 0),
  sha256        char(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  storage_key   text NOT NULL UNIQUE,
  status        text NOT NULL DEFAULT 'pending_scan' CHECK (status IN ('pending_scan','clean','infected','rejected')),
  scan_engine   text,
  scanned_at    timestamptz,
  valid_until   date,
  visibility    text NOT NULL DEFAULT 'private' CHECK (visibility IN ('private','parties','public')),
  version       integer NOT NULL DEFAULT 1,
  supersedes_id uuid REFERENCES documents(id),
  origin        text NOT NULL DEFAULT 'upload' CHECK (origin IN ('upload','ai_draft','generated')),
  extracted_text text,
  uploaded_by   uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);
CREATE INDEX ix_documents_org ON documents(org_id, created_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX ix_documents_project ON documents(project_id) WHERE deleted_at IS NULL;

ALTER TABLE professional_credentials ADD CONSTRAINT fk_cred_doc FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;
ALTER TABLE materials ADD CONSTRAINT fk_material_doc FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;
ALTER TABLE application_steps ADD CONSTRAINT fk_step_doc FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;
ALTER TABLE expenses ADD CONSTRAINT fk_expense_doc FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;
ALTER TABLE evidences ADD CONSTRAINT fk_evidence_doc FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;
ALTER TABLE feedbacks ADD CONSTRAINT fk_feedback_doc FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;

CREATE TABLE drafts (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id   uuid REFERENCES projects(id) ON DELETE CASCADE,
  application_id uuid REFERENCES applications(id) ON DELETE CASCADE,
  kind         text NOT NULL CHECK (kind IN ('project_proposal','work_plan','budget_justification','cover_letter','progress_report','final_report','other')),
  title        text NOT NULL CHECK (length(title) BETWEEN 2 AND 200),
  content      text NOT NULL CHECK (length(content) <= 100000),
  content_sha256 char(64) NOT NULL,
  version      integer NOT NULL DEFAULT 1,
  ai_assisted  boolean NOT NULL DEFAULT false,
  status       text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','in_review','approved','signed','superseded')),
  created_by   uuid REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_drafts_org ON drafts(org_id, updated_at DESC);

CREATE TABLE professional_reviews (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id               uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  professional_org_id  uuid NOT NULL REFERENCES organizations(id),
  credential_id        uuid REFERENCES professional_credentials(id),
  subject_type         text NOT NULL CHECK (subject_type IN ('draft','document','application','project')),
  subject_id           uuid NOT NULL,
  subject_sha256       char(64),
  scope                text NOT NULL CHECK (length(scope) BETWEEN 3 AND 2000),
  status               text NOT NULL DEFAULT 'requested'
                       CHECK (status IN ('requested','accepted','declined','changes_requested','approved','signed','cancelled')),
  response_note        text CHECK (length(response_note) <= 4000),
  due_on               date,
  requested_by         uuid REFERENCES users(id),
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  CHECK (org_id <> professional_org_id)
);
CREATE INDEX ix_reviews_pro ON professional_reviews(professional_org_id, status);
CREATE INDEX ix_reviews_org ON professional_reviews(org_id, status);

CREATE TABLE signatures (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  review_id        uuid REFERENCES professional_reviews(id),
  subject_type     text NOT NULL CHECK (subject_type IN ('draft','document')),
  subject_id       uuid NOT NULL,
  subject_sha256   char(64) NOT NULL,
  signer_user_id   uuid NOT NULL REFERENCES users(id),
  signer_org_id    uuid NOT NULL REFERENCES organizations(id),
  credential_id    uuid REFERENCES professional_credentials(id),
  role             text NOT NULL CHECK (role IN ('professional','legal_representative','funder')),
  method           text NOT NULL DEFAULT 'platform_advanced' CHECK (method IN ('platform_advanced','icp_brasil','govbr')),
  statement        text NOT NULL CHECK (length(statement) BETWEEN 10 AND 2000),
  ip               text,
  user_agent       text,
  signature_hmac   char(64) NOT NULL,
  signed_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_signatures_subject ON signatures(subject_type, subject_id);

-- ===========================================================================================
-- Match, fiscal, compliance
-- ===========================================================================================
CREATE TABLE match_runs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  viewer_org_id   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  direction       text NOT NULL CHECK (direction IN ('funder_project','osc_call')),
  call_id         uuid REFERENCES calls(id) ON DELETE SET NULL,
  project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
  engine_version  text NOT NULL,
  weights_version text NOT NULL,
  eligibility     text NOT NULL CHECK (eligibility IN ('eligible','blocked','needs_review')),
  score           numeric(5,2),
  confidence      numeric(5,2) NOT NULL,
  result          jsonb NOT NULL,
  features        jsonb NOT NULL,
  outcome         text,             -- rótulo futuro p/ treino (ex.: shortlisted, approved, rejected)
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_match_runs_viewer ON match_runs(viewer_org_id, created_at DESC);

CREATE TABLE fiscal_rules (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code                 text NOT NULL CHECK (code ~ '^[A-Z0-9-]{3,60}$'),
  version              text NOT NULL,
  name                 text NOT NULL,
  mechanism            text NOT NULL,
  jurisdiction         text NOT NULL CHECK (jurisdiction IN ('federal','state','municipal')),
  uf                   char(2),
  ibge_code            char(7),
  taxpayer_types       text[] NOT NULL DEFAULT '{pj}',
  taxpayer_regimes     text[] NOT NULL DEFAULT '{}',
  tax_base             text NOT NULL,
  limit_pct            numeric(6,3) CHECK (limit_pct >= 0 AND limit_pct <= 100),
  combined_limit_group text,
  limit_note           text,
  causes               text[] NOT NULL DEFAULT '{}',
  requirements         jsonb NOT NULL DEFAULT '[]',
  project_requirements jsonb NOT NULL DEFAULT '[]',
  effective_from       date,
  effective_to         date,
  source_citation      text NOT NULL,
  source_url           text,
  source_consulted_on  date,
  notes                text,
  status               text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_review','approved','retired')),
  created_by           uuid REFERENCES users(id),
  approved_by_1        uuid REFERENCES users(id),
  approved_by_2        uuid REFERENCES users(id),
  approved_at          timestamptz,
  created_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (code, version),
  CHECK (status <> 'approved' OR (approved_by_1 IS NOT NULL AND approved_by_2 IS NOT NULL AND approved_by_1 <> approved_by_2)),
  CHECK (effective_from IS NULL OR effective_to IS NULL OR effective_from <= effective_to)
);

CREATE TABLE company_tax_profiles (
  org_id                  uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  regime                  text NOT NULL DEFAULT 'unknown' CHECK (regime IN ('lucro_real','lucro_presumido','simples','isenta','unknown')),
  fiscal_year             integer CHECK (fiscal_year BETWEEN 2000 AND 2100),
  estimated_ir_due_cents  bigint CHECK (estimated_ir_due_cents >= 0),
  uf                      char(2),
  ibge_code               char(7),
  updated_by              uuid REFERENCES users(id),
  updated_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE compliance_checks (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  check_type  text NOT NULL,
  status      text NOT NULL CHECK (status IN ('pass','fail','warning','pending','error','not_configured')),
  details     jsonb NOT NULL DEFAULT '{}',
  source      text NOT NULL,
  checked_by  uuid REFERENCES users(id),
  checked_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_compliance_checks_org ON compliance_checks(org_id, checked_at DESC);

CREATE TABLE compliance_reviews (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open','approved','rejected','info_requested')),
  risk_level    text CHECK (risk_level IN ('low','medium','high')),
  decision_note text CHECK (length(decision_note) <= 4000),
  reviewer_id   uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  decided_at    timestamptz
);
CREATE INDEX ix_compliance_reviews_status ON compliance_reviews(status, created_at);

-- ===========================================================================================
-- Billing, entitlements, vouchers, flags
-- ===========================================================================================
CREATE TABLE plans (
  plan_key      text PRIMARY KEY,
  version       text NOT NULL,
  role          text NOT NULL CHECK (role IN ('company','osc','provider','government')),
  name          text NOT NULL,
  price_cents   bigint,
  interval      text NOT NULL DEFAULT 'month' CHECK (interval IN ('month','year','custom')),
  limits        jsonb NOT NULL DEFAULT '{}',
  features      text[] NOT NULL DEFAULT '{}',
  requires_flag text,
  public        boolean NOT NULL DEFAULT true,
  active        boolean NOT NULL DEFAULT true,
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE subscriptions (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  plan_key                 text NOT NULL REFERENCES plans(plan_key),
  status                   text NOT NULL CHECK (status IN ('incomplete','trialing','active','past_due','canceled','expired')),
  provider                 text NOT NULL CHECK (provider IN ('stripe','manual','sandbox')),
  provider_customer_id     text,
  provider_subscription_id text UNIQUE,
  provider_checkout_id     text UNIQUE,
  current_period_end       timestamptz,
  cancel_at_period_end     boolean NOT NULL DEFAULT false,
  created_at               timestamptz NOT NULL DEFAULT now(),
  updated_at               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_subscriptions_org ON subscriptions(org_id, created_at DESC);

CREATE TABLE invoices (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id              uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  subscription_id     uuid REFERENCES subscriptions(id) ON DELETE SET NULL,
  provider            text NOT NULL CHECK (provider IN ('stripe','manual','sandbox')),
  provider_invoice_id text UNIQUE,
  description         text,
  amount_cents        bigint NOT NULL CHECK (amount_cents >= 0),
  currency            char(3) NOT NULL DEFAULT 'BRL',
  status              text NOT NULL CHECK (status IN ('draft','open','paid','void','uncollectible')),
  due_on              date,
  paid_at             timestamptz,
  payment_reference   text,
  hosted_url          text,
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_invoices_org ON invoices(org_id, created_at DESC);

CREATE TABLE billing_events (
  id           bigserial PRIMARY KEY,
  provider     text NOT NULL,
  event_id     text NOT NULL,
  type         text NOT NULL,
  payload      jsonb NOT NULL,
  status       text NOT NULL DEFAULT 'received' CHECK (status IN ('received','processed','ignored','failed')),
  error        text,
  received_at  timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz,
  UNIQUE (provider, event_id)
);

CREATE TABLE feature_flags (
  key         text PRIMARY KEY CHECK (key ~ '^[a-z0-9_]{2,60}$'),
  enabled     boolean NOT NULL DEFAULT false,
  description text,
  updated_by  uuid REFERENCES users(id),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE voucher_batches (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign    text NOT NULL CHECK (length(campaign) BETWEEN 2 AND 120),
  created_by  uuid NOT NULL REFERENCES users(id),
  approved_by uuid REFERENCES users(id),
  status      text NOT NULL DEFAULT 'pending_approval' CHECK (status IN ('pending_approval','active','revoked')),
  created_at  timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz,
  CHECK (approved_by IS NULL OR approved_by <> created_by)
);

CREATE TABLE vouchers (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id         uuid NOT NULL REFERENCES voucher_batches(id) ON DELETE CASCADE,
  code_hash        char(64) NOT NULL UNIQUE,
  code_hint        char(4) NOT NULL,
  type             text NOT NULL CHECK (type IN ('grant_plan','grant_feature','percent_off','amount_off','free_period')),
  plan_key         text REFERENCES plans(plan_key),
  feature_key      text,
  value            jsonb NOT NULL DEFAULT '{}',
  scope_roles      text[] NOT NULL DEFAULT '{}',
  scope_cnpj       char(14),
  duration_days    integer CHECK (duration_days > 0),
  max_redemptions  integer NOT NULL CHECK (max_redemptions > 0),
  redeemed_count   integer NOT NULL DEFAULT 0,
  valid_from       timestamptz,
  valid_until      timestamptz,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','revoked','exhausted')),
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (redeemed_count <= max_redemptions)
);

CREATE TABLE voucher_redemptions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  voucher_id  uuid NOT NULL REFERENCES vouchers(id),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  redeemed_by uuid NOT NULL REFERENCES users(id),
  redeemed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (voucher_id, org_id)
);

CREATE TABLE entitlement_grants (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  plan_key    text REFERENCES plans(plan_key),
  feature_key text,
  source      text NOT NULL CHECK (source IN ('voucher','admin')),
  source_ref  uuid,
  starts_at   timestamptz NOT NULL DEFAULT now(),
  ends_at     timestamptz,
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (plan_key IS NOT NULL OR feature_key IS NOT NULL)
);
CREATE INDEX ix_grants_org ON entitlement_grants(org_id);

-- ===========================================================================================
-- Denúncias, IA, auditoria, ledger, jobs
-- ===========================================================================================
CREATE TABLE reports (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_user_id uuid NOT NULL REFERENCES users(id),
  reporter_org_id  uuid REFERENCES organizations(id),
  target_type      text NOT NULL CHECK (target_type IN ('organization','project','call','document','user')),
  target_id        uuid NOT NULL,
  reason           text NOT NULL CHECK (reason IN ('fraud','inappropriate','incorrect_data','conflict','privacy','other')),
  details          text CHECK (length(details) <= 4000),
  status           text NOT NULL DEFAULT 'open' CHECK (status IN ('open','triaged','actioned','dismissed')),
  resolution       text CHECK (length(resolution) <= 4000),
  handled_by       uuid REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  resolved_at      timestamptz
);
CREATE INDEX ix_reports_status ON reports(status, created_at);

CREATE TABLE ai_usage (
  id           bigserial PRIMARY KEY,
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id      uuid REFERENCES users(id) ON DELETE SET NULL,
  feature      text NOT NULL,
  provider     text NOT NULL,
  model        text,
  status       text NOT NULL,
  input_chars  integer NOT NULL DEFAULT 0,
  output_chars integer NOT NULL DEFAULT 0,
  tokens_in    integer,
  tokens_out   integer,
  latency_ms   integer,
  input_sha256 char(64),
  redactions   integer NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_usage_org ON ai_usage(org_id, created_at);

CREATE TABLE chain_heads (
  chain_key text PRIMARY KEY,
  last_seq  bigint NOT NULL,
  last_hash char(64) NOT NULL
);

CREATE TABLE audit_events (
  id            bigserial PRIMARY KEY,
  org_id        uuid,
  actor_user_id uuid,
  action        text NOT NULL CHECK (action ~ '^[a-z_]+\.[a-z_.]+$'),
  object_type   text,
  object_id     text,
  ip            text,
  request_id    text,
  payload       jsonb NOT NULL DEFAULT '{}',
  seq           bigint,
  prev_hash     char(64),
  event_hash    char(64),
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_audit_org ON audit_events(org_id, id DESC);
CREATE INDEX ix_audit_action ON audit_events(action, at DESC);

CREATE TABLE ledger_entries (
  id            bigserial PRIMARY KEY,
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  org_id        uuid NOT NULL REFERENCES organizations(id),
  actor_user_id uuid REFERENCES users(id),
  entry_type    text NOT NULL CHECK (entry_type IN ('need_published','budget_defined','milestone_defined','interest_registered',
                    'application_submitted','application_approved','funding_committed','disbursement_reported','disbursement_confirmed',
                    'expense_recorded','evidence_submitted','evidence_reviewed','result_reported','report_submitted','feedback_given',
                    'professional_signature','project_completed')),
  amount_cents  bigint,
  ref_type      text,
  ref_id        uuid,
  payload       jsonb NOT NULL DEFAULT '{}',
  seq           bigint,
  prev_hash     char(64),
  entry_hash    char(64),
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ledger_project ON ledger_entries(project_id, seq);

CREATE TABLE job_runs (
  id          bigserial PRIMARY KEY,
  job         text NOT NULL,
  status      text NOT NULL CHECK (status IN ('running','ok','failed')),
  details     jsonb NOT NULL DEFAULT '{}',
  started_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
