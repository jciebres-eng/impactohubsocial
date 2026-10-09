# Auditoria final de execução — IMPACTO v0.27.0

**Data:** 08/10/2026 · **Ramo:** `main` · **Ponto de partida:** `014c83f` (v0.26.0) · **Versão:** 0.27.0

Estados: **PASS** (implementado, integrado e provado por teste executado nesta rodada) ·
**PARTIAL** (existe e funciona; o que falta está escrito) · **BLOCKED_EXTERNAL** (depende de conta,
credencial, parecer ou decisão de terceiro; nada simulado) · **FAIL** (falhou e não foi corrigido —
não há nenhum neste relatório; os que apareceram na regressão estão em §7 com a correção).

Cada linha traz evidência, arquivo, teste, resultado, risco e ação restante. Número citado sem
arquivo gerado ou execução registrada não entra. Nada aqui afirma "100% impossível de invadir".

## 1. O pedido → o que virou software

Pedido do proprietário (prompt mestre + redefinição econômica): **não existem mais assinaturas**; o
valor do SaaS é estar nele para alcançar recursos e comprovar evidência; 5% da operação financiada =
3,5% plataforma + 1,5% participação de autoria (só quando contratualmente elegível, nunca automática);
percentuais do contrato + versão de preço, nunca em código; GMV ≠ receita; não custodial; um aporte
só do financiador, direcionado a cada parte pela chave PIX do contrato; selos e reconhecimentos só na
quitação; torre MASTER; simulação de 24 meses; inventário KEEP/MIGRATE/DEPRECATE/DELETE antes de
apagar; nada inventado.

