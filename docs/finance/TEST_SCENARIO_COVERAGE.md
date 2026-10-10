# Cobertura dos 40 cenários de teste do pacote (PARTE XIV) — v0.34.0

> `✅` coberto por teste automatizado que roda na suíte (nome do teste); `(simulado)`/`(sandbox)` = a condição que depende do
> provedor real é injetada só no teste e o teste diz isso; `🟡` coberto em parte; `⛔` não coberto. Desde a etapa E6, **os 40
> cenários têm teste**; nenhum teste finge provedor real. Invariantes financeiras ao fim.

| # | Cenário | Estado | Teste / motivo |
|---|---|---|---|
| 1 | Doação confirmada por Pix | ✅ | `test_v0330_donations.test_03` |
| 2 | Pagamento de cartão confirmado | ✅ | `test_v0340_open_scenarios.test_02` — **achado da E6:** faltava a tabela de tarifa do sandbox para cartão, e toda doação por cartão era recusada (`provider_fee_unknown`); a nota anterior desta linha ("cartão aceito") estava errada. Cartão real depende do provedor |
| 3 | Pagamento pendente | ✅ | `test_v0340.test_01` (pendente não entra na barra) |
| 4 | Pagamento recusado | ✅ | eventos `payment.expired`/`checkout.canceled` → `expired`; decisão de risco `reject` → `cancelled` (`test_v0330.test_04`) |
| 5 | Webhook duplicado | ✅ | `test_v0330.test_03` (duplicado), `test_v0340.test_10` (6 entregas simultâneas → 1 confirmação) |
| 6 | Webhook fora de ordem | ✅ | estorno antes de confirmação → `ignored` com nota (`apply_provider_event`); liquidação antes de confirmação confirma e liquida (`test_v0340.test_03` usa `PAYMENT_RECEIVED` direto) |
| 7 | Assinatura inválida | ✅ | `test_v0330.test_03` (202, sem efeito) |
| 8 | Falha temporária do provedor | ✅ | `test_v0340_open_scenarios.test_08` — falha injetada só no teste: 503 `provider_unavailable`, nada gravado, a mesma chave de idempotência repete com sucesso |
| 9 | Evento recebido com atraso | ✅ | mesmo caminho idempotente; `unreconciled_overdue` na conciliação (`test_v0340.test_08` cobre tipos) |
| 10 | Estorno total | ✅ | `test_v0330.test_06` |
| 11 | Estorno parcial | ✅ | `test_v0340.test_06` |
| 12 | Chargeback | ✅ | `test_v0340.test_12` |
| 13 | Tarifa divergente | ✅ | `fee_mismatch` na conciliação (`run_for_campaign`); snapshot com `fee_cents` em `test_v0340.test_08` |
| 14 | Split bem-sucedido | ✅ (simulado) | `test_v0340_open_scenarios.test_14_15` — só para a **contribuição voluntária do doador** (ADR-384; nada sai da doação); trava `SPLIT_ENABLED` ligada e provedor que divide **só no teste**; obrigação nasce recebida com referência `split:<evento>`; razão equilibrado. Split real depende de contrato e homologação |
| 15 | Split indisponível | ✅ | `test_v0330.test_09` (flag recusa subir) e `test_v0340_open_scenarios.test_14_15` (sem split, a contribuição vira obrigação devida da organização, faturada à parte — nunca desconto) |
| 16 | Beneficiário ainda não verificado | ✅ | `test_v0330.test_01` (publicar → 422 `beneficiary_not_verified`) |
| 17 | Falha de liquidação | ✅ | `test_v0340_open_scenarios.test_17_18` — evento `payment.settlement_failed` → exceção `settlement_failed`, pagamento continua confirmado, nada liquidado |
| 18 | Transferência parcial | ✅ | `test_v0340_open_scenarios.test_17_18` — liquidação ACUMULADA: 4.000 de 10.000 é parcial (exceção `settlement_partial` com esperado × observado), 6.000 depois completa; acordos de repasse parcial seguem em `allocation_payouts.paid_cents` (v0.27.0) |
| 19 | Receita devida, mas não recebida | ✅ | `test_v0340.test_04` (devida/faturada ≠ recebida; `revenue.received_cents = 0`) |
| 20 | Fatura paga parcialmente | ✅ | `test_v0340.test_04` (parcial não fecha; excesso recusado) |
| 21 | Cobrança vencida | ✅ | `test_v0340.test_04` (`mark-overdue`; nenhum bloqueio) |
| 22 | Campanha que atinge a meta | ✅ | `test_v0340.test_13` |
| 23 | Campanha que ultrapassa a meta | ✅ | `test_v0340.test_13` (continua aceitando; contingência declarada) |
| 24 | Campanha cancelada | ✅ | máquina de estados (`cancelled`); suspensão administrativa `test_v0330.test_11` |
| 25 | Doação recorrente | ✅ (sandbox) | `test_v0340_open_scenarios.test_25_38` — autorização (consentimento por hash) ≠ tentativa (rotina `financial_ops`) ≠ confirmado (evento) ≠ falha (expirada); pausa após 3 falhas; recebido = só o confirmado. Desligada na configuração até instrumento homologado no provedor |
| 26 | Declaração de recurso externo | ✅ | `test_v0340.test_07` |
| 27 | Mesmo pagamento contabilizado duas vezes | ✅ | `test_v0330.test_03`, `test_v0340.test_10`, `duplicate_entry` na conciliação |
| 28 | Alterar valor financeiro pelo frontend | ✅ | `test_v0340.test_10` (campo extra → 422; estado só por webhook) |
| 29 | Painel financeiro de outra organização | ✅ | `test_v0330.test_05`, `test_v0340.test_07` (404) |
| 30 | Mudança de tarifa com operações antigas | ✅ | `test_v0340.test_09` |
| 31 | Valor zero, negativo ou fora dos limites | ✅ | `test_v0340.test_10` |
| 32 | Concorrência entre eventos simultâneos | ✅ | `test_v0340.test_10` (threads) |
| 33 | Falha no processamento da fila | ✅ | `test_v0340_open_scenarios.test_33_35` e `test_33b` — webhook em duas fases: o evento é gravado antes; erro interno → `failed` + exceção `event_processing_failed` + 500 (o provedor reenvia); nada lançado pela metade |
| 34 | Divergência entre razão e provedor | ✅ | `test_v0340.test_08` |
| 35 | Reprocessamento após indisponibilidade | ✅ | `test_v0340_open_scenarios.test_33_35` — a rotina `financial_ops` reaplica eventos `failed`/`received` e resolve a exceção; reentrega posterior é `duplicate` |
| 36 | Recuperação de backup | ✅ | job `ensaio-restauracao` (v0.32.0, execução 37997867650) e `backup-restaurar` |
| 37 | Acesso indevido a dados pessoais | ✅ | `test_v0330.test_05` (anônimo), redação do bruto (`test_03`), RLS |
| 38 | Cancelamento de assinatura | ✅ (recorrência) | Assinatura de plano não existe (ADR-341). O único instrumento recorrente do produto é a doação mensal: cancelamento pelo doador, sempre possível, sem nova tentativa (`test_v0340_open_scenarios.test_25_38`); outra pessoa recebe 404 |
| 39 | Reembolso de serviço de marketplace | ✅ (parte da plataforma) | `test_v0340_open_scenarios.test_39` — reembolso integral do que a plataforma recebeu vira `reversed` com referência no histórico (segregado: `finance.approve`; parcial é ajuste); devolução da cobrança pelo provedor também reverte; a organização não move a fatura da plataforma (403 `platform_invoice`). O serviço em si é pago entre as partes, sem custódia (ADR-284) |
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
