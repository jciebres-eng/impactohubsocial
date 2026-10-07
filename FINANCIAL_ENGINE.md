# Motor financeiro — CALCULA, INSTRUI, CONCILIA

> Documento da v0.22.0. Governado por `NON_CUSTODIAL_ARCHITECTURE.md` (ADR-284), que está **acima**
> deste: a plataforma não custodia, não repassa e não executa pagamento de terceiro.

## 0. A regra que define o motor

> *"Não implemente uma fintech dentro do IMPACTO só porque isso parece aumentar a monetização.
> Primeiro prove que a mesma receita e garantia operacional podem ser obtidas com uma arquitetura
> de software/orquestração muito mais simples."*

O motor financeiro desta versão é a resposta a essa exigência: o caminho mais simples que entrega
a mesma garantia operacional, com o dinheiro de terceiro fora da plataforma.

```
                 IMPACTO TRUST
       GOVERNANÇA · INTELIGÊNCIA · EXECUÇÃO
                      │
               FINANCIAL ENGINE
       ┌──────────────┼──────────────┐
   CALCULA         INSTRUI       CONCILIA
       └──────────────┼──────────────┘
             PAGAMENTOS EXTERNOS
      BENEFICIÁRIO        PROFISSIONAL
                EVIDÊNCIA → IMPACTO
```

| verbo | o que É | o que NÃO É |
| --- | --- | --- |
| **CALCULA** | taxa sobre valor de contrato, reconhecimento de receita por competência, rateio por centro de custo, orçado contra realizado | não debita, não credita conta de ninguém |
| **INSTRUI** | documento com valor, beneficiário, vencimento, referência e aprovação | não é transferência, não gera PIX, não movimenta conta |
| **CONCILIA** | compara o instruído com a evidência de pagamento e **aponta** divergência | não corrige, não compensa, não baixa automaticamente |

## 1. Contabilidade por competência

`chart_of_accounts` (43 contas, 5 naturezas), `cost_centers` (11), `accounting_periods`,
`accounting_entries`.

**Partida dobrada de verdade.** `post_batch()` recusa lote cujos débitos não igualam os créditos
(422 `batch_not_balanced`). Partida dobrada que aceita lote desequilibrado não é partida dobrada: é
duas colunas.

Três recusas no banco, por gatilho `accounting_entry_guard()`:

- conta **sintética** não recebe lançamento (lançar em conta de agrupamento faz o balancete contar
  duas vezes);
- conta **inativa** não recebe lançamento;
- competência **não aberta** não recebe lançamento.

`accounting_entries` é append-only (`forbid_mutation()`): não se altera nem se remove lançamento.
É o que faz dele contabilidade.

**Fechamento.** `close_period()` recusa fechar com lote desbalanceado (409 `unbalanced_batches`).
Fechar um mês que não fecha é publicar um número errado com carimbo de definitivo.

**Caixa não é competência.** `/v1/financeiro/summary` responde caixa (por `cash_date`);
`/v1/contabilidade/summary` responde competência. Os dois números são diferentes de propósito, e
cada tela diz qual dos dois está mostrando.

## 2. Despesa da própria plataforma

`platform_expenses`. Duas restrições de tabela, não de tela:

- `approved_by <> created_by` — quem registra não aprova;
- `(approved_by IS NULL) = (approved_at IS NULL)`, e estado `approved`/`scheduled`/`paid` exige
  aprovação, e `paid` exige `paid_on`.

Registrar uma despesa **abre automaticamente** um pedido de aprovação na faixa do valor. Registrar
não aprova e não paga.

## 3. Orçamento

`platform_budgets` (versionado, um aprovado por exercício) e `platform_budget_items` (mês × conta ×
centro de custo). O painel calcula orçado, realizado, desvio e percentual consumido, e destaca
linhas em 80% ou mais.

Sem orçamento aprovado, a tela diz: *"Orçado-vs-realizado sem orçado é só realizado."* Não devolve
zeros.

## 4. Instrução de pagamento

`payment_instructions`. Ciclo: `draft` → `pending_approval` → `approved` → `issued` → `executed` →
`reconciled`, com `cancelled` e `rejected`.

