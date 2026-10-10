# Matriz perfil × jornada × permissão × dado × ação — v0.30.0

> GERADA por `scripts/make_profile_journey_matrix.py` a partir das jornadas executadas (`docs/evidence/jornadas_v0250/relatorio.json`),
> da matriz de autorização (`API_AUTHORIZATION_MATRIX.csv`) e do mapa tela → operação (`screen_backend_map.json`). Não edite à mão.
> Cada linha é um passo REALMENTE executado pela API na última regressão (status HTTP registrado), com o que a autorização exige
> para aquele passo e as telas que o alcançam. 'sem tela' é fato medido, não falha.

Jornadas: **16** · passos: **274** · falhas: **0**

## Perfis e o que cada um percorre

| Perfil | Passos executados | Jornadas em que aparece |
| --- | ---: | --- |
| OSC / executora | 160 | 15 |
| Financiador (empresa/instituto) | 50 | 8 |
| Administração / auditoria | 25 | 6 |
| Profissional / prestador | 12 | 4 |
| Apoiador (pessoa física) | 11 | 3 |
| Governo / órgão | 9 | 1 |
| Visitante | 4 | 2 |
| controller | 2 | 1 |
| Suporte | 1 | 1 |

## Preparação: contas de demonstração e plano concedido pela administração

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Administração / auditoria | confirma a identidade (operação sensível) | `POST /v1/auth/reauth` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 2 | Administração / auditoria | administração concede plano osc_premium (osc) | `POST /v1/admin/organizations/{id}/grants` | 201 | plataforma_com_permissao · papel ≥ — · tipos: todos | billing.write | /admin/cobranca, /admin/organizacoes |
| 3 | Administração / auditoria | administração concede plano company_premium (company) | `POST /v1/admin/organizations/{id}/grants` | 201 | plataforma_com_permissao · papel ≥ — · tipos: todos | billing.write | /admin/cobranca, /admin/organizacoes |
| 4 | Administração / auditoria | administração concede plano provider_premium (provider) | `POST /v1/admin/organizations/{id}/grants` | 201 | plataforma_com_permissao · papel ≥ — · tipos: todos | billing.write | /admin/cobranca, /admin/organizacoes |
| 5 | Administração / auditoria | administração concede plano gov_institutional (government) | `POST /v1/admin/organizations/{id}/grants` | 201 | plataforma_com_permissao · papel ≥ — · tipos: todos | billing.write | /admin/cobranca, /admin/organizacoes |
| 6 | Administração / auditoria | administração concede plano individual_basic (individual) | `POST /v1/admin/organizations/{id}/grants` | 201 | plataforma_com_permissao · papel ≥ — · tipos: todos | billing.write | /admin/cobranca, /admin/organizacoes |
| 7 | OSC / executora | OSC lista seus projetos | `GET /v1/projects` | 200 | organizacao_tipo_e_papel · papel ≥ viewer · tipos: osc | — | sem tela |
| 8 | Financiador (empresa/instituto) | empresa lista seus programas | `GET /v1/calls` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 9 | OSC / executora | OSC abre o projeto | `GET /v1/projects/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |

## OSC: projeto → diagnóstico → impacto

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | OSC / executora | cria projeto novo | `POST /v1/projects` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/novo |
| 2 | OSC / executora | orça o projeto novo | `POST /v1/projects/{id}/budget-items` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id, /projetos/novo |
| 3 | OSC / executora | publica o projeto novo | `POST /v1/projects/{id}/publish` | 200 | organizacao_tipo_e_papel · papel ≥ manager · tipos: osc | — | /projetos/:id |
| 4 | OSC / executora | abre diagnóstico do projeto | `POST /v1/diagnoses` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /diagnosticos |
| 5 | OSC / executora | preenche o diagnóstico | `PUT /v1/diagnoses/{id}` | 200 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /diagnosticos/:id |
| 6 | OSC / executora | responde a etapa de contexto do roteiro | `PUT /v1/diagnoses/{id}/guide/context` | 200 | ? · papel ≥ — · tipos: todos | — | sem tela |
| 7 | OSC / executora | aplica o diagnóstico ao projeto | `POST /v1/diagnoses/{id}/apply` | 200 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /diagnosticos/:id |
| 8 | OSC / executora | grava a versão 1 do diagnóstico | `POST /v1/diagnoses/{id}/versions` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /diagnosticos/:id/versoes |
| 9 | OSC / executora | lê a análise de prontidão (8 dimensões) | `GET /v1/diagnoses/{id}/analysis` | 200 | organizacao_tipo_e_papel · papel ≥ viewer · tipos: osc | — | sem tela |
| 10 | OSC / executora | declara contexto de equidade | `PUT /v1/projects/{id}/equity/context` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | sem tela |
| 11 | OSC / executora | declara denominador com fonte | `POST /v1/equity/denominators` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | sem tela |
| 12 | OSC / executora | alinha ODS (declarado) | `PUT /v1/projects/{id}/ods-targets` | 200 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id/ods |
| 13 | OSC / executora | consulta catálogo de indicadores | `GET /v1/indicators/catalog` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 14 | OSC / executora | cria indicador com linha de base e fonte | `POST /v1/projects/{id}/indicators` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id/impacto |
| 15 | OSC / executora | registra evidência (2026-05-13) | `POST /v1/projects/{id}/evidences` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id |
| 16 | OSC / executora | registra medição 8 em 2026-05-13 | `POST /v1/project-indicators/{id}/values` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id/impacto |
| 17 | OSC / executora | registra evidência (2026-07-02) | `POST /v1/projects/{id}/evidences` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id |
| 18 | OSC / executora | registra medição 17 em 2026-07-02 | `POST /v1/project-indicators/{id}/values` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id/impacto |
| 19 | OSC / executora | registra evidência (2026-08-21) | `POST /v1/projects/{id}/evidences` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id |
| 20 | OSC / executora | registra medição 26 em 2026-08-21 | `POST /v1/project-indicators/{id}/values` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id/impacto |
| 21 | OSC / executora | registra evidência (2026-10-05) | `POST /v1/projects/{id}/evidences` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id |
| 22 | OSC / executora | registra medição 33 em 2026-10-05 | `POST /v1/project-indicators/{id}/values` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id/impacto |
| 23 | OSC / executora | registra risco | `POST /v1/projects/{id}/risks` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /projetos/:id/riscos |
| 24 | OSC / executora | grava retrato do projeto | `POST /v1/projects/{id}/snapshots` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /projetos/:id/retratos |
| 25 | OSC / executora | consulta os papéis de responsabilidade | `GET /v1/responsibility/roles` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 26 | OSC / executora | designa responsável (organization) | `POST /v1/responsibility/assignments` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | sem tela |
| 27 | OSC / executora | registra decisão do responsável | `POST /v1/responsibility/decisions` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | sem tela |
| 28 | OSC / executora | designa responsável (project) | `POST /v1/responsibility/assignments` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | sem tela |

## Financiador: edital → candidatura → aporte → validação

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Financiador (empresa/instituto) | declara perfil de financiador | `PUT /v1/org/funder-profile` | 200 | organizacao_tipo_e_papel · papel ≥ manager · tipos: company|individual | — | /organizacao |
| 2 | OSC / executora | OSC vê o match do edital com o projeto | `GET /v1/calls/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 3 | OSC / executora | OSC abre candidatura | `POST /v1/applications` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /oportunidades/:id |
| 4 | OSC / executora | OSC lê os passos da candidatura | `GET /v1/applications/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 5 | OSC / executora | OSC escreve o plano de trabalho (rascunho) | `POST /v1/drafts` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /rascunhos |
| 6 | OSC / executora | pede código de assinatura (draft) | `POST /v1/signatures/challenge` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 7 | OSC / executora | assina (draft) | `POST /v1/signatures` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /rascunhos/:id, /revisoes/:id |
| 8 | OSC / executora | OSC conclui o passo 'requirements' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 9 | OSC / executora | OSC conclui o passo 'req_plano_trabalho' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 10 | OSC / executora | OSC conclui o passo 'proposal' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 11 | OSC / executora | OSC conclui o passo 'budget' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 12 | OSC / executora | OSC conclui o passo 'signature' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 13 | OSC / executora | OSC conclui o passo 'submission' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 14 | OSC / executora | OSC envia a candidatura | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 15 | Financiador (empresa/instituto) | avaliador move para screening | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 16 | Financiador (empresa/instituto) | avaliador move para due_diligence | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 17 | Financiador (empresa/instituto) | avaliador declara não ter conflito | `POST /v1/applications/{id}/conflict` | 200 | organizacao_tipo_e_papel · papel ≥ analyst · tipos: company|government|individual | — | /candidaturas/:id |
| 18 | Financiador (empresa/instituto) | avaliador aprova | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 19 | Financiador (empresa/instituto) | financiador registra o aporte comprometido | `POST /v1/applications/{id}/commitments` | 201 | organizacao_tipo_e_papel · papel ≥ manager · tipos: company|government|individual | — | /candidaturas/:id |
| 20 | Financiador (empresa/instituto) | financiador informa o desembolso | `POST /v1/commitments/{id}/status` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /candidaturas/:id |
| 21 | OSC / executora | OSC confirma o recebimento | `POST /v1/commitments/{id}/status` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /candidaturas/:id |
| 22 | Financiador (empresa/instituto) | financiador registra pagamento | `POST /v1/commitments/{id}/payments` | 201 | organizacao_tipo_e_papel · papel ≥ manager · tipos: company|government|individual | — | sem tela |
| 23 | Financiador (empresa/instituto) | pagamento aguarda confirmação | `POST /v1/payments/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /pagamentos/:id |
| 24 | OSC / executora | OSC confirma o pagamento | `POST /v1/payments/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /pagamentos/:id |
| 25 | OSC / executora | OSC inicia a execução | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 26 | Financiador (empresa/instituto) | financiador valida medição | `POST /v1/indicator-values/{id}/review` | 200 | organizacao_tipo_e_papel · papel ≥ analyst · tipos: company|government|individual | — | /projetos/:id/impacto |
| 27 | Financiador (empresa/instituto) | financiador valida medição | `POST /v1/indicator-values/{id}/review` | 200 | organizacao_tipo_e_papel · papel ≥ analyst · tipos: company|government|individual | — | /projetos/:id/impacto |
| 28 | Financiador (empresa/instituto) | financiador valida medição | `POST /v1/indicator-values/{id}/review` | 200 | organizacao_tipo_e_papel · papel ≥ analyst · tipos: company|government|individual | — | /projetos/:id/impacto |
| 29 | Financiador (empresa/instituto) | financiador vê a série do projeto (reportado × validado) | `GET /v1/projects/{id}/impact` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |

## Rede: proposta → conversa → prestação de contas

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Financiador (empresa/instituto) | financiador propõe apoio | `POST /v1/proposals` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /propostas/nova |
| 2 | Financiador (empresa/instituto) | financiador envia a proposta | `POST /v1/proposals/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /propostas/:id |
| 3 | OSC / executora | OSC abre a proposta | `GET /v1/proposals/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 4 | OSC / executora | OSC aceita a proposta | `POST /v1/proposals/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /propostas/:id |
| 5 | Financiador (empresa/instituto) | financiador registra relação com a OSC | `POST /v1/network/relationships` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 6 | Financiador (empresa/instituto) | financiador abre conversa sobre o projeto | `POST /v1/conversations` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 7 | Financiador (empresa/instituto) | financiador escreve | `POST /v1/conversations/{id}/messages` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /conversas/:id |
| 8 | OSC / executora | OSC responde | `POST /v1/conversations/{id}/messages` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /conversas/:id |
| 9 | Financiador (empresa/instituto) | financiador manda mensagem direta | `POST /v1/messages/{id}` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /mensagens, /mensagens/:id |
| 10 | OSC / executora | OSC escreve relatório de impacto do período | `POST /v1/impact-updates` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /projetos/:id/relatorios |
| 11 | OSC / executora | OSC envia o relatório ao apoiador | `POST /v1/impact-updates/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /relatorios-impacto/:id |
| 12 | Financiador (empresa/instituto) | apoiador aceita o relatório | `POST /v1/impact-updates/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /relatorios-impacto/:id |

