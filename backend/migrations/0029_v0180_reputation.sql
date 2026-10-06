-- 0029_v0180_reputation.sql — REPUTAÇÃO EXPLICÁVEL, EM DIMENSÕES, SEM NOTA ÚNICA
--
-- O QUE OS DOCUMENTOS DESTA RODADA PEDEM, E A FRASE QUE GOVERNA A IMPLEMENTAÇÃO
--
--   "NUNCA transformar o score em uma caixa-preta que determina automaticamente acesso a
--    financiamento, contratação, benefícios, oportunidades ou exposição pública."
--
-- Tudo aqui é desenhado para que essa frase seja verdadeira por construção, não por promessa.
--
-- DECISÃO 1: NÃO EXISTE NOTA ÚNICA. É uma divergência consciente dos documentos, que falam de
-- "score de reputação". Nota única é o que vira ranking, e ranking é o que vira critério de acesso.
-- A saída é por DIMENSÃO, cada uma com valor, confiança, número de observações, quanto disso foi
-- verificado por terceiro, e a lista do que entrou na conta. Quem quiser compor as dimensões numa
-- nota só vai ter de fazer isso fora da plataforma, assinando a escolha dos pesos.
--
-- DECISÃO 2: A DIMENSÃO SEM BASE SUFICIENTE NÃO TEM VALOR. `value` é NULL e a faixa é
-- `insufficient`. Organização nova não começa ruim: começa SEM MEDIDA. Isso importa mais do que
-- parece — nota baixa por ausência de histórico seria uma barreira de entrada construída por
-- acidente, e cairia exatamente sobre a OSC pequena que esta plataforma existe para atender.
--
-- DECISÃO 3: O QUE ENTRA NA CONTA É FATO REGISTRADO POR TERCEIRO OU COM RASTRO. Medição validada
-- por organização diferente, evidência aceita, documento validado, despesa com comprovante, aporte
-- confirmado, alegação sustentada. Nada que a própria organização declare sobre si entra como
-- verificado — entra contado à parte, como `self_declared`.
--
-- DECISÃO 4: NADA DE PLANO, ASSINATURA OU PAGAMENTO ENTRA. Reafirma a ADR-042 (plano não influencia
-- busca, match nem recomendação) para a reputação. Há teste de varredura no código deste módulo.
--
-- DECISÃO 5: ÓRGÃO PÚBLICO NÃO RECEBE NOTA. Recebe "Perfil de Governança e Transparência": os
-- mesmos fatos, em contagem, sem valor de 0 a 100. Pontuar ente público é pontuar política pública.
--
-- DECISÃO 6: PESSOA FÍSICA NÃO TEM PERFIL PÚBLICO DE REPUTAÇÃO. Nem agregado, nem dimensão.

-- ======================================================================= 1. catálogo de dimensões
CREATE TABLE reputation_dimensions (
  code         text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]{3,40}$'),
  name_pt      text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 5 AND 120),
  what_it_measures text NOT NULL CHECK (length(btrim(what_it_measures)) BETWEEN 20 AND 1000),
  why_it_is_fair text NOT NULL CHECK (length(btrim(why_it_is_fair)) BETWEEN 20 AND 1000),
  -- O que a dimensão NÃO mede. Está no banco porque é a parte que some quando alguém resume o
  -- indicador numa tela.
  what_it_does_not_measure text NOT NULL CHECK (length(btrim(what_it_does_not_measure)) BETWEEN 20 AND 1000),
  signals_note text NOT NULL CHECK (length(btrim(signals_note)) BETWEEN 20 AND 2000),
  min_observations integer NOT NULL CHECK (min_observations BETWEEN 1 AND 50),
  position     integer NOT NULL,
  active       boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE reputation_dimensions IS
  'As dimensões de reputação. Lista FECHADA em código (impact/reputation.py calcula uma função por '
  'código): a tabela documenta e parametriza o mínimo de observações, não define cálculo novo.';