| Item | Estado | Evidência (arquivo · teste) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Inventário de cada ocorrência de assinatura/trial/preço/plano/checkout/paywall, classificado KEEP/MIGRATE/DEPRECATE/DELETE | PASS | `docs/execution/SUBSCRIPTION_INVENTORY.md` (banco, backend, front, testes, documentos) | 65 classificações; nenhuma remoção sem destino | — | — |
| Arquivo prévio de tudo que cai (`legacy_subscription_archive`, append-only, só leitura privilegiada) antes de qualquer DROP | PASS | `migrations/0067` §0 · `test_v0230_data_infra_gate.test_no_migration_drops_a_table_or_column_without_a_declared_reason` (9 remoções declaradas com razão) | passa; migração aplicada do zero e sobre base da v0.26.0 (`impacto_m67`, dry-run com ROLLBACK) | baixo | — |
| Nenhuma assinatura em lugar nenhum: sem tabela, sem rota, sem job, sem texto na interface, sem preço de plano no catálogo | PASS | `tests/test_v0270_no_subscription.py::NoSubscriptionAnywhereTests` (tabelas dropadas; `/v1/plans` sem preço; `/v1/me.subscription = null`; rotas de trial/preço/checkout → 404/405; `plans.json` sem `price_cents`; i18n sem `subscription/checkout/cancellation`; `readyz.billing = none-subscription`) | passa | baixo: textos históricos ficam em `history/` e em documentos marcados SUPERADO | — |
| Plano = pacote de capacidades (sem preço, sem intervalo); acesso vem de concessão, convênio, voucher, licença ou contrato | PASS | `config/plans.json` (plans@4.0, `obtained_by`); `services/entitlements.py`; `org_commercial_state` v2 (FREE_ACCESS/FREE_GRANT/GRANT_EXPIRING/CONTRACTED) · `test_v0210_pricing_catalog`, `test_v0210_free_period`, `test_v0210_commercial_ui`, `test_api_features` | passa | — | — |
| Oferta comercial = CONTRATO avulso/parcelado criado por quem tem alçada (`finance.approve`), com valor e razão; nunca recorrente | PASS | `services/offers.py`, `api/commercial_routes.py`; CHECK `billing_frequency IN (one_time, installment)` · `test_v0210_offer`, `test_v0220_authorization` | passa | — | preço de cada contrato é negociado (não há tabela) |
| Cobrança própria real só com autorização: contrato aceito OU acordo de financiamento assinado pelo financiador com taxa (ADR-342) | PASS | `charge_requires_authorization` v2 (`migrations/0067` §6) · `test_v0120_hardening`, `test_v0270_no_subscription` | passa | — | — |
| Vouchers de desconto e desconto de convênio aposentados (criação 422; resgate legado 409 `voucher_type_retired`) — vouchers de concessão continuam | PASS | `services/monetization.py` (`GRANT_VOUCHER_TYPES`/`RETIRED_VOUCHER_TYPES`) · `test_v0110_monetization`, `test_e2e_baseline` (jornada do voucher em `/conta/acesso`) | passa | — | — |
| 5% = 3,5% + 1,5%, no catálogo versionado (`economic_rules`, Pricing Version 2027.02), congelado no acordo; cliente não envia taxa (422) | PASS | `migrations/0066` + `0067` §8; `trust/economy.py` · `test_v0270_economy.test_D_the_client_cannot_set_the_fee_on_a_funding_agreement` (422) e `test_100k_becomes_95k_project_3500_platform_1500_proponent_and_the_layer_is_5000`, `test_v0270_financial_model.test_the_percentages_mirror_the_catalog_in_force` | passa | — | — |
| Participação de autoria nunca automática: proposta → aceita só pelo proponente → consolidada → elegível (parte `proponent` no acordo) → matriz → paga | PASS | `proponent_participations`, `trust/economy.py` · `test_without_an_eligible_proponent_there_is_no_participation_line`, `test_a_proponent_who_did_not_accept_gets_nothing_even_as_a_party`, `test_multiple_proponents_split_the_participation_and_cents_still_close` | passa | baixo | — |
| Matriz de distribuição: bruto = projeto + plataforma + proponente + terceiros; imutável; hash; modos `deducted`/`additional` | PASS | `agreement_allocations` (CHECK `allocation_sums`) · `test_v0260_contract_rules`; `test_100k_becomes_95k_project_3500_platform_1500_proponent_and_the_layer_is_5000`, `test_cents_close_for_awkward_amounts_and_rounding_goes_to_the_project` | passa | — | — |
| Um aporte só, direcionado: instruções de repasse por linha com a chave PIX que cada parte informou no contrato (validada por tipo); plataforma por `PLATFORM_PIX_KEY` | PASS | `allocation_payouts`, `api/trust_routes.py` (PIX/transfers, `min_role = OWNER`) · `test_only_the_party_sets_its_own_key_and_the_format_is_checked_by_the_database`, `test_golden_path_settles_the_operation_and_grants_recognition_only_then` | passa | `PLATFORM_PIX_KEY` vazia → "NÃO CONFIGURADA" (BLOCKED_EXTERNAL) | chave real da pessoa jurídica |
| Transferência registrada por quem paga, confirmada por quem recebe; idempotente por referência; soma limitada à linha; recusa → `disputed`; conciliação com nota | PASS | `payout_transfers`, `payout_state_guard`, `payout_immutable_guard` · `test_E_F_transfers_are_idempotent_and_only_the_recipient_confirms`, `test_I_J_rejected_transfer_puts_the_payout_in_dispute_and_the_platform_line_waits_for_the_rule`, `test_tenant_isolation_a_stranger_sees_no_payouts_and_cannot_touch_them` | passa | médio: conciliação é manual (sem banco) | integração bancária (BLOCKED_EXTERNAL) |
| Não custodial: nenhuma tabela guarda dinheiro de terceiro; instrução ≠ custódia (ADR-343) | PASS | `test_v0220_financial_engine.test_the_platform_has_no_table_that_holds_third_party_money` (confere estrutura, não nome) | passa | — | — |
| Livro econômico append-only, idempotente, com `reversal` obrigatório em nova versão/cancelamento | PASS | `economic_events` · `test_G_changing_the_contract_after_funding_creates_a_new_version_and_reverses_open_instructions`, `test_H_O_cancelling_a_funded_operation_reverses_and_produces_no_revenue` | passa | — | — |
| GMV ≠ receita: `operation_revenue` só de `platform_service_paid` com regra ativa; sem regra → R$ 0,00 | PASS | `economics/metrics.py` · `test_gmv_is_not_revenue_in_the_economic_ledger`, `test_v0220_financial_engine` (operation_revenue), `MasterTowerTests.test_no_invented_balance_and_gmv_is_not_revenue` | passa | — | parecer externo para ativar a regra |
| Reconhecimentos só na operação quitada (entregas aceitas + repasses confirmados); nunca por pagar a plataforma; trajetória pública cumulativa (contagens/datas, nunca valores) | PASS | `trust/economy.py::_recognize`, `network/profiles.py` (`trajectory`) · `test_golden_path_settles_the_operation_and_grants_recognition_only_then`, `test_B_an_operation_is_not_settled_until_every_due_payout_is_confirmed_by_the_recipient`, jornada `caminho_dourado` | passa | — | — |
| Torre MASTER (`/v1/control-tower/master`, `finance.read`): GMV × camada por mês, participação, marketplace sem percentual, uso, contratos, a receber, banco NÃO CONECTADO, captura de valor NÃO MEDIDO sem denominador | PASS | `economics/master_tower.py`, `web/src/pages/internal.tsx::TorreMaster` · `MasterTowerTests` (3: `finance.read`, sem saldo inventado e GMV ≠ receita, menu da equipe), robô de telas (`/controladoria/torre`: OK administração, recusa correta aos demais) | passa | — | — |
| Cartões do dia, selos e trajetória (`/v1/me/today`; `TodayCards` na página inicial; `TrajectoryCard` no perfil público) | PASS | `network/today.py`, `web/src/pages/home.tsx`, `publicprofile.tsx` · `TodayCardsTests` (cartões e selos vêm de registros e não vendem nada; participação proposta vira cartão e selo), `test_e2e_v0181_accessibility` (contraste e alvo de toque do botão "Dispensar", corrigidos nesta rodada) | passa | — | — |
| Simulação de 24 meses derivada de hipóteses declaradas (3 cenários, 3 clientes/mês, sensibilidade R$ 50 mil → R$ 10 milhões, GMV para R$ 1/5/10 milhões) | PASS | `scripts/make_24_month_model.py`, `config/economic_model.json`, `24_MONTH_FINANCIAL_MODEL.md` · `test_v0270_financial_model` (documento = gerador; percentuais = catálogo; aritmética) | passa | — | — |
| Sem pay-to-rank: pacote, voucher, convênio e contrato não alteram match, elegibilidade ou ranking | PASS | `test_architecture` (motores não importam `billing`/`entitlements`/`voucher`), `test_v0110_monetization.test_plan_has_no_effect_on_match_architecture` | passa | — | — |
| "Por que eu pagaria?": núcleo gratuito; a plataforma só é remunerada quando a operação acontece e quita | PASS (por desenho) | `docs/ECONOMIC_MODEL.md` §1; `MONETIZATION.md` §9 (cinco recusas) · `test_v0170_docs.test_the_refused_ones_are_the_five_the_documents_name` | — | — | — |

