# Arquitetura econômica da Plataforma (v0.17.0)

> Escrito a partir do código, não da intenção. Cada afirmação aqui tem tabela, função ou teste
> correspondente, e os pontos em que a Plataforma **não** pode cobrar estão declarados como tais.

## 1. A tese, e a inversão que ela exige

A tese desta rodada, nas palavras do próprio pedido: **o proponente não pode ser o pagador principal.**
Uma OSC que precisa de R$ 80 mil para um projeto não é cliente de software — ela é a razão de o software
existir. Cobrar dela para que ela consiga captar inverte o produto.

Consequência concreta e implementada: **cadastro, perfil, criação de projeto, descoberta de
oportunidades, participação na rede e acompanhamento básico são gratuitos e permanecem gratuitos.** O
plano `osc_basic` chama-se "OSC — gratuito" em `config/plans.json`, e os limites dele são técnicos
(projetos ativos, requisições de IA, armazenamento, assentos, buscas salvas) — não paredes de cobrança:
ao atingir o limite, a organização continua com acesso ao que já criou.

Quem paga, em ordem de prioridade do produto:

| Prioridade | Motor de receita | Quem paga | Situação legal |
|---|---|---|---|
| 1 | SaaS institucional | empresa, instituto, fundação | ⚠️ pendente de parecer |
| 2 | B2G | órgão público | ⛔ **cobrança automática recusada** — o cliente é legítimo, o checkout de autosserviço não |
| 3 | Enterprise / ESG | grande empresa | ⚠️ pendente de parecer |
| 4 | Implantação | quem contrata | ⚠️ pendente de parecer |
| 5 | Take rate de marketplace | profissional anunciante | ⛔ **recusada** (ADR-022) |
| 6 | Success fee sobre aporte | financiador | ⛔ **recusada** (ADR-022) |
| 7 | Premium do proponente (duas regras) | OSC, por escolha | ⚠️ pendente — aquisição, nunca o núcleo |
| 8 | Inteligência territorial | quem compra dado agregado | ⛔ **recusada** — risco de reidentificação |

Nove regras estão cadastradas em `monetization_rules`; **nenhuma está verde e nenhuma está ativa**. Cinco
estão amarelas (falta parecer) e quatro estão vermelhas. O detalhamento, com fonte oficial e data de cada
uma, está em `MONETIZATION_LEGAL_MATRIX.md`; a leitura de cada recusa está em `MONETIZATION.md` §3.

## 2. A cadeia que nenhuma cobrança pode furar

```
evento de valor  →  elegibilidade  →  regra de monetização  →  VALIDAÇÃO LEGAL  →  cobrança
 (value_events)    (billable_events)   (monetization_rules)  (monetization_legal_cards) (platform_charges)
```

Cada seta é uma trava real, não uma etapa de processo:

- **`value_events` é append-only e o app não tem INSERT nela.** Só `app_record_value()`, função
  `SECURITY DEFINER`, escreve — então o valor entregue nunca é informado por quem vai cobrar.
- **`app_promote_billable()`** é quem transforma evento de valor em evento cobrável, e só para regra
  ativa.
- **`monetization_rule_gate()`** recusa ativar regra sem cartão legal verde. Para `success_fee` e
  `marketplace_take_rate` a recusa é incondicional, com a ADR-022 citada na mensagem de erro.
- **`green_needs_evidence`** recusa cartão legal verde que não cite fonte, e
  **`green_has_no_open_questions`** recusa verde com pergunta aberta. Ausência de proibição não é
  permissão.
- **`platform_charges.is_simulated`** é derivada do provedor, e `platform_revenue()` nunca soma
  simulado com real.

## 3. Registro de valor separado da cobrança

`VALUE_LEDGER.md` detalha. O que importa aqui é a separação: **o que a Plataforma entregou** e **o que a
Plataforma cobrou** são dois registros distintos, porque juntá-los faz o número da entrega servir à
conta. Onze tipos de evento de valor estão cadastrados, cada um com o campo `what_counts` dizendo o que
conta e o que não conta.

