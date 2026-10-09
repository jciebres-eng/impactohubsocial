# Auditoria final de execução — IMPACTO v0.31.0

**Data:** 09/10/2026 · **Ramo:** `infra/v0.31.0` (o `main` é o que o Railway publica; a junção depende da sua aprovação) ·
**Ponto de partida:** `171d8b4` (v0.30.0 + análise econômica) · **Versão:** 0.31.0

Estados: **PASS** (implementado e provado por execução nesta rodada) · **PARTIAL** (existe e funciona; o que falta está escrito) ·
**BLOCKED_EXTERNAL** (depende de conta, credencial, painel ou decisão do proprietário; nada simulado) · **FAIL** (falhou e não foi
corrigido — não há nenhum; os que apareceram estão em §7 com a correção). Nada aqui afirma "100% impossível de invadir".

## 1. O pedido → o que virou software e prova

Pedido (pacote `IMPACTO_FINAL_FULL_RAILWAY_SUPABASE_R2_CLOUDFLARE_CLAUDE`): auditoria read-only do estado real, divergência
baseline × Git, Supabase com papéis de menor privilégio e migrações seguras, Railway (build, start, health, workers), R2 privado com
URL assinada, Cloudflare sem mudar DNS, CI/CD sem deploy duplicado, segurança/LGPD, **backup com restauração testada**, release com
ZIP e SHA-256, decisão GO/NO-GO e lista de ações do proprietário — sem publicar produção.

| Item | Estado | Evidência (arquivo · teste · execução) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Identidade da baseline (Gate A) | PASS | `docs/release/REPO_BASELINE_DIFF.md` · `verify_package_against_git.py <baseline> dd2f8c3` | ZIP do pacote = tag v0.29.0 byte a byte; "0.29.01" é só o nome do arquivo | nenhum | — |
| Estado do Supabase por leitura | PASS | `supabase_check.py` · runs 37974779816, 37975067994 | PG 17.11; `impacto_app` sem superusuário/bypass RLS; 71 migrações, 0 pendentes; lote 0064–0070 em 09/10 18:24 UTC fora do GitHub | senha de `impacto_app` divergente do segredo do GitHub | igualar segredo (checklist) |
| Backup **e restauração** do Supabase | PASS | `managed_backup_restore.sh` · modo `backup-restaurar` · run 37975650545 | 341 tabelas, 2.577 linhas idênticas; verificadores íntegros; RTO 15,1 s; nada exportado | RPO depende do plano | conferir backup gerenciado no painel |
| Separação staging × produção | BLOCKED_EXTERNAL | diagnóstico: 15 contas demo + 1 real no mesmo projeto | um projeto só | **P0** para produção | decisão do proprietário (G1) |
| Railway: serviço no ar, variáveis, domínio | BLOCKED_EXTERNAL | sem acesso; nenhum deployment/check-run do Railway no GitHub | não comprovado | **P0** para produção | URL + `railway config pull` (G2) |
| Worker separado (tarefas periódicas) | PASS | `backend/start_worker.sh` · ensaio local · `test_v0310_release_docs.WorkerTests` | pendente → sai; em dia → `impacto_app` + ciclo (18 OK, 2 não configurado) | — | criar o serviço no Railway |
| Imagem com o worker constrói | PASS | job `docker` do CI (run 37977204420) | verde | — | — |
| Validação do R2 (região `auto`, https) | PASS | `config.validate`, `is_r2_endpoint` · `test_v0310_storage.R2ConfigTests` | recusa região AWS com endpoint R2 | — | — |
| Armazenamento local efêmero sinalizado | PASS | `config.storage_is_ephemeral` · `/readyz` `storage_durable` · `EphemeralStorageTests` | aviso no log e em `/readyz` | — | usar R2 |
| Adaptador S3 contra servidor S3 real | PASS | job `armazenamento` do CI (CloudServer, digest registrado) · `RealS3ProtocolTests` | PUT/GET/pré-assinada/expiração/adulteração/credencial errada/DELETE | o servidor de teste não é o R2 | — |
| Bucket R2 real | BLOCKED_EXTERNAL | workflow `armazenamento` pronto | não executado (sem bucket/segredos) | `response-content-disposition` não documentado pelo R2 | criar buckets/tokens e rodar |
| Antivírus (ClamAV) no Railway | BLOCKED_EXTERNAL | cliente `clamd` existente; serviço documentado | não comprovado na rede privada do Railway | uploads em quarentena sem ele (falha fechada) | criar serviço `clamav` |
| Um caminho de publicação; `deploy.yml` de modelo removido | PASS | `pos-deploy.yml` · `test_v0310_release_docs.OnePublicationPathTests` | Railway publica; Actions só verifica | — | — |
| Commit implantado verificável | PASS | `/healthz` `commit` · `test_healthz_reports_the_deployed_commit` | `RAILWAY_GIT_COMMIT_SHA` | — | rodar `pos-deploy` |
| Sem `railway.json` (Config as Code descontinuado) | PASS | docs.railway.com/config-as-code · teste | corte em 2026-12-01 | — | configuração no painel |
| SMTP / e-mail | BLOCKED_EXTERNAL | produção recusa `console` | não configurado | cadastro sem verificação de e-mail | provedor + DNS |
| Cloudflare DNS/TLS/WAF | BLOCKED_EXTERNAL | `INFRA_…_v0310.md` §7 | nada alterado (correto) | — | passos do checklist |
| Documentação de infraestrutura verdadeira | PASS | `test_v0310_release_docs.InfraDocTests` | toda variável documentada é lida pelo código; workflows citados existem | — | — |
| Checklist do proprietário sem pedir segredo | PASS | `OwnerChecklistTests` | — | — | — |
| Análise econômica entra no manifesto | PASS | manifesto v0.31.0 | portão do manifesto verde | — | — |

