"""Máquina de estados das candidaturas e checklist de candidatura assistida.

Fluxo (plataforma): Cadastro → Validação → Compliance → Match → Interesse/Candidatura → Triagem → Due Diligence →
Aprovação (com declaração de conflito) → Aporte registrado (sem custódia) → Execução → Prestação de contas → Encerramento.
Edital externo: a OSC acompanha o próprio processo (protocolo, resultado, execução, prestação de contas).
"""
from __future__ import annotations

from ..db.pq import Connection
from ..http import ApiError, Ctx
from . import matching
from .audit import ledger

PLATFORM = {
    "draft": {"submitted": "osc", "withdrawn": "osc"},
    "interest": {"due_diligence": "osc", "withdrawn": "any"},
    "submitted": {"screening": "funder", "rejected": "funder", "withdrawn": "osc"},
    "screening": {"due_diligence": "funder", "rejected": "funder", "withdrawn": "osc"},
    "due_diligence": {"approved": "funder", "rejected": "funder", "withdrawn": "osc"},
    "approved": {"rejected": "funder"},
    "committed": {"in_execution": "osc"},
    "in_execution": {"reporting": "osc"},
    "reporting": {"closed": "funder", "in_execution": "funder"},
}
EXTERNAL = {
    "draft": {"submitted": "osc", "withdrawn": "osc"},
    "submitted": {"approved": "osc", "rejected": "osc", "withdrawn": "osc"},
    "approved": {"in_execution": "osc"},
    "in_execution": {"reporting": "osc"},
    "reporting": {"closed": "osc"},
}
LABELS = {"interest": "Interesse do financiador", "draft": "Em preparação", "submitted": "Enviada", "screening": "Em triagem",
          "due_diligence": "Em diligência", "approved": "Aprovada", "rejected": "Não aprovada", "withdrawn": "Retirada",
          "committed": "Aporte registrado", "in_execution": "Em execução", "reporting": "Prestação de contas", "closed": "Encerrada"}


def allowed(app: dict) -> dict:
    table = EXTERNAL if app["origin"] == "external_tracking" else PLATFORM
    return table.get(app["status"], {})


def actor_side(ctx: Ctx, app: dict) -> str:
    if ctx.principal.org_id == app["osc_org_id"]:
        return "osc"
    if ctx.principal.org_id == app["funder_org_id"]:
        return "funder"
    return "none"


def build_steps(call: dict | None, origin: str, live_doc_types: set[str]) -> list[dict]:
    steps: list[dict] = []

    def add(code, title, kind, desc=None, mandatory=True, done=False):
        steps.append({"code": code, "title": title, "kind": kind, "description": desc, "mandatory": mandatory,
                      "status": "done" if done else "todo"})

    add("requirements", "Conferir requisitos e pré-requisitos do edital", "requirement",
        "Revise a análise de compatibilidade: requisitos atendidos, pendentes e riscos.")
    for dt in (call or {}).get("required_document_types") or []:
        add(f"doc_{dt}", f"Documento obrigatório: {matching_label(dt)}", "document",
            "Envie o documento atualizado ao cofre (verificação antivírus e validade).", done=dt in live_doc_types)
    for item in (call or {}).get("requirements") or []:
        if isinstance(item, dict) and item.get("code"):
            add(f"req_{item['code']}", str(item.get("label"))[:200], "requirement", item.get("detail"), bool(item.get("mandatory", True)))
    add("proposal", "Redigir a proposta (rascunho assistido por IA, revisado pela equipe)", "writing")
    add("budget", "Orçamento detalhado e cronograma de marcos", "writing")
    add("professional_review", "Validação por profissional habilitado (contábil/jurídica/projetos)", "review",
        "Solicite a revisão a um profissional parceiro com credencial verificada.", mandatory=False)
    add("signature", "Assinatura do representante legal", "signature")
    if origin == "external_tracking":
        url = (call or {}).get("url") or "portal do financiador"
        add("submission", "Protocolar no portal oficial e registrar o número do protocolo", "submission", f"Envio em: {url}")
    else:
        add("submission", "Enviar a candidatura pela plataforma", "submission")
    add("followup", "Acompanhar resultado, prazos de recurso e assinatura do termo", "followup", mandatory=False)
    for t in (call or {}).get("steps_template") or []:
        if isinstance(t, dict) and t.get("code") and not any(s["code"] == t["code"] for s in steps):
            add(t["code"], t.get("title", t["code"]), t.get("kind", "writing"), t.get("description"), bool(t.get("mandatory", True)))
    return steps


