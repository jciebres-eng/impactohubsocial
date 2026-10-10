"""Doações, campanhas de arrecadação e espelho de conciliação — v0.33.0 (ADR-372 a ADR-376).

A REGRA ACIMA DESTE MÓDULO (NON_CUSTODIAL_ARCHITECTURE.md §0): a plataforma pode saber e dizer tudo
sobre o dinheiro; ela não guarda o dinheiro de ninguém. Aqui:

  * uma doação é confirmada SÓ por evento assinado do provedor de pagamento (ou pela consulta ao
    provedor), nunca pela tela — `confirm_from_provider_event` é o único caminho até `confirmed`;
  * o "saldo" de uma campanha é SOMA de lançamentos append-only (partidas dobradas, fechadas no
    COMMIT) e é rotulado "contábil estimado" até a conciliação; não existe coluna de saldo;
  * a taxa da plataforma (1 %, hipótese) e a reserva do beneficiário (até 4 %, hipótese) são
    CALCULADAS com a versão de regra congelada na doação e exibidas — mas a regra está inativa:
    `platform_fee_due()` devolve zero enquanto `monetization_rules.active` for falso;
  * só existe o provedor `sandbox`. Um provedor real entra por adaptador (`PaymentProvider`), com
    credencial no cofre, `live_payment_provider_enabled` e ADR — e `is_simulated` é derivada do
    provedor por gatilho, não escrita aqui.

PROVEDORES AVALIADOS (documentação oficial, lida em 09/10/2026; ver DONATIONS_PROVIDER_MATRIX.md):
  Asaas — cobrança `POST /v3/payments` com `billingType=PIX` exige `customer` (cadastro do pagador);
  webhook com header `asaas-access-token` (token opcional por webhook), `id` do evento para
  idempotência, entrega "at-least-once" sem garantia de ordem, fila pausada após 15 falhas; eventos
  PAYMENT_RECEIVED/CONFIRMED/REFUNDED/PARTIALLY_REFUNDED/CHARGEBACK_REQUESTED/OVERDUE/DELETED; split
  por `walletId` sobre o valor líquido (recebedor precisa de conta Asaas).
  Mercado Pago — webhook com `x-signature` (ts/v1, HMAC) e `x-request-id`, segredo por aplicação,
  reenvio a cada 15 min, espera 22 s por 200/201. Pix sem cadastro prévio do pagador (a confirmar
  na página de integração Pix, não lida por bloqueio de acesso).
  Nenhum foi escolhido: tarifas, KYB de subconta e split exigem contrato (BLOCKED_PROVIDER).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import ROUND_FLOOR, ROUND_HALF_EVEN, Decimal
from typing import Any, Protocol

from ..db.pq import Connection
from ..http import ApiError, forbidden, not_found, unprocessable

#: Provedores que cobram de verdade (espelha o gatilho `donation_simulated_flag`). Vazio de propósito
#: até existir adaptador real: a lista do gatilho é a lista de NOMES reservados, não de integrações.
LIVE_PROVIDERS: tuple[str, ...] = ()
SANDBOX = "sandbox"
TERMS_VERSION = "campaign-terms-2026-10-draft"   # minuta; versão real vem da revisão jurídica
CONFIRMING_EVENTS = {"payment.confirmed", "PAYMENT_RECEIVED", "PAYMENT_CONFIRMED", "charge.paid"}
REFUND_EVENTS = {"payment.refunded", "PAYMENT_REFUNDED", "charge.refunded"}
CHARGEBACK_EVENTS = {"payment.chargeback", "PAYMENT_CHARGEBACK_REQUESTED"}
EXPIRE_EVENTS = {"payment.expired", "PAYMENT_OVERDUE", "PAYMENT_DELETED", "checkout.canceled"}
#: Liquidação: o provedor diz que o dinheiro está DISPONÍVEL ao beneficiário (≠ confirmado). No Asaas, PAYMENT_RECEIVED
#: já é "recebido na conta"; PAYMENT_CONFIRMED (cartão) é confirmado sem liquidação. `payment.settled` é o nome neutro.
SETTLE_EVENTS = {"payment.settled", "PAYMENT_RECEIVED", "charge.settled"}
PARTIAL_REFUND_EVENTS = {"payment.partially_refunded", "PAYMENT_PARTIALLY_REFUNDED", "charge.partially_refunded"}
# v0.34.0 (E6): o provedor informa que NÃO conseguiu liquidar/repassar ao beneficiário (o pagamento continua confirmado).
SETTLEMENT_FAILED_EVENTS = {"payment.settlement_failed", "settlement.failed", "TRANSFER_FAILED"}
CONTRIBUTION_RULE = "donation.platform_contribution"
CONTRIBUTION_CAP_CENTS = 50_000          # espelho de hypothesis_max_cents da regra (0073); o menor entre isto e o valor doado
RECURRING_PAUSE_AFTER_FAILURES = 3
REDACT_KEYS = {"cpf", "cpfCnpj", "email", "phone", "ip", "card", "cardNumber", "document", "name", "payer"}


# ============================================================================ dinheiro
def apply_bps(amount_cents: int, bps: int, rounding: str = "half_even") -> int:
    """Percentual em pontos-base sobre centavos inteiros, arredondamento declarado. Nunca float."""
    q = (Decimal(amount_cents) * Decimal(bps) / Decimal(10_000)).quantize(
        Decimal(1), rounding=ROUND_HALF_EVEN if rounding == "half_even" else ROUND_FLOOR)
    return int(q)


@dataclass(frozen=True)
class Breakdown:
    amount_cents: int
    platform_fee_cents: int        # calculado pela versão congelada; DEVIDO só se a regra estiver ativa
    beneficiary_fund_cents: int    # destinação da organização; nunca receita da plataforma
    provider_fee_cents: int        # tarifa do provedor (catálogo versionado)
    cover_costs_cents: int         # contribuição voluntária do doador (nunca pré-marcada)

    @property
    def beneficiary_net_cents(self) -> int:
        return self.amount_cents + self.cover_costs_cents - self.provider_fee_cents - self.platform_fee_cents - self.beneficiary_fund_cents

    def as_dict(self) -> dict:
        return {"amount_cents": self.amount_cents, "platform_fee_cents": self.platform_fee_cents,
                "beneficiary_fund_cents": self.beneficiary_fund_cents, "provider_fee_cents": self.provider_fee_cents,
                "cover_costs_cents": self.cover_costs_cents, "beneficiary_net_cents": self.beneficiary_net_cents}


def current_rule_version(c: Connection, rule_key: str) -> dict | None:
    return c.one("SELECT id, bps, fixed_cents, base, rounding, legal_status FROM fee_rule_versions"
                 " WHERE rule_key = $1 AND effective_from <= now() AND (effective_to IS NULL OR effective_to > now())"
                 " ORDER BY version DESC LIMIT 1", rule_key)


def provider_schedule(c: Connection, provider: str, method: str) -> dict | None:
    return c.one("SELECT id, bps, fixed_cents FROM provider_fee_schedules WHERE provider = $1 AND method = $2"
                 " AND effective_from <= now() AND (effective_to IS NULL OR effective_to > now()) ORDER BY id DESC LIMIT 1",
                 provider, method)


def compute_breakdown(c: Connection, *, amount_cents: int, provider: str, method: str, cover_costs: bool,
                      fund_bps_declared: int) -> tuple[Breakdown, dict]:
    """Calcula as parcelas com as versões vigentes e devolve (breakdown, ids congelados).

    `fund_bps_declared` é o que a campanha DECLAROU ao doador (0–400): a regra do catálogo é o teto."""
    fee_v = current_rule_version(c, "donation.platform_fee")
    fund_v = current_rule_version(c, "donation.beneficiary_fund")
    sched = provider_schedule(c, provider, method)
    if not sched:
        raise unprocessable(f"sem tabela de tarifa para {provider}/{method}: tarifa real vem do contrato do provedor", code="provider_fee_unknown")
    provider_fee = apply_bps(amount_cents, sched["bps"]) + int(sched["fixed_cents"])
    platform_fee = apply_bps(amount_cents, fee_v["bps"], fee_v["rounding"]) + int(fee_v["fixed_cents"]) if fee_v else 0
    fund_bps = min(int(fund_bps_declared), int(fund_v["bps"]) if fund_v else 0)
    fund = apply_bps(amount_cents, fund_bps, fund_v["rounding"]) if fund_v else 0
    cover = provider_fee + platform_fee if cover_costs else 0
    b = Breakdown(amount_cents, platform_fee, fund, provider_fee, cover)
    return b, {"fee_rule_version_id": fee_v["id"] if fee_v else None, "fund_rule_version_id": fund_v["id"] if fund_v else None,
               "provider_fee_schedule_id": sched["id"]}


def platform_fee_due(c: Connection, donation: dict) -> int:
    """O que a plataforma pode COBRAR: zero enquanto a regra estiver inativa no catálogo (carta não verde)."""
    active = c.scalar("SELECT active FROM monetization_rules WHERE key = 'donation.platform_fee'")
    return int(donation["platform_fee_cents"]) if active else 0


# ============================================================================ provedor (porta + sandbox)
@dataclass(frozen=True)
class Charge:
    provider_charge_id: str
    method: str
    amount_cents: int
    expires_at: datetime
    pix_payload: str | None       # "copia e cola" — no sandbox, um texto claramente de TESTE
    checkout_url: str | None


class ProviderUnavailable(Exception):
    """O provedor não respondeu ou recusou temporariamente (timeout, 5xx). Nada é gravado: a transação volta e o doador
    pode tentar de novo com a MESMA chave de idempotência."""


class PaymentProvider(Protocol):
    name: str
    supports_split: bool

    def create_charge(self, *, donation_id: str, amount_cents: int, method: str, description: str, expires_in_minutes: int,
                      split: list[dict] | None = None) -> Charge: ...
    def verify_signature(self, headers: dict, body: bytes) -> bool: ...
    def parse_event(self, body: bytes) -> dict: ...
    def fetch_charge(self, provider_charge_id: str) -> dict | None: ...


class SandboxProvider:
    """Provedor de TESTE. Não move dinheiro. A assinatura usa um segredo local; o "pagamento" só acontece
    quando um evento assinado chega (test ou ferramenta de operação) — exatamente como seria com o real."""
    name = SANDBOX
    # O sandbox NÃO divide pagamentos: split depende de contrato e homologação com um provedor real (ADR-375/384).
    # Os testes que exercitam o caminho de split trocam este atributo e dizem isso no nome do teste.
    supports_split = False

    def __init__(self, secret: str):
        self.secret = secret or "sandbox-sem-segredo"

    def create_charge(self, *, donation_id: str, amount_cents: int, method: str, description: str, expires_in_minutes: int,
                      split: list[dict] | None = None) -> Charge:
        if split and not self.supports_split:
            raise ProviderUnavailable("split não suportado por este provedor")
        cid = "sbx_" + secrets.token_hex(10)
        exp = datetime.now(UTC) + timedelta(minutes=expires_in_minutes)
        payload = (f"PIX-SANDBOX-NAO-PAGAVEL|{cid}|{amount_cents}|{donation_id[:8]}" if method == "pix" else None)
        return Charge(cid, method, amount_cents, exp, payload, None if method == "pix" else f"/doar/checkout-sandbox/{cid}")

    def verify_signature(self, headers: dict, body: bytes) -> bool:
        given = headers.get("x-impacto-signature", "")
        expected = hmac.new(self.secret.encode(), body, hashlib.sha256).hexdigest()
        return bool(given) and hmac.compare_digest(given, expected)

    def parse_event(self, body: bytes) -> dict:
        data = json.loads(body or b"{}")
        return {"event_id": str(data.get("event_id") or "")[:120], "event_type": str(data.get("type") or "")[:60],
                "provider_charge_id": (str(data.get("charge_id")) if data.get("charge_id") else None),
                "amount_cents": data.get("amount_cents"), "currency": data.get("currency", "BRL"), "raw": data}

    def fetch_charge(self, provider_charge_id: str) -> dict | None:
        return None   # sandbox não tem consulta: um evento ambíguo fica em `under_review`


def provider_for(settings: Any, name: str | None = None) -> PaymentProvider:
    name = name or SANDBOX
    if name in LIVE_PROVIDERS and getattr(settings, "live_payment_provider_enabled", False):
        raise NotImplementedError("adaptador real entra por ADR, com credencial no cofre")   # pragma: no cover
    if name != SANDBOX:
        raise unprocessable(f"provedor '{name}' não disponível: só o sandbox existe nesta versão", code="provider_unavailable")
    return SandboxProvider(getattr(settings, "payment_webhook_secret", "") or "")


def redact(payload: dict) -> dict:
    out = {}
    for k, v in (payload or {}).items():
        if k in REDACT_KEYS:
            out[k] = "[REDACTED]"
        elif isinstance(v, dict):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


# ============================================================================ campanhas
def campaign_totals(c: Connection, campaign_id: str) -> dict:
    """Números da campanha, cada um com definição e NUNCA somados num número só (pacote §4.2). Nada aqui é saldo custodiado.

    Contas do razão lidas com sinal (D − C), de modo que reversões totais e parciais abatem a conta certa."""
    r = c.one(
        "SELECT"
        " coalesce(sum(amount_cents) FILTER (WHERE account = 'donor_payment' AND side = 'C' AND reversal_of IS NULL), 0) AS gross_confirmed,"
        " coalesce(sum(amount_cents) FILTER (WHERE account IN ('refund','chargeback') AND side = 'D'), 0) AS reversed,"
        " coalesce(sum(CASE WHEN side = 'D' THEN amount_cents ELSE -amount_cents END) FILTER (WHERE account = 'provider_fee'), 0) AS provider_fees,"
        " coalesce(sum(CASE WHEN side = 'D' THEN amount_cents ELSE -amount_cents END) FILTER (WHERE account = 'platform_fee_accrued'), 0) AS platform_fee_accrued,"
        " coalesce(sum(CASE WHEN side = 'D' THEN amount_cents ELSE -amount_cents END) FILTER (WHERE account = 'beneficiary_fund'), 0) AS beneficiary_fund,"
        " coalesce(sum(CASE WHEN side = 'D' THEN amount_cents ELSE -amount_cents END) FILTER (WHERE account = 'beneficiary_receivable'), 0) AS beneficiary_net,"
        " bool_or(is_simulated) AS any_simulated, max(created_at) AS last_entry_at"
        " FROM donation_ledger_entries WHERE campaign_id = $1", campaign_id)
    st = c.one(
        "SELECT count(*) FILTER (WHERE status IN ('confirmed','reconciled','partially_refunded')) AS confirmed_n,"
        " count(*) FILTER (WHERE status = 'reconciled') AS reconciled_n,"
        " count(*) FILTER (WHERE status = 'awaiting_payment') AS pending_n,"
        " coalesce(sum(amount_cents + cover_costs_cents) FILTER (WHERE status = 'awaiting_payment'), 0) AS pending_cents,"
        " coalesce(sum(amount_cents + cover_costs_cents - least(refunded_cents, amount_cents + cover_costs_cents)) FILTER (WHERE settled_at IS NOT NULL AND status IN ('confirmed','reconciled','partially_refunded')), 0) AS settled_cents,"
        " coalesce(sum(least(settled_cents, amount_cents + cover_costs_cents)) FILTER (WHERE settled_at IS NULL AND settled_cents > 0 AND status IN ('confirmed','reconciled','partially_refunded')), 0) AS settled_partial_cents,"
        " count(*) FILTER (WHERE settled_at IS NULL AND settled_cents > 0 AND status IN ('confirmed','reconciled','partially_refunded')) AS settled_partial_n,"
        " count(*) FILTER (WHERE status = 'under_review') AS under_review_n,"
        " coalesce(sum(amount_cents + cover_costs_cents) FILTER (WHERE status = 'under_review'), 0) AS under_review_cents,"
        " count(*) FILTER (WHERE status IN ('refunded','chargeback')) AS reversed_n,"
        " count(*) FILTER (WHERE status = 'partially_refunded') AS partially_refunded_n"
        " FROM donations WHERE campaign_id = $1", campaign_id)
    pl = c.one("SELECT count(*) AS n, coalesce(sum(amount_cents),0) AS cents FROM donation_pledges WHERE campaign_id = $1 AND status = 'pledged'", campaign_id)
    ex = c.one("SELECT count(*) AS n, coalesce(sum(amount_cents),0) AS cents FROM external_resources WHERE campaign_id = $1", campaign_id)
    sp = c.one("SELECT coalesce(sum(amount_cents),0) AS declared, coalesce(sum(amount_cents) FILTER (WHERE evidence_status = 'validated'),0) AS validated"
               " FROM campaign_expenses WHERE campaign_id = $1", campaign_id)
    return {
        "gross_confirmed_cents": int(r["gross_confirmed"]),
        "reversed_cents": int(r["reversed"]),
        "net_after_reversals_cents": int(r["gross_confirmed"]) - int(r["reversed"]),
        "settled_cents": int(st["settled_cents"]),
        "settled_partial_cents": int(st["settled_partial_cents"]), "settled_partial_donations": int(st["settled_partial_n"]),
        "pending_cents": int(st["pending_cents"]), "pending_donations": int(st["pending_n"]),
        "under_review_cents": int(st["under_review_cents"]), "under_review_donations": int(st["under_review_n"]),
        "provider_fees_cents": int(r["provider_fees"]),
        "platform_fee_accrued_cents": int(r["platform_fee_accrued"]),
        "beneficiary_fund_cents": int(r["beneficiary_fund"]),
        "beneficiary_net_estimated_cents": int(r["beneficiary_net"]),
        "expenses_declared_cents": int(sp["declared"]), "expenses_validated_cents": int(sp["validated"]),
        "pledged_cents": int(pl["cents"]), "pledges": int(pl["n"]),
        "external_declared_cents": int(ex["cents"]), "external_resources": int(ex["n"]),
        "confirmed_donations": int(st["confirmed_n"]), "reconciled_donations": int(st["reconciled_n"]),
        "reversed_donations": int(st["reversed_n"]), "partially_refunded_donations": int(st["partially_refunded_n"]),
        "basis": "pagamentos CONFIRMADOS pelo provedor; pode mudar por estorno ou chargeback",
        "counting_policy": "uma doação conta uma vez (por cobrança do provedor); estornada total sai da contagem; parcial continua contada com o valor abatido",
        "definitions": {
            "gross_confirmed_cents": "soma do que os doadores pagaram em doações confirmadas pelo provedor",
            "settled_cents": "parcela já LIQUIDADA (disponível ao beneficiário segundo o provedor), líquida de estornos",
            "settled_partial_cents": "liquidação PARCIAL informada pelo provedor (o restante segue pendente e aparece na fila de conciliação)",
            "pending_cents": "cobranças iniciadas e ainda não pagas — NÃO é arrecadação",
            "under_review_cents": "valores em análise (divergência ou risco) — NÃO entram na barra",
            "beneficiary_net_estimated_cents": "bruto − tarifa do provedor − taxa calculada − fundo, abatidos os estornos; estimado até conciliar",
            "platform_fee_accrued_cents": "taxa CALCULADA (hipótese); devida só por obrigação com gatilho — hoje R$ 0,00 devido",
            "pledged_cents": "compromissos de doação futura — NÃO é dinheiro recebido",
            "external_declared_cents": "recursos declarados pela organização fora da plataforma — não conferidos pelo provedor"},
        "label": "saldo contábil estimado (espelho de conciliação) — não é dinheiro guardado pela plataforma",
        "any_simulated": bool(r["any_simulated"]), "last_entry_at": r["last_entry_at"],
    }


def public_campaign(c: Connection, slug: str) -> dict:
    camp = c.one("SELECT c.id::text AS id, c.slug, c.title, c.summary, c.story, c.status, c.kind, c.target_cents, c.currency, c.funding_source,"
                 " c.starts_on, c.ends_on, c.purpose, c.contingency_policy, c.refund_policy, c.published_at, c.show_backers,"
                 " c.min_donation_cents, c.allow_recurring, c.qr_version, c.project_id::text AS project_id, p.title AS project_title,"
                 " o.legal_name, o.trade_name, o.city, o.uf, o.kind AS org_kind, o.id::text AS beneficiary_org_id,"
                 " beneficiary_verified(o.id) AS beneficiary_verified"
                 " FROM campaigns c LEFT JOIN projects p ON p.id = c.project_id JOIN organizations o ON o.id = c.beneficiary_org_id"
                 " WHERE c.slug = $1 AND c.status IN ('published','paused','target_reached','ended','closed')", slug)
    if not camp:
        raise not_found("Campanha")
    totals = campaign_totals(c, camp["id"])
    backers = []
    if camp["show_backers"]:
        backers = c.query("SELECT CASE WHEN public_anonymous OR donor_display IS NULL THEN 'Apoiador anônimo' ELSE donor_display END AS name,"
                          " amount_cents, confirmed_at FROM donations WHERE campaign_id = $1 AND status IN ('confirmed','reconciled')"
                          " ORDER BY confirmed_at DESC LIMIT 50", camp["id"])
    updates = c.query("SELECT id::text AS id, title, body, created_at FROM campaign_updates WHERE campaign_id = $1 AND is_public"
                      " ORDER BY created_at DESC LIMIT 20", camp["id"])
    expenses = c.query("SELECT budget_line, amount_cents, spent_on, evidence_status FROM campaign_expenses WHERE campaign_id = $1"
                       " ORDER BY spent_on DESC LIMIT 100", camp["id"])
    fee_v = current_rule_version(c, "donation.platform_fee")
    fund_v = current_rule_version(c, "donation.beneficiary_fund")
    fee_active = bool(c.scalar("SELECT active FROM monetization_rules WHERE key = 'donation.platform_fee'"))
    return {
        "campaign": {k: camp[k] for k in ("slug", "title", "summary", "story", "status", "kind", "target_cents", "currency", "starts_on",
                                           "ends_on", "purpose", "contingency_policy", "refund_policy", "published_at", "project_title",
                                           "min_donation_cents", "allow_recurring", "qr_version")},
        "beneficiary": {"name": camp["trade_name"] or camp["legal_name"], "city": camp["city"], "uf": camp["uf"], "kind": camp["org_kind"],
                        "verified": bool(camp["beneficiary_verified"])},
        "totals": totals, "backers": backers, "updates": updates, "expenses": expenses,
        "external_resources": c.query("SELECT kind, source_name, funding_source, amount_cents, in_kind_description, received_on, status"
                                      " FROM external_resources WHERE campaign_id = $1 ORDER BY received_on DESC LIMIT 100", camp["id"]),
        "pledges": {"count": totals["pledges"], "cents": totals["pledged_cents"], "note": "compromissos de doação futura: NÃO é dinheiro recebido"},
        "last_financial_update_at": totals["last_entry_at"],
        "funding_source": camp.get("funding_source", "private"),
        "costs_disclosure": {
            "platform_fee_bps": fee_v["bps"] if fee_v else 0, "platform_fee_active": fee_active,
            "beneficiary_fund_max_bps": fund_v["bps"] if fund_v else 0,
            "provider": SANDBOX, "provider_fee_note": "tarifa real vem do contrato do provedor; o sandbox não cobra",
            "note": "A taxa de serviço da plataforma é uma HIPÓTESE registrada no catálogo e está INATIVA: nenhuma parcela é devida "
                    "até parecer e contrato. O preço total aparece antes de pagar.",
            # ADR-384: só aparece ao doador com a regra ativa; começa em zero; nunca sugerida; separada no total
            "platform_contribution": {"available": bool(c.scalar("SELECT active FROM monetization_rules WHERE key = $1", CONTRIBUTION_RULE)),
                                      "default_cents": 0, "max_cents": CONTRIBUTION_CAP_CENTS,
                                      "note": "Opcional: um valor A MAIS para a manutenção da plataforma. Não sai da sua doação e pode ficar em zero."},
        },
        "payment_mode": "sandbox" if not LIVE_PROVIDERS else "live",
        "what_this_is_not": ["A plataforma não recebe, não guarda e não repassa doações: o provedor de pagamento liquida ao beneficiário.",
                             "A barra de arrecadação conta só pagamentos confirmados pelo provedor e pode mudar por estornos.",
                             "Comprovante de doação não é recibo dedutível nem nota fiscal; a dedutibilidade depende do caso."],
    }


def canonical_url(settings: Any, slug: str, qr_version: int) -> str:
    base = (getattr(settings, "public_base_url", "") or "").rstrip("/")
    return f"{base}/campanha/{slug}?v={qr_version}"


# ============================================================================ doações
def start_donation(c: Connection, *, settings: Any, campaign_slug: str, amount_cents: int, method: str, donor_user_id: str | None,
                   donor_display: str | None, donor_email: str | None, public_anonymous: bool, cover_costs: bool,
                   idempotency_key: str | None, cipher: Any, donor_org_id: str | None = None, funding_source: str | None = None,
                   platform_contribution_cents: int = 0, recurring_agreement_id: str | None = None) -> dict:
    """Cria a doação e a cobrança no provedor. Devolve o que o doador precisa (QR/copia e cola, total, parcelas) — e NUNCA marca pago."""
    if not getattr(settings, "donations_enabled", True):
        raise ApiError(503, "donations_disabled", "Doações desligadas nesta instalação")
    camp = c.one("SELECT id::text AS id, beneficiary_org_id::text AS beneficiary_org_id, status, min_donation_cents, qr_version,"
                 " coalesce((SELECT bps FROM fee_rule_versions WHERE rule_key = 'donation.beneficiary_fund' ORDER BY version DESC LIMIT 1), 0) AS fund_bps_max,"
                 " title, funding_source FROM campaigns WHERE slug = $1", campaign_slug)
    if not camp or camp["status"] not in ("published", "target_reached"):
        raise not_found("Campanha aberta a doações")
    if funding_source not in (None, "private", "public", "mixed"):
        raise unprocessable("origem do recurso desconhecida", code="funding_source")
    funding_source = funding_source or camp["funding_source"]
    if amount_cents < int(camp["min_donation_cents"]):
        raise unprocessable(f"doação mínima desta campanha: {camp['min_donation_cents']} centavos", code="below_minimum")
    if method not in ("pix", "card"):
        raise unprocessable("meio de pagamento não suportado", code="method_unsupported")
    contribution = int(platform_contribution_cents or 0)
    if contribution < 0:
        raise unprocessable("contribuição negativa", code="contribution_invalid")
    if contribution > 0:
        from . import remuneration as REM
        if not REM.rule_active(c, CONTRIBUTION_RULE):
            raise unprocessable("contribuição voluntária à plataforma não está disponível (regra inativa)", code="contribution_unavailable")
        if contribution > min(int(amount_cents), CONTRIBUTION_CAP_CENTS):
            raise unprocessable("contribuição acima do teto: o menor entre o valor doado e R$ 500,00", code="contribution_above_cap")
    if idempotency_key:
        dup = c.one("SELECT id::text AS id FROM donations WHERE campaign_id = $1 AND idempotency_key = $2", camp["id"], idempotency_key)
        if dup:
            return get_donation(c, dup["id"], settings=settings) | {"duplicate": True}
    prov = provider_for(settings)
    # Destinação ao fundo declarada na campanha: nesta versão, 0 (a organização ainda não declara na tela); o teto é a regra.
    fund_bps_declared = 0
    b, frozen = compute_breakdown(c, amount_cents=amount_cents, provider=prov.name, method=method, cover_costs=cover_costs,
                                  fund_bps_declared=fund_bps_declared)
    # Split só para a contribuição VOLUNTÁRIA (nada sai do valor doado) e só com a trava ligada e um provedor que divida.
    split_cents = contribution if (contribution > 0 and getattr(settings, "split_enabled", False) and getattr(prov, "supports_split", False)) else 0
    did = c.scalar(
        "INSERT INTO donations(campaign_id, beneficiary_org_id, donor_user_id, donor_display, donor_contact_enc, public_anonymous,"
        " amount_cents, method, provider, status, fee_rule_version_id, fund_rule_version_id, provider_fee_schedule_id,"
        " platform_fee_cents, beneficiary_fund_cents, provider_fee_cents, cover_costs_opt_in, cover_costs_cents, qr_version, idempotency_key,"
        " donor_org_id, funding_source, platform_contribution_cents, split_platform_cents, recurring_agreement_id)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,'created',$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24) RETURNING id::text",
        camp["id"], camp["beneficiary_org_id"], donor_user_id, (donor_display or None), (cipher.encrypt(donor_email) if donor_email else None),
        public_anonymous, amount_cents, method, prov.name, frozen["fee_rule_version_id"], frozen["fund_rule_version_id"],
        frozen["provider_fee_schedule_id"], b.platform_fee_cents, b.beneficiary_fund_cents, b.provider_fee_cents, cover_costs,
        b.cover_costs_cents, camp["qr_version"], idempotency_key, donor_org_id, funding_source or "private", contribution, split_cents,
        recurring_agreement_id)
    split = [{"receiver": "platform", "amount_cents": split_cents, "reason": CONTRIBUTION_RULE}] if split_cents else None
    try:
        ch = prov.create_charge(donation_id=did, amount_cents=amount_cents + b.cover_costs_cents + contribution, method=method,
                                description=f"Doação — {camp['title'][:80]}", expires_in_minutes=30, split=split)
    except ProviderUnavailable as exc:
        # nada fica gravado (a transação volta): repetir com a mesma chave é seguro
        raise ApiError(503, "provider_unavailable", "O provedor de pagamento não respondeu. Nada foi cobrado; tente de novo em instantes.") from exc
    c.run("UPDATE donations SET status = 'awaiting_payment', provider_charge_id = $2, expires_at = $3 WHERE id = $1", did, ch.provider_charge_id, ch.expires_at)
    _risk_screen(c, donation_id=did, campaign_id=camp["id"], amount_cents=amount_cents, donor_user_id=donor_user_id)
    return get_donation(c, did, settings=settings) | {"pix_payload": ch.pix_payload, "checkout_url": ch.checkout_url}


def get_donation(c: Connection, donation_id: str, *, settings: Any) -> dict:
    d = c.one("SELECT d.id::text AS id, d.campaign_id::text AS campaign_id, d.status, d.amount_cents, d.currency, d.method, d.provider,"
              " d.is_simulated, d.platform_fee_cents, d.beneficiary_fund_cents, d.provider_fee_cents, d.cover_costs_opt_in,"
              " d.cover_costs_cents, d.public_anonymous, d.donor_display, d.expires_at, d.confirmed_at, d.created_at, d.qr_version,"
              " d.platform_contribution_cents, d.split_platform_cents, d.settled_cents, d.settled_at, d.recurring_agreement_id::text AS recurring_agreement_id,"
              " c.slug, c.title AS campaign_title FROM donations d JOIN campaigns c ON c.id = d.campaign_id WHERE d.id = $1", donation_id)
    if not d:
        raise not_found("Doação")
    b = Breakdown(d["amount_cents"], d["platform_fee_cents"], d["beneficiary_fund_cents"], d["provider_fee_cents"], d["cover_costs_cents"])
    receipt = c.one("SELECT number, issued_at, status FROM donation_receipts WHERE donation_id = $1", donation_id)
    return {**{k: d[k] for k in ("id", "campaign_id", "status", "amount_cents", "currency", "method", "provider", "is_simulated", "public_anonymous",
                                 "donor_display", "expires_at", "confirmed_at", "created_at", "qr_version", "slug", "campaign_title",
                                 "platform_contribution_cents", "settled_cents", "settled_at", "recurring_agreement_id")},
            "total_to_pay_cents": d["amount_cents"] + d["cover_costs_cents"] + d["platform_contribution_cents"], "breakdown": b.as_dict(),
            "split_platform_cents": d["split_platform_cents"],
            "platform_fee_due_cents": platform_fee_due(c, d), "campaign_url": canonical_url(settings, d["slug"], d["qr_version"]),
            "receipt": receipt,
            "notice": ("SIMULAÇÃO: provedor de teste, nenhum dinheiro movido." if d["is_simulated"] else
                       "Pagamento confirmado pelo provedor; a plataforma não recebe nem guarda o valor.")}


# ============================================================================ eventos do provedor → estado → razão
def record_provider_event(c: Connection, *, provider: str, event: dict, signature_verified: bool, raw: bytes) -> dict:
    """Guarda o evento uma única vez (UNIQUE provider+event_id, inclusive sob entregas simultâneas). Reentrega devolve
    `duplicate` com o estado do processamento — e um evento ainda não aplicado (`received`/`failed`) pode ser reaplicado."""
    sha = hashlib.sha256(raw or b"").hexdigest()
    status = "received" if signature_verified else "rejected"
    row_id = c.scalar(
        "INSERT INTO payment_provider_events(provider, event_id, event_type, provider_charge_id, amount_cents, signature_verified,"
        " payload_redacted, payload_sha256, processing_status, processing_note)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10) ON CONFLICT (provider, event_id) DO NOTHING RETURNING id",
        provider, event["event_id"], event["event_type"], event.get("provider_charge_id"), event.get("amount_cents"), signature_verified,
        json.dumps(redact(event.get("raw") or {})), sha, status, (None if signature_verified else "assinatura inválida: nenhum efeito"))
    if row_id is None:
        existing = c.one("SELECT id, processing_status, signature_verified FROM payment_provider_events WHERE provider = $1 AND event_id = $2",
                         provider, event["event_id"])
        c.run("UPDATE payment_provider_events SET attempts = attempts + 1 WHERE id = $1", existing["id"])
        return {"event_row_id": existing["id"], "duplicate": True, "applied": False, "status": existing["processing_status"],
                "reapplicable": bool(existing["signature_verified"]) and existing["processing_status"] in ("received", "failed")}
    return {"event_row_id": row_id, "duplicate": False, "applied": signature_verified, "status": status, "reapplicable": signature_verified}


def apply_provider_event(c: Connection, *, provider: str, event: dict, signature_verified: bool, raw: bytes) -> dict:
    """Gravar + aplicar NA MESMA transação (usado onde não há separação de fases). O webhook HTTP usa as duas fases
    (`record_provider_event` e `apply_recorded_event`) para que uma falha interna não perca o evento (cenário 33)."""
    rec = record_provider_event(c, provider=provider, event=event, signature_verified=signature_verified, raw=raw)
    if not rec["reapplicable"]:
        return rec | {"effect": "none"}
    return apply_recorded_event(c, provider=provider, row_id=rec["event_row_id"], event=event) | {"duplicate": rec["duplicate"]}


def event_from_row(row: dict) -> dict:
    """Reconstrói o evento a partir do que foi gravado (payload já sem dado pessoal) — é o que a rotina reprocessa."""
    payload = row["payload_redacted"] if isinstance(row["payload_redacted"], dict) else json.loads(row["payload_redacted"] or "{}")
    return {"event_id": row["event_id"], "event_type": row["event_type"], "provider_charge_id": row["provider_charge_id"],
            "amount_cents": row["amount_cents"], "currency": payload.get("currency", "BRL"), "raw": payload}


def _close(c: Connection, row_id: int, status: str, note: str | None = None) -> None:
    c.run("UPDATE payment_provider_events SET processing_status = $2, processing_note = $3, processed_at = now() WHERE id = $1", row_id, status, note)


def apply_recorded_event(c: Connection, *, provider: str, row_id: int, event: dict) -> dict:
    """O único caminho até `confirmed`/`refunded`/`chargeback`/liquidado. Idempotente por evento (a linha do evento é
    travada: duas entregas simultâneas não aplicam duas vezes); valor conferido; transição atômica."""
    lock = c.one("SELECT processing_status, signature_verified FROM payment_provider_events WHERE id = $1 FOR UPDATE", row_id)
    rec = {"event_row_id": row_id, "duplicate": False, "applied": True}
    if not lock or not lock["signature_verified"] or lock["processing_status"] not in ("received", "failed"):
        return rec | {"effect": "none", "duplicate": True, "status": lock["processing_status"] if lock else None}
    et = event["event_type"]
    raw = event.get("raw") or {}
    cid = event.get("provider_charge_id")
    d = c.one("SELECT id::text AS id, campaign_id::text AS campaign_id, beneficiary_org_id::text AS beneficiary_org_id, status, amount_cents,"
              " cover_costs_cents, provider_fee_cents, platform_fee_cents, beneficiary_fund_cents, is_simulated, currency, settled_at, refunded_cents,"
              " fee_rule_version_id, funding_source, platform_contribution_cents, split_platform_cents, settled_cents,"
              " recurring_agreement_id::text AS recurring_agreement_id FROM donations WHERE provider = $1 AND provider_charge_id = $2"
              " FOR UPDATE", provider, cid) if cid else None
    if not d:
        _close(c, row_id, "ignored", "cobrança desconhecida")
        return rec | {"effect": "ignored", "note": "cobrança desconhecida"}
    c.run("UPDATE payment_provider_events SET donation_id = $2 WHERE id = $1", row_id, d["id"])
    expected_total = int(d["amount_cents"]) + int(d["cover_costs_cents"]) + int(d["platform_contribution_cents"])
    # o que o provedor deve liquidar ao BENEFICIÁRIO: total − tarifa − parte já dividida para a plataforma − estornos
    expected_settlement = expected_total - int(d["provider_fee_cents"]) - int(d["split_platform_cents"]) - int(d["refunded_cents"])
    if et in SETTLEMENT_FAILED_EVENTS:
        if d["status"] not in ("confirmed", "reconciled", "partially_refunded"):
            _close(c, row_id, "ignored", "falha de liquidação sem confirmação prévia")
            return rec | {"effect": "ignored", "note": "falha de liquidação sem confirmação prévia"}
        from . import reconciliation as RECON
        RECON.open_from_event(c, kind="settlement_failed", campaign_id=d["campaign_id"], org_id=d["beneficiary_org_id"], donation_id=d["id"],
                              provider=provider, provider_ref=cid, expected=expected_settlement, observed=int(d["settled_cents"]),
                              detail="o provedor informou falha na liquidação ao beneficiário: " + str(raw.get("reason") or "sem motivo informado")[:300])
        _close(c, row_id, "applied", "falha de liquidação: exceção aberta; o pagamento continua confirmado")
        return rec | {"effect": "settlement_failed", "donation_id": d["id"]}
    # Liquidação de doação já confirmada (pode ser PARCIAL: `settled_cents` no evento). Nunca "desliquida".
    if et in SETTLE_EVENTS and d["status"] in ("confirmed", "reconciled", "partially_refunded"):
        if d["settled_at"] is not None:
            _close(c, row_id, "ignored", "já liquidada")
            return rec | {"effect": "already_settled"}
        return rec | _apply_settlement(c, d, row_id=row_id, provider=provider, raw=raw, expected=expected_settlement)
    if et in PARTIAL_REFUND_EVENTS:
        amt = int(event.get("amount_cents") or 0)
        if d["status"] not in ("confirmed", "reconciled", "partially_refunded") or amt <= 0:
            _close(c, row_id, "ignored", "estorno parcial sem confirmação ou sem valor")
            return rec | {"effect": "ignored", "note": "estorno parcial sem confirmação ou sem valor"}
        if int(d["refunded_cents"]) + amt > expected_total:
            open_risk_case(c, campaign_id=d["campaign_id"], donation_id=d["id"], reason_codes=["refund_exceeds_payment"], level="high",
                           explanation=f"estorno parcial acumulado ({d['refunded_cents']} + {amt}) maior que o pago ({expected_total})")
            _close(c, row_id, "applied", "estorno maior que o pago: caso de risco")
            return rec | {"effect": "under_review"}
        _post_partial_reversal(c, d, amount=amt, source_event_id=row_id)
        new_total = int(d["refunded_cents"]) + amt
        c.run("UPDATE donations SET refunded_cents = $2 WHERE id = $1", d["id"], new_total)
        if new_total == expected_total:
            c.run("UPDATE donations SET status = 'refunded' WHERE id = $1", d["id"])
            c.run("UPDATE donation_receipts SET status = 'voided', voided_at = now() WHERE donation_id = $1 AND status = 'issued'", d["id"])
            _obligations_on_reversal(c, d, note="estorno parcial acumulado até o total")
            effect = "refunded"
        else:
            c.run("UPDATE donations SET status = 'partially_refunded' WHERE id = $1 AND status <> 'partially_refunded'", d["id"])
            effect = "partially_refunded"
        _close(c, row_id, "applied")
        return rec | {"effect": effect, "donation_id": d["id"], "refunded_cents": new_total}
    if et in CONFIRMING_EVENTS:
        if event.get("amount_cents") is not None and int(event["amount_cents"]) != expected_total or (event.get("currency") or "BRL") != d["currency"]:
            c.run("UPDATE donations SET status = 'under_review' WHERE id = $1 AND status = 'awaiting_payment'", d["id"])
            open_risk_case(c, campaign_id=d["campaign_id"], donation_id=d["id"], reason_codes=["amount_mismatch"], level="high",
                           explanation=f"evento do provedor com valor/moeda diferente da cobrança: {event.get('amount_cents')} {event.get('currency')} ≠ {expected_total} {d['currency']}")
            _close(c, row_id, "applied", "divergência: doação em revisão")
            return rec | {"effect": "under_review"}
        if d["status"] in ("confirmed", "reconciled"):
            _close(c, row_id, "ignored", "já confirmada")
            return rec | {"effect": "already_confirmed"}
        if d["status"] not in ("awaiting_payment", "under_review"):
            _close(c, row_id, "ignored", f"estado {d['status']}")
            return rec | {"effect": "ignored", "note": f"estado {d['status']}"}
        c.run("UPDATE donations SET status = 'confirmed' WHERE id = $1", d["id"])
        _post_confirmation(c, d, source_event_id=row_id)
        _register_obligations(c, d, split_event=raw.get("split"), event_id=event["event_id"])
        issue_receipt(c, d["id"])
        if d["recurring_agreement_id"]:
            c.run("UPDATE recurring_donation_agreements SET failed_attempts = 0 WHERE id = $1", d["recurring_agreement_id"])
        out = rec | {"effect": "confirmed", "donation_id": d["id"]}
        if et in SETTLE_EVENTS:   # confirmação e liquidação no mesmo evento (ex.: PAYMENT_RECEIVED)
            d["status"] = "confirmed"
            settle = _apply_settlement(c, d, row_id=row_id, provider=provider, raw=raw, expected=expected_settlement, close=False)
            out["settlement"] = settle.get("effect")
        _close(c, row_id, "applied")
        _maybe_target_reached(c, d["campaign_id"])
        return out
    if et in REFUND_EVENTS or et in CHARGEBACK_EVENTS:
        kind = "chargeback" if et in CHARGEBACK_EVENTS else "refund"
        # A reversal already posted in the ledger wins over the status gate:
        # a repeated refund/chargeback event must never post a second reversal.
        if d["status"] in ("refunded", "chargeback") or int(d["refunded_cents"]) >= expected_total:
            _close(c, row_id, "ignored", "reversão já lançada")
            return rec | {"effect": "already_reversed"}
        if d["status"] not in ("confirmed", "reconciled", "refund_pending", "partially_refunded"):
            _close(c, row_id, "ignored", "reversão sem confirmação prévia")
            return rec | {"effect": "ignored", "note": "reversão sem confirmação prévia"}
        if int(d["refunded_cents"]) > 0:
            # já houve estorno parcial: a reversão total é o RESTANTE, como lançamento novo
            _post_partial_reversal(c, d, amount=expected_total - int(d["refunded_cents"]), source_event_id=row_id)
        else:
            _post_reversal(c, d, kind=kind, source_event_id=row_id)
        target = "chargeback" if kind == "chargeback" else "refunded"
        if d["status"] in ("confirmed", "reconciled") and target == "refunded":
            c.run("UPDATE donations SET status = 'refund_pending' WHERE id = $1", d["id"])
        c.run("UPDATE donations SET status = $2, refunded_cents = $3 WHERE id = $1", d["id"], target, expected_total)
        c.run("UPDATE donation_receipts SET status = 'voided', voided_at = now() WHERE donation_id = $1 AND status = 'issued'", d["id"])
        _obligations_on_reversal(c, d, note=kind)
        _close(c, row_id, "applied")
        return rec | {"effect": target, "donation_id": d["id"]}
    if et in EXPIRE_EVENTS:
        if d["status"] == "awaiting_payment":
            c.run("UPDATE donations SET status = 'expired' WHERE id = $1", d["id"])
            if d["recurring_agreement_id"]:
                _recurring_attempt_failed(c, d["recurring_agreement_id"])
        _close(c, row_id, "applied")
        return rec | {"effect": "expired" if d["status"] == "awaiting_payment" else "ignored"}
    _close(c, row_id, "ignored", "tipo de evento sem efeito")
    return rec | {"effect": "ignored", "note": "tipo de evento sem efeito"}


def _apply_settlement(c: Connection, d: dict, *, row_id: int, provider: str, raw: dict, expected: int, close: bool = True) -> dict:
    """Liquidação ACUMULADA: cada evento soma o que o provedor diz ter liquidado (sem valor = o total esperado). Só com o
    acumulado igual ao esperado a doação vira `settled_at`; antes disso é parcial e abre exceção para a conciliação."""
    informed = raw.get("settled_cents")
    amount = expected if informed is None else max(0, int(informed))
    cumulative = int(d["settled_cents"]) + amount
    c.run("UPDATE donations SET settled_cents = $2 WHERE id = $1", d["id"], cumulative)
    if cumulative >= expected:
        c.run("UPDATE donations SET settled_at = now() WHERE id = $1 AND settled_at IS NULL", d["id"])
        if close:
            _close(c, row_id, "applied", "liquidação")
        return {"effect": "settled", "donation_id": d["id"], "settled_cents": cumulative}
    from . import reconciliation as RECON
    RECON.open_from_event(c, kind="settlement_partial", campaign_id=d["campaign_id"], org_id=d["beneficiary_org_id"], donation_id=d["id"],
                          provider=provider, provider_ref=None, expected=expected, observed=cumulative,
                          detail=f"liquidação parcial: {cumulative} de {expected} centavos liquidados ao beneficiário")
    if close:
        _close(c, row_id, "applied", "liquidação parcial: exceção aberta")
    return {"effect": "settled_partial", "donation_id": d["id"], "settled_cents": cumulative}


def mark_event_failed(c: Connection, *, row_id: int, error: str) -> None:
    """Erro interno ao aplicar um evento já gravado: o evento fica `failed` (nunca perdido) e entra na fila de exceções."""
    c.run("UPDATE payment_provider_events SET processing_status = 'failed', processing_note = $2, processed_at = now()"
          " WHERE id = $1 AND processing_status IN ('received','failed')", row_id, ("erro ao aplicar: " + error)[:500])
    from . import reconciliation as RECON
    row = c.one("SELECT provider, event_id, provider_charge_id FROM payment_provider_events WHERE id = $1", row_id)
    if row:
        RECON.open_from_event(c, kind="event_processing_failed", campaign_id=None, org_id=None, donation_id=None, provider=row["provider"],
                              provider_ref=row["event_id"], expected=None, observed=None,
                              detail="evento assinado gravado e não aplicado; a rotina financeira reprocessa: " + error[:300])


def reprocess_pending_events(c: Connection, *, older_than_seconds: int = 60, limit: int = 200) -> dict:
    """Rotina (cenário 35): reaplica eventos ASSINADOS que ficaram `failed` ou `received` (o processo caiu entre gravar e
    aplicar). Cada um numa savepoint: um evento ruim não impede os outros. Idempotente pela trava da linha do evento."""
    rows = c.query("SELECT id, provider, event_id, event_type, provider_charge_id, amount_cents, payload_redacted FROM payment_provider_events"
                   " WHERE signature_verified AND processing_status IN ('failed','received')"
                   " AND received_at < now() - make_interval(secs => $1) ORDER BY id LIMIT $2", older_than_seconds, limit)
    done = failed = 0
    for r in rows:
        c.run("SAVEPOINT reprocess_event")
        try:
            apply_recorded_event(c, provider=r["provider"], row_id=int(r["id"]), event=event_from_row(r))
            c.run("RELEASE SAVEPOINT reprocess_event")
            done += 1
            c.run("UPDATE reconciliation_exceptions SET status = 'resolved', resolution_note = 'reprocessado pela rotina', resolved_at = now()"
                  " WHERE kind = 'event_processing_failed' AND provider_ref = $1 AND status IN ('open','assigned')", r["event_id"])
        except Exception as exc:  # noqa: BLE001 — um evento ruim não bloqueia a fila; fica registrado para a pessoa
            c.run("ROLLBACK TO SAVEPOINT reprocess_event")
            mark_event_failed(c, row_id=int(r["id"]), error=type(exc).__name__ + ": " + str(exc)[:200])
            failed += 1
    return {"reprocessed": done, "still_failing": failed}


# ============================================================================ recorrência (cenários 25 e 38)
def start_recurring(c: Connection, *, settings: Any, campaign_slug: str, donor_user_id: str, amount_cents: int, method: str,
                    consent_text: str) -> dict:
    """Autorização de doação recorrente: o doador consente (texto guardado por hash) e o provedor guarda o instrumento.
    Autorizar NÃO é cobrar: cada ciclo é uma tentativa, que vira doação confirmada só por evento do provedor."""
    if not getattr(settings, "recurring_donations_enabled", False):
        raise ApiError(503, "recurring_disabled", "Doação recorrente desligada: depende de instrumento homologado no provedor (ADR-375)")
    camp = c.one("SELECT id::text AS id, status, allow_recurring, min_donation_cents FROM campaigns WHERE slug = $1", campaign_slug)
    if not camp or camp["status"] not in ("published", "target_reached"):
        raise not_found("Campanha aberta a doações")
    if not camp["allow_recurring"]:
        raise unprocessable("esta campanha não aceita doação recorrente", code="recurring_not_allowed")
    if amount_cents < int(camp["min_donation_cents"]):
        raise unprocessable("valor abaixo do mínimo da campanha", code="below_minimum")
    if method not in ("card", "pix_automatic"):
        raise unprocessable("recorrência só por cartão ou Pix automático", code="method_unsupported")
    if len((consent_text or "").strip()) < 40:
        raise unprocessable("o texto de consentimento exibido ao doador é obrigatório", code="consent_required")
    prov = provider_for(settings)
    aid = c.scalar("INSERT INTO recurring_donation_agreements(campaign_id, donor_user_id, amount_cents, cadence, method, provider, consent_text_sha256,"
                   " status, next_charge_on) VALUES ($1,$2,$3,'monthly',$4,$5,$6,'active',current_date) RETURNING id::text",
                   camp["id"], donor_user_id, amount_cents, method, prov.name, hashlib.sha256(consent_text.strip().encode()).hexdigest())
    return recurring_view(c, aid)


def recurring_view(c: Connection, agreement_id: str) -> dict:
    r = c.one("SELECT r.id::text AS id, r.amount_cents, r.cadence, r.method, r.status, r.next_charge_on, r.consent_at, r.attempts, r.failed_attempts,"
              " r.last_attempt_at, r.cancelled_at, c.slug, c.title,"
              " (SELECT count(*) FROM donations d WHERE d.recurring_agreement_id = r.id AND d.status IN ('confirmed','reconciled','partially_refunded')) AS confirmed_n,"
              " (SELECT coalesce(sum(d.amount_cents - least(d.refunded_cents, d.amount_cents)),0) FROM donations d WHERE d.recurring_agreement_id = r.id"
              "   AND d.status IN ('confirmed','reconciled','partially_refunded')) AS received_cents,"
              " (SELECT count(*) FROM donations d WHERE d.recurring_agreement_id = r.id AND d.status IN ('expired','failed')) AS failed_n"
              " FROM recurring_donation_agreements r JOIN campaigns c ON c.id = r.campaign_id WHERE r.id = $1", agreement_id)
    if not r:
        raise not_found("Acordo recorrente")
    return r | {"definitions": {"consent_at": "autorização dada pelo doador (não é pagamento)", "attempts": "ciclos em que uma cobrança foi criada",
                                "confirmed_n": "ciclos confirmados pelo provedor", "received_cents": "soma confirmada e não estornada",
                                "failed_n": "ciclos expirados/falhos", "status": "active · paused (falhas seguidas) · cancelled (pelo doador)"}}


def _recurring_attempt_failed(c: Connection, agreement_id: str) -> None:
    c.run("UPDATE recurring_donation_agreements SET failed_attempts = failed_attempts + 1,"
          " status = CASE WHEN failed_attempts + 1 >= $2 AND status = 'active' THEN 'paused' ELSE status END WHERE id = $1",
          agreement_id, RECURRING_PAUSE_AFTER_FAILURES)


def run_recurring_cycle(c: Connection, *, settings: Any, cipher: Any, today: date | None = None) -> dict:
    """Rotina: para cada acordo ATIVO com ciclo vencido, cria UMA tentativa (doação aguardando pagamento) com chave de
    idempotência por acordo × número da tentativa. Pausado ou cancelado não gera tentativa. Nada aqui marca pago."""
    if not getattr(settings, "recurring_donations_enabled", False):
        return {"skipped": "recurring_disabled"}
    today = today or datetime.now(UTC).date()
    due = c.query("SELECT r.id::text AS id, r.donor_user_id::text AS donor_user_id, r.amount_cents, r.method, r.next_charge_on, r.attempts, c.slug"
                  " FROM recurring_donation_agreements r JOIN campaigns c ON c.id = r.campaign_id"
                  " WHERE r.status = 'active' AND r.next_charge_on <= $1 ORDER BY r.next_charge_on FOR UPDATE OF r SKIP LOCKED", today)
    created = failed = 0
    for r in due:
        # chave por acordo × número da tentativa: o contador sobe na MESMA transação que cria a doação, então uma rodada
        # repetida (worker reiniciado) não cria duas tentativas para o mesmo ciclo
        key = f"rec-{r['id'][:8]}-{int(r['attempts']) + 1}"
        c.run("SAVEPOINT recurring_cycle")
        try:
            start_donation(c, settings=settings, campaign_slug=r["slug"], amount_cents=int(r["amount_cents"]),
                           method="card" if r["method"] == "card" else "pix", donor_user_id=r["donor_user_id"], donor_display=None,
                           donor_email=None, public_anonymous=True, cover_costs=False, idempotency_key=key, cipher=cipher,
                           recurring_agreement_id=r["id"])
            c.run("RELEASE SAVEPOINT recurring_cycle")
            created += 1
        except ApiError:
            c.run("ROLLBACK TO SAVEPOINT recurring_cycle")
            _recurring_attempt_failed(c, r["id"])
            failed += 1
        nxt = _add_month(r["next_charge_on"])
        c.run("UPDATE recurring_donation_agreements SET attempts = attempts + 1, last_attempt_at = now(), next_charge_on = $2 WHERE id = $1",
              r["id"], nxt)
    return {"attempts_created": created, "attempts_failed": failed}


def _add_month(d: date) -> date:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    import calendar
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _entry(c: Connection, *, donation: dict, txn: str, account: str, side: str, amount: int, source_event_id: int | None, reversal_of: int | None = None, note: str | None = None) -> int:
    if amount <= 0:
        return 0   # parcela zero (tarifa zero do sandbox, taxa não declarada) não vira linha
    return int(c.scalar(
        "INSERT INTO donation_ledger_entries(donation_id, campaign_id, txn_id, account, side, amount_cents, currency, source_event_id,"
        " reversal_of, is_simulated, note) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING id",
        donation["id"], donation["campaign_id"], txn, account, side, amount, donation["currency"], source_event_id, reversal_of,
        donation["is_simulated"], note))


def _post_confirmation(c: Connection, d: dict, *, source_event_id: int) -> str:
    """Partidas dobradas de uma confirmação: C donor_payment (total pago) = D receivable + D provider_fee + D platform_fee_accrued + D fund."""
    txn = str(uuid.uuid4())
    total = int(d["amount_cents"]) + int(d["cover_costs_cents"])
    net = total - int(d["provider_fee_cents"]) - int(d["platform_fee_cents"]) - int(d["beneficiary_fund_cents"])
    _entry(c, donation=d, txn=txn, account="donor_payment", side="C", amount=total, source_event_id=source_event_id)
    _entry(c, donation=d, txn=txn, account="beneficiary_receivable", side="D", amount=net, source_event_id=source_event_id,
           note="o provedor deve ao beneficiário (a plataforma não recebe)")
    _entry(c, donation=d, txn=txn, account="provider_fee", side="D", amount=int(d["provider_fee_cents"]), source_event_id=source_event_id)
    _entry(c, donation=d, txn=txn, account="platform_fee_accrued", side="D", amount=int(d["platform_fee_cents"]), source_event_id=source_event_id,
           note="CALCULADA pela versão congelada; devida só com a regra ativa")
    _entry(c, donation=d, txn=txn, account="beneficiary_fund", side="D", amount=int(d["beneficiary_fund_cents"]), source_event_id=source_event_id,
           note="destinação declarada da organização; não é receita da plataforma")
    contrib = int(d.get("platform_contribution_cents") or 0)
    if contrib:
        # Contribuição VOLUNTÁRIA: par próprio, fora da arrecadação da campanha (que é só `donor_payment`).
        _entry(c, donation=d, txn=txn, account="donor_platform_contribution", side="C", amount=contrib, source_event_id=source_event_id,
               note="valor que o doador escolheu somar para a plataforma; não sai da doação")
        _entry(c, donation=d, txn=txn, account="platform_contribution_receivable", side="D", amount=contrib, source_event_id=source_event_id,
               note="a receber: pelo split (se homologado) ou da organização que recebeu o valor")
    return txn


def _post_reversal(c: Connection, d: dict, *, kind: str, source_event_id: int) -> str:
    """Reversão = lançamentos NOVOS espelhando a confirmação, nunca edição. D refund/chargeback (total) = C das contas originais."""
    txn = str(uuid.uuid4())
    orig = c.query("SELECT id, account, side, amount_cents FROM donation_ledger_entries WHERE donation_id = $1 AND reversal_of IS NULL"
                   " AND account NOT IN ('refund','chargeback') ORDER BY id", d["id"])
    for e in orig:
        if e["account"] == "donor_payment":
            _entry(c, donation=d, txn=txn, account=kind, side="D", amount=int(e["amount_cents"]), source_event_id=source_event_id, reversal_of=e["id"])
        else:   # espelho: o lado oposto do lançamento original, na mesma conta
            _entry(c, donation=d, txn=txn, account=e["account"], side="C" if e["side"] == "D" else "D", amount=int(e["amount_cents"]),
                   source_event_id=source_event_id, reversal_of=e["id"])
    return txn


def _post_partial_reversal(c: Connection, d: dict, *, amount: int, source_event_id: int) -> str:
    """Estorno PARCIAL: reverte `amount` do pagamento do doador contra o recebível do beneficiário. Tarifa, taxa e fundo
    ficam como lançados — quem os reverte (e se) é o contrato do provedor, e a divergência aparece na conciliação."""
    txn = str(uuid.uuid4())
    orig = c.one("SELECT id FROM donation_ledger_entries WHERE donation_id = $1 AND account = 'donor_payment' AND reversal_of IS NULL ORDER BY id LIMIT 1", d["id"])
    _entry(c, donation=d, txn=txn, account="refund", side="D", amount=amount, source_event_id=source_event_id, reversal_of=orig["id"] if orig else None,
           note="estorno parcial")
    _entry(c, donation=d, txn=txn, account="beneficiary_receivable", side="C", amount=amount, source_event_id=source_event_id,
           note="estorno parcial: o provedor deixa de dever esta parcela ao beneficiário")
    return txn


def _register_obligations(c: Connection, d: dict, *, split_event: Any = None, event_id: str | None = None) -> None:
    """Toda taxa CALCULADA vira obrigação registrada (estado `calculated`/`exempt`), nunca devida por si (ADR-377/379).

    A contribuição voluntária do doador (ADR-384) é outra coisa: o DOADOR já pagou; a obrigação nasce devida e, se o
    provedor confirmou o split da parcela da plataforma no próprio evento, nasce recebida (liquidação continua na conciliação)."""
    from . import remuneration as REM
    if int(d["platform_fee_cents"]) > 0:
        REM.register(c, org_id=d["beneficiary_org_id"], source_kind="donation", source_id=d["id"], rule_key="donation.platform_fee",
                     rule_version_id=d.get("fee_rule_version_id"), basis_cents=int(d["amount_cents"]), amount_cents=int(d["platform_fee_cents"]),
                     funding_source=d.get("funding_source") or "private", campaign_id=d["campaign_id"])
    contrib = int(d.get("platform_contribution_cents") or 0)
    if contrib:
        split_done = 0
        if int(d.get("split_platform_cents") or 0) and isinstance(split_event, list):
            split_done = sum(int(x.get("amount_cents") or 0) for x in split_event
                             if isinstance(x, dict) and x.get("receiver") == "platform" and x.get("status") == "done")
        REM.register_donor_contribution(c, org_id=d["beneficiary_org_id"], donation_id=d["id"], campaign_id=d["campaign_id"],
                                        amount_cents=contrib, split_received_cents=min(split_done, contrib),
                                        reference=f"split:{event_id}" if split_done else None)


def _obligations_on_reversal(c: Connection, d: dict, *, note: str) -> None:
    from . import remuneration as REM
    REM.reverse_for_source(c, source_kind="donation", source_id=d["id"], note=note)


def _maybe_target_reached(c: Connection, campaign_id: str) -> None:
    camp = c.one("SELECT status, target_cents FROM campaigns WHERE id = $1", campaign_id)
    if camp and camp["status"] == "published" and camp["target_cents"]:
        if campaign_totals(c, campaign_id)["net_after_reversals_cents"] >= int(camp["target_cents"]):
            c.run("UPDATE campaigns SET status = 'target_reached' WHERE id = $1", campaign_id)


def reconcile_campaign(c: Connection, campaign_id: str, *, provider_confirmed_ids: set[str] | None = None) -> dict:
    """Marca `reconciled` o que o provedor confirma (lista vinda da consulta ao provedor) e aponta divergências.
    No sandbox a lista vem da ferramenta de operação (não há consulta): o que não estiver nela fica como exceção."""
    rows = c.query("SELECT id::text AS id, provider_charge_id, status FROM donations WHERE campaign_id = $1 AND status = 'confirmed'", campaign_id)
    ok, exceptions = 0, []
    for r in rows:
        if provider_confirmed_ids is None or r["provider_charge_id"] in provider_confirmed_ids:
            c.run("UPDATE donations SET status = 'reconciled' WHERE id = $1", r["id"])
            ok += 1
        else:
            exceptions.append(r["id"])
    return {"reconciled": ok, "exceptions": exceptions, "at": datetime.now(UTC).isoformat()}


# ============================================================================ risco (graduado, explicável, humano)
RISK_RULES_VERSION = "donation-risk-2026-10.1"   # ver config/donation_risk_rules.json


def _risk_screen(c: Connection, *, donation_id: str, campaign_id: str, amount_cents: int, donor_user_id: str | None) -> None:
    """Regras simples e declaradas. Nenhuma é limite legal. Resultado: caso para revisão humana, nunca bloqueio de dinheiro."""
    reasons = []
    if amount_cents >= 10_000_00:
        reasons.append("large_single_donation")
    n_recent = c.scalar("SELECT count(*) FROM donations WHERE campaign_id = $1 AND created_at > now() - interval '10 minutes'", campaign_id)
    if int(n_recent or 0) >= 20:
        reasons.append("burst_attempts")
    age_days = c.scalar("SELECT extract(epoch FROM now() - coalesce(published_at, created_at)) / 86400 FROM campaigns WHERE id = $1", campaign_id)
    if age_days is not None and float(age_days) < 1 and amount_cents >= 2_000_00:
        reasons.append("new_campaign_large_inflow")
    if reasons:
        level = "high" if "large_single_donation" in reasons else "medium"
        open_risk_case(c, campaign_id=campaign_id, donation_id=donation_id, reason_codes=reasons, level=level,
                       explanation="sinais de risco configurados (" + ", ".join(reasons) + "); revisão humana; nenhum valor é retido pela plataforma")


def open_risk_case(c: Connection, *, campaign_id: str | None, donation_id: str | None, reason_codes: list[str], level: str, explanation: str) -> str:
    rid = c.scalar("INSERT INTO donation_risk_cases(campaign_id, donation_id, reason_codes, level, action, rule_version, explanation)"
                   " VALUES ($1,$2,$3,$4,'review',$5,$6) RETURNING id::text", campaign_id, donation_id, reason_codes, level, RISK_RULES_VERSION, explanation)
    if donation_id:
        c.run("UPDATE donations SET risk_case_id = $2 WHERE id = $1 AND risk_case_id IS NULL", donation_id, rid)
    return rid


def decide_risk_case(c: Connection, *, case_id: str, decided_by: str, action: str, note: str) -> dict:
    if action not in ("allow", "request_information", "reject", "report_to_provider"):
        raise unprocessable("ação não permitida nesta versão (payout_hold exige contrato com o provedor)", code="risk_action")
    if len(note or "") < 10:
        raise unprocessable("decisão exige justificativa", code="decision_note_required")
    if not c.run("UPDATE donation_risk_cases SET status = 'decided', action = $2, decided_by = $3, decided_at = now(), decision_note = $4"
                 " WHERE id = $1 AND status = 'open'", case_id, action, decided_by, note):
        raise not_found("Caso de risco aberto")
    return {"id": case_id, "action": action}


# ============================================================================ comprovante
def issue_receipt(c: Connection, donation_id: str) -> dict:
    d = c.one("SELECT d.id::text AS id, d.amount_cents, d.beneficiary_org_id::text AS org, d.confirmed_at, c.purpose, c.title"
              " FROM donations d JOIN campaigns c ON c.id = d.campaign_id WHERE d.id = $1", donation_id)
    if c.scalar("SELECT 1 FROM donation_receipts WHERE donation_id = $1", donation_id):
        return c.one("SELECT number, issued_at FROM donation_receipts WHERE donation_id = $1", donation_id)
    year = (d["confirmed_at"] or datetime.now(UTC)).year
    seq = c.scalar("SELECT count(*) + 1 FROM donation_receipts WHERE number LIKE $1", f"IMP-DOA-{year}-%")
    number = f"IMP-DOA-{year}-{int(seq):06d}"
    content = f"{number}|{d['id']}|{d['amount_cents']}|{d['org']}|{d['title']}"
    sha = hashlib.sha256(content.encode()).hexdigest()
    c.run("INSERT INTO donation_receipts(donation_id, number, issuer_org_id, amount_cents, purpose, content_sha256)"
          " VALUES ($1,$2,$3,$4,$5,$6)", donation_id, number, d["org"], d["amount_cents"], d["purpose"], sha)
    return {"number": number}


def receipt_view(c: Connection, donation_id: str) -> dict:
    r = c.one("SELECT r.number, r.kind, r.amount_cents, r.purpose, r.status, r.issued_at, r.content_sha256, o.legal_name AS issuer,"
              " d.is_simulated, d.confirmed_at, d.method, c.title AS campaign_title FROM donation_receipts r"
              " JOIN donations d ON d.id = r.donation_id JOIN organizations o ON o.id = r.issuer_org_id JOIN campaigns c ON c.id = d.campaign_id"
              " WHERE r.donation_id = $1", donation_id)
    if not r:
        raise not_found("Comprovante")
    return r | {"what_this_is": "Comprovante de doação confirmada pelo provedor de pagamento. NÃO é recibo para dedução fiscal nem "
                                "nota fiscal: a dedutibilidade depende da natureza do beneficiário e da legislação; texto sujeito a revisão contábil/jurídica."}


# ============================================================================ campanha: ciclo de vida (operador da organização)
def require_campaign_owner(c: Connection, campaign_id: str, org_id: str) -> dict:
    camp = c.one("SELECT id::text AS id, org_id::text AS org_id, beneficiary_org_id::text AS beneficiary_org_id, status, slug, created_by::text AS created_by,"
                 " qr_version FROM campaigns WHERE id = $1", campaign_id)
    if not camp or camp["org_id"] != org_id:
        raise not_found("Campanha")
    return camp


def submit_for_review(c: Connection, *, campaign_id: str, org_id: str, actor: str) -> dict:
    camp = require_campaign_owner(c, campaign_id, org_id)
    if camp["status"] not in ("draft", "rejected"):
        raise unprocessable(f"campanha em '{camp['status']}' não pode ser enviada para revisão", code="campaign_state")
    missing = [k for k in ("purpose", "contingency_policy", "refund_policy") if not c.scalar(f"SELECT {k} FROM campaigns WHERE id = $1", campaign_id)]
    if missing:
        raise unprocessable("faltam: " + ", ".join(missing), code="campaign_incomplete")
    c.run("UPDATE campaigns SET status = 'pending_review', policy_version = $2, accepted_terms_at = now() WHERE id = $1", campaign_id, TERMS_VERSION)
    return {"status": "pending_review", "policy_version": TERMS_VERSION}


def review(c: Connection, *, campaign_id: str, reviewer: str, approve: bool, note: str) -> dict:
    if len(note or "") < 10:
        raise unprocessable("revisão exige justificativa", code="review_note_required")
    camp = c.one("SELECT status, created_by::text AS created_by FROM campaigns WHERE id = $1", campaign_id)
    if not camp:
        raise not_found("Campanha")
    if camp["status"] != "pending_review":
        raise unprocessable("só campanha em revisão é aprovada ou rejeitada", code="campaign_state")
    if camp["created_by"] == reviewer:
        raise forbidden("quem criou a campanha não a revisa", "self_review")
    c.run("UPDATE campaigns SET status = $2, reviewed_by = $3, reviewed_at = now(), review_note = $4 WHERE id = $1",
          campaign_id, "approved" if approve else "rejected", reviewer, note)
    return {"status": "approved" if approve else "rejected"}


def suspend(c: Connection, *, campaign_id: str, reviewer: str, note: str, reinstate: bool = False) -> dict:
    """Administração tira uma campanha publicada do ar (`under_review`) ou a devolve ao ar. Sempre com justificativa."""
    if len(note or "") < 10:
        raise unprocessable("suspensão exige justificativa", code="review_note_required")
    camp = c.one("SELECT status FROM campaigns WHERE id = $1", campaign_id)
    if not camp:
        raise not_found("Campanha")
    if reinstate:
        if camp["status"] != "under_review":
            raise unprocessable("só campanha em análise volta ao ar", code="campaign_state")
        target = "published"
    else:
        if camp["status"] not in ("published", "paused", "target_reached"):
            raise unprocessable("só campanha no ar é suspensa", code="campaign_state")
        target = "under_review"
    c.run("UPDATE campaigns SET status = $2, reviewed_by = $3, reviewed_at = now(), review_note = $4 WHERE id = $1", campaign_id, target, reviewer, note)
    return {"status": target}


def publish(c: Connection, *, settings: Any, campaign_id: str, org_id: str) -> dict:
    camp = require_campaign_owner(c, campaign_id, org_id)
    if not getattr(settings, "campaign_publication_enabled", True):
        raise ApiError(503, "campaign_publication_disabled", "Publicação de campanhas desligada nesta instalação")
    if camp["status"] != "approved":
        raise unprocessable("publicar exige campanha aprovada", code="campaign_state")
    if not c.scalar("SELECT beneficiary_verified($1)", camp["beneficiary_org_id"]):
        raise unprocessable("beneficiário sem verificação válida: a campanha não vai ao ar", code="beneficiary_not_verified")
    c.run("UPDATE campaigns SET status = 'published' WHERE id = $1", campaign_id)
    return {"status": "published", "url": canonical_url(settings, camp["slug"], camp["qr_version"])}


def rotate_qr(c: Connection, *, settings: Any, campaign_id: str, org_id: str) -> dict:
    camp = require_campaign_owner(c, campaign_id, org_id)
    v = c.scalar("UPDATE campaigns SET qr_version = qr_version + 1 WHERE id = $1 RETURNING qr_version", campaign_id)
    return {"qr_version": v, "url": canonical_url(settings, camp["slug"], v)}


def accountability(c: Connection, *, campaign_id: str, org_id: str) -> dict:
    camp = require_campaign_owner(c, campaign_id, org_id)
    totals = campaign_totals(c, campaign_id)
    expenses = c.query("SELECT id::text AS id, description, budget_line, amount_cents, spent_on, evidence_status, document_id::text AS document_id"
                       " FROM campaign_expenses WHERE campaign_id = $1 ORDER BY spent_on DESC", campaign_id)
    donations = c.query("SELECT id::text AS id, status, amount_cents, method, is_simulated, confirmed_at, public_anonymous,"
                        " CASE WHEN public_anonymous THEN NULL ELSE donor_display END AS donor_display"
                        " FROM donations WHERE campaign_id = $1 ORDER BY created_at DESC LIMIT 200", campaign_id)
    risk = c.query("SELECT id::text AS id, level, action, status, reason_codes, created_at FROM donation_risk_cases WHERE campaign_id = $1 AND status = 'open'", campaign_id)
    updates = c.query("SELECT id::text AS id, title, body, is_public, created_at FROM campaign_updates WHERE campaign_id = $1 ORDER BY created_at DESC LIMIT 50", campaign_id)
    declared = sum(int(e["amount_cents"]) for e in expenses)
    validated = sum(int(e["amount_cents"]) for e in expenses if e["evidence_status"] == "validated")
    external = c.query("SELECT id::text AS id, kind, source_name, funding_source, instrument_ref, amount_cents, in_kind_description, received_on, status, note"
                       " FROM external_resources WHERE campaign_id = $1 ORDER BY received_on DESC", campaign_id)
    pledges = c.query("SELECT id::text AS id, pledger_display, amount_cents, expected_on, status, fulfilled_donation_id::text AS fulfilled_donation_id, created_at"
                      " FROM donation_pledges WHERE campaign_id = $1 ORDER BY created_at DESC", campaign_id)
    obligations = c.query("SELECT id::text AS id, rule_key, basis_cents, amount_cents, state, funding_source, due_on FROM remuneration_obligations"
                          " WHERE campaign_id = $1 ORDER BY created_at DESC", campaign_id)
    exceptions = c.query("SELECT id::text AS id, kind, priority, status, detail, created_at FROM reconciliation_exceptions WHERE campaign_id = $1 AND status IN ('open','assigned')", campaign_id)
    return {"campaign": camp, "totals": totals, "expenses": expenses, "updates": updates, "donations": donations, "open_risk_cases": risk,
            "external_resources": external, "pledges": pledges, "remuneration_obligations": obligations, "reconciliation_exceptions": exceptions,
            "expenses_declared_cents": declared, "expenses_validated_cents": validated,
            "definitions": {"gross_confirmed_cents": "soma das doações confirmadas pelo provedor",
                            "beneficiary_net_estimated_cents": "bruto − tarifa do provedor − taxa calculada − fundo − estornos; estimado até conciliar",
                            "platform_fee_accrued_cents": "taxa CALCULADA (hipótese 1 %); devida só com a regra ativa — hoje R$ 0,00 devido",
                            "expenses_declared_cents": "o que a organização declarou; 'validated' = com documento aceito"}}


# ============================================================================ recursos externos, compromissos, financiador (v0.34.0, ADR-382)
def declare_external_resource(c: Connection, *, campaign_id: str, org_id: str, user_id: str, kind: str, source_name: str, funding_source: str,
                              instrument_ref: str | None, amount_cents: int | None, in_kind_description: str | None, received_on: str,
                              evidence_document_id: str | None, note: str | None) -> str:
    camp = require_campaign_owner(c, campaign_id, org_id)
    if kind == "in_kind" and amount_cents is not None:
        raise unprocessable("apoio não financeiro não tem valor em dinheiro", code="in_kind_amount")
    if kind != "in_kind" and not amount_cents:
        raise unprocessable("recurso financeiro exige valor", code="amount_required")
    if funding_source in ("public", "mixed") and not instrument_ref:
        raise unprocessable("recurso público exige o instrumento (termo, convênio, edital)", code="instrument_required")
    return c.scalar("INSERT INTO external_resources(org_id, campaign_id, project_id, kind, source_name, funding_source, instrument_ref, amount_cents,"
                    " in_kind_description, received_on, evidence_document_id, status, note, declared_by)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14) RETURNING id::text",
                    org_id, campaign_id, camp.get("project_id"), kind, source_name, funding_source, instrument_ref, amount_cents, in_kind_description,
                    received_on, evidence_document_id, "documented" if evidence_document_id else "declared", note, user_id)


def make_pledge(c: Connection, *, campaign_slug: str, user_id: str, org_id: str | None, display: str | None, amount_cents: int,
                expected_on: str | None, note: str | None) -> dict:
    camp = c.one("SELECT id::text AS id, beneficiary_org_id::text AS beneficiary_org_id, status FROM campaigns WHERE slug = $1", campaign_slug)
    if not camp or camp["status"] not in ("published", "target_reached"):
        raise not_found("Campanha aberta a doações")
    if amount_cents <= 0:
        raise unprocessable("valor do compromisso deve ser positivo", code="amount")
    pid = c.scalar("INSERT INTO donation_pledges(campaign_id, beneficiary_org_id, pledger_user_id, pledger_org_id, pledger_display, amount_cents, expected_on, note)"
                   " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id::text", camp["id"], camp["beneficiary_org_id"], user_id, org_id, display, amount_cents, expected_on, note)
    return {"id": pid, "status": "pledged", "note": "compromisso registrado; NÃO é doação confirmada nem dinheiro recebido"}


def fulfill_pledge(c: Connection, *, pledge_id: str, org_id: str, donation_id: str) -> dict:
    p = c.one("SELECT id::text AS id, campaign_id::text AS campaign_id, beneficiary_org_id::text AS org, status, amount_cents FROM donation_pledges WHERE id = $1", pledge_id)
    if not p or p["org"] != org_id:
        raise not_found("Compromisso")
    if p["status"] != "pledged":
        raise unprocessable("compromisso não está aberto", code="pledge_state")
    d = c.one("SELECT id::text AS id, campaign_id::text AS campaign_id, status FROM donations WHERE id = $1", donation_id)
    if not d or d["campaign_id"] != p["campaign_id"] or d["status"] not in ("confirmed", "reconciled", "partially_refunded"):
        raise unprocessable("só doação CONFIRMADA da mesma campanha cumpre um compromisso", code="donation_state")
    c.run("UPDATE donation_pledges SET status = 'fulfilled', fulfilled_donation_id = $2 WHERE id = $1", pledge_id, donation_id)
    return {"status": "fulfilled"}


def cancel_pledge(c: Connection, *, pledge_id: str, user_id: str) -> dict:
    if not c.run("UPDATE donation_pledges SET status = 'cancelled' WHERE id = $1 AND pledger_user_id = $2 AND status = 'pledged'", pledge_id, user_id):
        raise not_found("Compromisso")
    return {"status": "cancelled"}


def funder_view(c: Connection, *, org_id: str) -> dict:
    """Painel do financiador: o que a organização doou/comprometeu, com estado e comprovante — nunca dados de outros doadores."""
    rows = c.query("SELECT d.id::text AS id, d.status, d.amount_cents, d.refunded_cents, d.confirmed_at, d.settled_at, d.created_at, d.is_simulated,"
                   " c.slug, c.title AS campaign_title, o.legal_name AS beneficiary, r.number AS receipt_number"
                   " FROM donations d JOIN campaigns c ON c.id = d.campaign_id JOIN organizations o ON o.id = d.beneficiary_org_id"
                   " LEFT JOIN donation_receipts r ON r.donation_id = d.id WHERE d.donor_org_id = $1 ORDER BY d.created_at DESC LIMIT 200", org_id)
    pledges = c.query("SELECT p.id::text AS id, p.amount_cents, p.expected_on, p.status, c.slug, c.title AS campaign_title FROM donation_pledges p"
                      " JOIN campaigns c ON c.id = p.campaign_id WHERE p.pledger_org_id = $1 ORDER BY p.created_at DESC", org_id)
    tot = {"confirmed_cents": sum(int(r["amount_cents"]) - int(r["refunded_cents"]) for r in rows if r["status"] in ("confirmed", "reconciled", "partially_refunded")),
           "pending_cents": sum(int(r["amount_cents"]) for r in rows if r["status"] == "awaiting_payment"),
           "reversed_cents": sum(int(r["refunded_cents"]) for r in rows),
           "pledged_cents": sum(int(p["amount_cents"]) for p in pledges if p["status"] == "pledged")}
    campaigns = sorted({r["slug"] for r in rows})
    return {"donations": rows, "pledges": pledges, "totals": tot, "campaigns_supported": campaigns,
            "definitions": {"confirmed_cents": "doações confirmadas pelo provedor, líquidas de estornos", "pending_cents": "cobranças não pagas — não é doação",
                            "pledged_cents": "compromissos — não é dinheiro"},
            "note": "Resultados das campanhas apoiadas são os declarados pelas organizações na prestação de contas; validação é indicada item a item."}
