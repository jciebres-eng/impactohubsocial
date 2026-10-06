"""Rede: seguir, bloquear, mensagens entre organizações com relação prévia, necessidades de projeto, ofertas e match de profissionais,
conquistas organizacionais. Anti-abuso: só conversa quem tem relação legítima (candidatura, revisão, oferta ou seguimento mútuo),
limites por hora/dia, bloqueio bilateral, denúncia e moderação humana. Sem ranking nem pontuação entre organizações."""
from __future__ import annotations


from ..engines.match import professional as pm
from ..http import ApiError, Ctx, not_found, page, route
from ..services import badges
from . import schemas as S
from ..clock import today as _hoje_utc  # data do produto é UTC; ver impacto/clock.py

T = ("network",)
MAX_MSG_PER_HOUR = 60
MAX_NEW_CONVERSATIONS_PER_DAY = 20


def _org_exists(c, oid: str) -> dict:
    o = c.one("SELECT id::text AS id, kind, legal_name FROM organizations WHERE id = $1 AND status = 'active'", oid)
    if not o:
        raise not_found("Organização")
    return o


# ------------------------------------------------------------------------------------------------ seguir / bloquear
@route("POST", "/v1/network/follow/{org_id}", min_role="member", tags=T, summary="Passa a seguir uma organização (seguimento mútuo habilita mensagens)")
def follow(ctx: Ctx):
    with ctx.tx() as c:
        o = _org_exists(c, ctx.path["org_id"])
        if o["id"] == ctx.org_id:
            raise ApiError(422, "self", "Não é possível seguir a si mesma")
        if c.scalar("SELECT app_blocked_between($1, $2)", ctx.org_id, o["id"]):
            raise ApiError(403, "blocked", "Ação indisponível")
        c.run("INSERT INTO follows(follower_org_id, followed_org_id) VALUES ($1,$2) ON CONFLICT DO NOTHING", ctx.org_id, o["id"])
    return {"following": True}


@route("DELETE", "/v1/network/follow/{org_id}", min_role="member", tags=T)
def unfollow(ctx: Ctx):
    with ctx.tx() as c:
        c.run("DELETE FROM follows WHERE follower_org_id = $1 AND followed_org_id = $2", ctx.org_id, ctx.path["org_id"])
    return {"following": False}