Três garantias no banco:

1. **Congelamento na emissão** (`instruction_frozen_after_issue()`): depois de emitida, valor,
   beneficiário, documento do beneficiário, moeda, referência e tipo não mudam. Para corrigir,
   cancela-se com motivo e emite-se outra — como se faz com documento que já saiu.
2. **Evidência obrigatória** para registrar execução. Marcar como executada sem evidência seria a
   plataforma afirmando um pagamento que ela não viu — e ela nunca vê, por desenho.
3. **Emissão exige aprovação concluída** na faixa do valor (409 `approval_required`, com quantas
   faltam e quais permissões servem, para a tela poder dizer "aguardando 2ª aprovação" em vez de um
   erro genérico).

Segregação de função pela porta da rota: `instruction.create` (papel `finance`) cria;
`instruction.approve` (papel `controller`) emite e registra execução.

## 5. Alçada por valor

Oito faixas vigentes:

| operação | faixa | assinaturas | permissões aceitas |
| --- | --- | --- | --- |
| instrução de pagamento | até R$ 1.000 | 1 | `finance.approve` |
| instrução de pagamento | R$ 1.000 – 10.000 | 2 | `finance.approve` + `accounting.close` |
| instrução de pagamento | acima de R$ 10.000 | 2 | `finance.approve` + `accounting.close` |
| despesa da plataforma | até R$ 500 | 1 | `finance.approve` |
| despesa da plataforma | R$ 500 – 10.000 | 1 | `finance.approve` |
| despesa da plataforma | acima de R$ 10.000 | 2 | `finance.approve` + `accounting.close` |
| estorno de cobrança | até R$ 200 | 1 | `billing.refund` |
| estorno de cobrança | acima de R$ 200 | 2 | `billing.refund` + `finance.approve` |

Os valores são dados em `approval_rules`: mudá-los é operação de governança, não implantação.
Detalhes do mecanismo em `AUTHORIZATION.md` §7.

## 6. Conciliação

`reconcile()` aponta, não corrige. Quatro conferências:

- instruções emitidas, vencidas e sem execução registrada;
- execuções sem evidência (**não deveria existir** — a restrição exige evidência; se aparecer, há
  caminho novo gravando sem ela);
- despesa paga sem lançamento contábil (saiu caixa e a competência não registrou);
- lotes que não fecham.

## 7. Métricas — cada número diz de onde veio

`economics/metrics.py`. Todo indicador carrega `source`, `calculation`, `period` e
`last_updated` — este último passou a existir na correção pós-auditoria: estava prometido aqui e
ausente da resposta, promessa escrita no lugar de dado.

E o que **não pode ser medido** responde `available: false` com o motivo, nunca zero. Zero parece
medição, e num painel executivo é a forma mais convincente de mentir. `null` não explica.

Hoje respondem **indisponíveis, com motivo**: churn, LTV, CAC, custo de IA (a tabela
`ai_price_table` está vazia — ver §9) e autonomia de caixa quando não há queima.

Duas correções pós-auditoria nesse ponto, porque a regra valia menos do que o texto dizia:

- o **custo de IA** respondia **zero, disponível**, com nota de procedência. A condição era
  `not (chamadas and sem_preco == chamadas)`: com zero chamadas o `and` curto-circuitava e o
  indicador saía disponível valendo zero. Pior, com dez chamadas das quais quatro sem preço, ele
  somava as seis precificadas e apresentava o total como apurado — custo **subestimado** com cara
  de medição. Agora é indisponível em ambos os casos, com o motivo dizendo qual dos dois;
- um indicador indisponível **sem motivo escrito** agora levanta erro na construção, onde é
  barato. `available: false` com `unavailable_reason: null` é o próprio "`null` não explica" que
  este módulo existe para recusar, e era o que `free_to_paid` devolvia sem organização ativa.

Respondem com valor: MRR, ARR, assinaturas ativas, receita bruta/deduções/líquida por competência,
entradas e saídas de caixa, despesa total e por centro de custo, GMV, conversão de teste para pago.

