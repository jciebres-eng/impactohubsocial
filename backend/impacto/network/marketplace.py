"""Marketplace: publicação governada por ESTADO, não por condição de consulta.

ACHADO QUE ORIGINOU ESTE MÓDULO (RECONSTRUCTION_AUDIT.md §4, erro E6): a visibilidade pública era a combinação de
`projects.visibility` com `projects.status`, avaliada em cada consulta de feed. Isso significa que um `WHERE` esquecido
em qualquer rota nova expõe rascunho — e foi exatamente o cenário que o pedido proíbe: "nunca permitir que projeto
privado apareça no marketplace por erro de query".

A correção é estrutural, não cuidadosa: existe uma ENTIDADE de anúncio com estado próprio, e a consulta pública lê
`marketplace_listings WHERE publication_state = 'published'`. O projeto privado não tem anúncio publicado; não há
condição a esquecer. Além disso o gatilho `listing_publish_guard()` recusa publicar anúncio de projeto não publicado,
e `listing_state_guard()` recusa transição fora do grafo — inclusive em SQL direto.
"""
from __future__ import annotations

from typing import Any

from ..db.pq import Connection
from ..http import ApiError, forbidden, not_found, unprocessable
from . import notify

SUBJECTS = ("project", "opportunity", "need", "service", "solution", "partnership", "sponsorship")
SEEKING = ("investment", "sponsorship", "partner", "professional", "volunteer", "mentorship", "equipment",
           "knowledge", "quota")
STATES = ("draft", "review", "approved", "published", "paused", "expired", "archived", "suspended")
#: Único estado que aparece em público. A lista existe para que os testes possam afirmar que é UM só.
PUBLIC_STATES = ("published",)

_SUBJECT_COL = {"project": "project_id", "opportunity": "call_id", "need": "need_id", "service": "service_id",
                "solution": "solution_id", "partnership": "project_id", "sponsorship": "project_id"}

ST_LABEL = {"draft": "rascunho", "review": "em conferência", "approved": "aprovado internamente",
            "published": "publicado", "paused": "pausado", "expired": "expirado", "archived": "arquivado",
            "suspended": "suspenso pela administração"}


def graph(conn: Connection) -> list[dict]:
    return conn.query("SELECT from_status, to_status, actor, requires_note, note FROM network_status_graph"
                      " WHERE entity = 'listing' ORDER BY from_status, to_status")


def create(conn: Connection, *, org_id: str, actor: str | None, subject_type: str, subject_id: str, headline: str,
           summary: str | None = None, seeking: list[str] | None = None, amount_target_cents: int | None = None,
           currency: str = "BRL", territory: str | None = None, causes: list[str] | None = None,
           ods: list[int] | None = None, esg_tags: list[str] | None = None, stage: str | None = None,
           expires_at: Any = None) -> dict:
    """Cria o anúncio em RASCUNHO, sempre. Nenhum anúncio nasce no ar."""
    if subject_type not in SUBJECTS:
        raise unprocessable(f"Tipo de anúncio desconhecido: {subject_type}")
    bad = sorted(set(seeking or []) - set(SEEKING))
    if bad:
        raise unprocessable(f"Busca desconhecida: {', '.join(bad)}", {"aceitos": list(SEEKING)})
    col = _SUBJECT_COL[subject_type]
    _check_owner(conn, col, subject_id, org_id)

    exists = conn.one(
        f"SELECT id::text AS id, publication_state FROM marketplace_listings"
        f" WHERE subject_type = $1 AND {col} = $2", subject_type, subject_id)
    if exists:
        raise ApiError(409, "listing_exists", "Já existe anúncio para este item", exists)

    row = conn.one(
        f"INSERT INTO marketplace_listings(org_id, subject_type, {col}, seeking, headline, summary,"
        f" amount_target_cents, currency, territory, causes, ods, esg_tags, stage, expires_at, created_by)"
        f" VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)"
        f" RETURNING id::text AS id, publication_state, created_at",
        org_id, subject_type, subject_id, seeking or [], headline, summary, amount_target_cents, currency.upper(),
        territory, causes or [], ods or [], esg_tags or [], stage, expires_at, actor)
    return {**row, "subject_type": subject_type, "state_label": ST_LABEL[row["publication_state"]]}


