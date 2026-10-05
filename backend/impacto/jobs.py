"""Worker de rotinas (rastreio de editais, alertas, importação de fontes, antivírus pendente, validade de documentos,
encerramento de chamadas e retenção de dados).

Uso:  python -m impacto.jobs once      (executa tudo uma vez — ideal para cron/Kubernetes CronJob)
      python -m impacto.jobs loop      (laço com intervalo JOBS_INTERVAL_SECONDS, padrão 900)
Um lock consultivo garante uma única instância ativa por vez. Cada job grava job_runs (observabilidade).
Buscas salvas rodam no CONTEXTO DA ORGANIZAÇÃO dona (RLS aplicada), nunca como superusuário.
"""
from __future__ import annotations

import csv
import io
import json
import logging
import os
import sys
import time
from datetime import datetime, UTC

from .adapters.http_client import HttpClient
from .db.pool import DbContext
from .db.pq import Connection, Json
from .observability import log, setup_logging

logger = logging.getLogger("impacto.jobs")
JOB_LOCK = 726_431_002


def _run(app, name: str, fn) -> dict:
    with app.pool.tx(DbContext(system=True)) as c:
        rid = c.scalar("INSERT INTO job_runs(job, status) VALUES ($1,'running') RETURNING id", name)
    try:
        details = fn() or {}
        status = "ok"
    except Exception as exc:  # noqa: BLE001
        details, status = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}, "failed"
        log(logger, logging.ERROR, "job_failed", job=name, error=details["error"])
    with app.pool.tx(DbContext(system=True)) as c:
        c.run("UPDATE job_runs SET status = $2, details = $3::jsonb, finished_at = now() WHERE id = $1", rid, status, Json(details))
    return {"job": name, "status": status, **details}


# ------------------------------------------------------------------------------------------------ buscas salvas
def run_saved_search(c: Connection, s: dict, notify_email=None) -> int:
    """Executa uma busca salva no contexto (RLS) da organização. Retorna nº de novos editais notificados."""
    from .services import matching
    f = s["filters"] or {}
    where, vals = ["c.status = 'open'", "(c.closes_at IS NULL OR c.closes_at >= now())",
                   "NOT EXISTS (SELECT 1 FROM saved_search_hits h WHERE h.search_id = $1 AND h.call_id = c.id)"], [s["id"]]

    def add(cond, val):
        vals.append(val)
        where.append(cond.replace("?", f"${len(vals)}"))
    if f.get("q"):
        add("(c.title ILIKE '%' || ? || '%' OR c.summary ILIKE '%' || ? || '%')", str(f["q"])[:120])
    if f.get("sphere"):
        add("c.sphere = ANY(?::text[])", [x for x in str(f["sphere"]).split(",") if x][:10])
    if f.get("instrument"):
        add("c.instrument = ANY(?::text[])", [x for x in str(f["instrument"]).split(",") if x][:10])
    if f.get("cause"):
        add("(c.causes && ?::text[] OR cardinality(c.causes) = 0)", [x for x in str(f["cause"]).split(",") if x][:10])
    if f.get("territory"):
        add("(cardinality(c.territories) = 0 OR EXISTS (SELECT 1 FROM unnest(c.territories) t WHERE t = 'INT' OR ? LIKE t || '%'))", str(f["territory"]))
    if f.get("min_amount_cents"):
        add("(c.ticket_max_cents IS NULL OR c.ticket_max_cents >= ?::bigint)", int(f["min_amount_cents"]))
    rows = c.query(f"SELECT c.id::text AS id, c.title FROM calls c WHERE {' AND '.join(where)} ORDER BY c.created_at DESC LIMIT 200", *vals)
    min_score = float(f.get("min_score") or 0)
    kind = c.scalar("SELECT kind FROM organizations WHERE id = $1", s["org_id"])
    new = 0
    titles = []
    for r in rows:
        score = None
        if kind == "osc":
            m = matching.evaluate_osc_call(c, str(s["org_id"]), matching.load_call(c, r["id"]), None)
            score = m["score"]
            if m["eligibility"] == "blocked" or (min_score and (score or 0) < min_score):
                continue
        c.run("INSERT INTO saved_search_hits(search_id, call_id, org_id, score) VALUES ($1,$2,$3,$4::numeric) ON CONFLICT DO NOTHING",
              s["id"], r["id"], s["org_id"], score)
        new += 1
        titles.append(r["title"])
    c.run("UPDATE saved_searches SET last_run_at = now() WHERE id = $1", s["id"])
    if new and s["notify"]:
        c.scalar("SELECT app_notify($1, $2, 'alert', $3, $4, '/oportunidades')", s["org_id"], s["user_id"],
                 f"{new} nova(s) oportunidade(s): {s['name']}", "; ".join(titles[:5])[:1900])
        if notify_email:
            notify_email(s, new, titles)
    return new