INSERT INTO reputation_dimensions(code, name_pt, what_it_measures, why_it_is_fair,
  what_it_does_not_measure, signals_note, min_observations, position) VALUES
  ('evidence_discipline', 'Disciplina de evidência',
   'Quanto do que a organização afirma como resultado está apoiado em medição validada por '
   'organização diferente e com evidência anexada no cofre.',
   'Mede o rastro, não o mérito: uma organização pequena com três medições validadas pontua igual a '
   'uma grande com trezentas, porque a conta é proporção e não volume.',
   'Não mede qualidade do projeto, tamanho do atendimento nem relevância da causa. Medir bem um '
   'projeto pequeno é disciplina; medir bem não é fazer mais.',
   'Numerador: valores de indicador com status validado E evidência anexada. Denominador: valores '
   'reportados. Observações: valores reportados.', 3, 10),
  ('financial_transparency', 'Transparência financeira',
   'Quanto das despesas registradas tem comprovante no cofre e quantos aportes foram confirmados '
   'pelas duas pontas.',
   'A distinção entre gasto e comprovado já existe no banco desde program_financials(); esta '
   'dimensão só a torna visível no perfil, sem reinterpretá-la.',
   'Não mede se o gasto foi bom, se o preço foi adequado nem se o recurso foi suficiente. Também '
   'não mede volume de recurso captado.',
   'Numerador: despesas com document_id. Denominador: despesas registradas. Segundo sinal: aportes '
   'com status confirmado sobre aportes desembolsados.', 3, 20),
  ('claim_integrity', 'Integridade de alegação',
   'Como as alegações publicadas pela organização se comportaram no confronto determinístico com o '
   'que está registrado.',
   'A regra é pública, o léxico é público e a alegação marcada tem direito a revisão de outra '
   'organização. Pontuar o resultado desse processo é pontuar algo contestável.',
   'Não mede intenção, não acusa fraude e não distingue erro de exagero. Alegação nunca verificada '
   'não conta como boa nem como ruim: não conta.',
   'Numerador: alegações com situação derivada substantiated. Denominador: alegações verificadas '
   '(qualquer rodada). Alegações flagged pesam negativamente apenas enquanto não revisadas.', 2, 30),
  ('institutional_formality', 'Formalidade institucional',
   'Documentos validados pela administração, qualificações verificadas e vigentes, e situação de '
   'compliance.',
   'Todo sinal desta dimensão depende de ato de terceiro (validação, verificação): nada entra por '
   'autodeclaração.',
   'Não mede capacidade de execução nem impacto. É a dimensão em que uma organização grande e '
   'burocrática leva vantagem — está declarado aqui para que ninguém a leia como qualidade.',
   'Documentos com validation_status validated e vigentes; qualificações com verification_status '
   'verified e não expiradas; compliance_status approved.', 2, 40),
  ('delivery_record', 'Histórico de entrega',
   'Marcos com evidência aceita e projetos levados a conclusão, sobre o que foi iniciado.',
   'Conta o que foi concluído sobre o que foi começado, e não o número absoluto de projetos: quem '
   'faz dois e entrega dois não fica atrás de quem faz vinte e entrega cinco.',
   'Não mede resultado social, só cumprimento do que foi planejado. Projeto cancelado por decisão '
   'do financiador não é falha da organização, e a plataforma não sabe distinguir — por isso só '
   'projetos concluídos contam a favor, e nenhum conta contra.',
   'Numerador: marcos com status accepted e projetos com status completed. Denominador: marcos não '
   'planejados e projetos que saíram de rascunho.', 3, 50),
  ('contribution_to_others', 'Contribuição à rede',
   'Atos em que a organização serviu de terceiro para outra: validar medição, revisar causalidade, '
   'revisar alegação marcada, revisar regra fiscal.',
   'É a única dimensão que não depende de ter projeto próprio, e a única em que o trabalho de '
   'conferir o alheio aparece. Sem ela, quem sustenta a confiança do sistema não tem onde aparecer.',
   'Não mede qualidade da revisão. Revisar muito e revisar bem não são a mesma coisa, e a '
   'plataforma só sabe contar.',
   'Medições validadas em projeto de outra organização, causalidades revisadas, revisões de '
   'alegação registradas, aprovações de regra fiscal.', 2, 60);