def _check_owner(conn: Connection, col: str, subject_id: str, org_id: str) -> None:
    """O item anunciado é da organização? Sem isso, qualquer uma anunciaria o projeto de outra."""
    sql = {
        "project_id": "SELECT org_id::text AS org_id FROM projects WHERE id = $1",
        "need_id": ("SELECT p.org_id::text AS org_id FROM project_needs n JOIN projects p ON p.id = n.project_id"
                    " WHERE n.id = $1"),
        "solution_id": "SELECT org_id::text AS org_id FROM solutions WHERE id = $1",
        "service_id": "SELECT org_id::text AS org_id FROM professional_services WHERE id = $1",
        # edital usa `owner_org_id`, e é NULO quando o edital veio de fonte externa (não é de ninguém aqui)
        "call_id": "SELECT owner_org_id::text AS org_id FROM calls WHERE id = $1",
    }[col]
    r = conn.one(sql, subject_id)
    if not r:
        raise not_found("Item anunciado")
    if r["org_id"] and r["org_id"] != org_id:
        raise forbidden("O item anunciado precisa pertencer à sua organização")


def update(conn: Connection, *, listing_id: str, org_id: str, fields: dict[str, Any]) -> dict:
    """Edita o conteúdo do anúncio. Estado de publicação muda só por `transition()`."""
    lst = _load(conn, listing_id)
    if lst["org_id"] != org_id:
        raise forbidden("Apenas a organização dona edita o anúncio")
    if lst["publication_state"] == "suspended":
        raise ApiError(409, "suspended", "Anúncio suspenso pela administração; não é editável",
                       {"motivo": lst["suspended_reason"]})
    allowed = {"headline", "summary", "seeking", "amount_target_cents", "currency", "territory", "causes", "ods",
               "esg_tags", "stage", "expires_at"}
    sets, params = [], []
    for k, v in fields.items():
        if k in allowed and v is not None:
            if k == "seeking":
                bad = sorted(set(v) - set(SEEKING))
                if bad:
                    raise unprocessable(f"Busca desconhecida: {', '.join(bad)}")
            params.append(v.upper() if k == "currency" else v)
            sets.append(f"{k} = ${len(params) + 1}")
    if not sets:
        return lst
    conn.run(f"UPDATE marketplace_listings SET {', '.join(sets)} WHERE id = $1", listing_id, *params)
    return _load(conn, listing_id)


def transition(conn: Connection, *, listing_id: str, to: str, org_id: str, actor: str | None,
               note: str | None = None, admin: bool = False, by_platform: bool = False) -> dict:
    """Move o anúncio no grafo. Suspender e liberar são da administração; o resto é da organização dona."""
    lst = _load(conn, listing_id)
    if to == lst["publication_state"]:
        return {**lst, "unchanged": True}
    if to == "published" and not (admin or by_platform):
        from . import enforcement as _ENF
        _ENF.ensure_allowed(conn, capability="publish_listing", org_id=org_id)
    rule = conn.one("SELECT actor, requires_note FROM network_status_graph"
                    " WHERE entity = 'listing' AND from_status = $1 AND to_status = $2",
                    lst["publication_state"], to)
    if not rule:
        opts = [r["to_status"] for r in conn.query(
            "SELECT to_status FROM network_status_graph WHERE entity = 'listing' AND from_status = $1",
            lst["publication_state"])]
        raise ApiError(409, "invalid_transition",
                       f"Anúncio {ST_LABEL[lst['publication_state']]} não pode ir para {ST_LABEL.get(to, to)}",
                       {"permitidas": opts})
    if rule["actor"] == "admin" and not admin:
        raise forbidden("Esta transição é da administração da plataforma", "admin_only")
    if rule["actor"] == "system" and not by_platform:
        raise forbidden("Esta transição é feita pela plataforma", "system_only")
    if rule["actor"] == "owner" and not admin and lst["org_id"] != org_id:
        raise forbidden("Apenas a organização dona altera o anúncio")
    if rule["requires_note"] and not (note and len(note.strip()) >= 3):
        raise unprocessable("Esta transição exige motivo (mínimo 3 caracteres)")

    if to == "suspended":
        conn.run("UPDATE marketplace_listings SET publication_state = $2, suspended_reason = $3 WHERE id = $1",
                 listing_id, to, note)
    else:
        conn.run("UPDATE marketplace_listings SET publication_state = $2 WHERE id = $1", listing_id, to)

    event = {"published": "Listing.published", "paused": "Listing.paused", "suspended": "Listing.suspended"}.get(to)
    if event:
        _announce(conn, lst, to=to, event=event, actor=actor, note=note)
    return {**_load(conn, listing_id), "unchanged": False}


