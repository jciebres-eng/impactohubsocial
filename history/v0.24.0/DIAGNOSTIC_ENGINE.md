# Motor de diagnóstico — `diagnostic-engine@1.0.0`

O diagnóstico da IMPACTO não é um questionário pontuado. É uma leitura do que a plataforma **sabe** sobre a
organização e o projeto, com a procedência de cada coisa, e uma lista do que falta para que uma afirmação possa ser
feita. Código: `backend/impacto/core/diagnostic.py`.

## 1. A regra que organiza tudo: três tipos de saída, nunca misturados

| Tipo | Campo na resposta | O que é | O que NÃO é |
|---|---|---|---|
| **FATO** | `evidence`, `evidence_summary` | o que está registrado, com fonte e data | não é opinião da plataforma |
| **INFERÊNCIA** | `current_state`, `gaps`, `strengths`, `stale_evidence` | o que uma REGRA aponta a partir dos fatos | não é verdade absoluta |
| **RECOMENDAÇÃO** | `recommended_actions`, `priority` | o que fazer em seguida | não é decisão |
| **DESCONHECIDO** | `unknown`, `missing_evidence` | não há dado para avaliar | **não é "está ruim"** |

A quarta linha é a mais importante e a mais fácil de errar. Uma organização que não informou o tamanho da equipe não
"tem equipe insuficiente": a plataforma não sabe. `unknown` existe para que a interface nunca apresente ausência de
dado como avaliação negativa — e o teste de navegador
(`test_e2e_v0150_web.test_readiness_shows_unknown_separately_from_gaps`) confere que a tela escreve isso.

## 2. As 8 dimensões e o peso de cada uma

| Dimensão | Peso | O que cobre |
|---|---|---|
| `identity` | 10 | CNPJ, natureza jurídica |
| `compliance` | 20 | cadastro institucional, estatuto, ata de eleição |
| `governance` | 10 | tamanho e composição da equipe |
| `problem` | 15 | problema descrito, fonte do dado, causas |
| `territory` | 10 | território, público, alcance estimado |
| `solution` | 15 | metodologia, objetivo |
| `budget` | 10 | orçamento, cronograma, marcos |
| `measurement` | 10 | metas, indicadores, medições validadas |

A completude é a média **ponderada** das lacunas fechadas por dimensão, e a resposta traz a abertura por dimensão
(`current_state.by_dimension`), não só o número final. Um 60% com compliance zerado é um problema diferente de um
60% com medição zerada.

## 3. As 20 lacunas

Cada lacuna aponta para as **chaves de evidência** que a fecham. Fechar uma lacuna não é marcar uma caixa: é a
evidência passar a existir.

| Código | Dimensão | Severidade | Fecha com |
|---|---|---|---|
| `missing_cnpj` | identity | alta | CNPJ registrado |
| `missing_legal_nature` | identity | média | natureza jurídica informada |
| `compliance_not_approved` | compliance | **crítica** | cadastro aprovado pela plataforma |
| `missing_statute` | compliance | alta | `doc.estatuto_social` no cofre |
| `missing_board` | compliance | alta | `doc.ata_eleicao_diretoria` no cofre |
| `no_team_size` | governance | baixa | tamanho da equipe |
| `no_problem` | problem | **crítica** | problema do projeto ou necessidade do diagnóstico |
| `no_evidence_sources` | problem | alta | fonte de dado citada |
| `no_root_causes` | problem | média | análise de causas |
| `no_territory` | territory | alta | território do projeto ou da organização |
| `no_audience` | territory | alta | descrição agregada do público |
| `no_audience_size` | territory | média | estimativa de alcance |
| `no_methodology` | solution | alta | metodologia |
| `no_objective` | solution | **crítica** | objetivo |
| `no_budget` | budget | **crítica** | orçamento |
| `no_schedule` | budget | alta | datas de início e fim |
| `no_milestones` | budget | média | marcos |
| `no_goals` | measurement | **crítica** | metas ou indicadores |
| `no_indicators` | measurement | alta | indicadores do catálogo |
| `no_measurements` | measurement | média | medição validada por terceiro |

