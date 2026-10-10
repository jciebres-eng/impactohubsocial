-- 0073 — v0.34.0 — ECOSSISTEMA FINANCEIRO: GRATUITO ATÉ GERAR VALOR, OBRIGAÇÕES DE REMUNERAÇÃO,
--        RECURSO PÚBLICO, RECURSOS EXTERNOS, COMPROMISSOS, LIQUIDAÇÃO E FILA DE EXCEÇÕES (ADR-377 a ADR-383)
--
-- O que esta migração É:
--   * o registro ÚNICO das obrigações de remuneração da plataforma, qualquer que seja a origem (doação, acordo,
--     serviço, crédito de IA, manual), com a cadeia de estados que o pacote exige: calculada → devida → faturada →
--     cobrada → recebida → liquidada; e os desvios estornada / inadimplente / em disputa / dispensada / isenta.
--     Remuneração CALCULADA nunca é receita: só o evento financeiro muda o estado, e cada mudança fica no histórico;
--   * a política "gratuito até gerar valor" (free until you make money) como REGISTRO versionado e o aviso prévio como
--     REGISTRO: sem gatilho auditável (regra ativa + valor liquidado acima da franquia + aviso dentro do prazo) nada é
--     devido. Quem decide a franquia é a política versionada, nunca uma constante no código;
--   * a origem do recurso (privado/público/misto) na campanha, na doação e na obrigação: recurso público é ISENTO por
--     padrão; só vira elegível com instrumento identificado e autorização registrada (ADR-379 — a regra depende do
--     instrumento e do ente, não é proibição universal);
--   * recursos declarados fora da plataforma e compromissos de doação futura: registros SEPARADOS do dinheiro
--     recebido, que entram na prestação de contas e nunca no razão nem na receita;
--   * liquidação ≠ confirmação (`settled_at`), estorno parcial (`refunded_cents`), doação feita em nome de uma
--     organização (`donor_org_id`) para o painel do financiador;
--   * a fila de exceções de conciliação, com tipo, prioridade, responsável e histórico de resolução.
--
-- O que esta migração NÃO É:
--   * não liga nenhuma cobrança: as regras continuam INATIVAS; as duas regras institucionais (3,5 % e 1,5 %) entram
--     como HIPÓTESE do pacote, inativas, carta amarela; a "reserva institucional" é destinação contábil da organização,
--     nunca custódia nem rendimento pela plataforma (ADR-380);
--   * não cria saldo nem carteira; não retém repasse; não bloqueia prestação de contas por obrigação em aberto
--     (ADR-381: o estado comercial é separado da integridade e do acesso aos registros);
--   * não substitui `platform_charges`/`invoices` (0022/0001): quando uma obrigação é FATURADA, a cobrança própria da
--     plataforma continua sendo `platform_charges` (kind 'operation', provedor manual/sandbox), referenciada aqui.

-- ============================================================================ 1. origem do recurso
ALTER TABLE campaigns
  ADD COLUMN funding_source        text NOT NULL DEFAULT 'private' CHECK (funding_source IN ('private','public','mixed')),
  ADD COLUMN public_instrument_ref text CHECK (length(public_instrument_ref) <= 300);   -- ex.: "Termo de Fomento nº …"
COMMENT ON COLUMN campaigns.funding_source IS
  'Origem declarada dos recursos que a campanha mobiliza. public/mixed: toda obrigação de remuneração nasce ISENTA, salvo autorização registrada por instrumento (ADR-379).';

ALTER TABLE donations
  ADD COLUMN settled_at     timestamptz,                                           -- o provedor diz que o dinheiro está disponível ao beneficiário
  ADD COLUMN refunded_cents bigint NOT NULL DEFAULT 0 CHECK (refunded_cents >= 0),
  ADD COLUMN donor_org_id   uuid REFERENCES organizations(id) ON DELETE SET NULL,   -- doação feita em nome de uma organização (financiador)
  ADD COLUMN funding_source text NOT NULL DEFAULT 'private' CHECK (funding_source IN ('private','public','mixed'));
ALTER TABLE donations DROP CONSTRAINT donations_status_check;
ALTER TABLE donations ADD CONSTRAINT donations_status_check CHECK (status IN (
  'created','awaiting_payment','confirmed','reconciled','expired','failed','cancelled',
  'refund_pending','refunded','partially_refunded','chargeback','under_review'));
-- v0.34.0 (E6): contribuição VOLUNTÁRIA do doador à plataforma (nunca pré-marcada, nunca descontada da doação: é um
-- valor A MAIS que o doador escolhe; ADR-384), liquidação ACUMULADA pelo provedor (parcial ≠ total), parcela que o provedor
-- dividiu direto para a plataforma (split, só se o contrato e a homologação permitirem) e ciclo de recorrência.
ALTER TABLE donations
  ADD COLUMN platform_contribution_cents bigint NOT NULL DEFAULT 0 CHECK (platform_contribution_cents >= 0),
  ADD COLUMN settled_cents        bigint NOT NULL DEFAULT 0 CHECK (settled_cents >= 0),
  ADD COLUMN split_platform_cents bigint NOT NULL DEFAULT 0 CHECK (split_platform_cents >= 0);   -- recurring_agreement_id já existe (0072)
