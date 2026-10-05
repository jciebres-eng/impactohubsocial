-- 0012 — v0.14.0: TRUST, IDENTITY & DIGITAL SIGNATURE + taxonomia ODS/ESG, idioma, cotas, honorários, georreferência e diagnóstico guiado.
-- REUTILIZA (não duplica): documents.sha256 e versionamento · cofre de documentos (magic bytes, conteúdo ativo, antivírus) · signatures
-- (append-only, HMAC do servidor) · professional_credentials · professional_reviews · auth_tokens · consents · FieldCipher · chain_heads +
-- ts_canonical + forbid_mutation + guard_columns · audit_events/ledger_entries (já encadeados por hash) · users.locale (existia, nunca usada)
-- · organizations.ods/esg_focus e projects.ods (arrays já existentes) · Integration Hub (provedores de identidade e assinatura qualificada).
-- PRINCÍPIOS: verificação pública NUNCA lê tabela privada (lê um registro público curado); assinatura é append-only e revogação é um fato novo,
-- nunca um UPDATE; nenhum dado biométrico é armazenado; nenhum preço é inventado (tabela de honorários exige fonte e data).

-- ================================================================================================ 1. IDENTIDADE DA PESSOA
-- Níveis de identidade. 'biometric' depende de provedor externo contratado: a plataforma NÃO faz biometria própria e NÃO armazena face.
CREATE TABLE identity_verifications (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  level           text NOT NULL CHECK (level IN ('email','phone','document','professional','biometric')),
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','under_review','verified','rejected','expired','revoked')),
  method          text NOT NULL CHECK (method IN ('platform_token','human_review','council_document','external_provider')),
  provider_key    text REFERENCES integration_providers(key),   -- preenchido só quando method = 'external_provider'
  -- evidência MINIMIZADA: nunca número de documento, nunca imagem, nunca vetor biométrico. Apenas o que sustenta a decisão.
  evidence        jsonb NOT NULL DEFAULT '{}'::jsonb,
  decided_by      uuid REFERENCES users(id),
  decided_at      timestamptz,
  decision_note   text CHECK (length(decision_note) <= 2000),
  expires_at      timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, level)
);
CREATE INDEX ix_idv_user ON identity_verifications(user_id, status);
CREATE INDEX ix_idv_queue ON identity_verifications(status, created_at) WHERE status IN ('pending','under_review');

-- Documentos enviados para identificação. Guardamos a REFERÊNCIA ao documento no cofre e o resultado da conferência — não o número.
CREATE TABLE identity_documents (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  verification_id uuid NOT NULL REFERENCES identity_verifications(id) ON DELETE CASCADE,
  user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  document_id     uuid NOT NULL REFERENCES documents(id) ON DELETE RESTRICT,
  kind            text NOT NULL CHECK (kind IN ('official_id','drivers_license','passport','proof_of_address','council_card','other')),
  status          text NOT NULL DEFAULT 'submitted' CHECK (status IN ('submitted','accepted','rejected')),
  reject_reason   text CHECK (length(reject_reason) <= 500),
  reviewed_by     uuid REFERENCES users(id),
  reviewed_at     timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (verification_id, document_id)
);

-- Nível corrente de identidade (maior nível verificado e não expirado). SECURITY DEFINER: usada por políticas e pelo núcleo.
CREATE FUNCTION identity_level(p_user uuid) RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT coalesce((SELECT level FROM identity_verifications
                   WHERE user_id = p_user AND status = 'verified' AND (expires_at IS NULL OR expires_at > now())
                   ORDER BY CASE level WHEN 'biometric' THEN 5 WHEN 'professional' THEN 4 WHEN 'document' THEN 3
                                       WHEN 'phone' THEN 2 ELSE 1 END DESC LIMIT 1), 'none')
$$;

-- ================================================================================================ 2. CONSELHOS E CREDENCIAIS PROFISSIONAIS
-- Catálogo de conselhos. number_pattern e official_site ficam NULOS de propósito: o formato de registro varia por conselho/UF/época e a
-- plataforma NÃO inventa regra nem URL. A administração preenche com fonte. Sem padrão, vale só a sanidade genérica do CHECK de number.
CREATE TABLE professional_councils (
  code            text PRIMARY KEY CHECK (code ~ '^[A-Z]{2,10}$'),
  name            text NOT NULL CHECK (length(name) BETWEEN 3 AND 160),
  profession      text NOT NULL CHECK (length(profession) BETWEEN 3 AND 120),
  number_pattern  text CHECK (number_pattern IS NULL OR length(number_pattern) <= 200),
  uf_required     boolean NOT NULL DEFAULT true,
  official_site   text CHECK (official_site IS NULL OR official_site ~ '^https://'),
  lookup_note     text CHECK (length(lookup_note) <= 500),
  source_name     text CHECK (length(source_name) <= 200),
  source_date     date,
  active          boolean NOT NULL DEFAULT true,
  updated_at      timestamptz NOT NULL DEFAULT now()
);

