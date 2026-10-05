"""Biblioteca de Soluções — interação (salvar, pedidos, intenção de financiamento, replicação, avaliações, disputas) e administração (verificação).

Privacidade: o autor só vê a identidade do financiador se ela foi tornada pública OU se o financiador fez um pedido direto ao autor (RLS no banco).
Etapas avançadas da intenção só mudam pelo fluxo de pedidos ou por confirmação do autor (funções SECURITY DEFINER no banco)."""
from __future__ import annotations

from ..http import ApiError, Ctx, not_found, page, route
from ..services import solutions as svc
from ..engines.solutions import scoring as SC
from . import schemas as S

T = ("solutions",)
AUTHOR_KINDS = ("osc", "individual", "company", "government", "provider")
DAILY_REQUEST_CAP = 10


def _published(c, sid: str) -> dict:
    s = c.one("SELECT id::text AS id, org_id::text AS org_id, title, visibility, allow_replication, allow_adaptation, confidentiality FROM solutions WHERE id = $1", sid)
    if not s or s["visibility"] != "published":
        raise not_found("Solução")
    return s


def _event(c, ctx: Ctx, sid: str, etype: str) -> None:
    c.run("INSERT INTO solution_events(solution_id, org_id, user_id, event_type) VALUES ($1,$2,$3,$4) ON CONFLICT (solution_id, user_id, event_type, day) WHERE solution_id IS NOT NULL DO NOTHING",
          sid, ctx.org_id, ctx.user_id, etype)


def _notify(c, org_id: str, title: str, body: str, link: str) -> None:
    c.scalar("SELECT app_notify($1, NULL, 'solution', $2, $3, $4)", org_id, title, body, link)


# ------------------------------------------------------------------------------------------------ salvar e eventos
@route("PUT", "/v1/solutions/{solution_id}/save", min_role="viewer", tags=T, summary="Salva a solução na minha lista")
def save(ctx: Ctx):
    with ctx.tx() as c:
        s = _published(c, ctx.path["solution_id"])
        c.run("INSERT INTO solution_saves(user_id, solution_id, org_id) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", ctx.user_id, s["id"], ctx.org_id)
        _event(c, ctx, s["id"], "solution_saved")
    return {"saved": True}


@route("DELETE", "/v1/solutions/{solution_id}/save", min_role="viewer", status=204, tags=T, summary="Remove da minha lista")
def unsave(ctx: Ctx):
    with ctx.tx() as c:
        c.run("DELETE FROM solution_saves WHERE user_id = $1 AND solution_id = $2", ctx.user_id, ctx.path["solution_id"])
    return None


@route("GET", "/v1/solutions/saved", min_role="viewer", query=S.Pagination, tags=T, summary="Minhas soluções salvas")
def saved(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {svc.CARD_COLS} FROM solution_saves v JOIN solutions s ON s.id = v.solution_id WHERE v.user_id = $1 AND s.visibility = 'published'"
                       " ORDER BY v.created_at DESC LIMIT $2 OFFSET $3", ctx.user_id, q.limit + 1, q.offset)
        feats = svc.features(c, [r["id"] for r in rows[:q.limit]])
        items = [svc.public_card(r, svc.scores_for(r, feats[r["id"]])) for r in rows[:q.limit]]
    return {"items": items, "limit": q.limit, "offset": q.offset, "has_more": len(rows) > q.limit, "next_offset": q.offset + q.limit if len(rows) > q.limit else None}


@route("POST", "/v1/solutions/{solution_id}/events", body=S.SolutionEventIn, min_role="viewer", status=204, tags=T, summary="Registra compartilhamento/comparação (deduplicado por dia)")
def event(ctx: Ctx, body: S.SolutionEventIn):
    with ctx.tx() as c:
        s = _published(c, ctx.path["solution_id"])
        if s["org_id"] != ctx.org_id:
            _event(c, ctx, s["id"], body.event_type)
    return None


