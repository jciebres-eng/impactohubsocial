# Relatório de integridade do banco — v0.18.0

Todo número aqui vem de consulta ao catálogo do PostgreSQL, não de contagem à mão. O coletor é
`scripts/db_integrity_report.py`; a saída bruta está em `docs/evidence/db_integrity_v0.18.0.txt`
(as anteriores ficaram em `docs/evidence/db_integrity_v0.16.0.txt` e `_v0.15.0.txt`).

Banco medido: criado **do zero** pelas 32 migrações (`scripts/dev_reset_db.sh`), PostgreSQL 16.15.

## 0. Os números da v0.18.0, e o que o coletor apontou

| Medida | v0.17.0 | **v0.18.0** |
|---|---|---|
| Tabelas | 253 | **285** |
| Tabelas sem RLS | `schema_migrations` | **`schema_migrations`** (única) |
| Políticas | 521 | **593** |
| Gatilhos | 194 | **231** |
| Funções | 277 (75 `SECURITY DEFINER`) | **308**, das quais **78** `SECURITY DEFINER` |
| `SECURITY DEFINER` sem `search_path` fixo | nenhuma | **nenhuma** |
| Chaves estrangeiras | 680 | **756** |
| FK **quente** sem índice | nenhuma | **nenhuma** (uma apareceu e foi corrigida — abaixo) |
| CHECKs | 1.216 | **1.378** |
| Índices | 714 | **797** |
| Tabelas sem chave primária | nenhuma | **nenhuma** |
| Tabelas append-only | 26 | **37** (entram `claim_checks`, `claim_reviews`, `equity_assessments`, `reputation_snapshots`, `reputation_disputes`, `reputation_dispute_resolutions`, `seal_awards`, `seal_revocations`, `seal_evaluations`, `responsibility_assignments`, `responsibility_decisions`) |
| Migrações aplicadas | 24 | **32** |

**O coletor achou um defeito real nesta rodada:** `materiality_assessments.project_id` era FK **quente** sem índice
— apagar um projeto fazia o banco varrer a tabela inteira para resolver o `ON DELETE`, e a listagem de
materialidade por projeto fazia o mesmo. Corrigido na migração **0032**, respeitando a regra da 0015: índice só em
coluna de inquilino ou de pai percorrido, nunca em toda FK — por isso **384** FKs continuam sem índice, de propósito
(as de `users`: `declared_by`, `reviewed_by`, `opened_by`, `resolved_by`).

As três funções `SECURITY DEFINER` novas e por que cada uma precisa ser:

| Função | Por que `SECURITY DEFINER` | O que ela **não** permite |
|---|---|---|
| `app_record_reputation()` | a aplicação não tem `INSERT` em `reputation_snapshots`: valor de reputação não pode ser escrito por rota | recusa valor sem observação que o sustente |
| `app_award_seal()` | reavalia os critérios no banco antes de inserir a concessão | não concede quando um critério falha, nem por contexto privilegiado |
| `app_claim_invited()` | quebra a recursão entre a política de `claims` e a de `claim_review_requests`, que o PostgreSQL recusa inteira | responde só "esta organização foi convidada?"; não devolve conteúdo nem responde sobre outra organização |

## 0.1 Os números da v0.17.0, e o que o coletor apontou então

| Medida | v0.16.0 | **v0.17.0** |
|---|---|---|
| Tabelas | 231 | **253** |
| Tabelas sem RLS | `schema_migrations` | **`schema_migrations`** (única; `chain_heads` tem RLS e política própria) |
| Políticas | — | **521** |
| Gatilhos | — | **194** |
| Funções | — | **277**, das quais **75** `SECURITY DEFINER` |
| `SECURITY DEFINER` sem `search_path` fixo | nenhuma | **nenhuma** |
| Chaves estrangeiras | — | **680** |
| FK **quente** sem índice | nenhuma | **nenhuma** |
| CHECKs | — | **1.216** |
| Índices | — | **714** |
| Tabelas sem chave primária | nenhuma | **nenhuma** |
| Tabelas append-only | — | **26** (entram `value_events`, `billable_events`, `charge_events`, `monetization_legal_cards`) |
| Migrações aplicadas | 17 | **24** |

