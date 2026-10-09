"""Camada de conhecimento v0.29.0: fontes com direitos de uso, citações, retirada com motivo e fila editorial (migração 0069).

Público: consulta de fontes (são referências, não conteúdo privado) e relato de informação incorreta.
Equipe editorial (staff_roles com MFA): registrar fonte (editor), verificar fonte (reviewer, nunca quem registrou), citar na versão em
rascunho (editor), retirar conteúdo/fonte com motivo (reviewer), fila de trabalho (editor/reviewer/support).
"""
from __future__ import annotations

from ..http import ApiError, Ctx, route
from ..services import kb_provenance as KP
from . import hub_schemas as H

T = ("help",)
TA = ("admin", "content")
EDIT = ("editor", "reviewer")
REVIEW = ("reviewer",)
SUPPORT = ("support",)
R_READ = ("help_src_ip", 300, 3600)


def A(method, path, staff=(), **kw):
    return route(method, path, auth="admin", tags=TA, staff=staff, **kw)


# ------------------------------------------------------------------------------------------------ público
@route("GET", "/v1/help/sources", auth="none", query=H.SourceListQ, rate=R_READ, tags=T,
       summary="Registro de fontes da camada de conhecimento: classe editorial O/A/V/H/D, jurisdição, vigência, licença, direitos de uso e verificação")
def sources_public(ctx: Ctx, q: H.SourceListQ):
    with ctx.tx() as c:
        items = KP.list_sources(c, klass=q.klass, status=q.status or "active", limit=q.limit, offset=q.offset)
    return {"items": items, "taxonomy": KP.KLASS_LABEL,
            "notice": "A classe é classificação editorial, não parecer jurídico; 'unknown' em um direito de uso significa que a operação está bloqueada até conferência."}


@route("GET", "/v1/help/sources/{key}", auth="none", rate=R_READ, tags=T, summary="Uma fonte, com os conteúdos que a citam")
def source_public(ctx: Ctx):
    with ctx.tx() as c:
        return KP.get_source(c, ctx.path["key"])


@route("POST", "/v1/help/report-incorrect", auth="user", body=H.IncorrectReportIn, rate=("help_report_ip", 20, 3600), tags=T,
       summary="Relata informação incorreta em um conteúdo publicado: entra na fila editorial para revisão humana (o conteúdo continua visível até a revisão)")
def report_incorrect(ctx: Ctx, body: H.IncorrectReportIn):
    with ctx.tx() as c:
        out = KP.report_incorrect(c, reporter=ctx.user_id, target_type=body.target_type, target_id=body.target_id, what=body.what, ctx_key=body.ctx)
        ctx.audit(c, "kb.incorrect_report", body.target_type, body.target_id, {"work_item_id": out.get("work_item_id")})
    return out


# ------------------------------------------------------------------------------------------------ equipe editorial
@A("POST", "/v1/admin/content/sources", staff=EDIT, body=H.SourceIn, status=201, summary="Registra uma fonte (classe O/A/V/H/D, jurisdição, vigência, licença, direitos de uso); nasce 'unverified'")
def source_create(ctx: Ctx, body: H.SourceIn):
    with ctx.tx() as c:
        out = KP.create_source(c, actor=ctx.user_id, data=body.model_dump())
        ctx.audit(c, "kb.source_registered", "kb_source", out["id"], {"key": body.key, "klass": body.klass})
    return out


@A("POST", "/v1/admin/content/sources/{key}/verify", staff=REVIEW, body=H.SourceVerifyIn,
   summary="Marca a fonte como conferida/em disputa/vencida — por pessoa diferente de quem a registrou (quatro olhos)")
def source_verify(ctx: Ctx, body: H.SourceVerifyIn):
    with ctx.tx() as c:
        out = KP.verify_source(c, ctx.path["key"], actor=ctx.user_id, verification=body.verification, note=body.note, review_due=body.review_due)
        ctx.audit(c, "kb.source_verified", "kb_source", out["id"], {"verification": body.verification})
    return out


