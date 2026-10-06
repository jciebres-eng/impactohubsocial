# DATABASE_SCHEMA

**v0.18.0 — 285 tabelas, 32 migrações.** O retrato completo e medido do banco (RLS, políticas, gatilhos, funções
`SECURITY DEFINER`, chaves estrangeiras, índices, imutabilidade e caminho de atualização) está em
**`DATABASE_INTEGRITY_REPORT.md`**, com os números colhidos do catálogo do PostgreSQL por
`scripts/db_integrity_report.py`.

## Migrações da v0.17.0

| Migração | O que faz |
|---|---|
| `0018_v0170_programs.sql` | **6 tabelas** do Programa: `programs` (com `objective` NOT NULL), `program_status_graph` (11 arestas, ator `owner`/`platform`/`either`), `program_calls`, `program_projects` (6 papéis), `program_indicators` (CHECK exigindo fonte na linha de base), `program_needs`. Funções `program_has_project_of()` (SECURITY DEFINER), `program_financials()`, `result_chain()`, `territorial_gap()`; gatilhos `program_initial_state()`, `program_status_guard()` (deriva `published_at`/`closed_at` e **RAISE** se alguém tentar escrevê-las), `program_visibility_guard()`, `program_link_guard()`; `notification_prefs` estendido a 15 grupos |
| `0019_v0170_value_ledger.sql` | **4 tabelas** do registro de valor: `value_event_types` (11 tipos com `what_counts`), `value_baselines` (versionada, `minutes_per_unit` **nulo** de fábrica, CHECK `baseline_needs_source`), `value_events` (append-only, **sem INSERT** para a aplicação), `ai_price_table` (nasce **sem nenhuma linha**). Funções `app_record_value()` (porta única, SECURITY DEFINER), `app_price_ai_usage()`; `close_previous_version()` **BEFORE INSERT** (o índice único parcial é conferido antes dos gatilhos AFTER), `version_row_immutable()`; `ai_usage` ganha custo derivado |
| `0020_v0170_monetization.sql` | **3 tabelas** da monetização: `monetization_legal_cards` (append-only, CHECK `green_needs_evidence` e `green_has_no_open_questions`), `monetization_rules` (8 motores, `problem_solved` e `substitution_answer` NOT NULL), `billable_events` (6 estados, com `reason`). Gatilho `monetization_rule_gate()` — o portão legal — e `app_promote_billable()` |
| `0021_v0170_legal_cards.sql` | os **9 cartões legais**, com texto literal de fonte oficial e data de consulta; cada um atualiza `monetization_rules.legal_status` para `refused` ou `review_required` conforme a cor. **Zero verdes** |
| `0022_v0170_payments.sql` | **7 tabelas** do pagamento: `charge_state_graph` (27 arestas), `payment_instruments` (só token; CHECK de quatro dígitos em `last4`), `platform_charges` (`is_simulated` **derivada** de lista explícita de provedores reais), `charge_events` (escrita por gatilho `SECURITY DEFINER`; `REVOKE INSERT` para a aplicação), `charge_installments` (+ `CONSTRAINT TRIGGER ... DEFERRABLE` conferindo a soma no COMMIT), `charge_pix`, `charge_boleto`. Funções `charge_belongs_to()` (SECURITY DEFINER), `platform_revenue()` (simulado em colunas próprias); `billing_events` ganha `signature_verified`, `charge_id`, `duplicate_count`, o estado `rejected_signature` e o CHECK `billing_events_signature_effect` |
| `0023_v0170_legal.sql` | **2 tabelas** do arcabouço legal: `legal_documents` (11 documentos, todos `draft`; CHECK `approved_needs_review` e `effective_needs_approved`) e `legal_acceptances` (prova com sha256 copiado pelo gatilho). Funções `legal_pending()`, `legal_overview()`, `legal_text()`; gatilhos `legal_doc_hash()`, `legal_doc_text_immutable()`, `legal_doc_status_guard()`, `acceptance_stamp()`. **Gerada** por `scripts/gen_legal_registry.py` a partir de `docs/legal/*.md` |
| `0024_v0170_privacy_hardening.sql` | o estreitamento do append-only: `acceptance_anonymize_only()` substitui `forbid_mutation()` em `legal_acceptances`, permitindo **só** apagar IP e agente de usuário, com GRANT de coluna; índice `ix_legal_acc_org` (FK quente apontada pelo relatório de integridade) |

