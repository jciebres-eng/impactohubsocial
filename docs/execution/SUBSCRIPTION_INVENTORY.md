# INVENTÁRIO DA ASSINATURA — v0.27.0 (ADR-341)

**Decisão do proprietário:** NÃO EXISTEM MAIS ASSINATURAS. O IMPACTO deixa de ser um SaaS por mensalidade e
passa a ser infraestrutura de inteligência e operação de impacto, monetizada pelo valor econômico que cria
(camada econômica da operação financiada: 3,5% de taxa de serviço contratada + 1,5% de participação de
autoria quando contratualmente elegível) e por contratos avulsos/parcelados.

**Método (exigido pelo prompt):** nada foi apagado às cegas. Cada ocorrência foi inventariada, classificada
em **KEEP / MIGRATE / DEPRECATE / DELETE**, migrada ou removida, e a regressão foi executada. O resultado
estrutural é conferido por `backend/tests/test_v0210_pricing_catalog.py::CatalogIsCapabilityBundlesTests::test_the_database_has_no_subscription_structures`
e os comportamentos por `test_v0110_monetization.py`, `test_v0210_offer.py`, `test_api_features.py`,
`test_v0220_financial_engine.py`, `test_v0210_free_period.py`, `test_architecture.py`.

Legenda: **KEEP** continua como está · **MIGRATE** continua com semântica nova · **DEPRECATE** fica no banco
por histórico e não é mais produzido · **DELETE** removido.

## 1. Banco de dados (migração `0067_v0270_no_subscription.sql`)

| Estrutura | Classificação | O que foi feito |
| --- | --- | --- |
| `subscriptions` | DELETE | tabela removida (status, provedor, período, cancelamento) |
| `subscription_prices` | DELETE | preço congelado por assinatura — sem assinatura, sem o que congelar |
| `price_change_notices` + `price_notice_guard`, `price_notice_ack_only`, `price_apply_guard` | DELETE | aviso de reajuste de 30 dias: só existe para mensalidade |
| `plan_price_versions` + `price_current()`, `price_version_immutable` | DELETE | tabela de preços de assinatura com vigência |
| `plan_prices` | DELETE | tabela de preços v0.11.0 |
| `org_trials`, `trial_claims`, `trg_org_trials_guard` | DELETE | trial de 14 dias e anti-abuso por HMAC |
| `trial_requests` | DELETE | pedido de teste; quem quer conhecer módulos pede demonstração (`demo_requests`, KEEP) |
| `invoices.subscription_id`, `platform_charges.subscription_id`, `free_periods.subscription_id`, `voucher_redemptions.consumed_by_subscription`, `commercial_offers.price_version_id`, `commercial_offers.interval`, `offer_acceptances.price_version_id` | DELETE | colunas dependentes |
| `plans.price_cents`, `plans.interval` | DELETE | `plans` vira PACOTE DE CAPACIDADES (MIGRATE): nome de um conjunto de limites e recursos |
| `platform_charges.kind = 'subscription'` | DEPRECATE | CHECK novo (`NOT VALID`): linhas históricas ficam, nenhuma nova nasce |
| `voucher_redemptions.status = 'pending_discount'` | DEPRECATE | idem |
| `free_periods.source = '2027_NEW_SUBSCRIPTION'` | DEPRECATE | idem; `free_periods` KEEP como período de CONCESSÃO |
| `commercial_offers.billing_frequency = 'recurring'`, `offer_acceptances` idem | DEPRECATE | CHECK novo; a oferta vira CONTRATO avulso/parcelado (MIGRATE) com `amount_reason` e `contract_ref` |
| `entitlement_grants` | KEEP + MIGRATE | origem nova `contract` (aceite de contrato com autorização concede o pacote; revogar revoga) |
| `vouchers` (`grant_plan`, `grant_feature`, `free_period`) | KEEP | concessões por código continuam |
| `vouchers` (`percent_off`, `amount_off`) | DEPRECATE | não há assinatura para descontar; resgate responde resposta genérica; criação recusada pelo schema |
| `agreements.discount_percent` (convênios) | DEPRECATE | convênio só concede pacote; desconto recusado na criação (422 `discount_retired`) |
| `billing_notices` | KEEP | deduplicação de avisos (concessões, alertas de uso) |
| `org_commercial_state()` | MIGRATE | v2: FREE_ACCESS / FREE_GRANT / GRANT_EXPIRING / CONTRACTED |
| `charge_requires_authorization()` | MIGRATE | reconhece também o acordo de financiamento assinado pelo pagador (ADR-342) |
| `acceptance_immutable()`, `free_period_immutable()` | MIGRATE | recriadas sem as colunas removidas |
| `monetization_rules.saas.institutional.funder` | DEPRECATE | `legal_status = refused`, `active = false`, carta VERMELHA explicando a decisão; `trigger_kind`/`pricing_mode` perdem o valor `subscription` |
| `economic_rules` | MIGRATE | Pricing Version **2027.02** com os mesmos 350/150 bps; a 2027.01 fica (acordos antigos a congelaram) |
| `chart_of_accounts` 4.1 / 4.1.1 / 2.2.1 | MIGRATE | renomeadas: receita da camada econômica da operação; taxa instruída e não quitada |
| `billing_events`, `invoices`, `platform_charges` | KEEP | histórico de cobrança própria; nada apagado |

