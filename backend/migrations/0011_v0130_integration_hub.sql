-- 0011 — v0.13.0: INTEGRATION HUB — fronteira entre o núcleo da IMPACTO e sistemas externos (ERP, governo, parceiros, identidade, pagamento, BI).
-- REUTILIZA (não duplica): adapters/http_client.py (guarda de SSRF, retries), defusedxml (XXE), documents (validação de upload/magic bytes/zip bomb),
-- storage (URL temporária), audit_events (auditoria), job_runs (histórico de jobs da plataforma), notifications, RLS por organização
-- e o padrão de idempotência do billing_events. O importador de editais (call_sources) e o webhook do Stripe CONTINUAM como estão.
-- PRINCÍPIOS: o núcleo depende de CONTRATOS INTERNOS, nunca de fornecedor; segredo nunca em coluna legível; ID interno nunca é substituído por ID
-- externo; nada é sobrescrito em silêncio (conflito é registrado); toda operação é auditável e idempotente.

-- ------------------------------------------------------------------------------------------------ catálogo de provedores (dado de referência)
-- Sincronizado de config/integration_providers.json pelo runner de migrations (mesmo mecanismo de plans/feature flags).
CREATE TABLE integration_providers (
  key            text PRIMARY KEY CHECK (key ~ '^[a-z0-9_]{3,40}$'),
  name           text NOT NULL CHECK (length(name) BETWEEN 2 AND 120),
  category       text NOT NULL CHECK (category IN ('erp','government','identity','payment','communication','bi','storage','crm','lms','custom')),
  api_style      text NOT NULL CHECK (api_style IN ('rest','soap','file','hybrid','oauth','none')),
  auth_kinds     text[] NOT NULL DEFAULT '{}',
  capabilities   jsonb NOT NULL DEFAULT '{}'::jsonb,   -- {connect,pull,push,webhook,batch,async,health}: yes|no|partial|not_implemented
  -- maturidade REAL da integração; 'production_active' exige evidência externa e NUNCA é definido por código de aplicação.
  maturity       text NOT NULL DEFAULT 'scaffolded' CHECK (maturity IN ('scaffolded','contract_tested','sandbox','homologated','production_active')),
  docs_url       text CHECK (docs_url IS NULL OR docs_url ~ '^https://'),
  notes          text CHECK (length(notes) <= 2000),
  active         boolean NOT NULL DEFAULT true,
  updated_at     timestamptz NOT NULL DEFAULT now()
);

-- ------------------------------------------------------------------------------------------------ conexões (por organização e ambiente)
CREATE TABLE integration_connections (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  provider_key       text NOT NULL REFERENCES integration_providers(key),
  name               text NOT NULL CHECK (length(name) BETWEEN 2 AND 120),
  environment        text NOT NULL CHECK (environment IN ('development','sandbox','homologation','production')),
  status             text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','paused','revoked')),
  endpoint           text CHECK (endpoint IS NULL OR endpoint ~ '^https?://'),
  external_system_id text CHECK (length(external_system_id) <= 200),
  config             jsonb NOT NULL DEFAULT '{}'::jsonb,         -- configuração NÃO sensível (caminhos, códigos de filial, limites)
  health_state       text NOT NULL DEFAULT 'unconfigured' CHECK (health_state IN ('healthy','degraded','unavailable','unconfigured','unauthorized','unknown')),
  health_detail      text CHECK (length(health_detail) <= 500),
  last_health_at     timestamptz,
  last_success_at    timestamptz,
  failure_streak     integer NOT NULL DEFAULT 0 CHECK (failure_streak >= 0),
  -- disjuntor: quando aberto, o hub recusa chamadas até o horário indicado (protege o núcleo de sistema externo instável)
  circuit_open_until timestamptz,
  metadata           jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by         uuid REFERENCES users(id),
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, provider_key, environment, name)
);
CREATE INDEX ix_int_conn_org ON integration_connections(org_id, status);
CREATE INDEX ix_int_conn_health ON integration_connections(health_state, last_health_at DESC);

