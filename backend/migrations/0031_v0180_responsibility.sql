-- 0031_v0180_responsibility.sql — RESPONSABILIDADE: QUEM RESPONDE POR QUÊ, EM QUE ESCOPO E QUANDO
--
-- O QUE OS DOCUMENTOS PEDEM
--
-- "Responsável × papel × escopo × versão × decisão", separado da assinatura.
--
-- POR QUE SEPARADO DA ASSINATURA
--
-- Assinatura (v0.14.0) amarra uma PESSOA a um CONTEÚDO (`subject_sha256`): responde "quem conferiu
-- este texto exato". Responsabilidade responde outra pergunta: "quem responde por esta decisão, em
-- que papel, em que escopo e em que período". São coisas diferentes, e misturá-las produz os dois
-- erros clássicos: documento assinado por quem não tinha competência para decidir, e decisão
-- tomada por quem tinha competência mas sem registro nenhum.
--
-- AS DECISÕES
--
-- 1. **Designação é append-only; encerrar é preencher `ended_on`, uma vez só.** Trocar o
--    responsável retroativamente apagaria quem respondia no dia do fato — que é justamente o que
--    este módulo existe para registrar.
-- 2. **Um papel por escopo tem UM responsável corrente.** Índice único parcial.
-- 3. **Encerrar exige motivo.** Responsabilidade não é transferida em silêncio.
-- 4. **A decisão é conferida contra a designação**: o banco recusa decisão fora do período da
--    designação, ou sobre escopo que a designação não cobre.
-- 5. **Decisão que exige quatro olhos declara isso no catálogo**, e o banco recusa a segunda
--    confirmação pela mesma pessoa.
-- 6. **Pessoa externa entra por NOME, sem CPF.** O produto não precisa do documento para registrar
--    quem respondeu, e guardar CPF aqui criaria dado pessoal sensível sem necessidade (LGPD,
--    minimização).

-- ====================================================================== 1. catálogo de papéis
CREATE TABLE responsibility_roles (
  code        text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]{3,40}$'),
  name_pt     text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 5 AND 120),
  answers_for text NOT NULL CHECK (length(btrim(answers_for)) BETWEEN 20 AND 1000),
  -- O limite do papel. Está no banco porque é a parte que desaparece quando alguém lê só o nome.
  does_not_answer_for text NOT NULL CHECK (length(btrim(does_not_answer_for)) BETWEEN 20 AND 1000),
  scopes      text[] NOT NULL CHECK (cardinality(scopes) > 0),
  active      boolean NOT NULL DEFAULT true,
  position    integer NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE responsibility_roles IS
  'Papéis de responsabilidade. Lista editorial: a redação é nossa, e papel formal exigido por lei '
  '(dirigente, contador) continua sendo o que o estatuto e o contrato dizem, não o que esta tabela '
  'diz.';

