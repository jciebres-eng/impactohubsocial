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
