# Acompanhamento no tempo

A pergunta que este documento responde: **o que mudou, quando, por decisão de quem, e com qual evidência?**

Sem isso, "impacto" é adjetivo. Com isso, é uma série que alguém pode conferir.

## 1. Quatro mecanismos, cada um para uma pergunta diferente

| Pergunta | Mecanismo | Onde |
|---|---|---|
| O que aconteceu, em ordem, sem possibilidade de reescrita? | trilha encadeada por hash | `ledger_entries` |
| Quem mudou a situação do projeto, quando e por quê? | transições append-only | `project_transitions` |
| Como o projeto estava num instante, para comparar com outro? | retratos com hash de estado | `project_snapshots` |
| O que a plataforma sabia sobre a organização naquela data? | versões imutáveis de diagnóstico | `diagnosis_versions` |

Nenhum dos quatro aceita UPDATE ou DELETE pela aplicação. São tabelas `append-only` por gatilho
(`forbid_mutation`), e a trilha é encadeada por hash: alterar uma entrada antiga quebra a verificação de todas as
seguintes.

## 2. Trilha: fato novo, nunca correção silenciosa

`ledger_entries` existe desde a migração 0002 e carrega tanto fato financeiro (aporte, desembolso, despesa) quanto
fato de produto (situação alterada, documento gerado, risco registrado). Encadeamento:

```
entry_hash(N) = sha256( canônico(entrada N) || entry_hash(N-1) )
```

`ledger_verify(project_id)` devolve `{entries, valid, first_broken_seq}`, e a API expõe isso em
`GET /v1/projects/{id}/timeline/integrity`. A interface mostra "íntegro" ou "quebrado" — não esconde.

Quando um fato registrado estava errado, **não se apaga**: entra um fato novo que o corrige. Isso vale para
revogação de assinatura, para risco que deixou de valer, para medição substituída. A consequência é que o histórico
cresce e nunca encolhe, e isso é o ponto.

### Os 41 tipos de entrada

Agrupados pelo que contam: ciclo do projeto (`project_created`, `idea_promoted`, `status_changed`,
`project_archived`, `project_completed`), diagnóstico (`diagnosis_created`, `diagnosis_revised`, `action_created`,
`action_completed`), estruturação (`need_published`, `budget_defined`, `milestone_defined`, `goal_created`),
documentos (`document_generated`, `document_approved`, `document_signed`, `professional_signature`), captação
(`interest_registered`, `application_submitted`, `application_approved`, `funding_committed`,
`disbursement_reported`, `disbursement_confirmed`, `refund_completed`, `payment_disputed`), execução
(`expense_recorded`, `evidence_submitted`, `evidence_reviewed`, `result_reported`, `indicator_validated`,
`report_submitted`, `feedback_given`, `procurement_decided`), risco (`risk_created`, `risk_resolved`), parceria
(`partner_added`, `submission_created`, `submission_sent`), oportunidade (`opportunity_matched`) e retrato
(`snapshot_taken`).

## 3. Retratos: comparar exige que o mesmo estado dê o mesmo hash

Um retrato (`project_snapshots`) guarda o estado canônico do projeto em JSON, o `state_sha256` desse estado e o
`ledger_seq` da trilha naquele momento.

O que entra no retrato: ficha do projeto, captação somada de `commitments`, marcos, indicadores **com a última
medição validada**, riscos, documentos e partes (derivadas de `applications`).

Invariante testada: **retrato de um projeto que não mudou tem o mesmo hash**
(`test_snapshot_of_an_unchanged_project_has_the_same_hash`). Sem isso, comparar dois retratos devolveria diferença
onde não houve mudança nenhuma, e a função perderia utilidade no primeiro uso.

A comparação é campo a campo, com o caminho do campo:

```json
{"changed": [{"field": "project.budget_total_cents", "from": "5000000", "to": "7500000"}],
 "added":   [{"field": "milestones.0.title", "to": "Etapa 1"}],
 "removed": []}
```

## 4. Indicadores: produto, resultado e impacto não são a mesma coisa

`indicator_catalog.result_kind` tem três valores — `output`, `outcome`, `impact` — e um comentário na coluna que diz:
**"Meta atingida NÃO é impacto"**.

| Nível | O que é | Exemplo |
|---|---|---|
| `output` (produto) | o que foi entregue | 48 oficinas realizadas |
| `outcome` (resultado) | a mudança no público, curto/médio prazo | 70% das crianças avançaram um nível de leitura |
| `impact` (impacto) | mudança sustentada e atribuível | redução da defasagem escolar no território, com desenho de avaliação |

A plataforma registra e acompanha os três. **Ela não afirma impacto a partir de produto**: o modelo de plano de
monitoramento marca o campo de impacto como opcional e pede que a organização declare quando ainda não há desenho de
avaliação, e o próprio modelo tem um campo obrigatório para **limitações conhecidas da medição** — dizer o que o
dado não prova é parte do relatório.

Medição validada é evidência verificada; medição informada é declaração. A separação de funções está no banco:
`indicator_values` exige que quem valida não seja quem informou.

## 5. Versões de diagnóstico

Detalhadas em `DIAGNOSTIC_ENGINE.md` §5. O que importa para o acompanhamento:

- a versão guarda o retrato completo da análise e o hash dele;
- `changes` é calculado pelo servidor (lacunas fechadas, lacunas novas, forças ganhas/perdidas, delta de completude
  e de confiança);
- publicar sem mudança **não cria versão**;
- a versão 1 continua dizendo exatamente o que valia no dia em que foi congelada — conferido na jornada 3
  (`test_e2e_v0150_journeys.J3`).

## 6. O que a plataforma NÃO rastreia

- **Não há cadastro nominal de beneficiário.** O projeto guarda contagem e descrição agregada do público. Decisão
  de LGPD: a plataforma não precisa do nome da criança para acompanhar o projeto, e dado que não existe não vaza.
  Ver `DATA_RETENTION_MATRIX.md`.
- **Não há rastreamento de comportamento de navegação** além do necessário para operar (sessão, auditoria de ação,
  log de busca de solução sem dado pessoal).
- **Não há inferência de atributo sensível.** Não entra no diagnóstico, não entra no match
  (`forbidden_inputs` inclui `sensitive_attributes`).

## 7. Rotas

| Pergunta | Rota |
|---|---|
| o que aconteceu | `GET /v1/projects/{id}/timeline` |
| a trilha está íntegra? | `GET /v1/projects/{id}/timeline/integrity` |
| quem mudou a situação | `GET /v1/projects/{id}/lifecycle` (campo `history`) |
| retratos guardados | `GET /v1/projects/{id}/snapshots` |
| comparar dois retratos | `GET /v1/projects/{id}/snapshots/compare?a=&b=` |
| estado agora | `GET /v1/projects/{id}/state` |
| versões do diagnóstico | `GET /v1/diagnoses/{id}/versions` |
| o que mudou entre versões | `GET /v1/diagnoses/{id}/versions/compare?a=&b=` |
| riscos e histórico deles | `GET /v1/projects/{id}/risks` |
