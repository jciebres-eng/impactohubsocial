# DESIGN_HANDOFF_FINAL — o que o designer recebe (v0.19.0)

**Baseline:** 0.19.0 · snapshot da anterior em `history/v0.18.1/` · Suíte, API e banco: ver
`FINAL_PRE_DESIGN_RELEASE_REPORT.md` (números medidos nesta rodada, não repetidos de memória).

## v0.19.0 — as três coisas que mudaram o seu trabalho

Esta rodada foi feita **para** a camada de design. Três itens, cada um resolvendo uma decisão que,
sem eles, você teria de tomar por conta — e que depois teria de ser desfeita.

### 1 · O vocabulário é dado, não escolha sua

Antes desta rodada, as palavras que a interface mostra estavam espalhadas por doze módulos Python,
com uma terceira cópia dentro de uma página em TypeScript, e **nenhuma** no catálogo de tradução.
Quem desenhasse inventaria os rótulos, e a tela passaria a dizer "sinalizada" onde a API devolve
`flagged` e o texto de ajuda diz "marcada".

**Agora existe uma origem única.** Leia `GLOSSARY.md`: 123 termos em 23 domínios, com rótulo em
pt-BR, en e es, e a definição de cada um. Use assim:

| O que você precisa | De onde tirar |
|---|---|
| rótulo de chip, etiqueta, cabeçalho de estado | `web/src/glossary.ts` (`import { CLAIM_STATUS, term } from "../glossary"`) |
| a mesma coisa em outro idioma | `GET /v1/public/glossary?locale=en` ou `GET /v1/public/translations?locale=en` (namespaces `g_*`) |
| o que o termo SIGNIFICA, para escrever ajuda | coluna **definição** do `GLOSSARY.md` — ela não é texto de tela |
| onde o termo aparece na API | coluna `aparece em` de cada domínio no `GLOSSARY.md` |

**A regra:** se o termo existe no glossário, a tela usa a palavra do glossário. Se você precisar de
uma palavra melhor, **mude o glossário** (`config/glossary.json` + `python3 scripts/sync_glossary.py`)
— não a tela. Um teste reprova quando os dois divergem, nos dois sentidos.

Os termos EDITORIAIS longos (as 12 regras de alegação, as 12 de selo, as 6 dimensões de reputação, os
8 papéis de responsabilidade, os tipos de decisão, o catálogo de barreiras) **não** estão no glossário
de propósito: eles vivem no banco, com nome e explicação próprios, e a API os devolve. Pegue o texto
de lá. Tradução deles está adiada para depois do design.

### 2 · Estado vazio é contrato de API, não texto que você escreve

Os 76 estados vazios do produto diziam "Nada aqui". Agora existe **`GET /v1/firstrun`**, que devolve,
por área, as nove respostas que um estado vazio precisa dar:

o que é esta área · por que está vazia · qual é o próximo passo (com método, rota e tela) · o que se
ganha ao completar · o que é obrigatório · o que é opcional · de onde vem o dado · como se verifica ·
e, quando falta pré-requisito, **qual** (`blocked_by`).

Tudo isso sai de contagem real no banco. Nenhum valor de exemplo, nenhum dado de demonstração.
`EmptyArea` e `FirstRunPanel` em `web/src/ui/kit.tsx` são a referência de como isso se desenha —
deliberadamente sóbrios. **O que precisa resistir à sua reestilização é a hierarquia:** o motivo da
ausência vem ANTES do botão, e nunca existe botão sem motivo ao lado.

### 3 · As SEIS telas que ainda não existem

Esta é a informação mais concreta deste documento. A camada v0.18.0 entregou a API inteira de seis
áreas e **nenhuma tela**. A própria API declara isso (`screen_status: "to_be_designed"`), e um teste
garante que a lista não mente:

