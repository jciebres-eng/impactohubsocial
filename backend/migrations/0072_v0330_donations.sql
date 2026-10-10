-- 0072 — v0.33.0 — DOAÇÕES, CAMPANHAS DE ARRECADAÇÃO E ESPELHO DE CONCILIAÇÃO (ADR-372 a ADR-376)
--
-- O que esta migração É: o registro de campanhas de arrecadação (pontual e recorrente), das doações que
-- um provedor de pagamento confirma, dos eventos que ele envia, dos lançamentos de conciliação e da
-- prestação de contas — tudo sem a plataforma segurar dinheiro de ninguém (NON_CUSTODIAL_ARCHITECTURE.md §0).
--
-- O que esta migração NÃO É:
--   * não cria saldo: `donation_ledger_entries` é append-only e o "saldo" de uma campanha é SOMA
--     calculada, rotulada "contábil estimado" até a conciliação com o provedor (ADR-374);
--   * não liga cobrança: o único provedor que existe é `sandbox`, e `is_simulated` é DERIVADA do
--     provedor por gatilho (mesmo desenho de platform_charges, 0020); um provedor real só entra por
--     adaptador, com credencial no cofre e feature flag `live_payment_provider_enabled`;
--   * não cobra taxa: as regras `donation.platform_fee` (1 %) e `donation.beneficiary_fund` (até 4 %)
--     entram no catálogo como HIPÓTESE, `review_required`, carta amarela, INATIVAS — como todas as outras;
--   * não decide quem pode receber: `beneficiary_verifications` guarda o estado da verificação, e uma
--     campanha só é publicada com verificação `verified` (gatilho), mas QUEM verifica e COM QUE documentos
--     depende do provedor e do parecer (BLOCKED_LEGAL / BLOCKED_PROVIDER).
--
-- Reutiliza: `campaigns` (0004) ganha tipo, meta, prazo, beneficiário, política e revisão — não nasce
-- uma segunda tabela de campanha. `risk_assessments`/`risk_signals` continuam para organizações;
-- `donation_risk_cases` é o caso por doação/campanha, com revisão humana.

-- ============================================================================ 1. campanhas: o que faltava
ALTER TABLE campaigns
  ADD COLUMN kind              text NOT NULL DEFAULT 'project_crowdfunding'
    CHECK (kind IN ('project_crowdfunding','emergency','institutional_fund','recurring','organization')),
  ADD COLUMN target_cents      bigint CHECK (target_cents IS NULL OR target_cents > 0),
  ADD COLUMN currency          char(3) NOT NULL DEFAULT 'BRL' CHECK (currency = 'BRL'),
  ADD COLUMN starts_on         date,
  ADD COLUMN ends_on           date,
  ADD COLUMN beneficiary_org_id uuid REFERENCES organizations(id) ON DELETE RESTRICT,
  ADD COLUMN purpose           text CHECK (length(purpose) <= 2000),          -- destino declarado dos recursos
  ADD COLUMN contingency_policy text CHECK (length(contingency_policy) <= 2000), -- se a meta não for atingida / sobrar
  ADD COLUMN refund_policy     text CHECK (length(refund_policy) <= 2000),
  ADD COLUMN policy_version    text,                                           -- versão dos termos de campanha aceitos
  ADD COLUMN accepted_terms_at timestamptz,
  ADD COLUMN review_note       text CHECK (length(review_note) <= 2000),
  ADD COLUMN reviewed_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN reviewed_at       timestamptz,
  ADD COLUMN qr_version        integer NOT NULL DEFAULT 1 CHECK (qr_version >= 1),  -- regenerar QR/link = versão nova
  ADD COLUMN min_donation_cents bigint NOT NULL DEFAULT 500 CHECK (min_donation_cents >= 100),
  ADD COLUMN allow_recurring   boolean NOT NULL DEFAULT false;
UPDATE campaigns SET beneficiary_org_id = org_id WHERE beneficiary_org_id IS NULL;
ALTER TABLE campaigns ALTER COLUMN beneficiary_org_id SET NOT NULL;
ALTER TABLE campaigns ALTER COLUMN project_id DROP NOT NULL;   -- campanha de organização/fundo não tem projeto
ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS campaigns_project_id_key;
CREATE UNIQUE INDEX ux_campaigns_project ON campaigns(project_id) WHERE project_id IS NOT NULL;
ALTER TABLE campaigns DROP CONSTRAINT campaigns_status_check;
ALTER TABLE campaigns ADD CONSTRAINT campaigns_status_check CHECK (status IN (
  'draft','pending_review','approved','published','paused','target_reached','ended','under_review','rejected','cancelled','refunding','closed'));
ALTER TABLE campaigns ADD CONSTRAINT campaign_dates CHECK (starts_on IS NULL OR ends_on IS NULL OR ends_on >= starts_on);
COMMENT ON COLUMN campaigns.status IS
  'draft → pending_review → approved → published → (paused|target_reached|ended|under_review) → closed; rejected/cancelled/refunding '
  'são desvios. `published` (0004) continua sendo o estado público; a máquina está em campaign_state_guard().';

