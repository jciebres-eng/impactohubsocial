"""Assistência de IA (sempre rascunho + revisão humana; nunca decide elegibilidade, aprova ou assina)."""
from __future__ import annotations

from ..http import Ctx, not_found, page, route
from . import schemas as S

T = ("ai",)


@route("POST", "/v1/ai/structure-need", body=S.AiStructureIn, min_role="member", kinds=("osc",), rate=("ai_ip", 60, 3600), tags=T,
       summary="Transforma uma necessidade descrita livremente em projeto estruturado (título, causas, ODS, itens de orçamento, perguntas)")
def structure_need(ctx: Ctx, body: S.AiStructureIn):
    return ctx.app.ai.structure_need(ctx, body.text)


@route("POST", "/v1/ai/draft", body=S.AiDraftIn, min_role="member", kinds=("osc",), rate=("ai_ip", 60, 3600), tags=T,
       summary="Gera rascunho de proposta/plano/relatório a partir dos dados do projeto (marca [COMPLETAR] onde faltar)")
def draft(ctx: Ctx, body: S.AiDraftIn):
    with ctx.tx(readonly=True) as c:
        p = c.one("SELECT * FROM projects WHERE id = $1 AND org_id = $2", body.project_id, ctx.org_id)
        if not p:
            raise not_found("Projeto")
        org = c.one("SELECT legal_name, cnpj, city, uf FROM organizations WHERE id = $1", ctx.org_id)
        call = c.one("SELECT title, funder_name FROM calls WHERE id = $1", body.call_id) if body.call_id else None
        items = c.query("SELECT description, quantity::float AS quantity, unit_cost_cents, total_cents FROM budget_items WHERE project_id = $1"
                        " ORDER BY created_at", body.project_id)
        ms = c.query("SELECT seq, title, amount_cents, due_on FROM milestones WHERE project_id = $1 ORDER BY seq", body.project_id)
    return ctx.app.ai.draft(ctx, body.kind, p, org, call, items, ms, body.instructions)


@route("POST", "/v1/ai/summarize-project", body=S.AiSummarizeIn, min_role="viewer", rate=("ai_ip", 60, 3600), tags=T,
       summary="Resumo do projeto para leitura rápida do financiador")
def summarize(ctx: Ctx, body: S.AiSummarizeIn):
    with ctx.tx(readonly=True) as c:
        p = c.one("SELECT id::text AS id, title, summary, problem, objectives, methodology, beneficiaries_count, budget_total_cents, territory FROM projects"
                  " WHERE id = $1", body.project_id)
    if not p:
        raise not_found("Projeto")
    return ctx.app.ai.summarize(ctx, p)


# v0.23.0 — LIMITE DE TAXA. Esta era a única rota de IA sem `rate=`, e a auditoria apontou por quê
# isso importa mesmo sendo processamento local: ela lê `extracted_text` de até 20 mil caracteres e
# roda a classificação por documento, então serve de amplificador — uma conta pode varrer o próprio
# cofre em sequência e consumir CPU do servidor inteiro. As outras três já tinham o mesmo limite.
@route("POST", "/v1/ai/classify-document/{document_id}", min_role="member",
       rate=("ai_ip", 60, 3600), tags=T,
       summary="Sugere o tipo e a validade de um documento enviado (processamento local; nada é enviado a terceiros)")
def classify(ctx: Ctx):
    from ..engines.ai.local import classify_document
    with ctx.tx(readonly=True) as c:
        d = c.one("SELECT filename, extracted_text FROM documents WHERE id = $1 AND org_id = $2", ctx.path["document_id"], ctx.org_id)
    if not d:
        raise not_found("Documento")
    return classify_document((d["extracted_text"] or "")[:20000], d["filename"])


@route("GET", "/v1/ai/usage", min_role="viewer", tags=T,
       summary="Uso de IA no mês: cota, orçamento em dinheiro, crédito e como as chamadas terminaram")
