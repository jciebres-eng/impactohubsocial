"""Doações, campanhas de arrecadação, QR, webhook do provedor, conciliação e prestação de contas — v0.33.0.

Toda confirmação de pagamento entra por UM lugar: `POST /v1/webhooks/donations/{provider}` (evento assinado,
deduplicado). Nenhuma rota aceita "pago" vindo do navegador. Só existe o provedor sandbox (simulado).
"""
from __future__ import annotations

import json

from starlette.responses import JSONResponse, Response

from ..http import ApiError, Ctx, not_found, route
from ..services import donations as DON
from ..services import reconciliation as RECON
from ..services import remuneration as REM
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
    out["recurring_available"] = bool(getattr(ctx.settings, "recurring_donations_enabled", False) and out["campaign"].get("allow_recurring"))
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
    donor_org_id = ctx.principal.org_id if (body.as_organization and ctx.principal) else None
    with ctx.system_tx() as c:
        out = DON.start_donation(c, settings=ctx.settings, campaign_slug=ctx.path["slug"], amount_cents=body.amount_cents,
                                 method=body.method, donor_user_id=donor_user_id, donor_display=body.donor_display,
                                 donor_email=body.donor_email, public_anonymous=body.public_anonymous, cover_costs=body.cover_costs,
                                 idempotency_key=body.idempotency_key, cipher=ctx.app.cipher, donor_org_id=donor_org_id,
                                 funding_source=body.funding_source, platform_contribution_cents=body.platform_contribution_cents)
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
       summary="Webhook do provedor: assinatura conferida; evento gravado uma vez (fase 1) e aplicado travando a linha do evento (fase 2); falha interna fica registrada e é reprocessada")
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
    # Fase 1: gravar (commit próprio) — um evento aceito nunca se perde, mesmo que a aplicação falhe a seguir.
    with ctx.system_tx() as c:
        rec = DON.record_provider_event(c, provider=provider, event=event, signature_verified=verified, raw=payload)
    if not verified:
        return JSONResponse({"status": "rejected_signature", "effect": None, "donation_id": None}, status_code=202)
    if not rec["reapplicable"]:
        return JSONResponse({"status": "duplicate", "effect": None, "donation_id": None}, status_code=200)
    # Fase 2: aplicar. Erro interno → evento `failed` + exceção na fila; 500 faz o provedor reenviar (at-least-once),
    # e a rotina financeira reprocessa mesmo que ele não reenvie (cenários 33 e 35).
    try:
        with ctx.system_tx() as c:
            out = DON.apply_recorded_event(c, provider=provider, row_id=rec["event_row_id"], event=event)
    except ApiError:
        raise
    except Exception as exc:  # noqa: BLE001 — falha interna: registra e devolve 500 para o provedor tentar de novo
        with ctx.system_tx() as c:
            DON.mark_event_failed(c, row_id=rec["event_row_id"], error=type(exc).__name__)
        return JSONResponse({"status": "failed", "retry": True}, status_code=500)
    status = "duplicate" if (rec["duplicate"] or out.get("duplicate")) else out.get("effect", "recorded")
    return JSONResponse({"status": status, "effect": out.get("effect"), "donation_id": out.get("donation_id")}, status_code=200)


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
        ids = c.query("SELECT id::text AS id FROM recurring_donation_agreements WHERE donor_user_id = $1 ORDER BY created_at DESC", ctx.user_id)
        rec = [DON.recurring_view(c, r["id"]) for r in ids]
    return {"donations": rows, "recurring": rec,
            "recurring_note": "Doação recorrente exige instrumento suportado pelo provedor e consentimento explícito; nesta versão nenhum provedor real está ligado."}


@route("POST", "/v1/public/donation-campaigns/{slug}/recurring", auth="user", body=TSch.RecurringDonationIn, status=201,
       rate=("recurring_user", 10, 3600), tags=T,
       summary="Autoriza doação recorrente (consentimento guardado por hash). Desligada até instrumento homologado no provedor")
def start_recurring(ctx: Ctx, body: TSch.RecurringDonationIn):
    with ctx.system_tx() as c:
        out = DON.start_recurring(c, settings=ctx.settings, campaign_slug=ctx.path["slug"], donor_user_id=ctx.user_id,
                                  amount_cents=body.amount_cents, method=body.method, consent_text=body.consent_text)
        ctx.audit(c, "donation.recurring_authorized", "recurring_donation_agreement", out["id"], {"amount_cents": body.amount_cents}, org_id=None)
    return out