E a trava que mais incomoda, de propósito: **nenhuma linha de base tem número.** Existe uma linha por
tipo de evento, todas com `minutes_per_unit` nulo e a nota "não definida", para que a ausência seja
visível em vez de silenciosa. Enquanto ninguém declarar "quanto tempo esta tarefa levava antes", com
fonte, data e método, nenhum evento produz estimativa de tempo economizado — fica marcado `no_baseline`.
"Economizamos 40 horas por mês" sem linha de base é marketing com cara de métrica.

## 4. O que a Plataforma não faz, e por que isso é econômico e não técnico

- **Não custodia nem processa aporte** (ADR-022/031). O dinheiro entre financiador e OSC circula fora;
  aqui ele é registrado e conferido pelas partes, com comprovante anexado por quem o detém.
- Logo, **não há success fee**: cobrar percentual de um valor que a Plataforma não vê não é verificável.
- **Não há take rate de marketplace**: mesmo raciocínio.
- **Não há cobrança automática de órgão público**: a contratação depende do procedimento da Lei
  14.133/2021 aplicável, e oferecer checkout a um órgão sem procedimento prévio é o risco central da
  modalidade.
- **Não há nota fiscal automatizada** nem provedor fiscal contratado.
- **Não há provedor de pagamento configurado.** Nenhuma cobrança real foi processada por este código.

Essas quatro ausências são a parte do modelo econômico que não se resolve programando. Elas se resolvem
com parecer jurídico, contador e contrato — e estão listadas, uma a uma, com o que falta, em
`MONETIZATION_LEGAL_MATRIX.md` §5.

## 5. Preço: onde está e onde não está

**Nenhum preço está embutido no código.** O preço vigente vive em `plan_price_versions`, com início de
vigência, moeda e motivo; mudar preço abre versão nova e **não** atinge vigência em curso. Há teste de
arquitetura (`test_prices_are_not_hard_coded`) que varre `impacto/` e `web/src/` procurando
`*_cents = <número>` e falha se alguém embutir um valor.

O preço institucional (B2B, B2G, Enterprise, implantação) **não está declarado em lugar nenhum do
sistema**, porque é decisão comercial do proprietário e porque declarar um número que ninguém validou
seria inventar.

## 6. O que vender, segundo esta arquitetura

"Não venda 20 funcionalidades por R$ 99. Venda um problema caro resolvido." Os campos
`problem_solved` e `substitution_answer` são **NOT NULL** em `monetization_rules`: regra de receita que
não diz qual problema caro resolve e o que ela substitui não entra no banco.

Para o institucional, o problema caro é a **gestão de portfólio com prestação de contas auditável** —
planilha paralela, pasta de e-mail e relatório montado à mão no fim do ano. Para o poder público, é a
**trilha auditável de chamamento**. O que sustenta os dois é a mesma coisa: declarado ≠ medido,
registrado ≠ comprovado, e trilha que ninguém consegue reescrever.

## 7. Documentos irmãos

| Documento | Assunto |
|---|---|
| `SAAS_ECONOMIC_AUDIT.md` | a auditoria que abriu a rodada: o que existia, o que faltava |
| `MONETIZATION_LEGAL_MATRIX.md` | cartão legal de cada receita, com fonte e data |
| `PROGRAM_ARCHITECTURE.md` | a entidade Programa, que é o produto institucional |
| `VALUE_LEDGER.md` | registro de valor entregue |
| `MONETIZATION.md` | regras, elegibilidade e o portão legal |
| `PAYMENT_ARCHITECTURE.md` | cobrança, parcelamento, PIX, boleto e webhook |
| `docs/LEGAL_FRAMEWORK.md` | as onze minutas e por que nenhuma pode ser aceita |
| `docs/AI_ENGINES.md` | IA como motor operacional, com teste provando |
