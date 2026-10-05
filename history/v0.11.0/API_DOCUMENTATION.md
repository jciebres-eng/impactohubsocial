# API — documentação (v0.11.0)

Referência completa **gerada do código**: `docs/API.md` (373 operações) e `docs/openapi.json` (também em `GET /v1/openapi.json`). Convenções de autenticação, CSRF, erros e paginação: início de `docs/API.md`.

## Biblioteca de Soluções (60 operações novas)
| Grupo | Rotas principais |
|---|---|
| Cadastro | `POST /v1/solutions` · `PATCH/DELETE /v1/solutions/{id}` · `POST …/publish·archive·confirm-review·request-review` · `GET …/versions` · `GET /v1/solutions/mine` |
| Componentes | `PUT …/people` · `POST …/evidence` · `POST …/results` · `PUT …/replication-profile` · `POST …/relationships` |
| Leitura | `GET /v1/solutions/{id}` (perfil + proveniência + pontuações) · `GET /v1/solutions/vocabulary` · `GET /v1/solutions/aggregates` · `GET …/funnel` |
| Busca | `POST /v1/solutions/search` (rate-limit 120/10 min) · `POST /v1/solutions/intent/parse` · `POST /v1/solutions/assistant` · `GET …/similar` |
| Análise | `POST /v1/solutions/compare` (2–4) · `POST /v1/solutions/combine` · `GET /v1/solutions/combinations` · `POST …/adapt` · `GET …/adaptations` · `POST …/develop` |
| Match | `POST …/match` · `GET /v1/solutions/recommendations` · `PUT/GET /v1/solutions/funder-preferences` · `PUT /v1/solutions/personalization` |
| Interação | `PUT/DELETE …/save` · `GET /v1/solutions/saved` · `POST …/events` · `POST …/requests` · `GET /v1/solution-requests/{received,sent}` · `POST /v1/solution-requests/{id}/respond·close` |
| Intenção | `PUT/DELETE …/intent` · `GET …/intents` · `POST /v1/solution-intents/{id}/stage` · `GET /v1/solution-intents/mine` |
| Replicação | `GET /v1/replications/marketplace` · `POST …/replications` · `PATCH /v1/solution-replications/{id}` · `POST …/confirm` · `GET …/mine` |
| Confiança | `POST …/reviews` · `POST …/disputes` · denúncia via `POST /v1/reports` (`target_type: solution`) |
| Admin | `GET /v1/admin/solutions/queue` · `POST /v1/admin/solution-evidence/{id}/review` · `POST …/solution-results/{id}/validate` · `POST …/solutions/{id}/verify·remove` · `POST …/solution-disputes/{id}/decide` |

Os caminhos pedidos no prompt (`/solutions/{id}/replicate`, `/recommendations`, `/intent`…) foram mapeados para os nomes acima (prefixo `/v1`, recursos no plural). Rotas literais são registradas antes de `/{solution_id}` (ordenação por especificidade em `app.py`).
Segurança por rota: `auth=org` (sessão + CSRF + e-mail verificado em escrita), papéis mínimos, `kinds`, UUID validado em todo `*_id`, corpo com `extra=forbid`, limites de tamanho, RLS no banco.

## Camada institucional (37 operações novas)
| Grupo | Rotas principais |
|---|---|
| Catálogos e regras (leitura) | `GET /v1/institutional/catalogs` · `GET /v1/institutional/rules` |
| Perfil | `GET/PUT /v1/institutional/profile` · `GET /v1/institutional/overview` · `GET …/maturity` · `GET …/statement` · `GET …/badges` · `GET /v1/institutional/orgs/{org_id}` (público) |
| Qualificações | `GET/POST /v1/institutional/qualifications` · `PATCH/DELETE …/{id}` · `GET …/{id}/events` |
| Documentos | `GET /v1/institutional/documents` (com estado) |
| Elegibilidade | `POST /v1/institutional/eligibility` (limite 120/10 min) · `GET /v1/institutional/eligibility` |
| Necessidades | `GET/POST /v1/institutional/needs` · `PATCH/DELETE …/{id}` |
| Admin (MFA) — catálogos | `GET/POST /v1/admin/institutional/catalog` · `…/{id}/new-version` · `…/{id}/action` |
| Admin — regras | `GET/POST /v1/admin/institutional/rules` · `…/{id}/new-version` · `…/{id}/action` · `POST …/rules/import-candidates` |
| Admin — filas | `GET /v1/admin/institutional/qualifications` · `POST …/{id}/decide` · `GET …/documents` · `POST …/{id}/validate` |
| Admin — organização | `GET …/organizations/{org_id}` · `POST …/organizations/{org_id}/status` · `GET …/overview` |
Campos novos: edital (`funding_modality`, `accepted_legal_natures`, `min_maturity`), perfil do financiador, cadastro (`organization.legal_nature_code`), solução (IP/confidencialidade/modalidades) e busca (`legal_natures`, `qualifications`, `modalities`, `funding_ready`, `sharing`).

## Novidades do v0.10.1
`GET /v1/institutional/persona`, `GET/POST /v1/institutional/agreements` (+ `PATCH/DELETE /{id}`), `GET /v1/institutional/formalization`, `PUT /v1/institutional/formalization/{step_code}`, `GET/POST /v1/institutional/mentoring` (+ `POST /{id}/cancel`), `GET /v1/solutions/{id}/network`; admin: `GET /v1/admin/institutional/agreements`, `POST …/agreements/{id}/decide`, `GET /v1/admin/institutional/mentoring`, `POST …/mentoring/{id}/update`. `GET /v1/insights/fiscal-estimates` ganhou `osc_org_id` e o bloco `institutional_eligibility`. Detalhes gerados em `docs/API.md`.

## Monetização (v0.11.0 — 15 operações novas; ver `docs/billing.md`)
| Grupo | Rotas |
|---|---|
| Organização | `GET /v1/plans` (tiers, preços, economia anual) · `GET /v1/billing` · `POST /v1/billing/quote` · `/checkout` · `/cancel` · `/reactivate` · `/change-plan` · `/portal` · `POST /v1/vouchers/redeem` · `POST /v1/agreements/join` |
| Webhook | `POST /v1/billing/webhooks/stripe` (assinatura HMAC, idempotente, fora de ordem) |
| Admin (MFA, motivo, auditoria) | `GET /v1/admin/billing/organizations/{id}` · `POST .../trial` · `POST /v1/admin/grants/{id}/revoke` · `PUT /v1/admin/plans/{plan_key}/price` · `/v1/admin/agreements` (+ `/action`, `/members`, revogar) · `GET /v1/admin/voucher-batches/{id}/redemptions` |
O cliente **não** envia preço, desconto, tier nem direitos: campos extras são recusados (422).