## Profissional: necessidade → oferta → revisão técnica

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Profissional / prestador | profissional declara perfil | `PUT /v1/org/provider-profile` | 200 | organizacao_tipo_e_papel · papel ≥ manager · tipos: provider | — | /organizacao |
| 2 | OSC / executora | OSC publica necessidade do projeto | `POST /v1/projects/{id}/needs` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id/apoio-profissional |
| 3 | Profissional / prestador | profissional oferece ajuda | `POST /v1/needs/{id}/offers` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: provider | — | /oportunidades-profissionais |
| 4 | OSC / executora | OSC aceita a oferta | `POST /v1/offers/{id}/decide` | 200 | organizacao_tipo_e_papel · papel ≥ manager · tipos: osc | — | /necessidades/:id |
| 5 | Profissional / prestador | profissional lista suas credenciais | `GET /v1/org/credentials` | 200 | organizacao_tipo_e_papel · papel ≥ viewer · tipos: provider | — | sem tela |
| 6 | OSC / executora | OSC escreve justificativa orçamentária | `POST /v1/drafts` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /rascunhos |
| 7 | OSC / executora | OSC pede revisão técnica ao profissional | `POST /v1/professional-reviews` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /profissionais |
| 8 | Profissional / prestador | profissional aceita a revisão | `POST /v1/professional-reviews/{id}/respond` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /revisoes/:id |
| 9 | Profissional / prestador | profissional aprova com credencial verificada | `POST /v1/professional-reviews/{id}/respond` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /revisoes/:id |