def usage(ctx: Ctx):
    """O painel que a organização vê. Três controles diferentes, declarados como diferentes.

    Até a v0.22.0 esta rota devolvia três números (usado, limite, provedor) e o frontend não a
    consumia. Os controles que existem agora são distintos e precisam aparecer como distintos:

      * COTA conta chamadas (vem do plano);
      * ORÇAMENTO limita dinheiro (a organização define; `hard_stop` decide se avisa ou para);
      * CRÉDITO é unidade comercial, independente de token — é o que foi comprado ou concedido.

    E `outcomes` é a parte que faltava: até esta versão toda chamada era registrada como `ok`,
    inclusive quando a resposta do provedor era descartada. Mostrar a distribuição real é o que
    permite à organização perceber que metade das chamadas caiu no motor local.
    """
    from ..services.entitlements import effective
    with ctx.tx(readonly=True) as c:
        # A MESMA função que o bloqueio usa: o número exibido é o número que limita.
        used = c.scalar("SELECT ai_usage_this_month($1)", ctx.org_id)
        ent = effective(c, ctx.org_id, ctx.principal.org_kind)
        orcamento = c.one("SELECT * FROM ai_budget_state($1, current_date)", ctx.org_id)
        creditos = c.scalar("SELECT ai_credit_balance($1)", ctx.org_id)
        resultados = c.query(
            "SELECT status, count(*) AS calls, sum(coalesce(tokens_in,0) + coalesce(tokens_out,0)) AS tokens"
            "  FROM ai_usage WHERE org_id = $1 AND created_at > now() - interval '30 days'"
            " GROUP BY status ORDER BY calls DESC", ctx.org_id)
        versoes = c.query(
            "SELECT prompt_key, prompt_version, tier, count(*) AS calls FROM ai_usage"
            " WHERE org_id = $1 AND prompt_key IS NOT NULL"
            "   AND created_at > now() - interval '30 days'"
            " GROUP BY 1,2,3 ORDER BY calls DESC", ctx.org_id)
    return {
        "quota": {"used_this_month": used, "limit": ent["limits"].get("ai_requests_month"),
                  "counts": "chamadas"},
        "budget": dict(orcamento) if orcamento else None,
        "credits": {"balance": creditos,
                    "note": "Crédito é unidade comercial da plataforma. NÃO é token: token é "
                            "unidade do provedor e muda quando o provedor muda de tabela."},
        "outcomes_30d": resultados,
        "prompt_versions_30d": versoes,
        "provider": ctx.app.ai.provider_name,
        "note": "Cota conta chamadas; orçamento limita dinheiro; crédito é saldo comercial. São "
                "três controles diferentes e qualquer um deles pode barrar uma chamada.",
    }


@route("GET", "/v1/ai/policies", min_role="viewer", tags=T,
       summary="Política de IA por faixa de risco: o que sai da instalação e o que exige revisão humana")
def ai_policies(ctx: Ctx):
    """Pública para quem está autenticado, de propósito.

    A organização tem direito de saber que a faixa 3 não sai da instalação e que toda saída exige
    revisão humana. Esconder a política obrigaria a confiar na palavra da plataforma sobre o
    tratamento do dado dela.
    """
    with ctx.tx(readonly=True) as c:
        faixas = c.query("SELECT tier, label, max_input_chars, max_output_tokens, allow_external,"
                         "       requires_schema, requires_human_review, note"
                         "  FROM ai_model_policies ORDER BY tier")
        # `ai_prompt_public` e não `ai_prompts`: a visão não tem a coluna `system_text`. A
        # organização vê QUAL instrução processou o dado dela, não a instrução.
        em_uso = c.query("SELECT prompt_key, version, tier, has_schema FROM ai_prompt_public"
                         " WHERE active ORDER BY tier, prompt_key")
    return {"tiers": faixas, "active_uses": em_uso,
            "guarantees": [
                "Nenhuma saída de IA vira estado do sistema sozinha: toda faixa exige revisão humana.",
                "A IA não tem ferramenta para chamar nem acesso de escrita ao banco.",
                "Dado pessoal é redigido (CPF, CNPJ, e-mail, telefone, CEP, RG, número longo) "
                "antes de qualquer envio externo.",
                "Nenhum dado desta plataforma é usado para treinar modelo.",
                "A faixa 4 (efeito jurídico ou financeiro) não tem nenhum uso implementado, e os "
                "limites dela a tornam inoperante por construção.",
            ],
            "note": "A faixa é do USO, não do modelo: classificar por modelo amarraria a política "
                    "ao catálogo do provedor e envelheceria a cada lançamento."}


