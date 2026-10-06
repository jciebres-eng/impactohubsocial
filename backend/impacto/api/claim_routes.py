"""Integridade de alegação: declarar, verificar (determinístico) e revisar (humano, de outra org)."""
from __future__ import annotations

from ..http import Ctx, route
from ..impact import claims as CL
from . import impact_schemas as S

T = ("claims",)


@route("GET", "/v1/claims/rules", auth="user", tags=T,
       summary="As regras de integridade e os léxicos usados — quem é marcado tem direito de saber")
def rules(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return CL.rules(c)


@route("POST", "/v1/claims", body=S.ClaimIn, min_role="manager", status=201, tags=T,
       summary="Declara a alegação no texto exato em que será publicada")
def declare(ctx: Ctx, body: S.ClaimIn):
    with ctx.tx() as c:
        out = CL.declare(c, org_id=ctx.org_id, actor=ctx.user_id, **body.model_dump())
        ctx.audit(c, "claim.declared", "claim", out["id"],
                  {"subject_type": body.subject_type, "claim_kind": body.claim_kind})
    return out


@route("GET", "/v1/claims", query=S.ClaimQ, min_role="viewer", tags=T,
       summary="Alegações com a situação DERIVADA da última verificação")
def listing(ctx: Ctx, q: S.ClaimQ):
    with ctx.tx(readonly=True) as c:
        return CL.listing(c, org_id=ctx.org_id if q.mine else None, subject_type=q.subject_type,
                          subject_id=q.subject_id, limit=q.limit, offset=q.offset)


@route("GET", "/v1/claims/{claim_id}", min_role="viewer", tags=T,
       summary="A alegação, a situação derivada, todas as rodadas de verificação e as revisões")
def get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return CL.get(c, claim_id=ctx.path["claim_id"])


@route("POST", "/v1/claims/{claim_id}/check", min_role="manager", status=201, tags=T,
       summary="Roda as regras determinísticas e grava uma nova rodada (nunca apaga a anterior)")
def check(ctx: Ctx):
    with ctx.tx() as c:
        out = CL.check(c, claim_id=ctx.path["claim_id"])
        ctx.audit(c, "claim.checked", "claim", ctx.path["claim_id"],
                  {"status": out["status"], "round": out["check_round"],
                   "engine_version": out["engine_version"]})
    return out


@route("POST", "/v1/claims/{claim_id}/withdraw", body=S.ClaimWithdrawIn, min_role="manager", tags=T,
       summary="Retira a alegação (o histórico de verificação permanece legível)")
def withdraw(ctx: Ctx, body: S.ClaimWithdrawIn):
    with ctx.tx() as c:
        out = CL.withdraw(c, claim_id=ctx.path["claim_id"], org_id=ctx.org_id, reason=body.reason)
        ctx.audit(c, "claim.withdrawn", "claim", ctx.path["claim_id"])
    return out


@route("GET", "/v1/claims/review-requests", min_role="viewer", tags=T,
       summary="Convites de revisão recebidos pela organização — a fila de quem é convidado")
def review_requests(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return CL.review_requests(c, org_id=ctx.org_id)


@route("POST", "/v1/claims/{claim_id}/review-requests", body=S.ClaimReviewRequestIn,
       min_role="manager", status=201, tags=T,
       summary="Convida uma organização nomeada a revisar a rodada (é o convite que abre a leitura)")
def request_review(ctx: Ctx, body: S.ClaimReviewRequestIn):
    with ctx.tx() as c:
        out = CL.request_review(c, claim_id=ctx.path["claim_id"], org_id=ctx.org_id,
                                reviewer_org_id=body.reviewer_org_id, note=body.note,
                                actor=ctx.user_id)
        ctx.audit(c, "claim.review_requested", "claim", ctx.path["claim_id"],
                  {"reviewer_org_id": body.reviewer_org_id, "round": out["check_round"]})
    return out


@route("POST", "/v1/claims/{claim_id}/review", body=S.ClaimReviewIn, min_role="manager", status=201,
       tags=T,
       summary="Revisão humana por organização DIFERENTE; aceitar não apaga a marca, qualifica")
def review(ctx: Ctx, body: S.ClaimReviewIn):
    with ctx.tx() as c:
        out = CL.review(c, claim_id=ctx.path["claim_id"], reviewer_org_id=ctx.org_id,
                        reviewer_user_id=ctx.user_id, decision=body.decision, note=body.note)
        ctx.audit(c, "claim.reviewed", "claim", ctx.path["claim_id"],
                  {"decision": body.decision})
    return out
