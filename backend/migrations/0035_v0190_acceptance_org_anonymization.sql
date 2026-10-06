-- v0.19.0 — o gatilho da prova de aceite passa a permitir a anonimização que a própria chave promete.
--
-- DEFEITO QUE ESTA MIGRAÇÃO CORRIGE. Dois mecanismos do mesmo schema se contradiziam:
--
--   * legal_acceptances.org_id tem ON DELETE SET NULL — a chave PROMETE que, removida a organização,
--     o aceite sobrevive sem o vínculo;
--   * acceptance_anonymize_only() recusava qualquer alteração de org_id, inclusive essa.
--
-- Resultado prático: remover uma organização que tivesse um único aceite registrado era IMPOSSÍVEL, e
-- o erro aparecia como violação de append-only — uma mensagem que leva a investigar a coisa errada.
-- Encontrado ao executar, pela primeira vez, a remoção de organização com registro em todas as áreas
-- (tests/test_v0190_lgpd_deletion.py).
--
-- A CORREÇÃO NÃO ENFRAQUECE A TRAVA. O que a prova de aceite precisa manter é QUEM aceitou, QUAL
-- versão e o HASH do texto — e nada disso muda. Passa a ser permitido exatamente um caminho a mais:
-- org_id de um valor para NULL. Transferir o aceite para OUTRA organização continua recusado, que é o
-- abuso que importa (reaproveitar a prova de aceite de uma organização em nome de outra).
CREATE OR REPLACE FUNCTION acceptance_anonymize_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.id <> OLD.id OR NEW.document_id <> OLD.document_id OR NEW.user_id <> OLD.user_id
     OR NEW.doc_key <> OLD.doc_key OR NEW.version <> OLD.version
     OR NEW.body_sha256 <> OLD.body_sha256 OR NEW.accepted_at <> OLD.accepted_at
     OR NEW.source <> OLD.source THEN
    RAISE EXCEPTION 'prova de aceite é append-only: as únicas alterações permitidas são apagar IP e '
                    'agente de usuário e desvincular a organização removida (anonimização LGPD)'
      USING ERRCODE = '23514';
  END IF;
  -- org_id só pode ser APAGADO (o SET NULL da chave), nunca trocado por outra organização.
  IF NEW.org_id IS DISTINCT FROM OLD.org_id AND NEW.org_id IS NOT NULL THEN
    RAISE EXCEPTION 'o vínculo da prova de aceite com a organização só pode ser APAGADO, nunca '
                    'trocado por outra organização' USING ERRCODE = '23514';
  END IF;
  -- A regra anterior era "NEW.ip IS NOT NULL -> recusa", o que confundia duas coisas: "não pode
  -- TROCAR o IP" com "a linha tem de ficar sem IP". Com isso, o SET NULL de org_id falhava em
  -- qualquer linha que ainda tivesse IP — ou seja, na situação normal de uma organização removida
  -- com titular ativo. Agora a condição é a que a regra sempre quis dizer: só pode APAGAR.
  IF NEW.ip IS DISTINCT FROM OLD.ip AND NEW.ip IS NOT NULL THEN
    RAISE EXCEPTION 'IP só pode ser APAGADO, nunca trocado' USING ERRCODE = '23514';
  END IF;
  IF NEW.user_agent IS DISTINCT FROM OLD.user_agent AND NEW.user_agent IS NOT NULL THEN
    RAISE EXCEPTION 'agente de usuário só pode ser APAGADO, nunca trocado' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;

COMMENT ON FUNCTION acceptance_anonymize_only IS
  'Substitui forbid_mutation() em legal_acceptances. Permite exatamente dois tipos de alteração: ip e '
  'user_agent para NULL, e org_id para NULL (o ON DELETE SET NULL da chave). A prova — titular, '
  'versão e hash do texto — continua intocável.';
