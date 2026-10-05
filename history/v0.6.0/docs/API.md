# API v1 (especificação inicial; nada implementado)

Regras: REST `/v1`; OpenAPI versionado; autenticação OIDC; autorização por objeto/tenant; paginação por cursor; `Idempotency-Key` em comandos externos; rate limit; erros RFC 9457 (`application/problem+json`).

## Recursos
| Área | Endpoints |
|---|---|
| Programas | `POST /v1/programs`, `POST /v1/calls`, `POST /v1/calls/{id}/criteria-versions` |
| Candidaturas | `GET/POST /v1/applications`, `POST /v1/applications/{id}/documents`, `POST /v1/reviews/{id}/decision` |
| Oportunidades/Match | `GET /v1/opportunities`, `POST /v1/matches/evaluate`, `GET /v1/matches/{runId}` |
| Projetos | `POST /v1/projects`, `POST /v1/projects/{id}/tranches`, `POST /v1/commitments`, `POST /v1/milestones`, `POST /v1/evidence` |
| Prestadores | `GET/POST /v1/projects/{id}/service-needs`, `POST /v1/service-providers/search`, `POST /v1/service-engagements`, `POST /v1/tasks`, `POST /v1/signatures` |
| Billing | `GET /v1/plans`, `GET /v1/me/entitlements`, `POST /v1/subscriptions`, `POST /v1/subscriptions/{id}/cancel`, `POST /v1/webhooks/billing` |
| Vouchers (usuário) | `POST /v1/vouchers/validate`, `POST /v1/vouchers/redeem` |
| Vouchers (admin) | `POST /v1/admin/voucher-batches`, `GET /v1/admin/vouchers`, `POST /v1/admin/vouchers/{id}/revoke`, `GET /v1/admin/voucher-batches/{id}/export` |
| Auditoria | `GET /v1/audit-events` |
| Fiscal | `GET /v1/fiscal/mechanisms?context=...` (somente "possível mecanismo a validar") |
| LGPD | `POST /v1/privacy/requests` |
| Saúde | `GET /healthz`, `GET /readyz` |

## Contratos sensíveis
- `POST /v1/vouchers/redeem` → `200 {entitlement, expires_at}` | `404` (genérico para código inválido/expirado/esgotado, evita enumeração) | `429`.
- `GET /v1/me/entitlements` → lista de `featureKey` com limites e origem (`plan|voucher|flag`).
- Respostas de match **sempre** incluem `engine_version`, `criteria_version`, `computed_at`, `confidence`, `explanations`.
