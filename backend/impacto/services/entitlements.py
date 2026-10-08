"""EntitlementService — ÚNICO lugar que traduz pacote de capacidades/voucher/concessão em direitos.

Regras (docs/PLANS_AND_ENTITLEMENTS.md):
* direito mais favorável por featureKey/limite entre o pacote base do tipo e as concessões vigentes
  (licenças, vouchers, convênios, contratos);
* limite ``None`` = ilimitado;
* perder uma concessão nunca apaga dados (só bloqueia criação acima do limite);
* match e diretório de prestadores NÃO consultam este módulo (teste de dependência).

v0.27.0 (ADR-341): NÃO EXISTE ASSINATURA NEM TRIAL. As fontes de direito são o pacote base do tipo da
organização e `entitlement_grants`. Grants revogados não contam. ``tier`` = maior nível entre as fontes
(free < plus < premium < gov). ``has_access`` e ``get_entitlements`` são os pontos únicos de decisão de acesso.
"""
from __future__ import annotations

from ..db.pq import Connection
from ..http import ApiError
from .monetization import TIER_LABEL, TIER_ORDER

BASE_PLAN = {"osc": "osc_basic", "company": "company_basic", "provider": "provider_basic", "government": "government_basic",
             "individual": "individual_basic"}


def effective(conn: Connection, org_id: str, org_kind: str) -> dict:
    if org_kind == "platform":
        # `tier`/`tier_label` também aqui (v0.25.0): `GET /v1/billing` lê as duas chaves de qualquer
        # tipo de organização, e a administração recebia 500 (KeyError) ao abrir "Plano".
        return {"plans": ["platform"], "plan_names": ["Administração da plataforma"], "features": ["*"], "limits": {}, "grants": [],
                "tier": "platform", "tier_label": "Administração da plataforma"}
    plan_keys: list[str] = []
    base = BASE_PLAN.get(org_kind)
    if base:
        plan_keys.append(base)
    grants = conn.query("SELECT id, plan_key, feature_key, source, ends_at FROM entitlement_grants WHERE org_id = $1"
                        " AND starts_at <= now() AND (ends_at IS NULL OR ends_at > now()) AND revoked_at IS NULL", org_id)
    plan_keys += [g["plan_key"] for g in grants if g["plan_key"]]
    rows = conn.query("SELECT plan_key, name, role, limits, features, tier FROM plans WHERE plan_key = ANY($1::text[])", plan_keys)
    features: set[str] = {g["feature_key"] for g in grants if g["feature_key"]}
    limits: dict = {}
    for r in rows:
        features |= set(r["features"])
        for k, v in (r["limits"] or {}).items():
            if k not in limits:
                limits[k] = v
            elif limits[k] is None or v is None:
                limits[k] = None
            else:
                limits[k] = max(limits[k], v)
    tier = max((r["tier"] for r in rows), key=lambda t: TIER_ORDER.get(t, 0), default="free")
    return {"plans": [r["plan_key"] for r in rows], "plan_names": [r["name"] for r in rows], "features": sorted(features),
            "limits": limits, "grants": grants, "tier": tier, "tier_label": TIER_LABEL.get(tier, tier.upper())}


def get_entitlements(conn: Connection, org_id: str, org_kind: str) -> dict:
    """Ponto único: direitos efetivos da organização (alias explícito de ``effective``)."""
    return effective(conn, org_id, org_kind)


def has_access(conn: Connection, org_id: str, org_kind: str, feature: str) -> bool:
    ent = effective(conn, org_id, org_kind)
    return "*" in ent["features"] or feature in ent["features"]


def _plans_with(conn: Connection, feature: str, role: str | None) -> list[str]:
    return [r["name"] for r in conn.query("SELECT name FROM plans WHERE active AND $1 = ANY(features)"
                                           " AND ($2::text IS NULL OR role = $2) ORDER BY name", feature, role)]


def require_feature(ctx, feature: str) -> None:
    if ctx.admin_mode:
        return
    with ctx.tx(readonly=True) as c:
        ent = effective(c, ctx.org_id, ctx.principal.org_kind)
        if "*" in ent["features"] or feature in ent["features"]:
            return
        plans = _plans_with(c, feature, ctx.principal.org_kind)
    raise ApiError(402, "feature_not_in_plan", "Recurso disponível por concessão, convênio ou contrato" + (f": {', '.join(plans)}" if plans else ""),
                   {"feature": feature, "plans": plans})


def check_limit(conn: Connection, ctx, key: str, current: int) -> None:
    if ctx.admin_mode:
        return
    ent = effective(conn, ctx.org_id, ctx.principal.org_kind)
    if "*" in ent["features"]:
        return
    lim = ent["limits"].get(key, 0)
    if lim is not None and current >= lim:
        raise ApiError(402, "plan_limit_reached", f"Limite do pacote atingido para '{key}' ({lim}). Solicite concessão/contrato ou arquive itens.",
                       {"limit": key, "max": lim, "current": current})
