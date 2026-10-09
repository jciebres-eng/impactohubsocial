-- 0070 — v0.30.0: evidência como objeto de primeira classe (ADR-360).
--
-- O que já existia (0001/0002): evidência ligada a projeto/marco/candidatura, tipo, título, data, documento (com SHA-256 em
-- documents), status submitted/accepted/rejected/needs_info, revisão por financiador/governo com nota, RLS, quatro olhos
-- (a executora não revisa o próprio registro — guard_self_review), trilha no ledger. O que faltava e esta migração
-- acrescenta, aplicado PELO BANCO:
--   1. ORIGEM E USO: método de coleta, nível de acesso, base de consentimento, classe de retenção — campos declarados por quem
--      envia (valores fechados; 'unknown' é estado válido e visível, nunca é convertido em "ok");
--   2. VERSÃO E SUBSTITUIÇÃO: version + supersedes_id; a evidência substituída vira 'superseded' (terminal) e continua legível;
--   3. CONTESTAÇÃO: a executora pode contestar uma rejeição ('contested', motivo obrigatório); quem revisa decide
--      ('under_review' → accepted/rejected) com justificativa obrigatória; rejeitar SEMPRE exige motivo (CHECK);
--   4. HISTÓRICO PRÓPRIO (evidence_events, append-only): de → para, ator, motivo, data — além do ledger e da auditoria;
--   5. nada aqui afirma veracidade: o hash do documento prova integridade do arquivo referenciado, não o fato.

-- ============================================================================ 1. campos de origem e uso
ALTER TABLE evidences
  ADD COLUMN method          text NOT NULL DEFAULT 'unknown'
    CHECK (method IN ('direct_observation','document','self_report','third_party','sensor_or_system','interview','sample','unknown')),
  ADD COLUMN access_level    text NOT NULL DEFAULT 'parties'
    CHECK (access_level IN ('public','parties','restricted')),
  ADD COLUMN consent_basis   text NOT NULL DEFAULT 'unknown'
    CHECK (consent_basis IN ('not_personal','consent','legal_obligation','public_interest','legitimate_interest','unknown')),
  ADD COLUMN retention_class text NOT NULL DEFAULT 'project'
    CHECK (retention_class IN ('project','accountability','legal_hold')),
  ADD COLUMN version         integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  ADD COLUMN supersedes_id   uuid REFERENCES evidences(id) ON DELETE RESTRICT,
  ADD COLUMN superseded_by   uuid REFERENCES evidences(id) ON DELETE RESTRICT,
  ADD COLUMN contest_reason  text CHECK (length(contest_reason) BETWEEN 10 AND 2000),
  ADD COLUMN contested_at    timestamptz,
  ADD COLUMN contested_by    uuid REFERENCES users(id),
  ADD COLUMN updated_at      timestamptz NOT NULL DEFAULT now();

ALTER TABLE evidences DROP CONSTRAINT evidences_status_check;
ALTER TABLE evidences ADD CONSTRAINT evidences_status_check
  CHECK (status IN ('submitted','needs_info','accepted','rejected','contested','under_review','superseded'));
-- rejeição e contestação sempre têm motivo escrito
ALTER TABLE evidences ADD CONSTRAINT evidences_rejection_has_reason
  CHECK (status <> 'rejected' OR (review_note IS NOT NULL AND length(review_note) >= 10));
ALTER TABLE evidences ADD CONSTRAINT evidences_contest_has_reason
  CHECK (status NOT IN ('contested','under_review') OR contest_reason IS NOT NULL);
ALTER TABLE evidences ADD CONSTRAINT evidences_superseded_has_successor
  CHECK ((status = 'superseded') = (superseded_by IS NOT NULL));
