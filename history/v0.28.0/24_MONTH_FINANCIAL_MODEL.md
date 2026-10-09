# MODELO FINANCEIRO DE 24 MESES — v0.27.0 (sem assinatura, ADR-341)

**Pricing Version:** 2027.02 · **Camada econômica:** 3,50% plataforma + 1,50% participação de autoria = 5,00% da operação financiada
**Gerado por:** `scripts/make_24_month_model.py` a partir de `config/economic_model.json` · **Conferido por:** `backend/tests/test_v0270_financial_model.py`

> **RECEITA REAL DESTA INSTALAÇÃO: R$ 0,00.** A regra comercial `contract.platform_service_fee` está INATIVA (carta
> legal amarela). A camada econômica é registrada e instruída, mas nada fica devido nem é cobrado até a carta verde.
> Tudo abaixo é SIMULAÇÃO sobre HIPÓTESES DECLARADAS — não é projeção, não é meta, não é dado apurado.
>
> **Não existe assinatura.** O modelo da v0.21.0 (MRR de mensalidades a partir do mês 16) foi retirado com a
> assinatura. A receita possível da plataforma nasce da operação financiada e de contratos avulsos (não modelados aqui).

---

## 1. A FÓRMULA (decorre do contrato e do catálogo, não é premissa)

```
camada_registrada(op) = valor_financiado(op) × 350 bps      -- congelada na matriz do acordo na ativação
participacao(op)      = valor_financiado(op) × 150 bps      -- só com proponente elegível; NÃO é receita da plataforma
camada_paga(mês)      = Σ camada_registrada das operações QUITADAS no mês   -- só isto é receita, e só com a regra ativa
GMV ≠ receita: o valor financiado vai do financiador ao projeto; a plataforma não custodia (ADR-284).
```

## 2. SENSIBILIDADE — uma operação, do menor ao maior ticket

| Valor financiado | Projeto recebe (modo descontado) | Plataforma (3,50%) | Participação de autoria (1,50%) | Camada total |
| ---: | ---: | ---: | ---: | ---: |
| R$ 50.000,00 | R$ 47.500,00 | R$ 1.750,00 | R$ 750,00 | R$ 2.500,00 |
| R$ 100.000,00 | R$ 95.000,00 | R$ 3.500,00 | R$ 1.500,00 | R$ 5.000,00 |
| R$ 500.000,00 | R$ 475.000,00 | R$ 17.500,00 | R$ 7.500,00 | R$ 25.000,00 |
| R$ 1.000.000,00 | R$ 950.000,00 | R$ 35.000,00 | R$ 15.000,00 | R$ 50.000,00 |
| R$ 5.000.000,00 | R$ 4.750.000,00 | R$ 175.000,00 | R$ 75.000,00 | R$ 250.000,00 |
| R$ 10.000.000,00 | R$ 9.500.000,00 | R$ 350.000,00 | R$ 150.000,00 | R$ 500.000,00 |

Com `fee_mode = additional` o projeto recebe o valor cheio e o financiador paga a camada à parte; a soma fecha nos dois modos (CHECK no banco).

## 3. GMV NECESSÁRIO PARA CADA PATAMAR DE RECEITA (só aritmética)

| Receita da plataforma (camada PAGA) | GMV quitado necessário | Operações de R$ 150.000,00 |
| ---: | ---: | ---: |
| R$ 1.000.000,00 | R$ 28.571.428,57 | 190 |
| R$ 5.000.000,00 | R$ 142.857.142,86 | 952 |
| R$ 10.000.000,00 | R$ 285.714.285,71 | 1.905 |

## 4. TRÊS CENÁRIOS — PREMISSAS, NÃO PREVISÕES

Premissa comum: **3 novos clientes financiadores por mês**. O que muda entre cenários:

| Cenário | Ticket médio por operação | Operações por cliente/ano | Fração quitada | Meses até quitar | Rampa (meses) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Conservador | R$ 50.000,00 | 1 | 60% | 6 | 6 |
| Base | R$ 150.000,00 | 2 | 75% | 5 | 4 |
| Agressivo | R$ 500.000,00 | 3 | 85% | 4 | 3 |

### 4.1 Conservador

