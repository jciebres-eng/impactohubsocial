-- v0.23.0 — MOTOR DE INTEGRIDADE RELACIONAL (ÓRFÃOS E REFERÊNCIAS POLIMÓRFICAS)
--
-- O QUE ESTA MIGRAÇÃO CORRIGE
--
-- `scripts/db_integrity_report.py` publicava esta linha como resultado de verificação:
--
--     "orphan_rows_check": "SELECT 'nenhuma verificação de órfão aplicável:
--                            toda referência é FK declarada'"
--
-- Era uma STRING LITERAL. Não consultava nada, e a afirmação é falsa: existem 25 colunas de
-- referência polimórfica no banco — `audit_events.object_id`, `ledger_entries.ref_id`,
-- `value_events.subject_id`, `approval_requests.object_id`, `accounting_entries.source_id` e
-- outras 20 — e NENHUMA tem chave estrangeira, porque uma referência que aponta para tabelas
-- diferentes conforme o tipo não pode ter FK. São exatamente as referências que precisam de
-- verificação, e eram as únicas que não tinham.
--
-- COMO O MOTOR FUNCIONA
--
-- Não há enumeração manual de tipo → tabela. Há três peças:
--   1. `polymorphic_refs`: o catálogo das TRIPLAS (tabela, coluna de tipo, coluna de id). São 25.
--   2. Convenção de resolução: o valor de tipo `project` resolve para a tabela `projects` (plural),
--      `indicator_value` para `indicator_values`. A convenção é conferida contra o catálogo do
--      PostgreSQL — se a tabela não existir, o tipo entra como NÃO RESOLVIDO em vez de ser pulado.
--   3. `polymorphic_ref_exceptions`: valores de tipo que NÃO são referência a entidade, cada um com
--      motivo escrito. `kill_switch`, por exemplo: ali `object_id` guarda o nome do escopo.
--
-- O resultado é um verificador que fica mais forte conforme os dados aparecem, e que acusa quando
-- o catálogo fica atrás do código — que é o modo como esta classe de verificação costuma morrer.

CREATE TABLE IF NOT EXISTS polymorphic_refs (
  source_table text NOT NULL,
  type_column  text NOT NULL,
  id_column    text NOT NULL,
  note         text NOT NULL,
  PRIMARY KEY (source_table, type_column, id_column)
);

CREATE TABLE IF NOT EXISTS polymorphic_ref_exceptions (
  type_value text PRIMARY KEY,
  reason     text NOT NULL CHECK (length(btrim(reason)) >= 30)
);

INSERT INTO polymorphic_refs (source_table, type_column, id_column, note) VALUES
  ('accounting_entries','source_kind','source_id','origem do lançamento contábil'),
  ('approval_requests','object_type','object_id','objeto que aguarda aprovação'),
  ('audit_events','object_type','object_id','recurso tocado pelo evento auditado'),
  ('claims','subject_type','subject_id','sujeito da reivindicação'),
  ('content_history','object_type','object_id','objeto editorial versionado'),
  ('domain_events','subject_type','subject_id','sujeito do evento de domínio'),
  ('feed_feedback','target_type','target_id','item do feed avaliado'),
  ('impact_tags','subject_type','subject_id','sujeito marcado'),
  ('integration_events','event_type','entity_id','entidade tocada pela integração'),
  ('kb_events','target_type','target_id','item da central de conhecimento'),
  ('kb_feedback','target_type','target_id','item avaliado na central'),
  ('ledger_entries','ref_type','ref_id','objeto que originou o lançamento do Impact Ledger'),
  ('messages','ref_type','ref_id','objeto citado na conversa'),
  ('notifications','ref_type','ref_id','objeto que originou a notificação'),
  ('professional_reviews','subject_type','subject_id','objeto sob parecer profissional'),
  ('recommendations','subject_type','subject_id','objeto recomendado'),
  ('reports','target_type','target_id','alvo da denúncia'),
  ('seal_awards','scope','subject_id','sujeito do selo; a coluna de tipo chama-se `scope`'),
  ('seal_evaluations','scope','subject_id','sujeito avaliado; a coluna de tipo chama-se `scope`'),
  ('signature_challenges','subject_type','subject_id','objeto a assinar'),
  ('signatures','subject_type','subject_id','objeto assinado'),
  ('trust_events','subject_type','subject_id','sujeito do evento de confiança'),
  ('value_events','subject_type','subject_id','sujeito do evento de valor'),
  ('verifiable_records','subject_type','subject_id','objeto do registro verificável'),
  ('responsibility_assignments','scope','subject_id','objeto com responsável atribuído; a coluna de tipo chama-se `scope`')
