# Operação

## Processos
| Processo | Comando | Observação |
|---|---|---|
| API | `uvicorn impacto.main:app` (imagem Docker) | stateless; escale réplicas |
| Jobs | `python -m impacto.jobs loop` (ou `once` via cron) | uma instância (lock consultivo); intervalo `JOBS_INTERVAL_SECONDS` (900) |
| Migrações | `python -m impacto.db.migrate` | papel dono; forward-only |
| Admin/CLI | `python -m impacto.cli create-admin|gen-secrets|seed-demo` | seed só dev/test |

## Jobs (`jobs.py`)
`close_calls` (fecha editais vencidos) · `import_sources` (importa feeds JSON/RSS cadastrados) · `saved_searches` (alertas) · `pending_scans` (reprocessa antivírus pendente) · `document_expiry` (avisa vencimentos) · `retention` (limpeza). Resultado em `job_runs` (`GET /v1/admin/jobs`).

## Observabilidade
Logs JSON (`request_id`, sem corpo de requisição) · `/healthz` · `/readyz` (checa banco) · `/metrics` (Prometheus, exige `METRICS_TOKEN`; bloqueado no nginx de referência) · métricas de IA/jobs/HTTP · alertas de exemplo `infra/monitoring/alerts.yml` (**não ativos**). Ausentes: traces distribuídos, error tracking (ex.: Sentry), dashboards.

## Runbooks resumidos
- **Cadeia de hash quebrada** (`/v1/admin/audit/verify` ou `ledger_verify` inválido): isolar, comparar com último backup (`restore_test.sh`), investigar acesso privilegiado ao banco; nunca “consertar” linhas.
- **Webhook falhando**: ver `billing_events`; reenvio pelo Stripe é idempotente.
- **Antivírus indisponível**: documentos ficam `pending_scan` e **não contam** como válidos no match; job reprocessa.
- **Suspeita de vazamento de segredo**: rotacionar `SECRET_KEY` (invalida sessões), `FIELD_ENCRYPTION_KEY` (**exige recriptografar segredos MFA** — planejar), `VOUCHER_HMAC_KEY` (invalida códigos emitidos).
- **Incidente com dados pessoais**: acionar encarregado; avaliar comunicação à ANPD/titulares (art. 48).
- **Restore**: `scripts/restore_test.sh` em banco temporário antes de qualquer restauração real.

## Biblioteca de Soluções (v0.9.0)
Métricas a observar: latência de `/v1/solutions/search` (referência local p95 ≈ 474 ms com 5.000 soluções), taxa de buscas vazias, `unmatched_terms` mais frequentes (manutenção do tesauro), fila de verificação admin, pedidos sem resposta. Jobs de retenção devem limitar `solution_search_log`. Particionar `solution_events`/`solution_search_log` por mês ao crescer. Remover dados DEMO antes de abrir a usuários reais.
