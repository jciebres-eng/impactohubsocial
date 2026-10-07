-- v0.22.0 — a decisão de aprovação PASSA A VALER no objeto aprovado.
--
-- O DEFEITO (encontrado por auditoria independente, não por mim)
--
-- `POST /v1/financeiro/expenses` criava a despesa em `registered` e abria o pedido de aprovação.
-- `POST /v1/aprovacoes/{id}/decide` gravava a decisão e o gatilho fechava o PEDIDO como `approved`.
-- E ninguém escrevia de volta na DESPESA. Não existia um único `UPDATE platform_expenses` em todo
-- o código de aplicação.
--
-- O resultado era uma tela que mentia com números certos: duas despesas de R$ 99,00 registradas e
-- aprovadas, e o painel Financeiro mostrando "A pagar R$ 0,00" ao lado de "Despesa total
-- R$ 198,00" — porque `payable` soma `status IN ('approved','scheduled')` e nada nunca chegava
-- nesses estados. Em cascata: a posição líquida da tesouraria SUPERESTIMAVA o caixa pelo total das
-- despesas aprovadas, e a conferência de "despesa paga sem lançamento" da conciliação apontava
-- para um estado (`paid`) que era inalcançável.
--
-- POR QUE NO GATILHO E NÃO NO HANDLER
--
-- Porque o handler é um caminho; o gatilho é o único. A decisão pode chegar pela rota, por um
-- processo de fechamento futuro, por correção no console do banco. Escrever no handler faria a
-- segunda via nascer errada — e foi assim que este defeito existiu: a decisão tinha um caminho e o
-- objeto tinha outro.

CREATE OR REPLACE FUNCTION approval_applies_to_object() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  v_aprovador uuid;
BEGIN
  IF NEW.state = OLD.state THEN
    RETURN NEW;
  END IF;

  -- Quem aprovou: a decisão favorável mais recente. O gatilho `approval_no_self` já garante que
  -- não é quem pediu, então a restrição `expense_four_eyes` não pode ser violada por aqui.
  SELECT d.decided_by INTO v_aprovador
    FROM approval_decisions d
   WHERE d.request_id = NEW.id AND d.decision = 'approve'
   ORDER BY d.id DESC LIMIT 1;

  IF NEW.state = 'approved' THEN
    IF NEW.object_type = 'platform_expense' THEN
      UPDATE platform_expenses
         SET status = 'approved', approved_by = v_aprovador, approved_at = now()
       WHERE id = NEW.object_id::uuid AND status = 'registered';
    ELSIF NEW.object_type = 'payment_instruction' THEN
      -- A instrução sai de "aguardando aprovação" para "aprovada". Sem isto, a tela oferecia
      -- "Emitir" num estado que `require_approved()` recusa por construção.
      UPDATE payment_instructions
         SET state = 'approved'
       WHERE id = NEW.object_id::uuid AND state IN ('draft', 'pending_approval');
    END IF;

  ELSIF NEW.state = 'rejected' THEN
    IF NEW.object_type = 'platform_expense' THEN
      -- Recusada não volta a "registered": ficaria indistinguível de uma que ninguém olhou.
      UPDATE platform_expenses SET status = 'cancelled'
       WHERE id = NEW.object_id::uuid AND status = 'registered';
    ELSIF NEW.object_type = 'payment_instruction' THEN
      UPDATE payment_instructions
         SET state = 'rejected',
             cancel_reason = coalesce(
               (SELECT d.note FROM approval_decisions d
                 WHERE d.request_id = NEW.id AND d.decision = 'reject'
                 ORDER BY d.id DESC LIMIT 1),
               'recusada na alçada')
       WHERE id = NEW.object_id::uuid AND state IN ('draft', 'pending_approval', 'approved');
    END IF;
  END IF;

  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_approval_applies ON approval_requests;
CREATE TRIGGER trg_approval_applies AFTER UPDATE OF state ON approval_requests
  FOR EACH ROW EXECUTE FUNCTION approval_applies_to_object();

-- A nota do fechamento de competência era aceita pela rota e descartada: a coluna existia e
-- ninguém escrevia nela.
COMMENT ON COLUMN accounting_periods.note IS
  'Justificativa do fechamento, escrita por close_period(). Até a v0.22.0 a rota aceitava a nota e '
  'só a registrava em audit_events — a coluna ficava nula.';

-- A matriz papel → permissão era legível SEM restrição pelo papel da aplicação
-- (`USING (true)`), enquanto a rota que a expõe exige `admin.users.read`. Nenhuma rota de cliente a
-- lê hoje; é defesa em profundidade que estava faltando, não vazamento ativo.
DROP POLICY IF EXISTS staffperm_read ON staff_permissions;
CREATE POLICY staffperm_read ON staff_permissions FOR SELECT USING (app_system() OR app_priv());
DROP POLICY IF EXISTS permcat_read ON permission_catalog;
CREATE POLICY permcat_read ON permission_catalog FOR SELECT USING (app_system() OR app_priv());
