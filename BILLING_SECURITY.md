# SEGURANÇA DA CAMADA DE COBRANÇA — v0.21.0

> ⚠️ **SUPERADO EM PARTE — v0.27.0 (ADR-341): NÃO EXISTE MAIS ASSINATURA.** Tudo o que este documento diz
> sobre mensalidade, plano pago, trial, checkout, reajuste, portal e cancelamento descreve um modelo que o
> proprietário retirou do IMPACTO em 08/10/2026. O que continua valendo: núcleo gratuito por desenho, o que
> o dinheiro nunca compra, acesso gratuito ≠ autorização de cobrança, regras transacionais desligadas. O
> modelo vigente está em `docs/ECONOMIC_MODEL.md` e `MONETIZATION.md`; o inventário do que foi mantido,
> migrado, aposentado e removido está em `docs/execution/SUBSCRIPTION_INVENTORY.md`. O texto abaixo fica
> como histórico — ele explica contratos e decisões anteriores — e NÃO deve ser lido como regra atual.


Este documento descreve o que **impede** abuso na camada comercial, e onde cada proteção mora.
Regra geral do projeto: proteção comercial mora no **banco**, não na aplicação. Um módulo pode ser
contornado por outro caminho de escrita; um gatilho e uma política de linha, não.

---

## 1. ISOLAMENTO ENTRE ORGANIZAÇÕES

Todas as tabelas comerciais novas têm RLS com política por organização:

| Tabela | Leitura | Escrita |
| --- | --- | --- |
| `free_periods` | própria organização, administração, sistema | **só** administração e sistema |
| `commercial_offers` | própria organização | própria organização (valor vem do catálogo) |
| `offer_acceptances` | própria organização | própria organização (o aceite é ato do cliente) |
| `usage_counters` | própria organização | **só** sistema |
| `usage_alerts` | própria organização | **só** sistema |
| `spend_limits` | própria organização | própria organização (o teto é dela) |

`DELETE` revogado para o papel da aplicação em todas as seis.

### `ENABLE`, não `FORCE`

Nenhuma tabela usa `FORCE ROW LEVEL SECURITY`. A primeira versão desta rodada usou, e isso quebrou
o `pg_dump`: FORCE aplica as políticas também ao **dono** da tabela, e o dono é quem roda o backup.
O erro era `query would be affected by row-level security policy` — um backup que falha em silêncio
é pior do que não ter backup. O teste de backup (`test_v0190_ops`) pegou.

O modelo de segurança não depende de FORCE: a aplicação conecta como `impacto_app`, que é
`NOSUPERUSER`, `NOBYPASSRLS` e não-dono das tabelas. Quem impede a reescrita pelo dono é o
**gatilho**, que dispara para todo mundo.

---

## 2. A INVARIANTE CENTRAL: SEM AUTORIZAÇÃO, SEM COBRANÇA

```sql
CREATE TRIGGER trg_charge_requires_authorization BEFORE INSERT ON platform_charges ...
```

Uma cobrança real (`provider = 'stripe'`) com valor maior que zero exige um aceite com
`consent_status = 'authorized'` e `revoked_at IS NULL` para aquela organização. Sem ele, o INSERT é
recusado com `42501`.

### Ordem de gatilhos — defeito encontrado e corrigido

Gatilhos `BEFORE INSERT` disparam em **ordem alfabética do nome**.
`trg_charge_requires_authorization` vem **antes** de `trg_charge_simulated`, que é quem deriva
`is_simulated` do provedor. A primeira versão lia a coluna — que, naquele instante, ainda contém o
valor que o chamador enviou.

Bastava mandar `is_simulated = true` com `provider = 'stripe'` para escapar da exigência; o gatilho
seguinte então marcaria a cobrança como real. Corrigido: ambos perguntam a
`charge_is_simulated(provider)`.

Teste: `test_declaring_a_charge_simulated_does_not_bypass_the_requirement`.

---

## 3. IMUTABILIDADE DE PROVA

| O que | Gatilho | Alcance |
| --- | --- | --- |
| Versão de preço | `price_version_immutable` (0017) | papel da aplicação |
| Período gratuito concedido | `free_period_immutable` (0042) | **todos**, dono do banco inclusive |
| Aceite de oferta | `acceptance_immutable` (0043) | **todos** |
| Trilha de cobrança | `charge_record_event` (0022) | escrita **só** por gatilho |

