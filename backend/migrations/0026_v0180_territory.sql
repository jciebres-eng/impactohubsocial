-- 0026_v0180_territory.sql — TERRITÓRIO COMO CATÁLOGO E INDICADOR TERRITORIAL COM FONTE
--
-- O QUE ESTAVA ERRADO
--
-- O código territorial era validado por EXPRESSÃO REGULAR (`BR-MT-5105150`) e a hierarquia era
-- derivada por prefixo de string em Python (`covers`, `specificity`). Funciona para cobertura, e não
-- responde a nada que um produto territorial precisa responder: qual é o nome deste município, qual é
-- a população dele, e de que fonte veio esse número.
--
-- O QUE ESTA MIGRAÇÃO NÃO FAZ
--
-- **Não inventa dado oficial.** Os 5.570 municípios brasileiros e a população de cada um vêm do IBGE,
-- e a rede deste ambiente alcança só registros de pacote. Então:
--
--   * o catálogo nasce com o país, as 5 regiões e as 27 unidades federativas, e cada linha diz de
--     onde veio;
--   * o nível MUNICIPAL entra por importação (`scripts/import_territories.py`), que exige nome da
--     fonte, URL e data de consulta;
--   * `territory_indicators` nasce **vazia** — nenhuma população, nenhuma taxa, nenhum índice.
--
-- POR QUE NÃO HÁ CHAVE ESTRANGEIRA DAS TABELAS ANTIGAS PARA O CATÁLOGO
--
-- `territory_needs`, `projects`, `programs` e `solutions` já guardam código de município que o
-- catálogo ainda não conhece. Criar a FK agora recusaria dado existente e legítimo. Então o catálogo
-- é consultado, não imposto: `territory_label()` resolve o nome quando conhece e devolve o próprio
-- código quando não conhece — o produto fica melhor quando o catálogo cresce, e não quebra enquanto
-- ele é parcial.

