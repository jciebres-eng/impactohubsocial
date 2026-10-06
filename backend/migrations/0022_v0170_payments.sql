-- 0022_v0170_payments.sql — ARQUITETURA DE PAGAMENTO DA PLATAFORMA
--
-- ESCOPO, E A DISTINÇÃO QUE NÃO PODE SE PERDER
--
-- Isto é a cobrança **da plataforma** contra a organização que a usa. Não confundir com
-- `payment_records`, que é o REGISTRO de aporte declarado ao projeto — ali o dinheiro nunca passa pela
-- plataforma (ADR-022/031), e é por isso que `payment_records.method` já aceita 'pix' e 'boleto' sem
-- que exista cobrança por PIX nenhuma. A auditoria econômica (SAAS_ECONOMIC_AUDIT.md §3) registrou
-- essa confusão como o achado mais fácil de cometer lendo o banco.
--
-- A REGRA QUE GOVERNA TODA ESTA MIGRAÇÃO
--
-- Os documentos desta rodada: "Nunca apresentar pagamento fake como pagamento real" e
-- "PRODUCTION PAYMENT NOT CONFIGURED". Então a honestidade não é um aviso na tela: é a coluna
-- `is_simulated`, DERIVADA por gatilho do provedor usado, que ninguém escreve à mão. Uma cobrança
-- feita no provedor de teste fica marcada como simulada para sempre, e qualquer soma de receita que a
-- inclua está somando dinheiro que não existe — há invariante de teste para isso.
--
-- E não há credencial nenhuma aqui. Nenhuma chave, nenhum identificador de preço, nenhum token.

-- ============================================================================ 1. a máquina de estados
-- Como dado, no mesmo padrão de `project_status_graph`, `proposal_status_graph` e
-- `program_status_graph`: a transição válida é linha de tabela, e o gatilho recusa o que não está lá.
CREATE TABLE charge_state_graph (
  from_state text NOT NULL,
  to_state   text NOT NULL,
  origin     text NOT NULL CHECK (origin IN ('user','webhook','system','admin','any')),
  note       text NOT NULL,
  PRIMARY KEY (from_state, to_state)
);
INSERT INTO charge_state_graph(from_state, to_state, origin, note) VALUES
  ('created','checkout_started','user','A pessoa abriu o checkout do provedor'),
  ('created','cancelled','any','Desistência antes de iniciar'),
  ('checkout_started','pending','any','Instrução de pagamento emitida (PIX gerado, boleto impresso, cartão enviado)'),
  ('checkout_started','failed','any','O provedor recusou antes de gerar a instrução'),
  ('checkout_started','cancelled','any','Abandono do checkout'),
  ('pending','authorized','webhook','Cartão autorizado, ainda não capturado'),
  ('pending','paid','webhook','Pagamento confirmado pelo provedor'),
  ('pending','failed','webhook','Recusa do meio de pagamento'),
  ('pending','expired','system','PIX ou boleto venceu sem pagamento'),
  ('pending','cancelled','any','Cancelado antes do pagamento'),
  ('authorized','paid','webhook','Captura confirmada'),
  ('authorized','failed','webhook','Captura recusada depois da autorização'),
  ('authorized','cancelled','any','Autorização estornada antes da captura'),
  ('paid','settled','webhook','Liquidação confirmada: o dinheiro chegou'),
  ('paid','refunded','any','Devolução integral'),
  ('paid','partially_refunded','any','Devolução parcial'),
  ('paid','disputed','webhook','Contestação aberta pelo titular'),
  ('settled','refunded','any','Devolução integral após liquidação'),
  ('settled','partially_refunded','any','Devolução parcial após liquidação'),
  ('settled','disputed','webhook','Contestação aberta após liquidação'),
  ('partially_refunded','refunded','any','O restante também foi devolvido'),
  ('partially_refunded','disputed','webhook','Contestação sobre o saldo'),
  ('disputed','chargeback','webhook','Contestação decidida contra a plataforma'),
  ('disputed','settled','webhook','Contestação decidida a favor da plataforma'),
  ('disputed','refunded','any','Devolução acordada durante a contestação'),
  ('failed','created','user','Nova tentativa gera cobrança nova; esta volta ao início apenas para retentativa imediata'),
  ('expired','created','user','Nova instrução para a mesma fatura');

