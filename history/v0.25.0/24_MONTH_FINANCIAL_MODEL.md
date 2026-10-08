# MODELO FINANCEIRO DE 24 MESES — v0.21.0

**Pricing Version:** 2027.01 · **Início do horizonte:** janeiro de 2026

> **O que este documento é.** A estrutura do modelo, com o calendário de receita que decorre das
> regras comerciais já implementadas, e três cenários cujas **premissas de volume são declaradas,
> não apuradas**.
>
> **O que ele não é.** Uma projeção. O lado do custo está vazio (ver `UNIT_ECONOMICS.md` §2) e o
> volume de clientes é premissa do proprietário, não resultado de dado. Um modelo com receita
> calculada e custo inventado produz uma margem inventada — e margem inventada é o número que
> costuma ser citado.

---

## 1. O CALENDÁRIO DE RECEITA, QUE NÃO É PREMISSA

Isto decorre das regras já implementadas e **não depende de nenhuma suposição**:

| Mês | O que acontece | Receita de assinatura |
| --- | --- | ---: |
| jan–dez/2026 (meses 1–12) | FULL FREE 2026 | **R$ 0,00** |
| jan/2027 (mês 13) | tabela entra em vigor; assinaturas novas ganham 3 meses | **R$ 0,00** |
| fev/2027 (mês 14) | — | **R$ 0,00** |
| mar/2027 (mês 15) | — | **R$ 0,00** |
| abr/2027 (mês 16) | **primeira cobrança possível** (coorte de janeiro) | > 0 |
| mai–dez/2027 (17–24) | coortes seguintes entram a cada mês | crescente |

**A primeira receita da plataforma é no mês 16 de 24.** Qualquer modelo que fature antes disso está
contradizendo o produto.

Datas exatas por coorte (3 meses de calendário, `ends_at` exclusivo):

| Assinatura | Primeira cobrança |
| --- | --- |
| 01/01/2027 | 01/04/2027 |
| 01/02/2027 | 01/05/2027 |
| 15/02/2027 | 15/05/2027 |
| 28/02/2027 | 28/05/2027 |
| 31/03/2027 | 30/06/2027 |

---

## 2. A FÓRMULA

```
MRR(m) = Σ sobre coortes c com primeira_cobranca(c) ≤ m de
           assinaturas(c) × sobrevivencia(c, m) × preco_do_plano

sobrevivencia(c, m) = (1 − churn_mensal) ^ (m − primeira_cobranca(c))
```

Os preços estão no catálogo. `assinaturas(c)` e `churn_mensal` são **premissas**.

---

## 3. TRÊS CENÁRIOS — PREMISSAS, NÃO PREVISÕES

As premissas abaixo são **ilustrativas e não validadas**. Existem para mostrar a sensibilidade do
resultado, não para afirmar um futuro. Elas devem ser substituídas pelas do proprietário.

| Premissa | Conservador | Base | Agressivo |
| --- | ---: | ---: | ---: |
| Assinaturas pagas convertidas em jan/2027 | `[PREMISSA]` | `[PREMISSA]` | `[PREMISSA]` |
| Novas assinaturas por mês em 2027 | `[PREMISSA]` | `[PREMISSA]` | `[PREMISSA]` |
| Distribuição por plano | `[PREMISSA]` | `[PREMISSA]` | `[PREMISSA]` |
| Churn mensal | `[PREMISSA]` | `[PREMISSA]` | `[PREMISSA]` |
| Contratos ENTERPRISE/GOV | `[PREMISSA]` | `[PREMISSA]` | `[PREMISSA]` |

**Nenhum número foi inventado para preencher estas células.** A plataforma não tem base de conversão
(nunca cobrou), não tem churn (nunca teve assinatura paga) e não tem funil de vendas registrado.

### O que a sensibilidade já diz, sem premissa nenhuma

A diferença entre uma conversão para PRO e uma para BUSINESS é de **R$ 500/mês por cliente**
(R$ 6.000/ano). A diferença entre PROFESSIONAL PRO e FUNDER PRO é de **R$ 1.441/mês**. Em qualquer
cenário, o **mix de planos** domina o resultado mais do que o número de clientes — o que é um
argumento para instrumentar a conversão por plano antes de projetar volume.

---

## 4. CUSTO

`[PENDENTE]` em todas as linhas. Ver `UNIT_ECONOMICS.md` §2 para a lista e para como obter cada uma.

Consequência: **este modelo não produz margem, nem EBITDA, nem break-even.** Produz receita bruta
condicionada a premissas de volume.

---

## 5. CAIXA DURANTE A GRATUIDADE

Durante os meses 1 a 15, a receita de assinatura é zero por decisão comercial. O custo de operação
nesse período **não** é zero. Quanto ele é, está em `[PENDENTE]`.

Esta é a pergunta financeira mais importante do horizonte, e o modelo a deixa explicitamente em
aberto em vez de respondê-la com um número confortável.

---

## 6. COMO USAR ESTE DOCUMENTO

1. O proprietário substitui cada `[PREMISSA]` pelas suas;
2. A operação substitui cada `[PENDENTE]` por dado medido, à medida que existir;
3. O modelo passa a ser recalculável — e, a partir daí, discutível.

Enquanto houver `[PREMISSA]` e `[PENDENTE]`, o que este documento oferece é o **calendário de
receita** (§1), que é fato, e a **estrutura de cálculo** (§2), que é correta. O resto é trabalho que
ainda não foi feito, e dizer isso é mais útil do que preencher.