**O coletor achou um defeito real nesta rodada:** `legal_acceptances.org_id` era uma FK de caminho de acesso **sem
índice** — a administração lista aceite por organização, e sem o índice a consulta varreria a tabela inteira. O
índice foi criado na 0024, respeitando a regra da 0015 (índice só em coluna de inquilino ou de pai percorrido, não
em toda FK — por isso **345** FKs continuam sem índice, de propósito).

## 1. Números

| Medida | v0.15.0 | **v0.16.0** |
|---|---|---|
| Tabelas | 205 | **231** |
| Tabelas sem RLS habilitada | 1 | **1** — `schema_migrations` |
| Políticas de RLS | 408 / 203 tabelas | **466**, cobrindo **229** tabelas |
| Gatilhos (não internos) | 118 | **161** |
| Funções | 224 | **247** |
| das quais `SECURITY DEFINER` | 53 | **63** |
| `SECURITY DEFINER` sem `search_path` fixo | 0 | **0** |
| Chaves estrangeiras | 529 | **627** |
| FK de caminho de acesso sem índice próprio | 0 | **0** |
| Restrições `CHECK` | 922 | **1.082** |
| Restrições `UNIQUE`/`PRIMARY KEY` | 288 | **315** |
| Índices | 552 | **643** |
| Tabelas sem chave primária | 0 | **0** |
| Tabelas append-only | 17 | **22** |
| Tabelas com coluna guardada | 20 | **26** |
| Migrações aplicadas | 15 | **17** |
| Arestas de máquina de estados como dado | 58 | **103** (projeto 58 · proposta 19 · rede 26) |

### Por que `schema_migrations` não tem RLS

É a tabela do controlador de migrações, escrita pelo papel **dono** do banco antes de qualquer contexto de
organização existir. Habilitar RLS nela só criaria um caminho de falha na subida. O teste de arquitetura
(`test_every_table_has_rls`) tem essa exceção **nomeada** — e `chain_heads`, que é interna ao encadeamento de hash.

## 2. Isolamento por organização

Toda política compara `org_id = app_org()` (ou traverse equivalente por função `SECURITY DEFINER`). A verificação
não é só estrutural:

| Verificação | Onde |
|---|---|
| `SELECT` sem filtro devolve só as linhas da própria organização | `test_security_tenancy.test_unfiltered_select_returns_only_own_rows` |
| `UPDATE` sem filtro não toca linha de outra organização | `test_unfiltered_update_cannot_touch_other_tenant` |
| `INSERT` para outra organização é recusado | `test_insert_for_other_tenant_denied` |
| Contexto anônimo não vê nada | `test_anonymous_context_sees_nothing` |
| O papel da aplicação não tem `BYPASSRLS` | `test_app_role_has_no_bypass` |
| As tabelas novas da v0.15.0 isolam em SQL direto | `test_v0150_security.test_rls_blocks_the_new_tables_directly_in_sql` |
| Nenhuma rota de escrita da rede aceita identificador **existente de outra organização** (o caso em que um `WHERE org_id` esquecido vazaria de verdade) | `test_v0160_invariants.CrossTenantNetworkMatrix` |
| Os gatilhos de situação inicial e de guarda da rede recusam **em SQL direto no contexto da usuária** (papel `impacto_app`) | `test_v0160_network`, via `app_tx()` |
| Funções `SECURITY DEFINER` não entregam dado de outra organização | `test_security_definer_helpers_do_not_leak_other_tenant` |

### `org_id` anulável: 21 tabelas, todas por desenho

| Tabela | Por que `org_id` pode ser nulo |
|---|---|
| `audit_events` | ação de plataforma sem organização ativa (hoje: 0 linhas assim) |
| `sessions` | sessão criada antes de escolher a organização |
| `indicator_catalog` | **13 linhas** são o catálogo **da plataforma**, visível a todos |
| `signature_policies` | **3 linhas** são a política padrão da plataforma |
| `integration_events`, `trust_events`, `solution_events`, `solution_search_log` | evento de plataforma |
| `course_certificates`, `course_enrollments`, `lesson_progress` (via `kb_*`), `hub_event_registrations` | pessoa física pode estudar sem organização |
| `demo_requests`, `partnership_requests`, `trial_claims`, `support_tickets`, `kb_feedback`, `kb_checklist_progress`, `solution_people` | contato ou registro anterior ao cadastro da organização |
| `domain_events` *(v0.16.0)* | fato de plataforma sem organização ativa; o fato **de rede** sempre tem as duas organizações nomeadas |
| `professional_experiences` *(v0.16.0)* | a experiência pode citar organização que **não está** na plataforma — e aí não há `org_id` a apontar |
| `public_profiles` *(v0.16.0)* | perfil de pessoa física que ainda não criou organização |

