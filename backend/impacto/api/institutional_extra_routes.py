"""v0.10.1 — perfis institucionais (OS, OSCIP, OSC, iniciativa em estruturação), instrumentos de parceria/contratos de gestão, trilha de formalização
e pedidos de mentoria. Declarado ≠ verificado: instrumentos nascem declarados e só a administração os verifica."""
from __future__ import annotations

from datetime import date

from ..engines.institutional import formalization as form
from ..engines.institutional import persona as pers
from ..http import ApiError, Ctx, not_found, page, route
from ..services import documents as docsvc
from ..services import institutional as svc
from . import schemas as S

T = ("institutional",)
AG_COLS = ("a.id::text AS id, a.org_id::text AS org_id, a.agreement_type, a.counterpart_name, a.counterpart_authority, a.instrument_number, a.object_summary,"
           " a.start_date, a.end_date, a.value_cents, a.agreement_status, a.qualification_id::text AS qualification_id, a.verification_url, a.document_id::text AS document_id,"
           " a.verification_status, a.validation_date, a.validation_note, a.created_at, a.updated_at")


def A(method, path, **kw):
    return route(method, path, auth="admin", tags=("admin", "institutional"), **kw)


def _own_quals(c, org_id: str) -> list[dict]:
    return c.query("SELECT id::text AS id, qualification_type, verification_status, issuing_authority, certificate_number, protocol, expiration_date, areas"
                   " FROM organization_qualifications WHERE org_id = $1 ORDER BY created_at", org_id)


def _check_agreement(c, ctx: Ctx, d: dict) -> None:
    if d.get("start_date") and d.get("end_date") and d["end_date"] < d["start_date"]:
        raise ApiError(422, "dates_invalid", "A data final não pode ser anterior à inicial")
    if d.get("document_id") and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", d["document_id"], ctx.org_id):
        raise not_found("Documento")
    if d.get("qualification_id") and not c.one("SELECT 1 FROM organization_qualifications WHERE id = $1 AND org_id = $2", d["qualification_id"], ctx.org_id):
        raise not_found("Qualificação")