def saved_searches_job(app) -> dict:
    total, searches = 0, 0
    with app.pool.tx(DbContext(system=True), readonly=True) as c:
        due = c.query("SELECT s.*, s.id::text AS id, s.org_id::text AS org_id, s.user_id::text AS user_id, o.kind, u.email::text AS email"
                      " FROM saved_searches s JOIN organizations o ON o.id = s.org_id JOIN users u ON u.id = s.user_id"
                      " WHERE o.status = 'active' AND u.status = 'active' AND (s.last_run_at IS NULL OR"
                      " (s.frequency = 'instant') OR (s.frequency = 'daily' AND s.last_run_at < now() - interval '20 hours') OR"
                      " (s.frequency = 'weekly' AND s.last_run_at < now() - interval '6 days'))")
    for s in due:
        def email(search, n, titles, _to=s["email"]):
            try:
                app.mailer.send(_to, f"[Impacto] {n} nova(s) oportunidade(s) — {search['name']}",
                                "Novas oportunidades compatíveis com sua busca salva:\n\n- " + "\n- ".join(titles[:10]) +
                                f"\n\nAcesse: {app.settings.public_base_url}/oportunidades")
            except Exception as exc:  # noqa: BLE001
                log(logger, logging.WARNING, "alert_email_failed", error_type=type(exc).__name__)
        # Recurso pago: confirma o direito vigente da organização antes de rodar.
        from .services.entitlements import effective
        ctx = DbContext(user_id=s["user_id"], org_id=s["org_id"], org_kind=s["kind"])
        with app.pool.tx(ctx) as c:
            ent = effective(c, s["org_id"], s["kind"])
            if "alerts.saved_search" not in ent["features"]:
                continue
            total += run_saved_search(c, s, notify_email=email)
            searches += 1
    return {"searches": searches, "new_hits": total}


# ------------------------------------------------------------------------------------------------ importação de fontes
def _get(d: dict, path: str | None):
    if not path:
        return None
    cur = d
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def parse_feed(kind: str, raw: bytes, mapping: dict) -> list[dict]:
    m = {"reference": "id", "title": "title", "url": "url", "funder_name": "funder", "summary": "summary", "closes_at": "closes_at",
         "opens_at": "opens_at", "causes": "causes", "territories": "territories", "instrument": "instrument",
         "ticket_max_cents": "ticket_max_cents", **(mapping or {})}
    items: list[dict] = []
    if kind == "json_feed":
        data = json.loads(raw)
        rows = data.get(mapping.get("_items", "items"), []) if isinstance(data, dict) else data
        for r in rows[:2000]:
            items.append({k: _get(r, v) for k, v in m.items() if not k.startswith("_")})
    elif kind == "csv_feed":
        text = raw.decode("utf-8-sig", errors="replace")
        for r in list(csv.DictReader(io.StringIO(text)))[:2000]:
            items.append({k: r.get(v) for k, v in m.items() if not k.startswith("_")})
    elif kind == "rss":
        from defusedxml import ElementTree as ET  # proteção contra XXE/billion laughs
        root = ET.fromstring(raw)
        for it in root.iter("item"):
            link = (it.findtext("link") or "").strip()
            items.append({"reference": (it.findtext("guid") or link)[:300], "title": (it.findtext("title") or "").strip(), "url": link,
                          "summary": (it.findtext("description") or "")[:2000], "funder_name": mapping.get("_funder_name")})
    return items


