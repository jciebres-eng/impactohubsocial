"""Central de relatórios — gera, exporta (CSV) e imprime (HTML da interface) relatórios com linguagem controlada."""
from __future__ import annotations

from starlette.responses import Response

from ..http import ApiError, Ctx, route
from ..services import reports
from . import schemas as S

T = ("reports",)


class ReportQ(S.In):
    project_id: S.Uuid | None = None
    format: str = "json"


@route("GET", "/v1/report-center", min_role="viewer", tags=T, summary="Tipos de relatório disponíveis para o tipo da organização")
def report_types(ctx: Ctx):
    return {"items": reports.kinds_for(ctx.principal.org_kind), "wording": reports.WORDING}


@route("GET", "/v1/report-center/{rtype}", query=ReportQ, min_role="viewer", feature=None, tags=T, raw=True,
       summary="Gera o relatório (JSON ou CSV). Escopo: projetos próprios (OSC) ou com aporte (financiador)")
def build_report(ctx: Ctx, q: ReportQ):
    if q.format not in ("json", "csv"):
        raise ApiError(422, "validation_error", "format deve ser json ou csv")
    with ctx.tx(readonly=True) as c:
        rep = reports.build(c, ctx.path["rtype"], ctx.principal.org_kind, ctx.org_id, q.project_id)
    with ctx.tx() as c:
        ctx.audit(c, "report.generated", "report", None, {"type": rep["type"], "format": q.format})
    if q.format == "csv":
        return Response(reports.to_csv(rep), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{rep["type"]}.csv"', "Cache-Control": "no-store"})
    from ..http import json_response
    return json_response(rep)
