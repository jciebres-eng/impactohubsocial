-- 0004_v080_modules.sql — v0.8.0: financiador pessoa física, ODS/indicadores normalizados, Impact Graph, diagnóstico,
-- compras com cotações, risco/fraude, modelo de contribuição (com portão jurídico), estados de pagamento + reconciliação,
-- localização configurável, necessidades e ofertas de profissionais, rede (seguir/mensagens), erros agregados.
-- Forward-only. Toda tabela nova tem RLS (verificado em tests/test_architecture.py).

-- ===========================================================================================
-- 0. Tipos de organização e colunas novas
-- ===========================================================================================
ALTER TABLE organizations DROP CONSTRAINT organizations_kind_check;
ALTER TABLE organizations ADD CONSTRAINT organizations_kind_check
  CHECK (kind IN ('osc','company','provider','government','platform','individual'));
ALTER TABLE plans DROP CONSTRAINT plans_role_check;
ALTER TABLE plans ADD CONSTRAINT plans_role_check CHECK (role IN ('company','osc','provider','government','individual'));
ALTER TABLE funder_profiles ADD COLUMN public_name boolean NOT NULL DEFAULT false;  -- PF: nome visível às OSCs só com opt-in
ALTER TABLE reports DROP CONSTRAINT reports_target_type_check;
ALTER TABLE reports ADD CONSTRAINT reports_target_type_check
  CHECK (target_type IN ('organization','project','call','document','user','message'));

ALTER TABLE projects ADD COLUMN location_precision text NOT NULL DEFAULT 'municipality'
  CHECK (location_precision IN ('exact','approximate','neighborhood','municipality','region'));
ALTER TABLE projects ADD COLUMN lat numeric(8,5) CHECK (lat BETWEEN -90 AND 90);
ALTER TABLE projects ADD COLUMN lng numeric(8,5) CHECK (lng BETWEEN -180 AND 180);
ALTER TABLE projects ADD CONSTRAINT projects_latlng_pair CHECK ((lat IS NULL) = (lng IS NULL));

-- Nome de exibição de organização: pessoa física só aparece com opt-in (a própria organização sempre se vê).
CREATE FUNCTION org_display(p_org uuid) RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT CASE
    WHEN o.kind <> 'individual' THEN o.legal_name
    WHEN o.id = app_org() OR app_priv() OR coalesce(fp.public_name, false) THEN o.legal_name
    ELSE 'Apoiador pessoa física'
  END
  FROM organizations o LEFT JOIN funder_profiles fp ON fp.org_id = o.id WHERE o.id = p_org
$$;

ALTER TABLE ledger_entries DROP CONSTRAINT ledger_entries_entry_type_check;
ALTER TABLE ledger_entries ADD CONSTRAINT ledger_entries_entry_type_check CHECK (entry_type IN ('need_published','budget_defined','milestone_defined',
  'interest_registered','application_submitted','application_approved','funding_committed','disbursement_reported','disbursement_confirmed',
  'expense_recorded','evidence_submitted','evidence_reviewed','result_reported','report_submitted','feedback_given','professional_signature',
  'project_completed','refund_completed','payment_disputed','indicator_validated','procurement_decided'));

-- ===========================================================================================
-- 1. ODS normalizado, indicadores e ESG
-- ===========================================================================================
CREATE TABLE ods_goals (
  number smallint PRIMARY KEY CHECK (number BETWEEN 1 AND 17),
  name   text NOT NULL
);
CREATE TABLE ods_targets (
  code        text PRIMARY KEY CHECK (code ~ '^[0-9]{1,2}\.[0-9a-z]{1,2}$'),
  ods         smallint NOT NULL REFERENCES ods_goals(number),
  description text NOT NULL CHECK (length(description) <= 1000),
  source      text NOT NULL DEFAULT 'import',      -- origem da carga (ex.: publicação oficial da ONU/IBGE); nada é embutido sem fonte
  loaded_at   timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE indicator_catalog (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code          text NOT NULL UNIQUE CHECK (code ~ '^[a-z0-9_.-]{2,80}$'),
  name          text NOT NULL CHECK (length(name) BETWEEN 3 AND 200),
  unit          text NOT NULL CHECK (length(unit) BETWEEN 1 AND 40),
  definition    text CHECK (length(definition) <= 2000),
  esg_dimension text CHECK (esg_dimension IN ('E','S','G')),
  ods           smallint REFERENCES ods_goals(number),
  ods_target    text REFERENCES ods_targets(code),
  origin        text NOT NULL DEFAULT 'platform' CHECK (origin IN ('platform','official','org_defined')),
  org_id        uuid REFERENCES organizations(id) ON DELETE CASCADE,
  active        boolean NOT NULL DEFAULT true,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CHECK ((origin = 'org_defined') = (org_id IS NOT NULL))
);
CREATE TABLE project_ods_targets (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id       uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id           uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  ods              smallint NOT NULL REFERENCES ods_goals(number),
  target_code      text REFERENCES ods_targets(code),
  rationale        text CHECK (length(rationale) <= 2000),
  alignment_level  text NOT NULL DEFAULT 'declared' CHECK (alignment_level IN ('declared','supported_by_evidence','professionally_reviewed')),
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_project_ods ON project_ods_targets(project_id, ods, coalesce(target_code, ''));
CREATE TABLE project_indicators (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id   uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  indicator_id uuid NOT NULL REFERENCES indicator_catalog(id),
  baseline     numeric(18,4),
  target       numeric(18,4),
  target_date  date,
  method       text CHECK (length(method) <= 1000),   -- como será medido (fonte, periodicidade)
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, indicator_id)
);
CREATE TABLE indicator_values (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_indicator_id uuid NOT NULL REFERENCES project_indicators(id) ON DELETE CASCADE,
  project_id           uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id               uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  value                numeric(18,4) NOT NULL,
  measured_on          date NOT NULL,
  evidence_id          uuid REFERENCES evidences(id) ON DELETE SET NULL,
  status               text NOT NULL DEFAULT 'reported' CHECK (status IN ('reported','validated','rejected')),
  validated_by         uuid REFERENCES users(id),
  validated_by_org     uuid REFERENCES organizations(id),
  note                 text CHECK (length(note) <= 2000),
  created_by           uuid REFERENCES users(id),
  created_at           timestamptz NOT NULL DEFAULT now(),
  -- "validado" exige quem valida diferente de quem reportou (separação de funções)
  CHECK (status <> 'validated' OR (validated_by IS NOT NULL AND validated_by_org IS NOT NULL AND validated_by_org <> org_id))
);
CREATE INDEX ix_indicator_values ON indicator_values(project_indicator_id, measured_on DESC);

-- ===========================================================================================
-- 2. Impact Graph (tipos de ligação distintos: hipótese ≠ associação ≠ evidência ≠ causalidade validada)
-- ===========================================================================================
CREATE TABLE impact_nodes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('need','activity','output','outcome','impact','population','context')),
  label       text NOT NULL CHECK (length(label) BETWEEN 2 AND 200),
  description text CHECK (length(description) <= 2000),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_impact_nodes ON impact_nodes(project_id);
