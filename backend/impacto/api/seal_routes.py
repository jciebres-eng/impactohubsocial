"""Selos: definição versionada, avaliação em SQL, concessão que o banco confere e revogação como fato.

Nenhuma rota aqui concede selo por decisão da aplicação: `POST /v1/admin/seals/awards` chama
`app_award_seal()`, que reavalia os critérios no banco e recusa quando algum não está satisfeito.
A aplicação não tem INSERT em `seal_awards`.
"""
from __future__ import annotations

from ..http import ApiError, Ctx, route
from ..impact import seals as SEAL
from . import impact_schemas as S

T = ("seals",)


@route("GET", "/v1/seals/rules", auth="user", tags=T,
       summary="Conjunto fechado de critérios implementados em SQL")
def rules(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return SEAL.rules(c)


@route("GET", "/v1/seals/definitions", query=S.SealDefinitionQ, auth="user", tags=T,
       summary="Definições com critérios, incluindo rascunhos (para ninguém ser surpreendido)")
def definitions(ctx: Ctx, q: S.SealDefinitionQ):
    with ctx.tx(readonly=True) as c:
        return SEAL.definitions(c, scope=q.scope, code=q.code, status=q.status)


@route("POST", "/v1/admin/seals/definitions", body=S.SealDefinitionIn, auth="admin", status=201,
       tags=T, summary="Cria definição (nasce RASCUNHO; rascunho não concede selo)")
def create_definition(ctx: Ctx, body: S.SealDefinitionIn):
    d = body.model_dump()
    with ctx.tx() as c:
        out = SEAL.create_definition(c, **{**d, "criteria": d["criteria"]})
        ctx.audit(c, "seal.definition_created", "seal_definition", out["id"],
                  {"code": out["code"], "version": out["version"]}, org_id=None)
    return out


@route("POST", "/v1/admin/seals/definitions/{definition_id}/publish", auth="admin", tags=T,
       summary="Publica; a versão anterior é aposentada e suas concessões ficam 'superadas'")
def publish(ctx: Ctx):
    with ctx.tx() as c:
        out = SEAL.publish_definition(c, definition_id=ctx.path["definition_id"])
        ctx.audit(c, "seal.definition_published", "seal_definition", out["id"],
                  {"code": out["code"], "version": out["version"]}, org_id=None)
    return out


@route("POST", "/v1/admin/seals/definitions/{definition_id}/retire", auth="admin", tags=T,
       summary="Aposenta a definição (não revoga as concessões)")
def retire(ctx: Ctx):
    with ctx.tx() as c:
        out = SEAL.retire_definition(c, definition_id=ctx.path["definition_id"])
        ctx.audit(c, "seal.definition_retired", "seal_definition", out["id"], org_id=None)
    return out


@route("POST", "/v1/seals/evaluate", body=S.SealEvaluateIn, min_role="viewer", tags=T,
       summary="A mesma avaliação que a concessão usa — mostra critério por critério")
def evaluate(ctx: Ctx, body: S.SealEvaluateIn):
    with ctx.tx(readonly=True) as c:
        return SEAL.evaluate(c, definition_id=body.definition_id, subject_id=body.subject_id)


@route("POST", "/v1/admin/seals/awards", body=S.SealEvaluateIn, auth="admin", status=201, tags=T,
       summary="Concede; o banco reavalia e RECUSA se faltar critério")
def award(ctx: Ctx, body: S.SealEvaluateIn):
    with ctx.tx() as c:
        out = SEAL.award(c, definition_id=body.definition_id, subject_id=body.subject_id)
        if out["awarded"]:
            ctx.audit(c, "seal.awarded", "seal_award", out["id"],
                      {"code": out["code"], "version": out["version"]}, org_id=out["org_id"])
    # A recusa é levantada FORA da transação, depois do COMMIT: dentro dela, a exceção desfaria o
    # registro da avaliação que explica a recusa.
    if not out["awarded"]:
        raise ApiError(422, "criteria_not_met", out["message"],
                       {"unmet": [d["rule_code"] for d in out["unmet"]],
                        "evaluation_id": out["evaluation_id"]})
    return out


@route("GET", "/v1/seals/awards", query=S.SealAwardQ, auth="user", tags=T,
       summary="Concessões com situação derivada (ativo, expirado, revogado, superado)")
def awards(ctx: Ctx, q: S.SealAwardQ):
    with ctx.tx(readonly=True) as c:
        return SEAL.awards(c, scope=q.scope, subject_id=q.subject_id,
                           org_id=ctx.org_id if q.mine else None, active_only=q.active_only)


@route("GET", "/v1/seals/awards/{award_id}", auth="user", tags=T,
       summary="O selo, o que ele atesta, o que NÃO atesta e a evidência de cada critério")
def get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return SEAL.get(c, award_id=ctx.path["award_id"])


@route("POST", "/v1/admin/seals/awards/{award_id}/revoke", body=S.SealRevokeIn, auth="admin",
       status=201, tags=T, summary="Revoga como fato novo, com motivo (não apaga a concessão)")
def revoke(ctx: Ctx, body: S.SealRevokeIn):
    with ctx.tx() as c:
        out = SEAL.revoke(c, award_id=ctx.path["award_id"], actor=ctx.user_id,
                          reason=body.reason, detail=body.detail)
        ctx.audit(c, "seal.revoked", "seal_award", ctx.path["award_id"],
                  {"reason": body.reason}, org_id=out["org_id"])
    return out


@route("GET", "/v1/seals/evaluations", min_role="viewer", tags=T,
       summary="Por que eu não recebi: avaliações da organização, inclusive as que não concederam")
def evaluations(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return SEAL.evaluations(c, org_id=ctx.org_id)
