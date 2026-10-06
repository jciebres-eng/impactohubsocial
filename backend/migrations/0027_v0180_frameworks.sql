-- 0027_v0180_frameworks.sql — INTEROPERABILIDADE DE FRAMEWORKS E MATERIALIDADE
--
-- O QUE A RODADA PEDE, E A PARTE QUE EU RECUSO
--
-- Os documentos pedem um "tradutor universal de impacto": um mesmo indicador alimentando ODS, ESG,
-- GRI, ISSB, IRIS+, SROI, Teoria da Mudança e outros, com a escada
-- `aligned → mapped → assessed → reported → verified → audited → certified`.
--
-- Implemento a escada com SEIS degraus. **`certified` não existe neste banco.** A Plataforma não é
-- organismo certificador, e deixar o estado disponível é convidar o erro: no dia em que alguém
-- precisar de um selo para fechar uma venda, o campo estaria ali. O gatilho
-- `framework_relation_gate()` recusa a palavra com a mensagem explicando por quê.
--
-- E a segunda recusa, que é de produto: **nenhum mapeamento de indicador para GRI, ISSB, TCFD, TNFD
-- ou IRIS+ é semeado.** Não tenho a lista oficial de códigos desses referenciais neste ambiente (a
-- rede alcança só registros de pacote), e inventar código de framework de terceiro é pior que não
-- ter: alguém publicaria relatório citando um código que não existe. Então eles entram no registro
-- como `registry_only` — o produto sabe que existem, sabe que não os mapeia, e diz isso.
--
-- Importante: as minutas legais da v0.17.0 (docs/legal/B2B.md §3.5) dizem que a plataforma NÃO
-- entrega relatório pronto para CVM, GRI, SASB ou ISSB. Esta migração não contradiz aquilo — ela
-- cria a estrutura capaz de receber o mapeamento quando houver decisão de produto e de jurídico.
--
-- O QUE JÁ EXISTIA E SÓ PRECISAVA SER NOMEADO
--
-- Teoria da Mudança e Marco Lógico **já funcionam** desde a v0.8.0, com outro nome: `impact_nodes`
-- tem exatamente os sete tipos da cadeia (necessidade, atividade, produto, resultado, impacto,
-- população, contexto) e `impact_edges` tem a escada de ligação com CHECK recusando causalidade
-- validada sem evidência e sem revisor de outra organização. Os dois entram no registro como
-- `in_use`, apontando para a estrutura que os implementa.

-- ============================================================================ 1. registro
CREATE TABLE impact_frameworks (
  key          text PRIMARY KEY CHECK (key ~ '^[a-z][a-z0-9_]{2,40}$'),
  name_pt      text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 3 AND 200),
  name_en      text,
  kind         text NOT NULL CHECK (kind IN ('goal_system','reporting_standard','disclosure_standard',
                                             'evaluation_method','metric_catalog','due_diligence')),
  steward      text NOT NULL CHECK (length(btrim(steward)) BETWEEN 2 AND 200),
  what_it_is   text NOT NULL CHECK (length(btrim(what_it_is)) BETWEEN 20 AND 1000),
  -- `in_use`: a plataforma tem estrutura que o implementa, e o registro aponta para ela.
  -- `mappable`: dá para mapear indicador, mas ainda não há mapeamento.
  -- `registry_only`: existe, é reconhecido, e a plataforma NÃO o mapeia — e diz isso.
  status       text NOT NULL CHECK (status IN ('in_use','mappable','registry_only')),
  implemented_by text,
  version_label text,
  official_url text CHECK (official_url IS NULL OR official_url ~ '^https?://'),
  consulted_on date,
  -- FALSO até alguém conferir a referência contra a fonte oficial. Nasce falso em tudo.
  reference_verified boolean NOT NULL DEFAULT false,
  license_note text,
  active       boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT in_use_says_where CHECK (status <> 'in_use' OR implemented_by IS NOT NULL),
  CONSTRAINT verified_needs_source CHECK (
    NOT reference_verified OR (official_url IS NOT NULL AND consulted_on IS NOT NULL))
);
COMMENT ON TABLE impact_frameworks IS
  'Registro dos referenciais de impacto que a plataforma reconhece. `status` diz a verdade sobre cada '
  'um: in_use (há estrutura que o implementa), mappable (dá para mapear, ninguém mapeou ainda) ou '
  'registry_only (reconhecido e NÃO mapeado). Nenhuma linha nasce com reference_verified.';