-- ============================================================================ 2. verificação do beneficiário
CREATE TABLE beneficiary_verifications (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  status        text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','documents_requested','under_review','verified','rejected','expired')),
  provider      text NOT NULL DEFAULT 'manual' CHECK (provider IN ('manual','sandbox')),  -- provedor real: adaptador + ADR
  provider_ref  text CHECK (length(provider_ref) <= 200),
  -- Só REFERÊNCIAS a documentos já guardados (tabela documents, antivírus, quarentena); nunca documento cru aqui.
  evidence_document_ids uuid[] NOT NULL DEFAULT '{}',
  account_holder_matches boolean,   -- titularidade da conta de recebimento confere com a organização (quem confirma: provedor)
  reviewed_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at   timestamptz,
  review_note   text CHECK (length(review_note) <= 2000),
  expires_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT verified_has_reviewer CHECK (status <> 'verified' OR reviewed_by IS NOT NULL)
);
CREATE INDEX ix_benef_verif_org ON beneficiary_verifications(org_id, status);
CREATE TRIGGER trg_touch BEFORE UPDATE ON beneficiary_verifications FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
ALTER TABLE beneficiary_verifications ENABLE ROW LEVEL SECURITY;
CREATE POLICY benef_verif_read ON beneficiary_verifications FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY benef_verif_write ON beneficiary_verifications FOR ALL USING (app_priv()) WITH CHECK (app_priv());