CREATE TABLE impact_edges (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id        uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id            uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  from_node         uuid NOT NULL REFERENCES impact_nodes(id) ON DELETE CASCADE,
  to_node           uuid NOT NULL REFERENCES impact_nodes(id) ON DELETE CASCADE,
  link_type         text NOT NULL DEFAULT 'hypothesis'
                    CHECK (link_type IN ('observed_evidence','correlation','hypothesis','association','inference','validated_causality')),
  evidence_id       uuid REFERENCES evidences(id) ON DELETE SET NULL,
  note              text CHECK (length(note) <= 2000),
  reviewed_by       uuid REFERENCES users(id),
  reviewed_by_org   uuid REFERENCES organizations(id),
  created_by        uuid REFERENCES users(id),
  created_at        timestamptz NOT NULL DEFAULT now(),
  CHECK (from_node <> to_node),
  CHECK (link_type <> 'observed_evidence' OR evidence_id IS NOT NULL),
  CHECK (link_type <> 'validated_causality' OR (evidence_id IS NOT NULL AND reviewed_by IS NOT NULL AND reviewed_by_org IS NOT NULL
                                                  AND reviewed_by_org <> org_id AND note IS NOT NULL))
);
CREATE INDEX ix_impact_edges ON impact_edges(project_id);

