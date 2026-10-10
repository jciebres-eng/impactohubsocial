# Ciclo de vida do projeto

Código: `backend/impacto/core/lifecycle.py` · rotas: `backend/impacto/api/lifecycle_routes.py` · dados:
`project_status_graph`, `project_transitions`, `project_snapshots`, `project_risks`, `ledger_entries`.

## 1. A máquina de situações é DADO, não código

As transições permitidas estão na tabela `project_status_graph` (58 linhas). Um gatilho no banco
(`project_status_guard`) recusa qualquer `UPDATE projects SET status` que não corresponda a uma linha dessa tabela —
**inclusive no contexto privilegiado**, inclusive em SQL direto.

```
test_v0150_core.test_status_guard_refuses_invalid_transition_even_in_direct_sql
```

Por que no banco e não só na API: uma rota nova, um job, um script de correção ou uma importação podem mudar
`status`. Se a regra morasse só na camada HTTP, cada caminho novo seria uma chance de furar a máquina em silêncio.

### As 17 situações

| Fase | Situações |
|---|---|
| Construção | `draft` · `diagnosing` · `structuring` |
| Aberto | `ready` · `published` · `funding` · `submitted` |
| Execução | `approved` · `funded` · `in_execution` · `monitoring` · `paused` · `blocked` |
| Encerrado | `completed` · `cancelled` · `rejected` · `archived` |

### O grafo completo

```
approved      → funded, in_execution
archived      → monitoring*
blocked       → cancelled*, in_execution, ready, structuring
cancelled     → archived
completed     → archived, monitoring
diagnosing    → cancelled*, draft, structuring
draft         → cancelled*, diagnosing, published, structuring
funded        → blocked*, cancelled*, completed, in_execution
funding       → blocked*, cancelled*, funded, in_execution, published
in_execution  → archived, blocked*, completed, monitoring, paused*
monitoring    → blocked*, completed, in_execution, paused*
paused        → cancelled*, in_execution, monitoring
published     → cancelled*, draft, funded, funding, ready, submitted
ready         → blocked*, cancelled*, published, structuring, submitted
rejected      → archived, structuring
structuring   → blocked*, cancelled*, diagnosing, ready
submitted     → approved, ready, rejected*
```

`*` = **exige motivo registrado**. Sem motivo, 422 `reason_required`. Cancelar, bloquear, pausar, recusar e reabrir
projeto arquivado são decisões que alguém precisa explicar.

### Compatibilidade com o que já existia

O produto movia projeto de `draft` para `published`, de `published` para `funded`, de `funding` para `in_execution` e
de `funded` para `completed` **antes** desta máquina existir (desde a v0.7.0). Essas transições estão no grafo com
comentário no SQL dizendo por quê. Se não estivessem, a atualização quebraria fluxos em produção — e isso é
verificado no teste de caminho de atualização
(`test_v0150_upgrade.test_05_legacy_project_transitions_still_work`).

### Recusa explicada

```json
HTTP 409
{"code": "invalid_transition",
 "title": "Transição 'Rascunho' → 'Concluído' não é permitida. A partir de 'Rascunho' é possível ir para:
           cancelled, diagnosing, published, structuring."}
```

A recusa diz **para onde é possível ir**. Erro que só diz "não pode" transfere o trabalho para a pessoa.

## 2. Transições: append-only, com ator e motivo

`project_transitions` guarda `from_status`, `to_status`, `actor_user_id`, `actor_org_id`, `reason`,
`evidence_document_id`, `automatic` e `at`. Gatilho `forbid_mutation`: a tabela **não aceita UPDATE nem DELETE**.

Transição para a situação em que o projeto já está responde `{"changed": false}` e **não** registra nada — rodar duas
vezes não produz dois registros (`test_repeated_transition_to_the_same_status_is_not_recorded_twice`).

O documento de evidência, quando informado, é conferido como pertencente à organização antes de ser aceito.

## 3. Linha de tempo: a trilha que já existia

A linha de tempo **é** `ledger_entries`, encadeada por hash desde a migração 0002:

```
entrada N:   prev_hash = entry_hash da entrada N-1
             entry_hash = sha256(conteúdo canônico || prev_hash)
```

- `GET /v1/projects/{id}/timeline` — paginada, com rótulo legível de cada tipo de entrada (41 rótulos).
- `GET /v1/projects/{id}/timeline/integrity` — roda `ledger_verify(project_id)` e devolve
  `{entries, valid, first_broken_seq}`.
- A tabela é append-only por gatilho; alterar ou apagar uma entrada exige o papel **dono do banco**, e aí o
  encadeamento denuncia (`test_security_tenancy.test_ledger_tampering_is_detected`).

A v0.15.0 acrescentou 20 tipos de entrada do ciclo do produto ao `CHECK` existente, em vez de criar uma segunda
tabela de histórico. Histórico que pode ser reescrito não é histórico; e dois históricos paralelos são a forma mais
educada de não ter nenhum.

## 4. Retratos comparáveis

