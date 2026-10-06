-- v0.20.0 — a origem do aceite passa a distinguir o CADASTRO das demais telas.
--
-- Até aqui `legal_acceptances.source` aceitava 'web', 'mobile', 'api' e 'admin_import'. O aceite
-- coletado no cadastro é diferente desses quatro em um ponto que importa juridicamente: ele acontece
-- ANTES de existir sessão, no mesmo ato que cria a conta. Registrar isso como 'web' perderia a
-- informação de que a concordância foi condição de entrada, e não um aceite posterior a uma mudança
-- de termos.
ALTER TABLE legal_acceptances DROP CONSTRAINT IF EXISTS legal_acceptances_source_check;
ALTER TABLE legal_acceptances ADD CONSTRAINT legal_acceptances_source_check
  CHECK (source IN ('web','mobile','api','admin_import','signup'));

COMMENT ON COLUMN legal_acceptances.source IS
  'Onde o aceite foi coletado. ''signup'' = no ato de criar a conta (antes de haver sessão); os '
  'demais = aceite posterior, em tela com sessão, por mudança de versão.';
