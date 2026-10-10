# Cobertura dos 40 cenários de teste do pacote (PARTE XIV) — v0.34.0

> `✅` coberto por teste automatizado que roda na suíte (nome do teste); `🟡` coberto em parte (o que falta); `⛔` não coberto por
> dependência externa ou decisão (motivo). Invariantes financeiras ao fim. Nenhum teste simula provedor real: tudo é sandbox.

| # | Cenário | Estado | Teste / motivo |
|---|---|---|---|
| 1 | Doação confirmada por Pix | ✅ | `test_v0330_donations.test_03` |
| 2 | Pagamento de cartão confirmado | 🟡 | `method="card"` aceito; sandbox devolve `checkout_url`; confirmação pelo mesmo webhook (`test_03` cobre o caminho); cartão real depende do provedor |
| 3 | Pagamento pendente | ✅ | `test_v0340.test_01` (pendente não entra na barra) |
| 4 | Pagamento recusado | ✅ | eventos `payment.expired`/`checkout.canceled` → `expired`; decisão de risco `reject` → `cancelled` (`test_v0330.test_04`) |
| 5 | Webhook duplicado | ✅ | `test_v0330.test_03` (duplicado), `test_v0340.test_10` (6 entregas simultâneas → 1 confirmação) |
| 6 | Webhook fora de ordem | ✅ | estorno antes de confirmação → `ignored` com nota (`apply_provider_event`); liquidação antes de confirmação confirma e liquida (`test_v0340.test_03` usa `PAYMENT_RECEIVED` direto) |
| 7 | Assinatura inválida | ✅ | `test_v0330.test_03` (202, sem efeito) |
| 8 | Falha temporária do provedor | 🟡 | sandbox não falha; `provider_fee_unknown` (422) cobre tabela ausente; retentativa é do provedor (documentada na matriz) |
| 9 | Evento recebido com atraso | ✅ | mesmo caminho idempotente; `unreconciled_overdue` na conciliação (`test_v0340.test_08` cobre tipos) |
| 10 | Estorno total | ✅ | `test_v0330.test_06` |
| 11 | Estorno parcial | ✅ | `test_v0340.test_06` |
| 12 | Chargeback | ✅ | `test_v0340.test_12` |
| 13 | Tarifa divergente | ✅ | `fee_mismatch` na conciliação (`run_for_campaign`); snapshot com `fee_cents` em `test_v0340.test_08` |
| 14 | Split bem-sucedido | ⛔ | split recusado na configuração (ADR-375); depende de provedor e enquadramento |
| 15 | Split indisponível | ✅ | `test_v0330.test_09` (flag `SPLIT_ENABLED=true` recusa subir) |
| 16 | Beneficiário ainda não verificado | ✅ | `test_v0330.test_01` (publicar → 422 `beneficiary_not_verified`) |
| 17 | Falha de liquidação | 🟡 | liquidação só por evento; ausência aparece como `settled_cents = 0` e `settlement_partial` existe na fila; evento de falha de liquidação depende do provedor |
| 18 | Transferência parcial | 🟡 | `allocation_payouts.paid_cents` (v0.27.0) cobre repasse parcial de acordos; para doações, `settlement_partial` é tipo de exceção sem gerador automático |
| 19 | Receita devida, mas não recebida | ✅ | `test_v0340.test_04` (devida/faturada ≠ recebida; `revenue.received_cents = 0`) |
| 20 | Fatura paga parcialmente | ✅ | `test_v0340.test_04` (parcial não fecha; excesso recusado) |
| 21 | Cobrança vencida | ✅ | `test_v0340.test_04` (`mark-overdue`; nenhum bloqueio) |
| 22 | Campanha que atinge a meta | ✅ | `test_v0340.test_13` |
| 23 | Campanha que ultrapassa a meta | ✅ | `test_v0340.test_13` (continua aceitando; contingência declarada) |
| 24 | Campanha cancelada | ✅ | máquina de estados (`cancelled`); suspensão administrativa `test_v0330.test_11` |
| 25 | Doação recorrente | 🟡 | tabela, cancelamento pelo doador e flag recusada (`test_v0330.test_09`); cobrança recorrente depende de instrumento do provedor |
| 26 | Declaração de recurso externo | ✅ | `test_v0340.test_07` |
| 27 | Mesmo pagamento contabilizado duas vezes | ✅ | `test_v0330.test_03`, `test_v0340.test_10`, `duplicate_entry` na conciliação |
| 28 | Alterar valor financeiro pelo frontend | ✅ | `test_v0340.test_10` (campo extra → 422; estado só por webhook) |
| 29 | Painel financeiro de outra organização | ✅ | `test_v0330.test_05`, `test_v0340.test_07` (404) |
| 30 | Mudança de tarifa com operações antigas | ✅ | `test_v0340.test_09` |
| 31 | Valor zero, negativo ou fora dos limites | ✅ | `test_v0340.test_10` |
| 32 | Concorrência entre eventos simultâneos | ✅ | `test_v0340.test_10` (threads) |
| 33 | Falha no processamento da fila | ⛔ | não há fila própria: o webhook é processado na transação; a fila é do provedor (retentativas documentadas) |
| 34 | Divergência entre razão e provedor | ✅ | `test_v0340.test_08` |
| 35 | Reprocessamento após indisponibilidade | ✅ | reentrega do mesmo `event_id` é `duplicate`; evento novo aplica (`test_03` v0.33.0) |
| 36 | Recuperação de backup | ✅ | job `ensaio-restauracao` (v0.32.0, execução 37997867650) e `backup-restaurar` |
| 37 | Acesso indevido a dados pessoais | ✅ | `test_v0330.test_05` (anônimo), redação do bruto (`test_03`), RLS |
| 38 | Cancelamento de assinatura | ⛔ | não existe assinatura (ADR-341); recorrência de doação: cancelamento coberto por rota |
| 39 | Reembolso de serviço de marketplace | ⛔ | marketplace com `take_rate` recusado; reembolso é entre as partes (sem custódia) |
| 40 | Regressão de permissões e funcionalidades anteriores | ✅ | suíte completa (2.4 mil testes), matriz de autorização, telas no navegador |

## Invariantes financeiras (pacote §XIV) — onde cada uma é provada

| Invariante | Prova |
|---|---|
| Uma transação externa não gera duas contribuições por duplicidade de evento | UNIQUE `(provider,event_id)`; `test_v0340.test_10` |
| O mesmo evento reprocessado não duplica lançamentos | `test_v0330.test_03` |
| Estornos mantêm a trilha | `reversal_of`; `forbid_mutation`; `test_v0330.test_06`, `test_v0340.test_06` |
| Lançamentos obedecem ao equilíbrio | restrição diferida `donation_ledger_balanced`; `test_v0340.test_06` (toda txn soma zero) |
| Soma dos destinos = distribuição definida, ou diferença registrada | `_post_confirmation`; `fee_miscalculated`/`fee_mismatch` na conciliação |
| Pendente não aparece como liquidado disponível | `test_v0340.test_01` |
| Remuneração prevista não aparece como recebida | `test_v0340.test_02/04` |
| Nenhum usuário vê dados financeiros fora das permissões | RLS; `test_v0330.test_05`; `test_v0340.test_07/08` (403/404) |
| Tarifa nova não altera operação contratada | `test_v0340.test_09`; gatilho `remuneration_obligation_guard` |
| Arredondamento, mínimos, valores altos, centavos | `apply_bps` com `Decimal` (`half_even`); limites 100..100.000.000 centavos (`test_10`); R$ 30.000,00 → R$ 300,00 (`test_04`) |
