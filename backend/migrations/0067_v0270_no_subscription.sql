-- 0067 — v0.27.0 — NÃO EXISTEM MAIS ASSINATURAS (ADR-341).
--
-- Decisão do proprietário: o IMPACTO deixa de ser um SaaS por assinatura e passa a ser infraestrutura de
-- inteligência e operação de impacto monetizada pelo valor econômico que cria (camada econômica da
-- operação financiada — migração 0066). Esta migração aplica o INVENTÁRIO da v0.27.0, classificado
-- ocorrência a ocorrência (docs/execution/SUBSCRIPTION_INVENTORY.md):
--
--   DELETE   — estruturas que só existiam para cobrar mensalidade: assinatura, preço de plano com vigência,
--              aviso de reajuste, trial de 14 dias, pedidos de trial e anti-abuso do trial.
--   MIGRATE  — plano vira PACOTE DE CAPACIDADES (sem preço, sem intervalo); `org_commercial_state` deixa de
--              responder "pagou?" e passa a responder "de onde vem o acesso?"; a oferta comercial vira
--              CONTRATO (avulso ou parcelado, nunca recorrente); a autorização de cobrança passa a nascer
--              também do acordo de financiamento assinado pelo financiador.
--   KEEP     — concessões (entitlement_grants), vouchers de concessão, convênios, períodos de concessão,
--              cobranças próprias da plataforma (platform_charges) e o livro de eventos de cobrança.
--   DEPRECATE— vouchers de desconto (percent_off/amount_off) e desconto percentual de convênio: sem preço
--              de assinatura não há sobre o que descontar. As linhas históricas ficam; nada novo é criado.
--
-- Nada aqui apaga dado histórico de cobrança (invoices, platform_charges, billing_events): o que foi
-- faturado continua provado. O que deixa de existir é a MÁQUINA de assinatura, não o registro do passado.

