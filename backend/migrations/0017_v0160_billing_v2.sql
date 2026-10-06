-- ================================================================================================================
-- v0.16.0 — COBRANÇA v2: preço VERSIONADO, com moeda, vigência, preço de entrada e tratamento de imposto.
--
-- ACHADO QUE ORIGINOU ESTA MIGRAÇÃO (RECONSTRUCTION_AUDIT.md §2.5): `plan_prices(plan_key, interval, amount_cents)`
-- tem TODOS os valores nulos, não tem moeda, não tem vigência, não tem preço de entrada e não guarda o identificador
-- do preço no provedor. A plataforma formata tudo em BRL, enquanto a regra comercial nova é em dólar. E, sem
-- vigência, trocar um preço significa SOBRESCREVER o anterior — ou seja, perder a resposta a "quanto esta
-- organização contratou?".
--
-- REGRA COMERCIAL DESTA RODADA (ditada pelo proprietário do produto):
--   · 14 dias de teste, com o produto completo;
--   · depois, US$ 1,99/mês nos 3 primeiros meses pagos;
--   · depois, US$ 19,99/mês, ou o anual equivalente a US$ 14,99/mês (US$ 179,88/ano), com o total à vista.
--
-- O QUE ESTA MIGRAÇÃO NÃO FAZ, E POR QUÊ:
--   · não cria identificador de preço no Stripe (`provider_price_id` fica NULO). Esse identificador existe na conta
--     do provedor e precisa ser criado lá; inventar um faria o checkout falhar em produção com erro obscuro, em vez
--     de a plataforma dizer claramente que falta configurar. `price_resolve()` recusa cobrar sem ele.
--   · não ativa cobrança. `feature_flags.billing_live` continua decidindo isso.
-- ================================================================================================================

