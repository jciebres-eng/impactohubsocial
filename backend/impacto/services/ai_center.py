"""Central de IA (v0.28.0): saldo, cotas, pacotes, pedidos de crédito por PIX, patrocínio e painel financeiro.

Regras que este módulo aplica (e o banco reforça, migração 0068):
  * crédito COMPRADO só nasce de pedido real com pagamento confirmado por webhook assinado ou conciliação
    manual com referência; a página de retorno nunca credita;
  * pedido em modo PILOTO (regra comercial inativa ou provedor ausente) nunca vira compra: a administração
    pode aprová-lo como concessão de piloto (crédito PROMOCIONAL), com nota;
  * patrocínio compromete créditos do PRÓPRIO patrocinador; esgotado ou encerrado, para;
  * nenhuma venda sem a regra `ai.credits_prepaid` ativa (carta legal verde) — ADR-349.
"""
from __future__ import annotations

import hashlib
from typing import Any

from ..economics import payments
from ..engines.ai import usage_control as UC
from ..http import ApiError, forbidden, not_found, unprocessable

CREDIT_TERMS_V1 = ("Créditos de uso do IMPACTO: unidade de consumo de operações de inteligência. Não são moeda, não rendem, não são "
                   "resgatáveis em dinheiro nem transferíveis entre organizações. Valem pelo prazo do pacote. Operação que falha não "
                   "consome crédito. O preço de cada operação é mostrado antes da confirmação. Versão 1 (v0.28.0).")


def _sale_mode(conn, settings) -> dict:
    rule = conn.one("SELECT active, legal_status FROM monetization_rules WHERE key = 'ai.credits_prepaid'")
    pay = payments.status(settings)
    real = bool(rule and rule["active"]) and pay["is_real_provider"]
    return {"mode": "real" if real else "pilot",
            "rule_active": bool(rule and rule["active"]), "rule_legal_status": rule["legal_status"] if rule else None,
            "provider": pay["provider"], "provider_is_real": pay["is_real_provider"],
            "pix_key_configured": bool(settings.platform_pix_key),
            "why_pilot": None if real else ("a regra comercial ai.credits_prepaid não está ativa (carta legal amarela)" if not (rule and rule["active"])
                                            else "nenhum provedor de pagamento real configurado")}