ALTER TABLE donations ADD CONSTRAINT contribution_bounded CHECK (platform_contribution_cents <= amount_cents);
ALTER TABLE donations ADD CONSTRAINT split_only_contribution CHECK (split_platform_cents <= platform_contribution_cents);
ALTER TABLE donations ADD CONSTRAINT refund_within_amount CHECK (refunded_cents <= amount_cents + cover_costs_cents + platform_contribution_cents);
CREATE INDEX ix_donations_recurring ON donations(recurring_agreement_id) WHERE recurring_agreement_id IS NOT NULL;

-- Razão: duas contas para a contribuição voluntária (fora da arrecadação da campanha, que continua só `donor_payment`).
ALTER TABLE donation_ledger_entries DROP CONSTRAINT donation_ledger_entries_account_check;
ALTER TABLE donation_ledger_entries ADD CONSTRAINT donation_ledger_entries_account_check CHECK (account IN (
  'donor_payment', 'beneficiary_receivable', 'provider_fee', 'platform_fee_accrued', 'beneficiary_fund', 'refund', 'chargeback',
  'donor_platform_contribution',        -- crédito: o que o doador pagou A MAIS, por escolha, à plataforma
  'platform_contribution_receivable')); -- débito: o que a plataforma tem a receber (pelo split, ou da organização se não houve split)

-- Recorrência: autorização (consent_at) ≠ tentativa ≠ confirmado ≠ falha ≠ cancelado.
ALTER TABLE recurring_donation_agreements
  ADD COLUMN attempts        integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  ADD COLUMN failed_attempts integer NOT NULL DEFAULT 0 CHECK (failed_attempts >= 0),
  ADD COLUMN last_attempt_at timestamptz;
CREATE INDEX ix_donations_donor_org ON donations(donor_org_id) WHERE donor_org_id IS NOT NULL;

CREATE OR REPLACE FUNCTION donation_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    ok := CASE OLD.status
      WHEN 'created'            THEN NEW.status IN ('awaiting_payment','cancelled','failed','expired')
      WHEN 'awaiting_payment'   THEN NEW.status IN ('confirmed','expired','failed','cancelled','under_review')
      WHEN 'under_review'       THEN NEW.status IN ('confirmed','failed','cancelled','refund_pending')
      WHEN 'confirmed'          THEN NEW.status IN ('reconciled','refund_pending','partially_refunded','chargeback','under_review')
      WHEN 'reconciled'         THEN NEW.status IN ('refund_pending','partially_refunded','chargeback')
      WHEN 'partially_refunded' THEN NEW.status IN ('refund_pending','refunded','chargeback','reconciled')
      WHEN 'refund_pending'     THEN NEW.status IN ('refunded','reconciled','partially_refunded')
      ELSE false END;
    IF NOT ok THEN
      RAISE EXCEPTION 'transição de doação não permitida: % → %', OLD.status, NEW.status USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'confirmed' THEN NEW.confirmed_at := coalesce(NEW.confirmed_at, now()); END IF;
  END IF;
  IF OLD.status IN ('confirmed','reconciled','refunded','partially_refunded','chargeback') AND
     (NEW.amount_cents <> OLD.amount_cents OR NEW.currency <> OLD.currency OR NEW.provider <> OLD.provider
      OR NEW.provider_charge_id IS DISTINCT FROM OLD.provider_charge_id OR NEW.campaign_id <> OLD.campaign_id) THEN
    RAISE EXCEPTION 'doação confirmada não muda de valor, provedor, cobrança ou campanha' USING ERRCODE = '23514';
  END IF;
  -- liquidação só depois da confirmação; nunca "desliquida"
  IF NEW.settled_at IS NOT NULL AND OLD.settled_at IS NULL AND OLD.status NOT IN ('confirmed','reconciled','partially_refunded') THEN
    RAISE EXCEPTION 'liquidação exige doação confirmada' USING ERRCODE = '23514';
  END IF;
  IF OLD.settled_at IS NOT NULL AND NEW.settled_at IS NULL THEN
    RAISE EXCEPTION 'liquidação não é desfeita; estorno é lançamento novo' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;

-- ============================================================================ 2. política versionada "gratuito até gerar valor"
CREATE TABLE monetization_policy_versions (
  id             bigserial PRIMARY KEY,
  key            text NOT NULL CHECK (key ~ '^[a-z0-9_.]{3,60}$'),
  version        integer NOT NULL CHECK (version >= 1),
  content        jsonb NOT NULL,                      -- os parâmetros (franquia, prazo de aviso, mínimo de fatura…)
  effective_from timestamptz NOT NULL DEFAULT now(),
  effective_to   timestamptz,
  legal_status   text NOT NULL DEFAULT 'hypothesis' CHECK (legal_status IN ('hypothesis','approved','retired')),
  approved_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  note           text CHECK (length(note) <= 2000),
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (key, version)
);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON monetization_policy_versions FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
ALTER TABLE monetization_policy_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY policy_versions_read ON monetization_policy_versions FOR SELECT USING (true);
CREATE POLICY policy_versions_priv ON monetization_policy_versions FOR INSERT WITH CHECK (app_priv());
INSERT INTO monetization_policy_versions(key, version, content, note) VALUES
 ('free_until_value', 1, jsonb_build_object(
    'allowance_settled_cents_12m', 2000000,     -- HIPÓTESE: os primeiros R$ 20.000,00 LIQUIDADOS em 12 meses são livres de taxa
    'notice_days', 30,                           -- aviso prévio mínimo antes de qualquer obrigação virar devida
    'min_invoice_cents', 2000,                   -- abaixo de R$ 20,00 acumula; não fatura
    'due_days_after_invoice', 30,
    'overdue_grace_days', 15,
    'max_fee_share_of_settled_bps', 500,         -- trava: obrigações devidas no período nunca passam de 5 % do liquidado
    'public_funding_default', 'exempt',          -- recurso público: isento salvo autorização por instrumento
    'never_blocks', jsonb_build_array('accountability','exports','public_page','evidence','reports')),
  'HIPÓTESE do pacote de monetização (10/10/2026): "gratuito até gerar valor". Os números são parâmetros a validar; nenhum é contrato.');