@route("POST", "/v1/me/recurring-donations/{agreement_id}/cancel", auth="user", tags=T, summary="Cancela um acordo de doação recorrente (sempre possível pelo doador)")
def cancel_recurring(ctx: Ctx):
    with ctx.system_tx() as c:
        if not c.run("UPDATE recurring_donation_agreements SET status = 'cancelled', cancelled_at = now() WHERE id = $1 AND donor_user_id = $2 AND status <> 'cancelled'",
                     ctx.path["agreement_id"], ctx.user_id):
            raise not_found("Acordo recorrente")
        ctx.audit(c, "donation.recurring_cancelled", "recurring_donation_agreement", ctx.path["agreement_id"], {}, org_id=None)
    return {"status": "cancelled"}


# ============================================================================ revisão interna (quatro olhos) e risco
@route("GET", "/v1/admin/donation-campaigns", auth="admin", permission="compliance.read", tags=T,
       summary="Campanhas aguardando revisão e campanhas publicadas")
def admin_campaigns(ctx: Ctx):
    with ctx.system_tx() as c:
        wanted = ctx.request.query_params.get("status") or ""
        allowed = ("pending_review", "approved", "published", "under_review", "paused", "rejected")
        statuses = [wanted] if wanted in allowed else list(allowed[:-1])
        rows = c.query("SELECT c.id::text AS id, c.slug, c.title, c.kind, c.status, c.target_cents, c.created_at, c.purpose, c.accepted_terms_at,"
                       " c.created_by::text AS created_by, c.beneficiary_org_id::text AS beneficiary_org_id, o.legal_name AS org,"
                       " beneficiary_verified(c.beneficiary_org_id) AS beneficiary_verified,"
                       # v0.35.0 (KYC-03): decisão 'verificado' ainda sem a confirmação da segunda pessoa
                       " (SELECT k.id::text FROM org_kyb_verifications k WHERE k.org_id = c.beneficiary_org_id"
                       "   AND k.id = (SELECT k2.id FROM org_kyb_verifications k2 WHERE k2.org_id = c.beneficiary_org_id ORDER BY k2.created_at DESC, k2.id DESC LIMIT 1)"
                       "   AND k.status = 'verified' AND k.confirmed_by IS NULL) AS verification_awaiting_confirmation,"
                       " (SELECT k.reviewed_by::text FROM org_kyb_verifications k WHERE k.org_id = c.beneficiary_org_id"
                       "   ORDER BY k.created_at DESC, k.id DESC LIMIT 1) AS verification_reviewed_by"
                       " FROM campaigns c JOIN organizations o ON o.id = c.beneficiary_org_id"
                       " WHERE c.status = ANY($1) ORDER BY c.status, c.created_at", statuses)
    return {"items": rows, "me": ctx.user_id}


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
    # v0.35.0 (auditoria, KYC-03): 'verified' exige titularidade conferida e documentos de evidência da PRÓPRIA organização;
    # quem verifica não pode ser membro dela; e só vale depois da confirmação de OUTRA pessoa da equipe (rota abaixo).
    # Uma decisão que não seja 'verified' tira do ar as campanhas abertas da organização.
    org = ctx.path["org_id"]
    with ctx.system_tx() as c:
        if not c.scalar("SELECT 1 FROM organizations WHERE id = $1", org):
            raise not_found("Organização")
        if c.scalar("SELECT 1 FROM memberships WHERE org_id = $1 AND user_id = $2", org, ctx.user_id):
            raise ApiError(403, "conflict_of_interest", "Quem verifica não pode ser membro da organização verificada")
        if body.status == "verified" and body.account_holder_matches is not True:
            raise ApiError(422, "account_holder_required", "Verificado exige a titularidade da conta de recebimento conferida")
        ids = [str(d) for d in body.evidence_document_ids]
        if ids and int(c.scalar("SELECT count(*) FROM documents WHERE id = ANY($1::uuid[]) AND org_id = $2 AND deleted_at IS NULL", ids, org)) != len(set(ids)):
            raise ApiError(422, "evidence_invalid", "Documento de evidência inexistente ou de outra organização")
        vid = c.scalar("INSERT INTO org_kyb_verifications(org_id, status, provider, evidence_document_ids, account_holder_matches, reviewed_by, reviewed_at, review_note, expires_at)"
                       " VALUES ($1,$2,'manual',$3,$4,$5,now(),$6, CASE WHEN $2 = 'verified' THEN now() + interval '12 months' END) RETURNING id::text",
                       ctx.path["org_id"], body.status, [str(d) for d in body.evidence_document_ids], body.account_holder_matches, ctx.user_id, body.note)
        paused = 0
        if body.status != "verified":
            # 'published' → 'under_review' (a máquina de estados não leva 'target_reached' a revisão; ali a doação para
            # pela checagem de verificação em start_donation)
            paused = c.run("UPDATE campaigns SET status = 'under_review' WHERE beneficiary_org_id = $1 AND status = 'published'", org)
        ctx.audit(c, "beneficiary.verification", "organization", org, {"status": body.status, "campaigns_paused": paused}, org_id=org)
    return {"id": vid, "status": body.status, "needs_second_confirmation": body.status == "verified", "campaigns_paused": paused}


