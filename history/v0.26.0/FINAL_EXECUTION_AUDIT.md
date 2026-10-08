# Auditoria final de execução — IMPACTO v0.26.0

**Data:** 08/10/2026 · **Ramo:** `main` · **Ponto de partida:** `7d2730d` (v0.25.0) · **Versão:** 0.26.0

Estados: **PASS** (implementado, integrado e provado por teste executado nesta rodada) ·
**PARTIAL** (existe e funciona; o que falta está escrito) · **BLOCKED_EXTERNAL** (depende de conta,
credencial, parecer ou decisão de terceiro; nada simulado) · **FAIL** (falhou e não foi corrigido —
não há nenhum neste relatório; os que apareceram na regressão estão em §6 com a correção).

Cada linha traz evidência, arquivo, teste, resultado, risco e ação restante. Número citado sem
arquivo gerado ou execução registrada não entra.

## 1. A tese → produto

| Item | Estado | Evidência (arquivo · teste) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Contrato como regra de operação: cláusulas no acordo, congeladas após o rascunho | PASS | `backend/migrations/0064_v0260_contract_operating_rules.sql` (`agreement_terms_frozen`) · `tests/test_v0260_contract_rules.py` | 8/8 | baixo | redação jurídica da cláusula (BLOCKED_EXTERNAL) |
| Versão imutável do acordo; nova versão substitui a anterior e invalida a aprovação | PASS | `agreement_versions` (append-only, RLS) · `test_changing_an_approved_contract_creates_a_new_version_and_invalidates_the_old_approval`; jornada demo (assinatura antiga → 409) | passa | baixo | — |
| Obrigações derivadas (entregar, aceitar, pagar) com prazo pela política de aceite (dias úteis/corridos) | PASS | `trust/contract_rules.py::activate`, `business_days`, `acceptance_deadline` · `test_obligations_are_derived_from_the_contract_and_four_eyes_hold` | passa | médio: `overdue` é calculado na leitura, não gravado por varredura | varredura de prazos que grave `obligation_overdue` no razão (próxima rodada) |
| Aceite a quatro olhos no banco (quem reporta não aceita; quem aceita é parte; recusa exige motivo) | PASS | `agreement_milestone_guard` · mesmo teste; jornada demo (autoaceite → 403) | passa | baixo | — |
| Matriz de distribuição gravada na ativação, imutável, com hash e soma fechada por CHECK | PASS | `agreement_allocations` · `test_100k_with_3_percent_is_traceable_end_to_end_and_the_platform_holds_nothing` (100.000 → 100.000 + 3.000 registrada), `test_deducted_mode_sums_to_gross_and_gmv_is_not_revenue` (97.000 / 3.000) | passa | baixo | — |
| Taxa calculada na origem, paga por quem o contrato indica, em cobrança própria; nunca descontada em trânsito | PASS | `compute_allocation` + `economics.payments.create` (provedor `manual`, `is_simulated = true`) · `test_with_the_rule_active_the_fee_becomes_a_platform_charge_to_the_funder` | passa (carta verde só em TESTE, removida com superusuário ao final) | baixo | — |
| Regra `contract.platform_service_fee` nasce desligada; sem carta verde a taxa é registrada e NÃO cobrada | PASS | `migrations/0064` §5; `monetization_rule_gate` · `test_the_rule_exists_is_inactive_and_is_not_a_success_fee`; `test_v0170_monetization` (10 cartas, nenhuma verde) | passa | — | parecer jurídico e contábil (BLOCKED_EXTERNAL) |
| Sem percentual fixo no código (o percentual é do contrato; sem cláusula não há linha de taxa) | PASS | `percentage = NULL` · `test_without_a_contracted_fee_there_is_no_fee_line_at_all` | passa | — | — |
| GMV ≠ receita | PASS | `services/monetization.revenue_recognized` · `test_deducted_mode_sums_to_gross_and_gmv_is_not_revenue` | passa | — | — |
| Idempotência da ativação; isolamento de tenant | PASS | `activated_at` · `test_duplicate_activation_has_no_duplicate_effect_and_other_tenants_see_nothing` | passa | — | — |
| Razão encadeado recebe ativação, alocação, entrega, aceite, recusa (ator real, contexto de sistema) | PASS | `api/trust_routes.py::agreement_milestone_patch`; `ledger_verify` · jornada demo lê `/v1/projects/{id}/ledger` | passa | — | — |
| Torre do financiador (capital = carteira; onde/para quem/para quê; executado; evidência; mudou; atrasos; riscos; decisões com link) | PASS | `network/control_tower.py::funder`; `api/tower_routes.py`; `web/src/pages/tower.tsx` · `tests/test_v0260_control_towers.py` (3 testes) + robô de telas (`/torre`: OK empresa/apoiadora; recusa correta governo) | passa | baixo | agregação por programa (PARTIAL, API já existe) |
| Torre do governo (território → programas → editais → OSCs → projetos → recursos → indicadores declarados × validados → atrasos → lacunas; k-anonimato ≥ 3; só publicados) | PASS | `migrations/0065::gov_territory_overview`; `control_tower.government` · `test_small_territory_is_suppressed_and_published_projects_feed_the_tower`, `test_a_company_cannot_call_the_territory_function_directly` | passa | baixo | — |
| "Projeto IMPACTO Ready": 15 critérios com evidência, desconhecido ≠ zero, hash, visibilidade dupla | PASS | `migrations/0065::project_ready_facts`; `control_tower.ready`; `ReadyPanel` em `/projetos/:id` · 3 testes em `test_v0260_control_towers.py` | passa | médio: critério "identidade" usa o melhor nível entre donos/admins (não há nível por organização) | nível de identidade por organização; snapshot histórico do estado |
| Match explicado por critério | PASS (já existia) | `engines/match/engine.py` (`signals[]`, `why_match`, `why_not`, `missing_data`) · `test_v0200_engines` | passa | — | Ready como entrada do match (decisão: não acoplar antes de validar critérios com usuários) |
| Utilidade real, não dependência artificial | PASS (por desenho) | nenhum recurso exige que a OSC use a plataforma para receber; a OSC nunca desembolsa para pagar a plataforma; o Ready não é selo pago | — | — | — |