-- ============================================================================ 3. avisos prévios (comunicação registrada)
CREATE TABLE remuneration_notices (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  kind            text NOT NULL CHECK (kind IN ('free_until_value_intro','allowance_approaching','charging_starts','invoice_issued','overdue','dispute_received','waived')),
  policy_version_id bigint REFERENCES monetization_policy_versions(id),
  rule_key        text REFERENCES monetization_rules(key) ON DELETE SET NULL,
  body            text NOT NULL CHECK (length(body) BETWEEN 20 AND 4000),     -- o texto exatamente como foi comunicado
  channel         text NOT NULL DEFAULT 'in_app' CHECK (channel IN ('in_app','email','both')),
  sent_at         timestamptz NOT NULL DEFAULT now(),
  acknowledged_at timestamptz,
  acknowledged_by uuid REFERENCES users(id) ON DELETE SET NULL,
  created_by      uuid REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX ix_remuneration_notices_org ON remuneration_notices(org_id, kind, sent_at DESC);
ALTER TABLE remuneration_notices ENABLE ROW LEVEL SECURITY;
CREATE POLICY remuneration_notices_read ON remuneration_notices FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY remuneration_notices_ack ON remuneration_notices FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY remuneration_notices_priv ON remuneration_notices FOR INSERT WITH CHECK (app_priv());

-- ============================================================================ 4. obrigações de remuneração (registro único)
CREATE TABLE remuneration_obligations (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,   -- quem deve (pagador)
  source_kind        text NOT NULL CHECK (source_kind IN ('donation','agreement_allocation','service_contract','ai_credit','manual')),
  source_id          text NOT NULL CHECK (length(source_id) BETWEEN 1 AND 80),
  campaign_id        uuid REFERENCES campaigns(id) ON DELETE SET NULL,
  rule_key           text NOT NULL REFERENCES monetization_rules(key) ON DELETE RESTRICT,
  rule_version_id    bigint REFERENCES fee_rule_versions(id),
  basis_cents        bigint NOT NULL CHECK (basis_cents >= 0),
  amount_cents       bigint NOT NULL CHECK (amount_cents >= 0),
  currency           char(3) NOT NULL DEFAULT 'BRL' CHECK (currency = 'BRL'),
  funding_source     text NOT NULL DEFAULT 'private' CHECK (funding_source IN ('private','public','mixed','unknown')),
  public_instrument_ref text CHECK (length(public_instrument_ref) <= 300),
  public_fee_authorized boolean NOT NULL DEFAULT false,
  public_fee_authorization_note text CHECK (length(public_fee_authorization_note) <= 2000),
  state              text NOT NULL DEFAULT 'calculated' CHECK (state IN (
                       'calculated',   -- CALCULADA pela versão congelada; não é receita, não é devida
                       'exempt',       -- isenta (recurso público sem autorização; franquia; dispensa de política)
                       'due',          -- DEVIDA: regra ativa + gatilho + aviso prévio dentro do prazo
                       'invoiced',     -- FATURADA: platform_charge/invoice emitida
                       'charged',      -- COBRADA: cobrança enviada/registrada ao pagador
                       'received',     -- RECEBIDA (pagamento registrado com referência)
                       'settled',      -- LIQUIDADA (dinheiro disponível na conta da plataforma, conciliado)
                       'reversed',     -- ESTORNADA (doação/base estornada antes do recebimento)
                       'overdue',      -- INADIMPLENTE (vencida sem pagamento) — nunca bloqueia prestação de contas
                       'disputed',     -- EM DISPUTA (contestação do pagador registrada)
                       'waived')),     -- DISPENSADA por decisão registrada (quem, por quê)
  trigger_code       text CHECK (length(trigger_code) <= 80),                 -- o gatilho auditável que a tornou devida
  trigger_at         timestamptz,
  policy_version_id  bigint REFERENCES monetization_policy_versions(id),
  notice_id          uuid REFERENCES remuneration_notices(id) ON DELETE SET NULL,
  due_on             date,
  platform_charge_id uuid REFERENCES platform_charges(id) ON DELETE SET NULL,
  invoice_id         uuid REFERENCES invoices(id) ON DELETE SET NULL,
  received_cents     bigint NOT NULL DEFAULT 0 CHECK (received_cents >= 0),
  received_reference text CHECK (length(received_reference) <= 120),
  received_at        timestamptz,
  settled_at         timestamptz,
  dispute_reason     text CHECK (length(dispute_reason) <= 2000),
  waived_reason      text CHECK (length(waived_reason) <= 2000),
  decided_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_kind, source_id, rule_key),
  CONSTRAINT received_within_amount CHECK (received_cents <= amount_cents),
  CONSTRAINT due_needs_trigger CHECK (state NOT IN ('due','invoiced','charged','received','settled','overdue') OR trigger_code IS NOT NULL),
  CONSTRAINT waived_has_reason CHECK (state <> 'waived' OR length(coalesce(waived_reason,'')) >= 10),
  CONSTRAINT disputed_has_reason CHECK (state <> 'disputed' OR length(coalesce(dispute_reason,'')) >= 10)
);
CREATE INDEX ix_remuneration_obligations_org ON remuneration_obligations(org_id, state);
CREATE INDEX ix_remuneration_obligations_campaign ON remuneration_obligations(campaign_id) WHERE campaign_id IS NOT NULL;
CREATE TRIGGER trg_touch BEFORE UPDATE ON remuneration_obligations FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Máquina de estados da obrigação: cada transição permitida está aqui, e toda mudança gera linha no histórico.
CREATE FUNCTION remuneration_obligation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF NEW.state IS DISTINCT FROM OLD.state THEN
    ok := CASE OLD.state
      WHEN 'calculated' THEN NEW.state IN ('exempt','due','reversed','waived')
      WHEN 'exempt'     THEN NEW.state IN ('calculated','due','reversed','waived')
      WHEN 'due'        THEN NEW.state IN ('invoiced','received','reversed','disputed','waived','overdue','exempt')   -- received: split confirmado pelo provedor
      WHEN 'invoiced'   THEN NEW.state IN ('charged','received','reversed','disputed','waived','overdue')
      WHEN 'charged'    THEN NEW.state IN ('received','disputed','waived','overdue','reversed')
      WHEN 'overdue'    THEN NEW.state IN ('received','disputed','waived','reversed')
      WHEN 'disputed'   THEN NEW.state IN ('due','invoiced','charged','received','waived','reversed','exempt')
      WHEN 'received'   THEN NEW.state IN ('settled','disputed','reversed')
      WHEN 'settled'    THEN NEW.state IN ('reversed','disputed')
      ELSE false END;   -- reversed e waived são terminais
    IF NOT ok THEN
      RAISE EXCEPTION 'transição de obrigação não permitida: % → %', OLD.state, NEW.state USING ERRCODE = '23514';
    END IF;
  END IF;
  -- o valor calculado é congelado: quem muda a regra cria obrigação nova; nunca reescreve a antiga (ADR-378)
  IF NEW.amount_cents <> OLD.amount_cents OR NEW.basis_cents <> OLD.basis_cents OR NEW.rule_version_id IS DISTINCT FROM OLD.rule_version_id THEN
    RAISE EXCEPTION 'obrigação não muda de valor, base ou versão de regra; correção é obrigação nova' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_obligation_guard BEFORE UPDATE ON remuneration_obligations FOR EACH ROW EXECUTE FUNCTION remuneration_obligation_guard();