### As quatro estruturas da v0.17.0 que merecem leitura

**`platform_charges`** — `is_simulated` é derivada do provedor por gatilho, contra uma lista **explícita** de
provedores reais. "Todos menos sandbox" faria qualquer provedor novo nascer marcado como real, e um dublê de teste
chamado de outro jeito passaria por dinheiro. A tentativa de alterar a coluna é **recusada**, não sobrescrita.
`paid_at` e `settled_at` são derivados da transição e **não** entram em `guard_columns`, pela lição da 0018.

**`value_events`** — append-only e **sem INSERT para a aplicação**. A única porta é `app_record_value()`, que é
SECURITY DEFINER para que a estimativa de tempo seja **sempre** derivada da linha de base vigente e nunca possa
ser passada como parâmetro.

**`legal_documents` + `legal_acceptances`** — texto de versão é imutável, e o aceite guarda o **sha256 copiado do
documento pelo gatilho**, nunca informado pelo cliente. `acceptance_stamp()` **recusa** aceite de documento que não
esteja aprovado e vigente — o que, hoje, é o caso de todos os onze.

**`charge_installments`** — a soma das parcelas é conferida por `CONSTRAINT TRIGGER ... DEFERRABLE INITIALLY
DEFERRED`, no COMMIT. Tinha de ser postergada: a conferência precisa acontecer depois de todas as parcelas entrarem.

## Migrações da v0.16.0

| Migração | O que faz |
|---|---|
| `0016_v0160_impact_network.sql` | **23 tabelas** da rede: `relationships` (a aresta única, 22 tipos, 5 níveis de visibilidade), `proposals` + `proposal_events` + `proposal_attachments` + `proposal_status_graph`, `marketplace_listings`, `message_attachments`, `impact_updates`, `network_status_graph`, `personas` + `org_personas`, `taxonomies` + `taxonomy_terms`, `public_profiles` + `handle_history` + `reserved_handles`, `professional_experiences`, `enforcement_actions`, `territory_needs`, `investment_intents`, `recommendations`, `readiness_snapshots`, `domain_events`. Acrescenta `relationships.origin_proposal_id`; troca `conversations UNIQUE(org_a, org_b)` por `ux_conv_pair_context`; estende `app_related()` com lista **explícita** de tipos; cria `app_project_supporter()`, `app_record_event()`, `app_impact_metrics()`, `project_team()`, `notify_team()`, `notify_org_members()`, `rel_is_party()`, `proposal_is_party()`; 10 gatilhos de guarda; `REVOKE INSERT ON domain_events`; RLS, políticas, GRANT por coluna e os índices de chave estrangeira na própria migração |
| `0017_v0160_billing_v2.sql` | **3 tabelas** da cobrança versionada: `plan_price_versions` (com `ux_price_current` parcial único, CHECKs `intro_pair`, `intro_is_cheaper`, `effective_order`), `subscription_prices`, `price_change_notices`; funções `price_current()`; gatilhos `price_version_immutable()`, `price_notice_guard()` (30 dias), `price_apply_guard()`, `price_notice_ack_only()` |

### As quatro estruturas que merecem leitura

**`relationships`** — uma tabela de aresta para os 22 tipos. `source_org_id`, `target_org_id`, `kind`,
`subject_type`/`subject_id` (o contexto), `visibility`, `status`, `origin_proposal_id`. Índices nas duas pontas, que
é o que faz a travessia de profundidade 2 custar 14–15 ms. Ver `RELATIONSHIP_MODEL.md`.

