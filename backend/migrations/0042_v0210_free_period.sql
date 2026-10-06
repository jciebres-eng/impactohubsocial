-- v0.21.0 — PERÍODO GRATUITO INDIVIDUAL (FULL FREE 2026 e os 3 meses de 2027)
--
-- POR QUE ESTA TABELA EXISTE
--
-- A regra comercial é "tudo gratuito até 31/12/2026, e toda assinatura nova a partir de
-- 01/01/2027 ganha 3 meses". A tentação é escrever as duas datas numa constante e comparar com
-- now(). Isso não sobrevive à primeira pergunta real do suporte: "esta conta aqui está gratuita,
-- até quando, e por quê?" Uma constante não responde — ela só sabe o calendário, não a conta.
--
-- Então a gratuidade é um FATO POR CONTA, com origem, motivo, versão de preço e autor. A data
-- global vira uma CAMPANHA que concede registros individuais; e, no dia em que o proprietário
-- quiser estender dois clientes e não os outros, isso é uma linha a mais, não um `if` no código.
--
-- `ends_at` É EXCLUSIVO: o período é [started_at, ends_at). "Gratuito até 31/12/2026 23:59:59"
-- fica gravado como ends_at = 2027-01-01 00:00:00 em America/Sao_Paulo. Escrever 23:59:59
-- literalmente deixaria um buraco de um segundo (23:59:59.5 não seria nem gratuito nem pago) —
-- um defeito que só aparece uma vez por ano, à meia-noite, que é exatamente quando ninguém está
-- olhando.
--
-- FUSO: o armazenamento continua em UTC, como todo o resto do projeto (529 colunas timestamptz,
-- zero sem fuso). O fuso comercial America/Sao_Paulo é aplicado na FRONTEIRA — ao calcular o fim
-- de uma campanha e ao formatar datas para pessoas. Trocar a convenção interna por causa de uma
-- regra comercial seria pagar em toda consulta do sistema um preço que pertence a esta tabela.

-- ---------------------------------------------------------------------------------------------
-- 1. Fuso comercial e aritmética de meses de calendário
-- ---------------------------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION commercial_tz() RETURNS text
LANGUAGE sql IMMUTABLE AS $$ SELECT 'America/Sao_Paulo'::text $$;

COMMENT ON FUNCTION commercial_tz() IS
  'Fuso em que as fronteiras comerciais são declaradas. Função, e não constante espalhada, para '
  'que mudar de fuso seja uma alteração em um lugar só.';

-- Soma N MESES DE CALENDÁRIO (não 90 dias) preservando a hora local do fuso comercial.
-- O PostgreSQL já resolve o dia inexistente grudando no último dia do mês de destino
-- (31/01 + 1 mês = 28/02), que é a semântica documentada em FULL_FREE_2026.md §3.
CREATE OR REPLACE FUNCTION add_calendar_months(p_from timestamptz, p_months integer)
RETURNS timestamptz
LANGUAGE sql IMMUTABLE AS $$
  SELECT ((p_from AT TIME ZONE commercial_tz()) + make_interval(months => p_months))
         AT TIME ZONE commercial_tz()
$$;

COMMENT ON FUNCTION add_calendar_months(timestamptz, integer) IS
  'Três meses significa três meses de calendário, não 90 dias: quem assina dia 15 espera que '
  'termine dia 15. A conversão passa pelo fuso comercial para que a hora local seja preservada '
  'mesmo quando houver mudança de offset entre as duas datas.';

-- Instante em que a campanha FULL FREE 2026 termina: 01/01/2027 00:00:00 em São Paulo.
CREATE OR REPLACE FUNCTION full_free_2026_ends_at() RETURNS timestamptz
LANGUAGE sql IMMUTABLE AS $$
  SELECT ('2027-01-01 00:00:00'::timestamp) AT TIME ZONE commercial_tz()
$$;

-- ---------------------------------------------------------------------------------------------
-- 2. A tabela
-- ---------------------------------------------------------------------------------------------

