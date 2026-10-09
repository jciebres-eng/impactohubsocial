# MODELO DE CUSTO E SUSTENTABILIDADE DA IA — v0.28.0 (2027.02-ai-pilot)

**Gerado por:** `scripts/make_ai_cost_model.py` a partir de `config/ai_economics.json` e `docs/evidence/ai_pilot_v0280.json` · **Conferido por:** `backend/tests/test_v0280_ai_cost_model.py`

> **O que é MEDIDO e o que é [PREMISSA].** Medido nesta instalação: latência do motor local de similaridade e o tamanho das
> entradas (piloto, §1); execuções, créditos e custo externo apurado aparecem no painel `/v1/admin/ai/finance` quando
> existem. **Nenhum provedor externo está configurado e a tabela de preço do provedor está vazia**: todo custo de modelo
> abaixo é [PREMISSA] declarada em `config/ai_economics.json`. Preços de operação e de pacote são HIPÓTESES de teste do
> proprietário (ADR-349), não preços de produção. **Receita real de IA desta instalação: R$ 0,00** (modo piloto).

---

## 1. Piloto — o que foi medido de verdade

Medido em 2026-10-08, motor `similarity@1.0`, perfis sintéticos, nesta máquina:

| Medição | p50 | p95 / máx | n |
| --- | ---: | ---: | ---: |
| comparação de um par | 0.75 ms | 0.97 ms | 50 |
| originalidade contra 50 candidatos | 37.5 ms | 42.2 ms | 5 |
| originalidade contra 200 candidatos | 153.4 ms | 203.6 ms | 3 |
| entrada de um projeto | 1304 caracteres ≈ 326 tokens (4 car./token, aproximação) | | |

**Não medido:** custo de provedor externo (nenhum configurado; tabela de preço vazia); infraestrutura por operação; tarifa de pagamento; impostos; qualidade em base real.

## 2. Custo unitário e margem de contribuição por operação [PREMISSA]

Preço do crédito: R$ 0,10 [PREMISSA] · modelo externo: R$ 15,00/Mtok entrada, R$ 75,00/Mtok saída [PREMISSA] · infra R$ 0,02 local / R$ 0,05 externa por operação [PREMISSA] · retries 5% · tarifa PIX 1.0% · impostos 8.65% [PREMISSA]

| Operação | Cat. | Créditos | Preço | Custo modelo | Infra+retries | Tarifa | Imposto | Margem de contribuição | % |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `assist.summarize_project` | A | 1 | R$ 0,10 | 4,05 ¢ | 5,20 ¢ | 0,10 ¢ | 0,86 ¢ | **-0,22 ¢** | -2% |
| `assist.structure_need` | B | 5 | R$ 0,50 | 10,50 ¢ | 5,53 ¢ | 0,50 ¢ | 4,33 ¢ | **29,15 ¢** | 58% |
| `assist.draft_document` | B | 10 | R$ 1,00 | 21,00 ¢ | 6,05 ¢ | 1,00 ¢ | 8,65 ¢ | **63,30 ¢** | 63% |
| `similarity.single` | D | 49 | R$ 4,90 | 0,00 ¢ | 2,00 ¢ | 4,90 ¢ | 42,38 ¢ | **440,72 ¢** | 90% |
| `similarity.pair` | D | 49 | R$ 4,90 | 0,00 ¢ | 2,00 ¢ | 4,90 ¢ | 42,38 ¢ | **440,72 ¢** | 90% |
| `similarity.complementarity` | D | 29 | R$ 2,90 | 0,00 ¢ | 2,00 ¢ | 2,90 ¢ | 25,09 ¢ | **260,02 ¢** | 90% |
| `similarity.set` | D | 129 | R$ 12,90 | 0,00 ¢ | 2,00 ¢ | 12,90 ¢ | 111,58 ¢ | **1163,51 ¢** | 90% |
| `similarity.expense_overlap` | D | 149 | R$ 14,90 | 0,00 ¢ | 2,00 ¢ | 14,90 ¢ | 128,88 ¢ | **1344,21 ¢** | 90% |

