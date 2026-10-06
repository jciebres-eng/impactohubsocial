-- v0.21.0 — OFERTA COMERCIAL E ACEITE: ACESSO GRATUITO ≠ AUTORIZAÇÃO DE COBRANÇA
--
-- O DEFEITO QUE ESTA MIGRAÇÃO FECHA
--
-- A auditoria desta rodada procurou, literalmente, por qualquer distinção entre "esta pessoa
-- aceitou usar de graça" e "esta pessoa autorizou debitar o cartão dela". Não existia nenhuma:
-- `payment_method_required` tinha zero ocorrências no repositório, e o único registro parecido
-- com autorização era `subscription_prices.accepted_by` — que é o congelamento do preço aceito no
-- checkout, ou seja, já depois de a pessoa ter decidido pagar.
--
-- Enquanto os dois atos forem um só, o fim de um período gratuito vira cobrança por omissão: a
-- pessoa entrou de graça, nunca disse "pode cobrar", e mesmo assim a fatura sai. É a cobrança
-- surpresa, e ela nasce de modelagem, não de má-fé.
--
-- Aqui são dois atos, com dois valores de `consent_status`:
--
--   free_access  — "aceito usar, de graça, sob estes termos". NÃO autoriza cobrança nenhuma.
--   authorized   — "autorizo cobrar este valor, nesta frequência, neste meio de pagamento".
--
-- E uma invariante imposta por gatilho: NÃO HÁ COBRANÇA SEM UMA AUTORIZAÇÃO VIGENTE.
-- Quando o período gratuito acaba e não existe autorização, a conta volta ao plano gratuito —
-- não é cobrada, não é suspensa, não perde dado.

CREATE TABLE commercial_offers (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id             uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  pricing_version    text NOT NULL CHECK (length(pricing_version) BETWEEN 1 AND 40),
  plan_key           text NOT NULL REFERENCES plans(plan_key),
  price_version_id   uuid REFERENCES plan_price_versions(id),
  currency           char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  amount_cents       bigint NOT NULL CHECK (amount_cents >= 0),
  -- PARCELAMENTO NÃO É RECORRÊNCIA. São três coisas diferentes, e misturá-las é o que faz um
  -- cliente achar que pagou uma vez em 12x e descobrir que assinou 12 meses:
  --   one_time    — cobrança única
  --   installment — UMA dívida dividida em N parcelas; acaba quando a última parcela cai
  --   recurring   — cobrança que se repete enquanto a assinatura durar; não "acaba"
  billing_frequency  text NOT NULL CHECK (billing_frequency IN ('one_time','installment','recurring')),
  interval           text CHECK (interval IS NULL OR interval IN ('month','year')),
  installments       smallint CHECK (installments IS NULL OR installments BETWEEN 2 AND 24),
  payment_method     text NOT NULL CHECK (payment_method IN ('card','boleto','pix','manual')),
  free_period_months smallint CHECK (free_period_months IS NULL OR free_period_months BETWEEN 1 AND 60),
  free_period_id     uuid REFERENCES free_periods(id) ON DELETE SET NULL,
  status             text NOT NULL DEFAULT 'open'
                     CHECK (status IN ('open','accepted','expired','withdrawn')),
  expires_at         timestamptz,
  created_by         uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  -- Parcelamento exige número de parcelas, e recorrência exige intervalo. Uma oferta que diz
  -- "parcelado" sem dizer em quantas vezes não é uma oferta, é uma pergunta.
  CONSTRAINT offer_installments_pair CHECK ((billing_frequency = 'installment') = (installments IS NOT NULL)),
  CONSTRAINT offer_interval_pair     CHECK ((billing_frequency = 'recurring') = (interval IS NOT NULL))
);

COMMENT ON TABLE commercial_offers IS
  'O que foi OFERECIDO a esta organização: plano, valor, versão de preço, frequência, meio de '
  'pagamento e período gratuito incluído. A oferta é o documento que o aceite congela.';

CREATE INDEX ix_offer_org ON commercial_offers(org_id, created_at DESC);
CREATE INDEX ix_offer_open ON commercial_offers(expires_at) WHERE status = 'open';
CREATE INDEX ix_offer_price ON commercial_offers(price_version_id) WHERE price_version_id IS NOT NULL;
CREATE INDEX ix_offer_plan ON commercial_offers(plan_key);
CREATE INDEX ix_offer_free_period ON commercial_offers(free_period_id) WHERE free_period_id IS NOT NULL;
CREATE INDEX ix_offer_created_by ON commercial_offers(created_by) WHERE created_by IS NOT NULL;

