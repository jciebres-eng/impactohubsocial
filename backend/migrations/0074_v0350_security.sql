-- 0074 — v0.35.0 — CORREÇÕES DA AUDITORIA DE SEGURANÇA E INTEGRIDADE FINANCEIRA (fase 2, lotes A–I; ADR-385 a ADR-392)
--
-- Origem: auditoria somente leitura de 10/10/2026 (docs/security/AUDITORIA_SEGURANCA_FASE1.md). Cada bloco cita o ID do
-- controle da matriz. Esta migração só ACRESCENTA ou SUBSTITUI funções/políticas — nenhum dado é apagado.

-- ============================================================================ FILE-07 (lote A)
-- Antes (0002): financiador com candidatura em diligência (até 'closed') lia TODO documento da OSC sem projeto, ignorando a
-- visibilidade — inclusive a exportação de dados gerada pela plataforma e documentos de verificação de identidade —, e a
-- tela da candidatura os listava. Provado na auditoria (404 antes da diligência, 200 depois).
--
-- Agora:
--   * documento da OSC SEM projeto: só os tipos INSTITUCIONAIS (lista abaixo) ou o que a própria OSC marcar como
--     `visibility = 'parties'` (compartilhado com as partes em negociação);
--   * documento DO PROJETO da candidatura: como antes (é o objeto da diligência e da prestação de contas);
--   * NUNCA pela diligência: exportação de dados (`exportacao_dados`), documento pessoal de dirigente (`documento_dirigente`),
--     documento anexado a verificação de identidade (`identity_documents`) e evidência de verificação de beneficiário;
--   * o acesso termina quando a candidatura termina: 'closed' sai da lista (antes ficava aberto para sempre).
CREATE FUNCTION app_document_access(d_id uuid, d_org uuid, d_project uuid, d_application uuid, d_visibility text, d_type text)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT
    (
      coalesce(d_type, '') NOT IN ('exportacao_dados', 'documento_dirigente')
      AND NOT EXISTS (SELECT 1 FROM identity_documents i WHERE i.document_id = d_id)
      AND NOT EXISTS (SELECT 1 FROM org_kyb_verifications k WHERE d_id = ANY (k.evidence_document_ids))
      AND EXISTS (SELECT 1 FROM applications a
                   WHERE a.funder_org_id = app_org() AND a.osc_org_id = d_org
                     AND a.status IN ('due_diligence', 'approved', 'committed', 'in_execution', 'reporting')
                     AND ((d_project IS NULL
                           AND (d_visibility = 'parties'
                                OR d_type IN ('estatuto_social', 'ata_eleicao_diretoria', 'cartao_cnpj', 'cnd_federal', 'crf_fgts',
                                              'cndt_trabalhista', 'certidao_estadual', 'certidao_municipal', 'comprovante_endereco',
                                              'relatorio_atividades', 'balanco_patrimonial', 'registro_conselho', 'cebas',
                                              'titulo_utilidade_publica', 'plano_trabalho', 'orcamento_detalhado', 'proposta_projeto',
                                              'relatorio_prestacao_contas')))
                          OR (d_project IS NOT NULL AND a.project_id = d_project)))
    )
    -- documento compartilhado com as partes do projeto (investidores)
    OR (d_visibility = 'parties' AND d_project IS NOT NULL AND app_project_investor(d_project))
    -- profissional parceiro com revisão ativa sobre o documento, projeto ou candidatura
    OR app_review_access('document', d_id)
    OR (d_project IS NOT NULL AND app_review_access('project', d_project))
    OR (d_application IS NOT NULL AND app_review_access('application', d_application))
