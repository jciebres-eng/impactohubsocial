# Runbook de publicação — v0.19.0

> Um item por linha, com **O QUÊ · POR QUÊ · ONDE · COMO · QUEM · QUANDO · VALIDAÇÃO · ROLLBACK**.
> Escrito para ser executado por alguém que não participou da construção.
>
> Legenda de QUEM: **P** = proprietário (decisão/credencial) · **I** = infraestrutura · **D** =
> desenvolvimento · **J** = jurídico.

## 0. Pré-requisitos que não são técnicos

| # | O quê | Por quê | Quem | Validação |
|---|---|---|---|---|
| 0.1 | **Aprovação jurídica das 11 minutas** | o banco **recusa** registrar aceite de documento não revisado (`acceptance_stamp()`): sem isso ninguém se cadastra | J + P | `GET /v1/legal/pending` com `status = approved` e revisor registrado |
| 0.2 | Decisão sobre mapeamento GRI/ISSB/IRIS+ | as minutas atuais excluem esses relatórios | P + J | referenciais saem de `registry_only` ou permanecem, com a decisão escrita |
| 0.3 | Preço e regra comercial | nenhuma regra de receita está ativa (zero cartões verdes) | P | `monetization_rules` com cartão legal verde e fonte citada |
| 0.4 | Domínio, marca e busca de anterioridade | `PUBLIC_BASE_URL` e identidade visual | P | domínio registrado e DNS delegado |

## 1. Infraestrutura

| # | O quê | Como | Validação | Rollback |
|---|---|---|---|---|
| 1.1 | Rede e TLS | Nginx de `infra/nginx/impacto.conf`; certificado Let's Encrypt; `server_tokens off` e `proxy_hide_header Server` já estão no arquivo | `curl -I https://DOMINIO` sem `Server: uvicorn`; smoke `no_server_banner` e `https_or_local` | manter o proxy anterior apontando para a versão antiga |
| 1.2 | PostgreSQL 16 gerenciado | `infra/db/bootstrap.sql` cria papéis `impacto_owner`/`impacto_app`; **nunca** rodar a aplicação como owner | `SELECT current_user` = `impacto_app`; boot recusa papel inseguro | restaurar do dump mais recente |
| 1.3 | Contêiner da API | `docker build -f Dockerfile .`; o `CMD` já usa `--proxy-headers --no-server-header` e usuário não-root | `/healthz` 200 e `/readyz` 200 | `docker run` da imagem anterior (tag imutável) |
| 1.4 | Variáveis de ambiente | `.env.example` lista todas; `config.validate` **recusa subir** em produção com segredo de desenvolvimento | o processo sobe; `GET /v1/meta/config` devolve `env=production` | revogar o segredo novo e voltar o anterior |
| 1.5 | Segredos | gerenciador de segredos do provedor; `SECRET_KEY`, `VOUCHER_HMAC_KEY`, `METRICS_TOKEN`, credenciais de SMTP/S3/pagamento | nenhum segredo no Git (`make_release.py` varre o pacote) | rotação documentada em `KEY_ROTATION.md` |

## 2. Banco

| # | O quê | Como | Validação | Rollback |
|---|---|---|---|---|
| 2.1 | Migrações | `python -m impacto.db.migrate` (forward-only, com checksum e lock consultivo) | `python -m impacto.db.migrate --check` sem pendência; `/readyz` sem `pending_migrations` | **não há rollback de migration**: restaurar o dump pré-migração (2.3) |
| 2.2 | Dados de referência | o próprio runner sincroniza planos, flags e regras fiscais **em rascunho** (nunca aprovadas) | `select count(*) from fiscal_rules where status='approved'` = 0 | — |
| 2.3 | Backup ANTES de migrar | `BACKUP_DATABASE_URL=... bash scripts/backup.sh` | arquivo `.dump` + `.sha256` gerados | é o próprio rollback |
| 2.4 | Teste de restauração | `ADMIN_DATABASE_URL=... bash scripts/restore_test.sh backups/X.dump` | imprime "restore OK", 34 migrações, cadeias íntegras, camada econômica **desligada** e camada de impacto **íntegra** | — |
| 2.5 | Carga oficial (opcional) | `scripts/import_territories.py` e `scripts/import_territory_indicators.py` — exigem `--source-name/--source-url/--source-date` | `GET /v1/territories/catalog-status` com `from_official_load` verdadeiro | reverter para o catálogo anterior (versionado) |

## 3. Aplicação

