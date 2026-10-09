# Auditoria final de execução — IMPACTO v0.28.0

**Data:** 09/10/2026 · **Ramo:** `main` · **Ponto de partida:** `227c9aa` (v0.27.0) · **Versão:** 0.28.0

Estados: **PASS** (implementado, integrado e provado por teste executado nesta rodada) ·
**PARTIAL** (existe e funciona; o que falta está escrito) · **BLOCKED_EXTERNAL** (depende de conta,
credencial, parecer ou decisão de terceiro; nada simulado) · **FAIL** (falhou e não foi corrigido —
não há nenhum neste relatório; os que apareceram na regressão estão em §7 com a correção).

Cada linha traz evidência, arquivo, teste, resultado, risco e ação restante. Número citado sem
arquivo gerado ou execução registrada não entra. Nada aqui afirma "100% impossível de invadir".

## 1. O pedido → o que virou software

Pedido do proprietário (módulo estratégico + prompt mestre "AI Usage & Cost Control"): IA útil e
acessível, **governável e financeiramente sustentável** — sem consumo ilimitado pago pela
plataforma, sem assinatura (ADR-341), sem excluir quem não pode pagar, sem cobrar o que não executou,
sem confundir preço do cliente com custo do fornecedor; inventário das chamadas de IA ANTES de
construir; camada central com máquina de estados de execução; catálogo de operações versionado
(categorias A–F); cotas configuráveis com anti-abuso; créditos pré-pagos via PIX com webhook
confiável e idempotente; patrocínio institucional; BYOK só se viável (senão documentado); API Claude
× assinatura verificadas na documentação oficial; motor de originalidade/complementaridade/
sobreposição territorial/integridade do financiamento por dimensões (nunca um "% de plágio"), sem
bloqueio automático, sem efeito reputacional, com contestação; projeção financeira (3 cenários, 12
perguntas); limpeza do que não serve mais; **piloto com medição real antes de cobrança real**.

