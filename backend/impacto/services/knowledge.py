"""Central de Conhecimento: busca híbrida, detalhe com ação, ajuda contextual, recomendações, assistente ancorado e fluxo editorial.

Regras de verdade (CONTENT_GOVERNANCE.md): conteúdo institucional só é publicado após revisão de OUTRA pessoa (quatro olhos, também no banco);
versões publicadas são imutáveis; origem (oficial × educacional × terceiros) e o rótulo DEMO são sempre exibidos; conteúdo regulatório exige fonte
e data e é sinalizado quando vencido; o assistente só responde com a base publicada, cita a fonte e, sem base suficiente, diz isso e oferece abrir chamado.
Plano/assinatura nunca influencia busca ou recomendação."""
from __future__ import annotations

import json
import logging

from ..engines.knowledge import search as KS
from ..http import ApiError, not_found
from ..clock import today as _hoje_utc  # data do produto é UTC; ver impacto/clock.py

ORIGIN_LABEL = {"official": "Informação oficial da plataforma", "educational": "Material educacional", "third_party": "Conteúdo de terceiros"}
DEMO_LABEL = "Exemplo / rascunho — não é documento oficial"
TYPE_PATH = {"article": "/ajuda/{slug}", "faq": "/ajuda/faq/{id}", "resource": "/ajuda/biblioteca/{slug}", "course": "/ajuda/academia/{slug}", "event": "/ajuda/eventos/{slug}"}

STALE_SQL = ("(coalesce({a}.last_reviewed_at, {a}.published_at) + make_interval(days => {a}.review_every_days) < now())")


def _link(kind: str, row: dict) -> str:
    return TYPE_PATH[kind].format(slug=row.get("slug"), id=row.get("id"))


def _label(row: dict) -> dict:
    return {"origin": row.get("origin"), "origin_label": ORIGIN_LABEL.get(row.get("origin") or "official"), "demo": bool(row.get("demo")),
            "demo_label": DEMO_LABEL if row.get("demo") else None}


def log(c, kind: str, *, target_type: str | None = None, target_id: str | None = None, q: str | None = None, concepts: list[str] | None = None,
        count: int | None = None, ctx_key: str | None = None) -> None:
    """Analytics sem texto livre (hash + tópicos). Falhas de log nunca derrubam a requisição."""
    try:
        c.run("SELECT kb_log($1,$2,$3::uuid,$4,$5::text[],$6,$7)", kind, target_type, target_id, KS.q_hash(q) if q else None, concepts or [], count, ctx_key)
    except Exception:  # noqa: BLE001
        logging.getLogger("impacto.knowledge").warning("kb_log_failed")


# ------------------------------------------------------------------------------------------------ busca híbrida
def _item(kind_type: str, row: dict, parsed: dict, *, ctx_key: str | None, user_kind: str | None, kind_for_bonus: str, text: str, summary: str | None) -> dict:
    sc = KS.score(parsed, fts=float(row.get("fts") or 0), title_sim=float(row.get("sim") or 0), kind=kind_for_bonus, item_text=text, tags=row.get("tags") or [],
                  ctx_keys=row.get("ctx_keys") or [], ctx_key=ctx_key, audience=row.get("audience") or [], user_kind=user_kind)
    out = {"type": kind_type, "id": row["id"], "slug": row.get("slug"), "title": row["title"], "summary": summary, "kind": row.get("kind"),
           "link": _link(kind_type, row), "score": sc["score"], "why": sc["why"], "needs_review": bool(row.get("needs_review")),
           "est_minutes": row.get("est_minutes"), "category": row.get("category_name"), "audience": row.get("audience") or []}
    out.update(_label(row))
    return out


