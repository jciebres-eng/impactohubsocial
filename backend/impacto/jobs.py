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
from .db.pq import Connection
from .observability import log, setup_logging

logger = logging.getLogger("impacto.jobs")
JOB_LOCK = 726_431_002


def _run(app, name: str, fn) -> dict:
    """Executa a rotina e registra a execução em `ops_job_runs` — a ÚNICA trilha (v0.22.0).

    Até a v0.21.0 esta função mantinha a sua própria tabela (`job_runs`), sem duração e sem campo
    de erro, enquanto `ops/runs.py` mantinha outra com as duas coisas. Eram duas respostas
    diferentes para "o backup rodou?", e a que cobria 22 tarefas era a que menos sabia.
    """
    from .ops import runs as RUNS
    with app.pool.tx(DbContext(system=True)) as c:
        with RUNS.record(c, name) as execucao:
            try:
                details = fn() or {}
                status = "ok"
            except Exception as exc:  # noqa: BLE001
                details, status = {"error": f"{type(exc).__name__}: {str(exc)[:300]}"}, "failed"
                log(logger, logging.ERROR, "job_failed", job=name, error=details["error"])
                execucao["error"] = details["error"]
            execucao["status"], execucao["detail"] = status, details
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

    # O nome da tarefa é a IDENTIDADE dela, não a identidade mais o parâmetro. Até a v0.21.0 isto
    # era `f"import:{nome da fonte}"`: cada fonte criava uma "tarefa" nova na trilha, com texto
    # livre vindo do cadastro, e não havia como perguntar "a importação rodou?" — só "a importação
    # da fonte X rodou?", para um X que ninguém sabia enumerar. A fonte vai no DETALHE, que é onde
    # se guarda parâmetro, e o nome passou a caber na restrição de formato da trilha.
    res = _run(app, "import_source", run)
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
    unreadable: list[str] = []
    with app.pool.tx(DbContext(system=True), readonly=True) as c:
        docs = c.query("SELECT id::text AS id, storage_key FROM documents WHERE status = 'pending_scan' AND deleted_at IS NULL LIMIT 200")
    for d in docs:
        # UM ARQUIVO ILEGÍVEL NÃO PODE PARAR A FILA. Antes, um único objeto ausente no storage (404
        # do S3/R2 — por exemplo, registro criado antes de o bucket existir) derrubava a rotina
        # inteira e NENHUM outro documento era escaneado. O documento continua em quarentena
        # (`pending_scan`, download bloqueado): nada é marcado como limpo sem ter sido lido.
        try:
            data = app.storage.get(d["storage_key"])
        except Exception as exc:  # noqa: BLE001 - qualquer falha de leitura mantém a quarentena
            unreadable.append(d["id"])
            log(logger, logging.WARNING, "pending_scan_unreadable", document_id=d["id"], error=str(exc)[:200])
            continue
        status, note = app.antivirus.scan(data)
        if status == "pending_scan":
            continue
        with app.pool.tx(DbContext(system=True)) as c:
            c.run("UPDATE documents SET status = $2, scan_engine = $3, scanned_at = now() WHERE id = $1", d["id"], status, app.antivirus.name)
        if status == "infected":
            app.storage.delete(d["storage_key"])
        done += 1
    return {"scanned": done, "unreadable": len(unreadable), "unreadable_ids": unreadable[:20]}


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
            # O corpo do webhook pode conter nome e e-mail do pagador. O EVENTO fica para sempre
            # (idempotência e reconciliação); o conteúdo dele sai depois de 18 meses (v0.17.0).
            "billing_event_payloads": c.run("UPDATE billing_events SET payload = '{}'::jsonb"
                                            " WHERE received_at < now() - interval '18 months'"
                                            " AND payload <> '{}'::jsonb"),
            # IP de aceite vencido: a prova é o documento, a versão e o hash do texto — não o IP.
            "acceptance_ips": c.run("UPDATE legal_acceptances SET ip = NULL, user_agent = NULL"
                                    " WHERE accepted_at < now() - interval '18 months'"
                                    " AND (ip IS NOT NULL OR user_agent IS NOT NULL)"),
        }


def risk_scan(app) -> dict:
    """Sinais de risco/antifraude para revisão humana (services/risk.py). Não bloqueia ninguém automaticamente."""
    from .services import risk
    with app.pool.tx(DbContext(system=True)) as c:
        return risk.scan(c)


def commercial_sweep(app) -> dict:
    """Período de concessão: encerra o que venceu e avisa 90/60/30/7/1 dia antes, mais o semanal.

    v0.27.0 (ADR-341): `billing_lifecycle` (trial de 14 dias e ciclo de assinatura) foi removido com a
    assinatura. Nenhum job cobra nada: este só avisa e devolve a conta ao acesso livre do núcleo.
    """
    from .services import free_period as FP
    with app.pool.tx(DbContext(system=True)) as c:
        return FP.sweep(c)


