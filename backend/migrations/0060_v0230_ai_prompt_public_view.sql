-- v0.23.0 — QUAL PROMPT RODOU É PÚBLICO; O TEXTO DELE NÃO
--
-- A RLS de `ai_prompts` é `app_system() OR app_priv()`, e isso está certo: o TEXTO da instrução é
-- parte do produto, e expô-lo entrega a receita. Mas a organização tem direito de saber QUAL
-- instrução, em que versão e em que faixa de risco, processou o dado dela — é a diferença entre
-- "confie em nós" e "confira".
--
-- RLS é por LINHA e o que precisa ser protegido aqui é uma COLUNA. A separação é uma visão com as
-- colunas públicas e privilégio próprio. Sem `security_invoker`, a visão roda com o privilégio do
-- dono e não reaplica a RLS da tabela — que é exatamente o efeito desejado, e é por isso que a
-- visão NÃO expõe `system_text`.

CREATE OR REPLACE VIEW ai_prompt_public AS
  SELECT p.prompt_key, p.version, p.tier, p.active,
         p.output_schema IS NOT NULL AS has_schema,
         length(p.system_text) AS system_chars,
         p.note, p.created_at
    FROM ai_prompts p;

COMMENT ON VIEW ai_prompt_public IS
  'Metadados do prompt sem o texto da instrução. Serve `GET /v1/ai/policies`: a organização vê '
  'qual prompt e qual versão processaram o dado dela, sem receber a instrução em si.';

GRANT SELECT ON ai_prompt_public TO impacto_app;
