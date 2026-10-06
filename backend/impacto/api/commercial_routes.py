"""Oferta comercial, aceite, período gratuito e estado comercial da conta.

Estas rotas existem para que a interface NUNCA calcule data de fim de gratuidade nem deduza se a
conta pode ser cobrada. Ela lê `GET /v1/commercial/state` e mostra o que vier. Toda a classe de
defeito em que a tela anuncia um prazo e a cobrança usa outro nasce de duas camadas fazendo a
mesma conta — então só uma faz.
"""
from __future__ import annotations

from ..db.pool import DbContext
from ..http import ApiError, Ctx, not_found, route
from ..services import free_period as FP
from ..services import offers as OF
from . import schemas as S

T = ("commercial",)


@route("GET", "/v1/commercial/state", tags=T,
       summary="Estado comercial da conta: FREE_PERIOD_END, estado e se a cobrança foi autorizada")
def state(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        out = FP.state(c, ctx.org_id)
    # Dito em texto, e não só em código de estado: a tela mostra isto literalmente, e é a frase que
    # evita a pergunta "então vou ser cobrado?" chegar ao suporte.
    out["will_be_charged"] = bool(out["charge_authorized"])
    out["on_expiry"] = ("A assinatura segue e a primeira fatura sai no fim do período gratuito."
                        if out["charge_authorized"] else
                        "Nenhuma cobrança será feita. A conta volta ao plano gratuito, sem perder dados.")
    return out


@route("GET", "/v1/commercial/offers", tags=T, summary="Ofertas desta organização")
def list_offers(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": [dict(r) for r in c.query(
            "SELECT id::text AS id, plan_key, pricing_version, currency, amount_cents,"
            " billing_frequency, interval, installments, payment_method, free_period_months,"
            " status, expires_at, created_at FROM commercial_offers"
            " WHERE org_id = $1 ORDER BY created_at DESC LIMIT 50", ctx.org_id)]}


@route("POST", "/v1/commercial/offers", body=S.CommercialOfferIn, status=201, tags=T, rate=("commercial_offer", 60, 3600),
       summary="Monta uma oferta a partir do catálogo (valor nunca vem do cliente)")
def create_offer(ctx: Ctx, body: S.CommercialOfferIn):
    with ctx.tx() as c:
        out = OF.create(c, org_id=ctx.org_id, plan_key=body.plan_key, interval=body.interval,
                        billing_frequency=body.billing_frequency,
                        payment_method=body.payment_method, installments=body.installments,
                        free_period_months=body.free_period_months, created_by=ctx.user_id)
        ctx.audit(c, "commercial.offer_created", "offer", out["id"],
                  {"plan_key": body.plan_key, "billing_frequency": body.billing_frequency,
                   "payment_method": body.payment_method, "installments": body.installments})
    return out


@route("POST", "/v1/commercial/offers/{offer_id}/accept", body=S.CommercialAcceptIn, tags=T,
       rate=("commercial_accept", 60, 3600), summary="Aceita a oferta — acesso gratuito OU autorização de cobrança")
def accept_offer(ctx: Ctx, body: S.CommercialAcceptIn):
    with ctx.tx() as c:
        out = OF.accept(c, ctx.settings, offer_id=ctx.path["offer_id"], org_id=ctx.org_id,
                        user_id=ctx.user_id, consent_status=body.consent_status,
                        ip=ctx.ip, user_agent=ctx.user_agent)
        ctx.audit(c, "commercial.offer_accepted", "offer", ctx.path["offer_id"],
                  {"consent_status": body.consent_status})
    return out


@route("POST", "/v1/commercial/consent/revoke", body=S.ConsentRevokeIn, tags=T,
       summary="Revoga a autorização de cobrança (o aceite permanece registrado)")
def revoke_consent(ctx: Ctx, body: S.ConsentRevokeIn):
    with ctx.tx() as c:
        if not OF.revoke(c, org_id=ctx.org_id, user_id=ctx.user_id, reason=body.reason):
            raise ApiError(409, "no_authorization", "Não há autorização de cobrança vigente.")
        ctx.audit(c, "commercial.consent_revoked", "organization", ctx.org_id,
                  {"reason": body.reason})
    return {"revoked": True,
            "message": "Autorização revogada. Nenhuma cobrança nova será feita."}


@route("GET", "/v1/commercial/acceptances", tags=T, summary="Histórico de aceites desta organização")
def acceptances(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": [dict(r) for r in c.query(
            "SELECT id::text AS id, offer_id::text AS offer_id, pricing_version, plan_key,"
            " billing_frequency, payment_method, terms_version, privacy_version,"
            " commercial_terms_version, accepted_at, consent_status, revoked_at, revoke_reason"
            " FROM offer_acceptances WHERE org_id = $1 ORDER BY accepted_at DESC LIMIT 100",
            ctx.org_id)]}


