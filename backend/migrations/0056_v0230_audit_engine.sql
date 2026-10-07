-- v0.23.0 — MOTOR DE AUDITORIA: CAMPOS QUE FALTAVAM, CORRELAÇÃO E ANTES/DEPOIS
--
-- O QUE JÁ EXISTIA (e por isso não é refeito)
--
-- `audit_events` é append-only desde a v0.2.0, tem cadeia de hash por organização calculada no
-- banco (`chain_audit`/`audit_verify`), redação de campo sensível, e 319 chamadas no código. O
-- prompt desta rodada pede um "motor de auditoria" como se não houvesse nenhum; o que falta são
-- campos e relações específicos, não a tabela.
--
-- O QUE FALTAVA, item por item do modelo pedido
--
--   actor_type        → não existia. Toda a trilha dizia QUEM, nunca O QUE o quem era: pessoa,
--                       administrador, sistema, IA, automação ou integração. Numa investigação é a
--                       primeira pergunta depois de "quem".
--   before_state      → não existia. A trilha registrava que algo mudou, não de que PARA que.
--   after_state       → idem.
--   correlation_id    → não existia. Dava para perguntar "quem mexeu neste documento?" e não
--                       "mostre-me a cadeia de acontecimentos que levou este documento até aqui".
--   parent_event_id   → não existia. Sem ele, uma cadeia é uma lista ordenada por tempo, não uma
--                       árvore de causa.
--   session_id        → não existia. `request_id` identifica a requisição, não a sessão.
--   user_agent        → não existia.
--   severity          → não existia. Tudo tinha o mesmo peso.
--   status            → não existia. Só o SUCESSO era registrado; a tentativa recusada não entrava.
--   source            → não existia (api, job, cli, webhook, migration).
--   resource_name     → não existia. O id sobrevive ao objeto apagado; o nome é o que a pessoa lê.
--
-- A CADEIA DE HASH E OS CAMPOS NOVOS
--
-- `audit_material()` define o que o hash protege. Acrescentar coluna ao material invalidaria o hash
-- de TODA linha existente — a verificação passaria a acusar manipulação onde não houve, o que é
-- pior que não verificar. A solução é versionar o material: `chain_version = 1` usa a fórmula
-- antiga, `2` usa a nova com os campos novos. Linhas antigas continuam verificáveis, linhas novas
-- têm os campos novos PROTEGIDOS. Calcular o material novo sobre linhas antigas seria reescrever a
-- história para que ela feche.

ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS actor_type text NOT NULL DEFAULT 'user';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS session_id uuid;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS user_agent text;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS correlation_id text;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS parent_event_id bigint REFERENCES audit_events(id);
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS resource_name text;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS severity text NOT NULL DEFAULT 'info';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'success';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS source text NOT NULL DEFAULT 'api';
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS before_state jsonb;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS after_state jsonb;
ALTER TABLE audit_events ADD COLUMN IF NOT EXISTS chain_version smallint NOT NULL DEFAULT 1;

ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_actor_type_known;
ALTER TABLE audit_events ADD CONSTRAINT audit_actor_type_known
  CHECK (actor_type IN ('user','admin','system','ai','automation','integration'));

ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_severity_known;
ALTER TABLE audit_events ADD CONSTRAINT audit_severity_known
  CHECK (severity IN ('info','notice','warning','critical'));

-- `status` inclui `denied` e `failed` de propósito: uma trilha que só registra sucesso descreve um
-- sistema em que nada é recusado. A tentativa recusada é o sinal que uma investigação procura.
ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_status_known;
ALTER TABLE audit_events ADD CONSTRAINT audit_status_known
  CHECK (status IN ('success','denied','failed'));

ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_source_known;
ALTER TABLE audit_events ADD CONSTRAINT audit_source_known
  CHECK (source IN ('api','job','cli','webhook','migration','test'));

ALTER TABLE audit_events DROP CONSTRAINT IF EXISTS audit_text_sizes;
ALTER TABLE audit_events ADD CONSTRAINT audit_text_sizes
  CHECK (length(coalesce(user_agent,'')) <= 400
     AND length(coalesce(correlation_id,'')) <= 64
     AND length(coalesce(resource_name,'')) <= 300);

-- O evento pai é do MESMO rastro: um pai de outra correlação faria a árvore mentir.
CREATE OR REPLACE FUNCTION audit_parent_is_same_trail() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE pai_correlacao text; pai_org uuid;
BEGIN
  IF NEW.parent_event_id IS NULL THEN RETURN NEW; END IF;
  SELECT correlation_id, org_id INTO pai_correlacao, pai_org
    FROM audit_events WHERE id = NEW.parent_event_id;
  IF pai_org IS DISTINCT FROM NEW.org_id THEN
    RAISE EXCEPTION 'evento pai pertence a outra organização: a árvore de causa não cruza inquilino'
      USING ERRCODE = '42501';
  END IF;
  IF NEW.correlation_id IS NOT NULL AND pai_correlacao IS NOT NULL
     AND pai_correlacao <> NEW.correlation_id THEN
    RAISE EXCEPTION 'evento pai está em outra correlação (% ≠ %)', pai_correlacao, NEW.correlation_id
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS aa_trg_audit_parent ON audit_events;
CREATE TRIGGER aa_trg_audit_parent BEFORE INSERT ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_parent_is_same_trail();

