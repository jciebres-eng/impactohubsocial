# Motor de reputação — índice (v0.27.0)

Reputação explicável, consequência de conduta registrada — nunca de fatura, plano ou voucher (`never_sellable`).

Este arquivo existe com o nome exigido pelo PROMPT MASTER FINAL (§78) e aponta para onde o conteúdo real vive — não duplica documentação para não envelhecer em dois lugares.

## Onde está

* `backend/impacto/impact/reputation.py`; documento de desenho `REPUTATION_ARCHITECTURE.md`
* v0.27.0: reconhecimentos (`recognitions`) nascem só de conclusão e quitação e alimentam a trajetória pública (contagens e datas)
* Provas: `backend/tests/test_v0210_pricing_catalog.py::PaymentNeverBuysTheseTests`, `test_v0270_economy.py` (reconhecimentos)

## Estado

Ver `MOTOR_COVERAGE_MATRIX.md` (cor por motor, derivada do código) e `FINAL_EXECUTION_AUDIT.md` (PASS/FAIL com evidência).