## Governo: edital público → necessidade do território

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Governo / órgão | governo publica chamamento | `POST /v1/calls` | 201 | organizacao_tipo_e_papel · papel ≥ manager · tipos: company|government | — | /editais/:id/editar, /editais/novo |
| 2 | OSC / executora | OSC abre candidatura | `POST /v1/applications` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /oportunidades/:id |
| 3 | OSC / executora | OSC lê os passos da candidatura | `GET /v1/applications/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 4 | OSC / executora | OSC escreve o plano de trabalho (rascunho) | `POST /v1/drafts` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /rascunhos |
| 5 | OSC / executora | pede código de assinatura (draft) | `POST /v1/signatures/challenge` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 6 | OSC / executora | assina (draft) | `POST /v1/signatures` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /rascunhos/:id, /revisoes/:id |
| 7 | OSC / executora | OSC conclui o passo 'requirements' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 8 | OSC / executora | OSC conclui o passo 'proposal' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 9 | OSC / executora | OSC conclui o passo 'budget' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 10 | OSC / executora | OSC conclui o passo 'signature' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 11 | OSC / executora | OSC conclui o passo 'submission' | `PATCH /v1/applications/{id}/steps/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 12 | OSC / executora | OSC envia a candidatura | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 13 | Governo / órgão | governo lista as candidaturas do chamamento | `GET /v1/calls/{id}/applications` | 200 | organizacao_tipo_e_papel · papel ≥ analyst · tipos: company|government | — | sem tela |
| 14 | Governo / órgão | avaliador move para screening | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 15 | Governo / órgão | avaliador move para due_diligence | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 16 | Governo / órgão | avaliador declara não ter conflito | `POST /v1/applications/{id}/conflict` | 200 | organizacao_tipo_e_papel · papel ≥ analyst · tipos: company|government|individual | — | /candidaturas/:id |
| 17 | Governo / órgão | avaliador aprova | `POST /v1/applications/{id}/transition` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /candidaturas/:id |
| 18 | Governo / órgão | governo acompanha a carteira | `GET /v1/portfolio` | 200 | organizacao_tipo_e_papel · papel ≥ viewer · tipos: company|government|individual | — | sem tela |
| 19 | OSC / executora | OSC publica um terceiro projeto no território | `POST /v1/projects` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/novo |
| 20 | OSC / executora | orça o terceiro projeto | `POST /v1/projects/{id}/budget-items` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id, /projetos/novo |
| 21 | OSC / executora | publica o terceiro projeto | `POST /v1/projects/{id}/publish` | 200 | organizacao_tipo_e_papel · papel ≥ manager · tipos: osc | — | /projetos/:id |
| 22 | Governo / órgão | governo abre a torre territorial (território → programas → OSCs → projetos → indicadores → lacunas) | `GET /v1/control-tower/government` | 200 | organizacao_tipo_e_papel · papel ≥ viewer · tipos: government|platform | — | sem tela |
| 23 | Financiador (empresa/instituto) | empresa abre a torre de controle (meu capital → ... → o que preciso decidir) | `GET /v1/control-tower/funder` | 200 | organizacao_tipo_e_papel · papel ≥ viewer · tipos: company|individual | — | sem tela |
| 24 | Financiador (empresa/instituto) | financiador confere o estado IMPACTO Ready do projeto apoiado | `GET /v1/projects/{id}/ready` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 25 | Governo / órgão | governo registra necessidade do território com fonte | `POST /v1/territory/needs` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /territorio/necessidades |