def search(c, query: str, *, user_kind: str | None, ctx_key: str | None = None, types: set[str] | None = None, limit: int = 20,
           audience: str | None = None, category: str | None = None, record: bool = True) -> dict:
    parsed = KS.parse(query)
    types = types or {"article", "faq", "resource", "course", "event"}
    ts, nq = parsed["tsquery"], parsed["norm"]
    items: list[dict] = []

    def conds(doc_col: str, title_col: str, ctxcol: str | None, args: list) -> str:
        parts = []
        if ts:
            args.append(ts)
            parts.append(f"{doc_col} @@ to_tsquery('pt_unaccent', ${len(args)})")
        if nq:
            args.append(nq)
            parts.append(f"word_similarity(${len(args)}, {title_col}) > 0.45")
        if ctx_key and ctxcol:
            args.append(ctx_key)
            parts.append(f"${len(args)}::text = ANY({ctxcol})")
        return "(" + " OR ".join(parts) + ")" if parts else "false"

    def rank(doc_col: str, title_col: str, args_ts_idx: int | None, args_nq_idx: int | None) -> tuple[str, str]:
        fts = f"ts_rank_cd({doc_col}, to_tsquery('pt_unaccent', ${args_ts_idx}), 32)::float" if args_ts_idx else "0::float"
        sim = f"word_similarity(${args_nq_idx}, {title_col})::float" if args_nq_idx else "0::float"
        return fts, sim

    def idxs(args: list) -> tuple[int | None, int | None]:
        ti = args.index(ts) + 1 if ts and ts in args else None
        ni = args.index(nq) + 1 if nq and nq in args else None
        return ti, ni

    if "article" in types:
        args: list = []
        where = conds("a.search_doc", "a.title_norm", "a.ctx_keys", args)
        ti, ni = idxs(args)
        fts, sim = rank("a.search_doc", "a.title_norm", ti, ni)
        extra = ""
        if category:
            args.append(category)
            extra = f" AND cat.slug = ${len(args)}"
        rows = c.query(f"SELECT a.id::text AS id, a.slug, a.kind, a.title, a.summary, a.tags, a.ctx_keys, a.audience, a.origin, a.est_minutes, a.demo, cat.name AS category_name,"
                       f" {STALE_SQL.format(a='a')} OR (v.regulatory AND v.valid_until < current_date) AS needs_review, {fts} AS fts, {sim} AS sim"
                       f" FROM kb_articles a JOIN kb_article_versions v ON v.id = a.live_version_id LEFT JOIN kb_categories cat ON cat.id = a.category_id"
                       f" WHERE a.live_version_id IS NOT NULL AND {where}{extra} LIMIT 60", *args)
        for r in rows:
            items.append(_item("article", r, parsed, ctx_key=ctx_key, user_kind=user_kind, kind_for_bonus=r["kind"], text=f"{r['title']} {r['summary'] or ''}", summary=r["summary"]))
    if "faq" in types:
        args = []
        where = conds("f.search_doc", "f.title_norm", "f.ctx_keys", args)
        ti, ni = idxs(args)
        fts, sim = rank("f.search_doc", "f.title_norm", ti, ni)
        rows = c.query(f"SELECT f.id::text AS id, NULL::text AS slug, 'faq' AS kind, f.question AS title, left(f.answer, 240) AS summary, f.tags, f.ctx_keys, f.audience, f.origin,"
                       f" NULL::int AS est_minutes, f.demo, cat.name AS category_name, {STALE_SQL.format(a='f')} AS needs_review, f.answer, {fts} AS fts, {sim} AS sim"
                       f" FROM kb_faqs f LEFT JOIN kb_categories cat ON cat.id = f.category_id WHERE f.status = 'published' AND {where} LIMIT 40", *args)
        for r in rows:
            items.append(_item("faq", r, parsed, ctx_key=ctx_key, user_kind=user_kind, kind_for_bonus="faq", text=f"{r['title']} {r['answer']}", summary=r["summary"]))
    if "resource" in types:
        args = []
        where = conds("r.search_doc", "r.title_norm", "r.ctx_keys", args)
        ti, ni = idxs(args)
        fts, sim = rank("r.search_doc", "r.title_norm", ti, ni)
        rows = c.query(f"SELECT r.id::text AS id, r.slug, r.kind, r.title, r.summary, r.tags, r.ctx_keys, r.audience, r.origin, r.duration_min AS est_minutes, r.demo,"
                       f" cat.name AS category_name, ({STALE_SQL.format(a='r')} OR (r.regulatory AND r.valid_until < current_date)) AS needs_review, {fts} AS fts, {sim} AS sim"
                       f" FROM kb_resources r LEFT JOIN kb_categories cat ON cat.id = r.category_id WHERE r.status = 'published' AND {where} LIMIT 40", *args)
        for r in rows:
            items.append(_item("resource", r, parsed, ctx_key=ctx_key, user_kind=user_kind, kind_for_bonus=r["kind"], text=f"{r['title']} {r['summary'] or ''}", summary=r["summary"]))
    if "course" in types:
        args = []
        where = conds("k.search_doc", "k.title_norm", None, args)
        ti, ni = idxs(args)
        fts, sim = rank("k.search_doc", "k.title_norm", ti, ni)
        rows = c.query(f"SELECT k.id::text AS id, k.slug, 'course' AS kind, k.title, k.summary, k.tags, '{{}}'::text[] AS ctx_keys, k.audience, k.origin, round(k.hours * 60)::int AS est_minutes,"
                       f" k.demo, NULL::text AS category_name, false AS needs_review, {fts} AS fts, {sim} AS sim FROM courses k WHERE k.status = 'published' AND {where} LIMIT 30", *args)
        for r in rows:
            items.append(_item("course", r, parsed, ctx_key=ctx_key, user_kind=user_kind, kind_for_bonus="course", text=f"{r['title']} {r['summary'] or ''}", summary=r["summary"]))
    if "event" in types and nq:
        args = [ts or nq, nq]
        rows = c.query("SELECT e.id::text AS id, e.slug, e.kind, e.title, left(e.description, 240) AS summary, '{}'::text[] AS tags, '{}'::text[] AS ctx_keys, e.audience,"
                       " 'official' AS origin, e.duration_min AS est_minutes, e.demo, NULL::text AS category_name, false AS needs_review, e.starts_at,"
                       " ts_rank_cd(to_tsvector('pt_unaccent', e.title || ' ' || coalesce(e.description, '')), to_tsquery('pt_unaccent', $1), 32)::float AS fts,"
                       " word_similarity($2, lower(unaccent(e.title)))::float AS sim FROM hub_events e WHERE e.status IN ('published','completed')"
                       " AND (to_tsvector('pt_unaccent', e.title || ' ' || coalesce(e.description, '')) @@ to_tsquery('pt_unaccent', $1) OR word_similarity($2, lower(unaccent(e.title))) > 0.45) LIMIT 20",
                       *args) if ts else []
        for r in rows:
            it = _item("event", r, parsed, ctx_key=ctx_key, user_kind=user_kind, kind_for_bonus="event", text=f"{r['title']} {r['summary'] or ''}", summary=r["summary"])
            it["starts_at"] = r["starts_at"]
            items.append(it)
    keep = [i for i in items if i["score"] >= KS.MIN_SCORE or (ctx_key and "relacionado à tela em que você está" in i["why"])]
    keep.sort(key=lambda i: (-i["score"], i["title"]))
    if audience:
        keep = [i for i in keep if not i["audience"] or audience in i["audience"]]
    facets: dict[str, int] = {}
    for i in keep:
        facets[i["type"]] = facets.get(i["type"], 0) + 1
    result = {"query": parsed["q"], "engine": parsed["engine"], "topics": parsed["topic_labels"], "items": keep[:limit], "total": len(keep), "facets": facets,
              "semantic": "vocabulário de tópicos (sem embeddings)"}
    if record and (parsed["q"] or ctx_key):
        log(c, "search" if keep else "search_empty", q=parsed["q"], concepts=parsed["topics"], count=len(keep), ctx_key=ctx_key)
    if not keep:
        result["empty"] = {"message": "Não encontramos conteúdo para esta busca.", "suggest": ["Tente palavras mais simples", "Veja os guias por assunto", "Abra um chamado"]}
    return result


