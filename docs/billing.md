# Monetização e cobrança (v0.11.0)

Estende a arquitetura de billing já existente (`plans`, `subscriptions`, `invoices`, `billing_events`, `vouchers`, `entitlement_grants`, `EntitlementService`); **não há segunda arquitetura**.
Autoridade financeira = **backend + Stripe (webhooks)**. O cliente envia apenas `plan_key`, `interval` e `voucher`; preço, desconto, trial e direitos são sempre calculados no servidor.

> **Estado honesto.** Tudo abaixo foi testado com PostgreSQL real e um **dublê do Stripe** (nenhuma chamada real, nenhuma credencial). Nada foi exercitado contra a API do Stripe.
> **Preços não estão definidos** (`plan_prices.amount_cents = NULL`): sem preço, a contratação online é recusada. Nenhum valor, price ID ou chave foi inventado.

## Níveis (tiers) e função central de direitos
`FREE` · `PLUS` · `PREMIUM` (= "FULL") · `GOV` (institucional, contrato próprio — não é "premium com outro nome"). `plans.tier` + `config/plans.json` (`plans@1.1`).
`EntitlementService.effective()` (`services/entitlements.py`) é o único ponto: une plano pago, **trial**, licenças (grants não revogados) e convênios; features/limites mais favoráveis; devolve `tier`, `tier_label`, `trial`.
`get_entitlements(...)` e `has_access(...)` são os atalhos. **A divisão de recursos entre PLUS e PREMIUM é HIPÓTESE a validar com o produto.** Plano nunca influencia match/busca/ranking (teste de arquitetura).

## Trial de 14 dias FULL (por organização)
- Inicia no cadastro (`auth.register` → `monetization.start_trial`), **sem cartão**, plano FULL do tipo da organização; governo não recebe trial automático. `TRIAL_AUTO_START`/`TRIAL_DAYS`.
- Tabela `org_trials` (PK `org_id` = no máximo um trial por organização). Administração pode conceder trial a quem ainda não teve (motivo + auditoria).
- **Sem cobrança antes do fim.** Ao assinar durante o trial, o Checkout recebe `subscription_data[trial_end]` = fim do trial; a primeira cobrança ocorre só então.
  O Checkout do Stripe exige um mínimo (~48 h, constante `STRIPE_TRIAL_MIN`, **não verificado contra a API real**); se faltar menos, o trial é estendido o mínimo — nunca se cobra antes.
- **Cancelar no trial**: acesso FULL permanece até o fim, nenhuma cobrança, depois FREE. **Cancelar assinatura paga**: acesso até o fim do período pago (`cancel_at_period_end`), depois FREE. Dados e histórico financeiro nunca são apagados.
- Anti-abuso com minimização: `trial_claims` guarda só **HMAC** do e-mail normalizado (remove pontos/`+tag` do Gmail) e do CNPJ; nada em claro; retenção 24 meses (job). Alias do mesmo e-mail/CNPJ não ganha novo trial.
- Avisos (notificações in-app, sem repetição — `billing_notices`): dias 1, 7, 11, 13, 14, fim do trial, conversão, falha, cancelamento. **Não há envio de e-mail** dos avisos (só in-app).

## Estados da assinatura
`FREE` (sem assinatura) · `TRIALING` · `ACTIVE` · `PAST_DUE` · `CANCELED` · `INCOMPLETE` · `EXPIRED` (mais `payment_issue`: `payment_failed` | `action_required`). Uma única assinatura vigente por organização (índice único parcial).
Falha de pagamento **não corta o acesso de imediato** nem apaga dados; o usuário é orientado a atualizar o pagamento no portal.

## Cobrança mensal/anual
`plan_prices(plan_key, interval, amount_cents)`; `annual_savings` calcula a economia **real** (12×mensal − anual); sem os dois preços não há economia exibida. Price IDs: `STRIPE_PRICE_<PLAN>` (mensal), `_MONTH`, `_YEAR`.

## Stripe
- Checkout hospedado (`POST /v1/billing/checkout`), portal de cobrança (`POST /v1/billing/portal`: método de pagamento/faturas — a plataforma **não armazena dados de cartão**), cancelar/reativar, `change-plan` (upgrade/downgrade com `create_prorations`, sincronizado com o provedor).
- Webhook `POST /v1/billing/webhooks/stripe`: assinatura HMAC (`t=…,v1=…`, tolerância 300 s), **idempotente** por `event.id`, **tolerante a ordem** (`event.created` × `last_event_at`).
  Eventos tratados: `checkout.session.completed`, `customer.subscription.created/updated/deleted/trial_will_end`, `invoice.paid/payment_failed/finalized/payment_action_required`. `payment_intent.*` e `invoice.created` são ignorados (redundantes).

## Vouchers, licenças e convênios
- Vouchers (lote com quatro olhos): licença de plano, recurso, período gratuito, **percentual**, **valor fixo**, 100% (vira licença), permanente (sem duração), por plano e por organização. Desconto parcial fica `pending_discount` até o checkout; **um único desconto** (o maior) — não acumula.
- Licenças gratuitas (`entitlement_grants`) com origem `voucher|admin|license|partner|convention|gov|promotion`, motivo, revogáveis (`revoked_at/by/reason`); revogação mantém histórico.
- Convênios/GOV (`agreements`, `agreement_members`): código + período + vagas + plano e/ou desconto; domínio de e-mail **só restringe** quem entra (e-mail verificado) e **nunca autentica sozinho**; ativação por segundo administrador; respostas genéricas a códigos inválidos.
- Admin (MFA, motivo, auditoria): vouchers, convênios, conceder/revogar licença, conceder trial, preço do plano, visão de cobrança por organização.

## Segurança e LGPD
RLS em todas as tabelas novas; `org_trials`/`entitlement_grants` protegidas por gatilho (`billing_guard`) além do RLS; organização não escreve plano/assinatura/trial/licença; `agreements` e `trial_claims` invisíveis a organizações; rotas de checkout/cancelar/trocar exigem `owner`; limites de taxa.

## Configuração externa pendente (ver `PRODUCTION_READINESS.md`)
Conta Stripe + produtos/preços (definir os valores) · `STRIPE_SECRET_KEY`/`STRIPE_WEBHOOK_SECRET` · endpoint do webhook · Billing Portal configurado · homologação em modo de teste · e-mail transacional dos avisos · nota fiscal · textos legais (termos de assinatura, reembolso) e RIPD revisados por jurídico.

## Testes
`backend/tests/test_v0110_monetization.py` (34 testes: trial, cancelamento dia 1/13, FREE após trial, tiers, vouchers, anti-abuso, webhooks duplicados/inválidos/fora de ordem, upgrade/downgrade, falha de pagamento, portal, convênios, licenças, isolamento entre organizações).
