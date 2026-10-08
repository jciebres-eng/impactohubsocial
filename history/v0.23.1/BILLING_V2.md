# Cobrança v2 — preço versionado (v0.16.0)

> ⚠️ **ESTE DOCUMENTO DESCREVE A ARQUITETURA DA v0.16.0, NÃO A REGRA COMERCIAL VIGENTE.**
>
> A regra comercial que ele cita (US$ 1,99 nos três primeiros meses, depois US$ 19,99, cobrados do
> proponente) foi **APOSENTADA na v0.17.0** por decisão do proprietário, e `config/plans.json` já
> fechou a vigência daquela tabela. A auditoria da v0.21.0 encontrou esta divergência entre o
> documento e o código.
>
> A regra comercial vigente é a **Pricing Version 2027.01**:
> `PRICING_BIBLE.md` (decisão) · `PRICING_CATALOG.md` (catálogo gerado) ·
> `PRICING_VERSION_2027_01.md` (a versão) · `BILLING_ARCHITECTURE.md` (como se cobra hoje).
>
> O que continua válido aqui é a descrição dos **mecanismos** — versionamento de preço,
> imutabilidade, aviso de 30 dias, congelamento do preço aceito —, que a v0.21.0 preservou e usa.


A regra comercial desta rodada, verbatim do pedido:

> 14 dias de teste com o produto completo; **US$ 1,99/mês nos 3 primeiros meses pagos**; depois **US$ 19,99/mês** ou o
> anual equivalente a **US$ 14,99/mês** (US$ 179,88 à vista), com o total claramente exibido; preço **não** fixado em
> código; **backend é a autoridade**; impostos no checkout; **nunca mudar preço em silêncio**; sem padrões obscuros;
> webhooks idempotentes.

Migração: `backend/migrations/0017_v0160_billing_v2.sql` · Configuração: `config/plans.json` (`plans@1.2`) ·
Serviços: `services/monetization.py`, `services/billing.py` · Tela: `web/src/pages/org.tsx`

## Onde o preço mora

| Camada | Papel |
|---|---|
| `config/plans.json` | **declaração** da regra comercial, versionada em git |
| `plan_price_versions` | **histórico vigente** no banco: a autoridade de runtime |
| `_sync_price_versions()` em `db/migrate.py` | leva a declaração ao banco criando **versão nova** quando o valor difere |
| `price_current(plan, interval, currency)` | a função SQL que responde "quanto custa agora" |
| `monetization.price_quote()` | a montagem do que a tela mostra |
| frontend | **só exibe** o que o backend devolveu |

Nenhum valor monetário aparece em código Python ou TypeScript. O teste de arquitetura
`test_prices_are_not_hard_coded` lê os valores **declarados** em `config/plans.json` e falha se qualquer um deles
aparecer como literal no backend ou no frontend — se alguém "ajudar" escrevendo `1999` numa tela, a suíte quebra.

## A tabela de versões

`plan_price_versions(plan_key, interval, currency, amount_cents, intro_amount_cents, intro_periods, trial_days,
effective_from, effective_until, tax_behavior, provider, provider_price_id, reason)`

Travas estruturais:

* **`ux_price_current`** — índice único parcial: existe **no máximo uma** versão vigente por
  `(plano, intervalo, moeda)`. Duas vigentes ao mesmo tempo é impossível, não improvável.
* **`price_version_immutable()`** — gatilho que recusa alterar `amount_cents`, `intro_*`, `currency` ou
  `tax_behavior` de uma versão existente. Mudar preço **cria versão nova**; o histórico nunca é reescrito.
  (Aqui `guard_columns` era inútil: ela isenta `app_priv()`, que é justamente o único contexto que escreve esta
  tabela — então a trava teve de ser um gatilho próprio.)
* **CHECK `intro_pair`** — `intro_amount_cents` e `intro_periods` existem juntos ou não existem.
* **CHECK `intro_is_cheaper`** — preço de entrada **menor** que o regular. "Entrada" mais caro que o normal é padrão
  obscuro e o banco recusa.