**`domain_events`** — append-only, com `REVOKE INSERT` para o papel da aplicação. A gravação passa **só** por
`app_record_event()`, que é SECURITY DEFINER porque um fato de rede envolve **duas** organizações e a política de
inquilino recusaria a gravação da contraparte. Autoria derivada de `app_uid()`/`app_org()`, não do parâmetro.

**`impact_updates`** — `metrics`, `milestones` e `evidence_count` em `guard_columns`: **nem o motor** escreve. O
gatilho `impact_update_guard()` as preenche a partir de `app_impact_metrics()`, que lê `indicator_values`,
`milestones` e `evidences`. CHECK `reviewed_by <> created_by`.

**`plan_price_versions`** — vigência por `(plano, intervalo, moeda)` com índice único **parcial**, de modo que duas
versões vigentes ao mesmo tempo são impossíveis. `price_version_immutable()` recusa alterar valor, moeda ou imposto
de versão existente: mudar preço **cria versão**. Aqui `guard_columns` seria inútil, porque isenta `app_priv()`, que
é o único escritor da tabela.

## Migrações da v0.15.0

| Migração | O que faz |
|---|---|
| `0013_v0150_core_product.sql` | 15 tabelas do núcleo (`ideas`, `project_transitions`, `project_status_graph`, `project_snapshots`, `project_risks`, `diagnosis_versions`, `diagnosis_actions`, `document_templates`, `document_template_fields`, `document_assemblies`, `match_feedback`, `signature_providers`, `signature_policies`, `encryption_keys`, `encryption_rotations`); consolida os ODS **removendo** `sdg_goals`; acrescenta 20 tipos de entrada à trilha; `indicator_catalog.result_kind`; 5 gatilhos de guarda; RLS e GRANT por coluna |
| `0014_v0150_platform_templates.sql` | 3 modelos de documento da plataforma, publicados, com a fonte declarada (49 campos); exige motivo para reabrir projeto arquivado; `document_identity_guard()`; `project_funding_many()` em lote |
| `0015_v0150_fk_indexes.sql` | 92 índices para chave estrangeira de caminho de acesso (regra explicada no comentário da migração) |

---

## Camada institucional (migração `0006_v0100_institutional.sql`)

Esquema completo anterior: `docs/DATABASE.md`. Esta migração é **cumulativa** (0001–0005 intactas). Papéis: `impacto_owner` (dono) e `impacto_app` (aplicação, sujeito a RLS e gatilhos de guarda).

## Tabelas novas
| Tabela | Finalidade | Garantias no banco |
|---|---|---|
| `inst_catalog_items` | catálogos governados: `legal_nature`, `qualification_type`, `institutional_profile`, `institutional_status`, `funding_modality`, `badge` | versão; `status` draft/review/approved/published/archived; **CHECK de quatro olhos** (aprovador ≠ criador); 1 publicado por (catálogo, código); fonte, confiança, `needs_professional_validation` |
| `eligibility_rules` | regras de elegibilidade versionadas (`scope_type` global/modality/call/funder) | `requirement` jsonb de tipos fechados (validado na API/motor); `source_citation` obrigatória; `source_consulted_on`; fluxo editorial como acima |
| `organization_qualifications` | qualificação/certificação como relacionamento (não array): tipo, autoridade, número/protocolo, emissão, validade, documento, URL de consulta | `verification_status` não pode ser promovido pelo papel da aplicação (gatilho `qualification_guard`); único por (org, tipo, certificado) |
| `organization_qualification_events` | histórico de cada transição (quem, quando, de→para, nota) | leitura por RLS; escrita só em contexto privilegiado |
| `proponent_needs` | necessidades declaradas (financiamento, parceria, replicação, técnica, institucional, expansão territorial) | RLS por organização |
| `eligibility_evaluations` | resultado de cada avaliação (estado, JSON explicativo, versão do motor, regras usadas) | **append-only** para a aplicação (gatilho `trg_append_only`) |

