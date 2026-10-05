# Implantação

Ambientes `local` → `staging` → `production`; IaC; domínio/TLS; vault; banco gerenciado com PITR (retenção inicial 30 dias); storage privado; alertas — **tudo configurado antes do primeiro dado real**.

## CI/CD (alvo)
lint · typecheck · unit/integração · migrações em banco descartável · SCA de dependências · secret scan · SAST · build · deploy com aprovação humana · feature flags · rollback de app e plano de restauração de dados. Migrações compatíveis retroativamente.

## DR (metas do piloto, não SLA)
RPO ≤ 24 h, RTO ≤ 8 h; restore drill trimestral; runbook de incidente; backups imutáveis em conta/região separada **[VALIDAR residência]**.

## Configuração externa necessária (YELLOW quando implementado)
Cloud e DNS · IdP OIDC · e-mail transacional · provedor de IA/OCR · antivírus · **gateway de cobrança** (assinaturas) · KYB/listas (opcional) · monitoramento.

## Variáveis de ambiente (nomes apenas; sem valores)
`DATABASE_URL`, `OBJECT_STORE_*`, `OIDC_*`, `AI_PROVIDER_*`, `BILLING_PROVIDER_*`, `BILLING_WEBHOOK_SECRET`, `VOUCHER_HMAC_KEY`, `MAIL_*`, `SENTRY/OTEL_*`. Segredos só em vault.
