"""Proveniência, direitos de uso, retirada e fila editorial da camada de conhecimento (v0.29.0, migração 0069).

Regras (aplicadas pelo banco; aqui só a orquestração):
  * uma FONTE tem classe editorial O/A/V/H/D, jurisdição, vigência, licença e DIREITOS por operação; 'unknown' nunca libera nada;
  * uma CITAÇÃO liga a versão em rascunho a uma fonte, com localizador e, se houver direito de trecho, o trecho com hash;
  * RETIRAR um conteúdo exige motivo e é terminal: sai da busca, do assistente e do sitemap; reativar = nova versão;
  * lacunas (busca sem resultado, assistente sem base, 'não ajudou', conteúdo vencido, relato de erro) viram ITENS DE TRABALHO
    com dedupe — nunca texto livre da busca (ADR-043), só hash e tópicos.
"""
from __future__ import annotations

import hashlib
import json

from ..http import ApiError, not_found

RIGHT_OPS = ("store", "index", "excerpt", "summarize", "translate", "embed", "send_external", "train", "redistribute")
KLASS_LABEL = {"O": "Obrigação normativa", "A": "Autoridade / orientação", "V": "Padrão voluntário / boa prática",
               "H": "Hipótese de produto", "D": "Decisão / dependência pendente"}