## Captação: cotas → apoios → campanha pública

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | OSC / executora | OSC cria cota de apoio | `POST /v1/funding-quotas` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /cotas |
| 2 | OSC / executora | OSC abre a cota | `PATCH /v1/funding-quotas/{id}` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /cotas |
| 3 | Financiador (empresa/instituto) | empresa apoia 3 cotas | `POST /v1/funding-quotas/{id}/pledges` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 4 | Apoiador (pessoa física) | apoiadora apoia 1 cota | `POST /v1/funding-quotas/{id}/pledges` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 5 | Apoiador (pessoa física) | apoiadora declara interesse e causas | `PUT /v1/org/funder-profile` | 200 | organizacao_tipo_e_papel · papel ≥ manager · tipos: company|individual | — | /organizacao |
| 6 | Apoiador (pessoa física) | apoiadora manifesta interesse no projeto da horta | `POST /v1/applications/interest` | 201 | organizacao_tipo_e_papel · papel ≥ analyst · tipos: company|individual | — | /projetos/:id |
| 7 | OSC / executora | OSC cria campanha | `POST /v1/campaigns` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /campanha-gestao |
| 8 | OSC / executora | OSC envia a campanha para revisão (aceita os termos) | `POST /v1/campaigns/{id}/submit` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | sem tela |
| 9 | Administração / auditoria | administração aprova a campanha com justificativa | `POST /v1/admin/donation-campaigns/{id}/review` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | compliance.write | /admin/doacoes |
| 10 | Administração / auditoria | administração registra o beneficiário como verificado | `POST /v1/admin/beneficiaries/{id}/verification` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | compliance.write | /admin/doacoes |
| 11 | controller | confirma a identidade (operação sensível) | `POST /v1/auth/reauth` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 12 | controller | controladoria confirma a verificação (segunda pessoa, quatro olhos) | `POST /v1/admin/beneficiaries/{id}/verification/{id}/confirm` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | compliance.write | /admin/doacoes |
| 13 | OSC / executora | OSC publica a campanha | `POST /v1/campaigns/{id}/publish` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | sem tela |
| 14 | Visitante | pessoa anônima inicia uma doação Pix (sandbox, não pagável) | `POST /v1/public/donation-campaigns/orquestra-comunitaria-{slug}/donate` | 201 | ? · papel ≥ — · tipos: todos | — | sem tela |
| 15 | Visitante | pessoa anônima consulta a situação da doação | `GET /v1/public/donations/{id}` | 200 | publica · papel ≥ — · tipos: todos | — | sem tela |
| 16 | Financiador (empresa/instituto) | empresa inicia doação em nome da organização (sandbox) | `POST /v1/public/donation-campaigns/orquestra-comunitaria-{slug}/donate` | 201 | ? · papel ≥ — · tipos: todos | — | sem tela |
| 17 | Financiador (empresa/instituto) | empresa registra compromisso de doação futura | `POST /v1/public/donation-campaigns/orquestra-comunitaria-{slug}/pledge` | 201 | ? · papel ≥ — · tipos: todos | — | sem tela |
| 18 | OSC / executora | OSC declara recurso recebido fora da plataforma | `POST /v1/campaigns/{id}/external-resources` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | sem tela |
| 19 | OSC / executora | OSC abre a prestação de contas com os estados do dinheiro | `GET /v1/campaigns/{id}/accountability` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 20 | OSC / executora | OSC vê a política 'gratuito até gerar valor' e suas obrigações | `GET /v1/org/remuneration` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 21 | Financiador (empresa/instituto) | empresa vê o painel do financiador | `GET /v1/org/contributions` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 22 | Administração / auditoria | administração vê obrigações por estado (nenhuma devida) | `GET /v1/admin/remuneration` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | finance.read | sem tela |
| 23 | Administração / auditoria | administração vê a fila de conciliação | `GET /v1/admin/reconciliation/exceptions` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | finance.read | sem tela |
| 24 | Visitante | visitante sem login abre a campanha | `GET /v1/public/campaigns/orquestra-comunitaria-{slug}` | 200 | ? · papel ≥ — · tipos: todos | — | sem tela |

