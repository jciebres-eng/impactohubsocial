# ARQUITETURA DE MONETIZAÇÃO — v0.21.0

> ⚠️ **SUPERADO EM PARTE — v0.27.0 (ADR-341): NÃO EXISTE MAIS ASSINATURA.** Tudo o que este documento diz
> sobre mensalidade, plano pago, trial, checkout, reajuste, portal e cancelamento descreve um modelo que o
> proprietário retirou do IMPACTO em 08/10/2026. O que continua valendo: núcleo gratuito por desenho, o que
> o dinheiro nunca compra, acesso gratuito ≠ autorização de cobrança, regras transacionais desligadas. O
> modelo vigente está em `docs/ECONOMIC_MODEL.md` e `MONETIZATION.md`; o inventário do que foi mantido,
> migrado, aposentado e removido está em `docs/execution/SUBSCRIPTION_INVENTORY.md`. O texto abaixo fica
> como histórico — ele explica contratos e decisões anteriores — e NÃO deve ser lido como regra atual.


**Pricing Version:** 2027.01

---

## 1. AS CAMADAS, E O QUE CADA UMA DECIDE

```
PRICING_BIBLE.md              decisão comercial do proprietário (documento)
        ↓
config/plans.json             declaração: planos, limites, funcionalidades, price_versions.items
        ↓  (db/migrate.py::_sync_price_versions, forward-only, versão nova nunca sobrescreve)
plan_price_versions           CATÁLOGO — a única fonte de valor para cobrança
        ↓
commercial_offers             o que foi oferecido a ESTA organização
        ↓
offer_acceptances             o que ela aceitou, e SE autorizou cobrança
        ↓
subscriptions · subscription_prices   o preço congelado no aceite
        ↓
platform_charges · invoices   a cobrança, com grafo de estados e trilha append-only
```

Cada seta é unidirecional. Nenhuma camada de baixo escreve numa de cima, e nenhum valor entra pela
lateral: o preço de uma oferta é **lido do catálogo**, nunca recebido de quem pede.

---

## 2. AS QUATRO INVARIANTES, E ONDE ELAS MORAM

Todas as quatro moram no **banco**, não na aplicação. A diferença importa: um módulo pode ser
contornado por outro caminho de escrita — uma rota nova, um job, um script de operação, um console
de administração. Um gatilho, não.

| Invariante | Onde | Mensagem |
| --- | --- | --- |
| Não há cobrança sem autorização vigente | `charge_requires_authorization` (0043) | *cobrança sem autorização vigente: a organização aceitou acesso, não cobrança* |
| Preço não se sobrescreve | `price_version_immutable` (0017) | *Versão de preço não se reescreve: feche a vigência e crie outra* |
| Aumento exige aviso de 30 dias | `price_apply_guard` (0017) | recusa `subscription_prices` com aumento sem aviso vigente |
| Período gratuito concedido não se reescreve | `free_period_immutable` (0042) | *período gratuito concedido não se altera: cancele com motivo e conceda outro* |

Mais duas, herdadas e mantidas:

| Invariante | Onde |
| --- | --- |
| Take rate e success fee não se ativam sem custódia | `monetization_rule_gate` (0020), cita ADR-022 |
| `is_simulated` é derivada do provedor, não escrita à mão | `charge_simulated_flag` (0022) |

### Nota de correção: ordem de gatilhos

Gatilhos `BEFORE INSERT` disparam em **ordem alfabética do nome**, e
`trg_charge_requires_authorization` vem antes de `trg_charge_simulated`. A primeira versão da
exigência de autorização lia a coluna `is_simulated` — que, naquele instante, ainda contém o que o
chamador mandou, não o que o provedor determina. Bastava informar `is_simulated = true` junto com um
provedor real para passar pela exigência.

Corrigido: ambos os gatilhos perguntam à mesma função, `charge_is_simulated(provider)`. Teste:
`test_declaring_a_charge_simulated_does_not_bypass_the_requirement`.

---

## 3. GRATUIDADE: TRÊS MECANISMOS QUE COEXISTEM

| Mecanismo | Tabela | Prazo | Natureza |
| --- | --- | --- | --- |
| Plano gratuito | `plans` com `tier = 'free'` | **permanente** | desenho do produto |
| Teste de 14 dias | `org_trials` | 14 dias | aquisição |
| Período gratuito | `free_periods` | campanha ou N meses | decisão comercial |
| Licença / convênio | `entitlement_grants` | variável | contrato |

Nenhum substitui outro. `entitlements.effective()` combina todas as fontes e **a mais favorável
vale** — limites `None` (ilimitado) ganham, e entre números vale o maior.

---

## 4. ENTITLEMENTS: O QUE O PLANO LIBERA

`backend/impacto/services/entitlements.py`

