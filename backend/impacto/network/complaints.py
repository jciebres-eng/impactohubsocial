"""Denúncia, suspeita, infração comprovada e consequência jurídica — quatro coisas distintas.

A DISTINÇÃO QUE ESTE MÓDULO EXISTE PARA PROTEGER

    DENÚNCIA              alguém afirma alguma coisa. Peso zero por si só. Não aparece em reputação,
                          não restringe nada, não é mostrada a terceiros.

    SUSPEITA              a plataforma tem indício: uma denúncia triada para análise, ou um detector
                          automático que disparou. Continua não sendo achado. O denunciado é chamado
                          a se manifestar ANTES de qualquer conclusão.

    INFRAÇÃO COMPROVADA   uma pessoa humana analisou, com fundamentação escrita, e concluiu que
                          procede. SÓ ISTO autoriza medida — e a trava é do banco (gatilho
                          `enforcement_needs_substantiated_report`), não da boa vontade da rota.

    CONSEQUÊNCIA JURÍDICA a plataforma NÃO declara crime, NÃO tipifica conduta e NÃO substitui
                          polícia, Ministério Público, Judiciário, órgão regulador, conselho
                          profissional, contador, advogado ou autoridade fiscal. Ela marca
                          `legal_referral` com fundamentação e encaminha para quem tem competência.

POR QUE ESSA SEPARAÇÃO É ESTRUTURAL, E NÃO UMA BOA INTENÇÃO

Um produto que mede reputação e aplica sanção precisa responder a uma pergunta desconfortável: o que
impede que denunciar vire uma arma? A resposta aqui não é uma política escrita — é que a denúncia
**não tem para onde ir** sem passar por análise humana fundamentada. Ela não toca a reputação (as
seis dimensões não leem esta tabela, e há teste de arquitetura que mantém assim), não restringe
capacidade nenhuma, e o banco recusa a medida que tente se apoiar nela antes da conclusão.

O QUE O DENUNCIADO VÊ

Nada, até ser chamado a se manifestar. A partir daí: a categoria, o que lhe é imputado e o prazo —
**nunca quem denunciou**. As projeções deste módulo não selecionam o denunciante, e a política de
RLS que dá leitura ao alvo também não o alcança.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import ApiError, not_found, unprocessable
from . import notify

ENGINE_VERSION = "report-integrity@1.0.0"

#: Situação (ANDAMENTO) -> rótulo. Não confundir com `finding` (CONCLUSÃO).
STATUS_LABEL: dict[str, str] = {
    "reported": "registrada",
    "under_review": "em análise",
    "information_requested": "aguardando manifestação de quem foi denunciado",
    "substantiated": "procedente",
    "unsubstantiated": "não procedente",
    "dismissed": "arquivada sem análise de mérito",
    "appealed": "em recurso",
    "resolved": "encerrada",
}

FINDING_LABEL: dict[str, str] = {
    "substantiated": "a análise concluiu que procede",
    "unsubstantiated": "a análise concluiu que NÃO procede",
}

#: Como resolver a organização afetada a partir do alvo da denúncia. Serve ao direito de resposta:
#: sem isso, o denunciado não tem por onde ser ouvido.
TARGET_ORG_SQL: dict[str, str] = {
    "organization": "SELECT id::text FROM organizations WHERE id = $1",
    "project": "SELECT org_id::text FROM projects WHERE id = $1",
    "call": "SELECT org_id::text FROM calls WHERE id = $1",
    "document": "SELECT org_id::text FROM documents WHERE id = $1",
    "solution": "SELECT org_id::text FROM solutions WHERE id = $1",
    "message": "SELECT sender_org_id::text FROM messages WHERE id = $1",
    "user": "",   # pessoa não é organização: o contraditório corre por outro caminho
}

SEPARATION_NOTE = (
    "Denúncia não é suspeita, suspeita não é infração e infração apurada pela plataforma não é "
    "decisão judicial. A plataforma apura o que é dela (uso do produto, regras que publicou) e "
    "encaminha o resto a quem tem competência."
)


def _resolve_target_org(conn: Connection, target_type: str, target_id: str) -> str | None:
    """Organização afetada, ou ``None`` quando o alvo não tem uma (pessoa física).

    SEM `try/except` AQUI, DE PROPÓSITO. A primeira versão desta função engolia a exceção para
    "ser tolerante" — e, no PostgreSQL, uma exceção dentro da transação a ABORTA: todos os comandos
    seguintes falham com "current transaction is aborted". O efeito prático foi um 500 em `POST
    /v1/reports` quando o alvo era um recado, porque a consulta citava uma coluna inexistente
    (`messages.org_id`; a coluna é `sender_org_id`). Tolerância que esconde erro de SQL não é
    tolerância: é o erro aparecendo em outro lugar, mais tarde, sem relação aparente com a causa.
    Consulta que não casa devolve ``None`` normalmente, sem exceção; consulta ERRADA tem de estourar.
    """
    sql = TARGET_ORG_SQL.get(target_type)
    if not sql:
        return None
    return conn.scalar(sql, target_id)


# ===================================================================== abertura (DENÚNCIA)
def open_report(conn: Connection, *, reporter_user_id: str, reporter_org_id: str | None,
                target_type: str, target_id: str, reason: str, details: str | None,
                category: str | None = None, evidence_document_id: str | None = None) -> dict:
    """Registra a denúncia. Nada acontece com ela além de ficar registrada para triagem humana."""
    org = _resolve_target_org(conn, target_type, target_id)
    if org and reporter_org_id and org == reporter_org_id:
        raise unprocessable("Uma organização não denuncia a si mesma")
    row = conn.one(
        "INSERT INTO reports(reporter_user_id, reporter_org_id, target_type, target_id, reason,"
        " details, category, evidence_document_id, target_org_id)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)"
        " RETURNING id::text AS id, status, created_at",
        reporter_user_id, reporter_org_id, target_type, target_id, reason, details, category,
        evidence_document_id, org)
    return {**row, "status_label": STATUS_LABEL[row["status"]],
            "note": ("Registrada para triagem humana. Uma denúncia, por si só, não restringe nada, "
                     "não aparece em reputação e não é comunicada a terceiros."),
            "separation": SEPARATION_NOTE}


# ===================================================================== triagem (SUSPEITA)
def take_for_review(conn: Connection, *, report_id: str, reviewer: str) -> dict:
    """Leva para análise e registra QUEM analisa. Continua não sendo achado."""
    row = conn.one(
        "UPDATE reports SET status = 'under_review', assigned_reviewer = $2"
        " WHERE id = $1 AND status = 'reported'"
        " RETURNING id::text AS id, status, assigned_reviewer::text AS assigned_reviewer", report_id, reviewer)
    if not row:
        raise ApiError(409, "not_reported", "Só uma denúncia recém-registrada entra em análise")
    return {**row, "status_label": STATUS_LABEL[row["status"]]}


def request_response(conn: Connection, *, report_id: str, reviewer: str, question: str) -> dict:
    """Abre o contraditório: chama quem foi denunciado a se manifestar, sem revelar quem denunciou."""
    if len(question.strip()) < 20:
        raise unprocessable("Diga o que exatamente está sendo pedido (mínimo de 20 caracteres)")
    rep = conn.one("SELECT target_org_id::text AS org_id, status, category, target_type"
                   " FROM reports WHERE id = $1", report_id)
    if not rep:
        raise not_found("Denúncia")
    if rep["status"] not in ("reported", "under_review"):
        raise ApiError(409, "invalid_status", "A manifestação é pedida antes da conclusão")
    if not rep["org_id"]:
        raise unprocessable("Esta denúncia não tem organização identificada para se manifestar")
    row = conn.one(
        "UPDATE reports SET status = 'information_requested', response_requested_at = now(),"
        " assigned_reviewer = coalesce(assigned_reviewer, $2) WHERE id = $1"
        " RETURNING id::text AS id, status", report_id, reviewer)
    notify.org_event(
        conn, event="Report.response_requested", org_id=rep["org_id"],
        title="Pedido de manifestação", body=question[:1900], link="/conta/denuncias",
        priority="high", min_role="admin", ref_type="report", ref_id=report_id,
        action_label="Responder", dedupe_parts=("Report.response_requested", report_id))
    return {**row, "status_label": STATUS_LABEL[row["status"]],
            "note": "Quem foi denunciado foi avisado. O aviso não diz quem denunciou."}


def respond(conn: Connection, *, report_id: str, org_id: str, actor: str | None, body: str,
            document_id: str | None = None) -> dict:
    """Manifestação de quem foi denunciado. Append-only: não se reescreve depois da decisão."""
    rep = conn.one("SELECT target_org_id::text AS org_id, status FROM reports WHERE id = $1", report_id)
    if not rep or rep["org_id"] != org_id:
        raise not_found("Denúncia")
    if rep["status"] not in ("information_requested", "under_review"):
        raise ApiError(409, "not_open_for_response",
                       "Esta denúncia não está aberta para manifestação")
    # Escrita que atravessa a fronteira de visibilidade: a organização alvo não tem política de
    # escrita em `reports`, e é assim que deve ser. A função estreita faz as duas coisas e nada mais.
    rid = conn.scalar("SELECT app_report_respond($1,$2,$3,$4,$5)::text",
                      report_id, org_id, body, document_id, actor)
    return {"id": rid, "note": "Manifestação registrada e anexada à análise."}


# ===================================================================== conclusão (INFRAÇÃO ou não)
def conclude(conn: Connection, *, report_id: str, decided_by: str, finding: str,
             rationale: str, legal_referral: bool = False,
             legal_referral_note: str | None = None) -> dict:
    """Registra a CONCLUSÃO da análise humana, com fundamentação.

    `substantiated` é o único estado que autoriza medida — e quem garante isso é o gatilho do banco,
    não esta função. `unsubstantiated` não é "arquivada": é uma absolvição, e para quem foi denunciado
    a diferença entre as duas é o que vale.
    """
    if finding not in ("substantiated", "unsubstantiated"):
        raise unprocessable("Conclusão deve ser 'substantiated' ou 'unsubstantiated'")
    if len(rationale.strip()) < 20:
        raise unprocessable("A conclusão exige fundamentação (mínimo de 20 caracteres)")
    if legal_referral and len((legal_referral_note or "").strip()) < 20:
        raise unprocessable("Encaminhar a autoridade exige dizer por quê (mínimo de 20 caracteres)")
    rep = conn.one("SELECT status, target_org_id::text AS org_id FROM reports WHERE id = $1", report_id)
    if not rep:
        raise not_found("Denúncia")
    if rep["status"] not in ("under_review", "information_requested", "appealed"):
        raise ApiError(409, "invalid_status",
                       f"Denúncia em '{STATUS_LABEL.get(rep['status'], rep['status'])}' não conclui aqui")
    row = conn.one(
        "UPDATE reports SET status = $2, finding = $2, decided_by = $3, decided_at = now(),"
        " decision_rationale = $4, legal_referral = $5, legal_referral_note = $6,"
        " resolution = coalesce(resolution, $4), resolved_at = now() WHERE id = $1"
        " RETURNING id::text AS id, status, finding, legal_referral, decided_at",
        report_id, finding, decided_by, rationale, legal_referral, legal_referral_note)
    if rep["org_id"]:
        notify.org_event(
            conn, event="Report.concluded", org_id=rep["org_id"],
            title=("Análise concluída: procede" if finding == "substantiated"
                   else "Análise concluída: não procede"),
            body=rationale[:1900], link="/conta/denuncias", priority="high", min_role="admin",
            ref_type="report", ref_id=report_id,
            dedupe_parts=("Report.concluded", report_id, finding))
    return {**row, "status_label": STATUS_LABEL[row["status"]],
            "finding_label": FINDING_LABEL[finding],
            "authorizes_measure": finding == "substantiated",
            "legal_note": ("Encaminhado para análise de autoridade competente. A plataforma NÃO "
                           "declara crime nem tipifica conduta." if legal_referral else None),
            "separation": SEPARATION_NOTE}


def appeal(conn: Connection, *, report_id: str, org_id: str, note: str) -> dict:
    """Recurso de quem foi afetado pela conclusão. A conclusão só muda por aqui."""
    if len(note.strip()) < 20:
        raise unprocessable("O recurso precisa dizer o que contesta (mínimo de 20 caracteres)")
    rep = conn.one("SELECT target_org_id::text AS org_id, status, finding FROM reports WHERE id = $1",
                   report_id)
    if not rep or rep["org_id"] != org_id:
        raise not_found("Denúncia")
    if rep["status"] not in ("substantiated", "unsubstantiated"):
        raise ApiError(409, "nothing_to_appeal", "Só se recorre de uma conclusão")
    conn.scalar("SELECT app_report_appeal($1,$2,$3)::text", report_id, org_id, note)
    row = conn.one("SELECT id::text AS id, status, finding FROM reports WHERE id = $1", report_id)
    return {**row, "status_label": STATUS_LABEL[row["status"]],
            "note": "O recurso será analisado por pessoa diferente de quem concluiu."}


def dismiss(conn: Connection, *, report_id: str, decided_by: str, rationale: str) -> dict:
    """Arquiva SEM análise de mérito (fora de escopo, duplicada, sem conteúdo).

    Deliberadamente não grava `finding`: arquivar não é absolver, e dizer o contrário seria enganar
    quem foi denunciado tanto quanto quem denunciou.
    """
    if len(rationale.strip()) < 20:
        raise unprocessable("Arquivar exige dizer por quê (mínimo de 20 caracteres)")
    row = conn.one(
        "UPDATE reports SET status = 'dismissed', decided_by = $2, decided_at = now(),"
        " resolution = $3, resolved_at = now()"
        " WHERE id = $1 AND status IN ('reported','under_review','information_requested')"
        " RETURNING id::text AS id, status", report_id, decided_by, rationale)
    if not row:
        raise ApiError(409, "invalid_status", "Esta denúncia não está em situação de ser arquivada")
    return {**row, "status_label": STATUS_LABEL[row["status"]],
            "note": "Arquivada sem análise de mérito. Isto NÃO é uma conclusão de improcedência."}


# ===================================================================== leitura
def for_target(conn: Connection, *, org_id: str) -> dict:
    """O que a organização denunciada vê. NUNCA inclui quem denunciou."""
    rows = conn.query(
        "SELECT r.id::text AS id, r.target_type, r.category, r.reason, r.status, r.finding,"
        " r.decision_rationale, r.response_requested_at, r.decided_at, r.legal_referral,"
        " r.created_at,"
        " (SELECT count(*) FROM report_responses rr WHERE rr.report_id = r.id) AS responses"
        " FROM reports r WHERE r.target_org_id = $1"
        "   AND r.status IN ('information_requested','substantiated','unsubstantiated','appealed','resolved')"
        " ORDER BY r.created_at DESC", org_id)
    return {
        "items": [{**r, "status_label": STATUS_LABEL.get(r["status"], r["status"]),
                   "finding_label": FINDING_LABEL.get(r["finding"]) if r["finding"] else None,
                   "can_respond": r["status"] == "information_requested",
                   "can_appeal": r["status"] in ("substantiated", "unsubstantiated")} for r in rows],
        "note": ("Você vê o que lhe é imputado e pode se manifestar. Quem denunciou não é revelado — "
                 "nem aqui, nem na decisão."),
        "separation": SEPARATION_NOTE,
    }


def admin_view(conn: Connection, *, status: str | None = None, limit: int = 50,
               offset: int = 0) -> dict:
    rows = conn.query(
        "SELECT r.id::text AS id, r.target_type, r.target_id::text AS target_id, r.category,"
        " r.reason, r.details, r.status, r.finding, r.priority, r.decision_rationale,"
        " r.legal_referral, r.legal_referral_note, r.created_at, r.decided_at,"
        " r.assigned_reviewer::text AS assigned_reviewer, r.target_org_id::text AS target_org_id,"
        " (SELECT count(*) FROM report_responses rr WHERE rr.report_id = r.id) AS responses,"
        " (SELECT count(*) FROM enforcement_actions e WHERE e.report_id = r.id) AS measures"
        " FROM reports r WHERE ($1::text IS NULL OR r.status = $1)"
        " ORDER BY r.created_at DESC LIMIT $2 OFFSET $3", status, limit, offset)
    return {
        "items": [{**r, "status_label": STATUS_LABEL.get(r["status"], r["status"]),
                   "finding_label": FINDING_LABEL.get(r["finding"]) if r["finding"] else None,
                   "authorizes_measure": r["finding"] == "substantiated"} for r in rows],
        "statuses": [{"key": k, "label": v} for k, v in STATUS_LABEL.items()],
        "note": ("`dismissed` (arquivada sem mérito) e `unsubstantiated` (analisada e não procede) "
                 "são coisas diferentes: só a segunda é uma absolvição."),
        "separation": SEPARATION_NOTE,
    }


def responses(conn: Connection, *, report_id: str) -> list[dict]:
    return conn.query(
        "SELECT id::text AS id, body, created_at, document_id::text AS document_id"
        " FROM report_responses WHERE report_id = $1 ORDER BY created_at", report_id)


def vocabulary() -> dict[str, Any]:
    """O vocabulário dos quatro níveis, para a interface e para quem desenha."""
    from . import enforcement as ENF
    return {
        "levels": [
            {"key": "report", "label": "Denúncia",
             "means": "alguém afirma. Peso zero por si só.",
             "effects": "nenhum: não restringe, não entra em reputação, não é visível a terceiros"},
            {"key": "suspicion", "label": "Suspeita",
             "means": "há indício em análise humana, ou detector automático disparou",
             "effects": "nenhum efeito automático; o denunciado é chamado a se manifestar"},
            {"key": "substantiated", "label": "Infração comprovada",
             "means": "pessoa humana analisou, com fundamentação, e concluiu que procede",
             "effects": "é o ÚNICO estado que autoriza medida (gatilho no banco)"},
            {"key": "legal_referral", "label": "Consequência jurídica",
             "means": "o caso pode exigir autoridade externa",
             "effects": ("a plataforma encaminha com fundamentação. NÃO declara crime, NÃO tipifica "
                         "conduta e NÃO substitui polícia, Ministério Público, Judiciário, órgão "
                         "regulador, conselho, contador, advogado ou autoridade fiscal")},
        ],
        "statuses": [{"key": k, "label": v} for k, v in STATUS_LABEL.items()],
        "findings": [{"key": k, "label": v} for k, v in FINDING_LABEL.items()],
        "categories": [{"key": k, "label": v} for k, v in ENF.CATEGORIES],
        "never": ("Denúncia não vira sanção sem análise humana fundamentada; denúncia não toca "
                  "reputação em hipótese alguma; e arquivar não é absolver."),
        "engine_version": ENGINE_VERSION,
    }
