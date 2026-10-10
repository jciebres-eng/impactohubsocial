# BENCHMARKS DE PREÇO — v0.21.0

**Fonte:** `config/price_benchmark.json` · versão `price_benchmark@1.0` · consultado em 2026-10-06

> **O que é.** O que o MERCADO cobra, consultado em fontes públicas.
> **O que não é.** O que a Impacto Trust cobra. Essa decisão está em `PRICING_BIBLE.md`.
>
> Nenhuma linha de código lê este arquivo para preencher o catálogo, e há teste de
> arquitetura que recusa um módulo que leia os dois. Um benchmark que vira preço por
> conveniência produz um preço que **ninguém decidiu**: ele apenas apareceu, copiado de
> empresas com outro produto, outro custo e outro cliente.

---

## 1. PREÇOS PUBLICADOS PELOS CONCORRENTES

| Produto | Plano | Preço | Unidade | Período | Categoria |
| --- | --- | ---: | --- | --- | --- |
| Asana | Starter | USD 10.99 | por usuário/mês | anual | project_management_saas |
| monday.com | Work Management Standard | USD 12.00 | por assento/mês | anual ou mensal | project_management_saas |
| monday.com | Work Management Pro | USD 19.00 | por assento/mês | anual ou mensal | project_management_saas |
| HubSpot Sales Hub | Starter | USD 20.00 | por assento/mês | mensal | crm_b2b |
| Asana | Advanced | USD 24.99 | por usuário/mês | anual | project_management_saas |
| monday.com CRM | Pro | USD 28.00 | por assento/mês | anual ou mensal | crm_b2b |
| Salesforce Nonprofit Cloud | Sales & Service Core | USD 70.00 | por usuário/mês | anual | nonprofit_management |
| Salesforce Nonprofit Cloud | Sales & Service Advanced | USD 125.00 | por usuário/mês | anual | nonprofit_management |
| Salesforce Nonprofit Cloud | Sales Max / Service Max | USD 285.00 | por usuário/mês | anual | nonprofit_management |

**9 produtos com preço publicado.** Faixa: US$ 10.99 a US$ 285.00. Mediana: US$ 24.99.

---

## 2. PRODUTOS QUE NÃO PUBLICAM PREÇO

Não publicar preço é um **fato sobre o mercado**, não uma lacuna do levantamento: no segmento
institucional e governamental, o preço por proposta é a norma. Registrar o motivo evita que
alguém trate a ausência como descuido.

| Produto | Por que não há preço |
| --- | --- |
| Submittable | O fornecedor NÃO publica preço: a página direciona para contato comercial. |
| Workiva | O fornecedor NÃO publica preço de tabela. Os números que circulam vêm de agregadores de terceiros e são estimativas — não foram usados aqui. |
| Pipefy | Declara cobrança por usuário e NÃO publica o valor: a página direciona para contato comercial. |

---

## 3. COMO A TABELA DA IMPACTO SE SITUA

Comparação **informativa**. As unidades são diferentes — a maioria dos concorrentes cobra
por usuário/mês, e a Impacto Trust cobra por organização —, então o número por si não
compara.

| Plano Impacto (2027.01) | Mensal | Observação |
| --- | ---: | --- |
| PROFESSIONAL PRO | R$ 49,00 | por organização, não por usuário |
| PRO | R$ 299,00 | inclui múltiplos assentos |
| BUSINESS | R$ 799,00 | inclui múltiplos assentos |
| FUNDER PRO | R$ 1.490,00 | inclui múltiplos assentos |
| ENTERPRISE | a partir de R$ 2.500,00 | sob proposta |
| GOV | a partir de R$ 3.500,00 | sob proposta |

**A comparação direta não é possível** sem fixar número de usuários por organização, e esse
dado não existe (a plataforma nunca operou com cobrança). Converter dólar em real para
comparar acrescentaria uma segunda suposição — a taxa de câmbio de qual data? — sobre uma
primeira que já não se sustenta.

---

## 4. SITUAÇÃO DO LEVANTAMENTO

`PRICE_FINALIZATION_REQUIRED`: **True** no levantamento da v0.20.0.

Na v0.20.0 essa marca significava que **nenhum preço havia sido decidido**. Na v0.21.0 o
proprietário decidiu, e a decisão está na `PRICING_BIBLE.md` — não neste arquivo. A marca
continua `true` porque ela descreve o levantamento, não o produto: ela diz que este benchmark
**não** é uma decisão de preço, e isso continua verdadeiro.

### O que falta para o levantamento ser mais útil

1. Concorrentes **brasileiros** diretos — o levantamento é majoritariamente norte-americano;
2. Preço por organização, e não por usuário, onde existir;
3. Data de consulta por linha, para que uma linha velha se identifique sozinha.