Margem de contribuição = receita reconhecida − custos variáveis − tarifa − imposto. Não é lucro: despesas fixas e suporte ficam fora (§4).
A tabela acima supõe PROVEDOR EXTERNO contratado para as operações de assistência (A/B). Hoje NÃO há provedor: essas operações rodam no motor local e custam só infraestrutura (R$ 0,02 [PREMISSA]).
**Operações DEFICITÁRIAS com provedor externo nas premissas: `assist.summarize_project` (-0,22 ¢).** A regra do pedido é explícita: não manter cobrança deficitária por inércia — antes de ligar um provedor externo, a operação precisa de preço maior, limite de tokens menor, cache por versão ou permanência no motor local. Este documento registra o achado; a decisão é da administração (versão nova no catálogo, sem código).

## 3. Quanto custa a gratuidade (cota) [PREMISSA sobre custo; cotas MEDIDAS no catálogo]

Cota de boas-vindas: 60 créditos por organização (uma vez; uma por pessoa). Cota leve mensal: 10 créditos (OSC e profissional).

| Operação | Custo variável de UMA execução gratuita | Execuções gratuitas que a cota de boas-vindas cobre |
| --- | ---: | ---: |
| `assist.summarize_project` | 9,25 ¢ (com provedor) / 2,00 ¢ (local) | 60 |
| `assist.structure_need` | 16,02 ¢ (com provedor) / 2,00 ¢ (local) | 12 |
| `assist.draft_document` | 27,05 ¢ (com provedor) / 2,00 ¢ (local) | 6 |
| `similarity.single` | 2,00 ¢ (com provedor) / 2,00 ¢ (local) | 1 |
| `similarity.pair` | 2,00 ¢ (com provedor) / 2,00 ¢ (local) | 1 |
| `similarity.complementarity` | 2,00 ¢ (com provedor) / 2,00 ¢ (local) | 2 |
| `similarity.set` | 2,00 ¢ (com provedor) / 2,00 ¢ (local) | 0 |
| `similarity.expense_overlap` | 2,00 ¢ (com provedor) / 2,00 ¢ (local) | 0 |

Teto de subsídio declarado para o piloto: **R$ 500,00/mês** [PREMISSA]. A cada mês o painel compara o custo medido das execuções gratuitas (`free_quota_uses` × custo) com este teto; acima dele, a política `welcome.v1` é reduzida pela administração (sem código) ou a gratuidade passa a patrocínio institucional (§5).

## 4. Três cenários, 12 meses [PREMISSA]

### 4.1 Conservador — 40 usuários no mês 1, +8/mês, 35% usam IA, 2.0 operações/usuário de IA/mês

| Mês | Usuários | Usuários de IA | Operações | Gratuitas | Patrocinadas | Pagas | Custo variável | Custo da gratuidade | Receita reconhecida | Margem (após tarifa, imposto e suporte) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 40 | 14 | 28 | 17 | 3 | 3 | R$ 0,45 | R$ 0,35 | R$ 31,36 | R$ 15,88 |
| 2 | 48 | 17 | 34 | 21 | 3 | 3 | R$ 0,54 | R$ 0,42 | R$ 37,64 | R$ 19,06 |
| 3 | 56 | 20 | 39 | 24 | 4 | 4 | R$ 0,64 | R$ 0,49 | R$ 43,91 | R$ 22,24 |
| 4 | 64 | 22 | 45 | 28 | 4 | 4 | R$ 0,73 | R$ 0,56 | R$ 50,18 | R$ 25,41 |
| 5 | 72 | 25 | 50 | 31 | 5 | 5 | R$ 0,82 | R$ 0,63 | R$ 56,46 | R$ 28,59 |
| 6 | 80 | 28 | 56 | 35 | 5 | 5 | R$ 0,91 | R$ 0,70 | R$ 62,73 | R$ 31,77 |
| 7 | 88 | 31 | 62 | 38 | 6 | 6 | R$ 1,00 | R$ 0,77 | R$ 69,00 | R$ 34,95 |
| 8 | 96 | 34 | 67 | 42 | 6 | 6 | R$ 1,09 | R$ 0,83 | R$ 75,28 | R$ 38,12 |
| 9 | 104 | 36 | 73 | 45 | 7 | 7 | R$ 1,18 | R$ 0,90 | R$ 81,55 | R$ 41,30 |
| 10 | 112 | 39 | 78 | 49 | 7 | 7 | R$ 1,27 | R$ 0,97 | R$ 87,82 | R$ 44,48 |
| 11 | 120 | 42 | 84 | 52 | 8 | 8 | R$ 1,36 | R$ 1,04 | R$ 94,09 | R$ 47,65 |
| 12 | 128 | 45 | 90 | 56 | 8 | 8 | R$ 1,45 | R$ 1,11 | R$ 100,37 | R$ 50,83 |
| **12 meses** | 128 | | 706 | 438 | 67 | 67 | R$ 11,44 | R$ 8,76 | R$ 790,40 | **R$ 400,28** |