COMMENT ON COLUMN impact_frameworks.reference_verified IS
  'Falso em tudo que a migração semeia: versão e URL oficiais precisam ser conferidas por alguém '
  'contra a fonte, e o CHECK exige URL e data de consulta para marcar verdadeiro.';

INSERT INTO impact_frameworks(key, name_pt, name_en, kind, steward, what_it_is, status,
                              implemented_by, license_note) VALUES
  ('ods', 'Objetivos de Desenvolvimento Sustentável', 'Sustainable Development Goals',
   'goal_system', 'Organização das Nações Unidas',
   'Os 17 objetivos e as metas associadas, usados para declarar a que agenda o projeto se conecta.',
   'in_use', 'ods_goals, ods_targets, project_ods_targets, impact_tags',
   'Nome e número dos objetivos são públicos. O EMBLEMA e a arte oficial dependem de autorização de '
   'uso de marca da ONU e não são distribuídos pela plataforma.'),
  ('esg', 'Ambiental, Social e Governança', 'Environmental, Social and Governance',
   'reporting_standard', 'Uso de mercado, sem guardião único',
   'Agrupamento em três pilares usado por investidores e empresas para organizar temas de '
   'sustentabilidade e governança.',
   'in_use', 'esg_pillars, indicator_catalog.esg_dimension, materiality_topics', NULL),
  ('theory_of_change', 'Teoria da Mudança', 'Theory of Change', 'evaluation_method',
   'Campo de avaliação, sem guardião único',
   'Cadeia explícita de necessidade → atividade → produto → resultado → impacto, com as hipóteses '
   'entre os elos declaradas em vez de implícitas.',
   'in_use',
   'impact_nodes (7 tipos) e impact_edges (6 tipos de ligação, com CHECK recusando causalidade '
   'validada sem evidência e sem revisor de outra organização)', NULL),
  ('logical_framework', 'Marco Lógico', 'Logical Framework', 'evaluation_method',
   'Uso consagrado em cooperação internacional',
   'Matriz de objetivo, resultado, indicador, meio de verificação e pressuposto.',
   'in_use',
   'impact_nodes + indicator_catalog.result_kind (output/outcome/impact) + project_indicators.method',
   NULL),
  ('sroi', 'Retorno Social sobre o Investimento', 'Social Return on Investment',
   'evaluation_method', 'Social Value International',
   'Método que atribui valor financeiro a resultados sociais para compará-los ao investimento.',
   'registry_only', NULL,
   'Exige proxies financeiros declarados e verificação por terceiro. A plataforma NÃO calcula SROI: '
   'calcular sem os proxies declarados produziria número que ninguém pode conferir.'),
  ('gri', 'Padrões GRI', 'GRI Standards', 'reporting_standard',
   'Global Reporting Initiative', 'Padrões de relato de sustentabilidade organizados por tema.',
   'registry_only', NULL,
   'A plataforma NÃO mapeia indicador para código GRI: a lista oficial de códigos não está carregada '
   'aqui, e inventar código de referencial de terceiro faria alguém publicar relatório citando '
   'código inexistente. As minutas legais da v0.17.0 excluem expressamente relatório pronto para GRI.'),
  ('issb', 'Normas ISSB / IFRS Sustentabilidade', 'ISSB / IFRS Sustainability Disclosure Standards',
   'disclosure_standard', 'International Sustainability Standards Board (IFRS Foundation)',
   'Normas de divulgação de informação de sustentabilidade orientadas a investidores.',
   'registry_only', NULL,
   'Mesma razão do GRI. As minutas legais da v0.17.0 excluem relatório pronto para ISSB.'),
  ('tcfd', 'Recomendações TCFD', 'Task Force on Climate-related Financial Disclosures',
   'disclosure_standard', 'Criada pelo Financial Stability Board',
   'Estrutura de divulgação de risco e oportunidade relacionados ao clima, em quatro pilares.',
   'registry_only', NULL,
   'A plataforma não coleta dado climático estruturado; reconhecer o referencial não é implementá-lo.'),
  ('tnfd', 'Recomendações TNFD', 'Taskforce on Nature-related Financial Disclosures',
   'disclosure_standard', 'Taskforce on Nature-related Financial Disclosures',
   'Estrutura de divulgação de dependências, impactos, riscos e oportunidades relacionados à natureza.',
   'registry_only', NULL, 'Mesma razão do TCFD.'),
  ('iris_plus', 'Catálogo IRIS+', 'IRIS+', 'metric_catalog',
   'Global Impact Investing Network (GIIN)',
   'Catálogo de métricas padronizadas para investimento de impacto.',
   'registry_only', NULL,
   'A plataforma NÃO mapeia indicador para código IRIS+ pela mesma razão do GRI: sem a lista oficial '
   'carregada, o mapeamento seria inventado.'),
  ('outcome_harvesting', 'Colheita de Resultados', 'Outcome Harvesting', 'evaluation_method',
   'Campo de avaliação', 'Método que identifica resultados observados e depois investiga a '
   'contribuição do projeto para cada um, em vez de partir de metas.',
   'mappable', NULL, NULL),
  ('contribution_analysis', 'Análise de Contribuição', 'Contribution Analysis',
   'evaluation_method', 'Campo de avaliação',
   'Método que examina em que medida o projeto contribuiu para um resultado, sem alegar causalidade '
   'exclusiva.',
   'mappable', NULL,
   'Conversa direto com os tipos de ligação de impact_edges, que já separam correlação, hipótese, '
   'associação e causalidade validada.'),
  ('cost_effectiveness', 'Análise de Custo-Efetividade', 'Cost-Effectiveness Analysis',
   'evaluation_method', 'Campo de avaliação e economia',
   'Relação entre custo e unidade de resultado alcançada, para comparar alternativas de intervenção.',
   'mappable', NULL,
   'Depende de denominador declarado com fonte (equity_denominators, kind = resource_cents).'),
  ('mcda', 'Análise de Decisão Multicritério', 'Multi-Criteria Decision Analysis',
   'evaluation_method', 'Campo de pesquisa operacional',
   'Comparação de alternativas por múltiplos critérios com pesos explícitos e declarados.',
   'mappable', NULL,
   'Os pesos têm de ser declarados e versionados para a análise ser auditável — é o mesmo princípio '
   'que fez esta rodada recusar nota de equidade por multiplicação de fatores.'),
  ('lca', 'Avaliação de Ciclo de Vida', 'Life Cycle Assessment', 'evaluation_method',
   'Normas ISO 14040/14044', 'Avaliação de impactos ambientais ao longo do ciclo de vida de um '
   'produto ou serviço.',
   'registry_only', NULL,
   'Exige inventário de ciclo de vida que a plataforma não coleta.'),
  ('carbon_accounting', 'Contabilidade de Carbono', 'Carbon Accounting', 'reporting_standard',
   'GHG Protocol e normas correlatas',
   'Contabilização de emissões por escopo, além de redução e remoção.',
   'registry_only', NULL,
   'A plataforma NÃO calcula emissão e não aceita alegação de neutralidade: sem fator de emissão '
   'declarado com fonte, o número seria inventado.'),
  ('human_rights_dd', 'Devida Diligência em Direitos Humanos', 'Human Rights Due Diligence',
   'due_diligence', 'Princípios Orientadores da ONU sobre Empresas e Direitos Humanos',
   'Processo de identificar, prevenir, mitigar e prestar contas sobre impactos em direitos humanos.',
   'mappable', NULL, NULL),
  ('circular_economy', 'Economia Circular', 'Circular Economy', 'evaluation_method',
   'Campo técnico, sem guardião único',
   'Avaliação de reuso, reciclagem e extensão de vida útil em vez de extração e descarte.',
   'mappable', NULL, NULL),
  ('dei_equity', 'Diversidade, Equidade e Inclusão', 'Diversity, Equity and Inclusion',
   'evaluation_method', 'Campo técnico, sem guardião único',
   'Leitura de acesso, representação e distribuição, no nível do projeto e do território.',
   'mappable', 'equity_contexts, project_barriers, equity_denominators',
   'A plataforma NÃO classifica pessoas: barreira e equidade são atributos do contexto do projeto e '
   'do território (ADR-171). Segmentação de indivíduo por atributo sensível não é oferecida.');

