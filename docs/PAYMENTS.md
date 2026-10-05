# Pagamentos e cobrança (`services/billing.py`)

## Duas coisas diferentes
1. **Assinatura da própria plataforma** (planos pagos): implementada com adapters.
2. **Aportes de financiadores a projetos de OSC**: **não são processados pela plataforma** (ADR-003/022). São *registrados* (`commitments`): compromisso → desembolso informado pelo financiador → recebimento confirmado pela OSC. Triggers impedem que a mesma parte faça os dois lados e que a soma ultrapasse o orçamento. Isso evita atuar como instituição de pagamento/custódia e não cria “cotas” de valor mobiliário. Modelos formais de contribuição/cotas ficam para após parecer jurídico.

## Provedores de cobrança (`BILLING_PROVIDER`)
| Valor | Uso |
|---|---|
| `none` | tudo gratuito; checkout indisponível |
| `sandbox` | simula checkout, **sem cobrança real** (recusado em production; padrão em dev) |
| `stripe` | Checkout hospedado + webhook; preços por `STRIPE_PRICE_*` |
| `manual` | administrador registra assinatura/fatura/pagamento confirmado (sem emitir nota fiscal) |

## Garantias implementadas e testadas
Webhook com assinatura HMAC (tolerância 300 s) · idempotência por `event.id` (`billing_events`) · assinatura só muda por evento confiável do backend, nunca por “sucesso” do frontend · plano sem preço → 409 `price_not_defined` · downgrade não apaga dados (carência 60 dias) · nenhum dado de cartão armazenado · vouchers: HMAC, dupla aprovação, resgate transacional.
**Estados de pagamento:** subscriptions/invoices usam o ciclo do provedor (assinatura: `incomplete/trialing/active/past_due/canceled/expired`; fatura: `draft/open/paid/void/uncollectible`); **não há** máquina de estados CREATED→…→DISPUTED, reembolso/chargeback nem conciliação automática (RED).

## Pendências
Conta e homologação Stripe (modo de teste e produção) · preços · nota fiscal/contabilização · reembolso/chargeback/disputa · conciliação · meios locais (Pix/boleto) via provedor · exigência das lojas para venda dentro do app.
