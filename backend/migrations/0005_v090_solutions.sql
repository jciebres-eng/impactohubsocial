-- 0005_v090_solutions.sql — Impact Solutions Library: banco de ideias, projetos, cases, metodologias e soluções de impacto.
-- Reutiliza: organizations, users, projects (vínculo opcional), documents, evidences, funder_profiles, reports, notificações.
-- Princípios no banco: ideia ≠ case; autodeclarado ≠ comprovado (trust_level só muda pela administração); visualização ≠ intenção;
-- identidade do financiador privada por padrão; avaliações não entram no ranking.

CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TEXT SEARCH CONFIGURATION pt_unaccent (COPY = portuguese);
ALTER TEXT SEARCH CONFIGURATION pt_unaccent ALTER MAPPING FOR hword, hword_part, word WITH unaccent, portuguese_stem;

ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_target_type_check;
ALTER TABLE reports ADD CONSTRAINT reports_target_type_check CHECK (target_type IN ('organization','project','call','document','user','message','solution'));

-- ===========================================================================================
-- 1. Solução (entidade central) e versões
-- ===========================================================================================
CREATE TABLE solutions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  created_by       uuid NOT NULL REFERENCES users(id),
  project_id       uuid REFERENCES projects(id) ON DELETE SET NULL,
  parent_id        uuid REFERENCES solutions(id) ON DELETE SET NULL,
  kind             text NOT NULL CHECK (kind IN ('project','idea','methodology','social_tech','academic')),
  stage            text NOT NULL DEFAULT 'proposal' CHECK (stage IN ('idea','proposal','developing','running','completed','archived')),
  title            text NOT NULL CHECK (length(title) BETWEEN 5 AND 200),
  summary          text NOT NULL CHECK (length(summary) BETWEEN 20 AND 1500),
  problem          text CHECK (length(problem) <= 4000),
  approach         text CHECK (length(approach) <= 6000),
  objectives       text CHECK (length(objectives) <= 3000),
  learnings        text CHECK (length(learnings) <= 4000),
  challenges       text CHECK (length(challenges) <= 4000),
  limitations      text CHECK (length(limitations) <= 4000),
  themes           text[] NOT NULL DEFAULT '{}',
  population       text[] NOT NULL DEFAULT '{}',
  institutions     text[] NOT NULL DEFAULT '{}',
  ods              smallint[] NOT NULL DEFAULT '{}' CHECK (ods <@ ARRAY[1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17]::smallint[]),
  esg              text[] NOT NULL DEFAULT '{}' CHECK (esg <@ ARRAY['E','S','G']),
  uf               text CHECK (uf ~ '^[A-Z]{2}$'),
  city             text CHECK (length(city) <= 120),
  ibge_code        text CHECK (ibge_code ~ '^[0-9]{7}$'),
  modality         text CHECK (modality IN ('presencial','remoto','hibrido')),
  duration_months  integer CHECK (duration_months BETWEEN 1 AND 240),
  period_start     date,
  period_end       date,
  team_size        integer CHECK (team_size BETWEEN 1 AND 100000),
  beneficiaries_count integer CHECK (beneficiaries_count >= 0),
  budget_cents     bigint CHECK (budget_cents >= 0),
  raised_cents     bigint NOT NULL DEFAULT 0 CHECK (raised_cents >= 0),
  needed_cents     bigint CHECK (needed_cents >= 0),
  seeking_funding  boolean NOT NULL DEFAULT false,
  goals            jsonb NOT NULL DEFAULT '[]',
  schedule         jsonb NOT NULL DEFAULT '[]',
  license          text NOT NULL DEFAULT 'all_rights_reserved' CHECK (license IN ('cc_by','cc_by_sa','cc_by_nc','cc_by_nc_sa','public_domain','all_rights_reserved','custom')),
  allow_replication boolean NOT NULL DEFAULT false,
  allow_adaptation  boolean NOT NULL DEFAULT false,
  attribution_required boolean NOT NULL DEFAULT true,
  usage_conditions text CHECK (length(usage_conditions) <= 2000),
  ip_notes         text CHECK (length(ip_notes) <= 2000),
  visibility       text NOT NULL DEFAULT 'draft' CHECK (visibility IN ('draft','published','archived','removed')),
  current_version  integer NOT NULL DEFAULT 1,
  -- proveniência e confiança (só a administração altera)
  trust_level      text NOT NULL DEFAULT 'self_declared' CHECK (trust_level IN ('unverified','self_declared','in_review','documented','evidenced','verified')),
  verified_by      uuid REFERENCES users(id),
  verified_at      timestamptz,
  verification_note text,
  review_requested_at timestamptz,
  disputed         boolean NOT NULL DEFAULT false,
  source_type      text NOT NULL DEFAULT 'author' CHECK (source_type IN ('author','osc','university','government','document','audit','public_source','partner','external_system')),
  source_name      text CHECK (length(source_name) <= 300),
  source_date      date,
  is_demo          boolean NOT NULL DEFAULT false,
  generated_draft  boolean NOT NULL DEFAULT false,   -- rascunho gerado por regras/IA a partir de outra solução: exige revisão humana antes de publicar
  human_reviewed_at timestamptz,
  search_doc       tsvector,
  title_norm       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  published_at     timestamptz,
  CHECK (period_end IS NULL OR period_start IS NULL OR period_end >= period_start),
  CHECK (kind <> 'idea' OR stage IN ('idea','proposal','archived')),
  CHECK (needed_cents IS NULL OR budget_cents IS NULL OR needed_cents <= budget_cents + raised_cents + 1),
  CHECK (NOT generated_draft OR visibility <> 'published' OR human_reviewed_at IS NOT NULL)
);
CREATE INDEX ix_solutions_search ON solutions USING gin(search_doc);
CREATE INDEX ix_solutions_trgm ON solutions USING gin(title_norm gin_trgm_ops);
CREATE INDEX ix_solutions_themes ON solutions USING gin(themes);
CREATE INDEX ix_solutions_population ON solutions USING gin(population);
CREATE INDEX ix_solutions_ods ON solutions USING gin(ods);
CREATE INDEX ix_solutions_pub ON solutions(visibility, kind, stage, uf);
CREATE INDEX ix_solutions_org ON solutions(org_id);

