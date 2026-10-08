# Linha de base técnica antes da execução — v0.26.0

> Fase 1–3 do protocolo: *antes de escrever uma linha, registrar o que existe, o que está provado e o
> que não está.* Este documento descreve o estado do repositório no commit `7d2730d` (tag esperada
> `v0.25.0`), ponto de partida da rodada v0.26.0. Nenhum número aqui é estimativa: cada um vem de um
> arquivo gerado ou de uma execução registrada, citados ao lado.

## 1. Identificação

| Item | Valor | Fonte |
|---|---|---|
| Commit de partida | `7d2730d3e068db346c3a6041e4a782cd6158f607` — "v0.25.0 — manifesto de release" | `git log` |
| Versão | 0.25.0 (`VERSION`, `backend/pyproject.toml`, `web/package.json`) | arquivos de versão |
| Tag | `v0.25.0` criada localmente; **não pôde ser enviada** (o proxy deste ambiente recusa push de tag e a API de escrita do GitHub). Criação manual pelo dono no commit `7d2730d` | `RELEASE_REPORT_v0.25.0.md` §tag, `BLOCKERS.md` |
| CI de referência | execução `37751013867`, verde nos quatro jobs: `backend`, `auditoria`, `docker`, `pilha-do-zero` | GitHub Actions |
| Banco gerenciado | Supabase `efhhwjhrlbbmtuwjsbkk` (us-west-2, PostgreSQL 17.11), migrações **verificadas e aplicadas** pelos fluxos `verificar` (`37727218378`) e `aplicar` (`37727468920`) na v0.24.2 | `docs/execution/DATA_INFRA_GATE.md` |

## 2. Tamanho e forma

| Medida | Valor em `7d2730d` | Como foi medido |
|---|---|---|
| Testes (unittest, HTTP + PostgreSQL reais) | **2.277** | `python3 -m unittest discover` na rodada v0.25.0 (`RELEASE_REPORT_v0.25.0.md`) |
| Operações de API registradas | **888** | `docs/execution/API_AUTHORIZATION_MATRIX.csv` (uma linha por operação) |
| Telas do roteador | **218** (9 públicas, 30 de ajuda, 179 autenticadas) | `docs/execution/screen_inventory.json` |
| Migrações | 63 (`0001` … `0063`) | `backend/migrations/` |
| Tabelas com RLS | 321 de 322, 667 políticas | `docs/DEMO.md` §3, `test_architecture.test_every_table_has_rls` |
| Motores registrados | 42 (37 determinísticos, 3 com modelo de linguagem, 2 de busca fundamentada) | `backend/impacto/engines/registry.py`, `ENGINE_COVERAGE.md` |
| Integrações catalogadas | 14, **todas** `BLOCKED` por credencial (nenhuma ativa em produção) | `docs/execution/INTEGRATION_HOMOLOGATION_MATRIX.csv` |
| Jornadas de demonstração | 13 jornadas, 169 passos, 0 falha | `docs/execution/COVERAGE_MATRIX.md` |
| Visitas de tela no Chromium | 790 visitas às 218 rotas, por 6 perfis + visitante | `docs/execution/ROUTE_RUNTIME_MATRIX.csv` |
| Telefone (390 px) | 230 telas de menu, 0 vazamento horizontal | `docs/evidence/responsivo_v0250/resumo.json` |

## 3. O que já existia e em que estado (inventário por motor da tese)

Legenda: **PASS** = implementado, integrado e provado por teste e jornada; **PARTIAL** = existe, mas
não cobre a tese inteira; **MISSING** = não existe; **BLOCKED_EXTERNAL** = depende de terceiro.

