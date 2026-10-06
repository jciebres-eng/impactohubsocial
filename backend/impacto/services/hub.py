"""Central de Conhecimento — operações: "Comece aqui" (progresso por dados reais), central de pendências, suporte (SLA), eventos, academia,
parcerias, demonstração, solicitação de teste, boletim e preferências de notificação.

Princípios: progresso nunca é autodeclarado (detectores consultam tabelas reais); solicitação de teste nunca concede acesso por si só; quem pede
(usuária) não altera prioridade/SLA/estado interno (triggers + RLS); dados de contato só com consentimento; nada aqui depende de plano pago para
direito de ajuda (suporte e conteúdo oficial são para todas as contas)."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, UTC
from functools import lru_cache
from pathlib import Path

from ..http import ApiError, not_found
from . import knowledge as K

_CFG = Path(__file__).resolve().parents[3] / "config" / "onboarding_paths.json"


# ------------------------------------------------------------------------------------------------ "Comece aqui"
# Cada detector responde com dados reais (RLS aplica o escopo da organização ativa). $1 = org_id.
DETECTORS = {
    "always": "SELECT $1::uuid IS NOT NULL",
    "org_validated": "SELECT EXISTS (SELECT 1 FROM organizations WHERE id = $1 AND compliance_status = 'approved')",
    "profile_complete": "SELECT EXISTS (SELECT 1 FROM organizations WHERE id = $1 AND description IS NOT NULL AND uf IS NOT NULL AND cardinality(causes) > 0)",
    "documents": "SELECT EXISTS (SELECT 1 FROM documents WHERE org_id = $1 AND deleted_at IS NULL)",
    "diagnosis": "SELECT EXISTS (SELECT 1 FROM diagnoses WHERE org_id = $1 AND status IN ('complete','applied'))",
    "project_created": "SELECT EXISTS (SELECT 1 FROM projects WHERE org_id = $1)",
    "indicators": "SELECT EXISTS (SELECT 1 FROM project_indicators WHERE org_id = $1)",
    "budget": "SELECT EXISTS (SELECT 1 FROM budget_items WHERE org_id = $1)",
    "compliance_ok": "SELECT EXISTS (SELECT 1 FROM organizations WHERE id = $1 AND compliance_status = 'approved')",
    "project_published": "SELECT EXISTS (SELECT 1 FROM projects WHERE org_id = $1 AND visibility = 'published')",
    "applications": "SELECT EXISTS (SELECT 1 FROM applications WHERE osc_org_id = $1)",
    "commitments_osc": "SELECT EXISTS (SELECT 1 FROM commitments WHERE osc_org_id = $1)",
    "execution": "SELECT EXISTS (SELECT 1 FROM expenses WHERE org_id = $1) OR EXISTS (SELECT 1 FROM evidences WHERE org_id = $1)",
    "accountability": "SELECT EXISTS (SELECT 1 FROM evidences WHERE org_id = $1 AND status = 'accepted')",
    "impact_values": "SELECT EXISTS (SELECT 1 FROM indicator_values WHERE org_id = $1)",
    "funder_profile": "SELECT EXISTS (SELECT 1 FROM funder_profiles WHERE org_id = $1)",
    "saved_search": "SELECT EXISTS (SELECT 1 FROM saved_searches WHERE org_id = $1)",
    "applications_funder": "SELECT EXISTS (SELECT 1 FROM applications WHERE funder_org_id = $1)",
    "commitments_funder": "SELECT EXISTS (SELECT 1 FROM commitments WHERE funder_org_id = $1)",
    "follow_progress": "SELECT EXISTS (SELECT 1 FROM follows WHERE follower_org_id = $1)",
    "provider_profile": "SELECT EXISTS (SELECT 1 FROM provider_profiles WHERE org_id = $1)",
    "credential": "SELECT EXISTS (SELECT 1 FROM professional_credentials WHERE org_id = $1)",
    "reviews_done": "SELECT EXISTS (SELECT 1 FROM professional_reviews WHERE professional_org_id = $1)",
    "calls_published": "SELECT EXISTS (SELECT 1 FROM calls WHERE owner_org_id = $1 AND status IN ('open','closed'))",
}


@lru_cache(maxsize=1)
def onboarding_config() -> dict:
    return json.loads(_CFG.read_text(encoding="utf-8"))


def onboarding(c, *, org_id: str, org_kind: str) -> dict:
    cfg = onboarding_config()
    path = cfg["paths"].get(org_kind)
    if not path:
        return {"kind": org_kind, "steps": [], "percent": 0, "next": None, "status": cfg["status"], "config": cfg["version"]}
    steps, done = [], 0
    for s in path["steps"]:
        ok = bool(c.scalar(DETECTORS[s["detector"]], org_id))
        done += ok
        steps.append({"key": s["key"], "title": s["title"], "done": ok, "link": s["link"], "guide": s.get("guide"), "minutes": s.get("minutes")})
    nxt = next((s for s in steps if not s["done"]), None)
    pct = round(100 * done / len(steps)) if steps else 0
    return {"kind": org_kind, "title": path.get("title"), "steps": steps, "done": done, "total": len(steps), "percent": pct, "next": nxt,
            "status": cfg["status"], "config": cfg["version"], "measure": "Concluído por dados reais da plataforma (não por autodeclaração)."}


def pending_center(c, *, user_id: str, org_id: str | None, org_kind: str | None) -> dict:
    """"O que falta para eu avançar?" — pendências derivadas de dados reais, ordenadas por urgência."""
    items: list[dict] = []
    ob = None
    if org_id and org_kind:
        ob = onboarding(c, org_id=org_id, org_kind=org_kind)
        for s in ob["steps"]:
            if not s["done"]:
                items.append({"kind": "onboarding", "severity": "info", "title": s["title"], "why": "Etapa da sua jornada ainda não concluída", "link": s["link"], "guide": s.get("guide")})
                break
        comp = c.one("SELECT compliance_status FROM organizations WHERE id = $1", org_id)
        if comp and comp["compliance_status"] in ("rejected", "suspended"):
            items.append({"kind": "compliance", "severity": "high", "title": "Regularize a análise da organização", "why": "Há pendência na validação", "link": "/organizacao/compliance"})
        for d in c.query("SELECT title, valid_until FROM documents WHERE org_id = $1 AND deleted_at IS NULL AND valid_until IS NOT NULL AND valid_until < current_date + 30 ORDER BY valid_until LIMIT 5", org_id):
            vencido = d["valid_until"] < datetime.now(UTC).date()
            items.append({"kind": "document", "severity": "high" if vencido else "medium", "title": f"Documento {'vencido' if vencido else 'vencendo'}: {d['title']}", "why": f"Validade: {d['valid_until']}", "link": "/documentos"})
        tr = c.one("SELECT trial_end, status FROM org_trials WHERE org_id = $1", org_id)
        if tr and tr["status"] == "active":
            left = (tr["trial_end"] - datetime.now(UTC)).days
            if 0 <= left <= 3:
                items.append({"kind": "trial", "severity": "medium", "title": "Seu período de teste termina em breve", "why": f"Restam {left} dia(s)", "link": "/conta/plano"})
    for t in c.query("SELECT id::text AS id, number, subject FROM support_tickets WHERE user_id = $1 AND status = 'waiting_user' ORDER BY updated_at DESC LIMIT 5", user_id):
        items.append({"kind": "support", "severity": "high", "title": f"Chamado #{t['number']} aguarda sua resposta", "why": t["subject"], "link": f"/ajuda/suporte/{t['id']}"})
    for e in c.query("SELECT e.slug, e.title, e.starts_at FROM hub_event_registrations g JOIN hub_events e ON e.id = g.event_id WHERE g.user_id = $1 AND g.status = 'registered' AND e.status = 'published'"
                     " AND e.starts_at BETWEEN now() AND now() + interval '3 days' ORDER BY e.starts_at LIMIT 3", user_id):
        items.append({"kind": "event", "severity": "info", "title": f"Evento em breve: {e['title']}", "why": e["starts_at"].isoformat(), "link": f"/ajuda/eventos/{e['slug']}"})
    for k in c.query("SELECT k.slug, k.title FROM course_enrollments e JOIN courses k ON k.id = e.course_id WHERE e.user_id = $1 AND e.completed_at IS NULL AND k.status = 'published' LIMIT 3", user_id):
        items.append({"kind": "course", "severity": "info", "title": f"Continue o curso: {k['title']}", "why": "Curso em andamento", "link": f"/ajuda/academia/{k['slug']}"})
    order = {"high": 0, "medium": 1, "info": 2}
    items.sort(key=lambda i: order[i["severity"]])
    return {"items": items, "total": len(items), "onboarding_percent": ob["percent"] if ob else None}


def my_activities(c, *, user_id: str, org_id: str | None) -> dict:
    """Hub operacional "Minhas atividades": tudo que a pessoa tem em andamento na Central."""
    return {
        "tickets": c.query("SELECT id::text AS id, number, subject, status, priority, updated_at FROM support_tickets WHERE user_id = $1 AND status NOT IN ('closed') ORDER BY updated_at DESC LIMIT 10", user_id),
        "courses": c.query("SELECT k.slug, k.title, e.started_at, e.completed_at, (SELECT count(*) FROM lesson_progress p WHERE p.user_id = e.user_id AND p.course_id = e.course_id AND p.completed_at IS NOT NULL) AS lessons_done,"
                           " (SELECT count(*) FROM course_lessons l WHERE l.course_id = e.course_id) AS lessons_total FROM course_enrollments e JOIN courses k ON k.id = e.course_id WHERE e.user_id = $1 ORDER BY e.started_at DESC LIMIT 10", user_id),
        "events": c.query("SELECT e.slug, e.title, e.starts_at, g.status FROM hub_event_registrations g JOIN hub_events e ON e.id = g.event_id WHERE g.user_id = $1 AND g.status IN ('registered','waitlist') AND e.starts_at > now() - interval '1 day' ORDER BY e.starts_at LIMIT 10", user_id),
        "certificates": c.query("SELECT code, course_title, hours, issued_at, revoked_at FROM course_certificates WHERE user_id = $1 ORDER BY issued_at DESC LIMIT 20", user_id),
        "trial_requests": c.query("SELECT id::text AS id, status, period_days, created_at, decision_reason FROM trial_requests WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5", user_id),
        "partnership_requests": c.query("SELECT id::text AS id, org_name, kind, status, created_at FROM partnership_requests WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5", user_id),
        "demo_requests": c.query("SELECT id::text AS id, status, scheduled_at, meeting_url FROM demo_requests WHERE user_id = $1 ORDER BY created_at DESC LIMIT 5", user_id),
    }


# ------------------------------------------------------------------------------------------------ suporte
PRIORITIES = ("low", "normal", "high", "critical")


def _sla(c, priority: str) -> dict:
    return c.one("SELECT first_response_minutes AS fr, resolution_minutes AS rs FROM support_sla WHERE priority = $1", priority)


def ticket_create(c, *, user_id: str, org_id: str | None, category: str, subject: str, message: str, context: dict, document_ids: list[str]) -> dict:
    s = _sla(c, "normal")
    tid = c.scalar("INSERT INTO support_tickets(org_id, user_id, category, subject, context, first_response_due, resolution_due) VALUES ($1,$2,$3,$4,$5::jsonb,"
                   " now() + make_interval(mins => $6), now() + make_interval(mins => $7)) RETURNING id::text",
                   org_id, user_id, category, subject, json.dumps(context, ensure_ascii=False), s["fr"], s["rs"])
    c.run("INSERT INTO support_messages(ticket_id, author_id, author_kind, body) VALUES ($1,$2,'user',$3)", tid, user_id, message)
    _attach(c, tid, None, document_ids, org_id)
    num = c.scalar("SELECT number FROM support_tickets WHERE id = $1", tid)
    K.log(c, "ticket_from_help", target_type=None, ctx_key=(context or {}).get("field") or (context or {}).get("page"))
    return {"id": tid, "number": num}


def _attach(c, ticket_id: str, message_id: str | None, document_ids: list[str], org_id: str | None) -> None:
    for d in document_ids[:5]:
        if not c.one("SELECT 1 FROM documents WHERE id = $1 AND org_id = $2 AND deleted_at IS NULL", d, org_id):
            raise ApiError(422, "invalid_attachment", "Anexo inválido: envie o arquivo em Documentos da sua organização e tente de novo")
        c.run("INSERT INTO support_attachments(ticket_id, message_id, document_id) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING", ticket_id, message_id, d)


def ticket_get(c, ticket_id: str, *, staff: bool) -> dict:
    t = c.one("SELECT t.id::text AS id, t.number, t.category, t.priority, t.status, t.subject, t.context, t.org_id::text AS org_id, t.user_id::text AS user_id, t.assigned_to::text AS assigned_to,"
              " t.first_response_due, t.resolution_due, t.first_response_at, t.escalated_at, t.resolved_at, t.satisfaction, t.recurring, t.created_at, t.updated_at,"
              " u.full_name AS requester FROM support_tickets t JOIN users u ON u.id = t.user_id WHERE t.id = $1", ticket_id)
    if not t:
        raise not_found("Chamado")
    t["messages"] = c.query("SELECT id::text AS id, author_kind, body, internal, created_at FROM support_messages WHERE ticket_id = $1 ORDER BY created_at", ticket_id)
    t["attachments"] = c.query("SELECT a.document_id::text AS document_id, d.filename FROM support_attachments a JOIN documents d ON d.id = a.document_id WHERE a.ticket_id = $1", ticket_id)
    now = datetime.now(UTC)
    t["sla"] = {"first_response_overdue": bool(t["first_response_at"] is None and t["first_response_due"] and t["first_response_due"] < now and t["status"] not in ("resolved", "closed")),
                "resolution_overdue": bool(t["resolution_due"] and t["resolution_due"] < now and t["status"] not in ("resolved", "closed"))}
    if not staff:
        for k in ("assigned_to", "recurring", "org_id", "user_id"):
            t.pop(k, None)
    return t


def ticket_reply(c, ticket_id: str, *, author_id: str, body: str, staff: bool, internal: bool, document_ids: list[str], org_id: str | None) -> dict:
    t = c.one("SELECT status, first_response_at, user_id::text AS user_id, number, org_id::text AS org_id FROM support_tickets WHERE id = $1", ticket_id)
    if not t:
        raise not_found("Chamado")
    if t["status"] == "closed":
        raise ApiError(409, "ticket_closed", "Chamado encerrado: abra um novo")
    mid = c.scalar("INSERT INTO support_messages(ticket_id, author_id, author_kind, body, internal) VALUES ($1,$2,$3,$4,$5) RETURNING id::text",
                   ticket_id, author_id, "staff" if staff else "user", body, bool(internal and staff))
    _attach(c, ticket_id, mid, document_ids, org_id if not staff else t["org_id"])
    if staff and not internal:
        c.run("UPDATE support_tickets SET first_response_at = coalesce(first_response_at, now()), status = CASE WHEN status IN ('open','in_progress') THEN 'waiting_user' ELSE status END WHERE id = $1", ticket_id)
        if t["org_id"]:
            notify_user(c, t["user_id"], t["org_id"], "support", f"Resposta no chamado #{t['number']}", body[:200], f"/ajuda/suporte/{ticket_id}")
    elif not staff and t["status"] in ("waiting_user", "resolved"):
        c.run("UPDATE support_tickets SET status = 'open' WHERE id = $1", ticket_id)
    return {"id": mid}


def ticket_staff_update(c, ticket_id: str, *, status: str | None, priority: str | None, assigned_to: str | None, assign_set: bool) -> dict:
    t = c.one("SELECT status, priority, created_at, user_id::text AS user_id, org_id::text AS org_id, number FROM support_tickets WHERE id = $1 FOR UPDATE", ticket_id)
    if not t:
        raise not_found("Chamado")
    sets, vals = ["updated_at = now()"], [ticket_id]
    if priority and priority != t["priority"]:
        s = _sla(c, priority)
        vals += [priority, s["fr"], s["rs"]]
        sets += [f"priority = ${len(vals) - 2}", f"first_response_due = created_at + make_interval(mins => ${len(vals) - 1})", f"resolution_due = created_at + make_interval(mins => ${len(vals)})"]
    if assign_set:
        vals.append(assigned_to)
        sets.append(f"assigned_to = ${len(vals)}")
    if status and status != t["status"]:
        vals.append(status)
        sets.append(f"status = ${len(vals)}")
        if status == "resolved":
            sets.append("resolved_at = now()")
        if status == "closed":
            sets.append("closed_at = now()")
        if status in ("open", "in_progress", "waiting_user", "waiting_internal"):
            sets.append("resolved_at = NULL")
    c.run(f"UPDATE support_tickets SET {', '.join(sets)} WHERE id = $1", *vals)
    if status == "resolved" and t["org_id"]:
        notify_user(c, t["user_id"], t["org_id"], "support", f"Chamado #{t['number']} resolvido", "Se ainda precisar, responda para reabrir. Avalie o atendimento.", f"/ajuda/suporte/{ticket_id}")
    return {"id": ticket_id}


def ticket_rate(c, ticket_id: str, score: int) -> dict:
    t = c.one("SELECT status FROM support_tickets WHERE id = $1", ticket_id)
    if not t:
        raise not_found("Chamado")
    if t["status"] not in ("resolved", "closed"):
        raise ApiError(409, "not_resolved", "Avalie o atendimento após a resolução")
    c.run("UPDATE support_tickets SET satisfaction = $2 WHERE id = $1", ticket_id, score)
    return {"id": ticket_id, "satisfaction": score}


def sla_escalation(c) -> dict:
    """Escala chamados abertos além do prazo (marca `escalated_at` e avisa a equipe de plantão via mensagem de sistema)."""
    rows = c.query("SELECT t.id::text AS id, t.number FROM support_tickets t JOIN support_sla s ON s.priority = t.priority WHERE t.status NOT IN ('resolved','closed','waiting_user')"
                   " AND t.escalated_at IS NULL AND t.created_at + make_interval(mins => s.escalate_after_minutes) < now() AND coalesce(t.first_response_at, 'infinity') > t.created_at + make_interval(mins => s.escalate_after_minutes)")
    for r in rows:
        c.run("UPDATE support_tickets SET escalated_at = now(), priority = CASE WHEN priority IN ('low','normal') THEN 'high' ELSE priority END WHERE id = $1", r["id"])
        c.run("INSERT INTO support_messages(ticket_id, author_kind, body, internal) VALUES ($1,'staff',$2,true)", r["id"], "Escalado automaticamente: prazo de primeira resposta excedido.")
    return {"escalated": len(rows)}


def recurring_candidates(c, *, min_count: int = 3, days: int = 60) -> list[dict]:
    """Assuntos recorrentes (categoria + tela de origem) sem artigo associado → candidatos a novo artigo/FAQ."""
    return c.query("SELECT category, coalesce(context->>'page', '—') AS page, count(*) AS tickets, max(created_at) AS last_at, bool_or(kb_article_id IS NOT NULL) AS has_article"
                   " FROM support_tickets WHERE created_at > now() - make_interval(days => $2) GROUP BY 1, 2 HAVING count(*) >= $1 AND NOT bool_or(kb_article_id IS NOT NULL) ORDER BY count(*) DESC LIMIT 30",
                   min_count, days)


# ------------------------------------------------------------------------------------------------ eventos
def event_card(e: dict, *, seats: int | None) -> dict:
    cap = e.get("capacity")
    e["seats_taken"] = seats
    e["seats_left"] = max(0, cap - seats) if cap is not None and seats is not None else None
    e["full"] = bool(cap is not None and seats is not None and seats >= cap)
    e["demo_label"] = K.DEMO_LABEL if e.get("demo") else None
    return e


def event_register(c, event_id: str, *, user_id: str, org_id: str | None) -> dict:
    e = c.one("SELECT id::text AS id, slug, title, status, starts_at, capacity, registration_open FROM hub_events WHERE id = $1 FOR UPDATE", event_id)
    if not e or e["status"] != "published":
        raise not_found("Evento")
    if not e["registration_open"] or e["starts_at"] < datetime.now(UTC):
        raise ApiError(409, "registration_closed", "Inscrições encerradas para este evento")
    cur = c.one("SELECT status FROM hub_event_registrations WHERE event_id = $1 AND user_id = $2", event_id, user_id)
    if cur and cur["status"] in ("registered", "waitlist"):
        return {"status": cur["status"], "already": True}
    seats = c.scalar("SELECT hub_event_seats($1)", event_id)
    status = "waitlist" if e["capacity"] is not None and seats >= e["capacity"] else "registered"
    c.run("INSERT INTO hub_event_registrations(event_id, user_id, org_id, status) VALUES ($1,$2,$3,$4)"
          " ON CONFLICT (event_id, user_id) DO UPDATE SET status = EXCLUDED.status, org_id = EXCLUDED.org_id, created_at = now()", event_id, user_id, org_id, status)
    return {"status": status, "waitlist": status == "waitlist"}


def event_cancel(c, event_id: str, *, user_id: str) -> dict:
    """Cancela a inscrição e promove a primeira da lista de espera (por ordem de chegada)."""
    c.scalar("SELECT id FROM hub_events WHERE id = $1 FOR UPDATE", event_id)
    cur = c.one("SELECT status FROM hub_event_registrations WHERE event_id = $1 AND user_id = $2", event_id, user_id)
    if not cur or cur["status"] == "cancelled":
        raise not_found("Inscrição")
    c.run("UPDATE hub_event_registrations SET status = 'cancelled' WHERE event_id = $1 AND user_id = $2", event_id, user_id)
    promoted = None
    if cur["status"] == "registered":
        # a promoção é feita em contexto privilegiado pela rota (a usuária não enxerga inscrições alheias)
        promoted = event_promote(c, event_id)
    return {"cancelled": True, "promoted": bool(promoted)}


def event_promote(c, event_id: str) -> dict | None:
    e = c.one("SELECT title, slug, capacity FROM hub_events WHERE id = $1", event_id)
    if not e or e["capacity"] is None:
        return None
    if c.scalar("SELECT hub_event_seats($1)", event_id) >= e["capacity"]:
        return None
    w = c.one("SELECT id::text AS id, user_id::text AS user_id, org_id::text AS org_id FROM hub_event_registrations WHERE event_id = $1 AND status = 'waitlist' ORDER BY created_at LIMIT 1", event_id)
    if not w:
        return None
    c.run("UPDATE hub_event_registrations SET status = 'registered' WHERE id = $1", w["id"])
    if w["org_id"]:
        notify_user(c, w["user_id"], w["org_id"], "events", f"Vaga confirmada: {e['title']}", "Uma vaga abriu e sua inscrição foi confirmada.", f"/ajuda/eventos/{e['slug']}")
    return w


def event_reminders(c) -> dict:
    """Lembrete 24h antes (uma vez por inscrita): usa `billing_notices`-like dedupe via notifications.kind+link+dia."""
    rows = c.query("SELECT g.user_id::text AS user_id, g.org_id::text AS org_id, e.title, e.slug, e.id::text AS eid FROM hub_event_registrations g JOIN hub_events e ON e.id = g.event_id"
                   " WHERE g.status = 'registered' AND e.status = 'published' AND g.org_id IS NOT NULL AND e.starts_at BETWEEN now() AND now() + interval '24 hours'"
                   " AND NOT EXISTS (SELECT 1 FROM notifications n WHERE n.user_id = g.user_id AND n.kind = 'events.reminder' AND n.link = '/ajuda/eventos/' || e.slug)")
    n = 0
    for r in rows:
        if _pref(c, r["user_id"], "events", "in_app"):
            c.scalar("SELECT app_notify($1,$2,'events.reminder',$3,$4,$5)", r["org_id"], r["user_id"], f"Amanhã: {r['title']}", "Seu evento começa em menos de 24 horas.", f"/ajuda/eventos/{r['slug']}")
            n += 1
    return {"reminders": n}


# ------------------------------------------------------------------------------------------------ academia
def course_detail(c, slug: str, *, user_id: str | None) -> dict:
    k = c.one("SELECT id::text AS id, slug, title, summary, audience, origin, level, hours, pass_score, cert_enabled, version, demo, last_reviewed_at FROM courses WHERE slug = $1 AND status = 'published'", slug)
    if not k:
        raise not_found("Curso")
    mods = c.query("SELECT id::text AS id, position, title, description FROM course_modules WHERE course_id = $1 ORDER BY position", k["id"])
    lessons = c.query("SELECT id::text AS id, module_id::text AS module_id, position, title, kind, minutes, video_url, captions_url,"
                      " (transcript IS NOT NULL) AS has_transcript FROM course_lessons WHERE course_id = $1 ORDER BY position", k["id"])
    prog = {}
    enrolled = None
    if user_id:
        prog = {r["lesson_id"]: r for r in c.query("SELECT lesson_id::text AS lesson_id, score, attempts, completed_at FROM lesson_progress WHERE user_id = $1 AND course_id = $2", user_id, k["id"])}
        enrolled = c.one("SELECT started_at, completed_at, last_lesson_id::text AS last_lesson_id, course_version FROM course_enrollments WHERE user_id = $1 AND course_id = $2", user_id, k["id"])
    for m in mods:
        m["lessons"] = [dict(ls, completed=bool(prog.get(ls["id"], {}).get("completed_at")), score=prog.get(ls["id"], {}).get("score")) for ls in lessons if ls["module_id"] == m["id"]]
    done = sum(1 for ls in lessons if prog.get(ls["id"], {}).get("completed_at"))
    k.update(K._label(k))
    k.update({"modules": mods, "lessons_total": len(lessons), "lessons_done": done, "percent": round(100 * done / len(lessons)) if lessons else 0, "enrollment": enrolled,
              "certificate_note": "Certificado de conclusão desta plataforma — não é diploma nem certificação oficial/reconhecida pelo MEC." if k["cert_enabled"] else None})
    return k


def lesson_get(c, lesson_id: str) -> dict:
    ls = c.one("SELECT l.id::text AS id, l.course_id::text AS course_id, l.title, l.kind, l.body, l.video_url, l.captions_url, l.transcript, l.minutes, l.materials, l.quiz, k.slug AS course_slug,"
               " k.title AS course_title FROM course_lessons l JOIN courses k ON k.id = l.course_id WHERE l.id = $1", lesson_id)
    if not ls:
        raise not_found("Aula")
    return ls


def course_enroll(c, slug: str, *, user_id: str, org_id: str | None) -> dict:
    k = c.one("SELECT id::text AS id, version FROM courses WHERE slug = $1 AND status = 'published'", slug)
    if not k:
        raise not_found("Curso")
    c.run("INSERT INTO course_enrollments(user_id, course_id, org_id, course_version) VALUES ($1,$2,$3,$4) ON CONFLICT (user_id, course_id) DO NOTHING", user_id, k["id"], org_id, k["version"])
    return {"enrolled": True, "course_id": k["id"]}


def lesson_complete(c, lesson_id: str, *, user_id: str, answers: list[int] | None, holder_name: str, org_id: str | None) -> dict:
    ls = c.one("SELECT l.id::text AS id, l.course_id::text AS course_id, l.kind, k.pass_score, k.version FROM course_lessons l JOIN courses k ON k.id = l.course_id AND k.status = 'published' WHERE l.id = $1", lesson_id)
    if not ls:
        raise not_found("Aula")
    if not c.one("SELECT 1 FROM course_enrollments WHERE user_id = $1 AND course_id = $2", user_id, ls["course_id"]):
        raise ApiError(409, "not_enrolled", "Inscreva-se no curso para registrar progresso")
    score, passed = None, True
    if ls["kind"] == "quiz":
        if answers is None:
            raise ApiError(422, "answers_required", "Envie as respostas do quiz")
        score = c.scalar("SELECT lesson_grade($1, $2::int[])", lesson_id, answers)
        if score is None:
            raise ApiError(409, "quiz_not_configured", "Quiz sem gabarito configurado")
        passed = score >= ls["pass_score"]
    c.run("INSERT INTO lesson_progress(user_id, lesson_id, course_id, score, attempts, completed_at) VALUES ($1,$2,$3,$4,1, CASE WHEN $5 THEN now() END)"
          " ON CONFLICT (user_id, lesson_id) DO UPDATE SET attempts = lesson_progress.attempts + 1, score = greatest(coalesce(lesson_progress.score, 0), coalesce(EXCLUDED.score, 0)),"
          " completed_at = coalesce(lesson_progress.completed_at, EXCLUDED.completed_at)", user_id, lesson_id, ls["course_id"], score, passed)
    c.run("UPDATE course_enrollments SET last_lesson_id = $3 WHERE user_id = $1 AND course_id = $2", user_id, ls["course_id"], lesson_id)
    out = {"lesson_id": lesson_id, "score": score, "passed": passed, "required": ls["pass_score"] if ls["kind"] == "quiz" else None}
    total = c.scalar("SELECT count(*) FROM course_lessons WHERE course_id = $1", ls["course_id"])
    done = c.scalar("SELECT count(*) FROM lesson_progress WHERE user_id = $1 AND course_id = $2 AND completed_at IS NOT NULL", user_id, ls["course_id"])
    out["percent"] = round(100 * done / total) if total else 0
    if total and done >= total:
        c.run("UPDATE course_enrollments SET completed_at = coalesce(completed_at, now()) WHERE user_id = $1 AND course_id = $2", user_id, ls["course_id"])
        out["course_completed"] = True
    return out


def certificate_issue(c, slug: str, *, user_id: str, org_id: str | None, holder_name: str) -> dict:
    """Emite o certificado de conclusão (NÃO oficial) quando TODAS as aulas foram concluídas; o gabarito foi exigido na conclusão de cada quiz."""
    k = c.one("SELECT id::text AS id, title, hours, version, cert_enabled FROM courses WHERE slug = $1 AND status = 'published'", slug)
    if not k:
        raise not_found("Curso")
    if not k["cert_enabled"]:
        raise ApiError(409, "no_certificate", "Este curso não emite certificado")
    e = c.one("SELECT completed_at FROM course_enrollments WHERE user_id = $1 AND course_id = $2", user_id, k["id"])
    if not e or not e["completed_at"]:
        raise ApiError(409, "course_incomplete", "Conclua todas as aulas e atividades para emitir o certificado")
    ex = c.one("SELECT code, issued_at, revoked_at FROM course_certificates WHERE user_id = $1 AND course_id = $2 AND course_version = $3", user_id, k["id"], k["version"])
    if ex:
        return {"code": ex["code"], "issued_at": ex["issued_at"], "already": True}
    code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(12))
    c.run("INSERT INTO course_certificates(code, user_id, org_id, course_id, course_version, course_title, holder_name, hours) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
          code, user_id, org_id, k["id"], k["version"], k["title"], holder_name, k["hours"])
    return {"code": code, "issued": True}


def certificate_verify(c, code: str) -> dict:
    r = c.one("SELECT code, course_title, holder_name, hours, issued_at, revoked_at, course_version FROM course_certificates WHERE code = $1", code.upper())
    if not r:
        raise not_found("Certificado")
    return {"valid": r["revoked_at"] is None, "code": r["code"], "course_title": r["course_title"], "holder_name": r["holder_name"], "hours": r["hours"], "issued_at": r["issued_at"],
            "revoked": r["revoked_at"] is not None, "official": False,
            "notice": "Certificado de conclusão emitido pela plataforma para fins educacionais. Não é diploma nem certificação reconhecida oficialmente."}


# ------------------------------------------------------------------------------------------------ teste (solicitação → decisão administrativa)
def trial_request_decide(c, settings, request_id: str, *, admin_id: str, approve: bool, reason: str) -> dict:
    from . import monetization as mon
    r = c.one("SELECT id::text AS id, org_id::text AS org_id, org_kind, period_days, status, user_id::text AS user_id FROM trial_requests WHERE id = $1 FOR UPDATE", request_id)
    if not r:
        raise not_found("Solicitação")
    if r["status"] != "requested":
        raise ApiError(409, "already_decided", "Solicitação já decidida")
    outcome = "not_applicable"
    if approve:
        cur = c.one("SELECT status, trial_end FROM org_trials WHERE org_id = $1", r["org_id"])
        if not cur:
            res = mon.start_trial(c, settings, org_id=r["org_id"], org_kind=r["org_kind"], email=None, cnpj=None, user_id=admin_id, source="admin", days=r["period_days"], force=True)
            if not res.get("started"):
                raise ApiError(409, "trial_unavailable", f"Não foi possível iniciar o teste ({res.get('reason')})")
            outcome = "trial_started"
        elif cur["status"] == "active" and cur["trial_end"] > datetime.now(UTC):
            c.run("UPDATE org_trials SET trial_end = trial_end + make_interval(days => $2), updated_at = now() WHERE org_id = $1", r["org_id"], r["period_days"])
            outcome = "trial_extended"
        else:
            raise ApiError(409, "trial_used", "Esta organização já usou o período de teste; ofereça licença/convênio ou plano pago")
    c.run("UPDATE trial_requests SET status = $2, decided_by = $3, decided_at = now(), decision_reason = $4, outcome = $5 WHERE id = $1", request_id, "approved" if approve else "rejected", admin_id, reason, outcome)
    notify_user(c, r["user_id"], r["org_id"], "billing", "Solicitação de teste " + ("aprovada" if approve else "analisada"), reason[:300], "/conta/plano")
    return {"id": request_id, "status": "approved" if approve else "rejected", "outcome": outcome}


def trial_dashboard(c) -> dict:
    return {
        "requests": c.query("SELECT status, count(*) AS n FROM trial_requests GROUP BY status"),
        "active": c.scalar("SELECT count(*) FROM org_trials WHERE status = 'active' AND trial_end > now()"),
        "ending_7d": c.scalar("SELECT count(*) FROM org_trials WHERE status = 'active' AND trial_end BETWEEN now() AND now() + interval '7 days'"),
        "converted": c.scalar("SELECT count(*) FROM org_trials WHERE status = 'converted'"),
        "ended": c.scalar("SELECT count(*) FROM org_trials WHERE status = 'ended'"),
        "by_plan": c.query("SELECT plan_key, count(*) AS n FROM org_trials GROUP BY plan_key ORDER BY n DESC"),
        "usage": c.query("SELECT t.org_id::text AS org_id, o.legal_name, t.trial_end, (SELECT count(*) FROM projects p WHERE p.org_id = t.org_id) AS projects,"
                         " (SELECT count(*) FROM documents d WHERE d.org_id = t.org_id AND d.deleted_at IS NULL) AS documents,"
                         " (SELECT count(*) FROM applications a WHERE a.osc_org_id = t.org_id OR a.funder_org_id = t.org_id) AS applications"
                         " FROM org_trials t JOIN organizations o ON o.id = t.org_id WHERE t.status = 'active' ORDER BY t.trial_end LIMIT 50"),
        "note": "Uso derivado das tabelas reais; conversão = assinatura paga confirmada pelo provedor.",
    }


# ------------------------------------------------------------------------------------------------ boletim
def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def newsletter_subscribe(c, *, email: str, topics: list[str], frequency: str, user_id: str | None) -> str | None:
    """Duplo opt-in: cria/renova pendência e devolve o token de confirmação (só para envio por e-mail). Ativa já inscrita: devolve None (sem reenvio)."""
    token = secrets.token_urlsafe(32)
    row = c.one("SELECT status FROM newsletter_subscriptions WHERE email = $1", email)
    if row and row["status"] == "active":
        return None
    c.run("INSERT INTO newsletter_subscriptions(email, user_id, topics, frequency, token_hash) VALUES ($1,$2,$3::text[],$4,$5)"
          " ON CONFLICT (email) DO UPDATE SET topics = EXCLUDED.topics, frequency = EXCLUDED.frequency, token_hash = EXCLUDED.token_hash, status = 'pending', consent_at = now()",
          email, user_id, topics, frequency, _hash(token))
    return token


def newsletter_confirm(c, token: str) -> bool:
    return bool(c.scalar("SELECT newsletter_confirm($1)", _hash(token)))


def newsletter_unsubscribe(c, token: str) -> bool:
    return bool(c.scalar("SELECT newsletter_unsubscribe($1)", _hash(token)))


# ------------------------------------------------------------------------------------------------ preferências e notificações
GROUPS = ("billing", "content", "events", "support", "partnerships", "opportunities",
          # grupos da rede (0016): a pessoa silencia propostas sem silenciar cobrança.
          "network", "proposal", "message", "funding", "report", "project", "document", "account",
          # grupo da camada econômica (0018): quem administra programa com dezenas de projetos não quer o
          # mesmo interruptor das notificações de execução de cada projeto.
          "program")


def prefs_get(c, user_id: str) -> list[dict]:
    """Os 15 interruptores, com o que cada um governa — e com a janela de silêncio e o teto diário.

    v0.20.0: `kinds` existe porque um interruptor sem rótulo do que ele desliga é um interruptor que
    ninguém usa. Até aqui a tela oferecia "project" e a pessoa tinha de adivinhar se evidência,
    marco e despesa estavam ali dentro.
    """
    have = {r["grp"]: r for r in c.query(
        "SELECT grp, in_app, email, quiet_from::text AS quiet_from, quiet_to::text AS quiet_to,"
        " max_per_day, digest FROM notification_prefs WHERE user_id = $1", user_id)}
    catalogo: dict[str, list[dict]] = {}
    for k in c.query("SELECT kind, grp, label_pt, default_priority, emailable FROM notification_kinds"
                     " ORDER BY grp, label_pt"):
        catalogo.setdefault(k["grp"], []).append(k)
    return [{"grp": g,
             "in_app": have.get(g, {}).get("in_app", True),
             "email": have.get(g, {}).get("email", True),
             "quiet_from": have.get(g, {}).get("quiet_from"),
             "quiet_to": have.get(g, {}).get("quiet_to"),
             "max_per_day": have.get(g, {}).get("max_per_day"),
             "digest": have.get(g, {}).get("digest", "off"),
             "kinds": catalogo.get(g, [])} for g in GROUPS]


def prefs_set(c, user_id: str, items: list[dict]) -> list[dict]:
    for it in items:
        c.run("INSERT INTO notification_prefs(user_id, grp, in_app, email, quiet_from, quiet_to,"
              " max_per_day, digest) VALUES ($1,$2,$3,$4,$5,$6,$7,coalesce($8,'off'))"
              " ON CONFLICT (user_id, grp) DO UPDATE SET in_app = EXCLUDED.in_app,"
              " email = EXCLUDED.email, quiet_from = EXCLUDED.quiet_from,"
              " quiet_to = EXCLUDED.quiet_to, max_per_day = EXCLUDED.max_per_day,"
              " digest = EXCLUDED.digest",
              user_id, it["grp"], it["in_app"], it["email"], it.get("quiet_from"),
              it.get("quiet_to"), it.get("max_per_day"), it.get("digest"))
    return prefs_get(c, user_id)


def notification_policy(c) -> dict:
    """A política declarada da plataforma, para a tela não repetir números escritos à mão."""
    row = c.one("SELECT max_per_day, quiet_from::text AS quiet_from, quiet_to::text AS quiet_to,"
                " digest_hour, retry_max, retry_backoff_minutes, note FROM notification_policy")
    return row or {}


def _pref(c, user_id: str, grp: str, channel: str) -> bool:
    r = c.one(f"SELECT {channel} AS v FROM notification_prefs WHERE user_id = $1 AND grp = $2", user_id, grp)
    return True if r is None else bool(r["v"])


def notify_user(c, user_id: str, org_id: str, grp: str, title: str, body: str, link: str) -> bool:
    """Notificação interna respeitando a preferência da usuária (in_app)."""
    if not _pref(c, user_id, grp, "in_app"):
        return False
    c.scalar("SELECT app_notify($1,$2,$3,$4,$5,$6)", org_id, user_id, f"{grp}.notice", title, body, link)
    return True


def email_allowed(c, user_id: str, grp: str) -> bool:
    return _pref(c, user_id, grp, "email")


# ------------------------------------------------------------------------------------------------ parcerias (pipeline) e demonstração
PIPELINE = ("received", "qualification", "contact", "meeting", "proposal", "negotiation", "approved", "active", "completed", "archived", "rejected")


def partnership_move(c, request_id: str, *, to: str, actor: str, note: str | None) -> dict:
    r = c.one("SELECT status, org_name, kind, objective FROM partnership_requests WHERE id = $1 FOR UPDATE", request_id)
    if not r:
        raise not_found("Pedido de parceria")
    if r["status"] == to:
        return {"id": request_id, "status": to, "unchanged": True}
    if r["status"] in ("archived", "rejected", "completed") and to not in ("archived",):
        raise ApiError(409, "closed_request", "Pedido encerrado: registre um novo")
    c.run("UPDATE partnership_requests SET status = $2, last_activity_at = now() WHERE id = $1", request_id, to)
    c.run("INSERT INTO partnership_activities(request_id, kind, body, from_status, to_status, author_id) VALUES ($1,'status',$2,$3,$4,$5)", request_id, note, r["status"], to, actor)
    if to == "active":
        c.run("INSERT INTO partnerships(request_id, name, kind, scope, created_by) VALUES ($1,$2,$3,$4,$5) ON CONFLICT (request_id) DO NOTHING", request_id, r["org_name"], r["kind"], (r["objective"] or "")[:3000], actor)
    return {"id": request_id, "from": r["status"], "status": to}


def send_mail(app, c, *, to: str, subject: str, text: str, user_id: str | None = None, grp: str = "content") -> bool:
    """E-mail transacional via mailer configurado; respeita preferência quando há usuária. Falha de envio nunca derruba a operação."""
    try:
        if user_id and not email_allowed(c, user_id, grp):
            return False
        app.mailer.send(to, subject, text)
        return True
    except Exception:  # noqa: BLE001
        return False


def _delivery(c, notification_id: str, *, status: str, error: str | None = None,
              skipped_reason: str | None = None, next_retry_at=None) -> None:
    """Registra o estado REAL da entrega, inclusive quando ela não aconteceu e por quê.

    `sent` aqui significa aceito pelo servidor de e-mail. Não significa entregue na caixa da pessoa
    nem lido — duas coisas que a plataforma não tem como saber e por isso não afirma.
    """
    c.run("INSERT INTO notification_deliveries(notification_id, channel, status, attempts,"
          " last_error, skipped_reason, next_retry_at, sent_at)"
          " VALUES ($1,'email',$2, CASE WHEN $2 IN ('sent','failed','given_up') THEN 1 ELSE 0 END,"
          " $3,$4,$5, CASE WHEN $2 = 'sent' THEN now() END)"
          " ON CONFLICT (notification_id, channel) DO UPDATE SET status = EXCLUDED.status,"
          " attempts = notification_deliveries.attempts + EXCLUDED.attempts,"
          " last_error = EXCLUDED.last_error, skipped_reason = EXCLUDED.skipped_reason,"
          " next_retry_at = EXCLUDED.next_retry_at,"
          " sent_at = coalesce(notification_deliveries.sent_at, EXCLUDED.sent_at)",
          notification_id, status, (error or "")[:500] or None, skipped_reason, next_retry_at)


def notification_emails(app, c, *, limit: int = 200) -> dict:
    """Entrega por e-mail os avisos cujo TIPO é `emailable` no catálogo, mais os de prioridade crítica.

    O QUE MUDOU NA v0.20.0, e por quê

    * A seleção era por três grupos escritos à mão (`billing`, `support`, `events`). Agora é o
      catálogo `notification_kinds` que decide, então incluir um tipo no e-mail é uma linha de dado
      declarada — e a apuração de denúncia, a medida de moderação e a conformidade, que travam o
      trabalho de quem recebe, deixaram de depender de a pessoa abrir o sistema para descobrir.
    * `deliver_after` é respeitado: janela de silêncio e agrupamento diário seguram o e-mail sem
      descartar o aviso.
    * A falha de envio deixou de sumir. `notification_deliveries` guarda tentativa, erro e quando
      repetir; `emailed_at` só avança quando o envio REALMENTE saiu, e depois de `retry_max`
      tentativas o estado vira `given_up` em vez de ficar tentando para sempre.

    O QUE `sent` SIGNIFICA: e-mails ACEITOS pelo servidor de envio. Não significa entregue na caixa
    da pessoa, e muito menos lido — duas coisas que a plataforma não tem como saber e por isso não
    afirma em lugar nenhum.
    """
    base = app.settings.public_base_url.rstrip("/")
    pol = c.one("SELECT retry_max, retry_backoff_minutes FROM notification_policy") or {
        "retry_max": 3, "retry_backoff_minutes": 30}
    rows = c.query(
        "SELECT n.id::text AS id, n.org_id::text AS org_id, n.user_id::text AS user_id, n.grp,"
        " n.title, n.body, n.link, n.priority,"
        " coalesce(d.attempts, 0) AS attempts"
        " FROM notifications n"
        " JOIN notification_kinds k ON k.kind = split_part(n.kind, '.', 1)"
        " LEFT JOIN notification_deliveries d ON d.notification_id = n.id AND d.channel = 'email'"
        " WHERE n.emailed_at IS NULL AND n.created_at > now() - interval '3 days'"
        "   AND n.deliver_after <= now()"
        "   AND (k.emailable OR n.priority = 'critical')"
        "   AND coalesce(d.status, 'pending') NOT IN ('given_up', 'skipped')"
        "   AND (d.next_retry_at IS NULL OR d.next_retry_at <= now())"
        " ORDER BY n.priority = 'critical' DESC, n.created_at LIMIT $1", limit)
    sent = skipped = failed = given_up = 0
    for n in rows:
        if n["user_id"]:
            to = c.query("SELECT id::text AS uid, email::text AS email FROM users WHERE id = $1 AND status = 'active' AND email_verified_at IS NOT NULL", n["user_id"])
        else:
            to = c.query("SELECT u.id::text AS uid, u.email::text AS email FROM memberships m JOIN users u ON u.id = m.user_id WHERE m.org_id = $1 AND m.role IN ('owner','admin')"
                         " AND u.status = 'active' AND u.email_verified_at IS NOT NULL", n["org_id"])
        if not to:
            _delivery(c, n["id"], status="skipped", skipped_reason="no_verified_email")
            skipped += 1
            continue
        enviados = recusados = 0
        erro: str | None = None
        for r in to:
            if not _pref(c, r["uid"], n["grp"], "email"):
                recusados += 1
                continue
            try:
                app.mailer.send(r["email"], f"[Impacto] {n['title']}", f"{n['title']}\n\n{n['body'] or ''}\n\n{base}{n['link'] or ''}\n\nVocê pode ajustar estes avisos em Conta > Notificações.\n")
                enviados += 1
            except Exception as e:  # noqa: BLE001
                erro = f"{type(e).__name__}: {e}"
        if erro:
            tentativas = int(n["attempts"]) + 1
            if tentativas >= int(pol["retry_max"]):
                _delivery(c, n["id"], status="given_up", error=erro)
                given_up += 1
            else:
                prox = c.scalar("SELECT now() + make_interval(mins => $1)",
                                int(pol["retry_backoff_minutes"]))
                _delivery(c, n["id"], status="failed", error=erro, next_retry_at=prox)
            failed += 1
            continue
        if enviados:
            _delivery(c, n["id"], status="sent")
            sent += enviados
        else:
            _delivery(c, n["id"], status="skipped", skipped_reason="preference")
            skipped += recusados
        c.run("UPDATE notifications SET emailed_at = now() WHERE id = $1", n["id"])
    return {"emails_sent": sent, "emails_skipped_by_preference": skipped,
            "emails_failed": failed, "emails_given_up": given_up,
            "note": ("`emails_sent` conta e-mails ACEITOS pelo servidor de envio. A plataforma não "
                     "afirma entrega nem leitura: não tem como saber.")}


def bulletin_dispatch(app, c) -> dict:
    """Envia o boletim a quem confirmou (duplo opt-in): só conteúdo PUBLICADO desde o último envio; um e-mail por inscrita; link de descadastro."""
    due = c.query("SELECT id::text AS id, email::text AS email, frequency, last_sent_at, topics FROM newsletter_subscriptions WHERE status = 'active'"
                  " AND (last_sent_at IS NULL OR last_sent_at < now() - CASE frequency WHEN 'weekly' THEN interval '7 days' ELSE interval '30 days' END)")
    sent = failed = 0
    for s in due:
        since = s["last_sent_at"] or datetime.now(UTC) - timedelta(days=30)
        items = c.query("SELECT title, slug, summary FROM kb_resources WHERE status = 'published' AND kind = 'bulletin' AND visibility = 'public' AND published_at > $1 ORDER BY published_at DESC LIMIT 10", since)
        if not items:
            continue
        tok = secrets.token_urlsafe(32)
        c.run("UPDATE newsletter_subscriptions SET token_hash = $2 WHERE id = $1", s["id"], _hash(tok))     # o link precisa do token ANTES do envio
        base = app.settings.public_base_url.rstrip("/") if getattr(app.settings, "public_base_url", None) else ""
        body = "Novidades da plataforma:\n\n" + "\n".join(f"- {i['title']}: {base}/ajuda/biblioteca/{i['slug']}" for i in items) + f"\n\nPara não receber mais: {base}/ajuda/boletim/cancelar?token={tok}\n"
        # `last_sent_at` só avança quando o envio REALMENTE saiu: falha de e-mail não consome o período da inscrita (reenvia no ciclo seguinte).
        if send_mail(app, c, to=s["email"], subject="[Impacto] Boletim", text=body):
            c.run("UPDATE newsletter_subscriptions SET last_sent_at = now() WHERE id = $1", s["id"])
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "due": len(due), "failed": failed}


def retention(c, months: int = 18) -> dict:
    """Analytics de conhecimento: retenção de `kb_events` (sem texto livre) — padrão 18 meses."""
    return {"kb_events_deleted": c.run("DELETE FROM kb_events WHERE at < now() - make_interval(months => $1)", months)}


# ------------------------------------------------------------------------------------------------ analytics (painel da administração)
def knowledge_analytics(c, *, days: int = 30) -> dict:
    since = f"now() - make_interval(days => {int(days)})"
    return {
        "period_days": days,
        "searches": c.scalar(f"SELECT count(*) FROM kb_events WHERE kind IN ('search','search_empty') AND at > {since}"),
        "searches_without_result": c.scalar(f"SELECT count(*) FROM kb_events WHERE kind = 'search_empty' AND at > {since}"),
        "top_topics": c.query(f"SELECT t AS topic, count(*) AS n FROM kb_events, unnest(concepts) t WHERE kind IN ('search','search_empty') AND at > {since} GROUP BY t ORDER BY n DESC LIMIT 10"),
        "gap_topics": c.query(f"SELECT t AS topic, count(*) AS n FROM kb_events, unnest(concepts) t WHERE kind IN ('search_empty','assistant_empty') AND at > {since} GROUP BY t ORDER BY n DESC LIMIT 10"),
        "top_articles": c.query("SELECT slug, title, view_count FROM kb_articles WHERE live_version_id IS NOT NULL ORDER BY view_count DESC LIMIT 10"),
        "top_downloads": c.query("SELECT slug, title, download_count FROM kb_resources WHERE status = 'published' ORDER BY download_count DESC LIMIT 10"),
        "context_help": c.query(f"SELECT ctx_key, count(*) AS n FROM kb_events WHERE kind = 'ctx_open' AND at > {since} GROUP BY 1 ORDER BY n DESC LIMIT 10"),
        "assistant": {"answered": c.scalar(f"SELECT count(*) FROM kb_events WHERE kind = 'assistant' AND at > {since}"), "no_basis": c.scalar(f"SELECT count(*) FROM kb_events WHERE kind = 'assistant_empty' AND at > {since}")},
        "tickets_from_help": c.scalar(f"SELECT count(*) FROM kb_events WHERE kind = 'ticket_from_help' AND at > {since}"),
        "feedback": c.query(f"SELECT target_type, count(*) FILTER (WHERE helpful) AS yes, count(*) FILTER (WHERE NOT helpful) AS no FROM kb_feedback WHERE created_at > {since} GROUP BY 1"),
        "feedback_reasons": c.query(f"SELECT reason, count(*) AS n FROM kb_feedback WHERE NOT helpful AND created_at > {since} GROUP BY 1 ORDER BY n DESC"),
        "low_resolution_faqs": K.low_resolution_faqs(c),
        "stale": K.stale_overview(c),
        "tickets": {"open": c.scalar("SELECT count(*) FROM support_tickets WHERE status NOT IN ('resolved','closed')"),
                    "avg_first_response_h": c.scalar(f"SELECT round(avg(extract(epoch FROM first_response_at - created_at) / 3600)::numeric, 1) FROM support_tickets WHERE first_response_at IS NOT NULL AND created_at > {since}"),
                    "avg_satisfaction": c.scalar(f"SELECT round(avg(satisfaction)::numeric, 2) FROM support_tickets WHERE satisfaction IS NOT NULL AND created_at > {since}"),
                    "overdue": c.scalar("SELECT count(*) FROM support_tickets WHERE status NOT IN ('resolved','closed') AND resolution_due < now()")},
        "recurring_tickets": recurring_candidates(c),
        "academy": {"enrollments": c.scalar(f"SELECT count(*) FROM course_enrollments WHERE started_at > {since}"), "completions": c.scalar(f"SELECT count(*) FROM course_enrollments WHERE completed_at > {since}"),
                    "certificates": c.scalar(f"SELECT count(*) FROM course_certificates WHERE issued_at > {since}")},
        "events": c.query(f"SELECT e.title, e.starts_at, count(g.*) FILTER (WHERE g.status = 'registered') AS registered, count(g.*) FILTER (WHERE g.attended) AS attended,"
                          f" round(avg(g.satisfaction)::numeric, 2) AS satisfaction FROM hub_events e LEFT JOIN hub_event_registrations g ON g.event_id = e.id WHERE e.starts_at > {since}"
                          " GROUP BY e.id ORDER BY e.starts_at DESC LIMIT 10"),
        "partnerships": c.query("SELECT status, count(*) AS n FROM partnership_requests GROUP BY status ORDER BY n DESC"),
        "demos": c.query("SELECT status, count(*) AS n FROM demo_requests GROUP BY status"),
        "privacy_note": "Buscas são registradas como hash + tópicos (sem o texto digitado); eventos são apagados após 18 meses.",
    }