| Item | Estado | Evidência (arquivo · teste) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Inventário de toda chamada de IA, SDK, OCR, job, billing/créditos/webhook existentes, com diagnóstico do estado inicial | PASS | `docs/execution/AI_INVENTORY.md` (grep no código, não no README: `ExternalLLM`, `AiGateway`, `HttpClient`, `jobs.py`, `pytesseract`) | 8 itens pré-existentes diagnosticados (crédito nunca consumido; cota fixa; sem webhook; sem motor de originalidade) | — | — |
| Catálogo de operações versionado, append-only, com categoria A–F, créditos base/por unidade, limites, status (`free/active/hypothesis/planned/retired`) | PASS | `migrations/0068` §1 e §10 (12 operações: 9 executáveis, 3 `planned` → 501) · `test_v0280_ai_usage_control.AdminFinanceTests.test_the_admin_can_publish_a_new_operation_version_and_old_executions_keep_theirs` (publicar versão nova aposenta a anterior; guarda `ai_catalog_guard` só permite `status → retired`), `test_a_planned_operation_answers_501_and_is_in_the_catalog` | passa | — | preço de produção (são hipóteses — ADR-349) |
| Máquina de estados de execução `created → authorized → reserved → running → succeeded/failed/partial/cancelled → reconciled`, com eventos e guarda | PASS | `ai_executions`, `ai_execution_events`, `ai_execution_state_graph`, `ai_execution_guard` (0068 §3); `engines/ai/usage_control.py` (`Run`) · `test_v0280_ai_usage_control.QuotaAndCreditsTests` (`test_a_successful_operation_charges_exactly_the_reserved_credits_and_is_recorded`, `test_a_failed_execution_charges_nothing` — débito só em `succeeded`; falha/parcial não cobra e libera a reserva) | passa | — | — |
| Prévia obrigatória com custo em créditos, fonte de custeio, saldo e critério de conclusão ANTES de executar | PASS | `POST /v1/ai/preview`; `web/src/pages/aicenter.tsx::OperationLauncher`, `projects.tsx::SimilarityPanel` (confirmação "se falhar, nada é cobrado") · `test_preview_shows_cost_funding_and_balance_before_anything_runs`, `test_the_frontend_cannot_set_price_or_balance`, `test_e2e_v0280_ai_center.test_originality_from_the_project_page_with_confirmation_then_dispute_and_center` (diálogo no navegador) | passa | — | — |
| Ordem de custeio gratuito → patrocínio → promocional (cota) → comprado → recusa `402 ai_funding_required` com opções; cache → `cached` sem débito | PASS | `usage_control.authorize()` · `test_purchased_credits_are_used_after_the_quota_and_the_same_inputs_are_not_charged_twice`, `test_a_sponsor_commits_its_own_credits_and_an_eligible_osc_is_funded_until_the_budget_ends`, `test_without_funding_nothing_runs_and_the_answer_lists_options`, `test_e2e_v0280_ai_center.test_without_funding_the_dialog_explains_and_nothing_runs` | passa | — | — |
| Razão de créditos por lote (`purchased`/`promotional`), validade, motivos fechados, escrita só por função SECURITY DEFINER com portão por motivo; consumo atômico e idempotente sob concorrência | PASS | 0068 §2 e §7b (`ai_credit_post`, `ai_credit_consume_bucket`; `ai_credit_consume` da 0058 virou invólucro) · `test_the_ledger_gate_refuses_a_grant_outside_the_policy_from_an_org_context`, `test_concurrent_executions_never_spend_more_than_the_balance`, `test_the_same_idempotency_key_returns_the_same_execution_without_a_second_charge`; `test_v0230_ai_governance` continua verde | passa | — | — |
| Cotas configuráveis (`ai_quota_policies` + `ai_quota_grants`): boas-vindas 60 **uma vez por organização E por pessoa** (anti-abuso de contas), mensal leve 10 para OSC/pessoa | PASS | 0068 §4, `ai_quota_user_has()` · `test_welcome_quota_is_granted_once_per_org_and_once_per_person` | passa | baixo: a cota é promocional e expira | calibrar valores com o piloto |
| Patrocínio institucional: financiador/empresa/governo compra créditos e aponta beneficiários; consumo e prestação de contas agregada; esgotado não migra para a OSC | PASS | 0068 §5 (`ai_sponsorships`, `ai_sponsorship_used`, `ai_sponsorship_report` SECURITY DEFINER) · `SponsorshipTests.test_a_sponsor_commits_its_own_credits_and_an_eligible_osc_is_funded_until_the_budget_ends`, `test_a_sponsorship_above_the_sponsors_balance_is_refused`, robô de telas em `/ia/patrocinios/:id` | passa | — | — |
| Pedidos de crédito (`ai_credit_orders`): pacotes-hipótese; **modo piloto** (aprovação manual sem dinheiro) × **modo real** (exige `webhook`/`manual_reconciliation` + `paid_reference` + razão); `platform_charges.kind = 'ai_credits'`; `charge_requires_authorization` v3 (pedido consentido + regra `ai.credits_prepaid` ativa) | PASS / BLOCKED_EXTERNAL | 0068 §6 · `CreditOrdersAndPixTests` (`test_in_pilot_mode_an_order_has_no_payment_and_can_become_a_promotional_grant_only`, `test_terms_must_be_accepted_and_only_one_open_order_per_org`, `test_a_real_order_is_refused_by_the_database_without_an_active_rule`, `test_a_real_order_can_only_be_credited_with_a_reference_and_never_from_a_simulated_charge`), `test_e2e_v0280_ai_center.test_pilot_credit_order_and_admin_approval_panel` | passa | **nenhuma venda real**: regra inativa (parecer) e provedor de pagamento ausente | parecer jurídico/contábil; provedor PIX com webhook |
| Webhook de pagamento `POST /v1/webhooks/payments/{provider}`: HMAC `x-impacto-signature` sobre o corpo cru, idempotente por `event_id`, 404 `webhook_not_configured` sem `PAYMENT_WEBHOOK_SECRET` | PASS | `api/ai_center_routes.py`, `services/ai_center.apply_payment_webhook` · `WebhookWithSecretTests.test_signature_duplicates_and_single_credit` (assinatura válida credita uma vez; repetida não credita de novo; inválida recusada), `test_webhook_without_secret_is_refused_and_nothing_is_credited` (404) | passa | — | segredo real do provedor por ambiente |
| Nunca pede, guarda ou usa senha/sessão/cookie/token de assinatura Claude.ai; assinatura não paga API de terceiros (verificado na documentação oficial) | PASS | `AI_PROVIDERS_EVALUATION.md` §1 (fontes oficiais) · `test_architecture` (perímetro de segredos), `test_v0280_ai_usage_control` | passa | — | — |
| BYOK (chave do cliente) | BLOCKED_EXTERNAL (documentado, NÃO liberado — ADR-351) | `AI_PROVIDERS_EVALUATION.md` §2 (requisitos: cofre por tenant, teste sem revelar, revogação, sem fallback silencioso, cache isolado, termos do fornecedor) | não existe código BYOK; a interface não promete | — | decisão do proprietário quando houver demanda institucional |
| Motor de similaridade local por **dimensões** (texto, escopo, público, território, tempo, orçamento, financiamento, indicadores) com leituras separadas (reprodução textual ≠ sobreposição de escopo ≠ duplicidade territorial ≠ duplicidade de despesa ≠ complementaridade), recomendações, confiança e aviso de limite | PASS | `engines/similarity/engine.py` (`similarity@1.0`, determinístico, nada sai da instalação) · `test_v0280_similarity.EngineUnitTests` (7: dimensões separadas, indicação ≠ veredito, despesa exige itens+território+tempo, dado incompleto → confiança baixa, múltiplas fontes declaradas e não acusadas, originalidade); conjunto de avaliação rotulado (6 pares) → `docs/evidence/similarity_eval_v0280.json` (reprodução textual P=1,0 R=1,0; duplicidade de despesa P=1,0 R=1,0; complementaridade 6/6) | passa | **médio**: conjunto PEQUENO e sintético; não é medida em base real (o próprio arquivo diz) | ampliar o conjunto com casos reais rotulados no piloto |
| Nenhum bloqueio automático, nenhum efeito em reputação/match/elegibilidade; resultado explicável e contestável; trilha de autoria por versão | PASS | `similarity_analyses` (append-only, cache por `inputs_sha256 + engine_version`), `similarity_disputes` · `test_similarity_touches_neither_match_nor_reputation_nor_funding`, `test_a_changed_version_invalidates_the_cache_and_a_dispute_goes_to_human_review`, `test_published_projects_are_compared_and_the_analysis_is_explainable` | passa | — | — |
| Privacidade/isolamento: projeto de outra organização nunca é comparado em texto; só contagem k-anônima (k ≥ 3) de sobreposição de território | PASS | `similarity_hidden_overlap()` (0068 §8), `services/similarity._visible_candidates` (limite 300) · `test_a_draft_of_another_org_is_never_compared_only_counted_with_k_anonymity` (compara com o valor do banco) | passa | — | — |
| Cobrança da similaridade só por regra de contrato (créditos do catálogo; nunca por fora) | PASS | 0068 §7 (`ai.credits_prepaid`, 11ª regra, `review_required`, carta amarela em `MONETIZATION_LEGAL_MATRIX.md`) · `test_v0150_upgrade.test_09b` (11 regras, 0 ativas), `test_v0170_monetization` | passa | — | parecer para ativar |
| Painel financeiro da administração: estimado × **MEDIDO** × **NÃO MEDIDO**, obrigações (créditos vendidos ≠ lucro), margem parcial, alertas; GMV ≠ receita | PASS | `GET /v1/admin/ai/finance` (`finance.read`), `/admin/ia/financeiro` (menu Controladoria) · `AdminFinanceTests.test_the_finance_panel_requires_finance_read_and_says_what_is_not_measured`, robô de telas | passa | — | — |
| Projeção financeira derivada de hipóteses declaradas: piloto MEDIDO (par 0,75 ms p50; 200 candidatos 153 ms p50), 3 cenários × 12 meses, sensibilidade, as doze perguntas, operação deficitária nomeada, teto de subsídio do piloto declarado (R$ 500/mês, hipótese) | PASS | `scripts/make_ai_cost_model.py`, `config/ai_economics.json`, `AI_COST_MODEL.md`, `docs/evidence/ai_pilot_v0280.json` · `test_v0280_ai_cost_model` (documento = gerador; créditos e cotas = catálogo do banco; aritmética; marcadores de honestidade) | passa | — | substituir hipóteses por medição do piloto |
| Comparação das alternativas A–F com critérios do pedido e escolha justificada (híbrido A + C + D-local; B futuro; E não aplicável) | PASS | `AI_PROVIDERS_EVALUATION.md` §2–§3 | — | — | — |
| Interface: Central de IA (`/ia`), orçamento (`/ia/orcamento`), análise (`/ia/analises/:id`), patrocínio (`/ia/patrocinios/:id`), painel admin; painel de similaridade na ficha do projeto; 225 telas | PASS | `web/src/pages/aicenter.tsx`, `app.tsx`, `projects.tsx` · `test_e2e_v0280_ai_center` (3 jornadas no Chromium, inclusive confirmação de identidade para `billing.write`), `test_v0250_todas_as_telas` (robô por perfil), `test_v0230_frontend` | passa | — | — |
| LGPD: retenção declarada para as tabelas novas; dados pessoais não saem na similaridade (local, faixa 3); resumo de IA passa pela redação já existente | PASS | `config/data_retention.json` (ai_credit_orders, ai_executions, ai_quota_grants, similarity_*) · `test_v0190_lgpd_deletion.RetentionPolicyTests` (classe declarada = regra real) | passa | — | — |
| Limpeza: o que saiu, o que ficou e por quê — sem apagar o que ainda serve | PASS | `docs/execution/CLEANUP_INVENTORY_v0280.md` (19 manifestos → `history/manifests/`; consumo de crédito unificado; documentos SUPERADO mantidos com razão) · `test_v0200_cleanup` (sem código morto), `test_v0230_release_gate` | passa | — | mover SUPERADO numa rodada dedicada |
| Lote, monitoramento recorrente e relatório institucional (categorias E/F) | PARTIAL (declarados, NÃO implementados) | catálogo `planned`; rota responde **501** · `test_a_planned_operation_answers_501_and_is_in_the_catalog` | — | — | fila com orçamento por tarefa e cancelamento, quando houver volume real |

