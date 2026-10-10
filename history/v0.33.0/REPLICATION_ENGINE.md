# Replicabilidade, adaptação, combinação e marketplace (v0.9.0)

## Replicabilidade (`scoring.replicability`, `replicability@1.0`)
Score 0–100 calculado a partir de fatores **declarados pelo autor** (`solution_replication_profile`: simplicidade 1–5, custo, dependência de infraestrutura e territorial, especialistas, documentação, treinamento, dimensões adaptáveis) + **evidência cadastrada**.
Pesos em `config/solution_weights.json`. **Confiança** = peso dos fatores conhecidos ÷ total; abaixo de 50% o score é `null` com a mensagem "Dados insuficientes para estimar a replicabilidade." (nunca inventa número).
A resposta lista pontos positivos, pontos de atenção, dados ausentes e a restrição "autor não autorizou replicação" quando for o caso. O score **não prevê sucesso**.

## Adaptação (`engines/solutions/adaptation.py`, `adaptation@1.0.0`)
`POST /v1/solutions/{id}/adapt` compara origem × destino (UF/região, orçamento, prazo, infraestrutura, parceiros) e devolve **"ADAPTAÇÃO SUGERIDA — NECESSITA VALIDAÇÃO"** com mudanças, riscos, condições (licença, atribuição) e passos.
Menos de 2 informações comparáveis → **"Dados insuficientes para estimativa confiável."** Autor não autorizou adaptação → `403 adaptation_not_allowed`. É heurística explicável, não estimativa atuarial. Simulações ficam em `solution_adaptations`.

## "Desenvolver esta ideia"
`POST /v1/solutions/{id}/develop` cria um **rascunho** na organização do usuário (`parent_id`, relação `derived_from`, `generated_draft = true`), com `[COMPLETAR]` nos campos e crédito ao original. Gerado por **regras** (sem IA externa).
Para publicar: preencher os trechos, `POST …/confirm-review` (recusa enquanto houver `[COMPLETAR]`); o banco impõe `CHECK (NOT generated_draft OR visibility <> 'published' OR human_reviewed_at IS NOT NULL)`; o flag `generated_draft` não pode ser removido pelo autor.

## Combinar soluções (`combine@1.0.0`)
2–4 soluções → complementaridades, sobreposições (duplicidade), conflitos (escalas de orçamento > 5×, licença restritiva), dependências (ainda não executadas), oportunidades e observações (sem verificação). Status fixo "SUGESTÃO — NECESSITA REVISÃO HUMANA".

## Marketplace de replicação
`GET /v1/replications/marketplace` (executadas/realizadas com replicação autorizada, não ideias). Fluxo: interesse → (info/adaptação) → iniciada → concluída pelo replicador → **confirmada pelo autor**. Só "concluída + confirmada" conta como **REPLICADO** (rótulo e estatística).
Gatilho `solution_replication_guard`: replicador não confirma; autor só confirma; só conclui o que iniciou. Identidade do replicador privada por padrão.
