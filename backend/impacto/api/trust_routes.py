"""TRUST, IDENTITY & DIGITAL SIGNATURE — API.

Destaque desta camada: **verificação pública por terceiro** (`GET /v1/public/verify/{code}`), sem login, lendo apenas o
registro público curado. Responde: é genuíno? qual versão foi assinada? a integridade continua intacta? quem assinou?
está válido ou revogado?

Segurança: segredo nenhum trafega; identidade e credencial são decididas em contexto privilegiado (ninguém se promove);
assinatura exige senha **e** código de uso único ligado ao hash do conteúdo; `signatures` continua append-only e a
revogação é um fato novo; a cadeia de custódia é encadeada por gatilho no banco.
"""
from __future__ import annotations

from starlette.responses import Response

from ..core import access as ACCESS
from ..http import ApiError, Ctx, not_found, page, route
from ..security.tokens import hmac_hex
from ..trust import agreements as AG
from ..trust import challenges as CH
from ..trust import codes as CODES
from ..trust import credentials as CRED
from ..trust import custody as CUST
from ..trust import identity as IDENT
from ..trust import integrity as INTEG
from ..trust import qr as QR
from ..trust import timestamps as TS
from ..trust import verifiable as VR
from . import trust_schemas as TSch

T = ("trust",)
WRITE = "manager"
OWNER = "owner"


def _verify_url(ctx: Ctx, code: str) -> str:
    return f"{ctx.settings.public_base_url.rstrip('/')}/verificar/{code}"


# ================================================================================ catálogo
@route("GET", "/v1/trust/councils", min_role="viewer", tags=T,
       summary="Conselhos profissionais do catálogo (o formato do registro só é validado quando há padrão configurado)")
