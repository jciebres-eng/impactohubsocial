"""Convênios (entrada por código), licenças administrativas e visão de acesso por organização.
Toda intervenção administrativa exige MOTIVO e gera auditoria. O cliente nunca define pacote, valor ou direito.
v0.27.0 (ADR-341): saíram o trial administrativo e o preço de plano — não existe assinatura."""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from ..http import ApiError, Ctx, not_found, route
from ..services import monetization as mon
from . import schemas as S
from .billing_routes import ALPHABET, code_hash

T = ("billing",)


def A(method, path, **kw):
    return route(method, path, auth="admin", tags=("admin", "billing"), **kw)


# ------------------------------------------------------------------------------------------------ organização: entrar em convênio
@route("POST", "/v1/agreements/join", body=S.AgreementJoinIn, min_role="owner", rate=("agreement_ip", 10, 3600), tags=T,
       summary="Entrar em um convênio com o código (vagas, validade e — se houver — domínio de e-mail verificado). Resposta genérica para códigos inválidos.")
def join(ctx: Ctx, body: S.AgreementJoinIn):
    from ..services.ratelimit import hit
    hit(ctx, "agreement_org", ctx.org_id, 10, 3600)
    p = ctx.principal
    with ctx.system_tx() as c:
        res = mon.join_agreement(c, code_hash=code_hash(ctx.settings.voucher_hmac_key, "agr:" + body.code), org_id=ctx.org_id, user_id=ctx.user_id,
                                 user_email=p.email, email_verified=p.email_verified, org_kind=p.org_kind)
        ctx.audit(c, "agreement.joined", "agreement", res["agreement_id"], {"plan": res["plan_key"]})
    return {"joined": True, **res, "note": "Licença do convênio aplicada. Convênios não alteram compatibilidade, ranking ou posição no diretório."}


# ------------------------------------------------------------------------------------------------ administração: visão de cobrança
@A("GET", "/v1/admin/billing/organizations/{org_id}", permission="billing.read", summary="Visão de suporte: acesso, licenças, convênios, contratos, vouchers e faturas da organização")
def org_billing(ctx: Ctx):
    oid = ctx.path["org_id"]
    with ctx.tx(readonly=True) as c:
        org = c.one("SELECT id::text AS id, kind, legal_name FROM organizations WHERE id = $1", oid)
        if not org:
            raise not_found("Organização")
        ent = __import__("impacto.services.entitlements", fromlist=["effective"]).effective(c, oid, org["kind"])
        from ..services import free_period as FP
        return {"organization": org, "entitlements": ent,
                "access": FP.state(c, oid),
                "contracts": c.query("SELECT a.id::text AS id, a.plan_key, a.billing_frequency, a.payment_method, a.consent_status, a.accepted_at, a.revoked_at,"
                                     " o.amount_cents, o.currency, o.installments, o.contract_ref FROM offer_acceptances a JOIN commercial_offers o ON o.id = a.offer_id"
                                     " WHERE a.org_id = $1 ORDER BY a.accepted_at DESC", oid),
                "grants": c.query("SELECT id::text AS id, plan_key, feature_key, source, reason, starts_at, ends_at, revoked_at, revoke_reason FROM entitlement_grants WHERE org_id = $1 ORDER BY created_at DESC", oid),
                "voucher_redemptions": c.query("SELECT r.status, r.redeemed_at, v.type, v.code_hint FROM voucher_redemptions r JOIN vouchers v ON v.id = r.voucher_id WHERE r.org_id = $1 ORDER BY r.redeemed_at DESC", oid),
                "agreements": c.query("SELECT a.id::text AS id, a.name, m.status, m.joined_at FROM agreement_members m JOIN agreements a ON a.id = m.agreement_id WHERE m.org_id = $1", oid),
                "invoices": c.query("SELECT id::text AS id, amount_cents, status, paid_at, created_at FROM invoices WHERE org_id = $1 ORDER BY created_at DESC LIMIT 50", oid)}


class RevokeIn(S.In):
    reason: Annotated[str, Field(min_length=5, max_length=500)]