## 2. Motores

50 motores registrados (`backend/impacto/engines/registry.py`; +`ai_usage_control`, `similarity`).
`MOTOR_COVERAGE_MATRIX.md` (gerado): implemented 50/50 · integrated 50/50 · tested 50/50 ·
**VERDE 37 · AMARELO 13 · VERMELHO 0** (45 determinísticos). Os 13 amarelos são motores de leitura sem
rastro durável ou sem rota própria — por desenho, com o motivo listado no próprio documento.
`ENGINE_COVERAGE.md`, `docs/execution/ENGINE_VALIDATION_MATRIX.csv` e `docs/AI_ENGINES.md` regenerados;
`test_v0230_execution_matrices`, `test_architecture` e `test_v0270_release_docs` conferem.

## 3. Perfis, rotas e jornadas

| Prova | Resultado | Fonte |
|---|---|---|
| Jornadas pela API real (sem escrita direta no banco) | **16 jornadas, 256 passos, 0 falha** (15/244 na v0.27.0; nova: "Central de IA: prévia → execução → extrato → patrocínio → análise de similaridade → contestação") | `docs/evidence/jornadas_v0250/relatorio.json`, `test_v0250_jornadas` |
| Telas no Chromium, por perfil, com registro real | **825 visitas às 225 rotas**, 225 abertas com sucesso, 0 falha (OK 544 · vazia 125 · recusa correta 95 · sem registro 61) | `docs/evidence/telas_v0250/resumo.json`, `docs/execution/ROUTE_RUNTIME_MATRIX.csv`, `test_v0250_todas_as_telas` |
| Varredura de autorização | 923 operações, 229 de plataforma a 100%, 94 com permissão, 51 públicas revisadas (webhook incluído: sem segredo → 404) | `docs/execution/API_AUTHORIZATION_MATRIX.csv`, `test_v0230_api_sweep`, `test_v0230_authorization_matrix` |
| Rotas de IA que escrevem (prévia, execução, pedido, patrocínio, contestação, webhook) | limitadas por taxa; pedido de crédito e confirmação de pagamento exigem `billing.write` com confirmação de identidade; contestação admin exige `support.write` | `test_v0220_internal_ui`, `test_v0200_adversarial`, `test_e2e_v0280_ai_center` |
| Acessibilidade | contraste AA claro/escuro, alvos ≥ 24 px, menos movimento, axe | `test_e2e_v0181_accessibility` |
| Matriz por perfil / persona | `docs/execution/COVERAGE_MATRIX.md` (regenerada), `PERSONA_E2E_MATRIX.csv` | `make_coverage_matrix.py`, `make_persona_matrix.py` |

