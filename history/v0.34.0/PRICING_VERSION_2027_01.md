# PRICING VERSION 2027.01

**Entrada em vigor:** `2027-01-01 00:00:00` (`America/Sao_Paulo`)
**Decidida por:** proprietário, em `PRICING_BIBLE.md`
**Aplicada em:** v0.21.0 · `config/plans.json` → `plan_price_versions`
**Validação pendente:** jurídica, fiscal e operacional

---

## 1. TABELA VIGENTE

| `plan_key` | Rótulo comercial | Mensal | Anual | Moeda | Tributos |
| --- | --- | ---: | ---: | --- | --- |
| `individual_basic` | FREE — Pessoa | R$ 0 | — | BRL | n/a |
| `osc_basic` | FREE — OSC | R$ 0 | — | BRL | n/a |
| `provider_basic` | FREE — Profissional | R$ 0 | — | BRL | n/a |
| `company_basic` | FREE — Empresa | R$ 0 | — | BRL | n/a |
| `government_basic` | FREE — Governo | R$ 0 | — | BRL | n/a |
| `provider_premium` | PROFESSIONAL PRO | R$ 49,00 | — | BRL | não definidos |
| `osc_plus` | PRO | R$ 299,00 | R$ 2.990,00 | BRL | não definidos |
| `osc_premium` | BUSINESS | R$ 799,00 | R$ 7.990,00 | BRL | não definidos |
| `company_plus` | BUSINESS | R$ 799,00 | R$ 7.990,00 | BRL | não definidos |
| `company_premium` | FUNDER PRO | R$ 1.490,00 | — | BRL | não definidos |
| `company_enterprise` | ENTERPRISE | piso R$ 2.500,00 — **sob proposta** | — | BRL | — |
| `gov_institutional` | GOV | piso R$ 3.500,00 — **sob proposta** | — | BRL | — |

8 versões de preço contratáveis. 2 pisos publicados sem preço contratável. 5 planos gratuitos sem
versão de preço — ausência de cobrança não é uma versão de preço.

---

## 2. `tax_behavior = 'unspecified'`

Esta é a resposta **honesta** hoje. A `PRICING_BIBLE.md` não declara se os valores são com ou sem
tributos, e declarar `inclusive` sem parecer fiscal seria inventar um fato tributário.

A interface **exibe essa indefinição** em vez de escondê-la: "Tributos ainda não definidos para este
valor." Fechar isso exige validação fiscal, registrada em `PRICING_BIBLE.md` §10.

---

## 3. DESCONTO ANUAL

| Plano | Mensal × 12 | Anual | Desconto |
| --- | ---: | ---: | ---: |
| PRO | R$ 3.588,00 | R$ 2.990,00 | 16,7% |
| BUSINESS | R$ 9.588,00 | R$ 7.990,00 | 16,7% |

O desconto é **consequência de dois valores publicados**, não um percentual configurável. Não existe
"desconto de X%" em lugar nenhum do código, e há teste que confere a conta.

---

## 4. O QUE ESTA VERSÃO NÃO FAZ

| | |
| --- | --- |
| **Não ressuscita** a regra em dólar da v0.16.0 (US$ 1,99 → US$ 19,99) | os dois itens `retire: true` permanecem no arquivo, fechando a vigência daquela regra |
| **Não cria** valor anual para `provider_premium` nem `company_premium` | a Bíblia não publica; criar um desconto seria inventar preço |
| **Não ativa** take rate, success fee nem transaction fee | declarados, `active = false`, recusados pelo banco enquanto valer a ADR-022 |
| **Não torna contratável** ENTERPRISE nem GOV | piso publicado ≠ preço; o checkout recusa com `price_not_defined` |
| **Não cobra** nada em 2026 | FULL FREE 2026, por conta, em `free_periods` |

---

## 5. COMO SE CRIA A PRÓXIMA VERSÃO

1. **AUDIT** — localizar a regra vigente no código, no banco e nos testes;
2. **RECONCILIATION** — registrar a divergência e a decisão em `PRICING_RECONCILIATION.md`;
3. **PRICING VERSION** — alterar `config/plans.json` → `price_versions.items` e implantar.

O sincronizador fecha a vigência da versão anterior e abre a nova. O histórico **nunca** é
sobrescrito: é isso que permite responder "quanto esta organização contratou em março?" depois de um
reajuste.

Aumento para quem já assina exige aviso de 30 dias em `price_change_notices`, imposto por gatilho.

### Reajuste agendado

Uma versão com `effective_from` no futuro é suportada: o sincronizador fecha a vigência respeitando
`effective_until > effective_from` mesmo quando a versão ainda não começou. Isto foi corrigido na
v0.21.0 — até então, qualquer implantação feita com um reajuste anunciado pendente **quebrava a
migração**. Teste: `test_a_price_scheduled_for_the_future_does_not_break_the_sync`.

---

## 6. RASTREABILIDADE

Todo item de preço carrega, no campo `reason`, a versão de preço e a seção da Bíblia que o decidiu:

> `Pricing Version 2027.01 — PRO (Bíblia §12); PRICING_BIBLE.md §3. Valor de referência inicial,
> pendente de validação jurídica e fiscal.`

Há teste que recusa um preço cujo `reason` não nomeie a versão e a decisão
(`test_the_shipped_product_declares_no_price_at_all`, reescrito na v0.21.0).
