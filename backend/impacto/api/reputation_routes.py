"""Reputação explicável: dimensões, linha do tempo e contestação.

Nenhuma rota devolve nota única, e nenhuma resposta daqui alimenta busca, match, recomendação ou
elegibilidade. Órgão público recebe perfil de governança e transparência; pessoa física não tem
perfil público.
"""
from __future__ import annotations

from ..http import Ctx, route
from ..impact import reputation as REP
from . import impact_schemas as S

T = ("reputation",)


@route("GET", "/v1/reputation/dimensions", auth="user", tags=T,
       summary="As dimensões, o que cada uma NÃO mede, e os sinais excluídos de propósito")
def dimensions(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return REP.dimensions(c)


@route("GET", "/v1/reputation/me", min_role="viewer", tags=T,
       summary="A reputação da própria organização, calculada na leitura")
def me(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return REP.me(c, org_id=ctx.org_id)


@route("GET", "/v1/organizations/{org_id}/reputation", auth="user", tags=T,
       summary="Perfil de reputação por dimensão (ou de governança, se for órgão público)")
def profile(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return REP.profile(c, org_id=ctx.path["org_id"],
                           viewer_org_id=ctx.principal.org_id if ctx.principal else None,
                           privileged=ctx.admin_mode)


@route("POST", "/v1/reputation/snapshots", min_role="manager", status=201, tags=T,
       summary="Congela a leitura atual na linha do tempo (append-only)")
def snapshot(ctx: Ctx):
    with ctx.tx() as c:
        out = REP.snapshot(c, org_id=ctx.org_id)
        ctx.audit(c, "reputation.snapshot", "organization", ctx.org_id,
                  {"recorded": out["recorded"]})
    return out


@route("GET", "/v1/organizations/{org_id}/reputation/timeline", query=S.TimelineQ, auth="user",
       tags=T, summary="Evolução registrada, com a versão do motor de cada ponto")
def timeline(ctx: Ctx, q: S.TimelineQ):
    with ctx.tx(readonly=True) as c:
        return REP.timeline(c, org_id=ctx.path["org_id"], dimension=q.dimension, limit=q.limit)


@route("POST", "/v1/reputation/disputes", body=S.DisputeIn, min_role="manager", status=201, tags=T,
       summary="Contesta uma dimensão; a contestação aberta aparece no próprio perfil")
def open_dispute(ctx: Ctx, body: S.DisputeIn):
    with ctx.tx() as c:
        out = REP.open_dispute(c, org_id=ctx.org_id, actor=ctx.user_id, **body.model_dump())
        ctx.audit(c, "reputation.dispute_opened", "organization", ctx.org_id,
                  {"dimension": body.dimension})
    return out


@route("GET", "/v1/reputation/disputes", query=S.DisputeQ, min_role="viewer", tags=T,
       summary="Contestações da organização, com a resolução quando houver")
def disputes(ctx: Ctx, q: S.DisputeQ):
    with ctx.tx(readonly=True) as c:
        scope = None if (q.all_orgs and ctx.admin_mode) else ctx.org_id
        return REP.disputes(c, org_id=scope, only_open=q.only_open)


@route("POST", "/v1/admin/reputation/disputes/{dispute_id}/resolution",
       body=S.DisputeResolutionIn, auth="admin", status=201, tags=T,
       summary="Resolve a contestação; corrigir produz ponto NOVO, nunca reescreve o antigo")
def resolve(ctx: Ctx, body: S.DisputeResolutionIn):
    with ctx.tx() as c:
        out = REP.resolve_dispute(c, dispute_id=ctx.path["dispute_id"], actor=ctx.user_id,
                                  **body.model_dump())
        ctx.audit(c, "reputation.dispute_resolved", "organization", out["org_id"],
                  {"outcome": body.outcome, "dimension": out["dimension"]}, org_id=out["org_id"])
    return out