# ------------------------------------------------------------------------------------------------ central
def center(ctx) -> dict:
    with ctx.tx() as c:
        granted = UC.grant_due_quotas(c, ctx)
        bal = UC.balances(c, ctx.org_id)
        ops = c.query("SELECT code, version, name_pt, description_pt, category, tier, allowed_kinds, min_role, funding_modes, credits_base,"
                      "       credits_per_unit, unit_label_pt, max_units, max_input_chars, free_quota_eligible, sponsor_eligible,"
                      "       completion_rule_pt, failure_policy, delivers_pt, status, provider_mode"
                      "  FROM ai_operations WHERE status IN ('active','hypothesis','planned') ORDER BY category, code")
        kind = ctx.principal.org_kind
        for o in ops:
            o["available_to_me"] = kind in o["allowed_kinds"] and o["status"] != "planned"
            o["price_is_hypothesis"] = o["status"] == "hypothesis"
        packs = c.query("SELECT code, version, name_pt, credits, price_cents, currency, validity_days, status, note FROM ai_credit_packs"
                        " WHERE status IN ('active','hypothesis') ORDER BY credits")
        execs = c.query("SELECT id::text AS id, operation_code, category, state, funding_source, estimated_credits, charged_credits,"
                        "       cost_status, estimated_cost_cents, actual_cost_cents, project_id::text AS project_id, result_type, result_id,"
                        "       created_at, finished_at FROM ai_executions WHERE org_id = $1 ORDER BY created_at DESC LIMIT 20", ctx.org_id)
        ledger = c.query("SELECT id, delta, reason, bucket, ref_type, note, expires_at, created_at FROM ai_credit_ledger"
                         " WHERE org_id = $1 ORDER BY id DESC LIMIT 20", ctx.org_id)
        orders = c.query("SELECT id::text AS id, credits, amount_cents, currency, mode, state, expires_at, created_at FROM ai_credit_orders"
                         " WHERE org_id = $1 ORDER BY created_at DESC LIMIT 10", ctx.org_id)
        sponsorships = c.query(
            "SELECT s.id::text AS id, s.name_pt, o.legal_name AS sponsor_name, s.budget_credits, ai_sponsorship_used(s.id) AS used,"
            "       s.ends_on, s.operations, s.per_org_limit, s.per_project_limit, s.status, (s.sponsor_org_id = $1) AS mine"
            "  FROM ai_sponsorships s JOIN organizations o ON o.id = s.sponsor_org_id"
            " WHERE s.status = 'active' AND s.ends_on >= current_date ORDER BY s.ends_on", ctx.org_id)
        quotas = c.query("SELECT key, label_pt, scope, credits, period, validity_days FROM ai_quota_policies WHERE active AND $1 = ANY(applies_to_kinds)", kind)
        month = c.one("SELECT count(*) AS executions, coalesce(sum(charged_credits),0) AS credits,"
                      "       count(*) FILTER (WHERE funding_source = 'sponsorship') AS sponsored,"
                      "       count(*) FILTER (WHERE state IN ('failed','partial')) AS failed_or_partial"
                      "  FROM ai_executions WHERE org_id = $1 AND created_at >= date_trunc('month', now())", ctx.org_id)
        sale = _sale_mode(c, ctx.settings)
        for e in execs:
            e["funding_label"] = UC.FUNDING_LABEL.get(e["funding_source"], e["funding_source"])
            for k in ("estimated_cost_cents", "actual_cost_cents"):
                if e.get(k) is not None:
                    e[k] = float(e[k])
    return {
        "balances": bal, "quotas_granted_now": granted, "quota_policies": quotas,
        "operations": ops, "packs": packs, "recent_executions": execs, "ledger": ledger, "orders": orders,
        "sponsorships": [s for s in sponsorships if not s["mine"]], "my_sponsorships": [s for s in sponsorships if s["mine"]],
        "this_month": month, "sale": sale,
        "rules": [
            "Você não paga para entrar no IMPACTO: cadastro, projeto, rascunhos e seus dados nunca dependem de crédito.",
            "Cada operação mostra o custo em créditos e quem paga ANTES de executar. Nada roda sem a sua confirmação.",
            "Operação que falha não consome crédito. Resultado já calculado para os mesmos dados não é cobrado de novo.",
            "Ordem de custeio: patrocínio elegível → cota gratuita → créditos comprados. Sem fonte, nada é executado e seu trabalho fica salvo.",
            "Crédito não é dinheiro: não rende, não se saca, não se transfere. Vale pelo prazo do pacote.",
            "Pagar mais não altera resultado, match, reputação, elegibilidade nem posição de projeto algum.",
        ],
        "terms": CREDIT_TERMS_V1,
    }


