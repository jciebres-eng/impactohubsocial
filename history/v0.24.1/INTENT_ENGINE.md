# Intenção — interpretação de busca e intenção de financiamento (v0.9.0)

## 1. Interpretação da consulta (`engines/solutions/intent.py`)
Determinística, versionada (`intent-parser@1.0.0`), sem rede. Saída: `concepts` (com `how: exact|fuzzy`, `matched`, `corrected_to`), `concept_weights` (diretos 1,0; expansões 0,5),
`population`, `institutions`, `themes` (taxonomia), `ods`, `esg`, `territory{ufs,regions,city}`, `budget{kind:have|range|max|min, min_cents, max_cents}`, `months`, `desired{proven,ready_to_fund,idea,replicable,adapt,running,methodology,academic}`,
`intent` (`find_solution|explore_idea|invest|replicate|adapt|solve_problem`), `text_terms`, `unmatched_terms`. A UI mostra "Entendemos: …" e o usuário pode corrigir via filtros.
Endpoint de inspeção: `POST /v1/solutions/intent/parse`. Exemplos testados: `mulheres violência → violencia_mulheres`; `sude mental → saude_mental (fuzzy)`; `Tenho R$ 250 mil … Mato Grosso → budget have 25.000.000 centavos, MT`; `projeto no Pará → PA`; `quero ajudar para o futuro → sem UF`.

## 2. Intenção de financiamento (`solution_intents`, 10 etapas)
`discovery → interested → reviewing → requested_info → requested_adaptation → negotiating → commitment_started → funded → implementing → completed`.
- O financiador só define `discovery/interested/reviewing` (e a visibilidade da própria identidade, **privada por padrão**).
- `requested_info/requested_adaptation` avançam **somente** pelo envio de um pedido real (`solution_advance_intent`, `SECURITY DEFINER`, valida a existência do pedido).
- `negotiating … completed` só pelo **autor**, após **aceitar um pedido** do financiador (`solution_author_set_intent`); a etapa só avança; define `confirmed_by_author`.
- Gatilho `solution_intent_guard` bloqueia forja por SQL direto (testado). `solution_intent_events` é append-only.
- **Privacidade**: o autor vê identidades apenas se o financiador tornou pública **ou** fez pedido direto (RLS `sintent_read`); caso contrário só contagens de organizações distintas (`solution_public_stats`).
- **Anti-manipulação**: visualização nunca cria intenção; eventos deduplicados por (solução, usuário, tipo, dia); limite de 10 pedidos/dia/organização, 1 pedido aberto por tipo; avaliações só após pedido aceito ou replicação confirmada e fora do ranking.

## 3. Funil
`GET /v1/solutions/{id}/funnel` (só o autor): organizações distintas por evento (`solution_viewed … solution_replicated`). `GET /v1/solutions/{id}/intents`: estatísticas + identidades permitidas.