def contextual(c, ctx_key: str, user_kind: str | None, limit: int = 6) -> dict:
    """Ajuda contextual de uma tela/campo (ex.: project.budget): artigos, FAQs e modelos mapeados + botão de ajuda."""
    arts = c.query("SELECT a.id::text AS id, a.slug, a.kind, a.title, a.summary, a.est_minutes, a.origin, a.demo, a.audience FROM kb_articles a"
                   " WHERE a.live_version_id IS NOT NULL AND $1 = ANY(a.ctx_keys) ORDER BY (CASE WHEN $2::text = ANY(a.audience) THEN 0 ELSE 1 END), a.title LIMIT $3",
                   ctx_key, user_kind, limit)
    faqs = c.query("SELECT f.id::text AS id, f.question AS title, f.answer, f.origin, f.demo FROM kb_faqs f WHERE f.status = 'published' AND $1 = ANY(f.ctx_keys) ORDER BY f.sort LIMIT $2", ctx_key, limit)
    res = c.query("SELECT r.id::text AS id, r.slug, r.kind, r.title, r.summary, r.origin, r.demo FROM kb_resources r WHERE r.status = 'published' AND $1 = ANY(r.ctx_keys) ORDER BY r.title LIMIT $2", ctx_key, limit)
    log(c, "ctx_open", ctx_key=ctx_key)
    return {"ctx_key": ctx_key,
            "articles": [{**a, "link": _link("article", a), **_label(a)} for a in arts],
            "faqs": [{**f, "link": _link("faq", f), **_label(f)} for f in faqs],
            "resources": [{**r, "link": _link("resource", r), **_label(r)} for r in res],
            "help": {"label": "Preciso de ajuda", "ticket": {"page": ctx_key.split(".")[0], "field": ctx_key}}}