# ------------------------------------------------------------------------------------------------ pedidos de crédito
def create_order(ctx, *, pack_code: str, accept_terms: bool) -> dict:
    if not accept_terms:
        raise unprocessable("É preciso aceitar os termos de crédito para fazer o pedido", code="terms_required")
    ctx.require_role("admin")
    with ctx.tx() as c:
        pack = c.one("SELECT * FROM ai_credit_packs WHERE code = $1 AND status IN ('active','hypothesis') ORDER BY version DESC LIMIT 1", pack_code)
        if not pack:
            raise not_found("Pacote de créditos")
        sale = _sale_mode(c, ctx.settings)
        mode = sale["mode"]
        if c.one("SELECT 1 FROM ai_credit_orders WHERE org_id = $1 AND state IN ('created','awaiting_payment','paid')", ctx.org_id):
            raise ApiError(409, "order_open", "Já existe um pedido de crédito em aberto nesta organização. Conclua ou cancele antes de abrir outro.")
        row = c.one("INSERT INTO ai_credit_orders(org_id, user_id, pack_id, credits, amount_cents, currency, mode, consent_text_sha256)"
                    " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *",
                    ctx.org_id, ctx.user_id, pack["id"], pack["credits"], pack["price_cents"], pack["currency"], mode,
                    hashlib.sha256(CREDIT_TERMS_V1.encode()).hexdigest())
        charge = None
        if mode == "real":
            ch = payments.create(c, org_id=ctx.org_id, actor=ctx.user_id, kind="ai_credits", method="pix",
                                 amount_cents=pack["price_cents"], currency=pack["currency"], provider=sale["provider"],
                                 expires_at=row["expires_at"])
            c.run("UPDATE platform_charges SET idempotency_key = $2 WHERE id = $1", ch["id"], f"ai_credit_order:{row['id']}")
            payments.transition(c, charge_id=ch["id"], to_state="checkout_started", org_id=ctx.org_id)
            payments.transition(c, charge_id=ch["id"], to_state="pending", org_id=ctx.org_id)
            c.run("UPDATE ai_credit_orders SET state = 'awaiting_payment', charge_id = $2 WHERE id = $1", row["id"], ch["id"])
            charge = payments.get(c, charge_id=ch["id"], org_id=ctx.org_id)
        ctx.audit(c, "ai.credit_order_created", "ai_credit_order", row["id"], {"pack": pack_code, "credits": pack["credits"], "amount_cents": pack["price_cents"], "mode": mode})
        out = order_detail(c, ctx, str(row["id"]))
    out["charge"] = charge
    return out


def order_detail(c, ctx, order_id: str) -> dict:
    row = c.one("SELECT o.*, o.id::text AS id, o.charge_id::text AS charge_id, p.code AS pack_code, p.name_pt AS pack_name FROM ai_credit_orders o"
                " JOIN ai_credit_packs p ON p.id = o.pack_id WHERE o.id = $1 AND o.org_id = $2", order_id, ctx.org_id)
    if not row:
        raise not_found("Pedido de crédito")
    out = {k: v for k, v in row.items() if k not in ("org_id", "user_id", "pack_id", "confirmed_by", "consent_text_sha256")}
    out["pix"] = {"key": ctx.settings.platform_pix_key or None, "key_type": ctx.settings.platform_pix_key_type or None,
                  "status": "NÃO CONFIGURADA" if not ctx.settings.platform_pix_key else "configurada",
                  "note": ("Instrução de PIX real depende de provedor homologado; a chave da plataforma vem de PLATFORM_PIX_KEY."
                           if row["mode"] == "real" else "Pedido em modo PILOTO: nenhum pagamento; a administração pode aprová-lo como concessão de teste.")}
    out["message"] = {
        "created": "Pedido registrado em modo piloto: nenhum pagamento é devido. Aguarde a decisão da administração." if row["mode"] == "pilot" else "Pedido criado.",
        "awaiting_payment": "Estamos aguardando a confirmação do pagamento. Seus créditos serão liberados após a confirmação.",
        "paid": "Pagamento confirmado; os créditos estão sendo registrados.",
        "credited": "Créditos liberados.", "expired": "O pedido expirou sem pagamento. Nada foi cobrado.",
        "cancelled": "Pedido cancelado. Nada foi cobrado.", "failed": "O pagamento falhou. Nada foi creditado.",
    }[row["state"]]
    return out


def cancel_order(ctx, order_id: str) -> dict:
    ctx.require_role("admin")
    with ctx.tx() as c:
        row = c.one("SELECT * FROM ai_credit_orders WHERE id = $1 AND org_id = $2", order_id, ctx.org_id)
        if not row:
            raise not_found("Pedido de crédito")
        if row["state"] not in ("created", "awaiting_payment"):
            raise unprocessable("Só é possível cancelar pedidos ainda não pagos", {"state": row["state"]}, code="order_not_cancellable")
        c.run("UPDATE ai_credit_orders SET state = 'cancelled' WHERE id = $1", row["id"])
        if row["charge_id"]:
            payments.transition(c, charge_id=str(row["charge_id"]), to_state="cancelled", org_id=ctx.org_id)
        ctx.audit(c, "ai.credit_order_cancelled", "ai_credit_order", row["id"], {})
        return order_detail(c, ctx, order_id)


