-- 0030_v0180_seals.sql — SELO DE IMPACTO: DEFINIÇÃO VERSIONADA, CRITÉRIO EM SQL, NUNCA COMPRÁVEL
--
-- O QUE OS DOCUMENTOS PEDEM
--
-- Um motor de selos com SealDefinition, Rule, Criteria, Evidence, Verification, Version, Status,
-- ExpiresAt, RevokedAt e AuditTrail — baseado em regra, nunca comprável.
--
-- A DECISÃO QUE TORNA O SELO INFALSIFICÁVEL: **O CRITÉRIO É AVALIADO EM SQL, NÃO NA APLICAÇÃO.**
--
-- Se a avaliação morasse em Python e o resultado fosse gravado por uma rota, bastaria uma chamada
-- com o corpo certo para conceder selo sem critério — e nenhuma revisão de código pega isso depois
-- de um ano. Então `seal_evaluate()` consulta os fatos ela mesma, e `app_award_seal()` **chama
-- `seal_evaluate()` antes de inserir** e recusa quando algum critério não está satisfeito. Não
-- existe caminho, nem privilegiado, que conceda selo sem que o banco concorde.
--
-- AS OUTRAS DECISÕES
--
-- 1. **Definição publicada é IMUTÁVEL.** Mudar critério exige versão nova. Selo cujo critério muda
--    em silêncio não atesta nada: quem olha o selo de ontem não sabe o que ele exigia.
-- 2. **A situação é DERIVADA** (`seal_status()`): ativo, expirado, revogado ou de definição
--    superada. Mesma razão da alegação — coluna de situação é escrevível.
-- 3. **Revogação é fato NOVO**, append-only, com motivo. Perder o selo não apaga que ele existiu.
-- 4. **A avaliação que NÃO concede também fica registrada** (`seal_evaluations`), porque "por que
--    eu não recebi" é a pergunta mais legítima que existe sobre um selo.
-- 5. **Nenhum critério é comercial.** Não há plano, pagamento ou assinatura em lugar nenhum deste
--    arquivo, e há teste de varredura.
-- 6. **Nenhum critério é reputação.** O selo não lê `reputation_snapshots`: encadear selo em nota
--    transformaria a nota naquilo que a FASE 6 recusou ser.

