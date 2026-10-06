# Runbook de publicação — v0.18.1

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
