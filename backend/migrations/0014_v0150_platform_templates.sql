-- 0014 — v0.15.0: modelos de documento DA PLATAFORMA, como dado (owner_org_id NULL = modelo da plataforma).
-- HONESTIDADE DA FONTE: o campo `source_note` de cada modelo diz de onde a estrutura vem e o que precisa ser
-- conferido pela organização. Nenhum destes modelos é "o formulário oficial" de um financiador: a plataforma NÃO
-- distribui formulário de terceiro. O que existe aqui é estrutura de conteúdo, que a organização adapta ao edital.
-- Publicado = imutável (trg_guard em document_templates): corrigir exige nova versão do modelo.

-- ================================================================================================ 1. PROJETO TÉCNICO
WITH t AS (
  INSERT INTO document_templates(code, version, title, kind, description, data_sources, output_formats, status,
                                 owner_org_id, source_note, published_at)
  VALUES ('projeto_tecnico_base', '1.0', 'Projeto técnico — estrutura base', 'project_technical',
          'Estrutura de conteúdo para apresentar um projeto social: problema com evidência, objetivo, metodologia, '
          'metas, indicadores, orçamento e riscos.',
          '{project,organization,diagnosis,indicators,budget,milestones,risks}', '{pdf,docx,odt}', 'published',
          NULL,
          'Estrutura própria da Plataforma Impacto, derivada da prática de elaboração de projetos sociais. NÃO é '
          'formulário oficial de nenhum financiador: confira sempre as exigências do edital aplicável.', now())
  RETURNING id)
INSERT INTO document_template_fields(template_id, section, position, key, label, help, field_type, required,
                                     derived_from, requires_evidence)
SELECT t.id, s, p, k, l, h, ft, req, der, ev FROM t, (VALUES
  ('1. Identificação',  1, 'org.legal_name',     'Organização proponente', NULL, 'text', true,  'organization.legal_name', false),
  ('1. Identificação',  2, 'org.cnpj',           'CNPJ', NULL, 'text', false, 'organization.cnpj', false),
  ('1. Identificação',  3, 'org.city_uf',        'Município/UF', NULL, 'text', false, 'organization.city_uf', false),
  ('1. Identificação',  4, 'project.title',      'Título do projeto', NULL, 'text', true,  'project.title', false),
  ('1. Identificação',  5, 'project.territory',  'Território de atuação', NULL, 'text', false, 'project.territory', false),
  ('2. Problema',       1, 'problema',           'Problema que o projeto enfrenta',
     'Descreva o problema e apresente o dado que o sustenta. Problema sem evidência vira opinião.', 'textarea', true, 'project.problem', true),
  ('2. Problema',       2, 'publico',            'Público atendido',
     'Descrição agregada do público. Não inclua dado pessoal de beneficiário neste documento.', 'textarea', true, NULL, false),
  ('2. Problema',       3, 'beneficiarios',      'Quantidade estimada de pessoas atendidas', NULL, 'number', false, 'project.beneficiaries_count', false),
  ('3. Proposta',       1, 'objetivo_geral',     'Objetivo geral', NULL, 'textarea', true, 'project.objectives', false),
  ('3. Proposta',       2, 'objetivos_especificos','Objetivos específicos', NULL, 'list', true, NULL, false),
  ('3. Proposta',       3, 'metodologia',        'Metodologia',
     'Como o projeto será executado: atividades, frequência, responsáveis.', 'textarea', true, 'project.methodology', false),
  ('3. Proposta',       4, 'ods',                'ODS relacionados', NULL, 'ods', false, NULL, false),
  ('4. Resultados',     1, 'metas',              'Metas', 'Meta precisa de número, prazo e forma de aferição.', 'table', true, NULL, false),
  ('4. Resultados',     2, 'indicadores',        'Indicadores', 'Separe produto (output), resultado (outcome) e impacto.', 'indicator_ref', true, NULL, false),
  ('4. Resultados',     3, 'monitoramento',      'Como os indicadores serão medidos', NULL, 'textarea', true, NULL, false),
  ('5. Execução',       1, 'inicio',             'Início previsto', NULL, 'date', true, 'project.starts_on', false),
  ('5. Execução',       2, 'fim',                'Término previsto', NULL, 'date', true, 'project.ends_on', false),
  ('5. Execução',       3, 'cronograma',         'Cronograma de marcos', NULL, 'table', true, NULL, false),
  ('6. Orçamento',      1, 'orcamento_total',    'Orçamento total', NULL, 'money', true, 'project.budget_total_cents', false),
  ('6. Orçamento',      2, 'orcamento_detalhado','Detalhamento por rubrica', NULL, 'table', true, NULL, false),
  ('6. Orçamento',      3, 'contrapartida',      'Contrapartida da organização', NULL, 'textarea', false, NULL, false),
  ('7. Riscos',         1, 'riscos',             'Riscos e mitigação', NULL, 'table', true, NULL, false),
  ('8. Capacidade',     1, 'experiencia',        'Experiência da organização no tema', NULL, 'textarea', true, NULL, false),
  ('8. Capacidade',     2, 'equipe',             'Equipe responsável e qualificação', NULL, 'textarea', true, NULL, false),
  ('8. Capacidade',     3, 'doc_estatuto',       'Estatuto social', 'Anexe o documento vigente.', 'document_ref', true, NULL, true),
  ('8. Capacidade',     4, 'doc_regularidade',   'Comprovante de regularidade fiscal', NULL, 'document_ref', false, NULL, true)
) AS v(s, p, k, l, h, ft, req, der, ev);