-- Texto de busca (sem acentos, radicais do português) e título normalizado para similaridade por trigramas.
CREATE FUNCTION solution_index() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_doc :=
    setweight(to_tsvector('pt_unaccent', coalesce(NEW.title,'')), 'A') ||
    setweight(to_tsvector('pt_unaccent', coalesce(NEW.summary,'') || ' ' || array_to_string(NEW.themes,' ') || ' ' || array_to_string(NEW.population,' ')
                                         || ' ' || array_to_string(NEW.institutions,' ')), 'B') ||
    setweight(to_tsvector('pt_unaccent', concat_ws(' ', NEW.problem, NEW.approach, NEW.objectives, NEW.learnings, NEW.city)), 'C');
  NEW.title_norm := lower(unaccent(NEW.title));
  RETURN NEW;
END $$;
CREATE TRIGGER trg_solution_index BEFORE INSERT OR UPDATE ON solutions FOR EACH ROW EXECUTE FUNCTION solution_index();

-- Estado inicial e regras de verdade (impacto_app): confiança e marcas administrativas não podem ser forjadas;
-- "removed" só pela administração e irreversível pelo autor; publicação só de conteúdo íntegro.
CREATE FUNCTION solution_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN
    IF TG_OP = 'INSERT' THEN
      NEW.trust_level := 'self_declared'; NEW.verified_by := NULL; NEW.verified_at := NULL; NEW.verification_note := NULL;
      NEW.is_demo := false; NEW.disputed := false; NEW.visibility := CASE WHEN NEW.visibility = 'removed' THEN 'draft' ELSE NEW.visibility END;
    ELSE
      IF NEW.trust_level IS DISTINCT FROM OLD.trust_level OR NEW.verified_by IS DISTINCT FROM OLD.verified_by OR NEW.verified_at IS DISTINCT FROM OLD.verified_at
         OR NEW.verification_note IS DISTINCT FROM OLD.verification_note OR NEW.is_demo IS DISTINCT FROM OLD.is_demo OR NEW.disputed IS DISTINCT FROM OLD.disputed
         OR NEW.org_id IS DISTINCT FROM OLD.org_id OR NEW.created_by IS DISTINCT FROM OLD.created_by
         OR (OLD.generated_draft AND NOT NEW.generated_draft) OR (NOT OLD.generated_draft AND NEW.generated_draft) THEN
        RAISE EXCEPTION 'campos de verificação/autoria só podem ser alterados pela administração' USING ERRCODE = '42501';
      END IF;
      IF NEW.visibility = 'removed' OR OLD.visibility = 'removed' THEN
        IF NEW.visibility IS DISTINCT FROM OLD.visibility THEN RAISE EXCEPTION 'remoção só pela administração' USING ERRCODE = '42501'; END IF;
      END IF;
      -- conteúdo comprovado perde a verificação se o conteúdo substantivo mudar (volta a "em revisão")
      IF OLD.trust_level IN ('documented','evidenced','verified') AND
         (NEW.title IS DISTINCT FROM OLD.title OR NEW.summary IS DISTINCT FROM OLD.summary OR NEW.stage IS DISTINCT FROM OLD.stage
          OR NEW.budget_cents IS DISTINCT FROM OLD.budget_cents OR NEW.uf IS DISTINCT FROM OLD.uf OR NEW.kind IS DISTINCT FROM OLD.kind) THEN
        NEW.trust_level := 'in_review'; NEW.review_requested_at := now();
      END IF;
    END IF;
  END IF;
  IF TG_OP = 'UPDATE' THEN
    IF ROW(NEW.title, NEW.summary, NEW.problem, NEW.approach, NEW.objectives, NEW.learnings, NEW.challenges, NEW.limitations, NEW.themes, NEW.population,
           NEW.institutions, NEW.ods, NEW.esg, NEW.uf, NEW.city, NEW.modality, NEW.duration_months, NEW.budget_cents, NEW.needed_cents,
           NEW.beneficiaries_count, NEW.goals, NEW.schedule, NEW.license, NEW.allow_replication, NEW.allow_adaptation, NEW.stage, NEW.kind)
       IS DISTINCT FROM
       ROW(OLD.title, OLD.summary, OLD.problem, OLD.approach, OLD.objectives, OLD.learnings, OLD.challenges, OLD.limitations, OLD.themes, OLD.population,
           OLD.institutions, OLD.ods, OLD.esg, OLD.uf, OLD.city, OLD.modality, OLD.duration_months, OLD.budget_cents, OLD.needed_cents,
           OLD.beneficiaries_count, OLD.goals, OLD.schedule, OLD.license, OLD.allow_replication, OLD.allow_adaptation, OLD.stage, OLD.kind) THEN
      NEW.current_version := OLD.current_version + 1;
    END IF;
    NEW.updated_at := now();
  END IF;
  IF NEW.visibility = 'published' AND (TG_OP = 'INSERT' OR OLD.visibility <> 'published') THEN NEW.published_at := now(); END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_solution_guard BEFORE INSERT OR UPDATE ON solutions FOR EACH ROW EXECUTE FUNCTION solution_guard();