-- ------------------------------------------------------------------------------------------------ preço versionado
CREATE TABLE plan_price_versions (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_key      text NOT NULL REFERENCES plans(plan_key) ON DELETE CASCADE,
  interval      text NOT NULL CHECK (interval IN ('month','year')),
  currency      char(3) NOT NULL CHECK (currency ~ '^[A-Z]{3}$'),

  -- PREÇO REGULAR, em centavos da moeda. É o que a organização paga depois do período de entrada.
  amount_cents  bigint NOT NULL CHECK (amount_cents >= 0),

  -- PREÇO DE ENTRADA (promocional), opcional. Os dois campos andam juntos: preço sem duração, ou duração sem preço,
  -- seriam uma promoção sem fim definido — exatamente o padrão escuro que o pedido proíbe.
  intro_amount_cents bigint CHECK (intro_amount_cents IS NULL OR intro_amount_cents >= 0),
  intro_periods smallint CHECK (intro_periods IS NULL OR intro_periods BETWEEN 1 AND 36),
  CONSTRAINT intro_pair CHECK ((intro_amount_cents IS NULL) = (intro_periods IS NULL)),
  CONSTRAINT intro_is_cheaper CHECK (intro_amount_cents IS NULL OR intro_amount_cents <= amount_cents),

  -- Dias de teste desta versão de preço. NULO = usa o padrão da plataforma (`settings.trial_days`).
  trial_days    smallint CHECK (trial_days IS NULL OR trial_days BETWEEN 0 AND 90),

  -- VIGÊNCIA. É isto que torna o histórico possível: trocar preço é criar uma versão nova, nunca sobrescrever.
  effective_from  timestamptz NOT NULL DEFAULT now(),
  effective_until timestamptz,
  CONSTRAINT effective_order CHECK (effective_until IS NULL OR effective_until > effective_from),

  -- IMPOSTO: 'inclusive' = valor já contém imposto; 'exclusive' = imposto somado no checkout; 'unspecified' = não
  -- declarado, e nesse caso a plataforma não promete nada sobre imposto na tela.
  tax_behavior  text NOT NULL DEFAULT 'unspecified'
                  CHECK (tax_behavior IN ('inclusive','exclusive','unspecified')),

  -- Identificadores NO PROVEDOR. Nulos até serem criados na conta real; `price_resolve` recusa cobrar sem eles.
  provider      text CHECK (provider IS NULL OR provider IN ('stripe','manual')),
  provider_price_id       text CHECK (provider_price_id IS NULL OR length(provider_price_id) BETWEEN 3 AND 200),
  provider_intro_price_id text CHECK (provider_intro_price_id IS NULL
                                      OR length(provider_intro_price_id) BETWEEN 3 AND 200),

  -- por que este preço existe (decisão comercial, reajuste, promoção de lançamento)
  reason        text NOT NULL CHECK (length(reason) BETWEEN 3 AND 500),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
-- Uma versão VIGENTE por (plano, intervalo, moeda). Vigência aberta é a atual; fechar a anterior é o que permite
-- a nova entrar — e é por isso que o índice só olha `effective_until IS NULL`.
CREATE UNIQUE INDEX ux_price_current ON plan_price_versions(plan_key, interval, currency)
  WHERE effective_until IS NULL;
CREATE INDEX ix_price_plan ON plan_price_versions(plan_key, interval, currency, effective_from DESC);
COMMENT ON TABLE plan_price_versions IS
  'Preço por plano, intervalo e MOEDA, com vigência. Trocar preço cria versão nova; a anterior fecha a vigência e
   permanece, de modo que "quanto esta organização contratou em março?" tem resposta. Nenhum preço no código.';
COMMENT ON COLUMN plan_price_versions.provider_price_id IS
  'Identificador do preço na conta do provedor. NULO significa não configurado — e a plataforma recusa cobrar, em
   vez de tentar com um valor inventado e falhar no provedor.';

-- ------------------------------------------------------------------------------------------------ preço contratado
-- O preço que a organização aceitou, congelado no momento da contratação. Sem isto, um reajuste reescreveria
-- retroativamente o que cada uma concordou em pagar.
CREATE TABLE subscription_prices (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  subscription_id uuid REFERENCES subscriptions(id) ON DELETE SET NULL,
  price_version_id uuid NOT NULL REFERENCES plan_price_versions(id) ON DELETE RESTRICT,
  plan_key      text NOT NULL,
  interval      text NOT NULL,
  currency      char(3) NOT NULL,
  amount_cents  bigint NOT NULL,
  intro_amount_cents bigint,
  intro_periods smallint,
  -- quantos períodos de entrada já foram cobrados; o webhook de fatura paga incrementa
  intro_periods_used smallint NOT NULL DEFAULT 0 CHECK (intro_periods_used >= 0),
  tax_behavior  text NOT NULL,
  accepted_at   timestamptz NOT NULL DEFAULT now(),
  accepted_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  ends_at       timestamptz,
  CONSTRAINT intro_used_within CHECK (intro_periods IS NULL OR intro_periods_used <= intro_periods)
);
CREATE INDEX ix_subprice_org ON subscription_prices(org_id, accepted_at DESC);
CREATE UNIQUE INDEX ux_subprice_live ON subscription_prices(org_id) WHERE ends_at IS NULL;
COMMENT ON TABLE subscription_prices IS
  'O preço que a organização ACEITOU, congelado. Reajuste não reescreve o passado: cria outra linha.';

-- ------------------------------------------------------------------------------------------------ aviso de reajuste
-- "nunca mudar preço silenciosamente": a plataforma não consegue aplicar um preço novo a quem já é cliente sem que
-- exista o registro do aviso, porque `price_apply_guard()` recusa.
CREATE TABLE price_change_notices (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id        uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  from_price_version_id uuid REFERENCES plan_price_versions(id) ON DELETE SET NULL,
  to_price_version_id   uuid NOT NULL REFERENCES plan_price_versions(id) ON DELETE CASCADE,
  from_amount_cents bigint,
  to_amount_cents   bigint NOT NULL,
  currency      char(3) NOT NULL,
  -- quando o preço novo passa a valer para ESTA organização (nunca antes do aviso + carência)
  effective_at  timestamptz NOT NULL,
  notified_at   timestamptz NOT NULL DEFAULT now(),
  channel       text NOT NULL CHECK (channel IN ('in_app','email','both')),
  acknowledged_at timestamptz,
  acknowledged_by uuid REFERENCES users(id) ON DELETE SET NULL,
  reason        text NOT NULL CHECK (length(reason) BETWEEN 3 AND 500),
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT notice_before_effect CHECK (effective_at > notified_at)
);
CREATE INDEX ix_pricenotice_org ON price_change_notices(org_id, notified_at DESC);
COMMENT ON TABLE price_change_notices IS
  'Aviso de mudança de preço a uma organização. A carência mínima é verificada por gatilho: o preço novo não pode
   valer antes do aviso. Sem aviso registrado, trocar o preço contratado é recusado pelo banco.';

-- ------------------------------------------------------------------------------------------------ carência mínima
CREATE FUNCTION price_notice_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  -- 30 dias é a carência que a plataforma se impõe. Avisar na véspera é tecnicamente "avisar" e na prática não é.
  IF NEW.effective_at < NEW.notified_at + interval '30 days' THEN
    RAISE EXCEPTION 'Mudança de preço exige aviso com pelo menos 30 dias de antecedência (avisado em %, valeria em %)',
      NEW.notified_at, NEW.effective_at USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_price_notice BEFORE INSERT ON price_change_notices FOR EACH ROW
  EXECUTE FUNCTION price_notice_guard();

-- Trocar o preço de uma organização exige aviso registrado e já vigente.
CREATE FUNCTION price_apply_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prev record;
BEGIN
  SELECT * INTO prev FROM subscription_prices
   WHERE org_id = NEW.org_id AND ends_at IS NULL AND id <> NEW.id
   ORDER BY accepted_at DESC LIMIT 1;
  IF prev IS NULL THEN RETURN NEW; END IF;                       -- primeira contratação: não há o que avisar
  IF prev.price_version_id = NEW.price_version_id THEN RETURN NEW; END IF;
  IF prev.amount_cents >= NEW.amount_cents AND prev.currency = NEW.currency THEN
    RETURN NEW;                                                   -- preço igual ou MENOR não precisa de carência
  END IF;
  IF NOT EXISTS (SELECT 1 FROM price_change_notices n
                  WHERE n.org_id = NEW.org_id AND n.to_price_version_id = NEW.price_version_id
                    AND n.effective_at <= now()) THEN
    RAISE EXCEPTION 'Aumento de preço exige aviso prévio registrado e já vigente para esta organização'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_price_apply BEFORE INSERT ON subscription_prices FOR EACH ROW
  EXECUTE FUNCTION price_apply_guard();

-- ------------------------------------------------------------------------------------------------ preço vigente
CREATE FUNCTION price_current(p_plan text, p_interval text, p_currency text)
RETURNS plan_price_versions LANGUAGE sql STABLE AS $$
  SELECT * FROM plan_price_versions
   WHERE plan_key = p_plan AND interval = p_interval AND currency = upper(p_currency)
     AND effective_from <= now() AND (effective_until IS NULL OR effective_until > now())
   ORDER BY effective_from DESC LIMIT 1;
$$;
COMMENT ON FUNCTION price_current(text, text, text) IS
  'Versão de preço vigente agora. Uma definição; o servidor é a autoridade e o cliente nunca envia valor.';

CREATE TRIGGER trg_touch BEFORE UPDATE ON plan_price_versions FOR EACH ROW
  EXECUTE FUNCTION touch_updated_at();

-- ------------------------------------------------------------------------------------------------ imutabilidade
-- `guard_columns` NÃO serve aqui, e isso foi descoberto escrevendo o teste: ele dispensa o contexto privilegiado, e
-- o contexto privilegiado é justamente o único que escreve nesta tabela (o papel da aplicação só tem SELECT). Um
-- gatilho que nunca morde é pior do que nenhum: documenta uma garantia que não existe.
--
-- A regra verdadeira é: valor, moeda e vigência inicial de uma versão NÃO mudam, nem pela administração. Mudar
-- preço é fechar a vigência da versão atual e criar outra. Só o DONO do banco (migração) pode mexer, e aí o rastro
-- está no arquivo de migração.
CREATE FUNCTION price_version_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE col text;
BEGIN
  IF current_user::text <> 'impacto_app' THEN RETURN NEW; END IF;   -- dono do banco: migração, com rastro em arquivo
  FOREACH col IN ARRAY ARRAY['plan_key','interval','currency','amount_cents','intro_amount_cents','intro_periods',
                             'effective_from'] LOOP
    IF (to_jsonb(NEW) -> col) IS DISTINCT FROM (to_jsonb(OLD) -> col) THEN
      RAISE EXCEPTION 'Versão de preço não se reescreve (%): feche a vigência e crie outra versão', col
        USING ERRCODE = '42501';
    END IF;
  END LOOP;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_price_immutable BEFORE UPDATE ON plan_price_versions FOR EACH ROW
  EXECUTE FUNCTION price_version_immutable();

-- O aviso de reajuste é append-only EXCETO a confirmação de leitura — que é a única coisa que a organização
-- acrescenta a ele. `forbid_mutation` puro bloquearia a confirmação e tornaria o aviso impossível de reconhecer.
CREATE FUNCTION price_notice_ack_only() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE col text;
BEGIN
  IF current_user::text <> 'impacto_app' OR app_priv() THEN RETURN NEW; END IF;
  FOR col IN SELECT k FROM jsonb_object_keys(to_jsonb(NEW)) AS k LOOP
    IF (to_jsonb(NEW) -> col) IS DISTINCT FROM (to_jsonb(OLD) -> col)
       AND col NOT IN ('acknowledged_at','acknowledged_by') THEN
      RAISE EXCEPTION 'Aviso de reajuste não se altera; só a confirmação de leitura (%)', col
        USING ERRCODE = '42501';
    END IF;
  END LOOP;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_notice_ack BEFORE UPDATE ON price_change_notices FOR EACH ROW
  EXECUTE FUNCTION price_notice_ack_only();
CREATE TRIGGER trg_no_delete BEFORE DELETE ON price_change_notices FOR EACH ROW
  WHEN (current_user::text = 'impacto_app') EXECUTE FUNCTION forbid_mutation();

-- ------------------------------------------------------------------------------------------------ RLS
ALTER TABLE plan_price_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscription_prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_change_notices ENABLE ROW LEVEL SECURITY;

-- O catálogo de preços é público por natureza (é a tabela de preços do produto).
CREATE POLICY price_read ON plan_price_versions FOR SELECT USING (true);
CREATE POLICY price_write ON plan_price_versions FOR ALL USING (app_priv()) WITH CHECK (app_priv());
-- O preço contratado é da organização; ela precisa poder conferir o que aceitou.
CREATE POLICY subprice_read ON subscription_prices FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY subprice_write ON subscription_prices FOR ALL USING (app_priv()) WITH CHECK (app_priv());
CREATE POLICY pricenotice_read ON price_change_notices FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY pricenotice_write ON price_change_notices FOR INSERT WITH CHECK (app_priv());
CREATE POLICY pricenotice_admin ON price_change_notices FOR DELETE USING (app_priv());
-- A organização registra que VIU o aviso. Precisa de três coisas ao mesmo tempo, e as três são estreitas:
-- política de UPDATE para as suas linhas, GRANT das duas colunas, e o gatilho que recusa alterar qualquer outra.
CREATE POLICY pricenotice_ack ON price_change_notices FOR UPDATE
  USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());