## 4. Monetização (matriz)

| Regra | Situação | Carta | Prova |
|---|---|---|---|
| `ai.credits_prepaid` (NOVA, 11ª) | `active = false`, `review_required`; crédito pré-pago por operação de IA, proponente/empresa/governo; preço = hipótese de teste; **modo piloto** enquanto inativa | 🟡 perguntas abertas (natureza do crédito pré-pago, ISS × ICMS-software, NFS-e, estorno de crédito não usado, validade) | `migrations/0068` §7, `test_v0150_upgrade.test_09b`, `test_v0170_monetization`, `MONETIZATION_LEGAL_MATRIX.md` |
| `contract.platform_service_fee` (3,5%) | inalterada: `active = false`, `review_required` | 🟡 | `test_v0260_contract_rules` |
| as nove restantes | inalteradas (6 amarelas e 5 recusadas no total) | — | `test_v0170_docs.test_the_refused_ones_are_the_five_the_documents_name` |

A camada 3,5% / 1,5% **não muda** e é independente do custeio de IA (ADR-350). Nenhuma regra verde,
nenhuma ativa, nenhum preço inventado: os valores de pacote (R$ 10 / 45 / 160) e de operação são
hipóteses do proprietário para teste, marcadas `hypothesis` no banco e `[PREMISSA]` no modelo.