CREATE TABLE free_periods (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id           uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  subscription_id  uuid REFERENCES subscriptions(id) ON DELETE SET NULL,
  source           text NOT NULL CHECK (source IN ('2026_CAMPAIGN','2027_NEW_SUBSCRIPTION',
                                                   'PROMOTION','GRANT','PARTNERSHIP',
                                                   'MANUAL_EXCEPTION')),
  reason           text NOT NULL CHECK (length(reason) BETWEEN 3 AND 500),
  pricing_version  text NOT NULL CHECK (length(pricing_version) BETWEEN 1 AND 40),
  plan_key         text REFERENCES plans(plan_key),
  months           smallint CHECK (months IS NULL OR months BETWEEN 1 AND 60),
  started_at       timestamptz NOT NULL,
  ends_at          timestamptz NOT NULL,
  status           text NOT NULL DEFAULT 'active'
                   CHECK (status IN ('active','expired','cancelled','superseded')),
  granted_by       uuid REFERENCES users(id) ON DELETE SET NULL,
  cancelled_at     timestamptz,
  cancelled_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  cancel_reason    text CHECK (cancel_reason IS NULL OR length(cancel_reason) BETWEEN 3 AND 500),
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT free_period_order   CHECK (ends_at > started_at),
  CONSTRAINT free_period_cancel  CHECK ((status = 'cancelled') = (cancelled_at IS NOT NULL)),
  CONSTRAINT free_period_cancel_reason CHECK (status <> 'cancelled' OR cancel_reason IS NOT NULL)
);

COMMENT ON TABLE free_periods IS
  'Gratuidade TEMPORAL por conta. Não confundir com os planos tier=free, que são gratuitos por '
  'desenho e sem prazo. ends_at é EXCLUSIVO: o período é [started_at, ends_at).';
COMMENT ON COLUMN free_periods.months IS
  'Quantos meses de calendário foram concedidos. NULL quando o fim é uma data fixa de campanha. '
  'Guardado para que a auditoria responda "3 meses" sem reconstruir a conta a partir das datas.';
COMMENT ON COLUMN free_periods.subscription_id IS
  'Opcional de propósito: a campanha de 2026 concede gratuidade a contas que ainda não assinaram '
  'nada. Os 3 meses de 2027 sempre apontam para a assinatura que os originou.';

-- Uma conta não recebe a mesma campanha duas vezes. Concessões manuais e promoções podem repetir
-- (um cliente pode ganhar duas cortesias), por isso o índice cobre só as duas automáticas.
CREATE UNIQUE INDEX ux_free_period_campaign ON free_periods(org_id, source)
  WHERE source IN ('2026_CAMPAIGN','2027_NEW_SUBSCRIPTION') AND status <> 'cancelled';
CREATE UNIQUE INDEX ux_free_period_subscription ON free_periods(subscription_id)
  WHERE subscription_id IS NOT NULL AND source = '2027_NEW_SUBSCRIPTION' AND status <> 'cancelled';
CREATE INDEX ix_free_period_org ON free_periods(org_id, ends_at DESC);
CREATE INDEX ix_free_period_sweep ON free_periods(ends_at) WHERE status = 'active';
CREATE INDEX ix_free_period_plan ON free_periods(plan_key) WHERE plan_key IS NOT NULL;
CREATE INDEX ix_free_period_granted_by ON free_periods(granted_by) WHERE granted_by IS NOT NULL;
CREATE INDEX ix_free_period_cancelled_by ON free_periods(cancelled_by) WHERE cancelled_by IS NOT NULL;

-- Concessão é fato: origem, datas e versão de preço não se reescrevem. Encurtar um período
-- gratuito já concedido mudaria retroativamente o que o cliente recebeu — se for preciso tirar,
-- cancela-se com motivo, e o registro fica.
--
-- Este gatilho recusa a alteração para TODO MUNDO, administração inclusive. `guard_columns()` não
-- serviria aqui: ele isenta `app_priv()`, e a concessão precisa ser imutável justamente contra
-- quem tem privilégio — é contra a reescrita silenciosa do que o cliente recebeu que ela protege.
CREATE OR REPLACE FUNCTION free_period_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF (NEW.org_id, NEW.subscription_id, NEW.source, NEW.pricing_version, NEW.started_at,
      NEW.ends_at, NEW.months, NEW.granted_by, NEW.created_at)
     IS DISTINCT FROM
     (OLD.org_id, OLD.subscription_id, OLD.source, OLD.pricing_version, OLD.started_at,
      OLD.ends_at, OLD.months, OLD.granted_by, OLD.created_at) THEN
    RAISE EXCEPTION 'período gratuito concedido não se altera: cancele com motivo e conceda outro'
      USING ERRCODE = '42501';
  END IF;
  IF OLD.status IN ('cancelled','superseded') AND NEW.status <> OLD.status THEN
    RAISE EXCEPTION 'período gratuito % não volta a valer', OLD.status USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_free_period_immutable BEFORE UPDATE ON free_periods
  FOR EACH ROW EXECUTE FUNCTION free_period_immutable();