| Área | Rota da API que ela consome | Próxima ação que a tela precisa oferecer |
|---|---|---|
| **Contexto e equidade** | `PUT /v1/projects/{id}/equity/context` | declarar contexto e barreiras |
| **ODS** | `PUT /v1/projects/{id}/ods-targets` | mapear o projeto a uma meta |
| **Alegações** | `POST /v1/claims` | declarar alegação apoiada em evidência |
| **Reputação** | `GET /v1/reputation/me` | ver o que cada dimensão mede e quantas observações faltam |
| **Selos** | `POST /v1/seals/evaluate` | ver critério por critério o que falta |
| **Responsabilidade** | `POST /v1/responsibility/assignments` | atribuir o primeiro responsável |

As outras seis áreas já têm tela: diagnóstico (`/diagnosticos`), indicadores
(`/projetos/:id/impacto`), evidência (`/projetos/:id`), território (`/dados-territoriais`), cadeia de
impacto (`/projetos/:id/grafo`) e oportunidades (`/oportunidades`).

### 4 · O retorno que a OSC recebe por declarar contexto (tela nova a desenhar)

A plataforma pede o dado mais caro do produto — necessidade com fonte, barreiras, denominador com
método — e até esta rodada **não devolvia nada visível** para quem preencheu. Agora devolve, em
`GET /v1/projects/{id}/context-return`, oito itens com `available`, `total` e, para o que falta,
`would_open` (a peça que falta e o que ela abre).

Desenhe isso como **"o que você destravou"**, nunca como nota ou selo de progresso. O payload carrega
`no_ranking_note` justamente porque a tentação é transformar isso em pontuação: mais contexto NÃO dá
ranking, nem reputação, nem exposição. O que muda é operacional — cálculo que deixa de responder
"indisponível", sinal de match que deixa de ser DESCONHECIDO, critério de selo que deixa de ser
inalcançável.

### 5 · Vocabulário transversal que vale em toda tela

Quatro palavras, do domínio `data_availability` do glossário, que resolvem o erro mais comum deste
produto:

* **informado** — o dado existe, com origem registrada;
* **não informado** — o dado não existe. **Não é zero, não é falha, não é sucesso**;
* **indisponível** — o cálculo existe, falta um insumo obrigatório, e a tela diz qual;
* **não se aplica** — a pergunta não cabe neste caso.

Ausência tem de ser visível com o mesmo cuidado que presença. Espaço em branco onde deveria haver
"não informado" é defeito de design nesta base, não minimalismo.

---

## O que mudou para o Designer desde o handoff da v0.16.0

Duas rodadas entraram no meio, e as duas mudaram **o que a tela precisa mostrar**:

* **v0.17.0 (economia, legal, pagamento):** programa como entidade, registro de valor separado da
  cobrança, monetização com portão legal (**nenhuma receita ativa**), pagamento marcado
  `PRODUCTION PAYMENT NOT CONFIGURED`, 11 minutas legais **nenhuma aprovada**.
* **v0.18.0–v0.18.1 (impacto contextualizado):** oito telas novas de conteúdo, e uma regra que
  atravessa todas elas — **ausência de dado é informação, não espaço em branco**.

### As oito telas que esta camada exige, e o estado que cada uma tem de representar

| Tela | O que ela mostra | O estado que NÃO pode ser escondido |
|---|---|---|
| **Contexto de equidade do projeto** | necessidade, adicionalidade, barreiras com escada de prova (declarada → documentada → com evidência) | "sem denominador declarado com fonte, nenhum método de normalização está disponível" — com o motivo, nunca uma estimativa |
| **Normalização** | sete métodos, cada um com o denominador que exige | método **indisponível** aparece com o motivo ao lado |
| **Comparação entre projetos** | lado a lado, com fontes | `comparable: false` + lista de motivos, e **nunca** um veredito |
| **Perfil territorial** | determinantes do território | indicador **não medido** aparece com o mesmo peso do medido (`measured: false`) |
| **Integridade de alegação** | o texto que vai ser publicado, as 12 regras e o que falhou | `flagged` exige revisão de outra organização; aceitar **qualifica sem apagar** a marca |
| **Reputação** | seis dimensões, cada uma com valor **ou motivo da ausência**, confiança, observações e quanto foi verificado | **não existe nota única**; organização nova mostra "sem medida", não nota baixa; contestação aberta aparece ao lado da dimensão |
| **Selo** | o que atesta, **o que NÃO atesta**, critério por critério com evidência, validade | revogado e expirado são estados visíveis, não ausência |
| **Responsabilidade** | quem responde por quê, em que período, e as decisões tomadas | **papel vago é informação**: aparece com o que ele responderia |

