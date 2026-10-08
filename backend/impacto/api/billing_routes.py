"""Pacotes de capacidades, acesso e concessões da organização, resgate de vouchers.

v0.27.0 (ADR-341): NÃO EXISTE ASSINATURA. Saíram daqui checkout, cancelamento, reativação, troca de plano,
portal e webhook de assinatura do provedor, cotação, preço vigente, histórico e aviso de reajuste. Ficaram
o catálogo de pacotes (o que cada tipo de organização pode fazer e por qual via ganha mais), o estado de
acesso da organização (de onde vem o direito, o que foi concedido, o que foi faturado por contrato) e o
resgate de vouchers de concessão.
"""
from __future__ import annotations

import hashlib
import hmac

from ..db.pool import DbContext
from ..http import ApiError, Ctx, route
from . import schemas as S

T = ("billing",)

#: Por onde uma organização obtém capacidades além do núcleo. Nenhuma via é assinatura.
ACCESS_PATHS = [
    {"key": "core", "label": "Núcleo gratuito por desenho", "how": "Cadastro. Projetos, diagnóstico, documentos, matching, acordos e evidência — sem prazo e sem cobrança."},
    {"key": "operation", "label": "Camada econômica da operação financiada", "how": "Quem financia um projeto na plataforma paga 3,5% de taxa de serviço contratada no acordo (e 1,5% de participação de autoria ao proponente quando elegível). A OSC nunca desembolsa para pagar a plataforma."},
    {"key": "contract", "label": "Contrato avulso ou parcelado", "how": "Implantação, integração, módulo institucional, inteligência territorial: proposta com valor e motivo de quem tem alçada; o aceite com autorização de cobrança concede o pacote."},
    {"key": "grant", "label": "Concessão, convênio, voucher", "how": "Licença administrativa, convênio por código, voucher de concessão ou período promocional: concedem pacotes por prazo, nunca cobram."},
]


@route("GET", "/v1/plans", auth="none", tags=T, summary="Catálogo público de pacotes de capacidades (sem preço: não há assinatura) e as vias de acesso")
def plans(ctx: Ctx):
    from ..services import monetization as mon
    with ctx.pool.tx(DbContext(), readonly=True) as c:
        rows = c.query("SELECT plan_key, version, role, name, tier, limits, features, requires_flag FROM plans"
                       " WHERE active AND public ORDER BY role, CASE tier WHEN 'free' THEN 0 WHEN 'plus' THEN 1 WHEN 'premium' THEN 2 ELSE 3 END, plan_key")
        flags = {r["key"]: r["enabled"] for r in c.query("SELECT key, enabled FROM feature_flags")}
    pisos = mon.quote_floors()
    for r in rows:
        r["available"] = not r["requires_flag"] or flags.get(r["requires_flag"], False)
        r["tier_label"] = mon.TIER_LABEL.get(r["tier"], r["tier"])
        # Piso de proposta de CONTRATO (avulso/parcelado), não mensalidade.
        r["quote_floor_cents"] = pisos.get(r["plan_key"])
        r["obtained_by"] = "core" if r["tier"] == "free" else "contract_or_grant"
    return {"items": rows, "access_paths": ACCESS_PATHS,
            "pricing_version": mon.pricing_version_name(),
            "subscription": None,
            "pricing_note": "O IMPACTO não cobra assinatura (ADR-341). Pacotes além do núcleo vêm de contrato, concessão, "
                            "convênio ou voucher; a receita da plataforma nasce da camada econômica da operação financiada."}