CREATE TABLE remuneration_obligation_events (
  id            bigserial PRIMARY KEY,
  obligation_id uuid NOT NULL REFERENCES remuneration_obligations(id) ON DELETE CASCADE,
  from_state    text,
  to_state      text NOT NULL,
  actor_id      uuid REFERENCES users(id) ON DELETE SET NULL,
  trigger_code  text,
  note          text CHECK (length(note) <= 2000),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_obligation_events ON remuneration_obligation_events(obligation_id, id);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON remuneration_obligation_events FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE FUNCTION remuneration_obligation_log() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO remuneration_obligation_events(obligation_id, from_state, to_state, trigger_code, note)
    VALUES (NEW.id, NULL, NEW.state, NEW.trigger_code, 'obrigação registrada (' || NEW.source_kind || ')');
  ELSIF NEW.state IS DISTINCT FROM OLD.state THEN
    INSERT INTO remuneration_obligation_events(obligation_id, from_state, to_state, actor_id, trigger_code, note)
    VALUES (NEW.id, OLD.state, NEW.state, NEW.decided_by, NEW.trigger_code,
            coalesce(NEW.dispute_reason, NEW.waived_reason, NEW.received_reference));
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_obligation_log AFTER INSERT OR UPDATE ON remuneration_obligations FOR EACH ROW EXECUTE FUNCTION remuneration_obligation_log();

ALTER TABLE remuneration_obligations ENABLE ROW LEVEL SECURITY;
CREATE POLICY obligations_read ON remuneration_obligations FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY obligations_priv ON remuneration_obligations FOR ALL USING (app_priv()) WITH CHECK (app_priv());
ALTER TABLE remuneration_obligation_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY obligation_events_read ON remuneration_obligation_events FOR SELECT USING (
  app_priv() OR EXISTS (SELECT 1 FROM remuneration_obligations o WHERE o.id = obligation_id AND o.org_id = app_org()));
CREATE POLICY obligation_events_priv ON remuneration_obligation_events FOR INSERT WITH CHECK (app_priv());

-- ============================================================================ 5. recursos declarados fora da plataforma
CREATE TABLE external_resources (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  campaign_id     uuid REFERENCES campaigns(id) ON DELETE SET NULL,
  project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
  kind            text NOT NULL CHECK (kind IN ('public_transfer','grant','offline_donation','sponsorship','in_kind','own_funds','other')),
  source_name     text NOT NULL CHECK (length(source_name) BETWEEN 2 AND 200),
  funding_source  text NOT NULL CHECK (funding_source IN ('private','public','mixed')),
  instrument_ref  text CHECK (length(instrument_ref) <= 300),
  amount_cents    bigint CHECK (amount_cents IS NULL OR amount_cents > 0),      -- NULL para apoio não financeiro
  in_kind_description text CHECK (length(in_kind_description) <= 1000),
  received_on     date NOT NULL,
  evidence_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  status          text NOT NULL DEFAULT 'declared' CHECK (status IN ('declared','documented','contested')),
  note            text CHECK (length(note) <= 1000),
  declared_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT in_kind_or_amount CHECK ((kind = 'in_kind') = (amount_cents IS NULL))
);
COMMENT ON TABLE external_resources IS
  'Recurso que a organização DECLARA ter recebido fora da plataforma. Entra na prestação de contas rotulado como declarado; nunca no razão de doações, nunca na receita da plataforma, nunca na barra de arrecadação (ADR-382).';
CREATE INDEX ix_external_resources_campaign ON external_resources(campaign_id) WHERE campaign_id IS NOT NULL;
CREATE TRIGGER trg_touch BEFORE UPDATE ON external_resources FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
ALTER TABLE external_resources ENABLE ROW LEVEL SECURITY;
CREATE POLICY external_resources_read ON external_resources FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY external_resources_write ON external_resources FOR ALL USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

-- ============================================================================ 6. compromissos de doação futura
CREATE TABLE donation_pledges (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id     uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  beneficiary_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  pledger_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  pledger_org_id  uuid REFERENCES organizations(id) ON DELETE SET NULL,
  pledger_display text CHECK (length(pledger_display) <= 120),
  amount_cents    bigint NOT NULL CHECK (amount_cents > 0),
  expected_on     date,
  status          text NOT NULL DEFAULT 'pledged' CHECK (status IN ('pledged','fulfilled','cancelled','expired')),
  fulfilled_donation_id uuid REFERENCES donations(id) ON DELETE SET NULL,
  note            text CHECK (length(note) <= 500),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fulfilled_has_donation CHECK (status <> 'fulfilled' OR fulfilled_donation_id IS NOT NULL)
);
COMMENT ON TABLE donation_pledges IS 'Promessa de doação. NUNCA é dinheiro recebido: não entra no razão, na barra nem nos totais (ADR-382).';
CREATE INDEX ix_pledges_campaign ON donation_pledges(campaign_id, status);
CREATE TRIGGER trg_touch BEFORE UPDATE ON donation_pledges FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
ALTER TABLE donation_pledges ENABLE ROW LEVEL SECURITY;
CREATE POLICY pledges_read ON donation_pledges FOR SELECT USING (
  beneficiary_org_id = app_org() OR (pledger_user_id IS NOT NULL AND pledger_user_id = app_uid()) OR pledger_org_id = app_org() OR app_priv());
CREATE POLICY pledges_priv ON donation_pledges FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- ============================================================================ 7. fila de exceções de conciliação
CREATE TABLE reconciliation_exceptions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind            text NOT NULL CHECK (kind IN (
                    'provider_only',        -- cobrança existe no provedor e não no sistema
                    'system_only',          -- doação confirmada no sistema sem evento verificado do provedor
                    'amount_mismatch',      -- valores divergentes
                    'fee_mismatch',         -- tarifa do provedor diferente da prevista
                    'reversal_missing',     -- estorno no provedor sem lançamento de reversão
                    'duplicate_entry',      -- lançamento duplicado no razão
                    'fee_miscalculated',    -- obrigação com valor ≠ regra congelada × base
                    'settlement_partial',   -- repasse/liquidação parcial ou atrasada
                    'unreconciled_overdue',   -- operação sem conciliação dentro do prazo
                    'settlement_failed',      -- o provedor informou falha na liquidação/repasse ao beneficiário
                    'event_processing_failed')), -- evento assinado gravado e não aplicado (erro interno); reprocessado pela rotina
  campaign_id     uuid REFERENCES campaigns(id) ON DELETE SET NULL,
  org_id          uuid REFERENCES organizations(id) ON DELETE SET NULL,
  donation_id     uuid REFERENCES donations(id) ON DELETE SET NULL,
  obligation_id   uuid REFERENCES remuneration_obligations(id) ON DELETE SET NULL,
  provider        text,
  provider_ref    text,
  expected_cents  bigint,
  observed_cents  bigint,
  priority        text NOT NULL DEFAULT 'medium' CHECK (priority IN ('low','medium','high')),
  status          text NOT NULL DEFAULT 'open' CHECK (status IN ('open','assigned','resolved','dismissed')),
  assigned_to     uuid REFERENCES users(id) ON DELETE SET NULL,
  detail          text CHECK (length(detail) <= 2000),
  resolution_note text CHECK (length(resolution_note) <= 2000),
  resolved_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  resolved_at     timestamptz,
  run_id          uuid,                                     -- a execução de conciliação que a abriu
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT resolved_has_note CHECK (status NOT IN ('resolved','dismissed') OR length(coalesce(resolution_note,'')) >= 10)
);
-- uma exceção aberta por fato: reexecutar a conciliação não duplica a fila
CREATE UNIQUE INDEX ux_recon_open_fact ON reconciliation_exceptions(kind, coalesce(donation_id::text, ''), coalesce(provider_ref, ''), coalesce(obligation_id::text, ''))
  WHERE status IN ('open','assigned');
