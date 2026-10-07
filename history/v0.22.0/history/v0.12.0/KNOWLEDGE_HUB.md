# KNOWLEDGE_HUB — Central de Conhecimento (v0.12.0)

Hub único de ajuda, guias, biblioteca, FAQ, academia, eventos, suporte, parcerias, demonstração, teste e boletim. **Auditoria prévia** (para não duplicar) e o que foi reaproveitado estão em §1. Modelo de dados: `KNOWLEDGE_DATA_MODEL.md`. Rotas: `docs/API.md` (grupos *help*, *support*, *trial*, *partnerships*, *notifications*, *content-admin*).

## 1. Auditoria do que já existia (antes de construir)
| Existia | Decisão |
|---|---|
| Notificações in-app (`notifications`, `billing_notices`) | **Reaproveitadas**. Acrescentadas preferências por grupo (`notification_prefs`) e e-mail para cobrança/suporte/eventos (antes: só in-app). |
| `documents` (upload, antivírus, URL assinada) | **Reaproveitado** como arquivo de recursos da biblioteca e anexos de chamados. |
| Materiais (`/materiais`, `org.tsx`) | Mantido (materiais da organização). A Central cobre modelos/guias **da plataforma**; não substitui. |
| Biblioteca de **Soluções** (`solutions`) | Domínio diferente (práticas replicáveis). Não misturado; a Central **não** indexa soluções. |
| Trial/planos/vouchers (v0.11.0) | **Reaproveitados**: aprovar um pedido de teste chama `monetization.start_trial`/`org_trials`. Nenhuma segunda tabela de trial. |
| Suporte, eventos, cursos, FAQ, parcerias, demonstração, boletim | **Não existiam** → criados. |
| Busca | Motor de busca de soluções (`ai-search`) é específico; para a Central foi criado `help-search@1.0.0` (FTS `pt_unaccent` + trigrama + vocabulário de assuntos). |

## 2. O que a Central entrega
- **Busca híbrida** (`GET /v1/help/search`): texto completo + similaridade de título + assuntos (`config/help_synonyms.json`) + tela de origem + público. Cada resultado traz **“por que apareceu”**. Sem embeddings. **Pesos são hipótese** (`WEIGHTS`, `MIN_SCORE` em `engines/knowledge/search.py`).
- **Ajuda contextual** (`GET /v1/help/context?key=project.budget` + widget `ContextHelp`): artigos, FAQs e modelos ligados à tela.
- **Guias** com passo a passo, checklist (progresso por pessoa), erros comuns, documentos necessários, ação (“Fazer agora”), relacionados, referências, utilidade (“Ajudou?”) e dado estruturado schema.org (só conteúdo público e não-exemplo).
- **Biblioteca** (modelos preenchíveis que viram **rascunho** da organização, checklists, documentos, vídeos, relatórios, boletins), versões e download por URL temporária (5 min).
- **FAQ** inteligente com votos, motivos e fila de “FAQs que pouco ajudam”.
- **Assistente** (`POST /v1/help/assistant`): **extrativo e ancorado** — só devolve trechos de conteúdo publicado, cita fontes, marca “revisão pendente” e **recusa** (“Não encontrei informação suficiente na base oficial.”) com ação de abrir chamado. `ai_used:false`: **nenhum modelo generativo**.
- **Comece aqui** (`/ajuda/comece-aqui`): jornada por tipo de organização (OSC 15 etapas, empresa 7, apoiador 4, profissional 5, governo 4; `config/onboarding_paths.json`), com % **medido por dados reais** (consultas SQL por etapa), não por autodeclaração. Jornadas são hipótese editorial.
- **Pendências** (“O que falta para eu avançar?”) e **Minhas atividades**, derivadas de dados reais (compliance, documentos vencendo, trial, chamados aguardando resposta, eventos, cursos).
- Academia, suporte, eventos, parcerias, demonstração, teste e boletim: ver os documentos dedicados.

## 3. Navegação e frontend
`/ajuda` (hub), `/ajuda/busca`, `/ajuda/:slug`, `/ajuda/biblioteca[/:slug]`, `/ajuda/faq[/:id]`, `/ajuda/academia[/:slug]`, `/ajuda/academia/aula/:id`, `/ajuda/certificado/:code`, `/ajuda/eventos[/:slug]`, `/ajuda/suporte[/novo|/:id]`, `/ajuda/parcerias`, `/ajuda/demonstracao`, `/ajuda/teste`, `/ajuda/boletim[/confirmar|/cancelar]`, `/ajuda/comece-aqui|pendencias|atividades|preferencias`. Administração em `/admin/central/*`. Páginas públicas renderizam **sem login** (moldura própria); as privadas redirecionam para `/entrar?proximo=…`. Conteúdo privado/exemplo recebe `noindex`; só conteúdo público e não-exemplo entra em `GET /v1/help/sitemap` e recebe JSON-LD.

## 4. Rótulos de honestidade
Todo item exibe a **origem** (informação oficial, comunidade, parceiro, educativo) e, quando `demo=true`, o selo **“Exemplo / rascunho — não é documento oficial”**. Conteúdo regulatório exige **fonte + data** (CHECK no banco) e vira “Revisão necessária” ao vencer.

## 4.1 Limites declarados
- **Não há conteúdo real publicado**: o seed (`kb_seed.py`) tem 14 guias, 8 FAQs, 4 recursos, 1 curso e 1 evento **todos `demo=true`**, sem regra fiscal/jurídica/preço. Conteúdo oficial depende de redação e revisão humanas.
- Sem embeddings/IA generativa; busca por vocabulário (sinônimos curados) — recall limitado a termos cobertos.
- Editor de curso/recurso/FAQ/evento no CMS é **JSON validado pelo servidor** (editor visual completo só para guias).
- Curso publicado não é editado no lugar (nova versão = novo curso/versão; ver `TRAINING_ACADEMY.md`).
- Acessibilidade: verificação própria (rótulos, foco, `aria-*`), **sem axe/leitor de tela**.