Em todas, a política de RLS cobre o caso nulo explicitamente (`org_id IS NULL OR org_id = app_org() OR app_priv()`
ou equivalente), de modo que linha de plataforma é legível e linha de outra organização não.

## 3. Imutabilidade

### Append-only (22 tabelas)

`forbid_mutation()` recusa UPDATE e DELETE pelo papel da aplicação em:

`application_transitions` · `audit_events` · `credential_verifications` · `diagnosis_versions` ·
`eligibility_evaluations` · `ledger_entries` · `match_feedback` · `organization_qualification_events` ·
`payment_events` · `project_snapshots` · `project_transitions` · `signature_revocations` · `signatures` ·
`solution_intent_events` · `solution_versions` · `trust_events` · `trust_timestamps`

**Acrescentadas em v0.16.0:** `domain_events` (o fato aconteceu; apagá-lo é apagar a história da rede) ·
`proposal_events` (a trilha da negociação) · `readiness_snapshots` (a nota de ontem explica a decisão de ontem) ·
`handle_history` (quem foi `@nome` antes importa para quem confiou no endereço) · `price_change_notices` (o aviso
enviado é prova de que foi enviado — só o "ciente" pode ser escrito depois, por `price_notice_ack_only()`)

### Colunas guardadas (26 tabelas)

`guard_columns(...)` recusa que a organização escreva colunas que o servidor apura ou que a administração decide:
`calls` · `document_assemblies` · `document_templates` · `documents` · `fee_tables` · `ideas` ·
`identity_documents` · `identity_verifications` · `milestones` · `organizations` · `professional_credentials` ·
`quota_pledges` · `signature_providers` · `signed_agreement_parties` · `signed_agreements` ·
`solution_disputes` · `solution_evidence` · `solution_results` · `users` · `verifiable_records`

**Acrescentadas em v0.16.0:** `impact_updates` (as três colunas de número — `metrics`, `milestones`,
`evidence_count` — são colhidas por `app_impact_metrics()`, não digitadas) · `relationships` ·
`proposals` · `marketplace_listings` · `investment_intents` · `public_profiles`

**Lição desta rodada:** `guard_columns` isenta `app_priv()`. Nas tabelas em que **só** o contexto privilegiado
escreve — `plan_price_versions` é o caso — ela não guarda nada, e a trava precisa ser gatilho próprio
(`price_version_immutable()`). E nas tabelas em que a organização legitimamente muda a situação do próprio
registro, a guarda bloqueava o dono: a correção foi tirar as colunas de situação da guarda e passar a **derivá-las**
por gatilho (`published_at`, `submitted_at`, `reviewed_by`, `decided_at`, `version`…).

### Guardas que nem o contexto privilegiado atravessa