CREATE FUNCTION beneficiary_verified(p_org uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT EXISTS (SELECT 1 FROM beneficiary_verifications
                 WHERE org_id = p_org AND status = 'verified' AND (expires_at IS NULL OR expires_at > now()))
$$;

-- ============================================================================ 3. máquina de estados da campanha
CREATE FUNCTION campaign_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
    ok := CASE OLD.status
      WHEN 'draft'          THEN NEW.status IN ('pending_review','cancelled')
      WHEN 'pending_review' THEN NEW.status IN ('approved','rejected','draft')
      WHEN 'approved'       THEN NEW.status IN ('published','draft','cancelled')
      WHEN 'published'      THEN NEW.status IN ('paused','target_reached','ended','under_review','closed')
      WHEN 'paused'         THEN NEW.status IN ('published','ended','under_review','closed')
      WHEN 'target_reached' THEN NEW.status IN ('published','ended','closed')
      WHEN 'ended'          THEN NEW.status IN ('closed','refunding')
      WHEN 'under_review'   THEN NEW.status IN ('published','paused','rejected','refunding','closed')
      WHEN 'rejected'       THEN NEW.status IN ('draft')
      WHEN 'refunding'      THEN NEW.status IN ('closed')
      ELSE false END;
    IF NOT ok THEN
      RAISE EXCEPTION 'transição de campanha não permitida: % → %', OLD.status, NEW.status USING ERRCODE = '23514';
    END IF;
    -- Aprovar exige revisor nomeado e motivo; publicar exige beneficiário verificado e termos aceitos.
    IF NEW.status IN ('approved','rejected') AND (NEW.reviewed_by IS NULL OR coalesce(NEW.review_note, '') = '') THEN
      RAISE EXCEPTION 'aprovar ou rejeitar campanha exige revisor e justificativa' USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'published' AND OLD.status = 'approved' THEN
      IF NOT beneficiary_verified(NEW.beneficiary_org_id) THEN
        RAISE EXCEPTION 'campanha só é publicada com beneficiário verificado' USING ERRCODE = '23514';
      END IF;
      IF NEW.accepted_terms_at IS NULL OR NEW.policy_version IS NULL THEN
        RAISE EXCEPTION 'campanha só é publicada com os termos de campanha aceitos' USING ERRCODE = '23514';
      END IF;
      NEW.published_at := coalesce(NEW.published_at, now());
    END IF;
    IF NEW.status = 'closed' THEN NEW.closed_at := coalesce(NEW.closed_at, now()); END IF;
  END IF;
  -- Quem revisa não pode ser quem criou (quatro olhos).
  IF NEW.reviewed_by IS NOT NULL AND NEW.reviewed_by = NEW.created_by THEN
    RAISE EXCEPTION 'quem criou a campanha não a revisa' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_campaign_state BEFORE UPDATE ON campaigns FOR EACH ROW EXECUTE FUNCTION campaign_state_guard();

-- ============================================================================ 4. regras de taxa versionadas (hipótese, inativas)
-- O catálogo `monetization_rules` já é a fonte das regras comerciais. As duas hipóteses do pacote entram
-- nele; `fee_rule_versions` congela, por doação, QUAL versão de regra e de tarifa estava vigente.
INSERT INTO monetization_rules(
    key, label_pt, revenue_engine, engine_rank, payer_kind, trigger_kind, value_event_type,
    pricing_mode, percentage, currency, hypothesis_note, problem_solved, substitution_answer)
VALUES
 ('donation.platform_fee', 'Taxa de serviço sobre doação comunitária confirmada (campanha)', 'success_fee', 6,
  'individual', 'transaction', NULL, 'percentage', 1.00, 'BRL',
  'HIPÓTESE do pacote de monetização (09/10/2026): 1 % sobre doação confirmada, SE o arranjo for transparente ao doador, '
  'permitido pelo provedor e aceito nos termos da campanha. Para tickets baixos a tarifa fixa do provedor pode superar '
  '1 %: calcular margem por meio/ticket antes de ativar. Nunca deduzida de dinheiro em trânsito (ADR-337): faturada à '
  'organização beneficiária ou coberta por contribuição voluntária do doador (caixa nunca pré-marcada).',
  'Organizações arrecadam com página pública, QR e conciliação automática sem contratar um sistema de doações à parte '
  'nem reconciliar extrato à mão; o doador vê para quem, para quê e quanto chegou.',
  'Uma vaquinha genérica não liga a doação ao projeto, aos marcos, às evidências e à prestação de contas; o IMPACTO liga.'),
 ('donation.beneficiary_fund', 'Reserva para o fundo do beneficiário sobre doação comunitária (não é receita da plataforma)', 'success_fee', 6,
  'individual', 'transaction', NULL, 'percentage', 4.00, 'BRL',
  'HIPÓTESE do pacote (09/10/2026): até 4 % da doação destinados a reserva/fundo DA ORGANIZAÇÃO beneficiária, só se '
  'comunicado na campanha e autorizado. NÃO é receita da plataforma (mesma natureza da participação de autoria, ADR-337): '
  'entra no catálogo para ser calculada e exibida, nunca somada à receita.',
  'A organização constitui uma reserva declarada para continuidade do projeto, visível ao doador antes de doar.',
  'Sem a plataforma a reserva seria um lançamento interno invisível; aqui ela é calculada, exibida e conciliada.');
WITH c AS (
  INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature,
      contractual_relation, required_document, required_terms, cancellation_policy, refund_policy, tax_notes,
      invoice_notes, regulatory_notes, legal_basis, source_name, source_url, verified_on, open_questions, note)
  VALUES ('donation.platform_fee', 'yellow', 'low',
    'Organização beneficiária da campanha (ou o doador, por contribuição voluntária explícita)',
    'A plataforma (pessoa jurídica titular do software)',
    'Doação CONFIRMADA pelo provedor de pagamento (evento assinado e deduplicado); nunca pela tela do navegador',
    'Receita de serviço de software (arrecadação, conciliação, prestação de contas), faturada à parte — não é intermediação de pagamento',
    'Termos de campanha aceitos pela organização; termos de doação exibidos ao doador com o preço total antes de pagar',
    'Contrato/termos de campanha; nota fiscal de serviço à organização; comprovante de doação ao doador (não é "recibo dedutível" sem parecer)',
    'Termos de Uso, Termos de Campanha, Política de Doações e Reembolso, Política de Privacidade',
    'Taxa só é devida sobre doação confirmada e não estornada; estorno/chargeback reverte a taxa por lançamento novo',
    'Estorno/chargeback: reversão por lançamento; quem suporta a tarifa do provedor é definido no contrato',
    'ISS sobre serviço (LC 116/2003); doação ao beneficiário NÃO é receita da plataforma; dedutibilidade para o doador depende do caso e NÃO é prometida',
    'NFS-e obrigatória e NÃO implementada',
    'A plataforma não recebe, não guarda e não repassa a doação: o provedor liquida ao beneficiário. Enquadramento em arranjo de pagamento (Lei 12.865/2013), PLD/FT (Lei 9.613/1998, Circular BCB 3.978/2020) e captação pública (Lei 13.019/2014; Lei 9.790/1999) exigem parecer antes de qualquer doação real',
    'LC 116/2003; Lei 12.865/2013; Lei 9.613/1998; Lei 13.019/2014; CDC (Lei 8.078/1990)',
    'Planalto', 'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12865.htm', '2026-10-09',
    'Quem paga a taxa (organização × doador)? Pode ser cobrada "all-inclusive"? Tarifa fixa do provedor em tickets baixos? A plataforma é participante de arranjo de pagamento? Qual recibo o doador recebe?',
    'Carta AMARELA: regra registrada como hipótese; INATIVA; nenhuma doação real possível (só provedor sandbox).')
  RETURNING id)
