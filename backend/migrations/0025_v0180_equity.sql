-- 0025_v0180_equity.sql — CONTEXTO DE EQUIDADE, DENOMINADOR COM FONTE E NORMALIZAÇÃO ROTULADA
--
-- A FRASE QUE ESTA MIGRAÇÃO IMPLEMENTA
--
-- "Impacto não é quantidade. Impacto é resultado contextualizado." 50 pessoas atendidas numa
-- comunidade remota não são automaticamente menos impacto que 5.000 num centro urbano.
--
-- A DECISÃO MAIS IMPORTANTE, E É UMA RECUSA
--
-- Os documentos desta rodada propõem `IMPACTO = RESULTADO × CONTEXTO × NECESSIDADE × EQUIDADE ×
-- ADICIONALIDADE × EVIDÊNCIA × SUSTENTABILIDADE` — e eles próprios mandam não implementar a fórmula
-- literalmente. Esta migração não a implementa, e o motivo é concreto: **multiplicar sete fatores
-- estimados produz um número com aparência de precisão e sem significado**, e esconde quem escolheu
-- os pesos.
--
-- O que entra no lugar: contexto **declarado com fonte** e normalização **rotulada**. E a trava que
-- faz a diferença entre medir e inventar:
--
--   SEM DENOMINADOR DECLARADO COM FONTE, NÃO EXISTE NÚMERO NORMALIZADO.
--
-- É a mesma disciplina das linhas de base do Value Ledger (0019), que nascem sem número: "atendemos
-- 12% da população elegível" só pode ser dito por quem declarou qual é a população elegível, de que
-- fonte e de que data. Sem isso, a resposta é "indisponível", com o motivo — nunca uma estimativa.
--
-- O QUE ESTA MIGRAÇÃO NÃO FAZ, DE PROPÓSITO
--
-- Não cria nota de equidade, não ranqueia projeto, não ranqueia território e **não classifica
-- pessoa**. A v0.16.0 já havia decidido que vulnerabilidade é atributo do PROJETO e do TERRITÓRIO,
-- nunca da pessoa ("esta pessoa é mulher e pertence a grupo vulnerável" é dado pessoal sensível), e
-- esta migração respeita isso: barreira é declarada sobre o CONTEXTO em que o projeto opera.

-- ============================================================================ 1. catálogo de barreiras
-- Lista EDITORIAL da plataforma, como a de `social_determinants` (0012). A redação é nossa, o
-- agrupamento é nosso, e isso está declarado em `source_note` de cada linha — não é classificação
-- oficial de nenhum órgão. Quem usa precisa saber disso.
CREATE TABLE equity_barrier_catalog (
  code        text PRIMARY KEY CHECK (code ~ '^[a-z_]{3,40}$'),
  name_pt     text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 3 AND 120),
  dimension   text NOT NULL CHECK (dimension IN ('geografica','economica','cultural','linguistica',
                                                 'digital','institucional','infraestrutura',
                                                 'mobilidade','seguranca','informacional')),
  description text NOT NULL CHECK (length(btrim(description)) BETWEEN 20 AND 1000),
  source_note text NOT NULL CHECK (length(btrim(source_note)) BETWEEN 10 AND 600),
  active      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE equity_barrier_catalog IS
  'Barreiras de acesso que o projeto declara enfrentar no contexto em que opera. Lista editorial da '
  'plataforma, não classificação oficial — cada linha carrega essa ressalva em source_note.';
COMMENT ON COLUMN equity_barrier_catalog.dimension IS
  'Agrupamento para leitura, não para cálculo: não há peso por dimensão.';

