-- v0.23.0 — O PROCESSO LÊ O TEXTO DO PROMPT; A SESSÃO DO CLIENTE NÃO
--
-- O defeito que esta migração corrige foi encontrado pelo teste, na primeira execução: a RLS de
-- `ai_prompts` é `app_system() OR app_priv()`, e o gateway lê o prompt DENTRO da transação da
-- organização (`ctx.tx()`), porque é lá que a cota, o orçamento e o registro de uso acontecem.
-- Resultado: toda rota de IA devolvia 500.
--
-- As duas saídas erradas e por que não foram tomadas:
--
--   * Abrir a RLS de `ai_prompts` para sessão autenticada entregaria o TEXTO da instrução a
--     qualquer cliente. O texto é parte do produto.
--   * Fazer o gateway abrir contexto de sistema alargaria a lista de módulos autorizados a ignorar
--     a RLS — e o gateway é o módulo que mais toca dado de cliente.
--
-- A saída certa é a mesma que `app_record_value()` já usa nesta base: função SECURITY DEFINER com
-- escopo exato. Ela devolve UMA versão ativa de UMA chave, e nada mais. O processo recebe o texto
-- para montar a chamada; a sessão não consegue consultar a tabela.

CREATE OR REPLACE FUNCTION ai_active_prompt(p_key text)
RETURNS TABLE(id bigint, prompt_key text, version int, tier smallint, system_text text,
              output_schema jsonb, note text, tier_label text, max_input_chars int,
              max_output_tokens int, allow_external boolean, requires_schema boolean,
              requires_human_review boolean)
LANGUAGE sql SECURITY DEFINER STABLE AS $$
  SELECT p.id, p.prompt_key, p.version, p.tier, p.system_text, p.output_schema, p.note,
         m.label, m.max_input_chars, m.max_output_tokens, m.allow_external,
         m.requires_schema, m.requires_human_review
    FROM ai_prompts p JOIN ai_model_policies m ON m.tier = p.tier
   WHERE p.prompt_key = p_key AND p.active
$$;

COMMENT ON FUNCTION ai_active_prompt(text) IS
  'Devolve a versão ativa de um prompt, com a política da faixa. SECURITY DEFINER porque o '
  'processo precisa do texto da instrução e a sessão do cliente não pode consultar `ai_prompts`. '
  'Escopo exato: uma chave, a versão ativa, nada mais.';

REVOKE ALL ON FUNCTION ai_active_prompt(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION ai_active_prompt(text) TO impacto_app;

-- ── ORÇAMENTO É DA ORGANIZAÇÃO ───────────────────────────────────────────────────────────────────
--
-- A política de escrita de `ai_budgets` nasceu como `app_system()`, o que tornava a rota
-- `PUT /v1/ai/budget` impossível: a organização não conseguia definir o próprio limite. Quem paga
-- decide quanto quer gastar — a plataforma não escolhe isso por ela.
DROP POLICY IF EXISTS aibudget_write ON ai_budgets;
CREATE POLICY aibudget_write ON ai_budgets FOR ALL
  USING (app_system() OR org_id = app_org())
  WITH CHECK (app_system() OR org_id = app_org());
