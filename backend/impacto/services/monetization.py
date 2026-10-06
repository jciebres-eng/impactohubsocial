"""Monetização SaaS (v0.11.0): trial de 14 dias, preço calculado no servidor, descontos (voucher/convênio), convênios e avisos.

Princípios (docs/billing.md):
* a autoridade financeira é o servidor + o provedor (Stripe/webhooks): o cliente NUNCA envia plano, preço, desconto ou direito;
* a cobrança nunca ocorre antes do fim do trial; sem preço definido pelo proprietário não há contratação online (nada é inventado);
* trial é por organização (a plataforma é por organização), no máximo um, com anti-abuso por HMAC (sem guardar e-mail/CNPJ em claro);
* nenhum plano, trial, voucher ou convênio altera match, elegibilidade ou ranking (teste de arquitetura).
"""
from __future__ import annotations

import hashlib
import hmac
import math
from datetime import datetime, timedelta, timezone

from ..db.pool import DbContext
from ..http import ApiError

TIER_ORDER = {"free": 0, "plus": 1, "premium": 2, "gov": 3}
TIER_LABEL = {"free": "FREE", "plus": "PLUS", "premium": "PREMIUM (FULL)", "gov": "GOV / INSTITUCIONAL"}
DEFAULT_REMINDER_DAYS = (1, 7, 11, 13, 14)
STRIPE_TRIAL_MIN = timedelta(hours=48, minutes=5)      # Checkout exige trial_end com antecedência mínima (ver docs/billing.md — verificar na conta real)


# ------------------------------------------------------------------------------------------------ identidade (anti-abuso do trial)
def normalize_email(email: str) -> str:
    """Normaliza alias do mesmo remetente: minúsculas, remove +tag e pontos em domínios que os ignoram (gmail/googlemail)."""
    local, _, domain = (email or "").strip().lower().partition("@")
    local = local.split("+", 1)[0]
    if domain in ("gmail.com", "googlemail.com"):
        local, domain = local.replace(".", ""), "gmail.com"
    return f"{local}@{domain}"


def identity_hash(secret: str, kind: str, value: str) -> str:
    return hmac.new(secret.encode(), f"trial:{kind}:{value}".encode(), hashlib.sha256).hexdigest()


def _now(c) -> datetime:
    return c.scalar("SELECT now()")


# ------------------------------------------------------------------------------------------------ trial
def trial_plan_for(c, org_kind: str) -> dict | None:
    """Plano liberado no trial: o de tier PREMIUM do tipo da organização (contratação por assinatura, ativo e com flag ligada)."""
    return c.one("SELECT p.plan_key, p.name FROM plans p WHERE p.active AND p.role = $1 AND p.tier = 'premium' AND p.interval <> 'custom'"
                 " AND (p.requires_flag IS NULL OR coalesce((SELECT enabled FROM feature_flags f WHERE f.key = p.requires_flag), false))"
                 " ORDER BY p.plan_key LIMIT 1", org_kind)


def start_trial(c, settings, *, org_id: str, org_kind: str, email: str | None, cnpj: str | None, user_id: str | None,
                source: str = "signup", days: int | None = None, force: bool = False) -> dict:
    """Inicia o trial (idempotente por organização). Retorna {started, reason?, trial?}. Chamar em contexto de sistema."""
    if source == "signup" and not settings.trial_auto_start:
        return {"started": False, "reason": "disabled"}
    plan = trial_plan_for(c, org_kind)
    if not plan:
        return {"started": False, "reason": "no_trial_plan_for_kind"}
    if c.one("SELECT 1 FROM org_trials WHERE org_id = $1", org_id):
        return {"started": False, "reason": "trial_already_used"}
    claims = []
    if email:
        claims.append(("email", identity_hash(settings.secret_key, "email", normalize_email(email))))
    if cnpj:
        claims.append(("cnpj", identity_hash(settings.secret_key, "cnpj", cnpj)))
    if not force:
        for kind, h in claims:
            if c.one("SELECT 1 FROM trial_claims WHERE kind = $1 AND identity_hash = $2", kind, h):
                return {"started": False, "reason": "trial_already_used"}
    for kind, h in claims:
        c.run("INSERT INTO trial_claims(kind, identity_hash, org_id) VALUES ($1,$2,$3) ON CONFLICT (kind, identity_hash) DO NOTHING", kind, h, org_id)
    n = int(days or settings.trial_days)
    c.run("INSERT INTO org_trials(org_id, plan_key, source, trial_start, trial_end, created_by) VALUES ($1,$2,$3, now(), now() + make_interval(days => $4::int), $5)",
          org_id, plan["plan_key"], source, n, user_id)
    notify_once(c, org_id, "trial_started", "1", "Seu teste de 14 dias começou" if n == 14 else f"Seu teste de {n} dias começou",
                "Você tem acesso completo e não será cobrado durante o período de teste.")
    return {"started": True, "plan_key": plan["plan_key"], "days": n}


