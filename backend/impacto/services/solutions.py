"""Biblioteca de Soluções — recuperação híbrida e cartões. Pipeline (performance): filtros estruturados + FTS/trigramas (candidatos, teto fixo)
→ pontuação explicável em Python → ordenação → paginação. IA é opcional e NUNCA necessária; plano/assinatura não entram em nenhum ranking
(ADR-007/008; AST em tests/test_architecture.py)."""
from __future__ import annotations

import hashlib
import re

from ..engines.solutions import concepts as K
from ..engines.institutional import intent as inst_intent
from ..engines.institutional import readiness
from ..engines.solutions import intent as I
from ..engines.solutions import scoring as SC

CANDIDATE_LIMIT = 200
CARD_COLS = ("s.id::text AS id, s.org_id::text AS org_id, s.kind, s.stage, s.title, s.summary, s.themes, s.population, s.institutions, s.ods, s.esg, s.uf, s.city,"
             " s.modality, s.duration_months, s.budget_cents, s.raised_cents, s.needed_cents, s.seeking_funding, s.license, s.allow_replication,"
             " s.allow_adaptation, s.attribution_required, s.trust_level, s.disputed, s.source_type, s.source_name, s.source_date, s.is_demo,"
             " s.current_version, s.published_at, s.updated_at, s.visibility, s.problem, s.approach, s.objectives, s.schedule, s.goals,"
             " s.beneficiaries_count, s.project_id::text AS project_id, s.created_by::text AS created_by, s.confidentiality, s.ownership_type, s.rights_holder,"
             " s.compatible_modalities, s.authorization_publish")


def sha(text: str) -> str:
    return hashlib.sha256(norm_q(text).encode()).hexdigest()


def norm_q(t: str) -> str:
    return K.norm(t)


def features(c, ids: list[str]) -> dict[str, dict]:
    """Contagens por solução em lote (evita N+1). Só dados cadastrados."""
    if not ids:
        return {}
    out = {i: {"results": 0, "validated_results": 0, "reported_results": 0, "evidence": 0, "accepted_items": 0, "submitted_items": 0, "kinds_accepted": 0,
               "people": 0, "replication_profile": None, "project_accepted_evidences": 0, "replications_confirmed": 0} for i in ids}
    for r in c.query("SELECT solution_id::text AS sid, count(*) AS n, count(*) FILTER (WHERE status = 'validated') AS v FROM solution_results WHERE solution_id = ANY($1::uuid[]) GROUP BY 1", ids):
        out[r["sid"]].update(results=r["n"], validated_results=r["v"], reported_results=r["n"])
    for r in c.query("SELECT solution_id::text AS sid, count(*) AS n, count(*) FILTER (WHERE status = 'accepted') AS a, count(DISTINCT kind) FILTER (WHERE status = 'accepted') AS k"
                     " FROM solution_evidence WHERE solution_id = ANY($1::uuid[]) AND status <> 'rejected' GROUP BY 1", ids):
        out[r["sid"]].update(evidence=r["n"], submitted_items=r["n"], accepted_items=r["a"], kinds_accepted=r["k"])
    for r in c.query("SELECT solution_id::text AS sid, count(*) AS n FROM solution_people WHERE solution_id = ANY($1::uuid[]) GROUP BY 1", ids):
        out[r["sid"]]["people"] = r["n"]
    for r in c.query("SELECT solution_id::text AS sid, simplicity, cost_level, infra_dependency, territorial_dependency, specialists_needed, documented, training_available, adaptable"
                     " FROM solution_replication_profile WHERE solution_id = ANY($1::uuid[])", ids):
        out[r["sid"]]["replication_profile"] = {k: v for k, v in r.items() if k != "sid"}
    for r in c.query("SELECT s.id::text AS sid, count(e.id) AS n FROM solutions s JOIN evidences e ON e.project_id = s.project_id AND e.status = 'accepted'"
                     " WHERE s.id = ANY($1::uuid[]) GROUP BY 1", ids):
        out[r["sid"]]["project_accepted_evidences"] = r["n"]
    for r in c.query("SELECT solution_id::text AS sid, count(*) AS n FROM solution_replications WHERE solution_id = ANY($1::uuid[]) AND status = 'completed' AND author_confirmed GROUP BY 1", ids):
        out[r["sid"]]["replications_confirmed"] = r["n"]
    return out


def scores_for(s: dict, f: dict) -> dict:
    mat = SC.maturity(s, {"results": f["results"], "evidence": f["evidence"], "people": f["people"], "replication_profile": f["replication_profile"]})
    ev = SC.evidence(s, {"accepted_items": f["accepted_items"], "kinds_accepted": f["kinds_accepted"], "submitted_items": f["submitted_items"],
                         "validated_results": f["validated_results"], "reported_results": f["reported_results"], "project_accepted_evidences": f["project_accepted_evidences"]})
    rep = SC.replicability(s, f["replication_profile"], ev["score"])
    labels = SC.truth_labels(s, f["replications_confirmed"], f["validated_results"])
    return {"maturity": mat, "evidence": ev, "replicability": rep, "labels": labels}