| Capacidade da tese | Estado em 7d2730d | Evidência | O que faltava (escopo da v0.26.0) |
|---|---|---|---|
| Acordo assinado com hash congelado, partes, assinatura em duas camadas, registro verificável | PASS | `test_v0140_trust.py`, jornada "Documentos" | — |
| **Contrato como regra de operação**: versões, obrigações derivadas, política de aceite, marcos com valor | **PARTIAL** — marcos tinham só título/prazo/situação; sem versão, sem obrigação, sem prazo de aceite, qualquer um mudava a situação | `migrations/0012`, `trust/agreements.py` | versão imutável, `agreement_obligations`, aceite a quatro olhos, prazo em dias úteis, nova versão que substitui a anterior |
| **Matriz de distribuição** (bruto → projeto → taxa → terceiros) e taxa calculada na origem | **MISSING** | — | `agreement_allocations` (imutável, hash), `compute_allocation`, cobrança própria ao pagador quando a regra estiver ativa |
| Regra comercial da taxa de serviço contratada | **MISSING** (existiam `success_fee.funding` e `marketplace.take_rate`, ambas vedadas pela ADR-022) | `migrations/0020`, `0021` | `contract.platform_service_fee`, nascida desligada, carta amarela, sem percentual fixo (vem do contrato) |
| Monetização por valor, catálogo configurável, portão jurídico (`monetization_rule_gate`) | PASS | `test_v0170_monetization.py` | — |
| Cobrança própria da plataforma sem custódia (`platform_charges`, provedor `manual` → simulada) | PASS | `test_v0170_payments` | — |
| Aporte sem custódia (compromisso → desembolso → confirmação → despesa → evidência), carteira do financiador | PASS | `test_api_workflow.py`, `/v1/portfolio` | — |
| **Torre do financiador** ("meu capital → … → o que preciso decidir") | **PARTIAL** — painel (`/v1/dashboard`), carteira e área de trabalho respondiam partes isoladas; nenhuma tela reunia a cadeia nem "o que preciso decidir" | `insight_routes.py`, `network/workspace.py` | `/v1/control-tower/funder` + `/torre` |
| **Torre do governo** (território → … → territórios descobertos) | **PARTIAL** — `gov_territory_stats` (k-anonimato), `territorial_gap`, necessidades do território; `_s_programs` lia `calls`, não `programs`; indicadores validados invisíveis ao governo pela RLS | `migrations/0002`, `0018`, `workspace.py` | `gov_territory_overview` (k ≥ 3), `/v1/control-tower/government` + `/torre-territorial` |
| **"Projeto IMPACTO Ready"** como estado verificável | **PARTIAL** — prontidão por finalidade (`readiness@1.0.0`, 6 dimensões, só para a própria OSC), selos com regra pública (12 regras fechadas); nenhum estado com os 15 critérios da tese, legível pelo financiador | `network/readiness.py`, `impact/seals.py` | `project_ready_facts` + `/v1/projects/{id}/ready`, painel na ficha do projeto |
| Match explicado por critério (`signals[]` com peso, contribuição e evidência) | PASS | `engines/match/engine.py` (`match-engine@1.2.0`) | — |
| Prestação de contas (relatório de impacto por período, análise pela contraparte) | PASS | `network/impact_report.py` | — |
| Razão encadeado por projeto (`ledger_verify`) | PASS | `migrations/0002` | tipos novos: ativação de acordo, alocação, entrega, aceite, recusa, obrigação vencida |
| Pilha do zero com Docker, telas por perfil, axe, persistência | PASS (CI `pilha-do-zero`) | `infra/compose/demo`, `scripts/demo_stack.py` | — |
| Pagamento real, nota fiscal, assinatura qualificada, gov.br, biometria, KYC, SMS | BLOCKED_EXTERNAL | `INTEGRATION_HOMOLOGATION_MATRIX.csv` | não entra nesta rodada; nada será simulado |

## 4. Defeitos conhecidos encontrados na leitura da base (antes de executar)

Registrados aqui para que a rodada não os esconda; o que foi corrigido na v0.26.0 está marcado.

| # | Achado | Onde | Tratamento na v0.26.0 |
|---|---|---|---|
| B1 | `review_inbox` filtra `applications.status IN ('approved','accepted','contracted')`; `accepted` e `contracted` não existem no CHECK | `network/impact_report.py:233` | **não alterado** (fora do escopo; registrado em `FINAL_EXECUTION_AUDIT.md` como pendência) |
| B2 | `exec.progress` sempre 0: conta marcos `completed`/`verified`, que não existem (o estado é `accepted`) | `network/readiness.py:268` | **não alterado** (idem) |
| B3 | Área de trabalho do governo lê `calls` onde diz "programas" | `network/workspace.py:376` | a torre territorial lê `programs` **e** `calls`, separados |
| B4 | `identity_level` é por usuário; não há nível por organização | `migrations/0012` | o critério "identidade validada" usa o melhor nível entre donos/administradores da organização |
| B5 | `/v1/readiness/purposes` só avalia projeto da própria organização | `network_hub_routes.py` | o IMPACTO Ready é legível por qualquer parte que enxerga o projeto |
| B6 | Testes fixam contagens (888 operações, 218 telas, 42 motores) | `test_v0230_*`, `test_v0250_*` | atualizadas para 894 / 220 / 45 com comentário de versão; documentos que citam o número também |

## 5. Regras que governam a execução (não negociáveis)

- ADR-022 / ADR-178 / **ADR-284**: a plataforma **não custodia** e não vira fintech. A taxa é serviço
  contratado, calculada na origem, paga por quem o contrato indica, em cobrança própria — nunca
  descontada de dinheiro em trânsito.
- `monetization_rule_gate`: nenhuma regra com receita é ativada sem carta legal verde completa; a
  regra nova nasce desligada e assim permanece até parecer jurídico e contábil.
- Nada simulado: biometria, assinatura qualificada, ICP-Brasil, gov.br, SMS, Stripe real, provedor
  fiscal, KYC, identidade governamental.
- Nenhum teste enfraquecido ou removido para ficar verde; contagens fixas só mudam com a razão
  escrita ao lado.
- Desconhecido ≠ zero; GMV ≠ receita.

## 6. Ambiente desta rodada

PostgreSQL 16 local (testes), Chromium via Playwright, ruff, Node (esbuild). Sem acesso a registro
npm (lockfile versionado; typecheck oficial roda no CI). Push de tag e API de escrita do GitHub
recusados pelo proxy — a tag `v0.26.0` será criada localmente e deverá ser criada no GitHub pelo
dono, como na v0.25.0.