$$;
REVOKE ALL ON FUNCTION app_document_access(uuid, uuid, uuid, uuid, text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app_document_access(uuid, uuid, uuid, uuid, text, text) TO impacto_app;

DROP POLICY documents_read ON documents;
CREATE POLICY documents_read ON documents FOR SELECT USING (
  org_id = app_org() OR (visibility = 'public' AND app_authenticated())
  OR app_document_access(id, org_id, project_id, application_id, visibility, doc_type) OR app_priv());
DROP FUNCTION app_document_access(uuid, uuid, uuid, uuid, text);

-- ============================================================================ KYC-03 (lote B) — verificação do beneficiário
-- Antes: `beneficiary_verified()` aceitava QUALQUER linha 'verified' não vencida — registrar 'rejected' depois não desfazia
-- nada —; 'verified' podia ser gravado sem a titularidade da conta conferida; uma pessoa só decidia; a função não fixava
-- `search_path`. Agora: vale a decisão MAIS RECENTE; 'verified' exige titularidade conferida e a CONFIRMAÇÃO de uma
-- segunda pessoa da equipe (quatro olhos, conferido pelo banco).
ALTER TABLE org_kyb_verifications
  ADD COLUMN confirmed_by uuid REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN confirmed_at timestamptz,
  ADD CONSTRAINT kyb_four_eyes CHECK (confirmed_by IS NULL OR confirmed_by IS DISTINCT FROM reviewed_by),
  ADD CONSTRAINT kyb_verified_needs_account_holder CHECK (status <> 'verified' OR account_holder_matches IS TRUE),
  ADD CONSTRAINT kyb_only_verified_is_confirmed CHECK (confirmed_by IS NULL OR status = 'verified');

CREATE OR REPLACE FUNCTION beneficiary_verified(p_org uuid) RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER
SET search_path = public, pg_temp AS $$
  SELECT coalesce((SELECT k.status = 'verified' AND k.confirmed_by IS NOT NULL AND (k.expires_at IS NULL OR k.expires_at > now())
                     FROM org_kyb_verifications k WHERE k.org_id = p_org
                    ORDER BY k.created_at DESC, k.id DESC LIMIT 1), false)
$$;
REVOKE ALL ON FUNCTION beneficiary_verified(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION beneficiary_verified(uuid) TO impacto_app;

-- ============================================================================ PAY-03 / PAY-12 (lote B) — eventos do provedor
-- Evento que chega ANTES da confirmação (estorno, chargeback, liquidação) ficava 'ignored' para sempre. Agora fica
-- 'deferred' e é reaplicado logo depois da confirmação. Evento que falha ao aplicar conta tentativas: a rotina para
-- depois de 10 (fica na fila de exceções para uma pessoa), em vez de tentar para sempre.
ALTER TABLE payment_provider_events DROP CONSTRAINT payment_provider_events_processing_status_check;
ALTER TABLE payment_provider_events
  ADD CONSTRAINT payment_provider_events_processing_status_check
    CHECK (processing_status IN ('received','applied','ignored','rejected','failed','deferred')),
  ADD COLUMN apply_attempts integer NOT NULL DEFAULT 0 CHECK (apply_attempts >= 0);   -- `attempts` (0072) conta ENTREGAS

-- ============================================================================ PAY-07 (lote B) — conciliação com fonte declarada
-- Antes: sem extrato informado, o sistema conciliava contra os PRÓPRIOS eventos para qualquer provedor, e o extrato
-- manual (uma lista livre) marcava 'reconciled' na hora, enviado por uma pessoa só. Agora a execução registra a FONTE
-- (eventos assinados do sandbox | extrato manual | API do provedor); provedor real exige extrato; extrato manual só concilia
-- depois da aprovação de OUTRA pessoa (quatro olhos, conferido pelo banco).
ALTER TABLE reconciliation_runs
  ADD COLUMN status text NOT NULL DEFAULT 'done' CHECK (status IN ('done','awaiting_approval','approved')),
  ADD COLUMN snapshot_source text NOT NULL DEFAULT 'sandbox_signed_events'
    CHECK (snapshot_source IN ('sandbox_signed_events','manual_statement','provider_api')),
  ADD COLUMN snapshot jsonb,
  ADD COLUMN snapshot_sha256 text CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$'),
  ADD COLUMN approved_by uuid REFERENCES users(id) ON DELETE SET NULL,
  ADD COLUMN approved_at timestamptz,
  ADD CONSTRAINT recon_run_four_eyes CHECK (approved_by IS NULL OR approved_by IS DISTINCT FROM run_by),
  ADD CONSTRAINT recon_manual_has_snapshot CHECK (snapshot_source <> 'manual_statement' OR snapshot_sha256 IS NOT NULL);

-- ============================================================================ AUTH-04 (lote C) — cadastro do segundo fator da equipe
-- Para a equipe da plataforma, ativar o TOTP exige também um código enviado ao e-mail da conta (só o hash fica aqui).
ALTER TABLE users
  ADD COLUMN mfa_setup_code_hash text CHECK (mfa_setup_code_hash IS NULL OR mfa_setup_code_hash ~ '^[0-9a-f]{64}$'),
  ADD COLUMN mfa_setup_code_expires_at timestamptz;

-- ============================================================================ PAY-09 (lote D) — chave PIX de repasse
-- A chave é para onde o dinheiro vai. Antes: a dona trocava a chave a qualquer momento, sem confirmar identidade, sem aviso
-- às outras partes, sem carência e mesmo depois de todos assinarem. Agora (serviço + este gatilho, que vale para qualquer
-- caminho): chave JÁ INFORMADA não muda depois da primeira assinatura ou com o acordo fora de rascunho/assinatura — troca só
-- por nova versão do acordo; chave informada pela primeira vez depois de assinatura fica em carência (`pix_key_cooling_until`).
ALTER TABLE signed_agreement_parties ADD COLUMN pix_key_cooling_until timestamptz;

CREATE FUNCTION signed_party_pix_lock() RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $$
BEGIN
  IF OLD.pix_key IS NOT NULL
     AND (NEW.pix_key IS DISTINCT FROM OLD.pix_key OR NEW.pix_key_type IS DISTINCT FROM OLD.pix_key_type)
     AND (EXISTS (SELECT 1 FROM signed_agreement_parties p WHERE p.agreement_id = NEW.agreement_id AND p.signed_at IS NOT NULL)
          OR EXISTS (SELECT 1 FROM signed_agreements a WHERE a.id = NEW.agreement_id AND a.status NOT IN ('draft', 'awaiting_signatures')))
  THEN
    RAISE EXCEPTION 'chave PIX travada: o acordo já tem assinatura (troca só por nova versão do acordo)'
      USING ERRCODE = 'check_violation', CONSTRAINT = 'pix_locked_after_signature';
  END IF;
  RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION signed_party_pix_lock() FROM PUBLIC;
CREATE TRIGGER trg_party_pix_lock BEFORE UPDATE OF pix_key, pix_key_type ON signed_agreement_parties
  FOR EACH ROW EXECUTE FUNCTION signed_party_pix_lock();

-- ============================================================================ DB-03 (lote E) — `search_path` das funções SECURITY DEFINER
-- Uma função SECURITY DEFINER roda com o privilégio do DONO. Sem `search_path` fixo — ou fixo SEM `pg_temp` no fim, porque
-- então o esquema temporário é procurado PRIMEIRO para tabelas — quem executa SQL como `impacto_app` (por exemplo, por uma
-- injeção de SQL) cria uma tabela temporária com o nome de uma tabela da função e muda o resultado dela. Provado na fase 2:
-- uma tabela temporária `identity_verifications` fazia `identity_level()` devolver 'biometric' para qualquer pessoa.
-- Corrige TODAS as funções do esquema (laço no catálogo, não lista à mão); o teste de catálogo impede regressão.
-- Quem já fixava um caminho (por exemplo `public, extensions` — onde fica o pgcrypto no Supabase, 0062) MANTÉM os esquemas
-- e só ganha `pg_temp` no fim; quem não fixava nada passa a `public, pg_temp`.
DO $$
DECLARE
  f record;
  atual text;
  novo text;
BEGIN
  FOR f IN SELECT p.oid::regprocedure AS sig,
                  (SELECT substr(c, length('search_path=') + 1) FROM unnest(p.proconfig) c WHERE c LIKE 'search_path=%') AS caminho
             FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public' AND p.prosecdef
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
  LOOP
    atual := f.caminho;
    IF atual IS NULL THEN
      novo := 'public, pg_temp';
    ELSE
      SELECT string_agg(e, ', ' ORDER BY i) INTO novo
        FROM unnest(regexp_split_to_array(btrim(atual), '\s*,\s*')) WITH ORDINALITY AS x(e, i) WHERE e <> 'pg_temp' AND e <> '';
      novo := coalesce(novo || ', ', '') || 'pg_temp';
      IF novo = atual THEN
        CONTINUE;
      END IF;
    END IF;
    BEGIN
      EXECUTE format('ALTER FUNCTION %s SET search_path = %s', f.sig, novo);
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE WARNING 'search_path não fixado em % (a migração não é dona da função)', f.sig;
    END;
  END LOOP;
END $$;

-- ============================================================================ DB-05 (lote E) — EXECUTE só para quem usa
-- Toda função nasce executável por PUBLIC no PostgreSQL. A 0071 revogou de `anon`/`authenticated`, mas esses papéis herdam
-- de PUBLIC — 26 funções SECURITY DEFINER continuavam chamáveis pela API pública do Supabase (`/rest/v1/rpc/...`) se o
-- esquema estivesse exposto. Agora: EXECUTE revogado de PUBLIC em toda função do esquema (menos as de extensões) e
-- concedido explicitamente a `impacto_app` (que já executava por PUBLIC: o comportamento da aplicação não muda).
-- Funções criadas por migrações FUTURAS: o teste de catálogo falha se alguma nascer executável por PUBLIC (não se mexe no
-- privilégio padrão GLOBAL do papel administrativo, que no Supabase também cria objetos fora deste esquema).
DO $$
DECLARE f record;
BEGIN
  FOR f IN SELECT p.oid::regprocedure AS sig FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
            WHERE n.nspname = 'public'
              AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid = p.oid AND d.deptype = 'e')
  LOOP
    BEGIN
      EXECUTE format('REVOKE EXECUTE ON FUNCTION %s FROM PUBLIC', f.sig);
      EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO impacto_app', f.sig);
    EXCEPTION WHEN insufficient_privilege THEN
      RAISE WARNING 'EXECUTE não revisado em % (a migração não é dona da função)', f.sig;
    END;
  END LOOP;
END $$;

-- Supabase: os papéis da API pública perdem também o USO do esquema (a plataforma não usa a API de dados; CLAUDE.md).
-- Fora do Supabase os papéis não existem e o bloco não faz nada.
DO $$
DECLARE papel text;
BEGIN
  FOREACH papel IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = papel) THEN
      EXECUTE format('REVOKE USAGE ON SCHEMA public FROM %I', papel);
      EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I', papel);
    END IF;
  END LOOP;
