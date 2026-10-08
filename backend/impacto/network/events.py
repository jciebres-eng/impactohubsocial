"""Evento de domínio: o registro único do fato.

ACHADO QUE ORIGINOU ESTE MÓDULO (RECONSTRUCTION_AUDIT.md §2.3): existiam três maneiras de notificar
(`notify_user`, `notify_once`, `notify_counterpart`), cada chamador decidia por conta própria, e só cobrança tinha
idempotência. O fato e o aviso estavam embaralhados.

Aqui o fato é gravado UMA vez, **na mesma transação** em que aconteceu, e o aviso é consequência dele. O evento não
substitui a transação: ele faz parte dela. Se o fato não comitar, o evento não existe — que é exatamente o que se
quer de um registro de fato.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json

# Eventos de domínio da rede. Nome no formato Entidade.fato, para que a leitura do log seja óbvia.
EVENTS: dict[str, str] = {
    "Program.created": "Programa criado",
    "Program.opened": "Programa aberto",
    "Program.in_execution": "Programa em execução",
    "Program.suspended": "Programa suspenso",
    "Program.closed": "Programa encerrado",
    "Program.project_linked": "Projeto vinculado ao programa",
    "Program.project_role_changed": "Papel do projeto no programa alterado",
    "Relationship.created": "Relação criada",
    "Relationship.ended": "Relação encerrada",
    "Proposal.created": "Proposta criada",
    "Proposal.sent": "Proposta enviada",
    "Proposal.viewed": "Proposta vista",
    "Proposal.in_review": "Proposta em análise",
    "Proposal.accepted": "Proposta aceita",
    "Proposal.declined": "Proposta recusada",
    "Proposal.changes_requested": "Proposta devolvida para ajuste",
    "Proposal.withdrawn": "Proposta retirada",
    "Proposal.expired": "Proposta expirada",
    "Listing.published": "Anúncio publicado",
    "Listing.paused": "Anúncio pausado",
    "Listing.suspended": "Anúncio suspenso pela administração",
    "Conversation.started": "Conversa iniciada",
    "Message.sent": "Recado enviado",
    "Investment.intent": "Intenção de apoio registrada",
    "Investment.committed": "Apoio comprometido",
    "ImpactUpdate.submitted": "Relatório de impacto enviado",
    "ImpactUpdate.changes_requested": "Relatório devolvido para ajuste",
    "ImpactUpdate.accepted": "Relatório aceito",
    "ImpactUpdate.published": "Relatório publicado",
    "Experience.confirmed": "Experiência profissional confirmada",
    "Experience.disputed": "Experiência profissional contestada",
    "Team.member_added": "Pessoa acrescentada à equipe do projeto",
    "Team.member_removed": "Pessoa retirada da equipe do projeto",
    "Enforcement.applied": "Medida de moderação aplicada",
    # v0.20.0 — apuração de denúncia. O fato da DENÚNCIA em si não entra aqui de propósito: quem
    # denunciou e quem foi denunciado não viram evento de domínio legível pela rede.
    "Report.response_requested": "Manifestação pedida a quem foi denunciado",
    "Report.concluded": "Apuração de denúncia concluída",
    # os fatos do NÚCLEO que a rede também precisa observar para notificar a equipe
    "Project.status_changed": "Situação do projeto alterada",
    "Project.published": "Projeto publicado",
    "Document.generated": "Documento gerado",
    "Document.approved": "Documento aprovado",
    "Document.signed": "Documento assinado",
    "Document.attached": "Documento anexado",
    "Diagnosis.revised": "Nova versão do diagnóstico",
    "Milestone.completed": "Marco concluído",
    "Indicator.measured": "Indicador medido",
    "Indicator.validated": "Indicador validado",
    "Risk.created": "Risco registrado",
    "Risk.resolved": "Risco resolvido",
    # v0.20.0 — prazos. A plataforma registrava cinco prazos e varria um: o resto vencia em
    # silêncio. Ver `impacto.ops.deadlines`.
    "Milestone.due_soon": "Marco do projeto a vencer",
    "Seal.expiring": "Selo a vencer",
    "Proposal.expiring": "Proposta a vencer",
    "Agreement.milestone_due": "Marco de instrumento a vencer",
    "Call.closing": "Chamada a fechar",
    "Listing.expired": "Anúncio expirado",
    # v0.20.0 — fatos da camada de impacto, que não avisava ninguém sobre nada.
    "Seal.awarded": "Selo concedido",
    "Seal.revoked": "Selo revogado",
    "Reputation.band_changed": "Faixa de reputação alterada",
    "Claim.review_requested": "Revisão de afirmação solicitada",
    # v0.20.0 — assinatura.
    "Agreement.signature_required": "Assinatura pendente em instrumento",
    # v0.27.0 — camada econômica: participação de autoria e repasses.
    "Participation.proposed": "Participação de autoria proposta",
    "Participation.accepted": "Participação de autoria aceita",
    "Payout.registered": "Transferência registrada por quem paga",
    "Payout.confirmed": "Repasse confirmado por quem recebe",
    "Operation.settled": "Operação concluída e quitada",
    # NÃO existe `Security.*` aqui, e a ausência é deliberada. O reuso de credencial de sessão é
    # detectado durante a RENOVAÇÃO do token, quando ainda não há sessão autenticada —
    # `app_record_event()` amarra a autoria a `app_uid()` e recusaria o registro. O fato fica onde
    # ele pertence: na auditoria (`auth.refresh_reuse_detected`) e em um aviso `critical` à dona da
    # conta. Declarar aqui um evento que o caminho não consegue emitir seria repetir exatamente o
    # defeito que esta rodada corrigiu em outros dezoito.
}


def record(conn: Connection, *, event: str, org_id: str | None, actor_user_id: str | None = None,
           project_id: str | None = None, subject_type: str | None = None, subject_id: str | None = None,
           payload: dict[str, Any] | None = None, notified: int = 0) -> int:
    """Grava o fato e devolve o `id`.

    A escrita passa por `app_record_event()` (SECURITY DEFINER) e não por INSERT direto. A razão é estrutural: um
    fato da rede envolve DUAS organizações — "proposta enviada" interessa ao histórico de quem recebeu — e uma
    política de inquilino recusaria exatamente esse registro. A função aceita o fato da contraparte e, em troca,
    amarra a autoria a `app_uid()`: ninguém registra fato em nome de outra pessoa. `INSERT` em `domain_events` está
    revogado para o papel da aplicação, portanto este é o único caminho.
    """
    if event not in EVENTS:
        raise ValueError(f"evento de domínio desconhecido: {event}")
    return int(conn.scalar(
        "SELECT app_record_event($1,$2,$3,$4,$5,$6,$7::jsonb,$8)",
        event, org_id, actor_user_id, project_id, subject_type, subject_id, Json(payload or {}), notified))


def feed(conn: Connection, *, org_id: str | None = None, project_id: str | None = None, limit: int = 50,
         offset: int = 0) -> list[dict]:
    """Fatos recentes, com rótulo legível. É o que alimenta "atividade recente" em qualquer workspace."""
    rows = conn.query(
        "SELECT id, event, org_id::text AS org_id, actor_user_id::text AS actor_user_id,"
        " user_display_name(actor_user_id) AS actor_name, project_id::text AS project_id, subject_type,"
        " subject_id::text AS subject_id, payload, notified, at FROM domain_events"
        " WHERE ($1::uuid IS NULL OR org_id = $1) AND ($2::uuid IS NULL OR project_id = $2)"
        " ORDER BY id DESC LIMIT $3 OFFSET $4", org_id, project_id, limit, offset)
    for r in rows:
        r["label"] = EVENTS.get(r["event"], r["event"])
    return rows
