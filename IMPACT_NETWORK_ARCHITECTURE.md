# Arquitetura da IMPACT NETWORK (v0.16.0)

O que mudou conceitualmente nesta versão, numa frase: a IMPACTO deixou de ser um sistema que **administra projetos**
e passou a ser uma **infraestrutura de conexão** em que o projeto é um dos elos de uma cadeia. O núcleo da v0.15.0
respondia "o que este projeto é e o que falta nele". A rede responde "quem pode ajudar, como a conversa começa, o que
foi proposto, o que foi combinado, quem precisa saber, e o que o apoio produziu".

## A cadeia

```
Pessoa/Organização → Contexto → Necessidade/Objetivo → Rede → Match → Proposta → Relação →
Projeto → Execução → Evidência → Resultado → Novo match
```

Cada seta é um elo implementado, e cada elo é testado de ponta a ponta em `backend/tests/test_e2e_v0160_journeys.py`.
A cadeia não é um diagrama de intenção: é a ordem em que os motores se chamam.

| Elo | Onde vive | O que o elo garante |
|---|---|---|
| Pessoa/Organização | `organizations`, `users`, `memberships`, `personas`, `org_personas` | Persona é **declarada** e pode ser mais de uma. Não concede permissão. |
| Contexto | `relationships.context_project_id`, `conversations.context_*`, `proposals.*_id` | Conversa e proposta profissionais **exigem** contexto. |
| Necessidade | `project_needs`, `territory_needs`, `marketplace_listings.seeking` | Estimativa de pessoas exige fonte declarada. |
| Rede | `relationships` (22 tipos) | A existência da relação **não** implica visibilidade. |
| Match | `match_runs` (`match-engine@1.2.0`, intocado nesta versão) | Compatibilidade, com quatro versões viajando no resultado. |
| Proposta | `proposals`, `proposal_events`, `proposal_status_graph` | Proposta ≠ contrato ≠ compromisso ≠ pagamento. |
| Relação | `relationships` com `status='active'` | Nasce do aceite; quem propõe não aceita. |
| Projeto | `projects` + `project_status_graph` (v0.15.0) | Máquina de situações como dado. |
| Execução | `milestones`, `indicator_values`, `evidences` | Medição não validada não comprova resultado. |
| Evidência | `core/evidence.py` (v0.15.0) | `verified` deriva da fonte. |
| Resultado | `impact_updates` | Números apurados pelo servidor; quatro olhos; publicar só depois de aceito. |
| Novo match | `recommendations` | Ação com razão e evidência, separada do match. |

## Os onze motores

`backend/impacto/network/` — cada um com uma responsabilidade e nenhum com duas:

| Motor | Responde | Decisão estrutural que ele carrega |
|---|---|---|
| `relationships.py` | quem está ligado a quem, por quê | relação única em lugar de seis tabelas improvisadas; visibilidade por tipo com teto |
| `messaging.py` | como a conversa começa | contexto obrigatório na relação profissional; par de organizações preservado |
| `proposals.py` | o que foi proposto e decidido | máquina de estados como dado; versão no reenvio; aceite cria relação e intenção |
| `marketplace.py` | o que está publicado | publicação é **estado da entidade**, não condição de consulta |
| `impact_report.py` | o que o período produziu | apuração no banco; revisão por quem apoia; quatro olhos |
| `readiness.py` | pronto para quê | seis finalidades, cada número com os critérios que o compuseram |
| `recommendation.py` | o que fazer agora | razão obrigatória; confiança herdada; separado do match |
| `profiles.py` | o que o mundo vê | projeção curada; a página pública não lê tabela privada |
| `workspace.py` | o ambiente de cada persona | um núcleo, várias experiências; persona não dá permissão |
| `enforcement.py` | que medida cabe | escada proporcional; nada automático; contestação julgada por outra pessoa |
| `notify.py` + `events.py` | quem precisa saber | um fato, um aviso por pessoa, idempotente |

## Um núcleo, várias experiências

As quatro personas chamam **os mesmos motores**. O que muda é a seleção e a ordem das seções, declaradas em
`workspace.LAYOUT`. Não existe domínio por persona, não existem quatro produtos, e há um teste que prova isso
(`WorkspaceTests.test_four_personas_share_one_core`): as quatro experiências são diferentes entre si e nenhuma tem
rota, tabela ou motor próprio.