-- ============================================================================ 2. instrumento de pagamento
-- NÃO guardamos dado de cartão. O provedor tokeniza; aqui ficam só o token dele e o que é necessário
-- para a pessoa reconhecer o próprio cartão na tela.
--
-- Há um gatilho que recusa `last4` com mais de 4 caracteres. Parece exagero, e é de propósito: é o
-- tipo de campo em que alguém, um dia, grava o número inteiro "só para depurar".
CREATE TABLE payment_instruments (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  kind          text NOT NULL CHECK (kind IN ('card')),
  provider      text NOT NULL CHECK (length(provider) BETWEEN 2 AND 40),
  provider_token text NOT NULL CHECK (length(provider_token) BETWEEN 4 AND 200),
  brand         text CHECK (brand IS NULL OR length(brand) <= 30),
  last4         char(4) CHECK (last4 IS NULL OR last4 ~ '^[0-9]{4}$'),
  exp_month     smallint CHECK (exp_month IS NULL OR exp_month BETWEEN 1 AND 12),
  exp_year      smallint CHECK (exp_year IS NULL OR exp_year BETWEEN 2020 AND 2100),
  holder_label  text CHECK (holder_label IS NULL OR length(holder_label) <= 60),
  is_default    boolean NOT NULL DEFAULT false,
  removed_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider, provider_token)
);
COMMENT ON TABLE payment_instruments IS
  'Referência ao instrumento tokenizado NO PROVEDOR. A plataforma não guarda número, CVV, validade '
  'completa nem nome impresso: guarda o token do provedor e os quatro últimos dígitos, que existem '
  'para a pessoa reconhecer o próprio cartão.';
COMMENT ON COLUMN payment_instruments.provider_token IS
  'Token do provedor. NÃO é dado de cartão e não serve para cobrar fora do provedor que o emitiu.';
CREATE INDEX ix_instruments_org ON payment_instruments(org_id) WHERE removed_at IS NULL;
CREATE UNIQUE INDEX ux_instrument_default ON payment_instruments(org_id)
  WHERE is_default AND removed_at IS NULL;

-- ============================================================================ 3. a cobrança
CREATE TABLE platform_charges (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  subscription_id uuid REFERENCES subscriptions(id) ON DELETE SET NULL,
  invoice_id    uuid REFERENCES invoices(id) ON DELETE SET NULL,
  -- Cobrança por OPERAÇÃO liga no candidato que a originou, fechando a cadeia
  -- valor → candidato → cobrança. Nula nas cobranças de assinatura.
  billable_event_id bigint REFERENCES billable_events(id) ON DELETE SET NULL,
  kind          text NOT NULL CHECK (kind IN ('subscription','one_off','installment_plan','operation')),
  method        text NOT NULL CHECK (method IN ('card','pix','boleto','manual')),
  amount_cents  bigint NOT NULL CHECK (amount_cents > 0),
  currency      char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),
  state         text NOT NULL DEFAULT 'created',
  -- Parcelamento NÃO é assinatura: os documentos são explícitos sobre modelá-lo separado. Aqui o
  -- número de parcelas só existe em cartão, e o cronograma fica em `charge_installments`.
  installments  smallint CHECK (installments IS NULL OR installments BETWEEN 2 AND 24),
  instrument_id uuid REFERENCES payment_instruments(id) ON DELETE SET NULL,
  provider      text NOT NULL CHECK (length(provider) BETWEEN 2 AND 40),
  provider_charge_id text CHECK (provider_charge_id IS NULL OR length(provider_charge_id) <= 200),
  -- DERIVADA do provedor por gatilho. Ninguém escreve. É a trava central desta migração.
  is_simulated  boolean NOT NULL DEFAULT true,
  due_on        date,
  expires_at    timestamptz,
  paid_at       timestamptz,
  settled_at    timestamptz,
  refunded_cents bigint NOT NULL DEFAULT 0 CHECK (refunded_cents >= 0),
  failure_code  text CHECK (failure_code IS NULL OR length(failure_code) <= 80),
  failure_message text CHECK (failure_message IS NULL OR length(failure_message) <= 500),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT refund_within_amount CHECK (refunded_cents <= amount_cents),
  CONSTRAINT installments_only_on_card CHECK (installments IS NULL OR method = 'card'),
  CONSTRAINT installment_plan_has_installments CHECK (
    (kind = 'installment_plan') = (installments IS NOT NULL)),
  CONSTRAINT boleto_has_due_date CHECK (method <> 'boleto' OR due_on IS NOT NULL),
  CONSTRAINT pix_has_expiry CHECK (method <> 'pix' OR expires_at IS NOT NULL),
  CONSTRAINT state_values CHECK (state IN (
    'created','checkout_started','pending','authorized','paid','settled','failed','expired',
    'cancelled','refunded','partially_refunded','disputed','chargeback'))
);
COMMENT ON TABLE platform_charges IS
  'Cobrança da PLATAFORMA contra a organização. Não confundir com payment_records, que é o registro '
  'de aporte declarado ao projeto, em que o dinheiro não passa pela plataforma (ADR-022).';
