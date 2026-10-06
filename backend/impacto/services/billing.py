"""Billing da PRÓPRIA plataforma (assinaturas). Nunca processa aportes a projetos (sem custódia — ADR-003).

Provedores:
* ``none``    — cobrança desligada: checkout responde 503 explicando que não está configurada.
* ``sandbox`` — SOMENTE development/test: ativa a assinatura marcada como sandbox (proibido em production).
* ``stripe``  — Checkout Sessions + webhooks assinados (Stripe-Signature, tolerância 5 min, idempotência por event id).
* ``manual``  — contratos Enterprise/Governo: admin emite fatura e registra pagamento com referência.

v0.11.0: trial (a primeira cobrança só ocorre após o trial: ``subscription_data[trial_end]``), mensal/anual, desconto via cupom criado no servidor,
upgrade/downgrade sincronizados com o provedor, reativação, portal de pagamento, eventos adicionais de webhook e proteção contra eventos fora de ordem.
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
from . import monetization as mon

logger = logging.getLogger("impacto.billing")


class NoBilling:
    name = "none"
    needs_price_id = False   # não cobra nada, então não há preço a publicar

    def create_checkout(self, **kw):
        raise ApiError(503, "billing_not_configured", "Cobrança online ainda não configurada nesta instalação. "
                       "Entre em contato com o time comercial para contratar.")

    def cancel(self, sub):
        raise ApiError(503, "billing_not_configured", "Cobrança online não configurada")

    def reactivate(self, sub):
        raise ApiError(503, "billing_not_configured", "Cobrança online não configurada")

    def change_plan(self, sub, **kw):
        raise ApiError(503, "billing_not_configured", "Cobrança online não configurada")

    def portal(self, sub, return_url):
        raise ApiError(503, "billing_not_configured", "Cobrança online não configurada")


class SandboxBilling:
    name = "sandbox"
    needs_price_id = False   # ativa na hora, sem provedor externo: nada a publicar

    def create_checkout(self, *, org_id, plan_key, price_id=None, success_url=None, cancel_url=None, customer_email=None, **kw):
        return {"mode": "sandbox", "activate_now": True, "checkout_id": "sbx_" + hashlib.sha256(f"{org_id}{plan_key}{time.time()}".encode()).hexdigest()[:20]}

    def cancel(self, sub):
        return {"cancel_at_period_end": True}

    def reactivate(self, sub):
        return {"cancel_at_period_end": False}

    def change_plan(self, sub, **kw):
        return {"changed": True}

    def portal(self, sub, return_url):
        return {"mode": "sandbox", "url": None}


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
    needs_price_id = True   # o Checkout exige um `price` existente na conta
    API = "https://api.stripe.com/v1"

    def __init__(self, secret_key: str, webhook_secret: str, http: HttpClient | None = None):
        self.sk, self.whsec, self.http = secret_key, webhook_secret, http or HttpClient(retries=2)

    def _call(self, method: str, path: str, params: dict | None = None) -> dict:
        status, _, raw = self.http.request(method, f"{self.API}{path}", data=urllib.parse.urlencode(params).encode() if params is not None else None,
                                           headers={"Authorization": f"Bearer {self.sk}", "Content-Type": "application/x-www-form-urlencoded"}, timeout=20)
        data = json.loads(raw or b"{}")
        if status >= 400:
            raise ApiError(502, "billing_provider_error", "Falha no provedor de pagamento",
                           {"provider_message": (data.get("error") or {}).get("message", "")[:200]})
        return data

    def _post(self, path: str, params: dict) -> dict:
        return self._call("POST", path, params)

    def create_checkout(self, *, org_id, plan_key, price_id, success_url, cancel_url, customer_email, interval="month", trial_end=None, discount=None, **kw):
        if not price_id:
            raise ApiError(409, "price_not_configured", f"Preço do plano {plan_key} ({interval}) não configurado (STRIPE_PRICE_{plan_key.upper()}"
                           f"{'_YEAR' if interval == 'year' else ''})")
        params = {
            "mode": "subscription", "line_items[0][price]": price_id, "line_items[0][quantity]": "1",
            "success_url": success_url, "cancel_url": cancel_url, "client_reference_id": org_id, "customer_email": customer_email,
            "metadata[org_id]": org_id, "metadata[plan_key]": plan_key, "metadata[interval]": interval,
            "subscription_data[metadata][org_id]": org_id, "subscription_data[metadata][plan_key]": plan_key, "subscription_data[metadata][interval]": interval,
            "allow_promotion_codes": "false"}
        if trial_end:      # a primeira cobrança só acontece após o trial
            params["subscription_data[trial_end]"] = str(int(trial_end.timestamp()))
        if discount:
            cp = {"duration": discount["duration"]}
            if discount["kind"] == "percent":
                cp["percent_off"] = str(discount["value"])
            else:
                cp["amount_off"], cp["currency"] = str(discount["value"]), "brl"
            if discount["duration"] == "repeating":
                cp["duration_in_months"] = str(discount.get("months") or 1)
            params["discounts[0][coupon]"] = self._post("/coupons", cp)["id"]
        s = self._post("/checkout/sessions", params)
        return {"mode": "redirect", "url": s["url"], "checkout_id": s["id"]}

    def cancel(self, sub):
        # durante o trial, cancel_at_period_end encerra no fim do trial SEM cobrança
        self._post(f"/subscriptions/{sub['provider_subscription_id']}", {"cancel_at_period_end": "true"})
        return {"cancel_at_period_end": True}

    def reactivate(self, sub):
        self._post(f"/subscriptions/{sub['provider_subscription_id']}", {"cancel_at_period_end": "false"})
        return {"cancel_at_period_end": False}

    def change_plan(self, sub, *, price_id, plan_key, interval, **kw):
        if not price_id:
            raise ApiError(409, "price_not_configured", f"Preço do plano {plan_key} ({interval}) não configurado")
        cur = self._call("GET", f"/subscriptions/{sub['provider_subscription_id']}")
        item = ((cur.get("items") or {}).get("data") or [{}])[0].get("id")
        if not item:
            raise ApiError(502, "billing_provider_error", "Assinatura sem item no provedor")
        self._post(f"/subscriptions/{sub['provider_subscription_id']}", {
            "items[0][id]": item, "items[0][price]": price_id, "proration_behavior": "create_prorations", "cancel_at_period_end": "false",
            "metadata[plan_key]": plan_key, "metadata[interval]": interval})
        return {"changed": True}

    def portal(self, sub, return_url):
        if not sub.get("provider_customer_id"):
            raise ApiError(409, "no_customer", "Ainda não há cliente no provedor de pagamento")
        s = self._post("/billing_portal/sessions", {"customer": sub["provider_customer_id"], "return_url": return_url})
        return {"mode": "redirect", "url": s["url"]}


def make_billing_provider(settings):
    if settings.billing_provider == "stripe":
        return StripeBilling(settings.stripe_secret_key, settings.stripe_webhook_secret)
    if settings.billing_provider == "sandbox" and not settings.is_production:
        return SandboxBilling()
    return NoBilling()


def price_ref(settings, plan_key: str, interval: str, *, conn=None) -> str | None:
    """Identificador do preço NO PROVEDOR. Nunca embutido no código, e nunca inventado.

    Duas fontes, nesta ordem:
      1. `plan_price_versions.provider_price_id` da versão vigente (v0.16.0) — fica junto do preço que ele
         representa, o que impede a combinação errada "preço novo, identificador do antigo";
      2. variável de ambiente `STRIPE_PRICE_<PLAN>[_MONTH|_YEAR]` (v0.11.0), mantida para instalação já configurada.

    Devolver `None` é resposta legítima e significa "não configurado". Quem chama precisa recusar a cobrança com
    mensagem clara, e é o que `checkout` faz — tentar com um valor inventado produziria erro do provedor em
    produção, no pior momento possível.
    """
    if conn is not None:
        v = mon.price_version(conn, plan_key, interval)
        if v and v["provider_price_id"]:
            return str(v["provider_price_id"])
    p = settings.stripe_prices
    return p.get(f"{plan_key}_{interval}") or (p.get(plan_key) if interval == "month" else None)


# ------------------------------------------------------------------------------------------------
LIVE = ("active", "trialing", "past_due")


def _live_sub(c, org_id: str):
    return c.one("SELECT * FROM subscriptions WHERE org_id = $1 AND status = ANY($2::text[]) ORDER BY created_at DESC LIMIT 1", org_id, list(LIVE))


def _audit(ctx: Ctx, c, action: str, obj_type: str, obj_id, payload: dict) -> None:
    from .audit import record
    record(c, org_id=ctx.org_id, actor=ctx.user_id, action=action, object_type=obj_type, object_id=obj_id, payload=payload, ip=ctx.ip, request_id=ctx.request_id)


def record_accepted_price(c, *, org_id: str, subscription_id: str | None, quote: dict,
                          accepted_by: str | None) -> str | None:
    """Congela o preço que a organização aceitou.

    POR QUE CONGELAR: sem isto, um reajuste reescreveria retroativamente aquilo com que cada organização concordou,
    e "quanto esta organização contratou em março?" deixaria de ter resposta. `price_apply_guard()` no banco ainda
    recusa um aumento sem aviso prévio registrado — esta função é o lado honesto do mesmo par: ela grava O QUE foi
    aceito, no momento em que foi aceito.

    Devolve `None` quando não há versão de preço (instalação ainda na tabela antiga): a cobrança segue funcionando,
    só não há o que congelar.
    """
    pq = quote.get("price")
    if not pq:
        return None
    c.run("UPDATE subscription_prices SET ends_at = now() WHERE org_id = $1 AND ends_at IS NULL", org_id)
    return c.scalar(
        "INSERT INTO subscription_prices(org_id, subscription_id, price_version_id, plan_key, interval, currency,"
        " amount_cents, intro_amount_cents, intro_periods, tax_behavior, accepted_by)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id::text",
        org_id, subscription_id, pq["price_version_id"], quote["plan_key"], quote["interval"], pq["currency"],
        pq["amount_cents"], (pq["intro"] or {}).get("amount_cents"), (pq["intro"] or {}).get("periods"),
        pq["tax_behavior"], accepted_by)


def checkout(ctx: Ctx, plan_key: str, interval: str | None = None, voucher: str | None = None) -> dict:
    p = ctx.principal
    from ..api.billing_routes import code_hash
    with ctx.tx(readonly=True) as c:
        plan = c.one("SELECT * FROM plans WHERE plan_key = $1 AND active", plan_key)
        if not plan or plan["role"] != p.org_kind:
            raise ApiError(404, "not_found", "Plano não disponível para este tipo de organização")
        if plan["requires_flag"]:
            on = c.scalar("SELECT enabled FROM feature_flags WHERE key = $1", plan["requires_flag"])
            if not on:
                raise ApiError(409, "plan_not_available", "Plano ainda não disponível para contratação")
        if plan["price_cents"] == 0 or plan["tier"] == "free":
            raise ApiError(409, "free_plan", "Este plano é gratuito e já está ativo")
        if plan["interval"] == "custom" or plan["tier"] == "gov":
            raise ApiError(409, "quote_required", "Plano sob contrato — solicite proposta comercial")
        interval = interval or (plan["interval"] if plan["interval"] in ("month", "year") else "month")
        if mon.price_for(c, plan, interval) is None:
            raise ApiError(409, "price_not_defined", "Preço ainda não definido para contratação online — solicite proposta comercial ou use um voucher")
        active = _live_sub(c, ctx.org_id)
        if active and active["plan_key"] == plan_key and active.get("interval") in (None, interval):
            raise ApiError(409, "already_subscribed", "A organização já possui este plano")
        if active and active["provider"] == "stripe":
            raise ApiError(409, "use_change_plan", "Já existe assinatura ativa: use a alteração de plano (POST /v1/billing/change-plan)")
    if voucher:
        ctx_hash = code_hash(ctx.settings.voucher_hmac_key, voucher)
        from .ratelimit import hit
        hit(ctx, "voucher_org", ctx.org_id, 10, 3600)
        with ctx.system_tx() as c:
            v = mon.voucher_row(c, ctx_hash)
            org = c.one("SELECT kind, cnpj FROM organizations WHERE id = $1", ctx.org_id)
            if not mon.voucher_usable(c, v, org, ctx.org_id) or v["type"] not in ("percent_off", "amount_off"):
                raise ApiError(404, "voucher_unavailable", "Código inválido, expirado ou não aplicável a esta organização")
            mon.redeem_voucher(c, v, ctx.org_id, ctx.user_id)
            _audit(ctx, c, "voucher.redeemed", "voucher", v["id"], {"type": v["type"], "at": "checkout"})
    with ctx.system_tx() as c:
        q = mon.quote(c, org_id=ctx.org_id, org_kind=p.org_kind, plan_key=plan_key, interval=interval)
        pid = price_ref(ctx.settings, plan_key, q["interval"], conn=c)
    if q.get("price") and not pid and ctx.app.billing.needs_price_id:
        # Preço definido na tabela, mas sem identificador no provedor. Dizer isso é melhor do que tentar e receber
        # um erro opaco do Stripe: o problema é de configuração da conta, e a mensagem precisa apontar para lá.
        #
        # A checagem é CONDICIONADA ao provedor: o provedor de teste (sandbox) não publica preço nenhum, e a minha
        # primeira versão desta trava recusava a contratação até nele — o que quebrou o fluxo de desenvolvimento e
        # de demonstração inteiro. Quem precisa do identificador é quem cobra de verdade.
        raise ApiError(503, "provider_price_missing",
                       "Este preço ainda não está publicado no provedor de pagamento. A contratação online será "
                       "liberada assim que a configuração for concluída.")
    base = ctx.settings.public_base_url
    trial_end = q["first_charge_at"] if not q["charge_now"] else None
    res = ctx.app.billing.create_checkout(org_id=ctx.org_id, plan_key=plan_key, interval=q["interval"], price_id=pid,
                                          success_url=f"{base}/conta/plano?status=sucesso", cancel_url=f"{base}/conta/plano?status=cancelado",
                                          customer_email=p.email, trial_end=trial_end, discount=q["discount"])
    with ctx.system_tx() as c:
        c.run("UPDATE subscriptions SET status = 'expired' WHERE org_id = $1 AND status = 'incomplete'", ctx.org_id)
        trial = c.one("SELECT status, trial_end FROM org_trials WHERE org_id = $1", ctx.org_id)
        if trial and trial["status"] == "canceled" and trial["trial_end"] > mon._now(c):
            c.run("UPDATE org_trials SET status = 'active', canceled_at = NULL, updated_at = now() WHERE org_id = $1", ctx.org_id)   # quem contrata retoma o trial
        if trial_end and trial and trial["trial_end"] < trial_end:
            c.run("UPDATE org_trials SET trial_end = $2, updated_at = now() WHERE org_id = $1", ctx.org_id, trial_end)             # mínimo do Checkout (nunca cobra antes)
        disc = None
        if q["discount"]:
            d = q["discount"]
            disc = {k: d.get(k) for k in ("source", "kind", "value", "duration", "months", "redemption_id", "voucher_id", "agreement_id")}
        if res.get("activate_now"):
            c.run("UPDATE subscriptions SET status = 'canceled', canceled_at = now() WHERE org_id = $1 AND status = ANY($2::text[])", ctx.org_id, list(LIVE))
            in_trial = not q["charge_now"]
            sid = c.scalar("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_checkout_id, interval, amount_cents, discount, trial_end, origin, current_period_end)"
                           " VALUES ($1,$2,$3,'sandbox',$4,$5,$6,$7::jsonb,$8::timestamptz,'sandbox',"
                           " CASE WHEN $8::timestamptz IS NOT NULL THEN $8::timestamptz WHEN $5 = 'year' THEN now() + interval '365 days' ELSE now() + interval '30 days' END) RETURNING id::text",
                           ctx.org_id, plan_key, "trialing" if in_trial else "active", res["checkout_id"], q["interval"], q["final_cents"],
                           Json(disc) if disc else None, trial_end)
            if disc and disc.get("redemption_id"):
                c.run("UPDATE voucher_redemptions SET status = 'consumed', consumed_by_subscription = $2 WHERE id = $1", disc["redemption_id"], sid)
            record_accepted_price(c, org_id=ctx.org_id, subscription_id=sid, quote=q, accepted_by=ctx.user_id)
            res["subscription_id"] = sid
            res["warning"] = "Assinatura SANDBOX: nenhuma cobrança real foi feita."
        else:
            isid = c.scalar("INSERT INTO subscriptions(org_id, plan_key, status, provider, provider_checkout_id, interval, amount_cents, discount, trial_end)"
                            " VALUES ($1,$2,'incomplete',$3,$4,$5,$6,$7::jsonb,$8::timestamptz) RETURNING id::text",
                            ctx.org_id, plan_key, ctx.app.billing.name, res["checkout_id"], q["interval"], q["final_cents"], Json(disc) if disc else None, trial_end)
            # O preço é congelado já na ida ao provedor: é o valor que a pessoa viu na tela antes de clicar.
            record_accepted_price(c, org_id=ctx.org_id, subscription_id=isid, quote=q, accepted_by=ctx.user_id)
        _audit(ctx, c, "billing.checkout_started", "plan", plan_key,
               {"provider": ctx.app.billing.name, "interval": q["interval"], "final_cents": q["final_cents"], "trial": bool(trial_end)})
    res["quote"] = q
    return res


def cancel(ctx: Ctx) -> dict:
    """Cancelar é simples e sem obstáculos: durante o trial não há cobrança e o acesso FULL vai até o fim do teste; pago, até o fim do período."""
    with ctx.tx(readonly=True) as c:
        sub = _live_sub(c, ctx.org_id)
        trial = c.one("SELECT * FROM org_trials WHERE org_id = $1", ctx.org_id)
        now = mon._now(c)
    tv = mon.trial_view(trial, now)
    if sub and sub["provider"] == "manual":
        raise ApiError(409, "contract", "Assinatura sob contrato: solicite o cancelamento ao time comercial")
    if not sub and not (tv and tv["active"] and not tv["canceled"]):
        raise ApiError(404, "not_found", "Nenhuma assinatura ou período de teste ativo")
    if sub and sub.get("cancel_at_period_end"):
        raise ApiError(409, "already_canceled", "O cancelamento já foi solicitado")
    if sub:
        ctx.app.billing.cancel(sub)
    with ctx.system_tx() as c:
        if sub:
            c.run("UPDATE subscriptions SET cancel_at_period_end = true, canceled_at = now(), updated_at = now() WHERE id = $1", sub["id"])
        if tv and tv["active"]:
            c.run("UPDATE org_trials SET status = 'canceled', canceled_at = now(), updated_at = now() WHERE org_id = $1 AND status = 'active'", ctx.org_id)
        end = (tv["trial_end"] if tv and tv["active"] and (not sub or sub["status"] == "trialing") else (sub or {}).get("current_period_end"))
        _audit(ctx, c, "billing.cancel_requested", "subscription", sub["id"] if sub else None, {"in_trial": bool(tv and tv["active"])})
        mon.notify_once(c, ctx.org_id, "cancel_confirmed", str(sub["id"] if sub else "trial"), "Seu cancelamento foi confirmado",
                        f"Você continuará tendo acesso até {mon.fmt_date(end)}.")
    in_trial = bool(tv and tv["active"] and (not sub or sub["status"] == "trialing"))
    msg = ("Você continuará utilizando o acesso FULL gratuitamente até o fim do seu período de teste. Nenhuma cobrança será realizada."
           if in_trial else f"Você continuará tendo acesso até {mon.fmt_date(end)}.")
    return {"status": "cancel_requested", "access_until": end, "charged": False if in_trial else None, "message": msg,
            "data_retention": "Seus dados e histórico financeiro não são apagados; ao fim do acesso a conta passa para o plano gratuito."}


def reactivate(ctx: Ctx) -> dict:
    with ctx.tx(readonly=True) as c:
        sub = _live_sub(c, ctx.org_id)
        trial = c.one("SELECT * FROM org_trials WHERE org_id = $1", ctx.org_id)
        now = mon._now(c)
    tv = mon.trial_view(trial, now)
    if sub and sub.get("cancel_at_period_end") and (sub["current_period_end"] is None or sub["current_period_end"] > now):
        ctx.app.billing.reactivate(sub)
        with ctx.system_tx() as c:
            c.run("UPDATE subscriptions SET cancel_at_period_end = false, canceled_at = NULL, updated_at = now() WHERE id = $1", sub["id"])
            if tv and tv["canceled"]:
                c.run("UPDATE org_trials SET status = 'active', canceled_at = NULL, updated_at = now() WHERE org_id = $1", ctx.org_id)
            _audit(ctx, c, "billing.reactivated", "subscription", sub["id"], {})
        return {"status": "reactivated"}
    if not sub and tv and tv["canceled"]:
        with ctx.system_tx() as c:
            c.run("UPDATE org_trials SET status = 'active', canceled_at = NULL, updated_at = now() WHERE org_id = $1", ctx.org_id)
            _audit(ctx, c, "billing.trial_reactivated", "organization", ctx.org_id, {})
        return {"status": "reactivated"}
    raise ApiError(409, "not_reactivable", "Não há cancelamento em andamento que possa ser desfeito")


def change_plan(ctx: Ctx, plan_key: str, interval: str | None) -> dict:
    """Upgrade/downgrade SINCRONIZADO com o provedor (nunca só `subscription.plan = ...`). Downgrade para FREE = cancelar."""
    with ctx.tx(readonly=True) as c:
        sub = _live_sub(c, ctx.org_id)
        if not sub:
            raise ApiError(409, "no_subscription", "Não há assinatura ativa. Use o checkout para contratar.")
        if sub["provider"] == "manual":
            raise ApiError(409, "contract", "Assinatura sob contrato: solicite a alteração ao time comercial")
        q = mon.quote(c, org_id=ctx.org_id, org_kind=ctx.principal.org_kind, plan_key=plan_key, interval=interval)
    if sub["plan_key"] == plan_key and (sub.get("interval") or q["interval"]) == q["interval"]:
        raise ApiError(409, "same_plan", "Esta já é a sua assinatura atual")
    with ctx.system_tx() as c:
        pid = price_ref(ctx.settings, plan_key, q["interval"], conn=c)
    ctx.app.billing.change_plan(sub, price_id=pid, plan_key=plan_key, interval=q["interval"])
    with ctx.system_tx() as c:
        c.run("UPDATE subscriptions SET plan_key = $2, interval = $3, amount_cents = $4, updated_at = now() WHERE id = $1", sub["id"], plan_key, q["interval"], q["final_cents"])
        _audit(ctx, c, "billing.plan_changed", "subscription", sub["id"], {"from": sub["plan_key"], "to": plan_key, "interval": q["interval"]})
    return {"status": "changed", "plan_key": plan_key, "interval": q["interval"], "quote": q,
            "note": "O provedor aplica a diferença proporcional (proration) na próxima fatura."}


def portal(ctx: Ctx) -> dict:
    with ctx.tx(readonly=True) as c:
        sub = c.one("SELECT * FROM subscriptions WHERE org_id = $1 AND provider = $2 AND provider_customer_id IS NOT NULL ORDER BY created_at DESC LIMIT 1", ctx.org_id, ctx.app.billing.name)
    if not sub:
        raise ApiError(409, "no_customer", "Ainda não há método de pagamento cadastrado: contrate um plano primeiro")
    return ctx.app.billing.portal(sub, f"{ctx.settings.public_base_url}/conta/plano")


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
    # `signature_verified=True` chega aqui e em nenhum outro lugar: é a única função que confere a
    # assinatura. Quem chamar `process_event` por outro caminho grava o evento com a assinatura NÃO
    # conferida, e o CHECK billing_events_signature_effect impede que ele chegue a `processed`.
    return process_event(app_state, "stripe", event, signature_verified=True)


def _sub_by_provider(c, obj: dict):
    """Acha nossa assinatura pelo id do provedor; se o evento chegou antes do checkout.session.completed, associa pela org dos metadados."""
    row = c.one("SELECT id, org_id::text AS org_id, status, trial_end, last_event_at, plan_key FROM subscriptions WHERE provider_subscription_id = $1", obj.get("id"))
    if row:
        return row
    org = (obj.get("metadata") or {}).get("org_id")
    if org:
        row = c.one("SELECT id, org_id::text AS org_id, status, trial_end, last_event_at, plan_key FROM subscriptions WHERE org_id::text = $1 AND status = 'incomplete'"
                    " AND provider = 'stripe' ORDER BY created_at DESC LIMIT 1 FOR UPDATE", org)
        if row:
            c.run("UPDATE subscriptions SET provider_subscription_id = $2, provider_customer_id = coalesce(provider_customer_id, $3) WHERE id = $1", row["id"], obj.get("id"), obj.get("customer"))
    return row


def process_event(app_state, provider: str, event: dict, *,
                  signature_verified: bool = False) -> tuple[int, dict]:
    eid, etype = str(event.get("id", "")), str(event.get("type", ""))
    if not eid or not etype:
        return 400, {"error": "evento inválido"}
    obj = (event.get("data") or {}).get("object") or {}
    created = event.get("created")
    with app_state.pool.tx(DbContext(system=True)) as c:
        inserted = c.one("INSERT INTO billing_events(provider, event_id, type, payload, signature_verified)"
                         " VALUES ($1,$2,$3,$4::jsonb,$5)"
                         " ON CONFLICT (provider, event_id) DO NOTHING RETURNING id", provider, eid, etype, Json(event),
                         signature_verified)
        if not inserted:
            # Reentrega do MESMO evento: o UNIQUE já impediu o efeito; o contador existe para a
            # reconciliação enxergar que houve reentrega (v0.17.0).
            c.run("UPDATE billing_events SET duplicate_count = duplicate_count + 1 WHERE provider = $1 AND event_id = $2",
                  provider, eid)
            return 200, {"status": "duplicate_ignored"}
        if not signature_verified:
            c.run("UPDATE billing_events SET status = 'rejected_signature', processed_at = now() WHERE id = $1", inserted["id"])
            log(logger, logging.WARNING, "billing_event_without_verified_signature", provider=provider, event_id=eid)
            return 202, {"status": "rejected_signature"}
        status = "processed"
        if etype == "checkout.session.completed":
            md = obj.get("metadata") or {}
            row = c.one("SELECT id, trial_end FROM subscriptions WHERE provider_checkout_id = $1 AND org_id::text = $2 AND plan_key = $3 FOR UPDATE",
                        obj.get("id"), md.get("org_id", ""), md.get("plan_key", ""))
            if row:
                # encerra as outras ANTES de ativar (no máximo uma assinatura vigente por organização)
                c.run("UPDATE subscriptions SET status = 'canceled', canceled_at = now() WHERE org_id::text = $1 AND status IN ('active','trialing','past_due') AND id <> $2", md.get("org_id", ""), row["id"])
                in_trial = row["trial_end"] is not None and c.scalar("SELECT $1::timestamptz > now()", row["trial_end"])
                c.run("UPDATE subscriptions SET status = $2, provider_customer_id = $3, provider_subscription_id = coalesce(provider_subscription_id, $4), updated_at = now() WHERE id = $1",
                      row["id"], "trialing" if in_trial else "active", obj.get("customer"), obj.get("subscription"))
                c.run("UPDATE voucher_redemptions SET status = 'consumed', consumed_by_subscription = $1 WHERE id::text = (SELECT discount->>'redemption_id' FROM subscriptions WHERE id = $1)"
                      " AND status = 'pending_discount'", row["id"])
            else:
                status = "ignored"
        elif etype in ("customer.subscription.updated", "customer.subscription.deleted", "customer.subscription.created"):
            row = _sub_by_provider(c, obj)
            if not row:
                status = "ignored"
            elif created and row["last_event_at"] and c.scalar("SELECT to_timestamp($1::bigint) < $2::timestamptz", created, row["last_event_at"]):
                status = "ignored"         # evento fora de ordem (mais antigo que o último aplicado)
            else:
                st = "canceled" if etype.endswith("deleted") else _STATUS_MAP.get(obj.get("status"), "past_due")
                md = obj.get("metadata") or {}
                interval = ((obj.get("items") or {}).get("data") or [{}])[0].get("price", {}).get("recurring", {}).get("interval") or md.get("interval")
                c.run("UPDATE subscriptions SET status = $2, current_period_end = CASE WHEN $3::bigint IS NULL THEN current_period_end ELSE to_timestamp($3::bigint) END,"
                      " cancel_at_period_end = $4, trial_end = CASE WHEN $5::bigint IS NULL THEN trial_end ELSE to_timestamp($5::bigint) END,"
                      " plan_key = coalesce((SELECT plan_key FROM plans WHERE plan_key = $6 AND active), plan_key),"
                      " interval = CASE WHEN $7 IN ('month','year') THEN $7 ELSE interval END, last_event_at = CASE WHEN $8::bigint IS NULL THEN last_event_at ELSE to_timestamp($8::bigint) END,"
                      " canceled_at = CASE WHEN $4 OR $2 = 'canceled' THEN coalesce(canceled_at, now()) ELSE NULL END, updated_at = now() WHERE id = $1",
                      row["id"], st, obj.get("current_period_end"), bool(obj.get("cancel_at_period_end")), obj.get("trial_end"), md.get("plan_key"), interval, created)
                if st == "active":
                    c.run("UPDATE org_trials SET status = 'converted', updated_at = now() WHERE org_id::text = $1 AND status IN ('active','canceled')", row["org_id"])
                if st in ("canceled", "expired"):
                    c.run("UPDATE org_trials SET status = 'ended', updated_at = now() WHERE org_id::text = $1 AND status IN ('active','canceled')", row["org_id"])
        elif etype == "customer.subscription.trial_will_end":
            row = _sub_by_provider(c, obj)
            if row and not obj.get("cancel_at_period_end"):
                mon.notify_once(c, row["org_id"], "trial_will_end", str(obj.get("id")), "Seu período de teste termina em 3 dias", "A primeira cobrança ocorrerá ao fim do teste. Você pode cancelar antes, sem custo.")
            else:
                status = "ignored" if not row else status
        elif etype in ("invoice.paid", "invoice.payment_failed", "invoice.finalized", "invoice.payment_action_required"):
            sub = c.one("SELECT id, org_id, status FROM subscriptions WHERE provider_subscription_id = $1", obj.get("subscription"))
            if sub:
                inv_status = {"invoice.paid": "paid", "invoice.payment_failed": "open", "invoice.finalized": "open", "invoice.payment_action_required": "open"}[etype]
                c.run("INSERT INTO invoices(org_id, subscription_id, provider, provider_invoice_id, amount_cents, currency, status, paid_at, hosted_url)"
                      " VALUES ($1,$2,'stripe',$3,$4,upper($5),$6, CASE WHEN $6 = 'paid' THEN now() END, $7)"
                      " ON CONFLICT (provider_invoice_id) DO UPDATE SET status = CASE WHEN invoices.status = 'paid' THEN 'paid' ELSE EXCLUDED.status END,"
                      " paid_at = coalesce(invoices.paid_at, EXCLUDED.paid_at)",
                      sub["org_id"], sub["id"], obj.get("id"), int(obj.get("amount_paid") or obj.get("amount_due") or 0),
                      obj.get("currency") or "brl", inv_status, obj.get("hosted_invoice_url"))
                org = str(sub["org_id"])
                if etype == "invoice.paid":
                    c.run("UPDATE subscriptions SET payment_issue = NULL, status = CASE WHEN status IN ('past_due','incomplete') THEN 'active' ELSE status END, updated_at = now() WHERE id = $1", sub["id"])
                    # Cada fatura paga consome um período de ENTRADA, até acabarem. O limite é um CHECK da tabela
                    # (`intro_used_within`), então nem um webhook reprocessado passa do número contratado — e o
                    # `least(...)` evita que a corrida entre dois eventos estoure a restrição.
                    c.run("UPDATE subscription_prices SET intro_periods_used = least(intro_periods_used + 1,"
                          " intro_periods) WHERE org_id = $1 AND ends_at IS NULL AND intro_periods IS NOT NULL"
                          " AND intro_periods_used < intro_periods", sub["org_id"])
                    if int(obj.get("amount_paid") or 0) > 0:     # 1º pagamento confirmado (notify_once evita repetir nas renovações)
                        c.run("UPDATE org_trials SET status = 'converted', updated_at = now() WHERE org_id = $1 AND status IN ('active','canceled')", sub["org_id"])
                        mon.notify_once(c, org, "plan_activated", str(sub["id"]), "Seu plano foi ativado", "O pagamento foi confirmado. Obrigado!")
                elif etype == "invoice.payment_failed":
                    c.run("UPDATE subscriptions SET status = 'past_due', payment_issue = 'payment_failed', updated_at = now() WHERE id = $1", sub["id"])
                    mon.notify_once(c, org, "payment_failed", str(obj.get("id")), "Não conseguimos processar seu pagamento", "Atualize o método de pagamento para manter o plano. Seus dados continuam preservados.")
                elif etype == "invoice.payment_action_required":
                    c.run("UPDATE subscriptions SET payment_issue = 'action_required', updated_at = now() WHERE id = $1", sub["id"])
                    mon.notify_once(c, org, "action_required", str(obj.get("id")), "Seu pagamento precisa de confirmação", "Seu banco pede uma autenticação adicional. Abra o portal de pagamento para concluir.")
            else:
                status = "ignored"
        else:
            status = "ignored"      # invoice.created e payment_intent.*: redundantes para assinaturas (as faturas/assinatura já cobrem o estado)
        c.run("UPDATE billing_events SET status = $2, processed_at = now() WHERE id = $1", inserted["id"], status)
    return 200, {"status": status}