### 4.2 Base — 80 usuários no mês 1, +20/mês, 50% usam IA, 3.0 operações/usuário de IA/mês

| Mês | Usuários | Usuários de IA | Operações | Gratuitas | Patrocinadas | Pagas | Custo variável | Custo da gratuidade | Receita reconhecida | Margem (após tarifa, imposto e suporte) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 80 | 40 | 120 | 70 | 15 | 20 | R$ 2,10 | R$ 1,41 | R$ 218,31 | R$ 171,14 |
| 2 | 100 | 50 | 150 | 88 | 19 | 25 | R$ 2,63 | R$ 1,76 | R$ 272,89 | R$ 213,93 |
| 3 | 120 | 60 | 180 | 106 | 22 | 30 | R$ 3,15 | R$ 2,11 | R$ 327,47 | R$ 256,71 |
| 4 | 140 | 70 | 210 | 123 | 26 | 35 | R$ 3,68 | R$ 2,47 | R$ 382,05 | R$ 299,50 |
| 5 | 160 | 80 | 240 | 141 | 30 | 40 | R$ 4,21 | R$ 2,82 | R$ 436,62 | R$ 342,28 |
| 6 | 180 | 90 | 270 | 158 | 33 | 45 | R$ 4,73 | R$ 3,17 | R$ 491,20 | R$ 385,07 |
| 7 | 200 | 100 | 300 | 176 | 37 | 50 | R$ 5,26 | R$ 3,52 | R$ 545,78 | R$ 427,86 |
| 8 | 220 | 110 | 330 | 194 | 41 | 55 | R$ 5,78 | R$ 3,87 | R$ 600,36 | R$ 470,64 |
| 9 | 240 | 120 | 360 | 211 | 45 | 59 | R$ 6,31 | R$ 4,23 | R$ 654,94 | R$ 513,43 |
| 10 | 260 | 130 | 390 | 229 | 48 | 64 | R$ 6,83 | R$ 4,58 | R$ 709,51 | R$ 556,21 |
| 11 | 280 | 140 | 420 | 247 | 52 | 69 | R$ 7,36 | R$ 4,93 | R$ 764,09 | R$ 599,00 |
| 12 | 300 | 150 | 450 | 264 | 56 | 74 | R$ 7,88 | R$ 5,28 | R$ 818,67 | R$ 641,78 |
| **12 meses** | 300 | | 3420 | 2008 | 424 | 565 | R$ 59,93 | R$ 40,15 | R$ 6.221,89 | **R$ 4.877,55** |

### 4.3 Agressivo — 150 usuários no mês 1, +60/mês, 65% usam IA, 5.0 operações/usuário de IA/mês