-- ============================================================================ 2. mapeamento
CREATE TABLE framework_mappings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  framework_key text NOT NULL REFERENCES impact_frameworks(key) ON DELETE RESTRICT,
  indicator_id  uuid NOT NULL REFERENCES indicator_catalog(id) ON DELETE CASCADE,
  org_id        uuid REFERENCES organizations(id) ON DELETE CASCADE,
  external_code text CHECK (external_code IS NULL
                            OR length(btrim(external_code)) BETWEEN 1 AND 60),
  external_name text CHECK (external_name IS NULL
                            OR length(btrim(external_name)) BETWEEN 3 AND 300),
  -- A escada, com SEIS degraus. `certified` não está aqui de propósito.
  relation      text NOT NULL CHECK (relation IN ('aligned','mapped','assessed','reported',
                                                  'verified','audited')),
  rationale     text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 20 AND 2000),
  source_name   text CHECK (source_name IS NULL OR length(btrim(source_name)) BETWEEN 3 AND 300),
  reviewer_org_id uuid REFERENCES organizations(id) ON DELETE SET NULL,
  reviewer_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at   timestamptz,
  declared_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  -- Quatro olhos, pela mesma lição de `impact_edges` e de `indicator_values`: quem declara não
  -- verifica. "Verificado" e "auditado" exigem revisor de OUTRA organização.
  CONSTRAINT mapping_verified_needs_other_reviewer CHECK (
    relation NOT IN ('verified','audited')
    OR (reviewer_org_id IS NOT NULL AND reviewed_at IS NOT NULL
        AND (org_id IS NULL OR reviewer_org_id <> org_id))),
  CONSTRAINT mapping_reported_needs_source CHECK (
    relation NOT IN ('reported','verified','audited') OR source_name IS NOT NULL)
);
COMMENT ON TABLE framework_mappings IS
  'Mapeamento de um indicador para um referencial. Nasce VAZIA: nenhum mapeamento para GRI, ISSB, '
  'TCFD, TNFD ou IRIS+ foi semeado, porque a lista oficial de códigos não está carregada aqui e '
  'inventar código de terceiro faria alguém publicar relatório citando código inexistente.';
