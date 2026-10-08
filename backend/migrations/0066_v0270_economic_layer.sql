-- v0.27.0 — A camada econômica contratual da operação de financiamento (ADR-341 a ADR-346).
--
-- O que muda de modelo: a plataforma NÃO vende assinatura. A remuneração nasce de EVENTO ECONÔMICO
-- contratual: o acordo de financiamento assinado carrega, por versão de preços, a camada de serviço
-- da plataforma (infraestrutura, inteligência, governança, evidência, rastreabilidade) e, quando há
-- autoria elegível, a participação de autoria/desenvolvimento da ideia. O financiador faz UM aporte
-- e o direciona a cada destinatário pela chave PIX informada no contrato; a plataforma calcula,
-- instrui, registra, concilia e cobra a própria camada — nunca custodia (ADR-284).
--
-- Regras que o banco impõe aqui:
--   * percentual vem do catálogo versionado (economic_rules), congelado no acordo; nunca do cliente;
--   * a participação de autoria só entra na matriz com elegibilidade registrada (estado >= accepted)
--     e parte 'proponent' no acordo; sem isso, não existe linha;
--   * instrução de pagamento por destinatário, com estados; "confirmado" exige confirmação de quem
--     RECEBE, nunca de quem paga; conciliação é passo separado;
--   * ledger econômico append-only com idempotência: nenhuma operação gera evento econômico duas vezes;
--   * reconhecimento (crédito) só por conclusão E quitação — nunca por pagamento à plataforma.

-- ============================================================================ 1. catálogo de regras econômicas (versionado, imutável)
CREATE TABLE economic_rules (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key              text NOT NULL CHECK (key ~ '^[a-z][a-z0-9_.]{2,60}$'),
  pricing_version  text NOT NULL CHECK (pricing_version ~ '^[0-9]{4}\.[0-9]{2}$'),
  label_pt         text NOT NULL CHECK (length(label_pt) BETWEEN 3 AND 200),
  applies_to       text NOT NULL CHECK (applies_to IN ('funding_agreement','service_agreement','marketplace')),
  bps              integer NOT NULL CHECK (bps BETWEEN 0 AND 10000),
  payer_role       text NOT NULL CHECK (payer_role IN ('funder','contractor','provider')),
  recipient_kind   text NOT NULL CHECK (recipient_kind IN ('platform','proponent','provider')),
  monetization_rule_key text REFERENCES monetization_rules(key) ON DELETE RESTRICT,   -- portão jurídico, quando é receita da plataforma
  effective_from   date NOT NULL,
  effective_until  date,
  what_it_pays_for text NOT NULL CHECK (length(what_it_pays_for) BETWEEN 20 AND 2000),
  reason           text NOT NULL CHECK (length(reason) BETWEEN 10 AND 2000),
  created_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (key, pricing_version),
  CONSTRAINT economic_rule_period CHECK (effective_until IS NULL OR effective_until > effective_from)
);
COMMENT ON TABLE economic_rules IS
  'Percentuais da camada econômica POR VERSÃO DE PREÇOS. Imutável: mudar percentual cria versão nova. O acordo '
  'congela o valor no momento da publicação; recalcular operação antiga com regra nova é proibido por desenho.';
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON economic_rules FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
ALTER TABLE economic_rules ENABLE ROW LEVEL SECURITY;
CREATE POLICY econ_rules_read ON economic_rules FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY econ_rules_insert ON economic_rules FOR INSERT WITH CHECK (app_priv());

INSERT INTO economic_rules(key, pricing_version, label_pt, applies_to, bps, payer_role, recipient_kind, monetization_rule_key,
                           effective_from, what_it_pays_for, reason)