END $$;

-- ============================================================================ DB-04 (lote E) — visão que não reaplicava a RLS
-- `project_baselines_without_source` rodava como dona e mostrava linhas de base de TODAS as organizações a `impacto_app`.
-- Com `security_invoker`, vale a RLS de `project_indicators` de quem consulta (a administração continua vendo tudo).
-- `ai_prompt_public` continua como está DE PROPÓSITO: projeta só colunas não sensíveis de `ai_prompts` (sem o texto de
-- sistema) — com `security_invoker` a aplicação precisaria ler a tabela inteira (0060).
ALTER VIEW project_baselines_without_source SET (security_invoker = true);

-- ============================================================================ DB-07 (lote E) — TRUNCATE nas tabelas só-inclusão
-- Toda tabela protegida contra UPDATE/DELETE por `forbid_mutation` ganha também a trava de TRUNCATE (o razão das doações,
-- os eventos econômicos de catálogo etc. não a tinham). Laço no catálogo; o teste confere que nenhuma ficou de fora.
DO $$
DECLARE t record;
BEGIN
  FOR t IN SELECT DISTINCT c.oid::regclass AS rel FROM pg_trigger g JOIN pg_class c ON c.oid = g.tgrelid
             JOIN pg_namespace n ON n.oid = c.relnamespace JOIN pg_proc p ON p.oid = g.tgfoid
            WHERE n.nspname = 'public' AND p.proname = 'forbid_mutation' AND NOT g.tgisinternal
              AND NOT EXISTS (SELECT 1 FROM pg_trigger x WHERE x.tgrelid = c.oid AND (x.tgtype & 32) <> 0)   -- 32 = TRUNCATE
  LOOP
    EXECUTE format('CREATE TRIGGER trg_no_truncate BEFORE TRUNCATE ON %s FOR EACH STATEMENT EXECUTE FUNCTION forbid_truncate()', t.rel);
  END LOOP;
END $$;
