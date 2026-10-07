-- v0.23.0 — `ai_credit_ledger.ref_id` entra no catálogo de referência polimórfica
--
-- `integrity_catalog_drift()` acusou a coluna assim que ela nasceu, que é exatamente o que esse
-- relatório existe para fazer: catálogo escrito à mão envelhece, e o relatório é o que avisa.
--
-- `ai_credit_ledger.ref_type` aponta para `ai_usage` quando o lançamento é consumo — e `ai_usage`
-- tem id BIGINT, não uuid. A resolução por convenção (`ai_usage` → tabela `ai_usage`) funciona
-- porque a comparação de órfão é feita em texto nos dois lados.
INSERT INTO polymorphic_refs (source_table, type_column, id_column, note) VALUES
  ('ai_credit_ledger','ref_type','ref_id',
   'objeto que originou o lançamento de crédito; em consumo é a linha de ai_usage')
ON CONFLICT DO NOTHING;

-- O valor de tipo usado em consumo é 'ai_usage', que resolve por convenção para a própria tabela.
-- `teste` aparece em consumo criado por teste automatizado e não é referência a entidade.
INSERT INTO polymorphic_ref_exceptions (type_value, reason) VALUES
  ('teste', 'valor usado apenas por teste automatizado: o id não aponta para entidade nenhuma'),
  ('ai', 'abreviação usada em consumo de crédito de teste; o id é um contador, não uma chave')
ON CONFLICT DO NOTHING;
