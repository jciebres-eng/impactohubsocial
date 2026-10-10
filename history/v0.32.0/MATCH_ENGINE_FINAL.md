# Motor de match — estado final pré-design (`match-engine@1.2.0`)

Este documento substitui nada: `MATCH_ENGINE.md` descreve o motor desde a v0.7.0. Aqui está o que a v0.15.0 mudou e
o contrato completo do resultado, para que a designer e quem integra saibam exatamente o que existe.

## 1. O motor é central, modular e versionado

Duas direções de avaliação, mesmo pipeline:

- `osc_call` — uma OSC diante de um edital/fundo.
- `funder_project` — um financiador diante de um projeto publicado.

Código: `backend/impacto/engines/match/engine.py` (motor puro, sem banco) +
`backend/impacto/services/matching.py` (montagem das entradas sob RLS e gravação).

**O motor não vê plano, assinatura, voucher nem pagamento.** `config/match_weights.json` lista os
`forbidden_inputs`; `backend/tests/test_architecture.py` falha se qualquer módulo de match importar `billing`,
`entitlements` ou `voucher`; e `test_v0150_invariants.test_plan_does_not_influence_the_result` prova pelo
comportamento: conceder plano pago não muda pontuação, elegibilidade nem features.

## 2. Pipeline

```
1. BUSCA DE CANDIDATOS      SQL, com a elegibilidade dura que cabe em SQL já aplicada
2. ELEGIBILIDADE DURA       bloqueios: não é peso, é porta fechada
3. VALIDAÇÃO DE EVIDÊNCIA   procedência + data de cada fato (core/evidence.py)
4. EXTRAÇÃO DE SINAIS       9 sinais (funder_project) / 7 sinais (osc_call), cada um com peso
5. PONTUAÇÃO                média ponderada APENAS dos sinais conhecidos
6. CONFIANÇA                cobertura dos sinais, ajustada pela frescura das evidências
7. RISCO                    indícios de regra, com severidade
8. EXPLICAÇÃO               why_match · why_not · blockers · risks · missing_data
9. RECOMENDAÇÃO             recommended_state
10. PRÓXIMA AÇÃO            next_action (código + rótulo)
11. RETORNO HUMANO          match_feedback (sem treino automático)
```

### Etapa 1 — busca de candidatos (novo na v0.15.0)

O feed do financiador filtrava em SQL e avaliava **todos** os candidatos, um por um, com ~10 idas ao banco cada.
Medido com volume: 3.126 ms. Agora:

- a elegibilidade dura que cabe em SQL (compliance reprovado, causa excluída pela política, território excluído)
  entra no `WHERE` — esses candidatos seriam descartados de qualquer forma;
- a ordem de recuperação usa afinidade barata (interseção de causas, recência) só para **escolher a janela**;
- a janela de pontuação é **200 candidatos**, e isso é **declarado na resposta** (`scoring_window`,
  `candidates_scored`, `window_note`). Não é limite escondido;
- os candidatos são carregados em lote (`load_projects`: 3 consultas em vez de 3 por candidato, com
  `project_funding_many`), e organização/documentos/histórico/conflito/contexto institucional são memorizados por
  organização dentro da requisição (`FeedCache`).

Resultado medido na mesma máquina e no mesmo volume: **1.615 ms** (ver `PERFORMANCE_REPORT.md`). Quando
`include_blocked=true`, **nada** é pré-filtrado: quem pede para ver os bloqueados vê os bloqueados.

### Etapa 2 — elegibilidade dura

`funder_project`: `PROJECT_NOT_PUBLISHED`, `OSC_COMPLIANCE_BLOCKED`, `CONFLICT_OF_INTEREST`, `EXCLUDED_CAUSE`,
`EXCLUDED_TERRITORY` e os requisitos do edital quando há edital.

Invariante: **bloqueado nunca sai elegível e não recebe pontuação.**

```json
{"eligibility": "blocked", "score": null, "recommended_state": "bloqueada",
 "blockers": [{"code": "EXCLUDED_CAUSE", "message": "...", "how_to_fix": "..."}]}
```

Testado em `test_v0150_invariants.test_hard_blocker_never_comes_out_eligible_and_has_no_score`: o cenário tem
afinidade de causa alta e ainda assim sai bloqueado.

### Etapa 4 e 5 — sinais e pontuação

| Direção | Sinais (peso) |
|---|---|
| `funder_project` | cause 20 · territory 15 · budget 15 · ods_esg 10 · capacity 10 · evidence_history 10 · impact 10 · urgency 5 · preference 5 |
| `osc_call` | cause 25 · territory 15 · budget 15 · readiness 15 · ods 10 · deadline 10 · history 10 |

Pesos em `config/match_weights.json`, versão `weights@1.0`, com `"status": "hipotese_a_calibrar"` — a própria
configuração diz que ainda não foi calibrada com resultado real. Um edital pode sobrepor pesos
(`calls.weights`), e a versão usada fica gravada.

**Sinal sem dado não contribui**: `value = null` ⇒ `contribution = null`, e o peso dele sai do denominador. Não
existe "zero por falta de informação" — isso puniria quem não preencheu, e o teste
`test_signals_carry_weight_value_and_contribution` garante.