# ------------------------------------------------------------------------------------------------ artigo/guia com ação
def _res_cards(c, slugs: list[str]) -> list[dict]:
    if not slugs:
        return []
    rows = c.query("SELECT r.id::text AS id, r.slug, r.kind, r.title, r.summary, r.origin, r.demo, (r.template_schema IS NOT NULL) AS fillable,"
                   " (r.document_id IS NOT NULL OR r.url IS NOT NULL) AS downloadable FROM kb_resources r WHERE r.status = 'published' AND r.slug = ANY($1::text[])", slugs)
    return [{**r, "link": _link("resource", r), **_label(r)} for r in rows]


def get_article(c, slug: str, *, user_id: str | None) -> dict:
    a = c.one("SELECT a.id::text AS id, a.slug, a.kind, a.audience, a.visibility, a.origin, a.tags, a.ctx_keys, a.est_minutes, a.required_docs, a.action_label, a.action_link,"
              " a.related_articles, a.related_resources, a.related_courses, a.demo, a.published_at, a.last_reviewed_at, a.review_every_days, cat.slug AS category_slug,"
              " cat.name AS category_name, v.version, v.title, v.summary, v.body, v.steps, v.checklist, v.common_mistakes, v.refs, v.regulatory, v.regulatory_source,"
              " v.regulatory_date, v.valid_until, v.author_id::text AS author_id, v.approved_by::text AS reviewer_id, v.approved_at"
              " FROM kb_articles a JOIN kb_article_versions v ON v.id = a.live_version_id LEFT JOIN kb_categories cat ON cat.id = a.category_id WHERE a.slug = $1 AND a.live_version_id IS NOT NULL", slug)
    if not a:
        raise not_found("Conteúdo")
    due = (a["last_reviewed_at"] or a["published_at"])
    overdue = bool(due and (_hoje_utc() - due.date()).days > a["review_every_days"])
    expired = bool(a["regulatory"] and a["valid_until"] and a["valid_until"] < _hoje_utc())
    a["needs_review"] = overdue or expired
    a["review_notice"] = ("Este conteúdo regulatório está com a validade vencida ou a revisão em atraso. Confirme a regra vigente na fonte oficial antes de agir." if a["regulatory"] and a["needs_review"]
                          else ("Revisão necessária — este conteúdo pode estar desatualizado." if a["needs_review"] else None))
    a.update(_label(a))
    a["resources"] = _res_cards(c, a["related_resources"])
    a["courses"] = c.query("SELECT slug, title, hours FROM courses WHERE status = 'published' AND slug = ANY($1::text[])", a["related_courses"])
    a["related"] = c.query("SELECT slug, title, summary FROM kb_articles WHERE live_version_id IS NOT NULL AND slug = ANY($1::text[])", a["related_articles"])
    a["checklist_progress"] = []
    a["my_feedback"] = None
    if user_id:
        cp = c.one("SELECT checked FROM kb_checklist_progress WHERE user_id = $1 AND scope = $2 AND project_id IS NULL", user_id, f"article:{slug}")
        a["checklist_progress"] = cp["checked"] if cp else []
        a["my_feedback"] = c.one("SELECT helpful, reason, comment FROM kb_feedback WHERE user_id = $1 AND target_type = 'article' AND target_id = $2", user_id, a["id"])
    a["help"] = {"label": "Preciso de ajuda", "context": {"page": f"ajuda/{slug}", "article": slug}}
    a["structured_data"] = _structured_data(a)
    a["seo"] = {"index": a["visibility"] == "public" and not a["demo"], "title": a["title"], "description": (a["summary"] or "")[:160]}
    log(c, "view", target_type="article", target_id=a["id"])
    return a