SHARING_LABELS = {"public": "Público", "shareable": "Compartilhável", "shareable_on_request": "Compartilhável mediante autorização",
                  "confidential": "Confidencial", "restricted_use": "Uso restrito"}


def public_card(s: dict, sc: dict, *, mine: bool = False) -> dict:
    """Cartão/lista: só campos de leitura pública. O texto longo (problema/abordagem) fica no perfil."""
    card = {k: s[k] for k in ("id", "kind", "stage", "title", "summary", "themes", "population", "institutions", "ods", "esg", "uf", "city", "modality", "duration_months",
                              "budget_cents", "raised_cents", "needed_cents", "seeking_funding", "license", "allow_replication", "allow_adaptation", "trust_level",
                              "disputed", "source_type", "source_name", "is_demo", "published_at", "confidentiality", "ownership_type", "compatible_modalities")}
    card["sharing_label"] = SHARING_LABELS.get(s["confidentiality"])
    card.update({"labels": sc["labels"], "scores": {"maturity": sc["maturity"]["score"], "evidence": sc["evidence"]["score"], "replicability": sc["replicability"]["score"]}})
    if card["is_demo"]:
        card["demo_notice"] = "DADO DE DEMONSTRAÇÃO (DEMO) — não representa um projeto real."
    if mine:
        card["visibility"] = s["visibility"]
    return card


# ---------------------------------------------------------------------------------------------------------------------- busca
def _tsquery(intent: dict) -> str:
    terms: list[str] = []
    for t in intent["text_terms"]:
        terms.append(t)
    for cid, w in intent["concept_weights"].items():
        if w >= 1.0:
            for t in K.concept_terms(cid):
                terms.append(t)
    seen, parts = set(), []
    for t in terms:
        t = re.sub(r"[^a-z0-9 ]", "", t).strip()
        if len(t) < 2 or t in seen or t in K.load()["_stop"]:
            continue
        seen.add(t)
        parts.append("(" + " <-> ".join(t.split()) + ")")
    return " | ".join(parts[:40])


def _term_in(text: str, term: str) -> bool:
    return (" " + term + " ") in text


def _concept_hit(cid: str, text: str, sol: dict) -> bool:
    if cid in (sol.get("population") or []) or cid in (sol.get("institutions") or []):
        return True
    return any(_term_in(text, t) for t in K.concept_terms(cid))