CREATE TRIGGER trg_offer_touch BEFORE UPDATE ON commercial_offers
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ---------------------------------------------------------------------------------------------
-- O ACEITE
-- ---------------------------------------------------------------------------------------------

CREATE TABLE offer_acceptances (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  offer_id                 uuid NOT NULL REFERENCES commercial_offers(id) ON DELETE RESTRICT,
  org_id                   uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  pricing_version          text NOT NULL,
  plan_key                 text NOT NULL REFERENCES plans(plan_key),
  price_version_id         uuid REFERENCES plan_price_versions(id),
  free_period_id           uuid REFERENCES free_periods(id) ON DELETE SET NULL,
  billing_frequency        text NOT NULL CHECK (billing_frequency IN ('one_time','installment','recurring')),
  payment_method           text NOT NULL CHECK (payment_method IN ('card','boleto','pix','manual')),
  terms_version            text NOT NULL,
  privacy_version          text NOT NULL,
  commercial_terms_version text NOT NULL,
  accepted_at              timestamptz NOT NULL DEFAULT now(),
  accepted_by              uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  ip                       text,
  user_agent               text,
  -- O campo que separa os dois atos.
  consent_status           text NOT NULL CHECK (consent_status IN ('free_access','authorized')),
  revoked_at               timestamptz,
  revoked_by               uuid REFERENCES users(id) ON DELETE SET NULL,
  revoke_reason            text CHECK (revoke_reason IS NULL OR length(revoke_reason) BETWEEN 3 AND 500),
  created_at               timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT acceptance_revoke_pair CHECK ((revoked_at IS NULL) = (revoked_by IS NULL)),
  CONSTRAINT acceptance_revoke_reason CHECK (revoked_at IS NULL OR revoke_reason IS NOT NULL)
);

COMMENT ON TABLE offer_acceptances IS
  'Prova do aceite, com os campos que uma disputa exige: quem, quando, de onde, o que exatamente '
  'estava escrito (versão dos termos) e SE autorizou cobrança. consent_status=free_access NÃO '
  'autoriza cobrança — é aceite de acesso gratuito.';
COMMENT ON COLUMN offer_acceptances.consent_status IS
  'free_access = aceitou usar de graça; authorized = autorizou debitar. Cobrar uma conta cujo '
  'único aceite é free_access é exatamente a cobrança surpresa que esta coluna impede.';
COMMENT ON COLUMN offer_acceptances.revoked_at IS
  'Revogar a autorização é direito do cliente e não apaga o aceite: a prova de que ele autorizou '
  'em março continua, e a de que revogou em maio entra ao lado.';

CREATE INDEX ix_acceptance_org ON offer_acceptances(org_id, accepted_at DESC);
CREATE INDEX ix_acceptance_live ON offer_acceptances(org_id)
  WHERE consent_status = 'authorized' AND revoked_at IS NULL;
CREATE INDEX ix_acceptance_offer ON offer_acceptances(offer_id);
CREATE INDEX ix_acceptance_user ON offer_acceptances(accepted_by);
CREATE INDEX ix_acceptance_price ON offer_acceptances(price_version_id) WHERE price_version_id IS NOT NULL;
CREATE INDEX ix_acceptance_plan ON offer_acceptances(plan_key);
CREATE INDEX ix_acceptance_free_period ON offer_acceptances(free_period_id) WHERE free_period_id IS NOT NULL;
CREATE INDEX ix_acceptance_revoked_by ON offer_acceptances(revoked_by) WHERE revoked_by IS NOT NULL;

-- Uma organização tem no máximo UMA autorização de cobrança vigente. Duas autorizações vivas
-- seriam duas respostas para "este cliente autorizou o quê?", e a cobrança teria de escolher.
CREATE UNIQUE INDEX ux_acceptance_one_live ON offer_acceptances(org_id)
  WHERE consent_status = 'authorized' AND revoked_at IS NULL;