-- ================================================================================================ 2. PLANO DE TRABALHO
-- Base legal citada de forma verificável: Lei 13.019/2014 (MROSC), art. 22, que lista o conteúdo do plano de trabalho.
-- A estrutura abaixo é a leitura da plataforma sobre esse artigo. O edital concreto pode exigir mais — conferir.
WITH t AS (
  INSERT INTO document_templates(code, version, title, kind, description, data_sources, output_formats, status,
                                 owner_org_id, source_note, published_at)
  VALUES ('plano_trabalho_mrosc', '1.0', 'Plano de trabalho — conteúdo do art. 22 da Lei 13.019/2014', 'work_plan',
          'Estrutura de plano de trabalho organizada pelos itens de conteúdo que o art. 22 da Lei 13.019/2014 exige.',
          '{project,organization,indicators,budget,milestones}', '{pdf,docx,odt}', 'published', NULL,
          'Itens organizados a partir do art. 22 da Lei 13.019/2014 (MROSC). A redação final e eventuais anexos '
          'seguem o edital e o órgão parceiro — confira antes de protocolar. A plataforma não reproduz formulário '
          'oficial de órgão público.', now())
  RETURNING id)
INSERT INTO document_template_fields(template_id, section, position, key, label, help, field_type, required,
                                     derived_from, requires_evidence)
SELECT t.id, s, p, k, l, h, ft, req, der, ev FROM t, (VALUES
  ('I. Realidade',      1, 'realidade',          'Descrição da realidade objeto da parceria',
     'Art. 22, I: descrição da realidade e o nexo com a atividade proposta.', 'textarea', true, 'project.problem', true),
  ('I. Realidade',      2, 'nexo',               'Nexo entre a realidade e a atividade proposta', NULL, 'textarea', true, NULL, false),
  ('II. Metas',         1, 'metas_quantitativas','Metas quantitativas e mensuráveis',
     'Art. 22, I: metas a serem atingidas.', 'table', true, NULL, false),
  ('II. Metas',         2, 'parametros',         'Parâmetros de aferição do cumprimento das metas',
     'Art. 22, III: como cada meta será aferida.', 'table', true, NULL, false),
  ('III. Execução',     1, 'forma_execucao',     'Forma de execução das atividades',
     'Art. 22, II: forma de execução das ações.', 'textarea', true, 'project.methodology', false),
  ('III. Execução',     2, 'cronograma_fisico',  'Cronograma de execução física', NULL, 'table', true, NULL, false),
  ('IV. Financeiro',    1, 'receitas_despesas',  'Previsão de receitas e de despesas',
     'Art. 22, II: previsão de receitas e de despesas a serem realizadas.', 'table', true, NULL, false),
  ('IV. Financeiro',    2, 'cronograma_desembolso','Cronograma de desembolso', NULL, 'table', true, NULL, false),
  ('IV. Financeiro',    3, 'valor_total',        'Valor total da parceria', NULL, 'money', true, 'project.budget_total_cents', false),
  ('V. Proponente',     1, 'proponente',         'Organização proponente', NULL, 'text', true, 'organization.legal_name', false),
  ('V. Proponente',     2, 'vigencia_inicio',    'Início da vigência', NULL, 'date', true, 'project.starts_on', false),
  ('V. Proponente',     3, 'vigencia_fim',       'Término da vigência', NULL, 'date', true, 'project.ends_on', false)
) AS v(s, p, k, l, h, ft, req, der, ev);

-- ================================================================================================ 3. MONITORAMENTO
WITH t AS (
  INSERT INTO document_templates(code, version, title, kind, description, data_sources, output_formats, status,
                                 owner_org_id, source_note, published_at)
  VALUES ('plano_monitoramento_base', '1.0', 'Plano de monitoramento e avaliação', 'monitoring_plan',
          'Como o projeto será acompanhado: indicadores por nível de resultado, fonte do dado, periodicidade e '
          'responsável pela coleta.', '{project,indicators,milestones}', '{pdf,docx,odt}', 'published', NULL,
          'Estrutura própria da Plataforma Impacto. A separação produto/resultado/impacto segue a lógica de cadeia '
          'de valor usada em avaliação de projetos sociais; meta atingida não é impacto comprovado.', now())
  RETURNING id)