-- Histórico append-only da verificação de credencial (quem conferiu o quê, com qual evidência).
CREATE TABLE credential_verifications (
  id              bigserial PRIMARY KEY,
  credential_id   uuid NOT NULL REFERENCES professional_credentials(id) ON DELETE CASCADE,
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  action          text NOT NULL CHECK (action IN ('submitted','document_attached','verified','rejected','expired','revoked','reopened')),
  actor_user_id   uuid REFERENCES users(id),
  method          text NOT NULL DEFAULT 'human_review' CHECK (method IN ('human_review','council_document','external_provider','system')),
  document_id     uuid REFERENCES documents(id),
  note            text CHECK (length(note) <= 2000),
  at              timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_credver_cred ON credential_verifications(credential_id, at DESC);

ALTER TABLE professional_credentials ADD COLUMN council_code text REFERENCES professional_councils(code);
ALTER TABLE professional_credentials ADD COLUMN revoked_at timestamptz;
ALTER TABLE professional_credentials ADD COLUMN revocation_reason text CHECK (length(revocation_reason) <= 500);
UPDATE professional_credentials SET council_code = council WHERE council IN (SELECT code FROM professional_councils);

-- ================================================================================================ 3. CADEIA DE CUSTÓDIA (por objeto)
-- Encadeamento por hash, igual ao de auditoria/ledger, mas por OBJETO (documento, rascunho, acordo). Append-only por gatilho.
CREATE TABLE trust_events (
  id            bigserial PRIMARY KEY,
  subject_type  text NOT NULL CHECK (subject_type IN ('document','draft','agreement','credential','identity')),
  subject_id    uuid NOT NULL,
  org_id        uuid REFERENCES organizations(id) ON DELETE CASCADE,
  event_type    text NOT NULL CHECK (event_type IN ('created','version_created','hashed','signed','signature_revoked','timestamped',
                   'verified_public','integrity_ok','integrity_failed','revoked','superseded','shared','identity_decided','credential_decided')),
  actor_user_id uuid REFERENCES users(id),
  content_sha256 char(64) CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
  payload       jsonb NOT NULL DEFAULT '{}'::jsonb,       -- sem dado pessoal sensível, sem segredo
  seq           bigint,
  prev_hash     char(64),
  event_hash    char(64),
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_trust_subject ON trust_events(subject_type, subject_id, seq);

CREATE FUNCTION trust_material(e trust_events) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT concat_ws('|', e.prev_hash, e.seq::text, e.subject_type, e.subject_id::text, coalesce(e.org_id::text,''),
                   coalesce(e.actor_user_id::text,''), e.event_type, coalesce(e.content_sha256,''), e.payload::text, ts_canonical(e.at))
$$;
CREATE FUNCTION chain_trust() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE k text; s bigint; prev char(64);
BEGIN
  k := 'trust:' || NEW.subject_type || ':' || NEW.subject_id::text;
  INSERT INTO chain_heads(chain_key, last_seq, last_hash) VALUES (k, 0, repeat('0', 64)) ON CONFLICT DO NOTHING;
  SELECT last_seq, last_hash INTO s, prev FROM chain_heads WHERE chain_key = k FOR UPDATE;
  NEW.at := date_trunc('microseconds', now());
  NEW.seq := s + 1; NEW.prev_hash := prev;
  NEW.event_hash := encode(digest(trust_material(NEW), 'sha256'), 'hex');
  UPDATE chain_heads SET last_seq = NEW.seq, last_hash = NEW.event_hash WHERE chain_key = k;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_chain BEFORE INSERT ON trust_events FOR EACH ROW EXECUTE FUNCTION chain_trust();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON trust_events FOR EACH ROW WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

CREATE FUNCTION trust_verify(p_type text, p_subject uuid) RETURNS TABLE(entries bigint, valid boolean, first_broken_seq bigint)
LANGUAGE plpgsql STABLE AS $$
DECLARE r trust_events; expected_prev char(64) := repeat('0', 64); n bigint := 0; broken bigint := NULL;
BEGIN
  FOR r IN SELECT * FROM trust_events WHERE subject_type = p_type AND subject_id = p_subject ORDER BY seq LOOP
    n := n + 1;
    IF broken IS NULL AND (r.prev_hash <> expected_prev OR r.event_hash <> encode(digest(trust_material(r), 'sha256'), 'hex')) THEN
      broken := r.seq;
    END IF;
    expected_prev := r.event_hash;
  END LOOP;
  RETURN QUERY SELECT n, broken IS NULL, broken;
END $$;

-- ================================================================================================ 4. VERIFICAÇÃO PÚBLICA
-- A página pública lê SOMENTE esta tabela. O conteúdo público é CURADO na criação (public_fields), então nenhum dado pessoal vaza por
-- engano quando a tabela de origem muda. O código é legível, sem caracteres ambíguos, e não é sequencial (não dá para varrer).
CREATE TABLE verifiable_records (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code            text NOT NULL UNIQUE CHECK (code ~ '^IMP-[0-9A-HJ-NP-TV-Z]{4}-[0-9A-HJ-NP-TV-Z]{4}-[0-9A-HJ-NP-TV-Z]{4}$'),
  subject_type    text NOT NULL CHECK (subject_type IN ('document','draft','signature','agreement','credential')),
  subject_id      uuid NOT NULL,
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  title           text NOT NULL CHECK (length(title) BETWEEN 2 AND 200),
  content_sha256  char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  subject_version integer NOT NULL DEFAULT 1 CHECK (subject_version >= 1),
  status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','revoked','expired')),
  -- campos exibidos publicamente, montados pelo servidor (nomes de signatários só com consentimento explícito do papel público)
  public_fields   jsonb NOT NULL DEFAULT '{}'::jsonb,
  issued_at       timestamptz NOT NULL DEFAULT now(),
  expires_at      timestamptz,
  revoked_at      timestamptz,
  revocation_reason text CHECK (length(revocation_reason) <= 500),
  revoked_by      uuid REFERENCES users(id),
  superseded_by   uuid REFERENCES verifiable_records(id),
  access_count    bigint NOT NULL DEFAULT 0 CHECK (access_count >= 0),
  last_accessed_at timestamptz,
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (status <> 'revoked' OR (revoked_at IS NOT NULL AND revocation_reason IS NOT NULL))
);
CREATE INDEX ix_vrec_subject ON verifiable_records(subject_type, subject_id);
CREATE INDEX ix_vrec_org ON verifiable_records(org_id, created_at DESC);

-- Carimbo de tempo. 'internal' = selo HMAC do servidor sobre (hash, instante) — prova interna, não é carimbo de ACT.
-- 'rfc3161' exige Autoridade de Carimbo de Tempo contratada: a coluna do token existe, a emissão NÃO está implementada.
CREATE TABLE trust_timestamps (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id     uuid NOT NULL REFERENCES verifiable_records(id) ON DELETE CASCADE,
  kind          text NOT NULL CHECK (kind IN ('internal','rfc3161')),
  hashed_value  char(64) NOT NULL CHECK (hashed_value ~ '^[0-9a-f]{64}$'),
  seal          char(64) CHECK (seal IS NULL OR seal ~ '^[0-9a-f]{64}$'),   -- HMAC do servidor (kind = 'internal')
  token         bytea,                                                      -- token DER da ACT (kind = 'rfc3161')
  authority     text CHECK (length(authority) <= 160),
  stamped_at    timestamptz NOT NULL DEFAULT now(),
  CHECK ((kind = 'internal' AND seal IS NOT NULL AND token IS NULL) OR (kind = 'rfc3161' AND token IS NOT NULL))
);
CREATE INDEX ix_tstamp_record ON trust_timestamps(record_id, stamped_at);

-- ================================================================================================ 5. ASSINATURA EM DUAS CAMADAS
-- Camada 1: reautenticação por senha (já existia). Camada 2: código de uso único entregue por canal fora do formulário.
-- 'sms' consta no domínio porque o canal é previsto, mas NÃO há provedor de SMS: a API recusa com mensagem explícita.
CREATE TABLE signature_challenges (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  subject_type  text NOT NULL CHECK (subject_type IN ('document','draft','agreement')),
  subject_id    uuid NOT NULL,
  subject_sha256 char(64) NOT NULL CHECK (subject_sha256 ~ '^[0-9a-f]{64}$'),
  channel       text NOT NULL CHECK (channel IN ('email','sms')),
  destination_hint text CHECK (length(destination_hint) <= 120),
  code_hash     char(64) NOT NULL,
  expires_at    timestamptz NOT NULL,
  used_at       timestamptz,
  attempts      integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_sigchal_user ON signature_challenges(user_id, subject_type, subject_id, created_at DESC);

ALTER TABLE signatures ADD COLUMN challenge_id uuid REFERENCES signature_challenges(id);
ALTER TABLE signatures ADD COLUMN identity_level text;
ALTER TABLE signatures ADD COLUMN agreement_party_id uuid;
-- Revogação de assinatura é FATO NOVO: signatures é append-only (gatilho trg_append_only de 0002) e continua sendo.
CREATE TABLE signature_revocations (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  signature_id  uuid NOT NULL UNIQUE REFERENCES signatures(id) ON DELETE RESTRICT,
  org_id        uuid NOT NULL REFERENCES organizations(id),
  reason        text NOT NULL CHECK (length(reason) BETWEEN 10 AND 500),
  revoked_by    uuid NOT NULL REFERENCES users(id),
  revoked_at    timestamptz NOT NULL DEFAULT now()
);

-- ================================================================================================ 6. ACORDOS MULTIASSINATURA
CREATE TABLE signed_agreements (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
  kind            text NOT NULL CHECK (kind IN ('service','partnership','funding','volunteer','data_sharing','other')),
  title           text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  summary         text CHECK (length(summary) <= 4000),
  document_id     uuid REFERENCES documents(id) ON DELETE RESTRICT,
  content_sha256  char(64) NOT NULL CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
  status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','awaiting_signatures','active','completed','canceled','expired')),
  effective_from  date,
  effective_to    date,
  value_cents     bigint CHECK (value_cents IS NULL OR value_cents >= 0),
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (effective_to IS NULL OR effective_from IS NULL OR effective_to >= effective_from)
);
CREATE INDEX ix_agr_org ON signed_agreements(org_id, status);

CREATE TABLE signed_agreement_parties (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id  uuid NOT NULL REFERENCES signed_agreements(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id       uuid REFERENCES users(id) ON DELETE SET NULL,
  role          text NOT NULL CHECK (role IN ('contractor','provider','funder','professional','witness','beneficiary_rep')),
  required      boolean NOT NULL DEFAULT true,
  signature_id  uuid REFERENCES signatures(id),
  signed_at     timestamptz,
  declined_at   timestamptz,
  decline_reason text CHECK (length(decline_reason) <= 500),
  invited_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (agreement_id, org_id, role),
  CHECK (signed_at IS NULL OR declined_at IS NULL)
);
CREATE INDEX ix_agrparty_org ON signed_agreement_parties(org_id, signed_at);

-- Acompanhamento longitudinal do acordo (entregas, relatórios, documentos ao longo do tempo).
CREATE TABLE signed_agreement_milestones (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  agreement_id  uuid NOT NULL REFERENCES signed_agreements(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  title         text NOT NULL CHECK (length(title) BETWEEN 2 AND 200),
  due_on        date,
  status        text NOT NULL DEFAULT 'planned' CHECK (status IN ('planned','in_progress','delivered','accepted','rejected','canceled')),
  document_id   uuid REFERENCES documents(id) ON DELETE SET NULL,
  note          text CHECK (length(note) <= 2000),
  reported_by   uuid REFERENCES users(id),
  reported_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_agrms_agreement ON signed_agreement_milestones(agreement_id, due_on);

-- ================================================================================================ 7. TAXONOMIA ODS / ESG / DETERMINANTES
-- Catálogo oficial dos 17 Objetivos de Desenvolvimento Sustentável (Agenda 2030 da ONU). A paleta é a da identidade visual oficial.
-- ATENÇÃO: os EMBLEMAS/LOGOS da ONU e o selo dos ODS são marcas protegidas e NÃO são distribuídos com a plataforma — ver SDG_ESG_TAXONOMY.md.
-- As colunas de arrays que já existiam (organizations.ods, projects.ods, solutions.ods, calls.ods) passam a ter catálogo de referência.
CREATE TABLE sdg_goals (
  number     smallint PRIMARY KEY CHECK (number BETWEEN 1 AND 17),
  code       text NOT NULL UNIQUE CHECK (code ~ '^ODS[0-9]{1,2}$'),
  name_pt    text NOT NULL,
  name_en    text NOT NULL,
  color_hex  char(7) NOT NULL CHECK (color_hex ~ '^#[0-9A-F]{6}$'),
  active     boolean NOT NULL DEFAULT true
);
INSERT INTO sdg_goals(number, code, name_pt, name_en, color_hex) VALUES
 (1,'ODS1','Erradicação da pobreza','No Poverty','#E5243B'),
 (2,'ODS2','Fome zero e agricultura sustentável','Zero Hunger','#DDA63A'),
 (3,'ODS3','Saúde e bem-estar','Good Health and Well-being','#4C9F38'),
 (4,'ODS4','Educação de qualidade','Quality Education','#C5192D'),
 (5,'ODS5','Igualdade de gênero','Gender Equality','#FF3A21'),
 (6,'ODS6','Água potável e saneamento','Clean Water and Sanitation','#26BDE2'),
 (7,'ODS7','Energia limpa e acessível','Affordable and Clean Energy','#FCC30B'),
 (8,'ODS8','Trabalho decente e crescimento econômico','Decent Work and Economic Growth','#A21942'),
 (9,'ODS9','Indústria, inovação e infraestrutura','Industry, Innovation and Infrastructure','#FD6925'),
 (10,'ODS10','Redução das desigualdades','Reduced Inequalities','#DD1367'),
 (11,'ODS11','Cidades e comunidades sustentáveis','Sustainable Cities and Communities','#FD9D24'),
 (12,'ODS12','Consumo e produção responsáveis','Responsible Consumption and Production','#BF8B2E'),
 (13,'ODS13','Ação contra a mudança global do clima','Climate Action','#3F7E44'),
 (14,'ODS14','Vida na água','Life Below Water','#0A97D9'),
 (15,'ODS15','Vida terrestre','Life on Land','#56C02B'),
 (16,'ODS16','Paz, justiça e instituições eficazes','Peace, Justice and Strong Institutions','#00689D'),
 (17,'ODS17','Parcerias e meios de implementação','Partnerships for the Goals','#19486A');

CREATE TABLE esg_pillars (
  code       text PRIMARY KEY CHECK (code IN ('E','S','G')),
  name_pt    text NOT NULL,
  name_en    text NOT NULL,
  description text NOT NULL
);
INSERT INTO esg_pillars(code, name_pt, name_en, description) VALUES
 ('E','Ambiental','Environmental','Efeitos da organização sobre o meio ambiente: clima, resíduos, água, energia, biodiversidade.'),
 ('S','Social','Social','Relação com pessoas: trabalho, direitos humanos, comunidade, diversidade, saúde e segurança.'),
 ('G','Governança','Governance','Como a organização é dirigida e controlada: transparência, conformidade, conflito de interesse, prestação de contas.');

-- Determinantes sociais da saúde. Lista EDITORIAL baseada no modelo de Dahlgren e Whitehead adotado pela CNDSS; a redação é nossa e
-- precisa de revisão técnica. Não é classificação oficial de nenhum órgão.
CREATE TABLE social_determinants (
  code        text PRIMARY KEY CHECK (code ~ '^[a-z_]{3,40}$'),
  name_pt     text NOT NULL,
  layer       text NOT NULL CHECK (layer IN ('individual','social_community','living_working','socioeconomic')),
  description text NOT NULL,
  source_note text NOT NULL,
  active      boolean NOT NULL DEFAULT true
);
INSERT INTO social_determinants(code, name_pt, layer, description, source_note) VALUES
 ('income','Renda e situação econômica','socioeconomic','Capacidade de sustento, pobreza, desigualdade de renda.','Modelo de Dahlgren e Whitehead (CNDSS) — redação da plataforma, revisão técnica pendente'),
 ('education','Educação','socioeconomic','Escolaridade, alfabetização, acesso e permanência na escola.','idem'),
 ('work','Trabalho e emprego','living_working','Vínculo, informalidade, condições e segurança no trabalho.','idem'),
 ('housing','Moradia e saneamento','living_working','Habitação adequada, água, esgoto, resíduos, energia.','idem'),
 ('food','Segurança alimentar e nutricional','living_working','Acesso regular a alimento adequado em quantidade e qualidade.','idem'),
 ('environment','Ambiente e território','living_working','Poluição, exposição a risco ambiental, mobilidade, área de vulnerabilidade.','idem'),
 ('health_services','Acesso a serviços de saúde','living_working','Disponibilidade, acesso e continuidade do cuidado.','idem'),
 ('social_support','Rede e apoio social','social_community','Vínculos familiares e comunitários, isolamento, participação.','idem'),
 ('violence','Violência e segurança','social_community','Exposição a violência comunitária, doméstica ou institucional.','idem'),
 ('discrimination','Discriminação e desigualdade','socioeconomic','Barreiras por raça, etnia, gênero, deficiência, idade ou origem.','idem'),
 ('life_course','Curso de vida e comportamento','individual','Fatores individuais ao longo da vida, incluindo hábitos e idade.','idem');

-- Marcadores: liga qualquer objeto do domínio a um item de taxonomia. Convive com os arrays existentes (não os substitui).
CREATE TABLE impact_tags (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  subject_type  text NOT NULL CHECK (subject_type IN ('project','solution','diagnosis','need','call','organization','agreement')),
  subject_id    uuid NOT NULL,
  taxonomy      text NOT NULL CHECK (taxonomy IN ('sdg','esg','determinant')),
  code          text NOT NULL CHECK (length(code) BETWEEN 1 AND 40),
  is_primary    boolean NOT NULL DEFAULT false,
  note          text CHECK (length(note) <= 500),
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (subject_type, subject_id, taxonomy, code)
);
CREATE INDEX ix_itags_subject ON impact_tags(subject_type, subject_id);
CREATE INDEX ix_itags_code ON impact_tags(taxonomy, code);

-- O código precisa existir na taxonomia correspondente (integridade sem três colunas de FK).
CREATE FUNCTION impact_tag_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.taxonomy = 'sdg' AND NOT EXISTS (SELECT 1 FROM sdg_goals WHERE code = NEW.code) THEN
    RAISE EXCEPTION 'ODS desconhecido: %', NEW.code USING ERRCODE = '23514';
  ELSIF NEW.taxonomy = 'esg' AND NOT EXISTS (SELECT 1 FROM esg_pillars WHERE code = NEW.code) THEN
    RAISE EXCEPTION 'Pilar ESG desconhecido: %', NEW.code USING ERRCODE = '23514';
  ELSIF NEW.taxonomy = 'determinant' AND NOT EXISTS (SELECT 1 FROM social_determinants WHERE code = NEW.code) THEN
    RAISE EXCEPTION 'Determinante social desconhecido: %', NEW.code USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_itag_guard BEFORE INSERT OR UPDATE ON impact_tags FOR EACH ROW EXECUTE FUNCTION impact_tag_guard();

-- ================================================================================================ 8. IDIOMA E TEMA
CREATE TABLE locales (
  code         text PRIMARY KEY CHECK (code ~ '^[a-z]{2}(-[A-Z]{2})?$'),
  name_pt      text NOT NULL,
  native_name  text NOT NULL,
  is_default   boolean NOT NULL DEFAULT false,
  active       boolean NOT NULL DEFAULT true,
  coverage_note text CHECK (length(coverage_note) <= 300)
);
INSERT INTO locales(code, name_pt, native_name, is_default, coverage_note) VALUES
 ('pt-BR','Português (Brasil)','Português (Brasil)', true, 'Idioma de origem: 100% da interface.'),
 ('en','Inglês','English', false, 'Núcleo traduzido (navegação, ações comuns, verificação pública). Telas internas permanecem em português.'),
 ('es','Espanhol','Español', false, 'Núcleo traduzido (navegação, ações comuns, verificação pública). Telas internas permanecem em português.');
CREATE UNIQUE INDEX ux_locale_default ON locales(is_default) WHERE is_default;

CREATE TABLE translations (
  locale     text NOT NULL REFERENCES locales(code) ON DELETE CASCADE,
  namespace  text NOT NULL CHECK (namespace ~ '^[a-z0-9_]{2,40}$'),
  key        text NOT NULL CHECK (key ~ '^[a-z0-9_.]{2,80}$'),
  value      text NOT NULL CHECK (length(value) BETWEEN 1 AND 2000),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (locale, namespace, key)
);

ALTER TABLE users ADD COLUMN theme text NOT NULL DEFAULT 'system' CHECK (theme IN ('system','light','dark'));
ALTER TABLE users ADD COLUMN prefs_set_at timestamptz;   -- preenchido quando a pessoa escolhe idioma/tema (para perguntar só uma vez)
ALTER TABLE users ADD CONSTRAINT users_locale_fk FOREIGN KEY (locale) REFERENCES locales(code);

-- ================================================================================================ 9. FINANCIAMENTO EM COTAS + CAMPANHA
CREATE TABLE funding_quotas (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  label           text NOT NULL CHECK (length(label) BETWEEN 2 AND 120),
  description     text CHECK (length(description) <= 2000),
  -- valor definido pela organização proponente; a plataforma NÃO sugere nem calcula preço
  quota_cents     bigint NOT NULL CHECK (quota_cents > 0),
  total_quotas    integer NOT NULL CHECK (total_quotas > 0 AND total_quotas <= 100000),
  min_per_backer  integer NOT NULL DEFAULT 1 CHECK (min_per_backer >= 1),
  max_per_backer  integer CHECK (max_per_backer IS NULL OR max_per_backer >= min_per_backer),
  status          text NOT NULL DEFAULT 'open' CHECK (status IN ('draft','open','paused','closed')),
  deadline        date,
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_fquota_project ON funding_quotas(project_id, status);

CREATE TABLE quota_pledges (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  quota_id        uuid NOT NULL REFERENCES funding_quotas(id) ON DELETE CASCADE,
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  backer_org_id   uuid REFERENCES organizations(id) ON DELETE SET NULL,
  backer_user_id  uuid REFERENCES users(id) ON DELETE SET NULL,
  quantity        integer NOT NULL CHECK (quantity >= 1),
  amount_cents    bigint NOT NULL CHECK (amount_cents > 0),
  status          text NOT NULL DEFAULT 'pledged' CHECK (status IN ('pledged','confirmed','canceled','refunded')),
  display_name    text CHECK (length(display_name) <= 120),   -- nome público escolhido pelo apoiador (pode ser anônimo)
  is_anonymous    boolean NOT NULL DEFAULT false,
  payment_ref     text CHECK (length(payment_ref) <= 200),
  note            text CHECK (length(note) <= 1000),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_qpledge_quota ON quota_pledges(quota_id, status);

-- Nunca vender mais cotas do que existem: a soma de reservadas + confirmadas é verificada no banco, sob trava da própria cota.
-- SECURITY DEFINER é ESSENCIAL aqui, por dois motivos descobertos em teste:
--   1. `SELECT ... FOR UPDATE` aplica também a política de UPDATE da tabela travada; quem apoia não é dona da cota,
--      então a linha sumia e as variáveis vinham NULL — e toda comparação com NULL é "não verdadeira", ou seja, a
--      guarda passava em silêncio e dava para vender cota negativa;
--   2. a soma das reservas precisa ver TODAS as reservas, não só as da organização que está apoiando.
-- Por isso também existe a checagem explícita de NULL: guarda de integridade não pode depender de visibilidade.
CREATE FUNCTION quota_capacity_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE total integer; taken integer; qmin integer; qmax integer; st text;
BEGIN
  IF NEW.status NOT IN ('pledged','confirmed') THEN RETURN NEW; END IF;
  SELECT total_quotas, min_per_backer, max_per_backer, status INTO total, qmin, qmax, st
    FROM funding_quotas WHERE id = NEW.quota_id FOR UPDATE;
  IF total IS NULL THEN RAISE EXCEPTION 'Cota de financiamento inexistente' USING ERRCODE = '23514'; END IF;
  IF st <> 'open' THEN RAISE EXCEPTION 'Cota não está aberta para apoio' USING ERRCODE = '23514'; END IF;
  IF NEW.quantity < qmin THEN RAISE EXCEPTION 'Mínimo de % cota(s) por apoiador', qmin USING ERRCODE = '23514'; END IF;
  IF qmax IS NOT NULL AND NEW.quantity > qmax THEN RAISE EXCEPTION 'Máximo de % cota(s) por apoiador', qmax USING ERRCODE = '23514'; END IF;
  SELECT coalesce(sum(quantity), 0) INTO taken FROM quota_pledges
    WHERE quota_id = NEW.quota_id AND status IN ('pledged','confirmed') AND id <> NEW.id;
  IF taken + NEW.quantity > total THEN
    RAISE EXCEPTION 'Restam % cota(s) disponível(is)', total - taken USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_quota_capacity BEFORE INSERT OR UPDATE ON quota_pledges FOR EACH ROW EXECUTE FUNCTION quota_capacity_guard();

CREATE TABLE campaigns (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id      uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  slug            text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9-]{4,80}$'),
  title           text NOT NULL CHECK (length(title) BETWEEN 4 AND 200),
  summary         text NOT NULL CHECK (length(summary) BETWEEN 20 AND 600),
  story           text CHECK (length(story) <= 20000),
  cover_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  status          text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','closed')),
  show_backers    boolean NOT NULL DEFAULT false,
  published_at    timestamptz,
  closed_at       timestamptz,
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id)
);

-- ================================================================================================ 10. HONORÁRIOS (SEM PREÇO INVENTADO)
-- A tabela nasce VAZIA. Publicar exige nome da fonte, URL e data de consulta — a plataforma não inventa valor de referência.
CREATE TABLE fee_tables (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  council_code  text NOT NULL REFERENCES professional_councils(code),
  title         text NOT NULL CHECK (length(title) BETWEEN 4 AND 200),
  version       text NOT NULL CHECK (length(version) BETWEEN 1 AND 40),
  reference_year smallint CHECK (reference_year BETWEEN 2000 AND 2100),
  source_name   text CHECK (length(source_name) <= 200),
  source_url    text CHECK (source_url IS NULL OR source_url ~ '^https://'),
  source_date   date,
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
  notes         text CHECK (length(notes) <= 2000),
  published_by  uuid REFERENCES users(id),
  published_at  timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (council_code, version),
  CHECK (status <> 'published' OR (source_name IS NOT NULL AND source_url IS NOT NULL AND source_date IS NOT NULL))
);

CREATE TABLE fee_items (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fee_table_id  uuid NOT NULL REFERENCES fee_tables(id) ON DELETE CASCADE,
  service_code  text NOT NULL CHECK (service_code ~ '^[a-z0-9_.-]{2,60}$'),
  description   text NOT NULL CHECK (length(description) BETWEEN 3 AND 300),
  unit          text NOT NULL CHECK (unit IN ('hour','session','document','report','visit','month','project','other')),
  reference_cents bigint CHECK (reference_cents IS NULL OR reference_cents >= 0),
  min_cents     bigint CHECK (min_cents IS NULL OR min_cents >= 0),
  max_cents     bigint CHECK (max_cents IS NULL OR max_cents >= 0),
  negotiable    boolean NOT NULL DEFAULT true,
  note          text CHECK (length(note) <= 500),
  UNIQUE (fee_table_id, service_code),
  CHECK (max_cents IS NULL OR min_cents IS NULL OR max_cents >= min_cents)
);

-- Catálogo de atividades que cada profissional oferece. O preço é da PROFISSIONAL, não da plataforma.
CREATE TABLE professional_services (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id       uuid REFERENCES users(id) ON DELETE SET NULL,
  credential_id uuid REFERENCES professional_credentials(id) ON DELETE SET NULL,
  fee_item_id   uuid REFERENCES fee_items(id) ON DELETE SET NULL,
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  description   text CHECK (length(description) <= 4000),
  modality      text NOT NULL DEFAULT 'hybrid' CHECK (modality IN ('online','in_person','hybrid')),
  unit          text NOT NULL DEFAULT 'session' CHECK (unit IN ('hour','session','document','report','visit','month','project','other')),
  price_cents   bigint CHECK (price_cents IS NULL OR price_cents >= 0),
  negotiable    boolean NOT NULL DEFAULT true,
  duration_min  integer CHECK (duration_min IS NULL OR duration_min BETWEEN 5 AND 1440),
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','paused')),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_psvc_org ON professional_services(org_id, status);

-- ================================================================================================ 11. GEORREFERÊNCIA
-- Localização de organização/profissional é dado pessoal quando identifica uma pessoa: exige consentimento e tem precisão declarada.
ALTER TABLE organizations ADD COLUMN lat numeric(8,5) CHECK (lat BETWEEN -90 AND 90);
ALTER TABLE organizations ADD COLUMN lng numeric(8,5) CHECK (lng BETWEEN -180 AND 180);
ALTER TABLE organizations ADD CONSTRAINT organizations_latlng_pair CHECK ((lat IS NULL) = (lng IS NULL));
ALTER TABLE organizations ADD COLUMN geo_precision text CHECK (geo_precision IN ('exact','approximate','city'));
ALTER TABLE organizations ADD COLUMN geo_public boolean NOT NULL DEFAULT false;
ALTER TABLE organizations ADD COLUMN geo_consent_at timestamptz;
ALTER TABLE organizations ADD CONSTRAINT organizations_geo_consent CHECK (NOT geo_public OR geo_consent_at IS NOT NULL);

-- ================================================================================================ 12. DIAGNÓSTICO GUIADO
-- Etapas de referência (hipótese editorial, versionada em config/diagnosis_stages.json e sincronizada pelo runner de migrations).
CREATE TABLE diagnosis_stages (
  code          text PRIMARY KEY CHECK (code ~ '^[a-z0-9_]{3,40}$'),
  position      smallint NOT NULL CHECK (position BETWEEN 1 AND 50),
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 160),
  purpose       text NOT NULL CHECK (length(purpose) <= 1000),
  questions     jsonb NOT NULL DEFAULT '[]'::jsonb,        -- [{key,label,type,required,help,options}]
  required_documents jsonb NOT NULL DEFAULT '[]'::jsonb,   -- [{doc_type,label,required}]
  help_key      text CHECK (length(help_key) <= 80),
  active        boolean NOT NULL DEFAULT true,
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (position)
);

CREATE TABLE diagnosis_progress (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  diagnosis_id  uuid NOT NULL REFERENCES diagnoses(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  stage_code    text NOT NULL REFERENCES diagnosis_stages(code),
  status        text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','in_progress','complete','skipped')),
  answers       jsonb NOT NULL DEFAULT '{}'::jsonb,
  document_ids  uuid[] NOT NULL DEFAULT '{}',
  skip_reason   text CHECK (length(skip_reason) <= 500),
  updated_by    uuid REFERENCES users(id),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  completed_at  timestamptz,
  UNIQUE (diagnosis_id, stage_code)
);
CREATE INDEX ix_dprog_diag ON diagnosis_progress(diagnosis_id, stage_code);

-- ================================================================================================ 13. INTEGRIDADE E GUARDAS
-- Só tabelas que TÊM updated_at entram aqui: touch_updated_at() falha em tempo de execução se a coluna não existir.
DO $$ DECLARE t text; BEGIN
  FOREACH t IN ARRAY ARRAY['identity_verifications','signed_agreements','funding_quotas','quota_pledges','campaigns',
                           'professional_services','diagnosis_progress'] LOOP
    EXECUTE format('CREATE TRIGGER trg_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION touch_updated_at()', t);
  END LOOP;
END $$;

-- Ninguém promove a própria identidade nem a própria credencial: decisão é da administração (ou de função privilegiada).
CREATE TRIGGER trg_guard BEFORE UPDATE ON identity_verifications FOR EACH ROW
  EXECUTE FUNCTION guard_columns('status','decided_by','decided_at','decision_note','level','method','provider_key');
CREATE TRIGGER trg_guard BEFORE UPDATE ON identity_documents FOR EACH ROW
  EXECUTE FUNCTION guard_columns('status','reviewed_by','reviewed_at','reject_reason');
-- Registro público: a organização cria e pode revogar o seu; nunca reescreve o hash, a versão ou o contador de acesso.
CREATE TRIGGER trg_guard BEFORE UPDATE ON verifiable_records FOR EACH ROW
  -- 'superseded_by' NÃO entra na guarda: quando a organização gera o registro da nova versão, ela precisa apontar o
  -- registro anterior para 'substituído' na mesma transação. Hash, versão, código e contador seguem imutáveis.
  EXECUTE FUNCTION guard_columns('code','subject_type','subject_id','content_sha256','subject_version','issued_at','access_count','last_accessed_at');
-- A parte de um acordo não marca a assinatura de outra parte, e nem reescreve o hash do acordo.
CREATE TRIGGER trg_guard BEFORE UPDATE ON signed_agreements FOR EACH ROW
  EXECUTE FUNCTION guard_columns('content_sha256','document_id','org_id');
CREATE TRIGGER trg_guard BEFORE UPDATE ON signed_agreement_parties FOR EACH ROW
  EXECUTE FUNCTION guard_columns('signature_id','signed_at','org_id','role');
-- Quem apoia não confirma o próprio pagamento, e a tabela de honorários não é "publicada" sem fonte (CHECK) nem por quem não é administração.
CREATE TRIGGER trg_guard BEFORE UPDATE ON quota_pledges FOR EACH ROW
  EXECUTE FUNCTION guard_columns('status','payment_ref','amount_cents','quantity','quota_id');
CREATE TRIGGER trg_guard BEFORE UPDATE ON fee_tables FOR EACH ROW
  EXECUTE FUNCTION guard_columns('status','published_by','published_at','council_code');
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON credential_verifications FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON signature_revocations FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON trust_timestamps FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

-- Verificações de identidade e documentos de identidade nascem sempre em estado não verificado.
CREATE FUNCTION trust_initial_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  IF TG_TABLE_NAME = 'identity_verifications' THEN
    IF NEW.status NOT IN ('pending','under_review') THEN NEW.status := 'pending'; END IF;
    NEW.decided_by := NULL; NEW.decided_at := NULL;
  ELSIF TG_TABLE_NAME = 'identity_documents' THEN
    NEW.status := 'submitted'; NEW.reviewed_by := NULL; NEW.reviewed_at := NULL;
  ELSIF TG_TABLE_NAME = 'fee_tables' THEN
    NEW.status := 'draft'; NEW.published_by := NULL; NEW.published_at := NULL;
  ELSIF TG_TABLE_NAME = 'quota_pledges' THEN
    IF NEW.status <> 'pledged' THEN NEW.status := 'pledged'; END IF;
    NEW.payment_ref := NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_initial BEFORE INSERT ON identity_verifications FOR EACH ROW EXECUTE FUNCTION trust_initial_state();
CREATE TRIGGER trg_initial BEFORE INSERT ON identity_documents FOR EACH ROW EXECUTE FUNCTION trust_initial_state();
CREATE TRIGGER trg_initial BEFORE INSERT ON fee_tables FOR EACH ROW EXECUTE FUNCTION trust_initial_state();
CREATE TRIGGER trg_initial BEFORE INSERT ON quota_pledges FOR EACH ROW EXECUTE FUNCTION trust_initial_state();

-- Credencial profissional: o número tem de respeitar o padrão do conselho QUANDO houver padrão configurado (sem padrão, só sanidade).
CREATE FUNCTION credential_format_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pat text; need_uf boolean;
BEGIN
  IF NEW.council_code IS NULL THEN RETURN NEW; END IF;
  SELECT number_pattern, uf_required INTO pat, need_uf FROM professional_councils WHERE code = NEW.council_code;
  IF need_uf AND NEW.uf IS NULL THEN
    RAISE EXCEPTION 'O conselho % exige UF do registro', NEW.council_code USING ERRCODE = '23514';
  END IF;
  IF pat IS NOT NULL AND NEW.number !~ pat THEN
    RAISE EXCEPTION 'Número de registro fora do formato esperado para %', NEW.council_code USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_cred_format BEFORE INSERT OR UPDATE ON professional_credentials FOR EACH ROW EXECUTE FUNCTION credential_format_guard();

-- ================================================================================================ 14. RLS
ALTER TABLE identity_verifications  ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity_documents      ENABLE ROW LEVEL SECURITY;
ALTER TABLE professional_councils   ENABLE ROW LEVEL SECURITY;
ALTER TABLE credential_verifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE trust_events            ENABLE ROW LEVEL SECURITY;
ALTER TABLE verifiable_records      ENABLE ROW LEVEL SECURITY;
ALTER TABLE trust_timestamps        ENABLE ROW LEVEL SECURITY;
ALTER TABLE signature_challenges    ENABLE ROW LEVEL SECURITY;
ALTER TABLE signature_revocations   ENABLE ROW LEVEL SECURITY;
ALTER TABLE signed_agreements              ENABLE ROW LEVEL SECURITY;
ALTER TABLE signed_agreement_parties       ENABLE ROW LEVEL SECURITY;
ALTER TABLE signed_agreement_milestones    ENABLE ROW LEVEL SECURITY;
ALTER TABLE sdg_goals               ENABLE ROW LEVEL SECURITY;
ALTER TABLE esg_pillars             ENABLE ROW LEVEL SECURITY;
ALTER TABLE social_determinants     ENABLE ROW LEVEL SECURITY;
ALTER TABLE impact_tags             ENABLE ROW LEVEL SECURITY;
ALTER TABLE locales                 ENABLE ROW LEVEL SECURITY;
ALTER TABLE translations            ENABLE ROW LEVEL SECURITY;
ALTER TABLE funding_quotas          ENABLE ROW LEVEL SECURITY;
ALTER TABLE quota_pledges           ENABLE ROW LEVEL SECURITY;
ALTER TABLE campaigns               ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_tables              ENABLE ROW LEVEL SECURITY;
ALTER TABLE fee_items               ENABLE ROW LEVEL SECURITY;
ALTER TABLE professional_services   ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnosis_stages        ENABLE ROW LEVEL SECURITY;
ALTER TABLE diagnosis_progress      ENABLE ROW LEVEL SECURITY;

-- Identidade: é da PESSOA (não da organização). Cada uma vê e cria a sua; a decisão é privilegiada.
CREATE POLICY idv_own ON identity_verifications FOR SELECT USING (user_id = app_uid() OR app_priv());
CREATE POLICY idv_insert ON identity_verifications FOR INSERT WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY idv_update ON identity_verifications FOR UPDATE USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY iddoc_own ON identity_documents FOR SELECT USING (user_id = app_uid() OR app_priv());
CREATE POLICY iddoc_insert ON identity_documents FOR INSERT WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY iddoc_update ON identity_documents FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY iddoc_delete ON identity_documents FOR DELETE USING (user_id = app_uid() OR app_priv());

-- Catálogos de referência: leitura para qualquer sessão autenticada (e para o contexto de sistema, que serve as páginas públicas).
CREATE POLICY councils_read ON professional_councils FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY councils_write ON professional_councils FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY sdg_read ON sdg_goals FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY sdg_write ON sdg_goals FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY esg_read ON esg_pillars FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY esg_write ON esg_pillars FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY det_read ON social_determinants FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY det_write ON social_determinants FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY loc_read ON locales FOR SELECT USING (true);
CREATE POLICY loc_write ON locales FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY tr_read ON translations FOR SELECT USING (true);
CREATE POLICY tr_write ON translations FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY dstage_read ON diagnosis_stages FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY dstage_write ON diagnosis_stages FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- Credencial: histórico visível à organização dona; escrita de decisão é privilegiada, anexo de documento é da organização.
CREATE POLICY credver_read ON credential_verifications FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY credver_insert ON credential_verifications FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());

-- Cadeia de custódia: a organização lê a sua; a escrita é privilegiada (nenhuma aplicação "conta a história" por conta própria).
CREATE POLICY trust_read ON trust_events FOR SELECT USING (org_id = app_org() OR app_priv() OR (org_id IS NULL AND app_authenticated()));
-- A organização escreve eventos da própria cadeia (igual a audit_events): a INTEGRIDADE não vem da política, vem do gatilho
-- SECURITY DEFINER que calcula seq/prev_hash/event_hash — ninguém escolhe o próprio encadeamento.
CREATE POLICY trust_insert ON trust_events FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());

-- Registro público: a organização lê e cria o seu; a revogação é UPDATE da própria organização; o contador é privilegiado (guard_columns).
CREATE POLICY vrec_read ON verifiable_records FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY vrec_insert ON verifiable_records FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY vrec_update ON verifiable_records FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY tstamp_read ON trust_timestamps FOR SELECT
  USING (app_priv() OR EXISTS (SELECT 1 FROM verifiable_records r WHERE r.id = trust_timestamps.record_id AND r.org_id = app_org()));
-- O selo é HMAC com a chave do SERVIDOR: a organização não consegue forjar um carimbo válido, então pode gravar o
-- carimbo do próprio registro na mesma transação do fato (a tabela é append-only).
CREATE POLICY tstamp_insert ON trust_timestamps FOR INSERT WITH CHECK (app_priv()
  OR EXISTS (SELECT 1 FROM verifiable_records r WHERE r.id = trust_timestamps.record_id AND r.org_id = app_org()));

-- Desafio de assinatura: é da pessoa; a verificação acontece em contexto de sistema.
CREATE POLICY sigchal_own ON signature_challenges FOR ALL USING (user_id = app_uid() OR app_priv()) WITH CHECK (user_id = app_uid() OR app_priv());
CREATE POLICY sigrev_read ON signature_revocations FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY sigrev_insert ON signature_revocations FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());

-- Acordos: visíveis a QUALQUER parte do acordo (não só a quem criou).
-- As duas tabelas se referenciam, então a política NÃO pode consultar a outra tabela diretamente — isso gera
-- "infinite recursion detected in policy". A travessia passa por funções SECURITY DEFINER, que não reaplicam RLS.
CREATE FUNCTION agreement_owner_org(p_agreement uuid) RETURNS uuid
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
$$ SELECT org_id FROM signed_agreements WHERE id = p_agreement $$;
CREATE FUNCTION agreement_is_draft(p_agreement uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
$$ SELECT status = 'draft' FROM signed_agreements WHERE id = p_agreement $$;
CREATE FUNCTION agreement_has_party(p_agreement uuid, p_org uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS
$$ SELECT EXISTS (SELECT 1 FROM signed_agreement_parties WHERE agreement_id = p_agreement AND org_id = p_org) $$;
REVOKE ALL ON FUNCTION agreement_owner_org(uuid), agreement_is_draft(uuid), agreement_has_party(uuid, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION agreement_owner_org(uuid), agreement_is_draft(uuid), agreement_has_party(uuid, uuid) TO impacto_app;

CREATE POLICY agr_read ON signed_agreements FOR SELECT
  USING (org_id = app_org() OR app_priv() OR agreement_has_party(id, app_org()));
CREATE POLICY agr_insert ON signed_agreements FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY agr_update ON signed_agreements FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY agr_delete ON signed_agreements FOR DELETE USING ((org_id = app_org() AND status = 'draft') OR app_priv());
CREATE POLICY agrparty_read ON signed_agreement_parties FOR SELECT
  USING (org_id = app_org() OR app_priv() OR agreement_owner_org(agreement_id) = app_org());
CREATE POLICY agrparty_write ON signed_agreement_parties FOR INSERT
  WITH CHECK (app_priv() OR (agreement_owner_org(agreement_id) = app_org() AND agreement_is_draft(agreement_id)));
CREATE POLICY agrparty_update ON signed_agreement_parties FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY agrparty_delete ON signed_agreement_parties FOR DELETE
  USING (app_priv() OR (agreement_owner_org(agreement_id) = app_org() AND agreement_is_draft(agreement_id)));
CREATE POLICY agrms_rw ON signed_agreement_milestones FOR ALL
  USING (org_id = app_org() OR app_priv() OR agreement_owner_org(agreement_id) = app_org()
         OR agreement_has_party(agreement_id, app_org()))
  WITH CHECK (org_id = app_org() OR app_priv());

-- Marcadores de impacto: da organização dona do objeto.
CREATE POLICY itags_rw ON impact_tags FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

-- Cotas e campanha: a organização proponente administra; apoio é inserido pela apoiadora; campanha publicada é lida pelo contexto de sistema.
CREATE POLICY fquota_read ON funding_quotas FOR SELECT USING (org_id = app_org() OR app_priv() OR status = 'open');
CREATE POLICY fquota_write ON funding_quotas FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY fquota_update ON funding_quotas FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY fquota_delete ON funding_quotas FOR DELETE USING ((org_id = app_org() AND status = 'draft') OR app_priv());
CREATE POLICY qpledge_read ON quota_pledges FOR SELECT USING (app_priv() OR backer_org_id = app_org()
  OR EXISTS (SELECT 1 FROM funding_quotas q WHERE q.id = quota_pledges.quota_id AND q.org_id = app_org()));
CREATE POLICY qpledge_insert ON quota_pledges FOR INSERT WITH CHECK (app_priv() OR backer_org_id = app_org() OR backer_user_id = app_uid());
CREATE POLICY qpledge_update ON quota_pledges FOR UPDATE USING (app_priv() OR backer_org_id = app_org()) WITH CHECK (app_priv() OR backer_org_id = app_org());
CREATE POLICY camp_read ON campaigns FOR SELECT USING (org_id = app_org() OR app_priv() OR status = 'published');
CREATE POLICY camp_write ON campaigns FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

-- Honorários: tabela publicada é leitura para autenticadas; rascunho só para a administração.
CREATE POLICY fee_read ON fee_tables FOR SELECT USING (status = 'published' OR app_priv());
CREATE POLICY fee_write ON fee_tables FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY feeitem_read ON fee_items FOR SELECT
  USING (app_priv() OR EXISTS (SELECT 1 FROM fee_tables t WHERE t.id = fee_items.fee_table_id AND t.status = 'published'));
CREATE POLICY feeitem_write ON fee_items FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY psvc_read ON professional_services FOR SELECT USING (org_id = app_org() OR app_priv() OR status = 'published');
CREATE POLICY psvc_write ON professional_services FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

-- Diagnóstico guiado: da organização.
CREATE POLICY dprog_rw ON diagnosis_progress FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

-- ================================================================================================ 15. GRANTS
GRANT SELECT, INSERT, UPDATE, DELETE ON identity_verifications, identity_documents, impact_tags, signed_agreements, signed_agreement_parties,
  signed_agreement_milestones, funding_quotas, quota_pledges, campaigns, professional_services, diagnosis_progress, verifiable_records,
  signature_challenges TO impacto_app;
GRANT SELECT, INSERT ON credential_verifications, signature_revocations, trust_events, trust_timestamps TO impacto_app;
GRANT SELECT ON professional_councils, sdg_goals, esg_pillars, social_determinants, locales, translations, diagnosis_stages,
  fee_tables, fee_items TO impacto_app;
-- A administração escreve catálogos e honorários pelo papel privilegiado; o papel da aplicação não altera dado de referência.
GRANT INSERT, UPDATE, DELETE ON professional_councils, sdg_goals, esg_pillars, social_determinants, locales, translations,
  diagnosis_stages, fee_tables, fee_items TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE credential_verifications_id_seq, trust_events_id_seq TO impacto_app;
GRANT EXECUTE ON FUNCTION identity_level(uuid) TO impacto_app;
GRANT EXECUTE ON FUNCTION trust_verify(text, uuid) TO impacto_app;

-- ================================================================================================ 16. DADO DE REFERÊNCIA
-- Conselhos profissionais federais do Brasil. Códigos são de domínio público. number_pattern e official_site ficam NULOS DE PROPÓSITO:
-- o formato do registro varia por conselho/UF/época e a plataforma NÃO inventa regra nem endereço. A administração preenche com fonte.
INSERT INTO professional_councils(code, name, profession, uf_required, lookup_note) VALUES
 ('CRP','Conselho Regional de Psicologia','Psicologia', true, 'Consulta pública é feita no site do conselho; a plataforma não consulta conselho on-line.'),
 ('CRM','Conselho Regional de Medicina','Medicina', true, 'idem'),
 ('CRO','Conselho Regional de Odontologia','Odontologia', true, 'idem'),
 ('CRF','Conselho Regional de Farmácia','Farmácia', true, 'idem'),
 ('CRN','Conselho Regional de Nutrição','Nutrição', true, 'idem'),
 ('COREN','Conselho Regional de Enfermagem','Enfermagem', true, 'idem'),
 ('CREFITO','Conselho Regional de Fisioterapia e Terapia Ocupacional','Fisioterapia e Terapia Ocupacional', true, 'idem'),
 ('CRFA','Conselho Regional de Fonoaudiologia','Fonoaudiologia', true, 'idem'),
 ('CRESS','Conselho Regional de Serviço Social','Serviço Social', true, 'idem'),
 ('CRC','Conselho Regional de Contabilidade','Contabilidade', true, 'idem'),
 ('OAB','Ordem dos Advogados do Brasil','Advocacia', true, 'idem'),
 ('CREA','Conselho Regional de Engenharia e Agronomia','Engenharia e Agronomia', true, 'idem'),
 ('CAU','Conselho de Arquitetura e Urbanismo','Arquitetura e Urbanismo', true, 'idem'),
 ('CRMV','Conselho Regional de Medicina Veterinária','Medicina Veterinária', true, 'idem'),
 ('CRA','Conselho Regional de Administração','Administração', true, 'idem'),
 ('CORECON','Conselho Regional de Economia','Economia', true, 'idem'),
 ('CREF','Conselho Regional de Educação Física','Educação Física', true, 'idem'),
 ('CRB','Conselho Regional de Biblioteconomia','Biblioteconomia', true, 'idem'),
 ('CRBM','Conselho Regional de Biomedicina','Biomedicina', true, 'idem'),
 ('CRBIO','Conselho Regional de Biologia','Biologia', true, 'idem');

-- Etapas do diagnóstico guiado. HIPÓTESE EDITORIAL da plataforma (não é metodologia normatizada por nenhum órgão); revisão técnica pendente.
INSERT INTO diagnosis_stages(code, position, title, purpose, questions, required_documents, help_key) VALUES
 ('context', 1, 'Contexto e território',
  'Entender onde a organização atua e com quem, antes de falar de solução.',
  '[{"key":"territory","label":"Onde o problema acontece (município, bairro, comunidade)","type":"text","required":true},
    {"key":"population","label":"Quem é afetado (descrição agregada, sem dados pessoais)","type":"textarea","required":true},
    {"key":"since","label":"Desde quando a organização acompanha esta situação","type":"text","required":false}]'::jsonb,
  '[]'::jsonb, 'diagnostico.contexto'),
 ('problem', 2, 'Problema e evidências',
  'Separar o problema (o que acontece) das suas causas, com evidência de onde a informação veio.',
  '[{"key":"problem","label":"Qual é o problema, em uma frase","type":"text","required":true},
    {"key":"evidence","label":"Como vocês sabem disso (dado, observação, relato, estudo)","type":"textarea","required":true},
    {"key":"sources","label":"Fontes consultadas","type":"textarea","required":false}]'::jsonb,
  '[{"doc_type":"diagnostico_evidencia","label":"Dado, relatório ou registro que sustenta o problema","required":false}]'::jsonb, 'diagnostico.problema'),
 ('causes', 3, 'Causas e determinantes',
  'Ligar o problema aos determinantes sociais, para não tratar só o sintoma.',
  '[{"key":"root_causes","label":"Causas que vocês identificam","type":"list","required":true},
    {"key":"determinants","label":"Determinantes sociais envolvidos","type":"determinants","required":false}]'::jsonb,
  '[]'::jsonb, 'diagnostico.causas'),
 ('capacity', 4, 'Capacidade da organização',
  'Saber o que a organização já consegue fazer sozinha e onde precisa de apoio.',
  '[{"key":"team","label":"Equipe disponível","type":"textarea","required":true},
    {"key":"experience","label":"O que já foi tentado antes e o que aprenderam","type":"textarea","required":false},
    {"key":"gaps","label":"O que falta (pessoas, formação, estrutura, recurso)","type":"list","required":true}]'::jsonb,
  '[]'::jsonb, 'diagnostico.capacidade'),
 ('compliance', 5, 'Documentação e regularidade',
  'Verificar o que já existe de documentação antes de montar projeto, para não travar na hora da inscrição.',
  '[{"key":"has_statute","label":"Estatuto atualizado e registrado","type":"boolean","required":true},
    {"key":"has_board","label":"Diretoria vigente com ata registrada","type":"boolean","required":true},
    {"key":"certifications","label":"Certificações e qualificações que possui","type":"list","required":false}]'::jsonb,
  '[{"doc_type":"estatuto","label":"Estatuto social","required":true},
    {"doc_type":"ata_eleicao","label":"Ata de eleição da diretoria vigente","required":true},
    {"doc_type":"cnpj","label":"Comprovante de inscrição no CNPJ","required":false}]'::jsonb, 'diagnostico.documentacao'),
 ('objective', 6, 'Objetivo e metas',
  'Transformar o problema em objetivo com meta mensurável.',
  '[{"key":"objective","label":"Objetivo (o que muda, para quem, em quanto tempo)","type":"text","required":true},
    {"key":"goals","label":"Metas com indicador e prazo","type":"goals","required":true},
    {"key":"sdg","label":"ODS relacionados","type":"sdg","required":false}]'::jsonb,
  '[]'::jsonb, 'diagnostico.objetivo'),
 ('plan', 7, 'Plano de ação e orçamento',
  'Detalhar as ações, quem faz, quando e quanto custa — base do projeto e da necessidade de financiamento.',
  '[{"key":"actions","label":"Ações, responsáveis e prazos","type":"actions","required":true},
    {"key":"budget","label":"Itens de orçamento","type":"budget","required":true},
    {"key":"own_contribution","label":"O que a organização entra (contrapartida)","type":"textarea","required":false}]'::jsonb,
  '[]'::jsonb, 'diagnostico.plano'),
 ('needs', 8, 'Necessidade e forma de apoio',
  'Definir o que será pedido: profissional da plataforma, financiamento em cotas, doação direta ou candidatura a edital.',
  '[{"key":"support_kind","label":"Tipo de apoio necessário","type":"enum","required":true,
     "options":["profissional","financiamento","formacao","estrutura","articulacao"]},
    {"key":"amount_cents","label":"Valor estimado, se houver","type":"money","required":false},
    {"key":"publicize","label":"Pode dar publicidade ao pedido","type":"boolean","required":true}]'::jsonb,
  '[]'::jsonb, 'diagnostico.necessidade');

-- ================================================================================================ 17. FORMATOS DE EXPORTAÇÃO
-- A exportação do Integration Hub (v0.13.0) só aceitava csv e json. Agora a plataforma escreve docx, odt, xlsx, ods,
-- xml e pdf (escritores próprios em services/formats.py — sem biblioteca nova, pois os registros estão bloqueados).
ALTER TABLE integration_exports DROP CONSTRAINT integration_exports_format_check;
ALTER TABLE integration_exports ADD CONSTRAINT integration_exports_format_check
  CHECK (format IN ('csv','json','xlsx','ods','xml','docx','odt','pdf'));