### Etapa 6 — confiança é separada da pontuação

```
coverage   = peso dos sinais conhecidos / peso total
confidence = decay_confidence(coverage, evidências)      ← frescura e procedência entram AQUI
score      = média ponderada dos sinais conhecidos        ← frescura NÃO entra aqui
```

Com `confidence < 50` (`thresholds.min_confidence_for_score`), **`score` vira `null`** e a elegibilidade cai para
`needs_review`. Pontuação alta com confiança baixa não é apresentada como recomendação — está escrito no próprio
`disclaimer` do resultado.

Faixas: `high` (≥75) · `medium` (≥50) · `low` (≥25) · `insufficient_data` (abaixo disso **ou** cobertura de
evidência < 40%).

### Etapa 8 — explicação

Todo resultado traz: `why_match` (até 3 sinais fortes), `why_not` (até 3 fracos), `blockers`, `requirements`,
`risks`, `missing_data` (com `owner`: de quem é o dado que falta), `next_action`, `signals` (todos, com peso, valor
e contribuição), `features` (entrada para calibração), `evidence`, `evidence_summary`, `stale_evidence` e
`disclaimer`. Testado em `test_explanation_always_answers_why_and_what_is_missing`.

### Etapa 11 — retorno humano, sem treino automático

`POST /v1/match-runs/{id}/feedback` com um de sete valores: `accepted`, `rejected`, `ignored`, `not_relevant`,
`contacted`, `converted`, `expired`. Um retorno por avaliação (UNIQUE) — o histórico não é reescrito, e tentar de
novo responde 409 `already_recorded`.

A resposta diz, com estas palavras: *"A plataforma NÃO recalibra pesos automaticamente"*.
`GET /v1/admin/match/calibration` entrega a base (sem dado pessoal: identificadores, versões, features, retorno)
para uma calibração futura **feita por pessoas e publicada como versão nova**.

## 3. Determinismo

Mesma entrada + mesmas quatro versões ⇒ mesmo resultado, campo por campo
(`test_same_input_and_versions_give_the_same_result`: compara `score`, `eligibility`, `confidence`, `coverage`,
`features`, `confidence_band` e as quatro versões).

As quatro versões gravadas em cada `match_runs`: `engine_version`, `weights_version`, `rules_version`,
`taxonomy_version`. Mais `evidence` (jsonb) com a procedência que sustentou aquele resultado.

## 4. Os 15 tipos de encontro que a plataforma faz hoje

| # | Quem procura | O que encontra | Onde |
|---|---|---|---|
| 1 | OSC | edital/fundo compatível | `GET /v1/opportunities` |
| 2 | OSC | o que falta para concorrer | `missing_data` no mesmo resultado |
| 3 | Financiador | projeto para apoiar | `GET /v1/feed/projects` |
| 4 | Financiador | projeto dentro do próprio edital | `GET /v1/calls/{id}/match` |
| 5 | OSC | solução replicável | `GET /v1/solutions` (`solution-match@1.0.0`) |
| 6 | OSC | solução adaptável ao seu contexto | `POST /v1/solutions/{id}/adapt` |
| 7 | OSC | combinação de soluções | `POST /v1/solutions/combine` |
| 8 | OSC | profissional habilitado | `GET /v1/directory/professionals` |
| 9 | Profissional | demanda compatível | `GET /v1/professional/opportunities` |
| 10 | OSC | serviço com honorário de referência | `GET /v1/directory/services` |
| 11 | Instituição | elegibilidade institucional | `institutional-eligibility@1.0.0` |
| 12 | Empresa | enquadramento fiscal do aporte | `fiscal-engine@1.0.0` |
| 13 | Apoiador | campanha com cotas abertas | `GET /v1/public/campaigns/{slug}` |
| 14 | OSC | indicador do catálogo para a sua meta | `GET /v1/indicators/catalog` |
| 15 | Qualquer parte | necessidade declarada ↔ oferta | `/v1/institutional/needs` + `need_offers` |

Cada um usa o motor da sua família (match, solução, institucional, fiscal) — todos com versão gravada no resultado.

## 5. O que o motor NÃO faz

- Não decide. `disclaimer` em toda resposta: *"Indicador de apoio à decisão. Decisão final é humana"*.
- Não compensa bloqueio com pontuação.
- Não trata declaração como evidência verificada.
- Não usa atributo sensível: `forbidden_inputs` inclui `sensitive_attributes`; os sinais são causa, território,
  orçamento, ODS/ESG, capacidade documental, histórico na plataforma, impacto declarado, urgência e preferência
  registrada do financiador.
- Não ordena por quem paga mais à plataforma. A ordenação é elegibilidade → pontuação → id, e o feed devolve
  `engine_note` dizendo isso.

## 6. Limite conhecido e declarado

A janela de pontuação de 200 candidatos é um limite real: um financiador sem filtro algum, em uma base com 10.000
projetos publicados, recebe a avaliação explicável dos 200 melhores pela afinidade barata, não dos 10.000. A
resposta diz isso (`window_note`) e sugere estreitar por causa ou território. O caminho para remover o limite está
em `PERFORMANCE_REPORT.md` §5.
