# USER_GUIDES — guias de usuário na Central (v0.12.0)

## Como o conteúdo é organizado
Guias (`kb_articles` + versões imutáveis em `kb_article_versions`) têm: tipo (`start`, `how_it_works`, `guide`, `article`, `policy`, `glossary`, `procedure`), categoria, público (OSC, empresa, apoiador, profissional, governo), visibilidade (`public` / `authenticated` / `audience`), origem (informação oficial, material educacional, conteúdo de terceiros), telas de ajuda contextual (`ctx_keys`, ex.: `project.budget`), passos, checklist, erros comuns, documentos necessários, ação (“Fazer agora” → rota interna) e relacionados.

## Guias de exemplo incluídos (todos `demo=true`)
`backend/impacto/services/kb_seed.py` traz **14 guias, 8 FAQs, 4 recursos, 1 curso e 1 trilha** para demonstrar o funcionamento: começar na plataforma, perfil da organização, documentos e validade, criar projeto, orçamento, enviar candidatura, prestação de contas, pagamentos e evidências, plano e trial, suporte, etc. **São exemplos operacionais da plataforma, não orientação oficial**: não contêm regra fiscal, jurídica, valores de plano ou promessa de benefício, e aparecem com o selo “Exemplo / rascunho — não é documento oficial”. Para carregar no ambiente: `python -m impacto.cli seed-demo` (publica) ou `python -m impacto.cli kb-import --author-email …` (**só rascunhos**, a publicação passa pelo fluxo de quatro olhos).

## Como uma pessoa usa
1. **Encontrar**: busca em `/ajuda` ou botão “Preciso de ajuda” (`ContextHelp`), hoje ligado a 3 telas (Documentos `documents.upload`, Novo projeto `project.new`, Verificação do cadastro `compliance.status`); as demais chaves existem no conteúdo e na API, mas a tela ainda não exibe o botão.
2. **Seguir**: passos + checklist (salvo por pessoa; sem login, o checklist funciona mas não persiste).
3. **Agir**: botão de ação do guia leva à tela correspondente.
4. **Avaliar**: “Ajudou?” (com motivo) alimenta a fila de revisão. Se não ajudou por “preciso falar com alguém”, a interface oferece abrir chamado.

## Como a equipe escreve
Editor cria o guia em `/admin/central/artigos/novo` (rascunho). Enviar para revisão → **outra pessoa** com papel de revisor aprova e publica. Alterar texto publicado cria **nova versão**; a anterior fica imutável (trigger). Detalhes: `CONTENT_GOVERNANCE.md`.

## Limites
Sem conteúdo oficial real ainda; ligação do botão contextual: só 3 telas; sem tradução; sem editor rico (texto em parágrafos, sem HTML — evita injeção).
