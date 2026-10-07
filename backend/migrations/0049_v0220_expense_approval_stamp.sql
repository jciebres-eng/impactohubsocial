-- v0.22.0 — a aprovação de despesa passa a ter DATA.
--
-- `platform_expenses` guardava QUEM aprovou e não QUANDO. Aprovação sem data não responde a
-- pergunta que uma auditoria faz primeiro: a despesa foi aprovada antes ou depois de ser paga?
-- Sem o carimbo, "aprovada" e "paga no mesmo dia" são indistinguíveis de "paga e aprovada depois".
ALTER TABLE platform_expenses ADD COLUMN IF NOT EXISTS approved_at timestamptz;

-- Os dois campos andam juntos: um sem o outro é um registro pela metade.
ALTER TABLE platform_expenses DROP CONSTRAINT IF EXISTS expense_approval_is_complete;
ALTER TABLE platform_expenses ADD CONSTRAINT expense_approval_is_complete
  CHECK ((approved_by IS NULL) = (approved_at IS NULL));

-- E o estado tem de acompanhar: não existe despesa aprovada, agendada ou paga sem aprovação.
ALTER TABLE platform_expenses DROP CONSTRAINT IF EXISTS expense_state_needs_approval;
ALTER TABLE platform_expenses ADD CONSTRAINT expense_state_needs_approval
  CHECK (status NOT IN ('approved', 'scheduled', 'paid') OR approved_by IS NOT NULL);

-- Pagamento exige a data em que saiu o caixa: é ela que liga a despesa à conciliação.
ALTER TABLE platform_expenses DROP CONSTRAINT IF EXISTS expense_paid_needs_date;
ALTER TABLE platform_expenses ADD CONSTRAINT expense_paid_needs_date
  CHECK (status <> 'paid' OR paid_on IS NOT NULL);

CREATE INDEX IF NOT EXISTS ix_platform_expenses_pending
  ON platform_expenses (status, due_on) WHERE status IN ('registered', 'approved', 'scheduled');
