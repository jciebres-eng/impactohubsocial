"""Administração institucional (MFA): catálogos governados, regras de elegibilidade, verificação de qualificações, validação de documentos,
situação institucional e visão geral. Fluxo editorial: DRAFT → REVIEW → APPROVED → PUBLISHED → ARCHIVED (quatro olhos: quem cria não aprova)."""
from __future__ import annotations

from datetime import date

from ..db.pq import Json
from ..engines.institutional import badges as badge_engine
from ..engines.institutional import eligibility as elig
from ..engines.institutional.common import config
from ..http import ApiError, Ctx, not_found, page, route
from ..services import institutional as svc
from ..services import documents as docsvc
from ..services.catalog import DOCUMENT_TYPES
from . import schemas as S
from .institutional_routes import QUAL_COLS, _qual_view, _sync_certifications

T = ("admin", "institutional")


def A(method, path, **kw):
    return route(method, path, auth="admin", tags=T, **kw)


_FORBIDDEN_CLAIMS = ("certificado pelo governo", "certificacao oficial", "certificação oficial", "selo oficial", "homologado pelo governo", "aprovado pelo governo", "certificado pelo estado")
_ORG_KINDS = {"osc", "company", "government", "provider", "individual"}


def _validate_catalog_item(c, d: dict) -> None:
    cat = d["catalog"]
    if cat == "institutional_status":
        raise ApiError(422, "fixed_set", "O conjunto de situações institucionais é fixo (restrição do banco). Altere rótulo/descrição criando nova versão do item existente.")
    text = f"{d['label']} {d.get('description') or ''}".lower()
    if cat == "badge" and any(x in text for x in _FORBIDDEN_CLAIMS):
        raise ApiError(422, "misleading_badge", "Badge não pode sugerir certificação ou aprovação governamental; é classificação interna da plataforma.")
    a = d["attributes"] or {}
    if cat == "legal_nature":
        kinds = a.get("allowed_kinds")
        if not isinstance(kinds, list) or not kinds or not set(kinds) <= _ORG_KINDS:
            raise ApiError(422, "validation_error", "attributes.allowed_kinds: lista com tipos válidos (" + ", ".join(sorted(_ORG_KINDS)) + ")")
        if not isinstance(a.get("requires_cnpj", False), bool):
            raise ApiError(422, "validation_error", "attributes.requires_cnpj: booleano")
    if cat == "badge":
        scope, crit = a.get("scope"), a.get("criterion")
        allowed = badge_engine.ORG_CRITERIA if scope == "organization" else badge_engine.SOLUTION_CRITERIA if scope == "solution" else ()
        if crit not in allowed:
            raise ApiError(422, "validation_error", f"Badge: scope 'organization' ou 'solution' e criterion válido para o escopo ({', '.join(allowed) or '—'})")
        vd = a.get("validity_days", 365)
        if not isinstance(vd, int) or isinstance(vd, bool) or not 1 <= vd <= 3650:
            raise ApiError(422, "validation_error", "attributes.validity_days: inteiro de 1 a 3650")
        p = a.get("params") or {}
        if crit == "qualification_verified" and p.get("type") not in svc.catalog(c, "qualification_type").get("qualification_type", {}):
            raise ApiError(422, "validation_error", "params.type deve ser um tipo de qualificação publicado")
        if crit == "document_validated" and not (isinstance(p.get("doc_types"), list) and p["doc_types"] and all(t in DOCUMENT_TYPES for t in p["doc_types"])):
            raise ApiError(422, "validation_error", "params.doc_types: lista de tipos de documento conhecidos")
        if crit == "solution_trust" and not (isinstance(p.get("levels"), list) and p["levels"] and set(p["levels"]) <= {"documented", "evidenced", "verified"}):
            raise ApiError(422, "validation_error", "params.levels: subconjunto de documented, evidenced, verified")
        if not d.get("source_citation"):
            raise ApiError(422, "source_required", "Badge exige a fonte/critério documentado (source_citation)")


