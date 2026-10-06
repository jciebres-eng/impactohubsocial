-- v0.21.0 — MOTOR DE USO: contadores, alertas de 70/90/100% e teto de gasto
--
-- O QUE EXISTIA, E POR QUE NÃO BASTAVA
--
-- O limite de plano já era verificado em sete lugares (`check_limit`), sempre por contagem AO VIVO:
-- um `SELECT count(*)` imediatamente antes da ação. Isso funciona para BLOQUEAR e falha em tudo
-- mais:
--
--   * não há histórico — "quanto esta conta usou em março?" não tem resposta depois que março passa
--     e os registros foram apagados pela retenção;
--   * não há aviso — a pessoa descobre o limite quando bate nele, com um 402 no meio do trabalho,
--     e nunca aos 70%, quando ainda dá para fazer alguma coisa a respeito;
--   * não há teto de GASTO, só teto de quantidade; quem usa um recurso medido não consegue dizer
--     "não me deixe passar de R$ X este mês".
--
-- Nada aqui substitui a contagem ao vivo: ela continua sendo quem bloqueia, porque é ela que não
-- pode errar. O contador é a camada que AVISA e que LEMBRA.

CREATE TABLE usage_counters (
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  metric       text NOT NULL CHECK (length(metric) BETWEEN 2 AND 60),
  period_start date NOT NULL,
  period_end   date NOT NULL,
  used         bigint NOT NULL DEFAULT 0 CHECK (used >= 0),
  limit_value  bigint CHECK (limit_value IS NULL OR limit_value >= 0),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, metric, period_start),
  CONSTRAINT usage_period_order CHECK (period_end > period_start)
);

COMMENT ON TABLE usage_counters IS
  'Consumo por organização, métrica e período. `limit_value` NULL = ilimitado. Guardado para que a '
  'conta de março continue existindo em abril — a contagem ao vivo não sobrevive à retenção.';

CREATE INDEX ix_usage_period ON usage_counters(period_start DESC);

-- Um alerta por limiar, por período. Sem isto, um job que roda de hora em hora manda 24 avisos
-- por dia de "você chegou a 90%" — e a pessoa desliga a notificação, que é o oposto do objetivo.
CREATE TABLE usage_alerts (
  org_id       uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  metric       text NOT NULL,
  period_start date NOT NULL,
  threshold    smallint NOT NULL CHECK (threshold IN (70, 90, 100)),
  used         bigint NOT NULL,
  limit_value  bigint NOT NULL,
  notified_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, metric, period_start, threshold)
);

COMMENT ON TABLE usage_alerts IS
  'Qual limiar já foi avisado. A chave primária É a idempotência: o segundo aviso do mesmo limiar '
  'no mesmo período não entra.';

-- ---------------------------------------------------------------------------------------------
-- Teto de gasto
-- ---------------------------------------------------------------------------------------------