CREATE INDEX ix_recon_status ON reconciliation_exceptions(status, priority, created_at);
CREATE TRIGGER trg_touch BEFORE UPDATE ON reconciliation_exceptions FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TABLE reconciliation_exception_events (
  id            bigserial PRIMARY KEY,
  exception_id  uuid NOT NULL REFERENCES reconciliation_exceptions(id) ON DELETE CASCADE,
  from_status   text,
  to_status     text NOT NULL,
  actor_id      uuid REFERENCES users(id) ON DELETE SET NULL,
  note          text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON reconciliation_exception_events FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE FUNCTION reconciliation_exception_log() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO reconciliation_exception_events(exception_id, from_status, to_status, note) VALUES (NEW.id, NULL, NEW.status, NEW.detail);
  ELSIF NEW.status IS DISTINCT FROM OLD.status OR NEW.assigned_to IS DISTINCT FROM OLD.assigned_to THEN
    INSERT INTO reconciliation_exception_events(exception_id, from_status, to_status, actor_id, note)
    VALUES (NEW.id, OLD.status, NEW.status, coalesce(NEW.resolved_by, NEW.assigned_to), NEW.resolution_note);
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_recon_log AFTER INSERT OR UPDATE ON reconciliation_exceptions FOR EACH ROW EXECUTE FUNCTION reconciliation_exception_log();
CREATE TABLE reconciliation_runs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  scope         text NOT NULL,                       -- 'campaign:<id>' | 'org:<id>' | 'all'
  provider      text NOT NULL,
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz,
  checked       integer NOT NULL DEFAULT 0,
  opened        integer NOT NULL DEFAULT 0,
  reconciled    integer NOT NULL DEFAULT 0,
  run_by        uuid REFERENCES users(id) ON DELETE SET NULL,
  summary       jsonb
);
ALTER TABLE reconciliation_exceptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY recon_exc_read ON reconciliation_exceptions FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY recon_exc_priv ON reconciliation_exceptions FOR ALL USING (app_priv()) WITH CHECK (app_priv());
ALTER TABLE reconciliation_exception_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY recon_exc_ev_read ON reconciliation_exception_events FOR SELECT USING (app_priv());
CREATE POLICY recon_exc_ev_priv ON reconciliation_exception_events FOR INSERT WITH CHECK (app_priv());
ALTER TABLE reconciliation_runs ENABLE ROW LEVEL SECURITY;
CREATE POLICY recon_runs_priv ON reconciliation_runs FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- ============================================================================ 8. regras institucionais (hipóteses do pacote, INATIVAS)
-- Reclassificação (ADR-378): a taxa de serviço sobre doação é RECEITA DE SERVIÇO FATURADA À PARTE sobre uma base registrada
-- (a doação confirmada), exatamente como `contract.platform_service_fee` (v0.26.0) — motor `enterprise`. O motor `success_fee`
-- é estruturalmente inativável pela ADR-022 (percentual sobre dinheiro que a plataforma não processa), e é ONDE FICAM, de
-- propósito, o fundo (4 %) e a reserva (1,5 %): o banco recusa que uma destinação do beneficiário vire receita da plataforma.
UPDATE monetization_rules SET revenue_engine = 'enterprise', engine_rank = 3 WHERE key = 'donation.platform_fee';
INSERT INTO monetization_rules(
    key, label_pt, revenue_engine, engine_rank, payer_kind, trigger_kind, value_event_type,
    pricing_mode, percentage, currency, hypothesis_note, problem_solved, substitution_answer)
