"""Doações, campanhas de arrecadação, QR, webhook do provedor, conciliação e prestação de contas — v0.33.0.

Toda confirmação de pagamento entra por UM lugar: `POST /v1/webhooks/donations/{provider}` (evento assinado,
deduplicado). Nenhuma rota aceita "pago" vindo do navegador. Só existe o provedor sandbox (simulado).
"""
from __future__ import annotations

import json

from starlette.responses import JSONResponse, Response

from ..http import ApiError, Ctx, not_found, route
from ..services import donations as DON
from . import trust_schemas as TSch

T = ("donations",)
WRITE = "manager"


# ============================================================================ público
@route("GET", "/v1/public/donation-campaigns/{slug}", auth="none", rate=("dcamp_ip", 240, 3600), tags=("public",),
       summary="Campanha de arrecadação pública: beneficiário verificado, meta, totais confirmados, custos, atualizações e gastos declarados")
def public_campaign(ctx: Ctx):
    with ctx.system_tx() as c:
        out = DON.public_campaign(c, ctx.path["slug"])
    out["canonical_url"] = DON.canonical_url(ctx.settings, ctx.path["slug"], out["campaign"]["qr_version"])
    return out


@route("GET", "/v1/public/donation-campaigns/{slug}/qr.svg", auth="none", raw=True, rate=("dqr_ip", 120, 3600), tags=("public",),
       summary="QR Code da campanha: aponta para a URL HTTPS canônica (nunca para um payload Pix estático)")
