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
