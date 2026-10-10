# Busca da Biblioteca de Soluções (v0.9.0)

`POST /v1/solutions/search` — híbrida, **sem depender de IA**. Código: `services/solutions.py::search`, `engines/solutions/{intent,concepts,scoring}.py`.

## Pipeline (do filtro barato ao cálculo caro)
1. **Interpretação de intenção** (`intent-parser@1.0.0`, determinística): conceitos do tesauro (`config/solution_concepts.json`: 44 conceitos — temas, populações, instituições, modalidades),
   correção ortográfica por similaridade (`difflib`, só palavras ≥ 5 letras), ODS/ESG implícitos, território (UF, capital, região; guarda "para" ≠ Pará), orçamento
   ("tenho R$ 250 mil", "até 100 mil", faixas), prazo, tipo de intenção e preferências ("que já funcionou", "pronto para financiamento", "ideia", "metodologia", "acadêmico").
2. **Filtros estruturados** no SQL (tipo, estágio, temas, populações, ODS, ESG, UF, faixa de orçamento, buscando financiamento, replicável, verificação mínima) — índices GIN.
3. **Recuperação de candidatos** (teto fixo **200**): `to_tsquery('pt_unaccent', …)` (config de texto PT sem acentos + radicais), população/instituição por array, e `word_similarity` de título (pg_trgm, tolera erro de digitação).
4. **Pontuação explicável** em Python (`scoring.relevance`): sinais aplicáveis e com dado → renormaliza → 0–100 + **confiança**. Regras de negócio com bônus/penalidade explícitos.
5. **Ordenação, paginação** (offset sobre o conjunto de candidatos) e **explicação** ("por que apareceu": só o que foi calculado).
6. Registro em `solution_search_log`: **hash** da consulta + intenção estruturada, nunca o texto; excluído ao desativar a personalização.

## Relevância (pesos em `config/solution_weights.json`, status "HIPÓTESE inicial")
texto 30 (FTS .5 · conceitos .35 · título .15) · ODS/ESG 20 · população 15 · território 10 · orçamento 10 · maturidade 5 · replicabilidade 5 · evidência 5.
Só entram sinais **pedidos na busca** (ODS, população, território, orçamento) e **com dado**; ausência não penaliza. Bônus +5 (busca por ideia/metodologia/acadêmico/pronto para financiar/comprovada com evidência);
penalidade −10 quando se pede "o que já funcionou" e a solução é só autodeclarada ou ainda não executada. **Avaliações, visualizações, salvamentos e plano contratado não entram.**

### Análise dos pesos (a pedido do prompt)
`scripts/weights_sensitivity.py` → `docs/evidence/weights_sensitivity_v0.9.0.json`: 16 perturbações (cada peso ×0,5 e ×1,5) + pesos achatados, em 7 consultas de qualidade:
**o resultado esperado permaneceu em 1º lugar em todas**. Leitura honesta: no corpus sintético (8 soluções) o sinal textual/conceitual domina, então os pesos **não foram discriminados** —
isto prova robustez do desenho, **não** otimalidade dos números. Calibrar exige dados reais de uso (cliques, pedidos, conclusões). Os pesos seguem como hipótese e estão em arquivo (sem recompilar).

## Qualidade verificada (testes `test_search_quality`)
"artes caps", "arte saúde mental", "arte e centro de atenção psicossocial", "projeto idosos", "educação rural", "mulheres violência", "PcD tecnologia", "sude mental arte" (typo),
"idoso" (singular) → resultado esperado entre os 3 primeiros; CAPS ≈ Centro de Atenção Psicossocial ≈ saúde mental (expansão de 1 nível com peso 0,5); filtro por UF; consulta sem resultado → sugestões acionáveis;
rascunhos nunca aparecem.

## Limites conhecidos
- Sem embeddings: "semântica" = tesauro curado + radicais + trigramas. Sinônimos fora do tesauro não são entendidos (aparecem em `unmatched_terms`). `cap` (3 letras) não recebe correção ortográfica.
- Paginação é sobre ≤ 200 candidatos (`capped: true` quando atingido) — refinar filtros.
- Desempenho medido: ver `docs/evidence/search_perf_v0.9.0.json` (5.000 soluções sintéticas: p50 ≈ 181 ms, p95 ≈ 474 ms ponta a ponta, 1 processo, PostgreSQL local). Não é projeção de produção.