| Guarda | O que recusa | Por quê |
|---|---|---|
| `project_status_guard` | transição fora de `project_status_graph` | a máquina de estados não pode ser furada por rota nova, job ou script |
| `signature_provider_guard` | assinatura com provedor fora de `production` | impede estruturalmente a "assinatura ICP-Brasil simulada" |
| `document_identity_guard` | mudar `sha256`, `size_bytes`, `storage_key` ou `mime_type` de `documents` | a identidade do arquivo guardado não muda; nova versão é linha nova |
| `template_field_guard` | alterar campo de modelo publicado | documento gerado precisa continuar explicável |
| `quota_capacity_guard` | aporte acima da capacidade de cotas | `SECURITY DEFINER` para somar **todos** os aportes, com verificação explícita de nulo (ADR 103) |
| `proposal_status_guard` *(v0.16.0)* | transição fora de `proposal_status_graph` | mesmo princípio da máquina do projeto, agora na negociação |
| `network_initial_state` *(v0.16.0)* | situação inicial inventada em relação, anúncio ou relatório | a porta de entrada da máquina de estados também é máquina de estados |
| `listing_publish_guard` *(v0.16.0)* | anúncio ao ar com projeto não publicado | vitrine aberta para coisa privada é vazamento |
| `impact_update_guard` *(v0.16.0)* | relatório enviado sem os números colhidos pelo banco | impede "atendemos 400 pessoas" sem lastro |
| `enforcement_target_guard` *(v0.16.0)* | o alvo de uma medida escrever qualquer coluna além da contestação | a GRANT de coluna deixava o alvo anular a própria punição |
| `price_version_immutable` *(v0.16.0)* | alterar valor, moeda ou imposto de versão de preço existente | mudar preço cria versão; o histórico não se reescreve |
| `price_apply_guard` *(v0.16.0)* | aumento de preço sem aviso prévio de 30 dias reconhecido | "nunca mudar preço em silêncio", no banco |
| `counterpart_columns` *(v0.16.0)* | a contraparte escrever algo além de `status`/`ended_at`/`ended_reason` | aceitar uma relação não dá direito de reescrever a nota de quem convidou |
| `handle_guard` *(v0.16.0)* | tomar identificador reservado ou já usado, sem registrar o histórico | endereço público é identidade |

### Encadeamento por hash

`ledger_entries`, `audit_events` e a camada de confiança usam `chain_heads` + hash canônico, verificáveis por
`ledger_verify`, `audit_verify` e `trust_verify`. Adulterar exige o papel **dono** do banco — e aí a verificação
denuncia (`test_security_tenancy.test_ledger_tampering_is_detected`).

## 4. Índices: o achado desta versão

A medição com volume (`PERFORMANCE_REPORT.md`) revelou **92 colunas de chave estrangeira sem índice começando por
elas**, em `org_id`, `project_id`, `application_id`, `solution_id`, `call_id`, `diagnosis_id`, `template_id`,
`connection_id`, `course_id`, `agreement_id` e `milestone_id`.

Índice que tem a coluna no meio não serve nem para o filtro do inquilino (toda política de RLS compara
`org_id = app_org()`) nem para o `ON DELETE CASCADE` do pai: nos dois casos o banco varre a tabela inteira.

A migração `0015_v0150_fk_indexes.sql` criou os 92 índices. **Regra aplicada**: só as colunas de inquilino ou de pai
percorrido pela aplicação. Chave para `users` (`created_by`, `reviewed_by`, `approved_by`…) **não** entrou: a
aplicação não lista "tudo que a pessoa X criou", e índice que ninguém usa é custo de escrita sem retorno.

Resultado: de 460 para **552** índices, e `fk_without_index_hot` em **0**. A suíte completa (673 testes, que
escrevem muito) manteve o mesmo tempo: 268 s antes, 268 s depois — o custo de escrita é irrelevante nesta escala.

**Em v0.16.0** a mesma regra foi aplicada às 26 tabelas novas na própria migração 0016, e não como correção
posterior: 643 índices no total, `fk_without_index_hot` continua em **0**. As 327 FK sem índice próprio são,
todas, chaves para `users` (`created_by`, `decided_by`, `reviewed_by`…), que não são caminho de acesso — a
aplicação não lista "tudo que a pessoa X criou" (ADR-137).

## 5. Integridade referencial

- **627 chaves estrangeiras declaradas.** Não há referência "por convenção" entre tabelas do núcleo: toda ligação é
  FK, portanto não existe linha órfã possível.
- `ON DELETE` é explícito em cada FK: `CASCADE` onde o filho não tem sentido sem o pai (marco sem projeto),
  `SET NULL` onde o filho sobrevive (documento cujo projeto foi apagado), `RESTRICT` onde apagar o pai seria perder
  prova (modelo usado por montagem).
