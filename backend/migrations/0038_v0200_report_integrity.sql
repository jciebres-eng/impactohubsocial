-- v0.20.0 — a separação entre DENÚNCIA, SUSPEITA, INFRAÇÃO COMPROVADA e CONSEQUÊNCIA JURÍDICA.
--
-- O PROBLEMA QUE ESTA MIGRAÇÃO RESOLVE
--
-- A plataforma tinha quatro coisas diferentes tratadas com o mesmo vocabulário pobre:
--
--   * `reports.status` com quatro valores (`open`, `triaged`, `actioned`, `dismissed`) misturava
--     ANDAMENTO com CONCLUSÃO: "actioned" dizia que alguém agiu, e não dizia se a denúncia procedia;
--   * não havia como registrar que a análise CONCLUIU PELA IMPROCEDÊNCIA — "dismissed" cobre tanto
--     "não procede" quanto "não vamos analisar", que são coisas opostas para quem foi denunciado;
--   * não havia direito de resposta: o denunciado não era ouvido em lugar nenhum;
--   * e `enforcement_actions.report_id` aceitava QUALQUER denúncia, inclusive uma recém-aberta —
--     ou seja, o banco permitia aplicar uma sanção a partir de uma acusação não apurada.
--
-- Essa última é a que importa mais. Num produto cuja tese é evidência, um sistema de reputação e
-- sanção que pode ser acionado por denúncia não apurada vira máquina de acusação: basta denunciar
-- para causar efeito. A trava agora é do BANCO, não da boa vontade da rota.
--
-- O QUE CONTINUA VALENDO (e esta migração reforça)
--
--   DENÚNCIA          alguém afirma. Peso zero por si só.
--   SUSPEITA          a plataforma tem indício (detector automático ou denúncia triada). Não é achado.
--   INFRAÇÃO          pessoa humana analisou, com fundamentação, e concluiu. SÓ ISTO autoriza medida.
--   CONSEQUÊNCIA      a plataforma NÃO declara crime. Registra que o caso pode exigir autoridade
--   JURÍDICA          externa e encaminha. Quem decide é o Judiciário, o MP ou o órgão competente.

-- ============================================================ 1. situação: andamento ≠ conclusão
ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_status_check;

UPDATE reports SET status = CASE status
  WHEN 'open'     THEN 'reported'
  WHEN 'triaged'  THEN 'under_review'
  WHEN 'actioned' THEN 'resolved'
  ELSE status END;

ALTER TABLE reports ALTER COLUMN status SET DEFAULT 'reported';
ALTER TABLE reports ADD CONSTRAINT reports_status_check CHECK (status IN (
  'reported',               -- registrada, ninguém olhou ainda
  'under_review',           -- em análise humana (SUSPEITA, não achado)
  'information_requested',  -- o denunciado foi chamado a se manifestar
  'substantiated',          -- a análise concluiu que PROCEDE
  'unsubstantiated',        -- a análise concluiu que NÃO procede
  'dismissed',              -- arquivada sem análise de mérito (fora de escopo, duplicada, vazia)
  'appealed',               -- quem foi afetado pediu revisão da conclusão
  'resolved'                -- encerrada depois da conclusão e das providências
));

COMMENT ON COLUMN reports.status IS
  'ANDAMENTO da denúncia. Não confundir com `finding`, que é a CONCLUSÃO. '
  '`dismissed` (arquivada sem mérito) é diferente de `unsubstantiated` (analisada e não procede): '
  'para quem foi denunciado, a segunda é uma absolvição e a primeira não é nada.';

-- ============================================================ 2. a conclusão, separada e fundamentada
ALTER TABLE reports ADD COLUMN finding text
  CHECK (finding IS NULL OR finding IN ('substantiated','unsubstantiated'));
ALTER TABLE reports ADD COLUMN assigned_reviewer uuid REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE reports ADD COLUMN decided_by uuid REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE reports ADD COLUMN decided_at timestamptz;
ALTER TABLE reports ADD COLUMN decision_rationale text
  CHECK (decision_rationale IS NULL OR length(decision_rationale) BETWEEN 20 AND 4000);
ALTER TABLE reports ADD COLUMN response_requested_at timestamptz;
ALTER TABLE reports ADD COLUMN target_org_id uuid REFERENCES organizations(id) ON DELETE CASCADE;

