"""Conversa com contexto: nunca um chat solto quando a relação é profissional.

PEDIDO (§39): "nunca criar chat sem contexto quando a relação é profissional". A razão não é organização visual — é
que uma conversa sem contexto não pode ser auditada, não entra na linha de tempo do projeto e, seis meses depois,
ninguém sabe por que aquelas duas organizações estavam conversando.

O que foi PRESERVADO de propósito (RECONSTRUCTION_AUDIT.md §2.2): `conversations(org_a, org_b)` continua com esse par
de colunas. Eu havia planejado trocar por uma tabela de participantes, e não troquei por dois motivos concretos:
  1. a RLS de `messages` se apoia na RLS de `conversations` — um recado só é legível se a conversa for legível. Esse
     encadeamento está certo, e refazê-lo introduziria risco de vazamento sem ganho;
  2. pessoa física já participa da plataforma através de uma organização `individual`/`provider`. O par de
     organizações não é limitação do modelo, é o modelo.

O que mudou: a conversa ganhou assunto, CONTEXTO (projeto, proposta, necessidade ou edital), situação e carimbo do
último recado; o recado ganhou tipo (texto, fato do sistema, referência a proposta ou documento) e anexo pelo cofre.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import ApiError, forbidden, not_found, unprocessable
from . import notify, relationships

KINDS = ("text", "system", "event", "proposal_ref", "document_ref")
REFS = ("proposal", "document", "project", "relationship", "impact_update", "milestone")
CONTEXTS = ("context_project_id", "context_proposal_id", "context_need_id", "context_call_id")

#: Tipos de relação em que a conversa EXIGE contexto. Seguir alguém e trocar recado social não exige; negociar, sim.
PROFESSIONAL = ("proposal", "investment", "sponsorship", "service", "partnership", "mentorship", "collaboration",
                "support", "government_support")


def open_thread(conn: Connection, *, org_id: str, other_org_id: str, actor: str | None, subject: str | None = None,
                project_id: str | None = None, proposal_id: str | None = None, need_id: str | None = None,
                call_id: str | None = None, professional: bool = True) -> dict:
    """Abre (ou reaproveita) a conversa entre duas organizações NAQUELE contexto.

    Reaproveitar é importante: sem isso, cada clique em "conversar" criaria uma caixa nova e a negociação ficaria
    espalhada em cinco linhas do tempo.
    """
    if org_id == other_org_id:
        raise unprocessable("Não é possível abrir conversa com a própria organização")
    if relationships.blocked_between(conn, org_id, other_org_id):
        raise forbidden("Há bloqueio entre as organizações", "blocked")
    ctx = {"context_project_id": project_id, "context_proposal_id": proposal_id, "context_need_id": need_id,
           "context_call_id": call_id}
    if professional and not any(ctx.values()):
        raise unprocessable(
            "Conversa profissional exige contexto: informe o projeto, a proposta, a necessidade ou o edital",
            {"contextos": ["project_id", "proposal_id", "need_id", "call_id"]})

    a, b = sorted([org_id, other_org_id])   # par ordenado: (A,B) e (B,A) são a MESMA conversa
    found = conn.one(
        "SELECT id::text AS id, subject, status FROM conversations"
        " WHERE org_a = $1 AND org_b = $2"
        "   AND coalesce(context_project_id, '00000000-0000-0000-0000-000000000000'::uuid)"
        "     = coalesce($3::uuid, '00000000-0000-0000-0000-000000000000'::uuid)"
        "   AND coalesce(context_proposal_id, '00000000-0000-0000-0000-000000000000'::uuid)"
        "     = coalesce($4::uuid, '00000000-0000-0000-0000-000000000000'::uuid)"
        "   AND coalesce(context_need_id, '00000000-0000-0000-0000-000000000000'::uuid)"
        "     = coalesce($5::uuid, '00000000-0000-0000-0000-000000000000'::uuid)"
        "   AND coalesce(context_call_id, '00000000-0000-0000-0000-000000000000'::uuid)"
        "     = coalesce($6::uuid, '00000000-0000-0000-0000-000000000000'::uuid)",
        a, b, project_id, proposal_id, need_id, call_id)
    if found:
        if found["status"] != "open":
            conn.run("UPDATE conversations SET status = 'open' WHERE id = $1", found["id"])
        return {**found, "created": False}

    row = conn.one(
        "INSERT INTO conversations(org_a, org_b, subject, context_project_id, context_proposal_id,"
        " context_need_id, context_call_id, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)"
        " RETURNING id::text AS id, created_at",
        a, b, subject, project_id, proposal_id, need_id, call_id, actor)
    notify.org_event(
        conn, event="Conversation.started", org_id=other_org_id, actor_user_id=actor,
        title="Nova conversa", body=subject or "Uma organização iniciou uma conversa com você.",
        link=f"/conversas/{row['id']}", ref_type="conversation", ref_id=row["id"], min_role="member",
        project_id=project_id, payload={"context": {k: v for k, v in ctx.items() if v}})
    return {**row, "subject": subject, "status": "open", "created": True}


def send(conn: Connection, *, conversation_id: str, org_id: str, actor: str | None, body: str,
         kind: str = "text", ref_type: str | None = None, ref_id: str | None = None,
         document_ids: list[str] | None = None) -> dict:
    """Envia o recado e avisa a outra parte. Fato de alto volume: entra em `domain_events`, não na caixa de avisos."""
    c = _party(conn, conversation_id, org_id)
    if c["status"] != "open":
        raise ApiError(409, "closed", "Conversa encerrada; abra uma nova com o contexto atual")
    from . import enforcement as _ENF
    _ENF.ensure_allowed(conn, capability="send_message", org_id=org_id)
    if kind not in KINDS:
        raise unprocessable(f"Tipo de recado desconhecido: {kind}")
    if ref_type and ref_type not in REFS:
        raise unprocessable(f"Referência desconhecida: {ref_type}")
    if kind in ("proposal_ref", "document_ref") and not ref_id:
        raise unprocessable("Recado de referência precisa apontar para algo")
    if not (body or "").strip():
        raise unprocessable("O recado não pode ser vazio")

    m = conn.one(
        "INSERT INTO messages(conversation_id, sender_org_id, sender_user_id, body, kind, ref_type, ref_id)"
        " VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id::text AS id, created_at",
        conversation_id, org_id, actor, body.strip(), kind, ref_type, ref_id)
    for doc in (document_ids or [])[:10]:
        d = conn.one("SELECT org_id::text AS org_id FROM documents WHERE id = $1", doc)
        if not d:
            raise not_found("Documento")
        if d["org_id"] != org_id:
            raise forbidden("O documento anexado precisa pertencer à sua organização")
        conn.run("INSERT INTO message_attachments(message_id, document_id) VALUES ($1,$2)"
                 " ON CONFLICT DO NOTHING", m["id"], doc)
    conn.run("UPDATE conversations SET last_message_at = now() WHERE id = $1", conversation_id)

    other = c["org_b"] if org_id == c["org_a"] else c["org_a"]
    # Um aviso por conversa a cada rodada de recados não lidos: `dedupe_key` inclui o id do recado mais antigo não
    # lido, então dez recados seguidos geram UM aviso — e um novo só depois que a pessoa lê.
    # não existe min(uuid): o recado mais antigo não lido vem por ordenação, não por agregação
    oldest = conn.scalar(
        "SELECT id::text FROM messages WHERE conversation_id = $1 AND sender_org_id = $2"
        " AND read_at IS NULL ORDER BY created_at LIMIT 1", conversation_id, org_id)
    notify.org_event(
        conn, event="Message.sent", org_id=other, actor_user_id=actor, title="Novo recado",
        body=(c["subject"] or body.strip())[:200], link=f"/conversas/{conversation_id}",
        ref_type="conversation", ref_id=conversation_id, min_role="member",
        project_id=c["context_project_id"], dedupe_parts=("Message.sent", conversation_id, oldest or m["id"]),
        payload={"message_id": m["id"], "kind": kind})
    return {**m, "kind": kind}


def system_note(conn: Connection, *, conversation_id: str, body: str, ref_type: str | None = None,
                ref_id: str | None = None) -> dict:
    """Registra um FATO dentro da conversa (proposta enviada, documento anexado, situação alterada).

    Serve para que a conversa conte a história completa, e não só a parte digitada. O remetente é a conversa em si
    (sem organização), e por isso não dispara aviso: o fato já avisou por conta própria.
    """
    return conn.one(
        "INSERT INTO messages(conversation_id, sender_org_id, sender_user_id, body, kind, ref_type, ref_id)"
        " VALUES ($1, NULL, NULL, $2, 'system', $3, $4) RETURNING id::text AS id, created_at",
        conversation_id, body[:4000], ref_type, ref_id)


def mark_read(conn: Connection, *, conversation_id: str, org_id: str) -> dict:
    """Marca como lido o que a OUTRA parte enviou. Nunca o que a própria organização mandou."""
    _party(conn, conversation_id, org_id)
    n = conn.run("UPDATE messages SET read_at = now() WHERE conversation_id = $1"
                 " AND sender_org_id IS DISTINCT FROM $2 AND read_at IS NULL", conversation_id, org_id)
    return {"read": n}


def close(conn: Connection, *, conversation_id: str, org_id: str, status: str = "closed") -> dict:
    _party(conn, conversation_id, org_id)
    if status not in ("archived", "closed", "open"):
        raise unprocessable("Situação permitida: open, archived ou closed")
    conn.run("UPDATE conversations SET status = $2 WHERE id = $1", conversation_id, status)
    return {"id": conversation_id, "status": status}


# ------------------------------------------------------------------------------------------------ leitura

def _party(conn: Connection, conversation_id: str, org_id: str) -> dict:
    c = conn.one("SELECT id::text AS id, org_a::text AS org_a, org_b::text AS org_b, subject, status,"
                 " context_project_id::text AS context_project_id FROM conversations WHERE id = $1",
                 conversation_id)
    if not c:
        raise not_found("Conversa")
    if org_id not in (c["org_a"], c["org_b"]):
        raise forbidden("Apenas as partes acessam esta conversa")
    return c


def threads(conn: Connection, *, org_id: str, project_id: str | None = None, status: str = "open",
            limit: int = 30, offset: int = 0) -> list[dict]:
    rows = conn.query(
        "SELECT c.id::text AS id, c.subject, c.status, c.last_message_at, c.created_at,"
        " c.context_project_id::text AS context_project_id, c.context_proposal_id::text AS context_proposal_id,"
        " c.context_need_id::text AS context_need_id, c.context_call_id::text AS context_call_id,"
        " CASE WHEN c.org_a = $1 THEN c.org_b::text ELSE c.org_a::text END AS other_org_id,"
        " coalesce(o.trade_name, o.legal_name) AS other_name, o.kind AS other_kind, pr.title AS project_title,"
        " (SELECT count(*) FROM messages m WHERE m.conversation_id = c.id"
        "    AND m.sender_org_id IS DISTINCT FROM $1 AND m.read_at IS NULL AND m.removed_at IS NULL) AS unread,"
        " (SELECT m.body FROM messages m WHERE m.conversation_id = c.id AND m.removed_at IS NULL"
        "    ORDER BY m.created_at DESC LIMIT 1) AS last_body"
        " FROM conversations c"
        " JOIN organizations o ON o.id = CASE WHEN c.org_a = $1 THEN c.org_b ELSE c.org_a END"
        " LEFT JOIN projects pr ON pr.id = c.context_project_id"
        " WHERE (c.org_a = $1 OR c.org_b = $1) AND ($2::text IS NULL OR c.status = $2)"
        "   AND ($3::uuid IS NULL OR c.context_project_id = $3)"
        " ORDER BY coalesce(c.last_message_at, c.created_at) DESC LIMIT $4 OFFSET $5",
        org_id, status, project_id, limit, offset)
    for r in rows:
        r["has_context"] = any(r[k] for k in ("context_project_id", "context_proposal_id", "context_need_id",
                                              "context_call_id"))
    return rows


def thread(conn: Connection, *, conversation_id: str, org_id: str, limit: int = 100,
           before: Any = None) -> dict:
    c = _party(conn, conversation_id, org_id)
    msgs = conn.query(
        "SELECT m.id::text AS id, m.body, m.kind, m.ref_type, m.ref_id::text AS ref_id, m.created_at, m.read_at,"
        " m.sender_org_id::text AS sender_org_id, user_display_name(m.sender_user_id) AS sender_name,"
        " (m.sender_org_id = $2) AS mine,"
        " (SELECT count(*) FROM message_attachments a WHERE a.message_id = m.id) AS attachments"
        " FROM messages m WHERE m.conversation_id = $1 AND m.removed_at IS NULL"
        "   AND ($4::timestamptz IS NULL OR m.created_at < $4)"
        " ORDER BY m.created_at DESC LIMIT $3", conversation_id, org_id, limit, before)
    msgs.reverse()
    for m in msgs:
        if int(m["attachments"] or 0):
            m["documents"] = conn.query(
                "SELECT d.id::text AS id, d.title, d.doc_type FROM message_attachments a"
                " JOIN documents d ON d.id = a.document_id WHERE a.message_id = $1", m["id"])
    return {"conversation": c, "messages": msgs,
            "context": {k: c.get(k) for k in ("context_project_id",) if c.get(k)}}


def unread_count(conn: Connection, org_id: str) -> int:
    return int(conn.scalar(
        "SELECT count(*) FROM messages m JOIN conversations c ON c.id = m.conversation_id"
        " WHERE (c.org_a = $1 OR c.org_b = $1) AND m.sender_org_id IS DISTINCT FROM $1"
        "   AND m.read_at IS NULL AND m.removed_at IS NULL", org_id) or 0)