ON CONFLICT DO NOTHING;

INSERT INTO polymorphic_ref_exceptions (type_value, reason) VALUES
  ('kill_switch', 'o id guarda o NOME DO ESCOPO do interruptor (mutations, logins, ...), não o id de uma entidade'),
  ('manual', 'lançamento contábil digitado por pessoa: não tem documento de origem no banco, e é por isso que exige aprovação'),
  ('platform', 'o sujeito é a própria plataforma, que não é uma linha de `organizations` em todos os ambientes'),
  ('period', 'o id é a competência contábil (AAAA-MM), não a chave de uma linha')
ON CONFLICT DO NOTHING;

-- Resolve o valor de tipo para uma TABELA REAL, conferindo contra o catálogo do PostgreSQL.
CREATE OR REPLACE FUNCTION integrity_target_table(p_type text) RETURNS text LANGUAGE plpgsql STABLE AS $$
DECLARE candidatos text[]; alvo text;
BEGIN
  IF p_type IS NULL OR btrim(p_type) = '' THEN RETURN NULL; END IF;
  IF EXISTS (SELECT 1 FROM polymorphic_ref_exceptions e WHERE e.type_value = p_type) THEN RETURN NULL; END IF;
  -- Plural simples primeiro, depois o nome como veio. Nada de heurística esperta: se nenhuma das
  -- duas existir, o tipo é relatado como não resolvido e alguém decide o que fazer.
  candidatos := ARRAY[p_type || 's', p_type, regexp_replace(p_type, 'y$', 'ies')];
  FOREACH alvo IN ARRAY candidatos LOOP
    IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relname = alvo AND c.relkind = 'r')
       AND EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = alvo AND column_name = 'id') THEN
      RETURN alvo;
    END IF;
  END LOOP;
  RETURN NULL;
END $$;

-- Conta os órfãos de verdade: linha cujo id aponta para nada na tabela que o tipo indica.
CREATE OR REPLACE FUNCTION integrity_orphans()
RETURNS TABLE(source_table text, type_column text, id_column text, type_value text,
              target_table text, rows_checked bigint, orphans bigint)
LANGUAGE plpgsql STABLE AS $$
DECLARE r record; t record; alvo text; n bigint; o bigint;
BEGIN
  FOR r IN SELECT * FROM polymorphic_refs ORDER BY source_table, id_column LOOP
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name = r.source_table
                      AND column_name = r.type_column) THEN
      CONTINUE;   -- coluna renomeada: `integrity_catalog_drift()` acusa
    END IF;
    FOR t IN EXECUTE format(
        'SELECT %I::text AS tipo, count(*) AS n FROM %I WHERE %I IS NOT NULL AND %I IS NOT NULL GROUP BY 1',
        r.type_column, r.source_table, r.type_column, r.id_column) LOOP
      alvo := integrity_target_table(t.tipo);
      IF alvo IS NULL THEN CONTINUE; END IF;
      EXECUTE format(
        'SELECT count(*) FROM %I s WHERE s.%I::text = $1 AND s.%I IS NOT NULL'
        '   AND NOT EXISTS (SELECT 1 FROM %I x WHERE x.id::text = s.%I::text)',
        r.source_table, r.type_column, r.id_column, alvo, r.id_column)
        INTO o USING t.tipo;
      n := t.n;
      RETURN QUERY SELECT r.source_table, r.type_column, r.id_column, t.tipo, alvo, n, o;
    END LOOP;
  END LOOP;