COMMENT ON COLUMN framework_mappings.relation IS
  'aligned < mapped < assessed < reported < verified < audited. NÃO existe certified: a plataforma '
  'não é organismo certificador, e o gatilho framework_relation_gate() explica isso a quem tentar.';
-- UNIQUE de tabela não aceita expressão; o índice único aceita, e é ele que impede o mesmo
-- indicador ser mapeado duas vezes para o mesmo código do mesmo referencial.
CREATE UNIQUE INDEX ux_framework_mapping
  ON framework_mappings(framework_key, indicator_id, coalesce(external_code, ''));
CREATE INDEX ix_framework_mappings_framework ON framework_mappings(framework_key);
CREATE INDEX ix_framework_mappings_indicator ON framework_mappings(indicator_id);
CREATE INDEX ix_framework_mappings_org ON framework_mappings(org_id) WHERE org_id IS NOT NULL;

-- O CHECK já recusa 'certified'; este gatilho existe para que a recusa venha com a RAZÃO. "valor
-- viola restrição" não ensina nada a quem tentou.
CREATE FUNCTION framework_relation_gate() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.relation IN ('certified','certificado','certification') THEN
    RAISE EXCEPTION 'a plataforma NÃO é organismo certificador: a escada vai até "audited". '
                    'Chamar de certificado o que não é certificação é a alegação que mais rápido '
                    'destrói a credibilidade de um relatório de impacto.' USING ERRCODE = '42501';
  END IF;
  IF NEW.relation IN ('verified','audited')
     AND EXISTS (SELECT 1 FROM impact_frameworks f
                  WHERE f.key = NEW.framework_key AND f.status = 'registry_only') THEN
    RAISE EXCEPTION 'o referencial % está no registro como "registry_only": a plataforma não o '
                    'mapeia, então não há como declarar indicador verificado contra ele',
                    NEW.framework_key USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_framework_relation BEFORE INSERT OR UPDATE ON framework_mappings
  FOR EACH ROW EXECUTE FUNCTION framework_relation_gate();

