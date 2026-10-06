-- 0019_v0170_value_ledger.sql — VALUE LEDGER E CUSTO DE IA
--
-- BILLING ≠ VALUE. Esta é a distinção que a migração implementa, e ela vem textualmente dos
-- documentos desta rodada: "Billing registra cobrança. Value Ledger registra valor criado."
--
-- O produto já media USO (`ai_usage`, limites de plano) e cobrava ACESSO (assinatura por organização).
-- O que não existia em lugar nenhum era o registro de **quanto trabalho o sistema evitou** — e sem
-- isso não há ROI demonstrável, o que deixa a venda institucional sem lastro.
--
-- A DECISÃO MAIS IMPORTANTE DESTA MIGRAÇÃO
--
-- Os documentos dão o exemplo "42 minutos estimados de trabalho automatizado" e "72h estimadas de
-- trabalho operacional evitadas". Números assim são exatamente o que a regra permanente deste projeto
-- proíbe: não inventar, PROVAR.
--
-- Então o Value Ledger separa duas coisas que são tentadoras de misturar:
--
--   * **CONTAGEM** — quantos documentos foram conferidos, quantas inconsistências foram achadas,
--     quantos projetos foram triados. Isso é MEDIDO: o sistema fez e contou.
--   * **ESTIMATIVA DE TEMPO** — quanto trabalho humano aquilo teria custado. Isso **não** é medido por
--     nós, e não é digitável. Vem de `value_baselines`, uma tabela versionada em que cada linha
--     declara a fonte do número e a data em que foi conferida.
--
-- E a consequência prática, de propósito: **as linhas de referência nascem sem valor.**
-- `minutes_per_unit` é nulo até alguém declarar o número COM fonte. Até então o Value Ledger registra
-- as contagens (que são verdade) e devolve `minutes_saved_estimate = NULL` com
-- `estimate_status = 'no_baseline'`. Um painel que mostrasse "72h economizadas" baseado em número que
-- ninguém conferiu destruiria a credibilidade de todo o resto.

-- ============================================================================ 1. tipos de evento
-- Lista fechada e declarada: cada tipo diz O QUE conta como unidade. Sem isso, "unidades" viraria um
-- número sem significado, somável com qualquer outro.
CREATE TABLE value_event_types (
  key          text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_.]{2,60}$'),
  label_pt     text NOT NULL,
  unit_label   text NOT NULL,
  what_counts  text NOT NULL,
  active       boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN value_event_types.what_counts IS
  'Descreve em português o que é uma unidade deste evento. Serve de contrato: quem lê o Value Ledger '
  'sabe o que o número significa, e quem implementa um motor novo sabe o que deve contar.';

INSERT INTO value_event_types(key, label_pt, unit_label, what_counts) VALUES
  ('readiness.evaluated', 'Prontidão avaliada', 'verificação',
   'Cada verificação das 6 dimensões de prontidão executada contra o estado real do projeto.'),
  ('readiness.gap_found', 'Lacuna de prontidão encontrada', 'lacuna',
   'Cada item que faltava e foi apontado com o que fazer — documento ausente, indicador sem valor.'),
  ('match.run_completed', 'Avaliação de compatibilidade concluída', 'par avaliado',
   'Cada par projeto-oportunidade pontuado com explicação, versões de motor e faixa de confiança.'),
  ('document.assembled', 'Documento montado', 'documento',
   'Cada documento gerado a partir de modelo publicado, com campos derivados do domínio.'),
  ('document.blocked_incomplete', 'Geração recusada por incompletude', 'recusa',
   'Cada vez que a plataforma recusou gerar documento incompleto E disse o que faltava.'),
  ('diagnosis.version_published', 'Versão de diagnóstico congelada', 'versão',
   'Cada versão imutável de diagnóstico, com o que mudou calculado pelo servidor.'),
  ('risk.scan_completed', 'Varredura de risco concluída', 'regra aplicada',
   'Cada regra publicada de risco avaliada contra o projeto na varredura.'),
  ('program.projects_screened', 'Projetos triados no programa', 'projeto',
   'Cada projeto do programa classificado por papel, elegibilidade e situação.'),
  ('impact_report.accepted', 'Relatório de impacto aceito', 'relatório',
   'Cada relatório cujos números foram colhidos pelo banco e aceitos por quem apoia.'),
  ('territorial_gap.computed', 'Lacuna territorial calculada', 'território',
   'Cada território em que demanda registrada foi cruzada com oferta de projeto e de programa.'),
  ('ai.analysis_completed', 'Análise por IA concluída', 'análise',
   'Cada análise assistida por IA entregue com rascunho sujeito a revisão humana.');