def _credit_order(c, order: dict, *, bucket: str, reason: str, via: str, reference: str | None, actor: str | None, note: str) -> int:
    """Lança o crédito UMA vez (idempotente pelo pedido) e fecha o pedido como credited."""
    validade = c.scalar("SELECT validity_days FROM ai_credit_packs WHERE id = $1", order["pack_id"])
    ledger_id = c.scalar(
        "SELECT ai_credit_post($1, $2, $3, $4, 'ai_credit_order', $5, $6, $7, NULL, now() + make_interval(days => $8::int))",
        order["org_id"], order["credits"], reason, bucket, str(order["id"]), f"order:{order['id']}", note, int(validade))
    if ledger_id is None:
        ledger_id = c.scalar("SELECT id FROM ai_credit_ledger WHERE org_id = $1 AND idempotency_key = $2", order["org_id"], f"order:{order['id']}")
    c.run("UPDATE ai_credit_orders SET state = 'credited', ledger_id = $2, confirmed_via = $3, paid_reference = coalesce($4, paid_reference),"
          " confirmed_by = $5 WHERE id = $1", order["id"], ledger_id, via, reference, actor)
    return int(ledger_id)


def admin_confirm_order(ctx, order_id: str, *, reference: str, note: str) -> dict:
    """Conciliação MANUAL de um pedido REAL (administração com billing.write): a referência do extrato é
    obrigatória e fica no pedido. Pedido piloto não passa por aqui."""
    with ctx.tx() as c:
        row = c.one("SELECT * FROM ai_credit_orders WHERE id = $1", order_id)
        if not row:
            raise not_found("Pedido de crédito")
        if row["mode"] != "real":
            raise unprocessable("Pedido em modo piloto não é confirmado como pagamento; use a aprovação de piloto", code="order_is_pilot")
        if row["state"] not in ("awaiting_payment", "paid"):
            raise unprocessable("O pedido não está aguardando pagamento", {"state": row["state"]}, code="order_state")
        if row["charge_id"]:
            ch = c.one("SELECT state, is_simulated FROM platform_charges WHERE id = $1", row["charge_id"])
            if ch and ch["is_simulated"]:
                raise ApiError(409, "simulated_charge", "A cobrança deste pedido é SIMULADA (provedor não real): não credita compra.")
            if ch and ch["state"] == "pending":
                payments.transition(c, charge_id=str(row["charge_id"]), to_state="paid", admin=True)
        if row["state"] == "awaiting_payment":
            c.run("UPDATE ai_credit_orders SET state = 'paid', paid_reference = $2 WHERE id = $1", row["id"], reference)
        row = c.one("SELECT * FROM ai_credit_orders WHERE id = $1", order_id)
        _credit_order(c, row, bucket="purchased", reason="purchase", via="manual_reconciliation", reference=reference, actor=ctx.user_id,
                      note=f"Compra conciliada manualmente: {note}"[:300])
        ctx.audit(c, "ai.credit_order_confirmed", "ai_credit_order", row["id"], {"via": "manual_reconciliation", "reference": reference[:60]}, org_id=str(row["org_id"]))
        return _admin_order(c, order_id)


def admin_approve_pilot(ctx, order_id: str, *, note: str) -> dict:
    """Pedido PILOTO aprovado vira concessão PROMOCIONAL — nunca compra, nunca receita."""
    with ctx.tx() as c:
        row = c.one("SELECT * FROM ai_credit_orders WHERE id = $1", order_id)
        if not row:
            raise not_found("Pedido de crédito")
        if row["mode"] != "pilot" or row["state"] != "created":
            raise unprocessable("Só pedidos piloto ainda abertos podem ser aprovados como concessão", {"mode": row["mode"], "state": row["state"]}, code="order_state")
        _credit_order(c, row, bucket="promotional", reason="grant", via="pilot_grant", reference=None, actor=ctx.user_id,
                      note=f"Concessão de piloto (sem pagamento): {note}"[:300])
        ctx.audit(c, "ai.credit_order_pilot_granted", "ai_credit_order", row["id"], {"credits": row["credits"]}, org_id=str(row["org_id"]))
        return _admin_order(c, order_id)