def trial_view(row: dict | None, now: datetime, *, has_paid_sub: bool = False) -> dict | None:
    if not row:
        return None
    end = row["trial_end"]
    left_s = (end - now).total_seconds()
    active = row["status"] in ("active", "canceled") and left_s > 0
    days_left = max(0, math.ceil(left_s / 86400)) if active else 0
    return {"status": row["status"], "plan_key": row["plan_key"], "source": row["source"], "trial_start": row["trial_start"], "trial_end": end,
            "active": active, "canceled": row["status"] == "canceled", "days_left": days_left, "ends_today": active and left_s <= 86400,
            "will_convert": active and row["status"] == "active" and has_paid_sub}


def notify_once(c, org_id: str, kind: str, ref: str, title: str, body: str, link: str = "/conta/plano") -> bool:
    """Um aviso por (organização, tipo, referência) — evita spam em reprocessamentos de webhook/jobs."""
    if not c.one("INSERT INTO billing_notices(org_id, kind, ref) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING RETURNING 1 AS ok", org_id, kind, ref):
        return False
    c.scalar("SELECT app_notify($1, NULL, $2, $3, $4, $5)", org_id, "billing." + kind, title, body, link)
    return True


# ------------------------------------------------------------------------------------------------ preço e desconto (servidor é a autoridade)
#: Moeda padrão da tabela de preços. Vive aqui porque é decisão de produto, não de cada chamada — e porque o cliente
#: NUNCA escolhe a moeda da cobrança: escolher moeda é escolher preço.
DEFAULT_CURRENCY = "USD"


def price_version(c, plan_key: str, interval: str, currency: str = DEFAULT_CURRENCY) -> dict | None:
    """Versão de preço VIGENTE (v0.16.0). A autoridade é `plan_price_versions`, com vigência e moeda.

    Precedência, do mais específico ao mais antigo:
      1. `plan_price_versions` vigente agora — tem moeda, preço de entrada, imposto e identificador no provedor;
      2. `plan_prices` (v0.11.0) — sem moeda e sem vigência, mantida para não quebrar instalação que a preencheu;
      3. `plans.price_cents` — legado da v0.10.0.
    A ordem é deliberada: quem configurou a tabela nova manda. Devolver `None` significa "sem preço definido", e o
    checkout recusa com mensagem explícita em vez de inventar valor.
    """
    r = c.one("SELECT id::text AS id, plan_key, interval, currency, amount_cents, intro_amount_cents,"
              " intro_periods, trial_days, tax_behavior, provider, provider_price_id, provider_intro_price_id,"
              " effective_from, reason FROM price_current($1,$2,$3)", plan_key, interval, currency)
    return r if r and r["amount_cents"] is not None else None


def price_for(c, plan: dict, interval: str, currency: str = DEFAULT_CURRENCY) -> int | None:
    """Valor REGULAR, em centavos. O preço de entrada não entra aqui — ver `price_quote`."""
    v = price_version(c, plan["plan_key"], interval, currency)
    if v:
        return int(v["amount_cents"])
    r = c.one("SELECT amount_cents FROM plan_prices WHERE plan_key = $1 AND interval = $2 AND active", plan["plan_key"], interval)
    if r and r["amount_cents"] is not None:
        return int(r["amount_cents"])
    if plan.get("price_cents") and plan.get("interval") == interval:      # legado (plans.price_cents)
        return int(plan["price_cents"])
    return None


