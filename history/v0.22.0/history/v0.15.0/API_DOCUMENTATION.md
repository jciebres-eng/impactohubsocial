# API — documentação (v0.15.0)

Referência completa **gerada do código**: `docs/API.md` (625 operações) e `docs/openapi.json` (também em `GET /v1/openapi.json`). Convenções de autenticação, CSRF, erros e paginação: início de `docs/API.md`.

## Núcleo do produto (51 operações novas, v0.15.0)

| Grupo | Rotas principais |
|---|---|
| Ideias | `GET·POST /v1/ideas` · `GET·PUT /v1/ideas/{id}` · `POST /v1/ideas/{id}/promote` |
| Ciclo de vida | `GET /v1/project-status-graph` · `GET /v1/projects/{id}/lifecycle` · `POST /v1/projects/{id}/transitions` |
| Linha de tempo | `GET /v1/projects/{id}/timeline` · `GET …/timeline/integrity` |
| Retratos | `GET·POST /v1/projects/{id}/snapshots` · `GET …/snapshots/compare?a=&b=` · `GET /v1/projects/{id}/state` |
| Riscos | `GET·POST /v1/projects/{id}/risks` · `PUT …/risks/{rid}` · `POST …/risks/scan` · `GET /v1/risk-rules` |
| Diagnóstico | `GET /v1/readiness` · `GET /v1/diagnoses/{id}/analysis` · `POST·GET /v1/diagnoses/{id}/versions` · `GET …/versions/{n}` · `GET …/versions/compare?a=&b=` · `GET·POST /v1/diagnoses/{id}/actions` · `PUT …/actions/{aid}` · `GET /v1/diagnostic-engine` |
| Modelos de documento | `GET·POST /v1/document-templates` · `GET /v1/document-templates/{id}` · `POST …/{id}/fields` · `POST …/{id}/publish` · `GET /v1/document-assembly-reference` |
| Montagem | `GET·POST /v1/document-assemblies` · `GET·PUT /v1/document-assemblies/{id}` · `POST …/{id}/generate` · `POST …/{id}/review` |
| Match (retorno humano) | `POST·GET /v1/match-runs/{id}/feedback` · `GET /v1/admin/match/calibration` |
| Assinatura | `GET /v1/signature-providers` · `GET /v1/signature-policies` · `PUT /v1/signature-policies` · `PUT /v1/admin/signature-providers/{key}` |
| Chaves (administração) | `GET·POST /v1/admin/encryption/keys` · `POST /v1/admin/encryption/reencrypt` |

**Recusas que fazem parte do contrato** (não são erros a contornar):

| Situação | Resposta |
|---|---|
| transição fora do grafo | `409 invalid_transition`, com a lista do que é possível |
| transição que exige motivo, sem motivo | `422 reason_required` |
| montagem incompleta | `409 assembly_blocked`, com `missing` e `completeness` |
| quem montou tenta aprovar | `409 four_eyes` |
| modelo publicado recebendo campo | `409 template_published` |
| `derived_from` fora da lista fechada | `422 derived_unknown`, com os caminhos disponíveis |
| retorno de match repetido | `409 already_recorded` |
| política exigindo nível indisponível | `409 level_unavailable` |
| promover provedor qualificado sem assimetria real | `409 cannot_promote` |
| tabela sem coluna cifrada registrada | `422 table_not_rotatable` |
| ideia já promovida | `409 already_promoted` |

