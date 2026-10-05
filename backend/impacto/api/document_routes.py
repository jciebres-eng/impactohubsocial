"""Documentos (cofre privado), rascunhos assistidos, validação por profissional habilitado e assinaturas eletrônicas."""
from __future__ import annotations

import hashlib
from datetime import date, UTC
from typing import Literal

from starlette.responses import Response

from ..http import ApiError, Ctx, not_found, page, route
from ..security import passwords
from ..security.tokens import hmac_hex, sign_payload, verify_payload
from ..services import documents as docsvc
from ..services.audit import ledger
from ..services.entitlements import check_limit
from ..services.validators import safe_filename
from . import schemas as S

T = ("documents",)
DOC_COLS = ("d.id::text AS id, d.org_id::text AS org_id, d.project_id::text AS project_id, d.application_id::text AS application_id,"
            " d.doc_type, d.title, d.filename, d.mime_type, d.size_bytes, d.sha256, d.status, d.valid_until, d.visibility, d.version,"
            " d.origin, d.created_at, d.scanned_at, d.validation_status, d.validated_at, d.validation_note, d.issued_on, d.origin_source")


def with_state(d: dict) -> dict:
    """Acrescenta o estado documental (AUSENTE/EXPIRADO/PENDENTE DE VALIDAÇÃO/VALIDADO/REJEITADO) — antivírus ≠ validação humana."""
    from datetime import date as _d
    from ..engines.institutional.common import DOC_STATE_LABELS
    from ..engines.institutional.documents import doc_state
    ok = set(docsvc.usable_statuses())
    st = doc_state({"scan_status": "clean" if d.get("status") in ok else d.get("status"), "validation_status": d.get("validation_status"),
                    "valid_until": d.get("valid_until")}, _d.today())
    d["state"], d["state_label"] = st, DOC_STATE_LABELS[st]
    return d


class DocListQ(S.Pagination):
    project_id: S.Uuid | None = None
    doc_type: str | None = None


@route("GET", "/v1/documents", query=DocListQ, min_role="viewer", tags=T, summary="Documentos da organização (com validade)")
def list_docs(ctx: Ctx, q: DocListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {DOC_COLS}, (d.valid_until IS NOT NULL AND d.valid_until < current_date) AS expired,"
                       " (d.valid_until IS NOT NULL AND d.valid_until BETWEEN current_date AND current_date + 30) AS expiring_soon"
                       " FROM documents d WHERE d.org_id = $1 AND d.deleted_at IS NULL AND ($2::uuid IS NULL OR d.project_id = $2::uuid)"
                       " AND ($3::text IS NULL OR d.doc_type = $3) ORDER BY d.created_at DESC LIMIT $4 OFFSET $5",
                       ctx.org_id, q.project_id, q.doc_type, q.limit + 1, q.offset)
    return page([with_state(r) for r in rows], q.limit, q.offset)


@route("POST", "/v1/documents", multipart=True, min_role="member", status=201, rate=("upload_ip", 120, 3600), tags=T,
       summary="Upload seguro (multipart: file, doc_type, title, project_id?, application_id?, valid_until?, visibility?)")