def monthly_equivalent(amount_cents: int, interval: str) -> int:
    """Quanto dá por mês. Para anual, é o valor dividido por 12 — e o TOTAL continua sendo mostrado ao lado.

    Mostrar só o equivalente mensal de um plano anual é o padrão escuro clássico ("US$ 14,99/mês" cobrando
    US$ 179,88 de uma vez). A plataforma mostra os dois, sempre, e esta função existe para que o número de cima seja
    calculado e não escrito à mão.
    """
    return round(amount_cents / 12) if interval == "year" else amount_cents


def price_quote(c, plan_key: str, interval: str, currency: str = DEFAULT_CURRENCY) -> dict | None:
    """O que a pessoa vai pagar, em palavras completas: entrada, quando muda, e o preço depois.

    Esta é a função que a tela de preço e o checkout usam. Ela devolve TUDO o que precisa estar escrito antes de
    alguém pagar — porque "não é padrão escuro se está escrito antes de pagar" só vale se estiver, de fato, escrito.
    """
    v = price_version(c, plan_key, interval, currency)
    if not v:
        return None
    regular = int(v["amount_cents"])
    intro = v["intro_amount_cents"]
    periods = v["intro_periods"]
    unit = "mês" if interval == "month" else "ano"
    out = {
        "price_version_id": v["id"], "currency": v["currency"], "interval": interval,
        "amount_cents": regular, "monthly_equivalent_cents": monthly_equivalent(regular, interval),
        "tax_behavior": v["tax_behavior"],
        "tax_note": {"inclusive": "Imposto incluído no valor.",
                     "exclusive": "Imposto calculado no fechamento, conforme o seu país.",
                     "unspecified": "Imposto não declarado nesta tabela."}[v["tax_behavior"]],
        "trial_days": v["trial_days"],
        "provider_configured": bool(v["provider_price_id"]),
        "intro": None,
        "total_note": (f"Total de {_money(regular, v['currency'])} por ano."
                       if interval == "year" else f"{_money(regular, v['currency'])} por mês."),
    }
    if intro is not None and periods:
        out["intro"] = {
            "amount_cents": int(intro), "periods": int(periods),
            "then_amount_cents": regular,
            "summary": (f"{_money(int(intro), v['currency'])} por {unit} nos primeiros {periods} "
                        f"{'meses' if interval == 'month' else 'anos'} pagos, "
                        f"depois {_money(regular, v['currency'])} por {unit}."),
            "total_intro_cents": int(intro) * int(periods),
        }
    return out


def _money(cents: int, currency: str) -> str:
    """Valor legível. Separador por moeda; nada de formatar dólar com vírgula de real."""
    if currency == "BRL":
        return "R$ " + f"{cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    sym = {"USD": "US$ ", "EUR": "€ "}.get(currency, currency + " ")
    return sym + f"{cents / 100:,.2f}"


def annual_savings(monthly: int | None, yearly: int | None) -> dict | None:
    """Economia REAL entre os valores configurados (nunca inventada)."""
    if not monthly or not yearly or yearly >= monthly * 12:
        return None
    cents = monthly * 12 - yearly
    return {"cents": cents, "percent": round(100 * cents / (monthly * 12))}


def _discount_amount(base: int, kind: str, value: int) -> int:
    d = round(base * value / 100) if kind == "percent" else value
    return max(0, min(base, int(d)))


def candidate_discounts(c, org_id: str, plan_key: str, base: int, extra_voucher: dict | None = None) -> list[dict]:
    out = []
    rows = c.query("SELECT r.id::text AS rid, v.id::text AS vid, v.type, v.value, v.plan_key, v.discount_duration, v.discount_months FROM voucher_redemptions r"
                   " JOIN vouchers v ON v.id = r.voucher_id WHERE r.org_id = $1 AND r.status = 'pending_discount' AND v.type IN ('percent_off','amount_off')", org_id)
    for r in rows:
        if r["plan_key"] and r["plan_key"] != plan_key:
            continue
        kind, val = ("percent", int((r["value"] or {}).get("percent", 0))) if r["type"] == "percent_off" else ("amount", int((r["value"] or {}).get("amount_cents", 0)))
        if val > 0:
            out.append({"source": "voucher", "redemption_id": r["rid"], "voucher_id": r["vid"], "kind": kind, "value": val,
                        "duration": r["discount_duration"] or "once", "months": r["discount_months"],
                        "discount_cents": _discount_amount(base, kind, val)})
    ag = c.query("SELECT a.id::text AS id, a.discount_percent FROM agreement_members m JOIN agreements a ON a.id = m.agreement_id"
                 " WHERE m.org_id = $1 AND m.status = 'active' AND a.status = 'active' AND a.discount_percent IS NOT NULL"
                 " AND (a.valid_from IS NULL OR a.valid_from <= now()) AND (a.valid_until IS NULL OR a.valid_until > now())", org_id)
    for a in ag:
        out.append({"source": "agreement", "agreement_id": a["id"], "kind": "percent", "value": int(a["discount_percent"]), "duration": "forever", "months": None,
                    "discount_cents": _discount_amount(base, "percent", int(a["discount_percent"]))})
    return out