-- A conclusão nunca é um clique: exige quem concluiu, quando e POR QUÊ.
ALTER TABLE reports ADD CONSTRAINT report_finding_is_reasoned CHECK (
  finding IS NULL OR (decided_by IS NOT NULL AND decided_at IS NOT NULL
                      AND decision_rationale IS NOT NULL));
-- Situação de conclusão e campo de conclusão não podem divergir.
ALTER TABLE reports ADD CONSTRAINT report_status_matches_finding CHECK (
  (status = 'substantiated'   AND finding = 'substantiated')
  OR (status = 'unsubstantiated' AND finding = 'unsubstantiated')
  OR (status IN ('appealed','resolved') AND finding IS NOT NULL)
  OR (status IN ('reported','under_review','information_requested','dismissed') AND finding IS NULL));

COMMENT ON COLUMN reports.finding IS
  'CONCLUSÃO da análise humana. NULL enquanto não houver conclusão — e ausência de conclusão nunca '
  'é meia-culpa: é ausência. Só `substantiated` autoriza medida (ver trigger em enforcement_actions).';
COMMENT ON COLUMN reports.target_org_id IS
  'Organização afetada, resolvida na abertura. Existe para o DIREITO DE RESPOSTA: é por ela que o '
  'denunciado enxerga o que lhe é imputado — sem nunca enxergar quem denunciou.';

-- ============================================================ 3. consequência jurídica: encaminhar, não julgar
ALTER TABLE reports ADD COLUMN legal_referral boolean NOT NULL DEFAULT false;
ALTER TABLE reports ADD COLUMN legal_referral_note text
  CHECK (legal_referral_note IS NULL OR length(legal_referral_note) BETWEEN 20 AND 4000);
ALTER TABLE reports ADD CONSTRAINT report_referral_is_reasoned CHECK (
  NOT legal_referral OR legal_referral_note IS NOT NULL);

COMMENT ON COLUMN reports.legal_referral IS
  'POTENTIAL_LEGAL_ISSUE. Marca que o caso pode exigir autoridade externa (polícia, Ministério '
  'Público, Judiciário, órgão regulador, conselho profissional, autoridade fiscal). A plataforma '
  'NÃO declara crime, NÃO tipifica conduta e NÃO substitui nenhuma dessas instâncias: ela registra '
  'o encaminhamento, com fundamentação, para que uma pessoa competente decida.';

-- ============================================================ 4. categoria: um vocabulário só
-- Havia DOIS conjuntos de categorias: o CHECK da tabela (12 valores) e uma lista em Python exposta
-- por GET /v1/moderation/ladder (12 valores, cinco diferentes). Nenhuma rota escrevia a coluna, então
-- a divergência nunca apareceu — mas apareceria na primeira vez que alguém a usasse. Fica UM.
ALTER TABLE reports DROP CONSTRAINT IF EXISTS reports_category_check;
ALTER TABLE reports ADD CONSTRAINT reports_category_check CHECK (category IS NULL OR category IN (
  'fraud', 'abuse', 'harassment', 'hate_speech', 'impersonation', 'spam',
  'non_payment', 'unethical_conduct', 'conflict_of_interest', 'false_information',
  'data_misuse', 'illegal_content', 'child_safety', 'intellectual_property',
  'privacy', 'misinformation', 'other'));