@A("POST", "/v1/admin/grants/{grant_id}/revoke", body=RevokeIn, summary="Revoga uma licença/grant (motivo obrigatório); o histórico é preservado")
def revoke_grant(ctx: Ctx, body: RevokeIn):
    with ctx.tx() as c:
        g = c.one("SELECT id::text AS id, org_id::text AS org_id, revoked_at FROM entitlement_grants WHERE id = $1 FOR UPDATE", ctx.path["grant_id"])
        if not g:
            raise not_found("Licença")
        if g["revoked_at"]:
            raise ApiError(409, "already_revoked", "Licença já revogada")
        c.run("UPDATE entitlement_grants SET revoked_at = now(), revoked_by = $2, revoke_reason = $3 WHERE id = $1", g["id"], ctx.user_id, body.reason)
        ctx.audit(c, "billing.grant_revoked", "grant", g["id"], {"reason": body.reason}, org_id=g["org_id"])
    return {"id": g["id"], "revoked": True}


# ------------------------------------------------------------------------------------------------ administração: convênios
class AgreementIn(S.In):
    name: Annotated[str, Field(min_length=2, max_length=200)]
    kind: Literal["convention", "gov", "partner"]
    plan_key: S.Slug | None = None
    grant_days: Annotated[int | None, Field(ge=1, le=3650)] = None
    discount_percent: Annotated[int | None, Field(ge=1, le=100)] = None
    seats: Annotated[int, Field(ge=1, le=100000)]
    email_domains: list[Annotated[str, Field(pattern=r"^[a-z0-9.-]+\.[a-z]{2,}$")]] = Field(default_factory=list, max_length=20)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    contract_ref: Annotated[str | None, Field(max_length=200)] = None


@A("POST", "/v1/admin/agreements", body=AgreementIn, status=201,
   summary="Cria convênio (rascunho). O código é exibido UMA vez; a ativação exige outro administrador.")
def create_agreement(ctx: Ctx, body: AgreementIn):
    if not body.plan_key:
        raise ApiError(422, "validation_error", "Informe plan_key (licença). Desconto de convênio foi aposentado: não há assinatura para descontar (ADR-341)")
    if body.discount_percent:
        raise ApiError(422, "discount_retired", "Desconto percentual de convênio foi aposentado: não existe assinatura (ADR-341)")
    raw = "".join(secrets.choice(ALPHABET) for _ in range(12))
    code = f"{raw[:4]}-{raw[4:8]}-{raw[8:]}"
    with ctx.tx() as c:
        if body.plan_key and not c.one("SELECT 1 FROM plans WHERE plan_key = $1 AND active", body.plan_key):
            raise not_found("Plano")
        aid = c.scalar("INSERT INTO agreements(name, kind, plan_key, grant_days, discount_percent, seats, email_domains, code_hash, code_hint, valid_from, valid_until, contract_ref, created_by)"
                       " VALUES ($1,$2,$3,$4::int,$5::smallint,$6,$7::text[],$8,$9,$10::timestamptz,$11::timestamptz,$12,$13) RETURNING id::text",
                       body.name, body.kind, body.plan_key, body.grant_days, body.discount_percent, body.seats, body.email_domains,
                       code_hash(ctx.settings.voucher_hmac_key, "agr:" + code), raw[-4:], body.valid_from, body.valid_until, body.contract_ref, ctx.user_id)
        ctx.audit(c, "agreement.created", "agreement", aid, {"name": body.name, "kind": body.kind, "plan": body.plan_key, "seats": body.seats}, org_id=None)
    return {"id": aid, "status": "draft", "code": code, "warning": "Guarde o código agora: ele não poderá ser exibido novamente."}


@A("GET", "/v1/admin/agreements", permission="billing.read", summary="Lista convênios (sem o código)")
def list_agreements(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, name, kind, status, plan_key, grant_days, discount_percent, seats, seats_used, email_domains, valid_from, valid_until,"
                                 " contract_ref, code_hint, created_at FROM agreements ORDER BY created_at DESC")}


class AgreementActionIn(S.In):
    action: Literal["activate", "suspend", "end"]