### Dois componentes que já existem e o Designer deve reaproveitar

* **`Suggest`** (`web/src/ui/suggest.tsx`): autocomplete com **etiqueta de origem** em cada
  sugestão (carga oficial ≠ conhecimento da plataforma ≠ lista editorial ≠ histórico da própria
  organização) e confirmação antes de substituir o que a pessoa escreveu. A etiqueta **não é
  enfeite**: é o que permite avaliar a sugestão.
* **`Steps`** (mesmo arquivo): formulário em etapas que **nunca esconde trabalho já feito** — etapa
  bloqueada mostra o motivo e oferece "Abrir agora mesmo assim".

### Estados de exceção que o Designer precisa desenhar (não só o caminho felizes)

| Situação | Onde aparece | Mensagem que o produto já devolve |
|---|---|---|
| Falta contexto de impacto | match do financiador | sinal UNKNOWN + `missing_data: project.impact_context` → a tela deve virar **ação**, não erro |
| Prazo sem fuso horário | qualquer campo de data-hora | 422 com exemplo (`2026-12-05T23:59:00-03:00`) |
| Linha de base sem fonte | indicador | 422 `baseline_source_required` |
| Alegação marcada | ficha da alegação | lista das regras que falharam, com o detalhe (inclui a cobertura medida) |
| Dimensão sem base | reputação | `value: null` + `reason_without_value` em texto |
| Selo recusado | pedido de selo | "por que eu não recebi": a avaliação recusada **fica registrada** |
| Convite de revisão ausente | revisão de alegação | 422 `not_invited` |
| Sem organização ativa | qualquer rota de organização | 409 `no_active_org` |

### Acessibilidade — o piso já está medido

`ACCESSIBILITY_REPORT.md` tem as 12 verificações que passam hoje (nome acessível, atalho de
conteúdo como primeira parada, foco visível, marcos, contraste calculado nos dois temas, 390 px sem
rolagem horizontal, alvo de toque ≥ 24 px, movimento reduzido) e as 6 que **não** foram verificadas
(axe, leitor de tela real, segundo navegador, zoom 200%, daltonismo, voz). O Designer **não precisa
descobrir** esse piso: precisa não derrubá-lo.

---

# Histórico — handoff da v0.16.0 (preservado)


**Baseline:** 0.16.0 · **Branch:** `chore/v0.16.0-impact-network-core` · **Suíte:** 788 testes, 0 falhas
(12 de volume rodam em passo próprio com `PERF=1`) · Substitui `DESIGN_HANDOFF.md` (v0.15.0), que fica em
`history/v0.15.0/`.

## Leitura mínima, nesta ordem

1. **este arquivo**
2. `IMPACT_NETWORK_ARCHITECTURE.md` — a cadeia de impacto e os onze motores
3. `INFORMATION_ARCHITECTURE.md` — o inventário real e os sete domínios
4. `NAVIGATION_MODEL.md` — o modelo horizontal proposto, com o mapeamento item-a-item
5. `WORKSPACE_ARCHITECTURE.md` + `ROLE_BASED_EXPERIENCE.md` — o que cada persona precisa ver primeiro
6. `PRIVACY_VISIBILITY_MATRIX.md` — **obrigatório**: o que pode aparecer em tela pública
7. `BILLING_V2.md` — o que o checkout tem de mostrar

## 1 · O pacote "Design System Convergência" NÃO foi recebido

Primeiro ponto, porque muda o escopo desta entrega.