CREATE TABLE spend_limits (
  org_id      uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  limit_cents bigint CHECK (limit_cents IS NULL OR limit_cents >= 0),
  action      text NOT NULL DEFAULT 'warn' CHECK (action IN ('warn', 'hard_stop')),
  set_by      uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE spend_limits IS
  'Teto de gasto mensal escolhido pela organização. `hard_stop` interrompe o consumo excedente em '
  'vez de gerar fatura; `warn` apenas avisa. A escolha é do cliente porque o custo é dele.';
COMMENT ON COLUMN spend_limits.action IS
  'warn = avisa e deixa seguir; hard_stop = PARA. O padrão é warn porque parar o trabalho de alguém '
  'sem que essa pessoa tenha pedido é pior do que avisá-la.';

CREATE INDEX ix_spend_limit_set_by ON spend_limits(set_by) WHERE set_by IS NOT NULL;

CREATE TRIGGER trg_spend_limit_touch BEFORE UPDATE ON spend_limits
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();
CREATE TRIGGER trg_usage_counter_touch BEFORE UPDATE ON usage_counters
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

ALTER TABLE usage_counters ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_alerts   ENABLE ROW LEVEL SECURITY;
ALTER TABLE spend_limits   ENABLE ROW LEVEL SECURITY;

CREATE POLICY usage_read ON usage_counters FOR SELECT
  USING (app_system() OR app_priv() OR org_id = app_org());
CREATE POLICY usage_write ON usage_counters FOR INSERT WITH CHECK (app_system());
CREATE POLICY usage_update ON usage_counters FOR UPDATE USING (app_system()) WITH CHECK (app_system());

CREATE POLICY usage_alert_read ON usage_alerts FOR SELECT
  USING (app_system() OR app_priv() OR org_id = app_org());
CREATE POLICY usage_alert_write ON usage_alerts FOR INSERT WITH CHECK (app_system());

CREATE POLICY spend_read ON spend_limits FOR SELECT
  USING (app_system() OR app_priv() OR org_id = app_org());
-- O teto é do cliente: ele define, ele muda. Uma plataforma que só deixa o suporte mexer no teto
-- de gasto do cliente está tratando uma proteção dele como um favor dela.
CREATE POLICY spend_write ON spend_limits FOR INSERT
  WITH CHECK (app_system() OR org_id = app_org());
CREATE POLICY spend_update ON spend_limits FOR UPDATE
  USING (app_system() OR org_id = app_org()) WITH CHECK (app_system() OR org_id = app_org());

GRANT SELECT, INSERT, UPDATE ON usage_counters TO impacto_app;
GRANT SELECT, INSERT ON usage_alerts TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON spend_limits TO impacto_app;
REVOKE DELETE ON usage_counters, usage_alerts, spend_limits FROM impacto_app;

-- ---------------------------------------------------------------------------------------------
-- Idempotência de evento financeiro
-- ---------------------------------------------------------------------------------------------
--
-- Já havia idempotência por UNIQUE do lado do PROVEDOR (`billing_events(provider, event_id)`,
-- `platform_charges(provider, provider_charge_id)`): ela protege contra o provedor reenviar o mesmo
-- webhook. O que faltava era a do lado do CLIENTE — a chave que QUEM CHAMA escolhe para dizer "esta
-- é a mesma cobrança que eu já pedi". Sem ela, um cliente que não recebe a resposta por queda de
-- rede e tenta de novo cria a segunda cobrança, e ninguém no sistema sabe que são a mesma.

ALTER TABLE platform_charges ADD COLUMN idempotency_key text
  CHECK (idempotency_key IS NULL OR length(idempotency_key) BETWEEN 8 AND 200);

CREATE UNIQUE INDEX ux_charge_idempotency ON platform_charges(org_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL;

COMMENT ON COLUMN platform_charges.idempotency_key IS
  'Chave escolhida por quem chama. Escopo por organização: duas organizações podem usar a mesma '
  'string sem colidir, e uma não descobre a chave da outra por conflito de inserção.';

-- ---------------------------------------------------------------------------------------------
-- Cota de IA: UMA contagem
-- ---------------------------------------------------------------------------------------------
--
-- A auditoria encontrou duas contagens divergentes para a mesma cota: o bloqueio excluía
-- `status = 'rejected'` e o painel não. Resultado: a tela podia dizer "você usou 80 de 100" enquanto
-- o bloqueio contava 60 — e a pessoa planejava o mês com um número que não era o que a limitava.
-- Nenhuma das duas estava "errada" isoladamente; o defeito era existirem duas.

CREATE OR REPLACE FUNCTION ai_usage_this_month(p_org uuid) RETURNS bigint
LANGUAGE sql STABLE AS $$
  SELECT count(*) FROM ai_usage
   WHERE org_id = p_org
     AND created_at >= date_trunc('month', now())
     -- Pedido recusado não consome cota: a pessoa não recebeu nada. Esta era a regra do BLOQUEIO,
     -- e é a certa — então é ela que o painel passa a mostrar também.
     AND status <> 'rejected'
$$;

COMMENT ON FUNCTION ai_usage_this_month(uuid) IS
  'A contagem de cota de IA do mês. Função, e não consulta repetida, porque duas cópias da mesma '
  'regra divergiram uma vez e divergiriam de novo.';