@A("POST", "/v1/admin/content/sources/{key}/retract", staff=REVIEW, body=H.RetractIn,
   summary="Retira uma fonte (terminal, com motivo); todo conteúdo que a cita vira item de trabalho — não é retirado automaticamente")
def source_retract(ctx: Ctx, body: H.RetractIn):
    with ctx.tx() as c:
        out = KP.retract_source(c, ctx.path["key"], actor=ctx.user_id, reason=body.reason)
        ctx.audit(c, "kb.source_retracted", "kb_source", out["id"], {"reason": body.reason})
    return out


@A("POST", "/v1/admin/content/citations", staff=EDIT, body=H.CitationIn, status=201,
   summary="Cita uma fonte numa versão em RASCUNHO (localizador; trecho só se a fonte tiver direito de trecho permitido; hash conferido pelo banco)")
def citation_create(ctx: Ctx, body: H.CitationIn):
    with ctx.tx() as c:
        out = KP.add_citation(c, actor=ctx.user_id, object_type=body.object_type, object_id=body.object_id, source=body.source, locator=body.locator,
                              excerpt=body.excerpt, claim=body.claim)
        ctx.audit(c, "kb.citation_added", body.object_type, body.object_id, {"source_id": out["source_id"], "has_excerpt": out["has_excerpt"]})
    return out


@A("GET", "/v1/admin/content/citations/{object_type}/{object_id}", staff=EDIT + SUPPORT, summary="Citações de uma versão/FAQ/recurso")
def citations_get(ctx: Ctx):
    if ctx.path["object_type"] not in KP.OBJECT_TABLE:
        raise ApiError(404, "not_found", "Tipo de conteúdo")
    with ctx.tx() as c:
        return {"items": KP.citations_for(c, ctx.path["object_type"], ctx.path["object_id"])}


@A("POST", "/v1/admin/content/{object_type}/{object_id}/retract", staff=REVIEW, body=H.RetractIn,
   summary="Retira conteúdo publicado (terminal, com motivo): sai da busca, do assistente e do sitemap; reativar exige nova versão")
def content_retract(ctx: Ctx, body: H.RetractIn):
    if ctx.path["object_type"] not in KP.OBJECT_TABLE:
        raise ApiError(404, "not_found", "Tipo de conteúdo")
    with ctx.tx() as c:
        out = KP.retract(c, ctx.path["object_type"], ctx.path["object_id"], actor=ctx.user_id, reason=body.reason)
        ctx.audit(c, "kb.retracted", ctx.path["object_type"], ctx.path["object_id"], {"reason": body.reason})
    return out


@A("GET", "/v1/admin/content/work-items", staff=EDIT + SUPPORT, query=H.WorkItemsQ,
   summary="Fila editorial: buscas sem resultado, assistente sem base, 'não ajudou', vencidos, relatos de erro, fontes a revisar")
def work_items(ctx: Ctx, q: H.WorkItemsQ):
    with ctx.tx() as c:
        return KP.work_items(c, status=q.status, kind=q.kind, limit=q.limit, offset=q.offset)


@A("POST", "/v1/admin/content/work-items/sweep", staff=EDIT, summary="Varre conteúdo vencido/atrasado e fontes a revisar e abre os itens que faltam (idempotente)")
def work_items_sweep(ctx: Ctx):
    with ctx.tx() as c:
        out = KP.sweep_stale(c)
        ctx.audit(c, "kb.work_sweep", None, None, out)
    return out


@A("POST", "/v1/admin/content/work-items/{item}", staff=EDIT + SUPPORT, body=H.WorkItemUpdateIn, summary="Assume, conclui ou dispensa um item (concluir/dispensar exige resolução)")
def work_item_update(ctx: Ctx, body: H.WorkItemUpdateIn):
    try:
        item_id = int(ctx.path["item"])
    except ValueError:
        raise ApiError(404, "not_found", "Item") from None
    with ctx.tx() as c:
        out = KP.resolve_work(c, item_id, actor=ctx.user_id, status=body.status, resolution=body.resolution, assigned_to=body.assigned_to)
        ctx.audit(c, "kb.work_item", "kb_work_item", str(item_id), {"status": body.status})
    return out
