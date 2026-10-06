-- v0.20.0 — proveniência de dado externo e o conceito de dado DESATUALIZADO.
--
-- O QUE EXISTIA. Uma arquitetura de procedência honesta: `source_name`, `source_url` e `source_date`
-- obrigatórios em `territory_indicators` e `equity_denominators`, `method_note` obrigatório no
-- denominador, imutabilidade por gatilho, versionamento por vigência, e a separação explícita entre
-- "carga oficial" e "conhecimento da plataforma" (`territories.from_official_load`).
--
-- O QUE FALTAVA, e é o que esta migração acrescenta:
--
--   PUBLISHER   o ÓRGÃO publicador não era campo: ficava dissolvido no texto livre de `source_name`
--               ("IBGE — Censo Demográfico 2022"). Sem campo, não dá para responder "quais números
--               vieram do IBGE?" nem para avisar quando uma fonte inteira muda de metodologia.
--   DATASET     não havia identificador do conjunto de dados.
--   VERSION     "Censo 2022 revisão 2" não tinha onde ser registrado.
--   LICENSE     NENHUMA tabela de dado externo tinha licença. Redistribuir dado de terceiro sem saber
--               sob qual licença ele veio é problema jurídico, não detalhe.
--   HASH        nada ligava o número carregado ao ARQUIVO de onde ele saiu.
--   PUBLISHED_AT vs RETRIEVED_AT: as duas datas estavam colapsadas em `source_date`, que o importador
--               usa como "data da consulta". A data em que a FONTE publicou não era registrada.
--   STALE       e, sobretudo: não existia conceito de dado velho. Uma linha com `effective_until`
--               nula é "a vigente" — mesmo que o `reference_date` seja de 2010. O produto sabia
--               dizer que um número não foi substituído; não sabia dizer que ele envelheceu.
--
-- A SOLUÇÃO É UM CATÁLOGO, NÃO NOVE COLUNAS POR TABELA. Proveniência é um objeto com identidade: o
-- mesmo conjunto de dados alimenta centenas de linhas, e repetir publicador, licença e hash em cada
-- uma produziria divergência na primeira correção.

CREATE TABLE external_datasets (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key             text NOT NULL CHECK (key ~ '^[a-z][a-z0-9_.-]{2,80}$'),
  version         text NOT NULL CHECK (length(version) BETWEEN 1 AND 60),

  -- quem publicou, e o que
  publisher       text NOT NULL CHECK (length(publisher) BETWEEN 2 AND 200),
  dataset         text NOT NULL CHECK (length(dataset) BETWEEN 2 AND 300),
  url             text CHECK (url IS NULL OR url ~ '^https?://'),

  -- as DUAS datas, separadas de propósito
  published_at    date,
  retrieved_at    date NOT NULL,

  -- cobertura, método e licença
  geographic_scope text NOT NULL CHECK (geographic_scope IN
                     ('international','country','region','state','municipality','mixed')),
  methodology     text CHECK (methodology IS NULL OR length(methodology) BETWEEN 10 AND 4000),
  license         text NOT NULL CHECK (length(license) BETWEEN 2 AND 200),
  license_url     text CHECK (license_url IS NULL OR license_url ~ '^https?://'),

  -- o arquivo de onde o número saiu
  file_name       text CHECK (file_name IS NULL OR length(file_name) <= 300),
  file_sha256     text CHECK (file_sha256 IS NULL OR file_sha256 ~ '^[0-9a-f]{64}$'),
  rows_loaded     integer CHECK (rows_loaded IS NULL OR rows_loaded >= 0),

  -- envelhecimento DECLARADO pela carga, não adivinhado pela plataforma
  stale_after_months integer CHECK (stale_after_months IS NULL OR stale_after_months BETWEEN 1 AND 600),
  stale_note      text CHECK (stale_note IS NULL OR length(stale_note) BETWEEN 10 AND 1000),

  loaded_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (key, version)
);

COMMENT ON TABLE external_datasets IS
  'Procedência de dado que a plataforma NÃO produziu. Uma linha por conjunto de dados e versão. '
  'Nenhuma linha nasce com esta migração: o catálogo começa vazio, como as tabelas que ele descreve.';
COMMENT ON COLUMN external_datasets.published_at IS
  'Data em que a FONTE publicou. Diferente de retrieved_at (data da consulta). As duas estavam '
  'colapsadas em `source_date` até a v0.20.0, e a diferença importa: um dado consultado hoje pode '
  'ter sido publicado há cinco anos.';
COMMENT ON COLUMN external_datasets.license IS
  'Sob qual licença o dado foi obtido. Sem isto, redistribuir dado de terceiro é decisão tomada por '
  'omissão. Quando a fonte não declara licença, registre "não declarada pela fonte" — que é um fato, '
  'e não o mesmo que domínio público.';
COMMENT ON COLUMN external_datasets.stale_after_months IS
  'Depois de quantos meses, contados da data de REFERÊNCIA do número, este conjunto deve ser tratado '
  'como desatualizado. É DECLARAÇÃO DE QUEM CARREGA, não regra da plataforma: um censo decenal e uma '
  'pesquisa mensal envelhecem em ritmos diferentes, e inventar um prazo único seria arbitrário. '
  'NULL = não declarado, e aí a plataforma responde "desconhecido" em vez de "atual".';

CREATE INDEX ix_external_datasets_key ON external_datasets(key, retrieved_at DESC);

ALTER TABLE external_datasets ENABLE ROW LEVEL SECURITY;
-- Leitura aberta pelo mesmo motivo de `territories`: procedência de bem comum é bem comum.
CREATE POLICY external_datasets_read ON external_datasets FOR SELECT USING (true);
CREATE POLICY external_datasets_write ON external_datasets FOR ALL
  USING (app_priv() OR app_system()) WITH CHECK (app_priv() OR app_system());