def best_discount(c, org_id: str, plan_key: str, base: int) -> dict | None:
    """Um único desconto (o maior); descontos não se acumulam."""
    cands = candidate_discounts(c, org_id, plan_key, base)
    return max(cands, key=lambda d: d["discount_cents"]) if cands else None


def quote(c, *, org_id: str, org_kind: str, plan_key: str, interval: str | None, settings=None) -> dict:
    plan = c.one("SELECT * FROM plans WHERE plan_key = $1 AND active", plan_key)
    if not plan or plan["role"] != org_kind:
        raise ApiError(404, "not_found", "Plano não disponível para este tipo de organização")
    if plan["tier"] in ("free", "gov") or plan["interval"] == "custom" or plan["price_cents"] == 0:
        raise ApiError(409, "quote_required" if plan["tier"] == "gov" or plan["interval"] == "custom" else "free_plan",
                       "Plano sob contrato — solicite proposta comercial" if plan["tier"] == "gov" or plan["interval"] == "custom" else "Este plano é gratuito e já está ativo")
    if plan["requires_flag"] and not c.scalar("SELECT enabled FROM feature_flags WHERE key = $1", plan["requires_flag"]):
        raise ApiError(409, "plan_not_available", "Plano ainda não disponível para contratação")
    interval = interval or (plan["interval"] if plan["interval"] in ("month", "year") else "month")
    pq = price_quote(c, plan_key, interval)
    base = int(pq["amount_cents"]) if pq else price_for(c, plan, interval)
    if base is None:
        raise ApiError(409, "price_not_defined", "Preço ainda não definido para contratação online — solicite proposta comercial ou use um voucher")
    # PREÇO DE ENTRADA E VOUCHER NÃO EMPILHAM — quem paga leva o melhor dos dois.
    #
    # A decisão apareceu num teste antigo que falhou: com a promoção de entrada, um voucher de 20% passou a valer
    # 20% de US$ 1,99 (US$ 0,40) em vez de 20% de US$ 19,99 (US$ 4,00). Quem usa o código espera o desconto sobre o
    # preço do plano, não sobre uma promoção que já está ali. Empilhar os dois também não serve: daria desconto
    # sobre desconto, e a conta deixaria de ser explicável.
    #
    # A regra é: calcula-se o desconto sobre o preço REGULAR e cobra-se o MENOR entre esse valor e o preço de
    # entrada. Nunca é pior para quem paga do que qualquer das duas opções isoladas, e cabe numa frase na tela.
    disc = best_discount(c, org_id, plan_key, base)
    discounted = max(0, base - (disc["discount_cents"] if disc else 0))
    intro_cents = int(pq["intro"]["amount_cents"]) if (pq and pq["intro"]) else None
    if intro_cents is not None and intro_cents < discounted:
        final, applied = intro_cents, "intro"
    else:
        final, applied = discounted, ("voucher" if disc else "regular")
    now = _now(c)
    trial = c.one("SELECT * FROM org_trials WHERE org_id = $1", org_id)
    tv = trial_view(trial, now)
    if tv and tv["active"]:
        first = tv["trial_end"]
        if first - now < STRIPE_TRIAL_MIN:       # mínimo do Checkout: estende o trial só o necessário; nunca cobra antes
            first = now + STRIPE_TRIAL_MIN
    else:
        first = now
    other = "year" if interval == "month" else "month"
    other_price = price_for(c, plan, other)
    sav = annual_savings(base if interval == "month" else other_price, other_price if interval == "month" else base)
    currency = pq["currency"] if pq else "BRL"
    note = ("Valor calculado no servidor. Com período de teste ativo, a primeira cobrança só ocorre após o fim do "
            "teste.")
    if pq and pq["intro"]:
        note += " " + pq["intro"]["summary"]
    if intro_cents is not None and disc:
        note += (" Promoção de entrada e código de desconto não se somam: aplicamos o mais vantajoso para você"
                 f" ({'promoção de entrada' if applied == 'intro' else 'código de desconto'}).")
    return {"plan_key": plan_key, "plan_name": plan["name"], "tier": plan["tier"], "interval": interval,
            "currency": currency,
            # `base_cents` é o preço REGULAR; `first_cents` é o que sai na primeira fatura. Separar os dois é o que
            # impede a tela de dizer "US$ 1,99" e a cobrança seguinte surpreender.
            "base_cents": base, "first_cents": final, "discount": disc, "final_cents": final,
            "first_price_source": applied, "intro_cents": intro_cents, "discounted_cents": discounted,
            "first_charge_at": first, "charge_now": not (tv and tv["active"]),
            "trial": tv, "annual_savings": sav, "price": pq,
            "tax_behavior": pq["tax_behavior"] if pq else "unspecified",
            "provider_configured": bool(pq and pq["provider_configured"]),
            "note": note}


