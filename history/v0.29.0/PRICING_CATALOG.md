# CATÁLOGO DE PREÇOS — GERADO

**Pricing Version:** `2027.01` · **Catálogo:** `plans@3.0` · **Moeda:** BRL

> Gerado por `scripts/make_pricing_catalog.py` a partir de `config/plans.json` — não edite à
> mão. A decisão comercial está em `PRICING_BIBLE.md`; a reconciliação com o que o código já
> fazia está em `PRICING_RECONCILIATION.md`.

---

## 1. PLANOS

| `plan_key` | Nome | Perfil | Faixa | Mensal | Anual | Piso de proposta | Contratação |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| `company_basic` | Empresa Essencial | company | free | R$ 0,00 | — | — | online (gratuito) |
| `company_plus` | Empresa Plus | company | plus | R$ 799,00 | R$ 7.990,00 | — | online |
| `company_enterprise` | Empresa Enterprise | company | premium | — | — | R$ 2.500,00 | **proposta comercial** |
| `company_premium` | Empresa Impacto | company | premium | R$ 1.490,00 | — | — | online |
| `government_basic` | Governo | government | free | R$ 0,00 | — | — | online (gratuito) |
| `gov_institutional` | Governo / Institucional | government | gov | — | — | R$ 3.500,00 | **proposta comercial** |
| `individual_basic` | Apoiador Pessoa Física | individual | free | R$ 0,00 | — | — | online (gratuito) |
| `osc_basic` | OSC — gratuito | osc | free | R$ 0,00 | — | — | online (gratuito) |
| `osc_plus` | OSC Plus | osc | plus | R$ 299,00 | R$ 2.990,00 | — | online |
| `osc_premium` | OSC Captação | osc | premium | R$ 799,00 | R$ 7.990,00 | — | online |
| `provider_basic` | Profissional Parceiro | provider | free | R$ 0,00 | — | — | online (gratuito) |
| `provider_premium` | Profissional Parceiro Plus | provider | premium | R$ 49,00 | — | — | online |

---

## 2. VERSÕES DE PREÇO VIGENTES

| Plano | Intervalo | Valor | Tributos | Decisão |
| --- | --- | ---: | --- | --- |
| `company_plus` | month | R$ 799,00 | unspecified | Pricing Version 2027.01 — BUSINESS (Bíblia §13); PRICING_BIBLE.md §3. Valor de referência inicial, pendente de validação jurídica e fiscal. |
| `company_plus` | year | R$ 7.990,00 | unspecified | Pricing Version 2027.01 — BUSINESS (Bíblia §13) anual; PRICING_BIBLE.md §3. Valor de referência inicial, pendente de validação jurídica e fiscal. |
| `company_premium` | month | R$ 1.490,00 | unspecified | Pricing Version 2027.01 — FUNDER PRO (Bíblia §24); PRICING_BIBLE.md §3. Valor de referência inicial, pendente de validação jurídica e fiscal. |
| `osc_plus` | month | R$ 299,00 | unspecified | Pricing Version 2027.01 — PRO (Bíblia §12); PRICING_BIBLE.md §3. Valor de referência inicial, pendente de validação jurídica e fiscal. |
| `osc_plus` | year | R$ 2.990,00 | unspecified | Pricing Version 2027.01 — PRO (Bíblia §12) anual; PRICING_BIBLE.md §3. Valor de referência inicial, pendente de validação jurídica e fiscal. |
| `osc_premium` | month | R$ 799,00 | unspecified | Pricing Version 2027.01 — BUSINESS (Bíblia §13); PRICING_BIBLE.md §3. Valor de referência inicial, pendente de validação jurídica e fiscal. |
| `osc_premium` | year | R$ 7.990,00 | unspecified | Pricing Version 2027.01 — BUSINESS (Bíblia §13) anual; PRICING_BIBLE.md §3. Valor de referência inicial, pendente de validação jurídica e fiscal. |
| `provider_premium` | month | R$ 49,00 | unspecified | Pricing Version 2027.01 — PROFESSIONAL PRO (Bíblia §17); PRICING_BIBLE.md §3. Valor de referência inicial, pendente de validação jurídica e fiscal. |

---

## 3. VERSÕES APOSENTADAS

Aposentar **não é apagar**: o preço de ontem explica o contrato de ontem. Um item com
`retire: true` fecha a vigência e não abre nenhuma nova.

| Faixa | Intervalo | Moeda | Motivo |
| --- | --- | --- | --- |
| premium | month | USD | Regra comercial da v0.16.0 aposentada na v0.17.0: o proponente deixou de ser o pagador principal. |
| premium | year | USD | Regra comercial da v0.16.0 aposentada na v0.17.0: o proponente deixou de ser o pagador principal. |

---

## 4. LIMITES POR PLANO

`null` significa **ilimitado**. Entre fontes (plano base, assinatura, licença,
convênio, teste), vale sempre a mais favorável.

| Plano | `active_projects` | `ai_requests_month` | `storage_mb` | `seats` | `saved_searches` | `programs` | `open_reviews` |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `company_basic` | — | 50 | 1000 | 3 | 0 | 1 | — |
| `company_enterprise` | — | 5000 | ilimitado | ilimitado | ilimitado | ilimitado | — |
| `company_plus` | — | 150 | 10000 | 10 | 10 | 3 | — |
| `company_premium` | — | 500 | 50000 | 25 | 30 | 10 | — |
| `gov_institutional` | — | 1000 | ilimitado | ilimitado | — | ilimitado | — |
| `government_basic` | — | 100 | 20000 | 20 | — | ilimitado | — |
| `individual_basic` | — | 10 | 200 | 2 | 3 | — | — |
| `osc_basic` | 10 | 20 | 1000 | 5 | 3 | — | — |
| `osc_plus` | 8 | 100 | 3000 | 8 | 5 | — | — |
| `osc_premium` | 20 | 300 | 10000 | 15 | 20 | — | — |
| `provider_basic` | — | 10 | 500 | 3 | — | — | 10 |
| `provider_premium` | — | 100 | 5000 | 10 | — | — | 100 |

---

## 5. NUNCA VENDÁVEL

Nenhum plano libera estas capacidades, em nenhuma faixa, por nenhum valor:

* `provider_rank`
* `provider_featured`
* `provider_badge`
* `match_boost`
* `eligibility_override`

Travado por teste: `test_no_plan_sells_anything_from_the_list` e
`test_no_code_path_turns_a_plan_into_a_score`.

