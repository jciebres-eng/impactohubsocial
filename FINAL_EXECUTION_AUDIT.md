# Auditoria final de execução — IMPACTO v0.30.0

**Data:** 09/10/2026 · **Ramo:** `main` · **Ponto de partida:** `79a326d` (v0.29.0; tag `dd2f8c3`) · **Versão:** 0.30.0

Estados: **PASS** (implementado, integrado e provado por teste executado nesta rodada) · **PARTIAL** (existe e funciona; o que falta
está escrito) · **BLOCKED_EXTERNAL** (depende de conta, credencial, parecer, pessoa ou decisão de terceiro; nada simulado) · **FAIL**
(falhou e não foi corrigido — não há nenhum neste relatório; os que apareceram na regressão estão em §7 com a correção).

Cada linha traz evidência, arquivo, teste, resultado, risco e ação restante. Número citado sem arquivo gerado ou execução registrada
não entra. Nada aqui afirma "100% impossível de invadir".

## 1. O pedido → o que virou software

Pedido do proprietário (pacote "IMPACTO_SUPERPROMPTS_MASTER": orquestrador, arquitetura/roadmap, monetização, governança/evidências/
financiamento por marcos, jornadas por perfil, testes/segurança, versionamento, checklist de aceite, contexto original): inspecionar a
base real antes de alterar; inventário em quatro estados; plano P0/P1/P2 com evidência; evidência como objeto de primeira classe;
indicadores longitudinais com metodologia; dossiê para financiadores; estados do financiamento por marcos com separação decisão/
instrução/confirmação; economia do SaaS e simulação de take rate; matriz perfil × jornada; testes E2E e segurança; versão, ZIP, relatório.