## Documentos: montagem → acordo assinado → registro verificável

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | OSC / executora | lista modelos publicados | `GET /v1/document-templates` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 2 | OSC / executora | monta plano de monitoramento a partir do projeto | `POST /v1/document-assemblies` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /documentos/montagens |
| 3 | OSC / executora | lê os campos da montagem | `GET /v1/document-assemblies/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 4 | OSC / executora | preenche campos e anexa evidências | `PUT /v1/document-assemblies/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /documentos/montagens/:id |
| 5 | OSC / executora | gera o documento | `POST /v1/document-assemblies/{id}/generate` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /documentos/montagens/:id |
| 6 | OSC / executora | envia o contrato | `POST /v1/documents` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 7 | OSC / executora | cria acordo com o profissional | `POST /v1/signed-agreements` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/novo |
| 8 | OSC / executora | inclui o profissional como parte | `POST /v1/signed-agreements/{id}/parties` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 9 | OSC / executora | publica para assinatura | `POST /v1/signed-agreements/{id}/publish` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 10 | OSC / executora | pede código de assinatura (agreement) | `POST /v1/signatures/challenge` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 11 | OSC / executora | assina (agreement) | `POST /v1/signed-agreements/{id}/sign` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | sem tela |
| 12 | Profissional / prestador | pede código de assinatura (agreement) | `POST /v1/signatures/challenge` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 13 | Profissional / prestador | assina (agreement) | `POST /v1/signed-agreements/{id}/sign` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | sem tela |
| 14 | OSC / executora | emite registro verificável do acordo | `POST /v1/verifiable-records` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 15 | Visitante | visitante confere o registro sem login | `GET /v1/public/verify/IMP-{code}` | 200 | ? · papel ≥ — · tipos: todos | — | sem tela |
| 16 | OSC / executora | abre compra do projeto | `POST /v1/projects/{id}/procurement` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /projetos/:id/compras |
| 17 | OSC / executora | registra orçamento (Loja Exemplo A) | `POST /v1/procurement/{id}/quotes` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /compras/:id |
| 18 | OSC / executora | registra orçamento (Loja Exemplo B) | `POST /v1/procurement/{id}/quotes` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /compras/:id |
| 19 | OSC / executora | registra orçamento (Loja Exemplo C) | `POST /v1/procurement/{id}/quotes` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /compras/:id |
| 20 | OSC / executora | decide pelo menor orçamento | `POST /v1/procurement/{id}/decide` | 200 | organizacao_tipo_e_papel · papel ≥ manager · tipos: osc | — | /compras/:id |

## Contrato como regra: financiamento → vigência → entrega → aceite → obrigações → nova versão

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Apoiador (pessoa física) | apoiadora registra a ideia na biblioteca de soluções | `POST /v1/solutions` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc|individual|company|government|provider | — | /solucoes/:id/editar, /solucoes/nova |
| 2 | Apoiador (pessoa física) | apoiadora publica a ideia | `POST /v1/solutions/{id}/publish` | 200 | organizacao_tipo_e_papel · papel ≥ admin · tipos: osc|individual|company|government|provider | — | /solucoes/:id |
| 3 | OSC / executora | OSC propõe participação de autoria à apoiadora (1,5% quando elegível; nunca automática) | `POST /v1/projects/{id}/participations` | 201 | organizacao_tipo_e_papel · papel ≥ manager · tipos: osc | — | sem tela |
| 4 | Apoiador (pessoa física) | apoiadora aceita a participação (projeto já publicado → consolidada) | `POST /v1/participations/{id}/accept` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /participacoes |
| 5 | Apoiador (pessoa física) | apoiadora acompanha as próprias participações | `GET /v1/participations` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 6 | OSC / executora | OSC cria acordo de financiamento (camada econômica vem do catálogo 2027.02: 3,5% plataforma + 1,5% autoria, aporte único direcionado) | `POST /v1/signed-agreements` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/novo |
| 7 | OSC / executora | inclui a empresa como financiadora | `POST /v1/signed-agreements/{id}/parties` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 8 | OSC / executora | confirma a identidade (operação sensível) | `POST /v1/auth/reauth` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 9 | OSC / executora | quem recebe informa a própria chave PIX no contrato | `PUT /v1/signed-agreements/{id}/parties/{id}/pix` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 10 | OSC / executora | inclui a apoiadora como proponente (parte opcional) | `POST /v1/signed-agreements/{id}/parties` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 11 | Apoiador (pessoa física) | confirma a identidade (operação sensível) | `POST /v1/auth/reauth` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 12 | Apoiador (pessoa física) | apoiadora informa a própria chave PIX | `PUT /v1/signed-agreements/{id}/parties/{id}/pix` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 13 | OSC / executora | define o marco 1: Compra dos instrumentos | `POST /v1/signed-agreements/{id}/milestones` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 14 | OSC / executora | define o marco 2: Primeiro semestre de aulas | `POST /v1/signed-agreements/{id}/milestones` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 15 | OSC / executora | publica para assinatura (versão 1 congelada) | `POST /v1/signed-agreements/{id}/publish` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 16 | Financiador (empresa/instituto) | financiador vê a PRÉVIA da distribuição antes de assinar (95.000 projeto / 3.500 plataforma / 1.500 autoria, nada gravado) | `GET /v1/signed-agreements/{id}/allocation` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 17 | OSC / executora | pede código de assinatura (agreement) | `POST /v1/signatures/challenge` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 18 | OSC / executora | assina (agreement) | `POST /v1/signed-agreements/{id}/sign` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | sem tela |
| 19 | Financiador (empresa/instituto) | pede código de assinatura (agreement) | `POST /v1/signatures/challenge` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 20 | Financiador (empresa/instituto) | assina (agreement) | `POST /v1/signed-agreements/{id}/sign` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | sem tela |
| 21 | OSC / executora | acordo vigente: matriz gravada, obrigações derivadas, taxa registrada e NÃO cobrada (regra desligada) | `GET /v1/signed-agreements/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 22 | Financiador (empresa/instituto) | financiador abre as instruções de repasse (quem, quanto, por qual chave) | `GET /v1/signed-agreements/{id}/payouts` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 23 | Financiador (empresa/instituto) | financiador registra a transferência PIX feita ao projeto (a qualquer momento) | `POST /v1/payouts/{id}/transfers` | 201 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 24 | OSC / executora | OSC (quem recebe) confirma o recebimento — quem paga nunca confirma | `POST /v1/payout-transfers/{id}/confirm` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 25 | Financiador (empresa/instituto) | financiador tenta confirmar o que ele mesmo pagou → recusado | `POST /v1/payout-transfers/{id}/confirm` | 403 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 26 | Financiador (empresa/instituto) | financiador registra a transferência da participação de autoria à apoiadora | `POST /v1/payouts/{id}/transfers` | 201 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 27 | Apoiador (pessoa física) | apoiadora confirma o recebimento da participação | `POST /v1/payout-transfers/{id}/confirm` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 28 | Financiador (empresa/instituto) | o que o IMPACTO fez nesta operação (por registro) | `GET /v1/signed-agreements/{id}/value` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 29 | OSC / executora | OSC registra a entrega do marco 1 | `PATCH /v1/signed-agreements/{id}/milestones/{id}` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 30 | OSC / executora | OSC tenta aceitar a própria entrega → recusado (quatro olhos) | `PATCH /v1/signed-agreements/{id}/milestones/{id}` | 403 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 31 | Financiador (empresa/instituto) | financiador vê o que precisa da sua decisão | `GET /v1/agreements/pending` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 32 | Financiador (empresa/instituto) | financiador aceita a entrega do marco 1 → obrigação de pagar nasce com prazo | `PATCH /v1/signed-agreements/{id}/milestones/{id}` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 33 | OSC / executora | OSC registra a entrega do marco 2 | `PATCH /v1/signed-agreements/{id}/milestones/{id}` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 34 | Financiador (empresa/instituto) | financiador recusa o marco 2 com motivo (volta para quem executa) | `PATCH /v1/signed-agreements/{id}/milestones/{id}` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 35 | OSC / executora | razão do projeto registra ativação, alocação, entrega e aceite em cadeia | `GET /v1/projects/{id}/ledger` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 36 | OSC / executora | mudança no contrato → nova versão em rascunho; a anterior fica substituída e exige nova assinatura | `POST /v1/signed-agreements/{id}/new-version` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 37 | Financiador (empresa/instituto) | versão antiga não recebe assinatura (substituída) | `POST /v1/signed-agreements/{id}/sign` | 409 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | sem tela |

## Marketplace, soluções e perfis públicos

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | OSC / executora | OSC anuncia o projeto no marketplace | `POST /v1/marketplace/listings` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /marketplace/novo |
| 2 | OSC / executora | OSC publica o anúncio | `POST /v1/marketplace/listings/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /marketplace/meus |
| 3 | OSC / executora | OSC cadastra a metodologia como solução | `POST /v1/solutions` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc|individual|company|government|provider | — | /solucoes/:id/editar, /solucoes/nova |
| 4 | OSC / executora | OSC publica a solução | `POST /v1/solutions/{id}/publish` | 200 | organizacao_tipo_e_papel · papel ≥ admin · tipos: osc|individual|company|government|provider | — | /solucoes/:id |
| 5 | OSC / executora | osc cria perfil público | `POST /v1/profiles` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /perfil-publico |
| 6 | Profissional / prestador | provider cria perfil público | `POST /v1/profiles` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /perfil-publico |

