# Inteligência de contrato — índice (v0.27.0)

O contrato é a regra de operação (ADR-336): cláusulas congeladas, versões imutáveis, obrigações derivadas, quatro olhos, matriz de distribuição e instruções de repasse.

Este arquivo existe com o nome exigido pelo PROMPT MASTER FINAL (§78) e aponta para onde o conteúdo real vive — não duplica documentação para não envelhecer em dois lugares.

## Onde está

* `backend/impacto/trust/contract_rules.py` — cláusulas, obrigações, matriz, nova versão, cancelamento
* `backend/impacto/trust/economy.py` — camada econômica, repasses, participação, quitação
* `MONETIZATION.md` §8–9, `docs/ECONOMIC_MODEL.md`, `NON_CUSTODIAL_ARCHITECTURE.md`
* Provas: `backend/tests/test_v0260_contract_rules.py`, `backend/tests/test_v0270_economy.py`

## Estado

Ver `MOTOR_COVERAGE_MATRIX.md` (cor por motor, derivada do código) e `FINAL_EXECUTION_AUDIT.md` (PASS/FAIL com evidência).