## 2. Backend

| Ocorrência | Classificação | O que foi feito |
| --- | --- | --- |
| `services/billing.py` (Stripe checkout, portal, webhooks, cancel, change-plan, sandbox) | DELETE | arquivo removido |
| `services/monetization.py` | MIGRATE | ficaram tier, `notify_once`, vouchers de concessão, convênios, `pricing_version_name`, pisos de contrato; saíram trial, preço, cotação, desconto, avisos de cobrança, `lifecycle_job` |
| `services/entitlements.py` | MIGRATE | fontes de direito: pacote base + `entitlement_grants`; sem assinatura, sem trial |
| `services/free_period.py` | MIGRATE | período de CONCESSÃO; `grant_new_subscription` e `NEW_SUBSCRIPTION_MONTHS` removidos; STATES v2 |
| `services/offers.py` | MIGRATE | `create()` recebe valor + motivo (alçada), sem `recurring`; `grant_for_acceptance` / `revoke_contract_grants` |
| `services/hub.py` | DELETE parcial | `trial_request_decide`, `trial_dashboard`, item de pendência do trial (virou aviso de concessão) |
| `services/auth.py` | MIGRATE | cadastro não inicia trial; `me` devolve `subscription: null` e `tier` |
| `api/billing_routes.py` | MIGRATE | ficam `GET /v1/plans` (pacotes + vias de acesso), `GET /v1/billing` (acesso e concessões), `POST /v1/vouchers/redeem`; saíram checkout/quote/cancel/reactivate/change-plan/portal/price/price-history/price-notices/webhook Stripe |
| `api/monetization_routes.py` | MIGRATE | saíram trial administrativo e `PUT /v1/admin/plans/{k}/price`; visão de suporte mostra acesso e contratos |
| `api/commercial_routes.py` | MIGRATE | `POST /v1/admin/commercial/offers` (finance.approve) substitui a criação pela organização; aceite autorizado concede pacote; revogação revoga |
| `api/admin_routes.py` | MIGRATE | `manual-subscription` → `POST /v1/admin/organizations/{id}/license` (concessão com prazo, sem renovação); vouchers só de concessão; painel sem bloco de assinaturas |
| `api/knowledge_routes.py`, `api/content_admin_routes.py`, `api/hub_schemas.py` | DELETE parcial | rotas e schema de pedido de teste |
| `api/schemas.py`, `api/economics_schemas.py` | MIGRATE | `PriceQ/CheckoutIn/QuoteIn/ChangePlanIn` removidos; `CommercialOfferIn` com `org_id/amount_cents/amount_reason`; `ChargeKind` sem `subscription` |
| `economics/metrics.py` | MIGRATE | `recurring_revenue` (MRR/ARR) → `operation_revenue` lido de `economic_events`; `conversion` mede cadastro → operação |
| `economics/payments.py` | MIGRATE | provedor derivado da chave; bloco `subscriptions` do relatório → `invoices` |
| `core/access.py`, `api/access_routes.py` | MIGRATE | sem `subscription_status`; estado comercial v2 |
| `jobs.py` | DELETE parcial | `billing_lifecycle` removido; `commercial_sweep` continua (só avisa) |
| `db/migrate.py` | MIGRATE | sincroniza pacotes sem preço; `_sync_price_versions` removido |
| `config.py`, `.env.example`, `infra/compose/demo/compose.yml` | MIGRATE | `BILLING_PROVIDER`, `STRIPE_PRICE_*`, `TRIAL_*` removidos; `STRIPE_SECRET_KEY/WEBHOOK_SECRET` ficam (cobrança própria), `PLATFORM_PIX_KEY` documentada |
| `integrations/events.py` | MIGRATE | `SUBSCRIPTION.*`/`TRIAL.*` → `OPERATION.ACTIVATED`, `OPERATION.SETTLED`, `PAYOUT.CONFIRMED` |
| `config/plans.json` | MIGRATE | `plans@4.0`: sem `price_cents/interval/prices/price_versions/trial`; `obtained_by`; `pricing_version` 2027.02; invariante `no_subscription` |
| `config/i18n.json` | MIGRATE | namespaces `subscription`, `checkout`, `cancellation` removidos; `billing`/`pricing` reescritos |