UPDATE monetization_rules r SET legal_card_id = c.id FROM c WHERE r.key = 'donation.platform_fee';
WITH c AS (
  INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature,
      contractual_relation, required_document, required_terms, cancellation_policy, refund_policy, tax_notes,
      invoice_notes, regulatory_notes, legal_basis, source_name, source_url, verified_on, open_questions, note)
  VALUES ('donation.beneficiary_fund', 'yellow', 'low',
    'Doador (parte da doação, destinada pela organização ao seu fundo de continuidade, comunicada antes de doar)',
    'A ORGANIZAÇÃO beneficiária — nunca a plataforma',
    'Doação confirmada pelo provedor; a parcela é apenas CALCULADA e EXIBIDA (a organização a contabiliza internamente)',
    'Não é receita da plataforma: é destinação interna da organização, declarada ao doador',
    'Termos de campanha com a destinação declarada; aceite da organização',
    'Declaração de destinação na página da campanha e na prestação de contas',
    'Termos de Campanha',
    'Estorno reverte o cálculo; nada a devolver pela plataforma',
    'Estorno reverte o cálculo',
    'Contabilidade da organização (não da plataforma); parecer contábil sobre "reserva" e sobre a comunicação ao doador',
    'Nenhum documento fiscal da plataforma',
    'Nunca retida pela plataforma (ADR-284); a palavra "reserva" só pode ser usada com estrutura legal da própria organização',
    'Lei 13.019/2014; CDC (Lei 8.078/1990)', 'Planalto', 'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l13019.htm', '2026-10-09',
    'A organização pode declarar reserva percentual? Como aparece na prestação de contas? Base de cálculo bruta ou líquida?',
    'Carta AMARELA: hipótese; INATIVA; nunca somada à receita da plataforma.')
  RETURNING id)
UPDATE monetization_rules r SET legal_card_id = c.id FROM c WHERE r.key = 'donation.beneficiary_fund';

CREATE TABLE fee_rule_versions (
  id              bigserial PRIMARY KEY,
  rule_key        text NOT NULL REFERENCES monetization_rules(key) ON DELETE RESTRICT,
  version         integer NOT NULL CHECK (version >= 1),
  bps             integer NOT NULL CHECK (bps BETWEEN 0 AND 10000),     -- pontos-base (100 bps = 1 %)
  fixed_cents     bigint NOT NULL DEFAULT 0 CHECK (fixed_cents >= 0),
  base            text NOT NULL DEFAULT 'gross' CHECK (base IN ('gross','net_of_provider')),
  rounding        text NOT NULL DEFAULT 'half_even' CHECK (rounding IN ('half_even','floor')),
  effective_from  timestamptz NOT NULL DEFAULT now(),
  effective_to    timestamptz,
  legal_status    text NOT NULL DEFAULT 'hypothesis' CHECK (legal_status IN ('hypothesis','approved','retired')),
  note            text CHECK (length(note) <= 2000),
  created_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (rule_key, version)
);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON fee_rule_versions FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
ALTER TABLE fee_rule_versions ENABLE ROW LEVEL SECURITY;
CREATE POLICY fee_rule_versions_read ON fee_rule_versions FOR SELECT USING (true);
CREATE POLICY fee_rule_versions_priv ON fee_rule_versions FOR INSERT WITH CHECK (app_priv());
INSERT INTO fee_rule_versions(rule_key, version, bps, base, note) VALUES
  ('donation.platform_fee', 1, 100, 'gross', 'HIPÓTESE do pacote: 1 % sobre o bruto confirmado. Só para cálculo e exibição; a regra está inativa.'),
  ('donation.beneficiary_fund', 1, 400, 'gross', 'HIPÓTESE do pacote: até 4 % sobre o bruto confirmado; destinação da organização, não receita da plataforma.');

