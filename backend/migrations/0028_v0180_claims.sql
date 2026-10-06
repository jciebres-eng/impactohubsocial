-- 0028_v0180_claims.sql — INTEGRIDADE DE ALEGAÇÃO (o que os documentos chamam de anti-greenwashing)
--
-- O PROBLEMA REAL
--
-- Um relatório de impacto é feito de ALEGAÇÕES: "atendemos 1.200 pessoas", "contribuímos para o ODS
-- 4", "reduzimos em 30% o consumo de água", "nosso projeto é neutro em carbono". Cada uma dessas
-- frases pode ser verdadeira, exagerada ou inventada — e hoje nada no produto confronta a frase com
-- o que o banco sabe.
--
-- A DECISÃO DE DESENHO MAIS IMPORTANTE: **A SITUAÇÃO DA ALEGAÇÃO NÃO É UMA COLUNA.**
--
-- A tentação é guardar `status` em `claims` e deixar o verificador atualizá-lo. O problema é óbvio
-- depois de escrito: uma coluna de situação é escrevível, e no dia em que alguém precisar que a
-- alegação apareça como comprovada, ela aparece. Então a situação é DERIVADA por `claim_status()` a
-- partir da última rodada de verificações registradas. Não existe o que falsificar.
--
-- A SEGUNDA DECISÃO: O VERIFICADOR NÃO ACUSA FRAUDE
--
-- As regras devolvem `attention` ou `serious`, nunca "fraude". Nenhuma delas produz consequência
-- automática: alegação marcada `serious` exige REVISÃO HUMANA por alguém de OUTRA organização, e a
-- revisão fica registrada com motivo. Classificar automaticamente alguém como fraudador a partir de
-- heurística de texto seria pior que o problema que o verificador resolve.
--
-- A TERCEIRA: É DETERMINÍSTICO
--
-- Nenhuma regra chama modelo de linguagem. São consultas SQL e casamento de léxico declarado. O
-- motivo é o mesmo que fez o registro de motores (v0.17.0) existir: resultado de verificação precisa
-- ser reproduzível e contestável, e saída de modelo não é nem uma nem outra.

-- ============================================================================ 1. catálogo de regras
CREATE TABLE claim_rules (
  code         text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]{3,50}$'),
  name_pt      text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 5 AND 200),
  severity     text NOT NULL CHECK (severity IN ('info','attention','serious')),
  what_it_detects text NOT NULL CHECK (length(btrim(what_it_detects)) BETWEEN 20 AND 1000),
  why_it_matters  text NOT NULL CHECK (length(btrim(why_it_matters)) BETWEEN 20 AND 1000),
  deterministic boolean NOT NULL DEFAULT true,
  active       boolean NOT NULL DEFAULT true,
  created_at   timestamptz NOT NULL DEFAULT now(),
  -- Nenhuma regra desta tabela pode ser "probabilística": verificação não reproduzível não serve
  -- para contestar nem para defender.
  CONSTRAINT rules_are_deterministic CHECK (deterministic)
);
COMMENT ON TABLE claim_rules IS
  'As regras de integridade de alegação. Todas DETERMINÍSTICAS (consulta SQL ou léxico declarado): '
  'nenhuma chama modelo de linguagem, porque resultado de verificação precisa ser reproduzível e '
  'contestável.';