-- ===========================================================================================
-- 3. Diagnóstico estruturado da OSC
-- ===========================================================================================
CREATE TABLE diagnoses (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id       uuid REFERENCES projects(id) ON DELETE SET NULL,
  title            text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  need_statement   text CHECK (length(need_statement) <= 6000),
  affected_group   text CHECK (length(affected_group) <= 2000),   -- descrição agregada; sem dados pessoais
  root_causes      jsonb NOT NULL DEFAULT '[]',                   -- [{text, source, evidence_level}]
  objective        text CHECK (length(objective) <= 4000),
  goals            jsonb NOT NULL DEFAULT '[]',                   -- [{text, indicator_code, target, due}]
  action_plan      jsonb NOT NULL DEFAULT '[]',                   -- [{action, owner, start, end, budget_cents}]
  risks            jsonb NOT NULL DEFAULT '[]',
  data_sources     jsonb NOT NULL DEFAULT '[]',
  status           text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','complete','applied')),
  applied_at       timestamptz,
  created_by       uuid REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_diagnoses_org ON diagnoses(org_id, updated_at DESC);

-- ===========================================================================================
-- 4. Compras: política de cotações, fornecedores, pedidos e cotações
-- ===========================================================================================
CREATE TABLE procurement_policies (
  org_id                  uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  min_quotes              integer NOT NULL DEFAULT 3 CHECK (min_quotes BETWEEN 1 AND 10),
  quote_threshold_cents   bigint NOT NULL DEFAULT 0 CHECK (quote_threshold_cents >= 0),  -- abaixo disto, cotações não são exigidas
  outlier_pct             numeric(5,2) NOT NULL DEFAULT 30 CHECK (outlier_pct BETWEEN 1 AND 500),
  exception_needs_approval boolean NOT NULL DEFAULT true,
  updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE suppliers (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name       text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
  cnpj       char(14) CHECK (cnpj ~ '^[0-9]{14}$'),
  category   text CHECK (length(category) <= 80),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, cnpj)
);
CREATE TABLE procurement_requests (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id            uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  budget_item_id        uuid REFERENCES budget_items(id) ON DELETE SET NULL,
  description           text NOT NULL CHECK (length(description) BETWEEN 3 AND 500),
  estimated_cents       bigint NOT NULL CHECK (estimated_cents > 0),
  status                text NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open','decided','exception_pending','exception_approved','cancelled')),
  selected_quotation_id uuid,
  decision_reason       text CHECK (length(decision_reason) <= 2000),
  exception_reason      text CHECK (length(exception_reason) <= 2000),
  decided_by            uuid REFERENCES users(id),
  approved_by           uuid REFERENCES users(id),
  approved_at           timestamptz,
  created_by            uuid REFERENCES users(id),
  created_at            timestamptz NOT NULL DEFAULT now(),
  CHECK (approved_by IS NULL OR approved_by IS DISTINCT FROM decided_by)    -- quem aprova a exceção não é quem decidiu
);
CREATE INDEX ix_proc_req ON procurement_requests(project_id, created_at DESC);
CREATE TABLE quotations (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id     uuid NOT NULL REFERENCES procurement_requests(id) ON DELETE CASCADE,
  org_id         uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  supplier_id    uuid REFERENCES suppliers(id) ON DELETE SET NULL,
  supplier_name  text NOT NULL CHECK (length(supplier_name) BETWEEN 2 AND 200),
  supplier_cnpj  char(14) CHECK (supplier_cnpj ~ '^[0-9]{14}$'),
  amount_cents   bigint NOT NULL CHECK (amount_cents > 0),
  valid_until    date,
  document_id    uuid REFERENCES documents(id) ON DELETE SET NULL,
  notes          text CHECK (length(notes) <= 1000),
  created_by     uuid REFERENCES users(id),
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_quote_supplier ON quotations(request_id, coalesce(supplier_cnpj, lower(supplier_name)));
ALTER TABLE procurement_requests ADD CONSTRAINT fk_proc_selected FOREIGN KEY (selected_quotation_id) REFERENCES quotations(id) ON DELETE SET NULL;
ALTER TABLE expenses ADD COLUMN procurement_request_id uuid REFERENCES procurement_requests(id) ON DELETE SET NULL;

-- ===========================================================================================
-- 5. Risco e antifraude (SINAIS para revisão humana — nunca acusação)
-- ===========================================================================================
CREATE TABLE risk_signals (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,   -- organização sob análise
  project_id    uuid REFERENCES projects(id) ON DELETE CASCADE,
  signal_type   text NOT NULL CHECK (signal_type IN ('duplicate_document_hash','duplicate_expense','expense_over_budget_item',
                  'price_outlier','related_accounts','supplier_is_party','evidence_reuse','quotes_below_policy')),
  severity      text NOT NULL CHECK (severity IN ('low','medium','high')),
  dedupe_key    text NOT NULL UNIQUE,
  summary       text NOT NULL CHECK (length(summary) <= 500),
  details       jsonb NOT NULL DEFAULT '{}',
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open','reviewed_relevant','dismissed')),
  reviewed_by   uuid REFERENCES users(id),
  reviewed_at   timestamptz,
  review_note   text CHECK (length(review_note) <= 2000),
  detected_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (status = 'open' OR (reviewed_by IS NOT NULL AND review_note IS NOT NULL))
);
CREATE INDEX ix_risk_signals ON risk_signals(org_id, status);
CREATE TABLE risk_assessments (
  org_id       uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  level        text NOT NULL CHECK (level IN ('low','medium','high','manual_review','blocked')),
  rationale    text CHECK (length(rationale) <= 2000),
  open_signals integer NOT NULL DEFAULT 0,
  decided_by   uuid REFERENCES users(id),           -- 'blocked' só por decisão humana
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (level <> 'blocked' OR decided_by IS NOT NULL)
);
CREATE FUNCTION app_org_blocked(p_org uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM risk_assessments WHERE org_id = p_org AND level = 'blocked')
$$;

-- ===========================================================================================
-- 6. Modelos de contribuição (portão jurídico) e pagamentos (estados, estorno, reconciliação)
-- ===========================================================================================
CREATE TABLE contribution_models (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                 uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id             uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  kind                   text NOT NULL CHECK (kind IN ('donation','sponsorship','quota','incentive_law','impact_investment')),
  title                  text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  description            text CHECK (length(description) <= 4000),
  legal_structure        text CHECK (length(legal_structure) <= 1000),
  refundable             boolean NOT NULL DEFAULT false,
  refund_policy          text CHECK (length(refund_policy) <= 2000),
  min_contribution_cents bigint CHECK (min_contribution_cents >= 0),
  quota_value_cents      bigint CHECK (quota_value_cents > 0),
  quotas_total           integer CHECK (quotas_total > 0),
  status                 text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','legal_review','approved','retired')),
  legal_reviewer         uuid REFERENCES users(id),
  legal_note             text CHECK (length(legal_note) <= 4000),
  approved_at            timestamptz,
  created_by             uuid REFERENCES users(id),
  created_at             timestamptz NOT NULL DEFAULT now(),
  CHECK (status <> 'approved' OR (legal_reviewer IS NOT NULL AND legal_note IS NOT NULL AND approved_at IS NOT NULL)),
  CHECK (refundable = false OR refund_policy IS NOT NULL),
  CHECK (kind <> 'quota' OR (quota_value_cents IS NOT NULL AND quotas_total IS NOT NULL))
);
CREATE FUNCTION contribution_status_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN
    IF NEW.status = 'approved' AND (TG_OP = 'INSERT' OR OLD.status <> 'approved') THEN
      RAISE EXCEPTION 'aprovação jurídica só pela administração' USING ERRCODE = '42501';
    END IF;
    IF TG_OP = 'UPDATE' AND (NEW.legal_reviewer IS DISTINCT FROM OLD.legal_reviewer OR NEW.legal_note IS DISTINCT FROM OLD.legal_note
                             OR NEW.approved_at IS DISTINCT FROM OLD.approved_at) THEN
      RAISE EXCEPTION 'campos de revisão jurídica só pela administração' USING ERRCODE = '42501';
    END IF;
    -- após aprovado, os termos não mudam (só aposentar)
    IF TG_OP = 'UPDATE' AND OLD.status = 'approved' AND (NEW.kind, NEW.refundable, NEW.refund_policy, NEW.legal_structure, NEW.quota_value_cents,
         NEW.quotas_total, NEW.min_contribution_cents) IS DISTINCT FROM (OLD.kind, OLD.refundable, OLD.refund_policy, OLD.legal_structure,
         OLD.quota_value_cents, OLD.quotas_total, OLD.min_contribution_cents) THEN
      RAISE EXCEPTION 'modelo aprovado não pode ter termos alterados; crie outro' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_contribution_guard BEFORE INSERT OR UPDATE ON contribution_models FOR EACH ROW EXECUTE FUNCTION contribution_status_guard();

CREATE TABLE payment_records (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  commitment_id         uuid NOT NULL REFERENCES commitments(id) ON DELETE RESTRICT,
  project_id            uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  funder_org_id         uuid NOT NULL REFERENCES organizations(id),
  osc_org_id            uuid NOT NULL REFERENCES organizations(id),
  contribution_model_id uuid REFERENCES contribution_models(id) ON DELETE SET NULL,
  amount_cents          bigint NOT NULL CHECK (amount_cents > 0),
  refunded_cents        bigint NOT NULL DEFAULT 0 CHECK (refunded_cents >= 0),
  state                 text NOT NULL DEFAULT 'created'
                        CHECK (state IN ('created','awaiting_confirmation','confirmed','failed','cancelled','partially_refunded','refunded','disputed')),
  method                text NOT NULL DEFAULT 'bank_transfer' CHECK (method IN ('bank_transfer','pix','boleto','check','other')),
  external_ref          text CHECK (length(external_ref) <= 200),
  reconciliation_status text NOT NULL DEFAULT 'unreconciled' CHECK (reconciliation_status IN ('unreconciled','matched','mismatch','manual')),
  created_by            uuid REFERENCES users(id),
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  CHECK (refunded_cents <= amount_cents)
);
CREATE INDEX ix_payment_commitment ON payment_records(commitment_id);
CREATE INDEX ix_payment_osc ON payment_records(osc_org_id, state);
CREATE TABLE payment_events (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id    uuid NOT NULL REFERENCES payment_records(id) ON DELETE CASCADE,
  from_state    text,
  to_state      text NOT NULL,
  actor_org_id  uuid REFERENCES organizations(id),
  actor_user_id uuid REFERENCES users(id),
  note          text CHECK (length(note) <= 1000),
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_payment_events ON payment_events(payment_id, at);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON payment_events FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Máquina de estados do pagamento (o banco recusa transições inválidas, independentemente da API)
CREATE FUNCTION payment_transition_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF NEW.state = OLD.state THEN RETURN NEW; END IF;
  ok := CASE OLD.state
    WHEN 'created'               THEN NEW.state IN ('awaiting_confirmation','cancelled','failed')
    WHEN 'awaiting_confirmation' THEN NEW.state IN ('confirmed','failed','cancelled','disputed')
    WHEN 'confirmed'             THEN NEW.state IN ('partially_refunded','refunded','disputed')
    WHEN 'partially_refunded'    THEN NEW.state IN ('refunded','disputed')
    WHEN 'disputed'              THEN NEW.state IN ('confirmed','refunded','partially_refunded','cancelled')
    ELSE false END;
  IF NOT ok THEN
    RAISE EXCEPTION 'transição de pagamento inválida: % -> %', OLD.state, NEW.state USING ERRCODE = '23514';
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_payment_state BEFORE UPDATE ON payment_records FOR EACH ROW EXECUTE FUNCTION payment_transition_guard();
CREATE FUNCTION payment_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.amount_cents, NEW.commitment_id, NEW.funder_org_id, NEW.osc_org_id, NEW.project_id)
     IS DISTINCT FROM (OLD.amount_cents, OLD.commitment_id, OLD.funder_org_id, OLD.osc_org_id, OLD.project_id) THEN
    RAISE EXCEPTION 'valor e partes do pagamento são imutáveis' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_payment_immutable BEFORE UPDATE ON payment_records FOR EACH ROW EXECUTE FUNCTION payment_immutable_guard();

CREATE TABLE refunds (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payment_id       uuid NOT NULL REFERENCES payment_records(id) ON DELETE CASCADE,
  amount_cents     bigint NOT NULL CHECK (amount_cents > 0),
  reason           text NOT NULL CHECK (length(reason) BETWEEN 3 AND 1000),
  status           text NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','approved','rejected','completed')),
  requested_by_org uuid NOT NULL REFERENCES organizations(id),
  decided_by_org   uuid REFERENCES organizations(id),
  decided_by       uuid REFERENCES users(id),
  decided_at       timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (status IN ('requested') OR decided_by IS NOT NULL)
);
CREATE INDEX ix_refunds_payment ON refunds(payment_id);

CREATE TABLE statement_imports (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  filename   text NOT NULL CHECK (length(filename) <= 255),
  sha256     char(64) NOT NULL,
  row_count  integer NOT NULL,
  created_by uuid REFERENCES users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, sha256)
);
CREATE TABLE statement_lines (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  import_id          uuid NOT NULL REFERENCES statement_imports(id) ON DELETE CASCADE,
  org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  booked_on          date NOT NULL,
  amount_cents       bigint NOT NULL,
  description        text CHECK (length(description) <= 300),
  reference          text CHECK (length(reference) <= 200),
  matched_payment_id uuid REFERENCES payment_records(id) ON DELETE SET NULL
);
CREATE INDEX ix_stmt_lines ON statement_lines(org_id, booked_on);

-- ===========================================================================================
-- 7. Necessidades de projeto e ofertas de profissionais (match profissional ↔ projeto)
-- ===========================================================================================
CREATE TABLE project_needs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id  uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  category    text NOT NULL CHECK (category ~ '^[a-z0-9_]{2,60}$'),
  title       text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  description text CHECK (length(description) <= 3000),
  remote_ok   boolean NOT NULL DEFAULT true,
  language    text NOT NULL DEFAULT 'pt-BR',
  status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open','filled','cancelled')),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_needs_open ON project_needs(status, category);
CREATE FUNCTION app_need_owner(nid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM project_needs n WHERE n.id = nid AND n.org_id = app_org())
$$;
CREATE TABLE need_offers (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  need_id             uuid NOT NULL REFERENCES project_needs(id) ON DELETE CASCADE,
  professional_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  message             text CHECK (length(message) <= 2000),
  status              text NOT NULL DEFAULT 'offered' CHECK (status IN ('offered','accepted','declined','withdrawn')),
  created_at          timestamptz NOT NULL DEFAULT now(),
  decided_at          timestamptz,
  UNIQUE (need_id, professional_org_id)
);

-- ===========================================================================================
-- 8. Rede: seguir, bloquear, conversas e mensagens (com relação prévia e anti-abuso)
-- ===========================================================================================
CREATE TABLE follows (
  follower_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  followed_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  created_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (follower_org_id, followed_org_id),
  CHECK (follower_org_id <> followed_org_id)
);
CREATE TABLE org_blocks (
  org_id         uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  blocked_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  created_at     timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, blocked_org_id),
  CHECK (org_id <> blocked_org_id)
);
CREATE FUNCTION app_blocked_between(a uuid, b uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM org_blocks WHERE (org_id = a AND blocked_org_id = b) OR (org_id = b AND blocked_org_id = a))
$$;
-- Relação legítima entre duas organizações: candidatura, revisão profissional, oferta de profissional ou seguimento mútuo.
CREATE FUNCTION app_related(a uuid, b uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM applications x WHERE x.status <> 'withdrawn'
                   AND ((x.osc_org_id = a AND x.funder_org_id = b) OR (x.osc_org_id = b AND x.funder_org_id = a)))
      OR EXISTS (SELECT 1 FROM professional_reviews r WHERE (r.org_id = a AND r.professional_org_id = b) OR (r.org_id = b AND r.professional_org_id = a))
      OR EXISTS (SELECT 1 FROM need_offers o JOIN project_needs n ON n.id = o.need_id
                  WHERE (n.org_id = a AND o.professional_org_id = b) OR (n.org_id = b AND o.professional_org_id = a))
      OR (EXISTS (SELECT 1 FROM follows WHERE follower_org_id = a AND followed_org_id = b)
          AND EXISTS (SELECT 1 FROM follows WHERE follower_org_id = b AND followed_org_id = a))