-- ============================================================================= 1. o conjunto de regras
CREATE TABLE seal_rules (
  code        text PRIMARY KEY CHECK (code ~ '^[a-z][a-z0-9_]{3,50}$'),
  scope       text NOT NULL CHECK (scope IN ('organization','project')),
  name_pt     text NOT NULL CHECK (length(btrim(name_pt)) BETWEEN 5 AND 200),
  what_it_checks text NOT NULL CHECK (length(btrim(what_it_checks)) BETWEEN 20 AND 1000),
  params_note text NOT NULL CHECK (length(btrim(params_note)) BETWEEN 5 AND 500),
  created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE seal_rules IS
  'Conjunto FECHADO de critérios. Cada código tem implementação em seal_evaluate() (SQL); a tabela '
  'documenta, não define cálculo novo. Regra nova exige migração, que é o ponto: critério de selo '
  'não deveria poder nascer de um INSERT.';

INSERT INTO seal_rules(code, scope, name_pt, what_it_checks, params_note) VALUES
  ('compliance_approved', 'organization', 'Compliance aprovado',
   'A organização tem compliance aprovado pela administração da plataforma.', 'sem parâmetros'),
  ('documents_validated', 'organization', 'Documentos validados e vigentes',
   'Todos os tipos de documento exigidos estão validados por revisor e dentro da validade.',
   '{"doc_types": ["estatuto_social", "cartao_cnpj"]}'),
  ('measurements_with_evidence', 'organization', 'Medições validadas com evidência',
   'Há pelo menos N valores de indicador validados por organização diferente E com evidência '
   'anexada no cofre.', '{"min_count": 3}'),
  ('expenses_fully_documented', 'organization', 'Despesas com comprovante',
   'Há pelo menos N despesas registradas e NENHUMA sem comprovante no cofre.',
   '{"min_count": 3}'),
  ('no_open_flagged_claim', 'organization', 'Nenhuma alegação marcada em aberto',
   'Nenhuma alegação da organização está marcada como grave sem revisão de outra organização.',
   'sem parâmetros'),
  ('substantiated_claims', 'organization', 'Alegações sustentadas',
   'Há pelo menos N alegações verificadas cuja situação derivada é "sustentada".',
   '{"min_count": 1}'),
  ('materiality_published', 'organization', 'Materialidade publicada',
   'Existe avaliação de materialidade publicada, com lente e limiar declarados.',
   'sem parâmetros'),
  ('framework_mapping_verified', 'organization', 'Mapeamento de referencial verificado',
   'Há pelo menos N mapeamentos de indicador com relação "verified" (revisados por outra '
   'organização).', '{"min_count": 1}'),
  ('equity_context_declared', 'project', 'Contexto de equidade declarado',
   'O projeto declara necessidade e adicionalidade, e tem denominador vigente com fonte, data e '
   'método.', 'sem parâmetros'),
  ('validated_causality', 'project', 'Causalidade validada na cadeia',
   'A cadeia de resultado do projeto tem pelo menos N elos de causalidade validada (que já exigem '
   'evidência e revisor externo).', '{"min_count": 1}'),
  ('indicator_baseline_sourced', 'project', 'Linha de base com fonte',
   'Todo indicador do projeto que declara linha de base declara também a fonte dela.',
   'sem parâmetros'),
  ('project_completed', 'project', 'Projeto concluído',
   'O projeto está com situação "completed".', 'sem parâmetros');

-- ============================================================================= 2. definição versionada
CREATE TABLE seal_definitions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code        text NOT NULL CHECK (code ~ '^[a-z][a-z0-9_]{3,50}$'),
  version     integer NOT NULL CHECK (version > 0),
  scope       text NOT NULL CHECK (scope IN ('organization','project')),
  title       text NOT NULL CHECK (length(btrim(title)) BETWEEN 5 AND 200),
  what_it_attests text NOT NULL CHECK (length(btrim(what_it_attests)) BETWEEN 20 AND 2000),
  -- A parte que ninguém escreve e que é a mais importante num selo.
  what_it_does_not_attest text NOT NULL
    CHECK (length(btrim(what_it_does_not_attest)) BETWEEN 20 AND 2000),
  validity_days integer NOT NULL CHECK (validity_days BETWEEN 30 AND 1095),
  status      text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','retired')),
  published_at timestamptz,
  retired_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (code, version),
  CONSTRAINT published_has_date CHECK (status <> 'published' OR published_at IS NOT NULL)
);
COMMENT ON TABLE seal_definitions IS
  'Definição de selo, versionada. Publicada, é IMUTÁVEL: mudar critério exige versão nova, porque '
  'selo cujo critério muda em silêncio não atesta nada.';
CREATE UNIQUE INDEX ux_seal_definition_current ON seal_definitions(code)
  WHERE status = 'published';
CREATE TRIGGER trg_seal_definitions_touch BEFORE UPDATE ON seal_definitions
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE seal_criteria (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  definition_id uuid NOT NULL REFERENCES seal_definitions(id) ON DELETE CASCADE,
  rule_code     text NOT NULL REFERENCES seal_rules(code) ON DELETE RESTRICT,
  params        jsonb NOT NULL DEFAULT '{}'::jsonb,
  position      integer NOT NULL,
  UNIQUE (definition_id, rule_code)
);
COMMENT ON TABLE seal_criteria IS
  'Os critérios de uma definição, como LINHAS: ficam auditáveis e aparecem na resposta pública do '
  'selo. Critério em jsonb solto seria critério que ninguém lê.';

