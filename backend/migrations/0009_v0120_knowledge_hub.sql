-- 0009 — v0.12.0: Central de Conhecimento e Operações (conhecimento + academia + eventos + suporte + parcerias + demonstração/solicitação de teste + boletim).
-- Reutiliza: users/organizations/memberships, notifications (app_notify), documents (anexos), drafts (modelos preenchíveis), org_trials (monetização),
-- audit_events. NÃO duplica: `materials` (publicação por organização) continua separada do conteúdo OFICIAL da plataforma (kb_*).
-- Princípios: conteúdo institucional só é publicado por revisão de OUTRA pessoa (quatro olhos); versões nunca são sobrescritas; origem do conteúdo
-- (oficial × educacional × terceiros) é sempre explícita; conteúdo regulatório exige fonte e data; dados de contato só com consentimento e finalidade.

-- ------------------------------------------------------------------------------------------------ pessoal interno (papéis editoriais/suporte)
CREATE TABLE staff_roles (
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role       text NOT NULL CHECK (role IN ('editor','reviewer','support')),
  granted_by uuid REFERENCES users(id),
  granted_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, role)
);

-- ------------------------------------------------------------------------------------------------ visibilidade (RBAC/ABAC do conteúdo)
-- public = qualquer pessoa; authenticated = qualquer usuária autenticada; audience = só os tipos de organização listados em `audience`.
CREATE FUNCTION kb_visible(vis text, aud text[]) RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT vis = 'public' OR (app_authenticated() AND (vis = 'authenticated' OR coalesce(cardinality(aud), 0) = 0 OR app_kind() = ANY(aud)))
$$;

