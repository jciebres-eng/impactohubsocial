# Relatório final de execução — IMPACTO v0.30.0

**Data:** 09/10/2026 · **Ramo:** `main` · **Tag:** `v0.30.0` (a criar no GitHub pelo proprietário no commit indicado em §3 — o
proxy deste ambiente recusa envio de tag) · **Pacote:** `IMPACTO_TRUST_FINAL_RELEASE_0.30.0.zip` (SHA-256 no `.sha256` ao lado) ·
**Auditoria:** `FINAL_EXECUTION_AUDIT.md` · **Relatório técnico (DOCX):** `IMPACTO_v0.30.0_RELATORIO_TECNICO.docx`

## 1. Executive Summary

A rodada executou o pacote "IMPACTO_SUPERPROMPTS_MASTER" do jeito que ele manda: **inspeção e baseline antes de qualquer
alteração**, inventário em quatro estados, plano P0/P1/P2 com evidência, implementação do viável com testes, regressão, versão,
pacote e relatório — sem presumir que documento, rota, mock ou tela signifiquem funcionalidade pronta.

- **Baseline** (`docs/execution/BASELINE_v0300.md`): 18 contextos classificados (PROVADO / PARCIAL / SÓ DOCUMENTADO / AUSENTE) com o
  teste que prova cada linha. Lacunas reais encontradas: evidência rasa (sem método, acesso, consentimento, versão, contestação,
  histórico), dossiê inexistente como objeto, mudança metodológica sem rastro, matriz por jornada dispersa, economia do SaaS e
  take rate sem documento gerado.
- **Conflitos registrados e NÃO implementados** (ADR-363): escrow/conta gráfica, retenção automática do take rate, assinatura
  corporativa e selo pago — o contexto do pacote os propõe, as decisões do repositório (ADR-284, 337, 341, selos) os recusam e os
  próprios superprompts os chamam de hipóteses.
- **Evidência como objeto de primeira classe** (ADR-360, migração 0070): método de coleta, nível de acesso, base de consentimento,
  classe de retenção (`unknown` é lacuna visível); versão + substituição (nunca edição); **rejeitar exige motivo**; a executora
  **contesta** com motivo e quem revisa decide com justificativa; máquina de estados e histórico append-only **no banco**; hash do
  documento exposto com "integridade ≠ veracidade"; aceitar evidência **não move dinheiro** (teste).
- **Dossiê longitudinal** (ADR-361): `GET /v1/projects/{id}/dossier` + `/projetos/:id/dossie` — prontidão, marcos/obrigações,
  evidências por estado com qualidade, séries reportado × validado com método/unidade/descontinuidade, aportes e repasses,
  diligências, trilha — cada bloco com **origem, atualidade e lacunas**; "o que isto não é" no topo; só para as partes; a OSC vê
  exatamente o que o financiador vê.
- **Mudança metodológica registrada** (ADR-362): motivo obrigatório, append-only, série marca `comparable = false`.
- **Economia do SaaS** a partir do catálogo real (11 regras, 0 ativas, 5 recusadas), **sensibilidade do take rate 2–5 %** como
  simulação (catálogo inalterado), **estados do financiamento por marcos** mapeados ao código (decisão ≠ instrução ≠ confirmação;
  escrow "não existe" provado), **matriz perfil × jornada × permissão × dado × ação** gerada (16 jornadas, 256 passos).
- **Contagens** (ADR-340): 940 operações (+4), 227 telas (+1), 70 migrações, 50 motores (nenhum novo).
- Tudo provado por HTTP e PostgreSQL reais (20 testes novos em 4 módulos), no Chromium (dossiê: dona e financiador, claro e escuro,
  a11y e contraste), pelas 227 telas por perfil e pela regressão completa (§24), cuja primeira passagem acusou 10 falhas — todas
  com causa e correção (auditoria §7), nenhuma resolvida afrouxando teste.

**Decisão: GO WITH CONDITIONS** (§27) — condições externas e decisórias, não técnicas.

## 2. Version