GRANT SELECT ON external_datasets TO impacto_app;
GRANT INSERT, UPDATE ON external_datasets TO impacto_app;

-- ============================================================ ligação com o dado
ALTER TABLE territory_indicators ADD COLUMN dataset_id uuid REFERENCES external_datasets(id) ON DELETE RESTRICT;
ALTER TABLE equity_denominators  ADD COLUMN dataset_id uuid REFERENCES external_datasets(id) ON DELETE RESTRICT;
ALTER TABLE territories          ADD COLUMN dataset_id uuid REFERENCES external_datasets(id) ON DELETE RESTRICT;
ALTER TABLE ods_targets          ADD COLUMN dataset_id uuid REFERENCES external_datasets(id) ON DELETE RESTRICT;

CREATE INDEX ix_territory_indicators_dataset ON territory_indicators(dataset_id) WHERE dataset_id IS NOT NULL;
CREATE INDEX ix_equity_denominators_dataset ON equity_denominators(dataset_id) WHERE dataset_id IS NOT NULL;

COMMENT ON COLUMN ods_targets.dataset_id IS
  'As metas dos ODS são dado de terceiro como qualquer outro: entram por '
  '`scripts/import_ods_targets.py`, que exige publicador, licença e data de consulta. A tabela '
  'nasceu vazia na v0.8.0 e continuou vazia porque o importador que a documentação dizia existir '
  'não existia; a v0.20.0 entrega o importador e liga a carga a esta procedência.';

COMMENT ON COLUMN territory_indicators.dataset_id IS
  'Conjunto de dados de onde o número saiu. NULO nas linhas anteriores à v0.20.0 e nas declaradas à '
  'mão: a coluna não é obrigatória de propósito, porque tornar obrigatório o que já existe sem o '
  'dado só produziria preenchimento inventado.';

-- O catálogo é imutável depois de criado: corrigir é carregar versão nova. Mesma regra do
-- denominador e do indicador territorial — e pelo mesmo motivo (o número já foi usado em análise).
CREATE FUNCTION external_dataset_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.key <> OLD.key OR NEW.version <> OLD.version OR NEW.publisher <> OLD.publisher
     OR NEW.dataset <> OLD.dataset OR NEW.license <> OLD.license
     OR NEW.retrieved_at <> OLD.retrieved_at
     OR NEW.file_sha256 IS DISTINCT FROM OLD.file_sha256 THEN
    RAISE EXCEPTION 'procedência é imutável: corrigir é registrar uma VERSÃO nova do conjunto'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_external_dataset_immutable BEFORE UPDATE ON external_datasets
  FOR EACH ROW EXECUTE FUNCTION external_dataset_immutable();

-- ============================================================ dado desatualizado
CREATE FUNCTION data_freshness(p_reference_date date, p_stale_after_months integer)
RETURNS TABLE (state text, months_old integer, note text)
LANGUAGE sql STABLE AS $$
  SELECT
    CASE
      WHEN p_reference_date IS NULL THEN 'unknown'
      WHEN p_stale_after_months IS NULL THEN 'undeclared'
      WHEN p_reference_date + make_interval(months => p_stale_after_months) < current_date THEN 'stale'
      ELSE 'current'
    END,
    CASE WHEN p_reference_date IS NULL THEN NULL
         ELSE (EXTRACT(YEAR FROM age(current_date, p_reference_date)) * 12
               + EXTRACT(MONTH FROM age(current_date, p_reference_date)))::integer END,
    CASE
      WHEN p_reference_date IS NULL THEN 'sem data de referência: não dá para dizer se envelheceu'
      WHEN p_stale_after_months IS NULL THEN
        'a carga não declarou em quantos meses este dado envelhece; a plataforma não inventa o prazo'
      WHEN p_reference_date + make_interval(months => p_stale_after_months) < current_date THEN
        'passou do prazo declarado pela própria carga: trate como desatualizado'
      ELSE 'dentro do prazo declarado pela carga'
    END
$$;
COMMENT ON FUNCTION data_freshness IS
  'Quatro estados, e `undeclared` é o que importa: quando ninguém declarou o prazo, a resposta é '
  '"não declarado" — nunca "atual". Tratar silêncio como atualidade é a forma mais discreta de um '
  'produto de evidência mentir.';

-- Visão do indicador territorial com procedência e frescura resolvidas, para a API não refazer a
-- conta em cada rota (e divergir).
CREATE FUNCTION territory_indicator_current(p_territory text)
RETURNS TABLE (code text, value numeric, unit text, reference_date date,
               source_name text, source_url text, source_date date, method_note text,
               publisher text, dataset text, dataset_version text, license text,
               published_at date, retrieved_at date, file_sha256 text,
               freshness text, months_old integer, freshness_note text)
LANGUAGE sql STABLE AS $$
  SELECT ti.code, ti.value, ti.unit, ti.reference_date,
         ti.source_name, ti.source_url, ti.source_date, ti.method_note,
         d.publisher, d.dataset, d.version, d.license,
         d.published_at, d.retrieved_at, d.file_sha256,
         f.state, f.months_old, f.note
    FROM territory_indicators ti
    LEFT JOIN external_datasets d ON d.id = ti.dataset_id
    CROSS JOIN LATERAL data_freshness(ti.reference_date, d.stale_after_months) f
   WHERE ti.territory = p_territory AND ti.effective_until IS NULL
   ORDER BY ti.code
$$;
COMMENT ON FUNCTION territory_indicator_current IS
  'Indicadores vigentes de um território, com procedência e frescura. Indicador sem conjunto de dados '
  'ligado devolve `undeclared` — e isso é informação, não erro.';