VALUES
 ('funding.platform_service', '2027.01', 'Infraestrutura e inteligência IMPACTO', 'funding_agreement', 350, 'funder', 'platform',
  'contract.platform_service_fee', DATE '2027-01-01',
  'Matching, diagnóstico, governança do acordo (versões, obrigações, aceite a quatro olhos), matriz de distribuição, '
  'instrução e conciliação dos repasses, evidência e razão encadeado, acompanhamento longitudinal, relatórios e API. '
  'É a camada que reduz a distância entre o recurso aplicado e o impacto comprovado.',
  'Decisão comercial do dono do projeto (08/10/2026): a camada econômica da operação é 5%, sendo 3,5% da plataforma. '
  'A cobrança só existe com a regra contract.platform_service_fee ativa (carta legal verde).'),
 ('funding.proponent_participation', '2027.01', 'Participação de autoria e desenvolvimento da ideia', 'funding_agreement', 150, 'funder', 'proponent',
  NULL, DATE '2027-01-01',
  'Participação econômica contratual de quem criou e desenvolveu a ideia que virou o projeto financiado: só existe com '
  'autoria registrada, aceita pela executora, consolidada (projeto publicado) e com a parte no acordo. Não é receita da plataforma.',
  'Decisão comercial do dono do projeto (08/10/2026): 1,5% quando há proponente elegível; nunca automático para todo projeto.');

-- ============================================================================ 2. partes: papel 'proponent' e chave PIX informada no contrato
ALTER TABLE signed_agreement_parties DROP CONSTRAINT IF EXISTS signed_agreement_parties_role_check;
ALTER TABLE signed_agreement_parties ADD CONSTRAINT signed_agreement_parties_role_check
  CHECK (role IN ('contractor','provider','funder','professional','witness','beneficiary_rep','proponent'));
