"""Ciclo de vida do projeto: máquina de estados, transições registradas, linha de tempo e snapshots.

Antes desta versão, `projects.status` mudava por `UPDATE` solto espalhado em três módulos, sem registro de quem mudou,
por quê, nem a partir de qual estado. Agora:

* a máquina é **dado** (`project_status_graph`), não código espalhado — e um gatilho no banco recusa transição inválida
  mesmo que alguém escreva SQL direto;
* cada transição entra em `project_transitions` (append-only) e na trilha encadeada por hash (`ledger_entries`);
* snapshots permitem responder "como este projeto estava em 01/01?" e comparar dois momentos.

A linha de tempo REUSA `ledger_entries`, que já era append-only e encadeada por hash desde a migração 0002. Criar uma
segunda tabela de histórico seria duplicar a única fonte de verdade do projeto.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ..db.pq import Connection, Json
from ..services.audit import ledger

# Estados em que o projeto ainda está sendo montado (não é candidato a match nem a documento final).
BUILDING = ("draft", "diagnosing", "structuring")
# Estados em que o projeto é "vivo" para match e captação.
OPEN = ("ready", "published", "funding", "submitted")
# Estados terminais: não saem por iniciativa da organização (só reabertura excepcional).
TERMINAL = ("archived",)

LABELS: dict[str, str] = {
    "draft": "Rascunho", "diagnosing": "Em diagnóstico", "structuring": "Em estruturação", "ready": "Pronto",
    "published": "Publicado", "funding": "Em captação", "funded": "Captado", "submitted": "Submetido",
    "approved": "Aprovado", "in_execution": "Em execução", "monitoring": "Em acompanhamento",
    "completed": "Concluído", "archived": "Arquivado", "blocked": "Bloqueado", "paused": "Pausado",
    "cancelled": "Cancelado", "rejected": "Recusado",
}

TIMELINE_LABELS: dict[str, str] = {
    "project_created": "Projeto criado", "idea_promoted": "Ideia promovida a projeto",
    "status_changed": "Situação alterada", "diagnosis_created": "Diagnóstico criado",
    "diagnosis_revised": "Nova versão do diagnóstico", "action_created": "Ação criada",
    "action_completed": "Ação concluída", "goal_created": "Meta definida",
    "document_generated": "Documento gerado", "document_approved": "Documento aprovado",
    "document_signed": "Documento assinado", "opportunity_matched": "Oportunidade avaliada",
    "match_feedback": "Retorno sobre a recomendação", "partner_added": "Parceiro acrescentado",
    "submission_created": "Submissão montada", "submission_sent": "Submissão enviada",
    "risk_created": "Risco registrado", "risk_resolved": "Risco resolvido",
    "snapshot_taken": "Retrato do projeto", "project_archived": "Projeto arquivado",
    "need_published": "Necessidade publicada", "budget_defined": "Orçamento definido",
    "milestone_defined": "Marco definido", "interest_registered": "Interesse registrado",
    "application_submitted": "Candidatura submetida", "application_approved": "Candidatura aprovada",
    "funding_committed": "Aporte comprometido", "disbursement_reported": "Desembolso informado",
    "disbursement_confirmed": "Desembolso confirmado", "expense_recorded": "Despesa registrada",
    "evidence_submitted": "Evidência enviada", "evidence_reviewed": "Evidência avaliada",
    "result_reported": "Resultado informado", "report_submitted": "Relatório enviado",
    "feedback_given": "Devolutiva registrada", "professional_signature": "Assinatura profissional",
    "project_completed": "Projeto concluído", "refund_completed": "Devolução concluída",
    "payment_disputed": "Pagamento contestado", "indicator_validated": "Indicador validado",
    "procurement_decided": "Compra decidida",
}


def allowed_from(conn: Connection, status: str) -> list[dict]:
    return conn.query("SELECT to_status, requires_reason, note FROM project_status_graph WHERE from_status = $1"
                      " ORDER BY to_status", status)


def can_transition(conn: Connection, from_status: str, to_status: str) -> dict | None:
    return conn.one("SELECT to_status, requires_reason, note FROM project_status_graph"
                    " WHERE from_status = $1 AND to_status = $2", from_status, to_status)


def transition(conn: Connection, *, project_id: str, org_id: str, to_status: str, actor_user_id: str | None,
               actor_org_id: str | None = None, reason: str | None = None, evidence_document_id: str | None = None,
               automatic: bool = False) -> dict:
    """Muda a situação do projeto, registra a transição e entra na trilha. Erro explícito quando a máquina recusa."""
    from ..http import ApiError
    p = conn.one("SELECT id::text AS id, org_id::text AS org_id, status, title FROM projects WHERE id = $1", project_id)
    if not p:
        raise ApiError(404, "not_found", "Projeto não encontrado")
    if p["status"] == to_status:
        return {"changed": False, "status": to_status, "reason": "já está nesta situação"}
    rule = can_transition(conn, p["status"], to_status)
    if rule is None:
        options = ", ".join(r["to_status"] for r in allowed_from(conn, p["status"])) or "nenhuma"
        raise ApiError(409, "invalid_transition",
                       f"Transição '{LABELS.get(p['status'], p['status'])}' → '{LABELS.get(to_status, to_status)}' "
                       f"não é permitida. A partir de '{LABELS.get(p['status'], p['status'])}' é possível ir para: {options}.")
    if rule["requires_reason"] and not (reason or "").strip():
        raise ApiError(422, "reason_required",
                       f"A transição para '{LABELS.get(to_status, to_status)}' exige motivo registrado.")
    conn.run("UPDATE projects SET status = $2 WHERE id = $1", project_id, to_status)
    conn.run("INSERT INTO project_transitions(project_id, org_id, from_status, to_status, actor_user_id, actor_org_id,"
             " reason, evidence_document_id, automatic) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)",
             project_id, org_id, p["status"], to_status, actor_user_id, actor_org_id or org_id, reason,
             evidence_document_id, automatic)
    ledger(conn, project_id=project_id, org_id=org_id, actor=actor_user_id, entry_type="status_changed",
           ref_type="project", ref_id=project_id,
           payload={"from": p["status"], "to": to_status, "automatic": automatic, "reason": reason})
    return {"changed": True, "from": p["status"], "status": to_status, "label": LABELS.get(to_status, to_status)}


def transitions(conn: Connection, project_id: str, limit: int = 100) -> list[dict]:
    rows = conn.query("SELECT id, from_status, to_status, reason, automatic, at, actor_user_id::text AS actor_user_id,"
                      " user_display_name(actor_user_id) AS actor_name, evidence_document_id::text AS evidence_document_id"
                      " FROM project_transitions WHERE project_id = $1 ORDER BY id DESC LIMIT $2", project_id, limit)
    for r in rows:
        r["from_label"] = LABELS.get(r["from_status"], r["from_status"])
        r["to_label"] = LABELS.get(r["to_status"], r["to_status"])
    return rows


def timeline(conn: Connection, project_id: str, *, limit: int = 200, offset: int = 0) -> list[dict]:
    """Linha de tempo do projeto: a trilha encadeada por hash, com rótulo legível."""
    rows = conn.query("SELECT seq, entry_type, amount_cents, ref_type, ref_id::text AS ref_id, payload, at,"
                      " prev_hash, entry_hash, actor_user_id::text AS actor_user_id,"
                      " user_display_name(actor_user_id) AS actor_name, org_id::text AS org_id"
                      " FROM ledger_entries WHERE project_id = $1 ORDER BY seq DESC LIMIT $2 OFFSET $3",
                      project_id, limit, offset)
    for r in rows:
        r["label"] = TIMELINE_LABELS.get(r["entry_type"], r["entry_type"])
    return rows


def timeline_integrity(conn: Connection, project_id: str) -> dict:
    row = conn.one("SELECT entries, valid, first_broken_seq FROM ledger_verify($1)", project_id) or {}
    return {"entries": row.get("entries"), "valid": row.get("valid"), "first_broken_seq": row.get("first_broken_seq")}


# ------------------------------------------------------------------------------------------------ snapshots
SNAPSHOT_VERSION = "snapshot@1.0"


def build_state(conn: Connection, project_id: str) -> dict[str, Any]:
    """Retrato do projeto: o que precisa ser comparável ao longo do tempo."""
    p = conn.one("SELECT id::text AS id, title, status, visibility, budget_total_cents, funded_cents, territory,"
                 " causes, ods, esg_tags, starts_on, ends_on, urgency, beneficiaries_count, updated_at,"
                 " origin_idea_id::text AS origin_idea_id FROM projects WHERE id = $1", project_id)
    if not p:
        return {}
    milestones = conn.query("SELECT id::text AS id, title, due_on, amount_cents, funded_cents, status"
                            " FROM milestones WHERE project_id = $1 ORDER BY due_on NULLS LAST, id", project_id)
    indicators = conn.query(
        "SELECT pi.id::text AS id, ic.code, ic.name, ic.unit, ic.result_kind, pi.baseline, pi.target, pi.target_date,"
        " (SELECT iv.value FROM indicator_values iv WHERE iv.project_indicator_id = pi.id AND iv.status = 'validated'"
        "  ORDER BY iv.measured_on DESC LIMIT 1) AS last_validated,"
        " (SELECT iv.measured_on FROM indicator_values iv WHERE iv.project_indicator_id = pi.id AND iv.status = 'validated'"
        "  ORDER BY iv.measured_on DESC LIMIT 1) AS last_validated_on"
        " FROM project_indicators pi JOIN indicator_catalog ic ON ic.id = pi.indicator_id"
        " WHERE pi.project_id = $1 ORDER BY ic.code", project_id)
    risks = conn.query("SELECT id::text AS id, code, category, title, probability, impact, severity, status, origin"
                       " FROM project_risks WHERE project_id = $1 ORDER BY severity DESC, created_at", project_id)
    docs = conn.query("SELECT id::text AS id, doc_type, title, version, sha256, status, valid_until"
                      " FROM documents WHERE project_id = $1 AND deleted_at IS NULL ORDER BY created_at", project_id)
    # As "partes" do projeto são as organizações com candidatura/compromisso — não existe tabela project_parties.
    parties = conn.query(
        "SELECT DISTINCT a.funder_org_id::text AS org_id, 'funder' AS role, o.legal_name"
        " FROM applications a JOIN organizations o ON o.id = a.funder_org_id"
        " WHERE a.project_id = $1 AND a.funder_org_id IS NOT NULL ORDER BY 1", project_id)
    return {"snapshot_version": SNAPSHOT_VERSION, "project": p, "milestones": milestones, "indicators": indicators,
            "risks": risks, "documents": docs, "parties": parties,
            "counts": {"milestones": len(milestones), "indicators": len(indicators), "risks": len(risks),
                       "documents": len(docs)}}


def _canonical(state: dict) -> str:
    return json.dumps(state, sort_keys=True, ensure_ascii=False, default=str)


def take_snapshot(conn: Connection, *, project_id: str, org_id: str, label: str, reason: str = "manual",
                  taken_by: str | None = None) -> dict:
    state = build_state(conn, project_id)
    if not state:
        from ..http import ApiError
        raise ApiError(404, "not_found", "Projeto não encontrado")
    digest = hashlib.sha256(_canonical(state).encode()).hexdigest()
    seq = conn.scalar("SELECT max(seq) FROM ledger_entries WHERE project_id = $1", project_id)
    row = conn.one("INSERT INTO project_snapshots(project_id, org_id, label, reason, state, state_sha256, ledger_seq,"
                   " taken_by) VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,$8) RETURNING id::text AS id, taken_at",
                   project_id, org_id, label, reason, Json(state), digest, seq, taken_by)
    ledger(conn, project_id=project_id, org_id=org_id, actor=taken_by, entry_type="snapshot_taken",
           ref_type="snapshot", ref_id=row["id"], payload={"label": label, "reason": reason, "sha256": digest})
    return {"id": row["id"], "taken_at": row["taken_at"], "state_sha256": digest, "label": label}


def _flat(state: dict) -> dict[str, Any]:
    """Achata o retrato para comparar campo a campo."""
    out: dict[str, Any] = {}
    for k, v in (state.get("project") or {}).items():
        out[f"project.{k}"] = v
    for group in ("milestones", "indicators", "risks", "documents", "parties"):
        for item in state.get(group) or []:
            ident = item.get("code") or item.get("id")
            for k, v in item.items():
                if k == "id":
                    continue
                out[f"{group}[{ident}].{k}"] = v
    for k, v in (state.get("counts") or {}).items():
        out[f"counts.{k}"] = v
    return out


def compare_snapshots(conn: Connection, a_id: str, b_id: str) -> dict:
    a = conn.one("SELECT id::text AS id, label, taken_at, state, project_id::text AS project_id FROM project_snapshots WHERE id = $1", a_id)
    b = conn.one("SELECT id::text AS id, label, taken_at, state, project_id::text AS project_id FROM project_snapshots WHERE id = $1", b_id)
    if not a or not b:
        return {"found": False}
    if a["project_id"] != b["project_id"]:
        return {"found": False, "reason": "snapshots de projetos diferentes"}
    fa, fb = _flat(a["state"]), _flat(b["state"])
    changed, added, removed = [], [], []
    for k in sorted(set(fa) | set(fb)):
        va, vb = fa.get(k, "__missing__"), fb.get(k, "__missing__")
        if va == vb:
            continue
        if va == "__missing__":
            added.append({"field": k, "to": vb})
        elif vb == "__missing__":
            removed.append({"field": k, "from": va})
        else:
            changed.append({"field": k, "from": va, "to": vb})
    return {"found": True, "from": {"id": a["id"], "label": a["label"], "taken_at": a["taken_at"]},
            "to": {"id": b["id"], "label": b["label"], "taken_at": b["taken_at"]},
            "changed": changed, "added": added, "removed": removed,
            "summary": {"changed": len(changed), "added": len(added), "removed": len(removed)}}


# ------------------------------------------------------------------------------------------------ riscos por regra
RISK_RULES = (
    ("no_budget", "financial", "Projeto sem orçamento informado", "high", "medium",
     "SELECT 1 FROM projects WHERE id = $1 AND (budget_total_cents IS NULL OR budget_total_cents = 0)"),
    ("no_schedule", "timeline", "Projeto sem prazo definido", "medium", "medium",
     "SELECT 1 FROM projects WHERE id = $1 AND (starts_on IS NULL OR ends_on IS NULL)"),
    ("no_milestones", "operational", "Projeto sem marcos definidos", "medium", "medium",
     "SELECT 1 FROM projects WHERE id = $1 AND NOT EXISTS (SELECT 1 FROM milestones m WHERE m.project_id = $1)"),
    ("no_indicators", "operational", "Projeto sem indicador de resultado", "medium", "high",
     "SELECT 1 FROM projects WHERE id = $1 AND NOT EXISTS (SELECT 1 FROM project_indicators pi WHERE pi.project_id = $1)"),
    ("expired_credential", "eligibility", "Credencial profissional vencida na organização", "medium", "high",
     "SELECT 1 FROM professional_credentials c JOIN projects p ON p.org_id = c.org_id WHERE p.id = $1"
     " AND c.verification_status = 'verified' AND c.valid_until IS NOT NULL AND c.valid_until < current_date"),
    ("expiring_document", "documentary", "Documento obrigatório vencendo em 30 dias", "high", "medium",
     "SELECT 1 FROM documents d WHERE d.project_id = $1 AND d.deleted_at IS NULL AND d.valid_until IS NOT NULL"
     " AND d.valid_until BETWEEN current_date AND current_date + 30"),
    ("expired_document", "documentary", "Documento do projeto vencido", "high", "high",
     "SELECT 1 FROM documents d WHERE d.project_id = $1 AND d.deleted_at IS NULL AND d.valid_until IS NOT NULL"
     " AND d.valid_until < current_date"),
    ("compliance_pending", "legal", "Cadastro institucional ainda não aprovado", "medium", "high",
     "SELECT 1 FROM projects p JOIN organizations o ON o.id = p.org_id WHERE p.id = $1"
     " AND o.compliance_status <> 'approved'"),
)
RISK_RULES_VERSION = "risk-rules@1.0"
SEVERITY_MATRIX = {("low", "low"): "low", ("low", "medium"): "low", ("low", "high"): "medium",
                   ("medium", "low"): "low", ("medium", "medium"): "medium", ("medium", "high"): "high",
                   ("high", "low"): "medium", ("high", "medium"): "high", ("high", "high"): "critical"}


def scan_risks(conn: Connection, *, project_id: str, org_id: str, actor_user_id: str | None = None) -> dict:
    """Aplica as regras e registra os riscos encontrados como `system_identified` — indício, não verdade absoluta.

    Risco já resolvido pela organização NÃO volta sozinho; risco que deixou de valer é marcado como resolvido pelo
    sistema, com nota dizendo que a condição deixou de existir.
    """
    found, closed = [], []
    for code, category, title, prob, imp, sql in RISK_RULES:
        hit = bool(conn.scalar(sql, project_id))
        existing = conn.one("SELECT id::text AS id, status, origin FROM project_risks WHERE project_id = $1 AND code = $2",
                            project_id, code)
        severity = SEVERITY_MATRIX[(prob, imp)]
        if hit and existing is None:
            rid = conn.scalar("INSERT INTO project_risks(project_id, org_id, code, category, title, probability, impact,"
                              " severity, origin, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,'system_identified',$9)"
                              " RETURNING id::text", project_id, org_id, code, category, title, prob, imp, severity,
                              actor_user_id)
            ledger(conn, project_id=project_id, org_id=org_id, actor=actor_user_id, entry_type="risk_created",
                   ref_type="risk", ref_id=rid, payload={"code": code, "severity": severity, "origin": "system_identified"})
            found.append({"id": rid, "code": code, "title": title, "severity": severity})
        elif not hit and existing is not None and existing["status"] in ("open", "mitigating") \
                and existing["origin"] == "system_identified":
            conn.run("UPDATE project_risks SET status = 'resolved', resolved_at = now(),"
                     " resolution_note = 'A condição que gerou este risco deixou de existir.' WHERE id = $1",
                     existing["id"])
            ledger(conn, project_id=project_id, org_id=org_id, actor=actor_user_id, entry_type="risk_resolved",
                   ref_type="risk", ref_id=existing["id"], payload={"code": code, "automatic": True})
            closed.append({"id": existing["id"], "code": code})
    return {"rules_version": RISK_RULES_VERSION, "identified": found, "auto_resolved": closed,
            "note": "Riscos marcados como 'system_identified' são indícios de regra, não diagnóstico definitivo."}