-- Tarifas do PROVEDOR: catálogo versionado; nasce só com o provedor sandbox e tarifa ZERO explícita.
-- Tarifa real vem do contrato (BLOCKED_PROVIDER); nunca um número presumido.
CREATE TABLE provider_fee_schedules (
  id              bigserial PRIMARY KEY,
  provider        text NOT NULL,
  method          text NOT NULL CHECK (method IN ('pix','card','boleto')),
  bps             integer NOT NULL CHECK (bps BETWEEN 0 AND 10000),
  fixed_cents     bigint NOT NULL DEFAULT 0 CHECK (fixed_cents >= 0),
  settlement_days integer NOT NULL DEFAULT 0 CHECK (settlement_days >= 0),
  source          text NOT NULL CHECK (length(source) BETWEEN 5 AND 300),   -- contrato/tabela e data
  effective_from  timestamptz NOT NULL DEFAULT now(),
  effective_to    timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON provider_fee_schedules FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
ALTER TABLE provider_fee_schedules ENABLE ROW LEVEL SECURITY;
CREATE POLICY provider_fee_read ON provider_fee_schedules FOR SELECT USING (true);
CREATE POLICY provider_fee_priv ON provider_fee_schedules FOR INSERT WITH CHECK (app_priv());
INSERT INTO provider_fee_schedules(provider, method, bps, fixed_cents, settlement_days, source) VALUES
  ('sandbox', 'pix', 0, 0, 0, 'Provedor de TESTE (sem tarifa): nenhum valor real; a tarifa real vem do contrato do provedor escolhido');

-- ============================================================================ 5. doações
CREATE TABLE donations (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id      uuid NOT NULL REFERENCES campaigns(id) ON DELETE RESTRICT,
  beneficiary_org_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  donor_user_id    uuid REFERENCES users(id) ON DELETE SET NULL,         -- doador com conta, se houver
  donor_display    text CHECK (length(donor_display) <= 120),            -- nome PÚBLICO escolhido
  donor_contact_enc text,                                                -- e-mail cifrado (FIELD_ENCRYPTION_KEY) para o comprovante; nunca público
  public_anonymous boolean NOT NULL DEFAULT false,                       -- perante o PÚBLICO; não perante provedor/lei
  amount_cents     bigint NOT NULL CHECK (amount_cents > 0),
  currency         char(3) NOT NULL DEFAULT 'BRL' CHECK (currency = 'BRL'),
  method           text NOT NULL CHECK (method IN ('pix','card','boleto')),
  provider         text NOT NULL,
  provider_charge_id text,                                               -- id da cobrança no provedor
  is_simulated     boolean NOT NULL DEFAULT true,                        -- DERIVADA do provedor (gatilho)
  status           text NOT NULL DEFAULT 'created' CHECK (status IN (
                     'created','awaiting_payment','confirmed','reconciled','expired','failed','cancelled',
                     'refund_pending','refunded','chargeback','under_review')),
  fee_rule_version_id bigint REFERENCES fee_rule_versions(id),           -- congelado na criação
  fund_rule_version_id bigint REFERENCES fee_rule_versions(id),
  provider_fee_schedule_id bigint REFERENCES provider_fee_schedules(id),
  platform_fee_cents bigint NOT NULL DEFAULT 0 CHECK (platform_fee_cents >= 0),   -- CALCULADO; devido só se a regra estiver ativa
  beneficiary_fund_cents bigint NOT NULL DEFAULT 0 CHECK (beneficiary_fund_cents >= 0),
  provider_fee_cents bigint NOT NULL DEFAULT 0 CHECK (provider_fee_cents >= 0),
  cover_costs_opt_in boolean NOT NULL DEFAULT false,                     -- contribuição voluntária; NUNCA pré-marcada
  cover_costs_cents bigint NOT NULL DEFAULT 0 CHECK (cover_costs_cents >= 0),
  recurring_agreement_id uuid,
  qr_version       integer NOT NULL DEFAULT 1,
  idempotency_key  text,                                                 -- do cliente, evita doação duplicada por clique duplo
  confirmed_at     timestamptz,
  expires_at       timestamptz,
  risk_case_id     uuid,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT fee_within_amount CHECK (platform_fee_cents + beneficiary_fund_cents + provider_fee_cents <= amount_cents + cover_costs_cents),
  CONSTRAINT cover_costs_consent CHECK (cover_costs_cents = 0 OR cover_costs_opt_in)
);
CREATE UNIQUE INDEX ux_donation_provider_charge ON donations(provider, provider_charge_id) WHERE provider_charge_id IS NOT NULL;
CREATE UNIQUE INDEX ux_donation_idem ON donations(campaign_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX ix_donations_campaign ON donations(campaign_id, status);
CREATE INDEX ix_donations_donor ON donations(donor_user_id) WHERE donor_user_id IS NOT NULL;
CREATE TRIGGER trg_touch BEFORE UPDATE ON donations FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- is_simulated é DERIVADA do provedor: provedores reais entram nesta lista por ADR, com adaptador testado.
CREATE FUNCTION donation_simulated_flag() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_derived boolean := NEW.provider NOT IN ('asaas','mercadopago','pagarme','stripe');
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.is_simulated IS DISTINCT FROM OLD.is_simulated THEN
    RAISE EXCEPTION 'is_simulated é derivada do provedor (%): não se escreve à mão', NEW.provider USING ERRCODE = '42501';
  END IF;
  NEW.is_simulated := v_derived;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_donation_simulated BEFORE INSERT OR UPDATE ON donations FOR EACH ROW EXECUTE FUNCTION donation_simulated_flag();

-- Máquina de estados: confirmação só vem de evento do provedor (a API não aceita "pago" vindo do navegador);
-- valores confirmados não mudam; reembolso/chargeback só depois de confirmado.
CREATE FUNCTION donation_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE ok boolean;
BEGIN
  IF NEW.status IS DISTINCT FROM OLD.status THEN
    ok := CASE OLD.status
      WHEN 'created'          THEN NEW.status IN ('awaiting_payment','cancelled','failed','expired')
      WHEN 'awaiting_payment' THEN NEW.status IN ('confirmed','expired','failed','cancelled','under_review')
      WHEN 'under_review'     THEN NEW.status IN ('confirmed','failed','cancelled','refund_pending')
      WHEN 'confirmed'        THEN NEW.status IN ('reconciled','refund_pending','chargeback','under_review')
      WHEN 'reconciled'       THEN NEW.status IN ('refund_pending','chargeback')
      WHEN 'refund_pending'   THEN NEW.status IN ('refunded','reconciled')
      ELSE false END;
    IF NOT ok THEN
      RAISE EXCEPTION 'transição de doação não permitida: % → %', OLD.status, NEW.status USING ERRCODE = '23514';
    END IF;
    IF NEW.status = 'confirmed' THEN NEW.confirmed_at := coalesce(NEW.confirmed_at, now()); END IF;
  END IF;
  IF OLD.status IN ('confirmed','reconciled','refunded','chargeback') AND
     (NEW.amount_cents <> OLD.amount_cents OR NEW.currency <> OLD.currency OR NEW.provider <> OLD.provider
      OR NEW.provider_charge_id IS DISTINCT FROM OLD.provider_charge_id OR NEW.campaign_id <> OLD.campaign_id) THEN
    RAISE EXCEPTION 'doação confirmada não muda de valor, provedor, cobrança ou campanha' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_donation_state BEFORE UPDATE ON donations FOR EACH ROW EXECUTE FUNCTION donation_state_guard();

ALTER TABLE donations ENABLE ROW LEVEL SECURITY;
-- Beneficiária vê as suas (sem contato do doador: a coluna cifrada só sai por função própria); doador vê as dele.
CREATE POLICY donations_read ON donations FOR SELECT USING (
  beneficiary_org_id = app_org() OR (donor_user_id IS NOT NULL AND donor_user_id = app_uid()) OR app_priv());
CREATE POLICY donations_priv ON donations FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- ============================================================================ 6. acordos de doação recorrente
CREATE TABLE recurring_donation_agreements (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id      uuid NOT NULL REFERENCES campaigns(id) ON DELETE RESTRICT,
  donor_user_id    uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,  -- recorrência exige conta e consentimento
  amount_cents     bigint NOT NULL CHECK (amount_cents > 0),
  cadence          text NOT NULL CHECK (cadence IN ('monthly')),
  method           text NOT NULL CHECK (method IN ('card','pix_automatic')),
  provider         text NOT NULL,
  provider_token_ref text,                                                -- referência do instrumento NO PROVEDOR; nunca dado de cartão
  consent_at       timestamptz NOT NULL DEFAULT now(),
  consent_text_sha256 char(64) NOT NULL,
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','paused','cancelled','failed')),
  next_charge_on   date,
  cancelled_at     timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_recurring_donor ON recurring_donation_agreements(donor_user_id, status);
CREATE TRIGGER trg_touch BEFORE UPDATE ON recurring_donation_agreements FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
ALTER TABLE recurring_donation_agreements ENABLE ROW LEVEL SECURITY;
CREATE POLICY recurring_read ON recurring_donation_agreements FOR SELECT USING (donor_user_id = app_uid() OR app_priv()
  OR EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.beneficiary_org_id = app_org()));
CREATE POLICY recurring_donor ON recurring_donation_agreements FOR UPDATE USING (donor_user_id = app_uid() OR app_priv())
  WITH CHECK (donor_user_id = app_uid() OR app_priv());
CREATE POLICY recurring_priv ON recurring_donation_agreements FOR INSERT WITH CHECK (app_priv());
ALTER TABLE donations ADD CONSTRAINT donations_recurring_fk FOREIGN KEY (recurring_agreement_id)
  REFERENCES recurring_donation_agreements(id) ON DELETE SET NULL;

-- ============================================================================ 7. eventos do provedor (idempotência)
CREATE TABLE payment_provider_events (
  id                 bigserial PRIMARY KEY,
  provider           text NOT NULL,
  event_id           text NOT NULL,
  event_type         text NOT NULL,
  provider_charge_id text,
  amount_cents       bigint,
  signature_verified boolean NOT NULL,
  payload_redacted   jsonb NOT NULL DEFAULT '{}',   -- sem CPF, e-mail, IP ou dado de instrumento
  payload_sha256     char(64) NOT NULL,
  processing_status  text NOT NULL DEFAULT 'received' CHECK (processing_status IN ('received','applied','ignored','rejected','failed')),
  processing_note    text,
  attempts           integer NOT NULL DEFAULT 1,
  donation_id        uuid REFERENCES donations(id) ON DELETE SET NULL,
  received_at        timestamptz NOT NULL DEFAULT now(),
  processed_at       timestamptz,
  UNIQUE (provider, event_id)
);
CREATE INDEX ix_ppe_charge ON payment_provider_events(provider, provider_charge_id);
ALTER TABLE payment_provider_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY ppe_priv ON payment_provider_events FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- ============================================================================ 8. lançamentos de conciliação (partidas dobradas, append-only)
-- NÃO é dinheiro da plataforma e NÃO é saldo custodiado: é o ESPELHO do que o provedor confirmou, para conciliar.
CREATE TABLE donation_ledger_entries (
  id            bigserial PRIMARY KEY,
  donation_id   uuid NOT NULL REFERENCES donations(id) ON DELETE RESTRICT,
  campaign_id   uuid NOT NULL REFERENCES campaigns(id) ON DELETE RESTRICT,
  txn_id        uuid NOT NULL,                                             -- agrupa as partidas de um mesmo fato
  account       text NOT NULL CHECK (account IN (
                  'donor_payment',          -- o que o doador pagou (crédito)
                  'beneficiary_receivable', -- o que o provedor deve ao beneficiário (débito)
                  'provider_fee',           -- tarifa do provedor (débito)
                  'platform_fee_accrued',   -- taxa da plataforma CALCULADA (débito) — devida só com regra ativa
                  'beneficiary_fund',       -- reserva declarada da organização (débito)
                  'refund', 'chargeback')),
  side          char(1) NOT NULL CHECK (side IN ('D','C')),
  amount_cents  bigint NOT NULL CHECK (amount_cents >= 0),
  currency      char(3) NOT NULL DEFAULT 'BRL',
  source_event_id bigint REFERENCES payment_provider_events(id),
  reversal_of   bigint REFERENCES donation_ledger_entries(id),
  is_simulated  boolean NOT NULL,
  note          text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_dle_campaign ON donation_ledger_entries(campaign_id, created_at);
CREATE INDEX ix_dle_donation ON donation_ledger_entries(donation_id);
CREATE INDEX ix_dle_txn ON donation_ledger_entries(txn_id);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON donation_ledger_entries FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
ALTER TABLE donation_ledger_entries ENABLE ROW LEVEL SECURITY;
CREATE POLICY dle_read ON donation_ledger_entries FOR SELECT USING (app_priv()
  OR EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.beneficiary_org_id = app_org()));
CREATE POLICY dle_priv ON donation_ledger_entries FOR INSERT WITH CHECK (app_priv());

-- Cada fato (txn) fecha: soma dos débitos = soma dos créditos. Restrição postergada, conferida no COMMIT.
CREATE FUNCTION donation_ledger_balanced() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE d bigint; c bigint;
BEGIN
  SELECT coalesce(sum(amount_cents) FILTER (WHERE side = 'D'), 0), coalesce(sum(amount_cents) FILTER (WHERE side = 'C'), 0)
    INTO d, c FROM donation_ledger_entries WHERE txn_id = NEW.txn_id;
  IF d <> c THEN
    RAISE EXCEPTION 'lançamento % não fecha: débitos % ≠ créditos %', NEW.txn_id, d, c USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER trg_dle_balanced AFTER INSERT ON donation_ledger_entries
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION donation_ledger_balanced();

-- ============================================================================ 9. casos de risco (revisão humana, graduada)
CREATE TABLE donation_risk_cases (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id   uuid REFERENCES campaigns(id) ON DELETE RESTRICT,
  donation_id   uuid REFERENCES donations(id) ON DELETE RESTRICT,
  reason_codes  text[] NOT NULL CHECK (array_length(reason_codes, 1) >= 1),
  level         text NOT NULL CHECK (level IN ('low','medium','high')),
  action        text NOT NULL DEFAULT 'review' CHECK (action IN ('allow','review','request_information','payout_hold','reject','report_to_provider')),
  rule_version  text NOT NULL,                       -- versão das regras de risco (config/donation_risk_rules.json)
  explanation   text NOT NULL CHECK (length(explanation) BETWEEN 10 AND 2000),
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open','decided','appealed','closed')),
  decided_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  decided_at    timestamptz,
  decision_note text CHECK (length(decision_note) <= 2000),
  appeal_note   text CHECK (length(appeal_note) <= 2000),
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT decided_has_reviewer CHECK (status <> 'decided' OR (decided_by IS NOT NULL AND decision_note IS NOT NULL)),
  -- payout_hold só existe se o provedor/contrato permitir: nesta versão NUNCA é aplicado automaticamente.
  CONSTRAINT hold_needs_human CHECK (action <> 'payout_hold' OR decided_by IS NOT NULL)
);
CREATE INDEX ix_drc_open ON donation_risk_cases(status, level) WHERE status = 'open';
CREATE TRIGGER trg_touch BEFORE UPDATE ON donation_risk_cases FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
ALTER TABLE donation_risk_cases ENABLE ROW LEVEL SECURITY;
CREATE POLICY drc_priv ON donation_risk_cases FOR ALL USING (app_priv()) WITH CHECK (app_priv());
ALTER TABLE donations ADD CONSTRAINT donations_risk_fk FOREIGN KEY (risk_case_id) REFERENCES donation_risk_cases(id) ON DELETE SET NULL;

-- ============================================================================ 10. comprovantes
CREATE TABLE donation_receipts (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  donation_id   uuid NOT NULL UNIQUE REFERENCES donations(id) ON DELETE RESTRICT,
  number        text NOT NULL UNIQUE,                 -- IMP-DOA-AAAA-NNNNNN
  kind          text NOT NULL DEFAULT 'proof_of_donation' CHECK (kind IN ('proof_of_donation')),  -- "recibo dedutível"/"nota" só com parecer
  issuer_org_id uuid NOT NULL REFERENCES organizations(id),
  amount_cents  bigint NOT NULL,
  purpose       text,
  content_sha256 char(64) NOT NULL,
  status        text NOT NULL DEFAULT 'issued' CHECK (status IN ('issued','voided')),
  delivery_status text NOT NULL DEFAULT 'not_sent' CHECK (delivery_status IN ('not_sent','sent','failed')),
  issued_at     timestamptz NOT NULL DEFAULT now(),
  voided_at     timestamptz
);
ALTER TABLE donation_receipts ENABLE ROW LEVEL SECURITY;
CREATE POLICY receipts_read ON donation_receipts FOR SELECT USING (app_priv() OR issuer_org_id = app_org()
  OR EXISTS (SELECT 1 FROM donations d WHERE d.id = donation_id AND d.donor_user_id = app_uid()));
CREATE POLICY receipts_priv ON donation_receipts FOR ALL USING (app_priv()) WITH CHECK (app_priv());

-- ============================================================================ 11. prestação de contas da campanha
CREATE TABLE campaign_updates (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id   uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  title         text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
  body          text NOT NULL CHECK (length(body) BETWEEN 10 AND 8000),
  evidence_ids  uuid[] NOT NULL DEFAULT '{}',          -- referências a `evidences` (0070): origem, versão, contestação
  is_public     boolean NOT NULL DEFAULT true,
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_cupd_campaign ON campaign_updates(campaign_id, created_at DESC);
ALTER TABLE campaign_updates ENABLE ROW LEVEL SECURITY;
CREATE POLICY cupd_read ON campaign_updates FOR SELECT USING (is_public OR app_priv()
  OR EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.org_id = app_org()));
CREATE POLICY cupd_write ON campaign_updates FOR INSERT WITH CHECK (app_priv()
  OR EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.org_id = app_org()));

CREATE TABLE campaign_expenses (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  campaign_id   uuid NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
  description   text NOT NULL CHECK (length(description) BETWEEN 3 AND 500),
  budget_line   text CHECK (length(budget_line) <= 120),
  amount_cents  bigint NOT NULL CHECK (amount_cents > 0),
  spent_on      date NOT NULL,
  document_id   uuid REFERENCES documents(id) ON DELETE SET NULL,
  evidence_status text NOT NULL DEFAULT 'declared' CHECK (evidence_status IN ('declared','documented','validated','contested')),
  public_redacted boolean NOT NULL DEFAULT true,       -- publicamente: valor e rubrica; documento só para as partes
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_cexp_campaign ON campaign_expenses(campaign_id, spent_on);
CREATE TRIGGER trg_touch BEFORE UPDATE ON campaign_expenses FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
ALTER TABLE campaign_expenses ENABLE ROW LEVEL SECURITY;
CREATE POLICY cexp_read ON campaign_expenses FOR SELECT USING (app_priv()
  OR EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.org_id = app_org()));
CREATE POLICY cexp_write ON campaign_expenses FOR ALL USING (app_priv()
  OR EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.org_id = app_org()))
  WITH CHECK (app_priv() OR EXISTS (SELECT 1 FROM campaigns c WHERE c.id = campaign_id AND c.org_id = app_org()));