-- ============================================================================ 0. ARQUIVO do que será removido (nenhuma linha se perde)
-- Antes de qualquer DROP, toda linha das tabelas de assinatura e todo valor não nulo das colunas removidas é copiado
-- para `legacy_subscription_archive` (append-only, só leitura privilegiada). É o que permite responder "esta
-- organização chegou a ter assinatura/trial?" depois da remoção — e é a prova, exigida pelo portão de dados, de que a
-- migração não destrói dado em silêncio. `trial_claims` guarda só HMAC de e-mail/CNPJ (antifraude do trial, retenção
-- de 24 meses): sem trial não há o que proteger, e arquivar o hash seria reter dado pessoal sem finalidade — não entra.
CREATE TABLE legacy_subscription_archive (
  id          bigserial PRIMARY KEY,
  source      text NOT NULL,                  -- tabela ou tabela.coluna de origem
  source_id   text,                           -- id da linha de origem, quando havia
  row         jsonb NOT NULL,
  archived_at timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE legacy_subscription_archive IS
  'v0.27.0 (ADR-341): cópia integral do que a retirada da assinatura removeu do esquema. Só leitura; nunca alimenta tela, direito ou cobrança.';
CREATE TRIGGER trg_append_only BEFORE UPDATE OR DELETE ON legacy_subscription_archive FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
ALTER TABLE legacy_subscription_archive ENABLE ROW LEVEL SECURITY;
CREATE POLICY legacy_archive_priv ON legacy_subscription_archive FOR ALL USING (app_priv()) WITH CHECK (app_priv());
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['subscriptions','subscription_prices','price_change_notices','org_trials','trial_requests','plan_prices','plan_price_versions'] LOOP
    EXECUTE format('INSERT INTO legacy_subscription_archive(source, source_id, row) SELECT %L, (to_jsonb(x)->>''id''), to_jsonb(x) FROM %I x', t, t);
  END LOOP;
  INSERT INTO legacy_subscription_archive(source, source_id, row)
    SELECT 'invoices.subscription_id', id::text, jsonb_build_object('subscription_id', subscription_id) FROM invoices WHERE subscription_id IS NOT NULL;
  INSERT INTO legacy_subscription_archive(source, source_id, row)
    SELECT 'platform_charges.subscription_id', id::text, jsonb_build_object('subscription_id', subscription_id) FROM platform_charges WHERE subscription_id IS NOT NULL;
  INSERT INTO legacy_subscription_archive(source, source_id, row)
    SELECT 'free_periods.subscription_id', id::text, jsonb_build_object('subscription_id', subscription_id) FROM free_periods WHERE subscription_id IS NOT NULL;
  INSERT INTO legacy_subscription_archive(source, source_id, row)
    SELECT 'voucher_redemptions.consumed_by_subscription', id::text, jsonb_build_object('consumed_by_subscription', consumed_by_subscription) FROM voucher_redemptions WHERE consumed_by_subscription IS NOT NULL;
  INSERT INTO legacy_subscription_archive(source, source_id, row)
    SELECT 'commercial_offers.price_version_id+interval', id::text, jsonb_build_object('price_version_id', price_version_id, 'interval', interval) FROM commercial_offers WHERE price_version_id IS NOT NULL OR interval IS NOT NULL;
  INSERT INTO legacy_subscription_archive(source, source_id, row)
    SELECT 'offer_acceptances.price_version_id', id::text, jsonb_build_object('price_version_id', price_version_id) FROM offer_acceptances WHERE price_version_id IS NOT NULL;
  INSERT INTO legacy_subscription_archive(source, source_id, row)
    SELECT 'plans.price_cents+interval', plan_key, jsonb_build_object('price_cents', price_cents, 'interval', interval) FROM plans;
END $$;

-- ============================================================================ 1. colunas dependentes (DELETE)
ALTER TABLE invoices DROP COLUMN IF EXISTS subscription_id;
ALTER TABLE platform_charges DROP COLUMN IF EXISTS subscription_id;
ALTER TABLE free_periods DROP COLUMN IF EXISTS subscription_id;
ALTER TABLE voucher_redemptions DROP COLUMN IF EXISTS consumed_by_subscription;
ALTER TABLE commercial_offers DROP COLUMN IF EXISTS price_version_id;
ALTER TABLE offer_acceptances DROP COLUMN IF EXISTS price_version_id;

-- ============================================================================ 2. tabelas de assinatura (DELETE)
DROP TABLE IF EXISTS price_change_notices;
DROP TABLE IF EXISTS subscription_prices;
DROP TABLE IF EXISTS subscriptions;
DROP TABLE IF EXISTS trial_requests;
DROP TABLE IF EXISTS trial_claims;
DROP TABLE IF EXISTS org_trials;
DROP TABLE IF EXISTS plan_prices;
DROP FUNCTION IF EXISTS price_current(text, text, text);     -- devolve o tipo da tabela: cai antes dela
DROP TABLE IF EXISTS plan_price_versions;
DROP FUNCTION IF EXISTS price_apply_guard();
DROP FUNCTION IF EXISTS price_notice_guard();
DROP FUNCTION IF EXISTS price_notice_ack_only();
DROP FUNCTION IF EXISTS price_version_immutable();

-- ============================================================================ 3. plano = pacote de capacidades (MIGRATE)
-- Um plano continua existindo porque concessão, voucher e convênio apontam para ele: é o NOME de um
-- conjunto de capacidades (limites e recursos). O que ele deixa de ter é preço e periodicidade.
ALTER TABLE plans DROP COLUMN IF EXISTS price_cents;
ALTER TABLE plans DROP COLUMN IF EXISTS interval;
COMMENT ON TABLE plans IS 'v0.27.0: pacote de capacidades (limites e recursos) concedido por tipo de organização, concessão, voucher, convênio ou contrato. Sem preço e sem periodicidade: não há assinatura (ADR-341).';

-- ============================================================================ 4. cobranças, vouchers, períodos, ofertas (MIGRATE)
-- Restrições NOT VALID: linhas históricas ficam como estão (os livros são imutáveis); nenhuma linha nova
-- pode nascer com o valor aposentado.
ALTER TABLE platform_charges DROP CONSTRAINT IF EXISTS platform_charges_kind_check;
ALTER TABLE platform_charges ADD CONSTRAINT platform_charges_kind_check
  CHECK (kind IN ('one_off','installment_plan','operation')) NOT VALID;

ALTER TABLE voucher_redemptions DROP CONSTRAINT IF EXISTS voucher_redemptions_status_check;
ALTER TABLE voucher_redemptions ADD CONSTRAINT voucher_redemptions_status_check
  CHECK (status IN ('applied','consumed')) NOT VALID;

ALTER TABLE free_periods DROP CONSTRAINT IF EXISTS free_periods_source_check;
ALTER TABLE free_periods ADD CONSTRAINT free_periods_source_check
  CHECK (source IN ('2026_CAMPAIGN','PROMOTION','GRANT','PARTNERSHIP','MANUAL_EXCEPTION')) NOT VALID;

ALTER TABLE commercial_offers DROP CONSTRAINT IF EXISTS commercial_offers_billing_frequency_check;
ALTER TABLE commercial_offers ADD CONSTRAINT commercial_offers_billing_frequency_check
  CHECK (billing_frequency IN ('one_time','installment')) NOT VALID;
ALTER TABLE offer_acceptances DROP CONSTRAINT IF EXISTS offer_acceptances_billing_frequency_check;
ALTER TABLE offer_acceptances ADD CONSTRAINT offer_acceptances_billing_frequency_check
  CHECK (billing_frequency IN ('one_time','installment')) NOT VALID;
ALTER TABLE commercial_offers DROP CONSTRAINT IF EXISTS offer_interval_pair;
ALTER TABLE commercial_offers DROP COLUMN IF EXISTS interval;
-- O valor de um contrato é decidido por quem tem alçada financeira, com motivo e auditoria — não vem de
-- um catálogo de preços de assinatura (que não existe mais) nem do cliente.
ALTER TABLE commercial_offers ADD COLUMN IF NOT EXISTS amount_reason text CHECK (length(amount_reason) BETWEEN 5 AND 500);
ALTER TABLE commercial_offers ADD COLUMN IF NOT EXISTS contract_ref text CHECK (length(contract_ref) <= 200);

-- O contrato aceito com autorização de cobrança CONCEDE o pacote (origem 'contract'); revogar a autorização
-- revoga a concessão. É a única forma de um pacote pago existir sem assinatura.
ALTER TABLE entitlement_grants DROP CONSTRAINT IF EXISTS entitlement_grants_source_check;
ALTER TABLE entitlement_grants ADD CONSTRAINT entitlement_grants_source_check
  CHECK (source IN ('voucher','admin','license','partner','convention','gov','promotion','contract'));

-- Os guardas de imutabilidade comparavam as colunas retiradas; recriados sem elas (mesma regra, menos colunas).
CREATE OR REPLACE FUNCTION acceptance_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.offer_id, NEW.org_id, NEW.pricing_version, NEW.plan_key,
      NEW.free_period_id, NEW.billing_frequency, NEW.payment_method, NEW.terms_version,
      NEW.privacy_version, NEW.commercial_terms_version, NEW.accepted_at, NEW.accepted_by,
      NEW.ip, NEW.user_agent, NEW.consent_status, NEW.created_at)
     IS DISTINCT FROM
     (OLD.offer_id, OLD.org_id, OLD.pricing_version, OLD.plan_key,
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
CREATE OR REPLACE FUNCTION free_period_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.org_id, NEW.source, NEW.pricing_version, NEW.started_at,
      NEW.ends_at, NEW.months, NEW.granted_by, NEW.created_at)
     IS DISTINCT FROM
     (OLD.org_id, OLD.source, OLD.pricing_version, OLD.started_at,
      OLD.ends_at, OLD.months, OLD.granted_by, OLD.created_at) THEN
    RAISE EXCEPTION 'período de concessão não se altera: cancele com motivo e conceda outro'
      USING ERRCODE = '42501';
  END IF;
  IF OLD.status IN ('cancelled','superseded') AND NEW.status <> OLD.status THEN
    RAISE EXCEPTION 'período de concessão % não volta a valer', OLD.status USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;