## 2. Motores

50 motores, inalterados (nenhum código de motor tocado). `MOTOR_COVERAGE_MATRIX.md` VERDE 37 · AMARELO 13 · VERMELHO 0.

## 3. Perfis, rotas e jornadas

Inalterados: 940 operações (nenhuma rota nova: `/healthz` e `/readyz` são rotas estáticas fora do catálogo), 227 telas, 16 jornadas.

## 4. Banco de dados

Nenhuma migração nova (70). Supabase: 71 aplicadas (70 do repositório + `0063_v0231_…` de terceiro, documentada). Nenhuma escrita no
Supabase nesta rodada: diagnóstico em `READ ONLY`, `pg_dump` só lê.

## 5. Segurança e LGPD

| Item | Estado | Evidência | Resultado | Risco | Ação |
|---|---|---|---|---|---|
| Nenhum segredo no repositório, logs ou pacote | PASS | `secrets_scan.py` (0 achados), gitleaks no CI | — | — | — |
| Dump com dado pessoal não sai do job | PASS | `supabase.yml` sem `upload-artifact` · `BackupRestoreTests` | dump apagado | — | — |
| Restauração nunca sobre a origem | PASS | `managed_backup_restore.sh` recusa mesmo host | — | — | — |
| Worker com menor privilégio, sem rotação | PASS | `WorkerTests` | — | — | — |
| Contas de demonstração no banco que tem dado real | PARTIAL | diagnóstico | existem 15 | **P0** antes de produção | G1 |
| Credencial administrativa no ambiente da `api` | PARTIAL | `start_container.sh` migra com ela | aceitável no início | P2 | pré-deploy do Railway com variável própria |

## 6. CI

| Job | Estado | Evidência |
|---|---|---|
| `auditoria`, `docker`, `pilha-do-zero` | PASS | run 37977204420 (branch) |
| `armazenamento` (novo) | PASS | runs 37978728985 e seguintes |
| `backend` | PARTIAL | 2.414 testes; 3 falhas de fechamento/segredo já corrigidas (§7); run final no fechamento |

