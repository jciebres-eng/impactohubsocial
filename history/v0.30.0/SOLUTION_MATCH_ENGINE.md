# Match financiador ↔ solução (`solution-match@1.0.0`, v0.9.0)

Código: `engines/match/solution.py`; endpoint `POST /v1/solutions/{id}/match`; recomendações `GET /v1/solutions/recommendations`. **Separado** da relevância de busca (que mede aderência à *consulta*):
aqui mede-se aderência à *tese* cadastrada do financiador (`funder_profiles` + `funder_solution_prefs`). Mesma filosofia do núcleo (ADR-026): elegibilidade determinística separada do score, **sem nota** com confiança < 50, explicação completa.

- **Bloqueadores**: solução não publicada; tema excluído pela política; território excluído.
- **Sinais** (`config/match_weights.json → solution_funder`): causas 25 · ODS/ESG 20 · território 15 · faixa de investimento 15 · população 10 · preferências 10 · maturidade 5. `None` quando falta dado.
- **Riscos explícitos**: solução sem verificação independente; necessidade fora da faixa; tolerância baixa a risco com estágio inicial.
- **Independência do plano**: o motor não importa billing/entitlements (teste AST em `test_architecture`) e há teste de igualdade de score entre plano gratuito e premium.
- Perfil de financiador vazio → `409 funder_profile_missing` (não calcula com nada).
- **Recomendações**: (a) por tese do perfil (`basis: tese do financiador`); (b) opcional, **só com opt-in** (`PUT /v1/solutions/personalization`): temas das soluções salvas e conceitos das buscas recentes; desativar apaga o histórico de buscas. Cada item traz "por quê", riscos e a base. Sem tese nem opt-in → lista vazia com instrução.
- Pesos = **hipótese a calibrar**; indicador de apoio, não recomendação de investimento.