INSERT INTO equity_barrier_catalog(code, name_pt, dimension, description, source_note) VALUES
  ('distancia_servico', 'Distância até o serviço', 'geografica',
   'O público precisa percorrer distância relevante para alcançar o serviço, equipamento público ou '
   'ponto de atendimento mais próximo.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('transporte_ausente', 'Transporte público ausente ou irregular', 'mobilidade',
   'Não há transporte público regular até o local da atividade, ou o custo e o horário dele impedem '
   'a participação de parte do público.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('custo_participacao', 'Custo de participação', 'economica',
   'Participar implica custo direto ou indireto (passagem, alimentação, perda de jornada) que parte '
   'do público não tem como absorver.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('conectividade', 'Conectividade insuficiente', 'digital',
   'A conexão disponível no território não sustenta a atividade pretendida, ou parte do público não '
   'tem acesso a dispositivo adequado.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('letramento_digital', 'Letramento digital', 'digital',
   'Parte do público não tem familiaridade com as ferramentas digitais exigidas pela atividade ou '
   'pelo processo de inscrição.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('lingua', 'Língua e tradução', 'linguistica',
   'O público usa língua, variedade linguística ou língua de sinais diferente da do material e do '
   'atendimento, exigindo tradução ou mediação.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('especificidade_cultural', 'Especificidade cultural do território', 'cultural',
   'A atividade exige adequação ao modo de vida, calendário, organização social ou protocolo de '
   'consulta da comunidade atendida.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('infraestrutura_local', 'Infraestrutura local insuficiente', 'infraestrutura',
   'Falta no território a infraestrutura necessária à atividade: espaço, energia estável, água, '
   'saneamento ou equipamento.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('documentacao_publico', 'Documentação do público', 'institucional',
   'Parte do público não possui a documentação exigida para acessar o serviço ou o benefício a que '
   'o projeto se conecta.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('capacidade_executora', 'Capacidade da equipe executora', 'institucional',
   'A organização executa com equipe reduzida, acumulando funções, o que limita escala sem que isso '
   'reflita qualidade de execução.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('seguranca_territorio', 'Condições de segurança no território', 'seguranca',
   'As condições de segurança do território limitam horário, deslocamento ou permanência da equipe '
   'e do público.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.'),
  ('informacao_oportunidade', 'Acesso à informação sobre a oportunidade', 'informacional',
   'O público elegível não é alcançado pelos canais usuais de divulgação, exigindo busca ativa.',
   'Redação da plataforma. Precisa de revisão técnica; não é classificação oficial.');

-- ============================================================================ 2. barreira por projeto
-- Escada de prova idêntica em espírito à de `impact_edges` (0004) e a `alignment_level` (0004):
-- declarada → documentada → evidenciada. E o banco cobra a diferença.
CREATE TABLE project_barriers (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  barrier_code  text NOT NULL REFERENCES equity_barrier_catalog(code) ON DELETE RESTRICT,
  standing      text NOT NULL DEFAULT 'declared'
                  CHECK (standing IN ('declared','documented','evidenced')),
  note          text NOT NULL CHECK (length(btrim(note)) BETWEEN 10 AND 2000),
  source_name   text CHECK (source_name IS NULL OR length(btrim(source_name)) BETWEEN 3 AND 300),
  source_url    text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  source_date   date,
  evidence_id   uuid REFERENCES evidences(id) ON DELETE SET NULL,
  document_id   uuid REFERENCES documents(id) ON DELETE SET NULL,
  declared_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (project_id, barrier_code),
  -- "Documentada" exige documento no cofre OU fonte citada com data. Sem isso é declaração.
  CONSTRAINT barrier_documented_needs_basis CHECK (
    standing <> 'documented'
    OR document_id IS NOT NULL
    OR (source_name IS NOT NULL AND source_date IS NOT NULL)),
  -- "Evidenciada" exige evidência registrada. É o degrau que não se alcança escrevendo melhor.
  CONSTRAINT barrier_evidenced_needs_evidence CHECK (
    standing <> 'evidenced' OR evidence_id IS NOT NULL)
);
COMMENT ON TABLE project_barriers IS
  'Barreira que o projeto declara enfrentar, com a escada de prova declarada → documentada → '
  'evidenciada. Barreira é atributo do CONTEXTO do projeto, nunca da pessoa atendida (ADR-171).';
