"""Registro de documento legal versionado, aceite com prova e painel de pendência jurídica."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..http import Ctx, route
from ..services import legal as LEGAL

T = ("legal",)


class AcceptIn(BaseModel):
    model_config = {"extra": "forbid"}
    doc_key: str = Field(min_length=2, max_length=40)
    source: str = Field(default="web", pattern="^(web|mobile|api)$")


class ApproveIn(BaseModel):
    model_config = {"extra": "forbid"}
    reviewed_by: str = Field(min_length=3, max_length=200,
                             description="Nome de quem assume a revisão jurídica desta versão")
    review_reference: str = Field(min_length=3, max_length=300,
                                  description="Parecer, processo ou documento que embasa a aprovação")
    effective_from: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class AcceptanceQ(BaseModel):
    model_config = {"extra": "forbid"}
    doc_key: str | None = Field(default=None, max_length=40)
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


@route("GET", "/v1/legal/registry", auth="none", tags=T,
       summary="Situação de cada documento legal: versão, se está aprovado e se bloqueia o produto")
def registry(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return LEGAL.overview(c)


@route("GET", "/v1/legal/documents/{doc_key}", auth="none", tags=T,
       summary="O texto de um documento, com a situação dele e o sha256 do que seria aceito")
def document(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return LEGAL.text(c, key=ctx.path["doc_key"])


@route("GET", "/v1/legal/pending", auth="user", tags=T,
       summary="Documento vigente que esta pessoa ainda não aceitou")
def pending(ctx: Ctx):
    kind = ctx.principal.org_kind if ctx.principal else None
    with ctx.tx(readonly=True) as c:
        return LEGAL.pending(c, user_id=ctx.user_id, org_kind=kind)


@route("GET", "/v1/legal/acceptances/mine", auth="user", tags=T,
       summary="O que esta pessoa aceitou, com versão e hash do texto")
def mine(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return LEGAL.mine(c, user_id=ctx.user_id)


@route("POST", "/v1/legal/acceptances", auth="user", body=AcceptIn, status=201, tags=T,
       summary="Registra aceite (recusado se o documento for minuta não aprovada)")
def accept(ctx: Ctx, body: AcceptIn):
    org = ctx.principal.org_id if ctx.principal else None
    with ctx.tx() as c:
        return LEGAL.accept(c, user_id=ctx.user_id, org_id=org, key=body.doc_key, ip=ctx.ip,
                            user_agent=ctx.request.headers.get("user-agent"), source=body.source)


@route("POST", "/v1/admin/legal/documents/{doc_id}/review", auth="admin", tags=T,
       summary="Marca a minuta como enviada para revisão jurídica")
def to_review(ctx: Ctx):
    with ctx.tx() as c:
        out = LEGAL.submit_for_review(c, doc_id=ctx.path["doc_id"])
        ctx.audit(c, "legal.submitted_for_review", "legal_document", ctx.path["doc_id"],
                  org_id=None)
    return out


@route("POST", "/v1/admin/legal/documents/{doc_id}/approve", auth="admin", body=ApproveIn, tags=T,
       summary="Aprova a versão, exigindo quem revisou e sob qual referência")
def approve(ctx: Ctx, body: ApproveIn):
    with ctx.tx() as c:
        return LEGAL.approve(c, doc_id=ctx.path["doc_id"], reviewed_by=body.reviewed_by,
                             review_reference=body.review_reference,
                             effective_from=body.effective_from)


@route("GET", "/v1/admin/legal/acceptances", auth="admin", query=AcceptanceQ, tags=T,
       summary="Prova de aceite: quem, quando, qual versão e qual hash")
def admin_acceptances(ctx: Ctx, q: AcceptanceQ):
    with ctx.tx(readonly=True) as c:
        return LEGAL.acceptances(c, doc_key=q.doc_key, limit=q.limit, offset=q.offset)
