"""Planos, assinatura, faturas, webhooks do gateway e resgate de vouchers."""
from __future__ import annotations

import hashlib
import hmac

from starlette.responses import JSONResponse

from ..db.pool import DbContext
from ..http import ApiError, Ctx, not_found, route
from ..services import billing
from . import schemas as S

T = ("billing",)


@route("GET", "/v1/plans", auth="none", tags=T, summary="Catálogo público de planos (tier, preços mensal/anual; preço null = sob consulta)")
def plans(ctx: Ctx):
    from ..services import monetization as mon
    with ctx.pool.tx(DbContext(), readonly=True) as c:
        rows = c.query("SELECT plan_key, version, role, name, tier, price_cents, interval, limits, features, requires_flag FROM plans"
                       " WHERE active AND public ORDER BY role, CASE tier WHEN 'free' THEN 0 WHEN 'plus' THEN 1 WHEN 'premium' THEN 2 ELSE 3 END, price_cents NULLS LAST")
        flags = {r["key"]: r["enabled"] for r in c.query("SELECT key, enabled FROM feature_flags")}
        prices = {}
        for r in c.query("SELECT plan_key, interval, amount_cents FROM plan_prices WHERE active"):
            prices.setdefault(r["plan_key"], {})[r["interval"]] = r["amount_cents"]
        # v0.16.0: a tabela de preços vigente, com moeda, preço de entrada, imposto e o TOTAL à vista. Cada plano
        # carrega as duas leituras (mensal e anual) para que a tela compare sem fazer conta própria — conta feita no
        # navegador é conta que divergirá do que será cobrado.
        pisos = mon.quote_floors()
        quotes = {}
        for r in rows:
            for iv in ("month", "year"):
                q = mon.price_quote(c, r["plan_key"], iv)
                if q:
                    quotes.setdefault(r["plan_key"], {})[iv] = q
    for r in rows:
        r["available"] = not r["requires_flag"] or flags.get(r["requires_flag"], False)
        pr = dict(prices.get(r["plan_key"], {}))
        pq = quotes.get(r["plan_key"], {})
        for iv, q in pq.items():
            pr[iv] = q["amount_cents"]          # a versão vigente manda sobre a tabela antiga
        if r["price_cents"] and r["interval"] in ("month", "year") and pr.get(r["interval"]) is None:
            pr[r["interval"]] = r["price_cents"]
        r["prices"] = pr
        r["price_quotes"] = pq
        r["currency"] = next((q["currency"] for q in pq.values()), "BRL")
        r["annual_savings"] = mon.annual_savings(pr.get("month"), pr.get("year"))
        r["tier_label"] = mon.TIER_LABEL.get(r["tier"], r["tier"])
        # PISO de proposta comercial. Não é preço: planos com piso não têm linha vigente em
        # `plan_price_versions` e o checkout os recusa. Publicá-lo é honestidade com quem avalia o
        # produto — "sob consulta" sem nenhuma ordem de grandeza faz a pessoa perder tempo
        # descobrindo que o plano não cabe no orçamento dela.
        r["quote_floor_cents"] = pisos.get(r["plan_key"])
    return {"items": rows, "billing_provider": ctx.app.billing.name, "billing_live": flags.get("billing_live", False),
            "trial_days": ctx.settings.trial_days, "trial_auto_start": ctx.settings.trial_auto_start,
            "pricing_version": mon.pricing_version_name(),
            "pricing_note": "Valores definidos no servidor, com vigência. Imposto e total aparecem antes do "
                            "pagamento; o preço de entrada diz por quantos períodos vale e quanto passa a ser "
                            "depois."}


# A rota fica sob /v1/plans, não sob /v1/billing: tudo em /v1/billing exige autenticação (há um teste que verifica
# isso desde a v0.11.0), e a TABELA DE PREÇOS é pública por natureza — é o que alguém lê antes de ter conta.
@route("GET", "/v1/plans/price", query=S.PriceQ, auth="none", tags=T,
       summary="Preço vigente de um plano: entrada, preço regular, equivalente mensal, total e imposto")
def billing_price(ctx: Ctx, q: S.PriceQ):
    """Preço calculado no SERVIDOR. O cliente informa plano e intervalo; valor, moeda e imposto vêm daqui."""
    from ..services import monetization as mon
    with ctx.pool.tx(DbContext(), readonly=True) as c:
        out = mon.price_quote(c, q.plan_key, q.interval)
    if not out:
        raise ApiError(404, "price_not_defined",
                       "Este plano não tem preço publicado para contratação online")
    return out


@route("GET", "/v1/billing/price-history", min_role="owner", tags=T,
       summary="Histórico de preço da organização e avisos de reajuste recebidos")