def search(c, q: dict, *, user_id: str | None = None, org_id: str | None = None, include_trace: bool = True) -> dict:
    """q: text, kinds, stages, themes, population, ods, esg, ufs, budget_min_cents, budget_max_cents, seeking_funding, trust_min, replicable, proven, sort, limit, offset."""
    text = (q.get("text") or "").strip()
    # Termos institucionais viram filtros estruturados (qualificação VERIFICADA, natureza, modalidade); o resto segue para o parser temático.
    ii = inst_intent.parse(text) if text else None
    q = dict(q)
    if ii and ii["matched"]:
        known_mod = set(_modalities(c))
        for key, src in (("qualifications", ii["qualifications"]), ("legal_natures", ii["legal_natures"]), ("modalities", [m for m in ii["modalities"] if m in known_mod])):
            q[key] = sorted(set(q.get(key) or []) | set(src))
        if ii["funding_ready"]:
            q["funding_ready"] = True
        text_for_parse = ii["remaining"]
    else:
        text_for_parse = text
    intent = I.parse(text_for_parse) if text_for_parse else I.parse("")
    text = text_for_parse
    filters = {"ods": q.get("ods") or [], "esg": q.get("esg") or [], "population": q.get("population") or [], "ufs": q.get("ufs") or [], "proven": bool(q.get("proven"))}
    if q.get("budget_min_cents") is not None or q.get("budget_max_cents") is not None:
        filters["budget"] = {"kind": "range", "min_cents": q.get("budget_min_cents"), "max_cents": q.get("budget_max_cents")}
    where, args = ["s.visibility = 'published'"], []

    def a(v):
        args.append(v)
        return f"${len(args)}"

    if q.get("kinds"):
        where.append(f"s.kind = ANY({a(q['kinds'])}::text[])")
    if q.get("stages"):
        where.append(f"s.stage = ANY({a(q['stages'])}::text[])")
    if q.get("themes"):
        where.append(f"s.themes && {a(q['themes'])}::text[]")
    if filters["population"]:
        where.append(f"s.population && {a(filters['population'])}::text[]")
    if filters["ods"]:
        where.append(f"s.ods && {a(filters['ods'])}::smallint[]")
    if filters["esg"]:
        where.append(f"s.esg && {a(filters['esg'])}::text[]")
    if filters["ufs"]:
        where.append(f"s.uf = ANY({a(filters['ufs'])}::text[])")
    if q.get("seeking_funding") is not None:
        where.append(f"s.seeking_funding = {a(bool(q['seeking_funding']))}")
    if q.get("replicable"):
        where.append("s.allow_replication")
    if q.get("trust_min"):
        order = ["unverified", "self_declared", "in_review", "documented", "evidenced", "verified"]
        ok = order[order.index(q["trust_min"]):]
        where.append(f"s.trust_level = ANY({a(ok)}::text[])")
    if filters.get("budget"):
        b = filters["budget"]
        if b["min_cents"] is not None:
            where.append(f"coalesce(s.needed_cents, s.budget_cents) >= {a(b['min_cents'])}::bigint")
        if b["max_cents"] is not None:
            where.append(f"coalesce(s.needed_cents, s.budget_cents) <= {a(b['max_cents'])}::bigint")
    if q.get("legal_natures"):
        where.append(f"EXISTS (SELECT 1 FROM organizations po WHERE po.id = s.org_id AND po.legal_nature_code = ANY({a(q['legal_natures'])}::text[]))")
    if q.get("qualifications"):
        where.append(f"EXISTS (SELECT 1 FROM organization_qualifications pq WHERE pq.org_id = s.org_id AND pq.verification_status = 'verified'"
                     f" AND (pq.expiration_date IS NULL OR pq.expiration_date >= current_date) AND pq.qualification_type = ANY({a(q['qualifications'])}::text[]))")
    if q.get("modalities"):
        where.append(f"s.compatible_modalities && {a(q['modalities'])}::text[]")
    if q.get("sharing"):
        where.append(f"s.confidentiality = ANY({a(q['sharing'])}::text[])")
    if q.get("funding_ready"):
        where.append("s.seeking_funding AND s.needed_cents IS NOT NULL AND s.ownership_type <> 'unknown' AND s.authorization_publish")
    tsq = _tsquery(intent)
    nq = norm_q(text)
    fts_expr, sim_expr = "0::float", "0::float"
    if tsq:
        pt, pn = a(tsq), a(nq)
        fts_expr = f"ts_rank_cd(s.search_doc, to_tsquery('pt_unaccent', {pt}), 32)::float"
        sim_expr = f"word_similarity({pn}, s.title_norm)::float"
        direct = [cid for cid, w in intent["concept_weights"].items() if w >= 1.0]
        arr = a(direct)
        where.append(f"(s.search_doc @@ to_tsquery('pt_unaccent', {pt}) OR s.population && {arr}::text[] OR s.institutions && {arr}::text[]"
                     f" OR word_similarity({pn}, s.title_norm) > 0.45)")
    sql = (f"SELECT {CARD_COLS}, {fts_expr} AS fts, {sim_expr} AS sim FROM solutions s WHERE " + " AND ".join(where) +
           f" ORDER BY {fts_expr} DESC, s.published_at DESC NULLS LAST LIMIT {CANDIDATE_LIMIT}")
    rows = c.query(sql, *args)
    feats = features(c, [r["id"] for r in rows])
    direct = [cid for cid, w in intent["concept_weights"].items() if w >= 1.0]
    expanded = [cid for cid, w in intent["concept_weights"].items() if w < 1.0]
    scored = []
    for r in rows:
        f = feats[r["id"]]
        sc = scores_for(r, f)
        body = " " + K.norm(" ".join(filter(None, [r["title"], r["summary"], r["problem"], r["approach"], r["objectives"], " ".join(r["themes"]), r["city"]]))) + " "
        dh = [cid for cid in direct if _concept_hit(cid, body, r)]
        eh = [cid for cid in expanded if _concept_hit(cid, body, r)]
        if direct:
            cov = min(1.0, 0.8 * len(dh) / len(direct) + 0.2 * min(1.0, len(eh) / 2))
        else:
            cov = min(1.0, r["fts"] * 4)
        fts = min(1.0, r["fts"] * 4)
        feats_in = {"fts": fts, "concept_cov": cov, "trigram": r["sim"], "concepts_in_sol": set(dh) | set(eh) | set(r["population"]),
                    "maturity": sc["maturity"]["score"], "replicability": sc["replicability"]["score"], "evidence": sc["evidence"]["score"]}
        rel = SC.relevance(intent, filters, r, feats_in)
        item = public_card(r, sc)
        item["relevance"] = {"score": rel["score"], "confidence": rel["confidence"], "why": SC.explain(r, rel, intent)}
        if include_trace:
            item["relevance"]["signals"] = rel["signals"]
            item["relevance"]["adjustments"] = rel["adjustments"]
            item["relevance"]["matched_concepts"] = dh
        item["_org"], item["_sol"], item["_feats"] = r["org_id"], r, f
        scored.append(item)
    pros = inst_svc_proponents(c, [i["_org"] for i in scored])
    for item in scored:
        pro = pros.get(item.pop("_org"))
        sol, f = item.pop("_sol"), item.pop("_feats")
        item["proponent"] = pro
        item["funding_readiness"] = readiness.compute(sol, f, pro)
    if q.get("funding_ready"):
        scored = [i for i in scored if i["funding_readiness"]["ready"]]
    sort = q.get("sort") or "relevance"
    if sort == "recent":
        scored.sort(key=lambda x: x["published_at"] or "", reverse=True)
    elif sort == "evidence":
        scored.sort(key=lambda x: -(x["scores"]["evidence"] if x["scores"]["evidence"] is not None else -1))
    elif sort == "budget":
        scored.sort(key=lambda x: (x["budget_cents"] is None, x["budget_cents"] or 0))
    else:
        scored.sort(key=lambda x: (x["relevance"]["score"] is None, -(x["relevance"]["score"] or 0), x["title"]))
    limit, offset = q.get("limit", 25), q.get("offset", 0)
    window = scored[offset: offset + limit + 1]
    out = {"items": window[:limit], "limit": limit, "offset": offset, "has_more": len(window) > limit, "next_offset": offset + limit if len(window) > limit else None,
           "candidates": len(rows), "candidate_cap": CANDIDATE_LIMIT, "capped": len(rows) >= CANDIDATE_LIMIT, "sort": sort}
    out["institutional_filters"] = {"qualifications": q.get("qualifications") or [], "legal_natures": q.get("legal_natures") or [], "modalities": q.get("modalities") or [],
                                    "funding_ready": bool(q.get("funding_ready")), "from_text": ii["matched"] if ii else [],
                                    "note": "Qualificações são filtradas apenas quando VERIFICADAS pela plataforma e vigentes; declaração sem comprovação não entra."}
    out["intent"] = {k: intent[k] for k in ("parser_version", "intent", "concepts", "themes", "ods", "esg", "population", "institutions", "territory", "budget", "months",
                                           "desired", "unmatched_terms", "territory_notes")}
    if not out["items"]:
        out["empty"] = {"message": "Nenhuma solução encontrada.", "suggestions": _suggestions(intent, filters, q)}
    return out


