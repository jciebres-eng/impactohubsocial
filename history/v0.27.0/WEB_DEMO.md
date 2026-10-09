# Web Demo = instância operacional real — índice (v0.27.0)

A demonstração não é vitrine: é a mesma aplicação, com autenticação, API, banco, RLS, persistência e auditoria reais, carregada com dados de demonstração identificados como tal.

Este arquivo existe com o nome exigido pelo PROMPT MASTER FINAL (§78) e aponta para onde o conteúdo real vive — não duplica documentação para não envelhecer em dois lugares.

## Onde está

* `docs/DEMO.md` (como subir, contas, o que esperar), `docs/TESTER_GUIDE.md`, `docs/TROUBLESHOOTING.md`
* `infra/compose/demo/compose.yml` (pilha do zero), `backend/impacto/seed_dev.py` (semente de demonstração)
* Jornadas provadas pelo HTTP e pela interface: `backend/tests/demo_journeys.py`, `backend/tests/test_v0250_jornadas.py`, `backend/tests/test_v0250_todas_as_telas.py` (221 telas × personas, com Chromium)
* O que a demo NÃO tem (e diz): provedores externos — `EXTERNAL_INTEGRATIONS.md`

## Estado

Ver `MOTOR_COVERAGE_MATRIX.md` (cor por motor, derivada do código) e `FINAL_EXECUTION_AUDIT.md` (PASS/FAIL com evidência).