def matching_label(code: str) -> str:
    from ..engines.match.engine import _doc_label
    return _doc_label(code)


def insert_steps(c: Connection, app_id: str, steps: list[dict]) -> None:
    for i, s in enumerate(steps, 1):
        c.run("INSERT INTO application_steps(application_id, seq, code, title, description, kind, status, mandatory)"
              " VALUES ($1,$2::int,$3,$4,$5,$6,$7,$8::bool)", app_id, i, s["code"], s["title"], s["description"], s["kind"],
              s["status"], s["mandatory"])


def record_transition(c: Connection, ctx: Ctx, app: dict, to: str, note: str | None) -> None:
    c.run("INSERT INTO application_transitions(application_id, from_status, to_status, actor_user_id, actor_org_id, note)"
          " VALUES ($1,$2,$3,$4,$5,$6)", app["id"], app.get("status"), to, ctx.user_id, ctx.org_id, note)


def notify_counterpart(c: Connection, ctx: Ctx, app: dict, title: str, body: str) -> None:
    target = app["funder_org_id"] if ctx.principal.org_id == app["osc_org_id"] else app["osc_org_id"]
    if target:
        c.scalar("SELECT app_notify($1, NULL, 'application', $2, $3, $4)", target, title, body, f"/candidaturas/{app['id']}")