-- Definição publicada não muda, e critério de definição publicada não muda.
CREATE FUNCTION seal_definition_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'published' AND NEW.status = 'published'
     AND (NEW.code, NEW.version, NEW.scope, NEW.title, NEW.what_it_attests,
          NEW.what_it_does_not_attest, NEW.validity_days)
      IS DISTINCT FROM
         (OLD.code, OLD.version, OLD.scope, OLD.title, OLD.what_it_attests,
          OLD.what_it_does_not_attest, OLD.validity_days) THEN
    RAISE EXCEPTION 'definição de selo publicada é imutável: publique uma VERSÃO nova. Selo cujo '
                    'critério muda em silêncio não atesta nada' USING ERRCODE = '42501';
  END IF;
  IF OLD.status = 'published' AND NEW.status = 'draft' THEN
    RAISE EXCEPTION 'definição publicada não volta a rascunho' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_seal_definition_frozen BEFORE UPDATE ON seal_definitions
  FOR EACH ROW EXECUTE FUNCTION seal_definition_frozen();

CREATE FUNCTION seal_criteria_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_status text;
BEGIN
  SELECT status INTO v_status FROM seal_definitions
   WHERE id = coalesce(NEW.definition_id, OLD.definition_id);
  IF v_status <> 'draft' THEN
    RAISE EXCEPTION 'critério de definição já publicada não muda: publique uma versão nova'
      USING ERRCODE = '42501';
  END IF;
  RETURN coalesce(NEW, OLD);
END $$;
CREATE TRIGGER trg_seal_criteria_frozen BEFORE INSERT OR UPDATE OR DELETE ON seal_criteria
  FOR EACH ROW EXECUTE FUNCTION seal_criteria_frozen();

-- ============================================================================= 3. a avaliação EM SQL
--
-- Uma linha por critério: satisfeito ou não, com detalhe legível e a data em que o critério
-- expira (quando houver). A validade do selo é o MENOR entre a validade da definição e as datas
-- que os critérios impõem — selo que vale mais que o documento que o sustenta é selo falso.
CREATE FUNCTION seal_evaluate(p_definition uuid, p_subject uuid)
  RETURNS TABLE (rule_code text, met boolean, detail text, expires_on date)
  LANGUAGE plpgsql STABLE AS $$
DECLARE
  c record;
  v_scope text;
  v_org uuid;
  v_min integer;
  v_n integer;
  v_total integer;
  v_date date;
  v_txt text;