-- Aceite é prova: nada nele se reescreve, nem pela administração. A única transição permitida é
-- a revogação, e ela só acontece uma vez.
CREATE OR REPLACE FUNCTION acceptance_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.offer_id, NEW.org_id, NEW.pricing_version, NEW.plan_key, NEW.price_version_id,
      NEW.free_period_id, NEW.billing_frequency, NEW.payment_method, NEW.terms_version,
      NEW.privacy_version, NEW.commercial_terms_version, NEW.accepted_at, NEW.accepted_by,
      NEW.ip, NEW.user_agent, NEW.consent_status, NEW.created_at)
     IS DISTINCT FROM
     (OLD.offer_id, OLD.org_id, OLD.pricing_version, OLD.plan_key, OLD.price_version_id,
      OLD.free_period_id, OLD.billing_frequency, OLD.payment_method, OLD.terms_version,
      OLD.privacy_version, OLD.commercial_terms_version, OLD.accepted_at, OLD.accepted_by,
      OLD.ip, OLD.user_agent, OLD.consent_status, OLD.created_at) THEN
    RAISE EXCEPTION 'aceite é prova e não se altera; para desfazer, revogue' USING ERRCODE = '42501';
  END IF;
  IF OLD.revoked_at IS NOT NULL AND NEW.revoked_at IS DISTINCT FROM OLD.revoked_at THEN
    RAISE EXCEPTION 'aceite já revogado' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_acceptance_immutable BEFORE UPDATE ON offer_acceptances
  FOR EACH ROW EXECUTE FUNCTION acceptance_immutable();

ALTER TABLE commercial_offers  ENABLE ROW LEVEL SECURITY;
ALTER TABLE offer_acceptances  ENABLE ROW LEVEL SECURITY;

CREATE POLICY offer_read ON commercial_offers FOR SELECT
  USING (app_system() OR app_priv() OR org_id = app_org());
-- A organização monta a PRÓPRIA oferta: é o autosserviço — escolher um plano na tela e receber a
-- proposta materializada. Não há brecha nisso porque o VALOR vem do catálogo (`plan_price_versions`)
-- e nunca do pedido, e as regras de meio de pagamento são validadas no servidor. O que a
-- organização não pode é montar oferta para outra, e isso o `org_id = app_org()` garante.
CREATE POLICY offer_write ON commercial_offers FOR INSERT
  WITH CHECK (app_system() OR app_priv() OR org_id = app_org());
CREATE POLICY offer_update ON commercial_offers FOR UPDATE
  USING (app_system() OR app_priv() OR org_id = app_org())
  WITH CHECK (app_system() OR app_priv() OR org_id = app_org());

CREATE POLICY acceptance_read ON offer_acceptances FOR SELECT
  USING (app_system() OR app_priv() OR org_id = app_org());
-- Quem aceita é a organização: o aceite nasce de um ato do cliente, não de um ato da plataforma.
CREATE POLICY acceptance_write ON offer_acceptances FOR INSERT
  WITH CHECK (app_system() OR org_id = app_org());
CREATE POLICY acceptance_update ON offer_acceptances FOR UPDATE
  USING (app_system() OR app_priv() OR org_id = app_org())
  WITH CHECK (app_system() OR app_priv() OR org_id = app_org());

GRANT SELECT, INSERT, UPDATE ON commercial_offers TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON offer_acceptances TO impacto_app;
REVOKE DELETE ON commercial_offers FROM impacto_app;
REVOKE DELETE ON offer_acceptances FROM impacto_app;

-- ---------------------------------------------------------------------------------------------
-- A INVARIANTE: não há cobrança sem autorização vigente
-- ---------------------------------------------------------------------------------------------
--
-- Esta é a regra que torna "sem cobrança surpresa" uma propriedade do sistema, e não uma promessa
-- do marketing. Ela vale contra TODO caminho de escrita — rota, job, webhook, console de
-- administração — porque mora no banco.
--
-- Cobrança simulada (`is_simulated`) é isenta: ela não debita ninguém, e exigir autorização para
-- simular impediria de testar o próprio bloqueio.

