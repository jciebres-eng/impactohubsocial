-- 0045 — v0.21.0: modelos de documento para o lado de QUEM FOMENTA (órgão público e financiador).
--
-- A LACUNA QUE ISTO FECHA, E A QUE NÃO FECHA
--
-- A v0.15.0 publicou três modelos, todos do lado de quem PROPÕE: projeto técnico, plano de trabalho
-- e plano de monitoramento. Quem publica edital e quem formaliza a parceria não tinha nenhum. A
-- auditoria desta rodada encontrou isso ao conferir o pedido "documentos modelos inseridos,
-- formatados e disponíveis... em cada perfil".
--
-- Os dois modelos abaixo existem porque há FONTE LEGAL CITÁVEL para a estrutura deles — a Lei
-- 13.019/2014, a mesma de onde veio o `plano_trabalho_mrosc` da v0.15.0. Não há modelo novo para
-- empresa, financiador privado ou profissional nesta migração, e a razão é a mesma invertida: não
-- existe texto legal que diga o que uma política de investimento social privado ou uma proposta
-- técnica de consultoria precisa conter. Inventar essa estrutura produziria um modelo que PARECE
-- padrão e não é padrão de nada — e alguém o usaria achando que segue alguma norma.
--
-- HONESTIDADE DA FONTE: a Lei 13.019/2014 foi alterada (Lei 13.204/2015, entre outras). `source_note`
-- de cada modelo manda conferir a redação vigente, e a plataforma NÃO distribui formulário oficial de
-- nenhum órgão: o que existe aqui é estrutura de conteúdo.

-- ================================================================== 1. EDITAL DE CHAMAMENTO PÚBLICO
WITH t AS (
  INSERT INTO document_templates(code, version, title, kind, description, data_sources, output_formats,
                                 status, owner_org_id, source_note, published_at)
  VALUES ('edital_chamamento_mrosc', '1.0',
          'Edital de chamamento público — conteúdo do art. 24 da Lei 13.019/2014', 'form',
          'Estrutura de edital de chamamento público organizada pelos itens de conteúdo que o art. 24 '
          'da Lei 13.019/2014 exige: objeto, programação orçamentária, prazos, critérios de julgamento '
          'com pesos, recurso administrativo, minuta do instrumento e medidas de acessibilidade.',
          '{organization,call,budget}', '{pdf,docx,odt}', 'published', NULL,
          'Itens organizados a partir do art. 24 da Lei 13.019/2014 (MROSC), com as alterações da Lei '
          '13.204/2015. CONFIRA A REDAÇÃO VIGENTE: a lei foi alterada mais de uma vez. Não é o edital '
          'oficial de nenhum órgão nem substitui parecer da procuradoria.', now())
  RETURNING id)
INSERT INTO document_template_fields(template_id, section, position, key, label, help, field_type,
                                     required, derived_from, requires_evidence)