def councils(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        items = CRED.councils(c)
    return {"items": items, "note": CRED.VERIFIED_MEANING,
            "limits": "A plataforma não consulta conselho profissional on-line; a conferência é documental e humana."}


# ================================================================================ identidade da pessoa
@route("GET", "/v1/trust/identity", auth="user", tags=T, summary="Meu nível de identidade, pedidos e documentos enviados")
def identity_me(ctx: Ctx):
    with ctx.system_tx() as c:
        return IDENT.overview(c, ctx.user_id)


@route("POST", "/v1/trust/identity/verifications", auth="user", body=TSch.IdentityRequestIn, status=201,
       rate=("idv_user", 10, 3600), tags=T,
       summary="Pede verificação de identidade (documento = conferência humana; biometria e SMS não estão disponíveis)")
def identity_request(ctx: Ctx, body: TSch.IdentityRequestIn):
    with ctx.tx() as c:
        out = IDENT.request(c, user_id=ctx.user_id, level=body.level, method=body.method)
        ctx.audit(c, "identity.requested", "identity_verification", out["id"], {"level": body.level})
    return {**out, "next": "Envie o documento em Documentos e anexe-o a este pedido."}


@route("POST", "/v1/trust/identity/verifications/{verification_id}/documents", auth="user", body=TSch.IdentityDocumentIn,
       status=201, tags=T, summary="Anexa um documento já enviado ao cofre a um pedido de verificação")
def identity_attach(ctx: Ctx, body: TSch.IdentityDocumentIn):
    with ctx.tx() as c:
        out = IDENT.attach_document(c, verification_id=ctx.path["verification_id"], user_id=ctx.user_id,
                                    document_id=body.document_id, kind=body.kind)
        ctx.audit(c, "identity.document_attached", "identity_verification", ctx.path["verification_id"], {"kind": body.kind})
    if not out.get("duplicate"):
        with ctx.system_tx() as c:
            IDENT.mark_under_review(c, ctx.path["verification_id"])
    return {**out, "note": "A plataforma guarda a referência do documento; não extrai nem armazena o número."}


@route("GET", "/v1/admin/trust/identity/queue", auth="admin", query=TSch.Pagination, tags=("admin", "trust"),
       summary="Fila de verificações de identidade aguardando conferência humana")
def identity_queue(ctx: Ctx, q: TSch.Pagination):
    with ctx.system_tx() as c:
        return {"items": IDENT.queue(c, q.limit, q.offset)}


@route("POST", "/v1/admin/trust/identity/{verification_id}/decide", auth="admin", body=TSch.DecisionIn, tags=("admin", "trust"),
       summary="Decide um pedido de verificação de identidade (decisão humana registrada na cadeia de custódia)")
def identity_decide(ctx: Ctx, body: TSch.DecisionIn):
    with ctx.system_tx() as c:
        out = IDENT.decide(c, verification_id=ctx.path["verification_id"], approve=body.approve, decided_by=ctx.user_id,
                           note=body.note, expires_at=body.expires_at.isoformat() if body.expires_at else None)
        if not out["found"]:
            raise not_found("Verificação")
        ctx.audit(c, "identity.decided", "identity_verification", ctx.path["verification_id"],
                  {"approve": body.approve, "level": out["level"]})
    return out


# ================================================================================ credencial profissional
@route("POST", "/v1/org/credentials/{credential_id}/document", body=TSch.IdentityDocumentIn, min_role=WRITE, tags=T,
       summary="Anexa o documento do conselho à credencial e a coloca na fila de conferência")
def credential_document(ctx: Ctx, body: TSch.IdentityDocumentIn):
    with ctx.tx() as c:
        out = CRED.attach_document(c, credential_id=ctx.path["credential_id"], org_id=ctx.org_id,
                                   document_id=body.document_id, actor_user_id=ctx.user_id)
        ctx.audit(c, "credential.document_attached", "professional_credential", ctx.path["credential_id"], {})
    with ctx.system_tx() as c:
        CRED.mark_submitted(c, ctx.path["credential_id"])
    return out


@route("GET", "/v1/org/credentials/{credential_id}/history", min_role="viewer", tags=T,
       summary="Histórico append-only da verificação da credencial")
def credential_history(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        if not c.scalar("SELECT 1 FROM professional_credentials WHERE id = $1", ctx.path["credential_id"]):
            raise not_found("Credencial")
        return {"items": CRED.history(c, ctx.path["credential_id"]), "meaning": CRED.VERIFIED_MEANING}


@route("GET", "/v1/admin/trust/credentials/queue", auth="admin", query=TSch.Pagination, tags=("admin", "trust"),
       summary="Credenciais profissionais com documento aguardando conferência")
def credential_queue(ctx: Ctx, q: TSch.Pagination):
    with ctx.system_tx() as c:
        return {"items": CRED.queue(c, q.limit, q.offset)}


@route("POST", "/v1/admin/trust/credentials/{credential_id}/decide", auth="admin", body=TSch.CredentialDecisionIn,
       tags=("admin", "trust"), summary="Confere a credencial; aprovar eleva a identidade da pessoa ao nível profissional")
def credential_decide(ctx: Ctx, body: TSch.CredentialDecisionIn):
    with ctx.system_tx() as c:
        out = CRED.decide(c, credential_id=ctx.path["credential_id"], approve=body.approve, decided_by=ctx.user_id,
                          note=body.note, valid_until=body.valid_until.isoformat() if body.valid_until else None)
        if not out["found"]:
            raise not_found("Credencial")
        ctx.audit(c, "credential.decided", "professional_credential", ctx.path["credential_id"], {"approve": body.approve})
    return out


@route("POST", "/v1/admin/trust/credentials/{credential_id}/revoke", auth="admin", body=TSch.RevokeIn, tags=("admin", "trust"),
       summary="Revoga uma credencial verificada (motivo obrigatório; entra na cadeia de custódia)")
def credential_revoke(ctx: Ctx, body: TSch.RevokeIn):
    with ctx.system_tx() as c:
        out = CRED.revoke(c, credential_id=ctx.path["credential_id"], reason=body.reason, revoked_by=ctx.user_id)
        if not out["found"]:
            raise not_found("Credencial")
        ctx.audit(c, "credential.revoked", "professional_credential", ctx.path["credential_id"], {})
    return out


# ================================================================================ assinatura: segunda camada
@route("POST", "/v1/signatures/challenge", body=TSch.ChallengeIn, min_role="member", status=201,
       rate=("sigchal_ip", 30, 3600), tags=("signatures",),
       summary="Envia o código de confirmação da assinatura (segunda camada), amarrado ao hash exato do conteúdo")
def signature_challenge(ctx: Ctx, body: TSch.ChallengeIn):
    table, col = {"document": ("documents", "sha256"), "draft": ("drafts", "content_sha256"),
                  "agreement": ("signed_agreements", "content_sha256")}[body.subject_type]
    with ctx.tx(readonly=True) as c:
        h = c.scalar(f"SELECT {col} FROM {table} WHERE id = $1", body.subject_id)
    if h is None:
        raise not_found("Objeto da assinatura")
    with ctx.system_tx() as c:
        email = c.scalar("SELECT email FROM users WHERE id = $1", ctx.user_id)
        hint = email.split("@")[0][:2] + "•••@" + email.split("@")[1] if email and "@" in email else None
        code, chal = CH.create(c, user_id=ctx.user_id, subject_type=body.subject_type, subject_id=body.subject_id,
                               subject_sha256=h, channel=body.channel, destination_hint=hint)
    ctx.app.mailer.send(email, "Código para assinar na IMPACTO",
                        f"Seu código de confirmação é {code}.\n\nEle vale {CH.TTL_MINUTES} minutos e serve só para esta "
                        f"assinatura. Se você não pediu, ignore esta mensagem e troque sua senha.")
    with ctx.tx() as c:
        ctx.audit(c, "signature.challenge_sent", body.subject_type, body.subject_id, {"channel": body.channel})
    return {**chal, "subject_sha256": h,
            "note": "O código vale só para esta versão do conteúdo. Se o conteúdo mudar, peça um novo."}


@route("POST", "/v1/signatures/{signature_id}/revoke", body=TSch.RevokeIn, min_role=OWNER, tags=("signatures",),
       summary="Revoga uma assinatura (fato novo: a assinatura em si é append-only e permanece no histórico)")
def signature_revoke(ctx: Ctx, body: TSch.RevokeIn):
    with ctx.tx() as c:
        sig = c.one("SELECT id::text AS id, subject_type, subject_id::text AS subject_id, signer_org_id::text AS signer_org_id"
                    " FROM signatures WHERE id = $1", ctx.path["signature_id"])
        if not sig or sig["signer_org_id"] != ctx.org_id:
            raise not_found("Assinatura")
        if c.scalar("SELECT 1 FROM signature_revocations WHERE signature_id = $1", sig["id"]):
            raise ApiError(409, "already_revoked", "Esta assinatura já foi revogada")
        c.run("INSERT INTO signature_revocations(signature_id, org_id, reason, revoked_by) VALUES ($1,$2,$3,$4)",
              sig["id"], ctx.org_id, body.reason, ctx.user_id)
        CUST.record(c, subject_type=sig["subject_type"], subject_id=sig["subject_id"], org_id=ctx.org_id,
                    event_type="signature_revoked", actor_user_id=ctx.user_id,
                    payload={"signature_id": sig["id"], "reason": body.reason})
        ctx.audit(c, "signature.revoked", "signature", sig["id"], {})
    return {"revoked": True, "signature_id": sig["id"],
            "note": "A assinatura continua no histórico, marcada como revogada — nada é apagado."}


# ================================================================================ integridade e custódia
@route("GET", "/v1/documents/{document_id}/integrity", min_role="viewer", tags=T,
       summary="Reconta o hash do arquivo guardado e compara com o hash registrado no upload")
def document_integrity(ctx: Ctx):
    with ctx.tx() as c:
        out = INTEG.check_document(c, ctx.app.storage, ctx.path["document_id"], actor_user_id=ctx.user_id)
    if not out["found"]:
        raise not_found("Documento")
    return out


@route("GET", "/v1/trust/custody", query=TSch.CustodyQ, min_role="viewer", tags=T,
       summary="Cadeia de custódia do objeto e conferência do encadeamento por hash")
def custody_chain(ctx: Ctx, q: TSch.CustodyQ):
    with ctx.tx(readonly=True) as c:
        chain = CUST.chain(c, q.subject_type, q.subject_id)
        check = CUST.verify(c, q.subject_type, q.subject_id)
    return {"items": chain, "integrity": check,
            "note": "O encadeamento (seq, prev_hash, event_hash) é calculado por gatilho no banco; a tabela é append-only."}


# ================================================================================ registro público verificável
@route("POST", "/v1/verifiable-records", body=TSch.VerifiableIn, min_role=WRITE, status=201,
       rate=("vrec_org", 120, 3600), tags=T,
       summary="Cria o registro público de verificação (código + QR) do documento, rascunho ou acordo")
def verifiable_create(ctx: Ctx, body: TSch.VerifiableIn):
    spec = {"document": ("documents", "sha256", "title", "version"),
            "draft": ("drafts", "content_sha256", "title", None),
            "agreement": ("signed_agreements", "content_sha256", "title", None)}[body.subject_type]
    table, hash_col, title_col, version_col = spec
    with ctx.tx() as c:
        cols = f"{hash_col} AS h, {title_col} AS t" + (f", {version_col} AS v" if version_col else ", 1 AS v")
        subj = c.one(f"SELECT id::text AS id, org_id::text AS org_id, {cols} FROM {table} WHERE id = $1", body.subject_id)
        if not subj or subj["org_id"] != ctx.org_id:
            raise not_found("Objeto")
        if body.subject_type == "agreement":
            st = c.scalar("SELECT status FROM signed_agreements WHERE id = $1", body.subject_id)
            if st == "draft":
                raise ApiError(409, "agreement_draft", "Publique o acordo para assinatura antes de gerar o código público")
        existing = c.scalar("SELECT code FROM verifiable_records WHERE subject_type = $1 AND subject_id = $2"
                            " AND content_sha256 = $3 AND status = 'active'", body.subject_type, body.subject_id, subj["h"])
    if existing:
        return {"code": existing, "reused": True, "verify_url": _verify_url(ctx, existing)}
    # O payload público é montado em contexto de SISTEMA de propósito: as assinaturas de um acordo pertencem a
    # organizações diferentes e a RLS esconderia as das outras partes, produzindo uma página pública incompleta.
    # O que entra no payload continua sendo só o curado por build_public_fields.
    with ctx.system_tx() as c:
        public = VR.build_public_fields(c, subject_type=body.subject_type, subject_id=body.subject_id, org_id=ctx.org_id,
                                        extra={"document": {"title": body.title or subj["t"], "version": subj["v"]}})
        out = VR.create(c, org_id=ctx.org_id, subject_type=body.subject_type, subject_id=body.subject_id,
                        title=(body.title or subj["t"] or "Documento")[:200], content_sha256=subj["h"],
                        subject_version=subj["v"] or 1, public_fields=public, created_by=ctx.user_id,
                        expires_at=body.expires_at.isoformat() if body.expires_at else None,
                        secret_key=ctx.settings.secret_key)
        # substitui o registro anterior do mesmo objeto (a versão antiga continua verificável, marcada como substituída)
        for prev in c.query("SELECT id::text AS id FROM verifiable_records WHERE subject_type = $1 AND subject_id = $2"
                            " AND id <> $3 AND status = 'active' AND org_id = $4",
                            body.subject_type, body.subject_id, out["id"], ctx.org_id):
            VR.supersede(c, old_record_id=prev["id"], new_record_id=out["id"], org_id=ctx.org_id, by=ctx.user_id)
    with ctx.tx() as c:
        ctx.audit(c, "verifiable.created", body.subject_type, body.subject_id, {"code": out["code"]})
    return {**out, "reused": False, "verify_url": _verify_url(ctx, out["code"]), "privacy_note": VR.PRIVACY_NOTE}


@route("GET", "/v1/verifiable-records", query=TSch.Pagination, min_role="viewer", tags=T,
       summary="Registros públicos de verificação da organização")
def verifiable_list(ctx: Ctx, q: TSch.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, code, subject_type, subject_id::text AS subject_id, title, status,"
                       " content_sha256, subject_version, issued_at, expires_at, revoked_at, revocation_reason,"
                       " access_count, last_accessed_at FROM verifiable_records WHERE org_id = $1"
                       " ORDER BY created_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    for r in rows[:q.limit]:
        r["verify_url"] = _verify_url(ctx, r["code"])
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/verifiable-records/{record_id}/revoke", body=TSch.RevokeIn, min_role=OWNER, tags=T,
       summary="Revoga o registro público (a página passa a dizer REVOGADO, com motivo e data)")
def verifiable_revoke(ctx: Ctx, body: TSch.RevokeIn):
    with ctx.tx() as c:
        out = VR.revoke(c, record_id=ctx.path["record_id"], org_id=ctx.org_id, reason=body.reason, by=ctx.user_id)
        if not out["found"]:
            raise not_found("Registro")
        ctx.audit(c, "verifiable.revoked", "verifiable_record", ctx.path["record_id"], {})
    return out


@route("GET", "/v1/verifiable-records/{record_id}/qr", min_role="viewer", raw=True, tags=T,
       summary="QR Code (SVG) que aponta para a página pública de verificação")
def verifiable_qr(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        code = c.scalar("SELECT code FROM verifiable_records WHERE id = $1", ctx.path["record_id"])
    if not code:
        raise not_found("Registro")
    svg = QR.svg(_verify_url(ctx, code))
    return Response(svg, media_type="image/svg+xml", headers={"Cache-Control": "private, max-age=300"})


# ================================================================================ VERIFICAÇÃO PÚBLICA (sem login)
@route("GET", "/v1/public/verify/{code}", auth="none", rate=("pubverify_ip", 120, 3600), tags=("public",),
       summary="Verificação pública: genuíno? qual versão foi assinada? integridade intacta? quem assinou? está revogado?")
def public_verify(ctx: Ctx):
    with ctx.system_tx() as c:
        out = VR.public_lookup(c, ctx.path["code"], storage=ctx.app.storage)
    if not out["found"]:
        raise ApiError(404, "not_found", "Não encontramos nenhum registro com este código. "
                                          "Confira os caracteres — o código tem o formato IMP-XXXX-XXXX-XXXX.")
    return out


@route("GET", "/v1/public/verify/{code}/qr", auth="none", rate=("pubverify_ip", 120, 3600), raw=True, tags=("public",),
       summary="QR Code (SVG) da página pública de verificação deste código")
def public_verify_qr(ctx: Ctx):
    code = CODES.normalize(ctx.path["code"])
    if not code:
        raise ApiError(422, "validation_error", "Código fora do formato IMP-XXXX-XXXX-XXXX")
    return Response(QR.svg(_verify_url(ctx, code)), media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=3600"})


# ================================================================================ carimbo de tempo
@route("POST", "/v1/verifiable-records/{record_id}/timestamp", min_role=WRITE, tags=T,
       summary="Aplica carimbo de tempo interno (RFC 3161 exige ACT contratada e não está disponível)")
def verifiable_timestamp(ctx: Ctx):
    with ctx.tx() as c:
        r = c.one("SELECT id::text AS id, content_sha256, subject_type, subject_id::text AS subject_id"
                  " FROM verifiable_records WHERE id = $1 AND org_id = $2", ctx.path["record_id"], ctx.org_id)
        if not r:
            raise not_found("Registro")
        out = TS.stamp_internal(c, record_id=r["id"], hashed_value=r["content_sha256"], secret_key=ctx.settings.secret_key,
                                subject_type=VR._custody_type(r["subject_type"]), subject_id=r["subject_id"], org_id=ctx.org_id)
        ctx.audit(c, "trust.timestamped", "verifiable_record", r["id"], {"kind": "internal"})
    return {**out, "rfc3161": TS.RFC3161_UNAVAILABLE}


# ================================================================================ acordos assinados
@route("POST", "/v1/signed-agreements", body=TSch.AgreementIn, min_role=WRITE, status=201, tags=("agreements",),
       summary="Cria um acordo em rascunho a partir de um documento do cofre (o hash do documento é congelado ao publicar)")
def agreement_create(ctx: Ctx, body: TSch.AgreementIn):
    with ctx.tx() as c:
        doc = c.one("SELECT sha256, status FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL",
                    body.document_id, ctx.org_id)
        if not doc:
            raise not_found("Documento")
        from ..services.documents import usable_statuses
        if doc["status"] not in usable_statuses():
            raise ApiError(409, "document_not_usable", "O documento está aguardando verificação antivírus ou foi recusado")
        # v0.27.0 — no acordo de FINANCIAMENTO os percentuais vêm do catálogo versionado (economic_rules), nunca do cliente.
        # Quem manda outro valor recebe 422: o preço é autoridade do servidor (ADR-342). Nos demais tipos de acordo a taxa
        # é cláusula livre entre as partes (serviço, parceria), como na v0.26.0.
        fee_bps, payer, mode, prop_bps, econ_version = body.platform_fee_bps, body.fee_payer_role, body.fee_mode, 0, None
        if body.kind == "funding":
            from ..trust import economy as ECO
            terms = ECO.economic_terms_for_funding(c)
            if body.platform_fee_bps is not None and body.platform_fee_bps != terms["platform_fee_bps"]:
                raise ApiError(422, "fee_determined_by_pricing_version",
                               "No acordo de financiamento a taxa de serviço vem da versão de preços vigente, não do pedido",
                               {"pricing_version": terms["pricing_version"], "platform_fee_bps": terms["platform_fee_bps"]})
            if body.fee_payer_role not in (None, terms["fee_payer_role"]):
                raise ApiError(422, "fee_payer_determined_by_pricing_version", "No acordo de financiamento quem paga a camada é o financiador")
            fee_bps, payer, mode = terms["platform_fee_bps"], terms["fee_payer_role"], body.fee_mode or terms["fee_mode"]
            prop_bps, econ_version = terms["proponent_participation_bps"], terms["pricing_version"]
        aid = c.scalar("INSERT INTO signed_agreements(org_id, project_id, kind, title, summary, document_id, content_sha256,"
                       " effective_from, effective_to, value_cents, created_by, platform_fee_bps, fee_payer_role,"
                       " fee_mode, review_days, calendar_type, auto_accept, dispute_days, proponent_participation_bps, economic_rule_version)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::date,$9::date,$10,$11,$12,$13,coalesce($14,'additional'),"
                       " coalesce($15,10),coalesce($16,'calendar'),coalesce($17,false),coalesce($18,5),$19,$20) RETURNING id::text",
                       ctx.org_id, body.project_id, body.kind, body.title, body.summary, body.document_id, doc["sha256"],
                       body.effective_from, body.effective_to, body.value_cents, ctx.user_id, fee_bps,
                       payer, mode, body.review_days, body.calendar_type, body.auto_accept, body.dispute_days, prop_bps, econ_version)
        c.run("INSERT INTO signed_agreement_parties(agreement_id, org_id, role, required, user_id)"
              " VALUES ($1,$2,$3,true,$4)", aid, ctx.org_id,
              "contractor" if body.kind in ("service", "funding") else "provider", ctx.user_id)
        ctx.audit(c, "agreement.created", "agreement", aid, {"kind": body.kind})
    return {"id": aid, "status": "draft", "next": "Acrescente as outras partes e envie para assinatura."}


@route("GET", "/v1/signed-agreements", query=TSch.Pagination, min_role="viewer", tags=("agreements",),
       summary="Acordos em que a organização é dona ou parte")
def agreement_list(ctx: Ctx, q: TSch.Pagination):
    with ctx.tx(readonly=True) as c:
        return page(AG.mine(c, ctx.org_id, limit=q.limit + 1, offset=q.offset), q.limit, q.offset)


@route("GET", "/v1/signed-agreements/{agreement_id}", min_role="viewer", tags=("agreements",),
       summary="Acordo com partes, estado das assinaturas e acompanhamento")
def agreement_detail(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        a = AG.detail(c, ctx.path["agreement_id"], viewer_org_id=ctx.org_id)
    if not a:
        raise not_found("Acordo")
    return a


@route("PATCH", "/v1/signed-agreements/{agreement_id}", body=TSch.AgreementPatch, min_role=WRITE, tags=("agreements",),
       summary="Altera um acordo ainda em rascunho (hash e documento são imutáveis)")
def agreement_patch(ctx: Ctx, body: TSch.AgreementPatch):
    fields = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    if not fields:
        raise ApiError(422, "validation_error", "Nada para alterar")
    with ctx.tx() as c:
        row = c.one("SELECT status, kind FROM signed_agreements WHERE id = $1 AND org_id = $2", ctx.path["agreement_id"], ctx.org_id)
        st = row["status"] if row else None
        if st is None:
            raise not_found("Acordo")
        if st != "draft":
            raise ApiError(409, "not_draft", "Somente um acordo em rascunho pode ser alterado")
        if row["kind"] == "funding" and any(k in fields for k in ("platform_fee_bps", "fee_payer_role")):
            raise ApiError(422, "fee_determined_by_pricing_version",
                           "No acordo de financiamento a taxa de serviço e quem a paga vêm da versão de preços, não do pedido")
        sets = ", ".join(f"{k} = ${i + 2}" for i, k in enumerate(fields))
        c.run(f"UPDATE signed_agreements SET {sets} WHERE id = $1", ctx.path["agreement_id"], *fields.values())
        ctx.audit(c, "agreement.updated", "agreement", ctx.path["agreement_id"], {"fields": sorted(fields)})
    return {"updated": True}


@route("POST", "/v1/signed-agreements/{agreement_id}/parties", body=TSch.PartyIn, min_role=WRITE, status=201,
       tags=("agreements",), summary="Acrescenta uma parte ao acordo em rascunho")
def agreement_add_party(ctx: Ctx, body: TSch.PartyIn):
    with ctx.tx() as c:
        st = c.scalar("SELECT status FROM signed_agreements WHERE id = $1 AND org_id = $2", ctx.path["agreement_id"], ctx.org_id)
        if st is None:
            raise not_found("Acordo")
        if st != "draft":
            raise ApiError(409, "not_draft", "As partes são definidas enquanto o acordo está em rascunho")
        if not c.scalar("SELECT 1 FROM organizations WHERE id = $1 AND status = 'active'", body.org_id):
            raise ApiError(422, "unknown_org", "Organização não encontrada")
        try:
            pid = c.scalar("INSERT INTO signed_agreement_parties(agreement_id, org_id, role, required, user_id)"
                           " VALUES ($1,$2,$3,$4,$5) RETURNING id::text",
                           ctx.path["agreement_id"], body.org_id, body.role, body.required, body.user_id)
        except Exception as exc:                                     # unicidade (organização + papel)
            if "signed_agreement_parties" in str(exc):
                raise ApiError(409, "duplicate_party", "Esta organização já é parte com este papel") from exc
            raise
        ctx.audit(c, "agreement.party_added", "agreement", ctx.path["agreement_id"], {"role": body.role})
    return {"id": pid}


@route("POST", "/v1/signed-agreements/{agreement_id}/publish", min_role=WRITE, tags=("agreements",),
       summary="Envia o acordo para assinatura (exige pelo menos duas partes obrigatórias)")
def agreement_publish(ctx: Ctx):
    with ctx.tx() as c:
        out = AG.publish(c, agreement_id=ctx.path["agreement_id"], org_id=ctx.org_id, actor_user_id=ctx.user_id)
        ctx.audit(c, "agreement.published", "agreement", ctx.path["agreement_id"], {})
    with ctx.system_tx() as c:
        from ..trust import contract_rules
        contract_rules.record_version(c, agreement_id=ctx.path["agreement_id"], actor_user_id=ctx.user_id)
    return out


@route("POST", "/v1/signed-agreements/{agreement_id}/sign", body=TSch.AgreementSignIn, min_role=OWNER,
       rate=("agrsign_ip", 30, 3600), tags=("agreements",),
       summary="Assina o acordo como parte (duas camadas: senha e código de uso único ligado ao hash)")
def agreement_sign(ctx: Ctx, body: TSch.AgreementSignIn):
    # Camada 1 pela implementação única (core/access.py). `always_password=True`: assinatura não
    # aceita o atalho da janela de reautenticação — ver a docstring de `verify_identity`.
    ACCESS.verify_identity(ctx, password=body.password,
                           mfa_code=getattr(body, "mfa_code", None),
                           stamp=False, always_password=True)
    with ctx.tx(readonly=True) as c:
        a = c.one("SELECT id::text AS id, status, content_sha256 FROM signed_agreements WHERE id = $1", ctx.path["agreement_id"])
        if not a:
            raise not_found("Acordo")
        party = AG.party_for(c, agreement_id=a["id"], org_id=ctx.org_id)
    if a["status"] != "awaiting_signatures":
        raise ApiError(409, "not_awaiting", "Este acordo não está aguardando assinaturas")
    if not party:
        raise ApiError(403, "not_a_party", "Sua organização não é parte deste acordo")
    if party["signed_at"]:
        raise ApiError(409, "already_signed", "Sua organização já assinou este acordo")
    if party["declined_at"]:
        raise ApiError(409, "already_declined", "Sua organização recusou este acordo")
    with ctx.system_tx() as c:
        chk = CH.consume(c, user_id=ctx.user_id, subject_type="agreement", subject_id=a["id"],
                         subject_sha256=a["content_sha256"], code=body.code)
    if not chk["ok"]:
        raise ApiError(401 if chk["reason"] in ("wrong_code", "no_challenge") else 409, f"challenge_{chk['reason']}",
                       CH.REASONS.get(chk["reason"], "Código de confirmação inválido"))
    with ctx.tx() as c:
        material = "|".join([a["id"], a["content_sha256"], ctx.user_id, ctx.org_id, party["role"], body.statement])
        mac = hmac_hex(ctx.settings.secret_key, material)
        sid = c.scalar("INSERT INTO signatures(subject_type, subject_id, subject_sha256, signer_user_id, signer_org_id,"
                       " role, method, statement, ip, user_agent, signature_hmac, challenge_id, agreement_party_id"
                       ", identity_level) VALUES ('document',$1,$2,$3,$4,$5,'platform_advanced',$6,$7,$8,$9,$10,$11,"
                       " identity_level($3)) RETURNING id::text",
                       a["id"], a["content_sha256"], ctx.user_id, ctx.org_id,
                       party["role"] if party["role"] in ("professional", "funder") else "legal_representative",
                       body.statement, ctx.ip, ctx.user_agent, mac, chk["challenge_id"], party["id"])
        CUST.record(c, subject_type="agreement", subject_id=a["id"], org_id=ctx.org_id, event_type="signed",
                    actor_user_id=ctx.user_id, content_sha256=a["content_sha256"],
                    payload={"role": party["role"], "signature_id": sid, "two_factor": True})
        ctx.audit(c, "agreement.signed", "agreement", a["id"], {"role": party["role"]})
    with ctx.system_tx() as c:
        AG.mark_signed(c, party_id=party["id"], signature_id=sid)
        status = AG.settle(c, agreement_id=a["id"], actor_user_id=ctx.user_id)
    return {"signature_id": sid, "agreement_status": status, "method": "platform_advanced",
            "legal_note": "Assinatura eletrônica avançada: reautenticação, código de uso único, hash da versão exata e "
                          "trilha encadeada. Para exigência de assinatura qualificada (ICP-Brasil/gov.br) use certificado "
                          "próprio — a plataforma não emite nem homologa assinatura qualificada."}


@route("POST", "/v1/signed-agreements/{agreement_id}/cancel", body=TSch.RevokeIn, min_role=OWNER, tags=("agreements",),
       summary="Cancela um acordo VIGENTE (dona ou financiador, motivo obrigatório): obrigações dispensadas, repasses não confirmados cancelados com estorno")
def agreement_cancel(ctx: Ctx, body: TSch.RevokeIn):
    from ..trust import contract_rules
    with ctx.system_tx() as c:
        out = contract_rules.cancel_active(c, agreement_id=ctx.path["agreement_id"], org_id=ctx.org_id, actor_user_id=ctx.user_id, reason=body.reason)
        ctx.audit(c, "agreement.cancelled", "agreement", ctx.path["agreement_id"], {"reason": body.reason[:200]})
    return out


@route("POST", "/v1/signed-agreements/{agreement_id}/decline", body=TSch.RevokeIn, min_role=OWNER, tags=("agreements",),
       summary="Recusa o acordo como parte (motivo obrigatório; o acordo é cancelado)")
def agreement_decline(ctx: Ctx, body: TSch.RevokeIn):
    with ctx.tx() as c:
        out = AG.decline(c, agreement_id=ctx.path["agreement_id"], org_id=ctx.org_id, reason=body.reason,
                         actor_user_id=ctx.user_id)
        ctx.audit(c, "agreement.declined", "agreement", ctx.path["agreement_id"], {})
    with ctx.system_tx() as c:
        status = AG.settle(c, agreement_id=ctx.path["agreement_id"])
    return {**out, "agreement_status": status}


@route("POST", "/v1/signed-agreements/{agreement_id}/milestones", body=TSch.MilestoneIn, min_role=WRITE, status=201,
       tags=("agreements",), summary="Acrescenta um marco ao acordo (com valor e ordem; o contrato deriva as obrigações dele)")
def agreement_milestone(ctx: Ctx, body: TSch.MilestoneIn):
    with ctx.tx() as c:
        st = c.scalar("SELECT status FROM signed_agreements WHERE id = $1", ctx.path["agreement_id"])
        if st is None:
            raise not_found("Acordo")
        if st in ("superseded", "canceled", "completed", "expired"):
            raise ApiError(409, "not_editable", f"Acordo {st}: não recebe marcos novos")
        mid = c.scalar("INSERT INTO signed_agreement_milestones(agreement_id, org_id, title, due_on, note, seq, amount_cents)"
                       " VALUES ($1,$2,$3,$4::date,$5,$6,$7) RETURNING id::text",
                       ctx.path["agreement_id"], ctx.org_id, body.title, body.due_on, body.note, body.seq, body.amount_cents)
        ctx.audit(c, "agreement.milestone_added", "agreement", ctx.path["agreement_id"], {"amount_cents": body.amount_cents})
    return {"id": mid}


@route("PATCH", "/v1/signed-agreements/{agreement_id}/milestones/{milestone_id}", body=TSch.MilestonePatch,
       min_role=WRITE, tags=("agreements",), summary="Reporta a entrega (quem executa) ou aceita/recusa (a outra parte): o grafo e os quatro olhos são do banco")
def agreement_milestone_patch(ctx: Ctx, body: TSch.MilestonePatch):
    from ..trust import contract_rules
    with ctx.tx() as c:
        out = contract_rules.report_milestone(c, agreement_id=ctx.path["agreement_id"], milestone_id=ctx.path["milestone_id"],
                                              org_id=ctx.org_id, user_id=ctx.user_id, status=body.status,
                                              document_id=body.document_id, note=body.note)
        ctx.audit(c, "agreement.milestone_updated", "agreement", ctx.path["agreement_id"], {"status": body.status})
        a = c.one("SELECT project_id::text AS project_id, org_id::text AS org_id FROM signed_agreements WHERE id = $1", ctx.path["agreement_id"])
    if a and a["project_id"] and body.status in ("delivered", "accepted", "rejected"):
        # O razão do projeto pertence à organização dona do acordo; a contraparte (financiador) que aceita
        # ou recusa o marco escreve nele via contexto de sistema, com o ator real registrado.
        from ..services.audit import ledger
        with ctx.system_tx() as c:
            ledger(c, project_id=a["project_id"], org_id=a["org_id"], actor=ctx.user_id, entry_type=f"milestone_{body.status}",
                   ref_type="agreement_milestone", ref_id=ctx.path["milestone_id"],
                   payload={"agreement_id": ctx.path["agreement_id"], "actor_org_id": ctx.org_id})
    if body.status == "accepted":
        # v0.27.0 — última entrega aceita com todos os repasses confirmados = operação quitada
        from ..trust import economy as ECO
        with ctx.system_tx() as c:
            out["operation_settled"] = ECO.settle_if_complete(c, agreement_id=ctx.path["agreement_id"], actor_user_id=ctx.user_id)
    return {"updated": True, **out}


@route("GET", "/v1/signed-agreements/{agreement_id}/allocation", min_role="viewer", tags=("agreements",),
       summary="Matriz de distribuição do acordo: bruto, projeto, taxa da plataforma (cobrável ou não, e por quê), terceiros")
def agreement_allocation(ctx: Ctx):
    from ..trust import contract_rules
    with ctx.tx(readonly=True) as c:
        if not c.scalar("SELECT 1 FROM signed_agreements WHERE id = $1", ctx.path["agreement_id"]):
            raise not_found("Acordo")
        gravada = contract_rules.allocation(c, ctx.path["agreement_id"])
        return {"recorded": gravada, "preview": None if gravada else contract_rules.preview(c, ctx.path["agreement_id"]),
                "non_custodial": ("A plataforma calcula, instrui e concilia; não recebe nem repassa valor de terceiros (ADR-284). "
                                  "A taxa da plataforma, quando cobrável, é cobrança própria ao pagador — nunca desconto em trânsito.")}


@route("POST", "/v1/signed-agreements/{agreement_id}/new-version", body=TSch.AgreementNewVersionIn, min_role=WRITE, status=201,
       tags=("agreements",), summary="Abre a versão seguinte do acordo (rascunho); a anterior fica substituída e suas assinaturas deixam de aprovar")
def agreement_new_version(ctx: Ctx, body: TSch.AgreementNewVersionIn):
    from ..trust import contract_rules
    with ctx.tx() as c:
        doc = c.one("SELECT sha256, status FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", body.document_id, ctx.org_id)
        if not doc:
            raise not_found("Documento")
        from ..services.documents import usable_statuses
        if doc["status"] not in usable_statuses():
            raise ApiError(409, "document_not_usable", "O documento está aguardando verificação antivírus ou foi recusado")
        changes = body.model_dump(exclude_unset=True, exclude={"document_id", "reason"})
    with ctx.system_tx() as c:
        out = contract_rules.new_version(c, agreement_id=ctx.path["agreement_id"], org_id=ctx.org_id, actor_user_id=ctx.user_id,
                                         document_id=body.document_id, document_sha256=doc["sha256"], reason=body.reason, changes=changes)
    with ctx.tx() as c:
        ctx.audit(c, "agreement.new_version", "agreement", ctx.path["agreement_id"], {"new_id": out["id"], "version": out["version"]})
    return out


@route("GET", "/v1/agreements/pending", min_role="viewer", tags=("agreements",),
       summary="O que espera decisão desta organização nos acordos vigentes (entregar, aceitar, pagar)")
def agreements_pending(ctx: Ctx):
    from ..trust import contract_rules
    with ctx.tx(readonly=True) as c:
        return {"items": contract_rules.pending_for(c, ctx.org_id)}


# ================================================================================ v0.27.0 — camada econômica
def _flush_ledger(ctx: Ctx, out: dict) -> dict:
    """O razão do projeto é da executora; a contraparte (financiador, proponente, plataforma) escreve nele em
    contexto de sistema, com o ator real no lançamento — o mesmo desenho do aceite de marco (v0.26.0)."""
    entries = out.pop("_ledger", None) or []
    if entries:
        from ..services.audit import ledger
        with ctx.system_tx() as c:
            for e in entries:
                ledger(c, **e)
    return out

@route("PUT", "/v1/signed-agreements/{agreement_id}/parties/{party_id}/pix", body=TSch.PartyPixIn, min_role=WRITE, tags=("agreements",),
       summary="A própria parte informa a chave PIX que receberá os repasses deste acordo (formato conferido pelo banco)")
def party_set_pix(ctx: Ctx, body: TSch.PartyPixIn):
    from ..trust import economy as ECO
    with ctx.tx() as c:
        out = ECO.set_party_pix(c, agreement_id=ctx.path["agreement_id"], party_id=ctx.path["party_id"], org_id=ctx.org_id,
                                user_id=ctx.user_id, pix_key=body.pix_key, pix_key_type=body.pix_key_type)
        ctx.audit(c, "agreement.party_pix_set", "agreement", ctx.path["agreement_id"], {"party_id": ctx.path["party_id"], "type": body.pix_key_type})
    return out


@route("GET", "/v1/signed-agreements/{agreement_id}/payouts", min_role="viewer", tags=("agreements",),
       summary="Instruções de repasse da matriz: quem paga a quem, quanto, por qual chave, e o estado (instruída → pendente → confirmada → conciliada)")
def agreement_payouts(ctx: Ctx):
    from ..trust import economy as ECO
    with ctx.tx(readonly=True) as c:
        if not c.scalar("SELECT 1 FROM signed_agreements WHERE id = $1", ctx.path["agreement_id"]):
            raise not_found("Acordo")
        return {"items": ECO.payouts(c, ctx.path["agreement_id"], viewer_org_id=ctx.org_id),
                "settlement": ECO.settlement(c, ctx.path["agreement_id"]),
                "note": "A plataforma não move dinheiro: quem paga transfere pela chave informada no contrato e registra; quem recebe confirma."}


@route("GET", "/v1/signed-agreements/{agreement_id}/value", min_role="viewer", tags=("agreements",),
       summary="O que o IMPACTO fez nesta operação — por registro, não por slogan (base do Value Capture)")
def agreement_value(ctx: Ctx):
    from ..trust import economy as ECO
    with ctx.tx(readonly=True) as c:
        if not c.scalar("SELECT 1 FROM signed_agreements WHERE id = $1", ctx.path["agreement_id"]):
            raise not_found("Acordo")
        return ECO.explain_value(c, ctx.path["agreement_id"])


@route("POST", "/v1/payouts/{payout_id}/transfers", body=TSch.TransferIn, min_role=WRITE, status=201, tags=("agreements",),
       summary="Quem paga registra uma transferência feita (a qualquer momento, inclusive parcial); a mesma referência é idempotente")
def payout_register_transfer(ctx: Ctx, body: TSch.TransferIn):
    from ..trust import economy as ECO
    with ctx.tx() as c:
        out = ECO.register_transfer(c, payout_id=ctx.path["payout_id"], org_id=ctx.org_id, user_id=ctx.user_id,
                                    amount_cents=body.amount_cents, reference=body.reference, paid_on=body.paid_on,
                                    method=body.method, evidence_document_id=body.evidence_document_id)
        ctx.audit(c, "payout.transfer_registered", "payout", ctx.path["payout_id"], {"amount_cents": body.amount_cents, "duplicate": out["duplicate"]})
    if not out["duplicate"] and out.get("recipient_org_id"):
        from ..network import notify as NOTIFY
        with ctx.system_tx() as c:
            NOTIFY.org_event(c, org_id=out["recipient_org_id"], event="Payout.registered", title="Transferência registrada por quem paga",
                             body="Quem financia registrou uma transferência para você. Confirme o recebimento quando o valor chegar.",
                             link=f"/acordos/{out['agreement_id']}", actor_user_id=ctx.user_id, ref_type="payout", ref_id=ctx.path["payout_id"],
                             dedupe_parts=("Payout.registered", out["id"]))
    out.pop("recipient_org_id", None)
    out.pop("agreement_id", None)
    return _flush_ledger(ctx, out)


@route("POST", "/v1/payout-transfers/{transfer_id}/confirm", min_role=WRITE, tags=("agreements",),
       summary="Quem RECEBE confirma o recebimento; com o valor inteiro confirmado o repasse fica confirmado e o evento econômico nasce")
def transfer_confirm(ctx: Ctx):
    from ..trust import economy as ECO
    with ctx.tx() as c:
        out = ECO.confirm_transfer(c, transfer_id=ctx.path["transfer_id"], org_id=ctx.org_id, user_id=ctx.user_id)
        ctx.audit(c, "payout.transfer_confirmed", "payout_transfer", ctx.path["transfer_id"], {"payout_state": out["payout_state"]})
    _flush_ledger(ctx, out)
    # quitação: avaliada em contexto de sistema (lê marcos e repasses de todas as partes; escreve reconhecimentos)
    with ctx.system_tx() as c:
        out["operation_settled"] = ECO.after_confirm(c, payout_id=out.pop("payout_id"), actor_user_id=ctx.user_id)
        from ..network import notify as NOTIFY
        if out.get("payer_org_id") and out["payout_state"] == "confirmed":
            NOTIFY.org_event(c, org_id=out["payer_org_id"], event="Payout.confirmed", title="Repasse confirmado por quem recebe",
                             body="O destinatário confirmou o recebimento integral do repasse.", link=f"/acordos/{out['agreement_id']}",
                             actor_user_id=ctx.user_id, ref_type="payout_transfer", ref_id=ctx.path["transfer_id"],
                             dedupe_parts=("Payout.confirmed", ctx.path["transfer_id"]))
        if out["operation_settled"] and out.get("owner_org_id"):
            NOTIFY.org_event(c, org_id=out["owner_org_id"], event="Operation.settled", title="Operação concluída e quitada",
                             body="Todas as entregas foram aceitas e todos os repasses devidos confirmados. O reconhecimento foi registrado na trajetória.",
                             link=f"/acordos/{out['agreement_id']}", actor_user_id=ctx.user_id, ref_type="agreement", ref_id=out["agreement_id"],
                             dedupe_parts=("Operation.settled", out["agreement_id"]))
    for k in ("agreement_id", "payer_org_id", "owner_org_id"):
        out.pop(k, None)
    return out


@route("POST", "/v1/payout-transfers/{transfer_id}/reject", body=TSch.RevokeIn, min_role=WRITE, tags=("agreements",),
       summary="Quem recebe recusa uma transferência registrada (não chegou, valor errado): o repasse fica em disputa")
def transfer_reject(ctx: Ctx, body: TSch.RevokeIn):
    from ..trust import economy as ECO
    with ctx.tx() as c:
        out = ECO.reject_transfer(c, transfer_id=ctx.path["transfer_id"], org_id=ctx.org_id, user_id=ctx.user_id, reason=body.reason)
        ctx.audit(c, "payout.transfer_rejected", "payout_transfer", ctx.path["transfer_id"], {})
    return out


@route("POST", "/v1/payouts/{payout_id}/reconcile", body=TSch.RevokeIn, min_role=WRITE, tags=("agreements",),
       summary="Quem recebe concilia o repasse confirmado com o extrato (nota obrigatória)")
def payout_reconcile(ctx: Ctx, body: TSch.RevokeIn):
    from ..trust import economy as ECO
    with ctx.tx() as c:
        out = ECO.reconcile_payout(c, payout_id=ctx.path["payout_id"], org_id=ctx.org_id, user_id=ctx.user_id, note=body.reason)
        ctx.audit(c, "payout.reconciled", "payout", ctx.path["payout_id"], {})
    return _flush_ledger(ctx, out)


@route("POST", "/v1/admin/payout-transfers/{transfer_id}/confirm", auth="admin", permission="billing.write", tags=("agreements",),
       summary="Equipe financeira da plataforma confirma o recebimento da linha 'infraestrutura e inteligência'")
def admin_transfer_confirm(ctx: Ctx):
    from ..trust import economy as ECO
    with ctx.system_tx() as c:
        out = ECO.confirm_transfer(c, transfer_id=ctx.path["transfer_id"], org_id=ctx.org_id, user_id=ctx.user_id, platform_staff=True)
        ctx.audit(c, "payout.transfer_confirmed", "payout_transfer", ctx.path["transfer_id"], {"by": "platform"})
        out["operation_settled"] = ECO.after_confirm(c, payout_id=out.pop("payout_id"), actor_user_id=ctx.user_id)
    out.pop("agreement_id", None)
    return _flush_ledger(ctx, out)


@route("POST", "/v1/admin/payouts/{payout_id}/reconcile", body=TSch.RevokeIn, auth="admin", permission="billing.write", tags=("agreements",),
       summary="Equipe financeira concilia a linha da plataforma")
def admin_payout_reconcile(ctx: Ctx, body: TSch.RevokeIn):
    from ..trust import economy as ECO
    with ctx.system_tx() as c:
        out = ECO.reconcile_payout(c, payout_id=ctx.path["payout_id"], org_id=ctx.org_id, user_id=ctx.user_id, note=body.reason, platform_staff=True)
        ctx.audit(c, "payout.reconciled", "payout", ctx.path["payout_id"], {"by": "platform"})
    return _flush_ledger(ctx, out)


# ---------------------------------------------------------------- participação de autoria
@route("POST", "/v1/projects/{project_id}/participations", body=TSch.ParticipationIn, kinds=("osc",), min_role=WRITE, status=201,
       tags=("participations",), summary="A executora propõe participação de autoria/desenvolvimento da ideia a quem a propôs; só vale com o aceite do proponente")
def participation_propose(ctx: Ctx, body: TSch.ParticipationIn):
    from ..trust import economy as ECO
    with ctx.tx() as c:
        out = ECO.propose_participation(c, project_id=ctx.path["project_id"], org_id=ctx.org_id, actor_user_id=ctx.user_id,
                                        proponent_org_id=body.proponent_org_id, proponent_user_id=body.proponent_user_id,
                                        idea_ref_type=body.idea_ref_type, idea_ref_id=body.idea_ref_id,
                                        authorship_type=body.authorship_type, share_bps=body.share_bps, contribution=body.contribution)
        ctx.audit(c, "participation.proposed", "participation", out["id"], {"proponent_org_id": body.proponent_org_id})
        from ..network import notify as NOTIFY
        NOTIFY.org_event(c, org_id=body.proponent_org_id, event="Participation.proposed",
                         title="Participação de autoria proposta", body="Uma executora propôs sua participação de autoria num projeto. Aceite ou recuse.",
                         link="/participacoes", actor_user_id=ctx.user_id)
    return out


@route("GET", "/v1/participations", min_role="viewer", tags=("participations",),
       summary="Participações de autoria em que a organização é executora ou proponente")
def participations_mine(ctx: Ctx):
    from ..trust import economy as ECO
    with ctx.tx(readonly=True) as c:
        return {"items": ECO.mine(c, ctx.org_id)}


@route("GET", "/v1/participations/{participation_id}", min_role="viewer", tags=("participations",), summary="Detalhe da participação")
def participation_get(ctx: Ctx):
    from ..trust import economy as ECO
    with ctx.tx(readonly=True) as c:
        return ECO.participation(c, ctx.path["participation_id"])


@route("POST", "/v1/participations/{participation_id}/accept", min_role=OWNER, tags=("participations",),
       summary="O proponente aceita a participação (confirma a autoria e o combinado)")
def participation_accept(ctx: Ctx):
    from ..trust import economy as ECO
    with ctx.tx() as c:
        out = ECO.accept_participation(c, participation_id=ctx.path["participation_id"], org_id=ctx.org_id, user_id=ctx.user_id)
        ctx.audit(c, "participation.accepted", "participation", ctx.path["participation_id"], {"status": out["status"]})
    # o razão é do projeto da executora; o proponente escreve nele via contexto de sistema, com o ator real registrado
    from ..services.audit import ledger
    with ctx.system_tx() as c:
        ledger(c, project_id=out["project_id"], org_id=out["org_id"], actor=ctx.user_id, entry_type="participation_accepted",
               ref_type="participation", ref_id=ctx.path["participation_id"], payload={"proponent_org_id": ctx.org_id, "status": out["status"]})
        from ..network import notify as NOTIFY
        NOTIFY.org_event(c, org_id=out["org_id"], event="Participation.accepted", title="Participação de autoria aceita",
                         body="O proponente aceitou a participação de autoria. Ela entra na matriz do acordo de financiamento quando houver um em vigor.",
                         link="/participacoes", actor_user_id=ctx.user_id, ref_type="participation", ref_id=ctx.path["participation_id"])
    return {"id": out["id"], "status": out["status"]}


@route("POST", "/v1/participations/{participation_id}/cancel", body=TSch.RevokeIn, min_role=OWNER, tags=("participations",),
       summary="Executora ou proponente cancela a participação (motivo obrigatório)")
def participation_cancel(ctx: Ctx, body: TSch.RevokeIn):
    from ..trust import economy as ECO
    with ctx.tx() as c:
        out = ECO.cancel_participation(c, participation_id=ctx.path["participation_id"], org_id=ctx.org_id, user_id=ctx.user_id, reason=body.reason)
        ctx.audit(c, "participation.cancelled", "participation", ctx.path["participation_id"], {})
    return out


@route("GET", "/v1/economic-rules", min_role="viewer", tags=("participations",),
       summary="Catálogo versionado da camada econômica (percentuais por versão de preços) — o que o contrato congela")
def economic_rules(ctx: Ctx):
    from ..services.monetization import pricing_version_name
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT key, pricing_version, label_pt, applies_to, bps, payer_role, recipient_kind, monetization_rule_key,"
                       " effective_from, effective_until, what_it_pays_for, reason FROM economic_rules ORDER BY pricing_version DESC, key")
    return {"items": rows, "current_pricing_version": pricing_version_name(),
            "note": "Percentual é do contrato por versão de preços; a cobrança da plataforma só existe com a regra jurídica ativa. "
                    "A participação de autoria não é receita da plataforma."}
