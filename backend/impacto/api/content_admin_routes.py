"""Administração da Central de Conhecimento (CMS editorial, suporte, eventos, academia, parcerias, demonstrações, testes, boletim, analytics).

Papéis internos (tabela staff_roles, sempre com MFA): editor (cria/edita rascunhos e envia para revisão), reviewer (aprova/publica; NUNCA o próprio texto —
quatro olhos também no banco), support (fila de chamados). Administradores da plataforma podem tudo, mas a regra dos quatro olhos vale para eles também.
Cada handler toca apenas as tabelas do seu domínio (kb_*, courses, hub_*, support_*, partnership_*, demo_*, trial_requests, newsletter_*)."""
from __future__ import annotations

import json
from pydantic import Field

from ..http import ApiError, Ctx, not_found, page, route
from ..services import hub, knowledge as K
from . import hub_schemas as H
from . import schemas as S

T = ("admin", "content")
EDIT = ("editor", "reviewer")
REVIEW = ("reviewer",)
SUPPORT = ("support",)


def A(method, path, staff=(), **kw):
    return route(method, path, auth="admin", tags=T, staff=staff, **kw)


def _is_admin(ctx: Ctx) -> bool:
    return ctx.principal.is_platform_admin



def _cat(c, slug: str | None) -> str | None:
    if not slug:
        return None
    cid = c.scalar("SELECT id::text FROM kb_categories WHERE slug = $1", slug)
    if not cid:
        raise ApiError(422, "invalid_category", "Categoria inexistente")
    return cid


def _j(v) -> str:
    return json.dumps(v, ensure_ascii=False, default=str)


# ------------------------------------------------------------------------------------------------ papéis internos
@A("GET", "/v1/admin/staff-roles", permission="admin.users.read", summary="Papéis internos (editor, reviewer, support)")
def staff_list(ctx: Ctx):
    if not _is_admin(ctx):
        raise ApiError(403, "admin_only", "Somente administradores da plataforma")
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT s.user_id::text AS user_id, u.email::text AS email, u.full_name, s.role, s.granted_at FROM staff_roles s JOIN users u ON u.id = s.user_id ORDER BY u.full_name, s.role")}


@A("POST", "/v1/admin/staff-roles", permission="admin.users.write", body=H.StaffRoleIn, status=201, summary="Concede papel interno (auditado)")
def staff_grant(ctx: Ctx, body: H.StaffRoleIn):
    if not _is_admin(ctx):
        raise ApiError(403, "admin_only", "Somente administradores da plataforma")
    with ctx.tx() as c:
        u = c.one("SELECT id::text AS id FROM users WHERE email = $1 AND status = 'active'", body.email.lower())
        if not u:
            raise not_found("Usuária")
        c.run("INSERT INTO staff_roles(user_id, role, granted_by) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", u["id"], body.role, ctx.user_id)
        ctx.audit(c, "staff.role_granted", "user", u["id"], {"role": body.role})
    return {"user_id": u["id"], "role": body.role}


@A("DELETE", "/v1/admin/staff-roles/{user_id}/{role}", permission="admin.users.write", query=H.StaffRevokeQ,
   summary="Revoga papel interno, com motivo registrado")
def staff_revoke(ctx: Ctx, q: H.StaffRevokeQ):
    """v0.20.0: revogar um papel interno é tirar acesso de uma pessoa, e a operação não registrava
    por quê. O inventário de risco a classificou como CRITICAL e o teste cobrou o motivo."""
    if not _is_admin(ctx):
        raise ApiError(403, "admin_only", "Somente administradores da plataforma")
    with ctx.tx() as c:
        c.run("DELETE FROM staff_roles WHERE user_id = $1 AND role = $2", ctx.path["user_id"], ctx.path["role"])
        ctx.audit(c, "staff.role_revoked", "user", ctx.path["user_id"],
                  {"role": ctx.path["role"], "reason": q.reason})
    return {"revoked": True, "reason": q.reason}


# ------------------------------------------------------------------------------------------------ painel editorial
@A("GET", "/v1/admin/content/overview", staff=EDIT + SUPPORT, permission="content.read", summary="Painel editorial: itens por estado, aguardando revisão e conteúdo desatualizado")
def overview(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        by = {
            "article_versions": c.query("SELECT status, count(*) AS n FROM kb_article_versions GROUP BY status"),
            "resources": c.query("SELECT status, count(*) AS n FROM kb_resources GROUP BY status"),
            "faqs": c.query("SELECT status, count(*) AS n FROM kb_faqs GROUP BY status"),
            "courses": c.query("SELECT status, count(*) AS n FROM courses GROUP BY status"),
            "events": c.query("SELECT status, count(*) AS n FROM hub_events GROUP BY status"),
        }
        waiting = c.query("SELECT 'article_version' AS type, v.id::text AS id, v.title, a.slug AS ref, v.created_at FROM kb_article_versions v JOIN kb_articles a ON a.id = v.article_id WHERE v.status = 'review'"
                          " UNION ALL SELECT 'resource', id::text, title, slug, created_at FROM kb_resources WHERE status = 'review'"
                          " UNION ALL SELECT 'faq', id::text, question, NULL, created_at FROM kb_faqs WHERE status = 'review'"
                          " UNION ALL SELECT 'course', id::text, title, slug, created_at FROM courses WHERE status = 'review'"
                          " UNION ALL SELECT 'event', id::text, title, slug, created_at FROM hub_events WHERE status = 'review' ORDER BY created_at LIMIT 100")
        return {"by_status": by, "waiting_review": waiting, "stale": K.stale_overview(c), "low_resolution_faqs": K.low_resolution_faqs(c)}


@A("POST", "/v1/admin/content/categories", staff=EDIT, body=H.CategoryIn, status=201)
def category_create(ctx: Ctx, body: H.CategoryIn):
    with ctx.tx() as c:
        c.run("INSERT INTO kb_categories(slug, name, description, sort) VALUES ($1,$2,$3,$4) ON CONFLICT (slug) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, sort = EXCLUDED.sort",
              body.slug, body.name, body.description, body.sort)
        ctx.audit(c, "content.category_saved", "category", body.slug)
    return {"slug": body.slug}


@A("GET", "/v1/admin/content/history/{object_type}/{object_id}", staff=EDIT, summary="Histórico editorial (quem fez o quê, quando)")
def content_history(ctx: Ctx):
    if ctx.path["object_type"] not in K.OBJECTS:
        raise not_found("Tipo")
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT h.from_status, h.to_status, h.note, h.at, u.full_name AS actor FROM content_history h LEFT JOIN users u ON u.id = h.actor_id"
                                 " WHERE h.object_type = $1 AND h.object_id = $2 ORDER BY h.at", ctx.path["object_type"], ctx.path["object_id"])}