| Mês | Clientes | Operações ativadas | GMV ativado | Camada registrada | Participação (não é receita) | Camada PAGA |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 3 | 0.04 | R$ 2.083,33 | R$ 72,92 | R$ 31,25 | R$ 0,00 |
| 2 | 6 | 0.17 | R$ 8.333,33 | R$ 291,67 | R$ 125,00 | R$ 0,00 |
| 3 | 9 | 0.38 | R$ 18.750,00 | R$ 656,25 | R$ 281,25 | R$ 0,00 |
| 4 | 12 | 0.67 | R$ 33.333,33 | R$ 1.166,67 | R$ 500,00 | R$ 0,00 |
| 5 | 15 | 1.04 | R$ 52.083,33 | R$ 1.822,92 | R$ 781,25 | R$ 0,00 |
| 6 | 18 | 1.50 | R$ 75.000,00 | R$ 2.625,00 | R$ 1.125,00 | R$ 0,00 |
| 7 | 21 | 1.75 | R$ 87.500,00 | R$ 3.062,50 | R$ 1.312,50 | R$ 43,75 |
| 8 | 24 | 2.00 | R$ 100.000,00 | R$ 3.500,00 | R$ 1.500,00 | R$ 175,00 |
| 9 | 27 | 2.25 | R$ 112.500,00 | R$ 3.937,50 | R$ 1.687,50 | R$ 393,75 |
| 10 | 30 | 2.50 | R$ 125.000,00 | R$ 4.375,00 | R$ 1.875,00 | R$ 700,00 |
| 11 | 33 | 2.75 | R$ 137.500,00 | R$ 4.812,50 | R$ 2.062,50 | R$ 1.093,75 |
| 12 | 36 | 3.00 | R$ 150.000,00 | R$ 5.250,00 | R$ 2.250,00 | R$ 1.575,00 |
| 13 | 39 | 3.25 | R$ 162.500,00 | R$ 5.687,50 | R$ 2.437,50 | R$ 1.837,50 |
| 14 | 42 | 3.50 | R$ 175.000,00 | R$ 6.125,00 | R$ 2.625,00 | R$ 2.100,00 |
| 15 | 45 | 3.75 | R$ 187.500,00 | R$ 6.562,50 | R$ 2.812,50 | R$ 2.362,50 |
| 16 | 48 | 4.00 | R$ 200.000,00 | R$ 7.000,00 | R$ 3.000,00 | R$ 2.625,00 |
| 17 | 51 | 4.25 | R$ 212.500,00 | R$ 7.437,50 | R$ 3.187,50 | R$ 2.887,50 |
| 18 | 54 | 4.50 | R$ 225.000,00 | R$ 7.875,00 | R$ 3.375,00 | R$ 3.150,00 |
| 19 | 57 | 4.75 | R$ 237.500,00 | R$ 8.312,50 | R$ 3.562,50 | R$ 3.412,50 |
| 20 | 60 | 5.00 | R$ 250.000,00 | R$ 8.750,00 | R$ 3.750,00 | R$ 3.675,00 |
| 21 | 63 | 5.25 | R$ 262.500,00 | R$ 9.187,50 | R$ 3.937,50 | R$ 3.937,50 |
| 22 | 66 | 5.50 | R$ 275.000,00 | R$ 9.625,00 | R$ 4.125,00 | R$ 4.200,00 |
| 23 | 69 | 5.75 | R$ 287.500,00 | R$ 10.062,50 | R$ 4.312,50 | R$ 4.462,50 |
| 24 | 72 | 6.00 | R$ 300.000,00 | R$ 10.500,00 | R$ 4.500,00 | R$ 4.725,00 |
| **24 meses** | 72 | 73.55 | R$ 3.677.083,32 | R$ 128.697,93 | R$ 55.156,25 | **R$ 43.356,25** |

### 4.2 Base