# ------------------------------------------------------------------------------------------------ pedidos
@route("POST", "/v1/solutions/{solution_id}/requests", body=S.SolutionRequestIn, min_role="member", status=201, rate=("solution_request", 30, 3600), tags=T,
       summary="Pede informação, contato, adaptação, replicação ou orçamento ao autor (com limites anti-spam)")
def create_request(ctx: Ctx, body: S.SolutionRequestIn):
    from ..db.pq import Json
    with ctx.tx() as c:
        s = _published(c, ctx.path["solution_id"])
        if s["org_id"] == ctx.org_id:
            raise ApiError(409, "own_solution", "Não é possível enviar pedidos à própria solução")
        if body.kind in ("adaptation", "replication") and s["confidentiality"] == "restricted_use":
            raise ApiError(403, "restricted_use", "Uso restrito: o autor permite consulta, mas não replicação nem adaptação por terceiros.")
        if body.kind == "adaptation" and not s["allow_adaptation"]:
            raise ApiError(403, "adaptation_not_allowed", "O autor não autorizou adaptação desta solução.")
        if body.kind == "replication" and not s["allow_replication"]:
            raise ApiError(403, "replication_not_allowed", "O autor não autorizou replicação desta solução.")
        if c.scalar("SELECT count(*) FROM solution_requests WHERE requester_org_id = $1 AND created_at > now() - interval '24 hours'", ctx.org_id) >= DAILY_REQUEST_CAP:
            raise ApiError(429, "request_cap", f"Limite diário de {DAILY_REQUEST_CAP} pedidos da organização atingido.")
        if c.one("SELECT 1 FROM solution_requests WHERE solution_id = $1 AND requester_org_id = $2 AND kind = $3 AND status IN ('new','seen')", s["id"], ctx.org_id, body.kind):
            raise ApiError(409, "request_open", "Já existe um pedido deste tipo aguardando resposta do autor.")
        rid = c.scalar("INSERT INTO solution_requests(solution_id, requester_org_id, requester_user_id, kind, message, params) VALUES ($1,$2,$3,$4,$5,$6::jsonb) RETURNING id::text",
                       s["id"], ctx.org_id, ctx.user_id, body.kind, body.message, Json(body.params))
        stage = None
        if body.kind in ("info", "contact", "budget"):
            stage = c.scalar("SELECT solution_advance_intent($1, 'requested_info')", s["id"])
        elif body.kind == "adaptation":
            stage = c.scalar("SELECT solution_advance_intent($1, 'requested_adaptation')", s["id"])
        _event(c, ctx, s["id"], {"adaptation": "solution_adaptation_requested", "replication": "solution_replication_requested"}.get(body.kind, "solution_contact_requested"))
        if stage:
            _event(c, ctx, s["id"], "funding_intent_created")
        _notify(c, s["org_id"], "Novo pedido sobre sua solução", f"“{s['title'][:80]}” recebeu um pedido ({body.kind}).", "/solucoes/pedidos")
        ctx.audit(c, "solution.request_created", "solution", s["id"], {"request_id": rid, "kind": body.kind})
    return {"id": rid, "status": "new", "intent_stage": stage}


@route("GET", "/v1/solution-requests/received", min_role="viewer", query=S.Pagination, tags=T, summary="Pedidos recebidos pelas minhas soluções")
def received(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT r.id::text AS id, r.solution_id::text AS solution_id, s.title AS solution_title, r.kind, r.message, r.status, r.response, r.created_at, r.responded_at,"
                       " o.legal_name AS requester_name, o.kind AS requester_kind, o.uf AS requester_uf FROM solution_requests r JOIN solutions s ON s.id = r.solution_id"
                       " JOIN organizations o ON o.id = r.requester_org_id WHERE s.org_id = $1 ORDER BY r.created_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/solution-requests/sent", min_role="viewer", query=S.Pagination, tags=T, summary="Pedidos enviados pela minha organização")