# --- administração ----------------------------------------------------------------------------

@route("POST", "/v1/admin/free-periods", body=S.FreePeriodGrantIn, status=201, auth="admin",
       tags=T, summary="Concede período gratuito a uma organização (motivo obrigatório)")
def grant_free_period(ctx: Ctx, body: S.FreePeriodGrantIn):
    with ctx.tx() as c:
        out = FP.grant(c, org_id=body.org_id, source=body.source, reason=body.reason,
                       months=body.months, plan_key=body.plan_key, granted_by=ctx.user_id)
        if not out:
            raise ApiError(409, "free_period_exists",
                           "Esta organização já tem um período gratuito desta origem.")
        ctx.audit(c, "commercial.free_period_granted", "organization", body.org_id,
                  {"source": body.source, "months": body.months, "reason": body.reason},
                  org_id=body.org_id)
    return out


@route("POST", "/v1/admin/free-periods/{period_id}/cancel", body=S.FreePeriodCancelIn, auth="admin",
       tags=T, summary="Cancela um período gratuito (o registro permanece, com motivo e autor)")
def cancel_free_period(ctx: Ctx, body: S.FreePeriodCancelIn):
    with ctx.tx() as c:
        alvo = c.one("SELECT org_id::text AS org_id FROM free_periods WHERE id = $1",
                     ctx.path["period_id"])
        if not alvo:
            raise not_found("período gratuito")
        if not FP.cancel(c, period_id=ctx.path["period_id"], cancelled_by=ctx.user_id,
                         reason=body.reason):
            raise ApiError(409, "free_period_not_active", "Este período já não está ativo.")
        ctx.audit(c, "commercial.free_period_cancelled", "organization", alvo["org_id"],
                  {"period_id": ctx.path["period_id"], "reason": body.reason},
                  org_id=alvo["org_id"])
    return {"cancelled": True}


@route("GET", "/v1/admin/free-periods", auth="admin", tags=T,
       summary="Períodos gratuitos concedidos, por origem e situação")
def list_free_periods(ctx: Ctx):
    with ctx.pool.tx(DbContext(system=True), readonly=True) as c:
        resumo = [dict(r) for r in c.query(
            "SELECT source, status, count(*) AS total, min(ends_at) AS proximo_fim"
            " FROM free_periods GROUP BY source, status ORDER BY source, status")]
        itens = [dict(r) for r in c.query(
            "SELECT f.id::text AS id, f.org_id::text AS org_id, o.legal_name, f.source, f.months,"
            " f.started_at, f.ends_at, f.status, f.reason, f.pricing_version"
            " FROM free_periods f JOIN organizations o ON o.id = f.org_id"
            " ORDER BY f.ends_at DESC LIMIT 200")]
    return {"summary": resumo, "items": itens}


# --- uso e teto de gasto ------------------------------------------------------------------------

@route("GET", "/v1/commercial/usage", tags=T,
       summary="Consumo do período por métrica, com percentual e limite do plano")
def usage(ctx: Ctx):
    from ..services import usage as U
    # Contexto de SISTEMA porque esta leitura ESCREVE: ela sincroniza o contador do período. O
    # contador é escrito pela plataforma, não pela organização — se a organização pudesse escrever
    # nele, o histórico de consumo deixaria de ser prova de consumo. O `org_id` continua preso ao
    # da sessão, então o privilégio não amplia o alcance, só a permissão.
    with ctx.system_tx() as c:
        linhas = U.sync(c, ctx.org_id, ctx.principal.org_kind)
        teto = U.spend_limit(c, ctx.org_id)
        gasto = U.spent_this_month(c, ctx.org_id)
    return {"metrics": linhas, "thresholds": list(U.THRESHOLDS),
            "spend_limit": teto, "spent_cents": gasto,
            # Dito explicitamente porque é a pergunta que o número de consumo levanta: passar do
            # limite do plano não gera fatura — interrompe o excedente.
            "overage_policy": "Exceder o limite do plano não gera cobrança adicional: o excedente "
                              "é interrompido. Não há cobrança por excedente sem preço publicado "
                              "e sem autorização."}


@route("PUT", "/v1/commercial/spend-limit", body=S.SpendLimitIn, tags=T,
       summary="Define o teto de gasto mensal e o que fazer ao atingi-lo (avisar ou parar)")
def set_spend_limit(ctx: Ctx, body: S.SpendLimitIn):
    from ..services import usage as U
    with ctx.tx() as c:
        out = U.set_spend_limit(c, org_id=ctx.org_id, limit_cents=body.limit_cents,
                                action=body.action, set_by=ctx.user_id)
        ctx.audit(c, "commercial.spend_limit_set", "organization", ctx.org_id,
                  {"limit_cents": body.limit_cents, "action": body.action})
    return out