-- Mapeamento é append-only no que importa: a relação e a razão não se reescrevem em silêncio.
CREATE FUNCTION framework_mapping_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.framework_key IS DISTINCT FROM OLD.framework_key
     OR NEW.indicator_id IS DISTINCT FROM OLD.indicator_id THEN
    RAISE EXCEPTION 'mapeamento não troca de referencial nem de indicador: remova e declare outro'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_framework_mapping_guard BEFORE UPDATE ON framework_mappings
  FOR EACH ROW EXECUTE FUNCTION framework_mapping_guard();

-- O que um indicador alimenta hoje. É a resposta concreta à promessa de "executar uma vez e
-- traduzir para várias linguagens" — e também a prova de quanto dessa promessa ainda não existe.
CREATE FUNCTION indicator_frameworks(p_indicator uuid)
  RETURNS TABLE (framework_key text, name_pt text, status text, relation text,
                 external_code text, source_name text, reviewed boolean)
  LANGUAGE sql STABLE AS $$
  SELECT m.framework_key, f.name_pt, f.status, m.relation, m.external_code, m.source_name,
         m.reviewed_at IS NOT NULL
    FROM framework_mappings m JOIN impact_frameworks f ON f.key = m.framework_key
   WHERE m.indicator_id = p_indicator
   ORDER BY f.name_pt
$$;

-- ============================================================================ 3. materialidade
CREATE TABLE materiality_topics (
  code        text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]{3,50}$'),
  name_pt     text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 3 AND 200),
  pillar      char(1) NOT NULL REFERENCES esg_pillars(code) ON DELETE RESTRICT,
  description text NOT NULL CHECK (length(btrim(description)) BETWEEN 20 AND 1000),
  source_note text NOT NULL,
  active      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE materiality_topics IS
  'Temas candidatos a materialidade, agrupados nos três pilares. Lista EDITORIAL da plataforma — não '
  'é a lista de temas de nenhum referencial específico, e cada linha diz isso.';