def _structured_data(a: dict) -> dict | None:
    """JSON-LD (schema.org) só para conteúdo público; HowTo quando há passos."""
    if a["visibility"] != "public" or a["demo"]:
        return None
    base = {"@context": "https://schema.org", "name": a["title"], "description": a["summary"], "dateModified": (a["last_reviewed_at"] or a["published_at"]).isoformat() if (a["last_reviewed_at"] or a["published_at"]) else None}
    steps = a["steps"] or []
    if steps:
        return {**base, "@type": "HowTo", "step": [{"@type": "HowToStep", "name": s.get("title"), "text": s.get("text")} for s in steps]}
    return {**base, "@type": "Article", "headline": a["title"]}


# ------------------------------------------------------------------------------------------------ feedback e checklists
def set_feedback(c, *, user_id: str, org_id: str | None, target_type: str, target_id: str, helpful: bool, reason: str | None, comment: str | None) -> dict:
    exists = {"article": "SELECT 1 FROM kb_articles WHERE id = $1 AND live_version_id IS NOT NULL", "faq": "SELECT 1 FROM kb_faqs WHERE id = $1 AND status = 'published'",
              "resource": "SELECT 1 FROM kb_resources WHERE id = $1 AND status = 'published'", "course": "SELECT 1 FROM courses WHERE id = $1 AND status = 'published'",
              "lesson": "SELECT 1 FROM course_lessons WHERE id = $1", "event": "SELECT 1 FROM hub_events WHERE id = $1 AND status IN ('published','completed')"}[target_type]
    if not c.one(exists, target_id):
        raise not_found("Conteúdo")
    c.run("INSERT INTO kb_feedback(user_id, org_id, target_type, target_id, helpful, reason, comment) VALUES ($1,$2,$3,$4,$5,$6,$7)"
          " ON CONFLICT (user_id, target_type, target_id) DO UPDATE SET helpful = EXCLUDED.helpful, reason = EXCLUDED.reason, comment = EXCLUDED.comment, updated_at = now()",
          user_id, org_id, target_type, target_id, helpful, None if helpful else reason, comment)
    return {"recorded": True, "offer_support": (not helpful and reason in ("need_support", "not_found"))}


def set_checklist(c, *, user_id: str, org_id: str | None, scope: str, project_id: str | None, checked: list[int]) -> dict:
    checked = sorted({i for i in checked if 0 <= i < 500})
    c.run("INSERT INTO kb_checklist_progress(user_id, org_id, scope, project_id, checked) VALUES ($1,$2,$3,$4,$5::int[])"
          " ON CONFLICT (user_id, scope, coalesce(project_id, '00000000-0000-0000-0000-000000000000'::uuid)) DO UPDATE SET checked = EXCLUDED.checked, updated_at = now()",
          user_id, org_id, scope, project_id, checked)
    return {"scope": scope, "checked": checked}


