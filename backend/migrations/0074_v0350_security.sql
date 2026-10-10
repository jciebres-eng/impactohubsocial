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
