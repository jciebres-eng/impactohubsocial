"""Assistência de IA (sempre rascunho + revisão humana; nunca decide elegibilidade, aprova ou assina)."""
from __future__ import annotations

from ..http import Ctx, not_found, route
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
        p = c.one("SELECT title, summary, problem, objectives, methodology, beneficiaries_count, budget_total_cents, territory FROM projects"
                  " WHERE id = $1", body.project_id)
    if not p:
        raise not_found("Projeto")
    return ctx.app.ai.summarize(ctx, p)


@route("POST", "/v1/ai/classify-document/{document_id}", min_role="member", tags=T,
       summary="Sugere o tipo e a validade de um documento enviado (processamento local; nada é enviado a terceiros)")
def classify(ctx: Ctx):
    from ..engines.ai.local import classify_document
    with ctx.tx(readonly=True) as c:
        d = c.one("SELECT filename, extracted_text FROM documents WHERE id = $1 AND org_id = $2", ctx.path["document_id"], ctx.org_id)
    if not d:
        raise not_found("Documento")
    return classify_document((d["extracted_text"] or "")[:20000], d["filename"])


@route("GET", "/v1/ai/usage", min_role="viewer", tags=T, summary="Uso de IA no mês (cota do plano)")
def usage(ctx: Ctx):
    from ..services.entitlements import effective
    with ctx.tx(readonly=True) as c:
        used = c.scalar("SELECT count(*) FROM ai_usage WHERE org_id = $1 AND created_at >= date_trunc('month', now())", ctx.org_id)
        ent = effective(c, ctx.org_id, ctx.principal.org_kind)
    return {"used_this_month": used, "limit": ent["limits"].get("ai_requests_month"), "provider": ctx.app.ai.provider_name}
