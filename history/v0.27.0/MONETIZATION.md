# Monetização: regras, elegibilidade e o portão legal (v0.17.0)

> Escrito a partir de `backend/migrations/0020_v0170_monetization.sql`,
> `0021_v0170_legal_cards.sql` e `backend/impacto/economics/billable.py`. 26 testes em
> `backend/tests/test_v0170_monetization.py`, incluindo 7 de auditoria legal.

## 1. A regra que governa este módulo

**Nenhuma receita é ativável sem cartão legal verde.** O portão está no banco
(`monetization_rule_gate()`), não na interface, e a mensagem de erro dele cita a decisão que o
fundamenta.

## 2. As dez regras e a situação de cada uma

`monetization_rules` traz dez linhas (nove até a v0.25.0; a décima chegou na v0.26.0), ordenadas por `engine_rank` — a prioridade do produto:

| # | Chave | Motor | Situação |
|---|---|---|---|
| 1 | `saas.institutional.funder` | `saas_institutional` | ⛔ `refused` (v0.27.0, ADR-341: não existe assinatura) |
| 2 | `b2g.territorial_governance` | `b2g` | ⛔ `refused` |
| 3 | `enterprise.esg_portfolio` | `enterprise` | ⚠️ `review_required` |
| 4 | `implementation.setup` | `implementation` | ⚠️ `review_required` |
| 5 | `marketplace.take_rate` | `marketplace_take_rate` | ⛔ `refused` |
| 6 | `success_fee.funding` | `success_fee` | ⛔ `refused` |
| 7 | `premium.readiness_analysis` | `proponent_premium` | ⚠️ `review_required` |
| 7 | `premium.document_preparation` | `proponent_premium` | ⚠️ `review_required` |
| 8 | `data.territorial_intelligence` | `data_intelligence` | ⛔ `refused` |
| 3 | `contract.platform_service_fee` | `enterprise` | ⚠️ `review_required` (v0.26.0) |

**Zero verdes, e nenhuma ativa** (`active = false` nas dez). Cinco amarelas (falta parecer), cinco
vermelhas (recusadas — a quinta, `saas.institutional.funder`, por decisão comercial do proprietário na
v0.27.0: a assinatura saiu do modelo econômico, ADR-341). O cartão legal de cada uma, com texto literal de fonte oficial e data de consulta,
está em `MONETIZATION_LEGAL_MATRIX.md`.

Dois campos são **NOT NULL** e decidem se a regra entra no banco:

- `problem_solved` — qual problema caro ela resolve;
- `substitution_answer` — o que ela substitui na vida de quem paga.

"Não venda 20 funcionalidades por R$ 99. Venda um problema caro resolvido" deixou de ser conselho e
passou a ser restrição de esquema.

## 3. As cinco recusas, e por que são recusas e não pendências (a quinta, a assinatura, está no §9)

### `success_fee` e `marketplace_take_rate` — recusa de arquitetura

```sql
IF NEW.revenue_engine IN ('success_fee','marketplace_take_rate') THEN
  RAISE EXCEPTION 'ADR-022: a plataforma não custodia nem processa aporte, então % não pode ser '
                  'ativada. A infraestrutura de cálculo existe e fica desligada até haver parecer '
                  'e revisão da ADR-022.', NEW.revenue_engine USING ERRCODE = '42501';
END IF;
```

Cobrar percentual sobre um valor que a Plataforma **não vê** não é verificável. E receber recurso de
terceiro para repassar pode caracterizar atividade de instituição de pagamento, sujeita a autorização do
Banco Central (Lei 12.865/2013, art. 6º e art. 9º, V). Quando o recurso é público, somam-se as regras de
parceria da Lei 13.019/2014. A infraestrutura de cálculo existe e está desligada; ligá-la exige parecer
jurídico **e** reabrir a ADR-022, porque é a arquitetura que precisa mudar antes da receita.

### `b2g` — recusa do MECANISMO, não do cliente

Esta recusa é a mais fácil de ler errado, então vale precisão: **vender para o poder público não está
recusado.** O que está recusado é **cobrar o órgão por checkout de autosserviço**. Oferecer contratação
online a um órgão sem procedimento prévio é o risco central da modalidade — a contratação depende do
procedimento da Lei 14.133/2021 aplicável ao caso, cuja escolha é do órgão e de sua assessoria jurídica.

Na prática: o contrato B2G existe (minuta em `docs/legal/B2G.md`), e o caminho dele é contrato e nota
fiscal, não botão de pagar. O motor automático fica desligado.

### `data_intelligence` — recusa por privacidade, não por tributo

Vender inteligência territorial agregada. Dado anonimizado não é dado pessoal (LGPD art. 12), **mas
deixa de valer essa regra se a anonimização puder ser revertida com esforços razoáveis** — e agregado
territorial com contagem pequena é exatamente onde a reidentificação acontece. Enquanto não houver
limite mínimo de agregação definido por quem entende do assunto, a receita fica recusada.

## 4. O cartão legal e as duas travas dele

`monetization_legal_cards` é append-only, e tem dois CHECK que impedem o atalho mais tentador:

| CHECK | O que impede |
|---|---|
| `green_needs_evidence` | cartão verde sem fonte citada. **Ausência de proibição não é permissão** |
| `green_has_no_open_questions` | cartão verde com pergunta aberta registrada |

Um cartão verde, portanto, precisa dizer: qual norma, qual artigo, qual texto literal, qual URL, qual
data de consulta — e não pode ter pergunta pendente. Nenhum dos nove tem.

## 5. A cadeia completa

```
value_events  →  app_promote_billable()  →  billable_events  →  monetization_rules  →  platform_charges
  (entrega)         (só regra ATIVA)          (candidato)          (portão legal)        (cobrança)
```