## Confiança, identidade e assinatura (63 operações novas, v0.14.0)
| Grupo | Rotas principais |
|---|---|
| **Verificação pública (sem login)** | `GET /v1/public/verify/{code}` · `GET /v1/public/verify/{code}/qr` |
| Registros verificáveis | `POST·GET /v1/verifiable-records` · `POST …/{id}/revoke` · `POST …/{id}/timestamp` · `GET …/{id}/qr` |
| Assinatura | `POST /v1/signatures/challenge` (segunda camada) · `POST /v1/signatures` (**agora exige `code`**) · `POST /v1/signatures/{id}/revoke` · `GET /v1/signatures/verify` |
| Integridade e custódia | `GET /v1/documents/{id}/integrity` · `GET /v1/trust/custody?subject_type=&subject_id=` |
| Identidade | `GET /v1/trust/identity` · `POST /v1/trust/identity/verifications` · `POST …/{id}/documents` · `GET /v1/admin/trust/identity/queue` · `POST /v1/admin/trust/identity/{id}/decide` |
| Credencial profissional | `GET /v1/trust/councils` · `POST /v1/org/credentials/{id}/document` · `GET /v1/org/credentials/{id}/history` · `GET /v1/admin/trust/credentials/queue` · `POST …/{id}/decide` · `POST …/{id}/revoke` |
| Acordos | `POST·GET /v1/signed-agreements` · `GET·PATCH …/{id}` · `POST …/{id}/parties·publish·sign·decline·milestones` · `PATCH …/milestones/{id}` |
| Taxonomia | `GET /v1/impact-taxonomy` · `POST·GET /v1/impact-tags` · `DELETE …/{id}` |
| Idioma e tema | `GET /v1/public/locales` · `GET /v1/public/translations` · `GET·PUT /v1/me/preferences` |
| Cotas e campanha | `POST·GET /v1/funding-quotas` · `PATCH …/{id}` · `POST·GET …/{id}/pledges` · `POST /v1/admin/funding-quotas/pledges/{id}/confirm` · `POST·GET·PATCH /v1/campaigns` · `GET /v1/public/campaigns/{slug}` |
| Honorários e serviços | `GET /v1/fee-tables[/{id}]` · `POST /v1/admin/fee-tables[/{id}/items|/publish]` · `POST·GET·PATCH /v1/professional-services` · `GET /v1/directory/services` |
| Georreferência | `PUT /v1/org/geo` |
| Diagnóstico guiado | `GET /v1/diagnoses/{id}/guide` · `PUT /v1/diagnoses/{id}/guide/{stage_code}` |
| Documentos | `POST /v1/drafts/{id}/export` (pdf/docx/odt, com QR opcional) |

Detalhes: `PUBLIC_VERIFICATION.md`, `DIGITAL_SIGNATURE.md`, `TRUST_IDENTITY.md`.

## Integrações (36 operações novas, v0.13.0)
| Grupo | Rotas principais |
|---|---|
| Catálogo | `GET /v1/integrations/providers·datasets·events` |
| Conexões | `POST·GET /v1/integrations/connections` · `GET·PATCH·DELETE …/{id}` · `POST …/{id}/health` |
| Credencial (escreve, nunca lê) | `PUT·DELETE /v1/integrations/connections/{id}/credential` — resposta traz só a dica (`••••4f2a`) |
| Mapeamentos | `GET·PUT /v1/integrations/connections/{id}/mappings` |
| Jobs | `POST·GET /v1/integrations/connections/{id}/jobs` · `GET /v1/integrations/jobs[/{id}]` · `POST …/{id}/cancel` |
| Correspondências | `GET /v1/integrations/links` · `GET /v1/integrations/connections/{id}/links` |
| Webhooks de saída | `POST·GET /v1/integrations/subscriptions` · `PATCH·DELETE …/{id}` · `POST …/{id}/test` · `GET /v1/integrations/deliveries` · `POST …/{id}/replay` |
| Entrada (pública, assinada) | `POST /v1/integrations/inbound/{connection_id}` — HMAC `t=…,v1=…`, `X-Event-Id` obrigatório, duplicado ignorado |
| Arquivos | `POST·GET /v1/integrations/imports` · `GET …/{id}` · `POST …/{id}/approve` · `POST·GET /v1/integrations/exports` |
| Administração | `GET /v1/admin/integrations/overview` · `POST /v1/admin/integrations/providers/{code}/maturity` · `POST /v1/admin/integrations/run-worker` |
Detalhes de estados, assinatura e erros: `INTEGRATION_HUB.md`.