@A("POST", "/v1/admin/agreements/{agreement_id}/action", body=AgreementActionIn, summary="Ativa (por outro administrador), suspende ou encerra um convênio")
def agreement_action(ctx: Ctx, body: AgreementActionIn):
    with ctx.tx() as c:
        a = c.one("SELECT id::text AS id, status, created_by::text AS created_by FROM agreements WHERE id = $1 FOR UPDATE", ctx.path["agreement_id"])
        if not a:
            raise not_found("Convênio")
        if body.action == "activate":
            if a["status"] not in ("draft", "suspended"):
                raise ApiError(409, "invalid_transition", "Convênio não está em rascunho/suspenso")
            if a["created_by"] == ctx.user_id:
                raise ApiError(409, "second_approver_required", "A ativação deve ser feita por outro administrador")
            c.run("UPDATE agreements SET status = 'active', activated_by = $2, updated_at = now() WHERE id = $1", a["id"], ctx.user_id)
        elif body.action == "suspend":
            c.run("UPDATE agreements SET status = 'suspended', updated_at = now() WHERE id = $1", a["id"])
        else:
            c.run("UPDATE agreements SET status = 'ended', updated_at = now() WHERE id = $1", a["id"])
            c.run("UPDATE entitlement_grants SET revoked_at = now(), revoked_by = $2, revoke_reason = 'Convênio encerrado' WHERE agreement_id = $1 AND revoked_at IS NULL", a["id"], ctx.user_id)
        ctx.audit(c, f"agreement.{body.action}", "agreement", a["id"], org_id=None)
    return {"id": a["id"], "action": body.action}


@A("GET", "/v1/admin/agreements/{agreement_id}/members", summary="Organizações vinculadas ao convênio")
def agreement_members(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT m.org_id::text AS org_id, o.legal_name, m.status, m.joined_at, m.grant_id::text AS grant_id FROM agreement_members m"
                                 " JOIN organizations o ON o.id = m.org_id WHERE m.agreement_id = $1 ORDER BY m.joined_at", ctx.path["agreement_id"])}


@A("POST", "/v1/admin/agreements/{agreement_id}/members/{org_id}/revoke", body=RevokeIn, summary="Remove uma organização do convênio (revoga a licença e libera a vaga)")
def revoke_member(ctx: Ctx, body: RevokeIn):
    with ctx.tx() as c:
        m = c.one("SELECT grant_id::text AS grant_id, status FROM agreement_members WHERE agreement_id = $1 AND org_id = $2 FOR UPDATE", ctx.path["agreement_id"], ctx.path["org_id"])
        if not m or m["status"] != "active":
            raise not_found("Participação")
        c.run("UPDATE agreement_members SET status = 'revoked' WHERE agreement_id = $1 AND org_id = $2", ctx.path["agreement_id"], ctx.path["org_id"])
        if m["grant_id"]:
            c.run("UPDATE entitlement_grants SET revoked_at = now(), revoked_by = $2, revoke_reason = $3 WHERE id = $1 AND revoked_at IS NULL", m["grant_id"], ctx.user_id, body.reason)
        c.run("UPDATE agreements SET seats_used = greatest(0, seats_used - 1), updated_at = now() WHERE id = $1", ctx.path["agreement_id"])
        ctx.audit(c, "agreement.member_revoked", "agreement", ctx.path["agreement_id"], {"reason": body.reason}, org_id=ctx.path["org_id"])
    return {"revoked": True}


@A("GET", "/v1/admin/voucher-batches/{batch_id}/redemptions", permission="billing.read", summary="Utilizações de um lote de vouchers (quem usou e quando; código só pelo final)")
def batch_redemptions(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT v.code_hint, v.type, v.max_redemptions, v.redeemed_count, v.valid_until, v.status AS voucher_status, r.status, r.redeemed_at,"
                                 " o.legal_name AS organization, u.email::text AS redeemed_by FROM vouchers v LEFT JOIN voucher_redemptions r ON r.voucher_id = v.id"
                                 " LEFT JOIN organizations o ON o.id = r.org_id LEFT JOIN users u ON u.id = r.redeemed_by WHERE v.batch_id = $1"
                                 " ORDER BY r.redeemed_at DESC NULLS LAST, v.code_hint", ctx.path["batch_id"])}


@route("GET", "/v1/admin/price-benchmark", permission="finance.read", auth="admin", tags=("monetizacao",),
       summary="Benchmark de preço consultado (§47–48, §89) — referência, nunca preço decidido")
def price_benchmark(ctx: Ctx):
    """O que o MERCADO cobra, lido nas páginas dos próprios fornecedores, com data e fonte.

    Isto não é, e não vira, o preço da plataforma: `config/plans.json` segue com preço nulo nos
    planos pagos até o proprietário decidir, e há teste que impede qualquer código de usar esta
    tabela para preencher aquela. Um benchmark que vira preço por conveniência produz um preço que
    ninguém decidiu — apenas copiado de empresas com outro produto, outro custo e outro cliente.
    """
    from ..core import pricing
    return pricing.benchmark()
