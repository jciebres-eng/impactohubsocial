# Arquitetura do núcleo do produto — v0.15.0

Este documento descreve o que a IMPACTO **é**, não o que ela promete. Cada afirmação aqui tem código, tabela e teste
por trás; onde algo depende de terceiro não contratado, está escrito que depende.

## 1. A tese

A plataforma não é um cadastro de projetos com um buscador em cima. É **um sistema** em que cinco coisas
compartilham o mesmo vocabulário e a mesma trilha:

```
IDEIA ──► DIAGNÓSTICO ──► PROJETO ──► DOCUMENTO ──► MATCH ──► ACOMPANHAMENTO
   │            │            │            │           │              │
   └────────────┴────────────┴────────────┴───────────┴──────────────┘
                     evidência · versões · trilha encadeada
```

O que faz disso um sistema e não cinco telas:

| Peça | De onde vem o dado | Para onde o dado vai |
|---|---|---|
| Ideia | pessoa | projeto (`projects.origin_idea_id`), e a ideia **continua existindo** |
| Diagnóstico | evidência já registrada na plataforma | lacunas → ações; versões imutáveis |
| Projeto | ideia + diagnóstico | documentos, match, acompanhamento |
| Documento | modelo + campos do projeto + evidência do cofre | assinatura, verificação pública |
| Match | projeto + organização + documentos + histórico | recomendação explicável + retorno humano |
| Acompanhamento | tudo acima | trilha encadeada, retratos comparáveis, riscos |

## 2. O vocabulário comum: evidência

`backend/impacto/core/evidence.py` define o que a plataforma chama de "saber algo". Todo motor usa isto.

```
Evidence(key, source, value, observed_at, expires_at, kind, detail, reference)
```

- **`source`** é uma de nove: `signed_document`, `verified_credential`, `verified_document`, `validated_measurement`,
  `platform_record`, `third_party`, `declared`, `inferred`, `absent`.
- **`verified` não é declarado pelo chamador: deriva da fonte.** `Evidence(..., source=DECLARED, verified=True)`
  volta com `verified=False`. Não é convenção, é `__post_init__`. Isso existe porque a tentação de marcar uma
  declaração como verificada é grande e o custo é perda de confiança do financiador.
- **Frescura** (`freshness`) decai por meia-vida própria de cada tipo de dado, e documento vencido vai a zero com
  mensagem distinta de "está velho".
- **Decaimento reduz CONFIANÇA, nunca PONTUAÇÃO** (`decay_confidence`). Dado velho não torna um projeto pior; torna
  a plataforma menos capaz de afirmar algo sobre ele. Confundir as duas coisas é como punir quem não atualizou o
  cadastro.
- **Faixa de confiança** (`band`) tem quatro valores, e `insufficient_data` é um deles: quando menos de 40% das
  evidências são conhecidas, a resposta não é "confiança baixa", é "não dá para dizer".

Conflito entre fontes resolve pela fonte mais confiável (`SOURCE_TRUST`), e fonte pior **não sobrescreve** fonte
melhor — testado em `test_v0150_invariants.EvidenceInvariants.test_better_source_wins_the_conflict`.

## 3. Como cada motor usa o vocabulário

### Match (`backend/impacto/engines/match/`, `match-engine@1.2.0`)
Pipeline em etapas nomeadas, descrito em `MATCH_ENGINE_FINAL.md`. O que importa aqui: **bloqueio é etapa de
elegibilidade, não peso**. Projeto bloqueado sai com `eligibility: "blocked"`, `score: null` e a lista de bloqueios.
Nenhuma soma de pontos compensa requisito não atendido.

### Diagnóstico (`backend/impacto/core/diagnostic.py`, `diagnostic-engine@1.0.0`)
20 lacunas em 8 dimensões, cada uma amarrada às chaves de evidência que a fecham. Saída separada em FATO
(`evidence`), INFERÊNCIA (`gaps`, `unknown`) e RECOMENDAÇÃO (`recommended_actions`). Detalhe em
`DIAGNOSTIC_ENGINE.md`.

### Ciclo de vida (`backend/impacto/core/lifecycle.py`)
Máquina de situações como **dado** (`project_status_graph`, 58 transições) com gatilho no banco. Detalhe em
`PROJECT_LIFECYCLE.md`.

