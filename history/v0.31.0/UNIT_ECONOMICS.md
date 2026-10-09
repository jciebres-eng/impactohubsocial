# UNIT ECONOMICS — v0.21.0

**Pricing Version:** 2027.01

> **Leia isto primeiro.** Este documento é um **modelo**, não um resultado. O lado da receita está
> preenchido porque os preços foram decididos e estão no catálogo. O lado do custo **não está**, e
> não foi estimado: a plataforma não tem um mês de operação paga, não tem fatura de provedor de
> pagamento, não tem custo medido de IA por organização e não tem histórico de suporte.
>
> Preencher esses campos com números plausíveis produziria um documento que **parece** uma análise
> e funciona como uma invenção — e alguém o citaria numa decisão de investimento. Os campos
> pendentes estão marcados `[PENDENTE]` e nomeiam quem pode respondê-los.

---

## 1. RECEITA POR ASSINATURA — CONHECIDA

Valores da Pricing Version 2027.01, líquidos de nada (antes de tributos, taxa de pagamento e
inadimplência).

| Plano | MRR | ARR (12×) | ARR anual contratado | Desconto anual |
| --- | ---: | ---: | ---: | ---: |
| PROFESSIONAL PRO | R$ 49,00 | R$ 588,00 | — | — |
| PRO | R$ 299,00 | R$ 3.588,00 | R$ 2.990,00 | 16,7% |
| BUSINESS | R$ 799,00 | R$ 9.588,00 | R$ 7.990,00 | 16,7% |
| FUNDER PRO | R$ 1.490,00 | R$ 17.880,00 | — | — |
| ENTERPRISE | ≥ R$ 2.500,00 | ≥ R$ 30.000,00 | por proposta | por proposta |
| GOV | ≥ R$ 3.500,00 | ≥ R$ 42.000,00 | por contrato | por contrato |

### Receita transacional

**R$ 0,00.** Take rate (10%), success fee (2–3%) e transaction fee (1–3%) estão declarados e
**inativos**, recusados pelo banco enquanto valer a ADR-022. Qualquer modelo que os inclua está
modelando um produto diferente do que existe.

---

## 2. CUSTO POR ORGANIZAÇÃO — PENDENTE

| Componente | Valor | Como obter |
| --- | --- | --- |
| Infraestrutura (banco, aplicação, armazenamento) | `[PENDENTE]` | fatura do provedor ÷ organizações ativas |
| IA por organização | `[PENDENTE]` | `ai_price_table` está **vazia**; a tabela existe e nunca foi preenchida com preço de provedor |
| Taxa do meio de pagamento | `[PENDENTE]` | contrato com o provedor — não há contrato assinado |
| Tributos sobre a receita | `[PENDENTE]` | enquadramento fiscal — `tax_behavior` está `unspecified` |
| Suporte humano | `[PENDENTE]` | horas por organização × custo/hora |
| Aquisição (CAC) | `[PENDENTE]` | gasto de marketing e vendas ÷ clientes novos |

A plataforma **mede** consumo de IA (`ai_usage`, com `cost_status` em `no_price_table` ou
`estimated`) e já reconhece que não tem preço: o estado `no_price_table` existe justamente para não
registrar um custo inventado.

---

## 3. AS FÓRMULAS

```
MRR            = Σ (assinaturas ativas × preço mensal do plano)
ARR            = MRR × 12
Margem bruta   = (MRR − custo de servir) ÷ MRR
LTV            = (MRR por cliente × margem bruta) ÷ churn mensal
Payback (meses)= CAC ÷ (MRR por cliente × margem bruta)
```

**Nenhuma delas é calculável hoje**: todas dependem de pelo menos um `[PENDENTE]` da §2, e `churn`
exige um mês de operação paga que ainda não aconteceu.

---

## 4. O QUE O PRODUTO JÁ SABE MEDIR

O que falta é **dado de operação**, não instrumentação. Estas peças existem e funcionam:

| Pergunta | Onde a resposta vai estar |
| --- | --- |
| Quantas assinaturas ativas, por plano? | `subscriptions` |
| Qual preço cada organização aceitou, e quando? | `subscription_prices` (congelado no aceite) |
| Quanto cada organização consumiu no período? | `usage_counters` |
| Quanto foi efetivamente cobrado? | `platform_charges` (`is_simulated = false`) |
| Quem está gratuito, até quando e por quê? | `free_periods` |
| Quanto custou cada chamada de IA? | `ai_usage` + `ai_price_table` (**esta precisa ser preenchida**) |

---

## 5. EFEITO DA GRATUIDADE DE 2026 E DOS 3 MESES DE 2027

| Período | Receita de assinatura |
| --- | ---: |
| até 31/12/2026 | **R$ 0,00** — FULL FREE 2026 |
| 01/01/2027 a 31/03/2027 | **R$ 0,00** para quem assinar em janeiro (3 meses de calendário) |
| a partir do 4º mês de cada assinatura | preço de tabela |

A primeira receita possível de uma assinatura criada em 01/01/2027 é em **01/04/2027**. Uma criada
em 15/02/2027 fatura pela primeira vez em **15/05/2027**.

Isso não é um detalhe de calendário: é o desenho da entrada de caixa, e qualquer projeção que
comece a faturar antes dessas datas está errada.

---

## 6. O QUE PRECISA ACONTECER PARA ESTE DOCUMENTO TER NÚMEROS

1. Preencher `ai_price_table` com o preço real do provedor de IA;
2. Contratar o provedor de pagamento e registrar a taxa efetiva;
3. Definir o enquadramento fiscal e fechar `tax_behavior`;
4. Operar **um mês** com cobrança real, para ter custo de infraestrutura por organização;
5. Operar **três meses**, para ter a primeira leitura de churn.

Até lá, qualquer unit economics desta plataforma é opinião.