# ------------------------------------------------------------------------------------------------ vouchers (validação compartilhada)
def voucher_row(c, code_hash: str):
    return c.one("SELECT v.*, v.id::text AS id, b.status AS batch_status FROM vouchers v JOIN voucher_batches b ON b.id = v.batch_id"
                 " WHERE v.code_hash = $1 FOR UPDATE OF v", code_hash)


def voucher_usable(c, v: dict | None, org: dict, org_id: str) -> bool:
    return bool(v and v["status"] == "active" and v["batch_status"] == "active" and v["redeemed_count"] < v["max_redemptions"]
                and (v["valid_from"] is None or c.scalar("SELECT $1::timestamptz <= now()", v["valid_from"]))
                and (v["valid_until"] is None or c.scalar("SELECT $1::timestamptz > now()", v["valid_until"]))
                and (not v["scope_roles"] or org["kind"] in v["scope_roles"])
                and (not v["scope_cnpj"] or v["scope_cnpj"] == org["cnpj"])
                and (not v.get("organization_id") or str(v["organization_id"]) == org_id)
                and not c.one("SELECT 1 FROM voucher_redemptions WHERE voucher_id = $1 AND org_id = $2", v["id"], org_id))


def redeem_voucher(c, v: dict, org_id: str, user_id: str) -> str:
    """Aplica o voucher (já validado, linha travada): licença/recurso viram grant; desconto parcial fica PENDENTE até o checkout; 100% vira licença."""
    typ = v["type"]
    full_discount = typ == "percent_off" and int((v["value"] or {}).get("percent", 0)) >= 100
    status = "pending_discount" if typ in ("percent_off", "amount_off") and not full_discount else "applied"
    c.run("INSERT INTO voucher_redemptions(voucher_id, org_id, redeemed_by, status) VALUES ($1,$2,$3,$4)", v["id"], org_id, user_id, status)
    c.run("UPDATE vouchers SET redeemed_count = redeemed_count + 1, status = CASE WHEN redeemed_count + 1 >= max_redemptions THEN 'exhausted' ELSE status END WHERE id = $1", v["id"])
    if typ in ("grant_plan", "grant_feature", "free_period") or full_discount:
        c.run("INSERT INTO entitlement_grants(org_id, plan_key, feature_key, source, source_ref, reason, ends_at)"
              " VALUES ($1,$2,$3,'voucher',$4,'Voucher', CASE WHEN $5::int IS NULL THEN NULL ELSE now() + make_interval(days => $5::int) END)",
              org_id, v["plan_key"], v["feature_key"], v["id"], v["duration_days"])
    return status


