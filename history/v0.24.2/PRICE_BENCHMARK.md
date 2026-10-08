# Benchmark de preço — Impacto Trust

> **Isto é referência consultada, não preço.** Gerado a partir de `config/price_benchmark.json`,
> lido na API em `GET /v1/admin/price-benchmark`. `PRICE_FINALIZATION_REQUIRED: true`.

## O que foi feito

§47–48 e §89 pedem pesquisa web de preços de produtos comparáveis, com registro de **SOURCE, DATE,
PRODUCT, PLAN, PRICE, CURRENCY e FEATURES**, tratando o resultado como **BENCHMARK** e não como
preço final.

Cada linha da tabela foi lida **na página de preço do próprio fornecedor**, em 6 de outubro de 2026.
Agregador de preços de terceiro não foi usado como fonte: o número que eles publicam costuma ser
estimativa, e estimativa de terceiro apresentada como preço é exatamente o tipo de dado que esta
plataforma recusa em todo o resto.

## O que a pesquisa encontrou

**Faixa publicada:** de US$ 10,99 a US$ 285 por usuário/mês. Mediana das linhas publicadas: US$ 24,99.

| Categoria | Produto | Plano | Preço | Fonte |
|---|---|---|---|---|
| nonprofit management | Salesforce Nonprofit Cloud | Sales & Service Core | US$ 70/usuário/mês (anual) | [salesforce.com](https://www.salesforce.com/nonprofit/pricing/) |
| nonprofit management | Salesforce Nonprofit Cloud | Sales & Service Advanced | US$ 125/usuário/mês (anual) | [salesforce.com](https://www.salesforce.com/nonprofit/pricing/) |
| nonprofit management | Salesforce Nonprofit Cloud | Sales/Service Max | US$ 285/usuário/mês (anual) | [salesforce.com](https://www.salesforce.com/nonprofit/pricing/) |
| project management | Asana | Starter | US$ 10,99/usuário/mês (anual) | [asana.com](https://asana.com/pricing) |
| project management | Asana | Advanced | US$ 24,99/usuário/mês (anual) | [asana.com](https://asana.com/pricing) |
| project management | monday.com | Work Mgmt Standard | US$ 12/assento/mês | [monday.com](https://monday.com/pricing) |
| project management | monday.com | Work Mgmt Pro | US$ 19/assento/mês | [monday.com](https://monday.com/pricing) |
| CRM B2B | monday.com CRM | Pro | US$ 28/assento/mês | [monday.com](https://monday.com/pricing) |
| CRM B2B | HubSpot Sales Hub | Starter | US$ 20/assento/mês | [hubspot.com](https://www.hubspot.com/pricing/crm) |
| grant management | Submittable | — | **não publica** | [submittable.com](https://www.submittable.com/pricing/) |
| ESG software | Workiva | — | **não publica** | [workiva.com](https://www.workiva.com/) |
| SaaS brasileiro | Pipefy | Business/Enterprise | **não publica** (declara cobrança por usuário) | [pipefy.com](https://www.pipefy.com/pricing/) |

## Quatro conclusões, e nenhuma delas é um preço

1. **Um terço dos fornecedores pesquisados não publica preço algum** — inclusive os dois mais
   próximos do que a Impacto Trust faz: gestão de editais e relato ESG. Isso é informação sobre o
   mercado, não lacuna da pesquisa. Num setor em que comprador e vendedor negociam caso a caso,
   publicar preço é uma escolha, e a maioria dos fornecedores de nicho não a faz.
2. **Nenhum comparável cobra pelo que esta plataforma faz.** Todos cobram por ASSENTO. Nenhum cobra
   por organização atendida, por projeto acompanhado ou por evidência verificada. A comparação por
   assento serve de ordem de grandeza, não de modelo — a estrutura de monetização da Impacto Trust
   é outra (ver `MONETIZATION.md`).
3. **Preço publicado é preço de LISTA.** Desconto por volume, por setor sem fins lucrativos e por
   contrato plurianual é regra no mercado e não aparece em nenhuma destas páginas. O Salesforce, por
   exemplo, mantém um programa de doação de licenças para organizações sem fins lucrativos que não
   está refletido nos valores acima.
4. **Nenhum comparável internacional publica em reais.** Converter exigiria escolher uma taxa e uma
   data, e o resultado pareceria mais preciso do que é. Por isso não há nenhum valor em BRL nesta
   tabela, e há teste que impede que apareça.

## O que continua pendente

`config/plans.json` segue com **preço nulo** em todos os planos pagos, exibidos como "sob consulta".
A cobrança real continua exigindo provedor homologado (flag `billing_live`).

**A decisão de preço é do proprietário da plataforma.** Esta tabela existe para que ela seja tomada
com a referência do mercado à vista, e para que fique registrado o que foi consultado e quando — não
para tomá-la. Um benchmark que vira preço por conveniência produz um preço que ninguém decidiu: ele
apenas apareceu, copiado de empresas com outro produto, outro custo e outro cliente.

Há teste (`tests/test_v0200_pricing.py`) que reprova a suíte se algum módulo passar a ler este
benchmark e o arquivo de planos ao mesmo tempo — que é por onde um viraria o outro.