## Colunas novas
- `organizations`: `legal_nature_code`, `institutional_profile`, `institutional_status` (padrão `registered`; sem CNPJ ⇒ `in_structuring`), nota/autor/data da situação, `mission`, `vision`, `geographic_scope`, `operating_regions`. Gatilho `org_inst_guard`: **a aplicação não altera a situação institucional** — só a administração.
- `documents`: `validation_status` (pending/validated/rejected) + validador/data/nota, `issued_on`, `origin_source` (CHECK de consistência).
- `calls`: `funding_modality`, `accepted_legal_natures`, `min_maturity` (0–6). `funder_profiles`: naturezas aceitas, qualificações exigidas, maturidade mínima, modalidades.
- `solutions`: `ownership_type`, `rights_holder`, `confidentiality`, `authorization_publish`, `authorization_contact`, `ip_declared_at/by`, `compatible_modalities`, `legal_requirements`.

## Segurança de linha (RLS)
Todas as tabelas novas têm RLS (teste `test_every_table_has_rls`). Política de `solutions` alterada: **soluções `confidential` nunca são descobertas por terceiros** (só a própria organização e a administração); `app_solution_visible()` segue a mesma regra para tabelas filhas.

## Migração e reversão
Só para frente, com checksum. Reversão = restaurar backup (`scripts/restore_test.sh`); não há migração `down`. Reset de desenvolvimento: `scripts/dev_reset_db.sh`.

## v0.10.1 — migração 0007
| Tabela | Finalidade | Proteções |
|---|---|---|
| `organization_agreements` | instrumentos (contrato de gestão, termos, acordos) | `agreement_guard`: org não promove verificação; RLS |
| `formalization_steps` | etapas manuais declaradas (PK org+etapa) | RLS |
| `mentoring_requests` | pedidos de mentoria | `mentoring_guard`: org só cancela; RLS |
Coluna nova: `organization_qualifications.areas text[]`. Banco de desenvolvimento: 114 tabelas, 237 políticas RLS.


---
## v0.11.0 — migração `0008_v0110_monetization.sql` (cumulativa; 0001–0007 intactas)
| Tabela / alteração | Finalidade | Garantias |
|---|---|---|
| `plans.tier` | free/plus/premium/gov | CHECK |
| `plan_prices` | preço mensal/anual por plano (NULL = não definido) | RLS: leitura pública, escrita só privilegiado |
| `subscriptions` + `interval, trial_end, canceled_at, last_event_at, amount_cents, discount, payment_issue, origin` | ciclo de vida e valor calculado no servidor | índice único parcial: 1 assinatura vigente por organização |
| `org_trials` | trial por organização (PK = no máximo um) | RLS + `billing_guard` (só servidor/admin) |
| `trial_claims` | anti-abuso: HMAC do e-mail normalizado/CNPJ | RLS só privilegiado; sem dado em claro |
| `billing_notices` | avisos sem repetição | PK (org, tipo, ref) |
| `vouchers`/`voucher_redemptions` + desconto, duração, organização, status | descontos reais, `pending_discount` | RLS existente |
| `entitlement_grants` + origem ampliada, motivo, `agreement_id`, revogação | licenças com origem, revogáveis | `billing_guard` |
| `agreements`, `agreement_members` | convênios/GOV | RLS só privilegiado (código nunca visível); quatro olhos (CHECK) |
Banco de desenvolvimento: **120 tabelas, 247 políticas RLS**.

## v0.12.0 — migração 0009 (Central de Conhecimento)
32 tabelas novas (120 → 152 no banco de desenvolvimento), todas com RLS. Detalhe por grupo, gatilhos e funções: `KNOWLEDGE_DATA_MODEL.md`. Destaques: quatro olhos por CHECK, versões imutáveis, gabarito de quiz inacessível à aplicação, `support_guard`, duplo opt-in do boletim com token só em hash.

---

# Camada de integração (migração `0011_v0130_integration_hub.sql`, v0.13.0)
Cumulativa (0001–0010 intactas). **165 tabelas no total**, RLS em todas exceto `schema_migrations`.

