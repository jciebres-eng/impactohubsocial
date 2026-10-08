"""Central de Conhecimento (v0.12.0): ajuda pública/autenticada, busca, guias, biblioteca, FAQ, academia, eventos, suporte, parcerias, demonstração,
boletim e preferências. Reutiliza notificações e documentos (anexos/arquivos); não duplica `materials`. v0.27.0: a solicitação de teste saiu com a assinatura (ADR-341) — quem quer conhecer módulos pede demonstração.
Conteúdo oficial só aparece publicado e aprovado por outra pessoa; visibilidade é aplicada pelo banco (RLS + kb_visible)."""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, UTC

from ..http import ApiError, Ctx, not_found, page, route
from ..services import hub, knowledge as K
from ..services.ratelimit import hit
from . import hub_schemas as H
from . import schemas as S

T = ("help",)
R_READ = ("help_ip", 600, 3600)
R_WRITE = ("help_write_ip", 30, 3600)


def _kind(ctx: Ctx) -> str | None:
    return ctx.principal.org_kind if ctx.principal else None


# ------------------------------------------------------------------------------------------------ descoberta
@route("GET", "/v1/help/search", auth="none", query=H.HelpSearchQ, rate=R_READ, tags=T,
       summary="Busca híbrida (texto + similaridade + vocabulário de tópicos + perfil + tela). Pública para conteúdo público; autenticada amplia por perfil. Sem embeddings.")
def help_search(ctx: Ctx, q: H.HelpSearchQ):
    with ctx.tx() as c:
        return K.search(c, q.q or "", user_kind=_kind(ctx), ctx_key=q.ctx, types={q.type} if q.type else None, limit=q.limit, audience=q.audience, category=q.category)


@route("GET", "/v1/help/context", auth="none", query=H.CtxQ, rate=R_READ, tags=T, summary="Ajuda contextual de uma tela/campo (artigos, FAQs e modelos mapeados)")
def help_context(ctx: Ctx, q: H.CtxQ):
    with ctx.tx() as c:
        return K.contextual(c, q.key, _kind(ctx))


@route("GET", "/v1/help/categories", auth="none", rate=R_READ, tags=T, summary="Categorias com contagem de conteúdo publicado visível para o perfil")
def help_categories(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT k.slug, k.name, k.description, k.sort, (SELECT count(*) FROM kb_articles a WHERE a.category_id = k.id AND a.live_version_id IS NOT NULL) AS articles,"
                       " (SELECT count(*) FROM kb_resources r WHERE r.category_id = k.id AND r.status = 'published') AS resources,"
                       " (SELECT count(*) FROM kb_faqs f WHERE f.category_id = k.id AND f.status = 'published') AS faqs FROM kb_categories k ORDER BY k.sort, k.name")
    return {"items": rows}


class _ArticlesQ(S.Pagination):
    category: str | None = None
    kind: str | None = None


@route("GET", "/v1/help/articles", auth="none", query=_ArticlesQ, rate=R_READ, tags=T, summary="Lista de guias/artigos publicados (visibilidade por perfil)")
def help_articles(ctx: Ctx, q: _ArticlesQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT a.slug, a.kind, a.title, a.summary, a.est_minutes, a.origin, a.demo, a.audience, a.published_at, cat.slug AS category FROM kb_articles a"
                       " LEFT JOIN kb_categories cat ON cat.id = a.category_id WHERE a.live_version_id IS NOT NULL AND ($1::text IS NULL OR cat.slug = $1) AND ($2::text IS NULL OR a.kind = $2)"
                       " ORDER BY a.kind = 'start' DESC, a.title LIMIT $3 OFFSET $4", q.category, q.kind, q.limit + 1, q.offset)
    return page([{**r, **K._label(r), "link": f"/ajuda/{r['slug']}"} for r in rows], q.limit, q.offset)


@route("GET", "/v1/help/articles/{slug}", auth="none", rate=R_READ, tags=T, summary="Guia/artigo com passos, checklist, erros comuns, documentos necessários, ação e conteúdos relacionados")
def help_article(ctx: Ctx):
    with ctx.tx() as c:
        return K.get_article(c, ctx.path["slug"], user_id=ctx.principal.user_id if ctx.principal else None)


