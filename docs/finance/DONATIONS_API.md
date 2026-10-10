# API, webhooks e eventos do ecossistema financeiro (v0.34.0)

> Gerado a partir de `impacto/api/donation_routes.py` (o OpenAPI completo está em `docs/openapi.json` / `docs/API.md`).
> Quem pode: `público` (sem sessão, com limite por IP), `pessoa com conta`, `organização` (papel na organização ativa, RLS),
> permissões nomeadas de equipe (`compliance.*`, `finance.*`; `finance.approve` e `finance.write` exigem confirmação de identidade).

## Operações

| Método | Caminho | Quem | O que faz |
|---|---|---|---|
| `GET` | `/v1/public/donation-campaigns/{slug}` | público | Campanha de arrecadação pública: beneficiário verificado, meta, totais confirmados, custos, atualizações e gastos declarados |
| `GET` | `/v1/public/donation-campaigns/{slug}/qr.svg` | público | QR Code da campanha: aponta para a URL HTTPS canônica (nunca para um payload Pix estático) |
| `POST` | `/v1/public/donation-campaigns/{slug}/donate` | público | Inicia uma doação: cria a cobrança no provedor e devolve o Pix copia-e-cola/checkout com o preço total — não confirma nada |
| `GET` | `/v1/public/donations/{donation_id}` | público | Estado da doação (pendente/confirmada/expirada), como o provedor informou; nunca muda pelo navegador |
| `GET` | `/v1/public/donations/{donation_id}/receipt` | público | Comprovante da doação confirmada (não é recibo dedutível nem nota fiscal) |
| `POST` | `/v1/webhooks/donations/{provider}` | público | Webhook do provedor: assinatura conferida; evento gravado uma vez (fase 1) e aplicado travando a linha do evento (fase 2); falha interna fica registrada e é reprocessada |
| `POST` | `/v1/campaigns/{campaign_id}/submit` | organização (gestor) | Envia a campanha para revisão (aceita os termos de campanha na versão vigente) |
| `POST` | `/v1/campaigns/{campaign_id}/publish` | organização (gestor) | Publica a campanha aprovada (exige beneficiário verificado; o banco recusa sem isso) |
| `POST` | `/v1/campaigns/{campaign_id}/rotate-qr` | organização (gestor) | Regenera QR/link (versão nova; a anterior deixa de ser a canônica) — para QR comprometido ou substituído |
| `GET` | `/v1/campaigns/{campaign_id}/accountability` | organização (leitura) | Prestação de contas: totais conciliados (com definição de cada número), doações, gastos declarados × validados, casos de risco |
| `POST` | `/v1/campaigns/{campaign_id}/expenses` | organização (gestor) | Declara um gasto da campanha (declarado ≠ validado; documento vira evidência) |
| `POST` | `/v1/campaigns/{campaign_id}/updates` | organização (gestor) | Atualização pública da campanha, com referências a evidências |
| `GET` | `/v1/me/donations` | pessoa com conta | Minhas doações (com conta) e acordos recorrentes |
| `POST` | `/v1/public/donation-campaigns/{slug}/recurring` | pessoa com conta | Autoriza doação recorrente (consentimento guardado por hash). Desligada até instrumento homologado no provedor |
| `POST` | `/v1/me/recurring-donations/{agreement_id}/cancel` | pessoa com conta | Cancela um acordo de doação recorrente (sempre possível pelo doador) |
| `GET` | `/v1/admin/donation-campaigns` | compliance.read | Campanhas aguardando revisão e campanhas publicadas |
| `POST` | `/v1/admin/donation-campaigns/{campaign_id}/review` | compliance.write | Aprova ou rejeita a campanha com justificativa (quem criou não revisa) |
| `POST` | `/v1/admin/donation-campaigns/{campaign_id}/suspend` | compliance.write | Tira do ar (em análise) ou devolve ao ar uma campanha publicada, com justificativa |
| `POST` | `/v1/admin/beneficiaries/{org_id}/verification` | compliance.write | Registra o estado da verificação do beneficiário (KYB): quem verifica e com que documentos depende do provedor e do parecer |
| `POST` | `/v1/admin/beneficiaries/{org_id}/verification/{verification_id}/confirm` | compliance.write | Segunda pessoa da equipe confirma a verificação do beneficiário (quatro olhos, conferido pelo banco) |
| `GET` | `/v1/admin/donation-risk-cases` | compliance.read | Casos de risco abertos (revisão humana) |
| `POST` | `/v1/admin/donation-risk-cases/{case_id}/decide` | compliance.write | Decide um caso de risco com justificativa; fica na trilha |
| `POST` | `/v1/admin/donation-risk-cases/{case_id}/assign` | compliance.write | Assume a revisão de um caso de risco (revisor atribuído fica no caso) |
| `GET` | `/v1/campaigns/{campaign_id}/risk-cases` | organização (gestor) | Decisões de revisão sobre doações desta campanha (o que foi decidido e por quê) — base para recurso |
| `POST` | `/v1/campaigns/{campaign_id}/risk-cases/{case_id}/appeal` | organização (gestor) | Recurso da organização contra uma decisão de revisão (decidido por outra pessoa da equipe) |
| `POST` | `/v1/admin/donation-campaigns/{campaign_id}/reconcile` | finance.write | Conciliação da campanha (atalho da v0.33.0): mesma regra da execução com fila de exceções — sandbox contra os eventos assinados; provedor real exige extrato |
| `GET` | `/v1/admin/donation-ledger/{campaign_id}` | finance.read | Razão de conciliação da campanha (partidas dobradas, append-only) e totais com definição |
| `POST` | `/v1/campaigns/{campaign_id}/external-resources` | organização (gestor) | Declara recurso recebido FORA da plataforma (entra na prestação de contas; nunca no razão nem na barra) |
| `POST` | `/v1/public/donation-campaigns/{slug}/pledge` | pessoa com conta | Registra um compromisso de doação futura (não é doação, não é dinheiro) |
| `POST` | `/v1/me/pledges/{pledge_id}/cancel` | pessoa com conta | Cancela o próprio compromisso |
| `POST` | `/v1/campaigns/{campaign_id}/pledges/{pledge_id}/fulfill` | organização (gestor) | Liga um compromisso à doação CONFIRMADA que o cumpriu |
| `GET` | `/v1/org/contributions` | organização (leitura) | Painel do financiador: doações e compromissos feitos em nome da organização |
| `GET` | `/v1/org/remuneration` | organização (leitura) | Obrigações de remuneração da organização, política vigente, franquia e avisos — nada aqui bloqueia nada |
| `POST` | `/v1/org/remuneration/{obligation_id}/dispute` | organização (gestor) | Contesta uma obrigação (fica em disputa até decisão registrada) |
| `POST` | `/v1/org/remuneration/notices/{notice_id}/ack` | organização (leitura) | Registra ciência de um aviso |
| `GET` | `/v1/admin/remuneration` | finance.read | Obrigações por estado (previsto × devido × faturado × recebido × liquidado) — nunca somadas num número só |
| `POST` | `/v1/admin/remuneration/orgs/{org_id}/evaluate` | finance.write | Aplica a política 'gratuito até gerar valor' à organização: o que virou devido e por que o resto não virou |
| `POST` | `/v1/admin/remuneration/orgs/{org_id}/notices` | finance.write | Envia (registra) um aviso prévio da política à organização |
| `POST` | `/v1/admin/remuneration/invoice` | finance.write | Fatura obrigações DEVIDAS numa cobrança própria da plataforma (nunca desconto de doação) |
| `POST` | `/v1/admin/remuneration/{obligation_id}/charged` | finance.write | Marca como cobrada (enviada ao pagador) |
| `POST` | `/v1/admin/remuneration/{obligation_id}/receipt` | finance.write | Registra pagamento RECEBIDO (parcial ou total) com referência |
| `POST` | `/v1/admin/remuneration/{obligation_id}/refund` | finance.approve | Reembolso integral do que a plataforma recebeu (ex.: serviço cancelado) — a obrigação vira estornada; segregado |
| `POST` | `/v1/admin/remuneration/{obligation_id}/settle` | finance.approve | Marca como LIQUIDADA (conciliada com extrato) — segregado: exige finance.approve |
| `POST` | `/v1/admin/remuneration/{obligation_id}/decide` | finance.approve | Decide uma disputa (manter, dispensar, isentar) com justificativa |
| `POST` | `/v1/admin/remuneration/{obligation_id}/waive` | finance.approve | Dispensa uma obrigação com justificativa registrada |
| `POST` | `/v1/admin/remuneration/{obligation_id}/authorize-public` | finance.approve | Recurso público: registra instrumento e autorização que tornam a taxa elegível (ADR-379) |
| `POST` | `/v1/admin/remuneration/mark-overdue` | finance.write | Marca vencidas as faturadas além do prazo (rotina) |
| `POST` | `/v1/admin/reconciliation/campaigns/{campaign_id}/run` | finance.write | Executa a conciliação da campanha contra o snapshot do provedor (sandbox: derivado dos eventos assinados) e abre exceções |
| `POST` | `/v1/admin/reconciliation/runs/{run_id}/approve` | finance.approve | Segunda pessoa aprova o extrato manual: reexecuta com o mesmo extrato (hash conferido) e só então concilia |
| `GET` | `/v1/admin/reconciliation/exceptions` | finance.read | Fila de exceções de conciliação |
| `POST` | `/v1/admin/reconciliation/exceptions/{exception_id}/assign` | finance.write | Assume uma exceção |
| `POST` | `/v1/admin/reconciliation/exceptions/{exception_id}/resolve` | finance.write | Resolve ou descarta uma exceção com justificativa (fica no histórico) |
| `GET` | `/v1/admin/reconciliation/exceptions/{exception_id}/history` | finance.read | Histórico de uma exceção |

