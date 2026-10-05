"""Proposta: a conversa que vira combinado — e que NÃO é contrato, nem compromisso, nem pagamento.

ACHADO QUE ORIGINOU ESTE MÓDULO (RECONSTRUCTION_AUDIT.md §2.4): havia três fluxos paralelos de "proposta"
(`need_offers`, `solution_intents`, `partnership_requests`), com três vocabulários de estado e nenhuma versão. Uma OSC
que recebia oferta por necessidade e intenção por solução não tinha uma caixa única para responder.

Distinção que o módulo torna impossível de confundir, porque está no tipo de dado e não num parágrafo:

    proposta  ≠  relação formalizada  ≠  compromisso financeiro  ≠  dinheiro recebido
    (aqui)       (relationships)         (investment_commitments)    (transactions)

`amount_cents` é valor PROPOSTO. Aceitar uma proposta de investimento cria uma relação e uma INTENÇÃO; não cria
compromisso e muito menos recebimento. Essa cadeia é o ADR-022 e a razão de a plataforma nunca escrever "investido"
quando houve apenas interesse.

Versionamento: pedir mudança não apaga o que foi proposto. `changes_requested → sent` incrementa `version` e guarda a
versão anterior em `proposal_events`, de modo que "o que foi proposto quando eu disse não?" tem resposta.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import ApiError, forbidden, not_found, unprocessable
from ..services.audit import ledger
from . import notify, relationships

KINDS = ("investment", "sponsorship", "service", "partnership", "mentorship", "volunteer", "collaboration",
         "project_support", "government_support")

STATUSES = ("draft", "sent", "viewed", "in_review", "changes_requested", "accepted", "declined", "expired",
            "withdrawn", "cancelled")
#: Estados em que a proposta ainda pede ação de alguém. O workspace usa esta lista para montar "o que te espera".
OPEN = ("sent", "viewed", "in_review", "changes_requested")
CLOSED = ("accepted", "declined", "expired", "withdrawn", "cancelled")

#: Relação criada quando a proposta é aceita. Aceitar é o momento em que a rede ganha uma aresta de verdade.
ON_ACCEPT_RELATION: dict[str, str] = {
    "investment": "investment", "sponsorship": "sponsorship", "service": "service", "partnership": "partnership",
    "mentorship": "mentorship", "volunteer": "volunteer", "collaboration": "collaboration",
    "project_support": "support", "government_support": "government_support",
}

LABEL: dict[str, str] = {
    "investment": "Proposta de investimento", "sponsorship": "Proposta de patrocínio",
    "service": "Proposta de serviço", "partnership": "Proposta de parceria", "mentorship": "Oferta de mentoria",
    "volunteer": "Oferta de voluntariado", "collaboration": "Proposta de colaboração",
    "project_support": "Proposta de apoio ao projeto", "government_support": "Proposta de apoio governamental",
}
ST_LABEL: dict[str, str] = {
    "draft": "rascunho", "sent": "enviada", "viewed": "vista", "in_review": "em análise",
    "changes_requested": "ajuste solicitado", "accepted": "aceita", "declined": "recusada", "expired": "expirada",
    "withdrawn": "retirada", "cancelled": "cancelada",
}

#: Contextos aceitos. A lista existe para que "proposta sem contexto" seja impossível, não só desaconselhada.
CONTEXTS = ("project_id", "need_id", "call_id", "solution_id")


def graph(conn: Connection) -> list[dict]:
    """A máquina de estados como está no banco. Serve à interface e aos testes — ninguém a reescreve em TypeScript."""
    return conn.query("SELECT from_status, to_status, actor, requires_note, note FROM proposal_status_graph"
                      " ORDER BY from_status, to_status")


def allowed_from(conn: Connection, status: str, *, side: str) -> list[dict]:
    """Transições que ESTE lado pode fazer a partir deste estado. É o que desenha os botões sem adivinhação."""
    return conn.query(
        "SELECT to_status, requires_note, note FROM proposal_status_graph"
        " WHERE from_status = $1 AND actor IN ($2, 'either') ORDER BY to_status", status, side)


# ------------------------------------------------------------------------------------------------ criação

def create(conn: Connection, *, kind: str, sender_org_id: str, receiver_org_id: str, actor: str | None,
           title: str, purpose: str, terms: str | None = None, amount_cents: int | None = None,
           currency: str = "BRL", support_mode: str | None = None, compensation: str | None = None,
           project_id: str | None = None, need_id: str | None = None, call_id: str | None = None,
           solution_id: str | None = None, expires_at: Any = None) -> dict:
    """Cria a proposta em RASCUNHO. Nasce fechada: `network_initial_state()` no banco garante isso mesmo via SQL direto.

    Nascer em rascunho não é detalhe de interface. Significa que nenhuma proposta chega ao destinatário por acidente de
    requisição repetida, e que quem propõe pode montar valor e anexos antes de a outra parte ver qualquer coisa.
    """
    if kind not in KINDS:
        raise unprocessable(f"Tipo de proposta desconhecido: {kind}")
    if sender_org_id == receiver_org_id:
        raise unprocessable("A organização não envia proposta para ela mesma")
    if not any((project_id, need_id, call_id, solution_id)):
        # Regra do pedido: "nunca criar chat sem contexto quando a relação é profissional". Vale para proposta também —
        # uma proposta sem contexto é um e-mail frio com outro nome.
        raise unprocessable("A proposta precisa de contexto: projeto, necessidade, edital ou solução")
    if relationships.blocked_between(conn, sender_org_id, receiver_org_id):
        raise forbidden("Não é possível propor: há bloqueio entre as organizações", "blocked")

    _check_context(conn, project_id=project_id, need_id=need_id, call_id=call_id, solution_id=solution_id,
                   receiver_org_id=receiver_org_id)

    row = conn.one(
        "INSERT INTO proposals(kind, sender_org_id, sender_user_id, receiver_org_id, project_id, need_id, call_id,"
        " solution_id, title, purpose, terms, amount_cents, currency, support_mode, compensation, expires_at,"
        " created_by) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$3)"
        " RETURNING id::text AS id, status, version, created_at",
        kind, sender_org_id, actor, receiver_org_id, project_id, need_id, call_id, solution_id, title, purpose,
        terms, amount_cents, currency.upper(), support_mode, compensation, expires_at)
    _event(conn, row["id"], None, "draft", actor, sender_org_id, None)
    return {**row, "kind": kind, "label": LABEL[kind]}


def _check_context(conn: Connection, *, project_id: str | None, need_id: str | None, call_id: str | None,
                   solution_id: str | None, receiver_org_id: str) -> None:
    """O contexto citado existe e pertence a quem vai receber? Sem isso, proposta "sobre" projeto alheio passaria."""
    if project_id:
        p = conn.one("SELECT org_id::text AS org_id FROM projects WHERE id = $1", project_id)
        if not p:
            raise not_found("Projeto")
        if p["org_id"] != receiver_org_id:
            raise unprocessable("O projeto citado não pertence à organização destinatária")
    if need_id:
        n = conn.one("SELECT p.org_id::text AS org_id FROM project_needs n JOIN projects p ON p.id = n.project_id"
                     " WHERE n.id = $1", need_id)
        if not n:
            raise not_found("Necessidade")
        if n["org_id"] != receiver_org_id:
            raise unprocessable("A necessidade citada não pertence à organização destinatária")
    if solution_id and not conn.one("SELECT 1 AS ok FROM solutions WHERE id = $1", solution_id):
        raise not_found("Solução")
    if call_id and not conn.one("SELECT 1 AS ok FROM calls WHERE id = $1", call_id):
        raise not_found("Edital")


def update_draft(conn: Connection, *, proposal_id: str, org_id: str, fields: dict[str, Any]) -> dict:
    """Edita a proposta. Fora do rascunho, só depois de "ajuste solicitado" — e aí sai nova versão.

    Permitir edição silenciosa de proposta já enviada seria permitir trocar o valor depois do "sim". A proposta aceita
    é imutável aqui: o que muda a combinação é uma proposta nova.
    """
    p = _load(conn, proposal_id)
    if p["sender_org_id"] != org_id:
        raise forbidden("Apenas quem enviou edita a proposta")
    if p["status"] not in ("draft", "changes_requested"):
        raise ApiError(409, "not_editable",
                       f"Proposta {ST_LABEL[p['status']]} não é editável; envie uma nova proposta")
    allowed = {"title", "purpose", "terms", "amount_cents", "currency", "support_mode", "compensation", "expires_at"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            params.append(v.upper() if k == "currency" else v)
            sets.append(f"{k} = ${len(params) + 1}")
    if not sets:
        return p
    conn.run(f"UPDATE proposals SET {', '.join(sets)} WHERE id = $1", proposal_id, *params)
    return _load(conn, proposal_id)


def attach(conn: Connection, *, proposal_id: str, document_id: str, org_id: str, actor: str | None,
           label: str | None = None) -> dict:
    """Anexa documento do cofre à proposta e AVISA a equipe — "documentos juntados" é um dos eventos do pedido."""
    p = _load(conn, proposal_id)
    if org_id not in (p["sender_org_id"], p["receiver_org_id"]):
        raise forbidden("Apenas as partes anexam documentos à proposta")
    d = conn.one("SELECT title, org_id::text AS org_id FROM documents WHERE id = $1", document_id)
    if not d:
        raise not_found("Documento")
    if d["org_id"] != org_id:
        raise forbidden("O documento precisa pertencer à sua organização")
    conn.run("INSERT INTO proposal_attachments(proposal_id, document_id, label, added_by)"
             " VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", proposal_id, document_id, label, actor)
    other = p["receiver_org_id"] if org_id == p["sender_org_id"] else p["sender_org_id"]
    notify.org_event(
        conn, event="Document.attached", org_id=other, actor_user_id=actor,
        title="Documento anexado a uma proposta",
        body=f"“{d['title']}” foi anexado a “{p['title']}”.", link=f"/propostas/{proposal_id}",
        ref_type="proposal", ref_id=proposal_id, min_role="member", project_id=p["project_id"],
        dedupe_parts=("Document.attached", proposal_id, document_id), payload={"document_id": document_id})
    if p["project_id"]:
        # A equipe do projeto também precisa saber: o documento passa a fazer parte da negociação do projeto dela.
        notify.project_event(
            conn, event="Document.attached", project_id=p["project_id"], org_id=p["receiver_org_id"],
            actor_user_id=actor, title="Documento anexado a uma proposta do projeto",
            body=f"“{d['title']}” foi anexado a “{p['title']}”.", link=f"/propostas/{proposal_id}",
            ref_type="proposal", ref_id=proposal_id,
            dedupe_parts=("Document.attached.team", proposal_id, document_id))
    return {"proposal_id": proposal_id, "document_id": document_id, "title": d["title"]}


# ------------------------------------------------------------------------------------------------ transições

def transition(conn: Connection, *, proposal_id: str, to: str, org_id: str, actor: str | None,
               note: str | None = None, system: bool = False) -> dict:
    """Move a proposta. Valida máquina de estados, LADO e exigência de motivo — nessa ordem.

    O gatilho no banco já recusa transição inválida; a validação aqui existe para devolver 409 com a lista do que é
    possível, em vez de um erro de constraint. As duas camadas são deliberadas: a de cima explica, a de baixo garante.
    """
    p = _load(conn, proposal_id)
    if to == p["status"]:
        return {**p, "unchanged": True}
    side = _side(p, org_id, system=system)
    rule = conn.one("SELECT actor, requires_note FROM proposal_status_graph WHERE from_status = $1 AND to_status = $2",
                    p["status"], to)
    if not rule:
        opts = [r["to_status"] for r in conn.query(
            "SELECT to_status FROM proposal_status_graph WHERE from_status = $1", p["status"])]
        raise ApiError(409, "invalid_transition",
                       f"Proposta {ST_LABEL[p['status']]} não pode ir para {ST_LABEL.get(to, to)}",
                       {"permitidas": opts})
    if rule["actor"] == "system" and not system:
        raise forbidden("Esta transição é feita pela plataforma, não pelas partes", "system_only")
    if rule["actor"] in ("sender", "receiver") and not system and side != rule["actor"]:
        raise forbidden(
            "Só quem enviou pode fazer isso" if rule["actor"] == "sender" else "Só quem recebeu pode fazer isso",
            "wrong_side")
    if rule["requires_note"] and not (note and len(note.strip()) >= 3):
        raise unprocessable("Esta decisão exige justificativa (mínimo 3 caracteres)")

    if to == "sent" and p["status"] == "changes_requested":
        return _resend(conn, p, actor=actor, org_id=org_id, note=note)

    # Só `status` e `decision_note` saem daqui. Os carimbos (`sent_at`, `viewed_at`, `decided_at`, `decided_by`) e o
    # número da versão são DERIVADOS pelo gatilho `proposal_status_guard()` e protegidos por `guard_columns` — o
    # cliente não tem como dizer quando a proposta foi vista nem quem decidiu.
    conn.run("UPDATE proposals SET status = $2,"
             " decision_note = CASE WHEN $3::text IS NOT NULL THEN $3 ELSE decision_note END"
             " WHERE id = $1", proposal_id, to, note)
    _event(conn, proposal_id, p["status"], to, actor, org_id if not system else None, note)

    result: dict[str, Any] = {**p, "status": to, "unchanged": False}
    if to == "accepted":
        result["relationship"] = _on_accept(conn, p, actor=actor)
    _announce(conn, p, to=to, actor=actor, note=note, system=system)
    return result


def _resend(conn: Connection, p: dict, *, actor: str | None, org_id: str, note: str | None) -> dict:
    """Reenvio após ajuste pedido: nova versão, não sobrescrita.

    A versão anterior fica no histórico de eventos com o valor que tinha. Sem isso, "você aceitou R$ 50 mil" poderia
    virar "você aceitou R$ 500 mil" com um UPDATE.
    """
    # A transição é só de estado: o gatilho incrementa a versão e limpa visto/decidido. Fazer isso aqui exigiria
    # permissão de escrita nessas colunas, que é exatamente o que não se quer dar ao caminho do cliente.
    conn.run("UPDATE proposals SET status = 'sent' WHERE id = $1", p["id"])
    v = conn.scalar("SELECT version FROM proposals WHERE id = $1", p["id"])
    _event(conn, p["id"], p["status"], "sent", actor, org_id,
           f"versão {v} (anterior: {p['version']}; valor anterior: "
           f"{'não informado' if p['amount_cents'] is None else p['amount_cents']} {p['currency']})"
           + (f" — {note}" if note else ""))
    notify.org_event(
        conn, event="Proposal.sent", org_id=p["receiver_org_id"], actor_user_id=actor,
        title=f"Proposta revisada (versão {v})",
        body=f"“{p['title']}” foi ajustada e reenviada para sua análise.", link=f"/propostas/{p['id']}",
        priority="high", ref_type="proposal", ref_id=p["id"], action_label="Analisar", min_role="member",
        project_id=p["project_id"], dedupe_parts=("Proposal.sent", p["id"], v), payload={"version": v})
    return {**p, "status": "sent", "version": v, "unchanged": False}


def _on_accept(conn: Connection, p: dict, *, actor: str | None) -> dict | None:
    """Aceitar cria a RELAÇÃO (e, em investimento, a INTENÇÃO) — nunca compromisso nem recebimento.

    Esta função é o ponto exato em que a plataforma poderia mentir dizendo "investido". Ela não diz. Cria uma relação
    ativa e, no caso de investimento, uma `investment_intents` com situação `in_negotiation`; `commitment_id` fica
    nulo, e o CHECK da tabela impede que `status='committed'` exista sem compromisso real.
    """
    kind = ON_ACCEPT_RELATION[p["kind"]]
    target_type, target_id = ("project", p["project_id"]) if p["project_id"] else ("org", p["receiver_org_id"])
    rel = relationships.create(
        conn, kind=kind, org_id=p["sender_org_id"], actor=actor, target_type=target_type, target_id=target_id,
        context_project_id=p["project_id"], visibility="participants", status="active",
        note=f"Originada da proposta “{p['title']}”.", metadata={"proposal_id": p["id"], "proposal_kind": p["kind"]})
    conn.run("UPDATE proposals SET relationship_id = $2 WHERE id = $1", p["id"], rel["id"])

    if p["kind"] == "investment" and p["project_id"]:
        conn.run(
            "INSERT INTO investment_intents(investor_org_id, project_id, status, amount_cents, currency,"
            " support_mode, note, proposal_id, created_by) VALUES ($1,$2,'in_negotiation',$3,$4,$5,$6,$7,$8)"
            " ON CONFLICT (investor_org_id, project_id) DO UPDATE SET status = 'in_negotiation',"
            " amount_cents = excluded.amount_cents, proposal_id = excluded.proposal_id",
            p["sender_org_id"], p["project_id"], p["amount_cents"], p["currency"],
            p["support_mode"] or "financial",   # a intenção exige modalidade; proposta sem modalidade é financeira
            "Intenção registrada pelo aceite da proposta. NÃO é compromisso nem valor recebido.", p["id"], actor)
    if p["project_id"]:
        ledger(conn, project_id=p["project_id"], org_id=p["receiver_org_id"], actor=actor,
               entry_type="proposal_accepted", amount_cents=p["amount_cents"], ref_type="proposal", ref_id=p["id"],
               payload={"kind": p["kind"], "relationship_id": rel["id"],
                        "aviso": "valor proposto; não é compromisso nem recebimento"})
    return rel


def _announce(conn: Connection, p: dict, *, to: str, actor: str | None, note: str | None, system: bool) -> None:
    """Quem é avisado em cada transição. Vista não avisa ninguém: seria ruído, e quem enviou vê no painel."""
    event = {"sent": "Proposal.sent", "viewed": "Proposal.viewed", "in_review": "Proposal.in_review",
             "accepted": "Proposal.accepted", "declined": "Proposal.declined",
             "changes_requested": "Proposal.changes_requested", "withdrawn": "Proposal.withdrawn",
             "expired": "Proposal.expired", "cancelled": "Proposal.withdrawn"}.get(to)
    if not event:
        return
    if to in ("viewed", "cancelled"):
        notify.fact_only(conn, event=event, org_id=p["sender_org_id"], actor_user_id=actor,
                         project_id=p["project_id"], ref_type="proposal", ref_id=p["id"])
        return

    # Para quem vai o aviso: o que o destinatário faz avisa quem enviou, e vice-versa.
    to_sender = to in ("accepted", "declined", "changes_requested", "in_review", "expired")
    target_org = p["sender_org_id"] if to_sender else p["receiver_org_id"]
    titles = {
        "sent": f"{LABEL[p['kind']]} recebida", "in_review": "Sua proposta está em análise",
        "accepted": "Proposta aceita", "declined": "Proposta recusada",
        "changes_requested": "Ajuste solicitado na sua proposta", "withdrawn": "Proposta retirada",
        "expired": "Proposta expirada",
    }
    bodies = {
        "sent": f"“{p['title']}” aguarda sua análise.",
        "in_review": f"“{p['title']}” passou a ser analisada pela outra parte.",
        "accepted": f"“{p['title']}” foi aceita. A relação foi criada — ainda sem compromisso financeiro.",
        "declined": f"“{p['title']}” foi recusada. Motivo: {note or 'não informado'}.",
        "changes_requested": f"Pediram ajuste em “{p['title']}”: {note or 'sem detalhe'}.",
        "withdrawn": f"“{p['title']}” foi retirada por quem enviou. Motivo: {note or 'não informado'}.",
        "expired": f"O prazo de “{p['title']}” venceu sem decisão.",
    }
    notify.org_event(
        conn, event=event, org_id=target_org, actor_user_id=None if system else actor, title=titles[to],
        body=bodies[to], link=f"/propostas/{p['id']}",
        priority="high" if to in ("sent", "accepted", "changes_requested") else "normal",
        ref_type="proposal", ref_id=p["id"], min_role="member", project_id=p["project_id"],
        action_label={"sent": "Analisar", "changes_requested": "Revisar"}.get(to),
        dedupe_parts=(event, p["id"], p["version"]), payload={"kind": p["kind"], "status": to})

    # A EQUIPE do projeto é avisada nas decisões — é o pedido explícito: toda a equipe em cada alteração de etapa.
    if p["project_id"] and to in ("accepted", "declined", "changes_requested", "sent", "expired"):
        notify.project_event(
            conn, event=event, project_id=p["project_id"], org_id=p["receiver_org_id"],
            actor_user_id=None if system else actor, title=f"{titles[to]} — {p['title']}", body=bodies[to],
            link=f"/propostas/{p['id']}", ref_type="proposal", ref_id=p["id"],
            priority="high" if to == "accepted" else "normal",
            dedupe_parts=(event, "team", p["id"], p["version"]), payload={"kind": p["kind"], "status": to})


def expire_due(conn: Connection, *, limit: int = 500) -> dict:
    """Expira propostas vencidas. Chamada por job; idempotente por construção (só pega estado aberto com prazo no passado)."""
    rows = conn.query(
        "SELECT id::text AS id FROM proposals WHERE status IN ('sent','viewed','in_review','changes_requested')"
        " AND expires_at IS NOT NULL AND expires_at < now() ORDER BY expires_at LIMIT $1", limit)
    done = 0
    for r in rows:
        transition(conn, proposal_id=r["id"], to="expired", org_id="", actor=None, system=True)
        done += 1
    return {"expired": done, "checked": len(rows)}


# ------------------------------------------------------------------------------------------------ leitura

_SELECT = (
    "SELECT p.id::text AS id, p.kind, p.status, p.version, p.title, p.purpose, p.terms, p.amount_cents, p.currency,"
    " p.support_mode, p.compensation, p.decision_note, p.decided_at, p.viewed_at, p.sent_at, p.expires_at,"
    " p.created_at, p.updated_at, p.sender_org_id::text AS sender_org_id,"
    " p.receiver_org_id::text AS receiver_org_id, p.project_id::text AS project_id, p.need_id::text AS need_id,"
    " p.call_id::text AS call_id, p.solution_id::text AS solution_id,"
    " p.relationship_id::text AS relationship_id,"
    " coalesce(so.trade_name, so.legal_name) AS sender_name,"
    " coalesce(ro.trade_name, ro.legal_name) AS receiver_name,"
    " pr.title AS project_title FROM proposals p"
    " JOIN organizations so ON so.id = p.sender_org_id"
    " JOIN organizations ro ON ro.id = p.receiver_org_id"
    " LEFT JOIN projects pr ON pr.id = p.project_id")


def _load(conn: Connection, proposal_id: str) -> dict:
    r = conn.one(f"{_SELECT} WHERE p.id = $1", proposal_id)
    if not r:
        raise not_found("Proposta")
    return r


def _side(p: dict, org_id: str, *, system: bool) -> str:
    if system:
        return "system"
    if org_id == p["sender_org_id"]:
        return "sender"
    if org_id == p["receiver_org_id"]:
        return "receiver"
    raise forbidden("Apenas as partes acessam esta proposta")


def _event(conn: Connection, proposal_id: str, frm: str | None, to: str, actor: str | None, org: str | None,
           note: str | None) -> None:
    conn.run("INSERT INTO proposal_events(proposal_id, from_status, to_status, actor_user_id, actor_org_id, note)"
             " VALUES ($1,$2,$3,$4,$5,$6)", proposal_id, frm, to, actor, org or None, note)


def get(conn: Connection, *, proposal_id: str, org_id: str, mark_viewed: bool = False,
        actor: str | None = None) -> dict:
    """Carrega a proposta com histórico, anexos e as ações disponíveis para QUEM está olhando."""
    p = _load(conn, proposal_id)
    side = _side(p, org_id, system=False)
    if mark_viewed and side == "receiver" and p["status"] == "sent":
        # Abrir é a prova de que chegou. Marcar aqui evita "não vi" como estado permanente.
        p = transition(conn, proposal_id=proposal_id, to="viewed", org_id=org_id, actor=actor)
    p["label"] = LABEL[p["kind"]]
    p["status_label"] = ST_LABEL[p["status"]]
    p["side"] = side
    p["actions"] = allowed_from(conn, p["status"], side=side)
    p["events"] = conn.query(
        "SELECT from_status, to_status, note, at, user_display_name(actor_user_id) AS actor_name"
        " FROM proposal_events WHERE proposal_id = $1 ORDER BY id", proposal_id)
    p["attachments"] = conn.query(
        "SELECT a.document_id::text AS document_id, a.label, a.added_at, d.title, d.doc_type"
        " FROM proposal_attachments a JOIN documents d ON d.id = a.document_id"
        " WHERE a.proposal_id = $1 ORDER BY a.added_at", proposal_id)
    p["financial_notice"] = ("Proposta aceita cria relação e intenção. Não é contrato, compromisso financeiro nem "
                             "pagamento.")
    return p


def inbox(conn: Connection, *, org_id: str, box: str = "received", status: str | None = None,
          kind: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    """Caixa de propostas. `received`, `sent` ou `all` — uma única caixa para os três fluxos antigos."""
    where = {"received": "p.receiver_org_id = $1", "sent": "p.sender_org_id = $1",
             "all": "(p.receiver_org_id = $1 OR p.sender_org_id = $1)"}[box]
    extra = ""
    if status == "open":
        extra = " AND p.status = ANY($4::text[])"
    rows = conn.query(
        f"{_SELECT} WHERE {where} AND ($2::text IS NULL OR p.kind = $2)"
        f" AND ($3::text IS NULL OR $3 = 'open' OR p.status = $3){extra}"
        f" ORDER BY CASE WHEN p.status IN ('sent','changes_requested') THEN 0 ELSE 1 END, p.created_at DESC"
        f" LIMIT {int(limit)} OFFSET {int(offset)}",
        *([org_id, kind, status, list(OPEN)] if status == "open" else [org_id, kind, status]))
    for r in rows:
        r["label"] = LABEL[r["kind"]]
        r["status_label"] = ST_LABEL[r["status"]]
        r["side"] = "receiver" if r["receiver_org_id"] == org_id else "sender"
        r["awaiting_me"] = (r["side"] == "receiver" and r["status"] in ("sent", "viewed", "in_review")) or (
            r["side"] == "sender" and r["status"] == "changes_requested")
    return rows


def counts(conn: Connection, org_id: str) -> dict[str, int]:
    """Números para o workspace: o que espera por mim, o que espera pelo outro, o que foi aceito."""
    r = conn.one(
        "SELECT count(*) FILTER (WHERE receiver_org_id = $1 AND status IN ('sent','viewed','in_review'))"
        "         AS awaiting_me,"
        " count(*) FILTER (WHERE sender_org_id = $1 AND status = 'changes_requested') AS needs_my_revision,"
        " count(*) FILTER (WHERE sender_org_id = $1 AND status IN ('sent','viewed','in_review')) AS awaiting_other,"
        " count(*) FILTER (WHERE (sender_org_id = $1 OR receiver_org_id = $1) AND status = 'accepted') AS accepted,"
        " count(*) FILTER (WHERE (sender_org_id = $1 OR receiver_org_id = $1) AND status = 'draft') AS drafts"
        " FROM proposals WHERE sender_org_id = $1 OR receiver_org_id = $1", org_id)
    return {k: int(v or 0) for k, v in (r or {}).items()}
