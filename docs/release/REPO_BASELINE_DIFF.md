# Divergência — baseline do pacote de infraestrutura × repositório Git (v0.31.0)

Gerado em 09/10/2026 para o pacote `IMPACTO_FINAL_FULL_RAILWAY_SUPABASE_R2_CLOUDFLARE_CLAUDE.zip`.
Toda afirmação abaixo tem o comando que a reproduz.

## 1. A baseline é a v0.29.0, sem alteração

| Pergunta | Resposta | Como reproduzir |
|---|---|---|
| Que arquivo é a "baseline 0.29.01"? | `05_BASES/IMPACTO_TRUST_FINAL_RELEASE_0.29.01_BASELINE.zip`, 3.545 arquivos sob `plataforma-impacto-v0.29.0/` | `unzip -l` |
| SHA-256 do ZIP | `d8aec4241bc1f5a5d09d2da63b2e8434a1ccf96972c14f47f4c2f23970a940c3` | `sha256sum` |
| É o pacote da v0.29.0? | **Sim** — mesmo SHA-256 do `IMPACTO_TRUST_FINAL_RELEASE_0.29.0.zip` entregue em 08/10 (o hash foi gravado no empacotamento em `dist-release/IMPACTO_TRUST_FINAL_RELEASE_0.29.0.zip.sha256`, fora do Git, e informado na entrega) | `cat dist-release/IMPACTO_TRUST_FINAL_RELEASE_0.29.0.zip.sha256` |
| O conteúdo bate com o Git? | **Sim, byte a byte**: "OK: todo arquivo do pacote é o objeto Git do commit" `dd2f8c3` (tag `v0.29.0`); 2 exceções declaradas (geradas no empacotamento); 0 arquivos versionados fora do pacote | `python3 scripts/verify_package_against_git.py <extraído>/plataforma-impacto-v0.29.0 dd2f8c3` |
| Por que "0.29.01"? | o **nome do arquivo** foi alterado fora do repositório; não existe versão 0.29.01 no Git (`VERSION`, tags, changelog) | `git tag`; `git log --all --oneline -- VERSION` |

**Conclusão:** nenhum arquivo da baseline precisa ser copiado para o repositório — ela é um retrato
anterior do próprio repositório. Copiar arquivos dela **regrediria** o código.

## 2. O que o repositório tem a mais (dd2f8c3 → início desta rodada)

`git diff --name-status dd2f8c3 9634193` — 18 commits, 271 arquivos: 207 adicionados, 61 modificados,
2 renomeados, 1 removido.

| Área | Arquivos | Conteúdo |
|---|---:|---|
| `backend/migrations` | 1 | `0070_v0300_evidence_object.sql` (evidência como objeto de primeira classe, v0.30.0) |
| `backend/impacto` | 6 | dossiê longitudinal, evidência contestável, mudança de método de indicador; nesta rodada: `/healthz` com commit, `/readyz` com `storage_durable`, validação R2 |
| `backend/tests` | 11 | 10 módulos novos (v0.30.0, análise econômica, armazenamento v0.31.0) |
| `web/src` | 3 | tela do dossiê (`/projetos/:id/dossie`) |
| `.github/workflows` | 5 | `supabase.yml` (modo `backup-restaurar`), `ci.yml` (job `armazenamento`, disparo manual), `armazenamento.yml` (novo), `pos-deploy.yml` (substitui `deploy.yml`) |
| `scripts` | 11 | modelo econômico de 120 meses, `managed_backup_restore.sh`, `storage_smoke.py`, diagnóstico do Supabase estendido |
| `docs` | 44 | v0.30.0, análise econômica, infraestrutura v0.31.0 |
| `config` | 1 | sensibilidade da taxa (`economic_model.json`, v0.30.0) |

## 3. Itens que o pacote supunha e o código atual responde

| Suposição do pacote | Estado real no código |
|---|---|
| `Dockerfile` com `PORT=8080`, `/healthz`, `backend/start_container.sh` | confirmado; `HEALTHCHECK` usa `$PORT`; o entrypoint migra e troca para `impacto_app` |
| `DATABASE_URL` = papel de aplicação; `MIGRATION_DATABASE_URL` = dono | **mudou desde a v0.24**: no contêiner, `DATABASE_URL` é a **administrativa**; o entrypoint migra com ela e reescreve para `impacto_app` (`impacto.db.app_url`, ciente do sufixo do pooler do Supabase). `MIGRATION_DATABASE_URL` só é lida por `python -m impacto.db.migrate` avulso |
| `deploy.yml` termina em placeholder | confirmado e **removido** nesta rodada (substituído por `pos-deploy.yml`, que não publica) |
| Supabase usado só como PostgreSQL | confirmado: nenhum uso de Supabase Auth, Storage, Realtime ou Functions no código |
| adaptador S3 compatível com R2 | assinatura SigV4 própria, *path-style*; região tem de ser `auto` (agora validado); `response-content-disposition` não documentado pelo R2 — verificar no bucket real |
| ClamAV | cliente `clamd` (INSTREAM/TCP); download de arquivo não verificado bloqueado em produção (falha fechada) |