# ------------------------------------------------------------------------------------------------ assistente ancorado (sem IA generativa)
def assistant(c, question: str, *, user_kind: str | None, ctx_key: str | None) -> dict:
    """Responde SÓ com a base publicada (extrativo), cita a fonte e recusa quando não há base suficiente. `ai_used` é sempre falso: nenhum modelo gera texto."""
    res = search(c, question, user_kind=user_kind, ctx_key=ctx_key, types={"article", "faq"}, limit=5, record=False)
    top = [i for i in res["items"] if i["score"] >= KS.ANSWER_MIN]
    out = {"question": question[:300], "grounded": True, "ai_used": False, "engine": res["engine"], "human_review_required": False}
    if not top:
        out.update({"answer": None, "message": "Não encontrei informação suficiente na base oficial.", "actions": [{"label": "Abrir chamado", "link": "/ajuda/suporte/novo"}], "sources": []})
        log(c, "assistant_empty", q=question, concepts=res["topics"] and KS.parse(question)["topics"], count=0, ctx_key=ctx_key)
        return out
    best = top[0]
    if best["type"] == "article":
        a = c.one("SELECT a.slug, a.action_label, a.action_link, v.title, v.summary, v.steps, v.version, a.origin, a.demo FROM kb_articles a JOIN kb_article_versions v ON v.id = a.live_version_id WHERE a.id = $1", best["id"])
        steps = [f"{i + 1}. {s.get('title') or s.get('text')}" for i, s in enumerate((a["steps"] or [])[:6])]
        answer = f"Segundo o guia «{a['title']}»: {a['summary'] or ''}".strip()
        if steps:
            answer += "\n" + "\n".join(steps)
        out["actions"] = ([{"label": a["action_label"] or "Fazer agora", "link": a["action_link"]}] if a["action_link"] else []) + [{"label": "Abrir o guia completo", "link": best["link"]}]
        src_version = a["version"]
    else:
        f = c.one("SELECT question, answer FROM kb_faqs WHERE id = $1", best["id"])
        answer = f"Segundo a FAQ «{f['question']}»: {f['answer'][:1200]}"
        out["actions"] = [{"label": "Ver a FAQ", "link": best["link"]}]
        src_version = None
    out["answer"] = answer
    out["sources"] = [{"type": i["type"], "title": i["title"], "link": i["link"], "origin_label": i["origin_label"], "demo": i["demo"], "demo_label": i["demo_label"],
                       "needs_review": i["needs_review"], "version": src_version if i is best else None} for i in top[:3]]
    out["confidence"] = best["score"]
    out["notice"] = "Resposta montada a partir de conteúdo publicado da plataforma (sem IA generativa). Em caso de dúvida, abra um chamado."
    if any(s["needs_review"] for s in out["sources"]):
        out["notice"] += " Atenção: alguma fonte está com revisão pendente."
    log(c, "assistant", target_type=best["type"], target_id=best["id"], q=question, concepts=KS.parse(question)["topics"], count=len(top), ctx_key=ctx_key)
    return out


# ------------------------------------------------------------------------------------------------ recomendações
def recommend(c, *, user_id: str, org_id: str | None, user_kind: str | None, missing_guides: list[str], limit: int = 8) -> list[dict]:
    """Próximos conteúdos: guias das etapas que faltam, curso em andamento, eventos inscritos e FAQs mais úteis do perfil. Plano não influencia."""
    out: list[dict] = []
    if missing_guides:
        rows = c.query("SELECT a.slug, a.title, a.summary, a.est_minutes, a.origin, a.demo FROM kb_articles a WHERE a.live_version_id IS NOT NULL AND a.slug = ANY($1::text[])", missing_guides)
        by = {r["slug"]: r for r in rows}
        for g in missing_guides:
            if g in by:
                out.append({"type": "article", "reason": "Próxima etapa da sua jornada", "title": by[g]["title"], "link": f"/ajuda/{g}", "est_minutes": by[g]["est_minutes"], **_label(by[g])})
    for r in c.query("SELECT k.slug, k.title, k.hours, k.origin, k.demo FROM course_enrollments e JOIN courses k ON k.id = e.course_id WHERE e.user_id = $1 AND e.completed_at IS NULL AND k.status = 'published'"
                     " ORDER BY e.started_at DESC LIMIT 2", user_id):
        out.append({"type": "course", "reason": "Continue de onde parou", "title": r["title"], "link": f"/ajuda/academia/{r['slug']}", **_label(r)})
    for r in c.query("SELECT e.slug, e.title, e.starts_at FROM hub_event_registrations g JOIN hub_events e ON e.id = g.event_id WHERE g.user_id = $1 AND g.status = 'registered'"
                     " AND e.starts_at > now() AND e.status = 'published' ORDER BY e.starts_at LIMIT 2", user_id):
        out.append({"type": "event", "reason": "Evento em que você está inscrita", "title": r["title"], "link": f"/ajuda/eventos/{r['slug']}", "starts_at": r["starts_at"]})
    if user_kind:
        have = {o["link"] for o in out}
        for r in c.query("SELECT a.slug, a.title, a.est_minutes, a.origin, a.demo FROM kb_articles a WHERE a.live_version_id IS NOT NULL AND a.kind IN ('guide','start') AND $1 = ANY(a.audience)"
                         " ORDER BY a.view_count DESC, a.title LIMIT 4", user_kind):
            if f"/ajuda/{r['slug']}" not in have:
                out.append({"type": "article", "reason": "Muito consultado por organizações como a sua", "title": r["title"], "link": f"/ajuda/{r['slug']}", "est_minutes": r["est_minutes"], **_label(r)})
    return out[:limit]