INSERT INTO materiality_topics(code, name_pt, pillar, description, source_note) VALUES
  ('emissoes', 'Emissões e energia', 'E',
   'Emissões de gases de efeito estufa, consumo e matriz de energia das atividades.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('agua', 'Água e efluentes', 'E',
   'Uso de água, qualidade e destino de efluentes nas atividades.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('residuos', 'Resíduos e circularidade', 'E',
   'Geração, destinação, reuso e reciclagem de resíduos.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('biodiversidade', 'Biodiversidade e uso do solo', 'E',
   'Efeitos sobre ecossistemas, espécies e uso do solo no território de atuação.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('clima_adaptacao', 'Adaptação e resiliência climática', 'E',
   'Capacidade de antecipar, absorver e se recuperar de eventos climáticos extremos.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('trabalho_decente', 'Trabalho decente', 'S',
   'Condições de trabalho, remuneração, jornada, saúde e segurança de quem executa.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('comunidade', 'Relação com a comunidade', 'S',
   'Consulta, participação e repartição de benefícios com a comunidade atendida.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('acesso_servico', 'Acesso ao serviço', 'S',
   'Quem consegue e quem não consegue acessar o serviço, e por quais barreiras.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('direitos_humanos', 'Direitos humanos', 'S',
   'Riscos e efeitos sobre direitos de pessoas afetadas pela atividade e pela cadeia.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('diversidade_inclusao', 'Diversidade e inclusão', 'S',
   'Representação e acesso no nível da organização e do projeto, sem classificar indivíduos.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('privacidade_dados', 'Privacidade e proteção de dados', 'G',
   'Tratamento de dado pessoal, base legal, minimização e segurança.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('integridade', 'Integridade e anticorrupção', 'G',
   'Prevenção de fraude, conflito de interesse e uso indevido de recurso.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('transparencia', 'Transparência e prestação de contas', 'G',
   'O que é publicado, com que periodicidade e com qual nível de evidência.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('governanca_conselho', 'Governança e conselho', 'G',
   'Estrutura de decisão, independência, periodicidade de reunião e registro.',
   'Tema editorial da plataforma; não é lista de referencial específico.'),
  ('cadeia_fornecimento', 'Cadeia de fornecimento', 'G',
   'Critérios de seleção, acompanhamento e risco em fornecedores e parceiros.',
   'Tema editorial da plataforma; não é lista de referencial específico.');

CREATE TABLE materiality_assessments (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  scope         text NOT NULL CHECK (scope IN ('organization','program','project')),
  program_id    uuid REFERENCES programs(id) ON DELETE CASCADE,
  project_id    uuid REFERENCES projects(id) ON DELETE CASCADE,
  period_label  text NOT NULL CHECK (length(btrim(period_label)) BETWEEN 4 AND 60),
  framework_key text REFERENCES impact_frameworks(key) ON DELETE SET NULL,
  -- Dupla materialidade só é dupla se os dois eixos forem avaliados. A coluna declara qual leitura
  -- esta avaliação faz, em vez de deixar a dúvida no ar.
  lens          text NOT NULL DEFAULT 'double'
                  CHECK (lens IN ('impact_only','financial_only','double')),
  -- Limiar declarado por quem avalia: é o que torna `is_material` derivável em vez de opinável.
  threshold     smallint NOT NULL DEFAULT 4 CHECK (threshold BETWEEN 1 AND 5),
  method_note   text NOT NULL CHECK (length(btrim(method_note)) BETWEEN 20 AND 4000),
  status        text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','superseded')),
  published_at  timestamptz,
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT materiality_scope CHECK (
    (scope = 'organization' AND program_id IS NULL AND project_id IS NULL)
    OR (scope = 'program' AND program_id IS NOT NULL AND project_id IS NULL)
    OR (scope = 'project' AND project_id IS NOT NULL AND program_id IS NULL)),
  CONSTRAINT published_has_date CHECK (status <> 'published' OR published_at IS NOT NULL)
);
COMMENT ON COLUMN materiality_assessments.threshold IS
  'Limiar de 1 a 5 declarado por quem avalia. É o que faz `is_material` ser DERIVADA do número e do '
  'limiar, em vez de marcada à mão — o mesmo princípio das datas derivadas por transição.';
CREATE INDEX ix_materiality_org ON materiality_assessments(org_id, created_at DESC);
CREATE UNIQUE INDEX ux_materiality_published_org ON materiality_assessments(org_id, scope,
  coalesce(program_id, '00000000-0000-0000-0000-000000000000'::uuid),
  coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid))
  WHERE status = 'published';