@route("GET", "/v1/billing", min_role="viewer", tags=T, summary="Acesso e concessões da organização: de onde vem o direito, concessões, convênios, contratos e faturas")
def billing_state(ctx: Ctx):
    from ..services import free_period as FP
    from ..services.entitlements import effective
    with ctx.tx(readonly=True) as c:
        ent = effective(c, ctx.org_id, ctx.principal.org_kind)
        inv = c.query("SELECT id::text AS id, description, amount_cents, currency, status, due_on, paid_at, hosted_url, created_at FROM invoices"
                      " WHERE org_id = $1 ORDER BY created_at DESC LIMIT 50", ctx.org_id)
        red = c.query("SELECT redeemed_at, status FROM voucher_redemptions WHERE org_id = $1 ORDER BY redeemed_at DESC", ctx.org_id)
        agreements = c.query("SELECT a.name, a.kind, a.plan_key, m.status, g.ends_at FROM agreement_members m JOIN agreements a ON a.id = m.agreement_id"
                             " LEFT JOIN entitlement_grants g ON g.id = m.grant_id WHERE m.org_id = $1", ctx.org_id)
        grants = c.query("SELECT plan_key, feature_key, source, reason, starts_at, ends_at FROM entitlement_grants WHERE org_id = $1 AND revoked_at IS NULL"
                         " AND (ends_at IS NULL OR ends_at > now()) ORDER BY created_at DESC", ctx.org_id)
        contracts = c.query("SELECT a.id::text AS id, a.plan_key, a.billing_frequency, a.payment_method, a.consent_status, a.accepted_at, a.revoked_at,"
                            " o.amount_cents, o.currency, o.installments, o.contract_ref FROM offer_acceptances a"
                            " JOIN commercial_offers o ON o.id = a.offer_id WHERE a.org_id = $1 ORDER BY a.accepted_at DESC LIMIT 20", ctx.org_id)
        commercial = FP.state(c, ctx.org_id)
    state = commercial["state"]
    return {"entitlements": ent, "tier": ent["tier"], "tier_label": ent["tier_label"],
            "access": {"state": state, "label": FP.STATE_LABEL.get(state, state), "free_period_end": commercial.get("free_period_end"),
                       "days_remaining": commercial.get("days_remaining"), "charge_authorized": commercial.get("charge_authorized")},
            "subscription": None, "trial": None, "next_charge": None,
            "notices": _notices(commercial),
            "agreements": agreements, "licenses": grants, "contracts": contracts,
            "invoices": inv, "voucher_redemptions": red,
            "access_paths": ACCESS_PATHS,
            "no_subscription": "O IMPACTO não cobra assinatura. O núcleo é gratuito por desenho; capacidades além dele vêm de "
                               "contrato, concessão, convênio ou voucher (ADR-341)."}


def _notices(commercial: dict) -> list[dict]:
    """Avisos claros sobre o acesso. Nenhum fala de cobrança automática — não existe."""
    out: list[dict] = []
    st = commercial["state"]
    if st == "GRANT_EXPIRING":
        n = commercial.get("days_remaining")
        out.append({"level": "warn", "code": "grant_expiring",
                    "text": f"Sua concessão termina em {n} dia(s). Nada será cobrado: ao terminar, a conta segue com o acesso livre ao núcleo, sem perder dados."})
    elif st == "FREE_GRANT":
        out.append({"level": "info", "code": "grant_active", "text": "Há concessão temporal vigente. Nenhuma cobrança será feita ao terminar."})
    elif st == "CONTRACTED":
        out.append({"level": "info", "code": "contracted", "text": "Há contrato aceito com autorização de cobrança. As parcelas seguem o contrato; não há renovação automática."})
    else:
        out.append({"level": "info", "code": "free_access", "text": "Acesso livre ao núcleo, gratuito por desenho. Não existe assinatura."})
    return out


# ------------------------------------------------------------------------------------------------ vouchers
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def code_hash(secret: str, code: str) -> str:
    norm = code.strip().upper().replace("-", "").replace(" ", "")
    return hmac.new(secret.encode(), norm.encode(), hashlib.sha256).hexdigest()


@route("POST", "/v1/vouchers/redeem", body=S.VoucherRedeemIn, min_role="admin", rate=("voucher_ip", 10, 3600), tags=T,
       summary="Resgata voucher de concessão (transação atômica; resposta genérica para códigos inválidos; vouchers de desconto aposentados)")
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
            "pending_discount": False,
            "note": "Concessão aplicada. Nenhum pacote ou voucher altera compatibilidade, ranking ou posição no diretório."}
