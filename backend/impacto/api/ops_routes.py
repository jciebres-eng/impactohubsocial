"""Administração v0.8.0: risco/antifraude (sinais para revisão humana), erros agregados e moderação de mensagens."""
from __future__ import annotations

from ..http import ApiError, Ctx, not_found, page, route
from ..services import risk
from . import schemas as S

T = ("admin",)


class SignalQ(S.Pagination):
    status: str | None = None
    severity: str | None = None


@route("GET", "/v1/admin/risk/signals", auth="admin", permission="compliance.read", query=SignalQ, tags=T, summary="Sinais de risco (para revisão humana; não são acusações)")
def list_signals(ctx: Ctx, q: SignalQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT s.id::text AS id, s.org_id::text AS org_id, o.legal_name AS org_name, s.project_id::text AS project_id, s.signal_type, s.severity, s.summary,"
                       " s.details, s.status, s.detected_at, s.review_note FROM risk_signals s JOIN organizations o ON o.id = s.org_id"
                       " WHERE ($1::text IS NULL OR s.status = $1) AND ($2::text IS NULL OR s.severity = $2)"
                       " ORDER BY (s.status = 'open') DESC, CASE s.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, s.detected_at DESC LIMIT $3 OFFSET $4",
                       q.status, q.severity, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/admin/risk/scan", auth="admin", permission="compliance.write", body=S.RiskScanIn, tags=T, summary="Executa os detectores agora (todas as organizações ou uma)")
def run_scan(ctx: Ctx, body: S.RiskScanIn):
    with ctx.system_tx() as c:
        out = risk.scan(c, body.org_id)
        ctx.audit(c, "risk.scan", "risk", None, {"total_new": out["total_new"]}, org_id=body.org_id)
    return out


@route("POST", "/v1/admin/risk/signals/{signal_id}/review", auth="admin", permission="compliance.write", body=S.RiskReviewIn, tags=T,
       summary="Revisão humana do sinal (relevante ou descartado), com justificativa obrigatória")
def review_signal(ctx: Ctx, body: S.RiskReviewIn):
    with ctx.tx() as c:
        s = c.one("SELECT id::text AS id, org_id::text AS org_id, status FROM risk_signals WHERE id = $1", ctx.path["signal_id"])
        if not s:
            raise not_found("Sinal")
        c.run("UPDATE risk_signals SET status = $2, reviewed_by = $3, reviewed_at = now(), review_note = $4 WHERE id = $1", s["id"], body.status, ctx.user_id, body.note)
        risk.recompute(c, s["org_id"])
        ctx.audit(c, "risk.signal_reviewed", "risk_signal", s["id"], {"status": body.status}, org_id=s["org_id"])
    return {"id": s["id"], "status": body.status}


@route("GET", "/v1/admin/risk/assessments", auth="admin", permission="compliance.read", tags=T)
def list_assessments(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT a.org_id::text AS org_id, o.legal_name AS org_name, a.level, a.rationale, a.open_signals, a.updated_at,"
                       " CASE WHEN a.block_proposed_at > now() - interval '72 hours' THEN a.block_proposed_at END AS block_proposed_at,"
                       " user_display_name(a.block_proposed_by) AS block_proposed_by_name FROM risk_assessments a"
                       " JOIN organizations o ON o.id = a.org_id ORDER BY CASE a.level WHEN 'blocked' THEN 0 WHEN 'manual_review' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END, o.legal_name")
    return {"items": rows}


@route("POST", "/v1/admin/risk/orgs/{org_id}/block", auth="admin", permission="compliance.write", body=S.RiskBlockIn, tags=T,
       summary="Restrição operacional (publicar, candidatar, aportar) por DECISÃO HUMANA de duas pessoas: uma propõe, outra confirma; reversível")
def block_org(ctx: Ctx, body: S.RiskBlockIn):
    """v0.35.0 (auditoria, FRAUD-04): uma pessoa só restringia uma organização inteira. Agora a primeira chamada PROPÕE
    (fica registrada, a organização vai para revisão manual) e uma SEGUNDA pessoa confirma em até 72 horas."""
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM organizations WHERE id = $1", ctx.path["org_id"]):
            raise not_found("Organização")
        cur = c.one("SELECT level, block_proposed_by::text AS proposer, block_proposed_at > now() - interval '72 hours' AS fresh,"
                    " block_proposal_note FROM risk_assessments WHERE org_id = $1 FOR UPDATE", ctx.path["org_id"])
        if cur and cur["level"] == "blocked":
            raise ApiError(409, "already_blocked", "Organização já está com restrição operacional")
        if not cur or not cur["proposer"] or not cur["fresh"]:
            c.run("INSERT INTO risk_assessments(org_id, level, rationale, block_proposed_by, block_proposed_at, block_proposal_note)"
                  " VALUES ($1,'manual_review',$2,$3,now(),$2) ON CONFLICT (org_id) DO UPDATE SET block_proposed_by = EXCLUDED.block_proposed_by,"
                  " block_proposed_at = now(), block_proposal_note = EXCLUDED.block_proposal_note, updated_at = now()",
                  ctx.path["org_id"], body.note, ctx.user_id)
            ctx.audit(c, "risk.org_block_proposed", "organization", ctx.path["org_id"], {"note": body.note[:200]}, org_id=ctx.path["org_id"])
            return {"org_id": ctx.path["org_id"], "level": cur["level"] if cur else "manual_review", "status": "awaiting_second_approval",
                    "note": "Proposta registrada. Outra pessoa da equipe precisa confirmar a restrição em até 72 horas."}
        if cur["proposer"] == ctx.user_id:
            raise ApiError(403, "four_eyes", "Quem propôs a restrição não a confirma: outra pessoa da equipe precisa confirmar")
        c.run("UPDATE risk_assessments SET level = 'blocked', rationale = $2, decided_by = $3, updated_at = now() WHERE org_id = $1",
              ctx.path["org_id"], ((cur["block_proposal_note"] or "") + "\nConfirmação: " + body.note)[:2000], ctx.user_id)
        c.scalar("SELECT app_notify($1, NULL, 'compliance', 'Restrição operacional', $2, '/conformidade')", ctx.path["org_id"],
                 "Sua organização está com restrição operacional temporária enquanto a administração conclui uma revisão. Entre em contato com o suporte.")
        ctx.audit(c, "risk.org_blocked", "organization", ctx.path["org_id"], {"note": body.note[:200]}, org_id=ctx.path["org_id"])
    return {"org_id": ctx.path["org_id"], "level": "blocked"}


@route("POST", "/v1/admin/risk/orgs/{org_id}/unblock", auth="admin", permission="compliance.write", body=S.RiskBlockIn, tags=T)
def unblock_org(ctx: Ctx, body: S.RiskBlockIn):
    with ctx.tx() as c:
        if not c.run("DELETE FROM risk_assessments WHERE org_id = $1 AND (level = 'blocked' OR block_proposed_by IS NOT NULL)",
                     ctx.path["org_id"]):
            raise ApiError(409, "not_blocked", "Organização não está bloqueada nem tem restrição proposta")
        risk.recompute(c, ctx.path["org_id"])
        ctx.audit(c, "risk.org_unblocked", "organization", ctx.path["org_id"], {"note": body.note[:200]}, org_id=ctx.path["org_id"])
    return {"org_id": ctx.path["org_id"], "level": "released"}


# ------------------------------------------------------------------------------------------------ erros agregados
@route("GET", "/v1/admin/errors", permission="maintenance.read", auth="admin", query=S.Pagination, tags=T, summary="Erros 5xx agregados por impressão digital (sem dados pessoais)")
def list_errors(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, route, status, exception_type, message, occurrences, first_seen, last_seen, last_request_id, last_trace_id, resolved"
                       " FROM error_events ORDER BY resolved, last_seen DESC LIMIT $1 OFFSET $2", q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/admin/errors/{error_id}/resolve", auth="admin", permission="maintenance.execute", tags=T)
def resolve_error(ctx: Ctx):
    with ctx.tx() as c:
        if not c.run("UPDATE error_events SET resolved = true WHERE id = $1", ctx.path["error_id"]):
            raise not_found("Erro")
        ctx.audit(c, "error_event.resolved", "error_event", ctx.path["error_id"], org_id=None)
    return {"resolved": True}


# ------------------------------------------------------------------------------------------------ moderação de mensagens
@route("GET", "/v1/admin/messages/{message_id}", auth="admin", tags=T, summary="Lê uma mensagem denunciada (acesso auditado)")
def read_message(ctx: Ctx):
    with ctx.tx() as c:
        m = c.one("SELECT m.id::text AS id, m.body, m.created_at, m.removed_at, org_display(m.sender_org_id) AS sender, m.sender_org_id::text AS sender_org_id FROM messages m WHERE m.id = $1", ctx.path["message_id"])
        if not m:
            raise not_found("Mensagem")
        if not c.one("SELECT 1 FROM reports WHERE target_type = 'message' AND target_id = $1", m["id"]):
            raise ApiError(403, "not_reported", "Mensagens só são lidas pela administração quando denunciadas")
        ctx.audit(c, "moderation.message_read", "message", m["id"], org_id=m["sender_org_id"])
    return m


@route("POST", "/v1/admin/messages/{message_id}/remove", auth="admin", body=S.MessageRemoveIn, tags=T, summary="Oculta o conteúdo de uma mensagem denunciada (registro permanece)")
def remove_message(ctx: Ctx, body: S.MessageRemoveIn):
    with ctx.tx() as c:
        if not c.run("UPDATE messages SET removed_at = now(), removed_reason = $2 WHERE id = $1 AND removed_at IS NULL", ctx.path["message_id"], body.reason):
            raise not_found("Mensagem")
        ctx.audit(c, "moderation.message_removed", "message", ctx.path["message_id"], {"reason": body.reason})
    return {"removed": True}


# ============================================================ operação: backup e e-mail (v0.19.0)
@route("GET", "/v1/admin/ops/health", permission="health.read", auth="admin", tags=T,
       summary="Última execução de cada tarefa de operação e falhas de e-mail na janela")
def ops_health(ctx: Ctx):
    """A pergunta que não tinha resposta: "o backup rodou?".

    Devolve, por tarefa, a última execução com resultado — incluindo `not_configured`, que é o estado
    mais importante de todos: ele diz que a tarefa NÃO rodou por falta de credencial ou destino, em
    vez de deixar a ausência de registro parecer sucesso.
    """
    from ..ops import backup as BK
    from ..ops import email_canary as EC
    from ..ops import runs as RUNS
    with ctx.system_tx() as c:
        tarefas = []
        for job, modulo in (("backup", BK), ("email_canary", EC)):
            ultimo = RUNS.last(c, job)
            ok, motivo = modulo.configured(ctx.app.settings)
            tarefas.append({
                "job": job, "configured": ok, "not_configured_reason": motivo or None,
                "last_run": ultimo,
                "verdict": ("nunca executou" if not ultimo else
                            "última execução falhou" if ultimo["status"] == "failed" else
                            "não configurado" if ultimo["status"] == "not_configured" else
                            "última execução concluída"),
            })
        email = EC.recent_failures(c, minutes=60)
        offsite = bool(ctx.app.settings.backup_offsite_cmd)
    return {
        "jobs": tarefas,
        "email": email,
        "backup_offsite_configured": offsite,
        "note": ("Backup local conferido NÃO é recuperação de desastre: sem cópia externa, um "
                 "incidente no mesmo host leva o banco e os dumps juntos."
                 if not offsite else "Backup com cópia externa configurada."),
        "delivery_note": ("E-mail com status accepted_by_smtp foi ACEITO pelo servidor. A plataforma "
                          "não recebe retorno de entrega do provedor, então entrega não é afirmada."),
    }


# ─────────────────────────────────────────────────────────────────────────────────────────────────
# MOTOR DE INTEGRIDADE RELACIONAL
#
# Até a v0.22.0, a verificação de órfão do relatório de integridade era uma string literal que dizia
# "nenhuma verificação aplicável: toda referência é FK declarada". A afirmação é falsa: 25 colunas
# de referência polimórfica não podem ter FK, e eram as únicas sem verificação nenhuma.

@route("GET", "/v1/admin/integrity", auth="admin", permission="security.audit.read", tags=T,
       summary="Órfãos, referências não resolvidas, deriva de catálogo, cadeias de hash e cobertura de proveniência")
def integrity_report(ctx: Ctx):
    from ..core.access import log_privileged
    from ..engines import integrity
    log_privileged(ctx, "security.audit.read")
    with ctx.system_tx() as c:
        return integrity.report(c)
