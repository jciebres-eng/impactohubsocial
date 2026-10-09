# PRE_DESIGN_AUDIT — auditoria do código real antes da última rodada de engenharia (v0.15.0)

Regra seguida: **auditar antes de alterar**. Documentação não é prova de implementação — a prova é código + banco +
teste + comportamento observável. Cada linha abaixo foi verificada no repositório, não lida nos documentos.

## 1. O que já está melhor do que a documentação sugere
| Capacidade | Achado real | Classificação |
|---|---|---|
| Motor de match | `engines/match/engine.py` já tem `ENGINE_VERSION`, `weights_version`, **elegibilidade antes do score** (blocker nunca é compensado), `score` **separado de** `confidence` com limiar mínimo, `why_match`/`why_not`/`blockers`/`risks`/`missing_data`/`next_action`/`signals` com peso, valor e contribuição, e aviso de que plano/voucher não alteram o resultado | **IMPLEMENTADO** — mais completo do que o prompt assume |
| Trilha do projeto | `ledger_entries` é **append-only e encadeada por hash** desde a 0002, com `chain_heads` e `ledger_verify()` | **IMPLEMENTADO** |
| Indicadores | `indicator_catalog` + `project_indicators` (baseline/target/method) + `indicator_values` com evidência e **separação de funções no CHECK** (quem valida ≠ quem reportou) | **IMPLEMENTADO** |
| Transições de candidatura | `application_transitions` + máquina validada em `services/workflow.py` | **IMPLEMENTADO** |
| Rotação de chave | `FieldCipher` usa `MultiFernet`: a primeira chave cifra, **todas** decifram | **PARCIAL** — rotação funciona, mas sem metadado de versão, sem recifragem e **sem teste** |
| Credencial no match | `engines/match/professional.py` já distingue `verified` (1.0) de `pending` (0.3) de `none` (0.0) | **PARCIAL** — correto aqui, inconsistente nos outros sinais |
| Limpeza de código | 12 ocorrências de TODO/FIXME/XXX, **todas falso-positivo** ("TODOS", "XXXX" de placeholder). 35 `except Exception`, a maioria com justificativa escrita | **IMPLEMENTADO** |

## 2. Duplicação que EU introduzi na v0.14.0 (falha minha)
`ods_goals` **já existia desde a v0.7.0** com os 17 objetivos e os mesmos nomes em português, e é referenciada por
`indicator_catalog.ods` e `ods_targets.ods`. Na v0.14.0 eu criei `sdg_goals` com os mesmos 17 objetivos, acrescentando
código, nome em inglês e cor oficial — **duas fontes de verdade para a mesma taxonomia**.
`impact_tags` valida contra `sdg_goals`; `indicator_catalog` aponta para `ods_goals`. Isso ia morder mais tarde.
**Correção na 0013:** estender `ods_goals` com `code`, `name_en` e `color_hex`, apontar tudo para ela e **remover
`sdg_goals`**. A 0012 está liberada e **não** será editada.