## Caminho dourado: acordo → aporte direcionado → confirmação → entrega aceita → quitação → reconhecimento → torre

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | OSC / executora | OSC cria acordo de financiamento complementar (R$ 20.000, um marco) | `POST /v1/signed-agreements` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/novo |
| 2 | OSC / executora | inclui a empresa como financiadora | `POST /v1/signed-agreements/{id}/parties` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 3 | OSC / executora | confirma a identidade (operação sensível) | `POST /v1/auth/reauth` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 4 | OSC / executora | OSC informa a chave PIX no contrato | `PUT /v1/signed-agreements/{id}/parties/{id}/pix` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 5 | OSC / executora | define o único marco | `POST /v1/signed-agreements/{id}/milestones` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 6 | OSC / executora | publica para assinatura | `POST /v1/signed-agreements/{id}/publish` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 7 | OSC / executora | pede código de assinatura (agreement) | `POST /v1/signatures/challenge` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 8 | OSC / executora | assina (agreement) | `POST /v1/signed-agreements/{id}/sign` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | sem tela |
| 9 | Financiador (empresa/instituto) | pede código de assinatura (agreement) | `POST /v1/signatures/challenge` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | sem tela |
| 10 | Financiador (empresa/instituto) | assina (agreement) | `POST /v1/signed-agreements/{id}/sign` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | sem tela |
| 11 | Financiador (empresa/instituto) | instruções de repasse: projeto (19.000) e plataforma (700, aguardando regra) | `GET /v1/signed-agreements/{id}/payouts` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 12 | Financiador (empresa/instituto) | financiador registra o aporte ao projeto | `POST /v1/payouts/{id}/transfers` | 201 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 13 | OSC / executora | OSC confirma o recebimento | `POST /v1/payout-transfers/{id}/confirm` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 14 | OSC / executora | OSC concilia o repasse com nota | `POST /v1/payouts/{id}/reconcile` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /acordos/:id |
| 15 | OSC / executora | OSC registra a entrega | `PATCH /v1/signed-agreements/{id}/milestones/{id}` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 16 | Financiador (empresa/instituto) | financiador aceita a entrega → operação QUITADA (todo repasse devido confirmado) | `PATCH /v1/signed-agreements/{id}/milestones/{id}` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /acordos/:id |
| 17 | OSC / executora | acordo concluído: quitação derivada dos repasses | `GET /v1/signed-agreements/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 18 | OSC / executora | reconhecimentos nascem da quitação: OSC vê a trajetória crescer em 'Para você hoje' | `GET /v1/me/today` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 19 | Financiador (empresa/instituto) | financiador também: aporte integralmente confirmado | `GET /v1/me/today` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 20 | OSC / executora | perfil público da OSC carrega a trajetória (contagens e datas, nunca valores) | `GET /v1/profiles/mine` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 21 | Financiador (empresa/instituto) | o que o IMPACTO fez nesta operação | `GET /v1/signed-agreements/{id}/value` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 22 | OSC / executora | acesso sem assinatura: de onde vem o direito da OSC | `GET /v1/billing` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 23 | OSC / executora | catálogo público: pacotes e vias de acesso, nenhum preço recorrente | `GET /v1/plans` | 200 | publica · papel ≥ — · tipos: todos | — | sem tela |
| 24 | Financiador (empresa/instituto) | regras do catálogo econômico (versão vigente) | `GET /v1/economic-rules` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 25 | Administração / auditoria | confirma a identidade (operação sensível) | `POST /v1/auth/reauth` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 26 | Administração / auditoria | torre MASTER: GMV × camada da plataforma, banco NÃO CONECTADO, captura de valor | `GET /v1/control-tower/master` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | finance.read | sem tela |
| 27 | Administração / auditoria | administração propõe contrato avulso à OSC (valor e motivo de quem tem alçada) | `POST /v1/admin/commercial/offers` | 201 | plataforma_com_permissao · papel ≥ — · tipos: todos | finance.approve | sem tela |
| 28 | OSC / executora | OSC aceita com autorização de cobrança → pacote concedido pelo contrato | `POST /v1/commercial/offers/{id}/accept` | 200 | organizacao_por_papel · papel ≥ owner · tipos: todos | — | /conta/comercial |
| 29 | OSC / executora | estado comercial: CONTRATADO | `GET /v1/commercial/state` | 200 | organizacao · papel ≥ — · tipos: todos | — | sem tela |

## Central de IA: cota → prévia → originalidade → patrocínio → pedido piloto → painel

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | OSC / executora | OSC abre a Central de IA: cota de boas-vindas concedida, operações com preço e quem paga | `GET /v1/ai/center` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 2 | OSC / executora | prévia da originalidade: 49 créditos, pagos pela cota gratuita, motor local | `POST /v1/ai/preview` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 3 | OSC / executora | OSC confirma: originalidade do projeto em oito dimensões (cobra só em sucesso) | `POST /v1/projects/{id}/similarity` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 4 | OSC / executora | lê a análise: leituras separadas, recomendações, revisão humana, contagem k-anônima do invisível | `GET /v1/similarity/analyses/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 5 | OSC / executora | mesmos dados → resultado já calculado, sem nova cobrança | `POST /v1/projects/{id}/similarity` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 6 | OSC / executora | OSC contesta um ponto (vai para revisão humana) | `POST /v1/similarity/analyses/{id}/dispute` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /ia/analises/:id |
| 7 | OSC / executora | sem fonte de custeio (cota restante 21 < 29): a plataforma RECUSA e lista as opções; nada executa | `POST /v1/projects/{id}/similarity` | 402 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 8 | Financiador (empresa/instituto) | financiador abre a Central de IA (sem patrocínio ainda) | `GET /v1/ai/center` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 9 | Financiador (empresa/instituto) | financiador patrocina uso de IA para OSCs: compromete créditos do próprio saldo | `POST /v1/ai/sponsorships` | 201 | organizacao_tipo_e_papel · papel ≥ admin · tipos: company|government|osc | — | /ia |
| 10 | OSC / executora | agora a complementaridade é custeada pelo patrocínio: a OSC não paga nada | `POST /v1/projects/{id}/similarity` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 11 | Financiador (empresa/instituto) | prestação de contas agregada ao patrocinador | `GET /v1/ai/sponsorships/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 12 | OSC / executora | OSC faz um pedido de créditos: modo PILOTO (regra comercial inativa), nenhum pagamento | `POST /v1/ai/credit-orders` | 201 | organizacao_por_papel · papel ≥ admin · tipos: todos | — | /ia |
| 13 | OSC / executora | catálogo de pacotes e modo de venda | `GET /v1/ai/credit-packs` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 14 | Administração / auditoria | confirma a identidade (operação sensível) | `POST /v1/auth/reauth` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 15 | Administração / auditoria | administração aprova o pedido piloto como concessão PROMOCIONAL (nunca compra) | `POST /v1/admin/ai/credit-orders/{id}/approve-pilot` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | billing.write | /admin/ia/financeiro |
| 16 | Administração / auditoria | painel financeiro da IA: medido × NÃO MEDIDO, obrigações com clientes, alertas | `GET /v1/admin/ai/finance` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | finance.read | sem tela |
| 17 | Administração / auditoria | contestações aguardando revisão humana | `GET /v1/admin/ai/disputes` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | support.read | sem tela |
| 18 | OSC / executora | OSC vê o histórico de execuções e o extrato | `GET /v1/ai/executions` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |

## Suporte e Central de Conhecimento

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | OSC / executora | OSC abre chamado | `POST /v1/support/tickets` | 201 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | /ajuda/suporte/novo |
| 2 | Suporte | suporte responde o chamado | `POST /v1/admin/support/tickets/{id}/messages` | 201 | plataforma · papel ≥ — · tipos: todos | MFA | /admin/central/suporte/:id |
| 3 | OSC / executora | OSC lê a resposta | `GET /v1/support/tickets/{id}` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | /ajuda/suporte/:id |
| 4 | OSC / executora | OSC lista cursos | `GET /v1/help/courses` | 200 | publica · papel ≥ — · tipos: todos | — | /ajuda/academia |

## Banco de Ideias: ideia → amadurecimento → projeto

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | OSC / executora | OSC registra ideia | `POST /v1/ideas` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /ideias |
| 2 | OSC / executora | OSC amadurece a ideia (hipótese, público, impacto) | `PUT /v1/ideas/{id}` | 200 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /ideias |
| 3 | OSC / executora | OSC abre a ideia | `GET /v1/ideas/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |
| 4 | OSC / executora | OSC transforma a ideia em projeto | `POST /v1/ideas/{id}/promote` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: osc | — | /ideias |
| 5 | OSC / executora | OSC abre o projeto criado | `GET /v1/projects/{id}` | 200 | organizacao · papel ≥ viewer · tipos: todos | — | sem tela |