COMMENT ON COLUMN platform_charges.is_simulated IS
  'DERIVADA do provedor por gatilho: verdadeira para provedor de teste ou ausente. Cobrança simulada '
  'nunca pode ser somada como receita — há invariante de teste que confere.';

CREATE INDEX ix_charges_org ON platform_charges(org_id, created_at DESC);
CREATE INDEX ix_charges_state ON platform_charges(state) WHERE state IN ('created','checkout_started','pending','authorized');
CREATE INDEX ix_charges_sub ON platform_charges(subscription_id) WHERE subscription_id IS NOT NULL;
CREATE INDEX ix_charges_invoice ON platform_charges(invoice_id) WHERE invoice_id IS NOT NULL;
CREATE INDEX ix_charges_billable ON platform_charges(billable_event_id) WHERE billable_event_id IS NOT NULL;
CREATE INDEX ix_charges_instrument ON platform_charges(instrument_id) WHERE instrument_id IS NOT NULL;
CREATE UNIQUE INDEX ux_charge_provider ON platform_charges(provider, provider_charge_id)
  WHERE provider_charge_id IS NOT NULL;
CREATE INDEX ix_charges_expiring ON platform_charges(expires_at)
  WHERE state = 'pending' AND expires_at IS NOT NULL;
CREATE INDEX ix_charges_due ON platform_charges(due_on) WHERE state = 'pending' AND due_on IS NOT NULL;