BEGIN
  SELECT scope INTO v_scope FROM seal_definitions WHERE id = p_definition;
  IF v_scope IS NULL THEN
    RAISE EXCEPTION 'definição de selo inexistente' USING ERRCODE = '23503';
  END IF;
  IF v_scope = 'project' THEN
    SELECT p.org_id INTO v_org FROM projects p WHERE p.id = p_subject;
  ELSE
    v_org := p_subject;
  END IF;

  FOR c IN SELECT sc.rule_code, sc.params FROM seal_criteria sc
            WHERE sc.definition_id = p_definition ORDER BY sc.position LOOP
    v_min := coalesce((c.params->>'min_count')::integer, 1);
    met := false; detail := ''; expires_on := NULL; rule_code := c.rule_code;

    IF c.rule_code = 'compliance_approved' THEN
      SELECT o.compliance_status INTO v_txt FROM organizations o WHERE o.id = v_org;
      met := v_txt = 'approved';
      detail := 'compliance: ' || coalesce(v_txt, 'desconhecido');

    ELSIF c.rule_code = 'documents_validated' THEN
      SELECT count(*), min(d.valid_until) INTO v_n, v_date
        FROM jsonb_array_elements_text(coalesce(c.params->'doc_types', '[]'::jsonb)) t(dt)
        JOIN documents d ON d.org_id = v_org AND d.doc_type = t.dt
         AND d.deleted_at IS NULL AND d.validation_status = 'validated'
         AND (d.valid_until IS NULL OR d.valid_until >= current_date);
      SELECT count(*) INTO v_total
        FROM jsonb_array_elements_text(coalesce(c.params->'doc_types', '[]'::jsonb)) t(dt);
      met := v_total > 0 AND v_n >= v_total;
      expires_on := v_date;
      detail := v_n || ' de ' || v_total || ' tipo(s) de documento validado(s) e vigente(s)';

    ELSIF c.rule_code = 'measurements_with_evidence' THEN
      SELECT count(*) INTO v_n FROM indicator_values iv
       WHERE iv.org_id = v_org AND iv.status = 'validated' AND iv.evidence_id IS NOT NULL;
      met := v_n >= v_min;
      detail := v_n || ' medição(ões) validada(s) com evidência (mínimo ' || v_min || ')';

    ELSIF c.rule_code = 'expenses_fully_documented' THEN
      SELECT count(*), count(*) FILTER (WHERE e.document_id IS NULL) INTO v_total, v_n
        FROM expenses e WHERE e.org_id = v_org;
      met := v_total >= v_min AND v_n = 0;
      detail := v_total || ' despesa(s), ' || v_n || ' sem comprovante';

    ELSIF c.rule_code = 'no_open_flagged_claim' THEN
      SELECT count(*) INTO v_n FROM claims cl
        CROSS JOIN LATERAL claim_status(cl.id) s
       WHERE cl.org_id = v_org AND cl.withdrawn_at IS NULL AND s.status = 'flagged';
      met := v_n = 0;
      detail := v_n || ' alegação(ões) marcada(s) sem revisão';

    ELSIF c.rule_code = 'substantiated_claims' THEN
      SELECT count(*) INTO v_n FROM claims cl
        CROSS JOIN LATERAL claim_status(cl.id) s
       WHERE cl.org_id = v_org AND cl.withdrawn_at IS NULL AND s.status = 'substantiated';
      met := v_n >= v_min;
      detail := v_n || ' alegação(ões) sustentada(s) (mínimo ' || v_min || ')';

    ELSIF c.rule_code = 'materiality_published' THEN
      SELECT count(*) INTO v_n FROM materiality_assessments ma
       WHERE ma.org_id = v_org AND ma.status = 'published';
      met := v_n >= v_min;
      detail := v_n || ' avaliação(ões) de materialidade publicada(s)';

    ELSIF c.rule_code = 'framework_mapping_verified' THEN
      SELECT count(*) INTO v_n FROM framework_mappings fm
       WHERE fm.org_id = v_org AND fm.relation = 'verified';
      met := v_n >= v_min;
      detail := v_n || ' mapeamento(s) verificado(s) (mínimo ' || v_min || ')';

    ELSIF c.rule_code = 'equity_context_declared' THEN
      SELECT count(*) INTO v_n FROM equity_contexts ec WHERE ec.project_id = p_subject;
      SELECT count(*) INTO v_total FROM equity_denominators ed
       WHERE ed.effective_until IS NULL
         AND ((ed.scope = 'project' AND ed.project_id = p_subject)
           OR (ed.scope = 'territory' AND ed.territory =
               (SELECT p.territory FROM projects p WHERE p.id = p_subject)));
      met := v_n > 0 AND v_total > 0;
      detail := CASE WHEN v_n = 0 THEN 'sem contexto de equidade declarado'
                     WHEN v_total = 0 THEN 'sem denominador vigente com fonte'
                     ELSE 'contexto declarado e ' || v_total || ' denominador(es) vigente(s)' END;

    ELSIF c.rule_code = 'validated_causality' THEN
      SELECT count(*) INTO v_n FROM impact_edges ie
       WHERE ie.project_id = p_subject AND ie.link_type = 'validated_causality';
      met := v_n >= v_min;
      detail := v_n || ' elo(s) de causalidade validada (mínimo ' || v_min || ')';

    ELSIF c.rule_code = 'indicator_baseline_sourced' THEN
      SELECT count(*) INTO v_n FROM project_indicators pi
       WHERE pi.project_id = p_subject AND pi.baseline IS NOT NULL
         AND pi.baseline_source IS NULL;
      SELECT count(*) INTO v_total FROM project_indicators pi WHERE pi.project_id = p_subject;
      met := v_total > 0 AND v_n = 0;
      detail := v_total || ' indicador(es), ' || v_n || ' com linha de base sem fonte';

    ELSIF c.rule_code = 'project_completed' THEN
      SELECT p.status INTO v_txt FROM projects p WHERE p.id = p_subject;
      met := v_txt = 'completed';
      detail := 'situação do projeto: ' || coalesce(v_txt, 'desconhecida');

    ELSE
      RAISE EXCEPTION 'critério de selo sem implementação: %', c.rule_code USING ERRCODE = '42501';
    END IF;

    RETURN NEXT;
  END LOOP;
