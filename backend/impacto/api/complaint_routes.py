"""Denúncia e sua apuração (NÃO confundir com a Central de Relatórios, em report_routes.py) — com os quatro níveis separados por construção.

As rotas aqui respeitam duas assimetrias que não são detalhe:

* quem denuncia nunca é revelado a quem foi denunciado (nem na decisão);
* quem foi denunciado tem direito de ser ouvido ANTES da conclusão, e de recorrer DEPOIS dela.

E uma trava que não é desta camada: medida de moderação só pode citar denúncia com conclusão de
procedência, e quem recusa é o gatilho do banco (`enforcement_needs_substantiated_report`).
"""
from __future__ import annotations

from typing import Annotated

from pydantic import Field

from ..http import Ctx, page, route
from ..network import complaints as REP
from . import schemas as S

T = ("trust",)


class ReviewIn(S.In):
    question: Annotated[str, Field(min_length=20, max_length=4000)]


class RespondIn(S.In):
    body: Annotated[str, Field(min_length=20, max_length=4000)]
    document_id: S.Uuid | None = None


class ConcludeIn(S.In):
    finding: Annotated[str, Field(pattern="^(substantiated|unsubstantiated)$")]
    rationale: Annotated[str, Field(min_length=20, max_length=4000)]
    legal_referral: bool = False
    legal_referral_note: Annotated[str | None, Field(min_length=20, max_length=4000)] = None


class DismissIn(S.In):
    rationale: Annotated[str, Field(min_length=20, max_length=4000)]


class AppealIn(S.In):
    note: Annotated[str, Field(min_length=20, max_length=4000)]


class ReportQ(S.Pagination):
    status: Annotated[str | None, Field(pattern="^[a-z_]{4,30}$")] = None


# ============================================================ vocabulário
@route("GET", "/v1/reports/vocabulary", auth="user", tags=T,
       summary="Os quatro níveis (denúncia, suspeita, infração comprovada, consequência jurídica)")
def vocabulary(ctx: Ctx):
    return REP.vocabulary()


# ============================================================ quem foi denunciado
@route("GET", "/v1/conta/denuncias", min_role="admin", tags=T,
       summary="O que é imputado à sua organização — sem revelar quem denunciou")
def my_reports(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return REP.for_target(c, org_id=ctx.org_id)


@route("POST", "/v1/conta/denuncias/{report_id}/manifestacao", body=RespondIn, min_role="admin",
       status=201, tags=T, summary="Manifestação de quem foi denunciado (append-only)")
def respond(ctx: Ctx, body: RespondIn):
    with ctx.tx() as c:
        out = REP.respond(c, report_id=ctx.path["report_id"], org_id=ctx.org_id,
                          actor=ctx.user_id, body=body.body, document_id=body.document_id)
        ctx.audit(c, "report.responded", "report", ctx.path["report_id"], {})
    return out


@route("POST", "/v1/conta/denuncias/{report_id}/recurso", body=AppealIn, min_role="admin", tags=T,
       summary="Recurso da conclusão (a conclusão só muda por aqui)")
def appeal(ctx: Ctx, body: AppealIn):
    with ctx.tx() as c:
        out = REP.appeal(c, report_id=ctx.path["report_id"], org_id=ctx.org_id, note=body.note)
        ctx.audit(c, "report.appealed", "report", ctx.path["report_id"], {})
    return out


# ============================================================ apuração (plataforma)
@route("GET", "/v1/admin/reports/queue", auth="admin", query=ReportQ, tags=T,
       summary="Fila de apuração, com a distinção entre arquivada e não procedente")
def queue(ctx: Ctx, q: ReportQ):
    with ctx.system_tx() as c:
        out = REP.admin_view(c, status=q.status, limit=q.limit, offset=q.offset)
    return out


@route("GET", "/v1/admin/reports/{report_id}/responses", auth="admin", tags=T,
       summary="Manifestações de quem foi denunciado")
def report_responses(ctx: Ctx):
    with ctx.system_tx() as c:
        return page(REP.responses(c, report_id=ctx.path["report_id"]), 100, 0)


@route("POST", "/v1/admin/reports/{report_id}/review", auth="admin", tags=T,
       summary="Leva para análise e registra quem analisa (continua não sendo achado)")
def take(ctx: Ctx):
    with ctx.system_tx() as c:
        out = REP.take_for_review(c, report_id=ctx.path["report_id"], reviewer=ctx.user_id)
        ctx.audit(c, "report.under_review", "report", ctx.path["report_id"], {})
    return out


@route("POST", "/v1/admin/reports/{report_id}/request-response", body=ReviewIn, auth="admin", tags=T,
       summary="Abre o contraditório: chama quem foi denunciado a se manifestar")
def request_response(ctx: Ctx, body: ReviewIn):
    with ctx.system_tx() as c:
        out = REP.request_response(c, report_id=ctx.path["report_id"], reviewer=ctx.user_id,
                                   question=body.question)
        ctx.audit(c, "report.response_requested", "report", ctx.path["report_id"], {})
    return out


@route("POST", "/v1/admin/reports/{report_id}/conclude", body=ConcludeIn, auth="admin", tags=T,
       summary="Conclusão fundamentada. Só 'substantiated' autoriza medida")
def conclude(ctx: Ctx, body: ConcludeIn):
    with ctx.system_tx() as c:
        out = REP.conclude(c, report_id=ctx.path["report_id"], decided_by=ctx.user_id,
                           finding=body.finding, rationale=body.rationale,
                           legal_referral=body.legal_referral,
                           legal_referral_note=body.legal_referral_note)
        ctx.audit(c, "report.concluded", "report", ctx.path["report_id"],
                  {"finding": body.finding, "legal_referral": body.legal_referral})
    return out


@route("POST", "/v1/admin/reports/{report_id}/dismiss", body=DismissIn, auth="admin", tags=T,
       summary="Arquiva SEM análise de mérito — o que é diferente de concluir pela improcedência")
def dismiss(ctx: Ctx, body: DismissIn):
    with ctx.system_tx() as c:
        out = REP.dismiss(c, report_id=ctx.path["report_id"], decided_by=ctx.user_id,
                          rationale=body.rationale)
        ctx.audit(c, "report.dismissed", "report", ctx.path["report_id"], {})
    return out
