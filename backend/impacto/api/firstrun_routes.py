"""Primeiro acesso e retorno operacional por declarar contexto.

Estas duas rotas existem para que a interface não precise adivinhar duas coisas difíceis:
* o que mostrar quando uma área está legitimamente vazia (e qual é o próximo passo);
* o que a organização GANHOU ao preencher o formulário mais caro do produto.

A segunda rota é a resposta a uma assimetria real da plataforma: até aqui, declarar contexto de
necessidade, barreiras e denominador melhorava a avaliação de quem financia e não devolvia nada visível
para quem preencheu. O retorno é OPERACIONAL — cálculo que deixa de estar indisponível, sinal que deixa
de valer DESCONHECIDO, critério de selo que deixa de ser inalcançável. Nunca ranking.
"""
from __future__ import annotations

from ..core import firstrun as FR
from ..http import Ctx, not_found, route
from . import impact_schemas as S

T = ("firstrun",)


@route("GET", "/v1/firstrun", query=S.FirstRunQ, auth="user", min_role="viewer", tags=T,
       summary="Estado de primeiro acesso por área: o que é, por que está vazia, próximo passo e o que se ganha")
def state(ctx: Ctx, q: S.FirstRunQ):
    with ctx.tx(readonly=True) as c:
        if q.project_id and not c.scalar("SELECT 1 FROM projects WHERE id = $1", q.project_id):
            raise not_found("Projeto")
        return FR.state(c, org_id=ctx.org_id, project_id=q.project_id)


@route("GET", "/v1/projects/{project_id}/context-return", min_role="viewer", tags=T,
       summary="O que declarar contexto destravou, e o que cada peça que falta destravaria (sem ranking)")
def context_return(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        project_id = ctx.path["project_id"]
        if not c.scalar("SELECT 1 FROM projects WHERE id = $1", project_id):
            raise not_found("Projeto")
        return FR.context_return(c, project_id=project_id, org_id=ctx.org_id)