# ------------------------------------------------------------------------------------------------ artigos / guias
def _insert_version(c, article_id: str, version: int, body, actor: str) -> str:
    return c.scalar("INSERT INTO kb_article_versions(article_id, version, title, summary, body, steps, checklist, common_mistakes, refs, regulatory, regulatory_source, regulatory_date,"
                    " valid_until, change_note, author_id) VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb,$8::jsonb,$9::jsonb,$10,$11,$12,$13,$14,$15) RETURNING id::text",
                    article_id, version, body.title, body.summary, body.body, _j([s.model_dump() for s in body.steps]), _j(body.checklist), _j(body.common_mistakes),
                    _j([r.model_dump() for r in body.refs]), body.regulatory, body.regulatory_source, body.regulatory_date, body.valid_until, body.change_note, actor)


@A("POST", "/v1/admin/content/articles", staff=EDIT, body=H.ArticleIn, status=201, summary="Cria artigo/guia (versão 1 em rascunho)")
def article_create(ctx: Ctx, body: H.ArticleIn):
    with ctx.tx() as c:
        if c.one("SELECT 1 FROM kb_articles WHERE slug = $1", body.slug):
            raise ApiError(409, "slug_taken", "Já existe um conteúdo com este endereço (slug)")
        aid = c.scalar("INSERT INTO kb_articles(slug, kind, category_id, audience, visibility, origin, tags, ctx_keys, est_minutes, required_docs, action_label, action_link, related_articles,"
                       " related_resources, related_courses, review_every_days, demo, created_by) VALUES ($1,$2,$3,$4::text[],$5,$6,$7::text[],$8::text[],$9,$10::text[],$11,$12,$13::text[],$14::text[],$15::text[],$16,$17,$18)"
                       " RETURNING id::text", body.slug, body.kind, _cat(c, body.category), body.audience, body.visibility, body.origin, body.tags,
                       body.ctx_keys, body.est_minutes, body.required_docs, body.action_label, body.action_link, body.related_articles, body.related_resources, body.related_courses,
                       body.review_every_days, body.demo, ctx.user_id)
        vid = _insert_version(c, aid, 1, body, ctx.user_id)
        K.history(c, "article_version", vid, None, "draft", ctx.user_id, "criado")
        ctx.audit(c, "content.article_created", "article", aid, {"slug": body.slug})
    return {"id": aid, "version_id": vid, "slug": body.slug}


