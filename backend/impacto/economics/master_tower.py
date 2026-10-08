"""Torre de controle MASTER / financeira (v0.27.0) — a visão do proprietário sobre o que o IMPACTO ganha.

Regras, na ordem em que importam:

* **Nenhum saldo inventado.** Onde não há conexão com dado real (conta bancária, provedor de pagamento ao
  vivo) o bloco diz `DADO FINANCEIRO NÃO CONECTADO` e devolve `null`, nunca zero: zero seria uma medição.
* **GMV ≠ receita.** O valor financiado (instruído e confirmado entre as partes) é mostrado em bloco
  próprio e nunca se soma à camada da plataforma.
* **Camada econômica vem do livro.** `economic_events` é a única fonte de registrado / devido / pago da
  plataforma; a participação de autoria sai em bloco próprio e é dita como NÃO receita.
* **Value Capture Ratio só quando há o que medir.** A razão entre o que a plataforma capturou (pago) e o
  valor que passou pelo ecossistema (GMV confirmado) é `NÃO MEDIDO` enquanto o denominador for zero —
  o que, numa instalação sem operação quitada, é o estado verdadeiro.
* **Só leitura.** A torre aponta para onde se decide (regras de monetização, cobranças, acordos).
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection

NOT_CONNECTED = "DADO FINANCEIRO NÃO CONECTADO"
NOT_MEASURED = "NÃO MEDIDO"


def _i(v: Any) -> int:
    return int(v or 0)


def master(conn: Connection, *, settings: Any = None) -> dict:
    from . import metrics as MET
    from . import payments as PAY
    from .value_ledger import ai_cost_summary

    # ------------------------------------------------------------------ 1. GMV: o que passa pelo ecossistema
    gmv = conn.one(
        "SELECT coalesce(sum(a.gross_cents), 0) AS gross_active,"
        " count(DISTINCT a.agreement_id) AS agreements"
        " FROM agreement_allocations a JOIN signed_agreements s ON s.id = a.agreement_id"
        " WHERE s.status = 'active' AND a.version = s.version")
    fluxo = conn.one(
        "SELECT coalesce(sum(amount_cents) FILTER (WHERE kind = 'project_funds_instructed'), 0) AS instructed,"
        " coalesce(sum(amount_cents) FILTER (WHERE kind = 'project_funds_confirmed'), 0) AS confirmed,"
        " count(DISTINCT agreement_id) FILTER (WHERE kind = 'operation_settled') AS settled"
        " FROM economic_events")
    compromissos = conn.one(
        "SELECT coalesce(sum(amount_cents) FILTER (WHERE status <> 'cancelled'), 0) AS committed,"
        " coalesce(sum(amount_cents) FILTER (WHERE status = 'confirmed'), 0) AS confirmed FROM commitments")
    gmv_block = {
        "funding_agreements_active": _i(gmv["agreements"]),
        "gross_contracted_cents": _i(gmv["gross_active"]),
        "project_funds_instructed_cents": _i(fluxo["instructed"]),
        "project_funds_confirmed_cents": _i(fluxo["confirmed"]),
        "operations_settled": _i(fluxo["settled"]),
        "commitments_registered_cents": _i(compromissos["committed"]),
        "commitments_confirmed_cents": _i(compromissos["confirmed"]),
        "source": "agreement_allocations (versão vigente de acordo ativo) · economic_events · commitments",
        "warning": "GMV NÃO é receita da plataforma. Nenhum destes valores passa pela plataforma (ADR-284).",
    }

    # ------------------------------------------------------------------ 2. camada da plataforma (3,5%)
    op = MET.operation_revenue(conn)
    por_mes = conn.query(
        "SELECT to_char(date_trunc('month', created_at), 'YYYY-MM') AS month,"
        " coalesce(sum(amount_cents) FILTER (WHERE kind = 'platform_service_registered'), 0)"
        "   - coalesce(sum(amount_cents) FILTER (WHERE kind = 'reversal' AND rule_key = 'contract.platform_service_fee'), 0) AS registered_cents,"
        " coalesce(sum(amount_cents) FILTER (WHERE kind = 'platform_service_due'), 0) AS due_cents,"
        " coalesce(sum(amount_cents) FILTER (WHERE kind = 'platform_service_paid'), 0) AS paid_cents,"
        " coalesce(sum(amount_cents) FILTER (WHERE kind = 'project_funds_confirmed'), 0) AS gmv_confirmed_cents"
        " FROM economic_events GROUP BY 1 ORDER BY 1 DESC LIMIT 24")
    regra = conn.one("SELECT key, active, legal_status FROM monetization_rules WHERE key = 'contract.platform_service_fee'")
    platform_block = {
        "registered": op["platform_layer_registered"],
        "due": op["platform_layer_due"],
        "paid": op["platform_layer_paid"],
        "operations": op["operations"],
        "by_month": por_mes,
        "rule": {"key": regra["key"] if regra else None, "active": bool(regra and regra["active"]),
                 "legal_status": regra["legal_status"] if regra else None},
        "pricing": _pricing(conn),
        "note": ("Registrado = 3,5% congelado na matriz do acordo na ativação. Devido = a parcela registrada com a regra "
                 "comercial ATIVA. Pago = repasse à plataforma confirmado pela própria plataforma. Enquanto a regra "
                 "estiver inativa (carta amarela), nada fica devido e nada é cobrado — o registro existe para que a "
                 "receita possível seja conhecida sem ser inventada."),
    }

    # ------------------------------------------------------------------ 3. participação de autoria (1,5%) — NÃO é receita
    participation_block = {
        "accrued": op["participation_accrued"],
        "paid": op["participation_paid"],
        "participations": conn.query("SELECT status, count(*) AS n FROM proponent_participations GROUP BY status ORDER BY status"),
        "note": "Vai do financiador ao proponente, pela chave PIX do contrato. Não passa pela plataforma e não é receita dela.",
    }

    # ------------------------------------------------------------------ 4. marketplace — sem percentual
    mk = conn.one("SELECT count(*) AS listings, count(*) FILTER (WHERE publication_state = 'published') AS active FROM marketplace_listings")
    take = conn.one("SELECT legal_status, active FROM monetization_rules WHERE key = 'marketplace.take_rate'")
    marketplace_block = {
        "listings": _i(mk["listings"]), "listings_active": _i(mk["active"]),
        "take_rate": {"percent": None, "status": take["legal_status"] if take else None, "active": bool(take and take["active"])},
        "revenue_cents": 0,
        "note": "Sem percentual: a comissão de marketplace está RECUSADA (ADR-022/ADR-178). Contratação e pagamento acontecem entre as partes.",
    }

    # ------------------------------------------------------------------ 5. IA / API (uso)
    ia = ai_cost_summary(conn, days=30)
    api_use = conn.one(
        "SELECT (SELECT count(*) FROM integration_credentials) AS credentials,"
        " (SELECT count(*) FROM integration_subscriptions WHERE status = 'active') AS webhook_subscriptions,"
        " (SELECT count(*) FROM integration_deliveries WHERE created_at > now() - interval '30 days') AS deliveries_30d")
    usage_block = {
        "ai_calls_30d": ia["totals"]["calls"],
        "ai_cost_cents_estimate_30d": ia["totals"]["cost_cents_estimate"],
        "ai_calls_without_price_table": ia["totals"]["calls_without_price_table"],
        "api_credentials": _i(api_use["credentials"]),
        "webhook_subscriptions_active": _i(api_use["webhook_subscriptions"]),
        "webhook_deliveries_30d": _i(api_use["deliveries_30d"]),
        "revenue_cents": 0,
        "note": "Uso medido; receita por uso é ZERO por construção: não há preço de excedente publicado nem regra ativa (exceder o limite interrompe, não cobra).",
    }

    # ------------------------------------------------------------------ 6. contratos avulsos/parcelados (enterprise / governo)
    ct = conn.one(
        "SELECT count(*) FILTER (WHERE a.consent_status = 'authorized' AND a.revoked_at IS NULL) AS authorized,"
        " coalesce(sum(o.amount_cents) FILTER (WHERE a.consent_status = 'authorized' AND a.revoked_at IS NULL), 0) AS authorized_cents,"
        " count(*) FILTER (WHERE a.consent_status = 'free_access') AS free_access,"
        " (SELECT count(*) FROM commercial_offers WHERE status = 'open') AS open_offers"
        " FROM offer_acceptances a JOIN commercial_offers o ON o.id = a.offer_id")
    licencas = conn.one("SELECT count(*) AS n FROM entitlement_grants WHERE source IN ('license','gov','contract') AND revoked_at IS NULL AND (ends_at IS NULL OR ends_at > now())")
    contracts_block = {
        "authorized": _i(ct["authorized"]), "authorized_value_cents": _i(ct["authorized_cents"]),
        "free_access_acceptances": _i(ct["free_access"]), "open_offers": _i(ct["open_offers"]),
        "licenses_active": _i(licencas["n"]),
        "note": "Valor contratado com autorização de cobrança (não é caixa). Sem assinatura: contratos são avulsos ou parcelados e não renovam sozinhos (ADR-341).",
    }

    # ------------------------------------------------------------------ 7. a receber / cobranças próprias
    rec = conn.one(
        "SELECT coalesce(sum(amount_cents) FILTER (WHERE state IN ('created','checkout_started','pending','authorized') AND NOT is_simulated), 0) AS open_real,"
        " coalesce(sum(amount_cents) FILTER (WHERE state IN ('created','checkout_started','pending','authorized') AND is_simulated), 0) AS open_simulated,"
        " coalesce(sum(amount_cents) FILTER (WHERE state IN ('paid','settled') AND NOT is_simulated), 0) AS paid_real,"
        " coalesce(sum(amount_cents) FILTER (WHERE state IN ('paid','settled') AND is_simulated), 0) AS paid_simulated,"
        " count(*) FILTER (WHERE state = 'disputed') AS disputed"
        " FROM platform_charges")
    inv = conn.one("SELECT coalesce(sum(amount_cents) FILTER (WHERE status = 'open'), 0) AS open_cents, count(*) FILTER (WHERE status = 'open') AS n FROM invoices")
    payouts = conn.one(
        "SELECT count(*) FILTER (WHERE state = 'awaiting_rule') AS awaiting_rule,"
        " coalesce(sum(amount_cents) FILTER (WHERE state = 'awaiting_rule'), 0) AS awaiting_rule_cents,"
        " count(*) FILTER (WHERE state IN ('instruction_created','payment_pending')) AS open,"
        " coalesce(sum(amount_cents) FILTER (WHERE state IN ('instruction_created','payment_pending')), 0) AS open_cents,"
        " coalesce(sum(confirmed_cents), 0) AS confirmed_cents"
        " FROM allocation_payouts WHERE line_kind = 'platform_fee'")
    st = PAY.status(settings) if settings is not None else {"provider": "none", "configured": False}
    receivables_block = {
        "charges_open_real_cents": _i(rec["open_real"]), "charges_open_simulated_cents": _i(rec["open_simulated"]),
        "charges_paid_real_cents": _i(rec["paid_real"]), "charges_paid_simulated_cents": _i(rec["paid_simulated"]),
        "invoices_open_cents": _i(inv["open_cents"]), "invoices_open": _i(inv["n"]),
        "platform_fee_instructions_awaiting_rule": _i(payouts["awaiting_rule"]),
        "platform_fee_awaiting_rule_cents": _i(payouts["awaiting_rule_cents"]),
        "platform_fee_instructions_open": _i(payouts["open"]), "platform_fee_open_cents": _i(payouts["open_cents"]),
        "platform_fee_confirmed_cents": _i(payouts["confirmed_cents"]),
        "payment_provider": st,
        "note": ("`awaiting_rule` = instrução da linha da plataforma que fica parada até a regra comercial ter carta verde. "
                 "Simulado nunca entra em real."),
    }

    # ------------------------------------------------------------------ 8. banco: não conectado
    bank_block = {"status": NOT_CONNECTED, "balance_cents": None, "reconciled_until": None,
                  "note": "Não há integração bancária nem leitura de extrato. O que existe é o registro das partes e a conciliação manual com nota (payouts/reconcile)."}

    # ------------------------------------------------------------------ 9. captura de valor
    ve = conn.one("SELECT count(*) AS events, count(DISTINCT org_id) AS orgs FROM value_events")
    paid = _i(op["platform_layer_paid"]["value"])
    gmv_conf = _i(fluxo["confirmed"])
    ratio = round(paid / gmv_conf, 6) if gmv_conf > 0 and paid > 0 else None
    value_capture_block = {
        "value_events": _i(ve["events"]), "organizations_with_value_events": _i(ve["orgs"]),
        "value_capture_ratio": ratio,
        "value_capture_ratio_status": "medido" if ratio is not None else NOT_MEASURED,
        "formula": "camada da plataforma PAGA ÷ recursos de projeto CONFIRMADOS (ambos do livro economic_events)",
        "note": ("Evento de valor → evento econômico → cobrança própria: a cadeia está ligada (value_events contract.activated / "
                 "allocation.instructed / payout.confirmed / operation.settled → economic_events). A razão só é dita quando há "
                 "denominador e numerador; antes disso é NÃO MEDIDO, não zero."),
    }

    # ------------------------------------------------------------------ 10. regras
    regras = conn.query("SELECT key, label_pt, legal_status, active, pricing_mode FROM monetization_rules ORDER BY engine_rank, key")

    return {
        "gmv": gmv_block,
        "platform_layer": platform_block,
        "participation": participation_block,
        "marketplace": marketplace_block,
        "usage": usage_block,
        "contracts": contracts_block,
        "receivables": receivables_block,
        "bank": bank_block,
        "value_capture": value_capture_block,
        "rules": regras,
        "subscription": {"exists": False, "note": "Não existe assinatura (ADR-341): nenhuma receita recorrente de mensalidade."},
        "honesty": [
            "Nenhum número aqui é saldo: a plataforma não custodia (ADR-284).",
            "GMV e receita saem em blocos separados e nunca se somam.",
            "Camada registrada não é receita; devida só com regra ativa; paga só com confirmação.",
            f"Banco: {NOT_CONNECTED}.",
        ],
        "links": {"rules": "/admin/monetizacao", "charges": "/admin/pagamentos", "agreements": "/acordos", "model": "24_MONTH_FINANCIAL_MODEL.md"},
    }


def _pricing(conn: Connection) -> dict:
    from ..services.monetization import pricing_version_name
    pv = pricing_version_name()
    rows = conn.query("SELECT key, bps, payer_role, recipient_kind FROM economic_rules WHERE pricing_version = $1 ORDER BY key", pv)
    return {"pricing_version": pv, "rules": rows,
            "note": "Percentuais do catálogo versionado, congelados em cada acordo. Nunca em código."}
