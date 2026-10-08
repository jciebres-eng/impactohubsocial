# FULL FREE 2026 E OS TRÊS MESES DE 2027

> ⚠️ **SUPERADO EM PARTE — v0.27.0 (ADR-341): NÃO EXISTE MAIS ASSINATURA.** Tudo o que este documento diz
> sobre mensalidade, plano pago, trial, checkout, reajuste, portal e cancelamento descreve um modelo que o
> proprietário retirou do IMPACTO em 08/10/2026. O que continua valendo: núcleo gratuito por desenho, o que
> o dinheiro nunca compra, acesso gratuito ≠ autorização de cobrança, regras transacionais desligadas. O
> modelo vigente está em `docs/ECONOMIC_MODEL.md` e `MONETIZATION.md`; o inventário do que foi mantido,
> migrado, aposentado e removido está em `docs/execution/SUBSCRIPTION_INVENTORY.md`. O texto abaixo fica
> como histórico — ele explica contratos e decisões anteriores — e NÃO deve ser lido como regra atual.


**Versão:** v0.21.0 · **Pricing Version:** 2027.01
**Implementação:** `backend/impacto/services/free_period.py`, migração `0042_v0210_free_period.sql`
**Testes:** `backend/tests/test_v0210_free_period.py` (25 testes)

---

## 1. A REGRA

| | |
| --- | --- |
| **Gratuidade total** | até `2026-12-31 23:59:59` no fuso `America/Sao_Paulo` |
| **Tabela comercial** | a partir de `2027-01-01 00:00:00` (`America/Sao_Paulo`) |
| **Assinatura nova a partir de 2027** | 3 meses de calendário gratuitos |
| **Fim do período sem autorização de cobrança** | a conta volta ao plano gratuito. Sem cobrança, sem suspensão, sem perda de dados |

---

## 2. POR QUE A GRATUIDADE É UM REGISTRO, E NÃO UMA DATA NO CÓDIGO

A implementação óbvia seria uma constante comparada com `now()`. Ela responde a uma pergunta que
ninguém faz: *"estamos antes de 2027?"*

As perguntas reais são outras — **esta conta** está gratuita? até quando? por quê? quem concedeu?
o que ela aceitou? — e uma constante não sabe nada sobre uma conta. No dia em que o proprietário
quiser estender o prazo de dois clientes e não dos outros, uma constante exige mudar código,
implantar e torcer.

Então cada conta tem a sua linha em `free_periods`:

```
account_id · subscription_id · source · reason · pricing_version · plan_key
started_at · ends_at · months · status · granted_by · cancelled_at/by/reason
```

A campanha de 2026 é o que **concede** essas linhas — não o que as substitui. Um teste
(`test_the_campaign_date_is_not_hardcoded_across_the_product`) varre o código de produto e falha
se `2026-12-31` ou `2027-01-01` reaparecerem escritos em qualquer arquivo Python ou TSX.

### Origens de concessão

`2026_CAMPAIGN` · `2027_NEW_SUBSCRIPTION` · `PROMOTION` · `GRANT` · `PARTNERSHIP` ·
`MANUAL_EXCEPTION`

Toda concessão exige motivo. Cortesia sem motivo registrado é indistinguível de erro de operação
quando alguém for auditar.

---

## 3. "TRÊS MESES" SIGNIFICA TRÊS MESES DE CALENDÁRIO

**Decisão: meses de calendário. Não 90 dias.** (ADR-268)

### Por quê

O cliente compara o fim do período com a data em que assinou: *"assinei dia 15, acaba dia 15."*
Noventa dias quebram essa expectativa em todo trimestre que contenha um mês de 31 dias — e quebram
**para menos**, que é o lado que a pessoa percebe.

| Assinatura | 3 meses de calendário | 90 dias | Diferença |
| --- | --- | --- | --- |
| 01/03/2027 | 01/06/2027 | 30/05/2027 | −2 dias |
| 01/05/2027 | 01/08/2027 | 30/07/2027 | −2 dias |
| 01/01/2027 | 01/04/2027 | 01/04/2027 | **coincidem** |

A última linha é a armadilha: em 2027, janeiro + fevereiro + março somam exatamente 90 dias. Quem
testar a regra de 90 dias com uma assinatura de 1º de janeiro verá os dois métodos concordarem e
concluirá que são equivalentes. Há um teste dedicado a essa coincidência
(`test_ninety_days_sometimes_coincides_with_three_months_which_is_the_trap`), para que a próxima
pessoa a ler o código encontre a explicação junto com o caso.

### Dia que não existe no mês de destino

O fim é o **último dia do mês de destino**:

| Assinatura | Fim |
| --- | --- |
| 31/01/2027 | 30/04/2027 |
| 30/11/2026 | 28/02/2027 |
| 30/11/2027 | 29/02/2028 (bissexto) |
| 31/03/2027 | 30/06/2027 |

A alternativa — transbordar para 01/05 — daria ao cliente um dia a mais em silêncio e faria o fim
do período depender do mês em que ele assinou, que é exatamente o que meses de calendário evitam.

---

## 4. `ends_at` É EXCLUSIVO

O período é `[started_at, ends_at)`.

"Gratuito até 31/12/2026 23:59:59" fica gravado como `ends_at = 2027-01-01 00:00:00` em
`America/Sao_Paulo`. Escrever `23:59:59` literalmente deixaria `23:59:59,5` sem classificação — nem
gratuito, nem pago. Um defeito de meio segundo, uma vez por ano, à meia-noite: exatamente quando
ninguém está olhando.

