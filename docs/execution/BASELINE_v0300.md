# Baseline e mapa de lacunas — IMPACTO v0.30.0 (pacote "Superprompts Master")

**Data:** 09/10/2026 · **Base recebida:** repositório `jciebres-eng/impactohubsocial`, ramo `main`, `79a326d` (v0.29.0 fechada;
tag candidata `dd2f8c3`; CI 4/4 verde na run `37935603837`) · **Working tree:** limpo · **Convenção:** SemVer (`VERSION`,
`backend/pyproject.toml`, `web/package.json`) · **Próxima versão:** 0.30.0.

Este documento é a resposta ao `01_SUPERPROMPT_MASTER_ORQUESTRADOR.md` §"Regra absoluta: trabalhe na base real": inventário
em QUATRO estados — **PROVADO** (código + teste executado), **PARCIAL**, **SÓ DOCUMENTADO/MOCK**, **AUSENTE** — por contexto
delimitado, com a evidência no repositório. Nenhuma linha aqui foi marcada PROVADO por existir documento, rota, botão ou tela:
a prova é o teste nomeado (2.380 testes na regressão da v0.29.0, `docs/evidence/test_run_v0.29.0.log`).

## 0. Conflitos entre o material do pacote e as decisões vinculantes do repositório

O contexto original do pacote (`09_CONTEXTO_ORIGINAL_FORNECIDO.md`, conversa com outro modelo) propõe três mecanismos que os
próprios superprompts classificam como **hipóteses a validar**, e que as decisões já tomadas pelo proprietário neste
repositório **recusam ou substituem**. Nenhum deles será implementado nesta rodada; ficam registrados como decisão do
proprietário:

| Proposta do contexto | Decisão vigente (DECISIONS.md) | Consequência nesta rodada |
|---|---|---|
| Escrow / conta gráfica / BaaS com liberação por marco e **retenção automática** do take rate "no momento da liberação" | **ADR-284** (nenhuma fintech dentro do IMPACTO; não custodial — `NON_CUSTODIAL_ARCHITECTURE.md`; teste de estrutura do banco recusa tabela de saldo de terceiros) e **ADR-337** (a taxa nasce na origem, é cobrança própria ao pagador e **nunca é descontada de dinheiro em trânsito**) | não há escrow nem retenção; a liberação por marco é *instrução* ao pagador + *confirmação* por quem recebe (`allocation_payouts`, `payout_transfers`). O superprompt 04 pede exatamente essa separação ("aprovação de evidência ≠ liquidação") — já é o desenho |
| "Assinatura corporativa SaaS" (mensalidade B2B/B2G por painéis) | **ADR-341** (não existe mais assinatura; pacotes de capacidades por concessão/convênio/contrato avulso) | não volta. Receita por serviço avulso/contrato continua possível (`offer_acceptances`) |
| Take rate "2 %–5 % retido automaticamente" | **ADR-337/ADR-341** (3,5 % taxa de serviço + 1,5 % participação de autoria, do catálogo, congelados no acordo, **regra inativa** até parecer) | a simulação em múltiplos percentuais (superprompt 03 §5) entra como **sensibilidade** do modelo de 24 meses, declarada hipótese; nenhum percentual muda |
| "Selo / certificação paga de replicabilidade" | **ADR (selos)**: selo só por critério e fato (quitação), nunca por pagamento | não implementado; conflita com "não pay-to-rank" |
| "Repositório imutável", "auditoria elimina risco" | ADR-043/ADR-312..316: hash prova integridade do conteúdo, não veracidade; o próprio superprompt 04 exige essa distinção | mantido como está, com a frase na interface |

## 1. Inventário por contexto delimitado