CREATE INDEX ix_project_barriers_project ON project_barriers(project_id);
CREATE INDEX ix_project_barriers_org ON project_barriers(org_id);
CREATE INDEX ix_project_barriers_code ON project_barriers(barrier_code);
CREATE INDEX ix_project_barriers_evidence ON project_barriers(evidence_id) WHERE evidence_id IS NOT NULL;
CREATE INDEX ix_project_barriers_document ON project_barriers(document_id) WHERE document_id IS NOT NULL;

CREATE TRIGGER trg_project_barriers_touch BEFORE UPDATE ON project_barriers
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
-- `project_id` e `org_id` não mudam: barreira pertence ao projeto em que foi declarada.
CREATE TRIGGER trg_project_barriers_guard BEFORE UPDATE ON project_barriers
  FOR EACH ROW EXECUTE FUNCTION guard_columns('project_id', 'org_id');

-- ============================================================================ 3. denominador
-- A trava central desta migração. Toda normalização precisa de um denominador, e todo denominador
-- precisa de FONTE, DATA e MÉTODO. Versionado: população muda, e o número de ontem continua
-- explicando o cálculo de ontem.
CREATE TABLE equity_denominators (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scope          text NOT NULL CHECK (scope IN ('project','program','territory')),
  project_id     uuid REFERENCES projects(id) ON DELETE CASCADE,
  program_id     uuid REFERENCES programs(id) ON DELETE CASCADE,
  territory      text CHECK (territory IS NULL
                             OR territory ~ '^(INT|[A-Z]{2}(-[A-Z]{2}(-[0-9]{7})?)?)$'),
  org_id         uuid REFERENCES organizations(id) ON DELETE CASCADE,
  kind           text NOT NULL CHECK (kind IN ('eligible_population','reference_population',
                                               'households','enrolled','area_km2','service_units',
                                               'resource_cents')),
  value          numeric(18,4) NOT NULL CHECK (value > 0),
  unit           text NOT NULL CHECK (length(btrim(unit)) BETWEEN 1 AND 40),
  reference_date date NOT NULL,
  source_name    text NOT NULL CHECK (length(btrim(source_name)) BETWEEN 3 AND 300),
  source_url     text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  source_date    date NOT NULL,
  method_note    text NOT NULL CHECK (length(btrim(method_note)) BETWEEN 10 AND 2000),
  effective_from timestamptz NOT NULL DEFAULT now(),
  effective_until timestamptz,
  created_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT denominator_scope CHECK (
    (scope = 'project'   AND project_id IS NOT NULL AND program_id IS NULL)
    OR (scope = 'program' AND program_id IS NOT NULL AND project_id IS NULL)
    OR (scope = 'territory' AND territory IS NOT NULL AND project_id IS NULL AND program_id IS NULL)),
  CONSTRAINT denominator_period CHECK (effective_until IS NULL OR effective_until > effective_from)
);
COMMENT ON TABLE equity_denominators IS
  'O denominador de cada normalização, com fonte, data de referência e método OBRIGATÓRIOS. Sem '
  'linha vigente aqui, a plataforma responde "indisponível" em vez de estimar — "atendemos 12% da '
  'população elegível" só pode ser dito por quem declarou qual população, de que fonte e de quando.';
COMMENT ON COLUMN equity_denominators.value IS
  'Imutável. Corrigir é criar versão nova, que fecha a vigência da anterior.';

CREATE UNIQUE INDEX ux_denominator_current_project ON equity_denominators(project_id, kind)
  WHERE scope = 'project' AND effective_until IS NULL;
CREATE UNIQUE INDEX ux_denominator_current_program ON equity_denominators(program_id, kind)
  WHERE scope = 'program' AND effective_until IS NULL;
