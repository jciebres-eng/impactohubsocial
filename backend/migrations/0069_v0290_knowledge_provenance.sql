-- 0069 — v0.29.0: proveniência, direitos de uso, retirada e fila editorial da camada de conhecimento (ADR-353..357).
--
-- O que a Central já tinha (0009): quatro olhos, versão imutável, origem oficial/educacional/terceiros, DEMO, fonte e data
-- para conteúdo regulatório, visibilidade por perfil. O que faltava e esta migração acrescenta, aplicado PELO BANCO:
--   1. registro mestre de FONTES (kb_sources): classe O/A/V/H/D, jurisdição, vigência, licença, DIREITOS DE USO por operação
--      (guardar, indexar, citar trecho, resumir, traduzir, gerar embedding, enviar a provedor externo, treinar, redistribuir —
--      cada um 'allowed' | 'denied' | 'unknown'; desconhecido NÃO é permitido), hash do que foi preservado, estado de verificação;
--   2. CITAÇÕES (kb_citations): versão de conteúdo → fonte → localizador (artigo/seção) → trecho com hash; append-only;
--   3. RETIRADA (status 'retracted') com motivo, ator e data: terminal; sai da busca, do assistente e do sitemap; reativar = nova versão;
--   4. FILA EDITORIAL (kb_work_items): busca sem resultado, assistente sem base, "não ajudou", conteúdo vencido, relato de
--      informação incorreta e revisão de fonte viram itens de trabalho rastreáveis (dedupe por chave), nunca só um contador.
-- Nada aqui afirma vigência ou conformidade: a classe e a verificação são registradas por pessoa, com data, e vencem.