-- ------------------------------------------------------------------------------------------------ credenciais (cifradas; nunca saem pela API)
-- O segredo é gravado CIFRADO (AES-GCM na aplicação, chave derivada de SECRET_KEY/INTEGRATION_SECRET_KEY) e a coluna é inacessível ao papel da
-- aplicação em SELECT: a leitura acontece por função SECURITY DEFINER usada só pelo hub. A API devolve apenas a "dica" (últimos caracteres).
CREATE TABLE integration_credentials (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id  uuid NOT NULL REFERENCES integration_connections(id) ON DELETE CASCADE,
  kind           text NOT NULL CHECK (kind IN ('api_key','bearer_token','basic_auth','oauth2_client_credentials','oauth2_refresh','certificate','secret_ref')),
  secret_cipher  bytea,                                   -- NULL quando kind = 'secret_ref' (segredo fica no gerenciador externo)
  secret_ref     text CHECK (length(secret_ref) <= 300),  -- referência em gerenciador de segredos (não é o segredo)
  hint           text CHECK (length(hint) <= 40),          -- ex.: "••••4f2a" (nunca o segredo)
  username       text CHECK (length(username) <= 200),     -- basic/oauth client_id (não é segredo por si)
  scopes         text[] NOT NULL DEFAULT '{}',
  expires_at     timestamptz,
  rotated_at     timestamptz,
  created_by     uuid REFERENCES users(id),
  created_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (secret_cipher IS NOT NULL OR secret_ref IS NOT NULL)
);
CREATE UNIQUE INDEX ux_int_cred_active ON integration_credentials(connection_id, kind);

-- ------------------------------------------------------------------------------------------------ mapeamento de campos (mapping como DADO)
CREATE TABLE integration_mappings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id uuid NOT NULL REFERENCES integration_connections(id) ON DELETE CASCADE,
  entity        text NOT NULL CHECK (entity IN ('person','organization','document','course','certificate','event','invoice','payment','partner','call')),
  direction     text NOT NULL CHECK (direction IN ('inbound','outbound','both')),
  source_path   text NOT NULL CHECK (length(source_path) BETWEEN 1 AND 200),
  target_field  text NOT NULL CHECK (length(target_field) BETWEEN 1 AND 100),
  transform     text NOT NULL DEFAULT 'none' CHECK (transform IN ('none','trim','upper','lower','digits_only','date_iso','date_br','decimal_comma','cents_from_decimal','boolean','enum','split_list')),
  enum_map      jsonb NOT NULL DEFAULT '{}'::jsonb,
  required      boolean NOT NULL DEFAULT false,
  default_value text CHECK (length(default_value) <= 200),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (connection_id, entity, direction, target_field)
);
CREATE INDEX ix_int_map_conn ON integration_mappings(connection_id, entity, direction);

-- ------------------------------------------------------------------------------------------------ IDs externos (o ID interno NUNCA é substituído)
CREATE TABLE external_entity_links (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connection_id    uuid NOT NULL REFERENCES integration_connections(id) ON DELETE CASCADE,
  entity           text NOT NULL CHECK (entity IN ('person','organization','document','course','certificate','event','invoice','payment','partner','call')),
  internal_id      uuid NOT NULL,
  external_id      text NOT NULL CHECK (length(external_id) BETWEEN 1 AND 200),
  external_version text CHECK (length(external_version) <= 100),
  last_synced_at   timestamptz,
  sync_status      text NOT NULL DEFAULT 'linked' CHECK (sync_status IN ('linked','pending','conflict','stale','deleted_externally')),
  conflict_detail  jsonb NOT NULL DEFAULT '{}'::jsonb,   -- conflito é REGISTRADO, nunca resolvido em silêncio
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (connection_id, entity, external_id),
  UNIQUE (connection_id, entity, internal_id)
);
CREATE INDEX ix_ext_link_internal ON external_entity_links(entity, internal_id);
CREATE INDEX ix_ext_link_org ON external_entity_links(org_id, sync_status);