## Central de Conhecimento (102 operações novas, v0.12.0)
| Grupo | Rotas principais |
|---|---|
| Busca/leitura (públicas, com limite de taxa) | `GET /v1/help/search·context·categories·articles[/{slug}]·faqs·resources[/{slug}]·events[/{slug}]·courses[/{slug}]·sitemap` · `POST /v1/help/assistant` · `GET /v1/help/certificates/{code}` |
| Autenticadas | `POST /v1/help/feedback` · `GET·PUT /v1/help/checklists` · `GET /v1/help/start·pending·activities·recommendations` · `POST …/resources/{id}/download-url·use-template` · eventos `…/register·rate` · cursos `…/enroll·certificate`, `GET·POST /v1/help/lessons/{id}[/complete]` |
| Suporte | `POST·GET /v1/support/tickets` · `GET …/{id}` · `POST …/{id}/messages·rate·close` |
| Captação (públicas, consentimento + anti-bot) | `POST /v1/help/partnerships·demo-requests·newsletter` · `POST /v1/help/newsletter/confirm·unsubscribe` · `POST·GET /v1/help/trial-requests` (dono da organização) |
| Preferências | `GET·PUT /v1/notifications/prefs` |
| Administração (`staff`: editor/reviewer/support + administradores, MFA) | `/v1/admin/staff-roles` · `/v1/admin/content/{overview,categories,articles,resources,faqs,courses,paths,events,history}` · `POST …/{id}/transition` por tipo · `POST /v1/admin/content/{tipo}/{id}/reviewed` · `/v1/admin/support/{tickets,sla}` · `/v1/admin/hub/{partnerships,demo-requests,trial-requests,trials,analytics,newsletter,certificates}` |

## Biblioteca de Soluções (60 operações novas)
| Grupo | Rotas principais |
|---|---|
| Cadastro | `POST /v1/solutions` · `PATCH/DELETE /v1/solutions/{id}` · `POST …/publish·archive·confirm-review·request-review` · `GET …/versions` · `GET /v1/solutions/mine` |
| Componentes | `PUT …/people` · `POST …/evidence` · `POST …/results` · `PUT …/replication-profile` · `POST …/relationships` |
| Leitura | `GET /v1/solutions/{id}` (perfil + proveniência + pontuações) · `GET /v1/solutions/vocabulary` · `GET /v1/solutions/aggregates` · `GET …/funnel` |
| Busca | `POST /v1/solutions/search` (rate-limit 120/10 min) · `POST /v1/solutions/intent/parse` · `POST /v1/solutions/assistant` · `GET …/similar` |
| Análise | `POST /v1/solutions/compare` (2–4) · `POST /v1/solutions/combine` · `GET /v1/solutions/combinations` · `POST …/adapt` · `GET …/adaptations` · `POST …/develop` |
| Match | `POST …/match` · `GET /v1/solutions/recommendations` · `PUT/GET /v1/solutions/funder-preferences` · `PUT /v1/solutions/personalization` |
| Interação | `PUT/DELETE …/save` · `GET /v1/solutions/saved` · `POST …/events` · `POST …/requests` · `GET /v1/solution-requests/{received,sent}` · `POST /v1/solution-requests/{id}/respond·close` |
| Intenção | `PUT/DELETE …/intent` · `GET …/intents` · `POST /v1/solution-intents/{id}/stage` · `GET /v1/solution-intents/mine` |
| Replicação | `GET /v1/replications/marketplace` · `POST …/replications` · `PATCH /v1/solution-replications/{id}` · `POST …/confirm` · `GET …/mine` |
| Confiança | `POST …/reviews` · `POST …/disputes` · denúncia via `POST /v1/reports` (`target_type: solution`) |
| Admin | `GET /v1/admin/solutions/queue` · `POST /v1/admin/solution-evidence/{id}/review` · `POST …/solution-results/{id}/validate` · `POST …/solutions/{id}/verify·remove` · `POST …/solution-disputes/{id}/decide` |