-- ============================================================================ 5. estado comercial v2 (MIGRATE)
-- Antes: FREE / FREE_EXPIRING / PAYMENT_METHOD_REQUIRED / PAID_ACTIVE / PAST_DUE / CANCELLED…
-- Agora a pergunta é "de onde vem o acesso desta organização?":
--   FREE_ACCESS    — acesso ao núcleo, gratuito por desenho (não por prazo);
--   FREE_GRANT     — há concessão temporal vigente (campanha, promoção, parceria, exceção);
--   GRANT_EXPIRING — a concessão vigente termina em 30 dias ou menos (aviso, nunca cobrança);
--   CONTRACTED     — há contrato comercial aceito (avulso/parcelado) com autorização de cobrança vigente.
CREATE OR REPLACE FUNCTION org_commercial_state(p_org uuid) RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE
  v_free timestamptz;
  v_auth boolean;
BEGIN
  SELECT EXISTS (SELECT 1 FROM offer_acceptances
                  WHERE org_id = p_org AND consent_status = 'authorized' AND revoked_at IS NULL) INTO v_auth;
  IF v_auth THEN RETURN 'CONTRACTED'; END IF;
  v_free := free_period_end(p_org);
  IF v_free IS NOT NULL THEN
    IF v_free <= now() + interval '30 days' THEN RETURN 'GRANT_EXPIRING'; END IF;
    RETURN 'FREE_GRANT';
  END IF;
  RETURN 'FREE_ACCESS';