## 5. Estados de pagamento e créditos (matriz)

| Objeto | Estados | Guarda | Quem confirma |
|---|---|---|---|
| execução de IA | `created → authorized → reserved → running → succeeded / failed / partial / cancelled → reconciled` | `ai_execution_guard` (transição fora do grafo recusada; débito só em `succeeded`) | sistema (camada de uso) |
| pedido de crédito (`mode = pilot`) | `created → credited` (via `pilot_grant`, crédito PROMOCIONAL) / `cancelled` | `ai_credit_order_guard` (`credited` exige `ledger_id`; quantidade, valor, organização e modo imutáveis) | administração (`billing.write`, aprovação manual, sem dinheiro) |
| pedido de crédito (`mode = real`) | `created → awaiting_payment → paid → credited` / `expired` / `cancelled` / `failed` | mesma guarda + `confirmed_via IN (webhook, manual_reconciliation)` + `paid_reference` obrigatórios; o INSERT em modo real é recusado sem regra ativa | webhook assinado do provedor ou conciliação manual com referência |
| cobrança própria `ai_credits` | `platform_charges` (grafo existente) | `charge_requires_authorization` v3 | — |
| patrocínio | `active → exhausted / closed` | consumo por função SECURITY DEFINER; prestação de contas agregada | patrocinador fecha |

Prova: `test_v0280_ai_usage_control` (QuotaAndCreditsTests, CreditOrdersAndPixTests, WebhookWithSecretTests, SponsorshipTests).

## 6. Banco de dados