@route("GET", "/v1/network", min_role="viewer", tags=T, summary="Quem a organização segue, quem a segue, bloqueios e conversas")
def network(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        following = c.query("SELECT o.id::text AS id, org_display(o.id) AS name, o.kind FROM follows f JOIN organizations o ON o.id = f.followed_org_id"
                            " WHERE f.follower_org_id = $1 ORDER BY lower(o.legal_name)", ctx.org_id)
        followers = c.scalar("SELECT count(*) FROM follows WHERE followed_org_id = $1", ctx.org_id)
        blocked = c.query("SELECT o.id::text AS id, org_display(o.id) AS name FROM org_blocks b JOIN organizations o ON o.id = b.blocked_org_id WHERE b.org_id = $1", ctx.org_id)
    return {"following": following, "followers_count": followers, "blocked": blocked}


@route("POST", "/v1/network/block/{org_id}", min_role="admin", tags=T, summary="Bloqueia uma organização (encerra o seguimento e impede mensagens nos dois sentidos)")
def block(ctx: Ctx):
    with ctx.tx() as c:
        o = _org_exists(c, ctx.path["org_id"])
        if o["id"] == ctx.org_id:
            raise ApiError(422, "self", "Operação inválida")
        c.run("INSERT INTO org_blocks(org_id, blocked_org_id) VALUES ($1,$2) ON CONFLICT DO NOTHING", ctx.org_id, o["id"])
        c.run("DELETE FROM follows WHERE (follower_org_id = $1 AND followed_org_id = $2) OR (follower_org_id = $2 AND followed_org_id = $1)", ctx.org_id, o["id"])
        ctx.audit(c, "network.blocked", "organization", o["id"])
    return {"blocked": True}


@route("DELETE", "/v1/network/block/{org_id}", min_role="admin", tags=T)
def unblock(ctx: Ctx):
    with ctx.tx() as c:
        c.run("DELETE FROM org_blocks WHERE org_id = $1 AND blocked_org_id = $2", ctx.org_id, ctx.path["org_id"])
    return {"blocked": False}


# ------------------------------------------------------------------------------------------------ mensagens
@route("GET", "/v1/messages/conversations", min_role="viewer", tags=T)
def conversations(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT cv.id::text AS id, org_display(CASE WHEN cv.org_a = $1 THEN cv.org_b ELSE cv.org_a END) AS with_name,"
                       " (CASE WHEN cv.org_a = $1 THEN cv.org_b ELSE cv.org_a END)::text AS with_org_id,"
                       " (SELECT count(*) FROM messages m WHERE m.conversation_id = cv.id AND m.sender_org_id <> $1 AND m.read_at IS NULL AND m.removed_at IS NULL) AS unread,"
                       " (SELECT max(m.created_at) FROM messages m WHERE m.conversation_id = cv.id) AS last_at"
                       " FROM conversations cv WHERE cv.org_a = $1 OR cv.org_b = $1 ORDER BY last_at DESC NULLS LAST", ctx.org_id)
    return {"items": rows}


@route("GET", "/v1/messages/conversations/{conversation_id}", query=S.Pagination, min_role="viewer", tags=T)
def get_conversation(ctx: Ctx, q: S.Pagination):
    with ctx.tx() as c:
        cv = c.one("SELECT id::text AS id, org_a::text AS org_a, org_b::text AS org_b FROM conversations WHERE id = $1 AND (org_a = $2 OR org_b = $2)", ctx.path["conversation_id"], ctx.org_id)
        if not cv:
            raise not_found("Conversa")
        rows = c.query("SELECT id::text AS id, (sender_org_id = $2) AS mine, org_display(sender_org_id) AS sender, created_at, read_at,"
                       " CASE WHEN removed_at IS NULL THEN body ELSE NULL END AS body, removed_at IS NOT NULL AS removed, removed_reason FROM messages"
                       " WHERE conversation_id = $1 ORDER BY created_at DESC LIMIT $3 OFFSET $4", cv["id"], ctx.org_id, q.limit + 1, q.offset)
        c.run("UPDATE messages SET read_at = now() WHERE conversation_id = $1 AND sender_org_id <> $2 AND read_at IS NULL", cv["id"], ctx.org_id)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/messages/{org_id}", body=S.MessageIn, min_role="member", status=201, rate=("msg_ip", 120, 3600), tags=T,
       summary="Envia mensagem a outra organização (exige relação prévia; limites por hora; bloqueio respeitado)")