CREATE INDEX ix_evidences_supersedes ON evidences(supersedes_id) WHERE supersedes_id IS NOT NULL;
CREATE TRIGGER trg_touch BEFORE UPDATE ON evidences FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ============================================================================ 2. histórico próprio, append-only
CREATE TABLE evidence_events (
  id            bigserial PRIMARY KEY,
  evidence_id   uuid NOT NULL REFERENCES evidences(id) ON DELETE RESTRICT,
  project_id    uuid NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  from_status   text,
  to_status     text NOT NULL,
  actor_id      uuid REFERENCES users(id),
  actor_org_id  uuid REFERENCES organizations(id),
  reason        text CHECK (length(reason) <= 2000),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_evidence_events ON evidence_events(evidence_id, created_at);
CREATE TRIGGER trg_evidence_events_append_only BEFORE UPDATE OR DELETE ON evidence_events FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ============================================================================ 3. máquina de estados e guardas
-- Transições permitidas (quem pode está na API e na RLS; o banco garante o grafo):
--   submitted  → accepted | rejected | needs_info | superseded
--   needs_info → submitted (nova informação) | accepted | rejected | superseded
--   rejected   → contested | superseded
--   contested  → under_review | superseded
--   under_review → accepted | rejected
--   accepted   → superseded
--   superseded → (terminal)
CREATE FUNCTION evidence_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF NEW.status IS NOT DISTINCT FROM OLD.status THEN
    -- campos de identidade e de origem não mudam depois de enviados (substituir = nova evidência)
    IF NEW.document_id IS DISTINCT FROM OLD.document_id OR NEW.kind <> OLD.kind OR NEW.project_id <> OLD.project_id
       OR NEW.version <> OLD.version OR NEW.supersedes_id IS DISTINCT FROM OLD.supersedes_id THEN
      RAISE EXCEPTION 'evidência não é editada depois de enviada: envie uma nova versão' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
  END IF;
  IF OLD.status = 'superseded' THEN
    RAISE EXCEPTION 'evidência substituída é terminal' USING ERRCODE = '23514';
  END IF;
  ok := CASE OLD.status
    WHEN 'submitted'    THEN NEW.status IN ('accepted','rejected','needs_info','superseded')
    WHEN 'needs_info'   THEN NEW.status IN ('submitted','accepted','rejected','superseded')
    WHEN 'rejected'     THEN NEW.status IN ('contested','superseded')
    WHEN 'contested'    THEN NEW.status IN ('under_review','superseded')
    WHEN 'under_review' THEN NEW.status IN ('accepted','rejected')
    WHEN 'accepted'     THEN NEW.status IN ('superseded')
    ELSE false END;
  IF NOT ok THEN
    RAISE EXCEPTION 'transição de evidência não permitida: % → %', OLD.status, NEW.status USING ERRCODE = '23514';
  END IF;
  INSERT INTO evidence_events(evidence_id, project_id, from_status, to_status, actor_id, actor_org_id, reason)
  VALUES (NEW.id, NEW.project_id, OLD.status, NEW.status, app_uid(),
          CASE WHEN app_org() IS NULL THEN NULL ELSE app_org() END,
          CASE WHEN NEW.status IN ('contested','under_review') THEN NEW.contest_reason ELSE NEW.review_note END);
  RETURN NEW;
END $$;
CREATE TRIGGER trg_evidence_state BEFORE UPDATE ON evidences FOR EACH ROW EXECUTE FUNCTION evidence_state_guard();

-- a contestação é da executora (ou administração); a revisão continua vedada a ela (guard_self_review já existe)
CREATE FUNCTION evidence_contest_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  IF NEW.status = 'contested' AND OLD.status <> 'contested' AND app_org() IS DISTINCT FROM NEW.org_id THEN
    RAISE EXCEPTION 'só a organização executora contesta a própria evidência' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_evidence_contest BEFORE UPDATE ON evidences FOR EACH ROW EXECUTE FUNCTION evidence_contest_guard();

-- o evento inicial (envio) também fica no histórico
CREATE FUNCTION evidence_insert_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO evidence_events(evidence_id, project_id, from_status, to_status, actor_id, actor_org_id, reason)
  VALUES (NEW.id, NEW.project_id, NULL, NEW.status, COALESCE(NEW.created_by, app_uid()), NEW.org_id,
          CASE WHEN NEW.supersedes_id IS NOT NULL THEN 'substitui evidência anterior' ELSE NULL END);
  RETURN NEW;
END $$;
CREATE TRIGGER trg_evidence_insert_event AFTER INSERT ON evidences FOR EACH ROW EXECUTE FUNCTION evidence_insert_event();

-- ============================================================================ 4. RLS e grants
ALTER TABLE evidence_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY evidence_events_read ON evidence_events FOR SELECT USING (
  EXISTS (SELECT 1 FROM evidences e WHERE e.id = evidence_events.evidence_id
          AND (e.org_id = app_org() OR app_project_investor(e.project_id) OR app_project_party(e.project_id) OR app_priv())));
CREATE POLICY evidence_events_insert ON evidence_events FOR INSERT WITH CHECK (true);   -- só o gatilho insere; UPDATE/DELETE proibidos
GRANT SELECT, INSERT ON evidence_events TO impacto_app;
GRANT USAGE ON SEQUENCE evidence_events_id_seq TO impacto_app;

-- ============================================================================ 5. trilha: tipos de lançamento novos (lista completa repetida: o CHECK é substituído inteiro)
ALTER TABLE ledger_entries DROP CONSTRAINT IF EXISTS ledger_entries_entry_type_check;
ALTER TABLE ledger_entries ADD CONSTRAINT ledger_entries_entry_type_check CHECK (entry_type IN (
  'need_published','budget_defined','milestone_defined','interest_registered','application_submitted',
  'application_approved','funding_committed','disbursement_reported','disbursement_confirmed',
  'expense_recorded','evidence_submitted','evidence_reviewed','result_reported','report_submitted',
  'feedback_given','professional_signature','project_completed','refund_completed','payment_disputed',
  'indicator_validated','procurement_decided','project_created','idea_promoted','status_changed',
  'diagnosis_created','diagnosis_revised','action_created','action_completed','goal_created',
  'document_generated','document_approved','document_signed','opportunity_matched','match_feedback',
  'partner_added','submission_created','submission_sent','risk_created','risk_resolved','snapshot_taken',
  'project_archived','relationship_created','relationship_ended','proposal_sent','proposal_viewed',
  'proposal_accepted','proposal_declined','proposal_changes_requested','proposal_withdrawn',
  'listing_published','listing_paused','investment_intent','investment_committed',
  'impact_update_submitted','impact_update_accepted','impact_update_changes_requested','impact_update_published',
  'conversation_started','enforcement_applied','experience_confirmed','team_member_added','team_member_removed','correction',
  'agreement_activated','allocation_computed','milestone_delivered','milestone_accepted','milestone_rejected',
  'obligation_overdue',
  -- v0.27.0
  'participation_proposed','participation_accepted','participation_consolidated','participation_validated',
  'payout_instructed','payout_registered','payout_confirmed','payout_reconciled','operation_settled','recognition_granted',
  -- v0.30.0 (ADR-360)
  'evidence_contested','evidence_superseded'));


-- ============================================================================ 6. auditoria
-- (evidence_events referencia evidências por FK direta; nada polimórfico a declarar) — prefixo de auditoria já coberto por 'execution'
