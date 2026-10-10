# Auditoria final de execução — IMPACTO v0.33.0

**Data:** 10/10/2026 · **Ramo:** `doacoes-v0330` · **Ponto de partida:** `24793bb` (`correcoes-auditoria`, v0.32.0) ·
**Versão:** 0.33.0

Estados: **PASS** (feito e provado por execução nesta rodada) · **PARTIAL** (feito; o que falta está escrito) ·
**BLOCKED_EXTERNAL** (depende de contrato, parecer, painel ou decisão do responsável; nada simulado) · **FAIL** (falhou e não
foi corrigido — não há nenhum; os que apareceram estão em §7). Nada aqui afirma "100% impossível de invadir".

## 1. O pedido → o que virou software e prova

Pedido (pacote MASTER FULL, 09/10): doações/vaquinha/QR Pix/recorrência/carteira visual/PLD-KYC/comprovantes/prestação de
contas como módulo isolado, sandbox apenas, taxas como hipótese inativa, sem fintech dentro do SaaS.

| Item | Estado | Evidência (arquivo · teste) | Resultado | Risco | Ação restante |
|---|---|---|---|---|---|
| Campanha de doação com revisão a quatro olhos e beneficiário verificado | PASS | `0072` `campaign_state_guard` · `test_v0330_donations.test_01` | criador não aprova; sem verificação não publica; `PATCH published` → 409 | — | processo de KYB (checklist 9) |
| Página pública com QR canônico versionado | PASS | `donation_routes` · `test_02` · captura `01_campanha_publica.png` | QR aponta para `/campanha/{slug}?v={n}`; renovar invalida o anterior | — | — |
| Doação confirmada só por webhook assinado, idempotente, valor conferido | PASS | `apply_provider_event` · `test_03`, `test_04` | assinatura inválida → 202 sem efeito; duplicado → `duplicate`; valor diferente → `under_review` | replay sem carimbo de tempo no sandbox | adaptador real valida `ts` |
| Razão em partidas dobradas, só inserção | PASS | `donation_ledger_balanced` · `test_03`, `test_06`, `test_07` | soma zero por transação; estorno = lançamento novo; `already_reversed` na repetição | — | — |
| Sem custódia: nenhuma coluna de saldo; `is_simulated` não gravável | PASS | `test_10` | 0 colunas `balance`; gatilho deriva do provedor | — | — |
| Taxas inativas, congeladas por doação, devido R$ 0,00 | PASS | `platform_fee_due` · `test_03`, `test_10` · `MONETIZATION.md` | 13 regras no catálogo, 0 ativas | — | parecer (checklist 3) |
| Doador anônimo nunca exposto; isolamento entre organizações | PASS | `test_05` | nome ausente em público e na gestão; outra organização → 404 | — | — |
| Comprovante numerado com SHA-256, anulado em estorno, não dedutível | PASS | `issue_receipt` · `test_03`, `test_06` · captura `03_doacao_comprovante.png` | `IMP-DOA-…` | — | parecer contábil (checklist 6) |
| Prestação de contas (gastos, atualizações) sem condição financeira | PASS | `test_08` · captura `04_gestao_prestacao_contas.png` | entram sempre | — | validação documental |
| Travas de dinheiro real recusam subir | PASS | `config.validate()` · `test_09` · `.env.example` · `test_v0330_release_docs` | 4 flags `true` → erro de configuração | — | ADR nova quando houver provedor |
| Risco proporcional, decisão humana, sem `payout_hold` | PASS | `_risk_screen` · `test_04` · `config/donation_risk_rules.json` · `RiskRulesFileTests` | JSON = código | limiares não são obrigação legal | revisar com jurídico (checklist 8) |
| Suspensão administrativa de campanha publicada | PASS | `suspend` · `test_11` | `under_review` → página 404; organização não republica | — | — |
| Recorrência | PARTIAL | tabela + cancelamento pelo doador | cobrança desligada | — | instrumento do provedor + consentimento |
| Provedor real (≥ 2 avaliados) | BLOCKED_EXTERNAL | `docs/donations/DONATIONS_PROVIDER_MATRIX.md` (fontes datadas) | Asaas e Mercado Pago comparados | — | contrato |
| Modelo de 24 meses | PASS (sem receita) | `docs/donations/24_MONTH_DONATIONS_NOTE.md` | só aritmética; nenhuma projeção | — | 3 meses de dados reais |