CREATE TRIGGER trg_free_period_touch BEFORE UPDATE ON free_periods
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- `ENABLE`, e NÃO `FORCE`. A diferença importa: FORCE aplica as políticas também ao DONO da
-- tabela, e o dono é quem roda `pg_dump`. Com FORCE, o backup falha com "query would be affected by
-- row-level security policy" — um backup que quebra em silêncio é pior do que não ter backup.
--
-- Nenhuma outra migração deste projeto usa FORCE, e o modelo de segurança não depende dele: a
-- aplicação conecta como `impacto_app`, que é NOSUPERUSER, NOBYPASSRLS e não-dona das tabelas
-- (ver 0002_security.sql). Quem impede a reescrita pelo dono é o GATILHO de imutabilidade abaixo,
-- que dispara para todo mundo.
ALTER TABLE free_periods ENABLE ROW LEVEL SECURITY;

CREATE POLICY freeperiod_read ON free_periods FOR SELECT
  USING (app_system() OR app_priv() OR org_id = app_org());
-- Só servidor e administração concedem. Uma organização não se autoconcede gratuidade.
CREATE POLICY freeperiod_write ON free_periods FOR INSERT
  WITH CHECK (app_system() OR app_priv());
CREATE POLICY freeperiod_update ON free_periods FOR UPDATE
  USING (app_system() OR app_priv()) WITH CHECK (app_system() OR app_priv());

GRANT SELECT, INSERT, UPDATE ON free_periods TO impacto_app;
REVOKE DELETE ON free_periods FROM impacto_app;

-- ---------------------------------------------------------------------------------------------
-- 3. FREE_PERIOD_END — a fonte única
-- ---------------------------------------------------------------------------------------------
--
-- Toda tela, todo aviso e toda decisão de cobrança lê DAQUI. O frontend não calcula data de fim;
-- ele exibe o que esta função devolve. É o que impede a classe de defeito em que a tela mostra um
-- prazo e a cobrança usa outro.

CREATE OR REPLACE FUNCTION free_period_end(p_org uuid) RETURNS timestamptz
LANGUAGE sql STABLE AS $$
  SELECT max(ends_at) FROM free_periods
   WHERE org_id = p_org AND status IN ('active','expired') AND ends_at > now()
$$;

COMMENT ON FUNCTION free_period_end(uuid) IS
  'FREE_PERIOD_END: o instante em que a gratuidade desta conta termina. Quando há mais de um '
  'período vigente (campanha + cortesia, por exemplo), vale o que termina DEPOIS — o cliente '
  'recebeu os dois, e tirar o melhor seria quebrar a promessa menor.';

-- ---------------------------------------------------------------------------------------------
-- 4. Concessão da campanha FULL FREE 2026 às contas que já existem
-- ---------------------------------------------------------------------------------------------
--
-- Contas criadas a partir daqui recebem a concessão no cadastro (services/free_period.py). As que
-- já existiam recebem agora. A concessão é por conta, mesmo quando a origem é uma data só: é o
-- registro individual que permite responder, para QUALQUER conta, desde quando e por quê.

INSERT INTO free_periods (org_id, source, reason, pricing_version, months, started_at, ends_at, status)
SELECT o.id, '2026_CAMPAIGN',
       'FULL FREE 2026 — produto integralmente gratuito até 31/12/2026 (America/Sao_Paulo), por '
       'decisão do proprietário registrada em PRICING_BIBLE.md §4.1.',
       '2027.01', NULL,
       least(o.created_at, now()),
       full_free_2026_ends_at(),
       'active'
  FROM organizations o
 WHERE full_free_2026_ends_at() > now()     -- rodar a migração em 2027 não ressuscita a campanha
   AND NOT EXISTS (SELECT 1 FROM free_periods f
                    WHERE f.org_id = o.id AND f.source = '2026_CAMPAIGN' AND f.status <> 'cancelled');

-- `pricing_version` nomeia a REGRA que concedeu a gratuidade, e a campanha FULL FREE 2026 está
-- escrita na PRICING_BIBLE.md — que é a Pricing Version 2027.01. Não é o que o cliente aceitou:
-- aceite mora em `offer_acceptances`, e receber gratuidade não é aceitar tabela de preço.