def campaign_qr(ctx: Ctx):
    with ctx.system_tx() as c:
        camp = c.one("SELECT qr_version FROM campaigns WHERE slug = $1 AND status IN ('published','target_reached')", ctx.path["slug"])
    if not camp:
        raise not_found("Campanha")
    from ..trust.qr import svg as svg_for
    url = DON.canonical_url(ctx.settings, ctx.path["slug"], camp["qr_version"])
    return Response(svg_for(url), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=300", "X-Impacto-Qr-Target": url})


@route("POST", "/v1/public/donation-campaigns/{slug}/donate", auth="none", body=TSch.DonationStartIn, status=201,
       rate=("donate_ip", 30, 3600), tags=("public",),
       summary="Inicia uma doação: cria a cobrança no provedor e devolve o Pix copia-e-cola/checkout com o preço total — não confirma nada")
def donate(ctx: Ctx, body: TSch.DonationStartIn):
    donor_user_id = ctx.principal.user_id if ctx.principal else None
    with ctx.system_tx() as c:
        out = DON.start_donation(c, settings=ctx.settings, campaign_slug=ctx.path["slug"], amount_cents=body.amount_cents,
                                 method=body.method, donor_user_id=donor_user_id, donor_display=body.donor_display,
                                 donor_email=body.donor_email, public_anonymous=body.public_anonymous, cover_costs=body.cover_costs,
                                 idempotency_key=body.idempotency_key, cipher=ctx.app.cipher)
        ctx.audit(c, "donation.started", "donation", out["id"], {"amount_cents": body.amount_cents, "method": body.method,
                                                                  "provider": out["provider"], "simulated": out["is_simulated"]}, org_id=None)
    return out


@route("GET", "/v1/public/donations/{donation_id}", auth="none", rate=("dstat_ip", 600, 3600), tags=("public",),
       summary="Estado da doação (pendente/confirmada/expirada), como o provedor informou; nunca muda pelo navegador")
def donation_status(ctx: Ctx):
    with ctx.system_tx() as c:
        d = DON.get_donation(c, ctx.path["donation_id"], settings=ctx.settings)
    # Público: sem contato, sem nome se anônimo.
    if d["public_anonymous"]:
        d["donor_display"] = None
    return d


@route("GET", "/v1/public/donations/{donation_id}/receipt", auth="none", rate=("drec_ip", 120, 3600), tags=("public",),
       summary="Comprovante da doação confirmada (não é recibo dedutível nem nota fiscal)")
def donation_receipt(ctx: Ctx):
    with ctx.system_tx() as c:
        return DON.receipt_view(c, ctx.path["donation_id"])


# ============================================================================ webhook do provedor
@route("POST", "/v1/webhooks/donations/{provider}", auth="none", raw=True, raw_body=True, rate=("don_webhook_ip", 600, 60), tags=("donations",),
       summary="Webhook do provedor: assinatura conferida, evento gravado uma vez, estado e razão atualizados numa transação")
def donation_webhook(ctx: Ctx, payload: bytes):
    provider = ctx.path["provider"][:40]
    if not ctx.settings.payment_webhook_secret:
        return JSONResponse({"status": "rejected", "code": "webhook_not_configured",
                             "note": "PAYMENT_WEBHOOK_SECRET ausente: nenhum evento é aceito"}, status_code=404)
    try:
        prov = DON.provider_for(ctx.settings, provider)
    except ApiError:
        return JSONResponse({"status": "rejected", "code": "provider_unavailable"}, status_code=404)
    verified = prov.verify_signature(dict(ctx.request.headers), payload)
    try:
        event = prov.parse_event(payload)
    except (ValueError, json.JSONDecodeError):
        return JSONResponse({"status": "rejected", "code": "bad_json"}, status_code=400)
    if not event["event_id"]:
        return JSONResponse({"status": "rejected", "code": "missing_event_id"}, status_code=400)
    with ctx.system_tx() as c:
        out = DON.apply_provider_event(c, provider=provider, event=event, signature_verified=verified, raw=payload)
    status = "duplicate" if out.get("duplicate") else ("rejected_signature" if not verified else out.get("effect", "recorded"))
    return JSONResponse({"status": status, "effect": out.get("effect"), "donation_id": out.get("donation_id")},
                        status_code=200 if verified else 202)


# ============================================================================ organização beneficiária
@route("POST", "/v1/campaigns/{campaign_id}/submit", min_role=WRITE, tags=T,
       summary="Envia a campanha para revisão (aceita os termos de campanha na versão vigente)")
def campaign_submit(ctx: Ctx):
    with ctx.tx() as c:
        out = DON.submit_for_review(c, campaign_id=ctx.path["campaign_id"], org_id=ctx.org_id, actor=ctx.user_id)
        ctx.audit(c, "campaign.submitted", "campaign", ctx.path["campaign_id"], out)
    return out


@route("POST", "/v1/campaigns/{campaign_id}/publish", min_role=WRITE, tags=T,
       summary="Publica a campanha aprovada (exige beneficiário verificado; o banco recusa sem isso)")
def campaign_publish(ctx: Ctx):
    with ctx.tx() as c:
        out = DON.publish(c, settings=ctx.settings, campaign_id=ctx.path["campaign_id"], org_id=ctx.org_id)
        ctx.audit(c, "campaign.published", "campaign", ctx.path["campaign_id"], out)
    return out


@route("POST", "/v1/campaigns/{campaign_id}/rotate-qr", min_role=WRITE, tags=T,
       summary="Regenera QR/link (versão nova; a anterior deixa de ser a canônica) — para QR comprometido ou substituído")
def campaign_rotate_qr(ctx: Ctx):
    with ctx.tx() as c:
        out = DON.rotate_qr(c, settings=ctx.settings, campaign_id=ctx.path["campaign_id"], org_id=ctx.org_id)
        ctx.audit(c, "campaign.qr_rotated", "campaign", ctx.path["campaign_id"], out)
    return out


@route("GET", "/v1/campaigns/{campaign_id}/accountability", min_role="viewer", tags=T,
       summary="Prestação de contas: totais conciliados (com definição de cada número), doações, gastos declarados × validados, casos de risco")
def campaign_accountability(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return DON.accountability(c, campaign_id=ctx.path["campaign_id"], org_id=ctx.org_id)


@route("POST", "/v1/campaigns/{campaign_id}/expenses", body=TSch.CampaignExpenseIn, min_role=WRITE, status=201, tags=T,
       summary="Declara um gasto da campanha (declarado ≠ validado; documento vira evidência)")
def campaign_expense(ctx: Ctx, body: TSch.CampaignExpenseIn):
    with ctx.tx() as c:
        DON.require_campaign_owner(c, ctx.path["campaign_id"], ctx.org_id)
        eid = c.scalar("INSERT INTO campaign_expenses(campaign_id, description, budget_line, amount_cents, spent_on, document_id, evidence_status, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id::text", ctx.path["campaign_id"], body.description, body.budget_line,
                       body.amount_cents, body.spent_on, body.document_id, "documented" if body.document_id else "declared", ctx.user_id)
        ctx.audit(c, "campaign.expense_declared", "campaign_expense", eid, {"amount_cents": body.amount_cents})
    return {"id": eid, "evidence_status": "documented" if body.document_id else "declared"}


@route("POST", "/v1/campaigns/{campaign_id}/updates", body=TSch.CampaignUpdateIn, min_role=WRITE, status=201, tags=T,
       summary="Atualização pública da campanha, com referências a evidências")
def campaign_update(ctx: Ctx, body: TSch.CampaignUpdateIn):
    with ctx.tx() as c:
        DON.require_campaign_owner(c, ctx.path["campaign_id"], ctx.org_id)
        uid = c.scalar("INSERT INTO campaign_updates(campaign_id, title, body, evidence_ids, is_public, created_by) VALUES ($1,$2,$3,$4,$5,$6) RETURNING id::text",
                       ctx.path["campaign_id"], body.title, body.body, [str(e) for e in body.evidence_ids], body.is_public, ctx.user_id)
    return {"id": uid}


@route("GET", "/v1/me/donations", auth="user", tags=T, summary="Minhas doações (com conta) e acordos recorrentes")
def my_donations(ctx: Ctx):
    with ctx.system_tx() as c:
        rows = c.query("SELECT d.id::text AS id, d.status, d.amount_cents, d.method, d.is_simulated, d.confirmed_at, d.created_at, c.slug, c.title"
                       " FROM donations d JOIN campaigns c ON c.id = d.campaign_id WHERE d.donor_user_id = $1 ORDER BY d.created_at DESC LIMIT 100", ctx.user_id)
        rec = c.query("SELECT r.id::text AS id, r.amount_cents, r.cadence, r.status, r.next_charge_on, c.slug, c.title FROM recurring_donation_agreements r"
                      " JOIN campaigns c ON c.id = r.campaign_id WHERE r.donor_user_id = $1 ORDER BY r.created_at DESC", ctx.user_id)
    return {"donations": rows, "recurring": rec,
            "recurring_note": "Doação recorrente exige instrumento suportado pelo provedor e consentimento explícito; nesta versão nenhum provedor real está ligado."}


@route("POST", "/v1/me/recurring-donations/{agreement_id}/cancel", auth="user", tags=T, summary="Cancela um acordo de doação recorrente (sempre possível pelo doador)")
def cancel_recurring(ctx: Ctx):
    with ctx.system_tx() as c:
        if not c.run("UPDATE recurring_donation_agreements SET status = 'cancelled', cancelled_at = now() WHERE id = $1 AND donor_user_id = $2 AND status <> 'cancelled'",
                     ctx.path["agreement_id"], ctx.user_id):
            raise not_found("Acordo recorrente")
        ctx.audit(c, "donation.recurring_cancelled", "recurring_donation_agreement", ctx.path["agreement_id"], {}, org_id=None)
    return {"status": "cancelled"}


# ============================================================================ revisão interna (quatro olhos) e risco
@route("GET", "/v1/admin/donation-campaigns", auth="admin", permission="compliance.write", tags=T,
       summary="Campanhas aguardando revisão e campanhas publicadas")
def admin_campaigns(ctx: Ctx):
    with ctx.system_tx() as c:
        wanted = ctx.request.query_params.get("status") or ""
        allowed = ("pending_review", "approved", "published", "under_review", "paused", "rejected")
        statuses = [wanted] if wanted in allowed else list(allowed[:-1])
        rows = c.query("SELECT c.id::text AS id, c.slug, c.title, c.kind, c.status, c.target_cents, c.created_at, c.purpose, c.accepted_terms_at,"
                       " c.created_by::text AS created_by, c.beneficiary_org_id::text AS beneficiary_org_id, o.legal_name AS org,"
                       " beneficiary_verified(c.beneficiary_org_id) AS beneficiary_verified"
                       " FROM campaigns c JOIN organizations o ON o.id = c.beneficiary_org_id"
                       " WHERE c.status = ANY($1) ORDER BY c.status, c.created_at", statuses)
    return {"items": rows}


@route("POST", "/v1/admin/donation-campaigns/{campaign_id}/review", auth="admin", permission="compliance.write", body=TSch.CampaignReviewIn, tags=T,
       summary="Aprova ou rejeita a campanha com justificativa (quem criou não revisa)")
def admin_review(ctx: Ctx, body: TSch.CampaignReviewIn):
    with ctx.system_tx() as c:
        out = DON.review(c, campaign_id=ctx.path["campaign_id"], reviewer=ctx.user_id, approve=body.approve, note=body.note)
        ctx.audit(c, "campaign.reviewed", "campaign", ctx.path["campaign_id"], {"approve": body.approve}, org_id=None)
    return out


@route("POST", "/v1/admin/donation-campaigns/{campaign_id}/suspend", auth="admin", permission="compliance.write", body=TSch.CampaignSuspendIn, tags=T,
       summary="Tira do ar (em análise) ou devolve ao ar uma campanha publicada, com justificativa")
def admin_suspend(ctx: Ctx, body: TSch.CampaignSuspendIn):
    with ctx.system_tx() as c:
        out = DON.suspend(c, campaign_id=ctx.path["campaign_id"], reviewer=ctx.user_id, note=body.note, reinstate=body.reinstate)
        ctx.audit(c, "campaign.suspended" if not body.reinstate else "campaign.reinstated", "campaign", ctx.path["campaign_id"], {"note": body.note}, org_id=None)
    return out


@route("POST", "/v1/admin/beneficiaries/{org_id}/verification", auth="admin", permission="compliance.write", body=TSch.BeneficiaryVerificationIn, tags=T,
       summary="Registra o estado da verificação do beneficiário (KYB): quem verifica e com que documentos depende do provedor e do parecer")
def admin_beneficiary_verification(ctx: Ctx, body: TSch.BeneficiaryVerificationIn):
    with ctx.system_tx() as c:
        if not c.scalar("SELECT 1 FROM organizations WHERE id = $1", ctx.path["org_id"]):
            raise not_found("Organização")
        vid = c.scalar("INSERT INTO beneficiary_verifications(org_id, status, provider, evidence_document_ids, account_holder_matches, reviewed_by, reviewed_at, review_note, expires_at)"
                       " VALUES ($1,$2,'manual',$3,$4,$5,now(),$6, CASE WHEN $2 = 'verified' THEN now() + interval '12 months' END) RETURNING id::text",
                       ctx.path["org_id"], body.status, [str(d) for d in body.evidence_document_ids], body.account_holder_matches, ctx.user_id, body.note)
        ctx.audit(c, "beneficiary.verification", "organization", ctx.path["org_id"], {"status": body.status}, org_id=ctx.path["org_id"])
    return {"id": vid, "status": body.status}


@route("GET", "/v1/admin/donation-risk-cases", auth="admin", permission="compliance.write", tags=T, summary="Casos de risco abertos (revisão humana)")
def admin_risk_cases(ctx: Ctx):
    with ctx.system_tx() as c:
        rows = c.query("SELECT r.id::text AS id, r.campaign_id::text AS campaign_id, r.donation_id::text AS donation_id, r.reason_codes, r.level, r.action,"
                       " r.rule_version, r.explanation, r.status, r.created_at, d.amount_cents, d.status AS donation_status, c.title AS campaign_title"
                       " FROM donation_risk_cases r LEFT JOIN donations d ON d.id = r.donation_id LEFT JOIN campaigns c ON c.id = r.campaign_id"
                       " WHERE r.status = 'open' ORDER BY r.level DESC, r.created_at")
    return {"items": rows, "rules_version": DON.RISK_RULES_VERSION,
            "note": "Nenhum limiar aqui é obrigação legal; payout_hold não existe nesta versão (depende do contrato com o provedor)."}


@route("POST", "/v1/admin/donation-risk-cases/{case_id}/decide", auth="admin", permission="compliance.write", body=TSch.RiskDecisionIn, tags=T,
       summary="Decide um caso de risco com justificativa; fica na trilha")
def admin_risk_decide(ctx: Ctx, body: TSch.RiskDecisionIn):
    with ctx.system_tx() as c:
        out = DON.decide_risk_case(c, case_id=ctx.path["case_id"], decided_by=ctx.user_id, action=body.action, note=body.note)
        if body.action == "reject":
            c.run("UPDATE donations SET status = 'cancelled' WHERE risk_case_id = $1 AND status IN ('awaiting_payment','under_review')", ctx.path["case_id"])
        if body.action == "allow":
            c.run("UPDATE donations SET status = 'confirmed' WHERE risk_case_id = $1 AND status = 'under_review'"
                  " AND EXISTS (SELECT 1 FROM payment_provider_events e WHERE e.donation_id = donations.id AND e.signature_verified"
                  "             AND e.event_type IN ('payment.confirmed','PAYMENT_RECEIVED','PAYMENT_CONFIRMED','charge.paid'))", ctx.path["case_id"])
        ctx.audit(c, "donation.risk_decided", "donation_risk_case", ctx.path["case_id"], {"action": body.action}, org_id=None)
    return out


@route("POST", "/v1/admin/donation-campaigns/{campaign_id}/reconcile", auth="admin", permission="finance.read", tags=T,
       summary="Conciliação: marca como conciliadas as doações que o provedor confirma (sandbox: todas as confirmadas) e lista exceções")
def admin_reconcile(ctx: Ctx):
    with ctx.system_tx() as c:
        out = DON.reconcile_campaign(c, ctx.path["campaign_id"])
        ctx.audit(c, "donation.reconciled", "campaign", ctx.path["campaign_id"], out, org_id=None)
    return out


@route("GET", "/v1/admin/donation-ledger/{campaign_id}", auth="admin", permission="finance.read", tags=T,
       summary="Razão de conciliação da campanha (partidas dobradas, append-only) e totais com definição")
def admin_ledger(ctx: Ctx):
    with ctx.system_tx() as c:
        if not c.scalar("SELECT 1 FROM campaigns WHERE id = $1", ctx.path["campaign_id"]):
            raise not_found("Campanha")
        entries = c.query("SELECT id, donation_id::text AS donation_id, txn_id::text AS txn_id, account, side, amount_cents, currency, reversal_of,"
                          " is_simulated, note, created_at FROM donation_ledger_entries WHERE campaign_id = $1 ORDER BY id", ctx.path["campaign_id"])
        totals = DON.campaign_totals(c, ctx.path["campaign_id"])
    return {"entries": entries, "totals": totals}

