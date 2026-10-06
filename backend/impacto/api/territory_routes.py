"""Catálogo territorial: busca, perfil com fonte e o que não foi medido."""
from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import Field

from ..http import Ctx, route
from ..impact import territory as TERR
from . import impact_schemas as S
from .impact_schemas import In, SourceName, Url
from .schemas import Uuid


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
    # v0.20.0: liga o número ao conjunto de dados de onde ele saiu. Opcional de propósito — um
    # indicador declarado à mão continua válido, e exigir procedência de catálogo em quem não a tem
    # só produziria identificador inventado.
    dataset_id: Uuid | None = None


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


# ============================================================ procedência de dado externo (v0.20.0)
class DatasetIn(S.In):
    """Registro de um conjunto de dados externo. Tudo o que descreve de onde o número veio."""

    key: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_.-]{2,80}$")]
    version: Annotated[str, Field(min_length=1, max_length=60)]
    publisher: Annotated[str, Field(min_length=2, max_length=200)]
    dataset: Annotated[str, Field(min_length=2, max_length=300)]
    url: Annotated[str | None, Field(pattern=r"^https?://")] = None
    published_at: date | None = None
    retrieved_at: date
    geographic_scope: Annotated[str, Field(
        pattern="^(international|country|region|state|municipality|mixed)$")]
    methodology: Annotated[str | None, Field(min_length=10, max_length=4000)] = None
    license: Annotated[str, Field(min_length=2, max_length=200)]
    license_url: Annotated[str | None, Field(pattern=r"^https?://")] = None
    file_name: Annotated[str | None, Field(max_length=300)] = None
    file_sha256: Annotated[str | None, Field(pattern="^[0-9a-f]{64}$")] = None
    rows_loaded: Annotated[int | None, Field(ge=0)] = None
    stale_after_months: Annotated[int | None, Field(ge=1, le=600)] = None
    stale_note: Annotated[str | None, Field(min_length=10, max_length=1000)] = None


@route("GET", "/v1/datasets", auth="user", tags=T,
       summary="Conjuntos de dados externos carregados: publicador, licença, datas e hash do arquivo")
def datasets(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query(
            "SELECT d.id::text AS id, d.key, d.version, d.publisher, d.dataset, d.url,"
            " d.published_at, d.retrieved_at, d.geographic_scope, d.license, d.license_url,"
            " d.file_name, d.file_sha256, d.rows_loaded, d.stale_after_months, d.stale_note,"
            " d.created_at,"
            " (SELECT count(*) FROM territory_indicators ti WHERE ti.dataset_id = d.id) AS indicators,"
            " (SELECT count(*) FROM equity_denominators ed WHERE ed.dataset_id = d.id) AS denominators,"
            " (SELECT count(*) FROM ods_targets ot WHERE ot.dataset_id = d.id) AS ods_targets"
            " FROM external_datasets d ORDER BY d.retrieved_at DESC, d.key")
    return {
        "items": rows,
        "note": ("Vazio significa que nenhum conjunto de dados externo foi carregado — e é o estado "
                 "verdadeiro hoje. Dado de terceiro sem licença registrada é problema jurídico, não "
                 "detalhe: por isso a licença é obrigatória no registro."),
        "freshness_rule": ("`stale_after_months` é DECLARAÇÃO DE QUEM CARREGA. Sem ela, a plataforma "
                           "responde 'não declarado' — nunca 'atual'."),
    }


@route("POST", "/v1/admin/datasets", body=DatasetIn, auth="admin", status=201, tags=T,
       summary="Registra a procedência de um conjunto de dados externo (licença obrigatória)")
def register_dataset(ctx: Ctx, body: DatasetIn):
    with ctx.tx() as c:
        row = c.one(
            "INSERT INTO external_datasets(key, version, publisher, dataset, url, published_at,"
            " retrieved_at, geographic_scope, methodology, license, license_url, file_name,"
            " file_sha256, rows_loaded, stale_after_months, stale_note, loaded_by)"
            " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)"
            " RETURNING id::text AS id, key, version, publisher, retrieved_at",
            body.key, body.version, body.publisher, body.dataset, body.url, body.published_at,
            body.retrieved_at, body.geographic_scope, body.methodology, body.license,
            body.license_url, body.file_name, body.file_sha256, body.rows_loaded,
            body.stale_after_months, body.stale_note, ctx.user_id)
        ctx.audit(c, "dataset.registered", "dataset", row["id"],
                  {"key": body.key, "version": body.version, "publisher": body.publisher})
    return row