@route("POST", "/v1/admin/beneficiaries/{org_id}/verification/{verification_id}/confirm", auth="admin", permission="compliance.write",
       tags=T, summary="Segunda pessoa da equipe confirma a verificação do beneficiário (quatro olhos, conferido pelo banco)")
def admin_beneficiary_confirm(ctx: Ctx):
    org = ctx.path["org_id"]
    with ctx.system_tx() as c:
        v = c.one("SELECT id::text AS id, status, reviewed_by::text AS reviewed_by, confirmed_by FROM org_kyb_verifications"
                  " WHERE id = $1 AND org_id = $2 FOR UPDATE", ctx.path["verification_id"], org)
        if not v:
            raise not_found("Verificação")
        latest = c.scalar("SELECT id::text FROM org_kyb_verifications WHERE org_id = $1 ORDER BY created_at DESC, id DESC LIMIT 1", org)
        if v["status"] != "verified" or v["confirmed_by"] or latest != v["id"]:
            raise ApiError(409, "not_confirmable", "Só a decisão 'verificado' mais recente, ainda não confirmada, pode ser confirmada")
        if v["reviewed_by"] == ctx.user_id:
            raise ApiError(403, "four_eyes", "Quem verificou não pode confirmar a própria verificação")
        if c.scalar("SELECT 1 FROM memberships WHERE org_id = $1 AND user_id = $2", org, ctx.user_id):
            raise ApiError(403, "conflict_of_interest", "Quem confirma não pode ser membro da organização verificada")
        c.run("UPDATE org_kyb_verifications SET confirmed_by = $2, confirmed_at = now() WHERE id = $1", v["id"], ctx.user_id)
        ctx.audit(c, "beneficiary.verification_confirmed", "organization", org, {"verification_id": v["id"]}, org_id=org)
    return {"id": v["id"], "status": "verified", "confirmed": True}


@route("GET", "/v1/admin/donation-risk-cases", auth="admin", permission="compliance.read", tags=T, summary="Casos de risco abertos (revisão humana)")
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
            # v0.35.0 (auditoria, PAY-05): "permitir" confirma pelo caminho normal (razão, obrigações, comprovante);
            # antes era um UPDATE de estado sem lançamento.
            out = {**out, "released": DON.release_after_review(c, case_id=ctx.path["case_id"])}
        ctx.audit(c, "donation.risk_decided", "donation_risk_case", ctx.path["case_id"], {"action": body.action}, org_id=None)
    return out


@route("POST", "/v1/admin/donation-campaigns/{campaign_id}/reconcile", auth="admin", permission="finance.write", tags=T,
       summary="Conciliação da campanha (atalho da v0.33.0): mesma regra da execução com fila de exceções — sandbox contra os eventos assinados; provedor real exige extrato")
def admin_reconcile(ctx: Ctx):
    # v0.35.0 (auditoria, PAY-07): antes marcava TODAS as confirmadas como conciliadas, sem comparar nada.
    with ctx.system_tx() as c:
        out = RECON.run_for_campaign(c, campaign_id=ctx.path["campaign_id"], run_by=ctx.user_id)
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