@route("GET", "/v1/ai/estimate", min_role="viewer", query=S.AiEstimateQ, tags=T,
       summary="Estimativa de custo ANTES de uma operação paga (ou a declaração de que não há preço)")
def ai_estimate(ctx: Ctx, q: S.AiEstimateQ):
    """Estimar antes é o que permite decidir. E dizer que NÃO SE SABE é parte de estimar.

    A tabela de preço do provedor nasce vazia nesta base — nenhum preço foi inventado no pacote.
    Sem linha vigente, esta rota devolve `available: false` com o motivo, em vez de zero: zero
    pareceria custo apurado, e a pessoa decidiria com base num número que ninguém calculou.
    """
    with ctx.tx(readonly=True) as c:
        prompt = c.one("SELECT p.prompt_key, p.version, p.tier, m.label, m.max_input_chars,"
                       "       m.max_output_tokens, m.allow_external"
                       "  FROM ai_prompt_public p JOIN ai_model_policies m ON m.tier = p.tier"
                       " WHERE p.prompt_key = $1 AND p.active", q.prompt_key)
        if not prompt:
            raise not_found("Prompt")
        preco = c.one("SELECT input_per_mtok_cents, output_per_mtok_cents, currency, source_name,"
                      "       source_date FROM ai_price_table"
                      " WHERE provider = $1 AND (model = $2 OR $2 IS NULL)"
                      "   AND effective_from <= current_date"
                      "   AND (effective_until IS NULL OR effective_until >= current_date)"
                      " ORDER BY effective_from DESC LIMIT 1",
                      ctx.app.ai.provider_name, ctx.app.settings.ai_model or None)
    # 4 caracteres por token é a aproximação usada em todo o setor para português e inglês. É
    # declarada como aproximação porque é: a contagem exata depende do tokenizador do provedor.
    tokens_entrada = max(1, q.input_chars // 4)
    tokens_saida = prompt["max_output_tokens"]
    base = {"prompt": f'{prompt["prompt_key"]}@{prompt["version"]}', "tier": prompt["tier"],
            "tier_label": prompt["label"], "input_chars": q.input_chars,
            "estimated_tokens_in": tokens_entrada, "max_tokens_out": tokens_saida,
            "token_estimate_method": "aproximação de 4 caracteres por token; a contagem exata "
                                     "depende do tokenizador do provedor",
            "within_tier_limit": q.input_chars <= prompt["max_input_chars"],
            "max_input_chars": prompt["max_input_chars"],
            "leaves_installation": bool(prompt["allow_external"]) and ctx.app.ai.external is not None}
    if not preco:
        return base | {"available": False,
                       "unavailable_reason": "no_price_table",
                       "cost_cents": None,
                       "note": "Não há preço vigente para este provedor e modelo na tabela de "
                               "preço. O custo fica indisponível em vez de zero: zero pareceria "
                               "custo apurado. Cadastre o preço em Administração → IA."}
    centavos = round(tokens_entrada * preco["input_per_mtok_cents"] / 1_000_000
                     + tokens_saida * preco["output_per_mtok_cents"] / 1_000_000, 4)
    return base | {"available": True, "cost_cents": centavos,
                   "currency": preco["currency"], "price_source": preco["source_name"],
                   "price_date": preco["source_date"],
                   "note": "Estimativa do PIOR caso de saída (o máximo da faixa). O custo real "
                           "usa os tokens que o provedor informar."}


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# ORÇAMENTO DA PRÓPRIA ORGANIZAÇÃO
#
# O limite é da organização, não da plataforma: quem paga decide quanto quer gastar. `hard_stop`
# separa "avise" de "pare", e o padrão é AVISAR — parar o trabalho de alguém por decisão da
# plataforma seria escolher por ela.

@route("PUT", "/v1/ai/budget", body=S.AiBudgetIn, min_role="admin", tags=T,
       summary="Define o orçamento de IA da organização para o mês corrente")
def set_budget(ctx: Ctx, body: S.AiBudgetIn):
    with ctx.tx() as c:
        c.run("INSERT INTO ai_budgets(org_id, period, limit_cents, warn_at_pct, hard_stop, note,"
              " created_by) VALUES ($1, date_trunc('month', current_date)::date, $2, $3, $4, $5, $6)"
              " ON CONFLICT (org_id, period) DO UPDATE SET limit_cents = EXCLUDED.limit_cents,"
              " warn_at_pct = EXCLUDED.warn_at_pct, hard_stop = EXCLUDED.hard_stop,"
              " note = EXCLUDED.note",
              ctx.org_id, body.limit_cents, body.warn_at_pct, body.hard_stop, body.note, ctx.user_id)
        estado = c.one("SELECT * FROM ai_budget_state($1, current_date)", ctx.org_id)
        ctx.audit(c, "ai.budget_set", "ai_budget", ctx.org_id,
                  {"limit_cents": body.limit_cents, "hard_stop": body.hard_stop})
    return dict(estado) | {
        "note": "Chamadas sem preço vigente na tabela do provedor não entram no gasto apurado. "
                "`unpriced_calls` diz quantas são — se for alto, o orçamento está medindo pouco."}


@route("GET", "/v1/ai/credits", min_role="viewer", query=S.Pagination, tags=T,
       summary="Extrato de crédito de IA: concessão, consumo e devolução, em ordem")
def credits(ctx: Ctx, q: S.Pagination):
    """Extrato, não saldo. O saldo é soma do extrato — nunca uma coluna que alguém atualiza.

    Foi a lição do Value Ledger: coluna de saldo é um número que pode divergir dos lançamentos sem
    que nada acuse, e aí não há como responder "como esse saldo chegou a isto".
    """
    with ctx.tx(readonly=True) as c:
        linhas = c.query("SELECT id, delta, reason, ref_type, ref_id, note, created_at"
                         "  FROM ai_credit_ledger WHERE org_id = $1"
                         " ORDER BY id DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
        saldo = c.scalar("SELECT ai_credit_balance($1)", ctx.org_id)
    return page(linhas, q.limit, q.offset) | {"balance": saldo}


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# CENTRAL DE CONTROLE DE IA (administração da plataforma)

@route("GET", "/v1/admin/ai", auth="admin", permission="metrics.read", tags=("admin",),
       summary="Central de controle de IA: prompts, faixas, resultados reais, custo e o que não está implementado")
def ai_control_center(ctx: Ctx):
    """O painel da operação. Três coisas que ele mostra e que antes não existiam em lugar nenhum:

      1. COMO as chamadas terminaram de verdade, por `status`. Até esta versão tudo era `ok`.
      2. Qual VERSÃO de prompt produziu o quê — sem isso não há avaliação nem regressão.
      3. O que NÃO está implementado, nomeado. Um painel que mostra só o que existe faz o que
         falta parecer inexistente em vez de ausente.
    """
    from ..core.access import log_privileged
    from ..engines.ai import prompts as PR
    log_privileged(ctx, "metrics.read")
    with ctx.system_tx() as c:
        catalogo = PR.catalog(c)
        faixas = c.query("SELECT tier, label, allow_external, requires_schema,"
                         "       requires_human_review, max_input_chars, max_output_tokens, note"
                         "  FROM ai_model_policies ORDER BY tier")
        resultados = c.query(
            "SELECT status, count(*) AS calls,"
            "       count(*) FILTER (WHERE schema_valid IS FALSE) AS schema_failures,"
            "       round(avg(latency_ms)) AS avg_latency_ms"
            "  FROM ai_usage WHERE created_at > now() - interval '30 days'"
            " GROUP BY status ORDER BY calls DESC")
        custo = c.one(
            "SELECT count(*) AS calls,"
            "       count(*) FILTER (WHERE cost_status = 'no_price_table') AS unpriced,"
            "       sum(cost_cents_estimate) AS cents,"
            "       sum(coalesce(tokens_in,0)) AS tokens_in,"
            "       sum(coalesce(tokens_out,0)) AS tokens_out"
            "  FROM ai_usage WHERE created_at > now() - interval '30 days'")
        precos = c.query("SELECT provider, model, input_per_mtok_cents, output_per_mtok_cents,"
                         "       currency, source_name, source_date, effective_from"
                         "  FROM ai_price_table ORDER BY effective_from DESC LIMIT 20")
        orcamentos = c.query(
            "SELECT b.org_id::text AS org_id, o.legal_name, b.limit_cents, b.hard_stop,"
            "       (SELECT spent_cents FROM ai_budget_state(b.org_id, b.period)) AS spent_cents"
            "  FROM ai_budgets b JOIN organizations o ON o.id = b.org_id"
            " WHERE b.period = date_trunc('month', current_date)::date ORDER BY b.limit_cents DESC"
            " LIMIT 50")
        creditos = c.one(
            "SELECT count(DISTINCT org_id) AS orgs, sum(delta) FILTER (WHERE delta > 0) AS granted,"
            "       -sum(delta) FILTER (WHERE delta < 0) AS consumed FROM ai_credit_ledger")
    return {
        "provider": ctx.app.ai.provider_name,
        "model": ctx.app.settings.ai_model or None,
        "external_configured": ctx.app.ai.external is not None,
        "prompts": catalogo,
        "tiers": faixas,
        "outcomes_30d": resultados,
        "cost_30d": dict(custo) | {
            "note": "`unpriced` são chamadas sem preço vigente na tabela do provedor: elas NÃO "
                    "entram em `cents`. Se `unpriced` for alto, o custo apurado mede pouco."},
        "price_table": precos,
        "price_table_note": "A tabela nasce VAZIA de propósito: nenhum preço de provedor foi "
                            "inventado neste pacote. Preço é configuração, com fonte e data.",
        "budgets": orcamentos,
        "credits": dict(creditos),
        "not_implemented": [
            {"item": "Embeddings e busca semântica (RAG com recuperação por similaridade)",
             "reason": "Exigiria provedor de embedding contratado e pgvector. A recuperação hoje "
                       "é por consulta relacional com a RLS da organização, que é mais lenta e "
                       "não vaza entre inquilinos."},
            {"item": "Cache semântico de resposta",
             "reason": "Depende de embeddings. Cache por hash exato existe implicitamente em "
                       "`input_sha256`, mas não é usado para servir resposta: servir resposta "
                       "guardada de outro pedido exigiria decidir quando duas perguntas são a "
                       "mesma, e errar isso é entregar o dado de um projeto na resposta de outro."},
            {"item": "Fallback entre provedores externos",
             "reason": "Exige política de privacidade e base legal POR PROVEDOR. Mandar o dado "
                       "para um segundo provedor porque o primeiro caiu é tratamento que a "
                       "organização não autorizou. O fallback existente é para o motor LOCAL."},
            {"item": "Processamento em lote",
             "reason": "Exige volume e preço de lote reais para valer a pena. Nenhum dos dois "
                       "existe nesta instalação."},
            {"item": "Uso de ferramenta (tool calling) e agentes",
             "reason": "Dar ferramenta à IA é dar a ela a capacidade de MUDAR estado. A garantia "
                       "central desta camada é que nenhuma saída de IA vira estado do sistema "
                       "sozinha, e ferramenta a derruba."},
        ],
        "guarantees": [
            "Nenhum dado desta plataforma é usado para treinar modelo.",
            "Toda saída de IA é rascunho e exige revisão humana, em todas as faixas.",
            "A faixa 3 (afirmação sobre terceiro) não sai da instalação.",
            "A faixa 4 (efeito jurídico ou financeiro) não tem uso implementado.",
        ],
    }


@route("GET", "/v1/admin/ai/prompts/{prompt_key}", auth="admin", permission="metrics.read",
       tags=("admin",), summary="Histórico de versões de um prompt (sem o texto, que é do produto)")
def ai_prompt_versions(ctx: Ctx):
    from ..engines.ai import prompts as PR
    with ctx.system_tx() as c:
        versoes = PR.versions(c, ctx.path["prompt_key"])
        uso = c.query("SELECT prompt_version, status, count(*) AS calls,"
                      "       count(*) FILTER (WHERE schema_valid IS FALSE) AS schema_failures"
                      "  FROM ai_usage WHERE prompt_key = $1 GROUP BY 1,2 ORDER BY 1 DESC, 3 DESC",
                      ctx.path["prompt_key"])
    if not versoes:
        raise not_found("Prompt")
    return {"prompt_key": ctx.path["prompt_key"], "versions": versoes, "usage_by_version": uso,
            "note": "O texto da instrução não vai na resposta: ele é parte do produto. O que vai é "
                    "a versão, a faixa, se tem esquema e como as chamadas dela terminaram."}
