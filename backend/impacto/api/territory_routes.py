"""Catálogo territorial: busca, perfil com fonte e o que não foi medido."""
from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field

from ..http import Ctx, route
from ..impact import territory as TERR
from .impact_schemas import In, SourceName, Url


class SearchQ(In):
    q: Annotated[str, Field(min_length=1, max_length=120)]
    kind: Annotated[str, Field(pattern="^(international|country|region|state|municipality)$")] | None = None
    uf: Annotated[str, Field(pattern="^[A-Za-z]{2}$")] | None = None
    limit: Annotated[int, Field(ge=1, le=50)] = 20


class TerritoryIndicatorIn(In):
    territory: Annotated[str, Field(pattern=r"^(INT|BR-R[1-5]|[A-Z]{2}(-[A-Z]{2}(-[0-9]{7})?)?)$")]
    code: Annotated[str, Field(pattern="^[a-z][a-z0-9_]{3,50}$")]
    value: float
    reference_date: date
    source_name: SourceName
    source_url: Url | None = None
    source_date: date
    method_note: Annotated[str, Field(max_length=2000)] | None = None


T = ("território",)


@route("GET", "/v1/territories/search", query=SearchQ, auth="user", tags=T,
       summary="Busca território por nome ou código, para preenchimento incremental")
def search(ctx: Ctx, q: SearchQ):
    with ctx.tx(readonly=True) as c:
        return TERR.search(c, q=q.q, kind=q.kind, uf=q.uf, limit=q.limit)


@route("GET", "/v1/territories/catalog-status", auth="user", tags=T,
       summary="Quão completo está o catálogo — e o que depende de carga oficial")
def catalog_status(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return TERR.catalog_status(c)


@route("GET", "/v1/territories/definitions", auth="user", tags=T,
       summary="O que a plataforma pretende medir por determinante social")
def definitions(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return TERR.definitions(c)


@route("GET", "/v1/territories/{code}", auth="user", tags=T,
       summary="Perfil do território: cadeia, indicadores com fonte e o que NÃO foi medido")
def profile(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return TERR.profile(c, code=ctx.path["code"])


@route("POST", "/v1/admin/territory-indicators", body=TerritoryIndicatorIn, auth="admin",
       status=201, tags=T,
       summary="Publica um indicador territorial (fonte e data de referência obrigatórias)")
def set_indicator(ctx: Ctx, body: TerritoryIndicatorIn):
    with ctx.tx() as c:
        return TERR.set_indicator(c, actor=ctx.user_id, **body.model_dump())