VALUES
 ('donation.institutional_fee', 'Taxa de serviço sobre aporte institucional confirmado (campanha institucional)', 'enterprise', 3,
  'company', 'transaction', NULL, 'percentage', 3.50, 'BRL',
  'HIPÓTESE do pacote (10/10/2026): 3,5 % sobre aporte CONFIRMADO em campanha de tipo institutional_fund, pago pelo financiador '
  '(empresa/fundação) por contrato, SE o enquadramento permitir. ISENTA por padrão quando a origem do recurso é pública; elegível só com '
  'instrumento identificado e autorização registrada (ADR-379). Nunca deduzida de dinheiro em trânsito.',
  'Financiadores institucionais ganham originação, triagem, due diligence documental e acompanhamento de execução num só lugar.',
  'Sem a plataforma, a mesma gestão é feita com consultoria avulsa e planilhas, sem rastreabilidade.'),
 ('donation.institutional_reserve', 'Reserva institucional do beneficiário sobre aporte (destinação contábil, não é receita da plataforma)', 'success_fee', 6,
  'company', 'transaction', NULL, 'percentage', 1.50, 'BRL',
  'HIPÓTESE do pacote (10/10/2026): até 1,5 % do aporte destinado a reserva DA ORGANIZAÇÃO beneficiária, comunicada e autorizada. '
  'É DESTINAÇÃO CONTÁBIL/CONTRATUAL: a plataforma não retém, não guarda e não remunera esse valor (ADR-380).',
  'A organização constitui uma reserva declarada e visível ao financiador, sem intermediário.',
  'Sem a plataforma a reserva é lançamento interno invisível; aqui é calculada e exibida.');
