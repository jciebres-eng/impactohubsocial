"""Busca incremental para formulários, com procedência em cada sugestão.

Cada chave é uma consulta escrita à mão: não existe busca genérica parametrizável, que seria um
caminho para ler o que não deve. E toda linha devolvida diz de onde veio.
"""
from __future__ import annotations

from ..http import Ctx, route
from ..impact import lookups as LK
from . import impact_schemas as S

T = ("lookups",)


@route("GET", "/v1/lookups", auth="user", tags=T,
       summary="As buscas disponíveis e as origens que cada uma pode devolver")
def catalog(ctx: Ctx):
    return LK.catalog()


@route("GET", "/v1/lookups/{lookup_key}", query=S.LookupQ, min_role="viewer", tags=T,
       summary="Sugestões com origem, fonte e data — nenhuma é aplicada sozinha")
def search(ctx: Ctx, q: S.LookupQ):
    with ctx.tx(readonly=True) as c:
        return LK.search(c, key=ctx.path["lookup_key"], q=q.q, limit=q.limit,
                         org_id=ctx.principal.org_id if ctx.principal else None)
