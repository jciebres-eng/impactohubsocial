# CONTENT_GOVERNANCE — governança editorial (v0.12.0)

| Regra | Onde é garantida |
|---|---|
| Fluxo `draft → review → approved → published → archived` | `kb.transition` + CHECK/trigger; transições fora da tabela → 409 |
| **Quatro olhos**: quem criou não aprova (nem administrador) | CHECK `approved_by ≠ author_id` **no banco** (teste faz UPDATE direto e falha) + 403 `four_eyes` na API |
| Aprovar/publicar/arquivar exige papel `reviewer` (ou administrador) | `_transition` |
| Versões **imutáveis** depois da revisão | trigger; editar versão não-rascunho → 409; alterar = nova versão |
| Conteúdo regulatório exige **fonte e data** | CHECK `regulatory ⇒ source+date`; `valid_until` vencido ⇒ “Revisão necessária” |
| Revisão periódica | `review_every_days` + `last_reviewed_at`; painel “Revisão em atraso”; “Marcar revisado” fica no histórico |
| Histórico de quem fez o quê | `content_history` (de→para, autor, nota, data) |
| Papéis internos | `staff_roles` (`editor`, `reviewer`, `support`); só administrador concede; MFA exigido |
| Rotulagem | origem + selo “Exemplo” (`demo`) em todo item; exemplos nunca indexáveis |
| Feedback | “Ajudou?”, motivo, FAQs com baixa resolução, lacunas de busca → fila editorial |

**Limites:** administradores da plataforma, quando agindo em modo administrativo, têm privilégio amplo no banco; os manipuladores só tocam o domínio da Central, mas isso é **disciplina de código revisada**, não barreira de banco. Os papéis `editor/reviewer/support` hoje são concedidos a contas de organização comuns com MFA (o painel é acessado como administração) — a separação de contas internas é decisão operacional pendente. Não há workflow de comentários por trecho nem agendamento de publicação.

## v0.29.0 — fonte, direitos, citação, retirada e fila editorial (ADR-354 a ADR-357)

| Regra | Onde é garantida |
|---|---|
| Toda fonte tem classe editorial O/A/V/H/D, jurisdição, idioma, vigência, licença e **direitos de uso por operação** (store/index/excerpt/summarize/translate/embed/send_external/train/redistribute ∈ allowed/denied/unknown) | `kb_sources` + `kb_rights_ok()` (CHECK); `unknown` = operação bloqueada até conferência |
| Fonte nasce `unverified`; quem registrou **não** verifica | `kb_source_guard` (trigger) + 403 na API (`POST …/sources/{key}/verify`, papel `reviewer`) |
| Chave, URL, tipo, data de publicação e hash da fonte são imutáveis; retirada é terminal; DELETE proibido | `kb_source_guard`, `forbid_mutation` |
| Citação é append-only, só em versão em **rascunho**; trecho ≤600 caracteres **só** se `rights.excerpt = allowed`, com hash conferido pelo banco | `kb_citations` + `kb_citation_guard` |
| Retirar conteúdo publicado exige motivo (CHECK), é terminal (trigger) e some da busca, do assistente e do sitemap no mesmo instante | `status = 'retracted'` em `kb_article_versions`/`kb_faqs`/`kb_resources`; `kb_unpublish_article`; `kb_visible` |
| Retirar uma FONTE não retira conteúdo automaticamente: abre item `retraction_followup` para cada conteúdo que a cita | `KP.retract_source` + `kb_work_open()` |
| Lacunas viram trabalho: busca sem resultado, assistente sem base, "não ajudou", vencido/atrasado, relato de erro, fonte a revisar — deduplicados enquanto abertos, **só hash + tópicos** (ADR-043) | `kb_work_items` + `kb_work_open()` (SECURITY DEFINER, nunca lança) |
| Concluir ou dispensar um item exige resolução escrita | CHECK em `kb_work_items` + 422 na API |
| Quem lê pode relatar informação incorreta (entra na fila; o conteúdo continua visível até a revisão humana) | `POST /v1/help/report-incorrect` (usuário autenticado) |
| O assistente cita exatamente a fonte usada, exclui DEMO/vencido/terceiros com motivo, pergunta em empate e se abstém sem base | `services/knowledge.assistant()`; testes em `test_v0290_knowledge_base` |
| O conteúdo semeado continua `demo = true`, origem educacional: nenhuma tela o chama de "base oficial" | `kb_seed`; rótulo de origem em cada resultado |

**Papéis:** `editor` registra fonte e cita; `reviewer` verifica fonte, retira fonte/conteúdo; `editor/reviewer/support` operam a fila. Todos com MFA (`staff_roles`).

**Estado das fontes nesta versão:** 11 registradas, **0 conferidas** (`verification = unverified`, revisão marcada para 2026-11-07). A interface mostra "fonte ainda não conferida por outra pessoa" ao lado de cada citação. Conferir é tarefa de pessoa, não de software.