- **1.082 restrições `CHECK`** cobrem domínio de valor (situações, níveis, formatos), faixa (percentual 0–100,
  valores não negativos) e coerência entre colunas. Exemplos desta versão:
  `CHECK ((stage = 'promoted') = (promoted_project_id IS NOT NULL))` em `ideas`;
  `CHECK (approved_by IS NULL OR approved_by <> created_by)` em `document_assemblies`.
  Exemplos de v0.16.0: `CHECK (reviewed_by IS NULL OR reviewed_by <> created_by)` em `impact_updates` (quem revisa
  não é quem escreveu); `CHECK (appeal_decided_by IS NULL OR appeal_decided_by <> decided_by)` em
  `enforcement_actions` (quem julga a contestação não é quem aplicou); `CHECK ((intro_amount_cents IS NULL) =
  (intro_periods IS NULL))` e `CHECK (intro_amount_cents IS NULL OR intro_amount_cents < amount_cents)` em
  `plan_price_versions` (preço de entrada mais caro que o regular é padrão obscuro, e o banco recusa);
  `CHECK (char_length(reason) >= 10)` em `enforcement_actions` (medida sem motivo é arbítrio).

## 6. Caminho de atualização

`backend/tests/test_v0150_upgrade.py` prepara um banco na **v0.12.1** (migrações 0001–0010), insere organização,
usuário, projeto publicado, documento e entradas na trilha, e então aplica 0011 → 0012 → 0013 → 0015 → **0016 →
0017**. Confere:

| Verificação | Resultado |
|---|---|
| Dado anterior sobreviveu sem alteração | ✔ |
| Trilha encadeada intacta, `ledger_verify` válido | ✔ |
| Transições que o produto já fazia continuam no grafo | ✔ |
| Consolidação dos ODS não deixou referência quebrada (`sdg_goals` removida, `ods_goals` com 17 linhas) | ✔ |
| As 15 estruturas da v0.15.0 **e as 26 da v0.16.0** chegaram com RLS e política | ✔ |
| Modelos da plataforma e provedores de assinatura semeados | ✔ |
| O papel da aplicação usa as tabelas novas; tabelas de chave invisíveis | ✔ |
| **Esquema atualizado idêntico ao criado do zero** — colunas, índices, políticas e gatilhos | ✔ |

A última linha é a que importa mais: atualizar e criar do zero levam ao **mesmo** esquema. Divergência ali seria
dívida que só aparece meses depois, em uma instalação específica.

## 7. Consolidação de duplicata (defeito nosso, corrigido)

A v0.14.0 criou `sdg_goals` enquanto `ods_goals` já existia desde a migração 0001 e era referenciada por
`indicator_catalog.ods` e `ods_targets.ods`. Duas fontes de verdade para os Objetivos de Desenvolvimento
Sustentável.

A migração 0013 acrescentou `code`, `name_en`, `color_hex` e `active` a `ods_goals`, copiou o que faltava e
**removeu** `sdg_goals`. Três referências no código foram corrigidas, e `/v1/taxonomy` foi renomeada para
`/v1/impact-taxonomy` porque já existia `/v1/meta/taxonomy` com outro significado.

Isto está registrado em `PRE_DESIGN_AUDIT.md` como erro introduzido por nós, e o teste de atualização confere que a
remoção não deixou referência pendurada.

## 8. Privilégios do papel da aplicação

| Medida | Valor | Observação |
|---|---|---|
| Tabelas com `DELETE` para `impacto_app` | 194 | as 37 restantes são append-only ou de administração |
| Concessões por coluna para `impacto_app` | 8.080 | é assim que `integration_credentials.secret_cipher` fica ilegível e que o nível jurídico de um provedor de assinatura não pode ser escrito pela aplicação |

O papel da aplicação **não** tem `BYPASSRLS`, não é dono de nenhuma tabela e não pode criar nem alterar estrutura.

## 9. Conclusão

| Pergunta | Resposta |
|---|---|
| Alguma tabela de dado de organização está sem RLS? | **Não.** |
| Alguma `SECURITY DEFINER` está sem `search_path` fixo? | **Não.** |
| Alguma tabela está sem chave primária? | **Não.** |
| Alguma FK de caminho de acesso está sem índice? | **Não** — nem nas 26 tabelas da v0.16.0, cujos índices vieram na própria migração. |
| Existe caminho pela aplicação para reescrever histórico? | **Não** — 22 tabelas append-only, 15 guardas que o contexto privilegiado não atravessa, encadeamento por hash verificável. |
| Atualizar de uma versão anterior produz o mesmo esquema que criar do zero? | **Sim**, verificado por teste. |