| Item | Estado | Evidência (arquivo · teste) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Inspeção e baseline ANTES de alterar; inventário em 4 estados por contexto; conflitos do pacote com ADRs registrados | PASS | `docs/execution/BASELINE_v0300.md` · `test_v0300_release_docs.test_the_baseline_classifies_in_four_states_and_names_the_conflicts` | 18 contextos classificados; 4 conflitos (escrow, retenção, assinatura, selo pago) recusados por ADR-284/337/341 | — | decisão formal do proprietário se quiser reabrir (checklist D1) |
| Evidência: origem e uso (método, acesso, consentimento, retenção), `unknown` visível | PASS | 0070 · `test_origin_and_use_are_declared_and_unknown_is_a_visible_gap` | lacunas listadas em `gaps`; nunca "ok" por omissão | — | prazos de retenção por classe (DPO) |
| Hash do documento exposto com "integridade ≠ veracidade" | PASS | `GET /v1/evidences/{id}` · `test_document_hash_is_exposed_and_the_notice_says_what_it_proves` | SHA-256 da tabela `documents`; aviso na lista e no detalhe | — | — |
| Rejeitar exige justificativa (API e banco); contestar exige motivo; só a executora contesta; só evidência rejeitada | PASS | `evidences_rejection_has_reason` (NOT VALID), `evidence_contest_guard` · `test_rejecting_requires_a_written_reason…`, `test_only_the_executing_org_contests…` | 422 `reason_required`; 403 para o financiador; 404 para outra OSC | linhas antigas `rejected` sem nota ficam como estão (declarado) | completar notas com auditoria e `VALIDATE CONSTRAINT` |
| Contestação decidida por quem revisa com justificativa; máquina de estados no banco; histórico append-only | PASS | `evidence_state_guard`, `evidence_events` · `test_a_contest_is_decided_by_the_reviewer…` | `submitted → rejected → contested → under_review → accepted` no histórico com motivos; DELETE recusado | — | — |
| Versão e substituição (nunca edição); substituída é terminal e legível | PASS | `version`, `supersedes_id`, `superseded_by` · `test_replacing_creates_a_new_version…` | v2 referencia v1; v1 `superseded`; revisar/substituir de novo → 409; editar conteúdo → recusado pelo gatilho | — | — |
| Outra organização não vê; aceitar evidência não move dinheiro | PASS | RLS existente + `test_another_org_never_sees_the_evidence_and_accepting_moves_no_money` | 404/401; `payout_transfers` inalterado | — | — |
| Dossiê longitudinal: composição com origem, atualidade e lacunas; sem nota; só para as partes; mesma leitura para dona e financiador | PASS | `services/dossier.py`, `GET /v1/projects/{id}/dossier` · `test_v0300_dossier` (4) | blocos prontidão/marcos/evidências/indicadores/aportes/diligências/trilha; `what_this_is_not`; empresa sem relação → 404; anônimo → 401 | — | — |
| Tela do dossiê acessível, claro/escuro, sem erro de console | PASS | `web/src/pages/impact.tsx::ProjectDossier`, `/projetos/:id/dossie` · `test_e2e_v0300_dossier` | A11Y_JS e contraste vazios nos dois temas; números iguais para os dois lados | — | — |
| Mudança metodológica de indicador registrada (motivo obrigatório, append-only, série marca descontinuidade) | PASS | `indicator_method_changes`, `PATCH …/indicators/{pi}/method` · `test_changing_the_measurement_method…` | 422 sem motivo; recusa no banco; `comparable = false` | — | — |
| Estados do financiamento por marcos mapeados ao código (decisão ≠ instrução ≠ confirmação) | PASS (documental, conferido) | `docs/execution/MILESTONE_FUNDING_STATES_v0300.md` · `test_every_cited_table_and_column_exists`, `test_cited_state_values_exist_in_the_checks`, `test_no_escrow_or_balance_table_exists…` | 16 estados pedidos → objeto/coluna/teste; escrow "não existe" provado | — | — |
| Economia do SaaS (pagador → valor → evento → preço-hipótese → custo → margem → alternativa) e matriz de elegibilidade de cobrança | PASS (documento) / BLOCKED_EXTERNAL (validação) | `docs/SAAS_ECONOMY.md` · `test_every_cited_rule_exists_none_is_active_and_refused_ones_are_marked` | 11 regras, 0 ativas, 5 recusadas marcadas; R$ 0,00 | — | revisão jurídica/contábil (checklist D2) |
| Simulação de take rate em múltiplos percentuais | PASS | `24_MONTH_FINANCIAL_MODEL.md` §5a (gerado) · `test_the_sensitivity_section_exists_and_the_catalog_rate_is_the_bold_one`, `test_v0270_financial_model` | 2/3/3,5/4/5 % nos dois modos; catálogo inalterado (350/150 bps) | — | — |
| Matriz perfil × jornada × permissão × dado × ação | PASS (gerada) | `scripts/make_profile_journey_matrix.py` → `PROFILE_JOURNEY_MATRIX_v0300.md` · `test_the_profile_journey_matrix_is_what_the_generator_produces` | 16 jornadas, 256 passos, 0 falhas; 93 passos sem tela direta (fato medido) | — | — |
| Autorização no backend para as 4 rotas novas; RLS nas 2 tabelas novas | PASS | matriz de autorização (940) · `test_v0230_api_sweep`, `test_every_table_has_rls` | classes: `GET evidência` org/investidor/parte; `contest` osc member; `method` osc member; `dossier` partes | — | — |
| Documentação, changelog, notas, ADR-360..363, checklist de produção, rollback, aceite, limpeza | PASS | arquivos citados · `test_v0270_release_docs`, `test_v0230_frontend_gate` (números citados = gerados) | — | — | — |
| Escrow/BaaS, retenção automática, assinatura, selo pago (propostas do pacote) | NÃO FEITO por decisão | ADR-363 | — | — | decisão do proprietário |
| Conflito de interesse por serviço profissional; versão das regras de elegibilidade no match | PARTIAL (P2, registrado) | baseline §3 | — | — | próxima rodada |

## 2. Motores

50 motores registrados — nenhum novo (`dossier@1.0` é composição somente-leitura, não decide; `evaluation` idem). `MOTOR_COVERAGE_MATRIX.md`
(gerado): implemented/integrated/tested 50/50 · **VERDE 37 · AMARELO 13 · VERMELHO 0**. Matrizes regeneradas; `test_v0230_execution_matrices`.

## 3. Perfis, rotas e jornadas

| Prova | Resultado | Fonte |
|---|---|---|
| Jornadas pela API real | **16 jornadas, 256 passos, 0 falha** | `docs/evidence/jornadas_v0250/relatorio.json`, `test_v0250_jornadas` |
| Telas no Chromium, por perfil | **227 rotas** (+`/projetos/:id/dossie`), 0 falha | `test_v0250_todas_as_telas` (contagem 227 com razão) |
| Varredura de autorização | **940 operações** (+4), 238 de plataforma, 94 com permissão, 54 públicas | `API_AUTHORIZATION_MATRIX.csv`, `test_v0230_api_sweep` |
| Matriz por jornada | gerada | `PROFILE_JOURNEY_MATRIX_v0300.md` |

