-- 0068 — v0.28.0 — IA SUSTENTÁVEL: catálogo de operações, cotas configuráveis, execuções com estado,
-- créditos por lote (comprado / promocional / patrocinado), pedidos de crédito por PIX, patrocínio de
-- uso, motor de originalidade/similaridade/complementaridade e contestação (ADR-347 a ADR-352).
--
-- O que a inspeção encontrou (docs/execution/AI_INVENTORY.md): a camada de IA JÁ tinha governança de
-- prompt, faixa de risco, uso registrado, tabela de preço do provedor (vazia de propósito), orçamento
-- em dinheiro por organização e um razão de créditos append-only — mas NENHUMA chamada consumia
-- crédito, a cota era um número fixo no catálogo de pacotes (`ai_requests_month`) e não existia
-- operação com estado, estimativa antes de executar, fonte de custeio, patrocínio, pedido de crédito
-- nem conciliação entre custo previsto e apurado. Esta migração liga as peças que faltavam.
--
-- Princípios que o banco impõe aqui:
--   * nenhuma execução debita crédito sem passar por AUTHORIZED → RESERVED → RUNNING → SUCCEEDED;
--     falha, parcial e cancelamento NÃO debitam (política declarada na operação, não no código);
--   * saldo é soma do razão; crédito reservado é descontado do DISPONÍVEL por consulta, nunca por
--     coluna atualizada; consumo é atômico por organização (bloqueio consultivo);
--   * crédito comprado só nasce de pedido com pagamento CONFIRMADO (webhook assinado ou conciliação
--     manual pela administração com referência); a página de retorno nunca credita;
--   * patrocínio tem orçamento, período, elegibilidade e limites; esgotado, para — nunca migra em
--     silêncio para cobrança da organização beneficiada;
--   * a análise de similaridade é motor LOCAL (faixa 3: fala de terceiro, não sai da instalação),
--     devolve dimensões separadas e NUNCA um percentual único como prova; contestação é fluxo;
--   * preço (em créditos) e preço do crédito (em centavos) vêm de tabelas versionadas, marcadas
--     HIPÓTESE até a administração ativar — nenhum preço é vendido por padrão.

-- ============================================================================ 1. catálogo de operações (versionado)
CREATE TABLE ai_operations (
  id               bigserial PRIMARY KEY,
  code             text NOT NULL CHECK (code ~ '^[a-z][a-z0-9_.]{2,60}$'),
  version          int  NOT NULL CHECK (version >= 1),
  name_pt          text NOT NULL CHECK (length(name_pt) BETWEEN 3 AND 120),
  description_pt   text NOT NULL CHECK (length(description_pt) BETWEEN 20 AND 1200),
  purpose_pt       text NOT NULL CHECK (length(purpose_pt) BETWEEN 10 AND 400),
  category         char(1) NOT NULL CHECK (category IN ('A','B','C','D','E','F')),
  tier             smallint NOT NULL REFERENCES ai_model_policies(tier),
  allowed_kinds    text[] NOT NULL DEFAULT '{osc,company,government,individual,provider}',
  min_role         text NOT NULL DEFAULT 'member' CHECK (min_role IN ('viewer','member','manager','admin','owner')),
  data_requirements_pt text NOT NULL CHECK (length(data_requirements_pt) BETWEEN 5 AND 600),
  provider_mode    text NOT NULL CHECK (provider_mode IN ('local','external_allowed')),
  funding_modes    text[] NOT NULL DEFAULT '{free_quota,sponsorship,credits}',
  credits_base     int  NOT NULL CHECK (credits_base >= 0),
  credits_per_unit int  NOT NULL DEFAULT 0 CHECK (credits_per_unit >= 0),
  unit_label_pt    text NOT NULL DEFAULT 'execução',
  max_units        int  NOT NULL DEFAULT 1 CHECK (max_units >= 1),
  max_input_chars  int  NOT NULL CHECK (max_input_chars > 0),
  free_quota_eligible boolean NOT NULL DEFAULT true,
  sponsor_eligible    boolean NOT NULL DEFAULT true,
  completion_rule_pt  text NOT NULL CHECK (length(completion_rule_pt) BETWEEN 10 AND 600),
  failure_policy   text NOT NULL DEFAULT 'no_charge_on_failure'
                   CHECK (failure_policy IN ('no_charge_on_failure')),
  delivers_pt      text NOT NULL CHECK (length(delivers_pt) BETWEEN 10 AND 600),
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','hypothesis','planned','retired')),
  note             text,
  created_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (code, version)
);
COMMENT ON TABLE ai_operations IS
  'Catálogo VERSIONADO de operações de IA: categoria (A–F), faixa de risco, quem pode, de onde o dinheiro '
  'vem, quanto custa em créditos, limites e critério de conclusão. Imutável por linha: mudar preço ou '
  'limite cria versão nova; execuções antigas guardam a versão que as autorizou.';
COMMENT ON COLUMN ai_operations.status IS
  'active = executável e cobrável conforme funding_modes; hypothesis = preço é hipótese de teste (executa, '
  'mas a interface diz que o preço é piloto); planned = declarada no catálogo e NÃO implementada (a rota '
  'responde 501); retired = não executa mais.';
CREATE UNIQUE INDEX ux_ai_operations_current ON ai_operations (code) WHERE status IN ('active','hypothesis','planned');

-- Catálogo versionado: a única mudança permitida numa linha é APOSENTAR (status → retired), para que a versão
-- seguinte possa nascer; preço, limites e texto nunca mudam em linha existente.
CREATE OR REPLACE FUNCTION ai_catalog_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'catálogo de IA é append-only: aposente a versão em vez de apagar' USING ERRCODE = '42501';
  END IF;
  IF NEW.status <> 'retired' OR OLD.status = 'retired'
     OR row_to_json(NEW)::jsonb - 'status' <> row_to_json(OLD)::jsonb - 'status' THEN
    RAISE EXCEPTION 'catálogo de IA: a única alteração permitida é status → retired (publique uma versão nova)' USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_ai_operations_guard BEFORE UPDATE OR DELETE ON ai_operations FOR EACH ROW EXECUTE FUNCTION ai_catalog_guard();

-- Versão vigente de uma operação (a mais recente não aposentada).
CREATE OR REPLACE FUNCTION ai_operation_current(p_code text) RETURNS ai_operations LANGUAGE sql STABLE AS $$
  SELECT o FROM ai_operations o WHERE o.code = p_code AND o.status IN ('active','hypothesis','planned')
  ORDER BY o.version DESC LIMIT 1
$$;

-- ============================================================================ 2. lotes de crédito e razão
-- Crédito é unidade comercial da plataforma (ADR-233); o razão já existia (0058) e era append-only.
-- O que faltava: separar DE ONDE o crédito veio (comprado, promocional, patrocinado), quando expira,
-- e os motivos de compra/expiração — porque "créditos vendidos" é obrigação com o cliente, e
-- "promocional" é custo da plataforma. Misturar os dois faria receita de concessão.
ALTER TABLE ai_credit_ledger ADD COLUMN IF NOT EXISTS bucket text NOT NULL DEFAULT 'promotional';
ALTER TABLE ai_credit_ledger DROP CONSTRAINT IF EXISTS ai_credit_bucket_known;
ALTER TABLE ai_credit_ledger ADD CONSTRAINT ai_credit_bucket_known CHECK (bucket IN ('purchased','promotional'));
ALTER TABLE ai_credit_ledger ADD COLUMN IF NOT EXISTS expires_at timestamptz;
ALTER TABLE ai_credit_ledger ADD COLUMN IF NOT EXISTS execution_id uuid;
ALTER TABLE ai_credit_ledger DROP CONSTRAINT IF EXISTS ai_credit_ledger_reason_check;
ALTER TABLE ai_credit_ledger ADD CONSTRAINT ai_credit_ledger_reason_check
  CHECK (reason IN ('grant','plan_cycle','consumption','refund','adjustment','expiry','purchase','sponsor_commit','release'));