GRANT UPDATE (acknowledged_at, acknowledged_by) ON price_change_notices TO impacto_app;

GRANT SELECT ON plan_price_versions TO impacto_app;
-- A administração precisa poder fazer DUAS coisas sem criar versão nova: publicar o identificador do preço no
-- provedor (que não é preço) e FECHAR a vigência de uma versão (que é como se troca de preço). As colunas de valor
-- ficam fora do GRANT e, além disso, `price_version_immutable()` as recusa — duas trancas, porque é dinheiro.
GRANT UPDATE (effective_until, provider, provider_price_id, provider_intro_price_id, trial_days, tax_behavior,
              reason, updated_at) ON plan_price_versions TO impacto_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON subscription_prices TO impacto_app;
GRANT SELECT, INSERT ON price_change_notices TO impacto_app;
GRANT EXECUTE ON FUNCTION price_current(text, text, text) TO impacto_app;

-- ------------------------------------------------------------------------------------------------ onde ficam os preços
-- Os VALORES não estão aqui. Ficam em `config/plans.json` (seção `price_versions`), sincronizados por
-- `sync_reference_data`, por duas razões concretas:
--   · esta migração roda ANTES de o catálogo de planos existir, então um INSERT ... SELECT FROM plans não encontraria
--     nada (foi o que aconteceu na primeira tentativa: zero linhas inseridas, em silêncio);
--   · preço precisa mudar sem alteração de código, e com histórico — o sincronizador fecha a vigência da versão
--     anterior e cria a nova em vez de sobrescrever.
COMMENT ON COLUMN plan_price_versions.intro_periods IS
  'Quantos períodos são cobrados ao preço de entrada. 3 meses a US$ 1,99 nesta rodada; depois o preço regular, com
   o aviso de transição mostrado no checkout (não é padrão escuro se está escrito antes de pagar).';