SELECT t.id, s, p, k, l, h, ft, req, der, ev FROM t, (VALUES
  ('1. Órgão e identificação', 1, 'orgao.nome', 'Órgão ou entidade da administração pública', NULL, 'text', true, 'organization.legal_name', false),
  ('1. Órgão e identificação', 2, 'orgao.cnpj', 'CNPJ', NULL, 'text', false, 'organization.cnpj', false),
  ('1. Órgão e identificação', 3, 'edital.numero', 'Número do edital', NULL, 'text', true, NULL, false),
  ('1. Órgão e identificação', 4, 'edital.titulo', 'Título do chamamento', NULL, 'text', true, 'call.title', false),
  ('2. Objeto', 1, 'objeto', 'Objeto da parceria',
     'Art. 24. Descreva o que será executado, não o que se espera que aconteça. Objeto vago impede julgamento objetivo das propostas.', 'textarea', true, 'call.description', false),
  ('2. Objeto', 2, 'territorio', 'Território de abrangência', NULL, 'text', false, NULL, false),
  ('2. Objeto', 3, 'publico_alvo', 'Público a ser atendido', NULL, 'textarea', false, NULL, false),
  ('3. Programação orçamentária', 1, 'dotacao', 'Programação orçamentária que autoriza a parceria',
     'Art. 24, §1º, I. Sem dotação indicada, a parceria não pode ser celebrada — e o edital não deveria ser publicado.', 'text', true, NULL, true),
  ('3. Programação orçamentária', 2, 'valor_previsto', 'Valor previsto para a realização do objeto',
     'Art. 24, §1º, V.', 'money', true, 'call.budget_total_cents', false),
  ('3. Programação orçamentária', 3, 'parcelas', 'Cronograma de desembolso previsto', NULL, 'table', false, NULL, false),
  ('3. Programação orçamentária', 4, 'contrapartida', 'Contrapartida exigida, se houver',
     'Exigir contrapartida de OSC pequena pode restringir a competição sem ganho para o interesse público. Se exigir, justifique.', 'textarea', false, NULL, false),
  ('4. Prazos e apresentação', 1, 'prazo_propostas', 'Prazo para apresentação das propostas',
     'Art. 24, §1º, III.', 'date', true, 'call.deadline', false),
  ('4. Prazos e apresentação', 2, 'forma_envio', 'Local e forma de apresentação das propostas', NULL, 'textarea', true, NULL, false),
  ('4. Prazos e apresentação', 3, 'documentos_exigidos', 'Documentos exigidos da proponente', NULL, 'list', true, NULL, false),
  ('4. Prazos e apresentação', 4, 'acessibilidade_envio', 'Medidas de acessibilidade na apresentação de propostas',
     'Art. 24, §1º, IX. Acessibilidade não é cláusula de estilo: ela decide quem consegue concorrer.', 'textarea', false, NULL, false),
  ('5. Julgamento', 1, 'criterios', 'Critérios de seleção e julgamento',
     'Art. 24, §1º, IV. Cada critério precisa de metodologia de pontuação e peso — critério sem peso é critério sem efeito verificável.', 'table', true, NULL, false),
  ('5. Julgamento', 2, 'comissao', 'Composição da comissão de seleção', NULL, 'textarea', true, NULL, false),
  ('5. Julgamento', 3, 'impedimentos', 'Impedimentos e conflito de interesse na comissão',
     'Quem julga não pode ter vínculo com proponente. Diga como isso será declarado e conferido.', 'textarea', false, NULL, false),
  ('5. Julgamento', 4, 'divulgacao_resultado', 'Data e forma de divulgação do resultado', NULL, 'date', true, NULL, false),
  ('6. Recurso', 1, 'prazo_recurso', 'Prazo para interposição de recurso administrativo',
     'Art. 24, §1º, VII.', 'text', true, NULL, false),
  ('6. Recurso', 2, 'forma_recurso', 'Forma de interposição e julgamento do recurso', NULL, 'textarea', true, NULL, false),
  ('7. Instrumento e acessibilidade', 1, 'minuta_instrumento', 'Minuta do instrumento da parceria (anexo)',
     'Art. 24, §1º, VIII. A minuta é anexo obrigatório: quem concorre precisa saber o que vai assinar.', 'document_ref', true, NULL, true),
  ('7. Instrumento e acessibilidade', 2, 'acessibilidade_objeto', 'Medidas de acessibilidade na execução do objeto',
     'Art. 24, §1º, IX — pessoas com deficiência, mobilidade reduzida e idosos.', 'textarea', true, NULL, false),
  ('7. Instrumento e acessibilidade', 3, 'anexos', 'Demais anexos do edital', NULL, 'list', false, NULL, false)
) AS v(s, p, k, l, h, ft, req, der, ev);

-- ========================================================= 2. TERMO DE FOMENTO / COLABORAÇÃO
WITH t AS (
  INSERT INTO document_templates(code, version, title, kind, description, data_sources, output_formats,
                                 status, owner_org_id, source_note, published_at)
  VALUES ('termo_parceria_mrosc', '1.0',
          'Termo de fomento ou colaboração — cláusulas do art. 42 da Lei 13.019/2014', 'term',
          'Estrutura das cláusulas essenciais que o art. 42 da Lei 13.019/2014 exige do termo de '
          'fomento, do termo de colaboração e do acordo de cooperação. O plano de trabalho é anexo '
          'obrigatório e parte indissociável do instrumento.',
          '{organization,project,budget,milestones}', '{pdf,docx,odt}', 'published', NULL,
          'Cláusulas organizadas a partir do art. 42 da Lei 13.019/2014 (MROSC), com as alterações da '
          'Lei 13.204/2015. CONFIRA A REDAÇÃO VIGENTE e submeta à procuradoria: minuta de instrumento '
          'público não se assina a partir de modelo de plataforma.', now())
  RETURNING id)
INSERT INTO document_template_fields(template_id, section, position, key, label, help, field_type,
                                     required, derived_from, requires_evidence)
