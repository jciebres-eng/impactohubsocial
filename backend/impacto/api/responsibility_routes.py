"""Responsabilidade designada e decisões registradas — separado de assinatura."""
from __future__ import annotations

from ..http import Ctx, route
from ..impact import responsibility as RESP
from . import impact_schemas as S

T = ("responsibility",)


@route("GET", "/v1/responsibility/roles", auth="user", tags=T,
       summary="Papéis, o que cada um NÃO responde, e os tipos de decisão (com quatro-olhos)")
def roles(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return RESP.roles(c)


@route("POST", "/v1/responsibility/assignments", body=S.AssignmentIn, min_role="manager",
       status=201, tags=T, summary="Designa quem responde por um escopo (um papel, um responsável)")
def assign(ctx: Ctx, body: S.AssignmentIn):
    with ctx.tx() as c:
        out = RESP.assign(c, org_id=ctx.org_id, actor=ctx.user_id, **body.model_dump())
        ctx.audit(c, "responsibility.assigned", body.scope, body.subject_id,
                  {"role": body.role_code, "assignment_id": out["id"]})
    return out


@route("POST", "/v1/responsibility/assignments/{assignment_id}/end", body=S.AssignmentEndIn,
       min_role="manager", tags=T,
       summary="Encerra a designação com motivo (responsabilidade não se transfere em silêncio)")
def end(ctx: Ctx, body: S.AssignmentEndIn):
    with ctx.tx() as c:
        out = RESP.end(c, assignment_id=ctx.path["assignment_id"], org_id=ctx.org_id,
                       reason=body.reason, ended_on=body.ended_on)
        ctx.audit(c, "responsibility.ended", "assignment", ctx.path["assignment_id"],
                  {"role": out["role_code"]})
    return out


@route("GET", "/v1/responsibility/current", query=S.ResponsibleQ, auth="user", tags=T,
       summary="Quem responde agora, e quais papéis estão SEM responsável")
def current(ctx: Ctx, q: S.ResponsibleQ):
    with ctx.tx(readonly=True) as c:
        return RESP.current(c, scope=q.scope, subject_id=q.subject_id)


@route("GET", "/v1/responsibility/history", query=S.ResponsibleQ, min_role="viewer", tags=T,
       summary="Histórico completo de designações do escopo, com períodos e motivos")
def history(ctx: Ctx, q: S.ResponsibleQ):
    with ctx.tx(readonly=True) as c:
        return RESP.history(c, scope=q.scope, subject_id=q.subject_id, org_id=ctx.org_id)


@route("GET", "/v1/responsibility/mine", auth="user", tags=T,
       summary="O que eu respondo hoje e o que respondi antes")
def mine(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return RESP.mine(c, user_id=ctx.user_id)


@route("POST", "/v1/responsibility/decisions", body=S.DecisionIn, min_role="manager", status=201,
       tags=T, summary="Registra a decisão; sobre documento, aponta para a VERSÃO")
def decide(ctx: Ctx, body: S.DecisionIn):
    with ctx.tx() as c:
        out = RESP.decide(c, org_id=ctx.org_id, **body.model_dump())
        ctx.audit(c, "responsibility.decision", "assignment", body.assignment_id,
                  {"kind": body.kind, "decision_id": out["id"],
                   "four_eyes": body.second_assignment_id is not None})
    return out


@route("GET", "/v1/responsibility/decisions", query=S.DecisionQ, min_role="viewer", tags=T,
       summary="Decisões registradas, com papel, pessoa e segunda confirmação quando exigida")
def decisions(ctx: Ctx, q: S.DecisionQ):
    with ctx.tx(readonly=True) as c:
        return RESP.decisions(c, scope=q.scope, subject_id=q.subject_id,
                              assignment_id=q.assignment_id, limit=q.limit)