# ============================================================================ v0.34.0 — recursos externos, compromissos, financiador
@route("POST", "/v1/campaigns/{campaign_id}/external-resources", body=TSch.ExternalResourceIn, min_role=WRITE, status=201, tags=T,
       summary="Declara recurso recebido FORA da plataforma (entra na prestação de contas; nunca no razão nem na barra)")
def external_resource_declare(ctx: Ctx, body: TSch.ExternalResourceIn):
    with ctx.tx() as c:
        rid = DON.declare_external_resource(c, campaign_id=ctx.path["campaign_id"], org_id=ctx.org_id, user_id=ctx.user_id, kind=body.kind,
                                            source_name=body.source_name, funding_source=body.funding_source, instrument_ref=body.instrument_ref,
                                            amount_cents=body.amount_cents, in_kind_description=body.in_kind_description,
                                            received_on=body.received_on.isoformat(), evidence_document_id=str(body.evidence_document_id) if body.evidence_document_id else None,
                                            note=body.note)
        ctx.audit(c, "external_resource.declared", "external_resource", rid, {"kind": body.kind, "funding_source": body.funding_source, "amount_cents": body.amount_cents})
    return {"id": rid}


@route("POST", "/v1/public/donation-campaigns/{slug}/pledge", auth="user", body=TSch.DonationPledgeIn, status=201, rate=("pledge_user", 20, 3600), tags=T,
       summary="Registra um compromisso de doação futura (não é doação, não é dinheiro)")
def pledge(ctx: Ctx, body: TSch.DonationPledgeIn):
    org = ctx.principal.org_id if body.as_organization else None
    with ctx.system_tx() as c:
        out = DON.make_pledge(c, campaign_slug=ctx.path["slug"], user_id=ctx.user_id, org_id=org, display=body.display,
                              amount_cents=body.amount_cents, expected_on=body.expected_on.isoformat() if body.expected_on else None, note=body.note)
        ctx.audit(c, "pledge.created", "donation_pledge", out["id"], {"amount_cents": body.amount_cents}, org_id=org)
    return out


@route("POST", "/v1/me/pledges/{pledge_id}/cancel", auth="user", tags=T, summary="Cancela o próprio compromisso")
def pledge_cancel(ctx: Ctx):
    with ctx.system_tx() as c:
        out = DON.cancel_pledge(c, pledge_id=ctx.path["pledge_id"], user_id=ctx.user_id)
        ctx.audit(c, "pledge.cancelled", "donation_pledge", ctx.path["pledge_id"], {}, org_id=None)
    return out


@route("POST", "/v1/campaigns/{campaign_id}/pledges/{pledge_id}/fulfill", body=TSch.PledgeFulfillIn, min_role=WRITE, tags=T,
       summary="Liga um compromisso à doação CONFIRMADA que o cumpriu")
def pledge_fulfill(ctx: Ctx, body: TSch.PledgeFulfillIn):
    with ctx.tx() as c:
        DON.require_campaign_owner(c, ctx.path["campaign_id"], ctx.org_id)
        out = DON.fulfill_pledge(c, pledge_id=ctx.path["pledge_id"], org_id=ctx.org_id, donation_id=str(body.donation_id))
        ctx.audit(c, "pledge.fulfilled", "donation_pledge", ctx.path["pledge_id"], {"donation_id": str(body.donation_id)})
    return out