## 2. Motores

Inalterados (50; VERDE 37 · AMARELO 13 · VERMELHO 0).

## 3. Perfis, rotas e jornadas

962 operações (+22), 231 telas (+4: `/doacao/:id`, `/minhas-doacoes`, `/admin/doacoes`, `/admin/doacoes/risco`); 60 rotas
públicas (+6, todas na lista revisada de `test_architecture.py` com a razão); 246 rotas de plataforma (+8, com permissão
nomeada: leitura `compliance.read`, escrita `compliance.write`/`finance.write`). Jornada "Captação: cotas → apoios →
campanha pública" passa pela revisão a quatro olhos (`demo_journeys.py`).

## 4. Banco de dados

Migração `0072_v0330_donations.sql`: 11 tabelas (`org_kyb_verifications`, `fee_rule_versions`, `provider_fee_schedules`,
`donations`, `recurring_donation_agreements`, `payment_provider_events`, `donation_ledger_entries`, `donation_risk_cases`,
`donation_receipts`, `campaign_updates`, `campaign_expenses`), 5 funções/gatilhos, RLS em todas, GRANTs mínimos ao
`impacto_app`, 2 regras no catálogo (inativas), 2 categorias de auditoria (`donation`, `beneficiary`). Aplicada em banco novo
(72 migrações) e pelo caminho de atualização (`test_v0150_upgrade`). Só acrescenta; reversível por código.

## 5. Segurança e LGPD

Modelo de ameaças com 19 linhas em `docs/donations/SECURITY_REVIEW.md` (15 🟢 com teste, 3 🟡, 1 🔴 dependente do adaptador
real). Contexto de sistema no módulo revisado linha a linha (público, webhook, pessoa, equipe); rotas da organização com RLS.
Dados pessoais: e-mail cifrado, anônimo protegido, bruto do webhook redigido. `secrets_scan.py` limpo.

## 6. CI

O CI completo roda no pull request (repositório privado, ADR-371). Resultado da execução do PR deste ramo: a registrar no
PR; local: §7 e `docs/evidence/test_run_v0.33.0.log`.

## 7. Regressão — o que esta rodada encontrou e o que foi feito