-- ---------------------------------------------------------------- a trilha
CREATE TABLE charge_events (
  id          bigserial PRIMARY KEY,
  charge_id   uuid NOT NULL REFERENCES platform_charges(id) ON DELETE CASCADE,
  from_state  text,
  to_state    text NOT NULL,
  origin      text NOT NULL CHECK (origin IN ('user','webhook','system','admin')),
  actor_user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  provider_event_id text CHECK (provider_event_id IS NULL OR length(provider_event_id) <= 200),
  amount_cents bigint CHECK (amount_cents IS NULL OR amount_cents >= 0),
  note        text CHECK (note IS NULL OR length(note) <= 1000),
  at          timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE charge_events IS
  'Toda transição de cobrança, append-only, com origem, ator, identificador do evento do provedor e '
  'valor quando aplicável. É o que permite responder "por que esta cobrança está neste estado".';
CREATE INDEX ix_charge_events_charge ON charge_events(charge_id, id);
CREATE INDEX ix_charge_events_provider ON charge_events(provider_event_id)
  WHERE provider_event_id IS NOT NULL;

-- ---------------------------------------------------------------- parcelas
CREATE TABLE charge_installments (
  charge_id    uuid NOT NULL REFERENCES platform_charges(id) ON DELETE CASCADE,
  n            smallint NOT NULL CHECK (n >= 1),
  amount_cents bigint NOT NULL CHECK (amount_cents > 0),
  due_on       date NOT NULL,
  state        text NOT NULL DEFAULT 'pending'
               CHECK (state IN ('pending','paid','failed','cancelled','refunded')),
  paid_at      timestamptz,
  provider_installment_id text CHECK (provider_installment_id IS NULL
                                      OR length(provider_installment_id) <= 200),
  PRIMARY KEY (charge_id, n)
);
COMMENT ON TABLE charge_installments IS
  'Cronograma do parcelamento. Existe porque parcelamento NÃO é assinatura: tem número fixo de '
  'parcelas, vencimentos definidos e não renova.';
CREATE INDEX ix_installments_due ON charge_installments(due_on) WHERE state = 'pending';

-- ---------------------------------------------------------------- PIX e boleto
CREATE TABLE charge_pix (
  charge_id   uuid PRIMARY KEY REFERENCES platform_charges(id) ON DELETE CASCADE,
  -- "Copia e cola": a instrução de pagamento, não um segredo.
  payload     text NOT NULL CHECK (length(payload) BETWEEN 20 AND 4000),
  provider_txid text CHECK (provider_txid IS NULL OR length(provider_txid) <= 200),
  expires_at  timestamptz NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON COLUMN charge_pix.payload IS
  'Carga "copia e cola" do PIX, gerada pelo provedor. É instrução de pagamento com prazo, não '
  'credencial: não autoriza nada em nome de ninguém.';

CREATE TABLE charge_boleto (
  charge_id      uuid PRIMARY KEY REFERENCES platform_charges(id) ON DELETE CASCADE,
  digitable_line text NOT NULL CHECK (digitable_line ~ '^[0-9. ]{40,60}$'),
  barcode        text CHECK (barcode IS NULL OR barcode ~ '^[0-9]{40,50}$'),
  due_on         date NOT NULL,
  provider_boleto_id text CHECK (provider_boleto_id IS NULL OR length(provider_boleto_id) <= 200),
  pdf_storage_key text CHECK (pdf_storage_key IS NULL OR length(pdf_storage_key) <= 400),
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- ============================================================================ 4. gatilhos
-- `is_simulated` DERIVADA do provedor. Esta é a trava central: nenhuma rota, job ou script escreve a
-- coluna, e por isso uma cobrança de teste não consegue se passar por real.
--
-- A lista de provedores reais é explícita, e não o contrário ("todos menos sandbox"). A versão
-- permissiva faria qualquer provedor novo — inclusive um dublê de teste chamado de outro jeito —
-- nascer marcado como real, que é exatamente o erro que esta coluna existe para impedir. A lição é a
-- mesma que `app_related()` ensinou na v0.16.0.
CREATE FUNCTION charge_simulated_flag() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_derived boolean := NEW.provider NOT IN ('stripe');
BEGIN
  -- Em UPDATE, recusar em vez de sobrescrever em silêncio. Sobrescrever resolveria o caso igual e
  -- deixaria quem tentou marcar uma cobrança de teste como real sem nenhum sinal de que a tentativa
  -- foi ignorada. A lição é a da 0018: coluna derivada avisa quando alguém tenta escrevê-la.
  IF TG_OP = 'UPDATE' AND NEW.is_simulated IS DISTINCT FROM OLD.is_simulated THEN
    RAISE EXCEPTION 'is_simulated é derivada do provedor (%): não se escreve à mão', NEW.provider
      USING ERRCODE = '23514';
  END IF;
  NEW.is_simulated := v_derived;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_charge_simulated BEFORE INSERT OR UPDATE ON platform_charges
  FOR EACH ROW EXECUTE FUNCTION charge_simulated_flag();

-- Situação inicial não é escolha do cliente.
CREATE FUNCTION charge_initial_state() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.state IS DISTINCT FROM 'created' THEN
    RAISE EXCEPTION 'cobrança nasce em created' USING ERRCODE = '23514';
  END IF;
  IF NEW.paid_at IS NOT NULL OR NEW.settled_at IS NOT NULL OR NEW.refunded_cents <> 0 THEN
    RAISE EXCEPTION 'datas de pagamento e valor devolvido são derivados da transição'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_charge_initial BEFORE INSERT ON platform_charges
  FOR EACH ROW EXECUTE FUNCTION charge_initial_state();

-- Transição fora do grafo é recusada, e as datas são DERIVADAS aqui — não entram em `guard_columns`,
-- pela lição da v0.16.0 e da 0018: coluna derivada por gatilho guardada por `guard_columns` faz a
-- própria transição legítima responder 403.
CREATE FUNCTION charge_state_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_edge record;
BEGIN
  IF NEW.state IS DISTINCT FROM OLD.state THEN
    SELECT * INTO v_edge FROM charge_state_graph
     WHERE from_state = OLD.state AND to_state = NEW.state;
    IF v_edge IS NULL THEN
      RAISE EXCEPTION 'transição de cobrança % -> % não existe', OLD.state, NEW.state
        USING ERRCODE = '23514';
    END IF;
    IF NEW.state = 'paid' THEN NEW.paid_at := coalesce(NEW.paid_at, now()); END IF;
    IF NEW.state = 'settled' THEN NEW.settled_at := coalesce(NEW.settled_at, now()); END IF;
    IF NEW.state = 'refunded' THEN NEW.refunded_cents := NEW.amount_cents; END IF;
    -- Devolução parcial com valor zero, ou igual ao total, é contradição: ou é integral, ou não houve.
    IF NEW.state = 'partially_refunded'
       AND (NEW.refunded_cents <= 0 OR NEW.refunded_cents >= NEW.amount_cents) THEN
      RAISE EXCEPTION 'devolução parcial exige valor entre zero e o total da cobrança'
        USING ERRCODE = '23514';
    END IF;
  ELSE
    IF NEW.paid_at IS DISTINCT FROM OLD.paid_at
       OR NEW.settled_at IS DISTINCT FROM OLD.settled_at THEN
      RAISE EXCEPTION 'datas de pagamento são derivadas da transição' USING ERRCODE = '42501';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_charge_state BEFORE UPDATE ON platform_charges
  FOR EACH ROW EXECUTE FUNCTION charge_state_guard();
CREATE TRIGGER trg_charges_touch BEFORE UPDATE ON platform_charges
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- A trilha é append-only, e é escrita pelo gatilho — não por quem chama. Transição sem registro na
-- trilha seria transição sem explicação.
CREATE FUNCTION charge_record_event() RETURNS trigger LANGUAGE plpgsql
  SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    INSERT INTO charge_events(charge_id, from_state, to_state, origin, actor_user_id, amount_cents, note)
    VALUES (NEW.id, NULL, NEW.state, CASE WHEN app_uid() IS NULL THEN 'system' ELSE 'user' END,
            app_uid(), NEW.amount_cents, 'cobrança criada');
  ELSIF NEW.state IS DISTINCT FROM OLD.state THEN
    INSERT INTO charge_events(charge_id, from_state, to_state, origin, actor_user_id,
                              provider_event_id, amount_cents, note)
    VALUES (NEW.id, OLD.state, NEW.state,
            CASE WHEN app_system() THEN 'webhook' WHEN app_priv() THEN 'admin'
                 WHEN app_uid() IS NULL THEN 'system' ELSE 'user' END,
            app_uid(), NEW.provider_charge_id,
            CASE WHEN NEW.state IN ('refunded','partially_refunded') THEN NEW.refunded_cents END,
            NEW.failure_message);
  END IF;
  RETURN NULL;
END $$;
CREATE TRIGGER trg_charge_event AFTER INSERT OR UPDATE ON platform_charges
  FOR EACH ROW EXECUTE FUNCTION charge_record_event();
COMMENT ON FUNCTION charge_record_event IS
  'SECURITY DEFINER porque impacto_app NÃO tem INSERT em charge_events (REVOKE abaixo): a '
  'trilha é escrita pelo gatilho e por mais ninguém. Conceder INSERT ao app resolveria o erro '
  'de permissão e abriria a porta para alguém inventar uma linha de trilha à mão.';
CREATE TRIGGER trg_charge_events_append BEFORE UPDATE OR DELETE ON charge_events
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- `last4` com mais de quatro caracteres é recusado. Parece exagero e é de propósito: é o campo em que
-- alguém, um dia, grava o número inteiro "só para depurar".
CREATE FUNCTION instrument_no_pan() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.last4 IS NOT NULL AND NEW.last4 !~ '^[0-9]{4}$' THEN
    RAISE EXCEPTION 'last4 aceita exatamente quatro dígitos: a plataforma não guarda número de cartão'
      USING ERRCODE = '23514';
  END IF;
  IF NEW.holder_label IS NOT NULL AND NEW.holder_label ~ '[0-9]{9,}' THEN
    RAISE EXCEPTION 'o rótulo do portador não pode conter sequência longa de dígitos'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_instrument_no_pan BEFORE INSERT OR UPDATE ON payment_instruments
  FOR EACH ROW EXECUTE FUNCTION instrument_no_pan();

-- A soma das parcelas tem de fechar com o total da cobrança. Parcelamento que não fecha é cobrança
-- errada, e a diferença aparece na fatura de alguém.
CREATE FUNCTION installments_sum_matches() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_total bigint; v_sum bigint; v_n smallint;
BEGIN
  SELECT amount_cents, installments INTO v_total, v_n FROM platform_charges
   WHERE id = coalesce(NEW.charge_id, OLD.charge_id);
  SELECT coalesce(sum(amount_cents), 0), count(*) INTO v_sum, v_n
    FROM charge_installments WHERE charge_id = coalesce(NEW.charge_id, OLD.charge_id);
  -- Só confere quando o cronograma está completo: durante a inserção parcela a parcela, a soma
  -- naturalmente não fecha ainda.
  IF v_n = (SELECT installments FROM platform_charges WHERE id = coalesce(NEW.charge_id, OLD.charge_id))
     AND v_sum <> v_total THEN
    RAISE EXCEPTION 'a soma das parcelas (%) difere do total da cobrança (%)', v_sum, v_total
      USING ERRCODE = '23514';
  END IF;
  RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER trg_installments_sum AFTER INSERT OR UPDATE OR DELETE ON charge_installments
  DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION installments_sum_matches();

-- ============================================================================ 5. webhook endurecido
ALTER TABLE billing_events
  ADD COLUMN signature_verified boolean NOT NULL DEFAULT false,
  ADD COLUMN charge_id uuid REFERENCES platform_charges(id) ON DELETE SET NULL,
  ADD COLUMN duplicate_count integer NOT NULL DEFAULT 0;
-- `rejected_signature` é um estado novo e necessário: antes da v0.17.0 um evento sem assinatura
-- válida só podia ser gravado como `failed`, que é o mesmo rótulo de uma falha de processamento. São
-- coisas diferentes — uma é erro nosso, a outra é evento que não comprova nada — e a reconciliação
-- precisa distinguir as duas.
ALTER TABLE billing_events DROP CONSTRAINT billing_events_status_check;
ALTER TABLE billing_events ADD CONSTRAINT billing_events_status_check
  CHECK (status IN ('received','processed','ignored','failed','rejected_signature'));
ALTER TABLE billing_events ADD CONSTRAINT billing_events_signature_effect
  CHECK (signature_verified OR status <> 'processed');
COMMENT ON CONSTRAINT billing_events_signature_effect ON billing_events IS
  'Evento sem assinatura conferida não chega a processed. A regra fica no banco porque "não aplicar" '
  'é a parte que ninguém lembra de testar quando a integração finalmente for ligada.';

COMMENT ON COLUMN billing_events.signature_verified IS
  'Assinatura do provedor conferida. Evento sem assinatura válida NÃO deve produzir efeito: o '
  'frontend nunca é fonte de verdade sobre pagamento.';
COMMENT ON COLUMN billing_events.duplicate_count IS
  'Quantas vezes o MESMO identificador de evento chegou de novo. O UNIQUE(provider, event_id) já '
  'impede efeito duplicado; este contador existe para a reconciliação enxergar reentrega.';
CREATE INDEX ix_billing_events_charge ON billing_events(charge_id) WHERE charge_id IS NOT NULL;

-- ============================================================================ 6. RLS
ALTER TABLE platform_charges ENABLE ROW LEVEL SECURITY;
ALTER TABLE charge_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE charge_installments ENABLE ROW LEVEL SECURITY;
ALTER TABLE charge_pix ENABLE ROW LEVEL SECURITY;
ALTER TABLE charge_boleto ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_instruments ENABLE ROW LEVEL SECURITY;
ALTER TABLE charge_state_graph ENABLE ROW LEVEL SECURITY;

-- A organização vê as próprias cobranças e a trilha delas: "por que esta cobrança falhou" é pergunta
-- que ela tem direito de responder sozinha, sem abrir chamado.
CREATE FUNCTION charge_belongs_to(p_charge uuid, p_org uuid) RETURNS boolean
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM platform_charges WHERE id = p_charge AND org_id = p_org)
$$;
COMMENT ON FUNCTION charge_belongs_to IS
  'SECURITY DEFINER porque as políticas de charge_events, charge_installments, charge_pix e '
  'charge_boleto precisam consultar platform_charges; política que consulta outra tabela direto '
  'produz recursão infinita (ADR-104).';

CREATE POLICY charges_read ON platform_charges FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY charges_insert ON platform_charges FOR INSERT
  WITH CHECK (org_id = app_org() OR app_priv() OR app_system());
CREATE POLICY charges_update ON platform_charges FOR UPDATE
  USING (org_id = app_org() OR app_priv() OR app_system())
  WITH CHECK (org_id = app_org() OR app_priv() OR app_system());

CREATE POLICY charge_events_read ON charge_events FOR SELECT
  USING (charge_belongs_to(charge_id, app_org()) OR app_priv());
CREATE POLICY charge_inst_read ON charge_installments FOR SELECT
  USING (charge_belongs_to(charge_id, app_org()) OR app_priv());
CREATE POLICY charge_inst_write ON charge_installments FOR INSERT
  WITH CHECK (charge_belongs_to(charge_id, app_org()) OR app_priv() OR app_system());
CREATE POLICY charge_inst_update ON charge_installments FOR UPDATE
  USING (app_priv() OR app_system()) WITH CHECK (app_priv() OR app_system());

CREATE POLICY charge_pix_read ON charge_pix FOR SELECT
  USING (charge_belongs_to(charge_id, app_org()) OR app_priv());
CREATE POLICY charge_pix_write ON charge_pix FOR INSERT
  WITH CHECK (charge_belongs_to(charge_id, app_org()) OR app_priv() OR app_system());
CREATE POLICY charge_boleto_read ON charge_boleto FOR SELECT
  USING (charge_belongs_to(charge_id, app_org()) OR app_priv());
CREATE POLICY charge_boleto_write ON charge_boleto FOR INSERT
  WITH CHECK (charge_belongs_to(charge_id, app_org()) OR app_priv() OR app_system());

-- O token do instrumento é da organização e de mais ninguém. A administração da plataforma NÃO lê:
-- não há por que um administrador ver o token de cartão de um cliente.
CREATE POLICY instruments_read ON payment_instruments FOR SELECT USING (org_id = app_org());
CREATE POLICY instruments_write ON payment_instruments FOR INSERT
  WITH CHECK (org_id = app_org() OR app_system());
CREATE POLICY instruments_update ON payment_instruments FOR UPDATE
  USING (org_id = app_org() OR app_system()) WITH CHECK (org_id = app_org() OR app_system());

CREATE POLICY charge_graph_read ON charge_state_graph FOR SELECT USING (app_authenticated() OR app_priv());

GRANT SELECT, INSERT, UPDATE ON platform_charges TO impacto_app;
GRANT SELECT ON charge_events, charge_state_graph TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON charge_installments, charge_pix, charge_boleto TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON payment_instruments TO impacto_app;
REVOKE INSERT, UPDATE, DELETE ON charge_events FROM impacto_app;

-- A organização não reescreve o que o provedor decidiu nem o que a plataforma apurou.
CREATE TRIGGER trg_charges_guard BEFORE UPDATE ON platform_charges
  FOR EACH ROW EXECUTE FUNCTION guard_columns(
    'org_id', 'amount_cents', 'currency', 'provider', 'is_simulated', 'installments', 'kind',
    'billable_event_id');

-- ============================================================================ 7. receita apurada
-- A função que separa receita REAL de simulada. Existe porque somar as duas é o erro mais fácil e mais
-- grave de um painel financeiro: mostraria dinheiro que não entrou.
CREATE FUNCTION platform_revenue(p_from timestamptz DEFAULT NULL, p_to timestamptz DEFAULT NULL)
  RETURNS TABLE (
    currency        char(3),
    real_paid_cents bigint,
    real_settled_cents bigint,
    real_refunded_cents bigint,
    real_charges    bigint,
    simulated_charges bigint,
    simulated_cents bigint)
  LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT c.currency,
    coalesce(sum(c.amount_cents) FILTER (WHERE NOT c.is_simulated AND c.state IN ('paid','settled','partially_refunded')), 0),
    coalesce(sum(c.amount_cents) FILTER (WHERE NOT c.is_simulated AND c.state = 'settled'), 0),
    coalesce(sum(c.refunded_cents) FILTER (WHERE NOT c.is_simulated), 0),
    count(*) FILTER (WHERE NOT c.is_simulated),
    count(*) FILTER (WHERE c.is_simulated),
    coalesce(sum(c.amount_cents) FILTER (WHERE c.is_simulated), 0)
  FROM platform_charges c
  WHERE (p_from IS NULL OR c.created_at >= p_from) AND (p_to IS NULL OR c.created_at < p_to)
  GROUP BY c.currency
$$;
COMMENT ON FUNCTION platform_revenue IS
  'Receita apurada, com o simulado SEPARADO em colunas próprias e nunca somado ao real. Juntar os '
  'dois mostraria dinheiro que não entrou — e é por isso que `is_simulated` é derivada e não '
  'escrevível.';