## Administração: visão geral → verificação → auditoria

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Administração / auditoria | abre a visão geral | `GET /v1/admin/overview` | 200 | plataforma · papel ≥ — · tipos: todos | MFA | sem tela |
| 2 | Administração / auditoria | lista organizações | `GET /v1/admin/organizations` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | admin.organizations.read | sem tela |
| 3 | Administração / auditoria | lista usuários | `GET /v1/admin/users` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | admin.users.read | sem tela |
| 4 | Administração / auditoria | classifica a solução nova como autodeclarada | `POST /v1/admin/solutions/{id}/verify` | 200 | plataforma · papel ≥ — · tipos: todos | MFA | /admin/solucoes |
| 5 | Administração / auditoria | confere a cadeia da auditoria | `GET /v1/admin/audit/verify` | 200 | plataforma · papel ≥ — · tipos: todos | MFA | sem tela |
| 6 | Administração / auditoria | confirma a identidade (operação sensível) | `POST /v1/auth/reauth` | 200 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | sem tela |
| 7 | Administração / auditoria | lê o estado do interruptor de emergência | `GET /v1/admin/kill-switch` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | security.kill_switch | sem tela |

## Pendências: o que espera decisão de alguém

| # | Perfil | Ação (passo) | Operação | Resultado | Autorização exigida | Permissão | Telas que chegam aqui |
| ---: | --- | --- | --- | ---: | --- | --- | --- |
| 1 | Profissional / prestador | profissional propõe serviço à OSC | `POST /v1/proposals` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /propostas/nova |
| 2 | Profissional / prestador | profissional envia (fica aguardando a OSC) | `POST /v1/proposals/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /propostas/:id |
| 3 | OSC / executora | OSC envia relatório do 2º período | `POST /v1/impact-updates` | 201 | organizacao_por_papel · papel ≥ member · tipos: todos | — | /projetos/:id/relatorios |
| 4 | OSC / executora | relatório aguarda análise do apoiador | `POST /v1/impact-updates/{id}/transition` | 200 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /relatorios-impacto/:id |
| 5 | OSC / executora | OSC declara afirmação de impacto | `POST /v1/claims` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /afirmacoes |
| 6 | OSC / executora | plataforma confere a afirmação | `POST /v1/claims/{id}/check` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /afirmacoes |
| 7 | OSC / executora | OSC declara afirmação de impacto | `POST /v1/claims` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /afirmacoes |
| 8 | OSC / executora | plataforma confere a afirmação | `POST /v1/claims/{id}/check` | 201 | organizacao_por_papel · papel ≥ manager · tipos: todos | — | /afirmacoes |
| 9 | Profissional / prestador | profissional declara experiência com a OSC (aguarda confirmação) | `POST /v1/profile/experiences` | 201 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | /perfil-publico/experiencias |
| 10 | Profissional / prestador | profissional cadastra nova credencial (aguarda conferência) | `POST /v1/org/credentials` | 201 | organizacao_tipo_e_papel · papel ≥ member · tipos: provider | — | /organizacao |
| 11 | Administração / auditoria | administração procura a organização em estruturação | `GET /v1/admin/organizations` | 200 | plataforma_com_permissao · papel ≥ — · tipos: todos | admin.organizations.read | sem tela |
| 12 | Apoiador (pessoa física) | apoiadora denuncia dado incorreto (vai para a moderação) | `POST /v1/reports` | 201 | usuario_sem_organizacao · papel ≥ — · tipos: todos | — | /solucoes/:id |

## Leitura

* Passos sem tela que os alcance diretamente: **109** de 274 — operações que a jornada exercita pela API e que a interface ainda não expõe (ou expõe por auxiliar compartilhado). O número oficial de operações sem tela é o de `screen_backend_map.json`.
* A autorização é aplicada no backend (classe + papel + tipo + permissão), provada por `test_v0230_api_sweep` para TODAS as operações — a coluna aqui é a mesma matriz, lida por jornada.
* Dado tocado: cada rota nomeia o recurso (projects, evidences, indicator-values, agreements, payouts…); a classe de retenção de cada tabela está em `config/data_retention.json` e é conferida por `test_v0190_lgpd_deletion`.
* Estados vazios, erros e bloqueios por perfil: cobertos pelo robô de telas (`test_v0250_todas_as_telas`: OK · vazia · recusa correta · sem registro) e pela jornada 'Pendências'.