-- ============================================================================ 2. linha de referência
-- Versionada, imutável, com FONTE obrigatória quando há número. Mesma disciplina de `fee_tables`
-- (honorário sem fonte não publica) e de `plan_price_versions` (preço vigente não se reescreve).
CREATE TABLE value_baselines (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  event_type      text NOT NULL REFERENCES value_event_types(key) ON DELETE RESTRICT,
  -- Minutos de trabalho humano que UMA unidade deste evento substitui. NULO é o estado inicial e
  -- legítimo: significa "ninguém declarou com fonte", e o ledger então não estima nada.
  minutes_per_unit numeric(10,2) CHECK (minutes_per_unit IS NULL OR minutes_per_unit > 0),
  source_name     text CHECK (length(source_name) BETWEEN 3 AND 300),
  source_url      text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  source_date     date,
  method_note     text CHECK (length(method_note) <= 2000),
  effective_from  timestamptz NOT NULL DEFAULT now(),
  effective_until timestamptz,
  created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  -- Número sem fonte e sem data é número inventado. O banco recusa.
  CONSTRAINT baseline_needs_source CHECK (
    minutes_per_unit IS NULL
    OR (source_name IS NOT NULL AND source_date IS NOT NULL AND method_note IS NOT NULL)),
  CONSTRAINT baseline_period CHECK (effective_until IS NULL OR effective_until > effective_from)
);
COMMENT ON TABLE value_baselines IS
  'Quanto trabalho humano uma unidade de evento substitui. Versionada e imutável: mudar o número cria '
  'linha nova e fecha a vigência da anterior. `minutes_per_unit` nulo é o estado de fábrica — nenhuma '
  'estimativa é produzida até alguém declarar o número COM fonte, data e método.';
-- No máximo UMA linha vigente por tipo de evento. Duas vigentes ao mesmo tempo é impossível.
CREATE UNIQUE INDEX ux_baseline_current ON value_baselines(event_type)
  WHERE effective_until IS NULL;

-- Linha de fábrica para cada tipo: existe, está vigente, e NÃO tem número.
INSERT INTO value_baselines(event_type, method_note)
  SELECT key, 'Linha de referência não definida. Nenhuma estimativa de tempo é produzida enquanto '
              'não houver número declarado com fonte, data e método.'
    FROM value_event_types;