| Contexto | Estado | Evidência (código · teste) | Lacuna relevante para o pacote |
|---|---|---|---|
| Identidade, sessão, MFA, RBAC/ABAC, entitlements | PROVADO | `core/access.py` (AccessContext), `staff_roles`, step-up; `test_v0230_api_sweep` (936 operações), `test_v0230_authorization_matrix`, `test_v0220_internal_ui` | — |
| Organização, perfis (6 tipos), onboarding | PROVADO | `test_v0250_jornadas` (16 jornadas, 256 passos), `test_v0250_todas_as_telas` (226 telas × perfil) | — |
| Diagnóstico e prontidão (8 dimensões, versões imutáveis) | PROVADO | `core/diagnostic.py`, `diagnosis_versions`; `test_v0150_*`, `impact_core_hardening` | — |
| Elegibilidade institucional (regras publicadas, "pendente" sem regra) | PROVADO | `INSTITUTIONAL_ELIGIBILITY_ENGINE.md`; `test_v0100_institutional` | — |
| Match (critérios explicados, confiança, sem pay-to-rank, versão dos pesos) | PROVADO | `engines/match/`; `test_similarity_touches_neither_match…`, `test_architecture` | o resultado guarda versão do motor; **não guarda** a versão das regras de elegibilidade usada (P2) |
| Evidências (envio, revisão por financiador/governo, ledger, notificação) | **PARCIAL** | `evidences` (0001): kind, título, data, documento (hash via `documents`), `status ∈ submitted/accepted/rejected/needs_info`, nota de revisão; `execution_routes.py`; `test_v080`, jornadas | **faltam** (superprompt 04 "evidência como objeto de primeira classe"): método de coleta, nível de acesso, base de consentimento, classe de retenção, versão/substituição (`superseded`), **contestação** (`contested`) com direito de resposta, histórico de estados próprio, justificativa obrigatória na rejeição, exposição do hash e da distinção declarado/verificado/validado na própria evidência |
| Indicadores longitudinais (reportado × validado; validação por outra organização; evidência obrigatória para validar; proveniência com lacunas) | PROVADO | `indicator_values` (0004, 0053), `engines/provenance.py`; `test_v0230_provenance` | unidade vive no catálogo e método em `project_indicators.method` (texto livre); **mudança metodológica** não tem registro próprio (P1) |
| Acompanhamento no tempo (trilha hash, transições, snapshots) | PROVADO | `LONGITUDINAL_TRACKING.md`; `ledger_entries`, `project_transitions`, `project_snapshots`; `test_v0230_audit_engine` | — |
| Dossiê longitudinal para o financiador (uma leitura só: evidências por estado, séries reportadas × validadas, lacunas, diligências, marcos, versão das regras) | **AUSENTE como objeto** (as peças existem separadas: `/v1/control-tower/funder`, `/v1/public/projects/{id}/impact`, relatório de impacto, prontidão, `impacto_ready`) | — | P0: agregador somente-leitura com RLS do projeto, que declara origem/qualidade/atualidade/lacuna de cada bloco e nunca inventa número |
| Marcos, acordos como regra, obrigações, instrução de pagamento, confirmação por quem recebe, quitação, reconhecimento | PROVADO | 0066/0067; `test_v0260_contract_rules`, `test_v0270_economy`, jornada "caminho dourado" | o superprompt 04 pede estados nomeados "aporte confirmado pelo parceiro / autorização de liberação / liquidação confirmada": existem como `payout_transfers` (registrado por quem paga, confirmado por quem recebe) — **mapeamento explícito dos estados** falta em documento (P1, documental) |
| Profissionais (perfil, credencial conferida pela administração, necessidades → ofertas → aceite → entregas → revisão técnica → contestação de reputação) | PROVADO | `/v1/professional/*`, `/v1/professional-reviews`, `/v1/reputation/disputes`; jornada "Profissional" (9 passos) | conflito de interesse declarado por serviço: **AUSENTE** (P2) |
| Promotor de ideias (ideia → amadurecimento → promoção a projeto) | PROVADO | `ideas` (0013), `/v1/ideas`; jornada "Banco de Ideias" (5 passos) | busca de parceiros/oportunidades a partir da ideia: PARCIAL (match é de projeto) (P2) |
| Governo (torre, território, necessidades, edital público, estatísticas k-anônimas) | PROVADO | `/v1/control-tower/government`, `/v1/gov/territory-stats`, `/v1/territory/needs`; jornada "Governo" (25 passos) | relatório por instrumento (MROSC) é modelo editorial, não motor (LEG-014 PARTIAL na reconciliação) |
| Superadmin/auditor (torre master, auditoria encadeada, moderação em escada, interruptor de emergência, acesso privilegiado registrado, quatro olhos) | PROVADO | `killswitch.py`, `enforcement_ladder`, `privileged_access_log`; `test_v0230_security_gate`, `test_v0230_audit_engine` | — |
| Monetização (catálogo de 11 regras, 0 ativas; camada 3,5 %/1,5 %; créditos de IA em piloto; cartas jurídicas) | PROVADO (como registro) / BLOCKED_EXTERNAL (ativação) | `MONETIZATION_LEGAL_MATRIX.md`, `24_MONTH_FINANCIAL_MODEL.md`, `test_v0270_financial_model` | "Economia do SaaS" (pagador → valor → evento → preço-hipótese → custo → margem → alternativa) e **simulação de take rate em múltiplos percentuais** não existem como documento gerado (P1) |
| Billing: idempotência, webhook assinado, estados, estorno, reconciliação | PROVADO para o que existe (webhook HMAC idempotente, pedido piloto × real, cobrança só com autorização) | `test_v0280_ai_usage_control`, `charge_requires_authorization` v3 | provedor real ausente (BLOCKED_EXTERNAL); "preço alterado entre visualização e checkout": coberto por versão congelada da operação (ADR-347) |
| Fiscal (NFS-e, retenções) | SÓ DOCUMENTADO + adaptador desligado | `FISCAL_RULE_ENGINE.md`, `engines/fiscal` | BLOCKED_EXTERNAL (provedor, parecer) |
| Central de conhecimento (fontes, citações, retirada, fila, busca medida, glossário) | PROVADO (v0.29.0) | `test_v0290_*` | — |
| Notificações e recomendações | PROVADO | `app_notify`, `today_cards`, `recommendation` | — |
| LGPD (exportação, eliminação, retenção declarada, redação) | PROVADO | `test_v0190_lgpd_deletion`, `config/data_retention.json` | ROPA/RIPD/DPO: BLOCKED_EXTERNAL |
| CI/CD, Docker, pilha do zero, E2E por perfil, acessibilidade | PROVADO | `.github/workflows/ci.yml` (4 trabalhos), `test_e2e_*`, axe | — |