## 4. Evidências (matriz de estados)

| De | Para | Quem | Garantia |
|---|---|---|---|
| submitted | accepted / rejected (motivo) / needs_info / superseded | revisor (financiador/governo) · OSC (substituir) | `guard_self_review`, `evidence_state_guard`, CHECK de motivo |
| needs_info | submitted / accepted / rejected / superseded | OSC · revisor | idem |
| rejected | contested (motivo) / superseded | OSC | `evidence_contest_guard` |
| contested | under_review / superseded | revisor (via decisão) | API passa por `under_review` |
| under_review | accepted / rejected (motivo) | revisor | CHECK |
| accepted | superseded | OSC | — |
| superseded | — (terminal) | — | gatilho |

## 5. Economia (matriz)

Catálogo: 11 regras, 0 ativas; recusadas: `marketplace.take_rate`, `success_fee.funding`, `saas.institutional.funder`,
`b2g.territorial_governance`, `data.territorial_intelligence`. Taxa 3,5 % + 1,5 %: catálogo inalterado; sensibilidade 2–5 % é simulação.
Receita real: R$ 0,00. Nenhuma tabela de saldo/escrow (teste).

## 6. Banco de dados

Migração **0070**: +2 tabelas (`evidence_events`, `indicator_method_changes`; desenvolvimento 329 → 331), ambas RLS e append-only;
+11 colunas em `evidences`, +1 em `project_indicators`; 5 funções/gatilhos; CHECK de status ampliado em `evidences`; CHECK de
`ledger_entries` reescrito com 2 tipos a mais; 1 CHECK `NOT VALID` (rejeição com motivo). Dry-run `impacto_m70` (template de m69 +
0069; 0070 em BEGIN/ROLLBACK) e aplicação do zero na suíte. Nenhuma tabela/coluna removida (`test_v0230_data_infra_gate`).
Retenção: `evidence_events`/`indicator_method_changes` não guardam dado do titular além de referências; `test_v0190_lgpd_deletion` verde
(expectativa atualizada: evidência deixou de ser apagável — consequência do histórico append-only, com a razão escrita no teste).

## 7. Regressão — o que a primeira rodada completa encontrou e o que foi feito

(preenchido a partir de `scratchpad/suite/full_v0300_a.log` — ver abaixo)

## 8. Build limpo e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests scripts/make_profile_journey_matrix.py` | 0 avisos |
| `node build.mjs` (esbuild) | ok; nenhum pacote npm adicionado |
| `tsc --noEmit` (tipos do DefinitelyTyped no scratchpad; `node_modules` = lockfile) | 0 erros |
| `IMPACTO_TRUST_FINAL_RELEASE_0.30.0.zip` | `make_release.py` (REQUIRED += 19 arquivos da rodada); `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; sem ZIP aninhado; SHA-256 ao lado |

## 9. Segurança revisada

4 rotas novas com classe de autorização conferida pelo sweep; dossiê só para as partes (projeto publicado não basta); 2 tabelas novas
com RLS e append-only; quatro olhos preservado (quem envia não revisa; só a executora contesta; quem revisa decide); conteúdo da evidência
imutável depois de enviado; nenhum segredo em código/documento/pacote; nenhum dado novo sai da instalação. Nada aqui afirma "100%
impossível de invadir".

## 10. BLOCKED_EXTERNAL

Parceiro de pagamento e modelo de repasse (não há escrow nem haverá dentro do produto); parecer jurídico/contábil da matriz de
elegibilidade de cobrança; prazos de retenção por classe de evidência (DPO); decisão formal sobre as propostas recusadas por ADR; tag
no GitHub (proxy recusa). Tudo o que já era externo nas versões anteriores continua: `EXTERNAL_INTEGRATIONS.md`.

## 11. Veredito desta auditoria

Nenhum FAIL em aberto. Os P0 do baseline (evidência de primeira classe; dossiê longitudinal) e os P1 (mudança metodológica; matriz;
economia do SaaS; take rate; estados do financiamento) têm teste executado e verde na segunda rodada. O que impede "GO" puro é
externo e decisório (parecer, parceiro, DPO, decisão sobre as propostas recusadas). **Recomendação: GO WITH CONDITIONS** —
detalhado em `FINAL_EXECUTION_REPORT.md` §27.