@route("GET", "/v1/help/faqs", auth="none", query=H.HelpSearchQ, rate=R_READ, tags=T, summary="FAQ inteligente: por categoria, perfil ou tela; com votos de utilidade")
def help_faqs(ctx: Ctx, q: H.HelpSearchQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT f.id::text AS id, f.question, f.answer, f.origin, f.demo, f.audience, f.tags, f.helpful_yes, f.helpful_no, cat.slug AS category, f.related_article,"
                       " (f.last_reviewed_at IS NOT NULL AND f.last_reviewed_at + make_interval(days => f.review_every_days) < now()) AS needs_review"
                       " FROM kb_faqs f LEFT JOIN kb_categories cat ON cat.id = f.category_id WHERE f.status = 'published' AND ($1::text IS NULL OR cat.slug = $1)"
                       " AND ($2::text IS NULL OR $2 = ANY(f.ctx_keys)) AND ($3::text IS NULL OR cardinality(f.audience) = 0 OR $3 = ANY(f.audience)) ORDER BY f.sort, f.question LIMIT $4",
                       q.category, q.ctx, q.audience, q.limit)
    return {"items": [{**r, **K._label(r)} for r in rows]}


@route("GET", "/v1/help/resources", auth="none", query=H.ResourcesQ, rate=R_READ, tags=T, summary="Biblioteca de documentos, modelos, checklists, vídeos e relatórios publicados")
def help_resources(ctx: Ctx, q: H.ResourcesQ):
    ts = None
    if q.q:
        from ..engines.knowledge import search as KS
        ts = KS.parse(q.q)["tsquery"]
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT r.id::text AS id, r.slug, r.version, r.kind, r.title, r.summary, r.origin, r.demo, r.audience, r.tags, r.published_at, r.regulatory, r.valid_until,"
                       " (r.template_schema IS NOT NULL) AS fillable, (r.document_id IS NOT NULL OR r.url IS NOT NULL) AS downloadable, cat.slug AS category,"
                       " (coalesce(r.last_reviewed_at, r.published_at) + make_interval(days => r.review_every_days) < now() OR (r.regulatory AND r.valid_until < current_date)) AS needs_review"
                       " FROM kb_resources r LEFT JOIN kb_categories cat ON cat.id = r.category_id WHERE r.status = 'published' AND ($1::text IS NULL OR r.kind = $1)"
                       " AND ($2::text IS NULL OR cat.slug = $2) AND ($3::text IS NULL OR r.search_doc @@ to_tsquery('pt_unaccent', $3)) ORDER BY r.published_at DESC LIMIT $4 OFFSET $5",
                       q.kind, q.category, ts, q.limit + 1, q.offset)
    return page([{**r, **K._label(r), "link": f"/ajuda/biblioteca/{r['slug']}"} for r in rows], q.limit, q.offset)


@route("GET", "/v1/help/resources/{slug}", auth="none", rate=R_READ, tags=T, summary="Recurso da biblioteca (com modelo preenchível, checklist e versões anteriores)")
def help_resource(ctx: Ctx):
    with ctx.tx() as c:
        r = c.one("SELECT r.id::text AS id, r.slug, r.version, r.kind, r.title, r.summary, r.origin, r.demo, r.audience, r.tags, r.url, (r.document_id IS NOT NULL) AS has_file, r.template_schema,"
                  " r.checklist_items, r.duration_min, r.period_start, r.period_end, r.ods, r.themes, r.regulatory, r.regulatory_source, r.regulatory_date, r.valid_until, r.published_at,"
                  " r.last_reviewed_at, r.change_note, cat.slug AS category FROM kb_resources r LEFT JOIN kb_categories cat ON cat.id = r.category_id WHERE r.slug = $1 AND r.status = 'published'", ctx.path["slug"])
        if not r:
            raise not_found("Recurso")
        r["versions"] = c.query("SELECT version, status, published_at, change_note FROM kb_resources WHERE slug = $1 AND status IN ('published','superseded') ORDER BY version DESC", r["slug"])
        r["expired"] = bool(r["regulatory"] and r["valid_until"] and r["valid_until"] < datetime.now(UTC).date())
        r["review_notice"] = "Conteúdo regulatório com validade vencida: confirme a regra vigente na fonte oficial." if r["expired"] else None
        r.update(K._label(r))
        if r["url"] is None and not r["has_file"]:
            r["url"] = None
        K.log(c, "view", target_type="resource", target_id=r["id"])
        return r


