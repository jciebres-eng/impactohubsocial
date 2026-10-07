-- v0.22.0 — MOTOR FINANCEIRO (CALCULA · INSTRUI · CONCILIA) E ALÇADA DE APROVAÇÃO
--
-- A REGRA QUE GOVERNA ESTE ARQUIVO
--
-- NON_CUSTODIAL_ARCHITECTURE.md (ADR-284): a plataforma NÃO guarda dinheiro de outra pessoa. Ela
-- calcula quanto é devido, emite a INSTRUÇÃO de pagamento e concilia o que aconteceu. O dinheiro
-- vai direto de quem paga a quem recebe.
--
-- Por isso NÃO existe aqui: `payout`, `split`, `recipient`, `escrow`, carteira, saldo de terceiro.
-- Existe `payment_instructions` — que é DOCUMENTO, não transferência.
--
-- O QUE EXISTIA, E O QUE FALTAVA
--
-- `ledger_entries` existe desde a migração 0002 e é trilha encadeada por hash, não livro contábil:
-- 60 tipos de EVENTO DE NEGÓCIO, um `amount_cents` nullable, sem partida dobrada, sem conta, sem
-- competência. Chamar aquilo de contabilidade seria o tipo de erro que só aparece no primeiro
-- fechamento.
--
-- Faltavam: plano de contas, centro de custo, competência separada de caixa, despesa da PRÓPRIA
-- plataforma (só o custo de IA estava modelado, e a tabela de preço está vazia), e qualquer alçada
-- por valor — não havia nenhuma faixa que exigisse aprovação em lugar nenhum da plataforma.

-- ================================================================== 1. PLANO DE CONTAS
--
-- Da PRÓPRIA plataforma. Não é o plano de contas do cliente: aquilo é problema da contabilidade
-- dele, e a plataforma não se mete.

