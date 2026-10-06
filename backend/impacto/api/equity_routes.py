"""Contexto de equidade: barreira, denominador com fonte, normalização rotulada e comparação."""
from __future__ import annotations

from ..http import Ctx, route
from ..impact import equity as EQ
from . import impact_schemas as S

T = ("equidade",)


@route("GET", "/v1/equity/catalog", auth="user", tags=T,
       summary="Barreiras, escadas de prova, tipos de denominador e métodos de normalização")
def catalog(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return EQ.catalog(c)


@route("GET", "/v1/projects/{project_id}/equity", min_role="viewer", tags=T,
       summary="O contexto declarado do projeto, as barreiras e o que é normalizável")
def project_equity(ctx: Ctx):
    pid = ctx.path["project_id"]
    with ctx.tx(readonly=True) as c:
        return {
            "project_id": pid,
            "context": EQ.context(c, project_id=pid),
            "barriers": EQ.barriers(c, project_id=pid),
            "normalization": EQ.normalize(c, project_id=pid),
            "denominators": EQ.denominators(c, project_id=pid)["items"],
        }


@route("PUT", "/v1/projects/{project_id}/equity/context", body=S.EquityContextIn,
       min_role="manager", tags=T,
       summary="Declara necessidade, adicionalidade e cenário-base (com a escada de prova)")
def set_context(ctx: Ctx, body: S.EquityContextIn):
    with ctx.tx() as c:
        return EQ.set_context(c, project_id=ctx.path["project_id"], org_id=ctx.org_id,
                              actor=ctx.user_id, **body.model_dump())


@route("POST", "/v1/projects/{project_id}/equity/barriers", body=S.BarrierIn, min_role="manager",
       status=201, tags=T,
       summary="Declara uma barreira do contexto ('evidenciada' exige evidência registrada)")
def add_barrier(ctx: Ctx, body: S.BarrierIn):
    with ctx.tx() as c:
        return EQ.add_barrier(c, project_id=ctx.path["project_id"], org_id=ctx.org_id,
                              actor=ctx.user_id, **body.model_dump())


@route("DELETE", "/v1/projects/{project_id}/equity/barriers/{barrier_code}", min_role="manager",
       tags=T, summary="Desfaz a declaração de uma barreira")
def remove_barrier(ctx: Ctx):
    with ctx.tx() as c:
        return EQ.remove_barrier(c, project_id=ctx.path["project_id"], org_id=ctx.org_id,
                                 barrier_code=ctx.path["barrier_code"])


@route("GET", "/v1/projects/{project_id}/equity/normalization", query=S.NormalizeQ,
       min_role="viewer", tags=T,
       summary="Normalização rotulada; método sem denominador com fonte vem indisponível")
def normalization(ctx: Ctx, q: S.NormalizeQ):
    with ctx.tx(readonly=True) as c:
        return EQ.normalize(c, project_id=ctx.path["project_id"], indicator_id=q.indicator_id)


@route("POST", "/v1/projects/{project_id}/equity/assessments", body=S.AssessIn,
       min_role="manager", status=201, tags=T,
       summary="Grava o retrato do contexto (append-only; não produz nota de equidade)")
def assess(ctx: Ctx, body: S.AssessIn):
    with ctx.tx() as c:
        return EQ.assess(c, project_id=ctx.path["project_id"], org_id=ctx.org_id,
                         actor=ctx.user_id, indicator_id=body.indicator_id)


@route("GET", "/v1/projects/{project_id}/equity/assessments", query=S.HistoryQ, min_role="viewer",
       tags=T, summary="Histórico dos retratos de contexto do projeto")
def assessments(ctx: Ctx, q: S.HistoryQ):
    with ctx.tx(readonly=True) as c:
        return EQ.history(c, project_id=ctx.path["project_id"], limit=q.limit)


@route("GET", "/v1/equity/denominators", query=S.DenominatorQ, min_role="viewer", tags=T,
       summary="Denominadores vigentes, com fonte e data de cada um")
def denominators(ctx: Ctx, q: S.DenominatorQ):
    with ctx.tx(readonly=True) as c:
        return EQ.denominators(c, project_id=q.project_id, program_id=q.program_id,
                               territory=q.territory, include_closed=q.include_closed)


@route("POST", "/v1/equity/denominators", body=S.DenominatorIn, min_role="manager", status=201,
       tags=T, summary="Declara denominador do projeto ou do programa (fonte e método obrigatórios)")
def set_denominator(ctx: Ctx, body: S.DenominatorIn):
    with ctx.tx() as c:
        return EQ.set_denominator(c, org_id=ctx.org_id, actor=ctx.user_id, **body.model_dump())


@route("POST", "/v1/admin/equity/denominators", body=S.TerritoryDenominatorIn, auth="admin",
       status=201, tags=T,
       summary="Declara denominador de TERRITÓRIO (bem comum: só a administração publica)")
def set_territory_denominator(ctx: Ctx, body: S.TerritoryDenominatorIn):
    with ctx.tx() as c:
        return EQ.set_denominator(c, scope="territory", actor=ctx.user_id, **body.model_dump())


@route("POST", "/v1/equity/compare", body=S.CompareIn, min_role="viewer", tags=T,
       summary="Compara contextos — e devolve comparable=false com o motivo quando não há base")
def compare(ctx: Ctx, body: S.CompareIn):
    with ctx.tx(readonly=True) as c:
        return EQ.compare(c, project_ids=body.project_ids, indicator_code=body.indicator_code)
