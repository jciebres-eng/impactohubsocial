# Impact Graph (v0.8.0)

Relações tipadas entre elementos de impacto de um projeto (atividade, resultado, indicador, ODS…), com **força da afirmação** explícita:
`hypothesis` < `association` < `correlation` < `inference` < `observed_evidence` < `validated_causality`.
- Só `validated_causality` afirma causa: exige **evidência** e **revisão por outra organização** (CHECK no banco `link_type <> 'validated_causality' OR (evidence_id … AND reviewed_by … AND reviewed_by_org …)`).
- A interface explica o que cada força significa; correlação ≠ causa (ADR-030).
- Valores de indicadores têm estado **reportado × validado** (validação por outra organização; auto-validação é recusada pelo banco).
Página: `/projetos/:id/grafo`. Limite: não há inferência automática de relações nem estatística causal.