SELECT t.id, s, p, k, l, h, ft, req, der, ev FROM t, (VALUES
  ('1. Partes', 1, 'adm.nome', 'Administração pública parceira', NULL, 'text', true, NULL, false),
  ('1. Partes', 2, 'osc.nome', 'Organização da sociedade civil', NULL, 'text', true, 'organization.legal_name', false),
  ('1. Partes', 3, 'osc.cnpj', 'CNPJ da organização', NULL, 'text', true, 'organization.cnpj', false),
  ('1. Partes', 4, 'instrumento.tipo', 'Tipo de instrumento',
     'Fomento (proposta da OSC), colaboração (proposta da administração) ou acordo de cooperação (sem transferência de recursos).', 'enum', true, NULL, false),
  ('2. Objeto e obrigações', 1, 'objeto', 'Descrição do objeto pactuado', 'Art. 42, I.', 'textarea', true, 'project.title', false),
  ('2. Objeto e obrigações', 2, 'obrigacoes_adm', 'Obrigações da administração pública', 'Art. 42, II.', 'list', true, NULL, false),
  ('2. Objeto e obrigações', 3, 'obrigacoes_osc', 'Obrigações da organização', 'Art. 42, II.', 'list', true, NULL, false),
  ('2. Objeto e obrigações', 4, 'plano_trabalho', 'Plano de trabalho (anexo obrigatório)',
     'Art. 42, parágrafo único: o plano de trabalho é parte integrante e indissociável do instrumento. Use o modelo `plano_trabalho_mrosc`.', 'document_ref', true, NULL, true),
  ('3. Recursos', 1, 'valor_total', 'Valor total da parceria', 'Art. 42, III.', 'money', false, 'project.budget_total_cents', false),
  ('3. Recursos', 2, 'cronograma_desembolso', 'Cronograma de desembolso', 'Art. 42, III.', 'table', false, NULL, false),
  ('3. Recursos', 3, 'classificacao_orcamentaria', 'Classificação orçamentária da despesa e nota de empenho', 'Art. 42, IV.', 'text', false, NULL, true),
  ('3. Recursos', 4, 'conta_especifica', 'Conta bancária específica da parceria',
     'Art. 42: os recursos ficam em conta própria da parceria, não na conta geral da organização.', 'text', false, NULL, false),
  ('3. Recursos', 5, 'contrapartida', 'Contrapartida, quando houver', 'Art. 42, V.', 'textarea', false, NULL, false),
  ('4. Vigência', 1, 'inicio', 'Início da vigência', 'Art. 42, VI.', 'date', true, 'project.starts_on', false),
  ('4. Vigência', 2, 'fim', 'Término da vigência', 'Art. 42, VI.', 'date', true, 'project.ends_on', false),
  ('4. Vigência', 3, 'prorrogacao', 'Hipóteses de prorrogação', 'Art. 42, VI.', 'textarea', false, NULL, false),
  ('5. Prestação de contas', 1, 'forma_prestacao', 'Forma, metodologia e prazos da prestação de contas', 'Art. 42, VII.', 'textarea', true, NULL, false),
  ('5. Prestação de contas', 2, 'monitoramento', 'Forma de monitoramento e avaliação',
     'Art. 42, VIII — incluindo os recursos humanos e tecnológicos empregados.', 'textarea', true, NULL, false),
  ('5. Prestação de contas', 3, 'indicadores', 'Indicadores de aferição do cumprimento das metas', NULL, 'indicator_ref', false, NULL, false),
  ('5. Prestação de contas', 4, 'restituicao', 'Hipóteses de restituição de recursos', 'Art. 42, IX.', 'textarea', true, NULL, false),
  ('6. Controle e responsabilidades', 1, 'livre_acesso', 'Livre acesso dos agentes de controle e do Tribunal de Contas', 'Art. 42, XIII.', 'textarea', true, NULL, false),
  ('6. Controle e responsabilidades', 2, 'assuncao_objeto', 'Prerrogativa de assumir ou transferir a execução em caso de paralisação', 'Art. 42, XI.', 'textarea', false, NULL, false),
  ('6. Controle e responsabilidades', 3, 'responsabilidade_gestao', 'Responsabilidade exclusiva da organização pelo gerenciamento administrativo e financeiro', 'Art. 42, XVIII.', 'boolean', true, NULL, false),
  ('6. Controle e responsabilidades', 4, 'responsabilidade_encargos', 'Responsabilidade exclusiva da organização pelos encargos trabalhistas, previdenciários, fiscais e comerciais', 'Art. 42, XIX.', 'boolean', true, NULL, false),
  ('7. Encerramento', 1, 'rescisao', 'Condições de rescisão por qualquer dos partícipes', 'Art. 42, XIV.', 'textarea', true, NULL, false),
  ('7. Encerramento', 2, 'foro', 'Foro para dirimir dúvidas',
     'Art. 42, XVI. A lei exige tentativa prévia de solução administrativa com a participação da Advocacia Pública.', 'text', true, NULL, false),
  ('7. Encerramento', 3, 'assinaturas', 'Signatários', NULL, 'list', true, NULL, false)
) AS v(s, p, k, l, h, ft, req, der, ev);