| Falha | Causa real | Correção |
|---|---|---|
| `test_06_refund_is_a_new_reversing_entry_and_voids_the_receipt` (1ª versão) | o serviço checava o estado antes de olhar se já havia reversão no razão; a segunda reversão voltava `ignored` | ordem invertida em `apply_provider_event`: reversão já lançada → `already_reversed` (eu tinha afrouxado a asserção primeiro — desfeito; a regra é não enfraquecer teste) |
| `test_handlers_declare_auth` | 6 rotas públicas novas fora da lista revisada | listadas com a razão de segurança de cada uma |
| `test_system_context_only_in_allowed_modules` | `donation_routes.py` usa contexto de sistema | permitido com a razão escrita (público, webhook, pessoa, equipe; organização usa RLS) |
| `test_no_read_route_requires_a_write_permission` ×2 · `test_the_write_routes_require_a_write_permission` | GETs com `compliance.write`; `reconcile` (escreve) com `finance.read` | `compliance.read` nas leituras; `finance.write` na conciliação |
| `test_the_platform_does_not_store_individual_beneficiaries…` | tabela chamada `beneficiary_verifications` casava com o guarda de "beneficiário individual" — mas é KYB de organização | tabela renomeada `org_kyb_verifications`; o guarda continua intacto |
| `test_every_action_prefix_in_the_codebase_has_a_category` | prefixos `donation.` e `beneficiary.` sem categoria | categorias na própria 0072 (FINANCE, ORGS) |
| `test_09b_the_v0170_layer_arrived_with_its_seeds_and_its_refusals` · `test_the_table_in_the_document_has_one_line_per_rule` | 13 regras ≠ 11; `MONETIZATION.md` sem as duas linhas | contagem com a razão; duas linhas na tabela |
| `test_public_campaign_shows_remaining_quotas` (API e E2E) · jornada "Captação" | os testes antigos publicavam pelo atalho `PATCH status=published`, fechado pela ADR-374 | passam pela revisão a quatro olhos (`_publish_campaign`), com a razão; a página pública mantém o painel de cotas do projeto |
| `test_every_route_in_the_static_menus_has_an_icon` | 3 rotas de menu sem ícone | ícones oficiais mapeados |
| contagens fixadas (962 operações, 246 plataforma, 102 permissões, 60 públicas, 968 no mapa, 231 telas) · `DEMO.md`, `TESTER_GUIDE.md`, `TROUBLESHOOTING.md` | números mudaram com o módulo | atualizados com a razão ao lado (ADR-340) |
| `test_regenerating_each_matrix_reproduces_what_is_committed` · matriz de jornadas · manifesto · notas da versão | artefatos gerados antes das mudanças finais | regenerados no fechamento; manifesto da v0.33.0 |
| campanha criada pela interface com `kind: "donation"` | eu inventei um valor que o esquema não aceita | tipos reais (`project_crowdfunding`, `emergency`, `institutional_fund`, `recurring`, `organization`) no formulário; lista de campanhas sem `JOIN` obrigatório em projeto |
| CI do PR #6: matriz de jornadas (261 ≠ 267 passos) | o relatório das jornadas depende da ordem da suíte: `test_v0120_knowledge` semeia o curso em rascunho antes das jornadas e a jornada "Suporte" pula 6 passos — era assim na v0.32.0 (4 passos); eu havia regenerado a matriz de uma rodada isolada | matriz regenerada na ordem da suíte (261 passos, 0 falhas), igual ao CI; o teste passou a dizer qual jornada divergiu |
| CI do PR #6: `pilha-do-zero` — `Select` sem nome acessível em `/admin/doacoes` | filtro de situação sem `aria-label` | `aria-label="Filtrar por situação"` |
| CI do PR #6: manifesto cita bundle antigo | bundle reconstruído depois do manifesto | manifesto regerado no fechamento |
| captura de tela: `POST …/donate` 403 | origem do navegador ≠ `PUBLIC_BASE_URL` do servidor de teste (proteção de origem) | base pública apontada para o servidor de teste só na captura; nada mudou no produto |

## 8. Build e pacote

| Passo | Resultado |
|---|---|
| `ruff check impacto tests` | 0 avisos |
| `tsc --noEmit` (tipos oficiais do React, removidos após a checagem) | 0 erros |
| `node build.mjs` | ok |
| `IMPACTO_TRUST_FINAL_RELEASE_0.33.0.zip` | `make_release.py`; `verify_package_against_git.py` byte a byte; `secrets_scan.py`; `unzip -t`; SHA-256 no `.sha256` |

## 9. BLOCKED_EXTERNAL

Contrato com provedor; modelo de titularidade; parecer (taxas, comprovante, termos, LGPD); processo de KYB; merge e
publicação (demo → produção); pendências da v0.32.0; tag v0.33.0.

## 10. Veredito desta auditoria

Nenhum FAIL em aberto. O módulo faz o que o pacote pediu dentro do que é permitido sem contrato e sem parecer — e recusa,
por código, o que não é. Detalhado em `FINAL_EXECUTION_REPORT.md` §27.
