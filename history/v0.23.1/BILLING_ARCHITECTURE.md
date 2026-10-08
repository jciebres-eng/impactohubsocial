# ARQUITETURA DE COBRANÇA — v0.21.0

Complementa `MONETIZATION_ARCHITECTURE.md`, que trata de **quanto** se cobra. Este trata de **como**
a cobrança acontece.

---

## 1. PROVEDORES

`backend/impacto/services/billing.py`

| Classe | Quando | `is_simulated` |
| --- | --- | --- |
| `NoBilling` | sem provedor configurado | — |
| `SandboxBilling` | desenvolvimento e homologação | **true** |
| `StripeBilling` | produção, com credencial | **false** |

`is_simulated` é **derivada do provedor** por gatilho (`charge_simulated_flag`), nunca escrita à
mão. A lista de provedores reais é explícita (`'stripe'`), e não o contrário: um provedor novo nasce
**simulado**, que é o lado seguro do engano.

Enquanto o provedor não for real, a interface declara isso em faixa visível. Nenhuma tela finge
cobrança.

---

## 2. O CAMINHO DE UMA CONTRATAÇÃO

```
1. catálogo          GET /v1/plans            preço vigente, ou "não divulgado"
2. oferta            POST /v1/commercial/offers    valor lido do catálogo
3. aceite            POST .../accept          free_access OU authorized
4. cotação           POST /v1/billing/quote   valor final, desconto, imposto, primeira fatura
5. checkout          POST /v1/billing/checkout
6. assinatura        subscriptions            + subscription_prices (preço congelado)
7. período gratuito  free_periods             3 meses, se elegível
8. cobrança          platform_charges         exige autorização vigente
9. fatura            invoices
```

Os passos 2 e 3 são novos na v0.21.0. Antes, o aceite de termos e a autorização de cobrança eram o
mesmo ato — e o fim de um período gratuito virava cobrança por omissão.

---

## 3. GRAFO DE ESTADOS DA COBRANÇA

27 transições declaradas em `charge_state_graph`, com origem permitida (`user`, `webhook`, `system`,
`admin`, `any`). O gatilho recusa qualquer transição fora do grafo.

```
created → checkout_started → pending → authorized → paid → settled
                                ↓          ↓         ↓
                             failed    cancelled  refunded / disputed / chargeback
```

A trilha (`charge_events`) é escrita **exclusivamente pelo gatilho** `charge_record_event`. Nenhum
código de aplicação escreve ali, e há teste que impede qualquer módulo de passar a escrever —
registrado como dívida D3 na v0.20.0, depois de uma inserção duplicada ter sido introduzida e
pega pelo teste.

---

## 4. IDEMPOTÊNCIA EM TRÊS CAMADAS

| Camada | Chave | Protege contra |
| --- | --- | --- |
| Webhook | `billing_events(provider, event_id)` | o provedor reenviar o mesmo evento |
| Provedor | `platform_charges(provider, provider_charge_id)` | duplicar a mesma cobrança do provedor |
| **Cliente** | `platform_charges(org_id, idempotency_key)` | o cliente repetir o pedido após queda de rede |

A terceira é nova na v0.21.0. Sem ela, quem não recebesse a resposta por queda de rede e tentasse de
novo criaria a segunda cobrança, e ninguém no sistema saberia que são a mesma.

Escopo por organização: duas podem usar a mesma string sem colidir, e uma não descobre a chave da
outra por conflito de inserção.

---

## 5. PREÇO CONGELADO

`subscription_prices` guarda o preço no momento do aceite, com `accepted_at` e `accepted_by`. Um
reajuste de tabela não altera retroativamente o que alguém contratou.

Responder *"quanto esta organização contratou em março?"* é consulta, não arqueologia.

### Aviso de 30 dias

`price_apply_guard` recusa inserir em `subscription_prices` um **aumento** sem `price_change_notices`
vigente para aquela organização. Redução não exige aviso — a carência protege quem paga, não a
plataforma.

Não há job que crie esses avisos: criar um é decisão comercial, e automatizá-la transformaria um ato
deliberado em efeito colateral de implantação.

---

## 6. WEBHOOKS

`POST /v1/billing/webhooks/stripe`, assinatura verificada por HMAC
(`stripe_signature_valid`). Assinatura inválida é registrada e descartada.

`process_event` trata: assinatura criada, atualizada, cancelada, fim de teste próximo, fatura paga,
pagamento falho, ação necessária. Cada um é idempotente pela chave do evento.

---

## 7. TAREFAS

| Tarefa | O que faz |
| --- | --- |
| `billing_lifecycle` | trial de 14 dias: lembretes, encerramento, conversão sandbox |
| `commercial_sweep` | período gratuito: encerramento e avisos 90/60/30/7/1 + semanal |
| `usage_alerts` | 70/90/100% do limite do plano |
| `payment_deadlines` | prazos de pagamento |

`billing_lifecycle` e `commercial_sweep` são separados de propósito: o trial é mecanismo de
aquisição, o período gratuito é decisão comercial. Juntá-los faria um cancelar o aviso do outro.

---

## 8. O QUE NÃO ESTÁ EXERCITADO COM PROVEDOR REAL

Honestidade de fechamento:

| Fluxo | Situação |
| --- | --- |
| Checkout real | **não** — exige credencial e contrato |
| Fatura real | **não** |
| Estorno, disputa, chargeback | estados existem no grafo; fluxo **não** exercitado |
| Boleto real | **não** — exige provedor |
| Pix real | **não** — exige provedor |
| Nota fiscal | **não** — exige provedor fiscal contratado |

Todos os testes de cobrança rodam em `sandbox`. Isso está declarado na interface, no manifesto de
release e aqui — não escondido atrás de um fluxo que parece funcionar.

---

## 9. CORREÇÕES DESTA RODADA

| Defeito | Como aparecia | Correção |
| --- | --- | --- |
| Exigência de autorização podia ser burlada | gatilho lia `is_simulated` antes de ele ser derivado do provedor | ambos os gatilhos consultam `charge_is_simulated(provider)` |
| `FORCE ROW LEVEL SECURITY` quebrava o `pg_dump` | backup falhava com erro de política | trocado por `ENABLE`; a proteção é o gatilho |
| Reajuste agendado quebrava a migração | `effective_until = now()` violava `effective_until > effective_from` | fecha em `greatest(now(), effective_from + 1µs)` |
| Cota de IA contada de dois jeitos | painel mostrava mais consumo do que o que bloqueava | função única `ai_usage_this_month()` |
| `company_premium` com intervalo errado | catálogo anunciava R$ 1.490 **por ano** para um plano mensal | `interval` passou a `month` |