-- ============================================================================ 12. eventos de auditoria novos
-- (a trilha é a mesma `audit_events`; nomes registrados em services/audit.py)

-- ============================================================================ 13. privilégios mínimos (cada tabela declara os seus — ver 0052)
-- Nada de DELETE em lugar nenhum: histórico financeiro e de revisão não se apaga. Razão, eventos do provedor,
-- versões de regra e tarifas: só leitura e inserção (append-only também no privilégio).
GRANT SELECT, INSERT, UPDATE ON beneficiary_verifications TO impacto_app;
GRANT SELECT, INSERT ON fee_rule_versions TO impacto_app;
GRANT USAGE ON SEQUENCE fee_rule_versions_id_seq TO impacto_app;
GRANT SELECT, INSERT ON provider_fee_schedules TO impacto_app;
GRANT USAGE ON SEQUENCE provider_fee_schedules_id_seq TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON donations TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON recurring_donation_agreements TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON payment_provider_events TO impacto_app;
GRANT USAGE ON SEQUENCE payment_provider_events_id_seq TO impacto_app;
GRANT SELECT, INSERT ON donation_ledger_entries TO impacto_app;
GRANT USAGE ON SEQUENCE donation_ledger_entries_id_seq TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON donation_risk_cases TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON donation_receipts TO impacto_app;
GRANT SELECT, INSERT ON campaign_updates TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON campaign_expenses TO impacto_app;
GRANT EXECUTE ON FUNCTION beneficiary_verified(uuid) TO impacto_app;