-- ------------------------------------------------------------------------------------------------ jobs de integração (idempotentes)
CREATE TABLE integration_jobs (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connection_id   uuid REFERENCES integration_connections(id) ON DELETE CASCADE,
  operation       text NOT NULL CHECK (length(operation) BETWEEN 2 AND 60),
  entity          text CHECK (length(entity) <= 40),
  direction       text NOT NULL CHECK (direction IN ('inbound','outbound','bidirectional')),
  strategy        text NOT NULL DEFAULT 'manual' CHECK (strategy IN ('full','incremental','event_driven','scheduled','manual')),
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','succeeded','partial','failed','retrying','canceled')),
  attempts        integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts    integer NOT NULL DEFAULT 3 CHECK (max_attempts BETWEEN 1 AND 10),
  next_attempt_at timestamptz,
  correlation_id  text NOT NULL CHECK (length(correlation_id) BETWEEN 8 AND 64),
  idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 8 AND 200),
  request         jsonb NOT NULL DEFAULT '{}'::jsonb,     -- parâmetros (NUNCA segredo)
  result          jsonb NOT NULL DEFAULT '{}'::jsonb,     -- contadores: lidos/criados/atualizados/ignorados/erros
  error_code      text CHECK (length(error_code) <= 60),
  error_detail    text CHECK (length(error_detail) <= 1000),
  error_kind      text CHECK (error_kind IN ('temporary','permanent')),   -- 500/timeout = temporário; 400/422 = permanente (não repete para sempre)
  started_at      timestamptz,
  finished_at     timestamptz,
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, idempotency_key)
);
CREATE INDEX ix_int_job_conn ON integration_jobs(connection_id, created_at DESC);
CREATE INDEX ix_int_job_due ON integration_jobs(status, next_attempt_at) WHERE status IN ('pending','retrying');
CREATE INDEX ix_int_job_org ON integration_jobs(org_id, created_at DESC);

-- ------------------------------------------------------------------------------------------------ eventos de domínio (outbox) e entregas
CREATE TABLE integration_events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid REFERENCES organizations(id) ON DELETE CASCADE,
  event_type  text NOT NULL CHECK (event_type ~ '^[A-Z]+(\.[A-Z_]+)+$'),
  entity      text NOT NULL CHECK (length(entity) <= 40),
  entity_id   uuid,
  version     integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  payload     jsonb NOT NULL DEFAULT '{}'::jsonb,         -- mínimo necessário (LGPD): identificadores e campos públicos do domínio
  occurred_at timestamptz NOT NULL DEFAULT now(),
  actor_id    uuid REFERENCES users(id)
);
CREATE INDEX ix_int_event_type ON integration_events(event_type, occurred_at DESC);
CREATE INDEX ix_int_event_org ON integration_events(org_id, occurred_at DESC);

CREATE TABLE integration_subscriptions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connection_id uuid REFERENCES integration_connections(id) ON DELETE SET NULL,
  name          text NOT NULL CHECK (length(name) BETWEEN 2 AND 120),
  url           text NOT NULL CHECK (url ~ '^https://'),   -- saída só por HTTPS (a guarda de SSRF valida o destino na entrega)
  event_types   text[] NOT NULL CHECK (cardinality(event_types) BETWEEN 1 AND 40),
  secret_cipher bytea NOT NULL,                            -- segredo de assinatura HMAC (cifrado)
  status        text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','disabled')),
  headers       jsonb NOT NULL DEFAULT '{}'::jsonb,        -- cabeçalhos não sensíveis
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, name)
);
CREATE INDEX ix_int_sub_org ON integration_subscriptions(org_id, status);

CREATE TABLE integration_deliveries (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subscription_id uuid NOT NULL REFERENCES integration_subscriptions(id) ON DELETE CASCADE,
  event_id        uuid NOT NULL REFERENCES integration_events(id) ON DELETE CASCADE,
  status          text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','delivered','retrying','dead_letter','skipped')),
  attempts        integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  response_code   integer,
  error_detail    text CHECK (length(error_detail) <= 500),
  correlation_id  text NOT NULL CHECK (length(correlation_id) BETWEEN 8 AND 64),
  delivered_at    timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (subscription_id, event_id)
);
CREATE INDEX ix_int_deliv_due ON integration_deliveries(status, next_attempt_at) WHERE status IN ('pending','retrying');
CREATE INDEX ix_int_deliv_sub ON integration_deliveries(subscription_id, created_at DESC);

-- ------------------------------------------------------------------------------------------------ mensagens de ENTRADA (dedupe/idempotência)
CREATE TABLE integration_inbound (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  connection_id     uuid NOT NULL REFERENCES integration_connections(id) ON DELETE CASCADE,
  external_event_id text NOT NULL CHECK (length(external_event_id) BETWEEN 1 AND 200),
  event_type        text CHECK (length(event_type) <= 100),
  payload_sha256    char(64) NOT NULL,
  status            text NOT NULL DEFAULT 'received' CHECK (status IN ('received','processed','ignored','rejected','duplicate')),
  detail            text CHECK (length(detail) <= 500),
  job_id            uuid REFERENCES integration_jobs(id) ON DELETE SET NULL,
  received_at       timestamptz NOT NULL DEFAULT now(),
  processed_at      timestamptz,
  UNIQUE (connection_id, external_event_id)
);
CREATE INDEX ix_int_inbound_conn ON integration_inbound(connection_id, received_at DESC);