@route("POST", "/v1/help/resources/{resource_id}/download-url", auth="user", rate=("help_dl", 120, 3600), tags=T,
       summary="URL temporária (5 min) do arquivo do recurso; só recurso publicado e visível; arquivo já passou por varredura antivírus")
def help_resource_download(ctx: Ctx):
    with ctx.tx() as c:
        r = c.one("SELECT id::text AS id, url, document_id::text AS document_id FROM kb_resources WHERE id = $1 AND status = 'published'", ctx.path["resource_id"])
        if not r:
            raise not_found("Recurso")
        K.log(c, "download", target_type="resource", target_id=r["id"])
    if r["url"] and not r["document_id"]:
        return {"url": r["url"], "external": True}
    if not r["document_id"]:
        raise ApiError(409, "no_file", "Este recurso não possui arquivo para download")
    from ..security.tokens import sign_payload
    with ctx.system_tx(isolation=None) as c:
        d = c.one("SELECT id::text AS id, filename, status, storage_key FROM documents WHERE id = $1 AND deleted_at IS NULL", r["document_id"])
        if not d or d["status"] in ("infected", "rejected"):
            raise ApiError(409, "blocked_file", "Arquivo indisponível")
        if d["status"] == "pending_scan" and not ctx.settings.allow_unscanned_downloads:
            raise ApiError(409, "pending_scan", "Arquivo aguardando verificação antivírus")
    url = ctx.app.storage.presigned_get(d["storage_key"], d["filename"], 300)
    if not url:
        url = f"/v1/files/{sign_payload(ctx.settings.secret_key, {'d': d['id'], 'u': ctx.user_id, 'k': d['storage_key']}, 300)}"
    return {"url": url, "expires_in": 300}


@route("POST", "/v1/help/resources/{resource_id}/use-template", body=H.TemplateUseIn, min_role="member", status=201, tags=T,
       summary="Preenche um modelo e cria um rascunho (drafts) da organização — conteúdo gerado do modelo, sem IA")
def use_template(ctx: Ctx, body: H.TemplateUseIn):
    with ctx.tx() as c:
        r = c.one("SELECT title, template_schema FROM kb_resources WHERE id = $1 AND status = 'published'", ctx.path["resource_id"])
        if not r or not r["template_schema"]:
            raise not_found("Modelo")
        sch = r["template_schema"]
        parts = []
        for f in sch["fields"]:
            v = (body.values.get(f["key"]) or "").strip()
            if f.get("required") and not v:
                raise ApiError(422, "field_required", f"Preencha o campo «{f['label']}»")
            parts.append(f"## {f['label']}\n{v}\n")
        content = f"# {r['title']}\n\n" + "\n".join(parts)
        kind = sch.get("draft_kind") if sch.get("draft_kind") in ("project_proposal", "work_plan", "budget_justification", "cover_letter", "progress_report", "final_report") else "other"
        did = c.scalar("INSERT INTO drafts(org_id, project_id, kind, title, content, content_sha256, created_by) VALUES ($1,$2,$3,$4,$5,$6,$7) RETURNING id::text",
                       ctx.org_id, body.project_id, kind, body.title or r["title"], content, hashlib.sha256(content.encode()).hexdigest(), ctx.user_id)
        ctx.audit(c, "help.template_used", "draft", did, {"template": ctx.path["resource_id"]})
        K.log(c, "download", target_type="resource", target_id=ctx.path["resource_id"])
    return {"draft_id": did, "link": "/rascunhos"}


# ------------------------------------------------------------------------------------------------ assistente, feedback, checklists
@route("POST", "/v1/help/assistant", auth="none", body=H.AssistantIn, rate=("help_ai_ip", 60, 3600), tags=T,
       summary="Assistente ancorado: responde SÓ com conteúdo publicado, cita fontes; sem base suficiente recusa e oferece chamado. Não usa IA generativa.")
def help_assistant(ctx: Ctx, body: H.AssistantIn):
    with ctx.tx() as c:
        return K.assistant(c, body.question, user_kind=_kind(ctx), ctx_key=body.ctx)


@route("POST", "/v1/help/feedback", auth="user", body=H.FeedbackIn, rate=("help_fb", 200, 3600), tags=T, summary="\"Este conteúdo ajudou?\" — 'Não ajudou' exige o motivo")
def help_feedback(ctx: Ctx, body: H.FeedbackIn):
    if not body.helpful and not body.reason:
        raise ApiError(422, "reason_required", "Informe por que não ajudou")
    with ctx.tx() as c:
        return K.set_feedback(c, user_id=ctx.user_id, org_id=ctx.principal.org_id, target_type=body.target_type, target_id=body.target_id,
                              helpful=body.helpful, reason=body.reason, comment=body.comment)


