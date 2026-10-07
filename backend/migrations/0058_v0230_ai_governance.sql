-- v0.23.0 — GOVERNANÇA DA CAMADA DE IA
--
-- O QUE A AUDITORIA DESTA RODADA ENCONTROU (ver AI_AUDIT.md)
--
-- A camada de IA é pequena de propósito: 3 dos 42 motores chamam modelo, e o resto do produto é
-- determinístico. Isso é desenho, não lacuna. O que falta não é mais IA — é GOVERNANÇA da que
-- existe. Item por item:
--
--   1. O prompt vive em literal dentro do gateway. Mudar a instrução muda o resultado de todo
--      cliente, e nada diz QUAL instrução produziu QUAL saída. Sem isso não existe avaliação,
--      regressão nem explicação de uma resposta antiga.
--   2. `ai_usage.status` aceita qualquer texto e o código grava `'ok'` SEMPRE — inclusive quando a
--      resposta externa é descartada por ser inválida. Uma coluna de estado com um valor só é
--      uma coluna que mente.
--   3. Não há política por risco. A mesma chamada que redige um resumo poderia redigir uma peça
--      com efeito jurídico, com o mesmo limite e a mesma obrigação de revisão.
--   4. Cota é contagem de CHAMADAS. Chamada não é unidade de custo: uma de 200 caracteres e uma de
--      200 mil consomem o mesmo da cota e custos muito diferentes.
--   5. Não há orçamento em dinheiro. O custo é registrado e não limita nada.
--   6. CRÉDITO e TOKEN eram a mesma coisa. Não são: crédito é unidade comercial, token é unidade
--      do provedor, e amarrar os dois obriga a reprecificar o produto a cada mudança de provedor.
--
-- O QUE ESTA MIGRAÇÃO NÃO FAZ, e por quê, está em AI_AUDIT.md §3: embeddings e cache semântico
-- (exigiriam provedor de embedding contratado), fallback entre provedores (exige política de
-- privacidade por provedor), lote (exige volume e preço reais), uso de ferramenta e agentes.