## 3. Frontend

| Tela / rota | Classificação | O que foi feito |
| --- | --- | --- |
| `/conta/plano` → `/conta/acesso` (`pages/org.tsx::Plan`) | MIGRATE | "Acesso e concessões": de onde vem o acesso, vias de acesso, pacotes sem preço, voucher, convênio, faturas de contrato. Sem checkout, cotação, cancelamento, portal. A rota antiga continua respondendo a mesma tela |
| `/planos` (`pages/commercial.tsx::Pricing`) | MIGRATE | "Como o IMPACTO se sustenta": vias de acesso, pacotes com piso de contrato, o que o dinheiro não compra |
| `FreePeriodBanner`, estados comerciais | MIGRATE | concessão; rótulos v2 |
| `/ajuda/teste` (`Help.TrialRequest`), `/admin/central/testes` (`HelpA.Trials`) | DELETE | removidas; pedido de teste não existe |
| `pages/admin.tsx::OrgBilling` | MIGRATE | painel de trial → licença sob contrato; vouchers só de concessão; convênio sem desconto |
| `pages/internal.tsx` | MIGRATE | "Receita recorrente" → "Camada econômica da operação" |
| `pages/portal.tsx`, `pages/calls.tsx`, `access.tsx`, menu "Plano" → "Acesso" | MIGRATE | textos e tipos |

## 4. Testes

| Módulo | Classificação | O que foi feito |
| --- | --- | --- |
| `test_v0160_billing.py` (15: versões de preço, reajuste, webhook) | DELETE | a funcionalidade deixou de existir |
| `test_v0110_monetization.py` (34 → 18) | MIGRATE | removidos trial e fluxo Stripe; mantidos pacotes, vouchers de concessão, convênios, segurança; novos: ausência de checkout/assinatura, licença sob contrato, desconto aposentado |
| `test_v0210_pricing_catalog.py` (22 → 17) | MIGRATE | conferência da tabela de mensalidades → conferência de que NÃO há estrutura de assinatura e de que a regra está recusada |
| `test_v0210_offer.py` | MIGRATE | valor vem de quem tem alçada; `recurring` recusado; aceite concede/revogação revoga |
| `test_api_features.py` | MIGRATE | checkout sandbox → licença; webhook → ausente |
| `test_v0220_financial_engine.py` | MIGRATE | MRR → camada econômica (ADR-341); teste de custódia conferido pela estrutura (ADR-343) |
| `test_v0210_free_period.py`, `test_v0210_commercial_ui.py`, `test_v0210_usage.py`, `test_v0170_*`, `test_v0120_*`, `test_v0130_integrations.py`, `test_v0150_upgrade.py`, `test_v0220_authorization.py`, `test_v0230_*`, `test_architecture.py`, `test_e2e_*` | MIGRATE | referências a trial/assinatura/preço trocadas pelo equivalente do modelo novo |
| `tests/support.py` | DELETE parcial | `_declare_test_prices`, `TEST_PRICES` |

## 5. Documentação

Documentos que descreviam a assinatura (PRICING_BIBLE.md §3/§4.2/§8, BILLING_V2.md, BILLING_ARCHITECTURE.md,
TRIAL_SYSTEM.md, FULL_FREE_2026.md §4.2, COMMERCIAL_TERMS.md, docs/billing.md, docs/BUSINESS_MODEL.md) recebem
um cabeçalho **SUPERADO (v0.27.0, ADR-341)** apontando para este inventário e para `docs/ECONOMIC_MODEL.md`;
o conteúdo histórico fica, porque explica contratos e decisões anteriores. `MONETIZATION.md` §8 e
`PRICING_RECONCILIATION.md` ganham a linha da retirada da assinatura com o teste que a prova.

## 6. O que NÃO foi feito

* Nenhuma linha histórica de `invoices`, `platform_charges`, `billing_events`, `offer_acceptances` ou
  `free_periods` foi apagada ou reescrita.
* Nenhum valor de contrato foi inventado: a proposta de contrato exige valor e motivo de quem tem alçada.
* A regra `contract.platform_service_fee` continua **inativa** (carta amarela): a camada econômica é
  registrada e instruída, mas a cobrança própria só nasce com carta verde — como antes.