`POST /v1/projects/{id}/snapshots` congela o estado do projeto: ficha, captação (somada de `commitments`), marcos,
indicadores com a última medição **validada**, riscos, documentos e partes (derivadas de `applications`).

- `state_sha256` é o hash do estado canônico. **O mesmo estado produz o mesmo hash** — sem isso, "comparar" seria
  comparar ruído (`test_snapshot_of_an_unchanged_project_has_the_same_hash`).
- `ledger_seq` amarra o retrato à posição da trilha naquele instante.
- `GET /v1/projects/{id}/snapshots/compare?a=&b=` devolve `changed` / `added` / `removed`, campo a campo, com o
  caminho do campo (`project.budget_total_cents`, `milestones.0.status`, …).
- Retratos de projetos diferentes não são comparáveis: 404.
- `project_snapshots` é append-only.

`GET /v1/projects/{id}/state` devolve o estado **agora**, na mesma estrutura: a interface compara o presente com
qualquer retrato sem precisar guardar um retrato antes.

## 5. Riscos: declarado ≠ apontado por regra

`project_risks.origin` é `declared` ou `system_identified`, e a origem **nunca muda**. A lista e a interface dizem o
que cada origem significa.

### As 8 regras (`risk-rules@1.0`)

| Código | Categoria | Prob. × Impacto | Severidade |
|---|---|---|---|
| `no_budget` | financial | alta × média | high |
| `no_schedule` | timeline | média × média | medium |
| `no_milestones` | operational | média × média | medium |
| `no_indicators` | operational | média × alta | high |
| `expired_credential` | eligibility | média × alta | high |
| `expiring_document` | documentary | alta × média | high |
| `expired_document` | documentary | alta × alta | critical |
| `compliance_pending` | legal | média × alta | high |

`GET /v1/risk-rules` publica as regras para quem usa a plataforma, com a nota de que **regra aponta indício, não
veredito**.

### Comportamento da varredura

`POST /v1/projects/{id}/risks/scan`:

- cria o risco com `origin = 'system_identified'` quando a condição existe e ainda não há registro daquele código;
- **é idempotente**: rodar duas vezes não duplica (UNIQUE em `(project_id, code)`), e a segunda passada devolve
  `identified: []`;
- quando a condição deixa de valer, marca o risco **daquela origem** como `resolved` com a nota
  *"A condição que gerou este risco deixou de existir."*;
- **não reabre** risco que a organização encerrou como `accepted`, `resolved` ou `dismissed`. A decisão humana
  prevalece sobre a regra (`test_resolved_risk_is_not_reopened_by_the_scan`).

Severidade vem de uma matriz publicada (`SEVERITY_MATRIX`), não de julgamento caso a caso: média × alta = alta,
sempre. Encerrar um risco exige motivo (422 `reason_required`).

## 6. Da ideia ao projeto, sem apagar a ideia

`POST /v1/ideas/{id}/promote` cria o projeto com `projects.origin_idea_id` e marca a ideia como `promoted` com
`promoted_project_id`. A ideia **continua existindo**: um `CHECK` garante que `stage = 'promoted'` e
`promoted_project_id IS NOT NULL` andam sempre juntos, e `promoted_project_id`/`promoted_at` são colunas guardadas
(a organização não as escreve à mão).

Promover duas vezes responde 409 `already_promoted` com o id do projeto. Editar ideia já promovida responde 409
também: edite o projeto.

A promoção entra na trilha como `idea_promoted` **e** `project_created`, com o título original da ideia no
`payload`. Quem abrir o projeto em 2029 vai saber de onde ele veio.

Ideia não consome cota de projeto do plano; a promoção consome (`check_limit(active_projects)`).

## 7. Rotas

| Método | Caminho | O que faz |
|---|---|---|
| GET | `/v1/project-status-graph` | o grafo, os rótulos e as fases |
| GET | `/v1/projects/{id}/lifecycle` | situação, fase, transições possíveis, histórico |
| POST | `/v1/projects/{id}/transitions` | muda a situação (recusa explicada) |
| GET | `/v1/projects/{id}/timeline` | linha de tempo paginada |
| GET | `/v1/projects/{id}/timeline/integrity` | confere o encadeamento |
| GET | `/v1/projects/{id}/snapshots` | retratos guardados |
| POST | `/v1/projects/{id}/snapshots` | guarda um retrato |
| GET | `/v1/projects/{id}/snapshots/compare` | compara dois retratos |
| GET | `/v1/projects/{id}/state` | estado atual na estrutura do retrato |
| GET/POST | `/v1/projects/{id}/risks` | lista / registra risco |
| PUT | `/v1/projects/{id}/risks/{rid}` | atualiza (origem não muda) |
| POST | `/v1/projects/{id}/risks/scan` | aplica as regras |
| GET | `/v1/risk-rules` | as regras aplicadas |
| GET/POST | `/v1/ideas` | lista / anota ideia |
| GET/PUT | `/v1/ideas/{id}` | detalhe / edição |
| POST | `/v1/ideas/{id}/promote` | ideia → projeto |

Todas sob RLS por organização; a matriz de isolamento está em `SECURITY_FINAL_CHECKLIST.md` §3.