CREATE UNIQUE INDEX ux_denominator_current_territory ON equity_denominators(territory, kind)
  WHERE scope = 'territory' AND effective_until IS NULL;
CREATE INDEX ix_denominator_org ON equity_denominators(org_id) WHERE org_id IS NOT NULL;

-- BEFORE INSERT, pela lição da 0019: o índice único parcial é conferido no fim do comando, ANTES de
-- os gatilhos AFTER rodarem. Com AFTER, criar versão nova era impossível.
CREATE FUNCTION close_previous_denominator() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE equity_denominators SET effective_until = NEW.effective_from
   WHERE kind = NEW.kind AND id <> NEW.id AND effective_until IS NULL
     AND scope = NEW.scope
     AND ((NEW.scope = 'project'   AND project_id = NEW.project_id)
       OR (NEW.scope = 'program'   AND program_id = NEW.program_id)
       OR (NEW.scope = 'territory' AND territory  = NEW.territory));
  RETURN NEW;
END $$;
CREATE TRIGGER trg_denominator_close BEFORE INSERT ON equity_denominators
  FOR EACH ROW EXECUTE FUNCTION close_previous_denominator();

-- Valor, fonte e data são imutáveis. `guard_columns` seria inútil em parte dos casos porque isenta
-- `app_priv()`, então a trava é um gatilho próprio — a mesma lição de `plan_price_versions`.
CREATE FUNCTION denominator_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.value IS DISTINCT FROM OLD.value
     OR NEW.kind IS DISTINCT FROM OLD.kind
     OR NEW.unit IS DISTINCT FROM OLD.unit
     OR NEW.source_name IS DISTINCT FROM OLD.source_name
     OR NEW.source_date IS DISTINCT FROM OLD.source_date
     OR NEW.reference_date IS DISTINCT FROM OLD.reference_date
     OR NEW.scope IS DISTINCT FROM OLD.scope THEN
    RAISE EXCEPTION 'denominador é imutável: corrigir é declarar versão nova, que fecha a anterior'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_denominator_immutable BEFORE UPDATE ON equity_denominators
  FOR EACH ROW EXECUTE FUNCTION denominator_immutable();

-- ============================================================================ 4. contexto do projeto
CREATE TABLE equity_contexts (
  project_id      uuid PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  -- Qual necessidade, em uma frase que alguém de fora entenda.
  need_statement  text NOT NULL CHECK (length(btrim(need_statement)) BETWEEN 20 AND 2000),
  need_source_name text CHECK (need_source_name IS NULL
                               OR length(btrim(need_source_name)) BETWEEN 3 AND 300),
  need_source_url text CHECK (need_source_url IS NULL OR need_source_url ~ '^https?://'),
  need_source_date date,
  -- Adicionalidade: o que NÃO aconteceria sem este projeto. É a pergunta que mais incomoda e a que
  -- mais separa projeto de atividade.
  additionality   text NOT NULL CHECK (length(btrim(additionality)) BETWEEN 20 AND 2000),
  counterfactual  text CHECK (counterfactual IS NULL
                              OR length(btrim(counterfactual)) BETWEEN 20 AND 2000),
  additionality_standing text NOT NULL DEFAULT 'declared'
                  CHECK (additionality_standing IN ('declared','documented','evidenced')),
  additionality_evidence_id uuid REFERENCES evidences(id) ON DELETE SET NULL,
  context_note    text CHECK (context_note IS NULL OR length(context_note) <= 4000),
  updated_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT additionality_documented_needs_counterfactual CHECK (
    additionality_standing = 'declared' OR counterfactual IS NOT NULL),
  CONSTRAINT additionality_evidenced_needs_evidence CHECK (
    additionality_standing <> 'evidenced' OR additionality_evidence_id IS NOT NULL)
);
COMMENT ON TABLE equity_contexts IS
  'O contexto declarado do projeto: qual necessidade, com que fonte, e o que não aconteceria sem '
  'ele. Adicionalidade acima de "declarada" exige o cenário-base escrito; "evidenciada" exige '
  'evidência registrada.';