END $$;
COMMENT ON FUNCTION seal_evaluate IS
  'Avalia os critérios de uma definição CONTRA OS FATOS, em SQL. É o que torna o selo '
  'infalsificável pela aplicação: app_award_seal() chama esta função e recusa conceder quando algum '
  'critério não está satisfeito.';

-- ============================================================================= 4. concessão
CREATE TABLE seal_awards (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  definition_id uuid NOT NULL REFERENCES seal_definitions(id) ON DELETE RESTRICT,
  scope         text NOT NULL CHECK (scope IN ('organization','project')),
  subject_id    uuid NOT NULL,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  evidence      jsonb NOT NULL,
  expires_on    date NOT NULL,
  engine_version text NOT NULL,
  awarded_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT evidence_not_empty CHECK (jsonb_typeof(evidence) = 'array'
                                       AND jsonb_array_length(evidence) > 0)
);
COMMENT ON TABLE seal_awards IS
  'Concessão de selo, append-only. Só é escrita por app_award_seal(), que reavalia os critérios no '
  'banco antes de inserir. `evidence` guarda o que cada critério encontrou no momento da '
  'concessão: é o que permite conferir depois.';
CREATE INDEX ix_seal_awards_subject ON seal_awards(scope, subject_id, awarded_at DESC);
CREATE INDEX ix_seal_awards_org ON seal_awards(org_id, awarded_at DESC);
CREATE TRIGGER trg_seal_awards_append BEFORE UPDATE OR DELETE ON seal_awards
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE TABLE seal_revocations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  award_id   uuid NOT NULL REFERENCES seal_awards(id) ON DELETE CASCADE,
  reason     text NOT NULL CHECK (reason IN ('criterion_no_longer_met','definition_retired',
                                             'data_correction','request_of_holder','misconduct')),
  detail     text NOT NULL CHECK (length(btrim(detail)) BETWEEN 10 AND 2000),
  revoked_by uuid REFERENCES users(id) ON DELETE SET NULL,
  revoked_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (award_id)
);
COMMENT ON TABLE seal_revocations IS
  'Revogação como FATO NOVO, append-only e com motivo. Perder o selo não apaga que ele existiu, e a '
  'verificação pública mostra a revogação em vez de simplesmente não encontrar nada.';