* **CHECK `effective_order`** — `effective_until > effective_from`.
* `reason` obrigatório: toda versão de preço carrega por escrito por que existe.

`_sync_price_versions()` é idempotente: roda em cada migração, fecha a vigência anterior e abre a nova **apenas** se o
valor diferir. Planos com `interval: custom` (`company_enterprise`, que é por contrato) são ignorados de propósito.

## Nunca mudar preço em silêncio

Duas tabelas e dois gatilhos:

* `price_change_notices` — o aviso a cada organização assinante, com `effective_at` e `acknowledged_at`.
* **`price_notice_guard()`** — recusa aviso com menos de **30 dias** de antecedência.
* **`price_apply_guard()`** — recusa aplicar **aumento** a uma assinatura sem aviso prévio reconhecidamente enviado e
  vencido. **Redução** é livre: proteger o cliente de ficar mais barato seria absurdo.
* **`price_notice_ack_only()`** — a organização avisada pode escrever **apenas** `acknowledged_at`. (`forbid_mutation`
  bloqueava até o "ciente", o que tornava o aviso insatisfazível.)

`subscription_prices` registra qual versão de preço cada assinatura aceitou — `record_accepted_price()`. Então "quanto
esta organização paga" não é uma conta refeita a cada leitura: é um fato gravado no momento do aceite.

## O que o checkout mostra

`price_quote()` devolve, e a tela exibe nesta ordem:

| Rótulo na tela | Conteúdo |
|---|---|
| Preço do plano | US$ 19,99/mês · ou US$ 179,88/ano |
| Equivalente mensal | US$ 14,99/mês (só no anual) |
| Primeira fatura | US$ 1,99 (entrada) ou US$ 0,00 em teste |
| Depois do período de entrada | US$ 19,99/mês a partir do 4º mês pago |
| Total | o valor cheio do ciclo, sempre visível |
| Imposto | "imposto calculado no checkout" (`tax_behavior: exclusive`) |

Teste de 14 dias **com o produto completo** — não é versão reduzida: o `trial_days` concede o entitlement cheio.

## Entrada e cupom não se somam

Decisão de produto, registrada em ADR: `final = min(intro, regular − desconto)` — **o cliente recebe o melhor dos
dois**, não os dois empilhados. Empilhar levaria a primeira fatura perto de zero com renovação dez vezes maior, que é
exatamente o padrão obscuro que o pedido proíbe. A tela nomeia qual regra venceu (`first_price_source`).

## Provedor

`provider_price_id` é **`null`** de propósito: ninguém criou esses preços numa conta Stripe real, e inventar um
identificador seria mentir. Consequência verificável:

* `StripeBilling.needs_price_id = True` → checkout levanta **503 `provider_price_missing`** enquanto o id não existir.
  A plataforma **recusa cobrar** em vez de tentar com um valor inventado.
* `NoBilling` e `SandboxBilling` têm `needs_price_id = False` → desenvolvimento e teste funcionam sem conta de
  provedor.
* `price_ref()` lê `plan_price_versions.provider_price_id` **antes** de qualquer fallback.

**Estado honesto: a cobrança real não está integrada.** Não há conta Stripe, não há chave, não há preço criado no
provedor, nenhum pagamento real foi processado. O que está pronto e testado é toda a camada da plataforma: versão de
preço, vigência, aviso prévio, aceite registrado, cotação, imposto declarado e idempotência de webhook. Ligar o
provedor é: criar os dois preços na conta, gravar os ids e configurar a chave — nenhuma mudança de código.

## Idempotência de webhook

`billing_events` com `UNIQUE(provider, event_id)`: o mesmo evento reprocessado não duplica efeito. O contador
`intro_periods_used` é incrementado com `least(intro_periods_used + 1, intro_periods)` — reentrega não faz o cliente
"gastar" ciclos de entrada que não consumiu, e não deixa o contador passar do limite.

## Sem padrões obscuros

* Cancelar é uma rota, não um pedido por e-mail.
* Nenhuma renovação sem aviso de valor.
* Nenhum preço riscado que não tenha sido praticado.
* Nenhum "a partir de" sem o total.
* O teste de 14 dias não pede cartão para começar.