-- histórico editorial de qualquer conteúdo (nada é substituído em silêncio)
CREATE TABLE content_history (
  id          bigserial PRIMARY KEY,
  object_type text NOT NULL CHECK (object_type IN ('article_version','resource','faq','course','event','path')),
  object_id   uuid NOT NULL,
  from_status text,
  to_status   text NOT NULL,
  actor_id    uuid REFERENCES users(id),
  note        text CHECK (length(note) <= 1000),
  at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_content_history_obj ON content_history(object_type, object_id, at);

-- ------------------------------------------------------------------------------------------------ conhecimento: categorias, artigos/guias, versões
CREATE TABLE kb_categories (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{2,60}$'),
  name        text NOT NULL CHECK (length(name) BETWEEN 2 AND 120),
  description text CHECK (length(description) <= 500),
  sort        integer NOT NULL DEFAULT 100,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE kb_articles (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug             text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{3,100}$'),
  kind             text NOT NULL CHECK (kind IN ('start','how_it_works','guide','article','policy','glossary','procedure')),
  category_id      uuid REFERENCES kb_categories(id) ON DELETE SET NULL,
  audience         text[] NOT NULL DEFAULT '{}',
  visibility       text NOT NULL DEFAULT 'authenticated' CHECK (visibility IN ('public','authenticated','audience')),
  origin           text NOT NULL DEFAULT 'official' CHECK (origin IN ('official','educational','third_party')),
  tags             text[] NOT NULL DEFAULT '{}',
  ctx_keys         text[] NOT NULL DEFAULT '{}',          -- telas/campos onde a ajuda contextual aparece (ex.: project.budget)
  est_minutes      integer CHECK (est_minutes BETWEEN 1 AND 600),
  required_docs    text[] NOT NULL DEFAULT '{}',
  action_label     text CHECK (length(action_label) <= 80),
  action_link      text CHECK (action_link IS NULL OR action_link ~ '^/'),
  related_articles text[] NOT NULL DEFAULT '{}',
  related_resources text[] NOT NULL DEFAULT '{}',
  related_courses  text[] NOT NULL DEFAULT '{}',
  review_every_days integer NOT NULL DEFAULT 180 CHECK (review_every_days BETWEEN 7 AND 1095),
  demo             boolean NOT NULL DEFAULT false,         -- conteúdo de exemplo/rascunho: nunca é documento oficial
  -- cópia denormalizada da versão publicada (mantida por gatilho)
  live_version_id  uuid,
  title            text,
  summary          text,
  title_norm       text,
  search_doc       tsvector,
  published_at     timestamptz,
  last_reviewed_at timestamptz,
  view_count       bigint NOT NULL DEFAULT 0,
  created_by       uuid REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_kb_articles_search ON kb_articles USING gin (search_doc);
CREATE INDEX ix_kb_articles_title_trgm ON kb_articles USING gin (title_norm gin_trgm_ops);
CREATE INDEX ix_kb_articles_ctx ON kb_articles USING gin (ctx_keys);
CREATE INDEX ix_kb_articles_cat ON kb_articles(category_id, kind);

CREATE TABLE kb_article_versions (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  article_id         uuid NOT NULL REFERENCES kb_articles(id) ON DELETE CASCADE,
  version            integer NOT NULL CHECK (version >= 1),
  title              text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  summary            text CHECK (length(summary) <= 600),
  body               text NOT NULL CHECK (length(body) <= 60000),
  steps              jsonb NOT NULL DEFAULT '[]',          -- [{title, text}]
  checklist          jsonb NOT NULL DEFAULT '[]',          -- [texto]
  common_mistakes    jsonb NOT NULL DEFAULT '[]',
  refs               jsonb NOT NULL DEFAULT '[]',          -- [{label, url, source_date}]
  regulatory         boolean NOT NULL DEFAULT false,
  regulatory_source  text CHECK (length(regulatory_source) <= 500),
  regulatory_date    date,
  valid_until        date,
  status             text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','published','superseded','archived')),
  change_note        text CHECK (length(change_note) <= 500),
  author_id          uuid REFERENCES users(id),
  reviewed_by        uuid REFERENCES users(id),
  approved_by        uuid REFERENCES users(id),
  approved_at        timestamptz,
  published_at       timestamptz,
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (article_id, version),
  CHECK (approved_by IS NULL OR approved_by IS DISTINCT FROM author_id),                                   -- quatro olhos
  CHECK (status NOT IN ('approved','published') OR approved_by IS NOT NULL),
  CHECK (NOT regulatory OR status NOT IN ('approved','published') OR (regulatory_source IS NOT NULL AND regulatory_date IS NOT NULL))  -- regulatório: fonte e data
);
CREATE UNIQUE INDEX ux_kb_version_one_published ON kb_article_versions(article_id) WHERE status = 'published';

CREATE FUNCTION kb_sync_article() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NEW.status = 'published' THEN
    UPDATE kb_articles SET live_version_id = NEW.id, title = NEW.title, summary = NEW.summary, title_norm = lower(unaccent(NEW.title)),
      search_doc = setweight(to_tsvector('pt_unaccent', coalesce(NEW.title, '')), 'A') ||
                   setweight(to_tsvector('pt_unaccent', coalesce(NEW.summary, '') || ' ' || array_to_string(tags, ' ')), 'B') ||
                   setweight(to_tsvector('pt_unaccent', coalesce(NEW.body, '') || ' ' || coalesce(NEW.steps::text, '')), 'C'),
      published_at = coalesce(NEW.published_at, now()), last_reviewed_at = now(), updated_at = now()
    WHERE id = NEW.article_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_sync_article AFTER INSERT OR UPDATE OF status ON kb_article_versions FOR EACH ROW EXECUTE FUNCTION kb_sync_article();
-- arquivar/despublicar a versão ativa remove o conteúdo vivo
CREATE FUNCTION kb_unpublish_article() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF OLD.status = 'published' AND NEW.status IN ('archived') THEN
    UPDATE kb_articles SET live_version_id = NULL, search_doc = NULL, updated_at = now() WHERE id = NEW.article_id AND live_version_id = OLD.id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_unpublish AFTER UPDATE OF status ON kb_article_versions FOR EACH ROW EXECUTE FUNCTION kb_unpublish_article();
-- versões já revisadas não podem ter o conteúdo reescrito (só mudam de estado)
CREATE FUNCTION kb_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status <> 'draft' AND (NEW.body IS DISTINCT FROM OLD.body OR NEW.title IS DISTINCT FROM OLD.title OR NEW.steps IS DISTINCT FROM OLD.steps
     OR NEW.checklist IS DISTINCT FROM OLD.checklist OR NEW.summary IS DISTINCT FROM OLD.summary OR NEW.version IS DISTINCT FROM OLD.version
     OR NEW.article_id IS DISTINCT FROM OLD.article_id) THEN
    RAISE EXCEPTION 'versão fora de rascunho é imutável: crie uma nova versão' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_version_immutable BEFORE UPDATE ON kb_article_versions FOR EACH ROW EXECUTE FUNCTION kb_version_immutable();

-- ------------------------------------------------------------------------------------------------ recursos: documentos, modelos, checklists, vídeos, relatórios, boletins
CREATE TABLE kb_resources (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug            text NOT NULL CHECK (slug ~ '^[a-z0-9-]{3,100}$'),
  version         integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  kind            text NOT NULL CHECK (kind IN ('template','document','checklist','video','report','bulletin','spreadsheet','other')),
  category_id     uuid REFERENCES kb_categories(id) ON DELETE SET NULL,
  title           text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  summary         text CHECK (length(summary) <= 1000),
  audience        text[] NOT NULL DEFAULT '{}',
  visibility      text NOT NULL DEFAULT 'authenticated' CHECK (visibility IN ('public','authenticated','audience')),
  origin          text NOT NULL DEFAULT 'official' CHECK (origin IN ('official','educational','third_party')),
  tags            text[] NOT NULL DEFAULT '{}',
  url             text CHECK (url IS NULL OR url ~ '^https://'),
  document_id     uuid REFERENCES documents(id) ON DELETE SET NULL,   -- arquivo armazenado (passa pela varredura/URL temporária existentes)
  template_schema jsonb,           -- modelos preenchíveis: {draft_kind, fields:[{key,label,type,required,help}]}
  checklist_items jsonb NOT NULL DEFAULT '[]',
  duration_min    integer CHECK (duration_min BETWEEN 1 AND 1000),
  period_start    date,
  period_end      date,
  ods             smallint[] NOT NULL DEFAULT '{}',
  territories     text[] NOT NULL DEFAULT '{}',
  themes          text[] NOT NULL DEFAULT '{}',
  ctx_keys        text[] NOT NULL DEFAULT '{}',
  regulatory      boolean NOT NULL DEFAULT false,
  regulatory_source text CHECK (length(regulatory_source) <= 500),
  regulatory_date date,
  valid_until     date,
  status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','published','superseded','archived')),
  change_note     text CHECK (length(change_note) <= 500),
  author_id       uuid REFERENCES users(id),
  approved_by     uuid REFERENCES users(id),
  approved_at     timestamptz,
  published_at    timestamptz,
  last_reviewed_at timestamptz,
  review_every_days integer NOT NULL DEFAULT 365 CHECK (review_every_days BETWEEN 7 AND 1095),
  demo            boolean NOT NULL DEFAULT false,
  download_count  bigint NOT NULL DEFAULT 0,
  title_norm      text,
  search_doc      tsvector,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (slug, version),
  CHECK (approved_by IS NULL OR approved_by IS DISTINCT FROM author_id),
  CHECK (status NOT IN ('approved','published') OR approved_by IS NOT NULL),
  CHECK (NOT regulatory OR status NOT IN ('approved','published') OR (regulatory_source IS NOT NULL AND regulatory_date IS NOT NULL)),
  CHECK (url IS NOT NULL OR document_id IS NOT NULL OR template_schema IS NOT NULL OR jsonb_array_length(checklist_items) > 0 OR status = 'draft')
);
CREATE UNIQUE INDEX ux_kb_resource_one_published ON kb_resources(slug) WHERE status = 'published';
CREATE INDEX ix_kb_resources_search ON kb_resources USING gin (search_doc);
CREATE INDEX ix_kb_resources_title_trgm ON kb_resources USING gin (title_norm gin_trgm_ops);
CREATE INDEX ix_kb_resources_kind ON kb_resources(kind, status, published_at DESC);

CREATE FUNCTION kb_index_row() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.title_norm := lower(unaccent(NEW.title));
  IF TG_TABLE_NAME = 'kb_resources' THEN
    NEW.search_doc := setweight(to_tsvector('pt_unaccent', coalesce(NEW.title, '')), 'A') ||
                      setweight(to_tsvector('pt_unaccent', coalesce(NEW.summary, '') || ' ' || array_to_string(NEW.tags, ' ') || ' ' || array_to_string(NEW.themes, ' ')), 'B');
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_resources_index BEFORE INSERT OR UPDATE OF title, summary, tags, themes ON kb_resources FOR EACH ROW EXECUTE FUNCTION kb_index_row();

CREATE FUNCTION kb_resource_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status <> 'draft' AND (NEW.title IS DISTINCT FROM OLD.title OR NEW.url IS DISTINCT FROM OLD.url OR NEW.document_id IS DISTINCT FROM OLD.document_id
     OR NEW.template_schema IS DISTINCT FROM OLD.template_schema OR NEW.checklist_items IS DISTINCT FROM OLD.checklist_items
     OR NEW.version IS DISTINCT FROM OLD.version OR NEW.slug IS DISTINCT FROM OLD.slug) THEN
    RAISE EXCEPTION 'recurso fora de rascunho é imutável: crie uma nova versão' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_resource_immutable BEFORE UPDATE ON kb_resources FOR EACH ROW EXECUTE FUNCTION kb_resource_immutable();

-- ------------------------------------------------------------------------------------------------ FAQ + feedback ("Este conteúdo ajudou?")
CREATE TABLE kb_faqs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  category_id      uuid REFERENCES kb_categories(id) ON DELETE SET NULL,
  question         text NOT NULL CHECK (length(question) BETWEEN 5 AND 300),
  answer           text NOT NULL CHECK (length(answer) BETWEEN 5 AND 8000),
  audience         text[] NOT NULL DEFAULT '{}',
  visibility       text NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','authenticated','audience')),
  origin           text NOT NULL DEFAULT 'official' CHECK (origin IN ('official','educational','third_party')),
  tags             text[] NOT NULL DEFAULT '{}',
  ctx_keys         text[] NOT NULL DEFAULT '{}',
  related_article  text,
  revises_id       uuid REFERENCES kb_faqs(id) ON DELETE SET NULL,   -- revisão de uma FAQ publicada: a antiga só é arquivada quando a nova é publicada
  status           text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','published','archived')),
  author_id        uuid REFERENCES users(id),
  approved_by      uuid REFERENCES users(id),
  approved_at      timestamptz,
  published_at     timestamptz,
  last_reviewed_at timestamptz,
  review_every_days integer NOT NULL DEFAULT 180 CHECK (review_every_days BETWEEN 7 AND 1095),
  helpful_yes      integer NOT NULL DEFAULT 0,
  helpful_no       integer NOT NULL DEFAULT 0,
  sort             integer NOT NULL DEFAULT 100,
  demo             boolean NOT NULL DEFAULT false,
  title_norm       text,
  search_doc       tsvector,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (approved_by IS NULL OR approved_by IS DISTINCT FROM author_id),
  CHECK (status NOT IN ('approved','published') OR approved_by IS NOT NULL)
);
CREATE INDEX ix_kb_faqs_search ON kb_faqs USING gin (search_doc);
CREATE INDEX ix_kb_faqs_title_trgm ON kb_faqs USING gin (title_norm gin_trgm_ops);
CREATE FUNCTION kb_faq_index() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.title_norm := lower(unaccent(NEW.question));
  NEW.search_doc := setweight(to_tsvector('pt_unaccent', NEW.question), 'A') || setweight(to_tsvector('pt_unaccent', NEW.answer || ' ' || array_to_string(NEW.tags, ' ')), 'C');
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_faq_index BEFORE INSERT OR UPDATE ON kb_faqs FOR EACH ROW EXECUTE FUNCTION kb_faq_index();

CREATE TABLE kb_feedback (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id      uuid REFERENCES organizations(id) ON DELETE SET NULL,
  target_type text NOT NULL CHECK (target_type IN ('article','faq','resource','course','lesson','event')),
  target_id   uuid NOT NULL,
  helpful     boolean NOT NULL,
  reason      text CHECK (reason IN ('not_found','hard_to_understand','outdated','need_support','other')),
  comment     text CHECK (length(comment) <= 1000),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, target_type, target_id),
  CHECK (helpful OR reason IS NOT NULL)          -- "Não ajudou" pede o motivo
);
CREATE FUNCTION kb_feedback_rollup() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NEW.target_type = 'faq' THEN
    UPDATE kb_faqs SET helpful_yes = (SELECT count(*) FROM kb_feedback WHERE target_type = 'faq' AND target_id = NEW.target_id AND helpful),
                       helpful_no = (SELECT count(*) FROM kb_feedback WHERE target_type = 'faq' AND target_id = NEW.target_id AND NOT helpful)
    WHERE id = NEW.target_id;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_feedback_rollup AFTER INSERT OR UPDATE ON kb_feedback FOR EACH ROW EXECUTE FUNCTION kb_feedback_rollup();

-- progresso de checklists (por pessoa e, opcionalmente, por projeto)
CREATE TABLE kb_checklist_progress (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id     uuid REFERENCES organizations(id) ON DELETE CASCADE,
  scope      text NOT NULL CHECK (scope ~ '^[a-z0-9:_-]{3,140}$'),     -- ex.: article:como-cadastrar-projeto | resource:checklist-projeto
  project_id uuid REFERENCES projects(id) ON DELETE CASCADE,
  checked    integer[] NOT NULL DEFAULT '{}',
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX ux_kb_checklist ON kb_checklist_progress(user_id, scope, coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- analytics do conhecimento (sem texto livre: hash + conceitos; ADR-043)
CREATE TABLE kb_events (
  id           bigserial PRIMARY KEY,
  at           timestamptz NOT NULL DEFAULT now(),
  kind         text NOT NULL CHECK (kind IN ('view','search','search_empty','download','ctx_open','assistant','assistant_empty','ticket_from_help')),
  user_id      uuid,
  org_kind     text,
  target_type  text,
  target_id    uuid,
  q_hash       char(16),
  concepts     text[] NOT NULL DEFAULT '{}',
  result_count integer,
  ctx_key      text CHECK (length(ctx_key) <= 80)
);
CREATE INDEX ix_kb_events_kind ON kb_events(kind, at DESC);
CREATE INDEX ix_kb_events_target ON kb_events(target_type, target_id);
CREATE FUNCTION kb_log(p_kind text, p_target_type text, p_target uuid, p_q_hash text, p_concepts text[], p_count integer, p_ctx text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  INSERT INTO kb_events(kind, user_id, org_kind, target_type, target_id, q_hash, concepts, result_count, ctx_key)
  VALUES (p_kind, app_uid(), app_kind(), p_target_type, p_target, left(p_q_hash, 16), coalesce(p_concepts, '{}'), p_count, left(p_ctx, 80));
  IF p_kind = 'view' AND p_target_type = 'article' THEN UPDATE kb_articles SET view_count = view_count + 1 WHERE id = p_target; END IF;
  IF p_kind = 'download' AND p_target_type = 'resource' THEN UPDATE kb_resources SET download_count = download_count + 1 WHERE id = p_target; END IF;
END $$;

-- ------------------------------------------------------------------------------------------------ Academia
CREATE TABLE courses (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug         text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{3,100}$'),
  title        text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  summary      text CHECK (length(summary) <= 1000),
  audience     text[] NOT NULL DEFAULT '{}',
  visibility   text NOT NULL DEFAULT 'authenticated' CHECK (visibility IN ('public','authenticated','audience')),
  origin       text NOT NULL DEFAULT 'official' CHECK (origin IN ('official','educational','third_party')),
  level        text NOT NULL DEFAULT 'beginner' CHECK (level IN ('beginner','intermediate','advanced')),
  hours        numeric(5,1) CHECK (hours > 0 AND hours <= 400),
  pass_score   smallint NOT NULL DEFAULT 70 CHECK (pass_score BETWEEN 0 AND 100),
  cert_enabled boolean NOT NULL DEFAULT false,
  tags         text[] NOT NULL DEFAULT '{}',
  version      integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  status       text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','published','archived')),
  author_id    uuid REFERENCES users(id),
  approved_by  uuid REFERENCES users(id),
  approved_at  timestamptz,
  published_at timestamptz,
  last_reviewed_at timestamptz,
  review_every_days integer NOT NULL DEFAULT 365 CHECK (review_every_days BETWEEN 7 AND 1095),
  demo         boolean NOT NULL DEFAULT false,
  title_norm   text,
  search_doc   tsvector,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (approved_by IS NULL OR approved_by IS DISTINCT FROM author_id),
  CHECK (status NOT IN ('approved','published') OR approved_by IS NOT NULL),
  CHECK (NOT cert_enabled OR hours IS NOT NULL)
);
CREATE INDEX ix_courses_search ON courses USING gin (search_doc);
CREATE FUNCTION kb_course_index() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.title_norm := lower(unaccent(NEW.title));
  NEW.search_doc := setweight(to_tsvector('pt_unaccent', NEW.title), 'A') || setweight(to_tsvector('pt_unaccent', coalesce(NEW.summary, '') || ' ' || array_to_string(NEW.tags, ' ')), 'B');
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_courses_index BEFORE INSERT OR UPDATE ON courses FOR EACH ROW EXECUTE FUNCTION kb_course_index();

CREATE TABLE course_modules (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id   uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  position    integer NOT NULL CHECK (position >= 1),
  title       text NOT NULL CHECK (length(title) BETWEEN 2 AND 200),
  description text CHECK (length(description) <= 1000),
  UNIQUE (course_id, position)
);
CREATE TABLE course_lessons (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  module_id  uuid NOT NULL REFERENCES course_modules(id) ON DELETE CASCADE,
  course_id  uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  position   integer NOT NULL CHECK (position >= 1),
  title      text NOT NULL CHECK (length(title) BETWEEN 2 AND 200),
  kind       text NOT NULL DEFAULT 'text' CHECK (kind IN ('text','video','quiz','activity')),
  body       text CHECK (length(body) <= 40000),
  video_url  text CHECK (video_url IS NULL OR video_url ~ '^https://'),
  captions_url text CHECK (captions_url IS NULL OR captions_url ~ '^https://'),    -- legendas (acessibilidade)
  transcript text CHECK (length(transcript) <= 40000),
  minutes    integer CHECK (minutes BETWEEN 1 AND 600),
  materials  jsonb NOT NULL DEFAULT '[]',                                           -- [{label, url | resource_slug}]
  quiz       jsonb NOT NULL DEFAULT '[]',                                           -- [{q, options[], explanation}] — SEM gabarito
  UNIQUE (module_id, position),
  CHECK (kind <> 'video' OR video_url IS NOT NULL)
);
-- gabarito separado: nunca é lido por usuárias (só a função de correção)
CREATE TABLE lesson_quiz_keys (
  lesson_id uuid PRIMARY KEY REFERENCES course_lessons(id) ON DELETE CASCADE,
  answers   integer[] NOT NULL
);
CREATE FUNCTION lesson_grade(p_lesson uuid, p_answers integer[]) RETURNS smallint LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE k integer[]; ok integer := 0; i integer;
BEGIN
  SELECT answers INTO k FROM lesson_quiz_keys WHERE lesson_id = p_lesson;
  IF k IS NULL OR cardinality(k) = 0 THEN RETURN NULL; END IF;
  FOR i IN 1..cardinality(k) LOOP
    IF i <= coalesce(cardinality(p_answers), 0) AND p_answers[i] = k[i] THEN ok := ok + 1; END IF;
  END LOOP;
  RETURN round(100.0 * ok / cardinality(k));
END $$;

CREATE TABLE course_enrollments (
  user_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  course_id      uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  org_id         uuid REFERENCES organizations(id) ON DELETE SET NULL,
  course_version integer NOT NULL,
  started_at     timestamptz NOT NULL DEFAULT now(),
  completed_at   timestamptz,
  last_lesson_id uuid REFERENCES course_lessons(id) ON DELETE SET NULL,
  PRIMARY KEY (user_id, course_id)
);
CREATE TABLE lesson_progress (
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  lesson_id    uuid NOT NULL REFERENCES course_lessons(id) ON DELETE CASCADE,
  course_id    uuid NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
  score        smallint CHECK (score BETWEEN 0 AND 100),
  attempts     integer NOT NULL DEFAULT 0,
  completed_at timestamptz,
  PRIMARY KEY (user_id, lesson_id)
);
CREATE TABLE course_certificates (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code          text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9]{12}$'),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id        uuid REFERENCES organizations(id) ON DELETE SET NULL,
  course_id     uuid NOT NULL REFERENCES courses(id),
  course_version integer NOT NULL,
  course_title  text NOT NULL,
  holder_name   text NOT NULL,
  hours         numeric(5,1) NOT NULL,
  issued_at     timestamptz NOT NULL DEFAULT now(),
  revoked_at    timestamptz,
  revoke_reason text CHECK (length(revoke_reason) <= 500),
  UNIQUE (user_id, course_id, course_version)
);

CREATE TABLE learning_paths (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{3,100}$'),
  title       text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  description text CHECK (length(description) <= 1000),
  audience    text[] NOT NULL DEFAULT '{}',
  visibility  text NOT NULL DEFAULT 'authenticated' CHECK (visibility IN ('public','authenticated','audience')),
  items       jsonb NOT NULL DEFAULT '[]',                 -- [{type: course|article|resource, slug, title}]
  status      text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
  author_id   uuid REFERENCES users(id),
  approved_by uuid REFERENCES users(id),
  demo        boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (approved_by IS NULL OR approved_by IS DISTINCT FROM author_id),
  CHECK (status <> 'published' OR approved_by IS NOT NULL OR author_id IS NULL)
);

-- ------------------------------------------------------------------------------------------------ Eventos
CREATE TABLE hub_events (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug          text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{3,100}$'),
  kind          text NOT NULL CHECK (kind IN ('webinar','training','workshop','oficina','mentoring','demo','institutional','community')),
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  description   text CHECK (length(description) <= 6000),
  starts_at     timestamptz NOT NULL,
  duration_min  integer NOT NULL CHECK (duration_min BETWEEN 5 AND 1440),
  speaker       text CHECK (length(speaker) <= 300),
  modality      text NOT NULL DEFAULT 'online' CHECK (modality IN ('online','in_person','hybrid')),
  location      text CHECK (length(location) <= 300),
  capacity      integer CHECK (capacity IS NULL OR capacity > 0),
  registration_open boolean NOT NULL DEFAULT true,
  audience      text[] NOT NULL DEFAULT '{}',
  visibility    text NOT NULL DEFAULT 'public' CHECK (visibility IN ('public','authenticated','audience')),
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','review','approved','published','cancelled','completed','archived')),
  recording_url text CHECK (recording_url IS NULL OR recording_url ~ '^https://'),
  recording_resource_id uuid REFERENCES kb_resources(id) ON DELETE SET NULL,
  materials     jsonb NOT NULL DEFAULT '[]',
  summary       text CHECK (length(summary) <= 4000),
  demo          boolean NOT NULL DEFAULT false,
  author_id     uuid REFERENCES users(id),
  approved_by   uuid REFERENCES users(id),
  approved_at   timestamptz,
  published_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (approved_by IS NULL OR approved_by IS DISTINCT FROM author_id),
  CHECK (status NOT IN ('approved','published','completed') OR approved_by IS NOT NULL OR author_id IS NULL),
  CHECK (modality = 'online' OR location IS NOT NULL)
);
CREATE INDEX ix_hub_events_when ON hub_events(starts_at) WHERE status IN ('published','completed');
-- link de acesso só para inscritas (e administração)
CREATE TABLE hub_event_links (
  event_id uuid PRIMARY KEY REFERENCES hub_events(id) ON DELETE CASCADE,
  join_url text NOT NULL CHECK (join_url ~ '^https://')
);
CREATE TABLE hub_event_registrations (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_id     uuid NOT NULL REFERENCES hub_events(id) ON DELETE CASCADE,
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id       uuid REFERENCES organizations(id) ON DELETE SET NULL,
  status       text NOT NULL DEFAULT 'registered' CHECK (status IN ('registered','waitlist','cancelled')),
  attended     boolean,
  satisfaction smallint CHECK (satisfaction BETWEEN 1 AND 5),
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (event_id, user_id)
);
CREATE INDEX ix_hub_event_reg_user ON hub_event_registrations(user_id, created_at DESC);
-- vagas: contagem para qualquer autenticada sem expor quem se inscreveu
CREATE FUNCTION hub_event_seats(p_event uuid) RETURNS integer LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT count(*)::int FROM hub_event_registrations WHERE event_id = p_event AND status = 'registered'
$$;

-- ------------------------------------------------------------------------------------------------ Suporte (tickets, SLA configurável)
CREATE TABLE support_sla (
  priority               text PRIMARY KEY CHECK (priority IN ('low','normal','high','critical')),
  first_response_minutes integer NOT NULL CHECK (first_response_minutes > 0),
  resolution_minutes     integer NOT NULL CHECK (resolution_minutes > 0),
  escalate_after_minutes integer NOT NULL CHECK (escalate_after_minutes > 0),
  updated_by             uuid REFERENCES users(id),
  updated_at             timestamptz NOT NULL DEFAULT now()
);
-- valores INICIAIS (hipótese operacional a validar com a equipe de suporte; configuráveis pela administração)
INSERT INTO support_sla VALUES ('low', 2880, 14400, 4320, NULL, now()), ('normal', 1440, 7200, 2160, NULL, now()),
  ('high', 480, 2880, 720, NULL, now()), ('critical', 60, 720, 120, NULL, now());

CREATE TABLE support_tickets (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  number             bigint GENERATED ALWAYS AS IDENTITY UNIQUE,
  org_id             uuid REFERENCES organizations(id) ON DELETE SET NULL,
  user_id            uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  category           text NOT NULL CHECK (category IN ('question','bug','technical','document','payment','compliance','project','funding','report','partnership','other')),
  priority           text NOT NULL DEFAULT 'normal' CHECK (priority IN ('low','normal','high','critical')),
  status             text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','waiting_user','waiting_internal','resolved','closed')),
  subject            text NOT NULL CHECK (length(subject) BETWEEN 3 AND 200),
  context            jsonb NOT NULL DEFAULT '{}',          -- {page, field, project_id, app} — apenas o necessário e permitido
  assigned_to        uuid REFERENCES users(id),
  first_response_due timestamptz,
  resolution_due     timestamptz,
  first_response_at  timestamptz,
  escalated_at       timestamptz,
  resolved_at        timestamptz,
  closed_at          timestamptz,
  satisfaction       smallint CHECK (satisfaction BETWEEN 1 AND 5),
  recurring          boolean NOT NULL DEFAULT false,
  kb_article_id      uuid REFERENCES kb_articles(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_tickets_user ON support_tickets(user_id, created_at DESC);
CREATE INDEX ix_tickets_queue ON support_tickets(status, priority, created_at) WHERE status NOT IN ('resolved','closed');
CREATE TABLE support_messages (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ticket_id   uuid NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  author_id   uuid REFERENCES users(id),
  author_kind text NOT NULL CHECK (author_kind IN ('user','staff','system')),
  body        text NOT NULL CHECK (length(body) BETWEEN 1 AND 8000),
  internal    boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (NOT internal OR author_kind = 'staff')
);
CREATE INDEX ix_support_messages_ticket ON support_messages(ticket_id, created_at);
CREATE TABLE support_attachments (
  ticket_id   uuid NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
  message_id  uuid REFERENCES support_messages(id) ON DELETE CASCADE,
  document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  PRIMARY KEY (ticket_id, document_id)
);

-- usuária só pode: criar; reabrir/encerrar o que já foi resolvido; avaliar. Prioridade, SLA, responsável e demais estados são da equipe.
CREATE FUNCTION support_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT app_priv() THEN
    IF TG_OP = 'INSERT' THEN
      NEW.status := 'open'; NEW.assigned_to := NULL; NEW.first_response_at := NULL; NEW.resolved_at := NULL; NEW.closed_at := NULL;
      NEW.escalated_at := NULL; NEW.recurring := false; NEW.kb_article_id := NULL; NEW.satisfaction := NULL;
      IF NEW.priority NOT IN ('low','normal') THEN NEW.priority := 'normal'; END IF;     -- urgência alta/crítica só é definida pela equipe
    ELSE
      IF NEW.user_id IS DISTINCT FROM OLD.user_id OR NEW.priority IS DISTINCT FROM OLD.priority OR NEW.assigned_to IS DISTINCT FROM OLD.assigned_to
         OR NEW.category IS DISTINCT FROM OLD.category OR NEW.subject IS DISTINCT FROM OLD.subject OR NEW.first_response_due IS DISTINCT FROM OLD.first_response_due
         OR NEW.resolution_due IS DISTINCT FROM OLD.resolution_due OR NEW.kb_article_id IS DISTINCT FROM OLD.kb_article_id OR NEW.recurring IS DISTINCT FROM OLD.recurring
         OR NEW.first_response_at IS DISTINCT FROM OLD.first_response_at OR NEW.resolved_at IS DISTINCT FROM OLD.resolved_at OR NEW.escalated_at IS DISTINCT FROM OLD.escalated_at THEN
        RAISE EXCEPTION 'chamado só pode ser alterado pela equipe de suporte' USING ERRCODE = '42501';
      END IF;
      IF NEW.status IS DISTINCT FROM OLD.status AND NOT ((OLD.status IN ('waiting_user','resolved') AND NEW.status = 'open') OR (OLD.status = 'resolved' AND NEW.status = 'closed')) THEN
        RAISE EXCEPTION 'transição de estado não permitida para a usuária' USING ERRCODE = '42501';
      END IF;
      IF NEW.satisfaction IS DISTINCT FROM OLD.satisfaction AND OLD.status NOT IN ('resolved','closed') THEN
        RAISE EXCEPTION 'avalie o atendimento após a resolução' USING ERRCODE = '42501';
      END IF;
      IF NEW.status = 'closed' AND OLD.status <> 'closed' THEN NEW.closed_at := now(); END IF;
      IF NEW.status = 'open' AND OLD.status IN ('resolved') THEN NEW.resolved_at := NULL; END IF;
    END IF;
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_support_guard BEFORE INSERT OR UPDATE ON support_tickets FOR EACH ROW EXECUTE FUNCTION support_guard();
CREATE FUNCTION support_msg_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NOT app_priv() THEN NEW.author_kind := 'user'; NEW.internal := false; NEW.author_id := app_uid(); END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_support_msg_guard BEFORE INSERT ON support_messages FOR EACH ROW EXECUTE FUNCTION support_msg_guard();

-- ------------------------------------------------------------------------------------------------ Parcerias (pipeline), demonstração e solicitação de teste
CREATE TABLE partnership_requests (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES users(id) ON DELETE SET NULL,
  org_id          uuid REFERENCES organizations(id) ON DELETE SET NULL,
  org_name        text NOT NULL CHECK (length(org_name) BETWEEN 2 AND 200),
  contact_name    text NOT NULL CHECK (length(contact_name) BETWEEN 2 AND 200),
  contact_email   citext NOT NULL CHECK (length(contact_email) <= 254),
  contact_phone   text CHECK (length(contact_phone) <= 40),
  kind            text NOT NULL CHECK (kind IN ('institutional','academic','government','business','technology','osc','media','research','training','distribution','territorial')),
  objective       text NOT NULL CHECK (length(objective) BETWEEN 10 AND 3000),
  proposal        text CHECK (length(proposal) <= 6000),
  territory       text CHECK (length(territory) <= 300),
  audience        text CHECK (length(audience) <= 500),
  resources_offered text CHECK (length(resources_offered) <= 2000),
  counterpart     text CHECK (length(counterpart) <= 2000),
  target_date     date,
  status          text NOT NULL DEFAULT 'received' CHECK (status IN ('received','qualification','contact','meeting','proposal','negotiation','approved','active','completed','archived','rejected')),
  owner_id        uuid REFERENCES users(id),
  consent_at      timestamptz NOT NULL DEFAULT now(),
  consent_version text NOT NULL DEFAULT 'contact-v1',
  last_activity_at timestamptz NOT NULL DEFAULT now(),
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_partnership_status ON partnership_requests(status, last_activity_at DESC);
CREATE TABLE partnership_activities (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id  uuid NOT NULL REFERENCES partnership_requests(id) ON DELETE CASCADE,
  kind        text NOT NULL CHECK (kind IN ('note','status','meeting','proposal','email')),
  body        text CHECK (length(body) <= 4000),
  from_status text,
  to_status   text,
  author_id   uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE partnerships (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id  uuid NOT NULL UNIQUE REFERENCES partnership_requests(id),
  name        text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
  kind        text NOT NULL,
  scope       text CHECK (length(scope) <= 3000),
  starts_on   date,
  ends_on     date,
  status      text NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','suspended')),
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  CHECK (ends_on IS NULL OR starts_on IS NULL OR ends_on >= starts_on)
);

CREATE TABLE demo_requests (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  org_id         uuid REFERENCES organizations(id) ON DELETE SET NULL,
  org_name       text NOT NULL CHECK (length(org_name) BETWEEN 2 AND 200),
  contact_name   text NOT NULL CHECK (length(contact_name) BETWEEN 2 AND 200),
  contact_email  citext NOT NULL CHECK (length(contact_email) <= 254),
  contact_phone  text CHECK (length(contact_phone) <= 40),
  audience_kind  text NOT NULL CHECK (audience_kind IN ('osc','company','individual','provider','government','other')),
  org_size       text CHECK (org_size IN ('1-10','11-50','51-200','200+')),
  interest       text CHECK (length(interest) <= 1000),
  preferred_slots timestamptz[] NOT NULL DEFAULT '{}' CHECK (cardinality(preferred_slots) <= 3),
  notes          text CHECK (length(notes) <= 2000),
  status         text NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','scheduled','done','cancelled')),
  scheduled_at   timestamptz,
  meeting_url    text CHECK (meeting_url IS NULL OR meeting_url ~ '^https://'),
  handled_by     uuid REFERENCES users(id),
  consent_at     timestamptz NOT NULL DEFAULT now(),
  consent_version text NOT NULL DEFAULT 'contact-v1',
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (status <> 'scheduled' OR scheduled_at IS NOT NULL)
);
CREATE INDEX ix_demo_status ON demo_requests(status, created_at DESC);

-- Solicitação de teste: o acesso NUNCA é concedido automaticamente; a decisão (com motivo) usa o mecanismo de trial da monetização (org_trials).
CREATE TABLE trial_requests (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  org_kind      text NOT NULL,
  users_count   integer NOT NULL CHECK (users_count BETWEEN 1 AND 10000),
  purpose       text NOT NULL CHECK (length(purpose) BETWEEN 10 AND 2000),
  modules       text[] NOT NULL DEFAULT '{}',
  period_days   integer NOT NULL CHECK (period_days BETWEEN 7 AND 60),
  responsible   text NOT NULL CHECK (length(responsible) BETWEEN 2 AND 200),
  status        text NOT NULL DEFAULT 'requested' CHECK (status IN ('requested','approved','rejected','cancelled')),
  decided_by    uuid REFERENCES users(id),
  decided_at    timestamptz,
  decision_reason text CHECK (length(decision_reason) <= 1000),
  outcome       text CHECK (outcome IN ('trial_started','trial_extended','not_applicable')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  CHECK (status NOT IN ('approved','rejected') OR (decided_by IS NOT NULL AND decision_reason IS NOT NULL))
);
CREATE UNIQUE INDEX ux_trial_requests_open ON trial_requests(org_id) WHERE status = 'requested';

-- ------------------------------------------------------------------------------------------------ boletim e preferências
CREATE TABLE newsletter_subscriptions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid REFERENCES users(id) ON DELETE CASCADE,
  email        citext NOT NULL UNIQUE CHECK (length(email) <= 254),
  topics       text[] NOT NULL DEFAULT '{platform}' CHECK (topics <@ ARRAY['platform','opportunities','events','legislation','technology','esg','ods','cases','trends','results']),
  frequency    text NOT NULL DEFAULT 'monthly' CHECK (frequency IN ('weekly','monthly')),
  status       text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','unsubscribed')),
  token_hash   char(64) NOT NULL,
  consent_at   timestamptz NOT NULL DEFAULT now(),
  confirmed_at timestamptz,
  unsubscribed_at timestamptz,
  last_sent_at timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_newsletter_active ON newsletter_subscriptions(frequency, last_sent_at) WHERE status = 'active';
CREATE FUNCTION newsletter_confirm(p_hash text) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
  UPDATE newsletter_subscriptions SET status = 'active', confirmed_at = coalesce(confirmed_at, now()), unsubscribed_at = NULL
  WHERE token_hash = p_hash AND status IN ('pending','active');
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n > 0;
END $$;
CREATE FUNCTION newsletter_unsubscribe(p_hash text) RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE n integer;
BEGIN
  UPDATE newsletter_subscriptions SET status = 'unsubscribed', unsubscribed_at = now() WHERE token_hash = p_hash AND status <> 'unsubscribed';
  GET DIAGNOSTICS n = ROW_COUNT;
  RETURN n > 0;
END $$;

CREATE TABLE notification_prefs (
  user_id   uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  grp       text NOT NULL CHECK (grp IN ('billing','content','events','support','partnerships','opportunities')),
  in_app    boolean NOT NULL DEFAULT true,
  email     boolean NOT NULL DEFAULT true,
  PRIMARY KEY (user_id, grp)
);

-- ------------------------------------------------------------------------------------------------ categorias iniciais (estrutura; o conteúdo é cadastrado/aprovado pela equipe)
INSERT INTO kb_categories(slug, name, description, sort) VALUES
 ('primeiros-passos', 'Primeiros passos', 'Conta, organização e perfil', 10),
 ('projetos', 'Projetos', 'Cadastro, diagnóstico, metas e indicadores', 20),
 ('orcamento', 'Orçamento e cotações', 'Itens, cotações e justificativas', 30),
 ('documentos', 'Documentos e compliance', 'Documentos, validações e pendências', 40),
 ('match-financiamento', 'Match e financiamento', 'Compatibilidade, conexões e aportes', 50),
 ('execucao-prestacao', 'Execução e prestação de contas', 'Evidências, relatórios e encerramento', 60),
 ('impacto-esg', 'Impacto, ODS e ESG', 'Indicadores, evidências e relatórios', 70),
 ('assinatura-trial', 'Planos, teste e cobrança', 'Plano, período de teste, vouchers e convênios', 80),
 ('privacidade-seguranca', 'Privacidade e segurança', 'LGPD, dados pessoais e segurança da conta', 90);

-- ------------------------------------------------------------------------------------------------ RLS
ALTER TABLE staff_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE content_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_article_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_faqs ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_checklist_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_modules ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_lessons ENABLE ROW LEVEL SECURITY;
ALTER TABLE lesson_quiz_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE lesson_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE course_certificates ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_paths ENABLE ROW LEVEL SECURITY;
ALTER TABLE hub_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE hub_event_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE hub_event_registrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_sla ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE support_attachments ENABLE ROW LEVEL SECURITY;
ALTER TABLE partnership_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE partnership_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE partnerships ENABLE ROW LEVEL SECURITY;
ALTER TABLE demo_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE trial_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE newsletter_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_prefs ENABLE ROW LEVEL SECURITY;

CREATE POLICY staff_roles_priv ON staff_roles FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY staff_roles_self ON staff_roles FOR SELECT USING (user_id = app_uid());
CREATE POLICY content_history_priv ON content_history FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY kb_categories_read ON kb_categories FOR SELECT USING (true);
CREATE POLICY kb_categories_write ON kb_categories FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY kb_articles_read ON kb_articles FOR SELECT USING (app_priv() OR (live_version_id IS NOT NULL AND kb_visible(visibility, audience)));
CREATE POLICY kb_articles_write ON kb_articles FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY kb_versions_read ON kb_article_versions FOR SELECT USING (app_priv() OR (status = 'published' AND EXISTS (SELECT 1 FROM kb_articles a WHERE a.id = article_id AND kb_visible(a.visibility, a.audience))));
CREATE POLICY kb_versions_write ON kb_article_versions FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY kb_resources_read ON kb_resources FOR SELECT USING (app_priv() OR (status IN ('published','superseded') AND kb_visible(visibility, audience)));   -- versões anteriores ficam consultáveis
CREATE POLICY kb_resources_write ON kb_resources FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY kb_faqs_read ON kb_faqs FOR SELECT USING (app_priv() OR (status = 'published' AND kb_visible(visibility, audience)));
CREATE POLICY kb_faqs_write ON kb_faqs FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY kb_feedback_own ON kb_feedback FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY kb_checklist_own ON kb_checklist_progress FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY kb_events_priv ON kb_events FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY courses_read ON courses FOR SELECT USING (app_priv() OR (status = 'published' AND kb_visible(visibility, audience)));
CREATE POLICY courses_write ON courses FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY course_modules_read ON course_modules FOR SELECT USING (app_priv() OR EXISTS (SELECT 1 FROM courses c WHERE c.id = course_id AND c.status = 'published' AND kb_visible(c.visibility, c.audience)));
CREATE POLICY course_modules_write ON course_modules FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY course_lessons_read ON course_lessons FOR SELECT USING (app_priv() OR EXISTS (SELECT 1 FROM courses c WHERE c.id = course_id AND c.status = 'published' AND kb_visible(c.visibility, c.audience)));
CREATE POLICY course_lessons_write ON course_lessons FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY lesson_quiz_keys_priv ON lesson_quiz_keys FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY course_enroll_own ON course_enrollments FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY lesson_progress_own ON lesson_progress FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY certificates_own ON course_certificates FOR SELECT USING (user_id = app_uid() OR app_priv());
CREATE POLICY certificates_write ON course_certificates FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY paths_read ON learning_paths FOR SELECT USING (app_priv() OR (status = 'published' AND kb_visible(visibility, audience)));
CREATE POLICY paths_write ON learning_paths FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY hub_events_read ON hub_events FOR SELECT USING (app_priv() OR (status IN ('published','completed','cancelled') AND kb_visible(visibility, audience)));
CREATE POLICY hub_events_write ON hub_events FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY hub_event_links_read ON hub_event_links FOR SELECT USING (app_priv() OR EXISTS (SELECT 1 FROM hub_event_registrations r WHERE r.event_id = hub_event_links.event_id AND r.user_id = app_uid() AND r.status = 'registered'));
CREATE POLICY hub_event_links_write ON hub_event_links FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY hub_event_reg_own ON hub_event_registrations FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY support_sla_read ON support_sla FOR SELECT USING (true);
CREATE POLICY support_sla_write ON support_sla FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY tickets_read ON support_tickets FOR SELECT USING (user_id = app_uid() OR app_priv());
CREATE POLICY tickets_insert ON support_tickets FOR INSERT WITH CHECK ((user_id = app_uid() AND (org_id IS NULL OR org_id = app_org())) OR app_priv());
CREATE POLICY tickets_update ON support_tickets FOR UPDATE USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY support_msgs_read ON support_messages FOR SELECT USING (app_priv() OR (NOT internal AND EXISTS (SELECT 1 FROM support_tickets t WHERE t.id = ticket_id AND t.user_id = app_uid())));
CREATE POLICY support_msgs_insert ON support_messages FOR INSERT WITH CHECK (app_priv() OR EXISTS (SELECT 1 FROM support_tickets t WHERE t.id = ticket_id AND t.user_id = app_uid() AND t.status <> 'closed'));
CREATE POLICY support_att_read ON support_attachments FOR SELECT USING (app_priv() OR EXISTS (SELECT 1 FROM support_tickets t WHERE t.id = ticket_id AND t.user_id = app_uid()));
CREATE POLICY support_att_insert ON support_attachments FOR INSERT WITH CHECK (app_priv() OR EXISTS (SELECT 1 FROM support_tickets t WHERE t.id = ticket_id AND t.user_id = app_uid() AND t.status <> 'closed'));
-- pedidos de parceria/demonstração: o próprio autor lê; envio pode ser anônimo (user_id nulo) ou da própria sessão; nunca em nome de outra pessoa
CREATE POLICY partnership_read ON partnership_requests FOR SELECT USING ((user_id IS NOT NULL AND user_id = app_uid()) OR app_priv());
CREATE POLICY partnership_insert ON partnership_requests FOR INSERT WITH CHECK (user_id IS NULL OR user_id = app_uid() OR app_priv());
CREATE POLICY partnership_update ON partnership_requests FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY partnership_act_read ON partnership_activities FOR SELECT USING (app_priv() OR (kind IN ('status','proposal') AND EXISTS (SELECT 1 FROM partnership_requests r WHERE r.id = request_id AND r.user_id = app_uid())));
CREATE POLICY partnership_act_write ON partnership_activities FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY partnerships_priv ON partnerships FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY demo_read ON demo_requests FOR SELECT USING ((user_id IS NOT NULL AND user_id = app_uid()) OR app_priv());
CREATE POLICY demo_insert ON demo_requests FOR INSERT WITH CHECK (user_id IS NULL OR user_id = app_uid() OR app_priv());
CREATE POLICY demo_update ON demo_requests FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY trial_requests_read ON trial_requests FOR SELECT USING (user_id = app_uid() OR org_id = app_org() OR app_priv());
CREATE POLICY trial_requests_insert ON trial_requests FOR INSERT WITH CHECK ((user_id = app_uid() AND org_id = app_org()) OR app_priv());
CREATE POLICY trial_requests_update ON trial_requests FOR UPDATE USING (app_priv() OR (user_id = app_uid() AND status = 'requested')) WITH CHECK (app_priv() OR (user_id = app_uid() AND status IN ('requested','cancelled')));
CREATE POLICY newsletter_own ON newsletter_subscriptions FOR SELECT USING ((user_id IS NOT NULL AND user_id = app_uid()) OR app_priv());
CREATE POLICY newsletter_insert ON newsletter_subscriptions FOR INSERT WITH CHECK (user_id IS NULL OR user_id = app_uid() OR app_priv());
CREATE POLICY newsletter_update ON newsletter_subscriptions FOR UPDATE USING ((user_id IS NOT NULL AND user_id = app_uid()) OR app_priv()) WITH CHECK ((user_id IS NOT NULL AND user_id = app_uid()) OR app_priv());
CREATE POLICY notification_prefs_own ON notification_prefs FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());

-- ------------------------------------------------------------------------------------------------ privilégios
GRANT SELECT, INSERT, UPDATE, DELETE ON staff_roles, content_history, kb_categories, kb_articles, kb_article_versions, kb_resources, kb_faqs, kb_feedback,
  kb_checklist_progress, kb_events, courses, course_modules, course_lessons, lesson_quiz_keys, course_enrollments, lesson_progress, course_certificates,
  learning_paths, hub_events, hub_event_links, hub_event_registrations, support_sla, support_tickets, support_messages, support_attachments,
  partnership_requests, partnership_activities, partnerships, demo_requests, trial_requests, newsletter_subscriptions, notification_prefs TO impacto_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO impacto_app;
DO $$ DECLARE f regprocedure; BEGIN
  FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND pg_get_userbyid(p.proowner) = current_user LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO impacto_app', f);
  END LOOP;
END $$;