INSERT INTO fee_rule_versions(rule_key, version, bps, base, note) VALUES
  ('donation.institutional_fee', 1, 350, 'gross', 'HIPÓTESE do pacote: 3,5 % sobre aporte institucional confirmado. Inativa.'),
  ('donation.institutional_reserve', 1, 150, 'gross', 'HIPÓTESE do pacote: 1,5 % de reserva da organização. Destinação contábil; inativa.');
WITH c AS (
  INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature,
      contractual_relation, required_document, required_terms, cancellation_policy, refund_policy, tax_notes,
      invoice_notes, regulatory_notes, legal_basis, source_name, source_url, verified_on, open_questions, note)
  VALUES ('donation.institutional_fee', 'yellow', 'low',
    'Financiador institucional (empresa, fundação, instituto) por contrato próprio; NUNCA o ente público sem instrumento que preveja a despesa',
    'A plataforma (pessoa jurídica titular do software)',
    'Aporte CONFIRMADO pelo provedor em campanha institucional; a obrigação só fica DEVIDA com gatilho auditável (política free_until_value)',
    'Receita de serviço de software (originação, triagem, acompanhamento), faturada à parte — não é intermediação de pagamento',
    'Contrato de serviço com o financiador; termos da campanha institucional',
    'Contrato; NFS-e à parte; nunca dedução do aporte',
    'Termos de Uso, Contrato de Serviço Institucional',
    'Taxa só é devida sobre aporte confirmado e não estornado',
    'Estorno/chargeback reverte a obrigação por lançamento novo; se já recebida, abre disputa',
    'ISS sobre serviço (LC 116/2003). Recurso PÚBLICO: elegibilidade da despesa depende do instrumento (termo de fomento/colaboração — Lei 13.019/2014; convênio — Decreto 11.531/2023 e regras do ente); só com previsão/autorização e comprovação',
    'NFS-e obrigatória e NÃO implementada',
    'Não presumir que todo repasse público veda o pagamento de licença de software; nem que o permite. Análise por instrumento, regulamento do ente e natureza da despesa (ADR-379)',
    'LC 116/2003; Lei 13.019/2014; Decreto 11.531/2023; Lei 14.133/2021',
    'Planalto', 'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l13019.htm', '2026-10-10',
    'O que define "institucional"? Base: aporte bruto ou líquido? Contrato por financiador ou adesão? Quando a despesa é elegível em recurso público?',
    'Carta AMARELA: hipótese do pacote; INATIVA; nenhum aporte real possível (só provedor sandbox).')
  RETURNING id)
UPDATE monetization_rules r SET legal_card_id = c.id FROM c WHERE r.key = 'donation.institutional_fee';
WITH c AS (
  INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature,
      contractual_relation, required_document, required_terms, cancellation_policy, refund_policy, tax_notes,
      invoice_notes, regulatory_notes, legal_basis, source_name, source_url, verified_on, open_questions, note)
  VALUES ('donation.institutional_reserve', 'yellow', 'low',
    'Financiador (parte do aporte destinada pela organização beneficiária à sua reserva, comunicada antes do aporte)',
    'A ORGANIZAÇÃO beneficiária — nunca a plataforma',
    'Aporte confirmado; a parcela é CALCULADA e EXIBIDA; a organização contabiliza internamente',
    'Não é receita da plataforma; é destinação contábil/contratual da organização',
    'Termos da campanha com a destinação declarada; aceite do financiador',
    'Declaração na página e na prestação de contas',
    'Termos de Campanha Institucional',
    'Estorno reverte o cálculo; nada a devolver pela plataforma',
    'Estorno reverte o cálculo',
    'Contabilidade da organização; parecer sobre "reserva" e sobre vedação de rendimento/custódia pela plataforma',
    'Nenhum documento fiscal da plataforma',
    'A plataforma NÃO retém, NÃO guarda e NÃO oferece rendimento sobre reserva (ADR-280/284/380). Em recurso público, reserva depende do instrumento',
    'Lei 13.019/2014; Lei 12.865/2013', 'Planalto', 'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l13019.htm', '2026-10-10',
    'A reserva pode existir em recurso público? Como é demonstrada na prestação de contas?',
    'Carta AMARELA: hipótese; INATIVA; nunca custódia.')
  RETURNING id)
UPDATE monetization_rules r SET legal_card_id = c.id FROM c WHERE r.key = 'donation.institutional_reserve';

-- Cartão no sandbox (E6): sem esta linha, toda doação por cartão era recusada (`provider_fee_unknown`) — achado do teste
-- do cenário 2. Tarifa zero porque o sandbox não cobra; a tarifa real vem do contrato do provedor.
INSERT INTO provider_fee_schedules(provider, method, bps, fixed_cents, settlement_days, source) VALUES
  ('sandbox', 'card', 0, 0, 0, 'Provedor de TESTE (sem tarifa): nenhum valor real; cartão real tem tarifa e prazo do contrato do provedor');