def send_message(ctx: Ctx, body: S.MessageIn):
    other = ctx.path["org_id"]
    with ctx.tx() as c:
        o = _org_exists(c, other)
        if o["id"] == ctx.org_id:
            raise ApiError(422, "self", "Operação inválida")
        if c.scalar("SELECT app_blocked_between($1, $2)", ctx.org_id, o["id"]):
            raise ApiError(403, "blocked", "Não é possível enviar mensagem a esta organização")
        if not c.scalar("SELECT app_related($1, $2)", ctx.org_id, o["id"]):
            raise ApiError(403, "no_relationship", "Só é possível conversar após uma relação na plataforma (candidatura, revisão, oferta) ou seguimento mútuo")
        if c.scalar("SELECT count(*) FROM messages WHERE sender_org_id = $1 AND created_at > now() - interval '1 hour'", ctx.org_id) >= MAX_MSG_PER_HOUR:
            raise ApiError(429, "rate_limited", "Limite de mensagens por hora atingido")
        a, b = sorted([ctx.org_id, o["id"]])
        cv = c.one("SELECT id::text AS id FROM conversations WHERE org_a = $1 AND org_b = $2", a, b)
        if not cv:
            if c.scalar("SELECT count(*) FROM conversations WHERE (org_a = $1 OR org_b = $1) AND created_at > now() - interval '1 day'", ctx.org_id) >= MAX_NEW_CONVERSATIONS_PER_DAY:
                raise ApiError(429, "rate_limited", "Limite diário de novas conversas atingido")
            cv = {"id": c.scalar("INSERT INTO conversations(org_a, org_b) VALUES ($1,$2) RETURNING id::text", a, b)}
        mid = c.scalar("INSERT INTO messages(conversation_id, sender_org_id, sender_user_id, body) VALUES ($1,$2,$3,$4) RETURNING id::text",
                       cv["id"], ctx.org_id, ctx.user_id, body.body)
        c.scalar("SELECT app_notify($1, NULL, 'message', 'Nova mensagem', $2, '/mensagens')", o["id"], "Você recebeu uma mensagem. Abra a conversa para ler.")
    return {"id": mid, "conversation_id": cv["id"]}


# ------------------------------------------------------------------------------------------------ necessidades e ofertas
@route("GET", "/v1/projects/{project_id}/needs", min_role="viewer", tags=("professionals",))
def list_needs(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT n.id::text AS id, n.category, n.title, n.description, n.remote_ok, n.language, n.status, n.created_at,"
                       " (SELECT count(*) FROM need_offers o WHERE o.need_id = n.id) AS offers FROM project_needs n WHERE n.project_id = $1 ORDER BY n.created_at DESC", ctx.path["project_id"])
    return {"items": rows}


@route("POST", "/v1/projects/{project_id}/needs", body=S.NeedIn, kinds=("osc",), min_role="member", status=201, tags=("professionals",),
       summary="Publica uma necessidade de profissional (ex.: contador, jurídico, avaliador de impacto) vinculada ao projeto")
def create_need(ctx: Ctx, body: S.NeedIn):
    from ..services.catalog import PROFESSIONAL_CATEGORIES
    if body.category not in PROFESSIONAL_CATEGORIES:
        raise ApiError(422, "unknown_category", "Categoria profissional desconhecida")
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM projects WHERE id = $1 AND org_id = $2", ctx.path["project_id"], ctx.org_id):
            raise not_found("Projeto")
        nid = c.scalar("INSERT INTO project_needs(project_id, org_id, category, title, description, remote_ok, language) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id::text",
                       ctx.path["project_id"], ctx.org_id, body.category, body.title, body.description, body.remote_ok, body.language)
        ctx.audit(c, "need.created", "project_need", nid)
    return {"id": nid}


@route("POST", "/v1/needs/{need_id}/close", kinds=("osc",), min_role="member", tags=("professionals",))
def close_need(ctx: Ctx):
    with ctx.tx() as c:
        if not c.run("UPDATE project_needs SET status = 'cancelled' WHERE id = $1 AND org_id = $2 AND status = 'open'", ctx.path["need_id"], ctx.org_id):
            raise not_found("Necessidade")
    return {"status": "cancelled"}


def _prof_input(c, prof_org: str) -> dict:
    p = c.one("SELECT categories, services, remote, territories, languages, accepting_requests FROM provider_profiles WHERE org_id = $1", prof_org) or {}
    p["credentials"] = c.query("SELECT council, uf, verification_status AS status, valid_until FROM professional_credentials WHERE org_id = $1", prof_org)
    p["completed_reviews"] = c.scalar("SELECT count(*) FROM professional_reviews WHERE professional_org_id = $1 AND status IN ('approved','signed')", prof_org)
    p["open_reviews"] = c.scalar("SELECT count(*) FROM professional_reviews WHERE professional_org_id = $1 AND status IN ('requested','accepted','changes_requested')", prof_org)
    p["open_reviews_limit"] = c.scalar("SELECT (limits->>'open_reviews')::int FROM plans WHERE plan_key = 'provider_basic'") or None
    return p