$$;
CREATE TABLE conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_a      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  org_b      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (org_a < org_b),
  UNIQUE (org_a, org_b)
);
CREATE TABLE messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_org_id   uuid NOT NULL REFERENCES organizations(id),
  sender_user_id  uuid NOT NULL REFERENCES users(id),
  body            text NOT NULL CHECK (length(body) BETWEEN 1 AND 2000),
  created_at      timestamptz NOT NULL DEFAULT now(),
  read_at         timestamptz,
  removed_at      timestamptz,              -- moderação: o conteúdo é ocultado, o registro permanece
  removed_reason  text CHECK (length(removed_reason) <= 500)
);
CREATE INDEX ix_messages_conv ON messages(conversation_id, created_at);

-- ===========================================================================================
-- 9. Erros agregados (observabilidade sem PII; fingerprint = rota + tipo + local)
-- ===========================================================================================
CREATE TABLE error_events (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fingerprint     text NOT NULL UNIQUE,
  route           text NOT NULL,
  status          smallint NOT NULL,
  exception_type  text NOT NULL,
  message         text CHECK (length(message) <= 500),
  occurrences     bigint NOT NULL DEFAULT 1,
  first_seen      timestamptz NOT NULL DEFAULT now(),
  last_seen       timestamptz NOT NULL DEFAULT now(),
  last_request_id text,
  last_trace_id   text,
  resolved        boolean NOT NULL DEFAULT false
);