def import_source(app, s: dict, http: HttpClient | None = None) -> dict:
    if not s["active"]:
        return {"status": "inactive", "message": "Ative a fonte após verificar os termos de uso"}
    http = http or HttpClient(retries=2)

    def run():
        status, _, raw = http.request("GET", s["url"], timeout=30, headers={"User-Agent": "ImpactoBot/1.0 (+contato no site)"})
        if status != 200:
            raise RuntimeError(f"HTTP {status}")
        items = parse_feed(s["kind"], raw, s["mapping"] or {})
        created = updated = skipped = 0
        with app.pool.tx(DbContext(system=True)) as c:
            for it in items:
                title, url, ref = (it.get("title") or "").strip()[:300], (it.get("url") or "").strip(), str(it.get("reference") or it.get("url") or "")[:300]
                if len(title) < 3 or not ref or (url and not url.startswith(("http://", "https://"))):
                    skipped += 1
                    continue
                closes = it.get("closes_at") or None
                try:
                    closes = datetime.fromisoformat(str(closes)).astimezone(UTC) if closes else None
                except ValueError:
                    closes = None
                causes = it.get("causes") or []
                causes = [x.strip() for x in (causes.split(",") if isinstance(causes, str) else causes) if x and str(x).strip()][:10]
                terr = it.get("territories") or []
                terr = [x.strip() for x in (terr.split(",") if isinstance(terr, str) else terr) if x and str(x).strip()][:20]
                instrument = it.get("instrument") if it.get("instrument") in ("grant", "edital", "fund", "financing", "prize", "incentive_law",
                                                                              "donation", "other") else "edital"
                status_call = "open" if (closes is None or closes > datetime.now(UTC)) else "closed"
                r = c.one("INSERT INTO calls(source_type, source_id, source_reference, sphere, instrument, funder_name, title, summary, url, causes,"
                          " territories, closes_at, status, managed_on_platform, last_verified_at) VALUES ('imported',$1,$2,$3,$4,$5,$6,$7,$8,"
                          " $9::text[],$10::text[],$11::timestamptz,$12,false, now()) ON CONFLICT (source_id, source_reference) DO UPDATE SET"
                          " title = EXCLUDED.title, summary = EXCLUDED.summary, url = EXCLUDED.url, closes_at = EXCLUDED.closes_at,"
                          " status = EXCLUDED.status, last_verified_at = now() RETURNING (xmax = 0) AS inserted",
                          s["id"], ref, s["sphere"], instrument, (it.get("funder_name") or s["name"])[:200], title,
                          (it.get("summary") or "")[:2000] or None, url or None, causes, terr, closes, status_call)
                if r["inserted"]:
                    created += 1
                else:
                    updated += 1
            c.run("UPDATE call_sources SET last_run_at = now(), last_status = 'ok', last_error = NULL WHERE id = $1", s["id"])
        return {"source": s["name"], "items": len(items), "created": created, "updated": updated, "skipped": skipped}

    res = _run(app, f"import:{s['name']}", run)
    if res["status"] == "failed":
        with app.pool.tx(DbContext(system=True)) as c:
            c.run("UPDATE call_sources SET last_run_at = now(), last_status = 'failed', last_error = $2 WHERE id = $1", s["id"], res.get("error"))
    return res


def import_all(app) -> dict:
    with app.pool.tx(DbContext(system=True), readonly=True) as c:
        sources = c.query("SELECT * FROM call_sources WHERE active")
    return {"sources": [import_source(app, s) for s in sources]}


# ------------------------------------------------------------------------------------------------ manutenção
def pending_scans(app) -> dict:
    if app.antivirus.name == "none":
        return {"skipped": "antivírus não configurado"}
    done = 0
    with app.pool.tx(DbContext(system=True), readonly=True) as c:
        docs = c.query("SELECT id::text AS id, storage_key FROM documents WHERE status = 'pending_scan' AND deleted_at IS NULL LIMIT 200")
    for d in docs:
        status, note = app.antivirus.scan(app.storage.get(d["storage_key"]))
        if status == "pending_scan":
            continue
        with app.pool.tx(DbContext(system=True)) as c:
            c.run("UPDATE documents SET status = $2, scan_engine = $3, scanned_at = now() WHERE id = $1", d["id"], status, app.antivirus.name)
        if status == "infected":
            app.storage.delete(d["storage_key"])
        done += 1
    return {"scanned": done}