ALTER TABLE signed_agreement_parties
  ADD COLUMN pix_key       text,
  ADD COLUMN pix_key_type  text CHECK (pix_key_type IN ('cpf','cnpj','email','phone','evp')),
  ADD COLUMN pix_key_set_by uuid REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN pix_key_set_at timestamptz,
  -- A chave é informada PELA PRÓPRIA PARTE e validada por tipo. CPF/CNPJ só dígitos; telefone +55 E.164; EVP uuid.
  ADD CONSTRAINT pix_key_shape CHECK (
    (pix_key IS NULL AND pix_key_type IS NULL) OR
    (pix_key_type = 'cpf'   AND pix_key ~ '^[0-9]{11}$') OR
    (pix_key_type = 'cnpj'  AND pix_key ~ '^[0-9]{14}$') OR
    (pix_key_type = 'email' AND pix_key ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' AND length(pix_key) <= 77) OR
    (pix_key_type = 'phone' AND pix_key ~ '^\+55[1-9][0-9]{9,10}$') OR
    (pix_key_type = 'evp'   AND pix_key ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'));
COMMENT ON COLUMN signed_agreement_parties.pix_key IS
  'Chave PIX para os repasses e quitações desta parte, informada por ela mesma no acordo. A plataforma nunca a usa '
  'para pagar (não movimenta dinheiro): ela aparece na instrução de pagamento para quem paga.';

-- ============================================================================ 3. acordo: participação de autoria e versão econômica congelada
ALTER TABLE signed_agreements
  ADD COLUMN proponent_participation_bps smallint NOT NULL DEFAULT 0 CHECK (proponent_participation_bps BETWEEN 0 AND 10000),
  ADD COLUMN economic_rule_version text,
  ADD COLUMN proponent_participation_id uuid;

-- ============================================================================ 4. participação de autoria (entidade própria, com estados)
CREATE TABLE proponent_participations (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id         uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,       -- executora (dona do projeto)
  proponent_org_id   uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,      -- quem propôs (pessoa física, OSC, profissional)
  proponent_user_id  uuid REFERENCES users(id) ON DELETE SET NULL,
  idea_ref_type      text NOT NULL CHECK (idea_ref_type IN ('solution','idea')),
  idea_ref_id        uuid NOT NULL,
  authorship_type    text NOT NULL CHECK (authorship_type IN ('author','coauthor')),
  share_bps          integer NOT NULL DEFAULT 10000 CHECK (share_bps BETWEEN 1 AND 10000),  -- fração da participação entre vários proponentes
  contribution       text NOT NULL CHECK (length(contribution) BETWEEN 20 AND 2000),
  status             text NOT NULL DEFAULT 'proposed' CHECK (status IN (
                       'proposed','under_review','accepted','consolidated','validated','eligible',
                       'accrued','payable','paid','disputed','cancelled')),
  accepted_by        uuid REFERENCES users(id) ON DELETE SET NULL,   -- quem ACEITA é o proponente (confirma a autoria e o combinado)
  accepted_at        timestamptz,
  consolidated_at    timestamptz,
  validated_at       timestamptz,
  cancelled_reason   text CHECK (length(cancelled_reason) <= 1000),
  agreement_id       uuid REFERENCES signed_agreements(id) ON DELETE SET NULL,
  created_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT proponent_is_not_executor CHECK (proponent_org_id <> org_id),
  CONSTRAINT accepted_has_actor CHECK (status IN ('proposed','under_review','cancelled') OR accepted_by IS NOT NULL)
);
CREATE INDEX ix_participations_project ON proponent_participations(project_id);
CREATE INDEX ix_participations_proponent ON proponent_participations(proponent_org_id, status);
-- Soma das frações de um projeto não passa de 100%.
CREATE FUNCTION participation_share_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE total integer;
BEGIN
  SELECT coalesce(sum(share_bps), 0) INTO total FROM proponent_participations
   WHERE project_id = NEW.project_id AND id <> NEW.id AND status NOT IN ('cancelled','disputed');
  IF NEW.status NOT IN ('cancelled','disputed') AND total + NEW.share_bps > 10000 THEN
    RAISE EXCEPTION 'as frações de participação do projeto passam de 100%% (já há % bps)', total USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_participation_share BEFORE INSERT OR UPDATE OF share_bps, status ON proponent_participations
  FOR EACH ROW EXECUTE FUNCTION participation_share_guard();
-- Grafo de estados: nenhum salto; aceite só pelo proponente; cancelamento exige motivo.
CREATE FUNCTION participation_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  NEW.updated_at := now();
  IF NEW.status = OLD.status THEN RETURN NEW; END IF;
  ok := CASE OLD.status
    WHEN 'proposed'     THEN NEW.status IN ('under_review','accepted','cancelled')
    WHEN 'under_review' THEN NEW.status IN ('accepted','cancelled')
    WHEN 'accepted'     THEN NEW.status IN ('consolidated','cancelled','disputed')
    WHEN 'consolidated' THEN NEW.status IN ('eligible','validated','cancelled','disputed')
    WHEN 'eligible'     THEN NEW.status IN ('accrued','validated','consolidated','cancelled','disputed')
    WHEN 'validated'    THEN NEW.status IN ('eligible','accrued','payable','disputed','cancelled')
    WHEN 'accrued'      THEN NEW.status IN ('payable','paid','validated','consolidated','disputed','cancelled')   -- 'paid' direto: quem financia repassa quando quiser
    WHEN 'payable'      THEN NEW.status IN ('paid','disputed','cancelled')
    WHEN 'disputed'     THEN NEW.status IN ('accepted','consolidated','eligible','accrued','payable','cancelled')
    ELSE false END;
  IF NOT ok THEN
    RAISE EXCEPTION 'transição de participação inválida: % -> %', OLD.status, NEW.status USING ERRCODE = '23514';
  END IF;
  IF NEW.status = 'accepted' AND NEW.accepted_by IS NULL THEN
    RAISE EXCEPTION 'aceite da participação exige quem aceitou (o proponente)' USING ERRCODE = '23514';
  END IF;
  IF NEW.status = 'cancelled' AND coalesce(length(NEW.cancelled_reason), 0) < 10 THEN
    RAISE EXCEPTION 'cancelar participação exige motivo' USING ERRCODE = '23514';
  END IF;
  IF NEW.status = 'accepted' AND NEW.accepted_at IS NULL THEN NEW.accepted_at := now(); END IF;
  IF NEW.status = 'consolidated' AND NEW.consolidated_at IS NULL THEN NEW.consolidated_at := now(); END IF;
  IF NEW.status = 'validated' AND NEW.validated_at IS NULL THEN NEW.validated_at := now(); END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_participation_state BEFORE UPDATE ON proponent_participations FOR EACH ROW EXECUTE FUNCTION participation_state_guard();
ALTER TABLE proponent_participations ENABLE ROW LEVEL SECURITY;
CREATE POLICY ppart_read ON proponent_participations FOR SELECT
  USING (org_id = app_org() OR proponent_org_id = app_org() OR app_project_investor(project_id) OR app_priv());
CREATE POLICY ppart_insert ON proponent_participations FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY ppart_update ON proponent_participations FOR UPDATE
  USING (org_id = app_org() OR proponent_org_id = app_org() OR app_priv())
  WITH CHECK (org_id = app_org() OR proponent_org_id = app_org() OR app_priv());
ALTER TABLE signed_agreements ADD CONSTRAINT fk_agreement_participation
  FOREIGN KEY (proponent_participation_id) REFERENCES proponent_participations(id) ON DELETE SET NULL;

-- ============================================================================ 5. matriz: linha de participação e soma fechada
ALTER TABLE agreement_allocations
  ADD COLUMN proponent_cents bigint NOT NULL DEFAULT 0 CHECK (proponent_cents >= 0),
  ADD COLUMN proponent_bps integer CHECK (proponent_bps IS NULL OR proponent_bps BETWEEN 0 AND 10000),
  ADD COLUMN economic_layer_cents bigint GENERATED ALWAYS AS (platform_fee_cents + proponent_cents) STORED;
ALTER TABLE agreement_allocations DROP CONSTRAINT allocation_sums;
ALTER TABLE agreement_allocations ADD CONSTRAINT allocation_sums CHECK (
  (fee_mode = 'deducted'   AND project_cents + platform_fee_cents + proponent_cents + third_party_cents = gross_cents) OR
  (fee_mode = 'additional' AND project_cents + proponent_cents + third_party_cents = gross_cents));

-- ============================================================================ 6. instruções de pagamento por destinatário (não custodial)
CREATE TABLE allocation_payouts (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  allocation_id      uuid NOT NULL REFERENCES agreement_allocations(id) ON DELETE CASCADE,
  agreement_id       uuid NOT NULL REFERENCES signed_agreements(id) ON DELETE CASCADE,
  org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,     -- dona do acordo (tenant)
  line_kind          text NOT NULL CHECK (line_kind IN ('project','platform_fee','proponent','third_party')),
  payer_org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  recipient_org_id   uuid REFERENCES organizations(id) ON DELETE RESTRICT,            -- NULL = plataforma
  recipient_label    text NOT NULL CHECK (length(recipient_label) BETWEEN 3 AND 200),
  amount_cents       bigint NOT NULL CHECK (amount_cents >= 0),
  pix_key_snapshot   text,                                                              -- chave informada no contrato, no momento da instrução
  pix_key_type       text,
  state              text NOT NULL DEFAULT 'instruction_created' CHECK (state IN (
                       'awaiting_rule',          -- linha da plataforma com regra comercial desligada: registrada, não exigível
                       'instruction_created',    -- instrução emitida: quem paga sabe para quem, quanto e por qual chave
                       'payment_pending',        -- quem paga registrou a transferência; falta quem recebe confirmar
                       'confirmed',              -- quem recebe confirmou o recebimento (soma >= valor)
                       'reconciled',             -- conciliado com extrato ou conferência manual auditada
                       'failed','disputed','cancelled','refund_pending','refunded')),
  paid_cents         bigint NOT NULL DEFAULT 0 CHECK (paid_cents >= 0),
  confirmed_cents    bigint NOT NULL DEFAULT 0 CHECK (confirmed_cents >= 0),
  due_on             date,
  confirmed_at       timestamptz,
  reconciled_at      timestamptz,
  reconciled_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  reconciliation_note text CHECK (length(reconciliation_note) <= 1000),
  platform_charge_id uuid REFERENCES platform_charges(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (allocation_id, line_kind, recipient_org_id)
);
CREATE INDEX ix_payouts_agreement ON allocation_payouts(agreement_id);
CREATE INDEX ix_payouts_payer ON allocation_payouts(payer_org_id, state);
CREATE INDEX ix_payouts_recipient ON allocation_payouts(recipient_org_id, state);
CREATE FUNCTION payout_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  NEW.updated_at := now();
  IF NEW.state = OLD.state THEN RETURN NEW; END IF;
  ok := CASE OLD.state
    WHEN 'awaiting_rule'       THEN NEW.state IN ('instruction_created','cancelled')
    WHEN 'instruction_created' THEN NEW.state IN ('payment_pending','cancelled','failed')
    WHEN 'payment_pending'     THEN NEW.state IN ('confirmed','failed','disputed','cancelled','payment_pending')
    WHEN 'confirmed'           THEN NEW.state IN ('reconciled','disputed','refund_pending')
    WHEN 'reconciled'          THEN NEW.state IN ('disputed','refund_pending')
    WHEN 'disputed'            THEN NEW.state IN ('confirmed','reconciled','refund_pending','cancelled','payment_pending')
    WHEN 'failed'              THEN NEW.state IN ('instruction_created','cancelled')
    WHEN 'refund_pending'      THEN NEW.state IN ('refunded','disputed')
    ELSE false END;
  IF NOT ok THEN
    RAISE EXCEPTION 'transição de repasse inválida: % -> %', OLD.state, NEW.state USING ERRCODE = '23514';
  END IF;
  -- "Confirmado" só com confirmação de quem recebe cobrindo o valor: criar registro não é pagar.
  IF NEW.state = 'confirmed' AND NEW.confirmed_cents < NEW.amount_cents THEN
    RAISE EXCEPTION 'repasse só fica confirmado quando quem recebe confirmou o valor inteiro (% de %)', NEW.confirmed_cents, NEW.amount_cents
      USING ERRCODE = '23514';
  END IF;
  IF NEW.state = 'confirmed' AND NEW.confirmed_at IS NULL THEN NEW.confirmed_at := now(); END IF;
  IF NEW.state = 'reconciled' AND (NEW.reconciled_by IS NULL OR NEW.reconciliation_note IS NULL) THEN
    RAISE EXCEPTION 'conciliar exige quem conciliou e a nota (extrato, linha ou conferência manual)' USING ERRCODE = '23514';
  END IF;
  IF NEW.state = 'reconciled' AND NEW.reconciled_at IS NULL THEN NEW.reconciled_at := now(); END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_payout_state BEFORE UPDATE ON allocation_payouts FOR EACH ROW EXECUTE FUNCTION payout_state_guard();
CREATE FUNCTION payout_immutable_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.amount_cents, NEW.payer_org_id, NEW.recipient_org_id, NEW.line_kind, NEW.allocation_id)
     IS DISTINCT FROM (OLD.amount_cents, OLD.payer_org_id, OLD.recipient_org_id, OLD.line_kind, OLD.allocation_id) THEN
    RAISE EXCEPTION 'valor, partes e linha da instrução são imutáveis (a matriz é a fonte)' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_payout_immutable BEFORE UPDATE ON allocation_payouts FOR EACH ROW EXECUTE FUNCTION payout_immutable_guard();
ALTER TABLE allocation_payouts ENABLE ROW LEVEL SECURITY;
CREATE POLICY payouts_read ON allocation_payouts FOR SELECT
  USING (app_priv() OR org_id = app_org() OR payer_org_id = app_org() OR recipient_org_id = app_org()
         OR agreement_has_party(agreement_id, app_org()));
CREATE POLICY payouts_insert ON allocation_payouts FOR INSERT WITH CHECK (app_priv());
CREATE POLICY payouts_update ON allocation_payouts FOR UPDATE
  USING (app_priv() OR payer_org_id = app_org() OR recipient_org_id = app_org())
  WITH CHECK (app_priv() OR payer_org_id = app_org() OR recipient_org_id = app_org());

-- Transferências registradas por quem paga (a qualquer momento) e confirmadas por quem recebe.
CREATE TABLE payout_transfers (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  payout_id          uuid NOT NULL REFERENCES allocation_payouts(id) ON DELETE CASCADE,
  org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,     -- tenant do acordo
  amount_cents       bigint NOT NULL CHECK (amount_cents > 0),
  reference          text NOT NULL CHECK (length(reference) BETWEEN 3 AND 120),       -- E2E/ID da transferência, comprovante
  paid_on            date NOT NULL,
  method             text NOT NULL DEFAULT 'pix' CHECK (method IN ('pix','bank_transfer','other')),
  evidence_document_id uuid REFERENCES documents(id) ON DELETE SET NULL,
  registered_by_org  uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  registered_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  status             text NOT NULL DEFAULT 'registered' CHECK (status IN ('registered','confirmed','rejected')),
  confirmed_by_org   uuid REFERENCES organizations(id) ON DELETE SET NULL,
  confirmed_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  confirmed_at       timestamptz,
  rejection_reason   text CHECK (length(rejection_reason) <= 1000),
  created_at         timestamptz NOT NULL DEFAULT now(),
  -- Idempotência: a mesma referência no mesmo repasse é a mesma transferência, não uma segunda.
  UNIQUE (payout_id, reference),
  CONSTRAINT confirm_is_not_payer CHECK (confirmed_by_org IS NULL OR confirmed_by_org <> registered_by_org),
  CONSTRAINT rejected_has_reason CHECK (status <> 'rejected' OR length(coalesce(rejection_reason, '')) >= 10)
);
CREATE INDEX ix_transfers_payout ON payout_transfers(payout_id);
CREATE FUNCTION transfer_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.amount_cents, NEW.reference, NEW.paid_on, NEW.payout_id, NEW.registered_by_org)
     IS DISTINCT FROM (OLD.amount_cents, OLD.reference, OLD.paid_on, OLD.payout_id, OLD.registered_by_org) THEN
    RAISE EXCEPTION 'transferência registrada é imutável; registre outra ou recuse esta' USING ERRCODE = '23514';
  END IF;
  IF OLD.status <> 'registered' AND NEW.status <> OLD.status THEN
    RAISE EXCEPTION 'transferência já decidida (%)', OLD.status USING ERRCODE = '23514';
  END IF;
  IF NEW.status = 'confirmed' AND (NEW.confirmed_by IS NULL OR NEW.confirmed_by_org IS NULL) THEN
    RAISE EXCEPTION 'confirmar exige quem confirmou e a organização que recebe' USING ERRCODE = '23514';
  END IF;
  IF NEW.status = 'confirmed' AND NEW.confirmed_at IS NULL THEN NEW.confirmed_at := now(); END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_transfer_guard BEFORE UPDATE ON payout_transfers FOR EACH ROW EXECUTE FUNCTION transfer_guard();
ALTER TABLE payout_transfers ENABLE ROW LEVEL SECURITY;
CREATE POLICY transfers_read ON payout_transfers FOR SELECT
  USING (app_priv() OR org_id = app_org() OR registered_by_org = app_org()
         OR EXISTS (SELECT 1 FROM allocation_payouts p WHERE p.id = payout_id AND (p.recipient_org_id = app_org() OR p.payer_org_id = app_org())));
CREATE POLICY transfers_insert ON payout_transfers FOR INSERT
  WITH CHECK (app_priv() OR (registered_by_org = app_org()
              AND EXISTS (SELECT 1 FROM allocation_payouts p WHERE p.id = payout_id AND p.payer_org_id = app_org())));
CREATE POLICY transfers_update ON payout_transfers FOR UPDATE
  USING (app_priv() OR EXISTS (SELECT 1 FROM allocation_payouts p WHERE p.id = payout_id AND p.recipient_org_id = app_org()))
  WITH CHECK (app_priv() OR EXISTS (SELECT 1 FROM allocation_payouts p WHERE p.id = payout_id AND p.recipient_org_id = app_org()));

-- ============================================================================ 7. ledger econômico (append-only, idempotente)
CREATE TABLE economic_events (
  seq               bigserial PRIMARY KEY,
  id                uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
  kind              text NOT NULL CHECK (kind IN (
                      'platform_service_registered',   -- camada da plataforma calculada e congelada na matriz
                      'platform_service_due',          -- regra ativa: cobrança própria aberta
                      'platform_service_paid',         -- quitação confirmada pela plataforma
                      'proponent_participation_accrued',
                      'proponent_participation_paid',
                      'project_funds_instructed',
                      'project_funds_confirmed',
                      'operation_settled',
                      'reversal')),
  org_id            uuid REFERENCES organizations(id) ON DELETE SET NULL,     -- tenant (dona do acordo)
  agreement_id      uuid REFERENCES signed_agreements(id) ON DELETE SET NULL,
  allocation_id     uuid REFERENCES agreement_allocations(id) ON DELETE SET NULL,
  payout_id         uuid REFERENCES allocation_payouts(id) ON DELETE SET NULL,
  rule_key          text,
  pricing_version   text,
  bps               integer,
  base_cents        bigint,
  amount_cents      bigint NOT NULL,
  payer_org_id      uuid REFERENCES organizations(id) ON DELETE SET NULL,
  recipient_org_id  uuid REFERENCES organizations(id) ON DELETE SET NULL,     -- NULL = plataforma
  reverses_seq      bigint REFERENCES economic_events(seq),
  idempotency_key   text NOT NULL UNIQUE,
  payload           jsonb NOT NULL DEFAULT '{}'::jsonb,
  actor_user_id     uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT reversal_shape CHECK ((kind = 'reversal') = (reverses_seq IS NOT NULL))
);
COMMENT ON TABLE economic_events IS
  'Quem → pagou → quem → quanto → por quê → com base em qual regra e versão → em qual evento → quando. Append-only; '
  'correção é evento de estorno (reversal) com o valor oposto. GMV não entra aqui como receita: receita da plataforma '
  'é só platform_service_paid.';
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON economic_events FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER trg_no_truncate_economic BEFORE TRUNCATE ON economic_events EXECUTE FUNCTION forbid_truncate();
ALTER TABLE economic_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY econ_read ON economic_events FOR SELECT
  USING (app_priv() OR org_id = app_org() OR payer_org_id = app_org() OR recipient_org_id = app_org());
CREATE POLICY econ_insert ON economic_events FOR INSERT
  WITH CHECK (app_priv() OR org_id = app_org() OR payer_org_id = app_org() OR recipient_org_id = app_org());

-- ============================================================================ 8. reconhecimentos por conclusão e quitação
CREATE TABLE recognitions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  kind         text NOT NULL CHECK (kind IN (
                 'operation_settled',        -- acordo concluído (todas as entregas aceitas) E todos os repasses confirmados
                 'funding_settled',          -- financiador: aporte integralmente confirmado pelos destinatários
                 'delivery_accepted',        -- executora/profissional: entrega aceita pela outra parte
                 'participation_paid',       -- proponente: participação de autoria quitada
                 'evidence_validated')),     -- medição validada por outra parte
  ref_type     text NOT NULL,
  ref_id       uuid NOT NULL,
  project_id   uuid REFERENCES projects(id) ON DELETE SET NULL,
  amount_cents bigint,
  evidence     jsonb NOT NULL DEFAULT '{}'::jsonb,
  granted_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, kind, ref_type, ref_id)
);
COMMENT ON TABLE recognitions IS
  'Créditos de trajetória: nascem SÓ de conclusão e quitação registradas (entrega aceita, repasse confirmado por quem '
  'recebe, participação paga). Nunca de pagamento à plataforma, de plano ou de voucher — não existe pay-to-win.';