@A("GET", "/v1/admin/content/articles", staff=EDIT + SUPPORT, query=H.AdminListQ)
def article_list(ctx: Ctx, q: H.AdminListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT a.id::text AS id, a.slug, a.kind, a.demo, a.origin, a.visibility, a.live_version_id IS NOT NULL AS live, a.last_reviewed_at, a.view_count,"
                       " (SELECT v.title FROM kb_article_versions v WHERE v.article_id = a.id ORDER BY v.version DESC LIMIT 1) AS title,"
                       " (SELECT v.status FROM kb_article_versions v WHERE v.article_id = a.id ORDER BY v.version DESC LIMIT 1) AS latest_status FROM kb_articles a"
                       " WHERE ($1::text IS NULL OR a.slug ILIKE '%' || $1 || '%') ORDER BY a.created_at DESC LIMIT $2 OFFSET $3", q.q, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("GET", "/v1/admin/content/articles/{slug}", staff=EDIT + SUPPORT)
def article_admin_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        a = c.one("SELECT id::text AS id, slug, kind, audience, visibility, origin, tags, ctx_keys, est_minutes, required_docs, action_label, action_link, related_articles, related_resources,"
                  " related_courses, review_every_days, demo, last_reviewed_at, live_version_id::text AS live_version_id FROM kb_articles WHERE slug = $1", ctx.path["slug"])
        if not a:
            raise not_found("Artigo")
        a["versions"] = c.query("SELECT id::text AS id, version, status, title, summary, body, steps, checklist, common_mistakes, refs, regulatory, regulatory_source, regulatory_date, valid_until,"
                                " change_note, author_id::text AS author_id, approved_by::text AS approved_by, approved_at, published_at, created_at FROM kb_article_versions"
                                " WHERE article_id = $1 ORDER BY version DESC", a["id"])
        return a


class ArticleMetaIn(S.In):
    audience: H.Audience | None = None
    visibility: H.Visibility | None = None
    origin: H.Origin | None = None
    tags: list[str] | None = None
    ctx_keys: list[H.CtxKey] | None = None
    est_minutes: int | None = Field(default=None, ge=1, le=600)
    action_label: str | None = Field(default=None, max_length=80)
    action_link: str | None = Field(default=None, pattern=r"^/", max_length=200)
    related_articles: list[H.Slug] | None = None
    related_resources: list[H.Slug] | None = None
    related_courses: list[H.Slug] | None = None
    review_every_days: int | None = Field(default=None, ge=7, le=1095)
    demo: bool | None = None


@A("PATCH", "/v1/admin/content/articles/{slug}", staff=EDIT, body=ArticleMetaIn, summary="Atualiza metadados (público, tags, telas, relacionados). O texto só muda por nova versão.")
def article_meta(ctx: Ctx, body: ArticleMetaIn):
    data = body.model_dump(exclude_unset=True)
    if not data:
        raise ApiError(422, "empty", "Nada para atualizar")
    allowed = {"audience": "text[]", "tags": "text[]", "ctx_keys": "text[]", "related_articles": "text[]", "related_resources": "text[]", "related_courses": "text[]"}
    sets, vals = [], [ctx.path["slug"]]
    for k, v in data.items():
        vals.append(v)
        sets.append(f"{k} = ${len(vals)}" + (f"::{allowed[k]}" if k in allowed else ""))
    with ctx.tx() as c:
        a = c.one("SELECT id::text AS id FROM kb_articles WHERE slug = $1", ctx.path["slug"])
        if not a:
            raise not_found("Artigo")
        c.run(f"UPDATE kb_articles SET {', '.join(sets)}, updated_at = now() WHERE slug = $1", *vals)
        ctx.audit(c, "content.article_meta_updated", "article", a["id"], {"fields": sorted(data)})
    return {"slug": ctx.path["slug"]}


@A("POST", "/v1/admin/content/articles/{slug}/versions", staff=EDIT, body=H.VersionIn, status=201, summary="Nova versão (rascunho) a partir de uma edição; exige nota de mudança")
def article_new_version(ctx: Ctx, body: H.VersionIn):
    if not body.change_note:
        raise ApiError(422, "change_note_required", "Descreva a mudança (nota de versão)")
    with ctx.tx() as c:
        a = c.one("SELECT id::text AS id FROM kb_articles WHERE slug = $1", ctx.path["slug"])
        if not a:
            raise not_found("Artigo")
        if c.one("SELECT 1 FROM kb_article_versions WHERE article_id = $1 AND status IN ('draft','review','approved')", a["id"]):
            raise ApiError(409, "open_version", "Já existe uma versão em andamento para este artigo")
        n = c.scalar("SELECT coalesce(max(version), 0) + 1 FROM kb_article_versions WHERE article_id = $1", a["id"])
        vid = _insert_version(c, a["id"], n, body, ctx.user_id)
        K.history(c, "article_version", vid, None, "draft", ctx.user_id, body.change_note)
    return {"version_id": vid, "version": n}


@A("PUT", "/v1/admin/content/article-versions/{version_id}", staff=EDIT, body=H.VersionIn, summary="Edita uma versão em RASCUNHO (versões revisadas são imutáveis)")
def article_version_edit(ctx: Ctx, body: H.VersionIn):
    with ctx.tx() as c:
        v = c.one("SELECT status FROM kb_article_versions WHERE id = $1", ctx.path["version_id"])
        if not v:
            raise not_found("Versão")
        if v["status"] != "draft":
            raise ApiError(409, "not_draft", "Só é possível editar versões em rascunho: crie uma nova versão")
        c.run("UPDATE kb_article_versions SET title = $2, summary = $3, body = $4, steps = $5::jsonb, checklist = $6::jsonb, common_mistakes = $7::jsonb, refs = $8::jsonb, regulatory = $9,"
              " regulatory_source = $10, regulatory_date = $11, valid_until = $12, change_note = coalesce($13, change_note) WHERE id = $1", ctx.path["version_id"], body.title, body.summary, body.body,
              _j([s.model_dump() for s in body.steps]), _j(body.checklist), _j(body.common_mistakes), _j([r.model_dump() for r in body.refs]), body.regulatory, body.regulatory_source,
              body.regulatory_date, body.valid_until, body.change_note)
    return {"updated": True}


# ------------------------------------------------------------------------------------------------ transições (comum a todos os tipos)
def _transition(ctx: Ctx, obj_type: str, body: H.TransitionIn):
    if body.to in ("approved", "published", "archived") and not _is_admin(ctx) and "reviewer" not in ctx.principal.staff_roles:
        raise ApiError(403, "role_required", "Aprovar, publicar ou arquivar exige o papel 'reviewer'")
    with ctx.tx() as c:
        out = K.transition(c, obj_type, ctx.path["id"], body.to, actor=ctx.user_id, note=body.note)
        ctx.audit(c, f"content.{obj_type}.{body.to}", obj_type, ctx.path["id"], {"note": body.note})
    return out


for _t, _p in (("article_version", "article-versions"), ("resource", "resources"), ("faq", "faqs"), ("course", "courses"), ("event", "events"), ("path", "paths")):
    def _mk(t=_t):
        def handler(ctx: Ctx, body: H.TransitionIn):
            return _transition(ctx, t, body)
        handler.__name__ = f"transition_{t}"
        return handler
    route("POST", f"/v1/admin/content/{_p}/{{id}}/transition", auth="admin", staff=EDIT, body=H.TransitionIn, tags=T,
          summary="Fluxo editorial: rascunho → revisão → aprovado → publicado → arquivado. Aprovação por OUTRA pessoa (quatro olhos).")(_mk())


@A("POST", "/v1/admin/content/{obj_type}/{id}/reviewed", staff=REVIEW, body=H.ReviewedIn, summary="Confirma que o conteúdo continua válido (zera 'Revisão necessária')")
def reviewed(ctx: Ctx, body: H.ReviewedIn):
    if ctx.path["obj_type"] not in ("article", "resource", "faq", "course"):
        raise not_found("Tipo")
    with ctx.tx() as c:
        out = K.mark_reviewed(c, ctx.path["obj_type"], ctx.path["id"], actor=ctx.user_id, note=body.note)
        ctx.audit(c, "content.reviewed", ctx.path["obj_type"], ctx.path["id"])
    return out


# ------------------------------------------------------------------------------------------------ recursos
def _res_vals(body: H.ResourceIn, cid: str | None, doc_id: str | None) -> list:
    return [body.kind, cid, body.title, body.summary, body.audience, body.visibility, body.origin, body.tags, body.url, doc_id,
            _j(body.template_schema.model_dump()) if body.template_schema else None, _j(body.checklist_items), body.duration_min, body.period_start, body.period_end, body.ods,
            body.territories, body.themes, body.ctx_keys, body.regulatory, body.regulatory_source, body.regulatory_date, body.valid_until, body.change_note, body.review_every_days, body.demo]


RES_INSERT = ("INSERT INTO kb_resources(slug, version, kind, category_id, title, summary, audience, visibility, origin, tags, url, document_id, template_schema, checklist_items, duration_min,"
              " period_start, period_end, ods, territories, themes, ctx_keys, regulatory, regulatory_source, regulatory_date, valid_until, change_note, review_every_days, demo, author_id)"
              " VALUES ($1,$2,$3,$4,$5,$6,$7::text[],$8,$9,$10::text[],$11,$12,$13::jsonb,$14::jsonb,$15,$16,$17,$18::smallint[],$19::text[],$20::text[],$21::text[],$22,$23,$24,$25,$26,$27,$28,$29) RETURNING id::text")


def _check_doc(c, doc_id: str | None) -> None:
    if doc_id and not c.one("SELECT 1 FROM documents WHERE id = $1 AND deleted_at IS NULL AND status NOT IN ('infected','rejected')", doc_id):
        raise ApiError(422, "invalid_document", "Documento inexistente ou bloqueado")


@A("POST", "/v1/admin/content/resources", staff=EDIT, body=H.ResourceIn, status=201, summary="Cria recurso (modelo, documento, checklist, vídeo, relatório, boletim) em rascunho")
def resource_create(ctx: Ctx, body: H.ResourceIn):
    with ctx.tx() as c:
        if c.one("SELECT 1 FROM kb_resources WHERE slug = $1", body.slug):
            raise ApiError(409, "slug_taken", "Slug já existe: use 'nova versão' do recurso")
        _check_doc(c, body.document_id)
        v = _res_vals(body, _cat(c, body.category), body.document_id)
        rid = c.scalar(RES_INSERT, body.slug, 1, *v, ctx.user_id)
        K.history(c, "resource", rid, None, "draft", ctx.user_id, "criado")
        ctx.audit(c, "content.resource_created", "resource", rid, {"slug": body.slug})
    return {"id": rid}


@A("PUT", "/v1/admin/content/resources/{id}", staff=EDIT, body=H.ResourceIn, summary="Edita recurso em RASCUNHO")
def resource_edit(ctx: Ctx, body: H.ResourceIn):
    with ctx.tx() as c:
        r = c.one("SELECT status, slug FROM kb_resources WHERE id = $1", ctx.path["id"])
        if not r:
            raise not_found("Recurso")
        if r["status"] != "draft" or r["slug"] != body.slug:
            raise ApiError(409, "not_draft", "Só rascunhos podem ser editados (e o slug não muda): crie uma nova versão")
        _check_doc(c, body.document_id)
        v = _res_vals(body, _cat(c, body.category), body.document_id)
        c.run("UPDATE kb_resources SET kind=$2, category_id=$3, title=$4, summary=$5, audience=$6::text[], visibility=$7, origin=$8, tags=$9::text[], url=$10, document_id=$11, template_schema=$12::jsonb,"
              " checklist_items=$13::jsonb, duration_min=$14, period_start=$15, period_end=$16, ods=$17::smallint[], territories=$18::text[], themes=$19::text[], ctx_keys=$20::text[], regulatory=$21,"
              " regulatory_source=$22, regulatory_date=$23, valid_until=$24, change_note=$25, review_every_days=$26, demo=$27 WHERE id = $1", ctx.path["id"], *v)
    return {"updated": True}


@A("POST", "/v1/admin/content/resources/{id}/new-version", staff=EDIT, body=H.ResourceIn, status=201, summary="Nova versão de um recurso publicado (a anterior fica no histórico como 'superseded')")
def resource_new_version(ctx: Ctx, body: H.ResourceIn):
    if not body.change_note:
        raise ApiError(422, "change_note_required", "Descreva a mudança (nota de versão)")
    with ctx.tx() as c:
        r = c.one("SELECT slug FROM kb_resources WHERE id = $1", ctx.path["id"])
        if not r or r["slug"] != body.slug:
            raise not_found("Recurso")
        if c.one("SELECT 1 FROM kb_resources WHERE slug = $1 AND status IN ('draft','review','approved')", r["slug"]):
            raise ApiError(409, "open_version", "Já existe uma versão em andamento deste recurso")
        n = c.scalar("SELECT max(version) + 1 FROM kb_resources WHERE slug = $1", r["slug"])
        _check_doc(c, body.document_id)
        rid = c.scalar(RES_INSERT, body.slug, n, *_res_vals(body, _cat(c, body.category), body.document_id), ctx.user_id)
        K.history(c, "resource", rid, None, "draft", ctx.user_id, body.change_note)
    return {"id": rid, "version": n}


@A("GET", "/v1/admin/content/resources", staff=EDIT + SUPPORT, query=H.AdminListQ)
def resource_list(ctx: Ctx, q: H.AdminListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, slug, version, kind, title, status, demo, origin, regulatory, valid_until, published_at, download_count FROM kb_resources WHERE ($1::text IS NULL OR status = $1)"
                       " ORDER BY created_at DESC LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


# ------------------------------------------------------------------------------------------------ FAQ
@A("POST", "/v1/admin/content/faqs", staff=EDIT, body=H.FaqIn, status=201, summary="Cria FAQ em rascunho (ou revisão de uma publicada via revises_id)")
def faq_create(ctx: Ctx, body: H.FaqIn):
    with ctx.tx() as c:
        if body.revises_id and not c.one("SELECT 1 FROM kb_faqs WHERE id = $1 AND status = 'published'", body.revises_id):
            raise ApiError(422, "invalid_revision", "A FAQ a revisar precisa estar publicada")
        fid = c.scalar("INSERT INTO kb_faqs(category_id, question, answer, audience, visibility, origin, tags, ctx_keys, related_article, revises_id, review_every_days, sort, demo, author_id)"
                       " VALUES ($1,$2,$3,$4::text[],$5,$6,$7::text[],$8::text[],$9,$10,$11,$12,$13,$14) RETURNING id::text", _cat(c, body.category), body.question, body.answer, body.audience,
                       body.visibility, body.origin, body.tags, body.ctx_keys, body.related_article, body.revises_id, body.review_every_days, body.sort, body.demo, ctx.user_id)
        K.history(c, "faq", fid, None, "draft", ctx.user_id, "criado" if not body.revises_id else "revisão de FAQ publicada")
    return {"id": fid}


@A("PUT", "/v1/admin/content/faqs/{id}", staff=EDIT, body=H.FaqIn, summary="Edita FAQ em rascunho")
def faq_edit(ctx: Ctx, body: H.FaqIn):
    with ctx.tx() as c:
        f = c.one("SELECT status FROM kb_faqs WHERE id = $1", ctx.path["id"])
        if not f:
            raise not_found("FAQ")
        if f["status"] != "draft":
            raise ApiError(409, "not_draft", "Só rascunhos podem ser editados: crie uma revisão")
        c.run("UPDATE kb_faqs SET category_id=$2, question=$3, answer=$4, audience=$5::text[], visibility=$6, origin=$7, tags=$8::text[], ctx_keys=$9::text[], related_article=$10,"
              " review_every_days=$11, sort=$12, demo=$13 WHERE id = $1", ctx.path["id"], _cat(c, body.category), body.question, body.answer, body.audience, body.visibility, body.origin,
              body.tags, body.ctx_keys, body.related_article, body.review_every_days, body.sort, body.demo)
    return {"updated": True}


@A("GET", "/v1/admin/content/faqs", staff=EDIT + SUPPORT, query=H.AdminListQ)
def faq_list(ctx: Ctx, q: H.AdminListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, question, status, demo, helpful_yes, helpful_no, revises_id::text AS revises_id FROM kb_faqs WHERE ($1::text IS NULL OR status = $1) ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                       q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


# ------------------------------------------------------------------------------------------------ cursos e trilhas
def _insert_course_tree(c, course_id: str, body: H.CourseIn) -> None:
    for mi, m in enumerate(body.modules, 1):
        mid = c.scalar("INSERT INTO course_modules(course_id, position, title, description) VALUES ($1,$2,$3,$4) RETURNING id::text", course_id, mi, m.title, m.description)
        for li, ls in enumerate(m.lessons, 1):
            if ls.kind == "quiz" and not ls.quiz:
                raise ApiError(422, "quiz_empty", f"A aula «{ls.title}» é um quiz e precisa de perguntas")
            for q in ls.quiz:
                if q.answer >= len(q.options):
                    raise ApiError(422, "quiz_answer", f"Gabarito inválido em «{ls.title}»")
            lid = c.scalar("INSERT INTO course_lessons(module_id, course_id, position, title, kind, body, video_url, captions_url, transcript, minutes, materials, quiz)"
                           " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12::jsonb) RETURNING id::text", mid, course_id, li, ls.title, ls.kind, ls.body, ls.video_url, ls.captions_url,
                           ls.transcript, ls.minutes, _j(ls.materials), _j([{"q": q.q, "options": q.options, "explanation": q.explanation} for q in ls.quiz]))
            if ls.quiz:
                c.run("INSERT INTO lesson_quiz_keys(lesson_id, answers) VALUES ($1,$2::int[])", lid, [q.answer for q in ls.quiz])


@A("POST", "/v1/admin/content/courses", staff=EDIT, body=H.CourseIn, status=201, summary="Cria curso (módulos, aulas, quiz com gabarito separado) em rascunho")
def course_create(ctx: Ctx, body: H.CourseIn):
    with ctx.tx() as c:
        if c.one("SELECT 1 FROM courses WHERE slug = $1", body.slug):
            raise ApiError(409, "slug_taken", "Slug já existe")
        cid = c.scalar("INSERT INTO courses(slug, title, summary, audience, visibility, origin, level, hours, pass_score, cert_enabled, tags, review_every_days, demo, author_id)"
                       " VALUES ($1,$2,$3,$4::text[],$5,$6,$7,$8,$9,$10,$11::text[],$12,$13,$14) RETURNING id::text", body.slug, body.title, body.summary, body.audience, body.visibility,
                       body.origin, body.level, body.hours, body.pass_score, body.cert_enabled, body.tags, body.review_every_days, body.demo, ctx.user_id)
        _insert_course_tree(c, cid, body)
        K.history(c, "course", cid, None, "draft", ctx.user_id, "criado")
        ctx.audit(c, "content.course_created", "course", cid, {"slug": body.slug})
    return {"id": cid}


@A("PUT", "/v1/admin/content/courses/{id}", staff=EDIT, body=H.CourseIn, summary="Substitui a estrutura de um curso em RASCUNHO/REVISÃO (cursos publicados: arquive e crie outro — limitação documentada)")
def course_edit(ctx: Ctx, body: H.CourseIn):
    with ctx.tx() as c:
        k = c.one("SELECT status, slug FROM courses WHERE id = $1 FOR UPDATE", ctx.path["id"])
        if not k:
            raise not_found("Curso")
        if k["status"] not in ("draft", "review") or k["slug"] != body.slug:
            raise ApiError(409, "not_editable", "Só cursos em rascunho/revisão podem ser editados (slug não muda)")
        c.run("DELETE FROM course_modules WHERE course_id = $1", ctx.path["id"])
        c.run("UPDATE courses SET title=$2, summary=$3, audience=$4::text[], visibility=$5, origin=$6, level=$7, hours=$8, pass_score=$9, cert_enabled=$10, tags=$11::text[], review_every_days=$12, demo=$13,"
              " status = 'draft' WHERE id = $1", ctx.path["id"], body.title, body.summary, body.audience, body.visibility, body.origin, body.level, body.hours, body.pass_score, body.cert_enabled,
              body.tags, body.review_every_days, body.demo)
        _insert_course_tree(c, ctx.path["id"], body)
    return {"updated": True}


@A("GET", "/v1/admin/content/courses", staff=EDIT + SUPPORT, query=H.AdminListQ)
def course_list(ctx: Ctx, q: H.AdminListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT k.id::text AS id, k.slug, k.title, k.status, k.demo, k.version, (SELECT count(*) FROM course_enrollments e WHERE e.course_id = k.id) AS enrollments,"
                       " (SELECT count(*) FROM course_enrollments e WHERE e.course_id = k.id AND e.completed_at IS NOT NULL) AS completions FROM courses k WHERE ($1::text IS NULL OR k.status = $1)"
                       " ORDER BY k.created_at DESC LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("POST", "/v1/admin/content/paths", staff=EDIT, body=H.PathIn, status=201, summary="Cria trilha de aprendizado (cursos/guias/recursos em ordem)")
def path_create(ctx: Ctx, body: H.PathIn):
    with ctx.tx() as c:
        pid = c.scalar("INSERT INTO learning_paths(slug, title, description, audience, visibility, items, demo, author_id) VALUES ($1,$2,$3,$4::text[],$5,$6::jsonb,$7,$8) RETURNING id::text",
                       body.slug, body.title, body.description, body.audience, body.visibility, _j(body.items), body.demo, ctx.user_id)
        K.history(c, "path", pid, None, "draft", ctx.user_id, "criada")
    return {"id": pid}


@A("POST", "/v1/admin/hub/certificates/{code}/revoke", staff=REVIEW, body=H.RevokeCertIn, summary="Revoga certificado de conclusão (motivo obrigatório, auditado)")
def cert_revoke(ctx: Ctx, body: H.RevokeCertIn):
    with ctx.tx() as c:
        n = c.run("UPDATE course_certificates SET revoked_at = now(), revoke_reason = $2 WHERE code = $1 AND revoked_at IS NULL", ctx.path["code"].upper(), body.reason)
        if not n:
            raise not_found("Certificado")
        ctx.audit(c, "content.certificate_revoked", "certificate", ctx.path["code"].upper(), {"reason": body.reason})
    return {"revoked": True}


# ------------------------------------------------------------------------------------------------ eventos
@A("POST", "/v1/admin/content/events", staff=EDIT, body=H.EventIn, status=201, summary="Cria evento em rascunho (link de acesso fica restrito às inscritas)")
def event_create(ctx: Ctx, body: H.EventIn):
    if body.modality != "online" and not body.location:
        raise ApiError(422, "location_required", "Informe o local do evento presencial/híbrido")
    with ctx.tx() as c:
        if c.one("SELECT 1 FROM hub_events WHERE slug = $1", body.slug):
            raise ApiError(409, "slug_taken", "Slug já existe")
        eid = c.scalar("INSERT INTO hub_events(slug, kind, title, description, starts_at, duration_min, speaker, modality, location, capacity, registration_open, audience, visibility, demo, author_id)"
                       " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::text[],$13,$14,$15) RETURNING id::text", body.slug, body.kind, body.title, body.description, body.starts_at,
                       body.duration_min, body.speaker, body.modality, body.location, body.capacity, body.registration_open, body.audience, body.visibility, body.demo, ctx.user_id)
        if body.join_url:
            c.run("INSERT INTO hub_event_links(event_id, join_url) VALUES ($1,$2)", eid, body.join_url)
        K.history(c, "event", eid, None, "draft", ctx.user_id, "criado")
        ctx.audit(c, "content.event_created", "event", eid, {"slug": body.slug})
    return {"id": eid}


@A("PATCH", "/v1/admin/content/events/{id}", staff=EDIT, body=H.EventPatchIn, summary="Atualiza evento (alterações em evento publicado ficam no histórico)")
def event_patch(ctx: Ctx, body: H.EventPatchIn):
    data = body.model_dump(exclude_unset=True)
    join = data.pop("join_url", None)
    status = data.pop("status", None)
    with ctx.tx() as c:
        e = c.one("SELECT status, title, slug FROM hub_events WHERE id = $1 FOR UPDATE", ctx.path["id"])
        if not e:
            raise not_found("Evento")
        if status == "cancelled" and e["status"] not in ("published", "approved"):
            raise ApiError(409, "invalid_transition", "Só eventos aprovados/publicados podem ser cancelados")
        if status == "completed" and e["status"] != "published":
            raise ApiError(409, "invalid_transition", "Só eventos publicados podem ser concluídos")
        if data:
            sets, vals = [], [ctx.path["id"]]
            for k, v in data.items():
                vals.append(v)
                sets.append(f"{k} = ${len(vals)}")
            c.run(f"UPDATE hub_events SET {', '.join(sets)}, updated_at = now() WHERE id = $1", *vals)
        if status:
            c.run("UPDATE hub_events SET status = $2, updated_at = now() WHERE id = $1", ctx.path["id"], status)
            K.history(c, "event", ctx.path["id"], e["status"], status, ctx.user_id, "ação operacional")
            if status == "cancelled":
                for r in c.query("SELECT user_id::text AS user_id, org_id::text AS org_id FROM hub_event_registrations WHERE event_id = $1 AND status IN ('registered','waitlist') AND org_id IS NOT NULL", ctx.path["id"]):
                    hub.notify_user(c, r["user_id"], r["org_id"], "events", f"Evento cancelado: {e['title']}", "O evento foi cancelado pela organização.", f"/ajuda/eventos/{e['slug']}")
        if join:
            c.run("INSERT INTO hub_event_links(event_id, join_url) VALUES ($1,$2) ON CONFLICT (event_id) DO UPDATE SET join_url = EXCLUDED.join_url", ctx.path["id"], join)
        ctx.audit(c, "content.event_updated", "event", ctx.path["id"], {"fields": sorted(data) + ([status] if status else [])})
    return {"updated": True}


@A("POST", "/v1/admin/content/events/{id}/attendance", staff=EDIT, body=H.AttendanceIn, summary="Registra presença (a avaliação só é liberada a quem participou)")
def event_attendance(ctx: Ctx, body: H.AttendanceIn):
    with ctx.tx() as c:
        n = c.run("UPDATE hub_event_registrations SET attended = true WHERE event_id = $1 AND user_id = ANY($2::uuid[]) AND status = 'registered'", ctx.path["id"], body.user_ids)
    return {"marked": n}


@A("GET", "/v1/admin/content/events/{id}/registrations", staff=EDIT + SUPPORT, summary="Inscritas (dados mínimos: nome, organização, estado, presença)")
def event_regs(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT g.user_id::text AS user_id, u.full_name, o.legal_name AS org, g.status, g.attended, g.satisfaction FROM hub_event_registrations g JOIN users u ON u.id = g.user_id"
                                 " LEFT JOIN organizations o ON o.id = g.org_id WHERE g.event_id = $1 ORDER BY g.created_at", ctx.path["id"])}


@A("POST", "/v1/admin/content/events/{id}/recording-to-resource", staff=EDIT, status=201, summary="Transforma a gravação do evento em recurso da biblioteca (rascunho, sujeito a revisão)")
def event_recording(ctx: Ctx):
    with ctx.tx() as c:
        e = c.one("SELECT slug, title, recording_url, status, audience FROM hub_events WHERE id = $1", ctx.path["id"])
        if not e or e["status"] != "completed" or not e["recording_url"]:
            raise ApiError(409, "no_recording", "O evento precisa estar concluído e ter a URL da gravação")
        slug = f"gravacao-{e['slug']}"[:100]
        if c.one("SELECT 1 FROM kb_resources WHERE slug = $1", slug):
            raise ApiError(409, "already_converted", "A gravação já virou recurso")
        rid = c.scalar("INSERT INTO kb_resources(slug, kind, title, summary, audience, visibility, origin, url, author_id) VALUES ($1,'video',$2,$3,$4::text[],'authenticated','official',$5,$6) RETURNING id::text",
                       slug, f"Gravação: {e['title']}", "Gravação do evento.", e["audience"], e["recording_url"], ctx.user_id)
        c.run("UPDATE hub_events SET recording_resource_id = $2 WHERE id = $1", ctx.path["id"], rid)
        K.history(c, "resource", rid, None, "draft", ctx.user_id, "criado a partir de gravação de evento")
    return {"resource_id": rid}


# ------------------------------------------------------------------------------------------------ suporte (fila)
@A("GET", "/v1/admin/support/tickets", staff=SUPPORT, permission="support.read", query=H.TicketQ, summary="Fila de chamados (por estado, prioridade e atraso de SLA)")
def queue(ctx: Ctx, q: H.TicketQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT t.id::text AS id, t.number, t.category, t.priority, t.status, t.subject, t.created_at, t.first_response_due, t.resolution_due, t.escalated_at, t.recurring,"
                       " t.assigned_to::text AS assigned_to, u.full_name AS requester, (t.status NOT IN ('resolved','closed') AND t.resolution_due < now()) AS overdue FROM support_tickets t JOIN users u ON u.id = t.user_id"
                       " WHERE (($1::text IS NULL AND true) OR ($1 = 'active' AND t.status NOT IN ('resolved','closed')) OR t.status = $1) AND ($2::text IS NULL OR t.priority = $2)"
                       " AND (NOT $3 OR (t.status NOT IN ('resolved','closed') AND t.resolution_due < now())) ORDER BY CASE t.priority WHEN 'critical' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, t.created_at LIMIT $4 OFFSET $5",
                       q.status, q.priority, q.overdue, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("GET", "/v1/admin/support/tickets/{ticket_id}", staff=SUPPORT)
def staff_ticket_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return hub.ticket_get(c, ctx.path["ticket_id"], staff=True)


@A("POST", "/v1/admin/support/tickets/{ticket_id}/messages", staff=SUPPORT, body=H.TicketReplyIn, status=201, summary="Responde (ou anota internamente) um chamado")
def staff_reply(ctx: Ctx, body: H.TicketReplyIn):
    with ctx.tx() as c:
        out = hub.ticket_reply(c, ctx.path["ticket_id"], author_id=ctx.user_id, body=body.body, staff=True, internal=body.internal, document_ids=body.document_ids, org_id=None)
        ctx.audit(c, "support.staff_reply", "ticket", ctx.path["ticket_id"], {"internal": body.internal})
    return out


@A("PATCH", "/v1/admin/support/tickets/{ticket_id}", staff=SUPPORT, body=H.TicketStaffIn, summary="Estado, prioridade (recalcula SLA) e responsável")
def staff_ticket_update(ctx: Ctx, body: H.TicketStaffIn):
    with ctx.tx() as c:
        out = hub.ticket_staff_update(c, ctx.path["ticket_id"], status=body.status, priority=body.priority, assigned_to=body.assigned_to, assign_set=body.assign)
        ctx.audit(c, "support.ticket_updated", "ticket", ctx.path["ticket_id"], {"status": body.status, "priority": body.priority})
    return out


@A("POST", "/v1/admin/support/tickets/{ticket_id}/to-article", staff=EDIT + SUPPORT, summary="Vincula o chamado a um artigo (o assunto deixa de contar como recorrente sem base)")
def ticket_to_article(ctx: Ctx):
    slug = ctx.request.query_params.get("slug")
    with ctx.tx() as c:
        a = c.one("SELECT id::text AS id FROM kb_articles WHERE slug = $1", slug or "")
        if not a:
            raise not_found("Artigo")
        c.run("UPDATE support_tickets SET kb_article_id = $2, recurring = true WHERE id = $1", ctx.path["ticket_id"], a["id"])
    return {"linked": True}


@A("GET", "/v1/admin/support/sla", staff=SUPPORT, summary="SLA por prioridade (valores iniciais são hipótese operacional, configuráveis)")
def sla_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"items": c.query("SELECT priority, first_response_minutes, resolution_minutes, escalate_after_minutes, updated_at FROM support_sla ORDER BY first_response_minutes"),
                "status": "HIPÓTESE — validar com a equipe de suporte"}


@A("PUT", "/v1/admin/support/sla/{priority}", body=H.SlaIn, summary="Ajusta o SLA de uma prioridade (administradores)")
def sla_put(ctx: Ctx, body: H.SlaIn):
    if ctx.path["priority"] not in hub.PRIORITIES:
        raise not_found("Prioridade")
    with ctx.tx() as c:
        c.run("UPDATE support_sla SET first_response_minutes=$2, resolution_minutes=$3, escalate_after_minutes=$4, updated_by=$5, updated_at=now() WHERE priority=$1",
              ctx.path["priority"], body.first_response_minutes, body.resolution_minutes, body.escalate_after_minutes, ctx.user_id)
        ctx.audit(c, "support.sla_updated", "sla", ctx.path["priority"], body.model_dump())
    return {"updated": True}


# ------------------------------------------------------------------------------------------------ parcerias (CRM), demonstrações, testes, boletim, analytics
@A("GET", "/v1/admin/hub/partnerships", query=H.AdminListQ, summary="Pipeline de parcerias")
def partnership_list(ctx: Ctx, q: H.AdminListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, org_name, contact_name, contact_email::text AS contact_email, kind, status, owner_id::text AS owner_id, target_date, last_activity_at, created_at FROM partnership_requests"
                       " WHERE ($1::text IS NULL OR status = $1) ORDER BY last_activity_at DESC LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("GET", "/v1/admin/hub/partnerships/{id}")
def partnership_get(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        r = c.one("SELECT id::text AS id, org_name, contact_name, contact_email::text AS contact_email, contact_phone, kind, objective, proposal, territory, audience, resources_offered, counterpart,"
                  " target_date, status, owner_id::text AS owner_id, consent_at, consent_version, created_at FROM partnership_requests WHERE id = $1", ctx.path["id"])
        if not r:
            raise not_found("Pedido")
        r["activities"] = c.query("SELECT kind, body, from_status, to_status, created_at FROM partnership_activities WHERE request_id = $1 ORDER BY created_at", r["id"])
        return r


@A("POST", "/v1/admin/hub/partnerships/{id}/move", body=H.PartnershipMoveIn, summary="Move no pipeline (histórico) e define responsável; 'ativa' cria o registro de parceria")
def partnership_move(ctx: Ctx, body: H.PartnershipMoveIn):
    with ctx.tx() as c:
        out = hub.partnership_move(c, ctx.path["id"], to=body.to, actor=ctx.user_id, note=body.note)
        if body.owner_id:
            c.run("UPDATE partnership_requests SET owner_id = $2 WHERE id = $1", ctx.path["id"], body.owner_id)
        ctx.audit(c, "partnership.moved", "partnership_request", ctx.path["id"], {"to": body.to})
    return out


@A("POST", "/v1/admin/hub/partnerships/{id}/notes", body=H.NoteIn, status=201)
def partnership_note(ctx: Ctx, body: H.NoteIn):
    with ctx.tx() as c:
        if not c.one("SELECT 1 FROM partnership_requests WHERE id = $1", ctx.path["id"]):
            raise not_found("Pedido")
        c.run("INSERT INTO partnership_activities(request_id, kind, body, author_id) VALUES ($1,'note',$2,$3)", ctx.path["id"], body.body, ctx.user_id)
        c.run("UPDATE partnership_requests SET last_activity_at = now() WHERE id = $1", ctx.path["id"])
    return {"created": True}


@A("GET", "/v1/admin/hub/demo-requests", query=H.AdminListQ)
def demo_list(ctx: Ctx, q: H.AdminListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT id::text AS id, org_name, contact_name, contact_email::text AS contact_email, audience_kind, org_size, interest, preferred_slots, status, scheduled_at, meeting_url, created_at"
                       " FROM demo_requests WHERE ($1::text IS NULL OR status = $1) ORDER BY created_at DESC LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("POST", "/v1/admin/hub/demo-requests/{id}/handle", body=H.DemoHandleIn, summary="Agenda/conclui/cancela demonstração e avisa a pessoa por e-mail")
def demo_handle(ctx: Ctx, body: H.DemoHandleIn):
    if body.status == "scheduled" and not body.scheduled_at:
        raise ApiError(422, "scheduled_at_required", "Informe data e hora")
    with ctx.tx() as c:
        d = c.one("SELECT contact_email::text AS email, contact_name FROM demo_requests WHERE id = $1", ctx.path["id"])
        if not d:
            raise not_found("Pedido")
        c.run("UPDATE demo_requests SET status = $2, scheduled_at = coalesce($3, scheduled_at), meeting_url = coalesce($4, meeting_url), handled_by = $5 WHERE id = $1",
              ctx.path["id"], body.status, body.scheduled_at, body.meeting_url, ctx.user_id)
        ctx.audit(c, "demo.handled", "demo_request", ctx.path["id"], {"status": body.status})
    if body.status == "scheduled":
        hub.send_mail(ctx.app, None, to=d["email"], subject="[Impacto] Demonstração agendada",
                      text=f"Olá, {d['contact_name']}! Sua demonstração foi agendada para {body.scheduled_at:%d/%m/%Y %H:%M}." + (f"\nLink: {body.meeting_url}" if body.meeting_url else "") + "\n")
    return {"updated": True}


@A("GET", "/v1/admin/hub/trial-requests", query=H.AdminListQ)
def trial_req_list(ctx: Ctx, q: H.AdminListQ):
    with ctx.tx(readonly=True) as c:
        rows = c.query("SELECT r.id::text AS id, r.org_id::text AS org_id, o.legal_name, r.org_kind, r.users_count, r.purpose, r.modules, r.period_days, r.responsible, r.status, r.created_at,"
                       " r.decision_reason, r.outcome, (SELECT status FROM org_trials t WHERE t.org_id = r.org_id) AS current_trial FROM trial_requests r JOIN organizations o ON o.id = r.org_id"
                       " WHERE ($1::text IS NULL OR r.status = $1) ORDER BY r.created_at DESC LIMIT $2 OFFSET $3", q.status, q.limit + 1, q.offset)
    return page(rows, q.limit, q.offset)


@A("POST", "/v1/admin/hub/trial-requests/{id}/decide", body=H.DecisionIn, summary="Decide a solicitação de teste (motivo obrigatório): inicia/estende o trial existente ou recusa; nunca automático")
def trial_req_decide(ctx: Ctx, body: H.DecisionIn):
    with ctx.system_tx() as c:
        out = hub.trial_request_decide(c, ctx.settings, ctx.path["id"], admin_id=ctx.user_id, approve=body.approve, reason=body.reason)
        ctx.audit(c, "trial.request_decided", "trial_request", ctx.path["id"], {"approve": body.approve, "outcome": out["outcome"]})
    return out


@A("GET", "/v1/admin/hub/trials", summary="Painel de testes: solicitações, ativos, vencendo, conversão e uso por organização")
def trials_dash(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return hub.trial_dashboard(c)


@A("GET", "/v1/admin/hub/analytics", staff=EDIT + SUPPORT, summary="Analytics da Central: buscas, lacunas, utilidade, chamados, academia, eventos, parcerias")
def analytics(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return hub.knowledge_analytics(c)


@A("GET", "/v1/admin/hub/newsletter", summary="Inscrições do boletim (contagens; e-mails só para administradores)")
def newsletter_admin(ctx: Ctx):
    with ctx.tx(readonly=True) as c:
        return {"by_status": c.query("SELECT status, frequency, count(*) AS n FROM newsletter_subscriptions GROUP BY 1, 2 ORDER BY 1, 2"),
                "bulletins": c.query("SELECT slug, title, published_at FROM kb_resources WHERE kind = 'bulletin' AND status = 'published' ORDER BY published_at DESC LIMIT 20")}


@A("POST", "/v1/admin/hub/newsletter/dispatch", summary="Dispara agora o envio do boletim às inscritas devidas (o worker também faz)")
def newsletter_dispatch(ctx: Ctx):
    if not _is_admin(ctx):
        raise ApiError(403, "admin_only", "Somente administradores da plataforma")
    with ctx.system_tx() as c:
        out = hub.bulletin_dispatch(ctx.app, c)
        ctx.audit(c, "newsletter.dispatched", "newsletter", None, out)
    return out

