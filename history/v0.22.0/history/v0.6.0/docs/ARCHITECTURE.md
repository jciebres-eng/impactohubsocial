# Arquitetura de referência (alvo; nada implementado)

## Princípios
Modular monolith; fronteiras de domínio claras; PostgreSQL como fonte da verdade; tudo atrás de interfaces substituíveis (anti lock-in); autorização no servidor por objeto; complexidade só quando medida.

## Camadas
| Camada | Escolha | Substituível por |
|---|---|---|
| Web | React + TypeScript, responsivo, PWA | — |
| API | TypeScript/NestJS (ou equivalente), REST `/v1`, OpenAPI | Fastify etc. |
| Dados | PostgreSQL gerenciado, RLS | qualquer Postgres |
| Arquivos | S3-compatível privado, KMS, URLs assinadas curtas, antivírus | outro S3 |
| Jobs | Fila gerenciada (OCR, e-mail, relatórios) | pg-boss/SQS etc. |
| IA | `AiProvider` (interface) + gateway com redaction, custo, logs | qualquer LLM/OCR |
| Identidade | OIDC; MFA para papéis privilegiados | outro IdP |
| Billing | `BillingProvider` (interface) — **gateway não escolhido** | qualquer gateway |
| E-mail/Push | `Notifier` (interface) | qualquer provedor |
| Observabilidade | logs estruturados, métricas, tracing, alertas | — |

## Módulos de domínio
`identity`, `tenancy`, `organizations`, `programs` (calls, criteria), `applications`, `matching`, `fiscal`, `evidence`, `ledger`, `providers`, `billing` (plans, subscriptions, entitlements, vouchers), `compliance`, `ai`, `notifications`, `admin`, `reporting`.

## Entitlements (direitos)
Um único serviço `EntitlementService.can(subject, featureKey)` consulta plano vigente + vouchers/grants + flags. **Nenhum módulo checa plano diretamente.** Módulos `matching` e `providers` **não importam** `billing` (garante a invariante ADR-008 por construção; verificar com teste de dependência).

## Multi-tenancy
`tenant_id` em toda tabela de negócio; RLS ativa; testes negativos de acesso cruzado (BOLA). Organizações OSC/Prestador podem participar de vários tenants por convite.

## Fluxos críticos
1. Submissão → hard blockers → match_run (versionado) → shortlist → decisão → compromisso → eventos de ledger.
2. Resgate de voucher: transação única (ver `VOUCHERS.md`).
3. Webhook de billing: idempotente, assinatura verificada, reconciliação diária.

## Ambientes
`local`, `staging`, `production`; IaC; segredos em vault; nada de segredo em repositório.

## Portabilidade
Export de dados em formatos documentados; OpenAPI e migrações no repositório do proprietário; sem dependência de serviço proprietário no domínio.
