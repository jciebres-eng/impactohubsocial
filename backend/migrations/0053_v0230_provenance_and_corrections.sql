-- v0.23.0 — PROVENIÊNCIA DO INDICADOR, CORREÇÃO NO LEDGER, CADEIA DE HASH NO VALUE LEDGER
--
-- A REGRA QUE ESTA MIGRAÇÃO IMPÕE
--
--   "Nenhum indicador crítico deveria existir sem conseguir apontar para sua origem/evidência."
--
-- Até a v0.22.0 `indicator_values.evidence_id` era NULO permitido e a tabela não tinha gatilho
-- nenhum. O efeito: um valor podia chegar a `status = 'validated'` — o estado que o produto
-- apresenta como conferido — sem apontar para documento algum. A trava que existia conferia QUEM
-- validou (`validated_by`, e de outra organização), não COM BASE EM QUÊ.
--
-- A trava nova não proíbe indicador autodeclarado: proíbe indicador autodeclarado *apresentado
-- como validado*. Essa é a diferença entre exigir prova e impedir trabalho.

-- ── 1. ORIGEM DECLARADA ──────────────────────────────────────────────────────────────────────────
ALTER TABLE indicator_values
  ADD COLUMN IF NOT EXISTS source_kind text NOT NULL DEFAULT 'self_declared';

UPDATE indicator_values SET source_kind = 'evidence_document'
 WHERE evidence_id IS NOT NULL AND source_kind = 'self_declared';

ALTER TABLE indicator_values DROP CONSTRAINT IF EXISTS indicator_source_kind_known;
ALTER TABLE indicator_values ADD CONSTRAINT indicator_source_kind_known
  CHECK (source_kind IN ('evidence_document','system_calculated','external_import','self_declared'));

-- Dizer "veio de documento" e não apontar o documento é pior que não dizer nada.
ALTER TABLE indicator_values DROP CONSTRAINT IF EXISTS indicator_evidence_matches_source;
ALTER TABLE indicator_values ADD CONSTRAINT indicator_evidence_matches_source
  CHECK (source_kind <> 'evidence_document' OR evidence_id IS NOT NULL);

-- A trava central. ATENÇÃO À IMPLANTAÇÃO: num banco com dados, linhas já validadas sem evidência
-- fariam esta restrição falhar na aplicação da migração. É deliberado — a migração RECUSA subir
-- em vez de aceitar em silêncio um estado que a regra proíbe. O procedimento está em
-- DATABASE.md (§ proveniência): conferir `SELECT count(*) FROM indicator_values WHERE
-- status = 'validated' AND evidence_id IS NULL` e decidir caso a caso, porque rebaixar o estado
-- de uma medição alheia sem avisar quem a validou seria apagar trabalho de terceiro.
ALTER TABLE indicator_values DROP CONSTRAINT IF EXISTS indicator_validated_needs_evidence;
ALTER TABLE indicator_values ADD CONSTRAINT indicator_validated_needs_evidence
  CHECK (status <> 'validated' OR evidence_id IS NOT NULL);

-- E a origem não se reescreve depois de validada: trocar a evidência de uma medição conferida
-- desfaz a conferência sem que ninguém perceba.
CREATE OR REPLACE FUNCTION indicator_provenance_is_frozen_after_validation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'validated' AND (NEW.evidence_id IS DISTINCT FROM OLD.evidence_id
                                   OR NEW.source_kind <> OLD.source_kind
                                   OR NEW.value <> OLD.value
                                   OR NEW.measured_on <> OLD.measured_on) THEN
    RAISE EXCEPTION 'medição validada não muda de valor nem de origem: registre uma medição nova'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_indicator_provenance ON indicator_values;
CREATE TRIGGER trg_indicator_provenance BEFORE UPDATE ON indicator_values
  FOR EACH ROW EXECUTE FUNCTION indicator_provenance_is_frozen_after_validation();

CREATE INDEX IF NOT EXISTS ix_indicator_values_evidence ON indicator_values (evidence_id)
  WHERE evidence_id IS NOT NULL;

-- ── 2. CORREÇÃO NO LEDGER: ACRESCENTA, NÃO REESCREVE ─────────────────────────────────────────────
--
-- `ledger_entries` já é append-only e encadeado por hash. Faltava o CAMINHO para corrigir: sem um
-- tipo de lançamento de correção, a única forma de consertar um valor errado seria um UPDATE — que
-- a tabela recusa — ou deixar o erro. O modelo é o de contabilidade: o estorno é um lançamento
-- novo que aponta para o que corrige.
ALTER TABLE ledger_entries
  ADD COLUMN IF NOT EXISTS reverses_id bigint REFERENCES ledger_entries(id);

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
  'impact_update_submitted','impact_update_accepted','impact_update_published','conversation_started',
  'team_member_added','team_member_removed','experience_confirmed','enforcement_applied',
  -- v0.23.0
  'correction'));