A reescrita mais tentadora de todas — transformar um aceite de acesso gratuito em autorização de
cobrança depois do fato — é recusada: *"aceite é prova e não se altera; para desfazer, revogue"*.

Revogar é um `UPDATE`, não um `DELETE`: a prova de que o cliente autorizou em março continua, e a de
que revogou em maio entra ao lado. Apagar a primeira destruiria a justificativa das cobranças que já
aconteceram.

---

## 4. O VALOR NUNCA VEM DE QUEM PEDE

`POST /v1/commercial/offers` **não aceita** `amount_cents`. O schema recusa o pedido inteiro com 422
`extra_forbidden` — não ignora o campo em silêncio. Ignorar seria aceitar a requisição e devolver
outro valor, deixando quem integra achando que mandou um preço válido.

O valor é lido de `plan_price_versions` pela chave do plano e pelo intervalo. Sem versão vigente, a
oferta é recusada com 409 `price_not_defined` — a plataforma recusa em vez de inventar.

---

## 5. REGRAS DE MEIO DE PAGAMENTO, NO SERVIDOR

A tela é uma sugestão; a API é a porta. `offers.validate_payment_terms()` é chamada pelo serviço, e
há teste que a exercita **sem passar por rota nenhuma**.

| Regra | Código de erro |
| --- | --- |
| Boleto parcelado exige CNPJ | `boleto_installments_require_cnpj` |
| Parcelamento exige número de parcelas | `installments_required` |
| Recorrência não aceita parcelas | `installments_not_applicable` |
| Boleto não é recorrente (não tem débito automático) | `boleto_not_recurring` |
| Teto: 24 parcelas no cartão, 12 no boleto | `installments_above_limit` |

**Por que boleto parcelado só para CNPJ:** parcelamento em boleto é venda a prazo — cada parcela é
um título com vencimento futuro, sem a garantia que a bandeira de cartão oferece. Para pessoa
física isso é concessão de crédito, com o regime consumerista que vem junto. A plataforma não
concede crédito a pessoa física.

---

## 6. IDEMPOTÊNCIA

| Camada | Chave |
| --- | --- |
| Webhook do provedor | `billing_events(provider, event_id)` UNIQUE |
| Cobrança no provedor | `platform_charges(provider, provider_charge_id)` UNIQUE |
| **Cliente** | `platform_charges(org_id, idempotency_key)` UNIQUE |
| Aviso comercial | `billing_notices(org_id, kind, ref)` PK |
| Alerta de uso | `usage_alerts(org_id, metric, period_start, threshold)` PK |
| Concessão de campanha | `ux_free_period_campaign(org_id, source)` |

A chave do cliente é **escopada por organização**: duas organizações podem usar a mesma string sem
colidir, e — o que importa mais — uma não descobre a chave da outra por conflito de inserção.

---

## 7. AUTORIZAÇÃO ÚNICA VIGENTE

`ux_acceptance_one_live` garante **uma** autorização de cobrança viva por organização. Duas seriam
duas respostas para "o cliente autorizou o quê?", e a cobrança teria de escolher uma — em silêncio.
Ao autorizar de novo, a anterior é revogada com motivo registrado.

---

## 8. TETO DE GASTO

`spend_limits` é escrito pela **organização**, não só pela administração. Uma plataforma que só deixa
o suporte mexer no teto de gasto do cliente está tratando uma proteção dele como um favor dela.

Cobrança **simulada não conta** para o teto: um ambiente de teste não pode disparar o `hard_stop` de
um cliente real. E `is_simulated` é derivada do provedor por gatilho — não se escreve à mão.

---

## 9. O QUE NÃO ESTÁ PROTEGIDO, E POR QUÊ

| Risco | Situação | Por quê |
| --- | --- | --- |
| Fraude no provedor de pagamento | **não tratada aqui** | a plataforma não custodia valor; o provedor é quem autentica o pagamento |
| Estorno e disputa | estados existem (`refunded`, `disputed`, `chargeback`), fluxo não exercitado com provedor real | exige credencial e contrato |
| Lavagem via marketplace | **não aplicável hoje** | a plataforma não intermedeia pagamento de serviço (ADR-022) |
| Preço errado publicado | mitigado, não impedido | versão nova é auditável e reversível; nada impede publicar um valor errado — o aviso de 30 dias dá tempo de corrigir |