0.30.0 — `VERSION`, `backend/pyproject.toml`, `web/package.json`, `web/package-lock.json`, `README.md`, `docs/openapi.json`.
Documentos da v0.29.0 preservados em `history/v0.29.0/` (166 arquivos de `79a326d`); manifestos anteriores em `history/manifests/`.

## 3. Commit

Commits da rodada (sobre `79a326d`, v0.29.0): `3f5f139` (F1: versão, snapshot, baseline, P0 evidência — 0070, rotas, 7 testes),
`90aa5ef` (F2: P0 dossiê + P1 mudança metodológica, tela, 4 testes + 1 E2E), `21361f6` (F3: matriz por jornada, sensibilidade do take
rate, SAAS_ECONOMY, estados do financiamento, 8 testes de documento), commit de matrizes/contagens, `81d0792` (correções da 1ª
regressão, ADR-360..363, changelog, notas, checklists, rollback, limpeza), o commit de fechamento (auditoria, relatório, evidência da
regressão) e o **commit final dos manifestos**, para o qual a tag `v0.30.0` deve apontar e do qual o pacote é construído byte a byte
(`verify_package_against_git.py`); o hash desse commit é registrado no `.sha256` do pacote. `FINAL_RELEASE_MANIFEST.json` registra o
último commit de conteúdo.

**GitHub Actions:** run `37957125812` do commit candidato à tag `5d46e50`: `auditoria` (gitleaks + ruff), `docker` (typecheck
oficial `tsc --noEmit` + build), `pilha-do-zero` (banco vazio → imagem → migrações 0001–0070 → seed → jornadas → 227 telas → axe →
reinício) e `backend` (suíte oficial completa) — **os quatro verdes na primeira tentativa**. Este parágrafo foi acrescentado depois
da run, no commit seguinte; a tag `v0.30.0` aponta para `5d46e50`.

## 4. Architecture Status

Starlette + PostgreSQL 16 com RLS em toda tabela (exceção: `schema_migrations`; nenhuma FORCE), hash encadeado em auditoria/razão/
valor/confiança, sem custódia. Mudanças: 2 tabelas novas append-only (`evidence_events`, `indicator_method_changes`); `evidences` com
11 colunas e 3 estados a mais, máquina de estados e guardas; `project_indicators.method_change_reason` + gatilho; 4 rotas novas;
`services/dossier.py` (composição somente-leitura); `scripts/make_profile_journey_matrix.py`; `web/src/pages/impact.tsx::ProjectDossier`.
Documentos canônicos: `docs/execution/BASELINE_v0300.md`, `docs/SAAS_ECONOMY.md`, `docs/execution/MILESTONE_FUNDING_STATES_v0300.md`,
`docs/execution/PROFILE_JOURNEY_MATRIX_v0300.md`, `docs/execution/ACCEPTANCE_CHECKLIST_v0300.md`.

## 5. Engines Status

50 motores: implemented/integrated/tested 50/50; `MOTOR_COVERAGE_MATRIX.md` (gerado) VERDE 37 · AMARELO 13 · VERMELHO 0. Nenhum motor
novo: o dossiê é composição (não decide); o teste de registro (`test_v0200_engines`) foi quem apontou que `ENGINE_VERSION` no módulo
o faria parecer motor — renomeado para `DOSSIER_VERSION`.

## 6. Contract Intelligence

PASS (inalterado). O dossiê lê obrigações do contrato (`agreement_obligations`) e não escreve nelas.

## 7. Match

PASS (inalterado): nenhum dado novo (evidência, dossiê, método) entra no match; sem pay-to-rank. Registrado como P2: guardar no
resultado do match a versão das regras de elegibilidade usada.

## 8. Diagnostic

PASS (inalterado): o dossiê reusa `project_ready_facts()`/`control_tower.ready` (15 critérios, `unknown` é terceiro estado).

## 9. Equity

PASS (inalterado). O dossiê não cria nota nem ranking; "delta não implica causalidade" está no `what_this_is_not`.

## 10. Evidence