def upload(ctx: Ctx, form):
    f = form.get("file")
    if f is None or not hasattr(f, "read"):
        raise ApiError(422, "file_required", "Envie o arquivo no campo 'file'")
    doc_type = str(form.get("doc_type") or "outro").strip()
    title = str(form.get("title") or "").strip()[:200]
    project_id = str(form.get("project_id") or "").strip() or None
    application_id = str(form.get("application_id") or "").strip() or None
    visibility = str(form.get("visibility") or "private").strip()
    vu = str(form.get("valid_until") or "").strip() or None
    import re as _re
    if not _re.fullmatch(r"[a-z0-9_]{2,60}", doc_type):
        raise ApiError(422, "validation_error", "doc_type inválido")
    if visibility not in ("private", "parties", "public") or (visibility == "public" and ctx.principal.org_kind not in ("government", "platform")):
        raise ApiError(422, "validation_error", "Visibilidade inválida para este tipo de organização")
    try:
        valid_until = date.fromisoformat(vu) if vu else None
        iss = str(form.get("issued_on") or "").strip() or None
        issued_on = date.fromisoformat(iss) if iss else None
    except ValueError:
        raise ApiError(422, "validation_error", "valid_until e issued_on devem ser AAAA-MM-DD") from None
    origin_source = (str(form.get("origin_source") or "").strip()[:200]) or None
    data = f.file.read(ctx.settings.max_upload_bytes + 1)
    if len(data) > ctx.settings.max_upload_bytes:
        raise ApiError(413, "payload_too_large", f"Arquivo excede {ctx.settings.max_upload_bytes // 1048576} MB")
    filename = safe_filename(f.filename or "arquivo")
    mime = docsvc.sniff(filename, data)
    digest = hashlib.sha256(data).hexdigest()
    with ctx.tx() as c:
        used = c.scalar("SELECT coalesce(sum(size_bytes),0) FROM documents WHERE org_id = $1 AND deleted_at IS NULL", ctx.org_id)
        check_limit(c, ctx, "storage_mb", int((used + len(data)) / 1048576))
        for tbl, val in (("projects", project_id), ("applications", application_id)):
            if val:
                col = "org_id" if tbl == "projects" else "osc_org_id"
                if not c.one(f"SELECT 1 FROM {tbl} WHERE id = $1 AND {col} = $2", val, ctx.org_id):
                    raise not_found("Projeto/candidatura")
    status, scan_note = ctx.app.antivirus.scan(data)
    key = docsvc.new_storage_key(ctx.org_id)
    if status == "infected":
        with ctx.tx() as c:
            ctx.audit(c, "document.rejected_malware", "document", None, {"sha256": digest, "engine": ctx.app.antivirus.name})
        raise ApiError(422, "malware_detected", "Arquivo bloqueado pelo antivírus")
    ctx.app.storage.put(key, data, mime)
    text = docsvc.extract_text(mime, data)
    try:
        with ctx.tx() as c:
            did = c.scalar("INSERT INTO documents(org_id, project_id, application_id, doc_type, title, filename, mime_type, size_bytes, sha256,"
                           " storage_key, status, scan_engine, scanned_at, valid_until, visibility, extracted_text, uploaded_by, issued_on, origin_source)"
                           " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::bigint,$9,$10,$11,$12, CASE WHEN $11 = 'clean' THEN now() END, $13::date,$14,$15,$16,$17::date,$18)"
                           " RETURNING id::text", ctx.org_id, project_id, application_id, doc_type, title or filename, filename, mime, len(data),
                           digest, key, status, ctx.app.antivirus.name, valid_until, visibility, text, ctx.user_id, issued_on, origin_source)
            if application_id:
                c.run("UPDATE application_steps SET status = 'done', document_id = $3, completed_at = now(), completed_by = $4"
                      " WHERE application_id = $1 AND code = $2 AND status <> 'done'", application_id, f"doc_{doc_type}", did, ctx.user_id)
            ctx.audit(c, "document.uploaded", "document", did, {"sha256": digest, "size": len(data), "doc_type": doc_type, "scan": status})
    except Exception:
        ctx.app.storage.delete(key)
        raise
    out = {"id": did, "sha256": digest, "status": status, "mime_type": mime}
    if status == "pending_scan":
        out["notice"] = "Antivírus não configurado: arquivo em quarentena até verificação" if ctx.settings.is_hardened else \
            "Antivírus não configurado (ambiente de desenvolvimento)"
    if text and ctx.app.ai.provider_name != "disabled":
        from ..engines.ai.local import classify_document
        out["suggestion"] = classify_document(text[:20000], filename)
    return out


@route("PATCH", "/v1/documents/{document_id}", body=S.DocPatch, min_role="member", tags=T)
def patch_doc(ctx: Ctx, body: S.DocPatch):
    data = body.model_dump(exclude_unset=True)
    if data.get("visibility") == "public" and ctx.principal.org_kind not in ("government", "platform"):
        raise ApiError(422, "validation_error", "Somente órgãos públicos publicam documentos abertos")
    with ctx.tx() as c:
        n = c.run("UPDATE documents SET title = coalesce($3, title), valid_until = CASE WHEN $5::bool THEN $4::date ELSE valid_until END,"
                  " visibility = coalesce($6, visibility) WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL",
                  ctx.path["document_id"], ctx.org_id, data.get("title"), data.get("valid_until"), "valid_until" in data, data.get("visibility"))
        if not n:
            raise not_found("Documento")
        ctx.audit(c, "document.updated", "document", ctx.path["document_id"], {"fields": sorted(data)})
    return {"id": ctx.path["document_id"]}


@route("DELETE", "/v1/documents/{document_id}", min_role="admin", tags=T, summary="Exclusão lógica (preserva trilha; conteúdo removido do storage)")
def delete_doc(ctx: Ctx):
    with ctx.tx() as c:
        d = c.one("SELECT storage_key FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", ctx.path["document_id"], ctx.org_id)
        if not d:
            raise not_found("Documento")
        if c.scalar("SELECT count(*) FROM signatures WHERE subject_type = 'document' AND subject_id = $1", ctx.path["document_id"]):
            raise ApiError(409, "signed_document", "Documento assinado não pode ser excluído (prova de integridade)")
        c.run("UPDATE documents SET deleted_at = now(), extracted_text = NULL WHERE id = $1", ctx.path["document_id"])
        ctx.audit(c, "document.deleted", "document", ctx.path["document_id"])
    ctx.app.storage.delete(d["storage_key"])
    return None