## 2. Motores

48 motores registrados (`backend/impacto/engines/registry.py`; +`economic_layer`, `master_tower`,
`today_cards`). `MOTOR_COVERAGE_MATRIX.md` (gerado): implemented 48/48 · integrated 48/48 · tested
48/48 · **VERDE 35 · AMARELO 13 · VERMELHO 0**. Os 13 amarelos são motores de leitura sem rastro
durável (torres, Ready, cartões do dia, projeções) ou motores internos sem rota própria — por
desenho, com o motivo listado no próprio documento. `ENGINE_COVERAGE.md` e
`docs/execution/ENGINE_VALIDATION_MATRIX.csv` regenerados; `test_v0230_execution_matrices` e
`test_v0270_release_docs` conferem.

## 3. Perfis, rotas e jornadas

| Prova | Resultado | Fonte |
|---|---|---|
| Jornadas pela API real (sem escrita direta no banco) | **15 jornadas, 244 passos, 0 falha** (14/195 na v0.26.0; nova: "Caminho dourado: acordo → aporte direcionado → confirmação → entrega aceita → quitação → reconhecimento → torre") | `docs/evidence/jornadas_v0250/relatorio.json`, `test_v0250_jornadas` |
| Telas no Chromium, por perfil, com registro real | **805 visitas às 221 rotas**, 221 abertas com sucesso, 0 falha (OK 526 · vazia 134 · recusa correta 94 · sem registro 51) | `docs/evidence/telas_v0250/resumo.json`, `docs/execution/ROUTE_RUNTIME_MATRIX.csv`, `test_v0250_todas_as_telas` |
| Varredura de autorização | 895 operações, 220 de plataforma a 100%, 85 com permissão, 50 públicas revisadas | `docs/execution/API_AUTHORIZATION_MATRIX.csv`, `test_v0230_api_sweep`, `test_v0230_authorization_matrix` |
| Rotas financeiras (PIX, transferências, confirmação, recusa, conciliação) | só `OWNER` da organização; abaixo disso recusado | `test_v0200_adversarial.test_no_financial_route_is_reachable_by_anyone_below_owner` |
| Acessibilidade | contraste AA claro/escuro, alvos ≥ 24 px, menos movimento, axe | `test_e2e_v0181_accessibility` (14/14) |
| Matriz por perfil / persona | `docs/execution/COVERAGE_MATRIX.md` (regenerada), `PERSONA_E2E_MATRIX.csv` (49/49 ponta a ponta) | `make_coverage_matrix.py`, `make_persona_matrix.py` |