O pedido desta rodada pressupõe um pacote de Design System ("Convergência") a ser integrado nos passos 8–9 da
sequência de 13. **Esse pacote não chegou.** Verificado: não há arquivo correspondente no repositório, no diretório de
anexos (`/mnt/user-data/uploads` está vazio) nem em qualquer caminho do contêiner.

Consequência honesta: **as seções de integração de Design System desta rodada não foram executadas** — não por
dificuldade técnica, mas por ausência do insumo. Nada foi inventado para preencher o buraco: não há tokens
"Convergência" no CSS, não há componentes renomeados, não há afirmação de conformidade com um sistema que ninguém
viu.

O que **foi** feito no lugar: a camada de produto que o Design System precisava representar (os onze motores, as dez
personas, as 27 telas novas) e os documentos de AI e navegação acima, que são o insumo que o Design System consome.
Quando o pacote chegar, o trabalho é mapear tokens e componentes sobre uma AI já decidida — que é a ordem correta.

## 2 · O que está pronto e provado

| Camada | Estado | Prova |
|---|---|---|
| API `/v1` | **704 rotas**, contrato estável, OpenAPI gerado do código | `docs/API.md`, `GET /v1/openapi.json` |
| Banco | PostgreSQL 16, **231 tabelas**, RLS em todas (exceto `schema_migrations`), **17 migrations** forward-only | `DATABASE_INTEGRITY_REPORT.md` |
| Rede de impacto | 11 motores, 22 tipos de relação, 9 tipos de proposta, grafo até profundidade 2 | `backend/impacto/network/` |
| Workspace | 10 personas, 24 seções, 15 capacidades | `WORKSPACE_ARCHITECTURE.md` |
| Notificação | 14 grupos, 4 prioridades, fan-out para a equipe, idempotente | `NOTIFICATION_ARCHITECTURE.md` |
| Moderação | escada de 10 degraus com proporcionalidade e contestação | `MODERATION_LADDER.md` |
| Cobrança | preço versionado, aviso de 30 dias, imposto no checkout | `BILLING_V2.md` |
| Perfil público | `impacto.app/@identificador`, projeção curada | `PRIVACY_VISIBILITY_MATRIX.md` |
| Testes | 788, 0 falhas | `TEST_REPORT.md` |
| Desempenho | escala cheia, maior caminho 1.724 ms (orçamento 2.500 ms) | `PERFORMANCE_REPORT.md` |

## 3 · As 27 telas novas desta rodada

Funcionais, sem tratamento visual — é o que o designer vai vestir. Conferidas contra o roteador em
`web/src/app.tsx` (eram 151 telas, são **178**):

| Caminho | Tela |
|---|---|
| `/area` | **workspace** da persona ativa |
| `/rede/relacoes` | relações |
| `/rede/grafo` | grafo da rede |
| `/rede/atividade` | atividade da rede (eventos de domínio) |
| `/rede/experiencias` | experiências declaradas |
| `/propostas` | caixa de propostas |
| `/propostas/:id` | proposta |
| `/propostas/nova` | nova proposta |
| `/marketplace` | descobrir |
| `/marketplace/meus` | meus anúncios |
| `/marketplace/:id` | anúncio |
| `/marketplace/novo` | novo anúncio |
| `/conversas` | conversas |
| `/conversas/:id` | conversa |
| `/relatorios-impacto` | relatórios (caixa de análise) |
| `/relatorios-impacto/:id` | relatório |
| `/projetos/:id/relatorios` | relatórios do projeto |
| `/projetos/:id/equipe` | equipe do projeto (quem é notificado) |
| `/perfil-publico` | meu perfil público |
| `/perfil-publico/experiencias` | minhas experiências |
| `/perfil-publico/:id/identificadores` | histórico de identificadores |
| `/prontidao/finalidades` | prontidão por finalidade |
| `/territorio/necessidades` | necessidades do território |
| `/vocabulario` | taxonomias |
| `/conta/moderacao` | **a medida que me atingiu**, com regra, motivo, prazo e contestação |
| `/admin/medidas` | medidas de moderação (administração) |
| **`/@identificador`** | **página pública, sem sessão** |

