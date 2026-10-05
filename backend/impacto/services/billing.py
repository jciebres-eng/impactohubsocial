"""Billing da PRÓPRIA plataforma (assinaturas). Nunca processa aportes a projetos (sem custódia — ADR-003).

Provedores:
* ``none``    — cobrança desligada: checkout responde 503 explicando que não está configurada.
* ``sandbox`` — SOMENTE development/test: ativa a assinatura marcada como sandbox (proibido em production).
* ``stripe``  — Checkout Sessions + webhooks assinados (Stripe-Signature, tolerância 5 min, idempotência por event id).
* ``manual``  — contratos Enterprise/Governo: admin emite fatura e registra pagamento com referência.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import urllib.parse

from ..adapters.http_client import HttpClient
from ..db.pool import DbContext
from ..db.pq import Json
from ..http import ApiError, Ctx
from ..observability import log

logger = logging.getLogger("impacto.billing")


class NoBilling:
    name = "none"

    def create_checkout(self, **kw):
        raise ApiError(503, "billing_not_configured", "Cobrança online ainda não configurada nesta instalação. "
                       "Entre em contato com o time comercial para contratar.")

    def cancel(self, sub):
        raise ApiError(503, "billing_not_configured", "Cobrança online não configurada")


class SandboxBilling:
    name = "sandbox"

    def create_checkout(self, *, org_id, plan_key, price_id, success_url, cancel_url, customer_email):
        return {"mode": "sandbox", "activate_now": True, "checkout_id": "sbx_" + hashlib.sha256(f"{org_id}{plan_key}{time.time()}".encode()).hexdigest()[:20]}

    def cancel(self, sub):
        return {"canceled": True}


def stripe_signature_valid(payload: bytes, header: str, secret: str, tolerance: int = 300, now: float | None = None) -> bool:
    try:
        parts = dict(p.split("=", 1) for p in header.split(","))
        ts = int(parts["t"])
        sigs = [v for k, v in (p.split("=", 1) for p in header.split(",")) if k == "v1"]
    except (ValueError, KeyError):
        return False
    if abs((now or time.time()) - ts) > tolerance:
        return False
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, s) for s in sigs)


class StripeBilling:
    name = "stripe"
    API = "https://api.stripe.com/v1"

    def __init__(self, secret_key: str, webhook_secret: str, http: HttpClient | None = None):
        self.sk, self.whsec, self.http = secret_key, webhook_secret, http or HttpClient(retries=2)

    def _post(self, path: str, params: dict) -> dict:
        status, _, raw = self.http.request("POST", f"{self.API}{path}", data=urllib.parse.urlencode(params).encode(),
                                           headers={"Authorization": f"Bearer {self.sk}",
                                                    "Content-Type": "application/x-www-form-urlencoded"}, timeout=20)
        data = json.loads(raw or b"{}")
        if status >= 400:
            raise ApiError(502, "billing_provider_error", "Falha no provedor de pagamento",
                           {"provider_message": (data.get("error") or {}).get("message", "")[:200]})
        return data

    def create_checkout(self, *, org_id, plan_key, price_id, success_url, cancel_url, customer_email):
        if not price_id:
            raise ApiError(409, "price_not_configured", f"Preço do plano {plan_key} não configurado (STRIPE_PRICE_{plan_key.upper()})")
        s = self._post("/checkout/sessions", {
            "mode": "subscription", "line_items[0][price]": price_id, "line_items[0][quantity]": "1",
            "success_url": success_url, "cancel_url": cancel_url, "client_reference_id": org_id, "customer_email": customer_email,
            "metadata[org_id]": org_id, "metadata[plan_key]": plan_key,
            "subscription_data[metadata][org_id]": org_id, "subscription_data[metadata][plan_key]": plan_key,
            "allow_promotion_codes": "false"})
        return {"mode": "redirect", "url": s["url"], "checkout_id": s["id"]}

    def cancel(self, sub):
        self._post(f"/subscriptions/{sub['provider_subscription_id']}", {"cancel_at_period_end": "true"})
        return {"cancel_at_period_end": True}


def make_billing_provider(settings):
    if settings.billing_provider == "stripe":
        return StripeBilling(settings.stripe_secret_key, settings.stripe_webhook_secret)
    if settings.billing_provider == "sandbox" and not settings.is_production:
        return SandboxBilling()
    return NoBilling()


# ------------------------------------------------------------------------------------------------
def checkout(ctx: Ctx, plan_key: str) -> dict:
    p = ctx.principal
    with ctx.tx(readonly=True) as c:
        plan = c.one("SELECT * FROM plans WHERE plan_key = $1 AND active", plan_key)
        if not plan or plan["role"] != p.org_kind:
            raise ApiError(404, "not_found", "Plano não disponível para este tipo de organização")
        if plan["requires_flag"]:
            on = c.scalar("SELECT enabled FROM feature_flags WHERE key = $1", plan["requires_flag"])
            if not on:
                raise ApiError(409, "plan_not_available", "Plano ainda não disponível para contratação")
        if plan["price_cents"] == 0:
            raise ApiError(409, "free_plan", "Este plano é gratuito e já está ativo")
        if plan["price_cents"] is None:
            raise ApiError(409, "price_not_defined", "Preço ainda não definido para contratação online — solicite proposta comercial ou use um voucher")
        if plan["interval"] == "custom":
            raise ApiError(409, "quote_required", "Plano sob contrato — solicite proposta comercial")
        active = c.one("SELECT plan_key FROM subscriptions WHERE org_id = $1 AND status IN ('active','trialing','past_due')", ctx.org_id)
        if active and active["plan_key"] == plan_key:
            raise ApiError(409, "already_subscribed", "A organização já possui este plano")
    base = ctx.settings.public_base_url
    res = ctx.app.billing.create_checkout(org_id=ctx.org_id, plan_key=plan_key, price_id=ctx.settings.stripe_prices.get(plan_key),
                                          success_url=f"{base}/conta/plano?status=sucesso", cancel_url=f"{base}/conta/plano?status=cancelado",
                                          customer_email=p.email)
    with ctx.system_tx() as c:
        if res.get("activate_now"):
            c.run("UPDATE subscriptions SET status = 'canceled' WHERE org_id = $1 AND status IN ('active','trialing','past_due')", ctx.org_id)
            sid = c.scalar("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_checkout_id, current_period_end)"
                           " VALUES ($1,$2,'active','sandbox',$3, now() + interval '30 days') RETURNING id::text",
                           ctx.org_id, plan_key, res["checkout_id"])
            res["subscription_id"] = sid
            res["warning"] = "Assinatura SANDBOX: nenhuma cobrança real foi feita."
        else:
            c.run("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_checkout_id) VALUES ($1,$2,'incomplete',$3,$4)",
                  ctx.org_id, plan_key, ctx.app.billing.name, res["checkout_id"])
        from .audit import record
        record(c, org_id=ctx.org_id, actor=ctx.user_id, action="billing.checkout_started", object_type="plan", object_id=plan_key,
               payload={"provider": ctx.app.billing.name}, ip=ctx.ip, request_id=ctx.request_id)
    return res


def cancel(ctx: Ctx) -> dict:
    with ctx.tx(readonly=True) as c:
        sub = c.one("SELECT * FROM subscriptions WHERE org_id = $1 AND status IN ('active','trialing','past_due')"
                    " ORDER BY created_at DESC LIMIT 1", ctx.org_id)
    if not sub:
        raise ApiError(404, "not_found", "Nenhuma assinatura ativa")
    if sub["provider"] == "manual":
        raise ApiError(409, "contract", "Assinatura sob contrato: solicite o cancelamento ao time comercial")
    if sub["provider"] == "sandbox":
        with ctx.system_tx() as c:
            c.run("UPDATE subscriptions SET status = 'canceled' WHERE id = $1", sub["id"])
    else:
        ctx.app.billing.cancel(sub)
        with ctx.system_tx() as c:
            c.run("UPDATE subscriptions SET cancel_at_period_end = true WHERE id = $1", sub["id"])
    with ctx.system_tx() as c:
        from .audit import record
        record(c, org_id=ctx.org_id, actor=ctx.user_id, action="billing.cancel_requested", object_type="subscription",
               object_id=sub["id"], payload={}, ip=ctx.ip, request_id=ctx.request_id)
    return {"status": "cancel_requested", "data_retention": "Seus dados não são apagados; recursos premium ficam somente leitura após o período."}


_STATUS_MAP = {"active": "active", "trialing": "trialing", "past_due": "past_due", "unpaid": "past_due", "canceled": "canceled",
               "incomplete": "incomplete", "incomplete_expired": "expired", "paused": "past_due"}


def handle_stripe_webhook(app_state, payload: bytes, signature: str) -> tuple[int, dict]:
    s = app_state.settings
    if s.billing_provider != "stripe" or not s.stripe_webhook_secret:
        return 404, {"error": "billing não configurado"}
    if not stripe_signature_valid(payload, signature or "", s.stripe_webhook_secret):
        log(logger, logging.WARNING, "stripe_webhook_bad_signature")
        return 400, {"error": "assinatura inválida"}
    try:
        event = json.loads(payload)
    except ValueError:
        return 400, {"error": "json inválido"}
    return process_event(app_state, "stripe", event)


def process_event(app_state, provider: str, event: dict) -> tuple[int, dict]:
    eid, etype = str(event.get("id", "")), str(event.get("type", ""))
    if not eid or not etype:
        return 400, {"error": "evento inválido"}
    obj = (event.get("data") or {}).get("object") or {}
    with app_state.pool.tx(DbContext(system=True)) as c:
        inserted = c.one("INSERT INTO billing_events(provider, event_id, type, payload) VALUES ($1,$2,$3,$4::jsonb)"
                         " ON CONFLICT (provider, event_id) DO NOTHING RETURNING id", provider, eid, etype, Json(event))
        if not inserted:
            return 200, {"status": "duplicate_ignored"}
        status = "processed"
        if etype == "checkout.session.completed":
            md = obj.get("metadata") or {}
            n = c.run("UPDATE subscriptions SET status = 'active', provider_customer_id = $2, provider_subscription_id = $3"
                      " WHERE provider_checkout_id = $1 AND org_id::text = $4 AND plan_key = $5",
                      obj.get("id"), obj.get("customer"), obj.get("subscription"), md.get("org_id", ""), md.get("plan_key", ""))
            if n:
                c.run("UPDATE subscriptions SET status = 'canceled' WHERE org_id::text = $1 AND status IN ('active','trialing','past_due')"
                      " AND provider_checkout_id IS DISTINCT FROM $2", md.get("org_id", ""), obj.get("id"))
            else:
                status = "ignored"
        elif etype in ("customer.subscription.updated", "customer.subscription.deleted", "customer.subscription.created"):
            st = "canceled" if etype.endswith("deleted") else _STATUS_MAP.get(obj.get("status"), "past_due")
            pe = obj.get("current_period_end")
            n = c.run("UPDATE subscriptions SET status = $2, current_period_end = CASE WHEN $3::bigint IS NULL THEN current_period_end"
                      " ELSE to_timestamp($3::bigint) END, cancel_at_period_end = $4 WHERE provider_subscription_id = $1",
                      obj.get("id"), st, pe, bool(obj.get("cancel_at_period_end")))
            status = "processed" if n else "ignored"
        elif etype in ("invoice.paid", "invoice.payment_failed", "invoice.finalized"):
            sub = c.one("SELECT id, org_id FROM subscriptions WHERE provider_subscription_id = $1", obj.get("subscription"))
            if sub:
                inv_status = {"invoice.paid": "paid", "invoice.payment_failed": "open", "invoice.finalized": "open"}[etype]
                c.run("INSERT INTO invoices(org_id, subscription_id, provider, provider_invoice_id, amount_cents, currency, status, paid_at, hosted_url)"
                      " VALUES ($1,$2,'stripe',$3,$4,upper($5),$6, CASE WHEN $6 = 'paid' THEN now() END, $7)"
                      " ON CONFLICT (provider_invoice_id) DO UPDATE SET status = EXCLUDED.status, paid_at = coalesce(invoices.paid_at, EXCLUDED.paid_at)",
                      sub["org_id"], sub["id"], obj.get("id"), int(obj.get("amount_paid") or obj.get("amount_due") or 0),
                      obj.get("currency") or "brl", inv_status, obj.get("hosted_invoice_url"))
                if etype == "invoice.payment_failed":
                    c.run("UPDATE subscriptions SET status = 'past_due' WHERE id = $1", sub["id"])
            else:
                status = "ignored"
        else:
            status = "ignored"
        c.run("UPDATE billing_events SET status = $2, processed_at = now() WHERE id = $1", inserted["id"], status)
    return 200, {"status": status}