# ------------------------------------------------------------------------------------------------ instrumentos (contratos de gestão, termos)
@route("GET", "/v1/institutional/agreements", min_role="viewer", tags=T, summary="Instrumentos firmados (contrato de gestão, termo de parceria/fomento/colaboração…) com alertas de vigência")
def list_agreements(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {AG_COLS} FROM organization_agreements a WHERE a.org_id = $1 ORDER BY a.end_date NULLS LAST, a.created_at DESC", ctx.org_id)
    today = date.today()
    return {"items": [pers.agreement_view(r, today) for r in rows],
            "note": "Instrumentos são DECLARADOS pela organização até a administração verificar o documento comprobatório."}


@route("POST", "/v1/institutional/agreements", body=S.AgreementIn, min_role="manager", status=201, tags=T,
       summary="Registra um instrumento. Nasce 'declarado' (ou 'comprovante enviado' com documento); só a administração verifica.")
def add_agreement(ctx: Ctx, body: S.AgreementIn):
    d = body.model_dump()
    with ctx.tx() as c:
        _check_agreement(c, ctx, d)
        aid = c.scalar("INSERT INTO organization_agreements(org_id, agreement_type, counterpart_name, counterpart_authority, instrument_number, object_summary, start_date, end_date,"
                       " value_cents, agreement_status, qualification_id, verification_url, document_id, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7::date,$8::date,$9,$10,$11::uuid,$12,$13::uuid,$14)"
                       " RETURNING id::text", ctx.org_id, d["agreement_type"], d["counterpart_name"], d["counterpart_authority"], d["instrument_number"], d["object_summary"],
                       d["start_date"], d["end_date"], d["value_cents"], d["agreement_status"], d["qualification_id"], d["verification_url"], d["document_id"], ctx.user_id)
        ctx.audit(c, "inst.agreement_declared", "agreement", aid, {"type": d["agreement_type"]})
        row = c.one(f"SELECT {AG_COLS} FROM organization_agreements a WHERE a.id = $1", aid)
    return pers.agreement_view(row, date.today())


@route("PATCH", "/v1/institutional/agreements/{agreement_id}", body=S.AgreementPatch, min_role="manager", tags=T,
       summary="Edita o instrumento. Alterar dados comprobatórios de um instrumento verificado o devolve a 'declarado'/'comprovante enviado'.")
def patch_agreement(ctx: Ctx, body: S.AgreementPatch):
    d = body.model_dump(exclude_unset=True)
    if not d:
        raise ApiError(422, "empty", "Nada para atualizar")
    aid = ctx.path["agreement_id"]
    with ctx.tx() as c:
        cur = c.one("SELECT start_date, end_date, verification_status FROM organization_agreements WHERE id = $1 AND org_id = $2 FOR UPDATE", aid, ctx.org_id)
        if not cur:
            raise not_found("Instrumento")
        if cur["verification_status"] == "rejected":
            raise ApiError(409, "closed", "Instrumento rejeitado não pode ser editado; registre um novo.")
        _check_agreement(c, ctx, {"start_date": cur["start_date"], "end_date": cur["end_date"], **d})
        sets, vals = [], [aid]
        for k, v in d.items():
            vals.append(v)
            sets.append(f"{k} = ${len(vals)}" + {"start_date": "::date", "end_date": "::date", "document_id": "::uuid", "qualification_id": "::uuid"}.get(k, ""))
        c.run(f"UPDATE organization_agreements SET {', '.join(sets)} WHERE id = $1", *vals)
        ctx.audit(c, "inst.agreement_edited", "agreement", aid, {"fields": sorted(d)})
        row = c.one(f"SELECT {AG_COLS} FROM organization_agreements a WHERE a.id = $1", aid)
    return pers.agreement_view(row, date.today())


@route("DELETE", "/v1/institutional/agreements/{agreement_id}", min_role="manager", tags=T, summary="Remove instrumento ainda não verificado")
def delete_agreement(ctx: Ctx):
    with ctx.tx() as c:
        n = c.run("DELETE FROM organization_agreements WHERE id = $1 AND org_id = $2 AND verification_status IN ('declared','document_submitted','rejected')", ctx.path["agreement_id"], ctx.org_id)
        if not n:
            raise ApiError(409, "not_deletable", "Instrumento inexistente ou já verificado — fale com a administração.")
        ctx.audit(c, "inst.agreement_deleted", "agreement", ctx.path["agreement_id"])
    return None


# ------------------------------------------------------------------------------------------------ visões por perfil
@route("GET", "/v1/institutional/persona", min_role="viewer", tags=T,
       summary="Visões por perfil (OS, OSCIP, OSC, iniciativa em estruturação): qualificações, autoridade, áreas, instrumentos, alertas de validade e próximos passos")
def persona(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        facts = svc.facts(c, ctx.org_id)
        if not facts:
            raise not_found("Organização")
        quals = _own_quals(c, ctx.org_id)
        ags = c.query(f"SELECT {AG_COLS} FROM organization_agreements a WHERE a.org_id = $1", ctx.org_id)
        mods = {}
        profiles = pers.profile_of(facts, quals)
        if any(p in ("os", "oscip") for p in profiles):
            m = svc.maturity(c, ctx.org_id, facts)
            for code in svc.catalog(c, "funding_modality").get("funding_modality", {}):
                mods[code] = svc.evaluate_for_modality(c, ctx.org_id, code, f=facts, m=m)
    today = date.today()
    views = [pers.view(p, facts, quals, ags, today) for p in profiles if p != "structuring"]
    if "structuring" in profiles:
        views.append({"profile": "structuring", "see": "/v1/institutional/formalization", "next_steps": ["Siga a trilha de formalização e peça mentoria se precisar."],
                      "disclaimer": "Iniciativas em estruturação podem participar do Banco de Ideias e seguir a trilha de formalização; o acesso a recursos depende de cada oportunidade."})
    return {"profiles": profiles, "views": views,
            "modalities": [{"code": k, "state": v["state"], "state_label": v["state_label"], "missing": [r["label"] for r in v["requirements"] if r["status"] != "met"]} for k, v in sorted(mods.items())],
            "note": "Estados de modalidade são análises de apoio com as regras publicadas; não são parecer jurídico."}


# ------------------------------------------------------------------------------------------------ trilha de formalização
@route("GET", "/v1/institutional/formalization", min_role="viewer", tags=T, summary="Trilha de formalização: etapas derivadas dos dados + etapas declaradas, progresso e próxima etapa")
def formalization(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        facts = svc.facts(c, ctx.org_id)
        if not facts:
            raise not_found("Organização")
        manual = {r["step_code"]: r for r in c.query("SELECT step_code, state, note FROM formalization_steps WHERE org_id = $1", ctx.org_id)}
        has_project = bool(c.scalar("SELECT EXISTS (SELECT 1 FROM projects WHERE org_id = $1)", ctx.org_id))
        mentoring = c.query("SELECT id::text AS id, topic, status, created_at FROM mentoring_requests WHERE org_id = $1 AND status IN ('open','in_progress','scheduled') ORDER BY created_at DESC", ctx.org_id)
    out = form.compute(facts, manual, has_project)
    out["open_mentoring"] = mentoring
    return out


@route("PUT", "/v1/institutional/formalization/{step_code}", body=S.FormalizationStepIn, min_role="manager", tags=T,
       summary="Declara o andamento de uma etapa MANUAL (etapas automáticas não são editáveis)")
def set_step(ctx: Ctx, body: S.FormalizationStepIn):
    code = ctx.path["step_code"]
    if code not in form.manual_codes():
        raise ApiError(422, "step_not_manual", "Etapa inexistente ou derivada automaticamente dos dados.", {"valid": sorted(form.manual_codes())})
    with ctx.tx() as c:
        c.run("INSERT INTO formalization_steps(org_id, step_code, state, note, updated_by) VALUES ($1,$2,$3,$4,$5)"
              " ON CONFLICT (org_id, step_code) DO UPDATE SET state = EXCLUDED.state, note = EXCLUDED.note, updated_by = EXCLUDED.updated_by, updated_at = now()",
              ctx.org_id, code, body.state, body.note, ctx.user_id)
        ctx.audit(c, "inst.formalization_step", "organization", ctx.org_id, {"step": code, "state": body.state})
    return {"step_code": code, "state": body.state, "basis": "DECLARADO PELA ORGANIZAÇÃO"}


# ------------------------------------------------------------------------------------------------ mentoria
@route("GET", "/v1/institutional/mentoring", min_role="viewer", tags=T, summary="Pedidos de mentoria da organização")
def list_mentoring(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, topic, message, status, admin_note, created_at, updated_at FROM mentoring_requests WHERE org_id = $1 ORDER BY created_at DESC LIMIT 50", ctx.org_id)
    return {"items": rows, "note": "Atendimento humano, sem prazo garantido. O andamento é registrado pela equipe."}


@route("POST", "/v1/institutional/mentoring", body=S.MentoringIn, min_role="member", status=201, rate=("mentoring", 5, 3600), tags=T, summary="Pede mentoria (formalização, documentos, projeto, captação, prestação de contas)")
def request_mentoring(ctx: Ctx, body: S.MentoringIn):
    with ctx.tx() as c:
        n = c.scalar("SELECT count(*) FROM mentoring_requests WHERE org_id = $1 AND status IN ('open','in_progress')", ctx.org_id)
        if n >= 5:
            raise ApiError(429, "too_many_open", "Já existem 5 pedidos em aberto; aguarde o atendimento ou cancele algum.")
        mid = c.scalar("INSERT INTO mentoring_requests(org_id, topic, message, created_by) VALUES ($1,$2,$3,$4) RETURNING id::text", ctx.org_id, body.topic, body.message, ctx.user_id)
        ctx.audit(c, "inst.mentoring_requested", "mentoring", mid, {"topic": body.topic})
        row = c.one("SELECT id::text AS id, topic, message, status, created_at FROM mentoring_requests WHERE id = $1", mid)
    return row


@route("POST", "/v1/institutional/mentoring/{mentoring_id}/cancel", min_role="member", tags=T, summary="Cancela um pedido de mentoria em aberto")
def cancel_mentoring(ctx: Ctx):
    with ctx.tx() as c:
        n = c.run("UPDATE mentoring_requests SET status = 'cancelled' WHERE id = $1 AND org_id = $2 AND status IN ('open','in_progress','scheduled')", ctx.path["mentoring_id"], ctx.org_id)
        if not n:
            raise ApiError(409, "not_cancellable", "Pedido inexistente ou já encerrado")
        ctx.audit(c, "inst.mentoring_cancelled", "mentoring", ctx.path["mentoring_id"])
    return {"status": "cancelled"}


# ------------------------------------------------------------------------------------------------ administração
@A("GET", "/v1/admin/institutional/agreements", query=S.AgreementAdminQ, summary="Fila de verificação de instrumentos (padrão: comprovante enviado)")
def agreement_queue(ctx: Ctx, q: S.AgreementAdminQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {AG_COLS}, o.legal_name AS org_name, o.cnpj, d.validation_status AS document_validation FROM organization_agreements a"
                       " JOIN organizations o ON o.id = a.org_id LEFT JOIN documents d ON d.id = a.document_id"
                       " WHERE ($1::text IS NULL OR a.verification_status = $1) ORDER BY a.updated_at LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    today = date.today()
    return page([pers.agreement_view(r, today) for r in rows], q.limit, q.offset)


@A("POST", "/v1/admin/institutional/agreements/{agreement_id}/decide", body=S.AgreementDecisionIn,
   summary="Verifica ou rejeita o instrumento. Verificar exige número, documento VALIDADO ou URL oficial, e nota.")
def agreement_decide(ctx: Ctx, body: S.AgreementDecisionIn):
    today = date.today()
    with ctx.tx() as c:
        a = c.one("SELECT a.*, a.id::text AS id, a.org_id::text AS org_id, d.validation_status AS doc_validation, d.status AS doc_scan, d.valid_until AS doc_valid_until"
                  " FROM organization_agreements a LEFT JOIN documents d ON d.id = a.document_id WHERE a.id = $1 FOR UPDATE OF a", ctx.path["agreement_id"])
        if not a:
            raise not_found("Instrumento")
        note = body.note.strip()
        if body.decision == "verify":
            if a["verification_status"] in ("verified", "rejected"):
                raise ApiError(409, "invalid_transition", "Estado atual não permite verificação")
            gaps = []
            if not a["instrument_number"]:
                gaps.append("número do instrumento")
            doc_ok = bool(a["document_id"] and a["doc_validation"] == "validated" and a["doc_scan"] in docsvc.usable_statuses()
                          and not (a["doc_valid_until"] and a["doc_valid_until"] < today))
            if not (doc_ok or a["verification_url"]):
                gaps.append("documento comprobatório VALIDADO ou URL de verificação oficial")
            if gaps:
                raise ApiError(422, "verification_requirements", "Não é possível verificar: faltam " + "; ".join(gaps), {"missing": gaps})
            c.run("UPDATE organization_agreements SET verification_status = 'verified', validated_by = $2, validation_date = $3::date, validation_note = $4 WHERE id = $1",
                  a["id"], ctx.user_id, today, note)
        else:
            if a["verification_status"] == "rejected":
                raise ApiError(409, "invalid_transition", "Já rejeitado")
            c.run("UPDATE organization_agreements SET verification_status = 'rejected', validated_by = NULL, validation_date = NULL, validation_note = $2 WHERE id = $1", a["id"], note)
        c.scalar("SELECT app_notify($1, NULL, 'agreement', $2, $3, '/instituicao')", a["org_id"], f"Instrumento {a.get('instrument_number') or ''}: {body.decision}".strip(), note)
        ctx.audit(c, f"inst.agreement_{body.decision}", "agreement", a["id"], {"org": a["org_id"], "note": note}, org_id=a["org_id"])
        out = c.one("SELECT verification_status, validation_date, validation_note FROM organization_agreements WHERE id = $1", a["id"])
    return out


@A("GET", "/v1/admin/institutional/mentoring", query=S.MentoringAdminQ, summary="Fila de pedidos de mentoria (padrão: abertos e em andamento)")
def mentoring_queue(ctx: Ctx, q: S.MentoringAdminQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT m.id::text AS id, m.org_id::text AS org_id, o.legal_name AS org_name, m.topic, m.message, m.status, m.admin_note, m.created_at, m.updated_at"
                       " FROM mentoring_requests m JOIN organizations o ON o.id = m.org_id"
                       " WHERE ($1::text IS NULL AND m.status IN ('open','in_progress','scheduled') OR m.status = $1) ORDER BY m.created_at LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("POST", "/v1/admin/institutional/mentoring/{mentoring_id}/update", body=S.MentoringAdminIn, summary="Atualiza o andamento do pedido de mentoria")
def mentoring_update(ctx: Ctx, body: S.MentoringAdminIn):
    with ctx.tx() as c:
        m = c.one("SELECT id::text AS id, org_id::text AS org_id FROM mentoring_requests WHERE id = $1 FOR UPDATE", ctx.path["mentoring_id"])
        if not m:
            raise not_found("Pedido de mentoria")
        c.run("UPDATE mentoring_requests SET status = $2, admin_note = $3, handled_by = $4 WHERE id = $1", m["id"], body.status, body.admin_note, ctx.user_id)
        c.scalar("SELECT app_notify($1, NULL, 'mentoring', $2, $3, '/instituicao')", m["org_id"], f"Mentoria: {body.status}", body.admin_note or "Andamento atualizado pela equipe")
        ctx.audit(c, "inst.mentoring_updated", "mentoring", m["id"], {"org": m["org_id"], "status": body.status}, org_id=m["org_id"])
    return {"status": body.status}