**MRR exclui assinatura com `provider = 'sandbox'`** — incluí-la faria um ambiente de testes inflar
a receita, e o cálculo publicado diz isso.

**GMV nunca é somado à receita.** GMV é dinheiro de terceiro; a receita da plataforma sobre o GMV é
**zero** e a tela diz por quê (§8). Somar os dois é o erro que infla avaliação de SaaS.

## 8. Take rate: calculado e não cobrável

`compute_marketplace_fee()` devolve `billable: false` em qualquer caso, com **dois motivos
diferentes**, e a distinção importa:

- **`percentage_not_declared`** — é o estado de hoje. A regra `marketplace.take_rate` existe em
  `monetization_rules` com `percentage = NULL`, `active = false` e `legal_status = refused`.
  **Não existe alíquota nenhuma declarada**, e a função devolve `fee_cents: null`: não há cálculo
  a fazer, e devolver um número aqui seria inventar a alíquota. Uma versão anterior deste documento
  afirmava que "a regra de 10% existe" — não existe, e o teste que devia travar isso conferia
  apenas `billable` e nunca olhava o valor. Auditoria independente apontou os dois.
- **`rule_inactive`** — quando houver alíquota declarada e a regra seguir desligada. Aí sim a
  função **calcula** (`fee_cents`) e continua recusando a cobrança.

A regra continua desligada por decisão registrada: cobrar percentual sobre contrato de terceiro
**sem contrato comercial assinado e sem nota fiscal própria** é receita inventada. Ver
`NON_CUSTODIAL_ARCHITECTURE.md` §4 e §7. Quando houver base contratual, o que muda é uma linha de
dado — não o motor.

## 9. Limitações desta versão, ditas como limitações

- **Nenhum provedor de pagamento em produção.** Não há PIX gerado, não há cartão, não há boleto. O
  gerador de PIX foi **deliberadamente removido** na v0.20.0: sem provedor, a única forma de chamá-lo
  seria passando valor inventado.
- **`ai_price_table` está vazia**, então o custo de IA responde indisponível em vez de zero. O
  consumo é medido (tokens, latência, provedor); o preço não foi declarado.
- **Não há rota de estorno.** A faixa de alçada de `billing_refund` está cadastrada em
  `approval_rules` (duas faixas) e **inerte**: nenhuma rota abre pedido com essa operação, porque
  nenhum provedor de pagamento está ligado e estornar o que não foi cobrado não existe. A faixa
  espera a rota; a alçada não precisa ser reimplantada quando ela chegar.
- **Nenhum provedor fiscal ligado**: não há emissão de NFS-e. O adaptador e o contrato existem.
- **Não há `payouts`, `split`, `recipient`, `wallet`, `escrow` nem saldo de terceiro** — nem código
  nem tabela. É verificado por teste: nenhuma tabela cujo nome contenha `wallet|payout|split|escrow|custod|repasse` ou termine em `_balance(s)`.
- **Investimentos** aparecem como patrimônio **próprio** da plataforma (contas 1.1.1 e 1.1.2). Não
  há, e não se pretende sem análise regulatória própria, oferta de investimento a cliente.
- **Projeção (30/90/365 dias)** e **drill-down navegável até o lançamento** não foram
  implementados. Há drill-down de um nível: o resumo aponta a tela que detalha.
- **Moeda** é `BRL` em coluna própria e todo valor é inteiro em centavos (`bigint`). Não há
  `float` em valor monetário. Não há conversão de moeda.

## 10. O que foi testado

`backend/tests/test_v0220_financial_engine.py` (34 testes). Entre eles: lote que não fecha é
recusado; lançamento é indelével; conta sintética, conta inativa e competência fechada recusam;
fechamento recusa lote torto; reconhecimento anual distribui 12 meses sem perder centavo; quem pede
não aprova; faixa de duas assinaturas recusa a mesma permissão duas vezes; uma recusa basta para
recusar; instrução congela depois de emitida (quatro colunas conferidas, cada uma em sua
transação); execução sem evidência é recusada; não existe tabela que guarde dinheiro de terceiro;
GMV não entra no cálculo da receita; e todo indicador declara fonte e cálculo — ou diz por que não
pôde ser medido.