CREATE FUNCTION app_solution_owner(sid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM solutions s WHERE s.id = sid AND s.org_id = app_org())
$$;
CREATE FUNCTION app_solution_visible(sid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT EXISTS (SELECT 1 FROM solutions s WHERE s.id = sid AND (s.visibility = 'published' OR s.org_id = app_org()))
$$;

CREATE TABLE solution_versions (
  solution_id uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  version     integer NOT NULL,
  snapshot    jsonb NOT NULL,
  changed_by  uuid REFERENCES users(id),
  at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (solution_id, version)
);
CREATE FUNCTION solution_snapshot() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF TG_OP = 'INSERT' OR NEW.current_version <> OLD.current_version THEN
    INSERT INTO solution_versions(solution_id, version, snapshot, changed_by)
    VALUES (NEW.id, NEW.current_version, to_jsonb(NEW) - 'search_doc' - 'title_norm', app_uid())
    ON CONFLICT DO NOTHING;
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_solution_snapshot AFTER INSERT OR UPDATE ON solutions FOR EACH ROW EXECUTE FUNCTION solution_snapshot();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON solution_versions FOR EACH ROW WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

-- ===========================================================================================
-- 2. Autoria, evidências, resultados, perfil de replicação, relações
-- ===========================================================================================
CREATE TABLE solution_people (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  name        text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
  role        text NOT NULL CHECK (role IN ('author','coauthor','researcher','collaborator','institution')),
  user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  org_id      uuid REFERENCES organizations(id) ON DELETE SET NULL,
  institution text CHECK (length(institution) <= 200),
  position    smallint NOT NULL DEFAULT 0
);
CREATE INDEX ix_solution_people ON solution_people(solution_id);

CREATE TABLE solution_evidence (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('document','photo','video','report','publication','audit','external_source')),
  title       text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  description text CHECK (length(description) <= 2000),
  url         text CHECK (url ~ '^https://'),
  document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  evidence_id uuid REFERENCES evidences(id) ON DELETE SET NULL,
  source_type text NOT NULL DEFAULT 'author' CHECK (source_type IN ('author','osc','university','government','document','audit','public_source','partner','external_system')),
  source_date date,
  status      text NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','accepted','rejected')),
  reviewed_by uuid REFERENCES users(id),
  reviewed_at timestamptz,
  review_note text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (status = 'submitted' OR reviewed_by IS NOT NULL)
);
CREATE INDEX ix_solution_evidence ON solution_evidence(solution_id, status);
CREATE TRIGGER trg_guard BEFORE UPDATE ON solution_evidence FOR EACH ROW EXECUTE FUNCTION guard_columns('status','reviewed_by','reviewed_at','review_note','org_id');
CREATE FUNCTION solution_evidence_initial() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN NEW.status := 'submitted'; NEW.reviewed_by := NULL; NEW.reviewed_at := NULL; NEW.review_note := NULL; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_initial BEFORE INSERT ON solution_evidence FOR EACH ROW EXECUTE FUNCTION solution_evidence_initial();

CREATE TABLE solution_results (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  indicator   text NOT NULL CHECK (length(indicator) BETWEEN 2 AND 200),
  unit        text CHECK (length(unit) <= 40),
  baseline    numeric,
  value       numeric NOT NULL,
  period      text CHECK (length(period) <= 80),
  evidence_id uuid REFERENCES solution_evidence(id) ON DELETE SET NULL,
  status      text NOT NULL DEFAULT 'reported' CHECK (status IN ('reported','validated')),
  validated_by uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (status = 'reported' OR (validated_by IS NOT NULL AND evidence_id IS NOT NULL))
);
CREATE TRIGGER trg_guard BEFORE UPDATE ON solution_results FOR EACH ROW EXECUTE FUNCTION guard_columns('status','validated_by');
CREATE FUNCTION solution_result_initial() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND NOT app_priv() THEN NEW.status := 'reported'; NEW.validated_by := NULL; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_initial BEFORE INSERT ON solution_results FOR EACH ROW EXECUTE FUNCTION solution_result_initial();

CREATE TABLE solution_replication_profile (
  solution_id           uuid PRIMARY KEY REFERENCES solutions(id) ON DELETE CASCADE,
  simplicity            smallint CHECK (simplicity BETWEEN 1 AND 5),
  cost_level            text CHECK (cost_level IN ('low','moderate','high')),
  infra_dependency      text CHECK (infra_dependency IN ('low','medium','high')),
  territorial_dependency text CHECK (territorial_dependency IN ('low','medium','high')),
  specialists_needed    text CHECK (specialists_needed IN ('none','some','many')),
  documented            boolean,
  training_available    boolean,
  adaptable             text[] NOT NULL DEFAULT '{}' CHECK (adaptable <@ ARRAY['population','territory','budget','duration','scale','methodology','partners']),
  min_budget_cents      bigint CHECK (min_budget_cents >= 0),
  max_budget_cents      bigint CHECK (max_budget_cents >= 0),
  min_months            integer CHECK (min_months >= 1),
  required_infra        text[] NOT NULL DEFAULT '{}',
  required_partners     text[] NOT NULL DEFAULT '{}',
  notes                 text CHECK (length(notes) <= 3000),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  CHECK (max_budget_cents IS NULL OR min_budget_cents IS NULL OR max_budget_cents >= min_budget_cents)
);

CREATE TABLE solution_relationships (
  from_id     uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  to_id       uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  rel_type    text NOT NULL CHECK (rel_type IN ('derived_from','replicates','complements','combined_with')),
  created_by_org uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  note        text CHECK (length(note) <= 500),
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (from_id, to_id, rel_type),
  CHECK (from_id <> to_id)
);