-- ===========================================================================================
-- RLS
-- ===========================================================================================
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['ods_goals','ods_targets','indicator_catalog','project_ods_targets','project_indicators','indicator_values',
    'impact_nodes','impact_edges','diagnoses','procurement_policies','suppliers','procurement_requests','quotations','risk_signals',
    'risk_assessments','contribution_models','payment_records','payment_events','refunds','statement_imports','statement_lines',
    'project_needs','need_offers','follows','org_blocks','conversations','messages','error_events'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

CREATE POLICY ods_goals_read ON ods_goals FOR SELECT USING (true);
CREATE POLICY ods_goals_write ON ods_goals FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY ods_targets_read ON ods_targets FOR SELECT USING (true);
CREATE POLICY ods_targets_write ON ods_targets FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY indicator_catalog_read ON indicator_catalog FOR SELECT USING (origin <> 'org_defined' OR org_id = app_org() OR app_priv());
CREATE POLICY indicator_catalog_insert ON indicator_catalog FOR INSERT WITH CHECK ((origin = 'org_defined' AND org_id = app_org()) OR app_priv());
CREATE POLICY indicator_catalog_update ON indicator_catalog FOR UPDATE USING ((origin = 'org_defined' AND org_id = app_org()) OR app_priv())
  WITH CHECK ((origin = 'org_defined' AND org_id = app_org()) OR app_priv());

-- projetos e métricas associadas: dono escreve; quem enxerga o projeto (RLS de projects) lê
CREATE POLICY project_ods_read ON project_ods_targets FOR SELECT USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id));
CREATE POLICY project_ods_write ON project_ods_targets FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK ((org_id = app_org() AND app_project_owner(project_id)) OR app_priv());
CREATE POLICY project_indicators_read ON project_indicators FOR SELECT USING (EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id));
CREATE POLICY project_indicators_write ON project_indicators FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK ((org_id = app_org() AND app_project_owner(project_id)) OR app_priv());
CREATE POLICY indicator_values_read ON indicator_values FOR SELECT USING (
  org_id = app_org() OR app_project_investor(project_id) OR app_project_party(project_id) OR app_priv());