## 2. Matriz perfil × jornada × permissão × dado × ação

Existe de forma **gerada** e conferida por teste: `docs/execution/API_AUTHORIZATION_MATRIX.csv` (936 operações × 10 papéis),
`docs/execution/COVERAGE_MATRIX.md`, `PERSONA_E2E_MATRIX.csv`, `screen_backend_map.json` (tela → operações). O que falta é a
leitura **por jornada** num só lugar — entra como `docs/execution/PROFILE_JOURNEY_MATRIX_v0300.md` (gerado) nesta rodada (P1).

## 3. Plano desta rodada (P0/P1/P2), cada item com critério de aceite

| # | Item | Pri. | Problema → evidência | Mudança | Teste / aceite |
|---|---|---|---|---|---|
| 1 | Evidência como objeto de primeira classe | **P0** | `evidences` sem método, acesso, consentimento, versão, contestação, histórico | migração 0070: `method`, `access_level`, `consent_basis`, `retention_class`, `version`, `supersedes_id`, status `contested`/`superseded`/`under_review`, `evidence_events` append-only, justificativa obrigatória para `rejected`/`contested` (CHECK); rotas: contestar (OSC), substituir (OSC), decidir contestação (revisor); GET expõe hash do documento + "hash prova integridade, não veracidade" | `test_v0300_evidence_object`: CHECKs no banco; contestação exige motivo; substituição marca a anterior `superseded` e preserva histórico; quatro olhos (quem envia não revisa); outra organização 404; aceite de evidência **não** muda `payout_transfers` |
| 2 | Dossiê longitudinal do projeto para financiador/governo | **P0** | peças separadas; nenhuma leitura única com lacunas declaradas | `services/dossier.py` + `GET /v1/projects/{id}/dossier` (somente leitura; RLS; blocos: identidade, prontidão/`impacto_ready`, marcos e obrigações, evidências por estado com qualidade/atualidade, indicadores reportado × validado por série com método/unidade, lacunas UNKNOWN, diligências abertas, versão das regras; `what_this_is_not`) + tela `/projetos/:id/dossie` | `test_v0300_dossier`: número não existe sem fonte; UNKNOWN permanece; anônimo/outra org 404; financiador com candidatura vê; E2E abre a tela com legenda/fonte/data |
| 3 | Mudança metodológica de indicador registrada | P1 | `project_indicators.method` texto livre, sem histórico | `indicator_method_changes` append-only (de → para, motivo, data, quem) + aviso na série ("comparação quebrada em X") | teste: alterar método grava registro; série marca descontinuidade |
| 4 | Matriz perfil × jornada × permissão × dado × ação | P1 | existe por partes | `scripts/make_profile_journey_matrix.py` → `docs/execution/PROFILE_JOURNEY_MATRIX_v0300.md` | teste de reprodução (padrão `test_v0230_execution_matrices`) |
| 5 | Economia do SaaS + simulação de take rate | P1 | modelo de 24 meses só com 3,5 % | seção "Sensibilidade do take rate" (2 %, 3 %, 3,5 %, 4 %, 5 %: quem suporta, efeito no líquido do projeto, receita) no gerador `make_24_month_model.py`; `docs/SAAS_ECONOMY.md` (pagador → valor → evento → preço-hipótese → custo → margem → alternativa) | `test_v0270_financial_model` continua provando documento = gerador; marcadores [PREMISSA] |
| 6 | Estados do financiamento por marcos documentados contra o código | P1 | superprompt 04 pede nomes de estado | `docs/execution/MILESTONE_FUNDING_STATES_v0300.md` mapeando cada estado pedido ao objeto/coluna/teste real (ou "não existe") | conferido pelo teste de documentos (nomes de tabela/coluna existem) |
| 7 | Conflito de interesse declarado por serviço profissional | P2 | ausente | fora desta rodada — registrado | — |
| 8 | Match: guardar versão das regras de elegibilidade | P2 | ausente | fora desta rodada — registrado | — |

Itens 7–8 e tudo o que depende de parceiro, parecer ou DPO ficam explicitamente como pendência (seção 4).

## 4. Bloqueios e o que NÃO será feito

- Escrow, conta gráfica, split, retenção automática, assinatura, selo pago: recusados por ADR (seção 0) — decisão do proprietário, não lacuna técnica.
- Provedor de pagamento, fiscal, identidade, DPO, parecer jurídico/contábil: BLOCKED_EXTERNAL (`EXTERNAL_INTEGRATIONS.md`).
- Nenhum teste de "assinatura expirada/cancelada" (superprompt 06 §3): não existe assinatura (ADR-341); o equivalente — concessão expirada (`GRANT_EXPIRING`/`FREE_ACCESS`) — já tem teste (`test_v0270_no_subscription`).
- Nenhuma métrica, preço ou resultado será apresentado como pesquisado: tudo marcado [PREMISSA]/hipótese.