| Mês | Clientes | Operações ativadas | GMV ativado | Camada registrada | Participação (não é receita) | Camada PAGA |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 3 | 0.12 | R$ 18.750,00 | R$ 656,25 | R$ 281,25 | R$ 0,00 |
| 2 | 6 | 0.50 | R$ 75.000,00 | R$ 2.625,00 | R$ 1.125,00 | R$ 0,00 |
| 3 | 9 | 1.12 | R$ 168.750,00 | R$ 5.906,25 | R$ 2.531,25 | R$ 0,00 |
| 4 | 12 | 2.00 | R$ 300.000,00 | R$ 10.500,00 | R$ 4.500,00 | R$ 0,00 |
| 5 | 15 | 2.50 | R$ 375.000,00 | R$ 13.125,00 | R$ 5.625,00 | R$ 0,00 |
| 6 | 18 | 3.00 | R$ 450.000,00 | R$ 15.750,00 | R$ 6.750,00 | R$ 492,19 |
| 7 | 21 | 3.50 | R$ 525.000,00 | R$ 18.375,00 | R$ 7.875,00 | R$ 1.968,75 |
| 8 | 24 | 4.00 | R$ 600.000,00 | R$ 21.000,00 | R$ 9.000,00 | R$ 4.429,69 |
| 9 | 27 | 4.50 | R$ 675.000,00 | R$ 23.625,00 | R$ 10.125,00 | R$ 7.875,00 |
| 10 | 30 | 5.00 | R$ 750.000,00 | R$ 26.250,00 | R$ 11.250,00 | R$ 9.843,75 |
| 11 | 33 | 5.50 | R$ 825.000,00 | R$ 28.875,00 | R$ 12.375,00 | R$ 11.812,50 |
| 12 | 36 | 6.00 | R$ 900.000,00 | R$ 31.500,00 | R$ 13.500,00 | R$ 13.781,25 |
| 13 | 39 | 6.50 | R$ 975.000,00 | R$ 34.125,00 | R$ 14.625,00 | R$ 15.750,00 |
| 14 | 42 | 7.00 | R$ 1.050.000,00 | R$ 36.750,00 | R$ 15.750,00 | R$ 17.718,75 |
| 15 | 45 | 7.50 | R$ 1.125.000,00 | R$ 39.375,00 | R$ 16.875,00 | R$ 19.687,50 |
| 16 | 48 | 8.00 | R$ 1.200.000,00 | R$ 42.000,00 | R$ 18.000,00 | R$ 21.656,25 |
| 17 | 51 | 8.50 | R$ 1.275.000,00 | R$ 44.625,00 | R$ 19.125,00 | R$ 23.625,00 |
| 18 | 54 | 9.00 | R$ 1.350.000,00 | R$ 47.250,00 | R$ 20.250,00 | R$ 25.593,75 |
| 19 | 57 | 9.50 | R$ 1.425.000,00 | R$ 49.875,00 | R$ 21.375,00 | R$ 27.562,50 |
| 20 | 60 | 10.00 | R$ 1.500.000,00 | R$ 52.500,00 | R$ 22.500,00 | R$ 29.531,25 |
| 21 | 63 | 10.50 | R$ 1.575.000,00 | R$ 55.125,00 | R$ 23.625,00 | R$ 31.500,00 |
| 22 | 66 | 11.00 | R$ 1.650.000,00 | R$ 57.750,00 | R$ 24.750,00 | R$ 33.468,75 |
| 23 | 69 | 11.50 | R$ 1.725.000,00 | R$ 60.375,00 | R$ 25.875,00 | R$ 35.437,50 |
| 24 | 72 | 12.00 | R$ 1.800.000,00 | R$ 63.000,00 | R$ 27.000,00 | R$ 37.406,25 |
| **24 meses** | 72 | 148.74 | R$ 22.312.500,00 | R$ 780.937,50 | R$ 334.687,50 | **R$ 369.140,63** |

### 4.3 Agressivo

