"""Concessões de acesso (v0.27.0): pacotes de capacidades, vouchers de concessão, convênios e avisos deduplicados.

NÃO EXISTE ASSINATURA (ADR-341). Até a v0.26.0 este módulo era a máquina do SaaS por mensalidade: trial de
14 dias, preço calculado no servidor, desconto, cotação, avisos de cobrança e o job de ciclo de vida da
assinatura. O proprietário retirou a assinatura do modelo econômico; a receita do IMPACTO nasce da camada
econômica da operação financiada (`trust/economy.py`: 3,5% de taxa de serviço contratada + 1,5% de
participação de autoria quando contratualmente elegível) e de contratos avulsos/parcelados (`offers.py`).

O que FICA aqui, porque continua tendo utilidade técnica fora da assinatura:
* `tier` dos pacotes de capacidades (rótulo e ordem) — lidos por `entitlements.effective`;
* `notify_once` — um aviso por (organização, tipo, referência), usado por concessões e alertas de uso;
* vouchers de CONCESSÃO (grant_plan, grant_feature, free_period) — vouchers de desconto estão aposentados:
  sem preço de assinatura não há sobre o que descontar, e o resgate os recusa com motivo explícito;
* convênios (entrada por código → concessão com prazo);
* leitura da versão de preço (`pricing_version_name`) e dos pisos de proposta de CONTRATO.

Nenhum pacote, voucher ou convênio altera match, elegibilidade ou ranking (teste de arquitetura).
"""
from __future__ import annotations

from datetime import datetime

from ..http import ApiError

TIER_ORDER = {"free": 0, "plus": 1, "premium": 2, "gov": 3}
TIER_LABEL = {"free": "ACESSO LIVRE", "plus": "PLUS", "premium": "PREMIUM (FULL)", "gov": "GOV / INSTITUCIONAL"}

#: Tipos de voucher que ainda CONCEDEM algo. `percent_off`/`amount_off` ficam no banco (linhas históricas e
#: CHECK) mas não são mais resgatáveis: não há preço de assinatura para descontar.
GRANT_VOUCHER_TYPES = ("grant_plan", "grant_feature", "free_period")
RETIRED_VOUCHER_TYPES = ("percent_off", "amount_off")


def _now(c) -> datetime:
    return c.scalar("SELECT now()")


def notify_once(c, org_id: str, kind: str, ref: str, title: str, body: str, link: str = "/conta/acesso") -> bool:
    """Um aviso por (organização, tipo, referência) — evita spam em reprocessamentos de jobs."""
    if not c.one("INSERT INTO billing_notices(org_id, kind, ref) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING RETURNING 1 AS ok", org_id, kind, ref):
        return False
    c.scalar("SELECT app_notify($1, NULL, $2, $3, $4, $5)", org_id, "billing." + kind, title, body, link)
    return True


# ------------------------------------------------------------------------------------------------ vouchers (validação compartilhada)
def voucher_row(c, code_hash: str):
    return c.one("SELECT v.*, v.id::text AS id, b.status AS batch_status FROM vouchers v JOIN voucher_batches b ON b.id = v.batch_id"
                 " WHERE v.code_hash = $1 FOR UPDATE OF v", code_hash)


def voucher_usable(c, v: dict | None, org: dict, org_id: str) -> bool:
    return bool(v and v["status"] == "active" and v["batch_status"] == "active" and v["redeemed_count"] < v["max_redemptions"]
                and v["type"] in GRANT_VOUCHER_TYPES
                and (v["valid_from"] is None or c.scalar("SELECT $1::timestamptz <= now()", v["valid_from"]))
                and (v["valid_until"] is None or c.scalar("SELECT $1::timestamptz > now()", v["valid_until"]))
                and (not v["scope_roles"] or org["kind"] in v["scope_roles"])
                and (not v["scope_cnpj"] or v["scope_cnpj"] == org["cnpj"])
                and (not v.get("organization_id") or str(v["organization_id"]) == org_id)
                and not c.one("SELECT 1 FROM voucher_redemptions WHERE voucher_id = $1 AND org_id = $2", v["id"], org_id))


def redeem_voucher(c, v: dict, org_id: str, user_id: str) -> str:
    """Aplica o voucher (já validado, linha travada): pacote/recurso/período viram concessão em `entitlement_grants`."""
    if v["type"] in RETIRED_VOUCHER_TYPES:
        raise ApiError(409, "voucher_type_retired", "Vouchers de desconto foram aposentados: não existe assinatura para descontar (ADR-341)")
    c.run("INSERT INTO voucher_redemptions(voucher_id, org_id, redeemed_by, status) VALUES ($1,$2,$3,'applied')", v["id"], org_id, user_id)
    c.run("UPDATE vouchers SET redeemed_count = redeemed_count + 1, status = CASE WHEN redeemed_count + 1 >= max_redemptions THEN 'exhausted' ELSE status END WHERE id = $1", v["id"])
    c.run("INSERT INTO entitlement_grants(org_id, plan_key, feature_key, source, source_ref, reason, ends_at)"
          " VALUES ($1,$2,$3,'voucher',$4,'Voucher', CASE WHEN $5::int IS NULL THEN NULL ELSE now() + make_interval(days => $5::int) END)",
          org_id, v["plan_key"], v["feature_key"], v["id"], v["duration_days"])
    return "applied"


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
    # `discount_percent` continua na tabela por histórico, mas não é aplicado a nada: não há preço de assinatura.
    return {"agreement_id": str(a["id"]), "name": a["name"], "plan_key": a["plan_key"],
            "ends_at": c.scalar("SELECT ends_at FROM entitlement_grants WHERE id = $1", grant_id) if grant_id else None}


# --- v0.21.0: catálogo lido da configuração ------------------------------------------------------

def _plans_config() -> dict:
    from pathlib import Path
    import json
    return json.loads((Path(__file__).resolve().parents[3] / "config" / "plans.json")
                      .read_text(encoding="utf-8"))


def quote_floors() -> dict[str, int]:
    """Piso publicado de proposta de CONTRATO (implantação, módulo institucional), por pacote.

    Piso NÃO é preço e NÃO é mensalidade: é a ordem de grandeza de um contrato avulso/parcelado negociado com
    quem tem alçada. Existe para que "sob proposta" venha com um número — sem isso, quem avalia o produto
    descobre que ele não cabe no orçamento depois de duas reuniões.
    """
    return {k: p["quote_floor_cents"] for k, p in _plans_config()["plans"].items()
            if p.get("quote_floor_cents") is not None}


def pricing_version_name() -> str:
    return _plans_config().get("pricing_version") or "unversioned"