## 2. Motores (FASE 44)

45 motores registrados (`backend/impacto/engines/registry.py`); matriz gerada em
`docs/execution/ENGINE_VALIDATION_MATRIX.csv` e cobertura em `ENGINE_COVERAGE.md`:
implemented 45/45 · integrated 45/45 · tested 45/45 · E2E 40 sim / 2 não / 3 n/a · security 42 sim /
3 n/a · observability 35 sim / 10 não. Os três motores novos (`contract_rules`, `control_tower`,
`impacto_ready`) são determinísticos; `control_tower` e `impacto_ready` são **só leitura** e por
isso não deixam rastro durável (observability "não", como os outros motores de leitura). Teste:
`test_v0230_execution_matrices.test_the_engine_matrix_covers_every_registered_engine`.

## 3. Perfis e jornadas (FASE 42)

| Prova | Resultado | Fonte |
|---|---|---|
| Jornadas pela API real (sem escrita direta no banco) | **14 jornadas, 195 passos, 0 falha** (13/169 na v0.25.0; nova: "Contrato como regra") | `docs/evidence/jornadas_v0250/relatorio.json`, `test_v0250_jornadas` |
| Telas no Chromium, por perfil, com registro real | **796 visitas às 220 rotas**, 0 falha | `docs/execution/ROUTE_RUNTIME_MATRIX.csv`, `test_v0250_todas_as_telas` |
| Telefone (390 px) | 233 telas de menu, 0 vazamento | `docs/evidence/responsivo_v0250/resumo.json` |
| Recusa correta | `/torre` recusa governo; `/torre-territorial` recusa OSC; função SQL recusa empresa (42501) | robô de telas; `test_a_company_cannot_call_the_territory_function_directly` |
| Capturas | `docs/evidence/telas_v0260/` (4 páginas inteiras) | robô com `TELAS_PRINT_DIR` |

Matriz por perfil: `docs/execution/COVERAGE_MATRIX.md`; por persona: `PERSONA_E2E_MATRIX.csv`.

## 4. Monetização (matriz)

| Regra | Situação | Carta | Prova |
|---|---|---|---|
| `contract.platform_service_fee` (nova) | `active = false`, `review_required` | 🟡 com perguntas abertas | `test_the_rule_exists_is_inactive_and_is_not_a_success_fee`; `test_v0150_upgrade.test_09b` (10 regras, 0 ativas após atualização) |
| as nove anteriores | inalteradas (5 amarelas, 4 recusadas) | — | `test_v0170_monetization` (26 testes) |

Nenhuma regra verde, nenhuma ativa, nenhum preço inventado. `MONETIZATION.md` §8,
`MONETIZATION_LEGAL_MATRIX.md`.

## 5. Contratos (matriz)

| Estado do acordo | Pode | Não pode | Prova |
|---|---|---|---|
| `draft` | editar cláusulas, partes, marcos; publicar | ativar | `test_v0140_trust`, `test_v0260_contract_rules` |
| `awaiting_signatures` | assinar (parte, 2 camadas), recusar, nova versão | mudar cláusula (gatilho) | idem |
| `active` | reportar entrega (dono), aceitar/recusar (contraparte), nova versão, código público | autoaceite; mudar cláusula | idem + jornada demo |
| `superseded` | ler | assinar (409), receber marco (409), voltar | idem |
| `canceled`/`completed`/`expired` | ler | marco novo (409) | `agreement_milestone` POST |