@route("GET", "/v1/documents/{document_id}", min_role="viewer", tags=T)
def get_doc(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        d = c.one(f"SELECT {DOC_COLS} FROM documents d WHERE d.id = $1 AND d.deleted_at IS NULL", ctx.path["document_id"])
        if not d:
            raise not_found("Documento")
        with_state(d)
        d["signatures"] = c.query("SELECT s.id::text AS id, s.role, s.signed_at, s.subject_sha256 = $2 AS matches_current, user_display_name(s.signer_user_id) AS signer,"
                                  " s.credential_id IS NOT NULL AS with_credential FROM signatures s"
                                  " WHERE s.subject_type = 'document' AND s.subject_id = $1 ORDER BY s.signed_at", d["id"], d["sha256"])
    return d


@route("POST", "/v1/documents/{document_id}/download-url", min_role="viewer", tags=T,
       summary="Gera URL temporária (5 min) para download — somente após autorização e verificação antivírus")
def download_url(ctx: Ctx):
    with ctx.tx() as c:
        d = c.one("SELECT id::text AS id, filename, status, storage_key, org_id::text AS org_id FROM documents WHERE id = $1 AND deleted_at IS NULL",
                  ctx.path["document_id"])
        if not d:
            raise not_found("Documento")
        if d["status"] in ("infected", "rejected"):
            raise ApiError(409, "blocked_file", "Arquivo bloqueado")
        if d["status"] == "pending_scan" and not ctx.settings.allow_unscanned_downloads:
            raise ApiError(409, "pending_scan", "Arquivo aguardando verificação antivírus")
        ctx.audit(c, "document.download_url_issued", "document", d["id"], {"owner_org": d["org_id"]})
    ttl = 300
    url = ctx.app.storage.presigned_get(d["storage_key"], d["filename"], ttl)
    if not url:
        token = sign_payload(ctx.settings.secret_key, {"d": d["id"], "u": ctx.user_id, "k": d["storage_key"]}, ttl)
        url = f"/v1/files/{token}"
    return {"url": url, "expires_in": ttl}


@route("GET", "/v1/files/{token}", auth="none", raw=True, rate=("files_ip", 600, 3600), tags=T,
       summary="Entrega do arquivo via token assinado e de curta duração (storage local)")
def serve_file(ctx: Ctx):
    body = verify_payload(ctx.settings.secret_key, ctx.path["token"])
    if not body:
        raise ApiError(403, "invalid_or_expired", "Link inválido ou expirado")
    from ..db.pool import DbContext
    with ctx.pool.tx(DbContext(system=True), readonly=True) as c:
        d = c.one("SELECT filename, mime_type, storage_key, deleted_at FROM documents WHERE id = $1", body["d"])
    if not d or d["deleted_at"] or d["storage_key"] != body["k"]:
        raise not_found("Arquivo")
    data = ctx.app.storage.get(d["storage_key"])
    fname = d["filename"].encode("ascii", "ignore").decode() or "arquivo"
    return Response(data, media_type=d["mime_type"], headers={
        "Content-Disposition": f'attachment; filename="{fname}"', "Cache-Control": "private, no-store",
        "Content-Security-Policy": "sandbox; default-src 'none'", "X-Content-Type-Options": "nosniff"})


# ------------------------------------------------------------------------------------------------ rascunhos
@route("GET", "/v1/drafts", query=S.Pagination, min_role="viewer", tags=("drafts",))
def list_drafts(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, kind, title, version, status, ai_assisted, project_id::text AS project_id,"
                       " application_id::text AS application_id, content_sha256, updated_at FROM drafts WHERE org_id = $1"
                       " ORDER BY updated_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/drafts", body=S.DraftIn, min_role="member", status=201, tags=("drafts",),
       summary="Cria rascunho (proposta, plano de trabalho, relatório...) — pode vir da assistência de IA")
def create_draft(ctx: Ctx, body: S.DraftIn):
    with ctx.tx() as c:
        if body.project_id and not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", body.project_id, ctx.org_id):
            raise not_found("Projeto")
        if body.application_id and not c.one("SELECT 1 FROM applications WHERE id = $1 AND osc_org_id = $2", body.application_id, ctx.org_id):
            raise not_found("Candidatura")
        did = c.scalar("INSERT INTO drafts(org_id, project_id, application_id, kind, title, content, content_sha256, ai_assisted, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::bool,$9) RETURNING id::text", ctx.org_id, body.project_id, body.application_id,
                       body.kind, body.title, body.content, hashlib.sha256(body.content.encode()).hexdigest(), body.ai_assisted, ctx.user_id)
        ctx.audit(c, "draft.created", "draft", did, {"kind": body.kind, "ai_assisted": body.ai_assisted})
    return {"id": did}


@route("GET", "/v1/drafts/{draft_id}", min_role="viewer", tags=("drafts",), summary="Rascunho (OSC dona ou profissional revisor)")
def get_draft(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        d = c.one("SELECT id::text AS id, org_id::text AS org_id, kind, title, content, content_sha256, version, status, ai_assisted,"
                  " project_id::text AS project_id, application_id::text AS application_id, created_at, updated_at FROM drafts WHERE id = $1",
                  ctx.path["draft_id"])
        if not d:
            raise not_found("Rascunho")
        d["signatures"] = c.query("SELECT s.role, s.signed_at, s.subject_sha256 = $2 AS matches_current, user_display_name(s.signer_user_id) AS signer,"
                                  " s.credential_id IS NOT NULL AS with_credential FROM signatures s WHERE s.subject_type = 'draft' AND s.subject_id = $1"
                                  " ORDER BY s.signed_at", d["id"], d["content_sha256"])
        d["reviews"] = c.query("SELECT r.id::text AS id, r.status, r.response_note, o.legal_name AS professional FROM professional_reviews r"
                               " JOIN organizations o ON o.id = r.professional_org_id WHERE r.subject_type = 'draft' AND r.subject_id = $1", d["id"])
    return d


@route("PATCH", "/v1/drafts/{draft_id}", body=S.DraftPatch, min_role="member", tags=("drafts",))
def patch_draft(ctx: Ctx, body: S.DraftPatch):
    with ctx.tx() as c:
        d = c.one("SELECT id, status, content FROM drafts WHERE id = $1 AND org_id = $2 FOR UPDATE", ctx.path["draft_id"], ctx.org_id)
        if not d:
            raise not_found("Rascunho")
        if d["status"] in ("approved", "signed", "superseded"):
            raise ApiError(409, "immutable_version", "Versão aprovada/assinada é imutável. Crie uma nova versão.")
        content = body.content if body.content is not None else d["content"]
        c.run("UPDATE drafts SET title = coalesce($2, title), content = $3, content_sha256 = $4, status = 'draft' WHERE id = $1",
              d["id"], body.title, content, hashlib.sha256(content.encode()).hexdigest())
        if body.content is not None and content != d["content"]:
            c.run("UPDATE professional_reviews SET status = 'cancelled', response_note = 'Conteúdo alterado após solicitação'"
                  " WHERE subject_type = 'draft' AND subject_id = $1 AND status IN ('requested','accepted')", d["id"])
    return {"id": ctx.path["draft_id"]}


@route("POST", "/v1/drafts/{draft_id}/new-version", min_role="member", status=201, tags=("drafts",))
def new_version(ctx: Ctx):
    with ctx.tx() as c:
        d = c.one("SELECT * FROM drafts WHERE id = $1 AND org_id = $2", ctx.path["draft_id"], ctx.org_id)
        if not d:
            raise not_found("Rascunho")
        nid = c.scalar("INSERT INTO drafts(org_id, project_id, application_id, kind, title, content, content_sha256, version, ai_assisted, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8::int,$9,$10) RETURNING id::text", ctx.org_id, d["project_id"], d["application_id"],
                       d["kind"], d["title"], d["content"], d["content_sha256"], d["version"] + 1, d["ai_assisted"], ctx.user_id)
        c.run("UPDATE drafts SET status = 'superseded' WHERE id = $1 AND status NOT IN ('signed','approved')", d["id"])
    return {"id": nid, "version": d["version"] + 1}


@route("POST", "/v1/drafts/{draft_id}/export-pdf", min_role="member", status=201, tags=("drafts",),
       summary="Gera PDF do rascunho e guarda no cofre (documento hasheado, pronto para assinatura)")
def export_pdf(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        d = c.one("SELECT * FROM drafts WHERE id = $1 AND org_id = $2", ctx.path["draft_id"], ctx.org_id)
    if not d:
        raise not_found("Rascunho")
    footer = f"Versão {d['version']} · SHA-256 do texto: {d['content_sha256']}" + (" · Elaborado com assistência de IA e revisado pela equipe" if d["ai_assisted"] else "")
    data = docsvc.render_pdf(d["title"], d["content"], footer)
    digest = hashlib.sha256(data).hexdigest()
    key = docsvc.new_storage_key(ctx.org_id)
    ctx.app.storage.put(key, data, "application/pdf")
    with ctx.tx() as c:
        did = c.scalar("INSERT INTO documents(org_id, project_id, application_id, doc_type, title, filename, mime_type, size_bytes, sha256, storage_key,"
                       " status, scan_engine, scanned_at, origin, uploaded_by) VALUES ($1,$2,$3,'proposta_projeto',$4,$5,'application/pdf',$6::bigint,$7,$8,"
                       " 'clean','generated', now(), 'generated', $9) RETURNING id::text",
                       ctx.org_id, d["project_id"], d["application_id"], d["title"][:200], safe_filename(d["title"]) + ".pdf", len(data), digest, key, ctx.user_id)
        ctx.audit(c, "draft.exported_pdf", "document", did, {"draft": d["id"], "sha256": digest})
    return {"document_id": did, "sha256": digest}


class ExportQ(S.In):
    format: Literal["pdf", "docx", "odt"] = "pdf"
    include_verification: bool = False


@route("POST", "/v1/drafts/{draft_id}/export", body=ExportQ, min_role="member", status=201, tags=("drafts",),
       summary="Gera o rascunho em PDF, DOCX ou ODT e guarda no cofre; opcionalmente imprime o QR de verificação pública")
def export_draft(ctx: Ctx, body: ExportQ):
    from ..services import formats as FMT
    with ctx.tx(readonly=True) as c:
        d = c.one("SELECT * FROM drafts WHERE id = $1 AND org_id = $2", ctx.path["draft_id"], ctx.org_id)
    if not d:
        raise not_found("Rascunho")
    footer = (f"Versão {d['version']} · SHA-256 do texto: {d['content_sha256']}"
              + (" · Elaborado com assistência de IA e revisado pela equipe" if d["ai_assisted"] else ""))
    blocks = [("p", line) if line.strip() else ("spacer", "") for line in d["content"].split("\n")]
    code = url = None
    if body.include_verification:
        with ctx.tx(readonly=True) as c:
            code = c.scalar("SELECT code FROM verifiable_records WHERE subject_type = 'draft' AND subject_id = $1"
                            " AND status = 'active' ORDER BY created_at DESC LIMIT 1", d["id"])
        if not code:
            raise ApiError(409, "no_verifiable_record", "Gere o registro público de verificação deste rascunho antes de "
                                                        "imprimir o QR (POST /v1/verifiable-records).")
        url = f"{ctx.settings.public_base_url.rstrip('/')}/verificar/{code}"
    if body.format == "pdf":
        data, mime, ext = FMT.pdf(d["title"], blocks, footer=footer, verification_code=code,
                                  verification_url=url), "application/pdf", "pdf"
    elif body.format == "docx":
        extra = [("spacer", ""), ("h2", "Verificação pública"), ("p", f"Código: {code}"), ("p", url)] if code else []
        data, mime, ext = (FMT.docx(d["title"], blocks + [("spacer", ""), ("quote", footer)] + extra),
                           "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx")
    else:
        extra = [("spacer", ""), ("h2", "Verificação pública"), ("p", f"Código: {code}"), ("p", url)] if code else []
        data, mime, ext = (FMT.odt(d["title"], blocks + [("spacer", ""), ("quote", footer)] + extra),
                           "application/vnd.oasis.opendocument.text", "odt")
    digest = hashlib.sha256(data).hexdigest()
    key = docsvc.new_storage_key(ctx.org_id)
    ctx.app.storage.put(key, data, mime)
    with ctx.tx() as c:
        did = c.scalar("INSERT INTO documents(org_id, project_id, application_id, doc_type, title, filename, mime_type,"
                       " size_bytes, sha256, storage_key, status, scan_engine, scanned_at, origin, uploaded_by)"
                       " VALUES ($1,$2,$3,'proposta_projeto',$4,$5,$6,$7::bigint,$8,$9,'clean','generated', now(),"
                       " 'generated', $10) RETURNING id::text",
                       ctx.org_id, d["project_id"], d["application_id"], d["title"][:200],
                       safe_filename(d["title"]) + "." + ext, mime, len(data), digest, key, ctx.user_id)
        ctx.audit(c, "draft.exported", "document", did, {"draft": d["id"], "format": body.format, "sha256": digest})
    return {"document_id": did, "sha256": digest, "format": body.format, "filename": safe_filename(d["title"]) + "." + ext,
            "verification_code": code}


# ------------------------------------------------------------------------------------------------ validação profissional
@route("POST", "/v1/professional-reviews", body=S.ReviewRequestIn, min_role="member", status=201, feature="professional.request",
       tags=("professionals",), summary="Solicita validação a profissional parceiro habilitado (contrato e honorários fora da plataforma)")
def request_review(ctx: Ctx, body: S.ReviewRequestIn):
    with ctx.tx() as c:
        pro = c.one("SELECT o.id FROM organizations o JOIN provider_profiles p ON p.org_id = o.id WHERE o.id = $1 AND o.kind = 'provider'"
                    " AND o.status = 'active' AND p.accepting_requests", body.professional_org_id)
        if not pro:
            raise not_found("Profissional parceiro")
        table, col = {"draft": ("drafts", "content_sha256"), "document": ("documents", "sha256"),
                      "application": ("applications", None), "project": ("projects", None)}[body.subject_type]
        owner_col = "osc_org_id" if table == "applications" else "org_id"
        subj = c.one(f"SELECT {col + ' AS h' if col else 'NULL AS h'} FROM {table} WHERE id = $1 AND {owner_col} = $2", body.subject_id, ctx.org_id)
        if not subj:
            raise not_found("Objeto da revisão")
        rid = c.scalar("INSERT INTO professional_reviews(org_id, professional_org_id, subject_type, subject_id, subject_sha256, scope, due_on, requested_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7::date,$8) RETURNING id::text", ctx.org_id, body.professional_org_id, body.subject_type,
                       body.subject_id, subj["h"], body.scope, body.due_on, ctx.user_id)
        if body.subject_type == "draft":
            c.run("UPDATE drafts SET status = 'in_review' WHERE id = $1", body.subject_id)
        c.scalar("SELECT app_notify($1, NULL, 'review', $2, $3, $4)", body.professional_org_id, "Nova solicitação de validação",
                 f"{ctx.principal.org_name}: {body.scope[:150]}", f"/revisoes/{rid}")
        ctx.audit(c, "review.requested", "review", rid, {"subject_type": body.subject_type})
    return {"id": rid, "status": "requested"}


@route("GET", "/v1/professional-reviews", query=S.Pagination, min_role="viewer", tags=("professionals",))
def list_reviews(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT r.id::text AS id, r.subject_type, r.subject_id::text AS subject_id, r.scope, r.status, r.response_note, r.due_on,"
                       " r.created_at, r.updated_at, o.legal_name AS requester, p.legal_name AS professional,"
                       " CASE WHEN r.professional_org_id = $1 THEN 'incoming' ELSE 'outgoing' END AS direction"
                       " FROM professional_reviews r JOIN organizations o ON o.id = r.org_id JOIN organizations p ON p.id = r.professional_org_id"
                       " ORDER BY r.updated_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/professional-reviews/{review_id}/respond", body=S.ReviewRespondIn, min_role="member", tags=("professionals",),
       summary="Profissional aceita/recusa, pede ajustes ou aprova (aprovação exige credencial verificada e vigente)")
def respond_review(ctx: Ctx, body: S.ReviewRespondIn):
    with ctx.tx() as c:
        r = c.one("SELECT id::text AS id, org_id::text AS org_id, professional_org_id::text AS professional_org_id, subject_type,"
                  " subject_id::text AS subject_id, subject_sha256, status FROM professional_reviews WHERE id = $1 FOR UPDATE", ctx.path["review_id"])
        if not r:
            raise not_found("Revisão")
        is_pro = r["professional_org_id"] == ctx.org_id
        if body.status == "cancelled":
            if r["org_id"] != ctx.org_id:
                raise ApiError(403, "forbidden", "Somente o solicitante cancela")
        elif not is_pro:
            raise ApiError(403, "forbidden", "Somente o profissional responde")
        flow = {"requested": {"accepted", "declined", "cancelled"}, "accepted": {"changes_requested", "approved", "cancelled"},
                "changes_requested": {"approved", "cancelled", "accepted"}}
        if body.status not in flow.get(r["status"], set()):
            raise ApiError(409, "invalid_transition", f"Não é possível passar de {r['status']} para {body.status}")
        cred = None
        if body.status == "approved":
            if not body.credential_id:
                raise ApiError(422, "credential_required", "Informe a credencial profissional usada na validação")
            cred = c.one("SELECT id FROM professional_credentials WHERE id = $1 AND org_id = $2 AND user_id = $3 AND verification_status = 'verified'"
                         " AND (valid_until IS NULL OR valid_until >= current_date)", body.credential_id, ctx.org_id, ctx.user_id)
            if not cred:
                raise ApiError(409, "credential_not_verified", "Credencial inexistente, não verificada pela administração ou vencida")
            if r["subject_type"] in ("draft", "document"):
                table, col = ("drafts", "content_sha256") if r["subject_type"] == "draft" else ("documents", "sha256")
                cur = c.scalar(f"SELECT {col} FROM {table} WHERE id = $1", r["subject_id"])
                if cur != r["subject_sha256"]:
                    raise ApiError(409, "subject_changed", "O conteúdo mudou desde a solicitação; peça nova revisão")
        c.run("UPDATE professional_reviews SET status = $2, response_note = coalesce($3, response_note), credential_id = coalesce($4::uuid, credential_id)"
              " WHERE id = $1", r["id"], body.status, body.note, body.credential_id)
        target = r["org_id"] if is_pro else r["professional_org_id"]
        c.scalar("SELECT app_notify($1, NULL, 'review', $2, $3, $4)", target, "Atualização de validação profissional",
                 f"Status: {body.status}. {body.note or ''}"[:300], f"/revisoes/{r['id']}")
        ctx.audit(c, "review.responded", "review", r["id"], {"status": body.status}, org_id=ctx.org_id)
    if body.status == "approved" and r["subject_type"] == "draft":
        with ctx.system_tx() as c:
            c.run("UPDATE drafts SET status = 'approved' WHERE id = $1 AND content_sha256 = $2", r["subject_id"], r["subject_sha256"])
    return {"id": r["id"], "status": body.status}


@route("GET", "/v1/professional-reviews/{review_id}", min_role="viewer", tags=("professionals",))
def get_review(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        r = c.one("SELECT r.*, r.id::text AS id, r.subject_id::text AS subject_id, o.legal_name AS requester, p.legal_name AS professional"
                  " FROM professional_reviews r JOIN organizations o ON o.id = r.org_id JOIN organizations p ON p.id = r.professional_org_id"
                  " WHERE r.id = $1", ctx.path["review_id"])
        if not r:
            raise not_found("Revisão")
        if r["subject_type"] == "draft":
            r["subject"] = c.one("SELECT id::text AS id, title, kind, content, content_sha256, version, ai_assisted FROM drafts WHERE id = $1", r["subject_id"])
        elif r["subject_type"] == "document":
            r["subject"] = c.one(f"SELECT {DOC_COLS} FROM documents d WHERE d.id = $1", r["subject_id"])
        elif r["subject_type"] == "project":
            r["subject"] = c.one("SELECT id::text AS id, title, summary, budget_total_cents FROM projects WHERE id = $1", r["subject_id"])
    return r


# ------------------------------------------------------------------------------------------------ assinaturas
def _signature_material(sig: dict) -> str:
    return "|".join(str(sig[k]) for k in ("subject_type", "subject_id", "subject_sha256", "signer_user_id", "signer_org_id",
                                           "credential_id", "role", "statement", "signed_at"))


@route("POST", "/v1/signatures", body=S.SignIn, min_role="member", status=201, rate=("sign_ip", 30, 3600), tags=("signatures",),
       summary="Assinatura eletrônica avançada em DUAS CAMADAS (senha + código de uso único), hash da versão exata, credencial e trilha")
def sign(ctx: Ctx, body: S.SignIn):
    from datetime import datetime

    from ..trust import challenges as CH
    from ..trust import custody as CUST
    # Camada 1: reautenticação por senha.
    with ctx.system_tx() as c:
        h = c.scalar("SELECT password_hash FROM users WHERE id = $1", ctx.user_id)
    if not passwords.verify_password(body.password, h):
        raise ApiError(401, "reauth_failed", "Senha incorreta — a assinatura exige reautenticação")
    # Camada 2: código de uso único, amarrado ao hash EXATO do conteúdo (muda o conteúdo, o código não serve mais).
    with ctx.tx(readonly=True) as c:
        _t, _col = ("drafts", "content_sha256") if body.subject_type == "draft" else ("documents", "sha256")
        _h = c.scalar(f"SELECT {_col} FROM {_t} WHERE id = $1", body.subject_id)
    if _h is None:
        raise not_found("Objeto da assinatura")
    with ctx.system_tx() as c:
        chk = CH.consume(c, user_id=ctx.user_id, subject_type=body.subject_type, subject_id=body.subject_id,
                         subject_sha256=_h, code=body.code)
    if not chk["ok"]:
        raise ApiError(401 if chk["reason"] in ("wrong_code", "no_challenge") else 409, f"challenge_{chk['reason']}",
                       CH.REASONS.get(chk["reason"], "Código de confirmação inválido"))
    with ctx.tx() as c:
        table, col = ("drafts", "content_sha256") if body.subject_type == "draft" else ("documents", "sha256")
        subj = c.one(f"SELECT id::text AS id, org_id::text AS org_id, {col} AS h, project_id::text AS project_id FROM {table} WHERE id = $1",
                     body.subject_id)
        if not subj:
            raise not_found("Objeto da assinatura")
        if body.role == "legal_representative":
            if subj["org_id"] != ctx.org_id or ctx.principal.role not in ("owner", "admin"):
                raise ApiError(403, "forbidden", "Somente proprietário/administrador da organização assina como representante legal")
        elif body.role == "professional":
            rev = c.one("SELECT id::text AS id, credential_id::text AS credential_id, subject_sha256 FROM professional_reviews WHERE id = $1"
                        " AND professional_org_id = $2 AND subject_type = $3 AND subject_id = $4 AND status = 'approved'",
                        body.review_id, ctx.org_id, body.subject_type, body.subject_id)
            if not rev:
                raise ApiError(409, "review_not_approved", "Assinatura profissional exige revisão aprovada por esta organização")
            if rev["subject_sha256"] != subj["h"]:
                raise ApiError(409, "subject_changed", "Conteúdo alterado após a aprovação")
            body.credential_id = rev["credential_id"]
        elif body.role == "funder":
            if ctx.principal.org_kind not in ("company", "government") or not subj["project_id"] or not c.scalar("SELECT app_project_party($1)", subj["project_id"]):
                raise ApiError(403, "forbidden", "Assinatura de financiador exige relação com o projeto")
        sig = {"subject_type": body.subject_type, "subject_id": subj["id"], "subject_sha256": subj["h"], "signer_user_id": ctx.user_id,
               "signer_org_id": ctx.org_id, "credential_id": body.credential_id, "role": body.role, "statement": body.statement,
               "signed_at": datetime.now(UTC).isoformat()}
        mac = hmac_hex(ctx.settings.secret_key, _signature_material(sig))
        # identity_level() é SECURITY DEFINER: dá para ler o nível aqui dentro e gravar no INSERT
        # (signatures é append-only desde 0002 — nada de UPDATE depois).
        sid = c.scalar("INSERT INTO signatures(review_id, subject_type, subject_id, subject_sha256, signer_user_id, signer_org_id, credential_id, role,"
                       " statement, ip, user_agent, signature_hmac, signed_at, challenge_id, identity_level)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13::timestamptz,$14, identity_level($5))"
                       " RETURNING id::text", body.review_id, body.subject_type, subj["id"], subj["h"], ctx.user_id, ctx.org_id,
                       body.credential_id, body.role, body.statement, ctx.ip, ctx.user_agent, mac, sig["signed_at"],
                       chk["challenge_id"])
        CUST.record(c, subject_type=body.subject_type, subject_id=subj["id"], org_id=ctx.org_id, event_type="signed",
                    actor_user_id=ctx.user_id, content_sha256=subj["h"],
                    payload={"role": body.role, "signature_id": sid, "two_factor": True})
        if subj["project_id"]:
            ledger(c, project_id=subj["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="professional_signature",
                   ref_type="signature", ref_id=sid, payload={"role": body.role, "subject_sha256": subj["h"]})
        ctx.audit(c, "signature.created", "signature", sid, {"role": body.role, "subject_type": body.subject_type})
    if body.review_id and body.role == "professional":
        with ctx.system_tx() as c:
            c.run("UPDATE professional_reviews SET status = 'signed' WHERE id = $1", body.review_id)
            if body.subject_type == "draft":
                c.run("UPDATE drafts SET status = 'signed' WHERE id = $1", body.subject_id)
    return {"id": sid, "subject_sha256": subj["h"], "method": "platform_advanced", "two_factor": True,
            "legal_note": "Assinatura eletrônica avançada: reautenticação por senha, código de uso único, hash da versão exata e "
                          "trilha encadeada. Para exigências de assinatura qualificada (ICP-Brasil/gov.br), use certificado próprio — "
                          "a plataforma não emite nem homologa assinatura qualificada."}


class VerifyQ(S.In):
    subject_type: str
    subject_id: S.Uuid


@route("GET", "/v1/signatures/verify", query=VerifyQ, min_role="viewer", tags=("signatures",),
       summary="Verifica integridade: hash atual do conteúdo × hash assinado e selo HMAC do servidor")
def verify(ctx: Ctx, q: VerifyQ):
    if q.subject_type not in ("draft", "document"):
        raise ApiError(422, "validation_error", "subject_type inválido")
    import hmac as _h
    with ctx.tx(readonly=True) as c:
        table, col = ("drafts", "content_sha256") if q.subject_type == "draft" else ("documents", "sha256")
        cur = c.scalar(f"SELECT {col} FROM {table} WHERE id = $1", q.subject_id)
        if cur is None:
            raise not_found("Objeto")
        sigs = c.query("SELECT s.*, s.id::text AS id, s.subject_id::text AS subject_id, s.signer_user_id::text AS signer_user_id,"
                       " s.signer_org_id::text AS signer_org_id, s.credential_id::text AS credential_id, user_display_name(s.signer_user_id) AS full_name,"
                       " o.legal_name, pc.council, pc.number, pc.uf AS council_uf, pc.verification_status FROM signatures s"
                       " JOIN organizations o ON o.id = s.signer_org_id LEFT JOIN professional_credentials pc ON pc.id = s.credential_id"
                       " WHERE s.subject_type = $1 AND s.subject_id = $2 ORDER BY s.signed_at", q.subject_type, q.subject_id)
    out = []
    for s in sigs:
        mat = dict(s, signed_at=s["signed_at"].isoformat(), credential_id=s["credential_id"])
        ok_mac = _h.compare_digest(hmac_hex(ctx.settings.secret_key, _signature_material(mat)), s["signature_hmac"])
        out.append({"id": s["id"], "role": s["role"], "signer": s["full_name"], "organization": s["legal_name"], "signed_at": s["signed_at"],
                    "credential": s["council"] and f"{s['council']}/{s['council_uf'] or ''} {s['number']} ({s['verification_status']})",
                    "content_unchanged": s["subject_sha256"] == cur, "server_seal_valid": ok_mac, "statement": s["statement"]})
    return {"current_sha256": cur, "signatures": out}