## 4. Monetização (matriz)

| Regra | Situação | Carta | Prova |
|---|---|---|---|
| `contract.platform_service_fee` | `active = false`, `review_required`; percentual = do catálogo congelado no acordo | 🟡 perguntas abertas (arranjo de pagamento, ISS, NFS-e) | `test_v0260_contract_rules`, `test_v0170_monetization` |
| `saas.institutional.funder` | **DEPRECATE** → `contract`/`contract`, `legal_status = refused`, `active = false` | 🔴 "não existe assinatura institucional; módulo institucional é contrato" | `migrations/0067` §7, `test_v0170_docs.test_the_refused_ones_are_the_five_the_documents_name` |
| as oito restantes | inalteradas (5 amarelas, 4 recusadas no total com a anterior) | — | `test_v0170_monetization`, `test_v0150_upgrade.test_09b` (10 regras, 0 ativas) |

Catálogo econômico: `economic_rules` 2027.01 (histórico, acordos antigos) e **2027.02** (vigente),
ambas 350/150 bps. Nenhuma regra verde, nenhuma ativa, nenhum preço inventado.

## 5. Estados de pagamento e distribuição (matriz)

| Linha da matriz | Recebe | Chave PIX | Estado inicial | Confirma |
|---|---|---|---|---|
| projeto | OSC executora (`contractor`) | informada pela OSC no acordo | `instruction_created` | OSC |
| plataforma (3,5%) | titular do IMPACTO | `PLATFORM_PIX_KEY` | `awaiting_rule` enquanto a regra está inativa | administração (`billing.write`) |
| proponente (1,5%) | parte `proponent` elegível | informada no acordo | `instruction_created` | proponente |
| terceiros | parte indicada | informada no acordo | `instruction_created` | a parte |

Transições: `awaiting_rule → instruction_created → payment_pending → confirmed → reconciled`; ramos
`failed`, `disputed`, `cancelled`, `refund_pending → refunded` (`payout_state_guard`). Valor e destino
imutáveis (`payout_immutable_guard`). Prova: `test_v0270_economy`.

## 6. Banco de dados