**PASS — ampliado** (ADR-360): objeto de primeira classe. O que a v0.30.0 não faz: assinatura qualificada, carimbo de tempo externo
(RFC 3161), auditoria independente — o aviso na API diz o que o hash prova.

## 11. Responsibility

PARTIAL (inalterado): atribuição formal continua opcional. Conflito de interesse por serviço profissional: P2.

## 12. Reputation

PASS (inalterado). Contestação de evidência não produz efeito reputacional.

## 13. Seals

PASS (inalterado): selo só por critério e fato; **selo pago** (proposta do pacote) recusado (ADR-363).

## 14. Government Data

Inalterado: torre territorial k ≥ 3. O governo com acesso de revisão vê o dossiê (`app_review_access`).

## 15. Marketplace

Inalterado: comissão recusada (`marketplace.take_rate` **refused** no catálogo).

## 16. Payments

Inalterado (PASS / BLOCKED_EXTERNAL): nenhum pagamento real; **escrow/conta gráfica não existe e não existirá dentro do produto**
(ADR-284; `MILESTONE_FUNDING_STATES_v0300.md`); aprovação de evidência ≠ liquidação (teste).

## 17. Distribution

PASS (inalterado).

## 18. Billing

Inalterado: sem assinatura (ADR-341); `docs/SAAS_ECONOMY.md` documenta o catálogo e a matriz de elegibilidade de cobrança.

## 19. Fiscal

BLOCKED_EXTERNAL (inalterado): quem presta/fatura/recolhe por fluxo está em `SAAS_ECONOMY.md` §4; emissão real desligada.

## 20. Vouchers

Inalterado.

## 21. Identity

PARTIAL (inalterado).

## 22. Security

Revisada: 4 rotas novas na matriz de autorização (940); dossiê só para as partes; 2 tabelas novas com RLS e append-only; quatro olhos
preservado nas evidências (quem envia não revisa; só a executora contesta); conteúdo da evidência imutável após o envio; nenhum
segredo em código, documento ou pacote (`secrets_scan.py`, gitleaks no CI). **Nenhum sistema ligado à internet é "impossível de
invadir", e este não é exceção.**

## 23. LGPD

`evidence_events`/`indicator_method_changes` guardam referências de ator (trilha editorial), não dado do titular; `access_level`,
`consent_basis` e `retention_class` passam a existir por evidência (`unknown` visível); prazos por classe dependem do DPO (checklist D3);
`test_v0190_lgpd_deletion` verde com a expectativa atualizada (evidência deixou de ser apagável — histórico append-only).

## 24. Tests

```text
PRIMEIRA REGRESSÃO COMPLETA (código novo, antes das correções, scratchpad/suite/full_v0300_a.log):
  Ran 2400 tests in 1947.064s — 10 falhas, 0 erro, 30 pulados
  → causas e correções em FINAL_EXECUTION_AUDIT.md §7 (robô de telas sem resolvedor para /projetos/:id/dossie; E2E do dossiê lia a
    página antes de o dado chegar sob carga; DOSSIER_VERSION; matriz por jornada dependia de slugs aleatórios; checksum da 0070
    editada durante a rodada; documentos de fechamento e manifesto gerados no fechamento)
SEGUNDA REGRESSÃO COMPLETA (após correções, docs/evidence/test_run_v0.30.0.log):
  Ran 2400 tests in 1906.212s — 0 erro, 30 pulados (dependem de credencial), 8 falhas: 5 de fechamento (4× test_v0270_release_docs
       lendo os documentos da v0.29.0 no início da execução; manifesto gerado no fechamento) e 3 de regeneração (robô de telas sem
       resolvedor por RELAÇÃO para /projetos/:id/dossie — o dossiê é só das partes, então o financiador abre o projeto que financia;
       COVERAGE_MATRIX e PROFILE_JOURNEY_MATRIX regeradas da evidência desta rodada). Robô de telas reexecutado: 227 rotas, OK.
       Portões de fechamento reexecutados (saída anexada ao fim do mesmo log).
MÓDULOS NOVOS: test_v0300_evidence_object (7) · test_v0300_dossier (4) · test_v0300_release_docs (8) · test_e2e_v0300_dossier (1)
JORNADAS: 16 jornadas, 256 passos, 0 falha · TELAS: 227 rotas, 0 falha · TELEFONE: no CI (pilha do zero)
LINT: ruff 0 · BUILD: esbuild ok · TYPECHECK: tsc --noEmit 0 erros (local com tipos do DefinitelyTyped; oficial no CI)
```

