"""Camada institucional do terceiro setor (organização ativa): perfil institucional, qualificações, documentos com estado, maturidade 0–6,
elegibilidade explicável, badges com critério, necessidades do proponente e regras publicadas.

Honestidade: natureza jurídica/qualificação são DECLARADAS até a administração verificar; a plataforma nunca afirma elegibilidade por ausência de dados;
requisitos de origem legal exigem validação profissional (mesmo com tudo comprovado)."""
from __future__ import annotations

from datetime import date

from ..engines.institutional.common import DOC_STATE_LABELS, config
from ..http import ApiError, Ctx, not_found, page, route
from ..services import institutional as svc
from . import schemas as S
from .document_routes import DOC_COLS, with_state

T = ("institutional",)
FUNDER_KINDS = ("company", "government", "individual", "platform")
QUAL_COLS = ("q.id::text AS id, q.org_id::text AS org_id, q.qualification_type, q.issuing_authority, q.protocol, q.certificate_number, q.issue_date, q.expiration_date,"
             " q.verification_url, q.verification_status, q.document_id::text AS document_id, q.validation_date, q.validation_note, q.notes, q.areas, q.created_at, q.updated_at")


def _qual_view(q: dict, cat: dict, today: date | None = None) -> dict:
    today = today or date.today()
    exp = q.get("expiration_date")
    status = q["verification_status"]
    eff = "expired" if status == "verified" and exp and exp < today else status
    labels = {"declared": "DECLARADA (não verificada)", "document_submitted": "COMPROVANTE ENVIADO — aguarda análise", "under_review": "EM ANÁLISE",
              "verified": "VERIFICADA", "rejected": "REJEITADA", "revoked": "REVOGADA", "expired": "VERIFICADA, MAS EXPIRADA"}
    q["effective_status"], q["status_label"] = eff, labels[eff]
    q["type_label"] = (cat.get(q["qualification_type"]) or {}).get("label") or q["qualification_type"]
    q["expires_soon"] = bool(status == "verified" and exp and 0 <= (exp - today).days <= config()["qualification_warning_days"])
    return q


def _check_codes(c, d: dict, org_kind: str, has_cnpj: bool) -> None:
    cat = svc.catalog(c)
    try:
        svc.require_catalog_code(cat, "legal_nature", d.get("legal_nature_code"), "legal_nature_code")
        svc.require_catalog_code(cat, "institutional_profile", d.get("institutional_profile"), "institutional_profile")
    except ValueError as e:
        raise ApiError(422, "validation_error", str(e), {"valid": {k: sorted(v) for k, v in cat.items() if k in ("legal_nature", "institutional_profile")}}) from e
    code = d.get("legal_nature_code")
    if code:
        attrs = cat["legal_nature"][code]["attributes"]
        if attrs.get("allowed_kinds") and org_kind not in attrs["allowed_kinds"]:
            raise ApiError(422, "legal_nature_kind_mismatch", f"A natureza '{code}' não se aplica a organizações do tipo '{org_kind}'.")
        if attrs.get("requires_cnpj") and not has_cnpj:
            raise ApiError(422, "cnpj_required_for_nature", f"A natureza '{code}' exige CNPJ cadastrado. Se a iniciativa ainda não é formalizada, escolha 'Coletivo ou iniciativa em estruturação'.")


# ------------------------------------------------------------------------------------------------ catálogos e regras (leitura)
@route("GET", "/v1/institutional/catalogs", min_role="viewer", tags=T,
       summary="Catálogos publicados: naturezas jurídicas, qualificações, perfis, situações, modalidades e definições de badges (com fonte e confiança)")