def _admin_order(c, order_id: str) -> dict:
    row = c.one("SELECT o.*, o.id::text AS id, o.org_id::text AS org_id, o.charge_id::text AS charge_id, g.legal_name AS org_name, p.code AS pack_code"
                "  FROM ai_credit_orders o JOIN organizations g ON g.id = o.org_id JOIN ai_credit_packs p ON p.id = o.pack_id WHERE o.id = $1", order_id)
    return {k: v for k, v in row.items() if k not in ("consent_text_sha256",)}


def apply_payment_webhook(c, *, provider: str, event_id: str, event_type: str, charge_id: str | None, amount_cents: int | None,
                          payload: dict, signature_verified: bool) -> dict:
    """Evento do provedor → cobrança → pedido → crédito. Reentrega não duplica (billing_events + idempotência do razão)."""
    rec = payments.record_webhook(c, provider=provider, event_id=event_id, event_type=event_type, payload=payload,
                                  signature_verified=signature_verified, charge_id=charge_id)
    if rec["duplicate"] or not rec["applied"]:
        return rec | {"credited": False}
    if event_type not in ("charge.paid", "pix.paid"):
        return rec | {"credited": False, "note": "evento registrado; só charge.paid/pix.paid creditam"}
    ch = c.one("SELECT id::text AS id, org_id, state, amount_cents, is_simulated, idempotency_key FROM platform_charges WHERE id = $1", charge_id) if charge_id else None
    if not ch:
        return rec | {"credited": False, "note": "cobrança não encontrada"}
    if ch["is_simulated"]:
        return rec | {"credited": False, "note": "cobrança simulada: não credita compra"}
    if amount_cents is not None and int(amount_cents) != int(ch["amount_cents"]):
        return rec | {"credited": False, "note": "valor do evento difere do valor da cobrança; exige conciliação manual"}
    if ch["state"] in ("pending", "authorized"):
        payments.transition(c, charge_id=ch["id"], to_state="paid", provider_charge_id=str(payload.get("provider_charge_id") or "")[:120] or None)
    order = c.one("SELECT * FROM ai_credit_orders WHERE charge_id = $1", ch["id"])
    if not order:
        return rec | {"credited": False, "note": "cobrança paga sem pedido de crédito associado"}
    if order["state"] == "credited":
        return rec | {"credited": False, "note": "pedido já creditado"}
    if order["state"] == "awaiting_payment":
        c.run("UPDATE ai_credit_orders SET state = 'paid', paid_reference = $2 WHERE id = $1", order["id"], f"{provider}:{event_id}"[:120])
        order = c.one("SELECT * FROM ai_credit_orders WHERE id = $1", order["id"])
    _credit_order(c, order, bucket="purchased", reason="purchase", via="webhook", reference=f"{provider}:{event_id}"[:120], actor=None,
                  note=f"Compra confirmada por webhook {provider}")
    return rec | {"credited": True, "order_id": str(order["id"]), "credits": order["credits"]}