## Webhook do provedor — `POST /v1/webhooks/donations/{provider}`

- Corpo JSON com `event_id` (único por provedor), `type`, `charge_id`, `amount_cents`, `currency` e o bruto do provedor.
- Assinatura obrigatória: sandbox usa HMAC-SHA256 do corpo com `PAYMENT_WEBHOOK_SECRET` no cabeçalho `X-Impacto-Signature`;
  um adaptador real traduz o cabeçalho do provedor (`asaas-access-token`, `x-signature` ts/v1) e DEVE validar janela temporal.
- Respostas: `404` sem segredo configurado (nada é aceito); `202` assinatura inválida (gravado como rejeitado, sem efeito);
  `200` evento aplicado ou duplicado (`duplicate: true`); **`500` com `{"status":"failed","retry":true}`** quando o evento foi
  gravado mas a aplicação falhou (E6) — o provedor reenvia e a rotina `financial_ops` reaplica.
- **Duas fases (E6, ADR-384):** (1) gravar o evento numa transação própria; (2) aplicar travando a linha do evento. Reentrega de
  evento ainda `received`/`failed` é reaplicada; de evento `applied`/`ignored` é `duplicate`.
- Idempotência: `UNIQUE (provider, event_id)`; concorrência de entregas iguais produz uma única confirmação (`test_v0340.test_10`).
- Dados pessoais no bruto são redigidos antes de guardar (cpf, cpfCnpj, email, phone, ip, card, cardNumber, document, name, payer).