-- ============================================================ 5. direito de resposta (contraditório)
CREATE TABLE report_responses (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  report_id  uuid NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
  org_id     uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  body       text NOT NULL CHECK (length(body) BETWEEN 20 AND 4000),
  document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE report_responses IS
  'Manifestação de quem foi denunciado. Append-only: a resposta dada não se reescreve depois da '
  'decisão. Quem responde NUNCA vê quem denunciou — a tabela não guarda nem expõe o denunciante.';
CREATE INDEX ix_report_responses_report ON report_responses(report_id, created_at);

CREATE TRIGGER trg_report_response_append BEFORE UPDATE OR DELETE ON report_responses
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

ALTER TABLE report_responses ENABLE ROW LEVEL SECURITY;
-- A organização denunciada lê e escreve a PRÓPRIA manifestação; a plataforma lê todas.
CREATE POLICY report_resp_read ON report_responses FOR SELECT
  USING (org_id = app_org() OR app_priv() OR app_system());
CREATE POLICY report_resp_write ON report_responses FOR INSERT
  WITH CHECK ((org_id = app_org() AND app_uid() IS NOT NULL) OR app_system());
GRANT SELECT, INSERT ON report_responses TO impacto_app;

-- ============================================================ 6. a trava que importa
-- Medida de moderação ligada a denúncia EXIGE denúncia comprovada. Sem isto, "denunciar" produziria
-- efeito — e o caminho mais barato para prejudicar um concorrente seria uma acusação.
CREATE FUNCTION enforcement_needs_substantiated_report() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_finding text; v_status text;
BEGIN
  IF NEW.report_id IS NULL THEN
    RETURN NEW;   -- medida de ofício (detector, auditoria, decisão administrativa): outro caminho
  END IF;
  SELECT finding, status INTO v_finding, v_status FROM reports WHERE id = NEW.report_id;
  IF v_finding IS DISTINCT FROM 'substantiated' THEN
    RAISE EXCEPTION 'medida não pode se apoiar em denúncia sem conclusão de procedência (situação: %)',
      coalesce(v_status, 'inexistente')
      USING ERRCODE = '23514',
            HINT = 'Conclua a análise com fundamentação antes de aplicar qualquer medida.';
  END IF;
  RETURN NEW;
END $$;
COMMENT ON FUNCTION enforcement_needs_substantiated_report IS
  'DENÚNCIA NÃO É CULPA. Uma medida só pode citar uma denúncia depois que a análise humana concluiu '
  'pela procedência, com fundamentação registrada. Medida de ofício (report_id nulo) segue possível '
  'e continua exigindo regra, motivo e proporcionalidade.';

CREATE TRIGGER trg_enforcement_needs_substantiated
  BEFORE INSERT OR UPDATE OF report_id ON enforcement_actions
  FOR EACH ROW EXECUTE FUNCTION enforcement_needs_substantiated_report();

-- ============================================================ 7. andamento não anda para trás
CREATE FUNCTION report_flow_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE allowed text[];
BEGIN
  IF NEW.status = OLD.status THEN
    RETURN NEW;
  END IF;
  allowed := CASE OLD.status
    WHEN 'reported'              THEN ARRAY['under_review','dismissed']
    WHEN 'under_review'          THEN ARRAY['information_requested','substantiated','unsubstantiated','dismissed']
    WHEN 'information_requested' THEN ARRAY['under_review','substantiated','unsubstantiated','dismissed']
    WHEN 'substantiated'         THEN ARRAY['appealed','resolved']
    WHEN 'unsubstantiated'       THEN ARRAY['appealed','resolved']
    WHEN 'appealed'              THEN ARRAY['substantiated','unsubstantiated','resolved']
    ELSE ARRAY[]::text[] END;
  IF NOT (NEW.status = ANY(allowed)) THEN
    RAISE EXCEPTION 'transição de denúncia não permitida: % -> %', OLD.status, NEW.status
      USING ERRCODE = '23514';
  END IF;
  -- A conclusão, uma vez registrada, não se reescreve em silêncio: muda por recurso (`appealed`).
  IF OLD.finding IS NOT NULL AND NEW.finding IS DISTINCT FROM OLD.finding
     AND OLD.status <> 'appealed' THEN
    RAISE EXCEPTION 'a conclusão só muda por recurso (appealed), nunca por reescrita'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
COMMENT ON FUNCTION report_flow_guard IS
  'O andamento segue um grafo declarado. Arquivada, comprovada ou não comprovada não voltam a '
  '"recém-registrada": quem foi denunciado tem direito a um histórico que não é reescrito.';

CREATE TRIGGER trg_report_flow BEFORE UPDATE ON reports
  FOR EACH ROW EXECUTE FUNCTION report_flow_guard();

-- ============================================================ 8. o denunciado enxerga o que lhe imputam
-- A política de leitura de `reports` só mostrava a denúncia a quem denunciou e à plataforma. O
-- denunciado passa a ver a SUA denúncia quando é chamado a se manifestar — e a visão nunca inclui o
-- denunciante, porque a coluna não entra na projeção servida pela rota (ver api/report_routes.py).
CREATE POLICY reports_target_read ON reports FOR SELECT
  USING (target_org_id = app_org() AND status IN ('information_requested','substantiated',
                                                  'unsubstantiated','appealed','resolved'));

CREATE INDEX ix_reports_target_org ON reports(target_org_id, status)
  WHERE target_org_id IS NOT NULL;
CREATE INDEX ix_reports_finding ON reports(finding) WHERE finding IS NOT NULL;