| # | O quê | Como | Validação |
|---|---|---|---|
| 3.1 | Frontend | `cd web && node build.mjs`; o backend serve `web/dist` | `GET /` devolve a SPA com CSP; `test_e2e_web.py::test_security_headers_on_spa` |
| 3.2 | Service worker | gerado pelo build com hash de versão | aba de rede do navegador: `sw` com hash novo |
| 3.3 | Jobs | `python -m impacto.jobs` (ou agendador do provedor); 12 jobs, com lock consultivo | `select * from job_runs order by started_at desc limit 12` |
| 3.4 | E-mail | `MAIL_PROVIDER=smtp` + credenciais; fila em `outbox` com retentativa | enviar recuperação de senha para caixa real e conferir entrega |
| 3.5 | Armazenamento | `STORAGE=s3` + bucket privado | subir documento e baixar pelo link assinado |
| 3.6 | Antivírus | `clamd` como serviço separado | `/readyz` com `antivirus` ≠ `none`; upload infectado recusado |

## 4. Verificação de publicação (obrigatória, nesta ordem)

```bash
# 1. smoke contra o ambiente real (20 verificações)
python3 scripts/smoke_test.py --base https://DOMINIO \
    --email conta-de-verificacao@dominio --password '...' \
    --out docs/evidence/smoke_producao_$(date +%Y%m%d).json
# exige: required_failed = 0. Qualquer SKIPPED precisa de motivo aceito por escrito.

# 2. integridade do banco
REPORT_DATABASE_URL=... python3 scripts/db_integrity_report.py

# 3. carga curta, de fora da máquina do banco
python3 scripts/loadtest.py --base https://DOMINIO --threads 12 --seconds 60 \
    --out docs/evidence/loadtest_producao.json

# 4. backup + restauração ANTES de abrir ao público
BACKUP_DATABASE_URL=... bash scripts/backup.sh
ADMIN_DATABASE_URL=... bash scripts/restore_test.sh backups/<arquivo>.dump
```

**Critério de liberação:** smoke sem falha obrigatória · `/readyz` declarando provedores reais ·
restauração provada · auditoria de dependências anexada · alertas da §5 ativos.

## 4-A. Backup agendado, RPO e RTO (v0.19.0)

Até a v0.18.1 este runbook mandava rodar `scripts/backup.sh` à mão antes de migrar, e isso era tudo
que existia: **nada agendava o backup** — nenhum cron, nenhum serviço, nenhum passo de CI. A v0.19.0
colocou o agendamento no executor de tarefas que já roda (`python3 -m impacto.jobs loop`), com janela
própria.

### Configurar (sem isto, NÃO existe backup)

| Variável | Para quê | Sem ela |
|---|---|---|
| `BACKUP_DIR` | destino dos dumps | tarefa registra `not_configured` |
| `BACKUP_DATABASE_URL` | papel com leitura completa (`impacto_owner`), **não** o da aplicação | tarefa registra `not_configured` |
| `BACKUP_INTERVAL_HOURS` | janela (padrão 24) | — |
| `BACKUP_KEEP` | quantos dumps manter (padrão 14) | — |
| `BACKUP_OFFSITE_CMD` | comando que recebe o dump como `$1` (`rclone copy`, `aws s3 cp`) | só cópia local — **não é recuperação de desastre** |

### Conferir que está rodando

```bash
# veredito por tarefa, incluindo "nunca executou" e "não configurado"
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" https://SEU-DOMINIO/v1/admin/ops/health | jq .
```

O que a tarefa confere em cada execução, e registra em `ops_job_runs.detail`: tamanho do arquivo,
`sha256` contra o `.sha256` gravado, e `pg_restore --list` (que pega o caso do arquivo que existe,
tem tamanho e **não** é um backup válido). Falha não é silenciosa: a execução fica `failed` com o
erro, e a janela **não** se fecha — porque a janela conta do último SUCESSO, não da última tentativa.

### RPO e RTO

**Os números-alvo são decisão do proprietário — `DATA_TO_CONFIRM`.** O que é técnico e já está
decidido é o que a configuração ENTREGA:

| | O que a configuração entrega | O que ainda falta decidir |
|---|---|---|
| **RPO** (quanto de dado se aceita perder) | com `BACKUP_INTERVAL_HOURS=24`, até 24 h + a duração do dump. Com `=6`, até 6 h. O provedor de PostgreSQL gerenciado costuma oferecer PITR, que levaria o RPO a minutos — **somar os dois é o desenho correto**: este backup é camada ADICIONAL | o alvo aceitável para o negócio, e se o provedor terá PITR contratado |
| **RTO** (quanto tempo até voltar) | `scripts/restore_test.sh` mede o ciclo completo (restaurar → migrar → subir → validar) no ambiente onde roda. **Use a medição, não uma estimativa** | o alvo aceitável, e onde fica o ambiente de recuperação |