-- ===========================================================================================
-- 3. Interação: salvar, pedidos, intenção, replicação, avaliações, disputas
-- ===========================================================================================
CREATE TABLE solution_saves (
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  solution_id uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, solution_id)
);

CREATE TABLE solution_requests (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id  uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  requester_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  requester_user_id uuid NOT NULL REFERENCES users(id),
  kind         text NOT NULL CHECK (kind IN ('info','contact','adaptation','replication','budget')),
  message      text NOT NULL CHECK (length(message) BETWEEN 5 AND 3000),
  params       jsonb NOT NULL DEFAULT '{}',
  status       text NOT NULL DEFAULT 'new' CHECK (status IN ('new','seen','accepted','declined','closed')),
  response     text CHECK (length(response) <= 3000),
  responded_at timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_solution_requests ON solution_requests(solution_id, status);
CREATE INDEX ix_solution_requests_req ON solution_requests(requester_org_id, created_at);
-- Cada lado só mexe no que lhe cabe: autor (status/resposta), solicitante (apenas encerrar).
CREATE FUNCTION solution_request_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  IF NEW.solution_id IS DISTINCT FROM OLD.solution_id OR NEW.requester_org_id IS DISTINCT FROM OLD.requester_org_id OR NEW.kind IS DISTINCT FROM OLD.kind
     OR NEW.message IS DISTINCT FROM OLD.message OR NEW.params IS DISTINCT FROM OLD.params OR NEW.requester_user_id IS DISTINCT FROM OLD.requester_user_id THEN
    RAISE EXCEPTION 'conteúdo do pedido é imutável' USING ERRCODE = '42501';
  END IF;
  IF app_org() = OLD.requester_org_id AND NOT app_solution_owner(OLD.solution_id) THEN
    IF NEW.status <> 'closed' OR NEW.response IS DISTINCT FROM OLD.response THEN
      RAISE EXCEPTION 'o solicitante só pode encerrar o pedido' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_request_guard BEFORE UPDATE ON solution_requests FOR EACH ROW EXECUTE FUNCTION solution_request_guard();

-- Intenção de financiamento: etapas explícitas. Visualização NUNCA cria intenção. Etapas avançadas exigem confirmação do autor.
CREATE TABLE solution_intents (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id   uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id       uuid NOT NULL REFERENCES users(id),
  stage         text NOT NULL DEFAULT 'discovery' CHECK (stage IN ('discovery','interested','reviewing','requested_info','requested_adaptation','negotiating','commitment_started','funded','implementing','completed')),
  public_identity boolean NOT NULL DEFAULT false,
  confirmed_by_author boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (solution_id, org_id)
);
CREATE TABLE solution_intent_events (
  id          bigserial PRIMARY KEY,
  intent_id   uuid NOT NULL REFERENCES solution_intents(id) ON DELETE CASCADE,
  from_stage  text,
  to_stage    text NOT NULL,
  actor_org_id uuid NOT NULL REFERENCES organizations(id),
  at          timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON solution_intent_events FOR EACH ROW WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
-- Os estágios avançados só podem ser definidos pelo autor; o financiador só mexe nos iniciais (e na própria visibilidade).
CREATE FUNCTION solution_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE funder_set text[] := ARRAY['discovery','interested','reviewing'];
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  IF TG_OP = 'INSERT' THEN
    IF NEW.stage <> ALL (funder_set) THEN RAISE EXCEPTION 'estágio inicial inválido' USING ERRCODE = '42501'; END IF;
    NEW.confirmed_by_author := false;
    RETURN NEW;
  END IF;
  IF app_org() = OLD.org_id THEN
    IF NEW.stage IS DISTINCT FROM OLD.stage AND NOT (NEW.stage = ANY (funder_set) AND OLD.stage = ANY (funder_set)) THEN
      RAISE EXCEPTION 'este estágio só pode ser avançado pelo fluxo de pedidos ou pela confirmação do autor' USING ERRCODE = '42501';
    END IF;
    IF NEW.confirmed_by_author IS DISTINCT FROM OLD.confirmed_by_author THEN RAISE EXCEPTION 'confirmação é do autor' USING ERRCODE = '42501'; END IF;
  ELSIF app_solution_owner(OLD.solution_id) THEN
    IF NEW.public_identity IS DISTINCT FROM OLD.public_identity OR NEW.org_id IS DISTINCT FROM OLD.org_id THEN
      RAISE EXCEPTION 'o autor não altera a privacidade do financiador' USING ERRCODE = '42501';
    END IF;
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_intent_guard BEFORE INSERT OR UPDATE ON solution_intents FOR EACH ROW EXECUTE FUNCTION solution_intent_guard();

CREATE TABLE solution_replications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id   uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  replicator_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  target_uf     text CHECK (target_uf ~ '^[A-Z]{2}$'),
  target_city   text CHECK (length(target_city) <= 120),
  status        text NOT NULL DEFAULT 'interested' CHECK (status IN ('interested','info_requested','adaptation_requested','started','completed','cancelled')),
  public_identity boolean NOT NULL DEFAULT false,
  author_confirmed boolean NOT NULL DEFAULT false,
  started_at    timestamptz,
  completed_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (solution_id, replicator_org_id, target_uf, target_city)
);
CREATE FUNCTION solution_replication_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  IF TG_OP = 'INSERT' THEN
    IF NEW.status NOT IN ('interested') THEN RAISE EXCEPTION 'replicação nasce como interesse' USING ERRCODE = '42501'; END IF;
    NEW.author_confirmed := false; RETURN NEW;
  END IF;
  IF app_org() = OLD.replicator_org_id THEN
    IF NEW.author_confirmed IS DISTINCT FROM OLD.author_confirmed THEN RAISE EXCEPTION 'confirmação é do autor' USING ERRCODE = '42501'; END IF;
    IF NEW.status = 'completed' AND OLD.status <> 'started' THEN RAISE EXCEPTION 'só é possível concluir uma replicação iniciada' USING ERRCODE = '42501'; END IF;
  ELSIF app_solution_owner(OLD.solution_id) THEN
    IF NEW.status IS DISTINCT FROM OLD.status OR NEW.public_identity IS DISTINCT FROM OLD.public_identity THEN
      RAISE EXCEPTION 'o autor apenas confirma a replicação' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_replication_guard BEFORE INSERT OR UPDATE ON solution_replications FOR EACH ROW EXECUTE FUNCTION solution_replication_guard();

-- Avaliações: só quem tem relação real com a solução (pedido aceito ou replicação confirmada); não entram no ranking.
CREATE TABLE solution_reviews (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id),
  rating      smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
  body        text CHECK (length(body) <= 2000),
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (solution_id, org_id)
);
CREATE FUNCTION app_solution_reviewable(sid uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT NOT EXISTS (SELECT 1 FROM solutions s WHERE s.id = sid AND s.org_id = app_org())
     AND (EXISTS (SELECT 1 FROM solution_requests r WHERE r.solution_id = sid AND r.requester_org_id = app_org() AND r.status = 'accepted')
          OR EXISTS (SELECT 1 FROM solution_replications x WHERE x.solution_id = sid AND x.replicator_org_id = app_org() AND x.author_confirmed))
$$;

CREATE TABLE solution_disputes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  claimant_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  claimant_user_id uuid NOT NULL REFERENCES users(id),
  claim       text NOT NULL CHECK (length(claim) BETWEEN 20 AND 4000),
  supporting_note text CHECK (length(supporting_note) <= 4000),
  status      text NOT NULL DEFAULT 'open' CHECK (status IN ('open','upheld','rejected','withdrawn')),
  decided_by  uuid REFERENCES users(id),
  decision_note text,
  decided_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (status IN ('open','withdrawn') OR (decided_by IS NOT NULL AND decision_note IS NOT NULL))
);
CREATE TRIGGER trg_guard BEFORE UPDATE ON solution_disputes FOR EACH ROW EXECUTE FUNCTION guard_columns('decided_by','decision_note','decided_at','claimant_org_id');
-- Disputa aberta marca a solução (selo "autoria em disputa"); decisão volta a marcar.
CREATE FUNCTION solution_dispute_flag() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  UPDATE solutions SET disputed = EXISTS (SELECT 1 FROM solution_disputes d WHERE d.solution_id = NEW.solution_id AND d.status = 'open') WHERE id = NEW.solution_id;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_dispute_flag AFTER INSERT OR UPDATE ON solution_disputes FOR EACH ROW EXECUTE FUNCTION solution_dispute_flag();

