# Runbook — backup, restauração e recuperação (v0.31.0; cópia externa atualizada na v0.35.0)

Incidente em andamento? Veja também [RB-07 — perda do banco](../security/runbooks/RB-07-perda-do-banco.md).

## Camadas de backup (e o que cada uma cobre)

| Camada | O que cobre | Quem opera | Estado |
|---|---|---|---|
| Backup gerenciado do Supabase (diário / PITR conforme o plano) | o banco inteiro, incluindo schemas internos do Supabase | Supabase; restauração pelo painel | **não verificado nesta rodada** — conferir em *Database → Backups*: frequência, retenção, PITR |
| `supabase` → `backup-restaurar` (GitHub Actions) | schema `public` do IMPACTO; **prova que restaura** | proprietário dispara | **PASS** em 09/10 (run 37975650545) |
| `backup-supabase` (GitHub Actions, diário 06:17 UTC) | cópia EXTERNA cifrada do schema `public` no R2 (`impacto-backups/supabase/`), 30 dias | agendado; ensaio de restauração todo dia 1º | v0.35.0: cifra **autenticada** (`.dump.aead`, `scripts/backup_crypt.py`, AES-256-GCM em blocos, chave por scrypt da mesma `BACKUP_PASSPHRASE`); arquivo alterado/truncado ou frase errada **falha**; SHA-256 também no resumo da execução (fora do bucket). Os `.dump.enc` antigos (openssl) seguem legíveis até sair da retenção |
| Tarefa `backup` do worker (`BACKUP_DIR`) | dump lógico periódico para um diretório | worker | não configurado (precisa `BACKUP_DIR` num volume ou destino externo) |
| Arquivos (R2) | contratos, evidências, documentos | Cloudflare R2 | **não configurado** — ativar versionamento/cópia do bucket de produção |

## Ensaio de restauração (procedimento que já rodou)

1. GitHub → *Actions* → **supabase** → *Run workflow* → modo `backup-restaurar` (somente leitura na origem).
2. O job: `pg_dump` 17 do schema `public` → SHA-256 → PostgreSQL 17 **descartável** dentro do job → extensões do produto
   recriadas no schema da origem → `scripts/restore_test.sh` (hash, cadeias de hash, camada econômica desligada, travas de
   impacto, camada de operação) → contagem de **todas** as tabelas origem × restauração → dump apagado.
3. Sucesso = anotação "Backup e restauração" com `IDÊNTICAS` e `BACKUP_RESTORE_OK`. Qualquer outra saída = **NO-GO** para migrar.

Resultado de 09/10/2026: 341 tabelas, 2.577 linhas idênticas, 71 migrações, verificadores íntegros, **RTO 15,1 s**.

## RPO / RTO

| Medida | Valor | Base |
|---|---|---|
| RTO do banco (restaurar e verificar) | **15,1 s medidos** no volume atual (2,3 MB) | run 37975650545; cresce com o volume — remedir mensalmente |
| RTO do serviço (Railway volta a servir) | não medido | depende do deploy do Railway; medir no primeiro ensaio de staging |
| RPO | **não definido** | depende do plano do Supabase (diário × PITR) — decisão do proprietário |

## Calendário

| Quando | O quê |
|---|---|
| Antes de **toda** migração em produção | `backup-restaurar` no projeto de produção: PASS obrigatório |
| Mensal | `backup-restaurar` + registrar o RTO medido aqui |
| Trimestral | restaurar o backup **gerenciado** do Supabase num projeto novo (painel) e rodar `supabase` → `verificar` contra ele |
| Após incidente | rodar `verificar` antes de reabrir |

## Quem pode restaurar e como impedir acidentes

- Restauração **por cima** do banco de produção não está automatizada em lugar nenhum, de propósito. O script recusa destino no
  mesmo host da origem (`RECUSADO: origem e destino no mesmo host`).
- Credencial administrativa só em segredos do GitHub (`SUPABASE_ADMIN_URL`) e no Railway (`DATABASE_URL` da `api`). Rotação: trocar
  a senha no painel do Supabase → atualizar os dois lugares → `verificar`.
- Staging nunca aponta para produção: cada ambiente do Railway tem o próprio `DATABASE_URL`; `pos-deploy` mostra `env` e commit.

## Recuperação (incidente de dados)

1. Parar a escrita: suspender o serviço `api` e o `worker` no Railway.
2. Restaurar o backup gerenciado do Supabase **num projeto novo** (PITR para o instante anterior ao incidente, se o plano tiver).
3. `supabase` → `verificar` contra o projeto restaurado (ajustando o segredo para ele) e `backup-restaurar` para conferir integridade.
4. Apontar o `DATABASE_URL` do Railway para o projeto restaurado; redeploy; `pos-deploy`.
5. Registrar o incidente (o que, quando, RPO efetivo, RTO efetivo) neste arquivo.