CREATE INDEX ix_recognitions_org ON recognitions(org_id, kind);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON recognitions FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();
ALTER TABLE recognitions ENABLE ROW LEVEL SECURITY;
CREATE POLICY recog_read ON recognitions FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY recog_insert ON recognitions FOR INSERT WITH CHECK (app_priv() OR app_authenticated());

-- ============================================================================ 9. razão do projeto: tipos novos
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
  'payout_instructed','payout_registered','payout_confirmed','payout_reconciled','operation_settled','recognition_granted'));

-- ============================================================================ 10. eventos de valor novos (Value Ledger)
INSERT INTO value_event_types(key, label_pt, unit_label, what_counts) VALUES
  ('contract.activated', 'Acordo em vigor com regras derivadas', 'acordo',
   'Cada acordo que entrou em vigor com obrigações, prazos e matriz de distribuição derivados do contrato.'),
  ('allocation.instructed', 'Matriz de distribuição instruída', 'instrução',
   'Cada instrução de repasse emitida com destinatário, valor e chave informada no contrato.'),
  ('payout.confirmed', 'Repasse confirmado por quem recebe', 'repasse',
   'Cada repasse cuja confirmação veio de quem recebeu, não de quem pagou.'),
  ('operation.settled', 'Operação concluída e quitada', 'operação',
   'Cada acordo com todas as entregas aceitas e todos os repasses confirmados.')
ON CONFLICT (key) DO NOTHING;

-- ============================================================================ 11. grants
GRANT SELECT ON economic_rules TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON proponent_participations TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON allocation_payouts, payout_transfers TO impacto_app;
GRANT SELECT, INSERT ON economic_events, recognitions TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE economic_events_seq_seq TO impacto_app;