### Montagem de documento (`backend/impacto/core/assembly.py`, `document-assembly@1.0.0`)
Modelo → completude → bloqueio explicado → geração → revisão com quatro olhos. Detalhe em
`DOCUMENT_ASSEMBLY.md`.

### Chaves (`backend/impacto/core/keys.py`)
Inventário por impressão digital, recifragem auditada, KMS/HSM declarado ausente. Detalhe em `KEY_ROTATION.md`.

## 4. A trilha é uma só

Não existe "histórico do projeto" em uma tabela e "auditoria" em outra inventada para esta versão. A linha de tempo
do projeto **é** `ledger_entries`, que existe desde a migração 0002, é `append-only` por gatilho e encadeada por
hash (`prev_hash` → `entry_hash`), verificável por `ledger_verify(project_id)`.

A v0.15.0 acrescentou 20 tipos de entrada ao `CHECK` (`project_created`, `idea_promoted`, `status_changed`,
`diagnosis_created`, `diagnosis_revised`, `document_generated`, `document_approved`, `risk_created`,
`risk_resolved`, `snapshot_taken`, …) em vez de criar uma segunda tabela. Consequência prática: um fato novo entra
na mesma cadeia que os fatos financeiros, e quebrar o encadeamento para esconder um deles quebraria todos.

**Uma coisa que deliberadamente NÃO entra na trilha do projeto:** o retorno do financiador sobre uma recomendação
de match. Quem avalia é quem olha; a trilha do projeto é lida pela organização dona dele. Registrar ali "a empresa X
descartou seu projeto" seria expor a decisão de um terceiro no histórico de outro. O retorno fica em
`match_feedback` (append-only, UNIQUE por avaliação) e na auditoria de quem agiu.

## 5. Versionamento dos motores

Todo resultado viaja com as versões que o produziram:

| Motor | Versão | Onde fica gravada |
|---|---|---|
| Match | `match-engine@1.2.0` | `match_runs.engine_version` |
| Pesos do match | `weights@1.0` | `match_runs.weights_version` |
| Regras do match | `match-rules@1.1` | `match_runs.rules_version` |
| Taxonomia | `taxonomy@1.0` | `match_runs.taxonomy_version` |
| Diagnóstico | `diagnostic-engine@1.0.0` | `diagnosis_versions.engine_version` |
| Montagem | `document-assembly@1.0.0` | na resposta da avaliação |
| Frescura | `freshness@1.0` | no resumo de evidência |
| Regras de risco | `risk-rules@1.0` | na resposta da varredura |
| Retrato | `snapshot@1.0` | `project_snapshots.state` |

Motivo: quem leu "82 com confiança alta" em outubro precisa poder saber, em março, com qual régua aquilo foi medido.
Resultado antigo nunca muda de significado porque a régua mudou.

## 6. O que o núcleo NÃO faz

- **Não treina nada automaticamente.** `match_feedback` guarda o retorno humano e `calibration_dataset()` prepara a
  base; o ajuste de pesos é decisão humana, publicada como versão nova.
- **Não deduz diagnóstico de ausência de dado.** Sem evidência, a saída é `unknown`.
- **Não assina com provedor indisponível.** `signature_provider_guard()` recusa no banco; não há caminho de código
  que produza "assinatura ICP-Brasil" sem certificado ICP-Brasil real.
- **Não gera documento incompleto.** 409 com a lista do que falta.
- **Não deixa plano, assinatura ou voucher tocarem match nem diagnóstico.** Proibido por teste de arquitetura
  estático (`test_architecture.test_match_and_directory_never_import_billing`) e por teste de comportamento
  (`test_v0150_invariants.test_plan_does_not_influence_the_result`).

## 7. Onde olhar no código

```
backend/impacto/core/           evidence.py · lifecycle.py · diagnostic.py · assembly.py · keys.py
backend/impacto/engines/match/  engine.py (motor) · weights (config/match_weights.json)
backend/impacto/api/            lifecycle_routes.py · diagnostic_routes.py · assembly_routes.py · core_schemas.py
backend/migrations/             0013 (núcleo) · 0014 (modelos da plataforma) · 0015 (índices de FK)
backend/tests/                  test_v0150_core.py · _invariants.py · _security.py · _upgrade.py · _performance.py
                                test_e2e_v0150_journeys.py (8 jornadas) · test_e2e_v0150_web.py (navegador)
web/src/pages/core.tsx          telas funcionais (sem camada de design)
```