INSERT INTO claim_rules(code, name_pt, severity, what_it_detects, why_it_matters) VALUES
  ('ods_without_indicator', 'ODS declarado sem indicador', 'attention',
   'O sujeito da alegação declara contribuição a um ODS e não tem nenhum indicador vinculado que '
   'permita medir essa contribuição.',
   'Marcar um ODS é gratuito; medir a contribuição não é. Sem indicador, a declaração é intenção, e '
   'apresentá-la como contribuição é o caso mais comum de alegação vazia.'),
  ('indicator_without_measurement', 'Indicador sem medição', 'attention',
   'Há indicador vinculado ao sujeito e nenhum valor registrado para ele.',
   'Indicador sem valor não mede nada. Relatório que lista indicadores vazios dá impressão de '
   'medição onde não houve.'),
  ('measurement_without_evidence', 'Medição validada sem evidência anexada', 'attention',
   'Existem valores validados cujo registro não aponta para nenhuma evidência no cofre.',
   'A validação é conferência humana; a evidência é o que permite a um terceiro refazer a '
   'conferência. Sem ela, a medição depende da palavra de quem validou.'),
  ('absolute_language', 'Linguagem absoluta sem base', 'serious',
   'O texto da alegação usa termo absoluto (comprovado, garantido, 100%, zero, neutro, erradicou) '
   'sem que haja medição validada com evidência no período.',
   'Termo absoluto é o que transforma um resultado parcial em afirmação indefensável. É a forma mais '
   'direta de impact washing, e a mais fácil de detectar.'),
  ('certification_language', 'Alegação de certificação', 'serious',
   'O texto afirma certificação, homologação ou aprovação oficial.',
   'A plataforma não certifica nada e não é organismo certificador. Alegação de certificação '
   'inexistente expõe quem a publica, não a plataforma.'),
  ('causality_from_weak_link', 'Causalidade afirmada sobre elo fraco', 'serious',
   'O texto afirma causalidade (gerou, resultou em, provocou, foi responsável por) enquanto a cadeia '
   'de resultado do sujeito só tem elo de hipótese, correlação ou associação.',
   'Promover hipótese a causalidade é o erro que faz relatório de impacto virar ficção — e o banco já '
   'separa os dois desde a v0.8.0, então a alegação pode ser confrontada com o que foi declarado.'),
  ('comparative_without_denominator', 'Comparação sem denominador', 'attention',
   'O texto compara ("maior que", "mais que", "o maior", "lidera") sem que exista denominador '
   'declarado com fonte para o sujeito.',
   'Comparar sem denominador é comparar escala absoluta, que é exatamente o que esta rodada decidiu '
   'não tratar como impacto.'),
  ('number_not_in_measurements', 'Número do texto sem correspondência medida', 'attention',
   'O texto traz número de magnitude relevante que não corresponde a nenhum valor validado do '
   'sujeito no período.',
   'Número no texto e número no banco divergindo é o sinal mais objetivo de alegação solta — e quem '
   'relata costuma não perceber que divergiu.'),
  ('period_outside_execution', 'Período da alegação fora da execução', 'attention',
   'O período declarado na alegação não está contido no período de execução do projeto.',
   'Alegar resultado de período em que o projeto não estava em execução atribui a ele algo que '
   'aconteceu por outra razão.'),
  ('financial_claim_without_receipt', 'Alegação financeira sem comprovante', 'serious',
   'A alegação fala de valor aplicado ou executado e existem despesas do sujeito sem comprovante no '
   'cofre.',
   'Despesa registrada sem comprovante conta em "gasto" e não conta em "comprovado" — a distinção já '
   'existe em program_financials(), e a alegação não pode apagá-la.'),
  ('no_basis_at_all', 'Nenhuma base registrada', 'serious',
   'O sujeito da alegação não tem indicador, nem evidência, nem elo de cadeia de resultado.',
   'Alegação sobre sujeito sem nenhuma base registrada não é exagero: é texto.');

-- ============================================================================ 2. a alegação
CREATE TABLE claims (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  subject_type  text NOT NULL CHECK (subject_type IN ('project','program','organization','solution',
                                                      'impact_update')),
  subject_id    uuid NOT NULL,
  claim_kind    text NOT NULL CHECK (claim_kind IN ('result','ods_contribution','esg','environmental',
                                                    'social','governance','efficiency','financial',
                                                    'comparative','certification')),
  -- O texto EXATO que será publicado. É ele que o verificador confronta.
  statement     text NOT NULL CHECK (length(btrim(statement)) BETWEEN 10 AND 4000),
  scope_note    text CHECK (scope_note IS NULL OR length(scope_note) <= 2000),
  period_start  date,
  period_end    date,
  indicator_id  uuid REFERENCES indicator_catalog(id) ON DELETE SET NULL,
  evidence_id   uuid REFERENCES evidences(id) ON DELETE SET NULL,
  withdrawn_at  timestamptz,
  withdrawn_reason text,
  declared_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT claim_period CHECK (period_end IS NULL OR period_start IS NULL
                                 OR period_end >= period_start),
  CONSTRAINT withdrawn_has_reason CHECK (withdrawn_at IS NULL OR withdrawn_reason IS NOT NULL)
);
COMMENT ON TABLE claims IS
  'Alegação de impacto, no texto exato em que será publicada. NÃO tem coluna de situação: a situação '
  'é derivada por claim_status() da última rodada de verificação, justamente para que não exista o '
  'que falsificar.';