-- ======================================================================= 2. a linha do tempo
--
-- A reputação é CALCULADA na leitura, a partir das tabelas de fato. O snapshot existe para a linha
-- do tempo — "como estava em março" — e é append-only. Não existe caminho que escreva valor de
-- reputação sem passar pelo cálculo: a aplicação não tem INSERT nesta tabela, só a função
-- SECURITY DEFINER abaixo, que recebe o resultado do motor e não aceita valor arbitrário de fora
-- sem as contagens que o sustentam.
CREATE TABLE reputation_snapshots (
  id           bigserial PRIMARY KEY,
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  dimension    text NOT NULL REFERENCES reputation_dimensions(code) ON DELETE RESTRICT,
  value        numeric(5,2) CHECK (value IS NULL OR value BETWEEN 0 AND 100),
  confidence   numeric(5,2) NOT NULL CHECK (confidence BETWEEN 0 AND 100),
  band         text NOT NULL CHECK (band IN ('insufficient','low','medium','high')),
  observations integer NOT NULL CHECK (observations >= 0),
  verified_observations integer NOT NULL CHECK (verified_observations >= 0),
  self_declared_observations integer NOT NULL DEFAULT 0 CHECK (self_declared_observations >= 0),
  inputs       jsonb NOT NULL DEFAULT '{}'::jsonb,
  engine_version text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  -- Sem base suficiente não há valor. É a decisão 2, escrita como restrição.
  CONSTRAINT insufficient_has_no_value CHECK (band <> 'insufficient' OR value IS NULL),
  CONSTRAINT verified_within_observations CHECK (verified_observations <= observations)
);
COMMENT ON TABLE reputation_snapshots IS
  'Linha do tempo de reputação, append-only. A reputação corrente é CALCULADA na leitura; o '
  'snapshot serve para mostrar evolução e para que uma correção não apague o que foi publicado '
  'antes dela.';
CREATE INDEX ix_reputation_snapshots ON reputation_snapshots(org_id, dimension, created_at DESC);
CREATE TRIGGER trg_reputation_snapshots_append BEFORE UPDATE OR DELETE ON reputation_snapshots
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE FUNCTION app_record_reputation(p_org uuid, p_dimension text, p_value numeric,
                                      p_confidence numeric, p_band text, p_observations integer,
                                      p_verified integer, p_self_declared integer, p_inputs jsonb,
                                      p_engine text) RETURNS bigint
  LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_id bigint;
BEGIN
  IF p_observations = 0 AND p_value IS NOT NULL THEN
    RAISE EXCEPTION 'não se registra valor de reputação sem observação que o sustente'
      USING ERRCODE = '23514';
  END IF;
  INSERT INTO reputation_snapshots(org_id, dimension, value, confidence, band, observations,
    verified_observations, self_declared_observations, inputs, engine_version)
  VALUES (p_org, p_dimension, p_value, p_confidence, p_band, p_observations, p_verified,
          coalesce(p_self_declared, 0), coalesce(p_inputs, '{}'::jsonb), p_engine)
  RETURNING id INTO v_id;
  RETURN v_id;
END $$;
COMMENT ON FUNCTION app_record_reputation IS
  'Único caminho de escrita em reputation_snapshots: a aplicação não tem INSERT na tabela. Recusa '
  'valor sem observação que o sustente.';

-- ======================================================================= 3. contestação e correção
--
-- O direito de contestar só é real se a contestação APARECER. Então a contestação aberta é visível
-- no próprio perfil, ao lado da dimensão contestada, e não numa fila interna.
CREATE TABLE reputation_disputes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  dimension   text NOT NULL REFERENCES reputation_dimensions(code) ON DELETE RESTRICT,
  snapshot_id bigint REFERENCES reputation_snapshots(id) ON DELETE SET NULL,
  what_is_contested text NOT NULL CHECK (length(btrim(what_is_contested)) BETWEEN 20 AND 4000),
  expected_correction text NOT NULL CHECK (length(btrim(expected_correction)) BETWEEN 20 AND 4000),
  evidence_id uuid REFERENCES evidences(id) ON DELETE SET NULL,
  opened_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE reputation_disputes IS
  'Contestação de uma dimensão de reputação, aberta pela própria organização. Append-only: a '
  'contestação não é apagada nem reescrita, e a resolução é um fato NOVO em '
  'reputation_dispute_resolutions.';
