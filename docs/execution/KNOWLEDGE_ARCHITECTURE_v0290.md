# Arquitetura da camada de conhecimento — v0.29.0

```
fonte (kb_sources: O/A/V/H/D · jurisdição · vigência · licença · direitos por operação · verificação por outra pessoa)
   │ cita (kb_citations: localizador · trecho só com direito · hash · só em RASCUNHO)
   ▼
conteúdo (kb_articles/versions · kb_faqs · kb_resources: draft → review → approved → published → archived | retracted)
   │ publicado + kb_visible(visibilidade, público)         │ retirado: search_doc = NULL, some de tudo
   ▼                                                        ▼
busca help-search@1.0.0 (FTS pt_unaccent + trigram + tesauro 1.1 + ctx + perfil) ──▶ sem resultado → kb_work_items(search_gap)
   │
   ▼
assistente extrativo (só published · official/educational · não demo · não vencido) ──▶ sem base → kb_work_items(assistant_gap)
   │  resposta = UMA fonte usada + citações + excluídos com motivo | ambíguo → opções | abstenção
   ▼
interface: resultado com origem · artigo com citações e avisos · "não ajudou" → kb_work_items(unhelpful) · relato de erro
   │
   └── ajuda contextual (config/concepts.json → concepts.ts → Tooltip/InfoPopover/GlossaryTerm/ContextualHelp → /ajuda/glossario)
       fontes 'official' dos conceitos apontam para chaves de kb_sources
```

## Camadas e onde cada regra vive

| Camada | Regra | Onde |
|---|---|---|
| Banco | quatro olhos, imutabilidade, direitos, hash de trecho, retirada terminal, dedupe da fila, RLS | `0009` (existente) + `0069` |
| Serviço | listar/registrar/verificar/retirar fonte, citar, retirar conteúdo, abrir/resolver trabalho, varredura | `services/kb_provenance.py` |
| Serviço | busca, feedback, artigo com citações, assistente | `services/knowledge.py` |
| Motor | métricas da busca (puras, sem I/O) | `engines/knowledge/evaluation.py` |
| API | 13 rotas (3 públicas, 1 de usuário, 9 editoriais) | `api/kb_provenance_routes.py`, `api/platform_routes.py` (conceitos) |
| Configuração | tesauro, conjunto de avaliação, catálogo de conceitos | `config/help_synonyms.json`, `config/search_eval.json`, `config/concepts.json` |
| Front | componentes de ajuda, página de glossário, termos aplicados | `web/src/ui/help.tsx`, `web/src/pages/help.tsx`, 11 páginas |
| Base editorial | 58 controles + 12 pesquisas + reconciliação contra o código | `knowledge-base/` |

## Hierarquia de prevalência (da base v0.26.0, preservada)

O (obrigação) > A (orientação) > V (padrão voluntário) > H (hipótese de produto) > D (decisão pendente).
H nunca prova conformidade; D bloqueia o gate. A classe é **editorial**: a interface a mostra ao lado de cada
citação e a plataforma nunca a apresenta como parecer.

## O que NÃO existe (e por quê)

| Ausência | Motivo |
|---|---|
| Embeddings / banco vetorial / reranking por modelo | nenhum ganho medido contra o piso; conjunto pequeno (ADR-358) |
| Retirada automática de conteúdo quando a fonte é retirada | decisão editorial — vira item de trabalho |
| "Base oficial" como rótulo | a semente é DEMO/educacional; conteúdo oficial exige fonte conferida (0 de 11) |
| Tradução en/es dos conceitos | trabalho editorial |
| Conceitos em telas administrativas internas | fora do escopo (telas de operação, não de usuário) |