CREATE INDEX ix_claims_subject ON claims(subject_type, subject_id);
CREATE INDEX ix_claims_org ON claims(org_id, created_at DESC);
CREATE TRIGGER trg_claims_touch BEFORE UPDATE ON claims
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ============================================================================ 3. a verificação
CREATE TABLE claim_checks (
  id           bigserial PRIMARY KEY,
  claim_id     uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  check_round  integer NOT NULL CHECK (check_round > 0),
  rule_code    text NOT NULL REFERENCES claim_rules(code) ON DELETE RESTRICT,
  passed       boolean NOT NULL,
  severity     text NOT NULL CHECK (severity IN ('info','attention','serious')),
  detail       text NOT NULL CHECK (length(btrim(detail)) BETWEEN 5 AND 2000),
  engine_version text NOT NULL,
  checked_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (claim_id, check_round, rule_code)
);
COMMENT ON TABLE claim_checks IS
  'Trilha append-only de cada verificação. `check_round` existe para que a verificação de hoje não '
  'apague a de ontem: a situação vem da ÚLTIMA rodada, e as anteriores continuam legíveis para quem '
  'quiser mostrar que corrigiu.';
CREATE INDEX ix_claim_checks_claim ON claim_checks(claim_id, check_round DESC);
CREATE TRIGGER trg_claim_checks_append BEFORE UPDATE OR DELETE ON claim_checks
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- O texto não muda depois de verificado. Mudar o texto e manter a verificação anterior seria a forma
-- mais simples de burlar tudo isto.
CREATE FUNCTION claim_statement_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.statement IS DISTINCT FROM OLD.statement
     AND EXISTS (SELECT 1 FROM claim_checks WHERE claim_id = OLD.id) THEN
    RAISE EXCEPTION 'alegação já verificada não troca de texto: declare outra alegação. Trocar o '
                    'texto e manter a verificação anterior burlaria toda a integridade'
      USING ERRCODE = '42501';
  END IF;
  IF NEW.subject_type IS DISTINCT FROM OLD.subject_type
     OR NEW.subject_id IS DISTINCT FROM OLD.subject_id
     OR NEW.org_id IS DISTINCT FROM OLD.org_id THEN
    RAISE EXCEPTION 'alegação não troca de sujeito nem de organização' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_claim_frozen BEFORE UPDATE ON claims
  FOR EACH ROW EXECUTE FUNCTION claim_statement_frozen();

-- ====================================================================== 4. o convite para revisar
--
-- POR QUE REVISÃO É POR CONVITE
--
-- A primeira versão deixava qualquer organização revisar qualquer alegação marcada. Duas
-- consequências, as duas ruins: para revisar é preciso LER a alegação e a verificação, então
-- "qualquer um revisa" significa "toda alegação marcada é pública"; e revisão não solicitada é um
-- canal para pressionar concorrente. Então quem declarou convida uma organização nomeada para a
-- RODADA, e o convite é o que abre a leitura.
CREATE TABLE claim_review_requests (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id    uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  check_round integer NOT NULL,
  requested_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  note        text CHECK (note IS NULL OR length(btrim(note)) BETWEEN 10 AND 2000),
  requested_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (claim_id, check_round, requested_org_id)
);
COMMENT ON TABLE claim_review_requests IS
  'Convite nomeado para revisar uma RODADA de verificação. É o convite que abre a leitura da '
  'alegação e da verificação para a organização convidada — sem ele, alegação marcada não é '
  'visível fora de quem a declarou, e não existe revisão não solicitada.';
CREATE INDEX ix_claim_review_requests_org ON claim_review_requests(requested_org_id, created_at DESC);

CREATE FUNCTION claim_review_request_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_org uuid;
BEGIN
  SELECT org_id INTO v_org FROM claims WHERE id = NEW.claim_id;
  IF v_org = NEW.requested_org_id THEN
    RAISE EXCEPTION 'não se convida a própria organização para revisar: a revisão é externa'
      USING ERRCODE = '42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM claim_checks
                  WHERE claim_id = NEW.claim_id AND check_round = NEW.check_round) THEN
    RAISE EXCEPTION 'não existe rodada de verificação % para esta alegação', NEW.check_round
      USING ERRCODE = '23503';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_claim_review_request_guard BEFORE INSERT ON claim_review_requests
  FOR EACH ROW EXECUTE FUNCTION claim_review_request_guard();

