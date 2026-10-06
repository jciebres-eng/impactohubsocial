-- 0024_v0170_privacy_hardening.sql — o conflito entre "append-only" e "direito de eliminação"
--
-- O PROBLEMA, DESCOBERTO NA REVISÃO LGPD DESTA RODADA
--
-- `legal_acceptances` é append-only, porque prova de aceite que pode ser editada não prova nada. Mas a
-- linha guarda IP e agente de usuário, que são dado pessoal, e a exclusão de conta anonimiza o titular.
-- Com `forbid_mutation()`, a anonimização seria RECUSADA pelo gatilho: o produto teria de escolher entre
-- a prova e o direito do titular.
--
-- A escolha errada seria afrouxar o append-only. A certa é estreitá-lo: a ÚNICA alteração permitida
-- passa a ser apagar IP e agente de usuário (para NULL). Tudo o mais continua recusado, e a prova
-- sobrevive sem eles — ela é o documento, a versão, o sha256 do texto e o titular pseudonimizado.
--
-- Mesmo raciocínio para `billing_events.payload`: o corpo que o provedor manda pode conter nome e
-- e-mail do pagador. O evento precisa ser guardado para sempre (idempotência e reconciliação); o corpo
-- dele, não. Depois de 18 meses o corpo é esvaziado e o evento fica.

CREATE FUNCTION acceptance_anonymize_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.id <> OLD.id OR NEW.document_id <> OLD.document_id OR NEW.user_id <> OLD.user_id
     OR NEW.doc_key <> OLD.doc_key OR NEW.version <> OLD.version
     OR NEW.body_sha256 <> OLD.body_sha256 OR NEW.accepted_at <> OLD.accepted_at
     OR NEW.source <> OLD.source OR NEW.org_id IS DISTINCT FROM OLD.org_id THEN
    RAISE EXCEPTION 'prova de aceite é append-only: a única alteração permitida é apagar IP e agente '
                    'de usuário (anonimização LGPD)' USING ERRCODE = '23514';
  END IF;
  IF NEW.ip IS NOT NULL OR NEW.user_agent IS NOT NULL THEN
    RAISE EXCEPTION 'IP e agente de usuário só podem ser APAGADOS, nunca trocados'
      USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
COMMENT ON FUNCTION acceptance_anonymize_only IS
  'Substitui forbid_mutation() em legal_acceptances. Permite exatamente um tipo de alteração: ip e '
  'user_agent para NULL. A prova continua válida sem eles.';

DROP TRIGGER trg_acceptance_append ON legal_acceptances;
CREATE TRIGGER trg_acceptance_append BEFORE UPDATE ON legal_acceptances
  FOR EACH ROW EXECUTE FUNCTION acceptance_anonymize_only();

-- A anonimização roda no contexto do próprio titular (rota de exclusão de conta), então precisa de
-- UPDATE na própria linha — e em mais nenhuma.
CREATE POLICY legal_acc_anonymize ON legal_acceptances FOR UPDATE
  USING (user_id = app_uid() OR app_priv() OR app_system())
  WITH CHECK (user_id = app_uid() OR app_priv() OR app_system());
GRANT UPDATE (ip, user_agent) ON legal_acceptances TO impacto_app;

COMMENT ON COLUMN legal_acceptances.ip IS
  'Dado pessoal. Apagado na exclusão de conta e pela retenção; a prova de aceite não depende dele.';

-- Retenção do corpo do webhook: o evento fica, o conteúdo sai.
COMMENT ON COLUMN billing_events.payload IS
  'Corpo bruto do provedor. Pode conter nome e e-mail do pagador, então é ESVAZIADO após 18 meses '
  'pela retenção (jobs.retention). O evento em si é guardado para sempre, por idempotência.';

-- `db_integrity_report.py` apontou esta FK como "quente sem índice": a administração lista aceite por
-- organização, e sem o índice a consulta varre a tabela inteira. A regra da 0015 vale aqui — índice só
-- em coluna de inquilino ou de pai percorrido, não em toda FK.
CREATE INDEX ix_legal_acc_org ON legal_acceptances(org_id) WHERE org_id IS NOT NULL;
