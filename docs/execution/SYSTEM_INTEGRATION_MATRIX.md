# Matriz de integração do sistema — v0.26.0

> Responde, módulo a módulo, à pergunta do protocolo: *o que está ligado a quê, e isso está provado?*
> Estados: **PASS** (implementado, integrado e provado por teste automatizado nesta rodada),
> **PARTIAL** (existe e funciona, mas não cobre a tese inteira — o que falta está dito),
> **MISSING** (não existe), **BLOCKED_EXTERNAL** (depende de conta, credencial, parecer ou registro de
> terceiro; nada foi simulado para parecer pronto).
>
> Cada linha cita o teste ou artefato gerado que a sustenta. Linha sem evidência não recebe PASS.

## 1. Do contrato ao dinheiro (tese central)

| Elo | Estado | Como está ligado | Evidência |
|---|---|---|---|
| Documento do acordo → hash congelado → versão 1 | PASS | `publish` chama `contract_rules.record_version`; `agreement_versions` é append-only (`forbid_mutation`) e tem RLS por parte | `test_v0260_contract_rules.test_changing_an_approved_contract_creates_a_new_version_and_invalidates_the_old_approval`, `test_architecture.test_every_table_has_rls` |
| Cláusulas (taxa, pagador, modo, prazo de aceite, dias úteis, contestação) → colunas do acordo, congeladas após o rascunho | PASS | `agreement_terms_frozen` (trigger) recusa mudança fora do rascunho; `superseded` nunca volta | `test_v0260_contract_rules` (8 testes) |
| Assinatura de todas as partes → ativação idempotente → obrigações derivadas por marco (entregar, aceitar, pagar) | PASS | `agreements.settle` → `contract_rules.activate` em contexto de sistema; `activated_at` impede dupla ativação | `test_duplicate_activation_has_no_duplicate_effect_and_other_tenants_see_nothing` |
| Ativação → **matriz de distribuição** gravada (bruto, projeto, taxa, terceiros, linhas, hash, versão de preços) | PASS | `agreement_allocations` imutável; `CHECK allocation_sums` fecha a soma nos dois modos | `test_100k_with_3_percent_is_traceable_end_to_end…` (R$ 100.000 → 100.000 ao projeto + 3.000 de taxa registrada, modo adicional), `test_deducted_mode_sums_to_gross_and_gmv_is_not_revenue` (97.000 / 3.000) |
| Taxa cobrável → **cobrança própria** da plataforma ao pagador (`platform_charges`, provedor `manual`, `is_simulated = true`) | PASS | criada ANTES da alocação (que aponta para ela); só com `contract.platform_service_fee` ativa | `test_with_the_rule_active_the_fee_becomes_a_platform_charge_to_the_funder` (carta verde só em TESTE, removida ao final com superusuário) |
| Regra comercial desligada → taxa **registrada e não cobrada**, com o motivo | PASS | `fee_chargeable = false`, `fee_reason` cita o parecer pendente; nenhuma cobrança aberta | mesmo teste acima, e `test_the_rule_exists_is_inactive_and_is_not_a_success_fee` |
| Marco entregue → prazo de aceite (dias úteis/corridos) → aceite/recusa pela **outra** parte → obrigação de pagar com prazo | PASS | `agreement_milestone_guard` (grafo, quatro olhos, parte do acordo); recusa exige motivo | `test_obligations_are_derived_from_the_contract_and_four_eyes_hold` |
| Aceite/recusa/entrega → razão encadeado do projeto (`milestone_accepted` etc.) com o ator real | PASS | gravado em contexto de sistema com `org_id` do acordo e `actor_org_id` no payload | jornada "Contrato como regra" lê `/v1/projects/{id}/ledger` |
| GMV ≠ receita | PASS | `revenue_recognized` não contém o valor contratado; só a taxa cobrável entra | `test_deducted_mode_sums_to_gross_and_gmv_is_not_revenue` |
| Mudança do contrato → nova versão em rascunho; anterior `superseded`, obrigações `waived`, assinatura antiga recusada (409) | PASS | `contract_rules.new_version` | `test_changing_an_approved_contract_creates_a_new_version_and_invalidates_the_old_approval`, jornada demo (passo "versão antiga não recebe assinatura") |
| Pagamento real do projeto e da taxa | BLOCKED_EXTERNAL | o dinheiro segue pelo meio que as partes escolheram; `provider = manual` é declarado simulado na API | `INTEGRATION_HOMOLOGATION_MATRIX.csv` (Stripe: BLOCKED) |
| Parecer jurídico e contábil da taxa | BLOCKED_EXTERNAL | carta legal amarela com `needs_lawyer = true`, `open_questions` preenchidas | `migrations/0064` §5 |

## 2. Torres de controle