-- ============================================================================ 5. revisão humana
CREATE TABLE claim_reviews (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  claim_id    uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
  check_round integer NOT NULL,
  decision    text NOT NULL CHECK (decision IN ('accepted','needs_change','rejected')),
  note        text NOT NULL CHECK (length(btrim(note)) BETWEEN 20 AND 2000),
  reviewer_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  reviewer_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (claim_id, check_round, reviewer_org_id)
);
COMMENT ON TABLE claim_reviews IS
  'Revisão humana de alegação marcada. Vinculada à RODADA de verificação: revisão de uma rodada não '
  'vale para a rodada seguinte, pelo mesmo princípio que faz assinatura não valer para versão nova '
  'de documento.';
CREATE INDEX ix_claim_reviews_claim ON claim_reviews(claim_id, check_round DESC);
CREATE TRIGGER trg_claim_reviews_append BEFORE UPDATE OR DELETE ON claim_reviews
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Quem declara não revisa. Mesma lição de indicator_values, impact_edges e framework_mappings.
CREATE FUNCTION claim_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_org uuid;
BEGIN
  SELECT org_id INTO v_org FROM claims WHERE id = NEW.claim_id;
  IF v_org = NEW.reviewer_org_id THEN
    RAISE EXCEPTION 'quem declarou a alegação não a revisa: a revisão é de outra organização'
      USING ERRCODE = '42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM claim_checks
                  WHERE claim_id = NEW.claim_id AND check_round = NEW.check_round) THEN
    RAISE EXCEPTION 'não existe rodada de verificação % para esta alegação', NEW.check_round
      USING ERRCODE = '23503';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM claim_review_requests
                  WHERE claim_id = NEW.claim_id AND check_round = NEW.check_round
                    AND requested_org_id = NEW.reviewer_org_id) THEN
    RAISE EXCEPTION 'revisão exige convite para esta rodada: não existe revisão não solicitada'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_claim_review_guard BEFORE INSERT ON claim_reviews
  FOR EACH ROW EXECUTE FUNCTION claim_review_guard();

-- ============================================================================ 6. a situação derivada
CREATE FUNCTION claim_status(p_claim uuid)
  RETURNS TABLE (status text, check_round integer, serious integer, attention integer,
                 reviewed boolean, review_decision text)
  LANGUAGE sql STABLE AS $$
  WITH last_round AS (
    SELECT coalesce(max(check_round), 0) AS r FROM claim_checks WHERE claim_id = p_claim),
  tally AS (
    SELECT count(*) FILTER (WHERE NOT passed AND severity = 'serious') AS serious,
           count(*) FILTER (WHERE NOT passed AND severity = 'attention') AS attention,
           count(*) AS total
      FROM claim_checks, last_round WHERE claim_id = p_claim AND check_round = last_round.r),
  rev AS (
    SELECT decision FROM claim_reviews, last_round
      WHERE claim_id = p_claim AND check_round = last_round.r
      ORDER BY reviewed_at DESC LIMIT 1)
  SELECT CASE
           WHEN (SELECT withdrawn_at FROM claims WHERE id = p_claim) IS NOT NULL THEN 'withdrawn'
           WHEN (SELECT r FROM last_round) = 0 THEN 'unchecked'
           WHEN (SELECT decision FROM rev) = 'rejected' THEN 'rejected_by_review'
           WHEN (SELECT decision FROM rev) = 'needs_change' THEN 'needs_change'
           WHEN t.serious > 0 AND (SELECT decision FROM rev) IS NULL THEN 'flagged'
           WHEN t.serious > 0 AND (SELECT decision FROM rev) = 'accepted'
             THEN 'flagged_accepted_by_review'
           WHEN t.attention > 0 THEN 'attention'
           ELSE 'substantiated'
         END,
         (SELECT r FROM last_round)::integer, t.serious::integer, t.attention::integer,
         (SELECT decision FROM rev) IS NOT NULL, (SELECT decision FROM rev)
    FROM tally t