# ------------------------------------------------------------------------------------------------ convênios
def join_agreement(c, *, code_hash: str, org_id: str, user_id: str, user_email: str, email_verified: bool, org_kind: str) -> dict:
    generic = ApiError(404, "agreement_unavailable", "Código inválido, expirado ou não aplicável a esta organização")
    a = c.one("SELECT * FROM agreements WHERE code_hash = $1 FOR UPDATE", code_hash)
    if not a or a["status"] != "active":
        raise generic
    now = _now(c)
    if (a["valid_from"] and a["valid_from"] > now) or (a["valid_until"] and a["valid_until"] <= now):
        raise generic
    if a["seats_used"] >= a["seats"]:
        raise ApiError(409, "agreement_full", "Todas as vagas deste convênio foram utilizadas. Fale com o responsável pelo convênio.")
    if a["email_domains"]:
        # domínio SÓ restringe quem pode entrar e exige e-mail verificado; o código continua obrigatório (nunca autentica só por domínio)
        domain = user_email.lower().rsplit("@", 1)[-1]
        if not email_verified or domain not in [d.lower() for d in a["email_domains"]]:
            raise generic
    plan = c.one("SELECT role FROM plans WHERE plan_key = $1", a["plan_key"]) if a["plan_key"] else None
    if plan and plan["role"] != org_kind:
        raise generic
    if c.one("SELECT 1 FROM agreement_members WHERE agreement_id = $1 AND org_id = $2", a["id"], org_id):
        raise ApiError(409, "already_member", "Esta organização já participa do convênio")
    grant_id = None
    if a["plan_key"]:
        grant_id = c.scalar(
            "INSERT INTO entitlement_grants(org_id, plan_key, source, source_ref, agreement_id, reason, ends_at)"
            " VALUES ($1,$2,$3,$4,$4, $5, CASE WHEN $6::int IS NOT NULL THEN now() + make_interval(days => $6::int) ELSE $7::timestamptz END) RETURNING id::text",
            org_id, a["plan_key"], "gov" if a["kind"] == "gov" else ("partner" if a["kind"] == "partner" else "convention"), a["id"],
            f"Convênio: {a['name']}", a["grant_days"], a["valid_until"])
    c.run("INSERT INTO agreement_members(agreement_id, org_id, joined_by, grant_id) VALUES ($1,$2,$3,$4)", a["id"], org_id, user_id, grant_id)
    c.run("UPDATE agreements SET seats_used = seats_used + 1, updated_at = now() WHERE id = $1", a["id"])
    return {"agreement_id": str(a["id"]), "name": a["name"], "plan_key": a["plan_key"], "discount_percent": a["discount_percent"],
            "ends_at": c.scalar("SELECT ends_at FROM entitlement_grants WHERE id = $1", grant_id) if grant_id else None}


# ------------------------------------------------------------------------------------------------ avisos para a interface (textos do produto)
def fmt_date(d: datetime | None) -> str:
    return d.astimezone(timezone(timedelta(hours=-4))).strftime("%d/%m/%Y") if d else "—"      # America/Cuiaba


def billing_notices(*, trial: dict | None, sub: dict | None, now: datetime) -> list[dict]:
    """Mensagens claras, sem esconder informação importante (checkout, trial, cancelamento, falha de pagamento)."""
    out: list[dict] = []
    paid = sub and sub["status"] in ("active", "trialing", "past_due")
    if trial and trial["active"]:
        if trial["canceled"] or (sub and sub.get("cancel_at_period_end")):
            out.append({"level": "info", "code": "trial_canceled", "text": f"Seu acesso FULL permanece ativo até {fmt_date(trial['trial_end'])}. Nenhuma cobrança será realizada."})
        else:
            n = trial["days_left"]
            out.append({"level": "info", "code": "trial_active", "text": "Você está no período de teste gratuito de 14 dias." if (trial["trial_end"] - trial["trial_start"]).days == 14
                        else "Você está no período de teste gratuito."})
            out.append({"level": "info", "code": "no_charge", "text": "Você não será cobrado durante o período de teste."})
            out.append({"level": "warn" if n <= 3 else "info", "code": "trial_days",
                        "text": "Seu período de teste termina hoje." if trial["ends_today"] else f"Seu período de teste termina em {n} dia{'s' if n != 1 else ''}."})
            if paid:
                out.append({"level": "info", "code": "first_charge", "text": f"Primeira cobrança: {fmt_date(trial['trial_end'])}"})
            else:
                out.append({"level": "info", "code": "choose_plan", "text": f"Para manter o acesso completo após {fmt_date(trial['trial_end'])}, escolha um plano. "
                            "Sem isso, sua conta passa para o plano gratuito, sem cobrança e sem perder dados."})
    if sub and sub.get("cancel_at_period_end") and sub["status"] in ("active", "trialing", "past_due"):
        out.append({"level": "info", "code": "cancel_scheduled", "text": f"Você continuará tendo acesso até {fmt_date(sub['current_period_end'])}."})
    if sub and sub.get("payment_issue") == "payment_failed" or (sub and sub["status"] == "past_due"):
        out.append({"level": "error", "code": "payment_failed", "text": "Não conseguimos processar seu pagamento. Atualize o método de pagamento para manter o plano."})
    if sub and sub.get("payment_issue") == "action_required":
        out.append({"level": "error", "code": "action_required", "text": "Seu banco pede uma confirmação adicional para concluir o pagamento. Abra o portal de pagamento para confirmar."})
    return out