Migrações: 68 (nova: `0068_v0280_ai_usage_control.sql`, aplicada do zero na suíte e sobre cópia da
v0.27.0 em dry-run com ROLLBACK, `impacto_m68`). Base migrada: **324 tabelas, 323 com RLS**
(exceção: `schema_migrations`), **675 políticas, 0 FORCE** — a contagem de tabelas e políticas
desta instalação de referência é a medida em `impacto_m68` antes da 0068; a suíte (`test_every_table_has_rls`,
`test_force_row_level_security_is_nowhere`) confere a base migrada completa. Tabelas novas: `ai_operations`,
`ai_executions`, `ai_execution_events`, `ai_execution_state_graph`, `ai_quota_policies`, `ai_quota_grants`,
`ai_sponsorships`, `ai_credit_packs`, `ai_credit_orders`, `similarity_analyses`, `similarity_disputes` —
todas com RLS. Nenhuma tabela ou coluna removida. Categoria de auditoria `ai`; `polymorphic_refs` cobre
`ai_credit_ledger`; `data_retention.json` cobre as tabelas novas.

## 7. Regressão — o que a primeira rodada completa encontrou e o que foi feito

Primeira execução completa com o código novo (`scratchpad/suite/full_v0280_a.log`): **2.342 testes,
14 falhas, 0 erro, 29 pulados**. Nenhuma foi "resolvida" afrouxando teste (ADR-340). Causa e correção:

| Falha | Causa real | Correção |
|---|---|---|
| `test_v0190_lgpd_deletion.test_classe_declarada_bate_com_a_regra_real_da_chave` | `data_retention.json` não declarava as tabelas novas com `org_id`/`user_id` | classes declaradas (`ai_credit_orders`, `ai_executions`, `ai_quota_grants` retidas por org e anonimizáveis por pessoa; `similarity_analyses`/`similarity_disputes` retidas) |
| `test_v0220_internal_ui.test_the_write_routes_require_a_write_permission` | rota de decisão de contestação (`POST /v1/admin/ai/disputes/{id}`) escrevia com permissão de leitura `ai.read` | passou a exigir `support.write` (leitura `support.read`) — endurecimento real; entrada SEM_ROTA de `support.write` removida porque a rota agora existe |
| `test_v0230_execution_matrices.test_regenerating_each_matrix_reproduces_what_is_committed` | matrizes citam módulos de teste por nome e não conheciam `test_v0280_*` | regeneradas (`make_engine_matrix`, `make_integration_matrix`, `make_engine_coverage`) |
| `test_v0230_frontend.test_every_new_app_route_points_at_a_component_that_exists` | mapa módulo → arquivo do teste não conhecia o alias `AI` (`pages/aicenter.tsx`) | mapa atualizado |
| `test_v0230_frontend_gate.test_every_installed_package_matches_the_locked_version` | o `sed` do bump de versão alterou também a versão do pacote `scheduler` dentro do `package-lock.json` | versão do `scheduler` restaurada (0.27.0 → valor travado); nenhum pacote alterado |
| `test_v0230_release_gate.test_the_manifest_exists_for_this_version` | manifesto é gerado no fechamento | gerado no fechamento (`FINAL_RELEASE_MANIFEST.json`) |
| `test_v0250_todas_as_telas.test_every_screen_in_the_router_opens_with_real_data` | rotas com parâmetro `/ia/analises/:id` e `/ia/patrocinios/:id` sem resolvedor no robô | resolvedores adicionados em `tests/screen_crawler.py` (análise e patrocínio criados pela API real); contagem 225 com razão |
| `test_v0260_contract_rules.test_obligations_are_derived_from_the_contract_and_four_eyes_hold` | o teste comparava `date.today()` do Python com `current_date` do banco perto da meia-noite (fuso) | o teste lê a data do próprio banco — a prova (obrigação = contrato, quatro olhos) ficou intacta |
| `test_v0270_release_docs` (4: auditoria, relatório, log de testes, manifesto/notas) | documentos de fechamento ainda eram os da v0.27.0 | reescritos para a v0.28.0 (este documento, `FINAL_EXECUTION_REPORT.md`, `RELEASE_NOTES.md`, manifesto) |
| `test_v0280_ai_usage_control.test_the_existing_assistance_routes_now_go_through_the_usage_layer` | o resumo foi custeado por um patrocínio global criado por outro teste da mesma base; o teste exigia `promotional` | o teste aceita `promotional` OU `sponsorship` (ambas provam que a rota passou pela camada de uso); a ordem de custeio tem teste próprio |
| `test_v0280_similarity.test_a_draft_of_another_org_is_never_compared_only_counted_with_k_anonymity` | o teste fixava uma contagem absoluta de sobreposição que depende dos projetos de outros testes na mesma base | o teste compara com `similarity_hidden_overlap()` do banco e continua exigindo k ≥ 3 e nenhuma comparação textual |