-- ============================================================================ 1. catálogo
CREATE TABLE territories (
  code        text PRIMARY KEY
                CHECK (code ~ '^(INT|BR-R[1-5]|[A-Z]{2}(-[A-Z]{2}(-[0-9]{7})?)?)$'),
  kind        text NOT NULL CHECK (kind IN ('international','country','region','state','municipality')),
  name        text NOT NULL CHECK (length(btrim(name)) BETWEEN 2 AND 160),
  parent_code text REFERENCES territories(code) ON DELETE RESTRICT,
  uf          char(2) CHECK (uf IS NULL OR uf ~ '^[A-Z]{2}$'),
  ibge_code   text CHECK (ibge_code IS NULL OR ibge_code ~ '^[0-9]{2}$|^[0-9]{7}$'),
  -- De onde veio ESTA linha. Sem isso, catálogo é opinião com cara de referência.
  source_name text NOT NULL CHECK (length(btrim(source_name)) BETWEEN 3 AND 300),
  source_url  text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  source_date date,
  -- Verdadeiro só quando a linha veio de carga de arquivo oficial, não de conhecimento da plataforma.
  from_official_load boolean NOT NULL DEFAULT false,
  active      boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE territories IS
  'Catálogo territorial consultado, não imposto: nenhuma tabela antiga ganhou FK para cá, porque já '
  'existe código de município legítimo que este catálogo ainda não conhece. O nível municipal entra '
  'por importação de arquivo oficial.';
COMMENT ON COLUMN territories.from_official_load IS
  'FALSO nas linhas semeadas pela migração (conhecimento da plataforma, a conferir na carga). '
  'VERDADEIRO só no que veio de arquivo oficial pelo importador. É a diferença entre "achamos que é" '
  'e "está no arquivo do IBGE".';
CREATE INDEX ix_territories_parent ON territories(parent_code);
CREATE INDEX ix_territories_kind ON territories(kind);
CREATE INDEX ix_territories_uf ON territories(uf) WHERE uf IS NOT NULL;
CREATE INDEX ix_territories_name ON territories USING gin (to_tsvector('pt_unaccent', name));
CREATE TRIGGER trg_territories_touch BEFORE UPDATE ON territories
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Município precisa de UF e de código de 7 dígitos; UF precisa de região. A hierarquia é cobrada.
CREATE FUNCTION territory_shape() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.kind = 'municipality' THEN
    IF NEW.uf IS NULL OR NEW.ibge_code IS NULL OR length(NEW.ibge_code) <> 7 THEN
      RAISE EXCEPTION 'município exige UF e código IBGE de 7 dígitos' USING ERRCODE = '23514';
    END IF;
    IF NEW.parent_code IS NULL THEN
      RAISE EXCEPTION 'município exige a UF como território pai' USING ERRCODE = '23514';
    END IF;
  ELSIF NEW.kind = 'state' AND NEW.parent_code IS NULL THEN
    RAISE EXCEPTION 'unidade federativa exige a região como território pai' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_territory_shape BEFORE INSERT OR UPDATE ON territories
  FOR EACH ROW EXECUTE FUNCTION territory_shape();

-- O país, as regiões e as 27 unidades federativas. Nome e sigla são estáveis e públicos; o código
-- numérico de UF é o do IBGE. `from_official_load = false` em todas: é conhecimento da plataforma, a
-- ser CONFERIDO quando o arquivo oficial for carregado — e o importador sobrescreve com o oficial.
INSERT INTO territories(code, kind, name, parent_code, uf, ibge_code, source_name) VALUES
  ('INT', 'international', 'Internacional', NULL, NULL, NULL,
   'Marcação interna da plataforma para atuação fora do Brasil.'),
  ('BR', 'country', 'Brasil', NULL, NULL, NULL,
   'Conhecimento da plataforma; conferir na carga oficial.');
INSERT INTO territories(code, kind, name, parent_code, source_name) VALUES
  ('BR-R1', 'region', 'Norte', 'BR', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-R2', 'region', 'Nordeste', 'BR', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-R3', 'region', 'Sudeste', 'BR', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-R4', 'region', 'Sul', 'BR', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-R5', 'region', 'Centro-Oeste', 'BR', 'Conhecimento da plataforma; conferir na carga oficial.');
INSERT INTO territories(code, kind, name, parent_code, uf, ibge_code, source_name) VALUES
  ('BR-AC', 'state', 'Acre', 'BR-R1', 'AC', '12', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-AP', 'state', 'Amapá', 'BR-R1', 'AP', '16', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-AM', 'state', 'Amazonas', 'BR-R1', 'AM', '13', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-PA', 'state', 'Pará', 'BR-R1', 'PA', '15', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-RO', 'state', 'Rondônia', 'BR-R1', 'RO', '11', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-RR', 'state', 'Roraima', 'BR-R1', 'RR', '14', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-TO', 'state', 'Tocantins', 'BR-R1', 'TO', '17', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-AL', 'state', 'Alagoas', 'BR-R2', 'AL', '27', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-BA', 'state', 'Bahia', 'BR-R2', 'BA', '29', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-CE', 'state', 'Ceará', 'BR-R2', 'CE', '23', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-MA', 'state', 'Maranhão', 'BR-R2', 'MA', '21', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-PB', 'state', 'Paraíba', 'BR-R2', 'PB', '25', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-PE', 'state', 'Pernambuco', 'BR-R2', 'PE', '26', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-PI', 'state', 'Piauí', 'BR-R2', 'PI', '22', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-RN', 'state', 'Rio Grande do Norte', 'BR-R2', 'RN', '24', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-SE', 'state', 'Sergipe', 'BR-R2', 'SE', '28', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-ES', 'state', 'Espírito Santo', 'BR-R3', 'ES', '32', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-MG', 'state', 'Minas Gerais', 'BR-R3', 'MG', '31', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-RJ', 'state', 'Rio de Janeiro', 'BR-R3', 'RJ', '33', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-SP', 'state', 'São Paulo', 'BR-R3', 'SP', '35', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-PR', 'state', 'Paraná', 'BR-R4', 'PR', '41', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-RS', 'state', 'Rio Grande do Sul', 'BR-R4', 'RS', '43', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-SC', 'state', 'Santa Catarina', 'BR-R4', 'SC', '42', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-DF', 'state', 'Distrito Federal', 'BR-R5', 'DF', '53', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-GO', 'state', 'Goiás', 'BR-R5', 'GO', '52', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-MT', 'state', 'Mato Grosso', 'BR-R5', 'MT', '51', 'Conhecimento da plataforma; conferir na carga oficial.'),
  ('BR-MS', 'state', 'Mato Grosso do Sul', 'BR-R5', 'MS', '50', 'Conhecimento da plataforma; conferir na carga oficial.');

-- Resolve o nome quando conhece; devolve o código quando não conhece. É o que permite o catálogo ser
-- parcial sem quebrar nada.
CREATE FUNCTION territory_label(p_code text) RETURNS text
  LANGUAGE sql STABLE AS $$
  SELECT coalesce((SELECT name FROM territories WHERE code = p_code AND active), p_code)
$$;
COMMENT ON FUNCTION territory_label IS
  'Nome do território, ou o próprio código quando o catálogo ainda não o conhece. Nunca inventa nome.';

-- A cadeia de cima para baixo: município → UF → região → país, usando o que o catálogo conhece e
-- caindo para a derivação por prefixo quando não conhece.
CREATE FUNCTION territory_chain(p_code text)
  RETURNS TABLE (code text, kind text, name text, known boolean)
  LANGUAGE sql STABLE AS $$
  WITH RECURSIVE up AS (
    SELECT t.code, t.kind, t.name, t.parent_code, 0 AS depth FROM territories t
     WHERE t.code = p_code
    UNION ALL
    SELECT t.code, t.kind, t.name, t.parent_code, up.depth + 1
      FROM territories t JOIN up ON t.code = up.parent_code
  ),
  -- Quando o código não está no catálogo, devolve pelo menos o que o próprio código informa.
  fallback AS (
    SELECT p_code AS code,
           CASE WHEN p_code = 'INT' THEN 'international'
                WHEN p_code ~ '^[A-Z]{2}$' THEN 'country'
                WHEN p_code ~ '^[A-Z]{2}-[A-Z]{2}$' THEN 'state'
                ELSE 'municipality' END AS kind,
           p_code AS name
     WHERE NOT EXISTS (SELECT 1 FROM territories WHERE code = p_code)
  )
  SELECT z.code, z.kind, z.name, z.known FROM (
    SELECT code, kind, name, true AS known, depth FROM up
    UNION ALL
    SELECT code, kind, name, false AS known, -1 AS depth FROM fallback
  ) z ORDER BY z.depth DESC
$$;
COMMENT ON FUNCTION territory_chain IS
  'A cadeia município → UF → região → país pelo catálogo. Quando o código não está no catálogo, '
  'devolve uma linha com known = false e o próprio código como nome: o produto continua funcionando '
  'com catálogo parcial, e quem lê sabe que o nome não foi resolvido.';

-- ============================================================================ 2. o que medir
-- Definições do que SE PRETENDE medir por determinante social. Lista editorial, como a dos próprios
-- determinantes (0012) e a das barreiras (0025) — e isso está escrito em cada linha.
CREATE TABLE determinant_indicator_defs (
  code             text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]{3,50}$'),
  determinant_code text NOT NULL REFERENCES social_determinants(code) ON DELETE RESTRICT,
  name_pt          text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 5 AND 200),
  unit             text NOT NULL CHECK (length(btrim(unit)) BETWEEN 1 AND 40),
  direction        text NOT NULL CHECK (direction IN ('higher_is_better','lower_is_better','context')),
  description      text NOT NULL CHECK (length(btrim(description)) BETWEEN 20 AND 1000),
  source_note      text NOT NULL,
  usual_source     text,
  active           boolean NOT NULL DEFAULT true,
  created_at       timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE determinant_indicator_defs IS
  'O que a plataforma PRETENDE medir por determinante social — a definição, não o dado. Lista '
  'editorial; a coluna usual_source diz onde o número costuma estar, sem afirmar que ele já está '
  'carregado.';
COMMENT ON COLUMN determinant_indicator_defs.direction IS
  'Para onde o número é melhor. `context` é para indicador que não é melhor nem pior — é contexto, e '
  'tratar contexto como desempenho é o erro que esta coluna existe para evitar.';

INSERT INTO determinant_indicator_defs(code, determinant_code, name_pt, unit, direction, description,
                                       source_note, usual_source) VALUES
  ('renda_media_domiciliar', 'income', 'Renda média domiciliar por pessoa', 'R$', 'higher_is_better',
   'Renda média mensal por pessoa nos domicílios do território, para leitura de contexto econômico.',
   'Definição editorial da plataforma.', 'IBGE — Censo / PNAD Contínua'),
  ('taxa_pobreza', 'income', 'Proporção de pessoas em situação de pobreza', '%', 'lower_is_better',
   'Proporção da população do território abaixo da linha de pobreza adotada pela fonte citada.',
   'Definição editorial; a LINHA de pobreza é a da fonte, não nossa.', 'IBGE / Cadastro Único'),
  ('taxa_analfabetismo', 'education', 'Taxa de analfabetismo (15 anos ou mais)', '%',
   'lower_is_better',
   'Proporção de pessoas de 15 anos ou mais que não sabem ler e escrever, no território.',
   'Definição editorial da plataforma.', 'IBGE — Censo'),
  ('distorcao_idade_serie', 'education', 'Distorção idade-série na rede pública', '%',
   'lower_is_better',
   'Proporção de estudantes com idade acima da esperada para a série que cursam.',
   'Definição editorial da plataforma.', 'INEP — Censo Escolar'),
  ('taxa_desocupacao', 'work', 'Taxa de desocupação', '%', 'lower_is_better',
   'Proporção da população economicamente ativa sem ocupação no período de referência.',
   'Definição editorial da plataforma.', 'IBGE — PNAD Contínua'),
  ('trabalho_informal', 'work', 'Proporção de ocupação informal', '%', 'context',
   'Proporção de pessoas ocupadas sem vínculo formal. É contexto: informalidade alta não é, por si, '
   'desempenho ruim do território.',
   'Definição editorial da plataforma.', 'IBGE — PNAD Contínua'),
  ('saneamento_adequado', 'housing', 'Domicílios com saneamento adequado', '%', 'higher_is_better',
   'Proporção de domicílios com abastecimento de água, esgotamento sanitário e coleta de resíduos '
   'conforme a definição da fonte citada.',
   'Definição editorial; o critério de "adequado" é o da fonte.', 'IBGE / SNIS'),
  ('deficit_habitacional', 'housing', 'Déficit habitacional', 'domicílios', 'lower_is_better',
   'Número de domicílios em situação de déficit conforme a metodologia da fonte citada.',
   'Definição editorial; a metodologia é a da fonte.', 'Fundação João Pinheiro'),
  ('inseguranca_alimentar', 'food', 'Domicílios em insegurança alimentar', '%', 'lower_is_better',
   'Proporção de domicílios em insegurança alimentar conforme a escala usada pela fonte citada.',
   'Definição editorial; a escala é a da fonte.', 'IBGE — POF / Rede PENSSAN'),
  ('cobertura_atencao_basica', 'health_services', 'Cobertura de atenção básica', '%',
   'higher_is_better',
   'Proporção da população do território coberta por equipes de atenção básica.',
   'Definição editorial da plataforma.', 'Ministério da Saúde — e-Gestor'),
  ('mortalidade_infantil', 'health_services', 'Taxa de mortalidade infantil', 'por mil nascidos',
   'lower_is_better',
   'Óbitos de menores de um ano por mil nascidos vivos no território.',
   'Definição editorial da plataforma.', 'DATASUS — SIM / SINASC'),
  ('cobertura_internet', 'social_support', 'Domicílios com acesso à internet', '%',
   'higher_is_better',
   'Proporção de domicílios com acesso à internet, para leitura de barreira digital no território.',
   'Definição editorial da plataforma.', 'IBGE — PNAD Contínua TIC'),
  ('area_verde_urbana', 'environment', 'Área verde urbana por habitante', 'm²/hab',
   'higher_is_better',
   'Área verde urbana disponível por habitante no território.',
   'Definição editorial da plataforma.', 'Prefeitura / IBGE'),
  ('taxa_homicidio', 'violence', 'Taxa de homicídios', 'por 100 mil', 'lower_is_better',
   'Homicídios por 100 mil habitantes no território, conforme a fonte citada.',
   'Definição editorial; a classificação do óbito é a da fonte.', 'SIM / Fórum Brasileiro de '
   'Segurança Pública'),
  ('equipamentos_culturais', 'social_support', 'Equipamentos culturais públicos', 'unidades',
   'context',
   'Número de equipamentos culturais públicos no território. É contexto, não desempenho.',
   'Definição editorial da plataforma.', 'IBGE — MUNIC');

-- ============================================================================ 3. o dado, com fonte
CREATE TABLE territory_indicators (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  territory      text NOT NULL REFERENCES territories(code) ON DELETE RESTRICT,
  code           text NOT NULL REFERENCES determinant_indicator_defs(code) ON DELETE RESTRICT,
  value          numeric(18,4) NOT NULL,
  unit           text NOT NULL,
  reference_date date NOT NULL,
  source_name    text NOT NULL CHECK (length(btrim(source_name)) BETWEEN 3 AND 300),
  source_url     text CHECK (source_url IS NULL OR source_url ~ '^https?://'),
  source_date    date NOT NULL,
  method_note    text,
  effective_from timestamptz NOT NULL DEFAULT now(),
  effective_until timestamptz,
  created_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT territory_indicator_period CHECK (effective_until IS NULL
                                               OR effective_until > effective_from)
);
COMMENT ON TABLE territory_indicators IS
  'Indicador territorial com fonte e data OBRIGATÓRIAS. Nasce VAZIA: nenhum número do IBGE, do '
  'DATASUS ou de qualquer outra fonte foi embutido — eles entram por importação de arquivo oficial. '
  'Número sem fonte neste produto é número inventado, e aqui ele seria usado para comparar '
  'territórios.';
CREATE UNIQUE INDEX ux_territory_indicator_current ON territory_indicators(territory, code)
  WHERE effective_until IS NULL;
CREATE INDEX ix_territory_indicators_code ON territory_indicators(code, reference_date DESC);

CREATE FUNCTION close_previous_territory_indicator() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  UPDATE territory_indicators SET effective_until = NEW.effective_from
   WHERE territory = NEW.territory AND code = NEW.code AND id <> NEW.id
     AND effective_until IS NULL;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_territory_indicator_close BEFORE INSERT ON territory_indicators
  FOR EACH ROW EXECUTE FUNCTION close_previous_territory_indicator();

CREATE FUNCTION territory_indicator_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.value IS DISTINCT FROM OLD.value OR NEW.source_name IS DISTINCT FROM OLD.source_name
     OR NEW.reference_date IS DISTINCT FROM OLD.reference_date
     OR NEW.territory IS DISTINCT FROM OLD.territory OR NEW.code IS DISTINCT FROM OLD.code THEN
    RAISE EXCEPTION 'indicador territorial é imutável: corrigir é publicar versão nova'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_territory_indicator_immutable BEFORE UPDATE ON territory_indicators
  FOR EACH ROW EXECUTE FUNCTION territory_indicator_immutable();

-- Panorama de um território: o que se sabe, com a fonte de cada número, e o que NÃO se sabe.
-- A segunda parte é a que importa: "não medido" precisa aparecer com o mesmo destaque do medido.
CREATE FUNCTION territory_profile(p_territory text)
  RETURNS TABLE (code text, name_pt text, determinant_code text, unit text, direction text,
                 value numeric, reference_date date, source_name text, source_date date,
                 measured boolean)
  LANGUAGE sql STABLE AS $$
  SELECT d.code, d.name_pt, d.determinant_code, d.unit, d.direction,
         ti.value, ti.reference_date, ti.source_name, ti.source_date,
         ti.id IS NOT NULL AS measured
    FROM determinant_indicator_defs d
    LEFT JOIN territory_indicators ti
           ON ti.code = d.code AND ti.territory = p_territory AND ti.effective_until IS NULL
   WHERE d.active
   ORDER BY d.determinant_code, d.name_pt
$$;
COMMENT ON FUNCTION territory_profile IS
  'Perfil do território: toda definição ativa, com o valor quando existe e `measured = false` quando '
  'não existe. Devolver só o que foi medido daria a impressão de que o resto não importa.';

-- ============================================================================ 4. RLS
ALTER TABLE territories ENABLE ROW LEVEL SECURITY;
ALTER TABLE determinant_indicator_defs ENABLE ROW LEVEL SECURITY;
ALTER TABLE territory_indicators ENABLE ROW LEVEL SECURITY;

-- Catálogo territorial e indicador territorial são BEM COMUM: leitura aberta, inclusive sem sessão,
-- porque é o tipo de dado que um município ou um conselho tem direito de consultar sem cadastro. O
-- que é restrito é ESCREVER.
CREATE POLICY territories_read ON territories FOR SELECT USING (true);
CREATE POLICY territories_write ON territories FOR INSERT WITH CHECK (app_priv() OR app_system());
CREATE POLICY territories_update ON territories FOR UPDATE
  USING (app_priv() OR app_system()) WITH CHECK (app_priv() OR app_system());

CREATE POLICY determinant_defs_read ON determinant_indicator_defs FOR SELECT USING (true);
CREATE POLICY determinant_defs_write ON determinant_indicator_defs FOR INSERT
  WITH CHECK (app_priv());
CREATE POLICY determinant_defs_update ON determinant_indicator_defs FOR UPDATE
  USING (app_priv()) WITH CHECK (app_priv());

CREATE POLICY territory_indicators_read ON territory_indicators FOR SELECT USING (true);
CREATE POLICY territory_indicators_write ON territory_indicators FOR INSERT
  WITH CHECK (app_priv() OR app_system());
CREATE POLICY territory_indicators_update ON territory_indicators FOR UPDATE
  USING (app_priv() OR app_system()) WITH CHECK (app_priv() OR app_system());

GRANT SELECT, INSERT, UPDATE ON territories TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON determinant_indicator_defs TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON territory_indicators TO impacto_app;
