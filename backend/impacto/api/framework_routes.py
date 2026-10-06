"""Registro de frameworks de impacto, mapeamento de indicador e materialidade."""
from __future__ import annotations

from ..http import Ctx, route
from ..impact import frameworks as FW
from . import impact_schemas as S

T = ("frameworks",)


@route("GET", "/v1/frameworks", query=S.RegistryQ, auth="user", tags=T,
       summary="Referenciais reconhecidos, com o que a plataforma implementa e o que NÃO mapeia")
def registry(ctx: Ctx, q: S.RegistryQ):
    with ctx.tx(readonly=True) as c:
        return FW.registry(c, status=q.status)


@route("GET", "/v1/frameworks/mappings", query=S.MappingQ, min_role="viewer", tags=T,
       summary="Mapeamentos de indicador para referencial")
def mappings(ctx: Ctx, q: S.MappingQ):
    with ctx.tx(readonly=True) as c:
        return FW.mappings(c, framework_key=q.framework_key, indicator_id=q.indicator_id,
                           org_id=ctx.org_id if q.mine else None)


@route("POST", "/v1/frameworks/mappings", body=S.MappingIn, min_role="manager", status=201, tags=T,
       summary="Mapeia um indicador (a escada vai até 'audited'; 'certified' é recusado)")
def add_mapping(ctx: Ctx, body: S.MappingIn):
    with ctx.tx() as c:
        return FW.add_mapping(c, org_id=ctx.org_id, actor=ctx.user_id, **body.model_dump())


@route("DELETE", "/v1/frameworks/mappings/{mapping_id}", min_role="manager", tags=T,
       summary="Remove um mapeamento da própria organização")
def remove_mapping(ctx: Ctx):
    with ctx.tx() as c:
        return FW.remove_mapping(c, mapping_id=ctx.path["mapping_id"], org_id=ctx.org_id)


@route("GET", "/v1/frameworks/{framework_key}/coverage", min_role="viewer", tags=T,
       summary="Consigo relatar neste referencial? Responde com número, não com impressão")
def coverage(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return FW.coverage(c, org_id=ctx.org_id, framework_key=ctx.path["framework_key"])


@route("GET", "/v1/materiality/topics", auth="user", tags=T,
       summary="Temas candidatos a materialidade e as três lentes")
def topics(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return FW.topics(c)


@route("GET", "/v1/materiality", min_role="viewer", tags=T,
       summary="Avaliações de materialidade da organização")
def assessments(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return FW.assessments(c, org_id=ctx.org_id)


@route("POST", "/v1/materiality", body=S.MaterialityIn, min_role="manager", status=201, tags=T,
       summary="Abre uma avaliação (a lente e o limiar são declarados, não subentendidos)")
def open_assessment(ctx: Ctx, body: S.MaterialityIn):
    with ctx.tx() as c:
        return FW.open_assessment(c, org_id=ctx.org_id, actor=ctx.user_id, **body.model_dump())


@route("GET", "/v1/materiality/{assessment_id}", min_role="viewer", tags=T,
       summary="A matriz, com `is_material` DERIVADA do eixo e do limiar")
def assessment(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return FW.assessment(c, assessment_id=ctx.path["assessment_id"])


@route("PUT", "/v1/materiality/{assessment_id}/topics", body=S.MaterialityEntryIn,
       min_role="manager", tags=T, summary="Avalia um tema nos eixos permitidos pela lente")
def set_entry(ctx: Ctx, body: S.MaterialityEntryIn):
    with ctx.tx() as c:
        return FW.set_entry(c, assessment_id=ctx.path["assessment_id"], org_id=ctx.org_id,
                            **body.model_dump())


@route("POST", "/v1/materiality/{assessment_id}/publish", min_role="manager", tags=T,
       summary="Publica a avaliação (exige ao menos três temas avaliados)")
def publish(ctx: Ctx):
    with ctx.tx() as c:
        return FW.publish(c, assessment_id=ctx.path["assessment_id"], org_id=ctx.org_id)
