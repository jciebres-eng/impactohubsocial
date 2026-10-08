"""Contrato comercial (proposta e aceite), período de concessão e estado comercial da conta.

v0.27.0 (ADR-341): não há assinatura. A "oferta" é a proposta de um CONTRATO avulso ou parcelado
(implantação, integração, módulo institucional, inteligência territorial), montada pela administração
com alçada financeira, valor e motivo — nunca pela organização que paga. O aceite com autorização de
cobrança concede o pacote de capacidades; revogar a autorização revoga a concessão.

Estas rotas existem para que a interface NUNCA calcule data de fim de concessão nem deduza se a
conta pode ser cobrada. Ela lê `GET /v1/commercial/state` e mostra o que vier.
"""
from __future__ import annotations

from ..db.pool import DbContext
from ..http import ApiError, Ctx, not_found, route
from ..services import free_period as FP
from ..services import offers as OF
from . import schemas as S

T = ("commercial",)


@route("GET", "/v1/commercial/state", tags=T,
       summary="Estado comercial da conta: de onde vem o acesso (FREE_ACCESS/FREE_GRANT/GRANT_EXPIRING/CONTRACTED), fim da concessão e se há cobrança autorizada")
def state(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        out = FP.state(c, ctx.org_id)
    # Dito em texto, e não só em código de estado: a tela mostra isto literalmente, e é a frase que
    # evita a pergunta "então vou ser cobrado?" chegar ao suporte.
    out["will_be_charged"] = bool(out["charge_authorized"])
    out["on_expiry"] = ("Há contrato aceito com autorização de cobrança: as parcelas seguem o contrato."
                        if out["charge_authorized"] else
                        "Nenhuma cobrança será feita. O acesso ao núcleo continua gratuito, sem perder dados.")
    out["no_subscription"] = "O IMPACTO não cobra assinatura. A receita vem da camada econômica da operação financiada e de contratos avulsos."
    return out


@route("GET", "/v1/commercial/offers", tags=T, summary="Ofertas desta organização")
def list_offers(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": [dict(r) for r in c.query(
            "SELECT id::text AS id, plan_key, pricing_version, currency, amount_cents, amount_reason, contract_ref,"
            " billing_frequency, installments, payment_method, free_period_months,"
            " status, expires_at, created_at FROM commercial_offers"
            " WHERE org_id = $1 ORDER BY created_at DESC LIMIT 50", ctx.org_id)]}


@route("POST", "/v1/admin/commercial/offers", body=S.CommercialOfferIn, status=201, auth="admin", permission="finance.approve",
       tags=T, rate=("commercial_offer", 60, 3600),
       summary="Proposta de contrato para uma organização (avulso ou parcelado): valor e motivo de quem tem alçada, auditado")
def create_offer(ctx: Ctx, body: S.CommercialOfferIn):
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM organizations WHERE id = $1", body.org_id):
            raise not_found("Organização")
        out = OF.create(c, org_id=body.org_id, plan_key=body.plan_key, amount_cents=body.amount_cents,
                        amount_reason=body.amount_reason, contract_ref=body.contract_ref,
                        billing_frequency=body.billing_frequency,
                        payment_method=body.payment_method, installments=body.installments,
                        free_period_months=body.free_period_months, created_by=ctx.user_id)
        ctx.audit(c, "commercial.offer_created", "offer", out["id"],
                  {"plan_key": body.plan_key, "amount_cents": body.amount_cents, "reason": body.amount_reason,
                   "billing_frequency": body.billing_frequency, "payment_method": body.payment_method,
                   "installments": body.installments}, org_id=body.org_id)
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
    if body.consent_status == "authorized":
        with ctx.system_tx() as c:       # a concessão é escrita pela plataforma, nunca pela organização
            OF.grant_for_acceptance(c, org_id=ctx.org_id, plan_key=out["plan_key"], acceptance_id=out["id"],
                                    billing_frequency=out["billing_frequency"])
    return out


@route("POST", "/v1/commercial/consent/revoke", body=S.ConsentRevokeIn, tags=T,
       summary="Revoga a autorização de cobrança (o aceite permanece registrado)")
def revoke_consent(ctx: Ctx, body: S.ConsentRevokeIn):
    with ctx.tx() as c:
        if not OF.revoke(c, org_id=ctx.org_id, user_id=ctx.user_id, reason=body.reason):
            raise ApiError(409, "no_authorization", "Não há autorização de cobrança vigente.")
        ctx.audit(c, "commercial.consent_revoked", "organization", ctx.org_id,
                  {"reason": body.reason})
    with ctx.system_tx() as c:
        OF.revoke_contract_grants(c, org_id=ctx.org_id, user_id=ctx.user_id, reason=body.reason)
    return {"revoked": True,
            "message": "Autorização revogada. Nenhuma cobrança nova será feita e o pacote do contrato deixa de valer; nenhum dado é apagado."}


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

@route("POST", "/v1/admin/free-periods", permission="free_period.write", body=S.FreePeriodGrantIn, status=201, auth="admin",
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


@route("POST", "/v1/admin/free-periods/{period_id}/cancel", permission="free_period.write", body=S.FreePeriodCancelIn, auth="admin",
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


@route("GET", "/v1/admin/free-periods", permission="billing.read", auth="admin", tags=T,
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
       summary="Consumo do período por métrica, com percentual e limite do pacote")
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
            "overage_policy": "Exceder o limite do pacote não gera cobrança adicional: o excedente "
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