# ------------------------------------------------------------------------------------------------ rotinas periódicas (jobs)
def lifecycle_job(app) -> dict:
    """Lembretes do trial (dias 1, 7, 11, 13 e 14), encerramento de trials, conversão de sandbox e fim de períodos cancelados."""
    reminders = ended = converted_sbx = expired = 0
    cfg_days = set(getattr(app, "trial_reminder_days", None) or DEFAULT_REMINDER_DAYS)
    with app.pool.tx(DbContext(system=True)) as c:
        now = _now(c)
        for t in c.query("SELECT org_id::text AS org_id, trial_start, trial_end, status FROM org_trials WHERE status = 'active' AND trial_end > now()"):
            idx = int((now - t["trial_start"]).total_seconds() // 86400) + 1
            if idx in cfg_days:
                days_left = max(0, math.ceil((t["trial_end"] - now).total_seconds() / 86400))
                msgs = {1: ("Seu teste de 14 dias começou", "Você tem acesso FULL e não será cobrado durante o período de teste."),
                        7: ("Lembrete do período de teste", f"Faltam {days_left} dias de acesso FULL gratuito."),
                        11: ("Seu período de teste termina em 3 dias", "Escolha um plano para manter o acesso completo."),
                        13: ("Seu período de teste termina amanhã", "Sem escolher um plano, sua conta passa para o plano gratuito, sem cobrança."),
                        14: ("Seu período de teste termina hoje", "Nenhum dado será apagado ao passar para o plano gratuito.")}
                title, body = msgs.get(idx, (f"Seu período de teste termina em {days_left} dias", "Escolha um plano para manter o acesso completo."))
                if notify_once(c, t["org_id"], "trial_day", str(idx), title, body):
                    reminders += 1
        for t in c.query("SELECT org_id::text AS org_id, status FROM org_trials WHERE status IN ('active','canceled') AND trial_end <= now() FOR UPDATE"):
            paid = c.one("SELECT 1 FROM subscriptions WHERE org_id = $1 AND status = 'active'", t["org_id"])
            c.run("UPDATE org_trials SET status = $2, updated_at = now() WHERE org_id = $1", t["org_id"], "converted" if paid else "ended")
            if not paid:
                ended += 1
                notify_once(c, t["org_id"], "trial_ended", "1", "Seu período de teste terminou",
                            "Sua conta está no plano gratuito. Nenhum dado foi apagado e nenhuma cobrança foi feita.")
        # SOMENTE sandbox/manual (Stripe é a autoridade das assinaturas reais): o trial acabou ⇒ ativa; período cancelado acabou ⇒ encerra
        converted_sbx = c.run("UPDATE subscriptions SET status = 'active', updated_at = now() WHERE provider = 'sandbox' AND status = 'trialing' AND trial_end <= now() AND NOT cancel_at_period_end")
        expired = c.run("UPDATE subscriptions SET status = 'canceled', updated_at = now() WHERE provider IN ('sandbox','manual') AND status IN ('active','trialing')"
                        " AND current_period_end IS NOT NULL AND current_period_end <= now() AND cancel_at_period_end")
        c.run("DELETE FROM trial_claims WHERE created_at < now() - interval '24 months'")        # retenção: identidade só pelo tempo necessário à antifraude
    return {"reminders": reminders, "trials_ended": ended, "sandbox_converted": converted_sbx, "periods_ended": expired}