ALTER TABLE ai_credit_ledger DROP CONSTRAINT IF EXISTS credit_sign_matches_reason;
ALTER TABLE ai_credit_ledger ADD CONSTRAINT credit_sign_matches_reason CHECK (
  (reason IN ('grant','plan_cycle','refund','purchase','release') AND delta > 0)
  OR (reason IN ('consumption','expiry','sponsor_commit') AND delta < 0)
  OR reason = 'adjustment');
COMMENT ON COLUMN ai_credit_ledger.bucket IS
  'purchased = pago (obrigação com o cliente até consumir); promotional = concedido pela plataforma (custo '
  'da gratuidade). Patrocínio não é lote do beneficiário: o patrocinador COMPROMETE créditos do próprio '
  'razão (sponsor_commit) e a execução custeada registra funding_source = sponsorship.';

-- Saldo por lote (soma do razão, nunca coluna).
CREATE OR REPLACE FUNCTION ai_credit_balance_bucket(p_org uuid, p_bucket text) RETURNS bigint LANGUAGE sql STABLE AS $$
  SELECT coalesce(sum(delta), 0)::bigint FROM ai_credit_ledger WHERE org_id = p_org AND bucket = p_bucket
     AND (expires_at IS NULL OR expires_at > now() OR delta < 0)
$$;