INSERT INTO responsibility_roles(code, name_pt, answers_for, does_not_answer_for, scopes, position)
VALUES
  ('project_coordinator', 'Coordenação do projeto',
   'Responde pela execução do que foi planejado no projeto: cronograma, marcos, equipe e entrega '
   'das atividades.',
   'Não responde por conformidade fiscal, por validação de medição de terceiro nem por decisão '
   'jurídica da organização.', ARRAY['project'], 10),
  ('technical_lead', 'Responsabilidade técnica',
   'Responde pelo mérito técnico: metodologia, indicadores escolhidos, linha de base e leitura dos '
   'resultados.',
   'Não responde por prazo, por caixa nem por representação legal.', ARRAY['project','program'], 20),
  ('financial_lead', 'Responsabilidade financeira',
   'Responde pela execução financeira: classificação de despesa, comprovação e conciliação com o '
   'que foi aportado.',
   'Não responde por mérito técnico do projeto nem por decisão de investimento do financiador.',
   ARRAY['project','program','organization'], 30),
  ('legal_representative', 'Representação legal',
   'Responde pelos atos que obrigam a organização perante terceiros, nos limites do estatuto ou '
   'contrato social.',
   'Não substitui o que o estatuto exige (assembleia, conselho, diretoria colegiada), e esta '
   'designação na plataforma NÃO cria poder de representação.',
   ARRAY['organization'], 40),
  ('data_protection', 'Encarregado de dados pessoais',
   'Responde pelo atendimento de pedidos de titular e pela interlocução sobre tratamento de dados '
   'pessoais.',
   'Não responde pelo mérito das decisões de negócio que geraram o tratamento.',
   ARRAY['organization'], 50),
  ('measurement_validator', 'Validação de medição',
   'Responde pela conferência de medição de indicador de OUTRA organização: o que foi conferido, '
   'contra qual evidência.',
   'Não responde pela coleta do dado nem pelo resultado do projeto conferido.',
   ARRAY['project','program'], 60),
  ('program_owner', 'Titularidade do programa',
   'Responde pelas decisões do programa: objetivo, carteira, critérios de chamada e priorização.',
   'Não responde pela execução de cada projeto apoiado.', ARRAY['program'], 70),
  ('document_owner', 'Responsabilidade pelo documento',
   'Responde pelo conteúdo de um documento específico e pela sua atualização.',
   'Não é assinatura: responder pelo documento e assinar o documento são registros distintos.',
   ARRAY['document'], 80);

-- ====================================================================== 2. designação
CREATE TABLE responsibility_assignments (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  role_code   text NOT NULL REFERENCES responsibility_roles(code) ON DELETE RESTRICT,
  scope       text NOT NULL CHECK (scope IN ('organization','program','project','document')),
  subject_id  uuid NOT NULL,
  -- Pessoa da plataforma OU pessoa externa por NOME (sem CPF: o registro de quem respondeu não
  -- precisa do documento, e guardá-lo aqui criaria dado pessoal sem necessidade).
  user_id     uuid REFERENCES users(id) ON DELETE RESTRICT,
  external_name text CHECK (external_name IS NULL OR length(btrim(external_name)) BETWEEN 3 AND 200),
  external_note text CHECK (external_note IS NULL OR length(btrim(external_note)) BETWEEN 5 AND 500),
  mandate_basis text NOT NULL CHECK (length(btrim(mandate_basis)) BETWEEN 10 AND 2000),
  starts_on   date NOT NULL DEFAULT current_date,
  ended_on    date,
  ended_reason text CHECK (ended_reason IS NULL OR length(btrim(ended_reason)) BETWEEN 10 AND 2000),
  assigned_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT person_is_declared CHECK ((user_id IS NOT NULL) <> (external_name IS NOT NULL)),
  CONSTRAINT ended_has_reason CHECK (ended_on IS NULL OR ended_reason IS NOT NULL),
  CONSTRAINT ended_after_start CHECK (ended_on IS NULL OR ended_on >= starts_on)
);
COMMENT ON TABLE responsibility_assignments IS
  'Quem responde por quê, em que escopo e em que período. Append-only exceto o encerramento '
  '(ended_on + motivo, uma vez só): trocar o responsável retroativamente apagaria quem respondia no '
  'dia do fato.';
-- Um papel por escopo tem UM responsável corrente.
CREATE UNIQUE INDEX ux_responsibility_current
  ON responsibility_assignments(scope, subject_id, role_code) WHERE ended_on IS NULL;
CREATE INDEX ix_responsibility_org ON responsibility_assignments(org_id, created_at DESC);
CREATE INDEX ix_responsibility_user ON responsibility_assignments(user_id) WHERE ended_on IS NULL;