CREATE INDEX ix_reputation_disputes ON reputation_disputes(org_id, created_at DESC);
CREATE TRIGGER trg_reputation_disputes_append BEFORE UPDATE OR DELETE ON reputation_disputes
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE TABLE reputation_dispute_resolutions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dispute_id  uuid NOT NULL REFERENCES reputation_disputes(id) ON DELETE CASCADE,
  outcome     text NOT NULL CHECK (outcome IN ('corrected','no_change','partially_corrected',
                                               'needs_more_information')),
  rationale   text NOT NULL CHECK (length(btrim(rationale)) BETWEEN 20 AND 4000),
  -- O que mudou no PRODUTO por causa da contestação. "no_change" exige dizer por quê, e é aqui que
  -- a resposta fica registrada para quem contestou ler.
  what_changed text CHECK (what_changed IS NULL OR length(btrim(what_changed)) BETWEEN 10 AND 4000),
  resolved_by uuid REFERENCES users(id) ON DELETE SET NULL,
  resolved_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (dispute_id)
);
COMMENT ON TABLE reputation_dispute_resolutions IS
  'Resolução da contestação, append-only e uma por contestação. A situação da contestação é '
  'DERIVADA (dispute_status): aberta enquanto não houver resolução.';
CREATE TRIGGER trg_reputation_resolutions_append BEFORE UPDATE OR DELETE
  ON reputation_dispute_resolutions
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE FUNCTION dispute_status(p_dispute uuid)
  RETURNS TABLE (status text, outcome text, resolved_at timestamptz)
  LANGUAGE sql STABLE AS $$
  SELECT CASE WHEN r.id IS NULL THEN 'open'
              WHEN r.outcome = 'needs_more_information' THEN 'awaiting_organization'
              ELSE 'resolved' END,
         r.outcome, r.resolved_at
    FROM reputation_disputes d
    LEFT JOIN reputation_dispute_resolutions r ON r.dispute_id = d.id
   WHERE d.id = p_dispute
$$;

-- ======================================================================= 4. RLS
ALTER TABLE reputation_dimensions ENABLE ROW LEVEL SECURITY;
ALTER TABLE reputation_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE reputation_disputes ENABLE ROW LEVEL SECURITY;
ALTER TABLE reputation_dispute_resolutions ENABLE ROW LEVEL SECURITY;

-- O catálogo é aberto: quem é avaliado tem direito de ler o critério, inclusive sem conta.
CREATE POLICY reputation_dimensions_read ON reputation_dimensions FOR SELECT USING (true);

-- O snapshot é legível por quem é avaliado e por quem está autenticado — reputação que ninguém
-- pode ler não serve para nada, e o que ela expõe já é fato de projeto, não dado pessoal.
CREATE POLICY reputation_snapshots_read ON reputation_snapshots FOR SELECT
  USING (app_authenticated() OR app_priv());

-- A contestação é lida pela organização que contesta, pela administração, e por qualquer pessoa
-- autenticada que esteja lendo o perfil: contestação invisível não é direito, é formulário.
CREATE POLICY reputation_disputes_read ON reputation_disputes FOR SELECT
  USING (app_authenticated() OR app_priv());
CREATE POLICY reputation_disputes_write ON reputation_disputes FOR INSERT
  WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY reputation_resolutions_read ON reputation_dispute_resolutions FOR SELECT
  USING (app_authenticated() OR app_priv());
-- Resolver é ato da administração da plataforma. A organização contesta; não se resolve a própria
-- contestação.
CREATE POLICY reputation_resolutions_write ON reputation_dispute_resolutions FOR INSERT
  WITH CHECK (app_priv());

GRANT SELECT ON reputation_dimensions TO impacto_app;
GRANT SELECT ON reputation_snapshots TO impacto_app;
GRANT EXECUTE ON FUNCTION app_record_reputation(uuid, text, numeric, numeric, text, integer,
                                                integer, integer, jsonb, text) TO impacto_app;
GRANT SELECT, INSERT ON reputation_disputes TO impacto_app;
GRANT SELECT, INSERT ON reputation_dispute_resolutions TO impacto_app;
REVOKE UPDATE, DELETE ON reputation_snapshots, reputation_disputes,
                          reputation_dispute_resolutions FROM impacto_app;
