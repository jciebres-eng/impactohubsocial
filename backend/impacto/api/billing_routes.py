"""Planos, assinatura, faturas, webhooks do gateway e resgate de vouchers."""
from __future__ import annotations

import hashlib
import hmac

from starlette.responses import JSONResponse

from ..db.pool import DbContext
from ..http import ApiError, Ctx, route
from ..services import billing
from . import schemas as S

T = ("billing",)


@route("GET", "/v1/plans", auth="none", tags=T, summary="Catálogo público de planos (preço null = sob consulta)")
def plans(ctx: Ctx):
    with ctx.pool.tx(DbContext(), readonly=True) as c:
        rows = c.query("SELECT plan_key, version, role, name, price_cents, interval, limits, features, requires_flag FROM plans"
                       " WHERE active AND public ORDER BY role, price_cents NULLS LAST")
        flags = {r["key"]: r["enabled"] for r in c.query("SELECT key, enabled FROM feature_flags")}
    for r in rows:
        r["available"] = not r["requires_flag"] or flags.get(r["requires_flag"], False)
    return {"items": rows, "billing_provider": ctx.app.billing.name, "billing_live": flags.get("billing_live", False)}


@route("GET", "/v1/billing", min_role="viewer", tags=T, summary="Assinatura, direitos e faturas da organização")
def billing_state(ctx: Ctx):
    from ..services.entitlements import effective
    with ctx.tx(readonly=True) as c:
        ent = effective(c, ctx.org_id, ctx.principal.org_kind)
        inv = c.query("SELECT id::text AS id, description, amount_cents, currency, status, due_on, paid_at, hosted_url, created_at FROM invoices"
                      " WHERE org_id = $1 ORDER BY created_at DESC LIMIT 50", ctx.org_id)
        red = c.query("SELECT redeemed_at FROM voucher_redemptions WHERE org_id = $1 ORDER BY redeemed_at DESC", ctx.org_id)
    return {"entitlements": ent, "invoices": inv, "voucher_redemptions": red, "provider": ctx.app.billing.name}


@route("POST", "/v1/billing/checkout", body=S.CheckoutIn, min_role="owner", rate=("checkout_ip", 20, 3600), tags=T,
       summary="Inicia contratação (Stripe Checkout). Sem gateway configurado, responde 503 de forma explícita.")
def checkout(ctx: Ctx, body: S.CheckoutIn):
    return billing.checkout(ctx, body.plan_key)


@route("POST", "/v1/billing/cancel", min_role="owner", tags=T)
def cancel(ctx: Ctx):
    return billing.cancel(ctx)


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
       summary="Resgata voucher (transação atômica; resposta genérica para códigos inválidos)")
def redeem(ctx: Ctx, body: S.VoucherRedeemIn):
    from ..services.ratelimit import hit
    hit(ctx, "voucher_org", ctx.org_id, 10, 3600)
    h = code_hash(ctx.settings.voucher_hmac_key, body.code)
    generic = ApiError(404, "voucher_unavailable", "Código inválido, expirado ou não aplicável a esta organização")
    # READ COMMITTED + SELECT ... FOR UPDATE: resgates concorrentes do mesmo código são serializados pelo lock de linha;
    # quem espera relê o contador já atualizado e recebe a resposta genérica.
    with ctx.system_tx() as c:
        v = c.one("SELECT v.*, v.id::text AS id, b.status AS batch_status FROM vouchers v JOIN voucher_batches b ON b.id = v.batch_id"
                  " WHERE v.code_hash = $1 FOR UPDATE OF v", h)
        org = c.one("SELECT kind, cnpj FROM organizations WHERE id = $1", ctx.org_id)
        ok = (v and v["status"] == "active" and v["batch_status"] == "active" and v["redeemed_count"] < v["max_redemptions"]
              and (v["valid_from"] is None or c.scalar("SELECT $1::timestamptz <= now()", v["valid_from"]))
              and (v["valid_until"] is None or c.scalar("SELECT $1::timestamptz > now()", v["valid_until"]))
              and (not v["scope_roles"] or org["kind"] in v["scope_roles"])
              and (not v["scope_cnpj"] or v["scope_cnpj"] == org["cnpj"]))
        if not ok or c.one("SELECT 1 FROM voucher_redemptions WHERE voucher_id = $1 AND org_id = $2", v["id"], ctx.org_id):
            err = generic
        else:
            err = None
            c.run("INSERT INTO voucher_redemptions(voucher_id, org_id, redeemed_by) VALUES ($1,$2,$3)", v["id"], ctx.org_id, ctx.user_id)
            c.run("UPDATE vouchers SET redeemed_count = redeemed_count + 1, status = CASE WHEN redeemed_count + 1 >= max_redemptions"
                  " THEN 'exhausted' ELSE status END WHERE id = $1", v["id"])
            if v["type"] in ("grant_plan", "grant_feature", "free_period"):
                c.run("INSERT INTO entitlement_grants(org_id, plan_key, feature_key, source, source_ref, ends_at)"
                      " VALUES ($1,$2,$3,'voucher',$4, CASE WHEN $5::int IS NULL THEN NULL ELSE now() + make_interval(days => $5::int) END)",
                      ctx.org_id, v["plan_key"], v["feature_key"], v["id"], v["duration_days"])
            ctx.audit(c, "voucher.redeemed", "voucher", v["id"], {"type": v["type"], "plan": v["plan_key"]})
    if err:
        raise err
    return {"redeemed": True, "type": v["type"], "plan_key": v["plan_key"], "feature_key": v["feature_key"], "duration_days": v["duration_days"],
            "note": "Benefício aplicado. Nenhum plano ou voucher altera compatibilidade, ranking ou posição no diretório."}