-- ------------------------------------------------------------------------------------------------ importação de arquivos (com PRÉ-VISUALIZAÇÃO e APROVAÇÃO)
CREATE TABLE integration_imports (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  connection_id uuid REFERENCES integration_connections(id) ON DELETE SET NULL,
  entity        text NOT NULL CHECK (entity IN ('person','organization','document','course','certificate','event','invoice','payment','partner','call')),
  format        text NOT NULL CHECK (format IN ('csv','xlsx','json','xml')),
  document_id   uuid REFERENCES documents(id) ON DELETE SET NULL,   -- arquivo já validado pelo cofre (magic bytes, tamanho, zip bomb, antivírus)
  filename      text NOT NULL CHECK (length(filename) <= 255),
  sha256        char(64) NOT NULL,
  status        text NOT NULL DEFAULT 'uploaded' CHECK (status IN ('uploaded','validated','parsed','previewed','approved','imported','rejected','failed')),
  rows_total    integer NOT NULL DEFAULT 0,
  rows_valid    integer NOT NULL DEFAULT 0,
  rows_invalid  integer NOT NULL DEFAULT 0,
  rows_imported integer NOT NULL DEFAULT 0,
  report        jsonb NOT NULL DEFAULT '{}'::jsonb,
  approved_by   uuid REFERENCES users(id),
  approved_at   timestamptz,
  created_by    uuid REFERENCES users(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, entity, sha256)                                   -- o mesmo arquivo não é importado duas vezes (idempotência por conteúdo)
);
CREATE INDEX ix_int_import_org ON integration_imports(org_id, created_at DESC);

CREATE TABLE integration_import_rows (
  id         bigserial PRIMARY KEY,
  import_id  uuid NOT NULL REFERENCES integration_imports(id) ON DELETE CASCADE,
  row_no     integer NOT NULL CHECK (row_no >= 1),
  raw        jsonb NOT NULL DEFAULT '{}'::jsonb,
  mapped     jsonb NOT NULL DEFAULT '{}'::jsonb,
  valid      boolean NOT NULL DEFAULT false,
  errors     text[] NOT NULL DEFAULT '{}',
  UNIQUE (import_id, row_no)
);

-- ------------------------------------------------------------------------------------------------ exportação / datasets (BI sem acesso direto ao banco)
CREATE TABLE integration_exports (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  dataset     text NOT NULL CHECK (length(dataset) BETWEEN 2 AND 60),
  format      text NOT NULL CHECK (format IN ('csv','json')),
  filters     jsonb NOT NULL DEFAULT '{}'::jsonb,
  status      text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','ready','failed','expired')),
  rows        integer NOT NULL DEFAULT 0,
  document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  error_detail text CHECK (length(error_detail) <= 500),
  requested_by uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz
);
CREATE INDEX ix_int_export_org ON integration_exports(org_id, created_at DESC);

-- ------------------------------------------------------------------------------------------------ leitura de segredo só por função privilegiada
CREATE FUNCTION integration_secret(cred_id uuid) RETURNS bytea LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  SELECT secret_cipher FROM integration_credentials WHERE id = cred_id
$$;
REVOKE ALL ON FUNCTION integration_secret(uuid) FROM PUBLIC;

CREATE FUNCTION integration_subscription_secret(sub_id uuid) RETURNS bytea LANGUAGE sql SECURITY DEFINER SET search_path = public AS $$
  SELECT secret_cipher FROM integration_subscriptions WHERE id = sub_id
$$;
REVOKE ALL ON FUNCTION integration_subscription_secret(uuid) FROM PUBLIC;

-- guarda: a aplicação não promove maturidade de provedor nem estado de saúde por fora do hub
CREATE FUNCTION integration_provider_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user = 'impacto_app' AND NOT app_priv() THEN   -- o dono (runner de migrations) sincroniza o catálogo; a aplicação só em modo privilegiado
    RAISE EXCEPTION 'catálogo de provedores é mantido pela administração da plataforma' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_integration_provider_guard BEFORE INSERT OR UPDATE OR DELETE ON integration_providers
  FOR EACH ROW EXECUTE FUNCTION integration_provider_guard();

-- ------------------------------------------------------------------------------------------------ RLS (isolamento por organização)
ALTER TABLE integration_providers ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE external_entity_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_inbound ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_import_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_exports ENABLE ROW LEVEL SECURITY;