CREATE INDEX ix_equity_contexts_org ON equity_contexts(org_id);
CREATE TRIGGER trg_equity_contexts_touch BEFORE UPDATE ON equity_contexts
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_equity_contexts_guard BEFORE UPDATE ON equity_contexts
  FOR EACH ROW EXECUTE FUNCTION guard_columns('project_id', 'org_id');

-- ============================================================================ 5. retrato append-only
CREATE TABLE equity_assessments (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id     uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id         uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  engine_version text NOT NULL CHECK (length(engine_version) BETWEEN 3 AND 60),
  barriers_total integer NOT NULL DEFAULT 0 CHECK (barriers_total >= 0),
  barriers_documented integer NOT NULL DEFAULT 0 CHECK (barriers_documented >= 0),
  barriers_evidenced integer NOT NULL DEFAULT 0 CHECK (barriers_evidenced >= 0),
  -- Quais normalizações FORAM possíveis. Vazio é resposta legítima e frequente.
  methods_available text[] NOT NULL DEFAULT '{}',
  normalization  jsonb NOT NULL DEFAULT '{}'::jsonb,
  declared       jsonb NOT NULL DEFAULT '{}'::jsonb,
  evidence_confidence numeric(4,3) CHECK (evidence_confidence IS NULL
                                          OR evidence_confidence BETWEEN 0 AND 1),
  confidence_band text CHECK (confidence_band IS NULL
                              OR confidence_band IN ('high','medium','low','insufficient_data')),
  detail         jsonb NOT NULL DEFAULT '{}'::jsonb,
  computed_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  computed_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT barriers_subsets CHECK (barriers_documented <= barriers_total
                                     AND barriers_evidenced <= barriers_documented)
);
COMMENT ON TABLE equity_assessments IS
  'Retrato append-only do contexto de equidade. NÃO traz nota de equidade: traz o que foi declarado, '
  'o que foi normalizado (e com qual denominador e fonte), o que não foi possível normalizar e por '
  'quê, e a confiança da evidência.';
COMMENT ON COLUMN equity_assessments.normalization IS
  'Por método: {value, unit, denominator_kind, denominator_value, source_name, source_date} quando '
  'possível, ou {unavailable: true, reason} quando falta denominador com fonte.';
CREATE INDEX ix_equity_assessments_project ON equity_assessments(project_id, computed_at DESC);
CREATE INDEX ix_equity_assessments_org ON equity_assessments(org_id, computed_at DESC);
CREATE TRIGGER trg_equity_assessments_append BEFORE UPDATE OR DELETE ON equity_assessments
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ============================================================================ 6. a correção da 0017
-- `program_indicators` exige fonte na linha de base desde a v0.17.0; `project_indicators`, não. Era
-- inconsistência minha. A trava entra como GATILHO, não como CHECK, de propósito: CHECK recusaria a
-- própria migração em banco que já tem linha de base antiga sem fonte, e apagar ou inventar a fonte
-- dessas linhas seria pior. Assim, linha antiga continua legível e QUALQUER escrita nova obedece.
ALTER TABLE project_indicators
  ADD COLUMN baseline_source text CHECK (baseline_source IS NULL
                                         OR length(btrim(baseline_source)) BETWEEN 3 AND 300),
  ADD COLUMN baseline_date date;
COMMENT ON COLUMN project_indicators.baseline_source IS
  'Fonte da linha de base. Obrigatória para linha nova pelo gatilho; linhas anteriores à v0.18.0 '
  'ficam listadas na view project_baselines_without_source.';

CREATE FUNCTION project_indicator_baseline_source() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.baseline IS NOT NULL AND NEW.baseline_source IS NULL THEN
    RAISE EXCEPTION 'linha de base exige fonte: número de partida sem fonte é número inventado, e o '
                    'projeto inteiro passa a medir contra ele' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_project_indicator_baseline BEFORE INSERT OR UPDATE ON project_indicators
  FOR EACH ROW EXECUTE FUNCTION project_indicator_baseline_source();

