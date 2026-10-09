# Auditoria final de execução — IMPACTO v0.29.0

**Data:** 09/10/2026 · **Ramo:** `main` · **Ponto de partida:** `1c3114f` (v0.28.0; tag `ff31622`) · **Versão:** 0.29.0

Estados: **PASS** (implementado, integrado e provado por teste executado nesta rodada) ·
**PARTIAL** (existe e funciona; o que falta está escrito) · **BLOCKED_EXTERNAL** (depende de conta,
credencial, parecer, pessoa da área ou decisão de terceiro; nada simulado) · **FAIL** (falhou e não foi
corrigido — não há nenhum neste relatório; os que apareceram na regressão estão em §7 com a correção).

Cada linha traz evidência, arquivo, teste, resultado, risco e ação restante. Número citado sem
arquivo gerado ou execução registrada não entra. Nada aqui afirma "100% impossível de invadir".

## 1. O pedido → o que virou software

Pedido do proprietário (dois PROMPTS MASTER: "Engenharia da Base de Conhecimento" §1–18 e "Sistema global
de tooltip, popover e glossário contextual" §1–12, mais a análise de 4 achados): incorporar a base de
conhecimento v0.26.0 (ZIP) à release mais nova **sem copiar um ZIP sobre o outro e sem retroceder**;
classificar cada documento/componente; governança de ponta a ponta (fonte → direitos → citação →
quatro olhos → publicação imutável → retirada → busca → assistente → interface); busca híbrida com
limites declarados e **medida antes de mudar tecnologia**; assistente que cita só o que usou e se
abstém; feedback e lacunas como trabalho editorial; nunca rotular "base oficial" com conteúdo
educacional/terceiros; ledger de direitos por fonte; resistência a injeção; e um catálogo central de
conceitos consumido por tooltip, popover e glossário, acessível por mouse/teclado/toque, claro/escuro,
sem biblioteca nova, aplicado em telas reais, sem fonte inventada e sem promessa.

| Item | Estado | Evidência (arquivo · teste) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Inspeção da base v0.26.0 × release v0.28.0 e diagnóstico antes de construir (camadas, o que já existia na Central, o que faltava) | PASS | diagnóstico enviado ao proprietário na abertura da rodada; `knowledge-base/CHANGELOG.md` (entrada 2026-10-09); `docs/execution/KNOWLEDGE_ARCHITECTURE_v0290.md` | 4-olhos/imutabilidade/origem/DEMO/regulatório já existiam (0009); faltavam fontes com direitos, citações, retirada, fila, assistente que cita, busca medida, conceitos | — | — |
| Base v0.26.0 versionada no git **sem alteração** e reconciliada controle a controle contra o código | PASS | `knowledge-base/` (58 controles O 33/A 9/V 3/H 4/D 9; 12 pesquisas) · `CONTROL-RECONCILIATION.json` (IMPLEMENTED_TESTED 6 · PARTIAL 27 · BLOCKED_EXTERNAL 13 · NOT_IMPLEMENTED 12) · `test_v0290_knowledge_base.test_the_v0260_base_is_versioned_and_whole`, `test_the_matrix_has_58_controls…`, `test_the_reconciliation_cites_only_tests_that_exist…` (237 referências de teste conferidas por AST; zero inválida) | passa | — | decisões sobre os 13 bloqueados e 12 não implementados (proprietário) |
| Nenhuma alegação de conformidade/vigência/certificação/homologação na base nem no catálogo | PASS | `test_no_document_of_the_base_claims_compliance_certification_or_homologation`, `test_no_term_promises_approval_compliance_or_guarantee`; validador de `scripts/sync_concepts.py` | passa (negação ao lado é a única forma aceita) | — | — |
| Registro de fontes: classe O/A/V/H/D, jurisdição, idioma, vigência, licença, **direitos de uso por operação** (store/index/excerpt/summarize/translate/embed/send_external/train/redistribute ∈ allowed/denied/unknown), verificação por outra pessoa, revisão marcada, hash, supersedes | PASS | `migrations/0069` (`kb_sources`, `kb_rights_ok()`, `kb_source_guard`) · `services/kb_provenance.py` · `test_seeded_primary_sources_are_public_classified_and_unverified`, `test_whoever_registers_a_source_cannot_verify_it` | passa; 11 fontes semeadas, todas `unverified` | **as fontes não foram conferidas por pessoa** — a interface diz isso em cada citação | reviewer confere (checklist D1) |
| `unknown` em um direito bloqueia a operação (trecho) no BANCO | PASS | `kb_citation_guard` · `test_unknown_right_blocks_the_excerpt_at_the_database` | 409 vindo do gatilho | — | — |
| Citações append-only por versão: localizador, trecho ≤600 só com direito, hash conferido, só em RASCUNHO; leitor vê classe e avisos | PASS | `kb_citations` · `test_the_database_checks_the_excerpt_hash_and_only_drafts_accept_citations`, `test_the_reader_sees_the_citation_with_class_and_notices` | passa | — | — |
| Retirada terminal com motivo; propaga para busca, assistente e sitemap; fonte retirada abre acompanhamento (não retira conteúdo sozinha) | PASS | estado `retracted` + `kb_retraction_terminal` + `kb_unpublish_article` · `test_retracting_published_content_needs_a_reason_a_reviewer_and_removes_it_everywhere`, `test_a_retracted_source_is_terminal_and_opens_follow_up_work` | passa | — | — |
| Fila editorial: busca sem resultado, assistente sem base, "não ajudou", vencido/atrasado, relato de erro, fonte a revisar, retirada a acompanhar — deduplicada, **só hash + tópicos** (ADR-043), resolução obrigatória | PASS | `kb_work_items` + `kb_work_open()` · `test_search_without_result_opens_one_deduplicated_item_per_topic_without_free_text`, `test_unhelpful_feedback_and_incorrect_reports_become_work_items`, `test_the_sweep_turns_expired_content_into_work_items_idempotently` | passa | — | pessoas para operar a fila |
| Assistente: só publicado + oficial/educacional + não DEMO + não vencido; cita exatamente a fonte usada; `excluded` com motivo; `ambiguous` em empate; abstenção explícita; nunca "base oficial"; `ai_used = false` | PASS | `services/knowledge.assistant()` · 7 testes (`test_demo_content_never_grounds_an_answer…` … `test_the_assistant_is_declared_extractive_without_a_model`) | passa | — | se um modelo for ligado ao assistente, revisar injeção (ADR-357) |
| Busca MEDIDA: conjunto versionado (35 consultas, 8 tipos), métricas (P@5, R@5, MRR, nDCG@5, hit@1, zero, abstenção, p50/p95), baseline gravado como piso, evidência com limites | PASS | `config/search_eval.json`, `engines/knowledge/evaluation.py`, `docs/evidence/search_eval_v0290.json` · `test_v0290_search_eval` (4) | hit@1 0,875 · MRR 0,94 · nDCG@5 0,93 · R@5 0,98 · zero 0 % · abstenção 3/3 · p95 ≈ 25 ms | **médio**: conjunto pequeno e sintético, rotulado por uma pessoa — o arquivo diz | ampliar com consultas reais (só hash/tópicos) rotuladas por mais de uma pessoa |
| Melhoria só com ganho medido; sem embeddings/vector DB/LLM reranking | PASS | tesauro `help-thesaurus@1.1` (hit@1 0,84 → 0,875; MRR 0,906 → 0,9375) | passa | — | — |
| Anônimo nunca vê conteúdo restrito (medido à parte) | PASS | `test_restricted_content_never_appears_to_an_anonymous_visitor` | passa | — | — |
| Arquitetura: busca/conhecimento não lê reputação, planos, pagamento; rotas públicas revisadas; RLS nas tabelas novas | PASS | `test_knowledge_search_and_match_never_read_reputation_or_plans`, `test_architecture` (lista pública com justificativa), `test_every_table_has_rls`, `test_v0230_api_sweep`, `test_v0230_authorization_matrix` (936 operações; 238 de plataforma; 54 públicas) | passa | — | — |
| Catálogo central de conceitos (33: id, termo, short ≤160, long, por que importa, como o IMPACTO usa, limites, fontes → `kb_sources`/docs, related, applies_to, status) → TS gerado → rota pública | PASS | `config/concepts.json`, `scripts/sync_concepts.py`, `web/src/concepts.ts`, `GET /v1/public/concepts` · `test_schema_and_generated_typescript_are_in_sync`, `test_every_term_separates_definition_platform_use_and_limits`, `test_official_sources_point_to_registered_kb_sources`, `test_public_route_serves_the_catalog_without_auth` | passa | **as 33 definições foram escritas a partir do código e dos documentos; todas marcadas `needs_review`** (a interface avisa) | revisão por jurídico/contábil/impacto (checklist D2) |
| Componentes `Tooltip`, `InfoPopover`, `GlossaryTerm`, `ContextualHelp`, `GlossaryContent` sem biblioteca nova; teclado/mouse/toque; `role=tooltip`/`dialog`; Escape, clique fora, Tab; foco devolvido; inversão de posição; claro/escuro por token; movimento reduzido | PASS | `web/src/ui/help.tsx`, `web/src/styles.css` · `test_e2e_v0290_contextual_help` (7 no Chromium: glossário + a11y + contraste; escuro; mouse/teclado/Escape/fora; nome acessível de título limpo; toque com cartão dentro da janela; escuro + movimento reduzido; ids órfãos) | passa | — | — |
| Aplicado em telas reais | PASS | 11 telas (oportunidades, prontidão, diagnóstico social, determinantes, reputação, selos, equidade, Central de IA ×3, documentos, organização, cotas, torre interna, início ×2) · `test_every_concept_used_on_pages_exists_in_the_catalog` | passa | — | telas administrativas internas (fora do escopo) |
| Página `/ajuda/glossario` (busca sem acento, filtro por área, âncora, link para o glossário de rótulos) antes do catch-all | PASS | `Help.Glossary`, `app.tsx` · `test_glossary_page_lists_terms_filters_and_passes_a11y_and_contrast`; inventário 226 telas | passa | — | — |
| Documentação: ADR-353..359, CHANGELOG, RELEASE_NOTES, README, `KNOWLEDGE_HUB`, `KNOWLEDGE_DATA_MODEL`, `CONTENT_GOVERNANCE`, `AI_SEARCH_ARCHITECTURE`, checklist, rollback, matriz de rastreabilidade, relatório de segurança/privacidade, arquitetura da camada, inventário de limpeza | PASS | arquivos citados · `test_v0270_release_docs`, `test_v0230_frontend_gate` (números citados = gerados) | passa | — | — |
| Verificação humana das fontes · conteúdo oficial com citações · revisão das definições · tradução en/es | BLOCKED_EXTERNAL | — | 0 de 11 fontes conferidas; semente continua DEMO/educacional; 33/33 `needs_review` | declarado na interface e nos documentos | equipe editorial |

## 2. Motores

50 motores registrados (`backend/impacto/engines/registry.py`) — nenhum motor novo: `engines/knowledge/evaluation.py`
é um módulo de métricas puras, não um motor (não decide nada em produção). `MOTOR_COVERAGE_MATRIX.md` (gerado):
implemented 50/50 · integrated 50/50 · tested 50/50 · **VERDE 37 · AMARELO 13 · VERMELHO 0**. `ENGINE_COVERAGE.md`,
`docs/execution/ENGINE_VALIDATION_MATRIX.csv`, `PERSONA_E2E_MATRIX.csv` regenerados (citam os módulos de teste novos);
`test_v0230_execution_matrices` confere.

## 3. Perfis, rotas e jornadas

| Prova | Resultado | Fonte |
|---|---|---|
| Jornadas pela API real | **16 jornadas, 256 passos, 0 falha** (inalterado) | `docs/evidence/jornadas_v0250/relatorio.json`, `test_v0250_jornadas` |
| Telas no Chromium, por perfil, com registro real | **226 rotas** (+`/ajuda/glossario`), 0 falha | `docs/evidence/telas_v0250/resumo.json`, `test_v0250_todas_as_telas` (contagem 226 com razão) |
| Varredura de autorização | **936 operações** (+13), 238 de plataforma a 100 %, 94 com permissão, 54 públicas revisadas (`/v1/help/sources`, `/v1/help/sources/{key}`, `/v1/public/concepts` com justificativa) | `docs/execution/API_AUTHORIZATION_MATRIX.csv`, `test_v0230_api_sweep`, `test_v0230_authorization_matrix` |
| Rotas editoriais | admin + `staff_roles` (editor/reviewer/support) + MFA; relato de erro: usuário autenticado, 20/h | `api/kb_provenance_routes.py`, matriz |
| Acessibilidade | contraste AA claro/escuro nas páginas tocadas; `role=tooltip`/`dialog`; foco; movimento reduzido; achado corrigido (`.pill-muted` 1,27:1 no escuro) | `test_e2e_v0290_contextual_help`, `test_e2e_v0181_accessibility` |

## 4. Camada de conhecimento (matriz)

| Objeto | Estado | Onde é garantido |
|---|---|---|
| Fonte `unverified → verified/disputed/expired`; `active → retracted` (terminal) | PASS | `kb_source_guard` |
| Citação só em rascunho; trecho só com direito; hash | PASS | `kb_citation_guard` |
| Conteúdo `draft → review → approved → published → archived \| retracted` | PASS | `kb.transition` (0009) + `kb_retraction_terminal` (0069) |
| Item de trabalho `open → in_progress → done/dismissed` (resolução obrigatória) | PASS | CHECK + API |
| Semente: `demo = true`, origem `educational` — nunca "oficial" | PASS | `kb_seed`; rótulo de origem em cada resultado |

## 5. Busca e assistente (matriz)

| Pergunta | Resposta medida |
|---|---|
| Acha o guia certo em primeiro lugar? | hit@1 0,875 (28/32 respondíveis) |
| Quando não acha, diz? | zero-result 0 %; abstenção correta 3/3; mensagem explícita |
| Vaza conteúdo restrito ao anônimo? | não (R@5 do anônimo menor; nenhum restrito em ranking algum) |
| Assistente inventa? | não: extrativo, uma fonte usada, `excluded` com motivo, `ambiguous` em empate |
| Depende da ordem dos testes? | não mais: só o corpus rotulado é pontuado (134 itens de outros testes removidos na suíte completa; métricas iguais à medição isolada) |

## 6. Banco de dados

Migração **0069** (`v0290_knowledge_provenance`): +4 tabelas (desenvolvimento 325 → 329), todas com RLS; +7 funções/gatilhos;
+1 valor de status em 3 tabelas; categoria de auditoria `kb`; 11 fontes semeadas. Dry-run `impacto_m69` (template de m68 +
0068; 0069 em BEGIN/ROLLBACK) e aplicação do zero na suíte. Nenhuma tabela/coluna removida (`test_v0230_data_infra_gate`).
Nada a declarar em `config/data_retention.json` (as tabelas novas não guardam dado do titular além de referências
editoriais; `test_v0190_lgpd_deletion` verde).

## 7. Regressão — o que a primeira rodada completa encontrou e o que foi feito

Primeira execução completa com o código novo (`scratchpad/suite/full_v0290_a.log`): **2.379 testes,
10 falhas, 1 erro, 29 pulados**. Nenhuma foi "resolvida" afrouxando teste (ADR-340). Causa e correção:

| Falha | Causa real | Correção |
|---|---|---|
| `test_e2e_v0280_ai_center.test_originality_from_the_project_page…` | o título "Originalidade, similaridade e complementaridade" passou a conter três `GlossaryTerm`; `<button>` dentro de `<h2>` (o navegador força `inline-block`) e o `aria-label` do botão mudavam o **nome acessível do título** para "O que é Originalidade , …" — regressão real de acessibilidade, não só de teste | termo passa a ser `<span role="button" tabindex="0">` inline, sem `aria-label` e sem ícone (o sublinhado pontilhado é a marca; Enter/Espaço tratados); a dica só existe no DOM enquanto visível; teste novo `test_a_heading_made_of_terms_keeps_a_clean_accessible_name` prova (`aria_snapshot` do título) |
| `test_v0290_search_eval.test_the_metrics_do_not_fall_below_the_recorded_baseline` (P@5 0,1875 < 0,19) | na suíte completa outros módulos publicam artigos de teste no mesmo banco ("Prestação de contas passo a passo E2E", slugs aleatórios); eles entravam no ranking sem rótulo e a medição passava a depender da **ordem** dos testes | só itens do corpus rotulado (semente) entram no ranking pontuado — equivale a medir sobre a semente sozinha porque a pontuação é por documento; a evidência registra `unjudged_removed_total` (134); métricas iguais à medição isolada |
| `test_e2e_v0290_contextual_help.test_term_on_touch_device…` (cartão a 845,8 px numa janela de 844) | quando não cabia nem embaixo nem em cima, o cartão passava 2 px da janela | posição limitada à janela (`min(top, innerHeight − h − pad)`); o cartão tem rolagem própria |
| `test_v0250_todas_as_telas.test_every_screen_in_the_router_opens_with_real_data` (226 ≠ 225) | nova tela `/ajuda/glossario` | contagem 226 com a razão escrita ao lado (ADR-340) |
| `test_v0230_execution_matrices.test_regenerating_each_matrix…` [ENGINE_VALIDATION_MATRIX.csv, PERSONA_E2E_MATRIX.csv] | matrizes citam módulos de teste por nome e não conheciam `test_v0290_*` / `test_e2e_v0290_*` | regeneradas (`make_engine_matrix`, `make_persona_matrix`, …) |
| `test_v0230_release_gate.test_the_openapi_document_carries_the_same_version` | `docs/openapi.json` ainda dizia 0.28.0 | `gen_api_docs.py` (936 operações documentadas) |
| `test_v0230_release_gate.test_the_manifest_exists_for_this_version` | manifesto é gerado no fechamento | gerado no fechamento (`FINAL_RELEASE_MANIFEST.json`) |
| `test_v0270_release_docs` (4: auditoria, relatório, log de testes, manifesto/notas) | documentos de fechamento ainda eram os da v0.28.0 | reescritos para a v0.29.0 (este documento, `FINAL_EXECUTION_REPORT.md`, `RELEASE_NOTES.md`, manifesto) |

Achados colaterais corrigidos durante a construção (antes da 1ª regressão, registrados por honestidade): `.pill-muted` a
1,27:1 no tema escuro (`--linha-2` era neutro claro fixo — pré-existente, achado pelo E2E do glossário); path param `{item_id}`
da fila forçava UUID e devolvia 404 para id inteiro; o assistente anterior respondia com conteúdo DEMO/vencido/terceiros sem
dizer a origem; primeira medição anônima da busca "ruim" era comportamento correto (restrito não vaza) — medição passou a ser
como OSC autenticada, com o anônimo medido à parte.

## 8. Build limpo e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests scripts/sync_concepts.py` | 0 avisos |
| `node build.mjs` (esbuild) | ok; `dist/` regenerado; nenhum pacote npm adicionado |
| `scripts/sync_concepts.py --check` | 33 conceitos em sincronia |
| typecheck oficial (`tsconfig.json`) | roda no CI (`npm ci`); local sem `@types/react` |
| `IMPACTO_TRUST_FINAL_RELEASE_0.29.0.zip` | `scripts/make_release.py` (REQUIRED inclui os 31 arquivos novos da rodada); `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; sem ZIP aninhado; SHA-256 ao lado |

## 9. Segurança revisada

Detalhado em `docs/execution/SECURITY_PRIVACY_REPORT_v0290.md`. Resumo: 3 rotas públicas novas são de referência
(metadados de fonte sem texto; catálogo estático), limitadas por taxa e revisadas no teste de arquitetura; rotas editoriais
exigem papel + MFA; quatro olhos e imutabilidade no banco; texto de busca/pergunta nunca guardado (só hash + tópicos);
assistente sem modelo (sem superfície de injeção nesta versão; revisão obrigatória se um modelo for ligado); nenhum segredo
no catálogo ou nos documentos; sem `innerHTML`; URL de fonte imutável após o registro. Nada aqui afirma "100% impossível de
invadir".

## 10. BLOCKED_EXTERNAL

Conferência das 11 fontes (reviewer); conteúdo oficial com citações (equipe editorial); revisão das 33 definições por área;
decisão sobre os 13 controles bloqueados e 12 não implementados da reconciliação (parecer, DPO, provedores); tradução en/es;
tag no GitHub (proxy recusa). Tudo o que já era externo na v0.27.0/v0.28.0 (parecer, provedores, minutas, hospedagem)
continua: `EXTERNAL_INTEGRATIONS.md`.

## 11. Veredito desta auditoria

Nenhum FAIL em aberto. Todo requisito crítico interno (base versionada e reconciliada sem retrocesso; fontes com direitos e
verificação por outra pessoa; citações com hash só em rascunho; retirada terminal que propaga; fila editorial sem texto
livre; assistente que cita e se abstém; busca medida com piso que reprova regressão; catálogo único de conceitos consumido
por tooltip/popover/glossário acessíveis; autorização; tenancy; regressão) tem teste executado e verde na segunda rodada.
O que impede "GO" puro é editorial e externo: **ninguém conferiu as fontes, ninguém revisou as definições e não há conteúdo
oficial** — e a plataforma diz isso em cada tela. **Recomendação: GO WITH CONDITIONS** — detalhado em
`FINAL_EXECUTION_REPORT.md` §27.