-- catálogo: leitura por qualquer pessoa autenticada (é informação pública de produto); escrita só administração (gatilho acima)
CREATE POLICY int_providers_read ON integration_providers FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY int_providers_write ON integration_providers FOR ALL USING (app_priv()) WITH CHECK (app_priv());

CREATE POLICY int_conn_rw ON integration_connections FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
-- credencial: a organização pode gravar/apagar, mas NÃO ler o segredo (a coluna é negada no GRANT abaixo)
CREATE POLICY int_cred_rw ON integration_credentials FOR ALL
  USING (app_priv() OR EXISTS (SELECT 1 FROM integration_connections c WHERE c.id = connection_id AND c.org_id = app_org()))
  WITH CHECK (app_priv() OR EXISTS (SELECT 1 FROM integration_connections c WHERE c.id = connection_id AND c.org_id = app_org()));
CREATE POLICY int_map_rw ON integration_mappings FOR ALL
  USING (app_priv() OR EXISTS (SELECT 1 FROM integration_connections c WHERE c.id = connection_id AND c.org_id = app_org()))
  WITH CHECK (app_priv() OR EXISTS (SELECT 1 FROM integration_connections c WHERE c.id = connection_id AND c.org_id = app_org()));
CREATE POLICY int_links_rw ON external_entity_links FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY int_jobs_read ON integration_jobs FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY int_jobs_write ON integration_jobs FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY int_jobs_update ON integration_jobs FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());   -- progresso só pelo hub
CREATE POLICY int_events_read ON integration_events FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY int_events_write ON integration_events FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());   -- emitido pelo núcleo na própria
-- transação da organização; o payload é montado pelo servidor, nunca pelo cliente. Sem UPDATE/DELETE: o registro é apenas acrescentado.
CREATE POLICY int_sub_rw ON integration_subscriptions FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY int_deliv_read ON integration_deliveries FOR SELECT
  USING (app_priv() OR EXISTS (SELECT 1 FROM integration_subscriptions s WHERE s.id = subscription_id AND s.org_id = app_org()));
CREATE POLICY int_deliv_write ON integration_deliveries FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY int_inbound_read ON integration_inbound FOR SELECT
  USING (app_priv() OR EXISTS (SELECT 1 FROM integration_connections c WHERE c.id = connection_id AND c.org_id = app_org()));
CREATE POLICY int_inbound_write ON integration_inbound FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY int_import_rw ON integration_imports FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY int_import_rows_rw ON integration_import_rows FOR ALL
  USING (app_priv() OR EXISTS (SELECT 1 FROM integration_imports i WHERE i.id = import_id AND i.org_id = app_org()))
  WITH CHECK (app_priv() OR EXISTS (SELECT 1 FROM integration_imports i WHERE i.id = import_id AND i.org_id = app_org()));
CREATE POLICY int_export_rw ON integration_exports FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

-- ------------------------------------------------------------------------------------------------ privilégios
GRANT SELECT ON integration_providers TO impacto_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON integration_connections, integration_mappings, external_entity_links, integration_jobs,
  integration_events, integration_deliveries, integration_inbound, integration_imports,
  integration_import_rows, integration_exports TO impacto_app;
-- assinatura de webhook: a aplicação cria/apaga e lê os metadados, mas NÃO lê `secret_cipher`
-- (um GRANT de tabela tornaria o grant de coluna inútil; a leitura é só por integration_subscription_secret()).
GRANT INSERT, DELETE ON integration_subscriptions TO impacto_app;
GRANT UPDATE (name, url, event_types, status, headers) ON integration_subscriptions TO impacto_app;
-- credencial: a aplicação insere/apaga e lê os METADADOS, mas NÃO tem SELECT no segredo cifrado (leitura só por integration_secret()).
GRANT INSERT, DELETE ON integration_credentials TO impacto_app;
GRANT SELECT (id, connection_id, kind, secret_ref, hint, username, scopes, expires_at, rotated_at, created_by, created_at)
  ON integration_credentials TO impacto_app;
GRANT UPDATE (hint, username, scopes, expires_at, rotated_at) ON integration_credentials TO impacto_app;
GRANT SELECT (id, org_id, connection_id, name, url, event_types, status, headers, created_by, created_at)
  ON integration_subscriptions TO impacto_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO impacto_app;
GRANT EXECUTE ON FUNCTION integration_secret(uuid) TO impacto_app;
GRANT EXECUTE ON FUNCTION integration_subscription_secret(uuid) TO impacto_app;