def catalogs(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        cat = svc.catalog(c)
    return {"catalogs": {k: list(v.values()) for k, v in cat.items()},
            "note": "Itens iniciais são classificação da plataforma, com revisão jurídica pendente (ver 'needs_professional_validation')."}


@route("GET", "/v1/institutional/rules", min_role="viewer", tags=T, summary="Regras de elegibilidade PUBLICADAS (código, versão, fonte, data de consulta, confiança)")
def published_rules(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT code, version, name, description, scope_type, scope_ref, requirement, mandatory, how_to_fix, source_citation, source_url,"
                       " source_consulted_on, confidence, needs_professional_validation, effective_from, effective_to, published_at FROM eligibility_rules"
                       " WHERE status = 'published' ORDER BY code")
    return {"items": rows, "note": "Regras não substituem a leitura do edital nem a análise de profissional habilitado."}


# ------------------------------------------------------------------------------------------------ perfil institucional
@route("GET", "/v1/institutional/profile", min_role="viewer", tags=T, summary="Perfil institucional da organização ativa (natureza, perfil de atuação, situação, qualificações)")
def get_profile(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        o = c.one("SELECT id::text AS id, kind, legal_name, trade_name, cnpj, legal_nature, legal_nature_code, institutional_profile, institutional_status,"
                  " institutional_status_note, institutional_status_at, founded_on, website, contact_email::text AS email, phone, description, mission, vision,"
                  " geographic_scope, operating_regions, city, uf, ibge_code, territories FROM organizations WHERE id = $1", ctx.org_id)
        cat = svc.catalog(c)
        quals = [_qual_view(q, cat.get("qualification_type", {})) for q in c.query(
            f"SELECT {QUAL_COLS} FROM organization_qualifications q WHERE q.org_id = $1 ORDER BY q.created_at DESC", ctx.org_id)]
    o["headquarters"] = {"city": o["city"], "uf": o["uf"], "ibge_code": o["ibge_code"]}
    o["labels"] = {"legal_nature": (cat["legal_nature"].get(o["legal_nature_code"]) or {}).get("label"),
                   "institutional_profile": (cat["institutional_profile"].get(o["institutional_profile"]) or {}).get("label"),
                   "institutional_status": (cat["institutional_status"].get(o["institutional_status"]) or {}).get("label")}
    return {"organization": o, "qualifications": quals,
            "notes": ["Natureza jurídica e qualificações são DECLARADAS até a verificação pela administração.",
                      "A situação institucional só é alterada pela administração, após revisão documental."]}


@route("PUT", "/v1/institutional/profile", body=S.InstProfileIn, min_role="admin", tags=T,
       summary="Atualiza a natureza jurídica, o perfil de atuação, missão/visão e alcance geográfico (códigos validados no catálogo publicado)")
def put_profile(ctx: Ctx, body: S.InstProfileIn):
    d = body.model_dump(exclude_unset=True)
    if not d:
        raise ApiError(422, "empty", "Nada para atualizar")
    with ctx.tx() as c:
        o = c.one("SELECT kind, cnpj, legal_nature_code FROM organizations WHERE id = $1", ctx.org_id)
        _check_codes(c, {**{"legal_nature_code": None}, **d} if "legal_nature_code" in d else {k: v for k, v in d.items() if k != "legal_nature_code"}, o["kind"], bool(o["cnpj"]))
        sets, vals = [], [ctx.org_id]
        for k, v in d.items():
            vals.append(v)
            sets.append(f"{k} = ${len(vals)}" + {"operating_regions": "::text[]", "founded_on": "::date"}.get(k, ""))
        c.run(f"UPDATE organizations SET {', '.join(sets)} WHERE id = $1", *vals)
        ctx.audit(c, "inst.profile_updated", "organization", ctx.org_id, {"fields": sorted(d), "legal_nature_code": d.get("legal_nature_code")})
    return get_profile(ctx)


# ------------------------------------------------------------------------------------------------ qualificações
@route("GET", "/v1/institutional/qualifications", min_role="viewer", tags=T, summary="Qualificações e certificações da organização (estado: declarada, em análise, verificada, expirada…)")
def list_qualifications(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        cat = svc.catalog(c, "qualification_type").get("qualification_type", {})
        rows = c.query(f"SELECT {QUAL_COLS} FROM organization_qualifications q WHERE q.org_id = $1 ORDER BY q.created_at DESC", ctx.org_id)
    return {"items": [_qual_view(r, cat) for r in rows]}


def _check_qualification(c, ctx: Ctx, d: dict, *, creating: bool) -> None:
    if creating:
        cat = svc.catalog(c, "qualification_type")
        try:
            svc.require_catalog_code(cat, "qualification_type", d["qualification_type"], "qualification_type")
        except ValueError as e:
            raise ApiError(422, "validation_error", str(e), {"valid": sorted(cat.get("qualification_type", {}))}) from e
    if d.get("issue_date") and d.get("expiration_date") and d["expiration_date"] < d["issue_date"]:
        raise ApiError(422, "dates_invalid", "A data de validade não pode ser anterior à data de emissão")
    if d.get("document_id") and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", d["document_id"], ctx.org_id):
        raise not_found("Documento")


@route("POST", "/v1/institutional/qualifications", body=S.QualificationIn, min_role="manager", status=201, tags=T,
       summary="Registra uma qualificação/certificação. Nasce 'declarada' (ou 'comprovante enviado' se houver documento); só a administração verifica.")
def add_qualification(ctx: Ctx, body: S.QualificationIn):
    d = body.model_dump()
    with ctx.tx() as c:
        _check_qualification(c, ctx, d, creating=True)
        dup = c.one("SELECT 1 FROM organization_qualifications WHERE org_id = $1 AND qualification_type = $2 AND coalesce(certificate_number, '') = coalesce($3, '')"
                    " AND verification_status NOT IN ('rejected','revoked')", ctx.org_id, d["qualification_type"], d["certificate_number"])
        if dup:
            raise ApiError(409, "qualification_exists", "Já existe uma qualificação deste tipo e número. Edite a existente.")
        qid = c.scalar("INSERT INTO organization_qualifications(org_id, qualification_type, issuing_authority, protocol, certificate_number, issue_date, expiration_date,"
                       " verification_url, document_id, notes, declared_by, areas) VALUES ($1,$2,$3,$4,$5,$6::date,$7::date,$8,$9::uuid,$10,$11,$12::text[]) RETURNING id::text",
                       ctx.org_id, d["qualification_type"], d["issuing_authority"], d["protocol"], d["certificate_number"], d["issue_date"], d["expiration_date"],
                       d["verification_url"], d["document_id"], d["notes"], ctx.user_id, d.get("areas") or [])
        _sync_certifications(c, ctx.org_id)
        ctx.audit(c, "inst.qualification_declared", "qualification", qid, {"type": d["qualification_type"]})
        row = c.one(f"SELECT {QUAL_COLS} FROM organization_qualifications q WHERE q.id = $1", qid)
        cat = svc.catalog(c, "qualification_type").get("qualification_type", {})
    return _qual_view(row, cat)


def _sync_certifications(c, org_id: str) -> None:
    """Mantém organizations.certifications (legado, usado por telas antigas) como espelho das qualificações não rejeitadas — NÃO é prova."""
    c.run("UPDATE organizations SET certifications = coalesce((SELECT array_agg(DISTINCT qualification_type) FROM organization_qualifications"
          " WHERE org_id = $1 AND verification_status NOT IN ('rejected','revoked')), '{}') WHERE id = $1", org_id)


@route("PATCH", "/v1/institutional/qualifications/{qualification_id}", body=S.QualificationPatch, min_role="manager", tags=T,
       summary="Edita a qualificação. Alterar o conteúdo comprobatório de uma qualificação verificada a devolve para 'em análise'.")
def patch_qualification(ctx: Ctx, body: S.QualificationPatch):
    d = body.model_dump(exclude_unset=True)
    if not d:
        raise ApiError(422, "empty", "Nada para atualizar")
    qid = ctx.path["qualification_id"]
    with ctx.tx() as c:
        cur = c.one("SELECT verification_status, issue_date, expiration_date FROM organization_qualifications WHERE id = $1 AND org_id = $2 FOR UPDATE", qid, ctx.org_id)
        if not cur:
            raise not_found("Qualificação")
        if cur["verification_status"] in ("rejected", "revoked"):
            raise ApiError(409, "closed", "Qualificação rejeitada/revogada não pode ser editada; registre uma nova.")
        _check_qualification(c, ctx, {"issue_date": cur["issue_date"], "expiration_date": cur["expiration_date"], **d}, creating=False)
        sets, vals = [], [qid]
        for k, v in d.items():
            vals.append([] if (k == "areas" and v is None) else v)
            sets.append(f"{k} = ${len(vals)}" + {"issue_date": "::date", "expiration_date": "::date", "document_id": "::uuid", "areas": "::text[]"}.get(k, ""))
        c.run(f"UPDATE organization_qualifications SET {', '.join(sets)} WHERE id = $1", *vals)
        ctx.audit(c, "inst.qualification_edited", "qualification", qid, {"fields": sorted(d)})
        row = c.one(f"SELECT {QUAL_COLS} FROM organization_qualifications q WHERE q.id = $1", qid)
        cat = svc.catalog(c, "qualification_type").get("qualification_type", {})
    return _qual_view(row, cat)


@route("DELETE", "/v1/institutional/qualifications/{qualification_id}", min_role="manager", tags=T, summary="Remove uma qualificação ainda não verificada (as verificadas são encerradas pela administração)")
def delete_qualification(ctx: Ctx):
    with ctx.tx() as c:
        n = c.run("DELETE FROM organization_qualifications WHERE id = $1 AND org_id = $2 AND verification_status IN ('declared','document_submitted','rejected')", ctx.path["qualification_id"], ctx.org_id)
        if not n:
            raise ApiError(409, "not_deletable", "Qualificação inexistente ou já em análise/verificada — fale com a administração.")
        _sync_certifications(c, ctx.org_id)
        ctx.audit(c, "inst.qualification_deleted", "qualification", ctx.path["qualification_id"])
    return None


@route("GET", "/v1/institutional/qualifications/{qualification_id}/events", min_role="viewer", tags=T, summary="Histórico (append-only) da qualificação")
def qualification_events(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        if not c.one("SELECT 1 FROM organization_qualifications WHERE id = $1 AND org_id = $2", ctx.path["qualification_id"], ctx.org_id):
            raise not_found("Qualificação")
        rows = c.query("SELECT event, from_status, to_status, actor_is_admin, note, at FROM organization_qualification_events WHERE qualification_id = $1 ORDER BY at, id", ctx.path["qualification_id"])
    return {"items": rows}


# ------------------------------------------------------------------------------------------------ documentos (estado institucional)
@route("GET", "/v1/institutional/documents", min_role="viewer", tags=T,
       summary="Documentos institucionais com estado (AUSENTE · EXPIRADO · PENDENTE DE VALIDAÇÃO · VALIDADO · REJEITADO) e quais tipos básicos faltam")
def institutional_documents(ctx: Ctx):
    from ..services.catalog import DOCUMENT_TYPES  # noqa: WPS433
    base = config()["base_documents"]
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {DOC_COLS} FROM documents d WHERE d.org_id = $1 AND d.deleted_at IS NULL ORDER BY d.created_at DESC", ctx.org_id)
    rows = [with_state(r) for r in rows]
    by_type: dict[str, list] = {}
    for r in rows:
        by_type.setdefault(r["doc_type"], []).append(r)
    order = ["validated", "pending_validation", "expired", "rejected"]
    items = []
    for t in sorted(set(base) | set(by_type)):
        ds = by_type.get(t, [])
        best = min((d["state"] for d in ds), key=order.index, default="absent")
        items.append({"doc_type": t, "label": (DOCUMENT_TYPES.get(t) or {}).get("label", t), "base": t in base, "state": best, "state_label": DOC_STATE_LABELS[best],
                      "versions": len(ds), "latest": ds[0] if ds else None})
    return {"items": items, "base_documents": base, "missing_base": [i["doc_type"] for i in items if i["base"] and i["state"] == "absent"]}


# ------------------------------------------------------------------------------------------------ maturidade, visão geral, badges
@route("GET", "/v1/institutional/overview", min_role="viewer", tags=T,
       summary="Visão institucional: 'Pode participar' × 'Pode receber este tipo de recurso' × 'Ainda precisa cumprir requisitos', com maturidade e badges")
def overview(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return svc.overview(c, ctx.org_id)


@route("GET", "/v1/institutional/maturity", min_role="viewer", tags=T, summary="Maturidade institucional 0–6 com o que falta para o próximo nível e o caminho de formalização")
def maturity(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return svc.maturity(c, ctx.org_id)


@route("GET", "/v1/institutional/statement", min_role="viewer", tags=T,
       summary="Declaração institucional de apoio (gerada por regras): só afirma o que está cadastrado, rotula o estado e diz 'Não foi possível confirmar' no resto")
def institutional_statement(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return svc.statement(c, ctx.org_id)


@route("GET", "/v1/institutional/badges", min_role="viewer", tags=T, summary="Badges da organização (critério, fonte, data de verificação, validade, estado) — classificação interna, não certificação")
def my_badges(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": svc.org_badges(c, ctx.org_id)}


@route("GET", "/v1/institutional/orgs/{org_id}", min_role="viewer", tags=T,
       summary="Perfil institucional PÚBLICO de uma organização: natureza declarada, qualificações verificadas, situação e badges (sem documentos nem dados privados)")
def public_profile(ctx: Ctx):
    oid = ctx.path["org_id"]
    with ctx.tx(readonly=True) as c:
        f = svc.facts(c, oid)
        if not f:
            raise not_found("Organização")
        cat = svc.catalog(c)
        quals = [q for q in f["qualifications"] if q["status"] == "verified"]
        m = svc.maturity(c, oid, f) if f.get("kind_is_proponent") else None
        badges = [b for b in svc.org_badges(c, oid, f) if b["earned"]]
        name = c.one("SELECT legal_name, trade_name, kind FROM organizations WHERE id = $1", oid)
    return {"organization": {"id": oid, "name": (name or {}).get("trade_name") or (name or {}).get("legal_name"), "kind": f["kind"]},
            "legal_nature": {"code": f.get("legal_nature_code"), "label": (cat["legal_nature"].get(f.get("legal_nature_code")) or {}).get("label"), "status": "declarada"},
            "institutional_profile": (cat["institutional_profile"].get(f.get("institutional_profile")) or {}).get("label"),
            "institutional_status": {"code": f["institutional_status"], "label": (cat["institutional_status"].get(f["institutional_status"]) or {}).get("label")},
            "verified_qualifications": [{"type": q["type"], "label": (cat["qualification_type"].get(q["type"]) or {}).get("label"), "expiration_date": q.get("expiration_date"),
                                         "validation_date": q.get("validation_date"), "issuing_authority": q.get("issuing_authority")} for q in quals],
            "maturity": ({"level": m["level"], "label": m["label"]} if m and m.get("applicable") else None), "badges": badges,
            "disclaimer": "Informações institucionais derivadas de dados declarados e verificações da plataforma; não substituem consulta às fontes oficiais."}


# ------------------------------------------------------------------------------------------------ elegibilidade
def _load_call(c, call_id: str) -> dict:
    call = c.one("SELECT id::text AS id, owner_org_id::text AS owner_org_id, title, instrument, funding_modality, accepted_legal_natures, min_maturity, required_certifications,"
                 " required_document_types, min_org_age_months, causes, closes_at FROM calls WHERE id = $1", call_id)
    if not call:
        raise not_found("Edital/oportunidade")
    return call


@route("POST", "/v1/institutional/eligibility", body=S.EligibilityIn, min_role="viewer", rate=("elig_eval", 120, 600), tags=T,
       summary="Avalia a elegibilidade institucional (edital, modalidade de financiamento ou requisitos de um financiador): estado + o que falta + regras e fontes usadas")
def eligibility(ctx: Ctx, body: S.EligibilityIn):
    target = body.org_id or ctx.org_id
    if target != ctx.org_id and ctx.principal.org_kind not in FUNDER_KINDS:
        raise ApiError(403, "forbidden", "Somente financiadores e o poder público avaliam outras organizações.")
    with ctx.tx() as c:
        facts = svc.facts(c, target)
        if not facts:
            raise not_found("Organização")
        m = svc.maturity(c, target, facts)
        if body.subject_type == "call":
            if not body.subject_id.count("-") == 4:
                raise ApiError(422, "validation_error", "subject_id deve ser o id do edital")
            call = _load_call(c, body.subject_id)
            res = svc.evaluate_for_call(c, target, call, f=facts, m=m)
            if call["instrument"] == "incentive_law":
                res["fiscal"] = svc.fiscal_layers(c, res, call)
        elif body.subject_type == "modality":
            if body.subject_id not in svc.catalog(c, "funding_modality").get("funding_modality", {}):
                raise ApiError(422, "validation_error", "Modalidade fora do catálogo publicado")
            res = svc.evaluate_for_modality(c, target, body.subject_id, f=facts, m=m)
        else:
            fp = c.one("SELECT accepted_legal_natures, required_qualifications, required_document_types, min_org_age_months, min_maturity FROM funder_profiles WHERE org_id = $1", body.subject_id) or {}
            res = svc.evaluate_for_funder(c, target, body.subject_id, fp, f=facts, m=m)
            if not fp:
                res["note"] = "Perfil de requisitos do financiador não disponível para você; resultado limitado às regras publicadas."
        res["evaluation_id"] = svc.persist(c, target, ctx.org_id, ctx.user_id, body.subject_type, body.subject_id, res)
        ctx.audit(c, "inst.eligibility_evaluated", "organization", target, {"subject": body.subject_type, "ref": body.subject_id[:80], "state": res["state"]})
    return res


@route("GET", "/v1/institutional/eligibility", query=S.EligibilityHistoryQ, min_role="viewer", tags=T, summary="Histórico de avaliações de elegibilidade (versão do motor, regras usadas, data)")
def eligibility_history(ctx: Ctx, q: S.EligibilityHistoryQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, org_id::text AS org_id, subject_type, subject_ref, state, engine_version, rules_digest, created_at,"
                       " result->>'summary' AS summary FROM eligibility_evaluations WHERE (org_id = $1 OR viewer_org_id = $1) AND ($2::uuid IS NULL OR org_id = $2::uuid)"
                       " AND ($3::text IS NULL OR subject_type = $3) ORDER BY created_at DESC LIMIT $4 OFFSET $5", ctx.org_id, q.org_id, q.subject_type, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


# ------------------------------------------------------------------------------------------------ necessidades do proponente
@route("GET", "/v1/institutional/needs", min_role="viewer", tags=T, summary="Necessidades do proponente (financiamento, parceiro, replicação, técnica, institucional, expansão territorial)")
def list_needs(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT id::text AS id, solution_id::text AS solution_id, need_type, detail, amount_cents, territory, status, created_at FROM proponent_needs"
                                 " WHERE org_id = $1 ORDER BY created_at DESC", ctx.org_id)}


@route("POST", "/v1/institutional/needs", body=S.ProponentNeedIn, min_role="member", status=201, tags=T, summary="Declara uma necessidade (alimenta o match; não é compromisso de ninguém)")
def add_need(ctx: Ctx, body: S.ProponentNeedIn):
    d = body.model_dump()
    with ctx.tx() as c:
        if d["solution_id"] and not c.one("SELECT 1 FROM solutions WHERE id = $1 AND org_id = $2", d["solution_id"], ctx.org_id):
            raise not_found("Solução")
        nid = c.scalar("INSERT INTO proponent_needs(org_id, solution_id, need_type, detail, amount_cents, territory, created_by) VALUES ($1,$2::uuid,$3,$4,$5::bigint,$6,$7) RETURNING id::text",
                       ctx.org_id, d["solution_id"], d["need_type"], d["detail"], d["amount_cents"], d["territory"], ctx.user_id)
        ctx.audit(c, "inst.need_declared", "need", nid, {"type": d["need_type"]})
    return {"id": nid}


@route("PATCH", "/v1/institutional/needs/{need_id}", body=S.ProponentNeedPatch, min_role="member", tags=T)
def patch_need(ctx: Ctx, body: S.ProponentNeedPatch):
    d = body.model_dump(exclude_unset=True)
    if not d:
        raise ApiError(422, "empty", "Nada para atualizar")
    with ctx.tx() as c:
        sets, vals = [], [ctx.path["need_id"], ctx.org_id]
        for k, v in d.items():
            vals.append(v)
            sets.append(f"{k} = ${len(vals)}" + ("::bigint" if k == "amount_cents" else ""))
        if not c.run(f"UPDATE proponent_needs SET {', '.join(sets)}, updated_at = now() WHERE id = $1 AND org_id = $2", *vals):
            raise not_found("Necessidade")
    return {"ok": True}


@route("DELETE", "/v1/institutional/needs/{need_id}", min_role="member", tags=T)
def delete_need(ctx: Ctx):
    with ctx.tx() as c:
        if not c.run("DELETE FROM proponent_needs WHERE id = $1 AND org_id = $2", ctx.path["need_id"], ctx.org_id):
            raise not_found("Necessidade")
    return None