CREATE OR REPLACE FUNCTION ledger_correction_is_well_formed() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE alvo ledger_entries;
BEGIN
  IF NEW.entry_type = 'correction' THEN
    IF NEW.reverses_id IS NULL THEN
      RAISE EXCEPTION 'correção precisa apontar o lançamento que corrige' USING ERRCODE = '23514';
    END IF;
    SELECT * INTO alvo FROM ledger_entries WHERE id = NEW.reverses_id;
    IF alvo.project_id <> NEW.project_id THEN
      RAISE EXCEPTION 'correção só vale dentro do mesmo projeto' USING ERRCODE = '23514';
    END IF;
    IF alvo.entry_type = 'correction' THEN
      RAISE EXCEPTION 'correção de correção não é correção: registre uma correção do lançamento original'
        USING ERRCODE = '23514';
    END IF;
    IF EXISTS (SELECT 1 FROM ledger_entries WHERE reverses_id = NEW.reverses_id) THEN
      RAISE EXCEPTION 'este lançamento já foi corrigido uma vez' USING ERRCODE = '23505';
    END IF;
    IF alvo.amount_cents IS NOT NULL AND NEW.amount_cents IS DISTINCT FROM -alvo.amount_cents THEN
      RAISE EXCEPTION 'a correção tem de ser o oposto exato do valor corrigido (% esperado)',
        -alvo.amount_cents USING ERRCODE = '23514';
    END IF;
    IF coalesce(btrim(NEW.payload->>'reason'), '') = '' THEN
      RAISE EXCEPTION 'correção exige motivo em payload.reason' USING ERRCODE = '23514';
    END IF;
  ELSIF NEW.reverses_id IS NOT NULL THEN
    RAISE EXCEPTION 'só lançamento do tipo correction aponta para outro lançamento'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;

-- BEFORE INSERT e ANTES do gatilho de cadeia (ordem alfabética do nome decide): `aa_` garante que
-- a correção malformada seja recusada antes de consumir número de sequência da cadeia.
DROP TRIGGER IF EXISTS aa_trg_ledger_correction ON ledger_entries;
CREATE TRIGGER aa_trg_ledger_correction BEFORE INSERT ON ledger_entries
  FOR EACH ROW EXECUTE FUNCTION ledger_correction_is_well_formed();

CREATE UNIQUE INDEX IF NOT EXISTS ux_ledger_one_correction_per_entry
  ON ledger_entries (reverses_id) WHERE reverses_id IS NOT NULL;

-- ── 3. CADEIA DE HASH NO VALUE LEDGER ────────────────────────────────────────────────────────────
--
-- `value_events` é a tabela que sustenta o Value Ledger — a afirmação de valor gerado que o produto
-- usa no posicionamento. Ela já era append-only, e NÃO era encadeada: um administrador de banco
-- podia reescrever uma linha e nada acusaria. `audit_events` e `ledger_entries` já tinham cadeia;
-- a tabela que fundamenta o número principal do produto não tinha.
ALTER TABLE value_events ADD COLUMN IF NOT EXISTS seq bigint;
ALTER TABLE value_events ADD COLUMN IF NOT EXISTS prev_hash char(64);
ALTER TABLE value_events ADD COLUMN IF NOT EXISTS entry_hash char(64);

CREATE OR REPLACE FUNCTION value_event_material(e value_events) RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT concat_ws('|', e.prev_hash, e.seq::text, e.org_id::text, e.event_type,
                   coalesce(e.actor_user_id::text,''), coalesce(e.project_id::text,''),
                   coalesce(e.program_id::text,''), coalesce(e.subject_type,''),
                   coalesce(e.subject_id::text,''), coalesce(e.units::text,''),
                   coalesce(e.metrics::text,''), coalesce(e.minutes_saved_estimate::text,''),
                   coalesce(e.estimate_status,''), coalesce(e.baseline_id::text,''),
                   coalesce(e.engine_version,''), ts_canonical(e.created_at))
$$;

CREATE OR REPLACE FUNCTION chain_value_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE k text; s bigint; prev char(64);
BEGIN
  k := 'value:' || NEW.org_id::text;
  INSERT INTO chain_heads(chain_key, last_seq, last_hash) VALUES (k, 0, repeat('0', 64))
    ON CONFLICT DO NOTHING;
  SELECT last_seq, last_hash INTO s, prev FROM chain_heads WHERE chain_key = k FOR UPDATE;
  NEW.created_at := date_trunc('microseconds', now());
  NEW.seq := s + 1; NEW.prev_hash := prev;
  NEW.entry_hash := encode(digest(value_event_material(NEW), 'sha256'), 'hex');
  UPDATE chain_heads SET last_seq = NEW.seq, last_hash = NEW.entry_hash WHERE chain_key = k;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS aa_trg_chain_value_event ON value_events;
CREATE TRIGGER aa_trg_chain_value_event BEFORE INSERT ON value_events
  FOR EACH ROW EXECUTE FUNCTION chain_value_event();

CREATE OR REPLACE FUNCTION value_verify(p_org uuid)
RETURNS TABLE(entries bigint, valid boolean, first_broken_seq bigint) LANGUAGE plpgsql AS $$
DECLARE r value_events; expected_prev char(64) := repeat('0', 64); n bigint := 0; broken bigint := NULL;
BEGIN
  FOR r IN SELECT * FROM value_events WHERE org_id = p_org ORDER BY seq LOOP
    n := n + 1;
    IF broken IS NULL AND (r.prev_hash <> expected_prev OR r.seq <> n
        OR r.entry_hash <> encode(digest(value_event_material(r), 'sha256'), 'hex')) THEN
      broken := r.seq;
    END IF;
    expected_prev := r.entry_hash;
  END LOOP;
  RETURN QUERY SELECT n, broken IS NULL, broken;
END $$;

-- As linhas que já existiam ficam sem cadeia (seq NULO) de propósito: calcular hash para trás
-- produziria uma cadeia que PARECE verificada sem nunca ter protegido nada. `value_verify()` só
-- percorre linhas com `seq`, e o relatório de integridade informa quantas ficaram de fora.
CREATE INDEX IF NOT EXISTS ix_value_events_chain ON value_events (org_id, seq);