CREATE POLICY indicator_values_insert ON indicator_values FOR INSERT WITH CHECK (
  (org_id = app_org() AND app_project_owner(project_id)) OR app_priv());
CREATE POLICY indicator_values_update ON indicator_values FOR UPDATE USING (
  org_id = app_org() OR app_project_investor(project_id) OR app_priv())
  WITH CHECK (org_id = app_org() OR app_project_investor(project_id) OR app_priv());

CREATE POLICY impact_nodes_read ON impact_nodes FOR SELECT USING (
  org_id = app_org() OR app_project_investor(project_id) OR app_project_party(project_id) OR app_priv());
CREATE POLICY impact_nodes_write ON impact_nodes FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK ((org_id = app_org() AND app_project_owner(project_id)) OR app_priv());
CREATE POLICY impact_edges_read ON impact_edges FOR SELECT USING (
  org_id = app_org() OR app_project_investor(project_id) OR app_project_party(project_id) OR app_priv());
CREATE POLICY impact_edges_insert ON impact_edges FOR INSERT WITH CHECK ((org_id = app_org() AND app_project_owner(project_id)) OR app_priv());
CREATE POLICY impact_edges_update ON impact_edges FOR UPDATE USING (org_id = app_org() OR app_project_investor(project_id) OR app_priv())
  WITH CHECK (org_id = app_org() OR app_project_investor(project_id) OR app_priv());
CREATE POLICY impact_edges_delete ON impact_edges FOR DELETE USING (org_id = app_org() OR app_priv());

CREATE POLICY diagnoses_all ON diagnoses FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY proc_policy_all ON procurement_policies FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY suppliers_all ON suppliers FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY proc_req_read ON procurement_requests FOR SELECT USING (org_id = app_org() OR app_project_investor(project_id) OR app_priv());
CREATE POLICY proc_req_write ON procurement_requests FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK ((org_id = app_org() AND app_project_owner(project_id)) OR app_priv());
CREATE POLICY quotations_read ON quotations FOR SELECT USING (EXISTS (SELECT 1 FROM procurement_requests r WHERE r.id = request_id));
CREATE POLICY quotations_write ON quotations FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY risk_signals_priv ON risk_signals FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY risk_assessments_priv ON risk_assessments FOR ALL USING (app_priv()) WITH CHECK (app_priv());

CREATE POLICY contribution_read ON contribution_models FOR SELECT USING (
  org_id = app_org() OR (status = 'approved' AND app_authenticated()) OR app_priv());