Mais a entrada pública do marketplace, que usa `/marketplace` sem sessão.

## 4 · Oito invariantes de design — quebrar qualquer um destes é defeito, não escolha estética

1. **"Investido" ≠ "intenção".** Três estágios distintos (intenção → compromisso → transação) e a interface precisa
   nomear qual está mostrando. Nunca somar os três num número chamado "captado".
2. **Projeto privado nunca aparece em vitrine.** Só `publication_status = published` alcança área pública. Cartão de
   projeto publicado e de rascunho **não podem** ter a mesma aparência.
3. **Relação existir ≠ relação ser pública.** Cinco níveis de visibilidade; a interface mostra qual está ativo e quem
   alcança.
4. **Proposta ≠ contrato ≠ investimento ≠ pagamento.** Quatro coisas, quatro telas, quatro vocabulários. Aceitar
   proposta **não** é assinar contrato.
5. **Recomendação ≠ Match.** Match é o motor de compatibilidade (v0.9.0, intocado). Recomendação é "faça isto agora".
   Rotular recomendação como "match" promete precisão que ela não tem.
6. **Prontidão sempre com explicação.** Seis dimensões; nunca mostrar a nota sem o porquê e sem o que falta.
   Número sozinho é julgamento sem recurso.
7. **Número de impacto é colhido, não digitado.** O relatório exibe `metrics` apurado pelo banco. Se a interface
   oferecer campo editável para esses números, está desfazendo a trava.
8. **Nenhum padrão obscuro no checkout.** Total sempre visível, imposto declarado, cancelar é um botão.

## 5 · Modo claro e escuro

Pedido em rodada anterior e **entregue**: `prefers-color-scheme` com tokens em `:root` e redefinição sob
`@media (prefers-color-scheme: dark)`, mais alternância manual. O que o designer recebe é o **mecanismo**; a paleta
definitiva é decisão de design. Os tokens atuais são funcionais e deliberadamente neutros — não são proposta de
identidade visual.

## 6 · ODS

Os 17 Objetivos estão no banco na tabela `sdg_goals` (desde v0.14.0): número, código `ODS1`…`ODS17`, nome em
português e inglês e a **cor oficial** em hexadecimal (`#E5243B` para o ODS 1, e assim por diante), com CHECK de
formato. As colunas `ods smallint[]` de organizações, projetos, soluções e editais referenciam esse catálogo.

**Os emblemas e logotipos da ONU não estão embutidos no pacote** — são marcas protegidas, com regras de uso próprias,
e incorporar a arte sem conferir a licença seria exatamente o tipo de invenção que o projeto proíbe. O aviso está
escrito na própria migração, acima da tabela. Para o designer: número, nome e cor estão prontos; obter a autorização
de uso da arte oficial é tarefa externa, registrada em `IP_REGISTER.md` e detalhada em `SDG_ESG_TAXONOMY.md`.

## 7 · Pendências que NÃO são bugs

* **Navegação lateral plana** — AMARELO consciente; é a entrega de design, especificada em `NAVIGATION_MODEL.md`.
* **`provider_price_id` nulo** — não há conta Stripe real. O checkout recusa cobrar em vez de inventar.
* **Hub de integração sem tela** — 36 rotas funcionais, interface ainda não desenhada.
* **E2E de navegador cobre as telas de v0.15.0** — as 27 novas têm cobertura de API e de jornada, não de Playwright.
  Registrado em `TEST_REPORT.md`.
* **Nada de biometria, assinatura qualificada, ICP-Brasil, gov.br, SMS, ACT, Stripe real, provedor fiscal real, KYC
  real ou identidade governamental real.** Nenhum desses está simulado em nenhum caminho; onde o produto depende
  deles, há dublê explícito e marcado.

## 8 · O que o designer **não** precisa refazer

Backend, banco, autenticação, autorização, multi-tenancy, cobrança, notificação, moderação, taxonomias, perfil
público e os onze motores. Se algo parecer faltar, conferir primeiro a seção 7.