| Mês | Usuários | Usuários de IA | Operações | Gratuitas | Patrocinadas | Pagas | Custo variável | Custo da gratuidade | Receita reconhecida | Margem (após tarifa, imposto e suporte) |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 150 | 98 | 488 | 270 | 76 | 109 | R$ 9,10 | R$ 5,39 | R$ 1.225,53 | R$ 1.053,17 |
| 2 | 210 | 136 | 682 | 377 | 107 | 153 | R$ 12,73 | R$ 7,55 | R$ 1.715,75 | R$ 1.474,44 |
| 3 | 270 | 176 | 878 | 485 | 137 | 196 | R$ 16,37 | R$ 9,71 | R$ 2.205,96 | R$ 1.895,71 |
| 4 | 330 | 214 | 1072 | 593 | 168 | 240 | R$ 20,01 | R$ 11,86 | R$ 2.696,18 | R$ 2.316,98 |
| 5 | 390 | 254 | 1268 | 701 | 198 | 283 | R$ 23,65 | R$ 14,02 | R$ 3.186,39 | R$ 2.738,25 |
| 6 | 450 | 292 | 1462 | 809 | 229 | 327 | R$ 27,29 | R$ 16,18 | R$ 3.676,60 | R$ 3.159,52 |
| 7 | 510 | 332 | 1658 | 917 | 259 | 370 | R$ 30,93 | R$ 18,33 | R$ 4.166,82 | R$ 3.580,79 |
| 8 | 570 | 370 | 1852 | 1024 | 290 | 414 | R$ 34,57 | R$ 20,49 | R$ 4.657,03 | R$ 4.002,06 |
| 9 | 630 | 410 | 2048 | 1132 | 320 | 458 | R$ 38,20 | R$ 22,65 | R$ 5.147,25 | R$ 4.423,33 |
| 10 | 690 | 448 | 2242 | 1240 | 351 | 501 | R$ 41,84 | R$ 24,80 | R$ 5.637,46 | R$ 4.844,60 |
| 11 | 750 | 488 | 2438 | 1348 | 381 | 545 | R$ 45,48 | R$ 26,96 | R$ 6.127,67 | R$ 5.265,87 |
| 12 | 810 | 526 | 2632 | 1456 | 412 | 588 | R$ 49,12 | R$ 29,12 | R$ 6.617,89 | R$ 5.687,14 |
| **12 meses** | 810 | | 18720 | 10352 | 2929 | 4184 | R$ 349,30 | R$ 207,04 | R$ 47.060,54 | **R$ 40.441,90** |

### 4.4 Resumo

| Cenário | Usuários no mês 12 | Operações | Custo variável | Custo da gratuidade | Receita reconhecida (dos quais patrocínio) | Margem |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Conservador | 128 | 706 | R$ 11,44 | R$ 8,76 | R$ 790,40 (R$ 395,20) | **R$ 400,28** |
| Base | 300 | 3420 | R$ 59,93 | R$ 40,15 | R$ 6.221,89 (R$ 2.666,52) | **R$ 4.877,55** |
| Agressivo | 810 | 18720 | R$ 349,30 | R$ 207,04 | R$ 47.060,54 (R$ 19.377,87) | **R$ 40.441,90** |

## 5. Sensibilidade: e se o uso dobrar? [PREMISSA]

* **Conservador**: dobrando operações por usuário, custo variável R$ 11,44 → R$ 22,88; custo da gratuidade R$ 8,76 → R$ 17,53; margem R$ 400,28 → R$ 1.102,97. A gratuidade escala linearmente com o uso: é ela que precisa de teto (§3), não a operação paga.
* **Base**: dobrando operações por usuário, custo variável R$ 59,93 → R$ 119,85; custo da gratuidade R$ 40,15 → R$ 80,30; margem R$ 4.877,55 → R$ 10.439,10. A gratuidade escala linearmente com o uso: é ela que precisa de teto (§3), não a operação paga.
* **Agressivo**: dobrando operações por usuário, custo variável R$ 349,30 → R$ 698,59; custo da gratuidade R$ 207,04 → R$ 414,09; margem R$ 40.441,90 → R$ 82.611,79. A gratuidade escala linearmente com o uso: é ela que precisa de teto (§3), não a operação paga.