-- ============================================================================ 1. fontes
CREATE TABLE kb_sources (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key             text NOT NULL UNIQUE CHECK (key ~ '^[a-z0-9][a-z0-9.-]{2,80}$'),
  title           text NOT NULL CHECK (length(title) BETWEEN 3 AND 300),
  publisher       text CHECK (length(publisher) <= 200),                     -- órgão/autor/editora
  url             text CHECK (url IS NULL OR url ~ '^https?://'),
  effective_url   text CHECK (effective_url IS NULL OR effective_url ~ '^https?://'),   -- URL após redirecionamento, se houver
  source_type     text NOT NULL CHECK (source_type IN ('constitution','law','decree','resolution','guidance','jurisprudence','standard',
                                                        'literature','contract','internal_evidence','report','dataset','other')),
  klass           text NOT NULL CHECK (klass IN ('O','A','V','H','D')),     -- taxonomia editorial O/A/V/H/D (knowledge-base/MASTER §4)
  jurisdiction    text CHECK (length(jurisdiction) <= 80),                   -- BR, BR-MT, BR-MT-LucasDoRioVerde, UE, …
  language        text NOT NULL DEFAULT 'pt-BR' CHECK (length(language) BETWEEN 2 AND 10),
  published_on    date,
  consulted_on    date,
  effective_from  date,
  effective_until date,
  CHECK (effective_until IS NULL OR effective_from IS NULL OR effective_until >= effective_from),
  license         text CHECK (length(license) <= 200),                       -- texto da licença/base de direitos; NULL = desconhecida
  rights          jsonb NOT NULL DEFAULT '{}'::jsonb,                        -- {"index":"allowed","excerpt":"unknown",...}
  verification    text NOT NULL DEFAULT 'unverified' CHECK (verification IN ('unverified','verified','disputed','expired')),
  verified_by     uuid REFERENCES users(id),
  verified_at     timestamptz,
  review_due      date,
  content_sha256  char(64),                                                  -- hash do arquivo/trecho preservado, quando houver
  supersedes_id   uuid REFERENCES kb_sources(id),
  limitations     text CHECK (length(limitations) <= 2000),
  confidence      text NOT NULL DEFAULT 'editorial' CHECK (confidence IN ('editorial','reviewed','disputed')),
  status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active','retracted')),
  retraction_reason text CHECK (length(retraction_reason) <= 1000),
  note            text CHECK (length(note) <= 1000),
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (status <> 'retracted' OR retraction_reason IS NOT NULL),
  CHECK (verification <> 'verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL))
);
CREATE INDEX ix_kb_sources_klass ON kb_sources (klass, status);
CREATE INDEX ix_kb_sources_review ON kb_sources (review_due) WHERE status = 'active';
COMMENT ON TABLE kb_sources IS
  'Registro mestre de fontes da camada de conhecimento. klass é classificação EDITORIAL (O/A/V/H/D), não decisão jurídica. '
  'rights: direito de uso por operação (store/index/excerpt/summarize/translate/embed/send_external/train/redistribute) com valores '
  'allowed/denied/unknown — unknown bloqueia a operação. URL pública não implica licença.';

-- direitos: só chaves e valores conhecidos; desconhecido ≠ permitido
CREATE FUNCTION kb_rights_ok(r jsonb) RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
  SELECT r IS NOT NULL AND jsonb_typeof(r) = 'object'
     AND NOT EXISTS (SELECT 1 FROM jsonb_each_text(r) e
                     WHERE e.key NOT IN ('store','index','excerpt','summarize','translate','embed','send_external','train','redistribute')
                        OR e.value NOT IN ('allowed','denied','unknown'))
$$;
ALTER TABLE kb_sources ADD CONSTRAINT kb_sources_rights_known CHECK (kb_rights_ok(rights));

CREATE FUNCTION kb_source_right(p_source uuid, p_op text) RETURNS boolean LANGUAGE sql STABLE AS $$
  SELECT coalesce((SELECT s.status = 'active' AND s.rights ->> p_op = 'allowed' FROM kb_sources s WHERE s.id = p_source), false)
$$;
COMMENT ON FUNCTION kb_source_right(uuid, text) IS 'true só quando a fonte está ativa E o direito pedido está explicitamente allowed (unknown/denied/ausente = false).';

-- a fonte é um registro: o que foi consultado não se reescreve; mudam verificação, revisão, status e notas
CREATE FUNCTION kb_source_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.key <> OLD.key OR NEW.url IS DISTINCT FROM OLD.url OR NEW.source_type <> OLD.source_type OR NEW.published_on IS DISTINCT FROM OLD.published_on
     OR NEW.content_sha256 IS DISTINCT FROM OLD.content_sha256 OR NEW.created_by IS DISTINCT FROM OLD.created_by OR NEW.created_at <> OLD.created_at THEN
    RAISE EXCEPTION 'fonte: chave, URL, tipo, data de publicação e hash são imutáveis — registre uma fonte nova com supersedes_id' USING ERRCODE = '23514';
  END IF;
  IF OLD.status = 'retracted' AND NEW.status <> 'retracted' THEN
    RAISE EXCEPTION 'fonte retirada não volta a ativa: registre uma fonte nova' USING ERRCODE = '23514';
  END IF;
  IF NEW.verification = 'verified' AND (OLD.verification <> 'verified' OR NEW.verified_by IS DISTINCT FROM OLD.verified_by)
     AND NEW.verified_by IS NOT DISTINCT FROM NEW.created_by AND NEW.created_by IS NOT NULL THEN
    RAISE EXCEPTION 'quem registrou a fonte não pode verificá-la (quatro olhos)' USING ERRCODE = '42501';
  END IF;
  NEW.updated_at := now();
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_source_guard BEFORE UPDATE ON kb_sources FOR EACH ROW EXECUTE FUNCTION kb_source_guard();
CREATE TRIGGER trg_kb_sources_nodelete BEFORE DELETE ON kb_sources FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- ============================================================================ 2. citações (versão de conteúdo → fonte → trecho)
CREATE TABLE kb_citations (
  id              bigserial PRIMARY KEY,
  object_type     text NOT NULL CHECK (object_type IN ('article_version','faq','resource')),
  object_id       uuid NOT NULL,
  source_id       uuid NOT NULL REFERENCES kb_sources(id),
  locator         text CHECK (length(locator) <= 200),                       -- "art. 12, §1º", "§ 3.2", "p. 14"
  excerpt         text CHECK (length(excerpt) <= 600),                       -- trecho curto: só com rights.excerpt = allowed
  excerpt_sha256  char(64),
  claim           text CHECK (length(claim) <= 600),                         -- a afirmação do conteúdo que o trecho sustenta
  created_by      uuid REFERENCES users(id),
  created_at      timestamptz NOT NULL DEFAULT now(),
  CHECK (excerpt IS NULL OR excerpt_sha256 IS NOT NULL)
);
CREATE INDEX ix_kb_citations_obj ON kb_citations (object_type, object_id);
CREATE INDEX ix_kb_citations_src ON kb_citations (source_id);
CREATE TRIGGER trg_kb_citations_append_only BEFORE UPDATE OR DELETE ON kb_citations FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- trecho só com direito explícito; hash conferido no banco
CREATE FUNCTION kb_citation_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.excerpt IS NOT NULL THEN
    IF NOT kb_source_right(NEW.source_id, 'excerpt') THEN
      RAISE EXCEPTION 'citação com trecho exige fonte ativa com direito de trecho explicitamente permitido (rights.excerpt = allowed)' USING ERRCODE = '42501';
    END IF;
    IF NEW.excerpt_sha256 IS DISTINCT FROM encode(sha256(convert_to(NEW.excerpt, 'UTF8')), 'hex') THEN
      RAISE EXCEPTION 'hash do trecho não confere com o texto' USING ERRCODE = '23514';
    END IF;
  END IF;
  IF NEW.object_type = 'article_version' AND NOT EXISTS (SELECT 1 FROM kb_article_versions v WHERE v.id = NEW.object_id AND v.status = 'draft') THEN
    RAISE EXCEPTION 'citações entram na versão em rascunho; versões revisadas são imutáveis' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_citation_guard BEFORE INSERT ON kb_citations FOR EACH ROW EXECUTE FUNCTION kb_citation_guard();

-- ============================================================================ 3. retirada (terminal, com motivo)
ALTER TABLE kb_article_versions DROP CONSTRAINT kb_article_versions_status_check;
ALTER TABLE kb_article_versions ADD CONSTRAINT kb_article_versions_status_check
  CHECK (status IN ('draft','review','approved','published','superseded','archived','retracted'));
ALTER TABLE kb_article_versions ADD COLUMN retraction_reason text CHECK (length(retraction_reason) <= 1000);
ALTER TABLE kb_article_versions ADD COLUMN retracted_by uuid REFERENCES users(id);
ALTER TABLE kb_article_versions ADD COLUMN retracted_at timestamptz;
ALTER TABLE kb_article_versions ADD CONSTRAINT kb_article_versions_retraction_reason
  CHECK (status <> 'retracted' OR (retraction_reason IS NOT NULL AND retracted_by IS NOT NULL AND retracted_at IS NOT NULL));

ALTER TABLE kb_faqs DROP CONSTRAINT kb_faqs_status_check;
ALTER TABLE kb_faqs ADD CONSTRAINT kb_faqs_status_check CHECK (status IN ('draft','review','approved','published','archived','retracted'));
ALTER TABLE kb_faqs ADD COLUMN retraction_reason text CHECK (length(retraction_reason) <= 1000);
ALTER TABLE kb_faqs ADD COLUMN retracted_by uuid REFERENCES users(id);
ALTER TABLE kb_faqs ADD COLUMN retracted_at timestamptz;
ALTER TABLE kb_faqs ADD CONSTRAINT kb_faqs_retraction_reason
  CHECK (status <> 'retracted' OR (retraction_reason IS NOT NULL AND retracted_by IS NOT NULL AND retracted_at IS NOT NULL));

ALTER TABLE kb_resources DROP CONSTRAINT kb_resources_status_check;
ALTER TABLE kb_resources ADD CONSTRAINT kb_resources_status_check
  CHECK (status IN ('draft','review','approved','published','superseded','archived','retracted'));
ALTER TABLE kb_resources ADD COLUMN retraction_reason text CHECK (length(retraction_reason) <= 1000);
ALTER TABLE kb_resources ADD COLUMN retracted_by uuid REFERENCES users(id);
ALTER TABLE kb_resources ADD COLUMN retracted_at timestamptz;
ALTER TABLE kb_resources ADD CONSTRAINT kb_resources_retraction_reason
  CHECK (status <> 'retracted' OR (retraction_reason IS NOT NULL AND retracted_by IS NOT NULL AND retracted_at IS NOT NULL));

-- retirar = conteúdo vivo some (busca, assistente, sitemap); retirado é terminal
CREATE OR REPLACE FUNCTION kb_unpublish_article() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF OLD.status = 'published' AND NEW.status IN ('archived','retracted') THEN
    UPDATE kb_articles SET live_version_id = NULL, search_doc = NULL, updated_at = now() WHERE id = NEW.article_id AND live_version_id = OLD.id;
  END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION kb_retraction_terminal() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'retracted' AND NEW.status <> 'retracted' THEN
    RAISE EXCEPTION 'conteúdo retirado não volta: crie uma nova versão' USING ERRCODE = '23514';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_kb_version_retraction_terminal BEFORE UPDATE OF status ON kb_article_versions FOR EACH ROW EXECUTE FUNCTION kb_retraction_terminal();
CREATE TRIGGER trg_kb_faq_retraction_terminal BEFORE UPDATE OF status ON kb_faqs FOR EACH ROW EXECUTE FUNCTION kb_retraction_terminal();
CREATE TRIGGER trg_kb_resource_retraction_terminal BEFORE UPDATE OF status ON kb_resources FOR EACH ROW EXECUTE FUNCTION kb_retraction_terminal();

-- leitura: a versão retirada continua legível para a equipe (histórico), nunca para o público
-- (as políticas de leitura pública exigem status = 'published'; nada a alterar)

-- ============================================================================ 4. fila editorial
CREATE TABLE kb_work_items (
  id             bigserial PRIMARY KEY,
  kind           text NOT NULL CHECK (kind IN ('search_gap','assistant_gap','unhelpful','stale','expired','incorrect_report','source_review','retraction_followup')),
  dedupe_key     text NOT NULL,                                               -- kind + alvo/tópico; um item ABERTO por chave
  ref_type       text CHECK (ref_type IS NULL OR ref_type IN ('article','faq','resource','course','source','topic','ctx_key')),
  ref_id         text,
  topic          text CHECK (length(topic) <= 120),
  ctx_key        text CHECK (length(ctx_key) <= 120),
  occurrences    integer NOT NULL DEFAULT 1 CHECK (occurrences >= 1),
  details        jsonb NOT NULL DEFAULT '{}'::jsonb,                          -- nunca texto livre de busca (ADR-043): hash e tópicos
  reporter_id    uuid REFERENCES users(id),                                   -- relato de informação incorreta
  status         text NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','done','dismissed')),
  assigned_to    uuid REFERENCES users(id),
  resolution     text CHECK (length(resolution) <= 1000),
  resolved_by    uuid REFERENCES users(id),
  resolved_at    timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CHECK (status NOT IN ('done','dismissed') OR (resolution IS NOT NULL AND resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
);
CREATE UNIQUE INDEX ux_kb_work_items_open ON kb_work_items (dedupe_key) WHERE status IN ('open','in_progress');
CREATE INDEX ix_kb_work_items_status ON kb_work_items (status, kind, updated_at DESC);
CREATE TRIGGER trg_kb_work_items_touch BEFORE UPDATE ON kb_work_items FOR EACH ROW EXECUTE FUNCTION touch_updated_at();

-- abre (ou incrementa) um item de trabalho; chamado pela aplicação em contexto público (busca anônima) → SECURITY DEFINER
CREATE FUNCTION kb_work_open(p_kind text, p_dedupe text, p_ref_type text, p_ref_id text, p_topic text, p_ctx text, p_details jsonb, p_reporter uuid)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
DECLARE v_id bigint;
BEGIN
  INSERT INTO kb_work_items (kind, dedupe_key, ref_type, ref_id, topic, ctx_key, details, reporter_id)
  VALUES (p_kind, p_dedupe, p_ref_type, p_ref_id, p_topic, p_ctx, coalesce(p_details, '{}'::jsonb), p_reporter)
  ON CONFLICT (dedupe_key) WHERE status IN ('open','in_progress')
  DO UPDATE SET occurrences = kb_work_items.occurrences + 1, details = kb_work_items.details || coalesce(EXCLUDED.details, '{}'::jsonb), updated_at = now()
  RETURNING id INTO v_id;
  RETURN v_id;
END $$;

-- ============================================================================ 5. histórico editorial cobre fontes (itens de trabalho guardam a própria resolução)
ALTER TABLE content_history DROP CONSTRAINT content_history_object_type_check;
ALTER TABLE content_history ADD CONSTRAINT content_history_object_type_check
  CHECK (object_type IN ('article_version','resource','faq','course','event','path','source'));

-- ============================================================================ 6. RLS e permissões
ALTER TABLE kb_sources ENABLE ROW LEVEL SECURITY;
CREATE POLICY kb_sources_read ON kb_sources FOR SELECT USING (true);               -- fontes são referências públicas; o conteúdo privado é o artigo, não a fonte
CREATE POLICY kb_sources_write ON kb_sources FOR ALL USING (app_priv()) WITH CHECK (app_priv());
ALTER TABLE kb_citations ENABLE ROW LEVEL SECURITY;
CREATE POLICY kb_citations_read ON kb_citations FOR SELECT
  USING (app_priv()
         OR (object_type = 'article_version' AND EXISTS (SELECT 1 FROM kb_article_versions v JOIN kb_articles a ON a.id = v.article_id
                                                         WHERE v.id = object_id AND v.status = 'published' AND kb_visible(a.visibility, a.audience)))
         OR (object_type = 'faq' AND EXISTS (SELECT 1 FROM kb_faqs f WHERE f.id = object_id AND f.status = 'published' AND kb_visible(f.visibility, f.audience)))
         OR (object_type = 'resource' AND EXISTS (SELECT 1 FROM kb_resources r WHERE r.id = object_id AND r.status = 'published' AND kb_visible(r.visibility, r.audience))));
CREATE POLICY kb_citations_write ON kb_citations FOR INSERT WITH CHECK (app_priv());
ALTER TABLE kb_work_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY kb_work_items_priv ON kb_work_items FOR ALL USING (app_priv()) WITH CHECK (app_priv());
GRANT SELECT, INSERT, UPDATE ON kb_sources, kb_work_items TO impacto_app;
GRANT SELECT, INSERT ON kb_citations TO impacto_app;
GRANT USAGE, SELECT ON SEQUENCE kb_citations_id_seq, kb_work_items_id_seq TO impacto_app;
GRANT EXECUTE ON FUNCTION kb_work_open(text, text, text, text, text, text, jsonb, uuid), kb_source_right(uuid, text), kb_rights_ok(jsonb) TO impacto_app;

INSERT INTO polymorphic_refs (source_table, type_column, id_column, note) VALUES
  ('kb_citations','object_type','object_id','conteúdo citado: versão de artigo, FAQ ou recurso'),
  ('kb_work_items','ref_type','ref_id','alvo do item editorial: conteúdo, fonte, tópico ou tela (texto)')
ON CONFLICT DO NOTHING;
INSERT INTO audit_action_categories (prefix, category, note) VALUES
  ('kb','WORKFLOWS','camada de conhecimento: fontes, citações, retirada, fila editorial (v0.29.0)')
ON CONFLICT DO NOTHING;

-- ============================================================================ 7. sementes: fontes primárias preservadas pela base v0.26.0 (knowledge-base/MASTER §12)
-- Classe e vigência são EDITORIAIS e nascem 'unverified' com review_due: ninguém marcou aqui que a norma está em vigor na data da decisão.
-- Direitos: textos oficiais brasileiros (Planalto) permitem reprodução com indicação da fonte (Lei 9.610/1998, art. 8º, IV — atos oficiais
-- não são protegidos); padrões (W3C, NIST) e documentos de órgãos têm licenças próprias → 'unknown' até conferência.
INSERT INTO kb_sources (key, title, publisher, url, source_type, klass, jurisdiction, published_on, consulted_on, license, rights, review_due, note) VALUES
  ('br.lei.13709-2018', 'Lei nº 13.709/2018 — Lei Geral de Proteção de Dados Pessoais (LGPD), texto compilado', 'Presidência da República / Planalto',
   'https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709compilado.htm', 'law', 'O', 'BR', '2018-08-14', '2026-10-08',
   'ato oficial: sem proteção autoral (Lei 9.610/1998, art. 8º, IV)',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"allowed"}',
   '2026-11-07', 'preservada de knowledge-base/research/02-lgpd-anpd.md [R02]; vigência a revalidar na data da decisão'),
  ('br.lei.13019-2014', 'Lei nº 13.019/2014 — Marco Regulatório das Organizações da Sociedade Civil (MROSC), texto compilado', 'Presidência da República / Planalto',
   'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2014/lei/l13019compilado.htm', 'law', 'O', 'BR', '2014-07-31', '2026-10-08',
   'ato oficial: sem proteção autoral (Lei 9.610/1998, art. 8º, IV)',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"allowed"}',
   '2026-11-07', 'preservada de knowledge-base/research/03-osc-mro-sc.md [R03]'),
  ('br.lei.14133-2021', 'Lei nº 14.133/2021 — Lei de Licitações e Contratos Administrativos', 'Presidência da República / Planalto',
   'https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm', 'law', 'O', 'BR', '2021-04-01', '2026-10-08',
   'ato oficial: sem proteção autoral (Lei 9.610/1998, art. 8º, IV)',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"allowed"}',
   '2026-11-07', 'preservada de knowledge-base/research/04-public-procurement-innovation.md [R04]'),
  ('br.lei.14063-2020', 'Lei nº 14.063/2020 — assinaturas eletrônicas em interações com entes públicos', 'Presidência da República / Planalto',
   'https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2020/lei/l14063.htm', 'law', 'O', 'BR', '2020-09-23', '2026-10-08',
   'ato oficial: sem proteção autoral (Lei 9.610/1998, art. 8º, IV)',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"allowed"}',
   '2026-11-07', 'preservada de knowledge-base/research/01-civil-consumer-contracts.md [R01]'),
  ('br.lei.8078-1990', 'Lei nº 8.078/1990 — Código de Defesa do Consumidor, texto compilado', 'Presidência da República / Planalto',
   'https://www.planalto.gov.br/ccivil_03/leis/l8078compilado.htm', 'law', 'O', 'BR', '1990-09-11', '2026-10-08',
   'ato oficial: sem proteção autoral (Lei 9.610/1998, art. 8º, IV)',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"allowed"}',
   '2026-11-07', 'preservada de knowledge-base/research/01 e 11 [R01, R11]; incidência por fluxo é decisão de advogado (LEG-005)'),
  ('br.lei.12865-2013', 'Lei nº 12.865/2013 — arranjos e instituições de pagamento', 'Presidência da República / Planalto',
   'https://www.planalto.gov.br/ccivil_03/_ato2011-2014/2013/lei/l12865.htm', 'law', 'O', 'BR', '2013-10-09', '2026-10-08',
   'ato oficial: sem proteção autoral (Lei 9.610/1998, art. 8º, IV)',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"allowed"}',
   '2026-11-07', 'preservada de knowledge-base/research/05-finance-tax-payment.md [R05]; base da arquitetura não custodial (ADR-343)'),
  ('br.lei.13146-2015', 'Lei nº 13.146/2015 — Lei Brasileira de Inclusão da Pessoa com Deficiência', 'Presidência da República / Planalto',
   'https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2015/lei/l13146.htm', 'law', 'O', 'BR', '2015-07-06', '2026-10-08',
   'ato oficial: sem proteção autoral (Lei 9.610/1998, art. 8º, IV)',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"allowed"}',
   '2026-11-07', 'preservada de knowledge-base/research/10 e 12 [R10, R12]'),
  ('br.lei.9610-1998', 'Lei nº 9.610/1998 — direitos autorais', 'Presidência da República / Planalto',
   'https://www.planalto.gov.br/ccivil_03/leis/l9610.htm', 'law', 'O', 'BR', '1998-02-19', '2026-10-08',
   'ato oficial: sem proteção autoral (Lei 9.610/1998, art. 8º, IV)',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"allowed"}',
   '2026-11-07', 'preservada de knowledge-base/research/07 e 10 [R07, R10]; base do registro de direitos de uso'),
  ('w3c.wcag-2.2', 'Web Content Accessibility Guidelines (WCAG) 2.2', 'W3C',
   'https://www.w3.org/TR/WCAG22/', 'standard', 'V', NULL, '2023-10-05', '2026-10-08',
   NULL,
   '{"store":"unknown","index":"allowed","excerpt":"unknown","summarize":"allowed","translate":"unknown","embed":"unknown","send_external":"unknown","train":"denied","redistribute":"denied"}',
   '2026-11-07', 'preservada de knowledge-base/research/10 [R10]; padrão VOLUNTÁRIO adotado como meta (LEG-032); licença W3C Document License a conferir'),
  ('un.sdg', 'Objetivos de Desenvolvimento Sustentável (ODS) — relatório/síntese Brasil', 'ONU / Governo Federal (odsbrasil.gov.br)',
   'https://odsbrasil.gov.br/relatorio/sintese', 'report', 'V', 'BR', NULL, '2026-10-08',
   NULL,
   '{"store":"unknown","index":"allowed","excerpt":"unknown","summarize":"allowed","translate":"unknown","embed":"unknown","send_external":"unknown","train":"unknown","redistribute":"unknown"}',
   '2026-11-07', 'preservada de knowledge-base/research/06 [R06]; metas ODS continuam NÃO carregadas (LEG-053) até importação com proveniência'),
  ('impacto.kb.master-0.26.0', 'IMPACTO Trust — Master Knowledge Base v0.26.0 (consolidação de 12 pesquisas)', 'IMPACTO (interno)',
   NULL, 'internal_evidence', 'H', NULL, '2026-10-08', '2026-10-08',
   'documento interno do projeto',
   '{"store":"allowed","index":"allowed","excerpt":"allowed","summarize":"allowed","translate":"allowed","embed":"allowed","send_external":"denied","train":"denied","redistribute":"denied"}',
   '2026-11-07', 'knowledge-base/MASTER-KNOWLEDGE-BASE.md; classe H porque a base é síntese operacional, não norma; as fontes primárias que ela cita têm registro próprio');