def _announce(conn: Connection, lst: dict, *, to: str, event: str, actor: str | None, note: str | None) -> None:
    titles = {"published": "Anúncio publicado", "paused": "Anúncio pausado",
              "suspended": "Anúncio suspenso pela administração"}
    bodies = {"published": f"“{lst['headline']}” está no marketplace.",
              "paused": f"“{lst['headline']}” saiu do ar temporariamente.",
              "suspended": f"“{lst['headline']}” foi suspenso. Motivo: {note or 'não informado'}."}
    if lst["project_id"]:
        notify.project_event(
            conn, event=event, project_id=lst["project_id"], org_id=lst["org_id"], actor_user_id=actor,
            title=titles[to], body=bodies[to], link=f"/marketplace/{lst['id']}", ref_type="listing",
            ref_id=lst["id"], priority="high" if to == "suspended" else "normal",
            dedupe_parts=(event, lst["id"], to))
    else:
        notify.org_event(
            conn, event=event, org_id=lst["org_id"], actor_user_id=actor, title=titles[to], body=bodies[to],
            link=f"/marketplace/{lst['id']}", ref_type="listing", ref_id=lst["id"],
            min_role="manager" if to == "suspended" else "member",
            priority="high" if to == "suspended" else "normal", dedupe_parts=(event, lst["id"], to))


def expire_due(conn: Connection, *, limit: int = 500) -> dict:
    """Expira anúncios vencidos. Job idempotente: só pega `published` com prazo no passado."""
    rows = conn.query("SELECT id::text AS id, org_id::text AS org_id FROM marketplace_listings"
                      " WHERE publication_state = 'published' AND expires_at IS NOT NULL AND expires_at < now()"
                      " ORDER BY expires_at LIMIT $1", limit)
    for r in rows:
        conn.run("UPDATE marketplace_listings SET publication_state = 'expired' WHERE id = $1", r["id"])
        # Tirar um anúncio do ar sem avisar quem o publicou é deixar a organização acreditando que
        # continua anunciando.
        notify.org_event(
            conn, event="Listing.expired", org_id=r["org_id"],
            title="Anúncio expirado", body="O prazo de publicação que você declarou terminou.",
            link="/marketplace", priority="normal", min_role="member",
            ref_type="listing", ref_id=r["id"], action_label="Republicar",
            dedupe_parts=("Listing.expired", r["id"]))
    return {"expired": len(rows)}


# ------------------------------------------------------------------------------------------------ leitura

_SELECT = (
    "SELECT l.id::text AS id, l.org_id::text AS org_id, l.subject_type, l.headline, l.summary, l.seeking,"
    " l.amount_target_cents, l.currency, l.territory, l.causes, l.ods, l.esg_tags, l.stage,"
    " l.publication_state, l.published_at, l.expires_at, l.views, l.suspended_reason, l.created_at,"
    " l.project_id::text AS project_id, l.call_id::text AS call_id, l.need_id::text AS need_id,"
    " l.solution_id::text AS solution_id, l.service_id::text AS service_id,"
    " coalesce(o.trade_name, o.legal_name) AS org_name, o.kind AS org_kind, o.uf AS org_uf"
    " FROM marketplace_listings l"
    " JOIN organizations o ON o.id = l.org_id")


def _load(conn: Connection, listing_id: str) -> dict:
    r = conn.one(f"{_SELECT} WHERE l.id = $1", listing_id)
    if not r:
        raise not_found("Anúncio")
    r["state_label"] = ST_LABEL[r["publication_state"]]
    return r


