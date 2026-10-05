-- 0008 — v0.11.0: monetização (SaaS). Estende a arquitetura de billing existente (plans, subscriptions, invoices, billing_events, vouchers, grants);
-- NÃO cria uma segunda. Autoridade financeira = backend + Stripe/webhooks; o cliente nunca define plano, preço, desconto ou direito.

-- ------------------------------------------------------------------------------------------------ tier e preços (mensal/anual)
ALTER TABLE plans ADD COLUMN tier text NOT NULL DEFAULT 'free' CHECK (tier IN ('free','plus','premium','gov'));
UPDATE plans SET tier = CASE WHEN plan_key LIKE '%\_basic' THEN 'free' WHEN plan_key LIKE '%\_premium' OR plan_key LIKE '%\_enterprise' THEN 'premium' ELSE tier END;

-- NULL em amount_cents = preço NÃO definido pelo proprietário (nunca inventado): contratação online recusada.
CREATE TABLE plan_prices (
  plan_key     text NOT NULL REFERENCES plans(plan_key) ON DELETE CASCADE,
  interval     text NOT NULL CHECK (interval IN ('month','year')),
  amount_cents bigint CHECK (amount_cents IS NULL OR amount_cents >= 0),
  active       boolean NOT NULL DEFAULT true,
  updated_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (plan_key, interval)
);

-- ------------------------------------------------------------------------------------------------ assinatura: campos de ciclo de vida
ALTER TABLE subscriptions
  ADD COLUMN interval        text CHECK (interval IN ('month','year')),
  ADD COLUMN trial_end       timestamptz,
  ADD COLUMN canceled_at     timestamptz,
  ADD COLUMN last_event_at   timestamptz,                     -- evento mais recente aplicado (ignora eventos fora de ordem)
  ADD COLUMN amount_cents    bigint CHECK (amount_cents IS NULL OR amount_cents >= 0),   -- valor final CALCULADO NO SERVIDOR no checkout
  ADD COLUMN discount        jsonb,                           -- {source, percent|amount_cents, duration} aplicado
  ADD COLUMN payment_issue   text CHECK (payment_issue IN ('payment_failed','action_required')),
  ADD COLUMN origin          text NOT NULL DEFAULT 'checkout' CHECK (origin IN ('checkout','manual','sandbox','trial_conversion'));
-- No máximo UMA assinatura vigente por organização (não cria duas assinaturas para o mesmo cliente).
CREATE UNIQUE INDEX ux_subscriptions_one_live ON subscriptions(org_id) WHERE status IN ('active','trialing','past_due');

-- ------------------------------------------------------------------------------------------------ trial de 14 dias (por organização)
CREATE TABLE org_trials (
  org_id       uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,   -- PK = no máximo um trial por organização (trial_used)
  plan_key     text NOT NULL REFERENCES plans(plan_key),
  source       text NOT NULL CHECK (source IN ('signup','admin','promotion')),
  trial_start  timestamptz NOT NULL DEFAULT now(),
  trial_end    timestamptz NOT NULL,
  status       text NOT NULL DEFAULT 'active' CHECK (status IN ('active','canceled','ended','converted')),
  canceled_at  timestamptz,
  created_by   uuid REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (trial_end > trial_start)
);

-- Anti-abuso com minimização: guardamos só HMAC do e-mail normalizado (e do CNPJ, que a organização já informa no cadastro) — nunca o valor em claro.
CREATE TABLE trial_claims (
  kind        text NOT NULL CHECK (kind IN ('email','cnpj')),
  identity_hash char(64) NOT NULL,
  org_id      uuid REFERENCES organizations(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (kind, identity_hash)
);

-- Avisos de cobrança/trial sem spam: um por (organização, tipo, referência).
CREATE TABLE billing_notices (
  org_id   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  kind     text NOT NULL,
  ref      text NOT NULL,
  sent_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, kind, ref)
);

-- ------------------------------------------------------------------------------------------------ vouchers: descontos reais
ALTER TABLE vouchers
  ADD COLUMN organization_id    uuid REFERENCES organizations(id) ON DELETE CASCADE,     -- voucher restrito a uma organização
  ADD COLUMN discount_duration  text CHECK (discount_duration IN ('once','repeating','forever')),
  ADD COLUMN discount_months    integer CHECK (discount_months > 0),
  ADD COLUMN created_by         uuid REFERENCES users(id);
ALTER TABLE vouchers ALTER COLUMN duration_days DROP NOT NULL;
ALTER TABLE voucher_redemptions
  ADD COLUMN status text NOT NULL DEFAULT 'applied' CHECK (status IN ('applied','pending_discount','consumed')),
  ADD COLUMN consumed_by_subscription uuid REFERENCES subscriptions(id) ON DELETE SET NULL;

