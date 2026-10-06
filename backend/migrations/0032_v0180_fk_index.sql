-- 0032_v0180_fk_index.sql — ACHADO do relatório de integridade desta rodada, corrigido.
--
-- `scripts/db_integrity_report.py` aponta uma única chave estrangeira QUENTE sem índice depois das
-- migrações 0025–0031: `materiality_assessments.project_id`. Quente significa coluna de inquilino ou
-- de pai percorrido — aqui é o pai: apagar um projeto faz o banco varrer a tabela inteira para
-- resolver o ON DELETE, e a listagem de materialidade por projeto faz o mesmo.
--
-- As demais chaves sem índice continuam sem, pela regra da 0015: chave para `users`
-- (`declared_by`, `reviewed_by`, `opened_by`…) não entra, porque a aplicação não lista "tudo que a
-- pessoa X criou", e índice que ninguém usa é custo de escrita sem retorno.
CREATE INDEX IF NOT EXISTS ix_fk_materiality_assessments_project_id
  ON materiality_assessments(project_id);