| Persona | O ambiente que ela quer (não "dashboard") | Primeiras seções |
|---|---|---|
| Organização | construção, captação e execução | próximas ações · prontidão · propostas recebidas · projetos |
| Investidor | decisão e relacionamento | próximas ações · em avaliação · propostas enviadas · apoiados |
| Profissional | oportunidades e atuação | próximas ações · oportunidades · propostas · atuações |
| Governo | política pública, território e acompanhamento | próximas ações · território · programas · acompanhados |

Mais seis personas existem no catálogo (`donor`, `mentor`, `volunteer`, `researcher`, `educator`, `admin`), porque
"doador" e "mentor" são formas de **atuar**, não tipos de organização — e essa distinção era uma lacuna da v0.15.0.

## O que foi preservado, e por quê

A auditoria desta rodada (`RECONSTRUCTION_AUDIT.md`) listou 13 coisas que já funcionavam. Três merecem registro aqui,
porque a decisão de **não** mexer foi tão deliberada quanto as mudanças:

1. **`conversations(org_a, org_b)` ficou como estava.** A RLS de `messages` se apoia na RLS de `conversations` — um
   recado só é legível se a conversa for legível. Esse encadeamento está correto, e refazê-lo introduziria risco de
   vazamento sem ganho. Pessoa física já participa pela organização dela (`individual`/`provider`): o par de
   organizações não é limitação do modelo, é o modelo.
2. **`follows`, `favorites` e `org_blocks` continuam sendo a fonte das rotas antigas**, e um gatilho
   (`rel_mirror`) espelha cada linha em `relationships`. A rede enxerga tudo sem que nenhuma rota existente pare.
3. **O motor de match não foi tocado.** Ele responde compatibilidade e está versionado; a recomendação é outro motor,
   que o lê.

## Por que não um banco de grafos

A pergunta real do produto é "quem está a um ou dois passos de mim?". Em SQL, com índice em
`relationships(source_org_id)` e `(target_org_id)`, a vizinhança de profundidade 2 responde em **15 ms** com 10 mil
relações (`PERFORMANCE_REPORT.md`). Não há pergunta de caminho longo no produto — centralidade, menor caminho,
comunidade — e introduzir um banco de grafos sem necessidade comprovada seria adicionar uma dependência operacional,
um modelo de consistência e um backup a mais para resolver um problema que não existe. A decisão está registrada em
`DECISIONS.md` (ADR-141) e se reabre com medição, não com opinião.

## Os dois princípios que atravessam tudo

**1. A existência de uma relação não implica que ela seja visível.** `relationships.visibility` tem cinco níveis
(`private`, `participants`, `organization`, `network`, `public`) e cada tipo tem um teto: bloqueio, favorito e
acompanhamento são **sempre** privados, porque publicar um bloqueio é expor um juízo sobre terceiro e publicar um
favorito é expor a estratégia de quem investe. `relationships.visible_to()` é a única porta de leitura para quem não
é parte, e ela filtra por `visibility` — nunca por "existe". Ver `PRIVACY_VISIBILITY_MATRIX.md`.

**2. Atributo de projeto ≠ dado pessoal sensível.** "Este projeto atende mulheres em situação de vulnerabilidade" é
atributo do projeto ou da necessidade do território. "Esta pessoa é mulher e pertence a determinado grupo vulnerável"
é dado pessoal sensível. A coluna `beneficiary_groups` existe em **uma** tabela (`territory_needs`), há um invariante
que verifica isso, nenhuma rota a aceita como filtro de busca, e a `usage_policy` do termo está gravada no próprio
banco proibindo usá-la para filtrar, segmentar ou inferir característica de pessoa.

## Onde ler o resto

`IMPACT_GRAPH.md` (entidades) · `RELATIONSHIP_MODEL.md` (a relação única) · `PROPOSAL_ENGINE.md` ·
`IMPACT_MARKETPLACE.md` · `MESSAGING_ARCHITECTURE.md` · `NOTIFICATION_ARCHITECTURE.md` · `IMPACT_REPORTING.md` ·
`ROLE_BASED_EXPERIENCE.md` + `WORKSPACE_ARCHITECTURE.md` (personas) · `PRIVACY_VISIBILITY_MATRIX.md` ·
`MODERATION_LADDER.md` · `BILLING_V2.md` · `INFORMATION_ARCHITECTURE.md` + `NAVIGATION_MODEL.md` ·
`DESIGN_HANDOFF_FINAL.md` · `FINAL_IMPACT_NETWORK_HARDENING_REPORT.md` (o relatório honesto desta rodada).