def _need_input(n: dict) -> dict:
    return {"category": n["category"], "remote_ok": n["remote_ok"], "language": n["language"], "status": n["status"], "territory": n["territory"]}


@route("GET", "/v1/professional/opportunities", kinds=("provider",), query=S.Pagination, min_role="viewer", tags=("professionals",),
       summary="Necessidades abertas de projetos publicados, ordenadas por compatibilidade explicável (plano/voucher não influenciam)")
def opportunities(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        prof = _prof_input(c, ctx.org_id)
        needs = c.query("SELECT n.id::text AS id, n.category, n.title, n.description, n.remote_ok, n.language, n.status, p.territory, p.title AS project_title,"
                        " p.id::text AS project_id, org_display(p.org_id) AS osc_name FROM project_needs n JOIN projects p ON p.id = n.project_id"
                        " WHERE n.status = 'open' ORDER BY n.created_at DESC LIMIT 200")
        mine = {r["need_id"] for r in c.query("SELECT need_id::text AS need_id FROM need_offers WHERE professional_org_id = $1", ctx.org_id)}
    res = []
    for n in needs:
        m = pm.evaluate(pm.ProfessionalInput.build(prof, _need_input(n), _hoje_utc()))
        if m["eligibility"] == "blocked" and any(b["code"] == "category_mismatch" for b in m["blockers"]):
            continue      # fora da área do profissional: não polui a lista
        res.append({**n, "already_offered": n["id"] in mine, "match": m})
    res.sort(key=lambda r: (-(r["match"]["score"] if r["match"]["score"] is not None else -1), r["title"].lower(), r["id"]))
    sl = res[q.offset: q.offset + q.limit + 1]
    return page(sl, q.limit, q.offset)


@route("POST", "/v1/needs/{need_id}/offers", body=S.OfferIn, kinds=("provider",), min_role="member", status=201, tags=("professionals",),
       summary="Profissional oferece ajuda a uma necessidade (a contratação é livre entre as partes, fora da plataforma)")
def make_offer(ctx: Ctx, body: S.OfferIn):
    with ctx.tx() as c:
        n = c.one("SELECT n.id::text AS id, n.org_id::text AS org_id, n.project_id::text AS project_id, n.status, n.title FROM project_needs n WHERE n.id = $1", ctx.path["need_id"])
        if not n or n["status"] != "open":
            raise not_found("Necessidade")
        if c.one("SELECT 1 FROM need_offers WHERE need_id = $1 AND professional_org_id = $2", n["id"], ctx.org_id):
            raise ApiError(409, "already_offered", "Você já enviou uma oferta para esta necessidade")
        oid = c.scalar("INSERT INTO need_offers(need_id, professional_org_id, message) VALUES ($1,$2,$3) RETURNING id::text", n["id"], ctx.org_id, body.message)
        c.scalar("SELECT app_notify($1, NULL, 'professional', 'Nova oferta de profissional', $2, $3)", n["org_id"], n["title"], f"/projetos/{n['project_id']}")
        ctx.audit(c, "need.offer_made", "need_offer", oid)
    return {"id": oid}


@route("GET", "/v1/needs/{need_id}/offers", kinds=("osc",), min_role="viewer", tags=("professionals",),
       summary="Ofertas recebidas, com a compatibilidade explicável de cada profissional")
def list_offers(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        n = c.one("SELECT n.id::text AS id, n.category, n.remote_ok, n.language, n.status, p.territory FROM project_needs n JOIN projects p ON p.id = n.project_id"
                  " WHERE n.id = $1 AND n.org_id = $2", ctx.path["need_id"], ctx.org_id)
        if not n:
            raise not_found("Necessidade")
        offers = c.query("SELECT o.id::text AS id, o.professional_org_id::text AS professional_org_id, org_display(o.professional_org_id) AS name, o.message, o.status, o.created_at"
                         " FROM need_offers o WHERE o.need_id = $1 ORDER BY o.created_at", n["id"])
        for o in offers:
            o["match"] = pm.evaluate(pm.ProfessionalInput.build(_prof_input(c, o["professional_org_id"]), _need_input(n), _hoje_utc()))
    return {"items": offers}


@route("POST", "/v1/offers/{offer_id}/decide", body=S.OfferDecisionIn, kinds=("osc",), min_role="manager", tags=("professionals",))
def decide_offer(ctx: Ctx, body: S.OfferDecisionIn):
    with ctx.tx() as c:
        o = c.one("SELECT o.id::text AS id, o.need_id::text AS need_id, o.professional_org_id::text AS prof, o.status FROM need_offers o JOIN project_needs n ON n.id = o.need_id"
                  " WHERE o.id = $1 AND n.org_id = $2", ctx.path["offer_id"], ctx.org_id)
        if not o or o["status"] != "offered":
            raise not_found("Oferta")
        c.run("UPDATE need_offers SET status = $2, decided_at = now() WHERE id = $1", o["id"], body.decision)
        if body.decision == "accepted":
            c.run("UPDATE project_needs SET status = 'filled' WHERE id = $1", o["need_id"])
        c.scalar("SELECT app_notify($1, NULL, 'professional', 'Oferta analisada', $2, '/profissional')", o["prof"], "Resultado: " + body.decision)
        ctx.audit(c, "need.offer_decided", "need_offer", o["id"], {"decision": body.decision})
    return {"id": o["id"], "status": body.decision}


@route("GET", "/v1/professional/offers", kinds=("provider",), min_role="viewer", tags=("professionals",))
def my_offers(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT o.id::text AS id, o.status, o.created_at, n.title, n.category, n.project_id::text AS project_id FROM need_offers o JOIN project_needs n ON n.id = o.need_id"
                       " WHERE o.professional_org_id = $1 ORDER BY o.created_at DESC LIMIT 100", ctx.org_id)
    return {"items": rows}


@route("GET", "/v1/needs/{need_id}/professionals", kinds=("osc",), min_role="viewer", tags=("professionals",),
       summary="Sugestão de profissionais do diretório para a necessidade (match explicável; posição nunca depende de plano)")
def suggest_professionals(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        n = c.one("SELECT n.id::text AS id, n.category, n.remote_ok, n.language, n.status, p.territory FROM project_needs n JOIN projects p ON p.id = n.project_id"
                  " WHERE n.id = $1 AND n.org_id = $2", ctx.path["need_id"], ctx.org_id)
        if not n:
            raise not_found("Necessidade")
        cands = c.query("SELECT o.id::text AS id, coalesce(o.trade_name, o.legal_name) AS name FROM organizations o JOIN provider_profiles pp ON pp.org_id = o.id"
                        " WHERE o.kind = 'provider' AND o.status = 'active' AND $1 = ANY(pp.categories) LIMIT 100", n["category"])
        res = []
        for cd in cands:
            res.append({**cd, "match": pm.evaluate(pm.ProfessionalInput.build(_prof_input(c, cd["id"]), _need_input(n), _hoje_utc()))})
    res = [r for r in res if r["match"]["eligibility"] != "blocked"]
    res.sort(key=lambda r: (-(r["match"]["score"] if r["match"]["score"] is not None else -1), r["name"].lower(), r["id"]))
    return {"items": res[:20]}


# ------------------------------------------------------------------------------------------------ conquistas
@route("GET", "/v1/badges", min_role="viewer", tags=T, summary="Conquistas organizacionais verificáveis (privadas; sem pontos, ranking ou comparação)")
def my_badges(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        items = badges.compute(c, ctx.org_id, ctx.principal.org_kind)
    return {"items": items, "note": "Conquistas refletem critérios objetivos da plataforma. Não há ranking nem comparação entre organizações."}