CREATE VIEW project_baselines_without_source AS
  SELECT pi.id, pi.project_id, pi.org_id, pi.indicator_id, pi.baseline, pi.created_at
    FROM project_indicators pi
   WHERE pi.baseline IS NOT NULL AND pi.baseline_source IS NULL;
COMMENT ON VIEW project_baselines_without_source IS
  'Linhas de base anteriores à regra da v0.18.0. Existe para que a dívida seja CONTÁVEL em vez de '
  'silenciosa: ninguém descobre por acidente que metade das metas mede contra número sem fonte.';

-- ============================================================================ 7. RLS
ALTER TABLE equity_barrier_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE project_barriers ENABLE ROW LEVEL SECURITY;
ALTER TABLE equity_denominators ENABLE ROW LEVEL SECURITY;
ALTER TABLE equity_contexts ENABLE ROW LEVEL SECURITY;
ALTER TABLE equity_assessments ENABLE ROW LEVEL SECURITY;

-- O catálogo é público para quem tem conta: quem vê uma barreira declarada tem direito de ler a
-- definição dela e a ressalva de que a lista é editorial.
CREATE POLICY barrier_catalog_read ON equity_barrier_catalog FOR SELECT
  USING (app_authenticated() OR app_priv());

-- Barreira, contexto e retrato seguem o acesso do PROJETO: a dona, quem apoia e quem é parte. É o
-- mesmo desenho de `evidences` (0001), e por isso usa as mesmas funções.
CREATE POLICY project_barriers_read ON project_barriers FOR SELECT
  USING (org_id = app_org() OR app_project_investor(project_id) OR app_project_party(project_id)
         OR app_priv());
CREATE POLICY project_barriers_write ON project_barriers FOR INSERT
  WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY project_barriers_update ON project_barriers FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY project_barriers_delete ON project_barriers FOR DELETE
  USING (org_id = app_org() OR app_priv());

CREATE POLICY equity_contexts_read ON equity_contexts FOR SELECT
  USING (org_id = app_org() OR app_project_investor(project_id) OR app_project_party(project_id)
         OR app_priv());
CREATE POLICY equity_contexts_write ON equity_contexts FOR INSERT
  WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY equity_contexts_update ON equity_contexts FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY equity_assessments_read ON equity_assessments FOR SELECT
  USING (org_id = app_org() OR app_project_investor(project_id) OR app_project_party(project_id)
         OR app_priv());
CREATE POLICY equity_assessments_write ON equity_assessments FOR INSERT
  WITH CHECK (org_id = app_org() OR app_priv() OR app_system());

-- Denominador de TERRITÓRIO é bem comum: quem tem conta lê, porque comparação territorial sem o
-- denominador visível é número sem régua. Denominador de projeto e de programa segue o dono.
CREATE POLICY denominators_read ON equity_denominators FOR SELECT
  USING (scope = 'territory'
         OR org_id = app_org()
         OR (project_id IS NOT NULL AND (app_project_investor(project_id)
                                         OR app_project_party(project_id)))
         OR app_priv());
CREATE POLICY denominators_write ON equity_denominators FOR INSERT
  WITH CHECK ((scope = 'territory' AND app_priv())
              OR (scope <> 'territory' AND (org_id = app_org() OR app_priv())));
CREATE POLICY denominators_update ON equity_denominators FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

GRANT SELECT ON equity_barrier_catalog TO impacto_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON project_barriers TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON equity_denominators TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON equity_contexts TO impacto_app;
GRANT SELECT, INSERT ON equity_assessments TO impacto_app;
GRANT SELECT ON project_baselines_without_source TO impacto_app;
REVOKE UPDATE, DELETE ON equity_assessments FROM impacto_app;
