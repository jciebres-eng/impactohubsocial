# Arquitetura de busca e papel da IA (v0.9.0)

**Princípio:** a busca funciona completa sem IA. IA é camada opcional, nunca fonte de fato, nunca decide (ADR-014).

```
consulta → intent-parser (regras + tesauro) ─┐
filtros estruturados (SQL, GIN) ─────────────┤→ candidatos (≤200: FTS pt_unaccent ∪ população/instituição ∪ trigramas)
                                              └→ pontuação (Python, explicável) → ordenação → explicação → [IA opcional: texto explicativo]
```
Etapas ordenadas do mais barato ao mais caro; a IA nunca entra no caminho crítico.

## O que existe
- **Camada semântica por tesauro** (`config/solution_concepts.json`): sinônimos, plural/singular por radicais, siglas (CAPS, PcD), expansão de 1 nível, mapeamento conceito → temas/ODS/ESG. É curada à mão: precisa de manutenção e revisão por especialistas de domínio.
- **Gateway de IA existente** (`engines/ai/gateway.py`: provider-agnostic, redação de PII, cota, log em `ai_usage`) — não é chamado pela busca nesta versão.
- **Copiloto** (`POST /v1/solutions/assistant`): **ancorado nos dados** — roda a busca e responde somente com soluções cadastradas (título, rótulo, verificação, por quê); `ai_used: false`; sem texto gerado por modelo.
- **Governança**: logs de busca guardam hash + intenção estruturada (sem texto bruto); personalização exige opt-in e é apagável.

## O que NÃO existe (RED/YELLOW, não fingir)
- **Embeddings/busca vetorial**: `pgvector` indisponível no ambiente; o desenho prevê uma coluna `embedding` e um passo "recuperação vetorial" no pipeline após o FTS, sem mudar a API. Não implementado.
- **Refinamento de intenção por LLM** (slot): o gateway pode receber a consulta (já redigida) e **só** devolver IDs de conceitos válidos do tesauro (validados; qualquer outra saída descartada), registrando uso. Não implementado nesta versão — a interpretação determinística já cobre os casos testados.
- **IA explicativa** e **rascunho por IA**: o rascunho de "Desenvolver ideia" é por regras; geração por modelo exigirá provedor configurado e continuará marcada "gerada por IA — revisão humana".

## Quando considerar vetores
Quando houver volume de consultas reais com `unmatched_terms` frequentes (métrica já gravada) e pgvector/serviço equivalente disponível. Avaliar com conjunto de relevância rotulado por humanos antes de trocar pesos.

## v0.29.0 — a busca da Central é medida (ADR-358)

- **Motor:** `help-search@1.0.0` — FTS `pt_unaccent` + trigram no título + tesauro (`config/help_synonyms.json`, agora `help-thesaurus@1.1`) + contexto de tela + perfil. Sem embeddings, sem reranking por modelo: a busca é determinística.
- **Conjunto de avaliação:** `config/search_eval.json` — 35 consultas pt-BR (exato, natural, sinônimo, erro de digitação, sem acento, sigla, ambígua, sem resposta) com itens relevantes/aceitáveis rotulados à mão.
- **Métricas:** `engines/knowledge/evaluation.py` — P@5, R@5, MRR, nDCG@5 (ganho 2/1), hit@1, taxa de zero resultado, abstenção correta, latência p50/p95.
- **Baseline (OSC autenticada, semente publicada para a medição):** hit@1 0,84 · MRR 0,91 · R@5 0,97 · nDCG@5 0,91 · zero 0 % · abstenção 3/3 · p95 ≈ 17 ms — gravado como **piso** em `floors`: uma mudança de ranking abaixo dele reprova (`test_v0290_search_eval`).
- **Única mudança feita, porque mediu ganho:** tesauro 1.1 (custo/mensalidade/gratuito; certidão/documento vencido; esqueci/recuperar senha) → hit@1 0,875 · MRR 0,94 · nDCG 0,93 · R@5 0,98.
- **Anônimo medido à parte** para provar que conteúdo `authenticated`/por público **não vaza** (R@5 menor, restrito ausente de todos os rankings).
- **Evidência:** `docs/evidence/search_eval_v0290.json` (motor, pesos, corpus, métricas, por consulta, `what_this_is_not`).
- **O que isto NÃO é:** desempenho em base real (corpus = semente demo/educacional), julgamento por mais de uma pessoa, medida de modelo. **Quando considerar vetores:** só com conjunto maior, rotulado por mais de uma pessoa, e ganho medido contra este piso.

**Assistente (ADR-357):** extrativo (`ai_used = false`), só `published` + origem `official`/`educational` + não demo + não vencido; uma fonte usada com citações; `excluded` com motivo; `ambiguous` em empate (gap < 0,04); abstenção explícita e item `assistant_gap`.
