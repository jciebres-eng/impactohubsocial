# Deployment checklist

| Gate | Estado | Evidência |
|---|---|---|
| Testes locais | GREEN | 6 testes unitários + E2E HTTP |
| Backup/restore local | GREEN | scripts/backup.sh e restore.sh |
| CI declarada | GREEN | .github/workflows/ci.yml |
| RLS PostgreSQL | YELLOW | migration criada, banco não disponível neste ambiente |
| OIDC/MFA | RED | IdP e credenciais ausentes |
| Storage S3/KMS | RED | conta/bucket/IAM ausentes |
| Antivírus | YELLOW | hook + quarentena; engine não configurado |
| Billing | YELLOW | sandbox adapter; gateway real ausente |
| IA | YELLOW | interface + disabled adapter; provedor ausente |
| Observabilidade | YELLOW | variáveis OTEL; collector ausente |
| Pentest | RED | precisa autorização e execução externa |
| Web publicado | RED | domínio/hosting não conectados |
| Android/iOS | RED | contas, certificados e builds nativos ausentes |
