-- v0.24.0 — Onde o `digest()` mora num banco gerenciado.
--
-- O Supabase (e outros PostgreSQL gerenciados) instala extensões na schema `extensions`, não em
-- `public`. Toda função que chama `digest()` sem qualificar a schema resolve o nome pelo
-- `search_path` em vigor — e as três funções de cadeia (`chain_audit`, `chain_ledger`, `chain_trust`)
-- fixam `search_path = public, pg_temp` de propósito, por serem SECURITY DEFINER. Num banco
-- gerenciado elas falhavam com "function digest(text, unknown) does not exist" no primeiro INSERT
-- em audit_events: a plataforma não subia.
--
-- A versão desta migração recebida de fora cobria CINCO funções. São NOVE as que chamam digest():
-- ficavam de fora trust_verify, legal_doc_hash, chain_value_event e value_verify. Um teste varre o
-- catálogo e exige que toda função cujo corpo cita digest( tenha `extensions` no search_path — para
-- que a próxima função nova não repita o esquecimento.
--
-- Num PostgreSQL comum, onde pgcrypto já está em `public` (migração 0001), nada muda de
-- comportamento: a schema `extensions` fica vazia e `public` continua primeiro na lista.
CREATE SCHEMA IF NOT EXISTS extensions;
CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA extensions;
GRANT USAGE ON SCHEMA extensions TO impacto_app;

-- gatilhos de cadeia (SECURITY DEFINER; já fixavam search_path sem `extensions`)
ALTER FUNCTION public.chain_audit()       SET search_path = public, extensions, pg_temp;
ALTER FUNCTION public.chain_ledger()      SET search_path = public, extensions, pg_temp;
ALTER FUNCTION public.chain_trust()       SET search_path = public, extensions, pg_temp;
ALTER FUNCTION public.chain_value_event() SET search_path = public, extensions, pg_temp;
-- verificações de cadeia e hash de documento legal (não fixavam search_path: herdavam o da sessão)
ALTER FUNCTION public.audit_verify(uuid)        SET search_path = public, extensions, pg_temp;
ALTER FUNCTION public.ledger_verify(uuid)       SET search_path = public, extensions, pg_temp;
ALTER FUNCTION public.trust_verify(text, uuid)  SET search_path = public, extensions, pg_temp;
ALTER FUNCTION public.value_verify(uuid)        SET search_path = public, extensions, pg_temp;
ALTER FUNCTION public.legal_doc_hash()          SET search_path = public, extensions, pg_temp;