def transition(ctx: Ctx, app_id: str, to: str, note: str | None, external_protocol: str | None) -> dict:
    with ctx.tx() as c:
        app = c.one("SELECT a.*, a.id::text AS id, a.osc_org_id::text AS osc_org_id, a.funder_org_id::text AS funder_org_id,"
                    " a.project_id::text AS project_id, a.call_id::text AS call_id FROM applications a WHERE a.id = $1 FOR UPDATE", app_id)
        if not app:
            raise ApiError(404, "not_found", "Candidatura não encontrada")
        side = actor_side(ctx, app)
        rule = allowed(app).get(to)
        if not rule:
            raise ApiError(409, "invalid_transition", f"Transição '{LABELS.get(app['status'])}' → '{LABELS.get(to, to)}' não permitida",
                           {"from": app["status"], "allowed": sorted(allowed(app))})
        if rule != "any" and rule != side:
            raise ApiError(403, "not_your_turn", "Esta etapa é conduzida pela outra parte")
        ctx.require_role("manager" if to in ("approved", "rejected", "closed", "submitted") else "member")
        if to == "rejected" and not note:
            raise ApiError(422, "note_required", "Informe a justificativa (devolutiva) da decisão")
        # Guardas -----------------------------------------------------------------------------------
        if to == "submitted":
            pending = c.query("SELECT title FROM application_steps WHERE application_id = $1 AND mandatory AND status NOT IN ('done','not_applicable')"
                              " AND code NOT IN ('submission','followup')", app["id"])
            if pending:
                raise ApiError(409, "checklist_incomplete", "Conclua as etapas obrigatórias antes de enviar",
                               {"pending": [p["title"] for p in pending]})
            if app["origin"] == "osc_application":
                if not app["project_id"]:
                    raise ApiError(422, "project_required", "Vincule um projeto à candidatura antes de enviar")
                call = matching.load_call(c, app["call_id"])
                m = matching.evaluate_osc_call(c, app["osc_org_id"], call, app["project_id"])
                if m["eligibility"] == "blocked":
                    raise ApiError(409, "requirements_unmet", "Há requisitos obrigatórios não atendidos",
                                   {"blockers": [b["message"] for b in m["blockers"]]})
                matching.persist(c, ctx.org_id, ctx.user_id, m, app["call_id"], app["project_id"])
        if to == "approved" and app["origin"] != "external_tracking":
            decl = c.one("SELECT has_conflict FROM conflict_declarations WHERE application_id = $1 AND user_id = $2", app["id"], ctx.user_id)
            if not decl:
                raise ApiError(409, "conflict_declaration_required", "Declare ausência (ou existência) de conflito de interesse antes de aprovar")
            if decl["has_conflict"]:
                raise ApiError(409, "conflict_of_interest", "Você declarou conflito de interesse: outro membro deve decidir")
            if c.scalar("SELECT compliance_status FROM organizations WHERE id = $1", app["osc_org_id"]) != "approved":
                raise ApiError(409, "osc_compliance_pending", "A OSC precisa ter o compliance aprovado antes da aprovação")
        if to == "closed" and app["origin"] != "external_tracking":
            if not c.scalar("SELECT count(*) FROM feedbacks WHERE project_id = $1 AND kind = 'final_report'", app["project_id"]):
                raise ApiError(409, "final_report_required", "A OSC precisa enviar o relatório final")
            if not c.scalar("SELECT count(*) FROM evidences WHERE project_id = $1 AND status = 'accepted'", app["project_id"]):
                raise ApiError(409, "evidence_required", "É necessário ao menos uma evidência aceita")
        # Efeitos -----------------------------------------------------------------------------------
        record_transition(c, ctx, app, to, note)
        c.run("UPDATE applications SET status = $2,"
              " submitted_at = CASE WHEN $2 = 'submitted' THEN now() ELSE submitted_at END,"
              " decided_at = CASE WHEN $2 IN ('approved','rejected') THEN now() ELSE decided_at END,"
              " decision_note = CASE WHEN $2 IN ('approved','rejected') THEN $3 ELSE decision_note END,"
              " external_protocol = coalesce($4, external_protocol) WHERE id = $1", app["id"], to, note, external_protocol)
        if to == "submitted":
            c.run("UPDATE application_steps SET status = 'done', completed_at = now(), completed_by = $2 WHERE application_id = $1"
                  " AND code = 'submission'", app["id"], ctx.user_id)
        if app["project_id"]:
            entry = {"submitted": "application_submitted", "approved": "application_approved", "closed": "project_completed"}.get(to)
            if entry and not (app["origin"] == "external_tracking" and entry == "application_submitted"):
                ledger(c, project_id=app["project_id"], org_id=ctx.org_id, actor=ctx.user_id, entry_type=entry,
                       ref_type="application", ref_id=app["id"], payload={"status": to, "external": app["origin"] == "external_tracking"})
            if to == "in_execution":
                c.run("UPDATE projects SET status = 'in_execution' WHERE id = $1 AND status IN ('published','funding','funded')"
                      " AND org_id = $2", app["project_id"], ctx.org_id)
        ctx.audit(c, "application.transition", "application", app["id"], {"from": app["status"], "to": to})
        notify_counterpart(c, ctx, app, f"Candidatura: {LABELS.get(to, to)}", note or f"Status atualizado para {LABELS.get(to, to)}")
    if to == "closed" and app["project_id"]:
        _maybe_complete_project(ctx, app)
    return {"id": app["id"], "status": to}


def _maybe_complete_project(ctx: Ctx, app: dict) -> None:
    """Encerra o projeto quando não restam candidaturas ativas (executado pela OSC dona, ou via sistema quando o financiador encerra)."""
    with ctx.system_tx() as c:
        still = c.scalar("SELECT count(*) FROM applications WHERE project_id = $1 AND status IN ('committed','in_execution','reporting')",
                         app["project_id"])
        if not still:
            c.run("UPDATE projects SET status = 'completed' WHERE id = $1 AND status = 'in_execution'", app["project_id"])
