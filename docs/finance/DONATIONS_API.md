# API, webhooks e eventos do ecossistema financeiro (v0.34.0)

> Gerado a partir de `impacto/api/donation_routes.py` (o OpenAPI completo está em `docs/openapi.json` / `docs/API.md`).
> Quem pode: `público` (sem sessão, com limite por IP), `pessoa com conta`, `organização` (papel na organização ativa, RLS),
> permissões nomeadas de equipe (`compliance.*`, `finance.*`; `finance.approve` e `finance.write` exigem confirmação de identidade).

## Operações

| Método | Caminho | Quem | O que faz |
|---|---|---|---|
| `GET` | `/v1/public/donation-campaigns/{slug}` | público | QR Code da campanha: aponta para a URL HTTPS canônica (nunca para um payload Pix estático) |
| `GET` | `/v1/public/donation-campaigns/{slug}/qr.svg` | público |  |
| `POST` | `/v1/public/donation-campaigns/{slug}/donate` | público | Inicia uma doação: cria a cobrança no provedor e devolve o Pix copia-e-cola/checkout com o preço total — não confirma nada |
| `GET` | `/v1/public/donations/{donation_id}` | público | Comprovante da doação confirmada (não é recibo dedutível nem nota fiscal) |
| `GET` | `/v1/public/donations/{donation_id}/receipt` | público | Webhook do provedor: assinatura conferida, evento gravado uma vez, estado e razão atualizados numa transação |
| `POST` | `/v1/webhooks/donations/{provider}` | público |  |
| `POST` | `/v1/campaigns/{campaign_id}/submit` | organização (gestor) | Publica a campanha aprovada (exige beneficiário verificado; o banco recusa sem isso) |
| `POST` | `/v1/campaigns/{campaign_id}/publish` | organização (gestor) | Regenera QR/link (versão nova; a anterior deixa de ser a canônica) — para QR comprometido ou substituído |
| `POST` | `/v1/campaigns/{campaign_id}/rotate-qr` | organização (gestor) | Prestação de contas: totais conciliados (com definição de cada número), doações, gastos declarados × validados, casos de risco |
| `GET` | `/v1/campaigns/{campaign_id}/accountability` | organização (leitura) | Declara um gasto da campanha (declarado ≠ validado; documento vira evidência) |
| `POST` | `/v1/campaigns/{campaign_id}/expenses` | organização (gestor) |  |
| `POST` | `/v1/campaigns/{campaign_id}/updates` | organização (gestor) | Minhas doações (com conta) e acordos recorrentes |
| `GET` | `/v1/me/donations` | pessoa com conta |  |
| `POST` | `/v1/me/recurring-donations/{agreement_id}/cancel` | pessoa com conta |  |
| `GET` | `/v1/admin/donation-campaigns` | compliance.read |  |
| `POST` | `/v1/admin/donation-campaigns/{campaign_id}/review` | compliance.write | Tira do ar (em análise) ou devolve ao ar uma campanha publicada, com justificativa |
| `POST` | `/v1/admin/donation-campaigns/{campaign_id}/suspend` | compliance.write |  |
| `POST` | `/v1/admin/beneficiaries/{org_id}/verification` | compliance.write |  |
| `GET` | `/v1/admin/donation-risk-cases` | compliance.read |  |
| `POST` | `/v1/admin/donation-risk-cases/{case_id}/decide` | compliance.write |  |
| `POST` | `/v1/admin/donation-campaigns/{campaign_id}/reconcile` | finance.write | Razão de conciliação da campanha (partidas dobradas, append-only) e totais com definição |
| `GET` | `/v1/admin/donation-ledger/{campaign_id}` | finance.read |  |
| `POST` | `/v1/campaigns/{campaign_id}/external-resources` | organização (gestor) |  |
| `POST` | `/v1/public/donation-campaigns/{slug}/pledge` | pessoa com conta |  |
| `POST` | `/v1/me/pledges/{pledge_id}/cancel` | pessoa com conta | Liga um compromisso à doação CONFIRMADA que o cumpriu |
| `POST` | `/v1/campaigns/{campaign_id}/pledges/{pledge_id}/fulfill` | organização (gestor) | Painel do financiador: doações e compromissos feitos em nome da organização |
| `GET` | `/v1/org/contributions` | organização (leitura) | Obrigações de remuneração da organização, política vigente, franquia e avisos — nada aqui bloqueia nada |
| `GET` | `/v1/org/remuneration` | organização (leitura) | Contesta uma obrigação (fica em disputa até decisão registrada) |
| `POST` | `/v1/org/remuneration/{obligation_id}/dispute` | organização (gestor) | Registra ciência de um aviso |
| `POST` | `/v1/org/remuneration/notices/{notice_id}/ack` | organização (leitura) | Obrigações por estado (previsto × devido × faturado × recebido × liquidado) — nunca somadas num número só |
| `GET` | `/v1/admin/remuneration` | finance.read |  |
| `POST` | `/v1/admin/remuneration/orgs/{org_id}/evaluate` | finance.write | Envia (registra) um aviso prévio da política à organização |
| `POST` | `/v1/admin/remuneration/orgs/{org_id}/notices` | finance.write |  |
| `POST` | `/v1/admin/remuneration/invoice` | finance.write | Marca como cobrada (enviada ao pagador) |
| `POST` | `/v1/admin/remuneration/{obligation_id}/charged` | finance.write | Registra pagamento RECEBIDO (parcial ou total) com referência |
| `POST` | `/v1/admin/remuneration/{obligation_id}/receipt` | finance.write |  |
| `POST` | `/v1/admin/remuneration/{obligation_id}/settle` | finance.approve | Decide uma disputa (manter, dispensar, isentar) com justificativa |
| `POST` | `/v1/admin/remuneration/{obligation_id}/decide` | finance.approve |  |
| `POST` | `/v1/admin/remuneration/{obligation_id}/waive` | finance.approve |  |
| `POST` | `/v1/admin/remuneration/{obligation_id}/authorize-public` | finance.approve |  |
| `POST` | `/v1/admin/remuneration/mark-overdue` | finance.write |  |
| `POST` | `/v1/admin/reconciliation/campaigns/{campaign_id}/run` | finance.write | Fila de exceções de conciliação |
| `GET` | `/v1/admin/reconciliation/exceptions` | finance.read | Assume uma exceção |
| `POST` | `/v1/admin/reconciliation/exceptions/{exception_id}/assign` | finance.write | Resolve ou descarta uma exceção com justificativa (fica no histórico) |
| `POST` | `/v1/admin/reconciliation/exceptions/{exception_id}/resolve` | finance.write | Histórico de uma exceção |
| `GET` | `/v1/admin/reconciliation/exceptions/{exception_id}/history` | finance.read |  |