@route("GET", "/v1/org/contributions", min_role="viewer", tags=T, summary="Painel do financiador: doações e compromissos feitos em nome da organização")
def org_contributions(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return DON.funder_view(c, org_id=ctx.org_id)


# ============================================================================ v0.34.0 — remuneração: gratuito até gerar valor
@route("GET", "/v1/org/remuneration", min_role="viewer", tags=T,
       summary="Obrigações de remuneração da organização, política vigente, franquia e avisos — nada aqui bloqueia nada")
def org_remuneration(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return REM.org_view(c, ctx.org_id)


@route("POST", "/v1/org/remuneration/{obligation_id}/dispute", body=TSch.ObligationDisputeIn, min_role=WRITE, tags=T,
       summary="Contesta uma obrigação (fica em disputa até decisão registrada)")
def org_remuneration_dispute(ctx: Ctx, body: TSch.ObligationDisputeIn):
    with ctx.system_tx() as c:
        out = REM.dispute(c, obligation_id=ctx.path["obligation_id"], org_id=ctx.org_id, actor=ctx.user_id, reason=body.reason)
        ctx.audit(c, "remuneration.disputed", "remuneration_obligation", ctx.path["obligation_id"], {"reason": body.reason[:200]})
    return out


@route("POST", "/v1/org/remuneration/notices/{notice_id}/ack", min_role="viewer", tags=T, summary="Registra ciência de um aviso")
def org_notice_ack(ctx: Ctx):
    with ctx.tx() as c:
        REM.ack_notice(c, notice_id=ctx.path["notice_id"], org_id=ctx.org_id, user_id=ctx.user_id)
    return {"status": "acknowledged"}


@route("GET", "/v1/admin/remuneration", auth="admin", permission="finance.read", tags=T,
       summary="Obrigações por estado (previsto × devido × faturado × recebido × liquidado) — nunca somadas num número só")
def admin_remuneration(ctx: Ctx):
    with ctx.system_tx() as c:
        state = ctx.request.query_params.get("state")
        rows = c.query("SELECT o.id::text AS id, o.org_id::text AS org_id, org.legal_name AS org_name, o.source_kind, o.source_id, o.rule_key, o.basis_cents,"
                       " o.amount_cents, o.funding_source, o.public_fee_authorized, o.state, o.trigger_code, o.due_on, o.received_cents,"
                       " o.platform_charge_id::text AS platform_charge_id, o.created_at FROM remuneration_obligations o JOIN organizations org ON org.id = o.org_id"
                       + (" WHERE o.state = $1" if state else "") + " ORDER BY o.created_at DESC LIMIT 500", *([state] if state else []))
        return {"items": rows, "revenue": REM.platform_revenue_view(c), "policy": {k: v for k, v in REM.policy(c).items() if k != "id"}}


@route("POST", "/v1/admin/remuneration/orgs/{org_id}/evaluate", auth="admin", permission="finance.write", tags=T,
       summary="Aplica a política 'gratuito até gerar valor' à organização: o que virou devido e por que o resto não virou")
def admin_remuneration_evaluate(ctx: Ctx):
    with ctx.system_tx() as c:
        out = REM.evaluate(c, org_id=ctx.path["org_id"], actor=ctx.user_id)
        ctx.audit(c, "remuneration.evaluated", "organization", ctx.path["org_id"], {"became_due": len(out["became_due"]), "kept": len(out["kept"])}, org_id=ctx.path["org_id"])
    return out


@route("POST", "/v1/admin/remuneration/orgs/{org_id}/notices", auth="admin", permission="finance.write", body=TSch.NoticeIn, tags=T,
       summary="Envia (registra) um aviso prévio da política à organização")
def admin_remuneration_notice(ctx: Ctx, body: TSch.NoticeIn):
    with ctx.system_tx() as c:
        nid = REM.send_notice(c, org_id=ctx.path["org_id"], kind=body.kind, created_by=ctx.user_id, body=body.body, channel=body.channel)
        ctx.audit(c, "remuneration.notice_sent", "remuneration_notice", nid, {"kind": body.kind}, org_id=ctx.path["org_id"])
    return {"id": nid}


@route("POST", "/v1/admin/remuneration/invoice", auth="admin", permission="finance.write", body=TSch.ObligationInvoiceIn, tags=T,
       summary="Fatura obrigações DEVIDAS numa cobrança própria da plataforma (nunca desconto de doação)")
def admin_remuneration_invoice(ctx: Ctx, body: TSch.ObligationInvoiceIn):
    with ctx.system_tx() as c:
        out = REM.invoice(c, obligation_ids=[str(i) for i in body.obligation_ids], actor=ctx.user_id)
        ctx.audit(c, "remuneration.invoiced", "platform_charge", out["platform_charge_id"], {"total_cents": out["total_cents"], "n": len(out["obligations"])}, org_id=None)
    return out


@route("POST", "/v1/admin/remuneration/{obligation_id}/charged", auth="admin", permission="finance.write", tags=T, summary="Marca como cobrada (enviada ao pagador)")
def admin_remuneration_charged(ctx: Ctx):
    with ctx.system_tx() as c:
        out = REM.mark_charged(c, obligation_id=ctx.path["obligation_id"], actor=ctx.user_id)
        ctx.audit(c, "remuneration.charged", "remuneration_obligation", ctx.path["obligation_id"], {}, org_id=None)
    return out


@route("POST", "/v1/admin/remuneration/{obligation_id}/receipt", auth="admin", permission="finance.write", body=TSch.ObligationReceiptIn, tags=T,
       summary="Registra pagamento RECEBIDO (parcial ou total) com referência")
def admin_remuneration_receipt(ctx: Ctx, body: TSch.ObligationReceiptIn):
    with ctx.system_tx() as c:
        out = REM.register_receipt(c, obligation_id=ctx.path["obligation_id"], actor=ctx.user_id, received_cents=body.received_cents, reference=body.reference)
        ctx.audit(c, "remuneration.received", "remuneration_obligation", ctx.path["obligation_id"], {"received_cents": body.received_cents}, org_id=None)
    return out


@route("POST", "/v1/admin/remuneration/{obligation_id}/refund", auth="admin", permission="finance.approve", body=TSch.ObligationRefundIn, tags=T,
       summary="Reembolso integral do que a plataforma recebeu (ex.: serviço cancelado) — a obrigação vira estornada; segregado")
def admin_remuneration_refund(ctx: Ctx, body: TSch.ObligationRefundIn):
    with ctx.system_tx() as c:
        out = REM.refund_received(c, obligation_id=ctx.path["obligation_id"], actor=ctx.user_id, refunded_cents=body.refunded_cents,
                                  reference=body.reference, note=body.note)
        ctx.audit(c, "remuneration.refunded", "remuneration_obligation", ctx.path["obligation_id"], {"refunded_cents": body.refunded_cents}, org_id=None)
    return out


@route("POST", "/v1/admin/remuneration/{obligation_id}/settle", auth="admin", permission="finance.approve", body=TSch.ObligationSettleIn, tags=T,
       summary="Marca como LIQUIDADA (conciliada com extrato) — segregado: exige finance.approve")
def admin_remuneration_settle(ctx: Ctx, body: TSch.ObligationSettleIn):
    with ctx.system_tx() as c:
        out = REM.mark_settled(c, obligation_id=ctx.path["obligation_id"], actor=ctx.user_id, note=body.note)
        ctx.audit(c, "remuneration.settled", "remuneration_obligation", ctx.path["obligation_id"], {}, org_id=None)
    return out


@route("POST", "/v1/admin/remuneration/{obligation_id}/decide", auth="admin", permission="finance.approve", body=TSch.ObligationDecisionIn, tags=T,
       summary="Decide uma disputa (manter, dispensar, isentar) com justificativa")
def admin_remuneration_decide(ctx: Ctx, body: TSch.ObligationDecisionIn):
    with ctx.system_tx() as c:
        out = REM.decide_dispute(c, obligation_id=ctx.path["obligation_id"], actor=ctx.user_id, outcome=body.outcome, note=body.note)
        ctx.audit(c, "remuneration.dispute_decided", "remuneration_obligation", ctx.path["obligation_id"], {"outcome": body.outcome}, org_id=None)
    return out


@route("POST", "/v1/admin/remuneration/{obligation_id}/waive", auth="admin", permission="finance.approve", body=TSch.ObligationWaiveIn, tags=T,
       summary="Dispensa uma obrigação com justificativa registrada")
def admin_remuneration_waive(ctx: Ctx, body: TSch.ObligationWaiveIn):
    with ctx.system_tx() as c:
        out = REM.waive(c, obligation_id=ctx.path["obligation_id"], actor=ctx.user_id, reason=body.reason)
        ctx.audit(c, "remuneration.waived", "remuneration_obligation", ctx.path["obligation_id"], {"reason": body.reason[:200]}, org_id=None)
    return out


@route("POST", "/v1/admin/remuneration/{obligation_id}/authorize-public", auth="admin", permission="finance.approve", body=TSch.PublicFeeAuthorizationIn, tags=T,
       summary="Recurso público: registra instrumento e autorização que tornam a taxa elegível (ADR-379)")
def admin_remuneration_authorize_public(ctx: Ctx, body: TSch.PublicFeeAuthorizationIn):
    with ctx.system_tx() as c:
        out = REM.authorize_public_fee(c, obligation_id=ctx.path["obligation_id"], actor=ctx.user_id, instrument_ref=body.instrument_ref, note=body.note)
        ctx.audit(c, "remuneration.public_fee_authorized", "remuneration_obligation", ctx.path["obligation_id"], {"instrument_ref": body.instrument_ref}, org_id=None)
    return out


@route("POST", "/v1/admin/remuneration/mark-overdue", auth="admin", permission="finance.write", tags=T, summary="Marca vencidas as faturadas além do prazo (rotina)")
def admin_remuneration_overdue(ctx: Ctx):
    with ctx.system_tx() as c:
        n = REM.mark_overdue(c)
        ctx.audit(c, "remuneration.overdue_marked", "remuneration_obligation", "batch", {"n": n}, org_id=None)
    return {"marked": n}


# ============================================================================ v0.34.0 — conciliação com fila de exceções
@route("POST", "/v1/admin/reconciliation/campaigns/{campaign_id}/run", auth="admin", permission="finance.write", body=TSch.ReconciliationSnapshotIn, tags=T,
       summary="Executa a conciliação da campanha contra o snapshot do provedor (sandbox: derivado dos eventos assinados) e abre exceções")
def admin_reconciliation_run(ctx: Ctx, body: TSch.ReconciliationSnapshotIn):
    with ctx.system_tx() as c:
        if body.charges:
            out = RECON.propose_manual_run(c, campaign_id=ctx.path["campaign_id"], snapshot=[x.model_dump() for x in body.charges], run_by=ctx.user_id)
        else:
            out = RECON.run_for_campaign(c, campaign_id=ctx.path["campaign_id"], run_by=ctx.user_id)
        ctx.audit(c, "reconciliation.run", "campaign", ctx.path["campaign_id"],
                  {"opened": out["opened"], "reconciled": out["reconciled"], "source": out["snapshot_source"]}, org_id=None)
    return out


@route("POST", "/v1/admin/reconciliation/runs/{run_id}/approve", auth="admin", permission="finance.approve", tags=T,
       summary="Segunda pessoa aprova o extrato manual: reexecuta com o mesmo extrato (hash conferido) e só então concilia")
def admin_reconciliation_approve(ctx: Ctx):
    with ctx.system_tx() as c:
        out = RECON.approve_manual_run(c, run_id=ctx.path["run_id"], approver=ctx.user_id)
        ctx.audit(c, "reconciliation.approved", "reconciliation_run", ctx.path["run_id"], {"reconciled": out["reconciled"]}, org_id=None)
    return out


@route("GET", "/v1/admin/reconciliation/exceptions", auth="admin", permission="finance.read", tags=T, summary="Fila de exceções de conciliação")
def admin_reconciliation_exceptions(ctx: Ctx):
    with ctx.system_tx() as c:
        return {"items": RECON.list_exceptions(c, status=ctx.request.query_params.get("status") or None)}


@route("POST", "/v1/admin/reconciliation/exceptions/{exception_id}/assign", auth="admin", permission="finance.write", tags=T, summary="Assume uma exceção")
def admin_reconciliation_assign(ctx: Ctx):
    with ctx.system_tx() as c:
        out = RECON.assign(c, exception_id=ctx.path["exception_id"], user_id=ctx.user_id)
        ctx.audit(c, "reconciliation.assigned", "reconciliation_exception", ctx.path["exception_id"], {}, org_id=None)
    return out


@route("POST", "/v1/admin/reconciliation/exceptions/{exception_id}/resolve", auth="admin", permission="finance.write", body=TSch.ReconciliationResolveIn, tags=T,
       summary="Resolve ou descarta uma exceção com justificativa (fica no histórico)")
def admin_reconciliation_resolve(ctx: Ctx, body: TSch.ReconciliationResolveIn):
    with ctx.system_tx() as c:
        out = RECON.resolve(c, exception_id=ctx.path["exception_id"], user_id=ctx.user_id, outcome=body.outcome, note=body.note)
        ctx.audit(c, "reconciliation.resolved", "reconciliation_exception", ctx.path["exception_id"], {"outcome": body.outcome}, org_id=None)
    return out


@route("GET", "/v1/admin/reconciliation/exceptions/{exception_id}/history", auth="admin", permission="finance.read", tags=T, summary="Histórico de uma exceção")
def admin_reconciliation_history(ctx: Ctx):
    with ctx.system_tx() as c:
        return {"items": RECON.history(c, ctx.path["exception_id"])}