| Elo | Estado | Como está ligado | Evidência |
|---|---|---|---|
| Financiador: capital (comprometido → desembolsado → confirmado → gasto → validado) = carteira | PASS | mesma consulta de `commitments`/`expenses` da carteira; `in_transit_cents` = comprometido − desembolsado | `test_capital_in_the_tower_matches_the_portfolio_and_is_never_a_balance` |
| Financiador: onde está / para quem / para quê | PASS | por projeto: OSC, território, causas, ODS, beneficiários | mesmo teste; captura `docs/evidence/telas_v0260/` |
| Financiador: o que foi executado / que evidência existe | PASS | marcos aceitos/total, evidências aceitas/aguardando | idem |
| Financiador: o que mudou (30 dias) | PASS | `ledger_entries` dos projetos em que é investidor | idem |
| Financiador: o que atrasou | PASS | marcos vencidos não aceitos/recusados, `days_late` | `test_what_needs_my_decision_includes_evidence_delays_and_risks` |
| Financiador: que riscos apareceram | PARTIAL | contagem de riscos altos/críticos abertos por projeto (via `project_ready_facts`) + sinais de risco abertos; **o registro de riscos é da OSC** (RLS), o financiador não vê títulos | mesmo teste; decisão de desenho documentada no código |
| Financiador: o que preciso decidir (obrigações de acordo, candidaturas, relatórios de impacto, evidências) | PASS | união de `pending_for`, `applications`, `impact_updates`, `evidences`, cada item com o link da tela onde se decide | mesmo teste |
| Governo: território → programas → editais → OSCs → projetos → recursos → indicadores declarados × validados → atrasos | PASS | `gov_territory_overview` (SECURITY DEFINER, só governo/plataforma, k ≥ 3, só publicados) | `test_small_territory_is_suppressed_and_published_projects_feed_the_tower`, `test_a_company_cannot_call_the_territory_function_directly` |
| Governo: territórios descobertos | PASS | `PG.territorial_gap` (já existente) | idem |
| Governo: valores individuais de indicador | **não exposto de propósito** | contagens de medições, nunca valores de pessoa | nota na resposta da API |
| Torre por programa (`programs` com `program_projects`) | PARTIAL | programas do órgão listados com orçamento declarado; agregação por programa (`program_financials`) existe na API, não está na torre | `/v1/programs/{id}` |

## 3. "Projeto IMPACTO Ready"

| Elo | Estado | Como está ligado | Evidência |
|---|---|---|---|
| 15 critérios com tabela e contagem | PASS | `project_ready_facts` devolve contagens (NULL = desconhecido); `control_tower.ready` classifica met/unmet/unknown | `test_ready_lists_every_criterion_with_its_evidence_and_is_not_granted_by_default` |
| Desconhecido ≠ zero; `ready` só com todos atendidos | PASS | estado `not_assessable` quando só há desconhecidos | `test_unknown_is_not_zero` |
| Mesmo resultado para dono e financiador; 404 para quem não enxerga | PASS | visibilidade conferida na sessão (RLS) **e** dentro da função | `test_the_funder_sees_the_same_state_and_a_stranger_sees_nothing` |
| Hash reproduzível da avaliação | PASS | sha256 do material (critérios + evidência) | mesmo teste |
| Painel na ficha do projeto; estado resumido na torre do financiador | PASS | `ReadyPanel` em `/projetos/:id`; coluna "IMPACTO Ready" em `/torre` | captura `docs/evidence/telas_v0260/` |
| Snapshot histórico do estado (série temporal) | MISSING | avaliação é calculada a cada leitura; não há tabela de instantâneos | — (candidato à próxima rodada) |
| Identidade validada da organização | PARTIAL | usa o melhor nível entre donos/administradores (não existe nível por organização) | `TECHNICAL_BASELINE…` B4 |

## 4. Match explicado

| Elo | Estado | Como está ligado | Evidência |
|---|---|---|---|
| Critério a critério (peso, contribuição, evidência, frescor) | PASS (já existia) | `signals[]`, `why_match`, `why_not`, `missing_data`, `next_action` | `engines/match/engine.py`, `test_v0200_engines` |
| Estado IMPACTO Ready como entrada do match | MISSING | o match não lê `ready()`; o financiador vê os dois lado a lado na ficha do projeto | — (candidato à próxima rodada; decisão: não acoplar antes de validar os critérios com usuários) |

## 5. Interface

| Tela | Estado | Evidência |
|---|---|---|
| `/acordos/novo` com cláusulas de operação | PASS | crawler: OK para os 6 perfis |
| `/acordos/:id` — regras, matriz, partes, entregas e aceite, obrigações, versões, nova versão, recusa com motivo | PASS | crawler: OK (osc, company, provider); capturas |
| `/torre` (empresa, apoiadora) | PASS | crawler: OK; governo → recusa correta |
| `/torre-territorial` (governo, plataforma) | PASS | crawler: OK; OSC → recusa correta |
| `/projetos/:id` com painel IMPACTO Ready | PASS | crawler: OK para os 6 perfis |
| Inventário de telas regenerado (220) e mapa tela → backend (894 operações) | PASS | `screen_inventory.json`, `screen_backend_map.json`, `test_v0230_frontend_gate` |

## 6. O que continua BLOCKED_EXTERNAL (inalterado)

Pagamento real, nota fiscal e retenção, assinatura qualificada/ICP-Brasil/gov.br, biometria/KYC,
SMS/WhatsApp, as 14 integrações do catálogo, aceite de termos (minutas sem advogado), endereço
público (D-PUB1), parecer da taxa de serviço contratada. Nenhum foi simulado; cada um aparece na
interface como "não ligado".