-- ============================================================================ 3. o ledger
CREATE TABLE value_events (
  id            bigserial PRIMARY KEY,
  event_type    text NOT NULL REFERENCES value_event_types(key) ON DELETE RESTRICT,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  project_id    uuid REFERENCES projects(id) ON DELETE SET NULL,
  program_id    uuid REFERENCES programs(id) ON DELETE SET NULL,
  subject_type  text CHECK (subject_type IS NULL OR subject_type ~ '^[a-z_]{2,40}$'),
  subject_id    uuid,
  -- MEDIDO: quantas unidades o sistema efetivamente processou.
  units         integer NOT NULL CHECK (units >= 0),
  -- MEDIDO: o detalhe do que foi feito (inconsistências achadas, documentos faltantes, dimensões
  -- avaliadas). Contagens, não opiniões.
  metrics       jsonb NOT NULL DEFAULT '{}'::jsonb,
  -- DERIVADO do baseline vigente. Nulo quando não há número declarado — e aí `estimate_status` diz
  -- por quê, em vez de a interface mostrar zero e parecer que não houve valor.
  minutes_saved_estimate numeric(12,2),
  estimate_status text NOT NULL DEFAULT 'no_baseline'
                  CHECK (estimate_status IN ('no_baseline','estimated')),
  baseline_id   uuid REFERENCES value_baselines(id) ON DELETE SET NULL,
  engine_version text CHECK (length(engine_version) <= 60),
  created_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE value_events IS
  'Valor operacional criado pelo sistema. Append-only. NÃO é cobrança: billable_events (0020) é quem '
  'decide se um destes é faturável, e só depois de regra ativa e juridicamente validada.';
COMMENT ON COLUMN value_events.minutes_saved_estimate IS
  'ESTIMATIVA derivada de value_baselines, nunca digitada. Nula quando não há linha de referência com '
  'fonte declarada — e `estimate_status` carrega o motivo.';

CREATE INDEX ix_value_events_org ON value_events(org_id, created_at DESC);
CREATE INDEX ix_value_events_type ON value_events(event_type, created_at DESC);
CREATE INDEX ix_value_events_program ON value_events(program_id) WHERE program_id IS NOT NULL;
CREATE INDEX ix_value_events_project ON value_events(project_id) WHERE project_id IS NOT NULL;

-- ============================================================================ 4. tabela de preço de IA
-- Custo de IA por chamada. A auditoria encontrou `ai_usage` registrando tokens e NÃO registrando
-- custo: sem custo não existe margem por evento de valor, que é o cálculo central do prompt mestre.
--
-- Mesma disciplina do baseline: o preço vem de tabela versionada com FONTE, e nasce sem número. Nenhum
-- preço de provedor foi inventado aqui.
CREATE TABLE ai_price_table (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider        text NOT NULL CHECK (length(provider) BETWEEN 2 AND 40),
  model           text NOT NULL CHECK (length(model) BETWEEN 1 AND 80),
  -- Preço por milhão de tokens, que é a unidade em que os provedores publicam.
  input_per_mtok_cents  numeric(12,4) CHECK (input_per_mtok_cents IS NULL OR input_per_mtok_cents >= 0),
  output_per_mtok_cents numeric(12,4) CHECK (output_per_mtok_cents IS NULL OR output_per_mtok_cents >= 0),
  currency        char(3) NOT NULL DEFAULT 'USD' CHECK (currency ~ '^[A-Z]{3}$'),
  source_name     text CHECK (length(source_name) BETWEEN 3 AND 300),
  source_url      text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  source_date     date,
  effective_from  timestamptz NOT NULL DEFAULT now(),
  effective_until timestamptz,
  created_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ai_price_needs_source CHECK (
    (input_per_mtok_cents IS NULL AND output_per_mtok_cents IS NULL)
    OR (source_name IS NOT NULL AND source_date IS NOT NULL)),
  CONSTRAINT ai_price_period CHECK (effective_until IS NULL OR effective_until > effective_from)
);
COMMENT ON TABLE ai_price_table IS
  'Preço por milhão de tokens, por provedor e modelo, versionado e com fonte. Nasce VAZIO: nenhum '
  'preço de provedor foi inventado. Sem linha vigente, o custo estimado de uma chamada é nulo e a '
  'resposta diz que não há tabela de preço.';
CREATE UNIQUE INDEX ux_ai_price_current ON ai_price_table(provider, model)
  WHERE effective_until IS NULL;

-- `ai_usage` ganha o custo DERIVADO. Não é coluna que o cliente escreve.
ALTER TABLE ai_usage
  ADD COLUMN cost_cents_estimate numeric(12,6),
  ADD COLUMN cost_currency char(3),
  ADD COLUMN price_id uuid REFERENCES ai_price_table(id) ON DELETE SET NULL,
  ADD COLUMN cost_status text NOT NULL DEFAULT 'no_price_table'
      CHECK (cost_status IN ('no_price_table','estimated'));
COMMENT ON COLUMN ai_usage.cost_cents_estimate IS
  'ESTIMATIVA derivada de ai_price_table pelos tokens registrados. Nula quando não há linha vigente '
  'para o provedor e o modelo — e `cost_status` carrega o motivo.';

-- ============================================================================ 5. as funções que derivam
-- Registrar um evento de valor é chamada de FUNÇÃO, não INSERT. A razão é a mesma de
-- `app_record_event()` da v0.16.0: se a aplicação pudesse inserir direto, poderia escrever a
-- estimativa de tempo à mão — que é precisamente o que não se quer poder fazer.
CREATE FUNCTION app_record_value(
    p_event_type text, p_org uuid, p_units integer, p_metrics jsonb DEFAULT '{}'::jsonb,
    p_project uuid DEFAULT NULL, p_program uuid DEFAULT NULL,
    p_subject_type text DEFAULT NULL, p_subject_id uuid DEFAULT NULL,
    p_engine_version text DEFAULT NULL)
  RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_base record; v_minutes numeric; v_status text; v_id bigint;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM value_event_types WHERE key = p_event_type AND active) THEN
    RAISE EXCEPTION 'tipo de evento de valor desconhecido: %', p_event_type USING ERRCODE = '23514';
  END IF;
  SELECT id, minutes_per_unit INTO v_base FROM value_baselines
   WHERE event_type = p_event_type AND effective_until IS NULL;
  IF v_base.minutes_per_unit IS NULL THEN
    v_minutes := NULL; v_status := 'no_baseline';
  ELSE
    v_minutes := round(v_base.minutes_per_unit * p_units, 2); v_status := 'estimated';
  END IF;
  INSERT INTO value_events(event_type, org_id, actor_user_id, project_id, program_id, subject_type,
                           subject_id, units, metrics, minutes_saved_estimate, estimate_status,
                           baseline_id, engine_version)
  VALUES (p_event_type, p_org, app_uid(), p_project, p_program, p_subject_type, p_subject_id,
          greatest(p_units, 0), coalesce(p_metrics, '{}'::jsonb), v_minutes, v_status,
          v_base.id, p_engine_version)
  RETURNING id INTO v_id;
  RETURN v_id;