-- Material versionado. A versão 1 é LITERALMENTE a fórmula anterior, para que nenhum hash antigo
-- mude; a 2 acrescenta os campos novos.
CREATE OR REPLACE FUNCTION audit_material(e audit_events) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE WHEN e.chain_version <= 1 THEN
    concat_ws('|', e.prev_hash, e.seq::text, coalesce(e.org_id::text,''),
              coalesce(e.actor_user_id::text,''), e.action, coalesce(e.object_type,''),
              coalesce(e.object_id,''), e.payload::text, ts_canonical(e.at))
  ELSE
    concat_ws('|', e.prev_hash, e.seq::text, coalesce(e.org_id::text,''),
              coalesce(e.actor_user_id::text,''), e.action, coalesce(e.object_type,''),
              coalesce(e.object_id,''), e.payload::text, ts_canonical(e.at),
              e.actor_type, e.severity, e.status, e.source,
              coalesce(e.session_id::text,''), coalesce(e.user_agent,''),
              coalesce(e.correlation_id,''), coalesce(e.parent_event_id::text,''),
              coalesce(e.resource_name,''),
              coalesce(e.before_state::text,''), coalesce(e.after_state::text,''))
  END
$$;

-- Toda linha NOVA nasce na versão 2. O gatilho de cadeia é BEFORE INSERT e roda depois deste
-- (ordem alfabética do nome do gatilho), então o hash já é calculado com o material novo.
CREATE OR REPLACE FUNCTION audit_new_rows_use_chain_v2() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.chain_version := 2;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS ab_trg_audit_chain_version ON audit_events;
CREATE TRIGGER ab_trg_audit_chain_version BEFORE INSERT ON audit_events
  FOR EACH ROW EXECUTE FUNCTION audit_new_rows_use_chain_v2();

-- ÍNDICES
--
-- `ix_audit_object` é a linha do tempo por entidade — a consulta que o prompt pede ("mostre-me
-- tudo o que aconteceu com ESTE documento") e que até aqui fazia varredura sequencial na tabela
-- que mais cresce no banco.
CREATE INDEX IF NOT EXISTS ix_audit_object ON audit_events (object_type, object_id, id DESC)
  WHERE object_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_audit_correlation ON audit_events (correlation_id, id)
  WHERE correlation_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_audit_actor ON audit_events (actor_user_id, id DESC)
  WHERE actor_user_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_audit_severity ON audit_events (severity, id DESC)
  WHERE severity IN ('warning','critical');
CREATE INDEX IF NOT EXISTS ix_audit_not_success ON audit_events (status, id DESC)
  WHERE status <> 'success';

-- CADEIA DE CAUSA: a árvore inteira a partir de um evento, pelos dois lados.
CREATE OR REPLACE FUNCTION audit_trail_of(p_correlation text)
RETURNS TABLE(id bigint, parent_event_id bigint, depth int, at timestamptz, action text,
              actor_type text, actor_user_id uuid, object_type text, object_id text,
              resource_name text, status text, severity text, source text)
LANGUAGE sql STABLE AS $$
  WITH RECURSIVE raiz AS (
    SELECT e.*, 0 AS depth FROM audit_events e
     WHERE e.correlation_id = p_correlation AND e.parent_event_id IS NULL
    UNION ALL
    SELECT f.*, r.depth + 1 FROM audit_events f
      JOIN raiz r ON f.parent_event_id = r.id
     WHERE f.correlation_id = p_correlation
  )
  SELECT r.id, r.parent_event_id, r.depth, r.at, r.action, r.actor_type, r.actor_user_id,
         r.object_type, r.object_id, r.resource_name, r.status, r.severity, r.source
    FROM raiz r ORDER BY r.id;
$$;

-- CATEGORIA: derivada do prefixo da ação, não declarada numa segunda tabela que envelhece.
CREATE OR REPLACE FUNCTION audit_category(p_action text) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE split_part(p_action, '.', 1)
    WHEN 'auth' THEN 'AUTH'
    WHEN 'user' THEN 'USERS'
    WHEN 'member' THEN 'USERS'
    WHEN 'staff' THEN 'USERS'
    WHEN 'org' THEN 'ORGS'
    WHEN 'organization' THEN 'ORGS'
    WHEN 'document' THEN 'DOCUMENTS'
    WHEN 'document_assembly' THEN 'DOCUMENTS'
    WHEN 'signature' THEN 'DOCUMENTS'
    WHEN 'project' THEN 'PROJECTS'
    WHEN 'indicator' THEN 'PROJECTS'
    WHEN 'evidence' THEN 'PROJECTS'
    WHEN 'application' THEN 'WORKFLOWS'
    WHEN 'approval' THEN 'WORKFLOWS'
    WHEN 'compliance' THEN 'WORKFLOWS'
    WHEN 'billing' THEN 'FINANCE'
    WHEN 'payment' THEN 'FINANCE'
    WHEN 'invoice' THEN 'FINANCE'
    WHEN 'expense' THEN 'FINANCE'
    WHEN 'instruction' THEN 'FINANCE'
    WHEN 'accounting' THEN 'FINANCE'
    WHEN 'ai' THEN 'AI'
    WHEN 'security' THEN 'SECURITY'
    WHEN 'audit' THEN 'SECURITY'
    WHEN 'encryption' THEN 'SECURITY'
    WHEN 'admin' THEN 'ADMIN'
    WHEN 'integration' THEN 'INTEGRATIONS'
    ELSE 'OTHER'
  END
$$;

GRANT SELECT, INSERT ON audit_events TO impacto_app;