CREATE POLICY contribution_insert ON contribution_models FOR INSERT WITH CHECK ((org_id = app_org() AND app_project_owner(project_id)) OR app_priv());
CREATE POLICY contribution_update ON contribution_models FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY payment_read ON payment_records FOR SELECT USING (funder_org_id = app_org() OR osc_org_id = app_org() OR app_priv());
CREATE POLICY payment_insert ON payment_records FOR INSERT WITH CHECK (
  (funder_org_id = app_org() AND EXISTS (SELECT 1 FROM commitments c WHERE c.id = commitment_id AND c.funder_org_id = app_org()
     AND c.osc_org_id = payment_records.osc_org_id AND c.project_id = payment_records.project_id)) OR app_priv());
CREATE POLICY payment_update ON payment_records FOR UPDATE USING (funder_org_id = app_org() OR osc_org_id = app_org() OR app_priv())
  WITH CHECK (funder_org_id = app_org() OR osc_org_id = app_org() OR app_priv());
CREATE POLICY payment_events_read ON payment_events FOR SELECT USING (EXISTS (SELECT 1 FROM payment_records p WHERE p.id = payment_id));
CREATE POLICY payment_events_insert ON payment_events FOR INSERT WITH CHECK (
  (actor_org_id = app_org() AND EXISTS (SELECT 1 FROM payment_records p WHERE p.id = payment_id)) OR app_priv());
CREATE POLICY refunds_read ON refunds FOR SELECT USING (EXISTS (SELECT 1 FROM payment_records p WHERE p.id = payment_id));
CREATE POLICY refunds_insert ON refunds FOR INSERT WITH CHECK (
  (requested_by_org = app_org() AND EXISTS (SELECT 1 FROM payment_records p WHERE p.id = payment_id)) OR app_priv());
CREATE POLICY refunds_update ON refunds FOR UPDATE USING (EXISTS (SELECT 1 FROM payment_records p WHERE p.id = payment_id));
CREATE POLICY stmt_imports_all ON statement_imports FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY stmt_lines_all ON statement_lines FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY needs_read ON project_needs FOR SELECT USING (org_id = app_org() OR app_priv()
  OR (status = 'open' AND app_kind() = 'provider' AND EXISTS (SELECT 1 FROM projects p WHERE p.id = project_id AND p.visibility = 'published')));
CREATE POLICY needs_write ON project_needs FOR ALL USING (org_id = app_org() OR app_priv())
  WITH CHECK ((org_id = app_org() AND app_project_owner(project_id)) OR app_priv());
CREATE POLICY offers_read ON need_offers FOR SELECT USING (professional_org_id = app_org() OR app_need_owner(need_id) OR app_priv());
CREATE POLICY offers_insert ON need_offers FOR INSERT WITH CHECK (
  (professional_org_id = app_org() AND app_kind() = 'provider' AND EXISTS (SELECT 1 FROM project_needs n WHERE n.id = need_id AND n.status = 'open')) OR app_priv());
CREATE POLICY offers_update ON need_offers FOR UPDATE USING (professional_org_id = app_org() OR app_need_owner(need_id) OR app_priv());

CREATE POLICY follows_read ON follows FOR SELECT USING (follower_org_id = app_org() OR followed_org_id = app_org() OR app_priv());
CREATE POLICY follows_insert ON follows FOR INSERT WITH CHECK (follower_org_id = app_org() AND NOT app_blocked_between(follower_org_id, followed_org_id));
CREATE POLICY follows_delete ON follows FOR DELETE USING (follower_org_id = app_org());
CREATE POLICY blocks_all ON org_blocks FOR ALL USING (org_id = app_org()) WITH CHECK (org_id = app_org());
CREATE POLICY conversations_read ON conversations FOR SELECT USING (org_a = app_org() OR org_b = app_org() OR app_priv());
CREATE POLICY conversations_insert ON conversations FOR INSERT WITH CHECK (
  (app_org() IN (org_a, org_b) AND app_related(org_a, org_b) AND NOT app_blocked_between(org_a, org_b)) OR app_priv());
CREATE POLICY messages_read ON messages FOR SELECT USING (EXISTS (SELECT 1 FROM conversations c WHERE c.id = conversation_id) OR app_priv());
CREATE POLICY messages_insert ON messages FOR INSERT WITH CHECK (
  sender_org_id = app_org() AND sender_user_id = app_uid()
  AND EXISTS (SELECT 1 FROM conversations c WHERE c.id = conversation_id AND app_org() IN (c.org_a, c.org_b)
              AND NOT app_blocked_between(c.org_a, c.org_b) AND app_related(c.org_a, c.org_b)));
CREATE POLICY messages_update ON messages FOR UPDATE USING (EXISTS (SELECT 1 FROM conversations c WHERE c.id = conversation_id) OR app_priv());

CREATE POLICY error_events_priv ON error_events FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- Mensagem: só o destinatário marca leitura; o remetente não altera conteúdo; moderação (removed_*) só admin.
CREATE FUNCTION message_update_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN
    IF (NEW.body, NEW.sender_org_id, NEW.conversation_id, NEW.created_at, NEW.removed_at, NEW.removed_reason)
       IS DISTINCT FROM (OLD.body, OLD.sender_org_id, OLD.conversation_id, OLD.created_at, OLD.removed_at, OLD.removed_reason) THEN
      RAISE EXCEPTION 'mensagem é imutável (exceto leitura)' USING ERRCODE = '42501';
    END IF;
    IF NEW.read_at IS DISTINCT FROM OLD.read_at AND OLD.sender_org_id = app_org() THEN
      RAISE EXCEPTION 'apenas o destinatário marca leitura' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_message_guard BEFORE UPDATE ON messages FOR EACH ROW EXECUTE FUNCTION message_update_guard();

