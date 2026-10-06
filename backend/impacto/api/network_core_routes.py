"""Rotas da rede: relação unificada, proposta e conversa com contexto.

Três coisas que as rotas daqui NÃO fazem, de propósito:

* **Não decidem visibilidade.** Quem pode ler o quê é a RLS mais `visibility` da própria relação. Uma rota que
  "esqueça" um filtro não vaza, porque o banco recusa a linha antes de a rota a ver.
* **Não carimbam tempo nem autoria de decisão.** `sent_at`, `viewed_at`, `decided_at`, `decided_by` e `version` são
  derivados por gatilho e protegidos por `guard_columns`. A rota diz "aceita"; o banco diz quando e por quem.
* **Não notificam à mão.** Todo aviso sai dos motores, por `network.notify`, com chave de idempotência. Rota que
  notifica por conta própria é rota que avisa duas vezes no reprocessamento.
"""
from __future__ import annotations

from ..http import Ctx, page, route
from ..network import messaging as MSG
from ..network import proposals as PR
from ..network import relationships as REL
from . import network_schemas as N

T = ("rede",)
TP = ("propostas",)
TC = ("conversas",)


# ================================================================================================ relação
@route("GET", "/v1/network/relationship-kinds", auth="user", tags=T,
       summary="Tipos de relação, com alvos aceitos e teto de visibilidade de cada um")
def relationship_kinds(ctx: Ctx):
    return {
        "items": [{"kind": k, "label": REL.LABEL.get(k, k), "targets": list(REL.TARGETS[k]),
                   "max_visibility": REL.MAX_VISIBILITY.get(k, "public"),
                   "requires_consent": k in REL.CONSENTED,
                   "engine_only": k in REL.ENGINE_ONLY} for k in REL.KINDS],
        "visibility_levels": list(REL.VISIBILITY),
        "statuses": list(REL.STATUSES),
        "transitions": {k: list(v) for k, v in REL.TRANSITIONS.items()},
        "note": "A existência de uma relação não implica que ela seja visível: visibility decide. Bloqueio, "
                "favorito e acompanhamento são sempre privados.",
    }


@route("POST", "/v1/network/relationships", body=N.RelationshipIn, min_role="member", status=201, tags=T,
       summary="Cria uma relação (idempotente por tipo, origem, destino e contexto)")
def create_relationship(ctx: Ctx, body: N.RelationshipIn):
    with ctx.tx() as c:
        out = REL.create(c, kind=body.kind, org_id=ctx.org_id, actor=ctx.user_id, target_type=body.target_type,
                         target_id=body.target_id, context_project_id=body.context_project_id, role=body.role,
                         visibility=body.visibility, note=body.note,
                         evidence_document_id=body.evidence_document_id)
        if out.get("created"):
            ctx.audit(c, "relationship.created", "relationship", out["id"],
                      {"kind": body.kind, "target_type": body.target_type, "visibility": out["visibility"]})
    return out