def document_expiry(app) -> dict:
    with app.pool.tx(DbContext(system=True)) as c:
        rows = c.query("SELECT d.org_id::text AS org_id, d.title, d.valid_until FROM documents d WHERE d.deleted_at IS NULL"
                       " AND d.valid_until IN (current_date + 30, current_date + 7, current_date)")
        for r in rows:
            c.scalar("SELECT app_notify($1, NULL, 'document', $2, $3, '/documentos')", r["org_id"], f"Documento vencendo: {r['title']}",
                     f"Validade em {r['valid_until']}. Envie a versão atualizada para manter a elegibilidade.")
    return {"notified": len(rows)}


def close_calls(app) -> dict:
    with app.pool.tx(DbContext(system=True)) as c:
        n = c.run("UPDATE calls SET status = 'closed' WHERE status = 'open' AND closes_at < now()")
    return {"closed": n}


def retention(app) -> dict:
    """Política de retenção (docs/LGPD.md)."""
    with app.pool.tx(DbContext(system=True)) as c:
        return {
            "rate_events": c.run("DELETE FROM rate_events WHERE at < now() - interval '2 days'"),
            "auth_tokens": c.run("DELETE FROM auth_tokens WHERE expires_at < now() - interval '7 days'"),
            "oidc_states": c.run("DELETE FROM oidc_states WHERE expires_at < now()"),
            "sessions": c.run("DELETE FROM sessions WHERE refresh_expires_at < now() - interval '30 days'"),
            "ai_usage": c.run("DELETE FROM ai_usage WHERE created_at < now() - interval '13 months'"),
            "notifications": c.run("DELETE FROM notifications WHERE read_at IS NOT NULL AND read_at < now() - interval '180 days'"),
        }


def risk_scan(app) -> dict:
    """Sinais de risco/antifraude para revisão humana (services/risk.py). Não bloqueia ninguém automaticamente."""
    from .services import risk
    with app.pool.tx(DbContext(system=True)) as c:
        return risk.scan(c)


def billing_lifecycle(app) -> dict:
    from .services import monetization
    return monetization.lifecycle_job(app)


def hub_ops(app) -> dict:
    """Central de Conhecimento: escalonamento de SLA, lembretes de evento, envio do boletim (duplo opt-in), e-mails de cobrança/teste/suporte/eventos e retenção de analytics (18 meses)."""
    from .services import hub
    with app.pool.tx(DbContext(system=True)) as c:
        return {**hub.sla_escalation(c), **hub.event_reminders(c), **hub.bulletin_dispatch(app, c), **hub.notification_emails(app, c), **hub.retention(c)}


JOBS = [("close_calls", close_calls), ("import_sources", import_all), ("saved_searches", saved_searches_job),
        ("pending_scans", pending_scans), ("document_expiry", document_expiry), ("risk_scan", risk_scan), ("retention", retention), ("billing_lifecycle", billing_lifecycle), ("hub_ops", hub_ops)]


def run_once(app) -> list[dict]:
    with app.pool.connection() as lockc:
        if not lockc.scalar("SELECT pg_try_advisory_lock($1)", JOB_LOCK):
            return [{"status": "skipped", "reason": "outra instância do worker em execução"}]
        try:
            return [_run(app, name, lambda fn=fn: fn(app)) for name, fn in JOBS]
        finally:
            lockc.scalar("SELECT pg_advisory_unlock($1)", JOB_LOCK)


def main(argv: list[str]) -> int:
    from .app import AppState
    from .config import load_settings
    s = load_settings()
    setup_logging(s.log_level, s.version, s.env)
    app = AppState(s)
    mode = argv[0] if argv else "once"
    if mode == "once":
        print(json.dumps(run_once(app), default=str, ensure_ascii=False))
        return 0
    interval = int(os.getenv("JOBS_INTERVAL_SECONDS", "900"))
    while True:
        res = run_once(app)
        log(logger, logging.INFO, "jobs_cycle", results=res)
        time.sleep(interval)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