def billing_price_history(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {
            "accepted": c.query(
                "SELECT plan_key, interval, currency, amount_cents, intro_amount_cents, intro_periods,"
                " intro_periods_used, tax_behavior, accepted_at, ends_at FROM subscription_prices"
                " WHERE org_id = $1 ORDER BY accepted_at DESC", ctx.org_id),
            "notices": c.query(
                "SELECT id::text AS id, from_amount_cents, to_amount_cents, currency, effective_at, notified_at,"
                " channel, acknowledged_at, reason FROM price_change_notices WHERE org_id = $1"
                " ORDER BY notified_at DESC", ctx.org_id),
            "note": "O preço aceito fica congelado. Aumento exige aviso com 30 dias de antecedência, registrado "
                    "aqui — o banco recusa aplicar sem ele.",
        }


@route("POST", "/v1/billing/price-notices/{notice_id}/ack", min_role="owner", tags=T,
       summary="Registra que a organização viu o aviso de reajuste")
def ack_price_notice(ctx: Ctx):
    nid = ctx.path["notice_id"]
    with ctx.tx() as c:
        n = c.run("UPDATE price_change_notices SET acknowledged_at = now(), acknowledged_by = $2"
                  " WHERE id = $1 AND org_id = $3 AND acknowledged_at IS NULL", nid, ctx.user_id, ctx.org_id)
    if not n:
        raise not_found("Aviso de reajuste")
    return {"id": nid, "acknowledged": True}


@route("GET", "/v1/billing", min_role="viewer", tags=T, summary="Estado de cobrança da organização: plano, status, trial, próxima cobrança, avisos, faturas")
def billing_state(ctx: Ctx):
    from ..services import monetization as mon
    from ..services.entitlements import effective
    with ctx.tx(readonly=True) as c:
        ent = effective(c, ctx.org_id, ctx.principal.org_kind)
        inv = c.query("SELECT id::text AS id, description, amount_cents, currency, status, due_on, paid_at, hosted_url, created_at FROM invoices"
                      " WHERE org_id = $1 ORDER BY created_at DESC LIMIT 50", ctx.org_id)
        red = c.query("SELECT redeemed_at, status FROM voucher_redemptions WHERE org_id = $1 ORDER BY redeemed_at DESC", ctx.org_id)
        sub = c.one("SELECT id::text AS id, plan_key, status, provider, interval, amount_cents, discount, trial_end, current_period_end, cancel_at_period_end, canceled_at,"
                    " payment_issue, (provider_customer_id IS NOT NULL) AS has_payment_customer FROM subscriptions WHERE org_id = $1 AND status = ANY($2::text[])"
                    " ORDER BY created_at DESC LIMIT 1", ctx.org_id, ["active", "trialing", "past_due"])
        trial_row = c.one("SELECT * FROM org_trials WHERE org_id = $1", ctx.org_id)
        now = mon._now(c)
        agreements = c.query("SELECT a.name, a.kind, a.discount_percent, a.plan_key, m.status, g.ends_at FROM agreement_members m JOIN agreements a ON a.id = m.agreement_id"
                             " LEFT JOIN entitlement_grants g ON g.id = m.grant_id WHERE m.org_id = $1", ctx.org_id)
        grants = c.query("SELECT plan_key, feature_key, source, reason, starts_at, ends_at FROM entitlement_grants WHERE org_id = $1 AND revoked_at IS NULL"
                         " AND (ends_at IS NULL OR ends_at > now()) ORDER BY created_at DESC", ctx.org_id)
    # `vouchers` é invisível à organização por RLS (só app_priv()), então o desconto reservado é lido em contexto de sistema
    # SEMPRE restrito ao org_id da sessão e expondo apenas tipo/valor/plano — nunca código, hash ou dados de outra organização.
    with ctx.system_tx() as c:
        pending = c.query("SELECT v.type, v.value, v.plan_key FROM voucher_redemptions r JOIN vouchers v ON v.id = r.voucher_id"
                          " WHERE r.org_id = $1 AND r.status = 'pending_discount'", ctx.org_id)
    tv = mon.trial_view(trial_row, now, has_paid_sub=bool(sub and sub["status"] in ("active", "trialing")))
    next_charge = None
    if sub and sub["status"] in ("active", "trialing") and not sub["cancel_at_period_end"] and sub["provider"] != "manual":
        next_charge = {"at": sub["trial_end"] if sub["status"] == "trialing" and sub["trial_end"] else sub["current_period_end"], "amount_cents": sub["amount_cents"], "interval": sub["interval"]}
    return {"entitlements": ent, "tier": ent["tier"], "tier_label": ent["tier_label"], "subscription": sub, "trial": tv, "next_charge": next_charge,
            "notices": mon.billing_notices(trial=tv, sub=sub, now=now), "pending_discounts": pending, "agreements": agreements, "licenses": grants,
            "invoices": inv, "voucher_redemptions": red, "provider": ctx.app.billing.name,
            "payment_method": "Gerenciado no portal de pagamento do provedor; a plataforma não armazena dados de cartão." if sub and sub.get("has_payment_customer") else None}


@route("POST", "/v1/billing/quote", body=S.QuoteIn, min_role="viewer", tags=T,
       summary="Simulação do valor FINAL calculada no servidor (preço, desconto, trial, primeira cobrança). Não cobra nada.")
def quote(ctx: Ctx, body: S.QuoteIn):
    from ..services import monetization as mon
    with ctx.system_tx() as c:       # vouchers/convênios são invisíveis à organização por RLS; org_id vem sempre da sessão autenticada
        return mon.quote(c, org_id=ctx.org_id, org_kind=ctx.principal.org_kind, plan_key=body.plan_key, interval=body.interval)


@route("POST", "/v1/billing/checkout", body=S.CheckoutIn, min_role="owner", rate=("checkout_ip", 20, 3600), tags=T,
       summary="Inicia contratação (Stripe Checkout) com trial quando houver. Sem gateway configurado, responde 503 de forma explícita.")
def checkout(ctx: Ctx, body: S.CheckoutIn):
    return billing.checkout(ctx, body.plan_key, body.interval, body.voucher)


@route("POST", "/v1/billing/cancel", min_role="owner", tags=T, summary="Cancela a assinatura ou o trial (sem cobrança; acesso mantido até o fim do período)")
def cancel(ctx: Ctx):
    return billing.cancel(ctx)


@route("POST", "/v1/billing/reactivate", min_role="owner", tags=T, summary="Desfaz um cancelamento em andamento")
def reactivate(ctx: Ctx):
    return billing.reactivate(ctx)


@route("POST", "/v1/billing/change-plan", body=S.ChangePlanIn, min_role="owner", rate=("checkout_ip", 20, 3600), tags=T,
       summary="Upgrade/downgrade (sincronizado com o provedor)")
def change_plan(ctx: Ctx, body: S.ChangePlanIn):
    return billing.change_plan(ctx, body.plan_key, body.interval)


@route("POST", "/v1/billing/portal", min_role="owner", tags=T, summary="Portal de pagamento do provedor (método de pagamento, faturas)")
def portal(ctx: Ctx):
    return billing.portal(ctx)


@route("POST", "/v1/billing/webhooks/stripe", auth="none", raw=True, raw_body=True, rate=("webhook_ip", 600, 60), tags=T,
       summary="Webhook do Stripe (assinatura verificada, idempotente)")
def stripe_webhook(ctx: Ctx, payload: bytes):
    status, body = billing.handle_stripe_webhook(ctx.app, payload, ctx.request.headers.get("stripe-signature", ""))
    return JSONResponse(body, status_code=status)


# ------------------------------------------------------------------------------------------------ vouchers
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def code_hash(secret: str, code: str) -> str:
    norm = code.strip().upper().replace("-", "").replace(" ", "")
    return hmac.new(secret.encode(), norm.encode(), hashlib.sha256).hexdigest()


@route("POST", "/v1/vouchers/redeem", body=S.VoucherRedeemIn, min_role="admin", rate=("voucher_ip", 10, 3600), tags=T,
       summary="Resgata voucher (transação atômica; resposta genérica para códigos inválidos). Descontos ficam pendentes até o checkout.")
def redeem(ctx: Ctx, body: S.VoucherRedeemIn):
    from ..services import monetization as mon
    from ..services.ratelimit import hit
    hit(ctx, "voucher_org", ctx.org_id, 10, 3600)
    h = code_hash(ctx.settings.voucher_hmac_key, body.code)
    generic = ApiError(404, "voucher_unavailable", "Código inválido, expirado ou não aplicável a esta organização")
    # READ COMMITTED + SELECT ... FOR UPDATE: resgates concorrentes do mesmo código são serializados pelo lock de linha;
    # quem espera relê o contador já atualizado e recebe a resposta genérica.
    with ctx.system_tx() as c:
        v = mon.voucher_row(c, h)
        org = c.one("SELECT kind, cnpj FROM organizations WHERE id = $1", ctx.org_id)
        if not mon.voucher_usable(c, v, org, ctx.org_id):
            err, outcome = generic, None
        else:
            err = None
            outcome = mon.redeem_voucher(c, v, ctx.org_id, ctx.user_id)
            ctx.audit(c, "voucher.redeemed", "voucher", v["id"], {"type": v["type"], "plan": v["plan_key"], "outcome": outcome})
    if err:
        raise err
    return {"redeemed": True, "type": v["type"], "plan_key": v["plan_key"], "feature_key": v["feature_key"], "duration_days": v["duration_days"],
            "pending_discount": outcome == "pending_discount",
            "note": ("Desconto reservado: será aplicado no checkout." if outcome == "pending_discount" else "Benefício aplicado.")
            + " Nenhum plano ou voucher altera compatibilidade, ranking ou posição no diretório."}
