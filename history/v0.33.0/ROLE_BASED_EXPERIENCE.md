# Experiência por papel — um núcleo, várias experiências (v0.16.0)

A tese que esta rodada tinha de provar, nas palavras do pedido:

> provar que Investidor, Organização, Profissional e Governo conseguem participar do mesmo ciclo de impacto **sem
> duplicar domínio, quebrar permissões ou criar quatro produtos independentes**.

A resposta: **não existem quatro aplicações**. Existe um núcleo de onze motores, e dez personas que chamam os mesmos
motores com seleção e ordem diferentes.

## O que separa persona de permissão

| | Persona | Papel + plano + RLS |
|---|---|---|
| Responde | "o que aparece primeiro para mim" | "o que eu posso fazer" |
| Onde mora | `org_personas` (declarada, trocável) | `memberships.role`, entitlements, políticas |
| Efeito de trocar | muda a ordem da tela | nada — não muda **nada** |
| Se eu mentir | vejo uma tela que não me serve | o banco recusa igual |

Esta separação é a trava mais importante do documento. Persona é preferência de visualização; tratá-la como
autorização transformaria "escolher um menu" em escalonamento de privilégio. Dois testes guardam isso:
`test_persona_does_not_grant_permission` compara o mapa de `capabilities` antes e depois de declarar persona e exige
que seja **idêntico**; `test_persona_must_match_the_organization_kind` verifica que uma persona fora do tipo da
organização é recusada com **422** (uma OSC não se declara `government`).

Persona é também **plural**: uma organização pode declarar várias (uma empresa que investe *e* presta serviço) e
alternar. `active_persona()` resolve a ativa; `DEFAULT_PERSONA` dá o chute inicial por tipo de organização — explícito
e sobrescrevível, não mágica.

## As dez personas

| Persona | Trabalho primário | Tipos de organização |
|---|---|---|
| `organization` | construir, captar, executar | osc |
| `investor` | decidir e relacionar-se | company, individual |
| `professional` | encontrar e realizar atuação | provider, individual |
| `government` | política pública, território, acompanhamento | government |
| `donor` | apoiar e receber prestação de contas | individual, company |
| `mentor` | orientar quem executa | individual, provider |
| `volunteer` | participar da execução | individual |
| `researcher` | ler evidência e indicador | individual, provider |
| `educator` | formar | individual, provider, osc |
| `admin` | operar a plataforma | platform |

As quatro primeiras são as do pedido. As outras seis existem porque o ciclo já as envolvia e deixá-las sem lugar
empurraria cada uma para a persona errada.

## Os mesmos motores, visto por quem

| Motor | Organização | Investidor | Profissional | Governo |
|---|---|---|---|---|
| Relação | parcerias e apoios | carteira e lista de acompanhamento | vínculos de atuação | convênios e programas |
| Proposta | recebe apoio e serviço | envia investimento e doação | envia serviço e mentoria | envia convênio e edital |
| Marketplace | anuncia projeto | descobre projeto | anuncia serviço | anuncia edital e necessidade |
| Prontidão | mede os próprios projetos | lê antes de decidir | — | lê antes de conveniar |
| Recomendação | "falta o documento X" | "este projeto combina" | "há vaga para seu registro" | "território sem oferta" |
| Relatório | escreve | analisa e aceita | — | analisa e aceita |
| Conversa | com quem propôs | com quem executa | com quem contrata | com quem executa |
| Perfil público | vitrine do projeto | — (opcional) | **o produto principal** | vitrine do programa |

Nada nessa tabela é um domínio novo. É a mesma tabela `relationships`, a mesma `proposals`, o mesmo
`readiness.evaluate()`.

## As quatro jornadas, ponta a ponta

Testadas em `backend/tests/test_e2e_v0160_journeys.py` (7 jornadas, todas verdes):

**Organização** — cadastra → declara persona → recebe recomendação "complete o diagnóstico" → publica anúncio no
marketplace → recebe proposta de apoio → aceita (nasce a relação `supporter`) → executa → envia relatório → quem
apoiou aceita → publica → o relatório aparece no perfil público.

**Investidor** — cadastra → persona `investor` → descobre no marketplace (só `published`) → adiciona à `watchlist`
(visibilidade travada em privada) → lê a prontidão → abre conversa **com contexto** → envia proposta de investimento
→ aceite cria `investment_intent` (intenção, **não** "investido") → recebe relatório → analisa → aceita.

**Profissional** — cadastra → persona `professional` → registra credencial → declara experiência (que fica pendente
até a organização citada confirmar) → escolhe identificador `@nome` → liga o perfil público → recebe proposta de
serviço → aceita → atua → a atuação entra no perfil **depois** de confirmada.

**Governo** — cadastra → persona `government` → registra necessidade de território → publica edital no marketplace →
recebe candidatura → propõe convênio → acompanha → analisa relatório → o indicador do território se move.

## O workspace de cada um

Ver `WORKSPACE_ARCHITECTURE.md`. Em resumo: `WorkspaceContext` devolve **quem sou, o que posso, o que me espera agora
e onde clico** — próximas ações com destino e razão, não um painel de números. A interface desenha; não decide.

## O que foi deliberadamente NÃO feito

* **Sem quatro aplicações, sem quatro bancos, sem quatro domínios.** Um esquema, 231 tabelas, 704 rotas.
* **Sem rota por persona.** Nenhuma rota tem persona na assinatura. `kinds=` e `min_role=` continuam sendo os
  controles, como em todas as versões anteriores.
* **Sem duplicar o motor de match.** O match existente (v0.9.0) não foi tocado; a recomendação é uma camada **acima**
  dele, e `Recomendação ≠ Match` tem documento próprio.
* **Sem "perfil" como entidade.** Profissional não é tabela: é organização do tipo `provider` ou `individual` com
  credenciais e experiências. Criar `Professional` como entidade duplicaria identidade, convite, papel e cobrança.
