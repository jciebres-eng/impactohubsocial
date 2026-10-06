# Arquitetura do Workspace (v0.16.0)

Correção conceitual pedida, verbatim:

> "Não chame isso de 'dashboard por perfil'; chame de **Workspace**. Essa diferença parece pequena, mas
> arquiteturalmente é enorme."

Motor: `backend/impacto/network/workspace.py` · Rota: `GET /v1/workspace` · Tela: `web/src/pages/workspace.tsx`

## A diferença, concretamente

| | Dashboard | Workspace |
|---|---|---|
| Devolve | números | **próximas ações com destino e razão** |
| A pergunta que responde | "como estão as coisas?" | "o que eu faço agora, e onde clico?" |
| Quem decide a ordem | a interface | o **backend** (`LAYOUT`) |
| Se eu não souber o que fazer | olho outro número | sigo a recomendação |

A razão está no próprio pedido: o investidor quer ambiente de **decisão e relacionamento**; a organização, de
**construção, captação e execução**; o profissional, de **oportunidades e atuação**; o governo, de **política
pública, território e acompanhamento**. Quatro ambientes diferentes, um núcleo.

## WorkspaceContext

`context()` devolve, numa chamada:

```
{
  org:            quem sou (id, tipo, nome, situação de conformidade)
  persona:        { key, label, primary_job, source }      source: primary | declared | default_by_org_kind
  personas:       as que posso declarar, pelo tipo da organização
  capabilities:   { create_project: true, manage_billing: false, ... }   15 capacidades
  counts:         propostas, relações, recomendações, recados não lidos, avisos não lidos
  recommendations: até 6, cada uma com ação, razão, destino e prioridade
  sections:       [ { key, title, data }, ... ]  NA ORDEM que esta persona precisa
}
```

Uma chamada, uma transação somente-leitura. A tela não monta o workspace a partir de dez requisições: o servidor
decide o que entra e em que ordem, e a interface desenha.

## `capabilities` — a interface não oferece o que a rota recusa

Quinze capacidades, cada uma com os papéis e os tipos de organização que a admitem:

| Capacidade | Papéis | Tipos |
|---|---|---|
| `create_project` | member+ | osc, government |
| `publish_project` | manager+ | osc, government |
| `create_listing` | manager+ | todos |
| `send_proposal` | manager+ | todos |
| `decide_proposal` | manager+ | todos |
| `submit_impact_report` | manager+ | osc, government |
| `review_impact_report` | manager+ | company, government, individual |
| `manage_team` | admin+ | todos |
| `manage_billing` | **owner** | todos |
| `edit_public_profile` | manager+ | todos |
| `run_match` | analyst+ | todos |
| `publish_call` | manager+ | government, company |
| `register_territory_need` | member+ | government, osc |
| `moderate` | — | só administração da plataforma |

`capabilities` é **espelho**, não fonte: a autoridade continua sendo `min_role=`/`kinds=` na rota e a RLS no banco.
O teste `test_capabilities_match_what_the_routes_accept` existe exatamente para impedir divergência — oferecer um
botão que a rota vai recusar é defeito de produto, e anunciar `false` para algo que a rota aceita é esconder função
que a pessoa pagou.

## As seções, por persona

`LAYOUT` é um dicionário de **tuplas ordenadas**. A ordem é a decisão de produto.

| Persona | Seções, em ordem |
|---|---|
| `organization` | o que fazer agora · prontidão dos projetos · propostas recebidas · seus projetos · seus anúncios · prestação de contas · conversas · sua rede |
| `investor` | o que fazer agora · projetos em avaliação · propostas enviadas · projetos que você apoia · relatórios para analisar · descobrir projetos · conversas · sua rede |
| `professional` | o que fazer agora · oportunidades de atuação · propostas enviadas · atuações em andamento · seu perfil público · registros e experiências · conversas |
| `government` | o que fazer agora · território e necessidades · programas e editais · projetos acompanhados · relatórios para analisar · indicadores do território · conversas |
| `donor` | o que fazer agora · projetos que você apoia · descobrir · prestação de contas recebida · conversas |
| `mentor` | o que fazer agora · pedidos de mentoria · mentorias em andamento · perfil público · conversas |
| `volunteer` | o que fazer agora · vagas · participações · perfil público |
| `researcher` | o que fazer agora · projetos e evidências · indicadores publicados · perfil público |
| `educator` | o que fazer agora · oportunidades de formação · formações em andamento · perfil público |
| `admin` | fila de administração · denúncias e medidas · filas de análise · saúde da plataforma |

Vinte e quatro funções `_s_*` implementam as seções. Seções se **repetem** entre personas (`conversations`,
`next_actions`, `network`) — e repetir a seção é o oposto de duplicar o domínio: é a mesma função chamada de dois
lugares.

Toda seção é uma função pura `(conn, org_id, user_id, org_kind) -> dados`. Nenhuma escreve. O workspace é
somente-leitura por construção, com uma exceção deliberada, abaixo.

## A única escrita

Na **primeira** abertura, a caixa de recomendações está vazia porque ninguém calculou ainda — não porque não há o que
fazer. Então `context()` chama `recommendation.refresh()` quando a lista volta vazia. Calcular custa 9 ms medidos, e a
alternativa seria um workspace em branco sem explicação.

Correção relacionada: organizações novas recebiam **zero** recomendações, porque todas as regras dependiam de haver
projeto, proposta ou documento. Foram acrescentadas três de primeiro passo (completar o cadastro, criar o primeiro
projeto, convidar a equipe), de modo que ninguém abre a plataforma num vazio.

## Desempenho medido

Escala cheia, com volume de rede semeado:

| Workspace | Tempo |
|---|---|
| `workspace_osc` | **341 ms** |
| `workspace_investidor` | **71 ms** |

Orçamento do teste de desempenho: 2.500 ms. O workspace da OSC é o mais caro porque é o que agrega mais seções
(prontidão por projeto, propostas, anúncios e prestação de contas). Fica registrado como o ponto a observar se o
volume crescer uma ordem de magnitude.

## Persona não dá permissão

Repetido aqui porque é a trava mais fácil de perder num refactor futuro: `org_personas` não participa de nenhuma
política de RLS, de nenhum `min_role=` e de nenhum `kinds=`. As únicas rotas que mencionam a persona de workspace são
`GET/POST/DELETE /v1/workspace/personas` e `GET /v1/workspace` — nenhuma no caminho de autorização.

(Não confundir com `GET /v1/institutional/persona`, de v0.10.1: aquela é a *persona institucional* do diagnóstico,
entidade anterior e sem relação com esta.)