$$;
COMMENT ON FUNCTION claim_status IS
  'Situação DERIVADA da última rodada de verificação. Não existe coluna de situação em claims, de '
  'propósito: coluna de situação é escrevível, e no dia em que alguém precisar que a alegação apareça '
  'como comprovada, ela apareceria. `flagged` exige revisão humana de OUTRA organização; a revisão '
  'não apaga a marca, apenas a qualifica (flagged_accepted_by_review).';

-- ============================================================================ 7. RLS
--
-- O convite abre a leitura da alegação, e a política do convite precisa olhar a alegação para saber
-- quem pode convidar: uma política citando a outra é recursão infinita (o Postgres recusa a
-- consulta inteira, como deve). A saída é uma função SECURITY DEFINER que responde a ÚNICA pergunta
-- necessária — "esta organização foi convidada para esta alegação?" — sem reentrar na política.
-- Ela não devolve conteúdo nenhum e só sabe responder sobre a organização de quem pergunta.
CREATE FUNCTION app_claim_invited(p_claim uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM claim_review_requests r
                  WHERE r.claim_id = p_claim AND r.requested_org_id = app_org());
$$;
COMMENT ON FUNCTION app_claim_invited IS
  'Responde apenas se a organização do chamador foi convidada a revisar a alegação. SECURITY '
  'DEFINER para quebrar a recursão entre a política de claims e a de claim_review_requests; não '
  'devolve conteúdo e não responde sobre outra organização.';
GRANT EXECUTE ON FUNCTION app_claim_invited(uuid) TO impacto_app;
ALTER TABLE claim_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_checks ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_reviews ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_review_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY claim_rules_read ON claim_rules FOR SELECT USING (true);

-- A alegação é da organização. Quem apoia o projeto também lê — é o interesse mais legítimo que
-- existe em saber se a alegação do relatório que recebeu se sustenta.
CREATE POLICY claims_read ON claims FOR SELECT
  USING (org_id = app_org() OR app_priv()
         OR (subject_type = 'project' AND app_project_investor(subject_id))
         OR app_claim_invited(claims.id));
CREATE POLICY claims_write ON claims FOR INSERT
  WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY claims_update ON claims FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY claim_checks_read ON claim_checks FOR SELECT
  USING (EXISTS (SELECT 1 FROM claims c WHERE c.id = claim_id
                   AND (c.org_id = app_org() OR app_priv()
                        OR (c.subject_type = 'project' AND app_project_investor(c.subject_id))))
         OR app_claim_invited(claim_checks.claim_id));
CREATE POLICY claim_checks_write ON claim_checks FOR INSERT
  WITH CHECK (EXISTS (SELECT 1 FROM claims c WHERE c.id = claim_id
                        AND (c.org_id = app_org() OR app_priv() OR app_system())));

CREATE POLICY claim_reviews_read ON claim_reviews FOR SELECT
  USING (reviewer_org_id = app_org() OR app_priv()
         OR EXISTS (SELECT 1 FROM claims c WHERE c.id = claim_id AND c.org_id = app_org()));
CREATE POLICY claim_reviews_write ON claim_reviews FOR INSERT
  WITH CHECK (reviewer_org_id = app_org() OR app_priv());

-- O convite é escrito por quem declarou a alegação, e lido pelas duas pontas.
CREATE POLICY claim_requests_read ON claim_review_requests FOR SELECT
  USING (requested_org_id = app_org() OR app_priv()
         OR EXISTS (SELECT 1 FROM claims c WHERE c.id = claim_id AND c.org_id = app_org()));
CREATE POLICY claim_requests_write ON claim_review_requests FOR INSERT
  WITH CHECK (app_priv()
              OR EXISTS (SELECT 1 FROM claims c WHERE c.id = claim_id AND c.org_id = app_org()));

GRANT SELECT ON claim_rules TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON claims TO impacto_app;
GRANT SELECT, INSERT ON claim_checks TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE claim_checks_id_seq TO impacto_app;
GRANT SELECT, INSERT ON claim_reviews TO impacto_app;
GRANT SELECT, INSERT, DELETE ON claim_review_requests TO impacto_app;
REVOKE UPDATE, DELETE ON claim_checks, claim_reviews FROM impacto_app;