@route("GET", "/v1/network/relationships", query=N.RelationshipQ, min_role="viewer", tags=T)
def list_relationships(ctx: Ctx, q: N.RelationshipQ):
    with ctx.tx(readonly=True) as c:
        rows = REL.mine(c, org_id=ctx.org_id, kind=q.kind, status=q.status, direction=q.direction,
                        limit=q.limit + 1, offset=q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/network/relationships/counts", min_role="viewer", tags=T)
def relationship_counts(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return REL.counts(c, ctx.org_id)


@route("GET", "/v1/network/graph", query=N.GraphQ, min_role="viewer", tags=T,
       summary="Vizinhança da organização no grafo (profundidade 1 ou 2, sem bloqueios)")
def network_graph(ctx: Ctx, q: N.GraphQ):
    with ctx.tx(readonly=True) as c:
        return REL.graph(c, org_id=ctx.org_id, depth=q.depth, limit=q.limit)


@route("POST", "/v1/network/relationships/{rel_id}/transition", body=N.RelationshipTransitionIn,
       min_role="member", tags=T, summary="Aceita, recusa, pausa, encerra ou revoga — conforme o lado")
def transition_relationship(ctx: Ctx, body: N.RelationshipTransitionIn):
    rid = ctx.path["rel_id"]
    with ctx.tx() as c:
        out = REL.transition(c, rel_id=rid, to=body.to, org_id=ctx.org_id, user_id=ctx.user_id,
                             actor=ctx.user_id, reason=body.reason)
        if not out.get("unchanged"):
            ctx.audit(c, "relationship.transition", "relationship", rid,
                      {"to": body.to, "reason": body.reason})
    return out


@route("PUT", "/v1/network/relationships/{rel_id}/visibility", body=N.VisibilityIn, min_role="manager", tags=T,
       summary="Altera a visibilidade (limitada ao teto do tipo)")
def set_relationship_visibility(ctx: Ctx, body: N.VisibilityIn):
    rid = ctx.path["rel_id"]
    with ctx.tx() as c:
        out = REL.set_visibility(c, rel_id=rid, visibility=body.visibility, org_id=ctx.org_id, actor=ctx.user_id)
        ctx.audit(c, "relationship.visibility", "relationship", rid, out)
    return out


@route("GET", "/v1/public/relationships/{subject_type}/{subject_id}", auth="none", tags=T,
       summary="Relações PÚBLICAS de um sujeito (filtradas por visibilidade, nunca por existência)")
def public_relationships(ctx: Ctx):
    st, sid = ctx.path["subject_type"], ctx.path["subject_id"]
    authed = ctx.principal is not None
    viewer = ctx.principal.org_id if ctx.principal else None
    with ctx.system_tx() as c:
        rows = REL.visible_to(c, subject_type=st, subject_id=sid, viewer_org_id=viewer, authenticated=authed,
                              limit=50)
    return {"items": rows, "count": len(rows),
            "note": "Somente relações de visibilidade pública"
                    + (" ou de rede (você está autenticado)." if authed else ".")}


# ================================================================================================ proposta
@route("GET", "/v1/proposals/graph", auth="user", tags=TP, summary="Máquina de estados da proposta, como está no banco")
def proposal_graph(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = PR.graph(c)
    return {"items": rows, "kinds": [{"kind": k, "label": PR.LABEL[k]} for k in PR.KINDS],
            "statuses": [{"status": s, "label": PR.ST_LABEL[s]} for s in PR.STATUSES],
            "note": "Proposta aceita cria relação e intenção. Não é contrato, compromisso financeiro nem pagamento."}


@route("POST", "/v1/proposals", body=N.ProposalIn, min_role="manager", status=201, tags=TP,
       summary="Cria a proposta em rascunho (exige contexto: projeto, necessidade, edital ou solução)")
def create_proposal(ctx: Ctx, body: N.ProposalIn):
    with ctx.tx() as c:
        out = PR.create(c, kind=body.kind, sender_org_id=ctx.org_id, receiver_org_id=body.receiver_org_id,
                        actor=ctx.user_id, title=body.title, purpose=body.purpose, terms=body.terms,
                        amount_cents=body.amount_cents, currency=body.currency, support_mode=body.support_mode,
                        compensation=body.compensation, project_id=body.project_id, need_id=body.need_id,
                        call_id=body.call_id, solution_id=body.solution_id, expires_at=body.expires_at)
        ctx.audit(c, "proposal.created", "proposal", out["id"],
                  {"kind": body.kind, "receiver": body.receiver_org_id, "amount_cents": body.amount_cents})
    return out


@route("GET", "/v1/proposals", query=N.ProposalQ, min_role="viewer", tags=TP,
       summary="Caixa única de propostas (recebidas, enviadas ou todas)")
def list_proposals(ctx: Ctx, q: N.ProposalQ):
    with ctx.tx(readonly=True) as c:
        rows = PR.inbox(c, org_id=ctx.org_id, box=q.box, status=q.status, kind=q.kind, limit=q.limit + 1,
                        offset=q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/proposals/counts", min_role="viewer", tags=TP)
def proposal_counts(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return PR.counts(c, ctx.org_id)


@route("GET", "/v1/proposals/{proposal_id}", min_role="viewer", tags=TP,
       summary="Proposta com histórico, anexos e as ações disponíveis para o seu lado")
def get_proposal(ctx: Ctx):
    pid = ctx.path["proposal_id"]
    # Abrir marca como vista: é a prova de que chegou. Exige papel que decide, para que um acesso de leitura
    # não consuma o estado "ainda não vista" de quem apenas conferiu.
    mark = bool(ctx.principal and ctx.principal.has_role("manager"))
    with ctx.tx() as c:
        return PR.get(c, proposal_id=pid, org_id=ctx.org_id, mark_viewed=mark, actor=ctx.user_id)


@route("PATCH", "/v1/proposals/{proposal_id}", body=N.ProposalPatch, min_role="manager", tags=TP,
       summary="Edita a proposta (só em rascunho ou após ajuste solicitado)")
def patch_proposal(ctx: Ctx, body: N.ProposalPatch):
    pid = ctx.path["proposal_id"]
    with ctx.tx() as c:
        out = PR.update_draft(c, proposal_id=pid, org_id=ctx.org_id,
                              fields=body.model_dump(exclude_unset=True, exclude_none=True))
        ctx.audit(c, "proposal.updated", "proposal", pid, body.model_dump(exclude_unset=True, exclude_none=True))
    return out


@route("POST", "/v1/proposals/{proposal_id}/transition", body=N.ProposalTransitionIn, min_role="manager",
       tags=TP, summary="Envia, analisa, aceita, recusa, pede ajuste ou retira")
def transition_proposal(ctx: Ctx, body: N.ProposalTransitionIn):
    pid = ctx.path["proposal_id"]
    with ctx.tx() as c:
        out = PR.transition(c, proposal_id=pid, to=body.to, org_id=ctx.org_id, actor=ctx.user_id, note=body.note)
        if not out.get("unchanged"):
            ctx.audit(c, "proposal.transition", "proposal", pid,
                      {"to": body.to, "note": body.note,
                       "relationship_id": (out.get("relationship") or {}).get("id")})
    return out


@route("POST", "/v1/proposals/{proposal_id}/attachments", body=N.ProposalAttachIn, min_role="member",
       status=201, tags=TP, summary="Anexa documento do cofre à proposta e avisa a outra parte e a equipe")
def attach_to_proposal(ctx: Ctx, body: N.ProposalAttachIn):
    pid = ctx.path["proposal_id"]
    with ctx.tx() as c:
        out = PR.attach(c, proposal_id=pid, document_id=body.document_id, org_id=ctx.org_id, actor=ctx.user_id,
                        label=body.label)
        ctx.audit(c, "proposal.attached", "proposal", pid, {"document_id": body.document_id})
    return out


# ================================================================================================ conversa
@route("POST", "/v1/conversations", body=N.ThreadIn, min_role="member", status=201, tags=TC,
       summary="Abre (ou reaproveita) a conversa naquele contexto")
def open_conversation(ctx: Ctx, body: N.ThreadIn):
    with ctx.tx() as c:
        out = MSG.open_thread(c, org_id=ctx.org_id, other_org_id=body.other_org_id, actor=ctx.user_id,
                              subject=body.subject, project_id=body.project_id, proposal_id=body.proposal_id,
                              need_id=body.need_id, call_id=body.call_id, professional=body.professional)
        if out.get("created"):
            ctx.audit(c, "conversation.opened", "conversation", out["id"],
                      {"other_org_id": body.other_org_id, "professional": body.professional})
    return out


@route("GET", "/v1/conversations", query=N.ThreadQ, min_role="viewer", tags=TC)
def list_conversations(ctx: Ctx, q: N.ThreadQ):
    with ctx.tx(readonly=True) as c:
        rows = MSG.threads(c, org_id=ctx.org_id, project_id=q.project_id, status=q.status, limit=q.limit + 1,
                           offset=q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/conversations/unread", min_role="viewer", tags=TC)
def unread(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"unread": MSG.unread_count(c, ctx.org_id)}


@route("GET", "/v1/conversations/{conversation_id}", query=N.MessagesQ, min_role="viewer", tags=TC)
def get_conversation(ctx: Ctx, q: N.MessagesQ):
    cid = ctx.path["conversation_id"]
    with ctx.tx(readonly=True) as c:
        return MSG.thread(c, conversation_id=cid, org_id=ctx.org_id, limit=q.limit, before=q.before)


@route("POST", "/v1/conversations/{conversation_id}/messages", body=N.MessageIn, min_role="member",
       status=201, tags=TC, rate=("message", 60, 60))
def send_message(ctx: Ctx, body: N.MessageIn):
    cid = ctx.path["conversation_id"]
    with ctx.tx() as c:
        return MSG.send(c, conversation_id=cid, org_id=ctx.org_id, actor=ctx.user_id, body=body.body,
                        kind=body.kind, ref_type=body.ref_type, ref_id=body.ref_id,
                        document_ids=body.document_ids)


@route("POST", "/v1/conversations/{conversation_id}/read", min_role="viewer", tags=TC)
def read_conversation(ctx: Ctx):
    cid = ctx.path["conversation_id"]
    with ctx.tx() as c:
        return MSG.mark_read(c, conversation_id=cid, org_id=ctx.org_id)


@route("PUT", "/v1/conversations/{conversation_id}/status", body=N.ThreadStatusIn, min_role="member", tags=TC)
def set_conversation_status(ctx: Ctx, body: N.ThreadStatusIn):
    cid = ctx.path["conversation_id"]
    with ctx.tx() as c:
        return MSG.close(c, conversation_id=cid, org_id=ctx.org_id, status=body.status)