END $$;

-- ============================================================================ 6. autorização de cobrança v2 (MIGRATE)
-- Uma cobrança real da plataforma precisa de autorização de quem paga. Antes só havia uma origem: o aceite
-- de oferta comercial. Agora há duas — e a segunda é a principal: o FINANCIADOR que assinou um acordo de
-- financiamento com taxa de serviço autorizou aquela cobrança no próprio contrato (0066 §2).
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
  RAISE EXCEPTION 'cobrança sem autorização vigente: nem contrato comercial aceito nem acordo de financiamento assinado pelo pagador'
    USING ERRCODE = '42501',
          HINT = 'registre um aceite com consent_status = authorized ou um acordo de financiamento assinado com taxa de serviço';
  RETURN NEW;
END $$;

-- ============================================================================ 7. regra de monetização por assinatura (DEPRECATE → refused)
-- `saas.institutional.funder` nasceu na v0.17.0 como "SaaS institucional para quem financia" cobrado por
-- assinatura. O proprietário decidiu que não existe mais assinatura; a regra fica no catálogo como
-- RECUSADA, com carta vermelha explicando por quê — apagar a linha apagaria a prova de que a hipótese
-- existiu e foi descartada.
ALTER TABLE monetization_rules DROP CONSTRAINT IF EXISTS monetization_rules_trigger_kind_check;
ALTER TABLE monetization_rules DROP CONSTRAINT IF EXISTS monetization_rules_pricing_mode_check;
UPDATE monetization_rules SET trigger_kind = 'contract', pricing_mode = 'contract', active = false,
       hypothesis_note = coalesce(hypothesis_note, '') || ' | v0.27.0: hipótese de assinatura RECUSADA pelo proprietário (ADR-341) — não existe mais assinatura no IMPACTO.'
 WHERE key = 'saas.institutional.funder';
ALTER TABLE monetization_rules ADD CONSTRAINT monetization_rules_trigger_kind_check
  CHECK (trigger_kind IN ('value_event','contract','transaction'));
ALTER TABLE monetization_rules ADD CONSTRAINT monetization_rules_pricing_mode_check
  CHECK (pricing_mode IN ('unit','percentage','contract'));