INSERT INTO document_template_fields(template_id, section, position, key, label, help, field_type, required,
                                     derived_from, requires_evidence)
SELECT t.id, s, p, k, l, h, ft, req, der, ev FROM t, (VALUES
  ('1. Escopo',         1, 'projeto',            'Projeto', NULL, 'text', true, 'project.title', false),
  ('1. Escopo',         2, 'periodo',            'Período coberto pelo plano', NULL, 'text', true, NULL, false),
  ('2. Indicadores',    1, 'indicadores_produto','Indicadores de produto (output)',
     'O que foi entregue: atendimentos, oficinas, kits. Entrega não é mudança.', 'indicator_ref', true, NULL, false),
  ('2. Indicadores',    2, 'indicadores_resultado','Indicadores de resultado (outcome)',
     'A mudança na vida do público no curto e médio prazo.', 'indicator_ref', true, NULL, false),
  ('2. Indicadores',    3, 'indicadores_impacto','Indicadores de impacto',
     'Mudança sustentada e atribuível. Exige desenho de avaliação — declare se ainda não houver.', 'indicator_ref', false, NULL, false),
  ('3. Coleta',         1, 'fontes',             'Fonte de cada dado', NULL, 'table', true, NULL, false),
  ('3. Coleta',         2, 'periodicidade',      'Periodicidade da coleta', NULL, 'table', true, NULL, false),
  ('3. Coleta',         3, 'responsaveis',       'Responsável por cada coleta', NULL, 'table', true, NULL, false),
  ('3. Coleta',         4, 'instrumento',        'Instrumento de coleta', 'Anexe o instrumento, se houver.', 'document_ref', false, NULL, true),
  ('4. Uso',            1, 'uso_resultados',     'Como os resultados serão usados na gestão', NULL, 'textarea', true, NULL, false),
  ('4. Uso',            2, 'limitacoes',         'Limitações conhecidas da medição',
     'Dizer o que o dado NÃO prova é parte da honestidade do relatório.', 'textarea', true, NULL, false)
) AS v(s, p, k, l, h, ft, req, der, ev);

-- ================================================================================================ 4. CORREÇÃO
-- Reabrir projeto arquivado é exceção: passa a exigir motivo registrado (a 0013 deixou sem exigência).
UPDATE project_status_graph SET requires_reason = true WHERE from_status = 'archived' AND to_status = 'monitoring';

-- ================================================================================================ 5. IDENTIDADE DO ARQUIVO
-- O hash, o tamanho, o tipo e a chave de armazenamento identificam o ARQUIVO guardado. Nada na aplicação altera isso
-- depois do envio: nova versão de documento é LINHA NOVA. Diferente de guard_columns, aqui nem o contexto
-- privilegiado passa — só o dono do banco, e isso fica visível na auditoria do banco.
CREATE FUNCTION document_identity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF current_user::text = 'impacto_app' AND (NEW.sha256 IS DISTINCT FROM OLD.sha256
     OR NEW.size_bytes IS DISTINCT FROM OLD.size_bytes
     OR NEW.storage_key IS DISTINCT FROM OLD.storage_key
     OR NEW.mime_type IS DISTINCT FROM OLD.mime_type) THEN
    RAISE EXCEPTION 'A identidade do arquivo (hash, tamanho, tipo, chave) não muda: registre uma nova versão'
      USING ERRCODE = '42501';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER trg_doc_identity BEFORE UPDATE ON documents FOR EACH ROW
  EXECUTE FUNCTION document_identity_guard();

-- ================================================================================================ 6. DESEMPENHO
-- Achado da medição com volume (PERFORMANCE_REPORT.md): o feed do financiador chamava `project_funding` uma vez por
-- projeto candidato — centenas de idas ao banco por requisição. Versão em LOTE, com a MESMA guarda da função
-- individual (`app_uid() IS NOT NULL OR app_priv()`), para carregar todos os candidatos de uma vez.
CREATE FUNCTION project_funding_many(p_projects uuid[])
RETURNS TABLE(project_id uuid, committed_cents bigint)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
  SELECT p AS project_id,
         coalesce((SELECT sum(c.amount_cents) FROM commitments c
                    WHERE c.project_id = p AND c.status <> 'cancelled'), 0)::bigint
    FROM unnest(p_projects) AS p
   WHERE app_uid() IS NOT NULL OR app_priv();
$$;
REVOKE EXECUTE ON FUNCTION project_funding_many(uuid[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION project_funding_many(uuid[]) TO impacto_app;