def _suggestions(intent: dict, filters: dict, q: dict) -> list[str]:
    s = []
    if intent["territory"]["ufs"] or filters["ufs"]:
        s.append("Remova o filtro de território — soluções replicáveis podem ser adaptadas para a sua região.")
    if filters.get("budget") or intent["budget"]:
        s.append("Amplie a faixa de orçamento.")
    if intent["unmatched_terms"]:
        s.append("Termos não reconhecidos: " + ", ".join(intent["unmatched_terms"][:5]) + ". Tente sinônimos ou termos mais gerais (ex.: “saúde mental”, “idosos”).")
    if q.get("kinds") or q.get("stages") or q.get("trust_min"):
        s.append("Remova filtros de tipo, estágio ou nível de verificação.")
    s.append("Cadastre sua necessidade: uma OSC pode ser convidada a propor uma solução.")
    return s


def log_search(c, user_id, org_id, text: str, intent: dict, mode: str, n: int, ai_used: bool = False) -> None:
    """Registra apenas o hash da consulta e a intenção estruturada — nunca o texto bruto (privacidade)."""
    from ..db.pq import Json
    c.run("INSERT INTO solution_search_log(user_id, org_id, query_sha256, parser_version, mode, intent, result_count, ai_used) VALUES ($1,$2,$3,$4,$5,$6,$7,$8)",
          user_id, org_id, sha(text), intent["parser_version"], mode, Json({"concepts": [x["id"] for x in intent["concepts"]], "ods": intent["ods"],
                                                                         "ufs": intent["territory"]["ufs"], "intent": intent["intent"]}), n, ai_used)


def get_solution(c, sid: str, *, for_owner_org: str | None = None) -> dict | None:
    return c.one(f"SELECT {CARD_COLS}, s.learnings, s.challenges, s.limitations, s.usage_conditions, s.ip_notes, s.period_start, s.period_end, s.team_size, s.review_requested_at, s.verified_at,"
                 f" s.verification_note, s.ibge_code, s.parent_id::text AS parent_id FROM solutions s WHERE s.id = $1", sid)


def inst_svc_proponents(c, org_ids):
    from . import institutional as inst
    return inst.proponents(c, org_ids)


def _modalities(c) -> dict:
    from . import institutional as inst
    return inst.catalog(c, "funding_modality").get("funding_modality", {})