WITH c AS (
  INSERT INTO monetization_legal_cards(rule_key, status, certainty, payer, beneficiary, billing_event, revenue_nature,
      contractual_relation, required_document, required_terms, cancellation_policy, refund_policy, tax_notes,
      invoice_notes, regulatory_notes, legal_basis, source_name, source_url, verified_on, open_questions, note)
  VALUES ('saas.institutional.funder', 'red', 'high',
    'Ninguém — a modalidade foi descartada',
    'Ninguém — a modalidade foi descartada',
    'Nenhum: não há cobrança recorrente de acesso',
    'Não se aplica: a plataforma não vende acesso por mensalidade',
    'Não se aplica',
    'Não se aplica',
    'Não se aplica',
    'Não se aplica',
    'Não se aplica',
    'Não se aplica',
    'Não se aplica',
    'Decisão de produto do proprietário (v0.27.0, ADR-341): o acesso ao núcleo é gratuito por desenho; a receita vem da camada econômica da operação financiada (3,5% de taxa de serviço contratada — regra contract.platform_service_fee) e de contratos avulsos/parcelados, nunca de assinatura.',
    'ADR-341; PRICING_BIBLE.md (superada no ponto da assinatura); MONETIZATION.md §8',
    'Decisão do proprietário registrada em DECISIONS.md', NULL, '2026-10-08',
    'Nenhuma: a modalidade está encerrada.',
    'Carta VERMELHA por decisão comercial, não por impedimento jurídico: a assinatura foi retirada do modelo econômico.')
  RETURNING id, rule_key
)
UPDATE monetization_rules r SET legal_card_id = c.id, legal_status = 'refused' FROM c WHERE r.key = c.rule_key;

-- ============================================================================ 8. PRICING VERSION 2027.02 (MIGRATE)
-- A versão de preço muda porque o MODELO mudou (sem assinatura), não porque os percentuais mudaram: 3,5% + 1,5%
-- continuam. A 2027.01 FICA no catálogo (os acordos que a congelaram continuam a apontar para ela; o catálogo é
-- imutável) e a 2027.02 nasce com os mesmos percentuais, para que todo acordo novo registre a versão em que a
-- assinatura já não existia. Quem escolhe a versão é `config/plans.json` (pricing_version), lido em um lugar só.
INSERT INTO economic_rules(key, pricing_version, label_pt, applies_to, bps, payer_role, recipient_kind, monetization_rule_key,
                           effective_from, what_it_pays_for, reason)
SELECT key, '2027.02', label_pt, applies_to, bps, payer_role, recipient_kind, monetization_rule_key, CURRENT_DATE,
       what_it_pays_for,
       reason || ' | 2027.02 (v0.27.0, ADR-341): mesmo percentual; a versão muda porque a assinatura saiu do modelo econômico.'
  FROM economic_rules WHERE pricing_version = '2027.01';

-- ============================================================================ 9. plano de contas (MIGRATE)
-- As contas 4.1/4.1.1/2.2.1 descreviam receita recorrente de assinatura. A receita 4.1 passa a ser a da
-- CAMADA ECONÔMICA da operação (taxa de serviço contratada, 3,5%); o diferimento 2.2.1 passa a ser a taxa
-- instruída e ainda não quitada. Os códigos ficam (lançamentos históricos apontam para eles).
UPDATE chart_of_accounts SET name = 'Receita da camada econômica da operação' WHERE code = '4.1';
UPDATE chart_of_accounts SET name = 'Taxa de serviço de operação financiada (3,5%)' WHERE code = '4.1.1';
UPDATE chart_of_accounts SET name = 'Taxa de operação instruída e não quitada' WHERE code = '2.2.1';

-- ============================================================================ 10. Central de Conhecimento (MIGRATE)
UPDATE kb_categories SET name = 'Acesso, concessões e contratos', description = 'De onde vem o acesso, vouchers, convênios e contratos — não existe assinatura'
 WHERE slug = 'assinatura-trial';

-- ============================================================================ 11. catálogo de referências polimórficas (MIGRATE)
-- `recognitions.ref_type/ref_id` aponta para o registro que gerou o reconhecimento (signed_agreement, allocation_payout).
-- Entra no catálogo para que `integrity_catalog_drift()` e a conferência de órfãos o vejam.
INSERT INTO polymorphic_refs (source_table, type_column, id_column, note) VALUES
  ('recognitions','ref_type','ref_id','registro que gerou o reconhecimento: acordo quitado (signed_agreement) ou repasse confirmado (allocation_payout)')
ON CONFLICT DO NOTHING;

-- ============================================================================ 12. categorias de auditoria (MIGRATE)
INSERT INTO audit_action_categories (prefix, category, note) VALUES
  ('participation','FINANCE','participação de autoria: proposta, aceite, cancelamento (camada econômica, v0.27.0)'),
  ('payout','FINANCE','instrução de repasse: transferência registrada, confirmada, recusada, conciliada (v0.27.0)')
ON CONFLICT DO NOTHING;