OBJECT_TABLE = {"article_version": "kb_article_versions", "faq": "kb_faqs", "resource": "kb_resources"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------------------------ fontes
def source_row(r: dict) -> dict:
    r = dict(r)
    r["klass_label"] = KLASS_LABEL.get(r.get("klass"), r.get("klass"))
    rights = r.get("rights") or {}
    if isinstance(rights, str):
        rights = json.loads(rights)
    r["rights"] = {op: rights.get(op, "unknown") for op in RIGHT_OPS}
    r["usable_for"] = [op for op in RIGHT_OPS if r["rights"][op] == "allowed" and r.get("status") == "active"]
    return r


def list_sources(c, *, klass: str | None = None, status: str = "active", limit: int = 100, offset: int = 0) -> list[dict]:
    args: list = [limit, offset]
    where = ["true"]
    if status:
        args.append(status)
        where.append(f"status = ${len(args)}")
    if klass:
        args.append(klass)
        where.append(f"klass = ${len(args)}")
    rows = c.query("SELECT id::text AS id, key, title, publisher, url, effective_url, source_type, klass, jurisdiction, language, published_on, consulted_on,"
                   " effective_from, effective_until, license, rights, verification, verified_by::text AS verified_by, verified_at, review_due, content_sha256,"
                   " supersedes_id::text AS supersedes_id, limitations, confidence, status, retraction_reason, note, created_at"
                   f" FROM kb_sources WHERE {' AND '.join(where)} ORDER BY klass, key LIMIT $1 OFFSET $2", *args)
    return [source_row(r) for r in rows]


def get_source(c, key_or_id: str) -> dict:
    r = c.one("SELECT id::text AS id, key, title, publisher, url, effective_url, source_type, klass, jurisdiction, language, published_on, consulted_on,"
              " effective_from, effective_until, license, rights, verification, verified_by::text AS verified_by, verified_at, review_due, content_sha256,"
              " supersedes_id::text AS supersedes_id, limitations, confidence, status, retraction_reason, note, created_by::text AS created_by, created_at"
              " FROM kb_sources WHERE key = $1 OR id::text = $1", key_or_id)
    if not r:
        raise not_found("Fonte")
    out = source_row(r)
    out["cited_by"] = c.query("SELECT ct.object_type, ct.object_id::text AS object_id, ct.locator, (ct.excerpt IS NOT NULL) AS has_excerpt FROM kb_citations ct"
                              " WHERE ct.source_id = $1 ORDER BY ct.created_at DESC LIMIT 50", r["id"])
    return out


def create_source(c, *, actor: str, data: dict) -> dict:
    rights = {op: (data.get("rights") or {}).get(op, "unknown") for op in RIGHT_OPS}
    row = c.one("INSERT INTO kb_sources (key, title, publisher, url, effective_url, source_type, klass, jurisdiction, language, published_on, consulted_on,"
                " effective_from, effective_until, license, rights, review_due, content_sha256, supersedes_id, limitations, note, created_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb,$16,$17,$18,$19,$20,$21) RETURNING id::text AS id, key",
                data["key"], data["title"], data.get("publisher"), data.get("url"), data.get("effective_url"), data["source_type"], data["klass"],
                data.get("jurisdiction"), data.get("language") or "pt-BR", data.get("published_on"), data.get("consulted_on"), data.get("effective_from"),
                data.get("effective_until"), data.get("license"), json.dumps(rights), data.get("review_due"), data.get("content_sha256"),
                data.get("supersedes_id"), data.get("limitations"), data.get("note"), actor)
    c.run("INSERT INTO content_history(object_type, object_id, from_status, to_status, actor_id, note) VALUES ('source', $1, NULL, 'registered', $2, $3)",
          row["id"], actor, f"classe {data['klass']}")
    return row


def verify_source(c, key_or_id: str, *, actor: str, verification: str, note: str | None, review_due=None) -> dict:
    s = c.one("SELECT id::text AS id, created_by::text AS created_by, verification FROM kb_sources WHERE key = $1 OR id::text = $1", key_or_id)
    if not s:
        raise not_found("Fonte")
    if verification == "verified" and s["created_by"] == actor:
        raise ApiError(403, "four_eyes", "Quem registrou a fonte não pode verificá-la: peça a conferência de outra pessoa")
    c.run("UPDATE kb_sources SET verification = $2, verified_by = CASE WHEN $2 = 'verified' THEN $3::uuid ELSE verified_by END,"
          " verified_at = CASE WHEN $2 = 'verified' THEN now() ELSE verified_at END, review_due = coalesce($4, review_due),"
          " confidence = CASE WHEN $2 = 'verified' THEN 'reviewed' WHEN $2 = 'disputed' THEN 'disputed' ELSE confidence END WHERE id = $1",
          s["id"], verification, actor, review_due)
    c.run("INSERT INTO content_history(object_type, object_id, from_status, to_status, actor_id, note) VALUES ('source', $1, $2, $3, $4, $5)",
          s["id"], s["verification"], verification, actor, note)
    return {"id": s["id"], "verification": verification}


def retract_source(c, key_or_id: str, *, actor: str, reason: str) -> dict:
    s = c.one("SELECT id::text AS id, status FROM kb_sources WHERE key = $1 OR id::text = $1", key_or_id)
    if not s:
        raise not_found("Fonte")
    if len((reason or "").strip()) < 5:
        raise ApiError(422, "reason_required", "Informe o motivo da retirada da fonte")
    c.run("UPDATE kb_sources SET status = 'retracted', retraction_reason = $2 WHERE id = $1", s["id"], reason)
    c.run("INSERT INTO content_history(object_type, object_id, from_status, to_status, actor_id, note) VALUES ('source', $1, $2, 'retracted', $3, $4)",
          s["id"], s["status"], actor, reason)
    # todo conteúdo publicado que cita a fonte vira item de trabalho (não é retirado automaticamente: decisão editorial)
    for ct in c.query("SELECT DISTINCT object_type, object_id::text AS object_id FROM kb_citations WHERE source_id = $1", s["id"]):
        open_work(c, "retraction_followup", f"retraction_followup:{ct['object_type']}:{ct['object_id']}", ref_type=_ref_type(ct["object_type"]),
                  ref_id=ct["object_id"], details={"source_id": s["id"], "reason": reason[:200]})
    return {"id": s["id"], "status": "retracted"}


def _ref_type(object_type: str) -> str:
    return {"article_version": "article", "faq": "faq", "resource": "resource"}[object_type]


# ------------------------------------------------------------------------------------------------ citações
def add_citation(c, *, actor: str, object_type: str, object_id: str, source: str, locator: str | None, excerpt: str | None, claim: str | None) -> dict:
    src = c.one("SELECT id::text AS id, status, rights FROM kb_sources WHERE key = $1 OR id::text = $1", source)
    if not src:
        raise not_found("Fonte")
    if src["status"] != "active":
        raise ApiError(409, "source_retracted", "A fonte foi retirada; registre uma fonte nova")
    if object_type not in OBJECT_TABLE or not c.one(f"SELECT 1 FROM {OBJECT_TABLE[object_type]} WHERE id = $1", object_id):
        raise not_found("Conteúdo")
    if excerpt is not None:
        rights = src["rights"] if isinstance(src["rights"], dict) else json.loads(src["rights"])
        if rights.get("excerpt") != "allowed":
            raise ApiError(403, "excerpt_not_allowed", "Esta fonte não tem direito de trecho registrado como permitido: cite por localizador, sem transcrever")
    row = c.one("INSERT INTO kb_citations (object_type, object_id, source_id, locator, excerpt, excerpt_sha256, claim, created_by)"
                " VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING id, created_at",
                object_type, object_id, src["id"], locator, excerpt, _sha(excerpt) if excerpt is not None else None, claim, actor)
    return {"id": row["id"], "source_id": src["id"], "has_excerpt": excerpt is not None}


def citations_for(c, object_type: str, object_id: str) -> list[dict]:
    """Citações de uma versão/FAQ/recurso com os dados da fonte que o leitor precisa (classe, vigência, verificação)."""
    rows = c.query("SELECT ct.id, ct.locator, ct.excerpt, ct.excerpt_sha256, ct.claim, s.id::text AS source_id, s.key, s.title, s.publisher, s.url, s.klass,"
                   " s.jurisdiction, s.published_on, s.effective_from, s.effective_until, s.verification, s.verified_at, s.status AS source_status, s.license"
                   " FROM kb_citations ct JOIN kb_sources s ON s.id = ct.source_id WHERE ct.object_type = $1 AND ct.object_id = $2 ORDER BY ct.id", object_type, object_id)
    out = []
    for r in rows:
        r = dict(r)
        r["klass_label"] = KLASS_LABEL.get(r["klass"])
        r["notices"] = []
        if r["source_status"] != "active":
            r["notices"].append("fonte retirada")
        if r["verification"] in ("unverified", "disputed", "expired"):
            r["notices"].append({"unverified": "fonte ainda não conferida por outra pessoa", "disputed": "fonte em disputa", "expired": "fonte vencida"}[r["verification"]])
        if r["klass"] in ("H", "D"):
            r["notices"].append("não é norma: " + KLASS_LABEL[r["klass"]].lower())
        out.append(r)
    return out


# ------------------------------------------------------------------------------------------------ retirada de conteúdo
def retract(c, object_type: str, object_id: str, *, actor: str, reason: str) -> dict:
    if object_type not in OBJECT_TABLE:
        raise not_found("Tipo")
    if len((reason or "").strip()) < 5:
        raise ApiError(422, "reason_required", "Informe o motivo da retirada (fica público no histórico editorial)")
    table = OBJECT_TABLE[object_type]
    row = c.one(f"SELECT id::text AS id, status FROM {table} WHERE id = $1 FOR UPDATE", object_id)
    if not row:
        raise not_found("Conteúdo")
    if row["status"] == "retracted":
        return {"id": object_id, "status": "retracted", "unchanged": True}
    c.run(f"UPDATE {table} SET status = 'retracted', retraction_reason = $2, retracted_by = $3, retracted_at = now() WHERE id = $1", object_id, reason, actor)
    c.run("INSERT INTO content_history(object_type, object_id, from_status, to_status, actor_id, note) VALUES ($1,$2,$3,'retracted',$4,$5)",
          object_type, object_id, row["status"], actor, reason)
    # feedback/itens abertos sobre o conteúdo retirado são encerrados pela retirada
    c.run("UPDATE kb_work_items SET status = 'done', resolution = 'conteúdo retirado: ' || left($3, 200), resolved_by = $2, resolved_at = now()"
          " WHERE status IN ('open','in_progress') AND ref_type = $4 AND ref_id = $1", object_id, actor, reason, _ref_type(object_type))
    return {"id": object_id, "from": row["status"], "status": "retracted"}


# ------------------------------------------------------------------------------------------------ fila editorial
def open_work(c, kind: str, dedupe: str, *, ref_type: str | None = None, ref_id: str | None = None, topic: str | None = None,
              ctx_key: str | None = None, details: dict | None = None, reporter: str | None = None) -> int | None:
    try:
        return c.scalar("SELECT kb_work_open($1,$2,$3,$4,$5,$6,$7::jsonb,$8::uuid)", kind, dedupe[:200], ref_type, ref_id, topic, ctx_key,
                        json.dumps(details or {}, ensure_ascii=False, default=str), reporter)
    except Exception:  # noqa: BLE001 — a fila nunca derruba a busca
        return None


def work_items(c, *, status: str | None = "open", kind: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    args: list = [limit, offset]
    where = ["true"]
    if status:
        args.append(status)
        where.append(f"status = ${len(args)}")
    if kind:
        args.append(kind)
        where.append(f"kind = ${len(args)}")
    items = c.query("SELECT id, kind, ref_type, ref_id, topic, ctx_key, occurrences, details, reporter_id::text AS reporter_id, status, assigned_to::text AS assigned_to,"
                    f" resolution, resolved_at, created_at, updated_at FROM kb_work_items WHERE {' AND '.join(where)} ORDER BY occurrences DESC, updated_at DESC LIMIT $1 OFFSET $2", *args)
    counts = {r["kind"]: int(r["n"]) for r in c.query("SELECT kind, count(*) AS n FROM kb_work_items WHERE status IN ('open','in_progress') GROUP BY kind")}
    return {"items": items, "open_by_kind": counts, "total_open": sum(counts.values())}


def resolve_work(c, item_id: int, *, actor: str, status: str, resolution: str | None, assigned_to: str | None = None) -> dict:
    row = c.one("SELECT id, status FROM kb_work_items WHERE id = $1 FOR UPDATE", item_id)
    if not row:
        raise not_found("Item")
    if status in ("done", "dismissed") and len((resolution or "").strip()) < 5:
        raise ApiError(422, "resolution_required", "Diga o que foi feito (ou por que o item foi dispensado)")
    c.run("UPDATE kb_work_items SET status = $2, resolution = CASE WHEN $2 IN ('done','dismissed') THEN $3 ELSE resolution END,"
          " resolved_by = CASE WHEN $2 IN ('done','dismissed') THEN $4::uuid ELSE NULL END, resolved_at = CASE WHEN $2 IN ('done','dismissed') THEN now() ELSE NULL END,"
          " assigned_to = coalesce($5::uuid, assigned_to) WHERE id = $1", item_id, status, resolution, actor, assigned_to)
    return {"id": item_id, "from": row["status"], "status": status}


def report_incorrect(c, *, reporter: str | None, target_type: str, target_id: str, what: str, ctx_key: str | None) -> dict:
    exists = {"article": "SELECT 1 FROM kb_articles WHERE id = $1 AND live_version_id IS NOT NULL", "faq": "SELECT 1 FROM kb_faqs WHERE id = $1 AND status = 'published'",
              "resource": "SELECT 1 FROM kb_resources WHERE id = $1 AND status = 'published'"}.get(target_type)
    if not exists or not c.one(exists, target_id):
        raise not_found("Conteúdo")
    wid = open_work(c, "incorrect_report", f"incorrect_report:{target_type}:{target_id}", ref_type=target_type, ref_id=target_id, ctx_key=ctx_key,
                    details={"what": what[:1000]}, reporter=reporter)
    return {"recorded": wid is not None, "work_item_id": wid,
            "message": "Obrigado. O relato entrou na fila editorial e será revisado por uma pessoa; a informação atual continua visível até a revisão."}


def sweep_stale(c) -> dict:
    """Conteúdo com revisão atrasada ou validade vencida vira item de trabalho (idempotente por dedupe). Chamado pelo job de manutenção e pelo painel."""
    from .knowledge import STALE_SQL
    opened = 0
    for r in c.query("SELECT a.id::text AS id, a.slug, (v.regulatory AND v.valid_until < current_date) AS expired FROM kb_articles a JOIN kb_article_versions v ON v.id = a.live_version_id"
                     " WHERE a.live_version_id IS NOT NULL AND (" + STALE_SQL.format(a="a") + " OR (v.regulatory AND v.valid_until < current_date))"):
        kind = "expired" if r["expired"] else "stale"
        if open_work(c, kind, f"{kind}:article:{r['id']}", ref_type="article", ref_id=r["id"], details={"slug": r["slug"]}) is not None:
            opened += 1
    for r in c.query("SELECT f.id::text AS id FROM kb_faqs f WHERE f.status = 'published' AND " + STALE_SQL.format(a="f")):
        if open_work(c, "stale", f"stale:faq:{r['id']}", ref_type="faq", ref_id=r["id"]) is not None:
            opened += 1
    for r in c.query("SELECT r.id::text AS id, r.slug, (r.regulatory AND r.valid_until < current_date) AS expired FROM kb_resources r WHERE r.status = 'published'"
                     " AND (" + STALE_SQL.format(a="r") + " OR (r.regulatory AND r.valid_until < current_date))"):
        kind = "expired" if r["expired"] else "stale"
        if open_work(c, kind, f"{kind}:resource:{r['id']}", ref_type="resource", ref_id=r["id"], details={"slug": r["slug"]}) is not None:
            opened += 1
    for r in c.query("SELECT id::text AS id, key FROM kb_sources WHERE status = 'active' AND (review_due < current_date OR (effective_until IS NOT NULL AND effective_until < current_date))"):
        if open_work(c, "source_review", f"source_review:{r['id']}", ref_type="source", ref_id=r["id"], details={"key": r["key"]}) is not None:
            opened += 1
    return {"touched": opened}
