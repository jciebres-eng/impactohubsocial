# Implantação (v0.7.0)

**Status honesto:** nada aqui foi executado em infraestrutura real. Docker/Compose, Nginx, GitHub Actions e deploy são **templates revisados, não testados** neste ambiente (sem daemon Docker, sem GitHub, sem domínio). O que foi testado: a aplicação, o banco, o build web, backup/restore.

## Topologia mínima recomendada
```
Internet → CDN/WAF (opcional) → Nginx (TLS, infra/nginx/impacto.conf) → container "api" (uvicorn, :8080)
                                                    ├─ PostgreSQL 16 gerenciado (backup + PITR)
                                                    ├─ Object storage S3-compatível (privado)
                                                    ├─ ClamAV (clamd) — obrigatório em produção
                                                    ├─ SMTP transacional
                                                    └─ container "jobs" (python -m impacto.jobs loop)
```
Escala: API é *stateless* (sessões no banco) → réplicas atrás do balanceador. Jobs: **uma** instância (usa lock consultivo).

## Passo a passo
1. **Banco**: criar papéis/banco com `infra/db/bootstrap.sql` (defina senhas fortes; `impacto_owner` e `impacto_app`). Habilitar backup automático e criptografia em repouso.
2. **Segredos**: `python -m impacto.cli gen-secrets` → guardar em cofre (não em git). Ver lista em `.env.example`.
3. **Config**: `IMPACTO_ENV=production`, `PUBLIC_BASE_URL=https://…`, `COOKIE_SECURE=true`, `MAIL_PROVIDER=smtp`, `STORAGE_PROVIDER=s3`, `ANTIVIRUS_PROVIDER=clamd`, `BILLING_PROVIDER=none` (ou `stripe` após homologação), `TRUST_PROXY_HEADERS=true` somente atrás do proxy.
4. **Build**: `docker build -t impacto:0.7.0 .` (multi-stage: Node → build web; Python slim com libpq5, tesseract-por, usuário não-root, healthcheck).
5. **Migrações**: `MIGRATION_DATABASE_URL=… python -m impacto.db.migrate` (papel dono; checksum, lock consultivo).
6. **Primeiro admin**: `python -m impacto.cli create-admin --email … --name …` (senha lida do stdin, nunca por argumento; MFA é exigido no primeiro acesso à área admin).
7. **Subir** API + jobs; conferir `GET /healthz` (vivo), `GET /readyz` (banco ok), `/metrics` com `METRICS_TOKEN`.
8. **Fail-fast**: com configuração insegura em production o processo **não sobe** (`config.validate`) — isso é intencional.
9. **Proxy/TLS**: ajustar `infra/nginx/impacto.conf`; HSTS já é enviado pela aplicação.
10. **Observabilidade**: raspar `/metrics` (Prometheus); regras de alerta de exemplo em `infra/monitoring/alerts.yml`; logs JSON com `request_id` → agregador.
11. **Backups**: `scripts/backup.sh` agendado + `scripts/restore_test.sh` periódico (restaura em banco temporário e valida as cadeias de hash).

## Docker Compose (desenvolvimento/homologação)
`infra/compose/docker-compose.yml` (postgres + api + jobs + clamav). **Não testado aqui.**

## Rollback
Imagens versionadas; migrações são *forward-only*: para reverter, restaure backup + imagem anterior. Faça backup antes de cada migração.

## CI/CD
`.github/workflows/ci.yml` (lint, typecheck com tipos oficiais, build, testes com Postgres de serviço, E2E Playwright, pip-audit/npm audit, build Docker + teste fail-fast) e `deploy.yml` (modelo — requer ambiente, segredos e destino definidos pelo proprietário). **Nenhum pipeline foi executado.**

Checklist de go-live: `DEPLOYMENT_CHECKLIST.md`. Prontidão: `PRODUCTION_READINESS.md`.