Testes que fixam contagem foram atualizados com a razão escrita ao lado (940 operações, 227 telas): ADR-340. Expectativa atualizada
com motivo: `test_v0190_lgpd_deletion`. Nenhum teste foi removido ou enfraquecido.

## 25. External Dependencies

| Dependência | Exige | Efeito hoje |
|---|---|---|
| Decisão formal sobre as propostas recusadas por ADR (escrow, retenção, assinatura, selo pago) | proprietário | continuam fora; qualquer reabertura exige parecer e ADR nova |
| Parceiro de pagamento e modelo de repasse | contrato + análise jurídica | não há liquidação automática; instrução + confirmação continuam manuais |
| Revisão jurídica/contábil da matriz de elegibilidade de cobrança | advogado(a) e contador(a) | 0 regras ativas; R$ 0,00 |
| Prazos de retenção por classe de evidência | DPO | classes existem; prazos não declarados |
| Conferência de fontes e revisão do glossário (v0.29.0) | equipe editorial | inalterado |
| Tag `v0.30.0` no GitHub | o proxy recusa push de tag | criar manualmente |

## 26. Known Limitations

- Evidências antigas `rejected` sem nota permanecem (CHECK `NOT VALID`); completar é trabalho editorial com auditoria.
- O dossiê não sintetiza: compõe. Não há exportação em PDF; não há comparação entre projetos (de propósito).
- Hash interno prova integridade do arquivo; não há carimbo externo nem assinatura qualificada.
- A matriz por jornada lista 93 passos sem tela direta — fato medido (backend à frente da interface), não corrigido nesta rodada.
- P2 registrados: conflito de interesse por serviço profissional; versão das regras de elegibilidade no resultado do match.
- Documentos SUPERADO da assinatura continuam com banner; typecheck oficial do front só no CI; defeitos pré-existentes B1/B2 fora do escopo.

## 27. GO / GO WITH CONDITIONS / NO-GO

```text
GO WITH CONDITIONS
```

Nenhuma falha técnica interna crítica em aberto: evidência de primeira classe (origem, versão, contestação, histórico, máquina de
estados no banco), dossiê para as partes sem nota e sem assimetria, mudança metodológica registrada, autorização, tenancy,
persistência e regressão têm teste executado e verde na segunda rodada. As condições são **decisórias e externas** (§25): decisão
sobre as propostas recusadas, parceiro de pagamento, parecer da matriz de cobrança, prazos de retenção, tag no GitHub. Nenhuma
falha crítica foi convertida em "condição". Checklist operacional: `docs/execution/PRODUCTION_CHECKLIST_v0300.md`; rollback:
`docs/execution/ROLLBACK_v0300.md`; aceite: `docs/execution/ACCEPTANCE_CHECKLIST_v0300.md`.

## 28. Exact Next Step

1. Criar a tag `v0.30.0` no GitHub (Releases → nova tag no commit de fechamento) e anexar `IMPACTO_TRUST_FINAL_RELEASE_0.30.0.zip`
   + `.sha256` + o relatório DOCX.
2. Decidir, por escrito, sobre as quatro propostas do pacote recusadas por ADR (manter fora ou reabrir com parecer) — ADR nova se mudar.
3. Levar `docs/SAAS_ECONOMY.md` §4 (matriz de elegibilidade de cobrança) a advogado(a) e contador(a) junto com
   `MONETIZATION_LEGAL_MATRIX.md`; declarar com o DPO os prazos de retenção por classe de evidência.
4. Próxima rodada técnica (sem dependência externa): conflito de interesse por serviço profissional; versão das regras de
   elegibilidade no resultado do match; telas para os passos de jornada que hoje só existem na API (93, medidos); exportação do dossiê.