@route("PUT", "/v1/help/checklists", auth="user", body=H.ChecklistIn, tags=T, summary="Salva o progresso de um checklist (por pessoa e, opcionalmente, por projeto)")
def checklist_put(ctx: Ctx, body: H.ChecklistIn):
    with ctx.tx() as c:
        if body.project_id and not c.one("SELECT 1 FROM projects WHERE id = $1", body.project_id):
            raise not_found("Projeto")
        return K.set_checklist(c, user_id=ctx.user_id, org_id=ctx.principal.org_id, scope=body.scope, project_id=body.project_id, checked=body.checked)


class _ChecklistQ(S.In):
    scope: str
    project_id: S.Uuid | None = None


@route("GET", "/v1/help/checklists", auth="user", query=_ChecklistQ, tags=T)
def checklist_get(ctx: Ctx, q: _ChecklistQ):
    with ctx.tx(readonly=True) as c:
        r = c.one("SELECT checked, updated_at FROM kb_checklist_progress WHERE user_id = $1 AND scope = $2 AND project_id IS NOT DISTINCT FROM $3", ctx.user_id, q.scope, q.project_id)
    return r or {"checked": [], "updated_at": None}


# ------------------------------------------------------------------------------------------------ "Comece aqui", pendências, atividades
@route("GET", "/v1/help/start", min_role="viewer", tags=T, summary="Comece aqui: jornada por tipo de organização com % de prontidão calculado por dados reais")
def help_start(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        ob = hub.onboarding(c, org_id=ctx.org_id, org_kind=ctx.principal.org_kind)
        miss = [s["guide"] for s in ob["steps"] if not s["done"] and s.get("guide")]
        ob["recommendations_guides"] = miss[:4]
        return ob


@route("GET", "/v1/help/pending", auth="user", tags=T, summary="O que falta para eu avançar? (pendências derivadas de dados reais)")
def help_pending(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return hub.pending_center(c, user_id=ctx.user_id, org_id=ctx.principal.org_id, org_kind=ctx.principal.org_kind)


@route("GET", "/v1/help/activities", auth="user", tags=T, summary="Minhas atividades: chamados, cursos, eventos, certificados e solicitações")
def help_activities(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return hub.my_activities(c, user_id=ctx.user_id, org_id=ctx.principal.org_id)


@route("GET", "/v1/help/recommendations", auth="user", tags=T, summary="Próximos conteúdos recomendados (etapas faltantes, cursos em andamento, eventos); plano não influencia")
def help_recs(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        miss: list[str] = []
        if ctx.principal.org_id:
            ob = hub.onboarding(c, org_id=ctx.principal.org_id, org_kind=ctx.principal.org_kind)
            miss = [s["guide"] for s in ob["steps"] if not s["done"] and s.get("guide")]
        return {"items": K.recommend(c, user_id=ctx.user_id, org_id=ctx.principal.org_id, user_kind=ctx.principal.org_kind, missing_guides=miss)}


# ------------------------------------------------------------------------------------------------ eventos
@route("GET", "/v1/help/events", auth="none", query=H.EventsQ, rate=R_READ, tags=T, summary="Agenda de eventos (vagas restantes) e gravações")
def events(ctx: Ctx, q: H.EventsQ):
    cond = {"upcoming": "e.starts_at >= now() - interval '2 hours' AND e.status = 'published'", "past": "e.starts_at < now() AND e.status IN ('published','completed')", "all": "true"}[q.when]
    with ctx.tx(readonly=True) as c:
        rows = c.query(f"SELECT e.id::text AS id, e.slug, e.kind, e.title, e.description, e.starts_at, e.duration_min, e.speaker, e.modality, e.location, e.capacity, e.registration_open, e.status,"
                       f" e.demo, e.recording_url, (e.recording_url IS NOT NULL OR e.recording_resource_id IS NOT NULL) AS has_recording, hub_event_seats(e.id) AS seats FROM hub_events e"
                       f" WHERE {cond} AND ($1::text IS NULL OR e.kind = $1) ORDER BY CASE WHEN e.starts_at >= now() THEN e.starts_at END ASC NULLS LAST, e.starts_at DESC LIMIT $2 OFFSET $3",
                       q.kind, q.limit + 1, q.offset)
    items = []
    for r in rows:
        seats = r.pop("seats")
        items.append(hub.event_card(r, seats=seats))
    return page(items, q.limit, q.offset)


@route("GET", "/v1/help/events/mine", auth="user", tags=T, summary="Minhas inscrições")
def events_mine(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT e.id::text AS id, e.slug, e.title, e.starts_at, g.status, g.attended, g.satisfaction FROM hub_event_registrations g JOIN hub_events e ON e.id = g.event_id"
                                 " WHERE g.user_id = $1 AND g.status <> 'cancelled' ORDER BY e.starts_at DESC LIMIT 50", ctx.user_id)}


@route("GET", "/v1/help/events/{slug}", auth="none", rate=R_READ, tags=T, summary="Evento (link de acesso só para inscritas; materiais/gravação após o evento)")
def event_get(ctx: Ctx):
    with ctx.tx() as c:
        e = c.one("SELECT e.id::text AS id, e.slug, e.kind, e.title, e.description, e.starts_at, e.duration_min, e.speaker, e.modality, e.location, e.capacity, e.registration_open, e.status, e.audience,"
                  " e.demo, e.recording_url, e.materials, e.summary FROM hub_events e WHERE e.slug = $1", ctx.path["slug"])
        if not e:
            raise not_found("Evento")
        seats = c.scalar("SELECT hub_event_seats($1)", e["id"])
        mine = c.one("SELECT status, attended, satisfaction FROM hub_event_registrations WHERE event_id = $1 AND user_id = $2", e["id"], ctx.principal.user_id) if ctx.principal else None
        link = c.one("SELECT join_url FROM hub_event_links WHERE event_id = $1", e["id"]) if mine and mine["status"] == "registered" else None
        e = hub.event_card(e, seats=seats)
        e["my_registration"] = mine
        e["join_url"] = link["join_url"] if link else None
        if e["status"] != "completed":
            e["materials"] = []
            e["recording_url"] = None
        return e


@route("POST", "/v1/help/events/{event_id}/register", auth="user", rate=("event_reg", 60, 3600), tags=T, summary="Inscrição (lista de espera quando lotado)")
def event_register(ctx: Ctx):
    with ctx.system_tx() as c:
        # contagem de vagas e promoção exigem ver todas as inscrições: contexto de sistema restrito a este módulo revisado
        out = hub.event_register(c, ctx.path["event_id"], user_id=ctx.user_id, org_id=ctx.principal.org_id)
        ctx.audit(c, "help.event_registered", "event", ctx.path["event_id"], {"status": out["status"]})
    return out


@route("DELETE", "/v1/help/events/{event_id}/register", auth="user", tags=T, summary="Cancela a inscrição e promove a lista de espera")
def event_cancel(ctx: Ctx):
    with ctx.system_tx() as c:
        out = hub.event_cancel(c, ctx.path["event_id"], user_id=ctx.user_id)
        ctx.audit(c, "help.event_cancelled", "event", ctx.path["event_id"])
    return out


@route("POST", "/v1/help/events/{event_id}/rate", auth="user", body=H.EventRateIn, tags=T, summary="Avalia o evento (só quem participou)")
def event_rate(ctx: Ctx, body: H.EventRateIn):
    with ctx.tx() as c:
        r = c.one("SELECT attended FROM hub_event_registrations WHERE event_id = $1 AND user_id = $2", ctx.path["event_id"], ctx.user_id)
        if not r or not r["attended"]:
            raise ApiError(409, "not_attended", "Só quem participou pode avaliar")
        c.run("UPDATE hub_event_registrations SET satisfaction = $3 WHERE event_id = $1 AND user_id = $2", ctx.path["event_id"], ctx.user_id, body.satisfaction)
    return {"recorded": True}


# ------------------------------------------------------------------------------------------------ academia
@route("GET", "/v1/help/courses", auth="none", rate=R_READ, tags=T, summary="Cursos publicados e trilhas por perfil")
def courses(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT k.slug, k.title, k.summary, k.level, k.hours, k.audience, k.origin, k.demo, k.cert_enabled,"
                       " (SELECT count(*) FROM course_lessons l WHERE l.course_id = k.id) AS lessons FROM courses k WHERE k.status = 'published' ORDER BY k.title")
        paths = c.query("SELECT slug, title, description, audience, items, demo FROM learning_paths WHERE status = 'published' ORDER BY title")
    return {"items": [{**r, **K._label(r)} for r in rows], "paths": paths}


@route("GET", "/v1/help/courses/{slug}", auth="none", rate=R_READ, tags=T, summary="Curso: módulos, aulas e progresso (quando autenticada)")
def course_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return hub.course_detail(c, ctx.path["slug"], user_id=ctx.principal.user_id if ctx.principal else None)


@route("POST", "/v1/help/courses/{slug}/enroll", auth="user", tags=T)
def course_enroll(ctx: Ctx):
    with ctx.tx() as c:
        return hub.course_enroll(c, ctx.path["slug"], user_id=ctx.user_id, org_id=ctx.principal.org_id)


@route("GET", "/v1/help/lessons/{lesson_id}", auth="user", tags=T, summary="Conteúdo da aula (quiz sem gabarito)")
def lesson_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        ls = hub.lesson_get(c, ctx.path["lesson_id"])
        ls["quiz"] = [{"q": q.get("q"), "options": q.get("options")} for q in (ls["quiz"] or [])]
        return ls


@route("POST", "/v1/help/lessons/{lesson_id}/complete", auth="user", body=H.LessonDoneIn, rate=("lesson_done", 300, 3600), tags=T,
       summary="Conclui a aula; quiz é corrigido no servidor (gabarito nunca sai do banco)")
def lesson_complete(ctx: Ctx, body: H.LessonDoneIn):
    with ctx.tx() as c:
        return hub.lesson_complete(c, ctx.path["lesson_id"], user_id=ctx.user_id, answers=body.answers, holder_name=ctx.principal.full_name, org_id=ctx.principal.org_id)


@route("POST", "/v1/help/courses/{slug}/certificate", auth="user", status=201, tags=T, summary="Emite o certificado de conclusão (não oficial) quando todas as aulas foram concluídas")
def certificate(ctx: Ctx):
    with ctx.system_tx() as c:
        out = hub.certificate_issue(c, ctx.path["slug"], user_id=ctx.user_id, org_id=ctx.principal.org_id, holder_name=ctx.principal.full_name)
        if out.get("issued"):
            ctx.audit(c, "help.certificate_issued", "course", ctx.path["slug"], {"code": out["code"]})
    return out


@route("GET", "/v1/help/certificates/{code}", auth="none", rate=("cert_verify", 60, 3600), tags=T, summary="Verifica a autenticidade de um certificado de conclusão pelo código")
def certificate_verify(ctx: Ctx):
    with ctx.system_tx() as c:
        return hub.certificate_verify(c, ctx.path["code"])


# ------------------------------------------------------------------------------------------------ suporte
@route("POST", "/v1/support/tickets", auth="user", body=H.TicketIn, status=201, rate=("ticket_ip", 30, 3600), tags=("support",),
       summary="Abre chamado (categoria, contexto da tela e anexos já enviados em Documentos). Prioridade/SLA são definidos pela equipe.")
def ticket_create(ctx: Ctx, body: H.TicketIn):
    hit(ctx, "ticket_user", ctx.user_id, 15, 3600)
    with ctx.tx() as c:
        out = hub.ticket_create(c, user_id=ctx.user_id, org_id=ctx.principal.org_id, category=body.category, subject=body.subject, message=body.message,
                                context=dict(body.context), document_ids=body.document_ids)
        ctx.audit(c, "support.ticket_created", "ticket", out["id"], {"category": body.category})
    return {**out, "note": "Recebemos seu chamado. Você será avisada aqui e nas notificações."}


@route("GET", "/v1/support/tickets", auth="user", query=S.Pagination, tags=("support",))
def tickets_mine(ctx: Ctx, q: S.Pagination):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, number, category, subject, status, priority, created_at, updated_at FROM support_tickets WHERE user_id = $1 ORDER BY updated_at DESC LIMIT $2 OFFSET $3",
                       ctx.user_id, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@route("GET", "/v1/support/tickets/{ticket_id}", auth="user", tags=("support",))
def ticket_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return hub.ticket_get(c, ctx.path["ticket_id"], staff=False)


@route("POST", "/v1/support/tickets/{ticket_id}/messages", auth="user", body=H.TicketReplyIn, status=201, rate=("ticket_msg_ip", 120, 3600), tags=("support",))
def ticket_reply(ctx: Ctx, body: H.TicketReplyIn):
    with ctx.tx() as c:
        out = hub.ticket_reply(c, ctx.path["ticket_id"], author_id=ctx.user_id, body=body.body, staff=False, internal=False, document_ids=body.document_ids, org_id=ctx.principal.org_id)
    return out


@route("POST", "/v1/support/tickets/{ticket_id}/rate", auth="user", body=H.TicketRateIn, tags=("support",), summary="Avalia o atendimento (após resolvido)")
def ticket_rate(ctx: Ctx, body: H.TicketRateIn):
    with ctx.tx() as c:
        return hub.ticket_rate(c, ctx.path["ticket_id"], body.score)


@route("POST", "/v1/support/tickets/{ticket_id}/close", auth="user", tags=("support",), summary="Encerra um chamado já resolvido")
def ticket_close(ctx: Ctx):
    with ctx.tx() as c:
        t = c.one("SELECT status FROM support_tickets WHERE id = $1", ctx.path["ticket_id"])
        if not t:
            raise not_found("Chamado")
        if t["status"] != "resolved":
            raise ApiError(409, "not_resolved", "Só é possível encerrar um chamado resolvido")
        c.run("UPDATE support_tickets SET status = 'closed' WHERE id = $1", ctx.path["ticket_id"])
    return {"closed": True}


# ------------------------------------------------------------------------------------------------ públicos de captação (consentimento obrigatório)
def _spam(body) -> bool:
    return bool(getattr(body, "website", None))


@route("POST", "/v1/help/partnerships", auth="none", body=H.PartnershipIn, status=201, rate=("partner_ip", 5, 3600), tags=("partnerships",),
       summary="Pedido de parceria (formulário público; consentimento obrigatório para contato)")
def partnership_create(ctx: Ctx, body: H.PartnershipIn):
    if not body.consent:
        raise ApiError(422, "consent_required", "É necessário concordar com o contato para enviar o pedido")
    if _spam(body):
        return {"id": str(uuid.uuid4()), "status": "received"}      # isca anti-bot: resposta idêntica, nada é gravado
    rid = str(uuid.uuid4())
    p = ctx.principal
    with ctx.tx() as c:
        c.run("INSERT INTO partnership_requests(id, user_id, org_id, org_name, contact_name, contact_email, contact_phone, kind, objective, proposal, territory, audience, resources_offered,"
              " counterpart, target_date) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)", rid, p.user_id if p else None, p.org_id if p else None, body.org_name, body.contact_name,
              body.contact_email, body.contact_phone, body.kind, body.objective, body.proposal, body.territory, body.audience, body.resources_offered, body.counterpart, body.target_date)
    try:
        ctx.app.mailer.send(body.contact_email, "[Impacto] Recebemos seu pedido de parceria", "Olá! Recebemos seu pedido de parceria e nossa equipe retornará por este e-mail.\n")
    except Exception:  # noqa: BLE001
        logging.getLogger("impacto.knowledge").warning("mail_failed")
    return {"id": rid, "status": "received"}


@route("POST", "/v1/help/demo-requests", auth="none", body=H.DemoIn, status=201, rate=("demo_ip", 5, 3600), tags=("help",), summary="Agendamento de demonstração (consentimento obrigatório)")
def demo_create(ctx: Ctx, body: H.DemoIn):
    if not body.consent:
        raise ApiError(422, "consent_required", "É necessário concordar com o contato para agendar")
    if _spam(body):
        return {"id": str(uuid.uuid4()), "status": "requested"}
    rid = str(uuid.uuid4())
    p = ctx.principal
    with ctx.tx() as c:
        c.run("INSERT INTO demo_requests(id, user_id, org_id, org_name, contact_name, contact_email, contact_phone, audience_kind, org_size, interest, preferred_slots, notes)"
              " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::timestamptz[],$12)", rid, p.user_id if p else None, p.org_id if p else None, body.org_name, body.contact_name, body.contact_email,
              body.contact_phone, body.audience_kind, body.org_size, body.interest, body.preferred_slots, body.notes)
    return {"id": rid, "status": "requested"}


@route("POST", "/v1/help/newsletter", auth="none", body=H.NewsletterIn, rate=("news_ip", 10, 3600), tags=("help",),
       summary="Inscrição no boletim com confirmação por e-mail (duplo opt-in). Resposta idêntica exista ou não a inscrição (sem enumeração).")
def newsletter(ctx: Ctx, body: H.NewsletterIn):
    if not body.consent:
        raise ApiError(422, "consent_required", "Confirme que deseja receber o boletim")
    hit(ctx, "news_email", hashlib.sha256(body.email.lower().encode()).hexdigest()[:32], 3, 3600)
    out = {"status": "pending", "note": "Se o e-mail for válido, enviaremos um link para confirmar a inscrição."}
    if _spam(body):
        return out
    with ctx.system_tx() as c:
        tok = hub.newsletter_subscribe(c, email=body.email.lower(), topics=list(body.topics), frequency=body.frequency, user_id=ctx.principal.user_id if ctx.principal else None)
    if tok:
        link = f"{ctx.settings.public_base_url.rstrip('/')}/ajuda/boletim/confirmar?token={tok}"
        try:
            ctx.app.mailer.send(body.email, "[Impacto] Confirme sua inscrição no boletim", f"Para confirmar sua inscrição, acesse: {link}\nSe não foi você, ignore esta mensagem.\n")
        except Exception:  # noqa: BLE001
            logging.getLogger("impacto.knowledge").warning("mail_failed")
    return out


@route("POST", "/v1/help/newsletter/confirm", auth="none", body=H.TokenIn, rate=("news_conf_ip", 30, 3600), tags=("help",))
def newsletter_confirm(ctx: Ctx, body: H.TokenIn):
    with ctx.tx() as c:
        ok = hub.newsletter_confirm(c, body.token)
    if not ok:
        raise ApiError(404, "invalid_token", "Link inválido ou já utilizado")
    return {"status": "active"}


@route("POST", "/v1/help/newsletter/unsubscribe", auth="none", body=H.TokenIn, rate=("news_unsub_ip", 30, 3600), tags=("help",))
def newsletter_unsubscribe(ctx: Ctx, body: H.TokenIn):
    with ctx.tx() as c:
        ok = hub.newsletter_unsubscribe(c, body.token)
    if not ok:
        raise ApiError(404, "invalid_token", "Link inválido ou inscrição já cancelada")
    return {"status": "unsubscribed"}


# ------------------------------------------------------------------------------------------------ preferências, SEO
@route("GET", "/v1/notifications/prefs", auth="user", tags=("notifications",), summary="Preferências de notificação por grupo (app e e-mail)")
def prefs_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": hub.prefs_get(c, ctx.user_id)}


@route("PUT", "/v1/notifications/prefs", auth="user", body=H.PrefsIn, tags=("notifications",))
def prefs_put(ctx: Ctx, body: H.PrefsIn):
    with ctx.tx() as c:
        return {"items": hub.prefs_set(c, ctx.user_id, [i.model_dump() for i in body.items])}


@route("GET", "/v1/help/sitemap", auth="none", rate=R_READ, tags=T, summary="Sitemap do conteúdo PÚBLICO indexável (exemplos/DEMO e conteúdo privado ficam de fora)")
def sitemap(ctx: Ctx):
    base = ctx.settings.public_base_url.rstrip("/")
    with ctx.pool.tx(__import__("impacto.db.pool", fromlist=["DbContext"]).DbContext(), readonly=True) as c:
        arts = c.query("SELECT slug, coalesce(last_reviewed_at, published_at) AS lastmod FROM kb_articles WHERE live_version_id IS NOT NULL AND visibility = 'public' AND NOT demo ORDER BY slug")
        res = c.query("SELECT slug, published_at AS lastmod FROM kb_resources WHERE status = 'published' AND visibility = 'public' AND NOT demo ORDER BY slug")
        evs = c.query("SELECT slug, starts_at AS lastmod FROM hub_events WHERE status IN ('published','completed') AND visibility = 'public' AND NOT demo ORDER BY slug")
    urls = [{"loc": f"{base}/ajuda", "lastmod": None}] + [{"loc": f"{base}/ajuda/{a['slug']}", "lastmod": a["lastmod"]} for a in arts] \
        + [{"loc": f"{base}/ajuda/biblioteca/{r['slug']}", "lastmod": r["lastmod"]} for r in res] + [{"loc": f"{base}/ajuda/eventos/{e['slug']}", "lastmod": e["lastmod"]} for e in evs]
    return {"urls": urls, "robots": {"private_areas": ["/ajuda/suporte", "/ajuda/minhas-atividades", "/conta"], "note": "conteúdo autenticado/DEMO recebe noindex"}}