CREATE FUNCTION responsibility_end_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.org_id, NEW.role_code, NEW.scope, NEW.subject_id, NEW.user_id, NEW.external_name,
      NEW.mandate_basis, NEW.starts_on)
     IS DISTINCT FROM
     (OLD.org_id, OLD.role_code, OLD.scope, OLD.subject_id, OLD.user_id, OLD.external_name,
      OLD.mandate_basis, OLD.starts_on) THEN
    RAISE EXCEPTION 'designação de responsabilidade não é reescrita: encerre esta e crie outra. '
                    'Reescrever apagaria quem respondia no dia do fato' USING ERRCODE = '42501';
  END IF;
  IF OLD.ended_on IS NOT NULL AND NEW.ended_on IS DISTINCT FROM OLD.ended_on THEN
    RAISE EXCEPTION 'designação já encerrada não muda de data de encerramento'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_responsibility_end_only BEFORE UPDATE ON responsibility_assignments
  FOR EACH ROW EXECUTE FUNCTION responsibility_end_only();
CREATE TRIGGER trg_responsibility_no_delete BEFORE DELETE ON responsibility_assignments
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- O papel tem escopos permitidos, e o escopo da designação tem de ser um deles.
CREATE FUNCTION responsibility_scope_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_scopes text[];
BEGIN
  SELECT scopes INTO v_scopes FROM responsibility_roles
   WHERE code = NEW.role_code AND active;
  IF v_scopes IS NULL THEN
    RAISE EXCEPTION 'papel de responsabilidade inexistente ou inativo' USING ERRCODE = '23503';
  END IF;
  IF NOT (NEW.scope = ANY (v_scopes)) THEN
    RAISE EXCEPTION 'o papel % não se aplica ao escopo %: os escopos do papel são %',
      NEW.role_code, NEW.scope, array_to_string(v_scopes, ', ') USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_responsibility_scope BEFORE INSERT ON responsibility_assignments
  FOR EACH ROW EXECUTE FUNCTION responsibility_scope_guard();

-- ====================================================================== 3. decisão
CREATE TABLE responsibility_decision_kinds (
  code        text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]{3,40}$'),
  name_pt     text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 5 AND 120),
  what_it_is  text NOT NULL CHECK (length(btrim(what_it_is)) BETWEEN 20 AND 1000),
  requires_two boolean NOT NULL DEFAULT false,
  active      boolean NOT NULL DEFAULT true
);
COMMENT ON TABLE responsibility_decision_kinds IS
  'Tipos de decisão. `requires_two` é quatro-olhos declarado em DADO, e o banco o aplica — não '
  'depende de a rota lembrar.';

INSERT INTO responsibility_decision_kinds(code, name_pt, what_it_is, requires_two) VALUES
  ('approval', 'Aprovação', 'Aprova um conteúdo, um plano ou uma etapa, dentro do escopo do papel.',
   false),
  ('rejection', 'Recusa', 'Recusa um conteúdo, um plano ou uma etapa, com motivo.', false),
  ('technical_opinion', 'Parecer técnico',
   'Registra opinião técnica fundamentada, que não aprova nem recusa por si.', false),
  ('authorization_to_publish', 'Autorização para publicar',
   'Autoriza a publicação externa de conteúdo da organização — relatório, alegação, página '
   'pública.', true),
  ('acceptance_of_risk', 'Aceitação de risco',
   'Registra que a organização segue adiante CIENTE de um risco identificado, com quem aceitou.',
   true),
  ('delegation', 'Delegação',
   'Transfere a condução de um assunto para outra pessoa, sem transferir o papel.', false);

