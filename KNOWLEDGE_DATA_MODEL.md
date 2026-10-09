# KNOWLEDGE_DATA_MODEL — migração `0009_v0120_knowledge_hub.sql` (v0.12.0)

**32 tabelas novas** (banco de desenvolvimento: 120 → **152**), todas com RLS (teste `test_every_table_has_rls`), 16 funções/gatilhos. Migração só para frente; como a 0009 ainda não havia sido liberada, foi ajustada no lugar durante a construção e o banco de desenvolvimento recriado (`scripts/dev_reset_db.sh`).

| Grupo | Tabelas | Garantias no banco |
|---|---|---|
| Papéis internos | `staff_roles` (editor, reviewer, support) | só administração escreve |
| Governança | `content_history` | histórico de transições (autor, de→para, nota) |
| Conteúdo | `kb_categories`, `kb_articles` (+`live_version_id`), `kb_article_versions` | versão **imutável** (`kb_version_immutable`); **quatro olhos** (CHECK `approved_by <> author_id`); regulatório ⇒ fonte+data (CHECK); `kb_visible(visibilidade, público)`; publicar sincroniza `live_version_id` (`kb_sync_article`) |
| Biblioteca | `kb_resources` (versões como linhas `published/superseded`), `kb_faqs` | imutabilidade; índice FTS (`kb_index_row`, `pt_unaccent`) + trigrama; política de leitura `status IN ('published','superseded')` |
| Interação | `kb_feedback`, `kb_checklist_progress`, `kb_events` (analytics) | feedback por pessoa (1 por alvo); analytics **sem texto livre** (hash+assuntos), retenção 18 meses |
| Academia | `courses`, `course_modules`, `course_lessons`, `lesson_quiz_keys`, `course_enrollments`, `lesson_progress`, `course_certificates`, `learning_paths` | gabarito em tabela inacessível à aplicação; `lesson_grade()` SECURITY DEFINER; certificado com código único, `revoked_at` |
| Eventos | `hub_events`, `hub_event_links` (link de acesso), `hub_event_registrations` | link só para inscritas confirmadas (RLS); `hub_event_seats()`; lista de espera |
| Suporte | `support_sla`, `support_tickets`, `support_messages`, `support_attachments` | `support_guard`/`support_msg_guard`: pessoa não define prioridade/estado/SLA/responsável nem escreve como equipe; nota interna oculta por RLS |
| Parcerias | `partnership_requests`, `partnership_activities`, `partnerships`, `demo_requests` | consentimento (versão+data) obrigatório; leitura só pela administração/dona do pedido |
| Teste | `trial_requests` | `requested` até decisão com motivo; reaproveita `org_trials` |
| Boletim/preferências | `newsletter_subscriptions` (**duplo opt-in**, token só como hash), `notification_prefs` | confirmação/cancelamento por funções dedicadas |

Fontes versionadas fora do banco: `config/help_synonyms.json` (assuntos e sinônimos) e `config/onboarding_paths.json` (jornadas e detectores) — **hipóteses editoriais** a validar.

## v0.29.0 — migração `0069_v0290_knowledge_provenance.sql` (ADR-354 a ADR-357)

| Grupo | Tabelas / funções | Garantias no banco |
|---|---|---|
| Fontes | `kb_sources` | chave única; `klass` ∈ O/A/V/H/D; `rights` jsonb validado por `kb_rights_ok()`; `verification` ∈ unverified/verified/disputed/expired com `verified_by ≠ created_by` (trigger `kb_source_guard`); campos de identidade imutáveis; `status` retracted terminal com motivo; DELETE proibido; RLS: leitura pública, escrita `app_priv()` |
| Citações | `kb_citations`, `kb_source_right(uuid, text)` | append-only; `object_type` ∈ article_version/faq/resource; trecho só com `rights.excerpt = allowed` e `excerpt_sha256 = sha256(excerpt)` (trigger `kb_citation_guard`); citação de artigo só em versão `draft`; leitura via conteúdo publicado + `kb_visible` |
| Retirada | `kb_article_versions`, `kb_faqs`, `kb_resources` (+ `retraction_reason/retracted_by/retracted_at`) | CHECK: `retracted` exige os três campos; trigger `kb_retraction_terminal`; `kb_unpublish_article` anula `live_version_id`/`search_doc` |
| Fila editorial | `kb_work_items`, `kb_work_open(kind, dedupe_key, details, reporter)` | `kind` em 8 valores; `dedupe_key` única enquanto open/in_progress (índice parcial) com `occurrences` incrementado; `resolution` obrigatória para done/dismissed; `details` só `q_hash` + tópicos; RLS `app_priv()` |
| Histórico | `content_history.object_type += 'source'` | mesma trilha de transições |
| Auditoria | categoria `kb` em `audit_action_categories`; `polymorphic_refs` para `kb_source`/`kb_work_item` | filtros do painel |
| Semente | 11 fontes (8 leis federais, WCAG 2.2, ODS, base interna v0.26.0) | todas `unverified`, `review_due = 2026-11-07`; direitos `embed/send_external/train = unknown` para texto legal (bloqueado até conferência) |

Tabelas: **+4** (desenvolvimento: 325 → 329), todas com RLS; nenhuma tem `org_id`/`user_id` (nada a declarar em `config/data_retention.json`). Catálogo de conceitos da ajuda contextual **não** está no banco: é `config/concepts.json` servido por `GET /v1/public/concepts` (ADR-359).
