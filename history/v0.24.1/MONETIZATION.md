# Monetização: regras, elegibilidade e o portão legal (v0.17.0)

> Escrito a partir de `backend/migrations/0020_v0170_monetization.sql`,
> `0021_v0170_legal_cards.sql` e `backend/impacto/economics/billable.py`. 26 testes em
> `backend/tests/test_v0170_monetization.py`, incluindo 7 de auditoria legal.

## 1. A regra que governa este módulo

**Nenhuma receita é ativável sem cartão legal verde.** O portão está no banco
(`monetization_rule_gate()`), não na interface, e a mensagem de erro dele cita a decisão que o
fundamenta.

## 2. As nove regras e a situação de cada uma

`monetization_rules` traz nove linhas, ordenadas por `engine_rank` — a prioridade do produto:

| # | Chave | Motor | Situação |
|---|---|---|---|
| 1 | `saas.institutional.funder` | `saas_institutional` | ⚠️ `review_required` |
| 2 | `b2g.territorial_governance` | `b2g` | ⛔ `refused` |
| 3 | `enterprise.esg_portfolio` | `enterprise` | ⚠️ `review_required` |
| 4 | `implementation.setup` | `implementation` | ⚠️ `review_required` |
| 5 | `marketplace.take_rate` | `marketplace_take_rate` | ⛔ `refused` |
| 6 | `success_fee.funding` | `success_fee` | ⛔ `refused` |
| 7 | `premium.readiness_analysis` | `proponent_premium` | ⚠️ `review_required` |
| 7 | `premium.document_preparation` | `proponent_premium` | ⚠️ `review_required` |
| 8 | `data.territorial_intelligence` | `data_intelligence` | ⛔ `refused` |

**Zero verdes, e nenhuma ativa** (`active = false` nas nove). Cinco amarelas (falta parecer), quatro
vermelhas (recusadas). O cartão legal de cada uma, com texto literal de fonte oficial e data de consulta,
está em `MONETIZATION_LEGAL_MATRIX.md`.

Dois campos são **NOT NULL** e decidem se a regra entra no banco:

- `problem_solved` — qual problema caro ela resolve;
- `substitution_answer` — o que ela substitui na vida de quem paga.

"Não venda 20 funcionalidades por R$ 99. Venda um problema caro resolvido" deixou de ser conselho e
passou a ser restrição de esquema.

## 3. As quatro recusas, e por que são recusas e não pendências

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

Nenhum preço de regra de monetização está declarado no sistema, e nenhum está embutido no código. O
preço de plano vive em `plan_price_versions` com vigência e motivo; o preço institucional é decisão
comercial do proprietário.

`set_rule()` preserva a mensagem do portão: `InsufficientPrivilege` e `IntegrityError` viram
`ApiError(422, "monetization_gate", ...)` com a primeira linha da exceção, porque o tratador global
substitui 403 por uma mensagem genérica — e a mensagem genérica esconderia justamente a razão da recusa.