Os quatro instantes da fronteira estão sob teste:

| Instante local (São Paulo) | Dentro da campanha? |
| --- | --- |
| 2026-12-31 23:59:58 | sim |
| 2026-12-31 23:59:59 | sim |
| 2027-01-01 00:00:00 | **não** |
| 2027-01-01 00:00:01 | não |

---

## 5. FUSO HORÁRIO

O projeto inteiro opera em UTC: 529 colunas `timestamptz`, zero sem fuso, e um teste de arquitetura
que proíbe `date.today()`. **Isso não muda.**

O fuso comercial `America/Sao_Paulo` vive na **fronteira** — ao calcular o fim de uma campanha e ao
formatar datas para pessoas. Trocar a convenção interna por causa de uma regra comercial faria toda
consulta do sistema pagar um preço que pertence a esta tabela.

O caso que separa uma implementação certa de uma errada:

> **2027-01-01 02:00 UTC ainda é 2026-12-31 23:00 em São Paulo.**

Um sistema que comparasse a data UTC com `'2026-12-31'` cortaria a gratuidade de todo mundo **três
horas antes** da virada real. Há teste para esse instante.

Nota de dívida corrigida: `monetization.py:366` formatava datas de aviso com offset **fixo**
`-04:00`, comentado como `America/Cuiaba`. Offset fixo não acompanha mudança de regra de fuso.

---

## 6. ACESSO GRATUITO ≠ AUTORIZAÇÃO DE COBRANÇA

| | Acesso gratuito | Autorização de cobrança |
| --- | --- | --- |
| O que é | direito de usar sem pagar | permissão para debitar um meio de pagamento |
| Exige meio de pagamento | **não** | sim |
| Onde fica | `free_periods` | `offer_acceptances` com `consent_status = 'authorized'` |
| Como é dado | concessão da plataforma | **ato explícito** de quem aceita |

**O fim do período gratuito não autoriza nada.** Sem autorização vigente:

* a conta **não é cobrada** — um gatilho de banco (`charge_requires_authorization`) recusa a
  cobrança, e ele vale contra todo caminho de escrita, inclusive os que ainda não existem;
* a conta **não é suspensa** — ela volta ao plano gratuito, que é permanente;
* **nenhum dado é apagado.**

Os avisos dizem isso em letras, e não em código de estado: *"Você NÃO será cobrado... Se não fizer
nada, sua conta continua no plano gratuito, sem perder dados."*

---

## 7. ESTADOS COMERCIAIS

`FREE` · `FREE_EXPIRING` · `PAYMENT_METHOD_REQUIRED` · `COMMERCIAL_TERM_PENDING` · `PAID_ACTIVE` ·
`CANCELLED` · `SUSPENDED` · `PAST_DUE` · `GRACE_PERIOD` · `TERMINATED`

Derivados por `org_commercial_state(org_id)`, **não guardados em coluna**. Uma conta "vira" paga à
meia-noite sem ninguém rodar nada; uma coluna só mudaria quando algum job passasse, deixando a tela
e a cobrança discordando justamente na virada.

`PAYMENT_METHOD_REQUIRED` não é erro: é o estado em que faltam 30 dias ou menos e ninguém autorizou
cobrança. O cliente pode simplesmente não fazer nada.

---

## 8. AVISOS

**90, 60, 30, 7 e 1 dia** antes do fim, mais **lembrete semanal** nos últimos 30 dias, mais um aviso
**no fim**.

Fonte única da data: `free_period_end(org_id)` → `FREE_PERIOD_END`. Quando há mais de um período
vigente (campanha + cortesia), vale o que **termina depois** — o cliente recebeu os dois, e tirar o
melhor seria quebrar a promessa menor. E só o período que termina por último dispara aviso: alertar
pelo que acaba primeiro assustaria o cliente com um prazo que não é o dele.

A interface **nunca calcula essa data**. Um teste varre o frontend em busca de aritmética de datas
perto de qualquer coisa chamada `free`/`period`/`trial` e falha se encontrar.

---

## 9. CONVIVÊNCIA COM O TESTE DE 14 DIAS

O trial de 14 dias (`org_trials`, desde a v0.11.0) **continua existindo**. Ele é mecanismo de
**aquisição**; o período gratuito é decisão **comercial**. Os dois coexistem numa mesma conta, e
`free_period_end` devolve o que termina depois.

Nada foi apagado para abrir espaço para o novo.

---

## 10. IMUTABILIDADE

Concessão é fato. `org_id`, `source`, `pricing_version`, `started_at`, `ends_at`, `months` e
`granted_by` não se reescrevem — **nem pela administração, nem pelo dono do banco**. Um gatilho
(`free_period_immutable`) recusa a alteração para todos.

Para tirar um período concedido, **cancela-se com motivo e autor**, e o registro fica. Apagar a
linha apagaria a prova de que a plataforma concedeu — que é exatamente o que o cliente invocaria se
discordasse do cancelamento. Um período cancelado não volta a valer.

---

## 11. O QUE NÃO ESTÁ RESOLVIDO

1. As 11 minutas jurídicas continuam em `draft`. Enquanto estiverem, nenhum aceite legal é gravado
   (o gatilho `acceptance_stamp` recusa aceite de documento não aprovado). Aprovar minuta é ato
   humano com responsabilidade profissional.
2. Não há preço de excedente publicado. Sem ele, excedente é bloqueado ou avisado — nunca cobrado.
3. A integração real com provedor de pagamento continua em modo sandbox, e a interface diz isso.
