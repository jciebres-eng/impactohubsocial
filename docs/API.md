# API REST /v1 — referência gerada do código (v0.22.0)

Gerado por `scripts/gen_api_docs.py`. Contrato completo (schemas de entrada): `docs/openapi.json` ou `GET /v1/openapi.json`.

## Convenções

- Autenticação web: cookie httpOnly `__Host-impacto_at` + header `X-CSRF-Token` em métodos que alteram dados.
- Autenticação mobile/API: `POST /v1/auth/login` com header `X-Auth-Mode: token` → `Authorization: Bearer <access_token>`; renovação em `/v1/auth/refresh`.
- Erros: RFC 7807 (`application/problem+json`) com `code` estável, `request_id` e, em 5xx, `error_id` para suporte.
- Paginação: `limit` (1–100) e `offset`; respostas trazem `has_more` e `next_offset`.
- Dinheiro sempre em centavos (inteiro). Datas ISO 8601 (UTC).

## Operações (873)

| Método | Caminho | Acesso | Restrições | Descrição |
|---|---|---|---|---|
| POST | `/v1/access/check` | usuário autenticado | — | Posso executar esta ação? Devolve decisão com motivo, nunca só um booleano |
| GET | `/v1/admin/agreements` | admin da plataforma + MFA | — | Lista convênios (sem o código) |
| POST | `/v1/admin/agreements` | admin da plataforma + MFA | — | Cria convênio (rascunho). O código é exibido UMA vez; a ativação exige outro administrador. |
| POST | `/v1/admin/agreements/{agreement_id}/action` | admin da plataforma + MFA | — | Ativa (por outro administrador), suspende ou encerra um convênio |
| GET | `/v1/admin/agreements/{agreement_id}/members` | admin da plataforma + MFA | — | Organizações vinculadas ao convênio |
| POST | `/v1/admin/agreements/{agreement_id}/members/{org_id}/revoke` | admin da plataforma + MFA | — | Remove uma organização do convênio (revoga a licença e libera a vaga) |
| GET | `/v1/admin/ai/cost` | admin da plataforma + MFA | — | Custo estimado de IA por provedor, modelo e recurso — insumo da margem |
| POST | `/v1/admin/ai/prices` | admin da plataforma + MFA | — | Declara o preço de um modelo de IA (versionado, com fonte) |
| GET | `/v1/admin/audit` | admin da plataforma + MFA | — | audit search |
| GET | `/v1/admin/audit/verify` | admin da plataforma + MFA | — | Verifica a cadeia de hashes da trilha de auditoria |
| GET | `/v1/admin/billing/organizations/{org_id}` | admin da plataforma + MFA | — | Visão de suporte: assinatura, trial, licenças, descontos, faturas e eventos da organização |
| GET | `/v1/admin/call-sources` | admin da plataforma + MFA | — | list sources |
| POST | `/v1/admin/call-sources` | admin da plataforma + MFA | — | Cadastra fonte de importação (exige registro da verificação de termos de uso/licença da fonte) |
| POST | `/v1/admin/call-sources/{source_id}/run` | admin da plataforma + MFA | — | Importa agora (feed configurado) |
| POST | `/v1/admin/calls` | admin da plataforma + MFA | — | Cadastra edital/fundo externo curado (com URL da fonte oficial) |
| POST | `/v1/admin/calls/{call_id}/status` | admin da plataforma + MFA | — | call status |
| POST | `/v1/admin/calls/{call_id}/verify` | admin da plataforma + MFA | — | Registra conferência do edital na fonte oficial (data/responsável) |
| GET | `/v1/admin/compliance-reviews` | admin da plataforma + MFA | — | compliance queue |
| POST | `/v1/admin/compliance-reviews/{review_id}/decide` | admin da plataforma + MFA | — | compliance decide |
| POST | `/v1/admin/content/article-versions/{id}/transition` | admin da plataforma + MFA | — | Fluxo editorial: rascunho → revisão → aprovado → publicado → arquivado. Aprovação por OUTRA pessoa (quatro olhos). |
| PUT | `/v1/admin/content/article-versions/{version_id}` | admin da plataforma + MFA | — | Edita uma versão em RASCUNHO (versões revisadas são imutáveis) |
| GET | `/v1/admin/content/articles` | admin da plataforma + MFA | — | article list |
| POST | `/v1/admin/content/articles` | admin da plataforma + MFA | — | Cria artigo/guia (versão 1 em rascunho) |
| GET | `/v1/admin/content/articles/{slug}` | admin da plataforma + MFA | — | article admin get |
| PATCH | `/v1/admin/content/articles/{slug}` | admin da plataforma + MFA | — | Atualiza metadados (público, tags, telas, relacionados). O texto só muda por nova versão. |
| POST | `/v1/admin/content/articles/{slug}/versions` | admin da plataforma + MFA | — | Nova versão (rascunho) a partir de uma edição; exige nota de mudança |
| POST | `/v1/admin/content/categories` | admin da plataforma + MFA | — | category create |
| GET | `/v1/admin/content/courses` | admin da plataforma + MFA | — | course list |
| POST | `/v1/admin/content/courses` | admin da plataforma + MFA | — | Cria curso (módulos, aulas, quiz com gabarito separado) em rascunho |
| PUT | `/v1/admin/content/courses/{id}` | admin da plataforma + MFA | — | Substitui a estrutura de um curso em RASCUNHO/REVISÃO (cursos publicados: arquive e crie outro — limitação documentada) |
| POST | `/v1/admin/content/courses/{id}/transition` | admin da plataforma + MFA | — | Fluxo editorial: rascunho → revisão → aprovado → publicado → arquivado. Aprovação por OUTRA pessoa (quatro olhos). |
| POST | `/v1/admin/content/events` | admin da plataforma + MFA | — | Cria evento em rascunho (link de acesso fica restrito às inscritas) |
| PATCH | `/v1/admin/content/events/{id}` | admin da plataforma + MFA | — | Atualiza evento (alterações em evento publicado ficam no histórico) |
| POST | `/v1/admin/content/events/{id}/attendance` | admin da plataforma + MFA | — | Registra presença (a avaliação só é liberada a quem participou) |
| POST | `/v1/admin/content/events/{id}/recording-to-resource` | admin da plataforma + MFA | — | Transforma a gravação do evento em recurso da biblioteca (rascunho, sujeito a revisão) |
| GET | `/v1/admin/content/events/{id}/registrations` | admin da plataforma + MFA | — | Inscritas (dados mínimos: nome, organização, estado, presença) |
| POST | `/v1/admin/content/events/{id}/transition` | admin da plataforma + MFA | — | Fluxo editorial: rascunho → revisão → aprovado → publicado → arquivado. Aprovação por OUTRA pessoa (quatro olhos). |
| GET | `/v1/admin/content/faqs` | admin da plataforma + MFA | — | faq list |
| POST | `/v1/admin/content/faqs` | admin da plataforma + MFA | — | Cria FAQ em rascunho (ou revisão de uma publicada via revises_id) |
| PUT | `/v1/admin/content/faqs/{id}` | admin da plataforma + MFA | — | Edita FAQ em rascunho |
| POST | `/v1/admin/content/faqs/{id}/transition` | admin da plataforma + MFA | — | Fluxo editorial: rascunho → revisão → aprovado → publicado → arquivado. Aprovação por OUTRA pessoa (quatro olhos). |
| GET | `/v1/admin/content/history/{object_type}/{object_id}` | admin da plataforma + MFA | — | Histórico editorial (quem fez o quê, quando) |
| GET | `/v1/admin/content/overview` | admin da plataforma + MFA | — | Painel editorial: itens por estado, aguardando revisão e conteúdo desatualizado |
| POST | `/v1/admin/content/paths` | admin da plataforma + MFA | — | Cria trilha de aprendizado (cursos/guias/recursos em ordem) |
| POST | `/v1/admin/content/paths/{id}/transition` | admin da plataforma + MFA | — | Fluxo editorial: rascunho → revisão → aprovado → publicado → arquivado. Aprovação por OUTRA pessoa (quatro olhos). |
| GET | `/v1/admin/content/resources` | admin da plataforma + MFA | — | resource list |
| POST | `/v1/admin/content/resources` | admin da plataforma + MFA | — | Cria recurso (modelo, documento, checklist, vídeo, relatório, boletim) em rascunho |
| PUT | `/v1/admin/content/resources/{id}` | admin da plataforma + MFA | — | Edita recurso em RASCUNHO |
| POST | `/v1/admin/content/resources/{id}/new-version` | admin da plataforma + MFA | — | Nova versão de um recurso publicado (a anterior fica no histórico como 'superseded') |
| POST | `/v1/admin/content/resources/{id}/transition` | admin da plataforma + MFA | — | Fluxo editorial: rascunho → revisão → aprovado → publicado → arquivado. Aprovação por OUTRA pessoa (quatro olhos). |
| POST | `/v1/admin/content/{obj_type}/{id}/reviewed` | admin da plataforma + MFA | — | Confirma que o conteúdo continua válido (zera 'Revisão necessária') |
| GET | `/v1/admin/contribution-models` | admin da plataforma + MFA | — | Fila de revisão jurídica de modelos de contribuição |
| POST | `/v1/admin/contribution-models/{model_id}/decide` | admin da plataforma + MFA | — | Decisão jurídica: aprova (vira utilizável em pagamentos) ou devolve ao rascunho, com parecer registrado |
| GET | `/v1/admin/credentials` | admin da plataforma + MFA | — | credentials |
| POST | `/v1/admin/credentials/{credential_id}/verify` | admin da plataforma + MFA | — | Verifica credencial profissional (registre a fonte consultada, ex.: cadastro público do conselho, e a data) |
| POST | `/v1/admin/datasets` | admin da plataforma + MFA | — | Registra a procedência de um conjunto de dados externo (licença obrigatória) |
| GET | `/v1/admin/encryption/keys` | admin da plataforma + MFA | — | Inventário de chaves por impressão digital (a chave nunca é gravada) |
| POST | `/v1/admin/encryption/keys` | admin da plataforma + MFA | — | Registra no inventário as chaves em uso para uma finalidade |
| POST | `/v1/admin/encryption/reencrypt` | admin da plataforma + MFA | — | Recifra a coluna com a chave corrente (idempotente, com auditoria do resultado) |
| GET | `/v1/admin/enforcement` | admin da plataforma + MFA | — | list enforcement |
| POST | `/v1/admin/enforcement` | admin da plataforma + MFA | — | Aplica medida (proporcional ao histórico; contornar a escada exige justificativa registrada) |
| GET | `/v1/admin/enforcement/history` | admin da plataforma + MFA | — | Histórico de medidas contra um alvo — é o que torna a proporcionalidade verificável |
| POST | `/v1/admin/enforcement/{action_id}/appeal-decision` | admin da plataforma + MFA | — | Julga a contestação (nunca quem aplicou a medida) |
| POST | `/v1/admin/enforcement/{action_id}/lift` | admin da plataforma + MFA | — | Levanta a medida (exige motivo, como aplicar) |
| POST | `/v1/admin/equity/denominators` | admin da plataforma + MFA | — | Declara denominador de TERRITÓRIO (bem comum: só a administração publica) |
| GET | `/v1/admin/errors` | admin da plataforma + MFA | — | Erros 5xx agregados por impressão digital (sem dados pessoais) |
| POST | `/v1/admin/errors/{error_id}/resolve` | admin da plataforma + MFA | — | resolve error |
| POST | `/v1/admin/fee-tables` | admin da plataforma + MFA | — | Cria tabela de honorários em rascunho (publicar exige fonte, URL e data de consulta) |
| POST | `/v1/admin/fee-tables/{table_id}/items` | admin da plataforma + MFA | — | Acrescenta item à tabela de honorários (valor vem da fonte, não da plataforma) |
| POST | `/v1/admin/fee-tables/{table_id}/publish` | admin da plataforma + MFA | — | Publica a tabela (recusado sem nome da fonte, URL e data de consulta) |
| GET | `/v1/admin/fiscal-rules` | admin da plataforma + MFA | — | list rules |
| POST | `/v1/admin/fiscal-rules` | admin da plataforma + MFA | — | Cadastra regra (nasce rascunho; exige fonte oficial e data de consulta) |
| POST | `/v1/admin/fiscal-rules/{rule_id}/action` | admin da plataforma + MFA | — | Fluxo: draft → pending_review → approved (dois aprovadores distintos) → retired |
| GET | `/v1/admin/flags` | admin da plataforma + MFA | — | flags |
| PUT | `/v1/admin/flags/{key}` | admin da plataforma + MFA | — | set flag |
| GET | `/v1/admin/free-periods` | admin da plataforma + MFA | — | Períodos gratuitos concedidos, por origem e situação |
| POST | `/v1/admin/free-periods` | admin da plataforma + MFA | — | Concede período gratuito a uma organização (motivo obrigatório) |
| POST | `/v1/admin/free-periods/{period_id}/cancel` | admin da plataforma + MFA | — | Cancela um período gratuito (o registro permanece, com motivo e autor) |
| POST | `/v1/admin/funding-quotas/pledges/{pledge_id}/confirm` | admin da plataforma + MFA | — | Confirma o recebimento de um apoio (registro humano; a reserva não se confirma sozinha) |
| POST | `/v1/admin/grants/{grant_id}/revoke` | admin da plataforma + MFA | — | Revoga uma licença/grant (motivo obrigatório); o histórico é preservado |
| GET | `/v1/admin/hub/analytics` | admin da plataforma + MFA | — | Analytics da Central: buscas, lacunas, utilidade, chamados, academia, eventos, parcerias |
| POST | `/v1/admin/hub/certificates/{code}/revoke` | admin da plataforma + MFA | — | Revoga certificado de conclusão (motivo obrigatório, auditado) |
| GET | `/v1/admin/hub/demo-requests` | admin da plataforma + MFA | — | demo list |
| POST | `/v1/admin/hub/demo-requests/{id}/handle` | admin da plataforma + MFA | — | Agenda/conclui/cancela demonstração e avisa a pessoa por e-mail |
| GET | `/v1/admin/hub/newsletter` | admin da plataforma + MFA | — | Inscrições do boletim (contagens; e-mails só para administradores) |
| POST | `/v1/admin/hub/newsletter/dispatch` | admin da plataforma + MFA | — | Dispara agora o envio do boletim às inscritas devidas (o worker também faz) |
| GET | `/v1/admin/hub/partnerships` | admin da plataforma + MFA | — | Pipeline de parcerias |
| GET | `/v1/admin/hub/partnerships/{id}` | admin da plataforma + MFA | — | partnership get |
| POST | `/v1/admin/hub/partnerships/{id}/move` | admin da plataforma + MFA | — | Move no pipeline (histórico) e define responsável; 'ativa' cria o registro de parceria |
| POST | `/v1/admin/hub/partnerships/{id}/notes` | admin da plataforma + MFA | — | partnership note |
| GET | `/v1/admin/hub/trial-requests` | admin da plataforma + MFA | — | trial req list |
| POST | `/v1/admin/hub/trial-requests/{id}/decide` | admin da plataforma + MFA | — | Decide a solicitação de teste (motivo obrigatório): inicia/estende o trial existente ou recusa; nunca automático |
| GET | `/v1/admin/hub/trials` | admin da plataforma + MFA | — | Painel de testes: solicitações, ativos, vencendo, conversão e uso por organização |
| GET | `/v1/admin/institutional/agreements` | admin da plataforma + MFA | — | Fila de verificação de instrumentos (padrão: comprovante enviado) |
| POST | `/v1/admin/institutional/agreements/{agreement_id}/decide` | admin da plataforma + MFA | — | Verifica ou rejeita o instrumento. Verificar exige número, documento VALIDADO ou URL oficial, e nota. |
| GET | `/v1/admin/institutional/catalog` | admin da plataforma + MFA | — | Itens de catálogo em qualquer estado do fluxo editorial |
| POST | `/v1/admin/institutional/catalog` | admin da plataforma + MFA | — | Cria item de catálogo (nasce rascunho; passa por revisão e aprovação de outra pessoa) |
| POST | `/v1/admin/institutional/catalog/{item_id}/action` | admin da plataforma + MFA | — | Fluxo: submit → approve (outra pessoa) → publish → archive / return_to_draft |
| POST | `/v1/admin/institutional/catalog/{item_id}/new-version` | admin da plataforma + MFA | — | Nova versão de um item existente (rascunho). A versão publicada anterior só é arquivada quando a nova for publicada. |
| GET | `/v1/admin/institutional/documents` | admin da plataforma + MFA | — | Fila de validação documental (arquivos já aprovados no antivírus) |
| POST | `/v1/admin/institutional/documents/{document_id}/validate` | admin da plataforma + MFA | — | Valida ou rejeita um documento (validação humana; antivírus não substitui). Rejeição exige justificativa. |
| GET | `/v1/admin/institutional/mentoring` | admin da plataforma + MFA | — | Fila de pedidos de mentoria (padrão: abertos e em andamento) |
| POST | `/v1/admin/institutional/mentoring/{mentoring_id}/update` | admin da plataforma + MFA | — | Atualiza o andamento do pedido de mentoria |
| GET | `/v1/admin/institutional/organizations/{org_id}` | admin da plataforma + MFA | — | Visão institucional de uma organização: fatos, maturidade, situação atual e SUGESTÃO de situação |
| POST | `/v1/admin/institutional/organizations/{org_id}/status` | admin da plataforma + MFA | — | Define a situação institucional (decisão humana, justificada e auditada) |
| GET | `/v1/admin/institutional/overview` | admin da plataforma + MFA | — | Painel institucional: filas e estados do fluxo editorial |
| GET | `/v1/admin/institutional/qualifications` | admin da plataforma + MFA | — | Fila de qualificações (padrão: comprovante enviado / em análise) |
| POST | `/v1/admin/institutional/qualifications/{qualification_id}/decide` | admin da plataforma + MFA | — | Verifica, rejeita, revoga ou pede informações. Verificar exige autoridade, número/protocolo e (documento VALIDADO ou URL de verificação). |
| GET | `/v1/admin/institutional/rules` | admin da plataforma + MFA | — | Regras de elegibilidade em qualquer estado (com fonte, versão e vigência) |
| POST | `/v1/admin/institutional/rules` | admin da plataforma + MFA | — | Cria regra (nasce rascunho). Exige fonte; só vale depois de revisão, aprovação por outra pessoa e publicação. |
| POST | `/v1/admin/institutional/rules/import-candidates` | admin da plataforma + MFA | — | Importa as regras CANDIDATAS do repositório como RASCUNHO (nunca publica; idempotente por código) |
| POST | `/v1/admin/institutional/rules/{rule_id}/action` | admin da plataforma + MFA | — | Fluxo: submit → approve (outra pessoa) → publish (data de consulta da fonte) → archive |
| POST | `/v1/admin/institutional/rules/{rule_id}/new-version` | admin da plataforma + MFA | — | Nova versão de uma regra existente (a publicada continua valendo até a nova ser publicada) |
| GET | `/v1/admin/integrations/overview` | admin da plataforma + MFA | — | Qual integração está quebrada agora? Saúde, filas, falhas, dead-letters |
| POST | `/v1/admin/integrations/providers/{key}/maturity` | admin da plataforma + MFA | — | Promove/rebaixa a maturidade de um provedor COM evidência registrada (nunca automático) |
| POST | `/v1/admin/integrations/run-worker` | admin da plataforma + MFA | — | Executa um ciclo do trabalhador agora (jobs devidos + entregas devidas) |
| POST | `/v1/admin/invoices` | admin da plataforma + MFA | — | Emite cobrança manual (registro interno; NF-e é emitida no sistema fiscal da empresa) |
| POST | `/v1/admin/invoices/{invoice_id}/paid` | admin da plataforma + MFA | — | invoice paid |
| GET | `/v1/admin/jobs` | admin da plataforma + MFA | — | jobs |
| GET | `/v1/admin/legal/acceptances` | admin da plataforma + MFA | — | Prova de aceite: quem, quando, qual versão e qual hash |
| POST | `/v1/admin/legal/documents/{doc_id}/approve` | admin da plataforma + MFA | — | Aprova a versão, exigindo quem revisou e sob qual referência |
| POST | `/v1/admin/legal/documents/{doc_id}/review` | admin da plataforma + MFA | — | Marca a minuta como enviada para revisão jurídica |
| POST | `/v1/admin/marketplace/listings/{listing_id}/transition` | admin da plataforma + MFA | — | Suspende ou libera anúncio (exige motivo registrado) |
| GET | `/v1/admin/match/calibration` | admin da plataforma + MFA | — | Base para calibração futura do match (sem dado pessoal) |
| GET | `/v1/admin/messages/{message_id}` | admin da plataforma + MFA | — | Lê uma mensagem denunciada (acesso auditado) |
| POST | `/v1/admin/messages/{message_id}/remove` | admin da plataforma + MFA | — | Oculta o conteúdo de uma mensagem denunciada (registro permanece) |
| POST | `/v1/admin/monetization/legal-cards` | admin da plataforma + MFA | — | Registra a pesquisa de base normativa de uma receita |
| GET | `/v1/admin/monetization/pipeline` | admin da plataforma + MFA | — | A fila de monetização de todas as organizações |
| POST | `/v1/admin/monetization/pipeline/{billable_seq}/waive` | admin da plataforma + MFA | — | Dispensa um candidato a cobrança, com motivo escrito |
| PATCH | `/v1/admin/monetization/rules/{rule_key}` | admin da plataforma + MFA | — | Ajusta preço, situação jurídica e ativação de uma regra (o portão é no banco) |
| GET | `/v1/admin/ops/health` | admin da plataforma + MFA | — | Última execução de cada tarefa de operação e falhas de e-mail na janela |
| GET | `/v1/admin/organizations` | admin da plataforma + MFA | — | orgs |
| POST | `/v1/admin/organizations/{org_id}/compliance-checks` | admin da plataforma + MFA | — | Executa verificações automáticas de compliance |
| POST | `/v1/admin/organizations/{org_id}/grants` | admin da plataforma + MFA | — | grant |
| POST | `/v1/admin/organizations/{org_id}/manual-subscription` | admin da plataforma + MFA | — | Ativa assinatura sob contrato (Enterprise/Governo) com referência do contrato |
| POST | `/v1/admin/organizations/{org_id}/status` | admin da plataforma + MFA | — | org status |
| POST | `/v1/admin/organizations/{org_id}/trial` | admin da plataforma + MFA | — | Concede trial a uma organização que ainda não o teve (motivo obrigatório) |
| GET | `/v1/admin/overview` | admin da plataforma + MFA | — | Métricas operacionais da plataforma |
| GET | `/v1/admin/payments/reconciliation` | admin da plataforma + MFA | — | Onde o provedor e a plataforma discordam: cobrança parada e evento sem assinatura |
| GET | `/v1/admin/payments/revenue` | admin da plataforma + MFA | — | Receita apurada, com o simulado em colunas próprias e nunca somado ao real |
| GET | `/v1/admin/permissions` | admin da plataforma + MFA | — | Matriz papel → permissão, como está no banco |
| PUT | `/v1/admin/plans/{plan_key}/price` | admin da plataforma + MFA | — | Define/limpa o preço mensal ou anual de um plano (auditado; nada é inventado — o proprietário decide) |
| GET | `/v1/admin/price-benchmark` | admin da plataforma + MFA | — | Benchmark de preço consultado (§47–48, §89) — referência, nunca preço decidido |
| GET | `/v1/admin/privileged-access` | admin da plataforma + MFA | — | Quem entrou com papel interno, quando, em qual rota e com qual permissão |
| GET | `/v1/admin/reports` | admin da plataforma + MFA | — | reports |
| GET | `/v1/admin/reports/queue` | admin da plataforma + MFA | — | Fila de apuração, com a distinção entre arquivada e não procedente |
| POST | `/v1/admin/reports/{report_id}/conclude` | admin da plataforma + MFA | — | Conclusão fundamentada. Só 'substantiated' autoriza medida |
| POST | `/v1/admin/reports/{report_id}/dismiss` | admin da plataforma + MFA | — | Arquiva SEM análise de mérito — o que é diferente de concluir pela improcedência |
| POST | `/v1/admin/reports/{report_id}/request-response` | admin da plataforma + MFA | — | Abre o contraditório: chama quem foi denunciado a se manifestar |
| GET | `/v1/admin/reports/{report_id}/responses` | admin da plataforma + MFA | — | Manifestações de quem foi denunciado |
| POST | `/v1/admin/reports/{report_id}/review` | admin da plataforma + MFA | — | Leva para análise e registra quem analisa (continua não sendo achado) |
| POST | `/v1/admin/reputation/disputes/{dispute_id}/resolution` | admin da plataforma + MFA | — | Resolve a contestação; corrigir produz ponto NOVO, nunca reescreve o antigo |
| GET | `/v1/admin/risk-levels` | admin da plataforma + MFA | — | Inventário de risco por operação (§40): nível, controle humano exigido e se ele existe |
| GET | `/v1/admin/risk/assessments` | admin da plataforma + MFA | — | list assessments |
| POST | `/v1/admin/risk/orgs/{org_id}/block` | admin da plataforma + MFA | — | Restrição operacional (publicar, candidatar, aportar) por DECISÃO HUMANA registrada; reversível |
| POST | `/v1/admin/risk/orgs/{org_id}/unblock` | admin da plataforma + MFA | — | unblock org |
| POST | `/v1/admin/risk/scan` | admin da plataforma + MFA | — | Executa os detectores agora (todas as organizações ou uma) |
| GET | `/v1/admin/risk/signals` | admin da plataforma + MFA | — | Sinais de risco (para revisão humana; não são acusações) |
| POST | `/v1/admin/risk/signals/{signal_id}/review` | admin da plataforma + MFA | — | Revisão humana do sinal (relevante ou descartado), com justificativa obrigatória |
| POST | `/v1/admin/seals/awards` | admin da plataforma + MFA | — | Concede; o banco reavalia e RECUSA se faltar critério |
| POST | `/v1/admin/seals/awards/{award_id}/revoke` | admin da plataforma + MFA | — | Revoga como fato novo, com motivo (não apaga a concessão) |
| POST | `/v1/admin/seals/definitions` | admin da plataforma + MFA | — | Cria definição (nasce RASCUNHO; rascunho não concede selo) |
| POST | `/v1/admin/seals/definitions/{definition_id}/publish` | admin da plataforma + MFA | — | Publica; a versão anterior é aposentada e suas concessões ficam 'superadas' |
| POST | `/v1/admin/seals/definitions/{definition_id}/retire` | admin da plataforma + MFA | — | Aposenta a definição com motivo registrado (não revoga as concessões) |
| PUT | `/v1/admin/signature-providers/{provider_key}` | admin da plataforma + MFA | — | Ajusta o estado real de um provedor de assinatura (passar para produção exige dependência resolvida) |
| POST | `/v1/admin/solution-disputes/{dispute_id}/decide` | admin da plataforma + MFA | — | Decide uma contestação (humano; registra decisor e nota) |
| POST | `/v1/admin/solution-evidence/{evidence_id}/review` | admin da plataforma + MFA | — | Aceita ou rejeita uma evidência (registra revisor e nota) |
| POST | `/v1/admin/solution-results/{result_id}/validate` | admin da plataforma + MFA | — | Valida um resultado (exige evidência aceita vinculada) |
| GET | `/v1/admin/solutions/queue` | admin da plataforma + MFA | — | Fila de verificação: solicitações, evidências a revisar, contestações abertas |
| POST | `/v1/admin/solutions/{solution_id}/remove` | admin da plataforma + MFA | — | Remove a solução da biblioteca (irreversível pelo autor) |
| POST | `/v1/admin/solutions/{solution_id}/verify` | admin da plataforma + MFA | — | Define o nível de confiança. Níveis altos exigem evidências aceitas (regras no servidor) |
| GET | `/v1/admin/staff-roles` | admin da plataforma + MFA | — | Papéis internos (editor, reviewer, support) |
| POST | `/v1/admin/staff-roles` | admin da plataforma + MFA | — | Concede papel interno (auditado) |
| DELETE | `/v1/admin/staff-roles/{user_id}/{role}` | admin da plataforma + MFA | — | Revoga papel interno, com motivo registrado |
| GET | `/v1/admin/support/sla` | admin da plataforma + MFA | — | SLA por prioridade (valores iniciais são hipótese operacional, configuráveis) |
| PUT | `/v1/admin/support/sla/{priority}` | admin da plataforma + MFA | — | Ajusta o SLA de uma prioridade (administradores) |
| GET | `/v1/admin/support/tickets` | admin da plataforma + MFA | — | Fila de chamados (por estado, prioridade e atraso de SLA) |
| GET | `/v1/admin/support/tickets/{ticket_id}` | admin da plataforma + MFA | — | staff ticket get |
| PATCH | `/v1/admin/support/tickets/{ticket_id}` | admin da plataforma + MFA | — | Estado, prioridade (recalcula SLA) e responsável |
| POST | `/v1/admin/support/tickets/{ticket_id}/messages` | admin da plataforma + MFA | — | Responde (ou anota internamente) um chamado |
| POST | `/v1/admin/support/tickets/{ticket_id}/to-article` | admin da plataforma + MFA | — | Vincula o chamado a um artigo (o assunto deixa de contar como recorrente sem base) |
| POST | `/v1/admin/territory-indicators` | admin da plataforma + MFA | — | Publica um indicador territorial (fonte e data de referência obrigatórias) |
| GET | `/v1/admin/trust/credentials/queue` | admin da plataforma + MFA | — | Credenciais profissionais com documento aguardando conferência |
| POST | `/v1/admin/trust/credentials/{credential_id}/decide` | admin da plataforma + MFA | — | Confere a credencial; aprovar eleva a identidade da pessoa ao nível profissional |
| POST | `/v1/admin/trust/credentials/{credential_id}/revoke` | admin da plataforma + MFA | — | Revoga uma credencial verificada (motivo obrigatório; entra na cadeia de custódia) |
| GET | `/v1/admin/trust/identity/queue` | admin da plataforma + MFA | — | Fila de verificações de identidade aguardando conferência humana |
| POST | `/v1/admin/trust/identity/{verification_id}/decide` | admin da plataforma + MFA | — | Decide um pedido de verificação de identidade (decisão humana registrada na cadeia de custódia) |
| GET | `/v1/admin/users` | admin da plataforma + MFA | — | users |
| POST | `/v1/admin/users/{user_id}/status` | admin da plataforma + MFA | — | Ativa/desativa usuário (revoga sessões ao desativar) |
| POST | `/v1/admin/value/baselines` | admin da plataforma + MFA | — | Declara a linha de referência de um tipo de evento (cria versão; não reescreve) |
| GET | `/v1/admin/voucher-batches` | admin da plataforma + MFA | — | list batches |
| POST | `/v1/admin/voucher-batches` | admin da plataforma + MFA | — | Gera lote de vouchers (códigos exibidos UMA vez; armazenados só como HMAC). Ativação exige segundo administrador. |
| POST | `/v1/admin/voucher-batches/{batch_id}/action` | admin da plataforma + MFA | — | batch action |
| GET | `/v1/admin/voucher-batches/{batch_id}/redemptions` | admin da plataforma + MFA | — | Utilizações de um lote de vouchers (quem usou e quando; código só pelo final) |
| GET | `/v1/administrativo/orcamento` | admin da plataforma + MFA | — | Orçado × comprometido × realizado, por conta e centro de custo |
| POST | `/v1/agreements/join` | membro da organização ativa | papel ≥ owner; limite 10/3600s | Entrar em um convênio com o código (vagas, validade e — se houver — domínio de e-mail verificado). Resposta genérica para códigos inválidos. |
| POST | `/v1/ai/classify-document/{document_id}` | membro da organização ativa | papel ≥ member | Sugere o tipo e a validade de um documento enviado (processamento local; nada é enviado a terceiros) |
| POST | `/v1/ai/draft` | membro da organização ativa | tipos: osc; papel ≥ member; limite 60/3600s | Gera rascunho de proposta/plano/relatório a partir dos dados do projeto (marca [COMPLETAR] onde faltar) |
| POST | `/v1/ai/structure-need` | membro da organização ativa | tipos: osc; papel ≥ member; limite 60/3600s | Transforma uma necessidade descrita livremente em projeto estruturado (título, causas, ODS, itens de orçamento, perguntas) |
| POST | `/v1/ai/summarize-project` | membro da organização ativa | papel ≥ viewer; limite 60/3600s | Resumo do projeto para leitura rápida do financiador |
| GET | `/v1/ai/usage` | membro da organização ativa | papel ≥ viewer | Uso de IA no mês (cota do plano) |
| GET | `/v1/applications` | membro da organização ativa | papel ≥ viewer | Candidaturas da organização (enviadas pela OSC ou recebidas pelo financiador) |
| POST | `/v1/applications` | membro da organização ativa | tipos: osc; papel ≥ member | Inicia candidatura assistida (plataforma) ou acompanhamento de edital externo, com checklist gerado dos requisitos |
| POST | `/v1/applications/interest` | membro da organização ativa | tipos: company, individual; papel ≥ analyst | Financiador manifesta interesse em projeto publicado (OSC aceita para iniciar a diligência) |
| GET | `/v1/applications/{application_id}` | membro da organização ativa | papel ≥ viewer | Detalhe: checklist passo a passo, linha do tempo, compatibilidade, aportes e documentos compartilhados |
| POST | `/v1/applications/{application_id}/commitments` | membro da organização ativa | tipos: company, government, individual; papel ≥ manager | Registra aporte comprometido (o dinheiro NÃO passa pela plataforma) |
| POST | `/v1/applications/{application_id}/conflict` | membro da organização ativa | tipos: company, government, individual; papel ≥ analyst | Declaração de conflito de interesse do avaliador (obrigatória antes de aprovar) |
| PATCH | `/v1/applications/{application_id}/steps/{step_id}` | membro da organização ativa | papel ≥ member | Atualiza uma etapa do checklist (passo a passo) |
| POST | `/v1/applications/{application_id}/transition` | membro da organização ativa | papel ≥ member | Avança/retrocede o status conforme a máquina de estados (validações e devolutiva obrigatória na reprovação) |
| GET | `/v1/aprovacoes` | admin da plataforma + MFA | — | Pedidos de aprovação pendentes, com quantas faltam e quais permissões servem |
| POST | `/v1/aprovacoes/{request_id}/decide` | admin da plataforma + MFA | — | Decide um pedido. Quem pede não aprova, e faixas de duas exigem permissões diferentes |
| POST | `/v1/auth/accept-invite` | usuário autenticado | — | accept invite |
| POST | `/v1/auth/change-password` | usuário autenticado | limite 10/3600s | change password |
| POST | `/v1/auth/forgot-password` | pública | limite 5/3600s | forgot |
| POST | `/v1/auth/login` | pública | limite 30/900s | Login por e-mail/senha. Web recebe cookies httpOnly; mobile envia X-Auth-Mode: token. |
| POST | `/v1/auth/logout` | usuário autenticado | — | Encerra a sessão atual |
| POST | `/v1/auth/logout-all` | usuário autenticado | — | Encerra todas as sessões do usuário |
| POST | `/v1/auth/mfa/disable` | usuário autenticado | — | mfa disable |
| POST | `/v1/auth/mfa/enable` | usuário autenticado | — | Confirma TOTP e devolve códigos de recuperação |
| POST | `/v1/auth/mfa/setup` | usuário autenticado | — | Gera segredo TOTP (pendente até confirmar) |
| POST | `/v1/auth/mfa/verify` | pública | limite 30/900s | Conclui login com TOTP ou código de recuperação |
| GET | `/v1/auth/oidc/callback` | pública | limite 60/900s | Retorno do provedor de identidade: valida id_token (JWKS, iss, aud, nonce) e cria a sessão |
| GET | `/v1/auth/oidc/start` | pública | limite 60/900s | Inicia login corporativo (OIDC Authorization Code + PKCE) |
| POST | `/v1/auth/reauth` | usuário autenticado | limite 20/900s | Confirma a identidade para operações sensíveis (vale por 15 minutos) |
| POST | `/v1/auth/refresh` | pública | limite 120/900s | Rotaciona o refresh token (reuso revoga toda a família de sessões) |
| POST | `/v1/auth/register` | pública | limite 10/3600s | Cadastra usuário (e organização opcional). Resposta não revela se o e-mail já existe. |
| POST | `/v1/auth/resend-verification` | usuário autenticado | limite 5/3600s | resend |
| POST | `/v1/auth/reset-password` | pública | limite 10/3600s | reset |
| GET | `/v1/auth/sessions` | usuário autenticado | — | Sessões ativas do usuário |
| DELETE | `/v1/auth/sessions/{session_id}` | usuário autenticado | — | Revoga uma sessão |
| POST | `/v1/auth/verify-email` | pública | limite 30/900s | verify email |
| GET | `/v1/badges` | membro da organização ativa | papel ≥ viewer | Conquistas organizacionais verificáveis (privadas; sem pontos, ranking ou comparação) |
| GET | `/v1/billing` | membro da organização ativa | papel ≥ viewer | Estado de cobrança da organização: plano, status, trial, próxima cobrança, avisos, faturas |
| POST | `/v1/billing/cancel` | membro da organização ativa | papel ≥ owner | Cancela a assinatura ou o trial (sem cobrança; acesso mantido até o fim do período) |
| POST | `/v1/billing/change-plan` | membro da organização ativa | papel ≥ owner; limite 20/3600s | Upgrade/downgrade (sincronizado com o provedor) |
| POST | `/v1/billing/checkout` | membro da organização ativa | papel ≥ owner; limite 20/3600s | Inicia contratação (Stripe Checkout) com trial quando houver. Sem gateway configurado, responde 503 de forma explícita. |
| POST | `/v1/billing/portal` | membro da organização ativa | papel ≥ owner | Portal de pagamento do provedor (método de pagamento, faturas) |
| GET | `/v1/billing/price-history` | membro da organização ativa | papel ≥ owner | Histórico de preço da organização e avisos de reajuste recebidos |
| POST | `/v1/billing/price-notices/{notice_id}/ack` | membro da organização ativa | papel ≥ owner | Registra que a organização viu o aviso de reajuste |
| POST | `/v1/billing/quote` | membro da organização ativa | papel ≥ viewer | Simulação do valor FINAL calculada no servidor (preço, desconto, trial, primeira cobrança). Não cobra nada. |
| POST | `/v1/billing/reactivate` | membro da organização ativa | papel ≥ owner | Desfaz um cancelamento em andamento |
| POST | `/v1/billing/webhooks/stripe` | pública | limite 600/60s | Webhook do Stripe (assinatura verificada, idempotente) |
| GET | `/v1/calls` | membro da organização ativa | papel ≥ viewer | Busca no banco de oportunidades. Para OSC, cada item traz a compatibilidade resumida. |
| POST | `/v1/calls` | membro da organização ativa | tipos: company, government; papel ≥ manager | Cria programa/chamada própria (empresa) ou edital público (governo) |
| GET | `/v1/calls/recommended` | membro da organização ativa | tipos: osc; papel ≥ viewer | Editais abertos ranqueados por compatibilidade com a OSC (elegíveis primeiro, depois score) |
| GET | `/v1/calls/{call_id}` | membro da organização ativa | papel ≥ viewer | Detalhe do edital. Para OSC: requisitos atendidos/pendentes, compatibilidade, riscos e próxima ação. |
| PUT | `/v1/calls/{call_id}` | membro da organização ativa | tipos: company, government; papel ≥ manager | update call |
| GET | `/v1/calls/{call_id}/applications` | membro da organização ativa | tipos: company, government; papel ≥ analyst | Candidaturas recebidas, com compatibilidade explicada (shortlist) |
| GET | `/v1/campaigns` | membro da organização ativa | papel ≥ viewer | Campanhas da organização, com o endereço público e a situação |
| POST | `/v1/campaigns` | membro da organização ativa | papel ≥ manager | Cria a campanha de divulgação do projeto (rascunho; publicar é um passo separado) |
| PATCH | `/v1/campaigns/{campaign_id}` | membro da organização ativa | papel ≥ manager | Altera ou publica/fecha a campanha |
| GET | `/v1/claims` | membro da organização ativa | papel ≥ viewer | Alegações com a situação DERIVADA da última verificação |
| POST | `/v1/claims` | membro da organização ativa | papel ≥ manager | Declara a alegação no texto exato em que será publicada |
| GET | `/v1/claims/review-requests` | membro da organização ativa | papel ≥ viewer | Convites de revisão recebidos pela organização — a fila de quem é convidado |
| GET | `/v1/claims/rules` | usuário autenticado | — | As regras de integridade e os léxicos usados — quem é marcado tem direito de saber |
| GET | `/v1/claims/{claim_id}` | membro da organização ativa | papel ≥ viewer | A alegação, a situação derivada, todas as rodadas de verificação e as revisões |
| POST | `/v1/claims/{claim_id}/check` | membro da organização ativa | papel ≥ manager | Roda as regras determinísticas e grava uma nova rodada (nunca apaga a anterior) |
| POST | `/v1/claims/{claim_id}/review` | membro da organização ativa | papel ≥ manager | Revisão humana por organização DIFERENTE; aceitar não apaga a marca, qualifica |
| POST | `/v1/claims/{claim_id}/review-requests` | membro da organização ativa | papel ≥ manager | Convida uma organização nomeada a revisar a rodada (é o convite que abre a leitura) |
| POST | `/v1/claims/{claim_id}/withdraw` | membro da organização ativa | papel ≥ manager | Retira a alegação (o histórico de verificação permanece legível) |
| GET | `/v1/commercial/acceptances` | membro da organização ativa | — | Histórico de aceites desta organização |
| POST | `/v1/commercial/consent/revoke` | membro da organização ativa | — | Revoga a autorização de cobrança (o aceite permanece registrado) |
| GET | `/v1/commercial/offers` | membro da organização ativa | — | Ofertas desta organização |
| POST | `/v1/commercial/offers` | membro da organização ativa | limite 60/3600s | Monta uma oferta a partir do catálogo (valor nunca vem do cliente) |
| POST | `/v1/commercial/offers/{offer_id}/accept` | membro da organização ativa | limite 60/3600s | Aceita a oferta — acesso gratuito OU autorização de cobrança |
| PUT | `/v1/commercial/spend-limit` | membro da organização ativa | — | Define o teto de gasto mensal e o que fazer ao atingi-lo (avisar ou parar) |
| GET | `/v1/commercial/state` | membro da organização ativa | — | Estado comercial da conta: FREE_PERIOD_END, estado e se a cobrança foi autorizada |
| GET | `/v1/commercial/usage` | membro da organização ativa | — | Consumo do período por métrica, com percentual e limite do plano |
| POST | `/v1/commitments/{commitment_id}/payments` | membro da organização ativa | tipos: company, government, individual; papel ≥ manager | Registra um pagamento (parcela) do aporte — declarado pelo financiador; a plataforma não movimenta dinheiro |
| POST | `/v1/commitments/{commitment_id}/status` | membro da organização ativa | papel ≥ manager | Financiador informa desembolso/cancelamento; OSC confirma o recebimento |
| GET | `/v1/compliance` | membro da organização ativa | papel ≥ viewer | Status de compliance/KYB da organização e verificações |
| POST | `/v1/compliance/request-review` | membro da organização ativa | papel ≥ admin | Executa verificações automáticas e envia para análise humana da administração |
| GET | `/v1/conta/denuncias` | membro da organização ativa | papel ≥ admin | O que é imputado à sua organização — sem revelar quem denunciou |
| POST | `/v1/conta/denuncias/{report_id}/manifestacao` | membro da organização ativa | papel ≥ admin | Manifestação de quem foi denunciado (append-only) |
| POST | `/v1/conta/denuncias/{report_id}/recurso` | membro da organização ativa | papel ≥ admin | Recurso da conclusão (a conclusão só muda por aqui) |
| GET | `/v1/conta/moderacao` | membro da organização ativa | papel ≥ admin | Medidas de moderação contra a sua organização, com o direito de contestar |
| POST | `/v1/conta/moderacao/{action_id}/contestar` | membro da organização ativa | papel ≥ admin | Contesta uma medida (uma vez por medida) |
| POST | `/v1/contabilidade/batches` | admin da plataforma + MFA | — | Lança um lote (tem de fechar: débitos iguais a créditos) |
| GET | `/v1/contabilidade/chart` | admin da plataforma + MFA | — | Plano de contas da plataforma |
| POST | `/v1/contabilidade/close` | admin da plataforma + MFA | — | Fecha a competência — irreversível; recusa se houver lote que não fecha |
| GET | `/v1/contabilidade/summary` | admin da plataforma + MFA | — | Balancete da competência, plano de contas e situação do período |
| POST | `/v1/contribution-models/{model_id}/retire` | membro da organização ativa | tipos: osc; papel ≥ manager | retire model |
| POST | `/v1/contribution-models/{model_id}/submit` | membro da organização ativa | tipos: osc; papel ≥ manager | Envia o modelo à revisão jurídica da administração |
| GET | `/v1/controladoria/reconciliation` | admin da plataforma + MFA | — | Conciliação: o que foi esperado × o que aconteceu. APONTA, não corrige |
| GET | `/v1/controladoria/summary` | admin da plataforma + MFA | — | Painel executivo: MRR, ARR, receita, caixa, despesa, GMV, resultado e autonomia |
| GET | `/v1/conversations` | membro da organização ativa | papel ≥ viewer | list conversations |
| POST | `/v1/conversations` | membro da organização ativa | papel ≥ member | Abre (ou reaproveita) a conversa naquele contexto |
| GET | `/v1/conversations/unread` | membro da organização ativa | papel ≥ viewer | unread |
| GET | `/v1/conversations/{conversation_id}` | membro da organização ativa | papel ≥ viewer | get conversation |
| POST | `/v1/conversations/{conversation_id}/messages` | membro da organização ativa | papel ≥ member; limite 60/60s | send message |
| POST | `/v1/conversations/{conversation_id}/read` | membro da organização ativa | papel ≥ viewer | read conversation |
| PUT | `/v1/conversations/{conversation_id}/status` | membro da organização ativa | papel ≥ member | set conversation status |
| GET | `/v1/dashboard` | membro da organização ativa | papel ≥ viewer | Indicadores da organização ativa (dados reais do banco) |
| GET | `/v1/data-quality/vocabulary` | usuário autenticado | — | Os sete tipos de achado de qualidade de dado e o que cada um significa |
| GET | `/v1/datasets` | usuário autenticado | — | Conjuntos de dados externos carregados: publicador, licença, datas e hash do arquivo |
| GET | `/v1/determinants` | membro da organização ativa | tipos: government, company, individual, platform; papel ≥ viewer | Camada agregada: projetos por domínio de determinante social e território (k-anonimato; sem ranking de grupos vulneráveis) |
| GET | `/v1/diagnoses` | membro da organização ativa | tipos: osc; papel ≥ viewer | list diagnoses |
| POST | `/v1/diagnoses` | membro da organização ativa | tipos: osc; papel ≥ member | Cria diagnóstico estruturado: necessidade → causas → objetivo → metas → plano de ação (sem dados pessoais de beneficiários) |
| GET | `/v1/diagnoses/{diagnosis_id}` | membro da organização ativa | tipos: osc; papel ≥ viewer | get diagnosis |
| PUT | `/v1/diagnoses/{diagnosis_id}` | membro da organização ativa | tipos: osc; papel ≥ member | update diagnosis |
| GET | `/v1/diagnoses/{diagnosis_id}/actions` | membro da organização ativa | tipos: osc; papel ≥ viewer | list actions |
| POST | `/v1/diagnoses/{diagnosis_id}/actions` | membro da organização ativa | tipos: osc; papel ≥ member | Ação declarada pela equipe (a ação de lacuna nasce com a versão do diagnóstico) |
| PUT | `/v1/diagnoses/{diagnosis_id}/actions/{action_id}` | membro da organização ativa | tipos: osc; papel ≥ member | Atualiza a ação (encerrar por descarte exige motivo) |
| GET | `/v1/diagnoses/{diagnosis_id}/analysis` | membro da organização ativa | tipos: osc; papel ≥ viewer | Análise do diagnóstico no estado atual (prévia, antes de congelar uma versão) |
| POST | `/v1/diagnoses/{diagnosis_id}/apply` | membro da organização ativa | tipos: osc; papel ≥ member | Aplica o diagnóstico completo ao projeto: problema, objetivos, metas como indicadores do projeto e nós iniciais do Impact Graph |
| GET | `/v1/diagnoses/{diagnosis_id}/guide` | membro da organização ativa | papel ≥ viewer | Roteiro guiado do diagnóstico: etapas, perguntas, documentos exigidos e progresso real |
| PUT | `/v1/diagnoses/{diagnosis_id}/guide/{stage_code}` | membro da organização ativa | papel ≥ manager | Salva as respostas e os documentos de uma etapa do diagnóstico guiado |
| GET | `/v1/diagnoses/{diagnosis_id}/versions` | membro da organização ativa | tipos: osc; papel ≥ viewer | list versions |
| POST | `/v1/diagnoses/{diagnosis_id}/versions` | membro da organização ativa | tipos: osc; papel ≥ member | Congela uma versão do diagnóstico (a anterior nunca é alterada) |
| GET | `/v1/diagnoses/{diagnosis_id}/versions/compare` | membro da organização ativa | tipos: osc; papel ≥ viewer | O que mudou entre duas versões (lacunas fechadas, novas forças, confiança) |
| GET | `/v1/diagnoses/{diagnosis_id}/versions/{version}` | membro da organização ativa | tipos: osc; papel ≥ viewer | Retrato completo de uma versão |
| GET | `/v1/diagnostic-engine` | membro da organização ativa | papel ≥ viewer | O que o motor de diagnóstico avalia, com que peso e como trata ausência de dado |
| GET | `/v1/directory/professionals` | membro da organização ativa | papel ≥ viewer | Diretório de profissionais parceiros. Ordenação objetiva e determinística — NUNCA por plano (invariante). |
| GET | `/v1/directory/services` | membro da organização ativa | papel ≥ viewer | Busca por ATIVIDADE oferecida, com card completo: preço, credencial verificada, ODS e localização (quando pública). O diretório por organização continua em GET /v1/directory/professionals. |
| GET | `/v1/document-assemblies` | membro da organização ativa | papel ≥ viewer | list assemblies |
| POST | `/v1/document-assemblies` | membro da organização ativa | papel ≥ member | Abre uma montagem a partir de um modelo publicado |
| GET | `/v1/document-assemblies/{assembly_id}` | membro da organização ativa | papel ≥ viewer | Montagem com campos, valores, evidência, completude e o que impede a geração |
| PUT | `/v1/document-assemblies/{assembly_id}` | membro da organização ativa | papel ≥ member | Preenche a montagem (completude e situação são recalculadas pelo servidor) |
| POST | `/v1/document-assemblies/{assembly_id}/generate` | membro da organização ativa | papel ≥ member | Gera o documento (RECUSA quando falta campo obrigatório ou evidência) |
| POST | `/v1/document-assemblies/{assembly_id}/review` | membro da organização ativa | papel ≥ member | Revisa a montagem (quem montou não aprova: quatro olhos, com CHECK no banco) |
| GET | `/v1/document-assembly-reference` | membro da organização ativa | papel ≥ viewer | Como a montagem funciona: caminhos de domínio, situações e o que bloqueia a geração |
| GET | `/v1/document-templates` | membro da organização ativa | papel ≥ viewer | Modelos de documento da plataforma e os da própria organização |
| POST | `/v1/document-templates` | membro da organização ativa | papel ≥ admin | Cria um modelo próprio da organização (nasce em rascunho) |
| GET | `/v1/document-templates/{template_id}` | membro da organização ativa | papel ≥ viewer | Modelo com seções, campos e o que cada campo exige de evidência |
| POST | `/v1/document-templates/{template_id}/fields` | membro da organização ativa | papel ≥ admin | Adiciona campo ao modelo (recusado depois de publicado) |
| POST | `/v1/document-templates/{template_id}/publish` | membro da organização ativa | papel ≥ admin | Publica o modelo (a partir daqui ele não muda mais) |
| GET | `/v1/documents` | membro da organização ativa | papel ≥ viewer | Documentos da organização (com validade) |
| POST | `/v1/documents` | membro da organização ativa | papel ≥ member; limite 120/3600s | Upload seguro (multipart: file, doc_type, title, project_id?, application_id?, valid_until?, visibility?) |
| DELETE | `/v1/documents/{document_id}` | membro da organização ativa | papel ≥ admin | Exclusão lógica (preserva trilha; conteúdo removido do storage) |
| GET | `/v1/documents/{document_id}` | membro da organização ativa | papel ≥ viewer | get doc |
| PATCH | `/v1/documents/{document_id}` | membro da organização ativa | papel ≥ member | patch doc |
| POST | `/v1/documents/{document_id}/download-url` | membro da organização ativa | papel ≥ viewer | Gera URL temporária (5 min) para download — somente após autorização e verificação antivírus |
| GET | `/v1/documents/{document_id}/integrity` | membro da organização ativa | papel ≥ viewer | Reconta o hash do arquivo guardado e compara com o hash registrado no upload |
| GET | `/v1/drafts` | membro da organização ativa | papel ≥ viewer | list drafts |
| POST | `/v1/drafts` | membro da organização ativa | papel ≥ member | Cria rascunho (proposta, plano de trabalho, relatório...) — pode vir da assistência de IA |
| GET | `/v1/drafts/{draft_id}` | membro da organização ativa | papel ≥ viewer | Rascunho (OSC dona ou profissional revisor) |
| PATCH | `/v1/drafts/{draft_id}` | membro da organização ativa | papel ≥ member | patch draft |
| POST | `/v1/drafts/{draft_id}/export` | membro da organização ativa | papel ≥ member | Gera o rascunho em PDF, DOCX ou ODT e guarda no cofre; opcionalmente imprime o QR de verificação pública |
| POST | `/v1/drafts/{draft_id}/export-pdf` | membro da organização ativa | papel ≥ member | Gera PDF do rascunho e guarda no cofre (documento hasheado, pronto para assinatura) |
| POST | `/v1/drafts/{draft_id}/new-version` | membro da organização ativa | papel ≥ member | new version |
| GET | `/v1/engines` | usuário autenticado | — | Os motores operacionais: natureza, versão, o que produzem e o que nunca decidem |
| GET | `/v1/engines/coverage` | usuário autenticado | — | Cobertura por motor: implementado, integrado, testado, E2E, segurança, observabilidade — tudo DERIVADO do código, nada declarado |
| GET | `/v1/equity/catalog` | usuário autenticado | — | Barreiras, escadas de prova, tipos de denominador e métodos de normalização |
| POST | `/v1/equity/compare` | membro da organização ativa | papel ≥ viewer | Compara contextos — e devolve comparable=false com o motivo quando não há base |
| GET | `/v1/equity/denominators` | membro da organização ativa | papel ≥ viewer | Denominadores vigentes, com fonte e data de cada um |
| POST | `/v1/equity/denominators` | membro da organização ativa | papel ≥ manager | Declara denominador do projeto ou do programa (fonte e método obrigatórios) |
| POST | `/v1/evidences/{evidence_id}/review` | membro da organização ativa | tipos: company, government, individual; papel ≥ analyst | review evidence |
| POST | `/v1/expenses/{expense_id}/review` | membro da organização ativa | tipos: company, government, individual; papel ≥ analyst | Financiador valida ou questiona a despesa (a OSC não revisa a si mesma — garantido também no banco) |
| GET | `/v1/fee-tables` | membro da organização ativa | papel ≥ viewer | Tabelas de honorários publicadas, com a fonte e a data de consulta (a plataforma não inventa valor) |
| GET | `/v1/fee-tables/{table_id}` | membro da organização ativa | papel ≥ viewer | Itens de uma tabela de honorários |
| GET | `/v1/feed/compare` | membro da organização ativa | tipos: company, individual; papel ≥ viewer | Compara até 4 projetos lado a lado com os mesmos critérios |
| GET | `/v1/feed/projects` | membro da organização ativa | tipos: company, individual; papel ≥ viewer; plano: `feed.projects` | Projetos publicados ranqueados por compatibilidade (explicável). Plano não altera ordem nem elegibilidade. |
| DELETE | `/v1/feed/projects/{project_id}/favorite` | membro da organização ativa | tipos: company, individual; papel ≥ analyst | unfavorite |
| POST | `/v1/feed/projects/{project_id}/favorite` | membro da organização ativa | tipos: company, individual; papel ≥ analyst | favorite |
| POST | `/v1/feed/projects/{project_id}/feedback` | membro da organização ativa | tipos: company, individual; papel ≥ analyst | Salvar ou descartar com motivo (sinal de preferência para o ranking do próprio financiador) |
| GET | `/v1/files/{token}` | pública | limite 600/3600s | Entrega do arquivo via token assinado e de curta duração (storage local) |
| GET | `/v1/financeiro/expenses` | admin da plataforma + MFA | — | Despesas da plataforma por competência |
| POST | `/v1/financeiro/expenses` | admin da plataforma + MFA | — | Registra despesa da plataforma (quem registra não aprova) |
| GET | `/v1/financeiro/fee-preview` | admin da plataforma + MFA | — | CALCULA a taxa de marketplace sobre um valor — e diz que ela não é cobrável |
| GET | `/v1/financeiro/instructions` | admin da plataforma + MFA | — | Instruções de pagamento, por situação |
| POST | `/v1/financeiro/instructions` | admin da plataforma + MFA | — | Emite instrução de pagamento (documento; a plataforma não executa o pagamento) |
| POST | `/v1/financeiro/instructions/{instruction_id}/executed` | admin da plataforma + MFA | — | Registra que quem paga executou, com evidência (obrigatória) |
| POST | `/v1/financeiro/instructions/{instruction_id}/issue` | admin da plataforma + MFA | — | Emite a instrução aprovada — valor e destinatário congelam a partir daqui |
| GET | `/v1/financeiro/summary` | admin da plataforma + MFA | — | Recebível, pagável, instruções em aberto e gasto por centro de custo |
| GET | `/v1/firstrun` | usuário autenticado | papel ≥ viewer | Estado de primeiro acesso por área: o que é, por que está vazia, próximo passo e o que se ganha |
| GET | `/v1/fiscal/estimates` | membro da organização ativa | tipos: company; papel ≥ analyst; plano: `fiscal.estimates` | Mecanismos possivelmente aplicáveis (regras aprovadas e vigentes): REGRA × ELEGIBILIDADE PROVÁVEL × ESTIMATIVA × VALIDAÇÃO |
| GET | `/v1/fiscal/rules` | membro da organização ativa | papel ≥ viewer | Regras fiscais aprovadas (fonte, versão e vigência) |
| GET | `/v1/frameworks` | usuário autenticado | — | Referenciais reconhecidos, com o que a plataforma implementa e o que NÃO mapeia |
| GET | `/v1/frameworks/mappings` | membro da organização ativa | papel ≥ viewer | Mapeamentos de indicador para referencial |
| POST | `/v1/frameworks/mappings` | membro da organização ativa | papel ≥ manager | Mapeia um indicador (a escada vai até 'audited'; 'certified' é recusado) |
| DELETE | `/v1/frameworks/mappings/{mapping_id}` | membro da organização ativa | papel ≥ manager | Remove um mapeamento da própria organização |
| GET | `/v1/frameworks/{framework_key}/coverage` | membro da organização ativa | papel ≥ viewer | Consigo relatar neste referencial? Responde com número, não com impressão |
| GET | `/v1/funding-quotas` | membro da organização ativa | papel ≥ viewer | Cotas da organização, com quantas faltam |
| POST | `/v1/funding-quotas` | membro da organização ativa | papel ≥ manager | Cria cotas de financiamento para um projeto (o valor da cota é definido pela organização proponente) |
| PATCH | `/v1/funding-quotas/{quota_id}` | membro da organização ativa | papel ≥ manager | Abre, pausa ou fecha as cotas e ajusta rótulo/prazo (quantidade e valor não mudam depois de criados) |
| GET | `/v1/funding-quotas/{quota_id}/pledges` | membro da organização ativa | papel ≥ viewer | Apoios de uma cota (proponente vê todos; apoiadora vê os seus) |
| POST | `/v1/funding-quotas/{quota_id}/pledges` | membro da organização ativa | papel ≥ member; limite 60/3600s | Reserva cotas (o banco impede vender mais do que existe, inclusive com pedidos simultâneos) |
| GET | `/v1/gov/territory-stats` | membro da organização ativa | tipos: government, platform; papel ≥ viewer; plano: `gov.data` | Dados agregados e anonimizados por território e causa (k-anonimato ≥ 3 projetos por grupo) |
| POST | `/v1/graph-edges/{edge_id}/validate` | membro da organização ativa | tipos: company, government, individual; papel ≥ manager | Revisão externa (financiador do projeto) que promove a ligação a 'causalidade validada', com evidência e justificativa |
| GET | `/v1/help/activities` | usuário autenticado | — | Minhas atividades: chamados, cursos, eventos, certificados e solicitações |
| GET | `/v1/help/articles` | pública | limite 600/3600s | Lista de guias/artigos publicados (visibilidade por perfil) |
| GET | `/v1/help/articles/{slug}` | pública | limite 600/3600s | Guia/artigo com passos, checklist, erros comuns, documentos necessários, ação e conteúdos relacionados |
| POST | `/v1/help/assistant` | pública | limite 60/3600s | Assistente ancorado: responde SÓ com conteúdo publicado, cita fontes; sem base suficiente recusa e oferece chamado. Não usa IA generativa. |
| GET | `/v1/help/categories` | pública | limite 600/3600s | Categorias com contagem de conteúdo publicado visível para o perfil |
| GET | `/v1/help/certificates/{code}` | pública | limite 60/3600s | Verifica a autenticidade de um certificado de conclusão pelo código |
| GET | `/v1/help/checklists` | usuário autenticado | — | checklist get |
| PUT | `/v1/help/checklists` | usuário autenticado | — | Salva o progresso de um checklist (por pessoa e, opcionalmente, por projeto) |
| GET | `/v1/help/context` | pública | limite 600/3600s | Ajuda contextual de uma tela/campo (artigos, FAQs e modelos mapeados) |
| GET | `/v1/help/courses` | pública | limite 600/3600s | Cursos publicados e trilhas por perfil |
| GET | `/v1/help/courses/{slug}` | pública | limite 600/3600s | Curso: módulos, aulas e progresso (quando autenticada) |
| POST | `/v1/help/courses/{slug}/certificate` | usuário autenticado | — | Emite o certificado de conclusão (não oficial) quando todas as aulas foram concluídas |
| POST | `/v1/help/courses/{slug}/enroll` | usuário autenticado | — | course enroll |
| POST | `/v1/help/demo-requests` | pública | limite 5/3600s | Agendamento de demonstração (consentimento obrigatório) |
| GET | `/v1/help/events` | pública | limite 600/3600s | Agenda de eventos (vagas restantes) e gravações |
| GET | `/v1/help/events/mine` | usuário autenticado | — | Minhas inscrições |
| POST | `/v1/help/events/{event_id}/rate` | usuário autenticado | — | Avalia o evento (só quem participou) |
| DELETE | `/v1/help/events/{event_id}/register` | usuário autenticado | — | Cancela a inscrição e promove a lista de espera |
| POST | `/v1/help/events/{event_id}/register` | usuário autenticado | limite 60/3600s | Inscrição (lista de espera quando lotado) |
| GET | `/v1/help/events/{slug}` | pública | limite 600/3600s | Evento (link de acesso só para inscritas; materiais/gravação após o evento) |
| GET | `/v1/help/faqs` | pública | limite 600/3600s | FAQ inteligente: por categoria, perfil ou tela; com votos de utilidade |
| POST | `/v1/help/feedback` | usuário autenticado | limite 200/3600s | "Este conteúdo ajudou?" — 'Não ajudou' exige o motivo |
| GET | `/v1/help/lessons/{lesson_id}` | usuário autenticado | — | Conteúdo da aula (quiz sem gabarito) |
| POST | `/v1/help/lessons/{lesson_id}/complete` | usuário autenticado | limite 300/3600s | Conclui a aula; quiz é corrigido no servidor (gabarito nunca sai do banco) |
| POST | `/v1/help/newsletter` | pública | limite 10/3600s | Inscrição no boletim com confirmação por e-mail (duplo opt-in). Resposta idêntica exista ou não a inscrição (sem enumeração). |
| POST | `/v1/help/newsletter/confirm` | pública | limite 30/3600s | newsletter confirm |
| POST | `/v1/help/newsletter/unsubscribe` | pública | limite 30/3600s | newsletter unsubscribe |
| POST | `/v1/help/partnerships` | pública | limite 5/3600s | Pedido de parceria (formulário público; consentimento obrigatório para contato) |
| GET | `/v1/help/pending` | usuário autenticado | — | O que falta para eu avançar? (pendências derivadas de dados reais) |
| GET | `/v1/help/recommendations` | usuário autenticado | — | Próximos conteúdos recomendados (etapas faltantes, cursos em andamento, eventos); plano não influencia |
| GET | `/v1/help/resources` | pública | limite 600/3600s | Biblioteca de documentos, modelos, checklists, vídeos e relatórios publicados |
| POST | `/v1/help/resources/{resource_id}/download-url` | usuário autenticado | limite 120/3600s | URL temporária (5 min) do arquivo do recurso; só recurso publicado e visível; arquivo já passou por varredura antivírus |
| POST | `/v1/help/resources/{resource_id}/use-template` | membro da organização ativa | papel ≥ member | Preenche um modelo e cria um rascunho (drafts) da organização — conteúdo gerado do modelo, sem IA |
| GET | `/v1/help/resources/{slug}` | pública | limite 600/3600s | Recurso da biblioteca (com modelo preenchível, checklist e versões anteriores) |
| GET | `/v1/help/search` | pública | limite 600/3600s | Busca híbrida (texto + similaridade + vocabulário de tópicos + perfil + tela). Pública para conteúdo público; autenticada amplia por perfil. Sem embeddings. |
| GET | `/v1/help/sitemap` | pública | limite 600/3600s | Sitemap do conteúdo PÚBLICO indexável (exemplos/DEMO e conteúdo privado ficam de fora) |
| GET | `/v1/help/start` | membro da organização ativa | papel ≥ viewer | Comece aqui: jornada por tipo de organização com % de prontidão calculado por dados reais |
| GET | `/v1/help/trial-requests` | membro da organização ativa | papel ≥ viewer | trial requests mine |
| POST | `/v1/help/trial-requests` | membro da organização ativa | papel ≥ owner; limite 10/3600s | Solicita teste de módulos/ambiente. Não concede acesso: a equipe decide (com motivo) e usa o mecanismo de trial existente. |
| GET | `/v1/ideas` | membro da organização ativa | papel ≥ viewer | Ideias da organização |
| POST | `/v1/ideas` | membro da organização ativa | papel ≥ member | Registra uma ideia (ainda não é projeto, e não consome cota de projeto) |
| GET | `/v1/ideas/{idea_id}` | membro da organização ativa | papel ≥ viewer | get idea |
| PUT | `/v1/ideas/{idea_id}` | membro da organização ativa | papel ≥ member | update idea |
| POST | `/v1/ideas/{idea_id}/promote` | membro da organização ativa | tipos: osc; papel ≥ member | Transforma a ideia em projeto sem apagar a ideia (o projeto guarda a origem) |
| GET | `/v1/impact-tags` | membro da organização ativa | papel ≥ viewer | Marcadores de um objeto |
| POST | `/v1/impact-tags` | membro da organização ativa | papel ≥ manager | Marca um objeto (projeto, solução, diagnóstico, necessidade…) com ODS, pilar ESG ou determinante social |
| DELETE | `/v1/impact-tags/{tag_id}` | membro da organização ativa | papel ≥ manager | Remove um marcador |
| GET | `/v1/impact-taxonomy` | membro da organização ativa | papel ≥ viewer | Catálogo ODS (17), pilares ESG e determinantes sociais, com código, nome e cor oficial |
| GET | `/v1/impact-updates` | membro da organização ativa | papel ≥ viewer | list impact updates |
| POST | `/v1/impact-updates` | membro da organização ativa | papel ≥ member | create impact update |
| GET | `/v1/impact-updates/gather` | membro da organização ativa | papel ≥ viewer | Prévia da apuração do período (mostra ANTES do envio o que será colhido) |
| GET | `/v1/impact-updates/graph` | usuário autenticado | — | impact graph |
| GET | `/v1/impact-updates/inbox` | membro da organização ativa | papel ≥ viewer | Relatórios que esta organização pode analisar (dos projetos que ela apoia) |
| GET | `/v1/impact-updates/{update_id}` | membro da organização ativa | papel ≥ viewer | get impact update |
| PATCH | `/v1/impact-updates/{update_id}` | membro da organização ativa | papel ≥ member | patch impact update |
| POST | `/v1/impact-updates/{update_id}/transition` | membro da organização ativa | papel ≥ manager | Envia, analisa, pede ajuste, aceita ou publica — conforme o lado |
| POST | `/v1/indicator-values/{value_id}/review` | membro da organização ativa | tipos: company, government, individual; papel ≥ analyst | Financiador do projeto valida ou rejeita um valor reportado (a OSC não valida o próprio valor — garantido no banco) |
| GET | `/v1/indicators/catalog` | membro da organização ativa | papel ≥ viewer | Catálogo de indicadores (plataforma, oficiais e definidos pela organização) |
| POST | `/v1/indicators/catalog` | membro da organização ativa | papel ≥ manager | Cria indicador próprio da organização (origem 'org_defined'; não é indicador oficial) |
| GET | `/v1/institutional/agreements` | membro da organização ativa | papel ≥ viewer | Instrumentos firmados (contrato de gestão, termo de parceria/fomento/colaboração…) com alertas de vigência |
| POST | `/v1/institutional/agreements` | membro da organização ativa | papel ≥ manager | Registra um instrumento. Nasce 'declarado' (ou 'comprovante enviado' com documento); só a administração verifica. |
| DELETE | `/v1/institutional/agreements/{agreement_id}` | membro da organização ativa | papel ≥ manager | Remove instrumento ainda não verificado |
| PATCH | `/v1/institutional/agreements/{agreement_id}` | membro da organização ativa | papel ≥ manager | Edita o instrumento. Alterar dados comprobatórios de um instrumento verificado o devolve a 'declarado'/'comprovante enviado'. |
| GET | `/v1/institutional/badges` | membro da organização ativa | papel ≥ viewer | Badges da organização (critério, fonte, data de verificação, validade, estado) — classificação interna, não certificação |
| GET | `/v1/institutional/catalogs` | membro da organização ativa | papel ≥ viewer | Catálogos publicados: naturezas jurídicas, qualificações, perfis, situações, modalidades e definições de badges (com fonte e confiança) |
| GET | `/v1/institutional/documents` | membro da organização ativa | papel ≥ viewer | Documentos institucionais com estado (AUSENTE · EXPIRADO · PENDENTE DE VALIDAÇÃO · VALIDADO · REJEITADO) e quais tipos básicos faltam |
| GET | `/v1/institutional/eligibility` | membro da organização ativa | papel ≥ viewer | Histórico de avaliações de elegibilidade (versão do motor, regras usadas, data) |
| POST | `/v1/institutional/eligibility` | membro da organização ativa | papel ≥ viewer; limite 120/600s | Avalia a elegibilidade institucional (edital, modalidade de financiamento ou requisitos de um financiador): estado + o que falta + regras e fontes usadas |
| GET | `/v1/institutional/formalization` | membro da organização ativa | papel ≥ viewer | Trilha de formalização: etapas derivadas dos dados + etapas declaradas, progresso e próxima etapa |
| PUT | `/v1/institutional/formalization/{step_code}` | membro da organização ativa | papel ≥ manager | Declara o andamento de uma etapa MANUAL (etapas automáticas não são editáveis) |
| GET | `/v1/institutional/maturity` | membro da organização ativa | papel ≥ viewer | Maturidade institucional 0–6 com o que falta para o próximo nível e o caminho de formalização |
| GET | `/v1/institutional/mentoring` | membro da organização ativa | papel ≥ viewer | Pedidos de mentoria da organização |
| POST | `/v1/institutional/mentoring` | membro da organização ativa | papel ≥ member; limite 5/3600s | Pede mentoria (formalização, documentos, projeto, captação, prestação de contas) |
| POST | `/v1/institutional/mentoring/{mentoring_id}/cancel` | membro da organização ativa | papel ≥ member | Cancela um pedido de mentoria em aberto |
| GET | `/v1/institutional/needs` | membro da organização ativa | papel ≥ viewer | Necessidades do proponente (financiamento, parceiro, replicação, técnica, institucional, expansão territorial) |
| POST | `/v1/institutional/needs` | membro da organização ativa | papel ≥ member | Declara uma necessidade (alimenta o match; não é compromisso de ninguém) |
| DELETE | `/v1/institutional/needs/{need_id}` | membro da organização ativa | papel ≥ member | delete need |
| PATCH | `/v1/institutional/needs/{need_id}` | membro da organização ativa | papel ≥ member | patch need |
| GET | `/v1/institutional/orgs/{org_id}` | membro da organização ativa | papel ≥ viewer | Perfil institucional PÚBLICO de uma organização: natureza declarada, qualificações verificadas, situação e badges (sem documentos nem dados privados) |
| GET | `/v1/institutional/overview` | membro da organização ativa | papel ≥ viewer | Visão institucional: 'Pode participar' × 'Pode receber este tipo de recurso' × 'Ainda precisa cumprir requisitos', com maturidade e badges |
| GET | `/v1/institutional/persona` | membro da organização ativa | papel ≥ viewer | Visões por perfil (OS, OSCIP, OSC, iniciativa em estruturação): qualificações, autoridade, áreas, instrumentos, alertas de validade e próximos passos |
| GET | `/v1/institutional/profile` | membro da organização ativa | papel ≥ viewer | Perfil institucional da organização ativa (natureza, perfil de atuação, situação, qualificações) |
| PUT | `/v1/institutional/profile` | membro da organização ativa | papel ≥ admin | Atualiza a natureza jurídica, o perfil de atuação, missão/visão e alcance geográfico (códigos validados no catálogo publicado) |
| GET | `/v1/institutional/qualifications` | membro da organização ativa | papel ≥ viewer | Qualificações e certificações da organização (estado: declarada, em análise, verificada, expirada…) |
| POST | `/v1/institutional/qualifications` | membro da organização ativa | papel ≥ manager | Registra uma qualificação/certificação. Nasce 'declarada' (ou 'comprovante enviado' se houver documento); só a administração verifica. |
| DELETE | `/v1/institutional/qualifications/{qualification_id}` | membro da organização ativa | papel ≥ manager | Remove uma qualificação ainda não verificada (as verificadas são encerradas pela administração) |
| PATCH | `/v1/institutional/qualifications/{qualification_id}` | membro da organização ativa | papel ≥ manager | Edita a qualificação. Alterar o conteúdo comprobatório de uma qualificação verificada a devolve para 'em análise'. |
| GET | `/v1/institutional/qualifications/{qualification_id}/events` | membro da organização ativa | papel ≥ viewer | Histórico (append-only) da qualificação |
| GET | `/v1/institutional/rules` | membro da organização ativa | papel ≥ viewer | Regras de elegibilidade PUBLICADAS (código, versão, fonte, data de consulta, confiança) |
| GET | `/v1/institutional/statement` | membro da organização ativa | papel ≥ viewer | Declaração institucional de apoio (gerada por regras): só afirma o que está cadastrado, rotula o estado e diz 'Não foi possível confirmar' no resto |
| GET | `/v1/integrations/connections` | membro da organização ativa | papel ≥ viewer | connections |
| POST | `/v1/integrations/connections` | membro da organização ativa | papel ≥ manager | Cria conexão em rascunho. Endpoint passa pela guarda de SSRF; ambiente production só com adapter disponível. |
| DELETE | `/v1/integrations/connections/{id}` | membro da organização ativa | papel ≥ owner | Revoga a conexão (credenciais apagadas; histórico de jobs preservado) |
| GET | `/v1/integrations/connections/{id}` | membro da organização ativa | papel ≥ viewer | Conexão com saúde, credencial (só dica), jobs recentes, correspondências e entradas |
| PATCH | `/v1/integrations/connections/{id}` | membro da organização ativa | papel ≥ manager | Altera nome, endpoint, configuração ou estado. Ativar exige configuração válida e credencial quando o provedor pede. |
| DELETE | `/v1/integrations/connections/{id}/credential` | membro da organização ativa | papel ≥ owner | credential delete |
| PUT | `/v1/integrations/connections/{id}/credential` | membro da organização ativa | papel ≥ owner | Grava/rotaciona a credencial (cifrada). A resposta traz só a dica; o segredo nunca volta pela API nem vai para log. |
| POST | `/v1/integrations/connections/{id}/health` | membro da organização ativa | papel ≥ viewer; limite 60/3600s | Verificação de saúde (somente leitura; nunca destrutiva). Uma chamada externa curta. |
| POST | `/v1/integrations/connections/{id}/jobs` | membro da organização ativa | papel ≥ manager; limite 120/3600s | Enfileira um job (executado pelo trabalhador, nunca dentro da requisição). Mesma chave de idempotência → mesmo job. |
| GET | `/v1/integrations/connections/{id}/mappings` | membro da organização ativa | papel ≥ viewer | mappings get |
| PUT | `/v1/integrations/connections/{id}/mappings` | membro da organização ativa | papel ≥ manager | Substitui o conjunto de mapeamentos da conexão (campo externo → campo canônico, com transformação declarada) |
| GET | `/v1/integrations/datasets` | membro da organização ativa | papel ≥ viewer | Datasets exportáveis (BI) — colunas públicas do domínio, filtradas pela organização |
| GET | `/v1/integrations/deliveries` | membro da organização ativa | papel ≥ viewer | deliveries |
| POST | `/v1/integrations/deliveries/{id}/replay` | membro da organização ativa | papel ≥ manager | Replay controlado: só dead-letter da própria organização |
| GET | `/v1/integrations/events` | membro da organização ativa | papel ≥ viewer | events list |
| GET | `/v1/integrations/events/catalog` | membro da organização ativa | papel ≥ viewer | Eventos de domínio que a plataforma realmente emite |
| GET | `/v1/integrations/exports` | membro da organização ativa | papel ≥ viewer | exports list |
| POST | `/v1/integrations/exports` | membro da organização ativa | papel ≥ manager; limite 30/3600s | Gera um dataset (CSV/JSON) da própria organização; download pela URL temporária de documentos |
| GET | `/v1/integrations/imports` | membro da organização ativa | papel ≥ viewer | imports list |
| POST | `/v1/integrations/imports` | membro da organização ativa | papel ≥ manager; limite 60/3600s | Importa a partir de um documento JÁ validado pelo cofre: valida → interpreta → mapeia → pré-visualiza (sem aplicar) |
| GET | `/v1/integrations/imports/{id}` | membro da organização ativa | papel ≥ viewer | Pré-visualização: linhas interpretadas, mapeadas e erros por linha |
| POST | `/v1/integrations/imports/{id}/approve` | membro da organização ativa | papel ≥ owner | Aprova e aplica (só linhas válidas; cria correspondências de ID externo; nunca cria usuários/organizações) |
| POST | `/v1/integrations/inbound/{connection_id}` | pública | limite 600/60s | Recebe webhook de sistema externo: assinatura verificada pelo adapter, deduplicada pelo banco, enfileira job. Nunca processa negócio na requisição. |
| GET | `/v1/integrations/jobs` | membro da organização ativa | papel ≥ viewer | jobs list |
| GET | `/v1/integrations/jobs/{id}` | membro da organização ativa | papel ≥ viewer | job get |
| POST | `/v1/integrations/jobs/{id}/cancel` | membro da organização ativa | papel ≥ manager | job cancel |
| GET | `/v1/integrations/links` | membro da organização ativa | papel ≥ viewer | Correspondências ID interno ↔ ID externo (conflitos nunca são resolvidos em silêncio) |
| GET | `/v1/integrations/providers` | membro da organização ativa | papel ≥ viewer | Catálogo de provedores com matriz de capacidades e maturidade REAL |
| GET | `/v1/integrations/subscriptions` | membro da organização ativa | papel ≥ viewer | subs list |
| POST | `/v1/integrations/subscriptions` | membro da organização ativa | papel ≥ manager | Webhook de saída: HTTPS, assinatura HMAC (t=…,v1=…), retries com backoff e dead-letter |
| DELETE | `/v1/integrations/subscriptions/{id}` | membro da organização ativa | papel ≥ manager | sub delete |
| PATCH | `/v1/integrations/subscriptions/{id}` | membro da organização ativa | papel ≥ manager | sub patch |
| POST | `/v1/integrations/subscriptions/{id}/test` | membro da organização ativa | papel ≥ manager; limite 30/3600s | Emite um evento INTEGRATION.TEST para esta assinatura (entregue pelo trabalhador) |
| POST | `/v1/legal/acceptances` | usuário autenticado | — | Registra aceite (recusado se o documento for minuta não aprovada) |
| GET | `/v1/legal/acceptances/mine` | usuário autenticado | — | O que esta pessoa aceitou, com versão e hash do texto |
| GET | `/v1/legal/documents/{doc_key}` | pública | — | O texto de um documento, com a situação dele e o sha256 do que seria aceito |
| GET | `/v1/legal/pending` | usuário autenticado | — | Documento vigente que esta pessoa ainda não aceitou |
| GET | `/v1/legal/registry` | pública | — | Situação de cada documento legal: versão, se está aprovado e se bloqueia o produto |
| GET | `/v1/legal/{doc}` | pública | — | Texto legal em Markdown, servido do registro versionado (minuta vem marcada como minuta) |
| GET | `/v1/lookups` | usuário autenticado | — | As buscas disponíveis e as origens que cada uma pode devolver |
| GET | `/v1/lookups/{lookup_key}` | membro da organização ativa | papel ≥ viewer | Sugestões com origem, fonte e data — nenhuma é aplicada sozinha |
| GET | `/v1/map/projects` | membro da organização ativa | papel ≥ viewer | Projetos publicados no mapa: pontos só conforme a precisão escolhida + contagem por UF (sem mapa-base externo) |
| GET | `/v1/marketplace/feed` | pública | — | Feed público: lê SÓ anúncios publicados (a publicação é estado da entidade, não condição de consulta) |
| GET | `/v1/marketplace/graph` | usuário autenticado | — | Máquina de estados do anúncio |
| GET | `/v1/marketplace/listings` | membro da organização ativa | papel ≥ viewer | my listings |
| POST | `/v1/marketplace/listings` | membro da organização ativa | papel ≥ manager | Cria o anúncio em rascunho (nada nasce no ar) |
| GET | `/v1/marketplace/listings/{listing_id}` | pública | — | marketplace item |
| PATCH | `/v1/marketplace/listings/{listing_id}` | membro da organização ativa | papel ≥ manager | patch listing |
| POST | `/v1/marketplace/listings/{listing_id}/transition` | membro da organização ativa | papel ≥ manager | Publica, pausa, arquiva (suspender e liberar são da administração) |
| GET | `/v1/match-runs/{match_run_id}/feedback` | membro da organização ativa | papel ≥ viewer | get match feedback |
| POST | `/v1/match-runs/{match_run_id}/feedback` | membro da organização ativa | papel ≥ member | Retorno humano sobre uma recomendação (nada é treinado automaticamente) |
| GET | `/v1/materiality` | membro da organização ativa | papel ≥ viewer | Avaliações de materialidade da organização |
| POST | `/v1/materiality` | membro da organização ativa | papel ≥ manager | Abre uma avaliação (a lente e o limiar são declarados, não subentendidos) |
| GET | `/v1/materiality/topics` | usuário autenticado | — | Temas candidatos a materialidade e as três lentes |
| GET | `/v1/materiality/{assessment_id}` | membro da organização ativa | papel ≥ viewer | A matriz, com `is_material` DERIVADA do eixo e do limiar |
| POST | `/v1/materiality/{assessment_id}/publish` | membro da organização ativa | papel ≥ manager | Publica a avaliação (exige ao menos três temas avaliados) |
| PUT | `/v1/materiality/{assessment_id}/topics` | membro da organização ativa | papel ≥ manager | Avalia um tema nos eixos permitidos pela lente |
| GET | `/v1/materials` | membro da organização ativa | papel ≥ viewer | Biblioteca de materiais governamentais e institucionais publicados |
| POST | `/v1/materials` | membro da organização ativa | tipos: government, platform; papel ≥ manager | create material |
| GET | `/v1/me` | usuário autenticado | — | Usuário, organizações, direitos do plano e token CSRF |
| GET | `/v1/me/context` | usuário autenticado | — | AccessContext: identidade, organização, papéis, plano, período gratuito, permissões |
| GET | `/v1/me/preferences` | usuário autenticado | — | Idioma e tema da pessoa (tema: system, light ou dark) |
| PUT | `/v1/me/preferences` | usuário autenticado | — | Define idioma e tema (a interface pergunta uma vez, logo depois do primeiro acesso) |
| POST | `/v1/me/switch-org` | usuário autenticado | — | switch org |
| GET | `/v1/messages/conversations` | membro da organização ativa | papel ≥ viewer | conversations |
| GET | `/v1/messages/conversations/{conversation_id}` | membro da organização ativa | papel ≥ viewer | get conversation |
| POST | `/v1/messages/{org_id}` | membro da organização ativa | papel ≥ member; limite 120/3600s | Envia mensagem a outra organização (exige relação prévia; limites por hora; bloqueio respeitado) |
| GET | `/v1/moderation/ladder` | usuário autenticado | — | A escada de medidas, com o que cada degrau significa e se exige prazo |
| GET | `/v1/monetization/legal-cards` | usuário autenticado | — | Pesquisa de base normativa por receita (não é parecer jurídico) |
| GET | `/v1/monetization/pipeline` | membro da organização ativa | papel ≥ viewer | O que a plataforma criou de valor que alguma regra alcança — e por que não é cobrado |
| GET | `/v1/monetization/rules` | usuário autenticado | — | As regras de receita, em ordem de hierarquia, com o estado real e a carta legal |
| POST | `/v1/needs/{need_id}/close` | membro da organização ativa | tipos: osc; papel ≥ member | close need |
| GET | `/v1/needs/{need_id}/offers` | membro da organização ativa | tipos: osc; papel ≥ viewer | Ofertas recebidas, com a compatibilidade explicável de cada profissional |
| POST | `/v1/needs/{need_id}/offers` | membro da organização ativa | tipos: provider; papel ≥ member | Profissional oferece ajuda a uma necessidade (a contratação é livre entre as partes, fora da plataforma) |
| GET | `/v1/needs/{need_id}/professionals` | membro da organização ativa | tipos: osc; papel ≥ viewer | Sugestão de profissionais do diretório para a necessidade (match explicável; posição nunca depende de plano) |
| GET | `/v1/network` | membro da organização ativa | papel ≥ viewer | Quem a organização segue, quem a segue, bloqueios e conversas |
| DELETE | `/v1/network/block/{org_id}` | membro da organização ativa | papel ≥ admin | unblock |
| POST | `/v1/network/block/{org_id}` | membro da organização ativa | papel ≥ admin | Bloqueia uma organização (encerra o seguimento e impede mensagens nos dois sentidos) |
| GET | `/v1/network/events` | membro da organização ativa | papel ≥ viewer | Fatos recentes da organização (a fonte única que alimenta avisos, linha de tempo e auditoria) |
| DELETE | `/v1/network/follow/{org_id}` | membro da organização ativa | papel ≥ member | unfollow |
| POST | `/v1/network/follow/{org_id}` | membro da organização ativa | papel ≥ member | Passa a seguir uma organização (seguimento mútuo habilita mensagens) |
| GET | `/v1/network/graph` | membro da organização ativa | papel ≥ viewer | Vizinhança da organização no grafo (profundidade 1 ou 2, sem bloqueios) |
| GET | `/v1/network/relationship-kinds` | usuário autenticado | — | Tipos de relação, com alvos aceitos e teto de visibilidade de cada um |
| GET | `/v1/network/relationships` | membro da organização ativa | papel ≥ viewer | list relationships |
| POST | `/v1/network/relationships` | membro da organização ativa | papel ≥ member | Cria uma relação (idempotente por tipo, origem, destino e contexto) |
| GET | `/v1/network/relationships/counts` | membro da organização ativa | papel ≥ viewer | relationship counts |
| POST | `/v1/network/relationships/{rel_id}/transition` | membro da organização ativa | papel ≥ member | Aceita, recusa, pausa, encerra ou revoga — conforme o lado |
| PUT | `/v1/network/relationships/{rel_id}/visibility` | membro da organização ativa | papel ≥ manager | Altera a visibilidade (limitada ao teto do tipo) |
| GET | `/v1/notifications` | membro da organização ativa | papel ≥ viewer | notifications |
| GET | `/v1/notifications/catalog` | usuário autenticado | — | Quais avisos existem, a qual interruptor pertencem e quais podem sair por e-mail |
| GET | `/v1/notifications/prefs` | usuário autenticado | — | Preferências de notificação por grupo (app e e-mail) |
| PUT | `/v1/notifications/prefs` | usuário autenticado | — | prefs put |
| POST | `/v1/notifications/read-all` | membro da organização ativa | papel ≥ viewer | read all |
| POST | `/v1/notifications/{notification_id}/read` | membro da organização ativa | papel ≥ viewer | read one |
| GET | `/v1/ods` | membro da organização ativa | papel ≥ viewer | 17 ODS e quantidade de metas oficiais carregadas (metas/indicadores oficiais entram por importação) |
| GET | `/v1/ods/{number}/targets` | membro da organização ativa | papel ≥ viewer | ods targets |
| POST | `/v1/offers/{offer_id}/decide` | membro da organização ativa | tipos: osc; papel ≥ manager | decide offer |
| GET | `/v1/operacoes/alerts` | admin da plataforma + MFA | — | CENTRAL DE ALERTAS: o que exige ação agora, por prioridade |
| GET | `/v1/operacoes/health` | admin da plataforma + MFA | — | HEALTH CENTER: banco, migrações, tarefas, backup, integrações e cobrança presa |
| GET | `/v1/org` | membro da organização ativa | papel ≥ viewer | Perfil completo da organização ativa |
| PATCH | `/v1/org` | membro da organização ativa | papel ≥ admin | Atualiza o perfil da organização |
| GET | `/v1/org/credentials` | membro da organização ativa | tipos: provider; papel ≥ viewer | list credentials |
| POST | `/v1/org/credentials` | membro da organização ativa | tipos: provider; papel ≥ member | Registra credencial profissional (CRC, OAB...). Nasce 'autodeclarada' até verificação pela administração. |
| POST | `/v1/org/credentials/{credential_id}/document` | membro da organização ativa | papel ≥ manager | Anexa o documento do conselho à credencial e a coloca na fila de conferência |
| GET | `/v1/org/credentials/{credential_id}/history` | membro da organização ativa | papel ≥ viewer | Histórico append-only da verificação da credencial |
| GET | `/v1/org/experience-requests` | membro da organização ativa | papel ≥ manager | Experiências que pessoas declararam na sua organização e aguardam confirmação |
| POST | `/v1/org/experience-requests/{experience_id}/decide` | membro da organização ativa | papel ≥ manager | Confirma ou contesta a experiência (quem confirma não pode ser a própria pessoa) |
| PUT | `/v1/org/funder-profile` | membro da organização ativa | tipos: company, individual; papel ≥ manager | Perfil de investimento: causas, ODS, ESG, território, ticket, restrições e documentos exigidos |
| PUT | `/v1/org/geo` | membro da organização ativa | papel ≥ owner | Define a localização da organização; tornar pública exige consentimento explícito (registrado com data) |
| GET | `/v1/org/invitations` | membro da organização ativa | papel ≥ admin | list invites |
| POST | `/v1/org/invitations` | membro da organização ativa | papel ≥ admin | invite |
| DELETE | `/v1/org/invitations/{invitation_id}` | membro da organização ativa | papel ≥ admin | revoke invite |
| GET | `/v1/org/members` | membro da organização ativa | papel ≥ viewer | members |
| DELETE | `/v1/org/members/{user_id}` | membro da organização ativa | papel ≥ admin | remove member |
| PATCH | `/v1/org/members/{user_id}` | membro da organização ativa | papel ≥ admin | change role |
| PUT | `/v1/org/provider-profile` | membro da organização ativa | tipos: provider; papel ≥ manager | put provider profile |
| GET | `/v1/org/tax-profile` | membro da organização ativa | tipos: company; papel ≥ analyst | get tax profile |
| PUT | `/v1/org/tax-profile` | membro da organização ativa | tipos: company; papel ≥ manager | put tax profile |
| GET | `/v1/organizations/{org_id}` | membro da organização ativa | papel ≥ viewer | Perfil público de outra organização |
| GET | `/v1/organizations/{org_id}/compliance` | membro da organização ativa | tipos: company, government, individual; papel ≥ viewer | Resumo de compliance de uma OSC com a qual o financiador tem candidatura (due diligence) |
| GET | `/v1/organizations/{org_id}/reputation` | usuário autenticado | — | Perfil de reputação por dimensão (ou de governança, se for órgão público) |
| GET | `/v1/organizations/{org_id}/reputation/timeline` | usuário autenticado | — | Evolução registrada, com a versão do motor de cada ponto |
| POST | `/v1/orgs` | usuário autenticado | — | Cria organização adicional |
| GET | `/v1/payments` | membro da organização ativa | papel ≥ viewer | Pagamentos da organização (como financiador ou OSC) |
| GET | `/v1/payments/charges` | membro da organização ativa | papel ≥ viewer | As cobranças da organização, com o aviso em cada simulada |
| POST | `/v1/payments/charges` | membro da organização ativa | papel ≥ owner | Abre uma cobrança (nada é cobrado: é a intenção de cobrar) |
| GET | `/v1/payments/charges/{charge_id}` | membro da organização ativa | papel ≥ viewer | Uma cobrança com a trilha inteira: por que ela está neste estado |
| PUT | `/v1/payments/charges/{charge_id}/installments` | membro da organização ativa | papel ≥ owner | Grava o cronograma do parcelamento (a soma tem de fechar com o total) |
| POST | `/v1/payments/charges/{charge_id}/transition` | membro da organização ativa | papel ≥ owner | Move a cobrança (recusada se não estiver no grafo) |
| GET | `/v1/payments/state-graph` | usuário autenticado | — | Transições possíveis de uma cobrança, com a origem de cada uma |
| GET | `/v1/payments/status` | usuário autenticado | — | O que está e o que não está configurado para cobrar de verdade |
| GET | `/v1/payments/{payment_id}` | membro da organização ativa | papel ≥ viewer | Pagamento com linha do tempo de estados e estornos |
| POST | `/v1/payments/{payment_id}/reconcile-manual` | membro da organização ativa | tipos: osc; papel ≥ manager | Pareamento manual de uma linha do extrato com um pagamento (registrado em auditoria) |
| POST | `/v1/payments/{payment_id}/refunds` | membro da organização ativa | papel ≥ manager | Solicita estorno total ou parcial (a outra parte decide) |
| POST | `/v1/payments/{payment_id}/transition` | membro da organização ativa | papel ≥ manager | Muda o estado (financiador: declara/cancela; OSC: confirma/recusa; ambos: abrem disputa). O banco recusa transições inválidas |
| GET | `/v1/plans` | pública | — | Catálogo público de planos (tier, preços mensal/anual; preço null = sob consulta) |
| GET | `/v1/plans/price` | pública | — | Preço vigente de um plano: entrada, preço regular, equivalente mensal, total e imposto |
| GET | `/v1/portfolio` | membro da organização ativa | tipos: company, government, individual; papel ≥ viewer | Carteira do financiador: recurso comprometido → desembolsado → gasto comprovado → evidências e resultados |
| POST | `/v1/privacy/consents` | usuário autenticado | — | Registra/revoga consentimento opcional (ex.: comunicações) |
| POST | `/v1/privacy/delete-account` | usuário autenticado | limite 5/3600s | Elimina a conta: anonimiza dados pessoais e revoga sessões. Registros financeiros/auditoria são mantidos pseudonimizados (obrigação legal). |
| GET | `/v1/privacy/export` | usuário autenticado | limite 10/3600s | Exporta os dados pessoais do titular em JSON (art. 18, II e V da LGPD) |
| GET | `/v1/privacy/retention` | usuário autenticado | — | O que a plataforma guarda, por quanto tempo e o que ela NÃO consegue apagar |
| GET | `/v1/procurement/policy` | membro da organização ativa | tipos: osc; papel ≥ viewer | Política de cotações da organização (padrão: 3 cotações) |
| PUT | `/v1/procurement/policy` | membro da organização ativa | tipos: osc; papel ≥ admin | Configura nº mínimo de cotações, valor a partir do qual exige, limite de desvio e aprovação de exceções |
| GET | `/v1/procurement/{request_id}` | membro da organização ativa | papel ≥ viewer | Pedido com cotações, benchmark (média, mediana, mín., máx., desvio) e conformidade com a política |
| POST | `/v1/procurement/{request_id}/approve-exception` | membro da organização ativa | tipos: osc; papel ≥ admin | Aprova a exceção à política (usuário diferente de quem decidiu) |
| POST | `/v1/procurement/{request_id}/decide` | membro da organização ativa | tipos: osc; papel ≥ manager | Decide a compra: com cotações suficientes escolhe uma (justifica se não for a menor); sem elas, registra exceção (com aprovação) |
| POST | `/v1/procurement/{request_id}/quotes` | membro da organização ativa | tipos: osc; papel ≥ member | add quote |
| DELETE | `/v1/procurement/{request_id}/quotes/{quote_id}` | membro da organização ativa | tipos: osc; papel ≥ member | delete quote |
| GET | `/v1/professional-reviews` | membro da organização ativa | papel ≥ viewer | list reviews |
| POST | `/v1/professional-reviews` | membro da organização ativa | papel ≥ member; plano: `professional.request` | Solicita validação a profissional parceiro habilitado (contrato e honorários fora da plataforma) |
| GET | `/v1/professional-reviews/{review_id}` | membro da organização ativa | papel ≥ viewer | get review |
| POST | `/v1/professional-reviews/{review_id}/respond` | membro da organização ativa | papel ≥ member | Profissional aceita/recusa, pede ajustes ou aprova (aprovação exige credencial verificada e vigente) |
| GET | `/v1/professional-services` | membro da organização ativa | papel ≥ viewer | Atividades cadastradas pela organização |
| POST | `/v1/professional-services` | membro da organização ativa | tipos: provider, individual; papel ≥ manager | Cadastra uma atividade oferecida (preço é da profissional, com margem de negociação) |
| PATCH | `/v1/professional-services/{service_id}` | membro da organização ativa | papel ≥ manager | Altera ou publica uma atividade |
| GET | `/v1/professional/offers` | membro da organização ativa | tipos: provider; papel ≥ viewer | my offers |
| GET | `/v1/professional/opportunities` | membro da organização ativa | tipos: provider; papel ≥ viewer | Necessidades abertas de projetos publicados, ordenadas por compatibilidade explicável (plano/voucher não influenciam) |
| GET | `/v1/profile/experiences` | usuário autenticado | — | list experiences |
| POST | `/v1/profile/experiences` | usuário autenticado | — | Declara experiência profissional (nasce 'declarada'; confirmação é de quem administra a organização) |
| POST | `/v1/profiles` | membro da organização ativa | papel ≥ manager | Cria o perfil público (@identificador único, com normalização e reservas) |
| GET | `/v1/profiles/handle-available` | usuário autenticado | — | handle available |
| GET | `/v1/profiles/handle-suggest` | usuário autenticado | — | handle suggest |
| GET | `/v1/profiles/mine` | membro da organização ativa | papel ≥ viewer | my profiles |
| PATCH | `/v1/profiles/{profile_id}` | membro da organização ativa | papel ≥ viewer | Edita o perfil e remonta a projeção pública |
| GET | `/v1/profiles/{profile_id}/handle-history` | membro da organização ativa | papel ≥ viewer | Histórico de identificadores (append-only: trocar é permitido, apagar o rastro não) |
| POST | `/v1/profiles/{profile_id}/rebuild` | membro da organização ativa | papel ≥ viewer | Remonta a projeção pública a partir do estado atual |
| GET | `/v1/programs` | membro da organização ativa | papel ≥ viewer | Programas da organização |
| POST | `/v1/programs` | membro da organização ativa | papel ≥ manager | Cria um programa (nasce em rascunho; o limite do plano é conferido aqui) |
| GET | `/v1/programs/feed` | pública | — | Programas publicados (público, sem sessão) |
| GET | `/v1/programs/status-graph` | usuário autenticado | — | Transições possíveis de um programa, com quem move e se exige motivo |
| GET | `/v1/programs/{program_id}` | pública | — | Um programa, com o declarado e o apurado em objetos separados |
| PATCH | `/v1/programs/{program_id}` | membro da organização ativa | papel ≥ manager | Edita o que é declarado (situação e datas derivadas não passam por aqui) |
| POST | `/v1/programs/{program_id}/calls` | membro da organização ativa | papel ≥ manager | Pendura um edital da própria organização no programa |
| DELETE | `/v1/programs/{program_id}/calls/{call_id}` | membro da organização ativa | papel ≥ manager | Desfaz o vínculo com o edital |
| POST | `/v1/programs/{program_id}/indicators` | membro da organização ativa | papel ≥ manager | Acrescenta indicador ao programa (linha de base exige fonte) |
| POST | `/v1/programs/{program_id}/needs` | membro da organização ativa | papel ≥ manager | Liga o programa a uma necessidade de território (habilita a análise de lacuna) |
| POST | `/v1/programs/{program_id}/projects` | membro da organização ativa | papel ≥ manager | Põe ou move um projeto no programa, com o papel que ele tem ali |
| POST | `/v1/programs/{program_id}/transition` | membro da organização ativa | papel ≥ manager | Move a situação do programa (recusada se não estiver no grafo) |
| POST | `/v1/project-indicators/{pi_id}/values` | membro da organização ativa | tipos: osc; papel ≥ member | Reporta valor medido (status 'reported'; só vira 'validated' por quem não reportou) |
| GET | `/v1/project-status-graph` | membro da organização ativa | papel ≥ viewer | Máquina de situações do projeto (é DADO no banco, não código: um gatilho recusa o que não está aqui) |
| GET | `/v1/projects` | membro da organização ativa | tipos: osc; papel ≥ viewer | Projetos da OSC |
| POST | `/v1/projects` | membro da organização ativa | tipos: osc; papel ≥ member | create project |
| DELETE | `/v1/projects/{project_id}` | membro da organização ativa | tipos: osc; papel ≥ admin | Exclui projeto em rascunho |
| GET | `/v1/projects/{project_id}` | membro da organização ativa | papel ≥ viewer | Detalhe do projeto (OSC dona, financiadores com relação ou projeto publicado) |
| PATCH | `/v1/projects/{project_id}` | membro da organização ativa | tipos: osc; papel ≥ member | patch project |
| POST | `/v1/projects/{project_id}/budget-items` | membro da organização ativa | tipos: osc; papel ≥ member | add item |
| DELETE | `/v1/projects/{project_id}/budget-items/{item_id}` | membro da organização ativa | tipos: osc; papel ≥ member | del item |
| GET | `/v1/projects/{project_id}/context-return` | membro da organização ativa | papel ≥ viewer | O que declarar contexto destravou, e o que cada peça que falta destravaria (sem ranking) |
| GET | `/v1/projects/{project_id}/contribution-models` | membro da organização ativa | papel ≥ viewer | Modelos de contribuição do projeto (a OSC vê todos; os demais, só os aprovados juridicamente) |
| POST | `/v1/projects/{project_id}/contribution-models` | membro da organização ativa | tipos: osc; papel ≥ manager | Propõe um modelo (doação, patrocínio, cotas, lei de incentivo, investimento de impacto). Nasce em rascunho |
| GET | `/v1/projects/{project_id}/data-quality` | membro da organização ativa | papel ≥ viewer | Achados sobre o DADO declarado — nunca avaliação do projeto (§69) |
| GET | `/v1/projects/{project_id}/equity` | membro da organização ativa | papel ≥ viewer | O contexto declarado do projeto, as barreiras e o que é normalizável |
| GET | `/v1/projects/{project_id}/equity/assessments` | membro da organização ativa | papel ≥ viewer | Histórico dos retratos de contexto do projeto |
| POST | `/v1/projects/{project_id}/equity/assessments` | membro da organização ativa | papel ≥ manager | Grava o retrato do contexto (append-only; não produz nota de equidade) |
| POST | `/v1/projects/{project_id}/equity/barriers` | membro da organização ativa | papel ≥ manager | Declara uma barreira do contexto ('evidenciada' exige evidência registrada) |
| DELETE | `/v1/projects/{project_id}/equity/barriers/{barrier_code}` | membro da organização ativa | papel ≥ manager | Desfaz a declaração de uma barreira |
| PUT | `/v1/projects/{project_id}/equity/context` | membro da organização ativa | papel ≥ manager | Declara necessidade, adicionalidade e cenário-base (com a escada de prova) |
| GET | `/v1/projects/{project_id}/equity/normalization` | membro da organização ativa | papel ≥ viewer | Normalização rotulada; método sem denominador com fonte vem indisponível |
| GET | `/v1/projects/{project_id}/evidences` | membro da organização ativa | papel ≥ viewer | list evidences |
| POST | `/v1/projects/{project_id}/evidences` | membro da organização ativa | tipos: osc; papel ≥ member | Posta evidência de uma etapa (foto, lista de presença, relatório, resultado de indicador) |
| GET | `/v1/projects/{project_id}/expenses` | membro da organização ativa | papel ≥ viewer | Despesas do projeto (OSC dona e financiadores com aporte) |
| POST | `/v1/projects/{project_id}/expenses` | membro da organização ativa | tipos: osc; papel ≥ member | Registra despesa com comprovante (nota fiscal/recibo) vinculada a marco e item de orçamento |
| GET | `/v1/projects/{project_id}/expenses.csv` | membro da organização ativa | papel ≥ viewer | Exporta despesas em CSV (prestação de contas) |
| GET | `/v1/projects/{project_id}/feedbacks` | membro da organização ativa | papel ≥ viewer | Devolutivas e relatórios |
| POST | `/v1/projects/{project_id}/feedbacks` | membro da organização ativa | papel ≥ member | OSC envia relatório parcial/final; financiador envia devolutiva |
| GET | `/v1/projects/{project_id}/graph` | membro da organização ativa | papel ≥ viewer | Impact Graph: nós, ligações e a legenda dos tipos de evidência |
| POST | `/v1/projects/{project_id}/graph/edges` | membro da organização ativa | tipos: osc; papel ≥ member | Cria ligação. 'observed_evidence' exige evidência; 'validated_causality' só por revisão externa (rota própria) |
| DELETE | `/v1/projects/{project_id}/graph/edges/{edge_id}` | membro da organização ativa | tipos: osc; papel ≥ member | delete edge |
| POST | `/v1/projects/{project_id}/graph/nodes` | membro da organização ativa | tipos: osc; papel ≥ member | add node |
| DELETE | `/v1/projects/{project_id}/graph/nodes/{node_id}` | membro da organização ativa | tipos: osc; papel ≥ member | delete node |
| GET | `/v1/projects/{project_id}/impact` | membro da organização ativa | papel ≥ viewer | ODS, indicadores (reportado × validado) e progresso do projeto |
| POST | `/v1/projects/{project_id}/indicators` | membro da organização ativa | tipos: osc; papel ≥ member | add project indicator |
| DELETE | `/v1/projects/{project_id}/indicators/{pi_id}` | membro da organização ativa | tipos: osc; papel ≥ member | remove project indicator |
| GET | `/v1/projects/{project_id}/ledger` | membro da organização ativa | papel ≥ viewer | Impact Ledger do projeto (append-only, encadeado por hash) com verificação de integridade |
| GET | `/v1/projects/{project_id}/lifecycle` | membro da organização ativa | papel ≥ viewer | Situação atual, para onde pode ir e o que já aconteceu |
| PUT | `/v1/projects/{project_id}/location` | membro da organização ativa | tipos: osc; papel ≥ member | Define a precisão pública da localização (exata, aproximada, bairro, município, região) e as coordenadas privadas |
| POST | `/v1/projects/{project_id}/milestones` | membro da organização ativa | tipos: osc; papel ≥ member | Fracionamento: marcos/etapas com valor e prazo (soma ≤ orçamento) |
| DELETE | `/v1/projects/{project_id}/milestones/{milestone_id}` | membro da organização ativa | tipos: osc; papel ≥ member | del milestone |
| GET | `/v1/projects/{project_id}/needs` | membro da organização ativa | papel ≥ viewer | list needs |
| POST | `/v1/projects/{project_id}/needs` | membro da organização ativa | tipos: osc; papel ≥ member | Publica uma necessidade de profissional (ex.: contador, jurídico, avaliador de impacto) vinculada ao projeto |
| PUT | `/v1/projects/{project_id}/ods-targets` | membro da organização ativa | tipos: osc; papel ≥ member | Define o alinhamento do projeto a ODS/metas (declarado; sobe de nível com evidência validada e revisão profissional) |
| GET | `/v1/projects/{project_id}/procurement` | membro da organização ativa | papel ≥ viewer | Pedidos de compra do projeto (OSC dona ou financiador) |
| POST | `/v1/projects/{project_id}/procurement` | membro da organização ativa | tipos: osc; papel ≥ member | create request |
| POST | `/v1/projects/{project_id}/publish` | membro da organização ativa | tipos: osc; papel ≥ manager | Publica o projeto no feed de financiadores (exige dados mínimos e e-mail confirmado) |
| GET | `/v1/projects/{project_id}/report` | membro da organização ativa | papel ≥ viewer | Relatório consolidado do projeto (dados para gráficos: orçamento × captado × gasto, evidências, indicadores) |
| GET | `/v1/projects/{project_id}/result-chain` | membro da organização ativa | papel ≥ viewer | Cadeia de resultado do projeto, com a força declarada de cada elo |
| GET | `/v1/projects/{project_id}/risks` | membro da organização ativa | papel ≥ viewer | list risks |
| POST | `/v1/projects/{project_id}/risks` | membro da organização ativa | papel ≥ member | create risk |
| POST | `/v1/projects/{project_id}/risks/scan` | membro da organização ativa | papel ≥ member | Aplica as regras de risco sobre o projeto (indícios, revisados por pessoa) |
| PUT | `/v1/projects/{project_id}/risks/{risk_id}` | membro da organização ativa | papel ≥ member | Atualiza o risco (a origem nunca muda: risco apontado por regra não passa a declarado) |
| GET | `/v1/projects/{project_id}/snapshots` | membro da organização ativa | papel ≥ viewer | list snapshots |
| POST | `/v1/projects/{project_id}/snapshots` | membro da organização ativa | papel ≥ member | Guarda um retrato comparável do projeto neste instante |
| GET | `/v1/projects/{project_id}/snapshots/compare` | membro da organização ativa | papel ≥ viewer | Compara dois retratos campo a campo (o que mudou, entrou e saiu) |
| GET | `/v1/projects/{project_id}/state` | membro da organização ativa | papel ≥ viewer | Estado comparável do projeto agora (mesma estrutura dos retratos) |
| GET | `/v1/projects/{project_id}/team` | membro da organização ativa | papel ≥ viewer | Quem é a equipe do projeto — e portanto quem será avisado em cada mudança |
| GET | `/v1/projects/{project_id}/timeline` | membro da organização ativa | papel ≥ viewer | Linha de tempo imutável (trilha encadeada por hash) |
| GET | `/v1/projects/{project_id}/timeline/integrity` | membro da organização ativa | papel ≥ viewer | Confere o encadeamento da linha de tempo |
| POST | `/v1/projects/{project_id}/transitions` | membro da organização ativa | papel ≥ member | Muda a situação do projeto (recusa explícita quando a máquina não permite) |
| POST | `/v1/projects/{project_id}/unpublish` | membro da organização ativa | tipos: osc; papel ≥ manager | unpublish |
| GET | `/v1/proposals` | membro da organização ativa | papel ≥ viewer | Caixa única de propostas (recebidas, enviadas ou todas) |
| POST | `/v1/proposals` | membro da organização ativa | papel ≥ manager | Cria a proposta em rascunho (exige contexto: projeto, necessidade, edital ou solução) |
| GET | `/v1/proposals/counts` | membro da organização ativa | papel ≥ viewer | proposal counts |
| GET | `/v1/proposals/graph` | usuário autenticado | — | Máquina de estados da proposta, como está no banco |
| GET | `/v1/proposals/{proposal_id}` | membro da organização ativa | papel ≥ viewer | Proposta com histórico, anexos e as ações disponíveis para o seu lado |
| PATCH | `/v1/proposals/{proposal_id}` | membro da organização ativa | papel ≥ manager | Edita a proposta (só em rascunho ou após ajuste solicitado) |
| POST | `/v1/proposals/{proposal_id}/attachments` | membro da organização ativa | papel ≥ member | Anexa documento do cofre à proposta e avisa a outra parte e a equipe |
| POST | `/v1/proposals/{proposal_id}/transition` | membro da organização ativa | papel ≥ manager | Envia, analisa, aceita, recusa, pede ajuste ou retira |
| GET | `/v1/public/campaigns/{slug}` | pública | limite 120/3600s | Campanha pública: história do projeto, meta e QUANTAS COTAS FALTAM |
| GET | `/v1/public/glossary` | pública | limite 120/3600s | Vocabulário oficial: termo da API, rótulo de tela e definição (origem: config/glossary.json) |
| GET | `/v1/public/locales` | pública | limite 120/3600s | Idiomas disponíveis, com a cobertura real de tradução declarada |
| GET | `/v1/public/profiles/{handle}` | pública | — | Perfil público: lê SÓ a projeção curada (public_fields), nunca tabela privada |
| GET | `/v1/public/profiles/{handle}/open-graph` | pública | — | Metadados de compartilhamento, montados da mesma projeção |
| GET | `/v1/public/projects/{project_id}/impact` | pública | — | Relatórios PUBLICADOS de um projeto publicado |
| GET | `/v1/public/relationships/{subject_type}/{subject_id}` | pública | — | Relações PÚBLICAS de um sujeito (filtradas por visibilidade, nunca por existência) |
| GET | `/v1/public/translations` | pública | limite 240/3600s | Catálogo de traduções do idioma (chaves ausentes devem cair para pt-BR no cliente) |
| GET | `/v1/public/verify/{code}` | pública | limite 120/3600s | Verificação pública: genuíno? qual versão foi assinada? integridade intacta? quem assinou? está revogado? |
| GET | `/v1/public/verify/{code}/qr` | pública | limite 120/3600s | QR Code (SVG) da página pública de verificação deste código |
| GET | `/v1/readiness` | membro da organização ativa | tipos: osc; papel ≥ viewer | Leitura de prontidão da organização agora (não grava nada) |
| GET | `/v1/readiness/history` | membro da organização ativa | papel ≥ viewer | readiness history |
| GET | `/v1/readiness/purposes` | membro da organização ativa | papel ≥ viewer | Prontidão por finalidade: seis números, cada um com os critérios que o compuseram |
| POST | `/v1/readiness/snapshots` | membro da organização ativa | papel ≥ member | Grava o retrato da prontidão (append-only, para comparar ao longo do tempo) |
| GET | `/v1/recommendations` | membro da organização ativa | papel ≥ viewer | Próximas ações, com razão e evidência (recomendação não é match) |
| POST | `/v1/recommendations/refresh` | membro da organização ativa | papel ≥ member | Recalcula as recomendações (as que deixaram de valer ficam como superseded, não desaparecem) |
| POST | `/v1/recommendations/{rec_id}/resolve` | membro da organização ativa | papel ≥ member | resolve recommendation |
| POST | `/v1/refunds/{refund_id}/decide` | membro da organização ativa | papel ≥ manager | Aprova/rejeita (a parte que NÃO pediu) ou conclui (OSC registra a devolução) |
| GET | `/v1/replications/marketplace` | membro da organização ativa | papel ≥ viewer | Marketplace de replicação: soluções que o autor autorizou replicar, com contagem de replicações |
| GET | `/v1/report-center` | membro da organização ativa | papel ≥ viewer | Tipos de relatório disponíveis para o tipo da organização |
| GET | `/v1/report-center/{rtype}` | membro da organização ativa | papel ≥ viewer | Gera o relatório (JSON ou CSV). Escopo: projetos próprios (OSC) ou com aporte (financiador) |
| POST | `/v1/reports` | usuário autenticado | limite 20/3600s | Denuncia organização, projeto, edital, documento ou usuário (triagem humana pela administração) |
| GET | `/v1/reports/vocabulary` | usuário autenticado | — | Os quatro níveis (denúncia, suspeita, infração comprovada, consequência jurídica) |
| GET | `/v1/reputation/dimensions` | usuário autenticado | — | As dimensões, o que cada uma NÃO mede, e os sinais excluídos de propósito |
| GET | `/v1/reputation/disputes` | membro da organização ativa | papel ≥ viewer | Contestações da organização, com a resolução quando houver |
| POST | `/v1/reputation/disputes` | membro da organização ativa | papel ≥ manager | Contesta uma dimensão; a contestação aberta aparece no próprio perfil |
| GET | `/v1/reputation/me` | membro da organização ativa | papel ≥ viewer | A reputação da própria organização, calculada na leitura |
| POST | `/v1/reputation/snapshots` | membro da organização ativa | papel ≥ manager | Congela a leitura atual na linha do tempo (append-only) |
| POST | `/v1/responsibility/assignments` | membro da organização ativa | papel ≥ manager | Designa quem responde por um escopo (um papel, um responsável) |
| POST | `/v1/responsibility/assignments/{assignment_id}/end` | membro da organização ativa | papel ≥ manager | Encerra a designação com motivo (responsabilidade não se transfere em silêncio) |
| GET | `/v1/responsibility/current` | usuário autenticado | — | Quem responde agora, e quais papéis estão SEM responsável |
| GET | `/v1/responsibility/decisions` | membro da organização ativa | papel ≥ viewer | Decisões registradas, com papel, pessoa e segunda confirmação quando exigida |
| POST | `/v1/responsibility/decisions` | membro da organização ativa | papel ≥ manager | Registra a decisão; sobre documento, aponta para a VERSÃO |
| GET | `/v1/responsibility/history` | membro da organização ativa | papel ≥ viewer | Histórico completo de designações do escopo, com períodos e motivos |
| GET | `/v1/responsibility/mine` | usuário autenticado | — | O que eu respondo hoje e o que respondi antes |
| GET | `/v1/responsibility/roles` | usuário autenticado | — | Papéis, o que cada um NÃO responde, e os tipos de decisão (com quatro-olhos) |
| GET | `/v1/risk-rules` | membro da organização ativa | papel ≥ viewer | Regras de risco aplicadas (abertas a quem usa) |
| GET | `/v1/saved-searches` | membro da organização ativa | papel ≥ viewer | list saved |
| POST | `/v1/saved-searches` | membro da organização ativa | papel ≥ member; plano: `alerts.saved_search` | Rastreio automático: salva filtros e notifica novos editais compatíveis (planos pagos) |
| DELETE | `/v1/saved-searches/{search_id}` | membro da organização ativa | papel ≥ member | delete saved |
| POST | `/v1/saved-searches/{search_id}/run` | membro da organização ativa | papel ≥ member; plano: `alerts.saved_search` | Executa agora o rastreio desta busca (normalmente executado pelo worker) |
| GET | `/v1/seals/awards` | usuário autenticado | — | Concessões com situação derivada (ativo, expirado, revogado, superado) |
| GET | `/v1/seals/awards/{award_id}` | usuário autenticado | — | O selo, o que ele atesta, o que NÃO atesta e a evidência de cada critério |
| GET | `/v1/seals/definitions` | usuário autenticado | — | Definições com critérios, incluindo rascunhos (para ninguém ser surpreendido) |
| POST | `/v1/seals/evaluate` | membro da organização ativa | papel ≥ viewer | A mesma avaliação que a concessão usa — mostra critério por critério |
| GET | `/v1/seals/evaluations` | membro da organização ativa | papel ≥ viewer | Por que eu não recebi: avaliações da organização, inclusive as que não concederam |
| GET | `/v1/seals/rules` | usuário autenticado | — | Conjunto fechado de critérios implementados em SQL |
| GET | `/v1/signature-policies` | membro da organização ativa | papel ≥ viewer | Política de assinatura por tipo de documento (padrão da plataforma + a da organização) |
| PUT | `/v1/signature-policies` | membro da organização ativa | papel ≥ admin | Define a política de assinatura da organização |
| GET | `/v1/signature-providers` | membro da organização ativa | papel ≥ viewer | Provedores de assinatura e o estado REAL de cada um (o que depende de contratação diz isso) |
| POST | `/v1/signatures` | membro da organização ativa | papel ≥ member; limite 30/3600s | Assinatura eletrônica avançada em DUAS CAMADAS (senha + código de uso único), hash da versão exata, credencial e trilha |
| POST | `/v1/signatures/challenge` | membro da organização ativa | papel ≥ member; limite 30/3600s | Envia o código de confirmação da assinatura (segunda camada), amarrado ao hash exato do conteúdo |
| GET | `/v1/signatures/verify` | membro da organização ativa | papel ≥ viewer | Verifica integridade: hash atual do conteúdo × hash assinado e selo HMAC do servidor |
| POST | `/v1/signatures/{signature_id}/revoke` | membro da organização ativa | papel ≥ owner | Revoga uma assinatura (fato novo: a assinatura em si é append-only e permanece no histórico) |
| GET | `/v1/signed-agreements` | membro da organização ativa | papel ≥ viewer | Acordos em que a organização é dona ou parte |
| POST | `/v1/signed-agreements` | membro da organização ativa | papel ≥ manager | Cria um acordo em rascunho a partir de um documento do cofre (o hash do documento é congelado ao publicar) |
| GET | `/v1/signed-agreements/{agreement_id}` | membro da organização ativa | papel ≥ viewer | Acordo com partes, estado das assinaturas e acompanhamento |
| PATCH | `/v1/signed-agreements/{agreement_id}` | membro da organização ativa | papel ≥ manager | Altera um acordo ainda em rascunho (hash e documento são imutáveis) |
| POST | `/v1/signed-agreements/{agreement_id}/decline` | membro da organização ativa | papel ≥ owner | Recusa o acordo como parte (motivo obrigatório; o acordo é cancelado) |
| POST | `/v1/signed-agreements/{agreement_id}/milestones` | membro da organização ativa | papel ≥ manager | Acrescenta uma entrega ao acompanhamento longitudinal do acordo |
| PATCH | `/v1/signed-agreements/{agreement_id}/milestones/{milestone_id}` | membro da organização ativa | papel ≥ manager | Reporta ou avalia uma entrega do acordo |
| POST | `/v1/signed-agreements/{agreement_id}/parties` | membro da organização ativa | papel ≥ manager | Acrescenta uma parte ao acordo em rascunho |
| POST | `/v1/signed-agreements/{agreement_id}/publish` | membro da organização ativa | papel ≥ manager | Envia o acordo para assinatura (exige pelo menos duas partes obrigatórias) |
| POST | `/v1/signed-agreements/{agreement_id}/sign` | membro da organização ativa | papel ≥ owner; limite 30/3600s | Assina o acordo como parte (duas camadas: senha e código de uso único ligado ao hash) |
| GET | `/v1/solution-intents/mine` | membro da organização ativa | papel ≥ viewer | Meu funil: soluções em que declarei interesse |
| POST | `/v1/solution-intents/{intent_id}/stage` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ admin | O autor confirma uma etapa avançada (negociando … concluído); exige pedido aceito do financiador |
| GET | `/v1/solution-replications/mine` | membro da organização ativa | papel ≥ viewer | Replicações da minha organização (como replicadora) e das minhas soluções (como autora) |
| PATCH | `/v1/solution-replications/{replication_id}` | membro da organização ativa | papel ≥ member | O replicador atualiza o andamento da replicação |
| POST | `/v1/solution-replications/{replication_id}/confirm` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ admin | O autor confirma que a replicação aconteceu |
| GET | `/v1/solution-requests/received` | membro da organização ativa | papel ≥ viewer | Pedidos recebidos pelas minhas soluções |
| GET | `/v1/solution-requests/sent` | membro da organização ativa | papel ≥ viewer | Pedidos enviados pela minha organização |
| POST | `/v1/solution-requests/{request_id}/close` | membro da organização ativa | papel ≥ member | O solicitante encerra o próprio pedido |
| POST | `/v1/solution-requests/{request_id}/respond` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | O autor responde a um pedido |
| POST | `/v1/solutions` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Cadastra uma solução (nasce como rascunho, autodeclarada e não verificada) |
| GET | `/v1/solutions/aggregates` | membro da organização ativa | papel ≥ viewer | Contagens por UF, ODS e tipo das soluções publicadas (mapa e visão por ODS) |
| POST | `/v1/solutions/assistant` | membro da organização ativa | papel ≥ viewer; limite 120/600s | Copiloto ancorado nos dados: responde SOMENTE com soluções realmente cadastradas (sem texto gerado por modelo) |
| GET | `/v1/solutions/combinations` | membro da organização ativa | papel ≥ viewer | Combinações geradas pela minha organização |
| POST | `/v1/solutions/combine` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Combina 2 a 4 soluções: complementaridade, sobreposição, conflitos, dependências — sugestão que exige revisão humana |
| POST | `/v1/solutions/compare` | membro da organização ativa | papel ≥ viewer | Compara 2 a 4 soluções lado a lado |
| GET | `/v1/solutions/funder-preferences` | membro da organização ativa | papel ≥ viewer | Minha tese para soluções |
| PUT | `/v1/solutions/funder-preferences` | membro da organização ativa | tipos: company, government, individual; papel ≥ admin | Tese do financiador para soluções (populações, tipos, horizonte, preferência por comprovadas, tolerância a risco) |
| POST | `/v1/solutions/intent/parse` | membro da organização ativa | papel ≥ viewer; limite 120/600s | Mostra como o texto livre é interpretado (conceitos, ODS, território, orçamento) — sem executar a busca |
| GET | `/v1/solutions/mine` | membro da organização ativa | papel ≥ viewer | Soluções da minha organização (inclui rascunhos) |
| PUT | `/v1/solutions/personalization` | membro da organização ativa | papel ≥ viewer | Aceita ou recusa personalização por histórico (padrão: recusada) |
| GET | `/v1/solutions/recommendations` | membro da organização ativa | papel ≥ viewer | Recomendações com explicação: tese do financiador e, se o usuário aceitou, histórico próprio (salvas e buscas) |
| GET | `/v1/solutions/saved` | membro da organização ativa | papel ≥ viewer | Minhas soluções salvas |
| POST | `/v1/solutions/search` | membro da organização ativa | papel ≥ viewer; limite 120/600s | Busca híbrida por intenção: texto livre + filtros; resposta explica por que cada resultado apareceu |
| GET | `/v1/solutions/vocabulary` | membro da organização ativa | papel ≥ viewer | Vocabulário controlado (temas, populações, instituições) para filtros e cadastro |
| DELETE | `/v1/solutions/{solution_id}` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ admin | Exclui rascunho (publicadas devem ser arquivadas) |
| GET | `/v1/solutions/{solution_id}` | membro da organização ativa | papel ≥ viewer | Perfil completo da solução com proveniência, evidências e pontuações explicadas |
| PATCH | `/v1/solutions/{solution_id}` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Edita a solução (gera nova versão; mudança substantiva de conteúdo verificado volta para 'em revisão') |
| POST | `/v1/solutions/{solution_id}/adapt` | membro da organização ativa | papel ≥ member | ADAPTAÇÃO SUGERIDA — NECESSITA VALIDAÇÃO: o que mudar para outro território/orçamento (ou 'dados insuficientes') |
| GET | `/v1/solutions/{solution_id}/adaptations` | membro da organização ativa | papel ≥ viewer | Adaptações que a minha organização já simulou para esta solução |
| POST | `/v1/solutions/{solution_id}/archive` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ admin | Retira a solução da biblioteca (arquiva) |
| POST | `/v1/solutions/{solution_id}/confirm-review` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Confirma a revisão humana de um rascunho gerado (exigida antes de publicar) |
| POST | `/v1/solutions/{solution_id}/develop` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | “Desenvolver esta ideia”: cria um RASCUNHO derivado (gerado por regras, com [COMPLETAR]); exige revisão humana para publicar |
| POST | `/v1/solutions/{solution_id}/disputes` | membro da organização ativa | papel ≥ member; limite 10/3600s | Contesta a autoria ou o conteúdo (marca a solução como 'em disputa' até decisão humana) |
| POST | `/v1/solutions/{solution_id}/events` | membro da organização ativa | papel ≥ viewer | Registra compartilhamento/comparação (deduplicado por dia) |
| POST | `/v1/solutions/{solution_id}/evidence` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Anexa evidência (nasce 'enviada'; só a administração aceita) |
| GET | `/v1/solutions/{solution_id}/funnel` | membro da organização ativa | papel ≥ viewer | Funil de interesse (organizações distintas; somente o autor) |
| DELETE | `/v1/solutions/{solution_id}/intent` | membro da organização ativa | papel ≥ member | Retira a intenção declarada (apenas das etapas iniciais) |
| PUT | `/v1/solutions/{solution_id}/intent` | membro da organização ativa | papel ≥ member | Declara interesse (descoberta → interessado → em análise). A identidade é privada por padrão |
| GET | `/v1/solutions/{solution_id}/intents` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ viewer | Interessados na minha solução: contagens agregadas + identidades somente das que são públicas ou que fizeram pedido direto |
| POST | `/v1/solutions/{solution_id}/match` | membro da organização ativa | papel ≥ viewer | Aderência desta solução à tese do meu perfil de financiador (independente do plano; explicável) |
| GET | `/v1/solutions/{solution_id}/network` | membro da organização ativa | papel ≥ viewer | Rede de impacto da solução (autor, território, ODS, temas, soluções relacionadas e demanda agregada). Sem identidades privadas de financiadores/replicadores. |
| PUT | `/v1/solutions/{solution_id}/people` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Define autoria e equipe (substitui a lista) |
| POST | `/v1/solutions/{solution_id}/publish` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ admin | Publica a solução na biblioteca (valida o mínimo de conteúdo) |
| POST | `/v1/solutions/{solution_id}/relationships` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Relaciona esta solução a outra (derivada de, replica, complementa, combinada com) |
| PUT | `/v1/solutions/{solution_id}/replication-profile` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Perfil de replicação declarado pelo autor (base do score de replicabilidade) |
| POST | `/v1/solutions/{solution_id}/replications` | membro da organização ativa | papel ≥ member | Manifesta interesse em replicar a solução em um território |
| POST | `/v1/solutions/{solution_id}/request-review` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ admin | Pede verificação à administração |
| POST | `/v1/solutions/{solution_id}/requests` | membro da organização ativa | papel ≥ member; limite 30/3600s | Pede informação, contato, adaptação, replicação ou orçamento ao autor (com limites anti-spam) |
| POST | `/v1/solutions/{solution_id}/results` | membro da organização ativa | tipos: osc, individual, company, government, provider; papel ≥ member | Registra resultado/indicador (nasce 'reportado'; só a administração valida) |
| POST | `/v1/solutions/{solution_id}/reviews` | membro da organização ativa | papel ≥ member | Avalia a solução (só quem teve pedido aceito ou replicação confirmada; não entra no ranking) |
| DELETE | `/v1/solutions/{solution_id}/save` | membro da organização ativa | papel ≥ viewer | Remove da minha lista |
| PUT | `/v1/solutions/{solution_id}/save` | membro da organização ativa | papel ≥ viewer | Salva a solução na minha lista |
| GET | `/v1/solutions/{solution_id}/similar` | membro da organização ativa | papel ≥ viewer | “Quero algo como este”: soluções parecidas, com filtro opcional pelo meu território |
| GET | `/v1/solutions/{solution_id}/versions` | membro da organização ativa | papel ≥ viewer | Histórico de versões (somente a organização autora) |
| POST | `/v1/statements` | membro da organização ativa | tipos: osc; papel ≥ manager | Importa extrato CSV (data;valor;descricao;referencia) para conferir recebimentos. Reimportar o mesmo arquivo é recusado |
| GET | `/v1/statements/lines` | membro da organização ativa | tipos: osc; papel ≥ viewer | statement lines |
| POST | `/v1/statements/reconcile` | membro da organização ativa | tipos: osc; papel ≥ manager | Reexecuta o pareamento extrato × pagamentos |
| GET | `/v1/suppliers` | membro da organização ativa | tipos: osc; papel ≥ viewer | list suppliers |
| POST | `/v1/suppliers` | membro da organização ativa | tipos: osc; papel ≥ member | create supplier |
| GET | `/v1/support/tickets` | usuário autenticado | — | tickets mine |
| POST | `/v1/support/tickets` | usuário autenticado | limite 30/3600s | Abre chamado (categoria, contexto da tela e anexos já enviados em Documentos). Prioridade/SLA são definidos pela equipe. |
| GET | `/v1/support/tickets/{ticket_id}` | usuário autenticado | — | ticket get |
| POST | `/v1/support/tickets/{ticket_id}/close` | usuário autenticado | — | Encerra um chamado já resolvido |
| POST | `/v1/support/tickets/{ticket_id}/messages` | usuário autenticado | limite 120/3600s | ticket reply |
| POST | `/v1/support/tickets/{ticket_id}/rate` | usuário autenticado | — | Avalia o atendimento (após resolvido) |
| GET | `/v1/taxonomies` | usuário autenticado | — | Taxonomias versionadas com política de uso de cada uma |
| GET | `/v1/territorial-gap` | membro da organização ativa | papel ≥ viewer | Demanda registrada contra oferta, por território — agregado, sem dado de pessoa |
| GET | `/v1/territories/catalog-status` | usuário autenticado | — | Quão completo está o catálogo — e o que depende de carga oficial |
| GET | `/v1/territories/definitions` | usuário autenticado | — | O que a plataforma pretende medir por determinante social |
| GET | `/v1/territories/search` | usuário autenticado | — | Busca território por nome ou código, para preenchimento incremental |
| GET | `/v1/territories/{code}` | usuário autenticado | — | Perfil do território: cadeia, indicadores com fonte e o que NÃO foi medido |
| GET | `/v1/territory/needs` | usuário autenticado | — | list territory needs |
| POST | `/v1/territory/needs` | membro da organização ativa | papel ≥ member | Registra necessidade do território (estimativa exige fonte declarada) |
| GET | `/v1/tesouraria/summary` | admin da plataforma + MFA | — | Caixa e patrimônio PRÓPRIO da plataforma (nunca valor de terceiro) |
| GET | `/v1/trust/councils` | membro da organização ativa | papel ≥ viewer | Conselhos profissionais do catálogo (o formato do registro só é validado quando há padrão configurado) |
| GET | `/v1/trust/custody` | membro da organização ativa | papel ≥ viewer | Cadeia de custódia do objeto e conferência do encadeamento por hash |
| GET | `/v1/trust/identity` | usuário autenticado | — | Meu nível de identidade, pedidos e documentos enviados |
| POST | `/v1/trust/identity/verifications` | usuário autenticado | limite 10/3600s | Pede verificação de identidade (documento = conferência humana; biometria e SMS não estão disponíveis) |
| POST | `/v1/trust/identity/verifications/{verification_id}/documents` | usuário autenticado | — | Anexa um documento já enviado ao cofre a um pedido de verificação |
| GET | `/v1/value/events` | membro da organização ativa | papel ≥ viewer | Os eventos de valor da organização, um a um |
| GET | `/v1/value/summary` | membro da organização ativa | papel ≥ viewer | Quanto valor o sistema criou para esta organização (contagem medida, tempo estimado) |
| GET | `/v1/value/types` | usuário autenticado | — | Vocabulário de eventos de valor, com a linha de referência vigente e a fonte dela |
| GET | `/v1/verifiable-records` | membro da organização ativa | papel ≥ viewer | Registros públicos de verificação da organização |
| POST | `/v1/verifiable-records` | membro da organização ativa | papel ≥ manager; limite 120/3600s | Cria o registro público de verificação (código + QR) do documento, rascunho ou acordo |
| GET | `/v1/verifiable-records/{record_id}/qr` | membro da organização ativa | papel ≥ viewer | QR Code (SVG) que aponta para a página pública de verificação |
| POST | `/v1/verifiable-records/{record_id}/revoke` | membro da organização ativa | papel ≥ owner | Revoga o registro público (a página passa a dizer REVOGADO, com motivo e data) |
| POST | `/v1/verifiable-records/{record_id}/timestamp` | membro da organização ativa | papel ≥ manager | Aplica carimbo de tempo interno (RFC 3161 exige ACT contratada e não está disponível) |
| POST | `/v1/vouchers/redeem` | membro da organização ativa | papel ≥ admin; limite 10/3600s | Resgata voucher (transação atômica; resposta genérica para códigos inválidos). Descontos ficam pendentes até o checkout. |
| GET | `/v1/workspace` | membro da organização ativa | papel ≥ viewer | WorkspaceContext: persona, capacidades, contadores, próximas ações e seções em ordem |
| GET | `/v1/workspace/personas` | usuário autenticado | — | Personas disponíveis (persona orienta o workspace; permissão continua vindo de papel e plano) |
| POST | `/v1/workspace/personas` | membro da organização ativa | papel ≥ admin | declare persona |
| DELETE | `/v1/workspace/personas/{persona}` | membro da organização ativa | papel ≥ admin | undeclare persona |

Rotas de infraestrutura: `GET /healthz` (liveness), `GET /readyz` (banco + migrations), `GET /metrics` (Prometheus, Bearer `METRICS_TOKEN`),
`GET /v1/openapi.json`, `GET /v1/meta/taxonomy`, `GET /v1/meta/config`.