# ------------------------------------------------------------------------------------------------ fluxo editorial (quatro olhos)
OBJECTS = {"article_version": ("kb_article_versions", "kb_article_versions"), "resource": ("kb_resources", "kb_resources"), "faq": ("kb_faqs", "kb_faqs"),
           "course": ("courses", "courses"), "event": ("hub_events", "hub_events"), "path": ("learning_paths", "learning_paths")}
TRANSITIONS = {("draft", "review"), ("review", "draft"), ("review", "approved"), ("approved", "draft"), ("approved", "published"), ("published", "archived"),
               ("draft", "archived"), ("review", "archived"), ("approved", "archived"), ("archived", "draft")}


def history(c, obj_type: str, obj_id: str, frm: str | None, to: str, actor: str | None, note: str | None) -> None:
    c.run("INSERT INTO content_history(object_type, object_id, from_status, to_status, actor_id, note) VALUES ($1,$2,$3,$4,$5,$6)", obj_type, obj_id, frm, to, actor, (note or None))


def transition(c, obj_type: str, obj_id: str, to: str, *, actor: str, note: str | None = None) -> dict:
    """Move o conteúdo no fluxo DRAFT → REVIEW → APPROVED → PUBLISHED → ARCHIVED. Aprovar exige pessoa diferente da autora; devolver exige nota."""
    table = OBJECTS[obj_type][0]
    row = c.one(f"SELECT id::text AS id, status, author_id::text AS author_id FROM {table} WHERE id = $1 FOR UPDATE", obj_id)
    if not row:
        raise not_found("Conteúdo")
    frm = row["status"]
    if frm == to:
        return {"id": obj_id, "status": to, "unchanged": True}
    if obj_type == "path" and to in ("review", "approved"):
        raise ApiError(409, "invalid_transition", "Trilhas vão direto de rascunho para publicada (com aprovação de outra pessoa)")
    if obj_type == "path" and to == "published":
        pass
    elif (frm, to) not in TRANSITIONS:
        raise ApiError(409, "invalid_transition", f"Transição {frm} → {to} não permitida")
    if frm == "review" and to == "draft" and not (note and len(note.strip()) >= 5):
        raise ApiError(422, "note_required", "Informe o que precisa ser ajustado (nota obrigatória ao devolver para rascunho)")
    sets = ["status = $2"]
    vals: list = [obj_id, to]
    if to == "approved" or (obj_type == "path" and to == "published"):
        if row["author_id"] and row["author_id"] == actor:
            raise ApiError(403, "four_eyes", "Quem escreveu o conteúdo não pode aprová-lo: peça a revisão de outra pessoa")
        vals.append(actor)
        sets.append(f"approved_by = ${len(vals)}")
        if obj_type != "path":
            sets.append("approved_at = now()")
    if to == "published":
        if obj_type == "article_version":
            ver = c.one("SELECT article_id::text AS article_id FROM kb_article_versions WHERE id = $1", obj_id)
            c.run("UPDATE kb_article_versions SET status = 'superseded' WHERE article_id = $1 AND status = 'published' AND id <> $2", ver["article_id"], obj_id)
            sets.append("published_at = now()")
        elif obj_type == "resource":
            slug = c.scalar("SELECT slug FROM kb_resources WHERE id = $1", obj_id)
            c.run("UPDATE kb_resources SET status = 'superseded' WHERE slug = $1 AND status = 'published' AND id <> $2", slug, obj_id)
            sets.append("published_at = now()")
            sets.append("last_reviewed_at = now()")
        elif obj_type == "faq":
            c.run("UPDATE kb_faqs SET status = 'archived' WHERE id = (SELECT revises_id FROM kb_faqs WHERE id = $1) AND status = 'published'", obj_id)
            sets.append("published_at = now()")
            sets.append("last_reviewed_at = now()")
        elif obj_type in ("course", "event"):
            sets.append("published_at = now()")
            if obj_type == "course":
                sets.append("last_reviewed_at = now()")
    c.run(f"UPDATE {table} SET {', '.join(sets)} WHERE id = $1", *vals)
    history(c, obj_type, obj_id, frm, to, actor, note)
    return {"id": obj_id, "from": frm, "status": to}