Os caminhos pedidos no prompt (`/solutions/{id}/replicate`, `/recommendations`, `/intent`…) foram mapeados para os nomes acima (prefixo `/v1`, recursos no plural). Rotas literais são registradas antes de `/{solution_id}` (ordenação por especificidade em `app.py`).
Segurança por rota: `auth=org` (sessão + CSRF + e-mail verificado em escrita), papéis mínimos, `kinds`, UUID validado em todo `*_id`, corpo com `extra=forbid`, limites de tamanho, RLS no banco.

## Camada institucional (37 operações novas)
| Grupo | Rotas principais |
|---|---|
| Catálogos e regras (leitura) | `GET /v1/institutional/catalogs` · `GET /v1/institutional/rules` |
| Perfil | `GET/PUT /v1/institutional/profile` · `GET /v1/institutional/overview` · `GET …/maturity` · `GET …/statement` · `GET …/badges` · `GET /v1/institutional/orgs/{org_id}` (público) |
| Qualificações | `GET/POST /v1/institutional/qualifications` · `PATCH/DELETE …/{id}` · `GET …/{id}/events` |
| Documentos | `GET /v1/institutional/documents` (com estado) |
| Elegibilidade | `POST /v1/institutional/eligibility` (limite 120/10 min) · `GET /v1/institutional/eligibility` |
| Necessidades | `GET/POST /v1/institutional/needs` · `PATCH/DELETE …/{id}` |
| Admin (MFA) — catálogos | `GET/POST /v1/admin/institutional/catalog` · `…/{id}/new-version` · `…/{id}/action` |
| Admin — regras | `GET/POST /v1/admin/institutional/rules` · `…/{id}/new-version` · `…/{id}/action` · `POST …/rules/import-candidates` |
| Admin — filas | `GET /v1/admin/institutional/qualifications` · `POST …/{id}/decide` · `GET …/documents` · `POST …/{id}/validate` |
| Admin — organização | `GET …/organizations/{org_id}` · `POST …/organizations/{org_id}/status` · `GET …/overview` |
Campos novos: edital (`funding_modality`, `accepted_legal_natures`, `min_maturity`), perfil do financiador, cadastro (`organization.legal_nature_code`), solução (IP/confidencialidade/modalidades) e busca (`legal_natures`, `qualifications`, `modalities`, `funding_ready`, `sharing`).

## Novidades do v0.10.1
`GET /v1/institutional/persona`, `GET/POST /v1/institutional/agreements` (+ `PATCH/DELETE /{id}`), `GET /v1/institutional/formalization`, `PUT /v1/institutional/formalization/{step_code}`, `GET/POST /v1/institutional/mentoring` (+ `POST /{id}/cancel`), `GET /v1/solutions/{id}/network`; admin: `GET /v1/admin/institutional/agreements`, `POST …/agreements/{id}/decide`, `GET /v1/admin/institutional/mentoring`, `POST …/mentoring/{id}/update`. `GET /v1/insights/fiscal-estimates` ganhou `osc_org_id` e o bloco `institutional_eligibility`. Detalhes gerados em `docs/API.md`.

## Monetização (v0.11.0 — 15 operações novas; ver `docs/billing.md`)
| Grupo | Rotas |
|---|---|
| Organização | `GET /v1/plans` (tiers, preços, economia anual) · `GET /v1/billing` · `POST /v1/billing/quote` · `/checkout` · `/cancel` · `/reactivate` · `/change-plan` · `/portal` · `POST /v1/vouchers/redeem` · `POST /v1/agreements/join` |
| Webhook | `POST /v1/billing/webhooks/stripe` (assinatura HMAC, idempotente, fora de ordem) |
| Admin (MFA, motivo, auditoria) | `GET /v1/admin/billing/organizations/{id}` · `POST .../trial` · `POST /v1/admin/grants/{id}/revoke` · `PUT /v1/admin/plans/{plan_key}/price` · `/v1/admin/agreements` (+ `/action`, `/members`, revogar) · `GET /v1/admin/voucher-batches/{id}/redemptions` |
O cliente **não** envia preço, desconto, tier nem direitos: campos extras são recusados (422).