# ------------------------------------------------------------------------------------------------ patrocínio
def create_sponsorship(ctx, body: Any) -> dict:
    if ctx.principal.org_kind not in ("company", "government", "osc"):
        raise forbidden("Só empresas, governos e organizações podem patrocinar uso de IA", code="sponsor_kind")
    ctx.require_role("admin")
    with ctx.tx() as c:
        c.run("SELECT pg_advisory_xact_lock(hashtext('ai_credit:' || $1))", ctx.org_id)
        avail = {b: int(c.scalar("SELECT ai_credit_available($1,$2)", ctx.org_id, b)) for b in ("purchased", "promotional")}
        if avail["purchased"] + avail["promotional"] < body.budget_credits:
            raise ApiError(402, "sponsor_insufficient_credits",
                           "O patrocínio compromete créditos do próprio patrocinador; o saldo disponível não cobre o orçamento.",
                           {"available": avail, "budget_credits": body.budget_credits})
        row = c.one("INSERT INTO ai_sponsorships(sponsor_org_id, name_pt, budget_credits, starts_on, ends_on, eligible_kinds, eligible_org_ids,"
                    " eligible_uf, operations, per_org_limit, per_project_limit, accountability_pt, created_by)"
                    " VALUES ($1,$2,$3,coalesce($4, current_date),$5,$6,$7::uuid[],$8,$9,$10,$11,$12,$13) RETURNING id::text AS id",
                    ctx.org_id, body.name, body.budget_credits, body.starts_on, body.ends_on, body.eligible_kinds, body.eligible_org_ids or [],
                    (body.eligible_uf or None), body.operations or ["*"], body.per_org_limit, body.per_project_limit, body.accountability, ctx.user_id)
        # compromete do comprado primeiro (obrigação paga), depois do promocional
        restante = body.budget_credits
        for bucket in ("purchased", "promotional"):
            take = min(restante, avail[bucket])
            if take > 0:
                c.scalar("SELECT ai_credit_post($1, $2, 'sponsor_commit', $3, 'ai_sponsorship', $4, $5, $6, NULL, NULL)",
                         ctx.org_id, -take, bucket, row["id"], f"sponsor:{row['id']}:{bucket}", f"Patrocínio: {body.name}")
                restante -= take
        ctx.audit(c, "ai.sponsorship_created", "ai_sponsorship", row["id"], {"budget_credits": body.budget_credits, "ends_on": str(body.ends_on)})
        return sponsorship_report(c, ctx, row["id"])


def sponsorship_report(c, ctx, sponsorship_id: str) -> dict:
    s = c.one("SELECT s.*, s.id::text AS id, s.sponsor_org_id::text AS sponsor_org_id, ai_sponsorship_used(s.id) AS used FROM ai_sponsorships s"
              " WHERE s.id = $1 AND s.sponsor_org_id = $2", sponsorship_id, ctx.org_id)
    if not s:
        raise not_found("Patrocínio")
    # prestação de contas AGREGADA: contagens e créditos por operação e por organização beneficiada — nunca o conteúdo
    rep = c.query("SELECT * FROM ai_sponsorship_report($1) ORDER BY credits DESC", sponsorship_id)
    by_op = [{"operation_code": r["label"], "executions": r["executions"], "credits": r["credits"], "not_charged": r["not_charged"]} for r in rep if r["group_kind"] == "operation"]
    by_org = [{"org_name": r["label"], "executions": r["executions"], "credits": r["credits"]} for r in rep if r["group_kind"] == "organization"]
    out = {k: v for k, v in s.items() if k != "created_by"}
    out["eligible_org_ids"] = [str(x) for x in (s["eligible_org_ids"] or [])]
    out["remaining"] = int(s["budget_credits"]) - int(s["used"])
    out["by_operation"], out["by_organization"] = by_op, by_org
    out["note"] = "Prestação de contas agregada: o patrocinador vê operações e créditos, nunca o conteúdo dos projetos beneficiados."
    return out


def close_sponsorship(ctx, sponsorship_id: str) -> dict:
    ctx.require_role("admin")
    with ctx.tx() as c:
        s = c.one("SELECT * FROM ai_sponsorships WHERE id = $1 AND sponsor_org_id = $2", sponsorship_id, ctx.org_id)
        if not s:
            raise not_found("Patrocínio")
        if s["status"] == "closed":
            raise unprocessable("Patrocínio já encerrado", code="sponsorship_closed")
        if c.one("SELECT 1 FROM ai_executions WHERE sponsorship_id = $1 AND state IN ('reserved','running')", sponsorship_id):
            raise ApiError(409, "sponsorship_busy", "Há execuções patrocinadas em andamento; encerre depois que terminarem.")
        used = int(c.scalar("SELECT ai_sponsorship_used($1)", sponsorship_id))
        unused = int(s["budget_credits"]) - used
        c.run("UPDATE ai_sponsorships SET status = 'closed', closed_at = now() WHERE id = $1", sponsorship_id)
        if unused > 0:
            # devolve o não usado, lote a lote, na proporção comprometida
            for bucket in ("purchased", "promotional"):
                comp = c.scalar("SELECT coalesce(-sum(delta),0) FROM ai_credit_ledger WHERE org_id = $1 AND reason = 'sponsor_commit' AND ref_id = $2 AND bucket = $3",
                                ctx.org_id, sponsorship_id, bucket)
                if comp and unused > 0:
                    back = min(int(comp), unused)
                    c.scalar("SELECT ai_credit_post($1, $2, 'release', $3, 'ai_sponsorship', $4, $5, $6, NULL, NULL)",
                             ctx.org_id, back, bucket, sponsorship_id, f"sponsor_release:{sponsorship_id}:{bucket}", "Patrocínio encerrado: crédito não usado devolvido")
                    unused -= back
        ctx.audit(c, "ai.sponsorship_closed", "ai_sponsorship", sponsorship_id, {"used": used})
        return sponsorship_report(c, ctx, sponsorship_id)