## 7. Regressão — o que esta rodada encontrou e o que foi feito

Nenhuma falha foi "resolvida" afrouxando teste.

| Falha | Causa real | Correção |
|---|---|---|
| CI do `main` vermelho desde `171d8b4` (`test_every_tracked_file_is_either_in_the_manifest…`) | os 18 arquivos da análise econômica entraram no Git sem entrar no manifesto de nenhuma versão; o portão não foi rodado antes do commit | não reescrevo o manifesto da v0.30.0 (já tem tag): a análise entra no manifesto da v0.31.0, gerado no fechamento |
| Restauração local: `schema "public" already exists` | o dump de um único schema traz `CREATE SCHEMA public`, que todo banco já tem | lista de restauração (`RESTORE_TOC_LIST`) pula só essa entrada e o comentário dela |
| Restauração local: `type "public.citext" does not exist` (e `unaccent`) | `pg_dump --schema=public` não leva extensões; o produto usa `pgcrypto` (em `extensions` no Supabase), `citext`, `unaccent`, `pg_trgm` | o script lê na origem as extensões do produto e o schema de cada uma e as recria no destino antes de restaurar |
| `test_the_repository_carries_no_secret` (`supabase.yml:165`) | URL do PostgreSQL descartável com senha própria (`descartavel`) | segue a convenção do repositório para banco de CI (`postgres`), sem exceção no scanner |
| Job `armazenamento`: `docker run` saiu com 125 | a tag fixada do MinIO não existe | seleção por lista com a imagem e o digest registrados |
| Job `armazenamento`: nenhuma imagem do MinIO baixável | Docker Hub e quay.io negam acesso às imagens públicas do MinIO (run 37978407913) | servidores S3 alternativos que validam SigV4 (CloudServer na prática); o job falha se o teste de protocolo pular |
| `test_v0310_storage` (5 erros na primeira versão) | `load_settings()` valida e recusa sem `DATABASE_URL` no ambiente do teste | ambiente mínimo de desenvolvimento no próprio teste |
| `armazenamento.yml` inválido | `concurrency` em mapa de fluxo com `${{ }}` | mapa em bloco |
| `test_the_frontend_package_metadata_matches` (1ª passagem local) | `web/package.json`/`package-lock.json` ficaram em 0.30.0 | atualizados para 0.31.0 (só o campo de versão) |
| `test_v0230_release_gate` / `test_v0270_release_docs` (5, 1ª passagem) | manifesto e documentos de fechamento são gerados no fechamento | reescritos/gerados no fechamento |
| Afirmação errada num documento meu: "SHA da v0.29.0 registrado no relatório" | estava no `.sha256` do empacotamento (fora do Git) | texto corrigido para o lugar exato |

## 8. Build e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests` | 0 avisos |
| imagem Docker (job `docker` do CI) | verde com `start_worker.sh` |
| `IMPACTO_TRUST_FINAL_RELEASE_0.31.0.zip` | `make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; sem ZIP aninhado; SHA-256 no `.sha256` |

## 9. BLOCKED_EXTERNAL

Railway (serviço, variáveis, domínio); separação staging/produção do Supabase; senha de `impacto_app` no GitHub; buckets e tokens
R2; ClamAV no Railway; SMTP; Cloudflare; backup gerenciado do Supabase (conferir no painel); tag `v0.31.0` (proxy recusa); junção
no `main` (dispara o Railway — requer sua aprovação).

## 10. Veredito desta auditoria

Nenhum FAIL em aberto. O que a rodada podia provar sem as suas contas está provado com execução (inclusive a restauração real do
banco). Para **produção**: dois P0 abertos (G1 separação de ambientes; G2 Railway não verificado) — **NO-GO para produção hoje**;
staging pode ser montado seguindo o checklist. Detalhado em `FINAL_EXECUTION_REPORT.md` §27.