CREATE TRIGGER trg_materiality_touch BEFORE UPDATE ON materiality_assessments
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE materiality_entries (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assessment_id uuid NOT NULL REFERENCES materiality_assessments(id) ON DELETE CASCADE,
  topic_code    text NOT NULL REFERENCES materiality_topics(code) ON DELETE RESTRICT,
  -- Eixo 1: quanto a organização afeta o mundo neste tema.
  impact_score  smallint CHECK (impact_score IS NULL OR impact_score BETWEEN 1 AND 5),
  -- Eixo 2: quanto o tema afeta a organização.
  financial_score smallint CHECK (financial_score IS NULL OR financial_score BETWEEN 1 AND 5),
  rationale     text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 20 AND 2000),
  stakeholder_note text CHECK (stakeholder_note IS NULL OR length(stakeholder_note) <= 2000),
  evidence_id   uuid REFERENCES evidences(id) ON DELETE SET NULL,
  indicator_id  uuid REFERENCES indicator_catalog(id) ON DELETE SET NULL,
  -- DERIVADA por gatilho a partir dos eixos e do limiar da avaliação.
  is_material   boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (assessment_id, topic_code),
  CONSTRAINT entry_has_at_least_one_axis CHECK (impact_score IS NOT NULL
                                                OR financial_score IS NOT NULL)
);
COMMENT ON COLUMN materiality_entries.is_material IS
  'DERIVADA: verdadeira quando qualquer eixo avaliado alcança o limiar declarado na avaliação. Não é '
  'escrevível — tentar escrevê-la é sobrescrito pelo gatilho, e é por isso que a matriz não pode ser '
  'ajustada no fim para dar o resultado desejado.';

CREATE FUNCTION materiality_derive() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v record;
BEGIN
  SELECT threshold, lens, status INTO v FROM materiality_assessments WHERE id = NEW.assessment_id;
  IF v.status <> 'draft' THEN
    RAISE EXCEPTION 'avaliação de materialidade publicada não recebe tema novo: publique outra versão'
      USING ERRCODE = '42501';
  END IF;
  IF v.lens = 'impact_only' AND NEW.financial_score IS NOT NULL THEN
    RAISE EXCEPTION 'esta avaliação declarou lente "impact_only": não aceita eixo financeiro'
      USING ERRCODE = '23514';
  END IF;
  IF v.lens = 'financial_only' AND NEW.impact_score IS NOT NULL THEN
    RAISE EXCEPTION 'esta avaliação declarou lente "financial_only": não aceita eixo de impacto'
      USING ERRCODE = '23514';
  END IF;
  NEW.is_material := coalesce(NEW.impact_score, 0) >= v.threshold
                     OR coalesce(NEW.financial_score, 0) >= v.threshold;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_materiality_derive BEFORE INSERT OR UPDATE ON materiality_entries
  FOR EACH ROW EXECUTE FUNCTION materiality_derive();

-- Publicar exige tema avaliado. Matriz vazia publicada seria afirmação de que nada é material.
CREATE FUNCTION materiality_publish_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status = 'published' AND OLD.status = 'draft' THEN
    IF (SELECT count(*) FROM materiality_entries WHERE assessment_id = NEW.id) < 3 THEN
      RAISE EXCEPTION 'publicar materialidade exige ao menos três temas avaliados: matriz quase '
                      'vazia publicada afirma que nada é material' USING ERRCODE = '23514';
    END IF;
    NEW.published_at := now();
    UPDATE materiality_assessments SET status = 'superseded'
     WHERE org_id = NEW.org_id AND scope = NEW.scope AND id <> NEW.id AND status = 'published'
       AND coalesce(program_id, '00000000-0000-0000-0000-000000000000'::uuid)
           = coalesce(NEW.program_id, '00000000-0000-0000-0000-000000000000'::uuid)
       AND coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid)
           = coalesce(NEW.project_id, '00000000-0000-0000-0000-000000000000'::uuid);
  ELSIF NEW.status = 'draft' AND OLD.status <> 'draft' THEN
    RAISE EXCEPTION 'materialidade publicada não volta a rascunho' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_materiality_publish BEFORE UPDATE ON materiality_assessments
  FOR EACH ROW EXECUTE FUNCTION materiality_publish_guard();