`billable_events` guarda `status` e **`reason`** — por que este evento é ou não cobrável. Os seis
estados dizem exatamente onde cada evento parou: `candidate`, **`blocked_legal`** (a regra existe e não
passou no portão), **`blocked_no_price`** (passou no portão e não há preço declarado), `eligible`,
`billed` e `waived` (dispensado, com o motivo registrado).

Como nenhuma regra está ativa, **nenhum evento de valor se torna cobrável hoje**. `pipeline()` mostra o
funil com zero na ponta, e isso é o estado verdadeiro.

## 6. Quem pode ser cobrado

A matriz completa está em `MONETIZATION_LEGAL_MATRIX.md` §3. O resumo:

| Perfil | Pode ser cobrado por | Nunca pode ser cobrado por |
|---|---|---|
| OSC proponente | premium opcional de aquisição | cadastro, perfil, projeto, descoberta, rede, acompanhamento básico |
| Empresa / instituto / fundação | SaaS institucional, Enterprise/ESG, implantação | percentual sobre aporte |
| Órgão público | SaaS B2G, implantação | — |
| Profissional parceiro | assinatura própria | percentual sobre serviço contratado (recusado) |

E o caso que a matriz trata à parte: **órgão público pode ser cliente, mas não por checkout** — ver a
recusa do motor `b2g` no §3.

## 7. Preço

Nenhum preço de regra de monetização está declarado no sistema, e nenhum está embutido no código.
v0.27.0 (ADR-341): **não há preço de plano** — não existe assinatura. Os percentuais da camada econômica
(3,5% + 1,5%) vivem em `economic_rules`, versionados (Pricing Version 2027.02) e congelados em cada
acordo; o valor de um contrato avulso/parcelado é decidido por quem tem alçada (`finance.approve`), com
motivo e auditoria, nunca pelo cliente.

`set_rule()` preserva a mensagem do portão: `InsufficientPrivilege` e `IntegrityError` viram
`ApiError(422, "monetization_gate", ...)` com a primeira linha da exceção, porque o tratador global
substitui 403 por uma mensagem genérica — e a mensagem genérica esconderia justamente a razão da recusa.

## 8. A taxa de serviço contratada no acordo (v0.26.0)

`contract.platform_service_fee` é a décima regra, e é a que materializa o §4 de
`NON_CUSTODIAL_ARCHITECTURE.md` ("take rate sem custódia") para o acordo de financiamento:

- **O percentual não é da plataforma: é do contrato.** `percentage` fica `NULL` na regra; o valor
  vem de `signed_agreements.platform_fee_bps`, escrito no acordo que as partes assinam. Não existe
  "3%" no código — o teste `test_without_a_contracted_fee_there_is_no_fee_line_at_all` prova que sem
  cláusula não há linha de taxa.
- **Quem paga é quem o contrato diz** (`fee_payer_role`: financiador, contratante ou prestador). O
  desenho recomendado é o financiador pagar a taxa diretamente à plataforma, em **cobrança própria**
  (`platform_charges`, tipo `operation`), e pagar o projeto diretamente à OSC. A OSC nunca
  desembolsa para pagar a plataforma e nenhum valor de terceiro passa pela plataforma.
- **A taxa é calculada na origem**, quando o acordo entra em vigor, e gravada em
  `agreement_allocations` com hash — a matriz de distribuição: bruto, projeto, taxa, terceiros, cada
  linha dizendo quem paga a quem e por qual meio. `fee_mode = additional` (padrão) deixa o projeto
  com o valor cheio; `deducted` é permitido pelo contrato, e a soma fecha nos dois modos por CHECK.
- **GMV ≠ receita.** O valor contratado não entra em `revenue_recognized`; só a taxa cobrável.
- **Nasce desligada e assim fica** até carta legal verde (`monetization_rule_gate`). Enquanto isso a
  taxa é **registrada e não cobrada**: `fee_chargeable = false`, com o motivo na própria matriz. O
  que falta está na carta amarela: parecer de que o desenho não configura arranjo de pagamento (Lei
  12.865/2013), alíquota e município do ISS, redação da cláusula, nota fiscal.

A prova: `backend/tests/test_v0260_contract_rules.py` (R$ 100.000 com 3% → R$ 100.000 ao projeto e
R$ 3.000 de taxa registrada; no modo descontado 97.000 / 3.000; cobrança própria ao financiador só com
a regra ativa; mudança de contrato gera versão nova e invalida a aprovação anterior).

## 9. O que a v0.27.0 mudou (ADR-341): não existe mais assinatura

A primeira regra do catálogo, `saas.institutional.funder` (SaaS institucional para quem financia, por
mensalidade), foi **recusada** com carta vermelha — não por impedimento jurídico, mas por decisão de
produto: o IMPACTO não vende acesso. O núcleo é gratuito por desenho; pacotes além dele vêm de contrato,
concessão, convênio ou voucher; a receita da plataforma nasce da **camada econômica da operação
financiada** (§8 — agora com percentual do catálogo `economic_rules`, 350 bps, congelado no acordo, e
mais 150 bps de participação de autoria ao proponente quando elegível) e de **contratos avulsos ou
parcelados**. A arquitetura de assinatura (tabelas, rotas, job, telas, textos) foi inventariada
ocorrência a ocorrência e removida, migrada ou aposentada — `docs/execution/SUBSCRIPTION_INVENTORY.md`.
O que a v0.26.0 provava com 3% fixado no contrato continua valendo com 3,5% vindo do catálogo:
`test_v0260_contract_rules.py` (atualizado) e `test_v0270_economy.py`.