-- ============================================================================ 3. execuções (máquina de estados)
CREATE TABLE ai_executions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid NOT NULL REFERENCES organizations(id),
  user_id          uuid REFERENCES users(id) ON DELETE SET NULL,
  operation_code   text NOT NULL,
  operation_version int NOT NULL,
  category         char(1) NOT NULL,
  project_id       uuid REFERENCES projects(id) ON DELETE SET NULL,
  subject_ref      text,                      -- id do segundo projeto, documento, etc.
  params_sha256    char(64) NOT NULL,
  units            int NOT NULL DEFAULT 1 CHECK (units >= 1),
  estimated_credits int NOT NULL CHECK (estimated_credits >= 0),
  reserved_credits  int NOT NULL DEFAULT 0 CHECK (reserved_credits >= 0),
  charged_credits   int NOT NULL DEFAULT 0 CHECK (charged_credits >= 0),
  funding_source   text NOT NULL CHECK (funding_source IN ('free','promotional','purchased','sponsorship','cached')),
  sponsorship_id   uuid,
  state            text NOT NULL DEFAULT 'created' CHECK (state IN
                   ('created','authorized','reserved','running','succeeded','failed','partial','cancelled','reconciled')),
  idempotency_key  text,
  estimated_cost_cents numeric(12,4),
  actual_cost_cents    numeric(12,4),
  cost_status      text NOT NULL DEFAULT 'pending' CHECK (cost_status IN ('pending','local_no_cost','estimated','measured','no_price_table')),
  provider         text,
  model            text,
  prompt_version   text,
  tokens_in        int,
  tokens_out       int,
  latency_ms       int,
  result_type      text,
  result_id        text,
  error_code       text,
  request_id       text,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  finished_at      timestamptz,
  CONSTRAINT exec_charge_needs_success CHECK (charged_credits = 0 OR state IN ('succeeded','reconciled'))
);
CREATE UNIQUE INDEX ux_ai_exec_idempotency ON ai_executions (org_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX ix_ai_exec_org ON ai_executions (org_id, created_at DESC);
CREATE INDEX ix_ai_exec_open ON ai_executions (org_id) WHERE state IN ('reserved','running');
CREATE INDEX ix_ai_exec_sponsor ON ai_executions (sponsorship_id) WHERE sponsorship_id IS NOT NULL;
ALTER TABLE ai_credit_ledger ADD CONSTRAINT ai_credit_ledger_execution_fk FOREIGN KEY (execution_id) REFERENCES ai_executions(id) ON DELETE SET NULL;

CREATE TABLE ai_execution_events (
  id            bigserial PRIMARY KEY,
  execution_id  uuid NOT NULL REFERENCES ai_executions(id) ON DELETE CASCADE,
  from_state    text,
  to_state      text NOT NULL,
  actor_user_id uuid,
  note          text,
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_exec_events ON ai_execution_events (execution_id, id);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON ai_execution_events FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

CREATE TABLE ai_execution_state_graph (from_state text NOT NULL, to_state text NOT NULL, PRIMARY KEY (from_state, to_state));
INSERT INTO ai_execution_state_graph VALUES
  ('created','authorized'), ('created','cancelled'), ('created','failed'),
  ('authorized','reserved'), ('authorized','cancelled'), ('authorized','failed'),
  ('reserved','running'), ('reserved','cancelled'), ('reserved','failed'),
  ('running','succeeded'), ('running','failed'), ('running','partial'),
  ('succeeded','reconciled'), ('partial','reconciled'), ('failed','reconciled');

CREATE OR REPLACE FUNCTION ai_execution_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.state <> OLD.state THEN
    IF NOT EXISTS (SELECT 1 FROM ai_execution_state_graph WHERE from_state = OLD.state AND to_state = NEW.state) THEN
      RAISE EXCEPTION 'execução de IA: transição % → % não existe', OLD.state, NEW.state USING ERRCODE = '23514';
    END IF;
    INSERT INTO ai_execution_events(execution_id, from_state, to_state, actor_user_id)
    VALUES (NEW.id, OLD.state, NEW.state, app_uid());
    IF NEW.state IN ('succeeded','failed','partial','cancelled') THEN NEW.finished_at := coalesce(NEW.finished_at, now()); END IF;
  END IF;
  -- campos que identificam a autorização não mudam depois dela
  IF OLD.state <> 'created' AND (NEW.operation_code <> OLD.operation_code OR NEW.operation_version <> OLD.operation_version
      OR NEW.estimated_credits <> OLD.estimated_credits OR NEW.funding_source <> OLD.funding_source OR NEW.org_id <> OLD.org_id) THEN
    RAISE EXCEPTION 'execução de IA: operação, crédito estimado e fonte de custeio são imutáveis após a autorização' USING ERRCODE = '23514';
  END IF;
  IF NEW.charged_credits > 0 AND NEW.charged_credits > OLD.reserved_credits AND NEW.funding_source IN ('promotional','purchased','sponsorship') THEN
    RAISE EXCEPTION 'execução de IA: cobrado (%) acima do reservado (%)', NEW.charged_credits, OLD.reserved_credits USING ERRCODE = '23514';
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_ai_execution_guard BEFORE UPDATE ON ai_executions FOR EACH ROW EXECUTE FUNCTION ai_execution_guard();

-- Créditos reservados por execuções abertas (não aparecem no razão: a reserva é estado, o consumo é lançamento).
CREATE OR REPLACE FUNCTION ai_credit_reserved(p_org uuid, p_bucket text) RETURNS bigint LANGUAGE sql STABLE AS $$
  SELECT coalesce(sum(reserved_credits), 0)::bigint FROM ai_executions
   WHERE org_id = p_org AND state IN ('reserved','running')
     AND funding_source = p_bucket
$$;

CREATE OR REPLACE FUNCTION ai_credit_available(p_org uuid, p_bucket text) RETURNS bigint LANGUAGE sql STABLE AS $$
  SELECT ai_credit_balance_bucket(p_org, p_bucket) - ai_credit_reserved(p_org, p_bucket)
$$;

-- CONSUMO ATÔMICO POR LOTE (substitui a função da 0058, que não conhecia lotes nem execuções).
CREATE OR REPLACE FUNCTION ai_credit_consume_bucket(
  p_org uuid, p_bucket text, p_credits int, p_execution uuid, p_idempotency text)
RETURNS TABLE(charged int, balance_after bigint, outcome text) LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE saldo bigint; existente int;
BEGIN
  IF p_credits <= 0 THEN RETURN QUERY SELECT 0, ai_credit_balance_bucket(p_org, p_bucket), 'nothing_to_charge'; RETURN; END IF;
  PERFORM pg_advisory_xact_lock(hashtext('ai_credit:' || p_org::text));
  IF p_idempotency IS NOT NULL THEN
    SELECT -delta INTO existente FROM ai_credit_ledger WHERE org_id = p_org AND idempotency_key = p_idempotency;
    IF existente IS NOT NULL THEN
      RETURN QUERY SELECT existente, ai_credit_balance_bucket(p_org, p_bucket), 'already_charged'; RETURN;
    END IF;
  END IF;
  -- a própria execução já reservou: o saldo bruto do lote tem de cobrir (a reserva dela não conta contra ela)
  saldo := ai_credit_balance_bucket(p_org, p_bucket);
  IF saldo < p_credits THEN RETURN QUERY SELECT 0, saldo, 'insufficient'; RETURN; END IF;
  IF NOT (app_priv() OR app_system()) AND (p_org IS DISTINCT FROM app_org()
     OR NOT EXISTS (SELECT 1 FROM ai_executions e WHERE e.id = p_execution AND e.org_id = p_org)) THEN
    RAISE EXCEPTION 'consumo exige execução da própria organização' USING ERRCODE = '42501';
  END IF;
  INSERT INTO ai_credit_ledger (org_id, delta, reason, bucket, ref_type, ref_id, idempotency_key, execution_id, created_by)
  VALUES (p_org, -p_credits, 'consumption', p_bucket, 'ai_execution', p_execution::text, p_idempotency, p_execution, app_uid());
  RETURN QUERY SELECT p_credits, ai_credit_balance_bucket(p_org, p_bucket), 'charged';
END $$;
REVOKE ALL ON FUNCTION ai_credit_consume_bucket(uuid,text,int,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ai_credit_consume_bucket(uuid,text,int,uuid,text) TO impacto_app;

-- ============================================================================ 4. cotas configuráveis
CREATE TABLE ai_quota_policies (
  id            bigserial PRIMARY KEY,
  key           text NOT NULL UNIQUE CHECK (key ~ '^[a-z][a-z0-9_.]{2,60}$'),
  label_pt      text NOT NULL CHECK (length(label_pt) BETWEEN 3 AND 120),
  scope         text NOT NULL CHECK (scope IN ('welcome','periodic','campaign','kind','demo','institutional')),
  applies_to_kinds text[] NOT NULL DEFAULT '{osc,company,government,individual,provider}',
  credits       int NOT NULL CHECK (credits > 0),
  period        text NOT NULL DEFAULT 'once' CHECK (period IN ('once','month')),
  validity_days int CHECK (validity_days IS NULL OR validity_days > 0),
  max_grants_per_org int NOT NULL DEFAULT 1 CHECK (max_grants_per_org >= 1),
  one_per_user  boolean NOT NULL DEFAULT true,   -- anti-abuso: a mesma pessoa não ganha a cota de novo criando outra organização
  valid_from    date NOT NULL DEFAULT current_date,
  valid_until   date,
  active        boolean NOT NULL DEFAULT true,
  note          text NOT NULL CHECK (length(note) >= 20),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE ai_quota_policies IS
  'Gratuidade CONFIGURÁVEL e orçada: cada política diz a quem se aplica, quantos créditos, com que validade e '
  'quantas vezes por organização. Que operações aceitam cota é dito pela operação (free_quota_eligible). '
  'Nenhum limite fixo no código.';
CREATE TRIGGER trg_ai_quota_touch BEFORE UPDATE ON ai_quota_policies FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

CREATE TABLE ai_quota_grants (
  id            bigserial PRIMARY KEY,
  policy_id     bigint NOT NULL REFERENCES ai_quota_policies(id),
  org_id        uuid NOT NULL REFERENCES organizations(id),
  user_id       uuid REFERENCES users(id) ON DELETE SET NULL,
  period_key    text NOT NULL DEFAULT 'once',
  ledger_id     bigint REFERENCES ai_credit_ledger(id),
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (policy_id, org_id, period_key)
);
-- uma pessoa, uma cota de boas-vindas — em qualquer organização que ela crie
CREATE UNIQUE INDEX ux_ai_quota_one_per_user ON ai_quota_grants (policy_id, user_id, period_key) WHERE user_id IS NOT NULL;
-- a conferência atravessa organizações (a concessão anterior é de OUTRA organização, invisível pela RLS): só sim/não sai
CREATE OR REPLACE FUNCTION ai_quota_user_has(p_policy bigint, p_user uuid, p_period text) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (SELECT 1 FROM ai_quota_grants WHERE policy_id = p_policy AND user_id = p_user AND period_key = p_period)
$$;
REVOKE ALL ON FUNCTION ai_quota_user_has(bigint, uuid, text) FROM PUBLIC;
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON ai_quota_grants FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ============================================================================ 5. patrocínio de uso
CREATE TABLE ai_sponsorships (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sponsor_org_id   uuid NOT NULL REFERENCES organizations(id),
  name_pt          text NOT NULL CHECK (length(name_pt) BETWEEN 3 AND 160),
  budget_credits   int  NOT NULL CHECK (budget_credits > 0),
  starts_on        date NOT NULL DEFAULT current_date,
  ends_on          date NOT NULL,
  eligible_kinds   text[] NOT NULL DEFAULT '{osc}',
  eligible_org_ids uuid[] NOT NULL DEFAULT '{}',   -- vazio = qualquer organização dos tipos elegíveis
  eligible_uf      char(2),
  operations       text[] NOT NULL DEFAULT '{*}',
  per_org_limit    int CHECK (per_org_limit IS NULL OR per_org_limit > 0),
  per_project_limit int CHECK (per_project_limit IS NULL OR per_project_limit > 0),
  accountability_pt text NOT NULL CHECK (length(accountability_pt) BETWEEN 10 AND 1000),
  status           text NOT NULL DEFAULT 'active' CHECK (status IN ('active','exhausted','closed')),
  closed_at        timestamptz,
  created_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CHECK (ends_on >= starts_on)
);
COMMENT ON TABLE ai_sponsorships IS
  'Um financiador, governo ou empresa custeia operações de IA para organizações elegíveis. Orçamento em '
  'créditos, período, elegibilidade, operações, limites por organização e por projeto, prestação de contas. '
  'Esgotado ou encerrado, NÃO migra para cobrança do beneficiário.';
CREATE TRIGGER trg_ai_sponsor_touch BEFORE UPDATE ON ai_sponsorships FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- consumo do patrocínio = execuções bem-sucedidas custeadas por ele (créditos cobrados) + reservas abertas.
-- SECURITY DEFINER: as execuções são de OUTRAS organizações (beneficiárias), invisíveis ao patrocinador pela RLS;
-- só a soma sai, nunca o conteúdo. Opcionalmente restrita a uma organização ou a um projeto (limites).
CREATE OR REPLACE FUNCTION ai_sponsorship_used(p_id uuid, p_org uuid DEFAULT NULL, p_project uuid DEFAULT NULL) RETURNS bigint
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT coalesce(sum(CASE WHEN state IN ('succeeded','reconciled') THEN charged_credits
                           WHEN state IN ('reserved','running') THEN reserved_credits ELSE 0 END), 0)::bigint
    FROM ai_executions WHERE sponsorship_id = p_id
      AND (p_org IS NULL OR org_id = p_org) AND (p_project IS NULL OR project_id = p_project)
$$;
REVOKE ALL ON FUNCTION ai_sponsorship_used(uuid, uuid, uuid) FROM PUBLIC;

-- prestação de contas AGREGADA ao patrocinador: por operação e por organização beneficiada (nome e contagens)
CREATE OR REPLACE FUNCTION ai_sponsorship_report(p_id uuid)
RETURNS TABLE(group_kind text, label text, executions bigint, credits bigint, not_charged bigint)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM ai_sponsorships s WHERE s.id = p_id AND (s.sponsor_org_id = app_org() OR app_priv())) THEN
    RAISE EXCEPTION 'prestação de contas só ao patrocinador' USING ERRCODE = '42501';
  END IF;
  RETURN QUERY
    SELECT 'operation'::text, e.operation_code, count(*)::bigint, coalesce(sum(e.charged_credits),0)::bigint,
           count(*) FILTER (WHERE e.state IN ('failed','partial','cancelled'))::bigint
      FROM ai_executions e WHERE e.sponsorship_id = p_id GROUP BY e.operation_code
    UNION ALL
    SELECT 'organization'::text, o.legal_name, count(*)::bigint, coalesce(sum(e.charged_credits),0)::bigint,
           count(*) FILTER (WHERE e.state IN ('failed','partial','cancelled'))::bigint
      FROM ai_executions e JOIN organizations o ON o.id = e.org_id WHERE e.sponsorship_id = p_id GROUP BY o.legal_name;
END $$;
REVOKE ALL ON FUNCTION ai_sponsorship_report(uuid) FROM PUBLIC;

-- ============================================================================ 6. pacotes e pedidos de crédito (PIX)
CREATE TABLE ai_credit_packs (
  id            bigserial PRIMARY KEY,
  code          text NOT NULL CHECK (code ~ '^[a-z][a-z0-9_.]{2,40}$'),
  version       int NOT NULL CHECK (version >= 1),
  name_pt       text NOT NULL,
  credits       int NOT NULL CHECK (credits > 0),
  price_cents   bigint NOT NULL CHECK (price_cents > 0),
  currency      char(3) NOT NULL DEFAULT 'BRL',
  validity_days int NOT NULL DEFAULT 365 CHECK (validity_days > 0),
  status        text NOT NULL DEFAULT 'hypothesis' CHECK (status IN ('active','hypothesis','retired')),
  note          text NOT NULL CHECK (length(note) >= 20),
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (code, version)
);
CREATE UNIQUE INDEX ux_ai_credit_packs_current ON ai_credit_packs (code) WHERE status IN ('active','hypothesis');
CREATE TRIGGER trg_ai_packs_guard BEFORE UPDATE OR DELETE ON ai_credit_packs FOR EACH ROW EXECUTE FUNCTION ai_catalog_guard();

CREATE TABLE ai_credit_orders (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id         uuid NOT NULL REFERENCES organizations(id),
  user_id        uuid REFERENCES users(id) ON DELETE SET NULL,
  pack_id        bigint NOT NULL REFERENCES ai_credit_packs(id),
  credits        int NOT NULL CHECK (credits > 0),
  amount_cents   bigint NOT NULL CHECK (amount_cents > 0),
  currency       char(3) NOT NULL DEFAULT 'BRL',
  mode           text NOT NULL CHECK (mode IN ('pilot','real')),
  state          text NOT NULL DEFAULT 'created' CHECK (state IN ('created','awaiting_payment','paid','credited','expired','cancelled','failed')),
  charge_id      uuid REFERENCES platform_charges(id) ON DELETE SET NULL,
  consent_at     timestamptz NOT NULL DEFAULT now(),
  consent_text_sha256 char(64),
  paid_reference text,
  confirmed_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  confirmed_via  text CHECK (confirmed_via IS NULL OR confirmed_via IN ('webhook','manual_reconciliation','pilot_grant')),
  ledger_id      bigint REFERENCES ai_credit_ledger(id),
  expires_at     timestamptz NOT NULL DEFAULT now() + interval '2 days',
  note           text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_ai_credit_orders_org ON ai_credit_orders (org_id, created_at DESC);
COMMENT ON TABLE ai_credit_orders IS
  'Pedido de crédito. mode=real: cobrança própria (PIX) confirmada por webhook assinado ou conciliação manual com '
  'referência — só então nasce crédito COMPRADO. mode=pilot (regra comercial inativa ou provedor ausente): nenhum '
  'pagamento; a administração pode aprovar como concessão de piloto (crédito PROMOCIONAL), nunca como compra.';

CREATE TABLE ai_credit_order_state_graph (from_state text NOT NULL, to_state text NOT NULL, PRIMARY KEY (from_state, to_state));
INSERT INTO ai_credit_order_state_graph VALUES
  ('created','awaiting_payment'), ('created','cancelled'), ('created','credited'),
  ('awaiting_payment','paid'), ('awaiting_payment','expired'), ('awaiting_payment','cancelled'), ('awaiting_payment','failed'),
  ('paid','credited'), ('paid','failed');

CREATE OR REPLACE FUNCTION ai_credit_order_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.state <> OLD.state AND NOT EXISTS (SELECT 1 FROM ai_credit_order_state_graph WHERE from_state = OLD.state AND to_state = NEW.state) THEN
    RAISE EXCEPTION 'pedido de crédito: transição % → % não existe', OLD.state, NEW.state USING ERRCODE = '23514';
  END IF;
  IF NEW.credits <> OLD.credits OR NEW.amount_cents <> OLD.amount_cents OR NEW.org_id <> OLD.org_id OR NEW.mode <> OLD.mode THEN
    RAISE EXCEPTION 'pedido de crédito: quantidade, valor, organização e modo são imutáveis' USING ERRCODE = '23514';
  END IF;
  IF NEW.state = 'credited' AND NEW.ledger_id IS NULL THEN
    RAISE EXCEPTION 'pedido de crédito: credited exige o lançamento no razão' USING ERRCODE = '23514';
  END IF;
  IF NEW.state = 'credited' AND NEW.mode = 'real' AND NEW.confirmed_via NOT IN ('webhook','manual_reconciliation') THEN
    RAISE EXCEPTION 'pedido real só credita por webhook assinado ou conciliação manual com referência' USING ERRCODE = '42501';
  END IF;
  IF NEW.state = 'credited' AND NEW.mode = 'real' AND coalesce(NEW.paid_reference, '') = '' THEN
    RAISE EXCEPTION 'pedido real: creditar exige a referência do pagamento' USING ERRCODE = '23514';
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_ai_credit_order_guard BEFORE UPDATE ON ai_credit_orders FOR EACH ROW EXECUTE FUNCTION ai_credit_order_guard();

-- cobrança própria de crédito: tipo novo e autorização = o próprio pedido com consentimento registrado
ALTER TABLE platform_charges DROP CONSTRAINT IF EXISTS platform_charges_kind_check;
ALTER TABLE platform_charges ADD CONSTRAINT platform_charges_kind_check
  CHECK (kind IN ('one_off','installment_plan','operation','ai_credits')) NOT VALID;

CREATE OR REPLACE FUNCTION charge_requires_authorization() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF charge_is_simulated(NEW.provider) THEN RETURN NEW; END IF;
  IF NEW.amount_cents IS NULL OR NEW.amount_cents = 0 THEN RETURN NEW; END IF;
  IF EXISTS (SELECT 1 FROM offer_acceptances
              WHERE org_id = NEW.org_id AND consent_status = 'authorized' AND revoked_at IS NULL) THEN
    RETURN NEW;
  END IF;
  IF NEW.kind = 'operation' AND EXISTS (
       SELECT 1 FROM signed_agreement_parties p JOIN signed_agreements s ON s.id = p.agreement_id
        WHERE p.org_id = NEW.org_id AND p.role = 'funder' AND p.signed_at IS NOT NULL
          AND s.kind = 'funding' AND coalesce(s.platform_fee_bps, 0) > 0) THEN
    RETURN NEW;
  END IF;
  -- v0.28.0: pedido de crédito de IA com consentimento registrado É a autorização (ADR-349), mas só se a
  -- regra comercial de crédito pré-pago estiver ativa — sem carta verde não existe venda real.
  IF NEW.kind = 'ai_credits' AND NEW.idempotency_key LIKE 'ai_credit_order:%' AND EXISTS (
       SELECT 1 FROM ai_credit_orders o
        WHERE o.id::text = substr(NEW.idempotency_key, 17) AND o.org_id = NEW.org_id AND o.mode = 'real'
          AND o.amount_cents = NEW.amount_cents AND o.consent_at IS NOT NULL)
     AND EXISTS (SELECT 1 FROM monetization_rules WHERE key = 'ai.credits_prepaid' AND active) THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'cobrança sem autorização vigente: nem contrato comercial aceito, nem acordo de financiamento assinado pelo pagador, nem pedido de crédito consentido com regra ativa'
    USING ERRCODE = '42501',
          HINT = 'registre um aceite com consent_status = authorized, um acordo de financiamento assinado com taxa de serviço, ou um pedido de crédito real com a regra ai.credits_prepaid ativa';
  RETURN NEW;
END $$;

-- ============================================================================ 7. regra de monetização: crédito pré-pago de IA
INSERT INTO monetization_rules(
    key, label_pt, revenue_engine, engine_rank, payer_kind, trigger_kind, value_event_type,
    pricing_mode, currency, hypothesis_min_cents, hypothesis_max_cents, hypothesis_note,
    problem_solved, substitution_answer)
VALUES ('ai.credits_prepaid', 'Créditos pré-pagos de operações de inteligência (IA)', 'proponent_premium', 7,
        'osc', 'value_event', 'ai.analysis_completed', 'unit', 'BRL', 490, 3990,
        'HIPÓTESE comercial do proprietário para TESTE, não preço de produção: diagnóstico inicial R$ 4,90–9,90; '
        'diagnóstico avançado R$ 14,90–29,90; comparação de dois projetos R$ 4,90–9,90; comparação aprofundada '
        'R$ 14,90–39,90; lote e relatório institucional por orçamento. Preço real só depois de medir custo e margem '
        '(AI_COST_MODEL.md). Crédito vendido é OBRIGAÇÃO com o cliente até ser consumido, não receita.',
        'Quem precisa estruturar, diagnosticar, comparar e provar um projeto não tem equipe para isso; paga só pela '
        'operação de inteligência que executa, sem mensalidade, e pode ser custeado por um patrocinador.',
        'ChatGPT genérico não conhece o projeto, o edital, o território, as evidências nem a versão do documento; não '
        'registra custo por operação, não respeita faixa de risco, não deixa trilha e não pode ser patrocinado por um '
        'financiador para uma OSC elegível.');
WITH c AS (
  INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature,
      contractual_relation, required_document, required_terms, cancellation_policy, refund_policy, tax_notes,
      invoice_notes, regulatory_notes, legal_basis, source_name, source_url, verified_on, open_questions, note)
  VALUES ('ai.credits_prepaid', 'yellow', 'medium',
    'Organização (OSC, empresa, governo, profissional) ou patrocinador que compra créditos de uso',
    'A plataforma (pessoa jurídica titular do software)',
    'Pagamento confirmado de um pedido de créditos (PIX); a receita é RECONHECIDA só quando o crédito é consumido por operação concluída',
    'Receita de prestação de serviço de software sob demanda (processamento de inteligência), com adiantamento do cliente (crédito não consumido = passivo)',
    'Termos de Uso com a modalidade de créditos pré-pagos; pedido com consentimento versionado, IP e data',
    'Termos aceitos no pedido; nota fiscal de serviço por consumo (ou por compra, a definir com o contador)',
    'Termos de Uso, Política de Créditos (validade, expiração, falha = não cobra), Política de Privacidade',
    'Crédito não consumido dentro da validade: regra de devolução a definir (CDC pode se aplicar a pessoa física e a OSC em certas condições)',
    'A definir com o jurídico: devolução de crédito não usado, expiração, falha após consumo de tokens (hoje: falha NÃO cobra)',
    'ISS sobre serviço (LC 116/2003); momento do fato gerador (compra × consumo) a confirmar com o contador; não é custódia (o crédito não é resgatável em dinheiro)',
    'NFS-e obrigatória e NÃO implementada',
    'Crédito de uso NÃO é moeda eletrônica nem saldo resgatável: não há saque, transferência entre clientes ou conversão em dinheiro — desenho para ficar fora da Lei 12.865/2013; parecer pendente',
    'LC 116/2003; CDC (Lei 8.078/1990) para expiração e devolução; Lei 12.865/2013 (a confirmar não aplicação)',
    'Planalto — LC 116/2003, Lei 8.078/1990, Lei 12.865/2013', 'https://www.planalto.gov.br/ccivil_03/leis/lcp/lcp116.htm', '2026-10-08',
    'Reconhecimento da receita (compra × consumo); expiração e devolução sob CDC; NFS-e; não enquadramento como arranjo de pagamento; preço após medição de custo',
    'Modalidade desenhada para cobrar por operação executada, nunca por acesso, e para que um terceiro possa custear o uso de quem não pode pagar. Fica AMARELA até parecer; até lá os pedidos correm em modo PILOTO (sem pagamento).')
  RETURNING id, rule_key
)
UPDATE monetization_rules r SET legal_card_id = c.id, legal_status = 'review_required' FROM c WHERE r.key = c.rule_key;

-- ============================================================================ 7b. lançamento de crédito com portão
-- LANÇAMENTO COM PORTÃO. A RLS do razão só aceita INSERT em contexto de sistema (0058). A aplicação, em
-- contexto de organização, lança por esta função SECURITY DEFINER, que decide O QUE a organização pode
-- lançar: consumo da própria execução, compromisso e devolução de patrocínio próprio, concessão de cota
-- configurada (valor da política, uma vez). Compra, estorno e ajuste exigem privilégio ou sistema.
CREATE OR REPLACE FUNCTION ai_credit_post(
  p_org uuid, p_delta int, p_reason text, p_bucket text, p_ref_type text, p_ref_id text,
  p_idempotency text, p_note text, p_execution uuid, p_expires timestamptz)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE v_id bigint; v_pol ai_quota_policies; v_commit bigint; v_released bigint;
BEGIN
  IF NOT (app_priv() OR app_system()) THEN
    IF p_org IS DISTINCT FROM app_org() THEN
      RAISE EXCEPTION 'razão de crédito: organização não é a da sessão' USING ERRCODE = '42501';
    END IF;
    IF p_reason = 'consumption' THEN
      IF p_execution IS NULL OR NOT EXISTS (SELECT 1 FROM ai_executions e WHERE e.id = p_execution AND e.org_id = p_org) THEN
        RAISE EXCEPTION 'consumo exige execução da própria organização' USING ERRCODE = '42501';
      END IF;
    ELSIF p_reason = 'sponsor_commit' THEN
      IF p_ref_type <> 'ai_sponsorship' OR NOT EXISTS (SELECT 1 FROM ai_sponsorships s WHERE s.id::text = p_ref_id AND s.sponsor_org_id = p_org) THEN
        RAISE EXCEPTION 'compromisso de patrocínio exige patrocínio da própria organização' USING ERRCODE = '42501';
      END IF;
    ELSIF p_reason = 'release' THEN
      IF p_ref_type <> 'ai_sponsorship' OR NOT EXISTS (SELECT 1 FROM ai_sponsorships s WHERE s.id::text = p_ref_id AND s.sponsor_org_id = p_org AND s.status = 'closed') THEN
        RAISE EXCEPTION 'devolução exige patrocínio próprio encerrado' USING ERRCODE = '42501';
      END IF;
      SELECT coalesce(-sum(delta),0) INTO v_commit FROM ai_credit_ledger WHERE org_id = p_org AND reason = 'sponsor_commit' AND ref_id = p_ref_id AND bucket = p_bucket;
      SELECT coalesce(sum(delta),0) INTO v_released FROM ai_credit_ledger WHERE org_id = p_org AND reason = 'release' AND ref_id = p_ref_id AND bucket = p_bucket;
      IF v_released + p_delta > v_commit - (SELECT coalesce(sum(charged_credits),0) FROM ai_executions WHERE sponsorship_id::text = p_ref_id) THEN
        RAISE EXCEPTION 'devolução acima do comprometido e não usado' USING ERRCODE = '23514';
      END IF;
    ELSIF p_reason = 'grant' AND p_ref_type = 'ai_quota_policy' THEN
      SELECT * INTO v_pol FROM ai_quota_policies WHERE id::text = p_ref_id AND active;
      IF v_pol.id IS NULL OR v_pol.credits <> p_delta OR p_bucket <> 'promotional' OR NOT (app_kind() = ANY (v_pol.applies_to_kinds)) THEN
        RAISE EXCEPTION 'concessão de cota fora da política configurada' USING ERRCODE = '42501';
      END IF;
    ELSE
      RAISE EXCEPTION 'lançamento % exige privilégio da administração', p_reason USING ERRCODE = '42501';
    END IF;
  END IF;
  INSERT INTO ai_credit_ledger (org_id, delta, reason, bucket, ref_type, ref_id, idempotency_key, note, created_by, execution_id, expires_at)
  VALUES (p_org, p_delta, p_reason, p_bucket, p_ref_type, p_ref_id, p_idempotency, p_note, app_uid(), p_execution, p_expires)
  ON CONFLICT DO NOTHING RETURNING id INTO v_id;
  RETURN v_id;   -- nulo = já lançado (idempotência)
END $$;
REVOKE ALL ON FUNCTION ai_credit_post(uuid,int,text,text,text,text,text,text,uuid,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ai_credit_post(uuid,int,text,text,text,text,text,text,uuid,timestamptz) TO impacto_app;

-- ============================================================================ 8. similaridade, originalidade, complementaridade
CREATE TABLE similarity_analyses (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid NOT NULL REFERENCES organizations(id),
  execution_id     uuid REFERENCES ai_executions(id) ON DELETE SET NULL,
  kind             text NOT NULL CHECK (kind IN ('single','pair','set','batch','complementarity','expense_overlap')),
  subject_project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  compared_project_ids uuid[] NOT NULL DEFAULT '{}',
  engine_version   text NOT NULL,
  inputs_sha256    char(64) NOT NULL,
  result           jsonb NOT NULL,
  confidence       text NOT NULL CHECK (confidence IN ('low','medium','high')),
  human_review_required boolean NOT NULL DEFAULT true,
  hidden_count     int NOT NULL DEFAULT 0,
  created_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_simil_org ON similarity_analyses (org_id, created_at DESC);
CREATE INDEX ix_simil_cache ON similarity_analyses (org_id, kind, subject_project_id, inputs_sha256, engine_version);
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON similarity_analyses FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
COMMENT ON TABLE similarity_analyses IS
  'Resultado explicável por dimensão (texto, escopo, público, território, tempo, orçamento, financiamento, '
  'indicadores): score, fatores, limitações, confiança, recomendações. Nunca um percentual único como prova; '
  'nunca bloqueia financiamento, reputação ou match. Mesmo insumo + mesma versão do motor = cache (não cobra de novo).';

CREATE TABLE similarity_disputes (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  analysis_id   uuid NOT NULL REFERENCES similarity_analyses(id) ON DELETE CASCADE,
  org_id        uuid NOT NULL REFERENCES organizations(id),
  opened_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  reason        text NOT NULL CHECK (length(reason) BETWEEN 20 AND 4000),
  status        text NOT NULL DEFAULT 'open' CHECK (status IN ('open','reviewed_upheld','reviewed_corrected','withdrawn')),
  reviewer_note text,
  reviewed_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  reviewed_at   timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_simil_disputes ON similarity_disputes (analysis_id);
CREATE TRIGGER trg_simil_dispute_touch BEFORE UPDATE ON similarity_disputes FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Sobreposição agregada com projetos que o solicitante NÃO enxerga (k-anonimato ≥ 3): conta projetos de
-- outras organizações, não publicados, com a mesma causa e o mesmo território. Só a contagem sai.
CREATE OR REPLACE FUNCTION similarity_hidden_overlap(p_project uuid) RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE n int; v_territory text; v_causes text[]; v_org uuid;
BEGIN
  SELECT territory, causes, org_id INTO v_territory, v_causes, v_org FROM projects WHERE id = p_project;
  IF v_territory IS NULL THEN RETURN 0; END IF;
  SELECT count(*) INTO n FROM projects p
   WHERE p.id <> p_project AND p.org_id <> v_org AND p.visibility <> 'published'
     AND p.status NOT IN ('archived')
     AND lower(p.territory) = lower(v_territory) AND p.causes && v_causes;
  RETURN CASE WHEN n >= 3 THEN n ELSE 0 END;
END $$;
REVOKE ALL ON FUNCTION similarity_hidden_overlap(uuid) FROM PUBLIC;

-- ============================================================================ 9. RLS e permissões
ALTER TABLE ai_operations ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_ops_read ON ai_operations FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY ai_ops_insert ON ai_operations FOR INSERT WITH CHECK (app_priv());
CREATE POLICY ai_ops_retire ON ai_operations FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());

ALTER TABLE ai_executions ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_exec_read ON ai_executions FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY ai_exec_insert ON ai_executions FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY ai_exec_update ON ai_executions FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

ALTER TABLE ai_execution_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_exec_ev_read ON ai_execution_events FOR SELECT
  USING (EXISTS (SELECT 1 FROM ai_executions e WHERE e.id = execution_id AND (e.org_id = app_org() OR app_priv())));
CREATE POLICY ai_exec_ev_insert ON ai_execution_events FOR INSERT WITH CHECK (true);   -- escrito só pelo gatilho

ALTER TABLE ai_execution_state_graph ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_exec_graph_read ON ai_execution_state_graph FOR SELECT USING (true);

ALTER TABLE ai_quota_policies ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_quota_pol_read ON ai_quota_policies FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY ai_quota_pol_write ON ai_quota_policies FOR ALL USING (app_priv()) WITH CHECK (app_priv());

ALTER TABLE ai_quota_grants ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_quota_gr_read ON ai_quota_grants FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY ai_quota_gr_insert ON ai_quota_grants FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());

ALTER TABLE ai_sponsorships ENABLE ROW LEVEL SECURITY;
-- patrocinador vê os seus; beneficiário elegível vê os que lhe servem (sem dados de outros beneficiários)
CREATE POLICY ai_sponsor_read ON ai_sponsorships FOR SELECT
  USING (sponsor_org_id = app_org() OR app_priv()
         OR (status = 'active' AND app_kind() = ANY (eligible_kinds)
             AND (cardinality(eligible_org_ids) = 0 OR app_org() = ANY (eligible_org_ids))));
CREATE POLICY ai_sponsor_insert ON ai_sponsorships FOR INSERT WITH CHECK (sponsor_org_id = app_org() OR app_priv());
CREATE POLICY ai_sponsor_update ON ai_sponsorships FOR UPDATE USING (sponsor_org_id = app_org() OR app_priv()) WITH CHECK (sponsor_org_id = app_org() OR app_priv());

ALTER TABLE ai_credit_packs ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_packs_read ON ai_credit_packs FOR SELECT USING (app_authenticated() OR app_priv());
CREATE POLICY ai_packs_insert ON ai_credit_packs FOR INSERT WITH CHECK (app_priv());
CREATE POLICY ai_packs_retire ON ai_credit_packs FOR UPDATE USING (app_priv()) WITH CHECK (app_priv());

ALTER TABLE ai_credit_orders ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_orders_read ON ai_credit_orders FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY ai_orders_insert ON ai_credit_orders FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY ai_orders_update ON ai_credit_orders FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

ALTER TABLE ai_credit_order_state_graph ENABLE ROW LEVEL SECURITY;
CREATE POLICY ai_order_graph_read ON ai_credit_order_state_graph FOR SELECT USING (true);

ALTER TABLE similarity_analyses ENABLE ROW LEVEL SECURITY;
CREATE POLICY simil_read ON similarity_analyses FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY simil_insert ON similarity_analyses FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());

ALTER TABLE similarity_disputes ENABLE ROW LEVEL SECURITY;
CREATE POLICY simil_disp_read ON similarity_disputes FOR SELECT USING (org_id = app_org() OR app_priv());
CREATE POLICY simil_disp_insert ON similarity_disputes FOR INSERT WITH CHECK (org_id = app_org() OR app_priv());
CREATE POLICY simil_disp_update ON similarity_disputes FOR UPDATE USING (org_id = app_org() OR app_priv()) WITH CHECK (org_id = app_org() OR app_priv());

GRANT SELECT, INSERT ON ai_quota_grants, similarity_analyses TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON ai_operations, ai_credit_packs TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON ai_executions, ai_sponsorships, ai_credit_orders, similarity_disputes, ai_quota_policies TO impacto_app;
GRANT SELECT, INSERT ON ai_execution_events TO impacto_app;
GRANT SELECT ON ai_execution_state_graph, ai_credit_order_state_graph TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE ai_operations_id_seq, ai_credit_packs_id_seq, ai_quota_policies_id_seq, ai_quota_grants_id_seq, ai_execution_events_id_seq TO impacto_app;
GRANT EXECUTE ON FUNCTION similarity_hidden_overlap(uuid) TO impacto_app;
GRANT EXECUTE ON FUNCTION ai_sponsorship_used(uuid, uuid, uuid), ai_sponsorship_report(uuid), ai_quota_user_has(bigint, uuid, text) TO impacto_app;

INSERT INTO polymorphic_refs (source_table, type_column, id_column, note) VALUES
  ('ai_credit_ledger','ref_type','ref_id','origem do lançamento de crédito: execução de IA, pedido de crédito, política de cota, patrocínio')
ON CONFLICT DO NOTHING;
INSERT INTO audit_action_categories (prefix, category, note) VALUES
  ('ai','WORKFLOWS','operações de IA: execução, cota, crédito, pedido, patrocínio, similaridade, contestação (v0.28.0)')
ON CONFLICT DO NOTHING;

-- ============================================================================ 10. sementes do catálogo (hipóteses de preço do proprietário)
-- Unidade: 1 crédito ≈ R$ 0,10 na hipótese de pacote abaixo. Preços em créditos nas faixas MÍNIMAS da
-- tabela do proprietário; status 'hypothesis' = executa, mas a interface diz que o preço é de teste.
INSERT INTO ai_operations (code, version, name_pt, description_pt, purpose_pt, category, tier, allowed_kinds, min_role,
  data_requirements_pt, provider_mode, funding_modes, credits_base, credits_per_unit, unit_label_pt, max_units, max_input_chars,
  free_quota_eligible, sponsor_eligible, completion_rule_pt, delivers_pt, status, note) VALUES
  ('assist.summarize_project', 1, 'Resumo do projeto', 'Resumo de leitura rápida a partir dos campos do projeto (título, resumo, problema, objetivos, metodologia). Motor local por padrão; provedor externo quando configurado, com redação de dado pessoal.', 'Leitura rápida para quem avalia', 'A', 1,
   '{osc,company,government,individual,provider}', 'viewer', 'Projeto com título e pelo menos um campo descritivo', 'external_allowed', '{free_quota,sponsorship,credits}', 1, 0, 'execução', 1, 20000,
   true, true, 'Concluída quando o resumo é devolvido (local ou externo validado).', 'Resumo em texto, marcado como rascunho para revisão humana', 'active', 'Categoria A: assistência leve; 1 crédito.'),
  ('assist.structure_need', 1, 'Estruturar necessidade em projeto', 'Transforma uma necessidade descrita livremente em estrutura de projeto: título, causas, ODS, objetivos, itens de orçamento e perguntas abertas. Nunca inventa números.', 'Primeira estruturação assistida', 'B', 1,
   '{osc}', 'member', 'Texto livre de 10 a 20.000 caracteres', 'external_allowed', '{free_quota,sponsorship,credits}', 5, 0, 'execução', 1, 20000,
   true, true, 'Concluída quando a estrutura é devolvida; o rascunho exige revisão humana.', 'Estrutura de projeto em rascunho com [COMPLETAR] onde falta informação', 'hypothesis', 'Categoria B: 5 créditos (hipótese).'),
  ('assist.draft_document', 1, 'Rascunho de documento do projeto', 'Gera rascunho de proposta, plano de trabalho, justificativa de orçamento, carta, relatório de progresso ou final a partir dos dados do projeto.', 'Rascunho para a equipe revisar', 'B', 1,
   '{osc}', 'member', 'Projeto da própria organização; opcionalmente edital e instruções', 'external_allowed', '{free_quota,sponsorship,credits}', 10, 0, 'execução', 1, 20000,
   true, true, 'Concluída quando o rascunho é devolvido (modelo local ou texto externo com mais de 200 caracteres).', 'Documento em rascunho, com marcações [COMPLETAR]', 'hypothesis', 'Categoria B: 10 créditos (hipótese).'),
  ('assist.classify_document', 1, 'Classificar documento enviado', 'Sugere tipo e validade de um documento a partir do texto extraído. Processamento local; nada sai da instalação.', 'Organizar o cofre de documentos', 'A', 0,
   '{osc,company,government,individual,provider}', 'member', 'Documento com texto extraído', 'local', '{free}', 0, 0, 'execução', 1, 20000,
   true, false, 'Concluída quando a sugestão é devolvida.', 'Sugestão de tipo e validade', 'active', 'Determinística e gratuita: não há custo externo.'),
  ('similarity.single', 1, 'Originalidade de um projeto', 'Compara o projeto com o conjunto AUTORIZADO (projetos publicados e os da própria organização) em oito dimensões separadas: texto, escopo, público, território, tempo, orçamento, financiamento e indicadores. Devolve o que o projeto traz de novo, com quem se parece, e o que exige revisão humana.', 'Saber o que a proposta traz de novo', 'D', 3,
   '{osc,company,government,individual,provider}', 'viewer', 'Projeto visível ao solicitante com campos descritivos preenchidos', 'local', '{free_quota,sponsorship,credits}', 49, 0, 'execução', 1, 60000,
   true, true, 'Concluída quando a análise é gravada com dimensões, fatores, limitações e confiança.', 'Análise de originalidade por dimensão, candidatos semelhantes visíveis, contagem agregada dos não visíveis, recomendações', 'hypothesis', 'Categoria D: 49 créditos (hipótese R$ 4,90).'),
  ('similarity.pair', 1, 'Comparar dois projetos', 'Compara dois projetos visíveis ao solicitante, dimensão a dimensão, separando similaridade textual, de escopo, sobreposição territorial e temporal, possível duplicidade de despesa e complementaridade.', 'Entender a relação entre duas propostas', 'D', 3,
   '{osc,company,government,individual,provider}', 'viewer', 'Dois projetos visíveis ao solicitante', 'local', '{free_quota,sponsorship,credits}', 49, 0, 'execução', 1, 120000,
   true, true, 'Concluída quando a comparação é gravada; não há conclusão de plágio ou fraude — só indícios com confiança.', 'Comparação por dimensão, fatores que elevam/reduzem, recomendações, necessidade de revisão humana', 'hypothesis', 'Categoria D: 49 créditos (hipótese R$ 4,90).'),
  ('similarity.set', 1, 'Comparar com conjunto autorizado', 'Compara um projeto com até 20 projetos escolhidos entre os visíveis ao solicitante (candidatura a edital, carteira, território).', 'Diligência de carteira', 'D', 3,
   '{company,government,osc}', 'member', 'Projeto base e lista de projetos visíveis (até 20)', 'local', '{sponsorship,credits}', 99, 10, 'projeto comparado', 20, 400000,
   false, true, 'Concluída quando todas as comparações do conjunto são gravadas; parcial se alguma falhar (não cobra).', 'Tabela de comparação por projeto, complementaridades e sobreposições, ordenadas por dimensão', 'hypothesis', 'Categoria D: 99 + 10 por projeto (hipótese R$ 9,90 + R$ 1,00).'),
  ('similarity.complementarity', 1, 'Complementaridade e parcerias', 'Em vez de concorrentes, sugere consórcio, divisão de território, compartilhamento de infraestrutura e referências metodológicas a partir dos projetos visíveis.', 'Encontrar com quem colaborar', 'D', 3,
   '{osc,company,government}', 'viewer', 'Projeto com causa, território e metodologia', 'local', '{free_quota,sponsorship,credits}', 29, 0, 'execução', 1, 60000,
   true, true, 'Concluída quando a lista de complementaridades é gravada.', 'Sugestões de parceria com o motivo de cada uma', 'hypothesis', 'Categoria D: 29 créditos (hipótese R$ 2,90).'),
  ('similarity.expense_overlap', 1, 'Sobreposição de despesas e financiamento', 'Para financiadores e governos: entre dois projetos, compara itens de orçamento, período e fontes de financiamento e aponta POSSÍVEL duplicidade — nunca presume irregularidade; exige revisão humana.', 'Integridade do financiamento', 'D', 3,
   '{company,government}', 'member', 'Dois projetos visíveis com itens de orçamento', 'local', '{sponsorship,credits}', 149, 0, 'execução', 1, 120000,
   false, true, 'Concluída quando a análise é gravada com indícios, evidências e limitações separados.', 'Indícios de sobreposição de despesa/financiamento com confiança e revisão humana obrigatória', 'hypothesis', 'Categoria D: 149 créditos (hipótese R$ 14,90).'),
  ('similarity.batch', 1, 'Comparação em lote', 'Comparação de carteira inteira (dezenas a centenas de projetos). Declarada no catálogo e NÃO implementada: exige execução assíncrona com fila, orçamento por tarefa e cancelamento — e volume real para medir.', 'Carteira institucional', 'E', 3,
   '{company,government}', 'admin', 'Carteira de projetos autorizada', 'local', '{sponsorship,credits}', 990, 10, 'projeto', 500, 5000000,
   false, true, 'Não implementada: a rota responde 501.', 'Relatório de carteira', 'planned', 'Categoria E: planejada; sem preço válido até medir.'),
  ('similarity.monitoring', 1, 'Monitoramento recorrente de correspondências', 'Avisar quando surgir projeto semelhante ao meu. Declarada e NÃO implementada: exige rotina agendada com orçamento próprio e consentimento de quem é comparado.', 'Acompanhar o ecossistema', 'D', 3,
   '{osc,company,government}', 'member', 'Projeto base', 'local', '{sponsorship,credits}', 19, 0, 'mês', 12, 60000,
   false, true, 'Não implementada: a rota responde 501.', 'Alertas periódicos', 'planned', 'Planejada.'),
  ('report.institutional_portfolio', 1, 'Relatório institucional de carteira', 'Relatório consolidado para financiador, empresa ou governo. Declarada e NÃO implementada: preço por escopo, contrato institucional (categoria F).', 'Prestação de contas institucional', 'F', 3,
   '{company,government}', 'admin', 'Carteira e contrato', 'local', '{credits}', 0, 0, 'relatório', 1, 5000000,
   false, false, 'Não implementada: a rota responde 501; preço por contrato.', 'Relatório institucional', 'planned', 'Categoria F: contrato por escopo.');

INSERT INTO ai_credit_packs (code, version, name_pt, credits, price_cents, validity_days, status, note) VALUES
  ('pack.100', 1, '100 créditos', 100, 1000, 365, 'hypothesis', 'HIPÓTESE de teste: R$ 10,00 por 100 créditos (R$ 0,10/crédito). Não vendável até a regra ai.credits_prepaid ativar.'),
  ('pack.500', 1, '500 créditos', 500, 4500, 365, 'hypothesis', 'HIPÓTESE de teste: R$ 45,00 por 500 créditos (R$ 0,09/crédito).'),
  ('pack.2000', 1, '2.000 créditos', 2000, 16000, 365, 'hypothesis', 'HIPÓTESE de teste: R$ 160,00 por 2.000 créditos (R$ 0,08/crédito).');

INSERT INTO ai_quota_policies (key, label_pt, scope, applies_to_kinds, credits, period, validity_days, max_grants_per_org, one_per_user, note) VALUES
  ('welcome.v1', 'Cota de boas-vindas', 'welcome', '{osc,company,government,individual,provider}', 60, 'once', 90, 1, true,
   'Uma vez por organização e uma vez por pessoa (anti-abuso: criar outra organização não renova). 60 créditos = ~1 originalidade + resumos. Custo da gratuidade é orçado em AI_COST_MODEL.md.'),
  ('monthly.light.v1', 'Assistência leve mensal', 'periodic', '{osc,individual}', 10, 'month', 31, 1, false,
   'Cota mensal pequena para OSC e profissional, renovada a cada mês civil. Vale só para operações marcadas free_quota_eligible.');