Preencha a tabela abaixo com a medição do SEU ambiente antes de abrir ao público:

| Medida | Valor medido | Medido em | Por quem |
|---|---|---|---|
| Duração do `backup.sh` em produção | _a medir_ | | |
| Tamanho do dump | _a medir_ | | |
| Ciclo de `restore_test.sh` (RTO observado) | _a medir_ | | |
| RPO alvo decidido | _a decidir_ | | |
| RTO alvo decidido | _a decidir_ | | |

### Cópia externa — `BLOCKED_EXTERNAL`

A plataforma tem o gancho (`BACKUP_OFFSITE_CMD`) e **não** tem destino: isso depende de conta e
credencial de armazenamento, que é decisão e contratação do proprietário. Enquanto não houver,
`GET /v1/admin/ops/health` devolve `backup_offsite_configured: false` e o texto diz, sem rodeio, que
backup local no mesmo host não é recuperação de desastre — um incidente leva o banco e os dumps
juntos.

## 4-B. Canário de e-mail (v0.19.0)

O cadastro depende do e-mail de verificação. Com falha silenciosa de SMTP, o funil de entrada vai a
zero e a plataforma continua respondendo 202 em `/v1/auth/register`.

1. Defina `EMAIL_CANARY_TO` com um endereço **monitorado por pessoa** (caixa de operação, não um
   alias que ninguém abre) e `EMAIL_CANARY_INTERVAL_MINUTES` (padrão 60).
2. Configure o alerta sobre duas coisas, as duas em `GET /v1/admin/ops/health`:
   * `jobs[job=email_canary].verdict` diferente de "última execução concluída";
   * `email.failed > 0` na janela de 60 minutos.
3. **Leia o vocabulário com cuidado:** `accepted_by_smtp` significa que o servidor ACEITOU a
   mensagem. Não é entrega. A plataforma não recebe retorno de entrega do provedor (webhook de
   bounce/delivery), e por isso não afirma entrega em nenhum lugar. Se o canário "passa" e as pessoas
   não recebem, o problema está depois do SMTP — reputação de domínio, SPF/DKIM/DMARC, filtro do
   destinatário — e isso se investiga no painel do provedor, não aqui.

## 5. Observabilidade mínima antes de abrir

| Sinal | Onde | Alerta quando |
|---|---|---|
| Erro 5xx | log estruturado (`level=error`, `request_id`, `error_id`) | > 1% das requisições em 5 min |
| Latência | `/metrics` (`impacto_http_*`) | p95 > 1 s por 10 min |
| Banco | `/readyz` + `impacto_db_pool_connections` | `/readyz` 503, ou pool saturado |
| Fila/jobs | `job_runs` | job sem execução bem-sucedida há 2× o intervalo |
| Webhook | `billing_events` com `status='rejected_signature'` ou `duplicate_count>0` | qualquer rejeição de assinatura |
| E-mail | `outbox` | mensagem com > 3 tentativas |
| Pagamento sem documento fiscal | `platform_charges` × `fiscal_*` | qualquer cobrança paga sem documento quando o provedor fiscal estiver ligado |
| Cross-tenant | log `rls_denied` | pico anômalo (pode ser tentativa, pode ser defeito) |
| Autenticação | tentativas por IP | explosão de 401/429 |

## 6. Incidente

1. **Identificar** pelo `error_id` no log (ele vai no corpo da resposta 500, sem vazar a pilha).
2. **Decidir**: se for regressão da versão nova → voltar a imagem anterior (1.3). Se for dado →
   restaurar (2.3/2.4) **com janela declarada de perda**.
3. **Comunicar**: página pública de estado + aviso na aplicação.
4. **Registrar**: `DECISIONS.md` ganha a decisão tomada; `docs/evidence/` ganha o log.

## 7. Depois de publicar

| Quando | O quê |
|---|---|
| D+0 | smoke a cada hora nas primeiras 6 horas |
| D+1 | conferir `audit_events`, `job_runs`, `outbox`, `rls_denied` |
| D+7 | primeiro backup restaurado em ambiente separado |
| D+30 | reexecutar auditoria de dependências e o relatório de integridade |

## 8. O que este runbook NÃO resolve

Nada aqui substitui: aprovação jurídica (0.1), credencial de provedor (C2 do registro de dívida),
construção da imagem em ambiente com Docker (C4) e coletor de métricas (C5). Os quatro são
**condições** do GO de publicação, e estão marcados como tal.
