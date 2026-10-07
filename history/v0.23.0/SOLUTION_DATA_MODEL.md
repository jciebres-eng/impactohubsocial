# Modelo de dados da Biblioteca de Soluções (migração `0005_v090_solutions.sql`)

20 tabelas novas (total 105), RLS habilitada em todas (44 políticas novas; total 207), 8 gatilhos de regra de verdade, 3 funções agregadas e 2 funções de fluxo controlado. Reutiliza `organizations`, `users`, `projects`, `documents`, `evidences`, `funder_profiles`, `reports`, notificações e auditoria.

| Tabela | Papel | Regras no banco |
|---|---|---|
| `solutions` | entidade central (tipo, estágio, texto, taxonomias, território, orçamento, licença/IP, visibilidade, proveniência) | `solution_guard`: autor não altera `trust_level/verified_*/is_demo/disputed/generated_draft`; `removed` só admin; mudança substantiva de verificada → `in_review`; CHECK ideia≠executada; `search_doc` (tsvector) e `title_norm` por gatilho |
| `solution_versions` | histórico completo (snapshot jsonb) | append-only (revogado UPDATE/DELETE/INSERT ao app; escrito por trigger `SECURITY DEFINER`) |
| `solution_people` | autoria/equipe/instituições | dono da solução |
| `solution_evidence` | evidências (documento, foto, vídeo, relatório, publicação, auditoria, fonte externa) | `status/reviewed_*` só admin; nasce `submitted`; URL somente `https` |
| `solution_results` | indicadores `reported`/`validated` | validado exige validador + evidência |
| `solution_replication_profile` | fatores declarados para replicabilidade | dono |
| `solution_relationships` | derivada de / replica / complementa / combinada | |
| `solution_saves`, `solution_events` | salvar; analytics deduplicado | índice único (solução, usuário, tipo, dia) |
| `solution_requests` | info/contato/adaptação/replicação/orçamento | conteúdo imutável; solicitante só encerra; bloqueio entre organizações respeitado (`app_blocked_between`) |
| `solution_intents`, `solution_intent_events` | 10 etapas de intenção + trilha | guard + funções de fluxo; eventos append-only; identidade privada por padrão |
| `solution_replications` | replicação por território | guard (autor confirma; replicador não) |
| `solution_reviews` | avaliações (não entram no ranking) | só com pedido aceito/replicação confirmada (`app_solution_reviewable`) |
| `solution_disputes` | contestação de autoria | decisão humana com decisor+nota; flag `disputed` por gatilho |
| `solution_search_log` | hash da consulta + intenção estruturada | sem texto bruto; apagável pelo usuário |
| `solution_preferences`, `funder_solution_prefs` | opt-in de personalização; tese do financiador | |
| `solution_adaptations`, `solution_combinations` | simulações/combinações salvas | |

Índices: GIN em `search_doc`, `title_norm gin_trgm_ops`, `themes`, `population`, `ods`; B-tree composto `(visibility, kind, stage, uf)`. Extensões: `unaccent`, `pg_trgm`; configuração de texto `pt_unaccent`.
Funções públicas agregadas: `solution_public_stats` (contagens de organizações distintas), `solution_funnel` (só dono), `solution_aggregates` (mapa/ODS/tipo, sem identidades).
**Crescimento:** particionar `solution_events`/`solution_search_log` por mês e mover o FTS para índice dedicado quando passar de ~10⁶ soluções; coluna `embedding` reservada para a etapa vetorial (não criada).
Mapeamento com o modelo pedido no prompt: Solution, SolutionVersion, SolutionAuthor→`solution_people`, SolutionLocation→colunas de território, SolutionODS/ESG→arrays, SolutionIndicator→`solution_results`, SolutionEvidence, SolutionBudget/Funding→colunas, SolutionReplication(Profile), SolutionAdaptation, SolutionLicense/IP→colunas, SolutionVerification→colunas `trust_level`/`verified_*` + fila admin, SolutionIntent, View/Save/Share/Contact/Request→`solution_events`/`saves`/`requests`, Review/Rating→`solution_reviews`, Relationship→`solution_relationships`.
