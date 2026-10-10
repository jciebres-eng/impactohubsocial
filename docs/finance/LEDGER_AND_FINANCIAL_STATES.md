# Razão e estados financeiros (v0.34.0)

> Documenta o que `donation_ledger_entries`, `donations`, `campaigns`, `remuneration_obligations` e `reconciliation_exceptions`
> fazem hoje. O razão operacional do IMPACTO **não é conta bancária, garantia de depósito, custódia regulada nem prova de
> liquidação bancária** — é o espelho auditável do que o provedor confirmou (pacote §5.1).

## 1. Razão de doações (`donation_ledger_entries`)

- **Só inserção** (`forbid_mutation`): lançamento confirmado nunca é apagado nem reescrito; correção é lançamento novo
  (`reversal_of` aponta para o original).
- **Partidas dobradas** com restrição diferida: cada `txn_id` soma zero (D − C) no COMMIT, senão a transação inteira falha.
- Valores em **centavos inteiros**; percentuais em pontos-base com `Decimal` (`apply_bps`) — nunca ponto flutuante.
- Contas: `donor_payment` (C: o que o doador pagou), `beneficiary_receivable` (D: o que o provedor deve ao beneficiário),
  `provider_fee` (D), `platform_fee_accrued` (D: taxa CALCULADA — devida só por obrigação), `beneficiary_fund` (D: destinação
  da organização), `refund`/`chargeback` (D: reversões).
- Cada linha carrega: `donation_id`, `campaign_id`, `txn_id`, `source_event_id` (o evento assinado do provedor que a originou),
  `is_simulated` (derivado do provedor), `reversal_of`, nota.
- Confirmação: `C donor_payment (total) = D receivable + D provider_fee + D platform_fee_accrued + D fund`.
- Estorno total: espelho com `reversal_of`. **Estorno parcial**: `D refund (valor) = C receivable (valor)`; tarifa/taxa/fundo
  ficam como lançados — quem os reverte é o contrato do provedor, e a divergência aparece na conciliação (`fee_mismatch`).

## 2. Estados de uma doação (`donations.status` + colunas de data)

| Estado | Como se chega | Entra na barra pública? |
|---|---|---|
| `created` | `POST …/donate` | não |
| `awaiting_payment` | cobrança criada no provedor (Pix/checkout devolvido) | **não** (mostrado como "pendente") |
| `under_review` | evento com valor/moeda divergente, ou estorno maior que o pago → caso de risco | não |
| `confirmed` | evento ASSINADO do provedor (`payment.confirmed`/`PAYMENT_CONFIRMED`/`PAYMENT_RECEIVED`), idempotente por `event_id`, valor conferido | sim |
| `settled_at` (coluna) | evento de liquidação (`payment.settled`/`PAYMENT_RECEIVED`): o dinheiro está disponível ao beneficiário segundo o provedor | mostrado à parte ("já liquidado"); é a base da franquia |
| `reconciled` | conciliação bateu razão × sistema × snapshot do provedor | sim |
| `partially_refunded` | estorno parcial; `refunded_cents` acumula | sim, com o valor abatido |
| `refund_pending` → `refunded` | estorno total (ou parcial que completou o total) | não (sai da contagem) |
| `chargeback` | contestação do pagador | não |
| `expired` / `failed` / `cancelled` | prazo, falha do provedor, cancelamento/decisão de risco | não |

Gatilho `donation_state_guard`: só estas transições; valor/provedor/cobrança/campanha não mudam depois de confirmada; liquidação
exige confirmação e não se desfaz.

## 3. Política de contagem (pacote §4.2)

Uma doação conta **uma vez** por cobrança do provedor; estornada total sai da contagem; parcial continua contada com o valor
abatido; pendente, em análise e cancelada não contam. A página pública explica isto (`counting_policy`) e mostra a data da
última atualização financeira válida (`last_financial_update_at` = último lançamento do razão).

## 4. Totais — nunca somados num número só (`campaign_totals`)

`gross_confirmed_cents`, `reversed_cents`, `net_after_reversals_cents`, `settled_cents`, `pending_cents`, `under_review_cents`,
`provider_fees_cents`, `platform_fee_accrued_cents`, `beneficiary_fund_cents`, `beneficiary_net_estimated_cents`,
`expenses_declared_cents` / `expenses_validated_cents`, `pledged_cents` (compromissos — não é dinheiro),
`external_declared_cents` (declarado fora da plataforma — não conferido). Cada um com definição no próprio JSON.

## 5. Estados de uma campanha

`draft → pending_review → approved → published → (paused | target_reached | ended | under_review) → closed`; `rejected`,
`cancelled`, `refunding` são desvios. Publicar exige revisor ≠ criador, termos aceitos e beneficiário verificado.
Campanha com `funding_source` público/misto exige `public_instrument_ref`.

## 6. Obrigações de remuneração

Ver `FREE_UNTIL_VALUE_POLICY.md` §2. Separação patrimonial (pacote §5.2): dinheiro do projeto (razão de doações, conta do
beneficiário no provedor) × remuneração devida (`remuneration_obligations`) × tarifas do provedor (`provider_fee`) × reservas
autorizadas (`beneficiary_fund`, destinação do beneficiário) × bloqueado/contestado (`under_review`, casos de risco) × recursos
próprios do SaaS (`platform_charges` recebidas) × a receber (`due/invoiced/charged`) × estornado (`reversed`).

## 7. Exceções de conciliação (`reconciliation_exceptions`)

`provider_only`, `system_only`, `amount_mismatch`, `fee_mismatch`, `reversal_missing`, `duplicate_entry`, `fee_miscalculated`,
`settlement_partial`, `unreconciled_overdue` — com prioridade, responsável, resolução justificada e histórico só-inserção.
Índice único por fato aberto: reexecutar a conciliação não duplica. Só vira `reconciled` a doação cujo evento assinado bate com
o snapshot em valor e estado.

## 8. O que NÃO existe (de propósito)

Coluna de saldo; carteira; retenção de repasse; split; desconto automático de taxa; rendimento sobre reserva; bloqueio por
inadimplência. Testes: `test_v0330_donations.test_10`, `test_v0340_financial_ecosystem.test_11`, `test_v0220_financial_engine`.