| Tabela | Finalidade | Garantias no banco |
|---|---|---|
| `integration_providers` | catálogo de provedores e capacidades | `maturity` enum `scaffolded→contract_tested→sandbox_validated→homologated→production_active`; gatilho impede promoção pelo papel da aplicação sem privilégio; GRANT UPDATE só em `(maturity, updated_at)` |
| `integration_connections` | organização × provedor × **ambiente** | UNIQUE `(org_id, provider_id, environment)`; `status` draft/active/paused/revoked; `health_state`, `failure_streak`, `circuit_open_until` |
| `integration_credentials` | segredo da conexão | `secret_cipher bytea` cifrado (Fernet) **ou** `secret_ref`, CHECK de um-ou-outro; **sem SELECT** na coluna para `impacto_app`; leitura só por `integration_secret(uuid)` SECURITY DEFINER; `hint` para exibição |
| `integration_mappings` | campo externo → canônico | transformação de conjunto fechado; obrigatoriedade; único por (conexão, entidade, campo) |
| `external_entity_links` | ID interno ↔ ID externo | UNIQUE `(conexão, entidade, external_id)` **e** `(conexão, entidade, internal_id)`; `sync_status` inclui `conflict` e `deleted_externally` com `conflict_detail` — **nada é sobrescrito em silêncio** |
| `integration_jobs` | execução idempotente | UNIQUE `(org_id, idempotency_key)`; `error_kind` temporary/permanent; tentativas e correlação |
| `integration_events` | caixa de saída de eventos de domínio | INSERT permitido na transação da organização (`org_id = app_org() OR app_priv()`) — o evento cai junto com o fato |
| `integration_subscriptions` | webhook de saída do parceiro | CHECK HTTPS; `secret_cipher` cifrado e não legível; GRANT UPDATE só em `(name, url, event_types, status, headers)` |
| `integration_deliveries` | entrega de evento | UNIQUE `(assinatura, evento)`; INSERT pela organização, UPDATE/DELETE só privilegiado (ninguém “declara entregue”) |
| `integration_inbound` | webhook recebido | UNIQUE `(conexão, external_event_id)` — deduplicação no banco, não na aplicação |
| `integration_imports` / `integration_import_rows` | importação de arquivo | UNIQUE `(org_id, entidade, sha256)`; erro por linha; aprovação humana registrada |
| `integration_exports` | exportação | gera documento no cofre; sem acesso direto ao banco |

---

# Camada de confiança (migração `0012_v0140_trust_layer.sql`, v0.14.0)
Cumulativa (0001–0011 intactas). **191 tabelas no total**, RLS em todas exceto `schema_migrations`.

## Identidade e credencial
| Tabela | Finalidade | Garantias no banco |
|---|---|---|
| `identity_verifications` | nível de identidade por **pessoa** (não por organização) | UNIQUE `(user_id, level)`; nasce `pending` por gatilho; `status`/`decided_by`/`decided_at`/`level`/`method` são **colunas guardadas** (nem a própria pessoa muda); função `identity_level(uuid)` SECURITY DEFINER devolve o maior nível verificado e não expirado |
| `identity_documents` | referência ao documento no cofre + resultado da conferência | UNIQUE `(verification_id, document_id)`; nasce `submitted`; `status`/`reviewed_by` guardados; **nenhum número ou imagem é armazenado** |
| `professional_councils` | catálogo de 20 conselhos federais | `number_pattern` e `official_site` **nulos de propósito** (a plataforma não inventa formato nem URL) |
| `credential_verifications` | histórico da conferência da credencial | **append-only** por gatilho |
| `professional_credentials` (+3 colunas) | `council_code` (FK ao catálogo), `revoked_at`, `revocation_reason` | gatilho `credential_format_guard` exige UF quando o conselho exige e aplica o padrão **quando** houver |