-- ===========================================================================================
-- 4. Analytics com deduplicação, busca (sem texto bruto), preferências, adaptações e combinações
-- ===========================================================================================
CREATE TABLE solution_events (
  id          bigserial PRIMARY KEY,
  solution_id uuid REFERENCES solutions(id) ON DELETE CASCADE,
  org_id      uuid REFERENCES organizations(id) ON DELETE CASCADE,
  user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  event_type  text NOT NULL CHECK (event_type IN ('solution_viewed','solution_searched','solution_saved','solution_shared','solution_compared','solution_contact_requested',
              'solution_adaptation_requested','solution_replication_requested','funding_intent_created','funding_started','funding_completed','solution_replicated')),
  day         date NOT NULL DEFAULT current_date,
  at          timestamptz NOT NULL DEFAULT now()
);
-- Deduplicação: no máximo 1 evento do mesmo tipo por usuário, solução e dia (abrir 500 vezes = 1 visualização).
CREATE UNIQUE INDEX ux_solution_events_dedupe ON solution_events(solution_id, user_id, event_type, day) WHERE solution_id IS NOT NULL;
CREATE INDEX ix_solution_events ON solution_events(solution_id, event_type);

CREATE TABLE solution_search_log (
  id          bigserial PRIMARY KEY,
  user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  org_id      uuid REFERENCES organizations(id) ON DELETE CASCADE,
  query_sha256 text NOT NULL,
  parser_version text NOT NULL,
  mode        text NOT NULL,
  intent      jsonb NOT NULL DEFAULT '{}',
  result_count integer NOT NULL,
  ai_used     boolean NOT NULL DEFAULT false,
  at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_solution_search_log ON solution_search_log(user_id, at);

CREATE TABLE solution_preferences (
  user_id     uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  personalization_opt_in boolean NOT NULL DEFAULT false,
  updated_at  timestamptz NOT NULL DEFAULT now()
);
-- Tese do financiador para soluções (extensão de funder_profiles)
CREATE TABLE funder_solution_prefs (
  org_id       uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  populations  text[] NOT NULL DEFAULT '{}',
  kinds        text[] NOT NULL DEFAULT '{}' CHECK (kinds <@ ARRAY['project','idea','methodology','social_tech','academic']),
  horizon_months integer CHECK (horizon_months BETWEEN 1 AND 240),
  prefer_proven boolean NOT NULL DEFAULT false,
  risk_tolerance text CHECK (risk_tolerance IN ('low','medium','high')),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE solution_adaptations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  solution_id uuid NOT NULL REFERENCES solutions(id) ON DELETE CASCADE,
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id),
  inputs      jsonb NOT NULL,
  result      jsonb NOT NULL,
  engine_version text NOT NULL,
  status      text NOT NULL DEFAULT 'suggested_needs_validation' CHECK (status IN ('suggested_needs_validation','validated_by_human','discarded')),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE solution_combinations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id     uuid NOT NULL REFERENCES users(id),
  title       text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  solution_ids uuid[] NOT NULL CHECK (array_length(solution_ids,1) BETWEEN 2 AND 4),
  analysis    jsonb NOT NULL,
  engine_version text NOT NULL,
  status      text NOT NULL DEFAULT 'suggestion_needs_review' CHECK (status IN ('suggestion_needs_review','reviewed','discarded')),
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Agregados públicos sem expor identidades (SECURITY DEFINER; só devolvem contagens de organizações distintas).
CREATE FUNCTION solution_public_stats(sid uuid) RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT CASE WHEN NOT app_authenticated() OR NOT EXISTS (SELECT 1 FROM solutions s WHERE s.id = sid AND (s.visibility = 'published' OR s.org_id = app_org() OR app_priv())) THEN NULL ELSE
  jsonb_build_object(
    'interested_orgs',  (SELECT count(*) FROM solution_intents i WHERE i.solution_id = sid AND i.stage IN ('interested','reviewing','requested_info','requested_adaptation','negotiating','commitment_started','funded','implementing','completed')),
    'requested_info_orgs', (SELECT count(DISTINCT r.requester_org_id) FROM solution_requests r WHERE r.solution_id = sid AND r.kind IN ('info','contact','budget')),
    'in_evaluation_orgs', (SELECT count(*) FROM solution_intents i WHERE i.solution_id = sid AND i.stage IN ('reviewing','negotiating','commitment_started')),
    'adaptation_requests', (SELECT count(DISTINCT r.requester_org_id) FROM solution_requests r WHERE r.solution_id = sid AND r.kind = 'adaptation'),
    'funded_confirmed_orgs', (SELECT count(*) FROM solution_intents i WHERE i.solution_id = sid AND i.confirmed_by_author AND i.stage IN ('funded','implementing','completed')),
    'replications', jsonb_build_object(
        'interested', (SELECT count(*) FROM solution_replications x WHERE x.solution_id = sid AND x.status IN ('interested','info_requested','adaptation_requested')),
        'started', (SELECT count(*) FROM solution_replications x WHERE x.solution_id = sid AND x.status = 'started'),
        'completed_confirmed', (SELECT count(*) FROM solution_replications x WHERE x.solution_id = sid AND x.status = 'completed' AND x.author_confirmed),
        'destinations', (SELECT coalesce(jsonb_agg(DISTINCT x.target_uf), '[]'::jsonb) FROM solution_replications x WHERE x.solution_id = sid AND x.target_uf IS NOT NULL AND x.status <> 'cancelled')),
    'saves', (SELECT count(*) FROM solution_saves v WHERE v.solution_id = sid)) END
$$;
CREATE FUNCTION solution_funnel(sid uuid) RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT CASE WHEN NOT (app_priv() OR EXISTS (SELECT 1 FROM solutions s WHERE s.id = sid AND s.org_id = app_org())) THEN NULL ELSE
  (SELECT coalesce(jsonb_object_agg(event_type, n), '{}'::jsonb) FROM (SELECT event_type, count(DISTINCT coalesce(org_id, '00000000-0000-0000-0000-000000000000'::uuid)) AS n
     FROM solution_events WHERE solution_id = sid GROUP BY event_type) x) END
$$;
-- Agregados do mapa/ODS sobre soluções publicadas (contagens, sem identidades)
CREATE FUNCTION solution_aggregates() RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT CASE WHEN NOT app_authenticated() THEN NULL ELSE jsonb_build_object(
    'by_uf', (SELECT coalesce(jsonb_agg(jsonb_build_object('uf', uf, 'solutions', n) ORDER BY n DESC), '[]'::jsonb) FROM (SELECT uf, count(*) AS n FROM solutions WHERE visibility = 'published' AND uf IS NOT NULL GROUP BY uf) a),
    'by_ods', (SELECT coalesce(jsonb_agg(jsonb_build_object('ods', o, 'solutions', n) ORDER BY o), '[]'::jsonb) FROM (SELECT unnest(ods) AS o, count(*) AS n FROM solutions WHERE visibility = 'published' GROUP BY 1) b),
    'by_kind', (SELECT coalesce(jsonb_agg(jsonb_build_object('kind', kind, 'solutions', n)), '[]'::jsonb) FROM (SELECT kind, count(*) AS n FROM solutions WHERE visibility = 'published' GROUP BY kind) c)) END
$$;

-- ===========================================================================================
-- 5. RLS
-- ===========================================================================================
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['solutions','solution_versions','solution_people','solution_evidence','solution_results','solution_replication_profile','solution_relationships',
    'solution_saves','solution_requests','solution_intents','solution_intent_events','solution_replications','solution_reviews','solution_disputes','solution_events',
    'solution_search_log','solution_preferences','funder_solution_prefs','solution_adaptations','solution_combinations'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  END LOOP;
END $$;

CREATE POLICY solutions_read   ON solutions FOR SELECT USING ((app_authenticated() AND visibility = 'published') OR org_id = app_org() OR app_priv());
CREATE POLICY solutions_insert ON solutions FOR INSERT WITH CHECK ((org_id = app_org() AND created_by = app_uid() AND app_kind() <> 'platform') OR app_priv());
CREATE POLICY solutions_update ON solutions FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY solutions_delete ON solutions FOR DELETE USING ((org_id = app_org() AND visibility = 'draft') OR app_priv());

CREATE POLICY sversions_read ON solution_versions FOR SELECT USING (app_solution_owner(solution_id) OR app_priv());
CREATE POLICY sversions_write ON solution_versions FOR INSERT WITH CHECK (app_priv());

CREATE POLICY speople_read  ON solution_people FOR SELECT USING (app_solution_visible(solution_id) OR app_priv());
CREATE POLICY speople_write ON solution_people FOR ALL USING (app_solution_owner(solution_id) OR app_priv()) WITH CHECK (app_solution_owner(solution_id) OR app_priv());

CREATE POLICY sevidence_read  ON solution_evidence FOR SELECT USING (app_solution_visible(solution_id) OR app_priv());
CREATE POLICY sevidence_write ON solution_evidence FOR ALL USING (app_solution_owner(solution_id) OR app_priv()) WITH CHECK ((org_id = app_org() AND app_solution_owner(solution_id)) OR app_priv());
CREATE POLICY sresults_read  ON solution_results FOR SELECT USING (app_solution_visible(solution_id) OR app_priv());
CREATE POLICY sresults_write ON solution_results FOR ALL USING (app_solution_owner(solution_id) OR app_priv()) WITH CHECK (app_solution_owner(solution_id) OR app_priv());
CREATE POLICY sreplprof_read  ON solution_replication_profile FOR SELECT USING (app_solution_visible(solution_id) OR app_priv());
CREATE POLICY sreplprof_write ON solution_replication_profile FOR ALL USING (app_solution_owner(solution_id) OR app_priv()) WITH CHECK (app_solution_owner(solution_id) OR app_priv());
CREATE POLICY srel_read  ON solution_relationships FOR SELECT USING (app_solution_visible(from_id) OR app_priv());
CREATE POLICY srel_write ON solution_relationships FOR ALL USING (created_by_org = app_org() OR app_priv()) WITH CHECK ((created_by_org = app_org() AND app_solution_owner(from_id)) OR app_priv());

CREATE POLICY ssaves_all ON solution_saves FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK ((user_id = app_uid() AND org_id = app_org() AND app_solution_visible(solution_id)) OR app_priv());

CREATE POLICY sreq_read   ON solution_requests FOR SELECT USING (requester_org_id = app_org() OR app_solution_owner(solution_id) OR app_priv());
CREATE POLICY sreq_insert ON solution_requests FOR INSERT WITH CHECK ((requester_org_id = app_org() AND requester_user_id = app_uid() AND app_solution_visible(solution_id)
                                                                       AND NOT app_solution_owner(solution_id) AND NOT app_blocked_between(requester_org_id, (SELECT s.org_id FROM solutions s WHERE s.id = solution_id))) OR app_priv());
CREATE POLICY sreq_update ON solution_requests FOR UPDATE USING (requester_org_id = app_org() OR app_solution_owner(solution_id) OR app_priv())
  WITH CHECK (requester_org_id = app_org() OR app_solution_owner(solution_id) OR app_priv());

-- Autor só enxerga a identidade do financiador se ele a tornou pública OU fez um pedido direto ao autor.
CREATE POLICY sintent_read ON solution_intents FOR SELECT USING (org_id = app_org() OR app_priv()
  OR (app_solution_owner(solution_id) AND (public_identity OR EXISTS (SELECT 1 FROM solution_requests r WHERE r.solution_id = solution_intents.solution_id AND r.requester_org_id = solution_intents.org_id))));
CREATE POLICY sintent_insert ON solution_intents FOR INSERT WITH CHECK ((org_id = app_org() AND user_id = app_uid() AND app_solution_visible(solution_id) AND NOT app_solution_owner(solution_id)) OR app_priv());
CREATE POLICY sintent_update ON solution_intents FOR UPDATE USING (org_id = app_org() OR app_solution_owner(solution_id) OR app_priv()) WITH CHECK (org_id = app_org() OR app_solution_owner(solution_id) OR app_priv());
CREATE POLICY sintev_read ON solution_intent_events FOR SELECT USING (actor_org_id = app_org() OR app_priv()
  OR EXISTS (SELECT 1 FROM solution_intents i WHERE i.id = intent_id AND (i.org_id = app_org() OR app_solution_owner(i.solution_id))));
CREATE POLICY sintev_insert ON solution_intent_events FOR INSERT WITH CHECK (actor_org_id = app_org() OR app_priv());

CREATE POLICY srepl_read   ON solution_replications FOR SELECT USING (replicator_org_id = app_org() OR app_solution_owner(solution_id) OR app_priv());
CREATE POLICY srepl_insert ON solution_replications FOR INSERT WITH CHECK ((replicator_org_id = app_org() AND app_solution_visible(solution_id) AND NOT app_solution_owner(solution_id)) OR app_priv());
CREATE POLICY srepl_update ON solution_replications FOR UPDATE USING (replicator_org_id = app_org() OR app_solution_owner(solution_id) OR app_priv())
  WITH CHECK (replicator_org_id = app_org() OR app_solution_owner(solution_id) OR app_priv());

CREATE POLICY srev_read   ON solution_reviews FOR SELECT USING (app_solution_visible(solution_id) OR app_priv());
CREATE POLICY srev_insert ON solution_reviews FOR INSERT WITH CHECK ((org_id = app_org() AND user_id = app_uid() AND app_solution_reviewable(solution_id)) OR app_priv());
CREATE POLICY srev_update ON solution_reviews FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY srev_delete ON solution_reviews FOR DELETE USING (org_id = app_org() OR app_priv());

CREATE POLICY sdisp_read   ON solution_disputes FOR SELECT USING (claimant_org_id = app_org() OR app_solution_owner(solution_id) OR app_priv());
CREATE POLICY sdisp_insert ON solution_disputes FOR INSERT WITH CHECK ((claimant_org_id = app_org() AND claimant_user_id = app_uid() AND app_solution_visible(solution_id) AND NOT app_solution_owner(solution_id)) OR app_priv());
CREATE POLICY sdisp_update ON solution_disputes FOR UPDATE USING (claimant_org_id = app_org() OR app_priv()) WITH CHECK (claimant_org_id = app_org() OR app_priv());

CREATE POLICY sevents_read   ON solution_events FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY sevents_insert ON solution_events FOR INSERT WITH CHECK ((user_id = app_uid() AND org_id = app_org()) OR app_priv());
CREATE POLICY slog_read   ON solution_search_log FOR SELECT USING (user_id = app_uid() OR app_priv());
CREATE POLICY slog_delete ON solution_search_log FOR DELETE USING (user_id = app_uid() OR app_priv());
CREATE POLICY slog_insert ON solution_search_log FOR INSERT WITH CHECK ((user_id = app_uid() AND org_id = app_org()) OR app_priv());
CREATE POLICY sprefs_all ON solution_preferences FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY fprefs_all ON funder_solution_prefs FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY sadapt_all ON solution_adaptations FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK ((org_id = app_org() AND user_id = app_uid()) OR app_priv());
CREATE POLICY scomb_all ON solution_combinations FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK ((org_id = app_org() AND user_id = app_uid()) OR app_priv());

-- Fluxos controlados da intenção de financiamento (SECURITY DEFINER = o "fluxo de pedidos" e a "confirmação do autor"; o gatilho de guarda
-- libera apenas estes caminhos). Visualização nunca passa por aqui.
CREATE FUNCTION solution_stage_rank(s text) RETURNS integer LANGUAGE sql IMMUTABLE AS $$
  SELECT array_position(ARRAY['discovery','interested','reviewing','requested_info','requested_adaptation','negotiating','commitment_started','funded','implementing','completed'], s)
$$;
CREATE FUNCTION solution_advance_intent(sid uuid, to_stage text) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE oid uuid := app_org(); prev text; iid uuid; newst text;
BEGIN
  IF NOT app_authenticated() OR oid IS NULL THEN RAISE EXCEPTION 'não autenticado' USING ERRCODE = '42501'; END IF;
  IF to_stage NOT IN ('requested_info','requested_adaptation') THEN RAISE EXCEPTION 'estágio inválido para este fluxo' USING ERRCODE = '42501'; END IF;
  IF NOT EXISTS (SELECT 1 FROM solutions s WHERE s.id = sid AND s.visibility = 'published' AND s.org_id <> oid) THEN RAISE EXCEPTION 'solução indisponível' USING ERRCODE = '42501'; END IF;
  IF NOT EXISTS (SELECT 1 FROM solution_requests r WHERE r.solution_id = sid AND r.requester_org_id = oid
                 AND ((to_stage = 'requested_info' AND r.kind IN ('info','contact','budget')) OR (to_stage = 'requested_adaptation' AND r.kind = 'adaptation'))) THEN
    RAISE EXCEPTION 'não há pedido correspondente' USING ERRCODE = '42501';
  END IF;
  SELECT id, stage INTO iid, prev FROM solution_intents WHERE solution_id = sid AND org_id = oid;
  IF iid IS NULL THEN
    INSERT INTO solution_intents(solution_id, org_id, user_id, stage) VALUES (sid, oid, app_uid(), to_stage) RETURNING id, stage INTO iid, newst;
    INSERT INTO solution_intent_events(intent_id, from_stage, to_stage, actor_org_id) VALUES (iid, NULL, newst, oid);
  ELSIF solution_stage_rank(to_stage) > solution_stage_rank(prev) THEN
    UPDATE solution_intents SET stage = to_stage, updated_at = now() WHERE id = iid RETURNING stage INTO newst;
    INSERT INTO solution_intent_events(intent_id, from_stage, to_stage, actor_org_id) VALUES (iid, prev, newst, oid);
  ELSE newst := prev; END IF;
  RETURN newst;
END $$;
CREATE FUNCTION solution_author_set_intent(iid uuid, to_stage text) RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE i solution_intents%ROWTYPE;
BEGIN
  SELECT * INTO i FROM solution_intents WHERE id = iid;
  IF NOT FOUND OR NOT app_solution_owner(i.solution_id) THEN RAISE EXCEPTION 'intenção não encontrada' USING ERRCODE = '42501'; END IF;
  IF to_stage NOT IN ('negotiating','commitment_started','funded','implementing','completed') THEN RAISE EXCEPTION 'estágio inválido' USING ERRCODE = '42501'; END IF;
  IF NOT EXISTS (SELECT 1 FROM solution_requests r WHERE r.solution_id = i.solution_id AND r.requester_org_id = i.org_id AND r.status = 'accepted') THEN
    RAISE EXCEPTION 'o autor só confirma etapas avançadas após aceitar um pedido do financiador' USING ERRCODE = '42501';
  END IF;
  IF solution_stage_rank(to_stage) <= solution_stage_rank(i.stage) THEN RAISE EXCEPTION 'a etapa só avança' USING ERRCODE = '42501'; END IF;
  UPDATE solution_intents SET stage = to_stage, confirmed_by_author = true, updated_at = now() WHERE id = iid;
  INSERT INTO solution_intent_events(intent_id, from_stage, to_stage, actor_org_id) VALUES (iid, i.stage, to_stage, app_org());
  RETURN to_stage;
END $$;

-- Privilégios (mesmo modelo): append-only reforçado para versões e eventos de intenção
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO impacto_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit_events, ledger_entries, signatures, application_transitions, payment_events, solution_versions, solution_intent_events FROM impacto_app;
REVOKE INSERT ON solution_versions FROM impacto_app;
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