END $$;
COMMENT ON FUNCTION app_record_value IS
  'Única porta de entrada do Value Ledger. SECURITY DEFINER para que a estimativa de tempo seja '
  'SEMPRE derivada do baseline vigente e nunca possa ser passada como parâmetro.';

-- Custo de uma chamada de IA, derivado dos tokens e da tabela de preço vigente.
CREATE FUNCTION app_price_ai_usage(p_usage bigint) RETURNS numeric
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_u record; v_p record; v_cost numeric;
BEGIN
  SELECT provider, model, tokens_in, tokens_out INTO v_u FROM ai_usage WHERE id = p_usage;
  IF v_u IS NULL THEN RETURN NULL; END IF;
  SELECT id, input_per_mtok_cents, output_per_mtok_cents, currency INTO v_p
    FROM ai_price_table
   WHERE provider = v_u.provider AND model = v_u.model AND effective_until IS NULL;
  IF v_p IS NULL OR v_p.input_per_mtok_cents IS NULL THEN
    UPDATE ai_usage SET cost_status = 'no_price_table', cost_cents_estimate = NULL,
                        cost_currency = NULL, price_id = NULL
     WHERE id = p_usage;
    RETURN NULL;
  END IF;
  v_cost := (coalesce(v_u.tokens_in, 0)::numeric / 1000000) * v_p.input_per_mtok_cents
          + (coalesce(v_u.tokens_out, 0)::numeric / 1000000) * coalesce(v_p.output_per_mtok_cents, 0);
  UPDATE ai_usage SET cost_cents_estimate = round(v_cost, 6), cost_currency = v_p.currency,
                      price_id = v_p.id, cost_status = 'estimated'
   WHERE id = p_usage;
  RETURN round(v_cost, 6);
END $$;
COMMENT ON FUNCTION app_price_ai_usage IS
  'Preifica uma chamada de IA já registrada, a partir dos tokens e da tabela de preço vigente. Sem '
  'linha vigente, grava cost_status = no_price_table e devolve nulo — nunca zero, porque zero pareceria '
  'custo apurado.';

