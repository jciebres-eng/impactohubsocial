"""v0.26.0 — Torres de controle do financiador e do governo, e o estado "Projeto IMPACTO Ready".

Só leitura. A torre responde à cadeia "meu capital → onde está → ... → o que preciso decidir" com os
registros que já existem; a decisão é tomada na tela do registro, nunca aqui.
"""
from __future__ import annotations

from ..http import Ctx, not_found, route
from ..network import control_tower as CT
from . import schemas as S


class TowerQ(S.In):
    territory: S.Territory | None = None


@route("GET", "/v1/control-tower/funder", kinds=("company", "individual"), min_role="viewer", tags=("torre",),
       summary="Torre do financiador: meu capital → onde está → para quem → finalidade → executado → evidência → mudou → atrasos → riscos → decisões")
def funder_tower(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return CT.funder(c, org_id=ctx.org_id)


@route("GET", "/v1/control-tower/government", kinds=("government", "platform"), min_role="viewer", query=TowerQ, tags=("torre",),
       summary="Torre territorial do governo: território → programas → editais → OSCs → projetos → recursos → indicadores declarados × validados → atrasos → lacunas")
def government_tower(ctx: Ctx, q: TowerQ):
    with ctx.tx(readonly=True) as c:
        return CT.government(c, org_id=ctx.org_id, territory=q.territory)


@route("GET", "/v1/projects/{project_id}/ready", min_role="viewer", tags=("torre",),
       summary="Estado verificável 'Projeto IMPACTO Ready': critérios com a evidência (tabela e contagem) de cada um; desconhecido ≠ zero")
def project_ready(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        out = CT.ready(c, ctx.path["project_id"])
    if out is None:
        raise not_found("Projeto")
    return out