CREATE TRIGGER trg_seal_revocations_append BEFORE UPDATE OR DELETE ON seal_revocations
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- A avaliação que NÃO concede também fica registrada: "por que eu não recebi" é a pergunta mais
-- legítima que existe sobre um selo.
CREATE TABLE seal_evaluations (
  id            bigserial PRIMARY KEY,
  definition_id uuid NOT NULL REFERENCES seal_definitions(id) ON DELETE CASCADE,
  scope         text NOT NULL,
  subject_id    uuid NOT NULL,
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  all_met       boolean NOT NULL,
  detail        jsonb NOT NULL,
  engine_version text NOT NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_seal_evaluations ON seal_evaluations(org_id, created_at DESC);
CREATE TRIGGER trg_seal_evaluations_append BEFORE UPDATE OR DELETE ON seal_evaluations
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE FUNCTION app_award_seal(p_definition uuid, p_subject uuid, p_engine text)
  RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  v_scope text;
  v_validity integer;
  v_status text;
  v_org uuid;
  v_unmet text;
  v_evidence jsonb;
  v_expires date;
  v_id uuid;
BEGIN
  SELECT scope, validity_days, status INTO v_scope, v_validity, v_status
    FROM seal_definitions WHERE id = p_definition;
  IF v_scope IS NULL THEN
    RAISE EXCEPTION 'definição de selo inexistente' USING ERRCODE = '23503';
  END IF;
  IF v_status <> 'published' THEN
    RAISE EXCEPTION 'selo só é concedido por definição PUBLICADA: rascunho não atesta nada'
      USING ERRCODE = '42501';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM seal_criteria WHERE definition_id = p_definition) THEN
    RAISE EXCEPTION 'definição sem critério não concede selo' USING ERRCODE = '42501';
  END IF;
  IF v_scope = 'project' THEN
    SELECT org_id INTO v_org FROM projects WHERE id = p_subject;
  ELSE
    SELECT id INTO v_org FROM organizations WHERE id = p_subject;
  END IF;
  IF v_org IS NULL THEN
    RAISE EXCEPTION 'sujeito do selo inexistente' USING ERRCODE = '23503';
  END IF;

  SELECT jsonb_agg(jsonb_build_object('rule_code', e.rule_code, 'met', e.met,
                                      'detail', e.detail, 'expires_on', e.expires_on)
                   ORDER BY e.rule_code),
         min(e.expires_on),
         string_agg(CASE WHEN NOT e.met THEN e.rule_code || ' (' || e.detail || ')' END,
                    '; ' ORDER BY e.rule_code)
    INTO v_evidence, v_expires, v_unmet
    FROM seal_evaluate(p_definition, p_subject) e;

  INSERT INTO seal_evaluations(definition_id, scope, subject_id, org_id, all_met, detail,
                               engine_version)
  VALUES (p_definition, v_scope, p_subject, v_org, v_unmet IS NULL, v_evidence, p_engine);

  -- A recusa NÃO levanta exceção, e isso é deliberado: exceção aqui desfaria a transação inteira e
  -- levaria embora o registro da avaliação que acabou de ser gravado — justamente o registro que
  -- responde "por que eu não recebi". Devolve NULL, e quem chamou transforma em 422 depois do
  -- COMMIT. O primeiro teste desta fase pegou exatamente isso.
  IF v_unmet IS NOT NULL THEN
    RETURN NULL;
  END IF;

  -- A validade é o MENOR entre a da definição e as datas que os critérios impõem: selo que vale
  -- mais que o documento que o sustenta é selo falso.
  v_expires := least(coalesce(v_expires, current_date + v_validity),
                     current_date + v_validity);

  INSERT INTO seal_awards(definition_id, scope, subject_id, org_id, evidence, expires_on,
                          engine_version)
  VALUES (p_definition, v_scope, p_subject, v_org, v_evidence, v_expires, p_engine)
  RETURNING id INTO v_id;
  RETURN v_id;
END $$;
COMMENT ON FUNCTION app_award_seal IS
  'Único caminho de concessão. Reavalia os critérios em SQL e RECUSA quando algum não está '
  'satisfeito, devolvendo NULL (e não exceção, que desfaria o registro da avaliação). A aplicação '
  'não tem INSERT em seal_awards, então não existe rota capaz de conceder selo sem critério.';