Lacuna crítica aberta coloca `priority: "high"` e entra em `current_state.blocking_gaps`.

**Dois defeitos corrigidos nesta versão, encontrados por teste:**
- `missing_statute` e `missing_board` usavam as chaves `doc.estatuto` e `doc.ata_eleicao`, mas o tipo real no cofre é
  `estatuto_social` e `ata_eleicao_diretoria`. A lacuna **nunca fechava**, por mais documento que a organização
  enviasse. Agora fecha.
- Orçamento `0` e público `0` contavam como "informado", porque `0` não é `None`. Zero é ausência de informação
  aqui, e passou a ser tratado como tal.

## 4. Força é o inverso da lacuna — e só conta com evidência verificada

| Chave | O que é |
|---|---|
| `org.compliance` | cadastro institucional aprovado pela plataforma |
| `doc.estatuto_social` | estatuto social no cofre |
| `project.validated_measurements` | medições validadas por **outra** organização |
| `project.signed_documents` | documentos do projeto assinados |

Declaração não gera força. Isso é consequência direta de `Evidence.verified` derivar da fonte
(`CORE_PRODUCT_ARCHITECTURE.md` §2) e está testado em
`test_v0150_core.test_declared_evidence_is_never_marked_verified`.

## 5. Versões imutáveis e "o que mudou"

`POST /v1/diagnoses/{id}/versions` congela uma versão:

- `payload` guarda o retrato **completo** da análise; `payload_sha256` fecha o retrato;
- `changes` é calculado **pelo servidor**: `closed_gaps`, `new_gaps`, `new_strengths`, `lost_strengths`,
  `completeness_delta`, `confidence_delta`. A usuária não declara o que mudou;
- a tabela é `append-only` por gatilho: a versão anterior **nunca** é alterada, nem pelo contexto privilegiado;
- se nada mudou, **não cria versão**: responde `{"created": false, "version": N, "reason": "nada mudou desde a
  versão anterior"}`.

O campo `generated_at` fica **fora** do hash de comparação. Sem isso, "congelar versão" criaria uma versão nova a
cada segundo e "o que mudou" passaria a ser uma pergunta sobre o relógio, não sobre a organização — defeito
encontrado e corrigido nesta versão, com teste que atravessa a virada do segundo de propósito.

`GET /v1/diagnoses/{id}/versions/compare?a=1&b=2` responde o mesmo diff entre quaisquer duas versões.

## 6. Lacuna gera ação, e ação fechada fecha sozinha

Ao congelar uma versão, cada lacuna aberta gera uma `diagnosis_actions` com `origin = 'system_identified'`,
`gap_code`, prioridade e `evidence_hint` (que evidência fecha aquilo). UNIQUE por `(diagnosis_id, gap_code)`:
congelar dez versões não gera dez ações iguais.

Quando a lacuna deixa de existir, a ação **daquela origem** é marcada `done` automaticamente. Ação que a equipe
criou (`origin = 'declared'`) nunca é mexida pela plataforma, e descartar uma ação exige motivo (422
`reason_required`).

## 7. Escopo

- `GET /v1/readiness` — leitura da organização agora, sem gravar nada. Aceita `project_id` para incluir o projeto.
- `GET /v1/diagnoses/{id}/analysis` — prévia do diagnóstico no estado atual, antes de congelar.
- `GET /v1/diagnostic-engine` — as dimensões, as lacunas, as fontes de evidência com o peso de confiança de cada uma
  e os quatro tipos de saída. Aberto a quem usa a plataforma: a régua não é secreta.

## 8. O que o motor NÃO faz

- Não diagnostica pessoa. O público aparece como descrição agregada e contagem; não há cadastro nominal de
  beneficiário na plataforma (decisão de LGPD — ver `DATA_RETENTION_MATRIX.md`).
- Não inventa valor onde não há evidência. Testado: nenhuma chave em `unknown` aparece como conhecida, e nenhuma em
  `missing_evidence` aparece como presente.
- Não muda com plano. `test_plan_does_not_influence_readiness` concede plano pago e compara completude e lacunas.
- Não substitui a decisão. `disclaimer` em toda resposta: *"Diagnóstico de apoio: … A decisão é humana."*
