"""Candidaturas: candidatura assistida (OSC → edital/programa), interesse do financiador (empresa → projeto),
acompanhamento de editais externos, checklist passo a passo, transições, conflito de interesse e aportes registrados."""
from __future__ import annotations

from ..http import ApiError, Ctx, not_found, page, route
from ..services import matching, risk, workflow
from ..services.audit import ledger
from . import schemas as S
from ..clock import today as _hoje_utc  # data do produto é UTC; ver impacto/clock.py

T = ("applications",)
APP_COLS = ("a.id::text AS id, a.call_id::text AS call_id, a.project_id::text AS project_id, a.osc_org_id::text AS osc_org_id,"
            " a.funder_org_id::text AS funder_org_id, a.origin, a.status, a.requested_cents, a.external_protocol, a.submitted_at,"
            " a.decided_at, a.decision_note, a.created_at, a.updated_at")


class AppListQ(S.Pagination):
    status: str | None = None


@route("GET", "/v1/applications", query=AppListQ, min_role="viewer", tags=T,
       summary="Candidaturas da organização (enviadas pela OSC ou recebidas pelo financiador)")
def list_apps(ctx: Ctx, q: AppListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {APP_COLS}, c.title AS call_title, c.funder_name, c.closes_at, p.title AS project_title,"
                       " o.legal_name AS osc_name, org_display(a.funder_org_id) AS funder_org_name,"
                       " (SELECT count(*) FROM application_steps s WHERE s.application_id = a.id AND s.mandatory) AS steps_total,"
                       " (SELECT count(*) FROM application_steps s WHERE s.application_id = a.id AND s.mandatory AND s.status IN ('done','not_applicable')) AS steps_done"
                       " FROM applications a LEFT JOIN calls c ON c.id = a.call_id LEFT JOIN projects p ON p.id = a.project_id"
                       " JOIN organizations o ON o.id = a.osc_org_id LEFT JOIN organizations f ON f.id = a.funder_org_id"
                       " WHERE (a.osc_org_id = $1 OR a.funder_org_id = $1) AND ($2::text IS NULL OR a.status = $2)"
                       " ORDER BY a.updated_at DESC LIMIT $3 OFFSET $4", ctx.org_id, q.status, q.limit + 1, q.offset)
    for r in rows:
        r["status_label"] = workflow.LABELS.get(r["status"], r["status"])
        r["side"] = "osc" if r["osc_org_id"] == ctx.org_id else "funder"
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/applications", body=S.ApplyIn, kinds=("osc",), min_role="member", status=201, tags=T,
       summary="Inicia candidatura assistida (plataforma) ou acompanhamento de edital externo, com checklist gerado dos requisitos")
def apply(ctx: Ctx, body: S.ApplyIn):
    with ctx.tx() as c:
        risk.ensure_not_blocked(c, ctx.org_id)
        call = c.one("SELECT c.*, c.id::text AS id, c.owner_org_id::text AS owner_org_id FROM calls c WHERE c.id = $1", body.call_id)
        if not call:
            raise not_found("Edital/chamada")
        if body.project_id and not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", body.project_id, ctx.org_id):
            raise not_found("Projeto")
        external = body.track_external or not call["managed_on_platform"] or not call["owner_org_id"]
        if not external and call["status"] != "open":
            raise ApiError(409, "call_not_open", "Chamada não está aberta para candidaturas")
        origin = "external_tracking" if external else "osc_application"
        docs = {d["doc_type"] for d in matching.load_documents(c, ctx.org_id, body.project_id)
                if d["status"] == "clean" and (d["valid_until"] is None or str(d["valid_until"]) >= _today())}
        aid = c.scalar("INSERT INTO applications(call_id, project_id, osc_org_id, funder_org_id, origin, status, requested_cents, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,'draft',$6::bigint,$7) RETURNING id::text", call["id"], body.project_id, ctx.org_id,
                       None if external else call["owner_org_id"], origin, body.requested_cents, ctx.user_id)
        workflow.insert_steps(c, aid, workflow.build_steps(call, origin, docs))
        workflow.record_transition(c, ctx, {"id": aid, "status": None}, "draft", "Candidatura iniciada")
        ctx.audit(c, "application.created", "application", aid, {"origin": origin, "call": call["id"]})
    return {"id": aid, "origin": origin, "status": "draft"}


@route("POST", "/v1/applications/interest", body=S.InterestIn, kinds=("company", "individual"), min_role="analyst", status=201, tags=T,
       summary="Financiador manifesta interesse em projeto publicado (OSC aceita para iniciar a diligência)")
