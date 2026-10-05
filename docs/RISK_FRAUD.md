# Risco e antifraude (v0.8.0) — sinais para revisão humana

Código: `backend/impacto/services/risk.py`; job `risk_scan`; rotas de risco/admin em `docs/API.md` (tag risk). **Nunca acusa**: gera *sinais* com linguagem neutra; **bloqueio só por decisão humana** com justificativa (CHECK no banco).

## Detectores (8, em `DETECTORS`)
`duplicate_document_hash` (mesmo SHA-256 usado por organizações diferentes) · `evidence_reuse` · `duplicate_expense` · `expense_over_budget_item` · `price_outlier` (cotação distante da mediana) · `related_accounts` · `supplier_is_party` (fornecedor é parte relacionada) · `quotes_below_policy` (menos cotações que a política exige).
Cada sinal tem tipo, severidade (low/medium/high), chave de deduplicação, resumo e detalhes; estados revisáveis (aberto → revisado/descartado/confirmado).

## Nível agregado (`level_for`)
alta severidade aberta → "revisão manual"; ≥ 3 médias → "alto"; alguma média/baixa → "médio"; nenhuma → "baixo". É **indicador de fila de revisão**, não pontuação de culpa.

## Limites honestos
Regras simples e explicáveis, sem aprendizado de máquina; falsos positivos e falsos negativos existem (hash idêntico pode ser documento legítimo compartilhado). Não cruza bases externas. Calibração depende de dados reais.