-- ============================================================================= 5. situação derivada
CREATE FUNCTION seal_status(p_award uuid)
  RETURNS TABLE (status text, expires_on date, revoked_at timestamptz, revocation_reason text)
  LANGUAGE sql STABLE AS $$
  SELECT CASE
           WHEN r.id IS NOT NULL THEN 'revoked'
           WHEN a.expires_on < current_date THEN 'expired'
           -- "superada" vem ANTES de "aposentada" porque é mais informativa: publicar a versão
           -- nova aposenta a anterior, e dizer só "aposentada" esconderia que existe versão nova.
           WHEN EXISTS (SELECT 1 FROM seal_definitions n
                         WHERE n.code = d.code AND n.version > d.version
                           AND n.status = 'published') THEN 'superseded_definition'
           WHEN d.status = 'retired' THEN 'definition_retired'
           ELSE 'active' END,
         a.expires_on, r.revoked_at, r.reason
    FROM seal_awards a
    JOIN seal_definitions d ON d.id = a.definition_id
    LEFT JOIN seal_revocations r ON r.award_id = a.id
   WHERE a.id = p_award
$$;
COMMENT ON FUNCTION seal_status IS
  'Situação DERIVADA: revogado, expirado, de definição aposentada, superado por versão nova, ou '
  'ativo. Não existe coluna de situação em seal_awards.';

-- ============================================================================= 6. RLS
ALTER TABLE seal_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE seal_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE seal_criteria ENABLE ROW LEVEL SECURITY;
ALTER TABLE seal_awards ENABLE ROW LEVEL SECURITY;
ALTER TABLE seal_revocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE seal_evaluations ENABLE ROW LEVEL SECURITY;

-- Regra, definição e critério são abertos: selo cujo critério não pode ser lido não serve para
-- conferir nada. Rascunho de definição também é legível, de propósito — assim ninguém é pego de
-- surpresa por um critério novo, e `status` diz que é rascunho.
CREATE POLICY seal_rules_read ON seal_rules FOR SELECT USING (true);
CREATE POLICY seal_definitions_read ON seal_definitions FOR SELECT USING (true);
CREATE POLICY seal_criteria_read ON seal_criteria FOR SELECT USING (true);

-- Definição é ato da plataforma.
CREATE POLICY seal_definitions_write ON seal_definitions FOR INSERT WITH CHECK (app_priv());
CREATE POLICY seal_definitions_update ON seal_definitions FOR UPDATE
  USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY seal_criteria_write ON seal_criteria FOR INSERT WITH CHECK (app_priv());
CREATE POLICY seal_criteria_delete ON seal_criteria FOR DELETE USING (app_priv());

-- Concessão é pública: é o ponto do selo.
CREATE POLICY seal_awards_read ON seal_awards FOR SELECT USING (true);
CREATE POLICY seal_revocations_read ON seal_revocations FOR SELECT USING (true);
CREATE POLICY seal_revocations_write ON seal_revocations FOR INSERT WITH CHECK (app_priv());

-- A avaliação é da organização avaliada (e da administração): é o "por que não recebi".
CREATE POLICY seal_evaluations_read ON seal_evaluations FOR SELECT
  USING (org_id = app_org() OR app_priv());

GRANT SELECT ON seal_rules, seal_definitions, seal_criteria, seal_awards, seal_revocations,
                seal_evaluations TO impacto_app;
GRANT INSERT, UPDATE ON seal_definitions TO impacto_app;
GRANT INSERT, DELETE ON seal_criteria TO impacto_app;
GRANT INSERT ON seal_revocations TO impacto_app;
GRANT EXECUTE ON FUNCTION app_award_seal(uuid, uuid, text) TO impacto_app;
GRANT EXECUTE ON FUNCTION seal_evaluate(uuid, uuid) TO impacto_app;
REVOKE INSERT, UPDATE, DELETE ON seal_awards FROM impacto_app;
REVOKE UPDATE, DELETE ON seal_revocations, seal_evaluations FROM impacto_app;