## 3. Lacunas reais confirmadas por busca no código
| # | Lacuna | Verificação feita |
|---|---|---|
| L1 | **Projeto não tem máquina de estados nem tabela de transições** | `projects.status` tem CHECK com 7 valores, mas as mudanças são `UPDATE` soltos em `services/workflow.py` (linhas 166 e 181). Candidatura tem máquina; projeto **não**. |
| L2 | **Trilha do projeto não cobre o ciclo de vida** | `ledger_entries.entry_type` tem CHECK fechado com 17 tipos, todos de financiamento/execução. Não há `diagnosis_created`, `document_signed`, `opportunity_matched`, `risk_created`… |
| L3 | **Sem snapshot de projeto** | nenhuma tabela; impossível responder "como este projeto estava em 01/01?" |
| L4 | **Sem registro de risco do projeto** | `risk_assessments` é **antifraude por organização** (nome parecido, domínio diferente); `risk_signals` também. Projeto não tem risco com probabilidade/impacto/mitigação. |
| L5 | **Sem entidade Ideia** | não existe; não há `origin_idea_id` em `projects` |
| L6 | **Diagnóstico não tem versão nem histórico** | `diagnoses` é uma linha mutável com `updated_at`; `diagnosis_progress` é por etapa. Um diagnóstico novo **sobrescreve** o anterior. |
| L7 | **Diagnóstico não gera plano de ação** | nenhum `ActionItem` ligado a lacuna |
| L8 | **Sem montagem de documento** | `kb_resources` tem modelo que gera `draft` (texto livre). Não há `DocumentTemplate` com campos, seções, requisitos, evidências, completude nem bloqueio de geração. |
| L9 | **Match sem evidência estruturada** | `Signal` tem `key/weight/value/detail` — **sem** `source`, `verified`, `observed_at`, `freshness`, `confidence` por sinal |
| L10 | **Match sem realimentação** | `match_runs.outcome` é um texto solto; não há quem, quando, por quê |
| L11 | **Match sem decaimento por idade** | nada reduz confiança por dado velho |
| L12 | **Match sem `rules_version`/`taxonomy_version`** | só `engine_version` e `weights_version` |
| L13 | **Assinatura sem abstração de provedor e de nível** | `signatures.method` tem o enum, mas não há `SignatureProvider`, `SignatureLevel`, `Certificate`, `Validation`, `Revocation` nem `Policy`. Não há como configurar provedor nem declarar indisponibilidade. |
| L14 | **Rotação de chave sem metadado, sem recifragem e sem teste** | `MultiFernet` resolve a leitura, mas não há `key_version`, não há job de recifragem, não há auditoria de rotação |
| L15 | **Indicador não separa produto/resultado/impacto** | `indicator_catalog` tem `esg_dimension` e `ods`, não tem `result_kind` |
| L16 | **Sem teste de volume sintético** | nenhum teste cria 10 mil linhas; N+1 e varredura de tabela não foram medidos |
| L17 | **Sem suíte sistemática de fronteira** | há testes de IDOR espalhados; não há a matriz "USER A → recurso B", "ORG A → segredo ORG B" varrendo todas as rotas de escrita |
| L18 | **Sem teste de invariante** | nada garante "mesma entrada + mesma versão = mesmo resultado" nem "plano não influencia match" |

## 4. O que NÃO é lacuna (verificado e descartado)
- RLS existe e é testada por SQL direto, inclusive em contexto de sistema (v0.14.0 provou que nem o contexto de sistema
  reescreve `trust_events`).
- Erros estruturados RFC 7807 com `code`/`title`/`status`/`request_id`/`details` e **sem traceback** — `http.py` já
  sanitiza texto interno do PostgreSQL desde a v0.12.1.
- Paginação com limite máximo de 100 em `page()`; não há paginação ilimitada.
- Idempotência de integração garantida por UNIQUE no banco, com teste de concorrência.
- Nenhum segredo no Git ou no ZIP: `make_release.py` varre por padrões e o teste `test_no_secrets_committed` roda na suíte.
- Demo data já é rotulada: `kb_*` tem `demo=true`, `calls.is_example`, e as telas mostram o selo "Exemplo / rascunho".

## 5. Plano desta rodada (por ordem de dependência)
1. Migração **0013**: consolidar ODS · máquina de estados do projeto + transições · eventos de ciclo de vida na trilha ·
   snapshots · risco de projeto · ideias · versões de diagnóstico + ações · modelos e montagem de documento ·
   realimentação de match · provedores e políticas de assinatura · metadado de chave de cifragem ·
   `result_kind` no indicador.
2. Motores: evidência estruturada e decaimento no match; motor de diagnóstico com versão e comparação; ciclo de vida do
   projeto; montagem de documento com completude e bloqueio.
3. API e frontend funcional (sem design).
4. Testes: fronteira sistemática, invariantes, jornadas ponta a ponta, volume sintético.
5. Documentos exigidos + release v0.15.0.