Segunda execução completa (após as correções, `docs/evidence/test_run_v0.28.0.log`):
**2.342 testes, 0 erro, 29 pulados, 5 falhas** — todas de fechamento (quatro de `test_v0270_release_docs`, que lê
auditoria, relatório e manifesto no início da execução, quando ainda eram os da v0.27.0; e o manifesto de
release, gerado no fechamento). Nenhuma falha de código, banco, interface ou autorização. Documentos
reescritos e manifestos gerados em seguida; portões reexecutados verdes (saída anexada ao fim do mesmo log).
Detalhe em `FINAL_EXECUTION_REPORT.md` §24.

## 8. Build limpo e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests` | 0 avisos |
| `node build.mjs` (esbuild) | ok; `dist/` regenerado |
| typecheck oficial (`tsconfig.json`) | roda no CI (`npm ci`); reproduzido localmente com o `tsc` da máquina, sem `@types/react` (ruído de tipos ausentes filtrado): nenhum aviso nos arquivos tocados |
| `IMPACTO_TRUST_FINAL_RELEASE_0.28.0.zip` | `scripts/make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; sem ZIP aninhado; SHA-256 ao lado |

## 9. Segurança revisada

- RLS em toda tabela nova; nenhuma FORCE; razão de créditos só por função SECURITY DEFINER com
  portão por motivo (INSERT direto recusado).
- Débito só em sucesso, nunca em falha ou parcial; reserva liberada no cancelamento; idempotência por
  chave; concorrência provada.
- Webhook: HMAC sobre o corpo cru, idempotente por evento, 404 sem segredo configurado; cobrança
  simulada nunca credita; modo real exige referência de pagamento E regra ativa.
- Pedido de crédito e confirmação exigem `billing.write` com confirmação de identidade (step-up);
  contestação admin exige `support.write`.
- Nenhum segredo, token, chave de provedor ou credencial em código, documento ou pacote
  (`secrets_scan.py`; `AI_API_KEY` e `PAYMENT_WEBHOOK_SECRET` só por ambiente); nenhum uso de
  senha/sessão/cookie de assinatura Claude.ai.
- Similaridade: nada sai da instalação (motor local); outra organização só vê contagem k-anônima.
- Contexto de sistema restrito aos módulos revisados (`test_architecture`).
- Nada aqui afirma "100% impossível de invadir".

## 10. BLOCKED_EXTERNAL

Parecer jurídico/contábil da regra `ai.credits_prepaid` (e da taxa de serviço); provedor de pagamento
PIX com webhook (segredo real); provedor de modelo e tabela de preço (`AI_API_KEY`, `ai_price_table`);
BYOK (decisão); nota fiscal; assinatura qualificada/ICP-Brasil/gov.br; biometria/KYC; SMS/WhatsApp;
demais integrações do catálogo; aceite de termos (minutas); endereço público; envio da tag pelo proxy.
Tabela completa: `EXTERNAL_INTEGRATIONS.md`, `EXTERNAL_DEPENDENCIES.md`.

## 11. Veredito desta auditoria

Nenhum FAIL em aberto. Todo requisito crítico interno (inventário antes de construir; catálogo
versionado; execução com estado e débito só em sucesso; razão por lote com portão; cotas com
anti-abuso; patrocínio; pedidos piloto × real; webhook idempotente; similaridade por dimensão sem
bloqueio e sem efeito reputacional, isolada e contestável; painel medido × não medido; projeção
derivada de hipóteses; autorização; tenancy; persistência; regressão) tem teste executado e verde na
segunda rodada. O que impede "GO" puro é externo: parecer, provedor de pagamento, provedor de modelo
e **o piloto com medição real antes de qualquer cobrança real**. **Recomendação: GO WITH CONDITIONS**
— detalhado em `FINAL_EXECUTION_REPORT.md` §27.