-- ===========================================================================================
-- Dados de referência: as 17 metas (nomes oficiais abreviados). Metas/indicadores oficiais NÃO são embutidos: carga por importação.
-- ===========================================================================================
INSERT INTO ods_goals(number, name) VALUES
 (1,'Erradicação da pobreza'),(2,'Fome zero e agricultura sustentável'),(3,'Saúde e bem-estar'),(4,'Educação de qualidade'),
 (5,'Igualdade de gênero'),(6,'Água potável e saneamento'),(7,'Energia limpa e acessível'),(8,'Trabalho decente e crescimento econômico'),
 (9,'Indústria, inovação e infraestrutura'),(10,'Redução das desigualdades'),(11,'Cidades e comunidades sustentáveis'),
 (12,'Consumo e produção responsáveis'),(13,'Ação contra a mudança global do clima'),(14,'Vida na água'),(15,'Vida terrestre'),
 (16,'Paz, justiça e instituições eficazes'),(17,'Parcerias e meios de implementação');
-- Indicadores DA PLATAFORMA (não são indicadores oficiais ONU/IBGE; origin='platform' deixa isso explícito).
INSERT INTO indicator_catalog(code, name, unit, definition, esg_dimension, ods, origin) VALUES
 ('people_served',      'Pessoas atendidas (únicas)',             'pessoas',  'Número de pessoas distintas atendidas no período, sem dados pessoais (contagem agregada).', 'S', NULL, 'platform'),
 ('activity_hours',     'Horas de atividade realizadas',          'horas',    'Soma das horas de atividades ofertadas no período.', 'S', NULL, 'platform'),
 ('sessions_held',      'Encontros/atividades realizados',        'unidades', 'Quantidade de encontros ou atividades realizadas.', 'S', NULL, 'platform'),
 ('meals_served',       'Refeições servidas',                     'refeições','Quantidade de refeições servidas.', 'S', 2, 'platform'),
 ('trained_people',     'Pessoas capacitadas',                    'pessoas',  'Pessoas que concluíram capacitação com frequência mínima definida pelo projeto.', 'S', 4, 'platform'),
 ('jobs_created',       'Postos de trabalho/renda gerados',       'unidades', 'Ocupações ou fontes de renda geradas, conforme critério declarado no método.', 'S', 8, 'platform'),
 ('women_participants', 'Participantes mulheres (agregado)',      'pessoas',  'Contagem agregada; não identifica pessoas.', 'S', 5, 'platform'),
 ('trees_planted',      'Árvores plantadas',                      'unidades', 'Mudas plantadas e georreferenciadas pelo projeto.', 'E', 15, 'platform'),
 ('waste_diverted',     'Resíduos desviados de aterro',           'kg',       'Massa de resíduos encaminhada para reciclagem/compostagem.', 'E', 12, 'platform'),
 ('water_access',       'Pessoas com acesso a água tratada',      'pessoas',  'Pessoas com novo acesso, conforme método declarado.', 'S', 6, 'platform'),
 ('volunteer_hours',    'Horas de voluntariado',                  'horas',    'Horas de voluntariado registradas.', 'S', 17, 'platform'),
 ('board_meetings',     'Reuniões de conselho/governança',        'unidades', 'Reuniões de governança realizadas e registradas em ata.', 'G', 16, 'platform'),
 ('audited_reports',    'Prestações de contas auditadas',         'unidades', 'Prestações de contas revisadas por profissional habilitado.', 'G', 16, 'platform');

-- ===========================================================================================
-- Privilégios das novas tabelas (mesmo modelo da 0002) e tabelas append-only
-- ===========================================================================================
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO impacto_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events, ledger_entries, signatures, application_transitions, payment_events FROM impacto_app;
REVOKE ALL ON chain_heads FROM impacto_app;
REVOKE ALL ON schema_migrations FROM impacto_app;
GRANT SELECT ON schema_migrations TO impacto_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO impacto_app;
DO $$ DECLARE f regprocedure; BEGIN
  FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND pg_get_userbyid(p.proowner) = current_user LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO impacto_app', f);
  END LOOP;
END $$;

-- Financiador pessoa física precisa avaliar projetos no feed: mesma leitura restrita de metadados (nunca conteúdo) que company/government.
CREATE OR REPLACE FUNCTION org_document_metadata(p_org uuid, p_project uuid)
RETURNS TABLE(doc_type text, status text, valid_until date)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NOT (app_org() = p_org OR app_kind() IN ('company','government','platform','individual') OR app_priv()) THEN
    RAISE EXCEPTION 'acesso negado aos metadados documentais' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
  SELECT d.doc_type, d.status, d.valid_until FROM documents d
   WHERE d.org_id = p_org AND d.deleted_at IS NULL
     AND (d.project_id IS NULL OR d.project_id = p_project);
END $$;
