# Motor de selos — FASE 7 da v0.18.0

> Documento lido do código: `backend/migrations/0030_v0180_seals.sql`,
> `backend/impacto/impact/seals.py`, `backend/tests/test_v0180_seals.py`.

## 1. A decisão que torna o selo infalsificável

**O critério é avaliado em SQL, não na aplicação.**

Se a avaliação morasse em Python e o resultado fosse gravado por uma rota, bastaria uma chamada com
o corpo certo para conceder selo sem critério — e nenhuma revisão de código pega isso um ano depois.
Então:

- `seal_evaluate(definition, subject)` consulta os fatos ela mesma e devolve uma linha por critério;
- `app_award_seal()` **chama `seal_evaluate()` antes de inserir** e não concede quando algum critério
  falha;
- a aplicação **não tem INSERT em `seal_awards`** (`REVOKE INSERT, UPDATE, DELETE`).

O teste `test_no_path_can_award_a_seal_without_the_criteria` tenta inserir a concessão por SQL direto
no papel da aplicação e falha. O teste `test_even_the_database_owner_goes_through_the_evaluation`
mostra que nem o dono do banco escapa da avaliação.

## 2. As outras decisões

| # | Decisão | Onde |
|---|---|---|
| 1 | **Definição publicada é imutável**; mudar critério exige versão nova | `seal_definition_frozen()`, `seal_criteria_frozen()` |
| 2 | **A situação é derivada** (ativo, expirado, revogado, superado, de definição aposentada) | `seal_status()` — não há coluna de situação |
| 3 | **Revogação é fato novo**, append-only, com motivo de lista fechada | `seal_revocations` |
| 4 | **A avaliação que NÃO concede também fica registrada** | `seal_evaluations` + `GET /v1/seals/evaluations` |
| 5 | **Nenhum critério é comercial** | varredura AST no módulo **e** no SQL da migração |
| 6 | **Nenhum critério é reputação** | varredura por leitura da tabela, linha a linha |
| 7 | **A plataforma embarca ZERO definições de selo** | critério de selo é decisão de produto; inventá-lo numa migração seria o mesmo erro que inventar regra fiscal |
| 8 | **Toda definição declara o que NÃO atesta** | `what_it_does_not_attest` `NOT NULL`, mínimo de 20 caracteres |
| 9 | **A validade é o menor** entre a da definição e as datas que os critérios impõem | `app_award_seal()`; selo que vale mais que o documento que o sustenta é selo falso |

### 2.1 Um erro de desenho que o primeiro teste pegou

A primeira versão levantava exceção quando o critério não era satisfeito. O teste
`test_the_refused_evaluation_is_recorded_for_whoever_was_refused` veio vazio, e o motivo era bom: a
exceção desfazia a transação e **levava embora o registro da avaliação** — justamente o registro que
responde "por que eu não recebi".

A função passou a devolver `NULL`, o serviço devolve `awarded: false` com os critérios que faltaram,
e a rota levanta o 422 **fora** da transação, depois do COMMIT. A recusa ficou durável, auditável e
legível por quem foi recusado.

## 3. Os doze critérios (conjunto fechado)

**Organização:** `compliance_approved`, `documents_validated` (parâmetro `doc_types`),
`measurements_with_evidence`, `expenses_fully_documented`, `no_open_flagged_claim`,
`substantiated_claims`, `materiality_published`, `framework_mapping_verified`.

**Projeto:** `equity_context_declared`, `validated_causality`, `indicator_baseline_sourced`,
`project_completed`.

Cada código tem implementação em `seal_evaluate()`. **Regra nova exige migração** — e esse é o
ponto: critério de selo não deveria poder nascer de um `INSERT`.

Note o encadeamento com as fases anteriores: um selo pode exigir contexto de equidade com
denominador de fonte declarada (FASE 2), causalidade validada com revisor externo (v0.8.0),
nenhuma alegação marcada em aberto (FASE 5) e mapeamento de referencial verificado (FASE 4). O selo
não inventa confiança: ele soma travas que já existiam.

## 4. Ciclo de vida

```
definição (rascunho) → publicada → [concessão avaliada no banco] → ativa
                           ↓                                          ↓
                      versão nova publicada                    revogada (fato novo)
                           ↓                                          ↓
              anterior aposentada; concessões             expirada na data mínima
              passam a "definição superada"               entre definição e critérios
```

`recheck()` reavalia os selos ativos e **revoga** os que deixaram de satisfazer o critério, com
motivo `criterion_no_longer_met` citando qual critério caiu. Selo que continua aparecendo depois de
o critério cair é pior que não ter selo: atesta o que não é mais verdade.

## 5. Rotas

| Método | Rota | Quem |
|---|---|---|
| GET | `/v1/seals/rules` | usuária autenticada |
| GET | `/v1/seals/definitions` | usuária autenticada (inclui rascunhos) |
| POST | `/v1/admin/seals/definitions` | administração |
| POST | `/v1/admin/seals/definitions/{id}/publish` | administração |
| POST | `/v1/admin/seals/definitions/{id}/retire` | administração |
| POST | `/v1/seals/evaluate` | leitora — a mesma avaliação que a concessão usa |
| POST | `/v1/admin/seals/awards` | administração (o banco confere) |
| GET | `/v1/seals/awards` e `/v1/seals/awards/{id}` | usuária autenticada |
| POST | `/v1/admin/seals/awards/{id}/revoke` | administração |
| GET | `/v1/seals/evaluations` | a organização avaliada |

## 6. O que esta fase NÃO faz

- **Não há selo embarcado.** Zero definições publicadas na migração, de propósito (§2, decisão 7).
- **Não há concessão automática.** Nenhum job concede selo; `recheck()` só **revoga**. Conceder é
  ato declarado, revogar é consequência de fato.
- **Não há verificação pública sem login para os selos novos.** A rota pública de verificação
  (`/v1/public/verify/{code}`, v0.14.0) continua servindo os registros verificáveis antigos; ligar
  os selos desta fase a ela é dívida declarada.
- **Não há arte de selo.** Nenhum emblema, nenhuma imagem: o selo é texto e critério. Arte depende
  de identidade visual, que é a fase de design.
- **Os critérios não têm peso nem nível.** Selo é binário: todos os critérios ou nenhum. Nível
  (bronze/prata/ouro) foi recusado nesta rodada porque nível é ranking com outro nome.