CREATE TABLE responsibility_decisions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  assignment_id uuid NOT NULL REFERENCES responsibility_assignments(id) ON DELETE RESTRICT,
  kind          text NOT NULL REFERENCES responsibility_decision_kinds(code) ON DELETE RESTRICT,
  statement     text NOT NULL CHECK (length(btrim(statement)) BETWEEN 20 AND 4000),
  -- "× versão": a decisão aponta para o documento E para a versão dele. Decisão sobre "o
  -- documento" sem versão é decisão sobre um alvo que muda depois.
  document_id   uuid REFERENCES documents(id) ON DELETE SET NULL,
  document_version integer CHECK (document_version IS NULL OR document_version > 0),
  -- A assinatura é OUTRA coisa, e opcional: pode existir decisão sem assinatura (registro de
  -- responsabilidade) e assinatura sem decisão (conferência de conteúdo).
  signature_id  uuid REFERENCES signatures(id) ON DELETE SET NULL,
  second_assignment_id uuid REFERENCES responsibility_assignments(id) ON DELETE RESTRICT,
  second_statement text CHECK (second_statement IS NULL
                               OR length(btrim(second_statement)) BETWEEN 20 AND 4000),
  taken_on      date NOT NULL DEFAULT current_date,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT document_version_needs_document CHECK (document_version IS NULL
                                                    OR document_id IS NOT NULL),
  CONSTRAINT second_has_statement CHECK ((second_assignment_id IS NULL)
                                         = (second_statement IS NULL))
);
COMMENT ON TABLE responsibility_decisions IS
  'A decisão tomada por uma designação, append-only, apontando para documento E VERSÃO quando o '
  'alvo é documento. Independente de assinatura: `signature_id` é opcional nos dois sentidos.';
CREATE INDEX ix_resp_decisions_assignment ON responsibility_decisions(assignment_id, taken_on DESC);
CREATE INDEX ix_resp_decisions_document ON responsibility_decisions(document_id)
  WHERE document_id IS NOT NULL;
CREATE TRIGGER trg_resp_decisions_append BEFORE UPDATE OR DELETE ON responsibility_decisions
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE FUNCTION responsibility_decision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  a record;
  b record;
  v_two boolean;
BEGIN
  SELECT * INTO a FROM responsibility_assignments WHERE id = NEW.assignment_id;
  IF a IS NULL THEN
    RAISE EXCEPTION 'designação inexistente' USING ERRCODE = '23503';
  END IF;
  -- A decisão vale no período da designação: quem respondia ontem não decide hoje, e quem responde
  -- hoje não decide por ontem.
  IF NEW.taken_on < a.starts_on OR (a.ended_on IS NOT NULL AND NEW.taken_on > a.ended_on) THEN
    RAISE EXCEPTION 'a decisão está fora do período da designação (% a %)', a.starts_on,
      coalesce(a.ended_on::text, 'em aberto') USING ERRCODE = '23514';
  END IF;

  SELECT requires_two INTO v_two FROM responsibility_decision_kinds
   WHERE code = NEW.kind AND active;
  IF v_two IS NULL THEN
    RAISE EXCEPTION 'tipo de decisão inexistente ou inativo' USING ERRCODE = '23503';
  END IF;

  IF NEW.second_assignment_id IS NOT NULL THEN
    SELECT * INTO b FROM responsibility_assignments WHERE id = NEW.second_assignment_id;
    IF b IS NULL THEN
      RAISE EXCEPTION 'segunda designação inexistente' USING ERRCODE = '23503';
    END IF;
    IF b.user_id IS NOT NULL AND b.user_id = a.user_id THEN
      RAISE EXCEPTION 'quatro-olhos exige PESSOAS diferentes: a mesma pessoa não confirma a '
                      'própria decisão' USING ERRCODE = '42501';
    END IF;
    IF b.id = a.id THEN
      RAISE EXCEPTION 'quatro-olhos exige designações diferentes' USING ERRCODE = '42501';
    END IF;
    IF NEW.taken_on < b.starts_on OR (b.ended_on IS NOT NULL AND NEW.taken_on > b.ended_on) THEN
      RAISE EXCEPTION 'a segunda confirmação está fora do período da designação dela'
        USING ERRCODE = '23514';
    END IF;
  ELSIF v_two THEN
    RAISE EXCEPTION 'a decisão "%" exige quatro-olhos: informe a segunda designação e a '
                    'declaração dela', NEW.kind USING ERRCODE = '23514';
  END IF;

  -- Documento tem de ser da mesma organização da designação, e a versão tem de existir.
  IF NEW.document_id IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM documents d WHERE d.id = NEW.document_id
                     AND d.org_id = a.org_id) THEN
      RAISE EXCEPTION 'o documento não é da organização desta designação' USING ERRCODE = '42501';
    END IF;
    IF NEW.document_version IS NOT NULL
       AND NOT EXISTS (SELECT 1 FROM documents d WHERE d.id = NEW.document_id
                         AND d.version = NEW.document_version) THEN
      RAISE EXCEPTION 'a versão % não é a do documento informado: decisão sobre documento é sobre '
                      'uma VERSÃO', NEW.document_version USING ERRCODE = '23514';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_resp_decision_guard BEFORE INSERT ON responsibility_decisions
  FOR EACH ROW EXECUTE FUNCTION responsibility_decision_guard();

