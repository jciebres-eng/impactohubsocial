"""Mapas: localização configurável por projeto e agregações. Coordenadas exatas nunca saem do banco para quem não é dono."""
from __future__ import annotations

from ..http import ApiError, Ctx, not_found, route
from ..services import geo
from . import schemas as S

T = ("map",)


@route("PUT", "/v1/projects/{project_id}/location", body=S.LocationIn, kinds=("osc",), min_role="member", tags=T,
       summary="Define a precisão pública da localização (exata, aproximada, bairro, município, região) e as coordenadas privadas")
def set_location(ctx: Ctx, body: S.LocationIn):
    if body.precision in ("exact", "approximate", "neighborhood") and (body.lat is None or body.lng is None):
        raise ApiError(422, "coordinates_required", "Esta precisão exige latitude e longitude")
    with ctx.tx() as c:
        p = c.one("SELECT id::text AS id FROM projects WHERE id = $1 AND org_id = $2", ctx.path["project_id"], ctx.org_id)
        if not p:
            raise not_found("Projeto")
        c.run("UPDATE projects SET location_precision = $2, lat = $3::numeric, lng = $4::numeric WHERE id = $1", p["id"], body.precision, body.lat, body.lng)
        ctx.audit(c, "project.location_set", "project", p["id"], {"precision": body.precision})
    return {"id": p["id"], "public": geo.public_point(p["id"], body.lat, body.lng, body.precision), "precision": body.precision}


@route("GET", "/v1/map/projects", min_role="viewer", tags=T,
       summary="Projetos publicados no mapa: pontos só conforme a precisão escolhida + contagem por UF (sem mapa-base externo)")
def map_projects(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, title, territory, causes, status, lat::float AS lat, lng::float AS lng, location_precision FROM projects"
                       " WHERE visibility = 'published' ORDER BY id LIMIT 2000")
    points, by_uf = [], {}
    for r in rows:
        uf = geo.uf_of(r["territory"]) or "—"
        by_uf[uf] = by_uf.get(uf, 0) + 1
        pt = geo.public_point(r["id"], r["lat"], r["lng"], r["location_precision"])
        if pt:
            points.append({"id": r["id"], "title": r["title"], "causes": r["causes"], "status": r["status"], **pt})
    return {"points": points, "by_uf": [{"uf": k, "projects": v} for k, v in sorted(by_uf.items())], "total": len(rows),
            "note": "Sem mapa-base: tiles exigem provedor externo (decisão pendente). Localização exata só aparece se a OSC escolher essa precisão."}
