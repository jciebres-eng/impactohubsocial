# Impacto Trust — Consolidação do núcleo de impacto

**Versão auditada:** v0.18.0 · **Data:** 2026-10-06

## Executive summary

A base recebida já possuía motores separados de match, diagnóstico, documentos, equidade e trilha longitudinal. O risco principal era de **integração semântica**: a equidade não alimentava o match; o diagnóstico não apresentava as oito prontidões solicitadas; documentos não expunham proveniência por campo; e o endpoint de impacto mostrava medições, mas não uma série temporal explícita.

Foram implementados quatro reforços pequenos e reversíveis, sem introduzir IA no cálculo determinístico e sem alterar regras de pagamento, ranking comercial ou atributos sensíveis.

## Alterações realizadas

| Eixo | Alteração | Evidência |
|---|---|---|
| Match | Novo `engines/match/context.py` calcula sinal contextual com necessidade, barreiras, infraestrutura, adicionalidade, sustentabilidade, evidência e denominadores; ausência retorna `UNKNOWN`. | `backend/impacto/engines/match/context.py`, `engine.py` |
| Match | `services/matching.py` carrega contexto agregado de `equity_contexts`, `project_barriers` e `equity_assessments`, sem PII. | `backend/impacto/services/matching.py` |
| Diagnóstico | Saída passa a conter `project_readiness`, `organization_readiness`, `funding_readiness`, `evidence_readiness`, `compliance_readiness`, `data_readiness`, `governance_readiness` e `impact_readiness`. | `backend/impacto/core/diagnostic.py` |
| Documentos | Cada campo da montagem retorna `provenance`: origem, presença, derivação e evidência vinculada. | `backend/impacto/core/assembly.py` |
| Longitudinal | Cada indicador retorna `longitudinal` com períodos, deltas reportado/validado, série e ressalva de não causalidade. | `backend/impacto/impact/longitudinal.py`, `api/impact_routes.py` |
| QA | Teste independente de banco cobre UNKNOWN, comparação contextual, contrato do match e série temporal. | `backend/tests/test_impact_core_hardening.py` |

## Regra de equidade implementada

O número de beneficiários **não é mais usado como proxy de impacto contextual**. Quando o projeto tem beneficiários, mas não tem contexto suficiente, o motor usa apenas uma **referência neutra** para manter compatibilidade de ordenação; o sinal é explicitamente rotulado como “alcance não é impacto” e a lacuna de contexto permanece em `missing_data`.

Com contexto informado, o sinal é calculado somente pelos campos agregados disponíveis e retorna `coverage`, `known`, `unknown` e explicação. Não há inferência de atributo sensível individual.

## Testes executados

- `python3 -m unittest tests.test_unit tests.test_impact_core_hardening -v` — **36 testes, OK**.
- `python3 -m unittest tests.test_architecture -v` — **20 testes, OK**.
- `python3 -m compileall -q impacto` — **OK**.
- `ruff check` nos arquivos alterados — **OK**.
- Guard AST de dependência do match contra billing/entitlements — **OK**.

## Limitação reproduzida

Os testes que exigem PostgreSQL real não puderam ser executados neste sandbox porque o cliente `psql`/servidor PostgreSQL não está disponível. A biblioteca `libpq5` foi instalada para liberar os testes de arquitetura, mas isso não substitui um banco migrado. Portanto, o estado correto é **GO WITH CONDITIONS**, não GO.

## Critérios de aceite para liberar Designer/publicação

1. Subir PostgreSQL 16 conforme `ENVIRONMENT_SETUP.md` e executar todas as migrations.
2. Rodar `make test` completo, incluindo `test_v0180_equity`, jornadas E2E e testes de documentos.
3. Verificar via API que um projeto com 5.000 beneficiários em território de alta infraestrutura não é automaticamente classificado como maior impacto que um projeto de 50 beneficiários com maiores barreiras.
4. Conferir no payload do match: `score`, `confidence`, `signals.impact`, `missing_data` e `contextual coverage`.
5. Conferir no diagnóstico a presença das oito chaves de `readiness`.
6. Conferir que montagem gerada contém proveniência por campo e que afirmações sem evidência continuam bloqueadas.
7. Conferir que o endpoint de impacto diferencia `reported` de `validated` e exibe `validated_delta` sem declarar causalidade.
8. Fazer smoke test de auth/RLS, upload, documentos, webhooks, backup/restore, observabilidade e rollback antes da publicação.

## Decisão

**GO WITH CONDITIONS.** O núcleo reforçado está compilável, testado em unidade e aprovado na auditoria arquitetural. A liberação para Designer pode prosseguir para validação funcional controlada; a publicação web continua condicionada à execução dos testes PostgreSQL/E2E e dos gates operacionais de produção.