-- ============================================================================ 8b. contribuição voluntária do doador (ADR-384)
-- Não é taxa sobre a doação: é um valor que o DOADOR escolhe somar, para a plataforma, antes de pagar. Começa em zero,
-- nunca é sugerido nem pré-marcado, e aparece separado no total. Hipótese INATIVA: o formulário só oferece o campo com a
-- regra ativa (carta verde). É a única operação elegível a split nesta arquitetura, porque nada sai do valor doado.
INSERT INTO monetization_rules(
    key, label_pt, revenue_engine, engine_rank, payer_kind, trigger_kind, value_event_type,
    pricing_mode, amount_cents, currency, hypothesis_min_cents, hypothesis_max_cents, hypothesis_note, problem_solved, substitution_answer)
VALUES
 ('donation.platform_contribution', 'Contribuição voluntária do doador para a manutenção da plataforma (opcional, começa em zero)', 'enterprise', 3,
  'individual', 'transaction', NULL, 'contract', NULL, 'BRL', 0, 50000,   -- sem preço fixado: o valor é o que o doador escolhe, nos termos da doação (0 a teto)
  'HIPÓTESE do pacote (10/10/2026, §7.1 "contribuição opcional sem indução enganosa"): o doador PODE somar um valor à doação, '
  'destinado à plataforma. Começa em R$ 0,00, nunca é sugerido nem pré-marcado, aparece separado no total e no comprovante. '
  'Teto por doação: o menor entre o valor doado e R$ 500,00. Com split homologado, o provedor divide direto; sem split, '
  'vira obrigação da organização que recebeu o valor (ADR-384).',
  'Quem quer apoiar a ferramenta além da causa consegue, sem que a organização pague por isso.',
  'Sem o campo, o apoio à plataforma exigiria uma segunda transação ou uma taxa sobre a doação.');
WITH c AS (
  INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature,
      contractual_relation, required_document, required_terms, cancellation_policy, refund_policy, tax_notes,
      invoice_notes, regulatory_notes, legal_basis, source_name, source_url, verified_on, open_questions, note)
  VALUES ('donation.platform_contribution', 'yellow', 'low',
    'O DOADOR, por escolha explícita, além da doação (nunca descontado do valor doado)',
    'A plataforma (pessoa jurídica titular do software)',
    'Pagamento CONFIRMADO pelo provedor com a contribuição informada antes de pagar',
    'Receita da plataforma de natureza a definir (contribuição/doação à empresa ou serviço) — parecer contábil necessário',
    'Termos de doação exibidos com a contribuição separada e o total antes de pagar',
    'Comprovante separado da contribuição; documento fiscal a definir',
    'Termos de Uso, Política de Doações e Reembolso',
    'Estorno da doação estorna a contribuição; o doador pode pedir o estorno só da contribuição',
    'Reversão por lançamento novo; se recebida, abre disputa',
    'Natureza tributária a definir com contador (pode não ser serviço); não é dedutível para o doador',
    'Documento fiscal NÃO implementado',
    'Split depende do provedor (cadastro da plataforma como recebedora) e do enquadramento; sem split, a organização recebe e deve repassar — exige termo aceito pela organização',
    'CDC (Lei 8.078/1990); Lei 12.865/2013', 'Planalto', 'https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm', '2026-10-10',
    'Qual a natureza da receita? O repasse pela organização (sem split) é aceitável? Qual o teto razoável?',
    'Carta AMARELA: hipótese; INATIVA; o campo não aparece ao doador enquanto a regra não for ativada.')
  RETURNING id)
UPDATE monetization_rules r SET legal_card_id = c.id FROM c WHERE r.key = 'donation.platform_contribution';

-- ============================================================================ 9. trilha e privilégios
INSERT INTO audit_action_categories (prefix, category, note) VALUES
  ('remuneration','FINANCE','obrigações de remuneração da plataforma: calculada/devida/faturada/recebida/disputa/dispensa (v0.34.0)'),
  ('reconciliation','FINANCE','conciliação: execuções e exceções (v0.34.0)'),
  ('pledge','FINANCE','compromisso de doação futura (v0.34.0)'),
  ('external_resource','FINANCE','recurso declarado fora da plataforma (v0.34.0)')
ON CONFLICT DO NOTHING;

-- Referência polimórfica da obrigação (doação, alocação de acordo, contrato de serviço, crédito de IA, lançamento manual):
-- catalogada para a verificação de órfãos da v0.23.0 (integrity_catalog_drift) enxergar a coluna.
INSERT INTO polymorphic_refs (source_table, type_column, id_column, note) VALUES
  ('remuneration_obligations','source_kind','source_id','operação que originou a obrigação de remuneração (doação, alocação, contrato de serviço, crédito de IA ou manual)')
ON CONFLICT DO NOTHING;

GRANT SELECT, INSERT ON monetization_policy_versions TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE monetization_policy_versions_id_seq TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON remuneration_notices TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON remuneration_obligations TO impacto_app;
GRANT SELECT, INSERT ON remuneration_obligation_events TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE remuneration_obligation_events_id_seq TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON external_resources TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON donation_pledges TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON reconciliation_exceptions TO impacto_app;
GRANT SELECT, INSERT ON reconciliation_exception_events TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE reconciliation_exception_events_id_seq TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON reconciliation_runs TO impacto_app;