* `effective(conn, org_id, org_kind)` — combina plano base, assinatura, licenças, convênios e trial;
* `require_feature()` — HTTP 402 `feature_not_in_plan`;
* `check_limit()` — HTTP 402 `plan_limit_reached`, por **contagem ao vivo**.

A contagem ao vivo é quem **bloqueia**, e continua sendo: ela é lida no instante da ação e não pode
errar. O contador persistido (`usage_counters`) é a camada que **avisa** e que **lembra** — se ele
atrasar, a pessoa recebe o aviso tarde; não perde acesso a nada.

---

## 5. MOTOR DE USO

| Peça | O que faz |
| --- | --- |
| `usage_counters` | consumo por organização, métrica e período; guarda o que a retenção dos registros originais apaga |
| `usage_alerts` | qual limiar já foi avisado — a chave primária **é** a idempotência |
| `spend_limits` | teto de gasto mensal, com ação `warn` ou `hard_stop` |

Limiares: **70%, 90%, 100%**. 70% é quando ainda dá para mudar de plano ou pedir orçamento; 90% é
quando dá para terminar o que está em curso; 100% é informação, não aviso. Avisar só em 100% é
avisar depois.

**Exceder o limite do plano não gera cobrança adicional.** O excedente é interrompido. Não há preço
de excedente publicado, e sem preço a plataforma bloqueia em vez de inventar.

### Divergência corrigida

A cota de IA era contada em dois lugares com regras diferentes: o bloqueio excluía pedidos
recusados, o painel não. A tela podia dizer "80 de 100" enquanto o bloqueio contava 60. Nenhuma das
duas estava errada sozinha — o defeito era existirem duas. Agora ambas chamam
`ai_usage_this_month(org_id)`, e um teste varre o código em busca de uma terceira cópia.

---

## 6. O QUE O PAGAMENTO NUNCA COMPRA

Declarado em `config/plans.json` → `never_sellable`, e travado por teste
(`test_no_code_path_turns_a_plan_into_a_score`): nenhum módulo de reputação, impacto, match, selo,
afirmação, equidade ou elegibilidade consulta `subscriptions`, `plan_price_versions`,
`platform_charges`, `invoices`, `offer_acceptances`, `commercial_offers` ou `free_periods`.

A varredura procura a relação, não a linha. `impact_score += payment` ninguém escreveria assim; o
que se escreve é um `JOIN` que, seis meses depois, vira peso.

---

## 7. RECEITA TRANSACIONAL — DECLARADA, DESLIGADA

`monetization_rules` tem 9 regras, **todas `active = false`**. `marketplace.take_rate` e
`success_fee.funding` não são apenas "não ativadas": são **recusadas pelo banco** enquanto valer a
ADR-022, porque a plataforma não custodia nem processa o valor sobre o qual cobraria percentual.

A PRICING_BIBLE.md §20 impõe a mesma condição em outras palavras: take rate só quando existir
`service + contract + transaction`. A Bíblia e a arquitetura dizem a mesma coisa; a arquitetura
apenas a impõe.

---

## 8. ROTAS

| Rota | O que serve |
| --- | --- |
| `GET /v1/plans` | catálogo público: preços, piso de proposta, versão de preço |
| `GET /v1/plans/price` | preço vigente de um plano/intervalo; 404 `price_not_defined` quando não há |
| `GET /v1/commercial/state` | **FREE_PERIOD_END**, estado comercial, se a cobrança foi autorizada |
| `GET/POST /v1/commercial/offers` | ofertas desta organização |
| `POST /v1/commercial/offers/{id}/accept` | aceite — `free_access` ou `authorized` |
| `POST /v1/commercial/consent/revoke` | revoga a autorização (o aceite permanece) |
| `GET /v1/commercial/acceptances` | histórico de aceites |
| `GET /v1/commercial/usage` | consumo, limiares, teto de gasto |
| `PUT /v1/commercial/spend-limit` | define o teto e a ação |
| `POST/GET /v1/admin/free-periods` | concessão e painel (auth admin) |

---

## 9. TAREFAS AGENDADAS

| Tarefa | O que faz |
| --- | --- |
| `commercial_sweep` | encerra períodos vencidos e dispara 90/60/30/7/1 + semanal + aviso de fim |
| `usage_alerts` | alertas de 70/90/100%, uma vez por limiar e por período |
| `billing_lifecycle` | o trial de 14 dias (separado de propósito: aquisição ≠ decisão comercial) |

---

## 10. LIMITES CONHECIDOS

1. **Minutas jurídicas em `draft`** — 11 documentos, nenhum aprovado, zero aceites legais gravados.
2. **Provedor de pagamento em sandbox** — a interface declara isso em faixa visível.
3. **Sem preço de excedente** — excedente é bloqueado, não cobrado.
4. **FUNDER CORPORATE sem plano próprio** — tratado como escopo de proposta (R-11).
5. **Sem valor anual** para `provider_premium` e `company_premium` — a Bíblia não publica, e não foi
   inventado.