def _validate_rule(c, d: dict) -> dict:
    try:
        req = elig.validate_requirement(d["requirement"])
    except ValueError as e:
        raise ApiError(422, "validation_error", "requirement: " + str(e)) from e
    cat = svc.catalog(c)
    if req["type"] in ("qualification_any", "qualification_all"):
        bad = [v for v in req["values"] if v not in cat.get("qualification_type", {})]
        if bad:
            raise ApiError(422, "validation_error", "Qualificações fora do catálogo publicado: " + ", ".join(bad))
    if req["type"] == "legal_nature_in":
        bad = [v for v in req["values"] if v not in cat.get("legal_nature", {})]
        if bad:
            raise ApiError(422, "validation_error", "Naturezas jurídicas fora do catálogo publicado: " + ", ".join(bad))
    if req["type"] == "org_status_in":
        bad = [v for v in req["values"] if v not in cat.get("institutional_status", {})]
        if bad:
            raise ApiError(422, "validation_error", "Situações fora do catálogo: " + ", ".join(bad))
    if req["type"] == "document_valid":
        bad = [v for v in req["doc_types"] if v not in DOCUMENT_TYPES]
        if bad:
            raise ApiError(422, "validation_error", "Tipos de documento desconhecidos: " + ", ".join(bad))
    st, ref = d["scope_type"], d.get("scope_ref")
    if (st == "global") != (ref is None):
        raise ApiError(422, "validation_error", "scope_ref é obrigatório exceto no escopo 'global' (onde deve ser vazio)")
    if st == "modality" and ref not in cat.get("funding_modality", {}):
        raise ApiError(422, "validation_error", "scope_ref deve ser uma modalidade publicada")
    if st == "call" and not c.one("SELECT 1 FROM calls WHERE id::text = $1", ref):
        raise not_found("Edital")
    if st == "funder" and not c.one("SELECT 1 FROM organizations WHERE id::text = $1", ref):
        raise not_found("Organização financiadora")
    if d.get("effective_from") and d.get("effective_to") and d["effective_from"] > d["effective_to"]:
        raise ApiError(422, "validation_error", "Vigência inválida")
    return req


# ------------------------------------------------------------------------------------------------ fluxo editorial (compartilhado)
def _transition(c, ctx: Ctx, table: str, rid: str, body: S.WorkflowIn, *, key: tuple[str, ...]) -> dict:
    r = c.one(f"SELECT * FROM {table} WHERE id = $1 FOR UPDATE", rid)
    if not r:
        raise not_found("Item")
    st, act = r["status"], body.action
    uid = ctx.user_id
    if act == "submit":
        if st != "draft":
            raise ApiError(409, "invalid_transition", "Somente rascunhos são enviados à revisão")
        c.run(f"UPDATE {table} SET status = 'review', updated_at = now() WHERE id = $1", rid)
    elif act == "approve":
        if st != "review":
            raise ApiError(409, "invalid_transition", "Somente itens em revisão são aprovados")
        if r["created_by"] and r["created_by"] == uid:
            raise ApiError(409, "second_reviewer_required", "Quem criou o item não pode aprová-lo: a aprovação exige outra pessoa")
        c.run(f"UPDATE {table} SET status = 'approved', approved_by = $2, reviewed_by = $2, updated_at = now() WHERE id = $1", rid, uid)
    elif act == "publish":
        if st != "approved":
            raise ApiError(409, "invalid_transition", "Somente itens aprovados são publicados")
        if table == "eligibility_rules":
            consulted = r["source_consulted_on"] or body.source_consulted_on
            if not consulted:
                raise ApiError(422, "source_required", "Informe a data em que a fonte foi consultada (source_consulted_on)")
            c.run("UPDATE eligibility_rules SET status = 'archived', archived_at = now() WHERE code = $1 AND status = 'published' AND id <> $2", r["code"], rid)
            c.run("UPDATE eligibility_rules SET status = 'published', published_by = $2, published_at = now(), source_consulted_on = $3::date, updated_at = now() WHERE id = $1", rid, uid, consulted)
        else:
            c.run("UPDATE inst_catalog_items SET status = 'archived', archived_at = now() WHERE catalog = $1 AND code = $2 AND status = 'published' AND id <> $3", r["catalog"], r["code"], rid)
            c.run("UPDATE inst_catalog_items SET status = 'published', published_by = $2, published_at = now(), updated_at = now() WHERE id = $1", rid, uid)
    elif act == "archive":
        if st not in ("published", "approved", "review"):
            raise ApiError(409, "invalid_transition", "Somente itens em revisão, aprovados ou publicados são arquivados")
        c.run(f"UPDATE {table} SET status = 'archived', archived_at = now(), updated_at = now() WHERE id = $1", rid)
    elif act == "return_to_draft":
        if st not in ("review", "approved"):
            raise ApiError(409, "invalid_transition", "Somente itens em revisão/aprovados voltam ao rascunho")
        c.run(f"UPDATE {table} SET status = 'draft', approved_by = NULL, reviewed_by = NULL, updated_at = now() WHERE id = $1", rid)
    if body.note:
        c.run(f"UPDATE {table} SET change_note = $2 WHERE id = $1", rid, body.note)
    out = c.one(f"SELECT id::text AS id, status, version FROM {table} WHERE id = $1", rid)
    ctx.audit(c, f"inst.{key[0]}_{act}", key[0], rid, {"from": st, "to": out["status"], "note": body.note}, org_id=None)
    return out