# ------------------------------------------------------------------------------------------------ painel financeiro da administração
def admin_finance(ctx) -> dict:
    """Métricas MEDIDAS desta instalação. Onde não há dado, diz NÃO MEDIDO — nunca estima no painel."""
    with ctx.tx(readonly=True) as c:
        ops = c.query("SELECT operation_code, category, count(*) AS executions,"
                      "       count(*) FILTER (WHERE state IN ('succeeded','reconciled')) AS succeeded,"
                      "       count(*) FILTER (WHERE state = 'failed') AS failed, count(*) FILTER (WHERE state = 'partial') AS partial,"
                      "       count(*) FILTER (WHERE state = 'cancelled') AS cancelled,"
                      "       coalesce(sum(charged_credits),0) AS credits_charged,"
                      "       count(*) FILTER (WHERE funding_source = 'promotional') AS free_quota_uses,"
                      "       count(*) FILTER (WHERE funding_source = 'sponsorship') AS sponsored_uses,"
                      "       count(*) FILTER (WHERE funding_source = 'purchased') AS purchased_uses,"
                      "       count(*) FILTER (WHERE funding_source = 'cached') AS cached_uses,"
                      "       sum(actual_cost_cents) FILTER (WHERE cost_status = 'measured') AS cost_measured_cents,"
                      "       sum(estimated_cost_cents) FILTER (WHERE cost_status = 'estimated') AS cost_estimated_cents,"
                      "       count(*) FILTER (WHERE cost_status = 'no_price_table') AS unpriced,"
                      "       percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms) AS latency_p50_ms,"
                      "       percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms) AS latency_p95_ms"
                      "  FROM ai_executions GROUP BY 1,2 ORDER BY 2,1")
        credits = c.one("SELECT coalesce(sum(delta) FILTER (WHERE reason = 'purchase'),0) AS sold,"
                        "       coalesce(sum(delta) FILTER (WHERE reason IN ('grant','plan_cycle')),0) AS granted,"
                        "       coalesce(-sum(delta) FILTER (WHERE reason = 'consumption' AND bucket = 'purchased'),0) AS consumed_purchased,"
                        "       coalesce(-sum(delta) FILTER (WHERE reason = 'consumption' AND bucket = 'promotional'),0) AS consumed_promotional,"
                        "       coalesce(-sum(delta) FILTER (WHERE reason = 'sponsor_commit'),0) AS committed_to_sponsorships,"
                        "       coalesce(sum(delta) FILTER (WHERE bucket = 'purchased'),0) AS outstanding_purchased,"
                        "       coalesce(sum(delta) FILTER (WHERE bucket = 'promotional'),0) AS outstanding_promotional"
                        "  FROM ai_credit_ledger")
        orders = c.query("SELECT mode, state, count(*) AS n, coalesce(sum(amount_cents),0) AS amount_cents, coalesce(sum(credits),0) AS credits"
                         "  FROM ai_credit_orders GROUP BY 1,2 ORDER BY 1,2")
        revenue = c.one("SELECT coalesce(sum(o.amount_cents),0) AS received_cents FROM ai_credit_orders o WHERE o.mode = 'real' AND o.state = 'credited'")
        sponsors = c.query("SELECT s.id::text AS id, s.name_pt, o.legal_name AS sponsor, s.budget_credits, ai_sponsorship_used(s.id) AS used, s.status, s.ends_on"
                           "  FROM ai_sponsorships s JOIN organizations o ON o.id = s.sponsor_org_id ORDER BY s.created_at DESC LIMIT 50")
        price = c.one("SELECT count(*) AS rows FROM ai_price_table WHERE effective_from <= current_date AND (effective_until IS NULL OR effective_until >= current_date)")
        packs = c.query("SELECT code, credits, price_cents, status FROM ai_credit_packs WHERE status IN ('active','hypothesis') ORDER BY credits")
        quotas = c.query("SELECT p.key, p.label_pt, p.credits, p.period, count(g.id) AS grants, coalesce(sum(p.credits) FILTER (WHERE g.id IS NOT NULL),0) AS credits_granted"
                         "  FROM ai_quota_policies p LEFT JOIN ai_quota_grants g ON g.policy_id = p.id GROUP BY p.id ORDER BY p.id")
        sale = _sale_mode(c, ctx.settings)
        disputes = c.one("SELECT count(*) FILTER (WHERE status = 'open') AS open, count(*) AS total FROM similarity_disputes")
    sold_price_cents = None
    recognized_cents = None
    if credits["sold"]:
        # preço médio do crédito vendido = recebido ÷ créditos vendidos (medido, não hipótese)
        sold_price_cents = round(float(revenue["received_cents"]) / float(credits["sold"]), 4)
        recognized_cents = round(sold_price_cents * float(credits["consumed_purchased"]), 2)
    cost_measured = sum(float(o["cost_measured_cents"] or 0) for o in ops)
    alerts = []
    if price["rows"] == 0 and any(o["unpriced"] for o in ops):
        alerts.append("Há execuções externas sem preço vigente na tabela do provedor: custo NÃO MEDIDO. Cadastre o preço em Administração → IA.")
    if credits["outstanding_purchased"] > 0:
        alerts.append(f"{credits['outstanding_purchased']} crédito(s) comprado(s) ainda não consumido(s): obrigação com clientes, não receita.")
    if disputes["open"]:
        alerts.append(f"{disputes['open']} contestação(ões) de similaridade aguardando revisão humana.")
    for o in ops:
        if o["executions"] >= 5 and (o["failed"] + o["partial"]) / o["executions"] > 0.2:
            alerts.append(f"{o['operation_code']}: mais de 20% de falhas/parciais ({o['failed'] + o['partial']}/{o['executions']}).")
    return {
        "by_operation": [{k: (float(v) if k.startswith(("cost_", "latency_")) and v is not None else v) for k, v in o.items()} for o in ops],
        "credits": credits, "orders": orders, "sponsorships": sponsors, "packs": packs, "quota_policies": quotas, "sale": sale,
        "revenue": {"received_cents": int(revenue["received_cents"]), "recognized_cents": recognized_cents,
                    "sold_credit_price_cents": sold_price_cents,
                    "note": "Recebido = pedidos reais creditados. Reconhecido = créditos comprados consumidos × preço médio. Créditos não consumidos são passivo."},
        "costs": {"external_measured_cents": round(cost_measured, 4) if cost_measured else 0.0,
                  "infra_cents": None, "payment_fees_cents": None, "taxes_cents": None,
                  "note": "Custo externo medido vem dos tokens informados pelo provedor × tabela de preço. Infraestrutura, tarifa de pagamento e impostos: NÃO MEDIDOS nesta instalação."},
        "contribution_margin": {"cents": (round(recognized_cents - cost_measured, 2) if recognized_cents is not None else None),
                                "status": "NÃO MEDIDO" if recognized_cents is None else "parcial (sem infra, tarifa e imposto)"},
        "alerts": alerts,
        "disputes": disputes,
        "honesty": ["Nenhum número aqui é estimado: onde não há medição, o campo é nulo e o status diz NÃO MEDIDO.",
                    "Preços de operação e de pacote marcados 'hypothesis' são hipóteses de teste do proprietário (AI_COST_MODEL.md)."],
    }