-- ====================================================================== 4. quem responde agora
CREATE FUNCTION responsible_now(p_scope text, p_subject uuid)
  RETURNS TABLE (role_code text, role_name text, assignment_id uuid, who text, kind text,
                 starts_on date, mandate_basis text)
  LANGUAGE sql STABLE AS $$
  SELECT a.role_code, r.name_pt, a.id,
         coalesce(u.full_name, a.external_name),
         CASE WHEN a.user_id IS NOT NULL THEN 'platform_user' ELSE 'external_person' END,
         a.starts_on, a.mandate_basis
    FROM responsibility_assignments a
    JOIN responsibility_roles r ON r.code = a.role_code
    LEFT JOIN users u ON u.id = a.user_id
   WHERE a.scope = p_scope AND a.subject_id = p_subject AND a.ended_on IS NULL
   ORDER BY r.position
$$;
COMMENT ON FUNCTION responsible_now IS
  'Quem responde AGORA por um escopo. Para saber quem respondia numa data, consulte as designações '
  'com o período — a tabela guarda o histórico inteiro, de propósito.';

-- ====================================================================== 5. RLS
ALTER TABLE responsibility_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE responsibility_decision_kinds ENABLE ROW LEVEL SECURITY;
ALTER TABLE responsibility_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE responsibility_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY resp_roles_read ON responsibility_roles FOR SELECT USING (true);
CREATE POLICY resp_kinds_read ON responsibility_decision_kinds FOR SELECT USING (true);

-- A designação é lida pela organização, pela administração e por quem tem aporte no projeto: saber
-- quem responde pelo projeto que você financia é o mínimo.
CREATE POLICY resp_assignments_read ON responsibility_assignments FOR SELECT
  USING (org_id = app_org() OR app_priv()
         OR (scope = 'project' AND app_project_investor(subject_id)));
CREATE POLICY resp_assignments_write ON responsibility_assignments FOR INSERT
  WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY resp_assignments_update ON responsibility_assignments FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

CREATE POLICY resp_decisions_read ON responsibility_decisions FOR SELECT
  USING (EXISTS (SELECT 1 FROM responsibility_assignments a WHERE a.id = assignment_id
                   AND (a.org_id = app_org() OR app_priv()
                        OR (a.scope = 'project' AND app_project_investor(a.subject_id)))));
CREATE POLICY resp_decisions_write ON responsibility_decisions FOR INSERT
  WITH CHECK (EXISTS (SELECT 1 FROM responsibility_assignments a WHERE a.id = assignment_id
                        AND (a.org_id = app_org() OR app_priv())));

GRANT SELECT ON responsibility_roles, responsibility_decision_kinds TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON responsibility_assignments TO impacto_app;
GRANT SELECT, INSERT ON responsibility_decisions TO impacto_app;
GRANT EXECUTE ON FUNCTION responsible_now(text, uuid) TO impacto_app;
REVOKE DELETE ON responsibility_assignments, responsibility_decisions FROM impacto_app;
REVOKE UPDATE ON responsibility_decisions FROM impacto_app;