def usage_alerts(app) -> dict:
    """Alertas de 70%, 90% e 100% do limite do plano, uma vez por limiar e por período.

    Varre só as organizações ativas: um alerta é um aviso para alguém decidir alguma coisa, e não
    há ninguém para decidir numa conta encerrada.
    """
    from .services import usage as U
    enviados = 0
    with app.pool.tx(DbContext(system=True)) as c:
        for org in c.query("SELECT id::text AS id, kind FROM organizations WHERE status = 'active'"):
            enviados += U.check_alerts(c, org["id"], org["kind"])
    return {"alerts": enviados}


def hub_ops(app) -> dict:
    """Central de Conhecimento: escalonamento de SLA, lembretes de evento, envio do boletim (duplo opt-in), e-mails de cobrança/teste/suporte/eventos e retenção de analytics (18 meses)."""
    from .services import hub
    with app.pool.tx(DbContext(system=True)) as c:
        return {**hub.sla_escalation(c), **hub.event_reminders(c), **hub.bulletin_dispatch(app, c), **hub.notification_emails(app, c), **hub.retention(c)}


def integration_ops(app) -> dict:
    """Integration Hub: executa jobs devidos, entrega webhooks de saída, verifica saúde das conexões ativas e aplica retenção."""
    from .integrations import events as EV, hub as HUB

    def run():
        with app.pool.tx(DbContext(system=True)) as c:
            jobs = HUB.process_due(app, c)
            deliveries = EV.deliver_pending(app, c)
            stale = c.query("SELECT id::text AS id FROM integration_connections WHERE status = 'active'"
                            " AND (last_health_at IS NULL OR last_health_at < now() - interval '30 minutes') LIMIT 20")
            for row in stale:
                HUB.health_check(app, c, row["id"])          # somente leitura; grava o estado na conexão
            kept = EV.retention(c)
        return {"jobs": jobs, "deliveries": deliveries, "health_checked": len(stale), **kept}

    return _run(app, "integration_ops", run)


def payment_deadlines(app) -> dict:
    """Fecha PIX e boleto vencidos.

    Instrução de pagamento com prazo passado que continua `pending` é a pior mentira possível neste
    módulo: a organização vê uma cobrança "aguardando pagamento" que nenhum banco aceita mais. O
    fechamento é do grafo (`pending -> expired`), e não um UPDATE solto.
    """
    from .economics import payments as PAY
    with app.pool.tx(DbContext(system=True)) as c:
        return PAY.expire_due(c)


def reputation_timeline(app) -> dict:
    """Congela um ponto da linha do tempo de reputação por organização ativa.

    A reputação corrente é sempre CALCULADA; este job só registra o ponto histórico, para que a
    evolução exista e para que uma correção futura não apague o que foi publicado antes dela.
    Organizações sem nenhuma observação não geram ponto: linha do tempo de quem não tem base é
    ruído com aparência de dado.
    """
    from .impact import reputation as REP
    done = 0
    with app.pool.tx(DbContext(system=True)) as c:
        orgs = [r["id"] for r in c.query(
            "SELECT id::text AS id FROM organizations WHERE status = 'active'"
            "   AND kind <> 'platform' ORDER BY created_at LIMIT 500")]
    for org_id in orgs:
        with app.pool.tx(DbContext(system=True)) as c:
            prof = REP.profile(c, org_id=org_id, privileged=True)
            if not any(d["observations"] for d in prof["dimensions"]):
                continue
            REP.snapshot(c, org_id=org_id)
            done += 1
    return {"organizations": len(orgs), "recorded": done}


def enforcement_expiry(app) -> dict:
    """Encerra medidas vencidas.

    `enforcement.expire_due()` existia desde a v0.16.0 e NUNCA foi chamada: a situação `expired`
    jamais era atingida, então uma suspensão "de 30 dias" valia para sempre no banco. Com a v0.20.0 a
    medida passou a restringir de verdade, e uma medida que não expira vira punição perpétua.
    """
    from .network import enforcement as ENF
    with app.pool.tx(DbContext(system=True)) as c:
        return ENF.expire_due(c)


def backup_job(app) -> dict:
    """Backup agendado. Roda no executor que já existe, em vez de um timer que ninguém exercita.

    O intervalo e a janela são da própria tarefa (ops.backup), porque este laço chama todas as tarefas
    a cada ciclo: sem janela própria, o backup rodaria a cada quinze minutos.
    """
    from .ops import backup as BK
    with app.pool.tx(DbContext(system=True)) as c:
        return BK.run(c, app.settings)


