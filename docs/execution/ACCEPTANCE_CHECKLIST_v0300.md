# Checklist de aceite do incremento — v0.30.0 (modelo: `08_CHECKLIST_ACEITE_RELEASE.md` do pacote)

Cada item: **PASSOU**, **FALHOU**, **BLOQUEADO** ou **NÃO EXECUTADO**, sempre com evidência. Nenhum item marcado PASSOU por
documento, rota, mock ou tela — só por teste executado ou arquivo gerado.

## Produto e arquitetura

| Item | Estado | Evidência |
|---|---|---|
| Inventário do que existe vs. documentado vs. ausente | PASSOU | `docs/execution/BASELINE_v0300.md` (4 estados por contexto, teste por linha) |
| Jornadas dos seis perfis mapeadas | PASSOU | `docs/execution/PROFILE_JOURNEY_MATRIX_v0300.md` (gerada: 16 jornadas, 256 passos, 8 perfis incl. visitante/suporte) |
| Autorização aplicada no backend e validada por testes negativos | PASSOU | `test_v0230_api_sweep` (940 operações), `test_v0230_authorization_matrix`, `test_v0300_dossier` (404 para quem não é parte), `test_v0300_evidence_object` (403/404) |
| Motores de diagnóstico, match, evidência e monitoramento avaliados | PASSOU | baseline §1; `MOTOR_COVERAGE_MATRIX.md` (50 motores, 0 vermelhos); evidência e monitoramento ampliados (0070) |
| Dados ausentes permanecem UNKNOWN; sem score inventado | PASSOU | `test_v0300_dossier` (lacunas declaradas; `unknown` em prontidão/método/consentimento); `what_this_is_not` |
| Interface explica estados, fontes, bloqueios e próximos passos | PASSOU (nas telas tocadas) | `test_e2e_v0300_dossier` (origem, atualidade, lacunas, "não é nota"); robô de 227 telas |

## Financeiro

| Item | Estado | Evidência |
|---|---|---|
| Catálogo de monetização e mapa de eventos de cobrança | PASSOU | `docs/SAAS_ECONOMY.md` §1–§2 a partir de `monetization_rules` (11 regras) |
| Hipóteses de preço explicitamente identificadas | PASSOU | `[PREMISSA]` em `24_MONTH_FINANCIAL_MODEL.md` e `SAAS_ECONOMY.md`; `test_v0300_release_docs` |
| Gratuidade e transição de campanha sem conflitos de regra | PASSOU | não há transição: não existe assinatura (ADR-341); núcleo gratuito provado por `test_v0270_no_subscription` |
| Ledger/reconciliação testados; nenhum dinheiro real movimentado | PASSOU | `test_v0270_economy`, `test_v0300_evidence_object` (aceitar evidência não move repasse); provedor ausente |
| Webhooks idempotentes e assinaturas verificadas | PASSOU (para o que existe) | `test_v0280_ai_usage_control.WebhookWithSecretTests` |
| Estorno/cancelamento atualizam entitlements | PASSOU (contratos avulsos/concessões) | `test_v0270_no_subscription`; não há assinatura a estornar |
| Parceiro e modelo de repasse confirmados antes de qualquer fluxo real | BLOQUEADO (externo) | `EXTERNAL_INTEGRATIONS.md`; `MILESTONE_FUNDING_STATES_v0300.md` (sem parceiro, sem escrow) |
| Matriz fiscal/jurídica sinalizada para validação especializada | PASSOU (sinalizada) / BLOQUEADO (validação) | `SAAS_ECONOMY.md` §4; `MONETIZATION_LEGAL_MATRIX.md` |

## Evidências e governança

| Item | Estado | Evidência |
|---|---|---|
| Origem, autoria, timestamp, versão e estado das evidências | PASSOU | 0070; `GET /v1/evidences/{id}`; `test_v0300_evidence_object` |
| Relatórios distinguem declarado, revisado e validado | PASSOU | `classification` da evidência; dossiê (validadas × declaradas × contestadas); séries reportado × validado |
| Indicadores longitudinais preservam metodologia e histórico | PASSOU | `indicator_method_changes` (ADR-362); valores nunca reescritos |
| Decisões de auditoria têm justificativa e trilha | PASSOU | motivo obrigatório para rejeitar/contestar; `evidence_events`; auditoria encadeada |
| Controles privilegiados e emergência testados | PASSOU (inalterado) | `test_v0230_security_gate`, kill switch |
| LGPD, isolamento multi-tenant e retenção avaliados | PASSOU / PENDENTE (prazos por classe de evidência: DPO) | `test_v0190_lgpd_deletion` (atualizado), RLS nas tabelas novas; checklist D3 |

## Qualidade

| Item | Estado | Evidência |
|---|---|---|
| Build/compilação | PASSOU | `node build.mjs`; `tsc --noEmit` 0 erros (tipos locais; oficial no CI) |
| Lint e análise estática | PASSOU | ruff 0 |
| Testes unitários / integração / contrato | PASSOU | ver `FINAL_EXECUTION_REPORT.md` §24 (regressão completa) |
| Migrações em banco limpo e upgrade | PASSOU | suíte (do zero) + `impacto_m70` (upgrade sobre m69, BEGIN/ROLLBACK) |
| E2E browser por perfil | PASSOU | `test_e2e_v0300_dossier` (dona + financiador), suíte E2E existente |
| Acessibilidade e responsividade | PASSOU (telas tocadas) | A11Y_JS + contraste claro/escuro no dossiê; `test_e2e_v0181_accessibility` |
| Testes de segurança e autorização negativa | PASSOU | sweep 940 operações; `test_v0230_security_gate` |
| Regressão após correções | PASSOU (2ª passagem 0 erro; portões 169/169; CI 4/4 verde em `5d46e50`) | `docs/evidence/test_run_v0.30.0.log`; run `37957125812` |
| ZIP validado e SHA-256 calculado | PASSOU | `IMPACTO_TRUST_FINAL_RELEASE_0.30.0.zip` (3.726 arquivos, byte a byte = `5d46e50`); SHA-256 `3f1f3988…f086a5` |

## Release

| Item | Estado | Evidência |
|---|---|---|
| Changelog e notas de release | PASSOU | `CHANGELOG.md` [0.30.0], `RELEASE_NOTES.md` |
| Versão coerente com a base real | PASSOU | `VERSION`, `pyproject`, `package.json`, `openapi.json`, README (`test_v0230_release_gate`) |
| Segredos excluídos | PASSOU | `secrets_scan.py`; gitleaks no CI |
| Instruções de instalação e rollback | PASSOU | `README.md`, `docs/execution/ROLLBACK_v0300.md`, `PRODUCTION_CHECKLIST_v0300.md` |
| Relatório final diferencia fatos, hipóteses e pendências | PASSOU | `FINAL_EXECUTION_REPORT.md`, `FINAL_EXECUTION_AUDIT.md` |