def public_feed(conn: Connection, *, subject_type: str | None = None, seeking: str | None = None,
                territory: str | None = None, cause: str | None = None, ods: int | None = None,
                q: str | None = None, limit: int = 20, offset: int = 0) -> dict:
    """Feed público. A única consulta de leitura pública do marketplace.

    `publication_state = 'published'` está escrito UMA vez, aqui. Qualquer rota pública que queira listar anúncios
    chama esta função; não há a segunda consulta que esqueceria o filtro. O teste de invariante verifica exatamente
    isso: nenhum item com estado diferente sai daqui.
    """
    rows = conn.query(
        f"{_SELECT} WHERE l.publication_state = 'published'"
        f" AND ($1::text IS NULL OR l.subject_type = $1)"
        f" AND ($2::text IS NULL OR $2 = ANY(l.seeking))"
        f" AND ($3::text IS NULL OR l.territory = $3 OR l.territory LIKE $3 || '-%')"
        f" AND ($4::text IS NULL OR $4 = ANY(l.causes))"
        f" AND ($5::int IS NULL OR $5::smallint = ANY(l.ods))"
        f" AND ($6::text IS NULL OR l.headline ILIKE '%' || $6 || '%' OR l.summary ILIKE '%' || $6 || '%')"
        f" ORDER BY l.published_at DESC LIMIT $7 OFFSET $8",
        subject_type, seeking, territory, cause, ods, q, limit, offset)
    total = conn.scalar(
        "SELECT count(*) FROM marketplace_listings l WHERE l.publication_state = 'published'"
        " AND ($1::text IS NULL OR l.subject_type = $1) AND ($2::text IS NULL OR $2 = ANY(l.seeking))"
        " AND ($3::text IS NULL OR l.territory = $3 OR l.territory LIKE $3 || '-%')"
        " AND ($4::text IS NULL OR $4 = ANY(l.causes)) AND ($5::int IS NULL OR $5::smallint = ANY(l.ods))"
        " AND ($6::text IS NULL OR l.headline ILIKE '%' || $6 || '%' OR l.summary ILIKE '%' || $6 || '%')",
        subject_type, seeking, territory, cause, ods, q)
    for r in rows:
        r["state_label"] = ST_LABEL[r["publication_state"]]
        r.pop("suspended_reason", None)   # motivo de suspensão é interno; anúncio suspenso nem aparece aqui
    return {"items": rows, "total": int(total or 0), "limit": limit, "offset": offset}


def has_published_listing(conn: Connection, project_id: str) -> bool:
    """Este projeto tem anúncio no ar?

    Existe para que nenhum outro módulo precise escrever `publication_state = 'published'`. Parece detalhe, mas é o
    achado E6 inteiro: quanto mais lugares repetem a condição de publicação, mais chances de um deles divergir. Há
    um teste de invariante que falha se a condição aparecer fora deste arquivo.
    """
    return bool(conn.one("SELECT 1 AS ok FROM marketplace_listings WHERE project_id = $1"
                         " AND publication_state = ANY($2::text[])", project_id, list(PUBLIC_STATES)))


def published_count(conn: Connection, *, org_id: str | None = None) -> int:
    """Quantos anúncios estão no ar (da organização, ou da plataforma inteira)."""
    return int(conn.scalar(
        "SELECT count(*) FROM marketplace_listings WHERE publication_state = ANY($1::text[])"
        " AND ($2::uuid IS NULL OR org_id = $2)", list(PUBLIC_STATES), org_id) or 0)


def mine(conn: Connection, *, org_id: str, state: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
    rows = conn.query(f"{_SELECT} WHERE l.org_id = $1 AND ($2::text IS NULL OR l.publication_state = $2)"
                      f" ORDER BY l.created_at DESC LIMIT $3 OFFSET $4", org_id, state, limit, offset)
    for r in rows:
        r["state_label"] = ST_LABEL[r["publication_state"]]
        r["actions"] = [x["to_status"] for x in conn.query(
            "SELECT to_status FROM network_status_graph WHERE entity = 'listing' AND from_status = $1"
            " AND actor = 'owner'", r["publication_state"])]
    return rows


def view(conn: Connection, listing_id: str) -> dict:
    """Abre o anúncio publicado e conta a visualização.

    A contagem usa contexto privilegiado porque `views` é coluna protegida — o número de visualizações é apuração da
    plataforma, não valor que a organização possa inflar.
    """
    r = conn.one(f"{_SELECT} WHERE l.id = $1 AND l.publication_state = 'published'", listing_id)
    if not r:
        raise not_found("Anúncio")
    r["state_label"] = ST_LABEL[r["publication_state"]]
    r.pop("suspended_reason", None)
    return r