def email_canary_job(app) -> dict:
    """Canário de e-mail: prova periódica de que o envio funciona."""
    from .ops import email_canary as EC
    with app.pool.tx(DbContext(system=True)) as c:
        return EC.run(c, app)


def proposal_expiry(app) -> dict:
    """Expira propostas vencidas — e, com isso, AVISA as duas partes.

    `proposals.expire_due()` existe desde a v0.16.0 e nunca teve chamador. A consequência não era só
    um estado parado: `transition(..., to="expired")` é o que emite `Proposal.expired`, então a
    proposta com prazo vencido ficava em `sent` para sempre e ninguém era avisado de nada. O aviso
    estava escrito, testado e inalcançável — o mesmo defeito de `enforcement.expire_due`.
    """
    from .network import proposals as PROP
    with app.pool.tx(DbContext(system=True)) as c:
        return PROP.expire_due(c)


def listing_expiry(app) -> dict:
    """Expira anúncios vencidos. `marketplace.expire_due()` também nunca teve chamador."""
    from .network import marketplace as MKT
    with app.pool.tx(DbContext(system=True)) as c:
        return MKT.expire_due(c)


def seal_recheck(app) -> dict:
    """Reavalia selos ativos e revoga os que deixaram de satisfazer o critério.

    `seals.recheck()` nunca teve chamador. O próprio docstring dela diz que selo que continua
    aparecendo depois de o critério cair é pior que não ter selo — e era exatamente o que acontecia,
    porque nada a executava. Um selo é uma afirmação da plataforma sobre terceiros: mantê-lo sem
    reavaliar é a plataforma atestando o que não é mais verdade.
    """
    from .impact import seals as SEALS
    with app.pool.tx(DbContext(system=True)) as c:
        return SEALS.recheck(c)


def deadline_sweep(app) -> dict:
    """Avisa os prazos que cruzaram D-30, D-7 ou D-1. Ver `impacto.ops.deadlines`."""
    from .ops import deadlines as DL
    with app.pool.tx(DbContext(system=True)) as c:
        return DL.sweep(c)


def financial_ops(app) -> dict:
    """v0.34.0 — rotina financeira (cenários 33, 35, 21, 25 e conciliação periódica). Cada parte numa transação própria:
    uma falha não impede as outras. Nenhuma parte cobra dinheiro, bloqueia acesso ou mexe em recurso de terceiro.

    1. reprocessa eventos assinados que ficaram `failed`/`received` (o processo caiu entre gravar e aplicar);
    2. marca vencidas as obrigações faturadas além do prazo (vencida não bloqueia nada — ADR-381);
    3. concilia campanhas com movimento recente (no sandbox, contra os eventos assinados);
    4. cria as tentativas de doação recorrente vencidas — só se a recorrência estiver ligada (hoje recusada pela configuração)."""
    from .services import donations as DON
    from .services import reconciliation as RECON
    from .services import remuneration as REM
    out: dict = {}
    for nome, fn in (("events", lambda c: DON.reprocess_pending_events(c)),
                     ("overdue", lambda c: {"marked": REM.mark_overdue(c)}),
                     ("reconciliation", lambda c: RECON.run_periodic(c)),
                     ("recurring", lambda c: DON.run_recurring_cycle(c, settings=app.settings, cipher=app.cipher))):
        try:
            with app.pool.tx(DbContext(system=True)) as c:
                out[nome] = fn(c)
        except Exception as exc:  # noqa: BLE001 — registrado no detalhe da execução; a próxima rodada tenta de novo
            out[nome] = {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    return out


JOBS = [("close_calls", close_calls), ("payment_deadlines", payment_deadlines), ("integration_ops", integration_ops), ("import_sources", import_all), ("saved_searches", saved_searches_job),
        ("pending_scans", pending_scans), ("document_expiry", document_expiry), ("risk_scan", risk_scan), ("retention", retention), ("commercial_sweep", commercial_sweep), ("usage_alerts", usage_alerts), ("hub_ops", hub_ops), ("reputation_timeline", reputation_timeline),
        # v0.19.0 — operação: as duas tarefas que faltavam para publicar.
        ("backup", backup_job), ("email_canary", email_canary_job),
        ("enforcement_expiry", enforcement_expiry),
        # v0.20.0 — três funções que existiam e nunca eram chamadas. Ver docstrings acima.
        ("proposal_expiry", proposal_expiry), ("listing_expiry", listing_expiry),
        ("seal_recheck", seal_recheck), ("deadline_sweep", deadline_sweep),
        # v0.34.0 — ecossistema financeiro: reprocessamento, vencimento, conciliação periódica e recorrência.
        ("financial_ops", financial_ops)]


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
