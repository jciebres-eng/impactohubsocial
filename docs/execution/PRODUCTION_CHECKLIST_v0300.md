# Checklist de validação de produção — v0.30.0

Estado de cada item nesta instalação de referência (sem produção): **FEITO** (provado por teste ou execução registrada),
**PENDENTE DO PROPRIETÁRIO** (credencial, conta, parecer, decisão) ou **PENDENTE DA EQUIPE** (pessoa da área). Nada marcado FEITO por suposição.

## A. Antes de subir a v0.30.0

| # | Item | Estado | Como conferir |
|---|---|---|---|
| A1 | Backup da base anterior guardado fora do host (`pg_dump -Fc`) | PENDENTE DO PROPRIETÁRIO | `docs/execution/ROLLBACK_v0300.md` §0 |
| A2 | Migração 0070 aplicada do zero e sobre cópia da v0.29.0 com ROLLBACK (dry-run) | FEITO | `impacto_m70` (template de m69 + 0069; 0070 em BEGIN/ROLLBACK) e suíte; `test_v0230_data_infra_gate` (nenhum DROP de tabela) |
| A3 | Regressão completa (2 passagens: 2400 testes, 0 erro; falhas só de fechamento/regeneração) e portões 169/169; robô de telas 227 OK | FEITO | `docs/evidence/test_run_v0.30.0.log`; `FINAL_EXECUTION_REPORT.md` §24 |
| A4 | CI do GitHub (auditoria, backend, docker, pilha-do-zero) verde no commit final | FEITO (`5d46e50`, run `37957125812`, 4/4 verdes na primeira tentativa) | `FINAL_EXECUTION_REPORT.md` §3 |
| A5 | Pacote confere byte a byte com o git; sem segredo; sem ZIP aninhado | FEITO no fechamento | `verify_package_against_git.py`, `secrets_scan.py`, `unzip -t` |
| A6 | Tag `v0.30.0` no commit de fechamento | PENDENTE DO PROPRIETÁRIO (proxy recusa push de tag) | GitHub → Releases |
| A7 | Evidências existentes continuam válidas após a 0070 | FEITO | colunas novas com DEFAULT (`method='unknown'`, `access_level='parties'`, `consent_basis='unknown'`, `retention_class='project'`, `version=1`); nenhum UPDATE em massa; o CHECK de rejeição é `NOT VALID` (vale para linhas que mudem daqui em diante) |

## B. Dados existentes e compatibilidade

| # | Item | Estado | Regra |
|---|---|---|---|
| B1 | Evidências antigas `rejected` sem `review_note` ≥ 10 caracteres | FEITO (não bloqueia) | o CHECK é `NOT VALID`: linhas antigas ficam como estão; para saber quantas são: `SELECT count(*) FROM evidences WHERE status='rejected' AND (review_note IS NULL OR length(review_note) < 10)`; completar notas é trabalho editorial com auditoria, depois `ALTER TABLE evidences VALIDATE CONSTRAINT evidences_rejection_has_reason` |
| B2 | Evidências antigas sem método/consentimento | FEITO | ficam `unknown` — lacuna visível na API e no dossiê, nunca "ok" |
| B3 | Indicadores: `method` existente não gera registro de mudança | FEITO | o gatilho só dispara em UPDATE que altere `method` |
| B4 | Nenhuma variável de ambiente nova | — | — |

## C. Fumaça após subir (10 minutos)

| # | Passo | Esperado | Estado |
|---|---|---|---|
| C1 | `GET /readyz` | `status = ready`, sem `pending_migrations` (última: 0070) | FEITO na suíte |
| C2 | OSC envia evidência sem método → `GET /v1/evidences/{id}` | `method = unknown`, `gaps` inclui `method`, aviso "integridade, não a veracidade" | FEITO (`test_v0300_evidence_object`) |
| C3 | Financiador rejeita sem motivo | 422 `reason_required`; com motivo: 200 e histórico com a razão | FEITO |
| C4 | OSC contesta; financiador decide | `contested → under_review → accepted/rejected`; histórico completo; outra organização 404 | FEITO |
| C5 | OSC substitui evidência | nova versão 2; anterior `superseded` legível; substituída não se revisa | FEITO |
| C6 | Abrir `/projetos/:id/dossie` como dona e como financiador | mesma leitura; origem e atualidade em cada bloco; lacunas declaradas; sem erro de console; contraste ok claro/escuro | FEITO (`test_e2e_v0300_dossier`) |
| C7 | Empresa sem relação com o projeto abre o dossiê | 404 | FEITO (`test_v0300_dossier`) |
| C8 | Mudar método de indicador sem motivo | 422; com motivo: registro e `comparable = false` no dossiê | FEITO |
| C9 | Aceitar evidência | nenhuma transferência registrada/confirmada muda | FEITO |

## D. Decisões e trabalho de pessoas (do baseline)

| # | Passo | Estado | Evidência exigida |
|---|---|---|---|
| D1 | Decidir formalmente sobre as propostas do pacote recusadas por ADR (escrow, retenção, assinatura, selo pago) — manter ou reabrir com parecer | PENDENTE DO PROPRIETÁRIO | ADR nova em `DECISIONS.md` se mudar |
| D2 | Revisão jurídica/contábil da matriz de elegibilidade de cobrança (`docs/SAAS_ECONOMY.md` §4) | PENDENTE DO PROPRIETÁRIO | cartas em `MONETIZATION_LEGAL_MATRIX.md` |
| D3 | Política de retenção por classe de evidência (`project`/`accountability`/`legal_hold`): prazos em `config/data_retention.json` | PENDENTE DO PROPRIETÁRIO (DPO) | prazos declarados; teste de retenção |
| D4 | Itens P2 do baseline (conflito de interesse por serviço; versão das regras de elegibilidade no match) | próxima rodada técnica | — |

## E. O que esta lista NÃO afirma

Que evidência aceita é verdade (é conferida no escopo registrado); que o dossiê é auditoria; que algum percentual de take rate é
preço; que há provedor de pagamento, fiscal ou escrow; que o sistema é "100% impossível de invadir".