## Custódia, verificação pública e carimbo
| Tabela | Finalidade | Garantias no banco |
|---|---|---|
| `trust_events` | cadeia de custódia **por objeto** (documento, rascunho, acordo, credencial, identidade) | `seq`/`prev_hash`/`event_hash` calculados por gatilho SECURITY DEFINER (`chain_trust`) usando `chain_heads`; **append-only**; sem GRANT de UPDATE; `trust_verify(tipo, id)` aponta o `seq` da quebra |
| `verifiable_records` | registro **público** curado — a única tabela que a verificação pública lê | `code` UNIQUE com CHECK de formato `IMP-XXXX-XXXX-XXXX`; CHECK exigindo data e motivo quando revogado; `code`/`subject_id`/`content_sha256`/`subject_version`/`issued_at`/`access_count` são **colunas guardadas** |
| `trust_timestamps` | carimbo interno (selo HMAC) ou token de ACT | CHECK garantindo selo para `internal` e token para `rfc3161`; **append-only**; a organização grava o carimbo do próprio registro (não consegue forjar selo válido) |

## Assinatura e acordos
| Tabela | Finalidade | Garantias no banco |
|---|---|---|
| `signature_challenges` | segunda camada: código de uso único | guarda `subject_sha256` (o código morre se o conteúdo mudar); só o SHA-256 do código é persistido; `attempts` limita a força bruta |
| `signatures` (+3 colunas) | `challenge_id`, `identity_level`, `agreement_party_id` | gravadas **no INSERT** porque a tabela é append-only desde a 0002 |
| `signature_revocations` | revogação como **fato novo** | UNIQUE por assinatura; **append-only** |
| `signed_agreements` | acordo multiassinatura (nome distinto de `agreements`, que é convênio de licenciamento da 0008) | `content_sha256`/`document_id`/`org_id` **guardados** (hash congelado ao publicar) |
| `signed_agreement_parties` | partes, papel e assinatura | UNIQUE `(acordo, organização, papel)`; CHECK impedindo assinado **e** recusado; `signature_id`/`signed_at` **guardados** (uma parte não marca a outra); políticas usam funções SECURITY DEFINER para não recursar |
| `signed_agreement_milestones` | acompanhamento longitudinal | visível a qualquer parte do acordo |

## Taxonomia, idioma, cotas, honorários e diagnóstico
| Tabela | Finalidade | Garantias no banco |
|---|---|---|
| `sdg_goals` / `esg_pillars` / `social_determinants` | catálogos (17 / 3 / 11) | semeados na migração; `social_determinants.source_note` carrega o aviso de revisão pendente |
| `impact_tags` | marcador de objeto × taxonomia | UNIQUE por `(tipo, objeto, taxonomia, código)`; gatilho `impact_tag_guard` **recusa código inexistente** |
| `locales` / `translations` | idiomas e catálogo | único idioma padrão (índice parcial); `users.locale` ganhou FK; `users.theme` e `users.prefs_set_at` novos |
| `funding_quotas` / `quota_pledges` | cotas e reservas | gatilho `quota_capacity_guard` **SECURITY DEFINER** com trava na cota, checagem de NULL e soma de todas as reservas; reserva nasce `pledged` e `status`/`payment_ref` são guardados |
| `campaigns` | campanha pública | `slug` UNIQUE global; uma campanha por projeto |
| `fee_tables` / `fee_items` | honorários por conselho | CHECK: publicar exige `source_name`, `source_url` (https) e `source_date`; nasce `draft` por gatilho; **seed vazio** |
| `professional_services` | catálogo de atividades do profissional | preço é da profissional; `negotiable` explícito |
| `diagnosis_stages` / `diagnosis_progress` | roteiro guiado (8 etapas) e progresso | UNIQUE `(diagnóstico, etapa)`; etapas semeadas com aviso de hipótese editorial |
| `organizations` (+6 colunas) | `lat`, `lng`, `geo_precision`, `geo_public`, `geo_consent_at` | CHECK de par lat/lng e CHECK `organizations_geo_consent`: **público exige consentimento com data** |
| `integration_exports` (CHECK alterado) | 8 formatos de exportação | antes: csv e json |