## 6. Regressão (FASE 46) — o que a primeira rodada completa encontrou e o que foi feito

Primeira execução completa com o código novo: **2.295 testes, 11 falhas, 3 erros**. Nenhuma foi
"resolvida" afrouxando teste. Causa e correção:

| Falha | Causa real | Correção |
|---|---|---|
| `test_v0190_ops` (3 erros: `pg_dump` falhava) e `test_v0230_data_infra_gate.test_force_row_level_security_is_nowhere` | a migração 0064 ligou `FORCE ROW LEVEL SECURITY` em 3 tabelas; o backup do dono sairia vazio (regra da v0.23.0) | FORCE removido das três tabelas |
| `test_e2e_v0160_journeys.J6` (publicar relatório de impacto → 422) | ao reescrever o CHECK de `ledger_entries.entry_type`, seis tipos existentes (`impact_update_published`, `conversation_started`, `enforcement_applied`, `experience_confirmed`, `team_member_added`, `team_member_removed`) ficaram de fora — **regressão real** | tipos restaurados; conferência de todo `entry_type="…"` do código contra o CHECK |
| `test_v0150_upgrade.test_09b` (9 regras ≠ 10) | décima regra | contagem atualizada com comentário |
| `test_v0170_docs` (tabela do documento ≠ regras do banco) | linha nova da tabela com sufixo na célula da chave | tabela corrigida |
| `test_v0200_engines` / `test_v0230_execution_matrices` (cobertura e matriz de motores) | a suíte começou antes do registro dos 3 motores | matrizes regeneradas |
| `test_v0230_execution_matrices` (matriz de autorização) | `api_sweep_observed.json` é produzido pela própria suíte; a matriz versionada era anterior | regenerada após a varredura |
| `test_v0230_release_gate` (2) e `test_v0250_cobertura` | manifesto e matriz de cobertura são gerados no fechamento | regenerados no fechamento |
| `test_v0260_control_towers` (AC já tinha projeto com medição validada vinda de outro módulo) | suposição de território vazio | o teste confere a regra contra o banco, não contra a suposição |

Segunda execução completa (após as correções): ver `FINAL_EXECUTION_REPORT.md` §24.

## 7. Build limpo e pacote (FASES 47–48, 53)

| Passo | Resultado |
|---|---|
| `ruff check impacto tests` | 0 avisos |
| `node build.mjs` (esbuild) | ok; `dist/` regenerado |
| typecheck oficial (`tsconfig.json`) | roda no CI (`npm ci`; registro npm indisponível neste ambiente, como desde a v0.24.0) |
| `IMPACTO_TRUST_FINAL_RELEASE_0.26.0.zip` | `scripts/make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; sem ZIP aninhado; SHA-256 ao lado |

## 8. Segurança revisada

- RLS em toda tabela nova (`agreement_versions`, `agreement_obligations`, `agreement_allocations`),
  sem FORCE; `test_every_table_has_rls`.
- Funções SECURITY DEFINER novas com portão interno: `project_ready_facts` repete a regra de
  visibilidade de `projects` (não confia só na sessão); `gov_territory_overview` recusa quem não é
  governo/plataforma (42501) e suprime território < 3 projetos.
- Contexto de sistema usado só em `trust_routes.py` (já revisado) e `agreements.settle` por chamada
  de rota; `test_architecture.test_system_context_only_in_allowed_modules`.
- Nenhum segredo, token ou credencial em código, documento ou pacote (`secrets_scan.py`).
- Nada aqui afirma "100% impossível de invadir".

## 9. BLOCKED_EXTERNAL (inalterado desde a v0.25.0, mais um)

Pagamento real; nota fiscal; assinatura qualificada/ICP-Brasil/gov.br; biometria/KYC; SMS/WhatsApp;
14 integrações do catálogo; aceite de termos (minutas); endereço público (D-PUB1); envio da tag
pelo proxy; **parecer da taxa de serviço contratada** (novo).

## 10. Veredito desta auditoria

Nenhum FAIL em aberto. Todo requisito crítico interno (integridade financeira, autorização,
tenancy, persistência, fluxo de negócio, regressão) tem teste executado e verde na segunda rodada.
O que impede "GO" puro é externo. **Recomendação: GO WITH CONDITIONS** — detalhado em
`FINAL_EXECUTION_REPORT.md` §27.
