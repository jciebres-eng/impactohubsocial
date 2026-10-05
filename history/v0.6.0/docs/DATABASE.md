# Dados

Rascunho SQL: `database/draft/schema_v0.1.sql` (**não executado nem testado**; RED até rodar em banco descartável com testes).

## Convenções
UUID v7/ULID; `timestamptz`; moeda em centavos (`bigint`) + código ISO; `tenant_id` obrigatório; soft-delete só onde a lei exigir retenção; tabelas imutáveis (append-only) para critérios, regras, decisões, evidências, auditoria, resgates de voucher.

## Grupos de tabelas
- **Identidade/tenant:** tenant, app_user, membership, organization (tipo: funder|osc|provider).
- **Billing:** plan, plan_version, plan_entitlement, subscription, voucher_batch, voucher, voucher_redemption, entitlement_grant.
- **Programas:** program, call, criteria_version, application, project, need, tranche, budget_line.
- **Match/fiscal:** match_run, match_factor, rule_set, fiscal_rule.
- **Evidência/ledger:** document, verification, evidence, milestone, commitment, audit_event (hash encadeado).
- **Prestadores:** provider_profile, provider_credential, service_request, service_proposal, service_engagement, scope_grant.
- **LGPD:** consent_record, data_subject_request, retention_policy.

## Restrições-chave
- Soma de `commitment_allocation` ≤ orçamento aprovado (trigger/constraint).
- `voucher_redemption` única por (voucher, organização) quando `single_use_per_org`.
- `audit_event.prev_hash` encadeado; UPDATE/DELETE revogados.
- `provider_profile` **não possui** coluna de plano nem de impulsionamento.

## Índices e performance
Índices por `(tenant_id, status, created_at)`; full-text PostgreSQL para busca; paginação por cursor; medir antes de cache.

## Retenção
Definida por finalidade em `LGPD.md`; cópias de backup seguem janela técnica documentada.
