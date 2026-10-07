# Núcleo SaaS implementado

O MVP agora possui o ciclo comercial local: catálogo de planos → assinatura sandbox → direitos do tenant → dashboard operacional.

## Planos locais

- `funder_basic`: programas:1, seats:3, reports:basic.
- `funder_premium`: programas:5, seats:15, reports:advanced, workflow:custom.
- `enterprise`: programas ilimitados e solicitações de SSO/API/exportação.

## Fluxo

1. Usuário autenticado consulta `GET /v1/plans`.
2. Escolhe um plano com `POST /v1/subscriptions`.
3. A API cria uma assinatura `sandbox_active` ligada ao `org_id`.
4. `GET /v1/entitlements` retorna a assinatura e grants do tenant.
5. `GET /v1/dashboard/summary` retorna contadores isolados por organização.
6. Auditoria registra a criação da assinatura.

## Limite

O sandbox não cobra, não processa cartão e não cria obrigação financeira. A integração real depende de um gateway, webhooks públicos, reconciliação, políticas de cancelamento, termos comerciais e credenciais. Nenhum plano altera o motor de match.
