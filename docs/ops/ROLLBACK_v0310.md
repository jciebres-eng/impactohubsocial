# Rollback — v0.31.0

## O que esta versão mudou que pode precisar voltar

| Mudança | Como voltar | Risco de voltar |
|---|---|---|
| Nenhuma migração nova (continua em 0070) | nada a fazer no banco | nenhum |
| `/healthz` com `commit`, `/readyz` com `storage_durable` | redeploy do commit anterior | nenhum (campos só acrescentados) |
| `config.validate` recusa região AWS com endpoint R2 | redeploy anterior **ou** corrigir `S3_REGION=auto` | voltar mantém o defeito (URLs assinadas falham no R2) |
| `start_worker.sh` (serviço novo) | apagar/suspender o serviço `worker` no Railway | tarefas periódicas param (antivírus, retenção, prazos) |
| `deploy.yml` removido | `git revert` do commit — **não recomendado**: era um modelo que não publicava | nenhum ganho |
| Workflows `armazenamento`, `pos-deploy`, modo `backup-restaurar` | não fazem nada sem disparo manual | nenhum |

## Aplicação (Railway)

1. *Deployments* do serviço → escolher o deployment anterior → **Redeploy** (o Railway mantém o histórico).
2. `pos-deploy` com `commit_esperado` = o SHA anterior.
3. Se o rollback cruzar uma migração: **não** desfazer esquema. As migrações são *forward-only*; o código anterior continua
   compatível com colunas a mais. Para defeito em migração: correção para frente (migração nova) ou restauração planejada
   (`BACKUP_RESTORE_RUNBOOK.md`), nunca `DROP` improvisado.

## Banco

Esta versão não toca o esquema. O lote 0064–0070 aplicado em 09/10 é da v0.26–v0.30 e já está no banco; voltar o código para
antes da 0067 **não** traz de volta as tabelas de assinatura (arquivadas em `legacy_subscription_archive` pela própria 0067).
