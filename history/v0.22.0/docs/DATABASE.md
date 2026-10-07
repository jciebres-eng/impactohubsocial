# Banco de dados — PostgreSQL 16 (v0.9.0)

Fonte de verdade: `backend/migrations/*.sql`, aplicadas em ordem por `python -m impacto.db.migrate` (tabela `schema_migrations`
com checksum: uma migração já aplicada e alterada é recusada).

| Migração | Conteúdo |
|---|---|
| `0001_schema.sql` | 56 tabelas (identidade, organizações, editais, projetos, candidaturas, execução, documentos, IA, fiscal, compliance, cobrança, vouchers, auditoria, ledger, jobs) |
| `0002_security.sql` | funções de contexto, helpers `SECURITY DEFINER`, RLS em todas as tabelas, triggers de integridade, cadeias de hash, grants |
| `0003_match_support.sql` | funções de apoio ao match: `org_document_metadata`, `org_track_record`, `project_funding`, `user_display_name` |

Bootstrap de papéis: `infra/db/bootstrap.sql` (ou `infra/compose/db-init.sh`).

## Papéis
| Papel | Uso | Propriedades |
|---|---|---|
| `impacto_owner` | aplicar migrações (`DATABASE_MIGRATION_URL`) | dono das tabelas |
| `impacto_app` | aplicação em execução (`DATABASE_URL`) | `NOBYPASSRLS`, **não** é dono → RLS sempre se aplica |
Em staging/production o boot falha se `DATABASE_URL` usar o papel dono ou um superusuário (`config.validate`).

## Contexto por transação
`db/pool.py` abre cada transação com `set_config(..., true)` para `app.user_id`, `app.org_id`, `app.org_kind`,
`app.platform_admin`, `app.system`. As funções `app_uid()`, `app_org()`, `app_kind()`, `app_admin()`, `app_system()`,
`app_priv()` leem esses valores. Como `is_local = true`, o contexto morre com a transação (sem vazamento entre requisições do pool).

## Isolamento (RLS)
- Toda tabela tem `ENABLE ROW LEVEL SECURITY` e políticas explícitas por operação.
- Relações entre organizações (financiador ↔ OSC, revisor ↔ rascunho, governo ↔ dados agregados) passam por funções
  `SECURITY DEFINER` estreitas (`app_project_party`, `app_project_investor`, `app_osc_counterparty`, `app_review_access`,
  `app_document_access`, `gov_territory_stats`) — evitam recursão de políticas e expõem só o necessário.
- Testes: `backend/tests/test_security_tenancy.py` (24 testes) tenta leitura/escrita cruzada via API **e via SQL direto
  como `impacto_app`**.

## Integridade garantida no banco
| Mecanismo | Onde | Garante |
|---|---|---|
| `forbid_mutation` | audit_events, ledger_entries, signatures, application_transitions | append-only (UPDATE/DELETE → erro 42501) |
| `chain_audit` / `chain_ledger` | audit_events (por org), ledger_entries (por projeto) | `seq`, `prev_hash` e `sha256` calculados no banco, serializados por `chain_heads … FOR UPDATE` |
| `ledger_verify(project)` / `audit_verify(org)` | funções | recalculam a cadeia e retornam `first_broken_seq` |
| `guard_columns` | organizations, users, professional_credentials, calls, milestones, documents | colunas privilegiadas (compliance, admin, status de antivírus, verificação) só mudam por admin/sistema |
| `force_initial_state` | professional_credentials | credencial nasce não verificada |
| `guard_self_review` | evidências/despesas | a OSC não aprova a própria evidência/despesa |
| `commitments_integrity` | commitments | soma dos aportes ≤ orçamento; "desembolsado" só pelo financiador; "confirmado" só pela OSC |
| `commitments_rollup`, `budget_rollup` | projetos/marcos | totais derivados, nunca digitados |
| `child_org_matches_project` | tabelas filhas de projeto | `org_id` da linha filha = `org_id` do projeto |
| CHECK em `fiscal_rules` | status `approved` | exige dois aprovadores distintos |

Ledger **sem blockchain**: a cadeia de hash permite detectar alteração; para prova externa, exporte periodicamente o último
`entry_hash` (âncora) para um local fora do controle do operador (ex.: e-mail a auditor, repositório público). Não automatizado.

## Backup e restauração
`scripts/backup.sh` (pg_dump formato custom) e `scripts/restore_test.sh` (restaura em banco temporário e roda
`ledger_verify`/`audit_verify` — **falha** se alguma cadeia estiver quebrada). Testado neste ambiente: restauração OK, cadeias íntegras.
Política de retenção de backup, criptografia em repouso e cópia fora da região: **responsabilidade da infraestrutura** (ver `DEPLOYMENT.md`).

## Desenvolvimento
`scripts/dev_reset_db.sh` recria o banco local (recusa nomes contendo `prod`). `python -m impacto.cli seed-demo` cria dados
**fictícios** (bloqueado fora de development/test).

## Migrações 0004–0005 (v0.8.0–v0.9.0)
| Migração | Conteúdo |
|---|---|
| `0004_v080_modules.sql` | impacto/ODS/indicadores, Impact Graph, diagnóstico, compras, pagamentos como registro, risco, rede/mensagens, localização, relatórios, observabilidade (56 → 85 tabelas) |
| `0005_v090_solutions.sql` | Biblioteca de Soluções: 20 tabelas, 44 políticas, 8 gatilhos de regra de verdade, funções agregadas e de fluxo — ver `SOLUTION_DATA_MODEL.md` (85 → **105** tabelas; **207** políticas RLS no total) |
Extensões exigidas: `pgcrypto`, `citext`, `unaccent`, `pg_trgm`. `pgvector` **não** é usado.