Migrações: 67 (nova: `0067_v0270_no_subscription.sql`, aplicada do zero na suíte e sobre cópia da
v0.26.0 em dry-run). Base migrada: **324 tabelas, 323 com RLS** (exceção: `schema_migrations`),
**675 políticas, 0 FORCE** (`test_every_table_has_rls`, `test_force_row_level_security_is_nowhere`).
Tabelas removidas: `subscriptions`, `subscription_prices`, `price_change_notices`, `org_trials`,
`trial_requests`, `plan_prices`, `plan_price_versions` (todas arquivadas antes). Nova:
`legacy_subscription_archive`. Categorias de auditoria para `participation` e `payout`; catálogo
polimórfico cobre `recognitions`; `data_retention.json` cobre `economic_events` e `recognitions`.

## 7. Regressão — o que a primeira rodada completa encontrou e o que foi feito

Primeira execução completa com o código novo (`scratchpad/suite/full_v0270_a.log`): **2.250 testes,
23 falhas, 2 erros, 26 pulados**. Nenhuma foi "resolvida" afrouxando teste (ADR-340). Causa e correção:

| Falha | Causa real | Correção |
|---|---|---|
| `tests.test_unit` (erro de importação) | importava `services/billing.py`, removido | importação removida |
| `test_architecture.test_the_counts_in_the_document_match_the_registry` | `AI_ENGINES.md` dizia 45 motores | 48 motores, 43 determinísticos |
| `test_e2e_v0181_accessibility` (contraste 1,02 e alvo 71×23 do "Dispensar") | botão dos cartões do dia usava `linklike small` (cor de tinta sobre fundo escuro) | botão `btn btn-ghost btn-sm` (≥ 40 px, contraste do tema) — defeito real de interface |
| `test_e2e_knowledge` (esperava "Página não encontrada" em `/ajuda/teste`) | a rota antiga cai no artigo genérico `/ajuda/:slug` ("Conteúdo não encontrado") | expectativa corrigida; o teste agora também afirma que não há "Solicitar teste" |
| `test_v0160_invariants.test_price_comes_from_the_server…` | não existe preço de assinatura | o teste passa a provar que o percentual vem do catálogo `economic_rules` e nunca do cliente |
| `test_v0190_lgpd_deletion` (classe declarada × regra real) | `data_retention.json` ainda listava `price_change_notices`/`trial_claims` e não cobria `economic_events`/`recognitions` | arquivo corrigido |
| `test_v0200_adversarial` (rotas financeiras) | prefixos novos `/v1/signed-agreements/{id}/pix`, `…/transfers`, `…/payouts` e `/v1/participations` | lista de prefixos atualizada; rotas de PIX/transferência passaram a exigir `OWNER` (endurecimento real) |
| `test_v0200_cleanup` (flag `billing_live` sem leitor; `fmt_date` sem chamador) | sobras da assinatura | flag e função removidas |
| `test_v0230_audit_engine` (prefixos `participation`, `payout` sem categoria) | ações novas | linhas em `audit_action_categories` (0067 §12) |
| `test_v0230_data_infra_gate` (DROP sem razão declarada) | 9 remoções da 0067 | razões declaradas + arquivo prévio (§0) |
| `test_v0230_provenance` (`recognitions.ref_type` fora do catálogo polimórfico) | coluna polimórfica nova | `polymorphic_refs` (0067 §11); `ref_type` passou a nomear tabelas reais (`proponent_participation`, `allocation_payout`, `signed_agreement`, `agreement_allocation`) |
| `test_v0230_authorization_matrix` / `execution_matrices` / `frontend_gate` / `v0250_cobertura` / `todas_as_telas` (contagens e matrizes) | +2 rotas (torre master, cartões do dia) e +1 tela (`/controladoria/torre`) depois da última geração | varredura e matrizes regeneradas; contagens atualizadas com a razão ao lado (895 / 220 / 85 / 221) |
| `test_v0230_release_gate` (manifesto; snapshot da versão anterior) | gerados no fechamento | `history/v0.26.0/` criado; manifesto gerado no fechamento |