## 6. Sensibilidade ao preço do provedor externo [PREMISSA]

| Preço do modelo | Custo de `assist.draft_document` | Margem da operação (10 créditos) |
| --- | ---: | ---: |
| metade | 16,02 ¢ | 74,32 ¢ (74%) |
| premissa | 27,05 ¢ | 63,30 ¢ (63%) |
| dobro | 49,10 ¢ | 41,25 ¢ (41%) |
| quádruplo | 93,20 ¢ | -2,85 ¢ (-3%) |

## 7. As doze perguntas, respondidas pelas premissas

1. **Quanto custa manter cada perfil ativo?** No cenário base, R$ 0,33 por usuário-mês em custo variável de IA + suporte [PREMISSA]; o perfil não muda o custo — a categoria da operação muda.
2. **Quanto custa cada modalidade?** §2: de 2,00 ¢ (motor local) a 27,05 ¢ (rascunho com provedor externo) por execução [PREMISSA].
3. **Quantas operações gratuitas cabem no orçamento?** Com teto de R$ 500,00/mês e custo médio da execução gratuita de 2,00 ¢, cabem ~25.000 execuções gratuitas por mês.
4. **Custo mensal da gratuidade?** Cenário base: R$ 3,35/mês em média; mês 12: R$ 5,28.
5. **Ponto de equilíbrio por categoria?** Com provedor externo, a menor margem é `assist.summarize_project` (-2%) — deficitária; no motor local (estado medido) todas cobrem o custo variável. O equilíbrio do TODO (gratuidade + suporte) chega no cenário base no mês 1.
6. **Margem por operação?** §2, coluna 'Margem de contribuição'.
7. **Pior cenário plausível?** Agressivo com uso dobrado (§5) e provedor ao quádruplo (§6): `assist.draft_document` fica com margem de -2,85 ¢ (NEGATIVA: a operação não pode ser vendida a este preço com esse provedor); a gratuidade quadruplica — é o caso que exige teto, patrocínio e reprecificação por versão nova.
8. **Limite de exposição financeira aceitável?** O declarado: R$ 500,00/mês de subsídio [PREMISSA]. O painel acusa quando o custo medido da gratuidade passa disso.
9. **Se o consumo dobrar?** §5: custo e gratuidade dobram; a margem das operações pagas também — o sinal de risco é a razão gratuitas/pagas, não o volume.
10. **Quais funcionalidades precisam de limites mais rigorosos?** `similarity.set` (até 20 projetos) e qualquer lote (`similarity.batch`, planejada e NÃO implementada); operações externas de categoria B (tamanho de entrada e `max_output_tokens` da faixa).
11. **Quando o patrocínio é melhor que a gratuidade subsidiada?** Sempre que a execução custa mais do que a cota cobre para a organização beneficiada: o patrocínio é crédito comprado por quem tem capacidade de pagar (receita), a gratuidade é custo. No cenário base, R$ 2.666,52 dos R$ 6.221,89 de receita vêm de patrocínio.
12. **Quais operações devem usar modelo mais barato, cache ou assíncrono?** Cache já vale para similaridade (mesmos dados = sem nova cobrança) e deve valer para resumo por versão de projeto; categoria A deve ficar no motor local sempre que a qualidade bastar; lote só assíncrono com orçamento por tarefa (não implementado).

## 8. O que este modelo NÃO contém

* Preço do provedor real, câmbio e tabela vigente: a `ai_price_table` nasce vazia e o painel marca `no_price_table` até a administração cadastrar.
* Reconhecimento contábil de créditos não consumidos (passivo) e regra de devolução/expiração: carta legal amarela de `ai.credits_prepaid`.
* Despesas fixas e margem líquida: fora do escopo (UNIT_ECONOMICS.md).
* Qualquer número de uso real: esta instalação não tem clientes; tudo aqui é [PREMISSA] até o painel medir.
