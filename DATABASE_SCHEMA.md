# DATABASE_SCHEMA — camada institucional (migração `0006_v0100_institutional.sql`)

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