END $$;

-- Valores de tipo presentes nos DADOS que o motor não consegue resolver nem tem exceção escrita.
-- É este relatório que impede o catálogo de ficar atrás do código em silêncio.
CREATE OR REPLACE FUNCTION integrity_unresolved_refs()
RETURNS TABLE(source_table text, type_column text, type_value text, rows_affected bigint)
LANGUAGE plpgsql STABLE AS $$
DECLARE r record; t record;
BEGIN
  FOR r IN SELECT * FROM polymorphic_refs ORDER BY source_table LOOP
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema='public' AND table_name = r.source_table
                      AND column_name = r.type_column) THEN
      CONTINUE;
    END IF;
    FOR t IN EXECUTE format(
        'SELECT %I::text AS tipo, count(*) AS n FROM %I WHERE %I IS NOT NULL AND %I IS NOT NULL GROUP BY 1',
        r.type_column, r.source_table, r.type_column, r.id_column) LOOP
      IF integrity_target_table(t.tipo) IS NULL
         AND NOT EXISTS (SELECT 1 FROM polymorphic_ref_exceptions e WHERE e.type_value = t.tipo) THEN
        RETURN QUERY SELECT r.source_table, r.type_column, t.tipo, t.n;
      END IF;
    END LOOP;
  END LOOP;
END $$;

-- Deriva do catálogo do PostgreSQL as colunas polimórficas que o catálogo do motor NÃO cobre.
-- Catálogo escrito à mão envelhece; este relatório é o que avisa.
CREATE OR REPLACE FUNCTION integrity_catalog_drift()
RETURNS TABLE(source_table text, id_column text, situation text) LANGUAGE sql STABLE AS $$
  -- 1. coluna de referência polimórfica, sem FK, que ninguém catalogou
  SELECT c.table_name::text, c.column_name::text, 'fora do catálogo'::text
    FROM information_schema.columns c
   WHERE c.table_schema = 'public'
     AND c.column_name IN ('object_id','ref_id','subject_id','source_id','target_id','entity_id','resource_id')
     AND NOT EXISTS (SELECT 1 FROM information_schema.key_column_usage k
                       JOIN information_schema.table_constraints t
                         ON t.constraint_name = k.constraint_name AND t.constraint_type = 'FOREIGN KEY'
                      WHERE k.table_name = c.table_name AND k.column_name = c.column_name)
     AND NOT EXISTS (SELECT 1 FROM polymorphic_refs p
                      WHERE p.source_table = c.table_name AND p.id_column = c.column_name)
  UNION ALL
  -- 2. entrada catalogada cuja tabela ou coluna já não existe
  SELECT p.source_table, p.id_column, 'catalogado e inexistente'::text
    FROM polymorphic_refs p
   WHERE NOT EXISTS (SELECT 1 FROM information_schema.columns c
                      WHERE c.table_schema='public' AND c.table_name = p.source_table
                        AND c.column_name = p.id_column)
      OR NOT EXISTS (SELECT 1 FROM information_schema.columns c
                      WHERE c.table_schema='public' AND c.table_name = p.source_table
                        AND c.column_name = p.type_column)
  ORDER BY 1, 2;
$$;

ALTER TABLE polymorphic_refs ENABLE ROW LEVEL SECURITY;
ALTER TABLE polymorphic_ref_exceptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY polyref_read ON polymorphic_refs FOR SELECT USING (app_system() OR app_priv());
CREATE POLICY polyexc_read ON polymorphic_ref_exceptions FOR SELECT USING (app_system() OR app_priv());

-- Sem gatilho de imutabilidade aqui, de propósito: o controle é o PRIVILÉGIO. A aplicação recebe
-- só SELECT, então o catálogo muda apenas por migração — que é versionada, tem sha256 por arquivo e
-- é forward-only. Um gatilho seria uma segunda trava mais fraca que a primeira.
GRANT SELECT ON polymorphic_refs, polymorphic_ref_exceptions TO impacto_app;