# ------------------------------------------------------------------------------------------------ catálogos
@A("GET", "/v1/admin/institutional/catalog", query=S.AdminInstListQ, summary="Itens de catálogo em qualquer estado do fluxo editorial")
def list_catalog(ctx: Ctx, q: S.AdminInstListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, catalog, code, version, label, description, attributes, source_citation, source_url, source_date, confidence, needs_professional_validation,"
                       " status, created_by::text AS created_by, approved_by::text AS approved_by, published_at, change_note, updated_at FROM inst_catalog_items"
                       " WHERE ($1::text IS NULL OR status = $1) AND ($2::text IS NULL OR catalog = $2) ORDER BY catalog, code, version DESC LIMIT $3 OFFSET $4",
                       q.status, q.catalog, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("POST", "/v1/admin/institutional/catalog", body=S.CatalogItemIn, status=201, summary="Cria item de catálogo (nasce rascunho; passa por revisão e aprovação de outra pessoa)")
def create_catalog(ctx: Ctx, body: S.CatalogItemIn):
    d = body.model_dump()
    with ctx.tx() as c:
        _validate_catalog_item(c, d)
        if c.one("SELECT 1 FROM inst_catalog_items WHERE catalog = $1 AND code = $2", d["catalog"], d["code"]):
            raise ApiError(409, "code_exists", "Código já existe neste catálogo: use 'nova versão' do item existente")
        rid = c.scalar("INSERT INTO inst_catalog_items(catalog, code, label, description, attributes, source_citation, source_url, source_date, confidence, needs_professional_validation, change_note, created_by)"
                       " VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8::date,$9,$10,$11,$12) RETURNING id::text", d["catalog"], d["code"], d["label"], d["description"], Json(d["attributes"]),
                       d["source_citation"], d["source_url"], d["source_date"], d["confidence"], d["needs_professional_validation"], d["change_note"], ctx.user_id)
        ctx.audit(c, "inst.catalog_created", "catalog_item", rid, {"catalog": d["catalog"], "code": d["code"]}, org_id=None)
    return {"id": rid, "status": "draft", "version": 1}


@A("POST", "/v1/admin/institutional/catalog/{item_id}/new-version", body=S.CatalogItemIn, status=201,
   summary="Nova versão de um item existente (rascunho). A versão publicada anterior só é arquivada quando a nova for publicada.")
def catalog_new_version(ctx: Ctx, body: S.CatalogItemIn):
    d = body.model_dump()
    with ctx.tx() as c:
        cur = c.one("SELECT catalog, code FROM inst_catalog_items WHERE id = $1", ctx.path["item_id"])
        if not cur:
            raise not_found("Item")
        if (cur["catalog"], cur["code"]) != (d["catalog"], d["code"]):
            raise ApiError(422, "validation_error", "catalog/code devem coincidir com o item de origem")
        _validate_catalog_item(c, d)
        v = c.scalar("SELECT max(version) + 1 FROM inst_catalog_items WHERE catalog = $1 AND code = $2", d["catalog"], d["code"])
        rid = c.scalar("INSERT INTO inst_catalog_items(catalog, code, version, label, description, attributes, source_citation, source_url, source_date, confidence, needs_professional_validation, change_note, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9::date,$10,$11,$12,$13) RETURNING id::text", d["catalog"], d["code"], v, d["label"], d["description"], Json(d["attributes"]),
                       d["source_citation"], d["source_url"], d["source_date"], d["confidence"], d["needs_professional_validation"], d["change_note"], ctx.user_id)
        ctx.audit(c, "inst.catalog_new_version", "catalog_item", rid, {"catalog": d["catalog"], "code": d["code"], "version": v}, org_id=None)
    return {"id": rid, "status": "draft", "version": v}


@A("POST", "/v1/admin/institutional/catalog/{item_id}/action", body=S.WorkflowIn, summary="Fluxo: submit → approve (outra pessoa) → publish → archive / return_to_draft")
def catalog_action(ctx: Ctx, body: S.WorkflowIn):
    with ctx.tx() as c:
        return _transition(c, ctx, "inst_catalog_items", ctx.path["item_id"], body, key=("catalog",))


# ------------------------------------------------------------------------------------------------ regras
@A("GET", "/v1/admin/institutional/rules", query=S.AdminInstListQ, summary="Regras de elegibilidade em qualquer estado (com fonte, versão e vigência)")
def list_rules(ctx: Ctx, q: S.AdminInstListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, code, version, name, description, scope_type, scope_ref, requirement, mandatory, how_to_fix, source_citation, source_url, source_consulted_on,"
                       " confidence, needs_professional_validation, effective_from, effective_to, status, created_by::text AS created_by, approved_by::text AS approved_by, published_at, change_note"
                       " FROM eligibility_rules WHERE ($1::text IS NULL OR status = $1) AND ($2::text IS NULL OR scope_type = $2) ORDER BY code, version DESC LIMIT $3 OFFSET $4",
                       q.status, q.scope_type, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("POST", "/v1/admin/institutional/rules", body=S.RuleIn, status=201, summary="Cria regra (nasce rascunho). Exige fonte; só vale depois de revisão, aprovação por outra pessoa e publicação.")
def create_rule(ctx: Ctx, body: S.RuleIn):
    d = body.model_dump()
    with ctx.tx() as c:
        req = _validate_rule(c, d)
        if c.one("SELECT 1 FROM eligibility_rules WHERE code = $1", d["code"]):
            raise ApiError(409, "code_exists", "Código de regra já existe: use 'nova versão'")
        rid = _insert_rule(c, ctx, d, req, 1)
        ctx.audit(c, "inst.rule_created", "rule", rid, {"code": d["code"], "scope": d["scope_type"]}, org_id=None)
    return {"id": rid, "status": "draft", "version": 1}


def _insert_rule(c, ctx: Ctx, d: dict, req: dict, version: int) -> str:
    return c.scalar("INSERT INTO eligibility_rules(code, version, name, description, scope_type, scope_ref, requirement, mandatory, how_to_fix, source_citation, source_url, source_consulted_on,"
                    " confidence, needs_professional_validation, effective_from, effective_to, change_note, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11,$12::date,$13,$14,$15::date,$16::date,$17,$18)"
                    " RETURNING id::text", d["code"], version, d["name"], d["description"], d["scope_type"], d["scope_ref"], Json(req), d["mandatory"], d["how_to_fix"], d["source_citation"],
                    d["source_url"], d["source_consulted_on"], d["confidence"], d["needs_professional_validation"], d["effective_from"], d["effective_to"], d["change_note"], ctx.user_id)


@A("POST", "/v1/admin/institutional/rules/{rule_id}/new-version", body=S.RuleIn, status=201, summary="Nova versão de uma regra existente (a publicada continua valendo até a nova ser publicada)")
def rule_new_version(ctx: Ctx, body: S.RuleIn):
    d = body.model_dump()
    with ctx.tx() as c:
        cur = c.one("SELECT code FROM eligibility_rules WHERE id = $1", ctx.path["rule_id"])
        if not cur:
            raise not_found("Regra")
        if cur["code"] != d["code"]:
            raise ApiError(422, "validation_error", "O código deve coincidir com a regra de origem")
        req = _validate_rule(c, d)
        v = c.scalar("SELECT max(version) + 1 FROM eligibility_rules WHERE code = $1", d["code"])
        rid = _insert_rule(c, ctx, d, req, v)
        ctx.audit(c, "inst.rule_new_version", "rule", rid, {"code": d["code"], "version": v}, org_id=None)
    return {"id": rid, "status": "draft", "version": v}


@A("POST", "/v1/admin/institutional/rules/{rule_id}/action", body=S.WorkflowIn, summary="Fluxo: submit → approve (outra pessoa) → publish (data de consulta da fonte) → archive")
def rule_action(ctx: Ctx, body: S.WorkflowIn):
    with ctx.tx() as c:
        return _transition(c, ctx, "eligibility_rules", ctx.path["rule_id"], body, key=("rule",))


@A("POST", "/v1/admin/institutional/rules/import-candidates", status=201,
   summary="Importa as regras CANDIDATAS do repositório como RASCUNHO (nunca publica; idempotente por código)")
def import_candidates(ctx: Ctx):
    import json
    from ..engines.institutional.common import CFG
    data = json.loads((CFG.parent / "institutional_rules.candidates.json").read_text(encoding="utf-8"))
    created, skipped = [], []
    with ctx.tx() as c:
        for r in data["rules"]:
            if c.one("SELECT 1 FROM eligibility_rules WHERE code = $1", r["code"]):
                skipped.append(r["code"])
                continue
            d = {"code": r["code"], "name": r["name"], "description": r.get("description"), "scope_type": r["scope_type"], "scope_ref": r.get("scope_ref"),
                 "requirement": r["requirement"], "mandatory": True, "how_to_fix": r.get("how_to_fix"), "source_citation": r["source_citation"], "source_url": r.get("source_url"),
                 "source_consulted_on": None, "confidence": r.get("confidence", "low"), "needs_professional_validation": True, "effective_from": None, "effective_to": None,
                 "change_note": "Candidata importada do repositório — requer conferência da fonte antes de publicar"}
            req = _validate_rule(c, d)
            rid = _insert_rule(c, ctx, d, req, 1)
            created.append(r["code"])
            ctx.audit(c, "inst.rule_candidate_imported", "rule", rid, {"code": r["code"]}, org_id=None)
    return {"created": created, "skipped": skipped, "status": "draft",
            "note": "Nenhuma regra foi publicada. Conferir a fonte, enviar à revisão e aprovar com outra pessoa."}


# ------------------------------------------------------------------------------------------------ qualificações
@A("GET", "/v1/admin/institutional/qualifications", query=S.AdminQualQ, summary="Fila de qualificações (padrão: comprovante enviado / em análise)")
def qualification_queue(ctx: Ctx, q: S.AdminQualQ):
    with ctx.tx(readonly=True) as c:
        cat = svc.catalog(c, "qualification_type").get("qualification_type", {})
        rows = c.query(f"SELECT {QUAL_COLS}, o.legal_name AS org_name, o.cnpj, d.validation_status AS document_validation, d.status AS document_scan FROM organization_qualifications q"
                       " JOIN organizations o ON o.id = q.org_id LEFT JOIN documents d ON d.id = q.document_id"
                       " WHERE ($1::text IS NULL AND q.verification_status IN ('document_submitted','under_review') OR q.verification_status = $1)"
                       " ORDER BY q.updated_at LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    return page([_qual_view(r, cat) for r in rows], q.limit, q.offset)


@A("POST", "/v1/admin/institutional/qualifications/{qualification_id}/decide", body=S.QualDecisionIn,
   summary="Verifica, rejeita, revoga ou pede informações. Verificar exige autoridade, número/protocolo e (documento VALIDADO ou URL de verificação).")
def qualification_decide(ctx: Ctx, body: S.QualDecisionIn):
    today = date.today()
    with ctx.tx() as c:
        q = c.one("SELECT q.*, q.id::text AS id, q.org_id::text AS org_id, d.validation_status AS doc_validation, d.status AS doc_scan, d.valid_until AS doc_valid_until"
                  " FROM organization_qualifications q LEFT JOIN documents d ON d.id = q.document_id WHERE q.id = $1 FOR UPDATE OF q", ctx.path["qualification_id"])
        if not q:
            raise not_found("Qualificação")
        dec, note = body.decision, (body.note or "").strip() or None
        if dec == "verify":
            if q["verification_status"] in ("rejected", "revoked", "verified"):
                raise ApiError(409, "invalid_transition", "Estado atual não permite verificação")
            gaps = []
            if not q["issuing_authority"]:
                gaps.append("autoridade concedente")
            if not (q["certificate_number"] or q["protocol"]):
                gaps.append("número do certificado ou protocolo")
            doc_ok = bool(q["document_id"] and q["doc_validation"] == "validated" and q["doc_scan"] in docsvc.usable_statuses()
                          and not (q["doc_valid_until"] and q["doc_valid_until"] < today))
            if not (doc_ok or q["verification_url"]):
                gaps.append("documento comprobatório VALIDADO ou URL de verificação oficial")
            if q["expiration_date"] and q["expiration_date"] < today:
                gaps.append("qualificação já expirada em " + q["expiration_date"].strftime("%d/%m/%Y"))
            if not note:
                gaps.append("nota de verificação")
            if gaps:
                raise ApiError(422, "verification_requirements", "Não é possível verificar: faltam " + "; ".join(gaps), {"missing": gaps})
            c.run("UPDATE organization_qualifications SET verification_status = 'verified', validated_by = $2, validation_date = $3::date, validation_note = $4 WHERE id = $1",
                  q["id"], ctx.user_id, body.validation_date or today, note)
        elif dec in ("reject", "revoke", "request_info"):
            if not note:
                raise ApiError(422, "note_required", "Informe a justificativa")
            if dec == "revoke" and q["verification_status"] != "verified":
                raise ApiError(409, "invalid_transition", "Somente qualificações verificadas podem ser revogadas")
            if dec != "revoke" and q["verification_status"] in ("rejected", "revoked"):
                raise ApiError(409, "invalid_transition", "Estado atual não permite esta decisão")
            new = {"reject": "rejected", "revoke": "revoked", "request_info": "declared"}[dec]
            c.run("UPDATE organization_qualifications SET verification_status = $2, validated_by = NULL, validation_date = NULL, validation_note = $3 WHERE id = $1", q["id"], new, note)
        _sync_certifications(c, q["org_id"])
        c.scalar("SELECT app_notify($1, NULL, 'qualification', $2, $3, '/instituicao')", q["org_id"], f"Qualificação {q['qualification_type'].upper()}: {dec}", note or "Decisão registrada pela administração")
        ctx.audit(c, f"inst.qualification_{dec}", "qualification", q["id"], {"org": q["org_id"], "type": q["qualification_type"], "note": note}, org_id=q["org_id"])
        out = c.one("SELECT verification_status, validation_date, validation_note FROM organization_qualifications WHERE id = $1", q["id"])
    return out


# ------------------------------------------------------------------------------------------------ documentos
@A("GET", "/v1/admin/institutional/documents", query=S.AdminDocQ, summary="Fila de validação documental (arquivos já aprovados no antivírus)")
def document_queue(ctx: Ctx, q: S.AdminDocQ):
    ok = list(docsvc.usable_statuses())
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT d.id::text AS id, d.org_id::text AS org_id, o.legal_name AS org_name, d.doc_type, d.title, d.filename, d.status AS scan_status, d.validation_status,"
                       " d.valid_until, d.issued_on, d.origin_source, d.created_at, d.sha256 FROM documents d JOIN organizations o ON o.id = d.org_id"
                       " WHERE d.deleted_at IS NULL AND d.validation_status = $1 AND d.status = ANY($2::text[])"
                       " AND ($5::uuid IS NULL OR d.org_id = $5) AND ($6::text IS NULL OR d.doc_type = $6)"
                       " ORDER BY d.created_at LIMIT $3 OFFSET $4",
                       q.validation, ok, q.limit + 1, q.offset, q.org_id, q.doc_type)
    for r in rows:
        r["label"] = (DOCUMENT_TYPES.get(r["doc_type"]) or {}).get("label", r["doc_type"])
    return page(rows, q.limit, q.offset)


@A("POST", "/v1/admin/institutional/documents/{document_id}/validate", body=S.DocValidationIn,
   summary="Valida ou rejeita um documento (validação humana; antivírus não substitui). Rejeição exige justificativa.")
def document_validate(ctx: Ctx, body: S.DocValidationIn):
    with ctx.tx() as c:
        d = c.one("SELECT id::text AS id, org_id::text AS org_id, doc_type, status, valid_until, validation_status FROM documents WHERE id = $1 AND deleted_at IS NULL FOR UPDATE", ctx.path["document_id"])
        if not d:
            raise not_found("Documento")
        if body.decision == "validate":
            if d["status"] not in docsvc.usable_statuses():
                raise ApiError(409, "not_scanned", "O arquivo ainda não foi aprovado no antivírus")
            if d["valid_until"] and d["valid_until"] < date.today():
                raise ApiError(409, "expired", "Documento já expirado: não pode ser validado")
            c.run("UPDATE documents SET validation_status = 'validated', validated_by = $2, validated_at = now(), validation_note = $3, issued_on = coalesce($4::date, issued_on) WHERE id = $1",
                  d["id"], ctx.user_id, body.note, body.issued_on)
        else:
            if not (body.note or "").strip():
                raise ApiError(422, "note_required", "Informe o motivo da rejeição")
            c.run("UPDATE documents SET validation_status = 'rejected', validated_by = $2, validated_at = now(), validation_note = $3 WHERE id = $1", d["id"], ctx.user_id, body.note)
        c.scalar("SELECT app_notify($1, NULL, 'document', $2, $3, '/instituicao')", d["org_id"], f"Documento {d['doc_type']}: {'validado' if body.decision == 'validate' else 'rejeitado'}", body.note or "Validação registrada")
        ctx.audit(c, f"inst.document_{body.decision}", "document", d["id"], {"org": d["org_id"], "type": d["doc_type"], "note": body.note}, org_id=d["org_id"])
    return {"id": d["id"], "validation_status": "validated" if body.decision == "validate" else "rejected"}


# ------------------------------------------------------------------------------------------------ situação institucional
@A("GET", "/v1/admin/institutional/organizations/{org_id}", summary="Visão institucional de uma organização: fatos, maturidade, situação atual e SUGESTÃO de situação")
def org_snapshot(ctx: Ctx):
    oid = ctx.path["org_id"]
    with ctx.tx(readonly=True) as c:
        f = svc.facts(c, oid)
        if not f:
            raise not_found("Organização")
        return {"facts": f, "maturity": svc.maturity(c, oid, f), "suggested_status": svc.suggest_status(f), "badges": svc.org_badges(c, oid, f)}


@A("POST", "/v1/admin/institutional/organizations/{org_id}/status", body=S.InstStatusIn, summary="Define a situação institucional (decisão humana, justificada e auditada)")
def set_org_status(ctx: Ctx, body: S.InstStatusIn):
    oid = ctx.path["org_id"]
    with ctx.tx() as c:
        cur = c.one("SELECT institutional_status FROM organizations WHERE id = $1 FOR UPDATE", oid)
        if not cur:
            raise not_found("Organização")
        if body.status in ("irregular", "suspended", "documents_pending", "partially_regular") and not body.note:
            raise ApiError(422, "note_required", "Situações restritivas exigem justificativa")
        c.run("UPDATE organizations SET institutional_status = $2, institutional_status_note = $3, institutional_status_by = $4, institutional_status_at = now() WHERE id = $1",
              oid, body.status, body.note, ctx.user_id)
        c.scalar("SELECT app_notify($1, NULL, 'institutional', $2, $3, '/instituicao')", oid, "Situação institucional atualizada", body.note or body.status)
        ctx.audit(c, "inst.status_set", "organization", oid, {"from": cur["institutional_status"], "to": body.status, "note": body.note}, org_id=oid)
    return {"institutional_status": body.status}


@A("GET", "/v1/admin/institutional/overview", summary="Painel institucional: filas e estados do fluxo editorial")
def admin_overview(ctx: Ctx):
    ok = list(docsvc.usable_statuses())
    with ctx.tx(readonly=True) as c:
        return {
            "qualifications_pending": c.scalar("SELECT count(*) FROM organization_qualifications WHERE verification_status IN ('document_submitted','under_review')"),
            "documents_pending": c.scalar("SELECT count(*) FROM documents WHERE deleted_at IS NULL AND validation_status = 'pending' AND status = ANY($1::text[])", ok),
            "rules": {r["status"]: r["n"] for r in c.query("SELECT status, count(*) AS n FROM eligibility_rules GROUP BY status")},
            "catalog": {r["status"]: r["n"] for r in c.query("SELECT status, count(*) AS n FROM inst_catalog_items GROUP BY status")},
            "organizations_by_status": {r["institutional_status"]: r["n"] for r in c.query("SELECT institutional_status, count(*) AS n FROM organizations WHERE kind <> 'platform' GROUP BY 1")},
            "maturity_config": config()["status"]}
