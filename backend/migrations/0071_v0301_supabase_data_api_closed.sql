-- 0071 — v0.30.1: fecha a API de dados do Supabase para os papéis públicos (anon/authenticated).
--
-- POR QUE EXISTE. A plataforma NÃO usa a API REST/GraphQL automática do Supabase (PostgREST): o
-- acesso ao banco é só do backend, como `impacto_app`, com RLS baseada em `app_*()`. Mas num
-- projeto Supabase o esquema `public` vem com PRIVILÉGIOS PADRÃO para `anon` e `authenticated`
-- (as chaves "publishable"/anon do projeto). Toda tabela e visão criada pelas migrações herdava
-- SELECT/INSERT/UPDATE/DELETE para esses papéis.
--
-- O que segurava: as tabelas têm RLS e as políticas dependem de `app_*()`, que para esses papéis
-- devolvem falso — nenhuma linha visível. O que NÃO segurava (apontado pelo Security Advisor do
-- Supabase em 2026-10-09):
--   * `schema_migrations` — sem RLS, legível e GRAVÁVEL pela API pública;
--   * `project_baselines_without_source` e `ai_prompt_public` — visões sem `security_invoker`
--     (rodam com o privilégio do dono e NÃO reaplicam a RLS da tabela de origem), legíveis por
--     qualquer pessoa com a chave anon.
--
-- O QUE FAZ. Revoga tudo de `anon` e `authenticated` no esquema `public` (tabelas, visões,
-- sequências, funções) e remove os privilégios padrão para objetos futuros criados pelo dono das
-- migrações. Liga RLS em `schema_migrations` (o dono continua lendo e gravando: RLS não se aplica
-- ao dono sem FORCE). As visões continuam SEM `security_invoker` — o efeito é deliberado (0025,
-- 0060) e o acesso a elas fica restrito a `impacto_app`, que já tinha GRANT próprio.
--
-- Fora do Supabase (Compose, CI, outro PostgreSQL) os papéis `anon`/`authenticated` não existem:
-- o bloco não faz nada.

DO $$
DECLARE
  papel text;
BEGIN
  FOREACH papel IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM %I', papel);
      EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', papel);
      EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I', papel);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM %I', papel);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', papel);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I', papel);
    END IF;
  END LOOP;
END $$;

-- `impacto_app` LÊ esta tabela (app.py confere na inicialização se todas as migrações foram
-- aplicadas; internal_routes conta as migrações). Com RLS ligada e sem política, a leitura
-- devolveria ZERO linhas e a aplicação concluiria que nada foi migrado. Por isso a política de
-- leitura vem junto, e só para `impacto_app` — escrita continua exclusiva do dono.
ALTER TABLE schema_migrations ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS schema_migrations_read_app ON schema_migrations;
CREATE POLICY schema_migrations_read_app ON schema_migrations FOR SELECT TO impacto_app USING (true);

COMMENT ON TABLE schema_migrations IS
  'Controle de migrações (runner forward-only). RLS ligada: impacto_app só lê; só o dono do esquema '
  'grava; nenhum papel da API pública do Supabase tem acesso (0071).';