def mark_reviewed(c, obj_type: str, obj_id: str, *, actor: str, note: str | None) -> dict:
    """Confirma que o conteúdo continua válido (zera o alerta 'Revisão necessária'); fica no histórico."""
    table = {"article": "kb_articles", "resource": "kb_resources", "faq": "kb_faqs", "course": "courses"}[obj_type]
    if not c.one(f"SELECT 1 FROM {table} WHERE id = $1", obj_id):
        raise not_found("Conteúdo")
    c.run(f"UPDATE {table} SET last_reviewed_at = now() WHERE id = $1", obj_id)
    history(c, {"article": "article_version"}.get(obj_type, obj_type), obj_id, None, "reviewed", actor, note)
    return {"id": obj_id, "reviewed": True}


def stale_overview(c) -> dict:
    """Painel: quantos conteúdos precisam de revisão (por tipo) e os mais atrasados."""
    out = {}
    out["articles"] = c.scalar("SELECT count(*) FROM kb_articles a LEFT JOIN kb_article_versions v ON v.id = a.live_version_id WHERE a.live_version_id IS NOT NULL AND (" + STALE_SQL.format(a="a") + " OR (v.regulatory AND v.valid_until < current_date))")
    out["resources"] = c.scalar("SELECT count(*) FROM kb_resources r WHERE r.status = 'published' AND (" + STALE_SQL.format(a="r") + " OR (r.regulatory AND r.valid_until < current_date))")
    out["faqs"] = c.scalar("SELECT count(*) FROM kb_faqs f WHERE f.status = 'published' AND " + STALE_SQL.format(a="f"))
    out["courses"] = c.scalar("SELECT count(*) FROM courses k WHERE k.status = 'published' AND " + STALE_SQL.format(a="k"))
    out["total"] = sum(out.values())
    out["oldest"] = c.query("SELECT 'article' AS type, a.id::text AS id, a.slug AS ref, a.title, coalesce(a.last_reviewed_at, a.published_at) AS last_reviewed FROM kb_articles a WHERE a.live_version_id IS NOT NULL AND "
                            + STALE_SQL.format(a="a") + " ORDER BY coalesce(a.last_reviewed_at, a.published_at) LIMIT 10")
    return out


def low_resolution_faqs(c, *, min_votes: int = 5, max_helpful_rate: float = 0.5) -> list[dict]:
    """FAQs com muitos votos e baixa taxa de 'ajudou': sinalizadas para a administração (e para virar ticket/artigo)."""
    return c.query("SELECT id::text AS id, question, helpful_yes, helpful_no, round(100.0 * helpful_yes / nullif(helpful_yes + helpful_no, 0)) AS helpful_pct FROM kb_faqs"
                   " WHERE status = 'published' AND helpful_yes + helpful_no >= $1 AND helpful_yes::float / nullif(helpful_yes + helpful_no, 0) < $2 ORDER BY helpful_no DESC LIMIT 50",
                   min_votes, max_helpful_rate)


def to_json(v) -> str:
    return json.dumps(v, ensure_ascii=False)
