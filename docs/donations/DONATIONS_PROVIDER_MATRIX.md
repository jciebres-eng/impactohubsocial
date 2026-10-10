# Provedores de pagamento para doações — matriz comparativa (v0.33.0)

Consultado em **2026-10-10** nas documentações oficiais (links abaixo). O que não está escrito na documentação pública
aparece como **não confirmado**: só o contrato, o sandbox real e o parecer jurídico fecham essas lacunas. Nenhum
provedor está contratado nem ligado ao produto. O único provedor em código é o `SandboxProvider` interno (ADR-372).

## Resumo

| Critério | Asaas | Mercado Pago | O que o IMPACTO faz hoje |
|---|---|---|---|
| Pix dinâmico (QR + copia-e-cola) | `POST /v3/payments` com `billingType: PIX`; `customer` é **obrigatório** no corpo | `POST /v1/orders` com `payment_method.id = pix` e `type = bank_transfer`; devolve `qr_code`, `qr_code_base64`, `ticket_url` | o sandbox devolve um código `PIX-SANDBOX-NAO-PAGAVEL|…`, nunca um Pix real |
| Dado do doador exigido pelo provedor | cliente cadastrado no Asaas (nome + CPF/CNPJ para emitir cobrança) → **implicação LGPD**: doação anônima precisa de solução contratual | `payer.email` obrigatório na ordem; identificação (CPF) aparece só no formulário de exemplo | guarda e-mail cifrado só se o doador quiser comprovante; nome público opcional |
| Expiração do Pix | configurável na cobrança (não confirmado o mínimo) | `expiration_time` ISO 8601, padrão 24 h, entre 30 min e 30 dias | 30 min no sandbox |
| Webhook — autenticação | cabeçalho `asaas-access-token` com o `authToken` configurado no webhook | cabeçalho `x-signature` (`ts=…,v1=…`), validado com a chave secreta da aplicação + `x-request-id` + `data.id` | HMAC-SHA256 em `x-impacto-signature` com `payment_webhook_secret` |
| Webhook — idempotência | `id` único por evento; entrega **at least once** (o mesmo evento pode chegar mais de uma vez) | reenvia a cada 15 min até confirmação; não documenta chave de idempotência do evento (usar `data.id` + tipo + `x-request-id`) | `UNIQUE (provider, event_id)` em `payment_provider_events` |
| Webhook — ordem | modo sequencial preserva ordem; modo não sequencial não garante | não documentado | estado da doação é máquina de estados; reversão sem confirmação prévia é ignorada e registrada |
| Webhook — resposta esperada | **só HTTP 200** conta como sucesso (201/204 são falha); fila pausa após **15 falhas consecutivas**; eventos guardados 14 dias | HTTP 200 ou 201; espera **22 s** | responde 200 em evento aplicado/duplicado, 202 em assinatura inválida, 404 sem segredo configurado |
| Split / repasse | parâmetro `split` (array) na cobrança — `walletId` e base do cálculo **não confirmados** na página de referência | marketplace via `application_fee` (não verificado nesta rodada) | `split_enabled = false`; `validate()` recusa `true` |
| Recorrência | assinaturas (`/v3/subscriptions`) com eventos próprios | assinaturas (preapproval) — não verificado nesta rodada | `recurring_donations_enabled = false`; cancelamento pelo doador sempre disponível |
| Sandbox | `https://api-sandbox.asaas.com` | credenciais de teste de usuário produtivo; URL de webhook separada para teste | sandbox interno sem rede |
| Tarifa Pix | não está na documentação técnica (tabela comercial) | idem | `provider_fee_schedules` com 0 bps para o sandbox; tarifa real entra por contrato |
| KYB do beneficiário | onboarding da conta Asaas (documentos da organização) | conta Mercado Pago da organização | `org_kyb_verifications` registra o estado; quem verifica e com quais documentos depende do provedor e do parecer |

## O que ainda falta para ligar um provedor real (bloqueios)

1. **Contrato** com o provedor em nome da organização responsável pela plataforma, com tarifa Pix por escrito.
2. **Modelo de titularidade**: a cobrança é emitida pela conta do **beneficiário** (não custodial, preferido pelo ADR-284)
   ou pela conta da plataforma com split (a plataforma passa a intermediar valores → avaliar enquadramento).
   O código só suporta o primeiro modelo por decisão.
3. **Parecer jurídico** sobre: taxa de serviço (1 %) e fundo (≤ 4 %) — hoje INATIVOS; recibo de doação × dedutibilidade;
   LGPD para dados do doador exigidos pelo provedor; termos da campanha.
4. **Adaptador** do provedor escolhido (`PaymentProvider` Protocol em `impacto/services/donations.py`), testado contra o
   sandbox oficial com eventos reais gravados — não contra o sandbox interno.
5. **Variáveis**: segredo do webhook e chave da API só no Railway; `live_payment_provider_enabled` continua recusado pelo
   `validate()` até a ADR que autorizar remover a trava.

## Fontes (consultadas em 2026-10-10)

- Asaas — receber eventos no endpoint de webhook: https://docs.asaas.com/docs/receba-eventos-do-asaas-no-seu-endpoint-de-webhook
- Asaas — fila pausada / penalização: https://docs.asaas.com/docs/fila-pausada
- Asaas — criar cobrança (`POST /v3/payments`): https://docs.asaas.com/reference/criar-nova-cobranca
- Asaas — criar webhook pela API: https://docs.asaas.com/docs/criar-novo-webhook-pela-api
- Mercado Pago — webhooks (assinatura `x-signature`, reenvio a cada 15 min, 22 s): https://www.mercadopago.com.br/developers/pt/docs/your-integrations/notifications/webhooks
- Mercado Pago — Pix via Orders API: https://www.mercadopago.com.br/developers/pt/docs/checkout-api-orders/payment-integration/websites/pix
