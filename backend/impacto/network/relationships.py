"""Relação unificada: quem está ligado a quem, por quê, e quem pode ver isso.

ACHADO QUE ORIGINOU ESTE MÓDULO (RECONSTRUCTION_AUDIT.md §2.1): "relação" estava espalhada em seis tabelas improvisadas
— `follows`, `favorites`, `org_blocks`, `need_offers`, `solution_intents`, `partnership_requests` — cada uma com suas
colunas, sua ideia de estado e nenhuma noção de visibilidade. Não havia como responder "com quem esta organização se
relaciona?" sem seis consultas, e cada motor novo criaria a sétima tabela.

Agora existe UMA relação (`relationships`) com tipo, origem, destino, contexto, visibilidade, situação e autoria. As
tabelas antigas continuam existindo e funcionando — um gatilho as espelha aqui (`mirrored_from`), de modo que a rede vê
tudo sem que nenhuma rota atual pare.

A regra que este módulo existe para não deixar ninguém violar:

    A EXISTÊNCIA DA RELAÇÃO NÃO IMPLICA QUE ELA SEJA VISÍVEL.

`visible_to()` é a única porta de leitura para quem não é parte, e ela filtra por `visibility`, não por "existe". Um
investidor que acompanha um projeto não deve aparecer na página pública do projeto só porque a linha existe.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection, Json
from ..http import ApiError, forbidden, not_found, unprocessable
from ..services.audit import ledger
from . import notify

# ------------------------------------------------------------------------------------------------ tipos

#: Tipos unilaterais: nascem ativos, não dependem de o outro lado aceitar. Seguir alguém não é pedir permissão.
UNILATERAL = ("favorite", "watchlist", "follow", "block", "referral")
#: Tipos que exigem consentimento: nascem `pending` e só viram `active` quando o destino aceita.
CONSENTED = ("contact", "partnership", "investment", "sponsorship", "service", "mentorship", "volunteer",
             "collaboration", "support", "government_support", "verified_by")
#: Participação em projeto: criada por quem administra o projeto, portanto nasce ativa.
PARTICIPATION = ("project_member", "project_partner", "project_sponsor", "project_investor")
#: Criada pelo motor de propostas, nunca pela mão do usuário — por isso fica fora de `create()`.
ENGINE_ONLY = ("proposal",)

KINDS = UNILATERAL + CONSENTED + PARTICIPATION + ENGINE_ONLY

#: Visibilidade, do mais fechado ao mais aberto. A ordem importa: `at_least()` compara por índice.
VISIBILITY = ("private", "participants", "organization", "network", "public")

#: Visibilidade máxima que cada tipo aceita. Bloqueio NUNCA é visível além de quem bloqueou — publicar um bloqueio
#: seria expor um juízo sobre terceiro. Favorito e watchlist são estratégia de quem investe: também privados.
MAX_VISIBILITY: dict[str, str] = {
    "block": "private", "favorite": "private", "watchlist": "private",
    "contact": "participants", "proposal": "participants",
    "follow": "network", "referral": "network",
}

#: Situações possíveis. `ended` é o fim combinado; `declined` é recusa na entrada; `revoked` é retirada unilateral.
STATUSES = ("pending", "active", "paused", "ended", "declined", "revoked")
CLOSED = ("ended", "declined", "revoked")

#: Transições permitidas. Igual ao ciclo de vida do projeto: a máquina é explícita, não implícita no `UPDATE`.
TRANSITIONS: dict[str, tuple[str, ...]] = {
    "pending": ("active", "declined", "revoked"),
    "active": ("paused", "ended", "revoked"),
    "paused": ("active", "ended", "revoked"),
    "ended": (), "declined": (), "revoked": (),
}

#: Alvos aceitos por tipo. Impede "mentoria de um edital" e outras combinações sem sentido antes de tocar o banco.
TARGETS: dict[str, tuple[str, ...]] = {
    "favorite": ("project", "solution", "call", "org", "idea"),
    "watchlist": ("project", "org", "call"),
    "follow": ("org", "user"),
    "block": ("org", "user"),
    "referral": ("org", "user", "project"),
    "contact": ("org", "user"),
    "proposal": ("org", "user", "project", "need", "call", "solution"),
    "partnership": ("org",), "investment": ("project", "org"), "sponsorship": ("project", "org"),
    "service": ("org", "project"), "mentorship": ("org", "user"), "volunteer": ("project", "org"),
    "collaboration": ("org", "project"), "support": ("project", "org"), "government_support": ("project", "org"),
    "verified_by": ("org", "user"),
    "project_member": ("project",), "project_partner": ("project",), "project_sponsor": ("project",),
    "project_investor": ("project",),
}

_TARGET_COL = {"org": "target_org_id", "user": "target_user_id", "project": "target_project_id",
               "solution": "target_solution_id", "call": "target_call_id", "need": "target_need_id",
               "idea": "target_idea_id"}

_LEDGER = {"project_member": "team_member_added", "project_partner": "partnership_formed",
           "project_sponsor": "partnership_formed", "project_investor": "investment_intent"}


def at_least(visibility: str, floor: str) -> bool:
    """`visibility` é pelo menos tão aberta quanto `floor`?"""
    return VISIBILITY.index(visibility) >= VISIBILITY.index(floor)


def cap_visibility(kind: str, asked: str) -> str:
    """Rebaixa a visibilidade pedida ao teto do tipo, em silêncio e sempre para o lado seguro.

    Rebaixar em vez de recusar é deliberado: quem pede "público" num bloqueio provavelmente errou o campo, e o custo de
    atender o pedido é vazar um juízo sobre terceiro. O custo de rebaixar é um aviso a menos.
    """
    top = MAX_VISIBILITY.get(kind)
    if top and at_least(asked, top):
        return top
    return asked


# ------------------------------------------------------------------------------------------------ escrita

def create(conn: Connection, *, kind: str, org_id: str, actor: str | None, target_type: str, target_id: str,
           source_user_id: str | None = None, context_project_id: str | None = None, role: str | None = None,
           visibility: str = "private", note: str | None = None, evidence_document_id: str | None = None,
           metadata: dict | None = None, status: str | None = None,
           origin_proposal_id: str | None = None) -> dict:
    """Cria a relação. Idempotente por (tipo, origem, destino, contexto): repetir devolve a que existe.

    A idempotência não é conveniência — é correção. "Favoritar" é um botão que o dedo aperta duas vezes, e duas linhas
    de favorito significariam dois avisos e dois pontos na contagem de interesse de um projeto.
    """
    if kind in ENGINE_ONLY:
        raise unprocessable(f"Relação '{kind}' é criada pelo motor correspondente, não diretamente")
    if kind not in KINDS:
        raise unprocessable(f"Tipo de relação desconhecido: {kind}")
    if target_type not in TARGETS[kind]:
        raise unprocessable(f"Relação '{kind}' não se aplica a '{target_type}'",
                            {"aceitos": list(TARGETS[kind])})
    if visibility not in VISIBILITY:
        raise unprocessable(f"Visibilidade desconhecida: {visibility}")
    vis = cap_visibility(kind, visibility)
    st = status or ("pending" if kind in CONSENTED else "active")
    if st not in STATUSES:
        raise unprocessable(f"Situação desconhecida: {st}")

    # Não se relaciona com si mesma: evita grafo com laço e contagem de rede inflada artificialmente.
    if target_type == "org" and target_id == org_id:
        raise unprocessable("A organização não pode criar relação com ela mesma")

    col = _TARGET_COL[target_type]
    existing = conn.one(
        f"SELECT id::text AS id, kind, status, visibility FROM relationships"
        f" WHERE kind = $1 AND coalesce(source_org_id, source_user_id) = coalesce($2::uuid, $3::uuid)"
        f"   AND {col} = $4 AND coalesce(context_project_id, '00000000-0000-0000-0000-000000000000'::uuid)"
        f"       = coalesce($5::uuid, '00000000-0000-0000-0000-000000000000'::uuid)",
        kind, None if source_user_id else org_id, source_user_id, target_id, context_project_id)
    if existing:
        return {**existing, "created": False}

    row = conn.one(
        f"INSERT INTO relationships(kind, source_org_id, source_user_id, {col}, org_id, context_project_id, role,"
        f" visibility, status, note, evidence_document_id, metadata, created_by, origin_proposal_id)"
        f" VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13,$14)"
        f" RETURNING id::text AS id, kind, status, visibility, created_at",
        kind, None if source_user_id else org_id, source_user_id, target_id, org_id, context_project_id, role,
        vis, st, note, evidence_document_id, Json(metadata or {}), actor, origin_proposal_id)

    project_id = target_id if target_type == "project" else context_project_id
    if project_id:
        _announce_project(conn, row, kind=kind, project_id=project_id, org_id=org_id, actor=actor)
    elif target_type == "org":
        _announce_org(conn, row, kind=kind, target_org=target_id, org_id=org_id, actor=actor)

    if kind in _LEDGER and project_id:
        # A trilha encadeada registra o fato no histórico do projeto. Só os tipos que mudam QUEM participa entram:
        # favoritar não é fato do projeto, é estratégia de quem favoritou (e é privado).
        ledger(conn, project_id=project_id, org_id=org_id, actor=actor, entry_type=_LEDGER[kind],
               ref_type="relationship", ref_id=row["id"], payload={"kind": kind, "role": role})
    return {**row, "created": True}


def _announce_project(conn: Connection, row: dict, *, kind: str, project_id: str, org_id: str,
                      actor: str | None) -> None:
    """Avisa a equipe do projeto — exceto nos tipos privados, em que o aviso seria o próprio vazamento."""
    if kind in ("favorite", "watchlist", "block"):
        notify.fact_only(conn, event="Relationship.created", org_id=org_id, actor_user_id=actor,
                         project_id=project_id, ref_type="relationship", ref_id=row["id"],
                         payload={"kind": kind, "visibility": row["visibility"]})
        return
    p = conn.one("SELECT title FROM projects WHERE id = $1", project_id)
    notify.project_event(
        conn, event="Relationship.created", project_id=project_id, org_id=org_id, actor_user_id=actor,
        title=f"Nova relação no projeto: {LABEL.get(kind, kind)}",
        body=f"{LABEL.get(kind, kind)} registrada em “{(p or {}).get('title', 'projeto')}”."
             f" Situação: {'aguardando aceite' if row['status'] == 'pending' else 'ativa'}.",
        link=f"/projetos/{project_id}", ref_type="relationship", ref_id=row["id"],
        payload={"kind": kind, "status": row["status"]})


def _announce_org(conn: Connection, row: dict, *, kind: str, target_org: str, org_id: str,
                  actor: str | None) -> None:
    """Avisa a organização de destino. Bloqueio e favorito nunca avisam — o alvo não deve saber."""
    if kind in ("block", "favorite", "watchlist"):
        notify.fact_only(conn, event="Relationship.created", org_id=org_id, actor_user_id=actor,
                         ref_type="relationship", ref_id=row["id"], payload={"kind": kind})
        return
    src = conn.one("SELECT coalesce(trade_name, legal_name) AS name FROM organizations WHERE id = $1", org_id)
    name = (src or {}).get("name") or "Uma organização"
    pend = row["status"] == "pending"
    notify.org_event(
        conn, event="Relationship.created", org_id=target_org, actor_user_id=actor,
        title=f"{name}: {LABEL.get(kind, kind)}",
        body=f"{name} registrou {LABEL.get(kind, kind).lower()}."
             + (" Depende do seu aceite." if pend else ""),
        link="/rede/relacoes", priority="high" if pend else "normal", ref_type="relationship", ref_id=row["id"],
        action_label="Responder" if pend else None, min_role="member", payload={"kind": kind})


def transition(conn: Connection, *, rel_id: str, to: str, org_id: str, user_id: str | None, actor: str | None,
               reason: str | None = None) -> dict:
    """Muda a situação da relação, validando a máquina de estados e quem tem direito de mudar.

    Quem aceita não é quem propôs: `pending → active` só pelo lado de destino. Sem essa checagem, uma organização
    poderia declarar-se parceira de outra sozinha — e a plataforma existe para que uma afirmação dessas valha algo.
    """
    r = conn.one(
        "SELECT id::text AS id, kind, status, visibility, org_id::text AS org_id,"
        " source_org_id::text AS source_org_id, source_user_id::text AS source_user_id,"
        " target_org_id::text AS target_org_id, target_user_id::text AS target_user_id,"
        " target_project_id::text AS target_project_id, context_project_id::text AS context_project_id,"
        " mirrored_from FROM relationships WHERE id = $1", rel_id)
    if not r:
        raise not_found("Relação")
    if r["mirrored_from"]:
        raise unprocessable("Esta relação é espelho de outra tabela; altere na origem",
                            {"origem": r["mirrored_from"]})
    if to not in STATUSES:
        raise unprocessable(f"Situação desconhecida: {to}")
    if r["status"] == to:
        return {**r, "unchanged": True}
    if to not in TRANSITIONS[r["status"]]:
        raise ApiError(409, "invalid_transition", f"Transição {r['status']} → {to} não é permitida",
                       {"permitidas": list(TRANSITIONS[r["status"]])})

    is_source = org_id in (r["source_org_id"], r["org_id"]) or (user_id and user_id == r["source_user_id"])
    is_target = org_id == r["target_org_id"] or (user_id and user_id == r["target_user_id"]) or _owns_target_project(
        conn, r, org_id)
    if to in ("active", "declined") and r["status"] == "pending" and not is_target:
        raise forbidden("Só o lado de destino aceita ou recusa uma relação pendente", "not_target")
    if to == "revoked" and not is_source:
        raise forbidden("Só quem criou a relação pode revogá-la", "not_source")
    if to in ("paused", "ended") and not (is_source or is_target):
        raise forbidden("Apenas as partes alteram a relação")
    if to in CLOSED and not (reason and len(reason.strip()) >= 3):
        # Encerramento sem motivo é o que torna um histórico de rede inútil seis meses depois.
        raise unprocessable("Informe o motivo do encerramento (mínimo 3 caracteres)")

    conn.run("UPDATE relationships SET status = $2, ended_at = CASE WHEN $2 IN ('ended','declined','revoked')"
             " THEN now() ELSE NULL END, ended_reason = $3 WHERE id = $1", rel_id, to, reason)
    project_id = r["target_project_id"] or r["context_project_id"]
    event = "Relationship.ended" if to in CLOSED else "Relationship.created"
    if project_id:
        notify.project_event(
            conn, event=event, project_id=project_id, org_id=r["org_id"], actor_user_id=actor,
            title=f"{LABEL.get(r['kind'], r['kind'])}: {ST_LABEL[to]}",
            body=reason or f"Situação alterada de {ST_LABEL[r['status']]} para {ST_LABEL[to]}.",
            link=f"/projetos/{project_id}", ref_type="relationship", ref_id=rel_id,
            dedupe_parts=(event, rel_id, to), payload={"from": r["status"], "to": to})
    else:
        other = r["target_org_id"] if is_source else r["source_org_id"]
        if other:
            notify.org_event(
                conn, event=event, org_id=other, actor_user_id=actor,
                title=f"{LABEL.get(r['kind'], r['kind'])}: {ST_LABEL[to]}",
                body=reason or f"A outra parte alterou a situação para {ST_LABEL[to]}.",
                link="/rede/relacoes", ref_type="relationship", ref_id=rel_id, min_role="member",
                dedupe_parts=(event, rel_id, to), payload={"from": r["status"], "to": to})
    return {**r, "status": to, "unchanged": False}


def _owns_target_project(conn: Connection, r: dict, org_id: str) -> bool:
    if not r["target_project_id"]:
        return False
    return bool(conn.one("SELECT 1 AS ok FROM projects WHERE id = $1 AND org_id = $2", r["target_project_id"], org_id))


def set_visibility(conn: Connection, *, rel_id: str, visibility: str, org_id: str, actor: str | None) -> dict:
    """Só quem criou a relação muda a visibilidade dela, e sempre limitada ao teto do tipo."""
    r = conn.one("SELECT kind, org_id::text AS org_id, source_org_id::text AS source_org_id, visibility"
                 " FROM relationships WHERE id = $1", rel_id)
    if not r:
        raise not_found("Relação")
    if org_id not in (r["org_id"], r["source_org_id"]):
        raise forbidden("Apenas quem criou a relação altera a visibilidade dela")
    if visibility not in VISIBILITY:
        raise unprocessable(f"Visibilidade desconhecida: {visibility}")
    vis = cap_visibility(r["kind"], visibility)
    conn.run("UPDATE relationships SET visibility = $2 WHERE id = $1", rel_id, vis)
    return {"id": rel_id, "visibility": vis, "capped": vis != visibility}


# ------------------------------------------------------------------------------------------------ leitura

_SELECT = (
    "SELECT r.id::text AS id, r.kind, r.status, r.visibility, r.role, r.note, r.created_at, r.updated_at,"
    " r.ended_at, r.ended_reason, r.mirrored_from, r.metadata,"
    " r.org_id::text AS org_id, r.source_org_id::text AS source_org_id, r.source_user_id::text AS source_user_id,"
    " r.target_org_id::text AS target_org_id, r.target_user_id::text AS target_user_id,"
    " r.target_project_id::text AS target_project_id, r.target_solution_id::text AS target_solution_id,"
    " r.target_call_id::text AS target_call_id, r.target_need_id::text AS target_need_id,"
    " r.target_idea_id::text AS target_idea_id, r.context_project_id::text AS context_project_id,"
    " r.evidence_document_id::text AS evidence_document_id,"
    " coalesce(so.trade_name, so.legal_name) AS source_org_name,"
    " coalesce(tgo.trade_name, tgo.legal_name) AS target_org_name, tp.title AS target_project_title,"
    " user_display_name(r.target_user_id) AS target_user_name,"
    " user_display_name(r.source_user_id) AS source_user_name"
    " FROM relationships r"
    " LEFT JOIN organizations so ON so.id = r.source_org_id"
    " LEFT JOIN organizations tgo ON tgo.id = r.target_org_id"
    " LEFT JOIN projects tp ON tp.id = r.target_project_id")


def mine(conn: Connection, *, org_id: str, kind: str | None = None, status: str | None = None,
         direction: str = "all", limit: int = 50, offset: int = 0) -> list[dict]:
    """Relações da própria organização, nas duas direções. A RLS já limita; o filtro aqui é conveniência de leitura."""
    where = {"out": "r.source_org_id = $1", "in": "r.target_org_id = $1",
             "all": "(r.source_org_id = $1 OR r.target_org_id = $1 OR r.org_id = $1)"}[direction]
    rows = conn.query(
        f"{_SELECT} WHERE {where} AND ($2::text IS NULL OR r.kind = $2) AND ($3::text IS NULL OR r.status = $3)"
        f" ORDER BY r.created_at DESC LIMIT $4 OFFSET $5", org_id, kind, status, limit, offset)
    for r in rows:
        r["label"] = LABEL.get(r["kind"], r["kind"])
        r["direction"] = "out" if r["source_org_id"] == org_id else "in"
    return rows


def visible_to(conn: Connection, *, subject_type: str, subject_id: str, viewer_org_id: str | None,
               authenticated: bool, limit: int = 50) -> list[dict]:
    """Relações de um sujeito que ESTE observador pode ver. Única porta para quem não é parte.

    O filtro é por `visibility`, nunca por "a relação existe":
      * `public`      — qualquer pessoa, inclusive sem conta;
      * `network`     — quem tem conta;
      * `organization`— membros da organização dona;
      * `participants`/`private` — nunca saem por aqui (a parte usa `mine()`, que passa pela RLS).
    """
    col = _TARGET_COL.get(subject_type)
    if subject_type == "org":
        scope = "(r.source_org_id = $1 OR r.target_org_id = $1)"
    elif col:
        scope = f"r.{col} = $1"
    else:
        raise unprocessable(f"Sujeito desconhecido: {subject_type}")
    allowed = ["public"] + (["network"] if authenticated else [])
    rows = conn.query(
        f"{_SELECT} WHERE {scope} AND r.status = 'active' AND (r.visibility = ANY($2::text[])"
        f"  OR ($3::uuid IS NOT NULL AND r.visibility = 'organization' AND r.org_id = $3))"
        f" ORDER BY r.created_at DESC LIMIT $4", subject_id, allowed, viewer_org_id, limit)
    for r in rows:
        r["label"] = LABEL.get(r["kind"], r["kind"])
    return rows


def graph(conn: Connection, *, org_id: str, depth: int = 1, limit: int = 200) -> dict[str, Any]:
    """Vizinhança da organização no grafo, em profundidade 1 ou 2.

    POR QUE SEM BANCO DE GRAFOS: a pergunta real do produto é "quem está a um ou dois passos de mim?", que em SQL com
    índice em `source_org_id`/`target_org_id` responde em milissegundos. Profundidade maior não tem uso declarado no
    produto, e introduzir um banco de grafos sem necessidade comprovada seria exatamente o que o pedido proíbe. Se um
    dia houver pergunta de caminho longo (centralidade, menor caminho), aí a decisão se reabre com medição.
    """
    depth = 1 if depth < 2 else 2
    rows = conn.query(
        "WITH RECURSIVE n(org_id, hop) AS ("
        "  SELECT $1::uuid, 0"
        "  UNION"
        "  SELECT CASE WHEN r.source_org_id = n.org_id THEN r.target_org_id ELSE r.source_org_id END, n.hop + 1"
        "    FROM relationships r JOIN n ON (r.source_org_id = n.org_id OR r.target_org_id = n.org_id)"
        "   WHERE n.hop < $2 AND r.status = 'active' AND r.kind <> 'block'"
        "     AND r.visibility IN ('network','public','organization')"
        "     AND CASE WHEN r.source_org_id = n.org_id THEN r.target_org_id ELSE r.source_org_id END IS NOT NULL)"
        " SELECT n.org_id::text AS org_id, min(n.hop) AS hop,"
        "        coalesce(o.trade_name, o.legal_name) AS name, o.kind AS org_kind, o.uf"
        "   FROM n JOIN organizations o ON o.id = n.org_id WHERE n.hop > 0"
        "  GROUP BY n.org_id, o.trade_name, o.legal_name, o.kind, o.uf"
        "  ORDER BY min(n.hop), coalesce(o.trade_name, o.legal_name) LIMIT $3",
        org_id, depth, limit)
    return {"depth": depth, "nodes": rows, "count": len(rows),
            "note": "Somente relações ativas e de visibilidade rede/pública/organização. Bloqueios não entram."}


def blocked_between(conn: Connection, a_org: str, b_org: str) -> bool:
    """Há bloqueio em qualquer direção? Reusa a função do banco, que já é a verdade usada pela RLS."""
    return bool(conn.scalar("SELECT app_blocked_between($1,$2)", a_org, b_org))


def counts(conn: Connection, org_id: str) -> dict[str, int]:
    """Contagens para o workspace. Só tipos não privados entram em número exibível a terceiros."""
    rows = conn.query(
        "SELECT kind, status, count(*) AS n FROM relationships"
        " WHERE (source_org_id = $1 OR target_org_id = $1) GROUP BY kind, status", org_id)
    out: dict[str, int] = {"active": 0, "pending_in": 0, "pending_out": 0}
    for r in rows:
        if r["status"] == "active":
            out["active"] += int(r["n"])
        out[f"{r['kind']}_{r['status']}"] = int(r["n"])
    out["pending_in"] = int(conn.scalar(
        "SELECT count(*) FROM relationships WHERE target_org_id = $1 AND status = 'pending'", org_id) or 0)
    out["pending_out"] = int(conn.scalar(
        "SELECT count(*) FROM relationships WHERE source_org_id = $1 AND status = 'pending'", org_id) or 0)
    return out


# ------------------------------------------------------------------------------------------------ rótulos
LABEL: dict[str, str] = {
    "favorite": "Favorito", "watchlist": "Acompanhamento", "follow": "Seguindo", "block": "Bloqueio",
    "contact": "Contato", "proposal": "Proposta", "partnership": "Parceria", "investment": "Investimento",
    "sponsorship": "Patrocínio", "service": "Prestação de serviço", "mentorship": "Mentoria",
    "volunteer": "Voluntariado", "collaboration": "Colaboração", "support": "Apoio",
    "government_support": "Apoio governamental", "project_member": "Integrante do projeto",
    "project_partner": "Organização parceira", "project_sponsor": "Patrocinadora do projeto",
    "project_investor": "Investidora do projeto", "referral": "Indicação", "verified_by": "Verificada por",
}
ST_LABEL: dict[str, str] = {
    "pending": "aguardando aceite", "active": "ativa", "paused": "pausada", "ended": "encerrada",
    "declined": "recusada", "revoked": "revogada",
}