-- ── 1. REGISTRO DE PROMPT ────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_prompts (
  id          bigserial PRIMARY KEY,
  prompt_key  text NOT NULL CHECK (prompt_key ~ '^[a-z][a-z0-9_.]{2,60}$'),
  version     int  NOT NULL CHECK (version >= 1),
  tier        smallint NOT NULL,
  system_text text NOT NULL CHECK (length(btrim(system_text)) >= 20),
  output_schema jsonb,
  note        text NOT NULL CHECK (length(btrim(note)) >= 20),
  active      boolean NOT NULL DEFAULT false,
  created_by  uuid REFERENCES users(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (prompt_key, version)
);

-- Uma versão ativa por chave. Duas ativas significaria que ninguém sabe qual rodou.
CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_prompt_active ON ai_prompts (prompt_key) WHERE active;

-- Versão publicada não se reescreve: o texto do prompt é o que explica uma resposta antiga.
CREATE OR REPLACE FUNCTION ai_prompt_text_is_frozen() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.system_text <> OLD.system_text OR NEW.output_schema IS DISTINCT FROM OLD.output_schema
     OR NEW.tier <> OLD.tier THEN
    RAISE EXCEPTION 'prompt publicado não muda de texto: registre uma versão nova'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_ai_prompt_frozen ON ai_prompts;
CREATE TRIGGER trg_ai_prompt_frozen BEFORE UPDATE ON ai_prompts
  FOR EACH ROW EXECUTE FUNCTION ai_prompt_text_is_frozen();

-- ── 2. POLÍTICA DE MODELO POR FAIXA DE RISCO ─────────────────────────────────────────────────────
--
-- A faixa é do USO, não do modelo. O que ela decide: tamanho de entrada e saída, se a chamada pode
-- sair da instalação, se a saída exige revisão humana e se exige esquema de saída conferido.
CREATE TABLE IF NOT EXISTS ai_model_policies (
  tier                  smallint PRIMARY KEY CHECK (tier BETWEEN 0 AND 4),
  label                 text NOT NULL,
  max_input_chars       int  NOT NULL CHECK (max_input_chars > 0),
  max_output_tokens     int  NOT NULL CHECK (max_output_tokens > 0),
  allow_external        boolean NOT NULL,
  requires_schema       boolean NOT NULL,
  requires_human_review boolean NOT NULL,
  note                  text NOT NULL CHECK (length(btrim(note)) >= 40)
);

INSERT INTO ai_model_policies (tier, label, max_input_chars, max_output_tokens, allow_external,
                               requires_schema, requires_human_review, note) VALUES
  (0, 'Determinístico (sem modelo)', 100000, 1, false, false, false,
   'Faixa dos motores que NÃO chamam modelo: regra, cálculo e consulta. Está na tabela para que o '
   'inventário mostre que a maioria do produto é determinística, em vez de deixar isso implícito.'),
  (1, 'Apoio à redação', 20000, 2000, true, false, true,
   'Rascunho, resumo, reescrita. A saída é texto para pessoa revisar e nunca vira estado do '
   'sistema sozinha. Pode sair da instalação porque o conteúdo é da própria organização e passa '
   'por redação de dado pessoal antes.'),
  (2, 'Classificação com esquema', 20000, 800, true, true, true,
   'Classificar documento, extrair campo. A saída ENTRA em campo estruturado, então exige esquema '
   'conferido: texto livre num campo tipado é como um número inventado chega ao banco.'),
  (3, 'Apoio a decisão sobre terceiro', 8000, 800, false, true, true,
   'Qualquer uso que produza afirmação sobre OUTRA organização. Não sai da instalação: mandar dado '
   'de terceiro para provedor externo exigiria base legal que a plataforma não tem hoje.'),
  (4, 'Efeito jurídico ou financeiro', 1, 1, false, true, true,
   'NENHUM uso nesta faixa está implementado, e a faixa existe para dizer isso. Limites de 1 '
   'tornam a faixa inoperante por construção: se alguém declarar um uso aqui, ele falha na '
   'primeira chamada em vez de funcionar sem a decisão humana que a faixa exige.')
ON CONFLICT (tier) DO UPDATE SET label = EXCLUDED.label,
  max_input_chars = EXCLUDED.max_input_chars, max_output_tokens = EXCLUDED.max_output_tokens,
  allow_external = EXCLUDED.allow_external, requires_schema = EXCLUDED.requires_schema,
  requires_human_review = EXCLUDED.requires_human_review, note = EXCLUDED.note;

ALTER TABLE ai_prompts DROP CONSTRAINT IF EXISTS ai_prompt_tier_exists;
ALTER TABLE ai_prompts ADD CONSTRAINT ai_prompt_tier_exists
  FOREIGN KEY (tier) REFERENCES ai_model_policies(tier);

-- ── 3. ESTADO REAL DA CHAMADA ────────────────────────────────────────────────────────────────────
--
-- `status` aceitava qualquer texto e o código gravava `'ok'` sempre — inclusive quando a resposta
-- externa era DESCARTADA por ser inválida e o resultado devolvido veio do motor local. Quem lesse
-- a tabela concluiria que o provedor externo funcionou.
ALTER TABLE ai_usage DROP CONSTRAINT IF EXISTS ai_usage_status_known;
ALTER TABLE ai_usage ADD CONSTRAINT ai_usage_status_known CHECK (status IN (
  'ok',                 -- resposta do provedor usada
  'local_only',         -- provedor externo não configurado: resultado é do motor local
  'fallback_local',     -- provedor externo falhou; resultado é do motor local
  'invalid_output',     -- provedor respondeu e a resposta foi descartada por não casar o esquema
  'blocked_policy',     -- recusado pela política da faixa (tamanho, saída externa proibida)
  'quota_exceeded',
  'budget_exceeded',
  'provider_error',
  'rejected'));

ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS prompt_key text;
ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS prompt_version int;
ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS tier smallint REFERENCES ai_model_policies(tier);
ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS credits_charged int;
ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS schema_valid boolean;
ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS idempotency_key text;
ALTER TABLE ai_usage ADD COLUMN IF NOT EXISTS request_id text;

-- Idempotência por organização: a MESMA chave não cobra duas vezes.
CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_usage_idempotency
  ON ai_usage (org_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_ai_usage_prompt ON ai_usage (prompt_key, prompt_version)
  WHERE prompt_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_ai_usage_not_ok ON ai_usage (status, created_at DESC)
  WHERE status <> 'ok';

-- ── 4. CRÉDITO ≠ TOKEN ───────────────────────────────────────────────────────────────────────────
--
-- Crédito é unidade COMERCIAL: o que a organização comprou ou recebeu. Token é unidade do
-- PROVEDOR. Amarrar os dois obriga a reprecificar o produto a cada mudança de tabela de preço do
-- provedor, e expõe ao cliente uma unidade que não é dele.
--
-- O razão é append-only: concessão, consumo e devolução são lançamentos. Saldo é soma, nunca uma
-- coluna que alguém atualiza — foi essa a lição do Value Ledger.
CREATE TABLE IF NOT EXISTS ai_credit_ledger (
  id              bigserial PRIMARY KEY,
  org_id          uuid NOT NULL REFERENCES organizations(id),
  delta           int  NOT NULL CHECK (delta <> 0),
  reason          text NOT NULL CHECK (reason IN ('grant','plan_cycle','consumption','refund','adjustment','expiry')),
  ref_type        text,
  ref_id          text,
  idempotency_key text,
  note            text,
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  -- Consumo é negativo, concessão é positiva. Sem isto, um "consumo" positivo criaria crédito.
  CONSTRAINT credit_sign_matches_reason CHECK (
    (reason IN ('grant','plan_cycle','refund') AND delta > 0)
    OR (reason IN ('consumption','expiry') AND delta < 0)
    OR reason = 'adjustment')
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_ai_credit_idempotency
  ON ai_credit_ledger (org_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_ai_credit_org ON ai_credit_ledger (org_id, id DESC);

DROP TRIGGER IF EXISTS trg_ai_credit_append_only ON ai_credit_ledger;
CREATE TRIGGER trg_ai_credit_append_only BEFORE UPDATE OR DELETE ON ai_credit_ledger
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

DROP TRIGGER IF EXISTS trg_no_truncate_ai_credit ON ai_credit_ledger;
CREATE TRIGGER trg_no_truncate_ai_credit BEFORE TRUNCATE ON ai_credit_ledger
  FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate();

CREATE OR REPLACE FUNCTION ai_credit_balance(p_org uuid) RETURNS bigint LANGUAGE sql STABLE AS $$
  SELECT coalesce(sum(delta), 0)::bigint FROM ai_credit_ledger WHERE org_id = p_org
$$;

-- CONSUMO ATÔMICO. O defeito que esta função existe para evitar: ler o saldo, decidir, e gravar o
-- consumo em três passos deixa a janela em que duas chamadas simultâneas leem o mesmo saldo e as
-- duas passam. O bloqueio consultivo por organização fecha a janela sem travar a tabela inteira.
CREATE OR REPLACE FUNCTION ai_credit_consume(
  p_org uuid, p_credits int, p_ref_type text, p_ref_id text, p_idempotency text)
RETURNS TABLE(charged int, balance_after bigint, outcome text) LANGUAGE plpgsql AS $$
DECLARE saldo bigint; existente int;
BEGIN
  IF p_credits <= 0 THEN
    RAISE EXCEPTION 'consumo de crédito tem de ser positivo' USING ERRCODE = '23514';
  END IF;
  PERFORM pg_advisory_xact_lock(hashtext('ai_credit:' || p_org::text));

  IF p_idempotency IS NOT NULL THEN
    SELECT -delta INTO existente FROM ai_credit_ledger
     WHERE org_id = p_org AND idempotency_key = p_idempotency;
    IF existente IS NOT NULL THEN
      -- Repetição da MESMA operação: devolve o que foi cobrado antes, sem cobrar de novo.
      RETURN QUERY SELECT existente, ai_credit_balance(p_org), 'already_charged';
      RETURN;
    END IF;
  END IF;

  saldo := ai_credit_balance(p_org);
  IF saldo < p_credits THEN
    RETURN QUERY SELECT 0, saldo, 'insufficient';
    RETURN;
  END IF;

  INSERT INTO ai_credit_ledger (org_id, delta, reason, ref_type, ref_id, idempotency_key)
  VALUES (p_org, -p_credits, 'consumption', p_ref_type, p_ref_id, p_idempotency);
  RETURN QUERY SELECT p_credits, ai_credit_balance(p_org), 'charged';
END $$;

-- ── 5. ORÇAMENTO EM DINHEIRO ─────────────────────────────────────────────────────────────────────
--
-- Cota conta CHAMADAS; orçamento limita DINHEIRO. São controles diferentes e os dois são
-- necessários: uma chamada de 200 mil caracteres consome o mesmo da cota que uma de 200 e custa
-- muito mais. `hard_stop` separa "avise" de "pare" — um limite que só avisa não é limite, e um que
-- só para no meio de um trabalho longo também não serve.
CREATE TABLE IF NOT EXISTS ai_budgets (
  org_id       uuid NOT NULL REFERENCES organizations(id),
  period       date NOT NULL,
  limit_cents  bigint NOT NULL CHECK (limit_cents > 0),
  warn_at_pct  smallint NOT NULL DEFAULT 80 CHECK (warn_at_pct BETWEEN 1 AND 100),
  hard_stop    boolean NOT NULL DEFAULT false,
  note         text,
  created_by   uuid REFERENCES users(id),
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (org_id, period)
);

CREATE OR REPLACE FUNCTION ai_spend_cents(p_org uuid, p_period date) RETURNS bigint
LANGUAGE sql STABLE AS $$
  SELECT coalesce(sum(cost_cents_estimate), 0)::bigint FROM ai_usage
   WHERE org_id = p_org AND cost_status = 'estimated'
     AND date_trunc('month', created_at) = date_trunc('month', p_period::timestamptz)
$$;

-- O estado do orçamento, com a ressalva que importa: gasto só é contado onde HÁ preço vigente.
-- Sem tabela de preço, `cost_status = 'no_price_table'` e a chamada não entra na soma — então o
-- orçamento diria "zero gasto" sobre uso real. A função declara isso em vez de esconder.
CREATE OR REPLACE FUNCTION ai_budget_state(p_org uuid, p_period date)
RETURNS TABLE(limit_cents bigint, spent_cents bigint, pct numeric, hard_stop boolean,
              unpriced_calls bigint, state text) LANGUAGE plpgsql STABLE AS $$
DECLARE lim bigint; gasto bigint; sem_preco bigint; parar boolean; aviso smallint;
BEGIN
  SELECT b.limit_cents, b.hard_stop, b.warn_at_pct INTO lim, parar, aviso
    FROM ai_budgets b WHERE b.org_id = p_org AND b.period = date_trunc('month', p_period)::date;
  gasto := ai_spend_cents(p_org, p_period);
  SELECT count(*) INTO sem_preco FROM ai_usage
   WHERE org_id = p_org AND cost_status = 'no_price_table'
     AND date_trunc('month', created_at) = date_trunc('month', p_period::timestamptz);
  IF lim IS NULL THEN
    RETURN QUERY SELECT NULL::bigint, gasto, NULL::numeric, false, sem_preco, 'no_budget';
    RETURN;
  END IF;
  RETURN QUERY SELECT lim, gasto, round(100.0 * gasto / lim, 1), coalesce(parar, false), sem_preco,
    CASE WHEN gasto >= lim THEN 'exceeded'
         WHEN gasto >= lim * aviso / 100.0 THEN 'warning'
         ELSE 'ok' END;
END $$;

-- ── RLS ──────────────────────────────────────────────────────────────────────────────────────────
ALTER TABLE ai_prompts ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_model_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_credit_ledger ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_budgets ENABLE ROW LEVEL SECURITY;

-- O TEXTO do prompt é da plataforma, não do cliente: expô-lo entrega a instrução que produz o
-- resultado, que é parte do produto. A organização vê QUAL versão rodou (em `ai_usage`), não o texto.
CREATE POLICY aiprompt_priv ON ai_prompts FOR SELECT USING (app_system() OR app_priv());
-- A política de faixa, ao contrário, é pública para quem está autenticado: o cliente tem direito de
-- saber que a faixa 3 não sai da instalação e que toda saída exige revisão humana.
CREATE POLICY aipolicy_read ON ai_model_policies FOR SELECT
  USING (app_system() OR app_authenticated() OR app_priv());
CREATE POLICY aicredit_own ON ai_credit_ledger FOR SELECT
  USING (app_system() OR app_priv() OR org_id = app_org());
CREATE POLICY aicredit_write ON ai_credit_ledger FOR INSERT WITH CHECK (app_system());
CREATE POLICY aibudget_own ON ai_budgets FOR SELECT
  USING (app_system() OR app_priv() OR org_id = app_org());
CREATE POLICY aibudget_write ON ai_budgets FOR ALL
  USING (app_system()) WITH CHECK (app_system());

GRANT SELECT ON ai_prompts, ai_model_policies TO impacto_app;
GRANT SELECT, INSERT ON ai_credit_ledger TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE ai_credit_ledger_id_seq TO impacto_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ai_budgets TO impacto_app;