| Mês | Clientes | Operações ativadas | GMV ativado | Camada registrada | Participação (não é receita) | Camada PAGA |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 3 | 0.25 | R$ 125.000,00 | R$ 4.375,00 | R$ 1.875,00 | R$ 0,00 |
| 2 | 6 | 1.00 | R$ 500.000,00 | R$ 17.500,00 | R$ 7.500,00 | R$ 0,00 |
| 3 | 9 | 2.25 | R$ 1.125.000,00 | R$ 39.375,00 | R$ 16.875,00 | R$ 0,00 |
| 4 | 12 | 3.00 | R$ 1.500.000,00 | R$ 52.500,00 | R$ 22.500,00 | R$ 0,00 |
| 5 | 15 | 3.75 | R$ 1.875.000,00 | R$ 65.625,00 | R$ 28.125,00 | R$ 3.718,75 |
| 6 | 18 | 4.50 | R$ 2.250.000,00 | R$ 78.750,00 | R$ 33.750,00 | R$ 14.875,00 |
| 7 | 21 | 5.25 | R$ 2.625.000,00 | R$ 91.875,00 | R$ 39.375,00 | R$ 33.468,75 |
| 8 | 24 | 6.00 | R$ 3.000.000,00 | R$ 105.000,00 | R$ 45.000,00 | R$ 44.625,00 |
| 9 | 27 | 6.75 | R$ 3.375.000,00 | R$ 118.125,00 | R$ 50.625,00 | R$ 55.781,25 |
| 10 | 30 | 7.50 | R$ 3.750.000,00 | R$ 131.250,00 | R$ 56.250,00 | R$ 66.937,50 |
| 11 | 33 | 8.25 | R$ 4.125.000,00 | R$ 144.375,00 | R$ 61.875,00 | R$ 78.093,75 |
| 12 | 36 | 9.00 | R$ 4.500.000,00 | R$ 157.500,00 | R$ 67.500,00 | R$ 89.250,00 |
| 13 | 39 | 9.75 | R$ 4.875.000,00 | R$ 170.625,00 | R$ 73.125,00 | R$ 100.406,25 |
| 14 | 42 | 10.50 | R$ 5.250.000,00 | R$ 183.750,00 | R$ 78.750,00 | R$ 111.562,50 |
| 15 | 45 | 11.25 | R$ 5.625.000,00 | R$ 196.875,00 | R$ 84.375,00 | R$ 122.718,75 |
| 16 | 48 | 12.00 | R$ 6.000.000,00 | R$ 210.000,00 | R$ 90.000,00 | R$ 133.875,00 |
| 17 | 51 | 12.75 | R$ 6.375.000,00 | R$ 223.125,00 | R$ 95.625,00 | R$ 145.031,25 |
| 18 | 54 | 13.50 | R$ 6.750.000,00 | R$ 236.250,00 | R$ 101.250,00 | R$ 156.187,50 |
| 19 | 57 | 14.25 | R$ 7.125.000,00 | R$ 249.375,00 | R$ 106.875,00 | R$ 167.343,75 |
| 20 | 60 | 15.00 | R$ 7.500.000,00 | R$ 262.500,00 | R$ 112.500,00 | R$ 178.500,00 |
| 21 | 63 | 15.75 | R$ 7.875.000,00 | R$ 275.625,00 | R$ 118.125,00 | R$ 189.656,25 |
| 22 | 66 | 16.50 | R$ 8.250.000,00 | R$ 288.750,00 | R$ 123.750,00 | R$ 200.812,50 |
| 23 | 69 | 17.25 | R$ 8.625.000,00 | R$ 301.875,00 | R$ 129.375,00 | R$ 211.968,75 |
| 24 | 72 | 18.00 | R$ 9.000.000,00 | R$ 315.000,00 | R$ 135.000,00 | R$ 223.125,00 |
| **24 meses** | 72 | 224.00 | R$ 112.000.000,00 | R$ 3.920.000,00 | R$ 1.680.000,00 | **R$ 2.327.937,50** |

## 5. RESUMO DOS CENÁRIOS (24 meses)

| Cenário | Clientes no mês 24 | GMV ativado | Camada registrada | Camada PAGA (receita possível) | Participação de autoria |
| --- | ---: | ---: | ---: | ---: | ---: |
| Conservador | 72 | R$ 3.677.083,32 | R$ 128.697,93 | **R$ 43.356,25** | R$ 55.156,25 |
| Base | 72 | R$ 22.312.500,00 | R$ 780.937,50 | **R$ 369.140,63** | R$ 334.687,50 |
| Agressivo | 72 | R$ 112.000.000,00 | R$ 3.920.000,00 | **R$ 2.327.937,50** | R$ 1.680.000,00 |

## 6. O QUE ESTE MODELO NÃO CONTÉM, E POR QUÊ

* **Custo e margem.** O lado do custo continua vazio (`UNIT_ECONOMICS.md`); um modelo com receita simulada e custo inventado produz margem inventada.
* **Contratos avulsos/parcelados** (implantação, módulo institucional, inteligência territorial): valor negociado por quem tem alçada, sem base para premissa.
* **Receita de IA/API e marketplace:** zero por construção (sem preço de excedente publicado; comissão recusada).
* **Data de ativação da regra comercial:** depende de parecer jurídico/contábil externo (`BLOCKED_EXTERNAL_DEPENDENCY`). Até lá, a camada PAGA simulada é hipótese sobre hipótese.
* **Churn, LTV, CAC:** não existem sem assinatura e sem histórico; o painel os marca como não medidos com motivo.

[PREMISSA] marca, neste repositório, qualquer número que venha de `config/economic_model.json` e não de registro. Todos os números deste documento são [PREMISSA], exceto os percentuais do catálogo e a aritmética sobre eles.