Segunda execução completa (após as correções, `docs/evidence/test_run_v0.27.0.log`):
**2.285 testes, 0 erro, 29 pulados, 4 falhas** — todas de fechamento (duas matrizes que citam os módulos de
teste por nome e não conheciam `test_v0270_release_docs.py`; manifesto de release; versão do openapi), todas
regeneradas em seguida com os portões reexecutados verdes (saída anexada ao fim do mesmo log). Detalhe em
`FINAL_EXECUTION_REPORT.md` §24.

**Primeira run do GitHub Actions** (commit `ec0e926`, run `37861052570`): `auditoria` verde; `backend` parou na
varredura de segredo (gitleaks: a mesma linha da matriz de homologação que DESCREVE a falta de credencial do
SMTP, já revisada na v0.24.0, reapareceu porque a coluna de testes mudou — fingerprint único liberado em
`.gitleaksignore`, contagem do teste atualizada com a razão); `docker` e `pilha-do-zero` pararam no typecheck
oficial: `DemoRow` sem uso em `helpAdmin.tsx` — atrás do aviso havia uma **regressão real**: ao retirar a tela
"Testes e demonstrações" com o trial, o painel de pedidos de DEMONSTRAÇÃO (classificado KEEP) ficou sem
interface. Restaurado em `/admin/central/parcerias` ("Parcerias e demonstrações"). O typecheck foi reproduzido
localmente com o `tsc` disponível na máquina (sem `@types/react`, que o registro não entrega aqui): os únicos
avisos fora do ruído de tipos ausentes eram esse e dois pré-existentes em arquivos não tocados, verdes no CI da
v0.26.0. Os logs da run não são legíveis deste ambiente (armazenamento do GitHub bloqueado pelo proxy); o que
está escrito acima vem das anotações da run e da reprodução local.

## 8. Build limpo e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests scripts/make_24_month_model.py` | 0 avisos |
| `node build.mjs` (esbuild) | ok; `dist/` regenerado |
| typecheck oficial (`tsconfig.json`) | roda no CI (`npm ci`); reproduzido localmente com o `tsc` da máquina, sem `@types/react` (ver §7, primeira run) |
| `IMPACTO_TRUST_FINAL_RELEASE_0.27.0.zip` | `scripts/make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; sem ZIP aninhado; SHA-256 ao lado |

## 9. Segurança revisada

- RLS em toda tabela nova (`legacy_subscription_archive`: só `app_priv`, append-only); nenhuma FORCE.
- Rotas que movem instrução de dinheiro (PIX, transferências, confirmação, recusa, conciliação)
  exigem `OWNER`; confirmação da linha da plataforma exige `billing.write`.
- `charge_requires_authorization` v2: nenhuma cobrança própria real sem contrato aceito ou acordo
  assinado pelo pagador com taxa.
- Contexto de sistema restrito aos módulos revisados (`test_architecture`).
- Nenhum segredo, token, chave PIX real ou credencial em código, documento ou pacote
  (`secrets_scan.py`; `PLATFORM_PIX_KEY` só por ambiente).
- Nada aqui afirma "100% impossível de invadir".

## 10. BLOCKED_EXTERNAL

Parecer jurídico/contábil da taxa de serviço (ativa a regra); chave PIX real da plataforma; provedor
de pagamento/banco (conciliação automática); nota fiscal; assinatura qualificada/ICP-Brasil/gov.br;
biometria/KYC; SMS/WhatsApp; 14 integrações do catálogo; aceite de termos (minutas); endereço público;
envio da tag pelo proxy. Tabela completa: `EXTERNAL_INTEGRATIONS.md`, `EXTERNAL_DEPENDENCIES.md`.

## 11. Veredito desta auditoria

Nenhum FAIL em aberto. Todo requisito crítico interno (nenhuma assinatura; integridade econômica
3,5 + 1,5 do catálogo; participação nunca automática; distribuição fechada e imutável; instrução ≠
custódia; confirmação por quem recebe; reconhecimento só na quitação; GMV ≠ receita; autorização;
tenancy; persistência; regressão) tem teste executado e verde na segunda rodada. O que impede "GO"
puro é externo. **Recomendação: GO WITH CONDITIONS** — detalhado em `FINAL_EXECUTION_REPORT.md` §27.