### Tipos de evento reconhecidos e efeito

| Tipo (neutro · Asaas) | Efeito |
|---|---|
| `payment.confirmed` · `PAYMENT_CONFIRMED` · `charge.paid` | confirma (valor e moeda conferidos; divergência → `under_review` + caso de risco); partidas dobradas; obrigação CALCULADA; comprovante |
| `payment.settled` · `PAYMENT_RECEIVED` · `charge.settled` | liquidação ACUMULADA (`settled_cents` opcional no corpo; sem valor = total esperado); parcial → exceção `settlement_partial`; se ainda não confirmada, confirma e liquida |
| `payment.settlement_failed` · `settlement.failed` · `TRANSFER_FAILED` | exceção `settlement_failed`; o pagamento continua confirmado (E6) |
| `split: [{receiver:"platform", amount_cents, status:"done"}]` no evento de confirmação | se a doação tinha contribuição dividida, a obrigação da contribuição nasce RECEBIDA com referência `split:<event_id>` (E6) |
| `payment.partially_refunded` · `PAYMENT_PARTIALLY_REFUNDED` | reversão parcial (`refunded_cents`); acima do pago → caso de risco |
| `payment.refunded` · `PAYMENT_REFUNDED` · `charge.refunded` | reversão total (ou do restante); comprovante anulado; obrigação estornada/em disputa |
| `payment.chargeback` · `PAYMENT_CHARGEBACK_REQUESTED` | idem, estado `chargeback` |
| `payment.expired` · `PAYMENT_OVERDUE` · `PAYMENT_DELETED` · `checkout.canceled` | expira cobrança aguardando pagamento |
| outros | gravados e ignorados (`tipo de evento sem efeito`) |

