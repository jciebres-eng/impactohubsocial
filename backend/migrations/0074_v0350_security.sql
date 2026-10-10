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
