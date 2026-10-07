# Relatório de integridade do banco — v0.15.0

Todo número aqui vem de consulta ao catálogo do PostgreSQL, não de contagem à mão. O coletor é
`scripts/db_integrity_report.py`; a saída bruta está em `docs/evidence/db_integrity_v0.15.0.txt`.

Banco medido: criado **do zero** pelas 15 migrações (`scripts/dev_reset_db.sh`), PostgreSQL 16.15.

## 1. Números

| Medida | Valor |
|---|---|
| Tabelas | **205** |
| Tabelas sem RLS habilitada | **1** — `schema_migrations` |
| Políticas de RLS | **408**, cobrindo **203** tabelas |
| Gatilhos (não internos) | **118** |
| Funções | **224**, das quais **53** `SECURITY DEFINER` |
| `SECURITY DEFINER` sem `search_path` fixo | **0** |
| Chaves estrangeiras | **529** |
| FK de caminho de acesso sem índice próprio | **0** (eram 92 antes da migração 0015) |
| Restrições `CHECK` | **922** |
| Restrições `UNIQUE`/`PRIMARY KEY` | **288** |
| Índices | **552** |
| Tabelas sem chave primária | **0** |
| Migrações aplicadas | **15** |

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
| Funções `SECURITY DEFINER` não entregam dado de outra organização | `test_security_definer_helpers_do_not_leak_other_tenant` |

### `org_id` anulável: 18 tabelas, todas por desenho

| Tabela | Por que `org_id` pode ser nulo |
|---|---|
| `audit_events` | ação de plataforma sem organização ativa (hoje: 0 linhas assim) |
| `sessions` | sessão criada antes de escolher a organização |
| `indicator_catalog` | **13 linhas** são o catálogo **da plataforma**, visível a todos |
| `signature_policies` | **3 linhas** são a política padrão da plataforma |
| `integration_events`, `trust_events`, `solution_events`, `solution_search_log` | evento de plataforma |
| `course_certificates`, `course_enrollments`, `lesson_progress` (via `kb_*`), `hub_event_registrations` | pessoa física pode estudar sem organização |
| `demo_requests`, `partnership_requests`, `trial_claims`, `support_tickets`, `kb_feedback`, `kb_checklist_progress`, `solution_people` | contato ou registro anterior ao cadastro da organização |

Em todas, a política de RLS cobre o caso nulo explicitamente (`org_id IS NULL OR org_id = app_org() OR app_priv()`
ou equivalente), de modo que linha de plataforma é legível e linha de outra organização não.

## 3. Imutabilidade

### Append-only (17 tabelas)

`forbid_mutation()` recusa UPDATE e DELETE pelo papel da aplicação em:

`application_transitions` · `audit_events` · `credential_verifications` · `diagnosis_versions` ·
`eligibility_evaluations` · `ledger_entries` · `match_feedback` · `organization_qualification_events` ·
`payment_events` · `project_snapshots` · `project_transitions` · `signature_revocations` · `signatures` ·
`solution_intent_events` · `solution_versions` · `trust_events` · `trust_timestamps`

### Colunas guardadas (20 tabelas)

`guard_columns(...)` recusa que a organização escreva colunas que o servidor apura ou que a administração decide:
`calls` · `document_assemblies` · `document_templates` · `documents` · `fee_tables` · `ideas` ·
`identity_documents` · `identity_verifications` · `milestones` · `organizations` · `professional_credentials` ·
`quota_pledges` · `signature_providers` · `signed_agreement_parties` · `signed_agreements` ·
`solution_disputes` · `solution_evidence` · `solution_results` · `users` · `verifiable_records`

### Guardas que nem o contexto privilegiado atravessa

| Guarda | O que recusa | Por quê |
|---|---|---|
| `project_status_guard` | transição fora de `project_status_graph` | a máquina de estados não pode ser furada por rota nova, job ou script |
| `signature_provider_guard` | assinatura com provedor fora de `production` | impede estruturalmente a "assinatura ICP-Brasil simulada" |
| `document_identity_guard` | mudar `sha256`, `size_bytes`, `storage_key` ou `mime_type` de `documents` | a identidade do arquivo guardado não muda; nova versão é linha nova |
| `template_field_guard` | alterar campo de modelo publicado | documento gerado precisa continuar explicável |
| `quota_capacity_guard` | aporte acima da capacidade de cotas | `SECURITY DEFINER` para somar **todos** os aportes, com verificação explícita de nulo (ADR 103) |

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

## 5. Integridade referencial

- **529 chaves estrangeiras declaradas.** Não há referência "por convenção" entre tabelas do núcleo: toda ligação é
  FK, portanto não existe linha órfã possível.
- `ON DELETE` é explícito em cada FK: `CASCADE` onde o filho não tem sentido sem o pai (marco sem projeto),
  `SET NULL` onde o filho sobrevive (documento cujo projeto foi apagado), `RESTRICT` onde apagar o pai seria perder
  prova (modelo usado por montagem).
- **922 restrições `CHECK`** cobrem domínio de valor (situações, níveis, formatos), faixa (percentual 0–100,
  valores não negativos) e coerência entre colunas. Exemplos desta versão:
  `CHECK ((stage = 'promoted') = (promoted_project_id IS NOT NULL))` em `ideas`;
  `CHECK (approved_by IS NULL OR approved_by <> created_by)` em `document_assemblies`.

## 6. Caminho de atualização

`backend/tests/test_v0150_upgrade.py` prepara um banco na **v0.12.1** (migrações 0001–0010), insere organização,
usuário, projeto publicado, documento e entradas na trilha, e então aplica 0011 → 0012 → 0013 → 0015. Confere:

| Verificação | Resultado |
|---|---|
| Dado anterior sobreviveu sem alteração | ✔ |
| Trilha encadeada intacta, `ledger_verify` válido | ✔ |
| Transições que o produto já fazia continuam no grafo | ✔ |
| Consolidação dos ODS não deixou referência quebrada (`sdg_goals` removida, `ods_goals` com 17 linhas) | ✔ |
| As 15 estruturas novas chegaram com RLS e política | ✔ |
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
| Tabelas com `DELETE` para `impacto_app` | 181 | as 24 restantes são append-only ou de administração |
| Concessões por coluna para `impacto_app` | 7.135 | é assim que `integration_credentials.secret_cipher` fica ilegível e que o nível jurídico de um provedor de assinatura não pode ser escrito pela aplicação |

O papel da aplicação **não** tem `BYPASSRLS`, não é dono de nenhuma tabela e não pode criar nem alterar estrutura.

## 9. Conclusão

| Pergunta | Resposta |
|---|---|
| Alguma tabela de dado de organização está sem RLS? | **Não.** |
| Alguma `SECURITY DEFINER` está sem `search_path` fixo? | **Não.** |
| Alguma tabela está sem chave primária? | **Não.** |
| Alguma FK de caminho de acesso está sem índice? | **Não** (depois da 0015). |
| Existe caminho pela aplicação para reescrever histórico? | **Não** — 17 tabelas append-only, 5 guardas que o contexto privilegiado não atravessa, encadeamento por hash verificável. |
| Atualizar de uma versão anterior produz o mesmo esquema que criar do zero? | **Sim**, verificado por teste. |