-- Fecha a vigência da linha anterior ao criar uma nova. Histórico não se reescreve.
--
-- **BEFORE INSERT, não AFTER.** A primeira versão usava AFTER e tornava impossível criar versão nova:
-- o índice único parcial `ux_baseline_current` é conferido no fim do comando, ANTES de os gatilhos
-- AFTER rodarem, então a inserção batia em "duplicate key" e o fechamento da vigência anterior nunca
-- acontecia. Com BEFORE, a linha antiga já está fechada quando o índice é conferido.
CREATE FUNCTION close_previous_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'value_baselines' THEN
    UPDATE value_baselines SET effective_until = NEW.effective_from
     WHERE event_type = NEW.event_type AND id <> NEW.id AND effective_until IS NULL;
  ELSE
    UPDATE ai_price_table SET effective_until = NEW.effective_from
     WHERE provider = NEW.provider AND model = NEW.model AND id <> NEW.id AND effective_until IS NULL;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_baseline_close BEFORE INSERT ON value_baselines
  FOR EACH ROW EXECUTE FUNCTION close_previous_version();
CREATE TRIGGER trg_ai_price_close BEFORE INSERT ON ai_price_table
  FOR EACH ROW EXECUTE FUNCTION close_previous_version();

-- Linha de referência e preço são IMUTÁVEIS: corrigir é criar versão nova.
-- (`guard_columns` seria inútil aqui, porque isenta `app_priv()`, que é o único contexto que escreve
-- estas tabelas — a mesma lição que `plan_price_versions` ensinou na v0.16.0.)
CREATE FUNCTION version_row_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_TABLE_NAME = 'value_baselines' THEN
    IF NEW.minutes_per_unit IS DISTINCT FROM OLD.minutes_per_unit
       OR NEW.source_name IS DISTINCT FROM OLD.source_name
       OR NEW.source_date IS DISTINCT FROM OLD.source_date
       OR NEW.event_type IS DISTINCT FROM OLD.event_type THEN
      RAISE EXCEPTION 'linha de referência de valor é imutável: crie uma versão nova'
        USING ERRCODE = '42501';
    END IF;
  ELSE
    IF NEW.input_per_mtok_cents IS DISTINCT FROM OLD.input_per_mtok_cents
       OR NEW.output_per_mtok_cents IS DISTINCT FROM OLD.output_per_mtok_cents
       OR NEW.currency IS DISTINCT FROM OLD.currency
       OR NEW.provider IS DISTINCT FROM OLD.provider OR NEW.model IS DISTINCT FROM OLD.model THEN
      RAISE EXCEPTION 'preço de IA é imutável: crie uma versão nova' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_baseline_immutable BEFORE UPDATE ON value_baselines
  FOR EACH ROW EXECUTE FUNCTION version_row_immutable();
CREATE TRIGGER trg_ai_price_immutable BEFORE UPDATE ON ai_price_table
  FOR EACH ROW EXECUTE FUNCTION version_row_immutable();

-- O ledger é append-only pela aplicação.
CREATE TRIGGER trg_value_events_append BEFORE UPDATE OR DELETE ON value_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ============================================================================ 6. RLS
ALTER TABLE value_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE value_baselines ENABLE ROW LEVEL SECURITY;
ALTER TABLE value_event_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_price_table ENABLE ROW LEVEL SECURITY;

-- A organização lê o próprio valor criado. Ninguém pela aplicação insere direto: a porta é
-- `app_record_value()`.
CREATE POLICY value_events_read ON value_events FOR SELECT USING (org_id = app_org() OR app_priv());

-- Vocabulário e linha de referência são públicos para quem tem conta — e é importante que sejam:
-- quem vê uma estimativa tem direito de ver de onde o número veio.
CREATE POLICY value_types_read ON value_event_types FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY value_baselines_read ON value_baselines FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY value_baselines_write ON value_baselines FOR INSERT WITH CHECK (app_priv());
CREATE POLICY value_baselines_update ON value_baselines FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());

-- Preço de IA é custo NOSSO: só a administração vê.
CREATE POLICY ai_price_read ON ai_price_table FOR SELECT USING (app_priv());
CREATE POLICY ai_price_write ON ai_price_table FOR INSERT WITH CHECK (app_priv());
CREATE POLICY ai_price_update ON ai_price_table FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());

GRANT SELECT ON value_events, value_event_types, value_baselines TO impacto_app;
GRANT INSERT, UPDATE ON value_baselines TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON ai_price_table TO impacto_app;
REVOKE INSERT, UPDATE, DELETE ON value_events FROM impacto_app;
