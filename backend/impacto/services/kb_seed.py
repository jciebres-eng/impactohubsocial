"""Conteúdo INICIAL da Central de Conhecimento (v0.12.0) — TODO marcado como `demo` (exemplo/rascunho, nunca oficial) e de origem educacional.

Descreve apenas fluxos que existem na plataforma; NÃO contém regras fiscais/legais, valores, prazos regulatórios nem promessas de resultado.
Em produção o import cria só RASCUNHOS (autor = pessoa informada); a publicação passa pelo fluxo editorial com revisão de outra pessoa.
Em desenvolvimento (`seed-demo`) os itens são publicados com o selo DEMO, para que a interface possa ser avaliada com conteúdo real de layout."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, UTC

DEMO_NOTE = "Conteúdo de exemplo para validação editorial."

# slug, kind, categoria, público, visibilidade, título, resumo, passos[(título, texto)], checklist, erros comuns, ação (rótulo, link), ctx_keys, tags, minutos, relacionados(recursos)
ARTICLES = [
    ("comece-aqui-osc", "start", "primeiros-passos", ["osc"], "authenticated", "Comece aqui: guia para organizações da sociedade civil",
     "Da conta ao primeiro projeto publicado e à prestação de contas: a ordem que costuma funcionar.",
     [("Complete o perfil da organização", "Informe descrição, território e causas em Organização."), ("Envie os documentos básicos", "Em Documentos, envie os arquivos da lista de verificação."),
      ("Cadastre o primeiro projeto", "Em Projetos, preencha objetivos, território, orçamento e indicadores."), ("Acompanhe a análise de conformidade", "Veja pendências em Organização > Conformidade."),
      ("Explore oportunidades", "Em Oportunidades e Explorar, veja editais e financiadores compatíveis.")],
     ["Perfil completo", "Documentos enviados", "Projeto com orçamento", "Conformidade sem pendências"],
     ["Deixar o orçamento sem justificativa dos itens", "Enviar documentos vencidos"], ("Ver meu progresso", "/"), ["home.start"], ["primeiros passos", "cadastro", "osc"], 10, ["checklist-documentos-organizacao"]),
    ("comece-aqui-empresa", "start", "primeiros-passos", ["company"], "authenticated", "Comece aqui: guia para empresas e financiadores",
     "Defina seu perfil de apoio, salve buscas e acompanhe os projetos que você apoia.",
     [("Complete o perfil da empresa", "Em Organização, informe causas e territórios de interesse."), ("Defina seu perfil de financiador", "Registre critérios de apoio."),
      ("Salve uma busca", "Em Oportunidades, salve filtros para receber novidades."), ("Manifeste interesse e acompanhe", "Use Explorar e Carteira.")],
     ["Perfil completo", "Critérios definidos"], ["Perfil genérico demais"], ("Explorar projetos", "/explorar"), ["home.start"], ["primeiros passos", "empresa", "financiador"], 8, []),
    ("como-cadastrar-organizacao", "guide", "primeiros-passos", [], "public", "Como cadastrar a organização",
     "Crie sua conta, informe os dados da organização e confirme o e-mail.",
     [("Crie a conta", "Informe e-mail, senha e aceite os termos."), ("Informe a organização", "Tipo, nome e CNPJ (quando exigido)."), ("Confirme o e-mail", "Use o link enviado para sua caixa de entrada."),
      ("Ative o MFA", "Recomendado para proteger a conta.")],
     ["E-mail confirmado", "Dados da organização conferidos"], ["Usar e-mail compartilhado sem acesso de todos"], ("Ir para a organização", "/organizacao"), ["org.profile"], ["cadastro", "organização", "conta"], 5, []),
    ("como-enviar-documentos", "guide", "documentos", ["osc", "company", "provider"], "authenticated", "Como enviar e manter documentos",
     "Envie arquivos, acompanhe a verificação e fique atento às validades.",
     [("Abra Documentos", "Acesse o menu Documentos."), ("Envie o arquivo", "Escolha o tipo, informe o título e a validade quando houver."),
      ("Aguarde a verificação", "Todo arquivo passa por varredura antes de ser liberado."), ("Acompanhe validades", "Você recebe avisos de documentos vencendo.")],
     ["Tipo correto selecionado", "Validade informada", "Arquivo legível"], ["Enviar foto cortada", "Esquecer de atualizar documento vencido"], ("Enviar documento", "/documentos"),
     ["documents.upload"], ["documentos", "upload", "validade"], 6, ["checklist-documentos-organizacao"]),
    ("como-cadastrar-projeto", "guide", "projetos", ["osc"], "authenticated", "Como cadastrar um projeto",
     "Descreva problema, objetivos, território, beneficiários, orçamento e indicadores.",
     [("Crie o projeto", "Em Projetos, clique em novo projeto."), ("Descreva o problema e os objetivos", "Seja específica: quem, onde, quanto."), ("Defina território e público", "Use o território mais preciso possível."),
      ("Cadastre indicadores", "Escolha indicadores do catálogo e defina metas."), ("Monte o orçamento", "Veja o guia de orçamento.")],
     ["Objetivos mensuráveis", "Território definido", "Indicadores com metas", "Orçamento por item"], ["Objetivos genéricos", "Meta sem data"], ("Cadastrar projeto", "/projetos"),
     ["project.new", "project.form"], ["projeto", "cadastro", "indicadores"], 12, ["modelo-plano-trabalho", "como-montar-orcamento"]),
    ("como-montar-orcamento", "guide", "orcamento", ["osc"], "authenticated", "Como montar o orçamento do projeto",
     "Itens, quantidades, valores e justificativa — a base para cotações e prestação de contas.",
     [("Liste os itens", "Um item por linha, com unidade e quantidade."), ("Informe valores unitários", "Use valores que você consegue comprovar."), ("Justifique cada grupo de itens", "Explique por que o item é necessário."),
      ("Revise o total", "Confira se o total confere com o plano de trabalho.")],
     ["Todos os itens com valor", "Justificativa por grupo", "Total conferido"], ["Valores redondos sem base", "Itens sem relação com as metas"], ("Abrir orçamento", "/projetos"),
     ["project.budget"], ["orçamento", "itens", "justificativa"], 8, ["modelo-justificativa-orcamento"]),
    ("como-fazer-cotacoes", "guide", "orcamento", ["osc"], "authenticated", "Como registrar cotações de fornecedores",
     "Registre propostas comparáveis e guarde a justificativa da escolha.",
     [("Crie o pedido de compra", "Descreva o item ou serviço."), ("Registre as propostas", "Inclua fornecedor, valor e prazo."), ("Compare e justifique", "Registre por que a escolhida atende melhor.")],
     ["Ao menos duas propostas comparáveis quando aplicável", "Justificativa registrada"], ["Propostas sem data", "Escolha sem justificativa"], ("Ir para projetos", "/projetos"),
     ["procurement.quotation"], ["cotação", "fornecedor", "compras"], 7, []),
    ("entender-conformidade", "how_it_works", "documentos", ["osc", "company", "provider"], "authenticated", "Como funciona a análise de conformidade",
     "O que é verificado, o que significa cada situação e como resolver pendências.",
     [("Veja sua situação", "Em Organização > Conformidade."), ("Resolva pendências", "Cada pendência indica o que fazer."), ("Aguarde a revisão", "Algumas verificações dependem de revisão humana.")],
     ["Pendências resolvidas"], ["Ignorar avisos de documento vencendo"], ("Ver conformidade", "/organizacao/compliance"), ["compliance.status"], ["conformidade", "compliance", "pendências"], 5, []),
    ("como-funciona-a-compatibilidade", "how_it_works", "match-financiamento", [], "authenticated", "Como funciona a compatibilidade (match)",
     "A compatibilidade é uma estimativa baseada em regras explicadas na tela — não garante aprovação.",
     [("Veja o motivo", "Cada resultado mostra por que foi sugerido."), ("Ajuste seu perfil", "Perfil e projeto completos melhoram as sugestões."), ("Manifeste interesse", "A decisão final é sempre humana.")],
     [], ["Tratar a compatibilidade como garantia"], ("Ver oportunidades", "/oportunidades"), ["match.explain"], ["match", "compatibilidade", "oportunidades"], 5, []),
    ("como-prestar-contas", "guide", "execucao-prestacao", ["osc"], "public", "Como registrar a execução e prestar contas do projeto",
     "Registre despesas, anexe comprovantes e envie evidências para validação.",
     [("Registre as despesas", "Associe cada despesa ao item do orçamento."), ("Anexe comprovantes", "Envie nota, recibo ou documento equivalente."), ("Envie evidências de resultado", "Fotos, listas de presença ou relatórios."),
      ("Acompanhe a validação", "Quem apoia o projeto pode aceitar ou pedir mais informações.")],
     ["Despesas registradas", "Comprovantes anexados", "Evidências enviadas"], ["Despesa sem comprovante", "Evidência sem data"], ("Ir para execução", "/projetos"),
     ["execution.accountability", "execution.expense"], ["prestação de contas", "despesas", "evidências", "execução"], 10, ["checklist-prestacao-contas"]),
    ("como-funciona-o-periodo-de-teste", "how_it_works", "assinatura-trial", [], "public", "Como funciona o período de teste",
     "Durante o teste você tem acesso completo e não é cobrada; a cobrança só começa se contratar um plano.",
     [("Veja o tempo restante", "Em Conta > Plano."), ("Escolha continuar ou cancelar", "Cancele quando quiser antes do fim do teste."), ("Peça mais tempo", "Se precisar, solicite um teste em Central > Teste.")],
     [], ["Esperar o último dia para decidir"], ("Ver meu plano", "/conta/plano"), ["billing.plan"], ["teste", "plano", "assinatura"], 4, []),
    ("como-abrir-chamado", "procedure", "primeiros-passos", [], "public", "Como abrir um chamado de suporte",
     "Escolha a categoria, descreva o problema e anexe um arquivo se ajudar.",
     [("Abra a Central", "Menu Ajuda."), ("Descreva o problema", "Diga o que tentou e o que aconteceu."), ("Anexe se precisar", "Use arquivos já enviados em Documentos."), ("Acompanhe", "Você é avisada a cada resposta.")],
     ["Descrição clara", "Anexo quando útil"], ["Abrir vários chamados para o mesmo problema"], ("Abrir chamado", "/ajuda/suporte/novo"), ["support.new"], ["suporte", "chamado", "ajuda"], 3, []),
    ("privacidade-e-seus-dados", "policy", "privacidade-seguranca", [], "public", "Privacidade e seus dados na Central de Conhecimento",
     "Buscas guardam apenas um código e tópicos; formulários de contato exigem seu consentimento.",
     [("Entenda o que é guardado", "Não guardamos o texto das buscas."), ("Controle suas notificações", "Em Conta, ajuste preferências por tipo."), ("Cancele o boletim quando quiser", "Todo e-mail traz o link de descadastro.")],
     [], [], ("Ver minha conta", "/conta"), ["privacy.help"], ["privacidade", "lgpd", "dados"], 3, []),
    ("glossario-basico", "glossary", "primeiros-passos", [], "public", "Glossário básico da plataforma",
     "Termos usados na plataforma: OSC, edital, compatibilidade, conformidade, evidência.",
     [("OSC", "Organização da sociedade civil."), ("Edital", "Chamada pública com regras para receber propostas."), ("Evidência", "Prova de que algo foi executado."), ("Conformidade", "Situação documental e cadastral da organização.")],
     [], [], None, [], ["glossário", "termos"], 3, []),
]

FAQS = [
    ("Preciso pagar para pedir ajuda?", "Não. O suporte e o conteúdo da Central estão disponíveis para todas as contas, inclusive no plano gratuito.", "assinatura-trial", ["help.faq"], []),
    ("Quanto custa o plano pago?", "Os valores aparecem na tela de planos. Quando um plano está sem preço definido, a contratação online fica indisponível e a equipe atende sob consulta.", "assinatura-trial", ["billing.plan"], []),
    ("Posso cancelar o período de teste?", "Sim, a qualquer momento em Conta > Plano. Você não é cobrada durante o teste.", "assinatura-trial", ["billing.plan"], []),
    ("O certificado dos cursos vale como diploma?", "Não. É um certificado de conclusão da plataforma, verificável por código, sem validade como diploma ou certificação oficial.", "primeiros-passos", [], []),
    ("O assistente da Central usa inteligência artificial?", "Não. Ele monta a resposta a partir de conteúdo já publicado e sempre mostra a fonte. Se não houver base suficiente, avisa e oferece abrir um chamado.", "primeiros-passos", ["help.assistant"], []),
    ("Quem aprova o conteúdo oficial?", "Todo conteúdo é revisado e aprovado por uma pessoa diferente de quem escreveu, e traz a data da última revisão.", "primeiros-passos", [], []),
    ("O texto da minha busca fica guardado?", "Não. Guardamos apenas um código irreversível e os tópicos identificados, para melhorar o conteúdo sem expor o que você digitou.", "privacidade-seguranca", [], []),
    ("Como recupero minha senha?", "Na tela de entrada, use a opção de recuperação de senha e siga o link enviado ao seu e-mail.", "primeiros-passos", ["auth.login"], []),
]

TEMPLATE_FIELDS_PLAN = [{"key": "objetivo", "label": "Objetivo geral", "type": "textarea", "required": True, "help": "O que o projeto quer mudar e para quem."},
                        {"key": "metas", "label": "Metas e prazos", "type": "textarea", "required": True}, {"key": "atividades", "label": "Principais atividades", "type": "textarea"},
                        {"key": "equipe", "label": "Equipe responsável", "type": "text"}]
TEMPLATE_FIELDS_BUDGET = [{"key": "grupo", "label": "Grupo de itens", "type": "text", "required": True}, {"key": "justificativa", "label": "Por que estes itens são necessários", "type": "textarea", "required": True},
                          {"key": "relacao", "label": "Relação com as metas", "type": "textarea"}]

RESOURCES = [
    ("checklist-documentos-organizacao", "checklist", "documentos", "Checklist de documentos da organização", "Lista de verificação para manter os documentos em dia.", "authenticated",
     {"checklist_items": ["Estatuto ou documento constitutivo", "Cartão de CNPJ", "Ata/designação da diretoria vigente", "Certidões com validade em dia", "Comprovante de endereço"]}),
    ("checklist-prestacao-contas", "checklist", "execucao-prestacao", "Checklist de prestação de contas", "Itens para conferir antes de enviar a prestação de contas.", "authenticated",
     {"checklist_items": ["Todas as despesas registradas", "Comprovante de cada despesa", "Evidências de resultado com data", "Indicadores atualizados", "Relatório narrativo revisado"]}),
    ("modelo-plano-trabalho", "template", "projetos", "Modelo de plano de trabalho", "Modelo preenchível que gera um rascunho do plano de trabalho.", "authenticated",
     {"template_schema": {"draft_kind": "work_plan", "fields": TEMPLATE_FIELDS_PLAN}}),
    ("modelo-justificativa-orcamento", "template", "orcamento", "Modelo de justificativa de orçamento", "Modelo preenchível para justificar grupos de itens.", "authenticated",
     {"template_schema": {"draft_kind": "budget_justification", "fields": TEMPLATE_FIELDS_BUDGET}}),
]

COURSE = {
    "slug": "primeiros-passos-na-plataforma", "title": "Primeiros passos na plataforma", "summary": "Do cadastro à primeira prestação de contas, em três aulas curtas.", "hours": 1.0, "pass_score": 70,
    "modules": [{"title": "Fundamentos", "lessons": [
        {"title": "O que é a plataforma", "kind": "text", "minutes": 5, "body": "A plataforma conecta organizações, financiadores e prestadores. Cada perfil tem uma jornada própria em Comece aqui."},
        {"title": "Documentos e conformidade", "kind": "text", "minutes": 7, "body": "Envie documentos com validade, acompanhe a verificação e resolva pendências em Conformidade."},
        {"title": "Quiz de fundamentos", "kind": "quiz", "minutes": 5, "quiz": [
            {"q": "A compatibilidade (match) garante a aprovação de uma proposta?", "options": ["Sim", "Não, é uma estimativa explicada"], "answer": 1},
            {"q": "Quem pode aprovar um conteúdo oficial da Central?", "options": ["A própria autora", "Uma pessoa diferente da autora"], "answer": 1}]}]}],
}

PATH = {"slug": "trilha-osc-cadastro-a-prestacao", "title": "Trilha OSC: do cadastro à prestação de contas", "description": "Sequência sugerida de guias e curso para organizações.",
        "items": [{"type": "article", "slug": "comece-aqui-osc", "title": "Comece aqui"}, {"type": "article", "slug": "como-enviar-documentos", "title": "Documentos"},
                  {"type": "article", "slug": "como-cadastrar-projeto", "title": "Projeto"}, {"type": "course", "slug": "primeiros-passos-na-plataforma", "title": "Curso de primeiros passos"},
                  {"type": "article", "slug": "como-prestar-contas", "title": "Prestação de contas"}]}


def _j(v) -> str:
    return json.dumps(v, ensure_ascii=False)


def import_seed(c, *, author_id: str, reviewer_id: str | None, publish: bool) -> dict:
    """Importa o conteúdo inicial (idempotente por slug). `publish` só com revisor diferente do autor (quatro olhos)."""
    if publish and (not reviewer_id or reviewer_id == author_id):
        raise ValueError("publicar exige revisor diferente do autor")
    cat = {r["slug"]: r["id"] for r in c.query("SELECT slug, id::text AS id FROM kb_categories")}
    n = {"articles": 0, "faqs": 0, "resources": 0, "courses": 0, "events": 0, "paths": 0}
    st = "published" if publish else "draft"
    ap = reviewer_id if publish else None
    for slug, kind, catg, aud, vis, title, summary, steps, checklist, mistakes, action, ctxk, tags, minutes, related in ARTICLES:
        if c.one("SELECT 1 FROM kb_articles WHERE slug = $1", slug):
            continue
        aid = c.scalar("INSERT INTO kb_articles(slug, kind, category_id, audience, visibility, origin, tags, ctx_keys, est_minutes, action_label, action_link, related_resources, demo, created_by)"
                       " VALUES ($1,$2,$3,$4::text[],$5,'educational',$6::text[],$7::text[],$8,$9,$10,$11::text[],true,$12) RETURNING id::text",
                       slug, kind, cat.get(catg), aud, vis, tags, ctxk, minutes, action[0] if action else None, action[1] if action else None, related, author_id)
        body = summary + "\n\n" + DEMO_NOTE
        c.run("INSERT INTO kb_article_versions(article_id, version, title, summary, body, steps, checklist, common_mistakes, status, author_id, approved_by, approved_at, published_at, change_note)"
              " VALUES ($1,1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,$8,$9,$10, CASE WHEN $10::uuid IS NULL THEN NULL ELSE now() END, CASE WHEN $8 = 'published' THEN now() END, 'conteúdo inicial de exemplo')",
              aid, title, summary, body, _j([{"title": t, "text": x} for t, x in steps]), _j(checklist), _j(mistakes), st, author_id, ap)
        n["articles"] += 1
    for question, answer, catg, ctxk, tags in FAQS:
        if c.one("SELECT 1 FROM kb_faqs WHERE question = $1", question):
            continue
        c.run("INSERT INTO kb_faqs(category_id, question, answer, origin, ctx_keys, tags, status, author_id, approved_by, approved_at, published_at, last_reviewed_at, demo, visibility)"
              " VALUES ($1,$2,$3,'educational',$4::text[],$5::text[],$6,$7,$8, CASE WHEN $8::uuid IS NULL THEN NULL ELSE now() END, CASE WHEN $6 = 'published' THEN now() END, CASE WHEN $6 = 'published' THEN now() END, true, 'public')",
              cat.get(catg), question, answer, ctxk, tags, st, author_id, ap)
        n["faqs"] += 1
    for slug, kind, catg, title, summary, vis, extra in RESOURCES:
        if c.one("SELECT 1 FROM kb_resources WHERE slug = $1", slug):
            continue
        c.run("INSERT INTO kb_resources(slug, kind, category_id, title, summary, visibility, origin, template_schema, checklist_items, status, author_id, approved_by, approved_at, published_at, last_reviewed_at, demo)"
              " VALUES ($1,$2,$3,$4,$5,$6,'educational',$7::jsonb,$8::jsonb,$9,$10,$11, CASE WHEN $11::uuid IS NULL THEN NULL ELSE now() END, CASE WHEN $9 = 'published' THEN now() END, CASE WHEN $9 = 'published' THEN now() END, true)",
              slug, kind, cat.get(catg), title, summary, vis, _j(extra["template_schema"]) if "template_schema" in extra else None, _j(extra.get("checklist_items", [])), st, author_id, ap)
        n["resources"] += 1
    if not c.one("SELECT 1 FROM courses WHERE slug = $1", COURSE["slug"]):
        cid = c.scalar("INSERT INTO courses(slug, title, summary, visibility, origin, hours, pass_score, cert_enabled, status, author_id, approved_by, approved_at, published_at, last_reviewed_at, demo)"
                       " VALUES ($1,$2,$3,'authenticated','educational',$4,$5,true,$6,$7,$8, CASE WHEN $8::uuid IS NULL THEN NULL ELSE now() END, CASE WHEN $6 = 'published' THEN now() END, CASE WHEN $6 = 'published' THEN now() END, true) RETURNING id::text",
                       COURSE["slug"], COURSE["title"], COURSE["summary"], COURSE["hours"], COURSE["pass_score"], st, author_id, ap)
        for mi, m in enumerate(COURSE["modules"], 1):
            mid = c.scalar("INSERT INTO course_modules(course_id, position, title) VALUES ($1,$2,$3) RETURNING id::text", cid, mi, m["title"])
            for li, ls in enumerate(m["lessons"], 1):
                lid = c.scalar("INSERT INTO course_lessons(module_id, course_id, position, title, kind, body, minutes, quiz) VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb) RETURNING id::text",
                               mid, cid, li, ls["title"], ls["kind"], ls.get("body"), ls.get("minutes"), _j([{"q": q["q"], "options": q["options"]} for q in ls.get("quiz", [])]))
                if ls.get("quiz"):
                    c.run("INSERT INTO lesson_quiz_keys(lesson_id, answers) VALUES ($1,$2::int[])", lid, [q["answer"] for q in ls["quiz"]])
        n["courses"] += 1
    if not c.one("SELECT 1 FROM learning_paths WHERE slug = $1", PATH["slug"]):
        c.run("INSERT INTO learning_paths(slug, title, description, audience, visibility, items, status, author_id, approved_by, demo) VALUES ($1,$2,$3,'{osc}','authenticated',$4::jsonb,$5,$6,$7,true)",
              PATH["slug"], PATH["title"], PATH["description"], _j(PATH["items"]), "published" if publish else "draft", author_id, ap)
        n["paths"] += 1
    if not c.one("SELECT 1 FROM hub_events WHERE slug = 'webinar-primeiros-passos-exemplo'"):
        eid = c.scalar("INSERT INTO hub_events(slug, kind, title, description, starts_at, duration_min, speaker, modality, capacity, audience, visibility, status, author_id, approved_by, approved_at, published_at, demo)"
                       " VALUES ('webinar-primeiros-passos-exemplo','webinar','[EXEMPLO] Webinar: primeiros passos na plataforma','Evento de exemplo para validar a agenda e as inscrições.',$1,60,'Equipe de exemplo','online',100,'{}','public',$2,$3,$4, CASE WHEN $4::uuid IS NULL THEN NULL ELSE now() END, CASE WHEN $2 = 'published' THEN now() END, true) RETURNING id::text",
                       datetime.now(UTC) + timedelta(days=14), st, author_id, ap)
        c.run("INSERT INTO hub_event_links(event_id, join_url) VALUES ($1,'https://example.org/sala-ficticia')", eid)
        n["events"] += 1
    return n