def sent(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT r.id::text AS id, r.solution_id::text AS solution_id, s.title AS solution_title, r.kind, r.message, r.status, r.response, r.created_at, r.responded_at"
                       " FROM solution_requests r JOIN solutions s ON s.id = r.solution_id WHERE r.requester_org_id = $1 ORDER BY r.created_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("POST", "/v1/solution-requests/{request_id}/respond", body=S.SolutionRequestRespondIn, kinds=AUTHOR_KINDS, min_role="member", tags=T, summary="O autor responde a um pedido")
def respond(ctx: Ctx, body: S.SolutionRequestRespondIn):
    with ctx.tx() as c:
        r = c.one("SELECT r.id::text AS id, r.status, r.requester_org_id::text AS requester_org_id, s.title, s.org_id::text AS owner FROM solution_requests r JOIN solutions s ON s.id = r.solution_id"
                  " WHERE r.id = $1 FOR UPDATE OF r", ctx.path["request_id"])
        if not r or r["owner"] != ctx.org_id:
            raise not_found("Pedido")
        if r["status"] in ("closed",):
            raise ApiError(409, "closed", "Pedido já encerrado")
        if body.status in ("accepted", "declined") and not body.response:
            raise ApiError(422, "response_required", "Informe uma resposta ao aceitar ou recusar")
        c.run("UPDATE solution_requests SET status = $2, response = $3, responded_at = now() WHERE id = $1", r["id"], body.status, body.response)
        _notify(c, r["requester_org_id"], "Resposta do autor", f"O autor respondeu ao seu pedido sobre “{r['title'][:80]}”.", "/solucoes/pedidos")
        ctx.audit(c, "solution.request_responded", "solution_request", r["id"], {"status": body.status})
    return {"id": r["id"], "status": body.status}


@route("POST", "/v1/solution-requests/{request_id}/close", min_role="member", tags=T, summary="O solicitante encerra o próprio pedido")
def close_request(ctx: Ctx):
    with ctx.tx() as c:
        r = c.one("SELECT id::text AS id FROM solution_requests WHERE id = $1 AND requester_org_id = $2", ctx.path["request_id"], ctx.org_id)
        if not r:
            raise not_found("Pedido")
        c.run("UPDATE solution_requests SET status = 'closed' WHERE id = $1", r["id"])
    return {"id": r["id"], "status": "closed"}


# ------------------------------------------------------------------------------------------------ intenção de financiamento
@route("PUT", "/v1/solutions/{solution_id}/intent", body=S.SolutionIntentIn, min_role="member", tags=T,
       summary="Declara interesse (descoberta → interessado → em análise). A identidade é privada por padrão")
def put_intent(ctx: Ctx, body: S.SolutionIntentIn):
    with ctx.tx() as c:
        s = _published(c, ctx.path["solution_id"])
        if s["org_id"] == ctx.org_id:
            raise ApiError(409, "own_solution", "Não é possível declarar interesse na própria solução")
        cur = c.one("SELECT id::text AS id, stage FROM solution_intents WHERE solution_id = $1 AND org_id = $2", s["id"], ctx.org_id)
        if cur and cur["stage"] not in ("discovery", "interested", "reviewing"):
            raise ApiError(409, "stage_locked", "Esta etapa já avançou pelo fluxo de pedidos/confirmação do autor e não pode ser alterada aqui.")
        if cur:
            c.run("UPDATE solution_intents SET stage = $2, public_identity = $3, updated_at = now() WHERE id = $1", cur["id"], body.stage, body.public_identity)
            iid, prev = cur["id"], cur["stage"]
        else:
            iid, prev = c.scalar("INSERT INTO solution_intents(solution_id, org_id, user_id, stage, public_identity) VALUES ($1,$2,$3,$4,$5) RETURNING id::text",
                                 s["id"], ctx.org_id, ctx.user_id, body.stage, body.public_identity), None
        if prev != body.stage:
            c.run("INSERT INTO solution_intent_events(intent_id, from_stage, to_stage, actor_org_id) VALUES ($1,$2,$3,$4)", iid, prev, body.stage, ctx.org_id)
        if body.stage != "discovery":
            _event(c, ctx, s["id"], "funding_intent_created")
    return {"id": iid, "stage": body.stage, "public_identity": body.public_identity}


@route("DELETE", "/v1/solutions/{solution_id}/intent", min_role="member", status=204, tags=T, summary="Retira a intenção declarada (apenas das etapas iniciais)")
def delete_intent(ctx: Ctx):
    with ctx.tx() as c:
        cur = c.one("SELECT id::text AS id, stage FROM solution_intents WHERE solution_id = $1 AND org_id = $2", ctx.path["solution_id"], ctx.org_id)
        if cur:
            if cur["stage"] not in ("discovery", "interested", "reviewing"):
                raise ApiError(409, "stage_locked", "Etapa já avançada: encerre o pedido ou fale com o autor.")
            c.run("UPDATE solution_intents SET stage = 'discovery', public_identity = false WHERE id = $1", cur["id"])
    return None


@route("GET", "/v1/solutions/{solution_id}/intents", kinds=AUTHOR_KINDS, min_role="viewer", tags=T,
       summary="Interessados na minha solução: contagens agregadas + identidades somente das que são públicas ou que fizeram pedido direto")
def list_intents(ctx: Ctx):
    sid = ctx.path["solution_id"]
    with ctx.tx(readonly=True) as c:
        if not c.one("SELECT 1 FROM solutions WHERE id = $1 AND org_id = $2", sid, ctx.org_id):
            raise not_found("Solução")
        stats = c.scalar("SELECT solution_public_stats($1)", sid)
        visible = c.query("SELECT i.id::text AS id, i.stage, i.confirmed_by_author, i.public_identity, o.legal_name AS org_name, o.kind AS org_kind, o.uf AS org_uf,"
                          " EXISTS (SELECT 1 FROM solution_requests r WHERE r.solution_id = i.solution_id AND r.requester_org_id = i.org_id AND r.status = 'accepted') AS request_accepted"
                          " FROM solution_intents i JOIN organizations o ON o.id = i.org_id WHERE i.solution_id = $1 ORDER BY i.updated_at DESC", sid)
    return {"stats": stats, "identified": visible, "note": "Organizações que não tornaram a identidade pública nem fizeram pedido direto aparecem somente nas contagens."}


@route("POST", "/v1/solution-intents/{intent_id}/stage", body=S.SolutionStageIn, kinds=AUTHOR_KINDS, min_role="admin", tags=T,
       summary="O autor confirma uma etapa avançada (negociando … concluído); exige pedido aceito do financiador")
def author_stage(ctx: Ctx, body: S.SolutionStageIn):
    stage = body.to
    with ctx.tx() as c:
        try:
            c.scalar("SELECT solution_author_set_intent($1, $2)", ctx.path["intent_id"], stage)
        except Exception as exc:  # noqa: BLE001 — mensagens do banco são em português e seguras
            msg = str(exc)
            if "42501" in msg or "intenção" in msg or "autor" in msg or "etapa" in msg:
                raise ApiError(403, "intent_stage_denied", msg.split("ERROR:")[-1].strip()[:200]) from exc
            raise
        sid = c.scalar("SELECT solution_id::text FROM solution_intents WHERE id = $1", ctx.path["intent_id"])
        if stage in ("commitment_started", "funded"):
            c.run("INSERT INTO solution_events(solution_id, org_id, user_id, event_type) VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING", sid, ctx.org_id, ctx.user_id,
                  "funding_started" if stage == "commitment_started" else "funding_completed")
        ctx.audit(c, "solution.intent_stage", "solution_intent", ctx.path["intent_id"], {"to": stage})
    return {"id": ctx.path["intent_id"], "stage": stage, "confirmed_by_author": True}


@route("GET", "/v1/solution-intents/mine", min_role="viewer", query=S.Pagination, tags=T, summary="Meu funil: soluções em que declarei interesse")
def my_intents(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT i.id::text AS id, i.solution_id::text AS solution_id, s.title, i.stage, i.public_identity, i.confirmed_by_author, i.updated_at FROM solution_intents i"
                       " JOIN solutions s ON s.id = i.solution_id WHERE i.org_id = $1 ORDER BY i.updated_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


# ------------------------------------------------------------------------------------------------ replicação (marketplace)
@route("GET", "/v1/replications/marketplace", min_role="viewer", query=S.Pagination, tags=T,
       summary="Marketplace de replicação: soluções que o autor autorizou replicar, com contagem de replicações")
def marketplace(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT {svc.CARD_COLS}, (SELECT count(*) FROM solution_replications x WHERE x.solution_id = s.id AND x.status = 'completed' AND x.author_confirmed) AS replications_confirmed"
                       " FROM solutions s WHERE s.visibility = 'published' AND s.allow_replication AND s.confidentiality NOT IN ('restricted_use','confidential') AND s.kind <> 'idea' AND s.stage IN ('running','completed')"
                       " ORDER BY s.published_at DESC LIMIT $1 OFFSET $2", q.limit + 1, q.offset)
        feats = svc.features(c, [r["id"] for r in rows[:q.limit]])
        items = []
        for r in rows[:q.limit]:
            sc = svc.scores_for(r, feats[r["id"]])
            items.append(svc.public_card(r, sc) | {"replications_confirmed": r["replications_confirmed"], "replicability_detail": sc["replicability"]})
    return {"items": items, "limit": q.limit, "offset": q.offset, "has_more": len(rows) > q.limit, "next_offset": q.offset + q.limit if len(rows) > q.limit else None,
            "note": "Replicado = replicação concluída E confirmada pelo autor."}


@route("POST", "/v1/solutions/{solution_id}/replications", body=S.SolutionReplicationIn, min_role="member", status=201, tags=T, summary="Manifesta interesse em replicar a solução em um território")
def start_replication(ctx: Ctx, body: S.SolutionReplicationIn):
    with ctx.tx() as c:
        s = _published(c, ctx.path["solution_id"])
        if s["org_id"] == ctx.org_id:
            raise ApiError(409, "own_solution", "Não é possível replicar a própria solução")
        if s["confidentiality"] == "restricted_use":
            raise ApiError(403, "restricted_use", "Uso restrito: o autor permite consulta, mas não replicação nem adaptação por terceiros.")
        if not s["allow_replication"]:
            raise ApiError(403, "replication_not_allowed", "O autor não autorizou replicação desta solução.")
        if c.one("SELECT 1 FROM solution_replications WHERE solution_id = $1 AND replicator_org_id = $2 AND target_uf = $3 AND target_city = $4", s["id"], ctx.org_id, body.target_uf, body.target_city):
            raise ApiError(409, "replication_exists", "Já há uma replicação sua para este território.")
        rid = c.scalar("INSERT INTO solution_replications(solution_id, replicator_org_id, target_uf, target_city, public_identity) VALUES ($1,$2,$3,$4,$5) RETURNING id::text",
                       s["id"], ctx.org_id, body.target_uf, body.target_city, body.public_identity)
        _event(c, ctx, s["id"], "solution_replication_requested")
        _notify(c, s["org_id"], "Interesse em replicar", f"Há interesse em replicar “{s['title'][:80]}”.", "/solucoes/replicacoes")
    return {"id": rid, "status": "interested"}


@route("PATCH", "/v1/solution-replications/{replication_id}", body=S.SolutionReplicationPatch, min_role="member", tags=T, summary="O replicador atualiza o andamento da replicação")
def patch_replication(ctx: Ctx, body: S.SolutionReplicationPatch):
    d = body.model_dump(exclude_unset=True)
    if not d:
        raise ApiError(422, "empty_patch", "Nenhum campo informado")
    with ctx.tx() as c:
        r = c.one("SELECT id::text AS id, status FROM solution_replications WHERE id = $1 AND replicator_org_id = $2 FOR UPDATE", ctx.path["replication_id"], ctx.org_id)
        if not r:
            raise not_found("Replicação")
        if d.get("status") == "completed" and r["status"] != "started":
            raise ApiError(409, "not_started", "Só é possível concluir uma replicação iniciada")
        sets, args = [], []
        for k, v in d.items():
            args.append(v)
            sets.append(f"{k} = ${len(args)}")
        if d.get("status") == "started":
            sets.append("started_at = now()")
        if d.get("status") == "completed":
            sets.append("completed_at = now()")
        args.append(r["id"])
        c.run(f"UPDATE solution_replications SET {', '.join(sets)} WHERE id = ${len(args)}", *args)
    return {"id": r["id"], **d}


@route("POST", "/v1/solution-replications/{replication_id}/confirm", kinds=AUTHOR_KINDS, min_role="admin", tags=T, summary="O autor confirma que a replicação aconteceu")
def confirm_replication(ctx: Ctx):
    with ctx.tx() as c:
        r = c.one("SELECT x.id::text AS id, x.status, x.solution_id::text AS sid, x.replicator_org_id::text AS rorg FROM solution_replications x JOIN solutions s ON s.id = x.solution_id"
                  " WHERE x.id = $1 AND s.org_id = $2 FOR UPDATE OF x", ctx.path["replication_id"], ctx.org_id)
        if not r:
            raise not_found("Replicação")
        if r["status"] not in ("started", "completed"):
            raise ApiError(409, "not_started", "O autor só confirma replicações iniciadas ou concluídas")
        c.run("UPDATE solution_replications SET author_confirmed = true WHERE id = $1", r["id"])
        c.run("INSERT INTO solution_events(solution_id, org_id, user_id, event_type) VALUES ($1,$2,$3,'solution_replicated') ON CONFLICT DO NOTHING", r["sid"], ctx.org_id, ctx.user_id)
        _notify(c, r["rorg"], "Replicação confirmada", "O autor confirmou a sua replicação.", "/solucoes/replicacoes")
        ctx.audit(c, "solution.replication_confirmed", "solution_replication", r["id"])
    return {"id": r["id"], "author_confirmed": True}


@route("GET", "/v1/solution-replications/mine", min_role="viewer", query=S.Pagination, tags=T, summary="Replicações da minha organização (como replicadora) e das minhas soluções (como autora)")
def my_replications(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT x.id::text AS id, x.solution_id::text AS solution_id, s.title, x.target_uf, x.target_city, x.status, x.author_confirmed, x.created_at,"
                       " (x.replicator_org_id = $1) AS as_replicator, CASE WHEN x.replicator_org_id = $1 OR x.public_identity THEN o.legal_name END AS replicator_name"
                       " FROM solution_replications x JOIN solutions s ON s.id = x.solution_id JOIN organizations o ON o.id = x.replicator_org_id"
                       " WHERE x.replicator_org_id = $1 OR s.org_id = $1 ORDER BY x.created_at DESC LIMIT $2 OFFSET $3", ctx.org_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


# ------------------------------------------------------------------------------------------------ avaliações e disputas
@route("POST", "/v1/solutions/{solution_id}/reviews", body=S.SolutionReviewIn, min_role="member", status=201, tags=T,
       summary="Avalia a solução (só quem teve pedido aceito ou replicação confirmada; não entra no ranking)")
def review(ctx: Ctx, body: S.SolutionReviewIn):
    with ctx.tx() as c:
        s = _published(c, ctx.path["solution_id"])
        if not c.scalar("SELECT app_solution_reviewable($1)", s["id"]):
            raise ApiError(403, "not_reviewable", "Só é possível avaliar após um pedido aceito pelo autor ou uma replicação confirmada.")
        c.run("INSERT INTO solution_reviews(solution_id, org_id, user_id, rating, body) VALUES ($1,$2,$3,$4,$5) ON CONFLICT (solution_id, org_id) DO UPDATE SET rating = EXCLUDED.rating, body = EXCLUDED.body",
              s["id"], ctx.org_id, ctx.user_id, body.rating, body.body)
    return {"saved": True, "affects_ranking": False}


@route("POST", "/v1/solutions/{solution_id}/disputes", body=S.SolutionDisputeIn, min_role="member", status=201, rate=("solution_dispute", 10, 3600), tags=T,
       summary="Contesta a autoria ou o conteúdo (marca a solução como 'em disputa' até decisão humana)")
def dispute(ctx: Ctx, body: S.SolutionDisputeIn):
    with ctx.tx() as c:
        s = _published(c, ctx.path["solution_id"])
        if s["org_id"] == ctx.org_id:
            raise ApiError(409, "own_solution", "Use a edição para corrigir a própria solução")
        if c.one("SELECT 1 FROM solution_disputes WHERE solution_id = $1 AND claimant_org_id = $2 AND status = 'open'", s["id"], ctx.org_id):
            raise ApiError(409, "dispute_open", "Já há uma contestação sua em análise")
        did = c.scalar("INSERT INTO solution_disputes(solution_id, claimant_org_id, claimant_user_id, claim, supporting_note) VALUES ($1,$2,$3,$4,$5) RETURNING id::text",
                       s["id"], ctx.org_id, ctx.user_id, body.claim, body.supporting_note)
        _notify(c, s["org_id"], "Contestação recebida", f"A solução “{s['title'][:80]}” recebeu uma contestação; a administração fará a análise.", f"/solucoes/{s['id']}")
    return {"id": did, "status": "open"}


# ------------------------------------------------------------------------------------------------ administração
def A(method, path, **kw):
    return route(method, path, auth="admin", tags=("admin", "solutions"), **kw)


_ORDER = ["unverified", "self_declared", "in_review", "documented", "evidenced", "verified"]


@A("GET", "/v1/admin/solutions/queue", summary="Fila de verificação: solicitações, evidências a revisar, contestações abertas")
def queue(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"review_requested": c.query("SELECT id::text AS id, title, trust_level, review_requested_at, org_id::text AS org_id FROM solutions WHERE review_requested_at IS NOT NULL"
                                            " AND trust_level IN ('self_declared','in_review') AND visibility = 'published' ORDER BY review_requested_at LIMIT 100"),
                "evidence_pending": c.query("SELECT e.id::text AS id, e.solution_id::text AS solution_id, s.title, e.kind, e.title AS evidence_title, e.url, e.created_at FROM solution_evidence e"
                                            " JOIN solutions s ON s.id = e.solution_id WHERE e.status = 'submitted' ORDER BY e.created_at LIMIT 100"),
                "disputes_open": c.query("SELECT d.id::text AS id, d.solution_id::text AS solution_id, s.title, d.claim, d.created_at FROM solution_disputes d JOIN solutions s ON s.id = d.solution_id"
                                         " WHERE d.status = 'open' ORDER BY d.created_at LIMIT 100"),
                "results_reported": c.query("SELECT r.id::text AS id, r.solution_id::text AS solution_id, s.title, r.indicator, r.value::float AS value, r.evidence_id::text AS evidence_id FROM solution_results r"
                                            " JOIN solutions s ON s.id = r.solution_id WHERE r.status = 'reported' AND r.evidence_id IS NOT NULL ORDER BY r.created_at LIMIT 100")}


@A("POST", "/v1/admin/solution-evidence/{evidence_id}/review", body=S.SolutionEvidenceReviewIn, summary="Aceita ou rejeita uma evidência (registra revisor e nota)")
def review_evidence(ctx: Ctx, body: S.SolutionEvidenceReviewIn):
    with ctx.tx() as c:
        e = c.one("SELECT id::text AS id, solution_id::text AS sid FROM solution_evidence WHERE id = $1", ctx.path["evidence_id"])
        if not e:
            raise not_found("Evidência")
        c.run("UPDATE solution_evidence SET status = $2, reviewed_by = $3, reviewed_at = now(), review_note = $4 WHERE id = $1", e["id"], body.status, ctx.user_id, body.note)
        ctx.audit(c, "solution.evidence_reviewed", "solution", e["sid"], {"evidence_id": e["id"], "status": body.status})
    return {"id": e["id"], "status": body.status}


@A("POST", "/v1/admin/solution-results/{result_id}/validate", summary="Valida um resultado (exige evidência aceita vinculada)")
def validate_result(ctx: Ctx):
    with ctx.tx() as c:
        r = c.one("SELECT r.id::text AS id, r.solution_id::text AS sid, e.status AS ev_status FROM solution_results r LEFT JOIN solution_evidence e ON e.id = r.evidence_id WHERE r.id = $1", ctx.path["result_id"])
        if not r:
            raise not_found("Resultado")
        if r["ev_status"] != "accepted":
            raise ApiError(409, "evidence_not_accepted", "O resultado só pode ser validado com uma evidência vinculada e já aceita.")
        c.run("UPDATE solution_results SET status = 'validated', validated_by = $2 WHERE id = $1", r["id"], ctx.user_id)
        ctx.audit(c, "solution.result_validated", "solution", r["sid"], {"result_id": r["id"]})
    return {"id": r["id"], "status": "validated"}


@A("POST", "/v1/admin/solutions/{solution_id}/verify", body=S.SolutionVerifyIn, summary="Define o nível de confiança. Níveis altos exigem evidências aceitas (regras no servidor)")
def verify(ctx: Ctx, body: S.SolutionVerifyIn):
    with ctx.tx() as c:
        s = c.one("SELECT id::text AS id, stage, kind, trust_level FROM solutions WHERE id = $1", ctx.path["solution_id"])
        if not s:
            raise not_found("Solução")
        f = svc.features(c, [s["id"]])[s["id"]]
        lvl = body.trust_level
        need = []
        if lvl in ("documented", "evidenced", "verified") and f["accepted_items"] < 1:
            need.append("ao menos 1 evidência aceita")
        if lvl in ("evidenced", "verified") and (f["accepted_items"] < 2 or f["kinds_accepted"] < 2):
            need.append("ao menos 2 evidências aceitas de 2 tipos diferentes")
        if lvl == "verified":
            if f["validated_results"] < 1:
                need.append("ao menos 1 resultado validado")
            if s["stage"] not in ("running", "completed") or s["kind"] == "idea":
                need.append("solução executada (em execução ou realizada) — ideia não é verificada como case")
        if lvl in ("evidenced", "verified") and s["kind"] == "idea":
            need.append("ideias não podem ser 'evidenciadas' ou 'verificadas' como cases")
        if need:
            raise ApiError(422, "verification_requirements", "Requisitos para este nível não atendidos", {"missing": need})
        c.run("UPDATE solutions SET trust_level = $2, verified_by = $3, verified_at = now(), verification_note = $4, review_requested_at = NULL WHERE id = $1", s["id"], lvl, ctx.user_id, body.note)
        ctx.audit(c, "solution.verified", "solution", s["id"], {"from": s["trust_level"], "to": lvl})
    return {"id": s["id"], "trust_level": lvl, "label": SC.TRUST_LABEL[lvl]}


@A("POST", "/v1/admin/solutions/{solution_id}/remove", body=S.SolutionRemoveIn, summary="Remove a solução da biblioteca (irreversível pelo autor)")
def remove(ctx: Ctx, body: S.SolutionRemoveIn):
    with ctx.tx() as c:
        if not c.run("UPDATE solutions SET visibility = 'removed' WHERE id = $1", ctx.path["solution_id"]):
            raise not_found("Solução")
        ctx.audit(c, "solution.removed", "solution", ctx.path["solution_id"], {"reason": body.reason})
    return {"id": ctx.path["solution_id"], "visibility": "removed"}


@A("POST", "/v1/admin/solution-disputes/{dispute_id}/decide", body=S.SolutionDisputeDecideIn, summary="Decide uma contestação (humano; registra decisor e nota)")
def decide_dispute(ctx: Ctx, body: S.SolutionDisputeDecideIn):
    with ctx.tx() as c:
        d = c.one("SELECT id::text AS id, solution_id::text AS sid, status FROM solution_disputes WHERE id = $1 FOR UPDATE", ctx.path["dispute_id"])
        if not d:
            raise not_found("Contestação")
        if d["status"] != "open":
            raise ApiError(409, "already_decided", "Contestação já decidida")
        c.run("UPDATE solution_disputes SET status = $2, decided_by = $3, decision_note = $4, decided_at = now() WHERE id = $1", d["id"], body.status, ctx.user_id, body.note)
        ctx.audit(c, "solution.dispute_decided", "solution", d["sid"], {"dispute_id": d["id"], "status": body.status})
    return {"id": d["id"], "status": body.status}