## Webhook do provedor — `POST /v1/webhooks/donations/{provider}`

- Corpo JSON com `event_id` (único por provedor), `type`, `charge_id`, `amount_cents`, `currency` e o bruto do provedor.
- Assinatura obrigatória: sandbox usa HMAC-SHA256 do corpo com `PAYMENT_WEBHOOK_SECRET` no cabeçalho `X-Impacto-Signature`;
  um adaptador real traduz o cabeçalho do provedor (`asaas-access-token`, `x-signature` ts/v1) e DEVE validar janela temporal.
- Respostas: `404` sem segredo configurado (nada é aceito); `202` assinatura inválida (gravado como rejeitado, sem efeito);
  `200` evento aplicado ou duplicado (`duplicate: true`).
- Idempotência: `UNIQUE (provider, event_id)`; concorrência de entregas iguais produz uma única confirmação (`test_v0340.test_10`).
- Dados pessoais no bruto são redigidos antes de guardar (cpf, cpfCnpj, email, phone, ip, card, cardNumber, document, name, payer).

### Tipos de evento reconhecidos e efeito

| Tipo (neutro · Asaas) | Efeito |
|---|---|
| `payment.confirmed` · `PAYMENT_CONFIRMED` · `charge.paid` | confirma (valor e moeda conferidos; divergência → `under_review` + caso de risco); partidas dobradas; obrigação CALCULADA; comprovante |
| `payment.settled` · `PAYMENT_RECEIVED` · `charge.settled` | liquidação (`settled_at`); se ainda não confirmada, confirma e liquida |
| `payment.partially_refunded` · `PAYMENT_PARTIALLY_REFUNDED` | reversão parcial (`refunded_cents`); acima do pago → caso de risco |
| `payment.refunded` · `PAYMENT_REFUNDED` · `charge.refunded` | reversão total (ou do restante); comprovante anulado; obrigação estornada/em disputa |
| `payment.chargeback` · `PAYMENT_CHARGEBACK_REQUESTED` | idem, estado `chargeback` |
| `payment.expired` · `PAYMENT_OVERDUE` · `PAYMENT_DELETED` · `checkout.canceled` | expira cobrança aguardando pagamento |
| outros | gravados e ignorados (`tipo de evento sem efeito`) |

## Eventos internos (trilha de auditoria)

`donation.started`, `donation.risk_decided`, `donation.reconciled`, `donation.recurring_cancelled`, `campaign.submitted/reviewed/published/suspended/reinstated/qr_rotated/expense_declared`,
`beneficiary.verification`, `external_resource.declared`, `pledge.created/cancelled/fulfilled`, `remuneration.evaluated/notice_sent/invoiced/charged/received/settled/disputed/dispute_decided/waived/public_fee_authorized/overdue_marked`,
`reconciliation.run/assigned/resolved`. Históricos só-inserção: `remuneration_obligation_events`, `reconciliation_exception_events`, `donation_ledger_entries`.

## Snapshot do provedor para conciliação

`POST /v1/admin/reconciliation/campaigns/{id}/run` aceita `charges: [{charge_id, amount_cents, fee_cents?, confirmed, reversed, settled?}]`.
Vazio → o sandbox deriva o snapshot dos próprios eventos assinados e aplicados. Um adaptador real implementa `snapshot(campaign)` consultando a API do provedor.

## Variáveis de ambiente

Nenhuma nova é obrigatória na v0.34.0. Continuam: `PAYMENT_WEBHOOK_SECRET`, `DONATIONS_ENABLED`, `CAMPAIGN_PUBLICATION_ENABLED` e as travas
`LIVE_PAYMENT_PROVIDER_ENABLED`, `SPLIT_ENABLED`, `RECURRING_DONATIONS_ENABLED`, `RISK_HOLD_ENABLED` (recusadas se `true`). Ver `.env.example`.