-- ------------------------------------------------------------------------------------------------ licenças gratuitas (grants): origem identificável e revogação
ALTER TABLE entitlement_grants DROP CONSTRAINT entitlement_grants_source_check;
ALTER TABLE entitlement_grants
  ADD CONSTRAINT entitlement_grants_source_check CHECK (source IN ('voucher','admin','license','partner','convention','gov','promotion')),
  ADD COLUMN reason         text CHECK (length(reason) <= 500),
  ADD COLUMN agreement_id   uuid,
  ADD COLUMN revoked_at     timestamptz,
  ADD COLUMN revoked_by     uuid REFERENCES users(id),
  ADD COLUMN revoke_reason  text CHECK (length(revoke_reason) <= 500);

-- ------------------------------------------------------------------------------------------------ convênios / GOV institucional
CREATE TABLE agreements (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name             text NOT NULL CHECK (length(name) BETWEEN 2 AND 200),
  kind             text NOT NULL CHECK (kind IN ('convention','gov','partner')),
  status           text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','active','suspended','ended')),
  plan_key         text REFERENCES plans(plan_key),                      -- licença concedida a cada membro (opcional)
  grant_days       integer CHECK (grant_days > 0),                       -- NULL = até o fim do convênio
  discount_percent smallint CHECK (discount_percent BETWEEN 1 AND 100),  -- desconto aplicado no checkout aos membros (opcional)
  seats            integer NOT NULL CHECK (seats > 0),
  seats_used       integer NOT NULL DEFAULT 0 CHECK (seats_used >= 0),
  email_domains    text[] NOT NULL DEFAULT '{}',                         -- restringe QUEM pode entrar; nunca substitui o código
  code_hash        char(64) NOT NULL UNIQUE,
  code_hint        char(4) NOT NULL,
  valid_from       timestamptz,
  valid_until      timestamptz,
  contract_ref     text CHECK (length(contract_ref) <= 200),
  created_by       uuid NOT NULL REFERENCES users(id),
  activated_by     uuid REFERENCES users(id),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (seats_used <= seats),
  CHECK (plan_key IS NOT NULL OR discount_percent IS NOT NULL),
  CHECK (activated_by IS NULL OR activated_by <> created_by)             -- quatro olhos para ativar
);
CREATE TABLE agreement_members (
  agreement_id uuid NOT NULL REFERENCES agreements(id) ON DELETE CASCADE,
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  joined_by    uuid NOT NULL REFERENCES users(id),
  joined_at    timestamptz NOT NULL DEFAULT now(),
  status       text NOT NULL DEFAULT 'active' CHECK (status IN ('active','revoked')),
  grant_id     uuid REFERENCES entitlement_grants(id) ON DELETE SET NULL,
  PRIMARY KEY (agreement_id, org_id)
);
ALTER TABLE entitlement_grants ADD CONSTRAINT entitlement_grants_agreement_fk FOREIGN KEY (agreement_id) REFERENCES agreements(id) ON DELETE SET NULL;

-- GOV não é "premium com outro nome": tier próprio, limites e contrato próprios.

-- ------------------------------------------------------------------------------------------------ RLS e privilégios
ALTER TABLE plan_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_trials ENABLE ROW LEVEL SECURITY;
ALTER TABLE trial_claims ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing_notices ENABLE ROW LEVEL SECURITY;
ALTER TABLE agreements ENABLE ROW LEVEL SECURITY;
ALTER TABLE agreement_members ENABLE ROW LEVEL SECURITY;

CREATE POLICY plan_prices_read ON plan_prices FOR SELECT USING (true);                                   -- catálogo público
CREATE POLICY plan_prices_write ON plan_prices FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY org_trials_read ON org_trials FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY org_trials_write ON org_trials FOR ALL USING (app_priv()) WITH CHECK (app_priv());        -- só servidor/administração
CREATE POLICY trial_claims_sys ON trial_claims FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY billing_notices_read ON billing_notices FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY billing_notices_write ON billing_notices FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY agreements_admin ON agreements FOR ALL USING (app_priv()) WITH CHECK (app_priv());        -- código/HMAC nunca visível à organização
CREATE POLICY agreement_members_read ON agreement_members FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY agreement_members_write ON agreement_members FOR ALL USING (app_priv()) WITH CHECK (app_priv());

GRANT SELECT, INSERT, UPDATE, DELETE ON plan_prices, org_trials, trial_claims, billing_notices, agreements, agreement_members TO impacto_app;

-- Organização nunca altera o próprio plano/assinatura/direito (defesa em profundidade além do RLS)
CREATE FUNCTION billing_guard() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF NOT app_priv() THEN
    RAISE EXCEPTION 'dados de cobrança só podem ser alterados pelo servidor ou pela administração' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_org_trials_guard BEFORE INSERT OR UPDATE OR DELETE ON org_trials FOR EACH ROW EXECUTE FUNCTION billing_guard();
CREATE TRIGGER trg_grants_guard BEFORE INSERT OR UPDATE ON entitlement_grants FOR EACH ROW EXECUTE FUNCTION billing_guard();

DO $$ DECLARE f regprocedure; BEGIN
  FOR f IN SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND pg_get_userbyid(p.proowner) = current_user LOOP
    EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f);
    EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO impacto_app', f);
  END LOOP;
END $$;