-- UMA definição de "esta cobrança é simulada". A v0.17.0 derivava isso de `provider` dentro do
-- gatilho `charge_simulated_flag()`. O gatilho de autorização abaixo precisa da MESMA resposta — e
-- não pode lê-la da coluna, porque os gatilhos BEFORE INSERT disparam em ordem alfabética do nome e
-- `trg_charge_requires_authorization` vem antes de `trg_charge_simulated`: nesse instante a coluna
-- ainda contém o que o chamador mandou, não o que o provedor determina.
--
-- Isso era uma brecha de verdade: bastava informar `is_simulated = true` junto com um provedor real
-- para passar pela exigência de autorização, e o gatilho seguinte marcaria a cobrança como real
-- logo depois. Quem decide é o provedor, e agora os dois gatilhos perguntam no mesmo lugar.
CREATE OR REPLACE FUNCTION charge_is_simulated(p_provider text) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$ SELECT p_provider IS DISTINCT FROM 'stripe' $$;

COMMENT ON FUNCTION charge_is_simulated(text) IS
  'Lista explícita de provedores REAIS, e não "todos menos sandbox": um provedor novo nasce '
  'simulado, que é o lado seguro do engano.';

CREATE OR REPLACE FUNCTION charge_simulated_flag() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_derived boolean := charge_is_simulated(NEW.provider);
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.is_simulated IS DISTINCT FROM OLD.is_simulated THEN
    RAISE EXCEPTION 'is_simulated é derivada do provedor (%): não se escreve à mão', NEW.provider
      USING ERRCODE = '23514';
  END IF;
  NEW.is_simulated := v_derived;
  RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION charge_requires_authorization() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  -- Derivado do PROVEDOR, não lido da coluna: ver o comentário acima.
  IF charge_is_simulated(NEW.provider) THEN RETURN NEW; END IF;
  IF NEW.amount_cents IS NULL OR NEW.amount_cents = 0 THEN RETURN NEW; END IF;
  IF NOT EXISTS (SELECT 1 FROM offer_acceptances
                  WHERE org_id = NEW.org_id AND consent_status = 'authorized'
                    AND revoked_at IS NULL) THEN
    RAISE EXCEPTION 'cobrança sem autorização vigente: a organização aceitou acesso, não cobrança'
      USING ERRCODE = '42501',
            HINT = 'registre um aceite com consent_status = authorized antes de cobrar';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_charge_requires_authorization BEFORE INSERT ON platform_charges
  FOR EACH ROW EXECUTE FUNCTION charge_requires_authorization();

-- ---------------------------------------------------------------------------------------------
-- Estado comercial derivado
-- ---------------------------------------------------------------------------------------------
--
-- Derivado, e não guardado em coluna: uma conta "vira" paga à meia-noite sem ninguém rodar nada,
-- e uma coluna só mudaria quando algum job passasse — deixando a tela e a cobrança discordando
-- justamente na virada, que é quando o cliente olha.

CREATE OR REPLACE FUNCTION org_commercial_state(p_org uuid) RETURNS text
LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_free timestamptz;
  v_sub  record;
  v_auth boolean;
BEGIN
  SELECT status, cancel_at_period_end INTO v_sub
    FROM subscriptions WHERE org_id = p_org
     AND status IN ('active','trialing','past_due') LIMIT 1;

  IF v_sub.status = 'past_due' THEN RETURN 'PAST_DUE'; END IF;

  SELECT EXISTS (SELECT 1 FROM offer_acceptances
                  WHERE org_id = p_org AND consent_status = 'authorized'
                    AND revoked_at IS NULL) INTO v_auth;

  v_free := free_period_end(p_org);
  IF v_free IS NOT NULL THEN
    IF v_free <= now() + interval '30 days' AND NOT v_auth THEN
      -- Faltam 30 dias ou menos e ninguém autorizou cobrança. Não é erro: é o estado em que a
      -- plataforma precisa AVISAR, e em que o cliente ainda pode simplesmente não fazer nada e
      -- continuar no plano gratuito.
      RETURN 'PAYMENT_METHOD_REQUIRED';
    END IF;
    IF v_free <= now() + interval '30 days' THEN RETURN 'FREE_EXPIRING'; END IF;
    RETURN 'FREE';
  END IF;

  IF v_sub.status IS NULL THEN RETURN 'FREE'; END IF;
  IF v_sub.cancel_at_period_end THEN RETURN 'CANCELLED'; END IF;
  RETURN 'PAID_ACTIVE';
END $$;

COMMENT ON FUNCTION org_commercial_state(uuid) IS
  'Estado comercial derivado. FREE não é "sem assinatura": o plano gratuito é permanente, e o fim '
  'de um período gratuito devolve a conta a ele em vez de suspendê-la.';