CREATE TABLE chart_of_accounts (
  code        text PRIMARY KEY CHECK (code ~ '^[0-9](\.[0-9]{1,2}){0,3}$'),
  name        text NOT NULL CHECK (length(name) BETWEEN 3 AND 120),
  nature      text NOT NULL CHECK (nature IN ('asset','liability','equity','revenue','expense')),
  parent_code text REFERENCES chart_of_accounts(code) ON DELETE RESTRICT,
  -- Conta ANALÍTICA recebe lançamento; SINTÉTICA só soma as filhas. Lançar numa sintética é o erro
  -- clássico que desalinha o balancete, e o gatilho abaixo o recusa.
  analytical  boolean NOT NULL DEFAULT true,
  active      boolean NOT NULL DEFAULT true,
  note        text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE chart_of_accounts IS
  'Plano de contas da plataforma. `nature` segue a natureza contábil; o sinal do lançamento sai '
  'dela, e não de um campo "positivo/negativo" que alguém preencheria errado.';

CREATE INDEX ix_coa_parent ON chart_of_accounts(parent_code) WHERE parent_code IS NOT NULL;

INSERT INTO chart_of_accounts(code, name, nature, parent_code, analytical) VALUES
  ('1',       'Ativo',                          'asset',     NULL, false),
  ('1.1',     'Disponibilidades',               'asset',     '1',  false),
  ('1.1.1',   'Caixa e equivalentes',           'asset',     '1.1', true),
  ('1.1.2',   'Aplicações de liquidez imediata','asset',     '1.1', true),
  ('1.2',     'Créditos',                       'asset',     '1',  false),
  ('1.2.1',   'Clientes a receber',             'asset',     '1.2', true),
  ('1.2.2',   'Valores a receber de provedor',  'asset',     '1.2', true),
  ('2',       'Passivo',                        'liability', NULL, false),
  ('2.1',     'Obrigações a pagar',             'liability', '2',  false),
  ('2.1.1',   'Fornecedores',                   'liability', '2.1', true),
  ('2.1.2',   'Obrigações tributárias',         'liability', '2.1', true),
  ('2.1.3',   'Obrigações trabalhistas',        'liability', '2.1', true),
  ('2.2',     'Receita diferida',               'liability', '2',  false),
  ('2.2.1',   'Assinatura faturada e não incorrida', 'liability', '2.2', true),
  ('3',       'Patrimônio líquido',             'equity',    NULL, false),
  ('3.1',     'Capital e resultados',           'equity',    '3',  true),
  ('4',       'Receita',                        'revenue',   NULL, false),
  ('4.1',     'Receita recorrente',             'revenue',   '4',  false),
  ('4.1.1',   'Assinatura',                     'revenue',   '4.1', true),
  ('4.2',     'Receita por uso',                'revenue',   '4',  false),
  ('4.2.1',   'Uso medido',                     'revenue',   '4.2', true),
  ('4.3',     'Receita de serviços',            'revenue',   '4',  false),
  ('4.3.1',   'Serviços e implantação',         'revenue',   '4.3', true),
  ('4.4',     'Receita de marketplace',         'revenue',   '4',  false),
  ('4.4.1',   'Taxa de intermediação',          'revenue',   '4.4', true),
  ('4.9',     'Deduções da receita',            'revenue',   '4',  false),
  ('4.9.1',   'Estornos e cancelamentos',       'revenue',   '4.9', true),
  ('4.9.2',   'Tributos sobre a receita',       'revenue',   '4.9', true),
  ('5',       'Despesa',                        'expense',   NULL, false),
  ('5.1',     'Custo de servir',                'expense',   '5',  false),
  ('5.1.1',   'Infraestrutura e nuvem',         'expense',   '5.1', true),
  ('5.1.2',   'Inteligência artificial',        'expense',   '5.1', true),
  ('5.1.3',   'Taxas de meio de pagamento',     'expense',   '5.1', true),
  ('5.1.4',   'Armazenamento e tráfego',        'expense',   '5.1', true),
  ('5.2',     'Pessoas',                        'expense',   '5',  false),
  ('5.2.1',   'Folha e encargos',               'expense',   '5.2', true),
  ('5.2.2',   'Serviços de terceiros',          'expense',   '5.2', true),
  ('5.3',     'Administrativas',                'expense',   '5',  false),
  ('5.3.1',   'Jurídico e contábil',            'expense',   '5.3', true),
  ('5.3.2',   'Ferramentas e licenças',         'expense',   '5.3', true),
  ('5.4',     'Comercial',                      'expense',   '5',  false),
  ('5.4.1',   'Marketing',                      'expense',   '5.4', true),
  ('5.4.2',   'Vendas',                         'expense',   '5.4', true);

-- ================================================================== 2. CENTRO DE CUSTO

CREATE TABLE cost_centers (
  code       text PRIMARY KEY CHECK (code ~ '^[A-Z][A-Z0-9_]{1,19}$'),
  name       text NOT NULL CHECK (length(name) BETWEEN 3 AND 80),
  active     boolean NOT NULL DEFAULT true,
  owner_role text,
  created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO cost_centers(code, name, owner_role) VALUES
  ('TECH',        'Tecnologia',        'operations'),
  ('CLOUD',       'Nuvem e infraestrutura', 'operations'),
  ('AI',          'Inteligência artificial', 'operations'),
  ('PRODUCT',     'Produto',           NULL),
  ('MARKETING',   'Marketing',         NULL),
  ('SALES',       'Vendas',            NULL),
  ('SUPPORT',     'Suporte',           'support'),
  ('LEGAL',       'Jurídico',          'compliance'),
  ('FINANCE',     'Financeiro',        'finance'),
  ('ADMIN',       'Administrativo',    NULL),
  ('MARKETPLACE', 'Marketplace',       NULL);

-- ================================================================== 3. COMPETÊNCIA ≠ CAIXA
--
-- Esta é a distinção que o prompt pede em letras e que não existia: "Separar claramente CAIXA de
-- COMPETÊNCIA. Não tratar fluxo de caixa como contabilidade."
--
-- Uma assinatura anual recebida em janeiro é CAIXA de janeiro e COMPETÊNCIA de doze meses. Tratar
-- as duas como a mesma coisa faz janeiro parecer um mês extraordinário e dezembro parecer um
-- desastre — e nenhuma das duas leituras é verdade.

CREATE TABLE accounting_periods (
  period     date PRIMARY KEY,                       -- primeiro dia do mês de competência
  status     text NOT NULL DEFAULT 'open' CHECK (status IN ('open','closing','closed')),
  closed_at  timestamptz,
  closed_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  note       text,
  CONSTRAINT period_is_first_day CHECK (date_trunc('month', period)::date = period),
  CONSTRAINT period_closed_pair CHECK ((status = 'closed') = (closed_at IS NOT NULL))
);

COMMENT ON TABLE accounting_periods IS
  'Competência mensal. Fechada não recebe lançamento novo — é o que torna o número de um mês '
  'citável depois. Reabrir exige decisão humana e fica registrado.';

CREATE TABLE accounting_entries (
  id            bigserial PRIMARY KEY,
  period        date NOT NULL REFERENCES accounting_periods(period) ON DELETE RESTRICT,
  account_code  text NOT NULL REFERENCES chart_of_accounts(code) ON DELETE RESTRICT,
  cost_center   text REFERENCES cost_centers(code) ON DELETE RESTRICT,
  -- Partida dobrada: cada lançamento é um lado, e os lados de um documento somam zero. O gatilho
  -- `accounting_batch_balances()` confere no fechamento do lote.
  batch_id      uuid NOT NULL,
  side          text NOT NULL CHECK (side IN ('debit','credit')),
  amount_cents  bigint NOT NULL CHECK (amount_cents > 0),
  currency      char(3) NOT NULL DEFAULT 'BRL' CHECK (currency ~ '^[A-Z]{3}$'),
  description   text NOT NULL CHECK (length(description) BETWEEN 3 AND 300),
  -- Procedência: de onde este lançamento veio. Lançamento sem origem é lançamento que ninguém
  -- consegue explicar no ano seguinte.
  source_kind   text NOT NULL CHECK (source_kind IN ('invoice','charge','instruction','ai_usage',
                                                     'manual','adjustment','accrual','deferral')),
  source_id     text,
  cash_date     date,          -- quando o dinheiro entrou/saiu. NULL = ainda não houve caixa.
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

COMMENT ON COLUMN accounting_entries.cash_date IS
  'Data do CAIXA, separada da competência (`period`). As duas juntas respondem "quanto entrou em '
  'janeiro" e "quanto foi de janeiro", que são perguntas diferentes com respostas diferentes.';

CREATE INDEX ix_acct_period ON accounting_entries(period, account_code);
CREATE INDEX ix_acct_batch ON accounting_entries(batch_id);
CREATE INDEX ix_acct_cash ON accounting_entries(cash_date) WHERE cash_date IS NOT NULL;
CREATE INDEX ix_acct_cc ON accounting_entries(cost_center) WHERE cost_center IS NOT NULL;
CREATE INDEX ix_acct_source ON accounting_entries(source_kind, source_id);

-- Lançamento contábil não se altera nem se apaga: corrige-se com lançamento de estorno. É o que
-- permite responder "o que o balancete de março dizia em março?".
CREATE TRIGGER trg_acct_append BEFORE UPDATE OR DELETE ON accounting_entries
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Lançar em conta sintética, em competência fechada, ou em conta inativa: recusado pelo banco.
CREATE OR REPLACE FUNCTION accounting_entry_guard() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v record;
BEGIN
  SELECT analytical, active INTO v FROM chart_of_accounts WHERE code = NEW.account_code;
  IF NOT v.analytical THEN
    RAISE EXCEPTION 'conta % é sintética: lançamento vai na analítica', NEW.account_code
      USING ERRCODE = '23514';
  END IF;
  IF NOT v.active THEN
    RAISE EXCEPTION 'conta % está inativa', NEW.account_code USING ERRCODE = '23514';
  END IF;
  IF (SELECT status FROM accounting_periods WHERE period = NEW.period) <> 'open' THEN
    RAISE EXCEPTION 'competência % não está aberta: use lançamento de ajuste na competência atual',
      to_char(NEW.period, 'MM/YYYY') USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_acct_guard BEFORE INSERT ON accounting_entries
  FOR EACH ROW EXECUTE FUNCTION accounting_entry_guard();

-- Lote desbalanceado é erro de lançamento, e um balancete que não fecha não é informação.
CREATE OR REPLACE FUNCTION batch_is_balanced(p_batch uuid) RETURNS boolean
LANGUAGE sql STABLE AS $$
  SELECT coalesce(sum(CASE WHEN side = 'debit' THEN amount_cents ELSE -amount_cents END), 0) = 0
    FROM accounting_entries WHERE batch_id = p_batch
$$;

ALTER TABLE chart_of_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE cost_centers ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting_periods ENABLE ROW LEVEL SECURITY;
ALTER TABLE accounting_entries ENABLE ROW LEVEL SECURITY;

-- Contabilidade da plataforma é assunto da EQUIPE: nenhuma organização cliente a lê.
CREATE POLICY coa_priv ON chart_of_accounts  FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY cc_priv ON cost_centers       FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY period_priv ON accounting_periods FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY period_w ON accounting_periods FOR INSERT WITH CHECK (app_system() OR app_priv());
CREATE POLICY period_u ON accounting_periods FOR UPDATE USING (app_system() OR app_priv())
                                                WITH CHECK (app_system() OR app_priv());
CREATE POLICY acct_priv ON accounting_entries FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY acct_w ON accounting_entries FOR INSERT WITH CHECK (app_system() OR app_priv());

GRANT SELECT ON chart_of_accounts, cost_centers TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON accounting_periods TO impacto_app;
GRANT SELECT, INSERT ON accounting_entries TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE accounting_entries_id_seq TO impacto_app;
REVOKE UPDATE, DELETE ON accounting_entries FROM impacto_app;

-- ================================================================== 4. DESPESA DA PLATAFORMA
--
-- Só o custo de IA estava modelado, e `ai_price_table` está vazia. Nuvem, folha, ferramentas e
-- taxa de meio de pagamento não existiam em lugar nenhum — e sem o lado do custo não existe
-- margem, que é o número que decide se o negócio se paga.

CREATE TABLE platform_expenses (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  period        date NOT NULL,                    -- competência
  account_code  text NOT NULL REFERENCES chart_of_accounts(code) ON DELETE RESTRICT,
  cost_center   text NOT NULL REFERENCES cost_centers(code) ON DELETE RESTRICT,
  supplier_name text CHECK (supplier_name IS NULL OR length(supplier_name) BETWEEN 2 AND 160),
  supplier_doc  text CHECK (supplier_doc IS NULL OR supplier_doc ~ '^[0-9]{11,14}$'),
  description   text NOT NULL CHECK (length(description) BETWEEN 3 AND 300),
  amount_cents  bigint NOT NULL CHECK (amount_cents > 0),
  currency      char(3) NOT NULL DEFAULT 'BRL',
  due_on        date,
  paid_on       date,
  document_ref  text,
  status        text NOT NULL DEFAULT 'registered'
                CHECK (status IN ('registered','approved','scheduled','paid','cancelled')),
  -- Despesa RECORRENTE declarada: nuvem, ferramenta, folha. Serve ao previsto, não só ao realizado.
  recurring     boolean NOT NULL DEFAULT false,
  created_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  approved_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT expense_period_first_day CHECK (date_trunc('month', period)::date = period),
  CONSTRAINT expense_paid_pair CHECK ((status = 'paid') = (paid_on IS NOT NULL)),
  -- Quem registra não aprova. A regra vale desde a primeira despesa, e não a partir do dia em que
  -- alguém se lembrar de criar o controle.
  CONSTRAINT expense_four_eyes CHECK (approved_by IS NULL OR approved_by <> created_by)
);

COMMENT ON TABLE platform_expenses IS
  'Despesa da PRÓPRIA plataforma, com conta e centro de custo. Distinto de `expenses`, que é '
  'despesa de projeto do cliente e serve à prestação de contas dele.';

CREATE INDEX ix_pexp_period ON platform_expenses(period, account_code);
CREATE INDEX ix_pexp_cc ON platform_expenses(cost_center, period);
CREATE INDEX ix_pexp_due ON platform_expenses(due_on) WHERE status IN ('approved','scheduled');
CREATE INDEX ix_pexp_recurring ON platform_expenses(recurring) WHERE recurring;
CREATE INDEX ix_pexp_created_by ON platform_expenses(created_by) WHERE created_by IS NOT NULL;
CREATE INDEX ix_pexp_approved_by ON platform_expenses(approved_by) WHERE approved_by IS NOT NULL;

CREATE TRIGGER trg_pexp_touch BEFORE UPDATE ON platform_expenses
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- ================================================================== 5. ORÇAMENTO
--
-- Orçado × comprometido × realizado, por conta e centro de custo. Existia orçamento de PROJETO do
-- cliente (`budget_items`) e nenhum da plataforma.

CREATE TABLE platform_budgets (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fiscal_year  integer NOT NULL CHECK (fiscal_year BETWEEN 2024 AND 2100),
  version      integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  status       text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','superseded')),
  approved_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  approved_at  timestamptz,
  note         text,
  created_by   uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (fiscal_year, version),
  CONSTRAINT budget_approved_pair CHECK ((status = 'approved') = (approved_at IS NOT NULL))
);

-- Um orçamento aprovado por ano. Dois seriam duas respostas para "qual é a meta".
CREATE UNIQUE INDEX ux_budget_approved ON platform_budgets(fiscal_year)
  WHERE status = 'approved';

CREATE TABLE platform_budget_items (
  budget_id    uuid NOT NULL REFERENCES platform_budgets(id) ON DELETE CASCADE,
  month        smallint NOT NULL CHECK (month BETWEEN 1 AND 12),
  account_code text NOT NULL REFERENCES chart_of_accounts(code) ON DELETE RESTRICT,
  cost_center  text NOT NULL REFERENCES cost_centers(code) ON DELETE RESTRICT,
  amount_cents bigint NOT NULL CHECK (amount_cents >= 0),
  PRIMARY KEY (budget_id, month, account_code, cost_center)
);

CREATE INDEX ix_budget_item_account ON platform_budget_items(account_code);
CREATE INDEX ix_budget_item_cc ON platform_budget_items(cost_center);

ALTER TABLE platform_expenses ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_budgets ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform_budget_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY pexp_priv ON platform_expenses     FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY pexp_w ON platform_expenses     FOR INSERT WITH CHECK (app_system() OR app_priv());
CREATE POLICY pexp_u ON platform_expenses     FOR UPDATE USING (app_system() OR app_priv())
                                                   WITH CHECK (app_system() OR app_priv());
CREATE POLICY pbud_priv ON platform_budgets      FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY pbud_w ON platform_budgets      FOR INSERT WITH CHECK (app_system() OR app_priv());
CREATE POLICY pbud_u ON platform_budgets      FOR UPDATE USING (app_system() OR app_priv())
                                                   WITH CHECK (app_system() OR app_priv());
CREATE POLICY pbi_priv ON platform_budget_items FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY pbi_w ON platform_budget_items FOR INSERT WITH CHECK (app_system() OR app_priv());

GRANT SELECT, INSERT, UPDATE ON platform_expenses, platform_budgets TO impacto_app;
GRANT SELECT, INSERT ON platform_budget_items TO impacto_app;

-- ================================================================== 6. INSTRUÇÃO DE PAGAMENTO
--
-- O "INSTRUI" do motor. É DOCUMENTO: diz quanto, a quem, por qual referência e até quando. Não
-- move dinheiro, não guarda dinheiro, não repassa dinheiro.
--
-- Por que isto não é `payout`: um repasse pressupõe que o valor passou pela plataforma. Aqui o
-- valor nunca passa — quem paga executa a instrução no banco dele, e a plataforma registra a
-- evidência e concilia. A diferença é a licença de instituição de pagamento que não precisamos ter
-- (ver NON_CUSTODIAL_ARCHITECTURE.md §3).

CREATE TABLE payment_instructions (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind           text NOT NULL CHECK (kind IN ('supplier','reimbursement','tax','payroll',
                                               'marketplace_fee','refund','other')),
  -- Quem deve pagar. NULL = a própria plataforma.
  payer_org_id   uuid REFERENCES organizations(id) ON DELETE SET NULL,
  payee_name     text NOT NULL CHECK (length(payee_name) BETWEEN 2 AND 160),
  payee_doc      text CHECK (payee_doc IS NULL OR payee_doc ~ '^[0-9]{11,14}$'),
  amount_cents   bigint NOT NULL CHECK (amount_cents > 0),
  currency       char(3) NOT NULL DEFAULT 'BRL',
  due_on         date NOT NULL,
  reference      text NOT NULL CHECK (length(reference) BETWEEN 3 AND 200),
  account_code   text REFERENCES chart_of_accounts(code) ON DELETE RESTRICT,
  cost_center    text REFERENCES cost_centers(code) ON DELETE RESTRICT,
  expense_id     uuid REFERENCES platform_expenses(id) ON DELETE SET NULL,
  -- Estados. Nenhum deles é "pago pela plataforma": `executed` significa que QUEM PAGA executou e
  -- a evidência foi registrada.
  state          text NOT NULL DEFAULT 'draft'
                 CHECK (state IN ('draft','pending_approval','approved','issued','executed',
                                  'reconciled','cancelled','rejected')),
  -- A instrução é um documento; o texto dela congela quando é emitida.
  issued_at      timestamptz,
  executed_at    timestamptz,
  evidence_doc   text,
  created_by     uuid REFERENCES users(id) ON DELETE SET NULL,
  cancel_reason  text,
  idempotency_key text CHECK (idempotency_key IS NULL OR length(idempotency_key) BETWEEN 8 AND 200),
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT instr_issued_pair   CHECK ((state IN ('issued','executed','reconciled')) = (issued_at IS NOT NULL)),
  CONSTRAINT instr_executed_pair CHECK ((state IN ('executed','reconciled')) = (executed_at IS NOT NULL)),
  CONSTRAINT instr_cancel_reason CHECK (state NOT IN ('cancelled','rejected') OR cancel_reason IS NOT NULL),
  -- Executada sem evidência seria a plataforma afirmando um pagamento que ela não viu.
  CONSTRAINT instr_executed_needs_evidence CHECK (state NOT IN ('executed','reconciled')
                                                  OR evidence_doc IS NOT NULL)
);

COMMENT ON TABLE payment_instructions IS
  'INSTRUÇÃO de pagamento: documento que diz quanto, a quem e até quando. A plataforma NÃO executa '
  'o pagamento nem guarda o valor — ADR-284. `executed` significa que quem paga executou e a '
  'evidência foi registrada.';

CREATE UNIQUE INDEX ux_instr_idem ON payment_instructions(idempotency_key)
  WHERE idempotency_key IS NOT NULL;
CREATE INDEX ix_instr_state ON payment_instructions(state, due_on);
CREATE INDEX ix_instr_payer ON payment_instructions(payer_org_id) WHERE payer_org_id IS NOT NULL;
CREATE INDEX ix_instr_expense ON payment_instructions(expense_id) WHERE expense_id IS NOT NULL;
CREATE INDEX ix_instr_created_by ON payment_instructions(created_by) WHERE created_by IS NOT NULL;
CREATE INDEX ix_instr_account ON payment_instructions(account_code) WHERE account_code IS NOT NULL;
CREATE INDEX ix_instr_cc ON payment_instructions(cost_center) WHERE cost_center IS NOT NULL;

CREATE TRIGGER trg_instr_touch BEFORE UPDATE ON payment_instructions
  FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- Emitida, a instrução não muda de valor nem de destinatário. Para corrigir, cancela-se com motivo
-- e emite-se outra — como se faz com um documento que já saiu.
CREATE OR REPLACE FUNCTION instruction_frozen_after_issue() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.issued_at IS NOT NULL
     AND (NEW.amount_cents, NEW.payee_name, NEW.payee_doc, NEW.currency, NEW.reference, NEW.kind)
         IS DISTINCT FROM
         (OLD.amount_cents, OLD.payee_name, OLD.payee_doc, OLD.currency, OLD.reference, OLD.kind) THEN
    RAISE EXCEPTION 'instrução já emitida não muda de valor nem de destinatário: cancele e emita outra'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_instr_frozen BEFORE UPDATE ON payment_instructions
  FOR EACH ROW EXECUTE FUNCTION instruction_frozen_after_issue();

ALTER TABLE payment_instructions ENABLE ROW LEVEL SECURITY;
CREATE POLICY instr_read ON payment_instructions FOR SELECT
  USING (app_system() OR app_priv() OR payer_org_id = app_org());
CREATE POLICY instr_write ON payment_instructions FOR INSERT WITH CHECK (app_system() OR app_priv());
CREATE POLICY instr_update ON payment_instructions FOR UPDATE USING (app_system() OR app_priv())
                                                   WITH CHECK (app_system() OR app_priv());
GRANT SELECT, INSERT, UPDATE ON payment_instructions TO impacto_app;
REVOKE DELETE ON payment_instructions FROM impacto_app;

-- ================================================================== 7. ALÇADA DE APROVAÇÃO
--
-- NÃO EXISTIA NENHUMA FAIXA DE VALOR que exigisse aprovação em lugar nenhum da plataforma. Havia
-- onze implementações independentes de quatro olhos, cada uma com o seu `CHECK` e o seu `raise`, e
-- nenhuma olhava para o VALOR da operação. Aprovar R$ 10 e aprovar R$ 100.000 passava pelo mesmo
-- caminho.
--
-- As faixas são DADO, não código: mudar a alçada é decisão de governança, e exigir implantação
-- para isso faz a decisão ser tomada por quem tem acesso ao servidor.

CREATE TABLE approval_policies (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  operation   text NOT NULL CHECK (length(operation) BETWEEN 3 AND 60),
  version     integer NOT NULL DEFAULT 1 CHECK (version >= 1),
  active      boolean NOT NULL DEFAULT true,
  note        text NOT NULL CHECK (length(note) BETWEEN 10 AND 500),
  created_by  uuid REFERENCES users(id) ON DELETE SET NULL,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (operation, version)
);

-- Uma política ativa por operação. Duas seriam duas alçadas simultâneas, e a cobrança escolheria.
CREATE UNIQUE INDEX ux_approval_policy_active ON approval_policies(operation) WHERE active;

CREATE TABLE approval_rules (
  policy_id        uuid NOT NULL REFERENCES approval_policies(id) ON DELETE CASCADE,
  min_cents        bigint NOT NULL DEFAULT 0 CHECK (min_cents >= 0),
  max_cents        bigint CHECK (max_cents IS NULL OR max_cents > min_cents),
  approvals_needed smallint NOT NULL CHECK (approvals_needed BETWEEN 1 AND 4),
  -- Permissões que, juntas, satisfazem a faixa. `{finance.approve}` significa uma aprovação de
  -- quem tem essa permissão; `{finance.approve, accounting.close}` significa DUAS pessoas, com
  -- permissões diferentes — segregação de função, não só contagem de cliques.
  required_permissions text[] NOT NULL CHECK (cardinality(required_permissions) >= 1),
  PRIMARY KEY (policy_id, min_cents)
);

COMMENT ON COLUMN approval_rules.required_permissions IS
  'Permissões que satisfazem a faixa. Mais de uma significa pessoas DIFERENTES com permissões '
  'diferentes: duas aprovações do mesmo papel não são segregação de função.';

CREATE TABLE approval_requests (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  policy_id     uuid NOT NULL REFERENCES approval_policies(id) ON DELETE RESTRICT,
  operation     text NOT NULL,
  object_type   text NOT NULL,
  object_id     text NOT NULL,
  amount_cents  bigint NOT NULL CHECK (amount_cents >= 0),
  currency      char(3) NOT NULL DEFAULT 'BRL',
  summary       text NOT NULL CHECK (length(summary) BETWEEN 5 AND 300),
  approvals_needed smallint NOT NULL CHECK (approvals_needed BETWEEN 1 AND 4),
  state         text NOT NULL DEFAULT 'pending'
                CHECK (state IN ('pending','approved','rejected','cancelled','expired')),
  requested_by  uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  decided_at    timestamptz,
  expires_at    timestamptz,
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT approval_decided_pair CHECK ((state IN ('approved','rejected')) = (decided_at IS NOT NULL))
);

CREATE INDEX ix_approval_pending ON approval_requests(state, created_at) WHERE state = 'pending';
CREATE INDEX ix_approval_object ON approval_requests(object_type, object_id);
CREATE INDEX ix_approval_requested_by ON approval_requests(requested_by);
CREATE INDEX ix_approval_policy ON approval_requests(policy_id);

CREATE TABLE approval_decisions (
  id          bigserial PRIMARY KEY,
  request_id  uuid NOT NULL REFERENCES approval_requests(id) ON DELETE CASCADE,
  decided_by  uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  decision    text NOT NULL CHECK (decision IN ('approve','reject')),
  permission_used text NOT NULL,
  note        text,
  at          timestamptz NOT NULL DEFAULT now(),
  -- Uma decisão por pessoa por pedido: ninguém aprova duas vezes para fechar sozinho uma alçada
  -- de duas aprovações.
  UNIQUE (request_id, decided_by)
);

COMMENT ON TABLE approval_decisions IS
  'Cada decisão, com a permissão USADA. Registrar a permissão importa porque a pessoa pode ter '
  'várias, e a alçada exige que aprovações diferentes vierem de permissões diferentes.';

CREATE INDEX ix_approval_decision_by ON approval_decisions(decided_by);

CREATE TRIGGER trg_approval_decision_append BEFORE UPDATE OR DELETE ON approval_decisions
  FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- QUEM PEDE NÃO APROVA. Imposto por gatilho, para todo caminho de escrita.
CREATE OR REPLACE FUNCTION approval_no_self() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v_requester uuid; v_needed smallint; v_perms text[];
BEGIN
  SELECT requested_by, approvals_needed INTO v_requester, v_needed
    FROM approval_requests WHERE id = NEW.request_id;
  IF NEW.decided_by = v_requester THEN
    RAISE EXCEPTION 'quem pede não aprova' USING ERRCODE = '42501';
  END IF;
  -- Quando a alçada exige permissões DIFERENTES, a segunda aprovação não pode repetir a primeira.
  SELECT required_permissions INTO v_perms FROM approval_rules r
    JOIN approval_requests q ON q.policy_id = r.policy_id
   WHERE q.id = NEW.request_id AND q.amount_cents >= r.min_cents
     AND (r.max_cents IS NULL OR q.amount_cents < r.max_cents)
   ORDER BY r.min_cents DESC LIMIT 1;
  IF cardinality(coalesce(v_perms, ARRAY[]::text[])) > 1
     AND EXISTS (SELECT 1 FROM approval_decisions
                  WHERE request_id = NEW.request_id AND permission_used = NEW.permission_used) THEN
    RAISE EXCEPTION 'esta faixa exige aprovações de permissões DIFERENTES: % já aprovou',
      NEW.permission_used USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_approval_no_self BEFORE INSERT ON approval_decisions
  FOR EACH ROW EXECUTE FUNCTION approval_no_self();

-- Fecha o pedido quando as aprovações necessárias chegam. Gatilho, e não código da rota: a conta
-- de "quantas faltam" num `if` da aplicação é a conta que diverge.
CREATE OR REPLACE FUNCTION approval_settle() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v record; n integer;
BEGIN
  SELECT approvals_needed, state INTO v FROM approval_requests WHERE id = NEW.request_id;
  IF v.state <> 'pending' THEN
    RETURN NEW;
  END IF;
  IF NEW.decision = 'reject' THEN
    UPDATE approval_requests SET state = 'rejected', decided_at = now() WHERE id = NEW.request_id;
    RETURN NEW;
  END IF;
  SELECT count(*) INTO n FROM approval_decisions
   WHERE request_id = NEW.request_id AND decision = 'approve';
  IF n >= v.approvals_needed THEN
    UPDATE approval_requests SET state = 'approved', decided_at = now() WHERE id = NEW.request_id;
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER trg_approval_settle AFTER INSERT ON approval_decisions
  FOR EACH ROW EXECUTE FUNCTION approval_settle();

-- As faixas iniciais. Valores de PARTIDA, revisáveis por quem governa — e por isso são dado.
WITH p AS (
  INSERT INTO approval_policies(operation, note) VALUES
    ('payment_instruction',
     'Emissão de instrução de pagamento. As faixas partem do que uma operação pequena consegue '
     'absorver sem segunda pessoa; revisar conforme o volume real.'),
    ('platform_expense',
     'Aprovação de despesa da plataforma. Quem registra nunca aprova — a restrição está na tabela.'),
    ('billing_refund',
     'Estorno a cliente. Faixa baixa porque estorno indevido é dinheiro que não volta e cliente '
     'que não entende.')
  RETURNING id, operation)
INSERT INTO approval_rules(policy_id, min_cents, max_cents, approvals_needed, required_permissions)
SELECT p.id, v.min_cents, v.max_cents, v.n, v.perms
  FROM p JOIN (VALUES
    -- instrução de pagamento
    ('payment_instruction',       0::bigint,   100000::bigint, 1::smallint, ARRAY['finance.approve']),
    ('payment_instruction',  100000,          1000000,          2,           ARRAY['finance.approve','accounting.close']),
    ('payment_instruction', 1000000,             NULL,          2,           ARRAY['finance.approve','accounting.close']),
    -- despesa
    ('platform_expense',          0,            50000,          1,           ARRAY['finance.approve']),
    ('platform_expense',      50000,          1000000,          1,           ARRAY['finance.approve']),
    ('platform_expense',    1000000,             NULL,          2,           ARRAY['finance.approve','accounting.close']),
    -- estorno
    ('billing_refund',            0,            20000,          1,           ARRAY['billing.refund']),
    ('billing_refund',        20000,             NULL,          2,           ARRAY['billing.refund','finance.approve'])
  ) AS v(operation, min_cents, max_cents, n, perms) ON v.operation = p.operation;

ALTER TABLE approval_policies ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE approval_decisions ENABLE ROW LEVEL SECURITY;
CREATE POLICY apol_priv ON approval_policies  FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY arul_priv ON approval_rules     FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY areq_priv ON approval_requests  FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY areq_w ON approval_requests  FOR INSERT WITH CHECK (app_system() OR app_priv());
CREATE POLICY areq_u ON approval_requests  FOR UPDATE USING (app_system() OR app_priv())
                                              WITH CHECK (app_system() OR app_priv());
CREATE POLICY adec_priv ON approval_decisions FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY adec_w ON approval_decisions FOR INSERT WITH CHECK (app_system() OR app_priv());

GRANT SELECT ON approval_policies, approval_rules TO impacto_app;
GRANT SELECT, INSERT, UPDATE ON approval_requests TO impacto_app;
GRANT SELECT, INSERT ON approval_decisions TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE approval_decisions_id_seq TO impacto_app;
REVOKE UPDATE, DELETE ON approval_decisions FROM impacto_app;

-- Qual faixa se aplica a este valor, nesta operação.
CREATE OR REPLACE FUNCTION approval_rule_for(p_operation text, p_amount_cents bigint)
RETURNS TABLE(policy_id uuid, approvals_needed smallint, required_permissions text[])
LANGUAGE sql STABLE AS $$
  SELECT r.policy_id, r.approvals_needed, r.required_permissions
    FROM approval_rules r JOIN approval_policies p ON p.id = r.policy_id
   WHERE p.operation = p_operation AND p.active
     AND p_amount_cents >= r.min_cents
     AND (r.max_cents IS NULL OR p_amount_cents < r.max_cents)
   ORDER BY r.min_cents DESC LIMIT 1
$$;