def interest(ctx: Ctx, body: S.InterestIn):
    with ctx.tx() as c:
        p = c.one("SELECT id::text AS id, org_id::text AS org_id, visibility FROM projects WHERE id = $1", body.project_id)
        if not p or p["visibility"] != "published":
            raise not_found("Projeto publicado")
        if body.call_id and not c.one("SELECT 1 FROM calls WHERE id = $1 AND owner_org_id = $2", body.call_id, ctx.org_id):
            raise not_found("Programa")
        proj = matching.load_project(c, p["id"])
        m = matching.evaluate_funder_project(c, ctx.org_id, proj, matching.load_call(c, body.call_id) if body.call_id else None)
        if m["eligibility"] == "blocked":
            raise ApiError(409, "blocked_by_policy", "Projeto bloqueado pelos critérios do programa/política",
                           {"blockers": [b["message"] for b in m["blockers"]]})
        aid = c.scalar("INSERT INTO applications(call_id, project_id, osc_org_id, funder_org_id, origin, status, created_by)"
                       " VALUES ($1,$2,$3,$4,'funder_interest','interest',$5) RETURNING id::text",
                       body.call_id, p["id"], p["org_id"], ctx.org_id, ctx.user_id)
        workflow.insert_steps(c, aid, [
            {"code": "osc_accept", "title": "OSC aceita iniciar a diligência", "kind": "followup", "description": None, "mandatory": True, "status": "todo"},
            {"code": "documents", "title": "Compartilhar documentos institucionais e do projeto", "kind": "document", "description": None, "mandatory": True, "status": "todo"},
            {"code": "work_plan", "title": "Plano de trabalho e cronograma de marcos", "kind": "writing", "description": None, "mandatory": True, "status": "todo"},
            {"code": "conflict", "title": "Declaração de conflito de interesse (financiador)", "kind": "requirement", "description": None, "mandatory": True, "status": "todo"},
            {"code": "decision", "title": "Decisão do financiador e registro do aporte", "kind": "followup", "description": None, "mandatory": True, "status": "todo"}])
        workflow.record_transition(c, ctx, {"id": aid, "status": None}, "interest", body.note)
        matching.persist(c, ctx.org_id, ctx.user_id, m, body.call_id, p["id"])
        ledger(c, project_id=p["id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="interest_registered", ref_type="application",
               ref_id=aid, payload={"funder": ctx.principal.org_name})
        c.scalar("SELECT app_notify($1, NULL, 'interest', $2, $3, $4)", p["org_id"], "Novo interesse em seu projeto",
                 f"{ctx.principal.org_name} manifestou interesse. Aceite para iniciar a diligência.", f"/candidaturas/{aid}")
        ctx.audit(c, "application.interest", "application", aid, {"project": p["id"]})
    return {"id": aid, "status": "interest"}


def _today() -> str:
    return _hoje_utc().isoformat()


@route("GET", "/v1/applications/{application_id}", min_role="viewer", tags=T,
       summary="Detalhe: checklist passo a passo, linha do tempo, compatibilidade, aportes e documentos compartilhados")
def get_app(ctx: Ctx):
    aid = ctx.path["application_id"]
    with ctx.tx(readonly=True) as c:
        a = c.one(f"SELECT {APP_COLS}, c.title AS call_title, c.funder_name, c.url AS call_url, c.closes_at, c.sphere,"
                  " p.title AS project_title, o.legal_name AS osc_name, o.compliance_status AS osc_compliance, org_display(a.funder_org_id) AS funder_org_name"
                  " FROM applications a LEFT JOIN calls c ON c.id = a.call_id LEFT JOIN projects p ON p.id = a.project_id"
                  " JOIN organizations o ON o.id = a.osc_org_id LEFT JOIN organizations f ON f.id = a.funder_org_id WHERE a.id = $1", aid)
        if not a:
            raise not_found("Candidatura")
        a["status_label"] = workflow.LABELS.get(a["status"])
        a["side"] = workflow.actor_side(ctx, a)
        a["next_transitions"] = [{"to": k, "label": workflow.LABELS.get(k, k), "by": v} for k, v in workflow.allowed(a).items()
                                 if v in (a["side"], "any")]
        a["steps"] = c.query("SELECT id::text AS id, seq, code, title, description, kind, status, mandatory, due_on,"
                             " document_id::text AS document_id, note, completed_at FROM application_steps WHERE application_id = $1 ORDER BY seq", aid)
        a["timeline"] = c.query("SELECT t.from_status, t.to_status, t.note, t.at, o.legal_name AS actor_org FROM application_transitions t"
                                " LEFT JOIN organizations o ON o.id = t.actor_org_id WHERE t.application_id = $1 ORDER BY t.at", aid)
        a["commitments"] = c.query("SELECT id::text AS id, amount_cents, status, milestone_id::text AS milestone_id, reference, disbursed_at,"
                                   " confirmed_at, created_at FROM commitments WHERE application_id = $1 ORDER BY created_at", aid)
        a["my_conflict_declaration"] = c.one("SELECT has_conflict, description, declared_at FROM conflict_declarations"
                                             " WHERE application_id = $1 AND user_id = $2", aid, ctx.user_id)
        if a["project_id"]:
            a["documents"] = c.query("SELECT id::text AS id, doc_type, title, status, valid_until, created_at FROM documents"
                                     " WHERE org_id = $1 AND deleted_at IS NULL AND (project_id IS NULL OR project_id = $2)"
                                     " ORDER BY created_at DESC LIMIT 100", a["osc_org_id"], a["project_id"])
        if a["call_id"] and a["side"] == "osc":
            call = matching.load_call(c, a["call_id"])
            a["match"] = matching.evaluate_osc_call(c, ctx.org_id, call, a["project_id"])
    return a


@route("POST", "/v1/applications/{application_id}/transition", body=S.TransitionIn, min_role="member", tags=T,
       summary="Avança/retrocede o status conforme a máquina de estados (validações e devolutiva obrigatória na reprovação)")
def transition(ctx: Ctx, body: S.TransitionIn):
    return workflow.transition(ctx, ctx.path["application_id"], body.to_status, body.note, body.external_protocol)


@route("PATCH", "/v1/applications/{application_id}/steps/{step_id}", body=S.StepPatch, min_role="member", tags=T,
       summary="Atualiza uma etapa do checklist (passo a passo)")
def patch_step(ctx: Ctx, body: S.StepPatch):
    with ctx.tx() as c:
        a = c.one("SELECT id::text AS id, osc_org_id::text AS osc_org_id, status FROM applications WHERE id = $1", ctx.path["application_id"])
        if not a:
            raise not_found("Candidatura")
        st = c.one("SELECT id, code, kind, mandatory FROM application_steps WHERE id = $1 AND application_id = $2", ctx.path["step_id"], a["id"])
        if not st:
            raise not_found("Etapa")
        if body.status == "not_applicable" and st["mandatory"]:
            raise ApiError(409, "mandatory_step", "Etapa obrigatória não pode ser marcada como não aplicável")
        if body.document_id and not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2", body.document_id, ctx.org_id):
            raise not_found("Documento")
        if st["kind"] == "signature" and body.status == "done":
            signed = c.scalar("SELECT count(*) FROM signatures s WHERE s.signer_org_id = $1 AND s.role = 'legal_representative'"
                              " AND ((s.subject_type = 'draft' AND s.subject_id IN (SELECT id FROM drafts WHERE application_id = $2))"
                              "   OR (s.subject_type = 'document' AND s.subject_id IN (SELECT id FROM documents WHERE application_id = $2)))",
                              ctx.org_id, a["id"])
            if not signed:
                raise ApiError(409, "signature_required", "Assine um rascunho ou documento desta candidatura como representante legal")
        c.run("UPDATE application_steps SET status = $2, note = coalesce($3, note), document_id = coalesce($4::uuid, document_id),"
              " completed_at = CASE WHEN $2 = 'done' THEN now() ELSE NULL END, completed_by = CASE WHEN $2 = 'done' THEN $5::uuid ELSE NULL END"
              " WHERE id = $1", st["id"], body.status, body.note, body.document_id, ctx.user_id)
        ctx.audit(c, "application.step_updated", "application", a["id"], {"step": st["code"], "status": body.status})
    return {"id": ctx.path["step_id"], "status": body.status}


@route("POST", "/v1/applications/{application_id}/conflict", body=S.ConflictIn, kinds=("company", "government", "individual"), min_role="analyst", tags=T,
       summary="Declaração de conflito de interesse do avaliador (obrigatória antes de aprovar)")
def conflict(ctx: Ctx, body: S.ConflictIn):
    with ctx.tx() as c:
        a = c.one("SELECT id::text AS id FROM applications WHERE id = $1 AND funder_org_id = $2", ctx.path["application_id"], ctx.org_id)
        if not a:
            raise not_found("Candidatura")
        c.run("INSERT INTO conflict_declarations(application_id, user_id, org_id, has_conflict, description) VALUES ($1,$2,$3,$4::bool,$5)"
              " ON CONFLICT (application_id, user_id) DO UPDATE SET has_conflict = EXCLUDED.has_conflict, description = EXCLUDED.description,"
              " declared_at = now()", a["id"], ctx.user_id, ctx.org_id, body.has_conflict, body.description)
        c.run("UPDATE application_steps SET status = 'done', completed_at = now(), completed_by = $2 WHERE application_id = $1 AND code = 'conflict'",
              a["id"], ctx.user_id)
        ctx.audit(c, "application.conflict_declared", "application", a["id"], {"has_conflict": body.has_conflict})
    return {"has_conflict": body.has_conflict}


# ------------------------------------------------------------------------------------------------ aportes (sem custódia)
@route("POST", "/v1/applications/{application_id}/commitments", body=S.CommitmentIn, kinds=("company", "government", "individual"), min_role="manager",
       status=201, tags=("funding",), summary="Registra aporte comprometido (o dinheiro NÃO passa pela plataforma)")
def commit(ctx: Ctx, body: S.CommitmentIn):
    with ctx.tx() as c:
        risk.ensure_not_blocked(c, ctx.org_id)
        a = c.one(f"SELECT {APP_COLS} FROM applications a WHERE a.id = $1 AND a.funder_org_id = $2 FOR UPDATE", ctx.path["application_id"], ctx.org_id)
        if not a:
            raise not_found("Candidatura")
        if a["status"] not in ("approved", "committed", "in_execution"):
            raise ApiError(409, "not_approved", "Aporte só pode ser registrado após a aprovação")
        if not a["project_id"]:
            raise ApiError(422, "project_required", "Candidatura sem projeto vinculado")
        cid = c.scalar("INSERT INTO commitments(application_id, project_id, milestone_id, funder_org_id, osc_org_id, amount_cents, reference, created_by)"
                       " VALUES ($1,$2,$3,$4,$5,$6::bigint,$7,$8) RETURNING id::text", a["id"], a["project_id"], body.milestone_id,
                       ctx.org_id, a["osc_org_id"], body.amount_cents, body.reference, ctx.user_id)
        if a["status"] == "approved":
            workflow.record_transition(c, ctx, a, "committed", "Aporte registrado")
            c.run("UPDATE applications SET status = 'committed' WHERE id = $1", a["id"])
        ledger(c, project_id=a["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type="funding_committed",
               amount_cents=body.amount_cents, ref_type="commitment", ref_id=cid, payload={"milestone": body.milestone_id})
        c.scalar("SELECT app_notify($1, NULL, 'funding', $2, $3, $4)", a["osc_org_id"], "Aporte registrado",
                 f"{ctx.principal.org_name} registrou um aporte de R$ {body.amount_cents / 100:,.2f}.", f"/candidaturas/{a['id']}")
        ctx.audit(c, "funding.committed", "commitment", cid, {"amount_cents": body.amount_cents})
    with ctx.system_tx() as c:
        c.run("UPDATE projects SET status = CASE WHEN (SELECT committed_cents FROM project_funding($1)) >= budget_total_cents"
              " THEN 'funded' ELSE 'funding' END WHERE id = $1 AND status IN ('published','funding','funded')", a["project_id"])
    return {"id": cid}


@route("POST", "/v1/commitments/{commitment_id}/status", body=S.CommitmentStatusIn, min_role="manager", tags=("funding",),
       summary="Financiador informa desembolso/cancelamento; OSC confirma o recebimento")
def commitment_status(ctx: Ctx, body: S.CommitmentStatusIn):
    with ctx.tx() as c:
        cm = c.one("SELECT id::text AS id, project_id::text AS project_id, osc_org_id::text AS osc_org_id, funder_org_id::text AS funder_org_id,"
                   " status, amount_cents FROM commitments WHERE id = $1 FOR UPDATE", ctx.path["commitment_id"])
        if not cm:
            raise not_found("Aporte")
        valid = {("pledged", "disbursed"), ("pledged", "cancelled"), ("disbursed", "confirmed")}
        if (cm["status"], body.status) not in valid:
            raise ApiError(409, "invalid_transition", f"Não é possível passar de {cm['status']} para {body.status}")
        c.run("UPDATE commitments SET status = $2, reference = coalesce($3, reference),"
              " disbursed_at = CASE WHEN $2 = 'disbursed' THEN now() ELSE disbursed_at END,"
              " confirmed_at = CASE WHEN $2 = 'confirmed' THEN now() ELSE confirmed_at END WHERE id = $1", cm["id"], body.status, body.reference)
        entry = {"disbursed": "disbursement_reported", "confirmed": "disbursement_confirmed"}.get(body.status)
        if entry:
            ledger(c, project_id=cm["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type=entry, amount_cents=cm["amount_cents"],
                   ref_type="commitment", ref_id=cm["id"], payload={"reference": body.reference})
        target = cm["osc_org_id"] if ctx.org_id == cm["funder_org_id"] else cm["funder_org_id"]
        c.scalar("SELECT app_notify($1, NULL, 'funding', $2, $3, $4)", target, "Atualização de aporte", f"Status: {body.status}",
                 f"/projetos/{cm['project_id']}")
        ctx.audit(c, "funding.status_changed", "commitment", cm["id"], {"to": body.status})
    return {"id": cm["id"], "status": body.status}