## Eventos internos (trilha de auditoria)

`donation.started`, `donation.risk_decided`, `donation.reconciled`, `donation.recurring_authorized`, `donation.recurring_cancelled`, `remuneration.refunded`, `campaign.submitted/reviewed/published/suspended/reinstated/qr_rotated/expense_declared`,
`beneficiary.verification`, `external_resource.declared`, `pledge.created/cancelled/fulfilled`, `remuneration.evaluated/notice_sent/invoiced/charged/received/settled/disputed/dispute_decided/waived/public_fee_authorized/overdue_marked`,
`reconciliation.run/assigned/resolved`. Históricos só-inserção: `remuneration_obligation_events`, `reconciliation_exception_events`, `donation_ledger_entries`.

## Operações novas da etapa E6

| Método e rota | Quem | O que faz |
|---|---|---|
| `POST /v1/public/donation-campaigns/{slug}/donate` (campo novo `platform_contribution_cents`) | qualquer pessoa | contribuição voluntária à plataforma, 0 por padrão; só aceita com a regra ativa (`contribution_unavailable`) e até o menor entre o valor doado e R$ 500 (`contribution_above_cap`) |
| `POST /v1/public/donation-campaigns/{slug}/recurring` | pessoa com conta | autoriza doação mensal com o texto de consentimento (guardado por hash); `503 recurring_disabled` enquanto a trava estiver desligada |
| `POST /v1/admin/remuneration/{id}/refund` | `finance.approve` | reembolso integral do que a plataforma recebeu; parcial é ajuste (`partial_refund`) |
| `POST /v1/payments/charges/{id}/transition` (regra nova) | organização | recusa (403 `platform_invoice`) mover a fatura de remuneração da plataforma |
| rotina `financial_ops` (worker) | sistema | reprocessa eventos, marca vencidas, concilia campanhas com movimento em 7 dias, cria tentativas de recorrência (se ligada) |

## Snapshot do provedor para conciliação

`POST /v1/admin/reconciliation/campaigns/{id}/run` aceita `charges: [{charge_id, amount_cents, fee_cents?, confirmed, reversed, settled?}]`.
Vazio → o sandbox deriva o snapshot dos próprios eventos assinados e aplicados. Um adaptador real implementa `snapshot(campaign)` consultando a API do provedor.

## Variáveis de ambiente

Nenhuma nova é obrigatória na v0.34.0. Continuam: `PAYMENT_WEBHOOK_SECRET`, `DONATIONS_ENABLED`, `CAMPAIGN_PUBLICATION_ENABLED` e as travas
`LIVE_PAYMENT_PROVIDER_ENABLED`, `SPLIT_ENABLED`, `RECURRING_DONATIONS_ENABLED`, `RISK_HOLD_ENABLED` (recusadas se `true`). Ver `.env.example`.
