# Biblioteca de Soluções de Impacto — visão geral (v0.9.0)

Banco inteligente de **ideias, projetos, metodologias, tecnologias sociais e projetos acadêmicos**, integrado às organizações, projetos, ODS/ESG, documentos,
perfil de financiador e administração já existentes. Código: `backend/impacto/{engines/solutions,services/solutions.py,api/solution_routes.py,api/solution_flow_routes.py}`,
migração `0005_v090_solutions.sql`, frontend `web/src/pages/solutions*.tsx`.

## Regra de verdade (aplicada no código e no banco)
| Afirmação | Só vale quando |
|---|---|
| IDEIA / PROPOSTA | `kind = idea` (nunca vira case; não aceita resultados; não pode ser "evidenciada/verificada") |
| EM EXECUÇÃO / REALIZADO | estágio declarado pelo autor (continua **autodeclarado**) |
| COMPROVADO | estágio executado **e** nível `evidenced`/`verified` (só a administração define, com evidências aceitas) |
| VALIDADO | nível `verified` **e** ≥ 1 resultado validado (evidência aceita vinculada) |
| REPLICADO | replicação concluída **e confirmada pelo autor** |
| Interesse ≠ financiamento | etapas avançadas só por pedido aceito + confirmação do autor (funções `SECURITY DEFINER`) |
| Visualização ≠ intenção | `GET` do perfil nunca cria intenção; evento deduplicado (1/usuário/solução/dia) |
| Score ≠ garantia, recomendação ≠ decisão | pontuações explicadas, `null` quando não há dados; avaliações não entram no ranking |
| Conteúdo gerado ≠ fato | "Desenvolver esta ideia" cria **rascunho** com `[COMPLETAR]`; publicar exige confirmação de revisão humana (CHECK no banco) |

Níveis de confiança (rótulos na UI): NÃO VERIFICADO · AUTODECLARADO · EM REVISÃO · DOCUMENTADO · EVIDENCIADO · VERIFICADO.
Evidências nascem `submitted`; resultados nascem `reported`; só a administração aceita/valida (triggers `guard_columns` + CHECKs). Editar conteúdo substantivo de
solução verificada a devolve para `in_review`. Disputa de autoria marca a solução ("Autoria em disputa") até decisão humana.

## Jornadas implementadas (UI + API + testes)
Busca por intenção (texto livre + filtros) → resultados com **"por que apareceu"** → 7 modos de visão (cartões, lista, mapa por UF, por ODS, cases, financiamento, pesquisa) →
perfil com proveniência → **comparar 2–4** → salvar → **"Quero algo como este"** (similares) → **"Adaptar para meu território"** → **"Desenvolver esta ideia"** →
**combinar soluções** → pedir informação/contato/adaptação/replicação/orçamento ao autor → declarar interesse (identidade privada por padrão) → o autor confirma etapas →
replicação (marketplace) → avaliação de quem teve relação real → contestação de autoria. Pontos de partida: "Tenho um problema / dinheiro / ideia / projeto que funciona".

## Papéis
Cadastram: OSC, pessoa física, empresa, governo, profissional. Todas as organizações autenticadas leem soluções **publicadas**; rascunhos só a própria organização (RLS).
Administração (MFA): fila de verificação, revisão de evidências, validação de resultados, remoção, decisão de contestações.

## Dados de demonstração
`seed_dev.py` (somente `development/test`) cria 7 soluções `is_demo = true`, títulos `[DEMO]`, `trust_level = self_declared`; a UI mostra aviso "DADO DE DEMONSTRAÇÃO". O usuário não consegue definir `is_demo` (trigger + schema `extra=forbid`).

## Fora do escopo desta versão (honesto)
Vetores/embeddings semânticos (pgvector indisponível), grafo de rede visual de soluções, mapa com tiles externos, importação em massa de fontes externas (Plataforma Brasil/Lattes/ODS Brasil),
refinamento de intenção por LLM (slot documentado em `AI_SEARCH_ARCHITECTURE.md`, **não implementado**), monetização específica da biblioteca (ver `docs/BUSINESS_MODEL.md`).