CREATE FUNCTION materiality_matrix(p_assessment uuid)
  RETURNS TABLE (topic_code text, name_pt text, pillar char(1), impact_score smallint,
                 financial_score smallint, is_material boolean, rationale text,
                 has_evidence boolean, has_indicator boolean)
  LANGUAGE sql STABLE AS $$
  SELECT e.topic_code, t.name_pt, t.pillar, e.impact_score, e.financial_score, e.is_material,
         e.rationale, e.evidence_id IS NOT NULL, e.indicator_id IS NOT NULL
    FROM materiality_entries e JOIN materiality_topics t ON t.code = e.topic_code
   WHERE e.assessment_id = p_assessment
   ORDER BY e.is_material DESC,
            greatest(coalesce(e.impact_score,0), coalesce(e.financial_score,0)) DESC, t.name_pt
$$;

-- ============================================================================ 4. RLS
ALTER TABLE impact_frameworks ENABLE ROW LEVEL SECURITY;
ALTER TABLE framework_mappings ENABLE ROW LEVEL SECURITY;
ALTER TABLE materiality_topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE materiality_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE materiality_entries ENABLE ROW LEVEL SECURITY;

-- Registro e catálogo de temas são leitura aberta: quem lê um relatório tem direito de saber o que
-- a plataforma reconhece, o que ela implementa e o que ela declaradamente NÃO mapeia.
CREATE POLICY frameworks_read ON impact_frameworks FOR SELECT USING (true);
CREATE POLICY frameworks_write ON impact_frameworks FOR INSERT WITH CHECK (app_priv());
CREATE POLICY frameworks_update ON impact_frameworks FOR UPDATE
  USING (app_priv()) WITH CHECK (app_priv());

CREATE POLICY materiality_topics_read ON materiality_topics FOR SELECT USING (true);
CREATE POLICY materiality_topics_write ON materiality_topics FOR INSERT WITH CHECK (app_priv());

-- Mapeamento da plataforma (org_id nulo) é público; o da organização é dela e de quem ela mostra.
CREATE POLICY mappings_read ON framework_mappings FOR SELECT
  USING (org_id IS NULL OR org_id = app_org() OR app_priv());
CREATE POLICY mappings_write ON framework_mappings FOR INSERT
  WITH CHECK ((org_id = app_org() AND app_authenticated()) OR app_priv());
CREATE POLICY mappings_update ON framework_mappings FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY mappings_delete ON framework_mappings FOR DELETE
  USING (org_id = app_org() OR app_priv());

CREATE POLICY materiality_read ON materiality_assessments FOR SELECT
  USING (org_id = app_org() OR app_priv()
         OR (status = 'published' AND project_id IS NOT NULL
             AND app_project_investor(project_id)));
CREATE POLICY materiality_write ON materiality_assessments FOR INSERT
  WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY materiality_update ON materiality_assessments FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY materiality_entries_read ON materiality_entries FOR SELECT
  USING (EXISTS (SELECT 1 FROM materiality_assessments a WHERE a.id = assessment_id
                   AND (a.org_id = app_org() OR app_priv()
                        OR (a.status = 'published' AND a.project_id IS NOT NULL
                            AND app_project_investor(a.project_id)))));
CREATE POLICY materiality_entries_write ON materiality_entries FOR INSERT
  WITH CHECK (EXISTS (SELECT 1 FROM materiality_assessments a WHERE a.id = assessment_id
                        AND (a.org_id = app_org() OR app_priv())));
CREATE POLICY materiality_entries_update ON materiality_entries FOR UPDATE
  USING (EXISTS (SELECT 1 FROM materiality_assessments a WHERE a.id = assessment_id
                   AND (a.org_id = app_org() OR app_priv())))
  WITH CHECK (EXISTS (SELECT 1 FROM materiality_assessments a WHERE a.id = assessment_id
                        AND (a.org_id = app_org() OR app_priv())));
CREATE POLICY materiality_entries_delete ON materiality_entries FOR DELETE
  USING (EXISTS (SELECT 1 FROM materiality_assessments a WHERE a.id = assessment_id
                   AND (a.org_id = app_org() OR app_priv()) AND a.status = 'draft'));

GRANT SELECT ON impact_frameworks, materiality_topics TO impacto_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON framework_mappings TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON materiality_assessments TO impacto_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON materiality_entries TO impacto_app;
